"""Path 2: a signal → every library candidate → combination → tournament → forecast (DM6).

Given a search with events, the pipeline does the following. Everything
specific to the search comes from its experiment module: the events and their
resolution (``observations``), the background density and, where the search
states one, the uncertainty on its count (``background_rate``: the background's
scale θ is then profiled in every fit, the toys and the combination; DM10), the
energy grid, the coupling convention of its published analysis
(``candidate_values``) and, if the collaboration published one, its own model
space. Nothing here assumes a
particular experiment, target or energy range; LZ's extended window is one
example (docs/dm6_signal.md). The steps:
1. fits every candidate of a library model space (``inference.signal_fit``);
2. groups the candidates into degeneracy classes at a given number of events
   (DM4's single-linkage classes);
3. computes the global significance over the whole space by background-only
   toys (``look_elsewhere``), with the one-event closed form as a check;
4. carries every member of the leading degeneracy classes (up to
   ``CLASS_MEMBERS`` each, every interaction and isospin first) into the tier-1 combination with the null
   experiments (``combination``), since members that fit the signal alike can
   differ in the null experiments;
5. flags each of them for the halo, the nuclear responses, the validity of
   the interaction and the size of the coupling;
6. judges each of them, at its best-fit coupling, against the curated
   complementary constraints (``constraints.verdicts``, DM7): a verdict per
   record, recorded beside the ranking;
7. ranks them, with the background alone, in the tournament
   (``dm_tournament``);
8. forecasts what would separate the leaders (``forecast``).

**The halo** (``SignalRequest.halo``; halo phase 1). Unset, every search keeps its own published halo: the signal
search's for its fit and toys, each null search's for its limit (a difference is noted, never reconciled), the
default SHM for the complementary verdicts and the forecast, and the halo flags vary one parameter at a time. With a
fixed common benchmark (``halo_choice.FixedHalo``), the fit, the toys, the null limits (each by the direct route at
that halo, or by its own published procedure where that halo is its published one), the halo and nuclear flags (now
from the benchmark), the complementary verdicts, the forecast and the physical eligibility's Track 1 points all use
it. A search with no halo variation (a private search) is refused at the benchmark, never calculated at another halo.
The halo in force is ``halo_region.using``'s, the same that Track 1 and Explain a signal put in force. A generated
benchmark (SHM++, halo phase 2) gives the fit, the toys, the null limits and the forecast its detector-frame table and
the complementary verdicts (capture in the Sun) its Sun-frame table (``FixedHalo.detector``, ``FixedHalo.solar``); its
halo flags generate SHM++ again at each changed parameter (``halo_choice.varied``), labelled as sensitivity checks.

**The halo models compared** (``SignalRequest.halos``; the owner, 2026-11-18, the signal best fits plan, phase B).
The whole pipeline runs once at each fixed benchmark named (every available family: the SHM and SHM++), each as
above; the result is the first halo's run, with ``SignalResult.halo_scan`` beside it: every candidate's standing at
every halo ranked together (the AIC of each against the same background-only hypothesis, which no halo changes), and
the global significance over every candidate at every halo, by toys over all their signal shapes (choosing the halo
is part of the look-elsewhere effect).
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
from pydantic import Field

from adroit.constraints import verdicts as complementary
from adroit.core.dm_state import (ConstraintVerdict, DarkMatterParticle, ExpectedSignal, HaloModel,
                                 InteractionModel, NuclearModel)
from adroit.core.model_spec import ModelSpec
from adroit.core.model_preferences import ModelPreference,StyleDeclaration,select
from adroit.core.certificate import Certificate
from adroit.core.eligibility import CandidateEligibility,EligibilitySettings
from adroit.core.halo_choice import FixedHalo, Resolution
from adroit.core.state import StrictModel
from adroit.experiments import registry as modules
from adroit.experiments.base import ExperimentModule
from adroit.inference import combination, dm_tournament, forecast, look_elsewhere, nuisance, signal_fit
from adroit.library.interactions import checks, degeneracy, registry
from adroit.library.interactions.derivation import Derivation
from adroit.orchestrator import exclusion
from adroit.core.chronology import dated_report

LIBRARY_MASSES = [5, 10, 20, 30, 50, 100, 200, 500, 1000, 2000, 5000]
CLOSED_FORM_BACKGROUND = 0.1      # expected background events below which the one-event form is used
CLOSED_FORM_SHARE = 0.1           # outcomes of two or more events, which it leaves out, at most this share of its p
ZERO_SIGNIFICANCE = 1e-9          # a largest local significance at or below it is 0σ (``_toy_significance``)
ALTERNATIVE_HALOS = {"v0 = 220 km/s": {"v0_km_s": 220.0}, "v0 = 260 km/s": {"v0_km_s": 260.0},
                     "v_esc = 500 km/s": {"v_esc_km_s": 500.0}, "v_esc = 600 km/s": {"v_esc_km_s": 600.0}}
FLAG_DELTA_Z = 0.5


class Candidate(StrictModel):
    """One library entry (a card with its couplings) or a user's model (its interaction), at a mass."""

    label: str
    display_label: str = ""           # may be rounded; never used as an identity
    card_id: str = ""
    isospin: str = ""
    mass_gev: float
    splitting_kev: float = 0.0
    values: dict[str, float] = Field(default_factory=dict)   # card parameters set by a variant (DM9)
    interaction: InteractionModel | None = None               # a user's model at this mass (DM14)
    spin: float = 0.5
    model: str = ""                                           # the user's model's name
    style_declarations: list[StyleDeclaration] = Field(default_factory=list)


class UserModel(StrictModel):
    """A user's typed model as Path 2 candidates (DM14), one per mass."""

    spec: ModelSpec
    derivation: Derivation | None = None   # needed only outside DM13's computable classes
    masses_gev: list[float] = Field(default_factory=list)    # empty: the library's masses
    catalog_reference: str = ''


class SignalRequest(StrictModel):
    """What to explain, with what, and against which null experiments."""

    experiment: str                    # the search with the signal (``registry.load_module``)
    candidates: list[Candidate] = Field(default_factory=list)   # empty: ``model_space(module)``
    user_models: list[UserModel] = Field(default_factory=list)   # (DM14)
    with_library: bool = False         # the library's space beside the given candidates or models (DM14)
    null_modules: list[str] = Field(default_factory=lambda: [
        "CRESST-III 2019", "CDMSlite Run 2", "PICO-60 C3F8 (2019)", "DEAP-3600 (2019)"])
    splittings_kev: list[float] = Field(default_factory=lambda: [0.0])   # for the library's own space
    leaders: int = Field(default=8, ge=1)          # classes carried into the combination
    class_events: float = 20.0
    toys: int = 200_000
    workers: int = 1
    complementary: bool = True
    unverified_records: bool = False   # records (and anomaly records) a person has not yet verified
    model_preferences: list[ModelPreference] = Field(default_factory=list)
    experimental_profile: str = ''
    eligibility_settings: EligibilitySettings = Field(default_factory=EligibilitySettings)
    track1_results: list[str] = Field(default_factory=list)
    # a fixed common benchmark every comparison able to use it is calculated at (module docstring); None: each search's
    # own published halo. Unset requests keep their earlier identity
    halo: FixedHalo | None = Field(default=None, exclude_if=lambda v: v is None)
    # the halo models compared (module docstring): each a fixed benchmark of its own family, the first the one ``halo``
    # holds; empty: one halo. Unset requests keep their earlier identity
    halos: list[FixedHalo] = Field(default_factory=list, exclude_if=lambda v: not v)


class HaloRun(StrictModel):
    """One halo model's run within a comparison: its family, its largest local and its own global significance, and its
    leader."""
    family: str
    label: str
    benchmark: str
    max_local_z: float
    global_z: float
    global_method: str
    leader: str
    candidates: int
    failures: int
    resolution: Resolution | None = None      # its halo as resolved, with its data files' identities


class HaloScan(StrictModel):
    """The halo models compared (module docstring): each run, every candidate's standing at every halo ranked together
    (labels "<candidate> [<halo>]"), and the global significance over every candidate at every halo."""
    runs: list[HaloRun]
    ranking: dm_tournament.TournamentResult
    max_local_z: float
    global_p_toys: float
    global_z: float
    global_method: str
    global_toys: int | None = None
    global_p_interval: list[float] | None = None
    shapes: int = 0                       # the signal shapes the toys searched, over every halo


class TriedVariant(StrictModel):
    """A candidate the agent-led search tried (``signal_search``): a one-step deformation of a leader, fitted and
    combined like any candidate, charged one more free parameter, joining only if it beats its parent by ΔAIC > 2."""
    label: str
    parent: str
    deformation: str
    description: str
    why: str = ""
    z_signal: float | None = None
    z_joint: float | None = None
    p_pg: float | None = None
    aic: float | None = None
    parent_aic: float | None = None
    joined: bool = False
    error: str = ""


class SearchRound(StrictModel):
    """One round of the agent-led search: the leaders it read, the menu's size, what it tried and why."""
    round: int
    leaders: list[str]
    menu: int
    tried: list[TriedVariant] = Field(default_factory=list)
    summary: str = ""
    discarded: list[str] = Field(default_factory=list)


class AgentSearch(StrictModel):
    """The agent-led search after the fixed scan (the owner, 2026-11-18, the signal best fits plan, phase C): its
    rounds, the ranking with every variant that joined, the global significance over everything searched and tried,
    and the agent's interpretation (its numbers checked against the result)."""
    model: str
    rounds: list[SearchRound] = Field(default_factory=list)
    stopped: str = ""
    ranking: dm_tournament.TournamentResult
    tried: int = 0
    max_local_z: float
    global_p_toys: float
    global_z: float
    global_method: str
    global_toys: int | None = None
    global_p_interval: list[float] | None = None
    interpretation: str = ""
    removed_numbers: list[str] = Field(default_factory=list)    # numbers in its text that the result does not hold
    # its requests' dollars, every one (its interpretation included), read from its account after the last (PS-03):
    # settled, and reserved for requests whose bill is not known
    spent_usd: float = 0.0
    uncertain_usd: float = 0.0


class SignalResult(StrictModel):
    """Everything the pipeline found."""

    request: SignalRequest
    fits: list[signal_fit.SignalFit]
    classes: dict[str, int]
    n_classes: int
    max_local_z: float
    global_p_toys: float
    global_p_closed_form: float | None     # only where the background rarely gives two events
    # the toys behind global_p_toys, and the exact (Clopper–Pearson) 95% interval on p (absent in older results)
    global_toys: int | None = Field(default=None, exclude_if=lambda v: v is None)
    global_p_interval: list[float] | None = Field(default=None, exclude_if=lambda v: v is None)
    global_z: float
    global_method: str = ""
    combinations: list[combination.Combination]
    tournament: dm_tournament.TournamentResult
    separations: list[forecast.Separation]
    verdicts: dict[str, list[ConstraintVerdict]] = Field(default_factory=dict)
    created: str = Field(default_factory=lambda: str(date.today()))
    candidate_failures: dict[str, str] = Field(default_factory=dict)
    engine_candidates: list[Candidate] = Field(default_factory=list)  # actual resolved rate inputs; legacy optional
    style_excluded: dict[str,str] = Field(default_factory=dict)
    style_matches: dict[str,dict[str,str]] = Field(default_factory=dict)
    eligibility: dict[str,CandidateEligibility] = Field(default_factory=dict)
    eligible_tournament: dm_tournament.TournamentResult | None = None
    unresolved_tournament: dm_tournament.TournamentResult | None = None
    eligibility_combinations: list[combination.Combination] = Field(default_factory=list)
    # each candidate's complementary relic comparison certificate by record id (M1's ``relic_comparison``), kept
    # beside ``verdicts``; absent in older results
    relic_certificates: dict[str, dict[str, Certificate]] = Field(default_factory=dict, exclude_if=lambda v: not v)
    # each candidate's complementary verdicts' records, by id, in the version they read (``verdicts.judged``: "" where
    # two were read, or the record changed before they were done); absent in older results (the auditor's CV recheck, CW-02)
    verdict_records: dict[str, dict[str, str]] = Field(default_factory=dict, exclude_if=lambda v: not v)
    # the halo as the run resolved it (``halo_choice.resolve``), with the halo data files' identities as read; absent
    # in older results (read from their request when shown)
    halo_resolution: Resolution | None = Field(default=None, exclude_if=lambda v: v is None)
    # the halo models compared (``SignalRequest.halos``); absent where one halo was used
    halo_scan: HaloScan | None = Field(default=None, exclude_if=lambda v: v is None)
    # the agent-led search after the fixed scan (``signal_search``); absent where none ran
    agent_search: AgentSearch | None = Field(default=None, exclude_if=lambda v: v is None)


def library_model_space(masses: list[float] | None = None,
                        splittings_kev: list[float] | None = None) -> list[Candidate]:
    """The library's own space: every operator (O1, O3–O15) and Lagrangian (L1–L20) card,
    isoscalar and isovector, at each mass and splitting."""
    import re
    cards = [c for c in registry.cards() if re.fullmatch(r"O\d+|L\d\d", c)]
    out = []
    for card in cards:
        for i in "sv":
            for m in masses or LIBRARY_MASSES:
                for d in splittings_kev or [0.0]:
                    label = f"{card}{i}@{int(m) if float(m).is_integer() else repr(float(m))}" + (f",d={int(d) if float(d).is_integer() else repr(float(d))}" if d else "")
                    out.append(Candidate(label=label, card_id=card, isospin=i, mass_gev=m,
                                         splitting_kev=d))
    return out


def model_space(module, splittings_kev: list[float] | None = None) -> list[Candidate]:
    """The space Path 2 searches by default: the collaboration's own, if it published one,
    else the library's."""
    published = module.model_space()
    if published and (splittings_kev is None or splittings_kev==[0.0]):
        return [Candidate(**entry) for entry in published]
    return library_model_space(splittings_kev=splittings_kev)


def candidates_for(request: SignalRequest, module) -> list[Candidate]:
    """The candidates of a request: those given, the users' models at their masses, and the library's
    space if asked for (or if nothing else is given)."""
    candidates = list(request.candidates)
    for um in request.user_models:
        from adroit.orchestrator import user_models
        added=user_models.candidates(um.spec,um.masses_gev or LIBRARY_MASSES,um.derivation)
        if um.catalog_reference:
            from adroit.library.personal import Catalog
            revision=Catalog().load(um.catalog_reference)
            declarations=[StyleDeclaration.model_validate(d) for d in revision.provenance.get('model_styles',[])]
            added=[c.model_copy(update={'label':f'{um.catalog_reference}:mass:{float(c.mass_gev).hex()}',
                'display_label':f'{c.display_label} [{um.catalog_reference[-10:]}]',
                'model':um.catalog_reference,'style_declarations':declarations}) for c in added]
        candidates += added
    if request.with_library or not candidates:
        candidates += model_space(module, request.splittings_kev)
    return select(candidates,request.model_preferences)[0] if request.model_preferences else candidates


def _values(module, c: Candidate) -> dict[str, float]:
    """The card's parameters: the module's convention for the isospin, then the candidate's own."""
    return {**module.candidate_values(c.card_id, c.isospin), **c.values}


def _particle(c: Candidate) -> DarkMatterParticle:
    return DarkMatterParticle(mass_gev=c.mass_gev, mass_splitting_kev=c.splitting_kev, spin=c.spin)


def fixed_halo() -> FixedHalo | None:
    """The fixed common benchmark in force (``halo_region.using``: this run's ``SignalRequest.halo``, or Explain a
    signal's), or None: each search's own published halo."""
    from adroit.parameter_space import halo_region
    value = halo_region.preset()
    return value if isinstance(value, FixedHalo) else None


def _signal(module, c: Candidate, halo: HaloModel | None = None, model: NuclearModel | None = None):
    """The candidate's expected signal in the search: at ``halo`` where given (a sensitivity flag's), else at the fixed
    benchmark in force, else at the search's own published halo."""
    conventions = module.conventions()
    fixed = fixed_halo()
    return signal_fit.true_energy(module.expected_signal(
        _particle(c), _interaction(module, c), halo or (fixed.detector() if fixed is not None else None) or conventions.halo,
        model or conventions.nuclear_model))


def _smeared(shape: np.ndarray, energies: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """A normalised shape seen through a Gaussian resolution σ(E) (evaluated at the seen energy) on the grid: the
    data's own smearing and normalisation on the window (``signal_fit.event_densities``; the audit's A09)."""
    return signal_fit.event_densities(energies, shape, energies, np.broadcast_to(np.asarray(sigma, float),
                                                                                energies.shape))


def _sensitivity(module, c: Candidate, z: float, mu_hat: float, what: str,
                 halo: HaloModel | None = None, model: NuclearModel | None = None) -> str:
    """A flag if Z moves by more than 0.5 or the best-fit coupling by more than a factor 2."""
    events, sigma = module.observations()
    b = module.background_at(events)
    signal = _signal(module, c, halo=halo, model=model)
    if signal.total_events <= 0.0:
        return f"{what}: no events at all"
    f = signal_fit.event_densities(signal.observable, signal.density, events, sigma)
    alternative = signal_fit.fit(c.label, f, b, module.background_rate())
    dz = alternative.z_local - z
    mu = math.sqrt(alternative.s_hat / signal_fit.seen_events(signal.observable, signal.density, sigma)) \
        if alternative.s_hat > 0 else 0.0
    ratio = mu / mu_hat if mu_hat > 0 else math.inf
    if abs(dz) > FLAG_DELTA_Z or not 0.5 <= ratio <= 2.0:
        return f"{what}: Z {dz:+.2f}, best-fit coupling ×{ratio:.2g}"
    return ""


def _flags(module, c: Candidate, z: float, mu_hat: float) -> list[str]:
    """Halo and nuclear sensitivity, validity, and the size of the coupling. At a fixed benchmark, each halo flag varies
    one of its parameters within its own family (and says so; a generated benchmark's tables are generated again at the
    changed parameter, ``halo_choice.varied``): a sensitivity check, never the benchmark, and never another family.
    Otherwise the search's own halo, the one its fit used, with that parameter changed (the second addendum to cycle
    3, AL3-35, 2026-11-16: the default SHM's had been changed, so "v0 = 220 km/s" for CDMS II Si, whose own v₀ is 220,
    gave ×1.23 where it is ×1.00)."""
    from adroit.core import halo_choice
    fixed = fixed_halo()
    if fixed is None:
        own = module.conventions().halo
        out = [_sensitivity(module, c, z, mu_hat, f"halo ({name})", halo=own.model_copy(update=change))
               for name, change in ALTERNATIVE_HALOS.items()]
    else:
        how = f"{halo_choice.family(fixed.family).label} generated again from" if fixed.generated else "from"
        out = [_sensitivity(module, c, z, mu_hat, f"halo sensitivity ({name}, {how} the fixed benchmark)",
                            halo=halo_choice.varied(fixed, change)) for name, change in ALTERNATIVE_HALOS.items()]
    out.append(_sensitivity(module, c, z, mu_hat, "nuclear (published shell model)",
                            model=NuclearModel.shell_model))
    out = [flag for flag in out if flag]
    if c.card_id:
        out += checks.flags(registry.card(c.card_id), _particle(c), q_max_gev=module.q_max_gev())
    if mu_hat > 4.0 * math.pi:
        out.append(f"coupling: the best fit needs {mu_hat:.3g} times the unit coupling of "
                   f"{module.info.name}'s convention, above 4π")
    return out


def _checked(request: SignalRequest) -> tuple[SignalRequest, ExperimentModule]:
    """The request with its experimental profile applied, and its search, once the inputs may be used: at a fixed
    benchmark, an available family, and no private search (``halo_choice.CONSUMERS``)."""
    from adroit.library.personal import Catalog
    if request.experimental_profile:
        from adroit.library.experimental_profiles import apply_signal
        request=apply_signal(request)
    for model in request.user_models:
        if model.catalog_reference:
            Catalog().verify_calculation(model.catalog_reference,model.spec,'track2',model.derivation)
    module = modules.load_module(request.experiment)
    if hasattr(module,'bound') and module.bound.contract.role!='signal':
        raise ValueError('private null input cannot be selected as the signal search')
    for name in request.null_modules:
        if name.startswith('private-search:') and modules.load_module(name).bound.contract.role!='null':
            raise ValueError('private signal dataset cannot be selected as an independent null')
    if request.halo is not None:
        refuse_at_benchmark(request.halo, [request.experiment, *request.null_modules])
    if getattr(module, "verified", True) is False and not request.unverified_records and not getattr(module,'interpretation_confirmed',False):
        raise ValueError(f"the anomaly record {request.experiment!r} has not been verified by a person "
                         "(set verified_by, or ask for unverified records)")
    if why := _background_reason(module):
        raise ValueError(why)
    return request, module


def refuse_at_benchmark(fixed: FixedHalo, searches: list[str]) -> None:
    """Refuse a fixed benchmark whose family is not available, or with a private search among ``searches`` (it holds
    only its paper's halo): nothing is calculated at another halo in its place."""
    from adroit.core import halo_choice
    halo_choice.available(fixed.family)
    private = [s for s in searches if s.startswith("private-search:")]
    if private:
        reason = halo_choice.unsupported(halo_choice.resolve(fixed, track="track2"), "private-search")
        raise ValueError(f"{', '.join(private)}: {reason}; run with each search's published halo (no --halo "
                         "benchmark), or without it")


def _background_reason(module) -> str:
    """Why Path 2 cannot rank candidates on this search, or "": its background density is zero (or not a finite
    positive number) at an observed event. The background-only likelihood is then zero, every candidate's improvement
    over it (Z, and the AIC against the background) is infinite, and the tournament had ordered the candidates by label
    and exported NaN ΔAIC (the RZ23 re-audit's RF23-03, 2026-10-23). This is not a search that observes no events,
    which Path 2 supports. Refused, as an unverified record is: no artificial background is added to rescue the
    ranking; a physically justified background model is needed, and ranking candidates by their own likelihoods would
    be a different procedure, not implemented (the owner's review, 2026-10-23)."""
    events, _ = module.observations()
    density = np.atleast_1d(np.asarray(module.background_at(events), dtype=float))
    bad = [float(e) for e, b in zip(np.atleast_1d(np.asarray(events, dtype=float)), density, strict=True)
           if not (math.isfinite(b) and b > 0)]
    if not bad:
        return ""
    where = ", ".join(f"{e:.4g}" for e in bad)
    return (f"the search's background density is not a positive number at the observed event{'s' if len(bad) > 1 else ''}"
            f" at {where} keV: the background-only likelihood is zero, so every candidate's improvement over it (its Z, "
            "and its AIC against the background) is infinite, and Path 2's ranking, built on that improvement, is not "
            "defined. This is not a search that observes no events, which Path 2 supports. No artificial background is "
            "added: a physically justified background model at that energy is needed (comparing the candidates by "
            "their own likelihoods would be a different procedure, not implemented)")


def _fit_all(module: ExperimentModule, candidates: list[Candidate], energies: np.ndarray,
             events: np.ndarray, sigma: np.ndarray, b_events: np.ndarray,
             rate: nuisance.BackgroundRate | None) -> tuple[dict[str, str], list[Candidate],
                                                           list[ExpectedSignal], list[signal_fit.SignalFit],
                                                           list[Candidate]]:
    """(failures, the completed candidates, their signals, fits and engine candidates)."""
    failures, completed, signals, fits, engine_candidates = {}, [], [], [], []
    for c in candidates:
        try:
            engine_candidate = c.model_copy(update={"interaction": _interaction(module, c)})
            signal = _signal(module, engine_candidate)
            fit = signal_fit.fit(c.label, signal_fit.event_densities(energies, signal.density, events, sigma),
                                 b_events, rate)
        except (KeyError, ValueError, RuntimeError, ArithmeticError) as error:
            failures[c.label] = f"signal fit failed: {type(error).__name__}: {error}"
            continue
        completed.append(c)
        signals.append(signal)
        fits.append(fit)
        engine_candidates.append(engine_candidate)
    return failures, completed, signals, fits, engine_candidates


def _no_fits(request: SignalRequest, failures: dict[str, str], style_excluded: dict[str, str],
             style_matches: dict[str, dict[str, str]]) -> SignalResult:
    """The result when no candidate's fit completed: nothing ranked, every failure kept."""
    return SignalResult(request=request, fits=[], classes={}, n_classes=0, max_local_z=0,
        global_p_toys=1, global_p_closed_form=None, global_z=0, global_method="not computed: no completed candidate fits",
        combinations=[], tournament=dm_tournament.run([]), separations=[], candidate_failures=failures,
        style_excluded=style_excluded,style_matches=style_matches,
        eligibility={label:CandidateEligibility(label=label,reasons=[reason]) for label,reason in failures.items()},
        eligible_tournament=dm_tournament.run([]),unresolved_tournament=dm_tournament.run([]))


def _classes(candidates: list[Candidate], signals: list[ExpectedSignal], energies: np.ndarray,
             class_events: float) -> tuple[np.ndarray, np.ndarray, list[list[str]], dict[str, int]]:
    """(normalised shapes, which of them are live, DM4's degeneracy classes, each label's class)."""
    shapes = np.array([np.asarray(s.density) / s.total_events if s.total_events > 0
                       else np.zeros(energies.size) for s in signals])
    live = shapes.sum(axis=1) > 0
    labels = [c.label for c in candidates]
    j = degeneracy.jeffreys_matrix(np.where(live[:, None], shapes, 1.0 / np.ptp(energies)), energies)
    groups = degeneracy.classes(labels, j, class_events)
    classes = {label: n for n, members in enumerate(groups) for label in members}
    return shapes, live, groups, classes


def _caveats(request: SignalRequest, fits: list[signal_fit.SignalFit], classes: dict[str, int],
             failures: dict[str, str], style_excluded: dict[str, str], searched: int) -> str:
    """What the global significance is conditional on, appended to how it was found."""
    method = ""
    if style_excluded:
        method += (f"; the toys search all {searched} candidates before the style filter, so the filter does "
                   "not shrink the trials factor")
    if failures:
        method += "; conditional on completed candidates; failed candidates remain unresolved"
    if request.model_preferences:
        method += '; over the explicitly selected NR candidate space; researcher style declarations are not theory certificates'
    left_out = _uncombined(fits, classes, request.leaders)
    if left_out:
        method += f"; {left_out} members of the leading classes beyond {CLASS_MEMBERS} each were not combined"
    return method


def _combine_leaders(module: ExperimentModule, request: SignalRequest, fits: list[signal_fit.SignalFit],
                     classes: dict[str, int], by_label: dict[str, Candidate], failures: dict[str, str],
                     certificates: dict | None = None, read: dict | None = None,
                     ) -> tuple[list[combination.Combination], dict[str, list[str]],
                                dict[str, list[ConstraintVerdict]]]:
    """The leaders' combinations with the null experiments, their flags and verdicts (the versions of the records each
    candidate's verdicts read into ``read``, by label).

    A failed null calculation is added to ``failures`` and the leader kept with no null coverage.
    """
    combos, flags, judged = [], {}, {}
    for fit_ in _leaders(fits, classes, request.leaders):
        c = by_label[fit_.label]
        try:
            combos.append(_combine(module, c, fit_, request))
        except (KeyError, ValueError, RuntimeError) as error:
            failures[c.label] = f"null calculation failed: {type(error).__name__}: {error}"
            partial = _combine(module, c, fit_, request.model_copy(update={"null_modules": []}))
            combos.append(partial.model_copy(update={"null_coverage": "none", "omitted_nulls": {
                name: failures[c.label] for name in request.null_modules}}))
        flags[c.label] = _flags(module, c, fit_.z_local, combos[-1].mu_hat_signal)
        if "halo mismatch" in combos[-1].note:
            flags[c.label].append(combos[-1].note.split("; ", 1)[1])
        if request.complementary:
            found: dict = {}
            fixed = fixed_halo()
            judged[c.label], versions = complementary.judged(_verdict_candidate(module, c, combos[-1].mu_hat_signal),
                                                             include_unverified=request.unverified_records,
                                                             halo=fixed.solar() if fixed is not None else None,
                                                             certificates=found)
            if certificates is not None and found:
                certificates[c.label] = found
            if read is not None and versions:
                read[c.label] = versions
    return combos, flags, judged


def _eligibility_combinations(module: ExperimentModule, request: SignalRequest,
                              fits: list[signal_fit.SignalFit], classes: dict[str, int],
                              by_label: dict[str, Candidate], combos: list[combination.Combination],
                              eligibility: dict[str, CandidateEligibility]) -> list[combination.Combination]:
    """The leaders' combinations plus those of the eligible and pending leaders; a failure leaves one pending."""
    eligibility_combos=list(combos)
    existing={c.label for c in combos}
    for status in ('eligible','pending'):
        possible=[f for f in fits if eligibility[f.label].status==status]
        for fit_ in _leaders(possible,classes,request.leaders):
            if fit_.label not in existing:
                c=by_label[fit_.label]
                try:
                    eligibility_combos.append(_combine(module,c,fit_,request))
                except (KeyError,ValueError,RuntimeError) as error:
                    eligibility[fit_.label].status='pending'
                    eligibility[fit_.label].reasons.append('null comparison incomplete: '+str(error))
                    continue
                existing.add(fit_.label)
    return eligibility_combos


def _incomplete_coverage(request: SignalRequest, eligibility: dict[str, CandidateEligibility],
                         eligibility_combos: list[combination.Combination], failures: dict[str, str]) -> None:
    """Incomplete requested null coverage leaves a candidate pending; every failure gets a row."""
    for combo in eligibility_combos:
        if request.null_modules and combo.null_coverage not in ('complete','not_requested'):
            row=eligibility[combo.label]
            if row.status!='excluded_point':
                row.status='pending'
                row.reasons.append('requested null coverage is incomplete')
    for label,reason in failures.items():
        if label not in eligibility:
            eligibility[label]=CandidateEligibility(label=label,reasons=[reason])


def _separations(module: ExperimentModule, ranking: dm_tournament.TournamentResult,
                 by_label: dict[str, Candidate]) -> list[forecast.Separation]:
    """What would separate each pair of the (at most five) indistinguishable leaders."""
    top = [label for label in ranking.indistinguishable if label != dm_tournament.NULL][:5]
    pairs = {label: (_particle(by_label[label]), _interaction(module, by_label[label])) for label in top}
    fixed = fixed_halo()
    return [forecast.separate(a, pairs[a], b, pairs[b], module.info.target,
                              halo=fixed.detector() if fixed is not None else None)
            for i, a in enumerate(top) for b in top[i + 1:]]


def run(request: SignalRequest) -> SignalResult:
    """The whole of Path 2 for one search with a signal, with its halo in force (module docstring) and resolved once
    (``SignalResult.halo_resolution``); its halo data files unchanged by its end (``halo_choice.unchanged``). It runs
    with its own copy of the request, and its halo must still be the one resolved at its end (``halo_choice.intact``:
    the auditor's halo phase 1 audit, HA-05, 2026-11-12). With halo models to compare, each in turn (``compared``)."""
    from adroit.core import halo_choice
    from adroit.parameter_space import halo_region
    if request.halos:
        return compared(request)
    request = request.model_copy(deep=True)
    resolution = halo_choice.resolve(halo_region.checked(request.halo), track="track2")
    with halo_region.using(request.halo), halo_choice.holding(resolution.data):   # the halo data as resolved (HB-03)
        result = _run(request)
    halo_choice.intact(resolution, request.halo, track="track2")
    halo_choice.unchanged(resolution)
    return result.model_copy(update={"halo_resolution": resolution})


def _run(request: SignalRequest) -> SignalResult:
    """``run``'s calculation, with its halo in force."""
    request, module = _checked(request)
    unfiltered=candidates_for(request.model_copy(update={'model_preferences':[]}),module) if request.model_preferences else candidates_for(request,module)
    candidates,style_excluded,style_matches=select(unfiltered,request.model_preferences)
    if len({c.label for c in candidates}) != len(candidates):
        raise ValueError("Candidate identifiers must be unique (display labels may be rounded)")
    events, sigma = module.observations()
    energies = np.asarray(module.signal_grid_kev(), dtype=float)
    b_events, rate = module.background_at(events), module.background_rate()
    failures, candidates, signals, fits, engine_candidates = _fit_all(module, candidates, energies, events,
                                                                      sigma, b_events, rate)
    if not fits:
        return _no_fits(request, failures, style_excluded, style_matches)
    theta0 = nuisance.null_fit(b_events, rate)[0] if rate is not None and rate.free else None
    shapes, live, groups, classes = _classes(candidates, signals, energies, request.class_events)
    z_max = max(f.z_local for f in fits)
    searched = shapes[live]
    if style_excluded:          # the toys search every candidate the filter saw, so it cannot shrink the trials factor
        searched = np.vstack([searched, *_shapes(module, [c for c in unfiltered if c.label in style_excluded])])
    p_toys, p_closed, z_global, method = _global_significance(module, searched, energies, z_max,
                                                              request.toys, theta0)
    method += _caveats(request, fits, classes, failures, style_excluded, len(searched))
    by_label = {c.label: c for c in candidates}
    relic_certificates: dict = {}
    verdict_records: dict = {}
    combos, flags, judged = _combine_leaders(module, request, fits, classes, by_label, failures, relic_certificates,
                                             verdict_records)
    ranking = dm_tournament.run(combos, classes, flags,
                                complementary={k: complementary.summary(v) for k, v in judged.items()})
    from adroit.orchestrator.physical_eligibility import assess
    eligibility=assess(request,engine_candidates,fits,module)
    eligibility_combos=_eligibility_combinations(module,request,fits,classes,by_label,combos,eligibility)
    _incomplete_coverage(request,eligibility,eligibility_combos,failures)
    eligible=dm_tournament.run([c for c in eligibility_combos if eligibility[c.label].status=='eligible'],classes,flags)
    unresolved=dm_tournament.run([c for c in eligibility_combos if eligibility[c.label].status=='pending'],classes,flags)
    separations = _separations(module, ranking, by_label)
    return SignalResult(request=request, fits=fits, classes=classes, n_classes=len(groups),
                        max_local_z=z_max, global_p_toys=p_toys, global_p_closed_form=p_closed,
                        global_toys=toy_record(z_max, p_toys, request.toys)[0],
                        global_p_interval=toy_record(z_max, p_toys, request.toys)[1],
                        global_z=z_global, global_method=method, combinations=combos,
                        tournament=ranking, separations=separations, verdicts=judged,
                        candidate_failures=failures, engine_candidates=engine_candidates,
                        style_excluded=style_excluded,style_matches=style_matches,eligibility=eligibility,
                        eligible_tournament=eligible,unresolved_tournament=unresolved,eligibility_combinations=eligibility_combos,
                        relic_certificates=relic_certificates, verdict_records=verdict_records)


def compared(request: SignalRequest) -> SignalResult:
    """The halo models compared (module docstring): the pipeline at each benchmark of ``request.halos``, the first's
    result returned with the comparison (``SignalResult.halo_scan``) and the request as given."""
    halos = list(request.halos)
    if len(halos) < 2 or len({h.family for h in halos}) != len(halos):
        raise ValueError("compare at least two halo models, each of its own family")
    if request.halo is not None and request.halo != halos[0]:
        raise ValueError("a comparison of halo models fixes no other halo: its first halo is the one its result shows")
    results = [run(request.model_copy(update={"halo": h, "halos": []}, deep=True)) for h in halos]
    union = _union_significance(request, halos, results)
    scan = HaloScan(runs=[_halo_run(h, r) for h, r in zip(halos, results)], ranking=_merged_ranking(halos, results),
                    **union)
    first = results[0]
    return first.model_copy(update={"request": first.request.model_copy(update={"halos": halos}), "halo_scan": scan})


def _label(halo: FixedHalo) -> str:
    from adroit.core import halo_choice
    return halo_choice.family(halo.family).label


def _halo_run(halo: FixedHalo, result: SignalResult) -> HaloRun:
    leader = next((e.label for e in result.tournament.ranking), dm_tournament.NULL)
    return HaloRun(family=halo.family, label=_label(halo), benchmark=halo.benchmark, max_local_z=result.max_local_z,
                   global_z=result.global_z, global_method=result.global_method, leader=leader,
                   candidates=len(result.fits), failures=len(result.candidate_failures),
                   resolution=result.halo_resolution)


def _merged_ranking(halos: list[FixedHalo], results: list[SignalResult]) -> dm_tournament.TournamentResult:
    """Every combined candidate at every halo, ranked together (``dm_tournament.run``), each labelled with its halo;
    the degeneracy classes kept apart by halo."""
    combos, classes, flags, judged, offset = [], {}, {}, {}, 0
    for halo, result in zip(halos, results):
        name = _label(halo)
        entries = {e.label: e for e in result.tournament.ranking}
        for c in result.combinations:
            label = f"{c.label} [{name}]"
            combos.append(c.model_copy(update={"label": label}))
            if c.label in result.classes:
                classes[label] = result.classes[c.label] + offset
            entry = entries.get(c.label)
            if entry is not None:
                flags[label] = [f for f in entry.flags if not f.startswith("null coverage pending:")]
                judged[label] = entry.complementary
        offset += result.n_classes
    return dm_tournament.run(combos, classes, flags, complementary=judged)


def _union_significance(request: SignalRequest, halos: list[FixedHalo], results: list[SignalResult]) -> dict:
    """The global significance over every candidate at every halo: background-only toys searching every signal shape
    the runs fitted (each at its halo), against the largest local significance of any of them."""
    names = ", ".join(_label(h) for h in halos)
    return searched_significance(request, halos, max(r.max_local_z for r in results), [],
                                 f"over every candidate at each halo model ({names}: {{shapes}} signal shapes); ")


def searched_significance(request: SignalRequest, halos: list[FixedHalo | None], z_max: float,
                          extra: list[Candidate], what: str) -> dict:
    """The global significance over every candidate the request searches at each of ``halos`` (None: each search's
    own published halo) and the ``extra`` candidates tried after (at the first halo), against ``z_max``, the largest
    local significance of any of them: background-only toys over all their signal shapes. ``what`` begins the method
    (``{shapes}``: how many)."""
    from adroit.core import halo_choice
    from adroit.parameter_space import halo_region
    shapes, module, energies, theta0 = [], None, None, None
    for i, halo in enumerate(halos):
        one = request.model_copy(update={"halo": halo, "halos": []}, deep=True)
        resolution = halo_choice.resolve(halo_region.checked(halo), track="track2")
        with halo_region.using(halo), halo_choice.holding(resolution.data):
            checked, module = _checked(one)
            shapes += _shapes(module, candidates_for(checked.model_copy(update={"model_preferences": []}), module)
                              + (extra if i == 0 else []))
        energies = np.asarray(module.signal_grid_kev(), dtype=float)
        events, _ = module.observations()
        rate = module.background_rate()
        theta0 = nuisance.null_fit(module.background_at(events), rate)[0] if rate is not None and rate.free else None
    if not shapes:
        return dict(max_local_z=z_max, global_p_toys=1.0, global_z=0.0, shapes=0,
                    global_method="not computed: no candidate's signal")
    p_toys, p_closed, z, method = _global_significance(module, np.vstack(shapes), energies, z_max, request.toys, theta0)
    toys, interval = toy_record(z_max, p_toys, request.toys)
    return dict(max_local_z=z_max, global_p_toys=p_toys if p_closed is None else p_closed, global_z=z,
                global_toys=toys, global_p_interval=interval, shapes=len(shapes),
                global_method=what.format(shapes=len(shapes)) + method)


def _shapes(module, candidates: list[Candidate]) -> list[np.ndarray]:
    """The normalised signal shapes of candidates outside the selected space (those that compute and are live)."""
    out = []
    for c in candidates:
        try:
            s = _signal(module, c.model_copy(update={"interaction": _interaction(module, c)}))
        except (KeyError, ValueError, RuntimeError, ArithmeticError):
            continue
        if s.total_events > 0:
            out.append(np.asarray(s.density)[None, :] / s.total_events)
    return out


WINDOW_SMEARING = ("the signal is smeared from true energies inside the window only (events from outside it are "
                   "not modelled) and normalised on the window as seen")


def _global_significance(module, shapes: np.ndarray, energies: np.ndarray, z_max: float,
                         toys: int, theta0: float | None = None) -> tuple[float, float | None, float, str]:
    """``_toy_significance``, its method saying how the signal was smeared where the search has a resolution (the
    audit's A09: the window-truncated smearing is stated)."""
    p_toys, p_closed, z, method = _toy_significance(module, shapes, energies, z_max, toys, theta0)
    if np.any(np.asarray(module.resolution_on_grid()) > 0):
        method += "; " + WINDOW_SMEARING
    return p_toys, p_closed, z, method


def _toy_significance(module, shapes: np.ndarray, energies: np.ndarray, z_max: float,
                      toys: int, theta0: float | None = None) -> tuple[float, float | None, float, str]:
    """(p from toys, p from the one-event closed form or None, the global Z, how it was found).

    An observed maximum of 0σ is reached by every outcome, the empty one included: p = 1 and Z = 0, whatever the
    background. The closed form holds only where one event was observed, the background rarely gives more than one
    (expected count ≤ CLOSED_FORM_BACKGROUND) and is fixed, and one event can reach the observed maximum; elsewhere
    the toys decide (the audit loop's AL1-02, 2026-11-14: the closed form had been taken whatever the observed
    maximum and however many events were observed, so a fit of 0σ had been reported at a global 3σ, and two events
    at an infinite one). With a profiled background (``theta0``, the data's background-only fit), the toys are drawn
    at θ̂₀ and profile θ themselves.
    """
    if z_max <= ZERO_SIGNIFICANCE:
        return 1.0, None, 0.0, ("rule that a largest local significance of 0σ is reached by every outcome, the empty "
                                "one included (p = 1, Z = 0)")                 # read as "… by the rule that …"
    observable = np.array([_smeared(row, energies, module.resolution_on_grid()) for row in shapes])
    background = module.background_on_grid()
    rate = module.background_rate() if theta0 is not None else None
    maxima = look_elsewhere.toys(observable, energies, background, toys, rate=rate, theta0=theta0 or 1.0)
    k = int(np.sum(maxima >= z_max - 1e-9))
    p_toys = k / toys
    expected = float(np.trapezoid(background, energies))
    aside = ""
    if rate is None and expected <= CLOSED_FORM_BACKGROUND and _observed(module) in (1, None):
        p_closed = look_elsewhere.one_event_p_value(z_max - 1e-9, observable, energies, background)
        several = look_elsewhere.several_events(expected)
        if 0.0 < p_closed < 1.0 and several <= CLOSED_FORM_SHARE * p_closed:   # one event reaches it, and alone
            return p_toys, p_closed, look_elsewhere.p_to_z(p_closed), (
                f"one-event closed form (expected background {expected:.2g} events), toys as a check "
                f"({_interval_text(k, toys)})")
        if 0.0 < p_closed < 1.0:                   # AL3-06: outcomes of several events not small against it
            aside = (f"; the one-event closed form (p = {p_closed:.2g}) is left aside: it counts single events only, "
                     f"and outcomes of two or more ({several:.2g}) are not small against it")
    low, high = look_elsewhere.p_interval(k, toys)
    what = (f"{toys:,} background-only toys, the background's rate profiled (expected {expected:.3g} "
            f"events, −{rate.minus:.0%} +{rate.plus:.0%}; background-only fit θ̂₀ = {theta0:.2f})" if rate is not None
            else f"{toys:,} background-only toys (expected background {expected:.3g} events)")
    if k == 0:                                     # the 95% upper bound ≈ 3/N, not 1/N (release audit minor)
        return p_toys, None, look_elsewhere.p_to_z(high), (
            f"{what}; no toy reached the observed maximum: p < {high:.2g} (95%), so Z ≥ "
            f"{look_elsewhere.p_to_z(high):.2f} is a lower bound{aside}")
    return p_toys, None, look_elsewhere.p_to_z(p_toys), (
        f"{what}; {_interval_text(k, toys)}, Z {look_elsewhere.p_to_z(high):.2f}–{look_elsewhere.p_to_z(low):.2f}{aside}")


def _observed(module) -> int | None:
    """How many events the search observed, or None for one that names none (a stand-in for the fit's maths)."""
    events = getattr(module, "observations", None)
    return len(events()[0]) if callable(events) else None


def _toys_drawn(result: SignalResult) -> bool:
    """Whether the result's global p came with toys: not for a maximum of 0σ, nor where nothing was computed (AL2-21:
    the report had given "toys: 1.00e+00" though none was drawn)."""
    return result.max_local_z > ZERO_SIGNIFICANCE and not (result.global_method or "").startswith("not computed")


def toy_record(z_max: float, p_toys: float, toys: int) -> tuple[int | None, list[float] | None]:
    """(the toys drawn, their 95% interval on p) as a result stores them: neither for a maximum of 0σ, which its rule
    decides without drawing a toy (AL2-21: the request's count and an interval of "N of N toys" had been stored)."""
    if z_max <= ZERO_SIGNIFICANCE:
        return None, None
    return toys, toy_interval(p_toys, toys)


def toy_interval(p_toys: float, toys: int) -> list[float]:
    """The exact (Clopper–Pearson) 95% interval on p from the fraction of toys that reached the observed maximum."""
    low, high = look_elsewhere.p_interval(round(p_toys * toys), toys)
    return [float(low), float(high)]


def _interval_text(k: int, n: int) -> str:
    """The toys' p with its Clopper–Pearson 95% interval."""
    low, high = look_elsewhere.p_interval(k, n)
    return (f"p = {k / n:.3g} (95% interval {low:.3g}–{high:.3g}, {k} of {n:,} toys)" if k else
            f"no toy of {n:,} reached it (p < {high:.2g} at 95%)")


def _verdict_candidate(module, c: Candidate, mu_hat: float) -> complementary.Candidate:
    """The candidate at the coupling that explains the signal (every coupling × μ̂)."""
    return complementary.Candidate(label=c.label, particle=_particle(c),
                                   interaction=complementary.scaled(_interaction(module, c), mu_hat))


def _interaction(module, c: Candidate):
    if c.interaction is not None:
        return c.interaction
    return registry.resolve(c.card_id, _particle(c), _values(module, c))


CLASS_MEMBERS = 32      # the most members of one class combined with the null experiments (was 12; 2026-10-12)


def _family(label: str) -> str:
    """A candidate's interaction and isospin without its mass ('L12s@4000' → 'L12s'): members of one family
    differ only in mass, so they meet the null experiments alike."""
    return label.split("@", 1)[0]


def _leaders(fits, classes: dict[str, int], n: int) -> list[signal_fit.SignalFit]:
    """Every member of the n best classes (best by their best signal fit), up to ``CLASS_MEMBERS`` each. Members
    of one class fit the signal alike but can differ greatly in the null experiments (isospin, target), so each
    is combined and the tournament's joint criterion ranks them (release audit M6). Within a class the best fit
    of every distinct interaction and isospin comes first, then the rest by signal fit, so a cap never drops a
    family that the null experiments could tell apart for more masses of one already kept."""
    ordered = sorted(fits, key=lambda f: (-f.z_local, f.label))
    top: list[int] = []
    for f in ordered:
        if classes[f.label] not in top:
            top.append(classes[f.label])
    chosen = set(top[:n])
    kept: dict[int, list[signal_fit.SignalFit]] = {k: [] for k in chosen}
    firsts, seen = [], set()
    for f in ordered:
        key = (classes[f.label], _family(f.label))
        if classes[f.label] in chosen and key not in seen:
            seen.add(key)
            firsts.append(f)
    for f in [*firsts, *(f for f in ordered if f not in firsts)]:
        k = classes[f.label]
        if k in chosen and len(kept[k]) < CLASS_MEMBERS:
            kept[k].append(f)
    return [f for f in ordered if f in kept.get(classes[f.label], [])]


def _uncombined(fits, classes: dict[str, int], n: int) -> int:
    """Members of the n best classes left out by ``CLASS_MEMBERS``."""
    combined = {f.label for f in _leaders(fits, classes, n)}
    top = {classes[f.label] for f in _leaders(fits, classes, n)}
    return sum(1 for f in fits if classes[f.label] in top and f.label not in combined)


def combine(request: SignalRequest, candidate: Candidate) -> combination.Combination:
    """The tier-1 combination of any one candidate (a leader or not) with the request's null experiments, at the
    request's halo."""
    from adroit.parameter_space import halo_region
    with halo_region.using(request.halo):
        return _combine(modules.load_module(request.experiment), candidate, None, request)


def _combine(module, c: Candidate, fit_: signal_fit.SignalFit | None, request: SignalRequest):
    """The tier-1 combination of one candidate with the null experiments."""
    events, sigma = module.observations()
    signal = _signal(module, c)
    f = signal_fit.event_densities(signal.observable, signal.density, events, sigma)
    b = module.background_at(events)
    limits, omitted, rows = {}, {}, {}
    nulls = [name for name in request.null_modules if name != request.experiment]
    if nulls:
        which = ({"bespoke": {repr(c.mass_gev): c.interaction}, "spin": c.spin, "name": c.model or c.label}
                 if c.interaction is not None else {"card_id": c.card_id, "values": _values(module, c)})
        per_module = []
        for halo, names in _null_halos(nulls):
            excl = exclusion.run(exclusion.ExclusionRequest(
                **which, masses_gev=[c.mass_gev], splitting_kev=c.splitting_kev, modules=names,
                workers=request.workers, telescopes=False, halo=halo))
            omitted.update(excl.skipped)
            per_module += excl.per_module
        rows = {row.experiment: row for row in per_module}
        for row in per_module:
            reason = row.omission_reason(0)
            if reason:
                omitted[row.experiment] = reason
            else:
                limits[row.experiment] = row.mu_up[0]
                if row.excludes_only:          # D1: its tension stands, its consistency is not established (C21-04)
                    omitted[row.experiment] = row.excludes_only
    result = combination.combine(c.label, signal_fit.seen_events(signal.observable, signal.density, sigma), f, b,
                                 limits, module.background_rate())
    insensitive = {}
    for name in [n for n in omitted if n in rows and not rows[n].excludes_only]:
        mu_up = rows[name].mu_up[0]
        # a candidate with no fitted signal (μ̂ = 0) has nothing to test, so no null counts as insensitive for it
        if not math.isfinite(mu_up) or (result.mu_hat_signal > 0 and mu_up >= INSENSITIVE * result.mu_hat_signal):
            insensitive[name] = (f"{omitted.pop(name)}; it cannot constrain this candidate (μ_up "
                                 f"{'= ∞' if not math.isfinite(mu_up) else f'≥ {INSENSITIVE:g} μ̂'})")
    resolved = limits or insensitive
    coverage = "not_requested" if not nulls else "none" if not resolved else "partial" if omitted else "complete"
    return result.model_copy(update={"omitted_nulls": omitted, "null_coverage": coverage,
                                     "insensitive_nulls": insensitive, "note": result.note + _halo_note(module, limits)})


def same_halo(a: HaloModel, b: HaloModel) -> bool:
    """Whether two halos are the same distribution and density (their labels aside)."""
    return a.model_copy(update={"label": ""}) == b.model_copy(update={"label": ""})


def _null_halos(nulls: list[str]) -> list[tuple[HaloModel | None, list[str]]]:
    """The null searches by the halo their limits are set at: each its own published halo (None), or, at a fixed
    benchmark, the benchmark (those whose published halo it is keep their own published procedure, the same halo)."""
    fixed = fixed_halo()
    if fixed is None:
        return [(None, nulls)]
    own = [n for n in nulls if same_halo(modules.load_module(n).conventions().halo, fixed.detector())]
    other = [n for n in nulls if n not in own]
    return [(halo, names) for halo, names in ((None, own), (fixed.detector(), other)) if names]


def _halo_note(module, limits: dict[str, float]) -> str:
    """Each null limit is set with its module's own published halo; say where it differs from the signal's
    (release audit minor: one halo was not passed through the combination, and nothing said so). At a fixed benchmark
    every limit and the signal are at that halo: nothing to note."""
    if fixed_halo() is not None:
        return ""
    own = module.conventions().halo
    halos = {name: modules.load_module(name).conventions().halo for name in limits}
    other = sorted(name for name, halo in halos.items() if halo != own)
    if not other:
        return ""
    return f"; halo mismatch: the signal uses {own.label}, while " + "; ".join(
        f"{name} uses {halos[name].label}" for name in other)


INSENSITIVE = 10.0    # a null whose μ_up is at least this many times the signal's μ̂ cannot change a verdict




@dated_report
def report(result: SignalResult) -> str:
    """The Path 2 report in Markdown."""
    from adroit.evidence.halo import line as halo_line
    t = result.tournament
    lines = [f"# Path 2: candidates for the signal in {result.request.experiment}", "",
             f"{len(result.fits)} candidates in {result.n_classes} degeneracy classes (at "
             f"{result.request.class_events:g} events). Largest local significance "
             f"{result.max_local_z:.2f}σ; global significance {_head(result)}.", "",
             "| rank | candidate | class | Z_signal | Z_joint | χ²_PG (p) | ΔAIC | flags |",
             "|---|---|---|---|---|---|---|---|"]
    if result.request.model_preferences:
        lines[2:2]=['Model selection: '+', '.join(p.mode+' '+p.property for p in result.request.model_preferences),
            f'{len(result.style_excluded)} candidates omitted by requirements. Preferences do not change fit scores or ranking.',
            'Model-property declarations retain their reviewed source/scope; they are not theory certificates.','']
    if result.eligible_tournament is not None:
        lines[2:2]=[*_eligibility_report(result),'## Original unfiltered NR reference ranking','']
    for i, e in enumerate(t.ranking, 1):
        lines.append(f"| {i} | {e.label} | {e.class_id if e.class_id is not None else '—'} | "
                     f"{e.z_signal:.2f} | {e.z_joint:.2f} | {e.chi2_pg:.2f} ({e.p_pg:.2f}) | "
                     f"{e.delta_aic:.2f} | {'; '.join(e.flags) or '—'} |")
    lines += ["", (f"Indistinguishable (ΔAIC ≤ {dm_tournament.INDISTINGUISHABLE_DAIC:g}): "
                   f"{', '.join(t.indistinguishable)}; classes {t.classes_in_top_set}."
                   if t.indistinguishable != [dm_tournament.NULL] else
                   "The background alone ranks first, so no indistinguishable candidate set is formed (with one "
                   "parameter every candidate is within ΔAIC ≤ 2 of it) and no separation is forecast."),
              f"Background alone ranks {t.null_rank}.",
              f"Contested: {t.contested or 'no'}.", "",
              "## What would separate the leaders", "",
              "| pair | best target | by | events needed (2σ) |", "|---|---|---|---|"]
    lines += [f"| {s.a} vs {s.b} | {s.best_target} | {s.route} | {s.events_needed:.3g} |"
              for s in result.separations]
    lines += ["", "Null experiments enter by limit-equivalent likelihoods.", ""]
    if result.request.model_preferences:
        lines+=['Model-property matches (yes/no/unknown): '+str(result.style_matches),
                'Omitted by model requirements: '+str(result.style_excluded),'']
    lines += [f"- Candidate calculation pending, {label}: {why}" for label, why in result.candidate_failures.items()] + [""]
    if result.request.experiment.startswith('anomaly:'):
        lines[2:2]=['**Exploratory researcher-confirmed interpretation; source-review status is recorded in captured evidence.**',
            'Global significance remains an unconstrained NR reference over the requested candidate space. '
            'Physical eligibility filtering and new physical-domain calibration are separate milestones.','']
    lines[2:2] = [halo_line("signal", result) + ".", "", *widest_scope(result), *_searched_section(result),
                  *_halo_section(result), *_agent_section(result)]
    return "\n".join(lines + _complementary_section(result)) + "\n"


def significance_parts(z: float, p: float, toys: int | None = None, interval: list[float] | None = None,
                       fmt: str = ".2e") -> tuple[str, str]:
    """(Z, p) of a toy-calibrated global significance as the report, the page and a bundle show them (the post-review
    audit's PT-03): where no toy reached the observed maximum, p is a finite-toy bound ("p < …", the saved 95%
    interval's upper end, else 1/N) and Z a lower bound ("≥"); never "p = 0"."""
    if p == 0 and toys:
        bound = interval[1] if interval and len(interval) == 2 else 1 / toys
        return f"≥{z:.2f}σ", f"p < {bound:.2g}: no toy of {toys:,} reached it"
    return f"{z:.2f}σ", f"p = {p:{fmt}}"


def _head(result) -> str:
    """The report's opening statement of the global significance: a closed-form p as computed, a toy p through
    ``significance_parts`` (R7-04: "p = 0.00e+00" had remained in the report's other sentences)."""
    method = result.global_method or "one-event closed form"
    if result.global_p_closed_form is not None:
        z, p = f"{result.global_z:.2f}σ", f"p = {result.global_p_closed_form:.2e}"
    else:
        z, p = significance_parts(result.global_z, result.global_p_toys, result.global_toys, result.global_p_interval)
    toys = ""
    if _toys_drawn(result):                  # as before R7-04: the toys' p named, closed form or not (AL2-21)
        toys = "; toys: " + significance_parts(result.global_z, result.global_p_toys, result.global_toys,
                                               result.global_p_interval)[1].removeprefix("p = ")
    return f"{z} by the {method} ({p}{toys})"


def scope_text(agent_search: dict | None, halo_scan: dict | None) -> str:
    """The global significance over the widest search a result holds, declared, from its saved fields (the result's,
    or a bundle's saved decisions: PS-02, PT-01): the agent-led search's, else the halo models compared; "" where the
    fixed scan is all."""
    widest = agent_search or halo_scan
    if not widest:
        return ""
    labels = [r.get("label", "") for r in (halo_scan or {}).get("runs", [])]
    where = ("everything searched and tried, the agent-led search's variants included" if agent_search else
             "every candidate at every halo model compared (" + ", ".join(labels) + ")")
    z, p = significance_parts(widest['global_z'], widest['global_p_toys'], widest.get('global_toys'),
                              widest.get('global_p_interval'))
    return (f"Global significance over {where}: {z} ({p}). "
            "The global significance given apart (global_z, global_p_toys, global_method) is the fixed scan's, over its "
            "own candidates" + (f" at {labels[0]}" if labels else "") + ".")


def widest_scope(result: SignalResult) -> list[str]:
    """``scope_text`` of a result, first in its report, in bold; nothing where the fixed scan is all."""
    dump = result.model_dump(mode="json")
    text = scope_text(dump.get("agent_search"), dump.get("halo_scan"))
    return [f"**{text}**", ""] if text else []


def _number(x: float) -> str:
    return f"{int(x):,}" if float(x).is_integer() else f"{x:g}"


def searched(result: SignalResult) -> str:
    """What the run searched and how it ranked, in one paragraph (the owner, 2026-11-18: the page and the report had
    not said that the library's interactions are searched)."""
    candidates = result.engine_candidates or []
    cards = sorted({c.card_id for c in candidates if c.card_id})
    users = sorted({c.model for c in candidates if c.model})
    masses = sorted({c.mass_gev for c in candidates if c.card_id})
    isospins = {"s": "isoscalar", "v": "isovector"}
    parts = []
    if cards:
        operators = [c for c in cards if c.startswith("O")]
        lagrangians = [c for c in cards if c.startswith("L")]
        other = [c for c in cards if c not in operators + lagrangians]
        kinds = ([f"{len(operators)} non-relativistic operators ({', '.join(operators)})"] if operators else []) + (
            [f"{len(lagrangians)} Lagrangians ({lagrangians[0]}–{lagrangians[-1]})"] if lagrangians else []) + (
            [f"{len(other)} published models of the search" if not operators and not lagrangians else
             f"{len(other)} other cards"] if other else [])
        spins = sorted({isospins.get(c.isospin, c.isospin) for c in candidates if c.card_id and c.isospin})
        parts.append(" and ".join(kinds) + (f", each {' and '.join(spins)}" if spins else "") +
                     (f", at {len(masses)} masses from {_number(masses[0])} to {_number(masses[-1])} GeV" if masses
                      else ""))
    if users:
        parts.append(f"{len(users)} of your own model(s) at their masses")
    space = "; ".join(parts) or "the candidates given"
    return (f"Searched: {len(result.fits)} candidate fits ({space}). Each is fitted to the events by its likelihood "
            f"ratio against the background alone; the leading {result.request.leaders} degeneracy classes are combined "
            "with the null searches and ranked by AIC (−Z_joint² + 2 per free parameter, lowest first; within ΔAIC ≤ "
            f"{dm_tournament.INDISTINGUISHABLE_DAIC:g} indistinguishable); the significance after the look-elsewhere "
            "effect counts every candidate searched.")


def _searched_section(result: SignalResult) -> list[str]:
    return ["## What was searched", "", searched(result), ""]


def _agent_section(result: SignalResult) -> list[str]:
    """The agent-led search (``SignalResult.agent_search``): the significance over everything tried, each round, the
    ranking with the variants that joined, and the agent's interpretation, labelled as its reading."""
    search = result.agent_search
    if search is None:
        return []
    lines = ["## The agent-led search", "",
             "Global significance over everything searched and tried: %s (%s; %s). " % (*significance_parts(
                 search.global_z, search.global_p_toys, search.global_toys, search.global_p_interval),
                 search.global_method) + f"{search.tried} variants tried in "
             f"{len(search.rounds)} round(s) by {search.model}; " + (f"stopped: {search.stopped}." if search.stopped
                                                                      else "every round run.")
             + f" Its language model cost ${search.spent_usd:.4f} settled"
             + (f", ${search.uncertain_usd:.4f} reserved for requests whose bill is not known" if search.uncertain_usd
                else "") + ".",
             "The variants were chosen after the data were seen: each is charged one more free parameter, and joins only "
             "if it beats its parent by ΔAIC > 2. The ranking and promotion above are of the fixed scan.", ""]
    for r in search.rounds:
        lines.append(f"- Round {r.round}: leaders {', '.join(r.leaders)}; {r.menu} options; "
                     + ("; ".join(f"{t.label} ({t.description}{': joined' if t.joined else ''}"
                                  + (f"; ΔAIC vs its parent {t.aic - t.parent_aic:+.2f}" if t.aic is not None
                                     and t.parent_aic is not None else f"; {t.error}" if t.error else "") + ")"
                                  for t in r.tried) or "nothing tried")
                     + (f". {r.summary}" if r.summary else ""))
    lines += ["", "| rank | candidate | Z_signal | Z_joint | ΔAIC |", "|---|---|---|---|---|"]
    lines += [f"| {i} | {e.label} | {e.z_signal:.2f} | {e.z_joint:.2f} | {e.delta_aic:.2f} |"
              for i, e in enumerate(search.ranking.ranking[:15], 1)]
    if search.interpretation:
        lines += ["", f"**The agent's interpretation ({search.model}; AI can make mistakes):** {search.interpretation}"]
        if search.removed_numbers:
            lines.append(f"(Numbers its text gave that the result does not hold were removed: "
                         f"{', '.join(search.removed_numbers)}.)")
    return lines + [""]


def _halo_section(result: SignalResult) -> list[str]:
    """The halo models compared (``SignalResult.halo_scan``): the global significance over every halo, each halo's
    run, and the ranking together; nothing where one halo was used."""
    scan = result.halo_scan
    if scan is None:
        return []
    first = scan.runs[0].label
    lines = ["## Halo models compared", "",
             "Global significance over every candidate at every halo: %s (%s; %s). " % (*significance_parts(
                 scan.global_z, scan.global_p_toys, scan.global_toys, scan.global_p_interval), scan.global_method)
             + f"Largest local significance {scan.max_local_z:.2f}σ.",
             f"The rest of this report, and promotion, are of the {first} run; each halo's own run:", ""]
    lines += [f"- {r.label} ({r.benchmark}): {r.candidates} fits, largest local {r.max_local_z:.2f}σ, its own global "
              f"{r.global_z:.2f}σ; leader {r.leader}" + (f"; {r.failures} pending" if r.failures else "")
              for r in scan.runs]
    lines += ["", "| rank | candidate [halo] | Z_signal | Z_joint | ΔAIC |", "|---|---|---|---|---|"]
    lines += [f"| {i} | {e.label} | {e.z_signal:.2f} | {e.z_joint:.2f} | {e.delta_aic:.2f} |"
              for i, e in enumerate(scan.ranking.ranking[:20], 1)]
    t = scan.ranking
    lines += ["", (f"Indistinguishable across halos (ΔAIC ≤ {dm_tournament.INDISTINGUISHABLE_DAIC:g}): "
                   f"{', '.join(t.indistinguishable)}." if t.indistinguishable != [dm_tournament.NULL] else
                   "The background alone ranks first at every halo."), ""]
    return lines

def _eligibility_report(result: SignalResult) -> list[str]:
    """Show point-scoped pruning and separate eligible/unresolved reference rankings."""
    lines=['## Physical eligibility of fitted hypotheses','',
        'The preceding tournament and global significance remain the original unfiltered NR reference. '
        'These views do not recalibrate significance or exclude whole model families. '
        'Only spectrum/likelihood-matched physical points can inherit their NR score.','',
        '| hypothesis | status | physical point | excluded by / pending | constraint calculation |',
        '|---|---|---|---|---|']
    for label,row in result.eligibility.items():
        lines.append(f'| {label} | {row.status} | {row.point.model_dump() if row.point else "unresolved completion/point"} | '
            f'{"; ".join(row.excluded_by+row.reasons) or "evaluated comparisons survived"} | {_constraint_origin(row)} |')
    for title,tournament in [('Eligible fitted points',result.eligible_tournament),('Unresolved hypotheses — provisional NR reference',result.unresolved_tournament)]:
        lines+=['',title+': '+', '.join(e.label for e in tournament.ranking),
                'Ranking uses unchanged NR AIC scores within this view; background alone is retained.']
    lines+=['','A rejected fitted point may have other unresolved parameter branches. Required model styles are separate from physical eligibility.','']
    return lines


def _constraint_origin(row: CandidateEligibility) -> str:
    """Where a fitted point's constraints came from: computed here, or reused from a saved Track 1 result, with the
    version reused (its result's digest), or, in a result saved before ADROIT kept it, that the version is not
    recorded (the auditor's CX recheck, CY-01, 2026-11-01)."""
    if row.constraints_origin != 'saved_exact_track1_point':
        return row.constraints_origin
    from pathlib import Path
    where = f'`{Path(row.reused_result).parent.name}`' if row.reused_result else 'a saved Track 1 result'
    if row.reused_result_sha256:
        return f'saved Track 1 point of {where} (its result as reused: SHA-256 {row.reused_result_sha256[:12]}…)'
    return f'saved Track 1 point of {where}; the version reused is not recorded (saved before ADROIT kept it)'


def _complementary_section(result: SignalResult) -> list[str]:
    """Each leader's verdicts: what excludes it, under which assumptions, and what cannot yet be said."""
    lines = ["## Complementary constraints (tiers 2 and 3)", ""]
    if not result.verdicts:
        return lines + ["Not applied (no usable record; records wait for a person's verification, "
                        "or the request switched them off)."]
    if result.request.unverified_records:
        lines += ["Records a person has not yet verified are used here, on request.", ""]
    lines += ["| candidate | constraint | verdict | assumptions or calculation needed | detail |",
              "|---|---|---|---|---|"]
    for label, verdicts_ in result.verdicts.items():
        for v in verdicts_:
            outcome = {True: "excluded", False: "allowed", None: "—"}[v.excluded]
            if v.native_excluded is not None:
                outcome += f" (native {100 * v.confidence_level:g}%: {'excluded' if v.native_excluded else 'allowed'})"
            why = "; ".join(v.assumptions) if v.excluded is not None else v.needed_calculation
            lines.append(f"| {label} | {v.constraint_id} | {outcome} | {why} | {v.note} |")
    unknown = sorted({rid for read in result.verdict_records.values() for rid, held in read.items() if not held})
    if unknown:
        lines += ["", f"Which version of {', '.join(unknown)} these verdicts read is not known: the record was read "
                      "in two versions, or changed before they were done. Their provenance is not certified; run the "
                      "study again."]
    return lines

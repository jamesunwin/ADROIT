"""Path 1 for library models: a card → rates → every experiment module → exclusion limits (DM5).

Given an interaction card and its parameters, the pipeline resolves the card
to operator coefficients, predicts the signal in each experiment module, and
sets each module's upper limit on the interaction's strength: the factor μ
by which all its couplings may be multiplied (the rate goes as μ²). The
result gives, per module and mass, μ_up and whether the module is validated
there, and the envelope over the validated modules: the strongest limit at
each mass. The envelope is not a statistical combination; that is DM6's
joint likelihood.

**Two routes to a module's limit.**
- If the interaction is proportional to one of the module's reference
  interactions (spin-independent, or spin-dependent on protons or neutrons),
  the module's published procedure for that reference is used
  (``ExperimentModule.reference_limits``) and rescaled. By linearity this is
  exact. It also reproduces the collaboration's own procedure, and it reuses
  the xenon searches' cached templates.
- Otherwise the signal is computed and the module's own statistics set the
  limit.

**Neutrino telescopes (tier 2, DM7).** Capture in the Sun goes as μ², so a
telescope's limit on the annihilation rate becomes a limit on μ at each mass,
μ_up = √(C_allowed / C(μ = 1)), under its assumptions: equilibrium, and a
channel (b b̄, the softest, and τ⁺τ⁻, among the hardest, bracket it). These
limits are listed beside the modules', never in the envelope, and only from
records a person has verified unless the request asks otherwise.

**Validated.** A result counts as validated where the mass lies in the
module's validated range for the matching kind (``status``). By the direct
route it depends on the response (``direct_validation``, release audit M8):
- elastic O₁ in the contact limit, any isospin: the module's spin-independent
  range (the same Helm response, weighted by its target's Z and A − Z);
- elastic O₄ in the contact limit: the module's spin-dependent range for
  each nucleon that couples;
- any other structure or splitting: only where that structure has been
  validated against published limits on the module's target with the same
  nuclear responses (``experiments.structures``), at that splitting and mass.
Anything else is unvalidated, with the reason, and is left out of the
envelope and of Track 2's combinations. (Until R6 the union of the module's
SI and SD ranges was used: PICO-60, validated for SD-proton only, set
isovector O₁ and anapole limits.)
"""

from __future__ import annotations

import subprocess

import math
from datetime import date
from pathlib import Path

import numpy as np
from pydantic import Field, model_validator

from adroit.core.dm_state import (ConstraintClass, CrossSectionKind, DarkMatterParticle, HaloModel,
                                  InteractionModel, NuclearModel)
from adroit.core.state import StrictModel
from adroit.experiments import registry as modules
from adroit.experiments import status
from adroit.experiments.base import (REFERENCE_SIGMA_CM2, DataUnavailable, ExperimentModule,
                                     reference_interaction)
from adroit.library.interactions import checks, degeneracy
from adroit.library.interactions import registry as library
from adroit.core.chronology import dated_report


class ExclusionRequest(StrictModel):
    """What to exclude: a card with its parameters, over masses, in chosen modules."""

    card_id: str = ""                      # a library card, or "" for a bespoke interaction
    bespoke: dict[str, InteractionModel] = Field(default_factory=dict)   # mass (GeV, as text) → interaction
    spin: float = 0.5                      # the dark matter's spin (scalar dark matter: 0)
    name: str = ""                         # the model's name, for a bespoke interaction
    values: dict[str, float] = Field(default_factory=dict)
    masses_gev: list[float] = Field(default_factory=lambda: np.geomspace(1.0, 1e4, 25).tolist())
    masses_by_module: dict[str, list[float]] = Field(default_factory=dict)
    splitting_kev: float = 0.0
    modules: list[str] = Field(default_factory=list)       # empty: every registered module
    halo: HaloModel | None = None                          # None: each module's published halo
    nuclear_model: NuclearModel | None = None              # None: each module's published model
    workers: int = Field(default=1, ge=1)
    telescopes: bool = True                                 # tier-2 limits from capture in the Sun
    unverified_records: bool = False                        # records no person has verified yet
    confidence_level: float = Field(default=0.9, gt=0, lt=1)

    @model_validator(mode="after")
    def unique_mass_keys(self) -> ExclusionRequest:
        """Reject ambiguous numeric aliases; never choose a nearby interaction."""
        masses = [float(key) for key in self.bespoke]
        if any(not math.isfinite(m) or m <= 0 for m in masses) or len(set(masses)) != len(masses):
            raise ValueError("Bespoke mass keys must be finite, positive and numerically unique")
        return self


class ModuleLimits(StrictModel):
    """One module's limits on the strength μ."""

    experiment: str
    masses_gev: list[float]
    mu_up: list[float]
    validated: list[bool]
    route: str                  # "reference SI", "reference SD-proton", ... or "direct"
    fidelity: str
    note: str = ""
    # why a direct-route mass is unvalidated, by mass (repr); left out of the serialised form when empty
    unvalidated: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)
    confidence_level: float = 0.9
    statistical_construction: str = "experiment module's native procedure"
    # why the limits decide exclusions only (D1: a maximum-gap fallback, ``limits.fallback``), or ""; left out of the
    # serialised form when empty
    excludes_only: str = Field(default="", exclude_if=lambda v: not v)

    def omission_reason(self, index: int) -> str:
        """Why this mass cannot contribute to a validated constraint."""
        if not self.validated[index]:
            return self.unvalidated.get(repr(self.masses_gev[index]),
                                        "outside the module's validated mass/interaction domain")
        if not math.isfinite(self.mu_up[index]) or self.mu_up[index] <= 0:
            return "no finite positive limit at this mass"
        return ""


class TelescopeLimits(StrictModel):
    """A neutrino telescope's limit on μ, through capture in the Sun, for one assumed channel."""

    record_id: str
    channel: str
    masses_gev: list[float]
    mu_up: list[float]              # inf: the Sun captures nothing; nan: outside the record's masses
    assumptions: list[str]
    verified: bool
    confidence_level: float = 0.9
    statistical_construction: str = "native published capture limit; no confidence-level conversion"
    # the version of the record and its curves these limits were computed from (``review_identity.version``): "" where
    # two were read, or the record had changed by the end; absent (None) in a result saved before (CW-02)
    record_version: str | None = Field(default=None, exclude_if=lambda v: v is None)


class ExclusionResult(StrictModel):
    """The limits of every module and their envelope over the validated ones."""

    request: ExclusionRequest
    interaction_name: str
    per_module: list[ModuleLimits]
    skipped: dict[str, str] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    telescopes: list[TelescopeLimits] = Field(default_factory=list)
    created: str = Field(default_factory=lambda: str(date.today()))

    def computed_envelope(self) -> list[tuple[float, float, str]]:
        """(mass, μ_up, module) where a module was computed and is the strongest validated there.

        No curve is interpolated at these points to decide the envelope: the
        fair basis for comparing it with a published picture.
        """
        out = []
        for r in self.per_module:
            for m, mu, ok in zip(r.masses_gev, r.mu_up, r.validated):
                if not ok or not math.isfinite(mu) or mu <= 0:
                    continue
                _, _, source = self.envelope([m])
                if source[0] == r.experiment:
                    out.append((m, mu, r.experiment))
        return sorted(out)

    def envelope(self, masses_gev: list[float] | None = None,
                 validated_only: bool = True) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """(masses, strongest μ_up, which module), interpolating each module in log-log between two neighbouring masses
        of its own that both have a limit: its masses sorted, and no value across a mass with none (the second
        addendum to cycle 3, AL3-36, 2026-11-16: masses out of order had been interpolated as given, and a mass with no
        limit bridged by its neighbours)."""
        grid = np.array(masses_gev or sorted({m for r in self.per_module for m in r.masses_gev}))
        best = np.full(grid.size, math.inf)
        source = [""] * grid.size
        for r in self.per_module:
            m, mu = np.array(r.masses_gev, dtype=float), np.array(r.mu_up, dtype=float)
            keep = np.array([not r.omission_reason(i) for i in range(len(mu))]) if validated_only else (
                np.isfinite(mu) & (mu > 0))
            keep = keep & np.isfinite(mu) & (mu > 0)
            if keep.sum() < 1:
                continue
            order = np.argsort(m, kind="stable")
            m, mu, keep = m[order], mu[order], keep[order]
            for i, x in enumerate(grid):
                value = _module_value(m, mu, keep, float(x))
                if value is not None and value < best[i]:
                    best[i], source[i] = value, r.experiment
        return grid, best, source


def _module_value(m: np.ndarray, mu: np.ndarray, keep: np.ndarray, x: float) -> float | None:
    """One module's μ_up at x, its masses ``m`` sorted: its own at one of them, log-log between the two around x where
    both have a limit (``keep``), else None."""
    if x < m[0] or x > m[-1]:
        return None
    j = int(np.searchsorted(m, x))
    if m[j] == x:
        return float(mu[j]) if keep[j] else None
    if not (keep[j - 1] and keep[j]):
        return None
    return float(np.exp(np.interp(np.log(x), np.log(m[j - 1:j + 1]), np.log(mu[j - 1:j + 1]))))


def _reference_route(interaction: InteractionModel,
                     mass: float) -> tuple[CrossSectionKind, float] | None:
    """(kind, λ) if the interaction is λ times a reference interaction at this mass."""
    for kind in CrossSectionKind:
        reference = reference_interaction(kind, REFERENCE_SIGMA_CM2, mass)
        if degeneracy.proportional(interaction, reference):
            ref = reference.coefficients[0]
            own = next(c for c in interaction.coefficients if c.operator == ref.operator)
            size = ref.proton if ref.proton else ref.neutron
            return kind, (own.proton if ref.proton else own.neutron) / size
    return None


RANGE_TOLERANCE = 1e-4     # the status file rounds its range edges to a few decimals


def _validated(experiment: str, kind: CrossSectionKind | None, mass: float) -> bool:
    """Whether the module is validated at this mass for this kind (any kind if None)."""
    keys = [kind] if kind is not None else list(CrossSectionKind)
    for key in keys:
        span = status.validated_range(experiment, key)
        if span is not None and (span[0] * (1 - RANGE_TOLERANCE) <= mass
                                 <= span[1] * (1 + RANGE_TOLERANCE)):
            return True
    return False


CONTACT_MEDIATOR_GEV = 1.0   # a propagator m²/(q² + m²) with m above this is a contact interaction within ~10%


def direct_validation(module: ExperimentModule, interaction: InteractionModel, particle: DarkMatterParticle,
                      model: NuclearModel) -> str:
    """'' if a direct-route limit of this module is validated for this response (module docstring), else why not."""
    from adroit.experiments import structures
    name, mass, splitting = module.info.name, particle.mass_gev, particle.mass_splitting_kev
    live = [c for c in interaction.coefficients if c.proton or c.neutron]
    contact = all(c.q_power == 0 and (c.mediator_mass_gev is None or c.mediator_mass_gev >= CONTACT_MEDIATOR_GEV)
                  for c in live)
    operators = {c.operator for c in live}
    if not splitting and contact and operators == {1}:
        return "" if _validated(name, CrossSectionKind.si, mass) else \
            "unvalidated: the module's spin-independent procedure is not validated at this mass"
    if not splitting and contact and operators == {4}:
        needed = {CrossSectionKind.sd_proton for c in live if c.proton} | {CrossSectionKind.sd_neutron for c in live
                                                                         if c.neutron}
        missing = sorted(k.value for k in needed if not _validated(name, k, mass))
        return "" if not missing else f"unvalidated: the module's {' and '.join(missing)} procedure is not validated here"
    found = structures.matching(interaction, particle)
    what = f"O{', O'.join(str(o) for o in sorted(operators))}" + (f", δ = {splitting:g} keV" if splitting else "")
    if found is None:
        return f"unvalidated: no validation of this response structure ({what}) against published limits"
    label, entry = found
    target, responses = structures.scope()
    if module.info.target != target or model.value != responses:
        return (f"unvalidated: structure {label} is validated on {target} with {responses} responses; this module "
                f"computes it on {module.info.target} with {model.value}")
    if not structures.validated_at(entry, mass):
        return f"unvalidated: structure {label} is validated only at {entry['validated_gev']} GeV"
    if not _validated(name, None, mass):
        return "unvalidated: the module's procedure is not validated at this mass"
    return ""


DOMINANT = 0.05   # a contact O₁ (or O₄) part giving the module's events to within this fraction decides validation


def contact_part(interaction: InteractionModel) -> InteractionModel | None:
    """The interaction's contact O₁ part, else its contact O₄ part, when it also has other terms: the part its
    validation is judged by if that part carries (nearly) all of a module's events (mini audit: a vector
    mediator's small momentum-dependent terms made its O₁-dominated rate "unvalidated")."""
    live = [c for c in interaction.coefficients if c.proton or c.neutron]
    for operator in (1, 4):
        kept = [c for c in live if c.operator == operator and c.q_power == 0
                and (c.mediator_mass_gev is None or c.mediator_mass_gev >= CONTACT_MEDIATOR_GEV)]
        if kept and len(kept) < len(live):
            return interaction.model_copy(update={"coefficients": kept})
    return None


def _direct_reasons(module: ExperimentModule, request: "ExclusionRequest", masses: list[float],
                    particles: list[DarkMatterParticle], interactions: list[InteractionModel],
                    signals: list) -> dict[str, str]:
    """Why each direct-route mass is unvalidated ('' if validated): by the full structure, or by its contact
    O₁/O₄ part where that part gives the module's events to within ``DOMINANT``."""
    conventions = module.conventions()
    halo = request.halo or conventions.halo
    out = {}
    for m, p, i, s in zip(masses, particles, interactions, signals):
        model = request.nuclear_model or _direct_model(conventions, i)
        why = direct_validation(module, i, p, model)
        part = contact_part(i) if why else None
        if part is not None and s.total_events > 0:
            share = module.expected_signal(p, part, halo, model).total_events / s.total_events
            if abs(share - 1.0) <= DOMINANT:
                why = direct_validation(module, part, p, model)
        out[repr(m)] = why
    return out


def revalidate(result: "ExclusionResult") -> "ExclusionResult":
    """The result with its validated marks recomputed from the current status files."""
    modules = []
    for r in result.per_module:
        if r.route.startswith("reference "):
            kind = CrossSectionKind(r.route.removeprefix("reference "))
            modules.append(r.model_copy(update={"validated": [_validated(r.experiment, kind, m) for m in r.masses_gev]}))
            continue
        module, request = modules_load(r.experiment), result.request
        why = {}
        for m in r.masses_gev:
            particle = DarkMatterParticle(mass_gev=m, mass_splitting_kev=request.splitting_kev, spin=request.spin)
            interaction = interaction_at(request, particle)
            why[repr(m)] = direct_validation(module, interaction, particle, request.nuclear_model or
                                             _direct_model(module.conventions(), interaction))
        modules.append(r.model_copy(update={"validated": [not why[repr(m)] for m in r.masses_gev],
                                            "unvalidated": {k: v for k, v in why.items() if v}}))
    return result.model_copy(update={"per_module": modules})


def modules_load(name: str) -> ExperimentModule:
    """The experiment module of that name (``experiments.registry.load_module``)."""
    return modules.load_module(name)


def _direct_model(conventions, interaction: InteractionModel) -> NuclearModel:
    """The nuclear model for a directly computed interaction.

    A module's spin-independent convention (often the Helm form factor, which
    has no spin responses) serves only interactions made of O1; any other
    operator needs the module's spin-dependent model, which carries the full
    set of responses.
    """
    only_o1 = all(c.operator == 1 for c in interaction.coefficients)
    return conventions.nuclear_model if only_o1 else conventions.spin_dependent_model


def _module_limits(module: ExperimentModule, request: ExclusionRequest,
                   masses: list[float]) -> ModuleLimits:
    """One module's μ_up at the masses, by the reference route where it applies."""
    particles = [DarkMatterParticle(mass_gev=m, mass_splitting_kev=request.splitting_kev, spin=request.spin)
                 for m in masses]
    interactions = [interaction_at(request, p) for p in particles]
    # The reference route is the collaboration's own procedure with its own halo, nuclear model and fermionic
    # dark matter; a request that sets any of them goes by the direct route, which honours them.
    own_conventions = request.halo is None and request.nuclear_model is None and request.spin == 0.5
    routes = [None if request.splitting_kev or not own_conventions else _reference_route(i, p.mass_gev)
              for i, p in zip(interactions, particles)]
    kinds = {r[0] for r in routes if r is not None}
    mu = [math.inf] * len(masses)
    if len(kinds) == 1 and all(r is not None for r in routes):
        kind = kinds.pop()
        options = {"cl": request.confidence_level} if request.confidence_level != 0.9 else {}
        sigmas = module.reference_limits(kind, masses, workers=request.workers, **options)
        mu = [math.sqrt(s / REFERENCE_SIGMA_CM2) / abs(r[1]) for s, r in zip(sigmas, routes)]
        route = f"reference {kind.value}"
    else:
        kind, route = None, "direct"
        conventions = module.conventions()
        signals = [module.expected_signal(p, i, request.halo or conventions.halo,
                                          request.nuclear_model or _direct_model(conventions, i))
                   for p, i in zip(particles, interactions)]
        live = [s for s in signals if s.total_events > 0.0]
        kappas = iter(module.upper_limits(live, cl=request.confidence_level) if live else [])
        mu = [math.sqrt(next(kappas)) if s.total_events > 0.0 else math.inf for s in signals]
    if hasattr(module, "accepts_validation"):
        why = {repr(m): "" if module.accepts_validation(p, i, request.confidence_level) else
               "outside the module's validated mass/interaction domain" for m, p, i in zip(masses, particles, interactions)}
    elif kind is not None:
        why = {repr(m): "" if _validated(module.info.name, kind, m) else
               f"outside the module's validated {kind.value} masses" for m in masses}
    else:
        why = _direct_reasons(module, request, masses, particles, interactions, signals)
    from adroit.parameter_space.limits import fallback_of
    return ModuleLimits(experiment=module.info.name, masses_gev=masses, mu_up=mu, excludes_only=fallback_of(module),
                        validated=[not why[repr(m)] for m in masses], route=route,
                        fidelity=module.info.fidelity.value,
                        note="" if kind else "validated by the response structure (direct route)",
                        unvalidated={k: v for k, v in why.items() if v},
                        confidence_level=request.confidence_level)


TELESCOPE_CHANNELS = ("bb", "tautau")


def telescope_limits(request: ExclusionRequest) -> list[TelescopeLimits]:
    """μ_up from each usable solar-capture record, for the softest and a hard channel, each with the version of its
    record read (``record_version``): the record admitted and its curves read within one collector
    (``searches.records_read``). The auditor's CV recheck, CW-02 (2026-10-30): the curves read as B, between A at both ends of
    the run, were saved and exported as A's; the version read is now kept with the limits, and the run's evidence is
    reconciled against it (``evidence.runtime.finish``)."""
    from adroit.constraints import database, searches
    out = []
    for record in database.usable(request.unverified_records, ConstraintClass.solar_capture):
        with searches.records_read() as read:
            searches.admits(record, request.unverified_records)
            rows = _telescope_rows(request, record)
        out += [row.model_copy(update={"record_version": read.get(record.id, "")}) for row in rows]
    return out


def _telescope_rows(request: ExclusionRequest, record) -> list[TelescopeLimits]:
    """One solar-capture record's limits on μ, a row for each channel."""
    from adroit.constraints import capture, database, verdicts
    kind = "SD_proton" if record.id.endswith("-sd") else "SI_proton"
    curves = database.data(record.id)["limits"][kind]["limits_cm2"]
    rates = {}
    for m in request.masses_gev:
        particle = DarkMatterParticle(mass_gev=m, mass_splitting_kev=request.splitting_kev, spin=request.spin)
        rates[m] = capture.capture_rate(particle, interaction_at(request, particle))
    out = []
    for channel in TELESCOPE_CHANNELS:
        mu = []
        for m in request.masses_gev:
            sigma = database.interpolate_limit(curves[channel], m)
            if sigma is None:
                mu.append(math.nan)
                continue
            allowed = capture.capture_rate(DarkMatterParticle(mass_gev=m), verdicts._reference(kind, sigma, m))
            mu.append(math.sqrt(allowed / rates[m]) if rates[m] > 0 else math.inf)
        out.append(TelescopeLimits(record_id=record.id, channel=channel, masses_gev=list(request.masses_gev),
                                   mu_up=mu, assumptions=[*record.assumptions[:2], f"channel {channel}"],
                                   verified=record.usable))
    return out


def interaction_at(request: ExclusionRequest, particle: DarkMatterParticle) -> InteractionModel:
    """The interaction at the particle's mass: the bespoke one given for that mass, or the card's."""
    if request.bespoke:
        keys = [key for key in request.bespoke if float(key) == particle.mass_gev]
        if len(keys) != 1:
            raise KeyError(f"no unique exact bespoke interaction at {particle.mass_gev!r} GeV")
        return request.bespoke[keys[0]]
    return library.resolve(request.card_id, particle, request.values)


def run(request: ExclusionRequest) -> ExclusionResult:
    """The exclusion limits of one card (or one bespoke interaction) in every chosen module."""
    if not request.card_id and not request.bespoke:
        raise ValueError("an exclusion needs a card or a bespoke interaction")
    names = request.modules or modules.module_names()
    per_module, skipped = [], {}
    for name in names:
        try:
            module = modules.load_module(name)
        except (DataUnavailable, KeyError) as error:
            skipped[name] = str(error)
            continue
        masses = request.masses_by_module.get(name, request.masses_gev)
        try:
            per_module.append(_module_limits(module, request, masses))
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:     # one module never stops the others
            skipped[name] = f"the module's calculation failed: {type(error).__name__}: {error}"
    particle = DarkMatterParticle(mass_gev=request.masses_gev[0],
                                  mass_splitting_kev=request.splitting_kev, spin=request.spin)
    if request.card_id:
        card = library.card(request.card_id)
        flags, name = checks.flags(card, particle, q_max_gev=0.3, values=request.values), card.name
    else:
        flags, name = [], request.name or "bespoke interaction"
    telescopes = []
    if request.telescopes:
        from adroit.constraints import capture, database
        if capture.available():
            telescopes = telescope_limits(request)
        elif database.usable(request.unverified_records, ConstraintClass.solar_capture):
            skipped["neutrino telescopes (capture in the Sun)"] = capture.UNAVAILABLE    # the fallback review's D3
    return ExclusionResult(request=request, interaction_name=name, per_module=per_module,
                           skipped=skipped, flags=flags, telescopes=telescopes)


def plot(result: ExclusionResult, path: Path, to_y=None, y_label: str = "strength μ (× the card's couplings)",
         published: dict[str, tuple[list[float], list[float]]] | None = None, fog: str = "",
         prediction: tuple[list[float], list[float]] | None = None) -> Path:
    """The exclusion plot: each module (solid where validated), the envelope, published curves; with ``fog``
    (a target), its published neutrino floor shaded beneath, and ``prediction`` the model's own curve."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    def convert(mu: float, mass: float) -> float:
        value = (to_y or (lambda u, _: u))(mu, mass)
        return value if math.isfinite(value) and value > 0 else math.nan

    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    drawn = 0
    for r in result.per_module:
        m, ok = np.array(r.masses_gev), np.array(r.validated)
        y = np.array([convert(u, x) for u, x in zip(r.mu_up, m)])
        if not np.isfinite(y).any():
            continue
        line, = ax.plot(m, np.where(ok, y, np.nan), lw=1.4, label=r.experiment)
        ax.plot(m, y, lw=0.8, ls=":", color=line.get_color())
        drawn += 1
    grid, env, _ = result.envelope()
    envelope_y = [convert(u, x) for u, x in zip(env, grid)]
    if np.isfinite(envelope_y).any():
        ax.plot(grid, envelope_y, color="black", lw=2.2, label="envelope of validated modules")
    for t in result.telescopes:
        y = [convert(u, x) for u, x in zip(t.mu_up, t.masses_gev)]
        if np.isfinite(y).any():
            ax.plot(t.masses_gev, y, lw=1.1, ls="-." if t.channel == "bb" else (0, (1, 1)),
                    color="tab:brown", label=f"{t.record_id} ({t.channel}; tier 2, assumptions)")
            drawn += 1
    for label, (m, y) in (published or {}).items():
        ax.plot(m, y, color="grey", lw=0.9, ls="--", label=label)
        drawn += 1
    if prediction is not None:
        ax.plot(*prediction, color="black", lw=1.0, ls="--", label="the model (μ = 1)")
    if drawn:
        ax.set(xscale="log", yscale="log")
        if fog:
            _fog(ax, fog)
        ax.legend(fontsize=7, loc="best")
    else:
        ax.text(0.5, 0.5, "no module is sensitive to this interaction", ha="center",
                transform=ax.transAxes)
    ax.set(xlabel="dark matter mass (GeV)", ylabel=y_label, title=result.interaction_name)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    from adroit.evidence.bindings import write_figure    # its digest kept for the report's binding
    write_figure(fig, path, 130)
    plt.close(fig)
    return path



def _fog(ax, target: str) -> None:
    """The target's published neutrino floor across the plotted masses, the fog shaded beneath it (an overlay)."""
    from adroit.physics.neutrino_fog import published_floor
    masses, sigmas = (np.array(v) for v in published_floor(target))
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    inside = (masses >= x0) & (masses <= x1)
    if not inside.any():
        return
    low = min(y0, sigmas[inside].min() / 3.0)
    ax.fill_between(masses[inside], low / 10.0, sigmas[inside], color="0.85", zorder=0,
                    label=f"neutrino fog ({target}, O'Hare 2021 floor)")
    ax.set_ylim(low, y1)


def plotted_masses(result: ExclusionResult) -> list[float]:
    """Every mass the exclusion plot draws a limit at: each module's, the envelope's and each telescope's."""
    masses = {m for r in result.per_module for m in r.masses_gev} | {m for t in result.telescopes for m in t.masses_gev}
    return sorted(masses | set(result.request.masses_gev))


def si_table(result: ExclusionResult) -> tuple[dict[float, float] | None, str]:
    """(the model's spin-independent nucleon cross section in cm² at every plotted mass, σ = λ² σ_ref where its
    interaction is λ times the SI reference there; or None, with why the σ view is unavailable). Each mass is
    resolved itself, never interpolated (the focused audit's NF-03); a plotted mass where the interaction is not SI's
    multiple (or cannot be resolved) is left out of the table and its limits are not drawn as σ. The view is an
    addition: it never makes Path 1 fail."""
    request = result.request
    if request.splitting_kev or request.halo is not None or request.nuclear_model is not None:
        return None, "a mass splitting, the run's own halo or its own nuclear model (the σ view uses the references')"
    table, refused = {}, []
    for m in plotted_masses(result):
        particle = DarkMatterParticle(mass_gev=m, mass_splitting_kev=0.0, spin=request.spin)
        try:
            route = _reference_route(interaction_at(request, particle), m)
        except (KeyError, ValueError) as error:
            refused.append(f"{m:g} GeV ({error})")
            continue
        if route is None or route[0] is not CrossSectionKind.si:
            refused.append(f"{m:g} GeV ({'not a reference interaction' if route is None else route[0].value})")
            continue
        table[m] = route[1] ** 2 * REFERENCE_SIGMA_CM2
    missing = [m for m in request.masses_gev if m not in table]
    if missing:
        return None, "the interaction is not the SI reference's multiple at " + ", ".join(
            r for r in refused if any(r.startswith(f"{m:g} GeV") for m in missing))
    return table, ("" if not refused else "limits not drawn as σ at " + ", ".join(refused))


def si_predictions(result: ExclusionResult) -> list[float] | None:
    """The model's σ_SI (cm²) at each requested mass (``si_table``), or None where the σ view is unavailable."""
    table, _ = si_table(result)
    return None if table is None else [table[m] for m in result.request.masses_gev]


def sigma_plot(result: ExclusionResult, path: Path, predicted: list[float] | dict[float, float],
               target: str = "Xe") -> Path:
    """The limits as σ_SI (μ_up² times the model's σ at that mass, each mass's own: a mass without one is not drawn),
    the model's σ and the target's neutrino fog. ``predicted``: ``si_table``'s table (or, for the requested masses
    alone, ``si_predictions``' list)."""
    table = predicted if isinstance(predicted, dict) else dict(zip(result.request.masses_gev, predicted))
    return plot(result, path, to_y=lambda mu, m: mu * mu * table.get(m, math.nan), y_label="SI nucleon cross section σ (cm²)",
                fog=target, prediction=(list(result.request.masses_gev), [table[m] for m in result.request.masses_gev]))


def fog_section(result: ExclusionResult, predicted: list[float], target: str = "Xe") -> str:
    """The report's section on σ_SI and the neutrino fog: the figure and, at each mass, the model's σ against the
    floor (an annotation; it decides nothing)."""
    from adroit.physics.neutrino_fog import floor_at
    lines = ["", "## The spin-independent cross section and the neutrino fog", "",
             "![limits as σ_SI, with the neutrino fog](exclusion_sigma_si.png)", "",
             f"The {target} neutrino floor is O'Hare's published n = 2 curve (arXiv:2109.03116): beneath it a discovery "
             "needs a disproportionate exposure. An annotation, not a constraint.", "",
             "| mass (GeV) | the model's σ (cm²) | floor (cm²) | where |", "|---|---|---|---|"]
    for m, s in zip(result.request.masses_gev, predicted):
        floor = floor_at(m, target)
        where = "—" if floor is None else "beneath the floor" if s < floor else "above the floor"
        lines.append(f"| {m:.4g} | {s:.3g} | {'—' if floor is None else f'{floor:.3g}'} | {where} |")
    return "\n".join(lines) + "\n"


@dated_report
def report(result: ExclusionResult) -> str:
    """A short report in Markdown: per module and the envelope."""
    lines = [f"# Exclusion limits: {result.interaction_name}", "",
             (f"Card `{result.request.card_id}`, values {result.request.values or 'the defaults'}, "
              if result.request.card_id else "A bespoke interaction (DM8), ")
             + f"splitting {result.request.splitting_kev} keV; {result.created}. Module limits at {100 * result.request.confidence_level:g}% CL.", "",
             "| module | fidelity | route | validated masses (GeV) | strongest validated μ_up (at mass) |",
             "|---|---|---|---|---|"]
    for r in result.per_module:
        ok = [m for m, v in zip(r.masses_gev, r.validated) if v]
        finite = [(u, m) for u, m in zip(r.mu_up, r.masses_gev) if math.isfinite(u)]
        valid = [(u, m) for u, m, v in zip(r.mu_up, r.masses_gev, r.validated)
                 if v and math.isfinite(u)]
        span = f"{min(ok):.3g}–{max(ok):.3g}" if ok else "none"
        strongest = (f"{min(valid)[0]:.3g} ({min(valid)[1]:.3g} GeV)" if valid
                     else "not validated" if finite else "no sensitivity")
        lines.append(f"| {r.experiment} | {r.fidelity} | {r.route} | {span} | {strongest} |")
    if result.skipped:
        lines += ["", "Not run: " + "; ".join(f"{k} ({v})" for k, v in result.skipped.items())]
    if result.flags:
        lines += ["", "Flags: " + "; ".join(result.flags)]
    lines += ["", "The envelope is the strongest validated limit at each mass, not a combination."]
    return "\n".join(lines + _telescope_section(result)) + "\n"


def _telescope_section(result: ExclusionResult) -> list[str]:
    """Tier 2: the neutrino telescopes' limits, with their assumptions, outside the envelope."""
    if not result.telescopes:
        return []
    lines = ["", "## Tier 2: neutrino telescopes, through capture in the Sun", "",
             "Native 90% CL, not in the module envelope: each assumes equilibrium in the Sun and one annihilation channel. These are not converted to 95%.",
             "", "| record | channel | strongest μ_up (at mass) | verified |", "|---|---|---|---|"]
    for t in result.telescopes:
        finite = [(u, m) for u, m in zip(t.mu_up, t.masses_gev) if math.isfinite(u)]
        best = f"{min(finite)[0]:.3g} ({min(finite)[1]:.3g} GeV)" if finite else "no limit"
        lines.append(f"| {t.record_id} | {t.channel} | {best} | {'yes' if t.verified else 'not yet'} |")
    unknown = sorted({t.record_id for t in result.telescopes if t.record_version == ""})
    if unknown:
        lines += ["", f"Which version of {', '.join(unknown)} these limits were computed from is not known: "
                      "the record was read in two versions, or changed before the run ended. Its provenance is not "
                      "certified; run it again."]
    return lines

"""A point over the halo region (``halo_region``): its own evaluation at the region's centre, then its halo-dependent
constraints at every sample, saved with it so that the verdict classifies it without new physics.

**What depends on the halo.** Direct detection (every module's limit at the sample, ``halo_limits``), capture in the
Sun (the model's capture rate at the sample's halo against IceCube's bound on the annihilation rate, which does not
move), and the Galactic-halo searches: γ-ray lines and antiprotons, whose limits on ⟨σv⟩ scale as (ρ_record/ρ₀)²
from the local density each record states (``constraints/data/local_densities.yaml``); the Galactic profile's shape
beyond ρ₀ is not varied. Dwarf galaxies (their own J-factors), the CMB, colliders, the relic density and the theory
certificates do not depend on the local halo.

**Order of work.** Every sample first with the count ratio for the slow modules. A comparison is decided by it only if
it holds with every count-ratio limit at either end of its margin (weakest and strongest, ``State.bias``); otherwise
direct detection is undecided at that sample (``State.fragile``), whichever way the central values point, and no
other comparison's exclusion stands in for it (the audit's PX-01). If the decided samples already differ, the point is halo-sensitive and
nothing more is computed. Otherwise the unresolved samples get the slow modules' full procedure, within the point's
budget (``HaloPreset.full_calculations``). A classification that holds throughout is then checked with the interior
points doubled.

**Not varied (the point's halo coverage stays incomplete):** a structure compared through Path 1 (``operator_limits``)
and a flavour-vector model's own direct-detection limit; these keep their published-halo comparison.

**What it read.** A point over the region or at a benchmark is calculated with the halo data files held (``_reading``:
its run's, else the files as they are as it starts) and saves their identities with its evaluation
(``HaloEvaluation.data``), so that whenever its claim is certified, in its run or from its saved result, the
certificate is bound to the data it was calculated with (the auditor's HB recheck, HC-01, 2026-11-11: a saved point's verdict
taken again had been bound to the data in force then, so a point calculated with one density file was certified
against another).
"""
from __future__ import annotations

import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from adroit.core.halo_choice import FixedHalo
from adroit.parameter_space import dd_channels, halo_limits, halo_region
from adroit.parameter_space.halo_region import HaloEvaluation, HaloOutcome, HaloPointSample, HaloPreset


def _dd(channels, m_dm: float, state: halo_limits.State, light: bool = False) -> tuple[HaloOutcome | None, list[str]]:
    """Direct detection at the state's halo: (its outcome, its pending reasons). Its ratio enters a combination only
    if no limit taken here came from a count ratio (PX-03), with the confidence level and sidedness of the channel
    whose ratio it is, at this halo (``combined_channel``, as at the centre: AL3-07), never the centre's (PX-04) nor
    another channel's (AL5-02: a one-sided SI ratio carried with a two-sided SD band's construction had made a
    pending point excluded). Through a light mediator (``light``) the contact comparison follows
    ``scan.light_mediator_rule``, as at the centre, and no ratio is combined (AL4-01)."""
    if not channels:
        return None, []
    found = dd_channels.compare(channels, m_dm)
    excluded = found.excluded
    if state.fragile:                             # a count ratio within its margin: does it decide at both ends?
        ends = []
        for bias in (1, -1):
            state.bias = bias
            try:
                ends.append(dd_channels.compare(channels, m_dm).excluded)
            finally:
                state.bias = 0
        if ends[0] is True:                       # excluded even with every count-ratio limit at its weakest
            excluded, state.fragile[:] = True, []
        elif ends[1] is False:                    # allowed even at their strongest (straddling there is undecided:
            excluded, state.fragile[:] = (None if found.excluded is True else found.excluded), []   # AL1-11)
        else:
            excluded = None
    ratio = found.combinable                      # never a channel whose prediction is not computable (AL1-01)
    combined = found.combined_channel or found.decisive          # the ratio's construction is its channel's (AL5-02)
    reasons = list(found.pending)
    if light:
        from adroit.parameter_space.scan import light_mediator_rule
        (excluded, reasons), ratio = light_mediator_rule(excluded, reasons), None
    limit = combined.limit if combined is not None else None
    return HaloOutcome(excluded=excluded, ratio=ratio, exact=not state.approximate(),
                       confidence_level=getattr(limit, "confidence_level", None),
                       sidedness=getattr(limit, "sidedness", None), why="; ".join(reasons)), reasons


def _outcome(o) -> HaloOutcome:
    return HaloOutcome(excluded=o.excluded, ratio=o.ratio, why=o.why)


def at(cls, p, sample: tuple[float, float, float, str], channels, ice: bool, unverified: bool,
       budget: halo_limits.Budget, full: bool = False) -> HaloPointSample:
    """The point's halo-dependent constraints at one halo (v₀, v_esc, ρ₀, where)."""
    from adroit.parameter_space import scan, searches
    v0, ve, rho, where = sample
    state = halo_limits.State(v0_km_s=v0, v_esc_km_s=ve, rho_gev_cm3=rho, full=full, defer=True, budget=budget)
    outcomes, pending = {}, []
    with halo_limits.using(state):
        dd, reasons = _dd(channels, searches.dm_mass(cls, p), state, scan._light_mediator(cls, p))
        if dd is not None:
            outcomes["direct detection"], pending = dd, list(reasons)
        if ice:
            o = scan._sun(cls, p, unverified)
            outcomes[o.name] = _outcome(o)
            if o.excluded is None:
                pending.append(f"{o.name}: {o.why}")
        for evaluator in (searches.lines, searches.antiprotons):
            o = evaluator(cls, p, unverified)
            if o is None:
                continue
            o = o.at95()
            outcomes[o.name] = _outcome(o)
            if o.excluded is None:
                pending.append(f"{o.name}: {o.why}")
    missing = [x for x in pending if "): halo: " in x]           # a module with no limit at this halo (budget)
    return HaloPointSample(v0_km_s=v0, v_esc_km_s=ve, rho_gev_cm3=rho, where=where, outcomes=outcomes,
                           pending=list(dict.fromkeys(pending)),
                           unresolved=list(dict.fromkeys(state.fragile + missing)),
                           full_calculations=list(state.spent))


def deciding(result) -> tuple[str, ...]:
    """The experiments whose limits set the point's direct-detection comparisons at the region's centre (each
    channel's limit's ``source``), in order: where a point's budget of full calculations goes first."""
    sources = []
    for channel in getattr(result, "dd_channels", None) or []:
        limit = getattr(channel, "limit", None)
        source = getattr(limit, "source", "") if limit is not None else ""
        if source and source not in sources:
            sources.append(source)
    return tuple(sources)


def recomputed(pending: list[str], model_pending: list[str] | None, channels: bool) -> list[str]:
    """The centre's pending reasons that every sample recomputes, and replaces with its own: those of a halo-dependent
    constraint, but the model's own (``PointResult.model_pending``: what applies and is not computed, which no halo
    computes) and, where the point scatters through no channel the samples compare, direct detection's (the audit
    loop's AL1-04, 2026-11-14: a model's own "direct detection: … not computed" had been taken as recomputed, so over
    the region its point lost the reason, and was viable where it was the only one)."""
    halo = tuple(k for k in halo_region.HALO_CONSTRAINTS if channels or k != "direct detection")
    own = set(model_pending or ())
    return [x for x in pending if x.startswith(halo) and x not in own]


def _halos(samples: list[halo_region.HaloSample]) -> list[tuple[float, float, float, str]]:
    """Each velocity sample at both ends of its density interval."""
    return [(s.v0_km_s, s.v_esc_km_s, rho, s.where) for s in samples for rho in (s.rho_low_gev_cm3, s.rho_high_gev_cm3)]


def _label(cls, result, evaluation: HaloEvaluation) -> str:
    """The region's classification of the point so far (the verdict's own rule, from saved data)."""
    from adroit.parameter_space.verdict import classify
    return classify(cls, result.model_copy(update={"halo": evaluation})).halo


def _resolve(cls, p, evaluation: HaloEvaluation, channels, ice: bool, unverified: bool,
             budget: halo_limits.Budget) -> HaloEvaluation:
    """The unresolved samples again with the slow modules' full procedure (within the budget)."""
    samples = [at(cls, p, (s.v0_km_s, s.v_esc_km_s, s.rho_gev_cm3, s.where), channels, ice, unverified, budget, True)
               if s.unresolved else s for s in evaluation.samples]
    return evaluation.model_copy(update={"samples": samples})


@contextmanager
def _reading() -> Iterator[dict[str, str]]:
    """Inside: the halo data files a point is calculated with, held (``halo_choice.holding``) and given as name: sha256
    ("" missing): those in force (its run's resolution, HB-03), else each file as it is now, read once here."""
    from adroit.core.halo_choice import HALO_DATA, data_identity, holding, in_force
    force = in_force() or {}
    data = {**data_identity(tuple(name for name in HALO_DATA if name not in force)),
            **{name: force[name] for name in HALO_DATA if name in force}}
    with holding({**force, **data}):
        yield data


def _recorded(calculate: Callable) -> Callable:
    """``calculate`` (a point's halo evaluation) inside ``_reading``, its result's evaluation saving what it read, and
    inside ``limit_tables.reading``: each module's inputs read once for the point, at every halo (DY-01)."""
    from adroit.parameter_space import limit_tables

    @functools.wraps(calculate)
    def recorded(*args, **kwargs):
        with _reading() as data, limit_tables.reading():
            result = calculate(*args, **kwargs)
        return result.model_copy(update={"halo": result.halo.model_copy(update={"data": data})})
    return recorded


@_recorded
def evaluate(cls, p, preset: HaloPreset, nominal: Callable, unverified: bool):
    """The point's evaluation at the region's centre (``nominal``, run there) with its halo evaluation."""
    from adroit.parameter_space import scan
    budget = halo_limits.Budget(preset.full_calculations)
    v0, ve, rho = halo_region.centre(preset)
    with halo_limits.using(halo_limits.State(v0_km_s=v0, v_esc_km_s=ve, rho_gev_cm3=rho, budget=budget)) as state:
        result = nominal()
    result = _nominal_cuts(result, state)
    budget.prefer = deciding(result)        # the decisive experiments first at every other halo (2026-11-24)
    kind, sigma = cls.dd(p)
    channels = scan.dd_channels_of(cls, p, kind, sigma)
    unsupported = [] if channels or result.dd_ratio is None else \
        [f"direct detection ({kind}): compared through Path 1, whose limits have no halo variation yet"]
    ice = "capture in the Sun (IceCube)" in result.excluded
    evaluation = HaloEvaluation(region=halo_region.describe(preset), unsupported=unsupported,
                                nominal_pending=recomputed(result.pending, result.model_pending, bool(channels)),
                                samples=[at(cls, p, h, channels, ice, unverified, budget)
                                         for h in _halos(halo_region.samples(preset))])
    label = _label(cls, result, evaluation)
    if label == halo_region.INCOMPLETE and any(s.unresolved for s in evaluation.samples):
        evaluation = _resolve(cls, p, evaluation, channels, ice, unverified, budget)
        label = _label(cls, result, evaluation)
    if label in halo_region.UNIFORM:
        more = [at(cls, p, h, channels, ice, unverified, budget) for h in _halos(halo_region.doubled(preset))]
        evaluation = evaluation.model_copy(update={"samples": evaluation.samples + more})
        if any(s.unresolved for s in more):
            evaluation = _resolve(cls, p, evaluation, channels, ice, unverified, budget)
        evaluation = evaluation.model_copy(update={"converged": _label(cls, result, evaluation) == label})
    return result.model_copy(update={"halo": evaluation.model_copy(update={"full_calculations": list(budget.spent)})})


@_recorded
def at_benchmark(cls, p, fixed: FixedHalo, nominal: Callable):
    """The point calculated at a fixed benchmark (``halo_choice.FixedHalo``; the request's choice, halo phase 1): every
    halo-dependent comparison able to use it is taken at that one halo, inside ``halo_limits.using``, as the region's
    centre is (direct detection: a module whose published halo it is by its own published procedure, the fast modules
    by their procedure there, the slow ones by the validated count ratio or their full procedure within the point's
    budget; capture in the Sun in its halo; the Galactic searches with their own profiles at its density). A comparison
    that cannot use it (a structure compared through Path 1, a flavour-vector model's own limit) is pending, named, and
    decides nothing: its exclusion at the published halos is not taken for one at the benchmark. A count ratio is a cut
    only, as over the region (``_nominal_cuts``). A generated benchmark (SHM++) is taken as its tables: every module by
    its own procedure there (no count ratio; the slow ones within the budget), capture in the Sun with the Sun's
    table (``halo_limits.at_tables``)."""
    from adroit.core.halo_choice import resolve, unsupported
    from adroit.parameter_space import scan
    from adroit.parameter_space.flavour_vector import FlavourVectorClass
    budget = halo_limits.Budget(fixed.full_calculations)
    if fixed.generated:
        state = halo_limits.at_tables(fixed, budget)
    else:
        h = fixed.halo
        if not halo_limits.parameterised(h):
            raise ValueError(f"{fixed.benchmark}: its halo is not one Track 1's direct-detection machinery evaluates "
                             "at (a standard halo with v_LSR = v₀ and the default solar and Earth velocities); nothing "
                             "is calculated")
        state = halo_limits.State(v0_km_s=h.v0_km_s, v_esc_km_s=h.v_esc_km_s, rho_gev_cm3=h.rho_gev_cm3,
                                  budget=budget, benchmark=True)
    with halo_limits.using(state):
        result = nominal()
    result = _nominal_cuts(result, state)
    resolution = resolve(fixed)
    kind, sigma = cls.dd(p)
    reasons = []
    if not scan.dd_channels_of(cls, p, kind, sigma) and result.dd_ratio is not None:
        consumer = "flavour-vector" if isinstance(cls, FlavourVectorClass) else "path1-structure"
        reasons.append(f"direct detection ({kind}): {unsupported(resolution, consumer)}")
        result = _undecided(result, "direct detection")
    evaluation = HaloEvaluation(region=resolution.label, treatment="benchmark", unsupported=reasons,
                                full_calculations=list(budget.spent))
    pending = result.pending + [x for x in reasons if x not in result.pending]
    return result.model_copy(update={"halo": evaluation, "pending": pending})


def _undecided(result, name: str):
    """The evaluation with ``name``'s comparison deciding nothing (left out of the cuts and the combination)."""
    return result.model_copy(update={
        "excluded": {**result.excluded, name: None},
        "ratios": {k: v for k, v in result.ratios.items() if k != name},
        "ratio_confidence_levels": {k: v for k, v in result.ratio_confidence_levels.items() if k != name},
        "ratio_sidedness": {k: v for k, v in result.ratio_sidedness.items() if k != name}})


def _nominal_cuts(result, state: halo_limits.State):
    """The centre's evaluation with a direct-detection ratio kept out of the combined likelihood wherever a limit
    taken there came from a count ratio (a cut only: the owner's condition 6)."""
    if "direct detection" not in result.statistical_limits or not state.approximate():
        return result
    drop = "direct detection"
    return result.model_copy(update={
        "ratios": {k: v for k, v in result.ratios.items() if k != drop},
        "ratio_confidence_levels": {k: v for k, v in result.ratio_confidence_levels.items() if k != drop},
        "ratio_sidedness": {k: v for k, v in result.ratio_sidedness.items() if k != drop}})

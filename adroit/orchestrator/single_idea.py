"""The single-idea report (DM14): one user's model as the explanation of an anomaly.

Track 2 for one idea, and Track 1 centred on the anomaly's best-fit region:
1. **The fit.** The model, at each dark matter mass, is fitted to the
   anomaly's events with every coupling scaled by one strength μ (μ = 1: the
   stated couplings), with the global significance over the masses from
   background-only toys.
2. **The tension** with the null experiments at the best mass (Path 2's
   combination, its parameter-goodness-of-fit).
3. **The best-fit band.** Solve the actual model's NR coefficients for g_chi
   at fixed physical masses and other couplings, on the original-sign
   perturbative branch. Verify the full predicted recoil spectrum and its
   profile likelihood. Unsupported inversions remain pending. Refine thermal
   intersections with the actual relic solver and a new fit at each mass.
4. **Track 1** on a window around the band: the plane, with the band drawn on
   it, the relic contour's verdict and the literature.

A model DM13 cannot compute keeps steps 1 and 2; its parameter space is
undetermined, with the reason.
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
from pydantic import Field, StrictInt, field_validator, model_validator

from adroit.constraints import eos_reads
from adroit.core.certificate import POLICY, Certificate, Check, survives
from adroit.core.chronology import dated_report, timed
from adroit.core.halo_choice import FixedHalo, Resolution
from adroit.parameter_space.assessment import SignalPlane
from adroit.parameter_space.halo_region import HaloPreset
from adroit.constraints.viability import Entry as ViabilityEntry
from adroit.core.constraint_discovery import DiscoveryCoverage
from adroit.core.model_spec import ModelSpec
from adroit.core.dm_state import InteractionModel
from adroit.core.state import StrictModel
from adroit.experiments import registry as modules
from adroit.experiments.base import ExperimentModule
from adroit.inference import nuisance, signal_fit
from adroit.inference.combination import Combination
from adroit.library.interactions import derivation as dv
from adroit.orchestrator import signal as path2
from adroit.orchestrator import track1, user_models
from adroit.orchestrator.track1 import Track1Result
from adroit.parameter_space import plots
from adroit.parameter_space.classify import Unsupported, classify
from adroit.parameter_space.scan import Axis, ModelClass, PointResult
from adroit.parameter_space.classes import Point
from adroit.parameter_space.fit_inversion import invert
from adroit.parameter_space.physical_fit import PhysicalFit, FitSettings, fit as bounded_fit, fixed_prediction
from adroit.core.model_spec import PhysicalFitRange
from adroit.parameter_space.native_joint import JointSettings, JointResult, run as native_joint_run
from adroit.parameter_space.thermal import refine
from adroit.parameter_space.verdict import OMEGA, judge_point

if TYPE_CHECKING:
    from adroit.library.experimental_profiles import Profile

DEFAULT_NULLS = ["CRESST-III 2019", "CDMSlite Run 2", "PICO-60 C3F8 (2019)", "DEAP-3600 (2019)"]


class SingleIdeaRequest(StrictModel):
    """A single-idea study: the anomaly's experiment or record, the model, the masses, the null experiments, the toys
    and the settings of the fit and of Track 1."""
    experiment: str                       # a signal search, or ``record:<path>`` (an anomaly record)
    spec: ModelSpec
    derivation: dv.Derivation | None = None
    masses_gev: list[float] = Field(default_factory=lambda: np.geomspace(5.0, 1000.0, 16).tolist())
    null_modules: list[str] = Field(default_factory=lambda: list(DEFAULT_NULLS))
    toys: int = 20_000
    # a promoted study (DM14): the parent's library-wide global significance, which caps this study's own
    # (release audit minor); left out of the serialised form when absent
    parent_global_z: float | None = Field(default=None, exclude_if=lambda v: v is None)
    grid: int = Field(default=20, ge=4, le=60)
    literature: bool = False                               # arXiv's prior work: a network request, only if asked
    workers: int = Field(default=2, ge=1, le=2)
    unverified_records: bool = False
    physical_fit_settings: FitSettings = Field(default_factory=FitSettings)
    native_joint: JointSettings | None = None
    catalog_reference: str = ''
    experimental_profile: str = ''
    # the propagation model for charged cosmic-ray bounds (``constraints.propagation``); None: the setting, resolved
    # when the study starts. Unset requests keep their earlier identity.
    propagation: str | None = Field(default=None, exclude_if=lambda v: v is None)
    # the halo region of its constraints and its Track 1 plane (``track1.Track1Request.halo``), or a fixed common
    # benchmark (``halo_choice.FixedHalo``), which its fit and null comparisons use too; unset requests keep their
    # identity
    halo: HaloPreset | Literal["published"] | FixedHalo | None = Field(default=None, exclude_if=lambda v: v is None)
    # a frozen constraint-discovery assessment (``track1.Track1Request.discovery``); unset requests keep their identity
    discovery: str = Field(default="", exclude_if=lambda v: not v)

    @field_validator("propagation")
    @classmethod
    def _known_propagation(cls, value: str | None) -> str | None:
        from adroit.constraints.propagation import normalise
        return None if value is None else normalise(value)


class BandPoint(StrictModel):
    """The fit at one mass, and (for a computable model) the band's mediator mass and its verdict."""

    m_chi: float
    s_hat: float
    events_at_unit: float                 # expected events seen inside the window at the stated couplings
    mu_hat: float
    mu_68: tuple[float, float]
    z_local: float
    point: Point | None = None
    physical_fit: PhysicalFit | None = None
    fitted_parameter: str = "g_chi"
    fitted_value: float | None = None
    fitted_68: tuple[float | None, float | None] = (None, None)
    spectrum_relative_error: float | None = None
    delta_log_l_error: float | None = None
    inversion_reason: str = ""
    target: float | None = None
    relative_residual: float | None = None
    converged: bool = False
    m_med: float | None = None
    m_med_68: tuple[float, float] | None = None
    omega_h2: float | None = None
    status: str = ""                      # viable, pending, excluded (DM13's statuses)
    excluded_by: list[str] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)
    evaluation: PointResult | None = None   # same comparisons used by Track 1; legacy optional
    reference_interaction: InteractionModel | None = None  # actual input to the NR reference rate
    # a thermal point's certificate (``certification``; the consolidation plan's M1): absent for fitted points and in
    # older results
    certificate: Certificate | None = Field(default=None, exclude_if=lambda v: v is None)


class SingleIdeaResult(StrictModel):
    """A single-idea study's result: the best-fit band, the global significance, the tension with the null
    experiments, the thermal points, the verdicts and the plane around the band with the signal requirement imposed."""
    request: SingleIdeaRequest
    verified: bool = True
    unsupported: str = ""                 # why the model's parameter space is not computed
    band: list[BandPoint] = Field(default_factory=list)
    best: str = ""
    global_z: float = 0.0
    global_method: str = ""
    global_toys: int | None = Field(default=None, exclude_if=lambda v: v is None)              # absent in older
    global_p_interval: list[float] | None = Field(default=None, exclude_if=lambda v: v is None)  # results
    combination: Combination | None = None
    thermal: list[BandPoint] = Field(default_factory=list)   # where the band meets the relic contour
    thermal_pending: list[str] = Field(default_factory=list)
    # which thermal points the headline rests on, by position (``_rests_on``), and which of each table's points it
    # also rests on (an excluded headline: the points the nominal lacks); None in older results, read as every one
    # (the auditor's CO recheck, CR-04, 2026-10-26); positions, so ``true`` is not one (CS-01)
    rests_on: list[StrictInt] | None = Field(default=None, exclude_if=lambda v: v is None)
    rests_on_tables: dict[str, list[StrictInt]] = Field(default_factory=dict, exclude_if=lambda v: not v)
    # each table's points the nominal lacks that an excluded headline sets aside because their fit is definitively
    # below the anomaly-fit criterion (no explanation, whatever their thermal history), by position (the auditor's CR
    # recheck, CS-04, 2026-10-27); absent where none and in older results
    set_aside_tables: dict[str, list[StrictInt]] = Field(default_factory=dict, exclude_if=lambda v: not v)
    # each equation-of-state table's certified thermal points, refitted at their own masses (``_eos_band``): what the
    # fit quality reads beside the nominal fits (RY23-02); absent in older results and where the band adds none
    eos_thermal: dict[str, list[BandPoint]] = Field(default_factory=dict, exclude_if=lambda v: not v)
    fit_quality: str = ""
    constraint_compatibility: str = ""
    thermal_viability: str = ""
    level: str = ""                       # no_fit, excluded, viable_pending, viable, undetermined
    summary: str = ""
    track1: Track1Result | None = None
    physical_best_mass_gev: float | None = None
    physical_significance_note: str = ""
    native_joint: JointResult | None = None
    plots: list[str] = Field(default_factory=list)
    # the halo as the study resolved it (``halo_choice.resolve``), with the halo data files' identities as read; absent
    # in older results (read from their request when shown)
    halo_resolution: Resolution | None = Field(default=None, exclude_if=lambda v: v is None)
    viability: list[ViabilityEntry] = Field(default_factory=list)   # the 28-item checklist (R8; empty in older results)
    calculation_started_at: str = ""          # UTC, recorded by chronology.timed
    calculation_completed_at: str = ""
    discovery_coverage: DiscoveryCoverage | None = Field(default=None, exclude_if=lambda v: v is None)
    # the plane with the signal requirement imposed (``signal_plane``; the owner's plan of 2026-11-24, section 2): the
    # signal assessment at each grid point and thermal crossing, and each crossing's joint reading; absent in older
    # results, whose plane is a constraint plane only
    signal_plane: SignalPlane | None = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def _support_held(self) -> SingleIdeaResult:
        """The points its headline rests on or sets aside are its own (``core.certificate.held``; the auditor's CR recheck,
        CS-01, 2026-10-27: with ``eos_thermal`` removed and ``rests_on_tables`` kept, an excluded headline had read
        certified): positions inside ``thermal`` and inside each named table's ``eos_thermal``; table points named
        where its own thermal points are not (``rests_on`` absent) are not a result's."""
        from adroit.core.certificate import held
        held("rests_on", self.rests_on or [], len(self.thermal))
        for field in ("rests_on_tables", "set_aside_tables"):
            for table, positions in getattr(self, field).items():
                held(f"{field}.{table}", positions, len(self.eos_thermal.get(table, [])))
        if self.rests_on is None and self.rests_on_tables:
            raise ValueError("rests_on_tables names table points where rests_on names no thermal points")
        return self


def _fit_masses(module, candidates: list[path2.Candidate], toys: int
                ) -> tuple[list[BandPoint], list, float, str, list[float] | None]:
    """The fit at every mass, and the global significance over them."""
    events, sigma = module.observations()
    energies = np.asarray(module.signal_grid_kev(), dtype=float)
    b, rate = module.background_at(events), module.background_rate()
    signals = [path2._signal(module, c) for c in candidates]
    fits = [signal_fit.fit(c.label, signal_fit.event_densities(energies, s.density, events, sigma), b, rate)
            for c, s in zip(candidates, signals)]
    shapes = np.array([np.asarray(s.density) / s.total_events if s.total_events > 0 else np.zeros(energies.size)
                       for s in signals])
    live = shapes.sum(axis=1) > 0
    theta0 = nuisance.null_fit(b, rate)[0] if rate is not None and rate.free else None
    z_max = max(f.z_local for f in fits)
    if live.any():
        p_toys, _, z_global, method = path2._global_significance(module, shapes[live], energies, z_max, toys, theta0)
        interval = path2.toy_record(z_max, p_toys, toys)[1]           # none at 0σ, where no toy is drawn (AL2-21)
    else:
        z_global, method, interval = 0., "not computed: no nonzero NR reference spectrum", None
    band = []
    for c, s, f in zip(candidates, signals, fits):
        unit = signal_fit.seen_events(energies, s.density, sigma)
        mu = math.sqrt(f.s_hat / unit) if unit > 0 else 0.0
        lo, hi = (math.sqrt(x / unit) if unit > 0 else 0.0 for x in f.interval_68)
        band.append(BandPoint(m_chi=c.mass_gev, s_hat=f.s_hat, events_at_unit=unit, mu_hat=mu, mu_68=(lo, hi),
                              z_local=f.z_local, reference_interaction=c.interaction))
    return band, fits, z_global, method, interval


def _candidate(cls: ModelClass, point: Point, spin: float) -> path2.Candidate:
    return path2.Candidate(label=f"physical@{point.m_chi!r}", mass_gev=point.m_chi,
                           interaction=cls.interaction(point), spin=spin)


def _inverse_band(cls: ModelClass, point: Point, b: BandPoint, module: ExperimentModule, spin: float = 0.5,
             unverified: bool = False, assess: bool = True,private_limits=None,private_searches=None) -> BandPoint:
    """Fit a physical coupling, verifying the spectrum and profiled likelihood."""
    base = point.model_copy(update={"m_chi": b.m_chi})
    try:
        p = invert(cls, base, b.mu_hat, _TIES.get())
        reference = path2._signal(module, _candidate(cls, base, spin))
        physical = path2._signal(module, _candidate(cls, p, spin))
        wanted = np.asarray(reference.density) * b.mu_hat ** 2
        error = float(np.max(np.abs(np.asarray(physical.density) - wanted)) /
                      max(float(np.max(np.abs(wanted))), 1e-300))
        if error > 1e-6 or not math.isfinite(error):
            raise ValueError("physical inversion does not reproduce the fitted recoil spectrum")
        energies = np.asarray(module.signal_grid_kev())
        events, sigma = module.observations()
        f0 = signal_fit.event_densities(energies, reference.density, events, sigma)
        fp = signal_fit.event_densities(energies, physical.density, events, sigma)
        target_events = signal_fit.seen_events(energies, reference.density, sigma) * b.mu_hat ** 2
        ll0 = signal_fit.profile_log_likelihood(target_events, f0, module.background_at(events),
                                                module.background_rate())[0]
        llp = signal_fit.profile_log_likelihood(signal_fit.seen_events(energies, physical.density, sigma), fp,
                                                module.background_at(events),
                                                module.background_rate())[0]
        ll_error = abs(float(llp - ll0))
        if not math.isfinite(ll_error) or ll_error > 1e-6:
            raise ValueError("physical inversion does not reproduce the fitted profile likelihood")
        bounds, notes = [], []
        for amplitude in b.mu_68:
            try:
                bounds.append(invert(cls, base, amplitude, _TIES.get()).g_chi)
            except ValueError as error_bound:
                bounds.append(None)
                notes.append(f"68% interval: {error_bound}")
        context={k:v for k,v in [('private_limits',private_limits),('private_searches',private_searches)] if v}
        c = judge_point(cls, p, unverified,**context) if assess else None
        return b.model_copy(update={"point": p, "m_med": p.m_med, "fitted_value": p.g_chi,
                    "fitted_68": tuple(sorted(bounds)) if None not in bounds else tuple(bounds),
                    "spectrum_relative_error": error, "delta_log_l_error": ll_error,
                    "inversion_reason": "; ".join(notes), "omega_h2": c.omega_h2 if c else None,
                    "status": c.status if c else "", "excluded_by": c.excluded_by if c else [],
                    "pending": c.pending if c else [], "evaluation": c.evaluation if c else None})
    except (ValueError, RuntimeError, ArithmeticError) as error:
        return b.model_copy(update={"status": "pending", "inversion_reason": str(error),
                                    "pending": [f"physical fit inversion: {error}"]})


def _on_band(cls: ModelClass, point: Point, b: BandPoint, module: ExperimentModule, spin: float = .5,
             unverified: bool = False, assess: bool = True, fit_range: PhysicalFitRange | None = None,
             fit_settings: FitSettings | None = None,private_limits=None,private_searches=None) -> BandPoint:
    """Keep successful inversion; otherwise maximise the bounded physical likelihood."""
    context={k:v for k,v in [('private_limits',private_limits),('private_searches',private_searches)] if v}
    from adroit.parameter_space.standard_binding import free_coupling
    free = free_coupling(cls)              # an electroweak multiplet has none: evaluated, never fitted (OB-11)
    inverse = _inverse_band(cls,point,b,module,spin,unverified,assess,**context) if fit_range is None and free else None
    if inverse is not None and inverse.point is not None:
        return inverse
    base = point.model_copy(update={"m_chi": b.m_chi})
    fit = (bounded_fit(cls,base,module,spin,fit_range,fit_settings,_TIES.get()) if free
           else fixed_prediction(cls,base,module,spin))
    if fit.log_l is not None and b.events_at_unit>0:
        reference = path2._signal(module,_candidate(cls,base,spin))
        events,resolution = module.observations()
        f0 = signal_fit.event_densities(module.signal_grid_kev(),reference.density,events,resolution)
        fit.reference_log_l = float(signal_fit.profile_log_likelihood(b.s_hat,f0,
            module.background_at(events),module.background_rate())[0])
        fit.delta_log_l_vs_reference = fit.log_l-fit.reference_log_l
    reason = "; ".join(filter(None,[inverse.inversion_reason if inverse else "declared physical fit range",fit.reason]))
    if not fit.resolved or not fit.identifiable or fit.point is None:
        return b.model_copy(update={"physical_fit":fit,"status":"pending","inversion_reason":reason,
            "pending":[f"bounded physical fit: {fit.reason}"],"point":None,"fitted_value":None})
    p = fit.point
    interval = (fit.regions[0].low,fit.regions[0].high) if len(fit.regions)==1 else (None,None)
    updated = {"physical_fit":fit,"point":p,"m_med":p.m_med,"fitted_value":None if fit.fixed else p.g_chi,
               "fitted_68":interval,"inversion_reason":reason,
               "spectrum_relative_error":None,"delta_log_l_error":None}
    try:
        c = judge_point(cls,p,unverified,**context) if assess else None
        updated.update(omega_h2=c.omega_h2 if c else None,status=c.status if c else "",
                       excluded_by=c.excluded_by if c else [],pending=c.pending if c else [],
                       evaluation=c.evaluation if c else None)
    except (ValueError,RuntimeError,ArithmeticError) as error:
        updated.update(status="pending",pending=[f"physical fit constraint evaluation: {error}"])
    return b.model_copy(update=updated)


def best_physical_fit(band: list[BandPoint]) -> BandPoint | None:
    """The band's best physical fit: its point with the largest fit statistic (``_fit_z``), among those whose statistic
    is finite and above 0, below the anomaly-fit criterion included; None where none is (OB-10, 2026-11-19: every mass
    at 0 had named the first mass, whatever its fit; the auditor's MF-09: a resolved fit with q0 = +∞ had been named)."""
    ranked = [(z, b) for b in band if b.point is not None and (z := _usable_z(b)) > 0]
    return max(ranked, key=lambda pair: pair[0], default=(0., None))[1]


def _usable_z(b: BandPoint) -> float:
    """``_fit_z`` where it is finite, else 0: a fit without a finite statistic (``_fit_state`` "no_statistic") or with
    a negative one (where ``_fit_z``'s square root has no value) is not ranked (MF-09)."""
    try:
        z = _fit_z(b)
    except (TypeError, ValueError):
        return 0.
    return z if math.isfinite(z) else 0.


def _fit_z(b: BandPoint) -> float:
    """Fit-quality diagnostic of a resolved physical fit, or the verified inverse."""
    if b.physical_fit is None:
        return b.z_local
    fit = b.physical_fit
    # a bounded fit stuck at the edge of its declared range cannot support a headline (release audit minor)
    return math.sqrt(fit.q0 or 0.) if fit.resolved and fit.identifiable and not fit.at_boundary else 0.


FIT_WORDS = {"eligible": "meets the anomaly-fit criterion", "below": "below the declared anomaly-fit threshold",
             "unresolved": "an unresolved physical fit", "unidentifiable": "an unidentifiable physical fit",
             "edge": "a physical fit at its range's edge", "no_statistic": "no finite fit statistic"}
FIT_LABEL = {"unresolved": "unresolved", "unidentifiable": "unidentifiable", "edge": "at its range's edge",
             "no_statistic": "no finite statistic"}


def _fit_state(b: BandPoint) -> str:
    """Where a point stands against the anomaly-fit criterion (``_fit_z`` ≥ 1), a key of ``FIT_WORDS``: "eligible";
    "below" for a resolved, identifiable fit inside its range with a finite statistic under 1 (√q0 measures the
    improvement over the background alone, not absolute goodness of fit); otherwise why the fit is undecided (the
    re-audit's R18-1, 2026-10-18)."""
    fit = b.physical_fit
    if fit is not None:
        if not fit.resolved:
            return "unresolved"
        if not fit.identifiable:
            return "unidentifiable"
        if fit.at_boundary:
            return "edge"
    z = b.z_local if fit is None else (math.sqrt(max(fit.q0, 0.)) if fit.q0 is not None and math.isfinite(fit.q0)
                                       else math.nan)
    if not math.isfinite(z):
        return "no_statistic"
    return "eligible" if z >= 1 else "below"


def _fit_at(module: ExperimentModule, cls: ModelClass, point: Point, mass: float, spin: float) -> BandPoint:
    """Profile the anomaly again at this exact mass (no interpolated best fit)."""
    c = _candidate(cls, point.model_copy(update={"m_chi": mass}), spin)
    signal = path2._signal(module, c)
    events, sigma = module.observations()
    f = signal_fit.fit(c.label, signal_fit.event_densities(module.signal_grid_kev(), signal.density, events, sigma),
                       module.background_at(events), module.background_rate())
    unit = signal_fit.seen_events(module.signal_grid_kev(), signal.density, sigma)
    return BandPoint(m_chi=mass, s_hat=f.s_hat, events_at_unit=unit, z_local=f.z_local,
                     mu_hat=math.sqrt(f.s_hat / unit) if unit > 0 else 0,
                     mu_68=tuple(math.sqrt(v / unit) if unit > 0 else 0 for v in f.interval_68))


def _thermal(cls: ModelClass, point: Point, band: list[BandPoint], target: float, module: ExperimentModule, spin: float,
             unverified: bool = False, fit_range: PhysicalFitRange | None = None,
             fit_settings: FitSettings | None = None,private_limits=None,private_searches=None) -> tuple[list[BandPoint], list[str]]:
    """Refine adjacent, complete brackets; never bridge a failed fit/relic point."""
    out, pending = [], []
    rows = sorted(band, key=lambda b: b.m_chi)
    def valid(b: BandPoint) -> bool:
        return b.point is not None and b.omega_h2 is not None and math.isfinite(b.omega_h2) and b.omega_h2 >= 0
    if any(not valid(b) for b in rows):
        pending.append("some fitted masses lack a physical inversion or relic calculation")
    for b in rows:
        if valid(b) and abs(b.omega_h2 / target - 1) < 1e-10:
            out.append(b.model_copy(update={"target": target, "relative_residual": abs(b.omega_h2 / target - 1),
                                            "converged": True}))
    for a, b in zip(rows, rows[1:]):
        if not valid(a) or not valid(b) or (a.omega_h2 - target) * (b.omega_h2 - target) >= 0:
            continue
        cache = {}
        def point_at(t: float) -> Point:
            mass = math.exp(math.log(a.m_chi) + t * math.log(b.m_chi / a.m_chi))
            if mass not in cache:
                fit = _fit_at(module, cls, point, mass, spin)
                cache[mass] = _on_band(cls, point, fit, module, spin, unverified, assess=False,
                                       fit_range=fit_range,fit_settings=fit_settings)
            fitted = cache[mass]
            if fitted.point is None:
                raise ValueError(fitted.inversion_reason)
            return fitted.point
        root = refine(point_at, cls.omega_h2, target)
        if not root.converged:
            pending.append(f"{a.m_chi:g}–{b.m_chi:g} GeV thermal bracket: {root.reason}")
            continue
        context={k:v for k,v in [('private_limits',private_limits),('private_searches',private_searches)] if v}
        fitted = _on_band(cls, point, cache[root.point.m_chi], module, spin, unverified,
                           fit_range=fit_range,fit_settings=fit_settings,**context)
        error = abs(fitted.omega_h2 / target - 1) if fitted.omega_h2 is not None else math.inf
        if not math.isfinite(error) or error > 0.01:
            pending.append("refined thermal density changed during the constraint evaluation")
            continue
        out.append(fitted.model_copy(update={"target": target, "relative_residual": error, "converged": True}))
    return out, pending


def _eos_band(cls: ModelClass, point: Point, band: list[BandPoint], thermal: list[BandPoint], target: float,
              module: ExperimentModule, spin: float, unverified: bool = False, qualified=None, discovery: bool = False,
              **extra) -> tuple[list[BandPoint], list[tuple[str, str, str]], list[str], dict[str, list[BandPoint]],
                                dict[str, list[int]], dict[str, list[int]]]:
    """The owner's decision #3 (2026-10-20) on the fitted band, as on the plane (``verdict._eos_band`` and
    ``_eos_new_roots``; C21-07, 2026-10-21: the single-idea headline had read the nominal equation of state alone).
    With each of Saikawa & Shirai's tables (``verdict.EOS_VARIANTS``, ``relic.eos_variant``) the band's Ωh² is
    computed again and its thermal points refound and judged inside the table (``_thermal``). A decided nominal point
    (viable or excluded) stands where both tables give a point of the same status between the same fitted masses;
    otherwise it is pending, EOS-sensitive, with the three statuses. A table's point supports a viable nominal one only
    where it also fits the anomaly (``_fit_state`` eligible: the recheck's RC21-03, 2026-10-22); an excluded nominal
    one stands where the table's point is excluded and fits, or definitively fails the fit ("below"); an unresolved,
    unidentifiable or range-edge fit decides nothing either way (the re-audit's RR22-03: an excluded point whose fit
    sat at its range's edge had kept an exclusion, though an explanation beyond the edge was neither found nor
    excluded). Returns (the thermal points; (what and where, its status, its
    fit state) for each point a table has between fitted masses where the nominal has none; each table's unresolved
    brackets, "the <table> table: <reason>", RC21-04; each table's certified points; and where, among those, the
    points the nominal lacks are, by table: those whose fit is not definitively poor, which an excluded headline also
    rests on, CR-04; and those whose fit is, which it sets aside by their fit: the auditor's CR recheck, CS-04, 2026-10-27,
    such a point had been among the claims an exclusion rests on, so its own open thermal history had un-certified an
    exclusion that its fit alone decides, as the nominal points' rule, ``_accepted``, already had it).

    Each table's point is qualified by the discovery assessment (``qualified``) and certified at its own parameters
    (``_table_certified``: its thermal history, finite comparisons, records and discovery) before it supports or adds
    anything, and the nominal points arrive already qualified (the auditor's consolidation audit, CO-02 and CO-01,
    2026-10-25: a table's point waiting on discovery had supported a certified nominal one, which the plane leaves
    pending); a supporting table point's unverified records become the nominal claim's (CO-03)."""
    from adroit.constraints import relic
    from adroit.core.certificate import EOS_NOT_ASSESSED, eos_band_assessed
    from adroit.parameter_space.verdict import EOS_VARIANTS, _eos_missing
    if not eos_band_assessed():            # the nominal policy (the owner, 2026-11-23): no band, no table points
        return [_with_eos(t, t, "not_applicable", EOS_NOT_ASSESSED) for t in thermal], [], [], {}, {}, {}
    if missing := _eos_missing():          # the tables not fetched (PR23-05): a decided point waits for the band
        return [_with_eos(t.model_copy(update={"status": "pending", "excluded_by": [], "pending": t.pending + [missing]}),
                          t, "unknown", missing) if t.status in ("viable", "excluded") and _certified(t)
                else _with_eos(t, t, "unknown", missing) for t in thermal], [], [missing], {}, {}, {}
    masses = sorted(b.m_chi for b in band)

    def cell(m: float) -> int:
        """Between which fitted masses a thermal point lies (an exact fitted mass is its own)."""
        return sum(x < m for x in masses) * 2 - (1 if m not in masses else 0)

    def omega(p: Point) -> float | None:
        """Ωh² at a fitted point as the band has it (None outside the model's domain or where it fails)."""
        try:
            return None if hasattr(cls, "domain") and cls.domain(p) else cls.omega_h2(p)
        except (ValueError, RuntimeError, ArithmeticError):
            return None
    found: dict[str, dict[int, BandPoint]] = {}
    unresolved: dict[str, list[str]] = {}
    for name in EOS_VARIANTS:
        with relic.eos_variant(name):
            shifted = [b.model_copy(update={"omega_h2": omega(b.point)}) if b.point is not None else b for b in band]
            rows, pending = _thermal(cls, point, shifted, target, module, spin, unverified, **extra)
        rows = _table_certified(rows, qualified, unverified, discovery, name)
        found[name] = {cell(r.m_chi): r for r in rows if _certified(r)}
        unresolved[name] = pending
    out = []
    for t in thermal:
        if t.status not in ("viable", "excluded") or not _certified(t):
            out.append(_with_eos(t, t, "unknown", "not computed: the point is undecided by its constraints"
                                 if _certified(t) else "not computed: not a certified thermal point"))
            continue
        others = {name: rows.get(cell(t.m_chi)) for name, rows in found.items()}
        if all(_supports(t, o) for o in others.values()):
            out.append(_with_eos(t, t, "satisfied", f"{t.status} also at the thermal points with Saikawa & Shirai's "
                                                    "upper and lower tables, which fit the anomaly",
                                 *_evidence(others.values())))
            continue
        where = ", ".join(f"{o.status} at the point with the {name} table (m_χ = {o.m_chi:.4g} GeV; its fit "
                          f"{FIT_WORDS[_fit_state(o)]}" + (f"; {o.certificate.open_reasons()[0]}" if o.status == "pending"
                                                          and o.certificate is not None and not o.certificate.decided
                                                          else "") + ")" if o is not None
                          else f"no thermal point with the {name} table between these fitted masses"
                               + (f" ({unresolved[name][0]})" if unresolved[name] else "")
                          for name, o in others.items())
        reason = f"EOS-sensitive: {t.status} at the nominal point (m_χ = {t.m_chi:.4g} GeV), {where}"
        state = "failed" if all(o is not None and (o.status in ("viable", "excluded") or _open_failed(o))
                                for o in others.values()) else "unknown"
        out.append(_with_eos(t.model_copy(update={"status": "pending", "excluded_by": [], "pending": t.pending + [reason]}),
                             t, state, reason, *_evidence(others.values())))      # the points its reason names (CT-03)
    # the cells a nominal point can speak for: one whose fit meets the criterion (the re-audit's RV22-02, 2026-10-22:
    # a nominal point below the criterion or at its fit's range edge, which the headline sets aside, had hidden the
    # tables' fitting, surviving points between the same fitted masses, leaving the headline "no thermal")
    nominal = {cell(t.m_chi) for t in thermal if _certified(t) and _fit_state(t) == "eligible"}
    added = [(f"the {name} table has a thermal point at m_χ = {r.m_chi:.4g} GeV ({r.status}; its fit "
              f"{FIT_WORDS[_fit_state(r)]}) where the nominal has none that fits", r.status, _fit_state(r))
             for name, rows in found.items() for c, r in rows.items() if c not in nominal]
    def lacked(poor: bool) -> dict[str, list[int]]:
        """By table, the positions of its points the nominal lacks whose fit is (not) definitively poor."""
        at = {name: [i for i, (c, r) in enumerate(rows.items()) if c not in nominal and (_fit_state(r) == "below") == poor]
              for name, rows in found.items()}
        return {name: i for name, i in at.items() if i}
    return out, added, [f"the {name} table: {reason}" for name, reasons in unresolved.items() for reason in reasons], \
        {name: list(rows.values()) for name, rows in found.items() if rows}, lacked(False), lacked(True)


def _evidence(points) -> tuple[list[str], dict[str, str]]:
    """The records the tables' points (None where a table has none) used: the unverified ones (CO-03), and every one
    with the version used (CS-02, CT-01), which a claim resting on them, or pending because of them, depends on and is
    bound to (the auditor's CS recheck, CT-03, 2026-10-28: a failed band had dropped the record that made it fail)."""
    from adroit.parameter_space.certification import versions_used
    held = [o.certificate for o in points if o is not None and o.certificate is not None]
    return (sorted({r for c in held for r in c.bound.unverified_records}),
            versions_used(*(c.bound.records for c in held)))


def _open_failed(o: BandPoint) -> bool:
    """Whether a table's point is pending because a prerequisite was shown not to hold (its thermal history), nothing
    being merely unknown (``verdict._variant_open``)."""
    states = [x.state for x in o.certificate.checks] if o.certificate is not None else []
    return o.status == "pending" and "failed" in states and "unknown" not in states


def _discovery_added(raw: list[BandPoint], qualified: list[BandPoint]) -> dict[float, list[str]]:
    """What the discovery qualification added to each point's pending reasons, by mass."""
    was = {b.m_chi: b.pending for b in raw}
    return {b.m_chi: [p for p in b.pending if p not in was.get(b.m_chi, [])] for b in qualified}


def _table_certified(rows: list[BandPoint], qualified, unverified: bool, discovery: bool,
                     name: str) -> list[BandPoint]:
    """A table's thermal points, each qualified by discovery (``qualified``) and certified as a thermal solution at its
    own parameters (``_complete``): its refined root, then its thermal history, finite comparisons, records and
    discovery from its own evaluation; the band across the tables is the nominal point's claim, not its own."""
    rows = [r.model_copy(update={"certificate": Certificate(
        claim_kind="thermal_solution", scope=f"the {name} table's thermal point at m_χ = {r.m_chi:.4g} GeV",
        checks=[Check(name="root", state="satisfied" if _certified(r) else "unknown",
                      reason="refined between fitted masses inside the table; its own Ωh² within 1% of the target"
                      if _certified(r) else "not a converged thermal point within 1% of its target"),
                Check(name="eos_band", state="not_applicable",
                      reason="a table's own point: the band across the tables is the nominal point's claim")],
        computed_status=r.status, policy=POLICY)}) for r in rows]
    after = qualified(rows) if qualified is not None else rows
    return _complete(after, _discovery_added(rows, after), unverified, discovery, eos=(name,))


def _with_eos(t: BandPoint, nominal: BandPoint, state: str, reason: str, records: list[str] | tuple = (),
              evidence: dict[str, str] | None = None) -> BandPoint:
    """A thermal point with the start of its certificate (M1): its refined root and the equation of state's band (with
    the unverified records the table points it rests on used, CO-03, and every record they used with its version,
    CS-02 and CT-01, whether the band holds or not, CT-03), the status its computed constraints gave before the band
    (``nominal``); ``_study`` completes it."""
    root = Check(name="root", state="satisfied" if _certified(nominal) else "unknown",
                 reason="refined between fitted masses; its own Ωh² within 1% of the target when judged"
                 if _certified(nominal) else "not a converged thermal point within 1% of its target")
    return t.model_copy(update={"certificate": Certificate(
        claim_kind="thermal_solution", scope=f"the thermal point at m_χ = {t.m_chi:.4g} GeV",
        checks=[root, Check(name="eos_band", state=state, reason=reason, records=list(records),
                            evidence_records=dict(evidence or {}))],
        computed_status=nominal.status,
        computed_excluded_by=list(nominal.excluded_by) if nominal.status != t.status else [], policy=POLICY)})


def _complete(thermal: list[BandPoint], discovered: dict[float, list[str]], enabled: bool,
              discovery: bool, eos: tuple[str, ...] | None = None) -> list[BandPoint]:
    """Each thermal point's certificate completed (``certification.certify``): the checks every point claim needs, and
    the discovery check from what the discovery qualification added to it (``discovered``, by mass:
    ``_discovery_added``); bound to the equation-of-state tables it was decided with (the auditor's CO recheck, CR-01,
    2026-10-26): a nominal point's band to every table, a table's own point (``eos``) to that table."""
    from adroit.parameter_space import certification
    out = []
    for t in thermal:
        if t.certificate is None:
            out.append(t)
            continue
        added = discovered.get(t.m_chi, [])
        found = (Check(name="discovery", state="not_applicable", reason="no discovery assessment in force")
                 if not discovery else Check(name="discovery", state="unknown", reason=added[0]) if added
                 else Check(name="discovery", state="satisfied"))
        prior = t.certificate
        out.append(certification.certify(
            t.model_copy(update={"certificate": None}), prior.claim_kind, prior.scope, prior.checks[:2],
            enabled=enabled, discovery=found, computed=(prior.computed_status, prior.computed_excluded_by
                                                        or (list(t.excluded_by) if t.status == prior.computed_status
                                                            else [])), eos=eos))
    return out


def _supports(t: BandPoint, o: BandPoint | None) -> bool:
    """Whether a table's thermal point ``o`` keeps the nominal point ``t``'s decided status (``_eos_band``)."""
    if o is None:
        return False
    fit = _fit_state(o)
    if t.status == "viable":
        return o.status == "viable" and fit == "eligible"
    return o.status == "excluded" and fit == "eligible" or fit == "below"


def _eos_level(level: str, text: str, added: list[tuple[str, str, str]], unresolved: list[str]) -> tuple[str, str]:
    """The headline with what the tables add (``_eos_band``), as the plane's rule: a verdict without a thermal point is
    undetermined, EOS-sensitive, with a table's point that may fit the anomaly (any fit but a definitively poor one);
    so is an all-excluded one where such a point is viable or pending, or excluded with a fit that decides nothing
    (unresolved, unidentifiable, at its range's edge: RR22-03); and either is undetermined while a table's bracket is
    unresolved, which could hold a viable explanation (the recheck's RC21-04, 2026-10-22). A viable headline is not
    changed by them (one viable point suffices). A "no fit" headline is undetermined with a table's point whose own
    fit is not definitively poor (RX22-04): the fits it rests on are then not all the study made."""
    open_ = _eos_open(level, added)
    if level in ("no_thermal", "excluded") and (open_ or unresolved) or level == "no_fit" and open_:
        return "undetermined", "EOS-sensitive: " + "; ".join(open_ + (unresolved if level != "no_fit" else [])) \
            + f" (nominally: {text})"
    return level, text


def _eos_open(level: str, added: list[tuple[str, str, str]]) -> list[str]:
    """The tables' added points (``_eos_band``) that leave a headline ``level`` without a thermal point, or
    all-excluded, open (``_eos_level``)."""
    return [t for t, status, fit in added if fit != "below"
            and (level in ("no_thermal", "no_fit") or status != "excluded" or fit != "eligible")]


def _compatibility(points: list[BandPoint]) -> str:
    statuses = {b.status for b in points}
    return "viable" if "viable" in statuses else "pending" if "pending" in statuses else "excluded" if points else "undetermined"


def _fits(band: list[BandPoint], thermal: list[BandPoint]) -> list[BandPoint]:
    """Every fit the study evaluated that can speak for the model's fit: the fitted band's and the certified thermal
    points', each refitted at its own mass (the RV22 audit's RX22-04, 2026-10-22: the headline had said "no fit" from
    the coarse band alone, a thermal point between its masses refitted to Z = 2 notwithstanding)."""
    return [*band, *(t for t in thermal if _certified(t))]


def _edge_z(b: BandPoint) -> float:
    """√q0 of a bounded fit held at its range's edge; nan without a finite statistic."""
    q0 = b.physical_fit.q0
    return math.sqrt(max(q0, 0.)) if q0 is not None and math.isfinite(q0) else math.nan


def _fit_verdict(fits: list[BandPoint]) -> tuple[str, str]:
    """("fits", "no_fit" or "undetermined"; why) over the fits given, each by its state (``_fit_state``): one that
    meets the anomaly-fit criterion fits; "no fit" only where every one is definitively below it, a bounded fit held
    at its range's edge counting so only with √q0 < 1 there (the release audit's rule); else undetermined, and why.
    The headline (``_level``) and the saved fit quality (``_fit_quality``) both read it (the RX22 audit's RY23-03,
    2026-10-23: a fit without a finite statistic had read as Z < 1, a definitive "no fit")."""
    states = [(b, _fit_state(b)) for b in fits]
    if any(state == "eligible" for _, state in states):
        return "fits", ""
    if any(state == "edge" and _edge_z(b) >= 1 for b, state in states):
        return "undetermined", "the bounded physical fit sits at the edge of its declared range"
    if any(state in ("unresolved", "unidentifiable") for _, state in states):
        return "undetermined", "bounded physical fit coverage remains unresolved"
    missing = [b for b, state in states if state == "no_statistic" or state == "edge" and not math.isfinite(_edge_z(b))]
    if missing:
        return "undetermined", (f"the fit at m_χ = {missing[0].m_chi:.4g} GeV has no finite statistic"
                                + (f" ({len(missing)} such fits)" if len(missing) > 1 else "")
                                + ": whether the model fits the events is not established")
    return "no_fit", "the model fits the events no better than the background alone (local Z < 1 at every mass)"


def _level(band: list[BandPoint], thermal: list[BandPoint], computed: bool,
           unresolved: list[str] | None = None, unverified: bool = False) -> tuple[str, str]:
    fit, why = _fit_verdict(_fits(band, thermal))
    if fit != "fits":
        return fit, why
    if not computed:
        return "undetermined", "the fit is reported; the model's parameter space is not computed"
    accepted = _accepted(thermal)
    statuses = {b.status for b in accepted}
    if "viable" in statuses:
        return "viable", "a certified thermal intersection fits the anomaly and survives applicable constraints"
    if any(b.status == "pending" and survives(b.status, b.certificate) for b in accepted):
        return "viable_pending", "a certified thermal intersection fits the anomaly; constraints remain pending"
    if "pending" in statuses:                 # every waiting one excluded by its computed constraints (D-2)
        return "undetermined", ("every thermal intersection that fits the anomaly is excluded by its computed "
                                "constraints, but their certification is not complete")
    if unresolved:
        return "undetermined", "thermal intersections or physical fits remain unresolved; completed samples do not establish viability"
    if undecided := _undecided_thermal(thermal):
        return "undetermined", undecided[0]
    from adroit.parameter_space.verdict import relic_validity_reason
    if invalid := relic_validity_reason([b.evaluation for b in [*band, *thermal] if b.evaluation is not None]):
        return "undetermined", f"the relic density does not decide (the external audit's R17-4): {invalid}"
    if accepted:
        return "excluded", "every resolved thermal intersection that fits the anomaly is excluded at this scan resolution"
    from adroit.parameter_space.certification import relic_target
    waits, rests = relic_target(unverified)            # AL2-06: the relic target's record, as a thermal claim's
    if waits:
        return "undetermined", waits
    return "no_thermal", ("no thermal intersection fitting the anomaly was resolved over the searched masses; features "
                          "between samples are not ruled out"
                          + (f"; this conclusion depends on unverified records: {', '.join(rests)}" if rests else ""))


def _across_disagreement(cls: ModelClass, point: Point, band: list[BandPoint], thermal: list[BandPoint],
                         nominal: tuple[str, str], target: float, thermal_at,
                         unresolved: list[str] | tuple = ()) -> tuple[str, str]:
    """D35 (``verdict._robust``'s rule, the external audit's item 17 and its interval rule R17-2): where a generic
    model's thermal points or the fitted masses a shifted target reaches (``_reaching``; the re-audit's R18-4), or
    else its fitted points, are in a regime of O(1) disagreement with the literature, the summary says so, and a
    decisive level stands only if the evaluated band supports it at every relic target in the interval
    (``_band_across``; ``thermal_at(target)`` gives the thermal points and unresolved brackets there, ``unresolved``
    the nominal search's); otherwise it is undetermined."""
    from adroit.parameter_space.portals.generic import GenericModel
    from adroit.parameter_space.portals import generic_regimes as gr
    level, text = nominal
    if not isinstance(cls, GenericModel):
        return nominal
    low, high = (target * s for s in gr.TARGET_SCALES)
    nominal_points = [b.point for b in thermal if b.point is not None]
    points = (nominal_points + [b.point for b in _reaching(band, low, high)] if nominal_points
              else [b.point for b in band if b.point is not None])
    found: list[str] = []
    for p in points:
        try:
            here = gr.regimes(cls, p)
        except (ValueError, RuntimeError, ArithmeticError) as error:      # unknown counts as inside (conservative)
            here = [f"the regime check failed at m_χ = {p.m_chi:.4g} GeV: {error}"]
        found += [f for f in here if f not in found]
    if not found:
        return nominal
    note = f"{gr.QUALIFICATION} ({'; '.join(found)})"
    if level not in ("viable", "viable_pending", "excluded", "no_thermal"):
        return level, f"{text}; {note}"
    span = f"Ωh² = {low:.3g}–{high:.3g}"
    held, why = _band_across(level, band, thermal, low, high, thermal_at, unresolved)
    if held:
        return level, f"{text}; {level} on the evaluated band across the disagreement ({span}), at its resolution: {why}; {note}"
    return "undetermined", f"{level} at the relic target; not established across the O(1) disagreement ({span}): {why}; {note}"


def _certified(b: BandPoint) -> bool:
    """A converged thermal point with Ωh² within 1% of its target."""
    return (b.converged and b.relative_residual is not None and b.relative_residual <= .01 and b.omega_h2 is not None
            and math.isfinite(b.omega_h2))


def _eligible(b: BandPoint) -> bool:
    """Whether a point's fit meets the anomaly-fit criterion by its state (``_fit_state``), never by a bare √q0 or Z
    (the RY23 audit's RZ23-01, 2026-10-23: an infinite statistic passed ``_fit_z ≥ 1``)."""
    return _fit_state(b) == "eligible"


def _undecided(b: BandPoint) -> bool:
    """Whether a point's fit is neither eligible nor definitively below the criterion (``_fit_verdict``'s rule)."""
    state = _fit_state(b)
    return state in ("unresolved", "unidentifiable", "no_statistic") or state == "edge" and not _edge_z(b) < 1


def _undecided_thermal(thermal: list[BandPoint]) -> list[str]:
    """Why each certified thermal point's fit is not established (``_undecided``), to be saved and to keep a headline
    without an eligible viable point undetermined (RZ23-01)."""
    return [f"the thermal point at m_χ = {b.m_chi:.4g} GeV has {FIT_WORDS[_fit_state(b)]}: whether it fits the "
            "anomaly is not established" for b in thermal if _certified(b) and _undecided(b)]


def _waiting(thermal: list[BandPoint], level: str) -> list[str]:
    """Why each certified thermal point a headline short of "viable" could rest on waits, from its certificate (its
    open checks: the tables' band, discovery, a table point's own prerequisite), saved with the headline so that
    the headline, the certificates and the saved reasons read one support set (the auditor's consolidation audit, CO-02,
    2026-10-25: a table point waiting on discovery was in the result but not among its pending reasons)."""
    if level == "viable":
        return []
    out = []
    for t in thermal:
        if t.status != "pending" or not _certified(t) or t.certificate is None or t.certificate.decided:
            continue
        reason = f"the thermal point at m_χ = {t.m_chi:.4g} GeV: {'; '.join(t.certificate.open_reasons())}"
        if reason not in out:
            out.append(reason)
    return out


def _rests_on(thermal: list[BandPoint], level: str) -> list[int]:
    """Which thermal points a headline rests on, by position, saved with it so that the history assesses exactly
    those (the auditor's CO recheck, CR-04, 2026-10-26: a certified viable witness beside an unrelated waiting point had
    read "not certified"): a viable headline on its viable points, a viable-pending one on those waiting that
    survive their computed constraints, an excluded one on every point it decided on (``_accepted``; with the
    tables' points the nominal lacks, ``rests_on_tables``); any other on every thermal point."""
    accepted = _accepted(thermal)
    chosen = ([b for b in accepted if b.status == "viable"] if level == "viable" else
              [b for b in accepted if b.status == "pending" and survives(b.status, b.certificate)]
              if level == "viable_pending" else accepted if level == "excluded" else thermal)
    return [i for i, t in enumerate(thermal) if any(t is b for b in chosen)]


def _accepted(thermal: list[BandPoint]) -> list[BandPoint]:
    """The thermal points ``_level`` decides on: converged, fitting the anomaly, Ωh² within 1% of the target."""
    return [b for b in thermal if _certified(b) and _eligible(b)]


def _reaching(band: list[BandPoint], low: float, high: float) -> list[BandPoint]:
    """The fitted masses a thermal solution at a shifted target in [low, high] can come from, on the evaluated band
    (the re-audit's R18-4): those with Ωh² inside the interval and both neighbours of every pair whose Ωh² range
    overlaps it."""
    rows = sorted((b for b in band if b.point is not None and b.omega_h2 is not None and math.isfinite(b.omega_h2)),
                  key=lambda b: b.m_chi)
    keep = {i for i, b in enumerate(rows) if low <= b.omega_h2 <= high}
    for i, (a, b) in enumerate(zip(rows, rows[1:])):
        if min(a.omega_h2, b.omega_h2) <= high and max(a.omega_h2, b.omega_h2) >= low:
            keep |= {i, i + 1}
    return [b for i, b in enumerate(rows) if i in keep]


def _band_across(level: str, band: list[BandPoint], thermal: list[BandPoint], low: float, high: float,
                 thermal_at, unresolved: list[str] | tuple = ()) -> tuple[bool, str]:
    """``verdict._across`` on the fitted band (R17-2): every fitted mass computed and the nominal thermal search
    complete (``unresolved`` empty; R18-2); for no thermal intersection, every Ωh² beyond the interval on one side;
    otherwise Ωh² spanning the interval, a fitted mass inside the band and thermal points resolved at both ends, and
    then every point evaluated in the band judged (``_judged_band``)."""
    valid = [b for b in band if b.point is not None and b.omega_h2 is not None and math.isfinite(b.omega_h2)
             and b.omega_h2 >= 0]
    gaps = [f"{len(band) - len(valid)} fitted masses lack a physical inversion or relic calculation"] if len(valid) < len(band) else []
    gaps += [f"at the relic target: {u}" for u in unresolved]
    values = [b.omega_h2 for b in valid]
    if level == "no_thermal":
        if not gaps and values and (min(values) > high or max(values) < low):
            return True, f"every fitted mass's Ωh² is {'above' if min(values) > high else 'below'} the interval"
        return False, gaps[0] if gaps else "some fitted mass's Ωh² reaches the interval"
    inside = [b for b in valid if low <= b.omega_h2 <= high]
    if not values or min(values) > low or max(values) < high:
        gaps.append("the fitted masses' Ωh² does not span the interval, so part of it has no thermal solution on the band")
    elif not inside:
        gaps.append("no fitted mass lies inside the band")
    ends: list[BandPoint] = []
    for t in () if gaps else (low, high):
        found, pending = thermal_at(t)
        gaps += [f"at Ωh² = {t:.3g}: {u}" for u in pending]
        gaps += [f"an uncertified thermal point at m_χ = {b.m_chi:.4g} GeV (Ωh² = {t:.3g})" for b in found
                 if not _certified(b)]
        if not found:
            gaps.append(f"no thermal point resolved at Ωh² = {t:.3g}")
        ends += found
    if gaps:
        return False, gaps[0] + (f" (and {len(gaps) - 1} more)" if len(gaps) > 1 else "")
    return _judged_band(level, inside, ends, thermal)


def _judged_band(level: str, inside: list[BandPoint], ends: list[BandPoint],
                 thermal: list[BandPoint]) -> tuple[bool, str]:
    """Every point evaluated in the band (each fitted mass inside it, every thermal point at its ends, every nominal
    one, refined roots as well as sampled masses) judged by its fit (``_fit_state``) before its status (R18-1): for
    viability each must meet the anomaly-fit criterion and have the level's status (``verdict.ROBUST``); for an
    exclusion an undecided fit blocks, a fit below the declared threshold is no explanation and is listed apart, and
    every remaining point must be excluded, of which there must be one."""
    from collections import Counter
    from adroit.parameter_space.verdict import ROBUST, ROBUST_WORD
    points = inside + ends + list(thermal)
    states = [(b, _fit_state(b)) for b in points]
    below = [b for b, s in states if s == "below"]
    blocked = [(b, s) for b, s in states if s != "eligible" and (s != "below" or level != "excluded")]
    if blocked:
        b, s = blocked[0]
        return False, (f"{len(blocked)} of the {len(points)} points evaluated in the band do not meet the anomaly-fit "
                       f"criterion, e.g. {FIT_WORDS[s]} at m_χ = {b.m_chi:.4g} GeV")
    eligible = [b for b, s in states if s == "eligible"]
    if not eligible:
        return False, ("no point evaluated in the band meets the anomaly-fit criterion, so there is no explanation "
                       f"to judge ({len(below)} below the declared anomaly-fit threshold)")
    wrong = [b for b in eligible if b.status not in ROBUST[level]]
    if wrong:
        tally = ", ".join(f"{n} {s}" for s, n in Counter(b.status or "unevaluated" for b in wrong).items())
        return False, (f"{tally} of the {len(eligible)} points evaluated in the band, e.g. "
                       f"{wrong[0].status or 'unevaluated'} at m_χ = {wrong[0].m_chi:.4g} GeV")
    text = (f"the {sum(_fit_state(b) == 'eligible' for b in inside)} fitted masses in the band, the "
            f"{sum(_fit_state(b) == 'eligible' for b in ends)} thermal points at its ends and the nominal ones "
            f"meeting the anomaly-fit criterion are all {ROBUST_WORD[level]}")
    if below:
        text += (f"; {len(below)} below the declared anomaly-fit threshold, not explanations, apart (m_χ = "
                 f"{', '.join(f'{b.m_chi:.4g}' for b in below)} GeV)")
    return True, text


def _window(band: list[BandPoint], n: int, bounds: PhysicalFitRange | None = None) -> tuple[Axis, Axis]:
    """Keep fixed masses; display the physical g_chi branch around the band."""
    values = [b.fitted_value for b in band if b.fitted_value is not None]
    lo, hi = min(values), max(values)
    positive = lo > 0
    if lo == 0:
        lo, hi = 0, min(math.sqrt(4 * math.pi), max(.01, hi * 10))
    elif positive:
        lo, hi = max(1e-12, lo / 10), min(math.sqrt(4 * math.pi), hi * 10)
    else:
        lo, hi = max(-math.sqrt(4 * math.pi), lo - max(abs(lo), 0.01)), min(0, hi / 10)
    if bounds is not None:
        lo, hi = max(lo,bounds.low), min(hi,bounds.high)
        if lo >= hi:
            lo, hi = bounds.low,bounds.high
        positive = lo > 0
    masses = [b.m_chi for b in band]
    mlo, mhi = min(masses), max(masses)
    if mlo == mhi:
        mlo, mhi = mlo / 1.1, mhi * 1.1
    return Axis(parameter="g_chi", low=lo, high=hi, log=positive, n=n), Axis(parameter="m_chi", low=mlo, high=mhi, n=n)


def prepared(request: SingleIdeaRequest) -> SingleIdeaRequest:
    """The request a single-idea study calculates and saves: its experimental profile applied, its propagation model
    and its halo resolved from their declared defaults. Its writer captures this request (``capture_request``) before
    the calculation, so that resolving a default is not read as the request changed during the run (the auditor's DF
    recheck, DG-04, 2026-11-06: a promotion's child had captured its request before its halo and propagation were
    resolved, and its evidence and its bundle were downgraded to "changed during the run")."""
    from adroit.constraints import propagation
    from adroit.parameter_space import halo_region
    if request.experimental_profile:
        from adroit.library.experimental_profiles import apply_signal
        request = apply_signal(request)
    return halo_region.resolved(propagation.resolved(request))


# the couplings the study's model ties to g_chi by a shared symbol (``classify.coupling_relations``), for its fits
_TIES: ContextVar[tuple] = ContextVar("adroit_single_idea_ties", default=())


@contextmanager
def _ties_of(spec):
    """Inside: the model's ties in force for the fits (AL3-03: a model with one coupling symbol had been fitted in g_chi
    alone and drawn on the plane that keeps them tied); none where its couplings cannot be tied linearly."""
    from adroit.parameter_space.classify import Unsupported, coupling_relations
    try:
        ties = tuple(coupling_relations(spec)) if spec is not None else ()
    except Unsupported:
        ties = ()
    token = _TIES.set(ties)
    try:
        yield ties
    finally:
        _TIES.reset(token)


@timed
def run(request: SingleIdeaRequest, folder: Path, fetch=None, *, claim=None) -> SingleIdeaResult:
    """The whole single-idea study, with its propagation model resolved and in force; plots go into ``folder``, held by
    its writer (``claim``, taken here where none is given) from before its first file (``track1.run``'s; the auditor's DE
    recheck, DF-01). Dated (``timed``): its result records when its calculation started and completed (the auditor's DG
    recheck, DH-03, 2026-11-06: ``prepared``, inserted above it, had taken its decorator, and a result lost its dates)."""
    from adroit.constraints import propagation
    from adroit.core import halo_choice
    from adroit.core.durable import publishing
    from adroit.parameter_space import halo_region
    request = halo_region.resolved(propagation.resolved(request)).model_copy(deep=True)   # its own (HA-05)
    resolution = halo_choice.resolve(halo_region.checked(request.halo))
    with publishing(folder, claim) as owned, propagation.using(request.propagation), \
            halo_region.using(halo_region.of(request.halo)), halo_choice.holding(resolution.data), \
            _ties_of(request.spec):
        result = _study(request, folder, fetch, owned)
    halo_choice.intact(resolution, request.halo)    # the halo it ran with is the one resolved (HA-05)
    halo_choice.unchanged(resolution)          # its halo data files as at its resolution, to its end
    from adroit.orchestrator import checklist
    return result.model_copy(update={"viability": checklist.for_single_idea(result), "halo_resolution": resolution})


def _checked(request: SingleIdeaRequest) -> tuple[SingleIdeaRequest, Profile | None, ExperimentModule, bool]:
    """(the request with its experimental profile applied, the profile, the search, whether a person verified it)."""
    profile=None
    if request.experimental_profile:
        from adroit.library.experimental_profiles import apply_signal,load
        request=apply_signal(request)
        profile=load(request.experimental_profile)
        if request.native_joint and (request.experiment.startswith('private-search:') or any(n.startswith('private-search:') for n in profile.null_modules)):
            raise ValueError('private event profiles use declared reconstructed/limit-equivalent terms; native joint workspace loader is unsupported')
        if request.native_joint and request.native_joint.null_experiment not in profile.null_modules:
            raise ValueError('native joint null is outside the reviewed profile selection')
    if request.catalog_reference:
        from adroit.library.personal import Catalog
        Catalog().verify_calculation(request.catalog_reference,request.spec,'track2',request.derivation)
    module = modules.load_module(request.experiment)
    from adroit.experiments.prescription import require_module
    require_module(module)          # its nuclear inputs installed, or refused now (V1-01)
    verified = getattr(module, "verified", True) is not False
    if not verified and not request.unverified_records and not getattr(module,'interpretation_confirmed',False):
        raise ValueError(f"the anomaly record {request.experiment!r} has not been verified by a person")
    _halo_checked(request, profile)
    return request, profile, module, verified


def _halo_checked(request: SingleIdeaRequest, profile: Profile | None) -> None:
    """The study's halo refused where it cannot be calculated (``refuse_halo``), with the profile's null searches."""
    nulls = [*request.null_modules, *(profile.null_modules if profile else [])]
    refuse_halo(request.halo, request.experiment, nulls, request.native_joint is not None)


def refuse_halo(halo, experiment: str, nulls: list[str], native_joint: bool = False) -> None:
    """A study's halo refused (``ValueError``) as its fresh run refuses it, before anything is calculated, never run at
    another halo: one this version cannot calculate (``halo_region.checked``: an unavailable family, a snapshot not of
    its family's form or not its generator's output); at a fixed benchmark, a search with no halo variation, or a
    native joint fit, which has no form at a benchmark yet (``halo_choice.CONSUMERS``). A promotion asks it of its
    children's halo before its first request (``promote.refuse_halo``: the auditor's HB recheck, HC-03, 2026-11-11)."""
    from adroit.parameter_space import halo_region
    halo_region.checked(halo_region.of(halo))
    if not isinstance(halo, FixedHalo):
        return
    from adroit.core import halo_choice
    path2.refuse_at_benchmark(halo, [experiment, *nulls])
    if native_joint:
        reason = halo_choice.unsupported(halo_choice.resolve(halo), "native-joint")
        raise ValueError(f"{reason}; drop --native-joint, or run with the published halos or the region")


def _fitted(request: SingleIdeaRequest, module: ExperimentModule, candidates: list[path2.Candidate],
            verified: bool) -> tuple[list[BandPoint], SingleIdeaResult]:
    """The fit at every mass, its global significance, and the tension with the nulls at the best mass."""
    band, fits, z_global, method, interval = _fit_masses(module, candidates, request.toys)
    if request.parent_global_z is not None:
        method += (f"; promoted from a library-wide search whose global significance is {request.parent_global_z:.2f}σ: "
                   "this study's own trials factor covers only its masses, so the parent's applies")
        z_global = min(z_global, request.parent_global_z)
    best = max(fits, key=lambda f: f.z_local)
    best_c = next(c for c in candidates if c.label == best.label)
    reference = next(b for b in band if b.m_chi==best_c.mass_gev)
    combo = path2._combine(module, best_c, best, path2.SignalRequest(
        experiment=request.experiment, null_modules=request.null_modules,
        unverified_records=request.unverified_records)) if reference.events_at_unit>0 else None
    result = SingleIdeaResult(request=request, verified=verified, band=band, best=best.label, global_z=z_global,
                              global_method=method, combination=combo,
                              global_toys=request.toys if interval else None, global_p_interval=interval)
    return band, result


def _native(request: SingleIdeaRequest, cls: ModelClass, point: Point, spin: float,
            folder: Path) -> JointResult | None:
    """The native joint calibration, if asked for: over its declared physical domain, or along the band."""
    if request.native_joint is None:
        return None
    if request.native_joint.null_experiment not in request.null_modules:
        raise ValueError("native joint null search must be explicitly included in the requested nulls")
    bounds = request.spec.physical_fit or PhysicalFitRange.perturbative_branch(point.g_chi)
    if request.native_joint.domain is not None:
        from adroit.orchestrator.native_fit import NativeFitRequest, run as native_domain_run
        destination = folder / "native_fit"
        return native_domain_run(NativeFitRequest(spec=request.spec,
            signal_experiment=request.experiment,masses_gev=request.masses_gev,settings=request.native_joint),
            destination,resume=(destination/".track1-checkpoint/manifest.json").exists())
    return native_joint_run(
        cls, point, request.masses_gev, bounds, request.native_joint,
        request.physical_fit_settings, spin, signal_experiment=request.experiment
    )


def _discovery(request: SingleIdeaRequest, options: dict):
    """(the pinned discovery assessment or None, the qualification of fitted and thermal points): an unresolved
    relevant constraint keeps an allowed point pending (``constraint_discovery.qualify_points``)."""
    if not request.discovery:
        return None, lambda points: points
    from adroit.orchestrator.constraint_discovery import check_model, load_coverage, qualify_points
    coverage = load_coverage(request.discovery)
    check_model(coverage, request.spec)
    selected = [item.reference for item in options.get("private_limits", [])]
    return coverage, lambda points: qualify_points(points, coverage, selected)


def _fit_options(request: SingleIdeaRequest, profile: Profile | None) -> dict:
    """The declared physical fit range and settings, with the profile's private limits and searches. Over the halo
    region or at a fixed benchmark, a private spin-independent curve or private search is refused, as in Track 1
    (``halo_region.check_inputs``: it holds only its paper's halo; before halo phase 1 the band's points had applied it
    over the region as if it held at every halo, beside the module it supersedes)."""
    options = {"fit_range":request.spec.physical_fit,"fit_settings":request.physical_fit_settings}
    if profile:
        from adroit.parameter_space.private_limits import check_applicability
        options.update(_private(profile))
        check_applicability(request.spec, options['private_limits'])       # as in Track 1 (S18-02)
        _refuse_private(request.halo, options["private_limits"], options["private_searches"])
    return options


def _private(profile: Profile) -> dict:
    """A profile's private limits and private searches, loaded."""
    from adroit.constraints.experimental_review import load_bound as limit
    from adroit.constraints.experimental_search_review import load_bound as search
    return {"private_limits": [limit(n) for n in profile.limits],
            "private_searches": [search(n) for n in profile.null_modules if n.startswith('private-search:')]}


def _refuse_private(halo, limits: list, searches: list) -> None:
    """Private inputs refused over the halo region or at a fixed benchmark (``halo_region.check_inputs``)."""
    from types import SimpleNamespace
    from adroit.parameter_space import halo_region
    if halo_region.of(halo) is not None:
        halo_region.check_inputs(SimpleNamespace(private_limits=limits, private_searches=searches, halo=halo))


def refuse_profile(halo, profile: Profile | None) -> None:
    """A profile's private spin-independent curves and private searches refused (``ValueError``) where the study's halo
    is the region or a fixed benchmark, as its fit refuses them (``_fit_options``). A promotion asks it of its
    children's halo, as their run states it (``halo_region.stated``), before its first request (``promote.refuse_halo``:
    the auditor's HC recheck, HD-03, 2026-11-12: a profile's private SI curve had reached the model builder first, and a
    published-halo parent's children, studied over the region, had been checked at the published halos)."""
    if profile is not None:
        found = _private(profile)
        _refuse_private(halo, found["private_limits"], found["private_searches"])


def _plane(request: SingleIdeaRequest, cls: ModelClass, point: Point, band: list[BandPoint], folder: Path,
           fetch=None, claim=None) -> tuple[Track1Result | None, list[str]]:
    """Track 1 on a window around the band, the band drawn on its plane (none without a physical point)."""
    # a model with no free coupling has no coupling plane (OB-11): its band is its masses, evaluated at its couplings
    fitted = any(b.point and b.fitted_value is not None for b in band)
    x, y = _window(band, request.grid,request.spec.physical_fit) if fitted else (None, None)
    t1 = None
    plot_names: list[str] = []
    if x is not None:
        t1 = track1.run(track1.Track1Request(spec=request.spec, model_class=cls, fixed=point, x=x, y=y,
                                             catalog_reference=request.catalog_reference,
                                             experimental_profile=request.experimental_profile,
                                             discovery=request.discovery, halo=request.halo,
                                             literature=request.literature, workers=request.workers,
                                             unverified_records=request.unverified_records), folder, fetch,
                       claim=claim)
        plot_names = t1.plots
    return t1, plot_names


def _draw_plane(result: "SingleIdeaResult", folder: Path) -> None:
    """The plane as the study shows it (``plane_overlays``: the band, and the stored signal assessment)."""
    t1 = result.track1
    if t1 is not None and t1.scan is not None and t1.verdict is not None:
        plots.plane(t1.scan, t1.verdict, folder / "parameter_plane.png", title=result.request.spec.name,
                    **plane_overlays(result))


def current_plane(result: "SingleIdeaResult"):
    """(the saved plane as read today, the indices of crossings whose reading changed): each saved signal assessment
    (a calculation) kept, the stored points' experimental, regional and thermal readings and the joint row taken
    again from them with today's reader (``assessment.from_crossing``, ``joint``), never from the copies saved beside
    them (the RB-01 recheck: a saved plane had kept "excluded" where its record is not established). The result's
    bytes are not changed; a changed reading is said where it is shown (``signal_plane_section``)."""
    from adroit.parameter_space import assessment as A
    plane, t1 = getattr(result, "signal_plane", None), getattr(result, "track1", None)
    if plane is None or t1 is None or t1.verdict is None or len(plane.crossings) != len(t1.verdict.crossings):
        return plane, []
    now = [A.from_crossing(c, saved.signal) for c, saved in zip(t1.verdict.crossings, plane.crossings)]
    same, constraints = plane.same_halo, plane.constraints_halo
    if same and not plane.assignment and constraints.startswith("each search's published halo"):
        # the common halo established again from the saved points' own evidence, never carried over as a saved flag
        # (the recheck's RC-04); a signal search whose module cannot be read establishes nothing
        try:
            from adroit.experiments import registry
            differ = _published_halos_differ(registry.load_module(result.request.experiment), t1)
        except Exception as error:  # noqa: BLE001 - not established, said
            differ = [f"the signal search's own halo ({type(error).__name__})"]
        if differ:
            same = False
            constraints = (f"each search's published halo, which differ or are not established: {', '.join(differ)}")
    joint = [A.joint(a, same)[0] for a in now]
    changed = [i for i, (old, new) in enumerate(zip(plane.joint, joint)) if old != new
               or plane.crossings[i].experimental != now[i].experimental]
    return plane.model_copy(update={"crossings": now, "joint": joint, "same_halo": same,
                                    "constraints_halo": constraints}), changed


def plane_overlays(result: "SingleIdeaResult") -> dict:
    """What Explain a signal draws on its plane beyond the constraints, from the stored result only (the study's own
    figure and every export read this one function): the fitted band (its fixed-mass 68% physical-fit intervals) and,
    where stored, the signal assessment at each grid point and each crossing's joint reading."""
    band = [(b.m_chi, b.fitted_68[0], b.fitted_value, b.fitted_68[1]) for b in result.band
            if b.point and _eligible(b) and None not in b.fitted_68]
    # a fit whose 68% region is disconnected keeps every piece (the plan's section 2), never one span across a gap
    pieces = [(b.m_chi, r.low, r.high) for b in result.band if b.point and _eligible(b) and b.physical_fit
              and len(b.physical_fit.regions) > 1 for r in b.physical_fit.regions]
    plane, _ = current_plane(result)        # the stored points read today, the saved signal assessments kept (RB-01)
    return {"band": band, "band_pieces": pieces, "signal": [g.state for g in plane.grid] if plane else None,
            "assessments": plane.crossings if plane else None, "joint": plane.joint if plane else None,
            "signal_label": f"meets the signal criterion ({plane.halo})" if plane else ""}


def signal_plane(request: SingleIdeaRequest, cls: ModelClass, module: ExperimentModule, spin: float,
                 t1: Track1Result | None) -> SignalPlane | None:
    """The signal requirement imposed on the plane (the owner's plan of 2026-11-24, section 2): the model's physical
    prediction (``physical_fit.predict``: its actual spectrum and accepted count, only the background profiled, no
    signal amplitude fitted) judged against the study's criterion at every grid point and at every thermal crossing
    at its own parameters (never the nearest grid point, never a refitted coupling), and each crossing's joint
    reading (``assessment.joint``). The signal is assessed where the study's fit is (a fixed benchmark in force, else
    the search's published halo); a plane judged over the halo region is not the same halo, so no crossing there is an
    unqualified joint explanation. None where there is no plane."""
    from adroit.parameter_space import assessment as A
    from adroit.parameter_space.halo_region import of
    if t1 is None or t1.scan is None or t1.verdict is None:
        return None
    events, _ = module.observations()
    null = float(signal_fit.profile_log_likelihood(0.0, np.zeros(len(events)), module.background_at(events),
                                                   module.background_rate())[0])
    halo = of(request.halo)
    if isinstance(halo, FixedHalo):
        where = constraints = f"the fixed benchmark {halo.benchmark}"
        same = True
    elif isinstance(halo, HaloPreset):
        where, constraints, same = "the search's published halo", "the tested halo region", False
    else:
        where = constraints = "each search's published halo"
        differ = _published_halos_differ(module, t1)
        same = not differ
        if differ:                  # the word "published" is not one halo (the signal/DD audit's R9-05)
            constraints = (f"each search's published halo, which differ: {', '.join(differ)} "
                           f"{'uses' if len(differ) == 1 else 'use'} another than {request.experiment}")
    assignment = ""
    if request.spec.relic_fraction != 1:
        same = False
        assignment = (f"the fit takes all the dark matter to be this particle; the thermal points are a "
                      f"{request.spec.relic_fraction:g} fraction of it")
    inputs = {"experiment": request.experiment, "model": request.spec.name}

    def at(p: Point) -> A.SignalAssessment:
        return A.signal_at(cls, p, module, spin, null, experiment=request.experiment, halo=where, inputs=inputs)
    grid = [A.grid_signal(at(row.point)) for row in t1.scan.points]
    crossings = [A.from_crossing(c, at(c.point)) for c in t1.verdict.crossings]
    return SignalPlane(experiment=request.experiment, halo=where, constraints_halo=constraints, same_halo=same,
                       assignment=assignment, null_log_l=null, grid=grid, crossings=crossings,
                       joint=[A.joint(a, same)[0] for a in crossings])


def _published_halos_differ(module, t1) -> list[str]:
    """The halo-dependent comparisons of the plane's points whose halo is not the signal search's (R9-05, and the
    repairs audit's RA-04: only direct detection's had been compared). Every constraint in
    ``halo_region.HALO_CONSTRAINTS`` that a point compared counts: direct detection by each deciding limit's module
    (its ``conventions().halo``); capture in the Sun by the default halo it is computed in under the published halos;
    the γ-ray line and antiproton searches by their own published Galactic profiles, which are not the signal's local
    halo and so never established the same. A point saved without its comparisons establishes nothing, so it is
    named too. Halos are compared physically (``exclusion.same_halo``: every field but the label)."""
    from adroit.core.dm_state import HaloModel
    from adroit.experiments import registry
    from adroit.orchestrator.exclusion import same_halo
    from adroit.parameter_space.halo_region import HALO_CONSTRAINTS
    mine = module.conventions().halo
    differ: set[str] = set()
    sources: set[str] = set()
    for c in t1.verdict.crossings:
        evaluation = getattr(c, "evaluation", None)
        if evaluation is None:
            differ.add("a point saved without its comparisons")
            continue
        compared = {name for name in (getattr(evaluation, "excluded", None) or {}) if name in HALO_CONSTRAINTS}
        mine_sources = {ch.limit.source for ch in getattr(evaluation, "dd_channels", None) or []
                        if ch.limit is not None and ch.limit.source}
        if "direct detection" in compared and not mine_sources:
            differ.add("direct detection (its limits' sources were not saved)")    # unknown, not the same (RB-03)
        sources |= mine_sources
        if "capture in the Sun (IceCube)" in compared and not same_halo(HaloModel(), mine):
            differ.add("capture in the Sun (IceCube)")
        differ |= {name for name in compared if name in ("γ-ray lines (Fermi-LAT, H.E.S.S.)", "antiprotons (AMS-02)")}
    for name in sorted(sources):
        try:
            theirs = registry.load_module(name).conventions().halo
        except (KeyError, ValueError, RuntimeError, OSError):
            differ.add(name)                # not established to be the same: never claimed so
            continue
        if not same_halo(theirs, mine):
            differ.add(name)
    return sorted(differ)


def _with_plane(level: str, text: str, plane: SignalPlane | None) -> tuple[str, str]:
    """The headline with what the signal-qualified plane resolved (the same stored rows the plot draws): a joint
    thermal explanation found there makes an undecided headline viable; one found only across two halo assignments
    makes it viable, pending; either way the plane's conclusion is said."""
    from adroit.parameter_space.assessment import EXPLAINS
    if plane is None:
        return level, text
    rows = set(plane.joint)
    if rows & set(EXPLAINS) and level in ("no_thermal", "undetermined", "no_fit", "viable_pending"):
        level = "viable"
    elif "explains_published_halo" in rows and level in ("no_thermal", "undetermined", "no_fit"):
        level = "viable_pending"
    return level, f"{text}; {plane.summary()}"


def _fit_quality(band: list[BandPoint], thermal: list[BandPoint] = (),
                 tables: dict[str, list[BandPoint]] | None = None) -> str:
    """fits, no_fit or undetermined (``_fit_verdict``) over every fit the study evaluated: the band's, the certified
    thermal points' and the equation-of-state tables' refits (the RX22 audit's RY23-02, 2026-10-23: a table's point
    refitted to Z = 2 was saved as "no_fit"). A fit found is not a thermal explanation: the headline stays the
    thermal one (``_eos_level``)."""
    extra = [b for rows in (tables or {}).values() for b in rows]
    return _fit_verdict(_fits(band, list(thermal)) + extra)[0]


@eos_reads.producer                      # its claims bound to the tables as it read them (the auditor's CT recheck, CU-02)
def _study(request: SingleIdeaRequest, folder: Path, fetch=None, claim=None) -> SingleIdeaResult:
    folder.mkdir(parents=True, exist_ok=True)
    request, profile, module, verified = _checked(request)
    options = _fit_options(request, profile)       # its private inputs checked before any calculation
    try:
        candidates = user_models.candidates(request.spec, request.masses_gev, request.derivation)
    except Unsupported as error:
        return SingleIdeaResult(request=request, verified=verified, unsupported=str(error), level="undetermined",
                                fit_quality="not_computed", constraint_compatibility="undetermined",
                                thermal_viability="undetermined", summary=f"the model cannot enter Track 2: {error}")
    band, result = _fitted(request, module, candidates, verified)
    try:
        cls, point, _ = classify(request.spec)
    except Unsupported as error:
        level, text = _level(band, [], computed=False)
        return result.model_copy(update={"unsupported": str(error), "level": level, "summary": text,
            "fit_quality": _fit_quality(band),
            "constraint_compatibility": "undetermined", "thermal_viability": level})
    spin = request.spec.dark_matter.spin
    native_result = _native(request, cls, point, spin, folder)
    band = [_on_band(cls, point, b, module, spin, request.unverified_records,**options) for b in band]
    extra = options if profile or request.spec.physical_fit is not None or request.physical_fit_settings != FitSettings() else {}
    thermal, unresolved = _thermal(cls, point, band, OMEGA * request.spec.relic_fraction, module, spin,
                                   request.unverified_records,**extra)
    # discovery qualifies every point, nominal and each table's, before the tables' comparison, as on the plane
    # (the auditor's consolidation audit, CO-02, 2026-10-25); the headline, the certificates and the pending reasons below
    # all read the one qualified set
    discovered, qualified = _discovery(request, options)
    unqualified, thermal = thermal, qualified(thermal)
    by_discovery = _discovery_added(unqualified, thermal)
    thermal, added, table_unresolved, tables, added_at, aside = _eos_band(cls, point, band, thermal,
                                                         OMEGA * request.spec.relic_fraction, module, spin,
                                                         request.unverified_records, qualified=qualified,
                                                         discovery=discovered is not None, **extra)
    band = qualified(band)
    thermal = _complete(thermal, by_discovery, request.unverified_records, discovered is not None)
    nominal_level, nominal_text = _level(band, thermal, computed=True, unresolved=unresolved,
                                         unverified=request.unverified_records)
    fit, fit_why = _fit_verdict(_fits(band, thermal))
    fit_pending = ([fit_why] if fit == "undetermined" else []) + _undecided_thermal(thermal)   # saved (RY23-03, RZ23-01)
    level, text = _eos_level(nominal_level, nominal_text, added, table_unresolved)
    if level != nominal_level:            # the tables' points that decided it, saved with its reasons (RV22-02)
        table_unresolved = table_unresolved + _eos_open(nominal_level, added)

    def thermal_at(target: float) -> tuple[list[BandPoint], list[str]]:
        rows, pending = _thermal(cls, point, band, target, module, spin, request.unverified_records, **extra)
        return qualified(rows), pending
    level, text = _across_disagreement(cls, point, band, thermal, (level, text), OMEGA * request.spec.relic_fraction,
                                       thermal_at, unresolved)
    aside = aside if level == "excluded" else {}
    if aside:                               # disposed of by their fit, not by a thermal claim (CS-04)
        text += "; " + "; ".join(f"the {name} table's thermal point at m_χ = {tables[name][i].m_chi:.4g} GeV is set "
                                 f"aside: its fit is {FIT_WORDS['below']}, so it explains nothing, whatever its "
                                 "thermal history" for name, positions in aside.items() for i in positions)
    t1, plot_names = _plane(request, cls, point, band, folder, fetch, claim)
    plane = signal_plane(request, cls, module, spin, t1)
    level, text = _with_plane(level, text, plane)
    best_physical = best_physical_fit(band)
    note = ("The reported global significance and null-amplitude comparison remain the unconstrained "
            "NR reference calculations. Bounded physical q0 is descriptive; discovery significance "
            "for the signal-only band has not been recalibrated. Native pair calibration, when "
            "requested, is reported separately for its own physical domain.") if any(b.physical_fit for b in band) or native_result is not None else ""
    done = result.model_copy(update={"band": band, "thermal": thermal, "level": level, "summary": text,
                                     "physical_best_mass_gev":best_physical.m_chi if best_physical else None,
                                     "physical_significance_note":note,
                                     "native_joint":native_result,
                                     "track1": t1, "plots": plot_names,
                                     "thermal_pending": fit_pending + unresolved + table_unresolved
                                     + _waiting(thermal, level),
                                     "rests_on": _rests_on(thermal, level),
                                     "rests_on_tables": added_at if level == "excluded" else {},
                                     "set_aside_tables": aside,
                                     "eos_thermal": tables,
                                     "fit_quality": _fit_quality(band, thermal, tables),
                                     "discovery_coverage": discovered,
                                     "constraint_compatibility": _compatibility([b for b in band if _eligible(b)]),
                                     "thermal_viability": level, "signal_plane": plane})
    _draw_plane(done, folder)            # from the stored result, as every export draws it (``plane_overlays``)
    return done


LEVELS = {"no_fit": "NO FIT", "excluded": "RESOLVED THERMAL EXPLANATIONS EXCLUDED", "viable": "A VIABLE THERMAL EXPLANATION",
          "viable_pending": "A VIABLE THERMAL EXPLANATION, PENDING A CALCULATION", "undetermined": "UNDETERMINED", "no_thermal": "NO RESOLVED THERMAL EXPLANATION"}


def _band_table(band: list[BandPoint]) -> list[str]:
    lines = ["| m_χ (GeV) | NR local Z / physical √q0 | μ̂ (68%, NR reference) | physical g_chi (nominal likelihood region); fixed m_med | Ωh² (relative thermal residual) | status | excluded by |",
             "|---|---|---|---|---|---|---|"]
    for b in band:
        bounds = "–".join("pending" if v is None else f"{v:.3g}" for v in b.fitted_68)
        med = ("—" if b.point is None else f"fixed couplings, not fitted; {b.m_med:.6g} GeV" if b.fitted_value is None
               else f"{b.fitted_value:.3g} ({bounds}); {b.m_med:.6g} GeV")
        omega = "—" if b.omega_h2 is None else f"{b.omega_h2:.3g}"
        if b.relative_residual is not None:
            omega += f" ({b.relative_residual:.2g}; {'certified' if b.converged else 'unresolved'})"
        lines.append(f"| {b.m_chi:.3g} | {_fit_column(b)} | {b.mu_hat:.3g} ({b.mu_68[0]:.3g}–{b.mu_68[1]:.3g}) | "
                     f"{med} | {omega} | {_status_words(b) or '—'} | {', '.join(b.excluded_by) or '—'} |")
    return lines


def _status_words(b: BandPoint) -> str:
    """A point's stored status, with its computed one where the certificate's gate changed it (M1)."""
    from adroit.parameter_space.certification import status_words
    return status_words(b) if b.status else ""


def _fit_column(b: BandPoint) -> str:
    """The NR local Z and, for a physical fit, its stored √q0, labelled where it cannot support the headline
    (``_fit_state``). The re-audit's R18-5 (2026-10-18): the headline policy's zero had been printed as the
    statistic."""
    if b.physical_fit is None:
        return f"{b.z_local:.2f}"
    q0 = b.physical_fit.q0
    value = f"{math.sqrt(max(q0, 0.)):.2f}" if q0 is not None and math.isfinite(q0) else "—"
    state = _fit_state(b)
    label = f" ({FIT_LABEL[state]}; not eligible)" if state in FIT_LABEL else ""
    return f"{b.z_local:.2f} / {value}{label}"




@dated_report
def report(result: SingleIdeaResult) -> str:
    """The single-idea report in Markdown (plots beside it)."""
    r, spec = result.request, result.request.spec
    lines = [f"# Single idea: {spec.name} as the explanation of {r.experiment}", ""]
    if not result.verified:
        lines += ["**The anomaly record has not been verified by a person**; this report is provisional.", ""]
    if result.native_joint is not None:
        lines += ["The thermal headline below uses the signal-only fitted band. "
                  "The native joint fit and significance are reported separately.", ""]
    lines += [f"**{LEVELS.get(result.level, result.level.upper())}**: {result.summary}.", ""]
    from adroit.evidence.halo import identity_note
    lines += [halo_line(result) + identity_note("single_idea", result), ""]
    from adroit.orchestrator.plain_summary import single_idea as in_brief
    lines += in_brief(result)                      # plain words first (OB-09); the detailed report below is unchanged
    if result.native_joint is not None:
        lines += _native_report(result.native_joint)
    if not result.band:
        return "\n".join(lines) + "\n"
    lines += _fit_section(result)
    lines += _certificate_sections(result)
    c = result.combination
    if c is not None:
        lines += ["## 2. The null experiments (unconstrained NR reference)", "",
                  f"At the best mass the signal alone wants μ̂ = {c.mu_hat_signal:.3g} (Z = {c.z_signal:.2f}); "
                  f"with the null experiments μ̂ = {c.mu_hat_joint:.3g} (Z = {c.z_joint:.2f}). Their tension: "
                  f"χ²_PG = {c.chi2_pg:.2f}, p = {c.p_pg:.2g}.", ""]
        lines += [f"- {name}: μ_up = {mu:.3g}" for name, mu in c.null_limits.items()]
        lines += [f"- Null coverage pending, {name}: {why}" for name, why in c.omitted_nulls.items()] + [""]
    if result.unsupported:
        lines += ["## 3. Parameter space", "", f"Not computed: {result.unsupported}.", ""]
        return "\n".join(lines) + "\n\n" + _checklist(result)
    if result.thermal:
        from adroit.parameter_space.certification import summary_lines
        lines += ["Where the band meets the thermal-relic contour:", ""] + _band_table(result.thermal) + [""]
        lines += summary_lines(result.thermal, "thermal points") + [""]
        from adroit.core.certificate import EOS_NOT_ASSESSED
        if any(b.certificate is not None and (x := b.certificate.check("eos_band")) is not None
               and x.reason == EOS_NOT_ASSESSED for b in result.thermal):
            stated = result.track1 is not None and result.track1.verdict is not None and \
                track1.eos_policy_lines(result.track1.verdict)               # its Track 1 section says it, once
            lines += [] if stated else [
                "Equation of state: Ωh² is computed with ADROIT's nominal equation of state, Saikawa & Shirai's 2018 "
                "fit (arXiv:1803.01038); its uncertainty is not propagated in ADROIT 1.0 (deferred to 1.0.2).", ""]
    if result.track1 is not None:
        rest = track1.report(result.track1).split("## 2. The verdict", 1)[-1].split("## 6. Viability checklist", 1)[0]
        lines += ["## 3. The plane around the band", ""] + signal_plane_section(result) + [
                  "### The constraint plane (Track 1 on the same window)", "",
                  "What follows judges the plane's points against the constraints only: whether a point can explain "
                  "the signal is the signal column above, never these levels.", "",
                  "#### The constraint verdict" + rest.replace("\n## ", "\n#### ")]
    return "\n".join(lines) + "\n\n" + _checklist(result)


def signal_plane_section(result: SingleIdeaResult) -> list[str]:
    """The plane with the signal requirement imposed, from the stored assessment (``signal_plane``): the conclusion,
    the criterion and the halo it was assessed at, and each thermal crossing's signal, constraint and joint readings.
    A result written before it says that its plane is a constraint plane only."""
    from adroit.parameter_space.assessment import JOINT, experimental_words
    plane, changed = current_plane(result)
    if plane is None:
        return ["This result was written before the signal requirement was imposed on its plane: the plane below is "
                "a constraint plane only, and none of its points is shown to explain the signal.", ""]
    t1 = result.track1
    lines = [f"**On the plane:** {plane.summary()}.", "",
             f"The signal criterion is that {plane.criterion}. The prediction is the model's actual spectrum and "
             f"accepted count at each point, only the background profiled and no signal amplitude fitted, at "
             f"{plane.halo}; the constraints are judged at {plane.constraints_halo}."
             + (" The two differ, so no point here is a halo-robust joint explanation." if not plane.same_halo and
                not plane.assignment else "")
             + (f" Density assignment: {plane.assignment}." if plane.assignment else ""),
             "The magenta band is the fit's fixed-mass 68% physical-fit intervals (not a joint region across mass "
             "and coupling), and the thermal solutions are coloured by whether they lie inside it at their mass; "
             "shading and hatching mark experimental exclusions, each named in the figure's legend (the signal "
             "criterion's region is drawn only where asked for).", ""]
    if changed:
        lines += [f"Read again with the current reader: {len(changed)} thermal crossing(s) read differently from the "
                  "readings saved with the study (an experimental input not established, for example); the saved "
                  "signal assessments are kept, and the result itself is unchanged.", ""]
    if not plane.crossings:
        return lines
    x, y = t1.scan.request.x.parameter, t1.scan.request.y.parameter
    lines += [f"| {x} | {y} | signal (2ΔlnL; predicted events) | constraints | jointly |", "|---|---|---|---|---|"]
    for c, a, row in zip(t1.verdict.crossings, plane.crossings, plane.joint):
        s = a.signal
        signal = (f"{s.state} ({s.improvement:+.3g}; {s.predicted_events:.3g})" if s is not None and
                  s.improvement is not None else f"{s.state if s else 'not assessed'}" + (f": {s.reason}" if s and
                                                                                       s.reason else ""))
        constraints = experimental_words(a) or {"not_excluded": "not excluded", "undecided": "undecided"}.get(
            a.experimental.state, a.experimental.state) + (f" ({a.regional.detail})" if a.regional.detail else "")
        lines.append(f"| {getattr(c.point, x):.4g} | {getattr(c.point, y):.4g} | {signal} | {constraints} | "
                     f"{JOINT.get(row, row)} |")
    return lines + [""]


def halo_line(result: SingleIdeaResult) -> str:
    """The report's statement of the study's halo: its fit's and its constraints' (they differ unless one fixed
    benchmark is asked for)."""
    from adroit.core.halo_choice import resolve
    r = result.request
    if isinstance(r.halo, FixedHalo):
        return (f"Halo: one fixed common benchmark for the fit, the null comparisons, the band's and thermal points' "
                f"constraints and the Track 1 plane: {resolve(r.halo).summary}")
    where = ("over the SHM uncertainty region (section 3 states it)" if isinstance(r.halo, HaloPreset) else
             "with each experiment's published halo")
    return (f"Halo: the fit and the null comparisons at each search's own published halo; the band's and thermal "
            f"points' constraints and the Track 1 plane {where}.")


def _fit_section(result: SingleIdeaResult) -> list[str]:
    """Section 1: the fitted band, its bounded physical fits and the thermal calculations still pending."""
    lines = ["## 1. The fit", "",
              f"Best fit: {result.best}; unconstrained NR-reference global significance over the {len(result.band)} masses "
              f"{result.global_z:.2f}σ ({result.global_method}). μ scales the NR amplitude; μ = 1 is "
              "its stated couplings. The physical band varies g_chi within its declared range or original-sign perturbative branch, keeping masses and other couplings fixed.", ""] + _band_table(result.band) + [""]
    if result.physical_significance_note:
        lines += [result.physical_significance_note,"",
                  f"Best resolved physical-fit mass: {result.physical_best_mass_gev} GeV." if
                  result.physical_best_mass_gev is not None else
                  "No mass has a resolved physical fit: none settles inside its range, away from its edge, with a "
                  "finite fit statistic above 0.",""]
    for b in result.band:
        fit = b.physical_fit
        if fit:
            regions = "; ".join(f"[{r.low:.6g}, {r.high:.6g}]"+(
                " (truncated at physical bound)" if r.low_at_bound or r.high_at_bound else "") for r in fit.regions)
            lines += [f"- {b.m_chi:g} GeV bounded g_chi: [{fit.bounds.low:g}, {fit.bounds.high:g}], "
                f"resolved={fit.resolved}, identifiable={fit.identifiable}, boundary={fit.at_boundary}, "
                f"{fit.evaluations}/{fit.settings.max_evaluations} spectrum evaluations; "
                f"nominal likelihood regions: {regions or 'unresolved'}. {fit.reason}"]
    best = next((b for b in result.band if result.physical_best_mass_gev is not None
                 and b.m_chi == result.physical_best_mass_gev), None)      # the best fit's own row (AL3-23)
    lines += [f"Constraint compatibility of the band's eligible fitted masses (viable where any is): "
              f"{result.constraint_compatibility or 'undetermined'}"
              + (f"; of the best resolved physical fit ({best.m_chi:g} GeV): {best.status}" if best else "")
              + f"; thermal viability: {result.thermal_viability or result.level}.", ""]
    lines += [f"- {b.m_chi:g} GeV: {b.inversion_reason}" for b in result.band if b.inversion_reason]
    lines += [f"- Thermal calculation pending: {reason}" for reason in result.thermal_pending] + [""]
    return lines


def _certificate_sections(result: SingleIdeaResult) -> list[str]:
    """The discovery coverage and the vacuum, unitarity, running and chemical certificates of every point."""
    lines = []
    if result.discovery_coverage is not None:
        from adroit.orchestrator.track1 import discovery_section
        lines += discovery_section(result.discovery_coverage, [])
    from adroit.theory.report import study_section
    lines += study_section([b.evaluation.vacuum_certificate for b in [*result.band,*result.thermal]
        if b.evaluation and b.evaluation.vacuum_certificate])
    from adroit.theory.unitarity_report import study_section as unitarity_section
    lines += unitarity_section([b.evaluation.unitarity_certificate for b in [*result.band,*result.thermal]
        if b.evaluation and b.evaluation.unitarity_certificate])
    from adroit.theory.running_report import study_section as running_section
    lines += running_section([b.evaluation.running_certificate for b in [*result.band,*result.thermal]
        if b.evaluation and b.evaluation.running_certificate])
    from adroit.theory.chemical_report import study_section as chemical_section
    lines += chemical_section([b.evaluation.chemical_certificate for b in [*result.band,*result.thermal]
        if b.evaluation and b.evaluation.chemical_certificate])
    return lines


def _checklist(result: SingleIdeaResult) -> str:
    """Section 4: the viability checklist, with the fit as direct-detection evidence (computed afresh for an older
    result that did not store it)."""
    from adroit.constraints import viability
    from adroit.orchestrator import checklist
    entries = result.viability or checklist.for_single_idea(result)
    text = viability.report(entries).replace("## Viability checklist (thermal freeze-out)",
                                             "## 4. Viability checklist (thermal freeze-out)", 1)
    if result.viability:            # the checklist as the study saved it, not rebuilt with today's code (R9-06)
        text = text.replace("## 4. Viability checklist (thermal freeze-out)",
                            "## 4. Viability checklist (thermal freeze-out)\n\nAs saved with the study, not rebuilt "
                            "with the current code.", 1)
    return text


def _native_report(result: JointResult) -> list[str]:
    """Keep calibrated native-pair results separate from NR/thermal references."""
    if result.settings.domain is not None:
        fit=result.domain_fit
        lines=["## Native bounded multiparameter fit", "",
            f"Pair: {result.signal_experiment} + {result.null_experiment}.",
            "Separate physical-fit view; signal-only thermal results and the unconstrained NR reference remain separate.",
            "No multiparameter discovery p-value or calibrated confidence region is reported.", "",
            f"Recorded reference Point: {result.reference_point}.",
            f"Declared domain: {result.settings.domain.model_dump(mode='json')}.", ""]
        if fit:
            lines += [fit.construction,
                f"Resolved={fit.resolved}; identifiable diagnostic={fit.identifiable}; "
                f"evaluations={fit.evaluations}/{fit.settings.max_evaluations}; {fit.reason}",
                f"Best point: {fit.point}; log L={fit.log_l}; descriptive q0={fit.q0}.", "",
                "| branch | physical point | log L | boundary coordinates | local rank |",
                "|---|---|---|---|---|"]
            lines += [f"| {m.branch} | {m.point} | {m.log_l:.9g} | {m.boundaries} | {m.local_rank} |" for m in fit.modes]
            lines += ["", "Sampled profile diagnostics (uncalibrated):"]
            for name, values in fit.profiles.items():
                lines += [f"- {name}: "+'; '.join(f"{p.value:.8g}: delta log L={p.delta_log_l:.8g} ({p.branch})" for p in values)]
        lines += ["", *[f"Pending, {k}: {v}" for k,v in result.omitted.items()],*result.assumptions,""]
        return lines
    lines=["## Native joint signal/null pilot", "",
        f"Pair: {result.signal_experiment} + {result.null_experiment}.",
        "This section fits one shared physical coupling. The main study's signal-only "
        "band/thermal headline and its unconstrained NR-reference statistics remain separate.",""]
    lines += [f"Searched mass bank: {result.masses_gev} GeV."]
    if result.bounds is not None:
        lines += [f"Continuous physical g_chi range: [{result.bounds.low:.8g}, {result.bounds.high:.8g}]."]
    if result.reference_point is not None:
        p = result.reference_point
        lines += [f"Fixed m_med={p.m_med:.8g} GeV, g_q={p.g_q:.8g}, g_l={p.g_l:.8g}."]
    lines += [""]
    if result.omitted:
        return lines+[f"- Pending native coverage, {name}: {why}" for name,why in result.omitted.items()]+[""]
    if result.best_point:
        p=result.best_point
        lines += [f"Best joint point: m_chi={p.m_chi:.8g} GeV, g_chi={p.g_chi:.8g}; "
                  f"observed max q0={result.observed_max_q0:.8g}; background theta={result.background_theta:.8g}."]
    cal=result.calibration
    if cal and cal.complete:
        low,high=cal.p_interval_95
        lines += [f"Calibrated physical-domain p_MC={cal.p_mc:.6g}, Z_MC={cal.z_mc:.4g}; "
            f"{cal.exceedances}/{cal.toys_completed} toys exceed the observed statistic; "
            f"binomial 95% tail interval [{low:.6g}, {high:.6g}].",
            f"Seed={cal.seed}; {cal.toy_fits} toy fits; p-resolution={cal.minimum_resolvable_p:.6g}; "
            f"q0 comparison tolerance={cal.q0_comparison_tolerance:.3g}.",cal.construction]
    elif cal:
        lines += [f"Native calibration pending: {cal.reason}; {cal.toys_completed}/{cal.toys_requested} toys complete. "
                  "No calibrated p-value is reported from incomplete coverage."]
    lines += ["",*result.assumptions,""]
    return lines


def grid_range() -> tuple[int, int]:
    """The Track 1 plane sizes a single-idea study accepts (``SingleIdeaRequest.grid``: n × n), read from the field so
    that the Promote form and ``adroit promote`` offer no size its child refuses (the release layer found the form
    offering 2 × 2, 2026-10-25)."""
    from annotated_types import Ge, Le
    meta = SingleIdeaRequest.model_fields["grid"].metadata
    return (next(int(m.ge) for m in meta if isinstance(m, Ge)), next(int(m.le) for m in meta if isinstance(m, Le)))


def reassessed(result: SingleIdeaResult, folder: Path | None = None) -> SingleIdeaResult:
    """The saved study with the signal requirement imposed on its saved plane (``orchestrator.reassess``; the owner's
    plan of 2026-11-24, section 4): ``signal_plane`` on the plane it saved, in the study's own halo and propagation
    context, and the headline read with it (``_with_plane``). No fit, scan or constraint is computed again. A study
    without a plane gets none. ``folder``: where its plane is drawn."""
    from adroit.constraints import propagation
    from adroit.core import halo_choice
    from adroit.parameter_space import halo_region
    request, _, module, _ = _checked(result.request)
    cls, _, _ = classify(request.spec)
    spin = request.spec.dark_matter.spin
    resolution = result.halo_resolution or halo_choice.resolve(halo_region.checked(request.halo))
    with propagation.using(request.propagation), halo_region.using(halo_region.of(request.halo)), \
            halo_choice.holding(resolution.data), _ties_of(request.spec):
        plane = signal_plane(request, cls, module, spin, result.track1)
    level, text = _with_plane(result.level, result.summary, plane)
    new = result.model_copy(update={"signal_plane": plane, "level": level, "summary": text,
                                    "thermal_viability": level})
    if folder is not None and plane is not None:
        _draw_plane(new, Path(folder))
        new = new.model_copy(update={"plots": ["parameter_plane.png"]})
    return new

"""The verdict on a model's parameter space, under the thermal assumption (DM13).

Adjacent grid brackets are refined with the actual relic solver. Accepted
contour points carry a density residual at most 1%; unavailable or unresolved
calculations remain pending. Negative statements refer only to the sampled
region and resolution. Optional theory-error band points are labelled
separately from certified numerical roots.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import NamedTuple

from pydantic import Field, StrictInt, model_validator

from adroit.constraints import eos_reads
from adroit.core.state import StrictModel
from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
from adroit.parameter_space.coverage import CoverageDiagnostic
from adroit.constraints.searches import Outcome
from adroit.parameter_space.limits import StatisticalLimit
from adroit.parameter_space.thermal import ThermalRoot, refine
from adroit.parameter_space import halo_region
from adroit.parameter_space.classes import Point
from adroit.parameter_space.likelihood import (DENSITY, LikelihoodSettings, Q_95, BAND_95, combined, combined_ratio,
                                              relic_chi2)
from adroit.core.certificate import Certificate, Check, survives
from adroit.parameter_space.scan import GENERIC_FLAG, PointResult, ScanResult, _point_at, evaluate

OMEGA = DENSITY.value                    # the relic target, as read with its record's version (CT-02)
COLLIDER_REACH_GEV = 1e4


class Crossing(StrictModel):
    """One evaluated point (on the thermal contour, in a theory band, or arbitrary): its status, the constraints that
    exclude it or leave it pending, its Ωh² residual against the target and the retained comparisons."""
    point: Point
    status: str                              # viable, pending, excluded
    excluded_by: list[str] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)     # unreliable verdicts here (e.g. a record's edge)
    omega_h2: float | None = None
    target: float | None = None
    relative_residual: float | None = None
    converged: bool = False
    kind: str = "point"                     # contour, theory_band, or arbitrary point
    native_constraints: dict[str, Outcome] = Field(default_factory=dict)
    statistical_limits: dict[str, StatisticalLimit] = Field(default_factory=dict)
    r_combined: float | None = None          # the combined likelihood's r (likelihood mode)
    evaluation: PointResult | None = None   # retained comparisons; absent in legacy results
    # over a halo region (``halo_region``): its label for the point, and the status at the region's centre
    halo: str = Field(default="", exclude_if=lambda v: not v)
    nominal_status: str = Field(default="", exclude_if=lambda v: not v)
    # the constraints that excluded it at the region's centre, kept when the region leaves it pending (the owner's plan
    # of 2026-11-24: a central exclusion is shown, qualified, never erased; ``assessment.nominal_exclusions``)
    nominal_excluded_by: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    # its claim's certificate (``certification``; the consolidation plan's M1): absent in results written before it,
    # which read "legacy, not assessed"
    certificate: Certificate | None = Field(default=None, exclude_if=lambda v: v is None)


class Verdict(StrictModel):
    """The verdict on a scanned plane: its level and summary, the thermal target, the evaluated crossings and the
    root attempts, in cuts or likelihood mode."""
    mode: str = "cuts"                       # cuts (each constraint at 95% CL) or likelihood (combined)
    level: str                               # viable, viable_pending, excluded, overabundant, underabundant
    summary: str
    target: float
    crossings: list[Crossing] = Field(default_factory=list)
    root_attempts: list[ThermalRoot] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    omitted_candidates: int = 0
    # formed with a pinned discovery assessment applied to every evaluated point (S18-03); left out when not
    discovery_applied: bool = Field(default=False, exclude_if=lambda v: not v)
    # the claims its level rests on, each "<kind> at <where>: <status>" (M1's headline reducer), and what qualifies it
    # (D-4: unverified records); absent in older results
    support: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    qualifiers: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    # the thermal roots only a table has (``_eos_new_roots``), each certified with its table and records; and which
    # claims the level rests on, by position in ``crossings`` and ``table_roots`` (the auditor's CO recheck, CR-02 and
    # CR-04, 2026-10-26): the history assesses exactly those. None in older results: every crossing.
    table_roots: list[Crossing] = Field(default_factory=list, exclude_if=lambda v: not v)
    rests_on: list[StrictInt] | None = Field(default=None, exclude_if=lambda v: v is None)       # positions, so
    rests_on_table_roots: list[StrictInt] = Field(default_factory=list, exclude_if=lambda v: not v)  # true is none

    @model_validator(mode="after")
    def _support_held(self) -> Verdict:
        """The claims its level rests on are its own (``core.certificate.held``; the auditor's CR recheck, CS-01,
        2026-10-27): a position outside ``crossings`` or ``table_roots``, or table roots named where its own
        crossings are not (``rests_on`` absent), is not a verdict's."""
        from adroit.core.certificate import held
        held("rests_on", self.rests_on or [], len(self.crossings))
        held("rests_on_table_roots", self.rests_on_table_roots, len(self.table_roots))
        if self.rests_on is None and self.rests_on_table_roots:
            raise ValueError("rests_on_table_roots names table roots where rests_on names no crossings")
        return self


def _with_discovery(result: ScanResult, v: Verdict | None) -> Verdict | None:
    return v.model_copy(update={"discovery_applied": True}) if v is not None and result.request.discovery else v


def _root_candidates(result: ScanResult, target: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Grid endpoints on target, plus each actual adjacent sign-changing edge."""
    nx, ny = len(result.xs), len(result.ys)
    candidates = []
    if len(result.points) != nx * ny:
        return candidates
    for j in range(ny):
        for i in range(nx):
            a = result.points[j * nx + i].omega_h2
            if a is None or not math.isfinite(a) or a < 0:
                continue
            xy = (result.xs[i], result.ys[j])
            if abs(a / target - 1) < 1e-10:
                candidates.append((xy, xy))
            for ii, jj in ((i + 1, j), (i, j + 1)):
                if ii >= nx or jj >= ny:
                    continue
                b = result.points[jj * nx + ii].omega_h2
                if b is not None and math.isfinite(b) and b >= 0 and (a - target) * (b - target) < 0:
                    candidates.append((xy, (result.xs[ii], result.ys[jj])))
    return candidates


def along(u: float, v: float, t: float, log: bool) -> float:
    """The value a fraction t of the way from u to v: geometrically on a log axis, u(v/u)^t, which also holds for an
    axis of negative values such as a negative portal coupling (G12's live check L3: math.log(u) had failed there,
    so every thermal root was left pending), else linearly."""
    return u * (v / u) ** t if log else u + t * (v - u)


def _bracket_point(request, a: tuple[float, float], b: tuple[float, float], t: float) -> Point:
    """The point a fraction t of the way along the grid edge from a to b (``along``)."""
    values = [along(u, v, t, axis.log) for u, v, axis in zip(a, b, (request.x, request.y))]
    return _point_at(request, *values)


def _grid_omega(request, point: Point) -> float | None:
    """Ωh² at a point by the grid's engine, the fallback included (G3/G4-5, G12); None outside its domain."""
    from adroit.parameter_space.scan import engine_for
    cls, _ = engine_for(request, point)
    if hasattr(cls, "domain") and cls.domain(point):
        return None
    return cls.omega_h2(point)


def _thermal_roots(result: ScanResult, target: float, maximum: int | None = None,
                   checkpoint: Checkpoint | None = None) -> tuple[list[ThermalRoot], int]:
    candidates = _root_candidates(result, target)
    step = max(1, math.ceil(len(candidates) / maximum)) if maximum else 1
    chosen = candidates[::step]
    request = result.request
    roots = []
    for index, (a, b) in enumerate(chosen):
        def point_at(t: float) -> Point:
            return _bracket_point(request, a, b, t)

        def omega(point: Point) -> float | None:
            return _grid_omega(request, point)

        root = checkpoint.load("refinement", str(index), ThermalRoot) if checkpoint else None
        if root is not None and (root.target != target or
                                 (root.point is not None and root.coordinate is not None and
                                  root.point != point_at(root.coordinate))):
            raise CheckpointMismatch("Cached thermal attempt differs from its bracket or target")
        if root is None:
            root = refine(point_at, omega, target, high=0 if a == b else 1)
            if checkpoint:
                checkpoint.save("refinement", str(index), root)
        root = root.model_copy(update={"bracket": (tuple(a), tuple(b))})
        if checkpoint:
            checkpoint.update("refinement", index + 1, len(chosen), "thermal brackets refined")
        if not root.converged or not any(r.point == root.point for r in roots):
            roots.append(root)
    return roots, len(candidates) - len(chosen)


def _crossings(result: ScanResult, target: float) -> list[Point]:
    """Only solver-evaluated thermal crossings; interpolation is not a certificate."""
    roots, _ = _thermal_roots(result, target)
    return [r.point for r in roots if r.converged]


RECORD_PENDING = {"invisible Higgs width (ATLAS)": "the invisible Higgs width: its record (ATLAS, arXiv:2301.10731) "
                                                    "awaits a person's verification",
                  "invisible Z width (LEP)": "the invisible Z width: its record (LEP, arXiv:hep-ex/0509008) awaits "
                                             "a person's verification"}


def judge_point(cls, p: Point, unverified: bool = False, likelihood: LikelihoodSettings | None = None,
                lhc_result: dict | None = None,private_limits: list | None=None,private_searches:list|None=None) -> Crossing:
    """Every constraint exactly at one point on the relic contour."""
    row=(evaluate(cls,p,unverified,lhc_result,private_limits,private_searches) if private_searches else
         evaluate(cls,p,unverified,lhc_result,private_limits) if private_limits else evaluate(cls,p,unverified,lhc_result))
    return classify(cls,row,likelihood)


def theory_status(r: PointResult) -> tuple[list[str], list[str]]:
    """(exclusions, pending) from a point's theory certificates (audit M10).

    A complete certificate that fails (a vacuum unbounded below, unstable, or metastable but decaying within the
    age of the universe; |a₀| ≥ ½ in some scalar channel; or running that leaves the bounded or perturbative
    region below the declared scale) makes the point an invalid model point, whatever the data say. A
    metastable vacuum that outlives the universe passes (``metastable_flag``). A certificate that is
    unresolved, incomplete or missing input leaves the point pending.
    """
    excluded, pending = [], []
    certificates = (("the tree-level vacuum", r.vacuum_certificate, "vacuum"),
                    ("tree-level scalar unitarity", r.unitarity_certificate, "status"),
                    ("the one-loop running", r.running_certificate, "status"))
    for name, c, field in certificates:
        if c is None:
            continue
        state = getattr(c, field)
        if c.complete and c.passed is False:
            excluded.append(f"theory: {name} fails ({state}), an invalid model point")
        elif c.passed is not True:
            why = "; ".join(c.reasons[:2])
            pending.append(f"theory: {name} is unresolved ({state}{': ' + why if why else ''})")
    return excluded, pending


def metastable_flag(r: PointResult) -> list[str]:
    """A flag for a declared vacuum that is metastable but outlives the universe (it passes)."""
    c = r.vacuum_certificate
    if c is None or c.vacuum != "metastable" or c.decay is None:
        return []
    return [f"theory: the electroweak vacuum is metastable (a deeper {c.decay.true_vacuum} minimum) but outlives "
            f"the universe: ln P = {c.decay.log_probability:.4g}, by {c.decay.decided_by}"]


def unfinite(ratios: dict[str, float], chi2: dict[str, float]) -> dict[str, float]:
    """The comparisons that are not numbers a verdict can rest on, each with its value: a ratio to a limit that is not
    finite and nonnegative, a Δχ² that is not finite. A constraint's own "excluded" read from one (nan > 1 is False)
    decides nothing (the consistency audit's CA-03, 2026-10-24: a nan ratio beside an excluding one made the combined
    likelihood nan, and the point viable)."""
    bad = {k: v for k, v in ratios.items() if v is None or not math.isfinite(v) or v < 0}
    return bad | {k: v for k, v in chi2.items() if v is None or not math.isfinite(v)}


def unfinite_reasons(bad: dict[str, float]) -> list[str]:
    """The pending reason of each of ``unfinite``'s comparisons."""
    return [f"{k}: its comparison gave {v}, not a finite, nonnegative ratio or a finite Δχ²; it decides nothing until "
            "computed again" for k, v in bad.items()]


def _combination(ratios: dict[str, float], chi2: dict[str, float], likelihood: LikelihoodSettings,
                 levels: dict | None, sided: dict | None, bad: dict[str, float]) -> tuple[float, list[str]]:
    """(r_comb, its exclusion or []) of the combination without ``bad``'s comparisons. Each limit's q is nonnegative,
    so the rest's q is a lower bound and an exclusion by it stands; a Δχ² left out can be negative, and then the rest
    decides nothing."""
    q = combined({k: v for k, v in ratios.items() if k not in bad}, {k: v for k, v in chi2.items() if k not in bad},
                 likelihood.prediction_theory, levels, sided)
    r_comb = combined_ratio(q)
    if q <= Q_95 or any(k in chi2 for k in bad):
        return r_comb, []
    without = f" without {', '.join(bad)}" if bad else ""
    return r_comb, [f"the combined likelihood (r = {r_comb:.2f}{without})"]


def classify(cls, r: PointResult, likelihood: LikelihoodSettings | None = None) -> Crossing:
    """A point's status from its constraints: each a 95% CL cut, or (``likelihood``) combined. A comparison that is
    not a finite number (``unfinite``) is pending, in either mode."""
    p = r.point
    bad = unfinite(r.ratios, r.chi2)
    if likelihood is None:
        excluded = [k for k, v in r.excluded.items() if v and k not in bad]
        r_comb = None
    else:
        cuts = [k for k, v in r.excluded.items() if v and k not in r.ratios and k not in r.chi2]
        r_comb, by = _combination(r.ratios, r.chi2, likelihood, r.ratio_confidence_levels or None,
                                  r.ratio_sidedness or None, bad)
        excluded = cuts + by
    pending = unfinite_reasons(bad)
    if r.model_pending is not None:                   # the engine's reasons, saved with the evaluation (F19-07)
        pending += r.model_pending
    elif hasattr(cls, "pending"):                     # a portal model names what applies but is not computed
        pending += cls.pending(p)
    elif (r.excluded.get("colliders (CMS)") is None and "LHC searches (SModelS)" not in r.excluded and p.g_q > 0
          and p.m_med < COLLIDER_REACH_GEV):
        pending.append("colliders: a recast of the LHC searches to this model")
    pending += [text for key, text in RECORD_PENDING.items() if key in r.excluded and r.excluded[key] is None]
    pending += [reason for reason in r.pending if reason not in pending]
    from adroit.parameter_space.operator_limits import STRUCTURES
    if r.dd_ratio is not None:
        pass
    elif r.dd_kind in STRUCTURES:
        pending.append(f"direct detection ({r.dd_kind}): no eligible 95% Path 1 module limit at this mass")
    elif r.dd_limit_cm2 is None and r.dd_kind in ("SI", "SD-proton", "SD-neutron"):
        pending.append(f"direct detection ({r.dd_kind}): beyond the validated range of the system's modules")
    elif r.dd_limit_cm2 is None and r.dd_kind != "inelastic":
        pending.append(f"direct detection ({r.dd_kind}): not compared with the spin-independent or "
                       "spin-dependent envelope")
    invalid, unresolved = theory_status(r)
    excluded += invalid
    pending += [reason for reason in unresolved if reason not in pending]
    status = "excluded" if excluded else "pending" if pending else "viable"
    c = Crossing(point=p, status=status, excluded_by=excluded, pending=pending, flags=r.flags + metastable_flag(r),
                 r_combined=r_comb, omega_h2=r.omega_h2, native_constraints=r.native_constraints,
                 statistical_limits=r.statistical_limits, evaluation=r)
    return _over_region(c, r, likelihood) if r.halo is not None else c


def _sample_status(r: PointResult, s, base_excluded: list[str], base_pending: list[str],
                   likelihood: LikelihoodSettings | None) -> tuple[str, list[str], list[str]]:
    """(status, excluded by, pending) at one halo: the halo-dependent constraints there, everything else as at the
    centre. In likelihood mode the combination takes the halo-dependent ratios whose limit was computed by a full
    procedure, direct detection's with the statistical construction of the limit deciding at this halo (PX-04); a
    count ratio's comparison is a cut (the owner's condition 6). A sample saved without that construction (an
    older result) keeps direct detection as a cut, and says so."""
    halo = set(halo_region.HALO_CONSTRAINTS)
    excluded = list(base_excluded)
    unsaved = []
    bad = unfinite({k: o.ratio for k, o in s.outcomes.items() if o.ratio is not None}, {})
    if likelihood is None:
        excluded += [k for k, o in s.outcomes.items() if o.excluded and k not in bad]
    else:
        levels = dict(r.ratio_confidence_levels) if r.ratio_confidence_levels else None   # None: a result saved
        sided = dict(r.ratio_sidedness) if r.ratio_sidedness else None                    # before they were
        ratios = {k: v for k, v in r.ratios.items() if k not in halo}
        for k, o in s.outcomes.items():
            if o.ratio is None or not o.exact:
                continue
            if k == "direct detection":
                if o.confidence_level is None:
                    unsaved.append(k)
                    continue
                if levels is not None:
                    levels[k] = o.confidence_level
                if sided is not None:
                    sided[k] = o.sidedness or "unknown"
            ratios[k] = o.ratio
        excluded += [k for k, o in s.outcomes.items()
                     if o.excluded and (o.ratio is None or not o.exact or k in unsaved) and k not in bad]
        bad = bad | unfinite(ratios, r.chi2)
        excluded += _combination(ratios, r.chi2, likelihood, levels, sided, bad)[1]
    pending = base_pending + [x for x in s.pending if x not in base_pending]
    pending += [x for x in unfinite_reasons(bad) if x not in pending]
    pending += [f"the combined likelihood at v₀ = {s.v0_km_s:.0f}, v_esc = {s.v_esc_km_s:.0f} km/s leaves out {k}: "
                "its statistical construction there was not saved (an older result); re-run the point" for k in unsaved]
    pending += [f"halo: undecided at v₀ = {s.v0_km_s:.0f}, v_esc = {s.v_esc_km_s:.0f} km/s, ρ₀ = {s.rho_gev_cm3:.3g}: "
                f"{u}" for u in s.unresolved]
    return ("excluded" if excluded else "pending" if pending else "viable"), excluded, pending


def _over_region(c: Crossing, r: PointResult, likelihood: LikelihoodSettings | None) -> Crossing:
    """The point classified over the halo region (``halo_region``): its constraints at every sample, each sample's
    status by the same rule, and the region's label. The centre's classification stays as the nominal. A point
    calculated at a fixed benchmark (``halo_evaluation.at_benchmark``) keeps its own classification, labelled so."""
    h = r.halo
    if h.treatment == "benchmark":            # calculated at one fixed benchmark: its own classification stands
        return c.model_copy(update={"halo": halo_region.AT_BENCHMARK})
    halo = set(halo_region.HALO_CONSTRAINTS)
    base_excluded = [k for k in c.excluded_by if k not in halo and not k.startswith("the combined likelihood")]
    own = set(r.model_pending or ())               # the model's own reasons: no sample recomputes them (AL1-04)
    base_pending = [x for x in c.pending if x not in h.nominal_pending or x in own]
    found = [_sample_status(r, s, base_excluded, base_pending, likelihood) for s in h.samples]
    label = halo_region.over([f[0] for f in found], [bool(s.unresolved or h.unsupported) for s in h.samples])
    n = len(found)
    excluded_at = sum(f[0] == "excluded" for f in found)
    note = f"{excluded_at} of {n} halos excluded" if excluded_at else f"none of {n} halos excluded"
    update = {"halo": label, "nominal_status": c.status,
              "nominal_excluded_by": list(c.excluded_by) if c.status == "excluded" else []}
    if label == halo_region.EXCLUDED:
        every = [k for k in dict.fromkeys(x for f in found for x in f[1]) if all(k in f[1] for f in found)]
        return c.model_copy(update={**update, "status": "excluded", "excluded_by": every or list(
            dict.fromkeys(x for f in found for x in f[1])), "pending": [], "flags": c.flags + [f"halo: {label}"]})
    if label == halo_region.ALLOWED:
        return c.model_copy(update={**update, "status": "viable", "excluded_by": [], "pending": [],
                                    "flags": c.flags + [f"halo: {label} ({h.region})"]})
    if label == halo_region.SAME_PENDING:
        pending = list(dict.fromkeys(x for f in found for x in f[2]))
        return c.model_copy(update={**update, "status": "pending", "excluded_by": [], "pending": pending})
    if label == halo_region.SENSITIVE:
        nominal = f"{c.status}" + (f", by {', '.join(c.excluded_by)}" if c.excluded_by else "")
        reason = f"halo: halo-sensitive over the tested region ({note}; nominal at its centre: {nominal})"
    else:
        reason = "halo: halo coverage incomplete (" + "; ".join(
            h.unsupported or list(dict.fromkeys(u for s in h.samples for u in s.unresolved))[:3]) + ")"
    pending = [reason] + list(dict.fromkeys(x for f in found for x in f[2] if not x.startswith("halo: undecided")))
    return c.model_copy(update={**update, "status": "pending", "excluded_by": [], "pending": pending})


NOT_SAVED = ("the model's own pending reasons: not saved with this evaluation (an older result); re-run the point "
             "to see them")


class _Saved:
    """A saved evaluation's stand-in for its engine: it names what was saved and calls no model."""

    def __init__(self, reasons: list[str]):
        self.reasons = reasons

    def pending(self, p: Point) -> list[str]:
        return list(self.reasons)


def classify_saved(result: ScanResult, r: PointResult, likelihood: LikelihoodSettings | None = None) -> Crossing:
    """``classify`` of a saved evaluation without calling any model (the fresh audit's F19-07: a saved view had
    re-run the engine's ``pending``, which for the generic route recomputes its scattering). The engine's reasons are
    those saved with the evaluation (``PointResult.model_pending``); an older result has none saved, and where the
    scan's engine or its fallback names such reasons the point is pending on their absence (``NOT_SAVED``), never
    recomputed. The engine is read from the saved flag ``scan.engine_for`` sets, never from its domain."""
    fallback = result.request.fallback_class
    generic = fallback is not None and any(f.startswith(GENERIC_FLAG) for f in r.flags)
    if r.model_pending is not None or not hasattr(fallback if generic else result.request.model_class, "pending"):
        return classify(None, r, likelihood)
    return classify(_Saved([NOT_SAVED]), r, likelihood)


def discovered(c: Crossing, discovery) -> Crossing:
    """A classified point with every unresolved discovery requirement that covers it (``ScanRequest.discovery``; the
    stacked audit's S18-03): an allowed point becomes pending, an excluded one stays excluded. Applied to every
    evaluation (grid rows, nominal and shifted-target roots) before any aggregate, so the O(1) certificate, the
    plots and the summaries all see it. Applying it twice changes nothing."""
    if not discovery or c.status == "excluded":
        return c
    extra = [d.text for d in discovery if d.applies(c.point.m_chi, getattr(c.point, "m_med", None))
             and d.text not in c.pending]
    if not extra:
        return c
    return c.model_copy(update={"status": "pending" if c.status == "viable" else c.status,
                                "pending": [*c.pending, *extra]})


@eos_reads.producer                      # its claims bound to the tables as it read them (the auditor's CT recheck, CU-02)
def verdict(result: ScanResult, max_crossings: int = 80, likelihood: LikelihoodSettings | None = None) -> Verdict:
    """The verdict on the scanned region (module docstring); ``likelihood``: the combined mode
    (``likelihood``), on the contour and on the grid points inside the relic band."""
    if max_crossings < 1:
        raise ValueError("max_crossings must be positive")
    target = OMEGA * result.request.relic_fraction
    with halo_region.using(result.request.halo):              # every root over the scan's own halo region
        roots, omitted = _thermal_roots(result, target, max_crossings)
        return _with_discovery(result, _robust(result, _verdict_from_roots(result, roots, omitted, max_crossings,
                                                                           likelihood), max_crossings, likelihood))


DECISIVE = ("viable", "viable_pending", "excluded", "overabundant", "underabundant")


def _engine(result: ScanResult, p: Point):
    """The engine that computes p on this scan: the model class, or its generic fallback outside the class's domain
    (``scan.engine_for``). The external audit's R17-5 (2026-10-17): roots refined by the fallback were judged, and
    regimes looked for, with the typed class alone, so the fallback's roots were lost and its regimes not seen."""
    from adroit.parameter_space.scan import engine_for
    return engine_for(result.request, p)[0]


def _prefetch(engines: list, points: list[Point], unverified: bool) -> list[dict | None]:
    """SModelS on the points, one batch per engine, aligned with ``points``."""
    from adroit.parameter_space.searches import prefetch_lhc
    out: list[dict | None] = [None] * len(points)
    for engine in {id(e): e for e in engines}.values():
        index = [i for i, e in enumerate(engines) if e is engine]
        for i, found in zip(index, prefetch_lhc(engine, [points[i] for i in index], unverified)):
            out[i] = found
    return out


def _regimes(result: ScanResult, nominal: Verdict) -> list[str]:
    """The O(1)-disagreement regimes (``generic_regimes``) at the verdict's contour points and the grid points a
    shifted target reaches (``_reaching``; the re-audit's R18-4, 2026-10-18: a regime reached only by a shifted
    thermal solution had been missed), or at the grid's computed points where it has none, wherever the point's
    engine (``_engine``, the fallback included) is the generic route; [] where none is."""
    from adroit.parameter_space.portals.generic import GenericModel
    from adroit.parameter_space.portals import generic_regimes
    request = result.request
    if not any(isinstance(c, GenericModel) for c in (request.model_class, request.fallback_class)):
        return []
    low, high = (nominal.target * s for s in generic_regimes.TARGET_SCALES)
    points = ([c.point for c in nominal.crossings] + _reaching(result, low, high) if nominal.crossings else
              [r.point for r in result.points if r.omega_h2 is not None and math.isfinite(r.omega_h2)])
    found: list[str] = []
    for p in points:
        cls = _engine(result, p)
        if not isinstance(cls, GenericModel):
            continue
        try:
            here = generic_regimes.regimes(cls, p)
        except (ValueError, RuntimeError, ArithmeticError) as error:      # unknown counts as inside (conservative)
            here = [f"the regime check failed at m_χ = {p.m_chi:.4g} GeV: {error}"]
        found += [f for f in here if f not in found]
    return found


ROBUST = {"viable": ("viable",), "viable_pending": ("viable", "pending"), "excluded": ("excluded",)}
ROBUST_WORD = {"viable": "allowed", "viable_pending": "allowed or pending, none excluded", "excluded": "excluded"}


def _robust(result: ScanResult, nominal: Verdict, max_crossings: int,
            likelihood: LikelihoodSettings | None) -> Verdict:
    """D35 (the external audit's item 17): in a regime where the generic route disagrees with the literature by
    O(1), the verdict is exploratory and says so, and a decisive level stands only if the evaluated grid supports it
    at every relic target in the interval ``generic_regimes.TARGET_SCALES`` (``_beyond``, ``_across``); otherwise it
    is pending. Until the audit of 2026-10-17 (R17-2) agreement at the two ends of the interval was taken for
    agreement across it, which an allowed point inside the interval defeats."""
    from adroit.parameter_space.portals import generic_regimes as gr
    found = _regimes(result, nominal)
    if not found:
        return nominal
    note = f"{gr.QUALIFICATION} ({'; '.join(found)})"
    if nominal.level not in DECISIVE:
        return nominal.model_copy(update={"summary": f"{nominal.summary}; {note}"})
    low, high = (nominal.target * s for s in gr.TARGET_SCALES)
    span = f"Ωh² = {low:.3g}–{high:.3g}"
    check = _beyond if nominal.level in ("overabundant", "underabundant") else _across
    held, why = check(result, nominal, low, high, max_crossings, likelihood)
    if held:
        return nominal.model_copy(update={"summary": f"{nominal.summary}; {nominal.level} on the evaluated grid across "
                                                     f"the disagreement ({span}), at the scan's resolution: {why}; "
                                                     f"{note}"})
    reason = f"{nominal.level} at the nominal target; not established across the O(1) disagreement ({span}): {why}"
    return nominal.model_copy(update={"level": "pending", "summary": f"pending: {reason}; {note}",
                                      "unresolved": nominal.unresolved + [reason],
                                      "rests_on": list(range(len(nominal.crossings))), "rests_on_table_roots": []})


def _beyond(result: ScanResult, nominal: Verdict, low: float, high: float, max_crossings: int,
            likelihood: LikelihoodSettings | None) -> tuple[bool, str]:
    """Over- or underabundance across [low, high]: every computed grid value above ``high`` (below ``low``) is above
    (below) every target in the interval, so the level at that end decides, exactly on the grid."""
    over = nominal.level == "overabundant"
    end = high if over else low
    roots, omitted = _thermal_roots(result, end, max_crossings)
    level = _verdict_from_roots(result, roots, omitted, max_crossings, likelihood, target=end).level
    if level == nominal.level:
        return True, f"every computed grid value is {'above' if over else 'below'} Ωh² = {end:.3g}"
    return False, f"{level} at Ωh² = {end:.3g}"


def _reaching(result: ScanResult, low: float, high: float) -> list[Point]:
    """The grid points a thermal solution at a shifted target in [low, high] can come from, on the evaluated grid
    (R18-4): those with Ωh² inside the interval and both ends of every grid edge whose Ωh² range overlaps it (the
    corners of the cells the shifted contours cross); every computed point where the grid is incomplete."""
    def finite(r: PointResult) -> bool:
        return r.omega_h2 is not None and math.isfinite(r.omega_h2)
    nx, ny = len(result.xs), len(result.ys)
    if len(result.points) != nx * ny:
        return [r.point for r in result.points if finite(r)]
    keep: set[int] = set()
    for k, r in enumerate(result.points):
        if not finite(r):
            continue
        if low <= r.omega_h2 <= high:
            keep.add(k)
        i, j = k % nx, k // nx
        for n in ([k + 1] if i + 1 < nx else []) + ([k + nx] if j + 1 < ny else []):
            s = result.points[n]
            if finite(s) and min(r.omega_h2, s.omega_h2) <= high and max(r.omega_h2, s.omega_h2) >= low:
                keep |= {k, n}
    return [result.points[k].point for k in sorted(keep)]


def _in_band(result: ScanResult, low: float, high: float) -> list[PointResult]:
    return [r for r in result.points if r.omega_h2 is not None and math.isfinite(r.omega_h2)
            and low <= r.omega_h2 <= high]


def _coverage_gaps(result: ScanResult, low: float, high: float) -> list[str]:
    """Why the evaluated grid does not cover the targets in [low, high]: an incomplete grid, a point without Ωh²,
    Ωh² that does not span the interval (some targets then have no thermal solution on the grid), or no point inside
    the band."""
    gaps = []
    if len(result.points) != len(result.xs) * len(result.ys):
        gaps.append("the grid is incomplete")
    good = [r.omega_h2 for r in result.points if r.omega_h2 is not None and math.isfinite(r.omega_h2)
            and r.omega_h2 >= 0]
    if len(good) < len(result.points):
        gaps.append(f"{len(result.points) - len(good)} grid points have no relic calculation")
    if not good or min(good) > low or max(good) < high:
        gaps.append("the grid's Ωh² does not span the interval, so part of it has no thermal solution on the grid")
    elif not _in_band(result, low, high):
        gaps.append("no grid point lies inside the band")
    return gaps


def _where(result: ScanResult, c: Crossing) -> str:
    request = result.request
    coords = ", ".join(f"{a.parameter} = {getattr(c.point, a.parameter):.4g}" for a in (request.x, request.y))
    density = f", Ωh² = {c.omega_h2:.3g}" if c.omega_h2 is not None and math.isfinite(c.omega_h2) else ""
    return f"{coords}{density}"


def _across(result: ScanResult, nominal: Verdict, low: float, high: float, max_crossings: int,
            likelihood: LikelihoodSettings | None) -> tuple[bool, str]:
    """A level on the thermal contour across [low, high] (R17-2). The contours of every target in the interval
    together fill the band low ≤ Ωh² ≤ high, so the level holds on the evaluated grid, at its resolution, only where
    the grid covers the interval (``_coverage_gaps``; the roots at both ends resolved, none left unrefined) and every
    grid point in the band, every root at its ends and every nominal crossing has the level's status (``ROBUST``):
    all excluded for an exclusion; all allowed for viability, which is stronger than needed (different points could
    serve different targets) and accepted as such (the owner, 2026-10-17). The nominal search must be complete as well:
    a failed or budget-omitted nominal root, or any other unresolved item, leaves part of the band unexamined (the
    re-audit's R18-2, 2026-10-18), though one surviving root may still make the nominal level viable."""
    gaps = [f"at the nominal target: {u}" for u in nominal.unresolved] + _coverage_gaps(result, low, high)
    ends: list[Crossing] = []
    for t in () if gaps else (low, high):
        roots, omitted = _thermal_roots(result, t, max_crossings)
        at = _verdict_from_roots(result, roots, omitted, max_crossings, likelihood, target=t)
        gaps += [f"at Ωh² = {t:.3g}: {u}" for u in at.unresolved]
        if not any(c.kind == "contour" for c in at.crossings):
            gaps.append(f"no thermal root resolved at Ωh² = {t:.3g}")
        ends += at.crossings
    if gaps:
        return False, gaps[0] + (f" (and {len(gaps) - 1} more)" if len(gaps) > 1 else "")
    rows = _in_band(result, low, high)
    points = [discovered(classify(_engine(result, r.point), r, likelihood), result.request.discovery)
              for r in rows] + ends + list(nominal.crossings)
    wrong = [c for c in points if c.status not in ROBUST[nominal.level]]
    if wrong:
        tally = ", ".join(f"{n} {s}" for s, n in Counter(c.status or "unevaluated" for c in wrong).items())
        return False, (f"{tally} of the {len(points)} points evaluated in the band (the grid's, the roots at its "
                       f"ends and the nominal crossings), e.g. {wrong[0].status or 'unevaluated'} at "
                       f"{_where(result, wrong[0])}")
    return True, (f"the {len(rows)} grid points in the band, the {len(ends)} roots at its ends and the nominal "
                  f"crossings are all {ROBUST_WORD[nominal.level]}")


def _counts_text(crossings: list[Crossing], level: str) -> str:
    """The headline's counts: certified relic roots apart from the theory band's grid points, which are unrooted
    (release audit minor: the band was counted with the roots)."""
    def tally(group: list[Crossing]) -> str:
        n = {s: sum(c.status == s for c in group) for s in ("viable", "pending", "excluded")}
        return f"{n['viable']} viable, {n['pending']} pending, {n['excluded']} excluded"
    roots = [c for c in crossings if c.kind != "theory_band"]
    band = [c for c in crossings if c.kind == "theory_band"]
    if not band:
        return f" ({tally(roots)})"
    text = f" ({tally(roots)} on the relic contour; theory band, unrooted: {tally(band)})"
    status = {"viable": "viable", "viable_pending": "pending"}.get(level)
    if status and not any(c.status == status for c in roots):
        text += "; this level rests on theory-band points only"
    return text


@eos_reads.producer                      # its claims bound to the tables as it read them (the auditor's CT recheck, CU-02)
def verdict_pair(result: ScanResult, max_crossings: int = 80,
                 likelihood: LikelihoodSettings | None = None, *, coverage: CoverageDiagnostic | None = None,
                 checkpoint: Checkpoint | None = None) -> tuple[Verdict, Verdict | None]:
    """Cuts and optional likelihood views with one refinement of this scan's thermal roots.

    Each view independently evaluates constraints and rechecks the final density.
    Only the shared root search is reused; nothing is cached between scans.
    """
    if max_crossings < 1:
        raise ValueError("max_crossings must be positive")
    with halo_region.using(result.request.halo):              # every root over the scan's own halo region
        return _verdict_pair(result, max_crossings, likelihood, coverage, checkpoint)


def _verdict_pair(result: ScanResult, max_crossings: int, likelihood: LikelihoodSettings | None,
                  coverage: CoverageDiagnostic | None, checkpoint: Checkpoint | None) -> tuple[Verdict, Verdict | None]:
    args = (result, OMEGA * result.request.relic_fraction, max_crossings)
    roots, omitted = _thermal_roots(*args, checkpoint=checkpoint) if checkpoint else _thermal_roots(*args)
    extra = []
    if coverage is not None:
        if coverage.request != result.request or coverage.target != OMEGA * result.request.relic_fraction:
            raise ValueError("Coverage diagnostic differs from this scan's physical inputs")
        roots = roots + [r for r in coverage.root_attempts if not r.converged or not any(old.point == r.point for old in roots)]
        extra = list(coverage.unresolved)
    cuts = _robust(result, _verdict_from_roots(result, roots, omitted, max_crossings, None, extra, checkpoint),
                   max_crossings, None)
    combined_view = _robust(result, _verdict_from_roots(result, roots, omitted, max_crossings, likelihood, extra,
                                                        checkpoint), max_crossings, likelihood) if likelihood else None
    return _with_discovery(result, cuts), _with_discovery(result, combined_view)


def relic_validity_reason(rows: list[PointResult]) -> str:
    """Why Ωh² at these points does not support a verdict: its thermal history is outside the supported one (A06's
    reason, ``PointResult.relic_validity``), or "". Over- or underabundance, and a contour's exclusion, rest on Ωh²
    itself, so such points leave them pending (the external audit of 2026-10-17, R17-4: the no-root branch read only
    missing values, so a scan of A06-pending points was called underabundant). An undecided search does not. A
    result written before the field reads A06's reason from its pending list (``scan.RELIC_PENDING``)."""
    from adroit.parameter_space.scan import RELIC_PENDING
    reasons = [r.relic_validity or [x.removeprefix(RELIC_PENDING) for x in r.pending if x.startswith(RELIC_PENDING)]
               for r in rows]
    invalid = [why for why in reasons if why]
    if not invalid:
        return ""
    return f"{len(invalid)} of {len(rows)} points have Ωh² outside the supported thermal history ({invalid[0][0]})"


def _verdict_from_roots(result: ScanResult, roots: list[ThermalRoot], omitted: int, max_crossings: int,
                        likelihood: LikelihoodSettings | None, extra: list[str] | None = None,
                        checkpoint: Checkpoint | None = None, target: float | None = None) -> Verdict:
    """Classify one view without mutating or reusing another view's output objects (at ``target``, by default the
    request's; the equation of state's band, ``_eos_band``, at the request's target only, and only where the
    equation-of-state policy assesses it: ``certificate.eos_band_assessed``; under the nominal policy each claim's
    band check is ``nominal_eos_check``, nothing waits for the tables, and no table root is searched for)."""
    from adroit.core.certificate import eos_band_assessed, nominal_eos_check
    at_target = target is None
    eos_band = at_target and eos_band_assessed()
    eos_off = (nominal_eos_check() if at_target else
               Check(name="eos_band", state="not_applicable", reason="judged at another target (the O(1) checks)"))
    target = OMEGA * result.request.relic_fraction if target is None else target
    roots = [root.model_copy(deep=True) for root in roots]
    accepted = [r for r in roots if r.converged]
    unresolved = _unresolved(result, roots, omitted, max_crossings, extra)
    band = [r for r in result.points if likelihood is not None and relic_chi2(r.omega_h2, target, likelihood) < BAND_95]
    mode = "likelihood" if likelihood else "cuts"
    missing = _eos_missing() if eos_band else ""
    if missing:                                         # the tables not fetched (PR23-05): nothing decided without them
        unresolved.append(missing)
    added = _eos_new_roots(result, roots, target, likelihood) if eos_band and not missing else []
    if not accepted and not band:
        unresolved += [f"EOS-sensitive: no thermal root with ADROIT's nominal degrees of freedom, but {a.why}"
                       for a in added]
        return _rootless(result, roots, unresolved, omitted, mode, target,
                         [a.root for a in added if a.root is not None])
    crossings = _contour_crossings(result, accepted, likelihood, checkpoint, target, unresolved, eos_band, eos_off)
    if added and not any(c.status == "viable" for c in crossings):
        unresolved += [f"EOS-sensitive: {a.why}, which the nominal verdict lacks" for a in added
                       if a.status != "excluded"]
    if invalid := relic_validity_reason([c.evaluation for c in crossings if c.evaluation is not None]):
        unresolved.append(f"the thermal roots: {invalid}")
    stride = max(1, math.ceil(len(band) / max_crossings))
    for row in band[::stride]:          # nominal grid points: inside the band with each table too, or they wait (D-1)
        c = discovered(classify(_engine(result, row.point), row, likelihood), result.request.discovery)
        c = c.model_copy(update={"kind": "theory_band", "target": target,
                                 "relative_residual": abs(row.omega_h2 / target - 1)})
        membership = _band_membership(result, row, target, likelihood, missing) if eos_band else eos_off
        crossings.append(_certified(result, c, "theory_band_membership", (c.status, list(c.excluded_by)),
                                    [membership]))
    if stride > 1:
        unresolved.append("theory band was sampled; unevaluated band points remain")
    # the roots only a table has, each with its certificate; an excluded headline rests on their exclusion too
    # (the auditor's CO recheck, CR-02, 2026-10-26: their certificates had been reduced to words and record names)
    table_roots = [a.root for a in added if a.root is not None]
    return aggregate(result, crossings, unresolved, likelihood, target, roots, omitted, table_roots)


def aggregate(result: ScanResult, crossings: list[Crossing], unresolved: list[str],
              likelihood: LikelihoodSettings | None, target: float, roots: list[ThermalRoot], omitted: int,
              table_roots: list[Crossing]) -> Verdict:
    """The verdict from its judged points (``headline``'s level and words, what it rests on and what qualifies it):
    one function for a fresh verdict and a reassessed one (``orchestrator.reassess``), so the two never differ."""
    mode = "likelihood" if likelihood else "cuts"
    level, text, rest = headline(crossings, bool(unresolved))
    resting = table_roots if level == "excluded" else []
    support = [support_words(c) for c in [*rest, *resting]]
    text += _counts_text(crossings, level)
    if likelihood:
        text = "combined mode, with separately labelled theory-band points: " + text
    qualifiers = _qualifiers(result, [*rest, *resting])
    if qualifiers:
        text += "; " + "; ".join(qualifiers)
    return Verdict(mode=mode, level=level, summary=text, target=target, crossings=crossings,
                   root_attempts=roots, unresolved=unresolved, omitted_candidates=omitted,
                   support=support, qualifiers=qualifiers, table_roots=table_roots,
                   rests_on=[i for i, c in enumerate(crossings) if any(c is r for r in rest)],
                   rests_on_table_roots=list(range(len(resting))))


HEADLINE_TEXT = {
    "viable": "at least one evaluated thermal solution survives all applicable constraints",
    "viable_pending": "evaluated thermal solutions survive computed constraints; other constraints remain pending",
    "pending": "thermal coverage or root refinement is incomplete; excluded samples do not decide the region",
    "waiting": "every evaluated thermal solution is excluded by its computed constraints, but their certification is "
               "not complete; excluded samples do not decide the region",
    "excluded": "all resolved thermal samples at this scan resolution are excluded; unsampled features are not ruled out"}


def all_found_excluded(crossings: list, level: str) -> bool:
    """Whether a headline at ``level`` is undecided only by its coverage, every thermal solution it found being
    excluded (the owner, 2026-11-23): its words, the report's label and the history badge then lead with that, the
    level staying "pending" (an incomplete coverage does not exclude the region). Read from the stored statuses."""
    return level == "pending" and bool(crossings) and all(getattr(c, "status", "") == "excluded" for c in crossings)


def _found_words(crossings: list[Crossing], level: str) -> str:
    """The headline's words where every thermal solution found is excluded (``all_found_excluded``), or for an
    excluded level: how many, and each by what where one constraint excludes them all."""
    common = set.intersection(*(set(c.excluded_by) for c in crossings)) if crossings else set()
    by = f", each by {' and '.join(sorted(common))}" if common else ""
    what = (f"all {len(crossings)} nominal thermal-relic crossing{'s' if len(crossings) != 1 else ''} identified in "
            f"this scan {'are' if len(crossings) != 1 else 'is'} excluded{by}")
    if level == "excluded":
        return f"{what}; unsampled features are not ruled out"
    return f"{what}; no surviving thermal solution was found, but the relic-density coverage is incomplete"


def headline(crossings: list[Crossing], unresolved: bool) -> tuple[str, str, list[Crossing]]:
    """(level, its words, the claims it rests on) from judged points (M1's headline reducer): viable where a certified
    point survives everything; viable pending where a point waits but survives its computed constraints (a waiting
    point is judged by the status those gave, ``survives``: the owner's direction D-2); pending where everything left
    waits while excluded by its computed constraints, or coverage is incomplete; excluded where every point is
    certified excluded and nothing is unresolved."""
    viable = [c for c in crossings if c.status == "viable"]
    waiting = [c for c in crossings if c.status == "pending"]
    survivors = [c for c in waiting if survives(c.status, c.certificate)]
    if viable:
        level, rest = "viable", viable
    elif survivors:
        level, rest = "viable_pending", survivors
    elif waiting or unresolved or not crossings:
        level, rest = "pending", waiting
    else:
        level, rest = "excluded", crossings
    words = HEADLINE_TEXT["waiting" if level == "pending" and waiting else level]
    if level == "excluded" or all_found_excluded(crossings, level):      # what was found, first (2026-11-23)
        words = _found_words(crossings, level)
    return level, words, rest


def resting(crossings: list[Crossing], level: str) -> list[int]:
    """Which of ``crossings`` a headline at ``level`` rests on, by position (``headline``'s rule): a viable one on its
    viable points, a viable-pending one on the waiting points that survive their computed constraints, an excluded
    one on every point, a pending one on those waiting."""
    def chosen(c: Crossing) -> bool:
        if level == "viable":
            return c.status == "viable"
        if level == "viable_pending":
            return c.status == "pending" and survives(c.status, c.certificate)
        return level == "excluded" or c.status == "pending"
    return [i for i, c in enumerate(crossings) if chosen(c)]


def support_words(c: Crossing) -> str:
    """One claim a headline rests on: its kind, where, its status, and the computed status where the gate changed it."""
    where = ", ".join(f"{k} = {v:.4g}" for k, v in c.point.model_dump().items() if v)
    computed = (f" (computed: {c.certificate.computed_status})" if c.certificate is not None
                and c.certificate.computed_status != c.status else "")
    return f"{c.kind} at {where}: {c.status}{computed}"


def _qualifiers(result: ScanResult, support: list[Crossing]) -> list[str]:
    """D-4 on the headline: the claims it rests on that depend on unverified records, apart from the run's setting.
    A certified claim's records are its certificate's (its own constraints' and its supporting table roots':
    the auditor's consolidation audit, CO-03, 2026-10-25); a table's added root an excluded headline rests on is one of
    those claims (CR-02, 2026-10-26)."""
    used = sorted({*(r for c in support for r in (c.certificate.bound.unverified_records
                                                       if c.certificate is not None else
                                                       c.evaluation.unverified_records if c.evaluation is not None
                                                       else []))})
    if used:
        return [f"this conclusion depends on unverified records: {', '.join(used)}"]
    return ["unverified records enabled for this run (this conclusion uses none)"] if result.request.unverified_records else []


def _unresolved(result: ScanResult, roots: list[ThermalRoot], omitted: int, max_crossings: int,
                extra: list[str] | None) -> list[str]:
    """What leaves a view unresolved before any constraint is evaluated (``_verdict_from_roots``)."""
    unresolved = [r.reason for r in roots if not r.converged] + (extra or [])
    if len(result.points) != len(result.xs) * len(result.ys):
        unresolved.append("incomplete grid: point count does not match the axes")
    missing = sum(r.omega_h2 is None or not math.isfinite(r.omega_h2) or r.omega_h2 < 0
                  for r in result.points)
    if missing:
        unresolved.append(f"{missing} grid points have unavailable/invalid relic calculations")
    if omitted:
        unresolved.append(f"{omitted} candidate brackets/endpoints not refined (max_crossings={max_crossings})")
    if invalid := relic_validity_reason(result.points):
        unresolved.append(invalid)
    return unresolved


def _rootless(result: ScanResult, roots: list[ThermalRoot], unresolved: list[str], omitted: int, mode: str,
              target: float, table_roots: list[Crossing] | None = None) -> Verdict:
    """A view with no thermal root and no band point: over- or underabundant throughout, or pending. The roots only a
    table has (``table_roots``, each with its certificate) are kept as evidence the level rests on none of (the auditor's CR
    recheck, CS-03, 2026-10-27: this return had dropped them, only their words surviving in ``unresolved``)."""
    from adroit.parameter_space.certification import relic_target
    waits, rests = relic_target(result.request.unverified_records)     # AL2-06: the target's record, as a root's
    unresolved = [*unresolved, waits] if waits else unresolved
    values = [r.omega_h2 for r in result.points if r.omega_h2 is not None and math.isfinite(r.omega_h2)]
    over = values and all(v > target for v in values)
    under = values and all(v < target for v in values)
    level = "overabundant" if over and not unresolved else "underabundant" if under and not unresolved else "pending"
    text = (f"all {len(values)} computed grid samples are {'above' if over else 'below'} the target; "
            "no thermal root resolved at this scan resolution (features between samples are not ruled out)"
            if level != "pending" else "no certified thermal solution; relic coverage/refinement remains pending")
    qualifiers = [f"this conclusion depends on unverified records: {', '.join(rests)}"] if rests and level != "pending" else []
    if qualifiers:
        text += "; " + "; ".join(qualifiers)
    return Verdict(mode=mode, level=level, summary=text, target=target, root_attempts=roots,
                   unresolved=unresolved, omitted_candidates=omitted, table_roots=list(table_roots or []),
                   qualifiers=qualifiers, **({"rests_on": [], "rests_on_table_roots": []} if table_roots else {}))


def _contour_crossings(result: ScanResult, accepted: list[ThermalRoot], likelihood: LikelihoodSettings | None,
                       checkpoint: Checkpoint | None, target: float, unresolved: list[str],
                       eos_band: bool = False, eos_off: Check | None = None) -> list[Crossing]:
    """Each certified root judged against the constraints (resumed from ``checkpoint``), kept where its Ω still
    meets the target; a root whose Ω moved is added to ``unresolved``; with ``eos_band``, a decided one judged again
    at the equation of state's edges (``_eos_band``); else its band check is ``eos_off``."""
    points = [r.point for r in accepted]
    engines = [_engine(result, p) for p in points]                 # the fallback's roots by the fallback (R17-5)
    lhc_results = _prefetch(engines, points, result.request.unverified_records)
    crossings = []
    for index, (root, lhc, cls) in enumerate(zip(accepted, lhc_results, engines)):
        phase = "likelihood-points" if likelihood else "cuts-points"
        c = checkpoint.load(phase, str(index), Crossing) if checkpoint else None
        if c is None:
            c = (judge_point(cls,root.point,result.request.unverified_records,likelihood,lhc,result.request.private_limits,result.request.private_searches)
                 if result.request.private_searches else judge_point(cls,root.point,result.request.unverified_records,likelihood,lhc,result.request.private_limits)
                 if result.request.private_limits else judge_point(cls,root.point,result.request.unverified_records,likelihood,lhc))
            if checkpoint:
                checkpoint.save(phase, str(index), c)
        elif c.point != root.point:
            raise CheckpointMismatch("Cached contour point differs from its certified root")
        c = discovered(c, result.request.discovery)
        if checkpoint:
            checkpoint.update(phase, index + 1, len(accepted), "certified roots checked against constraints")
        # Constraints re-evaluate Ω: do not accept a stale/unstable root certificate.
        residual = _final_residual(c, target)
        if residual > FINAL_RESIDUAL:
            unresolved.append("relic root changed or was unavailable when constraints were evaluated")
            continue
        computed = (c.status, list(c.excluded_by))
        eos = eos_off or Check(name="eos_band", state="not_applicable",
                               reason="judged at another target (the O(1) checks)")
        if eos_band:
            c, eos = _eos_checked(result, root, c, index, likelihood, checkpoint, target)
        c = c.model_copy(update={"target": target, "relative_residual": residual, "converged": True, "kind": "contour"})
        crossings.append(_certified(result, c, "thermal_solution", computed, [
            Check(name="root", state="satisfied", reason=f"refined in its cell; its own Ωh² within "
                                                         f"{FINAL_RESIDUAL:.0%} of the target when judged"), eos]))
    return crossings


def _certified(result: ScanResult, c: Crossing, kind: str, computed: tuple[str, list[str]],
               checks: list[Check], table: str = "") -> Crossing:
    """``c`` with its claim's certificate (``certification.certify``), the request's records setting and discovery
    applied, bound to the tables where its band across them is checked, or to ``table``, a table's own root's."""
    from adroit.parameter_space import certification
    return certification.certify(c, kind, f"{kind.replace('_', ' ')} at {_where(result, c)}", checks,
                                 enabled=result.request.unverified_records, discovery=result.request.discovery,
                                 computed=computed, eos=(table,) if table else None)


EOS_VARIANTS = ("upper", "lower")      # Saikawa & Shirai's 2020 band (``relic.EOS_TABLES``): the owner's decision #3


def _eos_missing() -> str:
    """Why the equation of state's band is not computed: its tables not fetched (the release audit's PR23-05,
    2026-10-23: they are no longer shipped), or one unreadable or not as published (CA-01; ``relic.eos_unavailable``),
    or "". A crossing then decides nothing."""
    from adroit.constraints import relic
    return relic.band_unavailable()


def _awaiting_eos(c: Crossing, missing: str) -> Crossing:
    """A decided crossing (viable or excluded) pending with ``missing`` (``_eos_missing``), as is, where ``missing`` is
    empty or the crossing is undecided. Applied to the contour's roots (``_eos_band``) and to the combined mode's
    theory-band points, nominal grid points (the combined audit's V1-01, 2026-10-24: without the tables they had
    decided the combined headline viable)."""
    if not missing or c.status not in ("viable", "excluded"):
        return c
    return c.model_copy(update={"status": "pending", "excluded_by": [], "pending": c.pending + [missing]})


FINAL_RESIDUAL = 0.01                  # a judged root's own Ωh², evaluated again with the constraints, meets the target


def _final_residual(c: Crossing, target: float) -> float:
    """|Ωh²/target − 1| of a judged root's own density (the constraints evaluate it again); ∞ where unavailable."""
    value = c.omega_h2
    return abs(value / target - 1) if value is not None and math.isfinite(value) else math.inf


def _recertified(c: Crossing, what: str, target: float) -> Crossing:
    """A table's judged root as it is while its own Ωh² still meets the target within ``FINAL_RESIDUAL``, as the
    nominal root's (``_contour_crossings``); else pending, with the reason. The RV22 audit's RX22-05 (2026-10-22): a
    shifted root whose density moved when the constraints were evaluated had supported a decided band. Applied to a
    root read from a checkpoint as to a fresh one."""
    if c.status == "pending" or _final_residual(c, target) <= FINAL_RESIDUAL:
        return c
    shown = f"{c.omega_h2:.4g}" if c.omega_h2 is not None and math.isfinite(c.omega_h2) else "unavailable"
    return Crossing(point=c.point, status="pending", omega_h2=c.omega_h2, evaluation=c.evaluation, pending=[
        f"{what} changed or was unavailable when constraints were evaluated (Ωh² = {shown}, target {target:.4g})"])


def _judged(result: ScanResult, cls, p: Point, likelihood: LikelihoodSettings | None, lhc=None) -> Crossing:
    """``judge_point`` with the request's records and private constraints."""
    request = result.request
    if request.private_searches:
        return judge_point(cls, p, request.unverified_records, likelihood, lhc, request.private_limits,
                           request.private_searches)
    if request.private_limits:
        return judge_point(cls, p, request.unverified_records, likelihood, lhc, request.private_limits)
    return judge_point(cls, p, request.unverified_records, likelihood, lhc)


def _elementary(result: ScanResult, c: Crossing, what: str, target: float, table: str) -> Crossing:
    """A table's root (a nominal root refound with a table, or a root only a table has; fresh or read from a
    checkpoint) certified as a thermal solution at its own parameters before it supports or decides anything (the auditor's
    consolidation audit, CO-01, 2026-10-25: a shifted root whose own relic calculation was outside the supported
    thermal history had certified a viable nominal root): its refined root, and from its own evaluation its thermal
    history, finite comparisons, records, discovery and halo, gated as any claim (``certification.certify``). The
    band across the tables is the nominal root's claim, not its own: no recursion. It is bound to its own table
    (``table``; the auditor's CO recheck, CR-01, 2026-10-26)."""
    root_ok = c.evaluation is not None and _final_residual(c, target) <= FINAL_RESIDUAL
    root = Check(name="root", state="satisfied" if root_ok else "unknown",
                 reason=f"{what}: refined in its cell; its own Ωh² within {FINAL_RESIDUAL:.0%} of the target when judged"
                 if root_ok else f"{what}: not a refined root judged at the target")
    band = Check(name="eos_band", state="not_applicable",
                 reason="a table's own root: the band across the tables is the nominal root's claim")
    return _certified(result, c.model_copy(update={"certificate": None}), "thermal_solution",
                      (c.status, list(c.excluded_by)), [root, band], table=table)


def _variant_open(v: Crossing) -> str:
    """How a table's certified root leaves the band: "" where it is decided; "failed" where a prerequisite was shown
    not to hold (a thermal history outside the supported one) and nothing is merely unknown; else "unknown"."""
    if v.status in ("viable", "excluded"):
        return ""
    states = [x.state for x in v.certificate.checks] if v.certificate is not None else []
    return "failed" if "failed" in states and "unknown" not in states else "unknown"


def _eos_root(result: ScanResult, root: ThermalRoot, name: str, target: float,
              likelihood: LikelihoodSettings | None) -> Crossing:
    """The root refound on its grid bracket with the table ``name`` and judged there, inside the table
    (``relic.eos_variant``: the point's Ωh² and everything that reads it); pending, with the reason, where the bracket
    holds no root of that table."""
    from adroit.constraints import relic
    a, b = root.bracket
    with relic.eos_variant(name):
        again = refine(lambda t: _bracket_point(result.request, a, b, t), lambda p: _grid_omega(result.request, p),
                       target, high=0 if a == b else 1)
        if not again.converged:
            return Crossing(point=root.point, status="pending", pending=[
                f"the root with the equation of state's {name} table is not in its grid cell ({again.reason})"])
        return discovered(_judged(result, _engine(result, again.point), again.point, likelihood),
                          result.request.discovery)


EOS_SHIFT_BOUND = 0.10     # declared: a supplied table moves Ωh² by at most this (the 256 crossings: −5.5% to +6.5%)


class Added(NamedTuple):
    """A thermal root a supplied table has where the nominal degrees of freedom have none (``_eos_new_roots``): what
    and where, its status there, the unverified records it used, and the root itself with its certificate (None
    where no root was certified: a search incomplete, a root unresolved)."""
    why: str
    status: str
    records: list[str]
    root: Crossing | None = None


def _eos_new_roots(result: ScanResult, roots: list[ThermalRoot], target: float,
                   likelihood: LikelihoodSettings | None) -> list[Added]:
    """The thermal roots a supplied table has where the nominal degrees of freedom have none (the recheck's RB20-07,
    2026-10-20: a variation can create a branch), each an ``Added``, the root kept with its certificate (CR-02). The
    grid edges searched are those holding no nominal root whose Ωh² range meets the targets a table within
    ``EOS_SHIFT_BOUND`` can move onto the target; on each, Ωh² is solved with each table at both ends, and a bracketed root refined and judged
    inside it, then certified at its own parameters (``_elementary``, CO-01): its status is its certified one, and
    the unverified records it used come with it (CO-03). A table moving Ωh² beyond the bound at a searched end is
    itself reported, the search being then incomplete."""
    from adroit.constraints import relic
    nominal = {tuple(r.bracket) for r in roots if r.bracket is not None} | set(_root_candidates(result, target))
    low, high = target / (1 + EOS_SHIFT_BOUND), target / (1 - EOS_SHIFT_BOUND)
    found, missing, seen = [], dict.fromkeys(EOS_VARIANTS, 0), set()
    for a, b in _grid_edges(result):
        values = [_grid_value(result, a), _grid_value(result, b)]
        if (a, b) in nominal or None in values or max(values) < low or min(values) > high:
            continue
        for name in EOS_VARIANTS:
            with relic.eos_variant(name):
                shifted = [_grid_omega(result.request, _bracket_point(result.request, a, b, t)) for t in (0, 1)]
                if None in shifted or not all(math.isfinite(v) and v > 0 for v in shifted):
                    missing[name] += 1                  # reported, not skipped (RX22-03)
                    continue
                moved = max(abs(v / w - 1) for v, w in zip(shifted, values) if w > 0)
                if moved > EOS_SHIFT_BOUND:
                    found.append(Added(f"the {name} table moves Ωh² by {moved:.1%}, beyond the declared bound of "
                                       f"{EOS_SHIFT_BOUND:.0%}: the search for its roots is incomplete", "pending", []))
                if (shifted[0] - target) * (shifted[1] - target) > 0:     # a root at an end is a root (RX22-03)
                    continue
                root = refine(lambda t: _bracket_point(result.request, a, b, t),
                              lambda p: _grid_omega(result.request, p), target)
                if not root.converged:
                    found.append(Added(f"the {name} table has a root it does not resolve between grid points "
                                       f"{a} and {b} ({root.reason})", "pending", []))
                    continue
                key = (name,) + tuple(f"{getattr(root.point, axis.parameter):.10g}"
                                      for axis in (result.request.x, result.request.y))
                if key in seen:                         # a root on a grid node: once, from its first edge
                    continue
                seen.add(key)
                c = discovered(_judged(result, _engine(result, root.point), root.point, likelihood),
                               result.request.discovery)
                if _final_residual(c, target) > FINAL_RESIDUAL:
                    found.append(Added(_recertified(c, f"the {name} table's root at {_where(result, c)}", target)
                                       .pending[0], "pending", []))
                    continue
                c = _elementary(result, c, f"the {name} table's root", target, name)
                why = f" ({c.pending[-1]})" if c.status == "pending" and c.pending else ""
                found.append(Added(f"the {name} table has a thermal root at {_where(result, c)} ({c.status} "
                                   f"there{why})", c.status, list(c.certificate.bound.unverified_records), c))
    found += [Added(f"the {name} table's Ωh² could not be computed at the ends of {n} grid "
                    f"edge{'s' if n > 1 else ''}: the search for its roots is incomplete", "pending", [])
              for name, n in missing.items() if n]
    return found


def _grid_edges(result: ScanResult) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Every pair of neighbouring grid points, (x, y) each; none where the grid is incomplete."""
    nx, ny = len(result.xs), len(result.ys)
    if len(result.points) != nx * ny:
        return []
    out = []
    for j in range(ny):
        for i in range(nx):
            for ii, jj in ((i + 1, j), (i, j + 1)):
                if ii < nx and jj < ny:
                    out.append(((result.xs[i], result.ys[j]), (result.xs[ii], result.ys[jj])))
    return out


def _grid_value(result: ScanResult, xy: tuple[float, float]) -> float | None:
    """The grid's Ωh² at a grid point (x, y), None where it was not computed."""
    i, j = result.xs.index(xy[0]), result.ys.index(xy[1])
    value = result.points[j * len(result.xs) + i].omega_h2
    return value if value is not None and math.isfinite(value) and value >= 0 else None


def _eos_band(result: ScanResult, root: ThermalRoot, c: Crossing, index: int, likelihood: LikelihoodSettings | None,
              checkpoint: Checkpoint | None, target: float) -> Crossing:
    """``_eos_checked``'s crossing."""
    return _eos_checked(result, root, c, index, likelihood, checkpoint, target)[0]


def _eos_checked(result: ScanResult, root: ThermalRoot, c: Crossing, index: int,
                 likelihood: LikelihoodSettings | None, checkpoint: Checkpoint | None,
                 target: float) -> tuple[Crossing, Check]:
    """The owner's decision #3 (2026-10-20): a decided crossing judged again at its root refound with the upper and
    lower edges of Saikawa & Shirai's 2020 equation of state, on the same grid bracket (``_eos_root``). The same status
    at all three: it stands, the band noted among its flags. Else it is pending, "EOS-sensitive", with the three
    statuses and the constraints that differ. The solver's tolerance (``thermal.refine``) and Planck's uncertainty
    (the likelihood mode) stay separate. Every root this verdict judges is refined now, with its cell (the plane's by
    ``_thermal_roots``, the coverage diagnostic's by ``coverage._roots``); a decided one without it is pending, the
    band not computable, never decided on the nominal alone (the consistency audit's CA-01, 2026-10-24: the coverage
    diagnostic's roots, without cells, had been left as they were, viable without the tables). Each table's root is
    certified at its own parameters before it is compared (``_elementary``; the auditor's consolidation audit, CO-01,
    2026-10-25), fresh or read from a checkpoint, so its own thermal history, records, discovery and halo count; the
    band, where it holds, carries the unverified records the tables' roots used (CO-03)."""
    if c.status not in ("viable", "excluded"):
        return c, Check(name="eos_band", state="unknown", reason="not computed: the point is undecided by its "
                                                                     "constraints")
    if missing := _eos_missing():
        return _awaiting_eos(c, missing), Check(name="eos_band", state="unknown", reason=missing)
    if root.bracket is None:
        why = "the equation of state's band is not computed: this root's grid cell is not recorded"
        return _awaiting_eos(c, why), Check(name="eos_band", state="unknown", reason=why)
    variants = {}
    for name in EOS_VARIANTS:
        phase = f"eos-{name}-{'likelihood' if likelihood else 'cuts'}"
        v = checkpoint.load(phase, str(index), Crossing) if checkpoint else None
        if v is None:
            v = _eos_root(result, root, name, target, likelihood)
            if checkpoint:
                checkpoint.save(phase, str(index), v)
        what = f"the root with the {name} table"
        variants[name] = _elementary(result, _recertified(v, what, target), what, target, name)
    where = "; ".join(f"{name}: {_where(result, v)}" for name, v in variants.items())
    if all(v.status == c.status for v in variants.values()):
        flag = (f"the equation of state's band: {c.status} also at the roots with Saikawa & Shirai's upper and lower "
                f"tables ({where}); the two supplied tables, not every equation of state between them")
        return c.model_copy(update={"flags": c.flags + [flag]}), Check(name="eos_band", state="satisfied",
                                                                        reason=flag, **_roots_records(variants))
    differ = sorted({x for v in variants.values() for x in set(v.excluded_by) ^ set(c.excluded_by)})
    reasons = [p for v in variants.values() if v.status == "pending" for p in v.pending[:1]]   # a gated root's too
    reason = (f"EOS-sensitive: {c.status} at the nominal root, "
              + ", ".join(f"{v.status} at the root with the {name} table" for name, v in variants.items())
              + f" ({where})" + (f"; deciding: {', '.join(differ)}" if differ else "")
              + (f"; {reasons[0]}" if reasons else ""))
    opened = [_variant_open(v) for v in variants.values()]
    state = "unknown" if "unknown" in opened else "failed"
    return (c.model_copy(update={"status": "pending", "excluded_by": [], "pending": c.pending + [reason]}),
            Check(name="eos_band", state=state, reason=reason, **_roots_records(variants)))       # CT-03


def _roots_records(variants: dict) -> dict:
    """The records the tables' roots used, which the band's check carries whether it holds or not: the unverified ones
    (``records``, CO-03), and every one with the version used (``evidence_records``, CS-02, CT-01; the auditor's CS
    recheck, CT-03, 2026-10-28: a failed band had dropped the record that made it fail)."""
    from adroit.parameter_space.certification import versions_used
    held = [v.certificate for v in variants.values() if v.certificate is not None]
    return {"records": sorted({r for x in held for r in x.bound.unverified_records}),
            "evidence_records": versions_used(*(x.bound.records for x in held))}


def _band_membership(result: ScanResult, row: PointResult, target: float, likelihood: LikelihoodSettings | None,
                     missing: str) -> Check:
    """The owner's direction D-1 (2026-10-25): a theory-band point, a nominal grid point inside the combined mode's
    relic band, is a band point across the equation of state's band only where its Ωh², at its own parameters, is
    inside the band with each of Saikawa & Shirai's tables too (χ²_Ω < 3.84 with the declared theory uncertainty).
    Its status is not judged again with each table: no constraint at a point reads its computed Ωh² (the rates use
    the declared density), only the thermal-history check, which stays at the nominal. A point a table moves onto
    the target elsewhere is a different point, that table's added root (``_eos_new_roots``)."""
    if missing:
        return Check(name="eos_band", state="unknown", reason=missing)
    from adroit.constraints import relic
    settings = likelihood or LikelihoodSettings()
    values = relic.band_values(lambda: _grid_omega(result.request, row.point))
    shown = ", ".join(f"{v:.4g} with the {name} table" if v is not None else f"not computed with the {name} table"
                      for name, v in values.items())
    if any(v is None for v in values.values()):
        return Check(name="eos_band", state="unknown", reason=f"the band point's Ωh² across the equation of state's "
                                                              f"band ({shown})")
    outside = [name for name, v in values.items() if relic_chi2(v, target, settings) >= BAND_95]
    if outside:
        return Check(name="eos_band", state="failed", reason=(
            f"EOS-sensitive: inside the relic band with the nominal degrees of freedom (Ωh² = {row.omega_h2:.4g}), "
            f"outside it with the {' and '.join(outside)} table{'s' if len(outside) > 1 else ''} (Ωh² = {shown})"))
    return Check(name="eos_band", state="satisfied", reason=f"inside the relic band with Saikawa & Shirai's upper and "
                                                            f"lower tables too (Ωh² = {shown})")

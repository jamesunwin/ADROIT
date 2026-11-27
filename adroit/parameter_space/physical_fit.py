"""Bounded one-parameter physical likelihood fits, distinct from NR inversion.

Every trial evaluates the model's actual detector spectrum. Finite grids and
refinement describe coverage at a declared resolution, not a proof that all
arbitrarily narrow modes were found. Incomplete calculations remain pending.
"""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np
from pydantic import Field
from scipy.optimize import brentq, minimize_scalar
from scipy.special import ndtri

from adroit.core.model_spec import PhysicalFitRange
from adroit.core.state import StrictModel
from adroit.experiments.base import ExperimentModule
from adroit.inference import signal_fit
from adroit.parameter_space.classes import Point
from adroit.parameter_space.fit_inversion import tied
from adroit.physics.haxton import ResponsesUnavailable


class FitSettings(StrictModel):
    """Resolution and hard cap on distinct physical-spectrum evaluations."""

    grid: int = Field(default=33, ge=9, le=129)
    max_evaluations: int = Field(default=512, ge=5, le=5000)
    coordinate_tolerance: float = Field(default=1e-8, gt=0, le=1e-3)
    log_l_tolerance: float = Field(default=1e-5, gt=0, le=0.01)


class FitTrial(StrictModel):
    """Actual prediction and profiled log likelihood at one physical point."""

    point: Point
    log_l: float
    signal_events: float
    densities_at_events: list[float]


class LikelihoodRegion(StrictModel):
    """One connected likelihood-ratio region, possibly truncated by bounds."""

    low: float
    high: float
    low_at_bound: bool = False
    high_at_bound: bool = False


class PhysicalFit(StrictModel):
    """A checked constrained maximum, coverage and likelihood-region metadata."""

    bounds: PhysicalFitRange
    settings: FitSettings
    point: Point | None = None
    log_l: float | None = None
    reference_log_l: float | None = None
    delta_log_l_vs_reference: float | None = None
    null_log_l: float | None = None
    signal_events: float | None = None
    q0: float | None = None
    at_boundary: bool = False
    resolved: bool = False
    identifiable: bool = False
    evaluations: int = 0
    modes: list[Point] = Field(default_factory=list)
    regions: list[LikelihoodRegion] = Field(default_factory=list)
    region_threshold: float = float(ndtri(0.84) ** 2)
    invalid: dict[str, str] = Field(default_factory=dict)
    reason: str = ""
    construction: str = (
        "profiled physical g_chi likelihood at fixed masses/other couplings; "
        "nominal one-parameter 68% likelihood-ratio regions, not calibrated boundary coverage; "
        "q0 is descriptive, not a recalibrated discovery significance"
    )
    # a model with no free coupling (``standard_binding.free_coupling``): its prediction at its own couplings, no fit
    fixed: bool = Field(default=False, exclude_if=lambda v: not v)


FIXED_CONSTRUCTION = ("the model has no free coupling (only gauge interactions): its prediction at its own couplings, "
                      "the background profiled; nothing is fitted and there is no likelihood region in a coupling")


def fixed_prediction(cls: Any, point: Point, module: ExperimentModule, spin: float) -> PhysicalFit:
    """The physical prediction of a model with no free coupling at its own couplings (OB-11): never a fit of a slot
    its engine does not read. Resolved where the prediction can be made, with its reason where not."""
    events, _ = module.observations()
    null = float(signal_fit.profile_log_likelihood(0.0, np.zeros(len(events)), module.background_at(events),
                                                   module.background_rate())[0])
    bounds = PhysicalFitRange.perturbative_branch(point.g_chi)
    try:
        trial = predict(cls, point, module, spin)
    except (ValueError, RuntimeError, ArithmeticError) as error:
        return PhysicalFit(bounds=bounds, settings=FitSettings(), null_log_l=null, evaluations=1, fixed=True,
                           construction=FIXED_CONSTRUCTION, reason=f"no prediction at the model's couplings: {error}")
    if not (math.isfinite(trial.log_l) and math.isfinite(null)):
        return PhysicalFit(bounds=bounds, settings=FitSettings(), null_log_l=null, evaluations=1, fixed=True,
                           construction=FIXED_CONSTRUCTION, reason="the likelihood at the model's couplings is not finite")
    return PhysicalFit(bounds=bounds, settings=FitSettings(), point=trial.point, log_l=trial.log_l, null_log_l=null,
                       signal_events=trial.signal_events, q0=max(0.0, 2 * (trial.log_l - null)), resolved=True,
                       identifiable=True, evaluations=1, modes=[trial.point], fixed=True,
                       construction=FIXED_CONSTRUCTION)


class _Incomplete(ValueError):
    pass


def predict(cls: Any, point: Point, module: ExperimentModule, spin: float) -> FitTrial:
    """Evaluate the real spectrum and the same background profile as Track 2."""
    from adroit.orchestrator.signal import Candidate, _signal

    if hasattr(cls, "domain") and cls.domain(point):
        raise ValueError(cls.domain(point))
    if hasattr(cls, "perturbative"):
        allowed = cls.perturbative(point)
    else:
        allowed = max(abs(point.g_chi), abs(point.g_q), abs(point.g_l)) <= math.sqrt(4 * math.pi)
    if not allowed:
        raise ValueError("outside the model's perturbative domain")
    candidate = Candidate(
        label="bounded physical fit",
        mass_gev=point.m_chi,
        interaction=cls.interaction(point),
        spin=spin,
    )
    signal = _signal(module, candidate)
    density = np.asarray(signal.density)
    if (
        not math.isfinite(signal.total_events)
        or signal.total_events < 0
        or not np.isfinite(density).all()
        or (density < 0).any()
    ):
        raise ValueError("nonfinite or negative physical spectrum")
    events, resolution = module.observations()
    f = signal_fit.event_densities(module.signal_grid_kev(), density, events, resolution)
    seen = signal_fit.seen_events(module.signal_grid_kev(), density, resolution)
    ll = float(
        signal_fit.profile_log_likelihood(
            seen, f, module.background_at(events), module.background_rate()
        )[0]
    )
    if not math.isfinite(ll):
        raise ValueError("nonfinite physical likelihood")
    return FitTrial(point=point, log_l=ll, signal_events=seen, densities_at_events=f.tolist())


def _grid(bounds: PhysicalFitRange, n: int) -> np.ndarray:
    """Linear coordinates plus near-zero probes for weak physical couplings."""
    values = np.linspace(bounds.low, bounds.high, n)
    if bounds.low == 0 < bounds.high:
        values = np.r_[values, bounds.high * np.geomspace(1e-10, 1.0, n)]
    elif bounds.low < 0 == bounds.high:
        values = np.r_[values, bounds.low * np.geomspace(1e-10, 1.0, n)]
    return np.unique(values)


def _maxima(
    grid: np.ndarray, at: Callable[[float], FitTrial | None], tolerance: float
) -> list[FitTrial]:
    """Locate sampled local maxima, including both endpoints, and refine them."""
    trials = [at(float(g)) for g in grid]
    scores = np.array([t.log_l if t else -math.inf for t in trials])
    candidates = [trials[i] for i in (0, len(trials) - 1) if trials[i] is not None]
    finite = scores[np.isfinite(scores)]
    if len(finite) and np.ptp(finite) <= 1e-12:
        return [t for t in trials if t is not None]
    for i, score in enumerate(scores):
        if not math.isfinite(score):
            continue
        left, right = max(0, i - 1), min(len(grid) - 1, i + 1)
        if (
            score >= scores[left]
            and score >= scores[right]
            and right > left
            and (i in (0, len(scores) - 1) or score > scores[left] or score > scores[right])
        ):
            candidates.append(trials[i])
            fit = minimize_scalar(
                lambda g: -(at(float(g)).log_l if at(float(g)) else -math.inf),
                bounds=(grid[left], grid[right]),
                method="bounded",
                options={"xatol": tolerance},
            )
            if not fit.success:
                raise _Incomplete("physical maximum refinement did not converge")
            trial = at(float(fit.x))
            if trial is not None:
                candidates.append(trial)
    return candidates


def _regions(
    grid: np.ndarray,
    at: Callable[[float], FitTrial | None],
    top: float,
    threshold: float,
    bounds: PhysicalFitRange,
) -> list[LikelihoodRegion]:
    """Resolve all sampled connected regions; do not bridge invalid trials."""

    def signed(g: float) -> float:
        trial = at(float(g))
        if trial is None:
            raise _Incomplete("likelihood region meets an invalid physical trial")
        return 2 * (top - trial.log_l) - threshold

    values = [signed(float(g)) for g in grid]
    roots = []
    for a, b, fa, fb in zip(grid[:-1], grid[1:], values[:-1], values[1:], strict=True):
        if fa * fb < 0:
            roots.append(brentq(signed, a, b, xtol=1e-12))
        elif fa == 0:
            roots.append(float(a))
    edges = np.unique([bounds.low, *roots, bounds.high])
    result = []
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        if signed(float((a + b) / 2)) <= 0:
            result.append(
                LikelihoodRegion(
                    low=a, high=b, low_at_bound=a == bounds.low, high_at_bound=b == bounds.high
                )
            )
    if not result:
        raise _Incomplete("no resolved likelihood region around the physical maximum")
    return result


def _solve(
    at: Callable[[float], FitTrial | None],
    bounds: PhysicalFitRange,
    settings: FitSettings,
    null: float,
) -> PhysicalFit:
    first = _grid(bounds, settings.grid)
    coarse = _maxima(first, at, settings.coordinate_tolerance)
    if not coarse:
        raise _Incomplete("no valid physical predictions in the declared range")
    second = np.unique(np.r_[first, (first[1:] + first[:-1]) / 2])
    fine = _maxima(second, at, settings.coordinate_tolerance)
    best = max(fine, key=lambda t: t.log_l)
    if best.log_l - max(coarse, key=lambda t: t.log_l).log_l > settings.log_l_tolerance:
        raise _Incomplete("physical maximum changed at finer resolution; refine the fit grid")
    scores = [at(float(g)).log_l for g in second if at(float(g)) is not None]
    if max(scores) - min(scores) <= settings.log_l_tolerance:
        raise _Incomplete("uninformative/degenerate physical likelihood")
    tied = sorted(
        (t for t in fine if abs(t.log_l - best.log_l) <= 1e-8), key=lambda t: t.point.g_chi
    )
    modes = []
    for t in tied:
        if not modes or abs(t.point.g_chi - modes[-1].g_chi) > 10 * settings.coordinate_tolerance:
            modes.append(t.point)
    grid = np.unique(np.r_[second, [t.point.g_chi for t in fine]])
    regions = _regions(grid, at, best.log_l, float(ndtri(0.84) ** 2), bounds)
    edge = min(abs(best.point.g_chi - bounds.low), abs(best.point.g_chi - bounds.high))
    return PhysicalFit(
        bounds=bounds,
        settings=settings,
        point=best.point,
        log_l=best.log_l,
        null_log_l=null,
        signal_events=best.signal_events,
        q0=max(0.0, 2 * (best.log_l - null)),
        at_boundary=edge <= 10 * settings.coordinate_tolerance,
        resolved=True,
        identifiable=len(modes) == 1,
        modes=modes,
        regions=regions,
        reason="multiple equally good physical modes; thermal branches need separate follow-up"
        if len(modes) > 1
        else "",
    )


def fit(
    cls: Any,
    point: Point,
    module: ExperimentModule,
    spin: float,
    bounds: PhysicalFitRange | None = None,
    settings: FitSettings | None = None,
    ties=(),
) -> PhysicalFit:
    """Fit within declared bounds, retaining failures, boundaries and all sampled regions; the couplings the model ties
    to g_chi (``ties``) follow it (``fit_inversion.tied``; AL3-03)."""
    bounds = bounds or PhysicalFitRange.perturbative_branch(point.g_chi)
    settings = settings or FitSettings()
    events, _ = module.observations()
    null = float(
        signal_fit.profile_log_likelihood(
            0.0, np.zeros(len(events)), module.background_at(events), module.background_rate()
        )[0]
    )
    return fit_trials(point, bounds, settings, null, lambda p: predict(cls, tied(p, ties), module, spin))


def fit_trials(
    point: Point,
    bounds: PhysicalFitRange,
    settings: FitSettings,
    null_log_l: float,
    evaluator: Callable[[Point], FitTrial],
) -> PhysicalFit:
    """The same bounded solver for an explicit physical likelihood evaluator.

    A joint evaluator must predict every component at the same point and
    profile/marginalise nuisances according to its declared source model.
    """
    cache: dict[float, FitTrial | None] = {}
    invalid: dict[str, str] = {}
    evaluations = 0

    def at(g: float) -> FitTrial | None:
        nonlocal evaluations
        if not bounds.low <= g <= bounds.high:
            raise _Incomplete("optimizer requested a point outside declared bounds")
        if g not in cache:
            if evaluations >= settings.max_evaluations:
                raise _Incomplete("physical fit evaluation budget exhausted")
            evaluations += 1
            try:
                cache[g] = evaluator(point.model_copy(update={"g_chi": g}))
            except ResponsesUnavailable:      # an installation the request needs, not an invalid point: refused (F1-01)
                raise
            except (ValueError, RuntimeError, ArithmeticError) as error:
                invalid[repr(g)] = str(error)
                cache[g] = None
        return cache[g]

    null = null_log_l
    if not math.isfinite(null):
        return PhysicalFit(
            bounds=bounds, settings=settings, reason="nonfinite background-only likelihood"
        )
    try:
        result = _solve(at, bounds, settings, null)
        # A fresh prediction independently checks the final maximum.
        if evaluations >= settings.max_evaluations:
            raise _Incomplete("no budget for independent physical fit verification")
        evaluations += 1
        checked = evaluator(result.point)
        if abs(checked.log_l - result.log_l) > settings.log_l_tolerance:
            raise _Incomplete("physical likelihood changed during independent verification")
        if invalid:
            result.resolved = False
            result.reason = "invalid regions leave physical fit coverage partial"
    except ResponsesUnavailable:
        raise
    except (ValueError, RuntimeError, ArithmeticError) as error:
        result = PhysicalFit(bounds=bounds, settings=settings, reason=str(error))
    result.evaluations = evaluations
    result.invalid = invalid
    return result


def fit_domain(*args, **kwargs):
    """Bounded named-parameter solver; see multiparameter_fit for typed diagnostics."""
    from adroit.parameter_space.multiparameter_fit import fit_domain as solve
    return solve(*args, **kwargs)

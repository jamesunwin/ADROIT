"""Finite-resolution bounded physical maxima and profiles, not calibrated regions.

All likelihood trials are direct physical predictions. Coarse/fine searches,
local modes, boundaries and profiles are retained. Resolution is an empirical
check, never a proof of global uniqueness or continuous-domain coverage.
"""
from __future__ import annotations

from itertools import product
import math
from typing import Callable, Sequence

import numpy as np
from pydantic import Field
from scipy.optimize import minimize

from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
from adroit.core.evidence import content_hash
from adroit.core.fit_domain import PhysicalDomain, DomainFitSettings, FitCoordinate
from adroit.core.state import StrictModel
from adroit.parameter_space.classes import Point
from adroit.parameter_space.physical_fit import FitTrial


class DomainMode(StrictModel):
    """One local maximum of the likelihood in a branch: its point, log L, the coordinates whose boundary it sits on,
    and its local rank if interior."""
    branch: str
    point: Point
    log_l: float
    boundaries: list[str] = Field(default_factory=list)
    local_rank: int | None = None


class ProfileValue(StrictModel):
    """One sampled value of a profiled coordinate: the best branch maximum there, its log L and Δlog L below the
    global maximum."""
    value: float
    log_l: float
    point: Point
    branch: str
    delta_log_l: float = 0


class DomainFit(StrictModel):
    """A bounded physical-domain fit: the best point, its log L and q0 against the background-only log L, the modes
    and sampled profiles, and whether it is resolved and identifiable."""
    domain: PhysicalDomain
    reference_point: Point
    settings: DomainFitSettings
    point: Point | None = None
    log_l: float | None = None
    null_log_l: float | None = None
    q0: float | None = None
    signal_events: float | None = None
    resolved: bool = False
    identifiable: bool = False
    modes: list[DomainMode] = Field(default_factory=list)
    profiles: dict[str, list[ProfileValue]] = Field(default_factory=dict)
    evaluations: int = 0
    invalid: dict[str, str] = Field(default_factory=dict)
    reason: str = ""
    construction: str = (
        "bounded shared physical parameters; direct likelihood trials; two grid resolutions "
        "and local refinement; sampled profile diagnostics and local rank, not calibrated "
        "confidence regions or a proof of global uniqueness; q0 descriptive, no discovery p"
    )


class TrialRecord(StrictModel):
    """One saved likelihood trial: the evaluator's ``FitTrial``, or the error that stopped the prediction."""
    trial: FitTrial | None = None
    error: str = ""


class _Incomplete(ValueError):
    pass


class _Trials:
    """Budgeted, cached and checkpointed direct physical trials on the unit cube."""

    def __init__(self, point: Point, domain: PhysicalDomain, settings: DomainFitSettings,
                 evaluator: Callable[[Point], FitTrial], checkpoint: Checkpoint | None,
                 result: DomainFit) -> None:
        self.point, self.domain, self.settings = point, domain, settings
        self.evaluator, self.checkpoint, self.result = evaluator, checkpoint, result
        self.axes = [c for c in domain.coordinates if c.values is None]
        self.cache: dict[str, TrialRecord] = {}

    def physical(self, x: np.ndarray, fixed: dict[str, float]) -> Point:
        """The physical Point at unit-cube coordinates x, after fixed values and relations."""
        values = {**self.point.model_dump(), **self.domain.fixed, **fixed,
                  **{c.parameter: c.value(float(u)) for c, u in zip(self.axes, x, strict=True)}}
        for relation in self.domain.relations:
            values[relation.target] = relation.scale * values[relation.source] + relation.offset
        if any(not math.isfinite(v) for v in values.values()) or min(values['m_chi'], values['m_med']) <= 0:
            raise ValueError("relation produces a nonphysical Point")
        return Point.model_validate(values)

    def _record(self, p: Point, key: str) -> TrialRecord:
        """A saved trial for p if the checkpoint holds one, else a fresh (saved) evaluation."""
        checkpoint = self.checkpoint
        record = checkpoint.load("domain_trials", key, TrialRecord) if checkpoint else None
        if record is not None and record.trial is not None and record.trial.point != p:
            raise CheckpointMismatch("cached physical trial does not match requested Point")
        if record is None:
            try:
                trial = self.evaluator(p)
                if (trial.point != p or not math.isfinite(trial.log_l) or
                    not math.isfinite(trial.signal_events) or trial.signal_events < 0 or
                    any(not math.isfinite(v) or v < 0 for v in trial.densities_at_events)):
                    raise ValueError("invalid evaluator likelihood or mismatched physical Point")
                record = TrialRecord(trial=trial)
            except (ValueError, RuntimeError, ArithmeticError) as error:
                record = TrialRecord(error=str(error))
            if checkpoint:
                checkpoint.save("domain_trials", key, record)
        return record

    def at(self, x: np.ndarray, fixed: dict[str, float]) -> FitTrial | None:
        """The trial at x; failed predictions count against the cap and return None."""
        if any(u < -1e-12 or u > 1 + 1e-12 for u in x):
            raise _Incomplete("optimizer left the declared physical domain")
        p = self.physical(np.clip(x, 0, 1), fixed)
        key = content_hash(p.model_dump(mode="json"))
        result, settings = self.result, self.settings
        if key not in self.cache:
            if result.evaluations >= settings.max_evaluations:
                raise _Incomplete("multiparameter evaluation budget exhausted")
            result.evaluations += 1
            record = self._record(p, key)
            self.cache[key] = record
            if record.error:
                result.invalid[key] = record.error
        if self.checkpoint and result.evaluations % 100 == 0:
            self.checkpoint.update("multiparameter", result.evaluations, settings.max_evaluations,
                                   "direct physical likelihood evaluations")
        return self.cache[key].trial

    def score(self, x: np.ndarray, fixed: dict[str, float]) -> float:
        """log L at x, or -inf for a failed prediction."""
        trial = self.at(x, fixed)
        return trial.log_l if trial is not None else -math.inf

    def verify(self, best: DomainMode) -> float:
        """Signal events from a fresh, uncached evaluation that reproduces the maximum."""
        result, settings = self.result, self.settings
        if result.evaluations >= settings.max_evaluations:
            raise _Incomplete("no budget for fresh maximum verification")
        result.evaluations += 1
        check = self.evaluator(best.point)
        if check.point != best.point or not math.isfinite(check.log_l) or abs(check.log_l-best.log_l) > settings.log_l_tolerance:
            raise _Incomplete("fresh physical maximum verification failed")
        return check.signal_events


def _contexts(domain: PhysicalDomain,
              discrete: list[FitCoordinate]) -> list[tuple[str, dict[str, float]]]:
    """Every explicit branch crossed with every combination of discrete coordinate values."""
    contexts = []
    for branch in domain.branches:
        for values in product(*(c.values for c in discrete)):
            contexts.append((branch.label, {**branch.fixed,
                **dict(zip([c.parameter for c in discrete], values, strict=True))}))
    return contexts


def _expand(y: Sequence[float], frozen: dict[int, float], free: list[int], size: int) -> np.ndarray:
    """Unit-cube coordinates from the frozen axes and the free-axis values y."""
    x = np.zeros(size)
    for i, value in frozen.items():
        x[i] = value
    for i, value in zip(free, y, strict=True):
        x[i] = value
    return x


def _grid_maxima(scores: np.ndarray, n: int, free: list[int]) -> list[np.ndarray]:
    """Sampled local maxima on the free-axis lattice, boundary faces included, plateaus not."""
    candidates = []
    for indices in product(range(n), repeat=len(free)):
        value = scores[indices]
        if not math.isfinite(value):
            continue
        neighbours = []
        for j, index in enumerate(indices):
            for step in (-1, 1):
                if 0 <= index + step < n:
                    other = list(indices)
                    other[j] += step
                    neighbours.append(scores[tuple(other)])
        if neighbours and (value < max(neighbours) or value == min(neighbours) == max(neighbours)):
            continue
        candidates.append(np.array(indices, dtype=float) / (n - 1))
    if not candidates:
        candidates = [np.array(np.unravel_index(np.argmax(scores), scores.shape), dtype=float) / (n - 1)]
    return candidates


def _refine(trials: _Trials, fixed: dict[str, float], y: np.ndarray, n: int, free: list[int],
            expand: Callable[[np.ndarray], np.ndarray]) -> tuple[float, np.ndarray]:
    """Best of the seed, its cell-bounded Powell refinement and a released local simplex."""
    settings = trials.settings
    x = expand(y)
    basin = [(trials.score(x, fixed), x)]
    if free:
        # Adjacent grid cell prevents one basin's refinement swallowing another.
        bounds = [(max(0, u - 1/(n-1)), min(1, u + 1/(n-1))) for u in y]
        opt = minimize(lambda z: -trials.score(expand(z), fixed), y, method="Powell", bounds=bounds,
            options={"xtol": settings.coordinate_tolerance,
                     "ftol": settings.log_l_tolerance * .01, "maxiter": 200})
        if not opt.success:
            raise _Incomplete("multiparameter refinement failed to converge")
        basin.append((trials.score(expand(opt.x), fixed), expand(opt.x)))
        # Release the cell walls with a local simplex method. Otherwise a
        # correlated valley can stop at an artificial grid-cell boundary.
        simplex = np.tile(opt.x,(len(free)+1,1))
        for j in range(len(free)):
            simplex[j+1,j] += -.02 if opt.x[j] > .5 else .02
        local = minimize(lambda z: -trials.score(expand(z), fixed), opt.x,
            method="Nelder-Mead",bounds=[(0.,1.) for _ in free],
            options={"xatol":settings.coordinate_tolerance,
                     "fatol":settings.log_l_tolerance*.001,"maxiter":1000,
                     "initial_simplex":simplex})
        if not local.success:
            raise _Incomplete(f"physical local refinement failed to converge: {local.message}")
        basin.append((trials.score(expand(local.x),fixed),expand(local.x)))
    return max(basin,key=lambda item:item[0])


def _search(trials: _Trials, fixed: dict[str, float], n: int,
            frozen: dict[int, float] | None = None) -> list[tuple[float, np.ndarray]]:
    """Refine every sampled local maximum, including grid boundary faces."""
    settings, size = trials.settings, len(trials.axes)
    frozen = frozen or {}
    free = [i for i in range(size) if i not in frozen]
    if n**len(free) > settings.max_evaluations:
        raise _Incomplete("declared grid exceeds the evaluation cap")
    lattice = list(product(np.linspace(0, 1, n), repeat=len(free)))

    def expand(y: Sequence[float]) -> np.ndarray:
        return _expand(y, frozen, free, size)

    scores = np.array([trials.score(expand(y), fixed) for y in lattice]).reshape((n,) * len(free))
    if trials.result.invalid:
        raise _Incomplete("invalid physical predictions leave domain coverage partial: "
                          + next(iter(trials.result.invalid.values())))
    if not np.isfinite(scores).any():
        raise _Incomplete("no valid physical trial in a branch/profile")
    candidates = _grid_maxima(scores, n, free)
    if len(candidates) > settings.max_modes:
        raise _Incomplete("sampled mode count exceeds the declared mode cap")
    found = [_refine(trials, fixed, y, n, free, expand) for y in candidates]
    # Keep refined modes only; a seed on a slope is not an additional mode.
    modes = []
    for _, x in sorted(found, key=lambda item: -item[0]):
        if any(np.max(abs(x - other), initial=0) <= max(1e-5, 20*settings.coordinate_tolerance)
               for _, other in modes):
            continue
        modes.append((trials.score(x, fixed), x))
    return modes


def _stable_modes(trials: _Trials, fixed: dict[str, float]) -> list[tuple[float, np.ndarray]]:
    """Fine-grid modes, required to agree with the coarse grid in maximum and basins."""
    settings = trials.settings
    coarse = _search(trials, fixed, settings.grid)
    fine = _search(trials, fixed, 2*settings.grid-1)
    if abs(max(v for v, _ in coarse) - max(v for v, _ in fine)) > settings.log_l_tolerance:
        raise _Incomplete("maximum changed at finer resolution; refine the declared grid")
    # Every resolved coarse basin must survive refinement; new fine basins
    # require another explicit grid rather than a silent completeness claim.
    for left, right in ((coarse, fine), (fine, coarse)):
        for value, x in left:
            if not any(abs(value-v) <= settings.log_l_tolerance and
                np.max(abs(x-y), initial=0) <= 2/(2*settings.grid-2)
                for v, y in right):
                raise _Incomplete("local modes changed at finer resolution; refine the declared grid")
    return fine


def _local_rank(trials: _Trials, x: np.ndarray, value: float, fixed: dict[str, float]) -> int:
    """Rank of the finite-difference curvature of log L at an interior mode."""
    score = trials.score
    h = min(1e-3, float(min(np.minimum(x, 1-x))) / 3)
    curvature = np.zeros((len(x), len(x)))
    for i in range(len(x)):
        ei = np.eye(len(x))[i]*h
        curvature[i,i] = -(score(x+ei, fixed)-2*value+score(x-ei, fixed))/h**2
        for j in range(i):
            ej = np.eye(len(x))[j]*h
            curvature[i,j] = curvature[j,i] = -(score(x+ei+ej, fixed)-score(x+ei-ej, fixed)
                -score(x-ei+ej, fixed)+score(x-ei-ej, fixed))/(4*h*h)
    eigen = np.linalg.eigvalsh(curvature)
    return int(np.sum(eigen > max(1e-5, float(max(abs(eigen)))*1e-4)))


def _mode(trials: _Trials, label: str, fixed: dict[str, float], value: float,
          x: np.ndarray) -> DomainMode:
    """A refined mode with its boundary faces and, if interior, its local rank."""
    p = trials.physical(x, fixed)
    boundaries = [c.parameter for c, u in zip(trials.axes, x, strict=True)
                  if min(u, 1-u) <= 20*trials.settings.coordinate_tolerance]
    rank = None
    if trials.axes and not boundaries:
        rank = _local_rank(trials, x, value, fixed)
    return DomainMode(branch=label, point=p, log_l=value, boundaries=boundaries, local_rank=rank)


def _profile(trials: _Trials, coordinate: FitCoordinate,
             contexts: list[tuple[str, dict[str, float]]], best: DomainMode) -> list[ProfileValue]:
    """Sampled profile of one coordinate: the best branch maximum at each value."""
    settings = trials.settings
    i = next((j for j, c in enumerate(trials.axes) if c.parameter == coordinate.parameter), None)
    units = np.linspace(0, 1, settings.profile_grid) if i is not None else coordinate.values
    profile = []
    for unit in units:
        choices = []
        for label, fixed in contexts:
            if i is None and fixed[coordinate.parameter] != unit:
                continue
            frozen = {i: float(unit)} if i is not None else {}
            a = _search(trials, fixed, settings.grid, frozen)
            b = _search(trials, fixed, 2*settings.grid-1, frozen)
            value, x = max(b, key=lambda item: item[0])
            if abs(value-max(v for v, _ in a)) > settings.log_l_tolerance:
                raise _Incomplete("profile changed at finer resolution; refine the declared grid")
            if value > best.log_l + settings.log_l_tolerance:
                raise _Incomplete("profile found a missed maximum; refine the declared grid")
            choices.append(ProfileValue(value=coordinate.value(float(unit)) if i is not None else unit,
                log_l=value, point=trials.physical(x,fixed), branch=label,
                delta_log_l=max(0, best.log_l-value)))
        profile.append(max(choices, key=lambda item: item.log_l))
    return profile


def fit_domain(point: Point, domain: PhysicalDomain, settings: DomainFitSettings,
               null_log_l: float, evaluator: Callable[[Point], FitTrial],
               checkpoint: Checkpoint | None = None) -> DomainFit:
    """Reuse only caller-identity-bound trials through the existing Checkpoint.

    The caller must bind model, domain, data, evaluator implementation and runtime
    in the checkpoint manifest. Failed predictions count against the hard cap.
    A resumed deterministic search counts saved trials in the same total budget.
    """
    result = DomainFit(domain=domain, reference_point=point, settings=settings,
                       null_log_l=null_log_l)
    discrete = [c for c in domain.coordinates if c.values is not None]
    if len(domain.branches)*math.prod(len(c.values) for c in discrete) > settings.max_evaluations:
        result.reason = "discrete branch bank exceeds the evaluation cap"
        return result
    contexts = _contexts(domain, discrete)
    trials = _Trials(point, domain, settings, evaluator, checkpoint, result)
    try:
        if not math.isfinite(null_log_l):
            raise _Incomplete("nonfinite background-only likelihood")
        for label, fixed in contexts:
            for value, x in _stable_modes(trials, fixed):
                result.modes.append(_mode(trials, label, fixed, value, x))
        best = max(result.modes, key=lambda m: m.log_l)
        result.point, result.log_l = best.point, best.log_l
        result.q0 = max(0, 2*(best.log_l-null_log_l))
        for coordinate in domain.coordinates:
            result.profiles[coordinate.parameter] = _profile(trials, coordinate, contexts, best)
        result.signal_events = trials.verify(best)
        result.resolved = not result.invalid
        tied = [m for m in result.modes if best.log_l-m.log_l <= settings.log_l_tolerance]
        flat = any(len(v)>1 and max(p.log_l for p in v)-min(p.log_l for p in v) <= settings.log_l_tolerance
                   for v in result.profiles.values())
        result.identifiable = result.resolved and len(tied)==1 and not flat and (
            best.local_rank is None or best.local_rank==len(trials.axes))
        result.reason = ("invalid trials leave fit coverage partial" if result.invalid else
                         "multiple best modes or locally rank-deficient/flat physical coordinates"
                         if not result.identifiable else "")
    except (ValueError, RuntimeError, ArithmeticError) as error:
        result.resolved = False
        result.identifiable = False
        result.reason = str(error)
    return result

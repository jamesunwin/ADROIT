"""Optional relic-only resolution diagnostic; not an experimental exclusion verdict."""
from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, PrivateAttr, model_validator

from adroit.parameter_space.likelihood import DENSITY
from adroit.core.state import StrictModel
from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
from adroit.parameter_space.classes import Point
from adroit.parameter_space.scan import Axis, ScanRequest, _point_at
from adroit.parameter_space.thermal import ThermalRoot, refine


class CoverageSettings(StrictModel):
    """Resolution and budget of the relic-only diagnostic: uniform refinement depth, or adaptive cell splitting with
    its selection thresholds, under a hard evaluation cap."""
    refinement_depth: int = Field(default=1, ge=1, le=3)
    max_evaluations: int = Field(default=250, ge=1, le=10000)
    strategy: Literal["uniform", "adaptive"] = "uniform"
    exploration_depth: int = Field(default=1, ge=1, le=3)
    near_target: float = Field(default=0.1, gt=0, le=1)
    log_curvature: float = Field(default=0.1, gt=0, le=10)

    @model_validator(mode="after")
    def _depths(self):
        if self.strategy == "adaptive" and self.exploration_depth > self.refinement_depth:
            raise ValueError("Adaptive exploration depth exceeds maximum refinement depth")
        return self


class AdaptiveCell(StrictModel):
    """One adaptive cell: its grid-index bounds (x0, x1, y0, y1), depth, and the decision on refining it with the
    reason."""
    bounds: tuple[int, int, int, int]
    depth: int
    decision: Literal["split", "maximum_depth", "not_selected", "unresolved", "not_sampled"]
    reason: str


class RelicSample(StrictModel):
    """Ωh² at one node (i, j) of the refined grid, or the reason it is unavailable."""
    index: tuple[int, int]
    point: Point
    omega_h2: float | None = None
    reason: str = ""


class CoverageDiagnostic(StrictModel):
    """The relic-only diagnostic of a scan plane: the refined grid, its density samples, the root attempts at the
    thermal target and what remains unresolved; not an exclusion verdict."""
    request: ScanRequest
    settings: CoverageSettings
    target: float
    xs: list[float]
    ys: list[float]
    samples: list[RelicSample]
    root_attempts: list[ThermalRoot]
    evaluations: int
    planned_samples: int
    omitted_candidates: int
    unresolved: list[str]
    status: Literal["sampled_at_requested_resolution", "adaptive_sampling_complete", "partial"]
    cells: list[AdaptiveCell] = Field(default_factory=list)
    interpretation: str = ("Relic-only diagnostic: constraints on these roots are not evaluated. "
                           "Finite probes do not rule out narrower unsampled features.")


def _coordinates(axis: Axis, depth: int) -> list[float]:
    values = axis.values()
    for _ in range(depth):
        refined = []
        for a, b in zip(values[:-1], values[1:]):
            if axis.log and a * b <= 0:
                raise ValueError("Logarithmic coverage refinement requires axis values of one sign")
            refined.extend([a, _coordinate(a, b, 0.5, axis.log)])     # a negative coupling's axis too (G12, L3)
        values = refined + [values[-1]]
    return values


class _Evaluator(StrictModel):
    request: ScanRequest
    maximum: int
    evaluations: int = 0
    _checkpoint: Checkpoint | None = PrivateAttr(default=None)

    def omega(self, point: Point) -> float:
        """Ωh² at the point, counted against the evaluation cap (and checkpointed); ValueError outside the model's
        domain or for an unavailable or nonfinite density."""
        if self.evaluations >= self.maximum:
            raise RuntimeError("coverage evaluation budget exhausted")
        self.evaluations += 1
        if self._checkpoint:
            self._checkpoint.save("coverage-budget", "count", _Budget(evaluations=self.evaluations))
            self._checkpoint.update("coverage", self.evaluations, self.maximum, "relic-search evaluations")
        from adroit.parameter_space.scan import engine_for
        cls, _ = engine_for(self.request, point)       # the grid's engine, the fallback included (G3/G4-5, G12)
        reason = cls.domain(point) if hasattr(cls, "domain") else ""
        if reason:
            raise ValueError(reason)
        value = cls.omega_h2(point)
        if value is None or not math.isfinite(value) or value < 0:
            raise ValueError("relic calculation unavailable/nonfinite")
        return float(value)


class _Budget(StrictModel):
    evaluations: int = Field(ge=0)


def _candidates(samples: list[RelicSample], target: float) -> list[tuple[RelicSample, RelicSample]]:
    known = {sample.index: sample for sample in samples}
    edges = []
    for sample in samples:
        if sample.omega_h2 is None:
            continue
        if abs(sample.omega_h2 / target - 1) < 1e-10:
            edges.append((sample, sample))
        i, j = sample.index
        for key in [(i + 1, j), (i, j + 1)]:
            other = known.get(key)
            if other is not None and other.omega_h2 is not None:
                if (sample.omega_h2 - target) * (other.omega_h2 - target) < 0:
                    edges.append((sample, other))
    return edges


def _coordinate(a: float, b: float, fraction: float, logarithmic: bool) -> float:
    if a == b or fraction == 0:
        return a
    if fraction == 1:
        return b
    return a * (b / a) ** fraction if logarithmic else a + fraction*(b-a)       # geometric, of either sign


def _roots(request: ScanRequest, evaluator: _Evaluator, samples: list[RelicSample], target: float,
           xs: list[float], ys: list[float],
           candidates: list[tuple[RelicSample, RelicSample]] | None = None) -> tuple[list[ThermalRoot], int]:
    candidates = _candidates(samples, target) if candidates is None else candidates
    roots = []
    for index, (a, b) in enumerate(candidates):
        checkpoint = evaluator._checkpoint
        key = f"{a.index[0]}_{a.index[1]}-{b.index[0]}_{b.index[1]}"      # the bracket, not its place in the list
        cached = checkpoint.load("coverage-roots", key, ThermalRoot) if checkpoint else None
        if cached is None and evaluator.evaluations >= evaluator.maximum:
            return roots, len(candidates) - index
        def point_at(t: float) -> Point:
            endpoints = [(xs[a.index[0]], xs[b.index[0]]), (ys[a.index[1]], ys[b.index[1]])]
            values = [_coordinate(u, v, t, axis.log)
                      for (u, v), axis in zip(endpoints, (request.x, request.y))]
            return _point_at(request, *values)
        if cached is not None and (cached.target != target or (cached.point is not None and cached.coordinate is not None
                                                               and cached.point != point_at(cached.coordinate))):
            raise CheckpointMismatch("a cached coverage root is not on its bracket (release audit minor)")
        root = cached or refine(point_at, evaluator.omega, target, high=0 if a.index == b.index else 1)
        if checkpoint and cached is None:
            checkpoint.save("coverage-roots", key, root)
        # its cell, (x, y) at each end, as a plane root carries (``verdict._thermal_roots``), so that the equation of
        # state's band refines it there; a root without one had been taken for a result written before the band and
        # decided on the nominal alone (the consistency audit's CA-01, 2026-10-24)
        root = root.model_copy(update={"bracket": ((xs[a.index[0]], ys[a.index[1]]), (xs[b.index[0]], ys[b.index[1]]))})
        if not root.converged or not any(old.point == root.point for old in roots):
            roots.append(root)
    return roots, 0


def diagnose(request: ScanRequest, settings: CoverageSettings | None = None,
             checkpoint: Checkpoint | None = None) -> CoverageDiagnostic:
    """Probe a finer relic grid and independently certify its bracketed roots.

    Args:
        request: The model, fixed inputs, axes and relations of the primary scan.
        settings: Resolution and a hard cap including refinement/final evaluations.

    Returns:
        Fresh density samples and root attempts, never an exclusion conclusion.
        No stored grid density is reused as a current numerical certificate.
    """
    settings = settings or CoverageSettings()
    if settings.strategy == "adaptive":
        from adroit.parameter_space.adaptive import diagnose as adaptive_diagnose
        return adaptive_diagnose(request, settings, checkpoint)
    target = DENSITY.value * request.relic_fraction
    if not math.isfinite(target) or target <= 0:
        raise ValueError("The thermal target must be positive and finite")
    xs, ys = _coordinates(request.x, settings.refinement_depth), _coordinates(request.y, settings.refinement_depth)
    evaluator = _Evaluator(request=request, maximum=settings.max_evaluations)
    if checkpoint:
        budget = checkpoint.load("coverage-budget", "count", _Budget)
        evaluator.evaluations = budget.evaluations if budget else 0
        if evaluator.evaluations > settings.max_evaluations:
            raise CheckpointMismatch("Saved coverage budget exceeds the requested cap")
        evaluator._checkpoint = checkpoint
    samples = _samples(request, evaluator, xs, ys, checkpoint)
    roots, omitted = _roots(request, evaluator, samples, target, xs, ys)
    unresolved = [root.reason for root in roots if not root.converged]
    missing = sum(sample.omega_h2 is None for sample in samples)
    planned = len(xs) * len(ys)
    if missing:
        unresolved.append(f"{missing} sampled points have unavailable/domain-invalid relic calculations")
    if len(samples) < planned:
        unresolved.append(f"coverage budget exhausted: {planned - len(samples)} planned samples not evaluated")
    if omitted:
        unresolved.append(f"coverage budget exhausted: {omitted} discovered candidates not refined")
    return CoverageDiagnostic(request=request, settings=settings, target=target, xs=xs, ys=ys,
                              samples=samples, root_attempts=roots, evaluations=evaluator.evaluations,
                              planned_samples=planned, omitted_candidates=omitted, unresolved=unresolved,
                              status="partial" if unresolved else "sampled_at_requested_resolution")


def _samples(request: ScanRequest, evaluator, xs, ys, checkpoint: Checkpoint | None) -> list[RelicSample]:
    """The finer grid's relic samples row by row (resumed from ``checkpoint``) until the evaluation budget ends."""
    samples = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            key = str(j * len(xs) + i)
            cached = checkpoint.load("coverage-samples", key, RelicSample) if checkpoint else None
            if cached is not None:
                if cached.point != _point_at(request, x, y) or cached.index != (i, j):
                    raise CheckpointMismatch("Cached coverage sample differs from its declared inputs")
                samples.append(cached)
                continue
            if evaluator.evaluations >= evaluator.maximum:
                break
            point = _point_at(request, x, y)
            value, reason = None, ""
            try:
                value = evaluator.omega(point)
            except (ValueError, RuntimeError, ArithmeticError) as error:
                reason = str(error)
            sample = RelicSample(index=(i, j), point=point, omega_h2=value, reason=reason)
            samples.append(sample)
            if checkpoint:
                checkpoint.save("coverage-samples", key, sample)
        if len(samples) < (j + 1) * len(xs):
            break
    return samples

"""Bounded cell refinement with explicit selection and independently checked roots."""
from __future__ import annotations

from collections import deque
import math

from adroit.parameter_space.likelihood import DENSITY
from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
from adroit.core.state import StrictModel
from adroit.parameter_space.coverage import (AdaptiveCell, CoverageDiagnostic, CoverageSettings, RelicSample,
                                             _Budget, _Evaluator, _coordinates, _roots)
from adroit.parameter_space.scan import ScanRequest, _point_at


class _Cell(StrictModel):
    bounds: tuple[int, int, int, int]
    depth: int


def _nodes(cell: _Cell) -> list[tuple[int, int]]:
    x0, x1, y0, y1 = cell.bounds
    return [(i, j) for j in (y0, (y0+y1)//2, y1) for i in (x0, (x0+x1)//2, x1)]


def _split(cell: _Cell) -> list[_Cell]:
    x0, x1, y0, y1 = cell.bounds
    xm, ym = (x0+x1)//2, (y0+y1)//2
    return [_Cell(bounds=(a, b, c, d), depth=cell.depth+1)
            for c, d in ((y0, ym), (ym, y1)) for a, b in ((x0, xm), (xm, x1))]


def _selection(rows: list[RelicSample], target: float, settings: CoverageSettings, depth: int) -> str:
    if any(row.omega_h2 is None for row in rows):
        return "unavailable or domain-invalid density"
    if depth < settings.exploration_depth:
        return "required exploration depth"
    values = [row.omega_h2 for row in rows]
    if min(values) <= target <= max(values):
        return "thermal target bracketed or sampled"
    if min(abs(value/target-1) for value in values) <= settings.near_target:
        return "near the thermal target"
    log = [math.log(max(value, 1e-300)/target) for value in values]
    predicted = [(log[0]+log[2])/2, (log[0]+log[6])/2,
                 sum(log[k] for k in (0,2,6,8))/4, (log[2]+log[8])/2, (log[6]+log[8])/2]
    if max(abs(log[k]-value) for k, value in zip((1,3,4,5,7), predicted)) > settings.log_curvature:
        return "log-density curvature"
    return ""


def _sample(index: tuple[int, int], request: ScanRequest, xs: list[float], ys: list[float],
            evaluator: _Evaluator, known: dict[tuple[int, int], RelicSample]) -> RelicSample | None:
    if index in known:
        return known[index]
    i, j = index
    point, checkpoint = _point_at(request, xs[i], ys[j]), evaluator._checkpoint
    key = str(j*len(xs)+i)
    row = checkpoint.load("coverage-samples", key, RelicSample) if checkpoint else None
    if row is not None:
        if row.point != point or row.index != index:
            raise CheckpointMismatch("Cached adaptive sample differs from its physical inputs")
    else:
        if evaluator.evaluations >= evaluator.maximum:
            return None
        value, reason = None, ""
        try:
            value = evaluator.omega(point)
        except (ValueError, RuntimeError, ArithmeticError) as error:
            reason = str(error)
        row = RelicSample(index=index, point=point, omega_h2=value, reason=reason)
        if checkpoint:
            checkpoint.save("coverage-samples", key, row)
    known[index] = row
    return row


def _edges(cells: list[AdaptiveCell], known: dict[tuple[int, int], RelicSample],
           target: float) -> list[tuple[RelicSample, RelicSample]]:
    edges = {}
    for cell in cells:
        if cell.decision == "split":
            continue
        nodes = _nodes(_Cell(bounds=cell.bounds, depth=cell.depth))
        for k, index in enumerate(nodes):
            a = known.get(index)
            if a is None or a.omega_h2 is None:
                continue
            if abs(a.omega_h2/target-1) < 1e-10:
                edges[(index, index)] = (a, a)
            for n in ([k+1] if k%3 < 2 else []) + ([k+3] if k < 6 else []):
                b = known.get(nodes[n])
                if b is not None and b.omega_h2 is not None and (a.omega_h2-target)*(b.omega_h2-target) < 0:
                    edges[(index, nodes[n])] = (a, b)
    return [edges[key] for key in sorted(edges)]


def _cells(request: ScanRequest, settings: CoverageSettings, xs: list[float], ys: list[float],
           evaluator: _Evaluator, target: float) -> tuple[list[AdaptiveCell], list[RelicSample]]:
    step = 2**settings.refinement_depth
    queue = deque(_Cell(bounds=(i,i+step,j,j+step), depth=1)
                  for j in range(0,len(ys)-1,step) for i in range(0,len(xs)-1,step))
    known, cells = {}, []
    while queue:
        cell = queue.popleft()
        rows = [_sample(index, request, xs, ys, evaluator, known) for index in _nodes(cell)]
        if any(row is None for row in rows):
            cells.append(AdaptiveCell(**cell.model_dump(), decision="not_sampled", reason="evaluation budget exhausted"))
            continue
        reason = _selection(rows, target, settings, cell.depth)
        missing = any(row.omega_h2 is None for row in rows)
        if reason and cell.depth < settings.refinement_depth:
            decision = "split"
            queue.extend(_split(cell))
        else:
            decision = "unresolved" if missing else "maximum_depth" if reason else "not_selected"
        cells.append(AdaptiveCell(**cell.model_dump(), decision=decision, reason=reason or "no refinement indicator"))
    return cells, list(known.values())


def diagnose(request: ScanRequest, settings: CoverageSettings,
             checkpoint: Checkpoint | None = None) -> CoverageDiagnostic:
    """Probe every starting cell, then refine selected cells within the declared cap.

    Nine probes per cell expose central/edge structure. Selection follows required
    exploration, brackets, proximity and curvature. Unselected cells retain coarser
    resolution. Final roots always call the actual solver independently.
    """
    target = DENSITY.value*request.relic_fraction
    if not math.isfinite(target) or target <= 0:
        raise ValueError("The thermal target must be positive and finite")
    xs, ys = _coordinates(request.x, settings.refinement_depth), _coordinates(request.y, settings.refinement_depth)
    evaluator = _Evaluator(request=request, maximum=settings.max_evaluations)
    if checkpoint:
        budget = checkpoint.load("coverage-budget", "count", _Budget)
        evaluator.evaluations = budget.evaluations if budget else 0
        if evaluator.evaluations > settings.max_evaluations:
            raise CheckpointMismatch("Saved adaptive budget exceeds the requested cap")
        evaluator._checkpoint = checkpoint
    cells, samples = _cells(request, settings, xs, ys, evaluator, target)
    roots, omitted = _roots(request, evaluator, samples, target, xs, ys,
                            _edges(cells, {row.index: row for row in samples}, target))
    unresolved = [root.reason for root in roots if not root.converged]
    missing = sum(row.omega_h2 is None for row in samples)
    unprobed = sum(cell.decision == "not_sampled" for cell in cells)
    if missing:
        unresolved.append(f"{missing} adaptive samples lack a valid relic calculation")
    if unprobed:
        unresolved.append(f"coverage budget exhausted: {unprobed} selected cells not completely probed")
    if omitted:
        unresolved.append(f"coverage budget exhausted: {omitted} discovered candidates not refined")
    return CoverageDiagnostic(request=request, settings=settings, target=target, xs=xs, ys=ys,
        samples=samples, root_attempts=roots, evaluations=evaluator.evaluations,
        planned_samples=len(xs)*len(ys), omitted_candidates=omitted, unresolved=unresolved, cells=cells,
        status="partial" if unresolved else "adaptive_sampling_complete",
        interpretation="Adaptive relic-only diagnostic: selected cells have the declared depth; other cells retain "
                       "coarser resolution. Finite probes do not rule out narrower unsampled features.")

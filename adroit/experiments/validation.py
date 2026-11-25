"""Reproducing a collaboration's published limit: the rules a module must meet (build plan, DM3).

The rule fixed before any module was run: the reproduced limit lies within
a factor 1.3 of the published one at every tested mass across the published
range. Two refinements, adopted by the owner on 2026-09-29 after the first
results:
- **Steep edges.** Where the published limit falls faster than
  |d ln σ/d ln m| = 8, a point also passes if the reproduced curve reaches
  the published cross-section within a 3% shift in mass. For light dark
  matter the lowest reachable mass goes as the square root of the threshold,
  so 3% in mass is about 6% in threshold energy, the size of the threshold
  and energy-scale uncertainties the collaborations quote.
- **Validated ranges, module by module.** A module is validated over a
  contiguous run of passing masses (``ValidationResult.validated_range``) and
  is used only as a flag outside it. It counts for the gate if that range
  spans a decade and includes the mass of its strongest published limit.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from adroit.core.dm_state import LimitCurve, ValidationResult
from adroit.experiments.base import ExperimentModule

TOLERANCE = 1.3
EDGE_SLOPE = 8.0
EDGE_SHIFT = 0.03


def published_at(curve: LimitCurve, masses_gev: np.ndarray) -> np.ndarray:
    """The published limit at the given masses, interpolated in log-log."""
    return np.exp(np.interp(np.log(masses_gev), np.log(curve.masses_gev),
                            np.log(curve.cross_sections_cm2)))


def published_slope(curve: LimitCurve, mass_gev: float, step: float = 0.01) -> float:
    """d ln σ / d ln m of the published curve at one mass (one-sided at the ends)."""
    low = max(mass_gev / (1.0 + step), curve.masses_gev[0])
    high = min(mass_gev * (1.0 + step), curve.masses_gev[-1])
    values = np.log(published_at(curve, np.array([low, high])))
    return float((values[1] - values[0]) / (np.log(high) - np.log(low)))


def trial_masses(curve: LimitCurve, points: int = 12) -> np.ndarray:
    """Masses spread evenly in log across the published range."""
    return np.geomspace(curve.masses_gev[0], curve.masses_gev[-1], points)


def validate(module: ExperimentModule, curve: LimitCurve, masses_gev: np.ndarray | None = None,
             tolerance: float = TOLERANCE,
             limits: Callable[[list[float]], list[float]] | None = None) -> ValidationResult:
    """The module's limit against the published one, under the collaboration's conventions.

    The halo, the nuclear input and the target are those of the published
    analysis (``conventions``, ``published_target``). Points that fail the
    ratio at a steep edge are tested for the edge clause with two more
    limits each, at ±3% in mass.

    Args:
        limits: the module's limits at a list of masses, if not its
            ``limits_on`` (CDMSlite's official procedure, for instance).
    """
    masses = trial_masses(curve) if masses_gev is None else np.asarray(masses_gev, dtype=float)
    if limits is None:
        target = module.published_target(curve.kind)

        def limits(values: list[float]) -> list[float]:
            return module.limits_on(curve.kind, values, target=target)

    reproduced = limits([float(m) for m in masses])
    published = published_at(curve, masses)
    steep = [i for i, (m, r, p) in enumerate(zip(masses, reproduced, published))
             if not 1.0 / tolerance <= r / p <= tolerance
             and abs(published_slope(curve, float(m))) > EDGE_SLOPE]
    shifted = limits([float(masses[i]) * f for i in steep
                      for f in (1 - EDGE_SHIFT, 1 + EDGE_SHIFT)]) if steep else []
    edges = [False] * len(masses)
    for k, i in enumerate(steep):
        low, high = shifted[2 * k], shifted[2 * k + 1]
        edges[i] = bool(min(low, high) <= published[i] <= max(low, high))
    return ValidationResult(experiment=module.info.name, kind=curve.kind,
                            masses_gev=masses.tolist(), published_cm2=published.tolist(),
                            reproduced_cm2=reproduced, edge_passes=edges, tolerance=tolerance,
                            method=module.info.statistical_method,
                            note=f"published: {curve.source}")

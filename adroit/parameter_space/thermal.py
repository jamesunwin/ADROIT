"""Certificates for numerical thermal roots, distinct from theory-error bands."""
from __future__ import annotations

import math
from typing import Callable

from pydantic import Field
from scipy.optimize import brentq

from adroit.core.state import StrictModel
from adroit.parameter_space.classes import Point

ROOT_RELATIVE_TOLERANCE = 0.01
ROOT_COORDINATE_TOLERANCE = 1e-6       # F4: the relic solver's own precision (below); was 1e-10


class ThermalRoot(StrictModel):
    """Evaluated density and residual of a bracketed root attempt."""

    point: Point | None = None
    omega_h2: float | None = None
    target: float
    relative_residual: float | None = None
    converged: bool = False
    reason: str = ""
    coordinate: float | None = None
    # the grid points (x, y) it was refined between (``verdict._thermal_roots``; the equation of state's band refines
    # it again there): absent in results written before the band
    bracket: tuple[tuple[float, float], tuple[float, float]] | None = Field(default=None, exclude_if=lambda v: v is None)


def refine(point_at: Callable[[float], Point], omega: Callable[[Point], float | None],
           target: float, low: float = 0, high: float = 1) -> ThermalRoot:
    """Refine with the actual solver; reject missing, discontinuous or inaccurate roots.

    Brent's coordinate tolerance is 10⁻⁶ of the bracket, matched to the relic
    solver: its Boltzmann integration (BDF, rtol 10⁻⁷) reproduces Ωh² to about
    10⁻⁵, so the earlier 10⁻¹⁰ only bisected that noise (twice the evaluations
    per root, the same roots to 4 × 10⁻⁵ in Ωh²; F4, 2026-10-19). The residual
    is ln(Ωh²/target): along a log axis (``verdict.along``, geometric in t) Ωh²
    is close to a power of the mass or coupling, so the residual is close to
    linear in t. The 1% acceptance is unchanged, and the final density is
    evaluated again independently.
    """
    if not math.isfinite(target) or target <= 0:
        raise ValueError("The thermal target must be positive and finite")

    def residual(t: float) -> float:
        value = omega(point_at(t))
        if value is None or not math.isfinite(value) or value <= 0:
            raise ValueError("relic solver unavailable/nonfinite within the bracket")
        return math.log(value / target)

    try:
        a = residual(low)
        b = residual(high) if high != low else a
        if abs(a) < 1e-10:
            t = low
        elif abs(b) < 1e-10:
            t = high
        else:
            t = float(brentq(residual, low, high, xtol=ROOT_COORDINATE_TOLERANCE,
                             rtol=ROOT_COORDINATE_TOLERANCE, maxiter=100))
        point = point_at(t)
        value = omega(point)
        if value is None or not math.isfinite(value) or value < 0:
            raise ValueError("final relic evaluation unavailable/nonfinite")
        error = abs(value / target - 1)
        good = error <= ROOT_RELATIVE_TOLERANCE
        return ThermalRoot(point=point, omega_h2=value, target=target, relative_residual=error,
                           converged=good, coordinate=t,
                           reason="" if good else f"relative relic residual {error:.6g} exceeds 0.01")
    except (ValueError, RuntimeError, ArithmeticError) as error:
        return ThermalRoot(target=target, reason=str(error))

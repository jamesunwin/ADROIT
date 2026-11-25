"""Invert a fitted NR amplitude along a bounded physical coupling branch.

Masses and other couplings stay fixed. The actual model supplies the NR
coefficients; no universal mediator-mass or coupling power law is assumed.
Only a common rescaling of the full coefficient vector is accepted. The
caller additionally verifies the detector spectrum and profile likelihood.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.optimize import brentq

from adroit.parameter_space.classes import Point


def _coefficients(cls: Any, point: Point) -> dict[tuple, float]:
    values = {}
    for c in cls.interaction(point).coefficients:
        for nucleon in ("proton", "neutron"):
            key = (c.operator, c.q_power, c.q_scale_gev, c.mediator_mass_gev, nucleon)
            values[key] = values.get(key, 0.0) + getattr(c, nucleon)
    return values


def tied(point: Point, ties) -> Point:
    """The point with every coupling the model ties to g_chi set from it (``relations.orient`` with g_chi free, then
    ``relations.apply``): a model written with one symbol for the dark matter's and the quarks' couplings moves both
    (the audit loop's AL3-03, 2026-11-15: g_chi alone had been fitted, and g_q left at 1)."""
    if not ties:
        return point
    from adroit.parameter_space import relations
    return relations.apply(point, relations.orient(list(ties), ("g_chi",)))


def invert(cls: Any, point: Point, amplitude: float, ties=()) -> Point:
    """Solve g_chi on its original-sign branch, 0 ≤ |g_chi| ≤ √(4π), with the couplings the model ties to it
    (``ties``, ``tied``) following it.

    This is the existing perturbative scan domain. A zero baseline, an
    insensitive/degenerate branch, changing operator shape, or a target
    outside that branch is explicitly unsupported (ValueError).
    """
    if not math.isfinite(amplitude) or amplitude < 0:
        raise ValueError("fitted amplitude must be finite and nonnegative")
    initial = _coefficients(cls, point)
    norm = math.sqrt(sum(v * v for v in initial.values()))
    if norm == 0:
        raise ValueError("zero reference interaction: physical inversion is undetermined")
    sign = -1 if point.g_chi < 0 else 1

    def at(g: float) -> Point:
        return tied(point.model_copy(update={"g_chi": sign * g}), ties)

    def size(g: float) -> float:
        return math.sqrt(sum(v * v for v in _coefficients(cls, at(g)).values())) / norm

    bound = math.sqrt(4 * math.pi)
    probes = np.array([size(g) for g in np.linspace(0, bound, 9)])
    if not np.isfinite(probes).all() or probes[-1] - probes[0] <= 1e-12:
        raise ValueError("g_chi does not identify a unique increasing scattering branch")
    if np.any(np.diff(probes) <= 0):
        raise ValueError("nonmonotone/degenerate g_chi inversion requires a model-specific fit")
    if amplitude < probes[0] - 1e-12 or amplitude > probes[-1] * (1 + 1e-12):
        raise ValueError("fitted amplitude lies outside the perturbative g_chi branch")
    target = min(max(amplitude, probes[0]), probes[-1])  # roundoff at an exact boundary only
    g = brentq(lambda g: size(g) - target, 0, bound, xtol=1e-14, rtol=1e-12)
    result = at(g)
    actual = _coefficients(cls, result)
    error = max((abs(actual.get(k, 0) - amplitude * initial.get(k, 0))
                 for k in initial.keys() | actual.keys()), default=0)
    if error > 1e-7 * max(amplitude * norm, 1e-300):
        raise ValueError("physical coupling changes the operator spectrum; a new fit is required")
    if hasattr(cls, "domain") and cls.domain(result):
        raise ValueError(f"fitted point outside model domain: {cls.domain(result)}")
    return result

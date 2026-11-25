"""Upper limits that allow for unknown background: Yellin's interval methods.

A search that cannot model its background (CRESST-III, CDMSlite) sets a limit
from where the observed events are *not*. Map each event to the fraction
F_i of the expected signal lying below it, so that the signal is uniform on
[0, 1] with total expectation μ. Then:

- **Maximum gap** (S. Yellin, Phys. Rev. D 66 (2002) 032005). The largest
  gap between neighbouring events holds x = μ g_max expected signal events.
  The probability that the largest gap is smaller than x is

      C₀(x, μ) = Σ_{k=0}^{⌊μ/x⌋} e^{−kx}/k! [(kx − μ)^k − k (kx − μ)^{k−1}] ,

  and the upper limit on μ is where C₀ = CL. It is computed here, exactly.
- **Optimum interval** (same paper; high-statistics extension, arXiv:0709.2701).
  It chooses the interval, with any number of events inside, that is most
  constraining, and needs Monte Carlo tables. Yellin's code and tables
  are an external tool (``optimum_interval.py``).
"""

from __future__ import annotations

import math

import mpmath
import numpy as np
from scipy.optimize import brentq


def cumulative_fractions(event_positions: np.ndarray, grid: np.ndarray,
                         density: np.ndarray) -> np.ndarray:
    """F_i: the fraction of the expected signal below each event, from a density on a grid.

    Events outside the grid get 0 or 1. The result is sorted.
    """
    increments = 0.5 * (density[1:] + density[:-1]) * np.diff(grid)
    cumulative = np.concatenate([[0.0], np.cumsum(increments)])
    if cumulative[-1] <= 0.0:
        raise ValueError("the signal density has no weight on the grid")
    return np.sort(np.interp(event_positions, grid, cumulative / cumulative[-1]))


def largest_gap(fractions: np.ndarray) -> float:
    """The largest gap in signal fraction between neighbouring events, ends included."""
    points = np.concatenate([[0.0], np.sort(np.asarray(fractions, dtype=float)), [1.0]])
    return float(np.max(np.diff(points)))


def maximum_gap_probability(x: float, mu: float) -> float:
    """C₀(x, μ): the probability that the largest gap holds fewer than x expected events."""
    if x <= 0.0:
        return 0.0
    if x >= mu:
        return 1.0 - math.exp(-mu) if x == mu else 1.0
    terms = int(math.floor(mu / x))
    with mpmath.workdps(30 + 2 * terms):
        xm, mum = mpmath.mpf(x), mpmath.mpf(mu)
        total = mpmath.mpf(0)
        for k in range(terms + 1):
            base = k * xm - mum
            bracket = base ** k - (k * base ** (k - 1) if k > 0 else 0)
            total += mpmath.exp(-k * xm) / mpmath.factorial(k) * bracket
        return float(total)


def maximum_gap_limit(fractions: np.ndarray, cl: float = 0.9) -> float:
    """The maximum-gap upper limit on μ, the total expected signal events."""
    gap = largest_gap(fractions)

    def excess(mu: float) -> float:
        return maximum_gap_probability(mu * gap, mu) - cl

    upper = 3.0 / gap
    while excess(upper) < 0.0:
        upper *= 2.0
    return float(brentq(excess, 1e-9, upper, xtol=1e-10, rtol=1e-10))

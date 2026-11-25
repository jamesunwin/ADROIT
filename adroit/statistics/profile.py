"""The profile likelihood ratio: upper limits and discovery significance on a signal strength.

A search's likelihood L(κ, θ) depends on the signal strength κ ≥ 0 (the
signal is κ times a reference spectrum) and on nuisance parameters θ. The
profile likelihood maximises over θ at each κ; the statistics below work
with its negative logarithm, nll(κ) = −ln max_θ L(κ, θ).

- **Upper limit.** With κ̂ the best fit (κ̂ ≥ 0), the one-sided statistic
  q(κ) = 2[nll(κ) − nll(κ̂)] for κ ≥ κ̂ follows, asymptotically, half a χ²
  with one degree of freedom (Cowan, Cranmer, Gross, Vitells, arXiv:1007.1727).
  The upper limit at confidence level CL is where q = z², z = Φ⁻¹(CL):
  1.642 for 90%.
- **Discovery.** q₀ = 2[nll(0) − nll(κ̂)] and the local significance is √q₀.

Asymptotic thresholds hold when counts are not small; for a handful of
events a module uses the method its collaboration used.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from scipy.optimize import brentq, minimize_scalar
from scipy.stats import norm


def one_sided_threshold(cl: float = 0.9) -> float:
    """The asymptotic threshold on q for a one-sided upper limit: (Φ⁻¹(CL))²."""
    return float(norm.ppf(cl) ** 2)


def best_fit(nll: Callable[[float], float], scale: float) -> tuple[float, float]:
    """(κ̂, nll(κ̂)) with κ̂ ≥ 0, searching up to ``scale`` and beyond if needed."""
    upper = scale
    for _ in range(40):
        result = minimize_scalar(nll, bounds=(0.0, upper), method="bounded",
                                 options={"xatol": 1e-10 * upper})
        if result.x < 0.9 * upper:
            break
        upper *= 10.0
    at_zero = nll(0.0)
    if at_zero <= result.fun:
        return 0.0, at_zero
    return float(result.x), float(result.fun)


def upper_limit(nll: Callable[[float], float], scale: float = 1.0, cl: float = 0.9) -> float:
    """The signal strength κ at which the one-sided profile-likelihood test excludes it.

    Args:
        nll: The profiled negative log-likelihood as a function of κ ≥ 0.
        scale: A rough size for κ (where to start looking).
        cl: The confidence level.
    """
    kappa_hat, nll_hat = best_fit(nll, scale)
    target = one_sided_threshold(cl) / 2.0

    def excess(kappa: float) -> float:
        return nll(kappa) - nll_hat - target

    lower, upper = kappa_hat, max(kappa_hat, scale) * 2.0 + scale
    for _ in range(80):
        if excess(upper) > 0.0:
            break
        lower, upper = upper, upper * 2.0
    else:
        raise ValueError("the likelihood never excludes the signal: is it insensitive?")
    return float(brentq(excess, lower, upper, xtol=1e-12 * upper, rtol=1e-10))


def discovery_significance(nll: Callable[[float], float], scale: float = 1.0) -> float:
    """The local significance √q₀ of the best-fit signal against the background alone."""
    kappa_hat, nll_hat = best_fit(nll, scale)
    return math.sqrt(max(0.0, 2.0 * (nll(0.0) - nll_hat))) if kappa_hat > 0 else 0.0

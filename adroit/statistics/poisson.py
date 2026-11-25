"""Counting statistics: Poisson upper limits and binned Poisson likelihoods.

For n events observed where b are expected from background, the classical
(Neyman) upper limit s_up on the expected signal at confidence level CL is
the signal for which observing n or fewer events has probability 1 − CL:

    P(N ≤ n | s_up + b) = 1 − CL .

A binned search compares the observed counts n_i with the expectation
λ_i = κ s_i + b_i bin by bin; its log-likelihood is Σ_i [n_i ln λ_i − λ_i]
(dropping the constant −ln n_i!).
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.special import gammaincc
from scipy.stats import poisson
from adroit.core.calculation_cache import reuse
from adroit.core.state import StrictModel
from adroit.statistics import cache_identity


def poisson_upper_limit(n_observed: int, background: float = 0.0, cl: float = 0.9) -> float:
    """The classical upper limit on the expected signal, given n observed and b expected.

    Returns 0 when the observation lies so far below the background that no
    positive signal satisfies the condition (the classical limit would be
    negative there).
    """
    if n_observed < 0 or background < 0.0 or not 0.0 < cl < 1.0:
        raise ValueError("need n_observed >= 0, background >= 0 and 0 < cl < 1")

    def excess(signal: float) -> float:
        return poisson.cdf(n_observed, signal + background) - (1.0 - cl)

    if excess(0.0) <= 0.0:
        return 0.0
    upper = n_observed + 10.0 * math.sqrt(n_observed + 1.0) + 10.0
    return float(brentq(excess, 0.0, upper, xtol=1e-12, rtol=1e-12))


def poisson_upper_limit_zero_background(n_observed: int, cl: float = 0.9) -> float:
    """The same limit for b = 0, from the regularised gamma function (a check on the above)."""
    return float(brentq(lambda s: gammaincc(n_observed + 1, s) - (1.0 - cl),
                        0.0, n_observed + 50.0, xtol=1e-12))


def binned_log_likelihood(observed: np.ndarray, expected: np.ndarray) -> float:
    """Σ_i [n_i ln λ_i − λ_i]; a bin with λ_i = 0 and n_i > 0 makes it −∞."""
    n = np.asarray(observed, dtype=float)
    lam = np.asarray(expected, dtype=float)
    if np.any(lam < 0.0):
        raise ValueError("expected counts must not be negative")
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(n > 0, n * np.log(lam), 0.0) - lam
    return float(np.sum(terms))


def free_background_statistic(observed: np.ndarray, expected: np.ndarray,
                              kappa: float) -> np.ndarray:
    """q(κ) of a counting search whose backgrounds are free and non-negative, bin by bin.

    With b_i free, b̂_i = max(0, n_i − κ s_i), and the likelihood is flat for
    κ s_i ≤ n_i in every bin, so its maximum lies at κ = 0 and

        q(κ) = 2 Σ_{i: κ s_i > n_i} [κ s_i − n_i − n_i ln(κ s_i / n_i)] .

    ``observed`` may carry toy experiments along its first axis.
    """
    signal = kappa * np.asarray(expected, dtype=float)
    n = np.asarray(observed, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = signal - n - np.where(n > 0, n * np.log(signal / np.where(n > 0, n, 1.0)), 0.0)
    return 2.0 * np.sum(np.where(signal > n, term, 0.0), axis=-1)


class _NeymanInput(StrictModel):
    observed: list[float]
    expected: list[float]
    cl: float
    toys: int
    seed: int


class _NeymanLimit(StrictModel):
    kappa: float


def free_background_limit(observed: np.ndarray, expected: np.ndarray, cl: float = 0.9,
                          toys: int = 20_000, seed: int = 20260929, *, cache: bool = True) -> float:
    """The upper limit on κ for free backgrounds, by a Neyman construction with toy experiments.

    At each trial κ the backgrounds are set to their conditional best fit,
    b_i = max(0, n_i − κ s_i); toys are drawn from Poisson(κ s_i + b_i); κ is
    excluded when the observed q(κ) exceeds the fraction ``cl`` of the toys'.
    Asymptotic thresholds fail at a handful of events; this does not.
    """
    observed, expected = np.asarray(observed, dtype=float), np.asarray(expected, dtype=float)
    if observed.ndim != 1 or expected.shape != observed.shape or not observed.size or (
            not np.isfinite(observed).all() or not np.isfinite(expected).all() or
            (observed < 0).any() or (expected < 0).any() or expected.sum() <= 0 or
            not 0 < cl < 1 or toys < 1):
        raise ValueError("Need finite nonnegative counts, positive signal/toys and 0 < CL < 1")
    inputs = _NeymanInput(observed=observed.tolist(), expected=expected.tolist(), cl=cl, toys=toys, seed=seed)
    result = reuse("free-background-neyman", inputs, cache_identity.python_statistics,
                   lambda: _NeymanLimit(kappa=_free_background_limit(observed, expected, cl, toys, seed)),
                   _NeymanLimit, lambda r: math.isfinite(r.kappa) and r.kappa > 0, enabled=cache)
    return result.kappa


def _free_background_limit(observed: np.ndarray, expected: np.ndarray, cl: float, toys: int, seed: int) -> float:
    """The unchanged seeded Neyman construction, without persistence."""
    n_obs = np.asarray(observed, dtype=float)
    unit = float(np.sum(expected))                 # work in units of one expected signal event
    s = np.asarray(expected, dtype=float) / unit
    rng = np.random.default_rng(seed)
    uniforms = rng.random((toys, len(s)))          # common random numbers across trial κ

    def excluded(kappa: float) -> bool:
        background = np.maximum(0.0, n_obs - kappa * s)
        toy_counts = poisson.ppf(uniforms, kappa * s + background)
        q_toys = free_background_statistic(toy_counts, s, kappa)
        q_obs = float(free_background_statistic(n_obs, s, kappa))
        return float(np.mean(q_toys >= q_obs)) < 1.0 - cl

    low, high = 0.0, 1.0
    while not excluded(high):
        low, high = high, 2.0 * high
    for _ in range(40):
        middle = 0.5 * (low + high)
        low, high = (low, middle) if excluded(middle) else (middle, high)
    return high / unit


def cousins_highland_limit(n_observed: int, relative_uncertainty: float,
                           cl: float = 0.9) -> float:
    """The Poisson upper limit when the signal expectation carries a relative uncertainty.

    Cousins & Highland (Nucl. Instrum. Meth. A 320 (1992) 331): the
    probability of the observation is averaged over a Gaussian sensitivity
    factor ε of mean 1 and width σ_r, truncated at zero, and the limit is the
    signal s at which P(N ≤ n | s ε) averages to 1 − CL. For σ_r = 0 it is
    the classical limit.
    """
    if relative_uncertainty < 0.0:
        raise ValueError("the relative uncertainty must not be negative")
    if relative_uncertainty == 0.0:
        return poisson_upper_limit(n_observed, 0.0, cl)
    eps = np.linspace(max(0.0, 1.0 - 8.0 * relative_uncertainty),
                      1.0 + 8.0 * relative_uncertainty, 4001)
    weights = np.exp(-0.5 * ((eps - 1.0) / relative_uncertainty) ** 2)
    weights /= np.trapezoid(weights, eps)

    def excess(signal: float) -> float:
        return float(np.trapezoid(poisson.cdf(n_observed, signal * eps) * weights, eps)) - (1.0 - cl)

    upper = poisson_upper_limit(n_observed, 0.0, cl)
    while excess(upper) > 0.0:
        upper *= 1.5
    return float(brentq(excess, 0.0, upper, xtol=1e-12, rtol=1e-10))

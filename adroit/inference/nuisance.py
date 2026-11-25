"""The background rate as a nuisance parameter (DM10).

A search states its expected background B with an uncertainty, often
asymmetric: −σ₋ and +σ₊, relative to B. The background density becomes
θ b(E), and the likelihood gains the constraint on θ from that statement, a
bifurcated Gaussian about the auxiliary measurement a (a = 1 for the data):

    ln L(s, θ) = −s − θB + Σ_i ln[s f_i + θ b_i] − ½ ((θ − a)/σ)²,
    σ = σ₊ where θ > a, σ₋ where θ ≤ a .

θ is profiled: every statement about s uses max_θ ln L(s, θ). The function is
concave in (s, θ) (logarithms of linear functions, a linear term, and a
convex penalty whose slope is continuous at θ = a), so projected Newton steps
with an active set find its maximum on s ≥ 0, θ > 0 from any feasible start,
the maximum on a bound included (θ → 0 where the events need no background);
a result that fails the maximum's conditions is unresolved (NaN), never
published. Many candidates are fitted at once: rows of f are candidates,
columns events. The events must lie where b > 0, as the background-only toys
guarantee.
"""

from __future__ import annotations

import numpy as np
from pydantic import Field, model_validator

from adroit.core.state import StrictModel

THETA_MIN = 1e-12        # θ is kept strictly positive


class BackgroundRate(StrictModel):
    """A search's expected background count and its stated relative uncertainty."""

    total: float = Field(ge=0.0)               # B: expected background events in the window
    minus: float = Field(default=0.0, ge=0.0)  # σ₋, relative
    plus: float = Field(default=0.0, ge=0.0)   # σ₊, relative
    # a: 1 for the data; drawn afresh in each toy, where a Gaussian measurement can fall at or below zero
    centre: float = Field(default=1.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _both_or_neither(self) -> "BackgroundRate":
        if (self.minus > 0.0) != (self.plus > 0.0):
            raise ValueError("give both σ₋ and σ₊, or neither (a fixed background)")
        return self

    @property
    def free(self) -> bool:
        """Whether θ is profiled (an uncertainty is stated)."""
        return self.minus > 0.0


def _terms(s: np.ndarray, theta: np.ndarray, f: np.ndarray, b: np.ndarray,
           rate: BackgroundRate) -> tuple[np.ndarray, ...]:
    """ln L and its first and second derivatives in (s, θ), for each row."""
    d = s[:, None] * f + theta[:, None] * b
    sigma = np.where(theta > rate.centre, rate.plus, rate.minus)
    pull = (theta - rate.centre) / sigma
    value = -s - theta * rate.total + np.log(d).sum(axis=1) - 0.5 * pull ** 2
    g_s = -1.0 + (f / d).sum(axis=1)
    g_t = -rate.total + (b / d).sum(axis=1) - pull / sigma
    h_ss = -(f * f / (d * d)).sum(axis=1)
    h_st = -(f * b / (d * d)).sum(axis=1)
    h_tt = -(b * b / (d * d)).sum(axis=1) - 1.0 / sigma ** 2
    return value, g_s, g_t, h_ss, h_st, h_tt


def _newton(s: np.ndarray, theta: np.ndarray, f: np.ndarray, b: np.ndarray, rate: BackgroundRate,
            vary_s: bool, iterations: int = 200) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Maximise ln L over θ ≥ ``THETA_MIN`` (and s ≥ 0, if ``vary_s``); returns (s, θ, ln L), with s and ln L NaN
    in a row whose result is not its maximum (``_optimal``).

    Projected Newton steps with an active set: a variable at its bound whose own slope points out of the region is held
    there, and the other is maximised alone; otherwise the joint step, projected onto the region and halved until it
    does not lower ln L. The joint step alone (as before) stalled where the maximum lies on θ's bound: halving shrank
    the step in s with the step in θ, so s was never maximised there (the independent audit, NA15-01, 2026-11-16:
    one event on B = 10 with ±100%, ŝ = 24.3 published for the maximum s = 1, θ = 0, and Z = 0 for 3.0)."""
    for iteration in range(iterations):
        if _optimal(s, theta, f, b, rate, vary_s).all():      # stopped by the maximum's conditions, not a step's size
            break
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):   # branches np.where does not take
            value, g_s, g_t, h_ss, h_st, h_tt = _terms(s, theta, f, b, rate)
            held_s = (s <= 0.0) & (g_s <= 0.0) if vary_s else np.ones(s.shape, bool)
            held_t = (theta <= THETA_MIN) & (g_t <= 0.0)
            det = h_ss * h_tt - h_st ** 2
            joint_s, joint_t = -(h_tt * g_s - h_st * g_t) / det, -(h_ss * g_t - h_st * g_s) / det
            # where the joint step is not finite or not uphill (one event makes the Hessian of rank one, singular
            # where d → 0), one variable at a time, alternately
            bad = ~(np.isfinite(joint_s) & np.isfinite(joint_t) & (g_s * joint_s + g_t * joint_t > 0.0))
            alone_s = ~held_s & (held_t | (bad & ((iteration % 2 == 0) | held_t)))
            alone_t = ~held_t & ~alone_s & (held_s | bad)
            d_s = np.where(held_s | alone_t, 0.0, np.where(alone_s, -g_s / h_ss, joint_s))
            d_t = np.where(held_t | alone_s, 0.0, np.where(alone_t, -g_t / h_tt, joint_t))
        step = np.ones_like(s)
        for _ in range(60):                                   # halve until not worse
            s_new = np.maximum(s + step * d_s, 0.0)
            t_new = np.maximum(theta + step * d_t, THETA_MIN)
            with np.errstate(invalid="ignore"):
                new = _terms(s_new, t_new, f, b, rate)[0]
            ok = np.isfinite(new) & (new >= value - 1e-12)
            if ok.all():
                break
            step = np.where(ok, step, 0.5 * step)
        s, theta = np.where(ok, s_new, s), np.where(ok, t_new, theta)
    value = _terms(s, theta, f, b, rate)[0]
    ok = _optimal(s, theta, f, b, rate, vary_s)
    return np.where(ok, s, np.nan), theta, np.where(ok, value, np.nan)


GRADIENT_TOLERANCE = 1e-9   # a slope this small against the terms it sums is zero (``_optimal``)
ULPS = 8                    # ... or within its change across this many units in the last place of the variable


def _optimal(s: np.ndarray, theta: np.ndarray, f: np.ndarray, b: np.ndarray, rate: BackgroundRate,
             vary_s: bool) -> np.ndarray:
    """Whether each row is its maximum: the Kuhn–Tucker conditions of a concave function on the region, each slope
    zero, or pointing out of the region at a bound (s = 0, θ = ``THETA_MIN``), within ``GRADIENT_TOLERANCE`` of the
    terms it sums, and within the slope's own resolution: its change across ``ULPS`` units in the last place of the
    variable (curvature × ε × the variable; with a background known to 10⁻⁵ the pull's slope moves by 2 × 10⁻⁶ per
    unit of θ, which no float θ resolves). NA15-01: the fit had returned without any such check."""
    d = s[:, None] * f + theta[:, None] * b
    sigma = np.where(theta > rate.centre, rate.plus, rate.minus)
    g_s = -1.0 + (f / d).sum(axis=1)
    g_t = -rate.total + (b / d).sum(axis=1) - (theta - rate.centre) / sigma ** 2
    epsilon = ULPS * np.finfo(float).eps
    allow_s = GRADIENT_TOLERANCE * (1.0 + (f / d).sum(axis=1)) + \
        epsilon * np.maximum(s, 1.0) * (f * f / (d * d)).sum(axis=1)
    allow_t = GRADIENT_TOLERANCE * (rate.total + (b / d).sum(axis=1) + np.abs(theta - rate.centre) / sigma ** 2) + \
        epsilon * np.maximum(theta, THETA_MIN) * ((b * b / (d * d)).sum(axis=1) + 1.0 / sigma ** 2)
    ok_s = ~np.full(s.shape, vary_s) | (np.abs(g_s) <= allow_s) | ((s <= 0.0) & (g_s <= allow_s))
    ok_t = (np.abs(g_t) <= allow_t) | ((theta <= THETA_MIN) & (g_t <= allow_t))
    return ok_s & ok_t & np.isfinite(s) & np.isfinite(theta)


THETA_START = 1e-2       # the Newton iteration starts from θ = max(a, this): θ must stay positive (audit M5)


def null_fit(b: np.ndarray, rate: BackgroundRate) -> tuple[float, float]:
    """(θ̂₀, ln L) of the background alone: s = 0, θ profiled from a strictly positive start."""
    b = np.asarray(b, float)[None, :]
    start = np.array([max(rate.centre, THETA_START)])
    _, theta, value = _newton(np.zeros(1), start, np.zeros_like(b), b[0], rate, vary_s=False)
    return float(theta[0]), float(value[0])


def best_fits(f: np.ndarray, b: np.ndarray, rate: BackgroundRate) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(ŝ, θ̂, Δ ln L) for each row of f, with θ profiled; Δ ln L against the background alone.

    The profile in s is concave, so ŝ > 0 exactly where its slope at s = 0 (with θ at
    the background-only θ̂₀) is positive; elsewhere ŝ = 0 and Δ ln L = 0.
    """
    f = np.atleast_2d(np.asarray(f, float))
    b = np.asarray(b, float)
    theta0, value0 = null_fit(b, rate)
    s_hat, theta_hat, gain = np.zeros(f.shape[0]), np.full(f.shape[0], theta0), np.zeros(f.shape[0])
    rising = (f / (theta0 * b)).sum(axis=1) > 1.0 if f.shape[1] else np.zeros(f.shape[0], bool)
    if rising.any():
        rows = f[rising]
        start = _held_maximum(rows, theta0 * b)        # s's maximum with θ held at θ̂₀: near the joint one (NA15-01)
        s, theta, value = _newton(start, np.full(rows.shape[0], theta0), rows, b, rate, vary_s=True)
        s_hat[rising], theta_hat[rising], gain[rising] = s, theta, np.maximum(value - value0, 0.0)
    return s_hat, theta_hat, gain


def _held_maximum(f: np.ndarray, background: np.ndarray, iterations: int = 80) -> np.ndarray:
    """Each row's ŝ with the background held: the root of Σ f_i/(s f_i + b_i) = 1, by bisection on [0, n], since the
    sum is below n/s (n the events); where the slope at 0 is not positive, 0. The start of the joint fit, which from
    the slope's linearisation at s = 0 (240 for one event on 0.004 background events) had stepped into the corner where
    every term of ln L diverges."""
    low, high = np.zeros(f.shape[0]), np.full(f.shape[0], float(f.shape[1]) + 1.0)
    for _ in range(iterations):
        mid = 0.5 * (low + high)
        rising = (f / (mid[:, None] * f + background)).sum(axis=1) > 1.0
        low, high = np.where(rising, mid, low), np.where(rising, high, mid)
    return 0.5 * (low + high)


def profile(s: np.ndarray, f: np.ndarray, b: np.ndarray, rate: BackgroundRate) -> np.ndarray:
    """max over θ of ln L(s, θ) at each s, for one candidate's f."""
    s = np.atleast_1d(np.asarray(s, float))
    f = np.asarray(f, float)
    rows = np.broadcast_to(f, (s.size, f.size))
    theta0, _ = null_fit(b, rate)
    return _newton(s, np.full(s.size, theta0), rows, np.asarray(b, float), rate, vary_s=False)[2]


def toy_centre(theta0: float, rate: BackgroundRate, rng: np.random.Generator) -> float:
    """The auxiliary measurement of one toy, drawn from the density the likelihood uses (audit M5).

    The likelihood's pull uses σ₊ for a < θ and σ₋ for a > θ, so a lies below θ̂₀ with probability
    σ₊/(σ₊ + σ₋), not ½ (``statistics.native_pair.auxiliary_toy``, which this reuses). The draw is not clipped:
    a measurement can fall at or below zero, and θ, not a, must stay positive.
    """
    from types import SimpleNamespace
    from adroit.statistics.native_pair import auxiliary_toy
    return auxiliary_toy(theta0, SimpleNamespace(sigma_plus=rate.plus, sigma_minus=rate.minus), rng)

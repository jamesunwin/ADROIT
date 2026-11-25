"""The global significance of a signal, over the whole library of candidates (DM6).

Toy experiments are drawn from the background alone, every candidate is
fitted to each (``signal_fit.best_fits``), and the largest local
significance is recorded. The global p-value of an observed maximum
Z_obs is the fraction of toys that reach it. This is LZ's procedure
(arXiv:2609.02823, supplement).

When the background expects much less than one event in the search window
(LZ's nuclear-recoil band above ~100 keV), almost every toy is empty, and
the toys with one event decide. For them there is a closed form, used where
one event was observed and the toys as a check:

    p_global ≈ 1 − exp(−∫ b(E) · 1[max_k Z_k(E) ≥ Z_obs] dE),

where Z_k(E) is candidate k's local significance for one event at E. It holds
for Z_obs > 0 only: every outcome, the empty one included, reaches Z_obs = 0
(p = 1). Where more than one event was observed, or no single event reaches
Z_obs, it does not hold, and the toys decide (``signal._toy_significance``).

Where the search states an uncertainty on its background count (``rate``),
each toy is drawn with the background at the data's background-only fit θ̂₀,
its auxiliary measurement is drawn afresh about θ̂₀ from the density the
likelihood uses (``nuisance.toy_centre``), and every fit profiles θ, as on
the data.

**The Monte Carlo uncertainty.** With k of N toys at or above the observed
maximum, p̂ = k/N carries a binomial uncertainty, reported as the exact
(Clopper–Pearson) 95% interval (``p_interval``). When no toy reaches it, the
95% upper bound is 1 − 0.05^{1/N} ≈ 3/N, and Z is a lower bound from it.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.special import ndtri

from adroit.inference import nuisance, signal_fit
from adroit.inference.nuisance import BackgroundRate


def max_significance(shapes: np.ndarray, energies: np.ndarray, events: np.ndarray,
                     background: np.ndarray, rate: BackgroundRate | None = None) -> float:
    """The largest local significance over the candidates for these events."""
    if events.size == 0:                        # no events: no signal can rise, θ free or not
        return 0.0
    f = np.array([np.interp(events, energies, row, left=0.0, right=0.0) for row in shapes])
    _, gain = signal_fit.best_fits(f, np.interp(events, energies, background), rate=rate)
    z = float(np.sqrt(2.0 * gain.max()))
    if not np.isfinite(z):                       # a failed fit must never score as Z = 0 (audit M5)
        raise ArithmeticError("a toy's fit gave no finite significance")
    return z


def toys(shapes: np.ndarray, energies: np.ndarray, background: np.ndarray, n_toys: int,
         seed: int = 20260930, rate: BackgroundRate | None = None, theta0: float = 1.0) -> np.ndarray:
    """The maximum local significance in each of ``n_toys`` background-only toys.

    ``background`` is the nominal background density b(E) on ``energies``
    (events/keV). With a free ``rate``, the toys are drawn from θ̂₀ b(E) and each
    has its own auxiliary measurement. Events are drawn exactly from b, linear in
    each cell as the likelihood and the closed form read it
    (``native_pair.sample_linear_density``; the independent audit, NA15-06,
    2026-11-16: the cumulative's linear inverse had drawn them uniformly within a
    cell, so p depended on the grid, 0.0275 on two nodes against 0.0100 on 101
    for one linear spectrum).
    """
    from adroit.statistics.native_pair import sample_linear_density
    rng = np.random.default_rng(seed)
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (background[1:] + background[:-1])
                                           * np.diff(energies))])
    free = rate is not None and rate.free
    counts = rng.poisson((theta0 if free else 1.0) * cdf[-1], n_toys)
    out = np.zeros(n_toys)
    for i in np.nonzero(counts)[0]:
        events = sample_linear_density(energies, background, int(counts[i]), rng)
        toy_rate = rate.model_copy(update={"centre": nuisance.toy_centre(theta0, rate, rng)}) if free else None
        out[i] = max_significance(shapes, energies, events, background, toy_rate)
    return out


def one_event_p_value(z_observed: float, shapes: np.ndarray, energies: np.ndarray,
                      background: np.ndarray) -> float:
    """The closed form for a background that rarely gives more than one event, where one event was observed. A
    maximum of 0σ or less is reached by every outcome, the empty one included: p = 1 (the audit loop's AL1-02: the
    form, 1 − e^(−B) there, counts only the outcomes with an event)."""
    if z_observed <= 0.0:
        return 1.0
    b = background
    z = np.array([max_significance(shapes, energies, np.array([e]), b) if b_e > 0 else 0.0
                  for e, b_e in zip(energies, b)])
    return 1.0 - math.exp(-_reaching_mass(z >= z_observed, z_observed, shapes, energies, b))


EDGE_STEPS = 30          # bisections of a cell that holds the reaching region's edge: 2⁻³⁰ of the cell


def _reaching_mass(inside: np.ndarray, z_observed: float, shapes: np.ndarray, energies: np.ndarray,
                   background: np.ndarray) -> float:
    """∫ b(E) 1[max_k Z_k(E) ≥ Z_obs] dE, with b linear in each cell, as the toys draw their events (``toys``). A
    cell whose ends lie on either side of the region's edge is integrated to the edge, found by bisection on one
    event's significance there (AL2-19: integrated by the trapezoid rule, such a cell counted half of itself whatever
    the edge, and p came out 6–9% above the toys'). One edge per cell is assumed, as the nodes resolve the shapes."""
    mass = 0.0
    for k in range(len(energies) - 1):
        e0, e1, b0, b1 = energies[k], energies[k + 1], background[k], background[k + 1]
        if inside[k] and inside[k + 1]:
            mass += 0.5 * (b0 + b1) * (e1 - e0)
        elif inside[k] != inside[k + 1]:
            lo, hi = e0, e1                                   # lo on e0's side of the edge, hi on e1's
            for _ in range(EDGE_STEPS):
                mid = 0.5 * (lo + hi)
                reached = bool(np.interp(mid, energies, background) > 0) and \
                    max_significance(shapes, energies, np.array([mid]), background) >= z_observed
                lo, hi = (mid, hi) if reached == bool(inside[k]) else (lo, mid)
            edge = 0.5 * (lo + hi)
            b_edge = b0 + (b1 - b0) * (edge - e0) / (e1 - e0)
            mass += 0.5 * (b0 + b_edge) * (edge - e0) if inside[k] else 0.5 * (b_edge + b1) * (e1 - edge)
    return float(mass)


def several_events(expected: float) -> float:
    """P(N ≥ 2) of a Poisson background expecting ``expected`` events: what the one-event closed form leaves out (about
    B²/2 for a small B; AL3-06: with one event at the best place a single event can be, the closed form's p had been
    orders below the toys', 5.7σ for 3.3σ at B = 0.09)."""
    b = float(expected)
    return float(-math.expm1(-b) - b * math.exp(-b)) if b > 0 else 0.0


def p_interval(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """The exact binomial (Clopper–Pearson) interval on p from k of n toys; for k = 0 the one-sided upper bound
    1 − (1 − level)^{1/n} ≈ 3/n at 95%."""
    from scipy.stats import beta
    if n <= 0 or not 0 <= k <= n:
        raise ValueError("k of n toys needs 0 ≤ k ≤ n and n > 0")
    if k == 0:
        return 0.0, 1.0 - (1.0 - level) ** (1.0 / n)
    alpha = 1.0 - level
    upper = 1.0 if k == n else float(beta.ppf(1.0 - alpha / 2, k + 1, n - k))
    return float(beta.ppf(alpha / 2, k, n - k + 1)), upper


def p_to_z(p: float) -> float:
    """The one-sided significance of a p-value."""
    return float(-ndtri(p)) if 0.0 < p < 1.0 else (math.inf if p <= 0.0 else 0.0)

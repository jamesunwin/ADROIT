"""Signal fits: an extended unbinned likelihood in recoil energy (DM6).

For a candidate interaction with normalised spectral density f(E) in a
search, s expected signal events, and a background of density b(E) with
total B, the likelihood of events at energies E_i is

    ln L(s) = −(s + B) + Σ_i ln[s f(E_i) + b(E_i)] .

The signal density is smeared at each event by the search's energy
resolution σ where one is given, and normalised on the window as seen:
s counts the events reconstructed inside the window, and ``seen_events`` is
that count at the stated couplings, against which s is turned into a
coupling (the external audit of 2026-10-16, A09). The smearing and the
window's share are integrated exactly for the piecewise-linear density
(``experiments.base.smear``, ``_below``), so a width narrower than the grid's
spacing gives the unsmeared density, wherever the events sit on the grid
(the external audit of 2026-10-17, R17-3: the Gaussian had been sampled on
the grid). One width serves the whole window; an energy-dependent one is
refused (``_resolution``). The fit maximises ln L over s ≥ 0.
- The local significance is Z = √q₀, with q₀ = 2[ln L(ŝ) − ln L(0)].
- Intervals are two-sided profile-likelihood intervals with the asymptotic
  thresholds of χ²₁.

The background enters only through b at the observed events, so a search
with a well-modelled background density supplies it, and one without supplies
an approximation, which it must state (``LzExtendedWindow`` uses one density,
calibrated from a published significance). Every candidate is fitted with
the same background: the comparison between candidates is fair whatever that
background is.

Where a search states an uncertainty on its background count (``rate``, a
``nuisance.BackgroundRate``), the background is θ b(E) with θ constrained by
that statement and profiled (``nuisance``); every function here then works with
the profile likelihood. Without one, the background is fixed, as above.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr, ndtri

from adroit.core.dm_state import ExpectedSignal
from adroit.core.state import StrictModel
from adroit.inference import nuisance
from adroit.inference.nuisance import BackgroundRate

S_MAX = 1e4          # the largest signal count the fit considers


class SignalFit(StrictModel):
    """The fit of one candidate to the events of one search."""

    label: str
    s_hat: float                        # the best-fit signal count
    delta_log_l: float                  # ln L(ŝ) − ln L(0), ≥ 0
    z_local: float                      # √(2 Δ ln L), 0 when ŝ = 0
    interval_68: tuple[float, float]    # on the signal count, two-sided
    interval_90: tuple[float, float]
    theta_hat: float = 1.0              # the background's scale at the best fit (1: fixed)


def _resolution(resolution_kev: np.ndarray | float) -> float:
    """The search's one resolution width σ (keV; 0: none). Widths that differ from event to event are refused: the
    smearing evaluates σ at the seen energy, and normalising that on the window needs σ everywhere in it, not at the
    events (the external audit of 2026-10-17, R17-3: the events' median had stood in, which does not normalise an
    energy-dependent kernel). Every built-in search has one width (``SearchModule.resolution_on_grid``)."""
    sigma = np.atleast_1d(np.asarray(resolution_kev, float))
    if not sigma.size:
        return 0.0
    if not np.all(np.isfinite(sigma)) or np.any(sigma < 0.0):
        raise ValueError(f"a resolution width must be finite and non-negative, not {sigma.min():g}–{sigma.max():g} keV")
    if np.ptp(sigma) > 1e-12 * float(sigma.max()):
        raise ValueError(f"an energy-dependent resolution ({sigma.min():g}–{sigma.max():g} keV) is not supported: "
                         "its normalisation on the window is not computed")
    return float(sigma[0])


def _below(energies: np.ndarray, density: np.ndarray, edge: float, sigma: float) -> float:
    """∫ p(E) Φ((edge − E)/σ) dE for the piecewise-linear interpolant p: the events seen below ``edge``. On each
    segment p = α + sE, and with w = (edge − E)/σ, ∫Φ dw = wΦ + φ and ∫wΦ dw = [(w² − 1)Φ + wφ]/2, so the segment
    gives σ[(α + s·edge) ΔI₀ − sσ ΔI₁], exactly whatever σ is against the spacing."""
    e0, e1 = energies[:-1], energies[1:]
    slope = np.diff(density) / np.diff(energies)
    alpha = density[:-1] - slope * e0
    w_a, w_b = (edge - e0) / sigma, (edge - e1) / sigma
    phi_a, phi_b = np.exp(-0.5 * w_a ** 2) / math.sqrt(2 * math.pi), np.exp(-0.5 * w_b ** 2) / math.sqrt(2 * math.pi)
    big_a, big_b = ndtr(w_a), ndtr(w_b)
    i0 = (w_a * big_a + phi_a) - (w_b * big_b + phi_b)
    i1 = ((w_a ** 2 - 1) * big_a + w_a * phi_a - (w_b ** 2 - 1) * big_b - w_b * phi_b) / 2
    return float(np.sum(sigma * ((alpha + slope * edge) * i0 - slope * sigma * i1)))


def seen_fraction(energies_kev: np.ndarray, density: np.ndarray, resolution_kev: np.ndarray | float = 0.0) -> float:
    """ε_W: the share of the window's events (true energy E in W = [E_lo, E_hi]) that are also seen inside it.

    ε_W = ∫_W f(E) [Φ((E_hi − E)/σ) − Φ((E_lo − E)/σ)] dE, with f the density normalised on W and σ the
    search's resolution (``_resolution``), integrated exactly (``_below``); 1 without a resolution. Events from
    outside W in true energy that are smeared into it are not modelled: a search's density is given on its window
    only.
    """
    energies, density = np.asarray(energies_kev, float), np.asarray(density, float)
    total, sigma = float(np.trapezoid(density, energies)), _resolution(resolution_kev)
    if total <= 0.0 or sigma <= 0.0:
        return 1.0
    return (_below(energies, density, energies[-1], sigma) - _below(energies, density, energies[0], sigma)) / total


def seen_events(energies_kev: np.ndarray, density: np.ndarray, resolution_kev: np.ndarray | float = 0.0) -> float:
    """The events seen inside the window at the stated couplings, ε_W ∫_W density: what a fitted s is measured
    against (μ² = ŝ / this)."""
    density = np.asarray(density, float)
    return float(np.trapezoid(density, np.asarray(energies_kev, float))) * seen_fraction(energies_kev, density,
                                                                                          resolution_kev)


def event_densities(energies_kev: np.ndarray, density: np.ndarray, events_kev: np.ndarray,
                    resolution_kev: np.ndarray | float = 0.0) -> np.ndarray:
    """The signal density at each event, smeared by the resolution and normalised on the window (per keV).

    f̃(e) = ∫_W f(E) G(e − E; σ) dE / ε_W, so that ∫_W f̃ de = 1 and the likelihood's s is the count seen inside
    the window (``seen_fraction``). The integral is exact for the piecewise-linear density
    (``experiments.base.smear``), so as σ → 0 it goes smoothly to the unsmeared density, wherever an event sits
    on the grid. The toys use the same operation on the grid (``orchestrator.signal._smeared``). Before the
    audit's A09 the leak across the window's edges was taken out of f̃ but not out of s; before its R17-3 the
    Gaussian was sampled on the grid, which a width narrower than the spacing falls between.
    """
    from adroit.experiments.base import smear
    energies, density = np.asarray(energies_kev, float), np.asarray(density, float)
    total = float(np.trapezoid(density, energies))
    if total <= 0.0:
        return np.zeros(len(np.atleast_1d(events_kev)))
    shape = density / total
    events = np.atleast_1d(np.asarray(events_kev, float))
    sigma = _resolution(resolution_kev)
    if sigma <= 0.0:
        return np.interp(events, energies, shape, left=0.0, right=0.0)
    return smear(energies, shape, events, sigma) / seen_fraction(energies, shape, sigma)


def true_energy(signal: ExpectedSignal) -> ExpectedSignal:
    """The signal, if its density is in true energy; one already in reconstructed energy is refused, since smearing
    it would apply the resolution twice."""
    if signal.energy_scale != "true":
        raise ValueError(f"{signal.experiment}'s signal is already in reconstructed energy; it is not smeared again")
    return signal


def log_likelihood(s: float | np.ndarray, f: np.ndarray, b: np.ndarray) -> np.ndarray:
    """ln L(s) up to the constant −B: −s + Σ ln(s f_i + b_i)."""
    s = np.atleast_1d(np.asarray(s, float))
    return -s + np.log(np.outer(s, f) + b).sum(axis=1)


def _free(rate: BackgroundRate | None) -> bool:
    return rate is not None and rate.free


def profile_log_likelihood(s: float | np.ndarray, f: np.ndarray, b: np.ndarray,
                           rate: BackgroundRate | None = None) -> np.ndarray:
    """ln L(s), with θ profiled where the background's rate is uncertain (else ``log_likelihood``)."""
    if not _free(rate):
        return log_likelihood(s, f, b)
    found = nuisance.profile(s, np.asarray(f, float), np.asarray(b, float), rate)
    if not np.isfinite(found).all():                   # never a profile that is not its maximum (NA15-01)
        raise ValueError("the background's rate could not be profiled to its maximum")
    return found


def best_fit(f: np.ndarray, b: np.ndarray) -> float:
    """ŝ ≥ 0: the root of Σ f_i/(s f_i + b_i) = 1, or 0 if the slope at 0 is not positive."""
    f, b = np.asarray(f, float), np.asarray(b, float)
    if f.size == 0 or np.sum(f / b) <= 1.0:
        return 0.0
    return brentq(lambda s: np.sum(f / (s * f + b)) - 1.0, 0.0, S_MAX)


def interval(f: np.ndarray, b: np.ndarray, s_hat: float, threshold: float,
             rate: BackgroundRate | None = None) -> tuple[float, float]:
    """Where 2[ln L(ŝ) − ln L(s)] ≤ threshold, two-sided, on s ≥ 0 (θ profiled if ``rate`` is free)."""
    top = float(profile_log_likelihood(s_hat, f, b, rate)[0])

    def q(s: float) -> float:
        return 2.0 * (top - float(profile_log_likelihood(s, f, b, rate)[0])) - threshold

    upper = brentq(q, s_hat, S_MAX) if q(S_MAX) > 0 else math.inf
    lower = brentq(q, 0.0, s_hat) if s_hat > 0 and q(0.0) > 0 else 0.0
    return lower, upper


def fit(label: str, f: np.ndarray, b: np.ndarray, rate: BackgroundRate | None = None) -> SignalFit:
    """The full fit of one candidate: best fit, local significance and intervals."""
    f, b = np.asarray(f, float), np.asarray(b, float)
    if _free(rate):
        s_hats, thetas, gains = nuisance.best_fits(f[None, :], b, rate)
        s_hat, theta, gain = float(s_hats[0]), float(thetas[0]), float(gains[0])
        if not (math.isfinite(s_hat) and math.isfinite(gain)):     # unresolved, never published (NA15-01)
            raise ValueError("the fit with the background's rate profiled did not reach its maximum")
    else:
        s_hat, theta = best_fit(f, b), 1.0
        gain = float(log_likelihood(s_hat, f, b)[0] - log_likelihood(0.0, f, b)[0]) if f.size else 0.0
        gain = max(gain, 0.0)
    return SignalFit(label=label, s_hat=s_hat, delta_log_l=gain, z_local=math.sqrt(2.0 * gain),
                     interval_68=interval(f, b, s_hat, ndtri(0.84) ** 2, rate),
                     interval_90=interval(f, b, s_hat, ndtri(0.95) ** 2, rate), theta_hat=theta)


def best_fits(f: np.ndarray, b: np.ndarray, iterations: int = 80,
              rate: BackgroundRate | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(ŝ, Δ ln L) for many candidates at once: rows of f are candidates, columns events.

    Vectorised bisection on the score, for the injection tests and the toys; with a
    free background rate, θ is profiled (``nuisance.best_fits``).
    """
    if _free(rate):
        s_hat, _, gain = nuisance.best_fits(f, np.broadcast_to(np.asarray(b, float), np.shape(f)[-1:]), rate)
        return s_hat, gain
    f = np.atleast_2d(np.asarray(f, float))
    b = np.broadcast_to(np.asarray(b, float), f.shape[1:])
    positive = (f / b).sum(axis=1) > 1.0
    low, high = np.zeros(f.shape[0]), np.full(f.shape[0], S_MAX)
    for _ in range(iterations):
        mid = 0.5 * (low + high)
        slope = (f / (mid[:, None] * f + b)).sum(axis=1) - 1.0
        low, high = np.where(slope > 0, mid, low), np.where(slope > 0, high, mid)
    s_hat = np.where(positive, 0.5 * (low + high), 0.0)
    gain = (-s_hat + np.log(s_hat[:, None] * f + b).sum(axis=1)) - np.log(b).sum()
    return s_hat, np.maximum(gain, 0.0)

"""Independent references for SHM++ (halo phase 2), written apart from ``adroit.halo_models.shm_plus_plus`` and sharing
none of its code. The Galactic distribution is transcribed again from arXiv:1810.11468 (Eqs. 1–7, with erfi as the paper
writes it), and its moments in a moving frame are computed without the generator's reduction to an angle about the boost:

- ``cubature``: randomised quasi-Monte Carlo in the Galactic frame. Scrambled Sobol points are mapped to the untruncated
  Gaussian, which is the importance density; the escape cut is an indicator, and each component is normalised by its own
  samples (its N_esc is not used). It gives η(v_min) and η⊥(v_min) in the moving frame, the laboratory velocity being
  v − boost.
- ``lattice_speed``: F(u) = u² ∮ f(u n̂ + boost) dΩ on a spherical Fibonacci lattice in the Galactic axes, not aligned with
  the boost.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import erf, erfi
from scipy.stats import norm, qmc


def sigmas(v0: float, beta: float, component: str) -> np.ndarray:
    """The Gaussian's dispersions along (x radial, y rotation, z north), km/s (Eqs. 1, 6)."""
    if component == "round":
        return np.full(3, v0 / math.sqrt(2.0))
    radial = math.sqrt(3.0 * v0 * v0 / (2.0 * (3.0 - 2.0 * beta)))
    tangential = math.sqrt(3.0 * v0 * v0 * (1.0 - beta) / (2.0 * (3.0 - 2.0 * beta)))
    return np.array([radial, tangential, tangential])


def normalisation(v0: float, v_esc: float, beta: float, component: str) -> float:
    """N_esc as Eqs. 2 and 7 write it."""
    if component == "round":
        s = v0 / math.sqrt(2.0)
        return math.erf(v_esc / (math.sqrt(2.0) * s)) - math.sqrt(2.0 / math.pi) * v_esc / s * math.exp(-v_esc ** 2 / (2 * s * s))
    radial, tangential, _ = sigmas(v0, beta, component)
    x = v_esc / (math.sqrt(2.0) * radial)
    return float(erf(x) - math.sqrt((1 - beta) / beta) * math.exp(-v_esc ** 2 / (2 * tangential ** 2))
                 * erfi(x * math.sqrt(beta / (1 - beta))))


def density(v: np.ndarray, v0: float, v_esc: float, beta: float, component: str) -> np.ndarray:
    """The normalised, truncated f_R or f_S at Galactic velocities v (…, 3)."""
    s = sigmas(v0, beta, component)
    exponent = np.sum((v / s) ** 2, axis=-1) / 2.0
    f = np.exp(-exponent) / ((2 * math.pi) ** 1.5 * np.prod(s) * normalisation(v0, v_esc, beta, component))
    return np.where(np.sum(v * v, axis=-1) < v_esc ** 2, f, 0.0)


def cubature(v_mins: np.ndarray, boost: np.ndarray, v0: float, v_esc: float, beta: float, eta: float,
             points: int = 2 ** 18, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """(η, η⊥) of the mixture in the frame moving at ``boost``, at each v_min (s/km, km/s)."""
    v_mins = np.atleast_1d(np.asarray(v_mins, dtype=float))
    total_eta, total_perp = np.zeros(v_mins.size), np.zeros(v_mins.size)
    for component, weight in (("round", 1.0 - eta), ("sausage", eta)):
        if weight == 0.0:
            continue
        z = norm.ppf(qmc.Sobol(3, scramble=True, seed=seed + (component == "sausage")).random(points))
        v = z * sigmas(v0, beta, component)
        inside = np.sum(v * v, axis=1) < v_esc ** 2
        speed = np.linalg.norm(v - boost, axis=1)
        share = inside.mean()
        for i, v_min in enumerate(v_mins):
            sel = inside & (speed > v_min)
            total_eta[i] += weight * np.mean(np.where(sel, 1.0 / speed, 0.0)) / share
            total_perp[i] += weight * np.mean(np.where(sel, (speed ** 2 - v_min ** 2) / speed, 0.0)) / share
    return total_eta, total_perp


def lattice_speed(speeds: np.ndarray, boost: np.ndarray, v0: float, v_esc: float, beta: float, eta: float,
                  points: int = 200_000) -> np.ndarray:
    """F(u) of the mixture on a spherical Fibonacci lattice of ``points`` directions in the Galactic axes."""
    i = np.arange(points) + 0.5
    z = 1.0 - 2.0 * i / points
    r = np.sqrt(1.0 - z * z)
    phi = math.pi * (1.0 + math.sqrt(5.0)) * i
    directions = np.stack([r * np.cos(phi), r * np.sin(phi), z], axis=1)
    out = []
    for u in np.atleast_1d(speeds):
        v = u * directions + boost
        f = (1.0 - eta) * density(v, v0, v_esc, beta, "round") + \
            (eta * density(v, v0, v_esc, beta, "sausage") if eta > 0 else 0.0)
        out.append(u * u * 4.0 * math.pi * float(np.mean(f)))
    return np.array(out)

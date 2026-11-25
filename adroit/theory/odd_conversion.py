"""Tree-level chi chi <-> phi phi* conversion for the existing eR Majorana family."""

from __future__ import annotations
from functools import lru_cache
import math
import numpy as np
from scipy.special import kve
from adroit.constraints import processes as pr
from adroit.constraints.amplitudes import _BASIS, bar, slash, spinor_u
from adroit.constraints.relic import thermal_average


def conversion_chain(
    chi: np.ndarray, phi: np.ndarray, antiphi: np.ndarray, mf: float
) -> np.ndarray:
    """Charge-conjugated t/u fermion exchange chain, with unit Yukawa coupling."""
    qt, qu = chi - phi, chi - antiphi
    return (
        pr.P_R @ slash(qt) @ pr.P_L / (pr._dot(qt, qt) - mf * mf)[:, None, None]
        + pr.P_L @ slash(qu) @ pr.P_R / (pr._dot(qu, qu) - mf * mf)[:, None, None]
    )


def squared(
    chi1: np.ndarray, chi2: np.ndarray, phi: np.ndarray, antiphi: np.ndarray, m: float, mf: float
) -> np.ndarray:
    """Majorana spin sum including both diagrams; no initial average or final symmetry."""
    chain = conversion_chain(chi1, phi, antiphi, mf)
    total = np.zeros(len(chi1))
    for xi in _BASIS:
        one = spinor_u(chi1[:, 1:], m, xi)
        for eta in _BASIS:
            two = bar(pr.conjugate(spinor_u(chi2[:, 1:], m, eta)))
            total += abs(np.einsum("ni,nij,nj->n", two, chain, one)) ** 2
    return total


@lru_cache(maxsize=16)
def _angular_nodes(nodes: int) -> tuple[np.ndarray, np.ndarray]:
    x, w = np.polynomial.legendre.leggauss(nodes)
    x.setflags(write=False)
    w.setflags(write=False)
    return x, w


def cross_section(
    s: float, m: float, M: float, mf: float, y: float, reverse: bool = False, nodes: int = 64
) -> float:
    """Forward spin average 1/4; reverse identical-Majorana final factor 1/2."""
    if (
        not all(math.isfinite(v) for v in (s, m, M, mf, y))
        or min(s, m, M) <= 0
        or mf < 0
        or nodes < 8
    ):
        raise ValueError("finite positive energy/masses and valid quadrature required")
    if math.sqrt(s) <= 2 * max(m, M):
        return 0.0
    x, w = _angular_nodes(nodes)
    if reverse:
        phi, antiphi, chi1, chi2, p, k = pr.frame(s, M, M, m, m, x)
    else:
        chi1, chi2, phi, antiphi, p, k = pr.frame(s, m, m, M, M, x)
    amplitude = squared(chi1, chi2, phi, antiphi, m, mf)
    return y**4 * pr._sigma(amplitude if reverse else amplitude / 4, w, s, p, k, reverse)


def thermal_rate(m: float, M: float, mf: float, y: float, x: float, refined: bool = False) -> float:
    """Actual chi-chi thermal average, including the endothermic partner-pair threshold."""
    if not all(math.isfinite(v) for v in (m, M, mf, y, x)) or min(m, M, x) <= 0 or mf < 0 or M <= m:
        raise ValueError("finite inputs, positive x and a heavier scalar required")
    return y**4 * _unit_rate(m, M, mf, x, refined)


@lru_cache(maxsize=2048)
def _unit_rate(m: float, M: float, mf: float, x: float, refined: bool) -> float:
    u, sigma = _cross_section_table(m, M, mf, refined)
    return float(thermal_average(u, sigma, np.array([x]))[0])


@lru_cache(maxsize=128)
def _cross_section_table(
    m: float, M: float, mf: float, refined: bool
) -> tuple[np.ndarray, np.ndarray]:
    low = max(M / m - 1, 0.0)
    # Resolve the threshold separately instead of integrating across a masked onset.
    u = low + np.r_[0.0, np.geomspace(1e-9, 80.0, 1801 if refined else 901)]
    sigma = np.array(
        [
            cross_section(
                float((2 * m * (1 + v)) ** 2), m, M, mf, 1.0, nodes=128 if refined else 64
            )
            for v in u
        ]
    )
    u.setflags(write=False)
    sigma.setflags(write=False)
    return u, sigma


def equilibrium_relaxation(
    m: float, M: float, mf: float, y: float, x: float, refined: bool = False
) -> tuple[float, float]:
    """(sigma v, relaxation GeV) from linearizing both number-conserving collision terms."""
    sv = thermal_rate(m, M, mf, y, x, refined)
    T = m / x
    r = (M / m) ** 2 * kve(2, x * M / m) / kve(2, x) * math.exp(-x * (M / m - 1))
    if r <= 0:
        raise ValueError("unresolved equilibrium partner population")
    density = 2 * m * m * T * kve(2, x) * math.exp(-x) / (2 * math.pi**2)
    return sv, float(2 * density * sv * (1 + 1 / r))

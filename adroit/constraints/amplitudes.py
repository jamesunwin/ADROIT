"""Tree-level 2 → 2 amplitudes from explicit Dirac matrices (DM7).

Dark matter χ (a Dirac fermion of mass m) annihilating through a spin-1
mediator Z′ of mass M, whose couplings to a fermion f are
−Z′_μ f̄ γ^μ (a_f + b_f γ⁵) f. Two processes enter the relic density:

- **s-channel, χχ̄ → f f̄:**
  M = [v̄(p₂) γ^μ(a_χ + b_χγ⁵) u(p₁)] P_μν(q) [ū(k₁) γ^ν(a_f + b_fγ⁵) v(k₂)],
  with the massive propagator P_μν = (−g_μν + q_μq_ν/M²)/(s − M² + iMΓ);
- **t- and u-channel, χχ̄ → Z′Z′:**
  M = v̄(p₂)[Γ(ε₂) S(p₁ − k₁) Γ(ε₁) + Γ(ε₁) S(p₁ − k₂) Γ(ε₂)]u(p₁),
  with Γ(ε) = ε̸(a_χ + b_χγ⁵) and S(ℓ) = (ℓ̸ + m)/(ℓ² − m²).

Spinors and polarisation vectors are written out in the Dirac representation
and the squares are summed over spins and polarisations numerically, in the
centre-of-momentum frame. Nothing is expanded in the velocity, so the result
holds at every energy, including the longitudinal modes of an axial
mediator. The analytic cross-sections of ``annihilation`` are checked
against these (tests/constraints/test_relic.py).

Metric (+, −, −, −); natural units, GeV.
"""

from __future__ import annotations

import numpy as np

_I2 = np.eye(2, dtype=complex)
_Z2 = np.zeros((2, 2), dtype=complex)
_PAULI = [np.array([[0, 1], [1, 0]], dtype=complex),
          np.array([[0, -1j], [1j, 0]], dtype=complex),
          np.array([[1, 0], [0, -1]], dtype=complex)]
GAMMA = np.array([np.block([[_I2, _Z2], [_Z2, -_I2]])]
                 + [np.block([[_Z2, s], [-s, _Z2]]) for s in _PAULI])
GAMMA5 = np.block([[_Z2, _I2], [_I2, _Z2]])
METRIC = np.array([1.0, -1.0, -1.0, -1.0])
_BASIS = (np.array([1.0, 0.0], dtype=complex), np.array([0.0, 1.0], dtype=complex))


_GAMMA_ROWS = GAMMA.reshape(4, 16)


def slash(a: np.ndarray) -> np.ndarray:
    """a̸ = γ^μ a_μ for four-vectors a^μ of shape (n, 4); returns (n, 4, 4). A matrix product rather than
    ``einsum``: the same numbers, several times faster on the generic route's stacked rows (F2)."""
    return ((a * METRIC) @ _GAMMA_ROWS).reshape(-1, 4, 4)


def _sigma_dot(p3: np.ndarray) -> np.ndarray:
    return np.einsum("ni,ijk->njk", p3, np.array(_PAULI))


def spinor_u(p3: np.ndarray, mass: float, xi: np.ndarray) -> np.ndarray:
    """u(p) = (√(E+m) ξ, σ·p ξ/√(E+m)) for momenta p3 of shape (n, 3)."""
    e = np.sqrt(mass ** 2 + np.sum(p3 ** 2, axis=1))
    root = np.sqrt(e + mass)[:, None]
    return np.concatenate([root * xi, (_sigma_dot(p3) @ xi) / root], axis=1)


def spinor_v(p3: np.ndarray, mass: float, eta: np.ndarray) -> np.ndarray:
    """v(p) = (σ·p η/√(E+m), √(E+m) η)."""
    e = np.sqrt(mass ** 2 + np.sum(p3 ** 2, axis=1))
    root = np.sqrt(e + mass)[:, None]
    return np.concatenate([(_sigma_dot(p3) @ eta) / root, root * eta], axis=1)


def bar(spinor: np.ndarray) -> np.ndarray:
    """ψ̄ = ψ† γ⁰."""
    return spinor.conj() @ GAMMA[0]


def polarisations(k: np.ndarray, mass: float) -> list[np.ndarray]:
    """The two transverse and the longitudinal polarisation vectors of a massive vector.

    ``k`` is (n, 4) with its spatial part in the x–z plane, as in ``_frame``; ``mass`` a number or one per row.
    The vectors are real, and Σ ε^μ ε^ν = −g^μν + k^μ k^ν / M².
    """
    kk = np.linalg.norm(k[:, 1:], axis=1)
    n = k[:, 1:] / kk[:, None]
    zero = np.zeros(len(k))
    e1 = np.stack([zero, n[:, 2], zero, -n[:, 0]], axis=1)
    e2 = np.stack([zero, zero, np.ones(len(k)), zero], axis=1)
    longitudinal = np.concatenate([(kk / mass)[:, None], (k[:, :1] / np.reshape(mass, (-1, 1))) * n], axis=1)
    return [e1, e2, longitudinal]


def _frame(s: float, m_in: float, m_out: float, cos_theta: np.ndarray):
    """Four-momenta p₁, p₂ (along ±z) and k₁, k₂ (at angle θ) in the CM frame."""
    root = np.sqrt(s)
    p = np.sqrt(max(s / 4.0 - m_in ** 2, 0.0))
    k = np.sqrt(max(s / 4.0 - m_out ** 2, 0.0))
    sin_theta = np.sqrt(1.0 - cos_theta ** 2)
    n = len(cos_theta)
    one = np.ones(n)
    p1 = np.stack([root / 2 * one, 0 * one, 0 * one, p * one], axis=1)
    p2 = p1 * np.array([1.0, -1.0, -1.0, -1.0])
    k1 = np.stack([root / 2 * one, k * sin_theta, 0 * one, k * cos_theta], axis=1)
    k2 = k1 * np.array([1.0, -1.0, -1.0, -1.0])
    return p1, p2, k1, k2, p, k


def _vertex(a: float, b: float) -> np.ndarray:
    return a * np.eye(4) + b * GAMMA5


def _current(left: np.ndarray, a: float, b: float, right: np.ndarray) -> np.ndarray:
    """J^μ = ψ̄_left γ^μ (a + bγ⁵) ψ_right, shape (n, 4)."""
    chiral = _vertex(a, b)
    return np.einsum("ni,mij,jk,nk->nm", left, GAMMA, chiral, right)


def _dot(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.sum(x * y * METRIC, axis=1)


def s_channel_squared(s: float, m: float, m_f: float, chi: tuple[float, float],
                      f: tuple[float, float], m_med: float, width: float,
                      cos_theta: np.ndarray) -> np.ndarray:
    """Spin-averaged |M|² of χχ̄ → f f̄ through the s-channel Z′, per final colour.

    Args:
        s: the squared CM energy (GeV²).
        m, m_f: the dark matter and final fermion masses.
        chi, f: the (vector, axial) couplings (a, b) of χ and of f.
        m_med, width: the mediator's mass and total width.
        cos_theta: the scattering angles.
    """
    p1, p2, k1, k2, _, _ = _frame(s, m, m_f, cos_theta)
    q = p1 + p2
    propagator = 1.0 / (s - m_med ** 2 + 1j * m_med * width)
    total = np.zeros(len(cos_theta))
    for x1 in _BASIS:
        for x2 in _BASIS:
            j_chi = _current(bar(spinor_v(p2[:, 1:], m, x2)), *chi, spinor_u(p1[:, 1:], m, x1))
            for y1 in _BASIS:
                for y2 in _BASIS:
                    j_f = _current(bar(spinor_u(k1[:, 1:], m_f, y1)), *f,
                                   spinor_v(k2[:, 1:], m_f, y2))
                    amp = (-_dot(j_chi, j_f)
                           + _dot(q, j_chi) * _dot(q, j_f) / m_med ** 2) * propagator
                    total += np.abs(amp) ** 2
    return total / 4.0


def pair_squared(s: float, m: float, m_med: float, chi: tuple[float, float],
                 cos_theta: np.ndarray) -> np.ndarray:
    """Spin-averaged, polarisation-summed |M|² of χχ̄ → Z′Z′ (t- and u-channel χ exchange)."""
    p1, p2, k1, k2, _, _ = _frame(s, m, m_med, cos_theta)
    chiral = _vertex(*chi)
    unit = np.eye(4)[None]
    prop_t = (slash(p1 - k1) + m * unit) / (_dot(p1 - k1, p1 - k1) - m ** 2)[:, None, None]
    prop_u = (slash(p1 - k2) + m * unit) / (_dot(p1 - k2, p1 - k2) - m ** 2)[:, None, None]
    total = np.zeros(len(cos_theta))
    for e1 in polarisations(k1, m_med):
        g1 = slash(e1) @ chiral
        for e2 in polarisations(k2, m_med):
            g2 = slash(e2) @ chiral
            chain = g2 @ prop_t @ g1 + g1 @ prop_u @ g2
            for x1 in _BASIS:
                u1 = spinor_u(p1[:, 1:], m, x1)
                for x2 in _BASIS:
                    v2 = bar(spinor_v(p2[:, 1:], m, x2))
                    total += np.abs(np.einsum("ni,nij,nj->n", v2, chain, u1)) ** 2
    return total / 4.0


def cross_section(squared: np.ndarray, weights: np.ndarray, s: float, p: float, k: float,
                  identical: bool) -> float:
    """σ = (k/p)/(32π s) ∫ |M|² d cos θ, halved for identical final particles."""
    sigma = (k / p) / (32.0 * np.pi * s) * float(np.sum(weights * squared))
    return 0.5 * sigma if identical else sigma


def s_channel_sigma(s: float, m: float, m_f: float, chi: tuple[float, float],
                    f: tuple[float, float], m_med: float, width: float, colours: int = 1,
                    points: int = 16) -> float:
    """σ(χχ̄ → f f̄) by Gauss–Legendre integration over the angle (GeV⁻²)."""
    if s <= 4.0 * max(m, m_f) ** 2:
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    squared = s_channel_squared(s, m, m_f, chi, f, m_med, width, x)
    return colours * cross_section(squared, w, s, np.sqrt(s / 4 - m ** 2),
                                   np.sqrt(s / 4 - m_f ** 2), identical=False)


def pair_sigma(s: float, m: float, m_med: float, chi: tuple[float, float],
               points: int = 32) -> float:
    """σ(χχ̄ → Z′Z′) by Gauss–Legendre integration over the angle (GeV⁻²)."""
    if s <= 4.0 * max(m, m_med) ** 2:
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    squared = pair_squared(s, m, m_med, chi, x)
    return cross_section(squared, w, s, np.sqrt(s / 4 - m ** 2),
                         np.sqrt(s / 4 - m_med ** 2), identical=True)


def s_channel_squared_many(s: float, m: float, m_f: float, mediators: list[tuple[float, float]],
                           chi: list[tuple[float, float]], f: list[tuple[float, float]],
                           cos_theta: np.ndarray) -> np.ndarray:
    """Spin-averaged |M|² of χχ̄ → f f̄ through several spin-1 mediators (mass, width), interfering.

    ``chi`` and ``f`` hold each mediator's (a, b) couplings; checks ``exchange.vector_to_fermions``.
    """
    p1, p2, k1, k2, _, _ = _frame(s, m, m_f, cos_theta)
    q = p1 + p2
    total = np.zeros(len(cos_theta))
    for x1 in _BASIS:
        for x2 in _BASIS:
            ubar_v = bar(spinor_v(p2[:, 1:], m, x2))
            u1 = spinor_u(p1[:, 1:], m, x1)
            for y1 in _BASIS:
                for y2 in _BASIS:
                    amp = np.zeros(len(cos_theta), dtype=complex)
                    for (mass, width), c, g in zip(mediators, chi, f):
                        j_chi = _current(ubar_v, *c, u1)
                        j_f = _current(bar(spinor_u(k1[:, 1:], m_f, y1)), *g, spinor_v(k2[:, 1:], m_f, y2))
                        amp += ((-_dot(j_chi, j_f) + _dot(q, j_chi) * _dot(q, j_f) / mass ** 2)
                                / (s - mass ** 2 + 1j * mass * width))
                    total += np.abs(amp) ** 2
    return total / 4.0

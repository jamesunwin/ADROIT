"""The oblique parameters S and T of new scalars at one loop, exactly (Grimus, Lavoura, Ogreid & Osland,
arXiv:0802.4353, Nucl. Phys. B801 (2008) 81): any number of scalar doublets with Y = ½ and real neutral singlets.

**The fields.** The doublets φ_k = (φ_k⁺, (v_k + φ_k⁰′)/√2); the charged mass eigenstates S_a⁺ with φ_k⁺ = Σ_a U_ka S_a⁺,
the neutral real ones S_b⁰ with φ_k⁰′ = Σ_b V_kb S_b⁰ (V complex), index 0 the Goldstone bosons G± and G⁰ (the paper's
index 1). A singlet enters only through V's columns, which then need not be unitary.

**The results** (eqs. (28) and (30)), with Q = m_Z², the Standard Model's Higgs loop subtracted:

  ᾱT = g²/(64π² m_W²) { Σ_{a,b ≥ 1} |(U†V)_ab|² F(m_a², μ_b²) − Σ_{b<b′} [Im(V†V)_bb′]² F(μ_b², μ_b′²)
        − 2 Σ_{a<a′} |(U†U)_aa′|² F(m_a², m_a′²) + 3 Σ_{b ≥ 1} [Im(V†V)_0b]² [F(m_Z², μ_b²) − F(m_W², μ_b²)]
        − 3 [F(m_Z², m_h²) − F(m_W², m_h²)] },
  αS/(4s_W²c_W²) = g²/(384π² c_W²) { Σ_a [2s_W² − (U†U)_aa]² G(m_a², m_a², Q) + 2 Σ_{a<a′} |(U†U)_aa′|² G(m_a², m_a′², Q)
        + Σ_{b<b′} [Im(V†V)_bb′]² G(μ_b², μ_b′², Q) − 2 Σ_a (U†U)_aa ln m_a² + Σ_b (V†V)_bb ln μ_b² − ln m_h²
        + Σ_b [Im(V†V)_0b]² Ĝ(μ_b², Q) − Ĝ(m_h², Q) },

with g² = 4πα/s_W², so that T and S do not depend on α; s_W² = 1 − m_W²/m_Z² (on shell). F is eq. (29), G eq. (C2),
Ĝ eq. (C5), f eq. (B7).

**Precision.** These closed forms cancel: for heavy, nearly degenerate states each term grows as the squared masses
(G's as their squares over m_Z⁴) while S and T decouple, and at a large mass ratio G loses digits too. In double
precision an inert doublet at (10⁶, 10⁶ + 0.001, 10⁶ + 0.002) GeV gave χ² = 1170 for the decoupled 3.78, and
(100, 10⁴, 100) GeV an S 3% low (the tactical audit's T20-08, 2026-10-20). They are therefore evaluated in
``DIGITS``-digit arithmetic (mpmath) from the masses' exact binary values. Exactly equal arguments take the
functions' limits.
"""
from __future__ import annotations

import math

import mpmath
import numpy as np

M_W, M_Z = 80.377, 91.1876              # GeV, as the library's electroweak inputs
S_W2 = 1.0 - (M_W / M_Z) ** 2
DIGITS = 50                             # the closed forms' working precision (module docstring)


def _mp(x) -> mpmath.mpf:
    return x if isinstance(x, mpmath.mpf) else mpmath.mpf(float(x))


def big_f(i, j) -> mpmath.mpf:
    """F(I, J) = (I + J)/2 − IJ/(I − J) ln(I/J), 0 for I = J (eq. (29)); call inside ``mpmath.workdps(DIGITS)``."""
    i, j = _mp(i), _mp(j)
    if i == j:
        return mpmath.mpf(0)
    return (i + j) / 2 - i * j / (i - j) * mpmath.log(i / j)


def small_f(t, r) -> mpmath.mpf:
    """f(t, r) (eq. (B7))."""
    t, r = _mp(t), _mp(r)
    if r > 0:
        root = mpmath.sqrt(r)
        return root * mpmath.log(abs((t - root) / (t + root)))
    if r < 0:
        root = mpmath.sqrt(-r)
        return 2 * root * mpmath.atan(root / t) if t != 0 else mpmath.pi * root
    return mpmath.mpf(0)


def big_g(i, j, q) -> mpmath.mpf:
    """G(I, J, Q) (eq. (C2)); at I = J the logarithm's bracket takes its limit 2I."""
    i, j, q = _mp(i), _mp(j), _mp(q)
    t, r = i + j - q, q * q - 2 * q * (i + j) + (i - j) ** 2
    if i == j:
        log_part = 2 * i
    else:
        log_part = ((i * i + j * j) / (i - j) - (i * i - j * j) / q + (i - j) ** 3 / (3 * q * q)) * mpmath.log(i / j)
    return (-mpmath.mpf(16) / 3 + 5 * (i + j) / q - 2 * (i - j) ** 2 / q ** 2 + 3 / q * log_part
            + r / q ** 3 * small_f(t, r))


def big_g_hat(i, q) -> mpmath.mpf:
    """Ĝ(I, Q) (eq. (C5)); at I = Q the term (I + Q)/(I − Q) ln(I/Q) takes its limit 2."""
    i, q = _mp(i), _mp(q)
    x = i / q
    log = mpmath.log(x)
    ratio = mpmath.mpf(2) if i == q else (i + q) / (i - q) * log
    return (-mpmath.mpf(79) / 3 + 9 * x - 2 * x * x + (-10 + 18 * x - 6 * x * x + x ** 3) * log - 9 * ratio
            + (12 - 4 * x + x * x) * small_f(i, i * i - 4 * i * q) / q)


def oblique(charged: list[float], u: np.ndarray, neutral: list[float], v: np.ndarray,
            m_h: float = 125.09) -> tuple[float, float]:
    """(S, T) of the scalars (module docstring): ``charged`` and ``neutral`` the masses (GeV) of S_a⁺ and S_b⁰, index 0
    the Goldstone bosons (its mass unused); U (n_d × n) and V (n_d × m) the doublets' components."""
    with mpmath.workdps(DIGITS):
        s, t = _oblique(charged, u, neutral, v, m_h)
        return float(s), float(t)


def _oblique(charged: list[float], u: np.ndarray, neutral: list[float], v: np.ndarray, m_h: float):
    uu, uv, vv = u.conj().T @ u, u.conj().T @ v, v.conj().T @ v
    mc, mn = [_mp(m) ** 2 for m in charged], [_mp(m) ** 2 for m in neutral]
    z, w, h, q = _mp(M_Z) ** 2, _mp(M_W) ** 2, _mp(m_h) ** 2, _mp(M_Z) ** 2
    n, m = len(charged), len(neutral)
    t = sum(abs(uv[a, b]) ** 2 * big_f(mc[a], mn[b]) for a in range(1, n) for b in range(1, m))
    t -= sum(vv[b, c].imag ** 2 * big_f(mn[b], mn[c]) for b in range(1, m) for c in range(b + 1, m))
    t -= 2 * sum(abs(uu[a, c]) ** 2 * big_f(mc[a], mc[c]) for a in range(1, n) for c in range(a + 1, n))
    t += 3 * sum(vv[0, b].imag ** 2 * (big_f(z, mn[b]) - big_f(w, mn[b])) for b in range(1, m))
    t -= 3 * (big_f(z, h) - big_f(w, h))
    s = sum((2 * S_W2 - uu[a, a].real) ** 2 * big_g(mc[a], mc[a], q) for a in range(1, n))
    s += 2 * sum(abs(uu[a, c]) ** 2 * big_g(mc[a], mc[c], q) for a in range(1, n) for c in range(a + 1, n))
    s += sum(vv[b, c].imag ** 2 * big_g(mn[b], mn[c], q) for b in range(1, m) for c in range(b + 1, m))
    s += -2 * sum(uu[a, a].real * mpmath.log(mc[a]) for a in range(1, n))
    s += sum(vv[b, b].real * mpmath.log(mn[b]) for b in range(1, m)) - mpmath.log(h)
    s += sum(vv[0, b].imag ** 2 * big_g_hat(mn[b], q) for b in range(1, m)) - big_g_hat(h, q)
    return s / (24 * mpmath.pi), t / (16 * mpmath.pi * _mp(S_W2) * w)


def inert_doublet(m_h0: float, m_a0: float, m_charged: float, m_h: float = 125.09) -> tuple[float, float]:
    """(S, T) of an inert doublet: the Standard Model's doublet (G±, h, G⁰) and the inert one (H±, H₀, A₀)."""
    u = np.eye(2, dtype=complex)
    v = np.array([[1j, 1, 0, 0], [0, 0, 1, 1j]], dtype=complex)        # G⁰, h, H₀, A₀
    return oblique([M_W, m_charged], u, [M_Z, m_h, m_h0, m_a0], v, m_h)


def two_hdm_a(m_heavy: float, m_a_heavy: float, m_a_light: float, m_charged: float, sin_theta: float,
              m_h: float = 125.09) -> tuple[float, float]:
    """(S, T) of the 2HDM+a at alignment (Higgs basis): the second doublet's CP-even H, its CP-odd part shared between
    A (cos θ) and a (sin θ), the singlet P the rest."""
    c = math.sqrt(max(1 - sin_theta ** 2, 0.0))
    u = np.eye(2, dtype=complex)
    v = np.array([[1j, 1, 0, 0, 0], [0, 0, 1, 1j * c, 1j * sin_theta]], dtype=complex)   # G⁰, h, H, A, a
    return oblique([M_W, m_charged], u, [M_Z, m_h, m_heavy, m_a_heavy, m_a_light], v, m_h)

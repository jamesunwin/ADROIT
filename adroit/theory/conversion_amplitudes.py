"""Crossed gauge-invariant amplitudes for the existing abelian t-channel component."""

from __future__ import annotations
import math
import numpy as np
from adroit.constraints import processes as pr
from adroit.constraints.amplitudes import _BASIS, bar, spinor_u, spinor_v, slash


def decay_width(m: float, M: float, mf: float, y: float) -> float:
    """One charged scalar width, spin-summed chiral Yukawa, finite fermion threshold."""
    if not all(math.isfinite(v) for v in (m, M, mf, y)) or m < 0 or M <= 0 or mf < 0:
        raise ValueError("finite nonnegative fermion masses and positive scalar mass required")
    if M <= m + mf:
        return 0.0
    lam = (M * M - (m + mf) ** 2) * (M * M - (m - mf) ** 2)
    return y * y * (M * M - m * m - mf * mf) * math.sqrt(lam) / (16 * math.pi * M**3)


def scattering_chain(
    p: np.ndarray,
    phi: np.ndarray,
    f: np.ndarray,
    B: np.ndarray,
    eps: np.ndarray,
    M: float,
    mf: float,
) -> np.ndarray:
    """Crossed chi phi->f B chain; phi/B are signed outgoing/incoming four-vectors."""
    q = p + phi
    prop = (slash(q) + mf * pr.UNIT[None]) / (pr._dot(q, q) - mf * mf)[:, None, None]
    scalar = pr._dot(2 * phi - B, eps) / (pr._dot(phi - B, phi - B) - M * M)
    return slash(eps) @ prop @ pr.P_L[None] + scalar[:, None, None] * pr.P_L[None]


def scattering_squared(
    s: float, m: float, M: float, mf: float, channel: str, cos_theta: np.ndarray, ward: bool = False
) -> tuple[np.ndarray, float, float]:
    """Spin/polarisation sum of unit couplings, crossing both conversion channels."""
    if channel == "chi_B":
        p, b, phi, f, pin, pout = pr.frame(s, m, 0.0, M, mf, cos_theta)
        signed_phi, signed_B = -phi, -b
        fermion = spinor_u
        polar = pr._transverse(b)
    elif channel == "chi_ebar":
        p, f, phi, b, pin, pout = pr.frame(s, m, mf, M, 0.0, cos_theta)
        signed_phi, signed_B = -phi, b
        fermion = spinor_v
        polar = pr._transverse(b)
    else:
        raise ValueError("unknown conversion scattering")
    if ward:
        polar = [signed_B]
    total = np.zeros(len(cos_theta))
    for eps in polar:
        chain = scattering_chain(p, signed_phi, f, signed_B, eps, M, mf)
        for xi in _BASIS:
            u = spinor_u(p[:, 1:], m, xi)
            for eta in _BASIS:
                amp = np.einsum("ni,nij,nj->n", bar(fermion(f[:, 1:], mf, eta)), chain, u)
                total += abs(amp) ** 2
    return total, pin, pout


def cross_section(
    s: float, m: float, M: float, mf: float, channel: str, angular_cut: float, nodes: int = 32
) -> float:
    """Hard-angle Born cross section averaged over four initial spin/polarisation states."""
    if channel not in ("chi_B", "chi_ebar") or not 0 < angular_cut < 1 or nodes < 8:
        raise ValueError(
            "known channel, 0<angular_cut<1 and at least eight quadrature nodes required"
        )
    if not all(math.isfinite(v) for v in (s, m, M, mf)) or s <= 0 or m <= 0 or M <= 0 or mf < 0:
        raise ValueError("finite positive energy/masses required")
    threshold = max(m + (mf if channel == "chi_ebar" else 0), M + (mf if channel == "chi_B" else 0))
    if math.sqrt(s) <= threshold:
        return 0.0
    x, w = np.polynomial.legendre.leggauss(nodes)
    square, p, k = scattering_squared(s, m, M, mf, channel, x * angular_cut)
    return pr._sigma(square / 4, w * angular_cut, s, p, k, False)

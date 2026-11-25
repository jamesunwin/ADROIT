"""Source-prescribed energy cuts and full mass-regulated angular Born integration.

Garny et al. 1705.09292 Appendix A: sqrt(s)_min=M_phi+m_cut, with
m_cut=0.1,0.5,5 GeV. This is a finite-cut component, not an inclusive NLO rate.
The retained Abelian vector vertex and chiral Yukawa are unchanged.

The scattering's collinear region (the exchanged e_R near its mass shell) is regulated by the
electron's mass. In the vacuum that is m_e; in the plasma the electron carries its asymptotic
thermal mass m_∞ = g′|Y|T/2 (Y = −1 for e_R, unbroken phase), which is far larger. The bank of
regulator variants therefore includes a thermal one, with m_f = √(m_e² + m_∞²) throughout: the
scattering at the central cut and, consistently (2026-10-12), the decay φ → χ e and its inverse,
whose phase space closes when m_φ < m_χ + m_f (thermal blocking). It cuts the scattering rates by
roughly ×0.07–0.21 near m_χ = 8 TeV, and the conservative bound takes the lowest variant
(release audit M11). The scalar's own thermal mass is not included (a further correction).
"""

from __future__ import annotations
from functools import lru_cache
import math
import numpy as np
from scipy.special import kve
from adroit.constraints import processes as pr
from adroit.constraints.amplitudes import _BASIS, bar, spinor_u, spinor_v, slash
from adroit.constraints.relic import degrees_of_freedom, M_PLANCK_GEV
from adroit.core.chemical_equilibrium import ConversionInput, ConversionRatePoint
from adroit.theory.conversion_amplitudes import decay_width
from adroit.theory.conversion_rates import ELECTRON_MASS


@lru_cache(maxsize=16)
def _gauss(n: int) -> tuple[np.ndarray, np.ndarray]:
    x, w = np.polynomial.legendre.leggauss(n)
    x.setflags(write=False)
    w.setflags(write=False)
    return x, w


def _frame(s: float, m: float, M: float, mf: float, channel: str, n: int) -> tuple:
    root = math.sqrt(s)
    ef = (s + mf * mf - (M * M if channel == "chi_B" else m * m)) / (2 * root)
    pf = math.sqrt(max(ef * ef - mf * mf, 0))
    delta = mf * mf / (pf * (ef + pf))
    high = math.log1p(2 / delta)
    nodes, weights = _gauss(n)
    z = (nodes + 1) * high / 2
    r = delta * np.expm1(z)
    jac = delta * np.exp(z) * weights * high / 2
    if channel == "chi_B":
        p, b, phi, f, pin, pout = pr.frame(s, m, 0, M, mf, 1 - r)
        phi[:, 1] = pout * np.sqrt(r * (2 - r))
        f[:, 1] = -phi[:, 1]
        signed_phi, signed_B, q = -phi, -b, f - b
        fd = -2 * b[:, 0] * (mf * mf / (ef + pf) + pf * r)
        sd = -2 * b[:, 0] * (phi[:, 0] + pout * (1 - r))
    else:
        p, f, phi, b, pin, pout = pr.frame(s, m, mf, M, 0, 1 - r)
        phi[:, 1] = pout * np.sqrt(r * (2 - r))
        b[:, 1] = -phi[:, 1]
        signed_phi, signed_B, q = -phi, b, b - f
        fd = -2 * b[:, 0] * (mf * mf / (ef + pf) + pf * r)
        sd = np.full(n, (root - M) * (root + M))
    return p, f, b, signed_phi, signed_B, q, fd, sd, jac, pin, pout


def cross_section(s: float, m: float, M: float, mf: float, channel: str, nodes: int = 48) -> float:
    """Unit-coupling full-angle cross section; log coordinates resolve the fermion pole."""
    if channel not in ("chi_B", "chi_ebar") or nodes < 16:
        raise ValueError("known channel and at least 16 angular nodes required")
    if not all(math.isfinite(v) for v in (s, m, M, mf)) or not 0 < m < M or mf <= 0 or s <= 0:
        raise ValueError(
            "finite inputs, heavier scalar and explicit positive vacuum mass regulator required"
        )
    threshold = max(m + (mf if channel == "chi_ebar" else 0), M + (mf if channel == "chi_B" else 0))
    if math.sqrt(s) <= threshold:
        return 0.0
    p, f, b, phi, B, q, fd, sd, jac, pin, pout = _frame(s, m, M, mf, channel, nodes)
    fermion = spinor_u if channel == "chi_B" else spinor_v
    total = np.zeros(nodes)
    for eps in pr._transverse(b):
        scalar = pr._dot(2 * phi - B, eps) / sd
        chain = (
            slash(eps) @ (slash(q) + mf * pr.UNIT[None]) @ pr.P_L / fd[:, None, None]
            + scalar[:, None, None] * pr.P_L[None]
        )
        for xi in _BASIS:
            u = spinor_u(p[:, 1:], m, xi)
            for eta in _BASIS:
                total += (
                    abs(np.einsum("ni,nij,nj->n", bar(fermion(f[:, 1:], mf, eta)), chain, u)) ** 2
                )
    result = (pout / pin) * float(sum(jac * total / 4)) / (32 * math.pi * s)
    if not math.isfinite(result) or result < 0:
        raise ArithmeticError("unresolved full-angle integral")
    return result


def thermal_mass(T: float, g_prime: float) -> float:
    """The electron's regulator mass in the plasma, √(m_e² + m_∞²) with m_∞ = g′|Y|T/2, Y = −1 for e_R (GeV)."""
    return math.hypot(ELECTRON_MASS, g_prime * T / 2)


@lru_cache(maxsize=256)
def _table(
    m: float, M: float, channel: str, cut: float, refined: bool, mf: float = ELECTRON_MASS
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    w = np.geomspace(
        max(cut, mf if channel == "chi_B" else 0.0), 80 * M, 1201 if refined else 601
    )
    roots = M + w
    s = roots * roots
    sig = np.array(
        [cross_section(float(ss), m, M, mf, channel, 96 if refined else 48) for ss in s]
    )
    bath = mf if channel == "chi_ebar" else 0.0
    lam = (s - (m + bath) ** 2) * (s - (m - bath) ** 2)
    product = sig * lam * w
    for a in (w, roots, product):
        a.setflags(write=False)
    return w, roots, product


def scattering_rate(
    m: float,
    M: float,
    y: float,
    g: float,
    T: float,
    channel: str,
    cut_gev: float,
    refined: bool = False,
    mf: float = ELECTRON_MASS,
) -> float:
    """Per-chi up rate including both charge conjugates, source MB reaction density in GeV (``mf``: the
    electron's regulator mass, the vacuum one by default)."""
    if (
        not all(math.isfinite(v) for v in (m, M, y, g, T, cut_gev))
        or not 0 < m < M
        or T <= 0
        or cut_gev <= 0
    ):
        raise ValueError("finite inputs, positive temperature/cut and heavier scalar required")
    w, roots, product = _table(m, M, channel, cut_gev, refined, mf)
    weight = kve(1, roots / T) / kve(2, m / T) * np.exp(-(roots - m) / T)
    return float(
        y * y * g * g * np.trapezoid(product * weight, np.log(w)) / (2 * math.pi**2 * m * m)
    )


def rate_point(inputs: ConversionInput, x: float) -> ConversionRatePoint:
    """Complete retained Born channels, independent energy-cut bank and refinement diagnostics."""
    if inputs.request is None or inputs.request.source_born is None:
        raise ValueError("explicit source-born request required")
    return _cached(inputs.model_dump_json(), x).model_copy(deep=True)


@lru_cache(maxsize=2048)
def _cached(payload: str, x: float) -> ConversionRatePoint:
    inputs = ConversionInput.model_validate_json(payload)
    p = inputs.point
    r = inputs.request
    m, M, y = p.m_chi, p.m_med, p.g_chi
    T = m / x
    z = M / T
    H = math.sqrt(4 * math.pi**3 * degrees_of_freedom(T)[0] / 45) * T * T / M_PLANCK_GEV
    ratio = (M / m) ** 2 * float(kve(2, z) / kve(2, x)) * math.exp(-(M - m) / T)
    if ratio <= 0:
        raise ValueError("unresolved partner population")
    down = decay_width(m, M, ELECTRON_MASS, y) * float(kve(1, z) / kve(2, z))
    variants = {}
    central = {}
    error = 0.0
    for cut in r.source_born.energy_cuts_gev:
        rates = {
            name: scattering_rate(m, M, y, inputs.g_prime, T, name, cut)
            for name in ("chi_B", "chi_ebar")
        }
        variants[str(cut)] = down * (1 + ratio) + sum(rates.values()) * (1 + 1 / ratio)
        if cut == 0.5:
            central = rates
            for name, value in rates.items():
                fine = scattering_rate(m, M, y, inputs.g_prime, T, name, cut, True)
                error = max(error, abs(value - fine) / max(fine, 1e-300))
    plasma = thermal_mass(T, inputs.g_prime)                        # the thermal regulator (module docstring)
    thermal = sum(scattering_rate(m, M, y, inputs.g_prime, T, name, 0.5, mf=plasma) for name in ("chi_B", "chi_ebar"))
    down_thermal = decay_width(m, M, plasma, y) * float(kve(1, z) / kve(2, z))     # the same thermal mass
    variants["thermal"] = down_thermal * (1 + ratio) + thermal * (1 + 1 / ratio)
    from adroit.theory.conversion_rates import _odd

    sv, odd, odd_error, absolute, lower = _odd(inputs, x)
    if odd is not None:
        variants = {key: value + odd for key, value in variants.items()}
        error = max(error, absolute / max(variants["0.5"], 1e-300))
    high, low = max(variants.values()), min(variants.values())
    return ConversionRatePoint(
        x=x,
        temperature_gev=T,
        hubble_gev=H,
        partner_to_chi_equilibrium_ratio=ratio,
        decay_down_gev=down,
        inverse_decay_up_gev=down * ratio,
        scatter_up_gev=central,
        relaxation_over_h=variants["0.5"] / H,
        conservative_over_h=(1 - r.rate_relative_uncertainty) * low / H,
        regulator_relative_spread=(high - low) / max(high, 1e-300),
        quadrature_relative_difference=error,
        odd_sector_sigma_v_gev2=sv,
        odd_sector_relaxation_gev=odd,
        odd_sector_quadrature_difference=odd_error,
        regulator_rates_over_h={key: value / H for key, value in variants.items()},
        upper_envelope_over_h=(1 + r.rate_relative_uncertainty) * high / H,
    )

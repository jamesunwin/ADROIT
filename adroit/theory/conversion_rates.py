"""Detailed balance and explicitly regulated thermal Born rates, in natural units."""

from __future__ import annotations
from functools import lru_cache
import math
import numpy as np
from scipy.special import kve
from adroit.core.chemical_equilibrium import ConversionInput, ConversionRatePoint
from adroit.constraints.relic import degrees_of_freedom, M_PLANCK_GEV
from adroit.theory.conversion_amplitudes import decay_width, cross_section

ELECTRON_MASS = 0.000511


@lru_cache(maxsize=8192)
def _scatter(
    m: float,
    M: float,
    T: float,
    mf: float,
    channel: str,
    cut: float,
    angle: float,
    refined: bool = False,
) -> float:
    # Eq7: gamma = g_chi*g_bath*T/(32*pi^4) integral ds sigma lambda/sqrt(s) K1.
    # Divide by n_chi=2*m^2*T*K2/(2*pi^2); multiply 2 for charge conjugates.
    threshold = M + mf if channel == "chi_B" else M
    root0 = max(threshold + cut * T, m + (mf if channel == "chi_ebar" else 0) + 1e-8)
    u = np.concatenate([[0.0], np.geomspace(1e-7, 50, 601 if refined else 301)])
    roots = root0 + T * u
    s = roots * roots
    sig = np.array(
        [cross_section(float(ss), m, M, mf, channel, angle, 64 if refined else 32) for ss in s]
    )
    bath_mass = 0.0 if channel == "chi_B" else mf
    lam = (s - (m + bath_mass) ** 2) * (s - (m - bath_mass) ** 2)
    weight = kve(1, roots / T) / kve(2, m / T) * np.exp(-(roots - m) / T)
    # ds=2*sqrt(s)*T du, two bath degrees, both conjugates; y²g'² applied later.
    return float(np.trapezoid(sig * lam * weight, u)) * T / (2 * math.pi**2 * m * m)


def rate_point(inputs: ConversionInput, x: float) -> ConversionRatePoint:
    """Thermal dilation, Boltzmann population and both leading gauge conversions."""
    p = inputs.point
    if (
        not math.isfinite(x)
        or x <= 0
        or not all(math.isfinite(v) for v in (p.m_chi, p.m_med, p.g_chi))
        or not 0 < p.m_chi < p.m_med
        or inputs.partner != "eR"
        or not inputs.majorana
    ):
        raise ValueError("finite positive x/masses and eR Majorana input required")
    if inputs.request is None:
        raise ValueError("explicit conversion request required")
    return _cached(inputs.model_dump_json(), x).model_copy(deep=True)


@lru_cache(maxsize=2048)
def _cached(payload: str, x: float) -> ConversionRatePoint:
    inputs = ConversionInput.model_validate_json(payload)
    r = inputs.request
    p = inputs.point
    m, M, y = p.m_chi, p.m_med, p.g_chi
    T = m / x
    z = M / T
    geff = degrees_of_freedom(T)[0]
    H = math.sqrt(4 * math.pi**3 * geff / 45) * T * T / M_PLANCK_GEV
    ratio = (
        (M / m) ** 2 * float(kve(2, z) / kve(2, x)) * math.exp(-(M - m) / T)
    )  # g_phi,total=g_chi=2
    if ratio < 1e-250:
        raise ValueError("thermal partner population is below resolved numerical range")
    down = decay_width(m, M, ELECTRON_MASS, y) * float(kve(1, z) / kve(2, z))
    variants = []
    channels = {}
    errors = []
    for cut, angle in zip(r.minimum_root_excess_over_T, r.angular_cuts):
        current = {
            name: y * y * inputs.g_prime**2 * _scatter(m, M, T, ELECTRON_MASS, name, cut, angle)
            for name in ("chi_B", "chi_ebar")
        }
        variants.append(sum(current.values()))
        if cut == 0.5:
            channels = current
            for name in current:
                fine = (
                    y
                    * y
                    * inputs.g_prime**2
                    * _scatter(m, M, T, ELECTRON_MASS, name, cut, angle, True)
                )
                errors.append(abs(fine - current[name]) / max(fine, 1e-300))
    central = down * (1 + ratio) + sum(channels.values()) * (1 + 1 / ratio)
    conservative = (1 - r.rate_relative_uncertainty) * (
        down * (1 + ratio) + min(variants) * (1 + 1 / ratio)
    )
    odd_sv, odd_rate, odd_error, odd_absolute_error, odd_lower = _odd(inputs, x)
    if odd_rate is not None:
        errors.append(odd_absolute_error / max(central + odd_rate, 1e-300))
        central += odd_rate
        conservative += (1 - r.rate_relative_uncertainty) * odd_lower
    spread = (max(variants) - min(variants)) / max(max(variants), 1e-300)
    return ConversionRatePoint(
        x=x,
        temperature_gev=T,
        hubble_gev=H,
        partner_to_chi_equilibrium_ratio=ratio,
        decay_down_gev=down,
        inverse_decay_up_gev=down * ratio,
        scatter_up_gev=channels,
        relaxation_over_h=central / H,
        conservative_over_h=conservative / H,
        regulator_relative_spread=spread,
        quadrature_relative_difference=max(errors),
        odd_sector_sigma_v_gev2=odd_sv,
        odd_sector_relaxation_gev=odd_rate,
        odd_sector_quadrature_difference=odd_error,
    )


def _odd(
    inputs: ConversionInput, x: float
) -> tuple[float | None, float | None, float | None, float, float]:
    if not inputs.request.include_odd_sector:
        return None, None, None, 0.0, 0.0
    from adroit.theory.odd_conversion import equilibrium_relaxation

    p = inputs.point
    sv, rate = equilibrium_relaxation(p.m_chi, p.m_med, ELECTRON_MASS, p.g_chi, x)
    fine_sv, fine_rate = equilibrium_relaxation(p.m_chi, p.m_med, ELECTRON_MASS, p.g_chi, x, True)
    return (
        sv,
        rate,
        abs(sv - fine_sv) / max(fine_sv, 1e-300),
        abs(rate - fine_rate),
        min(rate, fine_rate),
    )

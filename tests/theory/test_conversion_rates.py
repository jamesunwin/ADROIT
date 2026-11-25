"""Independent trace, phase space, crossing/Ward and thermal quadrature checks."""

import math
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import kv
from adroit.constraints import processes as pr
from adroit.constraints.kinetic_mixing import G_PRIME
from adroit.constraints.amplitudes import GAMMA, slash, _BASIS, bar, spinor_u
from adroit.theory.conversion_amplitudes import (
    decay_width,
    scattering_squared,
    cross_section,
)
from adroit.theory.conversion_rates import rate_point
from adroit.core.chemical_equilibrium import ConversionRequest, ConversionInput
from adroit.parameter_space.classes import Point


def example(y=1e-6):
    return ConversionInput(
        point=Point(m_chi=10000, m_med=10500, g_chi=y, g_q=0, g_l=0),
        partner="eR",
        majorana=True,
        g_prime=G_PRIME,
        request=ConversionRequest(
            x_low=15,
            x_high=40,
            rate_relative_uncertainty=0.5,
            approximation="unbroken_hypercharge_vacuum_Born_MB",
            samples=9,
        ),
    )


def test_finite_mass_decay_width_from_spin_sum():
    for m, M, mf in [(100, 105, 0.000511), (100, 100.2, 0.1), (100, 104, 3.0)]:
        s = M * M
        k = math.sqrt((s - (m + mf) ** 2) * (s - (m - mf) ** 2)) / (2 * M)
        a = np.array([[0.0, 0.0, k]])
        b = -a
        total = 0.0
        for xi in _BASIS:
            for eta in _BASIS:
                total += abs((bar(spinor_u(a, m, xi)) @ pr.P_R @ spinor_u(b, mf, eta).T)[0, 0]) ** 2
        assert decay_width(m, M, mf, 1) == pytest.approx(
            total * k / (8 * math.pi * M * M), rel=1e-10
        )
    assert decay_width(100, 100.1, 0.1, 1) == 0


def trace_squared(s, m, M, mf, channel, x):
    if channel == "chi_B":
        p, b, phi, f, _, _ = pr.frame(s, m, 0, M, mf, x)
        B = -b
        pol = pr._transverse(b)
        fnum = slash(f) + mf * pr.UNIT
    else:
        p, f, phi, b, _, _ = pr.frame(s, m, mf, M, 0, x)
        B = b
        pol = pr._transverse(b)
        fnum = slash(f) - mf * pr.UNIT
    chi = slash(p) + m * pr.UNIT
    total = np.zeros(len(x))
    # Independent trace of crossed Feynman chains, not explicit external spinors.
    q = p - phi
    denom = pr._dot(q, q) - mf * mf
    scalar_denom = pr._dot(-phi - B, -phi - B) - M * M
    for eps in pol:
        chain = slash(eps) @ (slash(q) + mf * pr.UNIT) / denom[:, None, None] @ pr.P_L
        chain += ((pr._dot(-2 * phi - B, eps) / scalar_denom)[:, None, None]) * pr.P_L
        adj = GAMMA[0] @ chain.conj().transpose(0, 2, 1) @ GAMMA[0]
        total += np.trace(fnum @ chain @ chi @ adj, axis1=1, axis2=2).real
    return total


def test_scattering_trace_ward_and_threshold():
    for ch in ("chi_B", "chi_ebar"):
        for root in (110, 150, 300):
            x = np.array([-0.8, 0.1, 0.9])
            s = root * root
            square, _, _ = scattering_squared(s, 100, 105, 0.000511, ch, x)
            assert np.allclose(
                square, trace_squared(s, 100, 105, 0.000511, ch, x), rtol=1e-10, atol=1e-12
            )
            ward, _, _ = scattering_squared(s, 100, 105, 0.000511, ch, x, True)
            assert max(ward) / (s * max(square)) < 1e-10
            assert cross_section(s, 100, 105, 0.000511, ch, 0.95) > 0
        assert cross_section(104**2, 100, 105, 0.000511, ch, 0.95) == 0
    with pytest.raises(ValueError):
        scattering_squared(150**2, 100, 105, 0, "bad", np.array([0.0]))


def test_thermal_population_and_dilation():
    inputs = example()
    r = rate_point(inputs, 25)
    assert r.partner_to_chi_equilibrium_ratio == pytest.approx(
        (1.05) ** 2 * kv(2, 26.25) / kv(2, 25), rel=1e-12
    )
    z = 26.25
    norm = quad(lambda u: u * u * math.exp(-math.hypot(u, z)), 0, 100)[0]
    dilation = (
        quad(lambda u: u * u * z / math.hypot(u, z) * math.exp(-math.hypot(u, z)), 0, 100)[0] / norm
    )
    assert r.decay_down_gev == pytest.approx(
        decay_width(10000, 10500, 0.000511, 1e-6) * dilation, rel=1e-6
    )
    assert r.quadrature_relative_difference < 0.01
    assert r.relaxation_over_h > r.conservative_over_h > 0
    doubled = rate_point(example(2e-6), 25)
    assert doubled.relaxation_over_h == pytest.approx(4 * r.relaxation_over_h)
    r.scatter_up_gev.clear()
    assert rate_point(inputs, 25).scatter_up_gev


def test_invalid_public_rates_reject_missing_or_nonfinite_inputs():
    with pytest.raises(ValueError):
        rate_point(example(), 0)
    with pytest.raises(ValueError):
        rate_point(example().model_copy(update={"request": None}), 25)
    with pytest.raises(ValueError):
        cross_section(150**2, 100, 105, 0.000511, "bad", 0.95)
    with pytest.raises(ValueError):
        decay_width(100, float("nan"), 0.1, 1)


def test_thermal_scattering_against_direct_reaction_density_quad():
    # A different integration variable and explicit number density fix all degeneracy factors.
    from adroit.theory.conversion_rates import _scatter

    m, M, T, mf = 100.0, 105.0, 4.0, 0.000511
    for channel in ("chi_B", "chi_ebar"):
        bath = 0.0 if channel == "chi_B" else mf
        threshold = M + mf if channel == "chi_B" else M
        low = threshold + 0.5 * T

        def integrand(root):
            s = root * root
            lam = (s - (m + bath) ** 2) * (s - (m - bath) ** 2)
            return 2 * cross_section(s, m, M, mf, channel, 0.95) * lam * kv(1, root / T)

        integral = quad(integrand, low, low + 50 * T, epsabs=1e-20, epsrel=1e-6)[0]
        gamma_one_charge = 2 * 2 * T * integral / (32 * math.pi**4)
        n_chi = 2 * m * m * T * kv(2, m / T) / (2 * math.pi**2)
        independent = 2 * gamma_one_charge / n_chi
        assert _scatter(m, M, T, mf, channel, 0.5, 0.95, True) == pytest.approx(
            independent, rel=0.003
        )


def test_closed_decay_threshold_does_not_supply_a_default_conversion():
    p = example()
    p.point.m_med = p.point.m_chi + 0.0001
    r = rate_point(p, 25)
    assert r.decay_down_gev == 0 and r.inverse_decay_up_gev == 0
    assert all(value > 0 for value in r.scatter_up_gev.values())
    from adroit.theory.chemical_equilibrium import certify

    assert certify(p).status == "outside_domain"

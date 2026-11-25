"""Full-angle and source energy-cut rates, scope and numerical stability."""

import math
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import kv
from adroit.theory import source_born as sb
from adroit.theory.conversion_amplitudes import scattering_squared
from adroit.core.chemical_equilibrium import SourceBornSettings
from test_conversion_rates import example


def source_inputs(y=3e-5):
    p = example(y)
    p.request.source_born = SourceBornSettings(
        scheme="garny_1705_appendix_A_full_angle_vacuum_mass_MB",
        scope="retained_abelian_component_only",
    )
    p.request.include_odd_sector = True
    return p


def test_full_angle_against_independent_direct_cosine_quad():
    for ch in ("chi_B", "chi_ebar"):
        s = 120.0**2
        m, M, mf = 100.0, 105.0, 0.1

        def integrand(c):
            square, p, k = scattering_squared(s, m, M, mf, ch, np.array([c]))
            return float(square[0]) / 4 * (k / p) / (32 * math.pi * s)

        independent = quad(
            integrand, -1, 1, epsabs=1e-12, epsrel=1e-8, points=[0.9, 0.99, 0.999], limit=300
        )[0]
        assert sb.cross_section(s, m, M, mf, ch) == pytest.approx(independent, rel=2e-7)
        assert sb.cross_section(s, m, M, mf, ch, 96) == pytest.approx(independent, rel=2e-7)
    with pytest.raises(ValueError):
        sb.cross_section(s, m, M, 0.0, "chi_B")
    with pytest.raises(ValueError):
        sb.cross_section(s, m, M, mf, "bad")
    assert sb.cross_section(104.0**2, m, M, mf, "chi_B") == 0


def test_physical_hierarchy_full_angle_refinement_and_scaling():
    for ch in ("chi_B", "chi_ebar"):
        for root in (10500.1, 11000.0, 15000.0):
            a = sb.cross_section(root**2, 10000, 10500, 0.000511, ch, 48)
            b = sb.cross_section(root**2, 10000, 10500, 0.000511, ch, 96)
            assert a == pytest.approx(b, rel=1e-5)
    a = sb.scattering_rate(100, 105, 0.03, 0.357, 4.0, "chi_B", 0.5)
    assert sb.scattering_rate(100, 105, 0.06, 0.357, 4.0, "chi_B", 0.5) == pytest.approx(4 * a)
    assert sb.scattering_rate(100, 105, 0.03, 0.714, 4.0, "chi_B", 0.5) == pytest.approx(4 * a)
    with pytest.raises(ValueError):
        sb.scattering_rate(100, 105, 0.03, 0.357, 0.0, "chi_B", 0.5)


def test_source_thermal_rate_by_independent_root_quad():
    m, M, T, mf, y, g = 100.0, 105.0, 4.0, 0.000511, 0.03, 0.357
    for channel in ("chi_B", "chi_ebar"):
        bath = mf if channel == "chi_ebar" else 0.0

        def integrand(root):
            s = root * root
            lam = (s - (m + bath) ** 2) * (s - (m - bath) ** 2)
            return 2 * sb.cross_section(s, m, M, mf, channel, 96) * lam * kv(1, root / T)

        integral = quad(integrand, M + 0.5, M + 0.5 + 50 * T, epsabs=1e-16, epsrel=1e-5, limit=200)[
            0
        ]
        independent = y * y * g * g * integral / (4 * math.pi**2 * m * m * kv(2, m / T))
        assert sb.scattering_rate(m, M, y, g, T, channel, 0.5, True) == pytest.approx(
            independent, rel=0.001
        )


def test_independent_cut_bank_output_and_missing_request():
    p = source_inputs()
    c = sb.rate_point(p, 25)
    assert c.odd_sector_sigma_v_gev2 > 0
    assert set(c.regulator_rates_over_h) == {"0.1", "0.5", "5.0", "thermal"}   # R5: the plasma regulator (M11)
    assert c.upper_envelope_over_h > c.relaxation_over_h > c.conservative_over_h
    assert c.quadrature_relative_difference < 0.01
    assert c.regulator_relative_spread > 0.01
    c.regulator_rates_over_h.clear()
    assert sb.rate_point(p, 25).regulator_rates_over_h
    with pytest.raises(ValueError):
        sb.rate_point(example(), 25)

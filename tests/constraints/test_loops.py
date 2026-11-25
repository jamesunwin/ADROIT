"""Loop-level and higher-twist direct detection, against the loop survey's benchmarks (2026-10-04)."""

import math

import pytest

from adroit.constraints import loops

GEV2_CM2 = 0.3894e-27
M_MU = 0.1056584


def _sigma(c: float, m: float, majorana_f: bool = False) -> float:
    """σ = μ²c²/π (ADROIT's c₁), or (4/π)μ²f² for a Majorana f_N."""
    mu = m * loops.M_NUCLEON / (m + loops.M_NUCLEON)
    return (4.0 if majorana_f else 1.0) * mu * mu * c * c / math.pi * GEV2_CM2


@pytest.mark.parametrize("m, m_phi, sigma_p", [(300.0, 360.0, 3.65e-44), (1000.0, 1100.0, 5.0e-46)])
def test_a_coloured_partner_scatters_through_twist_two(m, m_phi, sigma_p):
    f_p, f_n = loops.coloured_partner_si(m, m_phi, 1.0, "u")
    assert _sigma(f_p, m, majorana_f=True) == pytest.approx(sigma_p, rel=0.02)
    assert 0.3 < (f_n / f_p) ** 2 < 0.45                    # u-quark: the proton's larger second moment


def test_the_twist_two_term_dominates_and_a_b_partner_scatters_through_gluons_only():
    m, m_phi = 300.0, 360.0
    delta = m_phi ** 2 - m ** 2
    twist = 0.75 * loops.MOMENTS["p"]["u"] * m / (4.0 * delta ** 2) * loops.M_NUCLEON
    assert twist / loops.coloured_partner_si(m, m_phi, 1.0, "u")[0] > 0.8
    f_p, f_n = loops.coloured_partner_si(m, m_phi, 1.0, "b")
    assert f_p > 0 and f_p == pytest.approx(f_n, rel=0.05)


def test_the_anapole_form_factor_matches_kopp_et_al():
    assert loops.anapole_moment(100.0, 100.0 * math.sqrt(1.1), 1.0, M_MU) == pytest.approx(5.53e-6, rel=0.01)
    heavy = loops.anapole_moment(100.0, 2000.0, 1.0, M_MU)          # μ ≫ 1: e y²[ln(m_φ²/m_ℓ²) − 3/2]/(48π² m_φ²)
    assert heavy == pytest.approx(loops.E_CHARGE * (math.log(2000.0 ** 2 / M_MU ** 2) - 1.5)
                                  / (48 * math.pi ** 2 * 2000.0 ** 2), rel=0.01)


def test_a_dirac_lepton_partner_has_a_magnetic_moment_and_a_charge_radius():
    moment, radius = loops.dirac_moments(100.0, 110.0, 1.0, M_MU)
    assert moment / loops.E_CHARGE == pytest.approx(3.54e-5, rel=0.01)
    assert radius / loops.E_CHARGE == pytest.approx(5.16e-6, rel=0.01)


@pytest.mark.parametrize("m_a, m, sigma_p", [(250.0, 100.0, 9.0e-48), (250.0, 500.0, 2.7e-47), (100.0, 100.0, 9.8e-47),
                                             (250.0, 10.0, 1.5e-49)])
def test_the_2hdma_triangles_at_the_working_group_benchmark(m_a, m, sigma_p):
    c_p, _ = loops.two_hdma_si(m, m_a, 600.0, 600.0, 600.0, 0.35, 1.0, 3.0, 3.0, 3.0, 1.0)
    assert _sigma(c_p, m) == pytest.approx(sigma_p, rel=0.04)


def test_the_2hdma_triangles_reproduce_abe_fujiwara_hisano():
    """Sec. 4.1: with M² = m_H² the H couplings vanish and the triangles are 0.6 × the haa diagram."""
    lam3 = loops.M_H ** 2 / loops.V_EW ** 2
    g = loops.two_hdma_couplings(100.0, 600.0, 600.0, 600.0, 0.1, 40.0, lam3, 0.0, 0.0)
    assert g["Haa"] == pytest.approx(0.0, abs=1e-9) and g["haA"] < 0 < g["haa"] < abs(g["haA"])
    m, s = 1000.0, 0.1
    c = math.sqrt(1 - s * s)
    haa = g["haa"] * c * c * loops._b0_prime(100.0, m)
    total = haa + g["hAA"] * s * s * loops._b0_prime(600.0, m) \
        + 2 * g["haA"] * s * c * loops._b1_difference(600.0, 100.0, m) / (600.0 ** 2 - 100.0 ** 2)
    assert total / haa == pytest.approx(0.601, abs=0.005)

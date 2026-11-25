"""Units, constants and conventions."""

from __future__ import annotations

import math

import pytest

from adroit.physics import conventions as cv


def test_isospin_and_nucleon_bases_are_inverse() -> None:
    assert cv.to_isospin(3.0, 1.0) == (2.0, 1.0)
    assert cv.to_nucleon(2.0, 1.0) == (3.0, 1.0)
    # isoscalar: equal couplings; isovector: opposite couplings
    assert cv.to_nucleon(1.0, 0.0) == (1.0, 1.0) and cv.to_nucleon(0.0, 1.0) == (1.0, -1.0)


def test_a_dimensionless_coupling_is_in_units_of_the_weak_scale() -> None:
    assert cv.coupling_gev2(1.0) == pytest.approx(1.0 / 246.2 ** 2)
    assert cv.dimensionless_coupling(cv.coupling_gev2(0.37)) == pytest.approx(0.37)


def test_the_spin_independent_cross_section_and_its_inverse() -> None:
    # LZ's relation (arXiv:2609.02823, supplement): (c m_v^2)^2 = sigma pi m_v^4 / mu^2
    m_x, sigma = 1000.0, 1.0e-46
    c = cv.c1_from_sigma_si(sigma, m_x)
    assert cv.sigma_si_cm2(c, m_x) == pytest.approx(sigma)
    mu_cm = cv.reduced_mass(m_x, cv.M_NUCLEON_GEV) * cv.HBARC_GEV_CM
    assert cv.dimensionless_coupling(c) ** 2 == pytest.approx(
        sigma * math.pi * cv.M_V_GEV ** 4 / mu_cm ** 2)
    # the choice of nucleon mass is a 1.5% effect on the cross-section at fixed coupling
    ratio = cv.sigma_si_cm2(c, m_x, cv.AMU_GEV) / cv.sigma_si_cm2(c, m_x)
    assert ratio == pytest.approx((cv.AMU_GEV / cv.M_NUCLEON_GEV) ** 2, rel=1e-3)
    assert 0.98 < ratio < 0.99


def test_the_momentum_transfer_of_the_lz_event() -> None:
    # a 248 keV recoil on xenon-131: q = sqrt(2 m_T E_R), about 246 MeV
    q = cv.momentum_transfer_gev(248.0, cv.nuclear_mass_gev(131))
    assert q == pytest.approx(0.246, abs=0.001)


def test_the_least_speed_for_a_recoil() -> None:
    m_t = cv.nuclear_mass_gev(131)
    elastic = cv.v_min_km_s(10.0, m_t, 100.0)
    mu = cv.reduced_mass(100.0, m_t)
    assert elastic == pytest.approx(math.sqrt(m_t * 10e-6 / (2 * mu ** 2)) * cv.C_KM_S)
    # an endothermic splitting raises the least speed; an exothermic one lowers it here
    assert cv.v_min_km_s(10.0, m_t, 100.0, 50.0) > elastic > cv.v_min_km_s(10.0, m_t, 100.0, -5.0)
    # at the recoil energy E = mu |delta| / m_T an exothermic scatter needs no speed at all
    e_star = mu * 5e-6 / m_t / cv.KEV
    assert cv.v_min_km_s(e_star, m_t, 100.0, -5.0) == pytest.approx(0.0, abs=1e-9)

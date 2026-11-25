"""Hadronic final states below 2 GeV (constraints.hadrons) and their use in the vector portals."""

import numpy as np
import pytest

from adroit.constraints import hadrons
from adroit.constraints.searches import _tool
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.vector import ChargedZPrime, DarkPhoton

needs_pdg = pytest.mark.skipif(not hadrons.available(), reason="the PDG's R-ratio file is not in the tools folder")
needs_darkcast = pytest.mark.skipif(_tool("DarkCast") is None, reason="DarkCast is not in the tools folder")


@needs_pdg
def test_the_measured_r_ratio_at_its_resonances_and_its_edges():
    r = hadrons.r_ratio(np.array([0.2, 0.3, 0.78, 1.02, 1.99]))
    assert r[0] == 0.0 and r[1] == pytest.approx(0.01996)
    assert r[2] > 15 and r[3] > 40 and r[4] == pytest.approx(2.175, rel=0.01)


@needs_darkcast
def test_a_b_minus_l_vector_has_no_rho_and_reaches_the_parton_value():
    ratio = hadrons.baryonic_ratio(np.array([0.5, 0.78, 2.0]))
    assert ratio[0] < 0.01 and ratio[1] > 20 and ratio[2] == pytest.approx(1.0, rel=0.01)


def test_the_muon_width_has_the_vector_formula():
    assert hadrons.muon_width(1.0, 0.1, massless=True) == pytest.approx(0.01 / (12 * np.pi))
    assert hadrons.muon_width(0.2, 0.1) == 0.0


@needs_pdg
def test_light_dark_photon_dark_matter_annihilates_into_hadrons_continuously_at_two_gev():
    dp = DarkPhoton()
    p = Point(m_chi=0.8, m_med=3.0, g_chi=1.0, g_q=1e-4)
    below = dp.channels(np.array([1.99 ** 2]), p)
    above = dp.channels(np.array([2.01 ** 2]), p)
    quarks_above = sum(float(above[q][0]) for q in ("u", "d", "s")) / float(above["e"][0])     # ≈ N_c Σ Q² = 2
    assert "hadrons" in below and "u" in above
    assert float(below["hadrons"][0]) / float(below["e"][0]) == pytest.approx(quarks_above, rel=0.1)   # R ≈ 2.18
    assert dp.domain(Point(m_chi=0.3, m_med=0.9, g_q=1e-4)) == ""
    assert "BBN" in dp.domain(Point(m_chi=0.005, m_med=0.015, g_q=1e-4))
    assert dp.omega_h2(Point(m_chi=0.3, m_med=0.9, g_chi=1.0, g_q=1e-4)) > 0


@needs_darkcast
def test_b_minus_l_below_a_gev_is_computed():
    assert ChargedZPrime().omega_h2(Point(m_chi=0.5, m_med=1.5, g_chi=1e-3, g_q=1e-3)) > 0

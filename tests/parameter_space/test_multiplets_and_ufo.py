"""Electroweak multiplets, bound states of coloured partners, and the portals read from UFO files."""

import math

import numpy as np
import pytest

from adroit.constraints import relic, sommerfeld
from adroit.parameter_space import library
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals import multiplet as mp


@pytest.mark.parametrize("kind, expected", [("wino", lambda t2: 37.0 / 12.0),
                                            ("higgsino", lambda t2: (81 + 12 * t2 + 43 * t2 ** 2) / 128.0)])
def test_the_multiplets_tree_rate_is_the_griest_seckel_sigma_eff(kind, expected):
    m = 1500.0
    sectors = mp.wino_sectors(m) if kind == "wino" else mp.higgsino_sectors(m)
    unit = math.pi * mp.alpha_2(2 * m) ** 2 / m ** 2
    trace = sum(sx.multiplicity * np.trace(sx.gamma) for sx in sectors) / unit
    assert trace == pytest.approx(expected(mp.alpha_y(2 * m) / mp.alpha_2(2 * m)), rel=1e-12)


def test_the_wino_rate_without_the_sommerfeld_effect_is_the_tree_level_one():
    rate = mp.effective_rate("wino", 2000.0, 0.165, np.array([80.0]), sommerfeld_on=False)[0]
    unit = math.pi * mp.alpha_2(4000.0) ** 2 / 2000.0 ** 2
    assert rate == pytest.approx(37.0 / 12.0 * unit, rel=0.03)          # the splitting is ≪ T


def test_the_sommerfeld_effect_tends_to_one_at_high_speed_and_grows_at_low_speed():
    kinetic, sectors = mp.rate_table("wino", 2500.0, 0.165, True)
    _, _, tree = mp.rate_table("wino", 2500.0, 0.165, False)[1][0]
    ratio = sectors[0][2] / tree                                        # Q = 0, S = 0
    assert ratio[1, -1] == pytest.approx(1.0, abs=0.25) and ratio[1, 0] > 10.0


def test_the_bound_state_rate_is_suppressed_by_ionisation_when_hot():
    m = 1500.0
    hot, cold = sommerfeld.bound_state_rate(m, np.array([m / 10.0, m / 2000.0]))
    v = np.array([0.05])
    assert 0.0 < hot < cold
    assert sommerfeld.binding_energy(m) == pytest.approx(4.0 / 9.0 * m * sommerfeld.alpha_bohr(m) ** 2)
    assert sommerfeld.bsf_sigma_v(v, m)[0] > 0


def test_a_thermal_pair_rate_enters_with_its_equilibrium_weight():
    species = [relic.Species(100.0, 2.0), relic.Species(100.0, 2.0)]
    x = np.array([20.0])
    assert relic.pair_weight(species, 0, 1, x)[0] == pytest.approx(0.5)
    base = relic.omega_h2_species(species, {(0, 1): lambda s: np.full_like(s, 3e-9)})
    more = relic.omega_h2_species(species, {(0, 1): lambda s: np.full_like(s, 3e-9)},
                                  thermal={(0, 1): lambda t: np.full_like(t, 3e-9)})
    assert more < base


def test_the_new_library_entries_are_listed():
    ids = {e.id for e in library.ENTRIES}
    assert {"inert_doublet", "two_hdm_a", "wino", "higgsino"} <= ids


ufo = pytest.mark.skipif(not (library.INERT_DOUBLET.model_dir and
                              __import__("adroit.constraints.maddm", fromlist=["available"]).available()),
                         reason="MadGraph's Python is needed to read UFO files")


@pytest.mark.slow
@ufo
@pytest.mark.parametrize("point, reference", [((100, 200, 0.002, 5), 1.848e-3), ((990, 998.12, -0.051, 2.36), 0.1263)])
def test_the_inert_doublet_matches_micromegas(point, reference):
    m_h, m_c, lam, d_a = point
    omega = library.INERT_DOUBLET.omega_h2(Point(m_chi=m_h, m_med=m_c, g_chi=lam, g_q=d_a))
    assert omega == pytest.approx(reference, rel=0.05)   # micrOMEGAs 7.1.10, same inputs: Belyaev BM6, Kalinowski HP10


@pytest.mark.slow
@ufo
def test_the_2hdma_matches_maddm_on_the_same_ufo():
    from adroit.parameter_space.portals.ufo import UFOPortal
    model = UFOPortal(**{**library.TWO_HDM_A.model_dump(), "parameters": {**library.TWO_HDM_A.parameters,
                                                                           "mh2": "600.0", "mh3": "600.0", "mhc": "600.0"}})
    omega = model.omega_h2(Point(m_chi=150.0, m_med=250.0, g_chi=1.0, g_q=0.35, g_l=1.0))
    assert omega == pytest.approx(0.534, rel=0.20)    # MadDM 3.3, same UFO; its g* counts ghosts (DM8), ≈ −10% on Ωh²

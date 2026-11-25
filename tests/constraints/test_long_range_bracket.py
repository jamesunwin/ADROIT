"""The Sommerfeld bracket of G4's estimate (decision D4): group theory, the factor's limits, and the bracket's order."""

import math

import numpy as np
import pytest

from adroit.constraints import long_range_bracket as lb
from adroit.constraints import relic, sommerfeld
from adroit.parameter_space.portals import nplet

SU2 = lb.GaugeForce(group="SU2", alpha=0.033, mediator_gev=80.4)
HYPERCHARGE = lb.GaugeForce(group="U1", name="Y", alpha=0.0102)


@pytest.mark.parametrize("n, y", [(2, 0.5), (3, 0.0), (4, 0.5), (5, 0.0), (5, 1.0)])
def test_electroweak_channels_are_the_nplet_engines(n, y):
    pair = lb.PairRep(su2=(n, n), charges={"Y": (y, -y)} if y else {})
    found = lb.channels(pair, [SU2, HYPERCHARGE])
    assert [c.su2 for c in found] == list(range(1, 2 * n, 2))
    for c in found:
        assert c.alpha == pytest.approx(0.033 * nplet.lam(n, c.su2) + y * y * 0.0102, rel=1e-12)
    assert sum(c.share for c in found) == pytest.approx(1.0)


def test_colour_channels_are_sommerfelds_colour_factors():
    gluon = [lb.GaugeForce(group="SU3", alpha=1.0)]
    pair = {c.su3: c.alpha for c in lb.channels(lb.PairRep(su3=("3", "3bar")), gluon)}
    same = {c.su3: c.alpha for c in lb.channels(lb.PairRep(su3=("3", "3")), gluon)}
    assert pair["1"] == pytest.approx(sommerfeld.COLOUR["singlet"]) and pair["8"] == pytest.approx(
        sommerfeld.COLOUR["octet"])
    assert same["3bar"] == pytest.approx(sommerfeld.COLOUR["antitriplet"]) and same["6"] == pytest.approx(
        sommerfeld.COLOUR["sextet"])
    octets = lb.channels(lb.PairRep(su3=("8", "8")), gluon)
    assert sum(c.share for c in octets) == pytest.approx(1.0) and max(c.alpha for c in octets) == pytest.approx(3.0)
    with pytest.raises(ValueError, match="not tabulated"):
        lb.su3_product("6", "6")


def test_an_abelian_pair_attracts_as_particle_and_antiparticle_and_repels_as_two_particles():
    dark = [lb.GaugeForce(group="U1", name="D", alpha=0.1)]
    assert lb.channels(lb.PairRep(charges={"D": (1.0, -1.0)}), dark)[0].alpha == pytest.approx(0.1)
    assert lb.channels(lb.PairRep(charges={"D": (1.0, 1.0)}), dark)[0].alpha == pytest.approx(-0.1)
    assert lb.channels(lb.PairRep(), dark)[0].alpha == 0.0                     # no charge: no force


def test_the_factor_is_coulombs_without_a_mediator_mass_and_one_without_a_force():
    v = np.array([1e-4, 1e-2, 0.5])
    assert lb.sommerfeld_factor(0.0, v, 1000.0, 80.0) == pytest.approx(1.0)
    x = 2 * math.pi * 0.05 / v
    assert lb.sommerfeld_factor(0.05, v, 1000.0, 0.0) == pytest.approx(x / -np.expm1(-x), rel=1e-12)
    assert lb.sommerfeld_factor(0.05, v[1:], 1000.0, 0.0) == pytest.approx(sommerfeld.coulomb(0.05, v[1:] / 2),
                                                                         rel=1e-12)      # X = πα/β, v = 2β


def test_a_massive_mediator_saturates_and_switches_the_effect_off_below_the_bohr_momentum():
    v = np.geomspace(1e-6, 1e-4, 3)
    m, m_v, alpha = 3000.0, 80.4, 0.066
    saturated = lb.sommerfeld_factor(alpha, v, m, m_v)
    assert saturated == pytest.approx(2 * math.pi ** 2 * alpha * m / (lb.KAPPA * m_v), rel=1e-3)   # off resonance
    assert lb.sommerfeld_factor(0.003, v, 100.0, 80.4) == pytest.approx(1.0, abs=0.01)             # αμ ≪ m_V
    repulsive = np.geomspace(1e-4, 0.9, 6)
    assert lb.sommerfeld_factor(-0.033, repulsive, m, m_v) == pytest.approx(nplet.hulthen(-0.033, repulsive, m, m_v),
                                                                           rel=1e-10)
    far = np.array([0.3, 0.9])                                     # long range: Coulomb's, as the exact Hulthén
    assert lb.sommerfeld_factor(alpha, far, m, m_v) == pytest.approx(nplet.hulthen(alpha, far, m, m_v), rel=1e-6)


def test_the_thermal_factor_grows_as_the_bath_cools():
    x = np.array([1.0, 25.0, 1e3])
    s = lb.thermal_factor(0.1, 0.0, 1000.0, x)
    assert s[0] > 1.0 and np.all(np.diff(s) > 0)
    assert lb.thermal_factor(0.0, 0.0, 1000.0, x) == pytest.approx(1.0, abs=2e-3)


def toy(m: float):
    """A Majorana triplet with a constant perturbative rate (the wino's tree-level 37πα₂²/12M²)."""
    species = [relic.Species(m, 2.0)] * 3
    x = np.geomspace(1.0, 2e4, 140)
    rate = np.full_like(x, 37 * math.pi * 0.033 ** 2 / (12 * m * m))
    return species, x, [lb.PairRate(pair=lb.PairRep(su2=(3, 3)), rate=rate.tolist())], [SU2]


def test_the_bracket_orders_low_central_high_around_the_perturbative_value():
    b = lb.bracket(*toy(2500.0))
    assert b.omega_low < b.omega_central < b.omega_perturbative
    assert b.omega_low < b.omega_high
    assert b.alpha_max == pytest.approx(2 * 0.033) and b.alpha_min == pytest.approx(-0.033)
    assert "bound states" in b.warning.lower()
    shares = toy(2500.0)
    shares[2][0] = shares[2][0].model_copy(update={"shares": {"1/1": 1.0}})
    assert lb.bracket(*shares).omega_central == pytest.approx(b.omega_low, rel=1e-12)   # all in the strongest


def test_thermal_masses_bracket_the_perturbative_mass():
    masses = lb.thermal_masses(toy, target=0.12, guess=2000.0, tolerance=5e-3)
    assert masses["high"] < masses["perturbative"] < masses["central"] < masses["low"]
    assert masses["perturbative"] == pytest.approx(2.2e3, rel=0.15)       # the tree-level wino, ≈ 2.2–2.4 TeV


def test_the_selection_rule_drops_channels_no_standard_model_pair_can_carry():
    """A 5-plet pair annihilates into two Standard Model particles only from I ≤ 5 (W ⊗ W): the high edge then uses
    the least attractive of I = 1, 3, 5 (3α₂), not the repulsive I = 9."""
    species, x, pairs, forces = toy(10000.0)
    five = pairs[0].model_copy(update={"pair": lb.PairRep(su2=(5, 5))})
    plain = lb.bracket(species, x, [five], forces)
    ruled = lb.bracket(species, x, [five.model_copy(update={"final_su2_max": 5})], forces)
    assert plain.alpha_min == pytest.approx(-4 * 0.033) and ruled.alpha_min == pytest.approx(3 * 0.033)
    assert ruled.omega_low == pytest.approx(plain.omega_low, rel=1e-12)
    assert ruled.omega_high < plain.omega_high and ruled.omega_central < plain.omega_central
    assert sum(c.share for c in ruled.channels) == pytest.approx(1.0)

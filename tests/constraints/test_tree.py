"""The general tree-level engine, the UFO importer and the Sommerfeld factor."""

import math

import numpy as np
import pytest

from adroit.constraints import exchange, processes, sommerfeld, tree

E, V, MH = 0.3, 246.22, 125.09


def scalar_qed(mass: float = 300.0) -> tree.Model:
    m = tree.Model({})
    m.add(tree.Particle("phi", 0, mass, anti="phi~"), tree.Particle("A", 1, 0.0))
    m.vertices += [tree.Vertex("VSS", ("A", "phi", "phi~"), -E), tree.Vertex("VVSS", ("A", "A", "phi", "phi~"), 2 * E * E)]
    return m


def test_scalar_qed_matches_the_hand_built_amplitude():
    s = 600.0 ** 2 * 1.5
    assert tree.Process(scalar_qed(), "phi", "phi~", "A", "A").sigma(s) == pytest.approx(
        processes.partners_to_gauge_bosons(s, 300.0, E, coloured=False), rel=1e-9)


def test_singlet_scalars_into_higgs_pairs_match_the_hand_built_amplitude():
    lam, ms = 0.3, 400.0
    m = tree.Model({})
    m.add(tree.Particle("S", 0, ms), tree.Particle("h", 0, MH, width=0.0041))
    m.vertices += [tree.Vertex("SSS", ("S", "S", "h"), -lam * V), tree.Vertex("SSSS", ("S", "S", "h", "h"), -lam),
                   tree.Vertex("SSS", ("h", "h", "h"), -3 * MH ** 2 / V)]
    s = (2 * ms) ** 2 * 1.3
    contact = lam * (1 + 3 * MH ** 2 / (s - MH ** 2 + 1j * MH * 0.0041))
    assert tree.Process(m, "S", "S", "h", "h").sigma(s) == pytest.approx(
        processes.scalars_to_scalars(s, ms, MH, contact, lam * V, ms), rel=1e-9)


def test_fermions_into_scalar_pairs_and_into_fermions():
    m = tree.Model({})
    m.add(tree.Particle("chi", 0.5, 500.0, anti="chi~"), tree.Particle("phi", 0, 300.0),
          tree.Particle("V", 1, 500.0, 5.0), tree.Particle("b", 0.5, 4.7, anti="b~", colours=3))
    m.vertices += [tree.Vertex("FFS", ("chi~", "chi", "phi"), -0.7, -0.4),
                   tree.Vertex("FFV", ("chi~", "chi", "V"), -0.8, -0.2), tree.Vertex("FFV", ("b~", "b", "V"), -0.1, -0.05)]
    s = 1300.0 ** 2
    assert tree.Process(m, "chi", "chi~", "phi", "phi").sigma(s) == pytest.approx(
        processes.fermion_to_scalars(s, 500.0, 300.0, 300.0, (0.7, 0.4), (0.7, 0.4), identical=True), rel=1e-9)
    assert tree.Process(m, "chi", "chi~", "b", "b~").sigma(s) == pytest.approx(
        exchange.vector_to_fermions(np.array([s]), 500.0, "fermion", [(0.8, 0.2)], 4.7, 3, [(0.1, 0.05)],
                                    [exchange.Mediator(500.0, 5.0)])[0], rel=1e-9)


def test_a_process_without_a_diagram_is_refused():
    with pytest.raises(ValueError):
        tree.Process(scalar_qed(), "phi", "phi", "A", "A")


def test_the_coulomb_sommerfeld_factor():
    assert sommerfeld.coulomb(0.0, np.array([0.1]))[0] == pytest.approx(1.0)
    x = math.pi * 0.1 / 0.05
    assert sommerfeld.coulomb(0.1, np.array([0.05]))[0] == pytest.approx(x / (1 - math.exp(-x)))
    assert sommerfeld.coulomb(-0.1, np.array([0.05]))[0] < 1.0
    assert sommerfeld.COLOUR["singlet"] == pytest.approx(4 / 3) and sommerfeld.COLOUR["octet"] == pytest.approx(-1 / 6)


def test_coloured_cross_sections_split_by_colour_sum_to_the_total():
    s = 4 * 500.0 ** 2 / (1 - 0.0005 ** 2)
    one, eight = processes.partners_to_gauge_bosons_by_colour(s, 500.0, 1.0, True)
    assert one / (one + eight) == pytest.approx(2 / 7, rel=1e-4)
    s = 1100.0 ** 2
    assert sum(processes.partners_to_fermions_by_colour(s, 500.0, 0.0, 1.0, 1.0, True, y=0.7, m_chi=450.0)) == \
        pytest.approx(processes.partners_to_fermions(s, 500.0, 0.0, 1.0, 1.0, True, y=0.7, m_chi=450.0))
    six, three = processes.partners_to_same_fermions_by_colour(s, 500.0, 0.0, 450.0, 0.7, True)
    assert six + three == pytest.approx(processes.partners_to_same_fermions(s, 500.0, 0.0, 450.0, 0.7, True))


def test_ufo_lorentz_structures_are_translated():
    from adroit.constraints import ufo_model
    assert ufo_model._vss("P(1,2) - P(1,3)") == (1, 2, 3, 1.0)
    assert ufo_model._fermion_matrix("ProjM(2,1)") == (0.5, -0.5)
    assert ufo_model._vector_matrix("Gamma(3,2,-1)*ProjM(-1,1) - 2*Gamma(3,2,-1)*ProjP(-1,1)") == (-0.5, -1.5)
    assert ufo_model._vector_matrix("Gamma(3,2,1)*Something(1)") is None


@pytest.mark.parametrize("alpha, beta", [(0.1, 0.3), (0.1, 0.02), (-0.05, 0.05)])
def test_the_multi_state_solver_reproduces_the_coulomb_factor(alpha, beta):
    m = 1000.0
    a = sommerfeld.enhancement(lambda r: np.array([[-alpha / r]]), np.array([0.0]), np.array([alpha]), m / 2,
                               m * beta ** 2, r_max=50.0 / (m / 2 * beta))
    assert abs(a[0, 0]) ** 2 == pytest.approx(sommerfeld.coulomb(alpha, np.array([beta]))[0], rel=1e-3)


def test_a_yukawa_potential_interpolates_between_coulomb_and_no_enhancement():
    m, alpha, beta = 2000.0, 0.03, 0.05

    def s(mass):
        a = sommerfeld.enhancement(lambda r: np.array([[-alpha * np.exp(-mass * r) / r]]), np.array([0.0]),
                                   np.array([0.0]), m / 2, m * beta ** 2, r_max=max(40.0 / mass, 30.0 / (m / 2 * beta)))
        return abs(a[0, 0]) ** 2
    assert s(0.1) == pytest.approx(sommerfeld.coulomb(alpha, np.array([beta]))[0], rel=1e-3)
    assert 1.0 < s(1000.0) < s(80.0) < s(0.1)


def test_a_dirac_pair_of_two_particles_does_not_annihilate_through_a_particle_antiparticle_vertex():
    m = tree.Model({})
    m.add(tree.Particle("chi", 0.5, 100.0, anti="chi~"), tree.Particle("a", 0, 300.0, width=3.0),
          tree.Particle("b", 0.5, 4.7, anti="b~", colours=3))
    m.vertices += [tree.Vertex("FFS", ("chi~", "chi", "a"), 0.0, 1.0), tree.Vertex("FFS", ("b~", "b", "a"), 0.0, 0.02)]
    s = 250.0 ** 2
    assert tree.Process(m, "chi", "chi~", "b", "b~").sigma(s) > 0
    assert tree.Process(m, "chi", "chi", "b", "b~").sigma(s) == 0.0

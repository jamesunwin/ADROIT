"""The interaction library (DM4): cards, their resolution, graph, kinematics, checks, degeneracy."""

from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.core.dm_state import DarkMatterParticle, ModelLayer
from adroit.library.interactions import checks, degeneracy, kinematics, registry
from adroit.library.interactions.schema import Kinematics
from adroit.physics import nuclear, rates, targets
from adroit.physics.conventions import M_V_GEV, OPERATOR_MASS_GEV

PARTICLE = DarkMatterParticle(mass_gev=100.0)
LZ_PAIRS = {(1, 5), (2, 8), (3, 17), (4, 20), (11, 14)}


def _coefficients(card_id: str, values: dict | None = None, particle=PARTICLE) -> dict:
    """(operator, q_power) → (c^p, c^n) of a resolved card."""
    model = registry.resolve(card_id, particle, values)
    return {(c.operator, c.q_power): (c.proton, c.neutron) for c in model.coefficients}


# --- the cards ---------------------------------------------------------------------------


def test_the_library_loads_three_consistent_layers() -> None:
    cards = registry.cards()
    layers = [c.layer for c in cards.values()]
    assert layers.count(ModelLayer.nonrelativistic) == 14
    assert layers.count(ModelLayer.relativistic) == 27            # L1–L20, and LZ's L5–L9, L13, L17
    assert {f"L{j:02d}" for j in range(1, 21)} <= set(cards)
    assert layers.count(ModelLayer.mediator) >= 12
    assert registry.check_library() == []


def test_each_operator_card_lists_the_responses_the_rate_code_gives_it() -> None:
    qm2 = np.array([0.01, 0.05])
    for card in registry.cards().values():
        if card.layer is not ModelLayer.nonrelativistic:
            continue
        a = np.zeros(16)
        a[int(card.id[1:])] = 1.0
        plain, transverse = rates._pair_weights(a, a, 0.75, qm2)
        reached = {nuclear.RESPONSES[k] for k in range(len(nuclear.RESPONSES))
                   if np.any(plain[k] != 0) or np.any(transverse[k] != 0)}
        assert set(card.responses) == reached, card.id


def test_the_lagrangian_table_has_exactly_the_proportional_pairs_lz_found() -> None:
    # arXiv:2609.02823 (supplement): L1/L5, L2/L8, L3/L17, L4/L20, L11/L14 differ by a constant.
    # Our transcription of arXiv:1308.6288's Table 1 must give these and no others.
    models = {j: registry.resolve(f"L{j:02d}", PARTICLE,
                                  registry.isospin_values(f"L{j:02d}", "s", 1.0))
              for j in range(1, 21)}
    found = {(a, b) for a in range(1, 21) for b in range(a + 1, 21)
             if degeneracy.proportional(models[a], models[b])}
    assert found == LZ_PAIRS


def test_lzs_own_cards_have_exactly_the_proportional_pairs_lz_found() -> None:
    """The same pairs with the interactions as LZ computes them (lz_extended_window.LZ_CARDS), and no others."""
    from adroit.experiments.lz_extended_window import LZ_CARDS, lz_values
    names = {j: LZ_CARDS.get(f"L{j:02d}", f"L{j:02d}") for j in range(1, 21)}
    models = {j: registry.resolve(names[j], PARTICLE, lz_values(names[j], "s")) for j in range(1, 21)}
    found = {(a, b) for a in range(1, 21) for b in range(a + 1, 21)
             if degeneracy.proportional(models[a], models[b])}
    assert found == LZ_PAIRS


def test_lagrangian_reductions_follow_the_table() -> None:
    d = 1.0 / M_V_GEV ** 2
    m_chi, m_n, m_m = 100.0, OPERATOR_MASS_GEV, M_V_GEV
    l06 = _coefficients("L06")
    assert l06[(1, 2)][0] == pytest.approx(-d * m_chi / m_n / m_m ** 2)
    assert l06[(3, 0)][0] == pytest.approx(4 * d * m_chi * m_n / m_m ** 2)
    assert _coefficients("L15")[(4, 0)] == pytest.approx((-4 * d, -4 * d))
    isovector = _coefficients("L01", registry.isospin_values("L01", "v", d))
    assert isovector[(1, 0)] == pytest.approx((d, -d))


def test_the_matching_scale_cancels_in_every_mediator_card() -> None:
    for card in registry.cards().values():
        if card.layer is not ModelLayer.mediator:
            continue
        default = _coefficients(card.id)
        moved = _coefficients(card.id, {"m_M": 3.7 * M_V_GEV})
        assert moved.keys() == default.keys(), card.id
        for key, value in default.items():
            assert moved[key] == pytest.approx(value, rel=1e-12, abs=1e-30), (card.id, key)


# --- mediators against known results ----------------------------------------------------


def test_heavy_mediators_give_the_standard_contact_couplings() -> None:
    g, m = 0.5, 2000.0
    vector = _coefficients("M_vector", {"g_chi": 1.0, "gV_p": g, "gV_n": g, "m_med": m})
    assert vector[(1, 0)] == pytest.approx((-g / m ** 2, -g / m ** 2))
    axial = _coefficients("M_axial", {"g_chi": 1.0, "gA_p": g, "gA_n": -g, "m_med": m})
    assert axial[(4, 0)] == pytest.approx((4 * g / m ** 2, -4 * g / m ** 2))
    scalar = _coefficients("M_scalar", {"g_chi": 2.0, "gS_p": g, "gS_n": g, "m_med": m})
    assert scalar[(1, 0)] == pytest.approx((2 * g / m ** 2,) * 2)
    light = registry.resolve("M_scalar", PARTICLE, {"m_med": 0.01}).coefficients[0]
    assert light.mediator_mass_gev == 0.01


def test_the_magnetic_dipole_reproduces_the_classic_charge_scattering() -> None:
    card = registry.card("M_magnetic_dipole")
    e, kappa, mu = card.parameter("e").default, card.parameter("kappa_p").default, 1e-8
    m_chi, m_n = PARTICLE.mass_gev, OPERATOR_MASS_GEV
    c = _coefficients("M_magnetic_dipole", {"mu_chi": mu})
    # up to one overall sign; the spin terms (c4, c6) have the sign opposite to the charge
    # term c5, as the explicit reduction gives (corrected 2026-10-01, docs/dm8_lagrangians.md)
    assert c[(1, 0)][0] == pytest.approx(e * mu / (2 * m_chi))
    assert c[(5, -2)][0] == pytest.approx(-2 * e * mu * m_n)           # −2 e μ Q m_N / q²
    assert c[(4, 0)][0] == pytest.approx(2 * e * mu * (1 + kappa) / m_n)
    assert c[(6, -2)][0] == pytest.approx(-2 * e * mu * (1 + kappa) * m_n)
    assert c[(5, -2)][1] == 0.0                                         # neutral neutron
    # on a proton target the charge part, c1² + (q/m_N)² v⊥² c5²/4, is
    # e²μ²[v²/q² − 1/(4m_T²) − 1/(2 m_T m_χ)]: the Z² term of the textbook cross-section
    m_t, q, v = m_n, 0.05, 1e-3
    mu_t = m_chi * m_t / (m_chi + m_t)
    vperp2 = v * v - q * q / (4 * mu_t ** 2)
    charge = c[(1, 0)][0] ** 2 + (q / m_n) ** 2 * vperp2 * (c[(5, -2)][0] / q ** 2) ** 2 / 4
    assert charge == pytest.approx(e ** 2 * mu ** 2 * (v * v / q ** 2 - 1 / (4 * m_t ** 2)
                                                       - 1 / (2 * m_t * m_chi)), rel=1e-9)


def test_the_anapole_and_charge_radius_couplings() -> None:
    e = registry.card("M_anapole").parameter("e").default
    kappa_p = registry.card("M_anapole").parameter("kappa_p").default
    kappa_n = registry.card("M_anapole").parameter("kappa_n").default
    a = _coefficients("M_anapole", {"anapole": 1e-4})
    assert a[(8, 0)] == pytest.approx((2 * e * 1e-4, 0.0))
    assert a[(9, 0)] == pytest.approx((2 * e * (1 + kappa_p) * 1e-4, 2 * e * kappa_n * 1e-4))
    b = _coefficients("M_charge_radius", {"b_chi": 1e-4})
    assert b[(1, 0)] == pytest.approx((e * 1e-4, 0.0))


def test_the_portals() -> None:
    higgs = registry.card("M_higgs_portal")
    f_p = higgs.parameter("fN_p").default
    assert 0.29 < f_p < 0.32 and 0.29 < higgs.parameter("fN_n").default < 0.32
    c = _coefficients("M_higgs_portal", {"y_chi": 0.2})
    m_n, v, m_h = (higgs.parameter(n).default for n in ("m_nucleon", "v_h", "m_h"))
    assert c[(1, 0)][0] == pytest.approx(0.2 * f_p * m_n / (v * m_h ** 2))
    z = registry.card("M_z_portal")
    g_f, ga_p = z.parameter("G_F").default, z.parameter("gA_p").default
    zc = _coefficients("M_z_portal", {"gV_chi": 0.5, "gA_chi": 0.5})
    assert zc[(4, 0)][0] == pytest.approx(4 * math.sqrt(2) * g_f * 0.5 * ga_p)
    assert zc[(1, 0)][1] == pytest.approx(math.sqrt(2) * g_f * 0.5 * 0.5)   # −√2 G_F g_V g_V^n


# --- graph, kinematics, checks --------------------------------------------------------------


def test_the_neighbour_graph() -> None:
    g = registry.graph()
    assert g.number_of_nodes() == len(registry.cards())

    def deformations(a: str, b: str) -> set[str]:
        return {d["deformation"] for d in g.get_edge_data(a, b, default={}).values()}

    assert deformations("L06", "O1") == {"nonrelativistic_limit"}
    assert deformations("M_vector", "L10") == {"integrate_out_mediator"}
    assert {"change_isospin", "add_mass_splitting"} <= deformations("O1", "O1")
    assert "make_mediator_light" in deformations("M_vector", "M_vector")
    assert "add_mass_splitting" in deformations("M_vector", "M_pseudo_dirac_vector")
    assert "specialise_couplings" in deformations("M_scalar", "M_higgs_portal")


def test_kinematic_modifiers() -> None:
    o1, pseudo_dirac = registry.card("O1"), registry.card("M_pseudo_dirac_vector")
    assert kinematics.apply(o1, PARTICLE, Kinematics.inelastic, 120.0).mass_splitting_kev == 120.0
    assert kinematics.apply(o1, PARTICLE, Kinematics.exothermic, 50.0).mass_splitting_kev == -50.0
    with pytest.raises(ValueError, match="does not allow"):
        kinematics.apply(pseudo_dirac, PARTICLE, Kinematics.elastic)
    with pytest.raises(ValueError, match="needs a splitting"):
        kinematics.apply(o1, PARTICLE, Kinematics.inelastic)


def test_validity_flags() -> None:
    o1 = registry.card("O1")
    assert checks.flags(o1, PARTICLE, q_max_gev=0.25) == []
    assert "contact" in checks.flags(o1, PARTICLE, 0.25, mediator_mass_gev=0.5)[0]
    dipole = registry.card("M_magnetic_dipole")
    assert "Majorana" in checks.flags(dipole, PARTICLE, 0.25, majorana=True)[0]
    assert checks.flags(registry.card("L01"), PARTICLE.model_copy(update={"spin": 1.0}), 0.25)
    assert "4π" in checks.flags(registry.card("M_scalar"), PARTICLE, 0.25, {"g_chi": 20.0})[0]


# --- degeneracy -----------------------------------------------------------------------------


def test_the_divergence_and_the_classes() -> None:
    energies = np.linspace(1.0, 100.0, 200)
    a = np.exp(-energies / 20.0)
    b = np.exp(-energies / 21.0)
    c = np.exp(-energies / 60.0)
    rows = np.array([s / np.trapezoid(s, energies) for s in (a, b, c)])
    j = degeneracy.jeffreys_matrix(rows, energies)
    assert np.allclose(np.diag(j), 0.0, atol=1e-12) and np.allclose(j, j.T)
    assert j[0, 1] < j[0, 2]
    labels = ["a", "b", "c"]
    n_ab = degeneracy.events_to_separate(j[0, 1])
    assert degeneracy.classes(labels, j, n_ab / 2) == [["a", "b"], ["c"]]
    assert degeneracy.classes(labels, j, n_ab * 2) == [["a"], ["b"], ["c"]]


def test_lz_isospin_degeneracies_are_reproduced_on_xenon() -> None:
    # LZ: isoscalar and isovector spectra are indistinguishable for L2, L4, L7, L8, L10, L11,
    # L14, L15, L19, L20, and not for the others. Here N₂σ at 100 GeV, with LZ's efficiency.
    from adroit.experiments import digitised
    figure = digitised.load("lz_2026_figS2")
    energies = np.arange(1.5, 350.0, 1.0)
    efficiency = np.interp(energies, figure["energy_kev"], figure["efficiency"], left=0, right=0)
    xenon = targets.target("Xe")
    for j, degenerate in ((15, True), (10, True), (7, True), (1, False), (13, False), (6, False)):
        shapes = [degeneracy.shape(degeneracy.ModelPoint(
            label=iso, particle=PARTICLE, interaction=registry.resolve(
                f"L{j:02d}", PARTICLE, registry.isospin_values(f"L{j:02d}", iso, 1.0))),
            xenon, energies, efficiency) for iso in "sv"]
        n = degeneracy.events_to_separate(degeneracy.jeffreys_matrix(np.array(shapes),
                                                                     energies)[0, 1])
        assert (n > 100.0) == degenerate, (j, n)

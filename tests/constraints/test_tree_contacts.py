"""The tree engine's four-fermion contact vertex (FFFF, 2026-10-20): a heavy mediator's exchange equals its contact
operator, for Dirac and Majorana dark matter, scalar and vector, colourless and coloured final states; |M|² does
not depend on the fermion flow's direction."""
import numpy as np
import pytest

from adroit.constraints import tree

HEAVY = 1e5                      # GeV: s/M² ≈ 3e-5 at √s = 500 GeV


def _model(dm_anti: str, final: str, colours: int = 1) -> tree.Model:
    m = tree.Model(particles={})
    m.add(tree.Particle("chi", 0.5, 200.0, anti=dm_anti), tree.Particle(final, 0.5, 1.5, anti=f"{final}~",
                                                                        colours=colours))
    return m


def _sigma(m: tree.Model, a: str, b: str, final: str, root_s: float = 500.0) -> float:
    return tree.Process(m, a, b, final, f"{final}~").sigma(root_s ** 2)


@pytest.mark.parametrize("final, colours", [("mu", 1), ("c", 3)])
def test_a_heavy_vector_is_its_contact_operator_for_dirac_dark_matter(final, colours):
    """L ⊃ Z′·(g_χ χ̄γχ + g_f f̄γf) integrated out: −(g_χ g_f/M²)(χ̄γ^μχ)(f̄γ_μf); the vector and axial parts each."""
    g_chi, g_v, g_a = 0.8, 0.3, 0.2
    exchange = _model("chi~", final, colours)
    exchange.add(tree.Particle("Zp", 1, HEAVY, width=1.0))
    exchange.vertices += [tree.Vertex("FFV", ("chi~", "chi", "Zp"), g_chi, 0.0),
                          tree.Vertex("FFV", (f"{final}~", final, "Zp"), g_v, g_a)]
    contact = _model("chi~", final, colours)
    contact.vertices += [tree.Vertex("FFFF", ("chi~", "chi", f"{final}~", final),
                                     structure=(("V", "V", -g_chi * g_v / HEAVY ** 2),
                                                ("V", "A", -g_chi * g_a / HEAVY ** 2)))]
    a, b = _sigma(exchange, "chi", "chi~", final), _sigma(contact, "chi", "chi~", final)
    assert a > 0 and b == pytest.approx(a, rel=1e-3)


def test_a_heavy_scalar_is_its_contact_operator():
    """L ⊃ S(g_χ χ̄χ + g_f f̄ iγ⁵ f) − ½M²S² integrated out: +(g_χ g_f/M²)(χ̄χ)(f̄iγ⁵f)."""
    g_chi, g_p = 0.6, 0.4
    exchange = _model("chi~", "mu")
    exchange.add(tree.Particle("S", 0, HEAVY, width=1.0))
    exchange.vertices += [tree.Vertex("FFS", ("chi~", "chi", "S"), g_chi, 0.0),
                          tree.Vertex("FFS", ("mu~", "mu", "S"), 0.0, g_p)]
    contact = _model("chi~", "mu")
    contact.vertices += [tree.Vertex("FFFF", ("chi~", "chi", "mu~", "mu"),
                                     structure=(("S", "P", g_chi * g_p / HEAVY ** 2),))]
    a, b = _sigma(exchange, "chi", "chi~", "mu"), _sigma(contact, "chi", "chi~", "mu")
    assert a > 0 and b == pytest.approx(a, rel=1e-3)


def test_a_majorana_bilinear_counts_both_contractions():
    """Majorana χ, L ⊃ Z′·(½ g_A χ̄γγ⁵χ + g_f f̄γf) (the FFV vertex holds g_A, its combinatorial 2): the contact
    −(g_A g_f/2M²)(χ̄γ^μγ⁵χ)(f̄γ_μf) with its bare coefficient, both contractions counted by the engine; a Majorana
    vector bilinear vanishes."""
    g_a, g_f = 0.7, 0.3
    exchange = _model("", "mu")
    exchange.add(tree.Particle("Zp", 1, HEAVY, width=1.0))
    exchange.vertices += [tree.Vertex("FFV", ("chi", "chi", "Zp"), 0.0, g_a),
                          tree.Vertex("FFV", ("mu~", "mu", "Zp"), g_f, 0.0)]
    contact = _model("", "mu")
    contact.vertices += [tree.Vertex("FFFF", ("chi", "chi", "mu~", "mu"),
                                     structure=(("A", "V", -g_a * g_f / (2 * HEAVY ** 2)),))]
    a, b = _sigma(exchange, "chi", "chi", "mu"), _sigma(contact, "chi", "chi", "mu")
    assert a > 0 and b == pytest.approx(a, rel=1e-3)
    vector, axial = _model("", "mu"), _model("", "mu")
    vector.vertices += [tree.Vertex("FFFF", ("chi", "chi", "mu~", "mu"), structure=(("V", "V", 1e-6),))]
    axial.vertices += [tree.Vertex("FFFF", ("chi", "chi", "mu~", "mu"), structure=(("A", "V", 1e-6),))]
    assert _sigma(vector, "chi", "chi", "mu") < 1e-12 * _sigma(axial, "chi", "chi", "mu")      # round-off only


def test_the_contact_squared_amplitude_does_not_depend_on_the_flow(monkeypatch):
    m = _model("", "mu")
    m.vertices += [tree.Vertex("FFFF", ("chi", "chi", "mu~", "mu"),
                               structure=(("A", "A", 2e-6), ("S", "S", 1e-6), ("T", "T", 5e-7)))]
    angles = np.linspace(-0.9, 0.9, 7)
    one = tree.Process(m, "chi", "chi", "mu", "mu~").squared(500.0 ** 2, angles)
    monkeypatch.setattr(tree, "FLOW_FROM_HIGHER", True)
    other = tree.Process(m, "chi", "chi", "mu", "mu~").squared(500.0 ** 2, angles)
    assert np.all(one > 0) and np.allclose(one, other, rtol=1e-10)

"""DM8: quark-level Wilson coefficients → nonrelativistic coefficients, through DirectDM."""

from __future__ import annotations

import numpy as np
import pytest

from adroit.library.interactions import quark_level as ql
from adroit.library.interactions import registry
from adroit.core.dm_state import DarkMatterParticle, ModelLayer
from adroit.physics.conventions import OPERATOR_MASS_GEV

pytestmark = pytest.mark.skipif(not ql.available(), reason="DirectDM and its environment are not set up")

Q = [0.01, 0.05, 0.1, 0.2]


def value_at(interaction, operator: int, nucleon: str, q: float) -> float:
    return sum(getattr(c, nucleon) * float(c.q_factor(np.array([q]))[0])
               for c in interaction.coefficients if c.operator == operator)


@pytest.mark.parametrize("flavours,coefficients", [
    (3, {"C61u": 1e-4, "C61d": 1e-4, "C64u": 2e-4, "C64d": -1e-4, "C64s": 0.5e-4, "C78u": 1e-6,
         "C78d": 2e-6, "C77u": 1e-6, "C51": 1e-3, "C52": 1e-3, "C73": 1e-6, "C74": 2e-6}),
    (5, {"C61u": 1e-4, "C63b": 1e-4, "C75u": 1e-7, "C76b": 1e-7, "C71": 1e-6}),
])
def test_the_conversion_is_exact_in_q(flavours, coefficients) -> None:
    """Every term DirectDM assembles is reproduced, at every q, up to the operator-mass factor."""
    model = ql.QuarkLevelModel(name="mixed", flavours=flavours, coefficients=coefficients)
    reference = ql.components(model, 50.0, Q)
    _, interaction = ql.to_interaction(model, 50.0)
    m_n = reference["mN"]
    for q, assembled in zip(Q, reference["cNR"]):
        for operator in [1, *range(3, 15)]:
            scale = (OPERATOR_MASS_GEV / m_n) ** ql.Q_OVER_M_POWER[operator]
            for nucleon, key in (("proton", "p"), ("neutron", "n")):
                expected = assembled[f"cNR{operator}{key}"] * scale
                assert value_at(interaction, operator, nucleon, q) == pytest.approx(expected, rel=1e-9, abs=1e-30)


def test_a_vector_coupling_is_the_library_vector_mediator() -> None:
    """(χ̄γ^μχ)(q̄γ_μq) counts valence quarks: c₁ᵖ = 2C_u + C_d, as M_vector's g_V^N = 3g_q."""
    g_q, g_chi, m_med = 0.25, 1.0, 2000.0
    c = -g_chi * g_q / m_med ** 2
    model = ql.QuarkLevelModel(name="V", flavours=5, rge=False,
                               coefficients={f"C61{q}": c for q in "udscb"})
    particle, interaction = ql.to_interaction(model, 100.0)
    card = registry.resolve("M_vector", particle, {"g_chi": g_chi, "m_med": m_med,
                                                   "gV_p": 3 * g_q, "gV_n": 3 * g_q})
    card_c1 = sum(t.proton for t in card.coefficients if t.operator == 1 and t.q_power == 0)
    assert value_at(interaction, 1, "proton", 1e-4) == pytest.approx(card_c1, rel=1e-6)
    assert interaction.layer is ModelLayer.quark


def test_majorana_and_scalar_types_set_the_particle() -> None:
    """DirectDM's Majorana classes need the driver's NumPy shim in the four- and five-flavour theories."""
    for dm_type, spin, self_conjugate in (("M", 0.5, True), ("C", 0.0, False), ("R", 0.0, True)):
        name = {"M": "C64u", "C": "C61u", "R": "C63u"}[dm_type]
        model = ql.QuarkLevelModel(name="t", flavours=5, dm_type=dm_type, coefficients={name: 1e-4})
        particle, interaction = ql.to_interaction(model, 30.0)
        assert (particle.spin, particle.self_conjugate) == (spin, self_conjugate)
        assert interaction.coefficients


def test_an_isovector_axial_current_induces_the_pion_pole() -> None:
    """The induced pseudoscalar: c₆ ∝ 1/(m_π² + q²), carried as a propagator of mass m_π."""
    model = ql.QuarkLevelModel(name="A", flavours=3, coefficients={"C64u": 1e-4, "C64d": -1e-4})
    _, interaction = ql.to_interaction(model, 50.0)
    poles = [c for c in interaction.coefficients if c.operator == 6]
    assert poles and all(c.mediator_mass_gev == pytest.approx(0.135, rel=0.01) for c in poles)


def test_particle_is_a_rate_ready_dark_matter_particle() -> None:
    model = ql.QuarkLevelModel(name="V", coefficients={"C61u": 1e-6})
    particle, _ = ql.to_interaction(model, 10.0)
    assert isinstance(particle, DarkMatterParticle) and particle.mass_gev == 10.0


def test_an_unknown_coefficient_name_is_an_error() -> None:
    """DirectDM would drop it silently; the bridge refuses it."""
    model = ql.QuarkLevelModel(name="typo", dm_type="R", coefficients={"C62u": 1e-4})
    with pytest.raises(ValueError, match="unknown Wilson coefficients"):
        ql.to_interaction(model, 30.0)


# --- recognising library cards (matching) -------------------------------------------------

from adroit.library.interactions import matching  # noqa: E402


def test_a_universal_axial_coupling_is_the_axial_card() -> None:
    model = ql.QuarkLevelModel(name="A", flavours=5, rge=False,
                               coefficients={f"C64{q}": 0.25 / 2000 ** 2 for q in "udscb"})
    particle, interaction = ql.to_interaction(model, 100.0)
    fits = {f.card_id: f for f in matching.match(particle, interaction)}
    assert fits["M_axial"].verdict == "same" and fits["O4"].verdict == "same"
    assert fits["M_axial"].values["gA_p"] == pytest.approx(fits["M_axial"].values["gA_n"])


def test_the_induced_pion_pole_is_named_as_the_remainder() -> None:
    """An isovector axial quark current is the axial card up to its pion pole, in O6."""
    model = ql.QuarkLevelModel(name="Av", flavours=3, coefficients={"C64u": 1e-6, "C64d": -1e-6})
    particle, interaction = ql.to_interaction(model, 100.0)
    fit = matching.fit_card("M_axial", particle, interaction)
    assert fit.verdict == "different" and set(fit.remainder) == {6}


def test_a_coupling_without_effect_is_undetermined() -> None:
    """A pure O1 interaction does not determine the Pauli couplings of the vector card."""
    from adroit.core.dm_state import InteractionModel, OperatorCoefficient
    c = 1e-6
    interaction = InteractionModel(name="O1", layer=ModelLayer.nonrelativistic,
                                   coefficients=[OperatorCoefficient(operator=1, proton=c, neutron=c)])
    particle = DarkMatterParticle(mass_gev=100.0)
    fit = matching.fit_card("O1", particle, interaction)
    assert fit.verdict == "same" and fit.values == {"c_p": pytest.approx(c), "c_n": pytest.approx(c)}
    assert matching.fit_card("O15", particle, interaction).verdict == "different"

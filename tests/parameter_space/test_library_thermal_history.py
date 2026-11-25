"""The owner's decision #5 on the library's route (2026-10-20): a coannihilation relic needs its partners' chemical
equilibrium and one stable component, as on the generic route."""
import math

import pytest

from adroit.parameter_space import library
from adroit.parameter_space.classes import Point

CROSSING = Point(m_chi=1.0, m_med=3.0, g_q=0.00241394218692518, g_l=0.1, g_chi=1.1209982432795857)   # an R3 crossing


def test_the_inelastic_partners_conversion_is_certified_by_its_decay_or_left_pending():
    """χ₂ → χ₁ e⁺e⁻, Γ = 4ε²αα_D δ⁵/(15π m_A′⁴), against 10 H at χ₂'s freeze-out: at an R3 crossing (ε = 2.4 × 10⁻³)
    it is about 10⁴ times faster; at ε = 10⁻⁹ it is not, and the point's relic prerequisite is pending; below δ = 2m_e
    there is no tree-level decay."""
    cls = library.entry("inelastic_dark_photon").model_class
    assert cls.conversion_reason(CROSSING) == ""
    assert not any("chemical equilibrium" in x for x in cls.pending(CROSSING))
    slow = CROSSING.model_copy(update={"g_q": 1e-9})
    assert cls.conversion_reason(slow).startswith("χ₂ → χ₁ e⁺e⁻ at")
    assert any(x.startswith("coannihilation chemical equilibrium not certified") for x in cls.pending(slow))
    assert "below 2m_e" in cls.conversion_reason(CROSSING.model_copy(update={"g_l": 1e-4}))
    delta, alpha_d = 0.1, 1.1209982432795857 ** 2 / (4 * math.pi)
    from adroit.constraints import kinetic_mixing as km
    expected = 4 * CROSSING.g_q ** 2 * km.E_THOMSON ** 2 / (4 * math.pi) * alpha_d * delta ** 5 / (15 * math.pi * 81)
    assert expected == pytest.approx(4.4e-17, rel=0.05)


def test_a_t_channel_partner_that_cannot_decay_is_a_second_stable_component():
    cls = library.entry("tchannel_uR_majorana").model_class
    assert cls.domain(Point(m_chi=300.0, m_med=400.0, g_chi=0.0)).startswith("several stable components")
    assert cls.domain(Point(m_chi=300.0, m_med=400.0, g_chi=1.0)) == ""

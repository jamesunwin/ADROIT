"""The off-shell Higgs's higher-order factors (``constraints.higgs.anchor``): the closure audit's T1-3 (G12), whose
fix had no test."""

import pytest

from adroit.constraints import higgs


@pytest.mark.parametrize("name, m_v", [("W", higgs.M_W), ("Z", higgs.M_Z)])
def test_the_ww_and_zz_factors_fade_to_one_at_the_pair_threshold(name, m_v):
    """At 125.09 GeV the factor is the Working Group's partial width over the leading order; it fades linearly to 1 at
    2m_V and stays 1 above (it had been applied at every virtuality, +9.6% at 300 GeV)."""
    k = higgs._anchors()[name]
    assert abs(k - 1.0) > 1e-3
    assert higgs.anchor(name, higgs.M_H) == pytest.approx(k)
    assert higgs.anchor(name, 0.5 * (higgs.M_H + 2 * m_v)) == pytest.approx(0.5 * (1.0 + k))
    assert higgs.anchor(name, 2 * m_v) == pytest.approx(1.0) and higgs.anchor(name, 300.0) == 1.0


def test_the_fermion_factors_hold_at_every_virtuality():
    assert higgs.anchor("b", 300.0) == pytest.approx(higgs._anchors()["b"])

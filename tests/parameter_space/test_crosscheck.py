"""ADROIT's relic density against micrOMEGAs (parameter_space.crosscheck), where micrOMEGAs is built."""

import pytest

from adroit.constraints import micromegas
from adroit.parameter_space import crosscheck as cc
from adroit.parameter_space.classes import Point

built = pytest.mark.skipif(not (micromegas.resolve_install(None) / "IDM" / "mo_omega").exists(),
                           reason="micrOMEGAs is not built in the tools folder")


def test_a_portal_without_a_micromegas_model_is_refused():
    with pytest.raises(KeyError):
        cc.crosscheck("wino", Point(m_chi=1000.0, m_med=1.0))


def test_the_slots_map_onto_micromegas_parameters():
    p = Point(m_chi=72.77, m_med=114.639, g_chi=-0.0044, g_q=35.0)
    mapped = cc.MAPPINGS["inert_doublet"][1](p)
    assert mapped["M_A0"] == pytest.approx(107.77) and mapped["lambda_345"] == -0.0044 and mapped["MW"] == 79.947
    assert cc.MAPPINGS["b_minus_l"][1](Point(m_chi=1.0, m_med=3.0, g_q=0.3))["g_SM"] == pytest.approx(0.1)


@pytest.mark.slow
@built
@pytest.mark.parametrize("entry, point, tolerance", [
    ("higgs_portal_scalar", Point(m_chi=62.0, m_med=125.0, g_chi=3e-4), 0.03),         # on the Higgs pole
    ("higgs_portal_scalar", Point(m_chi=300.0, m_med=125.0, g_chi=0.1), 0.06),
    ("inert_doublet", Point(m_chi=990.0, m_med=998.12, g_chi=-0.051, g_q=2.36), 0.05),
    ("inert_doublet", Point(m_chi=72.77, m_med=114.639, g_chi=-0.00440723, g_q=35.033), 0.2)])   # W W*
def test_adroit_agrees_with_micromegas(entry, point, tolerance):
    """Like with like: ADROIT on micrOMEGAs' own degrees of freedom (DHS) within the declared tolerance. With its own
    (Saikawa & Shirai, since 2026-10-19) its Ωh² is 3.7% higher at each of these points, the equation of state's
    systematic (docs/relic_low_mass.md)."""
    same = cc.crosscheck(entry, point, its_equation_of_state=True).ratio
    assert same == pytest.approx(1.0, abs=tolerance)
    assert cc.crosscheck(entry, point).ratio / same == pytest.approx(1.037, abs=0.005)

"""ATLAS scenario 1a is a full benchmark, not just an open invisible decay."""
import pytest

from adroit.parameter_space.library import TWO_HDM_A
from adroit.parameter_space.classes import Point
from adroit.parameter_space import searches, resonances


def test_audit_dark_mass_threshold_does_not_reuse_the_same_contour():
    point = Point(m_chi=10, m_med=400, g_chi=1, g_q=0.35, g_l=1)
    good = searches.two_hdma(TWO_HDM_A, point, True)
    wrong = searches.two_hdma(TWO_HDM_A, point.model_copy(update={"m_chi": 199.999}), True)
    assert good.excluded is True and good.value is None          # R4 (M3): a polygon test has no single ratio
    assert wrong.excluded is None and wrong.value is None and "MXd" in wrong.why


@pytest.mark.parametrize("key,value", [("sinp", ".7"), ("tanbeta", "2"), ("gPXd", ".5"),
    ("lam3", "2"), ("laP1", "2"), ("laP2", "2"), ("sinbma", ".9"),
    ("mh2", "900"), ("mhc", "900"), ("mh1", "130"), ("MXd", "20")])
def test_each_benchmark_assumption_is_guarded(key, value):
    cls = TWO_HDM_A.model_copy(update={"parameters": {**TWO_HDM_A.parameters, key: value}})
    result = searches.two_hdma(cls, Point(m_chi=10, m_med=400, g_chi=1, g_q=.35, g_l=1), True)
    assert result.excluded is None and key in result.why


def test_independent_recasts_remain_dispatched(monkeypatch):
    called = []
    def recast(cls, point, unverified):
        called.append(point.m_chi)
        return searches.Outcome(name="independent mono-h", excluded=False)
    monkeypatch.setattr(searches, "EVALUATORS", (searches.two_hdma,))
    monkeypatch.setattr(resonances, "EVALUATORS", (recast,))
    results = searches.outcomes(TWO_HDM_A, Point(m_chi=199.999, m_med=400, g_q=.35, g_l=1), True)
    assert results[0].excluded is None and results[1].excluded is False and called == [199.999]

"""Thermal certificates test the solver, not a grid interpolation."""
import importlib

import pytest

from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult, _point_at
from adroit.parameter_space.thermal import refine

v = importlib.import_module("adroit.parameter_space.verdict")


def grid(values):
    req = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30),
                      x=Axis(parameter="m_chi", low=10, high=40, n=2),
                      y=Axis(parameter="g_chi", low=.1, high=.2, n=2), mediator_ratio=3)
    return ScanResult(request=req, xs=req.x.values(), ys=req.y.values(), points=[
        PointResult(point=_point_at(req, x, y), omega_h2=w, dd_kind="SI", dd_sigma_cm2=0,
                    dd_limit_cm2=1, excluded={})
        for (x, y), w in zip([(x, y) for y in req.y.values() for x in req.x.values()], values)])


def test_unavailable_and_incomplete_are_pending():
    assert v.verdict(grid([None] * 4)).level == "pending"
    assert v.verdict(grid([.01, None, .02, .03])).level == "pending"
    assert v.verdict(grid([.01, .02, .03])).level == "pending"


@pytest.mark.needs("eos")
def test_plateau_and_endpoint_are_retained(monkeypatch):
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: .12)
    monkeypatch.setattr(v, "judge_point", lambda cls, p, *a: v.Crossing(point=p, status="viable", omega_h2=.12,
                        evaluation=PointResult(point=p, omega_h2=.12, dd_kind='SI', dd_sigma_cm2=0.0, dd_limit_cm2=1.0, excluded={})))
    monkeypatch.setattr("adroit.parameter_space.searches.prefetch_lhc", lambda cls, pts, *a: [None]*len(pts))
    result = v.verdict(grid([.12] * 4))
    assert result.level == "viable" and len(result.crossings) == 4
    assert all(c.converged and c.relative_residual == 0 and c.kind == "contour" for c in result.crossings)


def test_discontinuous_or_failed_solver_is_not_a_thermal_root():
    def at(t):
        return Point(m_chi=t, m_med=100)
    discontinuous = refine(at, lambda p: .01 if p.m_chi < .51 else 10, .12)
    assert not discontinuous.converged and discontinuous.relative_residual > .01
    failed = refine(at, lambda p: None if .4 < p.m_chi < .6 else .24*p.m_chi, .12)
    assert not failed.converged and "unavailable" in failed.reason


def test_resonant_function_is_stable_under_local_refinement():
    """Two refinements of a steep resonance meet at one root, within the declared coordinate tolerance (10⁻⁶ since
    F4, matched to the relic solver's precision), each far inside the 1% acceptance."""
    from adroit.parameter_space.thermal import ROOT_COORDINATE_TOLERANCE
    def at(t):
        return Point(m_chi=t, m_med=100)
    def omega(p):
        return .001 + (p.m_chi - .501) ** 2 * 1000
    first = refine(at, omega, .12, .45, .501)
    second = refine(at, omega, .12, first.coordinate-.001, first.coordinate+.001)
    assert first.converged and second.converged
    assert first.relative_residual < 1e-4 and second.relative_residual < 1e-4
    assert first.coordinate == pytest.approx(second.coordinate, abs=ROOT_COORDINATE_TOLERANCE)


def test_a_power_law_root_takes_a_few_evaluations():
    """F4: along a log axis Ωh² ∝ m^k makes ln(Ωh²/target) linear in t, so Brent needs a handful of evaluations
    (the linear residual Ωh²/target − 1 had taken ten to fifteen)."""
    calls = []
    def omega(p):
        calls.append(p.m_chi)
        return .12 * (p.m_chi / 37.0) ** 2
    root = refine(lambda t: Point(m_chi=10.0 * 10.0 ** t, m_med=100), omega, .12)
    assert root.converged and root.point.m_chi == pytest.approx(37.0, rel=1e-6) and len(calls) <= 6


@pytest.mark.needs("eos")
def test_unexamined_brackets_cannot_establish_global_exclusion(monkeypatch):
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: .006*p.m_chi)
    monkeypatch.setattr(v, "judge_point", lambda cls, p, *a: v.Crossing(point=p, status="excluded", omega_h2=.12))
    monkeypatch.setattr("adroit.parameter_space.searches.prefetch_lhc", lambda cls, pts, *a: [None]*len(pts))
    result = v.verdict(grid([.06, .24, .06, .24]), max_crossings=1)
    assert result.level == "pending" and result.omitted_candidates == 1

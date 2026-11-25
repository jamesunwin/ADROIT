"""Independent closed-loop fixtures missed by coarse sign-changing-edge searches."""
import math

import pytest

from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.coverage import CoverageSettings, diagnose
from adroit.parameter_space.scan import Axis, ScanRequest


def request(log=False):
    return ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30),
                       x=Axis(parameter='m_chi', low=10, high=40, log=log, n=3),
                       y=Axis(parameter='g_chi', low=.1, high=.2, log=False, n=3), mediator_ratio=3)


def circles(point):
    x, y = (point.m_chi - 10)/30, (point.g_chi - .1)/.1
    return .12 + .1*min((x-cx)**2+(y-cy)**2-.04 for cx, cy in [(.25, .25), (.75, .75)])


def test_refinement_finds_two_closed_structures_that_coarse_corners_miss(monkeypatch):
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: circles(p))
    req = request()
    assert all(circles(Point(m_chi=x, m_med=3*x, g_chi=y)) > .12
               for x in req.x.values() for y in req.y.values())
    result = diagnose(req)
    assert result.status == 'sampled_at_requested_resolution' and len(result.samples) == 25
    accepted = [root for root in result.root_attempts if root.converged]
    assert len(accepted) == 8
    assert all(root.relative_residual < 1e-7 for root in accepted)
    assert all(root.point.m_med == 3*root.point.m_chi for root in accepted)
    points = [((r.point.m_chi-10)/30, (r.point.g_chi-.1)/.1) for r in accepted]
    assert all(sum(abs(math.hypot(x-cx, y-cy)-.2) < 1e-6 for x,y in points) == 4
               for cx,cy in [(.25,.25),(.75,.75)])
    assert 'not evaluated' in result.interpretation and 'do not rule out' in result.interpretation


def test_budget_caps_sampling_and_refinement_and_reports_partial_coverage(monkeypatch):
    calls = []
    def omega(self, p):
        calls.append(p)
        return circles(p)
    monkeypatch.setattr(Spin1Class, 'omega_h2', omega)
    result = diagnose(request(), CoverageSettings(max_evaluations=30))
    assert len(calls) == result.evaluations <= 30
    assert result.status == 'partial' and result.unresolved
    assert result.omitted_candidates > 0


def test_missing_density_never_becomes_a_certificate(monkeypatch):
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: None)
    result = diagnose(request())
    assert result.status == 'partial' and not result.root_attempts
    assert all(sample.omega_h2 is None and sample.reason for sample in result.samples)


def test_original_log_axis_nodes_and_relations_are_preserved(monkeypatch):
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: .12)
    req = request(log=True)
    result = diagnose(req, CoverageSettings(max_evaluations=100))
    assert result.xs[::2] == req.x.values()
    assert all(s.point.m_med == 3*s.point.m_chi for s in result.samples)
    assert all(r.converged and r.relative_residual == 0 for r in result.root_attempts)
    with pytest.raises(ValueError, match='thermal target'):
        diagnose(req.model_copy(update={'relic_fraction':0}))


def test_an_exact_tangent_root_is_retained_without_a_sign_change(monkeypatch):
    def tangent(self, p):
        return .12 + ((p.m_chi-17.5)/30)**2 + ((p.g_chi-.125)/.1)**2
    monkeypatch.setattr(Spin1Class, 'omega_h2', tangent)
    result = diagnose(request())
    accepted = [r for r in result.root_attempts if r.converged]
    assert len(accepted) == 1 and accepted[0].point.m_chi == 17.5
    assert accepted[0].point.g_chi == .125 and accepted[0].relative_residual == 0


def test_an_unresolved_subgrid_loop_does_not_generate_an_absence_or_exclusion_claim(monkeypatch):
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p:
                        .12 + .1*(((p.m_chi-10)/30-.125)**2 + ((p.g_chi-.1)/.1-.125)**2 - .03**2))
    result = diagnose(request())
    assert not result.root_attempts and result.status == 'sampled_at_requested_resolution'
    assert 'Finite probes do not rule out' in result.interpretation
    assert not hasattr(result, 'level')


def test_root_endpoints_and_constant_coordinates_keep_the_exact_input_identity(monkeypatch):
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: .12 + p.g_chi - .15)
    req = request(log=True).model_copy(update={'x':Axis(parameter='m_chi',low=50,high=200,n=2)})
    result = diagnose(req)
    assert all(root.point.m_chi in result.xs for root in result.root_attempts if root.converged)
    assert {50., 200.} <= {root.point.m_chi for root in result.root_attempts if root.converged}

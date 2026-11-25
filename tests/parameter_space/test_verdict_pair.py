"""One root search, separate physical checks and independent cuts/likelihood outputs."""
import importlib

import pytest

from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.likelihood import LikelihoodSettings
from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult, _point_at

v = importlib.import_module('adroit.parameter_space.verdict')


def grid():
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30),
                          x=Axis(parameter='m_chi', low=10, high=40, n=2),
                          y=Axis(parameter='g_chi', low=.1, high=.2, n=2), mediator_ratio=3)
    return ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=[
        PointResult(point=_point_at(request, x, y), omega_h2=.006*x, dd_kind='SI',
                    dd_sigma_cm2=0, dd_limit_cm2=1, excluded={'colliders (CMS)': False})
        for y in request.y.values() for x in request.x.values()])


def physical_checks(monkeypatch, density=None):
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: .006*p.m_chi)
    monkeypatch.setattr('adroit.parameter_space.searches.prefetch_lhc', lambda cls, pts, *a: [None]*len(pts))
    def evaluate(cls, p, *args):
        return PointResult(point=p, omega_h2=.006*p.m_chi if density is None else density,
                           dd_kind='SI', dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={'colliders (CMS)': False}, ratios={'toy95': .8},
                           ratio_confidence_levels={'toy95': .95})
    monkeypatch.setattr(v, 'evaluate', evaluate)


def test_pair_preserves_both_views_and_their_final_checks(monkeypatch):
    physical_checks(monkeypatch)
    scan, settings = grid(), LikelihoodSettings()
    expected = (v.verdict(scan), v.verdict(scan, likelihood=settings))
    original = v._thermal_roots
    calls = []
    def roots(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(v, '_thermal_roots', roots)
    pair = v.verdict_pair(scan, likelihood=settings)
    assert len(calls) == 1
    assert [x.model_dump() for x in pair] == [x.model_dump() for x in expected]
    assert all(c.point.m_med == pytest.approx(3*c.point.m_chi) for c in pair[0].crossings)
    pair[0].root_attempts[0].reason = 'changed by a caller'
    assert pair[1].root_attempts[0].reason != 'changed by a caller'


@pytest.mark.needs("eos")
def test_both_views_reject_a_density_that_changed_during_constraint_evaluation(monkeypatch):
    physical_checks(monkeypatch, density=.2)
    cuts, combined = v.verdict_pair(grid(), likelihood=LikelihoodSettings())
    assert cuts.level == combined.level == 'pending'
    assert not cuts.crossings and not combined.crossings
    assert all('root changed' in view.unresolved[0] for view in (cuts, combined))


def test_pair_retains_omitted_brackets_and_no_global_exclusion(monkeypatch):
    physical_checks(monkeypatch)
    cuts, combined = v.verdict_pair(grid(), max_crossings=1, likelihood=LikelihoodSettings())
    assert cuts.omitted_candidates == combined.omitted_candidates == 1
    assert cuts.unresolved == combined.unresolved


def test_cuts_only_pair_has_no_second_view(monkeypatch):
    physical_checks(monkeypatch)
    cuts, combined = v.verdict_pair(grid())
    assert combined is None and cuts == v.verdict(grid())
    with pytest.raises(ValueError, match='max_crossings'):
        v.verdict_pair(grid(), max_crossings=0)


def test_likelihood_view_still_rechecks_density_after_the_cuts_view(monkeypatch):
    physical_checks(monkeypatch)
    monkeypatch.setattr(v, '_eos_checked', lambda result, root, c, *args: (c, v.Check(
        name='eos_band', state='not_applicable')))     # the band's judgements counted apart
    original = v.evaluate
    calls = []
    def changing(cls, p, *args):
        calls.append(p)
        result = original(cls, p, *args)
        return result if len(calls) <= 2 else result.model_copy(update={'omega_h2': .2})
    monkeypatch.setattr(v, 'evaluate', changing)
    cuts, combined = v.verdict_pair(grid(), likelihood=LikelihoodSettings())
    assert len(calls) == 4 and cuts.level == 'viable' and combined.level == 'pending'
    assert not combined.crossings and any('root changed' in r for r in combined.unresolved)


def test_a_thermal_root_on_a_log_axis_of_negative_couplings_is_refined(monkeypatch):
    """G12's live check L3: a Higgs portal written with a positive Lagrangian coefficient has g_χ < 0, so its g axis
    is logarithmic over negative values; refining a bracket had taken math.log of them and left every root pending."""
    def omega(p):
        return .12 * (.15 / p.g_chi) ** 2
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: omega(p))
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30),
                          x=Axis(parameter='m_chi', low=10, high=40, n=2),
                          y=Axis(parameter='g_chi', low=-.2, high=-.1, n=2), mediator_ratio=3)
    result = ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=[
        PointResult(point=_point_at(request, x, y), omega_h2=omega(_point_at(request, x, y)), dd_kind='SI',
                    dd_sigma_cm2=0, dd_limit_cm2=1, excluded={})
        for y in request.y.values() for x in request.x.values()])
    roots, _ = v._thermal_roots(result, .12)
    assert roots and all(r.converged and r.point.g_chi == pytest.approx(-.15, rel=1e-6) for r in roots)
    assert v.along(-.2, -.1, .5, True) == pytest.approx(-(.02 ** .5))


def test_coverage_refines_a_log_axis_of_negative_couplings():
    """The same for coverage's refinement (it had refused any non-positive log axis): geometric midpoints of one
    sign; an axis that changes sign is still refused."""
    from adroit.parameter_space import coverage
    axis = Axis(parameter='g_chi', low=-1.0, high=-.01, n=3)
    assert coverage._coordinates(axis, 1) == pytest.approx([-1.0, -(.1 ** .5), -.1, -(.001 ** .5), -.01])
    with pytest.raises(ValueError, match="one sign"):
        coverage._coordinates(Axis(parameter='g_chi', low=-1.0, high=1.0, n=2, log=False).model_copy(
            update={"log": True}), 1)


def test_a_plane_of_negative_couplings_is_plotted_on_a_symmetric_log_scale(tmp_path):
    """G12's live check L3: matplotlib cannot log-scale negative values; such an axis is symlog, linear in |g| below
    its smallest value. The plane is drawn."""
    from adroit.parameter_space import plots
    assert plots._scale(True, [1.0, 10.0]) == ("log", {})
    assert plots._scale(True, [-10.0, -0.1]) == ("symlog", {"linthresh": 0.1})
    assert plots._scale(False, [-1.0, 1.0]) == ("linear", {})
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30),
                          x=Axis(parameter='m_chi', low=10, high=40, n=2),
                          y=Axis(parameter='g_chi', low=-.2, high=-.1, n=2), mediator_ratio=3)
    result = ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=[
        PointResult(point=_point_at(request, x, y), omega_h2=.1, dd_kind='SI', dd_sigma_cm2=0, dd_limit_cm2=1,
                    excluded={}) for y in request.y.values() for x in request.x.values()])
    verdict = v.Verdict(mode='cuts', level='pending', summary='', target=.12)
    assert plots.plane(result, verdict, tmp_path / 'plane.png').exists()

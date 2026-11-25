"""Grid and contour points must obey the same scan relations (audit F02)."""

import pytest

from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult, _point_at
from adroit.parameter_space.verdict import Crossing, _crossings


@pytest.mark.parametrize("mass_axis", ["x", "y"])
@pytest.mark.parametrize("log, expected_mass", [(True, 20.0), (False, 25.0)])
@pytest.mark.parametrize("ratio", [3.0, None])
def test_crossings_preserve_relations_and_fixed_parameters(
    monkeypatch, mass_axis: str, log: bool, expected_mass: float, ratio: float | None,
) -> None:
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: 0.006 * p.m_chi if log else
                        0.06 * 4 ** ((p.m_chi - 10) / 30))
    mass = Axis(parameter="m_chi", low=10, high=40, log=log, n=2)
    coupling = Axis(parameter="g_chi", low=0.1, high=0.2, n=2)
    request = ScanRequest(model_class=Spin1Class(),
                          fixed=Point(m_chi=10, m_med=30, g_q=0.17, g_l=-0.04),
                          x=mass if mass_axis == "x" else coupling,
                          y=mass if mass_axis == "y" else coupling, mediator_ratio=ratio, workers=1)
    points = [_point_at(request, x, y) for y in request.y.values() for x in request.x.values()]
    result = ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=[
        PointResult(point=p, omega_h2=0.06 if p.m_chi == 10 else 0.24, dd_kind="SI",
                    dd_sigma_cm2=0, dd_limit_cm2=1, excluded={}) for p in points])
    crossings = _crossings(result, 0.12)
    assert len(crossings) == 2
    for p in crossings:
        assert p.m_chi == pytest.approx(expected_mass)
        assert p.m_med == pytest.approx(expected_mass * ratio if ratio else 30)
        assert (p.g_q, p.g_l) == (0.17, -0.04)
    assert [p.g_chi for p in crossings] == pytest.approx([0.1, 0.2])
    assert request.fixed.m_chi == 10 and request.fixed.m_med == 30
    restored = ScanResult.model_validate_json(result.model_dump_json())
    assert _crossings(restored, 0.12) == crossings


@pytest.mark.parametrize("ratio", [0, -1, float("inf"), float("nan")])
def test_invalid_mediator_ratio_is_rejected(ratio: float) -> None:
    with pytest.raises(ValueError, match="mediator_ratio"):
        ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30), mediator_ratio=ratio,
                    x=Axis(parameter="m_chi", low=10, high=40), y=Axis(parameter="g_chi", low=0.1, high=1))


@pytest.mark.parametrize("second_parameter, ratio", [("m_chi", None), ("m_med", 3)])
def test_contradictory_axes_are_rejected(second_parameter: str, ratio: float | None) -> None:
    with pytest.raises(ValueError, match="axis|axes"):
        ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30), mediator_ratio=ratio,
                    x=Axis(parameter="m_chi", low=10, high=40),
                    y=Axis(parameter=second_parameter, low=10, high=40))


def test_relation_also_uses_fixed_dm_mass_when_both_axes_are_couplings() -> None:
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=20, m_med=30), mediator_ratio=3,
                          x=Axis(parameter="g_chi", low=0.1, high=1),
                          y=Axis(parameter="g_q", low=0.1, high=1))
    point = _point_at(request, 0.2, 0.3)
    assert (point.m_chi, point.m_med, point.g_chi, point.g_q) == (20, 60, 0.2, 0.3)


def test_verdict_sends_constrained_points_to_colliders_and_point_judging(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib import import_module
    module = import_module("adroit.parameter_space.verdict")
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30), mediator_ratio=3,
                          x=Axis(parameter="m_chi", low=10, high=40, n=2),
                          y=Axis(parameter="g_chi", low=0.1, high=0.2, n=2))
    points = [_point_at(request, x, y) for y in request.y.values() for x in request.x.values()]
    result = ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=[
        PointResult(point=p, omega_h2=0.06 if p.m_chi == 10 else 0.24, dd_kind="SI",
                    dd_sigma_cm2=0, dd_limit_cm2=1, excluded={}) for p in points])
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: 0.006 * p.m_chi)
    seen = {"collider": [], "judge": []}

    def prefetch(cls: Spin1Class, points: list[Point], unverified: bool) -> list[dict | None]:
        seen["collider"].extend(points)
        return [None] * len(points)

    def judge(cls: Spin1Class, point: Point, *args: object) -> Crossing:
        seen["judge"].append(point)
        return Crossing(point=point, status="viable", omega_h2=0.12,
                        evaluation=PointResult(point=point, omega_h2=0.12, dd_kind='SI', dd_sigma_cm2=0.0, dd_limit_cm2=1.0, excluded={}))

    monkeypatch.setattr("adroit.parameter_space.searches.prefetch_lhc", prefetch)
    monkeypatch.setattr(module, "judge_point", judge)
    monkeypatch.setattr(module, '_eos_checked', lambda result, root, c, *args: (c, module.Check(
        name='eos_band', state='not_applicable')))     # the band's judgements counted apart
    verdict = module.verdict(result)
    assert len(verdict.crossings) == 2
    assert seen["collider"] == seen["judge"] == [c.point for c in verdict.crossings]
    assert all(c.point.m_med == pytest.approx(60) for c in verdict.crossings)

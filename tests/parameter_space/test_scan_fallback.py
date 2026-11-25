"""A scan's per-point fallback to the generic route (the owner, 2026-10-15; ``scan.engine_for``)."""

import pytest

from adroit.core.model_spec import ModelSpec
from adroit.orchestrator.track1 import _fallback
from adroit.parameter_space.classes import Point
from adroit.parameter_space.classify import classify
from adroit.parameter_space.scan import Axis, ScanRequest, engine_for

SPEC = ModelSpec.model_validate({"name": "lepton_partner", "phase": "unbroken", "fields": [
    {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 120.0},
    {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 250.0,
     "charges": {"hypercharge": -1.0}},
    {"name": "muR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": {"hypercharge": -1.0}}],
    "couplings": [{"name": "y", "value": 1.0}],
    "terms": [{"fields": [{"field": "phi", "conjugate": True}, {"field": "chi"}, {"field": "muR"}],
               "lorentz": "chiral", "coupling": "y", "plus_hc": True}]})


def _request(y_parameter: str = "m_med") -> ScanRequest:
    cls, fixed, _ = classify(SPEC)
    return ScanRequest(model_class=cls, fixed=fixed, x=Axis(parameter="m_chi", low=100.0, high=140.0, n=2),
                       y=Axis(parameter=y_parameter, low=150.0 if y_parameter == "m_med" else 0.5,
                              high=300.0 if y_parameter == "m_med" else 1.0, n=2),
                       fallback_class=_fallback(SPEC, cls))


def test_a_point_outside_the_typed_domain_is_computed_by_the_generic_route():
    request = _request()
    assert type(request.model_class).__name__ == "TChannel" and request.fallback_class is not None
    below = Point(m_chi=120.0, m_med=150.0, g_chi=1.0)
    engine, flag = engine_for(request, below)
    assert engine is request.fallback_class and "outside the TChannel engine's domain" in flag
    above = Point(m_chi=120.0, m_med=250.0, g_chi=1.0)
    assert engine_for(request, above) == (request.model_class, "")


def test_a_coupling_axis_keeps_the_typed_engine():
    """The generic engine reads its couplings from the Lagrangian, so it cannot stand in on a coupling axis."""
    request = _request("g_chi")
    assert engine_for(request, Point(m_chi=120.0, m_med=150.0, g_chi=0.7)) == (request.model_class, "")


def test_the_fallback_is_left_out_of_a_requests_identity_when_unset():
    request = _request().model_copy(update={"fallback_class": None})
    assert "fallback_class" not in request.model_dump()


def test_a_thermal_root_between_fallback_points_is_refined_by_the_fallback(monkeypatch):
    """The audit's G3/G4-5 (G12): refinement used the typed class only, so a bracket of generic-route points could never
    be certified (\"relic solver unavailable within the bracket\")."""
    from adroit.parameter_space import verdict
    from adroit.parameter_space.scan import PointResult, ScanResult
    request = _request()
    fallback = type(request.fallback_class)
    monkeypatch.setattr(fallback, "omega_h2", lambda self, p: 0.12 * (p.m_chi / 120.0) ** 2)
    monkeypatch.setattr(fallback, "domain", lambda self, p: "")
    rows = []
    for m_med in request.y.values():
        for m_chi in request.x.values():
            p = request.fixed.model_copy(update={"m_chi": m_chi, "m_med": m_med})
            engine, flag = engine_for(request, p)
            rows.append(PointResult(point=p, omega_h2=engine.omega_h2(p), dd_kind="SI", dd_sigma_cm2=0.0,
                                    dd_limit_cm2=None, excluded={}, flags=[flag] if flag else []))
    result = ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=rows)
    roots, _ = verdict._thermal_roots(result, 0.12)
    fallback_roots = [r for r in roots if r.point is not None and r.point.m_med < 200.0]
    assert fallback_roots and all(r.converged for r in fallback_roots)


@pytest.mark.needs("eos")
def test_the_fallbacks_roots_are_judged_and_qualified_by_the_fallback(monkeypatch):
    """The external audit's R17-5 (2026-10-17): roots refined by the fallback were judged by the typed class, which
    refuses them by its domain, so both were lost; the regime check consulted the typed class only. Now each root is
    judged, prefetched and checked for D35's regimes with its own engine."""
    from adroit.parameter_space import searches, verdict
    from adroit.parameter_space.portals import generic_regimes
    from adroit.parameter_space.scan import PointResult, ScanResult
    request = _request().model_copy(update={"y": Axis(parameter="m_med", low=150.0, high=160.0, n=2)})
    fallback = type(request.fallback_class)
    monkeypatch.setattr(fallback, "omega_h2", lambda self, p: 0.12 * (p.m_chi / 120.0) ** 2)
    monkeypatch.setattr(fallback, "domain", lambda self, p: "")
    judged, prefetched = [], []

    def judge(cls, p, *args, **kwargs):
        judged.append(type(cls).__name__)
        omega = None if cls.domain(p) else cls.omega_h2(p)
        return verdict.Crossing(point=p, status="viable", omega_h2=omega,
                                evaluation=PointResult(point=p, omega_h2=omega, dd_kind='SI', dd_sigma_cm2=0.0, dd_limit_cm2=1.0, excluded={}))
    monkeypatch.setattr(verdict, "judge_point", judge)
    monkeypatch.setattr(searches, "prefetch_lhc", lambda cls, ps, *a: prefetched.append(type(cls).__name__) or [None] * len(ps))
    rows = []
    for m_med in request.y.values():
        for m_chi in request.x.values():
            p = request.fixed.model_copy(update={"m_chi": m_chi, "m_med": m_med})
            engine, flag = engine_for(request, p)
            rows.append(PointResult(point=p, omega_h2=engine.omega_h2(p), dd_kind="SI", dd_sigma_cm2=0.0,
                                    dd_limit_cm2=None, excluded={}, flags=[flag] if flag else []))
    result = ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=rows)
    roots, omitted = verdict._thermal_roots(result, 0.12)
    found = verdict._verdict_from_roots(result, roots, omitted, 80, None)
    assert roots and set(judged) == {"GenericModel"} and prefetched == ["GenericModel"]
    assert len(found.crossings) == len(roots) and found.level == "viable"
    monkeypatch.setattr(generic_regimes, "regimes", lambda model, p: ["a synthetic regime"])
    assert verdict._regimes(result, found) == ["a synthetic regime"]

"""A saved view classifies what was saved and calls no model (the fresh audit's F19-07, 2026-10-19): the engine's own
pending reasons are saved with each evaluation; an older result without them is pending on their absence. And
F19-06: a private replacement's own numbers are shown."""
import runpy
from pathlib import Path

import pytest

from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.generic import GenericModel
from adroit.parameter_space.scan import GENERIC_FLAG, PointResult, evaluate
from adroit.parameter_space.verdict import NOT_SAVED, classify, classify_saved

ROOT = Path(__file__).resolve().parents[1]


def _generic_scan(**update):
    """The generic-route grid of ``test_generic_regimes`` (GenericModel the engine), its rows updated."""
    scan, _ = runpy.run_path(str(ROOT / "parameter_space" / "test_generic_regimes.py"))["_grid"](
        excluded=lambda m: False)
    return scan.model_copy(update={"points": [r.model_copy(update=update) for r in scan.points]})


@pytest.fixture
def no_physics(monkeypatch):
    """GenericModel's scattering and pending raise: a view that calls either fails."""
    def refuse(self, p):
        raise AssertionError("a saved view called the model")
    monkeypatch.setattr(GenericModel, "scattering", refuse)
    monkeypatch.setattr(GenericModel, "pending", refuse)


def test_a_saved_generic_grid_is_listed_without_calling_the_model(no_physics):
    from types import SimpleNamespace
    from adroit.evidence import points
    scan = _generic_scan(model_pending=["direct detection: a saved reason"])
    rows = points.rows("track1", SimpleNamespace(scan=scan, verdict=None, likelihood_verdict=None))
    assert rows and all(row.status != "excluded" for row, _, _ in rows)
    assert {row.reason for row, _, _ in rows} == {"direct detection: a saved reason"}


def test_an_older_generic_result_is_pending_on_its_unsaved_reasons(no_physics):
    scan = _generic_scan()
    for r in scan.points:
        c = classify_saved(scan, r)
        assert c.status == "pending" and NOT_SAVED in c.pending


def test_decision_reads_the_saved_reasons(no_physics):
    from adroit.evidence.points import decision
    scan = _generic_scan(model_pending=[])
    r = scan.points[0]
    assert decision(r, r, scan) == (set(), [])


def test_classify_prefers_the_saved_reasons_to_the_engine():
    class Refuses:
        def pending(self, p):
            raise AssertionError("classify called the engine")
    scan = _generic_scan(model_pending=["a saved reason"])
    assert classify(Refuses(), scan.points[0]).pending == ["a saved reason"]


def test_an_older_point_of_an_engine_without_reasons_is_classified_as_before():
    """A typed class without ``pending`` (the fallback's flag absent) keeps the collider rule, not ``NOT_SAVED``."""
    from adroit.parameter_space.classes import Spin1Class
    from adroit.parameter_space.scan import Axis, ScanRequest, ScanResult
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=100, m_med=1000, g_chi=1.0, g_q=0.25),
                          x=Axis(parameter="m_med", low=500, high=1000, n=2),
                          y=Axis(parameter="m_chi", low=50, high=100, n=2))
    row = PointResult(point=request.fixed, omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=1e-50, dd_limit_cm2=1e-46,
                      excluded={"colliders (CMS)": False})
    scan = ScanResult(request=request, xs=[500, 1000], ys=[50, 100], points=[row])
    assert not hasattr(Spin1Class(), "pending")
    assert classify_saved(scan, row).pending == classify(Spin1Class(), row).pending
    assert NOT_SAVED not in classify_saved(scan, row).pending


def test_the_fallback_flag_names_the_engine(no_physics):
    """A typed engine without reasons, its point computed by the generic fallback (the saved flag): the fallback's
    reasons apply, and an older point is pending on them, never recomputed."""
    from adroit.parameter_space.classes import Spin1Class
    scan = _generic_scan()
    request = scan.request.model_copy(update={"model_class": Spin1Class(), "fallback_class": scan.request.model_class})
    scan = scan.model_copy(update={"request": request})
    computed_by_fallback = scan.points[0].model_copy(update={"flags": [f"{GENERIC_FLAG}: outside the domain"]})
    assert NOT_SAVED in classify_saved(scan, computed_by_fallback).pending
    assert NOT_SAVED not in classify_saved(scan, scan.points[0]).pending


@pytest.mark.needs("diamx", "solar_model")
def test_evaluate_saves_the_engines_reasons():
    from adroit.parameter_space.portals.higgs import HiggsPortalScalar
    cls, p = HiggsPortalScalar(), Point(m_chi=70.0, m_med=125.09, g_chi=1e-3)
    r = evaluate(cls, p)
    assert r.model_pending == cls.pending(p)
    assert "model_pending" in r.model_dump(mode="json")


def test_an_engine_without_reasons_saves_none_and_its_results_serialise_as_before():
    row = PointResult(point=Point(m_chi=10, m_med=100), omega_h2=0.1, dd_kind="SI", dd_sigma_cm2=0.0,
                      dd_limit_cm2=None, excluded={})
    assert row.model_pending is None and "model_pending" not in row.model_dump(mode="json")


def test_a_private_replacement_shows_its_own_bound_not_the_standard_records():
    """The fresh audit's F19-06: a private limit replacing the invisible-Higgs record keeps the record's name; its
    saved prediction and bound are shown, with units, never the standard record's 0.107."""
    from adroit.core.evidence import EvidenceContext, SourceEvidence
    from adroit.evidence.points import _numbers
    from adroit.parameter_space.scan import HIGGS_INVISIBLE, INVISIBLE_H
    row = PointResult(point=Point(m_chi=30, m_med=125.09), omega_h2=0.1, dd_kind="SI", dd_sigma_cm2=0.0,
                      dd_limit_cm2=None, excluded={INVISIBLE_H: False}, values={"BR(h → invisible)": 0.15})
    context = EvidenceContext(sources=[SourceEvidence(id=HIGGS_INVISIBLE, metadata={"data": {"br_limit": 0.107}})])
    replaced = _numbers(INVISIBLE_H, row, {"prediction": 0.15, "limit": 0.20}, {"source": "private-limit:" + "a" * 64},
                        context)
    assert replaced == (0.15, 0.20, "branching ratio")
    assert _numbers(INVISIBLE_H, row, {}, {}, context)[:2] == (0.15, 0.107)

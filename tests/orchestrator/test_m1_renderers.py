"""Renderers read the stored decision (the consolidation plan's M1, 2026-10-25): the Studies badge and its filter
(``study_headline``), the viability checklist's per-root counts, and the review queue's roles. Each was a hypothesis of
the survey; each test below is its control, failing before M1."""
from types import SimpleNamespace

from adroit.core.certificate import POLICY, Certificate, Check
from adroit.core.evidence import physical_identity
from adroit.orchestrator import study_headline
from adroit.parameter_space.classes import Point
from adroit.parameter_space.scan import PointResult
from adroit.parameter_space.verdict import Crossing


def test_the_badge_shows_the_combined_view_an_explain_study_and_an_unverified_dependence():
    track1 = {"verdict": {"level": "viable", "qualifiers": []},
              "likelihood_verdict": {"level": "viable_pending",
                                     "qualifiers": ["this conclusion depends on unverified records: x"]}}
    assert study_headline.read(track1) == ("VIABLE · combined: VIABLE PENDING · UNVERIFIED RECORDS", "viable")
    assert study_headline.read({"verdict": {"level": "pending"}}) == ("PENDING", "pending")
    explain = {"band": [], "level": "viable_pending", "thermal": [
        {"certificate": {"claim_kind": "thermal_solution", "scope": "a thermal point", "policy": POLICY,
                         "qualifiers": ["depends on unverified records: dampe-2112.08860-lines"]}}]}
    assert study_headline.read(explain) == ("VIABLE PENDING · UNVERIFIED RECORDS", "viable pending")
    explain["thermal"][0]["certificate"] = {"qualifiers": []}               # not a certificate: named (CO-06)
    assert study_headline.read(explain) == ("", "") and study_headline.headline(explain).damage
    assert study_headline.read({"level": "viable"}) == ("", "")           # not a single-idea study
    assert study_headline.colour("VIABLE · combined: PENDING") == "green"


def _root(status: str, excluded: bool, computed: str = "") -> Crossing:
    p = Point(m_chi=20, m_med=60)
    certificate = None
    if computed:
        certificate = Certificate(claim_kind="thermal_solution", scope="x", computed_status=computed,
                                  checks=[Check(name="eos_band", state="unknown", reason="tables missing")],
                                  policy=POLICY)
    return Crossing(point=p, status=status, kind="contour", certificate=certificate,
                    evaluation=PointResult(point=p, omega_h2=.12, dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                                           excluded={"toy": excluded}))


def test_the_checklist_does_not_count_a_waiting_roots_nominal_exclusion_as_a_verdict():
    from adroit.orchestrator.checklist import _contour
    waiting = [_root("pending", True, computed="excluded"), _root("pending", True, computed="excluded")]
    text = _contour("toy", waiting)
    assert "excluded at" not in text and "2 of them nominally excluded by it, awaiting their certificate" in text
    assert "excluded at 1" in _contour("toy", [_root("excluded", True)])


def test_the_review_queue_queues_the_single_idea_thermal_points_and_judges_candidates_by_eligibility():
    from adroit.constraints.review_queue import _roles
    engine = {"name": "test", "family": "test"}
    point = {"m_chi": 20.0, "m_med": 60.0, "g_chi": 0.1, "g_q": 0.25, "g_l": 0.0}
    single = SimpleNamespace(envelope=SimpleNamespace(workflow="single_idea", engine_mapping=engine),
                             result={"track1": None, "band": [], "thermal": [{"point": point, "status": "pending"}]})
    assert _roles(single)[physical_identity(engine, point)].role == "thermal_point"
    signal = SimpleNamespace(envelope=SimpleNamespace(workflow="signal", engine_mapping=engine), result={
        "verdicts": {"a": [{"excluded": False}], "b": [{"excluded": False}]},
        "eligibility": {"a": {"status": "pending", "certificate": {"claim_kind": "path2_thermal_eligibility"}},
                        "b": {"status": "pending"}}})
    roles = _roles(signal)
    assert roles["a"].status == "pending" and roles["a"].blocks_conclusion       # judged: by its eligibility
    assert roles["b"].status == "allowed"                                         # not judged: as before

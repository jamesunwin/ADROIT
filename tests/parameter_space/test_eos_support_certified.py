"""The auditor's consolidation audit (2026-10-25), CO-01 and CO-03 on the plane: a table's root (a nominal root refound
with a table, or a root only a table has; fresh or read from a checkpoint) supports or decides nothing until it is
certified at its own parameters (its thermal history, records, discovery), and the unverified records it used become
the conclusion's. The density and the constraints are ``test_eos_verdict``'s toy (the nominal root at 20 GeV, the
upper table's at 20.83, the lower's at 19.23); the refinement, the verdict, the certificates and the badge are
ADROIT's."""
from types import SimpleNamespace

import pytest

from adroit.constraints import relic
from adroit.orchestrator import study_headline
from adroit.parameter_space import certification
from adroit.parameter_space import verdict as v
from adroit.parameter_space.classes import Spin1Class
from adroit.parameter_space.scan import PointResult
from tests.parameter_space.test_eos_verdict import SHIFT, _density, _grid
from tests.unsigned_records import used

RECORD = "dampe-2112.08860-lines"
OUTSIDE = "Ωh² from a freeze-out outside the supported thermal history (toy)"


@pytest.fixture
def toy(monkeypatch):
    """``case``: ``history``, the tables (``relic.current_eos()`` names) whose roots' relic calculation is outside
    the supported history; ``excluded``, whether the toy constraint excludes at the nominal root; ``unsigned``, the
    tables whose roots are excluded only by the unverified record (enabled) or pending on it (disabled)."""
    case = {"history": (), "excluded": False, "unsigned": (), "enabled": False, "density": _density}
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: case["density"](p))
    monkeypatch.setattr("adroit.parameter_space.searches.prefetch_lhc", lambda cls, pts, *a: [None] * len(pts))

    def evaluate(cls, p, *args):
        table = relic.current_eos()
        unsigned = table in case["unsigned"]
        excluded = {"toy": case["excluded"] and not unsigned, "colliders (CMS)": False}
        if unsigned and case["enabled"]:
            excluded[RECORD] = True
        return PointResult(point=p, omega_h2=case["density"](p), dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded=excluded,
                           pending=[f"{RECORD}: unverified record not enabled"] if unsigned and not case["enabled"]
                           else [],
                           relic_validity=[OUTSIDE] if table in case["history"] else [],
                           unverified_records=[RECORD] if unsigned and case["enabled"] else [],
                           records=used(RECORD) if unsigned and case["enabled"] else {})
    monkeypatch.setattr(v, "evaluate", evaluate)
    return case


def _scan(case):
    scan = _grid()
    scan.request.unverified_records = case["enabled"]
    return scan


@pytest.mark.eos_band
@pytest.mark.needs("eos")
@pytest.mark.parametrize("table", ["ss2020-upper", "ss2020-lower"])
def test_a_shifted_root_outside_the_supported_history_does_not_certify_a_viable_root(toy, table):
    """CO-01: the nominal root valid and allowed; only one table's root has its relic calculation outside the
    supported thermal history. The band is not established (failed: a prerequisite shown not to hold), the root
    waits, and the headline is viable pending, never viable."""
    toy["history"] = (table,)
    result = v.verdict(_scan(toy))
    for c in result.crossings:
        eos = c.certificate.check("eos_band")
        assert c.status == "pending" and eos.state == "failed" and OUTSIDE in eos.reason, eos
        assert c.certificate.computed_status == "viable"
    assert result.level == "viable_pending"
    assert study_headline.read({"verdict": result.model_dump(mode="json")})[1] != "viable"


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_computed_exclusion_keeps_its_exclusion_without_a_certified_thermal_exclusion(toy):
    """CO-01 for exclusions: excluded at all three roots, but the upper table's root outside the supported history.
    The thermal exclusion is not certified (pending), the computed exclusion kept in the certificate (D-2)."""
    toy.update(history=("ss2020-upper",), excluded=True)
    result = v.verdict(_scan(toy))
    for c in result.crossings:
        assert c.status == "pending" and c.certificate.computed_status == "excluded"
        assert c.certificate.computed_excluded_by == ["toy"]
    assert result.level == "pending"


@pytest.mark.needs("eos")
def test_a_shifted_root_read_from_a_checkpoint_is_certified_too(toy):
    """CO-01 on resume: the upper table's root read back from a checkpoint (saved as judged, before certification)
    is certified at its own parameters exactly as a fresh one."""
    scan = _scan(toy)
    nominal = v.verdict(scan)
    root = nominal.root_attempts[0]
    saved = {}
    for name in v.EOS_VARIANTS:
        with relic.eos_variant(name):
            judged = v._eos_root(scan, root, name, .12, None)
        saved[name] = judged.model_copy(update={"evaluation": judged.evaluation.model_copy(
            update={"relic_validity": [OUTSIDE]})}) if name == "upper" else judged
    checkpoint = SimpleNamespace(load=lambda phase, key, model: saved[phase.split("-")[1]],
                                 save=lambda *a: None)
    c = v.judge_point(Spin1Class(), root.point)
    judged, eos = v._eos_checked(scan, root, c, 0, None, checkpoint, .12)
    assert judged.status == "pending" and eos.state == "failed" and OUTSIDE in eos.reason


@pytest.mark.needs("eos")
def test_a_root_only_a_table_has_is_certified_before_it_counts(toy):
    """CO-01 for a table's added root: Ωh² = 0.0029 m_χ has no nominal root on 10–40 GeV; the lower table's (× 1.04)
    is at 39.8 GeV. Outside the supported history, its status is pending, never the allowed one its constraints
    gave."""
    toy["density"] = lambda p: .0029 * p.m_chi * SHIFT[relic.current_eos()]
    scan = _scan(toy)
    scan.points = [r.model_copy(update={"omega_h2": .0029 * r.point.m_chi}) for r in scan.points]
    clean = v._eos_new_roots(scan, [], .12, None)
    toy["history"] = ("ss2020-lower",)
    outside = v._eos_new_roots(scan, [], .12, None)
    assert {a.status for a in clean} == {"viable"}
    assert {a.status for a in outside} == {"pending"} and all("thermal history" in a.why for a in outside)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_record_used_only_at_the_shifted_roots_is_the_conclusions_dependency(toy):
    """CO-03: the nominal root excluded by a verified constraint; the tables' roots excluded only by an unverified
    record the run enabled. The across-band exclusion rests on that record: the conclusion, its certificate (with
    the record's fingerprint), the report line and the badge say it depends on it."""
    toy.update(excluded=True, unsigned=("ss2020-upper", "ss2020-lower"), enabled=True)
    result = v.verdict(_scan(toy))
    assert result.level == "excluded"
    assert result.qualifiers == [f"this conclusion depends on unverified records: {RECORD}"]
    for c in result.crossings:
        assert c.status == "excluded" and c.certificate.bound.unverified_records == [RECORD]
        assert RECORD in c.certificate.bound.records
        assert c.certificate.qualifiers == [f"depends on unverified records: {RECORD}"]
    assert f"depends on unverified records: {RECORD}" in certification.summary_lines(result.crossings)[0]
    badge, level = study_headline.read({"verdict": result.model_dump(mode="json")})
    assert level == "excluded" and "UNVERIFIED RECORDS" in badge


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_the_same_record_disabled_leaves_the_across_band_claim_pending(toy):
    """CO-03's other side: with the record not enabled the tables' roots are pending on it, and the nominal
    exclusion is not certified across the band."""
    toy.update(excluded=True, unsigned=("ss2020-upper", "ss2020-lower"), enabled=False)
    result = v.verdict(_scan(toy))
    assert result.level == "pending" and all(c.status == "pending" for c in result.crossings)
    assert all(not c.certificate.bound.unverified_records for c in result.crossings)


def _table_only_branch(monkeypatch, enabled: bool):
    """The auditor's CO recheck, CR-02 (2026-10-26): nominal Ωh² 0.09, 0.13, 0.114, 0.119 at 10–40 GeV (roots between 10
    and 20 GeV, every one excluded by the toy constraint); the lower table (× 1.04) has roots at 32.77 GeV the
    nominal lacks, excluded only by an unverified record (``enabled``, or pending on it) that no nominal root
    uses."""
    import numpy as np
    from adroit.parameter_space.scan import _point_at

    def density(p):
        return float(np.interp(p.m_chi, [10, 20, 30, 40], [.09, .13, .114, .119])) * SHIFT[relic.current_eos()]

    def evaluate(cls, p, *args):
        needs = relic.current_eos() == "ss2020-lower" and p.m_chi > 30
        return PointResult(point=p, omega_h2=density(p), dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={RECORD: True} if needs and enabled else {"toy": not needs},
                           pending=[f"{RECORD}: unverified record not enabled"] if needs and not enabled else [],
                           unverified_records=[RECORD] if needs and enabled else [],
                           records=used(RECORD) if needs and enabled else {})
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: density(p))
    monkeypatch.setattr(v, "evaluate", evaluate)
    scan = _grid()
    scan.request.unverified_records = enabled
    scan.xs = [10., 20., 30., 40.]
    scan.request.x = scan.request.x.model_copy(update={"n": 4, "log": False})
    scan.points = [evaluate(None, _point_at(scan.request, x, y)) for y in scan.ys for x in scan.xs]
    return v.verdict(scan)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_root_only_a_table_has_keeps_its_certificate_and_record(toy, monkeypatch):
    """CR-02: the excluded conclusion rests on the table-only roots' exclusion, so their certificates are kept with
    it, bound to their table and to the record's fingerprint; the qualifier, the report's certification lines and
    the badge read them, and a changed record makes the stored conclusion stale without rewriting it."""
    from adroit.orchestrator.track1 import _contour_table
    result = _table_only_branch(monkeypatch, enabled=True)
    assert result.level == "excluded" and len(result.table_roots) == 2
    for c in result.table_roots:
        assert c.status == "excluded" and c.certificate.decided and c.point.m_chi == pytest.approx(32.77, abs=.01)
        assert set(c.certificate.bound.eos_tables) == {"lower"} and c.certificate.bound.unverified_records == [RECORD]
        assert len(c.certificate.bound.records[RECORD]) == 64
    assert not any(RECORD in c.certificate.bound.unverified_records for c in result.crossings)
    assert result.rests_on == list(range(len(result.crossings))) and result.rests_on_table_roots == [0, 1]
    assert result.qualifiers == [f"this conclusion depends on unverified records: {RECORD}"]
    report = "\n".join(_contour_table(result, "m_chi", "g_chi"))
    assert ("Certification of these 2 roots only a table has, which an excluded conclusion also rests on: 2 "
            f"certified; depends on unverified records: {RECORD}.") in report
    data = {"verdict": result.model_dump(mode="json")}
    assert study_headline.headline(data) == ("EXCLUDED · UNVERIFIED RECORDS", "excluded", "certified", "")
    monkeypatch.setattr(certification, "record_fingerprints", lambda ids: {i: "changed" for i in ids})
    assert study_headline.headline(data).certification == "stale"


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_root_only_a_table_has_on_a_disabled_record_leaves_the_conclusion_pending(toy, monkeypatch):
    """CR-02's other side: the record not enabled, the table-only roots wait on it; the headline is pending, and
    rests on none of them."""
    result = _table_only_branch(monkeypatch, enabled=False)
    assert result.level == "pending" and [c.status for c in result.table_roots] == ["pending", "pending"]
    assert result.rests_on_table_roots == [] and any("the lower table has a thermal root" in u
                                                     for u in result.unresolved)


@pytest.mark.needs("eos")
def test_a_viable_headline_rests_on_its_certified_witness_alone(toy, monkeypatch):
    """The auditor's CO recheck, CR-04 (2026-10-26), on the plane: one viable certified root, and one waiting (its relic
    calculation outside the supported history). The headline rests on the viable root alone; the history reads it
    certified, and the waiting root keeps its own reading."""
    allowed = v.evaluate
    monkeypatch.setattr(v, "evaluate", lambda cls, p, *a: allowed(cls, p, *a).model_copy(
        update={"relic_validity": [OUTSIDE] if p.g_chi > .15 else []}))
    result = v.verdict(_scan(toy))
    assert [(c.point.g_chi, c.status) for c in result.crossings] == [(.1, "viable"), (.2, "pending")]
    assert result.level == "viable" and result.rests_on == [0]
    assert study_headline.headline({"verdict": result.model_dump(mode="json")}).certification == "certified"
    waiting = result.crossings[1].certificate
    assert certification.reading(waiting).startswith("not certified: ")

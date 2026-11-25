"""The auditor's CS recheck (the independent audit of 2026-10-27 (cs recheck), 2026-10-28), each finding through its real producer:
- CT-01: a certificate bound a record as it read when the certificate was made, not the version its evaluation used,
  so an edit between the two was certified as if it had been evaluated;
- CT-02: a thermal claim was not bound to the density record that defines its target;
- CT-03: a band check that failed, on the single-idea study and on the plane, dropped the records that made it fail.
CT-04, a study whose result is missing, is in ``tests/ui/test_ct_missing_result.py``.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from adroit.constraints import database, planck
from adroit.constraints import searches as cs
from adroit.constraints.review_identity import version
from adroit.evidence.points import _certification
from adroit.orchestrator import study_headline
from adroit.orchestrator.single_idea import SingleIdeaResult
from adroit.parameter_space import certification
from adroit.parameter_space import verdict as v
from adroit.parameter_space.classes import Point
from adroit.parameter_space.likelihood import DENSITY_VERSION
from adroit.parameter_space.scan import PointResult
from tests.orchestrator import test_single_idea_eos as fixture
from tests.parameter_space.test_eos_support_certified import RECORD, _scan, toy  # noqa: F401  (a fixture)
from tests.unsigned_records import used

HIGGS = "atlas-2207.00092-higgs-mu"


def _changed(rid: str, **data):
    """The record and a copy of it with ``data`` changed."""
    record = database.record(rid)
    return record, record.model_copy(update={"data": {**record.data, **data}})


def _reading(rid: str, by):
    """The database reading ``by`` in place of the record ``rid``."""
    read = database.record
    return patch.object(database, "record", lambda key: by if key == rid else read(key))


def _evaluated(records):
    """The single-idea toy's evaluations noting ``records`` (or ``records(fields)``) as used."""
    original = fixture.PointResult
    return patch.object(fixture, "PointResult", lambda **kw: original(
        **{**kw, "records": records(kw) if callable(records) else records}))


@pytest.mark.needs("eos")
def test_a_certificate_binds_the_version_its_evaluation_read_not_a_later_one(tmp_path):
    """CT-01, the auditor's case: the real Higgs-strength search at a SingletMixing point (m_χ = 200, m_med = 500,
    g_χ = 0.5, sin θ = 0.3) is excluded by the reviewed ATLAS record (μ = 0.91); the record changes before the study
    is certified. The certificate binds the version evaluated, so the saved claim reads stale, naming the record; it
    is never certified against content that was not evaluated."""
    from adroit.parameter_space import searches as ps
    from adroit.parameter_space.portals.higgs import SingletMixing
    with cs.records_used() as every:
        outcome = ps.higgs_signal(SingletMixing(), Point(m_chi=200, m_med=500, g_chi=.5, g_q=.3), False)
    noted = cs.confirmed(every)
    record, changed = _changed(HIGGS, mu=outcome.value, sigma=1.0)
    assert outcome.excluded is True and noted == {HIGGS: version(record)} and version(changed) != version(record)
    original = fixture.PointResult
    with patch.object(fixture, "PointResult", lambda **kw: original(**{**kw, "excluded": {outcome.name: True},
                                                                         "records": noted})), \
            _reading(HIGGS, changed):
        result = fixture._study(tmp_path / "study", excluded_above=0)
        assert result.thermal
        assert all(p.certificate.bound.records[HIGGS] == version(record) for p in result.thermal)
        assert study_headline.headline(result.model_dump(mode="json"), "single_idea").certification == "stale"
        assert _certification(result.thermal[0]).startswith(f"stale: the record {HIGGS} changed")


def test_a_record_used_in_two_versions_or_changed_during_its_evaluation_has_no_version_used():
    """CT-01: two versions of one record within one evaluation leave neither as the one used; a record whose version
    differs once the evaluation is over (its data may have changed between its admission and its read) likewise."""
    record, changed = _changed(HIGGS, mu=.5)              # changed, it is no longer the reviewed content
    with cs.records_used() as every:
        assert cs.admits(record, True) and cs.admits(record, True) and cs.admits(changed, True)
    assert every == {HIGGS: ""}
    with cs.records_used() as every:
        cs.admits(record, False)
    assert cs.confirmed(every) == {HIGGS: version(record)}
    read = database.records
    with patch.object(database, "records", lambda: tuple(changed if r.id == HIGGS else r for r in read())):
        assert cs.confirmed(every) == {HIGGS: ""}


@pytest.mark.needs("eos")
@pytest.mark.parametrize("records", [{HIGGS: ""}, [HIGGS]], ids=["two versions", "a result before the versions"])
def test_a_claim_whose_record_version_is_not_known_is_not_certified(tmp_path, records):
    """CT-01: a claim whose record version used is not known is not certified, saying to run it again; a result's
    list of record ids (before CT-01) reads so, never bound to the record as it reads when certified."""
    with _evaluated(records):
        result = fixture._study(tmp_path / "study", excluded_above=0)
    assert result.thermal
    for p in result.thermal:
        check = p.certificate.check("records")
        assert check.state == "unknown" and HIGGS in check.reason and "run it again to certify" in check.reason
        assert p.certificate.bound.records[HIGGS] == "" and p.status == "pending"
    assert study_headline.headline(result.model_dump(mode="json"), "single_idea").certification == "not certified"


def test_a_records_data_file_is_read_again_when_it_changes(tmp_path):
    """CT-01: a record's data were kept by its id alone, so a process went on reading a changed file's old contents,
    which no fingerprint of the file would show. They are read again when the file changes."""
    data = tmp_path / "limits.yaml"
    data.write_text("limit: 1\n")
    rid = "cms-1806.00843-dijet"
    with _reading(rid, database.record(rid).model_copy(update={"data_file": str(data)})):
        cs._bundled.cache_clear()
        assert cs._bundled(rid)["limit"] == 1
        data.write_text("limit: 2\n")
        os.utime(data, ns=(1_000_000_000, 2_000_000_000))
        assert cs._bundled(rid)["limit"] == 2
    cs._bundled.cache_clear()


@pytest.mark.needs("eos")
def test_a_thermal_claim_is_bound_to_its_targets_record_and_reads_stale_when_it_changes(tmp_path):
    """CT-02, the auditor's case: the single-idea study's thermal points and its tables' points are decided against the
    relic target (planck-2018-omega, Ωh² = 0.12). Each is bound to that record's version as the target was read;
    the record changed after saving, the headline and the point read stale, and the saved result keeps the old
    binding."""
    result = fixture._study(tmp_path / "study", excluded_above=100)
    claims = [*result.thermal, *(r for rows in result.eos_thermal.values() for r in rows)]
    assert result.thermal and DENSITY_VERSION
    assert all(p.certificate.bound.records[planck.ID] == DENSITY_VERSION for p in claims)
    data = result.model_dump(mode="json")
    assert study_headline.headline(data, "single_idea").certification == "certified"
    _, changed = _changed(planck.ID, value=.15)
    with _reading(planck.ID, changed):
        assert study_headline.headline(data, "single_idea").certification == "stale"
        assert _certification(result.thermal[0]).startswith(f"stale: the record {planck.ID} changed")
        saved = SingleIdeaResult.model_validate_json(result.model_dump_json())
        assert saved.thermal[0].certificate.bound.records[planck.ID] == DENSITY_VERSION
        assert study_headline.headline(saved.model_dump(mode="json"), "single_idea").certification == "stale"


def test_a_fixed_point_exclusion_is_not_bound_to_the_relic_target():
    """CT-02: a fixed-point exclusion, which no relic density decides, stays independent of the target's record; a
    thermal claim at the same point is bound to it."""
    p = Point(m_chi=10, m_med=1000, g_chi=.5)
    c = v.Crossing(point=p, status="excluded", excluded_by=["toy"],
                   evaluation=PointResult(point=p, omega_h2=.1, dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                                          excluded={"toy": True}))
    fixed = certification.certify(c, "fixed_point_exclusion", "the point", [])
    thermal = certification.certify(c, "thermal_solution", "the point", [])
    assert planck.ID not in fixed.certificate.bound.records and fixed.certificate.decided
    assert thermal.certificate.bound.records[planck.ID] == DENSITY_VERSION


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_failed_band_keeps_the_record_that_made_it_fail(tmp_path):
    """CT-03, the auditor's case: only the upper table's point (20.83 GeV) uses the reviewed ATLAS record, and is excluded;
    the nominal (20 GeV) and the lower point are viable. The band fails, its reason naming that point, and the
    nominal claim depends on and is bound to the record's version used; changed, the nominal point and the headline
    read stale."""
    from adroit.constraints import relic

    def records(kw):
        return used(HIGGS) if (relic.current_eos() or "").endswith("upper") and kw["point"].m_chi > 20.5 else {}
    with _evaluated(records):
        result = fixture._study(tmp_path / "study", excluded_above=20.5)
    nominal = result.thermal[0]
    band = nominal.certificate.check("eos_band")
    assert band.state == "failed" and "excluded at the point with the upper table" in band.reason
    assert band.evidence_records[HIGGS] == used(HIGGS)[HIGGS]           # beside the tables' points' target record
    assert nominal.certificate.bound.records[HIGGS] == used(HIGGS)[HIGGS]
    data = result.model_dump(mode="json")
    assert study_headline.headline(data, "single_idea").certification == "not certified"
    _, changed = _changed(HIGGS, mu=.5)
    with _reading(HIGGS, changed):
        assert study_headline.headline(data, "single_idea").certification == "stale"
        assert _certification(nominal).startswith(f"stale: the record {HIGGS} changed")


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_the_planes_failed_band_keeps_the_records_of_the_roots_it_names(toy):  # noqa: F811
    """CT-03 on the plane: the nominal roots allowed; the upper table's roots excluded only by an unverified record
    the run enables. The band fails at each root; its check carries that record, unverified and with the version
    used, so the root depends on it and reads stale when it changes. Each root is bound to the target's record too
    (CT-02)."""
    toy.update(unsigned=("ss2020-upper",), enabled=True)
    result = v.verdict(_scan(toy))
    assert result.crossings
    for c in result.crossings:
        band = c.certificate.check("eos_band")
        assert c.status == "pending" and band.state == "failed" and "EOS-sensitive" in band.reason
        assert band.records == [RECORD] and band.evidence_records[RECORD] == used(RECORD)[RECORD]
        assert c.certificate.bound.records[RECORD] == used(RECORD)[RECORD]
        assert c.certificate.bound.records[planck.ID] == DENSITY_VERSION
    _, changed = _changed(RECORD, note_for_test=1)
    with _reading(RECORD, changed):
        assert _certification(result.crossings[0]).startswith(f"stale: the record {RECORD} changed")

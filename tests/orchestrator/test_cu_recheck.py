"""The auditor's CT recheck (the independent audit of 2026-10-28 (ct recheck), 2026-10-28), each finding through its real producer:
- CU-01: the scan's Fermi-LAT and IceCube curves were kept for the process, so a changed curve went on deciding while
  the certificate bound the new one;
- CU-02: a thermal claim's certificate hashed the equation-of-state tables when it was made, after the calculation;
- CU-03: a malformed list of record ids raised TypeError past the readers' damage boundaries;
- CU-04: one record object read in two data versions within an evaluation was certified as the one.
CU-03 through the pages is in ``tests/ui/test_cu_version_damage.py``; CU-05 in ``tests/orchestrator/test_browser_layer``.
"""
from __future__ import annotations

import copy
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from adroit.constraints import database, relic, review_identity
from adroit.constraints import searches as cs
from adroit.constraints.review_identity import version
from adroit.core.certificate import Check
from adroit.evidence.points import _certification
from adroit.orchestrator import single_idea, study_headline
from adroit.parameter_space import certification, halo_region, scan
from adroit.parameter_space import verdict as v
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.scan import PointResult
from tests.orchestrator import test_single_idea_eos as fixture
from tests.parameter_space.test_eos_support_certified import _scan, toy  # noqa: F401  (a fixture)

DIJET = "cms-1806.00843-dijet"
UPPER = relic.EOS_TABLES["upper"]
STALE_UPPER = "stale: the equation of state's upper table is not the one it was certified with"


def _scratch(rid: str, tmp_path, data: dict):
    """The record ``rid``, unverified, its data file a copy of ``data`` in the test's folder (read as a declared
    input there), and the database reading it in its place."""
    path = tmp_path / f"{rid}.yaml"
    path.write_text(yaml.safe_dump(data))
    record = database.record(rid).model_copy(update={"data_file": str(path), "verified_by": "", "verified_on": None,
                                                     "verification_sha256": ""})
    every = database.records()
    return path, record, patch.object(database, "records", lambda: tuple(record if r.id == rid else r for r in every))


def _rewrite(path, content: bytes, stamp: int) -> None:
    path.write_bytes(content)
    os.utime(path, ns=(stamp * 10**9, stamp * 10**9))


def test_a_long_lived_process_reads_a_changed_curve_and_binds_the_curve_it_read(tmp_path, monkeypatch):
    """CU-01, the auditor's case: the real ``scan.evaluate`` and Fermi-LAT comparison (``_gamma_rays``) in one process, the
    dwarfs' curve a scratch copy, b b̄ at four times its limit (ratio 2, excluded). The curve weakened a hundredfold,
    the next evaluation reads it, as a fresh process does (ratio 0.02, allowed), and is bound to the curve it read;
    the first claim, bound to the old curve, reads stale."""
    data = copy.deepcopy(database.data(scan.FERMI))
    monkeypatch.setattr(review_identity, "PROJECT_ROOT", tmp_path)
    path, record, reading = _scratch(scan.FERMI, tmp_path, data)
    p = Point(m_chi=100, m_med=1000, g_chi=.1, g_q=.1)
    limit = database.interpolate_limit(data["limits"]["bb"]["limit_cm3_s"], 100)

    def evaluator(cls, p, *args, **kwargs):
        ratio, _ = scan._gamma_rays(cls, p, True)
        return PointResult(point=p, omega_h2=.12, dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={"gamma rays": ratio > 1}, ratios={"gamma rays": ratio})

    def claim(row):
        status = "excluded" if row.excluded["gamma rays"] else "viable"
        crossing = v.Crossing(point=p, status=status, excluded_by=["gamma rays"] if status == "excluded" else [],
                              evaluation=row)
        return certification.certify(crossing, "fixed_point_exclusion", "the point", [], enabled=True).certificate

    with reading, patch.object(Spin1Class, "sigma_v_today", lambda *a: {"b": 4 * limit}), \
            patch.object(scan, "_evaluate", evaluator), patch.object(halo_region, "preset", lambda: None):
        cs._bundled.cache_clear()
        first = scan.evaluate(Spin1Class(), p, True)
        old = version(record)
        for panel in data["limits"].values():
            for row in panel["limit_cm3_s"]:
                row[1] *= 100
        _rewrite(path, yaml.safe_dump(data).encode(), 2)
        warm = scan.evaluate(Spin1Class(), p, True)
        cs._bundled.cache_clear()
        cold = scan.evaluate(Spin1Class(), p, True)
        new = version(record)
        assert first.ratios["gamma rays"] == pytest.approx(2.0) and first.excluded["gamma rays"] is True
        assert warm.ratios == cold.ratios and warm.ratios["gamma rays"] == pytest.approx(.02)
        assert warm.excluded["gamma rays"] is False
        assert first.records == {scan.FERMI: old} and warm.records == {scan.FERMI: new} and new != old
        now, then = claim(warm), claim(first)
        assert certification.reading(now, certification.current_bound(now)).startswith("certified")
        assert certification.reading(then, certification.current_bound(then)) == \
            f"stale: the record {scan.FERMI} changed since it was certified"
    cs._bundled.cache_clear()


def test_a_record_read_in_two_versions_within_one_evaluation_has_none_even_when_restored(tmp_path, monkeypatch):
    """CU-04, the auditor's case: one record object, its data file read as A, then B (a scientific number doubled), then A
    again, each read admitted. Two versions were read, so neither is the one used, and the claim is not certified,
    though the file ends as it began and the object is the same. A read before the record's admission counts too."""
    data = copy.deepcopy(database.data(DIJET))
    monkeypatch.setattr(review_identity, "PROJECT_ROOT", tmp_path)
    path, record, reading = _scratch(DIJET, tmp_path, data)
    a = path.read_bytes()
    b = yaml.safe_dump({**data, "limit": [[m, 2 * x] for m, x in data["limit"]]}).encode()
    with reading:
        cs._bundled.cache_clear()
        with cs.records_used() as every:
            for stamp, content in enumerate((a, b, a), start=1):
                _rewrite(path, content, stamp)
                assert cs.admits(database.record(DIJET), True)
                cs._bundled(DIJET)
        assert every == {DIJET: ""} and cs.confirmed(every) == {DIJET: ""}
        point = Point(m_chi=100, m_med=1000, g_chi=.5)
        row = PointResult(point=point, omega_h2=.12, dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                          excluded={"toy": True}, records=cs.confirmed(every), unverified_records=[DIJET])
        claim = certification.certify(v.Crossing(point=point, status="excluded", excluded_by=["toy"], evaluation=row),
                                      "fixed_point_exclusion", "the point", [], enabled=True)
        check = claim.certificate.check("records")
        assert claim.status == "pending" and check.state == "unknown" and "run it again to certify" in check.reason
        with cs.records_used() as every:                    # read in B before its admission in A
            _rewrite(path, b, 4)
            cs._bundled(DIJET)
            _rewrite(path, a, 5)
            cs.admits(database.record(DIJET), True)
        assert every == {DIJET: ""}
        with cs.records_used() as every:                    # one version throughout: that one
            cs.admits(database.record(DIJET), True)
            cs._bundled(DIJET)
        assert every == {DIJET: version(record)} != {DIJET: ""}
    cs._bundled.cache_clear()


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_table_changed_after_the_single_idea_study_used_it_is_not_the_version_bound(tmp_path, eos_copy):
    """CU-02, the auditor's case: the real single-idea study with copied tables; after the upper table's points are
    evaluated and before their certificates are made, the upper table's file changes. Its points and the nominal
    claim are bound to the table they were decided with, the one published, so they read stale; they are never bound to
    a file the calculation did not read."""
    upper = eos_copy / UPPER[0]
    original = upper.read_bytes()
    real = single_idea._complete

    def interleaved(thermal, discovered, enabled, discovery, eos=None):
        if eos == ("upper",) and upper.read_bytes() == original:
            upper.write_bytes(original + b"\n# changed after the upper table's points were evaluated\n")
        return real(thermal, discovered, enabled, discovery, eos=eos)
    relic.eos_table.cache_clear()
    try:
        with patch.object(single_idea, "_complete", interleaved):
            result = fixture._study(tmp_path / "study", excluded_above=1000)
        assert upper.read_bytes() != original and result.thermal and result.eos_thermal["upper"]
        assert all(p.certificate.bound.eos_tables == {"upper": UPPER[1]} for p in result.eos_thermal["upper"])
        assert all(p.certificate.bound.eos_tables["upper"] == UPPER[1] for p in result.thermal)
        assert study_headline.headline(result.model_dump(mode="json"), "single_idea").certification == "stale"
        assert _certification(result.thermal[0]).startswith(STALE_UPPER)
        upper.write_bytes(original)
        assert study_headline.headline(result.model_dump(mode="json"), "single_idea").certification == "certified"
    finally:
        relic.eos_table.cache_clear()


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_table_changed_after_the_plane_used_it_is_not_the_version_bound(toy, eos_copy):  # noqa: F811
    """CU-02 on the plane: the upper table changes after its root is refound and judged, before that root's
    certificate. The roots are bound to the published table they were decided with, and read stale."""
    upper = eos_copy / UPPER[0]
    original = upper.read_bytes()
    real = v._certified

    def interleaved(*args, **kwargs):
        if kwargs.get("table", args[5] if len(args) > 5 else "") == "upper" and upper.read_bytes() == original:
            upper.write_bytes(original + b"\n# changed after the upper table's root was judged\n")
        return real(*args, **kwargs)
    relic.eos_table.cache_clear()
    try:
        with patch.object(v, "_certified", interleaved):
            result = v.verdict(_scan(toy))
        assert upper.read_bytes() != original and result.crossings
        for c in result.crossings:
            assert c.certificate.bound.eos_tables["upper"] == UPPER[1]
            assert _certification(c).startswith(STALE_UPPER)
    finally:
        relic.eos_table.cache_clear()


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_table_changed_after_path_2_checked_it_is_not_the_version_bound(monkeypatch, eos_copy):
    """CU-02 on Path 2: the tables checked for the band at a point at the target, then the central table changed
    before the eligibility's certificate. It is bound to the table as checked, and reads stale."""
    from adroit.core.evidence import EvidenceContext
    from adroit.orchestrator import physical_eligibility as eligibility
    from adroit.orchestrator import signal
    from adroit.parameter_space.classify import classify
    from tests.orchestrator.test_physical_eligibility import point_result, spec
    central = eos_copy / relic.EOS_TABLES["central"][0]
    original = central.read_bytes()
    s = spec()
    cls, p, _ = classify(s)
    candidate = signal.Candidate(label="30", mass_gev=30, model=s.name, spin=0)
    request = signal.SignalRequest(experiment="toy", user_models=[signal.UserModel(spec=s, masses_gev=[30])])
    monkeypatch.setattr(eligibility, "_physical", lambda *a: (cls, p.model_copy(update={"m_chi": 30}), None, 0., 0.))
    monkeypatch.setattr(eligibility, "_current_context",
                        lambda *a: EvidenceContext(origin="captured", identity="current", code_sha256="code"))
    monkeypatch.setattr(scan, "evaluate", lambda cls, p, *a, **k: point_result(p))
    monkeypatch.setattr(relic, "band_values", lambda compute: {"upper": .1195, "lower": .1206})
    real = eligibility._certificate

    def interleaved(*args):
        central.write_bytes(original + b"\n# changed after the band was checked\n")
        return real(*args)
    monkeypatch.setattr(eligibility, "_certificate", interleaved)
    row = eligibility.assess(request, [candidate], [SimpleNamespace(label="30")], object())["30"]
    assert row.status == "eligible" and row.certificate.bound.eos_tables["central"] == relic.EOS_TABLES["central"][1]
    assert certification.reading(row.certificate, certification.current_bound(row.certificate)).startswith(
        "stale: the equation of state's central table is not the one it was certified with")


@pytest.mark.parametrize("member", [{}, []], ids=["an object", "a list"])
def test_a_malformed_list_of_record_ids_is_named_damage(member):
    """CU-03: a list of record ids (a result from before CT-01) holding something other than an id is a validation
    error, in a point's records and in a check's evidence, never a TypeError past the readers' boundaries; a list of
    ids still reads as versions not known."""
    point = {"point": {"m_chi": 10, "m_med": 100, "g_chi": .5}, "omega_h2": .1, "dd_kind": "SI", "dd_sigma_cm2": 0,
             "dd_limit_cm2": 1, "excluded": {}}
    with pytest.raises(ValidationError, match="not an id"):
        PointResult.model_validate({**point, "records": [member]})
    with pytest.raises(ValidationError, match="not an id"):
        Check.model_validate({"name": "eos_band", "state": "satisfied", "evidence_records": [member]})
    assert PointResult.model_validate({**point, "records": [DIJET]}).records == {DIJET: ""}


@pytest.mark.needs("eos")
@pytest.mark.parametrize("member", [{}, []], ids=["an object", "a list"])
def test_a_single_idea_result_with_a_malformed_list_reads_as_damaged(tmp_path, member):
    """CU-03, the auditor's case: a saved single-idea study's ``thermal[0].evaluation.records`` set to ``[{}]`` or ``[[]]``.
    Its kind's model refuses it as a validation error, which the headline names as damage."""
    data = fixture._study(tmp_path / "study", excluded_above=1000).model_dump(mode="json")
    data["thermal"][0]["evaluation"]["records"] = [member]
    with pytest.raises(ValidationError, match="not an id"):
        single_idea.SingleIdeaResult.model_validate(data)
    path = tmp_path / "result.json"
    path.write_text(json.dumps(data))
    assert "not an id" in study_headline.unlike(path.read_bytes(), "single_idea")

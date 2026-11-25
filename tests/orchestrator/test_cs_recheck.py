"""The auditor's CR recheck (2026-10-27): the regressions of its record findings, each failing before its repair.

- CS-01: a saved result whose named support is missing or malformed, a stored certificate without its policy, and a
  result of another kind's shape were read with a decisive (or certified) badge; now they are damage, named.
- CS-02: a reviewed record that decided a claim was not bound to it, so changing the record left the claim certified.
- CS-03: a nominally rootless plane dropped the roots only a table has, with their certificates.
- CS-04: a table's point whose fit is definitively below the criterion was among the claims an exclusion rests on, so
  its own open thermal history un-certified an exclusion its fit alone decides.
- CS-05: a records file that cannot be read made every page that assesses a saved study fail.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from adroit.core.certificate import POLICY, Certificate
from adroit.orchestrator import single_idea, studies, study_headline
from adroit.orchestrator.single_idea import SingleIdeaResult
from tests.unsigned_records import used

KINDS = ("track1", "single_idea", "signal", "idea", "promotion", "native_joint", "native_coverage", "exclusion",
         "lagrangian")


def _excluded(tmp_path: Path, **kw) -> SingleIdeaResult:
    """A real single-idea study (``_study`` over the toy of ``test_single_idea_eos``): every point excluded, its
    headline resting on the nominal points and on the lower table's point the nominal lacks (the auditor's control)."""
    from tests.orchestrator.test_single_idea_eos import _study
    return _study(tmp_path, excluded_above=0, masses=(10, 20, 30, 40),
                  nominal=lambda m: float(np.interp(m, [10, 20, 30, 40], [.09, .13, .114, .119])), **kw)


def _saved(root: Path, name: str, kind: str, data: object) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    studies.record(folder, kind, name)
    (folder / "result.json").write_text(json.dumps(data))
    return folder


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_result_whose_named_table_support_is_missing_or_malformed_is_damaged_never_certified(tmp_path):
    result = _excluded(tmp_path / "study")
    data = result.model_dump(mode="json")
    assert result.level == "excluded" and result.rests_on_tables == {"lower": [2]}
    assert study_headline.headline(data) == ("EXCLUDED", "excluded", "certified", "")
    variants = {"tables absent": lambda d: d.pop("eos_thermal"), "tables null": lambda d: d.update(eos_thermal=None),
                "tables a list": lambda d: d.update(eos_thermal=[]),
                "the table absent": lambda d: d["eos_thermal"].pop("lower"),
                "support false": lambda d: d.update(rests_on_tables=False),
                "support zero": lambda d: d.update(rests_on_tables=0),
                "support a list": lambda d: d.update(rests_on_tables=[]),
                "a position beyond": lambda d: d.update(rests_on_tables={"lower": [9]}),
                "a boolean position": lambda d: d.update(rests_on_tables={"lower": [True]}),
                "tables without its own": lambda d: d.pop("rests_on"),
                "a policy missing": lambda d: d["eos_thermal"]["lower"][2]["certificate"].pop("policy")}
    for name, damage in variants.items():
        d = copy.deepcopy(data)
        damage(d)
        with pytest.raises(ValueError):
            SingleIdeaResult.model_validate(d)
        found = study_headline.headline(d)                         # by its shape alone
        assert found.damage and not found.words and found.certification == "", (name, found)
        folder = _saved(tmp_path / "runs", name.replace(" ", "_"), "single_idea", d)
        found = study_headline.headline_of(folder)                 # as its study's kind
        assert found.damage and not found.words, (name, found)
        if name != "a policy missing":                          # the support itself damaged: the card's stale
            assert study_headline.resting_claims(d) == [], name  # reason reads nothing from it


def test_a_stored_certificate_without_its_policy_does_not_load():
    stored = {"claim_kind": "thermal_solution", "scope": "a point", "checks": []}
    with pytest.raises(ValueError):
        Certificate.model_validate(stored)
    assert Certificate.model_validate({**stored, "policy": POLICY}).policy == POLICY


def test_a_result_of_another_shape_shows_no_badge_on_a_study_of_any_kind(tmp_path):
    """The auditor's wrong-schema matrix: ``{"band": 3, "level": "viable"}`` had shown VIABLE on studies of all nine kinds."""
    for kind in KINDS:
        found = study_headline.headline_of(_saved(tmp_path, kind, kind, {"band": 3, "level": "viable"}))
        assert not found.words and not found.level and found.damage, (kind, found)
    explain = {"band": [], "level": "viable", "request": {}}
    found = study_headline.headline_of(_saved(tmp_path, "explain_as_track1", "track1", explain))
    assert not found.words and "not a track1 result" in found.damage


def test_only_track1_and_single_idea_results_carry_a_badge():
    track1 = {"verdict": {"level": "viable"}}
    assert study_headline.headline(track1, "track1").words == "VIABLE"
    assert study_headline.headline(track1, "signal") == study_headline.Headline()
    assert study_headline.headline({"band": [], "level": "viable"}, "track1") == study_headline.Headline()


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_rejected_export_names_the_missing_support(tmp_path):
    from adroit.evidence.archive import export_run
    data = _excluded(tmp_path / "study").model_dump(mode="json")
    data.pop("eos_thermal")
    folder = _saved(tmp_path / "runs", "missing", "single_idea", data)
    with pytest.raises(ValueError, match="rests_on_tables"):
        export_run(folder, tmp_path / "missing.zip")
    assert not (tmp_path / "missing.zip").exists()


@pytest.mark.needs("eos")
def test_a_reviewed_record_that_decided_a_claim_is_bound_to_it_and_its_change_reads_stale(tmp_path):
    """CS-02 with the auditor's case: the real Higgs-strength search at a SingletMixing point (m_χ = 200, m_med = 500,
    g_χ = 0.5, sin θ = 0.3) is excluded by the reviewed ATLAS record. Its use is noted although the record is
    reviewed, and the toy study's claims are bound to its fingerprint; a change to its content reads stale."""
    from adroit.constraints import database
    from adroit.constraints import searches as cs
    from adroit.parameter_space import searches as ps
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.portals.higgs import SingletMixing
    from tests.orchestrator import test_single_idea_eos as fixture
    rid = "atlas-2207.00092-higgs-mu"
    record = database.record(rid)
    with cs.unverified_used() as unverified, cs.records_used() as every:
        outcome = ps.higgs_signal(SingletMixing(), Point(m_chi=200, m_med=500, g_chi=.5, g_q=.3), False)
    assert record.usable and outcome.excluded is True and unverified == set() and every == used(rid)
    original = fixture.PointResult
    with patch.object(fixture, "PointResult", lambda **kw: original(**{**kw, "excluded": {outcome.name: True},
                                                                         "records": dict(every)})):
        result = _excluded(tmp_path / "study")
    data = result.model_dump(mode="json")
    assert all(rid in p.certificate.bound.records and not p.certificate.bound.unverified_records
               for p in result.thermal)
    assert not any("unverified" in q for p in result.thermal for q in p.certificate.qualifiers)
    assert study_headline.headline(data, "single_idea").certification == "certified"
    changed = record.model_copy(update={"data": {**record.data, "mu": 0.5}})
    read = database.record
    with patch.object(database, "record", lambda key: changed if key == rid else read(key)):
        found = study_headline.headline(data, "single_idea")
        assert found.certification == "stale" and "STALE CERTIFICATION" in found.words
        from adroit.evidence.points import _certification
        assert _certification(result.thermal[0]).startswith(f"stale: the record {rid} changed")


def test_every_record_a_search_admits_is_noted_and_the_unverified_apart():
    from adroit.constraints import searches as cs
    from types import SimpleNamespace
    reviewed, waiting = SimpleNamespace(id="r", usable=True), SimpleNamespace(id="u", usable=False)
    with cs.unverified_used() as unverified, cs.records_used() as every:
        assert cs.admits(reviewed, False) and not cs.admits(waiting, False) and cs.admits(waiting, True)
    assert set(every) == {"r", "u"} and unverified == {"u"}


@pytest.mark.eos_band
def test_the_rootless_planes_table_roots_are_kept_and_rest_on_nothing():
    """CS-03 with the auditor's toy plane: nominal Ωh² 0.114–0.119 over 10–20 GeV (no root); the lower table (× 1.04) gives
    two excluded roots at 12.77 GeV. The verdict is pending and keeps them, each with its certificate."""
    import runpy
    from contextlib import ExitStack
    from adroit.constraints import relic
    from adroit.evidence.points import points
    h = runpy.run_path("tests/parameter_space/test_eos_verdict.py")
    v, record = h["v"], "dampe-2112.08860-lines"
    scan = h["_grid"]()
    scan.request.unverified_records = True
    scan.xs = [10., 20.]
    scan.request.x = scan.request.x.model_copy(update={"n": 2, "low": 10., "high": 20., "log": False})

    def density(p):
        return float(np.interp(p.m_chi, [10., 20.], [.114, .119])) * h["SHIFT"][relic.current_eos()]

    def evaluate(c, p, *args):
        return h["PointResult"](point=p, omega_h2=density(p), dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                                excluded={record: True}, unverified_records=[record],
                                records=used(record))
    scan.points = [evaluate(None, h["_point_at"](scan.request, x, y)) for y in scan.ys for x in scan.xs]
    with ExitStack() as stack:
        stack.enter_context(patch.object(h["Spin1Class"], "omega_h2", lambda c, p: density(p)))
        stack.enter_context(patch.object(v, "evaluate", evaluate))
        stack.enter_context(patch("adroit.parameter_space.searches.prefetch_lhc", lambda c, p, *a: [None] * len(p)))
        if v._eos_missing():
            pytest.skip("the equation-of-state tables are not installed")
        out = v.verdict(scan)
    assert out.level == "pending" and len(out.table_roots) == 2
    assert out.rests_on == [] and out.rests_on_table_roots == []
    for root in out.table_roots:
        assert root.status == "excluded" and set(root.certificate.bound.eos_tables) == {"lower"}
        assert record in root.certificate.bound.records
    saved = type(out).model_validate_json(out.model_dump_json())
    assert saved == out
    rows = [r for r in points("track1", type("R", (), {"scan": scan, "verdict": out, "likelihood_verdict": None,
                                                       "discovery_coverage": None, "request": None})())
            if r.point_id.startswith("table-root:")]
    assert len(rows) == 2 and all(r.status == "excluded" for r in rows)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
@pytest.mark.parametrize("physical", [False, True])
def test_a_table_point_whose_fit_is_definitively_poor_is_set_aside_by_its_fit(tmp_path, physical):
    """CS-04 with the auditor's case: every point excluded; the lower table's point at 32.77 GeV the nominal lacks has a fit
    below the criterion. Its thermal history valid or not, the exclusion rests on the same claims and reads certified;
    the point is kept, set aside by its fit, and said."""
    from adroit.constraints import relic
    from tests.orchestrator import test_single_idea_eos as fixture
    original = fixture.PointResult
    readings = []
    for open_history in (False, True):
        def made(**kw):
            invalid = open_history and relic.current_eos() and kw["point"].m_chi > 30
            return original(**kw, **({"relic_validity": ["an unresolved thermal history (injected)"]} if invalid
                                     else {}))
        with patch.object(fixture, "PointResult", made):
            result = _excluded(tmp_path / f"{physical}_{open_history}", poor_fit_above=30, physical=physical)
        data = result.model_dump(mode="json")
        assert result.level == "excluded" and result.rests_on_tables == {}
        (table, (i,)), = result.set_aside_tables.items()
        aside = result.eos_thermal[table][i]
        assert single_idea._fit_state(aside) == "below" and aside.m_chi > 30
        assert f"thermal point at m_χ = {aside.m_chi:.4g} GeV is set aside" in result.summary
        readings.append((study_headline.headline(data, "single_idea"), result.rests_on, aside.certificate.decided))
    assert readings[0][0] == readings[1][0] == ("EXCLUDED", "excluded", "certified", "")
    assert readings[0][1] == readings[1][1] and readings[0][2] and not readings[1][2]


def test_a_records_file_that_cannot_be_read_leaves_bound_claims_stale_and_raises_nothing(tmp_path, monkeypatch):
    """CS-05: the current records damaged after a claim was certified; its fingerprints read "" (cannot be read), the
    claim stale, naming its record; restored, it reads certified again."""
    from adroit.constraints import database
    from adroit.parameter_space.certification import record_fingerprints
    record, original = "dampe-2112.08860-lines", database.RECORDS.read_bytes()
    copied = tmp_path / "records.yaml"
    copied.write_bytes(original)
    monkeypatch.setattr(database, "RECORDS", copied)
    database.records.cache_clear()
    bound = record_fingerprints([record])
    assert len(bound[record]) == 64
    c = Certificate(claim_kind="thermal_solution", scope="a root", checks=[], policy=POLICY,
                    bound={"records": bound})
    data = {"verdict": {"level": "excluded", "crossings": [], "rests_on": [], "table_roots": [
        {"point": {"m_chi": 10, "m_med": 100}, "status": "excluded", "kind": "contour",
         "certificate": c.model_dump(mode="json")}], "rests_on_table_roots": [0]}}
    assert study_headline.headline(data).certification == "certified"
    for damage in ("records: [\n", "", "- just a list\n", "records: 7\n", "records:\n  - id: 3\n"):
        copied.write_text(damage)
        assert record_fingerprints([record]) == {record: ""}, damage
        found = study_headline.headline(data)
        assert found.certification == "stale" and not found.damage, (damage, found)
    copied.write_bytes(original)                               # restored: the same claim certified again
    assert study_headline.headline(data).certification == "certified"

"""The auditor's CV recheck (the independent audit of 2026-10-30 (cv recheck), 2026-10-30), each finding through its real producer:
- CW-01: a study's result was validated once per size and modification time, so a malformed replacement keeping both
  read as the valid result before it (through the rendered pages in ``tests/ui/test_cw_history.py``);
- CW-02: the exclusion's telescope limits were computed from a curve read as B, between A at both ends of the run, and
  saved and exported as A's; the complementary verdicts of a signal study read records the same way;
- CW-03: the DarkCast regression needed the PDG's R-ratio file (``tests/orchestrator/test_cv_recheck.py``);
- CW-04: the cost of reading records was measured at one alias of the shared reader, missing the scan's.
"""
from __future__ import annotations

import copy
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from adroit.constraints import capture, database, review_identity
from adroit.constraints import searches as cs
from adroit.constraints import verdicts as complementary
from adroit.constraints.review_identity import version
from adroit.core.dm_state import DarkMatterParticle, InteractionModel, OperatorCoefficient
from adroit.evidence import build, runtime
from adroit.orchestrator import exclusion, studies, study_headline
from adroit.parameter_space import scan
from tests.orchestrator.test_cu_recheck import _scratch

ICECUBE = scan.ICECUBE
NOT_AN_ID = "not an id"


# --- CW-01 ------------------------------------------------------------------------------------------------------

def _malformed(original: bytes, where: str = "verdict") -> bytes:
    """``original`` with a resting claim's records set to ``[{}]`` (the auditor's damage), padded to the same length."""
    data = json.loads(original)
    claim = data["verdict"]["crossings"][0] if where == "verdict" else data["thermal"][0]
    claim["evaluation"]["records"] = [{}]
    bad = json.dumps(data).encode()
    assert len(bad) <= len(original)
    return bad + b" " * (len(original) - len(bad))


def _put(path, how: str):
    """Writing ``path`` as the auditor did: renamed over it, or rewritten in place; its size and modification time kept."""
    stat = path.stat()

    def put(content: bytes) -> None:
        if how == "replaced":
            fresh = path.with_name(path.name + ".new")
            fresh.write_bytes(content)
            os.replace(fresh, path)
        else:
            path.write_bytes(content)
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert (path.stat().st_size, path.stat().st_mtime_ns) == (stat.st_size, stat.st_mtime_ns)
    return put


TABLES = [pytest.param(True, marks=pytest.mark.needs("eos"), id="certified (the tables)"),
          pytest.param(False, id="viable pending (no tables)")]


def _toy_study(root, monkeypatch, tables: bool):
    """A Track 1 study written as the workbench writes one (``test_certification_journey._saved_study``): with the
    tables, VIABLE and certified; without, VIABLE PENDING."""
    from tests.ui.acceptance.test_certification_journey import _saved_study
    return _saved_study(root, monkeypatch, tables=tables, between=(5.0, 6.0))


@pytest.mark.eos_band
@pytest.mark.parametrize("tables", TABLES)
@pytest.mark.parametrize("how", ["replaced", "rewritten in place"])
def test_a_malformed_replacement_keeping_size_and_modification_time_is_damage_at_once(tmp_path, monkeypatch, how,
                                                                                       tables):
    """CW-01: a Track 1 study's headline read once (warm). Its result replaced by malformed bytes of the same length,
    modification time kept: the headline, Studies' facts, the typed loader and the export each refuse it at once,
    naming the field, with no badge and no certification; restored, the headline is as it was."""
    from adroit.evidence.archive import export_run
    from adroit.evidence.results import load_result
    from adroit.orchestrator import annotations
    root = tmp_path / "runs"
    folder = _toy_study(root, monkeypatch, tables)
    result = folder / "result.json"
    original = result.read_bytes()
    before = study_headline.headline_of(folder)
    assert before.words.startswith("VIABLE") and before.certification and not before.damage
    assert (before.certification == "certified") is tables
    put = _put(result, how)
    put(_malformed(original))
    after = study_headline.headline_of(folder)
    assert (after.words, after.level, after.certification) == ("", "", "") and NOT_AN_ID in after.damage
    facts = annotations.facts(root, studies.load(folder))
    assert (facts.badge, facts.certification) == ("", "") and NOT_AN_ID in facts.damage
    with pytest.raises(ValueError, match=NOT_AN_ID):
        load_result(result)
    with pytest.raises(ValueError, match=NOT_AN_ID):
        export_run(folder, tmp_path / "bundle.zip")
    put(original)
    assert study_headline.headline_of(folder) == before


@pytest.mark.needs("eos")
def test_the_auditors_single_idea_replacement_reads_as_damaged_while_warm(tmp_path):
    """CW-01, the auditor's own case: a single-idea study's ``thermal[0].evaluation.records`` set to ``[{}]``, renamed over
    the result with its size and modification time kept, after the history had read it."""
    from tests.orchestrator import test_single_idea_eos as fixture
    folder = tmp_path / "study"
    folder.mkdir()
    result = folder / "result.json"
    result.write_text(fixture._study(tmp_path / "work", excluded_above=1000).model_dump_json(indent=1))
    studies.record(folder, "single_idea", "the auditor's single-idea study")
    before = study_headline.headline_of(folder)
    assert before.words and not before.damage
    _put(result, "replaced")(_malformed(result.read_bytes(), "thermal"))
    after = study_headline.headline_of(folder)
    assert not after.words and NOT_AN_ID in after.damage


def test_the_validation_is_kept_by_the_bytes_not_the_file(monkeypatch):
    """CW-01: a result's validation is kept by its bytes and its kind: the same bytes are validated once, other bytes
    of the same length again, whatever file they came from."""
    calls: list[bytes] = []
    monkeypatch.setattr(study_headline, "_unlike", lambda content, kind: calls.append(content) or "")
    monkeypatch.setattr(study_headline, "_VALIDATED", {})
    one, other = b'{"a": 1}', b'{"a": 2}'
    for content in (one, one, other, one):
        study_headline.unlike(content, "track1")
    assert calls == [one, other]


# --- CW-02 ------------------------------------------------------------------------------------------------------

def _icecube(tmp_path, monkeypatch):
    """A scratch IceCube SD record, unverified and enabled, its data A in the test's folder; B is A's curves × 100
    (the auditor's control). Returns (path, record, the database reading it, A, B, the bb limit at 100 GeV)."""
    data = copy.deepcopy(database.data(ICECUBE))
    monkeypatch.setattr(review_identity, "PROJECT_ROOT", tmp_path)
    path, record, reading = _scratch(ICECUBE, tmp_path, data)
    a = path.read_bytes()
    limit = database.interpolate_limit(data["limits"]["SD_proton"]["limits_cm2"]["bb"], 100)
    for panel in data["limits"].values():
        for curve in panel["limits_cm2"].values():
            for pair in curve:
                pair[1] *= 100
    return path, record, reading, a, yaml.safe_dump(data).encode(), limit


def _linear_capture(monkeypatch, limit: float) -> None:
    """Solar capture alone replaced, as in the auditor's control: the model's rate twice the bb limit at 100 GeV, the
    reference's rate its cross-section."""
    monkeypatch.setattr(capture, "available", lambda: True)
    monkeypatch.setattr(capture, "capture_rate", lambda p, i, *a, **k: i if isinstance(i, float) else 2 * limit)
    monkeypatch.setattr(complementary, "_reference", lambda kind, sigma, m: sigma)


def _request() -> exclusion.ExclusionRequest:
    interaction = InteractionModel(name="CW-02", layer="nonrelativistic",
                                   coefficients=[OperatorCoefficient(operator=4, proton=1, neutron=0)])
    return exclusion.ExclusionRequest(bespoke={"100": interaction}, masses_gev=[100.], modules=["no-detector"],
                                      unverified_records=True, telescopes=True, name="CW-02 telescope provenance")


@pytest.mark.parametrize("case", ["A throughout", "B during the read", "B throughout the run"])
def test_telescope_limits_keep_the_version_they_read_through_save_and_export(tmp_path, monkeypatch, case):
    """CW-02, the auditor's case through ``exclusion.run``, the evidence capture, ``build.save``, the export and its
    verification; solar capture alone is a fixture. Read as A throughout, the limits are bound to A and the context is
    captured. Read as B, while the run's evidence names A at both ends (B during the read alone, or from the start of
    the calculation to its end): the limits are B's, never relabelled; the result keeps B's version, or none where A
    and B were both read (its report then says so), and its evidence and the exported bundle say the provenance is not
    certified."""
    from adroit.evidence.archive import export_run, verify_bundle
    path, record, reading, a, b, limit = _icecube(tmp_path, monkeypatch)
    _linear_capture(monkeypatch, limit)
    real = database.data

    def during_the_read(name):
        if name != ICECUBE:
            return real(name)
        path.write_bytes(b)
        try:
            return real(name)
        finally:
            path.write_bytes(a)
    request = _request()
    with reading, patch.object(database, "usable", lambda *args, **kwargs: [record]):
        version_a = version(record)
        path.write_bytes(b)
        version_b = version(record)
        path.write_bytes(a)
        context = runtime.capture_request(request, experiments=False)
        if case == "B during the read":
            with patch.object(database, "data", during_the_read):
                result = exclusion.run(request)
        elif case == "B throughout the run":
            path.write_bytes(b)
            result = exclusion.run(request)
            path.write_bytes(a)
        else:
            result = exclusion.run(request)
        folder = tmp_path / "study"
        folder.mkdir()
        (folder / "result.json").write_text(result.model_dump_json(indent=1))
        envelope = build.save(folder / "result.json", "exclusion", context=context)
        studies.record(folder, "exclusion", "CW-02")
        export_run(folder, tmp_path / "bundle.zip")
        bundle = verify_bundle(tmp_path / "bundle.zip")
    mu = {t.channel: t.mu_up[0] for t in result.telescopes}
    assert result.skipped and not result.per_module
    if case == "A throughout":
        assert mu["bb"] == pytest.approx(0.5 ** .5)
        assert envelope.context.origin == "captured" and not envelope.warnings
        assert bundle.nodes[0].provenance == "captured"
        assert {t.record_version for t in result.telescopes} == {version_a}
        assert "is not known" not in exclusion.report(result)
        return
    assert mu["bb"] == pytest.approx(50 ** .5)                     # B's numbers, as computed
    assert envelope.context.origin == "changed_during_run" and envelope.warnings
    assert any(ICECUBE in note for note in envelope.context.notes)
    assert bundle.valid and bundle.nodes[0].provenance == "changed_during_run"
    assert {t.record_version for t in result.telescopes} == ({""} if case == "B during the read" else {version_b})
    unknown = f"Which version of {ICECUBE} these limits were computed from is not known"
    assert (unknown in exclusion.report(result)) is (case == "B during the read")   # else B's version, kept


def test_a_version_read_otherwise_than_the_run_sources_name_leaves_the_context_changed(tmp_path, monkeypatch):
    """CW-02, the reconciliation alone: a record read in one version that is not the library's (B read, A at both
    ends), or in two (""), changes the captured context, naming the record; the version the library holds keeps it."""
    path, record, reading, a, b, _ = _icecube(tmp_path, monkeypatch)
    with reading:
        version_a = version(record)
        path.write_bytes(b)
        version_b = version(record)
        path.write_bytes(a)
        context = runtime.capture_request(_request(), experiments=False)
        assert runtime.finish(context, {ICECUBE: version_a}).origin == "captured"
        for held in (version_b, ""):
            finished = runtime.finish(context, {ICECUBE: held})
            assert finished.origin == "changed_during_run"
            assert any(ICECUBE in note and "provenance cannot certify" in note for note in finished.notes)
        assert runtime.finish(context).origin == "captured"


def test_complementary_verdicts_keep_the_version_of_each_record_they_read(tmp_path, monkeypatch):
    """CW-02, the analogous producer: a signal study's complementary verdicts (``verdicts.judged``) on the auditor's
    interleaving. Read as A, the telescope verdict's record is kept in A's version; read as B during the read alone,
    its version is not known ("")."""
    path, record, reading, a, b, limit = _icecube(tmp_path, monkeypatch)
    _linear_capture(monkeypatch, limit)
    interaction = InteractionModel(name="CW-02", layer="nonrelativistic",
                                   coefficients=[OperatorCoefficient(operator=4, proton=1, neutron=0)])
    candidate = complementary.Candidate(label="CW-02", particle=DarkMatterParticle(mass_gev=100.),
                                        interaction=interaction)
    real = database.data

    def during_the_read(name):
        if name != ICECUBE:
            return real(name)
        path.write_bytes(b)
        try:
            return real(name)
        finally:
            path.write_bytes(a)
    with reading, patch.object(database, "usable", lambda *args, **kwargs: [record]):
        rows, read = complementary.judged(candidate, include_unverified=True)
        assert [r.constraint_id for r in rows] == [ICECUBE] and read == {ICECUBE: version(record)}
        with patch.object(database, "data", during_the_read):
            raced, read = complementary.judged(candidate, include_unverified=True)
    assert read == {ICECUBE: ""} and raced[0].native_excluded is False      # B's curve: a hundred times weaker


def test_records_read_from_a_result_join_its_parts():
    """CW-02: the versions a result keeps, joined over its parts (each telescope channel; each signal candidate): one
    record in two versions across them is not known; a result saved before keeps none."""
    from adroit.evidence.results import records_read
    rows = [SimpleNamespace(record_id=ICECUBE, record_version="a"), SimpleNamespace(record_id=ICECUBE,
                                                                                    record_version="a")]
    assert records_read("exclusion", SimpleNamespace(telescopes=rows)) == {ICECUBE: "a"}
    rows[1].record_version = "b"
    assert records_read("exclusion", SimpleNamespace(telescopes=rows)) == {ICECUBE: ""}
    legacy = [SimpleNamespace(record_id=ICECUBE, record_version=None)]
    assert records_read("lagrangian", SimpleNamespace(exclusion=SimpleNamespace(telescopes=legacy))) == {}
    assert records_read("lagrangian", SimpleNamespace(exclusion=None)) == {}
    signal = SimpleNamespace(verdict_records={"x": {ICECUBE: "a", "planck-2018-omega": "p"}, "y": {ICECUBE: "b"}})
    assert records_read("signal", signal) == {ICECUBE: "", "planck-2018-omega": "p"}
    assert records_read("track1", SimpleNamespace()) == {}


def test_a_result_saved_before_keeps_its_bytes_and_its_evidence():
    """CW-02: a telescope row without a version (a result saved before) is written as it was, so its saved evidence,
    whose summary copies the rows, still matches it."""
    row = exclusion.TelescopeLimits(record_id=ICECUBE, channel="bb", masses_gev=[100.], mu_up=[1.], assumptions=[],
                                    verified=False)
    assert "record_version" not in row.model_dump(mode="json")
    assert exclusion.TelescopeLimits.model_validate(row.model_dump(mode="json")).record_version is None


# --- CW-04 ------------------------------------------------------------------------------------------------------

def test_the_scans_curve_reads_are_counted_at_the_shared_reader(monkeypatch):
    """CW-04: the scan reads its Fermi-LAT and IceCube curves through an alias of the shared reader
    (``scan.s_bundled``), which instrumenting ``searches._bundled`` misses; ``review_identity.snapshot``, which every
    alias reaches, counts both."""
    seen: list[str] = []
    real = review_identity.snapshot
    monkeypatch.setattr(review_identity, "snapshot", lambda record: seen.append(record.id) or real(record))
    calls = []
    monkeypatch.setattr(cs, "_bundled", lambda rid: calls.append(rid))           # the alias is not this
    scan._fermi_limits()
    scan._icecube_limits()
    assert seen == [scan.FERMI, ICECUBE] and calls == []

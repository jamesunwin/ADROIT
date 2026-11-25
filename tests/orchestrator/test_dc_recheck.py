"""The auditor's DB/VI recheck (2026-11-03), DC-01 to DC-06: what the VI repairs held at one boundary was joined to another
read, or lost, at the next. DC-01: the history's row, ``adroit studies`` and the pickers of saved studies had named B's
result by A's title, and a study page holding A had shown a later run's cost as A's. DC-02: a promotion exported and
then reviewed had shown no tasks, and not that its child could not be reviewed. DC-03: a native fit resumed part way
had been dated from the restart, and a resume's dates had been read again from the checkpoint, after its artifact was
restored. DC-04: the input-update card's reanalysis had required the result alone, not the evidence the card showed.
DC-05: a promotion's references download had left out its valid parent record as another version. DC-06: a bundle
replaced between its hash and its reading had verified as A's archive with B's decisions. Each result here is a typed
saved result written by the production writers; nothing is calculated."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from adroit.evidence import archive, build, exports
from adroit.orchestrator import accounting, studies
from adroit.ui import engine
from tests.orchestrator.test_vi_audit import _context, _evidence, _promotion, publish, versions


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- DC-01: one record, read with its result, through every list and its cost --------------------------------------


def test_a_study_record_names_the_run_that_published_it(tmp_path, monkeypatch):
    """DC-01: a study record written in a workbench run's own folder names that run's attempt; one written elsewhere
    (a child the run records), or outside a run, names none."""
    folder = tmp_path / "study"
    a, _ = versions(folder)
    monkeypatch.setenv("ADROIT_JOB_FOLDER", str(folder))
    monkeypatch.setenv("ADROIT_JOB_ATTEMPT", "attempt-a")
    publish(folder, a, "A")
    assert studies.load(folder).attempt == "attempt-a"
    bundle = tmp_path / "out.zip"                           # a record naming its run exports, and verifies, as itself
    archive.export_run(folder / "result.json", bundle)
    with zipfile.ZipFile(bundle) as z:
        assert json.loads(z.read("studies/n0/study.json"))["attempt"] == "attempt-a"
    assert archive.verify_bundle(bundle).valid
    child, _ = versions(folder / "children" / "c")
    publish(folder / "children" / "c", child, "child")
    assert studies.load(folder / "children" / "c").attempt == ""
    monkeypatch.delenv("ADROIT_JOB_FOLDER")
    publish(folder, a, "A")
    assert studies.load(folder).attempt == ""


def test_a_launch_has_an_attempt_that_its_resume_keeps_and_its_run_is_told(tmp_path, monkeypatch):
    """DC-01: each launch has its own attempt; a resume continues it (one from before is given one); the runner tells
    its command which attempt it is (ADROIT_JOB_ATTEMPT), beside its folder."""
    import subprocess
    from types import SimpleNamespace
    from adroit.ui import runner
    first = engine.launch(["signal", "--experiment", "A"], tmp_path / "a", "a", popen=lambda *a, **k: SimpleNamespace(
        pid=101))
    second = engine.launch(["signal", "--experiment", "B"], tmp_path / "b", "b", popen=lambda *a, **k: SimpleNamespace(
        pid=102))
    assert first.attempt and second.attempt and first.attempt != second.attempt
    for folder, attempt in ((tmp_path / "t", "kept"), (tmp_path / "old", "")):
        engine.save(engine.Job(title="t", kind="track1", command=["track1", "x.yaml"], folder=str(folder),
                               status="cancelled", attempt=attempt))
        (folder / ".track1-checkpoint").mkdir()
        (folder / ".track1-checkpoint" / "manifest.json").write_text("{}")
        resumed = engine.resume(folder, popen=lambda *a, **k: SimpleNamespace(pid=103))
        assert resumed.attempt == attempt if attempt else len(resumed.attempt) == 32
    seen = {}

    class Child:
        pid = 0

        def __init__(self, args, **kwargs):
            seen.update(kwargs["env"])

        def wait(self):
            return 0

        def terminate(self):
            pass
    monkeypatch.setattr(subprocess, "Popen", Child)
    job = engine.load(tmp_path / "a")
    runner.run(tmp_path / "a", engine.command_sha256(job.command))
    assert seen["ADROIT_JOB_ATTEMPT"] == first.attempt
    assert seen["ADROIT_JOB_FOLDER"] == str((tmp_path / "a").resolve())


def _run(folder: Path, attempt: str, dollars: float) -> None:
    """A finished paid workbench run in ``folder`` (the auditor's, simulated: no request is sent), its attempt ``attempt``,
    whose own ledger settles ``dollars``."""
    engine.save(engine.Job(title="a run", kind="idea", command=["idea", "--text", "SIMULATED", "--budget", "10"],
                           folder=str(folder), status="completed", returncode=0, attempt=attempt))
    (folder / "paid.jsonl").write_text(
        json.dumps({"id": "b", "state": "reserved", "provider": "SIMULATED", "model": "fixture",
                    "reserved_usd": 10}) + "\n" + json.dumps({"id": "b", "state": "settled", "cost_usd": dollars}) + "\n")


@pytest.mark.parametrize("case", ["its own run", "a later run", "published outside a run", "a record written before"])
def test_a_study_s_cost_is_the_run_its_record_names(tmp_path, monkeypatch, case):
    """DC-01, the auditor's cost case: the run recorded in a study's folder is read as the study's cost only where the study's
    record names it; a later run there (another attempt, or any run beside a record published outside one) is not the
    study's, and its record's own dollars are shown, saying so. A record written before records named their run is read
    as found."""
    folder = tmp_path / "study"
    a, _ = versions(folder)
    if case == "a record written before":
        publish(folder, a, "A", 1.25)
        studies.save(studies.load(folder).model_copy(update={"result_sha256": ""}))
    elif case == "published outside a run":
        publish(folder, a, "A", 1.25)
    else:
        monkeypatch.setenv("ADROIT_JOB_FOLDER", str(folder))
        monkeypatch.setenv("ADROIT_JOB_ATTEMPT", "attempt-a")
        publish(folder, a, "A", 1.25)
        monkeypatch.delenv("ADROIT_JOB_FOLDER")
    _run(folder, "attempt-a" if case == "its own run" else "attempt-b", 9.5)
    s = studies.load(folder)
    c = accounting.study_cost(folder, s.cost_usd, studies.publisher(s))
    from adroit.ui import pages
    from adroit.orchestrator.study_headline import held
    if case in ("its own run", "a record written before"):
        assert c.run_usd == pytest.approx(9.5) and not c.other_run
        assert "$9.50" in pages.study_cost(held(folder)) and "$9.50" in pages.list_cost(held(folder))
    else:
        assert c.run_usd == pytest.approx(1.25) and c.other_run
        assert "$9.50" not in pages.study_cost(held(folder)) and "is not the one that published" in pages.study_cost(held(folder))
        assert pages.list_cost(held(folder)) == "$1.25 settled (its study record's; the run in its folder is another)"


def _mismatched(folder: Path) -> None:
    """The auditor's persistent mismatch: A's record written back over B's publication."""
    a, b = versions(folder)
    publish(folder, a, "A", 1.25)
    record = studies.load(folder)
    publish(folder, b, "B", 9.5)
    studies.save(record)


@pytest.mark.parametrize("mismatched", [False, True], ids=["stable", "a record of another version"])
def test_the_studies_command_and_the_pickers_name_a_study_by_the_record_of_its_result(tmp_path, mismatched):
    """DC-01, the auditor's command and picker case: ``adroit studies``, the Track 1 picker and the reanalysis picker name a
    study by its record read with its result; a record of another version is named so, without its title, date or
    cost, never offered as the title of the result now saved."""
    from adroit.orchestrator.cli import app
    from adroit.ui import reanalysis, wizards
    root = tmp_path / "runs"
    if mismatched:
        _mismatched(root / "study")
    else:
        a, _ = versions(root / "study")
        publish(root / "study", a, "A", 1.25)
    shown = CliRunner().invoke(app, ["studies", str(root)])
    assert shown.exit_code == 0, shown.output
    with patch("adroit.ui.model_library.options", return_value={}):
        offered = reanalysis._sources(root)
    track1 = wizards._track1_studies(root)
    if mismatched:
        assert "A study" not in shown.output and "$1.25" not in shown.output
        assert "describes another version of its result): its date and cost are not shown" in shown.output
        assert list(track1.values()) == ["study (its study record describes another version of its result)"]
        assert list(offered.values()) == ["study: study (its study record describes another version of its result)"]
    else:
        assert "A study" in shown.output and "$1.25" in shown.output
        assert list(track1.values()) == ["A study"] and list(offered.values()) == ["study: A study"]


# --- DC-02: a bundle's review keeps what its export could not follow -----------------------------------------------


@pytest.mark.parametrize("case", ["child replaced", "parent replaced", "child absent", "no digests recorded"])
def test_a_bundle_s_review_says_what_its_export_could_not_follow(tmp_path, case):
    """DC-02, the auditor's case: a promotion whose child (or parent) is replaced, or whose child is no longer saved, exported
    and verified, then reviewed as the bundle: its queue, its packet and ``adroit records queue`` name the edge not
    followed and that its tasks are not shown, as the file's review does; a promotion recording no digests is reviewed
    as found, saying so, in both."""
    import shutil
    from adroit.constraints.review_packets import packet_for
    from adroit.constraints.review_queue import build_queue, load_selected
    from adroit.orchestrator.cli import app
    path, b, parent = _promotion(tmp_path / "graph", recorded=case != "no digests recorded")
    if case == "child replaced":
        publish(tmp_path / "graph" / "child", b, "B child")
    elif case == "parent replaced":
        other = parent.model_copy(update={"max_local_z": 1.0})
        build.publish(path.parent / "result.json", other.model_dump_json().encode(), other, lambda e: "Parent B",
                      workflow="signal")
    elif case == "child absent":
        shutil.rmtree(tmp_path / "graph" / "child")
    bundle = tmp_path / "out.zip"
    archive.export_run(path, bundle)
    assert archive.verify_bundle(bundle).valid
    direct, packed = build_queue(load_selected(path)), build_queue(load_selected(bundle))
    if case == "no digests recorded":
        for text in ("records no digest of its children's results", "records no digest of the result it was promoted"):
            assert any(text in w for w in direct.warnings) and any(w.startswith("bundle: ") and text in w
                                                                   for w in packed.warnings)
        return
    what = "the parent result" if case == "parent replaced" else "the study of fixture for c"
    named = "now saved is another version" if "replaced" in case else "is not saved"
    assert any(what in w and named in w and "its review tasks are not shown" in w for w in direct.warnings)
    edge = [w for w in packed.warnings if what in w and named in w]
    assert edge and all(w.endswith("not reviewed: its review tasks are not shown") for w in edge)
    assert set(packed.selected_results) == set(direct.selected_results)
    selections = load_selected(bundle)
    packet = packet_for("atlas-2301.10731-hinv", selections[0], None, selections)
    assert any(what in w and named in w for w in packet.warnings)
    shown = CliRunner().invoke(app, ["records", "queue", "--run", str(bundle)])
    assert shown.exit_code == 0 and "its review tasks are not shown" in shown.output and what in shown.output


# --- DC-03: a resume's dates, as its run holds them ----------------------------------------------------------------


def _native(tmp_path: Path, complete: bool = True):
    from adroit.orchestrator import native_fit
    from adroit.parameter_space import simplified
    from tests.orchestrator.test_db_recheck import _native_fit
    a, b = _native_fit(tmp_path)
    a.complete = complete
    request = native_fit.NativeFitRequest(spec=simplified.model("vector", 60, 125), masses_gev=[60], settings=a.settings)
    return request, a, b


def _resume_native(request, folder: Path, joint):
    from adroit.evidence import runtime
    from adroit.orchestrator import native_fit, track1_identity
    from adroit.parameter_space import native_joint
    with patch.object(track1_identity, "dependencies", return_value={}), \
            patch.object(runtime, "capture_request", return_value=_context(3)), \
            patch.object(native_joint, "run", joint), patch.object(runtime, "finish", side_effect=lambda c, **k: c):
        return native_fit.run(request, folder, resume=True)


def test_a_native_fit_resumed_part_way_is_dated_from_its_first_start(tmp_path):
    """DC-03, the auditor's case: a native fit whose checkpoint's first run started on 1 November, resumed on 3 November, its
    result incomplete (not saved as finished): published as started on 1 November, never the restart's date."""
    from adroit.core.checkpoint import Checkpoint
    request, a, _ = _native(tmp_path, complete=False)
    folder = tmp_path / "native"
    folder.mkdir()
    Checkpoint(folder, request.model_dump(mode="json"), {}, False, {"calculation_started_at": "2026-11-01T01:00:00Z"})
    result = _resume_native(request, folder, lambda *args, **kwargs: a)
    assert not result.complete
    assert build.read_saved(folder / "result.json").envelope.context.calculation_started_at == "2026-11-01T01:00:00Z"


def _replaced_after_load(b, phase: str, key: str):
    """``Checkpoint.load``, after which a valid other artifact ``b``, dated 2 November, replaces the one it loaded
    (the auditor's valid swap)."""
    from adroit.core.checkpoint import Checkpoint
    original, fired = Checkpoint.load, []

    def load(self, at, name, model):
        found = original(self, at, name, model)
        if (at, name) == (phase, key) and found is not None and not fired:
            fired.append(True)
            Checkpoint(self.folder, self.manifest.inputs, self.manifest.dependencies, True).save(
                at, name, b, dates=("2026-11-02T01:00:00Z", "2026-11-02T01:01:00Z"))
        return found
    return patch.object(Checkpoint, "load", load)


def test_a_native_checkpoint_replaced_after_its_restore_keeps_its_own_dates(tmp_path):
    """DC-03, the auditor's valid swap: checkpoint A (q0 = 2, 1 November) restored, then replaced by a valid checkpoint B (q0
    = 99, 2 November): A is published with A's dates, of the read that restored it, never B's or the restart's."""
    from adroit.core.checkpoint import Checkpoint

    def forbidden(*args, **kwargs):
        raise AssertionError("a resume must not calculate")
    request, a, b = _native(tmp_path)
    folder = tmp_path / "native"
    folder.mkdir()
    Checkpoint(folder, request.model_dump(mode="json"), {}, False).save(
        "finished", "native", a, dates=("2026-11-01T01:00:00Z", "2026-11-01T01:01:00Z"))
    with _replaced_after_load(b, "finished", "native"):
        _resume_native(request, folder, forbidden)
    saved = build.read_saved(folder / "result.json")
    assert saved.result.observed_max_q0 == 2.0
    context = saved.envelope.context
    assert (context.calculation_started_at, context.calculation_completed_at) == ("2026-11-01T01:00:00Z",
                                                                                 "2026-11-01T01:01:00Z")


def test_a_track1_checkpoint_replaced_after_its_restore_keeps_its_own_dates(tmp_path):
    """DC-03 at Track 1's resume: the finished checkpoint A restored, then replaced by a valid B dated 2 November: A is
    published with A's dates."""
    from adroit.core.checkpoint import Checkpoint
    from adroit.evidence import runtime
    from adroit.orchestrator import runs, track1, track1_identity

    def forbidden(*args, **kwargs):
        raise AssertionError("a resume must not calculate")
    folder = tmp_path / "t1"
    a, b = versions(folder)
    request = a.request.model_copy(update={"halo": "published", "propagation": "conservative", "workers": 1})
    a.request, a.fixed = request, a.scan.request.fixed
    b.request, b.fixed = request, b.scan.request.fixed
    checkpoint = Checkpoint(folder, request.model_dump(mode="json"), {}, False, {})
    checkpoint.save("finished", "result", a, dates=("2026-11-01T01:00:00Z", "2026-11-01T01:01:00Z"))
    checkpoint.save("finished", "artifacts", track1._Artifacts(hashes={}, drawn=True))
    with _replaced_after_load(b, "finished", "result"), patch.object(track1_identity, "dependencies", return_value={}), \
            patch.object(runs, "capture_request", return_value=_context(3)), patch.object(track1, "_run", forbidden), \
            patch.object(runtime, "finish", side_effect=lambda c, **k: c):
        runs.track1(request, folder=folder, resume=True)
    saved = build.read_saved(folder / "result.json")
    assert saved.result.scan.points[0].point.m_chi == 50
    assert saved.envelope.context.calculation_started_at == "2026-11-01T01:00:00Z"


def test_dates_written_into_a_checkpoint_after_its_restore_are_not_taken(tmp_path):
    """DC-03, the auditor's damaged artifact: A restored, then its file's payload and dates replaced by B's, A's stored digest
    left: the dates the run holds are A's, of the read that validated it; a load now refuses the file."""
    from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
    from adroit.orchestrator import runs
    folder = tmp_path / "c"
    a, b = versions(folder)
    checkpoint = Checkpoint(folder, {}, {})
    checkpoint.save("finished", "result", a, dates=("2026-11-01T01:00:00Z", "2026-11-01T01:01:00Z"))
    resumed = Checkpoint(folder, {}, {}, True)
    held = resumed.load("finished", "result", type(a))
    artifact = folder / ".track1-checkpoint" / "finished" / "result.json"
    raw = json.loads(artifact.read_text())
    raw.update(payload=b.model_dump(mode="json"), calculation_started_at="2026-11-02T01:00:00Z",
               calculation_completed_at="2026-11-02T01:01:00Z")
    artifact.write_text(json.dumps(raw))
    dated = runs.restored_dates(_context(3), folder, held, resumed.chronology("finished", "result", held))
    assert (dated.calculation_started_at, dated.calculation_completed_at) == ("2026-11-01T01:00:00Z",
                                                                             "2026-11-01T01:01:00Z")
    with pytest.raises(CheckpointMismatch):
        Checkpoint(folder, {}, {}, True).load("finished", "result", type(a))


# --- DC-04: an update card's reanalysis requires the evidence the card read ---------------------------------------


class _Recording:
    """A NiceGUI stand-in that records the links a card makes."""

    def __init__(self):
        self.links = []

    def link(self, text, target, *args, **kwargs):
        self.links.append((text, target))
        return self

    def __getattr__(self, name):
        return lambda *args, **kwargs: self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _card_link(root: Path, update) -> dict[str, str]:
    from urllib.parse import parse_qs, urlparse
    from adroit.ui import revisit
    recording = _Recording()
    with patch.object(revisit, "ui", recording):
        revisit.update_card(root, update)
    target = next(t for text, t in recording.links if text == "Prepare reanalysis with this update")
    return {k: v[0] for k, v in parse_qs(urlparse(target).query).items()}


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "evidence replaced, the result the same"])
def test_an_update_card_s_reanalysis_requires_the_version_the_update_was_read_from(tmp_path, replace):
    """DC-04, the auditor's case: an input update names the result's digest and the evidence's identity it was read from,
    and its card's link requires both: the evidence replaced after the card was made, the result's bytes the same, the
    reanalysis refuses; unchanged, it opens on that evidence."""
    from adroit.evidence.version import Token
    from adroit.library.personal import Catalog
    from adroit.orchestrator import revisit
    from adroit.orchestrator.reanalysis import Reanalysis
    from adroit.orchestrator.revisit import Update
    root = tmp_path / "runs"
    folder = root / "study"
    a, _ = versions(folder)
    held = sha(publish(folder, a, "A"))
    token = _evidence(folder / "result.json", a, "A")
    changed = Update(study="study", title="A study", kind="record", old="A evidence", new="a new record")
    with patch.object(revisit, "_models", return_value=[changed]), patch.object(revisit, "_records", return_value=[]):
        found = revisit.for_study(root, studies.load(folder))
    assert [(u.sha256, u.evidence) for u in found] == [(held, token)]
    query = _card_link(root, found[0])
    assert (query["sha256"], query["evidence"]) == (held, token)
    service = Reanalysis(Catalog(tmp_path / "catalog"))
    if replace:
        _evidence(folder / "result.json", a, "B")
        with pytest.raises(ValueError, match="evidence has changed"):
            service.open(query["source"], token=Token(query["source"], query["sha256"], query["evidence"]))
        return
    draft = service.open(query["source"], token=Token(query["source"], query["sha256"], query["evidence"]))
    assert draft.source_evidence_sha256 == token


def test_the_study_page_s_update_cards_use_the_evidence_the_page_read(tmp_path):
    """DC-04: given the page's version (its evidence read with its result), the updates are of it and name it; the
    evidence is not read again."""
    from adroit.evidence.version import resolve
    from adroit.orchestrator import revisit
    from adroit.orchestrator.revisit import Update
    root = tmp_path / "runs"
    folder = root / "study"
    a, _ = versions(folder)
    publish(folder, a, "A")
    page = resolve(folder)
    _evidence(folder / "result.json", a, "B")                    # replaced after the page read it
    changed = Update(study="study", title="A study", kind="model", old="r1", new="r2")
    with patch.object(revisit, "_models", return_value=[changed]):
        found = revisit.for_study(root, page)
    assert found and {u.evidence for u in found} == {page.identity("evidence")}


# --- DC-05: a promotion's parent record, by one rule --------------------------------------------------------------


def _parent_promotion(root: Path, record: str):
    """A signal parent, its study record (``record``: "bound", "another version", "written before" or "none") and a
    promotion recording the parent's digest, in the parent's folder."""
    from adroit.orchestrator.promote import Child, Promotion
    path, _, _ = _promotion(root)
    parent = sha((root / "result.json").read_bytes())
    if record == "bound":
        studies.record(root, "signal", "Parent", result_sha256=parent)
    elif record == "another version":
        studies.record(root, "signal", "Parent", result_sha256="0" * 64)
    elif record == "written before":
        studies.record(root, "signal", "Parent")
    promotion = build.read_saved(path).result
    assert isinstance(promotion, Promotion) and isinstance(promotion.children[0], Child)
    return path


@pytest.mark.parametrize("record", ["bound", "another version", "written before", "none"])
def test_a_promotion_s_references_download_checks_its_parent_record_as_its_export_does(tmp_path, record):
    """DC-05, the auditor's case: the record beside a promotion is its parent study's. The references download attaches it
    where it names the parent result the promotion records, as the export does; as found, saying so, where it names
    none; and leaves it out, saying so, where it names another, as the export does."""
    from adroit.ui.exports import files
    path = _parent_promotion(tmp_path / "graph", record)
    found = exports.request(path)
    manifest = archive.export_run(path, tmp_path / "out.zip")
    study_warning = [w for w in manifest.warnings if w.startswith("studies/n0/study.json")]
    note = found.get("study_record.txt", b"").decode()
    if record == "bound":
        assert "study.json" in found and not note and not study_warning
        _, data = files("references", path)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert "study.json" in z.namelist() and "study_record.txt" not in z.namelist()
    elif record == "another version":
        assert "study.json" not in found and "another version of the parent result this promotion records" in note
        assert study_warning and "not exported" in study_warning[0]
    elif record == "written before":
        assert "study.json" in found and "as found" in note and "the parent result this promotion records" in note
        assert study_warning and "exported as found" in study_warning[0]
    else:
        assert "study.json" not in found and not note and not study_warning


# --- DC-06: one read of a bundle ---------------------------------------------------------------------------------


BUNDLES = Path(__file__).parents[1] / "fixtures" / "bundles"


@pytest.mark.parametrize("when", ["after its read", "before its read"])
def test_a_bundle_replaced_while_it_is_verified_is_verified_as_one_archive(tmp_path, when):
    """DC-06, the auditor's case: two untouched exports A and B; A replaced by B after the verifier has read it (or before):
    the digest, the checks and the decisions reconstructed are all A's (or all B's), never A's digest with B's
    decisions, in ``verify_bundle`` and ``adroit evidence verify`` alike."""
    from adroit.core.durable import write_atomic
    from adroit.orchestrator.cli import app
    a = (BUNDLES / "promotion_v1_named_stable_A_dba8e6c.zip").read_bytes()
    b = (BUNDLES / "promotion_v1_named_second_B_dba8e6c.zip").read_bytes()
    path = tmp_path / "selected.zip"
    path.write_bytes(b)
    nodes_b = [n.evidence_identity for n in archive.verify_bundle(path).nodes]
    path.write_bytes(a)
    nodes_a = [n.evidence_identity for n in archive.verify_bundle(path).nodes]
    assert nodes_a != nodes_b
    real = archive.held_bundle

    def held(p):
        if when == "before its read":
            write_atomic(path, b)
        data = real(p)
        if when == "after its read":
            write_atomic(path, b)
        return data
    expected = (sha(a), nodes_a) if when == "after its read" else (sha(b), nodes_b)
    with patch.object(archive, "held_bundle", held):
        found = archive.verify_bundle(path)
    assert found.valid and (found.archive_sha256, [n.evidence_identity for n in found.nodes]) == expected
    path.write_bytes(a)
    with patch.object(archive, "held_bundle", held):
        shown = CliRunner().invoke(app, ["evidence", "verify", str(path)])
    assert shown.exit_code == 0
    reply = json.loads(shown.stdout)
    assert (reply["archive_sha256"], [n["evidence_identity"] for n in reply["nodes"]]) == expected

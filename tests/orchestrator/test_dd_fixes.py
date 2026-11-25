"""The auditor's version-handle audit (the independent audit of 2026-11-04 (version handle), pin f3bb204): DD-01, a reanalysis's lineage
added after publication to whatever its child's folder then held; DD-02, a study's cost checked against its run once,
before that run's ledger and records were read. (DD-03, the matrix's oracle, is repaired in ``tests/version_matrix.py``
and its harnesses.) Every calculation, review and provider is stood in for; nothing is sent, and $0 is spent."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from adroit.evidence import archive
from adroit.evidence.version import resolve
from adroit.orchestrator import accounting, runs, studies
from tests.orchestrator.test_dc_recheck import _run
from tests.orchestrator.test_vi_audit import publish, versions


# --- DD-01: the lineage is in the evidence its child is first published with -----------------------------------

def _reanalysis(tmp: Path, after=None):
    """A reanalysis of a signal study into its child folder, by the production path (its draft, ``runs._write``, its
    check), its calculation, review and catalogue stood in for (the auditor's control); ``after(child)`` once its writer has
    published. (the child's folder, the run's report or its refusal, the parent world)."""
    from adroit.core.evidence import EvidenceContext
    from adroit.evidence import runtime
    from adroit.library.personal import Catalog
    from adroit.orchestrator import signal
    from adroit.orchestrator.reanalysis import Reanalysis
    from tests.evidence.test_version_matrix import _signal_world
    world = _signal_world(tmp)
    service = Reanalysis(Catalog(tmp / "catalog"))
    draft = service.open(str(world.path))
    child, real = world.folder / "child", runs._write

    def write(folder, result, *args, **kw):
        text = real(folder, result, *args, **kw)
        if after is not None and kw.get("published") is not None:
            after(child)
        return text
    with patch.object(service, "preview", return_value={"review_sha256": "simulated-review", "blockers": []}), \
            patch.object(service, "_catalogue_models", side_effect=lambda request, *a: request), \
            patch.object(runtime, "capture_request", return_value=EvidenceContext(notes=["simulated, $0"])), \
            patch.object(signal, "run", return_value=world.a), \
            patch.object(signal, "report", return_value="A computed report"), \
            patch.object(runs, "_write", write):
        try:
            _, text = service.run(draft.reference, child, "simulated-review", confirmed=True, reviewer="SIMULATED")
        except ValueError as error:
            return child, error, world
    return child, text, world


def test_a_reanalysis_s_lineage_is_in_the_evidence_its_child_was_first_published_with(tmp_path):
    """DD-01, the auditor's stable case: the child's evidence carries its lineage from its first publication (no later
    write), its record lists the lineage's file, and its bundle verifies."""
    child, text, world = _reanalysis(tmp_path)
    assert isinstance(text, str) and "A computed report" in text
    found = resolve(child)
    lineage = found.envelope().certificates["reanalysis_lineage"]
    assert lineage == json.loads((child / "reanalysis.json").read_text())
    assert lineage["source_result_sha256"] == world.identities["A"]["result"].pop() and lineage["fresh_run"]
    assert found.record_state == "bound" and "reanalysis.json" in found.study().outputs
    archive.export_run(child, tmp_path / "child.zip")
    assert archive.verify_bundle(tmp_path / "child.zip").valid


def test_a_publication_replacing_the_child_after_its_writer_is_refused_and_given_nothing(tmp_path):
    """DD-01, the auditor's reproducer: a coherent, unrelated B published in the child's folder after the writer published A
    and before the run returned, by a process outside ADROIT's writers (ADROIT's own wait for the reanalysis, or are
    refused: DE-02). The run refuses, naming the result; B is left as B wrote it, its evidence without A's lineage (it
    had acquired it, and its bundle had verified)."""
    from tests import version_matrix as vm
    left = {}

    def replace(child):
        b = resolve(child).typed().model_copy(update={"global_z": 7.0})
        b.request.experiment = "UNRELATED B"
        with vm.outside():
            runs._write(child, b, "B report", "signal", "UNRELATED B study")
        left.update({p.name: p.read_bytes() for p in child.iterdir() if p.is_file()})
    child, error, _ = _reanalysis(tmp_path, after=replace)
    assert isinstance(error, ValueError) and "the new study's result was replaced by another process" in str(error)
    assert {p.name: p.read_bytes() for p in child.iterdir() if p.is_file()} == left
    found = resolve(child)
    assert found.typed().request.experiment == "UNRELATED B"
    assert "reanalysis_lineage" not in found.envelope().certificates


@pytest.mark.parametrize("part", ["evidence", "record"])
def test_a_part_of_the_child_replaced_after_its_writer_is_refused_by_name(tmp_path, part):
    """DD-01, the auditor's evidence-only and record-only changes, by a process outside ADROIT's writers: the run refuses,
    naming the part, and writes nothing."""
    from tests import version_matrix as vm

    def replace(child):
        if part == "evidence":
            vm.mark_evidence(child / "result.json", "B")
        else:
            record = studies.load(child)
            with vm.outside():
                studies.save(record.model_copy(update={"title": "another study's record", "cost_usd": 9.5}))
    child, error, _ = _reanalysis(tmp_path, after=replace)
    assert isinstance(error, ValueError) and f"the new study's {part} was replaced" in str(error)


def test_a_parent_changed_during_the_calculation_publishes_nothing(tmp_path):
    """DD-01: the parent is checked once the calculation is done and before anything of the child is written; a
    parent republished meanwhile refuses with nothing of the child published (the check had come after it)."""
    from adroit.core.evidence import EvidenceContext
    from adroit.evidence import runtime
    from adroit.library.personal import Catalog
    from adroit.orchestrator import signal
    from adroit.orchestrator.reanalysis import Reanalysis
    from tests.evidence.test_version_matrix import _signal_world
    world = _signal_world(tmp_path)
    service = Reanalysis(Catalog(tmp_path / "catalog"))
    draft = service.open(str(world.path))
    child = world.folder / "child"

    def calculate(request):
        world.publish("B")                          # the parent republished during the calculation
        return world.a
    with patch.object(service, "preview", return_value={"review_sha256": "r", "blockers": []}), \
            patch.object(service, "_catalogue_models", side_effect=lambda request, *a: request), \
            patch.object(runtime, "capture_request", return_value=EvidenceContext()), \
            patch.object(signal, "run", side_effect=calculate), \
            patch.object(signal, "report", return_value="A computed report"), \
            pytest.raises(ValueError, match="parent input changed during calculation"):
        service.run(draft.reference, child, "r", confirmed=True, reviewer="SIMULATED")
    assert not (child / "result.json").exists() and not (child / "reanalysis.json").exists()


def test_the_writer_certifies_before_writing_and_names_what_it_wrote(tmp_path):
    """DD-01, the writer's contract (``runs._write``): ``certify`` is given the result's digest before anything is
    written, and what it returns is in the evidence as first published; ``published`` receives the version as
    written, which the folder then resolves to; a refusal from ``certify`` writes nothing (its folder's publication
    lock aside, which holds nothing: DE-02)."""
    folder = tmp_path / "study"
    a, _ = versions(tmp_path / "fixture")
    folder.mkdir()
    seen, published = [], {}

    def certify(digest):
        seen.append((digest, sorted(p.name for p in folder.iterdir())))
        return {"matrix_certificate": {"of": digest}}
    runs._write(folder, a, "# A report\n\nA body\n", "track1", "A study", certify=certify, published=published)
    digest = resolve(folder).result_sha256
    assert seen == [(digest, [".study.lock"])]      # nothing of it written when it certifies, the lock held
    assert resolve(folder).envelope().certificates["matrix_certificate"] == {"of": digest}
    assert published["token"] == resolve(folder, presentation=True).token()
    other = tmp_path / "refused"
    other.mkdir()

    def refuse(_):
        raise ValueError("not certified")
    with pytest.raises(ValueError, match="not certified"):
        runs._write(other, a, "# A\n", "track1", "A", certify=refuse)
    assert [p.name for p in other.iterdir()] == [".study.lock"]


# --- DD-02: a held study's cost is its run's over the whole read ------------------------------------------------

def _a_study(folder: Path, monkeypatch):
    """Study A published by a workbench run, attempt-a, whose own ledger settles $1.25."""
    a, b = versions(folder)
    with monkeypatch.context() as m:
        m.setenv("ADROIT_JOB_FOLDER", str(folder))
        m.setenv("ADROIT_JOB_ATTEMPT", "attempt-a")
        publish(folder, a, "A", 1.25)
    _run(folder, "attempt-a", 1.25)
    return a, b


def _during_cost(folder: Path, write):
    """``write()`` once, inside the cost's read: after its run's record (``job.json``) is read, before the run's ledger
    and records are (the auditor's control: the attempt checked, then the run's records replaced)."""
    real, done = accounting.read_job, []

    def read(where):
        job = real(where)
        if not done and Path(where) == folder:
            done.append(True)
            write()
        return job
    return patch.object(accounting, "read_job", read)


@pytest.mark.parametrize("whole", [False, True], ids=["accounting only", "a whole new publication"])
def test_a_later_run_written_while_a_cost_is_read_is_not_the_study_s(tmp_path, monkeypatch, whole):
    """DD-02, the auditor's reproducer: a page holding A (published by attempt-a, $1.25) reads its cost while a later run,
    attempt-b, writes its record and its $9.50 ledger in the folder (and, ``whole``, publishes B there). The card, the
    Studies line and ``adroit studies`` show A's record's $1.25, saying the run in its folder is another; never $9.50
    as A's, nor a conflict between A's records."""
    from adroit.orchestrator.cli import app
    from adroit.ui import pages
    folder = tmp_path / "runs" / "study"
    _, b = _a_study(folder, monkeypatch)
    held = resolve(folder)

    def later():
        if whole:
            with patch.dict(os.environ, {"ADROIT_JOB_FOLDER": str(folder), "ADROIT_JOB_ATTEMPT": "attempt-b"}):
                publish(folder, b, "B", 9.5)
        _run(folder, "attempt-b", 9.5)

    def again():                 # A's run restored, for the next surface's reading
        _a_study(folder, monkeypatch)
        return resolve(folder)
    with _during_cost(folder, later):
        c = accounting.held_cost(held)
    assert c.run_usd == 1.25 and c.other_run and not c.conflicts and "9.50" not in accounting.run_line(c)
    held = again()
    with _during_cost(folder, later):
        card = pages.study_cost(held)
    assert "$1.25" in card and "is not the one that published this study" in card and "$9.50" not in card
    held = again()
    with _during_cost(folder, later):
        line = pages.list_cost(held)
    assert line == "$1.25 settled (its study record's; the run in its folder is another)"
    again()
    with _during_cost(folder, later):
        done = CliRunner().invoke(app, ["studies", str(tmp_path / "runs")])
    assert done.exit_code == 0, done.output
    assert "$1.25 settled (its study record's; the run in its folder is another)" in done.output
    assert "$9.50" not in done.output.split("total:")[0]


def test_the_same_run_settling_more_while_its_cost_is_read_is_the_study_s(tmp_path, monkeypatch):
    """DD-02, what stays: the study's own run (attempt-a) settling another request while its cost is read is that
    run's later settlement, shown as the study's (not another run's)."""
    folder = tmp_path / "runs" / "study"
    _a_study(folder, monkeypatch)
    held = resolve(folder)
    with _during_cost(folder, lambda: _run(folder, "attempt-a", 2.0)):
        c = accounting.held_cost(held)
    assert c.run_usd == 2.0 and not c.other_run


def test_a_held_cost_reads_the_versions_record_not_the_folder_s(tmp_path, monkeypatch):
    """DD-02: the study record whose dollars a cost is checked against is the version's, never the folder's read
    again: a record rewritten after the page's read (another publication's dollars) is not taken as the study's."""
    folder = tmp_path / "runs" / "study"
    _a_study(folder, monkeypatch)
    held = resolve(folder)
    record = studies.load(folder)
    studies.save(record.model_copy(update={"cost_usd": 9.5}))
    c = accounting.held_cost(held)
    assert c.run_usd == 1.25 and not c.conflicts, c

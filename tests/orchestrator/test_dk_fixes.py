"""The auditor's DJ recheck (the independent audit of 2026-11-07 (dj recheck), pin 435259d): DK-01, a session command refused before it
sent anything (its output folder a saved study's) replacing that study's request record with an empty one, outside the
folder's hold, so that its $1.25 read as no request sent; DK-02, a curated record's review prepared from several
readings of its data file, so that a file changed and restored between them exported B's curve or figure beside A's
current signature; DK-04, the N_eff refusal's account of its source's benchmark; DK-05, an export's failure contract.
(DK-03, the point table's columns, is repaired in ``tests/version_matrix.py`` and its harnesses.) The curated records are
read as they are, never signed; the saved studies are the earlier repairs' typed fixtures; no calculation or provider;
the dollars are simulated; $0."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
import yaml

from adroit.core import durable
from adroit.core.durable import INCOMPLETE, publishing
from adroit.orchestrator import preflight
from adroit.orchestrator.model_intake import REQUESTS, RunRequests
from tests.orchestrator import test_de_fixes as de
from tests.orchestrator.test_dj_fixes import A, B, PACKET, review, whose

ROOT = Path(__file__).parents[2]
SESSION = "0" * 32                                  # a session the refused commands never reach
DRAFT_FILES = ("intake.json", "report.md")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree(folder: Path) -> dict[str, str]:
    """Every file under ``folder`` (its publication lock aside), by its path there, and its bytes' digest."""
    return {str(p.relative_to(folder)): sha(p.read_bytes()) for p in sorted(folder.rglob("*"))
            if p.is_file() and p.name != ".study.lock"}


class Requests:
    """A session service as a command's budgeted clients leave it: the requests it reserved (``request_ids``)."""

    def __init__(self, *ids: str) -> None:
        self.ids = list(ids)

    def request_ids(self) -> list[str]:
        return self.ids


# --- DK-01: a command refused before it sends anything writes nothing --------------------------------------------

def _refused(command: str, out: Path) -> list[str]:
    """The auditor's four commands, each given a saved study's folder as its output (``dj_refused_class``)."""
    return {"models step": ["models", "step", SESSION, "--kind", "idea", "--text", "SIMULATED", "--budget", "10"],
            "models paper": ["models", "paper", SESSION, "--equation", "1", "--pages", "1", "--pdf", "absent.pdf",
                             "--budget", "10"],
            "constraints resume": ["constraints", "resume", SESSION, "--budget", "10"],
            "experiments extract": ["experiments", "extract", SESSION, "--budget", "10"]}[command] + ["--out", str(out)]


def _cli(tmp: Path, args: list[str]) -> subprocess.CompletedProcess:
    """The installed command line in a child process, its libraries and runs in the test's folder; no key, no
    network."""
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY") and not k.startswith("ADROIT_JOB")}
    env.update(ADROIT_PROJECTS_DIR=str(tmp / "projects"), ADROIT_RUNS_DIR=str(tmp / "cli runs"))
    return subprocess.run([sys.executable, "-m", "adroit.orchestrator.cli", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=300)


HOLD = """
import sys
from adroit.core.durable import publishing
with publishing(sys.argv[1]):
    print("held", flush=True)
    sys.stdin.readline()
"""


def _held_by_another_process(folder: Path):
    """A child process holding ``folder``'s publication until its input closes: (the process, its release)."""
    process = subprocess.Popen([sys.executable, "-c", HOLD, str(folder)], cwd=ROOT, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, text=True)
    assert process.stdout.readline().strip() == "held"

    def release():
        process.stdin.close()
        process.wait(60)
    return process, release


def _in_process(tmp: Path, args: list[str]) -> subprocess.CompletedProcess:
    """The command line in this process (``typer``'s runner), its libraries and runs in the test's folder: what a
    negative control can restore a defect in."""
    from typer.testing import CliRunner

    from adroit.core.config import get_settings
    from adroit.orchestrator.cli import app
    with patch.dict(os.environ, {"ADROIT_PROJECTS_DIR": str(tmp / "projects"), "ADROIT_RUNS_DIR": str(tmp / "cli runs")}):
        get_settings.cache_clear()
        try:
            done = CliRunner().invoke(app, args)
        finally:
            get_settings.cache_clear()
    return subprocess.CompletedProcess(args, done.exit_code, done.output, "")


COMMANDS = ("models step", "models paper", "constraints resume", "experiments extract")
HELD = ("not held", "held by another process")
WHERE = ("the installed command", "in process")


@pytest.mark.parametrize("where", WHERE)
@pytest.mark.parametrize("held", HELD)
@pytest.mark.parametrize("command", COMMANDS)
def test_a_command_refused_into_a_saved_study_s_folder_changes_nothing(tmp_path, command, held, where):
    """DK-01, the auditor's case: study A, published by the workbench run attempt-a, its request record naming that run's
    settled $1.25. Each of the four session commands given A's folder as its output, from the installed command line,
    with the folder held by another process or not: refused before it sends anything, it writes nothing there, whether
    or not it could reach its session; A's every file is the same byte for byte, and its cost is the same $1.25 on its
    card, in Studies and by ``adroit studies``. Before, each replaced A's request record with an empty one naming no
    run, which the cost then read as no request sent ($0)."""
    folder, _, service, _ = de._study(tmp_path, "receipt")
    before = _tree(folder)
    release = _held_by_another_process(folder)[1] if held != "not held" else (lambda: None)
    try:
        done = (_cli if where == "the installed command" else _in_process)(tmp_path, _refused(command, folder))
    finally:
        release()
    said = " ".join((done.stdout + done.stderr).translate(str.maketrans("│╭╮╰╯─", "      ")).split())
    assert done.returncode != 0 and "holds a saved study (result.json)" in said, done   # its box's frame aside (DL)
    assert _tree(folder) == before
    costs = shown(folder, service)
    assert costs["cost"].run_usd == 1.25 and costs["cost"].none_sent_evidence == "", costs["cost"]
    for surface in ("card", "list", "cli"):
        assert "$1.25" in costs[surface] and "no paid request" not in costs[surface], (surface, costs[surface])


def shown(folder: Path, service) -> dict:
    """The held study's cost as each surface reads it, each a fresh reading: ``held_cost``, its card, its line in
    Studies, ``adroit studies`` (``test_de_fixes``' surfaces), its session's ledger read from ``service``."""
    from typer.testing import CliRunner

    from adroit.evidence.version import resolve
    from adroit.orchestrator import accounting
    from adroit.orchestrator.cli import app
    from adroit.ui import pages
    with patch.object(accounting, "_budgets", return_value=service):
        return {"cost": accounting.held_cost(resolve(folder)), "card": pages.study_cost(resolve(folder)),
                "list": pages.list_cost(resolve(folder)),
                "cli": CliRunner().invoke(app, ["studies", str(folder.parent)]).output}


def test_a_session_export_is_its_request_record_and_its_files_whole(tmp_path):
    """A session command's export, as its writer prepares it: its request record, draft and report, one session's;
    a later export into the folder replaces it whole."""
    out = tmp_path / "out"
    preflight.session_export(out, Requests("r-a"), "session-a", members("session-a"))
    assert _coherent(out) == "session-a"
    assert RunRequests.model_validate_json((out / REQUESTS).read_text()).request_ids == ["r-a"]
    preflight.session_export(out, Requests("r-b"), "session-b", members("session-b"))
    assert _coherent(out) == "session-b" and not durable.interrupted(out)


def test_a_stopped_run_records_its_own_requests_and_no_earlier_draft_beside_them(tmp_path):
    """A run that reserved a request and then stopped records it (its request record), and its folder keeps nothing
    of an earlier export beside it: the draft and report of another session's run are removed, so that the folder's
    record is not read beside a draft that was not that run's (and the folder's record of its exports names this one's
    files, ``durable.RECORD``: DM-03)."""
    out = tmp_path / "out"
    preflight.session_export(out, Requests("r-earlier"), "earlier", {"intake.json": "{}", "report.md": "earlier"})
    preflight.record_requests(out, Requests("r-this"), "this", DRAFT_FILES)
    assert sorted(p.name for p in out.iterdir() if p.name != ".study.lock") == [durable.RECORD, REQUESTS]
    assert RunRequests.model_validate_json((out / REQUESTS).read_text()).request_ids == ["r-this"]


def test_a_run_that_sent_nothing_records_it_only_in_its_own_job_s_folder(tmp_path, monkeypatch):
    """A run refused before it sent anything writes nothing into a folder a person named; in its own workbench job's
    folder, which its runner made for it, it records that it sent nothing (an empty request record naming its run),
    so that its page reads no request sent rather than no record."""
    named = tmp_path / "named"
    named.mkdir()
    (named / "kept.txt").write_text("a person's")
    preflight.record_requests(named, Requests(), "s", DRAFT_FILES)
    assert sorted(p.name for p in named.iterdir()) == ["kept.txt"]
    job = tmp_path / "job"
    job.mkdir()
    monkeypatch.setenv("ADROIT_JOB_FOLDER", str(job))
    monkeypatch.setenv("ADROIT_JOB_ATTEMPT", de.A)
    preflight.record_requests(job, Requests(), "s", DRAFT_FILES)
    assert RunRequests.model_validate_json((job / REQUESTS).read_text()) == RunRequests(
        session_id="s", request_ids=[], attempt=de.A)


SESSION_EXPORT = """
import sys
from pathlib import Path
from adroit.orchestrator import preflight
from tests.orchestrator.test_dk_fixes import Requests, members
print("trying", flush=True)
preflight.session_export(Path(sys.argv[1]), Requests("r-b"), "session-b", members("session-b"))
print("done", flush=True)
"""


def members(session: str) -> dict[str, str]:
    """A session command's export as its writer prepares it: its draft and its report, each naming its session."""
    return {"intake.json": json.dumps({"session_id": session}), "report.md": f"# Model intake draft\n\nSession: {session}"}


def _coherent(out: Path) -> str:
    """The session the folder's request record, draft and report all name; AssertionError where they differ."""
    named = {RunRequests.model_validate_json((out / REQUESTS).read_text()).session_id,
             json.loads((out / "intake.json").read_text())["session_id"],
             (out / "report.md").read_text().rsplit("Session: ", 1)[1].strip()}
    assert len(named) == 1, named
    return named.pop()


@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_a_session_export_and_its_request_record_are_one_export(tmp_path, by):
    """DK-01, the success path: a session command's request record is written with its draft and report, under one
    hold of the folder (``preflight.session_export``), the record first. A's export paused just after its record is
    written; B's (another session's), from another thread or another process, given three seconds: B waits, writing
    nothing, then writes its own whole: the record, draft and report one session's, B's. Before, the record was
    written apart, outside the hold."""
    out, seen = tmp_path / "out", {}
    real = durable.write_atomic

    def b(path):
        if seen or Path(path).name != REQUESTS:
            return
        if by == "another process":
            process = subprocess.Popen([sys.executable, "-c", SESSION_EXPORT, str(out)], cwd=ROOT,
                                       stdout=subprocess.PIPE, text=True)
            assert process.stdout.readline().strip() == "trying"
            try:
                process.wait(3)
            except subprocess.TimeoutExpired:
                pass
            seen["B"] = lambda: process.wait(120)
        else:
            thread = threading.Thread(target=preflight.session_export,
                                      args=(out, Requests("r-b"), "session-b", members("session-b")))
            thread.start()
            thread.join(3)
            seen["B"] = lambda: thread.join(120)
        seen["while A held"] = sorted(p.name for p in out.iterdir() if p.name != ".study.lock")

    def atomic(path, data):
        written = real(path, data)
        b(path)
        return written
    with patch.object(durable, "write_atomic", atomic):
        preflight.session_export(out, Requests("r-a"), "session-a", members("session-a"))
    seen["B"]()
    assert seen["while A held"] == sorted([REQUESTS, INCOMPLETE]), seen["while A held"]
    assert _coherent(out) == "session-b" and not (out / INCOMPLETE).exists()


def test_a_study_published_while_a_stopped_run_waits_refuses_its_record(tmp_path):
    """A race of a successful output and a refused one: a stopped run's record waits for the folder's writer, which
    publishes a study there; the record is then refused under the hold (the folder holds a saved study), nothing of it
    written, and the study is as its writer wrote it. The run says so; its requests stay in its session's ledger."""
    out, started, release = tmp_path / "out", threading.Event(), threading.Event()

    def writer():
        with publishing(out):
            started.set()
            release.wait(30)
            durable.write_atomic(out / "result.json", b"{}")
    thread = threading.Thread(target=writer)
    thread.start()
    started.wait(10)
    said = []
    timer = threading.Timer(1.0, release.set)
    timer.start()
    with patch.object(typer, "echo", lambda line, *a, **k: said.append(line)):
        preflight.record_requests(out, Requests("r-1"), "s", DRAFT_FILES)
    thread.join(30)
    assert sorted(p.name for p in out.iterdir() if p.name != ".study.lock") == ["result.json"]
    assert said and "holds a saved study" in said[0] and "the session ledger keeps every request" in said[0], said


# --- DK-02: a curated review is one reading of its record and data ------------------------------------------------

def scratch_payload(tmp: Path, monkeypatch, record_id: str = A) -> Path:
    """The auditor's scratch payload root: the project root moved to a folder holding a copy of ``record_id``'s data file
    alone, at its own path there, so that a test can change its bytes; the record (and its signature) unchanged.
    Returns the copy."""
    from adroit.constraints import database, review_identity
    from adroit.core import config
    record = database.record(record_id)
    root = tmp / "payload"
    copy = root / record.data_file
    copy.parent.mkdir(parents=True)
    copy.write_bytes((config.PROJECT_ROOT / record.data_file).read_bytes())
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    monkeypatch.setattr(review_identity, "PROJECT_ROOT", root)
    database.data.cache_clear()
    return copy


def scaled(content: bytes, factor: float = 100.0) -> bytes:
    """The auditor's B: the data file with every curve's ordinate multiplied by ``factor``."""
    def walk(value):
        if isinstance(value, list) and value and all(isinstance(p, list) and len(p) == 2 and all(
                isinstance(v, (int, float)) for v in p) for p in value):
            return [[x, y * factor] for x, y in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value
    return yaml.safe_dump(walk(yaml.safe_load(content)), sort_keys=False).encode()


def _while(module, name: str, path: Path, data: bytes, restore: bool = True):
    """``module.name`` patched: the data file ``path`` holds ``data`` while it runs, and its earlier bytes again after
    it (``restore``), whatever it read; the file's own reading (``file_reads``) sees each change."""
    real, kept = getattr(module, name), path.read_bytes()

    def written(content: bytes, stamp: int) -> None:
        path.write_bytes(content)
        os.utime(path, ns=(stamp, stamp))

    def during(*args, **kwargs):
        written(data, 2_000_000_000_000_000_000)
        try:
            return real(*args, **kwargs)
        finally:
            if restore:
                written(kept, 3_000_000_000_000_000_000)
    return patch.object(module, name, during)


def _packet(folder: Path) -> dict:
    """What a review packet's JSON says of the record it read: its digests, its signature state and version, its
    curves."""
    packet = json.loads((folder / "record_review.json").read_text())
    binding = packet["current"]["verification_binding"]
    return {"payload": packet["current"]["payload_sha256"], "data": packet["current"]["data_sha256"],
            "state": binding["state"], "version": binding.get("current_sha256"), "curves": packet["current_curves"]}


BOUNDARIES = {"the figure": "figure", "the packet's curves": "curves"}      # the auditor's two interleavings (dj_record_aba)


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_a_review_export_is_one_reading_of_its_record_and_data(tmp_path, monkeypatch, boundary):
    """DK-02, the auditor's A→B→A: record A (the owner's signed Fermi-LAT dwarfs), its data file B (every ordinate a hundred
    times A's) while ``boundary`` is prepared, A's very bytes before and after. The export is A's whole: its packet's
    digests, current signature, version and curves, its report and its figure, each the same as A's exported alone;
    never B's figure or curves beside A's signature. Before, the figure, or the packet's curves, were B's."""
    from adroit.constraints import review as curated
    path = scratch_payload(tmp_path, monkeypatch)
    a = path.read_bytes()
    review(A, tmp_path / "A alone")
    path.write_bytes(scaled(a))
    review(A, tmp_path / "B alone")
    path.write_bytes(a)
    alone = {label: (_packet(tmp_path / f"{label} alone"), whose(tmp_path / f"{label} alone")) for label in "AB"}
    assert alone["A"][1][2] != alone["B"][1][2] and alone["A"][0]["curves"] != alone["B"][0]["curves"]
    out = tmp_path / "export"
    with _while(curated, BOUNDARIES[boundary], path, scaled(a)):
        review(A, out)
    assert path.read_bytes() == a
    assert (_packet(out), whose(out)) == alone["A"] and alone["A"][0]["state"] == "current"


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_a_review_whose_data_changed_while_it_was_prepared_is_refused(tmp_path, monkeypatch, boundary):
    """DK-02's T1 at both data-read boundaries: the data file B from ``boundary`` on, not restored. The export is
    refused, nothing written: it is of the record as it stands, or not written."""
    from adroit.constraints import review as curated
    path = scratch_payload(tmp_path, monkeypatch)
    out = tmp_path / "export"
    with _while(curated, BOUNDARIES[boundary], path, scaled(path.read_bytes()), restore=False), \
            pytest.raises(typer.BadParameter, match="changed while its review was prepared"):
        review(A, out)
    assert not out.exists() or [p.name for p in out.iterdir() if p.name != ".study.lock"] == []


# --- DK-04: the N_eff refusal states its source's benchmark ------------------------------------------------------

def test_the_neff_refusal_states_its_source_s_benchmark_in_each_frame():
    """DK-04, the auditor's case (``_lmu_neff(1e-3, 1e-3, .011, …)``): the 1% refusal is kept, and its words are the record's:
    the paper's Z′ decays to neutrinos and, in the natural-mixing frame, through its kinetic mixing to e⁺e⁻ (Escudero
    et al., eqs. (2.7)–(2.8)); never to dark matter; the 1% is ADROIT's threshold, not the paper's. Before, it said
    "μ, τ and neutrinos only" in both frames."""
    from adroit.parameter_space import searches
    said = {frame: searches._lmu_neff(1e-3, 1e-3, .011, frame, False) for frame in ("natural_mixing", "no_mixing")}
    for frame, out in said.items():
        assert out.excluded is None and "ADROIT's threshold, not the paper's" in out.why, out
        assert "1.1% of its width" in out.why and "μ, τ and neutrinos only" not in out.why, out.why
    assert "through its kinetic mixing (ε = g/70), to e⁺e⁻" in said["natural_mixing"].why
    assert "to neutrinos only (no kinetic mixing)" in said["no_mixing"].why and "e⁺e⁻" not in said["no_mixing"].why


# --- DK-05: an export's failure contract ----------------------------------------------------------------------------

def _failing(name: str, when: str):
    """``durable.write_atomic`` failing (an I/O error) at the entry ``name``: once, before replacing it or after; or
    at every write of it, before replacing it (``when`` "every write": the auditor's ``dj_export_failure``)."""
    real, done = durable.write_atomic, []

    def atomic(path, data):
        if when == "every write" and Path(path).name == name:
            done.append(True)
            raise OSError(5, "SIMULATED write failure before replacement")
        if not done and Path(path).name == name:
            done.append(True)
            if when == "before":
                raise OSError(5, "SIMULATED write failure before replacement")
            real(path, data)
            raise OSError(5, "SIMULATED write failure after replacement")
        return real(path, data)
    return patch.object(durable, "write_atomic", atomic), done


THREE = {"a.json": "B's record", "b.md": "B's report", "c.png": b"B's figure"}


@pytest.mark.parametrize("when", ["before", "after", "every write"])
@pytest.mark.parametrize("name", list(THREE))
def test_an_export_failing_part_way_leaves_its_folder_as_it_was(tmp_path, name, when):
    """DK-05: A's export replaced by B's, failing once before or after replacing each of its files, or at every write
    of one (the auditor's injection): the entry it never replaced is left as it is, not written again. The export raises,
    saying that nothing of it was kept; the folder is A's whole, as it was (a link of A's put back as a link), with no
    mark of an incomplete export."""
    out = tmp_path / "out"
    durable.export(out, {"a.json": "A's record", "b.md": "A's report", "c.png": None})
    os.symlink(tmp_path / "elsewhere.png", out / "c.png")
    before = {p.name: (os.readlink(p) if p.is_symlink() else p.read_bytes()) for p in out.iterdir()}
    failing, done = _failing(name, when)
    with failing, pytest.raises(durable.ExportFailed, match="nothing of it was kept; the folder's earlier files"):
        durable.export(out, THREE)
    assert done
    assert {p.name: (os.readlink(p) if p.is_symlink() else p.read_bytes()) for p in out.iterdir()} == before
    assert not durable.interrupted(out)


@pytest.mark.parametrize("name, when", [("report.md", "before"), ("current_curves.png", "before"),
                                        ("current_curves.png", "after"), ("report.md", "every write"),
                                        ("current_curves.png", "every write")])
def test_a_review_export_failing_part_way_leaves_the_earlier_packet_whole(tmp_path, name, when):
    """DK-05, the auditor's case (``dj_export_failure``): A's packet (Fermi-LAT) replaced by B's (IceCube), one I/O error
    before its report or its figure is replaced, or after its figure is. The command fails visibly, saying the earlier
    files were put back; the folder is A's packet whole. Before, it held B's record beside A's report and figure."""
    out = tmp_path / "export"
    review(A, out)
    before = {p: (out / p).read_bytes() for p in PACKET}
    failing, done = _failing(name, when)
    with failing, pytest.raises(typer.BadParameter, match="put back as they were"):
        review(B, out)
    assert done and {p: (out / p).read_bytes() for p in PACKET} == before and whose(out)[:2] == (A, A)
    assert not durable.interrupted(out)


@pytest.mark.parametrize("when", ["before", "after"])
@pytest.mark.parametrize("name", ["queue.json", "queue.md"])
def test_a_queue_export_failing_part_way_leaves_the_earlier_queue_whole(tmp_path, name, when):
    """DK-05, the queue: A's queue (a saved study's) replaced by B's (none selected), one I/O error before or after
    each of its files is replaced. The command fails, saying so; the folder is A's queue whole."""
    from tests import version_matrix as vm
    from tests.orchestrator.test_dj_fixes import coherent_queue, queue
    world, out = vm.make(tmp_path / "study"), tmp_path / "export"
    queue(out / "queue.json", [world.folder])
    before = {p: (out / p).read_bytes() for p in ("queue.json", "queue.md")}
    failing, done = _failing(name, when)
    with failing, pytest.raises(typer.BadParameter, match="put back as they were"):
        queue(out / "queue.json", [])
    assert done and {p: (out / p).read_bytes() for p in before} == before and coherent_queue(out)
    assert not durable.interrupted(out)


@pytest.mark.parametrize("when", ["before", "after"])
@pytest.mark.parametrize("name", [REQUESTS, *DRAFT_FILES])
def test_a_session_export_failing_part_way_leaves_the_earlier_one_whole(tmp_path, name, when):
    """DK-05, a session command's export: session A's request record, draft and report replaced by B's, one I/O error
    before or after each is replaced. The export fails, saying so; the folder is A's whole: its record still A's."""
    out = tmp_path / "out"
    preflight.session_export(out, Requests("r-a"), "session-a", members("session-a"))
    failing, done = _failing(name, when)
    with failing, pytest.raises(durable.ExportFailed, match="put back as they were"):
        preflight.session_export(out, Requests("r-b"), "session-b", members("session-b"))
    assert done and _coherent(out) == "session-a" and not durable.interrupted(out)


KILLED = """
import os, sys, time
from pathlib import Path
from adroit.core import durable
real = durable.write_atomic
def atomic(path, data):
    written = real(path, data)
    if Path(path).name == "a.json":
        print("written", flush=True)
        time.sleep(600)
    return written
durable.write_atomic = atomic
durable.export(Path(sys.argv[1]), {"a.json": "B's record", "b.md": "B's report", "c.png": b"B's figure"})
"""


def test_an_export_whose_writer_is_killed_part_way_reads_as_incomplete(tmp_path):
    """DK-05, the writer killed after its first file (the case the auditor proposed, not run): nothing can be put back, and
    the folder says so (``INCOMPLETE``, naming the export's files): the workbench's page of a run in it offers none of
    its files as the run's, a command-line draft in it is not shown as ready, and the review timer refuses a packet
    exported into it. The next export into the folder replaces it whole, the mark with it."""
    from adroit.constraints.review_cli import timer_start
    from adroit.ui import engine, outcomes
    out = tmp_path / "out"
    durable.export(out, {"a.json": "A's record", "b.md": "A's report", "c.png": b"A's figure"})
    child = subprocess.Popen([sys.executable, "-c", KILLED, str(out)], cwd=ROOT, stdout=subprocess.PIPE, text=True)
    assert child.stdout.readline().strip() == "written"
    child.send_signal(signal.SIGKILL)
    child.wait(60)
    assert durable.interrupted(out) and (out / "a.json").read_text() == "B's record"
    assert "a.json, b.md, c.png" in (out / INCOMPLETE).read_text()
    (out / "intake.json").write_text("{}")
    job = engine.Job(title="an intake", kind="models", command=["models", "step", SESSION, "--kind", "idea"],
                     folder=str(out), status="failed", attempt="x")
    shown = outcomes.outcome(tmp_path, out, job)
    assert shown.output == "none" and shown.headline == "Its output is incomplete" and INCOMPLETE in shown.detail
    assert outcomes.draft_outside_job(out).headline == "Its output is incomplete"
    (out / "record_review.json").write_text("{}")
    with pytest.raises(typer.BadParameter, match="was interrupted"):
        timer_start(out / "record_review.json", tmp_path / "timing.json", "P1")
    durable.export(out, {"a.json": "C's record", "b.md": "C's report", "c.png": b"C's figure"})
    assert not durable.interrupted(out) and (out / "b.md").read_text() == "C's report"

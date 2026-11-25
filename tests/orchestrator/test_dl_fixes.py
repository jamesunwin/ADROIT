"""The auditor's DK recheck (the independent audit of 2026-11-07 (dk recheck), pin 176a609): DL-01, a curated review's approval read
apart from the reading it shows, so that a packet of a stale B said "verified" (its page's badge too:
``tests/ui/test_dl_record_page.py``); DL-02, another export into a folder removing an interrupted export's mark; DL-03,
the mark's own removal failing outside the stated contract; DL-04, an interrupted discovery charged with the session of
an earlier export's companion; DL-05, a ZIP export replacing another export's bundle completed while it was prepared,
and the other files written only where none is. The curated records are read as they are, never signed; dollars are
simulated; no calculation or provider; $0."""
from __future__ import annotations

import errno
import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from adroit.core import durable
from adroit.core.durable import INCOMPLETE
from adroit.orchestrator.model_intake import REQUESTS, RunRequests
from tests.orchestrator.test_dj_fixes import A, B, PACKET, coherent_queue, queue, review, whose
from tests.orchestrator.test_dk_fixes import ROOT, scaled, scratch_payload


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def said(output: str) -> str:
    """A command's output in one line: its error box's frame and line breaks taken out."""
    return " ".join(output.translate(str.maketrans("│╭╮╰╯─", "      ")).split())


# --- DL-01: a review's approval is of the reading it shows ----------------------------------------------------------

def _approval(folder: Path) -> tuple[str, str, str]:
    """(the packet's review state, its signature binding's state, its report's "Review state")."""
    current = json.loads((folder / "record_review.json").read_text())["current"]
    said = next(line for line in (folder / "report.md").read_text().splitlines() if line.startswith("Review state: "))
    return current["review"], current["verification_binding"]["state"], said.removeprefix("Review state: ")


def unbound_reads_see(path: Path, other: bytes):
    """A signature check: one not given a reading's version (``version_of``) is made while the data file holds
    ``other``, its earlier bytes after (the auditor's ``review_export_status``); one given a reading's version, as it is."""
    from adroit.constraints import review_identity
    real = review_identity.signature_status

    def status(record, version_of=None):
        if version_of is not None:
            return real(record, version_of)
        kept, stamp = path.read_bytes(), path.stat().st_mtime_ns
        path.write_bytes(other)
        os.utime(path, ns=(stamp + 7_000_000_000, stamp + 7_000_000_000))
        try:
            return real(record)
        finally:
            path.write_bytes(kept)
            os.utime(path, ns=(stamp + 11_000_000_000, stamp + 11_000_000_000))
    return status


APPROVAL = {"A": ("verified", "current", "current"), "B": ("unreviewed", "stale", "stale")}   # the owner's A signature


def versions(tmp: Path, monkeypatch) -> tuple[Path, dict[str, bytes]]:
    """Record A (the owner's signed Fermi-LAT dwarfs) on a scratch copy of its data file: (the copy, its bytes as A and
    as B, every ordinate a hundred times A's)."""
    path = scratch_payload(tmp, monkeypatch)
    a = path.read_bytes()
    return path, {"A": a, "B": scaled(a)}


@pytest.mark.parametrize("captured", ["A", "B"])
def test_a_packet_s_review_state_and_its_binding_are_one_status(tmp_path, monkeypatch, captured):
    """DL-01, the auditor's ``dk_edges``: the record read as ``captured``, then its data file the other. The packet's review
    state and its signature's binding are both of the reading: A's "verified" and current, B's "unreviewed" and stale.
    Before, captured A beside a current B gave "unreviewed" beside a current binding, and captured B "verified" beside
    a stale one."""
    from adroit.constraints import review as curated
    from adroit.constraints.review_packets import packet_for
    path, data = versions(tmp_path, monkeypatch)
    path.write_bytes(data[captured])
    held = curated.reading(A)
    path.write_bytes(data["B" if captured == "A" else "A"])
    packet = packet_for(A, held=held)
    assert (packet.current.review, packet.current.verification_binding["state"]) == APPROVAL[captured][:2]


@pytest.mark.parametrize("captured", ["A", "B"])
def test_a_review_export_s_approval_is_of_the_version_it_read(tmp_path, monkeypatch, captured):
    """DL-01 in the export (the auditor's ``review_export_status``): the data file ``captured`` when the export reads it, and
    the other at every signature check not bound to that reading. The export is ``captured``'s whole, the same as it
    exported alone: its JSON's review state, its binding's state and its report's "Review state" agree, with its curve.
    Before, B's export said "verified" in its JSON beside a stale binding and "Review state: stale"."""
    from adroit.constraints import review_identity, review_packets
    path, data = versions(tmp_path, monkeypatch)
    alone = {}
    for label in "AB":
        path.write_bytes(data[label])
        review(A, tmp_path / f"{label} alone")
        alone[label] = _approval(tmp_path / f"{label} alone"), whose(tmp_path / f"{label} alone")
    assert alone["A"][0] == APPROVAL["A"] and alone["B"][0] == APPROVAL["B"] and alone["A"][1] != alone["B"][1]
    path.write_bytes(data[captured])
    status = unbound_reads_see(path, data["B" if captured == "A" else "A"])
    monkeypatch.setattr(review_identity, "signature_status", status)
    monkeypatch.setattr(review_packets, "signature_status", status)
    review(A, tmp_path / "export")
    assert path.read_bytes() == data[captured]
    assert (_approval(tmp_path / "export"), whose(tmp_path / "export")) == alone[captured]


def test_a_verification_reads_its_record_s_data_once(tmp_path, monkeypatch, awaiting):
    """DL-01's class in the verification: the data file is read once for the state checked and the version bound
    (``_verify_locked``); a data file changed after the page was drawn is refused, nothing written. The records file
    is a scratch copy, and its write is intercepted: nothing is signed."""
    from adroit.constraints import database
    from adroit.constraints import review as curated
    from adroit.constraints.review_identity import fingerprint
    awaiting(A)
    path, data = versions(tmp_path, monkeypatch)
    shown = fingerprint(database.record(A))
    written = []
    monkeypatch.setattr(durable, "write_atomic", lambda target, text: written.append(Path(target)))
    path.write_bytes(data["B"])
    with pytest.raises(ValueError, match="scientific content changed since the review panel"):
        curated.verify(A, "A. Tester", path=database.RECORDS, expected_sha256=shown)
    assert written == []
    path.write_bytes(data["A"])
    curated.verify(A, "A. Tester", path=database.RECORDS, expected_sha256=shown)
    assert written == [database.RECORDS]


# --- DL-02: another export keeps an interrupted export's mark --------------------------------------------------------

KILLED_REVIEW = """
import sys, time
from pathlib import Path
from adroit.core import durable
out, source = map(Path, sys.argv[1:])
real = durable.write_atomic
def atomic(path, data):
    written = real(path, data)
    if Path(path).name == "record_review.json":
        print("written", flush=True)
        time.sleep(600)
    return written
durable.write_atomic = atomic
durable.export(out, {name: (source / name).read_bytes() for name in ("record_review.json", "report.md",
                                                                      "current_curves.png")})
"""


def interrupted_review(tmp: Path) -> Path:
    """The auditor's ``dk_edges``: A's review packet (Fermi-LAT) exported, then B's (IceCube) export into the folder, its
    writer killed after it replaced the record: the folder holds B's record beside A's report and figure, marked."""
    out = tmp / "export"
    review(A, out)
    review(B, tmp / "B alone")
    child = subprocess.Popen([sys.executable, "-c", KILLED_REVIEW, str(out), str(tmp / "B alone")], cwd=ROOT,
                             stdout=subprocess.PIPE, text=True)
    assert child.stdout.readline().strip() == "written"
    child.send_signal(signal.SIGKILL)
    child.wait(60)
    assert durable.interrupted(out) and whose(out)[:2] == (B, A)
    return out


def _read_as_incomplete(tmp: Path, out: Path) -> None:
    """Each reader of an export's files reads ``out`` as incomplete: the review timer refuses its packet, the
    workbench's page of a run there offers none of its files, a command-line draft there is not shown as ready."""
    from adroit.constraints.review_cli import timer_start
    from adroit.ui import engine, outcomes
    with pytest.raises(typer.BadParameter, match="was interrupted"):
        timer_start(out / "record_review.json", tmp / "timing.json", "P1")
    assert not (tmp / "timing.json").exists()
    job = engine.Job(title="a survey", kind="constraints", command=["constraints", "resume", "0" * 32, "--out",
                                                                     str(out)], folder=str(out), status="failed",
                     attempt="x")
    assert outcomes.outcome(tmp, out, job).headline == "Its output is incomplete"


OTHERS = {"the review queue's": None,
          "another export, of other files": {"notes.json": "{}", "notes.md": "notes"},
          "an export of some of its files": {"record_review.json": "{}", "report.md": "a report"}}


@pytest.mark.parametrize("other", OTHERS)
def test_another_export_into_the_folder_keeps_an_interrupted_export_s_mark(tmp_path, other):
    """DL-02, the auditor's case: a review export interrupted (B's record beside A's report and figure), then ``other``
    exported whole into its folder: the review queue's (the real ``records queue``), another export of other files, or
    an export of only some of the interrupted one's. The mark stays, naming the review's files, and each reader still
    reads the folder as incomplete; the other export's files are its whole. The review exported again, its every file,
    removes it. Before, the queue's export removed the mark, and the review timer then accepted the mixed packet. (An
    export of only some of the files of A's packet, whole and recorded before B's was interrupted, is refused, nothing
    written: it would leave the rest of A's packet beside its own, the auditor's DL recheck, DM-03.)"""
    from tests import version_matrix as vm
    out = interrupted_review(tmp_path)
    if OTHERS[other] is None:
        queue(out / "queue.json", [vm.make(tmp_path / "study").folder])
        assert coherent_queue(out)
    elif other == "an export of some of its files":
        before = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
        with pytest.raises(ValueError, match="holds another export"):
            durable.export(out, OTHERS[other])
        assert {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()} == before
    else:
        durable.export(out, OTHERS[other])
    assert durable.interrupted(out)
    assert "record_review.json, report.md, current_curves.png" in (out / INCOMPLETE).read_text()
    _read_as_incomplete(tmp_path, out)
    review(A, out)
    assert not durable.interrupted(out) and whose(out)[:2] == (A, A)


def test_an_export_removes_only_the_interrupted_exports_it_writes_again(tmp_path):
    """DL-02: two interrupted exports in one folder (each writer killed after its first file); an export writing one's
    files again leaves the other's named; the second's then removes the mark. A mark ADROIT cannot read its files from
    (written by hand, or damaged) is kept by every export; an earlier mark (9055e67's words) is read."""
    out = tmp_path / "out"
    first, second = {"a.json": "A", "b.md": "A"}, {"c.json": "C", "d.md": "C"}
    (out).mkdir()
    (out / INCOMPLETE).write_text(durable._incomplete([tuple(first), tuple(second)]))
    durable.export(out, first)
    assert durable._interrupted_exports(out) == [tuple(second)] and "c.json, d.md" in (out / INCOMPLETE).read_text()
    durable.export(out, second)
    assert not durable.interrupted(out)
    (out / INCOMPLETE).write_text("someone stopped here\n")
    durable.export(out, {**first, **second})
    assert durable.interrupted(out) and durable._interrupted_exports(out) == [()]
    earlier = tmp_path / "earlier"
    earlier.mkdir()
    (earlier / INCOMPLETE).write_text("An export into this folder was interrupted while it was replacing these files, "
                                      "so they may be from two exports: a.json, b.md. Export again into this folder, "
                                      "or discard it. (ADROIT removes this file when an export into the folder "
                                      "completes.)\n")
    assert durable._interrupted_exports(earlier) == [("a.json", "b.md")]
    durable.export(earlier, first)
    assert not durable.interrupted(earlier)


# --- DL-03: the mark's own failures are said ---------------------------------------------------------------------------

def _failing_mark(step: str, when: str):
    """The mark (``INCOMPLETE``) failing: its write (``write_atomic``) before or after it replaces the entry, at the
    export's start (``step`` "written") or at its end where another interrupted export stays named ("rewritten"); or
    its removal (``Path.unlink``) at the end ("removed")."""
    real_write, real_unlink, done, marks = durable.write_atomic, Path.unlink, [], []

    def atomic(path, data):
        if Path(path).name == INCOMPLETE:
            marks.append(path)
        if Path(path).name == INCOMPLETE and not done and len(marks) == {"written": 1, "rewritten": 2}.get(step):
            done.append(True)
            if when == "after":
                real_write(path, data)
            raise OSError(errno.EIO, "SIMULATED failure at the mark")
        return real_write(path, data)

    def unlink(path, *args, **kwargs):
        if Path(path).name == INCOMPLETE and step == "removed" and not done:
            done.append(True)
            raise OSError(errno.EIO, "SIMULATED failure at the mark's removal")
        return real_unlink(path, *args, **kwargs)
    return patch.object(durable, "write_atomic", atomic), patch.object(Path, "unlink", unlink), done


MARK_STEPS = [("written", "before"), ("written", "after"), ("removed", "-"), ("rewritten", "before"),
              ("rewritten", "after")]


@pytest.mark.parametrize("step, when", MARK_STEPS)
def test_an_export_whose_mark_fails_says_what_it_left(tmp_path, step, when):
    """DL-03, the auditor's case and its kin: A's export replaced by B's, the mark failing. Where its first write fails, the
    export fails before any of its files is written ("nothing of it was kept"), the folder A's whole, unmarked. Where
    its removal, or its rewriting (another interrupted export staying named) fails after B's last file, the export
    fails saying B's files were each written and the folder reads as incomplete: B's whole, marked. Before, the
    removal's failure raised an ordinary I/O error, and the documented contract said the folder was as it had been."""
    out = tmp_path / "out"
    durable.export(out, {"a.json": "A", "b.md": "A"})
    if step == "rewritten":
        (out / INCOMPLETE).write_text(durable._incomplete([("c.json",)]))
    writing, unlinking, done = _failing_mark(step, when)
    with writing, unlinking, pytest.raises(durable.ExportFailed) as raised:
        durable.export(out, {"a.json": "B", "b.md": "B"})
    assert done
    files = {name: (out / name).read_text() for name in ("a.json", "b.md")}
    if step == "written":
        assert "nothing of it was kept" in str(raised.value)
        assert files == {"a.json": "A", "b.md": "A"} and not durable.interrupted(out)
    else:
        assert "wrote each of its files (a.json, b.md)" in str(raised.value) and "reads as incomplete" in str(
            raised.value)
        assert files == {"a.json": "B", "b.md": "B"} and durable.interrupted(out)


# --- DL-04: an interrupted discovery is charged with its own session -----------------------------------------------

KILLED_SESSION = """
import sys, time
from pathlib import Path
from adroit.core import durable
out, source, after = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
real = durable.write_atomic
def atomic(path, data):
    if Path(path).name == after:
        print("written", flush=True)
        time.sleep(600)
    return real(path, data)
durable.write_atomic = atomic
durable.export(out, {name: (source / name).read_bytes() for name in ("paid_requests.json", "discovery.json",
                                                                      "report.md")})
"""
SPENT = {"a": 1.25, "b": 8.5}           # each session's settled dollars, of a $10 cap (simulated)


def sessions(tmp: Path):
    """Two simulated discovery sessions in an isolated library, A $1.25 and B $8.50 settled of a $10 cap each (the auditor's
    ``interrupted_discovery_cost``): (the service, each session's id)."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service, ids = Intake(Catalog(tmp / "models")), {}
    for label, amount in SPENT.items():
        ids[label] = service.start(budget=10).session_id
        events = [dict(id=label, state="reserved", provider="anthropic", model="SIMULATED", reserved_usd=amount),
                  dict(id=label, state="settled", cost_usd=amount)]
        (service.folder(ids[label]) / "paid.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    return service, ids


def _members(ids: dict, label: str) -> dict:
    return {REQUESTS: RunRequests(session_id=ids[label], request_ids=[label], attempt=f"attempt-{label}")
            .model_dump_json(), "discovery.json": json.dumps({"session": ids[label]}), "report.md": f"survey {label}"}


def interrupted_survey(tmp: Path, ids: dict, after: str) -> Path:
    """A's survey exported; then B's export into its folder, its writer killed before ``after`` is written (the
    discovery record: after B's request record; the request record: before any)."""
    out, source = tmp / "export", tmp / "b"
    durable.export(out, _members(ids, "a"))
    durable.export(source, _members(ids, "b"))
    child = subprocess.Popen([sys.executable, "-c", KILLED_SESSION, str(out), str(source), after], cwd=ROOT,
                             stdout=subprocess.PIPE, text=True)
    assert child.stdout.readline().strip() == "written"
    child.send_signal(signal.SIGKILL)
    child.wait(60)
    assert durable.interrupted(out)
    return out


def _job(out: Path, ids: dict, command: str):
    from adroit.ui import engine
    words = (["constraints", "resume", ids["b"]] if command == "resume" else
             ["constraints", "discover", "SIMULATED model", "--budget", "10"])
    return engine.Job(title="SIMULATED survey B", kind="constraints", command=[*words, "--out", str(out)],
                      folder=str(out), status="failed", attempt="attempt-b")


KILLED = ("after its request record", "before its request record")


@pytest.mark.parametrize("killed", KILLED)
@pytest.mark.parametrize("command", ["resume", "discover"])
def test_an_interrupted_discovery_is_charged_with_its_own_session(tmp_path, monkeypatch, command, killed):
    """DL-04, the auditor's case: B's survey export killed after its request record (B's, attempt-b) replaced A's, or
    before it; A's discovery.json and report left; the run's log names B. A resume (its command names B), or a
    discover whose log names B: the run is charged with B's session, $8.50 settled of its $10 cap ($1.50 left), and
    the discovery.json naming A is named as not this run's ("records incomplete"); its page says its output is
    incomplete. Before, it showed A's $1.25 as "this run's session" and A's cap as its."""
    from adroit.orchestrator import accounting
    from adroit.ui import outcomes
    service, ids = sessions(tmp_path)
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    out = interrupted_survey(tmp_path, ids, "discovery.json" if killed.startswith("after") else REQUESTS)
    (out / "log.txt").write_text(f"# run attempt attempt-b\ndiscovery session {ids['b']} for SIMULATED model\n")
    job = _job(out, ids, command)
    cost = accounting.cost(out, job)
    lines = accounting.cost_lines(cost)
    assert (cost.session_id, cost.run_usd, cost.session_spent_usd) == (ids["b"], 8.5, 8.5)
    assert lines[0].startswith("This run's session: $8.50") and "its discovery.json names another session" in lines[0]
    assert lines[1] == "Session total so far: $8.50 spent of its approved $10.00 cap ($1.50 left)"
    assert accounting.short_line(cost).endswith("· records incomplete") and "$1.25" not in " ".join(lines)
    assert outcomes.outcome(tmp_path, out, job).headline == "Its output is incomplete"


def test_a_discovery_whose_session_is_not_established_shows_no_figure(tmp_path, monkeypatch):
    """DL-04: B's export killed before its request record, and nothing of the run names its session (a discover with
    no log): A's request record names another run, and A's discovery.json is in an interrupted folder. No figure is
    given for the run or its session, and why; never A's dollars."""
    from adroit.orchestrator import accounting
    service, ids = sessions(tmp_path)
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    out = interrupted_survey(tmp_path, ids, REQUESTS)
    cost = accounting.cost(out, _job(out, ids, "discover"))
    lines = accounting.cost_lines(cost)
    assert cost.run_usd is None and cost.session_spent_usd is None and "$1.25" not in " ".join(lines)
    assert "its session is not established" in lines[0] and lines[1] == "Session total: not available"


# --- DL-05: a new file is written only where none is ---------------------------------------------------------------

def test_a_bundle_export_never_replaces_one_written_while_it_was_prepared(tmp_path):
    """DL-05, the auditor's ``archive_destination_race``: A's export checks its new path, and at its temporary file B's
    export completes there. A's export is refused, saying so; B's bundle is left as B's export returned it, and valid;
    no temporary file of A's is left. Before, A's bundle replaced B's."""
    from adroit.evidence import archive
    from tests import version_matrix as vm
    a, b = vm.make(tmp_path / "a"), vm.make(tmp_path / "b")
    vm.publish(b, "B")
    destination, real, returned = tmp_path / "one.zip", archive.tempfile.NamedTemporaryFile, {}

    def meanwhile(*args, **kwargs):
        if not returned:
            with patch.object(archive.tempfile, "NamedTemporaryFile", real):
                archive.export_run(b.folder, destination)
            returned["B"] = destination.read_bytes()
        return real(*args, **kwargs)
    with patch.object(archive.tempfile, "NamedTemporaryFile", meanwhile), \
            pytest.raises(ValueError, match="was written by another export while this one was prepared"):
        archive.export_run(a.folder, destination)
    assert destination.read_bytes() == returned["B"] and archive.verify_bundle(destination).valid
    assert sorted(p.name for p in tmp_path.iterdir() if p.suffix == ".zip") == ["one.zip"]


def test_the_export_command_refuses_a_bundle_written_meanwhile(tmp_path):
    """DL-05 through ``adroit evidence export``: the same interleaving; the command exits 2, naming the other export,
    and B's bundle is left as it was."""
    from typer.testing import CliRunner

    from adroit.evidence import archive
    from adroit.evidence.cli import app
    from tests import version_matrix as vm
    a, b = vm.make(tmp_path / "a"), vm.make(tmp_path / "b")
    vm.publish(b, "B")
    destination, real, returned = tmp_path / "one.zip", archive.tempfile.NamedTemporaryFile, {}

    def meanwhile(*args, **kwargs):
        if not returned:
            with patch.object(archive.tempfile, "NamedTemporaryFile", real):
                archive.export_run(b.folder, destination)
            returned["B"] = destination.read_bytes()
        return real(*args, **kwargs)
    with patch.object(archive.tempfile, "NamedTemporaryFile", meanwhile):
        done = CliRunner().invoke(app, ["export", str(a.folder), "--out", str(destination)])
    assert done.exit_code == 2 and "written by another export while this one was prepared" in said(done.output), \
        done.output
    assert destination.read_bytes() == returned["B"]


@pytest.mark.parametrize("there", ["a file", "a link", "a link to nothing"])
@pytest.mark.parametrize("links", ["hard links", "no hard links"])
def test_a_new_file_is_never_written_over_an_entry(tmp_path, monkeypatch, there, links):
    """DL-05's primitive (``durable.write_new``, ``publish_new``): a new file is put in place only where no entry is,
    a file, a link or a link to nothing, which is left as it is; with hard links, or on a file system without them
    (``O_EXCL``). Where none is, it is written whole; no temporary file is left either way."""
    path, target = tmp_path / "new.zip", tmp_path / "target"
    if links == "no hard links":
        monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.ENOTSUP, "SIMULATED")))
    durable.write_new(tmp_path / "fresh.zip", b"whole")
    assert (tmp_path / "fresh.zip").read_bytes() == b"whole"
    if there == "a file":
        path.write_bytes(b"another's")
    else:
        if there == "a link":
            target.write_bytes(b"another's")
        os.symlink(target, path)
    before = (os.readlink(path), path.read_bytes() if path.exists() else None) if path.is_symlink() else path.read_bytes()
    with pytest.raises(FileExistsError, match="nothing of this one was kept"):
        durable.write_new(path, b"mine")
    assert ((os.readlink(path), path.read_bytes() if path.exists() else None) if path.is_symlink()
            else path.read_bytes()) == before
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def _appears(path: Path, data: bytes):
    """``durable.write_new`` with another writer's file at ``path`` just before it: the create-only check passed."""
    real = durable.write_new

    def written(target, payload):
        if Path(target) == path:
            path.write_bytes(data)
        return real(target, payload)
    return patch.object(durable, "write_new", written)


def test_a_model_export_never_replaces_one_written_meanwhile(tmp_path):
    """DL-05's class, ``adroit models export``: another file written at its path after its check is refused, naming
    it, and left as it is. Before, the export replaced it."""
    from adroit.library.personal import Catalog
    from tests.library.test_personal import save
    catalog = Catalog(tmp_path / "library")
    revision = save(catalog)
    path = tmp_path / "model.yaml"
    with _appears(path, b"another's"), pytest.raises(ValueError, match="written meanwhile"):
        catalog.export_model(revision.reference, path)
    assert path.read_bytes() == b"another's"


def test_a_review_timer_never_replaces_one_started_meanwhile(tmp_path):
    """DL-05's class, ``adroit records timer-start`` and ``adroit assist-session start``: another session written at the path
    after the check is refused, and left as it is. Before, the new session replaced it."""
    from typer.testing import CliRunner

    from adroit.constraints.review import start_timing
    from adroit.constraints.review_packets import packet_for
    from adroit.orchestrator.cli import app
    path = tmp_path / "timing.json"
    with _appears(path, b"another's"), pytest.raises(ValueError, match="started there meanwhile"):
        start_timing(packet_for(A), "P1", "assisted", path)
    assert path.read_bytes() == b"another's"
    other = tmp_path / "session.json"
    with _appears(other, b"another's"):
        done = CliRunner().invoke(app, ["assist-session", "start", str(other), "P1", "task", "0" * 64, "manual"])
    assert done.exit_code == 2 and "another was started there meanwhile" in said(done.output), done.output
    assert other.read_bytes() == b"another's"


def test_an_evidence_folder_made_meanwhile_is_refused(tmp_path):
    """DL-05's class, ``adroit evidence tables`` and ``figures``: a folder made at ``--out`` after the check is
    refused, nothing written into it."""
    from adroit.evidence import cli
    out = tmp_path / "tables"
    real = Path.exists
    with patch.object(Path, "exists", lambda self: False if self == out else real(self)):
        out.mkdir()
        with pytest.raises(typer.BadParameter, match="another was made there meanwhile"):
            cli._write(out, {"a.csv": b"x"})
    assert list(out.iterdir()) == []


def test_two_bundle_downloads_at_once_are_each_their_own(tmp_path):
    """DL-05's case on the download menu (``ui/exports.files``): B's download completed while A's is prepared. Each
    is written in a folder of its own, and each returns its own version's bundle, whole: A's and B's."""
    from adroit.evidence import archive
    from adroit.evidence.version import resolve
    from adroit.ui.exports import files
    from tests import version_matrix as vm
    a, b = vm.make(tmp_path / "a"), vm.make(tmp_path / "b")
    vm.publish(b, "B")
    tokens = {label: resolve(world.folder, presentation=True).token() for label, world in (("A", a), ("B", b))}
    real, returned = archive.tempfile.NamedTemporaryFile, {}

    def meanwhile(*args, **kwargs):
        if not returned:
            with patch.object(archive.tempfile, "NamedTemporaryFile", real):
                returned["B"] = files("bundle", tokens["B"])[1]
        return real(*args, **kwargs)
    with patch.object(archive.tempfile, "NamedTemporaryFile", meanwhile):
        returned["A"] = files("bundle", tokens["A"])[1]
    assert vm.agrees(vm.outcome(a, vm.Output(vm.text_of(returned["A"])), vm.PARTS), "A")
    assert vm.outcome(b, vm.Output(vm.text_of(returned["B"])), vm.PARTS) == "B"


def test_every_export_of_a_packet_is_whole_after_these_repairs(tmp_path):
    """The DK cases still hold: A's packet replaced by B's whole; the mark absent."""
    out = tmp_path / "export"
    review(A, out)
    review(B, out)
    assert whose(out)[:2] == (B, B) and not durable.interrupted(out)
    assert [p for p in PACKET if (out / p).exists()] == list(PACKET)

"""The auditor's DI recheck (the independent audit of 2026-11-07 (di recheck), pin 7860b3d): DJ-01, a curated record's review export
(``adroit records review --out``) writing its record, report and curve apart, with no hold of its folder, so that two
exports into one folder left one record's packet beside another's report and curve; and each member, and the review
queue's (``adroit records queue --out``), written through a link into a folder another writer held. The same export,
``durable.export``, now writes the theory checks' and the neutrino fog's results. (DJ-02, the plane's series, is repaired
in ``tests/version_matrix.py`` and its harnesses.) The curated records are read as they are, never signed; the saved
studies are the matrix's typed fixtures; no calculation or provider; $0."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from adroit.core.durable import INCOMPLETE, RECORD, publishing

ROOT = Path(__file__).parents[2]
A, B = "fermi-1503.02641-dsph", "icecube-1612.05949-sd"         # each with its curves (the auditor's pair)
NUMBERS = "pdg-2024-electroweak-st"                             # a record of numbers: no figure
PACKET = ("record_review.json", "report.md", "current_curves.png")
QUEUE = ("queue.json", "queue.md")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _files(folder: Path) -> dict[str, str]:
    """Each file of ``folder`` (its own entries, a link read through; the publication lock aside) and its digest."""
    return {p.name: sha(p.read_bytes()) for p in sorted(folder.iterdir()) if p.is_file() and p.name != ".study.lock"}


def review(record: str, out: Path | None, run: Path | None = None) -> str:
    """``adroit records review RECORD --out OUT`` as its command runs it: what it printed."""
    from adroit.constraints.review_cli import packet_command
    printed = StringIO()
    with redirect_stdout(printed):
        packet_command(record, run=run, task_id="", out=out)
    return printed.getvalue()


def whose(folder: Path) -> tuple[str, str, str]:
    """(the packet's JSON names, the record its report is of, its curve's digest or "")."""
    packet = json.loads((folder / "record_review.json").read_text())["record_id"]
    title = (folder / "report.md").read_text().splitlines()[0].removeprefix("# Record review: ")
    curve = folder / "current_curves.png"
    return packet, title, sha(curve.read_bytes()) if curve.exists() else ""


def alone(tmp: Path, record: str) -> tuple[str, str, str]:
    """``record``'s packet exported alone into a folder of its own: what a whole packet of it is."""
    review(record, tmp / f"alone {record}")
    return whose(tmp / f"alone {record}")


@contextmanager
def after_the_first_member(folder: Path, then):
    """``then()`` called once, just after the export's first member (its record, ``record_review.json``) is written
    into ``folder``: by ``durable.write_atomic`` now, by ``Path.write_text`` at the pin (the auditor's boundary)."""
    from adroit.core import durable
    real_atomic, real_text, done = durable.write_atomic, Path.write_text, []

    def boundary(path) -> None:
        if not done and Path(path).name == "record_review.json" and Path(path).parent.resolve() == folder.resolve():
            done.append(True)
            then()

    def atomic(path, data):
        written = real_atomic(path, data)
        boundary(path)
        return written

    def text(path, data, *args, **kwargs):
        written = real_text(path, data, *args, **kwargs)
        boundary(path)
        return written
    with patch.object(durable, "write_atomic", atomic), patch.object(Path, "write_text", text):
        yield done


B_EXPORT = """
import json, sys
from pathlib import Path
from tests.orchestrator.test_dj_fixes import review
print("trying", flush=True)
review(sys.argv[1], Path(sys.argv[2]))
print(json.dumps({"done": True}), flush=True)
"""


def _b_export(record: str, out: Path, by: str):
    """B, ``record``'s whole export into ``out``, from another thread or another process: (a callable waiting until it
    is trying, one waiting up to its seconds for it to end, one waiting for it to end)."""
    if by == "another process":
        process = subprocess.Popen([sys.executable, "-c", B_EXPORT, record, str(out)], cwd=ROOT,
                                   stdout=subprocess.PIPE, text=True)

        def waiting(seconds):
            try:
                process.wait(seconds)
            except subprocess.TimeoutExpired:
                pass
        return (lambda: process.stdout.readline().strip() == "trying", waiting,
                lambda: (process.wait(120), process.returncode)[1])
    trying, outcome = threading.Event(), {}

    def b():
        trying.set()
        try:
            review(record, out)
            outcome["code"] = 0
        except Exception as error:                      # noqa: BLE001 - reported to the test
            outcome["code"] = repr(error)
    thread = threading.Thread(target=b)
    thread.start()
    return (lambda: trying.wait(10), thread.join, lambda: (thread.join(120), outcome.get("code"))[1])


# --- DJ-01: an export is one record's whole -------------------------------------------------------------------------

@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_a_curated_review_export_is_one_record_s_whole(tmp_path, by):
    """DJ-01, the auditor's case: A's export (record ``A``) is paused just after its record is written; B's whole export into
    the same folder (record ``B``; another thread, or another process) starts and is given three seconds while A's is
    being written. A's export is written whole under its hold of the folder, and B waits for it, writing nothing; then
    B's is written whole: the folder is B's record, report and curve, one packet. Before, B completed inside A's export,
    and the folder held B's record beside A's report and curve."""
    whole = {record: alone(tmp_path, record) for record in (A, B)}
    out, seen = tmp_path / "export", {}

    def b_starts():
        seen["B"] = _b_export(B, out, by)
        assert seen["B"][0]()
        seen["B"][1](3)
        seen["while A held"] = _files(out)
    with after_the_first_member(out, b_starts) as reached:
        review(A, out)
    assert reached, "A's first member was never written"
    assert seen["B"][2]() == 0
    assert set(seen["while A held"]) == {"record_review.json", INCOMPLETE}, seen["while A held"]  # B wrote nothing
    assert not (out / INCOMPLETE).exists()                     # A's mark of an export being written, removed (DK-05)
    assert whose(out) == whole[B] == (B, B, whole[B][2])


def test_an_export_replaces_an_earlier_one_whole(tmp_path):
    """An export into a folder holding another record's replaces it whole: a record with no figure leaves none of the
    earlier record's beside its own (its entry removed), and the earlier record's is restored whole after it."""
    out = tmp_path / "export"
    review(A, out)
    review(NUMBERS, out)
    assert whose(out) == (NUMBERS, NUMBERS, "") and not (out / "current_curves.png").exists()
    review(A, out)
    assert whose(out) == alone(tmp_path, A)


def test_a_record_changed_while_its_review_is_prepared_is_refused(tmp_path):
    """The packet, its report and its curve are one reading of the record: a record whose content changes between the
    packet's reading and the figure's is refused, nothing written."""
    from adroit.constraints import database
    real, calls = database.record, []

    def record(record_id):
        found = real(record_id)
        calls.append(record_id)
        return found if len(calls) == 1 else found.model_copy(update={"notes": found.notes + " (changed)"})
    out = tmp_path / "export"
    with patch.object(database, "record", record), pytest.raises(typer.BadParameter, match="changed while its review"):
        review(A, out)
    assert not out.exists() or _files(out) == {}



def coherent_queue(folder: Path) -> bool:
    """Whether the queue export's Markdown is its JSON's own queue, rendered (``review_queue.report``; the time it was
    generated aside, which the report stamps itself)."""
    from adroit.constraints.review_queue import report
    from adroit.constraints.review_tasks import ReviewQueue
    found = ReviewQueue.model_validate_json((folder / "queue.json").read_text())

    def kept(text: str) -> list[str]:
        return [line for line in text.splitlines() if not line.startswith("Report generated (UTC):")]
    return kept((folder / "queue.md").read_text()) == kept(report(found))


def test_a_queue_export_is_its_queue_whole(tmp_path):
    """The review queue's export (``records queue --out``): its JSON and its Markdown one queue's, each replaced whole
    by a later export into the folder."""
    from tests import version_matrix as vm
    world, out = vm.make(tmp_path / "study"), tmp_path / "export"
    queue(out / "queue.json", [world.folder])
    assert coherent_queue(out)
    queue(out / "queue.json", [])
    assert coherent_queue(out) and "tasks" in (out / "queue.json").read_text()


@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_a_queue_export_is_one_queue_s_whole(tmp_path, by):
    """DJ-01, the queue: A's queue export (a saved study's queue) paused just after its JSON is written; B's export of
    another queue (none selected) into the same folder, from another thread or process, given three seconds. B waits,
    writing nothing; then B's is written whole: the JSON and the Markdown one queue's, B's. Before, B's JSON and
    Markdown were written inside A's, and A's Markdown was left beside B's JSON."""
    from adroit.core import durable
    from tests import version_matrix as vm
    world, out, seen = vm.make(tmp_path / "study"), tmp_path / "export", {}
    real_atomic, real_text = durable.write_atomic, Path.write_text

    def b_starts(path):
        if not seen and Path(path).name == "queue.json":
            seen["B"] = _write("queue", out, by)
            assert seen["B"][0]()
            seen["B"][1](3)
            seen["while A held"] = _files(out)

    def atomic(path, data):
        written = real_atomic(path, data)
        b_starts(path)
        return written

    def text(path, data, *args, **kwargs):
        written = real_text(path, data, *args, **kwargs)
        b_starts(path)
        return written
    with patch.object(durable, "write_atomic", atomic), patch.object(Path, "write_text", text):
        queue(out / "queue.json", [world.folder])
    assert seen["B"][2]() == 0
    assert set(seen["while A held"]) == {"queue.json", INCOMPLETE}, seen["while A held"]
    assert not (out / INCOMPLETE).exists()
    assert coherent_queue(out) and '"tasks": []' in (out / "queue.json").read_text()


# --- DJ-01: each member to its own entry, never through a link ------------------------------------------------------

def _write(command: str, out: Path, by: str, run: Path | None = None):
    """``command`` (``review`` of record A, or ``queue``) exporting into ``out``, from another thread or process."""
    if command == "review":
        return _b_export(A, out, by) if run is None else _b_export_run(A, out, run, by)
    script = ("import sys\nfrom pathlib import Path\nfrom tests.orchestrator.test_dj_fixes import queue\n"
              "print('trying', flush=True)\nqueue(Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]])\n")
    if by == "another process":
        process = subprocess.Popen([sys.executable, "-c", script, str(out / "queue.json"),
                                    *([str(run)] if run else [])], cwd=ROOT, stdout=subprocess.PIPE, text=True)

        def waiting(seconds):
            try:
                process.wait(seconds)
            except subprocess.TimeoutExpired:
                pass
        return (lambda: process.stdout.readline().strip() == "trying", waiting,
                lambda: (process.wait(120), process.returncode)[1])
    trying, outcome = threading.Event(), {}

    def q():
        trying.set()
        queue(out / "queue.json", [run] if run else [])
        outcome["code"] = 0
    thread = threading.Thread(target=q)
    thread.start()
    return (lambda: trying.wait(10), thread.join, lambda: (thread.join(120), outcome.get("code"))[1])


def _b_export_run(record: str, out: Path, run: Path, by: str):
    """As ``_b_export``, the review reading the saved study ``run``."""
    assert by == "another thread", "a process reads its run through the CLI's own test (``_cli``)"
    trying, outcome = threading.Event(), {}

    def b():
        trying.set()
        review(record, out, run)
        outcome["code"] = 0
    thread = threading.Thread(target=b)
    thread.start()
    return (lambda: trying.wait(10), thread.join, lambda: (thread.join(120), outcome.get("code"))[1])


def queue(out: Path, runs: list[Path]) -> str:
    """``adroit records queue --run … --out OUT`` as its command runs it: what it printed."""
    from adroit.constraints.review_cli import queue_command
    printed = StringIO()
    with redirect_stdout(printed):
        queue_command(run=runs, out=out, include_scan=False)
    return printed.getvalue()


MEMBERS = [("review", name) for name in PACKET] + [("queue", name) for name in QUEUE]


def _linked(command: str, out: Path, name: str, target: Path) -> None:
    """``out`` holding an earlier export of ``command`` (its files recorded there, ``durable.RECORD``), its ``name``
    then a link to ``target``: an entry the next export of it replaces (the auditor's DL recheck, DM-03: an entry that no
    export recorded there wrote is never replaced, ``test_dm_fixes``)."""
    if command == "review":
        review(A, out)
    else:
        queue(out / "queue.json", [])
    (out / name).unlink(missing_ok=True)
    (out / name).symlink_to(target)


@pytest.mark.parametrize("command, name", MEMBERS)
@pytest.mark.parametrize("held", ["its target's folder", "its own folder"])
@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_an_export_member_that_is_a_link_is_written_in_its_own_folder(tmp_path, by, held, command, name):
    """DJ-01, the auditor's link cases: the export folder holds an earlier export of the command, its ``name`` a link to a
    file of another folder (``_linked``), held by this thread's writer (its target's) or the export's own folder held;
    the whole export runs (another thread, or another process). With its target's folder held, the export writes into
    its own folder, the link replaced by its file, and the held folder is untouched; with its own held, it waits for
    that hold, writing nothing, then does the same. Before, each member but the curve was written through the link
    into the held folder."""
    target, out = tmp_path / "held", tmp_path / "export"
    target.mkdir()
    (target / name).write_bytes(b"SIMULATED held output")
    _linked(command, out, name, target / name)
    before, earlier = _files(target), _files(out)
    with publishing(target if held == "its target's folder" else out):
        trying, waiting, finish = _write(command, out, by)
        assert trying()
        if held == "its own folder":
            waiting(3)
            assert (out / name).is_symlink() and _files(out) == earlier                  # it waits, writing nothing
        else:
            assert finish() == 0
        assert _files(target) == before
    if held == "its own folder":
        assert finish() == 0
    assert _files(target) == before
    assert not (out / name).is_symlink(), f"{name} still the link"
    expected = PACKET if command == "review" else QUEUE
    assert set(_files(out)) == {*expected, RECORD}


@pytest.mark.parametrize("command, member", [("review", "record_review.json"), ("review", "report.md"),
                                             ("queue", "queue.json"), ("queue", "queue.md")])
def test_the_cli_s_export_leaves_a_held_study_reached_through_a_link(tmp_path, command, member):
    """DJ-01, the auditor's CLI case: the installed command (``adroit records review|queue``, a real child process) exporting
    a typed saved study's review into a folder whose ``member``, of an earlier export of it, is a link to another saved
    study's result or report (``_linked``), that study's folder held: the export completes in its own folder, the
    study's part untouched."""
    from tests import version_matrix as vm
    world, held = vm.make(tmp_path / "input"), vm.make(tmp_path / "target")
    target = held.folder / ("result.json" if member.endswith(".json") else "report.md")
    before = target.read_bytes()
    out = tmp_path / "export"
    _linked(command, out, member, target)
    args = (["review", A, "--run", str(world.folder), "--out", str(out)] if command == "review" else
            ["queue", "--run", str(world.folder), "--out", str(out / "queue.json")])
    with publishing(held.folder):
        done = subprocess.run([sys.executable, "-m", "adroit.orchestrator.cli", "records", *args], cwd=ROOT,
                              capture_output=True, text=True, timeout=120)
        assert target.read_bytes() == before
    assert done.returncode == 0, done.stderr[-2000:]
    assert target.read_bytes() == before and not (out / member).is_symlink()


# --- DJ-01's class: an export never writes into a saved study's folder, and the other exports are written so ---------

def test_an_export_into_a_saved_study_s_folder_is_refused(tmp_path):
    """An export into a folder holding a saved study (its ``result.json``) is refused, nothing written: its own
    ``report.md`` would have replaced the study's (the review, the queue, a theory check, the neutrino fog)."""
    from tests import version_matrix as vm
    world = vm.make(tmp_path / "study")
    before = _files(world.folder)
    with pytest.raises(typer.BadParameter, match="holds a saved study"):
        review(A, world.folder)
    with pytest.raises(typer.BadParameter, match="holds a saved study"):
        queue(world.folder / "queue.json", [])
    from adroit.orchestrator import fog_cli
    with pytest.raises(typer.BadParameter, match="holds a saved study"):
        fog_cli.standard(target="Xe", out=world.folder)
    assert _files(world.folder) == before


def test_the_fog_s_export_replaces_a_link_and_is_whole(tmp_path):
    """The neutrino fog's standard floor (``adroit fog standard``): its files written whole to their own entries, a link
    among them (in place of an earlier export's file) replaced, its target untouched."""
    from adroit.orchestrator import fog_cli
    target, out = tmp_path / "elsewhere", tmp_path / "fog"
    target.mkdir()
    (target / "floor.csv").write_text("SIMULATED other output")
    fog_cli.standard(target="Xe", out=out)
    (out / "floor.csv").unlink()
    (out / "floor.csv").symlink_to(target / "floor.csv")
    fog_cli.standard(target="Xe", out=out)
    assert (target / "floor.csv").read_text() == "SIMULATED other output"
    assert not (out / "floor.csv").is_symlink() and (out / "floor.csv").read_text().startswith("mass_gev,sigma_cm2")
    assert (out / "floor.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_theory_check_s_export_replaces_a_link(tmp_path):
    """A theory check (``adroit theory vacuum``): its results and report written to their own entries under one hold,
    a link to another folder's report (in place of an earlier check's) replaced, never written through."""
    import yaml
    from typer.testing import CliRunner

    from adroit.parameter_space.library import entry
    from adroit.theory.cli import app
    source = tmp_path / "model.yaml"
    source.write_text(yaml.safe_dump(entry("higgs_portal_scalar").spec().model_dump(mode="json")))
    target, out = tmp_path / "elsewhere", tmp_path / "vacuum"
    target.mkdir()
    (target / "report.md").write_text("SIMULATED other report")
    assert CliRunner().invoke(app, ["vacuum", str(source), "--out", str(out)]).exit_code == 0
    (out / "report.md").unlink()
    (out / "report.md").symlink_to(target / "report.md")
    done = CliRunner().invoke(app, ["vacuum", str(source), "--out", str(out)])
    assert done.exit_code == 0, done.output
    assert (target / "report.md").read_text() == "SIMULATED other report"
    assert not (out / "report.md").is_symlink() and (out / "vacuum.json").exists()


def test_a_single_file_written_to_a_path_given_replaces_a_link_there(tmp_path):
    """DJ-01's class, a single file: ``adroit anomaly template --out`` writes its own entry, a link there replaced,
    its target (another folder's file) untouched; and a model export refuses a path that is a link, even a dangling
    one, rather than writing through it."""
    from typer.testing import CliRunner

    from adroit.orchestrator.cli import app
    target, out = tmp_path / "elsewhere" / "result.json", tmp_path / "anomaly.yaml"
    target.parent.mkdir()
    target.write_text("SIMULATED other output")
    out.symlink_to(target)
    done = CliRunner().invoke(app, ["anomaly", "template", "--out", str(out)])
    assert done.exit_code == 0, done.output
    assert target.read_text() == "SIMULATED other output" and not out.is_symlink()
    from adroit.library.personal import Catalog
    from tests.library.test_personal import save
    catalog = Catalog(tmp_path / "library")
    revision = save(catalog)
    dangling = tmp_path / "model.yaml"
    dangling.symlink_to(tmp_path / "elsewhere" / "absent.yaml")
    with pytest.raises(ValueError, match="cannot overwrite"):
        catalog.export_model(revision.reference, dangling)
    assert not (tmp_path / "elsewhere" / "absent.yaml").exists()

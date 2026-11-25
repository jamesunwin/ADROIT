"""The auditor's DL recheck (2026-11-07), DM-01 to DM-03: a damaged request record establishes no session (DM-01); every
new file a command promises is written only where none is, whichever writer wins (DM-02); and an export never leaves
part of another export beside its own (DM-03). Every dollar is simulated; no provider is contacted, nothing is signed,
and no review session is conducted (the timer's session files are written into each test's own folder)."""

from __future__ import annotations

import ast
import json
import re
import signal
import subprocess
import sys
import threading
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from adroit.core import durable
from adroit.core.durable import INCOMPLETE, RECORD
from adroit.orchestrator.model_intake import REQUESTS, RunRequests
from tests.orchestrator import test_dl_fixes as dl
from tests.orchestrator.test_dj_fixes import A, B, PACKET, coherent_queue, queue, review, whose
from tests.orchestrator.test_dk_fixes import Requests
from tests.orchestrator.test_dl_fixes import _appears, said

ROOT = Path(__file__).parents[2]


def files(folder: Path) -> dict[str, bytes]:
    """Each entry of ``folder`` (a link by its target's name; the publication lock aside) and its bytes."""
    return {p.name: (b"-> " + str(p.readlink()).encode()) if p.is_symlink() else p.read_bytes()
            for p in sorted(folder.iterdir()) if p.name != ".study.lock"}


# --- DM-01: a damaged request record establishes no session ------------------------------------------------------

DAMAGED = {"torn": '{"session_id":', "null": "null", "a list": "[]", "an empty object": "{}"}


def damaged_survey(tmp: Path, ids: dict, damage: str, log: str = "") -> Path:
    """The auditor's ``damaged_session`` case: a survey folder holding an earlier survey's ``discovery.json`` (session A's)
    and this run's request record, damaged (``DAMAGED``); a log only where given."""
    out = tmp / "survey"
    out.mkdir(parents=True)
    (out / "discovery.json").write_text(json.dumps({"session": ids["a"]}))
    (out / REQUESTS).write_text(DAMAGED[damage])
    if log:
        (out / "log.txt").write_text(log)
    return out


def _charged(tmp: Path, monkeypatch, out_of, command: str = "discover"):
    """(the run's cost, its lines, the survey folder, the job, each session's id), the sessions of
    ``test_dl_fixes.sessions`` (A $1.25 and B $8.50 settled, of $10 caps)."""
    from adroit.orchestrator import accounting
    service, ids = dl.sessions(tmp)
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    out = out_of(ids)
    job = dl._job(out, ids, command)
    cost = accounting.cost(out, job)
    return cost, accounting.cost_lines(cost), out, job, ids


@pytest.mark.parametrize("damage", DAMAGED)
def test_a_damaged_request_record_charges_the_run_with_no_session(tmp_path, monkeypatch, damage):
    """DM-01, the auditor's case: a discover run (attempt B) whose request record is torn, ``null``, a list or ``{}``, beside
    an earlier survey's ``discovery.json`` naming session A, with no log: nothing bound to the run names its session.
    No figure is given for the run, its session or its cap, the damaged record is named, and no session is linked
    (``ledger_session``). Before, the run was charged with A's session, "$1.25 … ($8.75 left)", beside the damage."""
    from adroit.orchestrator import accounting
    cost, lines, out, job, _ = _charged(tmp_path, monkeypatch, lambda ids: damaged_survey(tmp_path, ids, damage))
    assert (cost.session_id, cost.run_usd, cost.session_spent_usd, cost.session_cap_usd,
            cost.session_remaining_usd) == ("", None, None, None, None)
    assert f"the run's request record ({REQUESTS}) cannot be read" in lines[0]
    assert "its session is not established" in lines[0] and lines[1] == "Session total: not available"
    shown = " ".join([*lines, accounting.short_line(cost)])
    assert not re.search(r"\$\d", shown), shown
    assert accounting.ledger_session(out, job) == ("", "source")


@pytest.mark.parametrize("bound", ["its log", "its command"])
@pytest.mark.parametrize("damage", DAMAGED)
def test_a_damaged_request_record_beside_a_bound_record_is_charged_with_that_session(tmp_path, monkeypatch, damage,
                                                                                     bound):
    """DM-01's controls: the record damaged, and a record bound to the run naming B's session, its log (naming its
    attempt) or its command (a resume of B): the run is charged with B's session, $8.50 of its $10.00 cap ($1.50 left),
    A's ``discovery.json`` named as not this run's, and the damaged record named, giving no own figure."""
    log = "# run attempt attempt-b\ndiscovery session {b} for SIMULATED model\n" if bound == "its log" else ""
    cost, lines, *_ = _charged(tmp_path, monkeypatch, lambda ids: damaged_survey(
        tmp_path, ids, damage, log.replace("{b}", ids["b"])), "discover" if bound == "its log" else "resume")
    assert (cost.run_usd, cost.session_spent_usd, cost.own_usd) == (8.5, 8.5, None)
    assert lines[0].startswith("This run's session: $8.50") and "its discovery.json names another session" in lines[0]
    assert f"the run's request record ({REQUESTS}) cannot be read" in lines[0]
    assert lines[1] == "Session total so far: $8.50 spent of its approved $10.00 cap ($1.50 left)"


def test_a_damaged_request_record_beside_a_log_that_names_no_run_charges_no_session(tmp_path, monkeypatch):
    """DM-01: the record damaged, and a log from before logs named their run naming B's session: not bound to this
    run, so no session is established, and no figure is given."""
    cost, lines, *_ = _charged(tmp_path, monkeypatch, lambda ids: damaged_survey(
        tmp_path, ids, "torn", f"discovery session {ids['b']} for SIMULATED model\n"))
    assert (cost.session_id, cost.run_usd) == ("", None) and "its session is not established" in lines[0]


@pytest.mark.parametrize("record", ["none", "one naming no run"])
def test_a_run_from_before_the_request_record_is_still_charged_with_its_discovery_json_s_session(tmp_path,
                                                                                                 monkeypatch, record):
    """DM-01's legacy control: a survey from before request records (none in its folder), or before they named their
    run (a record naming session A, no attempt), with no log: its ``discovery.json``'s session, A's $1.25, as before."""
    def survey(ids: dict) -> Path:
        out = tmp_path / "survey"
        out.mkdir()
        (out / "discovery.json").write_text(json.dumps({"session": ids["a"]}))
        if record != "none":
            (out / REQUESTS).write_text(RunRequests(session_id=ids["a"], request_ids=["a"]).model_dump_json())
        return out
    cost, lines, *_ = _charged(tmp_path, monkeypatch, survey)
    assert (cost.run_usd, cost.session_spent_usd) == (1.25, 1.25) and lines[0].startswith("This run's session: $1.25")


# --- DM-02: every new file a command promises is written only where none is ----------------------------------------

def _sessions_for_report(tmp: Path) -> tuple[Path, Path]:
    """The auditor's ``report_create_only``: (A's folder, empty; B's, one simulated, unfinished, unattested assisted session
    of $8.50 simulated API cost)."""
    from datetime import datetime, timezone

    from adroit.evaluation import assistance_timing as timing
    a, b = tmp / "A", tmp / "B"
    a.mkdir()
    b.mkdir()
    session = timing.start("SIMULATED", "SIMULATED", "a" * 64, "assisted", now=datetime(2026, 11, 7, tzinfo=timezone.utc))
    (b / "session.json").write_text(session.model_copy(update={"api_cost_usd": 8.5}).model_dump_json())
    return a, b


@pytest.mark.parametrize("how", ["in process", "the command"])
def test_a_usability_report_never_replaces_one_written_meanwhile(tmp_path, how):
    """DM-02, the auditor's case: A's report checks its new path (``adroit assist-session report --out``); during its analysis
    B's report, of another folder, is written there whole. A's is refused, saying so; B's bytes are left as B wrote
    them. Before, A's report replaced B's ("$8.50" became "$0.00"), and the command exited 0."""
    from adroit.evaluation import usability
    from adroit.orchestrator import cli
    a, b = _sessions_for_report(tmp_path)
    out, real, written = tmp_path / "report.md", usability.analyse, {}

    def meanwhile(*args, **kwargs):
        if not written:
            with patch.object(usability, "analyse", real), redirect_stdout(StringIO()):
                cli.session_report(b, sus=None, usage=None, out=out)
            written["B"] = out.read_bytes()
        return real(*args, **kwargs)
    with patch.object(usability, "analyse", meanwhile):
        if how == "in process":
            with pytest.raises(typer.BadParameter, match="written by another report meanwhile"):
                cli.session_report(a, sus=None, usage=None, out=out)
        else:
            done = CliRunner().invoke(cli.app, ["assist-session", "report", str(a), "--out", str(out)])
            assert done.exit_code == 2 and "written by another report meanwhile" in said(done.output), done.output
    assert out.read_bytes() == written["B"] and b"$8.50" in written["B"]
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []


def _model(tmp: Path):
    from adroit.orchestrator.model_approval import select_model
    from tests.orchestrator.test_model_approval import supplied
    return select_model(supplied())


def _import(tmp: Path, out: Path, title: str):
    from adroit.orchestrator.cli import app
    table = tmp / "limit.csv"
    table.write_text("m_GeV,sigma_cm2\n10,1e-43\n20,0\n")
    return CliRunner().invoke(app, ["experiments", "import", str(table), "--title", title, "--out", str(out)])


def _create_only(writer: str, tmp: Path, monkeypatch) -> tuple[Path, bytes, object]:
    """(its path, B's bytes, A's write): ``writer``'s new file, B's written at its path after A's check."""
    other = b"SIMULATED another's"
    if writer == "the usability report":
        a, _ = _sessions_for_report(tmp)
        from adroit.orchestrator import cli
        path = tmp / "report.md"
        return path, other, lambda: cli.session_report(a, sus=None, usage=None, out=path)
    if writer == "a signal draft":
        from adroit.orchestrator import cli
        path = tmp / "draft.yaml"
        return path, other, lambda: cli._write_new(path, "SIMULATED draft")
    if writer == "an approved model":
        from adroit.orchestrator.model_approval import write_approved
        path, (spec, approval) = tmp / "approved.yaml", _model(tmp)
        return path, other, lambda: write_approved(path, spec, approval)
    if writer == "a model export":
        from adroit.library.personal import Catalog
        from tests.library.test_personal import save
        catalog = Catalog(tmp / "library")
        revision = save(catalog)
        path = tmp / "model.yaml"
        return path, other, lambda: catalog.export_model(revision.reference, path)
    if writer == "a review timer":
        from adroit.constraints.review import start_timing
        from adroit.constraints.review_packets import packet_for
        path = tmp / "timing.json"
        return path, other, lambda: start_timing(packet_for(A), "P1", "assisted", path)
    if writer == "a session start":
        from adroit.orchestrator.cli import session_start
        path = tmp / "session.json"
        return path, other, lambda: session_start(path, "P1", "task", "0" * 64, "manual", assistance_result=None)
    raise ValueError(writer)


CREATE_ONLY = ("the usability report", "a signal draft", "an approved model", "a model export", "a review timer",
               "a session start")


@pytest.mark.parametrize("writer", CREATE_ONLY)
def test_every_create_only_writer_keeps_a_file_written_meanwhile(tmp_path, monkeypatch, writer):
    """DM-02's contract, each writer of a new file a person names whose promise is that it never replaces one: another
    file written at its path after its check (``test_dl_fixes._appears``, at the create-only write itself) is left as
    it is, and the writer refuses, saying so (an approved model, another model's: "cannot be overwritten"). The
    bundle ZIP, the evidence commands' folders and an experimental import's folder have their own (DL-05,
    ``test_an_experimental_import_into_a_folder_written_meanwhile_is_refused``)."""
    path, other, write = _create_only(writer, tmp_path, monkeypatch)
    with _appears(path, other), pytest.raises((ValueError, typer.BadParameter, FileExistsError)) as raised:
        write()
    assert path.read_bytes() == other
    assert re.search(r"meanwhile|another run|cannot be overwritten|already exists", str(raised.value)), raised.value
    assert not [p for p in path.parent.iterdir() if p.name.startswith(f".{path.name}.")], "a temporary file was left"


def test_an_approved_model_written_meanwhile_as_the_same_model_is_kept(tmp_path):
    """DM-02's class, the approved model: the same model's approval written at its path meanwhile is kept, and the
    writer returns (its promise: never another model)."""
    from adroit.orchestrator.model_approval import write_approved
    spec, approval = _model(tmp_path)
    path, first = tmp_path / "approved.yaml", tmp_path / "first.yaml"
    write_approved(first, spec, approval)
    with _appears(path, first.read_bytes()):
        write_approved(path, spec, approval)
    assert path.read_bytes() == first.read_bytes()


def test_an_experimental_import_into_a_folder_written_meanwhile_is_refused(tmp_path, monkeypatch):
    """DM-02's class, ``adroit experiments import --out`` (a new or empty folder): another import completes there after
    A's check, during A's import; A's export is refused once it holds the folder, B's files left as B wrote them.
    Before, A's replaced B's."""
    from adroit.core.config import get_settings
    from adroit.library.experimental import ExperimentalCatalog
    monkeypatch.setattr(get_settings(), "experimental_library_dir", tmp_path / "private")
    out, real, theirs = tmp_path / "import", ExperimentalCatalog.import_files, {}

    def meanwhile(self, *args, **kwargs):
        if not theirs:
            theirs["done"] = True
            with patch.object(ExperimentalCatalog, "import_files", real):
                assert _import(tmp_path, out, "B's search").exit_code == 0
            theirs["files"] = files(out)
        return real(self, *args, **kwargs)
    with patch.object(ExperimentalCatalog, "import_files", meanwhile):
        done = _import(tmp_path, out, "A's search")
    assert done.exit_code != 0 and "no longer new or empty" in said(done.output), done.output
    assert files(out) == theirs["files"] and b"B's search" in (out / "report.md").read_bytes()


PROMISE = re.compile(r"existing (file|--out|path)[^.\"]{0,30}(is|are) (refused|never replaced)|an existing file is "
                     r"refused|never replaces another|cannot (be )?overwrit|already exists|must be new|new or empty|"
                     r"never overwritten|is never replaced|choose a new (file|folder)|written only where no file is",
                     re.IGNORECASE)
# each promise of a new file in ADROIT's code, by its function, and where it is kept (or why it is not a file a person
# names): an inventory a new promise must join (the auditor's DL recheck, DM-02: only some writers had been moved)
PROMISES = {
    "constraints/review.py:start_timing": "a review timer",
    "evidence/archive.py:export_run": "test_dl_fixes: the bundle ZIP (DL-05)",
    "evidence/cli.py:export": "test_dl_fixes: the bundle ZIP (DL-05)",
    "evidence/cli.py:_write": "test_dl_fixes: the evidence commands' folders (DL-05)",
    "library/personal.py:export_model": "a model export",
    "orchestrator/catalog_cli.py:export": "a model export",
    "orchestrator/cli.py:session_start": "a session start",
    "orchestrator/cli.py:session_report": "the usability report",
    "orchestrator/cli.py:anomaly_draft": "a signal draft",
    "ui/forms.py:output_clash": "a signal draft (the page's check before the command's own)",
    "ui/wizards.py:_draft_section": "a signal draft (the page's check before the command's own)",
    "orchestrator/model_approval.py:write_approved": "an approved model",
    "orchestrator/experimental_cli.py:import_files": "an experimental import",
    "core/durable.py:export": "the primitive itself (its fresh folder, an experimental import's)",
    "library/personal.py:save": "not a person's path: a revision named by its content, written under the library's lock",
    "library/experimental.py:save": "not a person's path: a revision named by its content, under the library's lock",
    "orchestrator/model_intake.py:_save": "not a person's path: an intake step named by its content",
    "agents/budget.py:MissingJournal": "not a new file: a lost ledger is never made anew (CO-05)",
    "agents/budget.py:__init__": "not a new file: a lost ledger is never made anew (CO-05)",
    "agents/budget.py:recover_torn_tail": "not a new file: a lost ledger is never made anew (CO-05)",
    "ui/pages.py:_status_row": "not a file: a button never replaced under a click",
}


def _promises() -> set[str]:
    """Each function of ``adroit`` whose code or words make a promise ``PROMISE`` matches (``module:function``)."""
    found = set()
    for path in sorted((ROOT / "adroit").rglob("*.py")):
        text = path.read_text()
        lines = [n for n, line in enumerate(text.splitlines(), 1) if PROMISE.search(line)]
        if not lines:
            continue
        spans = [(node.lineno, node.end_lineno, node.name) for node in ast.walk(ast.parse(text))
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        for n in lines:
            inner = min((s for s in spans if s[0] <= n <= s[1]), key=lambda s: s[1] - s[0], default=None)
            found.add(f"{path.relative_to(ROOT / 'adroit')}:{inner[2] if inner else '<module>'}")
    return found


def test_every_promise_of_a_new_file_is_in_the_create_only_inventory():
    """DM-02: the auditor found one create-only report writer still replacing; every promise of a new file in ADROIT's code
    is listed in ``PROMISES``, each with the test that keeps it (or why it is not a new file a person names)."""
    found = _promises()
    assert found == set(PROMISES), (f"promises not in the inventory: {sorted(found - set(PROMISES))}; listed, no "
                                    f"longer found: {sorted(set(PROMISES) - found)}")
    kept = {where for where in PROMISES.values() if not where.startswith(("not ", "test_dl_fixes", "the primitive"))}
    assert {w.split(" (")[0] for w in kept} <= {*CREATE_ONLY, "an experimental import"}


# --- DM-03: an export never leaves part of another beside its own ------------------------------------------------

def _timer(out: Path, tmp: Path) -> str:
    """``adroit records timer-start`` on the folder's packet, its session in the test's own folder: "accepted", or the
    refusal's words."""
    from adroit.constraints.review_cli import timer_start
    session = tmp / f"timing {len(list(tmp.glob('timing *')))}.json"
    try:
        with redirect_stdout(StringIO()):
            timer_start(out / "record_review.json", session, "P1", condition="assisted")
    except typer.BadParameter as error:
        assert not session.exists()
        return str(error)
    assert session.exists()
    return "accepted"


def _session(out: Path, label: str = "SIMULATED") -> None:
    """A discovery's export (``preflight.session_export``): its request record, ``discovery.json`` and ``report.md``."""
    from adroit.orchestrator import preflight
    preflight.session_export(out, Requests(f"r-{label}"), label, {"discovery.json": json.dumps({"session": label}),
                                                                 "report.md": f"# Survey {label}\n"})


def _theory(out: Path, tmp: Path) -> None:
    """A theory check (``adroit theory vacuum``): ``vacuum.json`` and ``report.md``."""
    import yaml

    from adroit.parameter_space.library import entry
    from adroit.theory.cli import app
    source = tmp / "model.yaml"
    source.write_text(yaml.safe_dump(entry("higgs_portal_scalar").spec().model_dump(mode="json")))
    done = CliRunner().invoke(app, ["vacuum", str(source), "--out", str(out)])
    if done.exit_code:
        raise typer.BadParameter(said(done.output))


def _export(kind: str, out: Path, tmp: Path) -> None:
    """One export of ``kind`` into ``out``, as its command writes it."""
    from tests import version_matrix as vm
    if kind == "the review":
        review(A, out)
    elif kind == "the queue as report.json":
        queue(out / "report.json", [vm.make(tmp / "study").folder])
    elif kind == "a discovery's":
        _session(out)
    else:
        _theory(out, tmp)


KINDS = ("the review", "the queue as report.json", "a discovery's", "a theory check")
PAIRS = [(first, then) for first in KINDS for then in KINDS if first != then]


@pytest.mark.parametrize("first, then", PAIRS)
def test_an_export_of_another_kind_never_replaces_part_of_one_in_its_folder(tmp_path, first, then):
    """DM-03, the auditor's case and its kind: ``first`` exported whole into a folder, then ``then`` (each sharing
    ``report.md`` with it). The second is refused, saying which export it would leave part of, nothing written: the
    folder holds the first whole, and a review packet there is still accepted by the review timer. Before, the queue
    exported as ``report.json`` replaced the packet's report, and the timer accepted the packet beside the queue's."""
    out = tmp_path / "export"
    _export(first, out, tmp_path)
    before = files(out)
    with pytest.raises((ValueError, typer.BadParameter), match="holds another export") as raised:
        _export(then, out, tmp_path)
    assert "report.md" in str(raised.value) and files(out) == before and not durable.interrupted(out)
    if first == "the review":
        assert whose(out)[:2] == (A, A) and _timer(out, tmp_path) == "accepted"


def test_the_queue_command_refuses_a_report_json_beside_a_review_packet(tmp_path):
    """DM-03, the auditor's commands (``adroit records review … --out F``, then ``adroit records queue --run … --out
    F/report.json``): the queue's command exits 2, saying why, and the packet is A's whole, accepted by the timer."""
    from adroit.orchestrator.cli import app
    from tests import version_matrix as vm
    out = tmp_path / "packet"
    assert CliRunner().invoke(app, ["records", "review", A, "--out", str(out)]).exit_code == 0
    before = files(out)
    done = CliRunner().invoke(app, ["records", "queue", "--run", str(vm.make(tmp_path / "study").folder), "--out",
                                    str(out / "report.json")])
    assert done.exit_code == 2 and "holds another export" in said(done.output), done.output
    assert files(out) == before and _timer(out, tmp_path) == "accepted"


def test_an_export_replaces_its_own_kind_whole_and_keeps_another_s_files(tmp_path):
    """DM-03: a review packet and a discovery's export sharing no file can sit in one folder, each recorded
    (``RECORD``); a review exported again replaces its packet whole, B's, the discovery's files and their record
    kept; then the timer accepts B's packet."""
    out = tmp_path / "export"
    review(A, out)
    queue(out / "queue.json", [])
    kept = {name: data for name, data in files(out).items() if name.startswith("queue.")}
    review(B, out)
    assert whose(out)[:2] == (B, B) and {n: files(out)[n] for n in kept} == kept
    exports = json.loads((out / RECORD).read_text())["exports"]
    assert sorted(sorted(e["files"]) for e in exports) == [sorted(PACKET), ["queue.json", "queue.md"]]
    assert coherent_queue(out) and _timer(out, tmp_path) == "accepted"


def test_an_export_whose_earlier_one_s_other_files_are_gone_replaces_what_is_left(tmp_path):
    """DM-03: A's packet recorded, its record and figure then removed by a person: the queue exported as
    ``report.json`` leaves nothing of the packet beside its own, and replaces its report; the record names only the
    queue."""
    out = tmp_path / "export"
    review(A, out)
    (out / "record_review.json").unlink()
    (out / "current_curves.png").unlink(missing_ok=True)
    _export("the queue as report.json", out, tmp_path)
    exports = json.loads((out / RECORD).read_text())["exports"]
    assert [sorted(e["files"]) for e in exports] == [["report.json", "report.md"]]


THERE = ("a person's file", "a link to another folder's file", "an earlier ADROIT's export")


@pytest.mark.parametrize("there", THERE)
def test_an_export_never_replaces_an_entry_no_export_recorded_there(tmp_path, there):
    """DM-03: ``report.md`` in the folder, a person's own, a link to another folder's file, or an earlier ADROIT's
    review packet (its files with no record of them): the review's export there is refused, naming it, nothing written,
    the link's target untouched. Before, each was replaced."""
    out, elsewhere = tmp_path / "export", tmp_path / "elsewhere.md"
    elsewhere.write_text("SIMULATED another folder's")
    out.mkdir()
    if there == "a person's file":
        (out / "report.md").write_text("my notes")
    elif there.startswith("a link"):
        (out / "report.md").symlink_to(elsewhere)
    else:
        review(B, out)
        (out / RECORD).unlink()
    before = files(out)
    with pytest.raises(typer.BadParameter, match="which no export recorded there"):
        review(A, out)
    assert files(out) == before and elsewhere.read_text() == "SIMULATED another folder's"


@pytest.mark.parametrize("record", ["torn", "a list", "an export without files", "a link"])
def test_a_folder_whose_record_cannot_be_read_takes_no_export(tmp_path, record):
    """DM-03: a folder whose record of its exports (``RECORD``) cannot be read: an export there is refused, nothing
    written (it cannot tell another export's files from its own), and the timer refuses a packet there."""
    out = tmp_path / "export"
    review(A, out)
    (out / RECORD).unlink()
    if record == "a link":
        (tmp_path / "elsewhere.json").write_text(json.dumps({"exports": []}))
        (out / RECORD).symlink_to(tmp_path / "elsewhere.json")
    else:
        (out / RECORD).write_text({"torn": '{"exports": [', "a list": "[]",
                                   "an export without files": '{"exports": [{"files": {}}]}'}[record])
    before = files(out)
    with pytest.raises(typer.BadParameter, match=f"record of its exports \\({RECORD}\\) cannot be read"):
        review(B, out)
    assert files(out) == before and "cannot be read" in _timer(out, tmp_path)


TAMPERED = {"its report replaced": lambda out: (out / "report.md").write_text("# Requested-result review queue\n"),
            "its figure removed": lambda out: (out / "current_curves.png").unlink(),
            "its figure a link": lambda out: ((out / "current_curves.png").unlink(),
                                              (out / "current_curves.png").symlink_to(out / "report.md")),
            "no record": lambda out: (out / RECORD).unlink(),
            "its record another export's": lambda out: (out / RECORD).write_text(durable._record(
                [{"report.json": None, "report.md": None}]))}


@pytest.mark.parametrize("change", TAMPERED)
def test_the_review_timer_reads_a_packet_only_as_its_export_wrote_it(tmp_path, change):
    """DM-03's reader: the timer accepts a packet only where the folder's record names its export and each of its
    files is as written. A report replaced by hand (the queue's), a figure removed or made a link, no record (an
    earlier ADROIT's export), or a record naming another export: refused, saying why."""
    out = tmp_path / "export"
    review(A, out)
    assert _timer(out, tmp_path) == "accepted"
    TAMPERED[change](out)
    refused = _timer(out, tmp_path)
    assert refused != "accepted" and "export the review again" in refused, refused


def test_two_exports_of_different_kinds_at_once_leave_one_whole(tmp_path):
    """DM-03 under contention: the review and the queue (as ``report.json``) exported into one folder at once, each
    waiting for the folder's hold: one completes, the other is refused, and the folder holds the first whole."""
    from tests import version_matrix as vm
    out, study, outcomes = tmp_path / "export", vm.make(tmp_path / "study").folder, {}
    out.mkdir()

    def run(kind, write):
        try:
            write()
            outcomes[kind] = "written"
        except (ValueError, typer.BadParameter) as error:
            outcomes[kind] = str(error)
    threads = [threading.Thread(target=run, args=("review", lambda: review(A, out))),
               threading.Thread(target=run, args=("queue", lambda: queue(out / "report.json", [study])))]
    with durable.publishing(out):
        for thread in threads:
            thread.start()
        threading.Event().wait(1)
    for thread in threads:
        thread.join(120)
    assert sorted(o == "written" for o in outcomes.values()) == [False, True], outcomes
    winner = next(kind for kind, o in outcomes.items() if o == "written")
    assert "holds another export" in outcomes["queue" if winner == "review" else "review"]
    if winner == "review":
        assert whose(out)[:2] == (A, A) and _timer(out, tmp_path) == "accepted"
    else:
        assert (out / "report.md").read_text().startswith("# Requested-result review queue")
        assert json.loads((out / "report.json").read_text()) and "record_review.json" not in files(out)


KILLED_RECORD = """
import sys, time
from pathlib import Path
from adroit.core import durable
out, source = map(Path, sys.argv[1:])
real = durable.write_atomic
def atomic(path, data):
    if Path(path).name == durable.RECORD:
        print("written", flush=True)
        time.sleep(600)
    return real(path, data)
durable.write_atomic = atomic
durable.export(out, {name: (source / name).read_bytes() for name in ("record_review.json", "report.md",
                                                                      "current_curves.png")})
"""


def test_an_export_killed_before_its_record_reads_as_incomplete(tmp_path):
    """DM-03 and DK-05: B's review export killed after its last file, before the record names it: the folder reads as
    incomplete (the timer refuses it), the record still names A's export, and the review exported again completes it,
    the mark removed and the record naming its files."""
    out = tmp_path / "export"
    review(A, out)
    review(B, tmp_path / "B alone")
    child = subprocess.Popen([sys.executable, "-c", KILLED_RECORD, str(out), str(tmp_path / "B alone")], cwd=ROOT,
                             stdout=subprocess.PIPE, text=True)
    assert child.stdout.readline().strip() == "written"
    child.send_signal(signal.SIGKILL)
    child.wait(60)
    assert durable.interrupted(out) and whose(out)[:2] == (B, B)
    assert "was interrupted" in _timer(out, tmp_path)
    review(B, out)
    assert not durable.interrupted(out) and _timer(out, tmp_path) == "accepted"


def test_an_export_whose_record_cannot_be_written_says_so(tmp_path):
    """DM-03 and DL-03: the record failing once the export's files are written: ``ExportFailed``, saying the files
    were written and the folder reads as incomplete; the mark stays."""
    out, real = tmp_path / "export", durable.write_atomic
    durable.export(out, {"a.json": "A", "a.md": "A"})

    def failing(path, data):
        if Path(path).name == RECORD:
            raise OSError("SIMULATED disk full")
        return real(path, data)
    with patch.object(durable, "write_atomic", failing), \
            pytest.raises(durable.ExportFailed, match=f"the record of them \\({RECORD}\\) could not be written"):
        durable.export(out, {"a.json": "B", "a.md": "B"})
    assert durable.interrupted(out) and (out / "a.json").read_text() == "B"


def test_an_export_cannot_name_adroit_s_own_files(tmp_path):
    """DM-03: an export naming ``RECORD`` or ``INCOMPLETE`` among its files is refused, nothing written."""
    for name in (RECORD, INCOMPLETE):
        with pytest.raises(ValueError, match="ADROIT keeps that file"):
            durable.export(tmp_path / "out", {name: "{}"})
    assert not (tmp_path / "out").exists()


def test_the_create_only_contract_detects_a_writer_that_replaces(tmp_path, monkeypatch):
    """DM-02's defect restored, the contract's negative control: the create-only write replacing whatever is there (as
    the usability report's ``write_atomic`` did at the pin): the contract fails for that writer."""
    with patch.object(durable, "write_new", durable.write_atomic), pytest.raises(pytest.fail.Exception):
        test_every_create_only_writer_keeps_a_file_written_meanwhile(tmp_path, monkeypatch, "the usability report")

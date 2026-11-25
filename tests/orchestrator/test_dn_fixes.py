"""The auditor's DM recheck (2026-11-08), DN-01: a record of a run's or a session's money whose entry is there but leads to
nothing that can be read (a link to a missing file, a link to itself, a link through a file) is damage, never no
record. ``Path.exists`` answers False for those, so a discovery run whose request record was such a link had read as a
run from before request records, and been charged with its ``discovery.json``'s session: A's "$1.25 … ($8.75 left)" as
this run's, its page linking to A's session. Every reader that decides a run's or a session's money by whether a record
is there now asks whether an entry is (``durable.absent``), and an inventory keeps them so. Every dollar is simulated;
no provider is contacted and nothing is sent."""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from adroit.core import durable
from adroit.orchestrator.model_intake import REQUESTS, RunRequests
from tests.orchestrator.test_dm_fixes import _charged

ROOT = Path(__file__).parents[2]


def _missing(entry: Path) -> None:
    entry.symlink_to(entry.parent / "missing.json")


def _itself(entry: Path) -> None:
    entry.symlink_to(entry.name)


def _through(entry: Path) -> None:
    (entry.parent / "a file").write_text("")
    entry.symlink_to(entry.parent / "a file" / "inside")


# the three ways an entry leads nowhere that Path.exists reads as nothing there (ENOENT, ELOOP, ENOTDIR)
LINKS = {"a link to a missing file": _missing, "a link to itself": _itself, "a link through a file": _through}


def leads_nowhere(entry: Path, link: str) -> Path:
    """``entry`` made ``link`` (``LINKS``): there, as ``os.path.lexists`` sees it, and not, as ``Path.exists`` does."""
    LINKS[link](entry)
    assert os.path.lexists(entry) and not entry.exists()
    return entry


# --- the auditor's case: a survey's request record that leads nowhere ----------------------------------------------------

def linked_survey(tmp: Path, ids: dict, link: str, log: str = "") -> Path:
    """The auditor's ``dm_dangling_request`` case: a survey folder holding an earlier survey's ``discovery.json`` (session A's)
    and this run's request record, an entry that leads nowhere (``LINKS``); a log only where given."""
    out = tmp / "survey"
    out.mkdir(parents=True)
    (out / "discovery.json").write_text(json.dumps({"session": ids["a"]}))
    leads_nowhere(out / REQUESTS, link)
    if log:
        (out / "log.txt").write_text(log)
    return out


@pytest.mark.parametrize("link", LINKS)
def test_a_request_record_that_leads_nowhere_charges_the_run_with_no_session(tmp_path, monkeypatch, link):
    """DN-01, the auditor's case: a discover run (attempt B) whose request record is a link that leads nowhere, beside an
    earlier survey's ``discovery.json`` naming session A, with no log: nothing bound to the run names its session. No
    figure is given for the run, its session or its cap, the record is named, and no session is linked, by the reader
    (``ledger_session``) or by the run's page (its continuation). Before, the run was charged with A's session, "$1.25 …
    ($8.75 left)", its page linking to A's."""
    from adroit.orchestrator import accounting
    from adroit.ui import outcomes
    cost, lines, out, job, _ = _charged(tmp_path, monkeypatch, lambda ids: linked_survey(tmp_path, ids, link))
    assert (cost.session_id, cost.run_usd, cost.session_spent_usd, cost.session_cap_usd,
            cost.session_remaining_usd) == ("", None, None, None, None)
    assert f"the run's request record ({REQUESTS}) cannot be read (a link to " in lines[0]
    assert "its session is not established" in lines[0] and lines[1] == "Session total: not available"
    shown = " ".join([*lines, accounting.short_line(cost)])
    assert not re.search(r"\$\d", shown), shown
    assert accounting.ledger_session(out, job) == ("", "source")
    assert outcomes.discovery_outcome(out.parent, out, job).primary is None


@pytest.mark.parametrize("bound", ["its log", "its command"])
@pytest.mark.parametrize("link", LINKS)
def test_a_request_record_that_leads_nowhere_beside_a_bound_record_is_charged_with_that_session(tmp_path, monkeypatch,
                                                                                                link, bound):
    """DN-01's controls: the record a link that leads nowhere, and a record bound to the run naming B's session, its
    log (naming its attempt) or its command (a resume of B): the run is charged with B's session, $8.50 of its $10.00
    cap ($1.50 left), A's ``discovery.json`` named as not this run's, the record named, giving no own figure, and the
    page's continuation B's session."""
    from adroit.ui import outcomes
    log = "# run attempt attempt-b\ndiscovery session {b} for SIMULATED model\n" if bound == "its log" else ""
    cost, lines, out, job, ids = _charged(tmp_path, monkeypatch, lambda ids: linked_survey(
        tmp_path, ids, link, log.replace("{b}", ids["b"])), "discover" if bound == "its log" else "resume")
    assert (cost.run_usd, cost.session_spent_usd, cost.own_usd) == (8.5, 8.5, None)
    assert lines[0].startswith("This run's session: $8.50") and "its discovery.json names another session" in lines[0]
    assert f"the run's request record ({REQUESTS}) cannot be read (a link to " in lines[0]
    assert lines[1] == "Session total so far: $8.50 spent of its approved $10.00 cap ($1.50 left)"
    assert outcomes.discovery_outcome(out.parent, out, job).primary.target.endswith(f"session={ids['b']}")


@pytest.mark.parametrize("receipt", ["none", "one bound to the run"])
@pytest.mark.parametrize("link", LINKS)
def test_a_log_that_leads_nowhere_is_damage_not_a_run_from_before_logs(tmp_path, monkeypatch, link, receipt):
    """The run's other record of its session, its log, read by the same rule: a link that leads nowhere is named. With
    no request record, its ``discovery.json``'s session (A's) is not taken, for the log may have named another (it was:
    the log read as none, the run as one from before them); with a request record bound to the run naming B's session,
    B's, the log named beside the figure."""
    def survey(ids: dict) -> Path:
        out = tmp_path / "survey"
        out.mkdir()
        (out / "discovery.json").write_text(json.dumps({"session": ids["a"]}))
        if receipt != "none":
            (out / REQUESTS).write_text(RunRequests(session_id=ids["b"], request_ids=["b"], attempt="attempt-b")
                                        .model_dump_json())
        leads_nowhere(out / "log.txt", link)
        return out
    cost, lines, *_, ids = _charged(tmp_path, monkeypatch, survey)
    assert "its log (log.txt) cannot be read (a link to " in " ".join(lines)
    if receipt == "none":
        assert (cost.session_id, cost.run_usd, cost.session_spent_usd) == ("", None, None)
        assert "its session is not established" in lines[0] and lines[1] == "Session total: not available"
    else:
        assert (cost.session_id, cost.session_spent_usd, cost.own_usd) == (ids["b"], 8.5, 8.5)


# --- the same rule at every reader of a run's money ---------------------------------------------------------------

@pytest.mark.parametrize("link", LINKS)
def test_the_common_record_reader_names_an_entry_that_leads_nowhere(tmp_path, link):
    """``durable.read_object`` (a result's, a study's or a budget stop's record): no entry, absent; an entry that leads
    nowhere, a record that cannot be read, said to be a link (it read as absent)."""
    assert durable.read_object(tmp_path / "result.json") == (None, "")
    data, why = durable.read_object(leads_nowhere(tmp_path / "result.json", link))
    assert data is None and why.startswith("cannot be read (a link to "), why


def _paid_run(folder: Path) -> Path:
    """A finished paid run (``adroit idea --budget 1``): its own paid ledger opened empty, an empty log, no result."""
    from adroit.ui import engine
    folder.mkdir(parents=True)
    engine.save(engine.Job(title="the run", kind="idea", command=["idea", "--text", "x", "--budget", "1", "--out", "."],
                           folder=str(folder), status="failed", returncode=3))
    (folder / "paid.jsonl").write_text("")
    (folder / "log.txt").write_text("")
    return folder


RUN_RECORDS = {"its paid ledger": "paid.jsonl", "its log": "log.txt", "its result record": "result.json"}


@pytest.mark.parametrize("record", RUN_RECORDS)
@pytest.mark.parametrize("link", LINKS)
def test_a_paid_run_s_record_that_leads_nowhere_is_named_and_nothing_certified(tmp_path, link, record):
    """A paid run whose empty ledger certifies that no paid request was sent: with its ledger, its log or its result
    record (perhaps a budget stop's) a link that leads nowhere, the record is named, and "no paid request was sent" is
    not said; with its ledger such a link, no figure is given (the ledger had read as none, the run's figure then taken
    from its other records; the log and the result as none, so nothing contradicted the empty ledger)."""
    from adroit.orchestrator import accounting
    from adroit.ui import engine
    folder = _paid_run(tmp_path / "run")
    assert accounting.cost(folder, engine.load(folder)).sent_none          # as built: none sent, said
    (folder / RUN_RECORDS[record]).unlink(missing_ok=True)
    leads_nowhere(folder / RUN_RECORDS[record], link)
    c = accounting.cost(folder, engine.load(folder))
    assert not c.sent_none and "(a link to " in " ".join(c.damaged), c
    assert c.run_usd is None if record == "its paid ledger" else c.run_usd == 0
    assert "no paid request was sent" not in accounting.run_line(c)


@pytest.mark.parametrize("link", LINKS)
def test_a_study_whose_run_record_leads_nowhere_is_not_read_as_a_command_line_study(tmp_path, link):
    """A study's cost: with no run record (``job.json``) at all, a study from the command line, its record's dollars;
    with one that leads nowhere, its run's record cannot be read, and no figure (it read as the former)."""
    from adroit.orchestrator import accounting
    folder = tmp_path / "study"
    folder.mkdir()
    assert accounting.study_cost(folder, recorded_usd=0.4).run_usd == 0.4
    leads_nowhere(folder / "job.json", link)
    c = accounting.study_cost(folder, recorded_usd=0.4)
    assert c.run_usd is None and c.damaged == ["its run's record, job.json, cannot be read"]


# --- a session's paid ledger -------------------------------------------------------------------------------------

@pytest.mark.parametrize("link", LINKS)
def test_a_session_s_ledger_that_leads_nowhere_blocks_its_budget(tmp_path, link):
    """CO-05's rule for a lost ledger, kept for one that is there but leads nowhere: a session that has spent, its
    ledger replaced by such a link. Every reading of its money refuses, saying the ledger cannot be read; nothing is
    sent, its cap is not raised, and the link is left as it was."""
    from tests.agents.test_budget_reservations import client
    from tests.orchestrator.test_missing_journal import _session
    service, s, ledger = _session(tmp_path)
    ledger.unlink()
    leads_nowhere(ledger, link)
    blocked = "the paid ledger is there but cannot be read"
    for read in (lambda: service.budget_status(s.session_id), lambda: service.requests(s.session_id),
                 lambda: service.snapshot(s.session_id), lambda: service.account(service.session(s.session_id))):
        with pytest.raises(ValueError, match=blocked):
            read()
    sent = []
    with pytest.raises(ValueError, match=blocked):
        client(tmp_path, account=service.account(service.session(s.session_id)), send=lambda **k: sent.append(k))
    with pytest.raises(ValueError, match=blocked):
        service.raise_cap(s.session_id, 1.0, confirmed=True)
    assert not sent and ledger.is_symlink() and service.session(s.session_id).budget == 0.05


@pytest.mark.parametrize("link", LINKS)
def test_an_older_session_whose_ledger_leads_nowhere_is_blocked_and_none_made_in_its_place(tmp_path, link):
    """A paid session from before 2026-10-25, with no sign of spending: with no ledger at all, its first account makes
    one (``test_missing_journal``); with one that leads nowhere, its money cannot be read, and no empty ledger is made
    over the link (it read as none: its whole cap shown remaining, and an empty ledger written in the link's place)."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake, Session, session_identity
    service = Intake(Catalog(tmp_path / "models"))
    s = Session(session_id="a" * 32, budget=0.05)
    s.integrity_sha256 = session_identity(s)
    folder = service.folder(s.session_id)
    folder.mkdir(parents=True)
    (folder / "session.json").write_text(s.model_dump_json())
    leads_nowhere(folder / "paid.jsonl", link)
    for read in (lambda: service.budget_status(s.session_id), lambda: service.account(service.session(s.session_id))):
        with pytest.raises(ValueError, match="the paid ledger is there but cannot be read"):
            read()
    assert (folder / "paid.jsonl").is_symlink() and not service.session(s.session_id).journal


TORN = ('{"id": "r1", "state": "reserved", "provider": "anthropic", "model": "SIMULATED", "reserved_usd": 0.1}\n'
        '{"id": "r1", "state": "sett')


@pytest.mark.parametrize("link", LINKS)
def test_recovery_refuses_beside_a_run_record_that_leads_nowhere(tmp_path, link):
    """``adroit ledger recover`` never mends a ledger a run may still be writing: beside a run record that leads
    nowhere, the run may be going, as with one that cannot be read (it read as no run, and the ledger was rewritten)."""
    from adroit.agents.budget import recover_torn_tail
    control, folder = tmp_path / "control", tmp_path / "run"
    for each in (control, folder):
        each.mkdir()
        (each / "paid.jsonl").write_text(TORN)
    recover_torn_tail(control / "paid.jsonl")                       # no run record: recovered
    leads_nowhere(folder / "job.json", link)
    with pytest.raises(ValueError, match=r"its run is still going \(or its job record cannot be read\)"):
        recover_torn_tail(folder / "paid.jsonl")
    assert (folder / "paid.jsonl").read_text() == TORN


@pytest.mark.parametrize("link", LINKS)
def test_the_answer_recovery_readers_never_read_a_ledger_that_leads_nowhere_as_none(tmp_path, link):
    """A survey's relevance answer, or an extraction's, already paid for: read back from the session's ledger before a
    request is made again. A ledger that leads nowhere refuses (it read as none, and a new request was then prepared,
    stopped only later by the budget's own reading)."""
    from adroit.orchestrator.constraint_discovery import Discovery
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    leads_nowhere(tmp_path / "paid.jsonl", link)
    budgets = SimpleNamespace(folder=lambda session: tmp_path)
    blocked = "the paid ledger is there but cannot be read"
    with pytest.raises(ValueError, match=blocked):
        Discovery._recovered(SimpleNamespace(budgets=budgets, _read=lambda *args: None), SimpleNamespace(session_id="s"))
    with pytest.raises(ValueError, match=blocked):
        ExperimentalExtraction._recovered(SimpleNamespace(budgets=budgets, _pending=lambda *args: tmp_path / "none"),
                                          "s", "s", "i")


# --- whether a paid request may be sent ---------------------------------------------------------------------------

@pytest.mark.parametrize("link", LINKS)
def test_a_cancel_file_that_leads_nowhere_stops_the_run(tmp_path, link):
    """A run's or a batch's cancel request (``control.json``) that cannot be read stops it, never permits the next
    request (M3); one that leads nowhere had read as none, and the batch's next request was dispatched."""
    from adroit.ui import batch, engine
    folder = tmp_path / "run"
    folder.mkdir()
    assert not engine.cancelled(folder) and not batch.cancelled(folder)
    leads_nowhere(folder / engine.CONTROL, link)
    assert engine.cancelled(folder) and batch.cancelled(folder)
    assert engine.control_unreadable(folder).startswith(f"its control file, {engine.CONTROL}, cannot be read")


DISPATCH_RECORDS = ("the batch's", "the runs folder's", "both")


@pytest.mark.parametrize("records", DISPATCH_RECORDS)
@pytest.mark.parametrize("link", LINKS)
def test_a_dispatch_record_that_leads_nowhere_never_permits_a_dispatch_again(tmp_path, link, records):
    """RC20-01's case (``test_batch``): an approved $0.50 request completed, its job removed, the batch and item put
    back to running and queued; with the batch's record of its dispatches, the runs folder's, or both, a link that
    leads nowhere. It is not sent again, and the links are left: where the batch's own record shows its dispatch, the
    item fails as already launched; where that record cannot be read, saying whether it was sent is not known. Before,
    each read as no record, and with both so the request was dispatched a second time ($1.00 sent of a $0.50
    confirmation)."""
    from adroit.ui import batch, engine
    from tests.ui.test_batch import _batch, _completed, _run
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["paid"], [["idea", "--text", "x", "--budget", "0.5"]], confirmed=0.5)
    spent = []

    def launch(command, item_folder, title, confirmed_budget=0.0, owner=""):
        spent.append(confirmed_budget)
        engine.launch(command, item_folder, title, confirmed_budget, popen=lambda *a, **k: SimpleNamespace(pid=1),
                      owner=owner)
    done = _run(folder, approval, launch=launch, poll=_completed, sleep=lambda s: None)
    assert done.status == "completed" and spent == [0.5]
    damaged = {"the batch's": [folder / batch.LEDGER], "the runs folder's": [root / batch.DISPATCHES],
               "both": [folder / batch.LEDGER, root / batch.DISPATCHES]}[records]
    for path in damaged:
        path.unlink()
        leads_nowhere(path, link)
    (Path(done.items[0].folder) / engine.JOB).unlink()
    b = batch.load(folder)
    batch._save(b.model_copy(update={"status": "running", "finished": "",
                                     "items": [b.items[0].model_copy(update={"status": "queued", "error": ""})]}))
    again = _run(folder, approval, launch=launch, poll=_completed, sleep=lambda s: None)
    assert spent == [0.5] and again.items[0].status == "failed", (spent, again.items[0])
    said = ("this confirmation already launched the request" if records == "the runs folder's" else    # the batch's
            "whether this request was already sent is not known")                                     # own says so
    assert said in again.items[0].error, again.items[0].error
    assert all(path.is_symlink() for path in damaged)


@pytest.mark.parametrize("link", LINKS)
def test_a_running_item_whose_job_record_leads_nowhere_is_asked_to_stop_when_its_batch_is_cancelled(tmp_path, link):
    """A batch cancelled with no runner holding it (RC21-05): a running item whose job record leads nowhere may still be
    running, so its run is asked to stop (its control file written) and the item is cancelled. Before, it read as no
    job: the item marked cancelled, nothing asked of its run."""
    from adroit.ui import batch, engine
    from tests.ui.test_batch import _batch
    folder, _ = _batch(tmp_path / "runs", ["paid"], [["idea", "--text", "x", "--budget", "0.5"]], confirmed=0.5)
    b = batch.load(folder)
    batch._save(b.model_copy(update={"status": "running", "items": [b.items[0].model_copy(update={"status": "running"})]}))
    item = Path(b.items[0].folder)
    item.mkdir(parents=True, exist_ok=True)
    leads_nowhere(item / engine.JOB, link)
    batch.cancel(folder)
    assert batch.load(folder).items[0].status == "cancelled" and engine._asked(item)


@pytest.mark.parametrize("link", LINKS)
def test_a_study_card_and_a_batch_total_name_a_run_record_that_leads_nowhere(tmp_path, link):
    """The study's card (``pages.study_cost``) and a batch's spending (``batch_page._item_cost``) read a run record
    as the cost reader does: one that leads nowhere is the run's, damaged, never "no settled cost recorded" on the card
    or a run not started, left out of the batch's total."""
    from adroit.orchestrator import accounting, studies
    from adroit.orchestrator.study_headline import held
    from adroit.ui import batch_page, pages
    folder = tmp_path / "study"
    folder.mkdir()
    (folder / "result.json").write_text(json.dumps({"verdict": {"level": "viable"}}))
    studies.record(folder, "track1", "the study")
    leads_nowhere(folder / "job.json", link)
    assert pages.study_cost(held(folder)) == "cost: not available (its run's record, job.json, cannot be read)"
    cost = batch_page._item_cost(SimpleNamespace(folder=str(folder)))
    assert cost is not None and cost.damaged == ["its run's record, job.json, cannot be read"]
    assert accounting.total([cost]).unavailable == 1                  # counted, as not available


UNREAD_EVIDENCE = ("a step that leads nowhere", "a torn step", "a run's request record that leads nowhere")


@pytest.mark.parametrize("evidence", UNREAD_EVIDENCE)
def test_an_older_session_whose_only_sign_of_spending_cannot_be_read_is_blocked(tmp_path, monkeypatch, evidence):
    """CO-05's older session (from before 2026-10-25, no ledger flag), its ledger lost: its only sign of spending a
    step, or a run's request record, that cannot be read. It may be a paid one: the budget is blocked, saying so, and
    no ledger is made. Before, it read as no sign: the session one that never had a ledger, a new empty one made and
    its whole cap available. A readable free step is still no sign (the control)."""
    from adroit.agents.budget import MissingJournal
    from adroit.core.config import get_settings
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake, Session, session_identity
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(get_settings(), "runs_dir", runs)
    service = Intake(Catalog(tmp_path / "models"))

    def older(session_id: str) -> Path:
        s = Session(session_id=session_id, budget=0.05)
        s.integrity_sha256 = session_identity(s)
        folder = service.folder(session_id)
        (folder / "steps").mkdir(parents=True)
        (folder / "session.json").write_text(s.model_dump_json())
        return folder
    control = older("a" * 32)
    (control / "steps" / ("d" * 64 + ".json")).write_text(json.dumps({"kind": "typed"}))
    service.account(service.session("a" * 32))                       # no sign of spending: its ledger made
    assert (control / "paid.jsonl").is_file()
    folder = older("b" * 32)
    step = folder / "steps" / ("c" * 64 + ".json")
    if evidence == "a step that leads nowhere":
        leads_nowhere(step, "a link to a missing file")
    elif evidence == "a torn step":
        step.write_text('{"kind": "id')
    else:
        (runs / "run").mkdir()
        leads_nowhere(runs / "run" / REQUESTS, "a link to a missing file")
    with pytest.raises(MissingJournal, match="cannot be read"):
        service.account(service.session("b" * 32))
    assert not os.path.lexists(folder / "paid.jsonl")


# --- the inventory: no reader of money asks whether a record is there by following a link -------------------------

FOLLOWING = {"exists", "is_file"}           # Path's tests that follow a link, False for one that leads nowhere
MONEY_READERS = {                           # each module's readers of a run's or a session's money, or of whether a
    "adroit/orchestrator/accounting.py": None,  # paid request may be sent; None: all of the module
    "adroit/agents/budget.py": None,
    "adroit/core/durable.py": ["read_object", "append_held", "_appendable", "_unopened", "marked", "_displaced",
                               "_written_at", "_locked", "_as_written", "_recorded", "writing", "_writers_lock",
                               "_folder_at", "own", "read_own", "absent", "linked", "_in", "in_place", "one_entry"],
    # a ledger's writing (DO-01), what it may be appended after (DP-01), whether its path still leads to the file
    # written (DQ-02), and its writers' lock, what it holds once written and its mark read back (DR-01); the lock, its
    # folder's, which a recovery's replacement of it leaves (DS-01); the folder locked still the one at its path, and
    # the ledger read and written only by its own name (DT-01); every reading and writing under the lock made in the
    # folder locked, by name, and that folder still at its path before a recovery writes (DU-01); a client's ledger
    # known by what its path leads to (DU-02)
    "adroit/orchestrator/model_intake.py": ["Intake.requests", "Intake._journal", "Intake.account",
                                            "Intake.spending_evidence", "Intake.raise_cap", "Intake._open_journal",
                                            "Intake._spending_whole", "Intake._agreed"],   # its cap raises (DQ-03)
    "adroit/orchestrator/preflight.py": ["open_job_ledger"],
    "adroit/agents/llm.py": ["BudgetedLLMClient._journal", "BudgetedLLMClient._first_held", "BudgetedLLMClient._whole",
                             "BudgetedLLMClient._sendable", "BudgetedLLMClient._ledger"],
    # its whole check (DQ-03), its freeze (DQ-04), the ledger it journals to, its account's or its run's (DU-02)
    "adroit/orchestrator/experimental_extraction.py": ["ExperimentalExtraction._recovered"],
    "adroit/orchestrator/constraint_discovery.py": ["Discovery._recovered"],
    "adroit/ui/batch.py": ["_reserve", "_used", "_dispatched", "cancel", "_job_as_found"],
    "adroit/ui/batch_page.py": ["_item_cost"],
    "adroit/ui/engine.py": ["control_unreadable", "read_log", "tail"],
    "adroit/ui/activity.py": ["page"],          # a run's diagnosis, its log read apart from its reason (DP-03)
    "adroit/ui/outcomes.py": ["_stop_line"],
    "adroit/ui/pages.py": ["study_cost"],
}
EXEMPT = {("adroit/agents/budget.py", "recover_torn_tail"):
          "refuses to recover unless a journal can be read there, whether nothing is there or a link to nothing"}


def _following(source: str, functions: list[str] | None) -> list[tuple[str, int]]:
    """(each listed function, each line) of a call in ``source`` that asks whether a path is there by following a
    link: ``.exists()``, ``.is_file()``, ``os.path.exists`` or ``os.path.isfile``; every function's where None."""
    found: list[tuple[str, int]] = []

    def visit(node: ast.AST, scope: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, [*scope, child.name])
                continue
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                name, owner = child.func.attr, child.func.value
                dotted = ast.unparse(owner)
                if (name in FOLLOWING and dotted != "os.path") or (dotted == "os.path" and name in {"exists", "isfile"}):
                    where = ".".join(scope)
                    if functions is None or where in functions:
                        found.append((where, child.lineno))
            visit(child, scope)
    visit(ast.parse(source), [])
    return found


def test_every_reader_of_money_asks_whether_an_entry_is_there():
    """The inventory (DN-01): in every reader of a run's or a session's money (``MONEY_READERS``), whether a record is
    there is asked of its entry (``durable.absent``), never by following a link; ``EXEMPT`` names why one may. Each
    function listed exists, so the inventory names what it covers."""
    left = []
    for module, functions in MONEY_READERS.items():
        source = (ROOT / module).read_text()
        defined = {".".join(path) for path in _defined(ast.parse(source))}
        assert functions is None or set(functions) <= defined, (module, set(functions) - defined)
        left += [(module, where, line) for where, line in _following(source, functions)
                 if (module, where) not in EXEMPT]
    assert not left, left


def _defined(tree: ast.AST, scope: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    out = []
    for child in ast.iter_child_nodes(tree):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out += [(*scope, child.name), *_defined(child, (*scope, child.name))]
    return out


def test_the_inventory_detects_a_reader_that_follows_a_link():
    """The inventory's control: each form of the test it refuses, in a listed function, is found; the same in a
    function not listed is not."""
    source = ("import os\nclass Intake:\n    def _journal(self, p):\n        if p.exists(): pass\n"
              "        if p.is_file(): pass\n        if os.path.exists(p) or os.path.isfile(p): pass\n"
              "    def other(self, p):\n        return p.exists()\n")
    assert [where for where, _ in _following(source, ["Intake._journal"])] == ["Intake._journal"] * 4
    assert len(_following(source, None)) == 5

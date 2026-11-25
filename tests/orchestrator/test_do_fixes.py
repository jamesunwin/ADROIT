"""The auditor's DN recheck (2026-11-08), DO-01 and DO-02.

DO-01: a paid ledger's writers had made it anew under a run still writing to it. An append (``open("a")``) and
``touch`` follow a link: a ledger that was a link to nothing had its target made, and an empty ledger, or another put in
its place, was written on as the run's. The auditor's case: a session's live client settled a simulated $0.0008; its ledger was
then made a link to nothing, and the client's next request was sent, its reservation journalled in the link's new
target, so that the session read $0.0008 spent of its $0.05 cap ($0.0492 left), the first request lost from its durable
account. A run's job ledger opened on a link to nothing had become an empty ledger, and its page said that no paid
request was sent. Every writer of a paid ledger now appends only to the ledger it last read or wrote
(``durable.append_held``), and a mark beside the ledger records what was last written to it (``durable.marked``), so
that every later reading names a ledger replaced, emptied, cut short or removed since.

DO-02: the live page read its log raw, and one that could not be read made the whole page a server error
(``tests/ui/test_do_run_page.py``).

Every dollar is simulated; no provider is contacted and nothing is sent."""

from __future__ import annotations

import ast
import os
import re
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.agents.test_budget_reservations import ask

ROOT = Path(__file__).parents[2]
SPENT = 0.0008                      # one simulated request: 100 input and 20 output tokens of claude-opus-5-5


def _client(ledger: Path, *, account=None, cap=None):
    """A budgeted client journalling in ``ledger``, built as ADROIT's paid commands build theirs, whose provider is
    simulated (each request answered with 100 input and 20 output tokens): (the client, the requests sent)."""
    from adroit.agents.llm import BudgetedLLMClient, LLMClient
    calls: list[dict] = []

    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"value":4}')],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))
    raw = LLMClient(model="claude-opus-5-5", max_tokens=128,
                    client=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return BudgetedLLMClient(raw, account=account, dollar_budget=cap, ledger_path=ledger), calls


def _session(tmp: Path):
    """A model-library session with a $0.05 cap and a live client built as its paid steps build theirs (its account
    rebuilt from its ledger, ``Intake.account``): (the service, the session's id, the client, the requests sent)."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service = Intake(Catalog(tmp / "models"))
    s = service.start(0.05)
    llm, calls = _client(service.folder(s.session_id) / "paid.jsonl", account=service.account(s))
    return service, s.session_id, llm, calls


@contextmanager
def _in_job(folder: Path, attempt: str):
    with patch.dict(os.environ, {"ADROIT_JOB_FOLDER": str(folder), "ADROIT_JOB_ATTEMPT": attempt}):
        yield


def _entries(folder: Path) -> dict:
    """Everything in ``folder``, as it is, but its lock files (a writer refused under its lock may leave the lock's
    file): each entry's name, and its link's target, its folder's names or its bytes."""
    found = {}
    for name in sorted(n for n in os.listdir(folder) if not n.endswith(".lock")):
        path = folder / name
        if path.is_symlink():
            found[name] = ("link", os.readlink(path))
        elif path.is_dir():
            found[name] = ("folder", sorted(os.listdir(path)))
        else:
            found[name] = ("file", path.read_bytes() if os.access(path, os.R_OK) else "unreadable")
    return found


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        path.rmdir()
    elif os.path.lexists(path):
        path.unlink()


# --- what can be put in a ledger's place: the original moved aside first ------------------------------------------

def _dangling(ledger: Path, original: bytes) -> None:
    ledger.symlink_to("missing-ledger.jsonl")


def _nothing(ledger: Path, original: bytes) -> None:
    pass


def _empty(ledger: Path, original: bytes) -> None:
    ledger.write_bytes(b"")


def _empty_link(ledger: Path, original: bytes) -> None:
    (ledger.parent / "empty.jsonl").write_bytes(b"")
    ledger.symlink_to("empty.jsonl")


def _itself(ledger: Path, original: bytes) -> None:
    ledger.symlink_to(ledger.name)


def _through(ledger: Path, original: bytes) -> None:
    (ledger.parent / "a file").write_text("")
    ledger.symlink_to(ledger.parent / "a file" / "inside")


def _folder(ledger: Path, original: bytes) -> None:
    ledger.mkdir()


def _folder_link(ledger: Path, original: bytes) -> None:
    (ledger.parent / "a folder").mkdir()
    ledger.symlink_to("a folder")


def _cut(ledger: Path, original: bytes) -> None:
    ledger.write_bytes(original[:original.index(b"\n") + 1])


def _another(ledger: Path, original: bytes) -> None:
    changed = original.replace(b"e", b"E", 1)
    assert len(changed) == len(original) and changed != original
    ledger.write_bytes(changed)


# The auditor's four (dn_writer_boundary, dn_journal_continuity), the other entries that lead nowhere, and readable
# ledgers that hold less, or other bytes, than the one replaced
REPLACEMENTS = {"a link to a missing file": _dangling, "no entry": _nothing, "an empty file": _empty,
                "a link to an empty file": _empty_link, "a link to itself": _itself, "a link through a file": _through,
                "a folder": _folder, "a link to a folder": _folder_link, "its first line alone": _cut,
                "another ledger of its length": _another}
READABLE = ("an empty file", "a link to an empty file", "its first line alone", "another ledger of its length")


def _refused(act) -> str:
    """Why ``act`` was refused (``ValueError``), "" where it was not: asserted after what it may not do has been
    checked, so that a writer restored to the pin's fails at that, the matrix's controls' named assertion."""
    try:
        act()
    except ValueError as error:
        return str(error) or type(error).__name__
    return ""


def _replaced(ledger: Path, replacement: str) -> tuple[Path, dict]:
    """``ledger`` moved aside (its original kept beside it) and ``replacement`` put in its place: (where the original
    is, everything in its folder now)."""
    original = ledger.read_bytes()
    saved = ledger.with_name(f"{ledger.name}.original")
    ledger.rename(saved)
    REPLACEMENTS[replacement](ledger, original)
    return saved, _entries(ledger.parent)


# --- the auditor's case: a ledger put in a live session client's place between its requests -----------------------------

@pytest.mark.parametrize("replacement", REPLACEMENTS)
def test_a_live_client_never_writes_on_in_a_ledger_put_in_its_place(tmp_path, replacement):
    """DO-01, the auditor's case and its variants: a session's live client has settled $0.0008; its ledger is then moved
    aside and ``replacement`` put in its place. The client's next request is refused before it is sent, and nothing is
    written to what is there or made in its place (it had been sent, its reservation journalled in a link's new target
    or in the empty file, and the session then read $0.0008 spent, the first request lost). Every new reading of the
    session names its ledger: no figure, its budget blocked. The original restored, the session reads as the first
    request left it and spends on."""
    from adroit.agents.budget import read_ledger
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    assert service.budget_status(session)["spent"] == pytest.approx(SPENT)
    saved, before = _replaced(ledger, replacement)
    refused = _refused(lambda: ask(llm))
    assert len(calls) == 1, "the second request was sent"
    assert _entries(ledger.parent) == before, "something was written to the ledger's place, or made there"
    assert refused
    assert llm.account.committed() == pytest.approx(SPENT)
    assert [e["state"] for e in llm.ledger] == ["reserved", "received", "settled"]
    for reading in (lambda: service.budget_status(session), lambda: service.account(service.session(session)),
                    lambda: read_ledger(ledger)):
        with pytest.raises(ValueError):
            reading()
    _remove(ledger)
    saved.rename(ledger)
    assert service.budget_status(session)["spent"] == pytest.approx(SPENT)
    again, sent = _client(ledger, account=service.account(service.session(session)))
    ask(again)
    assert len(sent) == 1 and service.budget_status(session)["spent"] == pytest.approx(2 * SPENT)


def test_a_live_client_writes_on_after_the_session_s_other_writers_append(tmp_path):
    """What stays: a ledger that another of the session's writers appended to since the client last wrote (its cap
    raised, another command's client spending) still begins with what the client held, and the client writes on."""
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    service.raise_cap(session, 0.10, confirmed=True, reason="SIMULATED fixture")
    other, sent = _client(service.folder(session) / "paid.jsonl", account=service.account(service.session(session)))
    ask(other)
    ask(llm)
    assert len(calls) == 2 and len(sent) == 1
    status = service.budget_status(session)
    assert status["cap"] == 0.10 and status["spent"] == pytest.approx(3 * SPENT)


# --- a reading after the fact: the mark beside the ledger -----------------------------------------------------------

@pytest.mark.parametrize("replacement", ("no entry", *READABLE))
def test_every_reading_of_a_ledger_that_is_not_what_was_last_written_to_it_names_it(tmp_path, replacement):
    """DO-01, after the fact, with no client running: a session's ledger removed, emptied, cut short, or replaced by
    another of its length, beside the mark its last writer left. Every reading names it (the session's status and
    account, the ledger's requests and text, the answer recovery's reading): its money is not known, and its whole cap is
    never shown as remaining (an empty ledger had read as a session that spent nothing)."""
    from adroit.agents.budget import ledger_text, read_ledger
    service, session, llm, _ = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    _replaced(ledger, replacement)
    for reading in (lambda: service.budget_status(session), lambda: service.account(service.session(session)),
                    lambda: read_ledger(ledger), lambda: ledger_text(ledger)):
        with pytest.raises(ValueError, match="mark|missing|lost") as found:
            reading()
        assert "$0.05" not in str(found.value)


def test_a_paid_run_whose_ledger_is_emptied_since_is_not_read_as_one_that_sent_nothing(tmp_path):
    """DO-01, a run's own ledger: a workbench run that settled $0.0008, its ledger then emptied beside its mark. Its cost
    names the ledger and gives no figure; "no paid request was sent" is not said."""
    from adroit.orchestrator import accounting, preflight
    from adroit.ui import engine
    folder = tmp_path / "run"
    folder.mkdir()
    engine.save(engine.Job(title="the run", kind="idea", command=["idea", "--text", "x", "--budget", "1", "--out", "."],
                           folder=str(folder), status="completed", returncode=0, attempt="attempt-a"))
    (folder / "log.txt").write_text("")
    with _in_job(folder, "attempt-a"):
        preflight.open_job_ledger(folder / "paid.jsonl")
        llm, _ = _client(folder / "paid.jsonl", cap=1.0)
        ask(llm)
    assert accounting.cost(folder, engine.load(folder)).run_usd == pytest.approx(SPENT)
    (folder / "paid.jsonl").write_bytes(b"")
    c = accounting.cost(folder, engine.load(folder))
    assert c.run_usd is None and not c.sent_none and "mark" in " ".join(c.damaged), c
    assert "no paid request was sent" not in accounting.run_line(c)


def test_a_ledger_from_before_marks_reads_and_is_written_as_before(tmp_path):
    """What stays: a ledger with no mark beside it (written before marks) reads as it holds, and its next writer's
    line leaves the mark."""
    from adroit.agents.budget import read_ledger
    from adroit.core.durable import Held, marked
    ledger = tmp_path / "paid.jsonl"
    ledger.write_text('{"id": "r0", "state": "reserved", "provider": "anthropic", "model": "SIMULATED", '
                      '"reserved_usd": 0.1}\n{"id": "r0", "state": "settled", "cost_usd": 0.05}\n')
    assert marked(ledger) is None and read_ledger(ledger)["r0"].cost_usd == 0.05
    llm, calls = _client(ledger, cap=1.0)
    ask(llm)
    assert len(calls) == 1 and marked(ledger) == Held.of(ledger.read_bytes()) and len(read_ledger(ledger)) == 2


def test_a_torn_last_line_is_still_named_and_recovered_beside_its_mark(tmp_path):
    """What stays: a crash part way through a line leaves it torn after what the mark records (the mark is written after
    the line); the ledger is named as torn, never as replaced, ``adroit ledger recover`` recovers it, and the session
    spends on."""
    from adroit.agents.budget import TornLedger, read_ledger, recover_torn_tail
    service, session, llm, _ = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    with ledger.open("ab") as stream:
        stream.write(b'{"id": "r1", "state": "reserved", "provider": "anthropic", "model": "SIMULATED", '
                     b'"reserved_usd": 0.001, "invoc')
    with pytest.raises(TornLedger):
        read_ledger(ledger)
    assert recover_torn_tail(ledger).startswith("recovered paid.jsonl")
    again, sent = _client(ledger, account=service.account(service.session(session)))
    ask(again)
    status = service.budget_status(session)
    assert len(sent) == 1 and status["spent"] == pytest.approx(2 * SPENT) and status["reserved_uncertain"] == 0.001


# --- the other writers: a run's opening of its ledger, a cap raise, an older session's first ledger -----------------

DAMAGED = {"a link to a missing file": _dangling, "a link to itself": _itself, "a link through a file": _through,
           "a folder": _folder, "a link to a folder": _folder_link,
           "a file it may not read": lambda ledger, original: (ledger.write_text("x\n"), ledger.chmod(0))}


@pytest.mark.parametrize("damage", DAMAGED)
def test_a_damaged_job_ledger_is_never_opened_anew(tmp_path, damage):
    """DO-01, the opener (the auditor's ``open_job_ledger`` case): a run's own ledger that is there but cannot be read is
    refused, and nothing is made or written (``touch`` had made a link's missing target, an ``opened`` entry in it)."""
    from adroit.orchestrator import preflight
    folder = tmp_path / "job"
    folder.mkdir()
    DAMAGED[damage](folder / "paid.jsonl", b"")
    before = _entries(folder)
    with _in_job(folder, "attempt-b"):
        refused = _refused(lambda: preflight.open_job_ledger(folder / "paid.jsonl"))
    assert _entries(folder) == before, "the damaged ledger was made anew, or written"
    assert "the paid ledger is there but cannot be read" in refused


def test_a_job_ledger_missing_beside_its_mark_is_never_opened_anew(tmp_path):
    """DO-01: a run's ledger removed after it was written, its mark left: the opener refuses (it had made an empty
    one), and nothing is made."""
    from adroit.orchestrator import preflight
    folder = tmp_path / "job"
    folder.mkdir()
    with _in_job(folder, "attempt-a"):
        preflight.open_job_ledger(folder / "paid.jsonl")
    (folder / "paid.jsonl").unlink()
    before = _entries(folder)
    with _in_job(folder, "attempt-b"):
        refused = _refused(lambda: preflight.open_job_ledger(folder / "paid.jsonl"))
    assert _entries(folder) == before, "the lost ledger was made anew"
    assert "the paid ledger is missing" in refused


def test_a_new_job_ledger_is_made_and_opened(tmp_path):
    """What stays: where nothing is, the run's ledger is made, its ``opened`` entry journalled and its mark left."""
    from adroit.agents.budget import read_owned
    from adroit.core.durable import Held, marked
    from adroit.orchestrator import preflight
    folder = tmp_path / "job"
    with _in_job(folder, "attempt-a"):
        preflight.open_job_ledger(folder / "paid.jsonl")
    assert read_owned(folder / "paid.jsonl") == ({}, ["attempt-a"])
    assert marked(folder / "paid.jsonl") == Held.of((folder / "paid.jsonl").read_bytes())


OPENED_REPLACEMENTS = ("a link to a missing file", "no entry", "an empty file", "another ledger of its length")


@pytest.mark.parametrize("replacement", OPENED_REPLACEMENTS)
def test_a_job_ledger_replaced_after_its_run_opened_it_is_never_written_on(tmp_path, replacement):
    """DO-01: a run's ledger replaced after the run opened it, before its first request: the request is refused before
    it is sent, and nothing is written (the client takes the ledger as its run opened it, ``budget.OPENED``)."""
    from adroit.orchestrator import preflight
    folder = tmp_path / "job"
    folder.mkdir()
    with _in_job(folder, "attempt-a"):
        preflight.open_job_ledger(folder / "paid.jsonl")
        (folder / "paid.jsonl.held").unlink(missing_ok=True)   # the mark too: the client's holding refuses alone
        _, before = _replaced(folder / "paid.jsonl", replacement)
        llm, calls = _client(folder / "paid.jsonl", cap=1.0)
        refused = _refused(lambda: ask(llm))
    assert not calls, "the request was sent"
    assert _entries(folder) == before, "something was written to the ledger's place, or made there"
    assert refused


def test_a_paid_command_in_a_run_whose_ledger_is_damaged_is_refused_and_its_money_stays_unknown(tmp_path):
    """DO-01, the auditor's command line case: ``adroit lagrangian --derive --budget 1`` in a workbench run whose own ledger
    is a link to nothing, with no key. The command is refused at the ledger, nothing is made, and the run's cost is as
    before: its ledger named, no figure (the opener had made an empty ledger, and the page then said "This run: $0 (no
    paid request was sent)")."""
    from typer.testing import CliRunner
    from adroit.orchestrator import accounting, cli
    from adroit.ui import engine
    out = tmp_path / "cli"
    out.mkdir()
    (out / "paid.jsonl").symlink_to("lost.jsonl")
    (out / "log.txt").write_text("")
    command = ["lagrangian", "--derive", "--description", "SIMULATED model", "--checker", "none", "--budget", "1",
               "--out", str(out)]
    job = engine.Job(title="SIMULATED damaged ledger", kind="lagrangian", folder=str(out), command=command,
                     status="failed", attempt="cli-attempt")
    before = accounting.cost(out, job)
    with _in_job(out, "cli-attempt"), patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}):
        result = CliRunner().invoke(cli.app, command)
    said = " ".join(re.sub("[│╭╮╰╯─]", " ", result.output).split())     # the error's box and its wrapping removed
    assert result.exit_code == 2 and "the paid ledger is there but cannot be read" in said, result.output
    after = accounting.cost(out, job)
    assert after == before and after.run_usd is None and not after.sent_none
    assert "no paid request was sent" not in " ".join(accounting.cost_lines(after))
    assert os.readlink(out / "paid.jsonl") == "lost.jsonl" and not os.path.lexists(out / "lost.jsonl")


@pytest.mark.parametrize("replacement", ("a link to a missing file", "an empty file", "its first line alone"))
def test_a_cap_is_never_raised_in_a_ledger_put_in_the_session_s_place(tmp_path, replacement):
    """DO-01, the cap's writer: a cap raise on a session whose ledger was replaced since it spent is refused, and
    nothing is written: neither the ledger's place nor the session's record (its append had followed the link)."""
    service, session, llm, _ = _session(tmp_path)
    ask(llm)
    _, before = _replaced(service.folder(session) / "paid.jsonl", replacement)
    with pytest.raises(ValueError):
        service.raise_cap(session, 0.10, confirmed=True, reason="SIMULATED fixture")
    assert _entries(service.folder(session)) == before


def _older(tmp: Path):
    """A paid session from before 2026-10-25, opened without a ledger and never paid: (the service, its id)."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake, session_identity
    from adroit.core.checkpoint import atomic_json
    service = Intake(Catalog(tmp / "models"))
    s = service.start(0.05)
    (service.folder(s.session_id) / "paid.jsonl").unlink()
    older = s.model_copy(update={"journal": False})
    older.integrity_sha256 = session_identity(older)
    atomic_json(service.folder(s.session_id) / "session.json", older.model_dump(mode="json"))
    return service, s.session_id


def test_an_older_session_s_first_ledger_is_made_once_and_spent_in(tmp_path):
    """What stays: an older session's first paid account makes its empty ledger and marks its record as having one;
    its client then spends in it."""
    service, session = _older(tmp_path)
    llm, calls = _client(service.folder(session) / "paid.jsonl", account=service.account(service.session(session)))
    ask(llm)
    assert service.session(session).journal and len(calls) == 1
    assert service.budget_status(session)["spent"] == pytest.approx(SPENT)


def test_an_older_session_s_first_ledger_is_never_made_over_an_entry_put_there_meanwhile(tmp_path, monkeypatch):
    """DO-01: nothing at an older session's ledger's path when its account reads it, and a link put there before the
    ledger is made: the account is refused, the link left as it is and its target not made, the record not marked (its
    ledger had been written over whatever was there)."""
    service, session = _older(tmp_path)
    ledger = service.folder(session) / "paid.jsonl"
    real = service._journal

    def read_then_link(s):
        found = real(s)
        ledger.symlink_to("elsewhere.jsonl")
        return found
    monkeypatch.setattr(service, "_journal", read_then_link)
    with pytest.raises(ValueError, match="is there now, where nothing was"):
        service.account(service.session(session))
    assert os.readlink(ledger) == "elsewhere.jsonl" and not os.path.lexists(ledger.parent / "elsewhere.jsonl")
    assert not service.session(session).journal


# --- the inventory: every writer of a paid ledger appends only to the ledger it holds -------------------------------

# each function that writes a paid ledger (a session's, a run's own, a command's), and how
JOURNAL_WRITERS = {
    "adroit/agents/llm.py": {"BudgetedLLMClient._journal": "each request's lines, through durable.append_held, under its "
                                                           "account's whole check for a session's ledger (DQ-03) and "
                                                           "its writers' lock (DR-01), its folder's, taken before it "
                                                           "opens the ledger (DS-01), by the ledger's own name, its "
                                                           "folder still the one locked (DT-01), and in that folder, by "
                                                           "name, never by its path once locked (DU-01); to its "
                                                           "account's ledger, by the name the account was read by, "
                                                           "whatever path leads the client to it (DU-02); any failure "
                                                           "once its request is sent freezes the account (DQ-01)"},
    "adroit/orchestrator/preflight.py": {"open_job_ledger": "a run's own ledger made and opened, through append_held"},
    "adroit/orchestrator/model_intake.py": {
        "Intake.raise_cap": "a cap raise journalled, through append_held",
        "Intake._open_journal": "an older session's first, empty ledger, through append_held",
        "Intake.start": "a new session's empty ledger, in a folder made for it (no entry can be there)"},
    "adroit/agents/budget.py": {"recover_torn_tail": "the explicit recovery: read as every reading reads it, its mark "
                                                     "checked, before anything is written (DP-02); its original bytes "
                                                     "kept beside it, its complete lines rewritten as they were and an "
                                                     "entry added, and the mark then records it, all under the "
                                                     "journal's writers' lock (DR-01), its folder's, which the "
                                                     "journal's replacement leaves (DS-01), by the journal's own name, "
                                                     "its folder still the one locked (DT-01), read and written in "
                                                     "that folder, by name, and refused where it is no longer at the "
                                                     "journal's path (DU-01)"},
}
# each other function that appends to a file or makes one by touching it, and why it is not a paid ledger's writer
OTHER_APPENDS = {
    "adroit/ui/batch.py": {"run": "the batch runner's lock file", "_runner_held": "the batch runner's lock file",
                           "_reserve": "the runs folder's record of dispatches (no money; its reader, under the same "
                                       "lock, refuses one that cannot be read: DN-01)"},
    "adroit/ui/engine.py": {"job_lock": "a run's lock file", "resume": "a run's history of its states"},
    "adroit/core/durable.py": {"lock": "a lock file", "publishing": "a study's publication lock file"},
    "adroit/core/checkpoint.py": {"run_lock": "a lock file"},
    "adroit/ui/deletion.py": {"_busy": "a probe of a study's publication lock file found in a folder being deleted, to "
                                       "learn whether another writer holds it (no money; nothing written; PS-05)"},
    "adroit/core/calculation_cache.py": {"_lock": "the calculation cache's lock file"},
    "adroit/constraints/pair_production.py": {"_locked": "a calculation's lock file"},
    "adroit/experiments/xenon.py": {"DiamxXenon._attempt": "the xenon calculation's lock file, taken for each attempt "
                                                          "at one DIAMX generation (DX-01)"},
    "adroit/evaluation/core.py": {"_append": "the model zoo's evaluation ledger (no money)"},
    "adroit/evaluation/usage_log.py": {"record": "the usage log (no money)"},
}


def _functions(path: Path):
    """Each function of a module, by its qualified name (``Class.method``), with its node."""
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{item.name}", item


def _appends(node: ast.AST) -> list[str]:
    """The calls in ``node`` that append to a file or make one by following its path: ``open`` or ``.open`` in an
    append mode, ``.touch()``, ``os.open`` with ``O_APPEND`` or ``O_CREAT`` but not ``O_EXCL``."""
    found = []
    for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
        name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
        modes = [a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        modes += [k.value.value for k in call.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
        flags = ast.unparse(call)
        if name == "open" and any("a" in m for m in modes):
            found.append(ast.unparse(call))
        elif name == "touch":
            found.append(ast.unparse(call))
        elif name == "open" and isinstance(call.func, ast.Attribute) and ast.unparse(call.func.value) == "os" \
                and ("O_APPEND" in flags or "O_CREAT" in flags) and "O_EXCL" not in flags:
            found.append(flags)
    return found


def test_every_writer_of_a_paid_ledger_appends_only_to_the_ledger_it_holds():
    """The inventory (DO-01): every function in ``adroit`` that appends to a file or makes one by following its path is
    named, a paid ledger's writer or another with why; each paid ledger's writer appends through
    ``durable.append_held`` (or is the named recovery, or a new session's first ledger) and never appends or touches
    itself; and no function that names a ledger's path writes to it unnamed."""
    named = {(f, q) for table in (JOURNAL_WRITERS, OTHER_APPENDS) for f, qs in table.items() for q in qs}
    unnamed, raw = [], []
    for path in sorted((ROOT / "adroit").rglob("*.py")):
        module = str(path.relative_to(ROOT))
        for qualified, node in _functions(path):
            appends = _appends(node)
            if appends and (module, qualified) not in named:
                unnamed.append(f"{module}:{qualified}: {appends}")
            if qualified in JOURNAL_WRITERS.get(module, {}) and appends:
                raw.append(f"{module}:{qualified}: {appends}")
    assert not unnamed, "functions that append or touch, not in the inventory:\n" + "\n".join(unnamed)
    assert not raw, "a paid ledger's writer appends or touches itself:\n" + "\n".join(raw)
    for module, writers in JOURNAL_WRITERS.items():
        defined = dict(_functions(ROOT / module))
        for qualified, how in writers.items():
            assert qualified in defined, f"{module}:{qualified} is gone"
            if "append_held" in how:
                assert "append_held" in ast.unparse(defined[qualified]), f"{module}:{qualified}: {how}"


def test_the_inventory_finds_an_append_that_follows_a_link():
    """The inventory's control: the pin's journal append and job ledger opener (``open("a")``, ``touch``) are found."""
    pin = ast.parse('def _journal(self, event):\n    with self.ledger_path.open("a") as stream:\n        pass\n'
                    'def open_job_ledger(ledger):\n    ledger.touch()\n'
                    'def raw(path):\n    os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT)\n')
    found = {f.name: _appends(f) for f in pin.body}
    assert all(found.values()), found
    assert not _appends(ast.parse("os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL)"))

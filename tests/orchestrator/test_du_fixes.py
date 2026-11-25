"""The auditor's DT recheck (2026-11-10), DU-01 and DU-02.

DU-01: a writer of a paid journal checked, once it took its writers' lock, that the folder it locked was still at the
journal's path, and then read and wrote by that path. A recovery whose folder was renamed away while it held the lock,
an equal copy put at its path, wrote its mark into the copy, over the mark of a request another process had journalled
and sent there under the copy's own lock, and said it was done; the journal cut back to the recovery's mark read as
$0.0008 less spent (the auditor's ``dt_recovery_holder``). A writer, once it holds the lock, now reads and writes only in the
folder it locked, by name (``durable._in``), and says so where that folder is no longer at the path.

DU-02: a client of a session's account chose the session's checks (its record's cap raises, what the ledger held as the
account was read) by its ledger path's spelling. Given the session's ledger through a link to its folder, it appended
under every ledger's check and sent a request while the session's record and ledger disagreed, as by its own path it
was refused (the auditor's ``dt_folder_alias_account_v2``). A client now journals to its account's ledger, or its run's, by
the name that was read or opened, whatever path leads it there (``BudgetedLLMClient._ledger``).

Every dollar is simulated; no provider is contacted and nothing is sent."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import (OPENED_REPLACEMENTS, SPENT, _client, _entries, _in_job, _refused,
                                              _replaced, _session)
from tests.orchestrator.test_dp_fixes import EXTENSIONS
from tests.orchestrator.test_dq_fixes import _committed
from tests.orchestrator.test_dt_fixes import APPENDER

ROOT = Path(__file__).parents[2]


def _replace_folder(ledger: Path, moved: Path, seen: dict) -> None:
    """The journal's folder renamed to ``moved`` and an equal copy put at its path, as the auditor's control does, then one
    request asked there by another process (``test_dt_fixes.APPENDER``), which takes the copy's own writers' lock: what
    came of it, and the copy's every entry once it is done, kept in ``seen``."""
    ledger.parent.rename(moved)
    shutil.copytree(moved, ledger.parent)
    child = subprocess.run([sys.executable, "-c", APPENDER, str(ledger)], cwd=ROOT, capture_output=True, text=True,
                           timeout=120)
    assert child.returncode == 0, child.stdout + child.stderr
    seen["child"], seen["there"] = json.loads(child.stdout.splitlines()[-1]), _entries(ledger.parent)


# where the recovery is when its folder is replaced: at each of its writes, before it is made, and once its mark is
STAGES = {"before its side copy": "side", "before the journal is put in place": "journal", "before its mark": "mark",
          "once marked": "marked"}


@pytest.mark.parametrize("stage", STAGES)
def test_a_recovery_whose_folder_is_replaced_while_it_holds_its_lock_writes_nothing_there(tmp_path, stage):
    """DU-01, the auditor's ``dt_recovery_holder`` and its kin: a journal of one settled request and a torn reservation is
    recovered; at ``stage``, its folder is renamed away and an equal copy put at its path, and another process asks a
    request there. The recovery writes nothing in the copy: its side copy, its journal and its mark are written in the
    folder it locked, now moved, whole and marked there, and it is refused once done (``ChangedRecord``), never said
    done. Where the copy held the recovered journal, the other process's request is journalled and sent there, its
    mark records the whole journal, and the journal cut back to the recovery's is refused; where it held the torn
    journal, the other is refused. Before, the recovery's mark was written by its path over the other's, and the
    journal cut back to it read as $0.0008 less spent."""
    from adroit.agents.budget import recover_torn_tail
    from adroit.core import durable
    ledger = tmp_path / "current" / "paid.jsonl"
    llm, _ = _client(ledger, cap=0.25)
    ask(llm)
    with ledger.open("ab") as stream:
        stream.write(EXTENSIONS["a torn line"])
    torn, mark = ledger.read_bytes(), durable.marked(ledger)
    body, moved = torn[:torn.rfind(b"\n") + 1], tmp_path / "moved" / "paid.jsonl"
    real, seen = durable.write_atomic, {}

    def atomic(path, *args, **kw):
        target = Path(path)
        at = ("side" if target.name.startswith("paid.jsonl.torn-") else "journal" if target == ledger else
              "mark" if target == durable.mark_of(ledger) else "")
        if at and at == STAGES[stage] and not seen:
            _replace_folder(ledger, moved.parent, seen)
        done = real(path, *args, **kw)
        if at == "mark" and STAGES[stage] == "marked" and not seen:
            _replace_folder(ledger, moved.parent, seen)
        return done
    with patch.object(durable, "write_atomic", atomic):
        try:
            said = recover_torn_tail(ledger)
        except ValueError as error:
            said = error
    assert seen and _entries(ledger.parent) == seen["there"], \
        "a recovery wrote in a folder put in its place while it held its lock"
    assert isinstance(said, durable.ChangedRecord) and "while its writer held its writers' lock" in str(said), \
        f"a recovery whose folder was replaced while it held its lock said it was done: {said}"
    recovered = moved.read_bytes()
    assert recovered.startswith(body) and b'"state": "recovered"' in recovered[len(body):], recovered
    assert durable.marked(moved) == durable.Held.of(recovered), "the recovery is not whole in the folder it locked"
    assert any(side.read_bytes() == torn for side in moved.parent.glob("paid.jsonl.torn-*"))
    if STAGES[stage] in ("side", "journal"):        # the copy holds the torn journal: the other writer is refused
        assert seen["child"]["sent"] == 0 and "not whole" in seen["child"].get("refused", ""), seen["child"]
        assert ledger.read_bytes() == torn and durable.marked(ledger) == mark
        return
    whole = ledger.read_bytes()
    assert seen["child"] == {"sent": 1} and whole.startswith(recovered) and len(whole) > len(recovered), seen
    assert durable.marked(ledger) == durable.Held.of(whole), "a later writer's mark was written over"
    assert _committed(ledger) == pytest.approx(_committed(moved) + SPENT)
    ledger.write_bytes(recovered)                   # the other process's request cut away, in place
    assert _committed(ledger) is None, "the journal cut back to what its recovery wrote was read as less spent"


# where a request's append is when its folder is replaced: once it has checked the journal, before its mark is
# written (its line written and synced), and once its mark is written
APPEND_STAGES = ("once checked", "before its mark", "once marked")


@pytest.mark.parametrize("stage", APPEND_STAGES)
def test_an_append_whose_folder_is_replaced_while_it_holds_its_lock_writes_nothing_there(tmp_path, stage):
    """DU-01 for a request's append: after one settled request, the next request's reservation is being appended
    when, at ``stage``, its folder is renamed away and an equal copy put at its path, and another process asks a
    request there, journalled, sent and marked under the copy's own lock. The append writes nothing in the copy (its
    mark, written once its line is, is written in the folder it locked), and is refused: before its line is written,
    nothing written (``ChangedRecord``); once written, ``UnfinishedAppend``, its account frozen. Its request is never
    sent; the copy's mark records all the copy holds; the moved folder's journal and its mark are one. Before, its mark
    was written by its path over the other's."""
    from adroit.core import durable
    ledger = tmp_path / "current" / "paid.jsonl"
    llm, calls = _client(ledger, cap=0.25)
    ask(llm)
    first, moved = ledger.read_bytes(), tmp_path / "moved" / "paid.jsonl"
    checker, real, seen = durable._appendable, durable.write_atomic, {}

    def checked(path, *args, **kw):
        found = checker(path, *args, **kw)
        if stage == "once checked" and not seen:
            _replace_folder(ledger, moved.parent, seen)
        return found

    def atomic(path, *args, **kw):
        marking = Path(path) == durable.mark_of(ledger)
        if marking and stage == "before its mark" and not seen:
            _replace_folder(ledger, moved.parent, seen)
        done = real(path, *args, **kw)
        if marking and stage == "once marked" and not seen:
            _replace_folder(ledger, moved.parent, seen)
        return done
    with patch.object(durable, "_appendable", checked), patch.object(durable, "write_atomic", atomic):
        try:                                        # refused (``ChangedRecord``), or once written ``UnfinishedAppend``
            ask(llm)
            refused = ""
        except (ValueError, OSError) as error:
            refused = str(error)
    assert seen and _entries(ledger.parent) == seen["there"], \
        "an append wrote in a folder put in its place while it held its lock"
    assert len(calls) == 1, "a request was sent whose append's folder was replaced while it held its lock"
    assert "its folder was moved or removed, or another put in its place" in refused, refused
    assert seen["child"] == {"sent": 1}, seen["child"]
    whole = ledger.read_bytes()
    assert durable.marked(ledger) == durable.Held.of(whole), "the copy's mark does not record all it holds"
    kept = moved.read_bytes()
    assert durable.marked(moved) == durable.Held.of(kept), "the moved folder's journal and mark are not one"
    if stage == "once checked":
        assert kept == first and not llm.account.unjournalled
    else:
        assert kept.startswith(first) and len(kept) > len(first) and llm.account.unjournalled


def _folder_link(ledger: Path, tmp: Path) -> Path:
    (tmp / "alias").symlink_to(ledger.parent, target_is_directory=True)
    return tmp / "alias" / ledger.name


def _above_link(ledger: Path, tmp: Path) -> Path:
    (tmp / "above").symlink_to(ledger.parents[1], target_is_directory=True)
    return tmp / "above" / ledger.parent.name / ledger.name


# the paths a session's client may be given to its ledger: its own, through a link to its folder, and through a link
# to a folder above it (the auditor's routes)
SESSION_ROUTES = {"its own path": lambda ledger, tmp: ledger, "a link to its folder": _folder_link,
                  "a link to a folder above it": _above_link}


@pytest.mark.parametrize("route", SESSION_ROUTES)
def test_a_session_s_client_by_any_route_is_refused_while_its_record_and_ledger_disagree(tmp_path, route):
    """DU-02, the auditor's ``dt_folder_alias_account_v2``: a session's account taken after one settled request, and its
    client given the session's ledger by ``route``. A cap raise is then journalled and its record's write fails
    (``Intake.raise_cap`` interrupted). The client's next request is refused before it is sent, by every route, naming
    the raise its record lacks; the ledger is as the raise left it. Before, through a link to its folder, it was sent,
    under every ledger's check, not its session's."""
    from adroit.orchestrator import model_intake
    service, session, original, _ = _session(tmp_path)
    ask(original)
    ledger = service.folder(session) / "paid.jsonl"
    llm, calls = _client(SESSION_ROUTES[route](ledger, tmp_path), account=service.account(service.session(session)))
    with patch.object(model_intake, "atomic_json", side_effect=OSError("SIMULATED: the record is not written")), \
            pytest.raises(OSError, match="SIMULATED"):
        service.raise_cap(session, 0.2, confirmed=True)
    after = ledger.read_bytes()
    refused = _refused(lambda: ask(llm))
    assert calls == [], "a request was sent by another route to its session's ledger while its record and ledger disagree"
    assert "that its record does not have" in refused, refused
    assert ledger.read_bytes() == after


# ledgers put in a session's ledger's place that are whole journals, so that only what its account held refuses them
SESSION_REPLACEMENTS = ("an empty file", "its first line alone")


@pytest.mark.parametrize("replacement", SESSION_REPLACEMENTS)
@pytest.mark.parametrize("route", SESSION_ROUTES)
def test_a_session_s_ledger_put_in_its_place_since_its_account_was_read_is_refused_by_any_route(tmp_path, route,
                                                                                                 replacement):
    """DU-02, what the account held: a session's account taken after one settled request, its client given the
    session's ledger by ``route``; the ledger is then put aside and ``replacement`` put in its place, a whole journal,
    its mark removed too (the account's holding refuses alone). Refused before anything is written or sent, by every
    route. Before, through a link to its folder, the client took the ledger as it was then, wrote on and sent."""
    from adroit.core import durable
    service, session, original, _ = _session(tmp_path)
    ask(original)
    ledger = service.folder(session) / "paid.jsonl"
    llm, calls = _client(SESSION_ROUTES[route](ledger, tmp_path), account=service.account(service.session(session)))
    durable.mark_of(ledger).unlink()
    _, before = _replaced(ledger, replacement)
    refused = _refused(lambda: ask(llm))
    assert calls == [], "a request was sent by another route to its session's ledger put in its place since its " \
                        "account was read"
    assert _entries(ledger.parent) == before and refused


@pytest.mark.parametrize("route", SESSION_ROUTES)
def test_a_session_s_client_by_any_route_spends_under_its_account(tmp_path, route):
    """DU-02's healthy counterpart: a session's client given its ledger by ``route``, a cap raise made as a person
    makes it, then two requests. Both are sent, journalled in the session's ledger by the name its account was read
    by, and marked; the session's spending is its three requests'."""
    from adroit.agents.budget import read_ledger, settled_and_uncertain
    from adroit.core import durable
    service, session, original, _ = _session(tmp_path)
    ask(original)
    ledger = service.folder(session) / "paid.jsonl"
    llm, calls = _client(SESSION_ROUTES[route](ledger, tmp_path), account=service.account(service.session(session)))
    service.raise_cap(session, 0.2, confirmed=True, reason="SIMULATED")
    ask(llm)
    ask(llm)
    assert len(calls) == 2
    assert list(llm._held) == [Path(os.path.abspath(ledger))], \
        "a client given its session's ledger by another route journalled by that route, not by its account's name"
    assert durable.marked(ledger) == durable.Held.of(ledger.read_bytes())
    assert settled_and_uncertain(read_ledger(ledger)) == (pytest.approx(3 * SPENT), 0)


def test_a_client_of_a_session_s_account_given_another_ledger_is_refused(tmp_path):
    """DU-02, the pairing: a client of a session's account given a ledger that is not the session's is refused before
    anything is sent, nothing made where it was given, and the account as it was. Before, it journalled there under
    every ledger's check, apart from the account's ledger."""
    service, session, original, _ = _session(tmp_path)
    ask(original)
    account = service.account(service.session(session))
    other = tmp_path / "other" / "paid.jsonl"
    llm, calls = _client(other, account=account)
    refused = _refused(lambda: ask(llm))
    assert calls == [] and not os.path.lexists(other.parent), "a client of a session's account journalled to another " \
                                                              "ledger"
    assert "not this client's account's paid ledger" in refused, refused
    assert account.committed() == pytest.approx(SPENT) and not account.unjournalled


def _job(tmp: Path) -> tuple[Path, Path]:
    """A workbench job's folder, and its ledger's path through a link to it."""
    folder = tmp / "job"
    folder.mkdir()
    (tmp / "alias").symlink_to(folder, target_is_directory=True)
    return folder, tmp / "alias" / "paid.jsonl"


@pytest.mark.parametrize("replacement", OPENED_REPLACEMENTS)
def test_a_run_s_ledger_by_a_link_to_its_folder_is_held_as_its_run_opened_it(tmp_path, replacement):
    """DU-02 for a run's own ledger (DO-01's case through a link to its folder): opened by the run, then put in its
    place before its first request, its mark removed too; the run's client, given it through a link to the run's
    folder, is refused before anything is sent, nothing written. Before, the link's spelling was not the one opened,
    and the ledger was taken as it was then: an empty one, or none, written on, and the request sent."""
    from adroit.orchestrator import preflight
    folder, alias = _job(tmp_path)
    with _in_job(folder, "attempt-a"):
        preflight.open_job_ledger(folder / "paid.jsonl")
        (folder / "paid.jsonl.held").unlink(missing_ok=True)
        _, before = _replaced(folder / "paid.jsonl", replacement)
        llm, calls = _client(alias, cap=1.0)
        refused = _refused(lambda: ask(llm))
    assert not calls, "a request was sent through a link to its run's folder after its ledger was put in its place"
    assert _entries(folder) == before and refused


def test_a_run_s_client_by_a_link_to_its_folder_journals_in_its_ledger_as_opened(tmp_path):
    """The healthy counterpart: the run's client, given its ledger through a link to the run's folder, journals in it
    by the name the run opened it by, after its ``opened`` entry, and its request is sent."""
    from adroit.agents.budget import read_owned
    from adroit.orchestrator import preflight
    folder, alias = _job(tmp_path)
    with _in_job(folder, "attempt-a"):
        preflight.open_job_ledger(folder / "paid.jsonl")
        llm, calls = _client(alias, cap=1.0)
        ask(llm)
    requests, opened = read_owned(folder / "paid.jsonl")
    assert len(calls) == 1 and opened == ["attempt-a"] and len(requests) == 1
    assert list(llm._held) == [Path(os.path.abspath(folder / "paid.jsonl"))], \
        "a run's client given its ledger through a link to its folder journalled by the link, not as its run opened it"

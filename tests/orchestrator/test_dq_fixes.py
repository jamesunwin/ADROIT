"""The auditor's DP recheck (2026-11-09), DQ-01 to DQ-04.

DQ-01: a settlement whose append was refused before anything was written (the ledger could not be opened) had first
been settled in the live account, and the account was not frozen, since nothing was written: it then reserved against
$0.0008 where its ledger held the $0.040952 reservation, and sent a request a fresh account refused at the cap. Each
entry of a request is now journalled before its account changes, and once the request is sent any failure to journal
one of its entries, refused or begun, freezes the account (``BudgetAccount.unjournalled``), its reservation kept.
The auditor's cross-product: each entry (the reservation, the response, its bill uncertain, the settlement) failing at each
stage (refused, cut short, its sync failed, its mark not written).

DQ-02: a journal renamed away once its append had checked it, and its earlier bytes put back at its path, had had the
reservation appended to the file renamed, the mark beside the other written for it, and the request sent. The append
now writes only while its path still leads to the file it checked (``durable._displaced``): checked before it writes,
once it has written, and once it has marked.

DQ-03: a cap raise its writer never makes (without its caps; to $100) had been read as an entry, the next request sent,
and the session's account rebuilt over it, while the session's budget reading refused it. Each cap raise is now read as
its writer journals it (``budget._cap_raised``), and a session's spending reconciles its record's cap raises with its
ledger's, as its reading does, when its account is made and at each append (``model_intake.Intake._agreed``).

DQ-04: a request reserved before its account froze had been sent after it. The freeze is now read again the moment
before the provider is called (``BudgetedLLMClient._sendable``).

Every dollar is simulated; no provider is contacted and nothing is sent."""

from __future__ import annotations

import ast
import inspect
import json
import os
import textwrap
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import SPENT, _client, _refused, _session

BOUND = 0.040952                    # the reservation of one simulated request (its bound)


def _watch(llm) -> list[dict]:
    """Each request the provider is then sent, as the journal at the client's ledger path stands at its send, read as
    every reading reads it (its mark checked): its requests, or why it cannot be read."""
    from adroit.agents.budget import read_ledger
    seen, send = [], llm._inner._client.messages.create

    def create(**kw):
        try:
            seen.append({"requests": len(read_ledger(Path(llm.ledger_path)))})
        except ValueError as error:
            seen.append({"unreadable": str(error)})
        return send(**kw)
    llm._inner._client.messages.create = create
    return seen


# --- DQ-01: an entry that fails, at each stage, for each entry of a request -----------------------------------------

EVENTS = ("reserved", "received", "billing_uncertain", "settled")
FAULTS = ("refused", "cut short", "unsynced", "unmarked")


@contextmanager
def _failing(llm, event: str, fault: str):
    """The client's journalling of its next ``event`` entry fails, once, at ``fault``: refused before anything is
    written (the ledger cannot be opened), cut short (40 bytes written, then a storage error), written whole and its
    sync failed, or written and synced and the mark beside it not written. Yields [whether it is still to happen]."""
    from adroit.core import durable
    ledger = Path(os.path.abspath(llm.ledger_path))
    active, armed = [""], [True]
    journal, opener, writer, syncer, marker = llm._journal, os.open, os.write, os.fsync, durable.write_atomic

    def now() -> bool:
        if armed[0] and active[0] == event:
            armed[0] = False
            return True
        return False

    def journalled(entry):
        active[0] = entry["state"]
        try:
            return journal(entry)
        finally:
            active[0] = ""

    def opened(path, *args, **kw):          # the ledger, by its path, or by its name in the folder locked (DU-01)
        if fault == "refused" and (Path(path) == ledger or kw.get("dir_fd") is not None and path == ledger.name) \
                and now():
            raise PermissionError("SIMULATED: the ledger cannot be opened")
        return opener(path, *args, **kw)

    def written(handle, data):
        if fault == "cut short" and now():
            writer(handle, bytes(data)[:40])
            raise OSError("SIMULATED storage error part way through the line")
        return writer(handle, data)

    def synced(handle):
        if fault == "unsynced" and now():
            raise OSError("SIMULATED sync failure")
        return syncer(handle)

    def marked(path, *args, **kw):
        if fault == "unmarked" and Path(path) == durable.mark_of(ledger) and now():
            raise OSError("SIMULATED: the mark is not written")
        return marker(path, *args, **kw)
    with patch.object(llm, "_journal", journalled), patch.object(durable.os, "open", opened), \
            patch.object(durable.os, "write", written), patch.object(durable.os, "fsync", synced), \
            patch.object(durable, "write_atomic", marked):
        yield armed


def _committed(ledger: Path) -> float | None:
    """What a paid ledger commits, settled and still reserved, as every reading reads it; None where it cannot be read
    (a torn last line, named with its recovery)."""
    from adroit.agents.budget import read_ledger, settled_and_uncertain
    try:
        return sum(settled_and_uncertain(read_ledger(ledger)))
    except ValueError:
        return None


@pytest.mark.parametrize("fault", FAULTS)
@pytest.mark.parametrize("event", EVENTS)
def test_a_failed_entry_leaves_the_accounts_agreeing_or_the_account_frozen(tmp_path, event, fault):
    """DQ-01, the auditor's ``dp_failure_edges``: after one settled request, the next request's ``event`` entry fails at
    ``fault`` (its bill made uncertain by an answer lost after it was sent). Only a reservation refused before anything
    was written is released, its account as before, and the next request is sent with its reservation in the journal at
    its path. After every other failure the account is frozen and keeps the request's reservation (never less than its
    ledger holds), and nothing more is sent. Before, a settlement refused had been settled in the live account, unfrozen,
    and the next request sent against $0.0008 where the ledger held $0.040952."""
    from adroit.agents.budget import UnknownLedger
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    provider = llm._inner._client.messages.create
    if event == "billing_uncertain":
        def lost(**kw):
            provider(**kw)
            raise TimeoutError("SIMULATED: its answer lost after it was sent")
        llm._inner._client.messages.create = lost
    with _failing(llm, event, fault) as armed, pytest.raises((OSError, ValueError)):
        ask(llm)
    assert not armed[0], "the failure was not reached"
    llm._inner._client.messages.create = provider
    sends = _watch(llm)
    live, held = llm.account.committed(), _committed(ledger)
    if (event, fault) == ("reserved", "refused"):
        assert not llm.account.unjournalled and live == pytest.approx(SPENT) == pytest.approx(held)
        ask(llm)
        assert sends == [{"requests": 2}] and len(calls) == 2
        return
    assert llm.account.unjournalled, "an entry failed and its account was not frozen"
    assert live == pytest.approx(SPENT + BOUND), "the failed request's reservation was not kept"
    assert held is None or held <= live + 1e-12, "the live account holds less than its ledger"
    with pytest.raises(UnknownLedger):
        ask(llm)
    assert not sends and len(calls) == (1 if event == "reserved" else 2), "a request was sent after an entry failed"


def test_only_a_reservation_is_journalled_before_its_request_is_sent():
    """The client's ``_journal`` takes every entry but a reservation as one of a request already sent (DQ-01): in
    ``request``, the reservation is the only entry journalled before the provider is called, the freeze is read after
    it and before the call (DQ-04), and the settlement is journalled before the account settles it (DQ-01)."""
    from adroit.agents.llm import BudgetedLLMClient
    tree = ast.parse(textwrap.dedent(inspect.getsource(BudgetedLLMClient.request)))
    order = []
    for node in sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset)):
        name = ast.unparse(node.func)
        if name == "self._journal":
            state = {k.arg: ast.unparse(k.value) for k in node.args[0].keywords}["state"].strip("'\"")
            order.append(f"journal {state}")
        elif name in ("send", "self._sendable", "self.account.settle"):
            order.append(name)
    first = order.index("send")
    assert order[:first] == ["journal reserved", "self._sendable"], order
    assert order.index("journal settled") < order.index("self.account.settle"), order
    assert all(step != "journal reserved" for step in order[first:]), order


# --- DQ-02: the journal put in its place during an append ----------------------------------------------------------

MOMENTS = ("while it is checked", "once its append began", "as its append is recorded")


@contextmanager
def _replaced(ledger: Path, moment: str, aside: Path):
    """The journal at ``ledger`` renamed to ``aside``, and its bytes as they were put back at its path, once, at
    ``moment`` of the next reservation's append: once the append has checked it (the auditor's
    ``path_replaced_after_check``), once its line is written and synced, or once the mark beside it is written. Yields
    [whether it is still to happen]."""
    from adroit.core import durable
    original, armed, active = ledger.read_bytes(), [True], [False]
    checker, syncer, marker = durable._appendable, os.fsync, durable.write_atomic

    def swap(now: bool) -> None:
        if now and active[0] and armed[0]:
            armed[0] = False
            ledger.rename(aside)
            ledger.write_bytes(original)

    def checked(path, handle, data, *rest):
        found = checker(path, handle, data, *rest)
        active[0] = Path(path) == ledger and b'"state": "reserved"' in data
        swap(moment == MOMENTS[0])
        return found

    def synced(handle):
        syncer(handle)
        swap(moment == MOMENTS[1])

    def marked(path, *args, **kw):
        done = marker(path, *args, **kw)
        swap(moment == MOMENTS[2] and Path(path) == durable.mark_of(ledger))
        return done
    with patch.object(durable, "_appendable", checked), patch.object(durable.os, "fsync", synced), \
            patch.object(durable, "write_atomic", marked):
        yield armed


@pytest.mark.parametrize("moment", MOMENTS)
def test_a_journal_put_in_its_place_during_an_append_is_never_sent_past(tmp_path, moment):
    """DQ-02: at every send, the journal at the client's ledger path holds the reservation of each request sent, read as
    every reading reads it (its mark checked). Put in its place while it is checked, nothing is written
    (``ChangedRecord``) and the reservation is released: the journal at its path is as it was, and the next request is
    journalled there before it is sent. Once the write began, or as it is recorded beside it, the append fails
    (``UnfinishedAppend``), the account freezes, and nothing more is sent: the file renamed holds the line, the journal
    at its path does not. Before, the request was sent with its reservation only in the file renamed."""
    from adroit.agents.budget import UnknownLedger, read_ledger
    from adroit.core.durable import ChangedRecord, UnfinishedAppend
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = Path(os.path.abspath(service.folder(session) / "paid.jsonl"))
    before, aside = ledger.read_bytes(), tmp_path / "renamed.jsonl"
    sends = _watch(llm)
    with _replaced(ledger, moment, aside) as armed, pytest.raises((ChangedRecord, UnfinishedAppend)) as failed:
        ask(llm)
    assert not armed[0], "the journal was not replaced"
    assert len(calls) == 1 and not sends, "a request was sent without its reservation in the journal at its path"
    assert ledger.read_bytes() == before and aside.read_bytes().startswith(before)
    if moment == MOMENTS[0]:
        assert failed.type is ChangedRecord and aside.read_bytes() == before and not llm.account.unjournalled
        assert llm.account.committed() == pytest.approx(SPENT)
        ask(llm)
        assert sends == [{"requests": 2}] and len(calls) == 2
        return
    assert failed.type is UnfinishedAppend and llm.account.unjournalled and len(aside.read_bytes()) > len(before)
    with pytest.raises(UnknownLedger):
        ask(llm)
    assert len(calls) == 1 and not sends
    if moment == MOMENTS[1]:
        assert len(read_ledger(ledger)) == 1              # the journal at its path as it was, its mark too
    else:
        with pytest.raises(ValueError, match="does not begin with"):
            read_ledger(ledger)                         # its mark now records the file renamed: not known, never empty


# --- DQ-03: a cap raise its writer never makes, or its record does not have -----------------------------------------

def _raise(case: str) -> dict:
    """A cap raise as the auditor's controls and these cases append it: as its writer journals one, but for ``case``."""
    if case == "without its caps":
        return {"state": "cap_raised"}
    row = {"state": "cap_raised", "previous": 0.05, "new": 0.2, "at": "2026-11-09T00:00:00Z", "reason": "SIMULATED"}
    return {**row, **UNMADE[case]}


UNMADE = {                  # cap raises ``Intake.raise_cap`` never journals
    "without its caps": {},
    "to $100": {"new": 100.0},
    "lowered": {"new": 0.01},
    "to the same cap": {"new": 0.05},
    "a cap that is text": {"new": "0.2"},
    "a cap that is true": {"new": True},
    "a cap that is not finite": {"new": float("inf")},
    "without when": {"at": None},
    "when, empty": {"at": ""},
    "a reason that is not text": {"reason": 3},
    "a field its writer never writes": {"approved_by": "SIMULATED"},
}


@pytest.mark.parametrize("case", UNMADE)
def test_a_cap_raise_its_writer_never_makes_is_refused_by_every_reading_and_writing(tmp_path, case):
    """DQ-03, the auditor's ``invalid_cap_raise`` and ``invalid_cap_raise_order``: appended after one settled request, it is
    not an entry. Every reading refuses it (the ledger as a run's page reads it, the whole journal's check, the session's
    account and its budget's reading), its cap is not raised past it, and the live client writes nothing after it and
    sends nothing; the ledger stays as it is. Before, the next request was sent and settled, and a rebuilt account
    accepted, while the session's budget reading refused it."""
    from adroit.agents.budget import journal_whole, read_ledger
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    with ledger.open("ab") as stream:
        stream.write((json.dumps(_raise(case)) + "\n").encode())
    after = ledger.read_bytes()
    for reading in (lambda: read_ledger(ledger), lambda: journal_whole(after, ledger)):
        assert "cap raise" in _refused(reading), "a cap raise its writer never makes was read as an entry"
    refused = _refused(lambda: ask(llm))
    assert len(calls) == 1, "a request was sent after a cap raise its writer never makes"
    assert "cap raise" in refused, refused
    for act in (lambda: service.account(service.session(session)), lambda: service.budget_status(session),
                lambda: service.raise_cap(session, 1.0, confirmed=True)):
        assert "cap raise" in _refused(act)
    assert ledger.read_bytes() == after


def test_a_cap_raise_its_record_lacks_stops_spending_as_it_stops_the_reading(tmp_path):
    """DQ-03, its reconciliation: a raise as its writer journals it, but one the session's record does not have (a
    raise interrupted between its ledger and its record, made so here: the record's write fails). The session's budget
    reading refuses it (``UnsettledSession``), and now so does its spending: the live client writes nothing more and
    sends nothing, a rebuilt account is refused before anything is reserved, and its cap is not raised past it; the
    ledger stays as it is. Before, the session spent on while its reading refused it."""
    from adroit.orchestrator import model_intake
    from adroit.orchestrator.model_intake import UnsettledSession
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    with patch.object(model_intake, "atomic_json", side_effect=OSError("SIMULATED: the record is not written")), \
            pytest.raises(OSError, match="SIMULATED"):
        service.raise_cap(session, 0.2, confirmed=True)
    ledger = service.folder(session) / "paid.jsonl"
    after = ledger.read_bytes()
    assert b'"cap_raised"' in after and service.session(session).cap_history == []
    with pytest.raises(UnsettledSession):
        service.budget_status(session)
    refused = _refused(lambda: ask(llm))
    assert len(calls) == 1, "the session spent while its budget's reading refused it"
    assert "that its record does not have" in refused, refused
    for act in (lambda: service.account(service.session(session)),
                lambda: service.raise_cap(session, 0.5, confirmed=True)):
        with pytest.raises(UnsettledSession, match="that its record does not have"):
            act()
    assert ledger.read_bytes() == after


def test_a_session_spends_under_the_cap_raises_its_writer_makes(tmp_path):
    """DQ-03's healthy counterpart: two raises made as a person makes them ($0.05 to $0.20, then to $0.50), between
    requests. The live client made before them spends on (under its own, lower cap: the record is read at each
    append); a client made after them spends under the raised cap; the session's budget reading agrees."""
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    service.raise_cap(session, 0.2, confirmed=True, reason="SIMULATED")
    ask(llm)
    service.raise_cap(session, 0.5, confirmed=True, reason="SIMULATED")
    fresh, sent = _client(service.folder(session) / "paid.jsonl", account=service.account(service.session(session)))
    assert llm.account.cap == 0.05 and fresh.account.cap == 0.5
    for _ in range(3):
        ask(fresh)
    status = service.budget_status(session)
    assert status["cap"] == 0.5 and status["spent"] == pytest.approx(5 * SPENT) and len(calls) + len(sent) == 5
    assert status["reserved_uncertain"] == 0


# --- DQ-04: a request reserved before its account froze ------------------------------------------------------------

def _shared(tmp: Path):
    """Two clients sharing one account (a $0.10 cap) and one session's ledger: (the service, the session, A, A's sends,
    B, B's sends)."""
    service, session, a, a_calls = _session(tmp)
    a.account.cap = 0.1
    b, b_calls = _client(a.ledger_path, account=a.account)
    return service, session, a, a_calls, b, b_calls


def test_a_request_reserved_before_its_account_froze_is_never_sent(tmp_path):
    """DQ-04, the auditor's ``dp_shared_freeze``: B reserves, then waits before its reservation is journalled; A's
    reservation is written whole and its sync fails, freezing the account; B then goes on. B's request is not sent
    (``UnknownLedger``): its reservation, journalled, is kept, uncertain, in the live account and the ledger, which
    agree; a new request is refused too. Before, B's request was sent after the freeze."""
    from adroit.agents.budget import UnknownLedger
    from adroit.core import durable
    service, session, a, a_calls, b, b_calls = _shared(tmp_path)
    reserved, go, out, reserve = threading.Event(), threading.Event(), {}, a.account.reserve

    def held(*args, **kw):
        key = reserve(*args, **kw)
        if threading.current_thread().name == "already reserved":
            reserved.set()
            assert go.wait(20)
        return key

    def second():
        try:
            ask(b)
        except Exception as error:
            out["second"] = error
    with patch.object(a.account, "reserve", held):
        thread = threading.Thread(name="already reserved", target=second)
        thread.start()
        assert reserved.wait(10)
        with patch.object(durable.os, "fsync", side_effect=OSError("SIMULATED sync failure")), \
                pytest.raises(OSError, match="SIMULATED sync failure"):
            ask(a)
        assert a.account.unjournalled
        go.set()
        thread.join(15)
    assert not thread.is_alive()
    assert not b_calls, "a request reserved before its account froze was sent"
    assert isinstance(out.get("second"), UnknownLedger), out
    assert not a_calls and a.account.committed() == pytest.approx(2 * BOUND) == \
        pytest.approx(_committed(service.folder(session) / "paid.jsonl"))
    with pytest.raises(UnknownLedger):
        ask(b)
    assert not b_calls


def test_two_clients_of_one_account_both_settle(tmp_path):
    """DQ-04's healthy counterpart: two clients of one account, from two threads at once: both requests are sent and
    settled, and the live account and the ledger agree."""
    service, session, a, a_calls, b, b_calls = _shared(tmp_path)
    threads = [threading.Thread(target=ask, args=(client,)) for client in (a, b)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)
    assert len(a_calls) + len(b_calls) == 2 and not a.account.unjournalled
    assert a.account.committed() == pytest.approx(2 * SPENT) == \
        pytest.approx(_committed(service.folder(session) / "paid.jsonl"))

"""The auditor's DQ recheck (2026-11-09), DR-01.

DR-01: a session's journal emptied in place (the same file, ``write_bytes(b"")``) once its append had checked it, or its
earlier lines removed in place once the new reservation was written and synced, had had a fresh mark written for what
was left, the request sent, and a paid request forgotten: the journal, a rebuilt account and the session then held
$0.0008 where $0.0016 had been spent. The mark damaged as it was written had let the request be sent too. An append is
now made under its journal's writers' lock (``durable._locked``; ``durable.writing`` for the recovery, which replaces it
whole; a lock on the journal's folder since the auditor's DR recheck, DS-01), and acknowledged only for what it checked and
wrote: the journal must hold exactly the bytes checked and then its own once written and synced
(``durable._as_written``), the mark records those, and the mark must be read back as written, the journal holding what
it records (``durable._recorded``). Else ``UnfinishedAppend``: the account freezes, its reservation kept, nothing sent,
and every reading refuses the journal, never reading it as holding less.

Every dollar is simulated; no provider is contacted and nothing is sent."""

from __future__ import annotations

import json
import os
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import SPENT, _session
from tests.orchestrator.test_dq_fixes import BOUND, _committed

# --- DR-01: the journal changed in place during an append -----------------------------------------------------------


def _emptied(ledger: Path) -> None:
    ledger.write_bytes(b"")


def _earlier_removed(ledger: Path) -> None:
    """Every line but the last removed, in place: the new reservation kept, the request paid before erased."""
    ledger.write_bytes(ledger.read_bytes().splitlines(keepends=True)[-1])


def _bill_lowered(ledger: Path) -> None:
    """The settled request's bill rewritten in place to $0, the journal as long as before."""
    data, n = re.subn(rb'"cost_usd": [0-9.e-]+', lambda m: b'"cost_usd": 0.' + b"0" * (len(m[0]) - 14),
                      ledger.read_bytes())
    assert n == 1, data
    ledger.write_bytes(data)


def _mark_damaged(ledger: Path) -> None:
    from adroit.core.durable import mark_of
    mark_of(ledger).write_text("{")


def _mark_shortened(ledger: Path) -> None:
    """A mark that reads, recording only the new reservation's line (a history from which the paid request is gone)."""
    from adroit.core.durable import Held, mark_of
    last = Held.of(ledger.read_bytes().splitlines(keepends=True)[-1])
    mark_of(ledger).write_text(json.dumps({"size": last.size, "sha256": last.sha256}))


# (when, during the next reservation's append, what is done to the journal or its mark, in place)
REWRITES = {
    "emptied once checked": ("checked", _emptied),                    # the auditor's same_inode_after_check
    "its paid request removed once synced": ("synced", _earlier_removed),   # the auditor's same_inode_after_sync
    "its bill lowered once checked": ("checked", _bill_lowered),
    "emptied once synced": ("synced", _emptied),
    "its paid request removed once marked": ("marked", _earlier_removed),
    "its mark damaged once written": ("marked", _mark_damaged),       # the auditor's mark_corrupt_inside_publication
    "its mark shortened once written": ("marked", _mark_shortened),
}


@contextmanager
def _rewritten(ledger: Path, moment: str, change):
    """``change`` made to ``ledger`` (the same file, in place), once, at ``moment`` of the next reservation's append:
    once the append has checked it, once its line is written and synced, or once the mark beside it is written. Yields
    [whether it is still to happen]."""
    from adroit.core import durable
    armed, active = [True], [False]
    checker, syncer, marker = durable._appendable, os.fsync, durable.write_atomic

    def now(when: str) -> None:
        if when == moment and active[0] and armed[0]:
            armed[0] = False
            change(ledger)

    def checked(path, handle, data, *rest):
        found = checker(path, handle, data, *rest)
        active[0] = Path(path) == ledger and b'"state": "reserved"' in data
        now("checked")
        return found

    def synced(handle):
        syncer(handle)
        now("synced")

    def marked(path, *args, **kw):
        done = marker(path, *args, **kw)
        if Path(path) == durable.mark_of(ledger):
            now("marked")
        return done
    with patch.object(durable, "_appendable", checked), patch.object(durable.os, "fsync", synced), \
            patch.object(durable, "write_atomic", marked):
        yield armed


@pytest.mark.parametrize("case", REWRITES)
def test_a_journal_changed_in_place_during_an_append_is_never_sent_past_nor_read_as_less(tmp_path, case):
    """DR-01, the auditor's ``dq_inside_append`` and its kin: after one settled request, the next reservation's journal (the
    same file) is changed in place as it is appended to: emptied, its paid request removed or its bill lowered, once
    checked or once written and synced or once marked, or its mark damaged or shortened once written. The append
    fails (``UnfinishedAppend``), the account freezes and keeps the request's reservation, and nothing is sent; the
    journal is refused by every reading (a run's page, a rebuilt account, the session's budget), never read as holding
    less than was spent. Before, a fresh mark was written for what was left, the request sent, and the journal, a
    rebuilt account and the session held $0.0008 where $0.0016 had been spent."""
    from adroit.agents.budget import UnknownLedger
    from adroit.core.durable import UnfinishedAppend
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = Path(os.path.abspath(service.folder(session) / "paid.jsonl"))
    moment, change = REWRITES[case]
    with _rewritten(ledger, moment, change) as armed:
        try:
            ask(llm)
        except (OSError, ValueError) as error:      # UnfinishedAppend; at the pin, its next entry's refusal after it
            failed = error
        else:
            failed = None
    assert not armed[0], "the journal was not changed"
    assert len(calls) == 1, f"a request was sent after this change during its append: {case}"
    assert isinstance(failed, UnfinishedAppend), failed
    assert llm.account.unjournalled, "the append failed and its account was not frozen"
    assert llm.account.committed() == pytest.approx(SPENT + BOUND), "the request's reservation was not kept"
    assert _committed(ledger) is None, f"the journal {case} was read as holding {_committed(ledger)}"
    for reading in (lambda: service.account(service.session(session)), lambda: service.budget_status(session)):
        with pytest.raises(ValueError):
            reading()
    with pytest.raises(UnknownLedger):
        ask(llm)
    assert len(calls) == 1


def test_an_append_acknowledges_what_it_checked_and_wrote(tmp_path):
    """DR-01's healthy counterpart: three requests. At each send, the journal at the client's path, read as every
    reading reads it (its mark checked), holds every earlier request (its id and bill) and the new reservation; after
    them, its mark records its whole bytes, and a rebuilt account and the session's budget hold what it holds."""
    from adroit.agents.budget import read_ledger, settled_and_uncertain
    from adroit.core.durable import Held, marked
    service, session, llm, calls = _session(tmp_path)
    ledger = Path(os.path.abspath(service.folder(session) / "paid.jsonl"))
    seen, send = [], llm._inner._client.messages.create

    def create(**kw):
        requests = read_ledger(ledger)
        seen.append({key: (r.state, r.cost_usd) for key, r in requests.items()})
        return send(**kw)
    llm._inner._client.messages.create = create
    for _ in range(3):
        ask(llm)
    assert [len(s) for s in seen] == [1, 2, 3] and all(set(seen[i]) < set(seen[i + 1]) for i in range(2))
    for s in seen:
        *earlier, (new, _) = s.values()
        assert new == "open" and all(state == "settled" and cost == pytest.approx(SPENT)
                                         for state, cost in earlier), s
    assert marked(ledger) == Held.of(ledger.read_bytes())
    held = sum(settled_and_uncertain(read_ledger(ledger)))
    assert held == pytest.approx(3 * SPENT) == pytest.approx(service.account(service.session(session)).committed())
    assert service.budget_status(session)["spent"] == pytest.approx(3 * SPENT) and not llm.account.unjournalled


# --- the writers' lock ----------------------------------------------------------------------------------------------

@contextmanager
def _held_by_another(ledger: Path):
    """The journal's writers' lock held by another writer (``durable._writers_lock``, its own open folder) until the
    block ends (the auditor's DR recheck, DS-01: the lock is the folder's, no longer the journal's own file's)."""
    from adroit.core.durable import _writers_lock
    with _writers_lock(ledger):
        yield


def _waits(act, ledger: Path) -> tuple[bytes, threading.Thread, dict]:
    """``act`` started in a thread while another writer holds ``ledger``'s writers' lock, given 0.5 s: (the journal's
    bytes then, the thread, its outcome)."""
    out: dict = {}

    def run():
        try:
            out["value"] = act()
        except Exception as error:          # reported to the test
            out["error"] = error
    thread = threading.Thread(target=run)
    thread.start()
    thread.join(0.5)
    return ledger.read_bytes(), thread, out


def test_an_append_waits_while_another_writer_holds_its_journal(tmp_path):
    """While another writer holds the journal's writers' lock, the next request's reservation is not written, and the
    request is not sent; once it is released, the request is journalled and sent, and the journal and the account
    agree."""
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = Path(os.path.abspath(service.folder(session) / "paid.jsonl"))
    before = ledger.read_bytes()
    with _held_by_another(ledger):
        during, thread, out = _waits(lambda: ask(llm), ledger)
        assert during == before and len(calls) == 1, "an append wrote while another writer held the journal's lock"
    thread.join(15)
    assert not thread.is_alive() and "error" not in out, out
    assert len(calls) == 2 and _committed(ledger) == pytest.approx(2 * SPENT) == pytest.approx(llm.account.committed())


def test_a_recovery_waits_while_an_append_holds_its_journal(tmp_path):
    """The torn-line recovery, which replaces the journal whole, takes the journal's writers' lock too
    (``durable.writing``): while an append holds it, the journal is not rewritten; once it is released, it is
    recovered."""
    from adroit.agents.budget import recover_torn_tail
    from tests.orchestrator.test_dp_fixes import EXTENSIONS
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = Path(os.path.abspath(service.folder(session) / "paid.jsonl"))
    with ledger.open("ab") as stream:
        stream.write(EXTENSIONS["a torn line"])
    torn = ledger.read_bytes()
    with _held_by_another(ledger):
        during, thread, out = _waits(lambda: recover_torn_tail(ledger), ledger)
        assert during == torn and thread.is_alive(), "a recovery rewrote the journal while an append held its lock"
    thread.join(15)
    assert not thread.is_alive() and str(out.get("value", out)).startswith("recovered paid.jsonl"), out
    assert ledger.read_bytes() != torn and _committed(ledger) == pytest.approx(SPENT + 0.02)


def test_an_append_alone_marks_only_what_it_wrote(tmp_path):
    """``durable.append_held`` itself, for every append-only record: a record emptied in place once its line is synced
    is not marked (``UnfinishedAppend``); the mark still records what was there before, so the record now reads as
    damaged, never as one holding less."""
    from adroit.core import durable
    record = tmp_path / "record.jsonl"
    held = durable.append_held(record, b'{"n": 1}\n', None, whole=lambda data, path: None)
    syncer, done = os.fsync, []

    def synced(handle):
        syncer(handle)
        if not done:
            done.append(record.write_bytes(b""))
    with patch.object(durable.os, "fsync", synced), pytest.raises(durable.UnfinishedAppend, match="changed in place"):
        durable.append_held(record, b'{"n": 2}\n', held, whole=lambda data, path: None)
    assert durable.marked(record) == held and record.read_bytes() == b""
    assert not held.begins(record.read_bytes())

"""The auditor's DS recheck (2026-11-10), DT-01.

DT-01: a paid journal, its writers' lock and its mark were not one by every name it could be reached by. A request
asked through a link to a session's journal, or by a hard link's name, was appended to the journal's file and sent, its
mark written beside the other name: the journal's own mark still recorded less, and the journal cut back to it was read
as $0.0008 less spent, without a word (the auditor's ``ds_alias_without_recovery``); through a link, during a recovery, too
(``ds_linked_journal``). And a writer that waited for the lock of a folder since renamed away, an equal copy put at its
path, appended and sent its request while another held the lock of the folder there (``ds_folder_replaced``). A paid
journal is now read and written only by its own name (``durable.own``: not a link, its file with no other name), and a
writer, once it holds the lock, must find the folder it locked still at the journal's path (``durable._folder_at``).

Every dollar is simulated; no provider is contacted and nothing is sent."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import SPENT, _client, _refused
from tests.orchestrator.test_dp_fixes import EXTENSIONS
from tests.orchestrator.test_dq_fixes import _committed

ROOT = Path(__file__).parents[2]


def _link_beside(ledger: Path) -> Path:
    (ledger.parent / "alias.jsonl").symlink_to(ledger.name)
    return ledger.parent / "alias.jsonl"


def _link_elsewhere(ledger: Path) -> Path:
    (ledger.parents[1] / "other").mkdir()
    (ledger.parents[1] / "other" / "paid.jsonl").symlink_to(ledger)
    return ledger.parents[1] / "other" / "paid.jsonl"


def _hard_beside(ledger: Path) -> Path:
    os.link(ledger, ledger.parent / "alias.jsonl")
    return ledger.parent / "alias.jsonl"


def _hard_elsewhere(ledger: Path) -> Path:
    (ledger.parents[1] / "other").mkdir()
    os.link(ledger, ledger.parents[1] / "other" / "paid.jsonl")
    return ledger.parents[1] / "other" / "paid.jsonl"


# another name for a session's journal, as the auditor made them (a hard link and a link, in its folder and in another);
# the hard links first: a link is refused too where its path no longer leads to the file opened (DQ-02)
ALIASES = {"a hard link in its folder": _hard_beside, "a hard link in another folder": _hard_elsewhere,
           "a link in its folder": _link_beside, "a link in another folder": _link_elsewhere}


@pytest.mark.parametrize("alias", ALIASES)
def test_a_request_by_another_name_of_its_journal_is_refused_before_it_is_sent(tmp_path, alias):
    """DT-01, the auditor's ``ds_alias_without_recovery``: a journal of one settled request, and ``alias`` made to it. A
    client asking by that name is refused before anything is sent or written, and the journal's writer, asked by it
    directly, refuses too; every reading by it is refused, naming why. The journal and its mark are as they were. Once
    the other name is removed, the journal reads and spends on by its own. Before, the request was sent, its mark
    written beside the other name, and the journal cut back to its own mark read as $0.0008 less spent."""
    from adroit.agents.budget import journal_whole, read_ledger, settled_and_uncertain
    from adroit.core import durable
    ledger = tmp_path / "job" / "paid.jsonl"
    llm, _ = _client(ledger, cap=0.25)
    ask(llm)
    first = ledger.read_bytes()
    other = ALIASES[alias](ledger)
    again, calls = _client(other, cap=0.25)
    refused = _refused(lambda: ask(again))
    assert calls == [], "a request was sent through another name of its journal"
    assert "by its own name" in refused, refused
    with pytest.raises(durable.ChangedRecord, match="by its own name"):
        durable.append_held(other, b'{"n": 1}\n', durable.Held.of(first), whole=journal_whole)
    with pytest.raises(ValueError, match="by its own name"):
        read_ledger(other)
    assert ledger.read_bytes() == first and durable.marked(ledger) == durable.Held.of(first)
    assert not os.path.lexists(durable.mark_of(other)), "a mark was written beside another name of the journal"
    if "hard" in alias:                             # its own name is not its only one: not read by it either
        with pytest.raises(ValueError, match="2 names"):
            read_ledger(ledger)
    other.unlink()
    ask(llm)
    assert settled_and_uncertain(read_ledger(ledger)) == (pytest.approx(2 * SPENT), 0)


def test_a_hard_link_made_while_its_append_checks_it_is_refused(tmp_path):
    """A hard link made to the journal once its append has checked it, before it writes: refused, nothing written,
    nothing sent (the writer's own check, apart from every reading's)."""
    from adroit.core import durable
    ledger = tmp_path / "job" / "paid.jsonl"
    llm, calls = _client(ledger, cap=0.25)
    ask(llm)
    first, real = ledger.read_bytes(), durable._appendable

    def checked(path, *args, **kw):
        found = real(path, *args, **kw)
        if not os.path.lexists(ledger.with_name("alias.jsonl")):
            os.link(ledger, ledger.with_name("alias.jsonl"))
        return found
    with patch.object(durable, "_appendable", checked):
        refused = _refused(lambda: ask(llm))
    assert len(calls) == 1, "a request was sent once another name was made for its journal"
    assert "2 names" in refused and ledger.read_bytes() == first, refused


# another process's client of the journal, by the name given, as ADROIT's paid commands build theirs (its provider
# simulated): one request, said once it is about to be asked, then what came of it
APPENDER = """
import json, sys
from pathlib import Path
from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import _client
llm, calls = _client(Path(sys.argv[1]), cap=0.25)
print("asking", flush=True)
try:
    ask(llm)
    print(json.dumps({"sent": len(calls)}), flush=True)
except ValueError as error:
    print(json.dumps({"sent": len(calls), "refused": str(error)}), flush=True)
"""


def _linked_folder(ledger: Path) -> Path:
    (ledger.parents[1] / "alias").symlink_to(ledger.parent, target_is_directory=True)
    return ledger.parents[1] / "alias" / ledger.name


ROUTES = {"a linked folder": _linked_folder, "a link to it in its folder": _link_beside,
          "a link to it in another folder": _link_elsewhere}


@pytest.mark.parametrize("route", ROUTES)
def test_a_request_by_another_route_during_a_recovery_waits_or_is_refused(tmp_path, route):
    """DT-01, the auditor's ``ds_linked_journal``: a journal with a torn reservation is recovered, and once the recovered
    journal is in its place, before its mark is written, another process asks a request by ``route``. Through a linked
    folder, the journal's own folder, it waits for the recovery, then is journalled, sent and marked with the whole
    journal, which cut back is refused. Through a link to the journal it is refused before anything is sent or
    written, and the journal is the recovery's, marked so. Before, through a link to it, the request was sent, its mark
    written beside the link, and the journal cut back to the recovery's mark read as $0.0008 less spent."""
    from adroit.agents.budget import recover_torn_tail
    from adroit.core import durable
    ledger = tmp_path / "job" / "paid.jsonl"
    llm, _ = _client(ledger, cap=0.25)
    ask(llm)
    with ledger.open("ab") as stream:
        stream.write(EXTENSIONS["a torn line"])
    torn, other = ledger.read_bytes(), ROUTES[route](ledger)
    real, child, recovered, during = durable.write_atomic, [], [], []

    def atomic(path, *args, **kw):
        if Path(path) == durable.mark_of(ledger) and not child:
            recovered.append(ledger.read_bytes())
            child.append(subprocess.Popen([sys.executable, "-c", APPENDER, str(other)], cwd=ROOT,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
            assert child[0].stdout.readline().strip() == "asking", child[0].communicate()[0]
            try:
                child[0].wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            during.append((child[0].poll(), ledger.read_bytes()))
        return real(path, *args, **kw)
    with patch.object(durable, "write_atomic", atomic):
        said = recover_torn_tail(ledger)
    assert said.startswith("recovered paid.jsonl") and child, said
    output = child[0].communicate(timeout=60)[0]
    done = json.loads(output.splitlines()[-1])
    assert during[0][1] == recovered[0], "an append was made to a recovered journal before its mark was written"
    assert any(side.read_bytes() == torn for side in ledger.parent.glob("paid.jsonl.torn-*"))
    if route == "a linked folder":
        assert during[0][0] is None and done == {"sent": 1}, output
        whole = ledger.read_bytes()
        assert durable.marked(ledger) == durable.Held.of(whole) and _committed(ledger) == pytest.approx(
            2 * SPENT + 0.02)
        ledger.write_bytes(recovered[0])
        assert _committed(ledger) is None, "the journal cut back to what its recovery wrote was read as less spent"
        return
    assert done["sent"] == 0 and "by its own name" in done.get("refused", ""), \
        "a request was sent through a link to its journal during its recovery"
    assert ledger.read_bytes() == recovered[0] and durable.marked(ledger) == durable.Held.of(recovered[0])
    assert not os.path.lexists(durable.mark_of(other)), "a mark was written beside a link to the journal"


WAITERS = ("a request's append", "a recovery")


def test_a_writer_whose_folder_is_replaced_while_it_waits_for_its_lock_is_refused(tmp_path):
    """DT-01, the auditor's ``ds_folder_replaced``: a request's append waiting for its journal's writers' lock, held by
    another; its folder is then renamed away, an equal copy put at its path, the copy's lock taken by another and the
    first released. The waiter, holding the lock of a folder no longer there, is refused at once: nothing journalled
    in either folder, nothing sent. Before, it appended its reservation to the copy and called its provider while
    another held the copy's lock."""
    _waits_while_its_folder_is_replaced(tmp_path, WAITERS[0])


def test_a_recovery_whose_folder_is_replaced_while_it_waits_for_its_lock_is_refused(tmp_path):
    """The same for a torn-line recovery waiting for the lock: refused, neither journal changed, no side copy made."""
    _waits_while_its_folder_is_replaced(tmp_path, WAITERS[1])


def _waits_while_its_folder_is_replaced(tmp: Path, waiter: str) -> None:
    from adroit.agents.budget import recover_torn_tail
    ledger = tmp / "current" / "paid.jsonl"
    llm, _ = _client(ledger, cap=0.25)
    ask(llm)
    if waiter == "a recovery":
        with ledger.open("ab") as stream:
            stream.write(EXTENSIONS["a torn line"])
    before, entries = ledger.read_bytes(), _entries(ledger.parent)
    other, calls = _client(ledger, cap=0.25)
    out: dict = {}
    waiting, real = threading.Event(), fcntl.flock

    def flock(handle, how):
        if threading.current_thread().name == "waiter" and how == fcntl.LOCK_EX:     # the writers' lock, waited for
            waiting.set()
        return real(handle, how)

    def wait():
        try:
            out["done"] = recover_torn_tail(ledger) if waiter == "a recovery" else ask(other)
        except ValueError as error:
            out["refused"] = str(error)
    held = os.open(ledger.parent, os.O_RDONLY | os.O_DIRECTORY)
    fcntl.flock(held, fcntl.LOCK_EX)
    thread = threading.Thread(target=wait, name="waiter")
    copy = None
    with patch.object(fcntl, "flock", flock):
        try:
            thread.start()
            assert waiting.wait(10)
            thread.join(0.2)
            assert thread.is_alive(), out
            ledger.parent.rename(tmp / "old")
            shutil.copytree(tmp / "old", ledger.parent)
            copy = os.open(ledger.parent, os.O_RDONLY | os.O_DIRECTORY)
            fcntl.flock(copy, fcntl.LOCK_EX)
            os.close(held)
            held = None
            thread.join(5)
            if waiter == "a recovery":
                assert ledger.read_bytes() == before and not list(ledger.parent.glob("*.torn-*")), \
                    "a recovery rewrote a journal in a folder put in its place while it waited"
            assert calls == [] and ledger.read_bytes() == before, \
                "a request was journalled and sent in a folder put in its place while its writer waited"
            assert not thread.is_alive() and "while its writer waited for its writers' lock" in out.get("refused", ""), \
                out
        finally:
            for handle in (held, copy):
                if handle is not None:
                    os.close(handle)
            thread.join(30)
    for folder in (ledger.parent, tmp / "old"):
        assert (folder / "paid.jsonl").read_bytes() == before
        assert _entries(folder) == entries


def _entries(folder: Path) -> list[str]:
    """The entries in a journal's folder but the run lock's file, which a recovery makes before it waits."""
    return sorted(p.name for p in folder.iterdir() if p.name != ".track1.lock")

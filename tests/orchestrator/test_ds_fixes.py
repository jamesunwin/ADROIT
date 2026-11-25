"""The auditor's DR recheck (2026-11-09), DS-01.

DS-01: a torn-line recovery held its journal's writers' lock, a lock on the journal's own file, and put the recovered
journal in its place: another file. A request's append in another process, opening the journal meanwhile, locked that
new file, which no one held, wrote and marked its reservation and its settlement, and its request was sent; the
recovery then wrote its own mark, of the journal before them, over the append's. The journal still read correctly,
but its paid request was no longer covered by its mark: cut away, the journal was read as $0.0008 less spent, without
a word. The writers' lock is now a lock on the folder the journal is in (``durable._writers_lock``), which stays as the
journal is replaced in it, taken by every append before it opens the journal (``durable._locked``) and by the recovery
(``durable.writing``) until its mark is written: no append is made to a recovered journal before its mark is written,
nor a mark written over a later append's.

Every dollar is simulated; no provider is contacted and nothing is sent."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import SPENT, _client
from tests.orchestrator.test_dp_fixes import EXTENSIONS
from tests.orchestrator.test_dq_fixes import _committed

ROOT = Path(__file__).parents[2]

# another process's client of the same journal, as ADROIT's paid commands build theirs (its provider simulated): one
# request, said once it is about to be asked and again once it is done
APPENDER = """
import json, sys
from pathlib import Path
from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import _client
llm, calls = _client(Path(sys.argv[1]), cap=0.25)
print("asking", flush=True)
ask(llm)
print(json.dumps({"sent": len(calls)}), flush=True)
"""


def test_an_append_waits_while_a_recovery_that_replaced_its_journal_holds_its_lock(tmp_path):
    """DS-01, the auditor's ``dr_recovery_overlap``: a journal of one settled request and a torn reservation is recovered.
    Once the recovered journal is in its place (another file) and before its mark is written, another process asks a
    request against the journal. It is not journalled, nor sent, while the recovery holds the writers' lock; once the
    recovery is done, it is, and its mark records the whole journal, the recovery's lines and its own: the journal cut
    back to what the recovery wrote is refused by every reading, never read as less spent. Before, the other process
    locked the new file, its request was journalled, marked and sent during the recovery, and the recovery's mark, of
    the journal before it, was written over its own: the journal cut back was read as $0.0008 less spent."""
    from adroit.agents.budget import recover_torn_tail
    from adroit.core import durable
    ledger = tmp_path / "job" / "paid.jsonl"
    llm, calls = _client(ledger, cap=0.25)
    ask(llm)
    first = ledger.stat().st_ino
    with ledger.open("ab") as stream:
        stream.write(EXTENSIONS["a torn line"])
    real, other, recovered, during = durable.write_atomic, [], [], []

    def atomic(path, *args, **kw):
        if Path(path) == durable.mark_of(ledger) and not other:
            assert ledger.stat().st_ino != first, "the recovered journal was not put in the first one's place"
            recovered.append(ledger.read_bytes())
            other.append(subprocess.Popen([sys.executable, "-c", APPENDER, str(ledger)], cwd=ROOT,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True))
            assert other[0].stdout.readline().strip() == "asking", other[0].communicate()[0]
            try:
                other[0].wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            during.append((other[0].poll(), ledger.read_bytes()))
        return real(path, *args, **kw)
    with patch.object(durable, "write_atomic", atomic):
        said = recover_torn_tail(ledger)
    assert said.startswith("recovered paid.jsonl") and other, said
    finished, journal = during[0]
    assert finished is None and journal == recovered[0], \
        "an append was made to the journal a recovery had put in its place, its mark not yet written"
    output = other[0].communicate(timeout=60)[0]
    assert other[0].returncode == 0 and json.loads(output.splitlines()[-1]) == {"sent": 1}, output
    whole = ledger.read_bytes()
    assert whole.startswith(recovered[0]) and len(whole) > len(recovered[0])
    assert durable.marked(ledger) == durable.Held.of(whole), "the recovery's mark was written over a later append's"
    assert _committed(ledger) == pytest.approx(2 * SPENT + 0.02)
    ledger.write_bytes(recovered[0])                # the request appended after the recovery cut away, in place
    assert _committed(ledger) is None, "the journal cut back to what its recovery wrote was read as less spent"


def test_the_writers_lock_is_one_through_a_linked_folder(tmp_path):
    """The writers' lock is the folder's, opened by the record's path: a record reached through a link to its folder
    is locked by the same lock, so that an append through the link waits while a writer holds it by the folder's own
    path, and is then made and marked."""
    from adroit.core import durable
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)
    whole = lambda data, path: None             # noqa: E731
    held = durable.append_held(real / "r.jsonl", b'{"n": 1}\n', None, whole=whole)
    out: dict = {}
    thread = threading.Thread(target=lambda: out.update(
        held=durable.append_held(tmp_path / "link" / "r.jsonl", b'{"n": 2}\n', held, whole=whole)))
    with durable._writers_lock(real / "r.jsonl"):
        thread.start()
        thread.join(0.5)
        assert thread.is_alive() and (real / "r.jsonl").read_bytes() == b'{"n": 1}\n', \
            "an append through a linked folder wrote while its record's writers' lock was held"
    thread.join(15)
    assert not thread.is_alive()
    assert durable.marked(real / "r.jsonl") == out["held"] == durable.Held.of(b'{"n": 1}\n{"n": 2}\n')

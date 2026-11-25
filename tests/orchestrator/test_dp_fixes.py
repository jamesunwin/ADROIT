"""The auditor's DO recheck (2026-11-09), DP-01 and DP-02.

DP-01: a paid ledger's writers checked only that it still began with what they held, not that the whole of it was a
journal its writers could have kept. The auditor's cases, after one settled $0.0008 simulated request: a reservation's write
cut short after 120 bytes, then the same client's next request sent, its line written after the torn one, so that the
recoverable torn last line became damage in the middle of the journal; a malformed line appended after the client's
last, then the next request sent; a whole last entry without its newline, the next line joined to it; a run's own ledger
torn by an earlier attempt, opened and its first request sent; and a reservation written whole whose sync then failed:
released from the live account, kept in the ledger, and the next request sent with the journal holding $0.082704
against the $0.05 cap. Each writer now checks the whole ledger (``budget.journal_whole``) in its append
(``durable.append_held``), and a write that fails once begun leaves its account reserving nothing more, its reservation
kept (``BudgetAccount.unjournalled``).

DP-02: ``adroit ledger recover`` read the journal raw, rewrote it with its recovery entry, and only then refused it for
not beginning with what its mark records. It now reads it as every reading does, first.

DP-03, the Activity page's diagnosis of a log that cannot be read, is ``tests/ui/test_dp_activity.py``. Every dollar is
simulated; no provider is contacted and nothing is sent."""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import SPENT, _client, _entries, _in_job, _refused, _session

ROOT = Path(__file__).parents[2]
BOUND = 0.040952                    # the reservation of one simulated request (its bound)


def _cut_short(after: int = 120):
    """``os.write`` in ``durable`` that writes a reservation's first ``after`` bytes, then fails (a storage error
    part way through the line), once."""
    from adroit.core import durable
    real, armed = os.write, [True]

    def write(handle, data):
        if armed[0] and b'"state": "reserved"' in bytes(data):
            armed[0] = False
            real(handle, bytes(data)[:after])
            raise OSError("SIMULATED storage error part way through the line")
        return real(handle, data)
    return patch.object(durable.os, "write", write)


def _states(ledger: Path) -> dict:
    from adroit.agents.budget import read_ledger, settled_and_uncertain
    return dict(zip(("settled", "uncertain"), settled_and_uncertain(read_ledger(ledger))))


@pytest.mark.parametrize("after", [120, 170])
def test_a_reservation_whose_write_is_cut_short_is_kept_and_nothing_more_is_sent(tmp_path, after):
    """DP-01, the auditor's first case: the reservation's write cut short after 120 bytes (before its bound), or after 170
    (after it). The attempt fails before it is sent; its reservation stays in the live account, uncertain, as the
    ledger may hold it; the same client's next request is refused before anything is reserved, nothing written; the
    ledger stays torn, and a fresh account refuses it too. Its recovery: refused where the torn bytes do not show the
    bound, the budget blocked and the journal as it was; else the session reads the torn reservation as uncertain,
    and spends on."""
    from adroit.agents.budget import TornLedger, recover_torn_tail
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    before = ledger.read_bytes()
    llm.invocation = "SIMULATED step"
    with _cut_short(after), pytest.raises(OSError, match="SIMULATED storage error"):
        ask(llm)
    torn = ledger.read_bytes()
    assert len(calls) == 1 and torn.startswith(before) and len(torn) == len(before) + after
    assert llm.account.committed() == pytest.approx(SPENT + BOUND), "the reservation whose write failed was released"
    refused = _refused(lambda: ask(llm))
    assert len(calls) == 1, "the next request was sent after a write failed once begun"
    assert "nothing more is reserved or sent under its account" in refused, refused     # ``UnknownLedger``
    assert ledger.read_bytes() == torn, "something was written after the torn line"
    for read in (lambda: _states(ledger), lambda: service.account(service.session(session))):
        with pytest.raises(TornLedger):
            read()
    if after == 120:
        with pytest.raises(ValueError, match="torn before its provider or bound"):
            recover_torn_tail(ledger)
        assert ledger.read_bytes() == torn
        return
    assert recover_torn_tail(ledger).startswith("recovered paid.jsonl")
    service.raise_cap(session, 1.0, confirmed=True)
    again, sent = _client(ledger, account=service.account(service.session(session)))
    ask(again)
    status = service.budget_status(session)
    assert len(sent) == 1 and status["spent"] == pytest.approx(2 * SPENT)
    assert status["reserved_uncertain"] == pytest.approx(BOUND)


EXTENSIONS = {
    "a line that is not JSON": b'{"corrupt":}\n',
    "a line that is not an entry": b'{"x": 1}\n',
    "a settlement never reserved": b'{"id": "nowhere", "state": "settled", "cost_usd": 0.01}\n',
    "a torn line": b'{"id": "cut", "state": "reserved", "provider": "anthropic", "reserved_usd": 0.02, "model": "cla',
}


@pytest.mark.parametrize("extension", EXTENSIONS)
def test_nothing_is_written_or_sent_after_what_is_not_whole(tmp_path, extension):
    """DP-01, the auditor's damaged extension and its kin: after the client's last write, another writer leaves a line that
    is not one its writers could have kept. The client's next request is refused before it is sent (``ChangedRecord``,
    naming it), its reservation released (nothing was written), nothing written after the line, the ledger and its mark
    as they were."""
    from adroit.core.durable import mark_of
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    with ledger.open("ab") as stream:
        stream.write(EXTENSIONS[extension])
    folder = _entries(ledger.parent)
    refused = _refused(lambda: ask(llm))
    assert len(calls) == 1, "a request was sent after a line that is not whole"
    assert _entries(ledger.parent) == folder and mark_of(ledger).exists()
    assert "nothing is written after what it holds, which is not whole" in refused, refused
    assert llm.account.committed() == pytest.approx(SPENT) and not llm.account.unjournalled


def test_a_whole_last_entry_without_its_newline_is_ended_before_the_next(tmp_path):
    """DP-01, the auditor's legacy case: a ledger from before marks whose whole last entry has no newline reads as it holds;
    the next line is written after a newline, never joined to it, and the ledger reads both requests."""
    from adroit.core.durable import mark_of
    service, session, llm, _ = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    legacy = ledger.read_bytes().rstrip(b"\n")
    ledger.write_bytes(legacy)
    mark_of(ledger).unlink()
    assert _states(ledger) == {"settled": pytest.approx(SPENT), "uncertain": 0}
    again, sent = _client(ledger, account=service.account(service.session(session)))
    ask(again)
    assert len(sent) == 1 and ledger.read_bytes().startswith(legacy + b"\n{")
    assert _states(ledger) == {"settled": pytest.approx(2 * SPENT), "uncertain": 0}
    assert all(json.loads(line) for line in ledger.read_bytes().splitlines())


def test_a_reservation_written_whole_whose_sync_fails_is_kept_and_the_accounts_agree(tmp_path):
    """DP-01, the auditor's sync failure: the reservation's line is written whole and its sync fails. The live account keeps
    it (it was the ledger's), as a rebuilt account does; the live client's next request is refused before it is
    reserved, and nothing is sent. Before, the live account released it and sent the next, the journal then holding
    $0.082704 against the $0.05 cap."""
    from adroit.agents.budget import BudgetExceeded
    from adroit.core import durable
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    with patch.object(durable.os, "fsync", side_effect=OSError("SIMULATED sync failure")), \
            pytest.raises(OSError, match="SIMULATED sync failure"):
        ask(llm)
    status = service.budget_status(session)
    assert llm.account.committed() == pytest.approx(status["spent"] + status["reserved_uncertain"]) == \
        pytest.approx(SPENT + BOUND), "the reservation whose write failed was released"
    refused = _refused(lambda: ask(llm))
    assert len(calls) == 1, "the next request was sent after a write failed once begun"
    assert "nothing more is reserved or sent under its account" in refused, refused
    fresh, sent = _client(service.folder(session) / "paid.jsonl", account=service.account(service.session(session)))
    assert fresh.account.committed() == pytest.approx(SPENT + BOUND)
    with pytest.raises(BudgetExceeded):
        ask(fresh)
    assert not sent


def test_a_run_s_torn_ledger_is_refused_at_its_opening_and_nothing_is_sent(tmp_path):
    """DP-01, the auditor's job case: a run's own ledger torn by an earlier attempt. The next attempt's opening is refused
    (``TornLedger``, naming its recovery), nothing written; a client made all the same refuses at its first line; nothing
    is sent, and the ledger is as it was. Recovered, the run opens it and spends on."""
    from adroit.agents.budget import TornLedger, recover_torn_tail
    from adroit.core.durable import ChangedRecord
    from adroit.orchestrator import preflight
    ledger = tmp_path / "paid.jsonl"
    with _in_job(tmp_path, "attempt-a"):
        preflight.open_job_ledger(ledger)
        llm, _ = _client(ledger, cap=1)
        ask(llm)
    with ledger.open("ab") as stream:
        stream.write(EXTENSIONS["a torn line"])
    torn = _entries(tmp_path)
    with _in_job(tmp_path, "attempt-b"):
        with pytest.raises(TornLedger):
            preflight.open_job_ledger(ledger)
        again, sent = _client(ledger, cap=1)
        with pytest.raises(ChangedRecord):
            ask(again)
    assert not sent and _entries(tmp_path) == torn
    recover_torn_tail(ledger)
    with _in_job(tmp_path, "attempt-c"):
        preflight.open_job_ledger(ledger)
        last, sent = _client(ledger, cap=1)
        ask(last)
    assert len(sent) == 1 and _states(ledger) == {"settled": pytest.approx(2 * SPENT), "uncertain": 0.02}


def test_a_paid_command_in_a_run_whose_ledger_is_torn_is_refused_naming_its_recovery(tmp_path):
    """DP-01 through the command line: a paid command in a workbench run whose own ledger is torn is refused at its
    opening (exit 2), the ledger named with its recovery, nothing written."""
    from typer.testing import CliRunner
    from adroit.orchestrator import cli
    out = tmp_path / "cli"
    out.mkdir()
    (out / "paid.jsonl").write_bytes(EXTENSIONS["a torn line"])
    before = _entries(out)
    command = ["lagrangian", "--derive", "--description", "SIMULATED model", "--checker", "none", "--budget", "1",
               "--out", str(out)]
    with _in_job(out, "cli-attempt"), patch.dict(os.environ, {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}):
        result = CliRunner().invoke(cli.app, command)
    said = re.sub(r"[\s│╭╮╰╯─]", "", result.output)       # the error's box and its wrapping removed
    assert result.exit_code == 2 and "istorn" in said and "adroitledgerrecover" in said, result.output
    assert _entries(out) == before


def test_a_run_opens_a_ledger_whose_whole_last_entry_has_no_newline(tmp_path):
    """What stays: a run's ledger from before, whose whole last entry lacks its newline, is opened, its ``opened``
    entry written after a newline, and read as it holds."""
    from adroit.orchestrator import preflight
    ledger = tmp_path / "paid.jsonl"
    ledger.write_bytes(b'{"id": "r0", "state": "reserved", "provider": "anthropic", "model": "SIMULATED", '
                       b'"reserved_usd": 0.1}\n{"id": "r0", "state": "settled", "cost_usd": 0.05}')
    with _in_job(tmp_path, "attempt-a"):
        preflight.open_job_ledger(ledger)
    assert ledger.read_bytes().endswith(b'0.05}\n{"state": "opened", "attempt": "attempt-a"}\n')
    assert _states(ledger) == {"settled": 0.05, "uncertain": 0}


# --- DP-02: recovery reads the journal as every reading does, before it writes anything ----------------------------

def _ahead(ledger: Path) -> None:
    """The auditor's case: the journal replaced by a different, identifiable torn reservation shorter than its mark."""
    ledger.write_bytes(b'{"id": "z", "state": "reserved", "provider": "anthropic", "model": "SIMULATED", '
                       b'"reserved_usd": 0.1, "invoc')


def _another(ledger: Path) -> None:
    """Another journal of greater length, whose torn tail is identifiable: it does not begin with what was marked."""
    ledger.write_bytes(ledger.read_bytes().replace(b"anthropic", b"Anthropic", 1)
                       + b'{"id": "y", "state": "reserved", "provider": "anthropic", "reserved_usd": 0.1, "mod')


def _cut(ledger: Path) -> None:
    """The journal cut short within what was marked, then a torn line after it."""
    ledger.write_bytes(ledger.read_bytes().splitlines(keepends=True)[0]
                       + b'{"id": "y", "state": "reserved", "provider": "anthropic", "reserved_usd": 0.1, "mod')


MISMATCHED = {"a shorter torn journal": _ahead, "another journal": _another, "cut short, then torn": _cut}


@pytest.mark.parametrize("mismatch", MISMATCHED)
def test_recovery_of_a_journal_its_mark_refuses_changes_nothing(tmp_path, mismatch):
    """DP-02, the auditor's case and its kin: a session's journal that does not begin with what its mark records, with an
    identifiable torn last line. Its recovery is refused, naming the mark, and nothing is changed: the journal, its mark
    and its folder (no side copy) as they were; the command line says so (exit 1), and says it again, the same way."""
    from typer.testing import CliRunner
    from adroit.agents.budget import recover_torn_tail
    from adroit.orchestrator.cli import app
    service, session, llm, _ = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    MISMATCHED[mismatch](ledger)
    before = _entries(ledger.parent)
    refused = _refused(lambda: recover_torn_tail(ledger))
    assert _entries(ledger.parent) == before, "recovery changed a journal its mark refuses"
    assert "as the mark beside it" in refused, refused
    said = [CliRunner().invoke(app, ["ledger", "recover", str(ledger)]) for _ in range(2)]
    assert [r.exit_code for r in said] == [1, 1] and said[0].output == said[1].output
    assert "Not recovered" in said[0].output and "mark beside it" in " ".join(said[0].output.split())
    assert _entries(ledger.parent) == before


def test_recovery_behind_its_mark_recovers_and_records_it(tmp_path):
    """What stays (DP-02): a torn line after what the mark records is recovered, the original kept beside it; the mark
    then records the recovered journal, which every reading reads."""
    from adroit.agents.budget import recover_torn_tail
    from adroit.core.durable import Held, marked
    service, session, llm, _ = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    with ledger.open("ab") as stream:
        stream.write(EXTENSIONS["a torn line"])
    recover_torn_tail(ledger)
    assert marked(ledger) == Held.of(ledger.read_bytes()) and list(ledger.parent.glob("paid.jsonl.torn-*"))
    assert _states(ledger) == {"settled": pytest.approx(SPENT), "uncertain": 0.02}


# --- the writers' inventory: each checks the whole ledger --------------------------------------------------------

def test_every_append_to_a_paid_ledger_checks_the_whole_ledger(tmp_path):
    """Each paid ledger's writer's ``append_held`` is given the whole journal's check (``whole=journal_whole``), or,
    the client's, its own (``BudgetedLLMClient._whole``: its account's for a session's ledger, which is that check and
    the session's cap raises' (DQ-03); else ``journal_whole``), and the account of a client whose write failed once
    begun reserves nothing more (DP-01)."""
    from adroit.agents.budget import journal_whole
    from tests.orchestrator.test_do_fixes import JOURNAL_WRITERS
    calls = []
    for module in JOURNAL_WRITERS:
        for node in ast.walk(ast.parse((ROOT / module).read_text())):
            if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("append_held"):
                calls.append((module, {k.arg: ast.unparse(k.value) for k in node.keywords}.get("whole")))
    assert len(calls) == 5 and all(whole == ("self._whole(path)" if module == "adroit/agents/llm.py" else
                                             "journal_whole") for module, whole in calls), calls
    service, session, llm, _ = _session(tmp_path)
    ledger = Path(os.path.abspath(service.folder(session) / "paid.jsonl"))
    assert llm._whole(ledger) is llm.account.whole is not None and llm._whole(tmp_path / "job.jsonl") is journal_whole
    for whole in (llm._whole(ledger), journal_whole):
        with pytest.raises(ValueError, match="torn"):
            whole(b'{"id": "r", "state": "reser', ledger)

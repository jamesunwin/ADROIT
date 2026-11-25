"""A paid journal's torn last line (the owner's direction D-7, 2026-10-25; the consolidation plan's M3): named, with
the recovery command, never read past; recovered only where the torn bytes identify their request, the original kept,
every reservation kept in full, nothing ever sent again. Every journal here is written directly as its writer leaves
it (``BudgetedLLMClient.request``): no provider, no request, $0."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adroit.agents import budget
from adroit.agents.budget import TornLedger, read_ledger, recover_torn_tail, settled_and_uncertain

RESERVED = {"id": "r1", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.4}
SETTLED_EARLIER = [{"id": "r0", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5",
                    "reserved_usd": 0.1}, {"id": "r0", "state": "settled", "cost_usd": 0.0024}]


def _journal(folder: Path, rows: list[dict], torn: str = "") -> Path:
    path = folder / "paid.jsonl"
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + torn)
    return path


def _cut(row: dict, keep: int) -> str:
    """The first ``keep`` characters of a journal line, as a crash mid-write leaves it (no newline)."""
    return json.dumps(row)[:keep]


def test_a_torn_last_line_is_named_with_its_recovery_command(tmp_path):
    path = _journal(tmp_path, SETTLED_EARLIER + [RESERVED], _cut({"id": "r1", "state": "settled", "cost_usd": 0.01}, 30))
    with pytest.raises(TornLedger, match=r"line 4 is torn .* `adroit ledger recover .*paid.jsonl`"):
        read_ledger(path)


@pytest.mark.parametrize("text", ['{"id": "r0", "state": "reser\n{"id": "r0", "state": "reserved"}\n',
                                  json.dumps(SETTLED_EARLIER[0]) + "\n" + '{"id": "r0", "sta\n'])
def test_a_line_that_is_not_json_elsewhere_is_damage_not_a_torn_tail(tmp_path, text):
    path = tmp_path / "paid.jsonl"
    path.write_text(text)
    with pytest.raises(ValueError) as error:
        read_ledger(path)
    assert not isinstance(error.value, TornLedger)
    with pytest.raises(ValueError, match="no torn line|whole"):
        recover_torn_tail(path)


@pytest.mark.parametrize("torn", [
    _cut({"id": "r1", "state": "settled", "cost_usd": 0.0123, "bound_exceeded": False}, 40),
    _cut({"id": "r1", "state": "billing_uncertain", "error": "TimeoutError"}, 35),
    _cut({"id": "r1", "state": "received", "response": {"content": [{"text": "x" * 50}]}}, 60),
], ids=["a settlement", "an uncertain bill", "an answer"])
def test_a_torn_entry_for_an_open_request_keeps_its_reservation_in_full(tmp_path, torn):
    """The torn settlement's cost is never guessed: the request is uncertain, its $0.40 reservation kept until its
    bill is known; the original bytes kept beside the journal; the earlier settled request unchanged."""
    path = _journal(tmp_path, SETTLED_EARLIER + [RESERVED], torn)
    original = path.read_bytes()
    said = recover_torn_tail(path)
    requests = read_ledger(path)
    assert requests["r1"].state == "uncertain" and requests["r1"].reserved_usd == 0.4
    assert settled_and_uncertain(requests) == (pytest.approx(0.0024), pytest.approx(0.4))
    side = [p for p in tmp_path.iterdir() if p.name.startswith("paid.jsonl.torn-")]
    assert len(side) == 1 and side[0].read_bytes() == original
    last = json.loads(path.read_text().splitlines()[-1])
    assert last["state"] == "recovered" and last["id"] == "r1" and last["side_copy"] == side[0].name
    assert "nothing was sent again" in said and "$0.4000 reservation kept in full" in said


def test_a_torn_reservation_whose_request_and_bound_are_legible_is_kept_uncertain(tmp_path):
    path = _journal(tmp_path, SETTLED_EARLIER, _cut(dict(RESERVED, invocation="x" * 40), 110))
    recover_torn_tail(path)
    request = read_ledger(path)["r1"]
    assert request.state == "uncertain" and request.reserved_usd == 0.4 and request.provider == "anthropic"


@pytest.mark.parametrize("rows, torn, why", [
    (SETTLED_EARLIER, _cut(RESERVED, 60), "before its provider or bound"),
    (SETTLED_EARLIER, '{"st', "names no request"),
    (SETTLED_EARLIER, _cut({"id": "r0", "state": "billing_uncertain"}, 30), "already settled"),
    (SETTLED_EARLIER, _cut({"id": "zz", "state": "settled", "cost_usd": 1}, 30), "never reserved"),
    (SETTLED_EARLIER, _cut({"state": "background_received", "response": {}}, 40), "0 requests open"),
    (SETTLED_EARLIER + [RESERVED, dict(RESERVED, id="r2")], _cut({"state": "background_received", "response": {}}, 40),
     "2 requests open"),
], ids=["a torn reservation's bound", "no request", "a settled request", "a request never reserved",
        "a background response, nothing open", "a background response, two open"])
def test_torn_bytes_that_do_not_identify_their_request_leave_the_budget_blocked(tmp_path, rows, torn, why):
    path = _journal(tmp_path, rows, torn)
    before = path.read_bytes()
    with pytest.raises(ValueError, match=why):
        recover_torn_tail(path)
    assert path.read_bytes() == before and not list(tmp_path.glob("paid.jsonl.torn-*"))
    with pytest.raises(TornLedger):
        read_ledger(path)


def test_a_background_response_while_one_request_is_open_is_that_requests(tmp_path):
    path = _journal(tmp_path, SETTLED_EARLIER + [RESERVED], _cut({"state": "background_received", "response": {}}, 40))
    recover_torn_tail(path)
    assert read_ledger(path)["r1"].state == "uncertain"


def test_a_whole_last_line_without_its_newline_is_not_recovered(tmp_path):
    path = _journal(tmp_path, SETTLED_EARLIER, json.dumps(RESERVED))
    assert read_ledger(path)["r1"].state == "open"
    with pytest.raises(ValueError, match="nothing to recover"):
        recover_torn_tail(path)


def test_the_rest_of_the_journal_must_read_as_its_writer_kept_it(tmp_path):
    path = _journal(tmp_path, [{"id": "q", "state": "settled", "cost_usd": 0.02}, RESERVED],
                    _cut({"id": "r1", "state": "settled", "cost_usd": 0.1}, 30))
    with pytest.raises(ValueError, match="never reserved"):
        recover_torn_tail(path)


def test_a_journal_in_use_or_a_running_job_is_not_recovered(tmp_path):
    from adroit.core.checkpoint import run_lock
    path = _journal(tmp_path, SETTLED_EARLIER + [RESERVED], _cut({"id": "r1", "state": "settled"}, 25))
    with run_lock(tmp_path):
        with pytest.raises(ValueError, match="a run is using this journal"):
            recover_torn_tail(path)
    (tmp_path / "job.json").write_text(json.dumps({"status": "running"}))
    with pytest.raises(ValueError, match="still going"):
        recover_torn_tail(path)


def test_the_command_says_what_it_did_or_why_not(tmp_path):
    from adroit.orchestrator.cli import app
    path = _journal(tmp_path, SETTLED_EARLIER + [RESERVED], _cut({"id": "r1", "state": "settled"}, 25))
    blocked = _journal(tmp_path / "blocked", SETTLED_EARLIER, '{"st')
    done = CliRunner().invoke(app, ["ledger", "recover", str(path)])
    assert done.exit_code == 0 and "request r1 is uncertain" in done.output
    refused = CliRunner().invoke(app, ["ledger", "recover", str(blocked)])
    assert refused.exit_code == 1 and "Not recovered" in refused.output


def test_a_sessions_torn_journal_blocks_its_budget_until_recovered(tmp_path):
    """The session's account and the run page read the torn journal as blocked, naming the command; after the
    recovery the session's spendable account keeps the torn request's reservation."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service = Intake(Catalog(tmp_path / "models"))
    s = service.start(budget=1)
    path = _journal(service.folder(s.session_id), SETTLED_EARLIER + [RESERVED],
                    _cut({"id": "r1", "state": "settled", "cost_usd": 0.01}, 30))
    with pytest.raises(TornLedger, match="adroit ledger recover"):
        service.budget_status(s.session_id)
    recover_torn_tail(path)
    status = service.budget_status(s.session_id)
    assert status["spent"] == pytest.approx(0.0024) and status["reserved_uncertain"] == pytest.approx(0.4)
    assert status["remaining"] == pytest.approx(1 - 0.4024)


def test_the_writer_syncs_each_line(tmp_path, monkeypatch):
    """Each journal line is flushed and synced before the request goes on (M3)."""
    synced = []
    monkeypatch.setattr("os.fsync", lambda fd: synced.append(fd))
    from adroit.agents.llm import BudgetedLLMClient, FakeLLMClient
    client = BudgetedLLMClient(FakeLLMClient(), dollar_budget=1, ledger_path=tmp_path / "paid.jsonl")
    client._journal({"id": "x", "state": "reserved", "provider": "anthropic", "reserved_usd": 0.1})
    assert synced and budget.read_ledger(tmp_path / "paid.jsonl")["x"].state == "open"

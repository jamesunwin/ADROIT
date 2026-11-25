"""The auditor's consolidation audit, CO-05 (2026-10-25): a session whose paid ledger was lost had read as one that never
spent, its approved cap restored in full, so that a request beyond it was sent (its control: $0.08 sent under a
$0.05 approval). A session that shows it had a ledger now refuses, before anything is reserved, until the original
is restored; a session that never had one still works. The provider is a scripted SDK; no request leaves the
machine, $0."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from adroit.agents.budget import BudgetExceeded, MissingJournal, recover_torn_tail
from adroit.library.personal import Catalog
from adroit.orchestrator.model_intake import Intake, RunRequests, Session, session_identity
from tests.agents.test_budget_reservations import ask, client


def _bill(**kwargs):
    """A response of 9,900 input and 20 output tokens: about $0.04 under the scripted price."""
    return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"value":4}')],
                           usage=SimpleNamespace(input_tokens=9900, output_tokens=20))


def _fail(**kwargs):
    raise TimeoutError("simulated transport error after dispatch")


def _session(tmp_path, *, uncertain: bool = False):
    """A $0.05 session that has sent one request: settled at about $0.04, or (``uncertain``) with its bill unknown."""
    service = Intake(Catalog(tmp_path / "models"))
    s = service.start(0.05)
    llm, calls = client(tmp_path, account=service.account(s), send=_fail if uncertain else _bill)
    llm.ledger_path = service.folder(s.session_id) / "paid.jsonl"
    if uncertain:
        with pytest.raises(TimeoutError):
            ask(llm)
    else:
        ask(llm)
    return service, s, llm.ledger_path


@pytest.mark.parametrize("uncertain", [False, True], ids=["after a settled request", "after an uncertain request"])
def test_a_lost_journal_blocks_the_session_before_anything_is_reserved(tmp_path, uncertain):
    service, s, ledger = _session(tmp_path, uncertain=uncertain)
    before = service.budget_status(s.session_id)
    assert before["spent"] + before["reserved_uncertain"] > 0.03
    saved = ledger.with_suffix(".saved")
    ledger.rename(saved)
    for read in (lambda: service.budget_status(s.session_id), lambda: service.requests(s.session_id),
                 lambda: service.account(service.session(s.session_id))):
        with pytest.raises(MissingJournal, match="is missing, although the session was opened with a paid ledger"):
            read()
    sent = []
    with pytest.raises(MissingJournal):           # the spending path: refused before a client exists
        client(tmp_path, account=service.account(service.session(s.session_id)), send=lambda **k: sent.append(k))
    assert not sent and not ledger.exists()       # nothing sent, and no new or empty ledger made in its place
    with pytest.raises(MissingJournal):
        service.raise_cap(s.session_id, 1.0, confirmed=True)
    assert service.session(s.session_id).budget == 0.05 and not ledger.exists()
    saved.rename(ledger)                          # the original restored: the session goes on as it was
    assert service.budget_status(s.session_id) == before
    again, calls = client(tmp_path, account=service.account(service.session(s.session_id)), send=_bill)
    again.ledger_path = ledger
    with pytest.raises(BudgetExceeded):           # the cap still holds what was spent
        ask(again)
    assert not calls


def test_a_session_through_its_real_step_refuses_with_the_journal_lost(tmp_path, monkeypatch):
    """The intake's own paid step (``Intake.step``): refused before its language model is made."""
    import adroit.agents.llm as llm_module
    service, s, ledger = _session(tmp_path)
    ledger.unlink()
    made = []
    monkeypatch.setattr(llm_module, "LLMClient", lambda *a, **k: made.append(k))
    with pytest.raises(MissingJournal):
        service.step(s.session_id, "tex", r"\mathcal{L} = \bar\chi i\gamma^\mu\partial_\mu\chi")
    assert not made and not ledger.exists()


def test_a_session_that_never_had_a_ledger_still_works_and_makes_one(tmp_path):
    """A paid session from before 2026-10-25, never used: no ledger and no sign of one. Its first paid account makes
    its empty ledger and records that it has one, so that its loss is known from then on."""
    service = Intake(Catalog(tmp_path / "models"))
    s = Session(session_id="a" * 32, budget=0.05)
    s.integrity_sha256 = session_identity(s)
    folder = service.folder(s.session_id)
    folder.mkdir(parents=True)
    (folder / "session.json").write_text(s.model_dump_json())
    assert "journal" not in json.loads((folder / "session.json").read_text())        # the older record, unchanged
    assert service.budget_status(s.session_id)["remaining"] == 0.05                     # read-only: nothing written
    assert not (folder / "paid.jsonl").exists()
    llm, calls = client(tmp_path, account=service.account(service.session(s.session_id)), send=_bill)
    llm.ledger_path = folder / "paid.jsonl"
    ask(llm)
    assert len(calls) == 1 and service.session(s.session_id).journal
    (folder / "paid.jsonl").unlink()
    with pytest.raises(MissingJournal):
        service.budget_status(s.session_id)


@pytest.mark.parametrize("evidence", ["a raised cap", "an interpreted step", "a run's request record"])
def test_an_older_session_with_signs_of_spending_and_no_ledger_is_blocked(tmp_path, monkeypatch, evidence):
    from adroit.core.config import get_settings
    service = Intake(Catalog(tmp_path / "models"))
    s = Session(session_id="b" * 32, budget=0.05)
    folder = service.folder(s.session_id)
    folder.mkdir(parents=True)
    runs = tmp_path / "runs"
    monkeypatch.setattr(get_settings(), "runs_dir", runs)
    if evidence == "a raised cap":
        from adroit.orchestrator.model_intake import CapChange
        s.cap_history = [CapChange(previous=0.01, new=0.05, at="2026-10-01T00:00:00+00:00")]
    elif evidence == "an interpreted step":
        (folder / "steps").mkdir()
        (folder / "steps" / ("c" * 64 + ".json")).write_text(json.dumps({"kind": "idea"}))
    else:
        (runs / "run").mkdir(parents=True)
        (runs / "run" / "paid_requests.json").write_text(
            RunRequests(session_id=s.session_id, request_ids=["r1"]).model_dump_json())
    s.integrity_sha256 = session_identity(s)
    (folder / "session.json").write_text(s.model_dump_json())
    with pytest.raises(MissingJournal):
        service.account(service.session(s.session_id))
    assert not (folder / "paid.jsonl").exists()


def test_recovery_never_makes_a_ledger_that_was_lost(tmp_path):
    missing = tmp_path / "session" / "paid.jsonl"
    with pytest.raises(ValueError, match="no journal here to recover"):
        recover_torn_tail(missing)
    assert not missing.exists()


def test_the_run_page_says_the_session_money_is_not_available(tmp_path, monkeypatch):
    """The accounting surfaces read the refusal as damage: not available, with the reason, never $0."""
    from adroit.core.config import get_settings
    from adroit.orchestrator import accounting
    monkeypatch.setattr(get_settings(), "model_library_dir", tmp_path / "models")
    service, s, ledger = _session(tmp_path)
    run = tmp_path / "run"
    run.mkdir()
    (run / "paid_requests.json").write_text(RunRequests(session_id=s.session_id, request_ids=[]).model_dump_json())
    job = accounting.JobFacts(command=["models", "step", s.session_id, "--kind", "idea"], folder=str(run))
    assert accounting.cost(run, job).session_spent_usd is not None
    ledger.unlink()
    c = accounting.cost(run, job)
    assert c.run_usd is None and c.damaged and "is missing" in c.damaged[0]
    assert accounting.run_line(c).startswith("This run: not available")
    assert accounting.cost_lines(c)[1] == "Session total: not available"

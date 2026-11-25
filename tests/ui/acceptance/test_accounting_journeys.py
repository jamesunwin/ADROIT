"""The permanent acceptance gate's journey 5 (the consolidation plan's M4, written with M2): constraint discovery →
a linked extraction sharing its budget → the review session, where the auditor's consistency audit found the session page
reading another session's budget (CA-04). Every page that shows the money shows the same facts, from one journal.

Substituted (``SUBSTITUTED``): the provider's answers are a scripted Anthropic response behind the real budgeted
client and journal writer (``tests/agents/test_budget_reservations.client``), the transport failure a raised
``TimeoutError`` after dispatch; the survey's literature search is not run (its session is started, not surveyed);
the workbench runs are written as their jobs leave them. No request leaves the machine; $0.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from nicegui.testing import User

from adroit.orchestrator import accounting
from adroit.ui import engine

SUBSTITUTED = {"provider responses": "a scripted Anthropic message (100 input, 20 output tokens) per request",
               "transport failure": "TimeoutError raised by the SDK call after the reservation is journalled",
               "the survey's search": "not run: the discovery session is started and charged one request directly",
               "workbench runs": "job records written as the runner leaves them, not launched"}


def _job(folder: Path, command: list[str]) -> engine.Job:
    folder.mkdir(parents=True)
    job = engine.Job(title=folder.name, kind=command[0], folder=str(folder), command=command, status="completed",
                     returncode=0)
    engine.save(job)
    return job


async def test_journey_5_discovery_extraction_and_session_read_one_journal_alike(user: User, tmp_path, monkeypatch):
    from adroit.core.config import get_settings
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator import constraint_discovery as cd
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    from adroit.orchestrator.model_intake import REQUESTS, RunRequests
    from adroit.ui.app import build_pages
    from tests.agents.test_budget_reservations import ask, client
    from tests.orchestrator.test_constraint_discovery import Web, _abstracts, _model, _resolver
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path / "data")
    discovery = cd.Discovery(abstracts=_abstracts, fetch=Web(), resolver=_resolver)
    path, _ = _model(tmp_path)
    owner = discovery.start(str(path), cd.Options(budget=1.0)).session_id
    budgets = discovery.budgets
    ledger = budgets.folder(owner) / "paid.jsonl"
    account = budgets.account(budgets.session(owner))
    survey_llm, _ = client(tmp_path / "survey_client", account=account)
    survey_llm.ledger_path = ledger
    ask(survey_llm)                                                     # the survey's request: settled
    survey_cost = budgets.budget_status(owner)["spent"]
    catalog = ExperimentalCatalog()
    source = tmp_path / "source.txt"
    source.write_text("A synthetic experimental source. Exposure 1 kg day.")
    revision = catalog.import_files([source], "a source")
    extraction = ExperimentalExtraction(catalog)
    child = extraction.start(revision.reference, 0, vision=False, budget_session=owner).session_id
    assert extraction.budget_owner(child) == owner
    extract_llm, _ = client(tmp_path / "extract_client", account=account)
    extract_llm.ledger_path = ledger
    ask(extract_llm)                                                    # the extraction's first request: settled

    def fail(**kwargs):
        raise TimeoutError("simulated transport error after dispatch")
    extract_llm._inner._client.messages.create = fail
    with pytest.raises(TimeoutError):
        ask(extract_llm)                                                # its second: the bill is not known
    states = [json.loads(line)["state"] for line in ledger.read_text().splitlines()]
    assert states.count("settled") == 2 and states[-1] == "billing_uncertain"

    root = build_pages(tmp_path / "runs")
    survey_job = _job(root / "survey", ["constraints", "discover", "catalog:m@r", "--budget", "1", "--out", "."])
    (root / "survey" / "discovery.json").write_text(json.dumps({"session": owner}))
    ours = [e["id"] for e in survey_llm.ledger if e.get("state") == "reserved"]
    (root / "survey" / REQUESTS).write_text(RunRequests(session_id=owner, request_ids=ours).model_dump_json())
    extract_job = _job(root / "extract", ["experiments", "extract", child, "--batch", "0", "--budget", "1", "--out", "."])
    mine = [e["id"] for e in extract_llm.ledger if e.get("state") == "reserved"]
    (root / "extract" / REQUESTS).write_text(RunRequests(session_id=owner, request_ids=mine).model_dump_json())

    status = budgets.budget_status(owner)
    words = accounting.status_text(status)
    survey, extract = accounting.cost(root / "survey", survey_job), accounting.cost(root / "extract", extract_job)
    assert survey.scope == "session" and survey.run_usd == pytest.approx(status["spent"])
    assert survey.run_uncertain_usd == pytest.approx(status["reserved_uncertain"]) and survey.run_uncertain_usd > 0
    assert survey.own_usd == pytest.approx(survey_cost) and not survey.own_uncertain_usd    # the survey's own (G5)
    assert extract.run_usd == pytest.approx(status["spent"] / 2) and extract.run_uncertain_usd == survey.run_uncertain_usd
    together = accounting.total([survey, extract])                      # the shared requests once (D-6)
    assert (together.settled_usd, together.reserved_usd, together.requests) == (
        pytest.approx(status["spent"]), pytest.approx(status["reserved_uncertain"]), 3)

    await user.open(f"/experiments/session?session={child}")
    await user.should_see(words)
    await user.should_see(f"the budget of discovery session {owner[:8]}")
    await user.open("/live?path=extract")
    await user.should_see(accounting.run_line(extract))
    await user.should_see("Session total so far: " + words)
    await user.open("/live?path=survey")
    await user.should_see(accounting.run_line(survey))
    await user.should_see(f"this run's own requests: {accounting.usd(survey_cost)}")
    await user.open(f"/constraints/discovery?session={owner}")
    await user.should_see("Session spending: " + words)


async def test_journey_5_with_a_damaged_journal_every_page_says_not_available(user: User, tmp_path, monkeypatch):
    """The uncertain-money variant: the shared journal damaged (an orphan background response). The session page,
    the extraction's run page and the discovery page all say the money is not available; none says $0."""
    from adroit.core.config import get_settings
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator import constraint_discovery as cd
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    from adroit.ui.app import build_pages
    from tests.orchestrator.test_constraint_discovery import Web, _abstracts, _model, _resolver
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path / "data")
    discovery = cd.Discovery(abstracts=_abstracts, fetch=Web(), resolver=_resolver)
    path, _ = _model(tmp_path)
    owner = discovery.start(str(path), cd.Options(budget=1.0)).session_id
    (discovery.budgets.folder(owner) / "paid.jsonl").write_text(
        json.dumps({"state": "background_received", "response": {}}) + "\n")
    catalog = ExperimentalCatalog()
    source = tmp_path / "source.txt"
    source.write_text("A synthetic source.")
    revision = catalog.import_files([source], "a source")
    child = ExperimentalExtraction(catalog).start(revision.reference, 0, vision=False, budget_session=owner).session_id
    root = build_pages(tmp_path / "runs")
    _job(root / "extract", ["experiments", "extract", child, "--batch", "0", "--budget", "1", "--out", "."])
    await user.open(f"/experiments/session?session={child}")
    await user.should_see("spending not available")
    await user.open("/live?path=extract")
    await user.should_see("Session total: not available")
    await user.open(f"/constraints/discovery?session={owner}")
    await user.should_see("Session spending: spending not available")

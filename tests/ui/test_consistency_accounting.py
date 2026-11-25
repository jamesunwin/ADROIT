"""The consistency audit of 2026-10-24 (the independent audit of 2026-10-24 (consistency)): CA-04 to CA-06, money read one way on
every surface. Each run, session and journal here is written directly as its writer leaves it (the journal's states
and order are ``BudgetedLLMClient.request``'s): no provider, request or calculation, $0.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from nicegui.testing import User

from adroit.orchestrator import accounting, model_intake
from adroit.ui import engine, outcomes
from tests.ui.test_combined_audit_v1 import _legacy, _run

SETTLED = [{"id": "r1", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.1},
           {"id": "r1", "state": "received", "response": {}},
           {"id": "r1", "state": "settled", "cost_usd": 0.0008, "bound_exceeded": False}]
UNCERTAIN = [{"id": "r2", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5",
              "reserved_usd": 0.040952},
             {"id": "r2", "state": "billing_uncertain", "error": "TimeoutError"}]
SESSION_TEXT = "$0.0008 spent of its approved $1.00 cap ($0.9582 left); $0.0410 reserved whose bill is not yet known"


def _journal(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


# --- CA-05: every fact an old record gives is kept ----------------------------------------------------------------

CENT_RESERVED = "spent $0.12; up to $0.4000 reserved whose bill is not yet known\n"
STOP = {"status": "budget_stopped", "committed_usd": 0.4024}
EDGES = {
    # records: (words the detail line must hold, words the list's line must hold)
    "a line to the cent with a reservation": ({"log": CENT_RESERVED},
                                              ["about $0.1200", "up to $0.4000 reserved"], ["+ up to $0.4000 reserved"]),
    "the same beside a study record of $0": ({"log": CENT_RESERVED, "study": _legacy(cost_usd=0.0)},
                                             ["about $0.1200", "up to $0.4000 reserved"], ["+ up to $0.4000 reserved"]),
    "the same beside a study's settled subtotal": (
        {"log": CENT_RESERVED, "study": _legacy(cost_usd=0.0024)},
        ["$0.0024 settled", "up to $0.4000 reserved", "its log says about $0.1200"],
        ["+ up to $0.4000 reserved", "records incomplete"]),
    "a split that does not add up": ({"stop": {**STOP, "settled_usd": 0.0024, "uncertain_usd": 0.0}},
                                     ["up to $0.4024 committed", "does not add up"],
                                     ["up to $0.4024 committed", "records incomplete"]),
    "a split that is not a number, and a precise line": (
        {"stop": {**STOP, "settled_usd": 0.0024, "uncertain_usd": float("nan")}, "log": "spent $0.0024\n"},
        ["$0.0024 settled", "up to $0.4024 committed in all", "cannot be read"],
        ["(up to $0.4024 committed)", "records incomplete"]),
    "a negative split, and a precise line": (
        {"stop": {**STOP, "settled_usd": 0.0024, "uncertain_usd": -0.4}, "log": "spent $0.0024\n"},
        ["up to $0.4024 committed in all", "cannot be read"], ["(up to $0.4024 committed)"]),
    "an unsplit stop beside a precise line": ({"stop": STOP, "log": "spent $0.0024\n"},
                                              ["$0.0024 settled", "up to $0.4024 committed in all"],
                                              ["(up to $0.4024 committed)"]),
    "a zero line to the cent with a reservation": (
        {"log": "spent $0.00; up to $0.4000 reserved whose bill is not yet known\n"},
        ["settled dollars not available", "up to $0.4000 reserved"], ["settled not available + up to $0.4000"]),
}


@pytest.mark.parametrize("case", EDGES)
def test_an_old_records_reservation_and_committed_bound_survive_beside_any_other_figure(tmp_path, case):
    """CA-05: the first record that looked usable decided, so a reservation on a line to the cent, a stop's
    committed bound beside a precise line, and a split that did not add up or could not be read all disappeared
    (the detail said "$0.0024" or "about $0.1200" alone). Every fact is now kept, and damage or disagreement named."""
    records, detail, listed = EDGES[case]
    job = _run(tmp_path / "run", **records)
    c = outcomes.cost(tmp_path / "run", job)
    line, short = outcomes.run_line(c), outcomes.short_line(c)
    assert all(words in line for words in detail), line
    assert all(words in short for words in listed), short
    assert "no paid request was sent" not in line


# --- CA-06: one journal, one reading ------------------------------------------------------------------------------

@pytest.fixture
def intake(tmp_path, monkeypatch):
    """A paid model-intake session in a scratch catalog, and a run of it (its job and folder)."""
    from adroit.library.personal import Catalog
    service = model_intake.Intake(Catalog(tmp_path / "models"))
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    s = service.start(budget=1)
    folder = tmp_path / "runs" / "step"
    folder.mkdir(parents=True)
    job = engine.Job(title="step", kind="models", folder=str(folder), status="completed", returncode=0,
                     command=["models", "step", s.session_id, "--kind", "idea"])
    engine.save(job)
    return service, s.session_id, folder, job


def _receipt(folder: Path, session: str, ids: list[str]) -> None:
    (folder / model_intake.REQUESTS).write_text(model_intake.RunRequests(session_id=session, request_ids=ids)
                                                .model_dump_json())


def test_a_request_named_twice_is_not_counted_twice(intake):
    """CA-06: a receipt naming r1 twice doubled the run's cost ($0.048 for one $0.024 request)."""
    service, session, folder, job = intake
    _journal(service.folder(session) / "paid.jsonl", SETTLED)
    _receipt(folder, session, ["r1", "r1"])
    line = outcomes.run_line(outcomes.cost(folder, job))
    assert line.startswith("This run: not available") and "more than once" in line and "$0.0016" not in line
    _receipt(folder, session, ["r1"])
    assert outcomes.run_line(outcomes.cost(folder, job)) == "This run: $0.0008"


@pytest.mark.parametrize("rows", [
    [{"state": "background_received", "response": {"usage": {"input_tokens": 100, "output_tokens": 50}}}],
    SETTLED + [{"state": "background_received", "response": {}}]], ids=["alone", "after its request settled"])
def test_a_background_response_with_no_request_open_is_damage_not_nothing_sent(intake, rows):
    """CA-06: a journal holding only a background response read "This run: $0 (no paid request was sent)"; the
    response shows a request was made. The writer journals one only while its request is open."""
    service, session, folder, job = intake
    _journal(service.folder(session) / "paid.jsonl", rows)
    _receipt(folder, session, [])
    lines = outcomes.cost_lines(outcomes.cost(folder, job))
    assert lines[0].startswith("This run: not available") and "background response with no request open" in lines[0]
    assert lines[1] == "Session total: not available"
    with pytest.raises(ValueError, match="background response"):
        service.budget_status(session)


def test_a_background_response_while_its_request_is_open_reads(intake):
    """The writer's own order (reserved, then the responses kept while polling, then the answer) still reads."""
    service, session, folder, job = intake
    _journal(service.folder(session) / "paid.jsonl",
             SETTLED[:1] + [{"state": "background_received", "response": {}}] + SETTLED[1:])
    _receipt(folder, session, ["r1"])
    assert outcomes.run_line(outcomes.cost(folder, job)) == "This run: $0.0008"
    assert service.budget_status(session)["spent"] == pytest.approx(0.0008)


def test_the_session_account_and_the_run_page_read_one_journal_alike(intake):
    """CA-06: reserved, settled, then billing_uncertain for the same request: the run page called the ledger
    unreadable while the session's own account (``Intake.budget_status``, which also restores the spendable budget)
    read $0.024 spent and $0.976 left. Both now read it through ``read_ledger``."""
    service, session, folder, job = intake
    _journal(service.folder(session) / "paid.jsonl", SETTLED + [{"id": "r1", "state": "billing_uncertain"}])
    _receipt(folder, session, ["r1"])
    assert "already settled" in outcomes.run_line(outcomes.cost(folder, job))
    with pytest.raises(ValueError, match="already settled"):
        service.budget_status(session)
    with pytest.raises(ValueError):
        service.account(service.session(session))


def test_the_session_account_keeps_frozen_provider_caps_in_settlement_order(intake):
    """``Intake.account`` on ``read_ledger``: a settlement above its bound freezes its provider at the dollars
    settled by then, as the in-process account does (``BudgetAccount.settle``)."""
    service, session, folder, job = intake
    a = dict(SETTLED[0], id="a", reserved_usd=0.01)
    b = dict(SETTLED[0], id="b", reserved_usd=0.01)
    _journal(service.folder(session) / "paid.jsonl", [
        a, b, {"id": "b", "state": "settled", "cost_usd": 0.005, "bound_exceeded": False},
        {"id": "a", "state": "settled", "cost_usd": 0.02, "bound_exceeded": True}])
    account = service.account(service.session(session))
    assert account.spent == {"anthropic": pytest.approx(0.025)}
    assert account.provider_caps == {"anthropic": pytest.approx(0.025)} and not account.reservations


# --- CA-04: the experimental session, through its budget owner -----------------------------------------------------

def _extraction(tmp_path: Path, linked: bool):
    """An experimental source and its interpretation session (with its own $1 budget, or sharing a $1 discovery
    session's), the journal of one settled request and one whose bill is uncertain in the budget's ledger."""
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    catalog = ExperimentalCatalog()
    source = tmp_path / "source.txt"
    source.write_text("A synthetic experimental source. Exposure 1 kg day.")
    revision = catalog.import_files([source], "a source")
    service = ExperimentalExtraction(catalog)
    parent = service.budgets.start(1) if linked else None
    scope = service.start(revision.reference, 0 if linked else 1, vision=False,
                          budget_session=parent.session_id if parent else "")
    owner = service.budget_owner(scope.session_id)
    assert (owner != scope.session_id) is linked
    _journal(service.budgets.folder(owner) / "paid.jsonl", SETTLED + UNCERTAIN)
    return service, scope.session_id, owner


@pytest.mark.parametrize("linked", [False, True], ids=["its own budget", "a discovery session's budget"])
async def test_the_experimental_session_shows_its_budget_owners_money_as_the_run_page_does(user: User, tmp_path,
                                                                                           linked):
    """CA-04: the session page said "$0.00 of $1.00 spent · $1.00 left" for $0.0008 settled and $0.0410 reserved
    (rounded to cents, the reservation dropped); sharing a discovery session's budget, it read its own empty one,
    "$0.00 of $0.00 spent · $0.00 left", and its cap control and its batch's launch used that $0 cap."""
    from adroit.ui.app import build_pages
    service, session, owner = _extraction(tmp_path, linked)
    assert outcomes.session_money(service.budgets, owner) == SESSION_TEXT
    build_pages(tmp_path / "runs")
    await user.open(f"/experiments/session?session={session}")
    await user.should_see(SESSION_TEXT)
    if linked:
        await user.should_see(f"the budget of discovery session {owner[:8]}")
    cap = user.find(kind=__import__("nicegui").ui.number).elements.pop()
    assert cap.value == pytest.approx(1.0)                         # the owner's cap, not the shared session's $0

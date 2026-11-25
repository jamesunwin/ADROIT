"""The record check on a result's review (the owner, 2026-11-18, the post-review changes item 2): a person's
review is recommended first; a model's check is a paid choice with its own consent, asked even with the auto-approve
setting on; a check that comes back shows each mismatch and the two ways on. No paid call: the launcher is replaced."""
from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.agents.llm import FakeLLMClient
from adroit.core import workbench_settings
from adroit.core.config import get_settings
from adroit.orchestrator.record_check import RecordChecker
from adroit.ui import engine
from adroit.ui.app import build_pages
from adroit.ui.record_check import AI_RISK, CONSENT, PERSON_FIRST
from tests.orchestrator.test_record_check import checker, verdict
from tests.private_limit_fixtures import fixture


def capture(monkeypatch) -> list[dict]:
    calls = []

    def launch(command, folder, title, **kwargs):
        calls.append({"command": command, **kwargs})
        folder.mkdir(parents=True, exist_ok=True)
        engine.save(engine.Job(folder=str(folder), command=command, title=title, kind=command[0], status="completed",
                               returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine, "launch", launch)
    return calls


def _record(tmp_path, monkeypatch):
    catalog, r = fixture(tmp_path)
    monkeypatch.setattr(get_settings(), "experimental_library_dir", catalog.root)
    return catalog, r


async def test_a_person_s_review_is_recommended_and_a_model_s_check_needs_its_own_consent(user: User, tmp_path,
                                                                                          monkeypatch):
    calls = capture(monkeypatch)
    catalog, r = _record(tmp_path, monkeypatch)
    workbench_settings.set_auto_approve(True)                 # the spend is ticked; the choice is still asked
    build_pages(tmp_path / "runs")
    await user.open("/experiments/view?" + urlencode({"reference": r.reference}))
    await user.should_see(PERSON_FIRST)
    await user.should_see(AI_RISK)
    assert next(iter(user.find(marker="model_check_consent").elements)).value is False
    user.find(marker="start_model_check").click()
    assert calls == []                                        # not without the consent
    user.find(CONSENT).click()
    user.find(marker="start_model_check").click()
    await user.should_see("Run:")
    [call] = calls
    assert call["command"][:2] == ["experiments", "check"] and call["approval"] == "auto"
    run = RecordChecker(catalog).request(call["command"][2])
    assert (run.revision, run.result_id, run.model, run.retries) == (r.reference, "limit", "claude-fable-5-1", 2)


async def test_the_page_warns_when_the_drafting_model_would_check_its_own_draft(user: User, tmp_path, monkeypatch):
    capture(monkeypatch)
    catalog, r = _record(tmp_path, monkeypatch)
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    drafting = ExperimentalExtraction(catalog).budgets.start(1.0, "gpt-5.6-sol")
    revision = catalog.load(r.reference)
    r2 = catalog.save(revision.dossier, revision.sources, revision.ingestions, r.reference,
                      provenance={"extraction_session": drafting.session_id})
    build_pages(tmp_path / "runs")
    await user.open("/experiments/view?" + urlencode({"reference": r2.reference}))
    await user.should_not_see("GPT-5.6 Sol drafted this record")
    from nicegui import ui
    select = next(e for e in user.find(kind=ui.select).elements if e.props.get("label") == "the checking model")
    select.value = "gpt-5.6-sol"
    await user.should_see("GPT-5.6 Sol drafted this record: its check is not a second model's reading.")


async def test_no_agreement_shows_each_mismatch_and_a_suggestion_starts_a_new_check(user: User, tmp_path,
                                                                                    monkeypatch):
    calls = capture(monkeypatch)
    catalog, r = _record(tmp_path, monkeypatch)
    service = checker(catalog)
    run = service.start(r.reference, "limit", 1.0, retries=0)
    outcome = service.run(run.session_id, llm_for=lambda model: FakeLLMClient([verdict(False)]))
    assert outcome.status == "needs_you"
    build_pages(tmp_path / "runs")
    await user.open("/experiments/view?" + urlencode({"reference": r.reference}))
    await user.should_see("back to you: no agreement")
    await user.should_see("mismatch: the background count: the record says 0.4 events")
    await user.should_see("Approve the record yourself with the review form above")
    user.find(marker="suggestion").type("read the alternative background estimate on line 3")
    for box in [b for b in user.find("I approve this spend").elements if not b.value]:   # the suggestion's gate too
        box.value = True
    user.find(marker="apply_suggestion").click()
    await user.should_see("Run:")
    again = RecordChecker(catalog).request(calls[-1]["command"][2])
    assert again.instruction == "read the alternative background estimate on line 3" and again.retries == 0

"""The home page's auto-approve setting (the owner, 2026-11-18, the post-review changes item 1): kept between
restarts, it ticks each spend box while the page's models are the defaults, says so, and the run records that the
setting approved it. Money only: the cap is still the box's amount, and nothing else is ticked. No paid call."""
import os
from types import SimpleNamespace
from urllib.parse import urlencode

from nicegui import ui
from nicegui.testing import User

from adroit.core import workbench_settings
from adroit.ui import engine
from adroit.ui.app import build_pages
from adroit.ui.pages import AUTO_APPROVE, AUTO_TICKED
from tests.ui.test_model_library import stored


def capture(monkeypatch) -> list[dict]:
    """The launcher replaced: each launch's command and keywords, a completed job written in its folder."""
    calls = []

    def launch(command, folder, title, **kwargs):
        calls.append({"command": command, **kwargs})
        folder.mkdir(parents=True, exist_ok=True)
        engine.save(engine.Job(folder=str(folder), command=command, title=title, kind=command[0], status="completed",
                               returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine, "launch", launch)
    return calls


def _select(user: User, label: str):
    return next(e for e in user.find(kind=ui.select).elements if e.props.get("label") == label)


def _tick(user: User, text: str = "I approve this spend"):
    return next(iter(user.find(text).elements))


def test_the_setting_is_off_unless_saved_and_a_damaged_file_approves_nothing():
    assert workbench_settings.auto_approve() is False
    workbench_settings.set_auto_approve(True)
    assert workbench_settings.auto_approve() is True and workbench_settings.settings_file().exists()
    workbench_settings.settings_file().write_text("{not json")
    assert workbench_settings.auto_approve() is False
    workbench_settings.settings_file().write_text('{"auto_approve_default_models": true, "unknown": 1}')
    assert workbench_settings.auto_approve() is False                  # a file it cannot read whole approves nothing


async def test_the_home_page_switch_keeps_the_choice(user: User, tmp_path):
    build_pages(tmp_path / "runs")
    await user.open("/")
    await user.should_see(AUTO_APPROVE)
    user.find(marker="auto_approve").click()
    assert workbench_settings.auto_approve() is True
    await user.open("/")
    assert next(iter(user.find(marker="auto_approve").elements)).value is True
    user.find(marker="auto_approve").click()
    assert workbench_settings.auto_approve() is False


async def test_with_the_setting_on_the_default_model_s_spend_box_starts_ticked_and_the_job_says_so(user: User,
                                                                                                    tmp_path,
                                                                                                    monkeypatch):
    calls = capture(monkeypatch)
    workbench_settings.set_auto_approve(True)
    r = stored()
    build_pages(tmp_path / "runs")
    await user.open("/models/view?" + urlencode({"reference": r.reference}))
    assert _tick(user).value is True
    await user.should_see(AUTO_TICKED)
    user.find(marker="discover").click()
    await user.should_see("Run:")
    assert calls[0]["command"][:2] == ["constraints", "discover"] and calls[0]["approval"] == "auto"
    assert calls[0]["confirmed_budget"] == 1.0                          # the box's amount is still the cap


async def test_another_model_unticks_it_and_a_person_s_click_is_theirs(user: User, tmp_path, monkeypatch):
    calls = capture(monkeypatch)
    workbench_settings.set_auto_approve(True)
    r = stored()
    build_pages(tmp_path / "runs")
    await user.open("/models/view?" + urlencode({"reference": r.reference}))
    model = _select(user, "language model (paid)")
    model.value = "gpt-5.6-sol"
    assert _tick(user).value is False
    user.find(marker="discover").click()
    assert calls == []                                                  # not approved: nothing starts
    model.value = "claude-opus-5-5"
    assert _tick(user).value is True
    user.find("I approve this spend").click()                           # the person unticks it: theirs from now on
    model.value = "gpt-5.6-sol"
    model.value = "claude-opus-5-5"
    assert _tick(user).value is False
    user.find("I approve this spend").click()
    user.find(marker="discover").click()
    await user.should_see("Run:")
    assert calls[0]["approval"] == "click"


async def test_with_the_setting_off_nothing_is_ticked(user: User, tmp_path, monkeypatch):
    capture(monkeypatch)
    r = stored()
    build_pages(tmp_path / "runs")
    await user.open("/models/view?" + urlencode({"reference": r.reference}))
    assert _tick(user).value is False
    await user.should_not_see(AUTO_TICKED)


async def test_a_derivation_is_ticked_only_with_both_default_models(user: User, tmp_path, monkeypatch):
    capture(monkeypatch)
    workbench_settings.set_auto_approve(True)
    build_pages(tmp_path / "runs")
    await user.open("/new/track1")
    boxes = list(user.find("I approve this spend").elements)
    deriver = _select(user, "the deriver (paid)")
    checker = _select(user, "the checker (a different model)")
    unticked = lambda: sum(not box.value for box in boxes)              # noqa: E731
    assert len(boxes) >= 2 and unticked() == 0                         # every page's default models: all ticked
    checker.value = "none"
    assert unticked() == 1                                              # the derivation's box alone
    checker.value = "gpt-5.6-sol"
    deriver.value = "gpt-5.6-sol"
    assert unticked() == 1
    deriver.value = "claude-opus-5-5"
    assert unticked() == 0


def test_a_paid_session_keeps_how_it_was_approved_and_an_old_one_hashes_as_before(tmp_path):
    from adroit.orchestrator.model_intake import Intake, Session, session_identity
    service = Intake()
    paid = service.start(1.0, "claude-opus-5-5", approval="auto")
    assert service.session(paid.session_id).approval == "auto"
    free = service.start(0, "claude-opus-5-5", approval="auto")
    assert free.approval == ""                                          # nothing paid: nothing approved
    old = Session(session_id="x" * 32, budget=1.0)
    assert "approval" not in old.model_dump() and session_identity(old) == session_identity(
        old.model_copy(update={"approval": ""}))


def test_a_free_launch_records_no_approval(tmp_path):
    folder = tmp_path / "job"
    popen = lambda *a, **k: SimpleNamespace(pid=os.getpid())            # noqa: E731
    job = engine.launch(["exclusion", "x.yaml"], folder, "free", popen=popen, approval="auto")
    assert job.approval == "" and engine.load(folder).approval == ""


# --- the auditor's post-review audit (2026-11-18): the money blockers ---------------------------------------------------

async def test_a_remembered_checker_is_not_the_default_the_setting_approves(user: User, tmp_path, monkeypatch):
    """PR-01: a failed check by GPT-5.6 Sol, then "suggest another route": the form opens on Sol (the earlier choice),
    but only the system's default checker (Claude Fable 5.1) is approved by the setting."""
    from adroit.agents.llm import FakeLLMClient
    from adroit.core.config import get_settings
    from tests.orchestrator.test_record_check import checker, verdict
    from tests.private_limit_fixtures import fixture
    calls = capture(monkeypatch)
    catalog, r = fixture(tmp_path)
    monkeypatch.setattr(get_settings(), "experimental_library_dir", catalog.root)
    service = checker(catalog)
    run = service.start(r.reference, "limit", 1.0, model="gpt-5.6-sol", retries=0)
    service.run(run.session_id, llm_for=lambda model: FakeLLMClient([verdict(False)]))
    workbench_settings.set_auto_approve(True)
    build_pages(tmp_path / "runs")
    from urllib.parse import urlencode as encode
    await user.open("/experiments/view?" + encode({"reference": r.reference}))
    user.find(marker="suggestion").type("read table 2 instead")
    user.find(marker="apply_suggestion").click()
    assert calls == []                                       # Sol, remembered, is not the default: nothing started
    sol = [s for s in user.find(kind=ui.select).elements
           if s.props.get("label") == "the checking model" and s.value == "gpt-5.6-sol"][0]
    sol.value = "claude-fable-5-1"                          # the system's default: approved by the setting
    user.find(marker="apply_suggestion").click()
    await user.should_see("Run:")
    assert calls[0]["approval"] == "auto"


async def test_a_setting_switched_off_or_damaged_after_the_page_opened_approves_nothing(user: User, tmp_path,
                                                                                        monkeypatch):
    """PR-03: the box the setting ticked is read again when the run is asked for: off, damaged or foreign, it is
    unticked and nothing starts, with the model unchanged or changed."""
    calls = capture(monkeypatch)
    r = stored()
    build_pages(tmp_path / "runs")
    for damage in ("off", "torn", "foreign", "absent"):
        workbench_settings.set_auto_approve(True)
        await user.open("/models/view?" + urlencode({"reference": r.reference}))
        assert _tick(user).value is True
        path = workbench_settings.settings_file()
        if damage == "off":
            workbench_settings.set_auto_approve(False)
        elif damage == "torn":
            path.write_text('{"auto_approve_default_models": tr')
        elif damage == "foreign":
            path.write_text('{"auto_approve_default_models": true, "other": 1}')
        else:
            path.unlink()
        user.find(marker="discover").click()
        assert calls == [], damage
        assert _tick(user).value is False
        await user.should_see("the auto-approve setting no longer applies here")


async def test_the_approval_option_reads_the_setting_again_too(user: User, tmp_path, monkeypatch):
    """PR-03, at a model's approval: discovery's own box, ticked by the setting, approves nothing once it is off."""
    from tests.ui.test_model_library import draft
    calls = capture(monkeypatch)
    workbench_settings.set_auto_approve(True)
    svc, s, d = draft()
    build_pages(tmp_path / "runs")
    await user.open("/models/intake?" + urlencode({"session": s.session_id, "step": d.step_id}))
    user.find("I reviewed the transcription, assumptions, parameters and canonical model").click()
    user.find("Start constraint discovery after saving").click()
    workbench_settings.set_auto_approve(False)
    user.find("Save reviewed revision").click()
    await user.should_see("discovery did not start")
    assert not [c for c in calls if c["command"][:2] == ["constraints", "discover"]]

"""The repair round after cycle 7's pin, in the workbench (2026-11-17; the AL7 repair record of 2026-11-17).

- NP17-01 (a non-physics audit of ``a7335be``): one press of a launching form starts one request: two presses of an
  intake made one session and one job, an invalid form then corrected makes one, and the same guard on Track 1 and the
  batch draft (``adroit.ui.submission``).
- NP17-02: a stale batch page removes the request it shows, by its identity, and starts only the draft it showed.
- NP17-03: a run record whose time is not a time is named where it is listed, never a page's failure, and left as it
  is; one with a time zone is read.
- AL5-03 (the auditor's cycle 5): a model file's survey proceeds to My model with that model and the survey's assessment.
- A simplified model's candidate says so (the owner, 2026-11-17).

A press here reaches the server as a click event, whatever the browser shows: the second of two quick clicks arrives
before the disable of the first reaches the browser. Offline: the job launcher replaced, nothing spawned.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
import yaml
from nicegui import events, ui
from nicegui.testing import User

from adroit.ui import batch, engine
from adroit.ui.app import build_pages
from tests.ui.test_model_library import capture


def _press(user: User, element) -> None:
    """A click event delivered to the server (as Chrome's trusted events do), the element enabled or not."""
    with user.client:
        for listener in list(element._event_listeners.values()):
            if listener.type == "click":
                events.handle_event(listener.handler, events.GenericEventArguments(sender=element, client=user.client,
                                                                                   args=None))


def _counted_sessions(monkeypatch) -> list:
    from adroit.orchestrator.model_intake import Intake
    started, real = [], Intake.start

    def start(self, *args, **kwargs):
        started.append(args)
        return real(self, *args, **kwargs)
    monkeypatch.setattr(Intake, "start", start)
    return started


# --- NP17-01 ---------------------------------------------------------------------------------------------------

async def test_two_presses_of_an_intake_make_one_session_and_one_job(user: User, tmp_path, monkeypatch) -> None:
    calls, started = capture(monkeypatch), _counted_sessions(monkeypatch)
    build_pages(tmp_path / "runs")
    await user.open("/models/intake")
    user.find("Idea, TeX or typed field/model YAML").elements.pop().value = "a Dirac fermion and a light Z prime"
    user.find("I approve this spend").click()
    button = user.find("Start reviewed intake").elements.pop()
    _press(user, button)
    _press(user, button)                    # before the first press's page has opened
    await user.should_see("Run: Interpret model")
    assert len(calls) == 1 and len(started) == 1 and calls[0][:2] == ["models", "step"]


async def test_an_invalid_intake_corrected_makes_one_session(user: User, tmp_path, monkeypatch) -> None:
    calls, started = capture(monkeypatch), _counted_sessions(monkeypatch)
    build_pages(tmp_path / "runs")
    await user.open("/models/intake")
    user.find("Model input kind").elements.pop().value = "paper"
    user.find("Retrieve arXiv identifier instead of uploading (optional)").elements.pop().value = "2105.00599"
    user.find("I approve this spend").click()
    button = user.find("Start reviewed intake").elements.pop()
    _press(user, button)                                          # no equation label: refused before a session
    await user.should_see("select one PDF upload or arXiv identifier")
    assert started == [] and calls == []
    user.find("Paper equation label (for example 3.1)").elements.pop().value = "3.1"
    _press(user, button)
    await user.should_see("Run: Interpret paper equation")
    assert len(started) == 1 and len(calls) == 1 and calls[0][:2] == ["models", "paper"]


async def test_an_intake_whose_launch_failed_reuses_its_session(user: User, tmp_path, monkeypatch) -> None:
    started = _counted_sessions(monkeypatch)
    calls, attempts = [], []

    def launch(command, folder, title, **kwargs):
        attempts.append(command)
        if len(attempts) == 1:
            raise ValueError("the run's folder could not be prepared")
        calls.append(command)
        folder.mkdir(parents=True, exist_ok=True)
        engine.save(engine.Job(folder=str(folder), command=command, title=title, kind=command[0], status="completed",
                               returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine, "launch", launch)
    build_pages(tmp_path / "runs")
    await user.open("/models/intake")
    user.find("Idea, TeX or typed field/model YAML").elements.pop().value = "a scalar singlet"
    user.find("I approve this spend").click()
    button = user.find("Start reviewed intake").elements.pop()
    _press(user, button)
    await user.should_see("could not be prepared")
    _press(user, button)
    await user.should_see("Run: Interpret model")
    assert len(started) == 1 and len(calls) == 1 and attempts[0][2] == attempts[1][2]       # one session


async def test_two_presses_of_track1_launch_one_scan(user: User, tmp_path, monkeypatch) -> None:
    calls = capture(monkeypatch)
    build_pages(tmp_path / "runs")
    await user.open("/new/track1")
    button = user.find("Scan the portal").elements.pop()
    _press(user, button)
    _press(user, button)
    await user.should_see("Run:")
    assert len(calls) == 1 and calls[0][0] == "track1"


async def test_two_presses_add_one_request_to_the_batch(user: User, tmp_path, monkeypatch) -> None:
    root = tmp_path / "runs"
    build_pages(root)
    await user.open("/new/track1")
    user.find(marker="batch_switch").elements.pop().value = True
    button = user.find("Scan the portal").elements.pop()
    _press(user, button)
    _press(user, button)
    await user.should_see("The draft")
    assert len(batch.draft(root)) == 1


def test_a_press_refused_by_its_form_leaves_it_open_and_an_async_one_holds_it(monkeypatch) -> None:
    from adroit.ui import submission
    said, went = [], []
    monkeypatch.setattr(submission, "ui", SimpleNamespace(notify=said.append,
                                                          navigate=SimpleNamespace(to=went.append)))
    refusals = iter([True, False])

    def handler():
        if next(refusals):
            return                                    # refused (an invalid form): nothing started
        submission.go("/live?path=a")
    press = submission.once(handler)
    press(None)
    press(None)
    press(None)
    assert went == ["/live?path=a", "/live?path=a"] and said == [submission.ALREADY]

    started = []

    async def slow():
        await asyncio.sleep(0)
        started.append(1)
        submission.go("/live?path=b")

    async def twice():
        pending = submission.once(slow)
        first = pending(None)
        assert pending(None) is None                    # while the first is running: nothing more starts
        await first
    asyncio.run(twice())
    assert started == [1] and said[-1] == submission.BUSY


# --- NP17-02 ---------------------------------------------------------------------------------------------------

def _prepared(root: Path, name: str) -> Path:
    folder = root / f"prepared_{name}"
    folder.mkdir(parents=True)
    return folder


def _paid(root: Path, name: str) -> None:
    batch.add_to_draft(root, ["idea", name, "--budget", "0.50"], _prepared(root, name), name, budget=0.5)


async def test_a_stale_pages_remove_removes_the_request_it_shows(user: User, tmp_path) -> None:
    root = tmp_path / "runs"
    for name in ("A", "B"):
        _paid(root, name)
    build_pages(root)
    await user.open("/batches")
    buttons = sorted(user.find("Remove").elements, key=lambda e: e.id)        # A's, then B's
    batch.remove_from_draft(root, batch.draft(root)[0])                       # A removed in another tab
    _press(user, buttons[0])                                                  # this page's Remove of A
    await user.should_see("no longer in the draft")
    assert [x.title for x in batch.draft(root)] == ["B"]                      # B had been removed with it


async def test_a_stale_pages_start_starts_nothing_and_keeps_the_draft(user: User, tmp_path, monkeypatch) -> None:
    root = tmp_path / "runs"
    spawned = []
    monkeypatch.setattr(batch, "_spawn", lambda b, popen: spawned.append(b) or b)
    for name in ("A", "B"):
        _paid(root, name)
    build_pages(root)
    await user.open("/batches")
    user.find(marker="batch_budget").elements.pop().value = 1.0
    batch.remove_from_draft(root, batch.draft(root)[0])                       # elsewhere: A out, C in, the same total
    _paid(root, "C")
    _press(user, user.find(marker="start_batch").elements.pop())
    await user.should_see("the draft has changed since this page showed it")
    assert spawned == [] and batch.batches(root) == []
    assert [x.title for x in batch.draft(root)] == ["B", "C"]
    await user.open("/batches")                                               # shown as it is now, confirmed again
    user.find(marker="batch_budget").elements.pop().value = 1.0
    _press(user, user.find(marker="start_batch").elements.pop())
    await user.should_see("Batches")
    assert [[x.title for x in b.items] for b in spawned] == [["B", "C"]]


def test_starting_binds_the_draft_shown_even_at_the_same_total(tmp_path) -> None:
    root = tmp_path / "runs"
    for name in ("A", "B"):
        _paid(root, name)
    shown = batch.draft_digest(batch.draft(root))
    batch.remove_from_draft(root, batch.draft(root)[0])
    _paid(root, "C")
    with pytest.raises(batch.DraftChanged):
        batch.start(root, "b", 1.0, popen=lambda *a, **k: SimpleNamespace(pid=1), shown=shown)
    assert [x.title for x in batch.draft(root)] == ["B", "C"]


# --- NP17-03 ---------------------------------------------------------------------------------------------------

def _job(root: Path, name: str, started: str, status: str = "running") -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    job = engine.Job(title=name, kind="track1", command=["track1", "x.yaml"], folder=str(folder), status=status,
                     acknowledged=False).model_dump(mode="json")
    job["started"] = started
    (folder / engine.JOB).write_text(json.dumps(job, indent=1))
    return folder


@pytest.mark.parametrize("page", ["/studies", "/activity"])
async def test_a_run_record_whose_time_is_not_a_time_is_named_and_kept(user: User, tmp_path, page) -> None:
    root = tmp_path / "runs"
    _job(root, "good", "2026-11-17T09:00:00", status="completed")
    bad = _job(root, "bad", "not-a-date")
    before = (bad / engine.JOB).read_bytes()
    build_pages(root)
    await user.open(page)
    await user.should_see(marker="unreadable_runs")
    text = user.find(marker="unreadable_runs").elements.pop().text
    assert "bad/job.json" in text and "ValidationError" in text and "good" not in text
    assert (bad / engine.JOB).read_bytes() == before                        # viewing writes nothing over it


def test_a_time_with_a_zone_is_read_as_this_machines(tmp_path) -> None:
    root = tmp_path / "runs"
    _job(root, "moved", "2026-11-17T09:00:00+00:00", status="completed")
    found, damaged = engine.listing(root)
    assert damaged == [] and "+" not in found[0].started
    from adroit.orchestrator import recovery
    assert recovery.summary(root) == {"running": 0, "attention": 0}


def test_a_record_damaged_after_it_was_listed_is_named(tmp_path) -> None:
    root = tmp_path / "runs"
    _job(root, "good", "2026-11-17T09:00:00", status="completed")
    later = _job(root, "later", "2026-11-17T09:00:00", status="completed")
    listed, _ = engine.listing(root)
    record = json.loads((later / engine.JOB).read_text())
    (later / engine.JOB).write_text(json.dumps({**record, "started": "yesterday"}))
    now, lost = engine.polled(listed)
    assert [j.title for j in now] == ["good"] and len(lost) == 1 and lost[0].path.endswith("later/job.json")


# --- AL5-03 ----------------------------------------------------------------------------------------------------

@pytest.mark.needs("cresst", "cdmslite", "optimum_interval", "solar_model")
async def test_a_model_files_survey_proceeds_to_that_model_with_its_assessment(user: User, tmp_path,
                                                                              monkeypatch) -> None:
    from adroit.agents.llm import FakeLLMClient
    from adroit.core.config import get_settings
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator import constraint_discovery as cd
    from tests.orchestrator.test_constraint_discovery import Web, _abstracts, _model, _proposals, _resolver
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path / "data")
    monkeypatch.setattr(get_settings(), "experimental_library_dir", tmp_path / "private")
    service = cd.Discovery(ExperimentalCatalog(tmp_path / "private"), abstracts=_abstracts, fetch=Web(),
                           resolver=_resolver)
    _, spec = _model(tmp_path)                       # fully numerical, as the auditor's control's model
    spec = spec.model_copy(update={"couplings": [c.model_copy(update={"value": 0.01}) for c in spec.couplings]})
    path = tmp_path / "numerical_model.yaml"
    path.write_text(yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False))
    s = service.start(str(path), cd.Options(budget=1.0))
    service.run(s.session_id, llm=FakeLLMClient([_proposals(uncertain=True)]))
    calls = capture(monkeypatch)
    build_pages(tmp_path / "runs")
    await user.open("/constraints/discovery?" + urlencode({"session": s.session_id}))
    user.find(marker="proceed").click()
    await user.should_see(marker="survey_model")
    panels = user.find(ui.tab_panels).elements.pop()
    assert getattr(panels.value, "_props", {}).get("name", panels.value) == "My model"   # not the library tab
    text = next(e.value for e in user.find(ui.textarea).elements if "my scalar singlet" in (e.value or ""))
    assert yaml.safe_load(text) == spec.model_dump(mode="json")
    assert user.find(marker="survey_pin").elements.pop().value is True
    await user.should_see(marker="scan_state")
    user.find(marker="run_model_scan").click()
    await user.should_see("Run:")
    command = calls[0]
    assert command[0] == "track1" and "--discovery" in command
    model_file = next(Path(w) for w in command if w.endswith("model.yaml"))
    assert yaml.safe_load(model_file.read_text()) == spec.model_dump(mode="json")


# --- simplified models -----------------------------------------------------------------------------------------

async def test_a_simplified_candidate_says_so_in_its_name_and_what_it_leaves_out(user: User, tmp_path) -> None:
    from adroit.agents.llm import FakeLLMClient
    from adroit.agents.model_intake import Interpretation
    from adroit.orchestrator.model_intake import Intake
    from adroit.parameter_space.simplified import model
    service = Intake()
    s = service.start(1)
    spec = model("vector", 10, 125, .001, .25).model_copy(update={"name": "Bino with a light stau"})
    d = service.step(s.session_id, "tex", "x", llm=FakeLLMClient([Interpretation(
        transcription="t", spec=spec, simplified="the other superpartners")]))
    build_pages(tmp_path / "runs")
    await user.open("/models/intake?" + urlencode({"session": s.session_id, "step": d.step_id}))
    await user.should_see("Candidate 1: Bino with a light stau (simplified model)")
    await user.should_see("A simplified model: it leaves out the other superpartners.")


@pytest.mark.parametrize("started", ["0001-01-01T00:00:00+23:59", "9999-12-31T23:59:59-23:59"])
async def test_a_time_beyond_the_calendar_in_local_time_is_a_damaged_record(user: User, tmp_path, started) -> None:
    """The audit loop's AL8-02: an extreme offset overflowed converting to local time, outside ``moment``'s error
    handling, and Studies, Activity and Home returned 500. The record is named as damaged; its neighbour is listed."""
    from adroit.orchestrator import recovery
    root = tmp_path / "runs"
    _job(root, "good", "2026-11-17T09:00:00", status="completed")
    bad = _job(root, "bad", started)
    before = (bad / engine.JOB).read_bytes()
    found, damaged = engine.listing(root)
    assert [j.title for j in found] == ["good"] and len(damaged) == 1
    assert recovery.summary(root) == {"running": 0, "attention": 1}         # no crash: the damaged record needs you
    build_pages(root)
    await user.open("/studies")
    await user.should_see(marker="unreadable_runs")
    assert (bad / engine.JOB).read_bytes() == before

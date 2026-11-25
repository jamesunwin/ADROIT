"""The owner's report of 2026-10-23: a completed model intake showed $0 on its live view, and its "Open the results"
button opened the physics-study viewer, which said it might still be running.

Every journey here is offline. The provider's SDK is replaced by a scripted one that answers in each provider's own
format (an Anthropic ``Message``, an OpenAI ``Response``), behind the real budgeted client and the session's paid
ledger; the workbench's launch runs the real command line in-process (``inline``) instead of a detached process, and
writes the job record and log as the runner does. No request leaves the machine.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from nicegui import ui
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.agents import llm as llm_module
from adroit.agents.ideas import CouplingValue, ModelProposal, ModelProposals, ModelValues, ValueProposals
from adroit.agents.model_intake import Interpretation
from adroit.core.model_spec import Charges, FieldRole, ModelField
from adroit.core.pricing import price_per_token
from adroit.ui import engine

MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-5.6-sol"}
SINGLET = ModelField(name="S", role=FieldRole.dark_matter, spin=0, self_conjugate=True, dark_parity=-1, mass_gev=300.0)
IDEA_TOKENS, REFINE_TOKENS, VALUES_TOKENS = (1200, 800), (1000, 500), (600, 300)


def dollars(provider: str, tokens: tuple[int, int]) -> float:
    """What one request of these input and output tokens costs at the session model's price."""
    p_in, p_out = price_per_token(MODELS[provider])
    return tokens[0] * p_in + tokens[1] * p_out


def usd(value: float) -> str:
    return f"${value:.4f}" if value < 1 else f"${value:.2f}"


def anthropic_reply(text: str, tokens: tuple[int, int]):
    import anthropic.types
    return anthropic.types.Message.model_validate({
        "id": "msg_offline", "type": "message", "role": "assistant", "model": MODELS["anthropic"],
        "content": [{"type": "text", "text": text}], "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]}})


def openai_reply(text: str, tokens: tuple[int, int]):
    from openai.types.responses import Response
    return Response.model_validate({
        "id": "resp_offline", "object": "response", "created_at": 1792773606.0, "model": MODELS["openai"],
        "status": "completed", "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
        "output": [{"type": "message", "id": "msg_offline", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": text, "annotations": []}]}],
        "usage": {"input_tokens": tokens[0], "output_tokens": tokens[1], "total_tokens": sum(tokens),
                  "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                  "output_tokens_details": {"reasoning_tokens": 0}}})


class ProviderDown(Exception):
    """A provider failure (not one of ADROIT's own errors)."""


class Provider:
    """A scripted provider: each request takes the next reply, (an answer's text, its tokens) or an exception."""

    def __init__(self, name: str) -> None:
        self.name, self.replies, self.requests = name, [], []

    def create(self, **request):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return (anthropic_reply if self.name == "anthropic" else openai_reply)(*reply)


@pytest.fixture
def provider(monkeypatch, tmp_path) -> dict[str, Provider]:
    """Both providers scripted: the session's client is the real one, with a stub in place of the SDK."""
    scripted = {"anthropic": Provider("anthropic"), "openai": Provider("openai")}

    class Anthropic(llm_module.LLMClient):
        def __init__(self, **kw):
            super().__init__(**kw, client=SimpleNamespace(messages=SimpleNamespace(create=scripted["anthropic"].create)))

    class OpenAI(llm_module.OpenAIClient):
        def __init__(self, **kw):
            super().__init__(**kw, client=SimpleNamespace(responses=SimpleNamespace(create=scripted["openai"].create)))

    monkeypatch.setattr(llm_module, "LLMClient", Anthropic)
    monkeypatch.setattr(llm_module, "OpenAIClient", OpenAI)
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(), "runs_dir", tmp_path / "runs")
    return scripted


@pytest.fixture
def inline(monkeypatch) -> list[Path]:
    """The workbench's launch, in-process: the job record, the real command line, its log (standard output and error,
    as the runner keeps them) and its final status by its exit code, as ``runner.run`` writes them. The job has its
    attempt, which the command is told, as the runner tells it (ADROIT_JOB_ATTEMPT, with its folder: DC-01), so that the
    study it publishes names its run."""
    from adroit.core.receipts import BUDGET_STOPPED
    from adroit.orchestrator import cli
    folders: list[Path] = []

    def launch(command, folder, title, confirmed_budget=0.0, popen=None, owner="", approval=""):
        cost = engine.paid(command)
        if cost > 0 and cost > confirmed_budget + 1e-9:
            raise engine.BudgetNotConfirmed("unconfirmed")
        folder = Path(folder).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        attempt = uuid4().hex
        engine.save(engine.Job(title=title, kind=command[0], command=command, folder=str(folder), budget_usd=cost,
                               acknowledged=True, attempt=attempt, approval=approval if cost > 0 else ""))
        with monkeypatch.context() as told:
            told.setenv("ADROIT_JOB_FOLDER", str(folder))
            told.setenv("ADROIT_JOB_ATTEMPT", attempt)
            result = CliRunner().invoke(cli.app, command)
        (folder / engine.LOG).write_text(f"$ adroit {' '.join(command)}\n{result.output}")
        code = result.exit_code
        status = "completed" if code == 0 else "budget_stopped" if code == BUDGET_STOPPED else "failed"
        folders.append(folder)
        return engine.update(folder, status=status, returncode=code, finished=engine._now())

    monkeypatch.setattr(engine, "launch", launch)
    return folders


def proposals(name: str = "RealSinglet") -> str:
    return ModelProposals(proposals=[ModelProposal(name=name, fields=[SINGLET], rationale="a Z2-odd real scalar",
                                                   stability="Z2")]).model_dump_json()


def values(*names: str) -> str:
    """The model builder's second answer (2026-11-21): a value for one coupling of each model, numbered from 1."""
    return ValueProposals(models=[ModelValues(model=i, couplings=[CouplingValue(name=n, value=0.1, reason="benchmark")])
                                  for i, n in enumerate(names, 1)]).model_dump_json()


def idea_replies(replies: list, *names: str, text: str | None = None) -> None:
    """An idea intake's two replies: the proposals, then the values of the named couplings."""
    replies.extend([(text or proposals(), IDEA_TOKENS), (values(*names or ("lam_H_S",)), VALUES_TOKENS)])


async def test_candidates_are_ruled_apart_with_bold_titles_and_no_declarations_paragraph(user: User, tmp_path,
                                                                                          provider, inline):
    """The owner's JU1 (2026-11-16): a medium rule before Candidate 2 and each later one, the candidates' titles in
    bold, and the declarations' JSON paragraph moved to the README (no longer on the page)."""
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    # a different field content (not a duplicate) that can run with no proposed value: an electroweak quintuplet (a
    # complex singlet needs the right one of its two portals, L-7)
    quintuplet = ModelField(name="psi5", role=FieldRole.dark_matter, spin=0.5, mass_gev=10000.0, dark_parity=-1,
                            charges=Charges(su2=5, hypercharge=1.0))
    two = ModelProposals(proposals=[ModelProposal(name=n, fields=[f], rationale="a Z2-odd candidate", stability="Z2")
                                    for n, f in (("SingletA", SINGLET), ("Quintuplet", quintuplet))]).model_dump_json()
    idea_replies(provider["anthropic"].replies, "lam_H_S", text=two)
    await start_intake(user, "anthropic")
    await user.should_see("Draft ready for review")
    user.find(marker="primary_action").click()
    await user.should_see("Candidate 1: SingletA")
    await user.should_see("Candidate 2: Quintuplet")
    assert len(user.find(marker="candidate_rule").elements) == 1          # before Candidate 2 only
    panels = user.find(marker="candidate").elements
    assert len(panels) == 2 and all("text-weight-bold" in e.props.get("header-class", "") for e in panels)
    await user.should_not_see("Optional JSON list")


async def start_intake(user: User, provider: str, budget: float = 1.0) -> None:
    """The intake form: an idea in words, the provider's model, the session budget, the approval, Start."""
    await user.open("/models/intake")
    user.find("Idea, TeX or typed field/model YAML").elements.pop().value = "a Z2-odd real scalar singlet"
    choice = next(e for e in user.find(kind=ui.select).elements if e.props.get("label") == "Interpretation model (paid)")
    choice.value = MODELS[provider]
    user.find("Session budget ($)").elements.pop().value = budget
    user.find("I approve this spend").click()
    user.find("Start reviewed intake").click()


def page(root: Path, folder: Path) -> str:
    return "/live?" + urlencode({"path": str(folder.relative_to(root.resolve()))})


@pytest.mark.parametrize("name", ["anthropic", "openai"])
async def test_an_intake_shows_its_cost_and_opens_its_draft_then_a_refinement_counts_only_itself(
        user: User, tmp_path, provider, inline, name):
    """Enter an idea, choose the provider and budget, approve, run: the live view says the draft is ready (not a
    study), shows this request's cost, the session's total and its cap from the ledger, and its primary button opens
    the draft. A refinement in the same session shows its own cost only, the session total both; a reload and the
    older draft show the same; an old /study link to the intake folder offers the draft."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    idea_replies(provider[name].replies)
    await start_intake(user, name)
    await user.should_see("Draft ready for review")
    first_cost = dollars(name, IDEA_TOKENS) + dollars(name, VALUES_TOKENS)      # the proposals, then the values
    await user.should_see(f"This run: {usd(first_cost)}")
    await user.should_see(f"Session total so far: {usd(first_cost)} spent of its approved $1.00 cap")
    await user.should_see("No physics calculation was run")
    await user.should_not_see("Open the results")
    first = inline[0]
    draft = json.loads((first / "intake.json").read_text())
    from adroit.orchestrator.model_intake import Intake
    ledger = [json.loads(x) for x in (Intake().folder(draft["session_id"]) / "paid.jsonl").read_text().splitlines()]
    received = next(r for r in ledger if r["state"] == "received")["response"]
    assert ("content" if name == "anthropic" else "output") in received          # the provider's own format
    assert len(json.loads((first / "paid_requests.json").read_text())["request_ids"]) == 2
    user.find(marker="primary_action").click()                          # "Review model draft"
    await user.should_see("Candidate 1: RealSinglet")
    await user.should_see(f"This session: {usd(first_cost)} spent of its approved $1.00 cap")
    assert len(provider[name].requests) == 2                            # reviewing asked nothing

    refined = draft["choices"][0]["spec"] | {"name": "RealSingletHeavier"}
    reply = Interpretation(transcription="the singlet, heavier", spec=refined).model_dump_json()
    provider[name].replies.append((reply, REFINE_TOKENS))
    user.find("Refinement or clarification instructions").elements.pop().value = "rename it"
    user.find("Refine this candidate").click()
    await user.should_see("Draft ready for review")
    second_cost = dollars(name, REFINE_TOKENS)
    await user.should_see(f"This run: {usd(second_cost)}")
    await user.should_see(f"Session total so far: {usd(first_cost + second_cost)} spent of its approved $1.00 cap")
    second = inline[1]
    await user.open(page(root, second))                                 # a reload reads the same records
    await user.should_see(f"This run: {usd(second_cost)}")
    await user.open(page(root, first))                                  # the first run still shows only its own
    await user.should_see(f"This run: {usd(first_cost)}")
    await user.should_see(f"Session total so far: {usd(first_cost + second_cost)}")
    await user.open("/models/intake?" + urlencode({"session": draft["session_id"], "step": draft["step_id"]}))
    await user.should_see("Candidate 1: RealSinglet")                    # the older draft, reopened
    await user.should_see(f"draft {draft['step_id'][:10]}")
    await user.open("/study?" + urlencode({"path": str(first.relative_to(root))}))       # an old "Open the results"
    await user.should_see("Draft ready for review")
    await user.should_see("Review model draft")
    await user.should_not_see("may still be going")
    assert len(provider[name].requests) == 3            # the idea's two, the refinement's one; none on review


async def test_a_failed_request_shows_its_uncertain_bill_and_where_to_go(user: User, tmp_path, provider, inline):
    """A provider failure: the run failed, nothing settled, the reservation still held is shown as uncertain (never
    as a confirmed $0), and the next action starts again; the session's page does not call it pending."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    provider["anthropic"].replies.append(ProviderDown("provider unreachable"))
    await start_intake(user, "anthropic")
    await user.should_see("Interpretation: failed")
    await user.should_see("the provider call failed (ProviderDown)")
    await user.should_see("This run: $0.0000 settled, and up to $")
    await user.should_see("reserved whose bill is not yet known")
    await user.should_see("Start a new model intake")
    session = engine.load(inline[0]).command[2]
    await user.open("/models/intake?" + urlencode({"session": session}))
    await user.should_see("No draft yet: the runs of this session ended without one.")
    await user.should_not_see("pending")
    assert root.exists()


async def test_an_answer_that_is_not_a_model_is_billed_and_stops(user: User, tmp_path, provider, inline):
    """Incomplete output from the provider: three answers that are not the schema, each billed; the run failed and
    shows the three requests' cost."""
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    provider["openai"].replies.extend([("not a model", IDEA_TOKENS)] * 3)
    await start_intake(user, "openai")
    await user.should_see("Interpretation: failed")
    await user.should_see(f"This run: {usd(3 * dollars('openai', IDEA_TOKENS))}")
    assert len(provider["openai"].requests) == 3


async def test_a_completed_run_without_its_draft_record_says_so(user: User, tmp_path, provider, inline):
    """Incomplete output on disk: a run that completed but whose draft record is missing is not shown as a draft or
    a study; its session's page holds the drafts that were saved."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    idea_replies(provider["anthropic"].replies)
    await start_intake(user, "anthropic")
    await user.should_see("Draft ready for review")
    (inline[0] / "intake.json").unlink()
    await user.open(page(root, inline[0]))
    await user.should_see("Finished, but the draft is not available")
    await user.should_see("draft record (intake.json) was not written")
    user.find(marker="primary_action").click()                           # "Open the intake session"
    await user.should_see("Candidate 1: RealSinglet")


async def test_a_budget_refusal_sends_nothing_and_says_what_to_do(user: User, tmp_path, provider, inline):
    """A session cap too small for the request's reservation: stopped before dispatch, $0 because the run's request
    record says no request was sent, the cap shown, and a new intake offered."""
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    await start_intake(user, "anthropic", budget=0.01)
    await user.should_see("Stopped at the cap before a paid request")
    await user.should_see("This run: $0 (no paid request was sent)")
    await user.should_see("Session total so far: $0.0000 spent of its approved $0.0100 cap")
    await user.should_see("Start a new model intake")
    assert not provider["anthropic"].requests
    assert "raise-cap" in (inline[0] / engine.LOG).read_text()


def _job(folder: Path, command: list[str], status: str = "completed", title: str = "a run") -> engine.Job:
    folder.mkdir(parents=True, exist_ok=True)
    job = engine.Job(title=title, kind=command[0], command=command, folder=str(folder), status=status,
                     budget_usd=engine.paid(command), acknowledged=True, returncode=0 if status == "completed" else 2)
    engine.save(job)
    return job


async def test_a_paid_run_without_a_spending_record_is_not_shown_as_free(user: User, tmp_path):
    """Missing accounting is said to be missing: a paid derivation that failed before writing its study shows "not
    available", not "spent $0.00"."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _job(root / "derive", ["lagrangian", "m.yaml", "--derive", "--budget", "1.5", "--out", "x"], status="failed")
    await user.open("/live?path=derive")
    await user.should_see("This run: not available (this run has not reported its spending)")
    await user.should_see("Approved budget for this run: $1.50")
    await user.should_not_see("spent $0.00")


async def test_the_activity_page_offers_a_completed_drafts_review(user: User, tmp_path, provider, inline):
    """Activity: a completed intake is a draft to review, with its review link, not a bare "completed"."""
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    idea_replies(provider["openai"].replies)
    await start_intake(user, "openai")
    await user.should_see("Draft ready for review")
    await user.open("/activity")
    await user.should_see("Draft ready for review")
    link = user.find(marker="outcome_action").elements.pop()
    query = parse_qs(urlsplit(link.props["href"]).query)
    assert link.text == "Review model draft" and set(query) == {"session", "step"}


def test_every_workbench_job_type_has_its_destination_and_cost(tmp_path, monkeypatch):
    """The inventory (docs/workbench_intake_fix_2026-10-23.md): each job type's output, the page that reviews it and
    where its cost is read."""
    from adroit.core.config import get_settings
    from adroit.orchestrator import studies
    from adroit.ui import outcomes
    root = tmp_path / "runs"
    monkeypatch.setattr(get_settings(), "experimental_library_dir", tmp_path / "experimental")

    track1 = _job(root / "t1", ["track1", "m.yaml", "--out", "x"])
    (root / "t1" / "result.json").write_text("{}")
    studies.record(root / "t1", "track1", "Track 1")
    assert outcomes.outcome(root, root / "t1", track1).primary.target == "/study?path=t1"
    assert outcomes.cost_lines(outcomes.cost(root / "t1", track1))[0] == "This run: $0 (no paid request)"

    idea = _job(root / "idea", ["idea", "--text", "x", "--budget", "1", "--out", "x"], status="budget_stopped")
    (root / "idea" / "result.json").write_text(json.dumps({"status": "budget_stopped", "committed_usd": 0.31}))
    (root / "idea" / "report.md").write_text("stopped\n")
    result = outcomes.outcome(root, root / "idea", idea)
    assert result.headline == "Stopped at the cap before a paid request" and result.output == "report"
    stopped = outcomes.cost(root / "idea", idea)          # a stop record without its split: committed, not spent
    assert stopped.run_usd is None and stopped.run_committed_usd == pytest.approx(0.31)

    signal = root / "signal_run"
    promote = _job(signal / "children" / "promotion_x", ["promote", str(signal), "class:0", "--toys", "10"])
    assert outcomes.outcome(root, Path(promote.folder), promote).primary.target == "/study?path=signal_run"

    record = tmp_path / "draft_1304.4279.yaml"
    record.write_text("name: draft\n")
    drafted = _job(root / "anomaly", ["anomaly", "draft", "--arxiv", "1304.4279", "--out", str(record),
                                      "--budget", "0.5", "--model", "claude-opus-5-5"])
    (root / "anomaly" / engine.LOG).write_text(f"written to {record} (a draft); spent $0.12\n")
    result = outcomes.outcome(root, root / "anomaly", drafted)
    assert result.primary.target == "/new/anomaly?" + urlencode({"record": str(record)})
    assert outcomes.cost(root / "anomaly", drafted).run_usd == pytest.approx(0.12)

    from adroit.core.experimental_extraction import ExtractionStep
    extract = _job(root / "extract", ["experiments", "extract", "a" * 32, "--batch", "0", "--budget", "1", "--out", "x"])
    (root / "extract" / "extraction.json").write_text(ExtractionStep(
        step_id="s", session_id="a" * 32, created_at="2026-10-23T00:00:00+00:00", input_revision="experimental:e@1",
        output_revision="experimental:e@2", unit_ids=[], explanation="read", raw_answer={}).model_dump_json())
    result = outcomes.outcome(root, root / "extract", extract)
    assert result.primary.target == "/experiments/view?" + urlencode({"reference": "experimental:e@2"})
    assert result.links[0].target == "/experiments/session?session=" + "a" * 32
    assert outcomes.cost(root / "extract", extract).run_usd is None             # its session's ledger is not there

    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    budgets = Intake(Catalog(tmp_path / "experimental"))
    session = budgets.start(1.0, "claude-opus-5-5").session_id
    rows = [{"id": "r", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.2},
            {"id": "r", "state": "settled", "cost_usd": 0.07}]
    (budgets.folder(session) / "paid.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    discover = _job(root / "discover", ["constraints", "discover", "catalog:m@r", "--budget", "1", "--out", "x"])
    (root / "discover" / "discovery.json").write_text(json.dumps(
        {"session": session, "state": {"relevance": {"status": "done"}, "extraction": {"status": "budget_stopped"}}}))
    result = outcomes.outcome(root, root / "discover", discover)
    assert result.primary.target == "/constraints/discovery?session=" + session
    assert result.headline == "Survey finished with stages not done"
    assert outcomes.cost(root / "discover", discover).run_usd == pytest.approx(0.07)


def test_a_run_from_before_the_request_record_reads_its_log(tmp_path):
    """The evidence runs of 2026-10-23 have no request record: their cost is the session ledger's totals the log
    printed before and after (one run; then a refinement in the same session, counted alone); a log without them is
    "not available"."""
    from adroit.orchestrator.model_intake import Intake
    from adroit.ui import outcomes
    service = Intake()
    session = service.start(1.0, "claude-opus-5-5").session_id
    rows = [{"id": "a", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.25},
            {"id": "a", "state": "settled", "cost_usd": 0.054107},
            {"id": "b", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.25},
            {"id": "b", "state": "settled", "cost_usd": 0.03}]
    (service.folder(session) / "paid.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    line = "paid request: claude-opus-5-5; reserving up to $0.2493 before dispatch; committed ${:.4f} of the $1.00 hard cap"
    runs = []
    for name, before, after in (("first", 0.0, 0.054107), ("second", 0.054107, 0.084107)):
        job = _job(tmp_path / name, ["models", "step", session, "--kind", "idea", "--budget", "1.0"])
        status = {"cap": 1.0, "spent": after, "reserved_uncertain": 0, "remaining": 1 - after}
        (tmp_path / name / engine.LOG).write_text(line.format(before) + "\n{\n}\n" + json.dumps(status) + "\n")
        runs.append(outcomes.cost(tmp_path / name, job))
    assert runs[0].run_usd == pytest.approx(0.054107)          # the log's "before" is printed to $0.0001
    assert runs[1].run_usd == pytest.approx(0.03, abs=1e-4)
    assert runs[1].session_spent_usd == pytest.approx(0.084107)
    broken = _job(tmp_path / "broken", ["models", "step", session, "--kind", "idea", "--budget", "1.0"], "failed")
    (tmp_path / "broken" / engine.LOG).write_text(line.format(0.084107) + "\nIntake stopped: ...\n")
    lines = outcomes.cost_lines(outcomes.cost(tmp_path / "broken", broken))
    assert lines[0].startswith("This run: not available") and lines[1].startswith("Session total so far: $0.0841")


def test_a_refused_refinement_leads_back_to_its_draft(tmp_path):
    """A refinement stopped at the cap: the next action is its parent draft, where the cap is raised."""
    from adroit.ui import outcomes
    job = _job(tmp_path / "r", ["models", "step", "a" * 32, "--kind", "refine", "--parent-step", "b" * 64,
                                "--budget", "1.0"], "budget_stopped")
    result = outcomes.outcome(tmp_path, tmp_path / "r", job)
    assert result.primary.label == "Back to the draft it refines"
    assert result.primary.target == "/models/intake?" + urlencode({"session": "a" * 32, "step": "b" * 64})
    assert "Raise the session's cap" in result.detail


async def test_a_finished_runs_page_keeps_its_primary_action_between_refreshes(user: User, tmp_path):
    """The auditor's CO recheck (2026-10-26): the live view was rebuilt every second, so a finished run's primary button
    was replaced under a click, and the click's event, reaching the server for a button no longer there, was
    dropped (the intake's "Review model draft", intermittently, under load). Each part of the view is rebuilt only
    when what it shows changes, and the outcome's actions are a part of their own: the same button across ticks, the
    run's end and its report, none once there is no action. The button carries its destination as a link, which the
    browser follows without the server."""
    import asyncio
    import os
    from adroit.orchestrator import studies
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder = root / "scan"
    _job(folder, ["track1", "--portal", "higgs_portal_scalar", "--out", str(folder)], status="running")
    engine.update(folder, pid=os.getpid())
    (folder / "result.json").write_text(json.dumps({"verdict": {"level": "viable"}}))
    studies.record(folder, "track1", "the scan")
    await user.open("/live?path=scan")
    await user.should_see("The run: running")
    first = user.find(marker="primary_action").elements.pop()
    assert first.props["href"].startswith("/study?") and "scan" in first.props["href"]
    await asyncio.sleep(2.5)                                            # two refresh ticks, nothing changed
    assert user.find(marker="primary_action").elements.pop() is first
    engine.update(folder, status="completed", returncode=0, finished="2026-10-26T12:00:00")
    await asyncio.sleep(1.3)
    await user.should_see("Study complete")
    assert user.find(marker="primary_action").elements.pop() is first
    (folder / "report.md").write_text("# The scan\n")
    await asyncio.sleep(1.5)
    assert user.find(marker="primary_action").elements.pop() is first
    (folder / studies.FILE).unlink()
    await asyncio.sleep(1.3)
    await user.should_see("Finished without a study record")
    await user.should_not_see(marker="primary_action")


async def test_an_intakes_draft_button_is_kept_when_its_job_ends(user: User, tmp_path):
    """The intake failure the release checks of 2026-10-26 found on dbea83c: a model intake writes its draft, and
    the live view shows "Review model draft", while its job still runs; the job's end a moment later (its process
    gone, its record final; longer under load) changed the view, which was rebuilt, and the button with it, under a
    click. The button is kept as the job ends."""
    import asyncio
    import os
    import yaml
    from adroit.orchestrator.model_intake import Intake
    from adroit.parameter_space.simplified import model
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    service = Intake()
    session = service.start()
    draft = service.step(session.session_id, "typed",
                         yaml.safe_dump(model("vector", 10, 125, .001, .25).model_dump(mode="json")))
    folder = root / "intake"
    _job(folder, ["models", "step", session.session_id, "--kind", "typed", "--out", str(folder)], status="running",
         title="Interpret model")
    engine.update(folder, pid=os.getpid())
    (folder / "intake.json").write_text(draft.model_dump_json())
    await user.open("/live?path=intake")
    await user.should_see("Draft ready for review")
    button = user.find(marker="primary_action").elements.pop()
    engine.update(folder, status="completed", returncode=0, finished="2026-10-26T12:00:00")
    await asyncio.sleep(1.3)
    await user.should_see("completed")
    assert user.find(marker="primary_action").elements.pop() is button


async def test_a_running_runs_cancel_is_not_replaced_while_its_log_grows(user: User, tmp_path):
    """The same for Cancel while a run runs: the status row (its badge, the elapsed time, Cancel) is made once and
    updated in place, so Cancel is the same button while the clock moves and the log grows, and is hidden once the
    run has ended."""
    import asyncio
    import os
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder = root / "scan"
    folder.mkdir(parents=True)
    engine.save(engine.Job(title="a scan", kind="track1", command=["track1", "--out", str(folder)], folder=str(folder),
                           status="running", acknowledged=True, pid=os.getpid()))
    await user.open("/live?path=scan")
    await user.should_see(marker="cancel_run")
    cancel = user.find(marker="cancel_run").elements.pop()
    for line in ("one", "two"):
        (folder / engine.LOG).write_text(f"{line}\n")
        await asyncio.sleep(1.3)                                        # a tick: the view rebuilt for the log
        await user.should_see(line)
        assert user.find(marker="cancel_run").elements.pop() is cancel and cancel.visible
    engine.update(folder, status="completed", finished="2026-10-26T12:00:00")
    await asyncio.sleep(1.3)
    await user.should_see("completed")
    await user.should_not_see(marker="cancel_run")
    assert not cancel.visible and cancel.client is not None and not cancel.is_deleted

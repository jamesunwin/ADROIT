"""The workflow acceptance audit of 2026-10-24 (the independent audit of 2026-10-24 (workflow acceptance)): WA-01 to WA-07.

Each journey is driven through the workbench's pages where it has one, and checked against the record it reports (the
saved result, the paid ledger, the file written). Offline: the provider's SDK is the scripted one of
``test_run_outcomes`` behind the real budgeted client, and the workbench's launch runs the real command line in-process
with the job's folder in its environment, as the runner gives it (``inline_job``). No request leaves the machine.
"""
from __future__ import annotations

from pydantic import SecretStr
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from nicegui import ElementFilter, ui
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.agents import llm as llm_module
from adroit.ui import engine
from tests.ui.test_run_outcomes import (  # noqa: F401 - provider and inline are fixtures used here
    dollars, inline, page, provider, start_intake, usd)

PAPER = "0000.00000"


def draft_reply(name: str) -> str:
    """A drafter's answer: a complete synthetic record named ``name``."""
    from adroit.agents.anomaly import AnomalyDraft
    from adroit.experiments.anomaly import Curve, Halo
    return AnomalyDraft(name=name, target="Si", references=["synthetic:workflow-audit"], exposure_kg_day=1000.0,
                        window_kev=[5.0, 30.0], events_kev=[8.6, 10.4, 14.2], resolution_kev=0.2, background_events=0.4,
                        efficiency_points=Curve(recoil_energy_kev=[5.0, 30.0], efficiency=[1.0, 1.0]), halo=Halo(),
                        needs_person=["synthetic: not a publication"]).model_dump_json()


@pytest.fixture
def inline_job(monkeypatch) -> list[Path]:
    """The workbench's launch, in-process, as ``inline`` but with the job's folder in the command's environment
    (ADROIT_JOB_FOLDER), as ``runner.run`` gives it, and its attempt (ADROIT_JOB_ATTEMPT: DC-01)."""
    from adroit.core.receipts import BUDGET_STOPPED
    from adroit.orchestrator import cli
    folders: list[Path] = []

    def launch(command, folder, title, confirmed_budget=0.0, popen=None, owner="", approval=""):
        cost = engine.paid(command)
        if cost > 0 and cost > confirmed_budget + 1e-9:
            raise engine.BudgetNotConfirmed("unconfirmed")
        folder = Path(folder).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        from uuid import uuid4
        attempt = uuid4().hex
        engine.save(engine.Job(title=title, kind=command[0], command=command, folder=str(folder), budget_usd=cost,
                               acknowledged=True, attempt=attempt, approval=approval if cost > 0 else ""))
        monkeypatch.setenv("ADROIT_JOB_FOLDER", str(folder))
        monkeypatch.setenv("ADROIT_JOB_ATTEMPT", attempt)
        result = CliRunner().invoke(cli.app, command)
        monkeypatch.delenv("ADROIT_JOB_FOLDER")
        monkeypatch.delenv("ADROIT_JOB_ATTEMPT")
        (folder / engine.LOG).write_text(f"$ adroit {' '.join(command)}\n{result.output}")
        code = result.exit_code
        status = "completed" if code == 0 else "budget_stopped" if code == BUDGET_STOPPED else "failed"
        folders.append(folder)
        return engine.update(folder, status=status, returncode=code, finished=engine._now())

    monkeypatch.setattr(engine, "launch", launch)
    return folders


async def draft_from_paper(user: User, target: str = "") -> None:
    """Add a signal → draft from the paper: its identifier, an optional file, the drafter, $0.50 approved, Draft."""
    await user.open("/new/anomaly")
    user.find("arXiv identifier").elements.pop().value = PAPER
    if target:
        user.find("write the draft to").elements.pop().value = target
    user.find("the most this run may spend ($)").elements.pop().value = 0.5
    user.find("I approve this spend").click()
    user.find(kind=ui.button, content="Draft").click()


# --- WA-05 and WA-03: two drafts of one paper, each its own file, each its own cost ------------------------------

async def test_two_drafts_of_one_paper_keep_their_own_files_pages_and_costs(user: User, tmp_path, provider, inline_job,  # noqa: F811
                                                                             monkeypatch):
    """WA-05: two ordinary drafts of the same paper (output left blank) had written one file; the first run's "Check
    the draft record" then opened the second draft. Each now has its own file, its page opens its own draft, and a
    draft replaced afterwards is said to be replaced. WA-03: each run's settled $0.0024 is shown from its own paid
    ledger, not read from the log's whole-cent "spent $0.00" as "no paid request was sent"."""
    from adroit.retrieval import corpus
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    monkeypatch.setattr(corpus, "fetch_arxiv_pdf_text", lambda arxiv: "a synthetic paper with three events")
    tokens = (100, 100)
    cost = dollars("anthropic", tokens)
    assert 0 < cost < 0.005                                              # under a cent: the case that showed $0
    for name in ("FIRST", "SECOND"):
        provider["anthropic"].replies.append((draft_reply(f"AUDIT draft {name}"), tokens))
        await draft_from_paper(user)
        await user.should_see("Signal record draft ready for review")
        await user.should_see(f"This run: {usd(cost)}")
        await user.should_not_see("no paid request was sent")
    first, second = inline_job
    records = [Path(engine.load(f).command[engine.load(f).command.index("--out") + 1]) for f in (first, second)]
    assert records[0] != records[1] and all(r.parent == root / "signal_records" for r in records)
    assert "AUDIT draft FIRST" in records[0].read_text() and "AUDIT draft SECOND" in records[1].read_text()
    for folder, record in zip((first, second), records):
        ledger = [json.loads(x) for x in (folder / "paid.jsonl").read_text().splitlines()]
        assert [r["state"] for r in ledger] == ["opened", "reserved", "received", "settled"]
        assert ledger[0]["attempt"] == engine.load(folder).attempt        # opened by its own run (DE-01)
        assert ledger[-1]["cost_usd"] == pytest.approx(cost)
        await user.open(page(root, folder))
        user.find(marker="primary_action").click()                      # "Check the draft record"
        await user.should_see("a DRAFT: not verified")
        assert parse_qs(urlsplit(user.back_history[-1]).query) == {"record": [str(record)]}     # its own file
    records[0].write_text(records[1].read_text())                        # the first file replaced afterwards
    await user.open(page(root, first))
    await user.should_see("Finished, but its draft record has been replaced")
    await user.should_not_see("Check the draft record")
    assert len(provider["anthropic"].requests) == 2


async def test_an_existing_file_is_refused_before_anything_is_paid(user: User, tmp_path, provider, inline_job,  # noqa: F811
                                                                    monkeypatch):
    """WA-05: an explicit output that exists is refused by the form, by a batch (two requests writing one file) and by
    the command itself, each before a paid request."""
    from adroit.orchestrator import cli
    from adroit.retrieval import corpus
    from adroit.ui import batch, forms
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    monkeypatch.setattr(corpus, "fetch_arxiv_pdf_text", lambda arxiv: "a synthetic paper")
    existing = tmp_path / "mine.yaml"
    existing.write_text("name: kept\n")
    await draft_from_paper(user, str(existing))
    await user.should_see("already exists")
    assert not inline_job and existing.read_text() == "name: kept\n"

    with pytest.raises(SystemExit) as stopped:
        cli.app(["anomaly", "draft", "--arxiv", PAPER, "--out", str(existing), "--budget", "0.5"])
    assert stopped.value.code == 2 and existing.read_text() == "name: kept\n"

    shared = tmp_path / "shared.yaml"
    command = forms.anomaly_draft_command(PAPER, shared, 0.5)
    batch.add_to_draft(root, command, root / "a", "draft a", 0.5)
    with pytest.raises(ValueError, match="already writes"):
        batch.add_to_draft(root, command, root / "b", "draft b", 0.5)
    shared.write_text("written since\n")                                 # written after the request was added
    with pytest.raises(ValueError, match="already exists"):
        batch.start(root, "two drafts", 1.0, popen=lambda *a, **k: SimpleNamespace(pid=1))
    assert not provider["anthropic"].requests


# --- WA-03: a stop after an unsettled reservation is never shown as spent ----------------------------------------

class _Dropped(Exception):
    """A transport failure after dispatch: the bill is not known."""


def _stopped_after_an_uncertain_request(out: Path) -> dict:
    """A paid command whose first request fails after dispatch (its reservation kept) and whose second cannot fit the
    cap: the budget stop's record, through the real budget boundary."""
    import typer

    from adroit.agents.anomaly import AnomalyDraft
    from adroit.orchestrator import cli

    def create(**request):
        raise _Dropped("connection reset after the request was sent")

    @cli._budget_boundary
    def command(out: str, budget: float, model: str) -> None:
        inner = llm_module.LLMClient(model=model, client=SimpleNamespace(messages=SimpleNamespace(create=create)))
        llm = llm_module.BudgetedLLMClient(inner, dollar_budget=budget, ledger_path=Path(out) / "paid.jsonl")
        with pytest.raises(_Dropped):
            llm.complete_structured("draft", [{"role": "user", "content": "a paper"}], AnomalyDraft)
        llm.dollar_budget = llm.account.committed() * 1.5               # the next request cannot fit
        llm.complete_structured("draft", [{"role": "user", "content": "a paper"}], AnomalyDraft)

    with pytest.raises(typer.Exit):
        command(out=str(out), budget=1.0, model="claude-opus-5-5")
    return json.loads((out / "result.json").read_text())


def test_a_stop_after_an_uncertain_request_shows_its_reservation_as_reserved_not_spent(tmp_path, monkeypatch):
    """WA-03: a stop that had $0.40 committed, none of it settled, had shown "This run: $0.4000". The stop record and
    the run's own ledger keep the settled and the reserved apart, and the page says which is which; a stop record from
    before the split says "up to", committed."""
    from adroit.ui import outcomes
    folder = tmp_path / "job"
    folder.mkdir()
    monkeypatch.setenv("ADROIT_JOB_FOLDER", str(folder))
    stop = _stopped_after_an_uncertain_request(folder)
    reserved = stop["committed_usd"]
    assert reserved > 0 and stop["settled_usd"] == 0 and stop["uncertain_usd"] == pytest.approx(reserved)
    job = engine.Job(title="idea", kind="idea", command=["idea", "--text", "x", "--budget", "1", "--out", str(folder)],
                     folder=str(folder), status="budget_stopped", returncode=3)
    expected = f"This run: $0.0000 settled, and up to {outcomes.usd(reserved)} reserved whose bill is not yet known"
    assert outcomes.cost_lines(outcomes.cost(folder, job))[0] == expected       # from the run's own ledger
    (folder / "paid.jsonl").unlink()
    assert outcomes.cost_lines(outcomes.cost(folder, job))[0] == expected       # from the stop record's split
    (folder / "result.json").write_text(json.dumps({"status": "budget_stopped", "committed_usd": reserved}))
    line = outcomes.cost_lines(outcomes.cost(folder, job))[0]
    assert line.startswith(f"This run: up to {outcomes.usd(reserved)} committed") and "together" in line


def test_a_whole_cent_spent_line_is_not_read_as_no_request(tmp_path):
    """WA-03: a run from before its own ledger whose log says "spent $0.00" may have spent under half a cent, and a
    request whose bill is unknown is not in that line: its cost is not available, never "no paid request was sent";
    "spent $0.12" is about $0.12. A paid run whose ledger holds no request did send none."""
    from adroit.ui import outcomes
    command = ["anomaly", "draft", "--arxiv", PAPER, "--out", str(tmp_path / "d.yaml"), "--budget", "0.5"]
    cases = {"zero": "written to d.yaml (a draft); spent $0.00\n", "cents": "written to d.yaml; spent $0.12\n"}
    lines = {}
    for name, log in cases.items():
        folder = tmp_path / name
        folder.mkdir()
        (folder / engine.LOG).write_text(log)
        job = engine.Job(title=name, kind="anomaly", command=command, folder=str(folder), status="completed")
        lines[name] = outcomes.cost_lines(outcomes.cost(folder, job))[0]
    assert lines["zero"].startswith("This run: not available") and "no paid request" not in lines["zero"]
    assert lines["cents"] == "This run: about $0.1200 (rounded to the cent in its log)"
    (tmp_path / "zero" / "paid.jsonl").write_text("")
    job = engine.Job(title="z", kind="anomaly", command=command, folder=str(tmp_path / "zero"), status="completed")
    assert outcomes.cost_lines(outcomes.cost(tmp_path / "zero", job))[0] == "This run: $0 (no paid request was sent)"


async def test_a_sub_cent_study_shows_its_cost_on_its_card_and_in_the_list(user: User, tmp_path, monkeypatch):
    """WA-03's class on the study pages: a study whose run settled $0.0024 had read "cost $0.00" on its card and
    "$0.00" in the Studies list. The card reads the run's own ledger, the list the study record, to $0.0001."""
    from adroit.orchestrator import studies
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder = root / "derive_run"
    folder.mkdir()
    engine.save(engine.Job(title="derive", kind="lagrangian", command=["lagrangian", "--derive", "--description", "x",
                                                                        "--budget", "1", "--out", str(folder)],
                           folder=str(folder), status="completed"))
    rows = [{"id": "r", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.25},
            {"id": "r", "state": "settled", "cost_usd": 0.0024}]
    (folder / "paid.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    studies.record(folder, "lagrangian", "a derived model", cost_usd=0.0024)
    await user.open("/study?path=derive_run")
    await user.should_see("cost: $0.0024")
    await user.should_not_see("cost $0.00")
    await user.open("/studies")
    await user.should_see("$0.0024")


# --- WA-04: a missing key is said, before anything is reserved or sent -------------------------------------------

@pytest.fixture
def no_keys(monkeypatch):
    """Neither provider's key, and a transport that fails the test if it is ever called."""
    from adroit.core.config import get_settings
    for settings in {id(s): s for s in (get_settings(), llm_module.get_settings())}.values():   # conftest's copy too
        monkeypatch.setattr(settings, "anthropic_api_key", SecretStr(""))
        monkeypatch.setattr(settings, "openai_api_key", SecretStr(""))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sent: list[dict] = []

    class Anthropic(llm_module.LLMClient):
        def __init__(self, **kw):
            super().__init__(**kw)
            self._client = SimpleNamespace(messages=SimpleNamespace(create=lambda **r: sent.append(r)))

    class OpenAI(llm_module.OpenAIClient):
        def __init__(self, **kw):
            super().__init__(**kw)
            self._client = SimpleNamespace(responses=SimpleNamespace(create=lambda **r: sent.append(r)))

    monkeypatch.setattr(llm_module, "LLMClient", Anthropic)
    monkeypatch.setattr(llm_module, "OpenAIClient", OpenAI)
    return sent


@pytest.mark.parametrize("provider_name", ["anthropic", "openai"])
def test_a_missing_key_reserves_nothing_and_sends_nothing(tmp_path, no_keys, provider_name):
    """WA-04: an absent key had reached the SDK, whose TypeError was journalled as a request whose bill is unknown,
    its $0.25 reservation kept. It is refused before the reservation, with the variable to set and no key shown."""
    from adroit.agents.anomaly import AnomalyDraft
    inner = llm_module.client_for("gpt-5.6-sol" if provider_name == "openai" else "claude-opus-5-5")
    ledger = tmp_path / "paid.jsonl"
    llm = llm_module.BudgetedLLMClient(inner, dollar_budget=0.5, ledger_path=ledger)
    with pytest.raises(llm_module.MissingCredentials) as refused:
        llm.complete_structured("draft", [{"role": "user", "content": "a paper"}], AnomalyDraft)
    variable = "OPENAI_API_KEY" if provider_name == "openai" else "ANTHROPIC_API_KEY"
    assert variable in str(refused.value) and "nothing was sent and nothing was reserved" in str(refused.value)
    assert not no_keys and llm.account.committed() == 0 and not ledger.exists()


def test_a_command_without_a_key_says_what_to_set(tmp_path, no_keys, capsys):
    """WA-04 at the command line: one line naming the variable, exit status 2, no traceback, nothing sent."""
    from adroit.orchestrator import cli
    with pytest.raises(SystemExit) as stopped:
        cli.app(["idea", "--text", "a Z2-odd real scalar", "--budget", "0.5", "--out", str(tmp_path / "idea")])
    err = capsys.readouterr().err
    assert stopped.value.code == 2 and "ANTHROPIC_API_KEY" in err and "Traceback" not in err
    assert "TypeError" not in err and not no_keys


@pytest.mark.parametrize("provider_name", ["anthropic", "openai"])
async def test_an_intake_without_a_key_says_so_and_keeps_no_reservation(user: User, tmp_path, no_keys, inline,  # noqa: F811
                                                                        provider_name):
    """WA-04 in the workbench: a fresh install without keys, an intake started with each provider and $1 approved.
    The page says which key to set; the session's ledger holds no reservation; this run sent nothing."""
    from adroit.orchestrator.model_intake import Intake
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    await start_intake(user, provider_name)
    name, variable = {"anthropic": ("Anthropic", "ANTHROPIC_API_KEY"), "openai": ("OpenAI", "OPENAI_API_KEY")}[provider_name]
    await user.should_see(f"no {name} API key")
    await user.should_see(variable)
    await user.should_see("This run: $0 (no paid request was sent)")
    await user.should_not_see("TypeError")
    session = engine.load(inline[0]).command[2]
    assert not Intake().requests(session) and not no_keys


# --- WA-01: a confirmed anomaly passes the setup check its continuation runs --------------------------------------

def _confirmed(tmp_path) -> str:
    """A synthetic event source imported, interpreted (scripted) and confirmed: its ``anomaly:`` reference."""
    from adroit.agents.llm import FakeLLMClient
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator.anomaly_intake import confirm, interpretation
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    from tests.experimental_extraction_fixtures import TEXT, answer
    catalog = ExperimentalCatalog()
    file = tmp_path / "source.txt"
    file.write_text(TEXT)
    revision = catalog.import_files([file], "Synthetic event source")
    service = ExperimentalExtraction(catalog)
    scope = service.start(revision.reference, 1, vision=False)
    step = service.step(scope.session_id, llm=FakeLLMClient([answer(revision.sources[0].sha256)]))
    found = interpretation(step.output_revision, "signal", catalog)
    return confirm(step.output_revision, "signal", found.interpretation_sha256, "Reviewer", confirmed=True,
                   accepted_assumptions=found.assumptions, catalog=catalog).reference


async def test_a_confirmed_anomaly_passes_the_setup_check_of_signal_best_fits(user: User, tmp_path):
    """WA-01: import → interpret → confirm → Signal best fits had been blocked by the setup check ("not a known search
    or record") although the run loads the reference. The check resolves it as the run does and shows its review; a
    reference that does not resolve stays blocked, with why."""
    from adroit.experiments.registry import load_module
    from adroit.orchestrator.setup_check import check_signal
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    reference = _confirmed(tmp_path)
    name = load_module(reference).info.name
    check = check_signal(reference, 0, 1000)
    assert not check.blocked
    assert any(f"signal search: {name} (confirmed anomaly interpretation)" in i.message for i in check.items)
    assert any("not yet reviewed" in i.message for i in check.items)
    await user.open(f"/new/track2?anomaly={reference}")
    user.find(marker="check_setup").click()
    await user.should_see("(confirmed anomaly interpretation)")
    await user.should_not_see("is not a known search or record")
    other = check_signal("anomaly:" + "0" * 64, 0, 1000)
    assert other.blocked and any("cannot be used" in i.message for i in other.items)
    assert check_signal("record:" + str(tmp_path / "missing.yaml"), 0, 1000).blocked


# --- WA-02: the table's statistic is the compatibility p; the global p is the search's ----------------------------

def _signal_study(folder: Path) -> None:
    """A saved Path 2 study whose candidates are compatible with the null searches (p ≈ 1) and whose search has a
    global p of 0.003: the two must not be confused."""
    from adroit.inference.dm_tournament import NULL, Entry, TournamentResult
    from adroit.orchestrator import studies
    from adroit.orchestrator.signal import SignalRequest, SignalResult
    entries = [Entry(label="scalar @ 10", z_signal=3.03, z_joint=3.0, chi2_pg=0.0, p_pg=1.0, aic=-7.0, class_id=0),
               Entry(label="scalar @ 20", z_signal=2.26, z_joint=2.2, chi2_pg=1e-9, p_pg=0.9999999663716803,
                     aic=-2.84, class_id=1),
               Entry(label=NULL, z_signal=0.0, z_joint=0.0, chi2_pg=0.0, p_pg=1.0, aic=0.0)]
    tournament = TournamentResult(ranking=entries, indistinguishable=["scalar @ 10"], classes_in_top_set=[0],
                                  signal_fit_leader="scalar @ 10", null_rank=3)
    result = SignalResult(request=SignalRequest(experiment="CDMS II Si (2013)"), fits=[],
                          classes={"scalar @ 10": 0, "scalar @ 20": 1}, n_classes=2, max_local_z=3.03,
                          global_p_toys=0.003, global_p_closed_form=None, global_toys=1000,
                          global_z=2.7477813854449926, global_method="1000 background-only toys", combinations=[],
                          tournament=tournament, separations=[])
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(result.model_dump_json())
    studies.record(folder, "signal", "Signal fits: CDMS II Si")


async def test_the_signal_study_names_its_statistics_for_what_they_are(user: User, tmp_path):
    """WA-02: the study's table headed each candidate's compatibility p (p ≈ 1) "global p", beside a saved global p of
    0.003. The table now heads it as the compatibility with the null searches, and the global significance is stated
    once, for the search; reopened through Studies, the same."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _signal_study(root / "signal")
    for opening in ("/study?path=signal", "/studies"):
        await user.open(opening)
        if opening == "/studies":
            user.find("Signal fits: CDMS II Si").click()
        await user.should_see("Global significance of the largest local excess, over every candidate tried: 2.75σ "
                              "(p = 0.003, 1000 background-only toys)")
        table = user.find(kind=ui.table).elements.pop()
        headings = [c["label"] for c in table.columns]
        assert "compatibility with the null searches (p of χ²_PG)" in headings and "global p" not in headings
        assert [r["p_pg"] for r in table.rows] == ["1", "1"]


# --- WA-06: a record that exists is not said to be missing -------------------------------------------------------

def test_no_library_entry_says_a_record_it_uses_is_not_yet_a_record():
    """WA-06: the scalar singlet's page said DAMPE's line search was "not yet a record" while its study used the
    (unsigned) record dampe-2112.08860-lines."""
    from adroit.constraints.database import records
    from adroit.parameter_space.library import ENTRIES
    from adroit.parameter_space.searches import LINE_RECORDS
    ids = {r.id for r in records()}
    assert "dampe-2112.08860-lines" in ids and "dampe-2112.08860-lines" in LINE_RECORDS
    notes = [n for e in ENTRIES for n in e.not_computed]
    assert not [n for n in notes if "DAMPE" in n and "not yet a record" in n]


# --- WA-07: newest first, as the page says -------------------------------------------------------------------------

async def test_the_studies_page_lists_the_newest_study_first(user: User, tmp_path):
    """WA-07: the page said "newest first" and began with the oldest study. Root studies are newest first, each with
    its children beneath it in the order they were made."""
    from adroit.orchestrator import studies
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    made = {"oldest": "2026-10-23T23:04:00+00:00", "newest": "2026-10-24T00:02:00+00:00",
            "middle": "2026-10-23T23:30:00+01:00"}                       # 22:30 UTC: older than "oldest"
    for title, when in made.items():
        (root / title).mkdir()
        study = studies.record(root / title, "track1", title)
        studies.save(study.model_copy(update={"created": when}))
    (root / "oldest" / "children" / "child").mkdir(parents=True)
    studies.record(root / "oldest" / "children" / "child", "single_idea", "child", parent=root / "oldest")
    assert [s.title for _, s in studies.tree(root)] == ["newest", "oldest", "child", "middle"]
    await user.open("/studies")
    with user:
        shown = [e.text for e in ElementFilter(kind=ui.link) if e.text in (*made, "child")]
    assert shown == ["newest", "oldest", "child", "middle"]


# --- the promotion form: each child's size, as the command line takes it ----------------------------------------

async def test_the_promotion_form_sets_each_childs_size(user: User, tmp_path, monkeypatch):
    """The audit's bounded promotion could not be launched from the browser: the form did not expose the children's
    toys, grid or masses. It does, and the command receives them."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _signal_study(root / "signal")
    launched = []
    monkeypatch.setattr(engine, "launch", lambda command, folder, title, **kw: launched.append(command) or
                        SimpleNamespace(folder=str(folder)))
    await user.open("/study?path=signal")
    from adroit.orchestrator.single_idea import grid_range
    plane = user.find("each child's Track 1 plane: n × n").elements.pop()
    assert (plane.props["min"], plane.props["max"]) == grid_range() == (4, 60)   # no size a child refuses
    user.find("background-only simulations per child study").elements.pop().value = 500
    user.find("each child's Track 1 plane: n × n").elements.pop().value = 4
    user.find("masses per candidate").elements.pop().value = 2
    user.find("candidate or class").elements.pop().value = "scalar @ 10"
    user.find(kind=ui.button, content="Promote").click()
    command = launched.pop()
    assert command[command.index("--toys") + 1] == "500" and command[command.index("--grid") + 1] == "4"
    assert command[command.index("--mass-points") + 1] == "2"

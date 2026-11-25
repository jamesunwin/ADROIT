"""The command line: its commands write a result, a report, a study record and (Path 1) a plot."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adroit.evidence.bindings import binding, unbound
from adroit.orchestrator import cli, exclusion
from adroit.orchestrator import lagrangian as path1
from adroit.orchestrator import signal as path2


def test_only_the_pipelines_are_commands() -> None:
    names = {c.name or c.callback.__name__ for c in cli.app.registered_commands}
    assert names == {"exclude", "reassess", "signal", "lagrangian", "agents", "eval", "setup", "workbench", "idea", "track1",
                     "single-idea", "promote", "studies", "portals", "crosscheck", "native-coverage", "native-fit", "assist"}
    assert {g.name for g in cli.app.registered_groups} == {"anomaly", "records", "assist-session", "evidence", "theory", "models", "experiments","reanalyse",
                                                              "constraints", "fog", "ledger"}   # ledger: D-7's recovery


def test_exclude_writes_result_report_and_plot(tmp_path, monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(exclusion, "run", lambda request: seen.setdefault("r", request) and
                        exclusion.ExclusionResult(request=request,interaction_name="mock",per_module=[]))
    monkeypatch.setattr(exclusion, "report", lambda result: "the report")
    monkeypatch.setattr(exclusion, "plot", lambda result, path: path.write_text("png"))
    out = CliRunner().invoke(cli.app, ["exclude", "O1", "--values", "c1_s=1e-6",
                                       "--masses", "10,100", "--out", str(tmp_path)])
    assert out.exit_code == 0, out.output
    assert seen["r"].masses_gev == [10.0, 100.0] and seen["r"].values == {"c1_s": 1e-6}
    assert {p.name for p in tmp_path.iterdir()} == {"result.json", "report.md", "exclusion.png", "study.json",
                                                "result.evidence.json", ".study.lock"}    # its publication lock (DE-02)


def test_signal_writes_result_and_report(tmp_path, monkeypatch) -> None:
    seen = {}
    from adroit.inference.dm_tournament import run as tournament
    monkeypatch.setattr(path2, "run", lambda request: seen.setdefault("r", request) and
        path2.SignalResult(request=request,fits=[],classes={},n_classes=0,max_local_z=0,
            global_p_toys=1,global_p_closed_form=None,global_z=0,combinations=[],
            tournament=tournament([]),separations=[]))
    monkeypatch.setattr(path2, "report", lambda result: "the report")
    out = CliRunner().invoke(cli.app, ["signal", "--experiment", "LZ extended window (2026)",
                                       "--null", "DEAP-3600 (2019)", "--toys", "10", "--out", str(tmp_path)])
    assert out.exit_code == 0, out.output
    assert seen["r"].null_modules == ["DEAP-3600 (2019)"] and seen["r"].toys == 10
    assert seen["r"].experiment == "LZ extended window (2026)"
    text=(tmp_path / "report.md").read_text()
    assert unbound(text).rstrip("\n").endswith("the report") and "Calculation started (UTC)" in text
    assert binding(text).result_sha256 == sha256((tmp_path / "result.json").read_bytes()).hexdigest()  # CY-03
    assert (tmp_path / "result.evidence.json").is_file()


def test_lagrangian_reads_the_model_file(tmp_path, monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(path1, "run", lambda request, *clients: seen.setdefault("r", request)
                        and path1.LagrangianResult(request=request))     # a real result: its evidence is saved (Rep-2)
    monkeypatch.setattr(path1, "report", lambda result: "the report")
    model = tmp_path / "toy.yaml"
    model.write_text("masses_gev: [50]\nmodules: [DEAP-3600 (2019)]\n")
    out = CliRunner().invoke(cli.app, ["lagrangian", str(model), "--out", str(tmp_path / "out")])
    assert out.exit_code == 0, out.output
    assert seen["r"].masses_gev == [50.0] and not seen["r"].use_language_models
    text=(tmp_path / "out" / "report.md").read_text()
    assert unbound(text).rstrip("\n").endswith("the report") and "Report generated (UTC)" in text
    assert binding(text).result_sha256 == sha256((tmp_path / "out" / "result.json").read_bytes()).hexdigest()


def test_agents_runs_on_a_path1_result(tmp_path, monkeypatch) -> None:
    from adroit.agents import llm
    from adroit.orchestrator import agents as dm9
    seen = {}
    monkeypatch.setattr(llm, "LLMClient", lambda **kw: llm.FakeLLMClient())
    monkeypatch.setitem(dm9.RUNNERS, "lagrangian", lambda result, client, request, tools: seen.setdefault("r", result)
                        and dm9.AgentResult(subject="x"))
    source = tmp_path / "result.json"
    source.write_text(path1.LagrangianResult(request=path1.LagrangianRequest()).model_dump_json())
    out = CliRunner().invoke(cli.app, ["agents", str(source), "--budget", "1", "--out", str(tmp_path / "o")])
    assert out.exit_code == 0, out.output
    assert (tmp_path / "o" / "report.md").exists() and "spent $0.00" in out.output


def test_paid_command_saves_budget_stop_in_requested_output(tmp_path, monkeypatch) -> None:
    import json
    from adroit.agents import llm
    from adroit.orchestrator import agents as dm9
    monkeypatch.setattr(llm, "LLMClient", lambda **kw: llm.FakeLLMClient())
    def stop(*args, **kwargs):
        error = llm.BudgetExceeded(.1, .25, .2)
        error.ledger_path = str(tmp_path / "paid-answers.jsonl")
        raise error
    monkeypatch.setitem(dm9.RUNNERS, "lagrangian", stop)
    source = tmp_path / "result.json"
    source.write_text(path1.LagrangianResult(request=path1.LagrangianRequest()).model_dump_json())
    out = CliRunner().invoke(cli.app, ["agents", str(source), "--budget", ".25", "--out", str(tmp_path / "o")])
    assert out.exit_code == 3, out.output
    result = json.loads((tmp_path / "o/result.json").read_text())
    assert result["status"] == "budget_stopped" and result["next_request_reservation_usd"] == .2
    assert result["paid_response_ledger"].endswith("paid-answers.jsonl")
    assert "before dispatch" in (tmp_path / "o/report.md").read_text()


def _toy_suite():
    from adroit.evaluation.core import Case, CaseResult, Suite
    return Suite(name="toy", description="toy",
                 cases=lambda: [Case(suite="toy", id=f"c{i}") for i in range(20)],
                 run_case=lambda c: CaseResult(case_id=c.id, passed=True),
                 summarise=lambda results, cases: {"cases": len(results)})


def test_eval_runs_the_development_half_of_a_suite(tmp_path, monkeypatch) -> None:
    from adroit.evaluation import core, suites
    monkeypatch.setattr(core, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(core, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(suites, "suites", lambda: {"toy": _toy_suite()})
    out = CliRunner().invoke(cli.app, ["eval", "toy", "--limit", "3", "--out", str(tmp_path / "results")])
    assert out.exit_code == 0, out.output
    assert "the development half" in out.output and "| cases | 3 |" in out.output
    assert (tmp_path / "results" / "toy.jsonl").exists() and not (tmp_path / "ledger.jsonl").exists()


def test_eval_refuses_an_unknown_suite_and_a_held_out_run_without_reason(tmp_path, monkeypatch) -> None:
    from adroit.evaluation import core, suites
    monkeypatch.setattr(core, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(core, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(suites, "suites", lambda: {"toy": _toy_suite()})
    assert CliRunner().invoke(cli.app, ["eval", "nonsense"]).exit_code != 0
    out = CliRunner().invoke(cli.app, ["eval", "toy", "--held-out"])
    assert out.exit_code != 0 and not (tmp_path / "ledger.jsonl").exists()


@pytest.mark.needs("directdm")
def test_lagrangian_derive_runs_the_deriver_and_the_checker_under_one_cap(tmp_path, monkeypatch) -> None:
    """R7 item 8: DM8's two-model coefficient derivation from the command line, under the budget gate."""
    import yaml
    from adroit.agents import llm
    from adroit.library.interactions.derivation import Derivation
    data = yaml.safe_load(Path("docs/dm8/majorana_scalar.yaml").read_text())
    derivation = Derivation.model_validate(data.pop("derivation"))
    model = tmp_path / "model.yaml"
    model.write_text(yaml.safe_dump({**data, "run_exclusion": False}, allow_unicode=True))
    made = {}

    def fake(**kw):
        made[kw["model"]] = llm.FakeLLMClient([derivation], model=kw["model"])
        return made[kw["model"]]
    monkeypatch.setattr(llm, "LLMClient", fake)
    monkeypatch.setattr(llm, "OpenAIClient", fake)
    out = CliRunner().invoke(cli.app, ["lagrangian", str(model), "--derive", "--budget", "1", "--out", str(tmp_path / "o")])
    assert out.exit_code == 0, out.output
    assert set(made) == {"claude-opus-5-5", "gpt-5.6-sol"} and all(c.call_count == 1 for c in made.values())
    assert "Opt-in paid command: claude-opus-5-5; hard cap $1.00" in out.output and "checker: gpt-5.6-sol" in out.output
    result = path1.LagrangianResult.model_validate_json((tmp_path / "o" / "result.json").read_text())
    assert result.request.use_language_models and result.comparison is not None and result.comparison.agree
    assert result.status == "complete"


def test_lagrangian_derive_refuses_a_request_without_its_budget_or_its_model(tmp_path, monkeypatch) -> None:
    """R7 item 8's refusals, which need no tool (B20-08: the derivation above needs DirectDM); none sends a request."""
    import yaml
    from adroit.agents import llm
    made = []

    def fake(**kw):
        made.append(llm.FakeLLMClient(model=kw["model"]))
        return made[-1]
    monkeypatch.setattr(llm, "LLMClient", fake)
    monkeypatch.setattr(llm, "OpenAIClient", fake)
    data = yaml.safe_load(Path("docs/dm8/majorana_scalar.yaml").read_text())
    data.pop("derivation")
    model = tmp_path / "model.yaml"
    model.write_text(yaml.safe_dump({**data, "run_exclusion": False}, allow_unicode=True))
    for bad in ([str(model), "--derive"],                                      # no budget
                [str(model), "--description", "words"],                       # words need --derive
                [str(model), "--derive", "--budget", "1", "--description", "words"],   # MODEL or words, not both
                ["--derive", "--budget", "1"]):                                 # neither
        assert CliRunner().invoke(cli.app, ["lagrangian", *bad]).exit_code == 2
    with_derivation = tmp_path / "derived.yaml"
    with_derivation.write_text(Path("docs/dm8/majorana_scalar.yaml").read_text())
    refused = CliRunner().invoke(cli.app, ["lagrangian", str(with_derivation), "--derive", "--budget", "1"])
    assert refused.exit_code == 2 and "already has a derivation" in refused.output
    assert all(c.call_count == 0 for c in made)


def test_records_list_ends_with_the_verified_count() -> None:
    """R9's gate: `adroit records list` shows the verified count, and unverified records stay labelled."""
    from adroit.constraints import database
    out = CliRunner().invoke(cli.app, ["records", "list"])
    records = database.records()
    verified = sum(r.usable for r in records)
    assert out.exit_code == 0
    assert out.output.rstrip().endswith("unless a run asks for --unverified).")
    assert f"Verified: {verified} of {len(records)} records; {len(records) - verified} await" in out.output
    assert out.output.count("AWAITS VERIFICATION") == len(records) - verified


def test_a_missing_input_is_one_line_with_its_setup_command(monkeypatch, capsys) -> None:
    """The release audit's PR23-02 (2026-10-23): a fresh install without a data release or DirectDM showed a full
    traceback. The command ends with the missing item and the setup command that supplies it, exit status 1."""
    from adroit.external import fetch
    monkeypatch.setattr(fetch, "locate", lambda *args, **kwargs: None)
    for args, words in ((["signal", "--experiment", "CDMSlite Run 2", "--toys", "10"],
                         "adroit setup --fetch --only 'CDMSlite Run 2 data release (arXiv:1707.01632)'"),
                        (["lagrangian", "docs/dm8/majorana_scalar.yaml"], "adroit setup --fetch --only 'DirectDM'")):
        with pytest.raises(SystemExit) as stopped:
            cli.app(args)
        err = capsys.readouterr().err
        assert stopped.value.code == 1 and words in err and "Traceback" not in err


def test_the_arxiv_search_is_asked_for_not_assumed() -> None:
    """The release audit's PR23-03 (2026-10-23): Track 1, the single-idea study and promoted children searched arXiv
    unless told not to (a network request without the user's choice). It is made only when asked: --literature on the
    command line, a ticked box in the workbench (unticked by default)."""
    import typer

    from adroit.orchestrator import single_idea, track1
    from adroit.ui import forms
    assert track1.Track1Request.model_fields["literature"].default is False
    assert single_idea.SingleIdeaRequest.model_fields["literature"].default is False
    commands = typer.main.get_command(cli.app).commands
    for name in ("track1", "single-idea", "promote"):
        option = next(p for p in commands[name].params if p.name == "literature")
        legacy = next(p for p in commands[name].params if p.name == "no_literature")
        assert option.default is False and option.opts == ["--literature"] and legacy.hidden
    assert "--literature" not in forms.track1_command(Path("m.yaml"), Path("out"))
    assert "--literature" in forms.track1_command(Path("m.yaml"), Path("out"), literature=True)
    assert "--literature" not in forms.portal_command("higgs_portal_scalar", Path("out"))


def test_a_budget_stop_of_a_file_output_leaves_the_file_path_free(tmp_path) -> None:
    """The workbench fix's inventory (2026-10-23): a budget stop wrote its partial artifact into the command's --out
    as a folder, and for ``anomaly draft`` that is the YAML record's own path, which then could not be written. The
    stop goes beside it; a folder output keeps it."""
    from adroit.agents.llm import BudgetExceeded

    import typer

    def paid(out=None):
        error = BudgetExceeded(spent=0.4, budget=0.5, required=0.2)
        error.ledger_path = str(tmp_path / "paid.jsonl")
        raise error
    guarded = cli._budget_boundary(paid)
    for out, folder in ((tmp_path / "draft_1304.4279.yaml", tmp_path / "draft_1304.4279_budget_stop"),
                        (tmp_path / "study", tmp_path / "study")):
        with pytest.raises(typer.Exit):
            guarded(out=out)
        assert (folder / "result.json").is_file()
    assert not (tmp_path / "draft_1304.4279.yaml").exists()


@pytest.mark.parametrize("grid", ["2", "61"])
def test_promote_refuses_a_plane_its_children_would_refuse(tmp_path, grid):
    """The release layer (2026-10-25): a 2 × 2 plane passed the parent and failed in each child
    (``SingleIdeaRequest.grid``: 4 to 60). It is refused before anything runs."""
    result = CliRunner().invoke(cli.app, ["promote", str(tmp_path), "class:0", "--grid", grid])
    words = " ".join(result.output.replace("│", " ").split())          # the error box wraps its line
    assert result.exit_code == 2 and "between 4 × 4 and 60 × 60" in words

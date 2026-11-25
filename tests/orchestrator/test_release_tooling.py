"""R0: honest tooling. Gate and validation scripts write outside the tracked receipts unless told otherwise and
exit non-zero on a failure; budget stops exit 3; stopped commands say why; the release runner keeps a receipt."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from adroit.agents.budget import BudgetExceeded
from adroit.core import receipts
from adroit.orchestrator import cli, stops

ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _docs_digest() -> str:
    """A digest of every tracked file under docs/, to show that a gate run left them alone."""
    files = subprocess.run(["git", "ls-files", "docs"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    digest = hashlib.sha256()
    for name in sorted(files):
        path = ROOT / name
        digest.update(name.encode() + (path.read_bytes() if path.is_file() else b"<missing>"))
    return digest.hexdigest()


def _gate(script: str, patches: str, argv: list[str]) -> subprocess.CompletedProcess:
    """Run a gate script's main() in a fresh interpreter with its parts replaced by ``patches``."""
    source = f'''import importlib.util,sys
from pathlib import Path
s=importlib.util.spec_from_file_location("gate",{str(ROOT / script)!r})
g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
{patches}
sys.argv={["gate", *argv]!r}
sys.exit(g.main())
'''
    return subprocess.run([sys.executable, "-c", source], capture_output=True, text=True, cwd=ROOT)


# --- the shared receipts helper ---------------------------------------------------------------------------

def test_gate_output_defaults_to_a_new_runs_folder_and_honours_out(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(receipts, "get_settings", lambda: SimpleNamespace(runs_dir=tmp_path / "runs"))
    first, second = receipts.gate_output("dm13"), receipts.gate_output("dm13")
    assert first.parent == tmp_path / "runs" / "gates" / "dm13" and first.is_dir() and first != second
    assert receipts.gate_output("dm13", tmp_path / "mine") == tmp_path / "mine"


def test_validation_table_fails_none_nan_and_out_of_range() -> None:
    rows = [("ok", 1.0, 0.9, 1.1, "r"), ("none", None, 0.0, 1.0, "r"), ("nan", math.nan, 0.0, 1.0, "r"),
            ("high", 2.0, 0.0, 1.0, "r"), ("inf range", 5.0, 1.0, math.inf, "r")]
    table, failed = receipts.validation_table(rows)
    assert failed == 3 and table.count("| FAIL |") == 3 and "| none |" in table
    assert receipts.exit_code(True) == 0 and receipts.exit_code(False) == 1 and receipts.BUDGET_STOPPED == 3


# --- gate scripts: an injected failure exits non-zero and writes only to --out ------------------------------

GATES = {
    "dm8": ("docs/dm8/gate.py", 'g.dry_run=lambda:("injected\\n",False)', ["--dry-run"], "gate_dry_run.txt"),
    "dm9": ("docs/dm9/gate.py", 'g.dry_run=lambda:("injected\\n",False)', ["--dry-run"], "gate_dry_run.txt"),
    "dm12": ("docs/dm12/gate.py", "g.part_a=g.part_b=g.part_c=lambda:[]\ng.part_d=lambda llm:[]\n"
             "g.scripted=lambda:None\ng.verdict=lambda a,b,c,d:(False,'- injected: FAIL')",
             ["--dry-run"], "gate_dry_run.md"),
    "dm13": ("docs/dm13/gate.py", 'g.g1=lambda:[{"pass":False}]\ng.g2=lambda:[{"pass":True}]\n'
             'g.g4=lambda folder:[{"pass":True}]\ng.g3=lambda folder:{"test":{"pass":True}}', [], "gate.md"),
    "dm14": ("docs/dm14/gate.py", 'g.g1=lambda folder:{"case":{"pass":False}}\ng.g2=lambda:{"pass":True}\n'
             'g.g4=lambda folder:{"pass":True}\ng.g3=lambda folder:{"case":{"pass":True}}', [], "gate.md"),
    "dm15": ("docs/dm15/gate.py", 'g.tests=lambda spec:{"pass":False}\ng.workspace=lambda root:root\n'
             'g.g5=lambda root:{"pass":True}', [], "gate.md"),
    "portals": ("docs/portals/gate.py", 'g.p1=g.p2=g.p3=lambda:{"pass":True}\ng.p4=lambda folder:{"pass":False}',
                [], "gate.md"),
    "dm7": ("docs/dm7/relic_gate.py",
            "class Pool:\n    def __init__(self,**k): pass\n    def __enter__(self): return self\n"
            "    def __exit__(self,*a): return False\n    def map(self,f,tasks,chunksize=1): return map(f,tasks)\n"
            "g.ProcessPoolExecutor=Pool\n"
            "g.evaluate=lambda t:{'model':t[0],'m_med':t[1],'m_dm':t[2],'omega_h2':1.0,'shifted':{},"
            "'within_factor':False,'contour_within_3pct':False,'passes':False}", [], "relic_gate.txt"),
}


@pytest.mark.parametrize("gate", sorted(GATES))
def test_gate_script_exits_nonzero_on_an_injected_failure_and_writes_only_to_out(gate, tmp_path) -> None:
    script, patches, argv, written = GATES[gate]
    before = _docs_digest()
    process = _gate(script, patches, [*argv, "--out", str(tmp_path)])
    assert process.returncode == 1, process.stdout + process.stderr
    assert (tmp_path / written).is_file()
    assert _docs_digest() == before


def test_dm8_and_dm9_dry_runs_pass_only_when_every_part_behaves(tmp_path) -> None:
    ok = _gate("docs/dm8/gate.py", 'g.dry_run=lambda:("fine\\n",True)', ["--dry-run", "--out", str(tmp_path)])
    assert ok.returncode == 0 and (tmp_path / "gate_dry_run.txt").read_text() == "fine\n"
    gate = _load(ROOT / "docs/dm8/gate.py", "dm8_gate")
    assert gate.CONTROLS_PASS == (False, False, False, True)


def test_a_budget_stopped_live_gate_exits_3(tmp_path) -> None:
    process = _gate("docs/dm8/gate.py", 'g.live=lambda budget,deriver,checker,folder:("stopped\\n",3)',
                    ["--live", "--budget", "1", "--out", str(tmp_path)])
    assert process.returncode == 3
    dm12 = _gate("docs/dm12/gate.py", "g.part_a=g.part_b=g.part_c=lambda:[]\ng.scripted=lambda:None\n"
                 "g.part_d=lambda llm:[{'idea':'i','models':[],'textbook_found':False,'dropped':0,"
                 "'status':'budget_exhausted'}]\ng.verdict=lambda a,b,c,d:(False,'')",
                 ["--dry-run", "--out", str(tmp_path)])
    assert dm12.returncode == 3


def test_resuming_a_gate_needs_the_stopped_runs_folder() -> None:
    for script in ("docs/dm14/gate.py", "docs/portals/gate.py"):
        process = _gate(script, "", ["--resume"])
        assert process.returncode != 0 and "--resume needs --out" in process.stderr


def test_dm10_gate_writes_to_out_and_fails_while_rules_are_unmet(tmp_path, monkeypatch) -> None:
    from adroit.evaluation import core
    monkeypatch.setattr(core, "RESULTS", tmp_path / "empty_store")
    gate = _load(ROOT / "docs/dm10/gate.py", "dm10_gate")
    text, code = gate.main(tmp_path / "out")
    assert code == 1 and "not run" in text and (tmp_path / "out" / "gate.md").read_text() == text


def test_dm3_validation_writes_to_out_and_reports_a_lost_gate_comparison(tmp_path) -> None:
    tracked = [ROOT / "docs/dm3/validation_results.json", ROOT / "docs/dm3/validation_summary.txt",
               ROOT / "adroit/experiments/data/validated_ranges.yaml"]
    before = [p.read_bytes() for p in tracked]
    process = _gate("docs/dm3/validate_modules.py", "g.stored=lambda:[]\ng.STAGES={'none':lambda:[]}",
                    ["--only", "none", "--out", str(tmp_path)])
    assert process.returncode == 1 and "REGRESSION" in process.stdout
    assert {p.name for p in tmp_path.iterdir()} == {p.name for p in tracked}
    assert [p.read_bytes() for p in tracked] == before
    kept = _gate("docs/dm3/validate_modules.py", "g.STAGES={'none':lambda:[]}",
                 ["--only", "none", "--out", str(tmp_path / "kept")])
    assert kept.returncode == 0 and "no comparison lost" in kept.stdout


# --- validation scripts --------------------------------------------------------------------------------------

VALIDATIONS = {2: ["gates"], 3: ["gates"], 4: ["loop_gates", "line_gates", "production_gates"],
               5: ["monoh_gates"]}


@pytest.mark.parametrize("n", sorted(VALIDATIONS))
def test_validation_script_exits_nonzero_on_an_injected_failure(n, monkeypatch, capsys) -> None:
    script = _load(ROOT / f"scripts/validate_portal_library_{n}.py", f"validate_{n}")
    for name in VALIDATIONS[n]:
        monkeypatch.setattr(script, name, lambda: [("injected", 2.0, 0.0, 1.0, "test")])
    if n == 5:
        for name in ("monoz_gate", "dijet_gate", "zz_gate"):
            monkeypatch.setattr(script, name, lambda: ("fine", 1.0, 1.0, 1.0, "test"))
    assert script.main() == 1 and "FAIL" in capsys.readouterr().out
    for name in VALIDATIONS[n]:
        monkeypatch.setattr(script, name, lambda: [("fine", 1.0, 1.0, 1.0, "test")])
    assert script.main() == 0


# --- exit codes and messages of the command line -----------------------------------------------------------

def test_a_budget_stopped_command_exits_3_and_keeps_its_partial_record(tmp_path, monkeypatch) -> None:
    from adroit.agents import llm
    from adroit.orchestrator import agents as dm9
    from adroit.orchestrator import lagrangian as path1
    monkeypatch.setattr(llm, "LLMClient", lambda **kw: llm.FakeLLMClient())

    def stop(*args, **kwargs):
        raise BudgetExceeded(.1, .25, .2)
    monkeypatch.setitem(dm9.RUNNERS, "lagrangian", stop)
    source = tmp_path / "result.json"
    source.write_text(path1.LagrangianResult(request=path1.LagrangianRequest()).model_dump_json())
    out = CliRunner().invoke(cli.app, ["agents", str(source), "--budget", ".25", "--out", str(tmp_path / "o")])
    assert out.exit_code == receipts.BUDGET_STOPPED
    assert json.loads((tmp_path / "o/result.json").read_text())["status"] == "budget_stopped"


def test_anomaly_check_exits_nonzero_on_a_record_missing_a_required_field(tmp_path) -> None:
    import yaml
    from adroit.experiments import anomaly
    data = yaml.safe_load(anomaly.template())
    data.pop("resolution_kev")
    record = tmp_path / "draft.yaml"
    record.write_text(yaml.safe_dump(data))
    out = CliRunner().invoke(cli.app, ["anomaly", "check", str(record)])
    assert out.exit_code == 1 and "not a valid record yet" in out.output
    assert "- resolution_kev: not given yet; fill in the detector's energy resolution" in out.output
    assert "validation error" not in out.output and "pydantic" not in out.output


class _Extraction:
    def __init__(self, failure: Exception | None = None, bound: float = 0.1, trimmed: float = 0.08) -> None:
        self.failure, self.bound, self.trimmed, self.sent = failure, bound, trimmed, []
        self.budgets = SimpleNamespace(session=lambda session: SimpleNamespace(budget=0.6, model="claude-opus-5-5"))

    def preview(self, session, batch, instruction):
        return {"request_bound_usd": self.bound, "trimmed_request_bound_usd": self.trimmed,
                "budget": {"cap": 0.6, "spent": 0.27, "reserved_uncertain": 0.0, "remaining": 0.33}}

    def steps(self, session):
        return ["an earlier step"]

    def budget_owner(self, session):          # an extraction with its own cap (not a discovery session's shared one)
        return session

    def step(self, *args, **kwargs):
        self.sent.append(kwargs)
        raise self.failure


def test_experiments_extract_shows_why_it_stopped(monkeypatch) -> None:
    from adroit.orchestrator import experimental_extraction
    monkeypatch.setattr(experimental_extraction, "ExperimentalExtraction", lambda: _Extraction())
    out = CliRunner().invoke(cli.app, ["experiments", "extract", "s1", "--budget", "0.5"])
    assert out.exit_code == 2 and "supply the originally approved session budget" in out.output
    monkeypatch.setattr(experimental_extraction, "ExperimentalExtraction",
                        lambda: _Extraction(BudgetExceeded(0.27, 0.6, 0.436)))
    out = CliRunner().invoke(cli.app, ["experiments", "extract", "s1", "--budget", "0.6"])
    assert out.exit_code == 3 and "next request needs up to $0.436" in out.output
    assert "Opt-in paid command: claude-opus-5-5; hard cap $0.60" in out.output


def test_a_cap_that_cannot_cover_the_next_refinement_offers_a_raise_or_a_trim(monkeypatch) -> None:
    """Live check L6: a $0.60 session stopped with $0.27 spent because the next refinement reserved $0.436, and the
    only way on was a new session. Now the reservation is shown first and the options are named."""
    from adroit.orchestrator import experimental_extraction
    service = _Extraction(bound=0.436, trimmed=0.31)
    monkeypatch.setattr(experimental_extraction, "ExperimentalExtraction", lambda: service)
    out = CliRunner().invoke(cli.app, ["experiments", "extract", "s1", "--budget", "0.6", "--instruction", "x"])
    assert out.exit_code == 3 and not service.sent
    assert "next request: reserves up to $0.4360 ($0.3100 with --trim); $0.3300 of the $0.60 cap remains" in out.output
    assert "adroit experiments raise-cap s1 --budget 0.71 --confirmed" in out.output
    assert "(--trim): reserves up to $0.3100, fits the current cap" in out.output
    service = _Extraction(BudgetExceeded(0.27, 0.6, 0.2), bound=0.436, trimmed=0.3)
    monkeypatch.setattr(experimental_extraction, "ExperimentalExtraction", lambda: service)
    CliRunner().invoke(cli.app, ["experiments", "extract", "s1", "--budget", "0.6", "--instruction", "x", "--trim"])
    assert service.sent == [{"trimmed": True}]


def test_models_step_shows_why_it_stopped(monkeypatch) -> None:
    from adroit.orchestrator import catalog_cli
    service = SimpleNamespace(session=lambda session: SimpleNamespace(budget=0.6))
    monkeypatch.setattr(catalog_cli, "Intake", lambda: service)
    out = CliRunner().invoke(cli.app, ["models", "step", "s1", "--kind", "idea", "--text", "x", "--budget", "0.5"])
    assert out.exit_code == 2 and "originally approved session --budget" in out.output


def test_stop_messages_hide_provider_detail_but_show_our_own() -> None:
    message, code = stops.stop(ValueError("supply the budget"), "Extraction", "Kept.")
    assert code == 2 and "supply the budget" in message
    message, code = stops.stop(RuntimeError("provider echo: secret request body"), "Intake", "Kept.")
    assert code == 2 and "secret" not in message and "RuntimeError" in message
    error = BudgetExceeded(0.1, 0.2, 0.3)
    error.ledger_path = "paid.jsonl"
    message, code = stops.stop(error, "Intake", "Kept.")
    assert code == 3 and "paid.jsonl" in message


def test_eval_writes_development_runs_outside_the_tracked_store(tmp_path, monkeypatch) -> None:
    from adroit.evaluation import core, suites
    from adroit.evaluation.core import Case, CaseResult, Suite
    toy = Suite(name="toy", description="toy", cases=lambda: [Case(suite="toy", id=f"c{i}") for i in range(20)],
                run_case=lambda c: CaseResult(case_id=c.id, passed=True),
                summarise=lambda results, cases: {"cases": len(results)})
    monkeypatch.setattr(core, "RESULTS", tmp_path / "tracked")
    monkeypatch.setattr(core, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(suites, "suites", lambda: {"toy": toy})
    monkeypatch.setattr(cli, "_runs_dir", lambda: tmp_path / "runs")
    assert CliRunner().invoke(cli.app, ["eval", "toy", "--limit", "2"]).exit_code == 0
    assert (tmp_path / "runs" / "eval" / "toy.jsonl").is_file() and not (tmp_path / "tracked").exists()
    assert CliRunner().invoke(cli.app, ["eval", "toy", "--limit", "2", "--out", str(tmp_path / "s")]).exit_code == 0
    assert (tmp_path / "s" / "toy.jsonl").is_file()
    refused = CliRunner().invoke(cli.app, ["eval", "toy", "--held-out", "--reason", "r", "--out", str(tmp_path)])
    assert refused.exit_code != 0 and not (tmp_path / "ledger.jsonl").exists()
    with pytest.raises(ValueError, match="tracked store"):
        core.run(toy, core.Half.held_out, "r", results_dir=tmp_path)


def test_setup_exits_1_when_a_required_item_is_missing(monkeypatch) -> None:
    from adroit.external import setup
    missing = setup.ItemStatus(name="DIAMX", kind="tool", obtain="manual", present=False, required=True,
                               folder="", licence="", used_in=[], action="build it")
    monkeypatch.setattr(setup, "run", lambda **kw: [missing])
    out = CliRunner().invoke(cli.app, ["setup"])
    assert out.exit_code == 1 and "1 required item(s) missing" in out.output


def test_the_workbench_records_a_budget_stop(tmp_path, monkeypatch) -> None:
    from adroit.ui import engine, runner
    job = engine.Job(title="t", kind="idea", command=["idea", "--text", "x"], folder=str(tmp_path))
    engine.save(job)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: SimpleNamespace(pid=0, wait=lambda: 3,
                                                                                    terminate=lambda: None))
    assert runner.run(tmp_path, engine.command_sha256(job.command)).status == "budget_stopped"   # as its launch confirms
    assert "budget_stopped" in engine.DONE


# --- the release runner --------------------------------------------------------------------------------------

def test_release_runner_writes_a_receipt_and_fails_on_a_failing_step(tmp_path, monkeypatch) -> None:
    from adroit.core import config
    checks = _load(ROOT / "scripts/release_checks.py", "release_checks")
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(runs_dir=tmp_path / "runs"))
    monkeypatch.setattr(checks, "identity", lambda: ("abc1234", "tree-a", "tree-t"))
    good = checks.Step(name="fast", command=[sys.executable, "-c", "print('3 passed in 0.1s')"])
    bad = checks.Step(name="validate_portal_library_2",
                      command=[sys.executable, "-c", "import sys; print('1 of 2 gates pass (0 s)'); sys.exit(1)"])
    monkeypatch.setattr(checks, "steps", lambda log_root: [good, bad])
    assert checks.main(["--out", str(tmp_path / "receipts")]) == 1
    receipt = json.loads(next((tmp_path / "receipts").glob("*.json")).read_text())
    assert [s["verdict"] for s in receipt["steps"]] == ["pass", "FAIL"]
    assert receipt["steps"][0]["summary"] == "3 passed in 0.1s" and receipt["commit"] == "abc1234"
    assert "NOT PASSED" in next((tmp_path / "receipts").glob("*.md")).read_text()
    table = "| gate | ours |\n|---|---|\n| documented gate: ratio | 1.08 | 0.94–1.06 | ref | FAIL |\n1 of 2 gates pass"
    listed = checks.Step(name="validate_portal_library_2",
                         command=[sys.executable, "-c", f"import sys; print({table!r}); sys.exit(1)"])
    monkeypatch.setattr(checks, "steps", lambda log_root: [good, listed])
    monkeypatch.setattr(checks, "EXPECTED", {"validate_portal_library_2": {"documented gate": "documented in X"}})
    assert checks.main(["--out", str(tmp_path / "second")]) == 0
    receipt = json.loads(next((tmp_path / "second").glob("*.json")).read_text())
    assert receipt["steps"][1]["verdict"] == "expected failure" and "documented gate" in receipt["steps"][1]["summary"]
    monkeypatch.setattr(checks, "EXPECTED", {"validate_portal_library_2": {"another gate": "documented in X"}})
    assert checks.main(["--out", str(tmp_path / "third")]) == 1      # an unlisted failing gate is a failure


@pytest.mark.parametrize("code,output", [
    (2, "ruff failed\n  Cause: Failed to parse pyproject.toml: TOML parse error at line 3"),   # a configuration error
    (127, "ruff: command not found"),                                                          # a missing command
    (0, ""),                                                                                   # no output at all
    (1, "Found 3 errors.\n[*] 2 fixable with the `--fix` option."),                           # real violations
    (0, "Found 2 errors."),                                                                    # an inconsistent exit
])
def test_release_runner_fails_lint_unless_ruff_ran_and_reported_clean(code, output) -> None:
    """The external audit's A10 (2026-10-16): exit 2 and exit 127 had been passes, read as 0 violations."""
    checks = _load(ROOT / "scripts/release_checks.py", "release_checks")
    ruff = checks.Step(name="ruff", command=["ruff"])
    assert checks.verdict(ruff, code, checks.summarise("ruff", output), output) == "FAIL"


def test_release_runner_reads_ruff_as_a_ratchet_and_skips_only_unavailable_optional_backends() -> None:
    checks = _load(ROOT / "scripts/release_checks.py", "release_checks")
    ruff = checks.Step(name="ruff", command=["ruff"])
    over = f"Found {checks.RUFF_BASELINE + 1} errors."
    assert checks.verdict(ruff, 1, checks.summarise("ruff", over), over) == "FAIL"
    assert checks.RUFF_BASELINE == 0                                   # R11: ruff is clean, any violation fails
    assert checks.verdict(ruff, 0, checks.summarise("ruff", "All checks passed!"), "") == "pass"
    assert checks.summarise("ruff", "All checks passed!") == "0 violations"
    optional = checks.Step(name="validate_native_pico_si", command=["x"], optional=True)
    assert checks.verdict(optional, 1, "", "ValueError: native SI validation failed") == "FAIL"
    # the external audit of 2026-10-17, R17-9: only the preflight skips; a failed step's words no longer do
    assert checks.verdict(optional, 1, "", "ModuleNotFoundError: No module named 'pymupdf'") == "FAIL"
    with pytest.raises(SystemExit):
        checks.chosen(checks.steps(Path("/tmp")), "nonsense", "")
    assert [s.name for s in checks.chosen(checks.steps(Path("/tmp")), "ruff,fast", "fast")] == ["ruff"]


def test_an_optional_step_is_skipped_only_by_its_preflight(tmp_path) -> None:
    """R17-9: a numerical failure that also prints "offline mode active" (or a missing result file) had been read
    as an unavailable backend and skipped. Now the preflight decides availability before the step runs."""
    checks = _load(ROOT / "scripts/release_checks.py", "release_checks")
    py = sys.executable
    failing = [py, "-c", "import sys; print('offline mode active'); print('FileNotFoundError: result.json'); "
                         "print('ValueError: ratio 1.4 outside 0.8-1.2'); sys.exit(1)"]
    available = [py, "-c", "print('available')"]
    lacking = [py, "-c", "import sys; print('the reference WIMpy_NREFT is not installed'); sys.exit(3)"]
    hidden = checks.run_step(checks.Step(name="optional_backends", command=failing, optional=True,
                                         preflight=available), tmp_path)
    assert hidden.verdict == "FAIL"
    skipped = checks.run_step(checks.Step(name="optional_backends", command=failing, optional=True,
                                          preflight=lacking), tmp_path)
    assert skipped.verdict == "skipped" and "WIMpy_NREFT is not installed" in skipped.summary
    passing = checks.run_step(checks.Step(name="optional_backends", command=available, optional=True,
                                          preflight=available), tmp_path)
    assert passing.verdict == "pass"
    assert all(s.preflight for s in checks.steps(tmp_path) if s.optional)


def test_the_browser_layer_has_its_own_budget_and_a_step_is_stopped_at_its_own(tmp_path) -> None:
    """The browser layer passed the shared 3 h in its last control once the halo journeys were added (the release
    checks of 2026-11-18): it has 6 h; every other step keeps 3 h, and a step is stopped at its own budget."""
    checks = _load(ROOT / "scripts/release_checks.py", "release_checks")
    budgets = {s.name: s.timeout_s for s in checks.steps(tmp_path)}
    assert budgets.pop("browser_acceptance") == 6 * 3600
    assert set(budgets.values()) == {3 * 3600}
    slow = checks.Step(name="fast", command=[sys.executable, "-c", "import time; time.sleep(30)"], timeout_s=1)
    stopped = checks.run_step(slow, tmp_path)
    assert stopped.verdict == "FAIL" and stopped.returncode is None and stopped.seconds < 20
    assert "timed out after 1 s" in (tmp_path / "fast.log").read_text()


def test_the_portal_acceptance_comparison_lists_level_count_and_reason_changes() -> None:
    acceptance = _load(ROOT / "scripts" / "portal_acceptance.py", "portal_acceptance")
    def crossing(status, pending=(), excluded=()):
        return {"point": {}, "status": status, "pending": list(pending), "excluded_by": list(excluded)}
    before = {"a": {"level": "viable_pending", "crossings": [crossing("pending", ["capture in the Sun"])]}}
    after = {"a": {"level": "viable", "crossings": [crossing("viable")]}, "b": {"error": "ValueError: x"}}
    text = acceptance.compare(before, after)
    assert "| a | viable_pending → viable | 0 → 1 | 1 → 0 | 0 |" in text
    assert "- a: capture in the Sun (1)" in text and "| b | — → ValueError: x |" in text


def test_the_operator_table_envelope_uses_only_validated_finite_limits() -> None:
    tab = _load(ROOT / "scripts" / "tabulate_operator_limits.py", "tabulate_operator_limits")
    rows = [{"mu_up": [1.0, 2.0, math.inf], "validated": [True, False, True]},
            {"mu_up": [3.0, 0.5, 4.0], "validated": [True, False, True]}, {"error": "no data"}]
    assert tab.envelope(rows, [1.0, 2.0, 3.0]) == [1.0, None, 4.0]
    from adroit.parameter_space.operator_limits import table
    assert all(v is None for v in table("anapole")["mu_up"])           # R6: no module validated for O8/O9

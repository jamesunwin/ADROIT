"""DM15: the run engine (subprocesses through files) and the typed forms with their commands."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adroit.orchestrator import cli
from adroit.ui import engine, forms

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_the_budget_gate():
    assert not forms.check_budget(None, True).ok
    assert not forms.check_budget(0.0, True).ok
    assert not forms.check_budget(forms.CAP_USD + 1, True).ok
    assert not forms.check_budget(1.0, False).ok
    ok = forms.check_budget(1.5, True)
    assert ok.ok and ok.amount == 1.5


def test_a_paid_command_needs_its_budget_confirmed(tmp_path):
    command = forms.idea_command("text", "an idea", tmp_path, budget=2.0)
    assert engine.paid(command) == 2.0 and engine.paid(["track1", "m.yaml"]) == 0.0
    with pytest.raises(engine.BudgetNotConfirmed):
        engine.launch(command, tmp_path / "run", "an idea", confirmed_budget=1.0, popen=lambda *a, **k: None)


def test_only_valid_models_can_be_approved():
    from types import SimpleNamespace as NS
    good = NS(spec=NS(name="a"), audit=NS(valid=True))
    bad = NS(spec=NS(name="b"), audit=NS(valid=False))
    assert forms.approved([good, bad], {"a": True, "b": True}) == [good]


@pytest.mark.parametrize("command", [
    forms.idea_command("fields", "f.yaml", Path("out")),
    forms.idea_command("text", "an idea", Path("out"), models=3, budget=1.0),
    forms.track1_command(Path("m.yaml"), Path("out"), literature=False, parent=Path("p")),
    forms.signal_command("CDMS II Si (2013)", Path("out"), ["DEAP-3600 (2019)"], 1000, [Path("m.yaml")], "5,10",
                         True, True),
    forms.single_idea_command(Path("m.yaml"), "record:r.yaml", Path("out"), "5:40:8", 500, 6, False, True, Path("p")),
    forms.promote_command(Path("run"), ["class:0"], budget=1.0),
    forms.anomaly_check_command(Path("r.yaml")),
    forms.portal_command("higgs_portal_scalar", Path("out"), literature=False),
    forms.anomaly_draft_command("1304.4279", Path("d.yaml"), 0.5),
    forms.derive_command(Path("out"), 1.0, Path("m.yaml")),
    forms.derive_command(Path("out"), 1.0, description="a Majorana fermion with a scalar", checker="none"),
])
def test_every_wizard_command_is_one_the_command_line_accepts(command, monkeypatch):
    """Every option a wizard writes is one the real command declares."""
    from adroit.orchestrator import runs
    called = []
    for name in ("idea", "track1", "signal", "single_idea", "promote"):
        monkeypatch.setattr(runs, name, lambda *a, _n=name, **k: called.append(_n) or (Path("."), "ok"))
    monkeypatch.setattr(cli, "_spec", lambda path: None)
    monkeypatch.setattr(cli, "_derivation", lambda path: None)
    head = command[:2] if command[0] == "anomaly" else command[:1]
    result = CliRunner().invoke(cli.app, [*head, "--help"])
    assert result.exit_code == 0
    for option in [a for a in command if a.startswith("--")]:
        assert option in result.output, option


@pytest.mark.needs("diamx", "cdmslite", "solar_model")
@pytest.mark.needs("eos")
def test_a_launched_run_completes_and_leaves_its_study(tmp_path):
    """A real subprocess: Track 1 on a 3 × 3 grid, without the literature search."""
    folder = tmp_path / "run"
    command = forms.track1_command(DOCS / "dm13" / "axial_mediator.yaml", folder, "m_med:100:3000:log:3",
                                   "m_chi:50:1500:log:3", literature=False)
    job = engine.launch(command, folder, "a small scan")
    deadline = time.time() + 240
    try:
        while engine.poll(folder).status == "running" and time.time() < deadline:
            time.sleep(0.5)
    finally:
        if engine.poll(folder).status == "running":      # past its deadline: stopped, not left running
            engine.cancel(folder)
    snap = engine.snapshot(folder)
    assert snap["job"].status == "completed", snap["log"]
    assert snap["report"] and (folder / "study.json").exists() and job.pid > 0


def test_a_run_can_be_cancelled(tmp_path):
    folder = tmp_path / "run"
    engine.launch(forms.track1_command(DOCS / "dm13" / "axial_mediator.yaml", folder, "m_med:10:10000:log:60",
                                       "m_chi:1:2000:log:60", literature=False), folder, "a long scan")
    time.sleep(2.0)
    engine.cancel(folder)
    deadline = time.time() + 30
    while engine.poll(folder).status == "running" and time.time() < deadline:
        time.sleep(0.5)
    job = engine.poll(folder)
    assert job.status == "cancelled" and engine.cancelled(folder) and job.returncode != 0
    assert not engine.calculation_alive(job)        # its whole group ended before its runner wrote the status
    deadline = time.time() + 10                     # the status is its runner's last act: caught in its last moments,
    while engine._alive(job.pid) and time.time() < deadline:    # it ends at once (cancel's own reading of the group
        time.sleep(0.05)                                         # can outlast them)
    assert not engine._alive(job.pid)


def test_track1_forms_expose_coverage_and_failed_job_resume_keeps_its_inputs(tmp_path):
    from types import SimpleNamespace
    command=forms.track1_command(Path('model.yaml'),tmp_path,coverage_depth=1,coverage_budget=100)
    assert command[-4:]==['--coverage-depth','1','--coverage-budget','100']
    portal=forms.portal_command('higgsino',tmp_path,coverage_depth=2,coverage_budget=200)
    assert portal[-4:]==['--coverage-depth','2','--coverage-budget','200']
    checkpoint=tmp_path/'.track1-checkpoint'
    checkpoint.mkdir()
    (checkpoint/'manifest.json').write_text('{}')
    engine.save(engine.Job(title='interrupted',kind='track1',command=command,folder=str(tmp_path),status='cancelled'))
    (tmp_path/engine.CONTROL).write_text('{"cancel":true}')
    result=engine.resume(tmp_path,popen=lambda *a,**k:SimpleNamespace(pid=123))
    assert result.command==[*command,'--resume'] and not (tmp_path/engine.CONTROL).exists()
    assert (tmp_path/'job_history.jsonl').exists()


def test_the_derivation_form_needs_a_budget_and_one_input(tmp_path):
    """R7 item 8: DM8's derivation from the workbench is paid, behind the budget gate."""
    command = forms.derive_command(tmp_path, 1.5, Path("m.yaml"))
    assert command[:2] == ["lagrangian", "m.yaml"] and "--derive" in command and engine.paid(command) == 1.5
    with pytest.raises(engine.BudgetNotConfirmed):
        engine.launch(command, tmp_path / "x", "derive", confirmed_budget=0.5)
    for bad in (dict(budget=0, model=Path("m.yaml")), dict(budget=1.0), dict(budget=1.0, model=Path("m"), description="w")):
        with pytest.raises(ValueError):
            forms.derive_command(tmp_path, **bad)


def test_paid_forms_carry_the_chosen_model_and_the_checker_must_differ(tmp_path):
    from adroit.core.pricing import PRIMARY_MODELS, TOKEN_PRICES
    assert set(PRIMARY_MODELS) == {"claude-opus-5-5", "gpt-5.6-sol"} and set(PRIMARY_MODELS) <= set(TOKEN_PRICES)
    assert forms.idea_command("text", "x", tmp_path, budget=1.0, model="gpt-5.6-sol")[-4:-2] == ["--model", "gpt-5.6-sol"]
    assert "--model" not in forms.idea_command("fields", "f.yaml", tmp_path, model="gpt-5.6-sol")
    assert forms.anomaly_draft_command("1304.4279", tmp_path / "d.yaml", 0.5, "gpt-5.6-sol")[-2:] == ["--model", "gpt-5.6-sol"]
    assert "--model" in forms.promote_command(tmp_path, ["class:0"], budget=1.0, model="gpt-5.6-sol")
    assert "--model" not in forms.promote_command(tmp_path, ["class:0"], model="gpt-5.6-sol")      # free: no model
    with pytest.raises(ValueError, match="different model"):
        forms.derive_command(tmp_path, 1.0, Path("m.yaml"), checker="claude-opus-5-5", deriver="claude-opus-5-5")


def test_the_client_follows_the_models_provider(monkeypatch):
    from adroit.agents import llm
    monkeypatch.setattr(llm, "OpenAIClient", lambda **kw: ("openai", kw["model"]))
    monkeypatch.setattr(llm, "LLMClient", lambda **kw: ("anthropic", kw["model"]))
    assert llm.client_for("gpt-5.6-sol") == ("openai", "gpt-5.6-sol")
    assert llm.client_for("claude-opus-5-5") == ("anthropic", "claude-opus-5-5")


# The re-audit's R18-3 (2026-10-18): run folders allocated uniquely, and a job never overwritten by a launch.

class _FrozenClock:
    """``datetime`` with ``now`` stopped at one second."""
    @staticmethod
    def now():
        from datetime import datetime
        return datetime(2026, 10, 18, 0, 0, 0)


def _stub(pid: int = 101):
    from types import SimpleNamespace
    return lambda *a, **k: SimpleNamespace(pid=pid)


def test_two_launches_in_one_second_keep_their_own_folders_and_commands(tmp_path, monkeypatch):
    """The auditor's control: the clock frozen, the same kind and title, different inputs."""
    monkeypatch.setattr(forms, "datetime", _FrozenClock)
    first = forms.new_folder(tmp_path, "signal", "same title")
    a = engine.launch(["signal", "--experiment", "A"], first, "same title", popen=_stub(101))
    second = forms.new_folder(tmp_path, "signal", "same title")
    b = engine.launch(["signal", "--experiment", "B"], second, "same title", popen=_stub(102))
    assert first != second and len(list(tmp_path.iterdir())) == 2
    assert engine.load(first).command == a.command == ["signal", "--experiment", "A"]
    assert engine.load(second).command == b.command == ["signal", "--experiment", "B"]


def test_a_launch_into_a_folder_holding_a_job_is_refused(tmp_path):
    engine.launch(["signal", "--experiment", "A"], tmp_path, "first", popen=_stub())
    with pytest.raises(engine.JobExists):
        engine.launch(["signal", "--experiment", "B"], tmp_path, "second", popen=_stub())
    assert engine.load(tmp_path).command == ["signal", "--experiment", "A"]


def test_of_two_concurrent_launches_into_one_folder_exactly_one_starts(tmp_path):
    import threading
    gate, outcomes = threading.Barrier(2), {}

    def go(name: str) -> None:
        gate.wait()
        try:
            outcomes[name] = engine.launch(["signal", "--experiment", name], tmp_path, name, popen=_stub()).command
        except engine.JobExists:
            outcomes[name] = None
    threads = [threading.Thread(target=go, args=(n,)) for n in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    started = [c for c in outcomes.values() if c is not None]
    assert len(started) == 1 and engine.load(tmp_path).command == started[0]


def test_a_suffix_clash_retries_with_a_new_folder(tmp_path, monkeypatch):
    from adroit.orchestrator import runs
    suffixes = iter(["aaaaaaaa", "aaaaaaaa", "bbbbbbbb"])
    monkeypatch.setattr(runs.secrets, "token_hex", lambda n: next(suffixes))
    monkeypatch.setattr(forms, "datetime", _FrozenClock)
    first = forms.new_folder(tmp_path, "signal", "t")
    second = forms.new_folder(tmp_path, "signal", "t")
    assert first.name.endswith("_aaaaaaaa") and second.name.endswith("_bbbbbbbb") and second.is_dir()


def test_concurrent_allocations_with_one_clock_are_all_distinct(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(forms, "datetime", _FrozenClock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        folders = list(pool.map(lambda _: forms.new_folder(tmp_path, "signal", "same"), range(16)))
    assert len(set(folders)) == 16 and all(f.is_dir() for f in folders)


def _interrupted(folder: Path, kind: str = "track1", status: str = "cancelled") -> list[str]:
    command = forms.track1_command(Path("model.yaml"), folder)
    (folder / ".track1-checkpoint").mkdir(parents=True)
    (folder / ".track1-checkpoint" / "manifest.json").write_text("{}")
    engine.save(engine.Job(title="interrupted", kind=kind, command=command, folder=str(folder), status=status))
    return command


def test_resume_keeps_the_jobs_identity_and_only_restarts_an_interrupted_track1_job(tmp_path):
    import os
    command = _interrupted(tmp_path)
    job = engine.resume(tmp_path, popen=_stub(os.getpid()))           # a live process: the job stays running
    assert (job.title, job.kind, job.folder, job.status) == ("interrupted", "track1", str(tmp_path), "running")
    assert job.command == [*command, "--resume"] and engine.load(tmp_path).pid == os.getpid()
    with pytest.raises(ValueError, match="interrupted"):
        engine.resume(tmp_path, popen=_stub(os.getpid()))              # running: not interrupted
    other = tmp_path / "signal"
    other.mkdir()
    _interrupted(other, kind="signal")
    with pytest.raises(ValueError, match="Track 1"):
        engine.resume(other, popen=_stub())


def test_a_runner_that_finishes_before_the_launcher_records_it_keeps_its_status(tmp_path):
    """S18-15 (the stacked audit of 2026-10-18), the audit's control: the real detached runner and the real command
    line (``adroit --help``), with the launcher's Popen returning only after the runner has finished. The launcher used
    to overwrite "completed" with "running", which polling then turned into "failed"."""
    import subprocess

    def late(*args, **kwargs):
        process = subprocess.Popen(*args, **kwargs)
        process.wait(timeout=60)
        return process
    job = engine.launch(['--help'], tmp_path / 'run', 'the command line help', popen=late)
    assert job.status == 'completed' and job.returncode == 0 and job.pid
    polled = engine.poll(tmp_path / 'run')
    assert (polled.status, polled.returncode, polled.pid) == ('completed', 0, job.pid)


def _inert_child(seen: list):
    """A command line that records its words and ends at once (no command runs)."""
    from types import SimpleNamespace
    return lambda argv, **k: seen.append(argv) or SimpleNamespace(pid=0, returncode=0, wait=lambda: 0, terminate=lambda: None)


def _set_budget(folder, value: str) -> None:
    """Edit the job's file directly, as a person or another process could (the advisory lock does not stop it)."""
    import json
    path = folder / engine.JOB
    data = json.loads(path.read_text())
    data["command"][-1] = value
    path.write_text(json.dumps(data))


def test_the_runner_runs_the_command_it_checked_never_one_edited_after(tmp_path, monkeypatch):
    """C21-05 (the candidate audit, 2026-10-21): the runner checked the confirmed command's sha256 and then ran the
    command ``update`` read back from job.json, so an edit landing in between (here inside the check) raised a $0.50
    run to $5. Now that edit is refused and nothing runs; an edit after the start changes nothing that runs, and the
    job ends recording the command run and its budget."""
    import os
    from adroit.ui import runner
    command = ["idea", "--text", "offline fixture", "--budget", "0.5"]
    real, seen = engine.command_sha256, []
    monkeypatch.setattr(runner.signal, "signal", lambda *a: None)
    monkeypatch.setattr(runner.subprocess, "Popen", _inert_child(seen))   # this process's Popen, the launcher's too:
    monkeypatch.setattr(engine, "process_started", lambda pid: 0.0)       # its runner's start not read by ``ps``
    raced = tmp_path / "raced"
    engine.launch(command, raced, "fixture", confirmed_budget=0.5, popen=_stub(os.getpid()))

    def check_then_edit(words):
        value = real(words)
        _set_budget(raced, "5.0")
        return value
    monkeypatch.setattr(engine, "command_sha256", check_then_edit)
    result = runner.run(raced, real(command))
    assert result.status == "failed" and result.note == runner.REFUSED and not seen
    monkeypatch.setattr(engine, "command_sha256", real)
    later = tmp_path / "later"
    engine.launch(command, later, "fixture", confirmed_budget=0.5, popen=_stub(os.getpid()))
    monkeypatch.setattr(runner.subprocess, "Popen",
                        lambda argv, **k: _set_budget(later, "5.0") or _inert_child(seen)(argv))
    result = runner.run(later, real(command))
    assert seen[-1][-2:] == ["--budget", "0.5"] and result.status == "completed"
    assert result.command == command and result.budget_usd == 0.5


def test_a_spawned_process_is_not_an_acknowledged_start(tmp_path, monkeypatch):
    """C21-06 (the candidate audit, 2026-10-21): the launcher recorded the spawned process's PID at once, and the
    start's bound applied only while the PID was 0, so a live process that never started its run kept the job running,
    and a run reaching its job after the bound, unpolled, still ran. Now the runner acknowledges its start on the job:
    without that acknowledgement the job is closed after the bound by ``poll``, and by a late runner itself, which runs
    nothing; an acknowledged job's process alone decides, and a job from before acknowledgements keeps the old rule."""
    import os
    from datetime import datetime, timedelta
    from adroit.ui import runner
    seen = []
    monkeypatch.setattr(runner.signal, "signal", lambda *a: None)
    monkeypatch.setattr(runner.subprocess, "Popen", _inert_child(seen))   # this process's Popen, the launcher's too:
    monkeypatch.setattr(engine, "process_started", lambda pid: 0.0)       # its runner's start not read by ``ps``
    old = (datetime.now() - timedelta(seconds=engine.LAUNCH_GRACE_SECONDS + 600)).isoformat()
    spawned = tmp_path / "spawned"
    engine.launch(["track1", "fixture.yaml"], spawned, "slow start", popen=_stub(os.getpid()))
    assert engine.poll(spawned).status == "running"                          # within the bound: starting
    engine.update(spawned, started=old)
    closed = engine.poll(spawned)
    assert closed.status == "failed" and closed.note == engine.LAUNCH_NOT_CONFIRMED
    late = tmp_path / "late"
    job = engine.launch(["track1", "fixture.yaml"], late, "late", popen=_stub(os.getpid()))
    engine.update(late, started=old)
    out = runner.run(late, engine.command_sha256(job.command))
    assert out.status == "failed" and out.note == engine.LAUNCH_NOT_CONFIRMED and not seen
    prompt = tmp_path / "prompt"
    job = engine.launch(["track1", "fixture.yaml"], prompt, "prompt", popen=_stub(os.getpid()))
    out = runner.run(prompt, engine.command_sha256(job.command))
    assert out.status == "completed" and out.acknowledged is True and len(seen) == 1
    engine.update(prompt, status="running", started=old, finished="")
    assert engine.poll(prompt).status == "running"                           # acknowledged: its live process decides
    engine.update(prompt, acknowledged=None)
    assert engine.poll(prompt).status == "running"                           # a job from before: as then

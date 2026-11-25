"""A calculation that outlives its runner (a feature audit's ID-01 and ID-02, 2026-11-10): ``engine``'s module docstring.

Real processes: the real runner and its gate, the command line replaced by a stand-in calculation that takes the
study's publication lock and starts a grandchild, which beats a heartbeat; nothing scientific runs. The auditor's
control killed the runner alone and found the job failed while both went on, a cancel that reached neither and a
resume refused by the lock they held."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from adroit.core import durable
from adroit.ui import engine, runner

CALCULATION = '''
import json, os, subprocess, sys, time
from pathlib import Path
folder = Path(os.environ["ADROIT_JOB_FOLDER"])
if sys.argv[1:] == ["grandchild"]:
    for _ in range(300):                          # 30 s at most, whatever happens to the test
        (folder / "heartbeat").write_text(str(time.monotonic()))
        time.sleep(0.1)
    sys.exit(0)
from adroit.core.durable import publishing
with publishing(folder, wait=0.25):
    (folder / "ran").write_text("1")
    if (folder / "quick").exists():
        sys.exit(0)
    grandchild = subprocess.Popen([sys.executable, __file__, "grandchild"])
    (folder / "calculation.json").write_text(json.dumps({"pid": os.getpid(), "grandchild": grandchild.pid}))
    time.sleep(30)
'''

RUNNER = '''
import json, os, sys, time
from pathlib import Path
folder = Path(sys.argv[1])
if (folder / "hold").exists():                    # a launched process that has not yet acknowledged its start
    (folder / "held").write_text(str(os.getpid()))
    while (folder / "hold").exists():
        time.sleep(0.05)
if (folder / "popen_replaced").exists():          # as the auditor's runner fixture: this process's every Popen replaced
    import subprocess
    original = subprocess.Popen

    def launch(argv, **kwargs):                   # one JSON record a launch, whatever its words hold (DW-06)
        with (folder / "popens.log").open("a") as log:
            log.write(RECORD + "\\n")
        return original([sys.executable, sys.argv[3], "track1"], **kwargs)
    subprocess.Popen = launch
from adroit.ui import runner
gate = runner.GATE.replace("'-m', 'adroit.orchestrator.cli', ", repr(sys.argv[3]) + ", ")
assert gate != runner.GATE
runner.GATE = gate
runner.run(folder, sys.argv[2])
'''
RECORD = "json.dumps(list(map(str, argv)))"      # a launch's record in ``popens.log``: the fixture's writer, one source
RUNNER = RUNNER.replace("RECORD", RECORD)


def _launches(folder: Path) -> int:
    """The processes the runner started, by the replaced Popen's records: one JSON array of words each, so that a word
    holding line breaks (the gate's program) is not counted as more launches (the auditor's DV–IE recheck, DW-06: lines of
    the words joined, cut at 120 characters, had counted one launch as three on a short checkout path). Each is the
    gate, its program the runner's."""
    records = [json.loads(line) for line in (folder / "popens.log").read_text().splitlines()]
    assert all(r[1:3] == ["-c", r[2]] and "os.execv(" in r[2] and "os.read(int(sys.argv[1]), 1)" in r[2]
               for r in records), records
    return len(records)


@pytest.mark.parametrize("python", ["/usr/bin/python3", "/Users/someone/project/.venv/bin/python", sys.executable])
def test_one_launch_is_one_record_whatever_the_length_of_its_interpreter_s_path(tmp_path, python):
    """The runner fixture's writer (``RECORD``) and the count (``_launches``) at three lengths of the interpreter's path,
    the gate's program in its words: one launch, one record. The pin's writer and count (lines of the words joined, cut
    at 120 characters) give 6, 3 and 1 here, so the runner's own tests, run from a long checkout path, read 1 either
    way (the auditor's DW recheck, DX-04, 2026-11-12, its ``launch_count``)."""
    argv = [python, "-c", runner.GATE, "7", "track1", "m.yaml"]
    with (tmp_path / "popens.log").open("a") as log:
        log.write(eval(RECORD, {"json": json}, {"argv": argv}) + "\n")
    assert _launches(tmp_path) == 1


def _wait(predicate, seconds: float = 20.0) -> None:
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() > deadline:
            raise TimeoutError("the condition was not reached")
        time.sleep(0.05)


def _running(pid: int) -> bool:
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


def _lock(folder: Path) -> str:
    try:
        with durable.publishing(folder, wait=0.15):
            return "available"
    except durable.Busy:
        return "busy"


class _Launcher:
    """``engine.launch``'s and ``engine.resume``'s ``popen``: the real runner, its command line the stand-in."""

    def __init__(self, scripts: Path) -> None:
        self.scripts, self.started, self.known = scripts, [], []
        (scripts / "calculation.py").write_text(CALCULATION)
        (scripts / "runner.py").write_text(RUNNER)

    def __call__(self, argv, **kwargs):
        process = subprocess.Popen([sys.executable, str(self.scripts / "runner.py"), *argv[-2:],
                                    str(self.scripts / "calculation.py")], **kwargs)
        self.started.append(process)
        return process

    def clean(self, folder: Path) -> None:
        """End what the test left (the job's own group only, as the engine identifies it)."""
        try:
            engine.stop_calculation(engine.load(folder), forcibly=True)
        except (OSError, ValueError):
            pass
        for process in self.started:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
        for pid in self.known:                    # a stand-in this test started, wherever its group went
            command = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout
            if str(self.scripts / "calculation.py") in command:
                os.kill(pid, signal.SIGKILL)


@pytest.fixture
def launcher(tmp_path):
    made = _Launcher(tmp_path)
    yield made
    for folder in tmp_path.glob("job*"):
        made.clean(folder)


def _started(launcher: _Launcher, folder: Path) -> tuple[engine.Job, dict]:
    engine.launch(["track1", "fixture.yaml"], folder, "a stand-in calculation", popen=launcher)
    _wait(lambda: (folder / "calculation.json").exists() and (folder / "heartbeat").exists())
    ran = json.loads((folder / "calculation.json").read_text())
    launcher.known += [ran["pid"], ran["grandchild"]]
    return engine.load(folder), ran


def test_a_runner_killed_outright_leaves_its_calculation_named_stoppable_and_resumable(tmp_path, launcher):
    """ID-01, the auditor's ``kill_runner``: the runner SIGKILLed alone. The job names its calculation (its group's
    leader and start time) before the command began; once the runner has gone the job is closed failed, unresolved,
    naming the processes still running; a resume is refused while they run; a cancel ends both, the lock is free, and
    the resume then starts and publishes."""
    folder = tmp_path / "job"
    job, ran = _started(launcher, folder)
    assert job.calculation == ran["pid"]
    assert abs(job.calculation_started - engine.process_started(ran["pid"])) <= engine.SAME_START_S
    assert sorted(engine.calculation_alive(job)) == sorted([ran["pid"], ran["grandchild"]])
    os.kill(job.pid, signal.SIGKILL)
    launcher.started[0].wait(timeout=10)
    closed = engine.poll(folder)
    assert closed.status == "failed" and "unresolved, not stopped" in closed.note
    assert str(ran["pid"]) in closed.note and str(ran["grandchild"]) in closed.note
    assert _running(ran["pid"]) and _running(ran["grandchild"]) and _lock(folder) == "busy"
    (folder / ".track1-checkpoint").mkdir()                       # its existence only: no scientific checkpoint
    (folder / ".track1-checkpoint/manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="calculation still runs"):
        engine.resume(folder, popen=launcher)
    assert len(launcher.started) == 1                              # nothing was started
    engine.cancel(folder)
    _wait(lambda: not _running(ran["pid"]) and not _running(ran["grandchild"]), 10)
    assert engine.calculation_alive(engine.load(folder)) == [] and _lock(folder) == "available"
    assert "asked to stop by Cancel" in engine.load(folder).note
    (folder / "quick").write_text("1")
    (folder / "ran").unlink()
    resumed = engine.resume(folder, popen=launcher)
    assert resumed.status == "running" and resumed.calculation == 0          # its runner records its own
    _wait(lambda: engine.poll(folder).status != "running")
    done = engine.poll(folder)
    assert done.status == "completed" and (folder / "ran").exists() and done.calculation not in (0, ran["pid"])
    assert engine.calculation_alive(done) == []


def test_a_runner_stopped_by_sigterm_ends_its_whole_calculation(tmp_path, launcher):
    """ID-01, the auditor's ``term_runner``: SIGTERM to the runner alone had ended its direct child only, its
    grandchild beating on. Now it ends the calculation's group, and the job says it was stopped by a signal."""
    folder = tmp_path / "job"
    job, ran = _started(launcher, folder)
    os.kill(job.pid, signal.SIGTERM)
    launcher.started[0].wait(timeout=15)
    done = engine.poll(folder)
    assert done.status == "failed" and runner.SIGNALLED in done.note and done.returncode != 0
    assert not _running(ran["pid"]) and not _running(ran["grandchild"]) and _lock(folder) == "available"
    beat = (folder / "heartbeat").read_text()
    time.sleep(0.4)
    assert (folder / "heartbeat").read_text() == beat


def test_a_cancel_ends_the_calculation_and_its_descendants(tmp_path, launcher):
    """The auditor's ``normal_cancel``, with the grandchild checked too."""
    folder = tmp_path / "job"
    job, ran = _started(launcher, folder)
    engine.cancel(folder)
    launcher.started[0].wait(timeout=15)
    done = engine.poll(folder)
    assert done.status == "cancelled" and runner.SIGNALLED not in done.note and "unresolved" not in done.note
    assert not _running(ran["pid"]) and not _running(ran["grandchild"]) and _lock(folder) == "available"


def test_the_runner_starts_no_process_but_its_command_line(tmp_path, launcher):
    """The auditor's cancellation control replaces ``subprocess.Popen`` in the runner's process, so that every process it
    starts is the control's stand-in calculation. The runner starts one, its command line, and asks nothing of ``ps``:
    a run that ends is completed, nothing more started; a runner killed outright leaves its calculation named
    unresolved, and Cancel ends it (before, its every ``ps`` started another stand-in, and the control timed out)."""
    quick = tmp_path / "job-quick"
    quick.mkdir()
    (quick / "popen_replaced").write_text("1")
    (quick / "quick").write_text("1")
    engine.launch(["track1", "fixture.yaml"], quick, "a stand-in calculation", popen=launcher)
    _wait(lambda: engine.poll(quick).status != "running")
    assert engine.poll(quick).status == "completed" and (quick / "ran").exists()
    assert _launches(quick) == 1
    killed = tmp_path / "job-killed"
    killed.mkdir()
    (killed / "popen_replaced").write_text("1")
    job, ran = _started(launcher, killed)
    os.kill(job.pid, signal.SIGKILL)
    launcher.started[-1].wait(timeout=10)
    assert "unresolved, not stopped" in engine.poll(killed).note
    engine.cancel(killed)
    _wait(lambda: not _running(ran["pid"]) and not _running(ran["grandchild"]), 10)
    assert _launches(killed) == 1 and _lock(killed) == "available"


def test_a_recorded_calculation_is_never_another_process(tmp_path):
    """Its process number recycled: a live process with the recorded number but another start time is not the job's,
    and is neither signalled by a cancel nor waited for by a resume; with its own start time it is the job's."""
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    try:
        _wait(lambda: engine.process_started(other.pid) > 0)
        folder = tmp_path / "job"
        folder.mkdir()
        (folder / ".track1-checkpoint").mkdir()
        (folder / ".track1-checkpoint/manifest.json").write_text("{}")
        recycled = engine.Job(title="t", kind="track1", command=["track1", "m.yaml"], folder=str(folder),
                              status="failed", calculation=other.pid,
                              calculation_started=engine.process_started(other.pid) - 3600)
        engine.save(recycled)
        assert engine.calculation_alive(recycled) == []
        engine.cancel(folder)
        engine.cancel(folder)                                     # a second cancel would be forcible
        time.sleep(0.3)
        assert other.poll() is None and "Cancel" not in engine.load(folder).note
        assert engine.resume(folder, popen=lambda *a, **k: type("P", (), {"pid": 0})()).status == "running"
        own = recycled.model_copy(update={"calculation_started": engine.process_started(other.pid)})
        assert engine.calculation_alive(own) == [other.pid]
        assert engine.stop_calculation(own) == [other.pid]
        assert other.wait(timeout=10) == -signal.SIGTERM
        assert engine.calculation_alive(own) == []                # ended, its group gone
    finally:
        if other.poll() is None:
            other.kill()
            other.wait()


def test_a_cancel_before_the_run_acknowledged_its_start_is_recorded_cancelled(tmp_path, launcher):
    """ID-02: the run held before acknowledging its start, a cancel, its process ending: the job had read failed. Now
    cancelled, nothing run; without a cancel, a launched process that ends before acknowledging is still failed."""
    for name, cancelling in (("job-cancelled", True), ("job-lost", False)):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "hold").write_text("1")
        engine.launch(["track1", "fixture.yaml"], folder, "held", popen=launcher)
        _wait(lambda: (folder / "held").exists())
        process = launcher.started[-1]
        assert engine.load(folder).acknowledged is False
        if cancelling:
            engine.cancel(folder)
        else:
            os.kill(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        closed = engine.poll(folder)
        assert not (folder / "ran").exists() and closed.acknowledged is False and closed.calculation == 0
        if cancelling:
            assert closed.status == "cancelled" and closed.note == engine.NOTHING_RUN
        else:
            assert closed.status == "failed" and closed.note == ""
        assert engine.load(folder).status == closed.status                # as reopened


def test_the_gate_runs_nothing_without_the_runners_word(tmp_path):
    """The window between the command's start and its record: a runner that ends there leaves a gate that runs
    nothing; given the word, the gate becomes the command line itself (the same process, the recorded one)."""
    target = tmp_path / "command.py"
    target.write_text("import os, sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(str(os.getpid()))\n")
    gate = runner.GATE.replace("'-m', 'adroit.orchestrator.cli', ", repr(str(target)) + ", ")
    for word, expected in ((b"", 1), (b"1", 0)):
        mark = tmp_path / f"ran-{expected}"
        read, write = os.pipe()
        process = subprocess.Popen([sys.executable, "-c", gate, str(read), str(mark)], pass_fds=(read,))
        os.close(read)
        os.write(write, word)
        os.close(write)
        assert process.wait(timeout=20) == expected
        assert (mark.read_text() == str(process.pid)) if expected == 0 else not mark.exists()


@pytest.fixture
def left(tmp_path):
    """A closed Track 1 job (its runner gone, without a word) whose recorded calculation still runs: a process of its
    own group, with its own start time."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    _wait(lambda: engine.process_started(process.pid) > 0)
    folder = tmp_path / "runs" / "scan"
    folder.mkdir(parents=True)
    engine.save(engine.Job(title="a scan", kind="track1", command=["track1", "m.yaml"], folder=str(folder),
                           status="failed", acknowledged=True, finished=engine._now(), calculation=process.pid,
                           calculation_started=engine.process_started(process.pid)))
    yield folder, process
    if process.poll() is None:
        process.kill()
        process.wait()


def test_a_closed_job_whose_calculation_runs_is_said_unresolved_with_cancel(left):
    """ID-01, as the workbench reads the job: its diagnosis had been "the process ended without a word", with Resume
    (which the running calculation refused), and its outcome a failure, Cancel hidden. Now each says its calculation
    still runs, unresolved, and offers Cancel, which stops it; then the job reads as before."""
    from adroit.orchestrator.recovery import diagnose
    from adroit.ui import outcomes
    folder, process = left
    job = engine.load(folder)
    said = engine.left_running(job)
    assert str(process.pid) in said and "unresolved, not stopped" in said
    found = diagnose(job, [], folder)
    assert found.kind == "interrupted" and "still runs" in found.summary
    assert [a.kind for a in found.actions] == ["cancel"]
    assert outcomes.unfinished(job, "The run") == ("The run: failed, its calculation still running", said)
    assert engine.snapshot(folder)["left_running"] == said
    engine.cancel(folder)
    assert process.wait(timeout=10) == -signal.SIGTERM
    job = engine.load(folder)
    assert engine.left_running(job) == "" and "asked to stop by Cancel" in job.note
    assert diagnose(job, [], folder).summary.startswith("the process ended without a word")
    assert outcomes.unfinished(job, "The run")[0] == "The run: failed"


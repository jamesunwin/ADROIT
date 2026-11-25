"""The workbench's runs (DM15): command-line subprocesses, watched and controlled through files.

The workbench never runs a pipeline in its own process. A launch:
1. writes ``job.json`` into the run's folder: the command, the budget the
   person confirmed, and the status;
2. starts ``adroit.ui.runner`` detached (its own process group, at low
   priority with ``nice``). The runner runs the ordinary command line, with
   its output in ``log.txt``, and writes the final status and exit code when
   it ends, so a run outlives the workbench;
3. is watched through those files: the status, the time, the log's tail and
   the spend (the command line's "spent $x" lines, or ``study.json``).

Cancelling writes ``control.json`` and ends the process group. A command
that spends money (it has ``--budget``) is refused unless the person
confirmed that budget. A launch never reuses a folder that holds a job: its
``job.json`` is created exclusively, so of two launches into one folder
exactly one starts (the re-audit's R18-3); only ``resume`` restarts an
existing job, an interrupted Track 1 run, under the same identity.

**The command a launch confirmed is the one that runs** (the auditor's RC20-01,
2026-10-20). The launching process hands the runner the command's sha256 on
the runner's command line, never read back from ``job.json``; just before
running, the runner checks the job's command against it under the job's lock
and refuses a command edited since (its budget included), and it runs the
command it checked, its own copy, never one read again from the job (C21-05,
2026-10-21: an edit landing between the check and the start had run).
**Starting is acknowledged within a bound** (RC20-02): the runner acknowledges
its start on the job (``Job.acknowledged``, under the job's lock) within
``LAUNCH_GRACE_SECONDS`` of its job's start, or the job is closed ("launch not
confirmed"): by ``poll``, whatever process holds the launcher's PID and whether
or not the spawned process lives (a PID from spawning is not an acknowledgement:
C21-06), and by the runner itself if it reaches the job late, so a late run
dispatches nothing; a resume that fails to start closes its job with the
reason. Nothing here ever starts a command again on its own. The trust boundary: these files protect against crashes, restarts and a
batch's or job's own files changing; a person editing every record by hand is
outside it.

**A calculation that outlives its runner is the run's still** (a feature audit's ID-01 and ID-02, 2026-11-10). The
runner starts the command line in a process group of its own, its calculation's, and records its process and start
time on the job (``Job.calculation``); every process the command starts belongs to that group. A cancel ends the
runner's group, whose runner ends its calculation's group, and ends the calculation's group itself as well. Before,
the runner's SIGTERM had reached its direct child only, and a runner killed outright had left its calculation alive:
the job read failed, a cancel signalled nothing, and the calculation went on holding the study's publication lock, so a
resume was refused. Now:
- a job whose runner has ended while its calculation still runs is closed failed and says so: unresolved, its processes
  named (``UNRESOLVED``), never as if its work had ended;
- a cancel reaches that calculation (a second cancel ends what ignored the first);
- a resume waits for it (``calculation_alive``).
A group is the job's only where its recorded leader is alive with its recorded start time (``SAME_START_S``). The runner records that time by its own clock and starts no process but
the command line: it never asks ``ps`` (``runner._left``; the auditor's cancellation control replaces ``subprocess.Popen`` in
the runner's process, where every other process started would have been its stand-in calculation). A cancel before the
run acknowledged its start is recorded cancelled, not failed (ID-02).

**Nothing is signalled that is not proven the job's** (the auditor's DV–IE recheck, DW-03, 2026-11-11). A process number is
given again once its process has ended, so a number on a job proves nothing alone:
- the runner is signalled only where the process with its number has the start its launcher read from ``ps`` when it
  spawned it (``Job.runner_started``, ``runner_alive``). A job from before that record has its runner asked to stop
  by its control file only;
- a calculation's group is signalled only while its recorded leader lives with its recorded start. A group of that
  number whose leader has ended may be what the calculation left, or another's group made since: its processes are
  named (``calculation_unproven``, ``UNPROVEN``) and never signalled. Before, a cancel had signalled a recycled runner
  number's group, and a leaderless group had been taken as the job's.
- a start proves a process only where both starts, the one recorded and the one ``ps`` gives now, are times
  (finite, after the epoch) within ``SAME_START_S`` of each other (``_proven_start``); a start not recorded (0), not a
  time (NaN, ±∞) or not read (``ps`` giving nothing) proves nothing, and a group so led is named
  (``START_UNPROVEN``), never signalled. The auditor's DW recheck (DX-02, 2026-11-12) had found a recorded NaN, and a 0
  beside a ``ps`` that gave none, read as the same start, and the group signalled.

**A run reads the folders its launch read** (an operating-conditions audit's IE-01, 2026-11-10). The runner starts in
the project's folder, where a relative directory setting names another folder than in the launching process. A launch
records its directory settings on the job as absolute paths (``Job.directories``, ``config.launched``) and gives the
runner those, and a resume gives them again, whatever the resuming process's own.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from pydantic import Field, field_validator

from adroit.core.config import child_environment as _child, run_environment as _run_environment
from adroit.core.config import PROJECT_ROOT, launched
from adroit.core.state import StrictModel
from adroit.core.checkpoint import Progress

JOB, LOG, CONTROL = "job.json", "log.txt", "control.json"
DONE = ("completed", "budget_stopped", "failed", "cancelled")
LAUNCH_GRACE_SECONDS = 60.0      # a run records its process within this of its job's start, or its job is closed


def moment(value: str, empty: bool = False) -> str:
    """A run record's time as ADROIT reads it: an ISO date and time on this machine's clock, as ADROIT writes it
    (``datetime.now().isoformat``), kept as written; one with a time zone (a record moved from elsewhere) taken as
    this machine's local time; anything else refused (ValueError), so that the record is named as damaged where it is
    listed rather than failing the page that reads it (the non-physics audit's NP17-03, 2026-11-17: a job whose start
    was "not-a-date", or carried a time zone, had made the Studies page a server error). ``empty``: "" allowed (not
    yet finished)."""
    if empty and value == "":
        return value
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} is not a date and time (ISO 8601)") from None
    if parsed.tzinfo is not None:
        try:              # an offset that leaves the calendar's range is a damaged record (the audit loop's AL8-02)
            return parsed.astimezone().replace(tzinfo=None).isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError):
            raise ValueError(f"{value!r} cannot be converted to local time") from None
    return value


class Job(StrictModel):
    """A launched run (``job.json``): the command, its folder, the confirmed budget, the status, the process and its
    start and end (each checked as a time, ``moment``)."""
    title: str
    kind: str                                 # the command: idea, track1, signal, single-idea, promote, anomaly
    command: list[str]                        # the arguments after ``adroit``
    folder: str
    budget_usd: float = 0.0                   # what the person confirmed (paid commands only)
    # how that spend was approved (``forms.BudgetCheck.approval``): "auto", by the auto-approve setting with the
    # default models chosen; "click", by the person's tick; "" in a job from before 2026-11-18 or without a gate's word
    approval: str = ""
    status: str = "running"                   # running, completed, budget_stopped, failed, cancelled
    pid: int = 0                              # the run's process: 0 until it has been spawned
    acknowledged: bool | None = None          # its runner has started it (``runner.run``); None: a job from before
    launcher_pid: int = 0                     # the process that wrote the job (``launch``, ``resume``)
    owner: str = ""                           # who launched it, for a batch "<batch folder>#<item>#<approval>"
    note: str = ""                            # why it ended where no run said (a launch that never started)
    returncode: int | None = None
    started: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished: str = ""
    # this launch's own identity, kept through a resume: the study record its run publishes in its folder names it, so
    # that its cost is read as that study's only where the run in the folder is the one that published it (the auditor's DB/VI
    # recheck, DC-01, 2026-11-03); "" in a job from before
    attempt: str = ""
    # its calculation, the command line the runner started: its process, the leader of its own process group, and when
    # it started, in seconds since the epoch by its runner's clock (module docstring; absent from a job from before)
    calculation: int = Field(default=0, exclude_if=lambda v: not v)
    calculation_started: float = Field(default=0.0, exclude_if=lambda v: not v)
    # its runner's start as ``ps`` gave it to the launcher that spawned it: what proves a live process with ``pid`` is
    # its runner, before it is signalled (DW-03); 0 for a job from before
    runner_started: float = Field(default=0.0, exclude_if=lambda v: not v)
    # the directory settings its launch read, as ``ADROIT_<name>`` variables with absolute paths, given to its runner
    # at each start (module docstring; absent from a job from before, whose runner is given its launcher's own)
    directories: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)

    @field_validator("started")
    @classmethod
    def _started(cls, value: str) -> str:
        return moment(value)

    @field_validator("finished")
    @classmethod
    def _finished(cls, value: str) -> str:
        return moment(value, empty=True)


class BudgetNotConfirmed(PermissionError):
    """A paid command without a budget the person confirmed."""


class JobExists(FileExistsError):
    """A launch into a folder that already holds a job (R18-3); an interrupted Track 1 job is resumed instead."""


def paid(command: list[str]) -> float:
    """The dollars a command may spend (its ``--budget``), 0 for a free one: ``accounting.budget_of``, read as the
    command line reads it (a repeated, missing, non-finite or negative budget is refused: ValueError)."""
    from adroit.orchestrator.accounting import budget_of
    return budget_of(command)


def command_sha256(command: list[str]) -> str:
    """A command's identity: the sha256 of its words, in order."""
    import hashlib
    return hashlib.sha256(json.dumps(list(command), separators=(",", ":")).encode()).hexdigest()


def load(folder: Path) -> Job:
    """The job of a run folder."""
    return Job.model_validate_json((Path(folder) / JOB).read_text())


def save(job: Job) -> None:
    """Write a job into its folder's ``job.json`` (replaced whole, never half-written: ``durable.write_atomic``)."""
    from adroit.core.durable import write_atomic
    write_atomic(Path(job.folder) / JOB, job.model_dump_json(indent=1))


@contextlib.contextmanager
def job_lock(folder: Path):
    """The folder's job lock: every change of a job's state is a read-modify-write under it (S18-15)."""
    with (Path(folder) / ".job.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def update(folder: Path, locked: bool = False, **fields) -> Job:
    """Change these fields of the job as it is now, under its lock (``locked``: the caller holds it). Whoever writes
    first, the other's fields survive: the launcher's process id and the runner's final status (S18-15)."""
    if not locked:
        with job_lock(folder):
            return update(folder, locked=True, **fields)
    job = load(folder).model_copy(update=fields)
    save(job)
    return job


def launch(command: list[str], folder: Path, title: str, confirmed_budget: float = 0.0, popen=subprocess.Popen,
           owner: str = "", approval: str = "") -> Job:
    """Start a command-line run in ``folder`` (detached). Raises BudgetNotConfirmed for an unconfirmed spend, and
    JobExists if the folder already holds a job (its ``job.json`` is created exclusively, so of two launches into one
    folder exactly one starts). A launch that fails before its run starts leaves the job failed with the reason; one
    whose launcher dies there is closed by ``poll`` (the recheck's RB20-02, 2026-10-20). ``approval``: how a paid run's
    spend was approved (``Job.approval``)."""
    cost = paid(command)
    if cost > 0 and cost > confirmed_budget + 1e-9:
        raise BudgetNotConfirmed(f"this run may spend ${cost:.2f}; the person confirmed ${confirmed_budget:.2f}")
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    from uuid import uuid4
    job = Job(title=title, kind=command[0], command=command, folder=str(folder), budget_usd=cost,
              launcher_pid=os.getpid(), owner=owner, acknowledged=False, attempt=uuid4().hex, directories=launched(),
              approval=approval if cost > 0 else "")
    try:
        with (folder / JOB).open("x") as stream:
            stream.write(job.model_dump_json(indent=1))
    except FileExistsError:
        raise JobExists(f"{folder} already holds a job; launch into a new folder") from None
    try:
        return _start(job, popen)
    except BaseException:                     # the run was not started (or this process is ending): say so
        update(folder, status="failed", finished=_now(), note="the launch failed before its run started")
        raise


def _start(job: Job, popen, locked: bool = False) -> Job:
    """Start the detached runner on a job already written, with the confirmed command's sha256 and the job's
    directory settings (module docstring), and record its process on the job as it now is: a runner that has already
    finished keeps its final status (S18-15)."""
    process = popen(["nice", "-n", "10", sys.executable, "-m", "adroit.ui.runner", job.folder,
                     command_sha256(job.command)],
                    cwd=str(PROJECT_ROOT), start_new_session=True, env=_run_environment(job.directories),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return update(Path(job.folder), locked=locked, pid=process.pid, runner_started=process_started(process.pid))


def _alive(pid: int) -> bool:
    """Whether the process runs; a finished child of this process is reaped (not left a zombie)."""
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


NOTHING_RUN = "cancelled before its run acknowledged its start: nothing was run"
UNPROVEN = ("processes {pids} are in a process group of its calculation's number ({group}), whose leader has ended: not "
            "proven to be its calculation's (another may lead a group of that number since), so not signalled; end "
            "them yourself if they are its")
START_UNPROVEN = ("processes {pids} are in a process group of its calculation's number ({group}), whose leader's start "
                  "cannot be proven the one its calculation recorded (not recorded, not a time, or not read): not "
                  "proven to be its calculation's, so not signalled; end them yourself if they are its")
RUNNER_UNPROVEN = ("its runner's process number ({pid}) is held by a process not proven to be its runner (its start is "
                   "not the one its launch recorded, or either cannot be read): not signalled; the run was asked to "
                   "stop by its control file")
UNRESOLVED = ("its runner ended without recording an end while its calculation still runs (processes {pids}): "
              "unresolved, not stopped; Cancel stops it, and nothing resumes until it has ended")
STILL_RUNNING = ("Its calculation still runs (processes {pids}) although its run has ended: unresolved, not stopped. "
                 "Cancel stops it, and nothing resumes until it has ended.")


def left_running(job: Job) -> str:
    """What a closed job's calculation still running is said as (``STILL_RUNNING``), "" where none runs: only a
    failed or cancelled job is asked, whose runner can have ended without ending it."""
    left = calculation_alive(job) if job.status in ("failed", "cancelled") else []
    return STILL_RUNNING.format(pids=", ".join(map(str, left))) if left else ""


SAME_START_S = 3.0          # a start recorded by the runner's clock and ``ps``'s, to the second, of one process


def _ps(*args: str) -> str:
    """``ps`` with these arguments, its dates in the C locale ("" where it lists nothing)."""
    done = subprocess.run(["ps", *args], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          env=_child({"LC_ALL": "C"}))
    return done.stdout if done.returncode == 0 else ""


def process_started(pid: int) -> float:
    """A process's start, in seconds since the epoch, as ``ps`` gives it (to the second); 0 where it does not run."""
    import time
    text = " ".join(_ps("-o", "lstart=", "-p", str(pid)).split()) if pid > 0 else ""
    try:
        return time.mktime(time.strptime(text, "%a %b %d %H:%M:%S %Y")) if text else 0.0
    except ValueError:
        return 0.0


def _group(pgid: int) -> list[int]:
    """The live processes of process group ``pgid`` (one that has ended and waits to be reaped is not live)."""
    members = []
    for line in _ps("-A", "-o", "pid=,pgid=,stat=").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == str(pgid) and not parts[2].startswith("Z"):
            members.append(int(parts[0]))
    return members


def _known(start) -> bool:
    """Whether a recorded start is a time: finite and after the epoch (0 is "not recorded")."""
    return isinstance(start, (int, float)) and math.isfinite(start) and start > 0


def _proven_start(recorded, pid: int) -> bool:
    """Whether process ``pid`` is the one whose start was ``recorded`` (module docstring): both starts times, within
    ``SAME_START_S``; an unknown one on either side proves nothing (DX-02)."""
    if not _known(recorded):
        return False
    now = process_started(pid)
    return _known(now) and abs(now - recorded) <= SAME_START_S


def calculation_alive(job: Job) -> list[int]:
    """The live processes of the job's calculation (module docstring): its group's, where the group is proven the
    job's (its leader alive with the recorded start time, both known: ``_proven_start``); [] otherwise. A group whose
    leader has ended, or whose leader's start is not proven, is not taken as the job's (``calculation_unproven``;
    DW-03, DX-02)."""
    if not job.calculation:
        return []
    members = _group(job.calculation)
    if job.calculation not in members or not _proven_start(job.calculation_started, job.calculation):
        return []                             # its leader ended, another process has the number, or not proven
    return members


def calculation_unproven(job: Job) -> list[int]:
    """The live processes of a group of the job's calculation's number not proven the job's: its leader has ended
    (what the calculation left, or another's group made since, which nothing here can tell apart: DW-03), or its
    leader's start is not proven (DX-02); named (``unproven_note``), never signalled."""
    if not job.calculation:
        return []
    members = _group(job.calculation)
    if not members or (job.calculation in members and _proven_start(job.calculation_started, job.calculation)):
        return []
    if job.calculation in members and not _known(process_started(job.calculation)):
        members = _group(job.calculation)     # its start not read: it may have just ended (a cancel's own stop)
    return members


def unproven_note(job: Job, members: list[int]) -> str:
    """What an unproven group (``calculation_unproven``) is said as: its leader ended (``UNPROVEN``), or its leader's
    start not proven (``START_UNPROVEN``)."""
    words = UNPROVEN if job.calculation not in members else START_UNPROVEN
    return words.format(pids=", ".join(map(str, members)), group=job.calculation)


def _runner_runs(job: Job) -> bool:
    """Whether the job's runner may still run, for its status: its process alive and, where its launcher recorded its
    start, with that start (a number recycled since is a runner gone: DW-03). A job from before that record is read by
    its process alone, as before; it is never signalled (``runner_alive``)."""
    return _alive(job.pid) and (not _known(job.runner_started) or _proven_start(job.runner_started, job.pid))


def runner_alive(job: Job) -> bool:
    """Whether the job's runner runs, proven: its process alive with the start its launcher recorded
    (``runner_started``), both starts known (``_proven_start``). A job without that record (from before it), or with
    one that is not a time, never proves it (DW-03, DX-02)."""
    return bool(job.pid and _alive(job.pid) and _proven_start(job.runner_started, job.pid))


def stop_calculation(job: Job, forcibly: bool = False) -> list[int]:
    """Signal the job's calculation's group, if it still runs (SIGTERM, or SIGKILL ``forcibly``); its processes."""
    members = calculation_alive(job)
    if members:
        try:
            os.killpg(job.calculation, signal.SIGKILL if forcibly else signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    return members


def poll(folder: Path, locked: bool = False) -> Job:
    """The job's status; a running job whose process has vanished without a word is marked failed, under the job's
    lock, so a final status the runner wrote meanwhile is kept (``locked``: the caller holds it). A job whose run has
    not acknowledged its start is starting for ``LAUNCH_GRACE_SECONDS`` from its start; after that it is failed,
    "launch not confirmed", never launched again: its run, if it starts late, finds it closed and does nothing
    (``runner.run``; the recheck's RB20-02: it had waited forever; the auditor's RC20-02, 2026-10-20: a live process holding
    the launcher's PID had kept it waiting; C21-06, 2026-10-21: so had the spawned process's PID, which is recorded
    before the run starts)."""
    job = load(folder)
    if job.status == "running" and (job.pid and not _runner_runs(job) or _launch_lost(job)):
        if not locked:
            with job_lock(folder):
                return poll(folder, locked=True)
        job = load(folder)                    # the runner may have just written its end, or its acknowledgement
        if job.status == "running" and job.pid and not _runner_runs(job):
            job = _closed(folder, job)
        elif job.status == "running" and _launch_lost(job):
            job = _closed(folder, job, LAUNCH_NOT_CONFIRMED)
    return job


def _closed(folder: Path, job: Job, why: str = "") -> Job:
    """Close a running job whose run ended without recording its end, under its lock: cancelled where a cancel was
    asked (before its run acknowledged its start, nothing was run: ID-02), failed otherwise; unresolved, its processes
    named, where its calculation still runs (ID-01)."""
    left, unproven = calculation_alive(job), calculation_unproven(job)
    if cancelled(folder):
        status = "cancelled"
        note = control_unreadable(folder) or (NOTHING_RUN if not job.acknowledged else "")
    else:
        status, note = "failed", why
    if left:
        note = "; ".join(filter(None, [note, UNRESOLVED.format(pids=", ".join(map(str, left)))]))
    if unproven:
        note = "; ".join(filter(None, [note, unproven_note(job, unproven)]))
    return update(folder, locked=True, status=status, finished=_now(), note=note)


LAUNCH_NOT_CONFIRMED = f"launch not confirmed: its run did not start within {LAUNCH_GRACE_SECONDS:g} s"


def _launch_lost(job: Job) -> bool:
    """Whether a job whose run has not acknowledged its start is past its bound (module docstring): neither the
    launcher's PID nor the spawned process's is consulted, since a PID is not an acknowledgement. A job from before
    acknowledgements (``acknowledged`` None) is starting while its PID is 0, as then."""
    waiting = job.acknowledged is False or (job.acknowledged is None and not job.pid)
    age = (datetime.now() - datetime.fromisoformat(job.started)).total_seconds()
    return waiting and age > LAUNCH_GRACE_SECONDS


def cancel(folder: Path) -> None:
    """Ask the run to stop, and end its process group, and its calculation's (module docstring): the calculation is
    stopped whatever the job's status, since it may have outlived its runner; a second cancel ends it forcibly."""
    folder = Path(folder)
    from adroit.core.durable import write_atomic
    again = _asked_quietly(folder)
    write_atomic(folder / CONTROL, json.dumps({"cancel": True, "at": _now()}))
    job = load(folder)
    notes = []
    if job.status == "running" and job.pid:
        if runner_alive(job):                 # proven its runner (DW-03)
            try:
                os.killpg(os.getpgid(job.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        elif _alive(job.pid):
            notes.append(RUNNER_UNPROVEN.format(pid=job.pid))
    stopped = stop_calculation(job, forcibly=again)
    if stopped and job.status in DONE:       # a calculation its runner left: said on the job, under its lock
        notes.append(f"{'stopped forcibly' if again else 'asked to stop'} by Cancel at {_now()} (processes "
                     f"{', '.join(map(str, stopped))})")
    if unproven := calculation_unproven(job):
        notes.append(unproven_note(job, unproven))
    if notes:
        with job_lock(folder):
            now = load(folder)
            fresh = [n for n in notes if n not in (now.note or "")]
            if fresh:
                update(folder, locked=True, note="; ".join(filter(None, [now.note, *fresh])))


def _asked_quietly(folder: Path) -> bool:
    """Whether a cancel was asked before (an unreadable control file: no)."""
    try:
        return _asked(folder)
    except (OSError, ValueError, AttributeError):
        return False


def cancelled(folder: Path) -> bool:
    """Whether the run has been asked to stop (``control.json``). A control file that cannot be read stops it too
    (``control_unreadable`` says why): it is never permission to keep going (the consolidation plan's M3; it had
    raised, ending the runner before it wrote the job's final status)."""
    return bool(control_unreadable(folder)) or _asked(folder)


def _asked(folder: Path) -> bool:
    path = Path(folder) / CONTROL
    return path.exists() and bool(json.loads(path.read_text()).get("cancel", False))


def control_unreadable(folder: Path) -> str:
    """Why the folder's ``control.json`` cannot be read as a request ("" if it is absent or reads). Absent is no entry at
    all (``durable.absent``): a link there that leads nowhere cannot be read, and stops the run (the auditor's DM recheck,
    DN-01: it had read as no request to stop, and the next request was dispatched)."""
    from adroit.core.durable import absent
    path = Path(folder) / CONTROL
    if absent(path):
        return ""
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        from adroit.core.durable import reason
        return f"its control file, {CONTROL}, cannot be read ({reason(error)}): stopped as if cancelled"
    if not isinstance(value, dict):
        return f"its control file, {CONTROL}, is not a request: stopped as if cancelled"
    return ""


def read_log(folder: Path, lines: int = 40) -> tuple[list[str], str]:
    """(the last ``lines`` lines of the run's log; why it cannot be read, or ""): no lines and "" where nothing at all
    is at its path (``durable.absent``); where an entry there cannot be read (a folder, a link to one or to nothing, a
    file it may not read), no lines and why, named (the auditor's DN recheck, DO-02, 2026-11-08: the log was read raw, and
    one that could not be read had made the run's whole page a server error)."""
    from adroit.core.durable import absent, linked, reason
    log = Path(folder) / LOG
    if absent(log):
        return [], ""
    try:
        return log.read_text(errors="replace").splitlines()[-lines:], ""
    except OSError as error:
        return [], f"its log, {LOG}, cannot be read ({linked(log)}{reason(error)})"


def tail(folder: Path, lines: int = 40) -> list[str]:
    """The last ``lines`` lines of the run's log, the command's own words only: none where it cannot be read, whose why
    ``read_log`` gives apart, never as a line of the log (the auditor's DO recheck, DP-03, 2026-11-09: the reason had been
    returned as a log line, and the Activity page's diagnosis read a log that could not be opened as a missing tool)."""
    return read_log(folder, lines)[0]


def snapshot(folder: Path) -> dict:
    """What the live view shows. A log that cannot be read is named (``log_unreadable``), and the rest is shown: its
    status, its cost and its continuation (DO-02); a calculation still running after its run has ended
    (``left_running``; ID-01)."""
    job = poll(folder)
    start = datetime.fromisoformat(job.started)
    end = datetime.fromisoformat(job.finished) if job.finished else datetime.now()
    progress, unreadable = _progress(Path(folder))
    log, log_unreadable = read_log(Path(folder))
    from adroit.orchestrator.accounting import cost          # the one interpretation of money (M2)
    return {"job": job, "elapsed_s": (end - start).total_seconds(), "cost": cost(folder, job),
            "log": log, "log_unreadable": log_unreadable, "report": (Path(folder) / "report.md").exists(),
            "progress": progress, "progress_unreadable": unreadable, "left_running": left_running(job)}


def _progress(folder: Path) -> tuple[Progress | None, str]:
    """(the run's progress record, or None; why it cannot be read, or ""): a damaged one is named on the live view,
    which goes on refreshing (the consolidation plan's M3)."""
    path = folder / "progress.json"
    if not path.exists():
        return None, ""
    try:
        return Progress.model_validate_json(path.read_text()), ""
    except (OSError, ValueError) as error:
        from adroit.core.durable import reason
        return None, f"its progress record, progress.json, cannot be read ({reason(error)})"


def resume(folder: Path, popen=subprocess.Popen) -> Job:
    """Resume an interrupted Track 1 command through the existing detached runner: the same job (its folder, title,
    kind and confirmed budget), with ``--resume``. The check and the restart hold the folder's lock, so of two resumes
    one starts and the other finds the job running."""
    folder = Path(folder)
    with job_lock(folder):
        job = poll(folder, locked=True)
        if job.kind != "track1" or job.status not in ("failed", "cancelled"):
            raise ValueError("Only an interrupted Track 1 job can be resumed")
        left = calculation_alive(job)
        if left:                              # its earlier calculation still runs (ID-01): never two at once
            raise ValueError(f"Its earlier run's calculation still runs (processes {', '.join(map(str, left))}): "
                             "Cancel it, then resume once it has ended")
        if not (folder / ".track1-checkpoint/manifest.json").exists():
            raise ValueError("This run has no scientific checkpoint")
        with (folder / "job_history.jsonl").open("a") as stream:
            stream.write(job.model_dump_json() + "\n")
        (folder / CONTROL).unlink(missing_ok=True)
        command = job.command if "--resume" in job.command else [*job.command, "--resume"]
        from uuid import uuid4
        restarted = update(folder, locked=True, command=command, status="running", pid=0, runner_started=0.0,
                           returncode=None,
                           started=_now(), finished="", launcher_pid=os.getpid(), note="", acknowledged=False,
                           calculation=0, calculation_started=0.0,   # its runner records its own (ID-01)
                           attempt=job.attempt or uuid4().hex,       # the same attempt, continued (DC-01)
                           directories=job.directories or launched())   # the folders it was launched with (IE-01)
        try:
            return _start(restarted, popen, locked=True)
        except BaseException as error:        # the resumed run was not started: closed with the reason (RC20-02)
            update(folder, locked=True, status="failed", finished=_now(),
                   note=f"the resume failed before its run started: {type(error).__name__}: {error}"[:300])
            raise


def polled(listed: list[Job]) -> tuple[list[Job], list]:
    """(each listed job as ``poll`` reads it now, in order; each that cannot be read now, named with why:
    ``durable.read_each``). A record damaged after it was listed is named, never a page's failure (NP17-03)."""
    from adroit.core.durable import read_each
    return read_each([Path(j.folder) / JOB for j in listed], lambda path: poll(path.parent))


def jobs(root: Path) -> list[Job]:
    """Every readable job under ``root``, newest first (``listing``)."""
    return listing(root)[0]


def listing(root: Path):
    """(every readable job under ``root``, newest first; each job record that cannot be read, named with why:
    ``durable.read_each``). The consistency audit's CA-07 (2026-10-24): one job record holding ``{}`` made the Home
    and Studies pages fail. Opening a job (``load``) stays strict."""
    from adroit.core.durable import read_each
    found, damaged = read_each(sorted(Path(root).rglob(JOB)), lambda p: load(p.parent))
    return sorted(found, key=lambda j: j.started, reverse=True), damaged


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

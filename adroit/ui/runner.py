"""The detached runner of one workbench job (DM15): the command line, then the job's final status.

    python -m adroit.ui.runner FOLDER COMMAND_SHA256

Reads ``FOLDER/job.json``, runs ``adroit <command>`` with its output in
``FOLDER/log.txt``, and writes the status (completed, budget_stopped, failed or
cancelled) and the exit code back when the command ends. It runs only the
command whose sha256 its launcher confirmed (``engine``'s module docstring).

Its calculation, the command line, runs in a process group of its own, which every process it starts joins; the job
records that group's leader and its start time before the command begins (``engine``'s module docstring; a feature
audit's ID-01, 2026-11-10). The command is started through ``GATE``, which waits for the runner's word that the record
is written and replaces itself with the command line, the same process; without that word (the runner ended first) it
ends, having run nothing. So no calculation runs that its job does not name. The runner starts no other process: it
records the calculation's start by its own clock, and ends what its group leaves by signals alone (``_left``).
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from adroit.core.config import run_environment as _run_environment
from adroit.core.receipts import BUDGET_STOPPED
from adroit.ui import engine


REFUSED = ("refused: the job's command is not the one its launch confirmed (changed since, or no confirmation "
           "given); not run")
GATE = ("import os, sys\n"
        "word = os.read(int(sys.argv[1]), 1)\n"
        "os.close(int(sys.argv[1]))\n"
        "if word != b'1':\n"
        "    os._exit(1)\n"
        "os.execv(sys.executable, [sys.executable, '-m', 'adroit.orchestrator.cli', *sys.argv[2:]])\n")
SIGNALLED = "its runner was stopped by a signal, not by Cancel"


def run(folder: Path, confirmed_sha256: str = "") -> engine.Job:
    """Run the folder's job to its end; a cancel (SIGTERM) ends the command and is recorded. Under the job's lock it
    first acknowledges its start on the job (its process, ``Job.acknowledged``), and does nothing if the job is no
    longer running (closed meanwhile as a launch not confirmed, ``engine.poll``), was cancelled before it started (the
    recheck's RB20-02) or is past its start's bound (``engine.LAUNCH_GRACE_SECONDS``: it closes it, C21-06); it
    refuses a command that is not the one its launcher confirmed, ``confirmed_sha256`` (the auditor's RC20-01, 2026-10-20: a
    job's command edited between launch and start, its budget raised from $0.50 to $5, had run). The command it runs
    is the one it checked, its own copy (C21-05, 2026-10-21: an edit landing between the check and the start had run),
    and the job records that command and its budget at the end. The command learns its job's folder
    (ADROIT_JOB_FOLDER), where a paid command keeps its own paid ledger and a file output its identity
    (``preflight.job_ledger``; the workflow audit's WA-03 and WA-05, 2026-10-24), and its job's attempt
    (ADROIT_JOB_ATTEMPT), which the study record it publishes there names (``studies.record``; DC-01), as do its log
    and each record of its money (the auditor's DD recheck, DE-01, 2026-11-05)."""
    folder = Path(folder)
    with engine.job_lock(folder):
        job = engine.load(folder)
        if job.status != "running":
            return job
        if engine.cancelled(folder):
            return engine.update(folder, locked=True, status="cancelled", finished=engine._now(),
                                 note=engine.control_unreadable(folder))
        if engine._launch_lost(job):
            return engine.update(folder, locked=True, status="failed", finished=engine._now(),
                                 note=engine.LAUNCH_NOT_CONFIRMED)
        command = tuple(job.command)                       # the command checked is the command run
        if not confirmed_sha256 or engine.command_sha256(list(command)) != confirmed_sha256:
            return engine.update(folder, locked=True, status="failed", finished=engine._now(), note=REFUSED)
        job = engine.update(folder, locked=True, pid=os.getpid(), acknowledged=True)
        if tuple(job.command) != command:                  # edited since the check (a direct edit ignores the lock)
            return engine.update(folder, locked=True, status="failed", finished=engine._now(), note=REFUSED)
    with (folder / engine.LOG).open("w") as log:
        log.write(f"$ adroit {' '.join(command)}\n")
        if job.attempt:              # whose log it is, read with its lines (``accounting.LOG_ATTEMPT``; DE-01)
            log.write(f"# run attempt {job.attempt}\n")
        log.flush()
        code, signalled, left = _calculate(folder, job, command, log)
    status = ("cancelled" if engine.cancelled(folder) else "completed" if code == 0
              else "budget_stopped" if code == BUDGET_STOPPED else "failed")
    notes = [engine.control_unreadable(folder) if status == "cancelled" else "",
             SIGNALLED if signalled and status != "cancelled" else "",
             f"processes its calculation left when its command line ended were stopped (its process group, {left})"
             if left else ""]
    note = {"note": "; ".join(filter(None, notes))} if any(notes) else {}
    return engine.update(folder, status=status, returncode=code, finished=engine._now(),     # under the job's lock
                         command=list(command), budget_usd=engine.paid(list(command)), **note)


def _calculate(folder: Path, job: engine.Job, command: tuple, log) -> tuple[int, bool, int]:
    """Run the command in a process group of its own, named on the job before it begins (module docstring); a SIGTERM
    to the runner ends that whole group. (Its exit code; whether the runner was signalled; the group, where processes
    of it were left when its leader ended, which are ended too (``_left``), else 0.)"""
    held: dict = {"signalled": False, "child": None}

    def stop(*_) -> None:
        held["signalled"] = True
        child = held["child"]
        if child is not None and child.returncode is None and child.pid:     # its group: it leads it, unreaped
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
    signal.signal(signal.SIGTERM, stop)
    read, write = os.pipe()
    try:
        try:
            held["child"] = child = subprocess.Popen(
                [sys.executable, "-c", GATE, str(read), *command], stdout=log, stderr=subprocess.STDOUT,
                pass_fds=(read,), start_new_session=True,
                env=_run_environment({"ADROIT_JOB_FOLDER": str(folder.resolve()), "ADROIT_JOB_ATTEMPT": job.attempt}))
        finally:
            os.close(read)
        engine.update(folder, calculation=child.pid, calculation_started=time.time())
        if not held["signalled"]:
            with contextlib.suppress(BrokenPipeError):                       # its gate has ended: nothing to begin
                os.write(write, b"1")                                        # recorded: the command may begin
    finally:
        os.close(write)
    code = child.wait()
    return code, held["signalled"], child.pid if _left(child.pid) else 0


def _left(group: int) -> bool:
    """End what is left of the calculation's process group once its leader has ended: a second to end alone, then
    SIGTERM, then SIGKILL; whether any process was left. Asked at once, the group's number is its own: no process is
    given it while any of the group lives, and process numbers are given in turn, so it is not another's seconds after
    its leader ended (``engine.calculation_alive`` guards a later asking by its start). Signals alone: no process is
    started (module docstring)."""
    if not group or _ended(group, 1.0):
        return False
    for sig, seconds in ((signal.SIGTERM, 5.0), (signal.SIGKILL, 2.0)):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(group, sig)
        if _ended(group, seconds):
            break
    return True


def _ended(group: int, seconds: float) -> bool:
    """Whether the process group ``group`` has no process left within ``seconds`` (asked by signal 0: none is sent)."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


if __name__ == "__main__":
    run(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "")

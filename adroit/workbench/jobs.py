"""The workbench's jobs: a pipeline run in the background, one at a time, into its own folder.

A job's state is written to ``status.json`` in its folder, so the runs survive a
restart of the workbench; a folder written by the command line (a report with
no status file) is listed as a finished run too.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from pydantic import Field

from adroit.core.state import StrictModel
from adroit.orchestrator.runs import slug, unique_folder

STATUS_FILE = "status.json"
KINDS = {"exclusion": "Path 1: library card", "signal": "Path 2: a signal", "lagrangian": "Path 1: bespoke model"}


class Job(StrictModel):
    """One run of a pipeline, launched from the workbench (or found on disk)."""

    id: str                                   # the folder's name
    kind: str                                 # exclusion, signal, lagrangian, or other
    title: str
    status: str = "queued"                    # queued, running, done, failed
    created: str = ""
    finished: str = ""
    error: str = ""
    inputs: dict = Field(default_factory=dict)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Board:
    """The jobs of one workbench: submitted, run one at a time, and recorded in their folders."""

    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self._pool = ThreadPoolExecutor(max_workers=1)        # the owner's limit: heavy jobs one at a time
        self._lock = threading.Lock()

    def submit(self, kind: str, title: str, inputs: dict, work: Callable[[Path], object]) -> Job:
        """Queue ``work(folder)`` in a new folder of its own (``runs.unique_folder``; R18-3); returns the job at once."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        folder = unique_folder(self.runs_dir, f"{stamp}_{kind}_{slug(title)[:80]}")
        job = Job(id=folder.name, kind=kind, title=title, created=_now(), inputs=inputs)
        self._save(job)
        self._pool.submit(self._run, job, work)
        return job

    def _run(self, job: Job, work: Callable[[Path], object]) -> None:
        self._save(job.model_copy(update={"status": "running"}))
        try:
            work(self.runs_dir / job.id)
            done = job.model_copy(update={"status": "done", "finished": _now()})
        except Exception as error:  # noqa: BLE001 - any failure is shown on the job's page
            done = job.model_copy(update={"status": "failed", "finished": _now(),
                                          "error": "".join(traceback.format_exception_only(error)).strip()})
        self._save(done)

    def _save(self, job: Job) -> None:
        """The job's status file, replaced whole (``durable.write_atomic``): never cut short by an interrupted write
        (AL2-16)."""
        from adroit.core.durable import write_atomic
        with self._lock:
            write_atomic(self.runs_dir / job.id / STATUS_FILE, job.model_dump_json(indent=1))

    def get(self, job_id: str) -> Job | None:
        """A job by its folder's name, from its status file (or as a finished command-line run)."""
        return read(self.runs_dir / job_id)

    def wait(self) -> None:
        """Block until every queued job has finished (for tests and shutdown)."""
        self._pool.submit(lambda: None).result()


def read(folder: Path) -> Job | None:
    """The job of a run folder: its status file, or a finished run if it holds only a report. A status file that
    cannot be read (cut short or damaged) gives an "unreadable" job saying so, never an error that stops the runs page
    (AL2-16); the file is left as it is."""
    status = folder / STATUS_FILE
    if status.is_file():
        try:
            return Job.model_validate_json(status.read_text())
        except (OSError, ValueError) as error:              # a pydantic ValidationError is a ValueError
            when = datetime.fromtimestamp(status.stat().st_mtime).isoformat(timespec="seconds")
            return Job(id=folder.name, kind=next((k for k in KINDS if f"_{k}_" in folder.name), "other"),
                       title=folder.name, status="unreadable", created=when,
                       error=f"its {STATUS_FILE} cannot be read ({type(error).__name__}); the run's files are kept as "
                             "they are")
    if (folder / "report.md").is_file():
        kind = next((k for k in KINDS if folder.name.startswith(k)), "other")
        when = datetime.fromtimestamp((folder / "report.md").stat().st_mtime).isoformat(timespec="seconds")
        return Job(id=folder.name, kind=kind, title=folder.name, status="done", created=when, finished=when)
    return None


def list_runs(runs_dir: Path) -> list[Job]:
    """Every run in the runs directory, newest first."""
    if not runs_dir.is_dir():
        return []
    jobs = [job for folder in runs_dir.iterdir() if folder.is_dir() and (job := read(folder))]
    return sorted(jobs, key=lambda j: j.created, reverse=True)

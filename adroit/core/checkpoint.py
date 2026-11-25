"""Atomic, identity-bound scientific checkpoints and durable progress."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
from typing import NamedTuple, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

from adroit.core.state import StrictModel

T = TypeVar("T", bound=BaseModel)


class CheckpointMismatch(ValueError):
    """A checkpoint does not establish reuse under the current inputs/software."""


class StageMark(StrictModel):
    """One stage of a run as it stands: running, done or failed, with its last count (``completed`` of ``total``; 0
    of 0 where the stage counts nothing)."""
    state: str = "running"
    completed: int = 0
    total: int = 0


NOT_STAGES = ("starting", "completed")


class Progress(StrictModel):
    """A run's durable progress: phase, status, points completed of the total, a detail line, the time of the last
    update, and each phase's duration (s). ``plan``: the stages the run will go through, declared at its start;
    ``stages``: each stage reached, and how it stands (the owner, 2026-11-23: the live page's checklist). Both are
    empty in a record written before them, which reads as before."""
    phase: str = "starting"
    status: str = "running"
    completed: int = 0
    total: int = 0
    detail: str = ""
    updated: str = ""
    durations_s: dict[str, float] = Field(default_factory=dict)
    plan: list[str] = Field(default_factory=list)
    stages: dict[str, StageMark] = Field(default_factory=dict)


class Manifest(StrictModel):
    """A checkpoint's identity, the inputs and dependencies it was computed from, and whether it was invalidated."""
    schema_version: int = 1
    identity: str
    inputs: dict
    dependencies: dict
    invalidated: bool = False
    context: dict = Field(default_factory=dict)


def atomic_json(path: Path, value: dict) -> None:
    """Write one complete JSON document and publish it whole and synced (``durable.write_atomic``: the temporary file
    synced before it replaces the old one, the folder after), the bytes as ``json.dump`` writes them, in UTF-8. A
    value that cannot be serialised raises before anything is written, and a failed write or sync leaves the previous
    file whole, with no temporary file (the gap plan's G1, 2026-10-25: this writer had not synced, the limitation
    the consolidation audit noted). One sync per write: a run lock (``run_lock``) still guards a read-modify-write."""
    from adroit.core.durable import write_atomic
    write_atomic(path, json.dumps(value, ensure_ascii=False, allow_nan=True))


class Chronology(NamedTuple):
    """When the calculation of a result a run holds started and completed, as its checkpoint holds it, in the run that
    holds it: read back with the artifact (``restored``: a resume), from that one validated read, its dates as saved
    with it ("" where it was saved without them, by ADROIT before); or of the calculation this run completed
    (``Checkpoint.save``). The auditor's DB/VI recheck, DC-03 (2026-11-03): the dates had been read again from the file,
    checked only against the digest it stores, after the artifact was restored."""
    started: str
    completed: str
    restored: bool


def _what_changed(saved: "Manifest", inputs: dict, dependencies: dict) -> str:
    """The refusal's detail: which of the request's settings differ from the checkpoint's (the halo named first: a
    changed halo is a new scientific request, never resumed into one calculated with another; halo phase 1), and
    whether the software or calculation data did."""
    inputs, dependencies = json.loads(json.dumps(inputs)), json.loads(json.dumps(dependencies))   # as saved
    keys = sorted(k for k in {*saved.inputs, *inputs} if saved.inputs.get(k) != inputs.get(k))
    parts = []
    if "halo" in keys:
        parts.append("the halo differs from the one its checkpoint was calculated with (a changed halo is a new "
                     "request: start a new run)")
    if [k for k in keys if k != "halo"]:
        parts.append(f"the request's {', '.join(k for k in keys if k != 'halo')} differ")
    if saved.dependencies != dependencies:
        parts.append("the software or calculation data differ")
    if saved.invalidated:
        parts.append("the checkpoint was invalidated")
    return f": {'; '.join(parts)}" if parts else ""


class Checkpoint:
    """One locked run's typed artifacts, identified by all supplied dependencies."""

    def __init__(self, folder: Path, inputs: dict, dependencies: dict, resume: bool = False,
                 context: dict | None = None) -> None:
        self.folder = folder
        self.root = folder / ".track1-checkpoint"
        material = json.dumps({"inputs": inputs, "dependencies": dependencies}, sort_keys=True, allow_nan=False)
        identity = hashlib.sha256(material.encode()).hexdigest()
        path = self.root / "manifest.json"
        if resume:
            if not path.exists():
                raise CheckpointMismatch("No Track 1 checkpoint exists in this folder")
            saved = Manifest.model_validate_json(path.read_text())
            if saved.invalidated or saved.identity != identity:
                raise CheckpointMismatch("Resume refused: model, settings, software or calculation data changed"
                                         + _what_changed(saved, inputs, dependencies))
            self.manifest = saved
        else:
            if self.root.exists():
                history = folder / ".track1-history"
                history.mkdir(exist_ok=True)
                self.root.rename(history / uuid4().hex)
            self.manifest = Manifest(identity=identity, inputs=inputs, dependencies=dependencies, context=context or {})
            atomic_json(path, self.manifest.model_dump(mode="json"))
        progress = folder / "progress.json"
        self.progress = Progress.model_validate_json(progress.read_text()) if resume and progress.exists() else Progress()
        # each artifact loaded or saved, by its payload's digest: its dates (``chronology``)
        self.chronologies: dict[tuple[str, str, str], Chronology] = {}

    def _path(self, phase: str, key: str) -> Path:
        if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", value) and value not in (".", "..") for value in (phase, key)):
            raise ValueError("Invalid checkpoint artifact name")
        return self.root / phase / f"{key}.json"

    def load(self, phase: str, key: str, model: type[T]) -> T | None:
        """Load a typed artifact only when its identity and content digest agree; its dates, of the same read, are
        kept (``chronology``)."""
        path = self._path(phase, key)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text())
            digest = hashlib.sha256(json.dumps(value["payload"], sort_keys=True).encode()).hexdigest()
            if value["identity"] != self.manifest.identity or digest != value["sha256"]:
                raise CheckpointMismatch("Checkpoint identity/content mismatch")
            loaded = model.model_validate(value["payload"])
        except (KeyError, TypeError, ValueError) as error:
            raise CheckpointMismatch(f"Invalid checkpoint artifact: {phase}/{key}") from error
        self.chronologies[(phase, key, payload_digest(loaded))] = Chronology(
            str(value.get("calculation_started_at") or ""), str(value.get("calculation_completed_at") or ""), True)
        return loaded

    def save(self, phase: str, key: str, value: BaseModel, dates: tuple[str, str] | None = None) -> None:
        """Publish a completed typed artifact with its bound content digest; with ``dates`` (when its calculation started
        and completed, UTC), those dates in the same file, so that a resume restoring it restores when it was calculated
        (``chronology``)."""
        payload = value.model_dump(mode="json")
        digest = payload_digest(value)
        when = {"calculation_started_at": dates[0], "calculation_completed_at": dates[1]} if dates else {}
        atomic_json(self._path(phase, key), {"identity": self.manifest.identity, "sha256": digest, "payload": payload,
                                             **when})
        self.chronologies[(phase, key, digest)] = Chronology(*(dates or ("", "")), False)

    def chronology(self, phase: str, key: str, value: BaseModel) -> Chronology | None:
        """The dates of the artifact ``phase/key`` that is ``value``, as this run holds it: read back with it, or saved
        with it (``load``, ``save``), whatever has been saved there since; None where this run has neither loaded nor
        saved that value."""
        return self.chronologies.get((phase, key, payload_digest(value)))

    def started(self, now: str) -> str:
        """When this checkpoint's calculation started: as its manifest records it, where it was made by a run that
        recorded it (``context['calculation_started_at']``); else ``now``, the start of the process resuming it."""
        return str(self.manifest.context.get("calculation_started_at") or now)

    def update(self, phase: str, completed: int = 0, total: int = 0, detail: str = "",
               status: str = "running") -> None:
        """Publish durable phase/point progress for both terminal and workbench."""
        announce = phase != self.progress.phase or completed == total or (completed > 0 and completed % 10 == 0)
        stages = _marked(self.progress, phase, completed, total, status)
        self.progress = self.progress.model_copy(update={"phase": phase, "completed": completed, "total": total,
                                                       "detail": detail, "status": status, "stages": stages,
                                                       "updated": datetime.now(timezone.utc).isoformat()})
        atomic_json(self.folder / "progress.json", self.progress.model_dump(mode="json"))
        if announce:
            print(f"Track 1 {phase}: {completed}/{total} · {detail}", flush=True)

    def declare(self, plan: list[str]) -> None:
        """The stages this run will go through, in order, for the live page's checklist (a resumed run keeps those it
        has reached)."""
        self.progress = self.progress.model_copy(update={"plan": list(plan)})
        atomic_json(self.folder / "progress.json", self.progress.model_dump(mode="json"))

    def invalidate(self) -> None:
        """Permanently refuse this epoch after dependencies changed during execution."""
        self.manifest.invalidated = True
        atomic_json(self.root / "manifest.json", self.manifest.model_dump(mode="json"))


def _marked(progress: Progress, phase: str, completed: int, total: int, status: str) -> dict[str, StageMark]:
    """The stages after an update: a stage left behind is done with its last count; the current one running (or
    failed); a completed run's planned stages done (a stage it read from its checkpoint had been done before)."""
    stages = dict(progress.stages)
    previous = progress.phase
    if previous != phase and previous not in NOT_STAGES and previous in stages and stages[previous].state == "running":
        stages[previous] = stages[previous].model_copy(update={"state": "done"})
    if status == "completed":
        for name in progress.plan:
            if stages.get(name, StageMark()).state != "failed":
                stages[name] = stages.get(name, StageMark()).model_copy(update={"state": "done"})
    elif phase not in NOT_STAGES:
        stages[phase] = StageMark(state="failed" if status == "failed" else "running", completed=completed, total=total)
    return stages


def payload_digest(value: BaseModel) -> str:
    """The digest a checkpoint keeps of a typed artifact's payload (``Checkpoint.save``)."""
    return hashlib.sha256(json.dumps(value.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


@contextmanager
def run_lock(folder: Path):
    """Refuse concurrent writers in one folder: a run's output folder, a session's (its budget and paid ledger) or a
    library's. The refusal names the folder, not a kind of run (it had said "A Track 1 run" for a budget's folder too;
    the CO-04/CO-05 repairs, 2026-10-25). The lock file keeps its name, so a process already holding it still does."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".track1.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"Another ADROIT process is already active in {folder} (a run, a session's paid step "
                               "or a library change); try again when it has finished") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

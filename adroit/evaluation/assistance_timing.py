"""Paired researcher timing with explicit attestation, pauses and quality controls."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field

from adroit.core.state import StrictModel


class ResearcherSession(StrictModel):
    """Self-recorded active effort; automated runtime is not researcher effort."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    participant: str
    task: str
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    condition: Literal["manual", "assisted"]
    started: datetime
    last_mark: datetime
    phase: Literal["active", "paused", "finished"] = "active"
    active_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    researcher_attested: bool = False
    task_success: bool | None = None
    api_cost_usd: float = Field(default=0, ge=0, allow_inf_nan=False)


class TimingSummary(StrictModel):
    """Only quality-matched, attested pairs can estimate time saved."""

    sessions: int
    paired_completed_tasks: int = 0
    excluded: list[str] = Field(default_factory=list)
    reasons: dict[str, str] = Field(default_factory=dict)   # an excluded session's id → why
    paired_seconds_saved: list[float] = Field(default_factory=list)
    pairs: list[dict] = Field(default_factory=list)          # each pair's participant, task and seconds saved
    mean_seconds_saved: float | None = None
    api_cost_usd: float = 0.0                                # every assisted session's, paired or not
    interpretation: str = (
        "descriptive paired effort; not a causal claim without counterbalanced researcher trials"
    )


def start(
    participant: str,
    task: str,
    input_hash: str,
    condition: Literal["manual", "assisted"],
    now: datetime | None = None,
) -> ResearcherSession:
    """Begin a researcher-controlled active timer, with an immutable task identity."""
    mark = now or datetime.now(timezone.utc)
    if mark.tzinfo is None:
        raise ValueError("timezone-aware timing required")
    return ResearcherSession(
        participant=participant,
        task=task,
        input_hash=input_hash,
        condition=condition,
        started=mark,
        last_mark=mark,
    )


def transition(
    session: ResearcherSession,
    action: Literal["pause", "resume", "finish"],
    *,
    attest: bool = False,
    success: bool | None = None,
    now: datetime | None = None,
) -> ResearcherSession:
    """Exclude pauses, reject clock reversal, and require quality/attestation at finish."""
    mark = now or datetime.now(timezone.utc)
    if mark.tzinfo is None or mark < session.last_mark:
        raise ValueError("invalid or reversed timing clock")
    if session.phase == "finished":
        raise ValueError("finished timing session is immutable")
    if action == "resume" and session.phase != "paused":
        raise ValueError("resume requires a paused session")
    if action == "pause" and session.phase != "active":
        raise ValueError("pause requires an active session")
    if action == "finish" and (not attest or success is None):
        raise ValueError("finish needs researcher attestation and an explicit quality outcome")
    seconds = (
        session.active_seconds + (mark - session.last_mark).total_seconds()
        if session.phase == "active"
        else session.active_seconds
    )
    return session.model_copy(
        update={
            "active_seconds": seconds,
            "last_mark": mark,
            "phase": "active"
            if action == "resume"
            else "paused"
            if action == "pause"
            else "finished",
            "researcher_attested": attest if action == "finish" else False,
            "task_success": success if action == "finish" else None,
        }
    )


def summarize(sessions: list[ResearcherSession]) -> TimingSummary:
    """Aggregate matching successful pairs; never impute absent human observations. A task's sessions pair only if
    there is exactly one per condition, counted before any quality filter, so a failed attempt and its retry are a
    repeat, excluded, not a pair; then both must be finished, attested and successful. The API cost is every assisted
    session's, paired or not (the batch audit's B20-05: a retry had passed as one session and failed spend vanished)."""
    unique = list({s.id: s for s in sessions}.values())
    summary = TimingSummary(sessions=len(unique),
                            api_cost_usd=sum(s.api_cost_usd for s in unique if s.condition == "assisted"))
    groups: dict[tuple, dict[str, list[ResearcherSession]]] = {}
    for s in unique:
        groups.setdefault((s.participant, s.task, s.input_hash), {}).setdefault(s.condition, []).append(s)
    for group in groups.values():
        every = [s for values in group.values() for s in values]
        counts = (len(group.get("manual", [])), len(group.get("assisted", [])))
        if counts != (1, 1):
            why = "unpaired" if 0 in counts else (f"repeated ({counts[0]} manual, {counts[1]} assisted sessions): "
                                                   "the protocol allows one per condition")
            _exclude(summary, every, {s.id: why for s in every})
            continue
        failed = {s.id for s in every if s.phase != "finished" or not s.researcher_attested or not s.task_success}
        if failed:
            _exclude(summary, every, {s.id: "unfinished, unattested or unsuccessful" if s.id in failed
                                      else "its pair's other session does not qualify" for s in every})
            continue
        manual, assisted = group["manual"][0], group["assisted"][0]
        saved = manual.active_seconds - assisted.active_seconds
        summary.paired_seconds_saved.append(saved)
        summary.pairs.append({"participant": manual.participant, "task": manual.task, "seconds_saved": saved})
    summary.paired_completed_tasks = len(summary.paired_seconds_saved)
    if summary.paired_completed_tasks:
        summary.mean_seconds_saved = (
            sum(summary.paired_seconds_saved) / summary.paired_completed_tasks
        )
    return summary


def _exclude(summary: TimingSummary, sessions: list[ResearcherSession], why: dict[str, str]) -> None:
    for s in sessions:
        summary.excluded.append(s.id)
        summary.reasons[s.id] = why[s.id]


def save(session: ResearcherSession, path: Path, new: bool = False) -> None:
    """Persist a researcher session; this is a separate human-evidence artifact. ``new``: a session started, written
    only where no file is when it is written (``durable.write_new``; ``FileExistsError`` where one is: the auditor's DK
    recheck, DL-05's class)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if new:
        from adroit.core.durable import write_new
        write_new(path, session.model_dump_json(indent=2))
        return
    path.write_text(session.model_dump_json(indent=2))

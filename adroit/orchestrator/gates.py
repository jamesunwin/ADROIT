"""Human gates (U0 core): typed requests/responses, auto-approval, file channel.

This module is deliberately self-contained -- no pipeline imports. The
inherited pipeline that wired these gates in was retired at DM6 (tag
``pre-retirement``); the agents of DM8 and DM9 and the workbench of DM11
speak the file protocol defined here.

File protocol (under ``runs/<id>/gates/``):
    ``<seq>_<gate_id>.request.json``   written by the ENGINE side (the run),
    ``<seq>_<gate_id>.response.json``  written by the CLIENT side (the UI).
A request without a response is pending. Both files persist after a
successful exchange (they are part of the record, and their presence marks
the gate answered); an unanswered request survives a crash, so a resumed run
re-asks by reusing the same file. Responses are written atomically
(tmp + rename), so the engine never sees a torn response; a response that
fails validation is DELETED and the engine keeps waiting — a corrected
second response is honored.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Protocol

from pydantic import BaseModel, ValidationError

from adroit.core.state import EvidenceState, StrictModel

# Canonical gate ids (the wizard's WORKBENCH_GATES uses these names).
EVIDENCE_REVIEW = "evidence_review"
SHORTLIST_REVIEW = "shortlist_review"
BUDGET_CONFIRM = "budget_confirm"
FINAL_REVIEW = "final_review"


class GateRequest(StrictModel):
    """What the run asks the scientist, at one specific pipeline moment."""

    gate_id: str
    run_id: str
    seq: int
    stage: str
    payload: dict = {}
    created_at: float = 0.0


class EvidenceReviewResponse(StrictModel):
    """Approve or replace the extracted evidence (None = unchanged)."""

    approved: bool
    evidence: list[EvidenceState] | None = None


class ShortlistReviewResponse(StrictModel):
    """Approve or replace the family shortlist (None = unchanged)."""

    approved: bool
    family_ids: list[str] | None = None


class BudgetConfirmResponse(StrictModel):
    """Confirm further spend; optionally change the refinement rounds."""

    approved: bool
    refinement_rounds: int | None = None


class FinalReviewResponse(StrictModel):
    """Accept the ranking, or send the run back for one more refinement pass."""

    accepted: bool
    extra_refinement: bool = False


RESPONSE_MODELS: dict[str, type[StrictModel]] = {
    EVIDENCE_REVIEW: EvidenceReviewResponse,
    SHORTLIST_REVIEW: ShortlistReviewResponse,
    BUDGET_CONFIRM: BudgetConfirmResponse,
    FINAL_REVIEW: FinalReviewResponse,
}


class GateInterrupted(Exception):
    """A pause/cancel request arrived while the run waited at a gate."""

    def __init__(self, action: str) -> None:
        super().__init__(f"{action} requested while waiting at a gate")
        self.action = action


class GateHook(Protocol):
    """Anything the pipeline can ask a gate question through.

    ``actor`` names who answers in the provenance record (``"scientist"`` for
    a human channel, ``"auto_approve"`` for the headless default).
    """

    actor: str

    def ask(self, request: GateRequest, response_model: type[BaseModel], *,
            validate: Callable[[BaseModel], None] | None = None,
            timeout_s: float | None = None) -> BaseModel:
        """Block until a valid response exists and return it."""
        ...  # pragma: no cover - protocol


class AutoApproveGates:
    """Instant approving defaults — with one deliberate exception.

    ``budget_confirm`` auto-approves only when it was NOT in the requested
    gate list: a scientist who explicitly asked for a budget gate expects a
    human decision before further spend, so a headless run must never wave
    it through. It returns ``approved=False`` instead, which the pipeline
    treats as "cancel before construction" (ui_plan.md section 2): the run
    ends ``cancelled``, checkpointed and resumable, having spent nothing more.
    """

    actor = "auto_approve"

    def __init__(self, requested_gates: list[str] | None = None) -> None:
        self.requested_gates = list(requested_gates or [])

    def ask(self, request: GateRequest, response_model: type[BaseModel], *,
            validate: Callable[[BaseModel], None] | None = None,
            timeout_s: float | None = None) -> BaseModel:
        """Approve at once, except a requested ``budget_confirm``, which is declined."""
        if response_model is BudgetConfirmResponse:
            approved = request.gate_id not in self.requested_gates
            return BudgetConfirmResponse(approved=approved)
        if response_model is FinalReviewResponse:
            return FinalReviewResponse(accepted=True)
        return response_model(approved=True)


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class FileGateChannel:
    """Engine side of the file protocol: write a request, wait for a response.

    ``sleep_fn`` is injectable so tests script the scientist's side without
    real waiting; ``timeout_s`` (per ask) bounds the wait when the caller
    needs one (the pipeline's degradation budget will pass its own).
    """

    actor = "scientist"

    def __init__(self, run_dir: str | Path, *, poll_interval_s: float = 0.5,
                 sleep_fn: Callable[[float], None] = time.sleep,
                 interrupt: Callable[[], str | None] | None = None) -> None:
        """``interrupt`` is polled while waiting: a non-None return (``"pause"``
        / ``"cancel"``) aborts the wait with :class:`GateInterrupted`."""
        self.gates_dir = Path(run_dir) / "gates"
        self.poll_interval_s = poll_interval_s
        self.sleep_fn = sleep_fn
        self.interrupt = interrupt

    def ask(self, request: GateRequest, response_model: type[BaseModel], *,
            validate: Callable[[BaseModel], None] | None = None,
            timeout_s: float | None = None) -> BaseModel:
        """Publish the request and block until a VALID response file appears.

        A response that fails schema validation or the caller's ``validate``
        (e.g. unknown family ids in a shortlist) is deleted so the scientist
        can answer again; the request file stays put throughout.
        """
        self.gates_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{request.seq}_{request.gate_id}"
        request_file = self.gates_dir / f"{stem}.request.json"
        if not request_file.is_file():  # a resumed run re-asks with the same file
            _atomic_write(request_file, request.to_json())
        response_file = self.gates_dir / f"{stem}.response.json"

        waited = 0.0
        while True:
            if response_file.is_file():
                try:
                    response = response_model.model_validate_json(
                        response_file.read_text(encoding="utf-8"))
                    if validate is not None:
                        validate(response)
                    return response
                except (ValidationError, ValueError, json.JSONDecodeError):
                    response_file.unlink(missing_ok=True)  # discard; re-ask
            action = self.interrupt() if self.interrupt is not None else None
            if action is not None:
                raise GateInterrupted(action)
            if timeout_s is not None and waited >= timeout_s:
                raise TimeoutError(f"gate {request.gate_id} (seq {request.seq}) "
                                   f"unanswered after {timeout_s}s")
            self.sleep_fn(self.poll_interval_s)
            waited += self.poll_interval_s


# --------------------------------------------------------------------------
# Client side (the UI, tests, or a human with a text editor)
# --------------------------------------------------------------------------


def pending(run_dir: str | Path) -> list[GateRequest]:
    """Parsed, unanswered gate requests for one run, in seq order."""
    gates_dir = Path(run_dir) / "gates"
    if not gates_dir.is_dir():
        return []
    out = []
    for request_file in sorted(gates_dir.glob("*.request.json")):
        stem = request_file.name.removesuffix(".request.json")
        if (gates_dir / f"{stem}.response.json").is_file():
            continue
        try:
            out.append(GateRequest.model_validate_json(
                request_file.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError):
            continue  # torn or foreign file; the engine's copy is authoritative
    return sorted(out, key=lambda r: r.seq)


def archive_response(run_dir: str | Path, seq: int, gate_id: str, label: str) -> Path | None:
    """Rename an answered gate's response to ``<stem>.<label>.json`` (None if absent).

    Used when a decision must not stand on resume (a declined gate cancels the
    run; a resumed run asks afresh) while keeping the answer on record.
    """
    path = Path(run_dir) / "gates" / f"{seq}_{gate_id}.response.json"
    if not path.is_file():
        return None
    target = path.with_name(f"{seq}_{gate_id}.{label}.{int(time.time() * 1000)}.json")
    os.replace(path, target)
    return target


def respond(run_dir: str | Path, seq: int, gate_id: str, response: BaseModel) -> Path:
    """Write the scientist's answer atomically; returns the response path."""
    gates_dir = Path(run_dir) / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    path = gates_dir / f"{seq}_{gate_id}.response.json"
    _atomic_write(path, response.model_dump_json(indent=2))
    return path

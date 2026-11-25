"""Append-only provenance log backed by SQLite (via SQLModel).

Every state transition in a run is written here as an immutable :class:`Event`,
so any investigation can be audited and *replayed*. Events form a tree through
``parent_event_id`` (e.g. a nested tool call points at its caller), and are
totally ordered for replay by an autoincrement ``seq``.

The store is deliberately schema-complete for LLM calls *now*, before any
LLM code exists: an ``llm_called`` event records the model name, a hash and the
full text of the prompt, the response text, token counts and latency, so the
scientific cost of a run is fully auditable later.

Reconstruction (:meth:`ProvenanceStore.reconstruct_run`) replays the
``state_created`` events: each carries a typed state object as JSON, which is
deserialized back into its :mod:`adroit.core.state` schema and folded into a
:class:`RunState`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine, select

from adroit.core.state import (
    AdjudicationRecord,
    EvidenceState,
    FitResult,
    StrictModel,
    ModelCandidate,
    ProblemSpec,
    RevisionAction,
    RunState,
    _utc_now,
)
from adroit.core.evidence import EvidenceEnvelope


def _new_id() -> str:
    """Return a fresh random UUID string (default factory for ``event_id``)."""
    return str(uuid4())


class EventType(str, Enum):
    """The kind of provenance event recorded in the log."""

    state_created = "state_created"
    tool_called = "tool_called"
    llm_called = "llm_called"
    decision = "decision"
    error = "error"


class Event(SQLModel, table=True):
    """One immutable row in the append-only provenance ledger.

    ``seq`` is the autoincrement replay order; ``event_id`` is a stable UUID that
    ``parent_event_id`` references to form the event tree. The ``llm_*`` columns
    are populated only for :attr:`EventType.llm_called` events.
    """

    seq: int | None = Field(default=None, primary_key=True)
    event_id: str = Field(default_factory=_new_id, index=True, unique=True)
    run_id: str = Field(index=True)
    timestamp: datetime = Field(default_factory=_utc_now)
    actor: str
    event_type: EventType
    payload_json: str | None = None
    parent_event_id: str | None = Field(default=None, index=True)

    # LLM-call fields (nullable; set only for llm_called events).
    llm_model: str | None = None
    llm_prompt_hash: str | None = None
    llm_prompt_text: str | None = None
    llm_response_text: str | None = None
    llm_prompt_tokens: int | None = None
    llm_completion_tokens: int | None = None
    llm_total_tokens: int | None = None
    llm_latency_s: float | None = None


class LLMCallRecord(BaseModel):
    """Structured detail of a single LLM call, attached to an ``llm_called`` event.

    ``prompt_hash`` is derived from ``prompt_text`` if not supplied, so identical
    prompts are cheaply de-duplicable in the audit log.
    """

    model: str
    prompt_text: str
    response_text: str = ""
    prompt_hash: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_s: float | None = None

    def resolved_hash(self) -> str:
        """Return ``prompt_hash`` or a SHA-256 of ``prompt_text`` if it is unset."""
        if self.prompt_hash:
            return self.prompt_hash
        return hashlib.sha256(self.prompt_text.encode("utf-8")).hexdigest()


# Typed state classes that can appear in a ``state_created`` payload envelope.
_STATE_REGISTRY: dict[str, type[StrictModel]] = {
    cls.__name__: cls
    for cls in (
        ProblemSpec,
        EvidenceState,
        ModelCandidate,
        FitResult,
        AdjudicationRecord,
        RevisionAction,
        RunState,
        EvidenceEnvelope,
    )
}


def _encode_state(obj: StrictModel) -> str:
    """Wrap a typed state object as a JSON envelope tagged with its class name."""
    return json.dumps({"state_type": type(obj).__name__, "data": obj.model_dump(mode="json")})


def _decode_state(payload_json: str) -> StrictModel:
    """Rebuild the typed state object from a ``state_created`` payload envelope."""
    envelope = json.loads(payload_json)
    cls = _STATE_REGISTRY[envelope["state_type"]]
    return cls.model_validate(envelope["data"])


class ProvenanceStore:
    """A SQLite-backed, append-only log of the events that make up runs."""

    def __init__(self, engine: object) -> None:
        """Wrap an existing SQLAlchemy engine (prefer :meth:`open`)."""
        self._engine = engine

    @classmethod
    def open(cls, path: str | Path) -> "ProvenanceStore":
        """Open (creating if needed) a provenance DB at ``path`` and ensure the schema.

        Pass ``":memory:"`` for an ephemeral in-process store (used by tests).
        """
        if str(path) == ":memory:":
            engine = create_engine(
                "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
            )
        else:
            engine = create_engine(f"sqlite:///{Path(path)}")
        SQLModel.metadata.create_all(engine)
        return cls(engine)

    def log_event(
        self,
        *,
        run_id: str,
        actor: str,
        event_type: EventType,
        payload: StrictModel | dict | None = None,
        parent_event_id: str | None = None,
        llm: LLMCallRecord | None = None,
    ) -> Event:
        """Append one event and return the persisted row (with ``seq`` assigned).

        ``payload`` may be a typed state object (stored as a tagged envelope so it
        can be replayed), a plain dict (stored verbatim), or ``None``.
        """
        event = Event(
            run_id=run_id,
            actor=actor,
            event_type=event_type,
            payload_json=self._encode_payload(payload),
            parent_event_id=parent_event_id,
        )
        if llm is not None:
            self._attach_llm(event, llm)
        with Session(self._engine) as session:
            session.add(event)
            session.commit()
            session.refresh(event)
        return event

    @staticmethod
    def _encode_payload(payload: StrictModel | dict | None) -> str | None:
        """Serialize a payload to JSON: envelope for typed states, verbatim for dicts."""
        if payload is None:
            return None
        if isinstance(payload, StrictModel):
            return _encode_state(payload)
        return json.dumps(payload)

    @staticmethod
    def _attach_llm(event: Event, llm: LLMCallRecord) -> None:
        """Copy an :class:`LLMCallRecord` onto the ``llm_*`` columns of an event."""
        event.llm_model = llm.model
        event.llm_prompt_hash = llm.resolved_hash()
        event.llm_prompt_text = llm.prompt_text
        event.llm_response_text = llm.response_text
        event.llm_prompt_tokens = llm.prompt_tokens
        event.llm_completion_tokens = llm.completion_tokens
        event.llm_total_tokens = llm.total_tokens
        event.llm_latency_s = llm.latency_s

    def get_run_events(self, run_id: str) -> list[Event]:
        """Return all events for ``run_id`` in replay (insertion) order."""
        with Session(self._engine) as session:
            statement = select(Event).where(Event.run_id == run_id).order_by(Event.seq)
            return list(session.exec(statement))

    def reconstruct_run(self, run_id: str) -> RunState:
        """Replay ``state_created`` events for ``run_id`` into a :class:`RunState`.

        Raises:
            ValueError: if the run has no state-creating event to seed from.
        """
        run: RunState | None = None
        for event in self.get_run_events(run_id):
            if event.event_type is not EventType.state_created or event.payload_json is None:
                continue
            run = self._fold_state(run, _decode_state(event.payload_json))
        if run is None:
            raise ValueError(f"No state_created events found for run_id={run_id!r}")
        run.id = run_id
        return run

    @staticmethod
    def _fold_state(run: RunState | None, obj: StrictModel) -> RunState:
        """Fold one replayed state object into the run being reconstructed."""
        if isinstance(obj, RunState):
            return obj
        if isinstance(obj, ProblemSpec):
            if run is None:
                return RunState(problem=obj)
            run.problem = obj
            return run
        if run is None:
            raise ValueError("First state_created event must be a ProblemSpec or RunState")
        _appenders = {
            EvidenceState: run.evidence,
            ModelCandidate: run.candidates,
            FitResult: run.fits,
            AdjudicationRecord: run.adjudications,
            RevisionAction: run.revisions,
        }
        _appenders[type(obj)].append(obj)
        return run

    def export_run(self, run_id: str, path: str | Path) -> dict:
        """Dump a human-readable JSON audit file for ``run_id`` and return the dict."""
        audit = {
            "run_id": run_id,
            "n_events": 0,
            "events": [self._event_to_audit(e) for e in self.get_run_events(run_id)],
        }
        audit["n_events"] = len(audit["events"])
        Path(path).write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
        return audit

    @staticmethod
    def _event_to_audit(event: Event) -> dict:
        """Render one event as a readable audit entry (parsed payload, LLM block if any)."""
        entry: dict = {
            "seq": event.seq,
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "actor": event.actor,
            "event_type": event.event_type.value,
            "parent_event_id": event.parent_event_id,
            "payload": json.loads(event.payload_json) if event.payload_json else None,
        }
        if event.event_type is EventType.llm_called:
            entry["llm"] = {
                "model": event.llm_model,
                "prompt_hash": event.llm_prompt_hash,
                "prompt_text": event.llm_prompt_text,
                "response_text": event.llm_response_text,
                "prompt_tokens": event.llm_prompt_tokens,
                "completion_tokens": event.llm_completion_tokens,
                "total_tokens": event.llm_total_tokens,
                "latency_s": event.llm_latency_s,
            }
        return entry

"""Versioned scientific evidence, independent of presentation and physics verdicts."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from adroit.core.state import StrictModel


def content_hash(value: JsonValue) -> str:
    """Hash exact structured content, preserving zero and nonfinite legacy values."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class SourceEvidence(StrictModel):
    """A source snapshot; a human signature remains separate from computation."""

    id: str
    reference: str = ""
    version: str = ""
    payload_sha256: str = ""
    data_sha256: str = ""
    data_path: str = ""
    review: Literal["verified", "unreviewed", "not_required", "legacy_unknown"] = "legacy_unknown"
    reviewed_by: str = ""
    reviewed_on: date | None = None
    # a source a language model checked instead of a person, at the researcher's choice (the owner, 2026-11-18): the
    # model; its review is "verified", and every view that names the review says it was the model's, not a person's.
    # Absent from every other source, which hashes as before
    reviewed_by_model: str = Field(default="", exclude_if=lambda v: not v)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    verification_binding: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _signature(self) -> SourceEvidence:
        if self.review == "verified" and not (self.reviewed_by and self.reviewed_on):
            raise ValueError("verified evidence requires the recorded reviewer (a person, or the checking model) "
                             "and date")
        return self


class BackendEvidence(StrictModel):
    """Recorded availability and identity, not a claim that a backend was used."""

    name: str
    version: str = ""
    sha256: str = ""
    location: str = ""
    status: Literal["present", "unavailable", "unknown"] = "unknown"
    role: str = ""
    licence: str = ""
    reference: str = ""


class InputArtifact(StrictModel):
    """Explicit dependency; external releases are referenced, not copied by default."""

    name: str
    location: str
    sha256: str = ""
    role: Literal["package_input", "user_input", "catalog_input", "external", "software"] = "external"
    redistribution: Literal["project", "user_selected", "reference_only"] = "reference_only"


class EvidenceContext(StrictModel):
    """Run-time identities captured before calculation or explicitly unknown."""

    origin: Literal["captured", "legacy_unknown", "changed_during_run"] = "legacy_unknown"
    identity: str = ""
    request_sha256: str = ""
    python: str = ""
    versions: dict[str, str] = Field(default_factory=dict)
    code_sha256: str = ""
    git_sha: str = ""
    git_dirty: bool | None = None
    sources: list[SourceEvidence] = Field(default_factory=list)
    backends: list[BackendEvidence] = Field(default_factory=list)
    inputs: list[InputArtifact] = Field(default_factory=list)
    command: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    calculation_started_at: str = ''
    calculation_completed_at: str = ''

    @model_validator(mode='after')
    def chronology(self) -> EvidenceContext:
        """Refuse calculation times that are not explicit UTC, a completion without a start, or a completion before
        the start."""
        dates=[]
        for value in (self.calculation_started_at,self.calculation_completed_at):
            if value:
                parsed=datetime.fromisoformat(value)
                if parsed.tzinfo is None or parsed.utcoffset().total_seconds()!=0:
                    raise ValueError('calculation timestamps must be explicit UTC')
                dates.append(parsed)
        if self.calculation_completed_at and not self.calculation_started_at:
            raise ValueError('completion requires a recorded start')
        if len(dates)==2 and dates[1]<dates[0]:
            raise ValueError('completion precedes start')
        return self


class EvidenceObservation(StrictModel):
    """One source-bound calculation, with independent applicability/review states."""

    subject_id: str
    physical_input: dict[str, JsonValue]
    observable: str
    value: float | None = Field(default=None, allow_inf_nan=False)
    units: str = "unspecified in saved result"
    calculation: Literal["computed", "unavailable_backend", "missing_input", "unresolved",
                         "not_calculated", "legacy_unknown"] = "legacy_unknown"
    applicability: Literal["applicable", "not_applicable", "outside_domain", "unsupported",
                           "unknown"] = "unknown"
    review: Literal["verified", "unreviewed", "not_required", "legacy_unknown"] = "legacy_unknown"
    excluded: bool | None = None
    native_confidence_level: float | None = Field(default=None, gt=0, lt=1)
    required_confidence_level: float | None = Field(default=None, gt=0, lt=1)
    construction: str = "unspecified in saved result"
    source_ids: list[str] = Field(default_factory=list)
    domain: dict[str, JsonValue] = Field(default_factory=dict)
    uncertainties: dict[str, JsonValue] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @property
    def identity(self) -> str:
        """A view-independent digest of the complete scientific observation."""
        return content_hash(self.model_dump(mode="json"))


class EvidenceEnvelope(StrictModel):
    """Additive sidecar; raw typed results remain the numerical authority."""

    schema_version: Literal[1] = 1
    workflow: str
    result_sha256: str
    input_sha256: str
    original_inputs: dict[str, JsonValue] = Field(default_factory=dict)
    engine_mapping: dict[str, JsonValue] = Field(default_factory=dict)
    summary: dict[str, JsonValue] = Field(default_factory=dict)
    context: EvidenceContext = Field(default_factory=EvidenceContext)
    observations: list[EvidenceObservation] = Field(default_factory=list)
    certificates: dict[str, JsonValue] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @property
    def identity(self) -> str:
        """Hash inputs, mappings, sources/settings and results, excluding no physics."""
        return content_hash(self.model_dump(mode="json"))


def physical_identity(engine: dict[str, JsonValue], point: dict[str, JsonValue]) -> str:
    """Identify the same engine/physical point across tracks and display names."""
    model = dict(engine)
    model.pop("name", None)
    return content_hash({"engine": model, "point": point})

"""Typed, input-bound tasks for pending scientific conclusions, not new verdicts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from adroit.core.evidence import EvidenceObservation, SourceEvidence, content_hash
from adroit.core.state import StrictModel

TaskKind = Literal["source_verification", "recast_likelihood", "missing_input", "backend", "coverage",
                   "unsupported_model", "unresolved_calculation", "source_change"]


class AffectedResult(StrictModel):
    """One selected study/point and the exact saved scientific reason."""

    result_sha256: str
    workflow: str
    subject_id: str
    role: str
    status: str
    blocks_conclusion: bool
    reasons: list[str] = Field(default_factory=list)
    observation: EvidenceObservation


class ReviewTask(StrictModel):
    """An actionable prerequisite; completing it does not automatically confer eligibility."""

    id: str
    kind: TaskKind
    record_id: str = ""
    title: str
    action: str
    reason: str
    affected: list[AffectedResult] = Field(default_factory=list)
    blocked_points: int = 0
    affected_studies: int = 0
    prerequisites: list[str] = Field(default_factory=list)
    eligibility_note: str = "Re-evaluate the physical point after review/calculation; source review alone is not a recast or a CL conversion."

    @property
    def timing_identity(self) -> str:
        """Bind the timing comparison to exactly the same scientific review task."""
        return content_hash(self.model_dump(mode="json"))


class ReviewQueue(StrictModel):
    """Deterministic priorities over selected requested conclusions."""

    schema_version: Literal[1] = 1
    selected_results: list[str] = Field(default_factory=list)
    tasks: list[ReviewTask] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ranking: str = (
        "blocking requested conclusions first; descending distinct blocked physical points and selected studies; "
        "then source verification/missing input before new recasts; stable task ID tie-break. "
        "An unresolved check of an already excluded point does not overturn its exclusion."
    )


class ReviewDifference(StrictModel):
    """A displayed scientific change; missing old bytes remain missing."""

    field: str
    before: JsonValue
    after: JsonValue


class RecordReviewPacket(StrictModel):
    """Current source/curves, historical snapshot, comparisons and required human action."""

    record_id: str
    task: ReviewTask | None = None
    current: SourceEvidence
    previous: SourceEvidence | None = None
    differences: list[ReviewDifference] = Field(default_factory=list)
    current_curves: list[dict[str, JsonValue]] = Field(default_factory=list)
    previous_curves: list[dict[str, JsonValue]] = Field(default_factory=list)
    previous_curve_status: str = "not recorded"
    source_url: str = ""
    source_page: int | None = None
    source_label: str = ""
    warnings: list[str] = Field(default_factory=list)

    @property
    def timing_identity(self) -> str:
        """A stable review-protocol input identity, independent of elapsed human time."""
        return content_hash(self.model_dump(mode="json"))

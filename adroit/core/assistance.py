"""Typed advisory exchanges; no response can supply a physics calculation input."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from adroit.core.state import StrictModel

Action = Literal[
    "clarify_input",
    "source_review",
    "native_joint",
    "nuisance_check",
    "review_results",
    "single_idea",
]
Issue = Literal[
    "missing_input",
    "unsupported_model",
    "ineligible_null",
    "incomplete_calibration",
    "nr_mislabel",
    "fidelity_overclaim",
    "coverage_overclaim",
    "thermal_unresolved",
    "record_unverified",
    "other",
    "input_result_mismatch",
]

PROBE_FACTS = {
    "missing_input": {"has_study", "missing_fields"},
    "unsupported_model": {"supported_model"},
    "ineligible_null": {"ineligible_masses", "null_range"},
    "incomplete_calibration": {"draft_claims", "native_complete"},
    "nr_mislabel": {"draft_claims", "native_complete", "native_z"},
    "fidelity_overclaim": {"draft_claims", "native_fidelity"},
    "coverage_overclaim": {"draft_claims", "uniform_nuisance_coverage"},
    "thermal_unresolved": {"draft_claims", "thermal_certified"},
    "record_unverified": {"draft_claims", "unverified_record_count"},
    "input_result_mismatch": {"result_matches_input"},
}


class EvidencePacket(StrictModel):
    """A fetched source with separate trust states (the external audit's A08, 2026-10-16): the source exists
    (``exists``: its identifier resolves); the cited paper is this one (``reference_checked``: identified by its own
    title, ``identity`` "title"; a description that only fits it is ``identity`` "description" and not checked); the
    stated passage is on the page (``content_checked``: a non-empty anchor found there; with no anchor the page was
    fetched and nothing on it checked); and the claim is supported (``claim_verified``, by a probe or an expert)."""

    id: str
    reference: str
    title: str = ""
    page: int = Field(default=1, ge=1)
    url: str = ""
    document_sha256: str = ""
    excerpt: str = ""
    exists: bool = False
    identity: str = ""
    reference_checked: bool = False
    content_checked: bool = False
    claim_verified: bool = False
    note: str = ""


class CheckedFact(StrictModel):
    """A fact computed from the immutable request/result, never from an LLM."""

    id: str
    value: str
    origin: str


class AssistanceContext(StrictModel):
    """Scientific data are serialized read-only; plans can only refer to their identity."""

    input_hash: str
    goal: str
    original_inputs_json: str
    facts: list[CheckedFact] = Field(default_factory=list)
    evidence: list[EvidencePacket] = Field(default_factory=list)


class Clarification(StrictModel):
    """A question for the researcher, not an automatic parameter edit."""

    field: str
    question: str
    choices: list[str] = Field(default_factory=list, max_length=3)


class SourceRequest(StrictModel):
    """Bounded arXiv retrieval request; arbitrary URLs or files are not accepted."""

    arxiv_id: str = Field(pattern=r"^\d{4}\.\d{4,5}(?:v\d+)?$")
    title: str = ""
    page: int = Field(default=1, ge=1, le=128)
    anchor: str = Field(default="", max_length=100)

    @field_validator("anchor")
    @classmethod
    def _meaningful_anchor(cls, value: str) -> str:
        """Whitespace collapsed as on the fetched page, so an anchor of spaces is no anchor (nothing on the page is
        checked); one without a letter or digit is refused (the external audit of 2026-10-17, I17-2: a single
        space matched every page and marked its content checked)."""
        anchor = " ".join(value.split())
        if anchor and not any(ch.isalnum() for ch in anchor):
            raise ValueError("a source anchor needs letters or digits to check")
        return anchor


class PlanStep(StrictModel):
    """Only an existing operation on the exact supplied request can be proposed."""

    action: Action
    input_hash: str
    reason: str


class AssistanceProposal(StrictModel):
    """Clarification, source gathering and a bounded calculation plan."""

    input_hash: str
    questions: list[Clarification] = Field(default_factory=list, max_length=8)
    sources: list[SourceRequest] = Field(default_factory=list, max_length=4)
    steps: list[PlanStep] = Field(default_factory=list, max_length=6)


class ReviewClaim(StrictModel):
    """An advisory claim requiring a specific deterministic probe or human review."""

    issue: Issue
    fact_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str


class AssistanceReview(StrictModel):
    """Reviewer output; unknown or unsupported claims remain unconfirmed."""

    input_hash: str
    claims: list[ReviewClaim] = Field(default_factory=list, max_length=12)


class VettedClaim(StrictModel):
    """A passed probe is distinct from a matched citation or an agent suggestion."""

    claim: ReviewClaim
    confirmed: bool = False
    probe: str = ""
    reason: str = ""


class AssistanceResult(StrictModel):
    """Advisory output with deterministic baseline and truthful measurements."""

    input_hash: str
    context: AssistanceContext
    proposal: AssistanceProposal
    review: AssistanceReview
    review_origin: Literal["deterministic", "llm"] = "deterministic"
    vetted: list[VettedClaim] = Field(default_factory=list)
    baseline_issues: list[str] = Field(default_factory=list)
    mode: str = "deterministic"
    model: str = ""
    status: str = "complete"
    errors: list[str] = Field(default_factory=list)
    dropped_steps: list[str] = Field(default_factory=list)
    source_attempts: int = 0
    physics_input_preserved: bool = True
    executed: list[str] = Field(default_factory=list)
    calculation_artifacts: dict[str, str] = Field(default_factory=dict)
    automated_seconds: float = 0.0
    api_cost_usd: float = 0.0
    committed_cost_usd: float = 0.0
    researcher_seconds_saved: float | None = None
    calculation_started_at: str = ""          # UTC, recorded by chronology.timed
    calculation_completed_at: str = ""
    # the saved study's result its request was read from, as found (``AssistanceRequest.source_sha256``)
    source_sha256: str = Field(default="", exclude_if=lambda v: not v)

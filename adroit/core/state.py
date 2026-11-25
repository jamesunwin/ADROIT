"""Typed state schemas for a mechanistic-hypothesis investigation (inherited).

These are the schemas of the general engine retired at DM6 (tag
``pre-retirement``, where the modules named in the comments below live). They
are kept because the provenance store, the human gates and the LLM client
record them, and every ADROIT schema builds on :class:`StrictModel`. The
dark matter objects are in :mod:`adroit.core.dm_state`.

These Pydantic v2 models are the *typed internal state* of the system: instead
of agents exchanging free-form strings, every artifact of a run — the problem
statement, extracted evidence, candidate models, fits, adjudications and
revisions — is a rigidly validated object. In Mathematica terms each class is a
head such as ``ProblemSpec[objective, dataSources, ...]`` whose slots are
checked on construction.

Design conventions shared by every model (via :class:`StrictModel`):

* String UUID ``id`` fields with a default factory, so a fresh object is always
  uniquely addressable in the provenance store.
* ``extra="forbid"`` and ``validate_assignment=True`` so both a stray field and
  a later bad mutation raise :class:`pydantic.ValidationError` immediately.
* ``.to_json()`` / ``.from_json()`` helpers giving loss-free JSON round-trips,
  so any state can be serialized to the SQLite provenance log and rebuilt.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _new_id() -> str:
    """Return a fresh random UUID as a string (default factory for ``id`` fields)."""
    return str(uuid4())


def _utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    """Base class for all typed-state models.

    Supplies the strict validation config and symmetric JSON helpers used
    throughout the system. Subclasses only declare their fields.
    """

    # ser_json_inf_nan="constants": failed fits legitimately carry
    # loss/aic/bic = inf; the default JSON encoding turns inf into null, which
    # breaks the checkpoint round-trip (resume) and any dump->validate path
    # (both bitten live during the stage-A matrix, 2026-09-21/23).
    model_config = ConfigDict(extra="forbid", validate_assignment=True,
                              ser_json_inf_nan="constants")

    def to_json(self) -> str:
        """Serialize this model to a JSON string (ISO-8601 datetimes, enums as values)."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> "StrictModel":
        """Reconstruct a model instance from a JSON string produced by :meth:`to_json`."""
        return cls.model_validate_json(data)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DataSourceKind(str, Enum):
    """Modality of an admissible data source."""

    timeseries = "timeseries"
    table = "table"
    image = "image"
    text = "text"


class QualitativeFeatureKind(str, Enum):
    """A qualitative dynamical signature that evidence may exhibit."""

    oscillation = "oscillation"
    decay = "decay"
    growth = "growth"
    saturation = "saturation"
    bistability = "bistability"
    phase_transition = "phase_transition"
    power_law = "power_law"
    network_structure = "network_structure"
    collective_motion = "collective_motion"
    noise_dominated = "noise_dominated"
    other = "other"


class RevisionActionKind(str, Enum):
    """A revision kind in the provenance record.

    Version 1 proposes and applies only ``switch_family`` and ``adjust_priors``
    (``agents.refinement.V1_ACTIONS``); the other kinds are kept so that runs
    recorded before 2026-09-25 still load.
    """

    add_term = "add_term"
    remove_term = "remove_term"
    change_noise_model = "change_noise_model"
    switch_family = "switch_family"
    hybridize = "hybridize"
    adjust_priors = "adjust_priors"


class RunStatus(str, Enum):
    """Lifecycle stage of a full investigation."""

    created = "created"
    evidence_extracted = "evidence_extracted"
    shortlisted = "shortlisted"
    candidates_constructed = "candidates_constructed"
    fitted = "fitted"
    adjudicated = "adjudicated"
    refined = "refined"
    completed = "completed"
    failed = "failed"
    paused = "paused"        # stopped by the user on API degradation; resumable
    cancelled = "cancelled"  # abandoned by the user on API degradation


# ---------------------------------------------------------------------------
# Problem definition
# ---------------------------------------------------------------------------


class DataSourceRef(StrictModel):
    """A pointer to one admissible data source for a problem.

    ``roles`` are the scientist's declared variable roles (column -> one of
    ``core.roles.ROLE_CHOICES``); they override the roles the ingestion model
    proposes. ``options`` carries settings specific to a kind of source.
    """

    id: str = Field(default_factory=_new_id)
    kind: DataSourceKind
    path_or_url: str
    description: str = ""
    roles: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)


class ProblemSpec(StrictModel):
    """The scientific question and the evidence admissible to answer it."""

    id: str = Field(default_factory=_new_id)
    scientific_objective: str
    admissible_data: list[DataSourceRef] = Field(default_factory=list)
    context_literature: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# Extracted evidence
# ---------------------------------------------------------------------------


class VariableInfo(StrictModel):
    """A variable identified in the data, with units and a guessed role.

    A driver of a multi-driver response law also carries the ``symbol`` it has
    in the law (``x1``, ``x2``, ...), its ``measurement`` kind ("ratio" or
    "interval"; "" until known), and the ``offset`` and ``scale`` of the
    dimensionless driver the law sees, ``(value - offset) / scale``
    (library/drivers.py).
    ``uncertain`` marks a role the ingestion model could not settle from the
    data and the context (core/roles.py).
    """

    name: str
    units: str = ""
    role_guess: str = ""
    symbol: str = ""
    measurement: str = ""
    offset: float = 0.0
    scale: float | None = None
    uncertain: bool = False


class QualitativeFeature(StrictModel):
    """A qualitative signature observed in the evidence, with a confidence."""

    feature: QualitativeFeatureKind
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_snippet: str = ""


class EvidenceState(StrictModel):
    """Structured evidence extracted from a problem's data sources."""

    id: str = Field(default_factory=_new_id)
    problem_id: str
    summary: str = ""
    variables: list[VariableInfo] = Field(default_factory=list)
    qualitative_features: list[QualitativeFeature] = Field(default_factory=list)
    numeric_payload_ref: str | None = None


def merge_evidence(states: list[EvidenceState], problem_id: str | None = None) -> EvidenceState:
    """Fuse several evidence states (table, figure, text, ...) into one view.

    Multimodal problems produce one :class:`EvidenceState` per source; consumers
    that judge against a single evidence object (the tournament criteria, the
    refinement diagnostics) should see the *union* of what was observed, not an
    arbitrary first source. Merging is deterministic and lossless where it
    matters: summaries are concatenated in order, variables are deduplicated by
    name (first occurrence wins), each qualitative feature keeps the
    highest-confidence observation across sources (with its snippet), and the
    numeric payload reference comes from the first source that has one.

    Raises:
        ValueError: if ``states`` is empty and no ``problem_id`` is given.
    """
    if not states and problem_id is None:
        raise ValueError("merge_evidence needs at least one state or a problem_id")
    if len(states) == 1:
        return states[0]

    variables: dict[str, VariableInfo] = {}
    best: dict[QualitativeFeatureKind, QualitativeFeature] = {}
    payload_ref: str | None = None
    for state in states:
        for v in state.variables:
            variables.setdefault(v.name, v)
        for f in state.qualitative_features:
            held = best.get(f.feature)
            if held is None or f.confidence > held.confidence:
                best[f.feature] = f
        if payload_ref is None and state.numeric_payload_ref:
            payload_ref = state.numeric_payload_ref
    return EvidenceState(
        problem_id=problem_id or states[0].problem_id,
        summary=" | ".join(s.summary for s in states if s.summary),
        variables=list(variables.values()),
        qualitative_features=list(best.values()),
        numeric_payload_ref=payload_ref)


# ---------------------------------------------------------------------------
# Model candidates
# ---------------------------------------------------------------------------


SCALE_PRIOR_RATIO = 100.0  # a positive prior spanning two decades or more is a scale prior


class ParameterSpec(StrictModel):
    """A free parameter of a candidate model with its prior support.

    ``scale`` is how a position within the prior is read: ``log`` for a scale
    parameter (a rate constant, a half-saturation constant, an amplitude),
    ``linear`` otherwise. Left unset it is inferred: a positive prior spanning
    two decades or more is read on ln, as for a log-uniform prior. It is used
    by the diagnostic flags and the refinement agent ("pinned at a bound"),
    not by the fit.
    """

    name: str
    meaning: str = ""
    prior_low: float
    prior_high: float
    units: str = ""
    scale: Literal["linear", "log"] | None = None

    def on_log_scale(self) -> bool:
        """Whether positions in the prior are read on ln (declared, else inferred)."""
        if self.scale is not None:
            return self.scale == "log" and self.prior_low > 0.0
        return self.prior_low > 0.0 and self.prior_high >= SCALE_PRIOR_RATIO * self.prior_low

    def position(self, value: float) -> float:
        """Where ``value`` sits in the prior, 0 at the low bound and 1 at the high (NaN if undefined)."""
        low, high = self.prior_low, self.prior_high
        if not high > low or not math.isfinite(value):
            return float("nan")
        if self.on_log_scale():
            return math.log(value / low) / math.log(high / low) if value > 0.0 else float("nan")
        return (value - low) / (high - low)


class ModelCandidate(StrictModel):
    """A concrete symbolic model proposed as a mechanistic hypothesis."""

    id: str = Field(default_factory=_new_id)
    family_id: str
    name: str
    symbolic_form: str
    latex_form: str = ""
    parameters: list[ParameterSpec] = Field(default_factory=list)
    observables: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    expected_signatures: list[str] = Field(default_factory=list)
    justification: str = ""
    provenance_evidence_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Fitting and adjudication
# ---------------------------------------------------------------------------


class FitResult(StrictModel):
    """The outcome of fitting one candidate to data, with UQ and diagnostics."""

    id: str = Field(default_factory=_new_id)
    candidate_id: str
    param_estimates: dict[str, float] = Field(default_factory=dict)
    param_uncertainties: dict[str, float] = Field(default_factory=dict)
    loss: float
    aic: float
    bic: float
    residual_diagnostics: dict[str, float] = Field(default_factory=dict)
    heldout_score: float | None = None
    fit_success: bool = True
    notes: str = ""


class AdjudicationEntry(StrictModel):
    """A single scored judgement of one candidate on one criterion."""

    candidate_id: str
    criterion: str
    score: float
    rationale: str = ""


class PairwiseDecision(StrictModel):
    """The outcome of comparing two candidates on the weighted criteria vector.

    Produced only by the optional pairwise ranking rule
    (``TournamentConfig.pairwise=True``); the default aggregate rule records none.
    """

    candidate_a: str
    candidate_b: str
    winner: str = ""   # candidate id of the winner; "" denotes a tie
    margin: float = 0.0  # weight of criteria a wins minus b's, over the total active weight
    rationale: str = ""


class AdjudicationRecord(StrictModel):
    """A tournament's per-criterion scores, pairwise decisions, and final ranking.

    ``pairwise`` is empty under the default aggregate ranking rule.
    """

    id: str = Field(default_factory=_new_id)
    entries: list[AdjudicationEntry] = Field(default_factory=list)
    pairwise: list[PairwiseDecision] = Field(default_factory=list)
    final_ranking: list[str] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=dict)
    # Which definition of each mode-switchable criterion scored this record
    # (e.g. {"evidence_consistency": "card", "fit_quality": "relative"}); empty
    # on records written before the modes existed (A1, 2026-09-24).
    modes: dict[str, str] = Field(default_factory=dict)
    # Candidates of OTHER laws the data do not distinguish from the winner
    # (inference.tournament.indistinguishable_rivals); empty when the winner
    # stands clear, and on records written before 2026-09-26.
    indistinguishable: list[str] = Field(default_factory=list)
    # Candidates of other laws that fit decisively better IN-SAMPLE (AIC lower
    # by more than 2) although the tournament ranked the winner first: the
    # evidence conflicts (inference.tournament.contested_rivals).
    contested: list[str] = Field(default_factory=list)
    # Per candidate, what its parameters say that the ranking does not weigh
    # under the invariant rule: pinned at a bound, poorly determined, unstable
    # across folds (inference.tournament.candidate_flags; 2026-09-28).
    flags: dict[str, list[str]] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Refinement and the top-level run
# ---------------------------------------------------------------------------


class RevisionAction(StrictModel):
    """A refinement step transforming one candidate into a revised one.

    ``target_family_id`` names the neighbor family for a ``switch_family`` move and
    ``parameter`` the prior to widen for ``adjust_priors`` (empty: every prior).
    ``term`` is populated only in revisions recorded before 2026-09-25, when the
    retired ``add_term`` / ``remove_term`` moves existed.
    """

    id: str = Field(default_factory=_new_id)
    action: RevisionActionKind
    target_candidate_id: str
    description: str = ""
    target_family_id: str = ""
    term: str = ""
    parameter: str = ""
    resulting_candidate_id: str | None = None


class GateDecision(StrictModel):
    """A human-gate decision APPLIED to a run (U0).

    Appended only after the decision has taken effect, so a resumed run knows
    exactly which gates are settled and re-asks any that were pending. ``actor``
    is ``"scientist"`` for a human answer and ``"auto_approve"`` for a headless
    default -- an automatic approval is never recorded as a human one.
    """

    gate_id: str
    seq: int
    actor: str = "scientist"
    response: dict = Field(default_factory=dict)
    decided_at: datetime = Field(default_factory=_utc_now)


class RunState(StrictModel):
    """The complete, replayable state of one mechanistic investigation."""

    id: str = Field(default_factory=_new_id)
    problem: ProblemSpec
    evidence: list[EvidenceState] = Field(default_factory=list)
    shortlist: list[str] = Field(default_factory=list)
    candidates: list[ModelCandidate] = Field(default_factory=list)
    fits: list[FitResult] = Field(default_factory=list)
    adjudications: list[AdjudicationRecord] = Field(default_factory=list)
    revisions: list[RevisionAction] = Field(default_factory=list)
    status: RunStatus = RunStatus.created
    gate_log: list[GateDecision] = Field(default_factory=list)

"""New development tasks only: compare errors, false concerns and measured costs."""

from __future__ import annotations

from pydantic import Field

from adroit.core.state import StrictModel
from adroit.core.assistance import AssistanceResult


class AssistanceTask(StrictModel):
    """Ground truth remains outside the planner/reviewer prompts."""

    id: str
    expected_issues: list[str] = Field(default_factory=list)
    clean_control: bool = False


class ValueScore(StrictModel):
    """Count agent proposals separately from confirmed probes and baseline findings."""

    task_id: str
    expected: list[str]
    baseline_caught: list[str]
    agent_caught: list[str]
    added_over_baseline: list[str]
    missed: list[str]
    false_concerns: list[str]
    blocked_unconfirmed: list[str]
    unadjudicated_concerns: list[str] = Field(default_factory=list)
    physics_input_preserved: bool
    api_cost_usd: float
    automated_seconds: float
    researcher_seconds_saved: float | None = None


def score(task: AssistanceTask, result: AssistanceResult) -> ValueScore:
    """Score the LLM's own review against held-aside development truth, not its fallback."""
    expected = set(task.expected_issues)
    # A degraded deterministic fallback is not counted as an LLM success.
    agent = (
        set(c.claim.issue for c in result.vetted if c.confirmed)
        if result.review_origin == "llm"
        else set()
    )
    proposed = {c.issue for c in result.review.claims} if result.review_origin == "llm" else set()
    baseline = set(result.baseline_issues)
    return ValueScore(
        task_id=task.id,
        expected=sorted(expected),
        baseline_caught=sorted(expected & baseline),
        agent_caught=sorted(expected & agent),
        added_over_baseline=sorted((expected & agent) - baseline),
        missed=sorted(expected - agent),
        false_concerns=sorted((proposed - expected) - {"other"}),
        unadjudicated_concerns=sorted(proposed & {"other"}),
        blocked_unconfirmed=sorted(c.claim.issue for c in result.vetted if not c.confirmed),
        physics_input_preserved=result.physics_input_preserved,
        api_cost_usd=result.api_cost_usd,
        automated_seconds=result.automated_seconds,
    )

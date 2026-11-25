"""The assumption audit (DM9). Opt-in.

It reads the deterministic inventory of a result (``orchestrator.assumptions``)
and a summary of the conclusions, and says for each item how much the conclusion
rests on it. It may add an assumption the inventory missed; such an addition is
shown as the agent's own, not as part of the inventory. ``complete`` checks that
every inventory item was addressed.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from adroit.agents.lagrangian import DEFAULT_DERIVER
from adroit.agents.llm import StructuredLLM
from adroit.core.prompts import TERSE_CLAUSE
from adroit.core.state import StrictModel

AUDIT_SYSTEM = """You audit the assumptions behind a dark matter analysis. Return JSON for the AuditReport schema.

You are given the conclusions and a numbered inventory of the data, conventions, approximations,
statistics, validity limits and model choices the result rests on, each with where it comes from.

Rules:
- Address every inventory item by its id, once: impact critical (the conclusion could change if it were
  wrong), material (the numbers would move appreciably) or minor; and in "effect" one sentence on how and
  in which direction it would change the conclusion.
- In "additional", list assumptions the inventory misses that you are confident entered (at most five).
  They are shown as yours, not as the code's.
- No citations: do not cite papers by identifier or by author and year.
- Return only the JSON object.""" + TERSE_CLAUSE


class Impact(str, Enum):
    """How much a conclusion rests on an assumption: critical, material or minor."""
    critical = "critical"
    material = "material"
    minor = "minor"


class AuditEntry(StrictModel):
    """One inventory item's impact and, in a sentence, its effect on the conclusion."""
    id: str
    impact: Impact
    effect: str


class AuditReport(StrictModel):
    """The audit: one entry per inventory item, the agent's additional assumptions, and a summary."""
    entries: list[AuditEntry] = Field(default_factory=list)
    additional: list[str] = Field(default_factory=list)
    summary: str = ""


class AssumptionAudit:
    """Conclusions and an inventory → the weight of each assumption."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, conclusions: str, inventory: str, run_id: str | None = None) -> AuditReport:
        """The agent's report on the conclusions and the inventory, unchecked (see ``complete``)."""
        content = f"The conclusions:\n{conclusions}\n\nThe inventory:\n{inventory}"
        return self.llm.complete_structured(AUDIT_SYSTEM, [{"role": "user", "content": content}], AuditReport,
                                            model=self.model, run_id=run_id, actor="assumption_audit")


def complete(report: AuditReport, ids: list[str]) -> tuple[list[str], list[str]]:
    """(inventory ids the audit did not address, ids the audit gave that the inventory lacks)."""
    given = [e.id for e in report.entries]
    return [i for i in ids if i not in given], [i for i in given if i not in ids]

"""Vetting the constraint scout's proposals (DM9): deterministic.

- **References.** Each proposal's reference is checked against arXiv or Crossref
  with its claimed title (``retrieval.references``). A proposal whose reference
  cannot be confirmed is dropped, and the drop is reported.
- **DM7's rules.** A tier-3 constraint (relic density, indirect detection,
  colliders, beam dumps, flavour, cosmology) cannot simply apply to a candidate
  without a relativistic completion: "applies" becomes "needs_calculation", with
  the reason. "needs_calculation" must name the calculation.
- **Records.** What survives becomes a *proposed* ``ConstraintRecord``, with
  ``verified_on`` unset: ADROIT uses no record until a person verifies it.
"""

from __future__ import annotations

from pydantic import Field

from adroit.agents.scout import ProposedConstraint, ScoutReport
from adroit.core.dm_state import TIER_OF_CLASS, Applicability, ConstraintRecord
from adroit.core.state import StrictModel
from adroit.retrieval import references as refs


class Vetted(StrictModel):
    """One proposal after vetting."""

    proposal: ProposedConstraint
    reference: refs.Reference
    kept: bool
    changes: list[str] = Field(default_factory=list)       # what the rules corrected
    reason: str = ""                                        # why it was dropped


def _rules(p: ProposedConstraint, has_completion: bool) -> tuple[ProposedConstraint, list[str]]:
    changes = []
    if TIER_OF_CLASS[p.constraint_class] == 3 and not has_completion and p.applicability is Applicability.applies:
        p = p.model_copy(update={"applicability": Applicability.needs_calculation,
                                 "needed_calculation": p.needed_calculation or
                                 f"a relativistic completion of the candidate, and its {p.constraint_class.value}"})
        changes.append("tier 3 without a completion: applies → needs_calculation")
    if p.applicability is Applicability.needs_calculation and not p.needed_calculation.strip():
        p = p.model_copy(update={"needed_calculation": "the calculation the scout did not name"})
        changes.append("needs_calculation without the calculation named")
    if p.applicability is Applicability.applies_with_assumptions and not p.assumptions:
        p = p.model_copy(update={"applicability": Applicability.needs_calculation,
                                 "needed_calculation": "the assumptions under which it would apply"})
        changes.append("applies_with_assumptions without assumptions → needs_calculation")
    return p, changes


def vet(report: ScoutReport, has_completion: bool, resolver: refs.Resolver | None = None,
        cache: refs.ReferenceCache | None = None) -> list[Vetted]:
    """Every proposal, its reference checked against its own claimed title, and DM7's rules applied."""
    found = [(refs.find(p.reference) or [refs.Reference(kind="unknown", id=p.reference)])[0] for p in report.proposals]
    checkable = list({r.id: r for r in found if r.kind != "unknown"}.values())
    checked = {r.id: r for r in refs.verify(checkable, resolver, cache)} if checkable else {}
    out = []
    for p, r in zip(report.proposals, found):
        confirmed = checked.get(r.id, r.model_copy(update={"note": "not an arXiv identifier or DOI"}))
        how, why = refs.identify(p.title, confirmed) if confirmed.verified else ("title", "")
        if how != "title":
            confirmed = confirmed.model_copy(update={"verified": False, "note": why})
        corrected, changes = _rules(p, has_completion)
        out.append(Vetted(proposal=corrected, reference=confirmed, kept=confirmed.verified, changes=changes,
                          reason="" if confirmed.verified else f"reference {r.id!r}: {confirmed.note}"))
    return out


def proposed_records(vetted: list[Vetted], candidate: str) -> list[ConstraintRecord]:
    """The kept proposals as records for a person to verify (never usable as they stand)."""
    out = []
    for v in vetted:
        if not v.kept:
            continue
        p = v.proposal
        out.append(ConstraintRecord(
            name=p.name, constraint_class=p.constraint_class,
            source=f"arXiv:{v.reference.id}" if v.reference.kind == "arxiv" else v.reference.id,
            assumptions=p.assumptions, quantity=p.bound,
            checks=[f"proposed by the constraint scout for {candidate}; reference confirmed "
                    f"({v.reference.title!r}, {v.reference.year}) on {v.reference.checked_on}",
                    f"applicability proposed: {p.applicability.value}"
                    + (f"; needs {p.needed_calculation}" if p.needed_calculation else ""),
                    *v.changes]))
    return out


def report(vetted: list[Vetted], candidate: str) -> str:
    """The scout's section of a report: only confirmed references appear."""
    kept, dropped = [v for v in vetted if v.kept], [v for v in vetted if not v.kept]
    lines = [f"### Constraints proposed by the scout for {candidate} (to be verified by a person)", "",
             "| constraint | class | applicability | reference | assumptions or calculation needed |",
             "|---|---|---|---|---|"]
    for v in kept:
        p, r = v.proposal, v.reference
        cite = f"arXiv:{r.id}" if r.kind == "arxiv" else f"doi:{r.id}"
        detail = refs.clean("; ".join(p.assumptions) or p.needed_calculation or "—", [])
        lines.append(f"| {refs.clean(p.name, [])} | {p.constraint_class.value} | {p.applicability.value} | "
                     f"{cite} ({r.year}) | {detail} |")
    if not kept:
        lines.append("| none | | | | |")
    if dropped:
        lines += ["", f"{len(dropped)} proposal(s) dropped because their reference could not be confirmed."]
    return "\n".join(lines) + "\n"

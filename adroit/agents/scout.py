"""The constraint scout (DM9). Opt-in.

It reads a candidate and the abstracts ``retrieval.literature`` found for it, and
proposes constraints, each with DM7's applicability verdict and the paper it comes
from. It writes no number of its own into the analysis: what it proposes is vetted
by ``constraints.scouting`` (every reference checked, DM7's rules enforced) and
becomes at most a *proposed* record, which a person must verify before ADROIT uses it.
"""

from __future__ import annotations

import json

from pydantic import Field

from adroit.agents.lagrangian import DEFAULT_DERIVER
from adroit.agents.llm import StructuredLLM
from adroit.core.dm_state import Applicability, ConstraintClass
from adroit.core.prompts import TERSE_CLAUSE
from adroit.core.state import StrictModel
from adroit.retrieval.literature import Abstract, CandidateSketch

SCOUT_SYSTEM = """You search the literature for constraints on one dark matter candidate. Return JSON for the
ScoutReport schema.

Rules:
- Cite a paper only by its arXiv identifier (e.g. 1510.02110) or DOI, with its title in "title". Prefer
  the papers in the retrieved list. Cite another only if you are certain of its identifier and title:
  every reference is checked against arXiv or Crossref, and one that does not match is removed.
- Never cite by author and year alone, and never put a citation in the free-text fields.
- constraint_class: direct_detection, solar_capture, indirect_detection, relic_density, collider,
  beam_dump, flavour or cosmology.
- applicability, as ADROIT's rules define it:
  - applies: the published constraint holds for this candidate as it stands;
  - applies_with_assumptions: it holds under assumptions you list (an annihilation channel, a
    completion, equilibrium in the Sun, ...);
  - needs_calculation: it was derived for another interaction or model; say in needed_calculation what
    must be computed to apply it.
  Relic density, indirect detection, colliders, beam dumps, flavour and cosmology need a relativistic
  completion; for a candidate given only as an effective operator they cannot simply apply.
- Do not say whether the candidate is excluded: ADROIT computes that itself.
- Leave out direct-detection limits ADROIT already applies (listed under "already applied").
- At most eight proposals; none if the retrieved papers bear on nothing.
- Return only the JSON object.""" + TERSE_CLAUSE


class ProposedConstraint(StrictModel):
    """A constraint the scout proposes: its class, the cited paper, its applicability, what it bounds, its
    assumptions and the calculation it needs."""
    name: str
    constraint_class: ConstraintClass
    reference: str                        # an arXiv identifier or a DOI
    title: str                            # the cited paper's title
    applicability: Applicability
    bound: str = ""                       # what it limits, in words
    assumptions: list[str] = Field(default_factory=list)
    needed_calculation: str = ""
    note: str = ""


class ScoutReport(StrictModel):
    """The scout's proposed constraints and a summary."""
    proposals: list[ProposedConstraint] = Field(default_factory=list)
    summary: str = ""


def context(candidate: CandidateSketch, abstracts: list[Abstract], already: list[str]) -> str:
    """What the scout reads."""
    papers = "\n\n".join(f"[{a.arxiv_id}] {a.title} ({a.year})\n{a.text}" for a in abstracts)
    return (f"The candidate:\n{json.dumps(candidate.model_dump(), indent=1)}\n\n"
            f"Already applied by ADROIT: {', '.join(already) or 'none'}\n\nRetrieved papers:\n\n{papers}")


class ConstraintScout:
    """A candidate and its literature → proposed constraints."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, candidate: CandidateSketch, abstracts: list[Abstract], already: list[str],
            run_id: str | None = None) -> ScoutReport:
        """The scout's proposals, unvetted (see ``constraints.scouting.vet``)."""
        return self.llm.complete_structured(
            SCOUT_SYSTEM, [{"role": "user", "content": context(candidate, abstracts, already)}],
            ScoutReport, model=self.model, run_id=run_id, actor="constraint_scout")

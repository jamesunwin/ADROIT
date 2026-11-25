"""The variant agent of Path 2 (DM9). Opt-in.

It reads the leading candidates of a fit to a signal, the reasons some of them call
for a variant (``orchestrator.variants.triggers``) and a numbered menu of one-step
deformations along the neighbour graph, and picks from the menu with a physical
reason. It cannot propose anything that is not on the menu: ``choose`` discards
such picks. Fitting, combining and accepting a variant are deterministic
(``orchestrator.variants``).
"""

from __future__ import annotations

from pydantic import Field

from adroit.agents.lagrangian import DEFAULT_DERIVER
from adroit.agents.llm import StructuredLLM
from adroit.core.prompts import TERSE_CLAUSE
from adroit.core.state import StrictModel

PER_LEADER = 2

VARIANT_SYSTEM = """You choose variants of the leading dark matter candidates of a fit to the events of a
direct-detection search. Return JSON for the VariantChoices schema.

Rules:
- Choose only from the numbered menu, by its index. Never invent a card, a parameter or a value.
- Choose only for leaders that have a trigger, at most two per leader, and only a deformation that
  answers its trigger. Choose nothing if no item does.
- The physics of the deformations:
  - a mass splitting (inelastic scattering) needs a minimum speed, which suppresses scattering on light
    nuclei and at low recoil energy and moves the spectrum up: it weakens limits from light targets and
    low thresholds;
  - the other isospin (neutron and proton couplings of opposite sign, or equal) changes the rates on
    targets with different neutron fractions;
  - a light mediator enhances low momentum transfer (rates ∝ 1/q⁴), favouring light targets and low
    recoils;
  - a neighbouring operator or Lagrangian changes the momentum and velocity dependence of the
    spectrum, and which nuclear responses (spin, orbital) it probes.
- For each pick, give one sentence that names the trigger and why the deformation could answer it.
- Return only the JSON object.""" + TERSE_CLAUSE


class VariantPick(StrictModel):
    """One pick from the menu, by its index, with the sentence naming the trigger it answers."""
    index: int
    rationale: str


class VariantChoices(StrictModel):
    """The agent's picks and a summary."""
    picks: list[VariantPick] = Field(default_factory=list)
    summary: str = ""


class VariantAgent:
    """Leaders, triggers and a menu → the variants worth fitting."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, context: str, run_id: str | None = None) -> VariantChoices:
        """The agent's picks, unfiltered (see ``choose``)."""
        return self.llm.complete_structured(VARIANT_SYSTEM, [{"role": "user", "content": context}],
                                            VariantChoices, model=self.model, run_id=run_id,
                                            actor="variant_agent")


def choose(choices: VariantChoices, menu_parents: dict[int, str],
           triggered: set[str]) -> tuple[dict[int, str], list[str]]:
    """(index → rationale) for the picks that stand, and why the others were discarded."""
    kept: dict[int, str] = {}
    per_parent: dict[str, int] = {}
    discarded = []
    for pick in choices.picks:
        parent = menu_parents.get(pick.index)
        if parent is None:
            discarded.append(f"{pick.index}: not on the menu")
        elif parent not in triggered:
            discarded.append(f"{pick.index}: {parent} has no trigger")
        elif pick.index in kept:
            discarded.append(f"{pick.index}: chosen twice")
        elif per_parent.get(parent, 0) >= PER_LEADER:
            discarded.append(f"{pick.index}: more than {PER_LEADER} for {parent}")
        else:
            kept[pick.index] = pick.rationale
            per_parent[parent] = per_parent.get(parent, 0) + 1
    return kept, discarded

"""The agent of Signal best fits' agent-led search (the owner, 2026-11-18, the signal best fits plan, phase C).
Opt-in and paid.

Each round it reads the signal, the leading candidates and a numbered menu of one-step deformations of them (the
neighbour graph's, ``orchestrator.variants``, and finer masses about each leader), and picks the ones most likely to
explain the events better, each with a physical reason, or stops. It never computes: the fits, the combinations, the
acceptance and the significance are deterministic (``orchestrator.signal_search``). At the end it writes what the
ranking means, in the manner of an appendix that ranks operators; the numbers in that text are checked against the
result."""
from __future__ import annotations

from pydantic import Field

from adroit.agents.llm import StructuredLLM
from adroit.core.prompts import TERSE_CLAUSE
from adroit.core.state import StrictModel

SEARCH_SYSTEM = """You steer the search for the dark matter interactions that explain the events of a direct-detection
search. A fixed scan has fitted every library interaction (non-relativistic operators and Lagrangians, isoscalar and
isovector, across masses) to the events and ranked them, with the searches that saw nothing, by AIC. Return JSON for
the SearchChoices schema.

Rules:
- Choose only from the numbered menu, by its index. Never invent a card, a parameter or a value.
- Choose the deformations most likely to explain the events better than their parent once the null searches are
  included, at most the number you are told. Each is charged one more free parameter and joins the ranking only if it
  beats its parent by ΔAIC > 2, so choose with a physical reason, not at random.
- Stop (stop = true, with the reason) when nothing on the menu is likely to improve the ranking.
- The physics of the deformations:
  - a mass splitting (inelastic scattering) needs a minimum speed: it suppresses light nuclei and low recoils and
    moves the spectrum up, weakening limits from light targets and low thresholds;
  - the other isospin changes the rates on targets with different neutron fractions;
  - a light mediator enhances low momentum transfer (rates ∝ 1/q⁴), favouring light targets and low recoils;
  - a neighbouring operator or Lagrangian changes the momentum and velocity dependence of the spectrum, and which
    nuclear responses (spin, orbital) it probes; momentum-suppressed ones favour high recoils;
  - a finer mass moves the spectrum's endpoint and its peak against the observed energies.
- For each pick give one sentence: what in the events or the null searches it answers, and why.
- Return only the JSON object.""" + TERSE_CLAUSE

INTERPRET_SYSTEM = """You explain, for a physicist, what a ranking of dark matter interactions fitted to the events of
a direct-detection search shows: which interactions explain the events, which do not and why (the recoil spectrum's
shape, the target's nuclear responses, the tension with the searches that saw nothing), what the global significance
means, and what would tell the leaders apart. Return JSON for the Interpretation schema.

Rules:
- Use only the ranking, the significance and the search's facts you are given. Name candidates by their labels.
- Quote a number only as it is given to you (the same digits); never compute a new one.
- Say plainly where the evidence is weak (a global significance below 3σ is not evidence of a signal).
- At most 250 words.
- Return only the JSON object.""" + TERSE_CLAUSE


class SearchPick(StrictModel):
    """One pick from the menu, by its index, with its reason."""
    index: int
    why: str


class SearchChoices(StrictModel):
    """A round's picks, or the end of the search."""
    picks: list[SearchPick] = Field(default_factory=list)
    stop: bool = False
    reason: str = ""
    summary: str = ""


class Interpretation(StrictModel):
    """What the ranking means, as the agent reads it."""
    text: str


class SearchAgent:
    """The leaders, what was tried and a menu → the deformations to fit next, or stop; and at the end, the reading."""

    def __init__(self, llm: StructuredLLM, model: str) -> None:
        self.llm, self.model = llm, model

    def choose(self, context: str) -> SearchChoices:
        """The round's picks, unfiltered (``orchestrator.signal_search.kept`` keeps those on the menu)."""
        return self.llm.complete_structured(SEARCH_SYSTEM, [{"role": "user", "content": context}], SearchChoices,
                                            model=self.model, actor="signal_search", max_tokens=2048)

    def interpret(self, context: str) -> Interpretation:
        """The ranking explained."""
        return self.llm.complete_structured(INTERPRET_SYSTEM, [{"role": "user", "content": context}], Interpretation,
                                            model=self.model, actor="signal_interpretation", max_tokens=2048)

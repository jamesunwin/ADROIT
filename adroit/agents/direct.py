"""The direct-prompting baseline of DM10: a language model asked outright which candidate made the events.

No fitting and no spectra. The model is told what Path 2 is told (the
target, the energy window, the expected background, the event energies) and
the candidate list with what each label means. It names its best candidate and
every candidate it could not rule out against it. The evaluation scores this
answer on the same injection cases as the system (``evaluation.baselines``).
"""

from __future__ import annotations

from pydantic import Field

from adroit.agents.lagrangian import DEFAULT_DERIVER
from adroit.agents.llm import StructuredLLM, with_cached_prefix
from adroit.core.prompts import TERSE_CLAUSE
from adroit.core.state import StrictModel

MAX_PLAUSIBLE = 30

DIRECT_SYSTEM = f"""You identify which dark matter interaction most likely produced the nuclear-recoil events
of a direct-detection search. Return JSON for the DirectAnswer schema.

Rules:
- Use only labels from the candidate list, exactly as written.
- best: the single most likely candidate, given the event energies, the target, the window and the
  expected background.
- plausible: the candidates these events cannot rule out against best (best included), at most
  {MAX_PLAUSIBLE}, the most likely first.
- reason: one sentence.
- Return only the JSON object.""" + TERSE_CLAUSE


class DirectAnswer(StrictModel):
    """The agent's best candidate, the candidates the events cannot rule out against it, and a one-sentence reason."""
    best: str
    plausible: list[str] = Field(default_factory=list)
    reason: str = ""


class DirectAgent:
    """A search's events and a candidate list → the model's best candidate and its plausible set."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, candidates: str, case: str, run_id: str | None = None) -> DirectAnswer:
        """``candidates`` (the stable list, cached across cases) then ``case`` (the events)."""
        return self.llm.complete_structured(
            DIRECT_SYSTEM, [{"role": "user", "content": with_cached_prefix(candidates, case)}],
            DirectAnswer, model=self.model, run_id=run_id, actor="direct_baseline")


def clean(answer: DirectAnswer, labels: list[str]) -> tuple[str | None, list[str], list[str]]:
    """(best, plausible, labels not on the list): the answer kept to the list, best first in its set."""
    known = set(labels)
    invented = [x for x in [answer.best, *answer.plausible] if x not in known]
    best = answer.best if answer.best in known else None
    plausible = list(dict.fromkeys([*([best] if best else []), *(x for x in answer.plausible if x in known)]))
    return best, plausible[:MAX_PLAUSIBLE], list(dict.fromkeys(invented))

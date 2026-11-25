"""The baselines of DM10, on the injection cases.

- **Exhaustive likelihood fitting, no agents.** Every candidate is fitted and the
  single best is named: its success is the injection suite's exact rate,
  reported there beside the system's set (``injection``).
- **Direct prompting.** A language model is told the events and the candidate
  list and names its best candidate and plausible set (``agents.direct``). Its
  cases are the first PER_POINT injection cases of each target and number of
  events, in the injection suite's halves (the held-out cases stay held out).
  It is scored as the system is: exact; pairwise (its best cannot be told from
  the injected candidate with N events at 2σ); its class; and whether its
  plausible set holds the injected candidate, with the set's size.
"""

from __future__ import annotations

import numpy as np

from adroit.agents.direct import DirectAgent, clean
from adroit.evaluation import injection
from adroit.evaluation.core import Case, CaseResult, Suite
from adroit.library.interactions import registry

PER_POINT = 10


def cases(per_point: int = PER_POINT) -> list[Case]:
    """The first ``per_point`` injection cases of each target and number of events.

    Ordered by index first, so that a run stopped by its budget has covered every
    target and number of events about equally.
    """
    chosen = [c for c in injection.cases() if c.inputs["index"] < per_point]
    order = {t: i for i, t in enumerate(injection.TARGETS)}
    return sorted(chosen, key=lambda c: (c.inputs["index"], c.inputs["events"], order[c.inputs["target"]]))


def candidate_text(target: str) -> str:
    """The candidate list with a legend: what each card is, and how a label is written."""
    models = injection.models(target)
    cards = list(dict.fromkeys(card for _, card, _, _, _ in models))
    legend = [f"- {card.removesuffix('_LZ')}{' (LZ convention)' if card.endswith('_LZ') else ''}: "
              f"{registry.card(card).name}" for card in cards]
    return "\n".join([
        f"Candidates for the target of '{injection.TARGETS[target][0]}'.",
        "A label is the card, then s (isoscalar: equal couplings to protons and neutrons) or v (isovector: "
        "opposite couplings), then @ the dark matter mass in GeV, then for some ',d=' a mass splitting in keV "
        "(inelastic scattering). O<n> are the nonrelativistic operators of Fitzpatrick et al.; L<nn> are "
        "relativistic interactions. The cards:", *legend, "",
        f"The {len(models)} candidates:", ", ".join(m[0] for m in models)])


def case_text(case: Case, events: np.ndarray) -> str:
    """What the search shows: target, window, background and the event energies."""
    target = case.inputs["target"]
    _, energies, _, b_star, _ = injection.table(target)
    low, high = float(energies[0]), float(energies[-1])
    return (f"Search: {injection.TARGETS[target][0]}; target {target.split()[0]}; nuclear-recoil energies from "
            f"{low:.3g} to {high:.3g} keV. Expected background {b_star * (high - low):.3g} events, flat in energy over the "
            f"window. The signal strength is free: judge by how the energies are distributed. "
            f"{events.size} events observed, at (keV): {', '.join(f'{e:.2f}' for e in np.sort(events))}.")


def suite(agent: DirectAgent, per_point: int = PER_POINT) -> Suite:
    """The direct-prompting suite for one agent (one model)."""

    def run_case(case: Case) -> CaseResult:
        target, n = case.inputs["target"], case.inputs["events"]
        labels, _, _, _, n2 = injection.table(target)
        k, events = injection.draw(case)
        best, plausible, invented = clean(agent.run(candidate_text(target), case_text(case, events)), labels)
        i = labels.index(best) if best else None
        pairwise = i is not None and (i == k or n2[i, k] > n)
        same_class = i is not None and injection.classes(target, n)[best] == injection.classes(target, n)[labels[k]]
        return CaseResult(case_id=case.id, passed=bool(pairwise),
                          metrics={"injected": labels[k], "best": best or "none", "exact": i == k,
                                   "same_class": bool(same_class), "in_top_set": labels[k] in plausible,
                                   "top_set_size": len(plausible), "invented": len(invented)},
                          note="" if pairwise else f"injected {labels[k]}, named {best}")

    return Suite(name=f"direct_prompting_{agent.model}", description="direct prompting of a language model "
                 "on the injection cases", cases=lambda: cases(per_point), run_case=run_case,
                 summarise=injection.summarise)

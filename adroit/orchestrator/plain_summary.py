"""A plain-language summary at the head of the "Explain a signal" report (the owner, 2026-11-19: "the writing in the
reports is very dense and hard to understand"; the deferred list OB-09).

Every sentence is read from the result's own fields: nothing is computed here, and the detailed report below the
summary is unchanged. Whether a fit explains the signal is said from the study's own assessment (``fit_quality``,
over every fit it evaluated: the sampled masses, the refined points where the relic density is right and the
equation-of-state refits), never from the absence of a row; what each sampled or refined point shows is then said as
of that point (the auditor's audit of 2026-11-19, MF-06). The same summary for the Constrain-a-model and Signal-best-fits
reports, and the rewording of the reports' detailed text, are deferred to 1.0.1 (OB-09).
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adroit.orchestrator.single_idea import SingleIdeaResult

# what each state of a fit (``single_idea._fit_state``) means, said plainly, in the order they are given
FIT_PLAIN = {
    "eligible": "matches the events at least 1σ better than background alone",
    "below": "is less than 1σ better than background alone",
    "edge": "runs to the edge of {param}'s allowed range",
    "unresolved": "does not settle",
    "unidentifiable": "cannot pin {param} down",
    "no_statistic": "gives no usable fit statistic",
}

# the study's own assessment of its fits (``SingleIdeaResult.fit_quality``, ``single_idea._fit_verdict``), said plainly
FIT_LEAD = {
    "fits": "at least one fit meets the anomaly-fit criterion, at least 1σ better than background alone",
    "no_fit": "no fit meets the anomaly-fit criterion: every one is less than 1σ better than background alone",
    "undetermined": "whether any fit meets the anomaly-fit criterion (at least 1σ better than background alone) is not "
                    "established",
}

# what each headline level (``single_idea.LEVELS``) means, said plainly
LEVEL_PLAIN = {
    "no_fit": "No fit meets the anomaly-fit criterion, so by that criterion the model does not explain the signal.",
    "viable": "A point where the model has the observed relic density fits the signal and passes every applicable "
              "search.",
    "viable_pending": "A point where the model has the observed relic density fits the signal; some searches are still "
                      "undecided there.",
    "excluded": "Every point where the model has the observed relic density and fits the signal is excluded by another "
                "search.",
    "no_thermal": "No point where the model fits the signal was resolved at the observed relic density among the masses "
                  "searched; features between them are not ruled out.",
    "undetermined": "Whether the model explains the signal is not yet decided.",
}


def mass(value: float) -> str:
    """A mass in GeV to three significant figures, without an exponent: 1000, 84.4, 7.12."""
    return f"{float(f'{value:.3g}'):g}"


def masses(values: list[float], picked: list[int]) -> str:
    """The rows ``picked`` (positions in ``values``, the masses in the order the result holds them) said as runs of
    neighbouring rows: "5–59.3 GeV (8 masses)" for a run whose masses rise, "120 and 171 GeV", "84.4 GeV and 243–1000
    GeV (5 masses)". A run whose masses do not rise strictly (unsorted or repeated) is said mass by mass, never as an
    interval, and a mass held by several of the rows picked is said once with their number: "10 GeV (2 points)"
    (the auditor's audit of 2026-11-19, MF-08: rows had been picked by their mass's value, not by their position)."""
    runs: list[list[int]] = []
    for i in sorted(picked):
        if runs and runs[-1][-1] == i - 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    parts: list[str] = []
    for run in runs:
        v = [values[i] for i in run]
        if len(v) > 1 and all(a < b for a, b in zip(v, v[1:])):
            parts.append(f"{mass(v[0])} and {mass(v[1])} GeV" if len(v) == 2 else
                         f"{mass(v[0])}–{mass(v[-1])} GeV ({len(v)} masses)")
        else:
            parts += [f"{mass(x)} GeV" for x in v]
    said = [part if n == 1 else f"{part} ({n} points)" for part, n in Counter(parts).items()]
    return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1]


def _count(n: int, rows: list) -> str:
    """"n masses", or "n points" where some of ``rows`` share a mass (MF-08)."""
    distinct = len({b.m_chi for b in rows}) == len(rows)
    return f"{n} {'mass' if distinct else 'point'}{'' if n == 1 else ('es' if distinct else 's')}"


def _signal(result: "SingleIdeaResult") -> str:
    best = max(result.band, key=lambda b: b.z_local)
    if best.z_local <= 0:
        return ("**The signal.** With its size left free, the model's signal fits the events no better than "
                "background alone at any of the masses tried.")
    n = len({b.m_chi for b in result.band})
    # a promoted study's value is bounded by its parent's (``single_idea._fitted``; MF-07)
    scope = (f"Its significance is {result.global_z:.1f}σ: the smaller of this study's own, over its {n} masses, and "
             "that of the library-wide search it was promoted from, which allows for everything that search tried."
             if result.request.parent_global_z is not None else
             f"Allowing for the {n} masses tried, its significance is {result.global_z:.1f}σ: a measure of how "
             "unlikely background alone is to give an excess this large at any of them.")
    return (f"**The signal.** With its size left free, the model's signal matches the events best at "
            f"m_χ = {mass(best.m_chi)} GeV. {scope}")


def _clauses(rows: list, param: str) -> list[str]:
    """What each state of the fits in ``rows`` shows, at the masses that show it (``FIT_PLAIN``, ``masses``)."""
    from adroit.orchestrator.single_idea import _fit_state
    values = [b.m_chi for b in rows]
    groups: dict[str, list[int]] = {}
    for i, b in enumerate(rows):
        groups.setdefault(_fit_state(b), []).append(i)
    return [f"{FIT_PLAIN[state].format(param=param)} at {masses(values, groups[state])}"
            for state in FIT_PLAIN if state in groups]


def _couplings(result: "SingleIdeaResult") -> str:
    """The study's own assessment of its fits (``FIT_LEAD``; none said for an older result without one), then what the
    fit shows at the sampled masses and at the refined points the assessment also counts (``single_idea._fits``: the
    certified relic points, and the equation-of-state tables' refits)."""
    from adroit.orchestrator.single_idea import _certified
    param = result.band[0].fitted_parameter
    lead = FIT_LEAD.get(result.fit_quality, "")
    text = (f"**The model's own couplings** ({param} varied within its allowed range, the rest fixed): "
            + (f"{lead}. " if lead else "") + "At the sampled masses, the fit "
            + "; it ".join(_clauses(result.band, param)) + ".")
    refined = [*(t for t in result.thermal if _certified(t)), *(b for rows in result.eos_thermal.values() for b in rows)]
    if refined:
        text += (" At the refined points where the relic density is right, it "
                 + "; it ".join(_clauses(refined, param)) + ".")
    return text


def _searches(result: "SingleIdeaResult") -> str:
    points = [b for b in result.band if b.point is not None]
    if not points:
        return ""
    excluded = [b for b in points if b.status == "excluded"]
    allowed = [b for b in points if b.status == "viable"]
    undecided = [b for b in points if b.status not in ("excluded", "viable")]
    by = sorted({name for b in excluded for name in b.excluded_by})
    text = (f"**The other searches.** Of the {_count(len(points), points)} with a model point, "
            + (f"{len(excluded)} {'is' if len(excluded) == 1 else 'are'} excluded, by {', '.join(by)}; "
               if excluded else "none is excluded; ")
            + f"{len(undecided) or 'none'} {'is' if len(undecided) == 1 else 'are'} undecided; "
            + (f"{len(allowed)} {'is' if len(allowed) == 1 else 'are'} allowed." if allowed else "none is allowed."))
    reasons = Counter(name for b in undecided for name in {r.split(":", 1)[0].strip() for r in b.pending if r})
    if reasons:
        text += " Most often undecided: " + ", ".join(f"{name} at {_count(n, points)}"
                                                      for name, n in reasons.most_common(3)) + "."
    return text


def _relic(result: "SingleIdeaResult") -> str:
    if result.thermal:
        statuses = Counter(b.status for b in result.thermal)
        n = len(result.thermal)
        return (f"**The relic density.** The model has the observed relic density at {n} point"
                f"{'' if n == 1 else 's'} of the band, at "
                f"{masses([b.m_chi for b in result.thermal], list(range(n)))}: "
                f"{statuses.get('excluded', 0)} excluded, {statuses.get('pending', 0)} undecided, "
                f"{statuses.get('viable', 0)} allowed.")
    none = "**The relic density.** No point where the relic density is right was resolved among the masses searched"
    if result.thermal_pending:                    # reasons of several kinds, not a count of calculations (MF-06)
        n = len(result.thermal_pending)
        return f"{none}; section 1 lists {n} open item{'' if n == 1 else 's'} that bear on it."
    return f"{none}; features between the sampled masses are not ruled out."


def single_idea(result: "SingleIdeaResult") -> list[str]:
    """The report's "In brief" section, or [] where the study has no fitted band."""
    if not result.band:
        return []
    lines = ["## In brief", "", f"- {_signal(result)}"]
    if result.unsupported:
        lines.append(f"- **The model's own couplings** were not fitted: {result.unsupported}.")
    elif any(b.point is not None or b.physical_fit is not None for b in result.band):
        lines.append(f"- {_couplings(result)}")
        searches = _searches(result)
        lines += [f"- {searches}"] if searches else []
        lines.append(f"- {_relic(result)}")
    level = LEVEL_PLAIN.get(result.level, "")
    if level:
        lines.append(f"- **Overall.** {level}" + (f" The headline's reason: {result.summary}." if result.summary else ""))
    return lines + [""]

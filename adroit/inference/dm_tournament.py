"""The tournament of dark matter candidates for a signal (DM6).

The criteria depend only on what a candidate predicts (build plan, DM6):

| criterion | quantity |
|---|---|
| signal fit | Z_sig: its likelihood ratio against background alone, in the signal experiment |
| global consistency | Z_J, the joint evidence with the null experiments, and the PG tension χ²_PG |
| complementary constraints | tiers 2 and 3 (DM7): each candidate's verdicts, recorded beside it |
| information | AIC relative to the background alone: −Z_J² + 2k, with k free parameters |

**The ranking** is by AIC, lowest first, ties broken by label. The
background-only hypothesis is always a candidate, with AIC 0. This keeps the
invariant rule of the inherited tournament: relabelling a candidate's
parameters cannot change its rank.

**The records:**
- the indistinguishable set: every candidate within ΔAIC ≤ 2 of the best,
  with the degeneracy classes it spans;
- contested winners: the candidate best by the signal fit alone differs from
  the one best by AIC;
- each candidate's flags.

**Complementary constraints do not move the ranking.** A tier-2 or tier-3
verdict rests on assumptions beyond the candidate (an annihilation channel,
equilibrium in the Sun, a thermal history, a completion), so it is recorded
beside the candidate, with those assumptions, rather than folded into the
AIC (decision of DM7).
"""

from __future__ import annotations

import math

from pydantic import Field

from adroit.core.state import StrictModel
from adroit.inference.combination import Combination

NULL = "background only"
INDISTINGUISHABLE_DAIC = 2.0


class Entry(StrictModel):
    """One candidate's standing."""

    label: str
    z_signal: float
    z_joint: float
    chi2_pg: float
    p_pg: float
    aic: float
    delta_aic: float = 0.0
    class_id: int | None = None
    complementary: str = "—"
    flags: list[str] = Field(default_factory=list)
    omitted_nulls: dict[str, str] = Field(default_factory=dict)
    null_coverage: str = "not_requested"


class TournamentResult(StrictModel):
    """The ranking and its records."""

    ranking: list[Entry]
    indistinguishable: list[str]
    classes_in_top_set: list[int]
    contested: str = ""
    signal_fit_leader: str
    null_rank: int
    parameters_per_candidate: int = 1


def run(combinations: list[Combination], classes: dict[str, int] | None = None,
        flags: dict[str, list[str]] | None = None, free_parameters: int = 1,
        complementary: dict[str, str] | None = None,
        extra_parameters: dict[str, int] | None = None) -> TournamentResult:
    """Rank the candidates and the background-only hypothesis.

    ``extra_parameters`` charges a candidate more free parameters than the rest (a DM9
    variant, chosen after the data were seen, pays one more).
    """
    classes, flags, complementary = classes or {}, flags or {}, complementary or {}
    extra = extra_parameters or {}
    if infinite := [c.label for c in combinations if not math.isfinite(c.z_joint)]:
        # Z_J is infinite only where the background-only likelihood vanishes; AIC against it then orders nothing
        # (the RZ23 re-audit's RF23-03: a label order and NaN ΔAIC had been exported). Path 2 refuses such a search
        raise ValueError(f"the joint evidence of {', '.join(infinite)} is not finite: the background-only likelihood "
                         "vanishes or a fit failed, and the AIC ranking against it is not defined")
    entries = [Entry(label=NULL, z_signal=0.0, z_joint=0.0, chi2_pg=0.0, p_pg=1.0, aic=0.0,
                     complementary="—")]
    for c in combinations:
        entries.append(Entry(label=c.label, z_signal=c.z_signal, z_joint=c.z_joint,
                             chi2_pg=c.chi2_pg, p_pg=c.p_pg,
                             aic=-c.z_joint ** 2 + 2 * (free_parameters + extra.get(c.label, 0)),
                             class_id=classes.get(c.label),
                             flags=flags.get(c.label, []) + [f"null coverage pending: {name}: {reason}"
                                                            for name, reason in c.omitted_nulls.items()],
                             omitted_nulls=c.omitted_nulls, null_coverage=c.null_coverage,
                             complementary=complementary.get(c.label, "not applied")))
    ranked = sorted(entries, key=lambda e: (e.aic, e.label))
    best = ranked[0].aic
    ranked = [e.model_copy(update={"delta_aic": e.aic - best}) for e in ranked]
    top_set = [e.label for e in ranked if e.delta_aic <= INDISTINGUISHABLE_DAIC]
    if ranked[0].label == NULL:
        # with one parameter every candidate has AIC = 2 − Z_J² ≤ 2, so a ΔAIC ≤ 2 set around the background would
        # hold them all: when the background ranks first, no candidate set is formed (release audit minor)
        top_set = [NULL]
    signal_leader = max(entries, key=lambda e: (e.z_signal, e.label)).label
    contested = ("" if signal_leader == ranked[0].label else
                 f"{signal_leader} fits the signal best, but {ranked[0].label} is best once the "
                 "null experiments and the information criterion are included")
    return TournamentResult(
        ranking=ranked, indistinguishable=top_set,
        classes_in_top_set=sorted({e.class_id for e in ranked
                                   if e.label in top_set and e.class_id is not None}),
        contested=contested, signal_fit_leader=signal_leader,
        null_rank=1 + [e.label for e in ranked].index(NULL),
        parameters_per_candidate=free_parameters)

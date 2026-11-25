"""Signal best fits' agent-led search, after the fixed scan (the owner, 2026-11-18, the signal best fits plan,
phase C). Opt-in and paid; the agent only chooses (``agents.signal_search``), everything else is deterministic:

- **Rounds** (at most ``MAX_ROUNDS``). Each round the agent reads the signal, the current leaders and a numbered menu:
  each leader's one-step deformations along the neighbour graph (the other isospin, a mass splitting, a light
  mediator, a neighbouring operator or Lagrangian: ``variants``) and finer masses about it; anything already tried is
  left out. It picks at most ``picks`` with a reason, or stops.
- **Each pick** is a Path 2 candidate like any other (``variants.evaluate``): fitted, combined with the null searches,
  flagged and judged, at the run's halo. It was chosen after the data were seen, so it is charged one more free
  parameter, and joins the ranking only if it beats its parent by ΔAIC > 2. A variant that joined may be deformed in a
  later round.
- **The search stops** when the agent says so, when a round adds nothing to the ranking, when the rounds are spent, or
  when the budget is.
- **The global significance** is recomputed over everything searched and tried: the fixed scan's every candidate (at
  every halo compared) and every variant tried, joined or not (``signal.searched_significance``). The variants were
  chosen by looking at the data, so this is the significance over that set, and is said to be.
- **The interpretation**: the agent's reading of the final ranking; each number in it must be one the result holds
  (as written, to the precision shown), else it is removed and named.

The fixed scan's ranking and its promotion are unchanged; the search is kept beside them (``SignalResult.
agent_search``) and in the report.
"""
from __future__ import annotations

import re

from pydantic import Field

from adroit.agents.budget import BudgetExceeded
from adroit.core.pricing import DEFAULT_PRIMARY
from adroit.core.state import StrictModel
from adroit.experiments import registry as modules
from adroit.inference import dm_tournament
from adroit.library.interactions import registry
from adroit.orchestrator import signal as path2
from adroit.orchestrator import variants

MAX_ROUNDS = 5
MASS_STEPS = (0.7, 0.85, 1.2, 1.4)          # finer masses about a leader's, as factors of it


class SearchSettings(StrictModel):
    """How the agent-led search runs."""
    model: str = DEFAULT_PRIMARY
    rounds: int = Field(default=3, ge=1, le=MAX_ROUNDS)
    picks: int = Field(default=4, ge=1, le=6)          # deformations a round may fit
    leaders: int = Field(default=5, ge=1, le=10)       # leaders a round's menu deforms


def _masses(c: path2.Candidate) -> list[tuple[str, path2.Candidate]]:
    return [(f"mass {c.mass_gev * f:.4g} GeV", c.model_copy(update={"mass_gev": round(c.mass_gev * f, 6),
                                                                      "label": f"{c.label}~M{c.mass_gev * f:.4g}"}))
            for f in MASS_STEPS]


def menu(result: path2.SignalResult, pool: dict[str, path2.Candidate], leaders: list[str],
         tried: set[str]) -> list[variants.VariantOption]:
    """Every one-step deformation of the leaders, and finer masses about each, numbered; none already tried and none
    the search's convention cannot express."""
    module = modules.load_module(result.request.experiment)
    graph = registry.graph()
    out: list[variants.VariantOption] = []
    for label in leaders:
        c = pool.get(label)
        if c is None or not c.card_id:
            continue                                  # a user's model: its deformations are not in the card graph
        options = [(data["deformation"], description, variant)
                   for _, target, data in graph.out_edges(c.card_id, data=True)
                   for description, variant in variants._deformed(c, target, data["deformation"])]
        options += [("refine_mass", description, variant) for description, variant in _masses(c)]
        kept = 0
        for deformation, description, variant in options:
            if variant.label in tried or kept >= variants.MENU_LIMIT:
                continue
            try:
                module.candidate_values(variant.card_id, variant.isospin)
            except (KeyError, ValueError):
                continue
            out.append(variants.VariantOption(index=len(out), parent=label, deformation=deformation,
                                              description=description, candidate=variant))
            kept += 1
    return out


def kept(choices, options: list[variants.VariantOption], most: int) -> tuple[dict[int, str], list[str]]:
    """(index → reason) for the picks that stand (on the menu, once each, at most ``most``), and why the rest were not."""
    on_menu = {o.index for o in options}
    out: dict[int, str] = {}
    discarded = []
    for pick in choices.picks:
        if pick.index not in on_menu:
            discarded.append(f"{pick.index}: not on the menu")
        elif pick.index in out:
            discarded.append(f"{pick.index}: chosen twice")
        elif len(out) >= most:
            discarded.append(f"{pick.index}: more than {most} this round")
        else:
            out[pick.index] = pick.why
    return out, discarded


def _context(result: path2.SignalResult, ranking: dm_tournament.TournamentResult, options, tried_rows: list[str],
             picks: int) -> str:
    module = modules.load_module(result.request.experiment)
    events, _ = module.observations()
    leaders = [f"{e.label}: Z_signal {e.z_signal:.2f}, Z_joint {e.z_joint:.2f}, p_PG {e.p_pg:.2g}, ΔAIC "
               f"{e.delta_aic:.2f}, complementary {e.complementary}" + (f", flags: {'; '.join(e.flags)}" if e.flags
                                                                          else "")
               for e in ranking.ranking[:10] if e.label != dm_tournament.NULL]
    return (f"The search: {result.request.experiment}; {len(events)} events at "
            f"{', '.join(f'{e:.3g}' for e in events)} keV; null searches {', '.join(result.request.null_modules)}.\n"
            f"Global significance of the fixed scan: {result.global_z:.2f}σ.\n\nLeaders:\n" + "\n".join(leaders)
            + ("\n\nTried so far:\n" + "\n".join(tried_rows) if tried_rows else "")
            + f"\n\nChoose at most {picks}. Menu:\n"
            + "\n".join(f"[{o.index}] {o.parent} → {o.description} ({o.deformation})" for o in options))


def _row(o: variants.VariantOutcome) -> path2.TriedVariant:
    c = o.combination
    return path2.TriedVariant(label=o.option.candidate.label, parent=o.option.parent, deformation=o.option.deformation,
                              description=o.option.description, why=o.rationale,
                              z_signal=c.z_signal if c else None, z_joint=c.z_joint if c else None,
                              p_pg=c.p_pg if c else None, aic=o.aic, parent_aic=o.parent_aic, joined=o.joined,
                              error=o.error)


def run(result: path2.SignalResult, llm, settings: SearchSettings | None = None) -> path2.SignalResult:
    """The agent-led search on a finished fixed scan (module docstring): the result with ``agent_search``."""
    from adroit.agents.signal_search import SearchAgent
    settings = settings or SearchSettings()
    agent = SearchAgent(llm, settings.model)
    before = _account(llm)
    pool = variants.candidates_of(result)
    joined: list[variants.VariantOutcome] = []
    outcomes: list[variants.VariantOutcome] = []
    rounds: list[path2.SearchRound] = []
    stopped = ""
    for k in range(1, settings.rounds + 1):
        ranking = variants.with_variants(result, joined)
        leaders = [e.label for e in ranking.ranking if e.label != dm_tournament.NULL][:settings.leaders]
        options = menu(result, pool, leaders, {o.option.candidate.label for o in outcomes})
        if not options:
            stopped = "nothing left on the menu"
            break
        tried_rows = [f"{t.label} ({t.description}): " + ("joined" if t.joined else "did not improve its parent"
                                                           if not t.error else t.error)
                      for t in map(_row, outcomes)]
        try:
            choices = agent.choose(_context(result, ranking, options, tried_rows, settings.picks))
        except BudgetExceeded as error:
            stopped = f"the budget: {error}"
            break
        if choices.stop:
            rounds.append(path2.SearchRound(round=k, leaders=leaders, menu=len(options), summary=choices.summary))
            stopped = f"the agent stopped: {choices.reason or 'no reason given'}"
            break
        picked, discarded = kept(choices, options, settings.picks)
        new = variants.evaluate(result, [o for o in options if o.index in picked], picked,
                                parents={o.option.candidate.label: o.combination for o in joined})
        outcomes += new
        joined += [o for o in new if o.joined]
        pool.update({o.option.candidate.label: o.option.candidate for o in new if o.joined})
        rounds.append(path2.SearchRound(round=k, leaders=leaders, menu=len(options), tried=[_row(o) for o in new],
                                        summary=choices.summary, discarded=discarded))
        if not any(o.joined for o in new):
            stopped = "a round added nothing to the ranking"
            break
    result = _finished(result, agent, settings, rounds, outcomes, joined, stopped)
    settled, uncertain = (now - then for now, then in zip(_account(llm), before))   # after its last request (PS-03)
    return result.model_copy(update={"agent_search": result.agent_search.model_copy(update={
        "spent_usd": settled, "uncertain_usd": uncertain})})


def _account(llm) -> tuple[float, float]:
    """(settled, open or uncertain reservations) in dollars of the client's account as it holds them now
    (``accounting.account_text``'s two figures); a client without one (a test's fake): what it says it spent."""
    account = getattr(llm, "account", None)
    if account is None:
        return float(getattr(llm, "spent", 0.0)), 0.0
    return sum(account.spent.values()), sum(v for _, v in account.reservations.values())


def _finished(result, agent, settings, rounds, outcomes, joined, stopped) -> path2.SignalResult:
    """The search's record: the final ranking, the significance over everything tried, and the interpretation. Its
    observed maximum is that of everything searched: the fixed scan at every halo compared (``halo_scan``), and every
    variant fitted (the auditor's post-review recheck, PS-01: the first halo's alone had been taken)."""
    ranking = variants.with_variants(result, joined)
    tried = [o.option.candidate for o in outcomes if o.combination is not None]
    searched = result.halo_scan.max_local_z if result.halo_scan is not None else result.max_local_z
    z_max = max([result.max_local_z, searched, *(o.combination.z_signal for o in outcomes
                                                 if o.combination is not None)])
    halos = list(result.request.halos) or [result.request.halo]
    significance = path2.searched_significance(
        result.request, halos, z_max, tried,
        "over everything searched and tried ({shapes} signal shapes, the agent's variants among them; they were "
        "chosen by looking at the data, so this is the significance over that set); ")
    significance.pop("shapes", None)
    search = path2.AgentSearch(model=settings.model, rounds=rounds, stopped=stopped, ranking=ranking,
                               tried=len(outcomes), **significance)
    search = _interpreted(result, agent, search)
    return result.model_copy(update={"agent_search": search})


def _interpreted(result: path2.SignalResult, agent, search: path2.AgentSearch) -> path2.AgentSearch:
    """The agent's reading of the final ranking, each number in it checked against what it was given."""
    rows = [f"{e.label}: Z_signal {e.z_signal:.2f}, Z_joint {e.z_joint:.2f}, ΔAIC {e.delta_aic:.2f}"
            for e in search.ranking.ranking[:12]]
    given = (f"The search: {result.request.experiment}. Global significance over everything searched and tried: "
             f"{search.global_z:.2f}σ. Indistinguishable leaders (ΔAIC ≤ 2): {', '.join(search.ranking.indistinguishable)}."
             "\n\nRanking:\n" + "\n".join(rows) + "\n\n" + searched_text(result))
    try:
        text = agent.interpret(given).text
    except BudgetExceeded as error:
        return search.model_copy(update={"stopped": (search.stopped + "; " if search.stopped else "")
                                         + f"no interpretation: the budget: {error}"})
    text, removed = checked_numbers(text, given)
    return search.model_copy(update={"interpretation": text, "removed_numbers": removed})


def searched_text(result: path2.SignalResult) -> str:
    return path2.searched(result)


# A number ends at a non-word character, or at a unit written against it (the auditor's PS-06: "9.87σ" and "20GeV" had
# gone unchecked, since σ and letters are word characters); letters otherwise (L12s, 1st) keep it a word.
NUMBER = re.compile(r"(?<![\w.])[-−+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
                    r"(?=σ|%|×|(?:[kMGT]?eV|pb|fb|ab)(?![A-Za-z])|[^\w.]|\.(?!\d)|$)")


def checked_numbers(text: str, given: str) -> tuple[str, list[str]]:
    """``text`` with each number that ``given`` does not hold (as written) replaced by "[a number not in the result]",
    and those numbers. Numbers inside candidate labels (O1s@20) are words, not numbers."""
    allowed = {m.group(0).replace("−", "-").lstrip("+") for m in NUMBER.finditer(given)}
    removed: list[str] = []

    def keep(m: re.Match) -> str:
        value = m.group(0).replace("−", "-").lstrip("+")
        if value in allowed:                             # its sign as given (PS-06: −2.31 for 2.31 had passed)
            return m.group(0)
        removed.append(m.group(0))
        return "[a number not in the result]"
    return NUMBER.sub(keep, text), removed

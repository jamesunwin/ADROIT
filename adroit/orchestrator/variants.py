"""Variants of Path 2's leaders along the neighbour graph (DM9): the deterministic half.

The variant agent (``agents.variants``) only chooses. This module decides when a
variant is called for, what may be proposed, and whether a proposal is kept:

- **Triggers.** A leader calls for a variant when its fit or a constraint says so:
  tension with the null experiments (parameter goodness of fit p < 0.05), a
  complementary constraint that excludes it, or a best-fit coupling above 4π.
- **The menu.** One-step deformations of the leader's card along the neighbour
  graph (``registry.graph``): the other isospin; a mass splitting; a light
  mediator; a neighbouring card at the same mass. Nothing outside the menu can
  be proposed.
- **Evaluation.** A variant is a Path 2 candidate like any other: fitted to the
  search's events, combined with the null experiments, flagged and judged
  against the complementary constraints.
- **Acceptance.** A variant is chosen after the data are seen, so it is charged
  one more free parameter (k = 2 in AIC = −Z_joint² + 2k). It joins the pool
  only if its AIC is lower than its parent's by more than the tournament's
  indistinguishability threshold, ΔAIC > 2: Z_joint² must rise by more than 4.
"""

from __future__ import annotations

from pydantic import Field

from adroit.constraints import verdicts as complementary
from adroit.core.dm_state import ConstraintVerdict
from adroit.core.state import StrictModel
from adroit.experiments import registry as modules
from adroit.inference import dm_tournament, signal_fit
from adroit.inference.combination import Combination
from adroit.library.interactions import registry
from adroit.orchestrator import signal as path2

TENSION_P = 0.05
SPLITTINGS_KEV = [25.0, 50.0, 100.0, 150.0, 200.0]
LIGHT_MEDIATORS_GEV = [0.01, 0.1, 1.0]
VARIANT_PARAMETERS = 2
MENU_LIMIT = 12


class VariantOption(StrictModel):
    """One deformation a leader may take."""

    index: int
    parent: str
    deformation: str
    description: str
    candidate: path2.Candidate


class VariantOutcome(StrictModel):
    """A proposed variant, fitted like any candidate."""

    option: VariantOption
    rationale: str = ""
    combination: Combination | None = None
    aic: float | None = None
    parent_aic: float | None = None
    joined: bool = False
    flags: list[str] = Field(default_factory=list)
    verdicts: list[ConstraintVerdict] = Field(default_factory=list)
    error: str = ""
    # the records its verdicts read, by id, in the version read (``verdicts.judged``; the auditor's CV recheck, CW-02)
    verdict_records: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)


def candidates_of(result: path2.SignalResult) -> dict[str, path2.Candidate]:
    """The candidates a Path 2 result was run on, by label."""
    module = modules.load_module(result.request.experiment)
    return {c.label: c for c in path2.candidates_for(result.request, module)}


def triggers(result: path2.SignalResult) -> dict[str, list[str]]:
    """The leaders whose fit or constraints call for a variant, and why."""
    entries = {e.label: e for e in result.tournament.ranking}
    out: dict[str, list[str]] = {}
    for combo in result.combinations:
        reasons = []
        if combo.p_pg < TENSION_P:
            reasons.append(f"tension with the null experiments (p_PG = {combo.p_pg:.2g})")
        excluded = [v.constraint_id for v in result.verdicts.get(combo.label, []) if v.excluded]
        if excluded:
            reasons.append(f"excluded by {', '.join(excluded)}")
        if any("above 4π" in flag for flag in entries[combo.label].flags):
            reasons.append("the best-fit coupling is above 4π")
        if reasons:
            out[combo.label] = reasons
    return out


def _splittings(current: float, n: int = 5) -> list[float]:
    """The n splittings nearest the current one: the grid, and ±50 and ±100 keV about it."""
    pool = {d for d in [*SPLITTINGS_KEV, current - 100, current - 50, current + 50, current + 100]
            if d > 0 and d != current}
    return sorted(sorted(pool, key=lambda d: (abs(d - current), d))[:n])


def _deformed(c: path2.Candidate, target: str, deformation: str) -> list[tuple[str, path2.Candidate]]:
    card = registry.card(c.card_id)
    if deformation == "change_isospin" and target == c.card_id:
        other = "v" if c.isospin == "s" else "s"
        return [(f"isospin {other}", c.model_copy(update={"isospin": other, "label": f"{c.label}~iso{other}"}))]
    if deformation == "add_mass_splitting" and target == c.card_id:
        return [(f"splitting {d:g} keV", c.model_copy(update={"splitting_kev": d, "label": f"{c.label}~d{d:g}"}))
                for d in _splittings(c.splitting_kev)]
    if deformation == "make_mediator_light" and target == c.card_id and card.mediator_mass:
        return [(f"mediator {m:g} GeV", c.model_copy(update={"values": {**c.values, card.mediator_mass: m},
                                                             "label": f"{c.label}~m{m:g}"}))
                for m in LIGHT_MEDIATORS_GEV]
    if target != c.card_id:
        return [(f"{deformation.replace('_', ' ')} to {target}",
                 c.model_copy(update={"card_id": target, "label": f"{c.label}~{target}"}))]
    return []


def menu(result: path2.SignalResult, labels: list[str]) -> list[VariantOption]:
    """Every one-step deformation of the given leaders, numbered."""
    module = modules.load_module(result.request.experiment)
    pool = candidates_of(result)
    graph = registry.graph()
    out: list[VariantOption] = []
    for label in labels:
        c, options = pool[label], []
        if not c.card_id:
            continue                              # a user's model: its deformations are not in the card graph
        for _, target, data in graph.out_edges(c.card_id, data=True):
            for description, variant in _deformed(c, target, data["deformation"]):
                try:
                    module.candidate_values(variant.card_id, variant.isospin)
                except (KeyError, ValueError):
                    continue                      # the search's convention cannot express this card
                options.append((data["deformation"], description, variant))
        for deformation, description, variant in options[:MENU_LIMIT]:
            out.append(VariantOption(index=len(out), parent=label, deformation=deformation,
                                     description=description, candidate=variant))
    return out


def _aic(combo: Combination, parameters: int) -> float:
    return -combo.z_joint ** 2 + 2 * parameters


def evaluate(result: path2.SignalResult, options: list[VariantOption],
             rationales: dict[int, str] | None = None,
             parents: dict[str, Combination] | None = None) -> list[VariantOutcome]:
    """Each chosen variant through Path 2's own fit, combination, flags and verdicts, at the run's own halo (its fixed
    benchmark, or each search's published halo). ``parents``: variants that joined earlier, which a variant may
    deform in turn (the agent-led search, ``signal_search``), each charged ``VARIANT_PARAMETERS`` as its parent."""
    from adroit.parameter_space import halo_region
    with halo_region.using(result.request.halo):
        return _evaluate(result, options, rationales, parents or {})


def _evaluate(result: path2.SignalResult, options: list[VariantOption],
              rationales: dict[int, str] | None, joined: dict[str, Combination] | None = None) -> list[VariantOutcome]:
    """``evaluate`` with the run's halo in force."""
    module = modules.load_module(result.request.experiment)
    fixed = path2.fixed_halo()
    parents = {c.label: c for c in result.combinations}
    parameters = {label: VARIANT_PARAMETERS for label in joined or {}}
    parents.update(joined or {})
    events, sigma = module.observations()
    b_events = module.background_at(events)
    out = []
    for option in options:
        c = option.candidate
        outcome = VariantOutcome(option=option, rationale=(rationales or {}).get(option.index, ""))
        try:
            s = path2._signal(module, c)
            fit_ = signal_fit.fit(c.label, signal_fit.event_densities(s.observable, s.density, events, sigma),
                                  b_events, module.background_rate())
            combo = path2._combine(module, c, fit_, result.request)
        except (KeyError, ValueError, ZeroDivisionError) as exc:
            out.append(outcome.model_copy(update={"error": f"{type(exc).__name__}: {exc}"}))
            continue
        aic, parent_aic = _aic(combo, VARIANT_PARAMETERS), _aic(parents[option.parent], parameters.get(option.parent, 1))
        verdicts, read = (complementary.judged(path2._verdict_candidate(module, c, combo.mu_hat_signal),
                                               include_unverified=result.request.unverified_records,
                                               halo=fixed.solar() if fixed is not None else None)
                          if result.request.complementary else ([], {}))
        out.append(outcome.model_copy(update={
            "combination": combo, "aic": aic, "parent_aic": parent_aic, "verdicts": verdicts, "verdict_records": read,
            "joined": aic < parent_aic - dm_tournament.INDISTINGUISHABLE_DAIC,
            "flags": path2._flags(module, c, fit_.z_local, combo.mu_hat_signal)}))
    return out


def with_variants(result: path2.SignalResult, outcomes: list[VariantOutcome]) -> dm_tournament.TournamentResult:
    """The tournament again with the variants that joined: each its own class, charged one more parameter."""
    joined = [o for o in outcomes if o.joined]
    classes = dict(result.classes)
    flags = {e.label: e.flags for e in result.tournament.ranking}
    summaries = {k: complementary.summary(v) for k, v in result.verdicts.items()}
    next_class = max(classes.values(), default=-1) + 1
    for i, o in enumerate(joined):
        label = o.option.candidate.label
        classes[label], flags[label] = next_class + i, o.flags
        summaries[label] = complementary.summary(o.verdicts)
    return dm_tournament.run([*result.combinations, *(o.combination for o in joined)], classes, flags,
                             complementary=summaries,
                             extra_parameters={o.option.candidate.label: VARIANT_PARAMETERS - 1 for o in joined})

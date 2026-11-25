"""DM9's agents on a finished result: variants, the constraint scout and the assumption audit.

Opt-in: nothing here runs without a language-model client. Each agent chooses or
writes; deterministic code decides:
- **Variants** (Path 2 only): triggers, the menu, the fits, the combinations and
  the acceptance are ``orchestrator.variants``.
- **The scout**: the literature is ``retrieval.literature``; every reference is
  checked and DM7's rules applied (``constraints.scouting``); what survives is a
  proposed record for a person to verify.
- **The audit**: the inventory is ``orchestrator.assumptions``; the agent weighs
  each item, and must address all of them.

Every piece of agent text that reaches the report is cleaned of unconfirmed
identifiers and author–year citations (``references.clean``). The gate's measure,
``references.unverified_in`` on the final report, is recorded with the result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import Field

from adroit.agents.audit import AssumptionAudit, AuditReport, complete
from adroit.agents.lagrangian import DEFAULT_DERIVER
from adroit.agents.llm import BudgetExceeded, StructuredLLM
from adroit.agents.rehearsal import Rehearsal
from adroit.agents.scout import ConstraintScout
from adroit.agents.variants import VariantAgent, choose
from adroit.constraints import scouting, viability
from adroit.core.chronology import dated_report, timed
from adroit.core.dm_state import ConstraintRecord
from adroit.core.state import StrictModel
from adroit.inference.dm_tournament import NULL, TournamentResult
from adroit.library.interactions import registry
from adroit.orchestrator import assumptions, variants
from adroit.orchestrator.assumptions import Inventory
from adroit.orchestrator.variants import VariantOption, VariantOutcome
from adroit.constraints.scouting import Vetted
from adroit.retrieval import literature
from adroit.retrieval import references as refs


class AgentRequest(StrictModel):
    """Which of DM9's agents run (variants, scout, audit), the language model, and how many leading candidates the
    scout covers."""
    variants: bool = True
    scout: bool = True
    audit: bool = True
    model: str = DEFAULT_DERIVER
    scout_leaders: int = 3


class AgentResult(StrictModel):
    """What the agents produced on a result: the variants and their tournament, the vetted literature and proposed
    records, the assumption inventory and its audit, and the report's unverified citations."""
    subject: str
    triggers: dict[str, list[str]] = Field(default_factory=dict)
    menu: list[VariantOption] = Field(default_factory=list)
    discarded_picks: list[str] = Field(default_factory=list)
    variants: list[VariantOutcome] = Field(default_factory=list)
    tournament: TournamentResult | None = None
    scouting: dict[str, list[Vetted]] = Field(default_factory=dict)
    proposed_records: list[ConstraintRecord] = Field(default_factory=list)
    inventory: Inventory | None = None
    audit: AuditReport | None = None
    audit_missing: list[str] = Field(default_factory=list)
    audit_unknown: list[str] = Field(default_factory=list)
    report_unverified: list[str] = Field(default_factory=list)
    # why the variants were not run: the result's halo cannot be calculated (``halo_region.checked``), refused before
    # any request was sent (a halo phase 2 audit's HB-02, 2026-11-11)
    variants_refused: str = Field(default="", exclude_if=lambda v: not v)
    stopped: str = ""                         # the budget stop, if one came (G12's live check L7)
    not_run: list[str] = Field(default_factory=list)
    calculation_started_at: str = ""          # UTC, recorded by chronology.timed
    calculation_completed_at: str = ""


@dataclass
class Tools:
    """The deterministic services the agents use; tests replace the network ones."""

    resolver: refs.Resolver | None = None
    fetch: literature.Fetch | None = None
    cache: refs.ReferenceCache | None = None
    literature_cache: object | None = None       # a Path for the literature cache (default: the data folder)


def _stage(out: AgentResult, name: str, step) -> None:
    """One agent: a budget stop keeps the agents already finished, and the rest are listed as not run (G12's live
    check L7: the stop had left the finished agents' replies only in the paid-response journal)."""
    if out.stopped:
        out.not_run.append(name)
        return
    try:
        step()
    except BudgetExceeded as error:
        out.stopped = str(error)
        out.not_run.append(name)


def rehearse(kind: str, result, model: str, req: AgentRequest | None = None, tools: Tools | None = None) -> Rehearsal:
    """The agents on ``result`` at $0: each request's reservation, before any is sent (``agents.rehearsal``)."""
    rehearsal = Rehearsal(model)
    RUNNERS[kind](result, rehearsal, req, tools)
    return rehearsal


def plan_text(rehearsal: Rehearsal, budget: float) -> str:
    """The rehearsal for people: each request's reservation, the cap below which the run cannot finish, and a cap
    that lets it."""
    names = {"variant_agent": "variant agent", "constraint_scout": "constraint scout",
             "assumption_audit": "assumption audit"}
    parts = [f"{names.get(actor, actor)} ${usd:.2f}" for actor, usd in rehearsal.requests]
    return (f"The agents' {len(parts)} request(s), priced before any is sent (each reserves its largest possible cost "
            f"and usually settles at a tenth of it): {'; '.join(parts)}. Below ${rehearsal.largest:.2f} the run "
            f"cannot finish; ${rehearsal.suggested_cap():.2f} lets it, and ${rehearsal.total:.2f} covers every request "
            f"at its largest. The cap given: ${budget:.2f}.")


def _variants(result, llm: StructuredLLM, req: AgentRequest, out: AgentResult) -> None:
    from adroit.parameter_space import halo_region
    try:
        halo_region.checked(result.request.halo)       # what a fresh run refuses, refused before any request (HB-02)
    except ValueError as error:
        out.variants_refused = str(error)
        return
    out.triggers = variants.triggers(result)
    if not out.triggers:
        return
    out.menu = variants.menu(result, list(out.triggers))
    lines = [f"{label}: {'; '.join(why)}" for label, why in out.triggers.items()]
    leaders = [f"{e.label}: Z_signal {e.z_signal:.2f}, Z_joint {e.z_joint:.2f}, p_PG {e.p_pg:.2g}, "
               f"ΔAIC {e.delta_aic:.2f}" for e in result.tournament.ranking if e.label != NULL]
    menu = [f"[{o.index}] {o.parent} → {o.description} ({o.deformation})" for o in out.menu]
    context = ("Leaders:\n" + "\n".join(leaders) + "\n\nTriggers:\n" + "\n".join(lines)
               + "\n\nMenu:\n" + "\n".join(menu))
    picks = VariantAgent(llm, req.model).run(context)
    kept, out.discarded_picks = choose(picks, {o.index: o.parent for o in out.menu}, set(out.triggers))
    out.variants = variants.evaluate(result, [o for o in out.menu if o.index in kept], kept)
    out.tournament = variants.with_variants(result, out.variants)


SPIN_RESPONSES = {"Sigma'", "Sigma''"}
VELOCITY_RESPONSES = {"Delta", "Phi''", "Phi~'"}


def card_keywords(card_id: str) -> list[str]:
    """Search phrases for a card: a mediator's own name, or what an operator's nuclear responses probe."""
    card = registry.card(card_id)
    if card.layer.value == "mediator":
        name = re.sub(r"(?i)\b(dark matter|^an? )\b", "", card.name).strip(" :") or card.name
        return [name.lower()]
    responses = set(card.responses)
    for t in card.terms:
        if t.target in registry.cards():
            responses |= set(registry.card(t.target).responses)
    words = []
    if responses & SPIN_RESPONSES:
        words.append("spin-dependent")
    if "M" in responses:
        words.append("spin-independent")
    if responses & VELOCITY_RESPONSES or "v⊥" in card.interaction:
        words.append("velocity-dependent")
    return [*words, "non-relativistic effective"]


def model_keywords(spec) -> list[str]:
    """Search phrases for a bespoke model, from its terms and fields."""
    words = []
    names = {"dipole": "dipole", "anapole": "anapole", "charge_radius": "charge radius"}
    for t in spec.terms:
        if t.lorentz in names:
            words.append("electric dipole" if "γ" in (t.text or "") and "5" in (t.text or "") and t.lorentz == "dipole"
                         else "magnetic dipole" if t.lorentz == "dipole" else names[t.lorentz])
    for f in spec.fields:
        if f.role.value == "mediator":
            if f.name in ("h", "H"):
                words.append("Higgs portal")
            else:
                kind = next((t.lorentz for t in spec.terms if f.name in [o.field for o in t.fields]), "")
                spin = "vector" if f.spin == 1.0 else "scalar"
                words.append(f"{'axial-vector' if kind == 'axial' and spin == 'vector' else 'pseudoscalar' if kind == 'pseudoscalar' else spin} mediator")
    text = " ".join([spec.name, spec.source, *(t.text for t in spec.terms)]).lower().replace("_", " ")
    words += [w for w in ("anapole", "charge radius", "electric dipole", "magnetic dipole") if w in text]
    if spec.dark_matter.spin == 0.5 and spec.dark_matter.self_conjugate:
        words.append("Majorana")
    return list(dict.fromkeys(words)) or [spec.name.replace("_", " ")]


def sketch_card(c, verdict_names: list[str]) -> literature.CandidateSketch:
    """A Path 2 candidate, as the scout and the queries see it."""
    if not c.card_id:                             # a user's model (DM14)
        return literature.CandidateSketch(label=c.label, interaction=c.model or c.label, mass_gev=c.mass_gev,
                                          splitting_kev=c.splitting_kev, keywords=[(c.model or c.label).replace("_", " ")],
                                          details={"model": c.model, "already judged": ", ".join(verdict_names)})
    card = registry.card(c.card_id)
    return literature.CandidateSketch(label=c.label, interaction=card.name, mass_gev=c.mass_gev,
                                      splitting_kev=c.splitting_kev, keywords=card_keywords(c.card_id),
                                      details={"card": c.card_id, "isospin": c.isospin,
                                               "Lagrangian or operator": card.interaction,
                                               "already judged": ", ".join(verdict_names)})


def sketch_model(spec) -> literature.CandidateSketch:
    """A bespoke model, as the scout and the queries see it."""
    dm = spec.dark_matter
    mediators = [f for f in spec.fields if f.role.value == "mediator"]
    mediator = "; ".join(f"spin-{f.spin:g} {f.name} of {f.mass_gev:g} GeV" for f in mediators if f.mass_gev)
    return literature.CandidateSketch(
        label=spec.name, interaction=spec.name.replace("_", " "), mass_gev=dm.mass_gev or 100.0,
        spin=dm.spin, self_conjugate=dm.self_conjugate, mediator=mediator, keywords=model_keywords(spec),
        couples_to=viability.profile(spec).sectors,
        details={"terms": "; ".join(t.text or t.lorentz for t in spec.terms)})


def _scout(sketch: literature.CandidateSketch, already: list[str], has_completion: bool, llm: StructuredLLM,
           req: AgentRequest, tools: Tools, out: AgentResult) -> None:
    abstracts = literature.search(sketch, tools.fetch, tools.literature_cache)
    report = ConstraintScout(llm, req.model).run(sketch, abstracts, already)
    vetted = scouting.vet(report, has_completion, tools.resolver, tools.cache)
    out.scouting[sketch.label] = vetted
    out.proposed_records += scouting.proposed_records(vetted, sketch.label)


def _audit(inv: assumptions.Inventory, conclusions: str, llm: StructuredLLM, req: AgentRequest,
           out: AgentResult) -> None:
    out.inventory = inv
    out.audit = AssumptionAudit(llm, req.model).run(conclusions, assumptions.text(inv))
    out.audit_missing, out.audit_unknown = complete(out.audit, [i.id for i in inv.items])


@timed
def run_path2(result, llm: StructuredLLM, req: AgentRequest | None = None, tools: Tools | None = None) -> AgentResult:
    """The agents on a Path 2 result (``orchestrator.signal.SignalResult``)."""
    req, tools = req or AgentRequest(), tools or Tools()
    out = AgentResult(subject=f"Path 2 on {result.request.experiment}")
    if req.variants:
        _stage(out, "variants", lambda: _variants(result, llm, req, out))
    if req.scout:
        pool = variants.candidates_of(result)
        ranking = (out.tournament or result.tournament).ranking
        leaders = [e.label for e in ranking if e.label != NULL and e.label in pool][:req.scout_leaders]
        for label in leaders:
            names = [v.constraint_id for v in result.verdicts.get(label, [])]
            _stage(out, f"scout: {label}", lambda label=label, names=names: _scout(
                sketch_card(pool[label], names), ["the direct-detection limits of every experiment module", *names],
                False, llm, req, tools, out))
    if req.audit:
        top = [e for e in result.tournament.ranking[:6]]
        conclusions = (f"global Z = {result.global_z:.2f} ({result.global_method}); ranking: "
                       + "; ".join(f"{e.label} (ΔAIC {e.delta_aic:.2f})" for e in top))
        _stage(out, "audit", lambda: _audit(assumptions.path2(result), conclusions, llm, req, out))
    out.report_unverified = refs.unverified_in(report(out), tools.cache, tools.resolver)
    return out


@timed
def run_path1(result, llm: StructuredLLM, req: AgentRequest | None = None, tools: Tools | None = None) -> AgentResult:
    """The scout and the audit on a bespoke Path 1 result (``orchestrator.lagrangian.LagrangianResult``)."""
    req, tools = req or AgentRequest(), tools or Tools()
    out = AgentResult(subject=f"Path 1 for {result.spec.name}")
    if req.scout:
        _stage(out, "scout", lambda: _scout(sketch_model(result.spec), [
            "the direct-detection limits of every experiment module", "neutrino telescopes through capture in the Sun"],
            True, llm, req, tools, out))
    if req.audit:
        conclusions = f"status {result.status}; " + (
            "; ".join(f"{m.experiment}: strongest μ_up {min(m.mu_up):.3g}" for m in result.exclusion.per_module)
            if result.exclusion else "no limits computed")
        _stage(out, "audit", lambda: _audit(assumptions.path1(result), conclusions, llm, req, out))
    out.report_unverified = refs.unverified_in(report(out), tools.cache, tools.resolver)
    return out


def _verdict_text(v) -> str:
    return f"{v.mode} verdict {v.level}: {v.summary}" if v else ""


@timed
def run_track1(result, llm: StructuredLLM, req: AgentRequest | None = None, tools: Tools | None = None) -> AgentResult:
    """The scout and the audit on a Track 1 result (``orchestrator.track1.Track1Result``); variants are Path 2's."""
    req, tools = req or AgentRequest(), tools or Tools()
    spec = result.request.spec
    out = AgentResult(subject=f"Track 1 for {spec.name}")
    if req.scout:
        _stage(out, "scout", lambda: _scout(sketch_model(spec), assumptions.applied_constraints(result.scan) or
                                            ["the constraints of Track 1's scan"], True, llm, req, tools, out))
    if req.audit:
        conclusions = "; ".join(x for x in (_verdict_text(result.verdict), _verdict_text(result.likelihood_verdict),
                                            f"not computed: {result.unsupported}" if result.unsupported else "") if x)
        _stage(out, "audit", lambda: _audit(assumptions.track1(result), conclusions or "no verdict", llm, req, out))
    out.report_unverified = refs.unverified_in(report(out), tools.cache, tools.resolver)
    return out


@timed
def run_single_idea(result, llm: StructuredLLM, req: AgentRequest | None = None,
                    tools: Tools | None = None) -> AgentResult:
    """The scout and the audit on a single-idea result (``orchestrator.single_idea.SingleIdeaResult``)."""
    req, tools = req or AgentRequest(), tools or Tools()
    r = result.request
    out = AgentResult(subject=f"{r.spec.name} for {r.experiment}")
    if req.scout:
        already = [r.experiment, *r.null_modules, *assumptions.applied_constraints(
            result.track1.scan if result.track1 else None)]
        _stage(out, "scout", lambda: _scout(sketch_model(r.spec), already, True, llm, req, tools, out))
    if req.audit:
        conclusions = (f"level {result.level or 'none'}: {result.summary}; global Z = {result.global_z:.2f} "
                       f"({result.global_method or 'not computed'}); best fit {result.best or 'none'}")
        _stage(out, "audit", lambda: _audit(assumptions.single_idea(result), conclusions, llm, req, out))
    out.report_unverified = refs.unverified_in(report(out), tools.cache, tools.resolver)
    return out


RUNNERS = {"signal": run_path2, "lagrangian": run_path1, "track1": run_track1, "single_idea": run_single_idea}


def read_result(data: dict) -> tuple[str, StrictModel]:
    """A finished result's kind and typed form: Path 2 (signal), Track 1, single-idea or bespoke Path 1
    (lagrangian). Raises ValueError for a kind the agents do not take."""
    from adroit.evidence.results import _detect, result_type
    from adroit.orchestrator.lagrangian import LagrangianResult
    if "tournament" in data:
        kind = "signal"
    else:
        try:
            kind = _detect(data)
        except ValueError:
            kind = "lagrangian"
    if kind not in RUNNERS:
        raise ValueError(f"the agents take Path 2, Track 1, single-idea or bespoke Path 1 results, not {kind}")
    return kind, (LagrangianResult if kind == "lagrangian" else result_type(kind)).model_validate(data)


def _variants_section(r: AgentResult) -> list[str]:
    if not r.triggers:
        return ["## Variants (DM9)", "", "No leader called for a variant.", ""]
    lines = ["## Variants (DM9)", "", *(f"- {k}: {'; '.join(v)}" for k, v in r.triggers.items()), "",
             "| variant | deformation | reason | Z_joint | AIC (parent's) | joined |", "|---|---|---|---|---|---|"]
    for o in r.variants:
        z = f"{o.combination.z_joint:.2f}" if o.combination else o.error
        aic = f"{o.aic:.2f} ({o.parent_aic:.2f})" if o.aic is not None else "—"
        lines.append(f"| {o.option.candidate.label} | {o.option.description} | {refs.clean(o.rationale, [])} | "
                     f"{z} | {aic} | {'yes' if o.joined else 'no'} |")
    if not r.variants:
        lines.append("| none chosen | | | | | |")
    if r.discarded_picks:
        lines += ["", f"{len(r.discarded_picks)} pick(s) discarded: " + "; ".join(r.discarded_picks)]
    return lines + [""]


def _audit_section(r: AgentResult) -> list[str]:
    items = {i.id: i for i in r.inventory.items}
    order = {"critical": 0, "material": 1, "minor": 2}
    entries = sorted((e for e in r.audit.entries if e.id in items), key=lambda e: (order[e.impact.value], e.id))
    lines = ["## Assumption audit (DM9)", "", "| item | category | assumption | impact | effect |", "|---|---|---|---|---|"]
    lines += [f"| {e.id} | {items[e.id].category} | {items[e.id].statement} | {e.impact.value} | "
              f"{refs.clean(e.effect, [])} |" for e in entries]
    if r.audit_missing:
        lines += ["", f"Not addressed by the audit: {', '.join(r.audit_missing)}."]
    if r.audit.additional:
        lines += ["", "Added by the audit agent (its own, not the code's inventory):",
                  *(f"- {refs.clean(x, [])}" for x in r.audit.additional)]
    return lines + [""]




@dated_report
def report(r: AgentResult) -> str:
    """The agents' report in Markdown."""
    lines = [f"# DM9 agents: {r.subject}", ""]
    if r.stopped:
        lines += ["## Stopped by the budget", "", f"{r.stopped}. Not run: {', '.join(r.not_run)}. What follows is "
                  "the agents that finished.", ""]
    if r.variants_refused:
        lines += ["## Variants (DM9)", "", f"Not run: the result's halo cannot be calculated ({r.variants_refused}). "
                  "No variant was asked for or calculated.", ""]
    elif r.triggers or r.variants:
        lines += _variants_section(r)
    for label, vetted in r.scouting.items():
        lines.append(scouting.report(vetted, label))
    if r.audit and r.inventory:
        lines += _audit_section(r)
    return "\n".join(lines) + "\n"

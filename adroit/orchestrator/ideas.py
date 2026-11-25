"""Track 1's front end (DM12): a field content, a Lagrangian or an idea → typed models, each audited.

- **A field content** (a ``ModelSpec`` with fields and no terms needed): the
  generator writes the most general renormalizable Lagrangian, and, if asked,
  the dark sector's effective operators up to dimension 5 or 6.
- **A Lagrangian**, as a typed ``ModelSpec`` or in words through DM8's intake
  agent (opt-in): the audit decides whether it is valid and lists the terms its
  symmetries allow but it leaves out.
- **An idea in words** (opt-in): the model builder proposes field contents;
  each becomes a model through the generator, is audited, and duplicates are
  dropped.

Every model leaves with its audit. Validity here means theoretical consistency
(Lorentz and gauge invariance, matching spins, hermiticity, dimension); what the
data allow is DM13's question.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from adroit.core.chronology import dated_report, timed
from adroit.core.model_spec import ModelSpec, Phase
from adroit.core.state import StrictModel
from adroit.model_building import eft
from adroit.model_building.audit import AuditReport, audit
from adroit.model_building.content import content, new_fields
from adroit.model_building.lagrangian import Operator, general_lagrangian
from adroit.model_building.spec import general_spec


class IdeaRequest(StrictModel):
    """What to start from: exactly one of a field content, a Lagrangian, or an idea."""

    fields_spec: ModelSpec | None = None          # fields (terms ignored): build the most general Lagrangian
    lagrangian_spec: ModelSpec | None = None      # a typed Lagrangian to audit
    lagrangian_text: str = ""                     # a Lagrangian in words (DM8's intake agent)
    text: str = ""                                # an idea in words (the model builder)
    eft_dimension: int = Field(default=4, ge=4, le=6)
    models: int = Field(default=4, ge=1, le=6)


class ModelResult(StrictModel):
    """One model: as given or proposed, its most general Lagrangian, its effective operators and its audit."""

    source: str                                   # fields, lagrangian, or proposal
    spec: ModelSpec
    general: ModelSpec | None = None
    operators: list[Operator] = Field(default_factory=list)
    eft: list[Operator] = Field(default_factory=list)
    audit: AuditReport
    rationale: str = ""
    keywords: list[str] = Field(default_factory=list)
    simplified: str = Field(default="", exclude_if=lambda v: not v)    # what it leaves out (``simplified_name``)


SIMPLIFIED = "(simplified model)"


def simplified_name(name: str) -> str:
    """A simplified model's name: ``name`` ending "(simplified model)", once (the owner, 2026-11-17: a model built
    from part of a larger theory, a supersymmetric model's relevant superpartners only, says so in its name, wherever
    the name is shown)."""
    return name if SIMPLIFIED in name.lower() else f"{name.rstrip()} {SIMPLIFIED}"


class IdeaResult(StrictModel):
    """Track 1's front end on one request: the models built, each with its audit, and the proposals not built, with
    why."""
    request: IdeaRequest
    models: list[ModelResult] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)          # proposals not built, and why
    created: str = Field(default_factory=lambda: str(date.today()))
    calculation_started_at: str = ""          # UTC, recorded by chronology.timed
    calculation_completed_at: str = ""


def signature(spec: ModelSpec) -> tuple:
    """A field content's identity, for removing duplicate proposals (names do not matter)."""
    return tuple(sorted((f.spin, f.self_conjugate, f.chirality, f.charges.su3, f.charges.su2,
                         round(f.charges.hypercharge, 3), f.dark_parity or 1, len(f.charges.extra))
                        for f in new_fields(spec)))


def from_fields(spec: ModelSpec, eft_dimension: int = 4, source: str = "fields") -> ModelResult:
    """The most general Lagrangian of a field content, its effective operators, and its audit."""
    spec = spec.model_copy(update={"phase": Phase.unbroken, "terms": [], "couplings": []})
    ops = general_lagrangian(content(spec))
    general = general_spec(spec, ops)
    extra = eft.operators(spec, eft_dimension) if eft_dimension > 4 else []
    return ModelResult(source=source, spec=spec, general=general, operators=ops, eft=extra, audit=audit(general))


def from_lagrangian(spec: ModelSpec, eft_dimension: int = 4) -> ModelResult:
    """The audit of a given Lagrangian, and (above electroweak breaking) its most general completion."""
    report = audit(spec)
    general, ops = None, []
    if spec.phase is Phase.unbroken:
        try:
            ops = general_lagrangian(content(spec))
            general = general_spec(spec.model_copy(update={"terms": [], "couplings": []}), ops)
        except ValueError:
            pass
    extra = eft.operators(spec, eft_dimension) if eft_dimension > 4 else []
    return ModelResult(source="lagrangian", spec=spec, general=general, operators=ops, eft=extra, audit=report)


def agent_model(llm) -> str:
    """The model the client was made for (the command's --model), else the agents' default."""
    from adroit.agents.lagrangian import DEFAULT_DERIVER
    model = getattr(llm, "model", "")
    return model if isinstance(model, str) and model and model != "unknown" else DEFAULT_DERIVER


def from_idea(idea: str, llm, n: int = 4, eft_dimension: int = 4) -> tuple[list[ModelResult], list[str]]:
    """The model builder's proposals, each generated, completed and audited; only usable models are returned (the
    owner, 2026-11-21: ``complete``), and every proposal not offered is reported with why."""
    from adroit.agents.ideas import IdeaAgent
    from adroit.model_building.usable_models import canonical_fields, prepare
    proposals = IdeaAgent(llm, agent_model(llm)).run(idea, n)
    built, dropped, seen = [], [], set()
    for p in proposals.proposals:
        try:
            name = simplified_name(p.name) if p.simplified.strip() else p.name
            fields, renamed = canonical_fields(p.fields)
            spec = ModelSpec(name=name, phase=Phase.unbroken, source=idea, fields=fields, stability=p.stability,
                             assumptions=[*p.assumptions, *renamed])
            result = from_fields(spec, eft_dimension, source="proposal")
        except ValueError as error:
            dropped.append(f"{p.name}: {error}")
            continue
        key = signature(spec)
        if key in seen:
            dropped.append(f"{p.name}: the same field content as an earlier proposal")
            continue
        seen.add(key)
        built.append((result.model_copy(update={"rationale": p.rationale, "keywords": p.keywords,
                                                "simplified": p.simplified.strip(),
                                                "general": prepare(result.general)}), p.not_encoded))
    return complete(idea, llm, built, dropped)


def complete(idea: str, llm, built: list[tuple[ModelResult, list[str]]],
             dropped: list[str]) -> tuple[list[ModelResult], list[str]]:
    """The generated models with the values of the couplings the idea calls for (the model builder's one further call
    for all of them, ``agents.ideas.ValuesAgent``), the rest zero and stated (``usable_models.finish``). A model that
    cannot run for its values gets one repair round (phase C: the builder sees why, one more call for all of them); a
    model that still cannot run, or cannot for its structure, is not offered and is named in ``dropped`` with why."""
    from adroit.agents.ideas import ValuesAgent
    if not built:
        return [], dropped
    agent = ValuesAgent(llm, agent_model(llm))
    proposed = agent.run(idea, [m.general for m, _ in built], said=[list(ne) for _, ne in built])
    values, conflicts, notes, stray = read_values(proposed, len(built))
    dropped += stray
    out, failing = {}, []
    for i, (m, not_encoded) in enumerate(built, 1):
        given = values.get(i, {})
        offered, reasons = _judge(m, given, [*not_encoded, *notes.get(i, [])], idea, conflicts.get(i, {}))
        if offered is not None:
            out[i] = offered
        else:
            # the first reply's omissions travel with the model (the auditor's UO-08: a repair had dropped them)
            failing.append((i, m, [*not_encoded, *notes.get(i, [])], given, reasons))
    repaired, dropped = _repair_round(idea, agent, failing, dropped)
    out.update(repaired)
    return [out[i] for i in sorted(out)], dropped


def _judge(m: ModelResult, given: dict, notes: list[str], idea: str,
           conflicts: dict) -> tuple[ModelResult | None, list[str]]:
    """One model completed with its values: (the model to offer, []) or (None, why it cannot run)."""
    from adroit.library.personal import usable
    from adroit.model_building.usable_models import UNSOLVED, finish, inert
    spec, problems = finish(m.general, given, notes, idea, conflicts)
    verdict, lost = usable(spec), inert(spec)          # usable() holds unreachable (the route to the SM)
    unsolved = [p for p in problems if p.startswith(UNSOLVED)]       # a completion failure blocks (the auditor's UO-07)
    if not verdict.ok or lost or unsolved:
        return None, list(dict.fromkeys([*problems, *verdict.blocking, *[lost] * bool(lost)]))
    spec = spec.model_copy(update={"assumptions": list(dict.fromkeys([*spec.assumptions, *problems]))})
    return m.model_copy(update={"general": spec, "audit": audit(spec)}), []


STRUCTURAL = ("no engine computes it", "the structural audit found problems")


def repairable(reasons: list[str]) -> bool:
    """Whether new values could let a model run (phase C): not where no engine computes it or its audit fails, nor for
    a mass the proposal did not give (the values call never changes masses), unless its couplings made the stated
    mass impossible (``usable_models.physical_mass``)."""
    if any(r.startswith(STRUCTURAL) for r in reasons):
        return False
    return not any(r.startswith("no value for the mass of") for r in reasons) or \
        any("cannot be its physical mass" in r for r in reasons)


def _not_offered(name: str, first: list[str], after: list[str] = ()) -> str:
    return (f"{name}: not offered, since it cannot run as built: " + "; ".join(first)
            + (f"; after a repair round: {'; '.join(after)}" if after else ""))


def _repair_round(idea: str, agent, failing: list[tuple], dropped: list[str]) -> tuple[dict, list[str]]:
    """Phase C's one repair round (plan section 4.3): the models that cannot run for their values, each with its values
    and why, to the builder once; a model its new values let run is offered and says it was repaired. A round that
    cannot be made (the session's cap, the client) is said for each model."""
    fixable = [f for f in failing if repairable(f[4])]
    dropped += [_not_offered(m.general.name, reasons) for _, m, _, _, reasons in failing if not repairable(reasons)]
    if not fixable:
        return {}, dropped
    try:
        reply = agent.repair(idea, [m.general for _, m, _, _, _ in fixable], [g for _, _, _, g, _ in fixable],
                             [r for *_, r in fixable], said=[ne for _, _, ne, _, _ in fixable])
    except RuntimeError as error:                        # BudgetExceeded is one: the session's cap is kept
        return {}, dropped + [_not_offered(m.general.name, reasons, [f"the repair round could not be made ({error})"])
                              for _, m, _, _, reasons in fixable]
    values, conflicts, notes, stray = read_values(reply, len(fixable))
    dropped += stray
    out = {}
    for j, (i, m, not_encoded, _, reasons) in enumerate(fixable, 1):
        if j not in values:
            dropped.append(_not_offered(m.general.name, reasons, ["the model builder gave no new values"]))
            continue
        offered, again = _judge(m, values[j], [*not_encoded, *notes.get(j, [])], idea, conflicts.get(j, {}))
        if offered is None:
            dropped.append(_not_offered(m.general.name, reasons, again))
            continue
        note = ("repaired: its first values could not run (" + "; ".join(reasons)
                + "); the model builder's second values can")
        out[i] = offered.model_copy(update={"general": offered.general.model_copy(
            update={"assumptions": [*offered.general.assumptions, note]})})
    return out, dropped


def read_values(proposed, n: int) -> tuple[dict[int, dict], dict[int, dict], dict[int, list[str]], list[str]]:
    """The values reply checked before any coupling is set to zero (the auditor's UM-05): (each model's values, each model's
    conflicting values, each model's notes, what was addressed to no model). Entries for the same model are merged;
    two different values for one coupling are a conflict, and neither is used; an entry naming a model that does not
    exist is said, not dropped in silence."""
    values: dict[int, dict] = {}
    seen: dict[int, dict[str, list[float]]] = {}
    notes: dict[int, list[str]] = {}
    stray = []
    for v in proposed.models:
        if not 1 <= v.model <= n:
            stray.append(f"the model builder's values named model {v.model}, but there are {n}: they were not used ("
                         + (", ".join(f"{c.name} = {c.value:g}" for c in v.couplings) or "no couplings") + ")")
            continue
        notes.setdefault(v.model, []).extend(v.not_encoded)
        for c in v.couplings:
            seen.setdefault(v.model, {}).setdefault(c.name, []).append(c.value)
            values.setdefault(v.model, {}).setdefault(c.name, (c.value, c.reason))
    conflicts = {i: {name: xs for name, xs in by_name.items() if len(set(xs)) > 1} for i, by_name in seen.items()}
    return values, conflicts, notes, stray          # finish leaves a conflicting coupling without a value


@timed
def run(request: IdeaRequest, llm=None) -> IdeaResult:
    """Track 1's front end for one request. ``llm`` is needed only for words (a Lagrangian or an idea).

    Raises:
        ValueError: if the request names no input, or needs a language model and has none.
    """
    if request.fields_spec is not None:
        return IdeaResult(request=request, models=[from_fields(request.fields_spec, request.eft_dimension)])
    if request.lagrangian_spec is not None:
        return IdeaResult(request=request, models=[from_lagrangian(request.lagrangian_spec, request.eft_dimension)])
    if llm is None and (request.lagrangian_text or request.text):
        raise ValueError("words need a language model (opt-in): give a budget")
    if request.lagrangian_text:
        from adroit.agents.lagrangian import IntakeAgent
        spec = IntakeAgent(llm, agent_model(llm)).run(request.lagrangian_text)
        return IdeaResult(request=request, models=[from_lagrangian(spec, request.eft_dimension)])
    if request.text:
        models, dropped = from_idea(request.text, llm, request.models, request.eft_dimension)
        return IdeaResult(request=request, models=models, dropped=dropped)
    raise ValueError("give a field content, a Lagrangian, or an idea")


STRUCTURES = {"potential": "scalar potential", "mass": "mass", "yukawa": "Yukawa", "vector_current": "vector current",
              "scalar_current": "scalar current", "vector_scalar": "vector–scalar", "kinetic_mixing": "kinetic mixing",
              "eft": "effective"}


def _fields_table(spec: ModelSpec) -> list[str]:
    lines = ["| field | role | spin | SU(3), SU(2), Y | other charges | Z2 | mass (GeV) |", "|---|---|---|---|---|---|---|"]
    for f in new_fields(spec):
        c = f.charges
        kind = ("real " if f.self_conjugate and f.spin != 0.5 else "Majorana " if f.self_conjugate else
                f"{f.chirality}-handed " if f.chirality else "Dirac " if f.spin == 0.5 else "complex " if f.spin == 0 else "")
        extra = ", ".join(f"{k}: {v:g}" for k, v in c.extra.items()) or "—"
        lines.append(f"| {f.name} | {f.role.value} | {kind}{f.spin:g} | ({c.su3}, {c.su2}, {c.hypercharge:g}) | {extra} | "
                     f"{'odd' if f.dark_parity == -1 else 'even'} | {f.mass_gev if f.mass_gev is not None else '—'} |")
    return lines


def _operators_table(ops: list[Operator]) -> list[str]:
    lines = ["| structure | operator | dimension | couplings | + h.c. |", "|---|---|---|---|---|"]
    lines += [f"| {STRUCTURES.get(o.structure, o.structure)} | {o.text.replace('|', chr(92) + '|')} | {o.dimension:g} | {o.count} | "
              f"{'' if o.hermitian else 'yes'} |" for o in ops]
    return lines


def _model_section(i: int, m: ModelResult) -> list[str]:
    a = m.audit
    lines = [f"## {i}. {m.spec.name} ({m.source})", ""]
    if m.rationale:
        lines += [m.rationale, ""]
    if m.keywords:
        lines += [f"Literature search: {'; '.join(m.keywords)}.", ""]
    lines += _fields_table(m.spec) + [""]
    if m.spec.stability:
        lines += [f"Stability: {m.spec.stability}.", ""]
    groups = sorted({k for f in m.spec.fields for k in f.charges.extra})
    if groups:
        lines += [f"New U(1): {', '.join(groups)}. The Standard Model's fields are taken neutral under it, so they "
                  "couple to its boson only through kinetic mixing (Standard Model charges under new U(1)s, as in a "
                  "gauged B − L, are not yet supported).", ""]
    verdict = "**Valid**" if a.valid else f"**Not valid** ({len(a.problems)} problem(s))"
    lines += [f"{verdict}: Lorentz and gauge invariance, matching spins, hermiticity and dimension"
              f"{' all hold' if a.valid else ''}.", ""]
    lines += [f"- {p.check}: {p.term + ': ' if p.term else ''}{p.message}" for p in a.problems]
    if m.operators and m.source != "lagrangian":
        lines += ["", f"**The most general renormalizable Lagrangian** ({len(m.operators)} operators beyond the "
                  "Standard Model's; kinetic terms and gauge couplings follow from the representations):", ""]
        lines += _operators_table(m.operators)
    if m.eft:
        lines += ["", f"**Effective operators** up to dimension {max(int(o.dimension) for o in m.eft)} "
                  "(coefficient c/Λ^{d−4}); valid only for Λ above direct detection's momentum transfer, the "
                  "freeze-out energy 2m_χ and, for collider limits, the LHC's reach:", ""]
        lines += _operators_table(m.eft)
    if a.missing:
        lines += ["", "**Missing terms**: allowed by the model's own symmetries but absent. A term no symmetry "
                  "forbids is generated by loops even if set to zero:", ""]
        lines += [f"- {t.text} ({t.lorentz})" for t in a.missing]
    if a.flags or a.notes:
        lines += ["", "**Flags and notes:**", ""] + [f"- {x}" for x in [*a.notes, *a.flags]]
    return lines + [""]




@dated_report
def report(result: IdeaResult) -> str:
    """Track 1's front-end report in Markdown."""
    r = result.request
    start = (f"the idea: \"{r.text}\"" if r.text else "a Lagrangian in words" if r.lagrangian_text else
             f"the Lagrangian of {r.lagrangian_spec.name}" if r.lagrangian_spec else
             f"the field content of {r.fields_spec.name}" if r.fields_spec else "")
    lines = ["# Track 1: models and their consistency", "", f"From {start}. {len(result.models)} model(s).", ""]
    for i, m in enumerate(result.models, 1):
        lines += _model_section(i, m)
    if not result.models and result.dropped:              # phase C: said plainly, with what to do
        lines += ["No usable model could be built from this idea. Each proposal is listed below with why it cannot "
                  "run, including any repair round the model builder made. Reword the idea (name the couplings and masses it "
                  "needs), or write the model as a typed model and run it with `adroit models import` ($0).", ""]
    if result.dropped:
        lines += ["## Proposals not offered", ""] + [f"- {d}" for d in result.dropped] + [""]
    return "\n".join(lines) + "\n"

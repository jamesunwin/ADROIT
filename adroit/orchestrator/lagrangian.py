"""Path 1 for arbitrary Lagrangians (DM8): a model → its exclusion limits, with a contract.

The steps:
1. **The model.** A typed ``ModelSpec``, given by the user or produced from a
   description by the intake agent (a language model, opt-in).
2. **Deterministic checks** (``model_checks``): gauge invariance and
   hermiticity must pass; anomalies are flagged.
3. **The derivation.** DirectDM's Wilson coefficients as formulas, given by
   the user or derived by an agent (opt-in).
4. **Verification,** in the plan's order of weight:
   1. the dimension check, and the library: the result is compared with
      every card (``matching``);
   2. on request (``numerical_check``), a numerical cross-check: ADROIT's own
      UFO file of the model goes through MadDM, whose quark-level coefficients
      the derivation must reproduce within 1% (``constraints.maddm``; no
      Mathematica). Dipoles, the anapole and pseudoscalar couplings are not
      covered, and say so;
   3. an independent derivation by a second language model, compared at
      random parameter points: coefficient by coefficient, and, deciding,
      at the nucleon level after DirectDM; up to one overall sign.

   A failed check or a disagreement stops the run for a person to decide.
5. **DirectDM** to the nucleon-level operators, at each dark matter mass, and
   **Path 1's exclusion** in every module.
6. **The contract** (after FERMIACC): what of the full model was dropped, the
   assumptions made, and every mass and coupling with its justification.
"""

from __future__ import annotations

from pydantic import Field

from adroit.agents.lagrangian import DEFAULT_CHECKER, DEFAULT_DERIVER, DerivationAgent, IntakeAgent
from adroit.agents.llm import StructuredLLM
from adroit.constraints import maddm, viability
from adroit.constraints.maddm import AlphaComparison
from adroit.constraints.viability import Entry as ViabilityEntry
from adroit.core.chronology import dated_report, timed
from adroit.core.dm_state import InteractionModel
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.library.interactions import derivation as dv
from adroit.library.interactions import matching, model_checks, quark_level
from adroit.orchestrator import exclusion
from adroit.orchestrator.exclusion import ExclusionResult


class LagrangianRequest(StrictModel):
    """What to compute, from what, and whether language models may be called."""

    description: str = ""
    spec: ModelSpec | None = None
    derivation: dv.Derivation | None = None
    masses_gev: list[float] = Field(default_factory=list)   # empty: the model's dark matter mass
    modules: list[str] = Field(default_factory=list)
    use_language_models: bool = False
    second_derivation: bool = True
    deriver: str = DEFAULT_DERIVER
    checker: str = DEFAULT_CHECKER
    run_exclusion: bool = True
    numerical_check: bool = False          # MadDM installed in the tools folder; minutes per model


class Contract(StrictModel):
    """What the computed benchmark is, and is not, of the full model."""

    dropped: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    masses: dict[str, str] = Field(default_factory=dict)       # field → "value GeV: justification"
    couplings: dict[str, str] = Field(default_factory=dict)    # coupling → "value: justification"


class LagrangianResult(StrictModel):
    """Everything the pipeline did, and where it stopped if it did."""

    request: LagrangianRequest
    status: str = "complete"
    spec: ModelSpec | None = None
    checks: model_checks.CheckReport | None = None
    derivation: dv.Derivation | None = None
    dimension_problems: list[str] = Field(default_factory=list)
    second: dv.Derivation | None = None
    comparison: dv.Comparison | None = None
    numerical: AlphaComparison | None = None
    interactions: dict[str, InteractionModel] = Field(default_factory=dict)
    matches: list[matching.CardMatch] = Field(default_factory=list)
    exclusion: ExclusionResult | None = None
    viability: list[ViabilityEntry] = Field(default_factory=list)
    contract: Contract = Field(default_factory=Contract)
    calculation_started_at: str = ""          # UTC, recorded by chronology.timed
    calculation_completed_at: str = ""


def _contract(spec: ModelSpec, derivation: dv.Derivation | None, extra_dropped: list[str]) -> Contract:
    return Contract(
        dropped=[*spec.dropped, *(derivation.dropped if derivation else []), *extra_dropped],
        assumptions=[*spec.assumptions, *(derivation.assumptions if derivation else [])],
        masses={f.name: f"{f.mass_gev:g} GeV: {f.mass_justification or 'not justified'}"
                for f in spec.fields if f.mass_gev is not None},
        couplings={c.name: f"{c.value if c.value is not None else 'unset'}: {c.justification or 'not justified'}"
                   for c in spec.couplings})


def _model_and_derivation(request: LagrangianRequest, primary: StructuredLLM | None,
                          result: LagrangianResult) -> bool:
    """Steps 1–4: fill the result; False if the run stops."""
    if request.spec is None and not (request.use_language_models and primary):
        raise ValueError("give a typed model (spec), or allow the language models and pass a client")
    spec = request.spec or IntakeAgent(primary, request.deriver).run(request.description)
    result.spec, result.checks = spec, model_checks.check(spec)
    if not result.checks.passed:
        result.status = "stopped for a person: the model fails the deterministic checks"
        return False
    if request.derivation is None and not (request.use_language_models and primary):
        raise ValueError("give the Wilson coefficients (derivation), or allow the language models")
    result.derivation = request.derivation or DerivationAgent(primary, request.deriver).run(spec)
    try:
        result.dimension_problems = dv.dimension_problems(result.derivation, spec)
    except ValueError as exc:                   # a formula that does not evaluate
        result.dimension_problems = [str(exc)]
    if result.dimension_problems:
        result.status = "stopped for a person: the derivation fails the dimension check"
        return False
    return True


def _stop(result: LagrangianResult, why: str) -> LagrangianResult:
    result.status = f"stopped for a person: {why}"
    result.contract = _contract(result.spec, result.derivation, [])
    if result.spec is not None:
        result.viability = viability.assess(result.spec, result.checks)
    return result


def _numerical(spec: ModelSpec, derivation: dv.Derivation) -> AlphaComparison:
    """Verification rank two: MadDM's coefficients from ADROIT's UFO file of the model."""
    if not maddm.available():
        return AlphaComparison(covered=False, reason="MadGraph and MadDM are not installed in the tools folder")
    try:
        found = maddm.coefficients(spec, maddm.workdir(spec.name))
    except ValueError as exc:
        return AlphaComparison(covered=False, reason=f"not written as UFO: {exc}")
    except RuntimeError as exc:
        return AlphaComparison(covered=False, reason=f"MadDM failed: {str(exc).splitlines()[0]}")
    return maddm.check(spec, derivation, found)


@timed
def run(request: LagrangianRequest, primary: StructuredLLM | None = None,
        checker: StructuredLLM | None = None) -> LagrangianResult:
    """The whole of Path 1 for a bespoke model."""
    result = LagrangianResult(request=request)
    if not _model_and_derivation(request, primary, result):
        result.contract = _contract(result.spec, result.derivation, [])
        result.viability = viability.assess(result.spec, result.checks)
        return result
    spec, derivation = result.spec, result.derivation
    if request.use_language_models and request.second_derivation and checker is not None:
        result.second = DerivationAgent(checker, request.checker).run(spec)
        try:
            result.comparison = dv.compare(derivation, result.second, spec, nucleon=True)
        except ValueError as exc:
            return _stop(result, f"the second derivation does not evaluate ({exc})")
        if not result.comparison.agree:
            return _stop(result, "the two derivations disagree")
    if request.numerical_check:
        result.numerical = _numerical(spec, derivation)
        if not result.numerical.agree:
            return _stop(result, "the derivation disagrees with MadDM's coefficients from the full model")
    dm = spec.dark_matter
    masses = request.masses_gev or [dm.mass_gev]
    try:
        reduced = [quark_level.to_interaction(dv.evaluate(derivation, spec, {f"m_{dm.name}": m}), m)
                   for m in masses]
    except ValueError as exc:                   # e.g. a coefficient DirectDM does not know
        return _stop(result, f"DirectDM refused the derivation ({exc})")
    result.interactions = {str(int(m)) if float(m).is_integer() else repr(float(m)): interaction for m, (_, interaction) in zip(masses, reduced)}
    particle, interaction = reduced[0]
    fits = matching.match(particle, interaction)
    result.matches = fits[:max(3, sum(f.verdict == "same" for f in fits))]   # every exact card, at least three
    if request.run_exclusion:
        result.exclusion = exclusion.run(exclusion.ExclusionRequest(
            bespoke=result.interactions, masses_gev=masses, modules=request.modules,
            spin=particle.spin, name=spec.name))
    result.contract = _contract(spec, derivation, [d for d in interaction.dropped if d not in derivation.dropped])
    done = {"direct_detection", "neutrino_fluxes"} if result.exclusion else set()
    from adroit.orchestrator import checklist
    result.viability = checklist.apply(viability.assess(spec, result.checks, done), checklist.lagrangian_evidence(result))
    return result




@dated_report
def report(result: LagrangianResult) -> str:
    """The report in Markdown: the model, its checks, the derivation, the verification, the limits, the contract."""
    spec = result.spec
    lines = [f"# Path 1 for a bespoke model: {spec.name if spec else '(no model)'}", "",
             f"Status: **{result.status}**.", ""]
    if result.checks:
        c = result.checks
        lines += ["## Deterministic checks", "",
                  *(f"- gauge: {p}" for p in c.gauge), *(f"- hermiticity: {p}" for p in c.hermiticity),
                  *(f"- {kind} (flag): {p}" for kind, flags in (
                      ("coefficient", c.coefficients), ("anomaly", c.anomalies), ("stability", c.stability),
                      ("perturbativity", c.perturbativity),
                      ("contact interaction", c.contact), ("unitarity", c.unitarity)) for p in flags),
                  *(f"- note: {p}" for p in c.notes)]
        if c.passed and not c.flags:
            lines.append("- all passed")
        lines.append("")
    if result.derivation:
        d = result.derivation
        lines += [f"## The derivation ({d.derived_by or 'unattributed'}; {d.flavours} flavours, dm_type {d.dm_type.value})", "",
                  "| coefficient | formula |", "|---|---|", *(f"| {t.name} | `{t.expression}` |" for t in d.terms), ""]
        lines += [*(f"- {j}" for j in d.justifications), "",
                  f"Dimension check: {'passed' if not result.dimension_problems else '; '.join(result.dimension_problems)}."]
    if result.comparison:
        c = result.comparison
        lines += ["", f"Second derivation ({result.second.derived_by}), over {c.points} random points:",
                  f"- coefficients: largest relative difference {c.max_relative_difference:.2g}"
                  f"{' with every coefficient reversed' if c.sign < 0 else ''}"
                  + "".join(f"; only in {w}: {', '.join(n)}" for w, n in
                            (("the first", c.only_in_first), ("the second", c.only_in_second)) if n),
                  f"- nucleon level: {c.nucleon_difference:.2g}" if c.nucleon_difference is not None else
                  "- nucleon level: not computed",
                  f"- {'agree' if c.agree else 'DISAGREE'}"]
    if result.numerical:
        n = result.numerical
        lines += ["", "Numerical cross-check (ADROIT's UFO file through MadDM): " + (
            f"largest relative difference {n.max_relative_difference:.2g}{', overall sign reversed' if n.sign < 0 else ''}; "
            f"{'agree' if n.agree else 'DISAGREE'}" if n.covered else f"not covered: {n.reason}") + "."]
    if result.matches:
        lines += ["", "## The library", "", "| card | verdict | residual | remainder (operator: share) |", "|---|---|---|---|",
                  *(f"| {m.card_id} | {m.verdict} | {m.residual:.2g} | {m.remainder or '—'} |" for m in result.matches)]
    if result.exclusion:
        lines += ["", exclusion.report(result.exclusion)]
    if result.viability:
        lines += ["", viability.report(result.viability)]
    c = result.contract
    lines += ["", "## The contract", "", "Dropped:", *(f"- {x}" for x in c.dropped or ["nothing stated"]),
              "", "Assumptions:", *(f"- {x}" for x in c.assumptions or ["none stated"]),
              "", "Masses:", *(f"- {k}: {v}" for k, v in c.masses.items()),
              "", "Couplings:", *(f"- {k}: {v}" for k, v in c.couplings.items())]
    return "\n".join(lines) + "\n"

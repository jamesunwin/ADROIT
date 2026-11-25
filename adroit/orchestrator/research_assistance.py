"""Advisory assistance around immutable inputs and deterministic physics calls."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Literal, TYPE_CHECKING, Any

from pydantic import Field

from adroit.core.durable import write_atomic
from adroit.core.state import StrictModel
from adroit.core.assistance import (
    PROBE_FACTS,
    AssistanceContext,
    CheckedFact,
    SourceRequest,
    PlanStep,
    AssistanceProposal,
    AssistanceReview,
    ReviewClaim,
    VettedClaim,
    AssistanceResult,
)
from adroit.orchestrator.single_idea import SingleIdeaRequest, SingleIdeaResult
from adroit.parameter_space.native_joint import JointResult
from adroit.parameter_space.classify import classify, Unsupported
from adroit.orchestrator.native_coverage import CoverageRequest
from adroit.parameter_space.native_coverage import CoverageResult
from adroit.retrieval.source_evidence import gather
from adroit.core.chronology import dated_report, utc_now

if TYPE_CHECKING:
    from adroit.agents.llm import StructuredLLM
    from adroit.agents.research_assistant import ResearchAssistant


class ReportClaim(StrictModel):
    """A researcher/draft statement to check, never a replacement physics value."""

    kind: Literal[
        "native_z",
        "full_likelihood",
        "uniform_coverage",
        "thermal_certified",
        "all_records_verified",
    ]
    value: float | bool


class AssistanceRequest(StrictModel):
    """An explicit goal, typed inputs, optional saved results and bounded source reads."""

    goal: str
    study: SingleIdeaRequest | None = None
    result: SingleIdeaResult | None = None
    native_result: JointResult | None = None
    coverage: CoverageRequest | None = None
    coverage_result: CoverageResult | None = None
    draft_claims: list[ReportClaim] = Field(default_factory=list)
    sources: list[SourceRequest] = Field(default_factory=list, max_length=4)
    missing_fields: list[str] = Field(default_factory=list)
    # the saved study's result this request was read from (``adroit assist`` on a study's folder): its SHA-256, read
    # once (the version handle; the owner's decision on advisory outputs, 2026-11-03); "" for a request given whole
    source_sha256: str = Field(default="", exclude_if=lambda v: not v)


def input_hash(request: AssistanceRequest) -> str:
    """Stable identity of the original scientific request and supplied evidence."""
    return hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def context(request: AssistanceRequest) -> AssistanceContext:
    """Build only deterministic facts, with untrusted draft claims kept separate."""
    from adroit.constraints.database import records

    native = request.native_result or (request.result.native_joint if request.result else None)
    values = {
        "has_study": request.study is not None,
        "missing_fields": request.missing_fields,
        # This review fact refers to completed significance calibration.
        # M28 can finish physical optimisation without a calibrated p-value.
        "native_complete": bool(native and native.complete and native.calibration and native.calibration.complete),
        "native_domain_fit_resolved": bool(native and native.domain_fit and native.domain_fit.resolved),
        "native_z": native.calibration.z_mc
        if native and native.calibration and native.calibration.complete
        else None,
        "native_fidelity": "B",
        "uniform_nuisance_coverage": False,
        "draft_claims": [x.model_dump() for x in request.draft_claims],
        "unverified_record_count": sum(not r.usable for r in records()),
        "thermal_certified": bool(
            request.result and any(b.converged for b in request.result.thermal)
        ),
        "global_nr_reference_z": request.result.global_z if request.result else None,
        "supported_model": False,
        "null_range": None,
        "ineligible_masses": [],
        "result_matches_input": True,
        "has_result": bool(request.result or request.native_result or request.coverage_result),
        "native_requested": bool(request.study and request.study.native_joint),
        "coverage_requested": request.coverage is not None,
        "coverage_conclusion": request.coverage_result.conclusion
        if request.coverage_result
        else None,
    }
    _augment_input_facts(request, native, values)
    return AssistanceContext(
        input_hash=input_hash(request),
        goal=request.goal,
        original_inputs_json=json.dumps(
            request.model_dump(mode="json", exclude={"result", "native_result", "coverage_result"}),
            sort_keys=True,
        ),
        facts=[
            CheckedFact(id=k, value=json.dumps(v), origin="typed request/result and module policy")
            for k, v in values.items()
        ],
    )


def _augment_input_facts(
    request: AssistanceRequest, native: JointResult | None, values: dict[str, Any]
) -> None:
    from adroit.experiments import registry
    from adroit.experiments.native_validation import certified_range
    from adroit.parameter_space.native_joint import LOW_MASS_NULL, NULL, _supported

    if request.study:
        try:
            cls, _, _ = classify(request.study.spec)
            values["supported_model"] = not request.study.native_joint or (
                _supported(cls)
                and request.study.native_joint.null_experiment in (LOW_MASS_NULL, NULL)
            )
        except Unsupported:
            pass
        null_name = request.study.native_joint.null_experiment if request.study.native_joint else ""
        if null_name:
            try:
                module = registry.load_module(null_name)
                span = (
                    certified_range(null_name)
                    if null_name == LOW_MASS_NULL
                    else module.validated_range("SI")
                )
            except KeyError:
                span = None
            values["null_range"] = span
            values["ineligible_masses"] = [
                m for m in request.study.masses_gev if span is None or not span[0] <= m <= span[1]
            ]
        if request.result:
            values["result_matches_input"] = request.result.request == request.study
        if native and values["supported_model"]:
            _, point, _ = classify(request.study.spec)
            from adroit.core.model_spec import PhysicalFitRange

            values["result_matches_input"] = values["result_matches_input"] and (
                native.reference_point == point
                and native.masses_gev == request.study.masses_gev
                and native.settings == request.study.native_joint
                and native.bounds
                == (
                    None if request.study.native_joint.domain is not None else
                    request.study.spec.physical_fit or PhysicalFitRange.perturbative_branch(point.g_chi)
                )
            )
    if request.coverage and not request.study:
        values["has_study"] = True
        try:
            classify(request.coverage.spec)
            values["supported_model"] = True
        except Unsupported:
            pass


def probes(ctx: AssistanceContext) -> dict[str, bool]:
    """Specific numerical/policy checks; novel semantic concerns stay unconfirmed."""
    f = {x.id: json.loads(x.value) for x in ctx.facts}
    claims = {c["kind"]: c["value"] for c in f["draft_claims"]}
    return {
        "missing_input": not f["has_study"] or bool(f["missing_fields"]),
        "unsupported_model": f["has_study"] and not f["supported_model"],
        "ineligible_null": bool(f["ineligible_masses"]),
        "incomplete_calibration": "native_z" in claims and not f["native_complete"],
        "nr_mislabel": "native_z" in claims
        and f["native_complete"]
        and claims["native_z"] != f["native_z"],
        "fidelity_overclaim": bool(claims.get("full_likelihood")),
        "coverage_overclaim": bool(claims.get("uniform_coverage"))
        and not f["uniform_nuisance_coverage"],
        "thermal_unresolved": bool(claims.get("thermal_certified")) and not f["thermal_certified"],
        "record_unverified": bool(claims.get("all_records_verified"))
        and f["unverified_record_count"] > 0,
        "input_result_mismatch": not f["result_matches_input"],
    }


def baseline(
    ctx: AssistanceContext, sources: list[SourceRequest]
) -> tuple[AssistanceProposal, AssistanceReview]:
    """Free templates establish what optional LLMs must improve on."""
    from adroit.core.assistance import Clarification

    flags = probes(ctx)
    questions = []
    if flags["missing_input"]:
        questions = [
            Clarification(
                field="typed_study",
                question="Supply the typed model, masses and intended calculation; clarify the missing fields.",
            )
        ]
    f = {x.id: json.loads(x.value) for x in ctx.facts}
    action = (
        "clarify_input"
        if questions
        else "source_review"
        if flags["ineligible_null"]
        else "native_joint"
        if f["native_requested"] and not f["has_result"] and not flags["unsupported_model"]
        else "nuisance_check"
        if f["coverage_requested"] and not f["has_result"] and not flags["unsupported_model"]
        else "review_results"
    )
    plan = AssistanceProposal(
        input_hash=ctx.input_hash,
        questions=questions,
        sources=sources,
        steps=[
            PlanStep(
                action=action, input_hash=ctx.input_hash, reason="deterministic prerequisite check"
            )
        ],
    )
    evidence_ids = [x.id for x in ctx.facts]
    review = AssistanceReview(
        input_hash=ctx.input_hash,
        claims=[
            ReviewClaim(
                issue=k,
                fact_ids=evidence_ids,
                explanation=f"The deterministic {k} probe found a mismatch or missing prerequisite.",
            )
            for k, v in flags.items()
            if v
        ],
    )
    return plan, review


def vet(review: AssistanceReview, ctx: AssistanceContext) -> list[VettedClaim]:
    """Confirm only an identity-bound claim whose cited facts support its named probe."""
    facts = {f.id for f in ctx.facts}
    evidence = {e.id for e in ctx.evidence if e.reference_checked and e.content_checked}
    flags = probes(ctx)
    result = []
    for claim in review.claims:
        linked = (
            review.input_hash == ctx.input_hash
            and set(claim.fact_ids) <= facts
            and set(claim.evidence_ids) <= evidence
            and PROBE_FACTS.get(claim.issue, {"no_probe"}) <= set(claim.fact_ids)
        )
        confirmed = linked and flags.get(claim.issue, False)
        result.append(
            VettedClaim(
                claim=claim,
                confirmed=confirmed,
                probe=claim.issue,
                reason="deterministic probe confirms the concern"
                if confirmed
                else "not confirmed: stale identity, unmatched evidence, absent probe or failed predicate",
            )
        )
    return result


def _execute(request: AssistanceRequest, result: AssistanceResult, folder: Path) -> None:
    """Route a permitted step using exclusively the original typed physics arguments."""
    if probes(result.context)["missing_input"]:
        result.errors.append("calculation needs explicit typed inputs")
        return
    for step in result.proposal.steps:
        if step.action == "nuisance_check" and request.coverage:
            from adroit.orchestrator.native_coverage import run as coverage_run

            output = coverage_run(request.coverage, folder / "coverage")
            _refresh_context(request.model_copy(update={"coverage_result": output}), result)
            _artifact(folder / "coverage/result.json", folder, result,     # the bytes it wrote (CZ-02)
                      output.model_dump_json(indent=2).encode())
            result.executed.append(step.action)
            break
        if step.action == "single_idea" and request.study:
            _execute_single(request, result, folder)
            result.executed.append(step.action)
            break
        if step.action != "native_joint" or request.study is None:
            continue
        study = request.study
        if study.native_joint is None:
            result.errors.append("native settings must be supplied by the researcher")
            continue
        _execute_native(request, result, folder)
        result.executed.append("native_joint")
        break


def _execute_single(request: AssistanceRequest, result: AssistanceResult, folder: Path) -> None:
    """Run the researcher's single-idea study and keep its result, report and evidence."""
    from adroit.orchestrator.single_idea import prepared, run as single_run, report as single_report
    from adroit.core.chronology import analysis_report, model_references
    from adroit.evidence.runtime import capture_request
    from adroit.evidence.build import publish

    study = prepared(request.study)              # its defaults resolved before its capture (DG-04)
    evidence_context = capture_request(study)
    output = single_run(study, folder / "single_idea")
    _refresh_context(
        request.model_copy(update={"result": output, "native_result": None}), result
    )
    path = folder / "single_idea/result.json"
    # the result, its evidence and its report (dated by that evidence, bound to the result) of one serialization,
    # and the artifact's digest of those bytes (the auditor's CY recheck, CZ-02, 2026-11-01)
    content = output.model_dump_json(indent=2).encode()
    publish(path, content, output, lambda envelope: (
        analysis_report(single_report(output), context=envelope.context, references=model_references(output))
        if envelope.context.calculation_started_at else single_report(output)),
        workflow="single_idea", context=evidence_context)
    _artifact(path, folder, result, content)


def _execute_native(request: AssistanceRequest, result: AssistanceResult, folder: Path) -> None:
    """Run the researcher's native joint study with its explicit null and keep its result and evidence."""
    from adroit.parameter_space.native_joint import run as native_run
    from adroit.core.model_spec import PhysicalFitRange

    study = request.study
    if study.native_joint.null_experiment not in study.null_modules:
        raise ValueError("native null must be explicitly included in the researcher request")
    cls, point, _ = classify(study.spec)
    from adroit.evidence.runtime import capture_request
    from adroit.evidence.build import kept, save
    evidence_context = capture_request(study)
    native = native_run(
        cls,
        point,
        study.masses_gev,
        study.spec.physical_fit or PhysicalFitRange.perturbative_branch(point.g_chi),
        study.native_joint,
        study.physical_fit_settings,
        study.spec.dark_matter.spin,
        signal_experiment=study.experiment,
    )
    updated = request.model_copy(update={"native_result": native})
    path = folder / "native_result.json"
    content = native.model_dump_json(indent=2).encode()    # its evidence and digest of these bytes (CZ-02)
    from adroit.core.durable import publishing
    with publishing(folder) as held:            # its result and evidence under one lock (the auditor's DD recheck, DE-02)
        write_atomic(path, content)
        save(path, "native_joint", evidence_context, study.model_dump(mode="json"), content=content, claim=held)
        kept(path, content)
    _artifact(path, folder, result, content)
    _refresh_context(updated, result)


def _artifact(path: Path, folder: Path, result: AssistanceResult, content: bytes) -> None:
    result.calculation_artifacts[str(path.relative_to(folder))] = hashlib.sha256(content).hexdigest()


def _refresh_context(updated: AssistanceRequest, result: AssistanceResult) -> None:
    new = context(updated)
    new.input_hash = result.input_hash
    new.original_inputs_json = result.context.original_inputs_json
    new.evidence = result.context.evidence
    result.context = new


def run(
    request: AssistanceRequest,
    folder: Path,
    *,
    llm: StructuredLLM | None = None,
    model: str = "",
    fetch_sources: bool = False,
    execute_plan: bool = False,
    source_gather=gather,
) -> AssistanceResult:
    """Two optional advisory calls around bounded retrieval and deterministic execution."""
    start = time.perf_counter()
    started = utc_now()
    start_spend = float(getattr(llm, "spent", 0.0))
    original = input_hash(request)
    ctx = context(request)
    proposal, review = baseline(ctx, request.sources)
    result = AssistanceResult(
        input_hash=original,
        context=ctx,
        proposal=proposal,
        review=review,
        baseline_issues=[k for k, v in probes(ctx).items() if v],
        mode="llm-assisted" if llm else "deterministic",
        model=model,
        source_sha256=request.source_sha256,
    )
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "request.json").write_text(request.model_dump_json(indent=2))
    assistant = _plan(llm, model, ctx, original, result) if llm else None
    result.dropped_steps = [s.action for s in result.proposal.steps if s.input_hash != original]
    result.proposal.steps = [s for s in result.proposal.steps if s.input_hash == original]
    if fetch_sources:
        _read_sources(request, result, folder, source_gather)
    if execute_plan:
        try:
            _execute(request, result, folder)
        except (ValueError, RuntimeError, ArithmeticError) as error:
            result.errors.append(f"deterministic execution pending: {error}")
            result.status = "degraded"
    if assistant:
        _review(assistant, original, result)
    result.vetted = vet(result.review, result.context)
    result.physics_input_preserved = original == input_hash(request)
    result.automated_seconds = time.perf_counter() - start
    result.api_cost_usd = float(getattr(llm, "spent", 0.0)) - start_spend
    account = getattr(llm, "account", None)
    result.committed_cost_usd = (
        (sum(account.spent.values()) + sum(v for _, v in account.reservations.values()))
        if account
        else result.api_cost_usd
    )
    result.calculation_started_at, result.calculation_completed_at = started, utc_now()
    from adroit.evidence.build import publish        # the report bound to the result (the auditor's CY recheck, CZ-02)
    publish(folder / "result.json", result.model_dump_json(indent=2).encode(), result, lambda envelope: report(result),
            evidence=False)
    return result


def _plan(
    llm: StructuredLLM, model: str, ctx: AssistanceContext, original: str, result: AssistanceResult
) -> ResearchAssistant:
    """The advisory assistant, whose plan replaces the baseline only at the original input identity."""
    from adroit.agents.research_assistant import ResearchAssistant

    assistant = ResearchAssistant(llm, model)
    try:
        candidate = assistant.plan(ctx)
        if candidate.input_hash != original:
            raise ValueError("stale assistance identity")
        result.proposal = candidate
    except Exception as error:  # noqa: BLE001 - advisory failure preserves baseline, never changes physics
        result.errors.append(f"planning unavailable: {type(error).__name__}")
        result.status = "degraded"
    return assistant


def _read_sources(
    request: AssistanceRequest, result: AssistanceResult, folder: Path, source_gather
) -> None:
    """Read at most four distinct requested or proposed papers into the context's evidence."""
    sources = {}
    for s in [*request.sources, *result.proposal.sources]:
        sources.setdefault(s.arxiv_id, s)
    chosen = list(sources.values())[:4]
    result.source_attempts = len(chosen)
    result.context.evidence = source_gather(chosen, folder / "sources")


def _review(assistant: ResearchAssistant, original: str, result: AssistanceResult) -> None:
    """The advisory review, kept only at the original input identity."""
    try:
        candidate = assistant.review(result.context)
        if candidate.input_hash != original:
            raise ValueError("stale reviewer input identity")
        result.review = candidate
        result.review_origin = "llm"
    except Exception as error:  # noqa: BLE001
        result.errors.append(f"review unavailable: {type(error).__name__}")
        result.status = "degraded"




@dated_report
def report(result: AssistanceResult) -> str:
    """Separate confirmed probes, literal source matches and unconfirmed agent opinions."""
    from adroit.retrieval.references import Reference, clean

    refs = [
        Reference(kind="arxiv", id=e.reference, title=e.title, verified=e.reference_checked)
        for e in result.context.evidence
    ]
    lines = [
        "# Research assistance",
        "",
        f"Mode: {result.mode}; status: {result.status}; model: {result.model or 'none'}.",
        f"Input preserved: {result.physics_input_preserved}; paid spend ${result.api_cost_usd:.6f}; committed ${result.committed_cost_usd:.6f}.",
        f"Automated latency: {result.automated_seconds:.3f} s. Researcher time saved: not yet measured.",
        "",
    ]
    lines += [
        f"- Clarification ({q.field}): {clean(q.question, refs)}" for q in result.proposal.questions
    ]
    lines += [f"- Plan {s.action}: {clean(s.reason, refs)}" for s in result.proposal.steps]
    lines += [
        f"- {'Probe-confirmed' if c.confirmed else 'Unconfirmed'} {c.claim.issue}: {clean(c.claim.explanation, refs)}; {c.reason}"
        for c in result.vetted
    ]
    for e in result.context.evidence:
        lines.append(
            f"- Source [{e.reference}]({e.url}), page {e.page}; exists={e.exists}, identified by {e.identity or 'nothing'}, reference={e.reference_checked}, content={e.content_checked}, claim={e.claim_verified}; SHA256 {e.document_sha256}. {e.note}"
        )
    lines += [
        "",
        *result.errors,
        "",
        "Agent suggestions never write records, replace physics values or confer human source verification.",
    ]
    from adroit.evidence.version import as_found
    read = (f"It is an advisory reading of a saved study's result as found (SHA-256 {result.source_sha256}, read once)."
            if result.source_sha256 else "It is an advisory reading of the request given, as found.")
    return "\n".join(lines) + "\n" + as_found(read)

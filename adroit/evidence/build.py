"""Common evidence sidecars for all supported saved workflows."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Callable, NamedTuple

from pydantic import BaseModel, JsonValue

from adroit.core.checkpoint import atomic_json
from adroit.core.evidence import EvidenceContext, EvidenceEnvelope, EvidenceObservation, content_hash
from adroit.evidence.observations import point_observations, constraint_observation
from adroit.evidence.results import copies_match, inputs_read, records_read, summary, summary_matches, typed
from adroit.evidence.runtime import finish


def sidecar_path(result_path: Path) -> Path:
    """Use a separate sidecar for each result, including multiple promotions."""
    return result_path.with_name(f"{result_path.stem}.evidence.json")


def build(workflow: str, result: BaseModel, result_sha256: str,
          context: EvidenceContext | None = None,
          original_inputs: dict[str, JsonValue] | None = None,
          certificates: dict[str, JsonValue] | None = None) -> EvidenceEnvelope:
    """Adapt a typed saved result; never run a physics or statistical calculation. ``certificates``: more the result's
    writer certifies of it (a reanalysis's lineage), in its evidence as first published."""
    ctx = context or EvidenceContext(notes=["legacy result: calculation-time provenance not recorded"])
    payload = result.model_dump(mode="json")
    inputs = original_inputs if original_inputs is not None else payload.get("request", {})
    if workflow == "native_joint" and original_inputs is None:
        inputs = {key: payload[key] for key in ("model_class", "spin", "reference_point", "masses_gev",
            "bounds", "settings", "fit_settings", "signal_experiment", "null_experiment")}
    if ctx.request_sha256 and ctx.request_sha256 != content_hash(inputs):
        ctx = ctx.model_copy(update={"origin": "changed_during_run", "notes": [*ctx.notes,
            "typed request changed since calculation start; input provenance cannot certify reuse"]})
    engine, observations, adapted = _adapt(workflow, result, ctx)
    certificates = {**adapted, **(certificates or {})}
    warnings = [] if ctx.origin == "captured" else [f"calculation identity: {ctx.origin}"]
    envelope = EvidenceEnvelope(workflow=workflow, result_sha256=result_sha256,
        input_sha256=content_hash(inputs), original_inputs=inputs, engine_mapping=engine,
        summary=summary(workflow, result), context=ctx, observations=observations,
        certificates=certificates, warnings=warnings)
    from adroit.constraints.review_queue import SelectedEvidence,build_queue
    envelope.certificates["review_queue"] = build_queue([
        SelectedEvidence(envelope=envelope,result=payload)]).model_dump(mode="json")
    return envelope


def _track1(result: BaseModel, context: EvidenceContext) -> tuple[
    dict[str, JsonValue], list[EvidenceObservation], dict[str, JsonValue]
]:
    engine = result.scan.request.model_class.model_dump(mode="json") if result.scan else {}
    observations = [o for row in result.scan.points for o in point_observations(row, engine, context)] if result.scan else []
    missing = 0
    for view in (result.verdict, result.likelihood_verdict):
        for crossing in view.crossings if view else []:
            if crossing.evaluation is not None:
                observations.extend(point_observations(crossing.evaluation, engine, context))
            else:
                missing += 1
    certificates = {"audit": result.audit.model_dump(mode="json"), "missing_contour_comparisons": missing,
                    "coverage": result.coverage.model_dump(mode="json") if result.coverage else None,
                    "cuts": result.verdict.model_dump(mode="json") if result.verdict else None,
                    "likelihood": result.likelihood_verdict.model_dump(mode="json") if result.likelihood_verdict else None}
    if result.scan:
        certificates["scalar_high_energy_unitarity"] = [row.unitarity_certificate.model_dump(mode="json")
            for row in result.scan.points if row.unitarity_certificate is not None]
        certificates["scalar_one_loop_running"] = [row.running_certificate.model_dump(mode="json")
            for row in result.scan.points if row.running_certificate is not None]
        certificates["coannihilation_chemical_equilibrium"] = [row.chemical_certificate.model_dump(mode="json")
            for row in result.scan.points if row.chemical_certificate is not None]
        certificates["scalar_tree_vacua"] = [row.vacuum_certificate.model_dump(mode="json")
            for row in result.scan.points if row.vacuum_certificate is not None]
    if result.unsupported:
        physical = result.request.spec.model_dump(mode="json")
        observations.append(EvidenceObservation(subject_id=content_hash(physical), physical_input=physical,
            observable="model_mapping", calculation="not_calculated", applicability="unsupported",
            review="not_required", reasons=[result.unsupported], construction="saved typed-model refusal"))
    return engine, observations, certificates


def _adapt(workflow: str, result: BaseModel, context: EvidenceContext) -> tuple[
    dict[str, JsonValue], list[EvidenceObservation], dict[str, JsonValue]
]:
    if workflow == "track1":
        return _track1(result, context)
    if workflow in ("idea", "lagrangian"):
        return _model_building(workflow, result.model_dump(mode="json"))
    if workflow == "single_idea":
        return _single_idea(result, context)
    if workflow == "signal":
        return _signal(result, context)
    payload = result.model_dump(mode="json")
    if workflow == "native_joint":
        return {"model_class": payload["model_class"], "spin": payload["spin"],
                "reference_point": payload["reference_point"], "bounds": payload["bounds"],
                **({"physical_domain":payload["settings"]["domain"]} if result.domain_fit is not None else {})}, [], {
            "fits": payload["fits"], "calibration": payload["calibration"], "omitted": payload["omitted"],
            **({"multiparameter_fit":payload["domain_fit"]} if result.domain_fit is not None else {})}
    return {}, [], {workflow: payload}


def _single_idea(result: BaseModel, context: EvidenceContext) -> tuple[
    dict[str, JsonValue], list[EvidenceObservation], dict[str, JsonValue]
]:
    """A single-idea study: its Track 1 scan and band/thermal points, with their certificates and fits."""
    engine, observations, certificates = _track1(result.track1, context) if result.track1 else ({}, [], {})
    if not engine and context.origin == "captured":
        from adroit.parameter_space.classify import classify, Unsupported
        try:
            cls, _, _ = classify(result.request.spec)
            engine = cls.model_dump(mode="json")
        except Unsupported:
            pass
    for band in [*result.band, *result.thermal]:
        if band.evaluation:
            observations.extend(point_observations(band.evaluation, engine, context))
    certificates["band_scalar_high_energy_unitarity"] = [b.evaluation.unitarity_certificate.model_dump(mode="json")
        for b in [*result.band,*result.thermal] if b.evaluation and b.evaluation.unitarity_certificate]
    certificates["band_scalar_one_loop_running"] = [b.evaluation.running_certificate.model_dump(mode="json")
        for b in [*result.band,*result.thermal] if b.evaluation and b.evaluation.running_certificate]
    certificates["band_coannihilation_chemical_equilibrium"] = [b.evaluation.chemical_certificate.model_dump(mode="json")
        for b in [*result.band,*result.thermal] if b.evaluation and b.evaluation.chemical_certificate]
    certificates["band_scalar_tree_vacua"] = [b.evaluation.vacuum_certificate.model_dump(mode="json")
        for b in [*result.band,*result.thermal] if b.evaluation and b.evaluation.vacuum_certificate]
    certificates.update(physical_fits=[b.physical_fit.model_dump(mode="json") for b in result.band if b.physical_fit],
                        nr_reference_inputs=[b.reference_interaction.model_dump(mode="json") if b.reference_interaction else None
                                             for b in result.band],
                        thermal=[b.model_dump(mode="json") for b in result.thermal],
                        native_joint=result.native_joint.model_dump(mode="json") if result.native_joint else None)
    return engine, observations, certificates


def _signal(result: BaseModel, context: EvidenceContext) -> tuple[
    dict[str, JsonValue], list[EvidenceObservation], dict[str, JsonValue]
]:
    """A signal study: its null verdicts, eligible candidates and reference fits, with the likelihood contract."""
    observations = [constraint_observation(v.model_dump(mode="json"), label, context)
                    for label, verdicts in result.verdicts.items() for v in verdicts]
    source = f"experiment:{result.request.experiment}"
    for label,row in result.eligibility.items():
        if row.evaluation is not None:
            points=point_observations(row.evaluation,row.model_class,context)
            # a reused point's claims name the version reused (the auditor's CX recheck, CY-01, 2026-11-01)
            reused={k:v for k,v in (('reused_result',row.reused_result),('reused_result_sha256',row.reused_result_sha256),
                                    ('reused_evidence_sha256',row.reused_evidence_sha256)) if v}
            observations+=[o.model_copy(update={'details':{**o.details,'candidate_label':label,'eligibility_scope':row.scope,
                                                           **reused}}) for o in points]
    for fit in result.fits:
        review = next((s.review for s in context.sources if s.id == source), "legacy_unknown")
        observations.append(EvidenceObservation(subject_id=fit.label, physical_input={},
            observable="fitted_signal_events", value=fit.s_hat, units="events", calculation="computed",
            applicability="applicable", source_ids=[source], review=review,
            construction="unconstrained NR signal-amplitude reference fit; local significance",
            uncertainties={"interval_68": list(fit.interval_68), "interval_90": list(fit.interval_90),
                           "kind": "nominal profile-likelihood; not calibrated physical coverage"},
            details=fit.model_dump(mode="json")))
    return {"user_models": [m.model_dump(mode="json") for m in result.request.user_models],
            "original_candidates": [c.model_dump(mode="json") for c in result.request.candidates],
            "engine_candidates": [c.model_dump(mode="json") for c in result.engine_candidates]}, observations, {
                "fits": [f.model_dump(mode="json") for f in result.fits],
                "null_comparisons": [c.model_dump(mode="json") for c in result.combinations],
                **({'physical_eligibility':{k:v.model_dump(mode='json') for k,v in result.eligibility.items()},
                    'eligibility_score_scope':'unchanged unconstrained NR reference; exact fitted point only, not domain exclusion/significance recalibration'}
                   if result.eligible_tournament is not None else {}),
                "likelihood_contract": {"signal": result.request.experiment,
                    "nulls_requested": result.request.null_modules,
                    "construction": "null limit-equivalent likelihoods; not a full joint workspace",
                    "overlap_policy": "same-dataset native/reconstructed results are separate views, not multiplied"}}


def _model_building(workflow: str, payload: dict[str, JsonValue]) -> tuple[
    dict[str, JsonValue], list[EvidenceObservation], dict[str, JsonValue]
]:
    """Track 1's front end (``idea``) and a bespoke Lagrangian (``lagrangian``): no point is calculated, so there is no
    observation. The engine mapping is what was built (each model and where it came from) or what the Lagrangian was
    matched to (its nucleon-level interactions and the library's nearest cards); the certificates are the audits and
    checks the conclusion rests on."""
    if workflow == "idea":
        return {"models": [{"name": m["spec"]["name"], "source": m["source"]} for m in payload["models"]]}, [], {
            "audits": [m["audit"] for m in payload["models"]], "dropped": payload["dropped"]}
    return {"interactions": payload["interactions"], "card_matches": payload["matches"]}, [], {
        key: payload[key] for key in ("checks", "derivation", "second", "comparison", "numerical", "contract",
                                      "exclusion")}


def save(result_path: Path, workflow: str = "", context: EvidenceContext | None = None,
         original_inputs: dict[str, JsonValue] | None = None, content: bytes | None = None,
         certificates: dict[str, JsonValue] | None = None, claim=None) -> EvidenceEnvelope:
    """Bind a sidecar to a saved result and its calculation-time source context: the result typed and hashed from
    ``content``, the bytes its writer wrote (``publish``), else from one read of the file (``result_bytes``). The
    report beside it is its writer's to date and bind: it is no longer read again and rewritten here (the auditor's CY
    recheck, CZ-02, 2026-11-01: a report published meanwhile would have been dated with this run's context). Written
    under the folder's publication lock (``durable.publishing``; ``claim``, its writer's own: DE-02)."""
    from adroit.core.durable import publishing
    content = result_bytes(result_path) if content is None else content
    kind, result = typed(_object(result_path, content), workflow)
    ctx = (finish(context, read=records_read(kind, result), consumed=inputs_read(kind, result))
           if context is not None else None)
    envelope = build(kind, result, hashlib.sha256(content).hexdigest(), ctx, original_inputs, certificates)
    with publishing(Path(result_path).parent, claim):
        atomic_json(sidecar_path(result_path), envelope.model_dump(mode="json"))
    return envelope


def sidecar_identity(envelope: EvidenceEnvelope) -> str:
    """The identity of a sidecar as ``save`` writes ``envelope`` (``checkpoint.atomic_json``'s bytes): the evidence's
    identity in a version (``evidence.version``)."""
    import json
    return hashlib.sha256(json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False,
                                     allow_nan=True).encode()).hexdigest()


def publish(result_path: Path, content: bytes, result: BaseModel,
            report: Callable[[EvidenceEnvelope | None], str], *, workflow: str = "",
            context: EvidenceContext | None = None, original_inputs: dict[str, JsonValue] | None = None,
            evidence: bool = True, certificates: dict[str, JsonValue] | None = None,
            written: dict[str, str] | None = None, claim=None, marked: bool = False
            ) -> tuple[EvidenceEnvelope | None, str]:
    """A result written whole with its evidence and its report, all of one serialization, ``content`` (the auditor's CY
    recheck, CZ-02, 2026-11-01: two writers had bound the report of the result they held, A, to the digest of the file
    read again, B, published meanwhile, and the page and a verified bundle had shown A's report as B's).

    The bytes are written; their evidence (with ``evidence``) is built from them, never from the file read again
    (``save``); the report (``report``, given that evidence or None) is bound to their digest and to the figures as
    its writer drew them under its hold of the folder (``bindings.drawn``; the auditor's DE recheck, DF-01). Then ``Replaced`` where the file no longer holds them: another process
    published there meanwhile, so the folder's files are not of one version, and every reader refuses the mismatch
    (evidence of another version; a report bound to another, withheld). Returns the evidence (None without) and the
    report as written, without its binding.

    ``marked``: its writer has marked its publication incomplete already (``incomplete``: ``runs._write``,
    ``promote``'s children and proposals, ``native_fit``, whose record is their last part), so it marks nothing itself
    (IC-01, HE-02).

    ``certificates``: more its writer certifies of the result, in its evidence from the first (``build``). ``written``:
    given, it receives the identity of each part as written (``result``, ``evidence``, ``presentation``: those of a
    version, ``evidence.version``), so that what follows the publication can require that version, never the folder
    read again (the auditor's version-handle audit, DD-01, 2026-11-04).

    Its parts are written under the folder's publication lock (``durable.publishing``; ``claim``, its writer's own, held
    already), which every writer of a study's parts takes, so that no other publication's part is written between them;
    and before each part, the parts written already are checked to be still its own, so that a change by a process
    outside ADROIT's writers stops it there: ``Replaced``, naming what it wrote, nothing written after (the auditor's DD
    recheck, DE-02, 2026-11-05: its later parts had been written over another publication completed meanwhile)."""
    from adroit.core.durable import publishing, write_atomic
    from adroit.evidence.bindings import bind, figures_of, report_path
    with publishing(Path(result_path).parent, claim) as held, nullcontext() if marked else \
            incomplete(result_path, hashlib.sha256(content).hexdigest()):      # IC-01, its own mark (HE-01)
        write_atomic(result_path, content)
        kept_parts(result_path, content, ("result",))
        envelope = save(result_path, workflow, context, original_inputs, content=content,
                        certificates=certificates, claim=held) if evidence else None
        evidence_sha = sidecar_identity(envelope) if envelope is not None else ""
        kept_parts(result_path, content, ("result", "evidence") if evidence else ("result",), evidence_sha)
        text = report(envelope)
        digest = hashlib.sha256(content).hexdigest()
        bound = bind(text, digest, result_path.parent, figures_of(text, result), held)   # as its writer drew (DF-01)
        write_atomic(report_path(result_path), bound)
        kept(result_path, content)
        kept_parts(result_path, content, ("result", "evidence", "report") if evidence else ("result", "report"),
                    evidence_sha, hashlib.sha256(bound.encode()).hexdigest())
    if written is not None:
        written.update(result=digest, evidence=evidence_sha, presentation=hashlib.sha256(bound.encode()).hexdigest())
    return envelope, text


MARK = "PUBLICATION_INCOMPLETE.txt"     # beside a study's parts while a publication replaces them (``incomplete``)


def mark_path(result_path: Path) -> Path:
    """The mark of the publication of ``result_path``, one for each output of a folder (the auditor's merge-round audit,
    HE-01, 2026-11-12): ``MARK`` for a study's result (``result.json``, whose parts are its evidence, its report and its
    study record), ``<name>.PUBLICATION_INCOMPLETE.txt`` for any other (a promotion's record, ``promotion_<…>.json``,
    beside its parent's study). One output's publication never marks or unmarks another's: a promotion published into
    its parent's folder had removed the mark of the parent's own interrupted publication."""
    result_path = Path(result_path)
    return result_path.parent / (MARK if result_path.name == "result.json" else f"{result_path.stem}.{MARK}")


@contextmanager
def incomplete(result_path: Path, digest: str = ""):
    """A publication's parts written as one (the auditor's portability audit, IC-01, 2026-11-10): its mark (``mark_path``)
    written before its first part and removed once its last is written, so that a publication stopped between them (a
    failed write, a stopped process) leaves its output marked, and every reader (``evidence.version``) reads its report
    and its study record as interrupted, never as its result's. Its writer holds the folder's publication lock. A
    writer whose last part comes after ``publish`` (its study record, its offers) holds the mark itself
    (``publish(marked=True)``: ``runs._write``; ``promote``'s children and proposals and ``native_fit``, HE-02).

    The mark is removed only where the publication wrote every part (the auditor's merge-round audit, HE-01, 2026-11-12). A
    publication stopped because a part it wrote was replaced from outside ADROIT's writers (``Replaced``, DE-02) keeps
    it, as any other stop does: the parts there are not one publication. Before, it had been removed then, and with the
    same result bytes the earlier report and study record (their dates, title and cost) had read as bound to the new
    evidence. The mark goes once a later publication of the same output writes every part.

    The IC audit had found a replacement with the same result bytes stopped after its evidence: the earlier report and
    study record read as bound to the new evidence, the page and ``adroit studies`` counting the earlier cost, and a
    bundle verifying as internally consistent."""
    mark = mark_path(result_path)
    from adroit.core.durable import write_atomic
    write_atomic(mark, (
        "A publication into this folder was interrupted while it was writing its parts" +
        (f" (its result's SHA-256 {digest})" if digest else "") + ", so its result, its evidence, its report and its "
        "study record may be from two publications. ADROIT reads its report and its study record as incomplete: "
        "neither is shown, exported or counted as the result's. Run the study again to publish it whole; ADROIT "
        "removes this file once a publication has written every part.\n"))
    yield
    mark.unlink(missing_ok=True)          # its last part written: reached only when nothing failed or was replaced


class Replaced(ValueError):
    """A result's file no longer holds the bytes its writer wrote: another process published there meanwhile.
    ``wrote``: the parts its writer had written when it found that (DE-02)."""

    def __init__(self, message: str, wrote: tuple[str, ...] = ()):
        super().__init__(message)
        self.wrote = tuple(wrote)


def kept_parts(result_path: Path, content: bytes, wrote: tuple[str, ...], evidence_sha256: str = "",
                report_sha256: str = "", said: tuple[str, ...] = ()) -> None:
    """``Replaced`` where a part its writer has written (``wrote``) no longer holds what it wrote: the result's
    bytes, its sidecar's identity, its report's digest (DE-02). Said with what was written (``said``, where its writer
    wrote more than those parts: its record, a file beside them) and that nothing more is."""
    from adroit.evidence.bindings import report_path

    def now(path: Path) -> str | None:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None
    found = {"result": now(result_path) == hashlib.sha256(content).hexdigest(),
             "evidence": now(sidecar_path(result_path)) == evidence_sha256,
             "report": now(report_path(result_path)) == report_sha256}
    changed = [part for part in wrote if not found[part]]
    if changed:
        raise Replaced(f"{result_path.parent}: its {' and '.join(changed)}, written by this run, then replaced by "
                       f"another process outside ADROIT's writers. This run had written its {', '.join(said or wrote)}, "
                       "and wrote nothing more: the folder holds what the other process wrote, beside any part of this "
                       "run's it did not replace; its readers refuse what does not agree. Run it again into a new "
                       "folder", said or wrote)


def kept(result_path: Path, content: bytes) -> None:
    """``Replaced`` where the result's file, read now as one version, does not hold ``content``: the bytes its writer
    wrote, with the evidence and the report of those bytes."""
    try:
        now = result_bytes(result_path)
    except OSError:
        now = None
    if now != content:
        raise Replaced(f"{result_path} was replaced by another process while its evidence and report were written: "
                       "they describe the result this run computed, not the file now there, so the folder's files are "
                       "not one version; its readers refuse the mismatch. Run it again into a new folder")


def read(result_path: Path) -> EvidenceEnvelope:
    """Read bound evidence, or adapt a legacy result without upgrading its provenance (``read_saved``'s envelope)."""
    return read_saved(result_path).envelope


class Saved(NamedTuple):
    """A saved result and its evidence as one snapshot (``read_saved``): the result's bytes as read (``content``), their
    JSON object (``data``), that object typed as its evidence's workflow (``workflow``, ``result``), the evidence checked
    against exactly those bytes (``envelope``: the sidecar's, or rebuilt from them where there is none), and the digest
    of the sidecar's bytes as read ("" without one)."""
    content: bytes
    data: dict
    workflow: str
    result: BaseModel
    envelope: EvidenceEnvelope
    sidecar_sha256: str


def read_saved(result_path: Path) -> Saved:
    """A saved result and its evidence read once each, the evidence checked against the result's bytes as read: what a
    consumer shows or exports of a point, a table, a bundle or a continuation is of this one snapshot. The auditor's CW
    recheck, CX-02 (2026-10-31): the point page had parsed one result and read the evidence of another published
    between its reads (A's prediction beside B's limit), and the export had written a bundle of A's result and B's
    evidence. A result replaced between the two reads (its version changed: ``core.file_reads``) is read again; a
    mismatch that persists is refused. ``FileNotFoundError`` without a result; ``ValueError`` naming what it holds where
    it is not a JSON object, as ``load_result`` reads it."""
    from adroit.core import file_reads
    for _ in range(file_reads.TRIES):
        version, content = _versioned(result_path)
        try:
            return _saved(result_path, content)
        except ValueError:
            if version_now(result_path) == version:
                raise
    raise OSError(f"{result_path} changed each time it was read with its evidence ({file_reads.TRIES} attempts)")


def result_bytes(result_path: Path) -> bytes:
    """A saved result's bytes, read as one version of the file (``core.file_reads``)."""
    return _versioned(result_path)[1]


def _versioned(result_path: Path) -> tuple[tuple[int, ...], bytes]:
    from adroit.core import file_reads
    where = str(result_path)
    if not Path(where).exists():
        raise FileNotFoundError(f"{result_path}: no saved result")
    return file_reads.consistent(where, lambda *version: (version, file_reads.read(where, version)))


def version_now(result_path: Path) -> tuple[int, ...] | None:
    """The version of a file now (``core.file_reads.identity``: it changes with every replacement or rewrite), or None
    where it cannot be read."""
    import os
    from adroit.core import file_reads
    try:
        return file_reads.identity(os.stat(result_path))
    except OSError:
        return None


def _object(result_path: Path, content: bytes) -> dict:
    from adroit.core.durable import parse_object
    data, why = parse_object(content)
    if why:
        raise ValueError(f"{Path(result_path).name} {why}")
    return data


def _saved(result_path: Path, content: bytes) -> Saved:
    """``read_saved`` of the result's ``content``, read once: its sidecar read once and checked against it."""
    try:
        sidecar = sidecar_path(result_path).read_bytes()
    except FileNotFoundError:
        sidecar = None
    return saved_of(result_path, content, sidecar)


def saved_of(result_path: Path, content: bytes, sidecar: bytes | None) -> Saved:
    """``read_saved``'s checks of a result's bytes and its sidecar's (None: it has none), as their reader holds them
    (``evidence.version``, which reads them together): the snapshot, or ``ValueError`` naming the mismatch."""
    data = _object(result_path, content)
    digest = hashlib.sha256(content).hexdigest()
    if sidecar is None:
        kind, result = typed(data)
        return Saved(content, data, kind, result, build(kind, result, digest), "")
    envelope = EvidenceEnvelope.model_validate_json(sidecar)
    kind, result = typed(data, envelope.workflow)           # a damaged result is named by its field first
    if envelope.result_sha256 != digest:
        raise ValueError("evidence/result content mismatch")
    if not summary_matches(kind, envelope.summary, result):
        raise ValueError("evidence/result decision mismatch")
    if not copies_match(kind, envelope, result):
        raise ValueError("evidence/result copy mismatch: a certificate or the engine mapping differs from the result")
    if envelope.input_sha256 != content_hash(envelope.original_inputs):
        raise ValueError("evidence input identity mismatch")
    if hasattr(result, "request") and not request_matches(envelope.original_inputs, result.request):
        raise ValueError("evidence/result request mismatch")
    if (envelope.context.origin == "captured" and envelope.context.request_sha256
            and envelope.context.request_sha256 != envelope.input_sha256):
        raise ValueError("calculation-start request identity mismatch")
    return Saved(content, data, kind, result, envelope, hashlib.sha256(sidecar).hexdigest())


class EvidenceMismatch(ValueError):
    """A result's evidence names another version of it."""


def evidence_of(result_path: Path, content: bytes) -> EvidenceEnvelope | None:
    """The evidence of exactly ``content``, a result's bytes as its reader read them: its sidecar, read once, where it
    names those bytes' digest; None without a sidecar; ``EvidenceMismatch`` where it names another version, and
    ``ValueError`` where it cannot be read. For a reader that shows what the evidence holds beside a result it already
    holds, without the whole snapshot's checks (``read_saved``): the auditor's CX recheck, CY-03 (2026-11-01), a study page
    holding A had shown B's evidence's input history."""
    try:
        sidecar = sidecar_path(result_path).read_bytes()
    except FileNotFoundError:
        return None
    envelope = EvidenceEnvelope.model_validate_json(sidecar)
    if envelope.result_sha256 != hashlib.sha256(content).hexdigest():
        raise EvidenceMismatch("evidence/result content mismatch")
    return envelope


NO_EVIDENCE = "none"          # the evidence identity of a result without a sidecar (each reader rebuilds it)


class HeldEvidence(NamedTuple):
    """The evidence of a result's bytes as its reader holds them, read once (``evidence_held``): its identity
    (``evidence_identity``) and its envelope, of the same bytes (None without a sidecar, or where it cannot be read or
    names another version)."""
    identity: str
    envelope: EvidenceEnvelope | None


def evidence_held(result_path: Path, content: bytes) -> HeldEvidence:
    """The evidence of exactly ``content``, a result's bytes as its reader holds them, read once: what a page shows of
    it and the identity its actions then require are of one read (the auditor's DB/VI recheck, DC-04, 2026-11-03: an
    input-update card had read the evidence apart from the identity, and passed none to its reanalysis)."""
    try:
        sidecar = sidecar_path(result_path).read_bytes()
    except FileNotFoundError:
        return HeldEvidence(NO_EVIDENCE, None)
    except OSError:
        return HeldEvidence("", None)
    try:
        envelope = EvidenceEnvelope.model_validate_json(sidecar)
    except ValueError:
        return HeldEvidence("", None)
    if envelope.result_sha256 != hashlib.sha256(content).hexdigest():
        return HeldEvidence("", None)
    return HeldEvidence(hashlib.sha256(sidecar).hexdigest(), envelope)


def evidence_identity(result_path: Path, content: bytes) -> str:
    """The identity of the evidence of exactly ``content``, a result's bytes as its reader holds them, for an action
    that reader starts to require (``held_evidence``): the SHA-256 of its sidecar's bytes, read once, where it names
    those bytes' digest; ``NO_EVIDENCE`` without a sidecar; "" where it cannot be read or names another version (every
    reader of the snapshot refuses that already). The auditor's version-identity audit, VI-03 (2026-11-03): the result's digest
    alone had let a download and a reanalysis take evidence replaced after the page read it, the result unchanged."""
    return evidence_held(result_path, content).identity


def held_evidence(snapshot: Saved) -> str:
    """``evidence_identity`` of a snapshot (``read_saved``), as it read its evidence."""
    return snapshot.sidecar_sha256 or NO_EVIDENCE


def request_matches(original: dict[str, JsonValue], request: BaseModel) -> bool:
    """Compare typed requests with additive defaults; retain the original byte/digest identity."""
    try:
        return type(request).model_validate(original) == request
    except ValueError:
        return False

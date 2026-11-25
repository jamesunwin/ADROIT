"""Deterministic, selected-run review priorities; no scientific result is rewritten."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import Field, JsonValue

from adroit.core.evidence import EvidenceEnvelope, EvidenceObservation, content_hash, physical_identity
from adroit.core.state import StrictModel
from adroit.constraints.review_tasks import AffectedResult, ReviewQueue, ReviewTask, TaskKind
from adroit.core.chronology import dated_report


class SelectedEvidence(StrictModel):
    """One explicitly selected typed result and its calculation-time source snapshot."""

    envelope: EvidenceEnvelope
    result: dict[str, JsonValue]
    archived_inputs: dict[str, str] = Field(default_factory=dict)  # SHA256 -> YAML/JSON text
    # what its reader could not select as the graph's record names it (a promotion's edge to another version, or to
    # nothing saved), and edges it followed as found: the review queue's warnings (VI-04)
    warnings: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class PointRole(StrictModel):
    """A point's role in a selected result (thermal point, fit point, candidate, scan point), its status, and whether
    that status blocks the conclusion."""
    role: str
    status: str
    blocks_conclusion: bool = False


def load_selected(source) -> list[SelectedEvidence]:
    """Load a selected result or verified archive graph, never a directory-wide crawl. ``source``: a study's version
    (``evidence.version.Version``), a token naming one (each part it names checked), a result file or folder (the
    version saved now), or a bundle (``.zip``, read once: ``archive.held_bundle``). Each result is reviewed with its
    evidence as one version (the auditor's CW recheck, CX-02, 2026-10-31). A promotion's children and parent are the versions
    its record names (``evidence.version.follow``, as the export follows them): another version saved there, or
    nothing, is not reviewed in its place, and the promotion's warnings say so (the auditor's version-identity audit, VI-04,
    2026-11-03: a replaced child had been reviewed as the promotion's, and its review tasks lost). A bundle's selection
    keeps its manifest's warnings, among them the edges its export could not follow, so that its review says which
    tasks it cannot show, as the file's does (the auditor's DB/VI recheck, DC-02, 2026-11-03)."""
    import hashlib
    from adroit.evidence.archive import edge_notes, held_bundle, read_bundle, unfollowed
    from adroit.evidence.version import Token, Version, follow, resolve

    if not isinstance(source, (Version, Token)) and Path(source).suffix == ".zip":
        manifest, files = read_bundle(held_bundle(source))
        inputs = {hashlib.sha256(data).hexdigest(): data.decode("utf-8")
                  for name, data in files.items() if name.startswith("inputs/") and name.endswith((".yaml", ".json", ".yml"))}
        selected = [SelectedEvidence(envelope=EvidenceEnvelope.model_validate_json(files[n.evidence_path]),
            result=json.loads(files[n.result_path]), archived_inputs=inputs) for n in manifest.nodes]
        if selected:
            selected[0].warnings = [f"bundle: {warning}" + ("; not reviewed: its review tasks are not shown"
                                                            if unfollowed(warning) else "")
                                    for warning in manifest.warnings]
        return selected
    found = source if isinstance(source, Version) else resolve(source)       # ``Changed`` for a token's other version
    snapshot = found.saved()
    selected = [SelectedEvidence(envelope=snapshot.envelope, result=snapshot.result.model_dump(mode="json"))]
    if snapshot.workflow == "promotion":
        root = found.folder.resolve()
        edges = found.edges()
        for edge in edges:                          # the graph stays inside the selected study: checked before reading
            if not (Path(edge.target).parent.resolve() / "result.json").is_relative_to(root):
                raise ValueError("promotion review must stay inside the selected study graph")
        notes = []
        for followed in follow(found):
            if followed.version is None:            # its tasks not shown either (DC-02)
                notes.append(f"{followed.note}; not reviewed" + (" as it" if "now saved is another version" in
                                                                  followed.note else "")
                             + ": its review tasks are not shown")
                continue
            child = followed.version.saved()
            selected.append(SelectedEvidence(envelope=child.envelope, result=child.result.model_dump(mode="json")))
        selected[0].warnings = [f"promotion: {note}" for note in [*notes, *edge_notes(edges)]]
    return selected


def _roles(selection: SelectedEvidence) -> dict[str, PointRole]:
    envelope, result = selection.envelope, selection.result
    roles: dict[str, PointRole] = {}
    track = result.get("track1") if envelope.workflow == "single_idea" else result if envelope.workflow == "track1" else None
    engine = envelope.engine_mapping
    for key in ("verdict", "likelihood_verdict"):
        view = track.get(key) if track else None
        for crossing in view.get("crossings", []) if view else []:
            subject = physical_identity(engine, crossing["point"])
            roles[subject] = PointRole(role="thermal_point" if crossing.get("kind") == "contour" else "theory_band",
                status=crossing["status"], blocks_conclusion=crossing["status"] in ("pending", "undetermined"))
    for band in result.get("band", []):
        if band.get("point"):
            subject = physical_identity(engine, band["point"])
            roles[subject] = PointRole(role="fit_point", status=band["status"],
                                      blocks_conclusion=band["status"] in ("pending", "undetermined"))
    for point in result.get("thermal", []) if envelope.workflow == "single_idea" else []:   # the headline's points
        if point.get("point"):
            subject = physical_identity(engine, point["point"])
            roles[subject] = PointRole(role="thermal_point", status=point.get("status") or "pending",
                                      blocks_conclusion=(point.get("status") or "pending") in ("pending", "undetermined"))
    eligibility = result.get("eligibility") or {}
    for label, verdicts in result.get("verdicts", {}).items():
        row = eligibility.get(label) if isinstance(eligibility, dict) else None
        if isinstance(row, dict) and row.get("certificate"):    # a judged Path 2 candidate by its eligibility (M1)
            status = {"eligible": "allowed", "excluded_point": "excluded"}.get(row["status"], "pending")
        else:
            status = "excluded" if any(v.get("excluded") is True for v in verdicts) else "pending" if any(
                v.get("excluded") is None for v in verdicts) else "allowed"
        roles[label] = PointRole(role="candidate", status=status, blocks_conclusion=status == "pending")
    return roles


def build_queue(selections: list[SelectedEvidence], *, include_scan: bool = False) -> ReviewQueue:
    """Rank actionable prerequisites, deduplicating repeat views and repeated inputs."""
    queue = ReviewQueue(selected_results=sorted({s.envelope.result_sha256 for s in selections}))
    grouped: dict[str, ReviewTask] = {}
    for selection in selections:
        envelope = selection.envelope
        queue.warnings += selection.warnings
        roles = _roles(selection)
        if envelope.context.origin != "captured":
            queue.warnings.append(f"{envelope.workflow}: {envelope.context.origin} provenance; original source review is not inferred")
        records = {s.id: s for s in envelope.context.sources if "constraint_class" in s.metadata}
        for observation in [*envelope.observations,*_legacy_pending(selection)]:
            role = roles.get(observation.subject_id, PointRole(role="scan_point", status="diagnostic"))
            if role.role == "scan_point" and not include_scan:
                continue
            affected = AffectedResult(result_sha256=envelope.result_sha256, workflow=envelope.workflow,
                subject_id=observation.subject_id, role=role.role, status=role.status,
                blocks_conclusion=role.blocks_conclusion, reasons=observation.reasons, observation=observation)
            for kind, record_id, reason in _actions(observation, records):
                key = content_hash({"kind": kind, "record_id": record_id, "reason": reason})
                task = grouped.setdefault(key, _task(key, kind, record_id, reason))
                if not any(a.result_sha256 == affected.result_sha256 and a.observation.identity == observation.identity
                           for a in task.affected):
                    task.affected.append(affected)
        for name, reason in _study_pending(selection).items():
            observation = EvidenceObservation(subject_id=envelope.result_sha256, physical_input={}, observable=name,
                calculation="unresolved", reasons=[reason])
            kind = _calculation_kind(observation)
            key = content_hash({"kind": kind, "record_id": "", "reason": reason})
            task = grouped.setdefault(key, _task(key, kind, "", reason))
            task.affected.append(AffectedResult(result_sha256=envelope.result_sha256, workflow=envelope.workflow,
                subject_id=envelope.result_sha256,role="study",status="pending",blocks_conclusion=True,
                reasons=[reason],observation=observation))
    for task in grouped.values():
        task.blocked_points = len({a.subject_id for a in task.affected if a.blocks_conclusion})
        task.affected_studies = len({a.result_sha256 for a in task.affected})
    feasibility = {"source_verification":0,"missing_input":1,"backend":2,"source_change":3,
                   "coverage":4,"recast_likelihood":5,"unsupported_model":6,"unresolved_calculation":7}
    queue.tasks = sorted(grouped.values(), key=lambda t: (-bool(t.blocked_points), -t.blocked_points,
                                                        -t.affected_studies, feasibility[t.kind], t.id))
    queue.warnings = sorted(set(queue.warnings))
    return queue


def _actions(observation: EvidenceObservation, records: dict) -> list[tuple[TaskKind, str, str]]:
    if observation.observable in ("direct_detection_prediction", "fitted_signal_events"):
        return []
    ids = [sid for sid in observation.source_ids if sid in records or (
        observation.review == "legacy_unknown" and not sid.startswith("experiment:"))]
    tasks = []
    review_only = False
    cl_mismatch=(observation.native_confidence_level is not None and observation.required_confidence_level is not None
                 and observation.native_confidence_level != observation.required_confidence_level)
    explicit_waiting=any("verification" in reason.lower() and "await" in reason.lower() for reason in observation.reasons)
    if observation.review == "unreviewed" or explicit_waiting:
        for sid in ids:
            tasks.append(("source_verification", sid, f"source verification required for {sid}"))
        review_only = bool(ids) and all(not reason or any(word in reason.lower() for word in (
            "verification", "unverified", "re-review", "review required")) for reason in observation.reasons)
    if observation.observable == "omega_h2":
        return tasks
    if observation.excluded is None and not review_only:
        reason = "; ".join(observation.reasons) or "saved comparison is unresolved; identify the missing calculation"
        kind=_calculation_kind(observation)
        if not (cl_mismatch and kind=="recast_likelihood"):
            tasks.extend((kind, sid, reason) for sid in ids or [""])
    if cl_mismatch:
        reason = (f"native CL={observation.native_confidence_level:g}; requested CL={observation.required_confidence_level:g}; "
                  "source likelihood or justified new calculation required")
        tasks.extend(("recast_likelihood", sid, reason) for sid in ids or [""])
    return list(dict.fromkeys(tasks))


def _legacy_pending(selection: SelectedEvidence) -> list[EvidenceObservation]:
    """Keep exact old pending reasons when the historical comparison was not retained."""
    result=selection.result
    track=result.get("track1") if selection.envelope.workflow=="single_idea" else result if selection.envelope.workflow=="track1" else None
    observations=[]
    for view_name in ("verdict","likelihood_verdict"):
        view=track.get(view_name) if track else None
        for crossing in view.get("crossings",[]) if view else []:
            if crossing.get("evaluation") is not None:
                continue
            subject=physical_identity(selection.envelope.engine_mapping,crossing["point"])
            for reason in crossing.get("pending",[]):
                ids=re.findall(r"record \(([^)]+)\)",reason)
                native=next((o for o in crossing.get("native_constraints",{}).values()
                             if o.get("why") and o["why"]==reason),None)
                if not ids and native and native.get("source"):
                    ids=[s.id for s in selection.envelope.context.sources if native["source"] in (s.id,s.reference)]
                observations.append(EvidenceObservation(subject_id=subject,physical_input=crossing["point"],
                    observable="historical pending comparison",calculation="legacy_unknown",review="legacy_unknown",
                    source_ids=ids,reasons=[reason],native_confidence_level=native.get("confidence_level") if native else None,
                    required_confidence_level=.95,construction="exact saved pending reason; missing numerical comparison is not reconstructed",
                    details={"omega_h2":crossing.get("omega_h2"),"root_residual":crossing.get("relative_residual"),
                             "old_comparison_available":False}))
    return observations


def _calculation_kind(observation: EvidenceObservation) -> TaskKind:
    if observation.calculation == "unavailable_backend":
        return "backend"
    if observation.calculation == "missing_input":
        return "missing_input"
    if observation.applicability == "unsupported":
        return "unsupported_model"
    text = " ".join(observation.reasons).lower()
    if any(word in text for word in ("likelihood", "recast", "95% comparison needs")):
        return "recast_likelihood"
    if any(word in text for word in ("missing input", "not supplied", "mass-basis", "coefficient", "relativistic completion")):
        return "missing_input"
    if any(word in text for word in ("not in the tools", "not installed", "backend unavailable")):
        return "backend"
    if any(word in text for word in ("validated range", "no recorded search", "not tabulated", "uncovered", "coverage")):
        return "coverage"
    return "unresolved_calculation"


def _task(key: str, kind: TaskKind, record_id: str, reason: str) -> ReviewTask:
    actions = {
        "source_verification":"Compare the record's source figure/table, data, assumptions and native CL; a named expert must sign the current payload.",
        "recast_likelihood":"Obtain the source likelihood/acceptance or implement and independently validate the requested physical recast; do not rescale the published CL.",
        "missing_input":"Request the specific missing physical input from the researcher; do not fill it with a benchmark.",
        "backend":"Install or provide the declared calculation backend/data and validate it, then re-evaluate this point.",
        "coverage":"Add independent response/topology/domain validation or leave this region explicitly pending.",
        "unsupported_model":"Provide a faithful supported contract or implement and validate the omitted physics.",
        "source_change":"Review the scientific source/data diff and re-evaluate; preserve the old result as historical evidence.",
        "unresolved_calculation":"Inspect the exact saved reason and complete the bounded deterministic calculation or document the remaining limitation.",
    }
    return ReviewTask(id=key,kind=kind,record_id=record_id,title=f"{kind.replace('_',' ')}: {record_id or 'calculation'}",
                      action=actions[kind],reason=reason)


def _study_pending(selection: SelectedEvidence) -> dict[str, str]:
    result, pending = selection.result, {}
    if selection.envelope.workflow == "promotion":
        pending.update(result.get("undetermined", {}))
    if selection.envelope.workflow in ("native_joint", "exclusion"):
        pending.update(result.get("omitted", result.get("skipped", {})))
    if selection.envelope.workflow == "lagrangian":
        if result.get("status", "complete") != "complete":
            pending["bespoke model"] = result["status"]
        pending.update((result.get("exclusion") or {}).get("skipped", {}))
    for reason in result.get("thermal_pending", []):
        pending[f"thermal:{len(pending)}"] = reason
    if result.get("unsupported"):
        pending["model mapping"] = result["unsupported"]
    return pending


def queue_for(source: Path, *, include_scan: bool = False) -> ReviewQueue:
    """Shared CLI/UI/export queue for one selected result or promotion/archive graph."""
    return build_queue(load_selected(source),include_scan=include_scan)




@dated_report
def report(queue: ReviewQueue) -> str:
    """Render priority, exact affected inputs and separate actions without new verdicts."""
    lines = ["# Requested-result review queue", "", queue.ranking, "",
             "| priority | task | record | blocked points | studies | action |",
             "|---|---|---|---|---|---|"]
    for index, task in enumerate(queue.tasks, 1):
        lines.append(f"| {index} | {task.kind} | {task.record_id or '—'} | {task.blocked_points} | {task.affected_studies} | {task.action} |")
        lines += [""] + [f"- {a.workflow}, {a.role}, `{a.subject_id}` ({a.status}): "
                          f"{'; '.join(a.reasons) or task.reason}" for a in task.affected]
    lines += [""] + [f"- {w}" for w in queue.warnings]
    return "\n".join(lines)+"\n"

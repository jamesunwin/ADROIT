"""Input-bound review packets and historical diffs, with no fabricated old curves."""

from __future__ import annotations

import yaml

from adroit.core.evidence import SourceEvidence, content_hash
from adroit.constraints import review
from adroit.constraints.review_identity import REVIEW_FIELDS, signature_status
from adroit.constraints.review_queue import SelectedEvidence
from adroit.constraints.review_tasks import RecordReviewPacket, ReviewDifference, ReviewTask


def packet_for(record_id: str, selection: SelectedEvidence | None = None,
               task: ReviewTask | None = None, selected: list[SelectedEvidence] = (),
               held: review.Reading | None = None) -> RecordReviewPacket:
    """Assemble the curve/source panel, assumptions, saved comparisons and old/new diff. ``selected``: the whole
    selection the task was found in, whose warnings (an edge of a promotion's graph not followed, and so its tasks not
    shown) the packet keeps (the auditor's DB/VI recheck, DC-02, 2026-11-03). ``held``: the reading of the record
    (``review.Reading``) the packet is of, its content and data digests, signature state, version and curves alike,
    and the figure beside it (read here when not given; the auditor's DJ recheck, DK-02, 2026-11-07: each had been read
    apart). Its review state and its signature's binding are one status, of that reading (the auditor's DK recheck, DL-01,
    2026-11-07: the review state had been the record's signature checked again against its data file as it then
    stood, so a packet of a stale B said "verified")."""
    held = held if held is not None else review.reading(record_id)
    record = held.record
    metadata = record.model_dump(mode="json")
    status = signature_status(record,held.version)
    current = SourceEvidence(id=record.id,reference=record.source,version=str(record.version),
        payload_sha256=content_hash(metadata),data_path=record.data_file,data_sha256=held.data_sha256,
        review="verified" if status.usable else "unreviewed",reviewed_by=record.verified_by,
        reviewed_on=record.verified_on,metadata=metadata,verification_binding=status.model_dump(mode="json"))
    previous = next((s for s in selection.envelope.context.sources if s.id == record_id),None) if selection else None
    packet = RecordReviewPacket(record_id=record_id,task=task,current=current,previous=previous,
        source_url=f"https://arxiv.org/pdf/{record.figure.arxiv}" if review.on_arxiv(record) else record.source,
        source_page=record.figure.page if record.figure else None,source_label=record.figure.label if record.figure else "")
    try:
        packet.current.verification_binding["current_sha256"]=held.version()
    except (OSError,ValueError) as error:
        packet.warnings.append(f"current scientific payload cannot be bound: {error}")
    try:
        packet.current_curves=[c.model_dump(mode="json") for c in review.curves(record,held)]
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        packet.warnings.append(f"current curve unavailable: {error}")
    if previous is not None:
        _differences(packet)
        _old_curves(packet,selection)
    else:
        packet.warnings.append("no calculation-time source snapshot; historical review/content is unknown")
    packet.warnings.append("Source review does not change a saved verdict, transfer a benchmark, extend a validated range or convert the source CL.")
    packet.warnings += [warning for s in selected for warning in s.warnings]
    return packet


def _differences(packet: RecordReviewPacket) -> None:
    previous = packet.previous
    keys = sorted((previous.metadata.keys() | packet.current.metadata.keys()) - REVIEW_FIELDS)
    for key in keys:
        before,after=previous.metadata.get(key),packet.current.metadata.get(key)
        if before != after:
            packet.differences.append(ReviewDifference(field=key,before=before,after=after))
    if not previous.data_sha256 and packet.current.data_sha256:
        packet.warnings.append("calculation-time data digest not recorded; historical data-change status is unknown")
    elif previous.data_sha256 != packet.current.data_sha256:
        packet.differences.append(ReviewDifference(field="data_file_sha256",before=previous.data_sha256,
                                                  after=packet.current.data_sha256))


def _old_curves(packet: RecordReviewPacket, selection: SelectedEvidence) -> None:
    from adroit.core.dm_state import ConstraintRecord

    previous = packet.previous
    if not previous.data_path and not previous.metadata.get("data_file"):
        packet.previous_curve_status="source held inline values; see historical metadata"
        return
    contents=selection.archived_inputs.get(previous.data_sha256)
    if contents is None:
        packet.previous_curve_status="old data bytes not captured here; current curves are not a substitute"
        return
    old_record=ConstraintRecord.model_validate(previous.metadata)
    data=review._own_part(old_record,yaml.safe_load(contents))
    curves=[]
    review._walk({k:v for k,v in data.items() if k not in ("source","correction_note")},"",curves)
    packet.previous_curves=[c.model_dump(mode="json") for c in curves]
    packet.previous_curve_status="captured historical data"


def packet_report(packet: RecordReviewPacket) -> str:
    """Render the exact source changes and compared physical inputs for expert inspection."""
    import json

    lines=[f"# Record review: {packet.record_id}","",f"Source: {packet.current.reference}",
        f"Figure/table: {packet.source_label}; page {packet.source_page}; {packet.source_url}",
        f"Review state: {packet.current.verification_binding.get('state','unknown')}",
        f"Review binding: {packet.current.verification_binding.get('reason','unknown')}","",
        f"Current scientific hash: {packet.current.verification_binding.get('current_sha256','unknown')}","",
        "Source/assumption/data changes:"]
    lines += [f"- {d.field}: {json.dumps(d.before,ensure_ascii=False)} → {json.dumps(d.after,ensure_ascii=False)}"
              for d in packet.differences] or ["- No recorded scientific metadata change."]
    lines += ["",f"Historical curves: {packet.previous_curve_status}","","Saved numerical comparisons:"]
    if packet.task:
        for affected in packet.task.affected:
            observation=affected.observation
            lines += [f"- {affected.workflow} {affected.role} `{affected.subject_id}`: {affected.status}; "
                f"{observation.observable} = {observation.value} {observation.units}; "
                f"native/requested CL {observation.native_confidence_level}/{observation.required_confidence_level}; "
                f"reasons: {'; '.join(affected.reasons) or packet.task.reason}",
                f"  physical input: {json.dumps(observation.physical_input,sort_keys=True)}",
                f"  comparison details: {json.dumps(observation.details,sort_keys=True,ensure_ascii=False)}"]
    notes = str(packet.current.metadata.get("notes") or "").rstrip()      # the record as the packet read it (DK-02)
    lines += ["", "Notes (the reviewer's; not part of the signed content):", notes or "none yet"]
    lines += [""] + [f"- {w}" for w in packet.warnings]
    return "\n".join(lines)+"\n"

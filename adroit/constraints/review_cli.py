"""Selected-run expert review queue, source packet and researcher-controlled timer."""

from __future__ import annotations

from pathlib import Path

import typer

from adroit.constraints.review_queue import build_queue, load_selected, report
from adroit.constraints.review_packets import packet_for, packet_report


def queue_command(run: list[Path] = typer.Option(...,"--run",help="selected result, folder or evidence ZIP; repeatable"),
                  out: Path | None = typer.Option(None,"--out",help="write the typed queue JSON and Markdown"),
                  include_scan: bool = typer.Option(False,"--include-scan",help="also queue ordinary scan points' "
                                                    "tasks, not only the points a conclusion rests on")) -> None:
    """Prioritize the actual requested results' pending review/calculation tasks. $0."""
    try:
        queue=build_queue([s for path in run for s in load_selected(path)],include_scan=include_scan)
        if out is not None:                     # both prepared, then written under one hold (DJ-01)
            from adroit.core.durable import export
            if out.suffix==".md":
                raise ValueError("--out names the queue's JSON file; its Markdown is written beside it (.md)")
            export(out.parent,{out.name:queue.model_dump_json(indent=2),out.with_suffix(".md").name:report(queue)})
    except (ValueError,OSError,KeyError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(report(queue))


def packet_command(record_id: str,run: Path | None = typer.Option(None,"--run",help="a selected result, folder or "
                                                                 "evidence ZIP whose saved comparisons to show"),
                   task_id: str = typer.Option("","--task",help="a task ID from records queue (default: the "
                                               "record's first task in --run)"),
                   out: Path | None = typer.Option(None,"--out",help="folder for the review packet")) -> None:
    """Show current source/curves, saved comparisons and an honest old/new diff. $0."""
    try:
        selections=load_selected(run) if run else []
        queue=build_queue(selections)
        task=next((t for t in queue.tasks if (t.id==task_id if task_id else t.record_id==record_id)),None)
        if task_id and task is None:
            raise ValueError("no such task in the selected scientific input")
        if task is not None and task.record_id != record_id:
            raise ValueError("selected task belongs to another record")
        chosen=next((s for s in selections if task and s.envelope.result_sha256 in {
            a.result_sha256 for a in task.affected}),selections[0] if selections else None)
        packet,figure,missing=_prepared(record_id,chosen,task,selections,out is not None)
        if out is not None:
            from adroit.core.durable import export
            export(out,{"record_review.json":packet.model_dump_json(indent=2),"report.md":packet_report(packet),
                        "current_curves.png":figure})
    except (ValueError,OSError,KeyError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(packet_report(packet))
    for line in missing:
        typer.echo(f"Not shown in the record's figure: {line}.")


def _prepared(record_id: str,chosen,task,selections,draw: bool = True) -> tuple:
    """A curated record's review, prepared whole before any of it is written: its packet, the figure of the very record
    the packet describes (None where it has none to draw, or ``draw`` is false) and the curves that figure cannot
    show, all from one reading of the record and its data file (``review.reading``): its digests, signature state,
    version, curves, notes and figure are of the same bytes, however the files change while it is prepared (the auditor's
    DJ recheck, DK-02, 2026-11-07: read apart, a data file changed and restored between the reads had exported B's
    curve or figure beside A's current signature). Then the record is read again: a record that is no longer that
    version is refused, nothing written, so that an export is of the record as it stands (the auditor's DI recheck, DJ-01,
    2026-11-07: the three files of a packet had been written apart, and could describe two records)."""
    from adroit.constraints import review
    from adroit.core.evidence import content_hash
    held=review.reading(record_id)
    packet=packet_for(record_id,chosen,task,selections,held)
    figure=review.figure(held.record,held) if draw else None
    now=review.reading(record_id)
    if (content_hash(now.record.model_dump(mode="json")),now.data_sha256)!=(packet.current.payload_sha256,
                                                                           packet.current.data_sha256):
        raise ValueError(f"the record {record_id} changed while its review was prepared: export it again; nothing "
                         "was written")
    return packet,figure,held.missing


def timer_start(packet: Path,session: Path,participant: str,
                condition: str = typer.Option("assisted","--condition",help="manual or assisted")) -> None:
    """Start the existing paired-human protocol on an exported review packet: one whole export's, its report and
    figure as that export wrote them (``durable.exported``: not an interrupted export's, DK-05, nor a packet beside
    another export's report, the auditor's DL recheck, DM-03). $0."""
    from adroit.constraints.review import start_timing
    from adroit.constraints.review_tasks import RecordReviewPacket
    from adroit.core.durable import exported
    try:
        data=packet.read_bytes()
        if why:=exported(packet.parent,packet.name,data):
            raise ValueError(f"{why}: export the review again")
        start_timing(RecordReviewPacket.model_validate_json(data),participant,condition,session)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(f"Review timer started: {session}; no researcher-time saving has been inferred.")


def register(app: typer.Typer) -> None:
    """Extend the existing Records command group; preserve its verification gate."""
    app.command("queue")(queue_command)
    app.command("review")(packet_command)
    app.command("timer-start")(timer_start)

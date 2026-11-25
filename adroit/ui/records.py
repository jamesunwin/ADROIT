"""The workbench's review of the constraint records: each curve beside its source figure, and the verification.

- **Records** (``/records``): two views, as the models have (the owner, 2026-10-18): **Standard**, every packaged
  record, verified or awaiting verification; **Personal additions**, the personal experimental library's drafts,
  bound limits and searches and profiles, manually imported or retrieved by constraint discovery, each linked to its
  own page (``library.records_index``; read-only, nothing copied between the two).
- **A record** (``/record?id=…``): its source, quantity, data, assumptions and checks; the
  record's curves drawn beside the source paper opened at the figure's page (fetched into the
  tools folder by ``adroit records fetch-sources``, never copied into the repository); and a
  form that writes the person's verification into ``records.yaml`` (``constraints.review``).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from nicegui import ui

from adroit.constraints import database, review
from adroit.ui.pages import header
from adroit.constraints.review_identity import signature_status
from adroit.constraints.review_tasks import RecordReviewPacket


def records_page(root: Path | None = None, study: str = "") -> None:
    """Every constraint record with its verification status and, given a runs directory, the review queue of a
    selected study."""
    header("Constraint records", "The published constraints ADROIT applies, each transcribed from its paper and "
           "verified by a person before a run uses it. Open one to compare it with its source.",
           details=('"verified (current)": the person\'s signature matches the record as it is now. "verified '
                    '(legacy_baseline)": signed before the signatures were bound to the record\'s content, and '
                    'unchanged since. "awaits verification": not used unless a run asks for unverified records.',))
    with ui.tabs().classes("w-full") as tabs:
        standard = ui.tab("Standard")
        personal = ui.tab("Personal additions")
    with ui.tab_panels(tabs, value=standard).classes("w-full"):
        with ui.tab_panel(standard):
            _standard_panel(root, study)
        with ui.tab_panel(personal):
            personal_panel()


FILTERS = {"all": "everything", "personal_revision": "drafts", "personal_limit": "bound limits",
           "personal_search": "bound searches", "profile": "profiles", "discovery": "retrieved by discovery"}


def personal_panel() -> None:
    """The personal additions, filtered by kind or origin, each linked to its page in the experimental library."""
    from adroit.library.records_index import personal
    entries = personal()
    ui.label(f"{len(entries)} personal additions. They are used only when a run selects them (a private limit or a "
             "profile); the standard records are unchanged.").classes("text-gray-600")
    choice = ui.select(FILTERS, value="all", label="show").classes("w-64")

    @ui.refreshable
    def listing() -> None:
        for e in entries:
            if choice.value == "discovery" and not e.origin.startswith("discovery:"):
                continue
            if choice.value not in ("all", "discovery") and e.kind != choice.value:
                continue
            with ui.row().classes("items-center gap-2 no-wrap"):
                ui.badge(e.review or e.kind, color="green" if "bound" in e.review else "orange")
                target = ("/experiments/view?" + urlencode({"reference": e.reference}) if e.kind == "personal_revision"
                          else "/experiments/profiles")
                ui.link(e.title, target)
                ui.label(f"{e.reference} · {e.origin}").classes("text-gray-600 text-xs font-mono")
    listing()
    choice.on_value_change(lambda _: listing.refresh())


def _standard_panel(root: Path | None, study: str) -> None:
    """The packaged records: the review queue of a study, a search, and each record's verification state."""
    rows = database.records()
    status = {r.id: signature_status(r) for r in rows}      # each record's, read once: its badge and its place (DL-01)
    waiting = [r for r in rows if not status[r.id].usable]
    ui.label(f"{len(rows)} records; {len(waiting)} await a person's verification").classes("text-gray-600")
    if root is not None:
        with ui.expansion("Review the records a study depends on", value=bool(study)).classes("w-full"):
            _queue_panel(root,study)
    query = ui.input("Find a record", placeholder="part of a name, an id or a kind (collider, direct detection, …)").classes("w-full")

    @ui.refreshable
    def listing() -> None:
        text = (query.value or "").lower()
        groups: dict[str, list] = {}
        for r in sorted(rows, key=lambda r: (status[r.id].usable, r.id)):
            kind = r.constraint_class.value.replace("_", " ")
            if text and text not in f"{r.id} {r.name} {kind}".lower():
                continue
            groups.setdefault(kind, []).append(r)
        for kind, members in sorted(groups.items()):
            ui.label(kind.capitalize()).classes("text-lg font-medium mt-3")
            for r in members:
                with ui.row().classes("items-center gap-2 no-wrap"):
                    state, usable = status[r.id].state, status[r.id].usable
                    ui.badge(f"verified ({state})" if usable else f"awaits verification ({state})",
                             color="green" if usable else "orange")
                    ui.link(r.id, f"/record?id={r.id}")
                    ui.label(r.name).classes("text-gray-600 text-sm")
    listing()
    query.on_value_change(lambda _: listing.refresh())


def _source_view(r, sources: Path | None) -> None:
    """The source paper at the figure's page, if fetched; otherwise a link to it."""
    if r.figure is None:
        ui.label("No figure reference.").classes("text-gray-500")
        return
    from adroit.constraints.review import on_arxiv
    name = f"{r.figure.arxiv.replace('/', '_')}.pdf"
    paper = f"arXiv:{r.figure.arxiv}" if on_arxiv(r) else r.source
    ui.label(f"Compare with {paper}, {r.figure.label} (page {r.figure.page})").classes("font-bold")
    if sources is not None and (sources / name).exists():
        ui.element("iframe").props(f'src="/sources/{name}#page={r.figure.page}"').style(
            "width: 100%; height: 640px; border: 1px solid #ccc")
    elif not on_arxiv(r):                         # the PDG's review: no arXiv page to link to
        ui.label(f"Not an arXiv paper: put its PDF in the tools folder's record-sources/ as {name} to see it "
                 "here.").classes("text-gray-500 text-sm")
    else:
        ui.link("open the paper on arXiv", f"https://arxiv.org/pdf/{r.figure.arxiv}#page={r.figure.page}",
                new_tab=True)
        ui.label("(adroit records fetch-sources shows it here)").classes("text-gray-500 text-sm")


def record_page(root: Path, record_id: str, sources: Path | None, records_path: Path,
                study: str = "", task_id: str = "", version: dict | None = None) -> None:
    """One constraint record: its data, curves beside the source figure, assumptions and checks, and the verification
    form; with ``study``, the review packet of its task in that study, of the version its queue was shown from
    (``version``: the queue link's token parameters, ``_queue_panel``)."""
    try:            # one reading: the hash a verification binds, the figure, the data and the packet shown (DK-02)
        held = review.reading(record_id)
    except KeyError:
        header("Constraint record")
        ui.label(f"No record {record_id!r}.")
        return
    r = held.record
    header(r.name, "One constraint as ADROIT applies it: its numbers or curves beside the source's figure, its "
           "assumptions, and the checks made when it was transcribed.")
    try:
        expected_hash=held.version()
    except (OSError,ValueError):
        expected_hash=""
    ui.markdown(f"**{r.id}** · {r.constraint_class.value} · {r.source}")
    ui.label(f"Quantity: {r.quantity}").classes("text-gray-700")
    for line in review.quoted(r.data):
        ui.label(line).classes("font-mono text-sm")
    with ui.row().classes("w-full no-wrap gap-4"):
        with ui.column().classes("w-1/2"):
            plot = review.figure(r, held)                # drawn for this page, shown as drawn (DI-01)
            missing = held.missing
            if plot is not None:
                from adroit.ui.style import embedded
                ui.image(embedded(plot)).classes("w-full")
            elif not missing:
                ui.label("This record holds single numbers, not curves: compare them with the source.")
            for line in missing:
                ui.label(f"Not shown: {line}.").classes("text-sm text-red-700")
        with ui.column().classes("w-1/2"):
            _source_view(r, sources)
    ui.label("Assumptions").classes("text-lg mt-2")
    for line in r.assumptions:
        ui.label(f"• {line}").classes("text-sm")
    ui.label("Checks made on the transcription").classes("text-lg mt-2")
    for line in r.checks:
        ui.label(f"• {line}").classes("text-sm")
    ui.label("Notes").classes("text-lg mt-2")
    if r.notes:
        ui.markdown(r.notes).classes("text-sm")
    else:
        ui.label("None yet: write them under the record's notes in records.yaml (not part of the signed content).") \
            .classes("text-sm text-gray-500")
    packet = _packet(root,record_id,study,task_id,version or {},held)
    if packet:
        _packet_panel(packet)
    _verification(held, records_path,expected_hash)


def _verification(held: review.Reading, records_path: Path,expected_hash: str) -> None:
    """The record's signature state and the verification form, of the reading the page shows (``held``): its badge
    beside the figure drawn from it (the auditor's DK recheck, DL-01, 2026-11-07: the state had been read again from the
    records and the data file as they then stood, so a stale B's figure was shown as "verified"). After a verification
    the record is read again, and its new state shown only while its version is still the one shown."""
    shown = {"held": held, "changed": False}

    @ui.refreshable
    def panel() -> None:
        current = shown["held"].record
        status = signature_status(current, shown["held"].version)
        if shown["changed"]:
            ui.label("The record has changed since this page was drawn: reload the page to see it, and its "
                     "signature's state, as it is now.").classes("text-sm text-red-700")
            return
        if status.usable:
            ui.badge(f"verified {current.verified_on} by {current.verified_by}", color="green")
            ui.label("The signature matches the record as shown here." if status.state == "current" else
                     f"Signature: {status.state}; {status.reason}").classes("text-sm text-gray-600")
            return
        ui.label(f"Signature: {status.state}; {status.reason}").classes("text-sm text-gray-600")
        ui.label("Verification").classes("text-lg mt-2")
        name = ui.input("your name, as it will be written into the record")
        compared = ui.checkbox("I have compared the data and assumptions with the source")
        if not expected_hash:
            ui.label("Cannot bind a review: declared scientific input unavailable")
            return

        def verify() -> None:
            if not compared.value:
                ui.notify("Tick the box once you have compared the record with its source.", type="warning")
                return
            try:
                review.verify(current.id, name.value or "", path=records_path,expected_sha256=expected_hash)
            except ValueError as error:
                ui.notify(str(error), type="negative")
                return
            ui.notify(f"{current.id} verified by {name.value}", type="positive")
            try:
                now = review.reading(current.id)
                same = now.version() == expected_hash
            except (KeyError, OSError, ValueError):
                now, same = None, False
            if same:
                shown["held"] = now
            else:
                shown["changed"] = True
            panel.refresh()
        ui.button("Mark as verified", on_click=verify)
    panel()


def _queue_panel(root: Path, study: str) -> None:
    from adroit.orchestrator import studies
    from adroit.ui.pages import inside
    ui.label("Review selected results").classes("text-lg mt-3")
    options={str(Path(s.folder).relative_to(root)):s.title for _,s in studies.tree(root)
             if s.kind in ("track1","signal","single_idea","promotion")}
    selected=ui.select(options,label="study whose pending conclusions need review",value=study or None).classes("w-96")
    from adroit.ui.wizards import _unoffered
    _unoffered(root)
    ui.button("Show review queue",on_click=lambda: ui.navigate.to("/records?"+urlencode({"study":selected.value or ""})))
    if not study:
        ui.label("Select a completed study; priorities come from its actual requested results.")
        return
    from adroit.constraints.review_queue import build_queue,load_selected
    from adroit.evidence.version import Token,resolve
    try:                    # the study's version, read once: its packets are opened as this version (``_packet``)
        found=resolve(inside(root,study))
        queue=build_queue(load_selected(found))
    except (OSError,ValueError,KeyError) as error:
        ui.label(f"Review queue unavailable: {error}")
        return
    token=found.token()
    shown=Token(token.path,result=token.result,evidence=token.evidence).query(root)
    ui.label(queue.ranking).classes("text-sm text-gray-600")
    for index,task in enumerate(queue.tasks,1):
        with ui.card().classes("w-full"):
            ui.label(f"{index}. {task.title}").classes("font-bold")
            ui.label(f"{task.blocked_points} blocked points; {task.affected_studies} selected studies")
            ui.label(task.reason)
            ui.label(task.action)
            ui.label(task.eligibility_note).classes("text-sm text-gray-600")
            for affected in task.affected:
                ui.label(f"{affected.workflow}: {affected.role} {affected.status}; "+"; ".join(affected.reasons)).classes("text-sm")
            if task.record_id:
                ui.link("Review source, comparisons and changes","/record?"+urlencode(
                    {"id":task.record_id,"study":study,"task":task.id,
                     **{k:v for k,v in shown.items() if k in ("sha256","evidence")}}))
    for warning in queue.warnings:
        ui.label(warning).classes("text-sm text-orange-700")


def _packet(root: Path,record_id: str,study: str,task_id: str,version: dict,
            held: review.Reading | None = None) -> RecordReviewPacket | None:
    """The review packet of a task in a study, of the version of the study its queue was shown from (``version``: its
    result's digest and its evidence's identity, as the queue's link names them): another version is refused, saying
    so, never a packet of other results under the task the queue showed (the version handle; the auditor's inventory: the
    packet had loaded the study again). ``held``: the page's reading of the record (``review.Reading``), which the
    packet is of, as the figure and the verification's hash above it are (the auditor's DJ recheck, DK-02)."""
    from adroit.constraints.review_queue import load_selected,build_queue
    from adroit.constraints.review_packets import packet_for
    from adroit.evidence.version import Changed,Token
    try:
        try:
            selections=load_selected(Token.from_query(root,{"path":study,**version})) if study else []
        except Changed as changed:
            what={"result":"result","evidence":"evidence"}.get(changed.part,changed.part)
            raise ValueError(f"the study's {what} has changed since its review queue was shown; reopen its queue") \
                from None
        queue=build_queue(selections)
        task=next((t for t in queue.tasks if (t.id==task_id if task_id else t.record_id==record_id)),None)
        if task_id and (task is None or task.record_id != record_id):
            raise ValueError("task does not match the selected record/result")
        chosen=next((s for s in selections if task and s.envelope.result_sha256 in {
            a.result_sha256 for a in task.affected}),selections[0] if selections else None)
        packet=packet_for(record_id,chosen,task,selections,held)
    except (OSError,ValueError,KeyError) as error:
        ui.label(f"Review packet unavailable: {error}")
        return None
    if chosen is not None:          # which version of the study its comparisons are of: the one its queue showed,
        ui.label(f"Of the study as its review queue showed it: result SHA-256 {chosen.envelope.result_sha256[:12]}…, "
                 f"its evidence {chosen.envelope.identity[:12]}…") \
            .classes("text-xs font-mono text-gray-500").mark("packet_version")    # its result and its evidence (DD-03)
    return packet


def _packet_panel(packet: RecordReviewPacket) -> None:
    ui.label("Saved comparisons and source changes").classes("text-lg mt-3")
    if packet.task:
        ui.label(packet.task.action)
        for affected in packet.task.affected:
            observation=affected.observation
            ui.label(f"{affected.workflow}: {affected.role} {affected.status}; {observation.observable} = "
                f"{observation.value} {observation.units}; native/requested CL "
                f"{observation.native_confidence_level}/{observation.required_confidence_level}")
            ui.code(str(observation.physical_input)).classes("text-xs")
            ui.code(str(observation.details)).classes("text-xs")
            for reason in affected.reasons:
                ui.label(reason)
    for difference in packet.differences:
        ui.label(f"Changed {difference.field}").classes("font-bold")
        with ui.row().classes("w-full"):
            ui.code(str(difference.before)).classes("w-1/2 text-xs")
            ui.code(str(difference.after)).classes("w-1/2 text-xs")
    if not packet.differences:
        ui.label("No recorded scientific metadata change.")
    ui.label(f"Historical curves: {packet.previous_curve_status}")
    if packet.previous_curves:
        ui.table(columns=[{"name":k,"label":k,"field":k} for k in ("label","x","y")],rows=packet.previous_curves)
    for warning in packet.warnings:
        ui.label(warning).classes("text-sm text-gray-600")

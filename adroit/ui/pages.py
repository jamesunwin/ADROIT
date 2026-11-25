"""The workbench's pages (DM15): the home screen, the studies, a run's live view, and a study's results.

- **Home** (``/``): the name, the acronym and a button for each page of the menu.
- **Studies** (``/studies``): the tree of studies (parents and children) and what is
  running (no running total of spending: the owner, 2026-10-23; each run's own cost is on its page).
- **Live** (``/live``): a run's status, time, spend and log, refreshed every
  second, with Cancel.
- **Records** (``/records``, ``ui.records``): the constraint records, their review and verification.
- **A study** (``/study``): its report with its plots, its parent and
  children, and the forms that continue it:
  - a Path 2 run: promote a candidate or its class (recursion);
  - a model list from an idea: approve the valid models to constrain (Track 1).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import yaml
from nicegui import ui

from adroit.orchestrator import studies
from adroit.ui import engine, forms, submission

if TYPE_CHECKING:
    from adroit.orchestrator.ideas import ModelResult

# The menu (the owner, 2026-10-12): "Constrain a model" is Track 1, "Signal best fits" Track 2 and "Explain a signal"
# the single-idea report, in the documentation and the CLI (track1, signal, single-idea). "Add a limit" is the
# experimental library (a paper's files → a reviewed private limit, or a signal) and "Add a signal" the anomaly record
# (2026-10-13).
NAV = [("Home", "/"), ("Studies", "/studies"), ("Constrain a model", "/new/track1"), ("Signal best fits", "/new/track2"),
       ("Explain a signal", "/new/single"), ("Model library", "/models"), ("Add a limit", "/experiments"),
       ("Add a signal", "/new/anomaly"), ("Records", "/records")]
ACRONYM = "Agentic Dark matter Reinterpretation and Operator Inference Toolkit"
# the home page's switch (the owner, 2026-11-18, the post-review changes item 1; core.workbench_settings)
AUTO_APPROVE = "Auto approve paid LLM calls (via the systems default models)"
AUTO_APPROVE_NOTE = ("On: each spend box starts ticked while its page's models are the defaults (Claude Opus 5.5; a "
                     "derivation's checker GPT-5.6 Sol). Each budget is still a hard cap; raising a session's cap and "
                     "every scientific choice stay yours. AI can make mistakes.")
AUTO_TICKED = "ticked by the auto-approve setting (Home): the default models are chosen"
KIND_COLOUR = {"idea": "teal", "track1": "blue", "signal": "purple", "single_idea": "indigo", "exclusion": "grey",
               "lagrangian": "grey", "promotion": "orange"}
STATUS_COLOUR = {"completed": "green", "budget_stopped": "orange", "failed": "red", "cancelled": "grey",
                 "running": "blue"}


# What each page of the menu does, in one line (the home cards; the UI clarity plan)
PURPOSE = {
    "Studies": "Every analysis you have run, with its verdict, children and cost.",
    "Constrain a model": "Is a model consistent with every search, and where is it viable? Scan its parameters.",
    "Signal best fits": "Which interactions best explain a search that saw events, and how significant is the fit?",
    "Explain a signal": "Test one model of yours against a signal: fit it, then constrain it around the best fit.",
    "Model library": "Your models (each saved revision kept) and the standard library of benchmark models.",
    "Add a limit": "Upload a paper and its data; after review, its limit joins your constraints.",
    "Add a signal": "Write or draft the record of a search that saw events, for the two signal pages.",
    "Records": "The published constraints ADROIT applies, each verified by a person against its source.",
}
EXAMPLES = [("Scan a library model", "the scalar singlet Higgs portal against every search ($0)",
             "/new/track1?portal=higgs_portal_scalar"),
            ("Fit a signal", "CDMS II Si's three events with the library's interactions ($0)",
             "/new/track2?anomaly=CDMS%20II%20Si%20(2013)"),
            ("Build a model from fields", "write the fields; ADROIT writes the Lagrangian and audits it ($0)",
             "/new/track1")]


def header(title: str, description: str = "", facts=(), details=(), subtitle: str = "") -> None:
    """The menu, then the page's title, its description, its facts (cost, time, next step) and its details
    (``style.page_header``)."""
    from adroit.ui.style import page_header
    page_header(title, description, facts, details, subtitle)


def landing() -> None:
    """The home screen: ADROIT, its acronym, the menu's pages as cards (each with what it does), and three examples
    to start from."""
    header("")
    with ui.column().classes("w-full items-center gap-4 mt-8"):
        ui.label("ADROIT").classes("text-7xl font-bold tracking-wide")
        ui.label(ACRONYM).classes("text-xl text-gray-600")
        auto_approve_switch()
        with ui.grid(columns=4).classes("gap-4 mt-6"):
            for name, target in NAV[1:]:
                with ui.card().classes("w-60 items-stretch gap-2"):
                    ui.button(name, on_click=lambda target=target: ui.navigate.to(target)).classes("h-12 text-base")
                    ui.label(PURPOSE[name]).classes("text-sm text-gray-600")
        with ui.card().classes("mt-4 w-full max-w-4xl"):
            ui.label("New here? Start with an example").classes("text-lg font-medium")
            for name, what, target in EXAMPLES:
                with ui.row().classes("items-baseline gap-2"):
                    ui.link(name, target).classes("font-medium")
                    ui.label(what).classes("text-sm text-gray-600")


def auto_approve_switch() -> None:
    """The home page's auto-approve switch, kept in the workbench's settings (``core.workbench_settings``)."""
    from adroit.core.workbench_settings import auto_approve, set_auto_approve

    def changed(event) -> None:
        try:
            set_auto_approve(bool(event.value))
        except OSError as error:
            ui.notify(f"the setting could not be saved ({error})")
            return
        ui.notify("paid calls with the default models are now approved for you" if event.value else
                  "each paid call now waits for your tick")

    with ui.column().classes("items-center gap-0 mt-2"):
        ui.switch(AUTO_APPROVE, value=auto_approve(), on_change=changed).mark("auto_approve")
        ui.label(AUTO_APPROVE_NOTE).classes("text-xs text-gray-500 max-w-2xl text-center")


def inside(root: Path, rel: str) -> Path:
    """A folder named relative to the runs directory, refused if it leaves it."""
    folder = (root / rel).resolve()
    if folder != root and root not in folder.parents:
        raise ValueError("outside the runs directory")
    return folder


def rel(root: Path, folder: str | Path) -> str:
    """A folder's path relative to the runs directory."""
    return str(Path(folder).resolve().relative_to(root))


def with_files(text: str, root: Path, folder: Path) -> str:
    """A report's plots (``![x](plot.png)``) served from the runs directory."""
    base = f"/files/{rel(root, folder)}"
    return re.sub(r"!\[([^\]]*)\]\(([^)/:]+\.png)\)", lambda m: f"![{m.group(1)}]({base}/{m.group(2)})", text)


KIND_WORD = {"track1": "Constrain", "signal": "Signal fits", "single_idea": "Explain", "idea": "Proposed models",
             "promotion": "Promotion", "exclusion": "Limits", "lagrangian": "Derivation", "reanalysis": "Reanalysis",
             "native_joint": "Native fit"}


CERTIFICATION_WORDS = {
    "stale": "The claims this headline rests on were certified under an earlier policy or on data that have changed "
             "since (stale); the verdict is as it was decided, and the report below was written then.",
    "legacy": "This result was saved before certificates: legacy, not assessed. Its verdict is as it was decided.",
    "not certified": "Some claims this headline rests on are not certified; the report says which and why."}


def _certification_line(found, data: object) -> None:
    """The certification of the stored headline's claims (``found``, the headline of the result read as ``data``), said
    on the study's card where it is not simply "certified" (the auditor's consolidation audit, CO-07, 2026-10-25), with what
    a stale one is stale on."""
    if found.damage:
        ui.label(f"result.json: {found.damage}").classes("text-sm text-orange-800").mark("unreadable_result")
    elif found.certification in CERTIFICATION_WORDS:
        ui.label(CERTIFICATION_WORDS[found.certification] + _stale_on(data)) \
            .classes("text-sm text-amber-800").mark("study_certification")


def _stale_on(data: object) -> str:
    """What the first stale certificate of the claims a stored headline rests on is stale on
    (``core.certificate.stale_reasons``; ``study_headline.resting_claims``), in the result read as ``data``."""
    from adroit.core.certificate import Certificate, stale_reasons
    from adroit.orchestrator.study_headline import resting_claims
    from adroit.parameter_space.certification import current_bound
    try:
        for claim in resting_claims(data):
            if isinstance(claim, dict) and isinstance(claim.get("certificate"), dict):
                c = Certificate.model_validate(claim["certificate"])
                if why := stale_reasons(c, current_bound(c)):
                    return f" ({why[0]})"
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return ""


def studies_page(root: Path) -> None:
    """The studies: what is running, the tree of studies (kind, title, verdict, when, cost), searchable, and runs that
    ended without a study."""
    from adroit.ui.style import when
    header("Studies", "Every analysis you have run, newest first, with the studies made from it. Open one to see its "
           "verdict and report; its inputs are pinned, so later data need a new run.")
    listed, damaged = engine.listing(root)
    now, lost = engine.polled(listed)               # a run record that cannot be read is named (NP17-03)
    _damaged(root, "run record(s)", damaged + lost, "unreadable_runs")
    running = [j for j in now if j.status == "running"]
    if running:
        ui.label("Running now").classes("text-lg")
        for job in running:
            with ui.row().classes("items-center gap-2"):
                ui.badge("running", color="blue")
                ui.link(job.title, f"/live?path={rel(root, job.folder)}")
    tree = studies.tree(root)
    with ui.row().classes("items-baseline gap-4 mt-2"):
        ui.label(f"{len(tree)} studies").classes("text-gray-600")
        ui.link("studies to revisit after updates", "/studies/revisit").classes("text-sm")
    lost_records = studies.unreadable(root)
    if lost_records:                             # V1-04: named, not hidden, and the rest still listed
        ui.label(f"{len(lost_records)} study record(s) could not be read and are not listed: "
                 + "; ".join(f"{rel(root, p)} ({why})" for p, why in lost_records[:5])
                 + ". Repair or move the study.json named to list its study again.") \
            .classes("text-sm text-orange-800").mark("unreadable_studies")
    tangled = studies.inconsistent(root)
    if tangled:                                  # CA-08: each study listed once, its links named
        ui.label(f"{len(tangled)} study record(s) have links to parents or children that loop or disagree; each "
                 "study is listed once: " + "; ".join(f"{rel(root, p)} ({why})" for p, why in tangled[:5])) \
            .classes("text-sm text-orange-800").mark("inconsistent_studies")
    _damaged(root, "run record(s)", engine.listing(root)[1], "unreadable_runs")
    if not tree:
        ui.label("No studies yet. Start with an example on the home page, or from Constrain a model, Signal best fits "
                 "or Explain a signal above.").classes("text-gray-500")
        _failed_runs(root)                          # listed with no study too (the owner, 2026-11-19)
        return
    from adroit.orchestrator import annotations as an, study_headline
    from adroit.ui.annotations import badges, filter_bar, values
    notes, damaged_notes = an.listing(root)
    _damaged(root, "annotation(s)", damaged_notes, "unreadable_annotations")
    # each study's facts and the version they are of, which its row shows: its record and result read as one
    # checked transaction (DC-01; the version handle)
    views = {s.folder: an.held_facts(root, s) for _, s in tree}
    facts = {folder: view[0] for folder, view in views.items()}
    bad_results = [f for f in facts.values() if f.damage]
    if bad_results:                              # CO-06: named, each study still listed
        ui.label(f"{len(bad_results)} stud{'y' if len(bad_results) == 1 else 'ies'}' result could not be read in full; "
                 "listed without what could not be read: " + "; ".join(
                     f"{rel(root, Path(f.folder) / 'result.json')} ({f.damage})" for f in bad_results[:5])
                 + ". Repair or move the result named; the calculation that reads it refuses it.") \
            .classes("text-sm text-orange-800").mark("unreadable_results")
    table = [(facts[s.folder], notes.get(facts[s.folder].key)) for _, s in tree]
    controls = filter_bar(table, lambda: rows.refresh())

    @ui.refreshable
    def rows() -> None:
        chosen = values(controls)
        active = any(v for v in chosen.values())
        keep = {f.folder for f, _ in an.select(table, **chosen)}
        for depth, listed_as in tree:
            if listed_as.folder not in keep:
                continue
            f, found = views[listed_as.folder]
            word = KIND_WORD.get(f.kind, f.kind)
            note = notes.get(f.key)
            title = f.title                                 # its version's (``study_headline.listed``; DC-01)
            with ui.row().classes("items-center gap-2 no-wrap").style(f"margin-left: {0 if active else depth * 28}px"):
                ui.badge(word, color=KIND_COLOUR.get(f.kind, "grey"))
                ui.link(note.label if note and note.label else title,
                        "/study?path=" + quote(rel(root, listed_as.folder), safe="/"))   # a name with & or # too
                from adroit.ui.deletion import confirm_study, delete_button
                delete_button(lambda folder=listed_as.folder: confirm_study(
                    root, Path(folder), lambda: ui.navigate.to("/studies")), "study")
                if note and note.label:
                    ui.label(title).classes("text-xs text-gray-500")
                badges(note)
                verdict = f.badge                           # the stored level, its certification beside it (CO-07)
                if verdict:
                    ui.badge(verdict, color=_colour(verdict)).props("outline")
                if found is None or found.record_state not in study_headline.SHOWN:   # another version's: not shown
                    ui.label("its record is of another version: its date and cost are not shown"
                             if found is not None and found.record_state == "other" else
                             "its last publication was interrupted: its date and cost are not shown"
                             if found is not None and found.record_state == "interrupted" else      # IC-01
                             "its record cannot be read with its result: its date and cost are not shown") \
                        .classes("text-orange-800 text-sm").mark("listed_record_of_another")
                    continue
                spent = list_cost(found)
                ui.label(when(f.created) + (f" · {spent}" if spent else "")) \
                    .classes("text-gray-500 text-sm")
    rows()
    lost = an.orphans(root)
    if lost:
        ui.label(f"{len(lost)} annotation(s) whose study is no longer here: {', '.join(lost[:5])}") \
            .classes("text-xs text-gray-500")
    _failed_runs(root)


def _damaged(root: Path | None, what: str, damaged: list, mark: str) -> None:
    """A listing's damaged records, named under it (``durable.summary``), or nothing; their paths relative to the
    runs folder ``root``, or in full (``None``: a library's)."""
    from adroit.core.durable import summary
    text = summary(damaged, what, relative=lambda p: _relative(root, p))
    if text:
        ui.label(text).classes("text-sm text-orange-800").mark(mark)


def _relative(root: Path | None, path: str) -> str:
    """A path under the runs root as the pages show it, else as it is."""
    if root is None:
        return path
    try:
        return rel(root, Path(path.split(" [")[0])) + (" [" + path.split(" [", 1)[1] if " [" in path else "")
    except ValueError:
        return path


def _failed_runs(root: Path) -> None:
    """Runs that failed, stopped at their budget or were cancelled without a study, each linked to its live view."""
    failed = [j for j in engine.jobs(root) if j.status in ("failed", "budget_stopped", "cancelled")
              and not (Path(j.folder) / studies.FILE).exists()]
    if failed:
        ui.label("Runs that ended without a study").classes("text-lg mt-4")
        from adroit.orchestrator.recovery import FORMS
        from adroit.ui.deletion import confirm_run, delete_button
        for job in failed:
            with ui.row().classes("items-center gap-2"):
                ui.badge(job.status, color=STATUS_COLOUR[job.status])
                ui.link(job.title, f"/live?path={rel(root, job.folder)}")
                if FORMS.get(job.kind):
                    ui.link("start over", FORMS[job.kind]).classes("text-sm")
                ui.link("what to do", "/activity").classes("text-sm")
                delete_button(lambda folder=job.folder: confirm_run(root, Path(folder),
                                                                    lambda: ui.navigate.to("/studies")), "run")



def _colour(words: str) -> str:
    from adroit.orchestrator import study_headline
    return study_headline.colour(words)


def live(root: Path, path: str) -> None:
    """A run's live view: status, time, cost, progress and log, refreshed every second, with Cancel; once it ends,
    what it made and the button that opens it where it is reviewed (``outcomes``: a model intake's draft is not a
    study, and its cost is read from its session's ledger; the owner's report of 2026-10-23)."""
    folder = inside(root, path)
    try:
        title = engine.load(folder).title
    except (OSError, ValueError) as error:           # named, not a server error (CA-07); its files are unchanged
        from adroit.core.durable import reason
        header("Run record unreadable", "This folder's run record cannot be read, so its run cannot be shown.")
        ui.label(f"{rel(root, folder / engine.JOB)}: {reason(error)}. Repair or move it; the run's other files are "
                 "unchanged.").classes("text-orange-800").mark("unreadable_run")
        return
    header(f"Run: {title}", "This run's progress, refreshed every second. When it finishes, the "
           "button below opens what it made; you can leave this page, and the run continues.")

    status = _status_row(folder)
    snap, result = _live_state(root, folder)
    _show_status(status, snap)
    shows = _live_parts(folder, snap, result)
    head = _part(_live_head, *shows[0])
    with ui.card().classes("w-full").mark("outcome"):
        words = _part(_outcome_words, *shows[1])
        actions = _part(_outcome_actions, *shows[2])
    tail = _part(_live_tail, *shows[3])

    def tick() -> None:
        """The status row updated in place, and each other part rebuilt only when what it shows has changed
        (the auditor's CO recheck, 2026-10-26: the whole view was rebuilt every second, so a button was replaced under a
        click, whose event the server then dropped for a button no longer there; under load, a finished intake's
        "Review model draft" was lost so, and a running one's Cancel could be). The outcome's actions are a part of
        their own: an intake's draft is written, and its button shown, while its job still runs, and the job's end a
        moment later (its process gone, its record final) rebuilds the words and the log, never the button."""
        snap, result = _live_state(root, folder)
        _show_status(status, snap)
        for part, shown in zip((head, words, actions, tail), _live_parts(folder, snap, result)):
            part(*shown)

    ui.timer(1.0, tick)


def _live_state(root: Path, folder: Path) -> tuple[dict, object]:
    """What a run's live view shows: its snapshot, what it made (``outcomes.outcome``), and its report as read against
    the result its cost was read from (``snap["live_report"]``, ``_live_report``): the result's version is taken
    before the snapshot and again after the report is read, and where they differ the report is withheld until it
    settles (the auditor's CZ recheck, DA-02, 2026-11-02: the page had shown A's budget-stop report, $0.10 committed,
    beside the cost of B, $0.20, published meanwhile)."""
    from adroit.evidence.build import version_now
    from adroit.ui import outcomes
    before = version_now(folder / "result.json")
    snap = engine.snapshot(folder)
    result = outcomes.outcome(root, folder, snap["job"])
    snap["live_report"] = _live_report(folder, result.output)
    if snap["live_report"][0] and version_now(folder / "result.json") != before:
        snap["live_report"] = ("moving", "")
    return snap, result


def _live_report(folder: Path, output: str) -> tuple[str, str]:
    """The run's report as its live view reads it: ("", "") where it shows none (a study's is on its study page), else
    how it reads and its text. Read once against the result beside it, read once (``bindings.read_report``): "bound"
    (that result's), "other" (another version's: withheld), "legacy" (it records no link to the result: written
    before ADROIT recorded one, shown as found), "found" (a run that saves no result: shown), "unchecked" (it records
    a result that cannot be read: shown, saying so); "moving" while its files change each time they are read."""
    from adroit.evidence.version import Unsettled, resolve
    if output in ("study", "none"):
        return "", ""
    try:                            # the result and its report read together (``evidence.version``)
        version = resolve(folder, presentation=True, evidence=False)
    except Unsettled:
        return "moving", ""
    held = version.result_sha256 or None
    found = version.report()
    if found.state == "unreadable":
        return "", ""
    if found.state == "absent":
        return "", ""
    if found.state == "other":
        return ("other", "") if held is not None else ("unchecked", found.text)
    if found.state == "interrupted":                          # IC-01: possibly an earlier publication's
        return "interrupted", ""
    if found.state == "unbound":
        return ("legacy" if held is not None else "found"), found.text
    return found.state, found.text


def _live_parts(folder: Path, snap: dict, result) -> tuple[tuple, ...]:
    """What each rebuilt part of the live view shows, the arguments of its renderer: its progress and Resume
    (``_live_head``), the outcome's words (``_outcome_words``) and actions (``_outcome_actions``), and the report and
    log (``_live_tail``). The status row (its badge, elapsed time and Cancel) is not among them: it is updated in place
    (``_show_status``)."""
    job = snap["job"]
    return ((folder, job.kind, job.status, snap.get("progress"), snap.get("progress_unreadable"),
             (folder / ".track1-checkpoint/manifest.json").exists()),
            (result, snap["cost"]),
            (result.primary, result.links),
            (folder, job, snap["log"], result.output, snap.get("live_report", ("", "")),
             snap.get("log_unreadable", "")))


def _live_key(*shown) -> str:
    """What a part of the live view shows, in one string: equal keys render the same part."""
    return repr(shown)


def _part(render, *shown):
    """``render(*shown)`` here, as one part of the live view, and the function that renders it again in place when
    what it shows has changed (``_live_key``); called with what it already shows, it leaves the part as it is."""
    part, key = ui.refreshable(render), {"shown": _live_key(*shown)}
    part(*shown)

    def update(*now) -> None:
        if _live_key(*now) != key["shown"]:
            key["shown"] = _live_key(*now)
            part.refresh(*now)
    return update


def _live_head(folder: Path, kind: str, status: str, progress, unreadable: str, resumable: bool) -> None:
    """A run's progress, why its progress record cannot be read (named, the view goes on: M3), and for an
    interrupted Track 1 run with a scientific checkpoint, Resume."""
    _progress(progress)
    if unreadable:
        ui.label(unreadable).classes("text-sm text-orange-800").mark("unreadable_progress")
    if kind == "track1" and status in ("failed", "cancelled") and resumable:
        def resume() -> None:
            try:
                engine.resume(folder)
                ui.notify("Resuming completed scientific checkpoints")
            except ValueError as error:
                ui.notify(str(error))
        ui.button("Resume constraining the model", on_click=resume)


LIVE_WITHHELD = {
    "other": "This run's report is of another version of its result (the result was replaced while the report was "
             "written, or since), so it is not shown as this run's summary; the cost above is read from the result "
             "now saved.",
    "moving": "This run's result was replaced while this page read it, so its report is not shown until it settles.",
    "interrupted": "This run's publication was interrupted while it wrote its parts, so the report beside its result "
                   "may be an earlier publication's; it is not shown. Run it again to publish it whole.",
}
LIVE_NOTES = {
    "legacy": "This report records no link to the run's result (it was written before ADROIT recorded one), so which "
              "version of the result it describes is not checked; it is shown as found.",
    "unchecked": "The run's result cannot be read, so which version of it this report describes is not checked; it is "
                 "shown as found.",
}


def _live_tail(folder: Path, job: engine.Job, log: list[str], output: str, report: tuple[str, str],
               unreadable: str = "") -> None:
    """A run's report (``report``: how it reads and its text, ``_live_report``), withheld, saying why, where it is of
    another version of the run's result or the result is being replaced (DA-02); and its command and log, or why its
    log cannot be read (``unreadable``, named: DO-02), never "no output yet" for one that cannot be read."""
    state, text = report
    if state in LIVE_WITHHELD:
        ui.label(LIVE_WITHHELD[state]).classes("text-orange-800").mark("live_report_withheld")
    elif state:
        with ui.expansion("The run's summary (report.md)").classes("w-full"):
            if state in LIVE_NOTES:
                ui.label(LIVE_NOTES[state]).classes("text-xs text-gray-600").mark("live_report_unchecked")
            from adroit.evidence.bindings import unbound
            ui.markdown(readable_report(unbound(text))).classes("w-full")
    with ui.expansion("The command and its log", value=job.status != "completed").classes("w-full"):
        ui.label("adroit " + " ".join(job.command)).classes("font-mono text-xs text-gray-500")
        if unreadable:
            ui.label(f"{unreadable[:1].upper()}{unreadable[1:]}: the rest of this page is read from the run's other "
                     "records.").classes("text-sm text-orange-800").mark("unreadable_log")
        ui.code("\n".join(log) or ("(its log cannot be read)" if unreadable else "(no output yet)")
                ).classes("w-full text-xs")


def _status_row(folder: Path) -> dict:
    """The run's status, its elapsed time and, while it runs, Cancel: made once and updated in place
    (``_show_status``), so that Cancel is never replaced under a click."""
    with ui.row().classes("items-center gap-4"):
        badge = ui.badge("").mark("job_status")
        elapsed = ui.label("").classes("text-gray-600")
        cancel = ui.button("Cancel", on_click=lambda: (engine.cancel(folder), ui.notify("cancelling"))) \
            .props("outline color=negative").mark("cancel_run")
    left = ui.label("").classes("text-sm text-orange-800").mark("calculation_left")
    return {"badge": badge, "elapsed": elapsed, "cancel": cancel, "left": left}


def _show_status(row: dict, snap: dict) -> None:
    """The status row (``_status_row``) as the run is now: Cancel while it runs, and while its calculation still runs
    after it has ended, which is named (``engine.left_running``; ID-01)."""
    from adroit.ui.style import seconds_text
    job = snap["job"]
    row["badge"].set_text(job.status)
    row["badge"].props(f"color={STATUS_COLOUR.get(job.status, 'blue')}")
    row["elapsed"].set_text(f"elapsed {seconds_text(snap['elapsed_s'])}")
    row["cancel"].set_visibility(job.status == "running" or bool(snap.get("left_running")))
    row["left"].set_text(snap.get("left_running", ""))
    row["left"].set_visibility(bool(snap.get("left_running")))


MARKS = {"done": "✓", "running": "▸", "failed": "✗"}


def _stage_list(progress) -> None:
    """The run's stages in order, each ticked as it finishes, the current one with its count (the owner, 2026-11-23:
    a sense of how far through a long run is). Only where the run declared its plan (Constrain a model)."""
    from adroit.orchestrator.track1 import STAGE_NAMES
    with ui.column().classes("gap-0").mark("stage_list"):
        for name in progress.plan:
            mark = progress.stages.get(name)
            state = mark.state if mark else "to come"
            count = f" · {mark.completed} of {mark.total}" if mark and mark.total else ""
            colour = {"done": "text-green-800", "running": "text-gray-900 font-medium", "failed": "text-red-700"}
            ui.label(f"{MARKS.get(state, '○')} {STAGE_NAMES.get(name, name)}{count}") \
                .classes(f"text-sm {colour.get(state, 'text-gray-500')}").mark(f"stage_{state.replace(' ', '_')}")


def _progress(progress) -> None:
    """A run's reported progress: its stages where it declared them, its phase, how far, and a bar."""
    if progress and progress.plan:
        _stage_list(progress)
    if progress:
        ui.label(f"{progress.phase}: {progress.completed} of {progress.total} · {progress.detail}")
        if progress.total:
            ui.linear_progress(value=min(progress.completed / progress.total, 1.0), show_value=False) \
                .classes("w-full max-w-xl")


def show_outcome(result, cost=None) -> None:
    """What a run made, in words, its cost (this run's, its session's, the cap) and its primary and other actions
    (``outcomes.Outcome``)."""
    with ui.card().classes("w-full").mark("outcome"):
        _outcome_words(result, cost)
        _outcome_actions(result.primary, result.links)


def _outcome_words(result, cost=None) -> None:
    """An outcome's headline, its sentence and its cost (``show_outcome``)."""
    from adroit.ui import outcomes
    ui.label(result.headline).classes("text-lg font-medium").mark("outcome_headline")
    if result.detail:
        ui.label(result.detail).classes("text-gray-700")
    for line in outcomes.cost_lines(cost) if cost is not None else []:
        ui.label(line).classes("text-sm text-gray-700").mark("cost")
    if cost is not None and cost.run_source:
        ui.label(f"read from {cost.run_source}").classes("text-xs text-gray-500")


def _outcome_actions(primary, links) -> None:
    """An outcome's primary action, a button that is a link the browser follows itself, without the server (the auditor's
    CO recheck), and its other actions (``show_outcome``)."""
    with ui.row().classes("items-center gap-3"):
        if primary:
            target = primary.target
            button = ui.button(primary.label, on_click=lambda: ui.navigate.to(target)) \
                .props("color=primary").mark("primary_action")
            button.props["href"] = target
        for link in links:
            ui.link(link.label, link.target)


def _links(root: Path, s: studies.Study) -> None:
    if s.parent:
        with ui.row().classes("items-center gap-2"):
            ui.label("from")
            ui.link(Path(s.parent).name, f"/study?path={rel(root, s.parent)}")
    if s.children:
        ui.label("Studies made from this one:").classes("mt-1")
        for child in s.children:
            ui.link(Path(child).name, f"/study?path={rel(root, child)}").classes("ml-4")


STUDY_PURPOSE = {
    "track1": "A model's parameter space: where it gives the observed relic density, and which constraints exclude "
              "it there.",
    "signal": "The interactions that best fit a search with events, ranked, with their global significance and what "
              "else constrains them.",
    "single_idea": "One model as the explanation of a signal: its best fit, its tension with null searches, and its "
                   "constraints around the fit.",
    "idea": "Models proposed or built from your input, each audited; approve the ones to constrain.",
}


def study(root: Path, path: str) -> None:
    """A study: a summary card (kind, verdict, cost, time, run again), its parent and children, the forms that
    continue it, and its report with plots."""
    folder = inside(root, path)
    if not (folder / studies.FILE).exists():
        not_a_study(root, folder, path)
        return
    from adroit.evidence.version import Unsettled, resolve
    # one version of the study: its result, evidence, record, report and figures read as one checked transaction
    # (the version handle, the owner, 2026-11-03), and everything the page shows and each action it offers is of it:
    # the badge, its certification, the points, the continuation panels (the auditor's CV recheck, CW-01; its CW recheck,
    # CX-02), the input history, the report and its figures (its CX recheck, CY-02, CY-03), the record's title, cost and
    # dates only where the record names that result (its version-identity audit, VI-01), and the identities the
    # downloads and the reanalyses require (VI-03, DC-04)
    try:
        found = resolve(folder, presentation=True)
    except Unsettled as error:
        header("This study is changing", "Its files changed each time this page read them together, so no version of "
               "it is shown. Reload the page when its run has finished writing.")
        ui.label(str(error)).classes("text-orange-800").mark("study_unsettled")
        ui.link("All studies", "/studies")
        return
    s = found.study()
    if s is None:                               # V1-04: said, with the file to repair, not an internal error
        header("Study record unreadable", "This folder's study record cannot be read, so its study is not shown.")
        ui.label(f"{rel(root, folder / studies.FILE)}: its study record is {found.record_state}. Repair or move the "
                 "file; the folder's other files are unchanged.").classes("text-orange-800").mark("unreadable_study")
        ui.link("All studies", "/studies")
        return
    read = found.snapshot()
    other = found.record_state in ("other", "interrupted")
    if found.record_state == "interrupted":                   # the auditor's portability audit, IC-01
        header("This study's last publication was interrupted", "Its publication stopped while it wrote its parts, so "
               "this folder's report and study record may be an earlier publication's: the record's title, cost and "
               "dates and the report are not shown beside its result. Run the study again to publish it whole.")
    elif other:
        header("This study was replaced while it was read", "This folder's study record describes another version of its "
               "result than the one read here (one was replaced since the other was written), so the record's title, "
               "cost and dates are not shown beside it. Reload the page for the version now saved.")
    else:
        header(s.title, STUDY_PURPOSE.get(s.kind, "A saved analysis and its report.") +
               " Its inputs are pinned: later data need a new run.")
        ui.label("This analysis has been successfully saved in Studies.").classes("text-green-800") \
            .mark("saved_in_studies")                                  # the owner's JU1, 2026-11-16
    _summary(root, found, s, read)
    if not other:
        _links(root, s)
    damage = result_damage(read, s.kind)
    if damage:              # named; what reads the result is withheld, the rest of the page kept (CR-06, CT-04)
        _result_withheld(root, folder, path, damage)
    elif s.kind in ("signal", "idea"):
        (promote_panel if s.kind == "signal" else approve_panel)(root, found)
    from adroit.ui.exports import download_menu
    download_menu(found)
    from adroit.ui.annotations import annotation_card
    annotation_card(root, folder)
    if not other:
        from adroit.ui.revisit import study_updates
        study_updates(root, found)
    from adroit.ui.points import KINDS, points_panel
    if s.kind in KINDS and not damage:
        points_panel(root, found)
    study_report(root, found)
    from adroit.ui.deletion import confirm_study
    with ui.row().classes("gap-3 mt-4"):
        ui.button("Home", on_click=lambda: ui.navigate.to("/")).mark("home")                 # the owner's JU1
        ui.button("Delete this study", on_click=lambda: confirm_study(
            root, folder, lambda: ui.navigate.to("/studies"))).props("outline color=negative").mark("delete_this_study")


def study_report(root: Path, found) -> None:
    """The study's report and its figures, as read with its result (``found``, its version): shown, with its figures as
    read and checked against its binding, where it is bound to that result; withheld, saying why, where it is bound to
    another version; else shown as found, saying so, where it records no binding (written before ADROIT recorded one)
    or the result cannot be read (``evidence.bindings``; the auditor's CX recheck, CY-03, 2026-11-01: a page holding A had
    shown B's EXCLUDED report under A's VIABLE badge). Read in one transaction with the result, a report recording no
    binding is of the files as they were together (the version handle)."""
    from adroit.evidence.bindings import unbound
    report = found.report()
    folder = found.folder
    if report.state == "absent":
        return
    held = found.result_sha256 or None
    with ui.column().classes("w-full gap-1").mark("report"):
        if report.state == "bound":
            _headline_and_details(unbound(report.text), lambda part: _bound_figures(part, found))
            return
        if report.state == "interrupted":                     # IC-01
            ui.label("The report beside this result may be an earlier publication's: the study's last publication was "
                     "interrupted while it wrote its parts. It is not shown; run the study again to publish it "
                     "whole.").classes("text-orange-800").mark("report_interrupted")
            return
        if report.state == "other" and held is not None:
            ui.label("The report beside this result is of another version of it: the study was replaced while this "
                     "page was read. It is not shown; reload the page for the version now saved, with its own "
                     "report.").classes("text-orange-800").mark("report_of_another")
            return
        if report.state == "unreadable":
            ui.label("The report beside this result cannot be read; it is not shown.").classes("text-orange-800") \
                .mark("report_unreadable")
            return
        ui.label("This report records no link to the result above (it was written before ADROIT recorded one), so "
                 "which version of the result it describes is not checked; it is shown as found." if held is not None
                 else "The result cannot be read, so which version of it this report describes is not checked; it is "
                 "shown as found.").classes("text-xs text-gray-600").mark("report_unchecked")
        _headline_and_details(unbound(report.text), lambda part: with_files(part, root, folder))


def _headline_and_details(text: str, figures) -> None:
    """A report on its study's page (the owner's JU1, 2026-11-16: "a page with headline statements"): its opening, down
    to its plots, shown; the rest under "See details", closed; on the page the checklist's "to be built" column is left
    out (it is for those building ADROIT; the report file keeps it). ``figures`` embeds a part's figures."""
    head, rest = split_at_figures(without_build_column(text))
    ui.markdown(readable_report(figures(head))).classes("w-full")
    if rest.strip():
        with ui.expansion("See details").classes("w-full").mark("report_details"):
            ui.markdown(readable_report(figures(rest))).classes("w-full")


FIGURE_LINE = re.compile(r"^!\[[^\]]*\]\([^)]+\)\s*$")
BUILD_HEAD = "| check | status | for this model | to be built |"


def split_at_figures(text: str) -> tuple[str, str]:
    """``text`` cut after its first run of figure lines (``![…](…)``, blank lines between them allowed): (the opening with
    the figures, the rest); with no figure, (the whole, "")."""
    lines = text.split("\n")
    first = next((i for i, line in enumerate(lines) if FIGURE_LINE.match(line)), None)
    if first is None:
        return text, ""
    end = first
    for i in range(first + 1, len(lines)):
        if FIGURE_LINE.match(lines[i]):
            end = i
        elif lines[i].strip():
            break
    return "\n".join(lines[:end + 1]) + "\n", "\n".join(lines[end + 1:])


def without_build_column(text: str) -> str:
    """``text`` with the viability checklist's last column ("to be built") left out of each of its tables."""
    out, inside = [], False
    for line in text.split("\n"):
        if line.strip() == BUILD_HEAD:
            inside = True
        elif inside and not line.startswith("|"):
            inside = False
        if inside:
            body = line.rstrip().removesuffix("|").rstrip()
            if set(body.replace("|", "")) <= {"-", " ", ":"}:            # the separator row
                line = body[:body.rfind("|")] + "|"
            else:
                cut = body.rfind(" | ")
                line = (body[:cut] if cut > 0 else body) + " |"
        out.append(line)
    return "\n".join(out)


def _bound_figures(text: str, found) -> str:
    """A bound report's figures, each embedded from its bytes as read with it (``found``, its version), where they have
    the digest its binding names; a figure replaced since (or never named) is said to be withheld, never served from
    the folder later."""
    import base64
    from adroit.evidence.bindings import FIGURE

    def embed(match: re.Match) -> str:
        data = found.figure(match.group(1))
        if data is None:
            return f"*(The figure {match.group(1)} is not the one this report was written with; it is not shown.)*"
        alt = match.group(0)[2:match.group(0).index("](")]
        return f"![{alt}](data:image/png;base64,{base64.b64encode(data).decode()})"
    return FIGURE.sub(embed, text)


TYPED = {"signal", "idea"}          # the kinds whose study page validates its result for a panel
MISSING = "result.json is missing"


def _result_withheld(root: Path, folder: Path, path: str, damage: str) -> None:
    """A study whose result cannot be read: why, with what depends on it withheld; a missing result whose run is still
    going is said to be still going, with its live view (the auditor's CS recheck, CT-04, 2026-10-28)."""
    if damage == MISSING and _running(folder):
        ui.label("Its run is still going, and has not written its result yet; what depends on the result (promotion, "
                 "approval, the points) appears when it has.").classes("text-gray-700").mark("result_pending")
        ui.link("the run's live view and log", f"/live?path={path}").classes("text-sm")
        return
    fix = ("its run did not leave it, or it was moved; restore it, or run the study again"
           if damage == MISSING else "repair or move the file")
    ui.label(f"{damage}. What depends on it (promotion, approval, the points) is not shown; {fix}. The study's "
             "other files are unchanged.").classes("text-orange-800").mark("damaged_result")


def _running(folder: Path) -> bool:
    """Whether the folder's job says its run is still going (a job record that cannot be read says nothing)."""
    if not (folder / engine.JOB).exists():
        return False
    try:
        return engine.poll(folder).status == "running"
    except (OSError, ValueError):
        return False


def result_damage(found, kind: str) -> str:
    """Why a study's saved result, as its page read it (``found``, a ``study_headline.Snapshot``: the page's one read),
    cannot be read as one, or "" (readable): missing (the auditor's CS recheck, CT-04, 2026-10-28: a study whose result was
    gone had opened as a server error, its approval reading the absent file); present but not a JSON object (``null``,
    a list, a number, a torn file); or, for a kind whose page acts on it (``TYPED``: promotion, approval), not that
    kind's result. The auditor's CO recheck, CR-06 (2026-10-26): such a result, selected, had made its study's page a server
    error, though the Studies list named it. Its CW recheck, CX-02 (2026-10-31): checked in one read and acted on in
    another, a result replaced between them had made the page a server error."""
    from adroit.core.durable import parse_object, reason
    if found.content is None:
        return f"result.json {found.damage.removeprefix('its result ')}" if found.damage else MISSING
    data, why = parse_object(found.content)
    if why:
        return f"result.json {why}"
    if kind not in TYPED:
        return ""
    from adroit.evidence.results import result_type
    try:
        result_type(kind).model_validate(data)
    except (ValueError, TypeError) as error:
        return f"result.json is not {'a signal' if kind == 'signal' else 'an idea'} study's result ({reason(error)})"
    return ""


def not_a_study(root: Path, folder: Path, path: str) -> None:
    """A ``/study`` link to a folder without a study record (an old "Open the results" link to a model intake, say):
    what the folder holds, with the button that opens it where it is reviewed; a run still going is said to be going
    only if its job says so (the owner's report of 2026-10-23)."""
    from adroit.ui import outcomes
    if (folder / engine.JOB).exists():
        job = engine.poll(folder)
        result = outcomes.outcome(root, folder, job)
        header(result.headline, "This folder holds no study record: it is not a physics study. Its output is reviewed "
               "on the page the button opens.")
        show_outcome(result, outcomes.cost(folder, job))
        ui.link("the run's live view and log", f"/live?path={path}").classes("text-sm")
        return
    draft = outcomes.draft_outside_job(folder)
    if draft is not None:
        header(draft.headline, "This folder holds a model-intake draft, not a physics study.")
        show_outcome(draft)
        return
    header("Not a study", "This folder holds no study record, and no workbench run is recorded in it.")
    ui.label(f"{path} has no study record.")


def study_cost(found) -> str:
    """A study's cost on its card, of its version (``evidence.version``: its record as read with its result), as
    ``accounting.study_cost`` reads it: its run's, from the run's own records, where the study is a workbench run's
    folder (settled, reserved whose bill is not known, or not available, and why); else the record's settled dollars,
    at the precision cents need (a $0.0024 study had read "cost $0.00"; WA-03). The run in its folder is the study's
    only where it is the run its record names (``Version.publisher``; DC-01) throughout its reading, the record's
    dollars and result those of the version (``accounting.held_cost``; DD-02): live accounting, bound to its attempt."""
    from adroit.core.durable import absent
    from adroit.orchestrator import accounting
    c = accounting.held_cost(found)
    if not absent(Path(found.folder) / accounting.JOB):     # a run record that cannot be read is said so (DN-01)
        return "cost: " + accounting.run_line(c).removeprefix("This run: ")
    return f"cost {accounting.usd(c.run_usd)} settled" if c.run_usd else "no settled cost recorded"


def list_cost(found) -> str:
    """A study's cost in its line in Studies, the card's figure in a few words (``accounting.short_line``; the
    combined audit's V1-02, 2026-10-24: the list had shown a run's settled dollars alone, its reserved ones left
    out); "" where nothing was spent or recorded. Of its version's record and the run it names (``study_cost``)."""
    from adroit.orchestrator import accounting
    c = accounting.held_cost(found)
    return "" if not c.paid and c.run_usd is None and not c.unsettled else accounting.short_line(c)


def _halo_line(version, kind: str) -> None:
    """The study's halo (``evidence.halo``) of the version this page holds: as its run resolved it, or as read from an
    older result's request (said so); nothing is calculated."""
    if kind not in ("track1", "signal", "single_idea"):
        return
    from adroit.evidence.halo import line
    try:
        snapshot = version.saved()
    except (OSError, ValueError):
        return
    text = line(snapshot.workflow, snapshot.result)
    if text:
        ui.label(text).classes("text-sm text-gray-700").mark("study_halo")


def _summary(root: Path, version, s: studies.Study, read) -> None:
    """The study at a glance, of its version (``version``): its kind, its verdict (Track 1, Explain) and its
    certification, both of its result (``read``, its ``study_headline.Snapshot``), when it ran and how long, its cost,
    and one "Run again" menu, whose reanalyses require that version: its result's digest and its evidence's identity
    (the auditor's CX recheck, CY-03; its version-identity audit, VI-03). When it ran and its cost are the study record's:
    shown where the record names this result, as found (saying so) where it names none, and not shown where it names
    another (``Version.record_state``: VI-01)."""
    from urllib.parse import urlencode
    from adroit.orchestrator.study_headline import headline_from
    from adroit.ui.style import duration, show_when
    folder, held, binding = version.folder, version.result_sha256, version.record_state
    evidence = version.token().evidence
    found = headline_from(read)
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-3"):
            ui.badge(KIND_WORD.get(s.kind, s.kind), color=KIND_COLOUR.get(s.kind, "grey"))
            if found.words:
                ui.label(found.words).classes(f"text-xl font-bold text-{_colour(found.words)}-700") \
                    .mark("study_verdict")
            if binding not in ("other", "interrupted"):
                ui.label(study_cost(version)).classes("text-gray-600").mark("study_cost")
        _certification_line(found, read.data)
        _halo_line(version, s.kind)
        if held:                # which version this page holds: the study as saved when it was opened
            ui.label(f"as saved when this page was opened: result SHA-256 {held[:12]}…") \
                .classes("text-xs font-mono text-gray-500").mark("study_version")
        if binding == "other":
            ui.label("Its study record describes another version of this result, so when it ran and its cost are not "
                     "shown.").classes("text-orange-800").mark("study_record_of_another")
        elif binding == "interrupted":                        # IC-01
            ui.label("Its last publication was interrupted, so its study record may be an earlier publication's: when "
                     "it ran and its cost are not shown.").classes("text-orange-800").mark("study_record_interrupted")
        else:
            show_when("calculated", s.calculation_completed_at or s.created)
            took = duration(s.calculation_started_at, s.calculation_completed_at)
            if took:
                ui.label(f"took {took}").classes("text-gray-600")
        if binding == "unbound" and read.content is not None:
            ui.label("Its study record was written before ADROIT tied a record to its result, so its title, cost and "
                     "dates are shown as found, not checked against this result.").classes("text-xs text-gray-600") \
                .mark("study_record_unchecked")
        if s.kind in ('track1', 'signal', 'single_idea'):
            source = {'source': str(folder / 'result.json'), **({'sha256': held} if held else {}),
                      **({'evidence': evidence} if held and evidence else {})}
            with ui.dropdown_button("Run again", auto_close=True).props("outline"):
                ui.item("With the same inputs (review, then run)",
                        on_click=lambda: ui.navigate.to('/reanalyse?' + urlencode(source)))
                ui.item("As Constrain a model", on_click=lambda: ui.navigate.to(
                    '/reanalyse?' + urlencode({**source, 'target': 'track1'})))
                ui.item("As Signal best fits", on_click=lambda: ui.navigate.to(
                    '/reanalyse?' + urlencode({**source, 'target': 'signal'})))


def readable_report(text: str) -> str:
    """A report's Markdown for the page: its headings one level down (the page has the title), its chronology as a
    short list, and the underscores of parameter names kept literal (m_S, λ_hs had read as italics)."""
    text = re.sub(r"\A\s*# [^\n]*\n", "", text)            # the report's own title: the page shows it
    text = re.sub(r"^(#{1,5}) ", lambda m: "#" + m.group(1) + " ", text, flags=re.M)
    text = re.sub(r"<!-- adroit-chronology -->\n(.*?)<!-- /adroit-chronology -->",
                  lambda m: "".join(f"- {line}\n" for line in m.group(1).strip().splitlines() if line.strip()),
                  text, flags=re.S)
    text = text.replace("fixed at ; ", "")
    parts = re.split(r"(```.*?```|`[^`\n]*`|\]\([^)]*\)|<[^>]+>)", text, flags=re.S)   # code and link targets kept
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"(?<=[A-Za-zλχμ])_(?=[A-Za-z0-9{])", r"\\_", parts[i])
    return "".join(parts)


AI_NOTE = "AI can make mistakes."


def model_select(label: str = "language model (paid)", choices: dict | None = None, value: str = "",
                 default: str = ""):
    """The primary paid model, from the one list of choices (``core.pricing.PRIMARY_MODELS``), with a small reminder
    under it that its answers can be wrong: every live call in the workbench chooses its model here (the owner,
    2026-10-16). ``choices`` and ``default``: another list and the system's default of it (the record check's models,
    ``CHECKER_MODELS``); ``value``: the choice it opens with (a remembered one), which never becomes the default the
    auto-approve setting reads (``auto_tick``; the auditor's post-review audit, PR-01)."""
    from adroit.core.pricing import DEFAULT_PRIMARY, PRIMARY_MODELS
    default = default or (DEFAULT_PRIMARY if choices is None else value)
    select = ui.select(choices or PRIMARY_MODELS, value=value or default, label=label).classes("w-72")
    select.system_default = default
    ui.label(AI_NOTE).classes("text-xs text-gray-500").mark("ai-note")
    return select


def cap_controls(budgets, session: str, reload: str) -> None:
    """Raise a paid session's cap: an amount above the current one and an explicit approval; the change is kept in
    the session and its paid ledger (``Intake.raise_cap``), and the page reloads at ``reload``."""
    current = budgets.session(session).budget
    with ui.row().classes("items-center gap-3"):
        amount = ui.number("raise the session cap to ($)", value=current, min=0.0, max=forms.CAP_USD, step=0.1).classes("w-56")
        confirm = ui.checkbox("I approve the higher cap")

        def raise_cap() -> None:
            try:
                budgets.raise_cap(session, float(amount.value or 0), confirmed=bool(confirm.value),
                                  reason="raised from the workbench")
            except (ValueError, OSError) as error:
                ui.notify(str(error))
                return
            ui.notify(f"cap raised to ${float(amount.value):.2f} and recorded")
            ui.navigate.to(reload)

        ui.button("Raise cap", on_click=raise_cap).mark("raise_cap")


def auto_tick(confirm, models=()):
    """Tick ``confirm`` for the person where the auto-approve setting is on (``core.workbench_settings``) and each of
    ``models`` (the page's model choices) holds the system's default (``model_select``'s ``system_default``, else the
    choice the select was made with); with another model chosen it is unticked again. A box the person has clicked is
    theirs from then on. Without ``models`` nothing is ticked. Returns a function giving how the box is ticked now:
    "auto" (by the setting), "click" (by the person) or "". Call it before reading the box: a box the setting ticked is
    approved only if the setting, read again then, still applies to the models chosen then; otherwise it is unticked
    and approves nothing (the auditor's post-review audit, PR-03: the setting switched off or damaged while a page was open
    had left its box approving)."""
    from adroit.core.workbench_settings import auto_approve
    pairs = [(select, getattr(select, "system_default", select.value)) for select in models]
    state = {"auto": False, "setting": False, "touched": False}
    note = ui.label("").classes("text-xs text-gray-500").mark("auto_ticked")

    def defaults() -> bool:
        return bool(pairs) and all(select.value == default for select, default in pairs)

    def set_box(on: bool, text: str) -> None:
        state["setting"] = True
        try:
            confirm.value = on
        finally:
            state["setting"] = False
        state["auto"], note.text = on, text

    def apply() -> None:
        if state["touched"] or not pairs:
            return
        if auto_approve():
            set_box(defaults(), AUTO_TICKED if defaults() else "")
        elif state["auto"]:
            set_box(False, "")

    def clicked(_event) -> None:
        if not state["setting"]:
            state["touched"], state["auto"], note.text = True, False, ""

    def how() -> str:
        if state["auto"] and confirm.value and not (auto_approve() and defaults()):
            set_box(False, "the auto-approve setting no longer applies here: tick the box yourself")
        if not confirm.value:
            return ""
        return "auto" if state["auto"] else "click"

    confirm.on_value_change(clicked)
    for select, _ in pairs:
        select.on_value_change(lambda _event: apply())
    apply()
    return how


def budget_form(label: str = "the most this run may spend ($)", models=()):
    """A typed budget gate: an amount and a confirmation, ticked for the person by the auto-approve setting while
    ``models`` (the page's model choices) hold their defaults (``auto_tick``). Returns a function giving the check,
    which says how the box was ticked (``BudgetCheck.approval``)."""
    from adroit.ui.style import hint
    with ui.row().classes("items-center gap-3"):
        amount = hint(ui.number(label, value=1.0, min=0.0, max=forms.CAP_USD, step=0.5),
                      "a hard cap: nothing is sent that could exceed it; a run usually settles well below")
        confirm = ui.checkbox("I approve this spend")
        how = auto_tick(confirm, models)
    note = ui.label("").classes("text-sm text-gray-600")

    def check() -> forms.BudgetCheck:
        approval = how()                 # first: a box the setting ticked is unticked if it no longer applies (PR-03)
        result = forms.check_budget(amount.value, confirm.value)
        note.text = result.message
        return result.model_copy(update={"approval": approval}) if result.ok else result

    return check


# the candidate's parameter-goodness-of-fit p-value (χ²_PG, combination.Combination.p_pg): how well the signal search
# and the searches that saw nothing agree at the candidate's joint best fit; not a significance (the workflow audit's
# WA-02, 2026-10-24: it had been headed "global p", and p ≈ 1 read as no signal beside a global p of 0.003)
PG_HEADING = "compatibility with the null searches (p of χ²_PG)"


def global_significance(result) -> str:
    """The search's global significance, once, for the whole ranking: the look-elsewhere-corrected p and Z of the
    largest local excess over every candidate tried, by its method (``SignalResult.global_*``), as the report states
    it; not any one candidate's."""
    p = result.global_p_closed_form if result.global_p_closed_form is not None else result.global_p_toys
    method = result.global_method or "one-event closed form"
    from adroit.orchestrator.signal import significance_parts
    z, shown = significance_parts(result.global_z, p, result.global_toys, result.global_p_interval, '.2g')   # PT-03
    text = (f"Global significance of the largest local excess, over every candidate tried: {z} "
            f"({shown}, {method}). It belongs to the search, not to any one candidate. In the table, the "
            "compatibility p is each candidate's agreement between this search and the null searches (high is "
            "good); it is not a significance.")
    scan, search = getattr(result, "halo_scan", None), getattr(result, "agent_search", None)
    if search is None and scan is None:
        return text
    # one declared scope first, the widest searched: the agent-led search, else the halo models compared (the auditor's
    # post-review recheck, PS-02: the fixed scan's had been shown as over "every candidate tried")
    widest = search if search is not None else scan
    where = ("everything searched and tried, the agent-led search's variants included" if search is not None else
             f"every candidate at every halo model compared ({', '.join(r.label for r in scan.runs)})")
    z_widest, shown_widest = significance_parts(widest.global_z, widest.global_p_toys, widest.global_toys,
                                                widest.global_p_interval, '.2g')
    first = f" at {scan.runs[0].label}" if scan is not None else ""
    return (f"Global significance over {where}: {z_widest} ({shown_widest}; {widest.global_method}). "
            f"The candidates below, and promotion, are of the fixed scan{first}, over which alone: "
            f"{z} ({shown}). In the table, the compatibility p is each candidate's agreement "
            "between this search and the null searches (high is good); it is not a significance.")


def promote_panel(root: Path, version) -> None:
    """Recursion: promote a Path 2 candidate, or its degeneracy class, to studies. Of the page's version
    (``version``): the candidates shown are of its result, and Promote acts on it alone (its digest goes with the
    command, which refuses another version: the auditor's CX recheck, CY-02, 2026-11-01). A promotion is made of the parent's
    result alone, its candidates; its record names that digest."""
    from adroit.orchestrator.signal import SignalResult
    folder, held = version.folder, version.result_sha256
    result = SignalResult.model_validate_json(version.content)
    ui.label("Promote a candidate to studies (recursion)").classes("text-lg mt-4")
    ui.label("Each candidate is an interaction (operator, then @ its mass in GeV). Promoting one builds the models that "
             "complete it and constrains each as its own study, listed under this one.").classes("text-sm text-gray-600")
    ui.label(global_significance(result)).classes("text-sm").mark("global_significance")
    entries = [e for e in result.tournament.ranking if e.label in result.classes][:12]
    rows = [{"label": e.label, "class": result.classes[e.label], "z": f"{e.z_signal:.2f}",
             "p_pg": f"{e.p_pg:.2g}", "constraints": e.complementary,
             'eligibility':result.eligibility[e.label].status if e.label in result.eligibility else 'legacy unassessed'} for e in entries]
    headers = {"label": "candidate (operator @ mass)", "class": "degeneracy class", "z": "local significance z",
               "p_pg": PG_HEADING, "constraints": "other constraints", "eligibility": "physical point"}
    shared = {k for k in ("constraints", "eligibility") if rows and len({r[k] for r in rows}) == 1}
    for k in sorted(shared):                         # a column that says the same on every row is said once
        ui.label(f"{headers[k].capitalize()}, every candidate: {rows[0][k]}").classes("text-sm text-gray-600")
    ui.table(columns=[{"name": k, "label": v, "field": k, "align": "left"} for k, v in headers.items()
                      if k not in shared], rows=rows, row_key="label").classes("w-full")
    which = ui.select({**{e.label: e.label for e in entries},
                       **{f"class:{c}": f"class {c} (every member)" for c in sorted({r['class'] for r in rows})}},
                      label="candidate or class").classes("w-72")
    with ui.row().classes("items-center gap-3"):          # each child study's size, as the command line takes it
        from adroit.ui.style import hint
        toys = hint(ui.number("background-only simulations per child study", value=20_000, min=100, step=1000,
                              format="%d"), "each promoted model's study runs its own, for its global significance") \
            .classes("w-80")
        from adroit.orchestrator.single_idea import grid_range
        low, high = grid_range()                          # what a child accepts: no size it would refuse
        grid = ui.number("each child's Track 1 plane: n × n", value=16, min=low, max=high,
                         format="%d").classes("w-56")
        masses = ui.number("masses per candidate", value=9, min=1, max=50, format="%d").classes("w-44")
    uv = ui.checkbox("also ask the model builder for completions (paid)")
    excluded_followup=ui.checkbox('Explicitly follow alternative branches of excluded fitted points',value=False)
    with ui.column().bind_visibility_from(uv, "value"):
        builder = model_select("the model builder (paid)")
        check = budget_form(models=(builder,))

    def go() -> None:
        if not which.value:
            ui.notify("choose a candidate or a class")
            return
        launch_promotion(root, folder, which.value, uv.value, check,include_excluded=excluded_followup.value,
                         model=builder.value, size={"toys": int(toys.value or 20_000), "grid": int(grid.value or 16),
                                                    "mass_points": int(masses.value or 9)}, parent_sha256=held)

    ui.button("Promote", on_click=submission.once(go)).classes("mt-2")


def launch_promotion(root: Path, folder: Path, which: str, uv: bool, check,include_excluded:bool=False,
                     model: str = "", size: dict | None = None, parent_sha256: str = "") -> None:
    """Start ``adroit promote`` on one candidate or class, each child of the ``size`` given (toys, grid, mass_points;
    the command line's defaults otherwise); with the model builder only after the budget gate. ``parent_sha256``: the
    version of the result the choice was made on; another is refused here, and again by the command when it reads the
    result (``promote.parent_result``), before anything is reserved or computed."""
    budget, approval = 0.0, ""
    if uv:
        verdict = check()
        if not verdict.ok:
            ui.notify(verdict.message)
            return
        budget, approval = verdict.amount, verdict.approval
    if parent_sha256:
        from adroit.orchestrator.promote import ParentChanged, parent_result
        try:
            parent_result(folder, parent_sha256)
        except (ParentChanged, ValueError, OSError) as error:
            ui.notify(str(error) if isinstance(error, ParentChanged) else
                      f"the parent study's result cannot be read now ({error}); nothing was promoted")
            return
    job_folder = forms.new_folder(folder / "children", "promotion", which)
    command=forms.promote_command(folder,[which],budget=budget,model=model,parent_sha256=parent_sha256,**(size or {}))
    if include_excluded:
        command+=['--include-excluded']
    job = engine.launch(command, job_folder, f"promote {which}",
                        confirmed_budget=budget, approval=approval)
    submission.go(f"/live?path={rel(root, job.folder)}")


def _approval_row(m: ModelResult) -> dict:
    """One model's approval controls and its live review: the selected model and its scan setup."""
    from adroit.orchestrator.model_approval import select_model
    from adroit.parameter_space.classify import Unsupported
    state={}
    with ui.column().classes('w-full'):
        box=ui.checkbox(m.spec.name,value=forms.approvable(m))
        save_catalog=ui.checkbox(f'Save {m.spec.name} in my personal model library',value=True)
        completion=ui.checkbox(f"Use generated general completion for {m.spec.name} (changes model)",value=False) \
            if m.source=='lagrangian' and m.general is not None else None
        with ui.row():
            x=ui.input(f"{m.spec.name}: x axis",placeholder='model-specific default')
            y=ui.input(f"{m.spec.name}: y axis",placeholder='model-specific default')
            ratio=ui.number(f"{m.spec.name}: mediator mass ratio (0: fixed independently)",value=0,min=0)
        from adroit.ui.halo import halo_section
        halo=halo_section("track1",mark=f"approve-halo-{m.spec.name}")

        @ui.refreshable
        def details():
            state.clear()
            try:
                selected,approval=select_model(m,general_completion=bool(completion and completion.value))
                from adroit.ui.model_library import usable_status
                if not usable_status(selected):     # the owner, 2026-11-21: only a model that can run is constrained
                    state.clear()
                    box.value=False
                    box.disable()
                    ui.label('Complete it in the model library (Create or refine a model, a typed model with the '
                             'missing values, $0) to constrain it.').classes('text-sm text-gray-700')
                    return
                box.enable()
                ui.badge('valid',color='green')
                ui.label('Supplied Lagrangian preserved' if approval.choice=='supplied' else
                         'Generated general completion selected' if approval.choice=='general_completion' else
                         'Model generated from the reviewed field content')
                from adroit.ui.typeset import show_model
                show_model(selected)
                with ui.expansion('The model data (YAML) and the changes').classes('w-full'):
                    ui.code(yaml.safe_dump(selected.model_dump(mode='json'),sort_keys=False,allow_unicode=True),language='yaml')
                    if approval.changes:
                        ui.code('\n'.join(approval.changes))
                state.update(spec=selected,approval=approval)
                try:
                    _,setup,token=forms.review_scan(yaml.safe_dump(selected.model_dump(mode='json')),
                        x.value,y.value,float(ratio.value or 0))
                    state.update(setup=setup,token=token)
                    ui.label('Scan setup: active coordinates, fixed values and parameter relations')
                    ui.code(yaml.safe_dump(setup.model_dump(mode='json'),sort_keys=False,allow_unicode=True),language='yaml')
                except Unsupported as error:
                    state.update(setup=None,unsupported=True)
                    ui.label(f"No supported numerical scan: {error}. Constraining the model will report the limitation.")
            except (ValueError,KeyError,TypeError,yaml.YAMLError) as error:
                state.clear()
                ui.label(str(error)).classes('text-red-700')
                box.disable()

        details()
        for element in (x,y,ratio,*([completion] if completion else [])):
            element.on_value_change(lambda _:details.refresh())
    return {'box':box,'state':state,'x':x,'y':y,'ratio':ratio,'save_catalog':save_catalog,'halo':halo}


def _approved_run(folder: Path, row: dict, source: bytes | None = None) -> tuple[list[str], Path, str]:
    """Write one reviewed model's approval (and save it in the library if asked, with ``source``, the bytes of the idea
    study's result the model was reviewed from, as its source: never the file read again; the auditor's CX recheck,
    2026-11-01); its Track 1 command."""
    from adroit.orchestrator.model_approval import write_approved
    from adroit.orchestrator.runs import slug
    state=row['state']
    spec,approval=state['spec'],state['approval']
    if not state.get('unsupported'):
        _,_,token=forms.review_scan(yaml.safe_dump(spec.model_dump(mode='json')),
            row['x'].value,row['y'].value,float(row['ratio'].value or 0))
        if token!=state.get('token'):
            raise ValueError('scan setup changed; review its current values')
    setup=state.get('setup')
    path=folder/'approved'/f'{slug(spec.name)}_{approval.model_sha256[:12]}_{approval.choice}.yaml'
    write_approved(path,spec,approval)
    if row['save_catalog'].value:
        from adroit.library.personal import Catalog
        from adroit.model_building.tex import render
        catalog=Catalog()
        idea=(catalog.asset_bytes('result.json',source,'idea_source') if source is not None
              else catalog.asset(folder/'result.json','idea_source'))
        catalog.save(spec,approval,tex=render(spec),sources=[catalog.asset(path),idea],
                     provenance={'origin':'explicit model approval in an idea study','study':str(folder)})
    out=forms.new_folder(folder/'children','track1',spec.name)
    command=forms.track1_command(path,out,forms.axis_text(setup.x) if setup else '',
        forms.axis_text(setup.y) if setup else '',parent=folder,
        approved_model_hash=approval.model_sha256,mediator_ratio=float(row['ratio'].value or 0),
        **(row['halo']() if 'halo' in row else {}))
    if setup:
        command+=['--reviewed-scan-hash',state['token']]
    return command,out,spec.name


def approve_panel(root: Path, version) -> None:
    """Review the exact selected model and scan plane; completion is a separate choice. Of the page's version
    (``version``): the models offered are of its result, and the approval is bound to those bytes, refused where the
    study's result is another version when it is approved (its digest, ``evidence.version.Token``)."""
    from adroit.evidence.version import Changed, Token, resolve
    from adroit.orchestrator.ideas import IdeaResult
    folder, source, source_hash = version.folder, version.content, version.result_sha256
    result = IdeaResult.model_validate_json(source)
    if not result.models:
        return
    ui.label("Approve models to constrain").classes("text-lg mt-4")
    rows=[]

    for m in result.models:
        rows.append(_approval_row(m))

    def go() -> None:
        chosen=[r for r in rows if r['box'].value and r['state']]
        if not chosen:
            ui.notify("tick at least one valid model")
            return
        prepared=[]
        try:
            try:
                resolve(Token(str(version.path),result=source_hash),evidence=False)
            except Changed:
                raise ValueError('the source model list changed; reload and review it before approval') from None
            for row in chosen:
                prepared.append(_approved_run(folder,row,source))
        except (ValueError,KeyError,TypeError,OSError,yaml.YAMLError) as error:   # OSError: the study's files changed
            ui.notify(str(error))                       # each time they were read (``Unsettled``: DD-03's new row)
            return
        for command,out,name in prepared:
            engine.launch(command,out,f'Constrain a model: {name}')
        ui.notify(f"{len(prepared)} run(s) constraining the reviewed models started, with their scan setups")
        submission.go("/")

    ui.button("Constrain the approved models", on_click=submission.once(go)).classes("mt-2")

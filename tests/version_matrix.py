"""The version handle's acceptance matrix (the version handle plan, step 4; the owner's release rule of
2026-11-03): its rows, each a boundary by a stable identity; its cases; and each cell's expected outcome, fixed here
before the harness runs them; with the world and the oracle the harness runs them with
(``tests/evidence/test_version_matrix.py``, ``tests/ui/test_version_matrix_pages.py``). ``docs/version_matrix.md`` is
this table written out (``table``), and a test keeps the two the same.

The world: a saved study published whole as A by the production writer, every part of it marked so that what a
consumer shows or writes says whose it is (its result's model name, its evidence's notes, constructions and source,
its report's body, its figure's bytes, its record's title and cost), and B, another publication marked likewise. A
cell's change is made at the moment its row's kind fixes: for a row that resolves the study itself (``held``), after
its resolution and before it uses what it read, or during it (T1, T3); for a row acting on a version named earlier
(``token``), after its token was taken from the page's version of A and before the action resolves it (T2: after it has
resolved it). The oracle reads the consumer's output for the marks of A and of B: one version's throughout, every
observable its row declares shown (its parts, and what it derives from them: a verdict, a cost), or a refusal naming
the part, never both; and a row's baseline shows exactly what it declares (the auditor's version-handle audit, DD-03,
2026-11-04: a row declaring only its record had passed with B's verdict beside A's title)."""
from __future__ import annotations

import base64
import hashlib
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

from adroit.core.certificate import POLICY

PARTS = ("result", "evidence", "presentation", "record")
# what a row's output can show of a version: its parts, and what it derives from them (its verdict and certification,
# its cost), each marked apart (``marks``), so that one derived from another version than its part is seen (DD-03)
OBSERVED = PARTS + ("headline", "cost")

CASES = {
    "B": "nothing changed (the baseline)",
    "R": "the result replaced by a whole other publication (B: result, evidence, report, figure and record)",
    "E": "the evidence replaced (B's notes, constructions and source); the result's bytes the same",
    "E0": "the evidence sidecar removed; the result the same",
    "P": "the report and its figure replaced (B's), bound to the same result; the result and evidence the same",
    "S": "the study record replaced by another publication's (B's title and cost, naming B's result)",
    "S2": "the same result with another study record (B's title and cost; it names the same result)",
    "D": "a member damaged: the evidence sidecar no longer readable as one",
    "L": "an older study: no evidence sidecar, a report recording no binding, a record naming no result",
    "T1": "B published while the consumer reads the study, after it has read the result; a curated record, or its "
          "data file, changed while its review export is prepared (at its figure, and at its packet's curves); a "
          "curated record's page, its data file changed once the page has read it, or read as B and A restored "
          "after",
    "T2": "B published after the consumer has resolved its token, before it uses what it read",
    "T3": "the study replaced at every reading: a mismatch that persists through every retry",
    "ABA": "the token's version replaced by B, then A's very bytes restored; then A's record written anew; a curated "
           "record's data file B while its review export, or its page, is prepared (at its figure, at its packet's "
           "curves, and at each check of its signature apart from its reading), A's very bytes restored before the "
           "export is checked, or the page's verification clicked",
    "G": "a promotion's edge: its child replaced by another version; its parent replaced; its child removed",
    "GW": "an edge the export could not follow: its warning carried through a review of the bundle to its packet",
    "CK": "a resume: a completed checkpoint beside another publication, and a calculation resumed part way",
    "OA": "an operational attempt: a later run's record and settled ledger in the study's folder, before its cost is "
          "read or while it is (after its run's record was read), with or without a new publication; another run's "
          "records read, then the study's run's restored byte for byte (A, B, A), once or at every reading, for each "
          "record of its money (its paid ledger, its log, a budget stop's record, a session step's request record); "
          "another run's record beside its run's record unchanged; a request settled in a shared session's ledger "
          "before or after the cost's reading of it, or after it and then undone, its run's record unchanged; the "
          "session's cap raised, and spent or reserved under, between the reading of its record and of its ledger, "
          "or its record then restored; a raise read half made, or interrupted; the record changed at every reading; "
          "a reading while another thread raises and spends; a survey run's request record damaged (torn, null, a "
          "list, an empty object) beside an earlier survey's discovery.json, with or without a record bound to the "
          "run; its request record or its log a link that leads nowhere (to a missing file, to itself, through a "
          "file), with or without a record bound to the run; a paid ledger's lifecycle, from its making through each "
          "append between requests: a session's ledger put in its live client's place between two requests (a link "
          "to nothing, to itself, through a file, to a folder, a folder, no entry, an empty file or a link to one, "
          "its first line alone, another of its length), or after another writer appended, then every reading's "
          "totals, and the original restored; a run's own ledger damaged or lost when its run opens it, or replaced "
          "after, before its first request; a ledger emptied, cut short or replaced since its last writer, read "
          "after; a ledger past its writer's last line: a reservation's write cut short (before its bound, after it) "
          "or written whole and its sync failed, then the same client's next request; a line after the client's last "
          "that is not JSON, not an entry, a settlement never reserved, or torn; a whole last entry without its "
          "newline; a run's torn ledger at its opening, then recovered; a journal's recovery where it does not begin "
          "with what its mark records, and where it does; each entry of a request (its reservation, its response, its "
          "bill uncertain, its settlement) refused before it is written, cut short, unsynced or unmarked, then the same "
          "client's next request; the journal put in its place while its append checks it, once it has written, and "
          "once it has marked; a cap raise its writer never makes, one its record lacks, and the raises a person "
          "makes; a request reserved before its account froze, and two clients of one account; the journal changed in "
          "place as its append is made (emptied, its paid request removed, its bill lowered: once checked, once "
          "written and synced, once marked) or its mark damaged or shortened once written, and a healthy append's "
          "every earlier request and bill at each send; an append and a recovery while another writer holds the "
          "journal's lock; another process's request once a recovery has put the recovered journal in its place, "
          "before its mark is written, then the journal cut back to what the recovery wrote; an append through a "
          "linked folder while the lock is held by the folder's own path; a request asked by another name of the "
          "journal (a link to it or a hard link's name, in its folder or another), with no recovery and during one, "
          "and through a linked folder during one; a hard link made while an append checks the journal; an append "
          "and a recovery whose folder is replaced while it waits for its lock, and while it holds it, another "
          "process spending in the folder put in its place; a session's client given its ledger through a link to "
          "its folder or to one above it, while its record and ledger disagree, its ledger put in its place since its "
          "account was read, and healthy; a client of a session's account given another ledger; a run's ledger "
          "through a link to its folder, put in its place since its run opened it and healthy; a run's client given "
          "its ledger through a link to its folder or to one above it, the link then led to an empty folder or "
          "another opened run's before its first request, between two requests, and between a reservation and its "
          "receipt, and kept; a reservation's readback begun with its folder, the folder above it, or a link to a "
          "copy put in its place (an older coherent copy), and a folder so replaced once the readback has checked, "
          "then every reading of the run's cost and the ledger, a fresh client of it, and a session's account and "
          "spending beside such a notice",
    "AF": "a diagnostic output's report: what it was made of, said to be read as found",
    "W": "another of ADROIT's writers in a publication's folder while its writer runs: a second reanalysis into it, "
         "past its fresh-folder check; B published by the production writer during its calculation and after each of "
         "its parts and its record, from another thread and from its own; a Track 1 run drawing its own plane, from "
         "this thread, another and another process; each writer that calculates, draws or writes into a study's "
         "folder, with the folder held by another thread or process; a figure still rendering where no writer held "
         "the folder when another writer, in another thread or process, takes it; a figure that is a link, drawn by "
         "another writer while its folder, or its target's, is held; a review packet's writer, its overlay drawn, "
         "when another packet writer (another thread, another process) writes into its folder, and each of its files "
         "a link, with its folder or its target's held; the review page's packet, another packet writer into its "
         "folder as it is rendered; a curated record's review export, or the review queue's, another export into its "
         "folder (another thread, another process), and each of its files a link into another folder, with that "
         "folder or its own held; a session command's export and its request record, another export into its folder "
         "(another thread, another process); a session command refused into a saved study's folder, the folder held "
         "or not, and a stopped run's record waiting while a study is published there; two evidence bundles exported "
         "to one new ZIP path, the second completed while the first is prepared; an export of another kind into its "
         "folder (a review's, the queue's as report.json, a discovery's, a theory check's), after it or at once, and "
         "an entry there no export recorded (a person's file, a link, an earlier ADROIT's export), the review timer "
         "reading the packet after",
    "F": "a writer failing part way: an export's replacement failing (an I/O error) before or after each of its files, "
         "or at its mark of an export in progress (written, removed, or rewritten), or its writer killed after its "
         "first; then the folder read again by each reader of it, a session's run's cost read from it (its request "
         "record also damaged: torn, null, a list, an empty object, or a link that leads nowhere, beside an earlier "
         "export's discovery.json), and another export written into it (another kind's, or of some of its files)",
}
GENERIC = ("B", "R", "E", "E0", "P", "S", "S2", "D", "L", "T1", "T2", "T3", "ABA")
CHANGED = {"R": "result", "E": "evidence", "E0": "evidence", "D": "evidence", "P": "presentation", "S": "record",
           "S2": "record"}
QUALIFIED = ("as found", "legacy", "not checked", "written before", "records no link", "no link to", "unchecked",
             "reconstructed", "not recorded", "names none", "does not name")


@dataclass(frozen=True)
class Row:
    """A boundary: ``kind`` (held, token, publication, packet, export, graph, archive, resume, cost, diagnostic), the call
    site it is, what its output shows of a version (``shows``: of ``OBSERVED``, each required in its output, and in its
    baseline nothing else), what its token names (``needs``, a token row's), and where it runs."""
    id: str
    kind: str
    site: str
    shows: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    page: bool = False
    qualifies: bool = True          # whether its output says what it could not check of an older study (L)
    legacy: tuple[str, ...] | None = None       # what it shows of an older study, where that is less (``required``)
    special: dict[str, str] = field(default_factory=dict)    # case: expected, for a case this row decides alone


ROWS = [
    # renderers and lists: each resolves the study itself, once
    Row("history.row", "held", "ui/pages.py:studies_page", ("record", "headline", "cost"), page=True, qualifies=False),
    Row("history.facts", "held", "orchestrator/annotations.py:held_facts", ("record", "headline"), qualifies=False),
    Row("cli.studies", "held", "orchestrator/cli.py:studies_tree", ("record", "cost"), qualifies=False),
    Row("pickers.track1", "held", "ui/wizards.py:_track1_studies", ("record",), qualifies=False,
        special={"T3": "left out"}),
    Row("pickers.reanalysis", "held", "ui/reanalysis.py:_sources", ("record",), qualifies=False,
        special={"T3": "left out"}),
    Row("models.analyses", "held", "ui/model_library.py:analyses", ("record",), qualifies=False,
        special={"T3": "left out"}),
    Row("study.page", "held", "ui/pages.py:study", ("result", "evidence", "presentation", "record", "headline", "cost"),
        page=True),
    Row("point.table", "held", "ui/points.py:points_panel (its links)", ("result", "evidence"), page=True,
        qualifies=False),
    Row("study.cost", "held", "ui/pages.py:study_cost", ("cost",), qualifies=False),
    Row("setup.estimate", "held", "orchestrator/setup_check.py:estimate", ("record",), qualifies=False,
        special={"T3": "left out"}),
    Row("revisit.updates", "held", "orchestrator/revisit.py:updates", ("result", "evidence", "record"),
        qualifies=False, special={"T3": "left out"}),
    Row("classic.report", "held", "workbench/server.py:report_view", ("result", "presentation")),
    Row("live.report", "held", "ui/pages.py:_live_report", ("result", "presentation"), special={"T3": "left out"},
        legacy=("presentation",)),
    Row("export.cli", "held", "evidence/cli.py:export", ("result", "evidence", "presentation", "record")),
    Row("point.cli", "held", "evidence/cli.py:point", ("result", "evidence")),
    Row("tables.cli", "held", "evidence/cli.py:tables", ("result",), qualifies=False),
    Row("figures.cli", "held", "evidence/cli.py:figures", ("result", "presentation")),
    Row("review.queue", "held", "constraints/review_queue.py:load_selected", ("result", "evidence")),
    Row("agents.saved", "held", "orchestrator/cli.py:agents", ("result",)),
    Row("assist.saved", "held", "orchestrator/cli.py:assist (a single-idea study)", ("result",)),
    Row("reuse.track1", "held", "orchestrator/physical_eligibility.py:_saved", ("result", "evidence"),
        qualifies=False, special={"L": "refused:evidence"}),
    # navigation and actions: each acts on the version its page named
    Row("point.page", "token", "ui/points.py:point_page", ("result",), ("result", "evidence"), page=True),
    Row("point.link", "token", "evidence/points.py:explain", ("result", "evidence"), ("result", "evidence")),
    Row("download.tables", "token", "ui/exports.py:files tables", ("result",), ("result", "evidence"),
        qualifies=False),
    Row("download.figures", "token", "ui/exports.py:files figures", ("result", "presentation"),
        ("result", "presentation")),
    Row("download.references", "token", "ui/exports.py:files references", ("result", "evidence", "record"),
        ("result", "evidence", "record")),
    Row("download.bundle", "token", "ui/exports.py:files bundle", ("result", "evidence", "presentation", "record"),
        PARTS),
    Row("reanalysis.open", "token", "orchestrator/reanalysis.py:open (Run again)", ("result", "evidence"),
        ("result", "evidence"), qualifies=False),
    Row("reanalysis.preview", "token", "orchestrator/reanalysis.py:preview (the draft's)", ("result", "evidence"),
        ("result", "evidence"), qualifies=False),
    Row("revisit.card", "token", "ui/revisit.py:update_card → reanalysis.open", ("result", "evidence"),
        ("result", "evidence"), qualifies=False),
    Row("classic.file", "token", "workbench/server.py:route /file", ("result",), ("result",), qualifies=False,
        special={case: "N/A: the classic route sends one file, read once and checked against the token's digest: "
                       "there is no second part to join, nor a resolution to repeat" for case in ("T1", "T3")}),
    Row("promote.parent", "token", "orchestrator/promote.py:parent_result", ("result",), ("result",),
        qualifies=False),
    Row("approve.idea", "token", "ui/pages.py:approve_panel (Constrain the approved models)", ("result",),
        ("result",), page=True, qualifies=False),
    Row("records.packet", "token", "ui/records.py:_packet", ("result", "evidence"), ("result", "evidence"),
        page=True),
    # a publication: what follows it requires the version its writer wrote
    Row("reanalysis.run", "publication", "orchestrator/reanalysis.py:run (its child, as published)", PARTS),
    # a calibrated review packet: the page, overlay and record a researcher's figure verification binds to (DH-01)
    Row("review.packet", "packet", "constraints/experimental_review.py:plot_packet → _reviewed (verify-figure)"),
    # and its page: the images a researcher is shown beside the source, and the verification clicked there (DI-01)
    Row("review.page", "packet", "ui/experimental_review.py:_review_packet (its images; Verify the figure by hand)",
        page=True, special={"T1": "A then refused", "T2": "A then refused", "P": "A then refused", "ABA": "A"}),
    # curated review exports, each written whole into a folder a person names (the auditor's DI recheck, DJ-01)
    Row("records.export", "export", "constraints/review_cli.py:packet_command (records review --out)",
        special={"T1": "refused:record", "ABA": "A"}),
    Row("queue.export", "export", "constraints/review_cli.py:queue_command (records queue --out)"),
    # a session command's draft or report with its request record, one export (the auditor's DJ recheck, DK-01)
    Row("session.export", "export", "orchestrator/preflight.py:session_export, record_requests (models step, models "
        "paper, constraints discover, constraints resume, experiments extract --out)"),
    # a curated record's page: its figure, signature state and the version a verification binds, one reading (DL-01)
    Row("records.page", "curated", "ui/records.py:record_page (its figure, data, packet and signature state; Mark as "
        "verified)", page=True),
    # graphs, archives, continuations, accounting, diagnostics
    Row("graph.export", "graph", "evidence/archive.py:_promoted"),
    Row("graph.review", "graph", "constraints/review_queue.py:load_selected (promotion)"),
    Row("graph.bundle_review", "graph", "constraints/review_queue.py:load_selected (bundle)"),
    Row("graph.packet", "graph", "constraints/review_packets.py:packet_for"),
    Row("bundle.verify", "archive", "evidence/archive.py:verify_bundle"),
    Row("bundle.replay", "archive", "evidence/replay.py:replay_bundle"),
    Row("bundle.viewer", "archive", "ui/batch_page.py:_show_bundle (Open a bundle)", page=True),
    Row("resume.track1", "resume", "orchestrator/runs.py:restored_dates (Track 1)"),
    Row("resume.native", "resume", "orchestrator/native_fit.py:run (resume)"),
    Row("cost.attempt", "cost", "orchestrator/accounting.py:held_cost (the card, the Studies line, adroit studies)"),
    Row("theory.report", "diagnostic", "theory/cli.py"),
    Row("fog.report", "diagnostic", "orchestrator/fog_cli.py:write"),
    Row("intake.report", "diagnostic", "orchestrator/catalog_cli.py:_draft_report"),
    Row("discovery.report", "diagnostic", "orchestrator/discovery_cli.py:_report"),
    Row("advisory.report", "diagnostic", "orchestrator/research_assistance.py:report"),
]
BY_ID = {row.id: row for row in ROWS}

NA = {
    "held:T2": "a row that resolves the study itself has no earlier token: its changes are made after its resolution "
               "(R–D)",
    "held:ABA": "a row that resolves the study itself names no version to return to",
    "graph": "the row has no promotion graph",
    "graphw": "only a review of an exported bundle, and its packet, carry an export's warnings",
    "resume": "the row resumes no checkpoint",
    "cost": "the cost bound to a run's attempt is decided once, in the row cost.attempt (the study's card, its line "
            "in Studies and `adroit studies` read it)",
    "diagnostic": "the row is not a diagnostic output (the owner's decision 3)",
    "outside": "outside the handle by the owner's decision 3: a diagnostic output is read as found, and says so (AF)",
    "special": "this row's boundary is decided by its own cases",
    "publication:L": "a reanalysis publishes a new study: it is never an older one",
    "publication:T2": "the run's check of its child is its last use of it: nothing is read after it",
    "writers": "the row's boundary writes nothing another of ADROIT's writers shares: of the rows, only a publication, "
               "a review packet or an export shares its folder with another writer, and only a bundle's export a new "
               "path a person names; the row's changes by others are its other cases. Every other writer of a new "
               "file a person names (the usability report, a signal draft, an approved model, a model export, a "
               "review timer, a session start, an experimental import's folder, the evidence commands' folders) is "
               "outside the handle, with its own create-only contract (test_dm_fixes, test_dl_fixes)",
    "packet": "a review packet is its own folder's page, overlay and record, written once by its writer and read once "
              "by the figure verification: it has no study result, evidence or record, no older form, token, graph, "
              "resume or cost (its P and T1 replace its overlay and its page; W, another packet writer; its page's "
              "ABA, B's packet written and A's very bytes restored before the verification)",
    "export": "an export is written once, whole, into a folder a person names, for a person to read: it has no study "
              "result, evidence or record of its own, no older form, token, graph, resume or cost, and what reads it "
              "again reads it whole or as incomplete (its F) (its B, the export as its writer prepared it; its W, "
              "another export into its folder, of its kind or another's, and each of its files a link, and a session "
              "command refused into a study's folder; the review's T1 and ABA, its record or data changed while it is "
              "prepared)",
    "failure": "the row's writer failing part way is not a case of this matrix: it is decided for the exports a "
               "person's folder holds (the auditor's DJ recheck, DK-05)",
    "curated": "a curated record's page shows one reading of its record and data file: its figure, data, packet and "
               "signature state, and the version its verification binds; it has no study result, evidence or record, "
               "no older form, graph, resume or cost, and reads nothing again but after a verification (T3: no "
               "reading to repeat); its T1 is its data file changed once read, or read as B and A restored after, its "
               "ABA B while its figure is drawn and its signature checked, A's very bytes restored",
    "packet:page": "the review page shows one packet beside one source, as its rendering wrote it: it has no study "
                   "result, evidence or record, no older form, graph, resume or cost, and reads nothing again (T3: no "
                   "reading to repeat); its T1 is B's packet in its folder before its images are shown, its T2 A's "
                   "source's packet drawn otherwise once they are, its P B's overlay there, its ABA A's very bytes "
                   "restored, its W another packet writer",
}


DESTINATIONS = ("export.cli", "download.bundle")    # a bundle's export to a new path a person names (DL-05)


def expected(row: Row, case: str) -> str:
    """The cell's outcome, fixed beforehand: "A", "A, as found", "B", "refused:<part>", "refused:unsettled", "A then
    refused", one of a special row's, or "N/A: <why>"."""
    if case in row.special:
        return row.special[case]
    if case == "F":
        return "whole or incomplete" if row.kind == "export" else f"N/A: {NA['failure']}"
    if case == "W":
        return "one owner" if row.kind in ("publication", "packet", "export") or row.id in DESTINATIONS else \
            f"N/A: {NA['writers']}"
    if row.kind == "curated":
        return {"B": "A", "T1": "A then refused", "ABA": "A"}.get(case, f"N/A: {NA['curated']}")
    if row.kind == "export":
        return "A" if case == "B" else f"N/A: {NA['export']}"
    if row.kind == "packet":
        return {"B": "A", "P": "refused:presentation", "T1": "refused:presentation"}.get(
            case, f"N/A: {NA['packet:page' if row.page else 'packet']}")
    if row.kind == "diagnostic":
        return "as found" if case == "AF" else f"N/A: {NA['outside']}"
    if case == "AF":
        return f"N/A: {NA['diagnostic']}"
    if row.kind in ("held", "token", "publication"):
        if case in ("G", "GW"):
            return f"N/A: {NA['graph']}"
        if case == "CK":
            return f"N/A: {NA['resume']}"
        if case == "OA":
            return f"N/A: {NA['cost']}"
    legacy = "A, as found" if row.qualifies else "A"
    if row.kind == "held":
        return {"B": "A", "L": legacy, "T1": "B", "T2": f"N/A: {NA['held:T2']}", "T3": "refused:unsettled",
                "ABA": f"N/A: {NA['held:ABA']}"}.get(case, "A")
    if row.kind == "token":
        if case in CHANGED:
            return f"refused:{CHANGED[case]}" if CHANGED[case] in row.needs else "A"
        return {"B": "A", "L": legacy, "T1": "refused:result", "T2": "A", "T3": "refused:unsettled",
                "ABA": "A then refused" if "record" in row.needs else "A"}[case]
    if row.kind == "publication":         # B: by a process outside ADROIT's writers, in the child's folder (DE-02)
        return {"B": "A", "R": "refused:result", "E": "refused:evidence", "E0": "refused:evidence",
                "D": "refused:evidence", "P": "refused:presentation", "S": "refused:record", "S2": "refused:record",
                "T1": "refused:result", "T3": "refused:unsettled", "ABA": "A then refused",
                "L": f"N/A: {NA['publication:L']}", "T2": f"N/A: {NA['publication:T2']}"}[case]
    if row.kind == "graph":
        if case == "G":
            return "named"
        if case == "GW":
            return "carried" if row.id in ("graph.bundle_review", "graph.packet") else f"N/A: {NA['graphw']}"
        if case == "B":
            return "A"
        if case == "L":
            return "A, as found"
        return f"N/A: {NA['special']} (G, GW; its nodes are each read as a version: see the held and token rows)"
    if row.kind == "archive":
        return {"B": "A", "R": "A", "T1": "A"}.get(case, f"N/A: {NA['special']} (a bundle is read once, as bytes)")
    if row.kind == "resume":
        return {"B": "dated", "CK": "dated"}.get(case, f"N/A: {NA['special']} (CK)")
    if row.kind == "cost":
        return {"B": "own cost", "OA": "own cost"}.get(case, f"N/A: {NA['special']} (OA)")
    raise ValueError(f"{row.id}: no rule for {case}")


def cells() -> list[tuple[str, str, str]]:
    """Every cell: (row, case, expected)."""
    return [(row.id, case, expected(row, case)) for row in ROWS for case in CASES]


def table() -> str:
    """``docs/version_matrix.md``: the cases, the rows and every cell, as fixed here."""
    lines = ["# The version handle's acceptance matrix", "",
             "Written out from `tests/version_matrix.py` (a test keeps the two the same); run by",
             "`tests/evidence/test_version_matrix.py` and `tests/ui/test_version_matrix_pages.py`. The rule it decides",
             "is in the release plan (\"Amended by the owner, 2026-11-03\") and the version handle plan.", "",
             "## Cases", "", "| case | change |", "|---|---|"]
    lines += [f"| {case} | {what} |" for case, what in CASES.items()]
    lines += ["", "## Outcomes", "",
              "- **A**: everything the boundary shows or writes is A's: each observable its row declares (a part, its",
              "  verdict, its cost) shown with A's mark, no mark of B anywhere; in the baseline, nothing it does not",
              "  declare.",
              "- **A, as found**: A's, and it says what it could not check (legacy, as found, recording no link).",
              "- **B**: everything is B's, each declared observable (B was published while it read: its files read",
              "  again together).",
              "- **refused:part**: nothing is shown or made, naming the part (result, evidence, presentation, record),",
              "  or that the study's files changed each time they were read (unsettled); a curated record's",
              "  review export whose record or data file changed while it was prepared, nothing written (record).",
              "- **A then refused**: A's very bytes restored, A's; A's record written anew (another date), refused.",
              "  The review page: A's source and A's images shown, as A's rendering wrote them; its figure",
              "  verification, bound to the packet shown, refused once the folder holds another. A curated record's",
              "  page: A's figure and A's signature state shown; its verification, bound to A, refused once the",
              "  data file is another.",
              "- **left out**: a list leaves out a study whose files changed each time it read them, as it leaves out a",
              "  record it cannot read.",
              "- **named**: an edge to another version, or to nothing, is named unavailable; B nowhere.",
              "- **carried**: the export's warning about an edge is in the review of the bundle and its packet.",
              "- **dated**: a resume's dates are its checkpoint's own, never the publication beside it.",
              "- **own cost**: the cost shown on the card, in Studies and by `adroit studies` is the study's own",
              "  run's, or its record's saying so, never a later run's, whenever that run's records are written,",
              "  restored over or read beside its own.",
              "- **one owner**: the publication's folder is its writer's while it runs: a second reanalysis is refused",
              "  before it calculates; another of ADROIT's writers waits, then publishes whole, or, from its own",
              "  thread, is refused, nothing of it written; the run returns A. A review packet's folder is its",
              "  writer's from its first file to its record: another packet writer waits, then writes its packet whole;",
              "  the reader accepts each packet whole as its writer's, never one's record with another's overlay; each",
              "  of its files is written to its own entry, never through a link into another folder; its page shows",
              "  the packet its writer wrote. A curated export's folder is its writer's from its first file to its",
              "  last: another export waits, then writes its own whole, never one record's packet beside another's",
              "  report or curve; each file to its own entry, never through a link. A session command's draft or",
              "  report and its request record are one export; a command refused before it sends anything writes",
              "  nothing into the folder it was given, and a study there keeps its every byte and its cost. A",
              "  bundle's new ZIP is its export's: one written there while it is prepared is left as it is, and the",
              "  later export refused, nothing of it kept.",
              "- **whole or incomplete**: an export that fails part way leaves its folder's earlier export whole, put",
              "  back; one whose writer was killed leaves the folder saying it is incomplete (`EXPORT_INCOMPLETE.txt`),",
              "  which each reader of it reads so, until that export's files are written whole again (another export",
              "  into the folder keeps it); one whose mark could not be removed says so, the folder marked; a",
              "  session's run is charged with the session its own records name; never one export's file beside",
              "  another's as if whole.",
              "- **as found**: the report says what it was made of, read as found.",
              "- **N/A**: the cell does not apply, with why.", "",
              "## Rows", "", "| row | kind | call site | shows | its token names |", "|---|---|---|---|---|"]
    lines += [f"| {r.id} | {r.kind} | `{r.site}` | {', '.join(r.shows) or '—'} | {', '.join(r.needs) or '—'} |"
              for r in ROWS]
    lines += ["", "## Cells", "", "| row | " + " | ".join(CASES) + " |", "|---|" + "---|" * len(CASES)]
    short = {}
    for row in ROWS:
        out = []
        for case in CASES:
            value = expected(row, case)
            if value.startswith("N/A: "):
                key = value[5:]
                short.setdefault(key, f"n{len(short) + 1}")
                value = f"N/A ({short[key]})"
            out.append(value)
        lines.append(f"| {row.id} | " + " | ".join(out) + " |")
    lines += ["", "Not applicable, why:", ""] + [f"- {key}: {why}" for why, key in short.items()]
    return "\n".join(lines) + "\n"


# --- the world ----------------------------------------------------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n"
REFERENCE = "catalog:matrix@r1"           # the model revision every version's record says it used


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def marks(label: str) -> dict[str, tuple[str, ...]]:
    """What shows that an observable (``OBSERVED``) is version ``label``'s: its parts' marks, its verdict's (A's
    excluded, B's viable pending: the result's, as its headline words it) and its cost's (its record's dollars)."""
    coordinate = "500" if label == "A" else "1900"     # grid:0's mediator mass: a point of A's scan, or of B's
    return {"result": (f"MatrixResult{label}", f'"m_med": {coordinate}.0', f'"m_med":{coordinate}.0',
                       f"m_med = {coordinate} GeV", f",{coordinate}.0,"),
            "evidence": (f"MatrixEvidence{label}",),
            "presentation": (f"MatrixReport{label}", f"MatrixFigure{label}"),
            "record": (f"MatrixRecord{label}",),
            "headline": ("EXCLUDED · ",) if label == "A" else ("VIABLE PENDING · ", "viable pending"),
            "cost": ("$1.25",) if label == "A" else ("$9.50",)}


# Each version's fields as its study page shows them (the auditor's DD recheck, DE-03, 2026-11-05: a page showing A's point
# with B's decision had passed, one mark standing for a whole part): the point table's rows (``ui/points.points_panel``:
# point, kind, coordinates, Ωh², status, first exclusion or pending reason, and its link) and the summary's verdict,
# certification, cost and record dates (``ui/pages._summary``), fixed here from the world as published, apart for A and
# B, never computed by the code under test; ``test_the_fixed_fields_are_the_world_s`` keeps them the production
# projection's. A field is compared whole with each version's value, a summary field's text exactly, each link's every
# part, and each field asked for must be shown (``fields``; the auditor's DE recheck, DF-03, 2026-11-05: a link to another
# point or study, a certification line with more words, and a summary without its duration had passed). Each link is
# the workbench's own, with no origin or fragment of its own; and the interactive plane beside the table
# (``ui/points.chart_options``) is compared point by point (its series, colour, symbol and coordinates) and by its axes,
# with each version's plane fixed here (``CHART``; the auditor's DF recheck, DG-03, 2026-11-06: a link to another origin,
# and a plane drawing an excluded point as allowed, had passed): each point as drawn, its own colour, symbol and size
# where it gives them, and anything beyond the plane's contract named (``PLANE``; the auditor's DG recheck, DH-02).
TABLE = ("point", "kind", "where", "omega", "status", "reason", "halo")
# The point table's columns as the study page heads them (``points.points_panel``), in order, each whole: its name, its
# header's label with its units, the row field its cells show and whether it sorts; the template of each cell slot,
# which draws a column's cells in place of its field's text; and the table's other properties. Fixed here, apart from
# production: ``TABLE`` compares the rows passed to the table, field by field, and these which header each field is
# shown under, and how (the auditor's DJ recheck, DK-03, 2026-11-07: the Ωh² values headed as a cross section, or the status
# column showing Ωh², had passed both page cells, their rows unchanged).
COLUMNS = [{"name": "point", "label": "point", "field": "point", "sortable": True},
           {"name": "kind", "label": "kind", "field": "kind", "sortable": True},
           {"name": "where", "label": "coordinates", "field": "where"},
           {"name": "omega", "label": "Ωh²", "field": "omega"},
           {"name": "status", "label": "status", "field": "status", "sortable": True},
           {"name": "reason", "label": "first exclusion or pending reason", "field": "reason"},
           {"name": "halo", "label": "halo", "field": "halo"},
           {"name": "open", "label": "", "field": "open"}]
CELL_SLOTS = {"body-cell-open": '<q-td :props="props"><a :href="props.value">explain</a></q-td>'}
TABLE_PROPS = {"filter": None, "row-key": "point", "hide-pagination": False, "pagination": {"rowsPerPage": 25},
               "selection": "none", "selected": [], "fullscreen": False}     # every row reachable, none hidden
HIGGS = "the invisible Higgs width: its record (ATLAS, arXiv:2301.10731) awaits a person's verification"


def _at(chi: int, med: int) -> str:
    return f"m_chi = {chi} GeV, m_med = {med} GeV, g_chi = 1, g_q = 0.25, g_l = 0"


GRID = {"A": ((50, 500), (50, 1000), (100, 500), (100, 1000), (75, 750)),          # each point's (m_chi, m_med), GeV
        "B": ((900, 1900), (900, 2000), (1000, 1900), (1000, 2000), (950, 1950))}
# each point's halo (halo phase 1: ``evidence.halo.point_label``): both versions were saved before the halo choice
# existed, so each reads as calculated, with the published halos, said so
LEGACY_HALO = "Published halos (reproduction), not recorded"
POINTS = {label: [("grid:0", "grid sample", _at(*GRID[label][0]), "0.12", *first, LEGACY_HALO),
                  ("grid:1", "grid sample", _at(*GRID[label][1]), "0.12", "pending", HIGGS, LEGACY_HALO),
                  ("grid:2", "grid sample", _at(*GRID[label][2]), "—", "pending", HIGGS, LEGACY_HALO),
                  ("grid:3", "grid sample", _at(*GRID[label][3]), "0.12", "pending", HIGGS, LEGACY_HALO),
                  ("contour:0", "thermal root", _at(*GRID[label][4]), "0.12", "pending",
                   f"{HIGGS} (atlas-2301.10731-hinv)", LEGACY_HALO)]
          for label, first in (("A", ("excluded", "direct detection")),
                               ("B", ("pending", "colliders: a recast of the LHC searches to this model")))}
SUMMARY = {"A": {"verdict": "EXCLUDED · NOT ASSESSED (LEGACY)",
                 "certification": "This result was saved before certificates: legacy, not assessed. Its verdict is as "
                                  "it was decided.",
                 "cost": "cost $1.25 settled", "calculated": "UTC: 2026-11-01T01:01:40+00:00", "took": "took 1 min 40 s"},
           "B": {"verdict": "VIABLE PENDING · STALE CERTIFICATION",
                 "certification": "The claims this headline rests on were certified under an earlier policy or on data "
                                  "that have changed since (stale); the verdict is as it was decided, and the report "
                                  "below was written then. (certified under policy an-earlier-policy, not the current "
                                  f"{POLICY})",
                 "cost": "cost $9.50 settled", "calculated": "UTC: 2026-11-01T02:15:00+00:00", "took": "took 15 min 00 s"}}
LINK = ("evidence", "path", "point", "sha256")      # a point's link: its study, its point and its version's identities
COLOURS = {"allowed": "#2e7d32", "pending": "#ef6c00", "excluded": "#c62828"}    # the plane's colour of each status
AXES = {"A": {"x axis": ("m_med", "log", 500.0, 1000.0), "y axis": ("m_chi", "log", 50.0, 100.0)},
        "B": {"x axis": ("m_med", "log", 1900.0, 2000.0), "y axis": ("m_chi", "log", 900.0, 1000.0)}}


def _plotted(point: str, status: str, chi: float, med: float) -> tuple:
    """A point as the plane draws it: (its series: its status, a thermal root's apart; its colour; its symbol and
    size; its coordinates, the mediator's mass across and the dark matter's up)."""
    root = point.startswith("contour:")
    return (status + (" (thermal roots)" if root else ""), COLOURS[status], "diamond" if root else "circle",
            14 if root else 7, (float(med), float(chi)))


def _series(label: str) -> tuple:
    """The plane's series as it should draw them, in order (``chart_options``: one per status, its thermal roots apart,
    each only where it has points): each (its name, colour, symbol and size, how many points it draws). The legend is
    these series' names: an extra series, even an empty one, says what none of the points does (the auditor's DI recheck,
    DJ-02, 2026-11-07: an empty series named "ALL POINTS ALLOWED; NO PENDING CHECKS" had passed)."""
    drawn = [_plotted(row[0], row[4], *GRID[label][i])[0] for i, row in enumerate(POINTS[label])]
    out = []
    for status, colour in COLOURS.items():
        for roots in (False, True):
            name = status + (" (thermal roots)" if roots else "")
            if name in drawn:
                out.append((name, colour, "diamond" if roots else "circle", 14 if roots else 7, drawn.count(name)))
    return tuple(out)


CHART = {label: {"points": {row[0]: _plotted(row[0], row[4], *GRID[label][i]) for i, row in enumerate(POINTS[label])},
                 "series": _series(label), **AXES[label], "beyond": ()} for label in "AB"}
# the plane's contract (``ui/points.chart_options``): what it may say, each read by ``chart_of``; anything else it says
# (a point's own label, a visual map recolouring points, an axis inverted, a line through them) is named, never
# passed over (the auditor's DG recheck, DH-02, 2026-11-06: a point's own colour, overriding its series', had passed).
# ``said``: what it says of itself, each whole: its tooltip an item's own (its series, its name and its value, in
# ECharts' own words), its legend at the top, every series shown, and each axis's name centred beside it; any other
# value, a key more or one left out is named (the auditor's DH recheck, DI-02, 2026-11-06: a legend hiding the excluded
# series, and a tooltip saying every point allowed, had passed, the names "legend" and "tooltip" allowed unread)
PLANE = {"options": {"tooltip", "legend", "xAxis", "yAxis", "series"},
         "series": {"type", "name", "data", "symbolSize", "itemStyle", "symbol"},
         "item": {"name", "value", "itemStyle", "symbol", "symbolSize"}, "style": {"color"},
         "axis": {"type", "name", "nameLocation", "nameGap", "min", "max"},
         "said": {"tooltip": {"trigger": "item"}, "legend": {"top": 0},
                  "axis": {"nameLocation": "middle", "nameGap": 28}}}


def _said(where: str, given, contract: dict) -> list[str]:
    """Each key of ``given`` (a part of the plane's options) whose value is not its contract's, or that the contract
    does not have, or that it leaves out: named, as ``where``'s key."""
    given = given if isinstance(given, dict) else {}
    return [f"{where}'s {k}" for k in sorted(set(given) | set(contract), key=str)
            if k not in given or k not in contract or given[k] != contract[k]]


def chart_of(options: dict) -> dict:
    """An interactive plane's options (``ui.echart``'s) as ``CHART`` holds a plane: each point by its name, as it is
    drawn (its series, and its colour, symbol and size: its own where it gives them, else its series'; a point drawn
    twice, under each of its series), its series whole, in order, each its name, colour, symbol, size and how many
    points it draws, an empty one too (``_series``: the legend's names; DJ-02), its axes (name, kind, from, to), and
    whatever it says beyond the plane's contract (``PLANE``: "beyond", each named; its tooltip, its legend and its axes'
    names read whole, ``said``)."""
    found: dict[str, tuple] = {}
    inventory: list[tuple] = []
    beyond = [f"the plane's {k}" for k in sorted(set(options) - PLANE["options"])]
    beyond += [*_said("the tooltip", options.get("tooltip"), PLANE["said"]["tooltip"]),
               *_said("the legend", options.get("legend"), PLANE["said"]["legend"])]
    for series in options.get("series", []):
        style = series.get("itemStyle") or {}
        beyond += [f"{series.get('name')}'s {k}" for k in sorted(set(series) - PLANE["series"])]
        beyond += [f"{series.get('name')}'s colour's {k}" for k in sorted(set(style) - PLANE["style"])]
        beyond += [f"{series.get('name')} of type {series.get('type')!r}"] if series.get("type") != "scatter" else []
        inventory.append((series.get("name"), style.get("color"), series.get("symbol"), series.get("symbolSize"),
                          len(series.get("data") or [])))
        for item in series.get("data", []):
            name, own = item.get("name"), item.get("itemStyle") or {}
            beyond += [f"{name}'s {k}" for k in sorted(set(item) - PLANE["item"])]
            beyond += [f"{name}'s colour's {k}" for k in sorted(set(own) - PLANE["style"])]
            drawn = (series.get("name"), own.get("color", style.get("color")), item.get("symbol", series.get("symbol")),
                     item.get("symbolSize", series.get("symbolSize")), tuple(float(v) for v in item.get("value", ())))
            found[name] = drawn if name not in found else ("drawn twice", found[name], drawn)

    def axis(which: str) -> tuple:
        a = options.get(which) or {}
        beyond.extend(f"the {which}'s {k}" for k in sorted(set(a) - PLANE["axis"]))
        beyond.extend(_said(f"the {which}", {k: a[k] for k in PLANE["said"]["axis"] if k in a}, PLANE["said"]["axis"]))
        return a.get("name"), a.get("type"), a.get("min"), a.get("max")
    return {"points": found, "series": tuple(inventory), "x axis": axis("xAxis"), "y axis": axis("yAxis"),
            "beyond": tuple(beyond)}


@dataclass
class World:
    """A runs folder holding the study (``folder``), published as A; B's typed result, ready to publish; and each
    part's identities as published (``identities``: label → part → identity strings that also mark them). ``kind``:
    the study's workflow; ``context``: the evidence context both are published with (a captured one, for a row that
    reuses only captured results); ``extra``: more marks, label → observable → strings; ``unmarked``: observables
    whose common marks do not tell its A from its B (``marks``: a reuse's A and B share their point)."""
    root: Path
    folder: Path
    a: object
    b: object
    identities: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    kind: str = "track1"
    context: object = None
    marked: bool = True
    extra: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)
    unmarked: tuple[str, ...] = ()

    @property
    def path(self) -> Path:
        return self.folder / "result.json"


def versions(folder: Path):
    """A and B, two valid Track 1 results of the study (``tests.orchestrator.test_vi_audit.versions``), marked: their
    model's names, their verdicts, the figure each names, and the dates their records give them; and their claims'
    certification apart: A's saved before certificates (legacy), B's certified under an earlier policy (stale), so that a
    certification of the other version is seen (the auditor's DD recheck, DE-03)."""
    from adroit.core.certificate import Certificate
    from tests.orchestrator.test_vi_audit import versions as vi
    a, b = vi(folder)
    a.request.spec.name, b.request.spec.name = "MatrixResultA", "MatrixResultB"
    a.verdict.level, b.verdict.level = "excluded", "viable_pending"
    a.plots, b.plots = ["plane.png"], ["plane.png"]
    for crossing in b.verdict.crossings:
        crossing.certificate = Certificate(claim_kind="thermal_root", scope="the matrix's world",
                                           policy="an-earlier-policy")
    return a, b


def publish(world: World, label: str, *, legacy: bool = False, identify: bool = True) -> None:
    """Version ``label`` published whole at the study's folder by the production writer (``runs._write``): its figure
    drawn first, its report embedding it, its evidence marked, its record titled, costed and dated; ``legacy``: as an
    older study (no sidecar, a report recording no binding, a record naming no result). ``identify``: note its parts'
    identities as published (not while a resolution is under way, ``always``)."""
    from adroit.core.durable import write_atomic
    from adroit.evidence import bindings, build
    from adroit.orchestrator import runs, studies
    folder, result = world.folder, world.a if label == "A" else world.b
    folder.mkdir(parents=True, exist_ok=True)
    write_atomic(folder / "plane.png", PNG + f"MatrixFigure{label}".encode())
    runs._write(folder, result, f"# Matrix report\n\nMatrixReport{label} body.\n\n![plane](plane.png)\n", world.kind,
                f"MatrixRecord{label}", {}, cost_usd=1.25 if label == "A" else 9.5, evidence_context=world.context)
    record = studies.load(folder)
    hour = "01" if label == "A" else "02"
    record = record.model_copy(update={"model_references": [REFERENCE],
                                       "calculation_started_at": f"2026-11-01T{hour}:00:00+00:00",
                                       "calculation_completed_at": f"2026-11-01T{hour}:{'01:40' if label == 'A' else '15:00'}"
                                                                   "+00:00"})
    if legacy:
        record = record.model_copy(update={"result_sha256": "", "attempt": ""})
        report = (folder / "report.md").read_text()
        write_atomic(folder / "report.md", bindings.unbound(report))
        build.sidecar_path(world.path).unlink()
    elif world.marked:
        mark_evidence(world.path, label)
    studies.save(record)
    if identify:
        world.identities[label] = identities(world)


def mark_evidence(path: Path, label: str) -> None:
    """The evidence beside ``path`` rewritten as version ``label``'s: its notes, each observation's construction and a
    source naming the label; the result's bytes, the summary and the certificates unchanged (it still names them)."""
    from adroit.core.durable import write_atomic
    from adroit.core.evidence import EvidenceEnvelope, SourceEvidence
    from adroit.evidence import build
    envelope = EvidenceEnvelope.model_validate_json(build.sidecar_path(path).read_bytes())
    tag = f"MatrixEvidence{label}"
    context = envelope.context.model_copy(update={"notes": [tag], "sources": [SourceEvidence(
        id="matrix-source", reference=f"{tag} source", version=label, review="unreviewed")]})
    observations = [o.model_copy(update={"construction": f"{o.construction} [{tag}]"}) for o in envelope.observations]
    engine = {**envelope.engine_mapping, "matrix": tag}         # what a point's explanation keys its observations by
    write_atomic(build.sidecar_path(path), envelope.model_copy(update={
        "context": context, "observations": observations, "engine_mapping": engine}).model_dump_json().encode())


def identities(world: World) -> dict[str, set[str]]:
    """Each part's identity strings as now saved (a digest, and its first 12 characters, as pages show them; and the
    evidence's own identity, ``EvidenceEnvelope.identity``, as a bundle's nodes and a review packet name it)."""
    from adroit.evidence.version import resolve
    found = resolve(world.folder, presentation=True)
    token = found.token()
    out = {}
    for part in PARTS:
        value = getattr(token, part)
        out[part] = {value, value[:12]} if len(value) == 64 else set()
    if found.evidence_state == "bound":
        own = found.envelope().identity
        out["evidence"] |= {own, own[:12], own[:16]}
    return out


def make(root: Path, *, legacy: bool = False) -> World:
    """The world: the study published as A (or as an older study, ``legacy``)."""
    runs = root / "runs"
    folder = runs / "study"
    a, b = versions(folder)
    world = World(runs, folder, a, b)
    publish(world, "A", legacy=legacy)
    return world


def single_idea_versions():
    """A and B, two single-idea results of one study (an assistant's saved input), marked by their models' names."""
    from adroit.orchestrator.single_idea import SingleIdeaResult
    from tests.orchestrator.test_research_assistance import request
    study = request().study
    out = []
    for label, level in (("A", "excluded"), ("B", "viable_pending")):
        named = study.model_copy(update={"spec": study.spec.model_copy(update={"name": f"MatrixResult{label}"})})
        out.append(SingleIdeaResult(request=named, level=level, summary=f"MatrixResult{label}'s summary"))
    return out


REUSED = {"A": '"dd_sigma_cm2":1e-46,', "B": '"dd_sigma_cm2":1.23456e-46,'}     # the point a reuse returns


def reuse_versions(folder: Path):
    """A and B, two Track 1 results of one model, each reusable at A's first point: B's evaluation there differs
    (``REUSED``), so the point a reuse returns says whose it is."""
    a, _ = versions(folder)
    b = a.model_copy(deep=True)
    b.scan.points[0].dd_sigma_cm2 = 1.23456e-46
    b.verdict.level = "viable_pending"
    return a, b


def idea_versions():
    """A and B, two idea studies' results (an approval's source), each offering one reviewed model, named by its
    version (``tests/ui/test_model_approval.workspace``'s supplied singlet)."""
    from adroit.core.model_spec import ModelSpec
    from adroit.orchestrator import ideas
    fields = ModelSpec.model_validate({"name": "supplied_singlet", "fields": [{
        "name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1, "mass_gev": 70}]})
    general = ideas.from_fields(fields).general
    out = []
    for label in "AB":
        spec = general.model_copy(update={"name": f"MatrixResult{label}", "couplings": [
            c.model_copy(update={"value": .2}) for c in general.couplings]})
        out.append(ideas.run(ideas.IdeaRequest(lagrangian_spec=spec)))
    return out


def world_for(row_id: str, root: Path, *, legacy: bool = False) -> World:
    """A row's world: the Track 1 study (``make``); for the assistant, a single-idea study; for an approval, an idea
    study; for the reuse of a saved
    Track 1 result, one published with captured provenance (what alone it reuses), unmarked evidence (its marks would
    change its context), its point marked."""
    if row_id not in ("assist.saved", "reuse.track1", "approve.idea"):
        return make(root, legacy=legacy)
    from adroit.evidence.runtime import capture          # a captured context of no input: nothing read, $0
    runs = root / "runs"
    folder = runs / "study"
    folder.mkdir(parents=True, exist_ok=True)
    if row_id == "assist.saved":
        a, b = single_idea_versions()
        world = World(runs, folder, a, b, kind="single_idea")
    elif row_id == "approve.idea":
        a, b = idea_versions()
        world = World(runs, folder, a, b, kind="idea")
    else:
        a, b = reuse_versions(folder)
        world = World(runs, folder, a, b, context=capture([], []), marked=False, unmarked=("result",), extra={label: {"result": (mark,)} for label, mark in REUSED.items()})
    publish(world, "A", legacy=legacy)
    return world


# --- the changes ----------------------------------------------------------------------------------------------------

def change(world: World, case: str) -> None:
    """The change of a generic case (R, E, E0, P, S, S2, D), made to A as saved."""
    from adroit.core.durable import write_atomic
    from adroit.evidence import bindings, build
    from adroit.orchestrator import studies
    path, folder = world.path, world.folder
    if case == "R":
        publish(world, "B")
    elif case == "E":
        mark_evidence(path, "B")
    elif case == "E0":
        build.sidecar_path(path).unlink()
    elif case == "D":
        write_atomic(build.sidecar_path(path), b"{")
    elif case == "P":
        write_atomic(folder / "plane.png", PNG + b"MatrixFigureB")
        text = "# Matrix report\n\nMatrixReportB body.\n\n![plane](plane.png)\n"
        write_atomic(folder / "report.md", bindings.bind(text, sha(path.read_bytes()), folder, ["plane.png"]).encode())
    elif case in ("S", "S2"):
        record = studies.load(folder)
        named = sha(world.b.model_dump_json(indent=1).encode()) if case == "S" else record.result_sha256
        studies.save(record.model_copy(update={"title": "MatrixRecordB", "cost_usd": 9.5, "result_sha256": named}))
    else:
        raise ValueError(case)


@contextmanager
def at(world: World, case: str):
    """A held row's change at its moment: after its resolution (R–D), during it (T1: B after the result is read), or at
    every reading (T3); nothing for B and L."""
    from tests.version_events import after_resolution, during_resolution
    if case in CHANGED:
        with after_resolution(lambda: change(world, case)):
            yield
    elif case == "T1":
        with during_resolution("result.json", lambda: publish(world, "B")):
            yield
    elif case == "T3":
        with always(world):
            yield
    else:
        yield


@contextmanager
def outside():
    """Writes made as a process outside ADROIT's writers makes them: without a study folder's publication lock
    (``durable.publishing``), which such a process does not take (the auditor's DD recheck, DE-02). ADROIT's own writers wait
    for the lock, or are refused where its holder is a reanalysis that owns the folder."""
    from adroit.core import durable

    @contextmanager
    def unlocked(folder, claim=None, wait=0.0):
        yield claim or durable.Claim(Path(folder).resolve(), None, 0)
    with patch.object(durable, "publishing", unlocked):
        yield


@contextmanager
def always(world: World, by_another: bool = False):
    """B and A published in turn at every reading of the study's result; ``by_another``: by a process outside
    ADROIT's writers (``outside``)."""
    from contextlib import nullcontext
    from adroit.evidence import version
    real, turn = version._read, [0]

    def read(path, limit=None):
        found = real(path, limit)
        if Path(path).name == "result.json" and Path(path).parent == world.folder:
            turn[0] += 1
            with outside() if by_another else nullcontext():
                publish(world, "AB"[turn[0] % 2], identify=False)
        return found
    with patch.object(version, "_read", read):
        yield


# --- the oracle -----------------------------------------------------------------------------------------------------

@dataclass
class Output:
    """What a consumer showed or wrote (``text``), or why it refused (``refused``)."""
    text: str = ""
    refused: str = ""


def text_of(value) -> str:
    """Anything a consumer gives back as searchable text: bytes decoded, a ZIP's members, embedded figures decoded."""
    import io
    import zipfile
    if isinstance(value, bytes):
        if value[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(value)) as z:
                return "\n".join(f"{n}\n{text_of(z.read(n))}" for n in z.namelist())
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (list, tuple, set)):
        return "\n".join(text_of(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(f"{text_of(k)}\n{text_of(v)}" for k, v in value.items())
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()
    text = str(value)
    for data in re.findall(r"data:image/png;base64,([A-Za-z0-9+/=]+)", text):
        text += "\n" + base64.b64decode(data).decode("latin-1")
    return text


def run(consume) -> Output:
    """``consume()``'s output, or its refusal."""
    try:
        return Output(text_of(consume()))
    except (ValueError, OSError) as error:
        return Output(refused=str(error) or type(error).__name__)


def named(message: str) -> str:
    """The part a refusal names (a command's message unwrapped from its box)."""
    text = re.sub(r"[\s│╭╮╰╯─]+", " ", message).lower()
    if "changed each time" in text or "settle" in text:
        return "unsettled"
    said = re.search(r"study's (result|evidence|report|record) was replaced", text)   # what it says, before what it
    if said:                                                                            # wrote (DE-02)
        return {"report": "presentation"}.get(said.group(1), said.group(1))
    for part, words in (("evidence", ("evidence",)), ("presentation", ("report",)), ("record", ("record",)),
                        ("result", ("result", "candidates", "model list", "version"))):
        if any(w in text for w in words):
            return part
    return "?"


def seen(world: World, text: str, label: str) -> set[str]:
    """The observables ``text`` shows to be version ``label``'s: by their marks, or their identities as published."""
    found = {part for part, words in marks(label).items()
             if part not in world.unmarked and any(w in text for w in words)}
    found |= {part for part, words in world.extra.get(label, {}).items() if any(w in text for w in words)}
    found |= {part for part, ids in world.identities.get(label, {}).items() if any(i and i in text for i in ids)}
    return found


def required(row: Row, case: str) -> tuple[str, ...]:
    """What a cell's output must show (``Row.shows``): an older study (L) has no evidence of its own to show, and a
    report recording no binding names no result (``Row.legacy``)."""
    if case == "L" and row.legacy is not None:
        return row.legacy
    return tuple(part for part in row.shows if not (case == "L" and part == "evidence"))


def outcome(world: World, out: Output, shows: tuple[str, ...], *, exact: bool = False) -> str:
    """The cell's outcome as observed (``expected``'s vocabulary): one version's only where every observable in
    ``shows`` is shown as that version's (DD-03: one shown alone had stood for the rest); with ``exact`` (a baseline),
    only where it shows nothing more; else "mixed", "missing", "more than declared" or "nothing shown"."""
    if out.refused:
        return f"refused:{named(out.refused)}"
    if "changed each time" in out.text:                 # a list names a study it could not read together
        return "refused:unsettled"
    a, b = seen(world, out.text, "A"), seen(world, out.text, "B")
    wanted = set(shows)
    if a and b:
        return f"mixed (A: {sorted(a)}; B: {sorted(b)})"
    if not a and not b:
        return "nothing shown"
    label, found = ("B", b) if b else ("A", a)
    if wanted - found:
        return f"{label}, missing {sorted(wanted - found)}"
    if exact and found - wanted:
        return f"{label}, more than declared: {sorted(found - wanted)}"
    if label == "B":
        return "B"
    return "A, as found" if any(q in out.text.lower() for q in QUALIFIED) else "A"


def fields(world: World, shown: dict) -> str:
    """The cell's outcome by its page's fields (DE-03): ``shown["points"]``, the point table's rows as shown (each its
    ``TABLE`` fields and its link, "open"), or None where it shows no table; ``shown["columns"]``, ``["slots"]`` and
    ``["table"]``, the header each field is shown under and how (``COLUMNS``, ``CELL_SLOTS``, ``TABLE_PROPS``: each
    whole, both versions'; the auditor's DJ recheck, DK-03), or None; ``shown["chart"]``, the interactive plane
    (``chart_of``), or None where it shows none; and each summary field asked for, its text (``SUMMARY``'s keys), or
    None where it is not shown. One version's ("A", "B") only where every field asked for is shown and each is that
    version's whole: each row's every field; each link the workbench's own point page (no origin or fragment of its
    own, ``/study/point``), naming the study, the row's own point and the version's result and evidence, once each, and
    nothing more (``LINK``); each point of the plane in its series, colour, symbol, size and place as drawn (its own
    where it gives them), its series whole (an empty one too: DJ-02), its axes, and nothing beyond the plane's
    contract (``CHART``, ``PLANE``; the auditor's DF recheck,
    DG-03; its DG recheck, DH-02); each summary field the version's text exactly, not one holding it among more words
    (the auditor's DE recheck, DF-03). Else "fields of neither", "mixed fields", naming the other version's, or "missing
    fields" (asked for, not shown: a row without its point or link among them); "no fields" where none is shown (a
    refusal)."""
    from urllib.parse import parse_qs, urlsplit
    own: dict[str, list[str]] = {"A": [], "B": []}
    neither: list[str] = []

    def place(name: str, value, a, b) -> None:
        if value == a and value != b:
            own["A"].append(name)
        elif value == b and value != a:
            own["B"].append(name)
        elif value not in (a, b):
            neither.append(f"{name} ({value!r})")
    missing = [name for name, value in shown.items() if value is None]
    if len(missing) == len(shown):
        return "no fields"
    if shown.get("columns") is not None:               # which header each field is shown under, and how (DK-03)
        place("the table's columns", shown["columns"], COLUMNS, COLUMNS)
        place("the table's cell slots", shown.get("slots"), CELL_SLOTS, CELL_SLOTS)
        place("the table beyond its contract", shown.get("table"), TABLE_PROPS, TABLE_PROPS)
    rows = shown.get("points")
    if rows is not None:
        expected = {label: {row[0]: dict(zip(TABLE, row)) for row in POINTS[label]} for label in "AB"}
        if sorted(str(r.get("point")) for r in rows) != sorted(expected["A"]):
            neither.append(f"the table's points ({sorted(str(r.get('point')) for r in rows)})")
        study = world.folder.relative_to(world.root).as_posix()
        for row in rows:
            point = row.get("point")
            missing += [f"{point or 'a row'}'s {name}" for name in ("point", "open") if row.get(name) is None]
            if point is None:
                continue
            a, b = expected["A"].get(point, {}), expected["B"].get(point, {})
            for name in TABLE[1:]:
                place(f"{point} {name}", row.get(name), a.get(name), b.get(name))
            link = urlsplit(row.get("open") or "")
            query = {key: values[0] if len(values) == 1 else values
                     for key, values in parse_qs(link.query, keep_blank_values=True).items()}
            place(f"{point} link's origin", (link.scheme, link.netloc, link.fragment), ("", "", ""), ("", "", ""))
            place(f"{point} link's page", link.path, "/study/point", "/study/point")
            place(f"{point} link's names", tuple(sorted(query)), LINK, LINK)
            place(f"{point} link's study", query.get("path"), study, study)
            place(f"{point} link's point", query.get("point"), point, point)
            for part, key in (("result", "sha256"), ("evidence", "evidence")):
                value = query.get(key) or ""            # a version without evidence names none (an older study)
                theirs = {label for label in "AB" if value and value in (world.identities.get(label, {}).get(part) or (
                    {"none"} if label in world.identities else ()))}
                place(f"{point} link's {part}", next(iter(theirs)) if len(theirs) == 1 else value, "A", "B")
    chart = shown.get("chart")
    if chart is not None:
        if sorted(map(str, chart["points"])) != sorted(CHART["A"]["points"]):
            neither.append(f"the chart's points ({sorted(map(str, chart['points']))})")
        for point, drawn in chart["points"].items():
            place(f"{point} on the chart", drawn, CHART["A"]["points"].get(point), CHART["B"]["points"].get(point))
        place("the chart's series", chart["series"], CHART["A"]["series"], CHART["B"]["series"])      # DJ-02
        for axis in ("x axis", "y axis"):
            place(f"the chart's {axis}", chart[axis], CHART["A"][axis], CHART["B"][axis])
        place("the chart beyond its contract", chart["beyond"], (), ())
    for name in SUMMARY["A"]:
        if shown.get(name) is not None:
            place(name, shown[name], SUMMARY["A"][name], SUMMARY["B"][name])
    if neither:                                         # and the other version's, where it shows some too
        return f"fields of neither: {neither[:4]}" + (f"; mixed fields (A: {own['A'][:4]}; B: {own['B'][:4]})"
                                                      if own["A"] and own["B"] else "")
    if own["A"] and own["B"]:
        return f"mixed fields (A: {own['A'][:4]}; B: {own['B'][:4]})"
    if missing:
        return f"missing fields: {missing}"
    return "B" if own["B"] else "A" if own["A"] else "no fields"


def fields_agree(found: str, wanted: str) -> bool:
    """Whether a page's fields (``fields``) are those its cell expects: the version it shows, whole; where it refuses
    or leaves the study out, no fields."""
    if wanted in ("A", "A, as found", "B"):
        return found == wanted[0]
    return found == "no fields"


def agrees(found: str, wanted: str) -> bool:
    """Whether an observed outcome is the expected one: "A, as found" where that is expected (the qualification
    required); "A" accepts A with words of qualification (a baseline may say a date is not recorded, say)."""
    return found == wanted or (wanted == "A" and found == "A, as found") or (wanted == "left out" and
                                                                          found == "nothing shown")

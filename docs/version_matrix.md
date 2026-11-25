# The version handle's acceptance matrix

Written out from `tests/version_matrix.py` (a test keeps the two the same); run by
`tests/evidence/test_version_matrix.py` and `tests/ui/test_version_matrix_pages.py`. The rule it decides
is in the release plan ("Amended by the owner, 2026-11-03") and the version handle plan.

## Cases

| case | change |
|---|---|
| B | nothing changed (the baseline) |
| R | the result replaced by a whole other publication (B: result, evidence, report, figure and record) |
| E | the evidence replaced (B's notes, constructions and source); the result's bytes the same |
| E0 | the evidence sidecar removed; the result the same |
| P | the report and its figure replaced (B's), bound to the same result; the result and evidence the same |
| S | the study record replaced by another publication's (B's title and cost, naming B's result) |
| S2 | the same result with another study record (B's title and cost; it names the same result) |
| D | a member damaged: the evidence sidecar no longer readable as one |
| L | an older study: no evidence sidecar, a report recording no binding, a record naming no result |
| T1 | B published while the consumer reads the study, after it has read the result; a curated record, or its data file, changed while its review export is prepared (at its figure, and at its packet's curves); a curated record's page, its data file changed once the page has read it, or read as B and A restored after |
| T2 | B published after the consumer has resolved its token, before it uses what it read |
| T3 | the study replaced at every reading: a mismatch that persists through every retry |
| ABA | the token's version replaced by B, then A's very bytes restored; then A's record written anew; a curated record's data file B while its review export, or its page, is prepared (at its figure, at its packet's curves, and at each check of its signature apart from its reading), A's very bytes restored before the export is checked, or the page's verification clicked |
| G | a promotion's edge: its child replaced by another version; its parent replaced; its child removed |
| GW | an edge the export could not follow: its warning carried through a review of the bundle to its packet |
| CK | a resume: a completed checkpoint beside another publication, and a calculation resumed part way |
| OA | an operational attempt: a later run's record and settled ledger in the study's folder, before its cost is read or while it is (after its run's record was read), with or without a new publication; another run's records read, then the study's run's restored byte for byte (A, B, A), once or at every reading, for each record of its money (its paid ledger, its log, a budget stop's record, a session step's request record); another run's record beside its run's record unchanged; a request settled in a shared session's ledger before or after the cost's reading of it, or after it and then undone, its run's record unchanged; the session's cap raised, and spent or reserved under, between the reading of its record and of its ledger, or its record then restored; a raise read half made, or interrupted; the record changed at every reading; a reading while another thread raises and spends; a survey run's request record damaged (torn, null, a list, an empty object) beside an earlier survey's discovery.json, with or without a record bound to the run; its request record or its log a link that leads nowhere (to a missing file, to itself, through a file), with or without a record bound to the run; a paid ledger's lifecycle, from its making through each append between requests: a session's ledger put in its live client's place between two requests (a link to nothing, to itself, through a file, to a folder, a folder, no entry, an empty file or a link to one, its first line alone, another of its length), or after another writer appended, then every reading's totals, and the original restored; a run's own ledger damaged or lost when its run opens it, or replaced after, before its first request; a ledger emptied, cut short or replaced since its last writer, read after; a ledger past its writer's last line: a reservation's write cut short (before its bound, after it) or written whole and its sync failed, then the same client's next request; a line after the client's last that is not JSON, not an entry, a settlement never reserved, or torn; a whole last entry without its newline; a run's torn ledger at its opening, then recovered; a journal's recovery where it does not begin with what its mark records, and where it does; each entry of a request (its reservation, its response, its bill uncertain, its settlement) refused before it is written, cut short, unsynced or unmarked, then the same client's next request; the journal put in its place while its append checks it, once it has written, and once it has marked; a cap raise its writer never makes, one its record lacks, and the raises a person makes; a request reserved before its account froze, and two clients of one account; the journal changed in place as its append is made (emptied, its paid request removed, its bill lowered: once checked, once written and synced, once marked) or its mark damaged or shortened once written, and a healthy append's every earlier request and bill at each send; an append and a recovery while another writer holds the journal's lock; another process's request once a recovery has put the recovered journal in its place, before its mark is written, then the journal cut back to what the recovery wrote; an append through a linked folder while the lock is held by the folder's own path; a request asked by another name of the journal (a link to it or a hard link's name, in its folder or another), with no recovery and during one, and through a linked folder during one; a hard link made while an append checks the journal; an append and a recovery whose folder is replaced while it waits for its lock, and while it holds it, another process spending in the folder put in its place; a session's client given its ledger through a link to its folder or to one above it, while its record and ledger disagree, its ledger put in its place since its account was read, and healthy; a client of a session's account given another ledger; a run's ledger through a link to its folder, put in its place since its run opened it and healthy; a run's client given its ledger through a link to its folder or to one above it, the link then led to an empty folder or another opened run's before its first request, between two requests, and between a reservation and its receipt, and kept; a reservation's readback begun with its folder, the folder above it, or a link to a copy put in its place (an older coherent copy), and a folder so replaced once the readback has checked, then every reading of the run's cost and the ledger, a fresh client of it, and a session's account and spending beside such a notice |
| AF | a diagnostic output's report: what it was made of, said to be read as found |
| W | another of ADROIT's writers in a publication's folder while its writer runs: a second reanalysis into it, past its fresh-folder check; B published by the production writer during its calculation and after each of its parts and its record, from another thread and from its own; a Track 1 run drawing its own plane, from this thread, another and another process; each writer that calculates, draws or writes into a study's folder, with the folder held by another thread or process; a figure still rendering where no writer held the folder when another writer, in another thread or process, takes it; a figure that is a link, drawn by another writer while its folder, or its target's, is held; a review packet's writer, its overlay drawn, when another packet writer (another thread, another process) writes into its folder, and each of its files a link, with its folder or its target's held; the review page's packet, another packet writer into its folder as it is rendered; a curated record's review export, or the review queue's, another export into its folder (another thread, another process), and each of its files a link into another folder, with that folder or its own held; a session command's export and its request record, another export into its folder (another thread, another process); a session command refused into a saved study's folder, the folder held or not, and a stopped run's record waiting while a study is published there; two evidence bundles exported to one new ZIP path, the second completed while the first is prepared; an export of another kind into its folder (a review's, the queue's as report.json, a discovery's, a theory check's), after it or at once, and an entry there no export recorded (a person's file, a link, an earlier ADROIT's export), the review timer reading the packet after |
| F | a writer failing part way: an export's replacement failing (an I/O error) before or after each of its files, or at its mark of an export in progress (written, removed, or rewritten), or its writer killed after its first; then the folder read again by each reader of it, a session's run's cost read from it (its request record also damaged: torn, null, a list, an empty object, or a link that leads nowhere, beside an earlier export's discovery.json), and another export written into it (another kind's, or of some of its files) |

## Outcomes

- **A**: everything the boundary shows or writes is A's: each observable its row declares (a part, its
  verdict, its cost) shown with A's mark, no mark of B anywhere; in the baseline, nothing it does not
  declare.
- **A, as found**: A's, and it says what it could not check (legacy, as found, recording no link).
- **B**: everything is B's, each declared observable (B was published while it read: its files read
  again together).
- **refused:part**: nothing is shown or made, naming the part (result, evidence, presentation, record),
  or that the study's files changed each time they were read (unsettled); a curated record's
  review export whose record or data file changed while it was prepared, nothing written (record).
- **A then refused**: A's very bytes restored, A's; A's record written anew (another date), refused.
  The review page: A's source and A's images shown, as A's rendering wrote them; its figure
  verification, bound to the packet shown, refused once the folder holds another. A curated record's
  page: A's figure and A's signature state shown; its verification, bound to A, refused once the
  data file is another.
- **left out**: a list leaves out a study whose files changed each time it read them, as it leaves out a
  record it cannot read.
- **named**: an edge to another version, or to nothing, is named unavailable; B nowhere.
- **carried**: the export's warning about an edge is in the review of the bundle and its packet.
- **dated**: a resume's dates are its checkpoint's own, never the publication beside it.
- **own cost**: the cost shown on the card, in Studies and by `adroit studies` is the study's own
  run's, or its record's saying so, never a later run's, whenever that run's records are written,
  restored over or read beside its own.
- **one owner**: the publication's folder is its writer's while it runs: a second reanalysis is refused
  before it calculates; another of ADROIT's writers waits, then publishes whole, or, from its own
  thread, is refused, nothing of it written; the run returns A. A review packet's folder is its
  writer's from its first file to its record: another packet writer waits, then writes its packet whole;
  the reader accepts each packet whole as its writer's, never one's record with another's overlay; each
  of its files is written to its own entry, never through a link into another folder; its page shows
  the packet its writer wrote. A curated export's folder is its writer's from its first file to its
  last: another export waits, then writes its own whole, never one record's packet beside another's
  report or curve; each file to its own entry, never through a link. A session command's draft or
  report and its request record are one export; a command refused before it sends anything writes
  nothing into the folder it was given, and a study there keeps its every byte and its cost. A
  bundle's new ZIP is its export's: one written there while it is prepared is left as it is, and the
  later export refused, nothing of it kept.
- **whole or incomplete**: an export that fails part way leaves its folder's earlier export whole, put
  back; one whose writer was killed leaves the folder saying it is incomplete (`EXPORT_INCOMPLETE.txt`),
  which each reader of it reads so, until that export's files are written whole again (another export
  into the folder keeps it); one whose mark could not be removed says so, the folder marked; a
  session's run is charged with the session its own records name; never one export's file beside
  another's as if whole.
- **as found**: the report says what it was made of, read as found.
- **N/A**: the cell does not apply, with why.

## Rows

| row | kind | call site | shows | its token names |
|---|---|---|---|---|
| history.row | held | `ui/pages.py:studies_page` | record, headline, cost | — |
| history.facts | held | `orchestrator/annotations.py:held_facts` | record, headline | — |
| cli.studies | held | `orchestrator/cli.py:studies_tree` | record, cost | — |
| pickers.track1 | held | `ui/wizards.py:_track1_studies` | record | — |
| pickers.reanalysis | held | `ui/reanalysis.py:_sources` | record | — |
| models.analyses | held | `ui/model_library.py:analyses` | record | — |
| study.page | held | `ui/pages.py:study` | result, evidence, presentation, record, headline, cost | — |
| point.table | held | `ui/points.py:points_panel (its links)` | result, evidence | — |
| study.cost | held | `ui/pages.py:study_cost` | cost | — |
| setup.estimate | held | `orchestrator/setup_check.py:estimate` | record | — |
| revisit.updates | held | `orchestrator/revisit.py:updates` | result, evidence, record | — |
| classic.report | held | `workbench/server.py:report_view` | result, presentation | — |
| live.report | held | `ui/pages.py:_live_report` | result, presentation | — |
| export.cli | held | `evidence/cli.py:export` | result, evidence, presentation, record | — |
| point.cli | held | `evidence/cli.py:point` | result, evidence | — |
| tables.cli | held | `evidence/cli.py:tables` | result | — |
| figures.cli | held | `evidence/cli.py:figures` | result, presentation | — |
| review.queue | held | `constraints/review_queue.py:load_selected` | result, evidence | — |
| agents.saved | held | `orchestrator/cli.py:agents` | result | — |
| assist.saved | held | `orchestrator/cli.py:assist (a single-idea study)` | result | — |
| reuse.track1 | held | `orchestrator/physical_eligibility.py:_saved` | result, evidence | — |
| point.page | token | `ui/points.py:point_page` | result | result, evidence |
| point.link | token | `evidence/points.py:explain` | result, evidence | result, evidence |
| download.tables | token | `ui/exports.py:files tables` | result | result, evidence |
| download.figures | token | `ui/exports.py:files figures` | result, presentation | result, presentation |
| download.references | token | `ui/exports.py:files references` | result, evidence, record | result, evidence, record |
| download.bundle | token | `ui/exports.py:files bundle` | result, evidence, presentation, record | result, evidence, presentation, record |
| reanalysis.open | token | `orchestrator/reanalysis.py:open (Run again)` | result, evidence | result, evidence |
| reanalysis.preview | token | `orchestrator/reanalysis.py:preview (the draft's)` | result, evidence | result, evidence |
| revisit.card | token | `ui/revisit.py:update_card → reanalysis.open` | result, evidence | result, evidence |
| classic.file | token | `workbench/server.py:route /file` | result | result |
| promote.parent | token | `orchestrator/promote.py:parent_result` | result | result |
| approve.idea | token | `ui/pages.py:approve_panel (Constrain the approved models)` | result | result |
| records.packet | token | `ui/records.py:_packet` | result, evidence | result, evidence |
| reanalysis.run | publication | `orchestrator/reanalysis.py:run (its child, as published)` | result, evidence, presentation, record | — |
| review.packet | packet | `constraints/experimental_review.py:plot_packet → _reviewed (verify-figure)` | — | — |
| review.page | packet | `ui/experimental_review.py:_review_packet (its images; Verify the figure by hand)` | — | — |
| records.export | export | `constraints/review_cli.py:packet_command (records review --out)` | — | — |
| queue.export | export | `constraints/review_cli.py:queue_command (records queue --out)` | — | — |
| session.export | export | `orchestrator/preflight.py:session_export, record_requests (models step, models paper, constraints discover, constraints resume, experiments extract --out)` | — | — |
| records.page | curated | `ui/records.py:record_page (its figure, data, packet and signature state; Mark as verified)` | — | — |
| graph.export | graph | `evidence/archive.py:_promoted` | — | — |
| graph.review | graph | `constraints/review_queue.py:load_selected (promotion)` | — | — |
| graph.bundle_review | graph | `constraints/review_queue.py:load_selected (bundle)` | — | — |
| graph.packet | graph | `constraints/review_packets.py:packet_for` | — | — |
| bundle.verify | archive | `evidence/archive.py:verify_bundle` | — | — |
| bundle.replay | archive | `evidence/replay.py:replay_bundle` | — | — |
| bundle.viewer | archive | `ui/batch_page.py:_show_bundle (Open a bundle)` | — | — |
| resume.track1 | resume | `orchestrator/runs.py:restored_dates (Track 1)` | — | — |
| resume.native | resume | `orchestrator/native_fit.py:run (resume)` | — | — |
| cost.attempt | cost | `orchestrator/accounting.py:held_cost (the card, the Studies line, adroit studies)` | — | — |
| theory.report | diagnostic | `theory/cli.py` | — | — |
| fog.report | diagnostic | `orchestrator/fog_cli.py:write` | — | — |
| intake.report | diagnostic | `orchestrator/catalog_cli.py:_draft_report` | — | — |
| discovery.report | diagnostic | `orchestrator/discovery_cli.py:_report` | — | — |
| advisory.report | diagnostic | `orchestrator/research_assistance.py:report` | — | — |

## Cells

| row | B | R | E | E0 | P | S | S2 | D | L | T1 | T2 | T3 | ABA | G | GW | CK | OA | AF | W | F |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| history.row | A | A | A | A | A | A | A | A | A | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| history.facts | A | A | A | A | A | A | A | A | A | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| cli.studies | A | A | A | A | A | A | A | A | A | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| pickers.track1 | A | A | A | A | A | A | A | A | A | B | N/A (n1) | left out | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| pickers.reanalysis | A | A | A | A | A | A | A | A | A | B | N/A (n1) | left out | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| models.analyses | A | A | A | A | A | A | A | A | A | B | N/A (n1) | left out | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| study.page | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| point.table | A | A | A | A | A | A | A | A | A | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| study.cost | A | A | A | A | A | A | A | A | A | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| setup.estimate | A | A | A | A | A | A | A | A | A | B | N/A (n1) | left out | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| revisit.updates | A | A | A | A | A | A | A | A | A | B | N/A (n1) | left out | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| classic.report | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| live.report | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | left out | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| export.cli | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | one owner | N/A (n8) |
| point.cli | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| tables.cli | A | A | A | A | A | A | A | A | A | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| figures.cli | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| review.queue | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| agents.saved | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| assist.saved | A | A | A | A | A | A | A | A | A, as found | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| reuse.track1 | A | A | A | A | A | A | A | A | refused:evidence | B | N/A (n1) | refused:unsettled | N/A (n2) | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| point.page | A | refused:result | refused:evidence | refused:evidence | A | A | A | refused:evidence | A, as found | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| point.link | A | refused:result | refused:evidence | refused:evidence | A | A | A | refused:evidence | A, as found | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| download.tables | A | refused:result | refused:evidence | refused:evidence | A | A | A | refused:evidence | A | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| download.figures | A | refused:result | A | A | refused:presentation | A | A | A | A, as found | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| download.references | A | refused:result | refused:evidence | refused:evidence | A | refused:record | refused:record | refused:evidence | A, as found | refused:result | A | refused:unsettled | A then refused | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| download.bundle | A | refused:result | refused:evidence | refused:evidence | refused:presentation | refused:record | refused:record | refused:evidence | A, as found | refused:result | A | refused:unsettled | A then refused | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | one owner | N/A (n8) |
| reanalysis.open | A | refused:result | refused:evidence | refused:evidence | A | A | A | refused:evidence | A | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| reanalysis.preview | A | refused:result | refused:evidence | refused:evidence | A | A | A | refused:evidence | A | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| revisit.card | A | refused:result | refused:evidence | refused:evidence | A | A | A | refused:evidence | A | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| classic.file | A | refused:result | A | A | A | A | A | A | A | N/A (n9) | A | N/A (n9) | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| promote.parent | A | refused:result | A | A | A | A | A | A | A | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| approve.idea | A | refused:result | A | A | A | A | A | A | A | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| records.packet | A | refused:result | refused:evidence | refused:evidence | A | A | A | refused:evidence | A, as found | refused:result | A | refused:unsettled | A | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | N/A (n7) | N/A (n8) |
| reanalysis.run | A | refused:result | refused:evidence | refused:evidence | refused:presentation | refused:record | refused:record | refused:evidence | N/A (n10) | refused:result | N/A (n11) | refused:unsettled | A then refused | N/A (n3) | N/A (n3) | N/A (n4) | N/A (n5) | N/A (n6) | one owner | N/A (n8) |
| review.packet | A | N/A (n12) | N/A (n12) | N/A (n12) | refused:presentation | N/A (n12) | N/A (n12) | N/A (n12) | N/A (n12) | refused:presentation | N/A (n12) | N/A (n12) | N/A (n12) | N/A (n12) | N/A (n12) | N/A (n12) | N/A (n12) | N/A (n12) | one owner | N/A (n8) |
| review.page | A | N/A (n13) | N/A (n13) | N/A (n13) | A then refused | N/A (n13) | N/A (n13) | N/A (n13) | N/A (n13) | A then refused | A then refused | N/A (n13) | A | N/A (n13) | N/A (n13) | N/A (n13) | N/A (n13) | N/A (n13) | one owner | N/A (n8) |
| records.export | A | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | refused:record | N/A (n14) | N/A (n14) | A | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | one owner | whole or incomplete |
| queue.export | A | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | one owner | whole or incomplete |
| session.export | A | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | N/A (n14) | one owner | whole or incomplete |
| records.page | A | N/A (n15) | N/A (n15) | N/A (n15) | N/A (n15) | N/A (n15) | N/A (n15) | N/A (n15) | N/A (n15) | A then refused | N/A (n15) | N/A (n15) | A | N/A (n15) | N/A (n15) | N/A (n15) | N/A (n15) | N/A (n15) | N/A (n7) | N/A (n8) |
| graph.export | A | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | A, as found | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | named | N/A (n17) | N/A (n16) | N/A (n16) | N/A (n6) | N/A (n7) | N/A (n8) |
| graph.review | A | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | A, as found | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | named | N/A (n17) | N/A (n16) | N/A (n16) | N/A (n6) | N/A (n7) | N/A (n8) |
| graph.bundle_review | A | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | A, as found | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | named | carried | N/A (n16) | N/A (n16) | N/A (n6) | N/A (n7) | N/A (n8) |
| graph.packet | A | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | A, as found | N/A (n16) | N/A (n16) | N/A (n16) | N/A (n16) | named | carried | N/A (n16) | N/A (n16) | N/A (n6) | N/A (n7) | N/A (n8) |
| bundle.verify | A | A | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | A | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n6) | N/A (n7) | N/A (n8) |
| bundle.replay | A | A | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | A | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n6) | N/A (n7) | N/A (n8) |
| bundle.viewer | A | A | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | A | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n18) | N/A (n6) | N/A (n7) | N/A (n8) |
| resume.track1 | dated | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | dated | N/A (n19) | N/A (n6) | N/A (n7) | N/A (n8) |
| resume.native | dated | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | N/A (n19) | dated | N/A (n19) | N/A (n6) | N/A (n7) | N/A (n8) |
| cost.attempt | own cost | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | N/A (n20) | own cost | N/A (n6) | N/A (n7) | N/A (n8) |
| theory.report | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | as found | N/A (n7) | N/A (n8) |
| fog.report | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | as found | N/A (n7) | N/A (n8) |
| intake.report | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | as found | N/A (n7) | N/A (n8) |
| discovery.report | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | as found | N/A (n7) | N/A (n8) |
| advisory.report | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | N/A (n21) | as found | N/A (n7) | N/A (n8) |

Not applicable, why:

- n1: a row that resolves the study itself has no earlier token: its changes are made after its resolution (R–D)
- n2: a row that resolves the study itself names no version to return to
- n3: the row has no promotion graph
- n4: the row resumes no checkpoint
- n5: the cost bound to a run's attempt is decided once, in the row cost.attempt (the study's card, its line in Studies and `adroit studies` read it)
- n6: the row is not a diagnostic output (the owner's decision 3)
- n7: the row's boundary writes nothing another of ADROIT's writers shares: of the rows, only a publication, a review packet or an export shares its folder with another writer, and only a bundle's export a new path a person names; the row's changes by others are its other cases. Every other writer of a new file a person names (the usability report, a signal draft, an approved model, a model export, a review timer, a session start, an experimental import's folder, the evidence commands' folders) is outside the handle, with its own create-only contract (test_dm_fixes, test_dl_fixes)
- n8: the row's writer failing part way is not a case of this matrix: it is decided for the exports a person's folder holds (the auditor's DJ recheck, DK-05)
- n9: the classic route sends one file, read once and checked against the token's digest: there is no second part to join, nor a resolution to repeat
- n10: a reanalysis publishes a new study: it is never an older one
- n11: the run's check of its child is its last use of it: nothing is read after it
- n12: a review packet is its own folder's page, overlay and record, written once by its writer and read once by the figure verification: it has no study result, evidence or record, no older form, token, graph, resume or cost (its P and T1 replace its overlay and its page; W, another packet writer; its page's ABA, B's packet written and A's very bytes restored before the verification)
- n13: the review page shows one packet beside one source, as its rendering wrote it: it has no study result, evidence or record, no older form, graph, resume or cost, and reads nothing again (T3: no reading to repeat); its T1 is B's packet in its folder before its images are shown, its T2 A's source's packet drawn otherwise once they are, its P B's overlay there, its ABA A's very bytes restored, its W another packet writer
- n14: an export is written once, whole, into a folder a person names, for a person to read: it has no study result, evidence or record of its own, no older form, token, graph, resume or cost, and what reads it again reads it whole or as incomplete (its F) (its B, the export as its writer prepared it; its W, another export into its folder, of its kind or another's, and each of its files a link, and a session command refused into a study's folder; the review's T1 and ABA, its record or data changed while it is prepared)
- n15: a curated record's page shows one reading of its record and data file: its figure, data, packet and signature state, and the version its verification binds; it has no study result, evidence or record, no older form, graph, resume or cost, and reads nothing again but after a verification (T3: no reading to repeat); its T1 is its data file changed once read, or read as B and A restored after, its ABA B while its figure is drawn and its signature checked, A's very bytes restored
- n16: this row's boundary is decided by its own cases (G, GW; its nodes are each read as a version: see the held and token rows)
- n17: only a review of an exported bundle, and its packet, carry an export's warnings
- n18: this row's boundary is decided by its own cases (a bundle is read once, as bytes)
- n19: this row's boundary is decided by its own cases (CK)
- n20: this row's boundary is decided by its own cases (OA)
- n21: outside the handle by the owner's decision 3: a diagnostic output is read as found, and says so (AF)

# The workbench's model-intake completion and cost (2026-10-23)

The owner's report: model intake (an idea in words turned into a typed draft by a language model) completed with
both providers, but

1. the live job page showed **$0**, though the session's ledger holds $0.054107, $0.048011 (Anthropic) and $0.057540
   (OpenAI) for the three runs of 23 October;
2. **"Open the results"** opened `/study?path=…`, the physics-study viewer, which said "Not a study … the run may
   still be going"; the right page (the draft's review) was only the small "Review and refine the model" link.

Branch `ui23-fixes`, from `3012843`; the repair is `032f6c7`.

## Causes

- **The cost.** `engine.spend` read only `study.json`'s `cost_usd` or the log's last `spent $x`. Model intake writes
  neither: its requests are journalled in its session's `paid.jsonl` (reserved → received → settled), and its
  command prints the session's status as one JSON line (`{"cap": …, "spent": …}`). With no match, `spend` returned
  0.0, and the page showed it as a confirmed `spent $0.00 of $1.00`. The same held for every session job
  (`experiments extract`, `constraints discover`) and for a paid run that stopped at its budget (its spending is in
  its budget-stop `result.json`).
- **The destination.** `pages.live` showed "Open the results" whenever `report.md` existed, and every intake,
  experimental and discovery command writes a `report.md` (a summary, not a study). The button did not look at what
  the run had made.
- **The old link.** `/study` on a folder without `study.json` said "the run may still be going" without reading the
  job's status.

## Changes

| what | where |
|---|---|
| What a run made, decided by its command: a headline ("Draft ready for review", not "Study complete"), a sentence that says no physics calculation was run, the primary action to the page that reviews it, and after a stop the next action | `adroit/ui/outcomes.py` (`outcome`, `kind_of`) |
| Its cost from its authoritative record, in three figures: this run's, the session's total, the approved cap (or a run's approved budget). A missing record says "not available", never $0 | `outcomes.cost`, `outcomes.cost_lines` |
| A session command records **its own** ledger requests, `paid_requests.json` beside its output (the identifiers its budgeted clients reserved), whether it completed or stopped; the page sums those requests in the ledger, so a refinement never counts its parents' spending again | `model_intake.RunRequests`, `Intake.requests`, `Intake.request_ids`, `preflight.record_requests`; `models step`, `models paper`, `experiments extract` |
| A run from before that record (the evidence runs): the ledger totals its log printed before its first request and at its end (both read from the ledger then; the "before" to $0.0001); without both, "not available" | `outcomes._from_log` |
| The live view: the outcome card (headline, sentence, cost lines and their source, primary button), the run's summary folded below; "Open the results" is gone | `pages.live`, `pages.show_outcome` |
| `/study` on a folder that is not a study: what it is, from its job's status, with the button to its review page; a CLI draft without a job is offered too | `pages.not_a_study` |
| A session with no draft: "running" only while one of its runs is, else which runs ended without a draft and why, its spending and cap, and a new intake | `model_library._no_draft` |
| The draft page's session money at the cents an interpretation needs, from the ledger | `model_library._session_money` |
| Activity: a completed run's headline from its outcome and its review link | `activity._card` |
| `experiments import` and `reanalyse run` refused every workbench launch ("must be new or empty": the job's own `job.json` and `log.txt` are there first); a folder holding only a workbench job's files now counts as fresh | `runs.fresh`, `experimental_cli.import_files`, `Reanalysis.run` |
| A drafted signal record opens on Add a signal, checked | `/new/anomaly?record=…` (`wizards.anomaly_page`) |
| The running version and git revision: at the end of every page's menu (`v1.0.0 · 3012843`, `+changes` when tracked files were edited), and in full on `/about` (revision, branch, commit date, uncommitted changes, checkout, Python). Read once when the workbench starts, locally: git with optional locks off, else the repository's files (`HEAD`, its ref, `packed-refs`; a worktree's `.git` file), else "unknown" with the reason | `adroit/ui/about.py`, `style.nav`, `app.build_pages` |

Unchanged: drafts, sessions and their integrity hashes, approvals, the ledger's rows and the run folders' existing
files. `paid_requests.json` is a new file beside them. Reviewing a saved output reads files only: no request.

## The job types (every command the workbench launches)

| command | launched from | output in its folder | completion destination | cost read from |
|---|---|---|---|---|
| `track1` | Constrain a model (portal, model, approved idea model) | `study.json`, `result.json`, `report.md` | the study (`/study`) | free (no `--budget`): $0 |
| `idea` (fields, Lagrangian) | Constrain a model | `study.json`, `result.json`, `report.md`, `models/` | the study (approve models there) | free: $0 |
| `idea --text` (paid) | Constrain a model | as above; at a budget stop `result.json` (`budget_stopped`) and `report.md` | the study; after a stop, the stop's report on the live view | `study.json`, the log's "spent", or the stop record's committed dollars |
| `lagrangian --derive` (paid) | Constrain a model | `study.json`, `result.json`, `report.md`; at a stop the stop record | the study | `study.json` or the stop record; else "not available" (it prints no "spent" line) |
| `signal` | Signal best fits | `study.json`, `result.json`, `report.md` | the study (promote there) | free |
| `single-idea` | Explain a signal | `study.json`, `result.json`, `report.md` | the study | free |
| `native-fit` | Native fit | `study.json`, `result.json`, `report.md` | the study | free |
| `reanalyse run` | Reanalyse | `study.json`, `result.json`, `report.md`, `reanalysis.json` (refused every launch before this change) | the study | free |
| `promote` (paid with `--budget`) | a signal study | nothing (its studies are written under the signal study) | the signal study, which lists the promoted studies | the log's "spent"; a stop's record named in the log |
| `anomaly draft` (paid) | Add a signal | nothing (the record is written to its `--out` YAML) | `/new/anomaly?record=…`, the record checked | the log's "spent" |
| `models step` (paid unless typed/fields) | Model library, intake | `intake.json`, `report.md`, `paid_requests.json` | **the draft** (`/models/intake?session=…&step=…`) | the session's ledger (this run's requests); session total and cap |
| `models paper` (paid) | intake, paper | as `models step` | the draft | as `models step` |
| `experiments import` | Add a limit | `experimental.json`, `report.md` (refused every launch before this change) | `/experiments/view?reference=…` | free |
| `experiments extract` (paid) | an experimental session | `extraction.json`, `report.md`, `paid_requests.json` | `/experiments/view?reference=<output revision>`, and the session to continue | the ledger of the session that holds the cap (a discovery session's when shared) |
| `constraints discover` (paid) | a model's page, after approval | `discovery.json`, `report.md` (also after a budget stop, which its state records) | `/constraints/discovery?session=…` | the discovery session's ledger (the run opened the session, so all of it is the run's) |

Since the workflow audit's repairs (2026-10-24, the workflow acceptance repair record of 2026-10-24), a paid command
without a session (`anomaly draft`, `idea --text`, `lagrangian --derive`, `promote --budget`) keeps its own paid
ledger in its job's folder, and its cost is read from that, not from its log's "spent" line; a signal record draft is
written to the run's own file and opened only while it is still that draft.

A batch holds only the wizard commands above (`wizards._start`); each item is an ordinary job with the same outcome.
The classic page (`--classic`) launches no intake. `anomaly check` and Track 1's `--resume` are not new launches.

## Tests

New: `tests/ui/test_run_outcomes.py` (11), `tests/ui/test_about.py` (3), `tests/orchestrator/test_run_requests.py`
(4). The journeys run offline: the provider's SDK is a scripted stub answering in each provider's own format (an
Anthropic `Message`, an OpenAI `Response`), behind the real budgeted client and the session ledger; the workbench's
launch runs the real command line in-process. Nothing is sent.

| test | failing before (`3012843`) | after |
|---|---|---|
| journey, Anthropic and OpenAI: idea → provider and budget → approve → run → cost → "Review model draft" → draft; refinement in the session; reload; the older draft; the old `/study` link | the live page showed `spent $0.00 of $1.00 …` and the button "Open the results"; no "Draft ready for review" | passes for both: this run $0.0208, the refinement alone $0.0140, the session total $0.0348 (both models at $4 and $20 per million tokens); two provider requests in all, none on review or reload |
| a failed request (provider error) | only a "failed" badge and $0.00 | "Interpretation: failed", the provider's error class, $0 settled and the reservation shown as uncertain, a new intake offered; the session page does not say "pending" |
| an answer that is not a model (three billed attempts) | as above | failed, the three requests' cost |
| a completed run whose `intake.json` is missing | "Open the results" to "Not a study" | "Finished, but the draft is not available", the session's drafts one click away |
| a budget refusal (a $0.01 cap) | $0.00, no stop explained | "Stopped at the cap before a paid request", "$0 (no paid request was sent)", the cap, a new intake; the log has the raise-cap command |
| a paid run with no spending record | `spent $0.00 of $1.50` | "This run: not available …", the approved budget |
| Activity | "completed", no link | "Draft ready for review", "Review model draft" |
| every job type's destination and cost; a run from before the request record; a refused refinement back to its draft | `adroit.ui.outcomes` did not exist | pass |
| build tag and `/about`; git, repository files, nothing | `adroit.ui.about` did not exist | pass |
| ledger request states; a command records only its own requests; a job folder counts as fresh; `experiments import` into a job folder | `Intake.requests`, `RunRequests`, `runs.fresh` did not exist; the import exited 2, "output directory must be new or empty" | pass |

How "before" was run: the tree at `3012843` exported with `git archive` into a scratch folder, the three new test
files copied into it, and the same interpreter run with `PYTHONPATH` on that tree: 18 failed. After: 18 passed.

Copies of the four intake runs of the owner's runs folder (23 October, and one of 13 October), their sessions and
assets, were read in a scratch folder (job records repointed there): each shows "Draft ready for review", "Review
model draft" to its session and step, this run $0.0541, $0.0480, $0.0575 and $0.0698 (the ledger's settled costs;
read from their logs, which predate the request record), and the session total the same. A workbench started from
the branch on 127.0.0.1:18766 over those copies (every `ADROIT_*` folder in scratch; stopped afterwards) served, by
curl: the Anthropic and OpenAI live pages and the old `/study` link with the draft, its button and these costs (no
"Open the results", no "may still be going"), Activity with "Review model draft", the older draft's page with
"This session: $0.0698 spent of its approved $1.00 cap", and `v1.0.0 · 3012843+changes` in every menu (the edits
were not yet committed) with the branch on `/about`. Nothing in the owner's folders was changed or requested again.

Targeted runs after the change: `tests/ui` (165 passed); the orchestrator, library and agent tests of the changed
modules with the new ones (144 passed); `tests/orchestrator/test_cli.py` and `test_r7_journeys.py` (13 passed).

## Not verified

- No real browser: the pages were driven by NiceGUI's headless `User` and fetched with curl from a scratch server
  (127.0.0.1:18766, scratch folders); layout and refresh timing on screen were not seen.
- No live provider call: the provider formats are the SDKs' own types, filled offline. A provider whose usage is
  missing leaves the request's reservation as "not yet known", as the ledger does.
- `models paper` and `experiments extract` record their requests the same way as `models step`, but their
  journeys (a PDF, a source batch) were not run end to end here.
- The log fallback for runs before the request record reads the "before" total as printed (to $0.0001); where the
  session holds an uncertain reservation the split between settled and reserved is not recoverable and is said so.

## For the owner

- `anomaly draft` writes its record outside the run folder; at a budget stop the shared budget-stop handler makes a
  folder of the record's `.yaml` path (`cli._budget_boundary`), not changed here.
- `lagrangian --derive` prints no "spent" line; its cost appears once its study is written, and as "not available"
  if it fails before that.
- The Studies page's "total spent" is the studies' total; intake, extraction and discovery spending is in their
  sessions' ledgers, not added there.

# M39–M40 — saved-study reanalysis and complete researcher journeys

Owner-authorized 10 October 2026. **M39/M40 complete**: 131 focused/headless,
1468 fast and 25 slow checks passed; five fresh studies exported/replayed, two
physical-point replays matched. Paid spend $0.210006 Anthropic/$0 OpenAI.
Final report: local (summary); external audit handoff:
local (summary). Remaining M32 release audit stays open.

M39 opens a saved model/anomaly/study as an immutable analysis draft, retaining its
exact original model/data/profile/request and chronology. Select a target track,
model revision, anomaly/experiment and numerical options; review differences and
missing/unsupported inputs before a fresh child run. Refine models/experimental
sources through their existing immutable libraries. No silent “latest” lookup or
activation, no overwriting parent results, no reuse of stale checkpoints. Reuse
compatible source assets/model matching; physical-point reuse still follows M38's
exact model/point/current-provenance rules. Legacy unknown dates/approvals stay unknown.

M40 independently exercises both complete journeys through CLI and headless UI:
model idea/fields/TeX/image/paper → editable review → personal revision → Track1 →
Track2 comparison; experimental table/image/PDF/text → interpreted/confirmed review
→ supported private analysis → physical eligibility/ranking → saved study → changed
model/data/profile → reanalysis in either direction → dated evidence/export/replay.
Original analysis bytes/dates remain historical. Unsupported papers/workspaces,
missing parameters, unknown properties and unavailable calculations remain explicit.

Use controlled source fixtures and independent numerical expectations rather than
a second LLM's agreement. Preserve API budgets/journals and original source hashes.
Run focused/full fast/slow regression, public CLI routes and real deterministic
both-track/reanalysis jobs under frozen source. Keep private catalogs isolated in
tests, one nice10 worker/two numerical threads, no DM10 held-out work or production
expert signatures. Real-provider checks, if used, have an explicit total --budget;
no further human-time claim is inferred from synthetic sessions.

On successful closure, publish milestone receipts and a separate dated external
audit handoff covering all work since the initial audit/remediation, declared
component fidelity/limits, validation history (including failures), remaining
researcher/release tasks and reproducible audit entry points. Independent audit
must verify claims from code and sources, not accept previous reports as proof.

## Reopen, edit and run

In the workbench, open a saved study and select **Reopen saved inputs for a new analysis**,
or visit `/reanalyse`. Approved model pages and confirmed anomaly results also
link to this workflow. The form loads the original request. Choose the target
track, a pinned personal model or experimental profile and edit numerical options.
Save changed inputs as a new draft, review the differences and blockers, enter
your reviewer name and confirmation, then launch the fresh child analysis.
Changing the editor after review requires another save/review.

The same deterministic service is available through the public CLI:

```sh
adroit reanalyse open path/to/study/result.json --target signal
# Copy the returned reanalysis:... reference; choose an experiment and options
# in a YAML request based on its returned request object.
adroit reanalyse edit reanalysis:DRAFT_HASH --request revised_request.yaml
adroit reanalyse model reanalysis:DRAFT_HASH --model catalog:MODEL_REVISION
adroit reanalyse review reanalysis:DRAFT_HASH
adroit reanalyse run reanalysis:DRAFT_HASH --out path/to/study/new_child \
  --expected-hash REVIEW_HASH --by 'Researcher name' --confirmed
```

Use the **new** draft reference returned by each edit/model selection. `--target
track1` selects the reverse direction; `--model-index` selects an exact saved
physical model when opening a multi-model Track 2 request. A bare NR operator
result cannot be converted into a unique physical completion automatically.
Omit `--target` to keep the original workflow, including a saved single-idea study.
These commands do not dispatch an LLM and require no dollar budget.

Each run requires a fresh output directory. A saved-study child must be inside
its source study directory so the complete graph can be exported; the workbench
creates it there automatically. The child stores `reanalysis.json`
and an evidence lineage certificate with the pinned draft, reviewed hash,
reviewer/date and parent result/evidence hashes. Historical result and evidence
bytes are preserved; a study's child index can grow. Saved source models remain
immutable. For a changed model, refine/select a new catalog revision or explicitly
review a supported inline model; the latter is saved privately before calculation.
Updated experimental inputs use their own confirmed/validated revision reference.
Stale source/profile validation blocks numerical use rather than selecting latest.

The workbench displays jobs only within `ADROIT_RUNS_DIR`. For an external saved
study, use the CLI with a child directory inside that study, or start the
workbench with `ADROIT_RUNS_DIR` set to the study's containing directory.
The UI refuses an out-of-directory launch before dispatch.

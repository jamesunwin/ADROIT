# Requested-result record review — M21

Use a completed study to find the source reviews and calculations that actually
block its conclusions. The queue uses saved evidence; it performs no physics,
source download or paid call, and never changes a saved verdict.

```bash
uv run adroit records queue --run runs/my_track1 --out runs/review_queue.json
uv run adroit records queue --run runs/my_signal --run runs/my_single_idea
uv run adroit records queue --run runs/promotion_evidence.zip
uv run adroit records review RECORD_ID --run runs/my_track1 --out runs/record_review
```

`--run` accepts a selected result JSON, a completed study folder or a verified
evidence ZIP. Promotions follow their explicit parent/child graph. Other results
are not searched automatically. `--include-scan` adds diagnostic grid checks;
the default prioritizes thermal/fit points, candidates and unresolved studies.

## Priorities and separate actions

Tasks retain the exact physical input, saved status, source identity and pending
reason. Duplicate scientific observations from repeat views do not inflate the
priority. The deterministic ordering is:

1. Pending requested conclusions before unresolved checks of already excluded points.
2. More distinct blocked physical points, then more selected studies.
3. Source verification and missing inputs before new recasts, with a stable task-ID tie break.

An excluded point stays excluded: reviewing an unrelated pending search cannot
undo an existing exclusion. Priority counts are provenance/impact counts, not
estimates of scientific discovery probability or person-hours saved.

Source review, missing physical input, missing backend, additional domain
validation and a new recast/source likelihood have separate tasks. For example,
an unreviewed native-90% curve needing a 95% comparison has both a human-review
prerequisite and a likelihood/recast prerequisite. Signing it does not convert
its CL, transfer its benchmark or widen a detector's validated range. Requested
calculations must still be completed and the physical point re-evaluated.

The Records workbench page has a completed-study selector. Open its queue, then
the linked record panel to see the source figure/table, current curves and
assumptions beside the saved numerical comparisons and old/new diff. The same
queue builder serves CLI, UI, promotion graphs and evidence archives. New
evidence sidecars contain a queue snapshot; ZIPs contain `review_queue.json`
and `review_queue.md` for each study node.

## Scientific changes and signatures

New human approvals record `verification_sha256`, binding the source/figure,
quantity, assumptions, benchmark, native CL/construction, version, inline data
and that record's selected panel/channels. Editing these invalidates the approval
for future calculations while retaining its historical name/date. Editing another
panel of a shared file or a display-only name does not force an unrelated review.
Cached parsing/fingerprints are keyed by exact metadata and file size/mtime/ctime,
so actual edits are noticed without manually clearing a cache.

The current nine pre-M21 approvals are preserved in an explicitly labelled
`review_bindings.yaml` migration baseline. These hashes detect relevant changes
from 8 October 2026 onward. They **do not claim a new human review**, or prove the
identity of bytes on the original approval date. Generic historical approvals
without a binding remain visibly `legacy_unbound`; they are not relabelled current, and they are not usable: a name and
date bound to nothing cannot say what was approved, so such a record waits for a person to verify it again (the audit
loop's AL1-08, 2026-11-14; no record needs the state at 1.0.0).
No additional production record was signed while implementing M21.

```bash
uv run adroit records show RECORD_ID
uv run adroit records verify RECORD_ID --by "Your name"
```

Verification is the expert's assertion that they inspected the source, data and
assumptions. The UI requires that assertion and refuses a click if the displayed
scientific payload changed before signing. CLI users can supply the reviewed
packet's `current.verification_binding.current_sha256` when present, or the
`fingerprint(record)` value, with `--expected-hash`. Re-reviewing stale content
retains the prior approval in `verification_history`; an already current review
is not signed again. Assistant packets are evidence only and cannot sign.

Human signatures are plain provenance assertions, not cryptographic identity
certificates. The source PDF URL/page and record/data identity are retained;
M21 does not silently fetch or judge a revised paper or certify all detector
likelihood assumptions.

## Historical comparisons and numerical evidence

The review packet records scientific metadata changes and data hashes. When the
selected archive contains the old data bytes, it also reconstructs the old
record's own curves. Without those bytes it says so; today's curves are not
presented as a historical baseline. Missing old source snapshots or digests
remain unknown rather than being filled with today's human signatures.

Older thermal results can still supply exact saved pending reasons and root
inputs. Their missing numerical comparisons and source provenance remain
explicitly unknown. The packet presents the available relic residual and
comparison details; it does not rerun the model or infer a missing value.

Existing numerical results remain immutable historical evidence after a review.
Re-run the appropriate deterministic calculation to obtain a new conclusion.
The queue alone is not a new scientific eligibility decision.

## Optional researcher timing

```bash
uv run adroit records timer-start runs/record_review/record_review.json \
  runs/review_sessions/session.json "Researcher name" --condition assisted
uv run adroit assist-session mark runs/review_sessions/session.json pause
uv run adroit assist-session mark runs/review_sessions/session.json resume
uv run adroit assist-session mark runs/review_sessions/session.json finish --attest --success
uv run adroit assist-session summary runs/review_sessions
```

The Records panel also provides start/pause/resume/finish controls. These reuse
the existing researcher-controlled paired protocol: the review packet fixes the
task identity; pauses are excluded; finishing requires explicit effort attestation
and quality outcome. Timer completion does not verify a constraint record.

Compare manual and assisted sessions on the same scientific packet with matching
quality, and counterbalance order before making a causal claim. No automated
runtime is converted into human effort. Actual researcher-time savings remain
pending until real sessions are supplied, as requested by the owner. Review
queue/export/timing costs $0 in API fees.

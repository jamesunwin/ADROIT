# Measured optional research assistance

The assistant clarifies inputs, gathers primary-source evidence, plans existing
calculations and reviews saved results. Physics remains deterministic. The
default costs $0 and uses deterministic templates; LLMs are an explicit option.
See [installation and local API-key setup](installation.md).

## Use an existing study

```bash
uv run adroit assist runs/my_single_idea --out runs/my_review
uv run adroit assist runs/my_single_idea --out runs/my_review_llm \
  --provider anthropic --model claude-opus-5-5 --budget 1 --fetch-sources
```

The directory must contain a single-idea `result.json`. Alternatively use
`--provider openai --model gpt-5.6-sol`. Two advisory roles handle planning and
review. Every paid request/retry reserves its maximum charge before dispatch;
usage and uncertain charges are journalled in `budget.jsonl` (run as a workbench job, in the job's own
`paid.jsonl`). Failed assistance
preserves deterministic advice, reports degradation and exits nonzero.

For specific draft statements or new calculations, supply an `AssistanceRequest`
JSON. Fields include `goal`, the original `study`, a saved `result` or
`native_result`, `draft_claims`, missing fields, and up to four source requests.
Sources specify an arXiv ID, page and optional text anchor. A plan refers to the
exact request hash; it cannot supply new numerical arguments or shell commands.

`--execute-plan` separately authorizes at most one existing numerical operation:
the supplied native fit, a supplied `CoverageRequest` nuisance check, or the
supplied full single-idea study. Every numerical argument comes from that typed
request. Changed masses/searches/models require new researcher input. Without
this flag, calculations remain proposals. Numerical results are saved separately
with content hashes and then reviewed.

## Source and review trust

`--fetch-sources` performs bounded free arXiv/PDF reads. Reference/title lookup
and actual document text are checked separately. Packets retain URL, page,
document SHA256 and a short literal excerpt. Cached bytes must match their
provenance. Wrong titles, unavailable sources or absent anchors remain
unconfirmed. Explicit researcher sources take priority within the four-paper cap.

A real paper and literal passage match do **not** establish scientific entailment.
Reports distinguish probe-confirmed concerns from unconfirmed suggestions.
Named probes check input/result identities, null eligibility, calibration
completeness, significance labels, fidelity, coverage assertions, thermal
certificates and record-review status. Claims must cite the facts their probe
requires. Novel semantic concerns need expert review. Agents cannot write
constraints, sign human verifications or replace physics values.

The clients use the existing typed-response interfaces.
[Official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs)
describes structured output; schema conformance alone does not make a scientific
claim true.

## Measured value and its limits

Compare identical physics inputs, solver budgets and outputs against the free
baseline. Withheld development labels score issues caught/missed, known false
concerns, unconfirmed novel suggestions, input preservation, cost and latency.
An issue already found by a deterministic template is not an additional accuracy
gain. These cases never use a DM10 held-out half.

The first live three-task comparison contains five seeded issues and a clean
control per provider. Both Opus 5.5 and GPT-5.6 Sol caught 5/5 named issues with
no named false concern; the deterministic baseline also caught 5/5. Opus offered
additional unconfirmed suggestions. Costs were $0.1700586 and $0.091316.
This small development study demonstrates working safeguards, not a causal
gain in physics accuracy or researcher effort. Automated latency is reported
separately from human time.

## Researcher timing protocol

Human sessions were deferred by the owner. No time savings are yet claimed.
Timers support active effort, pauses, explicit quality outcomes and attestation:

```bash
uv run adroit assist-session start runs/timers/manual.json P01 task01 INPUT_HASH manual
uv run adroit assist-session mark runs/timers/manual.json pause
uv run adroit assist-session mark runs/timers/manual.json resume
uv run adroit assist-session mark runs/timers/manual.json finish --attest --success

uv run adroit assist-session start runs/timers/assisted.json P01 task01 INPUT_HASH assisted \
  --assistance-result runs/my_review_llm/result.json
uv run adroit assist-session mark runs/timers/assisted.json finish --attest --success
uv run adroit assist-session summary runs/timers
```

Replace `INPUT_HASH` with the recorded scientific request hash. Imported cost
must belong to that same assisted identity. Use `--unsuccessful` for failed
tasks. Only one completed, successful, attested manual/assisted pair with matching
participant/task/input identity contributes a descriptive time difference.
Missing/duplicated/unmatched sessions remain excluded. Zero pairs produce no
estimate, not a claim of zero savings.

Predeclare tasks, success criteria and solver budgets; counterbalance condition
order across researchers, include clean controls and publish mistakes. Identical
tasks can create learning effects; control and report them. Collect enough
independent researchers/tasks to assess variability before claiming causality.
Do not infer expert minutes from model latency or fictional effort estimates.

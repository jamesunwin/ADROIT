# Scientific evidence and reproduction — M19–M20

New CLI/workbench runs of Track 1, Track 2, single-idea studies, promoted
children, Track 1's front end (`idea`) and a bespoke Lagrangian (`lagrangian`,
since 2026-10-20) write a `result.evidence.json` beside the existing `result.json`.
Promotion summaries use `promotion_<selection>.evidence.json`. Native likelihood
results written by the assistance dispatcher and native-coverage studies also
use the same schema. Direct numerical APIs still return their normal typed
results; `adroit.evidence.build.save` can bind a sidecar to a selected saved result.

The numerical result remains authoritative. The sidecar adds the original typed
inputs, actual engine mapping, source/data hashes and review signatures,
software/runtime identities, numerical settings, units, confidence levels,
applicability, uncertainty descriptions, pending reasons and available root,
fit, calibration and scan-coverage certificates. Newly refined contour and
single-idea points retain the comparisons that determined their verdict.
Track 2 saves its actual resolved NR rate inputs; native results save their
actual numerical class, reference point and spin.

Calculation, applicability and human review are independent fields. A computed
zero is distinct from an unavailable backend. An unreviewed record does not
become verified because a numerical value exists. A missing comparison does not
establish that a topology is outside scope; where a saved result did not record
the distinction, the adapter says unknown. Source confidence levels and requested
95% comparisons remain separate, as do conditional native statistics and the
unconstrained NR reference. Generic null-limit comparisons retain their
limit-equivalent construction rather than acquiring native-likelihood fidelity.

## Export a selected result or promotion

```bash
uv run adroit evidence export runs/my_track1 --out runs/my_track1_evidence.zip
uv run adroit evidence export runs/my_single_idea --out runs/my_single_idea_evidence.zip
uv run adroit evidence export runs/my_signal/promotion_class_0.json --out runs/promotion_evidence.zip
```

All three commands cost $0 and perform no new numerical calculation. Export
includes the selected result, its evidence and report, named plots, study links,
the distributed physics/configuration inputs captured for that run and the
dependency bibliography/citation guide. A promotion includes its referenced
children and the parent signal result. Study descendants are selected through
the recorded graph, not by copying everything in the run directory.

External data releases, tools and their runtime environments are referenced by
identity rather than copied. This respects the existing download/licensing
arrangements; exported citations do not grant redistribution rights to external
papers or packages. A selected user anomaly file is included when it was captured
before calculation. If an input has disappeared or changed since the run, export
retains its old identity and reports the unavailable artifact; it never substitutes
the current file. No current source review is attached to an old result.

The ZIP has a versioned `manifest.json`, content hashes for every member and
explicit study-node links. From version 2 (2026-11-02) a promotion's node names
its parent. A version 1 bundle has one of two layouts: from 2026-11-01 it named
the parent too; before, it linked the parent after the children, unnamed. Each is
verified as it was written. Either way a promotion's parent must be the
version its record names, and so must its children where the record names them. Each version and layout is kept in
the tests as untouched exports made by the code that wrote it
(`tests/evidence/test_bundle_formats.py`).
A node's study record (`study.json`) is attached only where it describes the node's
result: from 2026-11-03 a record names its result's digest, and one naming another
version is left out, saying so, and a bundle holding one does not verify. A record
written before names none, and is attached as found, saying so (the auditor's
version-identity audit, VI-01). A promotion's children and parent are followed as
the versions its record names by the export and the review queue alike; an edge to
another version, or to nothing saved, is left out and named (VI-04). Reviewing the
bundle keeps those warnings, and says the tasks of an edge not followed are not
shown (the auditor's DB/VI recheck, DC-02). The record beside a promotion is its parent
study's, checked against the parent result the promotion records, in the bundle and
in the references download alike (DC-05). Verification hashes, checks and
reconstructs one read of the ZIP's bytes, so its digest and its decisions are of the
same archive (DC-06).
Original local paths inside saved results are
descriptive; manifest links identify the portable study graph. They are this
machine's absolute paths (the runs' command lines, each input's and backend's
location), so under a home directory they name the user and the folder layout:
the export counts them, prints how many and how many lie under the home
directory, and records the same note in the manifest (`local_paths`; the audit
loop's AL3-22, 2026-11-15). Share a bundle with that in mind. The archive does
not include `.env`, unrelated files, cache directories or protected DM10 cases.
Credential-like content and credential-valued JSON fields cause export to refuse.
Existing ZIP destinations are refused, so export cannot overwrite another bundle.

### Ideas and bespoke Lagrangians (Rep-2, 2026-10-20)

```bash
uv run adroit evidence export runs/idea_singlet --out runs/idea_singlet_evidence.zip
uv run adroit evidence export runs/lagrangian_V1 --out runs/lagrangian_V1_evidence.zip
```

Neither calculates a point, so neither has observations. An idea run's evidence keeps the models built and the
proposals dropped (its saved conclusion), each model's audit, and where each model came from; its bundle also holds the
typed model files written for Track 1 (`models/*.yaml`). No experiment is consulted, so none is among its sources. A
Lagrangian run's evidence keeps its status, checks, derivations and their comparison, the nucleon-level interactions it
was matched to, the library's nearest cards, its exclusion and its contract; a run stopped for a person, or an
exclusion that skipped a module, is a task in its review queue. Point replay is not provided for either: a model file
from an idea run is computed by Track 1, whose results replay point by point. Idea and Lagrangian results saved before
this export as legacy results (their provenance unknown), as older results do.

### The batch audit's repairs (B20-03, B20-04; 2026-10-20)

- **Every copy is checked.** An envelope's certificates and engine mapping copy scientific fields from its result: a
  Lagrangian's derivations, checks and interactions; Track 1's audit and verdicts; a fit's numbers. Verification now
  checks each copy against the typed result, through the schema's additive defaults as the summary is checked. A
  bundle whose copies disagree with its result does not verify.
- **An idea's model files are named for what they are:**
  - a file the run wrote is attached as such;
  - a completion written beside a model is noted as not part of the result;
  - any other file (edited after the run?) is exported with a warning in the manifest.
- **Structured files fail closed.** A JSON or YAML attachment is parsed strictly before its credential check: one
  that cannot be parsed, holds more than one YAML document or repeats a key is refused, never exported unchecked.

## Verify, then explicitly reproduce a calculation

```bash
uv run adroit evidence verify runs/my_track1_evidence.zip
uv run adroit evidence verify runs/my_track1_evidence.zip --check-environment
uv run adroit evidence replay runs/my_track1_evidence.zip --node n0 --index 0
uv run adroit evidence replay runs/my_single_idea_evidence.zip --node n0 --index 0
```

Verification checks archive version, paths, content, typed results, input identity,
saved conclusions and study links. It reconstructs saved verdicts and pending
reasons without rerunning physics, fitting or toys, and works after moving the ZIP
to another directory. Hashes detect corruption or inconsistency; they are not a
cryptographic author signature or a new expert review. "valid" therefore means
**internally consistent; provenance not verified** (the `assurance` field): anyone
can build a self-consistent bundle. A result that does not parse under the
installed schema (for example a UFO parameter that is not plain arithmetic) makes
the bundle invalid.

`--check-environment` separately checks the installed conservative dependency
inventory. Unknown, changed or unavailable inputs give named reproduction reasons;
this can include an unavailable backend that was not used by the selected point.
Availability is not a claim of actual use. Environment checks resolve known
installed dependencies locally, rather than reading arbitrary paths from the ZIP.

`replay` is an explicit calculation using installed ADROIT code on the bundle's
inputs, which are untrusted data. The model class is rebuilt from the bundle's
typed model (the library entry for a portal run, else `classify`); a stored class
that differs is refused, never run as given. (A standalone native-joint result
made through the Python API has no typed model; its saved simplified-model class,
couplings only, is used.) It reports `matched`, `different` or `incomplete` and
the expected/actual numbers. It supports:

- Track 1: one saved grid point, including its constraint comparisons.
- Track 2: one saved candidate's actual historical signal fit.
- Single idea: one saved mass's unconstrained NR reference fit.
- Standalone native joint result: one shared physical likelihood fit.

Reconstruction supports promotion, exclusion, native-coverage, idea and Lagrangian results too;
point replay for these aggregate workflows is not provided. Choose a supported
child node instead. Global toy calibrations, full scans and other points are not
silently rerun. Numerical replay has relative tolerance `1e-7`; a `1e-9` absolute
tolerance applies only to named count/log-likelihood and related numerical
diagnostics. Cross-sections, small physical couplings and other quantities use
relative comparison without that dimensionally inappropriate absolute floor.

Replay never executes code or shell commands from an archive. It restores only
an explicitly captured user anomaly input into a temporary directory; all other
calculations use the current installed components. A missing engine/model or
external calculation reports incomplete reproduction. Numerical agreement under
the current installation does not certify equality of historical environments.

## Older results and direct APIs

Pre-M19 results remain readable without new fields. Exporting them creates an
in-memory envelope with `legacy_unknown` calculation provenance. Existing values
and verdicts are preserved; missing engine inputs, contour comparisons, source
signatures and uncertainty information remain unknown. Export does not modify
the original result or create an evidence sidecar there.

```python
from pathlib import Path
from adroit.evidence.runtime import capture_request
from adroit.evidence.build import save

context = capture_request(request)     # before your deterministic calculation
result = run(request, folder)          # the existing workflow
path = folder / "result.json"
path.write_text(result.model_dump_json(indent=1))
save(path, context=context)            # checks for changed calculation dependencies
```

The calculation-start typed-request digest also detects in-memory input mutation.
For a standalone native result produced from a single-idea request, pass
`original_inputs=request.model_dump(mode="json")` to `save`: its result schema
records the numerical engine inputs rather than containing the whole original
single-idea request.

The existing provenance store can also log an `EvidenceEnvelope` as a typed
`tool_called` payload. It is scientific evidence, not a replacement for the
retired general engine's `RunState`.

M21 adds [requested-result review queues](record_review_workflow.md): new sidecars
retain the per-study task snapshot, and ZIPs include `review_queue.json`/`.md` for
each node. The shared queue preserves saved pending reasons and identifies human
review, missing inputs and new calculations separately. It does not revise the
saved numerical verdict or supply a human signature.

Optional allowlisted advisory attachments (`assistance.json` or `agents.json`)
require `--include-agents`; prompt/response text is omitted unless
`--include-private-prompts` is also supplied. Input descriptions and scientific
result content are part of the selected study: inspect these before sharing.
No paid call occurs during export, verification or replay.

For a review in a separate folder, select its JSON explicitly with
`--agent-evidence runs/my_review/result.json` (repeatable). This also omits raw
prompt/response fields by default. An advisory attachment does not alter the
scientific verdict or become an expert verification signature.

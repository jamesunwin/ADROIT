# Validation and audits

How ADROIT 1.0.0 was checked before release. The detailed working records (each audit's findings, the repairs and
their receipts) are kept with the development history and are not part of this repository. Commit identifiers and tags
(such as `pre-retirement`) cited in the documents, the data and the tests (for example the commit a result or a limit table was computed at) refer to
that development history; the public history starts at 1.0.0.

## Validation against published results

- **Direct detection:** each experiment module is validated against its collaboration's published limit inside a
  stated mass range, and is used only inside it (`docs/dm3_experiments.md`; the results in
  `docs/dm3/validation_results.json`).
- **The relic density:** checked against Saikawa & Shirai's published constant-s-wave benchmark
  (`scripts/validate_relic_ss2020.py`; [`relic_low_mass.md`](relic_low_mass.md)) and, for the portal library, against
  micrOMEGAs and MadDM where they apply.
- **The portal library and the generic route:** each benchmark model is checked against its source's numbers, and the
  generic route against the library where both apply ([`freeze_out_build.md`](freeze_out_build.md),
  [`g11_benchmarks.md`](g11_benchmarks.md)).
- **The model builder and the agents:** evaluated on a model zoo with a held-out half, scored once
  ([`dm10_evaluation.md`](dm10_evaluation.md), [`model_zoo.md`](model_zoo.md)).
- **The constraint records:** every record shipped was verified against its source and signed by a person
  ([`release_notes_v1.0.0.md`](release_notes_v1.0.0.md), "Records").

## Independent audits

From 2026-10-05 to 2026-11-23 the code was audited repeatedly by the author, Claude Code and Codex, each review
against a fixed commit and separate from the development work it reviewed. The audits covered:

- the physics: the operator basis and nuclear responses, the relic calculation and its validity limits, the generic
  route's derivations, the halo treatment, the statistics of fits and global significances;
- the workflows: Track 1, Signal best fits, Explain a signal, the model builder and the only-usable-models gate,
  constraint discovery, reanalysis and promotion;
- the evidence: how a result is certified, saved, versioned, exported and read back, and how damaged or changed
  inputs are named rather than calculated through;
- the workbench and the command line, money and paid calls, installation and the release checks.

Each finding was given a severity. Every critical and severe finding was repaired before release, each with a test
that reproduces the auditor's control and fails without the repair. Findings below that level were repaired or
deferred with the owner's sign-off; the deferrals that matter to a user are in the release notes' "Known limits and
deferrals". Finding identifiers (for example `CO-03` or `AL4-10`) are cited in the code and tests where a repair was
made.

## The release checks

`scripts/release_checks.py` runs the release gate on a committed tree: lint, the fast and slow test suites, the
validation scripts, a clean install, and a headless and a real-browser acceptance layer over every workflow, with
mutation controls that must fail when their defect is restored. A release needs every mandatory step.

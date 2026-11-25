# Track 1 speed and scan-coverage pilot

Prepared 2026-10-06 after remediation commit `3e3422d`. The owner selects
Track 1 thermal scans as the first workflow. ADROIT aims to integrate its
components faithfully and efficiently, with optional LLM checks and simpler
interaction. Correcting component weaknesses is valuable; new physical
precision beyond those components is not required to justify the system.

## Scope and evidence rules

Start with measured duplicate work and exact reuse. Preserve model parameters,
relations, native/source confidence levels, validated domains, solver tolerances,
independent final root evaluation and all pending reasons. Do not round masses,
replace actual 95% calculations with curves, or use a surrogate as a certificate.
No paid calls, protected DM10 evaluation, cache deletion, backend replacement or
new physics programme is needed for this pilot.

Profile in a fresh process using existing disk caches, then repeat in the same
process. These are explicitly different cache states, not a claim of a pristine
cold-machine benchmark. Save source/input hashes, function/call counts, elapsed
times and complete compared results under ignored `audit/performance/`.
Heavy calculations use nice 10, at most two scan workers and two native threads.
Existing external-tool caches may be written by normal calculations.

## Pilot milestones

1. **S01 — Measure Track 1 phases.** Profile cuts and likelihood views on the
   same saved physical scan; identify duplicate root refinement and constraint
   evaluation. Profile a representative electroweak rate table to distinguish
   solver cost from detector/process cost. Existing caches and the separation
   of relic refinement from final constraint judging are part of the baseline.
2. **S02 — Remove demonstrated exact duplication.** Reuse one scan's refinement
   and evaluated physical root points across cuts/likelihood views if the
   profile confirms duplication. Keep final re-evaluation of the density and
   independent view classification. Compare every result field, refused root,
   source/domain flag and theory-band label with the baseline; test invalid and
   unstable solvers as well as ordinary cases.
3. **S03 — Make long calculations recoverable.** Use the existing run/job
   conventions for persistent phase/point progress and restart. A checkpoint
   must be bound to model, parameters, numerical settings, sources and backend
   identities, and mismatches must refuse reuse. Assess this separately from
   scientific caching so resume cannot accept a stale result.
4. **S04 — Add a bounded coverage pilot.** First add an optional relic-only
   resolution diagnostic beside the rectangular scan. Test additional cell
   probes/refinement on independently specified disconnected/tangent/narrow
   branches, thresholds and unavailable regions, then on physical portals.
   Record explored resolution, solver calls and unresolved coverage. Finite
   probes cannot establish that all arbitrarily narrow features are absent.
   Keep the existing scan/result/plot defaults until the additive diagnostic is
   validated; apply constraints only to independently certified candidate roots.
5. **S05 — Validate the useful gain.** Measure complete-pipeline wall time and
   call reductions in declared cache states, exact preserved results and branch
   recovery on new development cases. Run the appropriate full offline suites
   before declaring the pilot complete. Report demonstrated gains separately
   from prospective improvements and select the next increment from evidence.

The first execution covers S01 and the smallest warranted S02 change. S03–S05
define the subsequent coverage/recovery work; this document does not claim they
are already implemented. Extensions remain incremental and preserve the
remediation acceptance baseline.

## Initial candidate

`orchestrator/track1.py` currently calls `parameter_space/verdict.py::verdict`
once for cuts and again for an optional likelihood view. Both calls refine the
same thermal target on the same scan and judge the same accepted points.
Measure that repetition before changing the API. The two scientific views and
their separately labelled theory-band points must remain distinct.

Profile artifacts remain local and ignored; no new publication is required to establish a baseline.

## Initial pilot result, 2026-10-06

S01 profiling and the two targeted S02 reuse changes are implemented and validated.
S04 has an optional standalone relic-only diagnostic and independent analytic plus
physical tests; its full workflow integration remains future work. S03 persistent
recovery and S05 broad full-pipeline benchmarking are still planned.

Measured phase gains are 2.016× for warm cuts-plus-likelihood judgment and 1.638×
for a cold higgsino rate table, with exact preserved results. These are not claimed
as whole-scan speedups. The finer physical diagnostic samples 49 points, makes 233
bounded density evaluations and certifies eight roots. It applies no experimental
constraints and makes no global completeness claim.

Full offline suites pass (1036 fast, 22 slow); the final seven coverage tests and
fresh physical diagnostic also pass after preserving endpoint identities. The
full fast collection preceded that final added identity test. The detailed local
report (summary) and evidence are ignored
artifacts intended for the owner's working checkout. No new commit/push is made.

Example API: load a `Track1Result` from an existing `result.json`, then call
`coverage.diagnose(result.scan.request, CoverageSettings(refinement_depth=1,
max_evaluations=250))`. Its results are density/coverage evidence, not a new verdict.

## Track 1 workflow integration

The CLI and workbench now offer the optional resolution check. Defaults keep the
original rectangular scan and coverage off. A typical local command is:

```bash
adroit track1 --portal higgs_portal_scalar --coverage-depth 1 --coverage-budget 250 --out runs/higgs_coverage --no-literature
```

The budget caps the coverage search's sampling, refinement and certificate checks.
Normal constraint evaluations add their own independent density rechecks. Certified
coverage roots join the primary thermal samples and receive the same constraints;
missing samples, exhausted budgets and failed root attempts remain explicit. If all
computed samples are excluded while requested coverage is partial, the region's
headline remains pending. Finite probes cannot prove absence of narrower features.

In the workbench, tick **Check finer thermal coverage** in either Track 1 scan tab.
The live view shows the current phase and completed/total counts. Reported contour
points are samples, not a count of disconnected physical branches.

### Progress and recovery

Track 1 saves atomic per-point/root/coverage artifacts and `progress.json` in the
run folder. The workbench already launches a detached low-priority process; it now
offers **Resume Track 1** for interrupted Track 1 jobs. The terminal equivalent is:

```bash
adroit track1 --resume --out runs/higgs_coverage
```

This restores the saved request rather than silently changing flags to defaults.
Giving model/portal arguments on resume requires that the reconstructed request
match. Changed physical inputs, resolution/budget settings, code, runtime identities,
source records, calibration/data releases or backend availability refuse reuse.
Checkpoint payload checksums and point identities are validated, and only one
scientific writer may use a folder. A new non-resume invocation creates a fresh
checkpoint epoch and archives the prior checkpoint directory.

The fingerprint includes bundled source/data, native-validation results, scientific
Python modules, installed version metadata, static external calculation folders
and external runtimes. Generated work/output directories and bytecode are excluded.
If dependency contents change during a run, that epoch is invalidated. Do not edit
calculation code or source data while a run is active. Derived backend caches remain
managed by their existing input-bound adapters; checkpoint outputs are separately
checksummed and bound to the calculation identity.

Coverage reservations are saved before dispatch. Interrupted in-flight evaluations
remain charged to the same search cap on resume. A root search may therefore finish
partial after repeated interruptions; increasing the cap requires a fresh request.
Parent-study provenance is restored when resuming, and completed plot artifacts are
verified/rebuilt from the saved scientific result when needed.

### Whole-workflow measurements

The integration benchmark uses isolated pre-pilot code (`3e3422d`) and current code,
with identical physical inputs and an identical DIAMX driver path/content to avoid
an artificial cache-key difference. Both orders are measured using existing disk
caches. Input fingerprinting and checkpoint writes are included in the current
workflow timing. Early 4×4 vector measurements show that this robust recovery
bookkeeping can outweigh the shared-refinement gain on a small run. No whole-run
speedup is claimed from the earlier phase-only gains. Exact results, coverage and
interruption/resume outcomes are checked separately; final numbers and logs belong
in the local integration closeout report.

## Integration closeout, 2026-10-06

S03 recovery, S04 normal-workflow optional coverage and the scoped S05 whole-run
comparison are complete. Full suites pass (1049 fast, 22 slow),
and real interrupted/resumed outputs match the uninterrupted baseline exactly.
The small full-workflow benchmark is about 11.3% slower after including robust
fingerprints/checkpoints; no whole-run speedup is claimed. Coverage deliberately
adds checked sampling and constraints. The local integration report (summary)
records all timings, limitations and preserved failures. The validated integration
was committed as `796e3f5` in the development history.

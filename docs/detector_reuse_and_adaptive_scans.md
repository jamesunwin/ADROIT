# Exact detector reuse and adaptive thermal scans

This work follows the authorised execution plan.
Track 2's previous optimisation is published as `2bde23b`.

## Detector calculation reuse

The persistent cache stores successful numerical statistical outputs under
`ADROIT_DATA_DIR/calculation-cache/`. It does not store or interpolate recoil
predictions. Every lookup retains the same native statistical construction.

- Yellin's optimum interval uses its exact existing input text, including CL and
  cumulative event fractions. Identity includes the executable, source/tables,
  tracked transitive native libraries, OS identity and adapter/cache code.
- The free-background Neyman construction uses exact observed/predicted bin counts,
  CL, toy count and seed. Identity includes the statistic, cache code, Python/OS
  and NumPy/SciPy numerical runtime contents.

Entries are checksummed, atomically written and locked per exact key. Changed
identities, damaged records, failed calls and rejected outputs cannot provide a
reused result. Backend availability is checked before native reuse. Untracked
library loaders or unavailable cache storage fall back to fresh calculation.
No mass rounding, changed seed, reduced toy count, altered confidence level or
surrogate is used. Upstream spectra, domains and experimental eligibility remain
their original calculations.

Use `ADROIT_CALCULATION_CACHE=off` to bypass persistence, or `cache=False` on the
two statistics functions for an explicit fresh comparison. Initial cache filling
has a small cost; repeated calculations are the intended benefit. Native backend
changes or unsupported library discovery can deliberately prevent reuse.

## Adaptive coverage

Uniform coverage remains the default. The adaptive option probes each starting
cell's corners, edge midpoints and centre, then refines cells selected by required
exploration depth, a thermal bracket, proximity to the target, log-density
curvature or unavailable values. The request supplies a maximum depth and a hard
density-evaluation cap. For example:

```bash
adroit track1 --portal higgs_portal_scalar --coverage-strategy adaptive --coverage-depth 3 --coverage-exploration 2 --coverage-budget 3000 --no-literature --out runs/higgs_adaptive
```

The workbench's Track 1 forms expose the same method, maximum depth, minimum
exploration depth and budget. Increased minimum exploration spends more evaluations
looking for structures that the coarser nodes might miss.

The diagnostic records every cell's bounds, depth, decision and reason. Cells not
selected for further refinement retain coarser resolution. `adaptive_sampling_complete`
means the declared selection procedure finished; it is not a global completeness
certificate. Failed/unprobed cells or uncertified candidates yield `partial` and
explicit pending reasons. Finite probes cannot rule out arbitrarily narrow features.

Every candidate root is refined using the actual solver and receives a fresh final
density check with the existing 1% acceptance tolerance. Track 1 applies its normal
constraints and another final-density check to certified roots. Original parameter
relations and endpoint identities are retained. Reservations precede evaluations;
checkpoints preserve completed samples and the cap on resume. Scientific settings
cannot be overridden by a bare resume command.

## Validation and measurement scope

Independent dense analytic scans specify disconnected loops and a narrow loop;
tangent, discontinuous-threshold, unavailable-region and interrupted-run tests
check certificates and honest unresolved outcomes. Physical vector/Higgs checks
use separately computed 41×41 grids and independent density re-evaluation.
Broader benchmark cases include 8×8 vector and 6×6 axial Track 1 scans plus silicon,
germanium and LZ signal searches. Cached comparisons retain complete scientific
result JSONs. Timings and cache-population costs are reported separately.

The closeout report and evidence are local and ignored.
The final closeout report (summary) records the
measurements, failures and limits. Full acceptance passes: 1,069 fast tests and
22 slow tests, with unchanged source/record/validation identities. No paid LLM or
protected held-out evaluation was used.

Repeated signal-pipeline speedups are 5.73× (CDMS II Si), 5.63× (CDMS II Ge) and
3.42× (LZ). Whole Track 1 gains are modest: about 4.5% and 5.4% less time in the
small vector/axial cases, with no meaningful gain for the larger vector plane.
Native cache population costs are kept separate. A deliberately stopped initial
new-dark-matter-mass run demonstrated several minutes of cold LZ calibration per
mass; controlled larger planes therefore vary mediator mass/coupling at fixed
dark-matter mass. That initial attempt is retained and not counted as a passed
benchmark.

Adaptive physical checks recover one vector and two Higgs dense-reference
components. Vector sampling uses 141 locations versus 289 at uniform depth; Higgs
uses all 289, so no sampling reduction is claimed there. Maximum independently
rechecked density residuals are 2.4×10⁻⁵ and 1.5×10⁻⁵. These are conditional
coverage/certificate measurements, not global completeness or new physics precision.

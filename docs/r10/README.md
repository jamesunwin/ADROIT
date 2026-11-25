# R10: Track 1 throughput

**Status (2026-10-12): passed.** The three Track 1 examples, 4 × 4 each at masses DIAMX had not seen, take
41–62 s with the tables against 938–1541 s with every limit computed directly (22–25× faster), and their verdicts are
identical at every grid point and every thermal-contour crossing. Eleven tables, all current.

## Where the time went (before)

A cold 4 × 4 scan of the Higgs-portal scalar (m_χ 11–9000 GeV, g_χ 10⁻⁵–10, one worker, no literature search;
`docs/r10/profile_track1.py`) took 595 s for the grid alone, then several minutes per thermal-contour root. Almost all
of it is direct detection at masses the scan had not seen:

| module | one new mass, one kind | how |
|---|---|---|
| LZ, XENONnT, PandaX-4T (DIAMX) | 1.5–2.5 min | template generation and the profile likelihood in (S1, S2) |
| CDMSlite Run 2 | 23 s | the median over efficiency realisations |
| PICO-60 | 3.6 s | the profile likelihood |
| CRESST-III, DEAP-3600 | < 1 s | |

A grid of n masses costs n new masses, and every thermal-contour root another. DIAMX's results are cached on disk
by spectrum, so a repeated scan is fast and only new masses cost.

**Threads.** DIAMX's subprocess already runs with every numerical pool capped (`xenon.capped_environment`, since
the R6 follow-up): measured at 194% CPU at two threads, against the 576% the audit saw.

## What changed

- **Tables** (`parameter_space/limit_tables.py`, `scripts/tabulate_reference_limits.py`). For each slow module and
  each kind it is validated for (SI, SD-proton, SD-neutron), the 95% limit by the module's own procedure:
  - **Masses:** sixteen per decade across its validated range, every one computed directly (a grid, then its
    midpoints, in two DIAMX runs).
  - **Interpolation:** a cubic spline in (log m, log σ) between them.
  - **Accuracy ε:** the largest |spline/direct − 1| with each interior mass left out and predicted from the
    others. That doubles the spacing locally, so ε overstates the table's own error.
  - **Batch check:** two midpoints are computed alone, to check that a batch gives a spectrum the same limit as a
    single run.

  Linear interpolation was tried first: on LZ's SI table, its error reached 10.8% at threshold (8.9–10 GeV), where
  the curve bends most. The spline's left-out error there is 0.63%.
- **Exact verdicts.** A table's value at a mass is used with a local tolerance η: twice the larger leave-one-out
  error of the two tabulated masses around it, at least 0.5%. The error is local: CDMSlite's SI limit falls by three
  orders of magnitude between 1.3 and 2 GeV, where η reaches 180% (and the points there are computed directly),
  while above 3 GeV it is 0.5–1%. Every comparison that decides a
  point's direct-detection verdict is checked (`dd_channels.compare`). A ratio x is clear if x > 1 + η or
  x(1 + η) ≤ 1. Tovey et al.'s √r − √s is clear if its whole range, with r and s each moved by up to η, stays on
  one side of ±1. If any comparison is not clear, the point is compared again with every limit computed directly.
  The verdicts are therefore the direct calculation's wherever a table's error is within η. That is not proven:
  η is twice an estimate that overstates the error by construction, and the gate checks it at every point of three
  test scans. Only the printed ratios differ, within η.
- **Currency.** A table carries a fingerprint of everything its numbers depend on (`limit_tables.fingerprint`):
  the rate, nuclear and statistics code, the experiments' shared code and data (including the validated ranges,
  conservatively), the module's own code, and its external inputs (DIAMX's driver, configuration and source;
  CDMSlite's data release). A table whose fingerprint differs from the installed code's is ignored, and the scan
  computes directly. A test fails until a stale table is retabulated.
- **Opting out.** `adroit track1 --exact-limits` uses no table. The combined likelihood (`--likelihood`) always
  uses exact limits, since its threshold is not at a single ratio. A scan's notes say when tables were used.

## Tables

`uv run python docs/r10/tables.py` (from the stored tables; computed 2026-10-12 in three parallel streams, about
7 h of computation in all):

| module | kind | masses (GeV) | count | largest left-out error | median | η, upper half | η > 5% (GeV) | current |
|---|---|---|---|---|---|---|---|---|
| CDMSlite Run 2 | SD-neutron | 1.31–20 | 21 | 188.30% | 0.69% | 0.85% | 1.31–2.59, 5.13–7.7 | yes |
| CDMSlite Run 2 | SD-proton | 1.31–20 | 21 | 188.30% | 0.67% | 0.50% | 1.31–2.59, 5.13–7.7 | yes |
| CDMSlite Run 2 | SI | 1.31–20 | 21 | 89.76% | 0.61% | 0.50% | 1.31–2.59, 5.13–7.7 | yes |
| LZ WS2022+WS2024 | SI | 8.87–92.07 | 19 | 0.63% | 0.27% | 0.53% | none | yes |
| PandaX-4T Run0+Run1 | SD-neutron | 341–1e+04 | 25 | 2.18% | 0.54% | 1.21% | none | yes |
| PandaX-4T Run0+Run1 | SD-proton | 148–1853 | 19 | 1.95% | 0.49% | 0.63% | none | yes |
| PandaX-4T Run0+Run1 | SI | 147–9715 | 31 | 1.52% | 0.68% | 2.40% | none | yes |
| PICO-60 C3F8 (2019) | SD-proton | 3.02–1000 | 43 | 4.58% | 0.01% | 0.50% | 3.02–4.57 | yes |
| XENONnT SR0+SR1 | SD-neutron | 21.5–1e+04 | 45 | 1.54% | 0.26% | 1.82% | none | yes |
| XENONnT SR0+SR1 | SD-proton | 21.5–1e+04 | 45 | 1.60% | 0.32% | 2.84% | none | yes |
| XENONnT SR0+SR1 | SI | 27.8–1000 | 27 | 1.91% | 0.42% | 0.56% | none | yes |

**Reading the table.** The left-out error is the spline's error at a tabulated mass predicted from the others
(so at twice the table's spacing): a conservative estimate of the table's own error. The median is 0.01–0.7%. The
large values sit where the limit is steep: CDMSlite's kinematic threshold (1.3–2.6 GeV, where the limit falls by
three orders of magnitude and |d ln σ / d ln m| reaches 38) and a bend at 5–8 GeV; PICO-60's threshold at 3–4.6 GeV.
There, the local tolerance η exceeds 5%, so a point near its limit there is computed directly; elsewhere the table
decides. `tests/parameter_space/test_limit_tables.py` requires every left-out error to be under 5% except where
|d ln σ / d ln m| > 5.

**Time.** A DIAMX table costs one run for the grid and one for the midpoints: 36 min for LZ's SI, 32–52 min per
kind for PandaX-4T, 52–86 min for XENONnT; a CDMSlite table 10 min per kind, PICO-60's 2 min. They are recomputed
only when the code their fingerprint covers changes (then a test fails until they are).

## The gate

`docs/r10/gate.py` runs `adroit track1` twice on the same plane, two workers, no literature search: first with
the tables, then with `--exact-limits`, and compares each grid point's verdict per constraint, its pending
constraints, and each thermal-contour crossing (status, what excludes it, what leaves it pending). Run on
2026-10-12, with masses DIAMX had not seen, so that the direct run is a cold one:

| arguments | points | tables | direct | speedup | verdict | grid points differing | crossings identical |
|---|---|---|---|---|---|---|---|
| `--portal higgs_portal_scalar --x m_chi:12:8000:log:4 --y g_chi:1e-5:10:log:4` | 16 | 41 s | 938 s | 22.9× | viable_pending | none | yes |
| `docs/dm13/axial_mediator.yaml --x m_med:13:9000:log:4 --y m_chi:1.3:1900:log:4` | 16 | 62 s | 1541 s | 25.0× | viable_pending | none | yes |
| `docs/dm13/vector_mediator.yaml --x m_med:14:8500:log:4 --y m_chi:1.4:1800:log:4` | 16 | 53 s | 1155 s | 21.9× | excluded | none | yes |

**Gate: passed.** The declared target, a 4 × 4 portal scan in under 5 minutes, is met by every example (41–62 s,
including the six thermal-contour roots each), and the verdicts are identical to the unaccelerated path at every
point. The outputs are in `docs/r10/gate_*.json`.

Two notes on the timing. A MadGraph job (the mono-Z calibration, one core) ran alongside, on both runs alike. And
the tabulated run goes first: any point it recomputes directly is then in DIAMX's disk cache for the direct run, so
the speedups are, if anything, understated.

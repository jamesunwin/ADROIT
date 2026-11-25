# Halo phase 2: completion record (2026-11-10)

The implementation of `docs/halo_phase_2_shmplusplus.md`: SHM++ (Evans, O'Hare and McCabe, arXiv:1810.11468) as a
validated fixed benchmark in both tracks. The SHM remains the default, with its results unchanged. Phase 3 (an LMC
benchmark) was not started here.

| | |
|---|---|
| Base commit | `66e1c7d748da9c2b1210e81a78385cdd59b4f30d` (halo phase 1, branch `halo-phase-1`; its own base the DU pin `5eb3b37`) |
| End commit | the commit that adds this record (branch `halo-phase-2`): the implementation, its tests and this record together |
| Worktree | a scratch worktree of its own; the owner's checkout, `cr-fixes`, `du-fixes`, `halo-phase-1` and the running workbench untouched |
| Environment | native arm64 Python 3.12, `uv sync --frozen --offline --all-extras`; writable runs, projects and temporary files in the scratch root; no provider keys, no network beyond 127.0.0.1; `nice -n 10`, `OMP_NUM_THREADS=2` |
| Scientific specification | [`halo_shmplusplus.md`](halo_shmplusplus.md), written before the code |
| Support matrix | [`halo_constraint_support.md`](halo_constraint_support.md), every row updated for SHM++ |
| Evidence | `scratch_evidence/halo_phase2_2026-11-10/`: the declared expectations, the validation scripts and outputs, the baseline, the test and browser logs |

## The scientific specification

[`halo_shmplusplus.md`](halo_shmplusplus.md), from the paper's full TeX source, the authors' public code (read, never run
or copied) and McCabe's paper on the Earth's velocity (arXiv:1312.1355). It gives, with equation and section citations:

- the round component and the Sausage (Eqs. 1–7);
- the Sausage's share and anisotropy;
- the circular-speed, escape-speed and density conventions;
- the dispersion relations and the Galactic axes (the Sausage along the Sun–centre axis);
- each component truncated at the Galactic escape speed and normalised alone;
- the solar motion;
- the laboratory transformation;
- the time convention;
- Table I's values and their sources.

**Departures from the published prescription.**
- **The Sun's peculiar velocity** is (11.1, 12.24, 7.25) km/s, the authors' code's values (Schönrich et al.). The paper's
  text rounds it to (11.1, 12.2, 7.3).
- **The instant.** The paper's figure caption speaks of averaging over time, while its code evaluates one instant:
  n = 7364.3 days after J2000.0. ADROIT takes the code's instant (below).
- **The authors' code comment** on that instant ("Day=0 is midnight 1 Jan 2020") is one day off by McCabe's Appendix A.
  The benchmark is defined by n, so it is not affected.

**The time convention: a decision for the owner, recommended and implemented.** The paper has no unique prescription.

*Recommended and implemented:* the authors' code's instant, n = 7364.3 days after J2000.0 (2020 February 29, 19:12 UT),
where |v_E| = 246.94 km/s, near its annual mean of 247.19.

*The alternatives, measured on g(v_min)* (`validation/prototype/time_convention.out`):

| v_min | the annual average | ADROIT's SHM 9 March vector |
|---|---|---|
| ≤ 500 km/s | within 0.3% | up to 1.6% |
| 600 km/s | −0.5% | +2.6% |
| 700 km/s | +3.4% | +5.3% |

The convention is part of the benchmark's version: choosing another is a new version (`shmpp-1810.11468` v2), never a
reinterpretation of a saved result. **The owner's decision is asked for, and nothing waits on it.**

## Design

**The distribution** (`adroit/halo_models/shm_plus_plus.py`, outside `adroit/physics`, whose files fingerprint every
limit table):
- `Parameters`: ρ₀, v₀, v_esc, β, η, the Sun's peculiar velocity and the Earth's at the instant.
  - Every value must be finite.
  - 0 ≤ β < 1, 0 ≤ η ≤ 1.
  - Each frame's speed must lie below the escape speed.
- `Numerics`: 1,601 speeds, 64 × 64 angular nodes, generator version 1.
- `galactic_density`: f_R and f_S, normalised by Eqs. 2 and 7. N_S,esc is written through Dawson's function, which stays
  finite as β → 1; at β = 0 it is N_R,esc.
- `speed_distribution`: F(u) = u² ∮ f(u n̂ + boost) dΩ.
  - The polar axis is along the boost, so the escape cut becomes a limit on cos α.
  - Gauss–Legendre nodes on the allowed interval; the trapezoid rule in the periodic azimuth.
  - Both components go through it, so the round one's agreement with the SHM's closed form checks it.
- `table(frame)`: a `HaloModel` of kind `tabulated` in the detector's frame, or a `SunFrameTable` in the Sun's
  (`halo_models/frames.py`: a subclass whose record says `frame: sun`). `HaloModel` itself is unchanged, byte for byte:
  `adroit/core/dm_state.py` is an input of the native PICO-60 validation certificate, which hashes it (below).
  - `physics.halo` integrates a table exactly for its linear interpolant: η(v_min) and η⊥(v_min) serve every operator,
    elastic or inelastic of either sign, unchanged.
- `agrees`: regenerates a table and compares it within 10⁻⁹ of the peak, with its frame, its boosts, its grid and the
  generator's version.

**The contract** (`adroit/core/halo_choice.py`):
- **The family:** `shm-plus-plus` is available, with the benchmark `shmpp-1810.11468` v1 and the capabilities
  `recoil`, `solar` and `local-density`. It has no `count-ratio`, `annual-modulation`, `directional` or `pair-velocity`.
- **`FixedHalo` for a generated benchmark** holds the snapshot: `halo` (the detector table), `sun`, `parameters`,
  `numerics` and `tables` (each frame's sha256, as generated). Each new field is left out of an SHM benchmark's record,
  so phase 1's requests and identities are unchanged (they are pinned in a test).
  - `FixedHalo.detector()` gives the table for recoil rates; `FixedHalo.solar()` gives the one for capture.
- **`verify`:** a table's bytes must be those its sha256 records, and must be its generator's output. Anything else is
  refused by `halo_region.checked` before a calculation, and now also by the reanalysis review. (Amended after the
  audit, 2026-11-11: the snapshot's form is now its family's, and every place a halo is put in force checks it; see the
  note at the end.)
- **`Resolution`:** two components with weights 1 − η and η. Its parameters, numerics and tables' sha256 are in the
  identity; the tables themselves stay in the request.
- **`varied`:** a sensitivity flag's halo, generated again at the changed parameter. A table's SHM fields are never edited.

**Track 1** (`halo_limits`, `halo_evaluation`, `dd_channels`, `limits`):
- **The state.** `halo_limits.at_tables` builds a `State` holding the two tables and the detector table's identity
  (`tabulated`). Its v₀ and v_esc are NaN, so no SHM path can take it for a standard halo.
- **Every module** runs its own procedure with the table as its halo:
  - the fast modules (CRESST-III, DEAP-3600, PICO-60) always;
  - the slow ones (the DIAMX xenon searches, CDMSlite) within the point's budget.
  - Each is cached in process by the table's sha256 (`exact_at_table`).
- **No count ratio.** An edge-clause mass gives no limit, since its published-curve floor has no validated scaling to
  this shape.
- **An infinite limit** stands only where the module sees no recoil at all from the table.
- **Capture** takes the Sun's table (`capture_halo`).
- **The Galactic searches** take ρ₀ = 0.55 through the existing conditional rescaling.
- **SD interference factors** are taken at the table.

**Track 2 and Explain a signal** (`signal`, `variants`):
- the fit, the toys, the null limits (by the direct route: no module's published halo is SHM++) and the forecast take
  the detector table;
- the complementary verdicts (capture) take the Sun's table;
- the four halo flags generate SHM++ again at v₀ = 220/260 (v_LSR with it) and v_esc = 500/600, labelled "halo
  sensitivity (…, SHM++ generated again from the fixed benchmark)". η and β are not varied.

**Capture** (`constraints/capture.py`): `sun_frame` refuses a table not in the Sun's frame. Before this, a tabulated halo
was taken as the Sun's without a check; no route passed one.

**The workbench** (`adroit/ui/halo.py`):
- **SHM++ enabled.** Choosing it sets the treatment to the benchmark and offers no other, so the SHM's region is never
  applied automatically.
- **Its line** reads "SHM++, fixed benchmark; halo uncertainty not propagated: …".
- **Its details** give ρ₀, v₀, v_esc, β, η, the components, the boosts, the time convention, the tables (settings and
  sha256) and what it cannot calculate.
- **Back on the SHM**, its treatments return and the chosen treatment is kept.

**The command line:** `--halo benchmark --halo-family shm-plus-plus` on `track1`, `single-idea` and `signal`. A region
or the published halos with SHM++ is refused.

## Validation

The expectations and tolerances were declared before the results, in
`scratch_evidence/halo_phase2_2026-11-10/expectations.md` (21:22 UTC; one size amended at 21:35, before its first
result). Items 1, 2 and 7 had been seen in the prototype before the file was written, and it says so. The measured
values are in `validation/report.out` and the scripts' outputs.

### The distribution (`tests/halo_models/test_shm_plus_plus.py`)

| item | check | declared | measured |
|---|---|---|---|
| 1 | normalisations N_R,esc, N_S,esc against the paper (5.47699, 2.09443) | 10⁻⁵ | 5.4769944, 2.0944304 |
| 2 | the round component through the angular integration against the SHM's closed form, both frames | 10⁻⁹ of the peak | 1.1 × 10⁻¹⁵, 9.0 × 10⁻¹⁶ |
| 3 | the Sausage at β = 0 and β = 10⁻⁶ against the round component | 10⁻¹², 10⁻⁵ of the peak | 3.0 × 10⁻¹⁶, 1.0 × 10⁻⁷ |
| 4 | η = 0 tables against the SHM at the same parameters (η, η⊥) | 10⁻⁶ (**failed**, below) | 1.2 × 10⁻⁵, 1.8 × 10⁻⁵; against the SHM tabulated on the same grid 1.8 × 10⁻¹⁵, 1.0 × 10⁻¹⁴ |
| 4 | the weights applied once: 0.8 × (η = 0) + 0.2 × (η = 1) = the η = 0.2 table | 10⁻¹² of the peak | passes |
| 5 | ∫F − 1, each component and the mixture, both frames | 10⁻⁶ | at most 1.9 × 10⁻⁸ |
| 6 | η and η⊥ against my Galactic-frame cubature (2¹⁸ Sobol points, two scramblings), v_min = 0–600 km/s | max(0.5%, 4σ) | at most 0.12% (η at 600 km/s, the Sun's frame) |
| 6 | the same at 700 km/s | max(2%, 4σ) | η −0.73% (σ 0.95%), η⊥ −1.6% (σ 0.6%), detector |
| 7 | g and h against the authors' Monte Carlo tables, v_min ≤ 500 km/s | 0.5% | 0.22%, 0.31% |
| 7 | the same, 500 < v_min ≤ 700 km/s | 3% | 1.6%, 2.2% |
| 8 | F(u) against a Fibonacci lattice of 200,000 directions in Galactic axes, u = 20–200 km/s | 10⁻⁵ | at most 1.0 × 10⁻⁹ |
| 8 | the same, u = 300–600 km/s (the escape cut) | 3 × 10⁻³ | at most 8.2 × 10⁻⁶ |
| 9 | doubling the angular nodes | 10⁻⁹ of the peak | 2.1 × 10⁻¹⁴ |
| 9 | doubling the speeds and the angles together (η, η⊥, v_min ≤ u_max − 50) | 10⁻⁴ | 9.3 × 10⁻⁶, 1.4 × 10⁻⁵ |
| 10 | NaN, infinities, v₀ ≤ 0, β < 0 or ≥ 1, η outside [0, 1], ρ₀ = 0, v_esc below a boost | refused | 12 cases refused |
| 11 | η = η⊥ = 0 at and above u_max; positive below 10⁻⁶ of η(0) within 1 km/s of it | exact | passes |
| 12 | the boosts: detector (39.674, 243.187, 16.359), its speed 246.944 km/s; Sun (11.1, 245.24, 7.25); the detector's annual-mean speed 247.186 km/s | 2 × 10⁻³ km/s; 0.05 | passes |
| 12 | the two frames' tables differ by more than 1% of the peak | (**failed**, below) | 0.59%; η at 600 km/s +4.3% |
| 12 | capture refuses a detector table; direct detection refuses a Sun table | refused | passes |

**Rates** (`tests/halo_models/test_shmpp_rates.py`, items 13–14). The xenon rate from the detector table, at 100 GeV,
against the same rate built from the cubature's η and η⊥ (the nuclear responses shared, the halo side independent),
wherever it exceeds 10⁻³ of its peak:

| operator | elastic | endothermic, δ = +50 keV | exothermic, δ = −50 keV |
|---|---|---|---|
| O1 (spin-independent) | 0.02% | 1.75% (reference σ 1.6%) | 0.29% |
| O3 (velocity-dependent) | 0.35% | 0.67% (σ 0.56%) | 0.30% |
| O4 (spin-dependent) | 0.07% | 2.6% (σ 3.0%) | 0.20% |

The declared tolerance was 1%; the endothermic cases failed it through the reference's own noise (below). Doubling ρ₀
doubles every rate and every capture flux to 10⁻¹².

**Three declared expectations failed as declared**, each recorded with its cause in `validation/` before the test was
changed:
- **Item 4** (`item4_failed_tolerance.md`): η = 0 against the SHM's closed form, declared 10⁻⁶, measured 1.2 × 10⁻⁵ (η)
  and 1.8 × 10⁻⁵ (η⊥).
  - The cause is the table's linear interpolation. The error falls as the grid spacing squared, and ADROIT's existing
    tabulation of the SHM shows the same error to 10⁻¹⁵.
  - The test now checks the generator against the SHM tabulated on the same grid (10⁻⁹) and the table against the exact
    closed form within 2 × 10⁻⁵, set after the observation.
- **Item 12** (`item12_failed_expectation.md`): the two frames' tables differ by at most 0.59% of the peak, not the
  "more than 1%" declared.
  - At this instant the Earth's velocity is nearly perpendicular to the Sun's: it adds 1.35 km/s to the boost's speed
    and turns it by 7°. η differs by 4% at v_min = 600 km/s.
  - The frame guards do not depend on the size of the difference.
- **Item 13** (`item13_reference_noise.md`): the endothermic rates missed 1% (at most 1.8%) where δ pushes v_min into the
  tail.
  - Against a reference with 16 times the points, the table agrees within 0.34%.
  - The test now allows max(1%, 4σ), σ the reference's own spread, as item 6 does.

### Spectra, accepted counts and limits (`validation/limits_validation.py`, item 15)

The test is a module's whole 95% procedure, with its detector response and its statistics:
- **with the SHM++ table** as its halo;
- **against the same procedure with an independent halo:** a histogram of laboratory speeds from an independent
  Galactic sampler (2²² Sobol points per component).

| module | kind | mass | SHM++ limit (cm², ρ_ref = 0.4) | independent − 1 | SHM++ / SHM at (233, 528) | time (s) |
|---|---|---|---|---|---|---|
| DEAP-3600 (2019), argon | SI | 100 GeV | 3.0096 × 10⁻⁴⁵ | 2.3 × 10⁻⁵ | 1.049 | 0.3 |
| DEAP-3600 (2019) | SI | 1000 GeV | 1.2984 × 10⁻⁴⁴ | −1.0 × 10⁻⁶ | 0.999 | 0.0 |
| PICO-60 C3F8 (2019) | SD-proton | 30 GeV | 2.5926 × 10⁻⁴¹ | 1.0 × 10⁻⁵ | 1.010 | 3.5 |
| LZ WS2022+WS2024 (DIAMX), xenon | SI | 50 GeV | 2.5450 × 10⁻⁴⁸ | 7.9 × 10⁻⁵ | 0.974 | 160 |

All four pass the declared 1%.

### Capture in the Sun (`tests/halo_models/test_shmpp_capture.py`, items 16–17)

| check | declared | measured |
|---|---|---|
| capture rate, the Sun-frame table against an independent Monte Carlo of the Galactic distribution boosted by v_⊙ (2²⁰ points per component, the same kernel), 100 GeV O4 proton | 1% | −0.02% |
| the same, 10 GeV O1 | 1% | −0.00% |
| the share of the density below 50, 100, 150 km/s in the Sun's frame (2.03 × 10⁻³, 1.62 × 10⁻², 5.45 × 10⁻²) against the lattice | 10⁻⁴ | 4.7 × 10⁻⁵, 1.2 × 10⁻⁵, 5.0 × 10⁻⁶ |
| out of equilibrium (⟨σv⟩ = 10⁻⁴⁰ cm³/s, tanh² = 2.3 × 10⁻⁶): Γ_A(SHM++)/Γ_A(SHM) against (C_++/C_SHM)² | 1% | 2.96287 against 2.96287 (C ratio 1.72130) |
| in equilibrium (3 × 10⁻²⁶ cm³/s): the same against C_++/C_SHM | 1% | 1.72130 against 1.72130 |

The annihilation rate goes as the capture rate squared out of equilibrium, linearly in equilibrium: the existing
evolution, unchanged, with SHM++'s capture rate.

### Track 1 with real modules (`validation/track1_points.py`, item 18)

Twelve points of the halo verdict study, judged at SHM++ and with the published halos:

| point | published | SHM++ |
|---|---|---|
| inelastic_dark_photon#7, alp_portal#11, inert_doublet#5, higgs_portal_scalar#7, scalar_mediator#12 | excluded | excluded |
| z_portal_majorana#3 | viable | excluded (direct detection) |
| higgs_portal_scalar#9 | viable | excluded (direct detection) |
| scalar_mediator#15 | pending | excluded (direct detection) |
| z_portal_majorana#0 | viable | pending (a slow module beyond the point's budget, named) |
| inelastic_dark_photon#5, alp_portal#8, scalar_mediator#16 | pending | pending |

The changes come from ρ₀ = 0.55 against the 0.3 the modules publish with, and from the shape.

- **No limit taken by a count ratio** in any of the twelve.
- **Every comparison in the points' verdicts with no local-halo input is identical** (dwarfs, the CMB, colliders,
  flavour and the others each point has).
- **Capture took the Sun's table** every time it was computed.
- **The Galactic searches** are identical to the same searches in a plain SHM state at ρ₀ = 0.55: they take the density
  alone, each record's profile kept.

The first run's check flagged eight points falsely: it matched the words "no validated count ratio", which name a slow
module's full calculation. It was corrected to match the count ratio's construction and rerun; both runs are kept.

### Track 2, Explain a signal and the workbench

- **The headless journeys** (`tests/ui/acceptance/test_halo_shmpp_journeys.py`) run through the workbench's forms, the
  launched command line, ADROIT's own scan, verdict, certificates, writer, pages and exports.
  - **Track 1:** SHM++ chosen; its applicability shown; every point with its tables, capture with the Sun's; the
    comparison it cannot calculate pending and named; the study's halo line; the export; a stale copy shown stale; a
    resume at the SHM refused; a reanalysis keeping it; two mixtures in one process keeping their own limits.
  - **Track 2:** the fit and the null limit with the detector table; the verdicts with the Sun's; the flags labelled; a
    reanalysis and a promotion keeping SHM++.
  - **Refused, naming why, nothing calculated:** the native joint fit, and a snapshot missing its Sun-frame table.
- **Explain a signal at SHM++** through the command line (`validation/explain_signal.py`, item 20), with the baseline's
  small settings: CDMS II Si (2013), the vector simplified model at 7, 9 and 12 GeV, the four default null searches,
  500 toys and a 4 × 4 plane. It ran in 619 s, a real calculation throughout. Its result:
  - the request's snapshot is SHM++'s generator's output;
  - the study and its Track 1 plane carry one resolution, SHM++'s;
  - all 32 of the plane's direct-detection limits were taken with the tables, and every point of the plane is at the
    benchmark;
  - the band's three masses are excluded at SHM++ (local Z 2.8–3.1), and the study's level is "no thermal".
- **The real-browser journeys** `shmpp_track1` and `shmpp_track2` (below) run real calculations in each track and
  compare each with the same request made on the command line.

## Tests and commands

**New tests: 86.**

| file | tests | what |
|---|---|---|
| `tests/halo_models/test_shm_plus_plus.py` | 33 (2 slow) | items 1–12: the paper, the authors' tables, the cubature, the lattice, the limits, convergence, refusals, frames, the snapshot check |
| `tests/halo_models/test_shmpp_rates.py` | 10 | items 13–14: three operators, three kinematics, the density once |
| `tests/halo_models/test_shmpp_capture.py` | 5 | items 16–17: capture against a Monte Carlo, the slow tail, out of equilibrium, the frame refused |
| `tests/core/test_halo_shmpp_choice.py` | 7 | the SHM's identities pinned; the snapshot; the resolution; every change another identity; a snapshot not the generator's refused; checkpoints; sensitivity halos |
| `tests/orchestrator/test_halo_phase2.py` | 12 | Track 2's fit, nulls, flags and verdicts; Track 1's state, routing, budget, edge clause, infinite limits, capture, Galactic scaling, SD factors, cache keys; interleaving; continuations; export |
| `tests/ui/acceptance/test_halo_shmpp_journeys.py` | 16 | the headless journeys (Track 1, Track 2, refusals), six controls each detecting its defect and failing without it |
| `tests/ui/test_halo_selector.py` | +1 | SHM++ on the form: its benchmark only, its details, its command |
| `tests/orchestrator/test_halo_browser.py` | +2 | the browser layer's SHM++ journeys, controls and mutations, offline |

Phase 1's tests that treated SHM++ as the refused family now use SHM + LMC: `tests/core/test_halo_choice.py`,
`tests/ui/test_halo_selector.py`, `tests/ui/acceptance/test_halo_journeys.py` and `tests/orchestrator/test_halo_browser.py`,
with the mutation `future_family_as_shm`.

**Commands and results** (`scratch_evidence/halo_phase2_2026-11-10/checks/`):

| run | result |
|---|---|
| the SHM++ tests while building (`tests/halo_models`, the contract, the calculations, the selector) | all pass; the slow convergence tests (2) pass |
| the headless SHM++ journeys and their six controls | 16 pass; each control detects its defect at its invariant and reports "unguarded" without it |
| the first full fast suite (`checks/fast_first.log`, 65 min under load) | 5,295 passed, **7 failed**, 652 skipped |
| the seven, the native fit's tests and every halo test after the repair (`checks/after_frame_repair.log`) | 180 passed |
| the full fast suite on the final tree (`checks/fast_final.log`; its tree `checks/tested_tree_final.sha`) | **5,302 passed, 0 failed**, 652 skipped, 61 min; the tree unchanged while it ran |

**The seven failures were a real defect of this branch, repaired.**
- **The defect.** The first design marked a Sun-frame table with a new field, `HaloModel.frame`, in
  `adroit/core/dm_state.py`. That file is one of the fourteen inputs the native PICO-60 validation certificate
  (`experiments/data/native_pico_si_validation.yaml`) byte-hashes, so the certificate stopped validating, and the native
  joint fit lost its certified range. Its replay, its research-assistance runs and its domain and low-mass tests then
  failed (`native_validation.certified_range` gave None).
- **The repair.** `dm_state.py` is restored byte for byte, and a Sun-frame table is a subclass, `SunFrameTable`
  (`halo_models/frames.py`). SHM++'s identities and both tables' sha256 are unchanged by the repair.
- **Why it was missed.** The phase-1 note held that `dm_state.py` is "not fingerprinted", which is true of the limit
  tables only. Every file this branch changes was then checked against every byte-hash list in the package; no other
  file is hashed.

## The SHM baseline, compared

Phase 1's baseline harness (requests; the physics of three halos; twelve points of the halo verdict study with the
published halos and over the region; a Track 1 run of each; Track 2; Explain a signal of each), rerun on this branch
(`scratch_evidence/halo_phase2_2026-11-10/baseline/`, its README). One part was added before any run: `benchmark`, four of
the twelve points at the fixed SHM benchmark, on phase 1's code and on this branch's.

- **Against phase 1's run**, every scientific field is identical in all seven parts. The only differences are nine
  interactions' random `id`s (a fresh UUID each run, `core.state._new_id`), as in phase 1's own comparison. Nothing is
  added or removed.
- **The SHM benchmark** at four points is identical between phase 1 and phase 2.
- **Against phase 1's base** (`5eb3b37`) the comparison is phase 1's: the same UUIDs, and the `halo_resolution` and
  `bound.halo_data` that phase 1 added.
- **The SHM identities** (the benchmark `d4ffb6e326dd…`, the region `512fbd2f0636…`, the published halos
  `7a828ad53ad1…`) are phase 1's. They are pinned in `tests/core/test_halo_shmpp_choice.py`, with the SHM benchmark's
  request record (its fields unchanged).

**How it was run.**
- The harness ran on a frozen copy of the tree, made so that the work could go on meanwhile.
- After the copy, only the workbench's halo component and the reanalysis review changed in `adroit/`, and neither is
  on the harness's paths (`snapshot_vs_final_adroit.txt`).
- A first attempt copied the tree without its package data folders (an rsync exclusion of `data` matched every one). It
  failed at once in every part, and was deleted and rerun.

## Costs

Wall times include other load on the machine (the fast suite and the browser layer partly ran together).

| what | time |
|---|---|
| generating SHM++'s two tables | about 1 s (once a process; cached) |
| checking a stored snapshot against its generator | about 1 s (once a process; cached) |
| a fast module's full procedure with the table (DEAP-3600, PICO-60) | 0.3 s, 3.5 s |
| a DIAMX xenon search's full procedure with the table (LZ, one mass) | 160 s |
| CDMSlite's full procedure (one kind, one mass) | about 23 s (unchanged from the SHM) |
| twelve Track 1 points at SHM++ (`validation/track1_points.py`), first run / again with DIAMX's results on disk | 1,278 s / 14 s |
| the four limit validations (`validation/limits_validation.py`) | 488 s |
| the validation report (`validation/report.py`) | about 2 min |
| Explain a signal at SHM++, a 4 × 4 plane (`validation/explain_signal.py`) | 619 s |
| the baseline rerun, all seven parts | 49 min |
| the headless SHM++ controls | 389 s |
| a full fast suite | 65 min (first run), 61 min (final) |

## The browser layer

The release layer's halo journeys in the installed Chrome (157.0.8103.39), each in a fresh profile with fresh servers,
offline. The logs are in `scratch_evidence/halo_phase2_2026-11-10/browser/`.

**`shmpp_track1`** (Track 1; 222–239 s):
- SHM + LMC is listed but disabled, and SHM++ is enabled.
- Choosing SHM++ takes its fixed benchmark; its numbers and applicability are shown before launch.
- The scan, a real child, runs on a 2 × 2 plane at 2–8 GeV, where CRESST-III and CDMSlite decide. Its command carries
  `--halo benchmark --halo-family shm-plus-plus`.
- Judged in the harness's own process:
  - the saved snapshot is SHM++'s own tables, not interchanged, its generator's output;
  - every one of its 14 direct-detection limits was taken with SHM++'s tables.
- The same request on the command line gives the same resolution, verdict and points.
- The study: its halo line and identity, and the point table's SHM++ column. After a restart, the same.
- The export: each point at SHM++, and `halo.json` with the study's identity and tables.
- A resume at the SHM benchmark is refused, naming the halo.
- Run again as Signal best fits: the draft keeps SHM++ and its tables. With its Sun-frame table removed, the review names
  it before anything is calculated (a missing required input).
- A copy whose certificates were certified on an earlier local-densities file is shown stale, naming the file, and is
  unchanged by viewing (a changed-data stale result).

**`shmpp_track2`** (Track 2; 100–362 s):
- CDMS II Si (2013) with the typed model at 10 GeV, SHM++ chosen; the run is a real child.
- Its snapshot is judged in the harness's own process.
- The same request on the command line gives the same fits and null limits.
- The study's halo line, the same after a restart.
- Run again as Constrain a model: the draft keeps SHM++.
- Explain a signal with a native joint fit at SHM++ is refused before calculating, naming SHM++ (an unsupported
  comparison).

**The runs:**

| run | tree | journeys | controls |
|---|---|---|---|
| `final.log` | before the repair of `dm_state.py` | 13 of 14: every halo journey of phases 1 and 2, twice | 9 of 9 detect their defect |
| `final_after_repair.log` | the final tree | 8 of 8: `network`, `halo_track1`, `shmpp_track1`, `shmpp_track2`, twice | 9 of 9 detect their defect |

The one failure in `final.log` was `shmpp_track2`'s first repetition. The workbench's connection dropped under load
(load average 9.5, with the fast suite alongside) before any halo step: the page's console logged "disconnected:
transport close", and the form came back empty. It passed in the second repetition, and twice on the final tree.

**The controls:**

| control | its defect, restored in the workbench's children | detected at |
|---|---|---|
| `halo_form_ignored` | phase 1: the form launches without the choice | "carries --halo benchmark" |
| `halo_dropped_by_child` | phase 1: a child drops the benchmark | "the point table names each point's halo" |
| `halo_checkpoint_identity_omitted` | phase 1: a checkpoint without the halo | "a resume with another halo is refused" |
| `halo_export_unqualified` | phase 1: the export loses the qualification | "the export names each point's halo" |
| `future_family_as_shm` | a planned family (now SHM + LMC) run as the SHM | "listed, disabled" |
| `shmpp_as_shm` | SHM substituted for SHM++ | "every direct-detection limit taken with SHM++'s tables" |
| `shmpp_isotropic` | the Sausage's anisotropy dropped | "the saved tables are SHM++'s generator's output" |
| `shmpp_frames_interchanged` | the detector's and the Sun's distributions interchanged | "the detector's and the Sun's tables are not interchanged" |
| `shmpp_continuation_reset` | a continuation reset to the SHM | "the draft keeps SHM++" |

The other two named defects are controlled in the headless layer (`test_halo_shmpp_journeys.py`), where they can be
exercised. Each control there is run as built first, must pass, and must then fail at its invariant:
- **a cache keyed without the mixture:** two SHM++ mixtures take one limit;
- **a pending comparison labelled allowed:** a comparison SHM++ cannot calculate is taken as allowed.

## Substitutions

- **Headless journeys** (`SUBSTITUTED` in `test_halo_shmpp_journeys.py`):
  - Track 1's points are a toy evaluation that records the halo in force. Everything around it is ADROIT's.
  - The limit cache's check uses two real CRESST-III limits in process.
  - Track 2 uses a toy germanium search and null with real recoil rates.
  - The complementary verdicts are not computed; the halo they are asked at is recorded.
  - The stale copy is a copy of the study whose certificates name another sha256 for the local densities file.
- **The browser journeys:** no calculation is substituted. The stale copy is made as in the headless layer.
- **Validation:** the independent references are mine, apart from the authors' Monte Carlo tables. No substitution.

## Remaining limitations

- **A fixed benchmark only.** Neither SHM++'s parameter uncertainties (Table I's ranges) nor the halo region's are
  propagated, and comparing SHM++ with the SHM gives no confidence interval.
- **No count ratio.** The slow searches cost a full calculation per (module, kind, mass): DIAMX 160 s, CDMSlite 23 s.
  - A point's budget (2 by default) leaves some comparisons pending.
  - The budget has no command-line or form option yet: it is `FixedHalo.full_calculations` in a request.
  - A validated SHM++ count ratio would need its own declared validation, as the SHM's had; it is not built.
- **At an edge-clause mass** a module gives no limit at SHM++. Over the region and at the SHM benchmark its floor is
  scaled by the SHM count ratio (an existing approximation, unchanged).
- **Not supported:**
  - annual modulation and directional rates (one instant's nondirectional distribution);
  - Path 1 structures and flavour-vector limits;
  - private curves and searches;
  - the native joint fit;
  - pair velocities. Velocity-dependent annihilation keeps ADROIT's fixed conventions.
- **The Galactic searches** take SHM++'s density through each record's own profile: conditional, not a new J-factor
  model. One record says its limit is not to be rescaled; the inconsistency noted in phase 1 is unchanged, its factor
  2.62 at SHM++.
- **The halo flags** vary v₀ and v_esc within SHM++, not η or β.
- **Two of the six named mutation controls run headless only.**
  - A cache keyed without the mixture needs two SHM++ mixtures in one process, which no workbench run makes.
  - A pending comparison labelled allowed needs a comparison SHM++ cannot calculate, which the small real plane does
    not have.
- **The tables are about 64 KB of JSON each.** A request at SHM++ carries both, about 130 KB.

## Not started

Phase 3 (an LMC benchmark), until the owner asks; the owner has queued it to follow this phase.

## Claims that did not hold (a note of 2026-11-11, after the auditor's audit)

The auditor's audit of this phase (the independent audit of 2026-11-11 (halo phase2), pin `df0a27b`) reproduced four defects. These
claims of this record were stronger than the code kept:
- **"`verify` … Anything else is refused by `halo_region.checked` before a calculation"** (above): true of a snapshot of
  SHM++'s form. A snapshot naming SHM++ but holding a standard halo and none of the generated fields was taken for a
  standard benchmark and calculated as the SHM under SHM++'s label (HB-01). `checked` stood before a fresh run, not
  before a continuation, a verdict on a saved scan, a scan's worker or a bundle's replay (HB-02).
- **"uses that snapshot throughout"** (`docs/halo_shmplusplus.md`, its Snapshot): the same check was not made wherever
  the snapshot was put in force (HB-02).
- **"The Galactic searches … take the density alone"** (the twelve points, above): true in a process that had read
  the local densities file once. A long-lived process kept that file's values under a later run's identity for a
  changed file (HB-03, inherited from phase 1).
- **The report** said an SHM++ scan's slow limits came from the standard precomputed tables, which it never read
  (HB-04).

Repaired on branch `hb-fixes` (the halo phase2 repairs record of 2026-11-11):
- the family decides a snapshot's form, and a snapshot of another form is not read;
- every calculation that puts a halo in force checks it (`halo_region.using`), and the variant agent checks it before
  any request;
- a run reads the halo data files it was resolved with, and binds them;
- an SHM++ scan says how its limits were taken.

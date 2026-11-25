# DM6: signal fits and the tournament (Path 2)

Built 2026-09-30. Cost: $0. Every number below comes from a script in
`docs/dm6/`, whose outputs sit beside it, or from the tests.

## 1. What was built

**Signal fits** (`inference/signal_fit.py`). An extended unbinned likelihood
in recoil energy:

    ln L(s) = −(s + B) + Σ_i ln[s f(E_i) + b(E_i)] ,

with the signal density smeared by the resolution at each event. It gives:
- the best fit ŝ;
- the local significance Z = √(2Δln L);
- two-sided 68% and 90% profile-likelihood intervals;
- a vectorised fit of many candidates at once.

For one event it reproduces the closed form of DM5's LZ module to 10⁻¹⁵.

**The global significance** (`inference/look_elsewhere.py`). Background-only
toys, with every candidate fitted to each; the global p-value is the share
reaching the observed maximum. This is LZ's procedure. For a background that
rarely gives more than one event there is also a closed form, which the
toys confirm.

**The tier-1 combination** (`inference/combination.py`). The signal
experiment's profile likelihood plus each null experiment's term, all as
functions of the strength μ (rates ∝ μ²). The null experiments enter by
limit-equivalent likelihoods: the zero-event Poisson likelihood scaled to
reproduce the module's own 90% limit.
- This is exact for a counting search with no events and no background, and
  the usual approximation otherwise.
- The joint minimum gives the joint evidence Z_J.
- The parameter-goodness-of-fit test (Maltoni & Schwetz, hep-ph/0304176)
  measures the tension between the signal and the null experiments:
  χ²_PG = Q(μ̂_J), with one degree of freedom.

**The tournament** (`inference/dm_tournament.py`). The criteria depend only
on what a candidate predicts:
- signal fit, Z_sig;
- global consistency, Z_J and χ²_PG;
- complementary constraints, recorded as not applied until DM7;
- information, AIC = −Z_J² + 2k relative to the background alone.

The ranking is by AIC, with the background-only hypothesis always a
candidate. The records:
- the indistinguishable set (ΔAIC ≤ 2) and the degeneracy classes it spans;
- a contested winner, if the best signal fit is not the best by AIC;
- each candidate's flags. Four kinds are checked:
  - **halo:** Z moves by more than 0.5, or the best-fit coupling by more
    than a factor 2, when v₀ or the escape speed changes;
  - **nuclear:** the same test, with the published shell-model responses in
    place of the revised ones;
  - **validity:** the card's own conditions;
  - **coupling:** a best-fit coupling above 4π.

**The forecast** (`inference/forecast.py`). For each pair of leaders and
each target (Xe, Ar, Ge, CaWO₄, C₃F₈, NaI), it gives the events needed to
separate them at 2σ in two ways:
- from the shape of the spectrum (N₂σ = 4/J);
- from the rate, with both normalised to the observed signal: 4/(1 − r)²,
  where r is the ratio of their predicted rates.

It reports the target and route that need the fewest events. This is a
planning estimate: no background, perfect resolution.

**Path 2** (`orchestrator/signal.py`; command `adroit signal`). Signal →
every candidate of a model space → degeneracy classes (DM4's single linkage
at 20 events) → global significance → the leading candidate of each of the
best classes → tier-1 combination → flags → tournament → forecast → report.
The LZ module now exposes its observations (the event and its resolution)
and its background density (b*, flat; only its value at the event is
published).

**LZ's documented L6 and L9** (cards `L06_LZ`, `L09_LZ`, from
arXiv:2404.17666, Table I). LZ's Tables S7 and S8 are transcribed from the
paper's text by `docs/dm6/transcribe_lz_tables.py` into
`experiments/data/lz_2026_tables_S7_S8.yaml`: 612 entries, the four
unphysical ones omitted.

## 2. The gate

The build plan fixes the gate: Tables S7 and S8 of arXiv:2609.02823 (616
local significances) are reproduced to within 0.3σ for at least 90% of
entries; and on synthetic signals injected into a module, the injected
interaction's degeneracy class is ranked first in at least 80% of cases at
20 events.

### 2a. LZ's local significances (`docs/dm6/lz_significances.txt`)

**579 of the 612 entries, 94.6%, are within 0.3σ: met.** This uses LZ's
conventions and its documented L6 and L9. With Table 1's L6 and L9 it is
94.1%.

The 33 misses are of three kinds:
- **Undocumented definitions:**
  - L6 isovector (5): off even with LZ's own L6;
  - L7 and L13 (10): LZ's numbers suggest it built them from γ^μ currents,
    as it did L6 and L9, but that is not documented, so no card guesses it;
  - L12 (4): LZ's table gives the same reduction as Table 1, yet its
    significances and limits differ. No discrete convention reproduces
    them (2026-10-12, `docs/notes/lz_model_cards.html`, "searching for
    LZ's convention").
- **The electron-recoil leakage region** (11): inelastic O1 at δ = 50–100 keV,
  and three at 250–300 keV at 400 GeV.
- **Scattered single entries** (3), among them L1v at 400 GeV. LZ's 0.3
  there conflicts with its own 0.7 for the identical L5v (DM4, section 4).

### 2b. Injected signals (`docs/dm6/injection.txt`)

The test was fixed before its first run:
- **candidates:** LZ's 612 models;
- **search:** its extended window, in true recoil energy;
- **trials:** 500 injections of 20 signal events each, from uniformly chosen
  models;
- **ranking:** by Δln L;
- **success:** the top candidate is the injected model, or one that cannot be
  told from it at 2σ with 20 events (pairwise, N₂σ > 20).

| reading of "its degeneracy class is ranked first" | success |
|---|---|
| **pairwise, N₂σ > 20 (declared before the run)** | **71.0%: not met** |
| DM4's single-linkage classes at 20 events (26 classes over 612 models) | 91.6% |
| the injected model inside the top set, 2Δln L ≤ 2.3 (median size 21) | 73.4% |
| one-sided, 4/(2 KL(injected ‖ top)) > 20 | 69.8% |
| exactly the injected model on top | 10.0% |

Why the pairwise reading fails:
- **The library is dense.** Each model has a median of 54 neighbours that
  20 events can separate only at between 2σ and about 4σ (5 < N₂σ ≤ 20). The
  best of so many near-shapes often beats the true one.
- **The symmetric measure misleads.** A broader spectrum can fit data drawn
  from a narrower one well, although the reverse fails, and N₂σ is symmetric.

The science is clear: with 20 events on xenon, LZ's 612 models resolve into
about 26 classes, and the ranking finds the right one in 92% of cases. It
cannot resolve them much further.

**Decision for the owner.** The plan's "degeneracy class" is DM4's term, and
DM4 defines classes by single linkage; under that definition the gate is met
(91.6%). The pairwise reading was my own stricter choice, declared before
the run, and under it the gate is not met. The principle of fixing rules in
advance weighs against switching after the fact. Two options:
- accept the gate under DM4's definition, with the pairwise result and its
  diagnosis recorded as a finding; or
- hold it as not met and revise it (for example 50 events, or a one-sided
  measure).

**Gate accepted by the owner (2026-09-30).** Part 2 is read with DM4's
single-linkage classes (91.6%). The pairwise result (71.0%) and its
diagnosis are recorded as a finding.

## 3. Path 2 on LZ's event of interest (`docs/dm6/lz_case.md`)

- **The model space.** LZ's 612 models fall into 26 classes at 20 events.
- **Significance.** The largest local significance is 3.65σ (LZ: 3.4σ).
- **Global significance.** 3.50σ by the closed form (p = 2.3 × 10⁻⁴), and
  p = 2.9 × 10⁻⁴ from 200,000 toys. LZ quotes 2.6σ. The difference is the
  background model. Ours is the calibrated density b*, flat across the
  window, whereas LZ's background rises below about 110 keV, where electron
  recoils leak into the band. That gives background events more chances to
  look like a signal. Our global significance is therefore optimistic,
  which the report states.
- **The leaders.** Inelastic scattering at large splittings (O1 and O4,
  δ = 300–350 keV, 400–4000 GeV) and L12 at 4 TeV. All 8 are within
  ΔAIC ≤ 2: one event cannot choose among them. The background alone ranks
  last (ΔAIC = 11.3).
- **No tension.** CRESST-III, CDMSlite, PICO-60 and DEAP-3600 leave these
  candidates untouched (χ²_PG = 0): they cannot see inelastic scattering with
  δ ≈ 300 keV at all.
- **Flags.** The inelastic leaders are halo-sensitive. With an escape speed of
  500 km/s the best-fit coupling of the leading candidate rises 36-fold. Two
  of the three O4 candidates lose all their events, and the third needs 4.9
  times the coupling, because δ = 300–350 keV sits at the kinematic edge. L12 at 4 TeV needs a coupling above 4π.
- **Forecast.** NaI or CaWO₄ would separate most pairs of leaders with a few
  events, since their iodine or tungsten and light nuclei respond
  differently to spin and to the splitting.

**With XENONnT and PandaX-4T as null experiments as well**
(`docs/dm6/lz_case_xenon.md`; LZ's own WS2024 search shares data with the
extended window and is never combined with it):
- **The inelastic leaders are untouched.** Their recoils (above ~100 keV) lie
  beyond these searches' windows. PandaX-4T sets μ < 7.8 on O1v at 1000 GeV,
  δ = 300 keV, far above its best fit of 0.038.
- **L12 at 4 TeV is constrained.** PandaX-4T allows μ < 60 and XENONnT
  μ < 135, against a best fit of 18. That is mild tension (χ²_PG = 0.44,
  p ≈ 0.5), and the joint evidence falls to 3.45σ. L12 drops from 5th to 8th
  place, still inside the indistinguishable set.

**Found on the way, and fixed.**
- **The nuclear model of the direct route** (DM5's pipeline). For
  interactions beyond O1 it used each module's spin-independent convention,
  often the Helm form factor without spin responses, so the xenon searches
  set no limit on spin-dependent candidates. It now uses the module's
  spin-dependent model.
- **DIAMX returning nothing.** For a spectrum with essentially no events in
  its region of interest DIAMX gives no result. The xenon module now reports
  no limit, with a warning, instead of stopping.

## 4. Not done in DM6

- **Complementary constraints** (tiers 2 and 3): DM7.
- **LZ's L7, L12 and L13 as LZ computes them:** undocumented; to ask LZ.
- **A fidelity-A LZ module** with its background model in (S1, S2), which
  would settle the electron-recoil leakage region and the global
  significance. It needs LZ's background PDFs, which are not public.

## 5. The inherited engine retired

With the owner's go-ahead (2026-09-30) Nomothetica's general engine was
removed from ADROIT in one cut. The separate Nomothetica repository was not
touched. Tag `pre-retirement` (commit `533babe`) holds the code as it was.

- **Removed:** the general library (twenty families, their simulators and
  drivers, response laws, shape search), the fitting stack, the old
  tournament, ingestion, the general agents and their offline client, the old
  pipeline with its gate points, reports, brief and export, the evaluation
  harness and benchmark suites, the workbench, the dashboard and the
  examples: 128 files, 92 test files, about 37,800 lines.
- **Kept:** the schemas in `core/state.py` (provenance, the gates and the
  client record them), provenance, configuration, pricing and the language
  model client, the human-gate protocol and control file, and retrieval.
- **More went than the build plan's reuse table foresaw.** The fitting stack,
  the offline client, the evaluation harness and the workbench were to be
  kept, but each runs only on the general simulators or the general pipeline.
  The table in `adroit_build.md` (section 4) now records both the plan and
  what happened.
- **The suite:** 343 tests pass (975 before; the rest tested removed code).
  The command line keeps `adroit exclude` and `adroit signal`.

## 5a. Path 2 made general (2026-10-01)

At the owner's instruction that LZ's event is a test case, not the target,
Path 2 no longer knows anything about LZ. Everything specific to a search
now comes from its experiment module (`ExperimentModule`, the methods for a
search with events):
- its events and their resolution;
- its background density and energy grid;
- the coupling convention of its published analysis;
- its own model space, if the collaboration published one, else the
  library's: every operator and Lagrangian card, both isospins, any masses
  and splittings.

Also:
- the forecast takes the search's own target, not xenon;
- the validity flags take the search's own momentum range, not LZ's;
- the global significance comes from the one-event closed form only where
  the expected background is below 0.1 events, and from the toys otherwise;
- `adroit signal` needs `--experiment`.

A test runs the whole of Path 2 on a synthetic germanium search with three
events at a few keV and about four expected background events.

**Regression check.** Rerun through the general pipeline, LZ's case
reproduces DM6 exactly:
- the 612 fits to 10⁻¹³;
- the 26 classes, the global significance, the leaders' couplings and joint
  evidence, the ranking and the forecast.

Two differences, both expected:
- the coupling flag's wording;
- DEAP-3600's effectively infinite "limit" on L12 at 4 TeV
  (μ < 1.7 × 10¹⁷, a predicted signal of ~10⁻³⁴ events), which moved by
  2% in numerical noise and enters the combination as zero.

## 5b. Statistics corrected in the release pass (R6, 2026-10-10)

- **The toys' auxiliary measurement.** The likelihood's pull uses σ₊ below θ and σ₋ above it, so the auxiliary
  measurement falls below θ̂₀ with probability σ₊/(σ₊ + σ₋). The toys drew it mirrored, with ½/½ weights, and
  clipped it at 10⁻³. They now reuse the native pair's sampler (`statistics.native_pair.auxiliary_toy`), let
  the measurement fall at or below zero, start the background-only fit from a positive θ, and raise on a failed
  fit instead of scoring Z = 0. In the regenerated CDMS II Si single-idea receipt (20,000 toys) the global Z
  moves from 3.04σ to 2.85σ (p = 2.2 × 10⁻³, 95% interval 1.6–3.0 × 10⁻³); `tests/inference/test_corrected_toys.py`.
- **The Monte Carlo interval.** Every global p from toys is reported with its exact (Clopper–Pearson) 95%
  interval; when no toy reaches the observed maximum, p < 1 − 0.05^{1/N} ≈ 3/N, and Z is a lower bound from it.
- **Class members.** Every member of the leading degeneracy classes (up to 12 each) is combined with the null
  experiments, and the tournament's joint AIC ranks them. Members that fit the signal alike can differ in the
  nulls: on CDMS II Si, O1v leads its class by ΔZ_sig ≈ 0.01 but has Z_J = 0, while O1s (Z_J ≈ 1.3) now ranks
  second, behind the background alone.
- **The ΔAIC set.** With one parameter every candidate has AIC = 2 − Z_J² ≤ 2. When the background ranks first,
  no "indistinguishable" candidate set is formed.
- **Nulls that cannot constrain.** A requested null whose μ_up is infinite, or at least 10 times the signal's
  μ̂, is listed as insensitive rather than as missing coverage, so the eligible view can be reached.
- **The direct route's validation.** Rows are validated by their response structure (`orchestrator.exclusion`):
  - elastic O₁ uses the SI range, and elastic O₄ the SD range of each coupled nucleon;
  - anything else must match a structure validated against published limits on the same target with the same
    responses.

  `docs/dm6/validate_direct_route.py` compares the fidelity-B LZ module with LZ's 43 tables
  (`docs/dm6/direct_route_validation.md`): 201 of 575 entries agree within the DM3 factor of 1.3 in rate, and
  40 of 61 structures have a validated span. Two caveats:
  - The module is 0.8–0.9 times LZ below about 100 GeV, as expected from its missing electron-recoil leakage.
  - L05, L07, L08, L12, L06, L13 and L17 disagree by factors of 2 to 10⁴. Their significances agreed in §2a, so
    the cause is the coupling's normalisation (our cards against LZ's d), which the significances cannot see.
    These are open, and stay unvalidated.

  The other xenon modules compute these structures with the shell-model responses, not LZ's revised ones, so the
  validation does not transfer to them.
- **Halo.** A combination whose nulls use another halo than the signal (the xenon modules' arXiv:2105.00599 SHM
  against the 220 km/s SHM) says so in its note and in the candidate's flags.

## 6. Reproducing DM6

```bash
uv run --with pymupdf python docs/dm6/transcribe_lz_tables.py   # Tables S7, S8 from the PDF
uv run python docs/dm6/lz_significances.py    # gate part 1, a few minutes
uv run python docs/dm6/injection.py           # gate part 2, a few minutes
uv run python docs/dm6/lz_case.py [--with-xenon]   # Path 2 on the event of interest
uv run adroit signal --experiment "LZ extended window (2026)"   # the same, as a command
```

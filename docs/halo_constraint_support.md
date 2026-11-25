# How every constraint depends on the local halo, and what each halo choice does with it

Halo phase 1 (`docs/halo_phase_1_shared_configuration.md`), written at `5eb3b37`; every row updated for SHM++ in halo phase
2 (`docs/halo_phase_2_shmplusplus.md`, the specification `docs/halo_shmplusplus.md`). One row
per consumer: every curated record (`adroit/constraints/data/records.yaml`, 48), every registered experiment module
(7 limit-setting, 3 searches with events), the anomaly, confirmed-anomaly and private routes, the operator and
flavour-vector routes, and Track 2's own uses of a halo. The 34 records with no halo input are mapped to one fully
specified row at the end. `tests/core/test_halo_constraint_support.py` checks that this file names every record and
module the code registers.

**The halo choices** (`adroit/core/halo_choice.py`):

- *published*: each experiment's and record's own published halo.
- *region*: the SHM uncertainty region, `docs/halo_region.md`.
- *benchmark*: the fixed common SHM benchmark `shm-2105.00599` v1. Its values are ρ₀ = 0.3 GeV cm⁻³, v₀ = 238 km/s, v_esc = 544 km/s, v_LSR = (0, 238, 0) km/s, the Sun's peculiar velocity (11.1, 12.2, 7.3) km/s, and the Earth's (29.2, −0.1, 5.9) km/s on 9 March (arXiv:2105.00599, Table 1 and Eq. 12; ADROIT's `HaloModel()`).
- *SHM++*: the fixed benchmark `shmpp-1810.11468` v1 (halo phase 2), a fixed benchmark only. It is the round halo (weight 0.8) and the Gaia Sausage (0.2, β = 0.9) at ρ₀ = 0.55 GeV cm⁻³, v₀ = 233 km/s, v_esc = 528 km/s, as two tables: the detector's frame and the Sun's (`halo_models/shm_plus_plus.py`). Its capabilities are `recoil`, `solar` and `local-density`; it has no `count-ratio`, `annual-modulation`, `directional` or `pair-velocity`.
- *SHM + LMC*: registered, refused until halo phase 3 implements and validates it, which is deferred to a later release
  (the owner, 2026-11-13: the benchmark's data are not public). Nothing is calculated under its name.

**The halo conventions in force** (H1–H3):

- H1 is `HaloModel()` above.
- H2 is the older convention `standard_halo(220, 232, 544)`: ρ₀ = 0.3 GeV cm⁻³, v₀ = 220 km/s, v_esc = 544 km/s, the detector moving at 232 km/s along the rotation, with no separate solar or Earth velocity.
- H3 is a sample of the region: `halo_limits.velocity_halo(v₀, v_esc, ρ₀)`, an SHM with v_LSR = v₀ and H1's solar and Earth velocities.
- T++ is SHM++'s detector-frame table (`FixedHalo.detector()`), and T⊙ its Sun-frame table (`FixedHalo.solar()`).

**Status words:**

- *Exact*: calculated by the consumer's own procedure at the halo in force.
- *Validated approximation*: the SHM accepted-count ratio, inside its validated masses and velocities, at e ≤ 15%. It is a cut only, never combined (`docs/halo_region.md`). It is never used for SHM++.
- *Unsupported*: named, pending. It decides nothing at that halo, an independent exclusion still stands, and nothing is computed at another halo in its place.

## Direct detection: the experiment modules (Track 1's comparisons and Track 2's nulls)

Consumer `direct-detection` in `halo_choice.CONSUMERS` (it needs capability `recoil`).

| Consumer | Code | Inputs actually needed | Existing assumptions | Frame / time | Treatment under each family | Status | Propagation and cache boundary | Test / evidence | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `LZ WS2022+WS2024` | `experiments/xenon.py` (`DiamxXenon`); Track 1 `parameter_space/halo_limits.py: module_limit` | η(v_min) through DIAMX's (S1, S2) likelihood; ρ₀ | H1; Helm; SI validated 8.9–92 GeV; two-sided t̃ | H1, detector frame, 9 March | **published:** own procedure / R10 table. **Region:** count ratio not validated (e = 40%): full procedure within the point's budget, else the halo is unresolved (coverage incomplete). **Benchmark:** H1 *is* its published halo → its own published procedure (`halo_limits.own_halo`), ρ₀ scaled analytically. **SHM++:** no count ratio (the SHM's validation does not cover another shape): its own procedure (DIAMX) with T++ as its halo, within the point's budget, else pending, named (`halo_limits._at_table`). **LMC:** refused (phase 3) | published, benchmark: exact; region, SHM++: exact within budget | Limit table fingerprint (`limit_tables`); `halo_limits.exact`/`accepted` cached by (module, kind, mass, v₀, v_esc); at SHM++ `exact_at_table`/`blind_at_table` by the table's sha256 (`halo_limits.tabulated`); checkpoint and evidence by the request's halo | `tests/parameter_space/test_halo_region.py`, `test_halo_audit.py`; `tests/orchestrator/test_halo_phase1.py` (own-halo route); `test_halo_phase2.py` (routing); phase 2 validation item 15 (LZ SI 50 GeV: the whole procedure with T++ against an independent Monte-Carlo halo) | LZ SD not validated (published limit used other structure factors) |
| `XENONnT SR0+SR1` | `experiments/xenon.py` | as LZ | H1; SI 27.8–1000, SD 21.5–10⁴ GeV | H1 | as LZ; region: SD-n count ratio validated (e = 12.6%), SI (21.2%) and SD-p (15.6%) not; SHM++: as LZ (no count ratio) | as LZ; region SD-n: validated approximation (cut only) | as LZ | as LZ | count ratio fails near threshold at low v₀ |
| `PandaX-4T Run0+Run1` | `experiments/xenon.py` | as LZ | H1; SI 146–9715, SD-n 341–10⁴, SD-p 148–1853 GeV | H1 | as LZ; region: count ratio validated for SI, SD-p, SD-n (e ≤ 5.7%); SHM++: as LZ (its count-ratio validation is the SHM's only) | region: validated approximation (cut only); benchmark: exact; SHM++: exact within budget | as LZ | as LZ | validated masses start far above threshold |
| `CDMSlite Run 2` | `experiments/cdmslite.py` | η through Yellin's optimum interval; median over 300 efficiency realisations | H2; Klos for SD; SI, SD-p, SD-n 1.3–20 GeV | H2 | **published:** own procedure / table. **Region and benchmark:** count ratio not validated (e = 46–90%): full procedure within the point's budget (2), else unresolved/pending. **SHM++:** the same with T++ | exact within budget | as LZ | as LZ | slow full procedure; a benchmark point may be pending on budget |
| `CRESST-III 2019` | `experiments/cresst_iii.py` | η; Yellin's optimum interval | H2 (detector speed 232 km/s assumed); SI, SD-n (¹⁷O) 0.35–130 GeV | H2 | **published:** own procedure. **Region, benchmark:** its own procedure at the halo (`halo_limits.exact`, FAST). **SHM++:** its own procedure with T++ (`halo_limits.exact_at_table`); at an edge-clause mass no limit (pending, named) | exact | `halo_limits.exact` cache by velocities; at SHM++ by the table's sha256 | `test_halo_region.py`; baseline `physics.json`; `test_halo_phase2.py` | maximum-gap fallback decides exclusions only (D1) |
| `DEAP-3600 (2019)` | `experiments/deap3600.py` | η; Cousins–Highland, 0 events | H2; SI 49.7–9942 GeV | H2 | as CRESST | exact | as CRESST | as CRESST; phase 2 validation item 15 (SI at 100 and 1000 GeV: the whole procedure with T++ against an independent Monte-Carlo halo) | — |
| `PICO-60 C3F8 (2019)` | `experiments/pico60.py` | η; profile likelihood with Neyman toys | H2; SD-p 3.0–1000 GeV (edge clause at 3.02) | H2 | as CRESST | exact | as CRESST (its table is ignored at a halo) | as CRESST; phase 2 validation item 15 (SD-p at 30 GeV) | over the region and at the SHM benchmark the edge floor is scaled by the count ratio's factor, unvalidated for this fast module (an existing approximation, unchanged); at SHM++ it is not scaled: the module gives no limit at the edge-clause mass |

## Searches with events (Track 2's signal, Explain a signal's fit) and user-defined routes

Consumers `private-search`, `private-si-curve`, `path1-structure`, `flavour-vector` and `native-joint` in
`halo_choice.CONSUMERS`: each supports the published halos only, and is named as unsupported off them.

| Consumer | Code | Inputs actually needed | Existing assumptions | Frame / time | Treatment under each family | Status | Propagation and cache boundary | Test / evidence | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `LZ extended window (2026)` | `experiments/lz_extended_window.py` | η, η⊥ for 43 structures; one-event profile likelihood | H1; Haxton 2022 responses; background calibrated at its published halo | H1 | **published:** own. **Benchmark:** H1 is its own, so the same. **SHM++:** its expected signal with T++; its background density b* stays (inferred from LZ's quoted significance at LZ's own halo: a property of the data, not of the signal's halo). **Region:** not used for fits (Track 2 has no region) | exact | the request's halo (`SignalRequest.halo`) | `tests/orchestrator/test_halo_phase1.py`, `test_halo_phase2.py` | the background is calibrated at H1 only |
| `CDMS II Si (2013)`, `CDMS II Ge (2009)` | `experiments/historical.py`, `data/historical/*.yaml` | η; Yellin's optimum interval | H2 (Ge declared, the paper says "standard") | H2 | **published:** own. **Benchmark:** its expected signal at the benchmark (`signal._signal` reads the halo in force), every fit and toy. **SHM++:** the same with T++ (`FixedHalo.detector()`) | exact | the request's halo; the toys' shapes from the same signal | `test_halo_phase1.py` (a toy with H2 shows the benchmark moving the fit and null limits); `test_halo_phase2.py` (SHM++ and the SHM benchmark fit differently) | — |
| `record:<path>` (anomaly records), `anomaly:<ref>` (confirmed anomalies) | `experiments/anomaly.py`, `confirmed_anomaly.py` | η; Yellin | the record's own halo; a record omitting it gets H2 silently (`anomaly.py`) | the record's | **published:** the record's halo. **Benchmark:** its expected signal at the benchmark (SHM++: T++) | exact | as above | `tests/experiments/test_anomaly.py` (existing) | a record without a halo is filled with H2 without saying so (existing; not changed) |
| `private-search:<hash>` (signal or null) | `experiments/private_search.py`; Track 1 `parameter_space/private_searches.py` | its paper's halo only | elastic O1, c_p = c_n | its paper's | **published:** its paper's halo. **Region, benchmark (SHM or SHM++):** refused before anything is calculated (`halo_region.check_inputs`; Track 2 `signal.refuse_at_benchmark`) | unsupported (refused) | — | `test_halo_integration.py`, `test_halo_phase1.py`, `test_halo_phase2.py` | holds only its paper's halo |
| Private SI curve (`si_isoscalar_curve`) | `parameter_space/private_limits.py` | σ_SI against a digitised curve | its contract's declared halo, never used in the comparison | — | as `private-search` (refused over the region and at either benchmark, Track 1 and Explain a signal) | unsupported (refused) | — | `test_halo_integration.py`; `test_halo_phase1.py` (Explain a signal, fixed in phase 1) | before phase 1 Explain a signal applied it over the region beside the module it supersedes |
| Private `sm_higgs_invisible` | `parameter_space/private_limits.py` | BR(h → inv) | none | — | no halo input; every choice the same | exact | — | existing | — |
| Path 1 structures (`operator_limits.STRUCTURES`: the anapole) | `parameter_space/operator_limits.py` | each module's limit through Path 1 | each module's published halo; native 90% table | each module's | **published:** as tabulated. **Region:** unsupported (coverage incomplete). **Benchmark (SHM or SHM++):** unsupported: pending, named, its published-halo exclusion not taken (`halo_evaluation.at_benchmark`) | unsupported off published | `operator_limits.limit95` cached without a halo (published only) | `test_halo_phase1.py` (pending; an independent exclusion stands) | no halo variation yet |
| Flavour-vector own DD limit | `parameter_space/flavour_vector.py`, `flavour_limits.py` | Path 1 at each module's halo | published halos | each module's | as Path 1 structures; at a universal point it reduces to the ordinary SI channel, which does vary | unsupported off published | as Path 1 | `test_halo_phase1.py` (consumer `flavour-vector`) | — |
| Native joint signal/null (CDMS II Si with DEAP-3600 or PICO-60) | `parameter_space/native_joint.py`, `native_domain.py`, `orchestrator/native_fit.py` | the pair's own likelihoods at one common published halo; toy calibration | the pair's common H2; refused unless their halos agree | H2 | **published / region** (Explain a signal): at its own common published halo, reported apart (as before). **Benchmark (SHM or SHM++):** refused before anything is calculated (`native_joint.published_halo_only`); its toy calibration belongs to its published halo and is never reused at another | unsupported at a benchmark | its own checkpoint (`native_fit`) | `test_halo_phase1.py`, `test_halo_phase2.py`; browser journey `halo_unavailable` | no benchmark form yet |

## Capture in the Sun

Consumer `capture` (it needs capability `solar`, a solar-frame distribution).

| Consumer | Code | Inputs actually needed | Existing assumptions | Frame / time | Treatment under each family | Status | Propagation and cache boundary | Test / evidence | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `icecube-1612.05949-sd` (Track 1, Track 2, Path 1) | Track 1 `parameter_space/scan.py: _icecube, _sun`; Track 2 `constraints/verdicts.py: telescope`; Path 1 `orchestrator/exclusion.py: _telescope_rows` | the model's capture rate C from a **solar-frame** distribution (`capture.sun_frame`: the Galactic SHM without the Earth's velocity), ρ₀/m; the equilibrium fraction tanh²(t⊙/τ); IceCube's σ limit converted to an allowed capture rate | the limit's side converted to an allowed capture rate at H1 in Track 1 and Path 1, and in Track 2 at the comparison's halo, the one the candidate's capture is taken in (`verdicts.telescope` passes it to both); IceCube's own halo is not recorded; Sun annihilation speed 10⁻³ c (Track 1), 10⁻⁴ c (Track 2) | Galactic SHM boosted to the Sun; no time dependence | **published:** H1 (`HaloModel()`). **Region:** each sample's H3 in the Sun's frame (`halo_limits.capture_halo`). **Benchmark:** the benchmark in the Sun's frame (Track 1 through the halo in force; Track 2's complementary verdicts are now asked at it, and their equilibrium fraction taken in it: `verdicts._channel`). **SHM++:** T⊙, the Galactic mixture boosted by the Sun's velocity alone and angle-integrated there (Track 1 `halo_limits.capture_halo`; Track 2 `FixedHalo.solar()`); `capture.sun_frame` refuses a detector-frame table. The capture-annihilation evolution tanh²(t⊙/τ) and the channel rules are unchanged. **LMC:** refused (phase 3) | exact | the request's halo; nothing cached by halo | `test_halo_integration.py`; `test_halo_phase1.py` (Track 2 verdicts asked at the benchmark); `tests/halo_models/test_shmpp_capture.py` (T⊙ against an independent Monte Carlo through the same kernel, the slow tail, out of equilibrium); `test_halo_phase2.py` (Track 1 takes T⊙) | Track 1 converts the limit side at H1 always, Track 2 in the halo in force (existing conventions, unchanged); Track 1 builds the capture particle from m_χ alone (existing) |
| `icecube-1612.05949-si` | `constraints/verdicts.py: telescope`; Path 1 | as above | as above | as above | Track 2 and Path 1 only; as above | exact | as above | as above | Track 2 judges both SD and SI records, which come from one annihilation-rate bound (existing) |

## Galactic indirect detection

Consumers `galactic-lines` and `antiprotons` (each needs capability `local-density`).

| Consumer | Code | Inputs actually needed | Existing assumptions | Frame / time | Treatment under each family | Status | Propagation and cache boundary | Test / evidence | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `fermi-lat-1506.00013-lines` | `parameter_space/searches.py: lines, _line_comparison` | ⟨σv⟩_γγ, Zγ against the record's limit; the local density only through `halo_limits.density_scale` | isothermal r_s = 5 kpc, R90, ρ(8.5 kpc) = 0.4 (`constraints/data/local_densities.yaml`); line rate at 10⁻³ c or the model's resummed lines | the record's profile; no velocity distribution used | **published:** the record's density. **Region, benchmark:** the record's profile kept, its limit rescaled by (ρ_record/ρ₀)², conditional on the profile's shape (not a spatial recast, no new J-factor). **SHM++:** the same rescaling with ρ₀ = 0.55 GeV cm⁻³ (capability `local-density`), conditional on each record's own profile: the Sausage's local anisotropy is not a Galactic J-factor model. **LMC:** refused (phase 3) | validated approximation of the record under a fixed profile | `local_densities.yaml`'s sha256 in the resolution and the certificate (`Bound.halo_data`) | `test_halo_integration.py` (ρ₀²); `test_halo_phase1.py` (stale when the file changes) | velocity-dependent annihilation is not averaged over a pair-velocity distribution: its fixed convention stays, with any halo |
| `hess-1805.05741-lines` | as above | as above | NFW r_s = 21 kpc, ρ⊙ = 0.39 | as above | as above | as above | as above | as above | a kpc core is not covered |
| `hess-2608.07234-lines` | as above | as above | contracted NFW, 1 kpc core, ρ⊙ = 0.34 (Cautun) | as above | as above | as above | as above | as above | **its record says its limit is not rescaled to other profiles, yet the region and the benchmarks rescale it by ρ₀²** (× 1.38 at the region's centre, 0.78 at the SHM benchmark, 2.62 at SHM++): an existing inconsistency, left for the owner |
| `dampe-2112.08860-lines` | as above | as above | the weakest of Einasto R16, NFW R40, isothermal R86 at ρ = 0.4 | as above | as above | as above | as above | as above | — |
| `calore-2202.03076-pbar` | `parameter_space/searches.py: antiprotons, _pbar_mixture`; `constraints/propagation.py` | ⟨σv⟩ by channel; the propagation factor (conservative/central/aggressive); the local density through `density_scale` | NFW r_s = 19.6 kpc, ρ⊙ = 0.385; conservative = weakest over transport and profiles at fixed ρ⊙ | the record's | as the line records, on top of the propagation choice (kept: conservative/central/aggressive semantics unchanged) | as the lines | as the lines, and the propagation model in the request | `test_halo_integration.py` | the region's ρ₀ envelope sits on the conservative profile envelope (doubly conservative, not double counted) |

## Dwarfs, cosmology and relic density

| Consumer | Code | Inputs actually needed | Existing assumptions | Frame / time | Treatment under each family | Status | Propagation and cache boundary | Test / evidence | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `fermi-1503.02641-dsph` | `parameter_space/scan.py: _gamma_rays`; `classes.fermi_ratio`; Track 2 `verdicts.indirect` | ⟨σv⟩ at the dwarf speed (10⁻⁴ c Track 1, 2 × 10⁻⁵ c Track 2) | the paper's NFW J-factors per dwarf; no local density | dwarf-specific | unchanged by any local-halo choice (dwarf-specific assumptions kept) | exact (as published) | — | baseline `points.json`, `track1.json` | the record's "(Ω/Ω_obs)²" note is not applied (existing) |
| `fermi-2311.04982-spectral` | `constraints/indirect.py: spectral_comparison`; `constraints/dwarf_likelihood.py` | profiled ⟨σv⟩ limit over 42 dwarfs | Gaussian priors on log₁₀ J | dwarf-specific | unchanged | exact | — | as above | — |
| `planck-2018-pann` | `constraints/searches.py: cmb` | p_ann with f_eff; s-wave extrapolated | the cosmic mean density | cosmological | unchanged | exact | — | as above | — |
| `planck-2018-omega` | `constraints/planck.py`; `parameter_space/verdict.py` | Ωh² = 0.1200 | thermal freeze-out | cosmological | unchanged | exact | — | baseline R3 crossings | a subdominant component is judged as all the dark matter (no f or f² rescaling anywhere: no double counting) |
| `sabti-1910.01649-bbn`, `ibe-1912.12152-dark-photon-neff`, `escudero-1901.02010-neff` | `parameter_space/searches.py: bbn, neff, _freeze_in_dark_photon` | ΔN_eff, BBN | cosmological | cosmological | unchanged | exact | — | baseline | — |

## Track 2's own uses of a halo

| Consumer | Code | Treatment unset (each search's published halo) | Treatment at the SHM benchmark | Treatment at SHM++ | Status | Test / evidence |
|---|---|---|---|---|---|---|
| The signal fit, its toys and the classes | `orchestrator/signal.py: _signal, _fit_all, _shapes` | the signal search's own halo | the benchmark (`signal.fixed_halo`, the halo in force) | T++; the toys and the global significance generated from the same templates, no calibration carried from another halo | exact | `test_halo_phase1.py`, `test_halo_phase2.py` |
| The null limits in the combination | `signal._combine` → `exclusion.run` | each null's own halo, a difference noted (`_halo_note`) | the direct route at the benchmark; a null whose published halo is the benchmark keeps its reference route (`_null_halos`) | the direct route with T++ for every null (no module's published halo is SHM++) | exact | `test_halo_phase1.py`, `test_halo_phase2.py` |
| The halo sensitivity flags | `signal._flags`, `ALTERNATIVE_HALOS` | one parameter of `HaloModel()` changed (**not** of the search's own halo: for H2 searches the flag also changes the frame; existing, kept, documented) | one parameter of the benchmark changed, labelled "halo sensitivity (…, from the fixed benchmark)" | SHM++ generated again at the changed v₀ (v_LSR with it) or v_esc (`halo_choice.varied`), labelled "halo sensitivity (…, SHM++ generated again from the fixed benchmark)"; η and β not varied | a labelled check, never the primary, never another family | `test_halo_phase1.py`, `test_halo_phase2.py` |
| The complementary verdicts | `verdicts.judged` | the default SHM (H1) | the benchmark | T⊙ (the telescope verdicts' only use of a halo) | exact | `test_halo_phase1.py`, `test_halo_phase2.py` |
| The forecast | `inference/forecast.py: separate` | the default SHM | the benchmark | T++ | exact | — |
| Physical eligibility (Track 1 points) | `orchestrator/physical_eligibility.py` | Track 1's evaluation with the published halos; a saved Track 1 point reused only if its halo is the same (`_other_halo`; before phase 1 a region point was reused beside published ones) | Track 1's evaluation at the benchmark; reuse only of a benchmark point | Track 1's evaluation at SHM++; reuse only of a point at the same resolution (its tables' sha256 included) | exact | `test_halo_phase1.py`, `test_halo_phase2.py` |
| Path 1 (`adroit exclude`) | `orchestrator/exclusion.py` | each module's own halo | not offered on the command line; Track 2 passes the benchmark to its nulls | as the SHM benchmark (T++) | exact | — |
| The neutrino-fog annotation | `parameter_space/neutrino_fog.py` | `HaloModel()` | unchanged (an annotation, never a decision) | unchanged | — | — |

Two limitations of Path 1 stay as they were: its telescope rows always use `HaloModel()`, and its command line has no halo option.

## The records with no halo input: one row

| Consumer | Code | Inputs actually needed | Existing assumptions | Frame / time | Treatment under each family | Status | Propagation and cache boundary | Test / evidence | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| Collider, accelerator, flavour, precision, laboratory and theory constraints (below) | `parameter_space/searches.py`, `resonances.py`, `scan.py: _collider, _invisible`; `constraints/verdicts.py` | couplings, masses and widths; no dark-matter density or velocity | each record's own | none | unchanged by every choice; their numerical results and review gates are the same | exact (as published) | none by halo | baseline `points.json`, `track1.json` (unchanged) | — |

The records this row covers:
- **Collider:** `cms-2405.13778-V1`, `cms-2405.13778-A1`, `cms-2405.13778-V2`, `cms-2405.13778-A2`, `atlas-2301.10731-hinv`, `lep-hep-ex-0509008-zinv`, `atlas-1903.06248-dilepton`, `lep-contact-bl`, `atlas-2010.14293-squark`, `lmu-ltau-babar-belle2`, `cms-1808.03684-4mu`, `atlas-2301.09342-4mu`, `lep-inert-doublet`, `atlas-2306.00641-2hdma`, `pdg-2024-electroweak-st`, `lep-charginos`, `opal-hep-ex-0309014-sleptons`, `smodels-3.2.1`, `atlas-2207.00092-higgs-mu`, `atlas-2009.14791-zz`, `atlas-2004.14636-ww`, `cms-2107.13021-monojet-spin0`, `cms-1806.00843-dijet`, `atlas-1910.08447-dijet-gaussian`, `cms-1908.01115-ttbar`, `atlas-2108.13391-monoh`, `atlas-2111.08372-monoz`.
- **Beam dump:** `darkcast-dark-photon`, `ccfr-1406.2332-trident`.
- **Flavour:** `flavour-b-to-k-invisible`, `muon-g2-2025`, `lhcb-1612.07818-b-to-k-mumu`, `li-2412.04572-bsgamma`, `dmwg-1810.09420-bsmumu`.
- **Theory certificates:** vacuum stability, unitarity and running. Nothing halo-dependent.

## Scientific notes that hold for every row

- **A local velocity distribution is not a Galactic profile.** The density-squared rescaling of the Galactic searches depends on the profile's shape staying fixed, so it is labelled conditional, never a complete alternative-halo recast.
- **No pair-velocity distribution is derived from any halo.**
  - Velocity-dependent annihilation keeps ADROIT's fixed velocity conventions: 10⁻³ c in the Galaxy and the Sun, 10⁻⁴ or 2 × 10⁻⁵ c in dwarfs, and a CMB extrapolation.
  - The conventions are the same under every choice and are stated in each resolution's limitations.
  - A family whose own claims need the velocities is pending on capability `pair-velocity` until it supplies them.
- **Capture needs a solar-frame distribution.** Changing the Earth's velocity on a detector-frame table is not a frame transformation. A family supplying only a detector-frame table lacks capability `solar`, and capture is pending for it.
- **Each density or weight is applied once.**
  - Each consumer takes ρ₀ once: analytically for direct detection, as the flux for capture, squared for the Galactic searches.
  - The candidate's relic fraction rescales no prediction anywhere.
  - The single SHM component has weight 1; SHM++'s two components have weights 1 − η and η, each normalised alone, applied once in the table.
- **The count ratio is not extended.** Its validation (15% gate, its masses and its velocity ellipse) covers the SHM shape only, inside its sampled domain. It is used for the region and for an SHM benchmark inside that domain, and for no other distribution: never for SHM++.
- **SHM++'s supported set** (halo phase 2): every experiment module's limit by its own procedure with T++ (the slow ones within the point's budget); the signal fits, toys, null limits and forecast of Track 2 and Explain a signal; capture in the Sun with T⊙; the Galactic line and antiproton records by the conditional ρ₀ rescaling. Not supported, named: Path 1 structures, a flavour-vector model's own limit, private curves and searches, the native joint fit, annual modulation and directional rates (one instant's nondirectional distribution), and pair velocities.
- **Unsupported is not unknown everywhere.** An unsupported comparison leaves a point pending unless an independent valid exclusion decides it. It cannot make an allowed point allowed.
- **Signed records are untouched.** A derived halo assumption lives in the request, its resolution and the certificate's `Bound`, never in a record.

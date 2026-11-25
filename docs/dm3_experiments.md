# DM3: experiment modules and limit reproduction

Built 2026-09-29. Cost: $0. The numbers below come from the final
validation run of 2026-09-29. Its results store is
`docs/dm3/validation_results.json` and its summary
`docs/dm3/validation_summary.txt`, both written by
`docs/dm3/validate_modules.py`.

## 1. What was built

**The interface** (`adroit/experiments/base.py`). A module is one search.
It declares:
- the search itself: target, exposure, window, observables, fidelity,
  statistical method;
- the conventions of the collaboration's published analysis: halo, nuclear
  input for each kind of limit, and the target as the analysis treated it;
- its published limits.

Given any interaction it predicts the signal in its observable, and from its
data it sets an upper limit on the signal strength κ. The rate is linear in
a cross-section, so σ_limit = κ_up × σ_reference.

**The statistics** (`adroit/statistics/`):

| method | file | used by |
|---|---|---|
| classical Poisson limit; Cousins–Highland limit with a relative uncertainty on the signal | `poisson.py` | DEAP-3600 |
| counting with free backgrounds: the profile-likelihood statistic, calibrated by a Neyman construction with toy experiments | `poisson.py` | PICO-60 |
| profile likelihood: one-sided limit and discovery significance, asymptotic thresholds (arXiv:1007.1727) | `profile.py` | DM6 fits |
| Yellin's maximum gap, in closed form | `intervals.py` | the fallback |
| Yellin's optimum interval, through Yellin's own code and tables | `optimum_interval.py` | CRESST-III, CDMSlite |

The optimum-interval wrapper reproduces the CDMSlite release's own example
output at all 92 masses, to the three figures the release prints.

**The modules:**

| module | target | data | fidelity | method |
|---|---|---|---|---|
| CRESST-III 2019 (`cresst_iii.py`) | CaWO₄ | the collaboration's release (arXiv:1905.07335): 441 events, efficiencies, limits | B, no background model | optimum interval |
| CDMSlite Run 2 (`cdmslite.py`) | Ge | the collaboration's release (arXiv:1707.01632): 318 events, 1000 efficiency samples, limits | B, no background model | optimum interval; the official median procedure |
| PICO-60 C₃F₈ (`pico60.py`) | C₃F₈ | two exposures; nucleation efficiencies digitised from Fig. 3 of arXiv:1902.04031 | B | profile likelihood with free backgrounds, calibrated with toys |
| DEAP-3600 (`deap3600.py`) | Ar | acceptance and energy scale digitised from Fig. 21 of arXiv:1902.04048; resolution and systematics from its text | B | Poisson with Cousins–Highland systematics |
| LZ WS2022+WS2024, XENONnT SR0+SR1, PandaX-4T Run0+Run1 (`xenon.py`) | Xe | DIAMX's packaging of the public data | A | profile likelihood in (S1, S2), through DIAMX |
| LZ extended window (`lz_extended_window.py`) | Xe | HEPData ins3199115: 43 model tables, three event samples | C | none yet: the reference for DM6 |

`registry.py` lists and loads them by name.

**Figures digitised from their vector data** (`adroit/experiments/data/digitised/`,
made by `docs/dm3/digitise_figures.py`). The published inputs that exist only
as figures are read from the drawing paths of the arXiv PDFs, with the axes
calibrated from the drawn ticks or grid. Each digitised curve was checked
against a number the paper quotes:

| figure | contents | check |
|---|---|---|
| PICO-60, Fig. 3 | best-fit F and C nucleation efficiencies at 2.45 and 3.29 keV, and their 1σ bands | the drawn Seitz lines fall at 2.450 and 3.290 keV |
| PICO-60, Figs. 6–7 | the SD-proton limit; the best-fit integrated efficiencies Φ | 2.56×10⁻⁴¹ cm² at 25 GeV (quoted: 2.5×10⁻⁴¹) |
| DEAP-3600, Fig. 21 | acceptance against photoelectrons; the recoil-energy axis | background-rejection acceptance 35%, as in Table VIII; the energy axis agrees with Fig. 20's to 1% |
| DEAP-3600, Fig. 24 | this analysis's SI limit; DarkSide-50 (2018) as drawn there | 3.97×10⁻⁴⁵ (100 GeV), 1.50×10⁻⁴⁴ (1 TeV); quoted 3.9×10⁻⁴⁵, 1.5×10⁻⁴⁴ |
| LZ, arXiv:2609.02823, Fig. S2 | the extended window's signal efficiency | 50% at 269.9 keV (quoted 269.9) and 5.1 keV (quoted 5.4) |
| LZ, Fig. 1 | LZ's recoil spectra for inelastic O₁ˢ and L₁₀ˢ | our O₁ˢ rate matches at low energy to 1% |

Two findings from the digitising:
- A community compilation of limit curves, first used for validation, was 5–7%
  off the DEAP-3600 figure and about 20% off PICO-60's, and had extended
  PICO-60's curve from 1 TeV to 100 TeV. It is no longer used.
- **LZ's coupling convention is confirmed.** "c^s = 1/m_v²" means c^p = c^n =
  1/m_v²: with that, our elastic O₁ spectrum matches LZ's Fig. 1 to 1% at low
  energy, and to 5–10% elsewhere except near minima of the nuclear response
  (WimPyDD's rounding, DM2).

**Data are fetched, never committed** (`adroit/external/fetch.py`).
Everything fetched lives in the tools folder:
- the CRESST-III and CDMSlite releases;
- Yellin's code;
- DIAMX with its environment;
- the arXiv PDFs that the digitising reads.

The fetcher uses `requests`, paced at one request every three seconds. arXiv
refuses Python's `urllib` (HTTP 406) on files it has not cached.

**DIAMX now works.** The DM0 failure had three causes:
- the build was Intel under Rosetta, not native;
- the in-place build breaks on the folder path;
- alea-inference 0.3.4 needs blueice 1.2.1 exactly.

Built in `~/agentic-dm-tools` with blueice 1.2.1, all 15 of its tests pass.
The build steps are in the manifest.

## 2. Validation

**The rule, fixed before any module was run** (decision 4): the reproduced
limit lies within a factor 1.3 of the published one at every tested mass
across the published range. Every comparison is made under the
collaboration's own conventions (halo, nuclear input, target) and, where
its release allows, with its own method.

**The refinements adopted by the owner after the first run** (section 3),
fixed before the final run:
- **Steep edges.** Where the published limit is steeper than
  |d ln σ/d ln m| = 8, a mass also passes if our curve reaches the published
  cross-section within a 3% shift in mass. It is tested with two more
  limits, at ±3%.
- **Validation module by module.** Each module is validated over a
  contiguous run of passing masses, and outside it serves only as a flag.
  That run is the one holding the tested mass where the published limit is
  strongest, if that mass passes; otherwise it is the widest run.
- **The gate.** A module counts for the gate if its validated range spans a
  decade and includes that mass.

The validation script records each module's range in
`adroit/experiments/data/validated_ranges.yaml`, and
`ExperimentModule.validated_range(kind)` reports it.

**The final run** (2026-09-29). The results store is
`docs/dm3/validation_results.json`; the summary is
`docs/dm3/validation_summary.txt`.

| module | limit | tested | validated range (GeV) | ratio inside | outside the range |
|---|---|---|---|---|---|
| CRESST-III 2019 | SI | 20 released masses, 0.16–130 GeV | 0.35–130 | 0.79–1.17 | 54, 2.8, 1.5 at 0.16, 0.21, 0.27 GeV |
| CRESST-III 2019 | SD-neutron (¹⁷O only) | 20 | 0.35–130 | 0.94–1.11 | 81, 3.2, 1.4 |
| CDMSlite Run 2 | SI, official procedure | 24, 1.3–20 GeV | all | 0.93–1.09; 0.34 at 1.31 GeV, by the edge clause | — |
| CDMSlite Run 2 | SD-proton (Klos et al.) | 24 | all | 1.01–1.21; 5.0 at 1.31 GeV, by the edge clause | — |
| CDMSlite Run 2 | SD-neutron (Klos et al.) | 24 | all | 0.99–1.07 | — |
| PICO-60 | SD-proton | 8, 3–1000 GeV | all | 1.16–1.23; 0.64 at 3.0 GeV, by the edge clause | — |
| DEAP-3600 | SI | 11, 24 GeV–10 TeV | 50–9900 | 0.78–0.96 | 0.58, 0.66 at 24, 30 GeV |
| LZ WS2022+WS2024 | SI | 10, 8.9 GeV–9.9 TeV | 8.9–92 | 0.96–1.26 | 1.31–1.34 from 200 GeV |
| XENONnT SR0+SR1 | SI | 10, 10 GeV–1 TeV | 28–1000 | 0.97–1.12 | 1.54, 1.37 at 10, 17 GeV |
| PandaX-4T Run0+Run1 | SI | 10, 5.1 GeV–9.7 TeV | 147–9700; does not count, as its strongest tested limit (63 GeV) fails | 1.14–1.20 | 0.21, 2.19, 1.93, 1.36 at 5.1, 12, 27, 63 GeV |

**The gate is met.** The build plan asks for one xenon module at fidelity
A or B and three modules on other targets. Two xenon modules count: XENONnT
(28 GeV–1 TeV) and LZ (8.9–92 GeV, just over a decade). PandaX-4T serves as
a constraint only above 147 GeV and as a flag below. Four other targets
count: CaWO₄ (CRESST-III, both limits), Ge (CDMSlite, all three), C₃F₈
(PICO-60) and Ar (DEAP-3600).

For comparison only, outside the rule:
- CRESST-III with the cut survival in reconstructed energy (Eq. 1 read
  literally) passes at every released mass: SI 0.79–1.02; SD-neutron
  0.91–0.98, with 0.16 GeV passing by the edge clause.
- CDMSlite's single best-fit analysis (k = 0.157) reproduces the release's
  best-fit limit at 1.00–1.07 above 1.4 GeV.

**What the comparisons needed.** Each was a documented choice, stated in
its module:
- **CRESST-III: where the cut survival acts** (owner's decision). The
  release is ambiguous:
  - its Eq. 1 applies the cut survival in reconstructed energy;
  - its appendix gives the curve "as a function of simulated energy".

  The module assumes the latter: the cut survival multiplies p_model(E)
  inside the convolution. This is an assumption, not a finding. The two
  readings agree from 0.35 GeV. Below that, ours is the weaker limit, by 54
  times at 0.16 GeV.
- **CRESST-III: the exposure** (owner's decision). It is 5.594 kg days, from
  Table I; the text on the same page says 5.689 kg days. The 1.7% difference
  scales every limit alike.
- **CRESST-III: the Earth's speed.** The paper does not state it; 232 km/s
  (Lewin & Smith) is assumed. The halo scan showed the result insensitive to
  it above 0.3 GeV.
- **CaWO₄ spin-dependent scattering: ¹⁷O only** (owner's decision). CRESST
  counted ¹⁷O as the only spin carrier (⟨S_n⟩ = 0.5, abundance 0.0367%).
  The project gives ¹⁸³W no spin-dependent response at all, not only in the
  comparison (`physics/data/isotopes.yaml`). The reasons:
  - no shell-model structure function exists for this heavy, deformed
    nucleus;
  - its published ⟨S_n⟩ runs from −0.031 (odd-group model, hep-ph/0502232)
    to −0.17 (single particle, as tabulated in hep-ph/0406218), a factor of
    30 in cross-section;
  - CRESST, RES-NOVA (arXiv:2601.16251) and Kang et al. (arXiv:1805.06113)
    all leave it out.

  Its spin-independent scattering is kept. With ⟨S_n⟩ = −0.17 the limit
  would be stronger by factors of about 4 at 3 GeV, 30 at 10 GeV and 300 at
  100 GeV. ⁴³Ca, ²⁹Si and ¹³C likewise have no spin-dependent response here.
- **CDMSlite: the official procedure.** The published limit is the median
  over realisations with sampled efficiencies and Lindhard k uniform in
  [0.1, 0.2]. The module implements it (`official_limit`, 300 realisations,
  run in parallel by `official_limits`).
- **CDMSlite: spin-dependent limits with the Klos et al. structure factors**
  (below). With the shell model of Anand et al., the SD-proton limit was 100
  times weaker than the published one, and the SD-neutron limit 0.68 times
  the published one. With Klos et al., both reproduce to 1–2% above 4 GeV.
- **PICO-60.** It combined its two exposures in a profile likelihood with
  free backgrounds, and did not say how the 90% threshold was calibrated.
  - The asymptotic threshold gives limits about 2.5 times stronger than
    published.
  - A Neyman construction with toys gives 1.16–1.23.
  - Its efficiency nuisance parameters are not public.
  - Separately, our integrated efficiencies are 0.74–0.77 of those marked in
    its Fig. 6, as if that figure used ρ = 0.4 GeV/cm³. With its Φ, our
    limit would be about 10% stronger than published.

  Both questions are in a draft to the collaboration.
- **DEAP-3600.** Its limit folds in systematic uncertainties by the method
  of Cousins & Highland.
  - The module includes the light yield, (6.1 ± 0.4) PE/keVee, and the 2.9%
    exposure uncertainty.
  - It leaves out the quenching and acceptance uncertainties, which are not
    published in usable form and weigh most at low mass. This is the likely
    cause of the deviation below 50 GeV.
  - Against the abstract's numbers the module gives 0.90 (100 GeV) and 0.96
    (1 TeV).

**The Klos et al. structure factors** (`NuclearModel.klos`,
`physics/nuclear.py`, data `physics/data/klos2013_structure_factors.yaml`).

*What they are.* Klos, Menéndez, Gazit and Schwenk (arXiv:1304.7684)
computed the axial structure factor S_A(q) = a₀² S₀₀ + a₀a₁ S₀₁ + a₁² S₁₁
of eight nuclei in the shell model, with chiral two-body currents, and
fitted S_ij(u) = e^{−u} Σ c_n uⁿ, where u = q²b²/2.
- The two-body currents renormalise the isovector coupling a₁ within a
  band. S₁₁ and S₀₁ are given at both of its edges.
- The project uses the middle of the band. At the band's edges, the ⁷³Ge
  structure factors at q → 0 move by ±10% (neutron-only) and ±45%
  (proton-only). The limits move inversely.

*The transcription.* The coefficients are parsed from the TeX source of
v4, whose appendix typos are corrected (`docs/dm3/klos_tables.py`), rather
than copied by hand. As a check, the isospin fits combined as
S₀₀ ± S₀₁ + S₁₁ reproduce the paper's separate proton- and neutron-only fits
to 0.5% of the larger of them, for all eight nuclei.

*The mapping to the responses.* Σ C^τ C^τ' (W_Σ'' + W_Σ')^{ττ'} is S_A(q),
with the couplings C^τ of `nuclear.py`. The sum is distributed as
W_Σ'' : W_Σ' = 1 : 2, the long-wavelength ratio. This is exact for O₄,
which needs only the sum. It is an approximation for O₆, O₇, O₉ and O₁₀,
which see the two responses separately. The model is meant for
spin-dependent limits.

*Scope.* The fits are used up to u = 5, the range of the paper's figures.
That corresponds to recoils of several hundred keV at least, so no search
reaches it.

*The key numbers.* At q → 0 on ⁷³Ge:
- the proton-only structure factor is 105 times the shell model's, because
  the two-body currents let the WIMP couple to the odd neutron;
- the neutron-only one is 0.68 times the shell model's.

These are the factors by which the CDMSlite comparisons had failed.

*One discrepancy in the paper.* The oscillator length printed for ¹⁹F
(1.8032 fm) is that of ²³Na. The paper's formula gives 1.762 fm, and agrees
with every other printed b to 0.1%. The printed value is kept, since the
fit's u is defined by it.

**The xenon searches inherit DIAMX's own fidelity.** Our spectra agree with
the wimprates spectra DIAMX ships to 1.3%, so the deviations come from
DIAMX's model of each detector. Its own benchmarks (the `plots/` of its
repository) show the same shapes:
- XENONnT within about 10% above 30 GeV;
- PandaX-4T up to twice as weak at 10–40 GeV;
- LZ 1.15–1.4 times weaker, growing with mass.

Going from 10⁶ to 10⁷ simulated events per template
(`docs/dm3/xenon_convergence.txt`) lowers the ratios by 3–7%:

| search | mass (GeV) | 10⁶ events | 10⁷ events |
|---|---|---|---|
| LZ | 42, 201, 956 | 1.22, 1.43, 1.43 | 1.16, 1.33, 1.34 |
| XENONnT | 10, 17, 46 | 1.58, 1.40, 1.12 | 1.54, 1.38, 1.07 |

The module defaults to 10⁷, which the validation above used.

**One bug found and fixed.** The first CRESST comparison drifted with mass,
by up to a factor 2. The cause was the smearing: a discrete sum over a
true-energy grid spaced 100 eV, twenty times the 4.6 eV resolution. The
smearing now integrates the density's piecewise-linear interpolant against
the Gaussian in closed form, which is exact on any grid.

**Spin-dependent limits for the xenon searches (added 2026-10-10, release plan R2 follow-up).** The
`xenon_sd` stage of `validate_modules.py` reproduces each search's published SD-neutron and SD-proton 90%
limits with the Klos et al. structure factors (`NuclearModel.klos`), by DIAMX, at 10 masses:

| search | published SD limits | SD-neutron validated (GeV) | SD-proton validated (GeV) | counts for the gate |
|---|---|---|---|---|
| XENONnT SR0+SR1 | the collaboration's data release (Zenodo 10.5281/zenodo.17419967) | 21.5–10⁴ (0.98–1.26) | 21.5–10⁴ (0.96–1.22) | yes |
| PandaX-4T Run0+Run1 | arXiv:2408.00664v2, Figs. 4 and 5, digitised from the vector paths | 341–10⁴ | 148–1853 | no |
| LZ WS2022+WS2024 | HEPData ins2841863 v2 | another reading only | another reading only | no |

- **XENONnT:** within 7% of the published limits from 46 GeV, and 1.6 times weaker at 10 GeV, as for SI.
- **PandaX-4T:** 1.2–1.3 times weaker above 150 GeV and up to twice as weak at 10–60 GeV, as its SI comparison.
  It is entered with its range, but does not count for the gate, as for SI.
- **LZ:** LZ's SD limits use the Hoferichter–Menéndez–Schwenk 2020 structure factors, whose chiral-EFT loop
  functions are released only on request. Ours use Klos et al. 2013, so the comparison is another reading:
  ratios 1.02–1.37 (SD-neutron) and 1.10–1.38 (SD-proton). It is listed in the summary and is not entered in the
  status file.

The new XENONnT ranges turn R2's "SD-neutron has no validated limit" pending outcomes into decisions where the
points are in their models' domains: DMWG A1 at 300 and 1000 GeV is now allowed. (R2's Majorana u_R point at
1000 GeV kept the benchmark's 600 GeV partner, so it lies outside its class's domain.)

## 3. The owner's decisions (2026-09-29)

The first run met the rule only for CRESST-III (SI, under Eq. 1's
reading). The failures were of four kinds, and the owner decided each one
before the final run:

1. **Kinematic edges.** At the lowest published masses, the published
   limit falls by factors of tens per few percent in mass. There a
   sub-percent difference in the threshold becomes a ratio of 2–50. The
   first run's edge points:

   | module | limit | mass (GeV) | ratio | published slope d ln σ/d ln m | shift in mass to match |
   |---|---|---|---|---|---|
   | CDMSlite (official procedure) | SI | 1.313 | 0.34 | −116 | −0.8% |
   | CRESST-III (Eq. 1's reading) | SD-neutron | 0.160 | 0.74 | −8.9 | −1.5% |
   | PICO-60 | SD-proton | 3.02 | 0.64 | −15.9 | −2.2% |
   | DEAP-3600 | SI | 23.8 | 0.58 | −10.2 | −4.6% |

   *Decided:* the edge clause of section 2, with slope threshold 8 and
   shift 3%. The 3% is physics, not fitted. For light dark matter the
   lowest reachable mass scales as the square root of the threshold energy,
   so 3% in mass is about 6% in threshold. That is the size of the
   threshold and energy-scale uncertainties the collaborations quote:
   - PICO's Seitz threshold, ±3–6%;
   - DEAP's light yield, ±6.6%;
   - CDMSlite's Lindhard k, over [0.1, 0.2].
2. **Partial agreement.** Some modules reproduce over only part of the
   published range. *Decided:* validation module by module, over validated
   mass ranges, as in section 2.
3. **Spin-dependent nuclear input.** *Decided:* add the Klos et al.
   structure factors as a second nuclear model, for spin-dependent limits.
   Done (section 2); CDMSlite's spin-dependent limits now reproduce.
4. **Argon.** *Decided:* accept DEAP-3600 as the argon module over its
   validated range, from 50 GeV.

With them, three further decisions on CRESST-III, all recorded in its
module:
- the cut survival acts inside the convolution, as the appendix says;
- the exposure is 5.594 kg days, with the text's 5.689 noted as an
  ambiguity;
- ¹⁸³W carries no spin-dependent response (section 2).

## 4. Questions for the collaborations

Drafts are in `drafts/` (not committed):
- **CRESST** (`drafts/email_cresst.txt`):
  - where the cut survival acts (Eq. 1 on page 3 of arXiv:1905.07335v3,
    against its appendix on page 5 and the Fig. 6 caption on page 6),
    saying that the project has meanwhile followed the appendix;
  - the exposure, 5.689 kg days in the text of page 3 against 5.594 in its
    Table I;
  - a request to confirm that ¹⁸³W was left out of the spin-dependent limit
    for the reasons above;
  - the Earth's speed.
- **PICO** (`drafts/email_pico.txt`): the normalisation of Fig. 6, and how
  the limit's threshold was calibrated.

## 5. Not done in DM3

- The LZ extended window at fidelity A or B. Its efficiency (Fig. S2) is
  now digitised, and its background expectations are in its supplement's
  tables. The module is DM6's first task.
- The Klos band as a nuclear uncertainty. Only the middle of the band
  enters limits; its edges are available (`klos_structure_factors(...,
  band=...)`) for DM6's systematics.
- A DarkSide-50 module. Its 2018 limit is digitised from DEAP's Fig. 24, as
  a second argon check, should one be wanted.

## 6. Reproducing DM3

```bash
uv run python -c "from adroit.external import fetch; [fetch.fetch(n) for n in (
    'CRESST-III data release (arXiv:1905.07335)', 'CDMSlite Run 2 data release (arXiv:1707.01632)',
    'Optimum interval code (Yellin)')]"
uv run --with pymupdf python docs/dm3/digitise_figures.py  # regenerates the digitised tables
uv run python docs/dm3/klos_tables.py WIMP_SD_corrected.tex  # from arXiv:1304.7684v4's source
uv run python docs/dm3/validate_modules.py --write         # over an hour with the xenon searches;
                                                           # without --write it writes to runs/gates/dm3/
uv run pytest tests/experiments tests/statistics             # the offline and data-backed checks
```

DIAMX and its environment are built by hand for now, following its manifest
entry; the set-up command of DM11 will do it.

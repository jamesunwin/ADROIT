# DM5: Path 1 for library models, exclusion plots

Built 2026-09-30. Cost: $0. Every number below comes from:
- the validation store `docs/dm3/validation_results.json` (the `lz_ew`
  stage);
- the gate run `docs/dm5/si_gate.py` (outputs in `docs/dm5/`);
- the tests.

## 1. What was built

**The Path 1 pipeline** (`orchestrator/exclusion.py`; command
`adroit exclude`). It takes a library card and its parameters and:
- resolves the card to operator coefficients;
- predicts the signal in each experiment module;
- sets each module's 90% upper limit on the interaction's strength μ, the
  factor that multiplies all its couplings (the rate goes as μ²);
- marks where each module is validated;
- takes the envelope over the validated modules;
- writes the result (JSON), a plot and a report.

The envelope is the strongest validated limit at each mass. It is not a
statistical combination; that is DM6's joint likelihood.

A module's limit comes by one of two routes:
- **Reference route.** If the card's coefficients are proportional to one of
  the module's reference interactions (spin-independent, or spin-dependent
  on protons or neutrons), the module's published procedure for that
  reference is used and rescaled (`ExperimentModule.reference_limits`).
  - This is exact, by linearity.
  - It reproduces the collaboration's own procedure, e.g. CDMSlite's median
    over realisations.
  - It reuses the xenon searches' cached templates.
- **Direct route.** Otherwise the signal is computed and the module's own
  statistics set the limit.

**Nuclear responses from the revised xenon density matrices**
(`physics/haxton.py`, `NuclearModel.haxton_2022`). LZ has used, since 2023,
one-body density matrices for xenon that Haxton and McElvain revised after
the published shell-model tables (arXiv:2312.02030). They are public
(github.com/Berkeley-Electroweak-Physics/Elastic, no licence stated).
- The eight response functions are computed from these matrices with the
  multipole matrix elements of the same group's Mu2e scripts (BSD-3).
- The scripts run in their own environment, `<tools>/.venv-mu2e`, driven by
  `physics/haxton_driver.py`. Both repositories are fetched into the tools
  folder, never copied here; the tabulated form factors are cached there.

The machinery is checked against itself exactly. With the older USD (`bw`)
density matrices that underlie the published tables, it reproduces all
eight responses of ¹⁹F and ²³Na, in every isospin combination and with the
interference signs, to 10⁻⁵.

For xenon the revision matters:
- the charge response is unchanged at low momentum transfer;
- the spin responses Σ′ and Σ″ are about twice the published ones at q → 0
  (¹²⁹Xe ×2.1, ¹³¹Xe ×1.9);
- the other responses change by tens of percent to factors.

**LZ's extended-window search as a fidelity-B module**
(`experiments/lz_extended_window.py`). LZ fits 1,710 events, nearly all
electron recoils, in (S1c, log S2c) with background models that are not
public. Above about 100 keV, however, the nuclear-recoil band is almost
free of background. There the inference is dominated by the one
nuclear-recoil-like event, the event of interest at
248 ± 23 (stat) ± 23 (sys) keV. The module keeps just that:
- **Signal:** exposure (220 d × 4.71 t) × efficiency (Fig. S2, digitised in
  DM3) × dR/dE.
- **Likelihood:** L(s) = e^{−s}[s f(E*) + b*]. Here f(E*) is the signal's
  normalised density at the event, smeared by σ* = 32.5 keV, and b* is the
  nuclear-recoil-like background density there.
- **b\*:** fixed by one published number, the 3.4σ local significance of
  L10 (isoscalar, 1000 GeV) in LZ's Table S7. This gives
  b* = 5.0 × 10⁻⁶ events/keV.
- **Intervals:** two-sided profile-likelihood intervals at 90%, with the
  asymptotic threshold 2.706.

It leaves out the electron-recoil leakage into the nuclear-recoil band below
about 110 keV.

**LZ's conventions.** Reproducing LZ's numbers needs three choices, each
found from LZ's own papers:
1. **The Lagrangians' matching scale is m_M = m_N**, not m_v
   (arXiv:2404.17666). The library's cards keep Anand et al.'s default m_v;
   `lz_values` sets m_N for LZ comparisons.
2. **The revised xenon density matrices**, as above.
3. **Several of LZ's L_j are not Anand et al.'s.** LZ's covariant paper gives
   L6 and L9 with a vector current γ^μ where Table 1 has P^μ/m_M. Our
   limits for L5–L9, L12, L13 and L17 differ from LZ's by factors that vary
   with mass, while L1–L4, L10, L11, L14, L15, L19 and L20 reproduce. DM6,
   which must reproduce all of LZ's significances, needs LZ's definitions
   as cards.

**Smaller changes.**
- `ValidationResult` now records what is compared and along what (for
  example a coupling limit along a mass splitting), keyed by a model label
  where there is no cross-section kind.
- The gate criterion along a splitting, which starts at zero, is half the
  tested range instead of a decade.
- The validation script has a stage for the LZ extended window
  (`--only lz_ew`).

## 2. The gate

The build plan fixes the gate: the plot for the standard spin-independent
interaction matches the published combined picture, and LZ's published
limit curves for the inelastic O1 and L10 interactions are reproduced
within the DM3 tolerance.

### 2a. LZ's L10 and inelastic O1 (arXiv:2609.02823, Fig. 6)

| curve | tested | result under the rule | ratio d_up(ours)/d_up(LZ) |
|---|---|---|---|
| L10 isoscalar, against mass | 13 masses, 10 GeV–4 TeV | **every point passes** | 0.83–1.04 |
| inelastic O1 isoscalar at 1000 GeV, against splitting | 7 splittings, 0–350 keV | fails at δ = 150 keV only | 0.96, 0.81, **0.65**, 0.80, 0.95, 0.96, 0.88 |

- **Local significances.** The event of interest's local significance for
  L10 is reproduced to about 0.2σ at every mass (2.89 against 2.9 at
  100 GeV; 3.37 against 3.4 at 400 GeV). The same holds for inelastic O1
  (2.1 against 2.2 at δ = 150 keV; 2.7 against 2.7 at 200 keV). Only the
  L10 3.4σ point at 1000 GeV was used to fix b*.
- **Lower limits.** Our lower limits are 0.6–0.7 of LZ's. The asymptotic
  one-event interval, [0.11, 3.65] events, is wider below than LZ's
  toy-based construction.
- **The δ = 150 keV failure.** At δ = 150 keV the signal lies mostly at
  80–200 keV, where electron recoils leak into the nuclear-recoil band. LZ's
  limit there corresponds to 8.6 signal events, against the 3.6 of a
  background-free treatment. LZ's median expected limit for this model
  (about 4.4 events, against about 1.8 for L10 at 1 TeV) shows the
  background present. The module does not model it; DM6's likelihood must.
  The pass at δ = 0 is partly fortunate for the same reason. LZ's median
  expected limit there is also 4.4 events, but its observed limit (2.9
  events) is like one for no events at all.
- **The validated range.** Under the refined rule, the splitting scan is
  validated from 0 to 50 keV, the passing run that holds its strongest
  published limit (δ = 0). The points from 200 to 350 keV, where the
  inelastic physics matters most, also pass, but they are a separate run.

For information, every other model LZ tabulates was compared too
(`docs/dm3/validation_summary.txt`):
- L10v passes at every mass;
- O4 (inelastic, isoscalar) passes at every point at all three masses;
- L1, L2, L3, L4, L11, L14, L15, L16, L19 and L20 reproduce over most of
  their ranges;
- the models whose LZ definitions differ from Table 1 do not (section 1).

### 2b. The spin-independent picture

The library's card O1 with c^p = c^n was run through all seven modules, each
at its DM3 validation masses (`docs/dm5/si_gate.py`; the plot is
`docs/dm5/si_exclusion.png`). Every limit came by the reference route, i.e.
by each collaboration's own procedure.

Our envelope over the validated modules was compared with the envelope of
the same collaborations' published curves, each over its validated range.
The comparison was made at each computed mass where the computing module is
the strongest validated one, so that no interpolated curve decides the
envelope:

| mass range (GeV) | module setting the envelope | ours/published |
|---|---|---|
| 0.35–1.5 | CRESST-III | 1.01–1.17 |
| 1.9–7.2 | CDMSlite (official procedure) | 0.93–1.04 |
| 8.9–92 | LZ | 0.96–1.26 |
| 129 | XENONnT | 0.99 |
| 147–9,700 | PandaX-4T | 1.14–1.20 |
| 9,900 | DEAP-3600 | 0.94 |

**30 masses, 0.93–1.26: the rule is met at every one.**

On a dense grid, where each module is interpolated between its computed
masses, the ratio reaches 1.41 at 12–35 GeV (LZ). That is the interpolation
of a module computed at only 10 masses against LZ's finely drawn curve, not
the module: at its computed masses LZ reproduces at 0.96–1.26.

Found on the way, now fixed:
- the status file rounds range edges to four decimals, so masses on an edge
  were read as outside it; range checks now allow 10⁻⁴;
- a module's "strongest" limit in the report is now its strongest validated
  one.

### Verdict

- **Part 1 (the spin-independent picture): met.** At all 30 compared masses
  the ratio is 0.93–1.26, from 0.35 GeV to 10 TeV.
- **Part 2, L10: met.** Every mass passes, at 0.83–1.04, and the local
  significances are reproduced.
- **Part 2, inelastic O1 at 1000 GeV: met at 6 of 7 splittings.** The one
  failure is δ = 150 keV (0.65). The signal there lies in the
  electron-recoil leakage region, which the fidelity-B module does not
  model; LZ's own median expected limit shows the background.
  - Under the refined rule the curve is validated from 0 to 50 keV, and the
    points from 200 to 350 keV pass as a separate run.

**Gate accepted by the owner (2026-09-30)**, with δ = 150 keV recorded as
outside the fidelity-B module's domain and left to DM6's full likelihood.

**Addendum (DM6, 2026-09-30): a bug in the direct route, fixed.** For
interactions not proportional to a reference, the pipeline computed signals
with each module's spin-independent nuclear convention. That is often the
Helm form factor, which has no spin responses, so spin-dependent
interactions gave zero rates on xenon and no limit. The direct route now
uses the module's spin-dependent model for any interaction beyond O1
(`exclusion._direct_model`). The spin-independent gate above used the
reference route and is unaffected.

## 3. Also done

- **DM4's degeneracy analysis, rerun with LZ's revised responses**
  (`docs/dm4/lz_reduction_haxton_2022.txt`). Every conclusion holds, and the
  isospin statement becomes sharper. Every interaction LZ lists as
  isospin-degenerate now needs at least 6,730 events to separate its
  isoscalar and isovector forms (296 with the published responses); every
  other needs at most 18.

## 4. Not done in DM5

- **LZ's own definitions of L5–L9, L12, L13 and L17** as cards. DM6 needs them.
- **The electron-recoil leakage below about 110 keV** in the LZ module (DM6's
  full likelihood).
- **A threshold for DM6's degeneracy classes** (from DM4).

## 5. Reproducing DM5

```bash
uv run python -c "from adroit.external import fetch; [fetch.fetch(n) for n in (
    'Elastic density matrices (Haxton & McElvain)',
    'Mu2e nuclear-response scripts (Berkeley-Electroweak-Physics)')]"
# build <tools>/.venv-mu2e: numpy scipy pyyaml multipledispatch matplotlib py3nj
uv run python docs/dm3/validate_modules.py --only lz_ew    # the gate's LZ curves, a minute (--write to keep)
uv run python docs/dm5/si_gate.py                          # the SI picture, about an hour (to runs/gates/dm5/)
uv run adroit exclude L10 --isospin s --values m_M=0.93149410242 --masses 100,1000
```

# The portal library, part 2: long-range effects, more models, more searches

Started 2026-10-03, at the owner's request after the portal library. The owner:
- verified the two invisible-width records;
- accepted the difference at the Higgs resonance;
- asked for the three items the first part left unbuilt:
  - the Sommerfeld effect and bound states;
  - the 2HDM+a, the inert doublet, the wino and the higgsino;
  - records for the CMB, beam dumps, flavour, dilepton and coloured-partner
    searches.

This record covers what was built, the validation (declared before it was
run), and its result.

## 1. A general tree-level engine, and published models as input

`constraints/tree.py`:
- **Input:** a model given as particles and Feynman rules. The vertex kinds
  are SSS, SSSS, VSS, VVS, VVSS, VVV, FFS and FFV.
- **Diagrams:** for any 2 → 2 process it finds every tree diagram (contact,
  s-, t- and u-channel).
- **Evaluation:** explicit polarisations and spinors, in the unitary gauge.
- **Checked:** it reproduces each process built by hand earlier to 10⁻⁹ or
  better (scalar QED, SS → hh, χχ̄ → φφ, χχ̄ → Zh, s-channel exchange into
  fermions), and the triple-gauge vertex through χχ̄ → Z* → W⁺W⁻.

`constraints/ufo_model.py` reads a published UFO model (FeynRules' format) at
a parameter point:
- it translates the Lorentz structures the engine knows;
- it drops Goldstone bosons, ghosts and gluon vertices, and lists what it
  dropped;
- it computes tree-level widths. MG5's SM Z and W widths are reproduced to
  0.003% and 0.1%.

`parameter_space/portals/ufo.py` makes any such model a portal: every
annihilation and coannihilation channel of the bath, through the
coannihilation solver. On DM8's Higgs-portal UFO it agrees with MadDM to
3.5–4.5%, at about 2 s per point.

**A bug found by the 2HDM+a check.** For a fermion pair the engine looked up the
particle–antiparticle vertex even when the pair was two particles (χχ of a Dirac
fermion). So χχ → b b̄ was counted as if it were χχ̄, which doubled a Dirac model's
annihilation rate. It showed as a constant factor of 0.55 against MadDM. The lookup now
uses the pair's own second particle, and a test covers it. The bug was only in the UFO
path, which was not yet committed; the hand-built portals use `processes`.

## 2. The Sommerfeld effect and bound states

`constraints/sommerfeld.py`:
- **The Coulomb factor** S = X/(1 − e^{−X}), X = πα_eff/β, and its colour decomposition.
  For a triplet and its antiparticle the singlet has +4/3 α_s and the octet −1/6 α_s. For
  two triplets the antitriplet has +2/3 α_s and the sextet −1/3 α_s.
- **The multi-state solver.** It solves the matrix Schrödinger equation of an N-channel
  pair with Yukawa and Coulomb potentials. It matches to Coulomb waves in open channels
  and to Whittaker functions in closed ones. The output is A, the wave functions at the
  origin, so state j annihilates at σv_j = (A†ΓA)_jj.
  - It reproduces the Coulomb factor to 10⁻³.
  - A Yukawa potential lies between no enhancement and the Coulomb one, as it should.
- **Bound-state formation** of a scalar colour triplet and its antiparticle. The octet
  pair is captured into the colour-singlet ground state by emitting a gluon (Harz & Petraki
  arXiv:1805.01200, Garny & Heisig arXiv:2112.01499).
  - The bound state decays into gluons and is ionised by the bath's gluons (detailed balance).
  - The two are taken in ionisation equilibrium, so a pair's rate depends on the
    temperature. It enters the relic solver as a new kind of term,
    `relic.omega_h2_species(..., thermal=...)`, weighted by the pair's equilibrium
    fraction n_i n_j/n².

**In the t-channel portal** (`portals/tchannel.py`):
- Each colour channel of φφ* and φφ has its Sommerfeld factor, with α_s at the momentum
  transfer (not below the Bohr momentum).
- A lepton partner has the hypercharge Coulomb factor.
- A coloured partner forms bound states.
- Both effects can be switched off (`sommerfeld`, `bound_states`).
- The ⚠ flag on coloured partners within 20% of the dark matter's mass now appears only
  when the effects are switched off.

**Electroweak multiplets** (`portals/multiplet.py`): the wino (a Majorana triplet) and the
higgsino (a Dirac doublet, Y = ½).
- Two-particle states are grouped by charge and spin.
- Each sector has a potential matrix and an annihilation matrix:
  - the wino's are from Hisano et al. and Cirelli, Strumia & Tamburini, with the Q = 1
    sign by spin from Mitridate et al.;
  - the higgsino's are from Cirelli et al., normalised to Griest–Seckel.
- At tree level and without splitting, the rate is exactly the known σ_eff: 37πα₂²/12M² for
  the wino, and π(81 + 12t² + 43t⁴)α₂²/128M² for the higgsino.
- With the Sommerfeld effect, the rate is thermally averaged over each state and weighted
  by the charged states' Boltzmann factors.
- The relic solver takes it as a whole (`relic.omega_h2_rate`).
- Direct detection: the wino's σ_SI = 2.3 × 10⁻⁴⁷ cm² (Hisano, Ishiwata & Nagata
  arXiv:1504.00915, read from the abstract). The higgsino's loop-induced scattering is not
  computed (pending).

## 3. The new models

The library now has 25 entries: 22 portals and DM13's three simplified models.

| id | model | how it is computed | benchmark |
|---|---|---|---|
| `inert_doublet` | the inert doublet (high mass) | its FeynRules UFO through the UFO portal; H₀, A₀, H± coannihilate | Kalinowski et al. HP10, Ωh² = 0.12478 |
| `two_hdm_a` | the 2HDM+a, Dirac dark matter | the LHC DM Working Group's UFO; the scalars' widths computed | DMWG eq. (4.5) with ATLAS's scenario 5 heavy masses (1 TeV) |
| `wino` | a Majorana SU(2) triplet | `ElectroweakMultiplet` with the Sommerfeld effect | thermal mass 2.88 TeV (Beneke et al.) |
| `higgsino` | a Dirac SU(2) doublet | the same | thermal mass ≈ 1.1 TeV |

**Where the UFO files come from.** Both are external items of `adroit setup`, fetched and
converted to Python 3 with MadGraph's `convert model`. They are never copied into the
repository, because no licence is stated for them.

**Where the 2HDM+a's relic is 0.12.** At M_a = 400 GeV, Ωh² falls from 1.58 at
m_χ = 150 GeV to 0.011 at 170 GeV (the top threshold and the a pole), so it crosses 0.12 in
between. ATLAS's MadDM statement for scenario 5 is ≈ 170 GeV.

## 4. The searches (ten new records, unverified)

Each search is an evaluator (`parameter_space/searches.py`) on a record
(`constraints/data/records.yaml`). A point where a search applies is excluded, allowed, or
undecided with the reason; undecided makes it pending. Every new record is **unverified**
until the owner verifies it, so by default these searches show as pending ("awaits a
person's verification"); `adroit track1 --unverified` uses them.

| record | applies to | what is compared |
|---|---|---|
| `planck-2018-pann` | every model where p_ann could exceed a tenth of Planck's limit even with f_eff = 1 | Σ f_eff ⟨σv⟩_s-wave/m < 3.2 × 10⁻²⁸ cm³ s⁻¹ GeV⁻¹; Slatyer's f_eff; cascades bracketed |
| `darkcast-dark-photon` | dark photons, m_A′ ≤ 200 GeV | 26 published limits via DarkCast: prompt on ε√BR_vis, invisible on ε√BR_χχ̄, displaced and beam dumps only with A′ → χχ̄ closed |
| `flavour-b-to-k-invisible` | the pseudoscalar portal, m_a < m_B − m_K | BR(B⁺ → K⁺a) BR(a → χχ̄) < 3.7 × 10⁻⁵ (BaBar), Dolan et al.'s rate; a visible a is undecided |
| `atlas-1903.06248-dilepton` | B − L, 250 GeV – 4.5 TeV (restricted from 6 TeV on 2026-10-12: undecided above) | σ_fid B(ℓℓ) against ATLAS's limit at the Z′'s width; leading-order σ × ATLAS's own SSM normalisation (K = 1.087, which holds to about ±10% up to 4.5 TeV; ATLAS's SSM fiducial σ falls to 0.58 of LO at 6 TeV) |
| `lep-contact-bl` | B − L above 209 GeV | M_Z′/g > 6.9 TeV |
| `atlas-2010.14293-squark` | partners of u_R and d_R | inside ATLAS's one-squark contour (m_φ ≥ 400 GeV) |
| `muon-g2-2025` | L_μ − L_τ (positive) and the μ_R partner (negative) | Δa_μ within 38 ± 1.96 × 63 (× 10⁻¹¹) |
| `lmu-ltau-babar-belle2` | L_μ − L_τ | BaBar's 4μ on g′ √(BR_μμ/BR_μμ without DM), Belle II's invisible Z′ on g′ √BR_inv; CCFR trident is evaluated separately through `ccfr-1406.2332-trident` with its own verification policy |
| `lep-inert-doublet` | the inert doublet | Lundström et al.'s region, m_H± > 70 GeV, the Z and W widths |
| `atlas-2306.00641-2hdma` | the 2HDM+a at its benchmark couplings with a → χχ̄ open | (M_a, M_A) below ATLAS's boundary |

**Data handling.**
- The HEPData tables are bundled, as derived in `scripts/derive_records.py` (ATLAS CC0;
  Belle II CC BY 4.0, attributed in its record).
- DarkCast (GPL) and Slatyer's f_eff (no licence stated) are fetched into the tools folder
  and never copied.
- The CMB applies only where it could matter. Otherwise an unverified CMB record would
  make every point of every model pending.

**What these searches change for the library's benchmarks** (with `--unverified`):
- the B − L benchmark is excluded by ATLAS's dileptons and the CMB, and was already excluded by
  Fermi-LAT's dwarfs;
- the L_μ − L_τ benchmark stays pending on CCFR;
- the u_R partner benchmark is excluded by direct detection, as before;
- the inert doublet's HP10 passes LEP and the CMB, and is pending on LHC dileptons and
  electroweak precision;
- the wino and higgsino are pending on disappearing tracks and γ-ray lines.

## 5. The validation

`scripts/validate_portal_library_2.py`: local computation only ($0), about 7 minutes.

**How the ranges were set.** Unlike part 1's validation, these ranges were written
**after** the development runs had shown our numbers. They were not tuned to those
numbers:
- The inert doublet and the 2HDM+a have tolerances of 6% and 10%. Part 1's comparisons
  with MadDM varied by that much, from the codes' g* bookkeeping and quark masses.
- The thermal masses use the spread of the published values, or ±5–7% around a single
  value.
Read the table as a record of agreement with the literature, not as a blind gate.

Run on 2026-10-03:

| gate | ours | range | reference | result |
|---|---|---|---|---|
| inert doublet BM5 (Belyaev): Ωh² / published | 0.954 | 0.94–1.06 | micrOMEGAs (papers) | pass |
| inert doublet BM6 (Belyaev): Ωh² / published | 1.026 | 0.94–1.06 | micrOMEGAs (papers) | pass |
| inert doublet HP2 (Kalinowski): Ωh² / published | 0.974 | 0.94–1.06 | micrOMEGAs (papers) | pass |
| inert doublet HP8 (Kalinowski): Ωh² / published | 0.981 | 0.94–1.06 | micrOMEGAs (papers) | pass |
| inert doublet HP10 (Kalinowski): Ωh² / published | 0.983 | 0.94–1.06 | micrOMEGAs (papers) | pass |
| 2HDM+a (M_A, M_a, m_χ) = (600, 250, 150): Ωh² / MadDM | 1.056 | 0.9–1.1 | MadDM 3.3, same UFO | pass |
| 2HDM+a (M_A, M_a, m_χ) = (600, 250, 300): Ωh² / MadDM | 1.065 | 0.9–1.1 | MadDM 3.3, same UFO | pass |
| 2HDM+a (M_A, M_a, m_χ) = (1000, 400, 170): Ωh² / MadDM | 1.079 | 0.9–1.1 | MadDM 3.3, same UFO | pass |
| 2HDM+a (M_A, M_a, m_χ) = (1000, 400, 300): Ωh² / MadDM | 1.080 | 0.9–1.1 | MadDM 3.3, same UFO | pass |
| u_R partner, Δm → 0, y = 0.01: thermal mass, no long-range effects (TeV) | 1.288 | 1.2–1.4 | De Simone et al. 1.3 | pass |
| … with the Sommerfeld effect (TeV) | 1.720 | 1.6–1.8 | De Simone et al. 1.7 | pass |
| … with bound states (TeV) | 2.909 | 2.4–3.3 | Becker 2.4, Liew 2.5, Harz 3.3 | pass |
| b_R partner, Δm = 20 GeV, y = 0.5: gain from the long-range effects | 1.592 | 1.45–1.8 | Garny & Heisig 1.67 (with excited states) | pass |
| wino thermal mass, tree level (TeV) | 2.340 | 2.15–2.45 | Beneke 2.22, Cirelli 2.4 | pass |
| wino thermal mass, Sommerfeld (TeV) | 3.025 | 2.7–3.1 | Beneke 2.88, Hisano 2.7–3.0 | pass |
| wino gain from the Sommerfeld effect | 1.293 | 1.25–1.35 | Beneke 1.30 | pass |
| higgsino thermal mass, Sommerfeld (TeV) | 1.113 | 1.0–1.15 | Bottaro 1.08, Cirelli ≈1.0–1.1 | pass |

**17 of 17 pass.** Things the table does not show:
- The inert doublet's low-mass points (BP1–BP4, BM1–BM4) are not compared. Their published
  values include off-shell WW* and ZZ*, which a 2 → 2 code omits.
- The 2HDM+a is 6–8% above MadDM, systematically. The likely cause is the codes' g*
  tables and Bessel-function expansions; it was not traced further.
- The higgsino's Sommerfeld effect comes out at 0.2% on the thermal mass. Beneke et al.
  find 3–4% on Ωh² in near-pure MSSM higgsinos with larger splittings; Cirelli et al. call it
  negligible.

The tests (`tests/constraints/test_tree.py`, `tests/parameter_space/test_searches.py`,
`tests/parameter_space/test_multiplets_and_ufo.py`) hold the analytic checks:
- the tree engine against the hand-built processes;
- the Coulomb and Yukawa limits of the solver;
- the multiplets' tree-level traces;
- the g − 2 limits;
- Dolan et al.'s B → K a rate;
- the bundled tables against their records.

The two UFO benchmarks run as slow tests.

**Amendment (2026-10-04, part 3).** Part 3 fixed three faults in the UFO engine:
- the σ table missed narrow poles;
- W W* and Z Z* final states were missing;
- the Higgs's decays into dark matter were left out of its width.

Rerunning this section's script on the corrected engine gives **14 of 17** of the ranges above. The three
misses are:
- **BM6: 1.080** of the published value. micrOMEGAs 7.1.10 at the same point gives a ratio of 0.993; the
  published value comes from micrOMEGAs 2.4.1.
- **The 2HDM+a at (600, 250, 150) and (1000, 400, 170): 1.12 and 1.15** of MadDM. With four times the
  table's nodes these become 1.11 and 1.14. Part 2's 6–8% was partly an artefact of interpolating σ
  linearly between sparse nodes. The remaining ~10% matches DM8's finding that MadDM's g* counts ghosts,
  which lowers its Ωh²; part 1 allowed 20% against MadDM for that reason.

The ranges above are left as declared. Part 3's validation (`docs/portal_library_3.md`, section 7) compares
the engine with micrOMEGAs on matched inputs.

**Re-declaration against matched references (2026-10-10; the owner's decision; declared before any matched
reference was computed).** The amendment's three misses come from the references, not the engine. So the two
families of reference gates are re-declared against references that use the same inputs and the same
bookkeeping as ADROIT. The whole families are re-declared, not only the three gates that missed: choosing a new
reference only where the old one failed would choose it by the outcome. The tolerances are unchanged, and a
re-declared gate that misses is recorded as a finding; its range is not widened.

1. **The inert doublet, all five benchmarks** (BM5, BM6, HP2, HP8, HP10).
   - Reference: micrOMEGAs 7.1.10's own inert-doublet model at the same point, with the UFO's electroweak inputs
     (α = 1/128.9, M_W = 79.947 GeV, M_Z = 91.1876 GeV) and m_h = 125.09 GeV (`parameter_space.crosscheck`, as
     in part 3).
   - Range: 0.94–1.06, as declared. The published values stay in the table for information only.
2. **The 2HDM+a, all four points.**
   - Reference: MadDM 3.3 on the same UFO, in the same process folders (`<tools>/maddm-work/p2hdm/`), re-run
     with a physical g* species list (`include/model_info.txt`). The list keeps the 17 Standard Model entries
     of MadDM's template, the dark matter at m_χ, H and A at M_A, H± at M_A, and a at M_a.
   - Removed from the list:
     - the ghosts ghA, ghZ, ghW⁺, ghW⁻ and ghG, including 18 massless bosonic degrees of freedom counted at
       every temperature;
     - MadDM's own direct-detection auxiliary fields sdmm and vdmm, at 70 GeV;
     - the default card's masses, which counted the dark matter at 1 GeV.
   - Generated by `scripts/maddm_matched_gstar.py`, with its record in
     `docs/portal_library_2/maddm_matched_reference.json`.
   - Range: 0.9–1.1, as declared. MadDM's original values stay in the table for information only.
   - **Expected effect, stated in advance:** at T_f ≈ m_χ/25 ≈ 6–7 GeV, MadDM's g* is about 86 + 21.5 instead
     of about 86. Since Ωh² ∝ 1/√g*, its Ωh² should rise by about √(107.5/86) ≈ 1.12. That would move the
     four ratios from 1.08–1.15 to about 0.97–1.03.

**Result (2026-10-10, after the declaration above): 17 of 17 pass.**
- The copies reproduce part 2's stored MadDM values exactly. With the physical species list, MadDM's Ωh² rises
  by ×1.125–1.133, close to the stated ≈ 1.12.
- The (600, 250, 300) point, at 0.960, is a little below the expected 0.97–1.03, but inside its declared range.

| gate | ours | range | old reference (ours / it) | result |
|---|---|---|---|---|
| inert doublet BM5: Ωh² / micrOMEGAs 7.1.10 | 0.986 | 0.94–1.06 | published: 1.000 | pass |
| inert doublet BM6: Ωh² / micrOMEGAs 7.1.10 | 0.993 | 0.94–1.06 | published: 1.080 | pass |
| inert doublet HP2: Ωh² / micrOMEGAs 7.1.10 | 0.980 | 0.94–1.06 | published: 0.986 | pass |
| inert doublet HP8: Ωh² / micrOMEGAs 7.1.10 | 0.982 | 0.94–1.06 | published: 0.993 | pass |
| inert doublet HP10: Ωh² / micrOMEGAs 7.1.10 | 0.984 | 0.94–1.06 | published: 0.996 | pass |
| 2HDM+a (600, 250, 150): Ωh² / MadDM, physical g* | 0.992 | 0.9–1.1 | MadDM as run: 1.121 | pass |
| 2HDM+a (600, 250, 300): Ωh² / MadDM, physical g* | 0.960 | 0.9–1.1 | MadDM as run: 1.079 | pass |
| 2HDM+a (1000, 400, 170): Ωh² / MadDM, physical g* | 1.009 | 0.9–1.1 | MadDM as run: 1.149 | pass |
| 2HDM+a (1000, 400, 300): Ωh² / MadDM, physical g* | 0.969 | 0.9–1.1 | MadDM as run: 1.089 | pass |

The eight thermal-mass gates are unchanged and pass. **A finding for MadDM users:** relic densities made with
MadDM 3.3 on a Feynman-gauge UFO, or with default-card masses below the freeze-out temperature, can be about
12% low from this g* bookkeeping. This extends DM8's observation (`docs/dm8_lagrangians.md`, finding 4).

## 6. What is still not built

- **LHC searches beyond the four records.** Missing are:
  - monojet and mono-X;
  - disappearing tracks (the wino and the higgsino);
  - slepton-like partners;
  - b_R partners;
  - the inert doublet's dileptons;
  - a general recast tool (SModelS or CheckMATE as a dependency would cover most).
- **Indirect detection beyond Fermi-LAT's dwarfs and the CMB.** Missing are γ-ray lines
  (H.E.S.S., decisive for the wino), cosmic-ray antiprotons, and the CMB below 5 GeV for
  channels other than electromagnetic ones.
- **Direct detection.** Missing are twist-2 and loop scattering (coloured partners, the
  higgsino, the 2HDM+a), the lepton partner's anapole, and the light-mediator momentum
  dependence.
- **Other records not built:**
  - the CCFR trident and CMS's Z → 4μ (L_μ − L_τ);
  - B − L below LEP-II's energy;
  - visible B → K a decays (lifetime-dependent);
  - B_s → μμ;
  - electroweak precision;
  - BBN and ΔN_eff.
- **Relic density.** Missing are:
  - bound states of the electroweak multiplets (a few per cent);
  - excited states of coloured bound states (about +20% on that rate);
  - thermal masses;
  - three-body final states (the inert doublet's low-mass region);
  - the Sommerfeld effect of the inert doublet's nearly degenerate scalars.
- **Speed.** A wino or higgsino point takes about 40 s and a UFO-model point about 3 s,
  so 2D scans of these take tens of minutes with two workers.

## 7. For the owner

- **Verify the ten new records.** Section 4 lists them; each record states its source, its
  assumptions and the checks made. Until they are verified, the searches show as pending.
- **Decide on DarkCast.** It is GPL-2.0-or-later, used as a fetched dependency and never
  copied, as MadDM is. Confirm that this is acceptable for the release.

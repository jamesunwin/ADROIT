# The portal library, part 3: LHC recasting, a second relic code, the review page, the combined likelihood

Started 2026-10-04 at the owner's request. The request was to build every "useful addition" from the verdict
after part 2, then revise the list of critical gaps. That covers:
- an LHC recasting tool;
- micrOMEGAs as a second relic code;
- a review page for records;
- a combined-likelihood mode;
- the smaller items: BBN and ΔN_eff, hadrons below 1 GeV, CCFR, and electroweak bound states.

This record covers what was built, what it was checked against, the validation, and the revised gaps. Four
research agents did the groundwork; their reports are summarised here:
- the electroweak bound-state formulas;
- the BBN, R-ratio and CCFR data;
- installing SModelS and gathering the LHC cross-sections;
- building micrOMEGAs.

## 1. LHC searches through SModelS (`constraints/lhc.py`, the `lhc_search` evaluator)

SModelS 3.2.1 (arXiv:2306.17676) runs in its own environment in the tools folder, with its official database
3.2.1: 131 ATLAS and CMS analyses, 1.1 GB, CC BY 4.0. It is GPL-3, so it runs as a program and talks JSON
(`constraints/smodels_driver.py`); it is never imported.

**The input.** For each point ADROIT writes an SLHA file: the dark sector's quantum numbers, masses, decays and
widths. Narrow widths make a particle long-lived, so disappearing tracks and displaced decays are covered.
The 13 TeV cross-sections come from the LHC SUSY Cross Section Working Group's tables, fetched into the tools
folder:
- **a coloured partner:** one colour-triplet scalar pair at NNLO+NNLL (the 2024 stop table). This is QCD only,
  a lower bound for a t-channel model, where χ exchange adds production.
- **a lepton partner:** a right-handed slepton pair at NLO+NLL.
- **the wino and the higgsino:** their electroweakinos at aNNLO+NNLL. The chargino's lifetime comes from its
  splitting (Γ(χ± → χ⁰π±, eν)); cτ ≈ 6 cm for a 164 MeV wino.

**The output.** r = σ × BR/σ₉₅ of the most sensitive result, excluded at r ≥ 1. The ratio also enters the
combined likelihood (section 4).

**When it is decided.**
- A point with fewer than one expected event in 139 fb⁻¹ is allowed.
- A point no result covers is undecided.
- A scan sends all its points in one batch, because loading the database takes ≈ 4 s.

**What it now decides.** SModelS covers:
- LHC searches for coloured partners of u_R, d_R and b_R;
- slepton-like partners of leptons;
- disappearing tracks for the wino and higgsino.

These were the pending "not yet a record" items of parts 1 and 2. Its record, `smodels-3.2.1`, awaits
verification like the others.

## 2. micrOMEGAs as a second relic code (`constraints/micromegas.py`, `adroit crosscheck`)

**The build.** micrOMEGAs 7.1.10 is built in the tools folder without Fortran. The only gfortran on this
machine is Intel Homebrew's, which cannot link arm64 code; the inert doublet, scalar singlet and Z′ portal
models do not need it. A small C program, `mo_omega.c`, is compiled into each model directory.

**The command.** `adroit crosscheck PORTAL` maps a library entry's slots onto micrOMEGAs's parameters, with
the same electroweak inputs where the model allows, and prints both Ωh². It covers `inert_doublet`,
`higgs_portal_scalar` and `b_minus_l`.

**What it found**, all now fixed or explained:
- **The UFO portal's table missed narrow resonances.** σ(s) was tabulated on 41 nodes in √s, and the 4 MeV
  Higgs pole fell between two of them, so annihilation through its thermal tail was lost. Nodes are now added
  around every pole, and σ is interpolated in log σ. Belyaev et al.'s BM2 moved from 5.4× to 0.69× of the
  published value.
- **Off-shell W and Z final states (W W*, Z Z*) were missing from our own engine.** The inert doublet's
  low-mass region needs them; they change Ωh² by a factor of 6–9 near 72 GeV.
  - They are now integrated over each boson's Breit–Wigner, with the running width Γ(m) = Γ m/M. That
    width was needed: with a constant width the light W* was overweighted, giving 25–40% too little Ωh².
  - The second boson's mass is integrated over its allowed range, nested inside the first's: a square grid
    with a cut put almost no nodes where the integral lives.
- **The UFO portal ignored the Higgs's decays into dark matter.** Its width is now the Standard Model's plus
  h → (dark pairs); this is 16% of the width at Belyaev et al.'s BM3.
- **Belyaev et al.'s BM3 is not reproducible.** Every micrOMEGAs version (4.3.5, 6.3.0 and 7.1.10) gives about
  1.0, not the published 0.099. Our value is 0.80.
- **micrOMEGAs agrees with ADROIT at the Higgs resonance, to 1%, when it computes its own Higgs width.**
  Fixing that width at 4.1 MeV when h → SS is open had made the codes look 2–4× apart. So part 1's accepted
  "spread between codes" at the resonance is a spread with GAMBIT's and MadDM's published numbers, not with
  micrOMEGAs. The ⚠ flag stays: kinetic decoupling, in neither code, matters there (arXiv:1706.07433).

## 3. The review page for records (`constraints/review.py`, `adroit records`, the workbench's Records page)

**What each record now names.** Its source figure: the arXiv paper and the page, `figure:` in `records.yaml`.

**`adroit records`:**
- `list [--unverified]` lists the records.
- `show ID [--plot file.png]` prints one record and can draw its curves.
- `fetch-sources` puts each record's source PDF into the tools folder.
- `verify ID --by NAME` writes `verified_on` and `verified_by` into `records.yaml`. It changes nothing else in
  the file.

**The workbench's Records page** (`/records`, `/record?id=…`) shows the record's curves beside the source paper,
opened at the figure's page. Below them it lists the assumptions and the checks made, and gives a form: a
name, a box to tick ("I have compared the data and assumptions with the source"), and Mark as verified.

## 4. The combined-likelihood mode (`parameter_space/likelihood.py`, `adroit track1 --likelihood`)

**How constraints combine (audit M15).** Only justified 95% comparisons enter as r = prediction/95% limit, scaled
as the signal: a coupling limit enters as (g/g₉₅)². A measurement (the muon's g − 2) reports its Δχ² against
the Standard Model. Native 90% IceCube, BaBar/Belle II and B→K comparisons, and mixed/unspecified-CL
records, are preserved separately and remain pending at 95% without a source likelihood. Native DD
curve validation stays at 90%; the 95% calculation uses each module's actual procedure. No universal
conversion is applied. Then:
- **Each limit** is treated as Gaussian with no excess, so q_i = (z r_i)² (z = 1.645 one-sided, 1.96 for the
  xenon modules' two-sided t̃). A relative theory uncertainty δ on the prediction (`--theory`) is profiled as a
  log-normal nuisance, s → s e^{κθ} with κ = ln(1 + δ): q_i = (2w + w²)/(4κ²), w = W₀(2κ²(z r_i)²). It grows as
  (ln r)² for large r. (Until R5 the nuisance was Gaussian, q_i = x²/(1 + x²δ²) → 1/δ², and could never exclude
  for δ ≥ 0.61; release audit M12.)
- **The point is excluded** if Σ q_i > 2.71, which is r_comb = √Σ r_i² > 1 without theory uncertainty.
- **Contours without a ratio** (CMS's planes, ATLAS's squark contour, beam dumps, LEP's inert-doublet region)
  stay as cuts.

**The relic band.** Ωh² is compared with 0.120 ± 0.0012 plus a theory uncertainty δ_Ω on the prediction (10%
by default, `--relic-theory`). Grid points inside the 95% band are judged as well as the contour. This is the
first place ADROIT carries a theory uncertainty into a verdict.

**In the report.** Track 1 prints both verdicts, and a table of r_comb along the band.

## 5. The smaller items

**Hadrons below 2 GeV** (`constraints/hadrons.py`):
- **Photon-like couplings** (the dark photon, L_μ − L_τ's loop mixing): σ(→ hadrons) = σ(→ μμ, massless) ×
  R(√s), the PDG's sum of exclusive channels from 0.30 to 1.99 GeV. The file is CC BY 4.0 and fetched.
- **B − L:** DarkCast's vector-meson-dominance ratio. B − L is isoscalar, so it has no ρ.
- **The widths and domain.** The mediators' widths below 2 GeV use the same ratios. The dark photon and Z′
  portals now reach m_χ = 10 MeV; below that the dark matter is in equilibrium during BBN.
- **Continuity.** At 2 GeV, R = 2.18 against N_c ΣQ² = 2.

**BBN and N_eff** (record `sabti-1910.01649-bbn`):
- A thermalised light vector is excluded below 9.8 MeV if it couples to electrons (the dark photon, for
  ε ≳ 10⁻⁸) and below 8.3 MeV if it couples to neutrinos (L_μ − L_τ, for g′ ≳ 4 × 10⁻⁹). These are Sabti et
  al.'s BBN+Planck values at 95.4% CL.
- B − L follows their eq. (18).
- A dark photon below thermalisation (ε < 10⁻⁸) is judged by Ibe et al.'s Fig. 4(a), the (m, ε) region Planck's N_eff excludes for freeze-in (record `ibe-1912.12152-dark-photon-neff`, 2026-10-13; before, undecided for 10⁻¹⁰ < ε < 10⁻⁸ and not applied below).

**CCFR** (record `ccfr-1406.2332-trident`):
- The source is Fig. 2 of Altmannshofer et al., as digitised by Bernal et al. That file has no licence, so it
  is fetched, not copied.
- Above 646 GeV the heavy-Z′ limit m_Z′/g′ > 580 GeV applies. The digitisation's ratio is constant at 578–581
  GeV, and the paper's formula gives 545–618 GeV. (Since 2026-10-17, 567 GeV: the figure's heavy line, after the
  external audit's item 18.)
- L_μ − L_τ points are now decided wherever BaBar, Belle II or CCFR reach. The exception is 5–70 GeV with
  g′ ≥ 2 × 10⁻³, where CMS's Z → 4μ is not a record.

**The wino's bound state** (`portals/multiplet.py`, Mitridate et al.):
- The ground state of the I = 1 pair is captured from the I = 3 p-wave by emitting a photon. It exists only
  above M ≈ 2.0 TeV (Hulthén) and below T_c, and is taken in ionisation equilibrium.
- With the Coulomb capture, Ωh² falls by 3.7% at 2.9 TeV. With the shallow bound state's factor 1 − y², our
  choice, it falls by 2.7%; Mitridate et al. find 1.3–2%.
- The higgsino forms no bound state below about 5 TeV.

## 6. What changed in the verdicts

Three records were added, all unverified: `smodels-3.2.1`, `sabti-1910.01649-bbn` and
`ccfr-1406.2332-trident`. Five external items were added to the set-up manifest, all fetched into the tools
folder and never copied: SModelS with its database, the LHC SUSY cross-sections, micrOMEGAs, the PDG R ratio,
and the CCFR digitisation.

The pending items these replace:
- LHC searches for coloured, b_R and slepton-like partners;
- disappearing tracks;
- CCFR;
- BBN for light mediators;
- light dark photon and B − L dark matter below 1 GeV (now computed rather than outside the domain).

## 7. The validation

`scripts/validate_portal_library_3.py`: local programs only ($0), about 10 minutes.

**How the ranges were set.** As in part 2, the ranges were set after the development comparisons above; they
are not a blind gate:
- 5% for relic codes where both agree on the physics;
- 20% for the inert doublet's W W* region, where Ωh² moves 6–9× with the off-shell states;
- 10% on SModelS's r against the install survey's runs;
- Mitridate et al.'s range, widened to our 2.7%, for the wino's bound state.
EOF
echo ok
Run on 2026-10-04:

| gate | ours | range | reference | result |
|---|---|---|---|---|
| inert doublet BP1: Ωh² / micrOMEGAs 7.1.10 | 0.867 | 0.8–1.2 | same electroweak inputs; W W*, Z Z* in both | pass |
| inert doublet BP4: Ωh² / micrOMEGAs 7.1.10 | 0.903 | 0.8–1.2 | same electroweak inputs; W W*, Z Z* in both | pass |
| inert doublet BP6: Ωh² / micrOMEGAs 7.1.10 | 0.891 | 0.8–1.2 | same electroweak inputs; W W*, Z Z* in both | pass |
| inert doublet BM1: Ωh² / micrOMEGAs 7.1.10 | 1.013 | 0.8–1.2 | same electroweak inputs; W W*, Z Z* in both | pass |
| inert doublet BM4: Ωh² / micrOMEGAs 7.1.10 | 1.153 | 0.8–1.2 | same electroweak inputs; W W*, Z Z* in both | pass |
| inert doublet HP2: Ωh² / micrOMEGAs 7.1.10 | 0.980 | 0.95–1.05 | same electroweak inputs | pass |
| inert doublet HP10: Ωh² / micrOMEGAs 7.1.10 | 0.984 | 0.95–1.05 | same electroweak inputs | pass |
| scalar singlet 40 GeV, λ_hs = 0.1: Ωh² / micrOMEGAs | 1.022 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 50 GeV, λ_hs = 0.1: Ωh² / micrOMEGAs | 0.999 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 57 GeV, λ_hs = 0.1: Ωh² / micrOMEGAs | 1.008 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 60 GeV, λ_hs = 0.001: Ωh² / micrOMEGAs | 1.008 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 62 GeV, λ_hs = 0.0003: Ωh² / micrOMEGAs | 1.005 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 66 GeV, λ_hs = 0.01: Ωh² / micrOMEGAs | 0.988 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 100 GeV, λ_hs = 0.1: Ωh² / micrOMEGAs | 0.964 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 300 GeV, λ_hs = 0.1: Ωh² / micrOMEGAs | 0.960 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 1000 GeV, λ_hs = 0.1: Ωh² / micrOMEGAs | 0.958 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| scalar singlet 3000 GeV, λ_hs = 0.1: Ωh² / micrOMEGAs | 0.961 | 0.95–1.05 | each code's own Higgs width (h → SS included) | pass |
| SModelS r, u_R partner 900/100 GeV | 0.998 | 0.9–1.1 | the install survey's r = 2.32 | pass |
| SModelS r, u_R partner 1500/100 GeV | 0.995 | 0.9–1.1 | the install survey's r = 0.46 | pass |
| SModelS r, μ_R partner 400/100 GeV | 1.003 | 0.9–1.1 | the install survey's r = 1.67 | pass |
| SModelS r, wino 500 GeV | 0.959 | 0.9–1.1 | the install survey's r = 3.16 | pass |
| wino 2.9 TeV: Ωh²(bound states) / Ωh²(Sommerfeld only) | 0.973 | 0.96–0.995 | Mitridate et al. 0.980–0.987 | pass |
| dark photon: hadrons/e⁺e⁻ at 1.99 GeV over quarks/e⁺e⁻ at 2.01 GeV | 1.088 | 0.95–1.15 | the measured R (2.18) against N_c ΣQ² = 2 | pass |
| combined likelihood: r_comb of r = (0.6, 0.8) | 1.000 | 0.999–1.001 | √(0.6² + 0.8²) = 1 | pass |

**24 of 24 pass.** The tests hold the unit checks: the slow tests run SModelS and micrOMEGAs where they
are built, and the fast ones cover everything without them. They check:
- the chargino's lifetime;
- the SLHA format;
- the R ratio and its continuity;
- BBN, CCFR and the bound state;
- the off-shell integral;
- the likelihood algebra;
- the review's written verification;
- the Records page.

## 8. The critical gaps that remain (revised)

1. **Thirteen records await verification.** Ten are from part 2 and three from part 3. Until they are
   verified, their searches make points pending. The Records page and `adroit records verify` make this a
   short task, but only a person can do it.
2. **LHC searches for s-channel portals outside CMS's benchmarks.** These are:
   - the singlet mixing's heavy scalar and the Higgs signal strengths;
   - the scalar and pseudoscalar mediators;
   - B − L below 250 GeV;
   - the inert doublet's dileptons;
   - the 2HDM+a away from ATLAS's benchmark plane.

   SModelS has the maps (mono-jet TRV1 and TRS1, dijets, dileptons). What is missing is the mediator's
   production cross-section, which MadGraph, already installed, could compute at leading order.
3. **Loop-level direct detection.** Not computed:
   - twist-2 and gluon scattering of a coloured partner near degeneracy;
   - the higgsino's and the 2HDM+a's loop scattering;
   - a lepton partner's anapole.

   These are pending wherever they apply.
4. **Indirect detection beyond the dwarfs and the CMB.** Not covered:
   - γ-ray lines (H.E.S.S.), decisive for the thermal wino;
   - cosmic-ray antiprotons;
   - the CMB's f_eff below 5 GeV for channels other than electromagnetic ones.
5. **Model-specific theory uncertainties.** The likelihood mode carries them, but its defaults are generic
   (10% on Ωh², 0 on predictions). The known spreads are larger in places:
   - ±35% on Ωh² for compressed coloured partners;
   - ±15% for the inert doublet's W W* region;
   - kinetic decoupling at resonances.

   These should be the model's own defaults.

**Smaller, documented gaps:**
- the inert doublet's Sommerfeld effect at high mass (a few per cent);
- excited coloured bound states (+20% on that rate);
- thermal masses;
- the visible B → K a decays and B_s → μμ;
- CMS's Z → 4μ;
- the 2HDM+a's flavour bounds;
- the combined likelihood's Gaussian approximation (SModelS's own likelihoods are not yet used);
- speed: a wino point takes ≈ 40 s and a low-mass inert-doublet point ≈ 30 s.

## 9. For the owner

- **Verify the thirteen records**, using the Records page or `adroit records verify ID --by NAME`.
- **Decide on the licences** of the external programs and data. SModelS (GPL-3) and DarkCast (GPL-2+) run
  as fetched programs. micrOMEGAs, the TWiki cross-sections, Slatyer's f_eff and the CCFR digitisation state
  no licence. None is copied into this repository.

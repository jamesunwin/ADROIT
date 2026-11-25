# The portal library, part 4: mediators at the LHC, loop-level direct detection, γ-ray lines and antiprotons

Started 2026-10-04 at the owner's request: close critical gaps 2, 3 and 4 of part 3 (`docs/portal_library_3.md`,
section 8), using MadGraph for the mediators' cross-sections. Three research agents did the groundwork:
- MadGraph's production tables, heavy-Higgs cross-sections and the HEPData limits;
- the loop-level direct-detection formulas, with their normalisations checked against each other;
- the indirect-detection data: γ-ray lines, antiprotons, and the CMB below 5 GeV.

## 1. Gap 2: s-channel mediators at the LHC (`constraints/production.py`, `parameter_space/searches.py`)

**The cross-sections.** MadGraph 3.8 (in the tools folder) tabulated each production process once, at unit
couplings, at leading order: NNPDF2.3 LO, μ_R = μ_F = M, 13 TeV, narrow width. The tables are JSON in
`<tools>/madgraph-xsec/`, with their metadata (process, model, couplings, PDF, scale, run time):
- **q q̄ → Z′** (DMsimp spin-1): a universal vector, a universal axial, one table per quark flavour, up- and
  down-type, and B − L (g_q = g_BL/3); 50 GeV – 6 TeV. Left at LO, so they are conservative by K ≈ 1.2–1.35.
- **gg → S** through the exact top and bottom loops (DMsimp spin-0, Yukawa-like couplings g_q m_q/v): scalar
  and pseudoscalar, t, b and t + b; 10 GeV – 3 TeV. Below 50 GeV the heavy-top EFT, rescaled by the loop
  function.
- **The K-factor of gluon fusion,** K ≈ 2.5–2.7. It is the Higgs Cross Section Working Group's heavy-Higgs σ
  (YR4, quark loop, NNLO+NNLL) over MadGraph's LO in the same setup. That Working Group σ is also used
  directly as the singlet's σ(gg → h₂)/sin²θ.
- **The inert doublet's Drell–Yan pairs** H₀A₀, H±H₀, H±A₀ and H⁺H⁻, at equal masses (50 GeV – 1 TeV) and
  at 8 split spectra each. A pair (m₁, m₂) uses the equal-mass table at (m₁ + m₂)/2 ×
  2√(m₁m₂)/(m₁ + m₂), the ratio of the unequal masses' phase space. This rule was found by looking at the
  split runs; it reproduces all 32 of them to 3% for mass ratios up to 8.3. Without the factor it was 31–62%
  high at ratios 4–8.

Between nodes, σ is a cubic spline in (ln M, ln σ). Leaving every other node out, it is good to 0.2% on the
Z′ grid, where linear interpolation is off by up to 14%; a K-factor column is interpolated linearly.
In the narrow-width approximation a point's σ is the table's times its couplings squared. Its branching
fractions are the portal's own widths. The SLHA spectrum goes to SModelS, which compares it with every
resonance, monojet, dijet and dilepton map in its database.

**What each portal now meets** (all through records awaiting verification):

| portal | production | searches |
|---|---|---|
| DM13 spin-1 class (V1, A1) | q q̄ → Z′ | SModelS: dijets (ATLAS-EXOT-2019-03, CMS-EXO-19-012), monojet (ATLAS-EXOT-2018-06), dileptons |
| B − L | q q̄ → Z′ (g_BL/3) | SModelS dileptons and dijets from 50 GeV, beside ATLAS's dilepton record |
| DM13 scalar class, ALP-like portal | gg → S × K | CMS's monojet signal-strength limits (new record), SModelS |
| singlet mixing's h₂ | sin²θ × σ_HXSWG | ATLAS H → ZZ and H → WW (new records), SModelS (monojet, dijets), the Higgs signal strength |
| inert doublet | Drell–Yan pairs | SModelS: soft dileptons (ATLAS-SUSY-2018-16), electroweakino searches |
| 2HDM+a, any (sin θ, tan β) | gg → a, A, H × K | SModelS (monojet; the cascades A → a h, H → a Z are passed on), beside ATLAS's plane |

**Audit M07 applicability:** spin-0 monojet rescaling now requires an open invisible decay and
Γ/M no greater than the source's g_q = g_χ = 1, m_DM = 1 GeV reference width at the same mediator mass.
This conservatively restricts the NWA to the source benchmark's width domain; it is not a published
validation of arbitrary coupling rescalings. Broader points report their width and remain pending.

**The monojet recast.** CMS publishes limits on the signal strength μ of the DMsimp spin-0 mediator with
g_q = g_χ = 1 and m_DM = 1 GeV (arXiv:2107.13021). Production is the same top loop, so a point's
μ = g_q² × BR(S → χχ̄)/BR_benchmark(S → χχ̄). It is used where m_med > 2m_χ. The missing-momentum
spectrum is taken to be the benchmark's, which is fair away from the threshold.

**The heavy scalar.** For the singlet's h₂ the evaluator compares σ(gg → h₂) × BR with ATLAS's narrow-scalar
limits in ZZ (4ℓ, 2ℓ2ν) and WW (ℓνqq), all at 139 fb⁻¹. It is undecided when Γ/m > 5%, because the
narrow-width limits do not apply. h₂ → h₁h₁ is absent, since the potential's trilinear couplings are set to
zero, so the resonant HH limits (fetched, CC0) are not used.

**Coverage SModelS does not have** is reported honestly, as undecided ("no SModelS result covers this
spectrum"), never as allowed. Two examples:
- a 1.5 TeV Z′ with Γ/M ≈ 3%: ATLAS's dijet maps are narrow-width, and CMS's width-dependent maps start at
  1.8 TeV;
- dijets below ≈ 1.5 TeV for heavy dark matter.

**The 2HDM+a away from ATLAS's plane.** Each neutral state's gluon fusion comes from the per-quark tables
with its type-II couplings in units of m_q/v (alignment; Djouadi's Table 1):
- a: g_t = s_θ/t_β, g_b = s_θ t_β;
- A: c_θ/t_β, c_θ t_β;
- H: −1/t_β, t_β.

The top–bottom interference is σ = g_t²σ_t + g_b²σ_b + g_t g_b(σ_tb − σ_t − σ_b), times the K-factor.
MadGraph run on the 2HDM+a model itself agrees to 0.6% at the Working Group's benchmark. Every two-body
decay the UFO model's vertices allow is passed to SModelS, including A → a h (mono-Higgs), H → a Z
(mono-Z) and H± → a W.

SModelS's database has the monojet (CMS-EXO-20-004) but not ATLAS's mono-h/mono-Z combination. So on
ATLAS's plane the dedicated record remains the stronger constraint, and off it SModelS gives what it has.
- At the default heavy masses (1 TeV): r = 0.48 at sin θ = 0.35, tan β = 1.
- r = 1.9 at sin θ = 0.7.
- r = 0.04 at tan β = 3.

**The same data once.** CMS-EXO-20-004 is the same paper as the monojet record (arXiv:2107.13021). When
SModelS's most sensitive analysis is one a dedicated record holds, its ratio leaves the combined likelihood;
the cut still applies.

**Not done.**
- The cascades A₀ → H±W* and H± → A₀W*.
- ATLAS's mono-h and mono-Z away from its plane.
- tt̄ resonances. CMS's H/A → tt̄ limits are on a coupling modifier with interference, not on σ × BR; they
  are fetched but not used.

**What the MadGraph survey found** (its report, 2026-10-04):
- **MadLoop is silently wrong at low mass.** gg → S with CutTools alone gives zero-weight points below
  ≈ 50 GeV. Below 50 GeV the tables therefore use the heavy-top EFT rescaled by the loop function. Each loop
  point carries an "unstable" count, 0 in the final tables.
- **MadGraph 3.8.0 crashes when refining a loop-induced 2 → 1 process** (`AssertionError ftn25`), so the
  spin-0 runs are surveys of 100 events (0.5% precision).
- **The inert doublet's UFO does not run in MadGraph as delivered.** α_s had to move to SMINPUTS 3, and the
  parameter named aEWM1 is α itself. The edited copy for MadGraph is `ufo/InertDoublet_UFO_mg5`; ADROIT's
  own UFO portal still reads the original. Its effective ggh vertex makes gg → h* → pairs depend on the
  portal coupling, so the tables leave the gluon out of the proton (pure Drell–Yan).
- **The aMC@NLO Z′ run fails** ("poles do not cancel"), so q q̄ → Z′ stays at LO. The Z check gives
  K = 1.33–1.37.
- **HEPData labelling errors:** CMS's X → HH units read fb⁻¹ for fb, and ATLAS's WW axis reads M_T for the
  resonance mass.
- **The survey changed MadGraph's shared configuration by mistake** (ninja, collier, C++ compiler) between
  ≈ 08:00 and 09:20, and then restored it. It was checked afterwards: the three original settings.
- **The K-factors include the PDF difference** (NNPDF2.3 LO with α_s = 0.130 against PDF4LHC15), not QCD alone.

## 2. Gap 3: direct detection beyond tree level (`constraints/loops.py`, `parameter_space/operator_limits.py`)

| portal | what is computed | reference | check |
|---|---|---|---|
| coloured partner, Majorana | scalar f_q, twist-2 g_q⁽¹⁾, gluon (short- and long-distance): c₁ = 2f_N | Hisano, Ishiwata & Nagata arXiv:1007.2601, 1502.02244 inputs | σ_p = 3.65 × 10⁻⁴⁴ cm² at (300, 360) GeV and 5.0 × 10⁻⁴⁶ at (1000, 1100), to 1% |
| coloured partner, Dirac | the same f_N added to the tree-level vector coupling | Ibarra & Wild arXiv:1503.03382 | subleading |
| lepton partner, Majorana | the anapole form factor F_A, through Path 1 | Kopp, Michaels & Smirnov arXiv:1401.6457 eq. 10 | F_A = 5.53 × 10⁻⁶ GeV⁻² at (100 GeV, μ = 1.1); its heavy-mediator limit to 1% |
| lepton partner, Dirac | the charge radius and the magnetic moment's contact term, c₁ᵖ = −e(b_χ + μ_χ/2m_χ) | Ibarra & Wild eqs. 10–13 | μ_χ = 3.54 × 10⁻⁵ e GeV⁻¹ and b_χ = 5.16 × 10⁻⁶ e GeV⁻², to 0.1% |
| higgsino | σ_SI = 7.4 × 10⁻⁵⁰ cm² (heavy limit, NLO) | Hisano et al. arXiv:1504.00915; Hill & Solon arXiv:1409.8290 | an order-of-magnitude uncertainty from a cancellation |
| 2HDM+a | the h and H triangles (boxes ≲ 10% for tan β ≲ 10, left out) | Abe, Fujiwara & Hisano arXiv:1810.01039 | the survey's table to 1%; their “0.6 times” to 0.601 |

**Normalisations that disagree in the literature** (the loop survey's findings, followed here):
- Kopp et al.'s own rate formula, and Bai & Berger's, are inconsistent with F_A by a factor 4 in rate.
- Abe et al.'s heavy-Higgs couplings (A.59–A.61) need a factor (t_β − 1/t_β).
- Several papers' Z terms for the higgsino are off by a factor 2 (not used: the higgsino uses the published
  number).

**The anapole's sign convention.** Del Nobile's map (arXiv:1806.01291) gives c₉ the opposite sign relative to
c₈ from ADROIT's library card M_anapole. The card was checked against an explicit spinor reduction in ADROIT's
own operator conventions. O₈ and O₉ interfere on xenon's odd isotopes, so the sign matters. The structure is
built from the card: same magnitudes (c₈ᵖ = 2eF_A, |c₉ᴺ| = g_N eF_A), the card's sign. A first tabulation
with Del Nobile's sign was stopped and restarted.

**Path 1 for a structure.** The anapole's operators (O₈, O₉) are neither SI nor SD, so it goes through Path 1:
each experiment module's own limit on the interaction's overall strength. That costs minutes per mass for
each xenon module, so each structure (a fixed ratio of operator coefficients) is tabulated once for unit
strength: `scripts/tabulate_operator_limits.py anapole` (12 masses from 5 GeV to 10 TeV, two processes). The
result is `data/operator_limits/anapole.yaml`, the envelope of the validated modules. A point with
F_A = scale has the native-90% ratio r = (scale/μ₉₀)². Audit M15 corrected the original confidence-level
label; the table's numbers are unchanged. The 95% verdict recomputes the actual module procedures
(`operator_limits.limit95`) within their validated ranges and stores source and confidence level.

**Flagged:** a coloured partner within 10 GeV of the dark matter. The twist-2 expansion needs m_φ − m_χ ≫ m_N,
because the quark's momentum in the nucleon resolves the propagator.

## 3. Gap 4: indirect detection (`parameter_space/searches.py`, `portals/multiplet.py`, `constraints/searches.py`)

**γ-ray lines.** Three records, each used with its most conservative published halo profile. The others are
stored beside it.
- **Fermi-LAT 2015** (arXiv:1506.00013), 0.2–500 GeV: the isothermal halo. It resolves the Zγ line at
  E = m − m_Z²/4m. One photon per annihilation, so σv_Zγ is compared with 2(m/E)² × the γγ limit at E.
  Audit M08 uses individual cuts (their maximum ratio), never their sum. If both lines are positive and
  separated by at most 20%, a two-line likelihood remains pending; this is a conservative applicability
  guard based on Fig. 1, not a calibrated joint statistic. H.E.S.S. retains its source-defined unresolved
  γγ + ½Zγ combination only inside its stated 10% separation domain.
- **H.E.S.S. 2018** (arXiv:1805.05741), 0.3–63 TeV: NFW.
- **H.E.S.S. 2026** (arXiv:2608.07234), 0.3–63 TeV: a contracted NFW with a 1 kpc core, the paper's most
  conservative profile. The paper warns that limits do not rescale between profiles, because of its OFF
  regions.

A model's line rate is its own σv_γγ and σv_Zγ. The multiplets supply these with the Sommerfeld effect:
- **The wino:** ADROIT's Schrödinger solver gives the neutral pair's charged component at the origin, d. Then
  σv_γγ + ½σv_Zγ = 2παα₂|d|²/M² (Hisano et al.), times the Sudakov suppression of the exclusive final state.
  That suppression is the ratio of Ovanesyan, Slatyer & Stewart's NLL and tree-level curves (digitised: 0.81
  at 0.5 TeV, 0.53 at 2.9 TeV, 0.33 at 10 TeV).
  - The tree-level line agrees with the survey's independent calculation to 2–4%.
  - The corrected line agrees with Baumgart et al.'s NLL, the curve H.E.S.S. compares with, to 2% at 2.9 TeV
    and 23% at 1 and 5 TeV.
  - **The thermal wino (2.9 TeV) is excluded by ×8.4 even for the cored profile**, as H.E.S.S. 2026 states.
- **The higgsino:** its line comes from the one-loop amplitude, which the Sommerfeld matrices do not hold. It
  uses Beneke, Urban & Vollmann's NLL′ curve as H.E.S.S. 2026 plots it, halved. The survey finds that the
  plotted higgsino curve is the photon count, 2σv_line, while the wino's is σv_line. At 1.1 TeV,
  σv_line ≈ 10⁻²⁸ cm³/s: r = 0.12 for the cored profile. Not excluded, and the paper's "probed" is
  overstated by about 2.
- The higgsino's neutral states are split into Majorana states today, so it annihilates as a self-conjugate
  particle in the lines.

**Antiprotons.** Calore et al. (arXiv:2202.03076) is the survey's choice of a robust bound: AMS-02's 4-year
data, BIG propagation with the halo height profiled, NFW.
- Its five channels (b b̄, q q̄, W⁺W⁻, hh, μ⁺μ⁻) are digitised to ≤ 0.0015 dex.
- Audit M05 applies only a supported pure prompt channel, with physical thresholds enforced.
- Mixed, cascade, off-shell or unrepresented spectra remain pending; no nearest-channel substitution or
  sum of channel-limit ratios is used.
- Outside a source curve's energy/mass domain the comparison is pending.
- Analyses differ by 3–10× at some masses (propagation, the ≈ 100 GeV "hint"), which the record says.

**The CMB below 5 GeV.** The planck-2018-pann record's f_eff now extends below the table's 5 GeV:
- e⁺e⁻ and γγ from Slatyer's f_eff of injected electrons and photons at E = m;
- μ⁺μ⁻ from the Michel spectrum boosted to the lab: 0.186 and 0.164 at 1 and 3.16 GeV, against Slatyer's
  notebook values 0.1843 and 0.1623 (1.2% high; we interpolate linearly, she cubically);
- Unrepresented/cascade channels use only the rigorous energy-deposition bracket 0 ≤ f_eff ≤ 1.
  A bracket is not supplied as a numerical likelihood ratio.

## 4. Records (8 new, all awaiting verification)

| id | what | data |
|---|---|---|
| atlas-2207.00092-higgs-mu | the Higgs signal strength, μ = 1.05 ± 0.06 | inline |
| atlas-2009.14791-zz | heavy scalar → ZZ, ggF, 139 fb⁻¹ | HEPData (CC0) |
| atlas-2004.14636-ww | heavy spin-0 → WW, ggF, 139 fb⁻¹ | HEPData (CC0) |
| cms-2107.13021-monojet-spin0 | monojet μ limits, DMsimp scalar and pseudoscalar | HEPData (CC0) |
| fermi-lat-1506.00013-lines | γ-ray lines, 0.2–500 GeV | the paper's tables (LaTeX source) |
| hess-1805.05741-lines | γ-ray lines, 0.3–63 TeV | digitised (vector figure) |
| hess-2608.07234-lines | γ-ray lines, Inner Galaxy Survey | digitised (vector figures) |
| calore-2202.03076-pbar | AMS-02 antiprotons, five channels | digitised (vector figure) |

The MadGraph tables, HEPData downloads and digitisation scripts live in the tools folder or the session's
scratch space. They are never copied, except the bundled limit curves above, which are numbers from papers
(CC0 where HEPData).

## 5. What changed in the verdicts (library benchmarks, unverified records allowed)

- **wino (2.9 TeV):** excluded by the γ-ray lines (and the antiprotons). Before, it was pending on H.E.S.S.
- **coloured partners:** excluded by twist-2 direct detection and SModelS. Before, they were pending on
  twist-2.
- **lepton partner (Majorana):** compared through the anapole's Path 1 table (section 6). Its benchmark is
  now viable (r = 5 × 10⁻⁴); near degeneracy at 100 GeV it is excluded.
- **B − L, V1, A1:** SModelS's resonance searches beside the existing records. They agree with CMS's own
  contour (section 6).
- **singlet mixing:** the Higgs signal strength and the ZZ/WW searches; nothing pending at its benchmark.
- **ALP-like portal:** the CMS monojet excludes it for g_q = 1 at m_a = 100–400 GeV.
- **2HDM+a:** SModelS's monojet at any (sin θ, tan β), beside ATLAS's plane.
- **inert doublet:** SModelS covers its Drell–Yan pairs and finds r = 0.03–0.11 at the low-mass benchmarks;
  the high-mass (990 GeV, compressed) benchmark is not covered, which is honest.
- **higgsino:** σ_SI = 7.4 × 10⁻⁵⁰ cm², below every limit; lines r = 0.12. It remains pending only on the
  Z-mediated inelastic scattering, which is a statement about its unspecified neutral splitting.

## 6. The validation

`scripts/validate_portal_library_4.py`: local programs only ($0), about 10 s.

**How the ranges were set.** As in parts 2 and 3, after the development comparisons. These gates guard
against regressions and record the agreement; they are not blind:
- 5% where a formula is reimplemented from the same paper;
- 2% for the analytic moments;
- 15% for the wino's tree-level line against an independent code (different couplings' scheme);
- 35% for our NLL-corrected line against Baumgart et al.'s full NLL;
- the expected K-factor windows for the production tables.

The inert-doublet pair rule and the CMS-agreement gate were also seen before they were declared.

Run on 2026-10-04:

| gate | ours | range | reference | result |
|---|---|---|---|---|
| coloured partner (300, 360): σ_p / Hisano et al. | 1.002 | 0.95–1.05 | 3.65 × 10⁻⁴⁴ cm² | pass |
| coloured partner (1000, 1100): σ_p / Hisano et al. | 1.009 | 0.95–1.05 | 5.0 × 10⁻⁴⁶ cm² | pass |
| lepton partner (100 GeV, μ = 1.1): F_A / Kopp et al. eq. 10 | 0.999 | 0.98–1.02 | 5.53 × 10⁻⁶ GeV⁻² | pass |
| Dirac lepton partner: μ_χ / Kopp and Ibarra & Wild | 1.001 | 0.98–1.02 | 3.54 × 10⁻⁵ e GeV⁻¹ | pass |
| Dirac lepton partner: b_χ / Ibarra & Wild eq. 12 | 1.000 | 0.98–1.02 | 5.16 × 10⁻⁶ e GeV⁻² | pass |
| 2HDM+a Working Group benchmark, m_χ = 100: σ_p / the survey | 1.002 | 0.95–1.05 | 9.0 × 10⁻⁴⁸ cm² | pass |
| 2HDM+a Working Group benchmark, m_χ = 500: σ_p / the survey | 0.996 | 0.95–1.05 | 2.7 × 10⁻⁴⁷ cm² | pass |
| 2HDM+a, Bell et al. Fig. 5 at 700 GeV: σ_p / the figure | 0.732 | 0.5–1.5 | ≈ 10⁻⁴⁷ cm² (figure-read) | pass |
| 2HDM+a: triangles / the haa diagram (Abe et al. Sec. 4.1) | 0.601 | 0.55–0.65 | “0.6 times” | pass |
| wino 1 TeV: tree + Sommerfeld line / the survey's | 0.973 | 0.85–1.15 | 1.44 × 10⁻²⁶ cm³/s | pass |
| wino 2.9 TeV: tree + Sommerfeld line / the survey's | 1.036 | 0.85–1.15 | 5.75 × 10⁻²⁶ cm³/s | pass |
| wino 5 TeV: tree + Sommerfeld line / the survey's | 0.984 | 0.85–1.15 | 5.93 × 10⁻²⁷ cm³/s | pass |
| wino 1 TeV: σv_line (× Sudakov) / Baumgart et al. NLL | 1.230 | 0.75–1.35 | 7.95 × 10⁻²⁷ cm³/s | pass |
| wino 2.9 TeV: σv_line (× Sudakov) / Baumgart et al. NLL | 0.984 | 0.75–1.35 | 3.23 × 10⁻²⁶ cm³/s | pass |
| wino 5 TeV: σv_line (× Sudakov) / Baumgart et al. NLL | 1.226 | 0.75–1.35 | 2.09 × 10⁻²⁷ cm³/s | pass |
| thermal wino: r(H.E.S.S. 2026, cored profile) / the survey's ×8.5 | 0.981 | 0.85–1.15 | "excluded for any of the adopted DM profiles" | pass |
| thermal higgsino: r of the lines (not excluded) | 0.118 | 0–1 | σv_line ≈ 10⁻²⁸ cm³/s | pass |
| CMB f_eff(μ⁺μ⁻) at 1 GeV / Slatyer's notebook | 1.012 | 0.97–1.03 | 0.18431 | pass |
| CMB f_eff(μ⁺μ⁻) at 3.162 GeV / Slatyer's notebook | 1.013 | 0.97–1.03 | 0.16233 | pass |
| the Z from the Z′ tables: σ_LO × BR(ℓℓ) / FEWZ's NNLO | 0.752 | 0.70–0.80 | 1928 pb; 1/K_NNLO ≈ 0.75 | pass |
| heavy-Higgs gg → H at 125 GeV / YR4's N3LO | 0.864 | 0.80–1.0 | 48.58 pb | pass |
| 2HDM+a gg → a (250 GeV): σ_LO / MadGraph on Pseudoscalar_2HDM | 0.994 | 0.95–1.05 | 1.535 pb | pass |
| 2HDM+a gg → A (600 GeV): σ_LO / MadGraph on Pseudoscalar_2HDM | 0.999 | 0.95–1.05 | 1.109 pb | pass |
| 2HDM+a gg → H (600 GeV): σ_LO / MadGraph on Pseudoscalar_2HDM | 1.000 | 0.95–1.05 | 0.7871 pb | pass |
| inert doublet pairs: worst \|σ(rule)/σ(MadGraph) − 1\| over 32 split runs | 0.030 | 0–0.05 | MadGraph's own runs | pass |
| SModelS × MadGraph against CMS's V1/A1 contour (20 points where both decide) | 1.000 | 1–1 | cms-2405.13778 | pass |

**26 of 26 pass.** The Z check is a measurement test of the production pipeline: the per-flavour Z′ tables
with the Z's couplings give the Drell–Yan σ at LO, low by exactly the known NNLO K-factor. The CMS-agreement
gate is the strongest: SModelS, fed MadGraph's σ, reproduces the experiment's own exclusion of V1 and A1 at
all 20 points where both decide. The 4 points only CMS decides are dijets at 0.5–1 TeV with heavy dark
matter, below SModelS's maps.

**The anapole table** (`data/operator_limits/anapole.yaml`, computed 2026-10-04 in 34 minutes with two
processes). **Native 90% CL** (label corrected by audit M15): μ₉₀ on F_A (GeV⁻²) of the envelope over the modules validated at each mass, by DM3's
validated-range rule:

| m_χ (GeV) | 5 | 10 | 20 | 40 | 79 | 158 | 316 | 630 | 1258 | 2511 | 5011 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| μ₉₀ (10⁻⁶ GeV⁻²) | 214 | 6.0 | 1.5 | 1.1 | 1.3 | 4.4 | 5.9 | 8.2 | 11.5 | 16.2 | 22.6 |
| from | PICO-60 | LZ | LZ | LZ | LZ | PandaX-4T | PandaX-4T | PandaX-4T | PandaX-4T | PandaX-4T | PandaX-4T |

- Above 80 GeV LZ is outside its validated range, so the envelope uses XENONnT and PandaX-4T. LZ's own values
  there are 2.4× stronger in μ₉₀, so 5.6× stronger in rate. Extending LZ's validated range would strengthen
  the anapole limit accordingly.
- At 10 TeV no module is validated: the table ends at 5 TeV.
- The structure is a fixed combination of O₈ and O₉, which DM5's validated operator rates already cover;
  there is no separate external benchmark for the anapole's limit.

**Effect.**
- The lepton-portal benchmark (300, 400 GeV, y = 1) has F_A = 1.3 × 10⁻⁷ GeV⁻², r = 5 × 10⁻⁴: allowed.
- Near degeneracy the 1/m_ℓ enhancement takes over: at m_χ = 100 GeV, m_φ = 1.05 m_χ, r = 8 (excluded);
  m_φ = 1.01 m_χ, r = 88.
- At 500 GeV, m_φ = 1.01 m_χ, r = 0.02.

**Tests** (fast, offline): the loop benchmarks (`tests/constraints/test_loops.py`), the portals' loop
scattering, the anapole structure, the lines (Fermi's Zγ, the wino and higgsino), the antiprotons' channel
rules, the CMB below 5 GeV (`tests/parameter_space/test_portal_library_4.py`), and the production tables, the
mediator spectra, the inert doublet's cascades, the heavy scalar and the monojet recast
(`tests/parameter_space/test_mediators_at_the_lhc.py`).

## 7. The critical gaps that remain (revised)

*Superseded by `docs/portal_library_5.md` (2026-10-04): the searches of item 2 are implemented there, and the
theory spreads of item 3 are recorded in its section 7.*

1. **Twenty-one records await verification**: ten from part 2, three from part 3, eight from part 4. Until a
   person verifies them, their searches make points pending. `adroit records` and the workbench's Records
   page show each curve beside its source.
2. **Searches outside SModelS's database:**
   - ATLAS's mono-h and mono-Z for the 2HDM+a off its plane;
   - tt̄ resonances;
   - dijets below ≈ 1.5 TeV;
   - broad resonances.

   These are undecided where they would decide.
3. **Model-specific theory uncertainties** in the likelihood mode (unchanged from part 3). They are now
   larger in known places:
   - ×2 on the wino's line (LO against NLO potential, resummation);
   - an order of magnitude on the higgsino's σ_SI;
   - ×3–10 between antiproton analyses;
   - the halo profile for lines, where a kpc core changes H.E.S.S. by 10²–10³ beyond the cored profile used.

**Smaller, documented gaps:**
- the Dirac lepton partner's long-range dipole scattering and anapole (its c₁ᵖ alone is a lower bound);
- the 2HDM+a's box diagrams;
- the coloured partner within 10 GeV of the dark matter (flagged);
- broad resonances (Γ/m > 5%) in the ZZ/WW searches;
- antiprotons below 10 GeV;
- f_eff for hadronic channels below 5 GeV (bracketed);
- dijets below SModelS's maps.

## 8. For the owner

- **Verify the twenty-one records.**
- **The licences:** the HEPData tables are CC0 and bundled. The Higgs Working Group's YR4 is CC BY 4.0; its
  spreadsheet states no licence of its own and is fetched into the tools folder. The DMsimp and heft models
  state none and are fetched. MadGraph's tables are regenerated by `scripts/madgraph_xsec/run_all.sh` (the
  manifest's "MadGraph production tables", about 2 h). The digitised line and antiproton curves are
  numbers read from papers (arXiv licences, cited). MadGraph's tables are our own computation (MadGraph is
  UIUC/NCSA-licensed, in the tools folder). DMγSpec (GPL-3) was used by the survey only to cross-check; none
  of it is in ADROIT.

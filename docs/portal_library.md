# The portal library: benchmark models of thermal dark matter

Started 2026-10-03 at the owner's request, after DM15:
- build the three model types the model builder proposed in DM15's gate (a
  singlet scalar mixing with the Higgs, a dark photon, Majorana dark matter
  with a coloured t-channel partner);
- scan the literature for similarly general portals, and build a library of
  10–20 with compelling benchmarks.

This record covers the literature survey, what was built, the validation
(declared in section 6 before its first run), and its result.

## 1. The literature survey

A literature agent opened every paper's arXiv page and checked its title and
first author. It quoted numbers only from text it read, and marked anything it
could not confirm. Its findings are kept in the entries of
`parameter_space/library.py`: references, benchmarks, and the literature's
statement of each result.

Two cautions came out of it:
- **Coupling conventions differ by factors of 2 or 4 between papers.**
  - The Higgs portal is written ½λ_hs S²|H|² by GAMBIT and a₂S²H†H by Yu et
    al., so a₂ = λ_hs/2.
  - Majorana couplings carry a ½.
  - The inelastic splitting Δ is absolute in one paper and fractional in
    another.

  Each entry states the convention it uses. Couplings are kept at the level
  of the Feynman rule, so a Majorana Lagrangian written with ½ has the same
  rule as a Dirac one.
- **Benchmarks older than LZ are starting points, not claims of viability.**
  The invisible-Higgs limits many papers used (19%, 24%) are also out of
  date: ATLAS now gives BR < 0.107 (arXiv:2301.10731).

## 2. The engine built for the portals

- **The off-shell Higgs width** Γ_h(m) by channel (`constraints/higgs.py`):
  - running quark masses;
  - W and Z pairs through a double Breit–Wigner (smooth through threshold);
  - gluons through the quark loops;
  - each channel anchored to the LHC Higgs Cross Section Working Group's
    value at 125.09 GeV (YR4: Γ = 4.100 MeV and its branching ratios);
  - tabulated from 2 GeV; below it the lepton pairs at tree level and γγ
    (`higgs.light_channel_width`), the quark and gluon pairs closed below
    2m_π and not computed above (2026-10-23; `docs/hadronic_window.md`).

  Annihilation through an off-shell Higgs boson is then
  σ ∝ √s Γ_h(√s)/|D|², every final state at once (Cline et al.).
- **Coannihilation** in the relic solver (`constraints/relic.py`):
  - the Edsjö–Gondolo average over species of any spin and degrees of
    freedom;
  - checked to reproduce DM7's single-species results to 5×10⁻⁵.
- **s-channel exchange of several interfering mediators**
  (`constraints/exchange.py`): spin 1 and spin 0, fermion, scalar or vector
  dark matter, and unequal masses (inelastic dark matter). Checked against
  explicit amplitudes to 10⁻¹⁵.
- **Explicit amplitudes** (`constraints/processes.py`):
  - fermion → two scalars;
  - scalar and vector dark matter → hh;
  - t-channel exchange (Dirac, and Majorana with consistent spin labels,
    v = iγ²u*);
  - χχ̄ → Z* → Zh;
  - the coannihilations of a coloured or charged partner: φφ* → VV,
    φφ* → f f̄, φφ → ff, χφ → fV, with exact colour sums.

  The gauge amplitudes satisfy the Ward identity, which also fixed the
  three-gluon term.
- **Kinetic mixing with hypercharge, diagonalised exactly**
  (`constraints/kinetic_mixing.py`):
  - the photon couples to eQ alone;
  - the dark photon couples as εeQ at low mass and like hypercharge when
    heavy;
  - the Z and the dark photon mix strongly near the Z pole.
- **Two records for the invisible widths** (`records.yaml`; verified by the
  owner on 2026-10-03):
  - ATLAS BR(h → inv) < 0.107;
  - LEP ΔΓ_inv(Z) < 2.0 MeV.
- **Two fixes found along the way:**
  - DM12's generator compared charges exactly, so a hypercharge written
    0.6666667 dropped the Yukawa coupling of a coloured partner. Charges are
    now read as the nearest fraction of denominator ≤ 36.
  - DM8's gauge check used a tolerance of 10⁻⁹ on charge sums; it is now
    10⁻⁶.

## 3. The models (`parameter_space/portals/`, `parameter_space/library.py`, `adroit portals`)

Eighteen portal entries, plus DM13's three classes listed beside them:

| family | entries |
|---|---|
| Higgs portal | real scalar singlet; Dirac fermion (ξ = 0 and ξ = π/2); Majorana fermion; vector; singlet fermion with a scalar mixing with the Higgs |
| vector portal | dark photon (Dirac; complex scalar); inelastic dark photon; Z portal (Dirac vector, Dirac axial, Majorana); gauged B − L; gauged L_μ − L_τ |
| pseudoscalar portal | Coy / ALP-like pseudoscalar with Yukawa-like couplings (DM13's scalar class, now with χχ̄ → aa) |
| t-channel | Majorana and Dirac dark matter with a coloured partner of u_R (S3M_uR, S3D_uR); Majorana with a partner of μ_R (lepton portal) |

Each entry holds:
- its benchmark point;
- the plane the literature plots (with m_A′ = 3m_χ for the dark photons and
  L_μ − L_τ);
- the Lagrangian and parameters;
- its references;
- the literature's statement of the result;
- what is not computed.

Each entry also holds a typed model. That model is DM12's own general
Lagrangian of the fields where the model is renormalizable above electroweak
breaking; otherwise it is written below breaking. All 21 pass DM12's audit.

`adroit track1 --portal ID` runs any entry. The DM13 scalar mediator now
includes χχ̄ → SS (t- and u-channel), which lifts its m_χ < (2/3) m_S
restriction.

**Read from a model.** `classify` maps the actual typed interactions and
coefficients for a real scalar Higgs portal, an explicit pure dark current
with kinetic mixing, or a single-flavour right-handed partner. Extra
interactions, generation multiplets and an unspecified scalar mass-basis
transformation remain unsupported. Field content alone does not supply a
physical coupling, flavour or mixing angle.

A supported single declared symbolic coefficient can take its documented
benchmark, with the coefficient convention and default stated in the notes.
Numerical coefficients are preserved. Library-selected benchmarks remain
available through `for_portal`, including scalar mixing.
DM8's scalar Higgs-portal model (G4) is now computed rather than
undetermined.

**Flags and pending items.** (Part 2, [`portal_library_2.md`](portal_library_2.md),
adds the Sommerfeld effect and bound states, and records for most of the searches
below; this section describes part 1 as built.)
- A point where a computed verdict is unreliable is flagged ⚠. Examples:
  - the edge of CMS's plane (section 6 of the DM13 record);
  - a coloured partner within 20% of the dark matter's mass, where the
    Sommerfeld effect and bound states, not included, matter (part 2
    includes them and removes this flag).
- Constraints that apply but are not yet computed make a point pending:
  - beam dumps, B-factories and flavour;
  - dilepton resonances;
  - the CMB for s-wave annihilation below ~10 GeV;
  - the muon g−2, twist-2 and loop scattering;
  - the inelastic models' scattering, which goes through Path 1.

## 4. What is not built

Superseded by part 2 ([`portal_library_2.md`](portal_library_2.md), 2026-10-03), which
builds the Sommerfeld effect and bound states, the 2HDM+a, the inert doublet, the wino
and the higgsino, and records for the CMB, dark-photon searches and beam dumps, flavour,
dilepton resonances, coloured partners and the muon g−2. As part 1 left it:

- **Sommerfeld enhancement and bound-state formation.** The literature finds
  them essential for coloured partners near degeneracy and for multi-TeV
  electroweak dark matter. The points are flagged.
- **The 2HDM+a and the inert doublet.** They have many channels and
  coannihilating partners; their benchmarks are recorded in the survey.
- **Wino and higgsino.** They need the Sommerfeld effect; the thermal masses
  are 2.86 and 1.08 TeV (arXiv:2107.09688, 2205.04486).
- **Missing records:**
  - the CMB's bound on s-wave annihilation;
  - beam-dump, B-factory and flavour bounds;
  - LHC dilepton and coloured-partner searches;
  - the muon g−2.
- **Missing channels:**
  - the electroweak coannihilation channels of a coloured partner;
  - the W and Z channels of the lepton partner below ~200 GeV (the lepton
    portal's coannihilation uses hypercharge in the unbroken phase).

## 5. The validation (declared 2026-10-03, before its first run)

Run by `docs/portals/gate.py` ($0). MadDM is installed, and the DMSimpt files
are fetched into the tools folder.

- **P1: the building blocks.**
  - Interfering s-channel exchange equals explicit amplitudes to 10⁻¹⁰.
  - The Ward identities hold to 10⁻¹⁰.
  - These textbook limits hold to 10⁻³:
    - scalar QED, σv → 2πα²/m²;
    - scalar QCD, 14πα_s²/(27m²);
    - the Dirac t-channel, y⁴m²/(32π(m² + M²)²);
    - the Majorana t-channel, y⁴v²m²(m⁴ + M⁴)/(48π(m² + M²)⁴), and its
      s-wave ∝ m_f².
  - Γ(V → W⁺W⁻) equals its closed form to 10⁻¹⁰.
  - The coannihilation solver reproduces DM7's single-species Ωh² for V1
    and A1 at three points to 10⁻³.
- **P2: independent codes (MadDM).** Each comparison must agree within 20%,
  or 25% for coannihilation. MadDM's g* bookkeeping alone moves Ωh² by about
  10% (DM8).
  - (a) The scalar Higgs portal (DM8's UFO files, S S h only) at
    m_S = 90, 100 and 110 GeV, λ_hs = 0.1. All channels there are two-body,
    and hh is closed.
  - (b) The scalar mediator's new SS channel (DM8's G3 files) at
    (m_χ, m_S) = (600, 500) and (800, 300) GeV, g_χ = g_q = 1.
  - (c) The t-channel S3M_uR (DMSimpt, arXiv:2001.05024) at
    (m_χ, m_φ, y) = (500, 1500, 1.0), without coannihilation, and
    (500, 550, 0.5), with it. This runs only if the DMSimpt files can be
    fetched and run; otherwise it is reported as not run.
- **P3: the literature's results.** Newer data only exclude more, so a point
  the literature excludes must be excluded here, and a point it calls viable
  is checked only against an analysis that already includes LZ.
  - (a) The scalar singlet, at GAMBIT's two full-relic points
    (arXiv:1705.07931):
    - Ωh²(62.27 GeV, λ_hs = 2.9×10⁻⁴) and Ωh²(9.79 TeV, λ_hs = 3.1) are
      within 30% of 0.12;
    - the resonance point is excluded by no computed constraint (the
      invisible-width record used for this check);
    - every relic-contour point with 110 GeV < m_S < 1 TeV is excluded (Yu
      et al. with LZ, arXiv:2410.21089).
  - (b) The Z portal (Escudero et al., arXiv:1609.09079):
    - vector: every contour point with m_χ < 5 TeV is excluded;
    - axial: every contour point with 50 < m_χ < 150 GeV is excluded, and
      some contour point above 300 GeV is not.
  - (c) The fermion Higgs portal (Escudero et al.):
    - CP-conserving: every contour point outside 55–65 GeV is excluded;
    - CP-violating (ξ = π/2): direct detection excludes no contour point.
  - (d) Gauged B − L at g_BL = 0.1, n_χ = 1/3 (Klasen et al.,
    arXiv:1607.06468): every contour point with |m_Z′ − 2m_χ| > 0.2 m_Z′
    is excluded.
- **P4: the library.**
  - Every entry's typed model passes DM12's audit.
  - Every reference resolves on arXiv to a paper whose title holds the
    entry's title words.
  - Every entry runs Track 1 end to end on an 8 × 8 grid, with a verdict
    and a plot.
  - DM12's generated singlet-scalar content maps to its declared symbolic
    portal. The dark-photon, mixing-singlet and two partner sketches are
    refused with specific missing-coefficient, mass-basis or flavour reasons.
    This replaces the pre-remediation field-only benchmark substitution;
    explicit supported-model mappings have separate regression checks.

## 6. The validation's result (2026-10-03): P1, P2 and P4 passed; P3 passed except one item

Record in `docs/portals/gate.md` and `gate.json`.

**How the runs went.**
- **Run 1:** P1 passed. In P4 four entries crashed in Track 1: the three
  fermion Higgs portals and the vector Higgs portal, all at m_χ = 10 GeV
  with order-one couplings.
  - *Cause:* the Higgs boson's invisible width there is absurd (5×10⁴ GeV),
    so the resonance nodes of the relic integral reached u ≈ 4×10⁵, where the
    Bessel weight is NaN.
  - *Fix:* resonance nodes beyond the thermal range (u > 80) are dropped,
    and non-finite weights are zero. DM7's relic tests are unchanged.
  - The run was stopped and the validation rerun from the start.
- **Run 2:** P1 and P4 passed. P3 is as reported below. P2 did not run: my
  script named the dark matter "S", but ADROIT's UFO files call it "dms".
- **Run 3:** P2(a) and (b) ran; (c) failed on DMSimpt's names in MadGraph,
  which lowercases them and gives the u_R partner (PDG 2000002) its MSSM
  name "ur".
- **Run 4:** P2 passed. Both P2 fixes were to particle names in the script;
  no check or tolerance changed.

- **P1: passed.**
  - Interfering exchange matches explicit amplitudes to 4×10⁻¹⁶.
  - The Ward identities hold to 1×10⁻¹³.
  - Γ(V → WW) matches its closed form to 2×10⁻¹⁶.
  - The coannihilation solver reproduces DM7 to 5×10⁻⁵.
  - The textbook limits hold to 1.3×10⁻⁵ or better: scalar QED, scalar QCD,
    the Dirac t-channel, the Majorana p-wave and its m_f² s-wave.
- **P2: passed.** Ωh², MadDM against ADROIT:

  | model | point | MadDM | ADROIT | ratio |
  |---|---|---|---|---|
  | scalar Higgs portal (λ_hs = 0.1) | m_S = 90 GeV | 0.0160 | 0.0152 | 1.05 |
  | | 100 GeV | 0.0167 | 0.0162 | 1.03 |
  | | 110 GeV | 0.0205 | 0.0197 | 1.04 |
  | scalar mediator, χχ̄ → SS (g_χ = g_q = 1) | (600, 500) GeV | 0.101 | 0.1014 | 0.996 |
  | | (800, 300) GeV | 0.224 | 0.2253 | 0.994 |
  | S3M_uR (DMSimpt) | (500, 1500) GeV, y = 1, no coannihilation | 2.03 | 2.14 | 0.95 |
  | | (500, 550) GeV, y = 0.5, coannihilation | 0.225 | 0.234 | 0.96 |

  The last row checks independently the coannihilation solver, the
  coloured partner's QCD processes and the Majorana amplitudes.
- **P3: passed except (a)'s first item.**
  - (a) The scalar singlet:
    - at 9.79 TeV, λ_hs = 3.1: Ωh² = 0.111, within 7% of 0.12;
    - the contour from 110 GeV to 1 TeV is excluded throughout (13/13);
    - the resonance point is excluded by no computed constraint;
    - **missed as declared:** at GAMBIT's resonance point (62.27 GeV,
      λ_hs = 2.9×10⁻⁴), Ωh² = 0.069, 42% below 0.12, outside the declared
      30%.
  - (b) The Z portal:
    - vector: every contour point below 5 TeV is excluded (53/53);
    - axial: 50–150 GeV is excluded (10/10), and 18 contour points above
      300 GeV are not.
  - (c) The fermion Higgs portal:
    - CP-conserving: every contour point outside 55–65 GeV is excluded
      (43/43);
    - CP-violating: direct detection excludes none of its 59 contour points.
  - (d) B − L: every off-resonance contour point is excluded (5/5 of 56).
- **P4: passed** (on the rerun).
  - All 21 typed models pass DM12's audit.
  - All 36 references resolve on arXiv with their stored titles.
  - All 21 entries run Track 1 with a verdict and a plot.
  - All five DM12-generated contents are recognised.

**The missed item, P3(a) at the resonance.** These diagnostics were run
after the validation and were not declared:
- **Numerics:** the thermal average at the resonance matches the
  narrow-width formula, π λ²v² m_h β K₁(m_h/T)/(8m⁴T K₂(m/T)²), to 0.1%. A
  four-times finer grid changes Ωh² by 0.05%.
- **The Higgs mass:** GAMBIT fitted m_h as a nuisance (125.09 ± 0.24 GeV).
  Shifting m_h by its uncertainty moves Ωh² by ±8% only.
- **MadDM at the same point** gives Ωh² = 0.085 (0.066 at 60 GeV,
  λ = 10⁻³). That is 1.22 times ADROIT's, and also short of 0.12. Part of the
  difference is expected: MadDM uses m_h = 125 GeV, a fixed Higgs width and
  two-body final states only.
- **Yu et al. (with LZ)** put the full-relic band at a₂ ≥ 1.7×10⁻⁴, i.e.
  λ_hs ≥ 3.4×10⁻⁴. ADROIT reaches Ωh² = 0.12 at λ_hs ≈ 2.2×10⁻⁴.

So at the narrow resonance the published codes and MadDM differ from
ADROIT, and from each other, by factors of 1.2–2 in σv. The physics of
⟨σv⟩ there is set by λ, m_h and m_S alone, since BR(h → SM) ≈ 1. The
difference therefore lies in the codes' inputs or treatment (the Higgs
mass, the resonance's thermal average, possibly kinetic decoupling, which
arXiv:1706.07433 finds large exactly here), not in ADROIT's cross-section.
Until this is resolved, relic contours at the Higgs resonance (m_DM within
about 2 GeV of m_h/2) should be read with a factor-2 uncertainty in the
coupling-squared.

**The flag.** Since then, every Higgs-portal model (and the singlet mixing at
h₁) flags points within 2 GeV of m_h/2 as ⚠ unreliable, with this section as
the reason (`portals/higgs.RESONANCE_FLAG`).

**The owner's decisions (2026-10-03).**
- **Records:** the two invisible-width records (ATLAS BR(h → inv) < 0.107;
  LEP ΔΓ_inv(Z) < 2.0 MeV) are verified, and the scans use them by default.
- **The resonance:** P3(a)'s difference at the Higgs resonance is accepted.
  ADROIT's standard calculation stands. The spread between codes there is
  recorded above, and points within 2 GeV of m_h/2 carry the ⚠ flag.

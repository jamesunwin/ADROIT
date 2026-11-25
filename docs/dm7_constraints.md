# DM7: complementary constraints

Built 2026-09-30 to 2026-10-01. Cost: $0. Every number below comes from a script
in `docs/dm7/`, whose outputs sit beside it, or from the tests.

## 1. The gate, fixed before the run

The build plan's gate: "For three textbook mediator models, the combined
picture agrees with a published summary." This section fixes its reading on
2026-09-30, before any comparison is run.

**The published summary.** CMS, *Dark sector searches with the CMS
experiment*, Phys. Rept. 1115 (2025) 448, arXiv:2405.13778: Figs. 11 and 12
(the plane of mediator mass and dark matter mass, with the collider
exclusions and the thermal-relic contour Ωh² = 0.12) and Fig. 13 (the same
models in the plane of cross-section and mass).

**The three textbook models** are the LHC Dark Matter Working Group's
benchmarks (arXiv:1703.05703): Dirac dark matter and an s-channel spin-1
mediator, with g_DM = 1 and couplings universal across flavours.
- **V1:** vector, g_q = 0.25, g_ℓ = 0 (Fig. 11, upper).
- **A1:** axial-vector, g_q = 0.25, g_ℓ = 0 (Fig. 11, lower).
- **A2:** axial-vector, g_q = g_ℓ = 0.1 (Fig. 12, lower).

A2 rather than V2 because it differs most from the other two: its lepton
coupling is as large as its quark coupling. V2 (vector, g_q = 0.1,
g_ℓ = 0.01; Fig. 12, upper) is run and reported, outside the gate.

**The combined picture** of a model, in the (m_med, m_DM) plane:
- **collider exclusions:** CMS's observed contours, digitised into curated
  records. The plan takes collider limits from published summaries; the
  system does not compute them;
- **relic density:** computed by the system;
- **direct detection:** computed by the system from its validated experiment
  modules. The summary does not draw this in the mass plane, and its direct
  detection results are older than the modules', so this part is reported
  but is not part of the gate;
- **the map between the mass plane and the cross-section plane,** which
  Fig. 13 uses.

**The rule.** The gate is met if all three hold for each of V1, A1 and A2:
1. **Relic density.** The published Ωh² = 0.12 contour, resampled at 100
   points equally spaced along its drawn length, is compared point by point.
   A point passes if the system's Ωh² there lies within a factor 1.3 of 0.12
   (the tolerance of decision 4), or if the system's own Ωh² = 0.12 contour
   passes within 3% of it in m_med or in m_DM (DM3's clause for steep
   stretches). At least 90% of the points must pass (DM6's fraction).
2. **Translation to direct detection.** For any point of the mass plane, the
   system's spin-independent (V) or spin-dependent proton (A) cross-section,
   reached through its interaction library and its own conventions, agrees
   with the Working Group's formula used by CMS (arXiv:1603.04156) to 1%.
3. **The collider records.** Each digitised monojet contour reproduces the
   limit CMS quotes in its Table 2 (m_Z′ > 1.95 TeV at small m_DM, V1 and
   A1) within 3% in m_med.

**A validation rule for capture in the Sun, fixed before its first run**
(2026-09-30; a check of the tier-2 calculator, not part of the plan's gate).
IceCube's Table 1 of arXiv:1601.00653 lists, for 17 supersymmetric benchmark
models, the scattering cross-sections used for capture (σ′_SI,p, σ′_SD,p)
and the capture rate C that DarkSUSY 5.1.3 computed from them. The system's
capture rate, with those cross-sections (isoscalar SI; SD on protons only)
and DarkSUSY's default halo (ρ = 0.3 GeV/cm³, a Maxwellian with
v₀ = 220 km/s, no escape-speed cut, the Sun moving at 220 km/s), must lie
within a factor 1.3 of the published C for at least 90% of the models.

## 2. The textbook models and their relic density (built 2026-09-30)

**The completions** (`constraints/spin1.py`). The Working Group's spin-1
models: widths (arXiv:1703.05703, eqs. 2.4–2.11), the neutrino coupling
that gauge invariance requires (g_ν = ±g_ℓ), and the map onto the library's
mediator cards: g_V^N = 3g_q; g_A^N = g_q(Δu + Δd + Δs), with the Working
Group's spin fractions (0.84, −0.43, −0.09; arXiv:1603.04156).

**Annihilation** (`constraints/annihilation.py`, `constraints/amplitudes.py`).
- χχ̄ → f f̄ through the s-channel mediator: an exact formula at every
  energy, including the longitudinal part of the propagator, which gives the
  helicity-suppressed s-wave of the axial model.
- χχ̄ → Z′Z′ through t- and u-channel exchange: computed from the explicit
  amplitude, with all polarisations.
- The explicit amplitude uses Dirac matrices, spinors and polarisation
  vectors written out and summed numerically. It checks the analytic formula
  to 10⁻⁶ for every coupling structure, and gives the Working Group's s-wave
  for mediator pairs (eqs. 3.7, 3.8).

**The relic density** (`constraints/relic.py`). The Boltzmann equation with
the exact relativistic thermal average (Gondolo–Gelmini), which follows the
s-channel resonance. The Standard Model degrees of freedom are an ideal gas
with a hadron gas below 160 MeV. An s-wave σv = 2.2 × 10⁻²⁶ cm³/s gives
Ωh² = 0.12 within 5% for self-conjugate dark matter at 100 GeV (twice that for
Dirac dark matter).

**Why not micrOMEGAs or MadDM.** The plan names them for tier 3. Their
licences are still unread (DM0), and the owner's rule is to read a licence
before depending on a tool. For the textbook models every cross-section is
known in closed form or from a two-diagram amplitude. So the relic density
is computed here, like the rates (decision 10), and checked against the
published MadDM curves. micrOMEGAs and MadDM stay the route for DM8's
arbitrary Lagrangians, once their licences are read. **Approved by the
owner (2026-10-01): micrOMEGAs and MadDM are left for DM8.**

## 3. The gate: results

**Item 2, the translation: met.** The library route (card → operator
coefficients → the rate code's conventions) gives the Working Group's
σ_SI and σ_SD,p to 10⁻⁶ for all four models at every mass tested
(`tests/constraints/test_relic.py`).

**Item 3, the collider records: met.** The digitised monojet contours reach
m_med = 1957 GeV (V1) and 1950 GeV (A1), against the 1.95 TeV of CMS's
Table 2.

**Item 1, the relic density (`docs/dm7/relic_gate.txt`): not met as
declared.**

| model | points passing | within ×1.3 | Ωh²/0.12, median | failures |
|---|---|---|---|---|
| V1 (gate) | 78/100 | 78 | 0.971 | all 22 at m_DM ≤ 8.4 GeV |
| A1 (gate) | 93/100 | 93 | 0.988 | all 7 at m_DM ≤ 5.0 GeV |
| A2 (gate) | 97/100 | 97 | 0.993 | all 3 at m_DM ≤ 5.0 GeV |
| V2 (reported) | 89/100 | 89 | 0.972 | all 11 at m_DM ≤ 5.0 GeV |

- **Above m_DM = 10 GeV every point passes:** 343 of 343 over the four
  models, the largest deviation 13% in Ωh². This includes the resonance
  corridor and the region where annihilation into mediator pairs dominates.
- **Every failure is below 8.4 GeV,** where the system's Ωh² is lower than
  0.12 by up to a factor 14. Three observations:
  - On the figure's linear axis (0 to 2000 GeV over 171 pt), m_DM < 10 GeV
    lies within one line width of the axis. There the published contour
    runs in steps (m_DM = 3.4, 3.4, 3.4, 4.0, 4.0, 4.5, …) and hugs the
    b-quark threshold. That is the signature of a contour interpolated on a
    coarse grid, not of the physics.
  - Taking out annihilation into u, d, s (or u, d, s, c) does not reproduce
    the published contour either: Ωh² then scatters from 0.01 to far above
    0.12 along it (`docs/dm7/diagnose_low_mass.txt`, a diagnosis only; the
    calculation keeps every quark).
  - Freeze-out for these masses happens at T ≈ 0.2–0.4 GeV, at the QCD
    transition. Annihilation into free quarks and the ideal-gas degrees of
    freedom are unreliable there, in any code.
- **A bug found by the first run, and fixed.** Annihilation into mediator
  pairs was allowed only for m_DM > m_med. It also opens slightly below, in
  the thermal tail ("forbidden" annihilation, Griest & Seckel 1991). In the
  first run (`docs/dm7/relic_gate_first_run.txt`) the 18 points with
  0.9 < m_DM/m_med < 1 had Ωh² up to 1.06; four of them failed, and the
  rest passed only by the 3% clause. With the channel all 18 give
  0.116–0.120. No point changed by more than 1% otherwise.

**Decision for the owner.** Under the rule as declared, the gate is not met,
because V1 has 78 passing points. The disagreement is confined to
m_DM < 10 GeV, where the reference cannot be read at the precision the rule
assumes and the physics is at the QCD transition. Two options:
- accept part 1, with the region m_DM < 10 GeV recorded as outside what the
  published figure resolves; or
- hold it as not met, and test the low masses against a reference that
  resolves them (a relic calculation plotted on a logarithmic mass axis, or
  micrOMEGAs once its licence is read).

**Gate accepted by the owner (2026-10-01).** Part 1 is accepted with the
region m_DM < 10 GeV recorded as outside what the published figure resolves.
The relic density below 10 GeV, at the QCD transition, is on the list of
future improvements (`adroit_phase2.md`).

## 4. Capture in the Sun (tier 2)

**The calculator** (`constraints/capture.py`). Gould's capture rate, with the
cross-section taken from the rate code itself (`rates.response_terms`, a
refactor that leaves every direct-detection rate unchanged):

    w² dσ/dE_R = m_T/(2π) [P(E_R) + Q(E_R)(w² − v_min²)] .

So capture uses the same operators, couplings and nuclear responses as
direct detection, for any interaction, inelastic and exothermic included. The
nuclear responses of the sixteen solar elements (H to Ni) are Catena and
Schwabe's (arXiv:1501.03729), already in the shipped shell-model data. The
Sun is the B16 AGSS09 standard solar model (arXiv:1611.09867; fetched from
Capt'n General, MIT, pinned to a commit), with escape speeds of 1381 km/s at
the centre and 618 km/s at the surface. The halo is seen from the Sun.

**Validation: met** (`docs/dm7/capture_check.txt`; rule in section 1).
18 of 18 of IceCube's DarkSUSY capture rates (arXiv:1601.00653, Table 1) are
reproduced within the factor 1.3:
- where capture on hydrogen dominates (up to 275 GeV), within 1–7%;
- near 1 TeV, where spin-independent capture on heavy elements matters,
  11–22% lower, as expected from different form factors (shell model here,
  Helm in DarkSUSY) and solar metallicities.

The table has 18 models; the rule's "17" was a miscount, and all 18 are used.

**Equilibrium.** Γ_A = (C/2) tanh²(t⊙/τ), from the completion's ⟨σv⟩ when
there is one; otherwise equilibrium is an assumption, stated.

## 5. The curated database and the verdicts

**The database** (`constraints/data/records.yaml`, `constraints/database.py`).
Eight records, each with its source, its data (inline or a digitised file),
the assumptions under which it holds and the checks made on its
transcription:
- Planck 2018 Table 2, TT,TE,EE+lowE+lensing: Ωh² = 0.1200 ± 0.0012;
- CMS's collider summary for V1, A1, V2, A2: the observed excluded regions,
  from the figure's fills (dijet and dilepton searches) or its contours
  closed to m_DM = 0 (searches with missing energy);
- IceCube 2011–2014 (arXiv:1612.05949): SD and SI limits for b b̄, W⁺W⁻,
  τ⁺τ⁻;
- Fermi-LAT, 15 dwarf galaxies (arXiv:1503.02641): ⟨σv⟩ limits for e⁺e⁻,
  μ⁺μ⁻, τ⁺τ⁻, u ū, b b̄, W⁺W⁻.

The figures are digitised from their vector paths
(`docs/dm7/digitise_limits.py`, `digitise_cms_summary.py`), calibrated from
the tick marks. On a logarithmic axis the label centres would bias the limits
by up to 8%. Every curve's masses fall on round values to 0.01%, and
Fermi-LAT's b b̄ limit at 100 GeV is 2.21 × 10⁻²⁶ cm³/s, as its text implies.

**Verified by the owner (2026-10-01).** The plan's rule is that a person
verifies each record before it is used. Until then `database.usable()`
returned none of them, and the pipelines used them only when asked
(`unverified_records=True`), saying so. The owner checked and approved all
eight; each now carries `verified_on` and `verified_by`. A record added later,
by a person or proposed by an agent, is again unused until verified.

**The verdicts** (`constraints/verdicts.py`). For every candidate and record
the verdict is one of three:
- *applies*;
- *applies under stated assumptions*;
- *needs a further calculation*, which is named.

The rules:
- **Tier 3** (relic density, gamma rays from dwarf galaxies, colliders) needs
  a relativistic completion. Without one the verdict names it as the missing
  calculation.
- **A collider summary applies only to its own benchmark;** any other model
  needs a recast.
- **Tier 2 (IceCube) applies to any interaction.** Capture rates are compared
  directly: C_candidate × tanh² against C(σ_lim), the capture rate of the
  telescope's own reference interaction at its limit. The system's capture
  code computes both, so the comparison holds for any operator, inelastic
  scattering included. Without a completion the channel is assumed to be
  b b̄, the softest and weakest limit.

A cross-check: IceCube's SD and SI limits are two translations of one limit
on the annihilation rate. Through the system's capture code they agree to
13%.

**In the pipelines.** Path 2 judges each leading candidate at its best-fit
coupling and records the verdicts beside the tournament. **Complementary
constraints do not move the ranking** (a design decision): each rests on
assumptions beyond the candidate (a channel, equilibrium, a thermal history,
a completion), so it is shown beside the candidate with them rather than
folded into the AIC. Approved by the owner (2026-10-01).

## 6. LZ's leading candidates against the complementary constraints

`docs/dm7/lz_complementary.md`: DM6's eight leaders, each at the coupling
that explains LZ's event (rerun with the verified records; the numbers are
unchanged).

| candidate | C (s⁻¹) | C / allowed by IceCube: b b̄, W⁺W⁻, τ⁺τ⁻ |
|---|---|---|
| O01v@1000, δ = 350 | 1.2 × 10²⁰ | 0.018, 0.68, **2.2** |
| O04v@1000, δ = 350 | 0 | — |
| O04v@4000, δ = 350 | 0 | — |
| O01v@400, δ = 300 | 2.6 × 10²⁰ | 0.006, 0.40, 0.94 |
| L12s@4000 | 2.3 × 10¹⁶ | ≤ 7 × 10⁻⁴ |
| O01v@1000, δ = 300 | 1.6 × 10¹⁹ | 0.003, 0.10, 0.32 |
| O04v@400, δ = 300 | 0 | — |
| O01s@1000, δ = 350 | 9.6 × 10²¹ | **1.5, 56, 180** |

- **The Sun cannot capture the inelastic spin-dependent leaders at all.**
  Only light nuclei carry spin in the Sun, and no scattering on them can
  supply 300–350 keV: upscattering needs w² ≥ 2δ/μ.
- **The isoscalar inelastic O1 leader is excluded by IceCube,** even for
  annihilation into b b̄, provided the Sun is in equilibrium.
- **The isovector O1 leaders survive for soft channels.** One of them
  (δ = 350 keV, 1 TeV) is excluded for τ⁺τ⁻. An isovector coupling nearly
  cancels on iron, the Sun's main capturer here (Z = 26, N = 30), more than on
  xenon.
- **A caveat attached to every inelastic verdict:** captured particles must
  scatter again to settle in the core, and each later scattering must also
  excite the splitting. The telescope limits assume they do.
- Tier 3 needs a completion for every leader: they are operators or
  Lagrangians without couplings to Standard Model states.

## 6a. The combined picture of the textbook models

`docs/dm7/combined_picture.png` (`.json`, `.py`) draws, for V1, A1, A2 and V2,
every constraint class in CMS's plane, on a 44 × 44 grid (computed with the
records before their verification, which changed none of their contents):
- CMS's collider regions (records);
- the system's relic contour, beside CMS's;
- direct detection from the system's own validated modules;
- IceCube through capture in the Sun, with the channel and equilibrium
  computed from the model;
- Fermi-LAT's dwarf galaxies.

| model | direct detection excludes m_med below (m_DM = 10 / 100 / 300 GeV) | IceCube reaches m_med | Fermi-LAT reaches m_med |
|---|---|---|---|
| V1 | 31 / 37 / 30 TeV | 1.9 TeV | 4.1 TeV (near resonance) |
| A1 | 420 / 440 / 350 GeV | 460 GeV | 520 GeV |
| A2 | 270 / 280 / 220 GeV | 280 GeV | 520 GeV |
| V2 | 19 / 23 / 19 TeV | 1.3 TeV | 4.1 TeV (near resonance) |

- **The vector models are excluded by direct detection throughout CMS's
  plane,** by tens of TeV in mediator mass: the known result that LZ, XENONnT
  and PandaX-4T overtake the LHC for vector mediators.
- **For the axial models the LHC leads.** PICO-60 (the only spin-dependent
  proton module validated above 20 GeV) reaches a few hundred GeV, as do
  IceCube and Fermi-LAT. The dijet and monojet searches reach 2–3.5 TeV.
- **The relic contours coincide with CMS's across the picture,** except below
  m_DM ≈ 10 GeV (section 3).

## 7. In Path 1

Capture in the Sun goes as μ², so each telescope record becomes a limit on
the strength μ at every mass: μ_up = √(C_allowed / C(μ = 1)). The report and
the plot list these limits beside the modules':
- for the softest channel (b b̄) and a hard one (τ⁺τ⁻);
- never in the envelope, which stays the direct-detection modules';
- only from verified records unless the request asks otherwise
  (`ExclusionRequest.telescopes`, `unverified_records`).

## 8. Not done in DM7

- **Completions beyond the spin-1 models:** scalar and pseudoscalar
  mediators, the Higgs and Z portals, dipoles. Until DM8 derives completions
  from Lagrangians (with micrOMEGAs or MadDM once their licences are read),
  their tier-3 verdicts name the missing completion.
- **Collider recasts** away from the published benchmarks; recasting tools
  are in `adroit_phase2.md`.
- **Further records:** other neutrino telescopes (Super-K, ANTARES, IceCube
  DeepCore), newer dwarf-galaxy analyses, the CMB bound on s-wave
  annihilation, beam dumps and flavour.
- **Inelastic dark matter in the Sun beyond first capture:** whether the
  captured particles settle in the core. And the relic density of
  pseudo-Dirac completions, which needs coannihilation with the excited
  state.
- **The relic density below m_DM = 10 GeV** (accepted gate, section 3):
  listed as a future improvement in `adroit_phase2.md`.

## 9. Reproducing DM7

```bash
uv run --with pymupdf python docs/dm7/digitise_cms_summary.py   # CMS Figs. 11–12
uv run --with pymupdf python docs/dm7/digitise_limits.py        # IceCube Figs. 7–8, Fermi-LAT Fig. 8
nice -n 10 uv run python docs/dm7/relic_gate.py                 # gate item 1, ~5 minutes
nice -n 10 uv run python docs/dm7/diagnose_low_mass.py > docs/dm7/diagnose_low_mass.txt
uv run python docs/dm7/capture_check.py                         # capture against IceCube's DarkSUSY rates
nice -n 10 uv run python docs/dm7/lz_complementary.py           # LZ's leaders
nice -n 10 uv run python docs/dm7/combined_picture.py           # the combined picture, ~10 minutes
```

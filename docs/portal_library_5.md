# The portal library, part 5: the remaining LHC searches, and where the theory uncertainty is larger

Started 2026-10-04 at the owner's request: implement the four searches that part 4 left to SModelS's gaps
(`docs/portal_library_4.md`, section 7), and record in the documentation the known cases where the theory
uncertainty is larger than the combined likelihood's generic defaults (section 7 below). The code is
`parameter_space/resonances.py`, plus the broad-width ZZ limits in `parameter_space/searches.py`.

## 1. Dijets below 1.5 TeV, and broad dijets (`resonances.dijet`)

**Below 1.5 TeV.** CMS's search with data scouting (arXiv:1806.00843, 36 fb⁻¹) publishes an upper limit on the
universal quark coupling g_q′ of a leptophobic Z′ that couples only to quarks, 0.6–3.7 TeV.

A portal's Z′, with its own σ and BR(jj), acts as that Z′ with

    g_eff² = σ BR(jj) / (σ₁ BR_ref(jj)),      r = (g_eff / g_lim)²,

where σ₁ is the unit-coupling σ (MadGraph) and BR_ref(jj) is the quark-only Z′'s: the five light flavours over
all quarks, which is 1 below the tt̄ threshold. This applies to the DM13 spin-1 class (V1, A1) and to B − L, for
Γ/m ≤ 10%.

**Broad.** For Γ/m > 10%, ATLAS's limits on Gaussian signals of relative width 0–15% (arXiv:1910.08447, 139 fb⁻¹)
are used from 1.5 TeV:
- σ_G is matched to the Breit–Wigner's full width at half maximum, σ_G = Γ/2.355 (since 2026-10-17 a flag only: the
  decision follows ATLAS's truncation recipe, 0.8–1.2 M against the 10% Gaussian; the external audit's item 18);
- the acceptance is ATLAS's own for its DM Z′ of the same width (its g_q columns have Γ/m = 3g_q²/(2π)),
  interpolated in the width between the columns that cover the mass (since 2026-10-12; before, the column nearest
  the point's g_q).

Up to Γ/m = 12% only (since 2026-10-12; before, to ≈ 35%): ATLAS's widest DM Z′ (g_q = 0.5) has Γ/m = 12%, "nearly
the maximum width to which this search is sensitive", and it gives no acceptance beyond. A broader Z′, or one at a
mass where no column of its width exists (10–12% only from 4 TeV), is undecided ([`widths.md`](widths.md)).

**Not covered.** Below 0.6 TeV. The photon- and jet-ISR searches (ATLAS arXiv:1901.10917, CMS arXiv:1909.04114)
would need σ(Z′ + γ or jet) with their selections, which is not tabulated. For V1 and A1, CMS's own summary
record covers that region.

## 2. tt̄ resonances (`resonances.ttbar`)

CMS (arXiv:1908.01115, 35.9 fb⁻¹, 400–750 GeV) publishes the excluded bands of the top-coupling modifier g_Φtt for
a scalar and a pseudoscalar, at relative widths 0.5, 1, 2.5, 5, 10 and 25%. The interference with QCD tt̄ is
included. At large widths and high masses there are allowed islands inside the excluded band.

g_Φtt is the top coupling in units of the Standard Model's m_t/v:

| portal | state | g_Φtt |
|---|---|---|
| DM13 scalar class, ALP-like portal | S (CP-even or CP-odd) | g_q |
| singlet mixing | h₂ | sin θ |
| 2HDM+a | a, A | s_θ/t_β, c_θ/t_β |
| 2HDM+a | H | 1/t_β |

**Between two tabulated widths** a point is excluded only if both widths exclude it, and allowed only if both
allow it; otherwise it is undecided. Γ/m below 0.5% uses the 0.5% table; above 25% it is undecided. This search is
a cut only, with no ratio in the combined likelihood, because the bands are not monotone in g.

## 3. Broad resonances

| search | widths | where |
|---|---|---|
| heavy scalar → ZZ (ATLAS arXiv:2009.14791) | the narrow table below Γ/m = 0.5% (§9.1.1); the 1–15% tables (from 400 GeV) only for a model matching ATLAS's interference modelling, which the singlet does not | the singlet's h₂ |
| heavy scalar → WW (ATLAS arXiv:2004.14636) | narrow only: Γ/m below the detector mass resolution (7% at 1 TeV to 4% at 5 TeV, §5.6) | the singlet's h₂ |
| dijets | to Γ/m = 12% (section 1) | Z′ from 1.5 TeV |
| tt̄ | 0.5–25% (section 2), for one state produced through the top loop | scalars, 400–750 GeV |
| dileptons (ATLAS arXiv:1903.06248) | 0–10%, already in part 2 | B − L |

Broader than these is undecided: it shows as pending, never as allowed. Each search's width domain and the
assumptions beyond the width are in [`widths.md`](widths.md) (2026-10-12).

## 4. The 2HDM+a's mono-Higgs and mono-Z away from ATLAS's plane (`resonances.monoh`, `resonances.monoz`)

**Mono-Higgs** (ATLAS arXiv:2108.13391, h → b b̄, 139 fb⁻¹). ATLAS publishes its upper limit σ₉₅(m_A, m_a) on the
gluon-fused 2HDM+a signal at 94 mass points. The masses fix the kinematics, so for any (sin θ, tan β):

    r = σ(gg → A) BR(A → a h) BR(a → χχ̄) / σ₉₅(m_A, m_a),

- **The cross-section** is at leading order, as ATLAS's benchmark is, from the per-quark tables with the type-II
  couplings (part 4). The branching fractions come from the UFO model's own vertices.
- **The limit** is interpolated linearly over ATLAS's grid, in log σ₉₅; outside the grid the point is undecided.

**The domain of the resonant picture.** At ATLAS's own benchmark our resonant σ is 0.4–1.2 of ATLAS's full
σ where A is narrow (Γ_A/m_A ≤ 10%), with median 0.89. It is lower at small m_a, where non-resonant diagrams add.
Beyond 10% width (m_A ≳ 1.4 TeV at sin θ = 0.35), the non-resonant production dominates, and ATLAS's σ exceeds the
resonant one by up to 10³. So the recast applies only to a narrow A; a broader A is undecided.

Within that domain (50 of ATLAS's 94 grid points; 38 have a broad A and 6 no resonant A), the verdict is undecided
where r lies in the band 0.4189–1.24 that ATLAS's full σ spans relative to our resonant one (`docs/monoh/README.md`):
11 points, among them (1000, 500) GeV, where ATLAS excludes and r = 0.95. The other 39 verdicts all agree with
ATLAS's. (Before the band, 49 of the 50 agreed, and the one disagreement was that point.)

b b̄ → A, important at large tan β, is left out, so that case is conservative too.

**Mono-Z** (ATLAS arXiv:2111.08372, Z → ℓℓ, 139 fb⁻¹). ATLAS publishes only contours, in (m_a, m_H) at tan β = 1
and sin θ = 0.35 and 0.7. The rule is therefore monotone. At the point's (m_a, m_H), the rate
σ(gg → H) BR(H → a Z) BR(a → χχ̄) is compared with each contour's reference model (tan β = 1, λ₃ = λ_P1 = λ_P2 = 3,
m_χ = 10 GeV, y_χ = 1), computed by ADROIT at the same masses. The K-factor cancels in the ratio.
- **Excluded:** inside a contour with at least its reference rate.
- **Allowed:** outside a contour with at most its reference rate.
- **Otherwise undecided,** because no interpolation in the rate is assumed.

The same narrow-H condition applies, and m_a below 100 GeV (the plane's edge) is not covered.

**The library's 2HDM+a benchmark** (M_a = 400, m_χ = 160, heavy states at 1 TeV) is now excluded by the mono-Higgs
as well as by ATLAS's plane. Its mono-Z is undecided: the rate lies between the two planes' references.

## 5. Validation

`scripts/validate_portal_library_5.py` is local and takes about 10 s. As in parts 2–4, the ranges were declared
after the development runs, so these gates guard against regressions rather than test blind.

| gate | ours | range | reference | result |
|---|---|---|---|---|
| 2HDM+a mono-h: verdicts agreeing with ATLAS's at its grid points with a narrow A (39) | 1.000 | 0.95–1 | ATLAS's σ₉₅ against its benchmark σ | pass |
| 2HDM+a mono-h: median σ(resonant, ours) / ATLAS's benchmark σ, narrow A (the 39 decided points) | 0.869 | 0.7–1.1 | ATLAS's σ includes non-resonant diagrams | pass |
| 2HDM+a mono-Z on ATLAS's own plane: the contour's verdict (12 points; plumbing) | 1.000 | 1–1 | the reference model is the point itself | pass |
| dijets below 1.5 TeV: CMS's coupling limit, recast, against CMS's V1/A1 contour (60 points) | 1.000 | 1–1 | cms-2405.13778 | pass |
| broad ZZ: smallest limit(wider) / limit(narrower) over masses and widths | 1.040 | 1–∞ | limits weaken with width | pass |

**5 of 5 pass.** The dijet gate is the strongest test. CMS's leptophobic-Z′ coupling limit, recast through
g_eff, reproduces CMS's own exclusion of V1 and A1 at all 60 points from 0.65 to 1.5 TeV, where SModelS has no map.

**Tests** (`tests/parameter_space/test_resonances.py`) cover:
- the reference BR(jj);
- the CMS dijet recast against a hand calculation;
- the broad and too-broad Z′;
- the tt̄ bands, including an allowed island at 740 GeV;
- each portal's top coupling;
- the ZZ width interpolation;
- the contour test;
- a slow test of the mono-h agreement.

## 6. Records (5 new, all awaiting verification)

| id | what | data |
|---|---|---|
| cms-1806.00843-dijet | a leptophobic Z′'s quark coupling, 0.6–3.7 TeV | HEPData (CC0) |
| atlas-1910.08447-dijet-gaussian | Gaussian dijet limits, 0–15% widths; the DM Z′ acceptance | HEPData (CC0) |
| cms-1908.01115-ttbar | g_Φtt excluded bands, 0.5–25% widths | HEPData (CC0) |
| atlas-2108.13391-monoh | σ₉₅ and the benchmark σ over (m_A, m_a); the contour | HEPData (CC0) |
| atlas-2111.08372-monoz | contours in (m_a, m_H) at sin θ = 0.35, 0.7 | HEPData (CC0) |

The ZZ record (atlas-2009.14791-zz) gains the broad-width tables 12–15. With these, **26 records await
verification**: 10 from part 2, 3 from part 3, 8 from part 4 and 5 from part 5.

**The same data once.** SModelS's database holds only one of these papers, ATLAS-EXOT-2019-03 (arXiv:1910.08447),
as narrow maps. The Gaussian limits are used only for Γ/m > 10%, where those maps give no result, so the two never
meet. CMS-EXO-20-004 (part 4's monojet record) remains the one de-duplicated analysis.

## 7. Where the theory uncertainty is larger than the defaults (gap 3, recorded)

The combined likelihood (`adroit track1 --likelihood`) profiles a generic theory uncertainty: 10% on Ωh² and 0 on
each prediction by default (`--relic-theory`, `--theory`). The hard-cut verdicts carry none. The cases below are
known to be larger. They are recorded here, not modelled per model, and a verdict near its boundary in one of them
should be read with the stated spread.

**The relic density**

| case | spread | source |
|---|---|---|
| coloured t-channel partner, compressed (m_φ < 1.2 m_χ) | ±15% on the thermal mass, ±35% on Ωh² | Sommerfeld and bound-state treatments: De Simone et al., Becker et al., Liew & Luo, Harz & Petraki (part 2) |
| inert doublet, W W* / Z Z* region (M_H₀ ≈ 55–75 GeV) | ADROIT/micrOMEGAs 0.87–1.15 | part 3's cross-check: Ωh² moves 6–9× with the off-shell states |
| near an s-channel resonance (m_χ ≈ m_med/2, e.g. the singlet at the Higgs pole) | up to an order of magnitude | early kinetic decoupling, not modelled: Binder, Bringmann, Gustafsson & Hryczuk arXiv:1706.07433 ("up to one order of magnitude" for the scalar singlet) |
| wino | thermal mass 2.84 (NLO potential) – 2.89 TeV (LO); bound states −2.7% (ours) against −1.3 to −2% (Mitridate et al.) | Beneke et al. arXiv:2009.00640; part 3 |
| higgsino | thermal mass 1.08–1.1 TeV | bound states, Bottaro et al. |
| 2HDM+a | ADROIT/MadDM 1.11–1.14 | MadDM's g* counts ghosts (part 2's amendment) |
| any model below ≈ 8–10 GeV | DM7's relic gate failed below 8.4 GeV | QCD phase transition and hadronic channels (`docs/adroit_phase2.md`) |

**Direct detection**

| case | spread | source |
|---|---|---|
| higgsino σ_SI | an order of magnitude | the scalar and spin-2 amplitudes nearly cancel: Hill & Solon arXiv:1409.8290, Hisano et al. arXiv:1504.00915 |
| Higgs-mediated σ_SI (Higgs portals, singlet, 2HDM+a) | about ±20% (estimate) | the nucleon's Higgs coupling f_N ≈ 0.28–0.33 between hadronic inputs (σ_πN, strangeness); σ ∝ f_N² |
| coloured partner, twist-2 | quantified since 2026-10-10: ±δ on the amplitude, ε = 2m_χm_N/(m_φ² − m_χ²); since 2026-10-12 δ = w ε/(1 − ε), the higher moments bounded by each quark's ⟨x²⟩/⟨x⟩ (an approximation; `docs/twist2/README.md` outlines the full calculation); not computed for ε ≥ 1 (`portals/tchannel.py`) | Hisano et al.; the quark's momentum resolves the propagator |
| lepton partner's anapole | 5.6× in rate, conservative | the envelope uses PandaX-4T and XENONnT above 80 GeV, where LZ is outside its validated range (part 4) |
| 2HDM+a loop scattering | ≲ 10% (boxes left out) at tan β ≲ 10, more at large tan β | Abe, Fujiwara & Hisano arXiv:1810.01039 |
| every limit | ρ⊙ and the velocity distribution are the standard halo model's; ρ⊙ = 0.3 against 0.4 GeV/cm³ moves every rate by 33% | not varied |

**Indirect detection**

| case | spread | source |
|---|---|---|
| wino γ-ray line | ×2 (1.7–5.5 × 10⁻²⁶ cm³/s at 2.9 TeV) | the LO against NLO potential, and the resummation (part 4) |
| higgsino γ-ray line | ×2 | H.E.S.S. 2026's plotted curve is the photon count (the survey's finding) |
| γ-ray lines, the halo | Einasto 5–6× stronger than the cored profile used; a kpc core weakens H.E.S.S. 2018 by 10²–10³ | the records use each paper's most conservative profile |
| antiprotons | ×3–10 between analyses at some masses | propagation, the ≈ 100 GeV "hint" (Calore et al. and others, part 4) |
| CMB below 5 GeV, hadronic channels | bracketed between the e, γ and μ values | f_eff for π, K final states not computed |

**The LHC**

| case | spread | source |
|---|---|---|
| q q̄ → Z′ at LO | conservative by K = 1.2–1.37 | the Z check, part 4 |
| gg → S × K ≈ 2.5 | YR4's own uncertainty on the heavy-Higgs σ: scale ±5–8%, PDF + α_s 3–9% (more above 1 TeV); and the CP-even K applied to the pseudoscalar | YR4 (arXiv:1610.07922); MadGraph survey |
| 2HDM+a mono-h | resonant σ 0.4–1.2 of ATLAS's full σ (narrow A only) | section 4 |
| SModelS | interpolation within its maps, and the simplified-topology decomposition (not quantified here) | arXiv:2306.17676 |
| broad dijets | the Breit–Wigner–Gaussian matching (σ_G = Γ/2.355) | section 1 |
| CMS tt̄ | undecided between tabulated widths when they disagree | section 2 |
| the monojet recast | the missing-momentum spectrum is the m_DM = 1 GeV benchmark's; poorer near m_med ≈ 2m_χ | part 4 |

## 8. The critical gaps that remain

1. **Twenty-six records await verification.** The owner will verify them, with an external language model's
   help.
2. **Searches still outside ADROIT:**
   - dijets below 0.6 TeV;
   - Z′ broader than 12% (dijets) or 10% (dileptons);
   - the 2HDM+a with a broad A or H, and b b̄ → A at large tan β;
   - tt̄ above 750 GeV (ATLAS's 140 fb⁻¹ result is not on HEPData);
   - the inert doublet's electroweak precision and the 2HDM+a's flavour bounds.

   Where these apply, points are undecided or the gap is named as pending.
3. **The theory spreads of section 7** are recorded, not propagated: the likelihood's defaults remain generic.

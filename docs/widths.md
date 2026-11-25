# Resonance widths: where each search's limits apply

A limit set for one signal shape applies to another only within the widths its paper validates, and sometimes only if
other assumptions match too (interference, production mode). ADROIT has no shared narrow-width default: each search
uses the domain its own paper states, and a point outside it is **undecided**, with the reason (never allowed). This
page lists every search whose application depends on a width (the owner's data audit, 2026-10-12).

## The searches

| search (record) | what the paper states | what ADROIT applies | since |
|---|---|---|---|
| **ATLAS H → ZZ** (`atlas-2009.14791-zz`) | The narrow-width result "is valid for models in which the width is less than 0.5% of m_H" (§9.1.1). The large-width limits (§9.1.2) are for ggF only, Γ/m = 1, 5, 10, 15%, from 400 GeV. They include the heavy scalar's interference with the SM Higgs boson h and with the gg → ZZ continuum (§5, "Interference modelling"). The H–h term is modelled for H and h with the same production and decay amplitudes, differing only in the propagator. | The narrow table for Γ/m < 0.5% (`ZZ_NARROW`). The large-width tables only for a model whose interference matches ATLAS's (`_lwa_mismatch`), interpolated in the width with the narrow table as 0%. The singlet's h₂ does not match, so for it Γ/m ≥ 0.5% is undecided. | 2026-10-12; before, the narrow table up to 5% below 400 GeV, and the large-width tables by width alone |
| **ATLAS X → WW** (`atlas-2004.14636-ww`) | Its spin-0 limits are for "narrow resonances, whose intrinsic widths are smaller than the detector mass resolution" (§5.6). The ℓνqq resolution is ≈ 8% resolved (0.5–1 TeV), and 7% at 1 TeV to 4% at 5 TeV merged. Its benchmark radion has Γ/m = 0.26% at 800 GeV and 3.2% at 3 TeV (Table 1). | Γ/m below 0.6 of the merged resolution (the smaller: 7% to 1 TeV, then linear to 4% at 5 TeV; `WW_RESOLUTION`, `WW_NARROW_FRACTION`), the largest ratio ATLAS applies its limits to (the radion at 3 TeV). | 2026-10-12 (0.6: the owner's decision); before, Γ/m ≤ 5% |
| **ATLAS dileptons** (`atlas-1903.06248-dilepton`) | Limits for generic Breit–Wigner signals of Γ/m = 0–10%. The fiducial region requires m_ℓℓ(true) > m − 2Γ, "to reduce the model dependence from off-shell effects". Interference with Drell–Yan is neglected. Efficiencies are for spin 1 (spin 0 and 2 within 4%). | Interpolated in Γ/m between the 0–10% tables; wider than 10% undecided. Leading-order σ × ATLAS's SSM fiducial/LO ratio (1.087), only up to 4.5 TeV. | widths: R4; 4.5 TeV: 2026-10-12 |
| **CMS dijets** (`cms-1806.00843-dijet`) | The narrow-resonance coupling limits are "approximately valid" for Γ/m < 10% (g_q′ < 0.45) for masses below about 4 TeV (§4.4). | Γ/m ≤ 10% (`NARROW_DIJET`); the record ends at 3.7 TeV. | R4 (consistent) |
| **ATLAS Gaussian dijets** (`atlas-1910.08447-dijet-gaussian`) | Gaussian signals of σ_G/m = 0–15% ("0%" being narrower than the resolution). The DM Z′ is simulated for g_q = 0.1–0.5. g_q = 0.5 has Γ/m = 12%, "nearly the maximum width to which this search is sensitive" (§3). Interference with QCD is neglected for its models. | 10% < Γ/m ≤ 12% (`ATLAS_GAUSSIAN_MAX`). The acceptance is that of the DM Z′ of the same width (Γ/m = 3g_q²/(2π)), interpolated between the columns at that mass. 10–12% columns exist only from 4 TeV; elsewhere undecided. Decided by ATLAS's recipe: the Breit–Wigner × q q̄ luminosity kept within 0.8–1.2 M, against the 10% Gaussian; the match σ_G = Γ/2.355 excluding alone gives a flag | 2026-10-12; before, up to Γ/m ≈ 35%, with the acceptance of the nearest g_q. 2026-10-17 (the external audit's item 18): the recipe decides; before, σ_G = Γ/2.355, too strong by 1.6–1.7 against ATLAS's own Breit–Wigner Z′ |
| **CMS tt̄** (`cms-1908.01115-ttbar`) | Γ/m = 0.5–25%; below 2.5% the shape is the 2.5% one, rescaled. One state, produced through the top-quark loop. The interference with QCD tt̄ "depends on the specific signal model, and can be significantly modified by new particles appearing in the loop" (§1). No interference between CP states. | Width tables 0.5–25% (below 0.5% as 0.5%: a state cannot be much narrower than its own tt̄ width); bracketing widths must agree. The state is undecided if its b-quark loop changes gg → Φ by more than 10% (`TOP_LOOP_TOLERANCE`), or if another state of its CP overlaps it within their widths. | tables: portal library 5; matching: 2026-10-12 |
| **Belle II invisible Z′** (`lmu-ltau-babar-belle2`) | Its limits are for "the intrinsic width Γ_Z′ … negligible compared with the experimental resolution". The recoil-mass-squared resolution is 0.06–0.23 GeV² (0.06 at 80 GeV², 0.23 at 9 GeV²). One benchmark with Γ = 0.1 M is shown separately (not in ADROIT's record). | Γ below the smallest quoted resolution, 0.06 GeV² in M², i.e. Γ < 0.03 GeV²/M (`belle2_resolution`); conservative where the resolution is larger. | 2026-10-12; before, Γ/m ≤ 5% |
| **CMS monojet, spin 0** (`cms-2107.13021-monojet-spin0`) | Limits on the DMsimp benchmark (g_q = g_χ = 1, m_DM = 1 GeV). | The narrow-width rescaling only for widths no broader than that benchmark's at the same mass. | 2026-10-06 (consistent) |
| **SModelS** (`smodels-3.2.1`) | Its efficiency maps are for on-shell (narrow) intermediate states. | Γ/m ≤ 10% for an s-channel mediator (`SMODELS_NARROW`), ADROIT's own choice after CMS's narrow-dijet statement; SModelS states no threshold. | R4; kept by the owner, 2026-10-12 |
| **2HDM+a mono-h and mono-Z** (`atlas-2108.13391-monoh`, `atlas-2111.08372-monoz`) | ATLAS generated the full processes at its benchmarks. | ADROIT's resonant approximation only for a narrow A or H (Γ/m ≤ 10%, `NARROW_2HDMA`). Beyond the benchmarks, mono-h's band and mono-Z's thresholds were calibrated with MadGraph's full gg → h a and gg → Z a, widths included ([`monoh/README.md`](monoh/README.md), [`monoz/README.md`](monoz/README.md)). | portal library 5; 2026-10-12 |
| **DarkCast's dark-photon searches** (`darkcast-dark-photon`, BaBar in `lmu-ltau-babar-belle2`) | The bump hunts and missing-mass searches assume a narrow A′ (Z′): a peak no wider than the mass resolution. Each paper's resolution and CL, with quotes and pages: [`darkcast_searches.yaml`](../adroit/constraints/data/darkcast_searches.yaml). | Per search: a bump hunt for Γ below its resolution (the smallest quoted, at every mass; NA48/2's σ = 0.067 MeV + 0.0105 m); a missing-mass search for Γ < σ(M²)/(2m), at most 10% of m; a missing-energy search (NA64 invisible, LEP) for Γ/m ≤ 10% (`DARKCAST_NARROW`); LHCb prompt, CMS and HPS, which state none for their own search, take the smaller of their collaboration's values for the same data (σ = 0.12% m, 0.7% m, 0.85 MeV). Outside its gate a search is not used either way: a point it covers is undecided unless an applicable search excludes it. BaBar's 4μ L_μ − L_τ search: Γ below its mass resolution, 1–9 MeV (arXiv:1606.03501 p. 4), the smallest at every mass, Γ < 1 MeV (`BABAR_4MU_RESOLUTION`). | per search: the owner's record review, 2026-10-13 (before, Γ/m ≤ 10% for all, 2026-10-12) |
| **CMS's summary planes** (`cms-2405.13778-*`) | The minimal width of the LHC DM Working Group's benchmarks. | Only where the model is one of those benchmarks. | R4 (consistent) |

## Why matching the width is not enough

**ZZ.** Near a broad heavy scalar, gg → H → ZZ interferes with gg → h* → ZZ and with the gg → ZZ continuum, which
changes the integrated rate by up to O(10%), more as the width grows (§5). ATLAS's large-width limits contain one
model of that interference: the H–h term with H and h of equal production and decay amplitudes. In the singlet
mixing, h₂ couples as sin θ and h as cos θ times the Standard Model's Higgs boson. Its H–h interference relative to
its own signal is therefore cot²θ times ATLAS's, which is large for the small mixings that survive the Higgs
measurements. Its interference with the continuum is not ATLAS's either. So no width makes the tables applicable to
it. A model would need a matching calculation (or ATLAS's samples' couplings) before they could be used.

**tt̄.** The resonance–QCD interference is a large part of CMS's signal, and its size depends on what runs in the
loop. A b-quark loop (a pseudoscalar at large tan β) or a second state of the same CP changes it. CMS's limit is for
one state through the top loop.

**Dijets.** ATLAS's generic limits are for Gaussian peaks. A Breit–Wigner maps onto them only near the peak, and the
acceptance for the off-peak part comes from ATLAS's own DM Z′ of the same width. There is none beyond 12%.

## Decided (the owner, 2026-10-12)

- **WW's reading of "smaller than the detector mass resolution":** Γ/m below 0.6 of the resolution. A width close
  to the resolution still broadens the reconstructed peak: for a Breit–Wigner of width Γ on a Gaussian resolution σ
  (if ATLAS's quoted resolution is σ), the peak's FWHM grows by about 25% at Γ = σ, 14% at Γ = 0.58σ and 12% at
  Γ = σ/2 (the Voigt profile). The literal reading (Γ < σ) was somewhat optimistic; half the resolution would be
  stricter than ATLAS's own use, since its benchmark radion has Γ/m = 3.2% at 3 TeV, where the resolution is about
  5.5% (Γ ≈ 0.58σ). 0.6 follows that use.
- **SModelS's 10%:** kept, stated as ADROIT's choice (after CMS's narrow-dijet statement); SModelS states no
  threshold.
- **DarkCast:** a gate per search, from each paper's mass resolution (the owner's record review, 2026-10-13; it
  replaces one Γ/m ≤ 10% for all, which still let a width above a bump hunt's few-MeV resolution through). A dark
  photon with a large dark coupling is broad (Γ ≈ α_D m/3 when its invisible decay is open). Outside its gate a
  search says nothing, neither exclusion nor allowed: a broader signal samples other masses, backgrounds and
  efficiencies, so its limit need not be weaker than the narrow one, least of all for missing energy (the owner,
  2026-10-13, after ADROIT returned "allowed" at m_A′ = 5 GeV, Γ/m = 23.6%). A point is then undecided unless a
  search that applies excludes it. Missing-mass searches (BaBar 2017, NA62) convert σ(M²) to σ_m = σ(M²)/(2m),
  capped at 10% of m where that linearisation fails (NA62 at its lowest masses). LHCb prompt, CMS and HPS give no
  number for their own search; each takes the smaller of what the same collaboration states for the same data
  (LHCb arXiv:2007.03923, CMS arXiv:2403.16134 with the search's own fit window, HPS's Møller calibration), with the
  quotes and derivations in the data file. Before (2026-10-13, earlier), they applied only to the minimal dark photon,
  which left every A′ that decays to dark matter undecided between 0.214 and 69.6 GeV. Each search also keeps its own CL: a 95% exclusion (A1, HPS, most old beam dumps) stands at
  95%; a 90% one is a native exclusion, undecided at 95%.
- **Coloured t-channel partners:** deferred to a future release ([`benchmark_limits.md`](benchmark_limits.md),
  "Known limitation").

## Records whose text stated a superseded domain

Three records signed by the owner stated the old domains. Their text was corrected (2026-10-12) with the owner's
agreement to re-sign them: the corrections changed their scientific hash, so their signatures are stale until then
(`docs/r9_record_verification.md`, section 1). The wording applied:

- **`atlas-2009.14791-zz`**, third assumption → "the width: the narrow table for Γ/m < 0.5%, the validity ATLAS
  states (§9.1.1). Tables 12–15 (Γ/m = 1, 5, 10, 15%, from 400 GeV) include the heavy scalar's interference with the
  SM Higgs boson, modelled for H and h with the same production and decay amplitudes, and with the gg → ZZ continuum
  (§5); they are applied, interpolated linearly in the width with the narrow table as 0%, only to a model that
  matches this. The singlet's h₂ does not (its H–h interference relative to the signal is cot²θ times ATLAS's), so
  Γ/m ≥ 0.5% is undecided."
- **`atlas-2004.14636-ww`**, third assumption → "applied to the singlet mixing's h₂ as the ZZ record is; narrow:
  Γ/m below the ℓνqq mass resolution, 7% at 1 TeV to 4% at 5 TeV (§5.6: 'narrow resonances, whose intrinsic widths
  are smaller than the detector mass resolution')".
- **`atlas-1910.08447-dijet-gaussian`**, first assumption → "applied to a Z′ with 10% < Γ/m ≤ 12% (ATLAS's widest DM
  Z′, g_q = 0.5): σ_G = Γ/2.355 (the Breit–Wigner's full width at half maximum), with the acceptance of the DM Z′ of
  the same width". (2026-10-17, after the external audit's item 18: decided by ATLAS's truncation recipe, the match
  a flag; validated against ATLAS's own Breit–Wigner Z′, `scripts/validate_dijet_breit_wigner.py`; re-verified
  by the owner the same day.)

The two unsigned records concerned (`cms-1908.01115-ttbar`, `lmu-ltau-babar-belle2`) were updated directly.

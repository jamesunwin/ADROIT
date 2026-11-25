# DM9 agents: Path 1 for Dirac fermion DM with axial-vector Z' mediator (isospin-odd quark couplings)

### Constraints proposed by the scout for Dirac fermion DM with axial-vector Z' mediator (isospin-odd quark couplings) (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| CMS 13 TeV monojet/mono-V, axial-vector simplified model | collider | needs_calculation | arXiv:1703.01651 (2017) | Recompute the Z' production rate and width with couplings to u and d only, instead of all quarks; the u/d sign is irrelevant at tree level. Rescale to the actual g_q and g_chi for M_Z'=2000 GeV and m_chi=100 GeV. |
| Dijet resonance plus monojet complementarity for an axial-vector mediator | collider | needs_calculation | arXiv:1503.05916 (2015) | Compute the Z' to jj rate and width with u,d-only axial couplings and the invisible branching ratio to chi chi-bar. Compare with dijet resonance limits at 2 TeV. |
| LHC DM WG visible/invisible comparison and analytic relic density | relic_density | applies_with_assumptions | arXiv:1703.05703 (2017) | standard thermal freeze-out; annihilation only via s-channel Z' to u u-bar and d d-bar; no other dark-sector states |
| Relic-abundance constraints on axial-vector simplified models | relic_density | needs_calculation | arXiv:1603.08525 (2016) | Redo the freeze-out calculation with couplings to first-generation quarks only. The paper assumes universal quark couplings, including top, which is open for m_chi=100 GeV only via off-shell channels. |
| Anomaly cancellation for an axial Z' | collider | needs_calculation | arXiv:1609.02188 (2016) | Construct an anomaly-free, gauge-invariant completion. Isospin-odd axial u/d couplings conflict with a common Q_L charge. Then compute LHC limits on the extra coloured chiral fermions expected near M_Z'. |
| s-channel internal Higgsstrahlung annihilation | indirect_detection | needs_calculation | arXiv:1605.00611 (2016) | Requires the Z' to couple to the Higgs, which the given terms omit. Compute the chi chi-bar to f f-bar h rate in a completion and compare with gamma-ray and antiproton limits. |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | model | Down-quark term carries coupling −g_q (sign in term text); no separate coupling introduced. | critical | The relative minus sign makes the axial coupling isovector, so proton and neutron SD couplings have opposite sign; flipping it to isoscalar would change nuclear interference and every SD limit. |
| A18 | validity | g_q Zp_μ ū γ^μ γ^5 u: an axial coupling to Standard Model fermions is anomalous unless the full model adds fermions (not checked: no chiral charges given) | critical | An uncancelled anomaly makes the model inconsistent and brings in Wess-Zumino terms or extra states that alter phenomenology. |
| A19 | validity | − g_q Zp_μ d̄ γ^μ γ^5 d: an axial coupling to Standard Model fermions is anomalous unless the full model adds fermions (not checked: no chiral charges given) | critical | Same as A18 for the down-quark term; an inconsistent spectrum undermines any limit derived. |
| A20 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Without the relic computation the viable couplings and the f in A4 are undetermined, so no conclusion is possible. |
| A25 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (Zp) are produced on shell) | critical | Dijet and monojet searches for a 2 TeV quark-coupled Zp are likely the strongest constraint and are not computed. |
| A29 | validity | Anomaly cancellation: flagged (g_q Zp_μ ū γ^μ γ^5 u: an axial coupling to Standard Model fermions is anomalous unless the full model adds fermions (not checked: no chiral charges given); − g_q Zp_μ d̄ γ^μ γ^5 d: an axial coupling to Standard Model fermions is anomalous unless the full model adds fermions (not checked: no chiral charges given)) | critical | This summarises A18–A19; consistency of the model is unresolved. |
| A4 | model | Relic fraction 1 and standard cosmology, as nothing else stated. | critical | A relic fraction below 1 rescales direct and indirect signals by f and f², weakening every exclusion. |
| A7 | model | left out of the model: Anomaly-cancelling states implied by axial couplings. | critical | Anomaly-cancelling fermions are required for consistency and could add collider signatures, loop couplings and annihilation channels. |
| A10 | approximation | Tree-level coefficients matched at m_Z without running. | material | Omitting running from m_Zp to m_Z misses heavy-quark-induced mixing into vector and other-flavour couplings, which can generate SI scattering that dominates over SD. |
| A13 | approximation | left out of the derivation: Loop-induced operators, including Zp-Z/photon mixing through quark loops and running from m_Zp to m_Z. | material | Loop-induced Z/photon mixing can produce coherent SI or vector couplings that strengthen direct-detection limits well beyond the tree-level SD result. |
| A16 | approximation | left out of the derivation: Anomaly-cancelling or mass-generation states. | material | Missing heavy states could add loop contributions and collider signals that change the excluded region. |
| A17 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Uncertainties in the nucleon axial charges and in DirectDM running shift SD rates at the 10–20% level. |
| A22 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | material | Duplicates A8; a nonstandard history moves the relic-target coupling. |
| A23 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | material | An isovector SD-only signal gives weak limits until computed; it becomes critical if loop-induced SI is included. |
| A24 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | Axial annihilation to light quarks is helicity-suppressed or p-wave, so indirect limits are likely weak but unverified. |
| A26 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | material | Solar capture via SD proton scattering could give competitive limits for this isovector coupling. |
| A5 | model | left out of the model: Couplings of Zp to other quarks (user states none), leptons, or Higgs. | material | Extra Zp couplings to leptons or other quarks would add dilepton and other channels, tightening collider limits and changing relic and indirect results. |
| A6 | model | left out of the model: Zp mass-generation sector and any kinetic mixing. | material | Kinetic mixing would add vector couplings to SM currents, induce SI scattering and strengthen direct-detection and dilepton limits. |
| A8 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | material | A nonstandard history would shift the coupling that gives Ωh²=0.12, and with it the viable parameter region. |
| A11 | approximation | Zp couples only to u and d quarks, per the model. | minor | This follows the stated model; it matters only if A5 fails. |
| A12 | approximation | Zp is integrated out at zero momentum transfer. | minor | With q of order MeV against a 2 TeV mediator, zero-momentum matching is accurate for direct detection. |
| A14 | approximation | left out of the derivation: Momentum-dependent corrections from Zp propagation (q^2/m_Zp^2), negligible since m_Zp = 2000 GeV. | minor | Corrections of order q²/m_Zp² are around 10⁻¹² and negligible. |
| A15 | approximation | left out of the derivation: chi-chi and q-q contact terms that do not enter the DM-quark basis. | minor | These terms are irrelevant for direct detection, although the q-q contact terms matter for collider dijets. |
| A2 | model | No stability symmetry stated; minimal Z2 with chi odd, all else even, assumed. | minor | A different stabilising symmetry would mainly allow extra decay or annihilation operators; minimal Z2 leaves the limits as derived. |
| A21 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | minor | Couplings to light quarks almost certainly thermalise chi at freeze-out; failure would require freeze-in instead. |
| A27 | validity | Flavour: applies, not yet computed (couplings single out flavours (individual fermions, or several in one term)) | minor | Flavour-diagonal u,d couplings give no tree-level FCNC; loop or anomaly effects are small. |
| A28 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | minor | The suppressed s-wave rate into light quarks makes CMB constraints weak. |
| A3 | model | Model written below EWSB (broken phase, electric charges). | minor | Writing the model below EWSB hides gauge-invariance requirements but does not shift low-energy direct-detection coefficients. |
| A30 | prior | no priors: frequentist limits | minor | Frequentist treatment affects only the interpretation of limits, not their existence. |
| A9 | approximation | Five-flavour scheme, since m_Zp = 2000 GeV is above m_Z. | minor | The five-flavour scheme is appropriate at the matching scale; leftover threshold effects are small. |

Added by the audit agent (its own, not the code's inventory):
- The chi-Zp coupling structure (vector or axial) and chi's nature (Dirac or Majorana) fix SI vs SD scattering and s- vs p-wave annihilation, yet are not inventoried.
- The Zp is assumed narrow-width with no invisible-width constraint from chi decays.
- Perturbative unitarity of the axial couplings, bounding m_chi and m_Zp/g, is assumed.
- Nuclear SD structure functions for isovector couplings are assumed, with target-dependent proton-neutron cancellation.
- The standard halo model (local density, velocity distribution) is assumed for direct detection and capture.


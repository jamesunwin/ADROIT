# DM9 agents: Path 1 for Dirac DM with axial-vector Z' mediator (quarks)

### Constraints proposed by the scout for Dirac DM with axial-vector Z' mediator (quarks) (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| CMS monojet / mono-V axial-vector mediator search (12.9 fb^-1) | collider | applies_with_assumptions | arXiv:1703.01651 (2017) | benchmark couplings g_q=0.25, g_chi=1; minimal width (Zp decays only to DM and quarks); universal quark couplings |
| Dijet resonance and monojet complementarity for axial-vector Zp | collider | applies_with_assumptions | arXiv:1503.05916 (2015) | axial-vector Zp coupled universally to quarks; total width set by the g_q and g_chi values used |
| LHC DMWG visible vs invisible Zp channel comparison | collider | applies_with_assumptions | arXiv:1703.05703 (2017) | benchmark couplings; no lepton couplings (g_l=0) |
| Relic density of axial-vector simplified model | relic_density | applies_with_assumptions | arXiv:1603.08525 (2016) | standard thermal freeze-out; only DM and quark couplings |
| Anomaly-free axial Zp completion and freeze-out | relic_density | needs_calculation | arXiv:1609.02188 (2016) | Specify an anomaly-free completion with extra chiral fermions near m_Zp. Recompute the relic density and collider limits including the new states and any lepton couplings. |
| Mass generation and gauge invariance (dark Higgs) | relic_density | needs_calculation | arXiv:1610.03063 (2016) | Include the dark Higgs scalar mediator and its annihilation channels (e.g. chi chi to Zp s). Recompute the relic density and indirect-detection rates. |
| s-channel internal Higgsstrahlung annihilation | indirect_detection | needs_calculation | arXiv:1605.00611 (2016) | Compute the s-wave chi chi to Zp* to qq h rate from the Higgs coupling of the completion. Compare the resulting gamma and antiproton spectra with Fermi-LAT and AMS limits. |
| Collider vs direct detection comparison for axial-vector mediator | collider | applies_with_assumptions | arXiv:1409.4075 (2014) | same simplified-model coupling conventions as the white paper |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | model | All six quark flavours represented by a single field q with one universal coupling g_q; electric charge left at 0 as placeholder since quark charges differ by flavour. | critical | A universal g_q with zero charge fixes the u/d/s ratios that set the spin-dependent proton/neutron split; flavour-dependent couplings could flip which target dominates and shift limits by orders of magnitude. |
| A15 | approximation | left out of the derivation: Anomaly-cancelling states and any lepton, Higgs or kinetic-mixing couplings. | critical | Omitting these couplings could miss the dominant constraints, so any eventual limits would be optimistic. |
| A17 | validity | g_q Σ_q Zp_μ q̄ γ^μ γ^5 q: an axial coupling to Standard Model fermions is anomalous unless the full model adds fermions (not checked: no chiral charges given) | critical | An anomalous axial coupling makes the theory inconsistent at high scale; the required completion adds constraints, and unitarity bounds the Zp mass. |
| A18 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | The relic abundance is not computed, so whether the thermal coupling lies in excluded regions is unknown. |
| A21 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | critical | Direct detection is not run; spin-dependent or velocity-suppressed limits are absent, so no exclusion is claimed. |
| A23 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (Zp) are produced on shell) | critical | Collider dijet and monojet searches for Zp below 3 TeV are likely the strongest bounds and are not computed. |
| A26 | validity | Anomaly cancellation: flagged (g_q Σ_q Zp_μ q̄ γ^μ γ^5 q: an axial coupling to Standard Model fermions is anomalous unless the full model adds fermions (not checked: no chiral charges given)) | critical | This duplicates A17; the flagged anomaly signals an incomplete model whose missing states alter constraints. |
| A4 | model | Relic fraction 1 and standard cosmology, since none stated. | critical | Rescaling local and relic density by a fraction below 1 weakens direct and indirect limits linearly or quadratically, which could remove exclusions. |
| A6 | model | left out of the model: Any Zp couplings to leptons, Higgs or kinetic mixing with photon/Z. | critical | Lepton couplings or kinetic mixing would add dilepton collider and electroweak constraints, likely much stronger than the quark-only bounds. |
| A7 | model | left out of the model: Loop-induced effects and gauge-anomaly-cancelling states for axial couplings. | critical | Anomaly-cancelling fermions and loops bring new states and Z-like couplings that could dominate constraints or change the viable parameter space. |
| A12 | approximation | left out of the derivation: Top-quark axial coupling: no tree-level operator in the 5-flavour basis after integrating out the top; loop and anomaly-related effects dropped. | material | Top-loop and anomaly-induced operators can generate vector or Z couplings that open coherent scattering, much stronger than spin-dependent rates. |
| A13 | approximation | left out of the derivation: Loop-induced mixing and RG running above m_Z, beyond tree-level matching at m_Zp. | material | Electroweak running mixes axial heavy-quark currents into light-quark and Z-mediated vector currents, which can raise direct-detection rates substantially. |
| A16 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Uncertainties in the nucleon axial charges Δq feed directly into spin-dependent cross sections at the tens-of-percent level. |
| A19 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | material | If chi never thermalises, freeze-out does not apply and a freeze-in regime would change the target couplings. |
| A20 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | material | This duplicates A8; a nonstandard history shifts the thermal target coupling. |
| A22 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | Indirect detection is not run; an s-wave qq̄ channel could exclude light thermal chi. |
| A24 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | material | Solar capture via spin-dependent proton scattering could give competitive limits that are currently missing. |
| A25 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | material | CMB energy injection excludes s-wave thermal chi below about 10 GeV, which is not yet applied. |
| A3 | model | No stabilizing symmetry stated: minimal Z2 with chi odd, Zp and quarks even. | material | A different stabilising symmetry could permit chi decay or extra operators, invalidating relic and indirect-detection inputs. |
| A5 | model | left out of the model: Kinetic terms and Zp mass origin (Higgs/Stueckelberg sector) not specified. | material | An unspecified Zp mass origin hides extra scalar states and longitudinal-mode growth that would add channels and unitarity bounds. |
| A8 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | material | Nonstandard expansion or entropy release would shift the coupling that gives Ωh²=0.12 by factors of a few or more. |
| A9 | approximation | g_q universal over u,d,s,c,b (and t). | material | Universality, including heavy quarks, fixes the effective nucleon axial charge; non-universal couplings would move the spin-dependent rates appreciably. |
| A10 | approximation | Matching at μ ≈ m_Zp is taken as the input at μ = m_Z, neglecting running. | minor | Neglecting running between m_Zp and m_Z gives percent to ten-percent shifts in axial Wilson coefficients for TeV mediators. |
| A11 | approximation | Zp is a real massive vector with a standard propagator. | minor | A standard propagator is valid away from resonance; a large width near 2m_chi would alter relic and collider rates. |
| A14 | approximation | left out of the derivation: Momentum-dependent terms of the Zp propagator (q²/m_Zp² corrections) and longitudinal p_μp_ν/M² pieces, which vanish or are mass-suppressed at d≤7. | minor | These corrections are suppressed by q²/m_Zp² or quark masses and are negligible at nuclear-recoil momenta. |
| A2 | model | Zp treated as a real (self-conjugate) massive vector. | minor | A complex Zp would only rescale the propagator and width normalisation, changing rates by O(1) factors. |
| A27 | prior | no priors: frequentist limits | minor | The choice of frequentist versus Bayesian treatment changes limit definitions only modestly. |

Added by the audit agent (its own, not the code's inventory):
- Chi's spin and its coupling structure to Zp (vector versus axial) are unspecified; vector×axial gives velocity-suppressed scattering, while axial×axial gives spin-dependent scattering.
- Standard halo model local density and velocity distribution assumed for direct-detection and neutrino-capture rates.
- Narrow-width Zp assumed, with no invisible or extra decay channels affecting collider and relic rates.
- Perturbative unitarity of the axial coupling (g_q·m_chi/m_Zp) assumed to be satisfied.
- Nuclear spin structure functions taken from standard shell-model calculations for spin-dependent targets.


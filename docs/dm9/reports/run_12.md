# DM9 agents: Path 1 for Majorana anapole dark matter

### Constraints proposed by the scout for Majorana anapole dark matter (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| LHC monojet limit on anapole moment | collider | applies_with_assumptions | arXiv:1311.5630 (2013) | Contact anapole EFT valid at LHC energies (heavy completion scale); Coupling fixed by thermal relic abundance |
| Thermal relic anapole coupling | relic_density | applies_with_assumptions | arXiv:1211.0503 (2012) | Standard thermal freeze-out; Photon-exchange operator is the only annihilation channel (no extra completion states) |
| CMB/BAO bound on anapole annihilation | cosmology | needs_calculation | arXiv:2102.04840 (2021) | Annihilation to e+e- at recombination |
| HL-LHC mono-Z reach on anapole moment | collider | applies_with_assumptions | arXiv:1710.11290 (2017) | EFT validity at collider energies; Projection with assumed systematics |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A12 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Nucleon inputs and tree-level matching would move the eventual direct-detection limits by tens of percent. |
| A3 | model | No 1/2 Majorana normalization factor added; coupling taken as written. | material | A factor-2 coupling ambiguity becomes a factor-4 shift in every rate, moving future limits by about 2 in the coupling. |
| A7 | approximation | Coupling taken as written for the Majorana field (no extra 1/2), giving the factor 2 against DirectDM's ½ normalization | material | Mismatch with DirectDM's ½ normalization would mis-scale direct-detection rates by 4 if handled wrongly. |
| A1 | model | No stability symmetry stated; minimal Z2 with chi odd, photon even assumed. | minor | Nothing is computed yet. Later results need a Z2 with χ odd; if χ were unstable, every relic and detection limit would be invalid. |
| A10 | approximation | left out of the derivation: Top quark: does not couple at tree level to an operator in the basis via the vector current (conserved current, no gluon operator) | minor | Omitting the top has a negligible effect on nuclear rates. It could matter for annihilation channels above m_t. |
| A11 | approximation | left out of the derivation: Photon propagation effects beyond the contact (anapole is already contact-like, q^2 cancels) | minor | This is consistent with the contact form, so no change is expected. |
| A13 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | minor | Pending. Missing channels would bias the relic-target coupling upward. |
| A14 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through photon: Γ against H to be computed) | minor | Pending. If χ is not in equilibrium, freeze-in applies and the relic coupling changes drastically. |
| A15 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | minor | This duplicates A5 and has the same effect when the relic is computed. |
| A16 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | minor | Pending. This is likely the strongest future limit. |
| A17 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | minor | Pending. Majorana anapole annihilation is p-wave, so present-day signals are velocity suppressed and limits would be weak. |
| A18 | validity | Colliders: applies, not yet computed (couples to photon; mediators above 3 TeV: contact-interaction (mono-X) searches) | minor | Pending. Mono-photon EFT limits are only valid if the UV scale exceeds the collider energy. |
| A19 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | minor | Pending. Capture depends on the velocity-dependent response, so these limits would be weak. |
| A2 | model | Phase broken since only the photon appears (below EWSB). | minor | A photon-only coupling ignores the Z and hypercharge partner. Above about m_Z this would add annihilation and collider channels, strengthening future limits. |
| A20 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | minor | The s-wave assumption is likely wrong for an anapole (p-wave), so the CMB constraint is negligible. |
| A21 | prior | no priors: frequentist limits | minor | This affects only the interpretation of the eventual frequentist limits. |
| A4 | model | Thermal freeze-out relic supplying full Ωh² = 0.12. | minor | No relic was computed. If χ is only a subcomponent, detection limits would weaken in proportion to the relic fraction. |
| A5 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | minor | A nonstandard history (low reheating or entropy release) would shift the coupling needed for Ωh²=0.12 when it is computed. |
| A6 | approximation | Covariant derivative D_μ = ∂_μ + i e Q A_μ (e>0), so ∂_μF^{μν} = e J^ν; opposite convention flips all signs | minor | The sign convention flips only overall signs. Interference with other operators is absent, so rates are unaffected. |
| A8 | approximation | Five-flavour scheme: no light mediator (photon exchange cancels to contact) | minor | The contact treatment is valid because the anapole's q² cancels the photon propagator, so there is no light-mediator enhancement. |
| A9 | approximation | left out of the derivation: Loop corrections and running from the anapole scale to m_Z | minor | Running and loop corrections would shift future rates at the percent-to-tens-of-percent level. |

Added by the audit agent (its own, not the code's inventory):
- Standard halo model (local density, Maxwellian velocities, escape speed) will set direct-detection rates.
- The anapole maps to velocity- and momentum-dependent NR operators (O8, O9), which need nuclear response functions beyond SI/SD.
- The anapole is assumed to be the only operator; Majorana fermions have no dipole moments, but other contact operators are neglected.
- Annihilation is velocity suppressed, so the freeze-out velocity expansion rather than s-wave dominance should be assumed.
- The EFT cutoff is assumed above all relevant energies (freeze-out, collider).


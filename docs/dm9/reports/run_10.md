# DM9 agents: Path 1 for Real singlet scalar Higgs-portal dark matter

### Constraints proposed by the scout for Real singlet scalar Higgs-portal dark matter (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Thermal freeze-out relic abundance for scalar Higgs portal | relic_density | applies_with_assumptions | arXiv:1804.02604 (2018) | standard thermal freeze-out; S makes up all of the dark matter |
| Planck relic density measurement | cosmology | applies_with_assumptions | arXiv:1807.06209 (2018) | standard cosmological history; thermal production via the h S S term |
| Fermi-LAT dwarf spheroidal gamma-ray limits | indirect_detection | applies_with_assumptions | arXiv:1503.02641 (2015) | s-wave annihilation dominated by WW/ZZ at m_S=100 GeV, channels weighted by Higgs-portal branching ratios; dwarf J-factors as published |
| Global fit of scalar singlet model | relic_density | applies | arXiv:1705.07931 (2017) | — |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A14 | approximation | Leading-order heavy-top relation, decoupling sign convention as stated | critical | A wrong sign in the heavy-quark gluon term would make it interfere destructively with f_Tq, suppressing σ_SI greatly and loosening limits. |
| A22 | validity | h (125.25 GeV) is below 400 GeV (4m_χ): the contact interaction does not hold at freeze-out (√s ≈ 2m_χ); the relic density needs the mediator itself | critical | The contact operator cannot give the relic density; using it would misestimate ⟨σv⟩ by large factors, so the full h propagator and widths are required. |
| A23 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Ωh² is not computed, so no coupling is fixed and no viability conclusion is possible. |
| A27 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | critical | Current xenon limits likely exclude the thermal Higgs-portal coupling at 100 GeV; until computed, viability is undetermined. |
| A33 | validity | EFT validity: flagged (h (125.25 GeV) is below 400 GeV (4m_χ): the contact interaction does not hold at freeze-out (√s ≈ 2m_χ); the relic density needs the mediator itself) | critical | This duplicates A22; the relic computation must use the full mediator, not the EFT. |
| A5 | model | Z2 S → −S as stated by user. | critical | Without exact Z2, S could decay, and the dark matter interpretation and all limits would collapse. |
| A9 | model | left out of the model: Higgs couplings to leptons, W, Z and loop-induced gluon/photon couplings. | critical | SS→WW/ZZ dominates annihilation at 100 GeV; dropping it overestimates Ωh² by a large factor and biases the inferred lam_hs upward. |
| A11 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | material | A non-standard history (low reheating, entropy release) would shift the coupling required for Ωh²=0.12 by an order of magnitude or more. |
| A17 | approximation | left out of the derivation: Loop corrections beyond the leading heavy-top threshold | material | Higher-order heavy-quark corrections move the effective gluon coupling by roughly 10–20%, shifting σ_SI similarly. |
| A21 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Nucleon sigma-term uncertainty (f_Ts especially) shifts σ_SI by up to about a factor of 2, moving direct-detection limits on lam_hs by about 40%. |
| A25 | validity | Coannihilation, resonances and thresholds: applies, not yet computed (the ZZ threshold (m_χ ≈ m_Z)) | material | At 100 GeV, just above the WW/ZZ thresholds, thermal smearing and off-shell effects change ⟨σv⟩ by tens of percent. |
| A26 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | material | This duplicates A11; any deviation rescales the relic-preferred coupling. |
| A28 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | Dwarf/γ-ray limits on WW at 100 GeV are near thermal and could exclude or constrain the model. |
| A1 | model | Sign convention: V term enters L with minus sign, giving -(lam_hs v/2) h S². | minor | Rates scale as lam_hs², so a sign flip leaves the single-portal σ_SI and relic density unchanged. |
| A10 | model | left out of the model: Higgs self-interactions. | minor | The h³ term enters only SS→hh, which is closed at this mass. |
| A12 | approximation | Five-flavour scheme since m_h = 125.25 GeV > m_Z | minor | Five-flavour matching at the m_h scale is standard; the top is integrated out separately via the heavy-top relation. |
| A13 | approximation | Quark Yukawa coupling exactly m_q/v (SM) | minor | Using MSbar versus pole masses changes light-quark couplings by percent, which is negligible after the gluon contribution dominates. |
| A15 | approximation | No S-h mixing beyond the given trilinear | minor | Z2 forbids S-h mixing, so the omission is exact. |
| A16 | approximation | left out of the derivation: Higgs couplings to leptons, W, Z (dropped in ModelSpec), so no C63e/mu/tau | minor | Lepton couplings are irrelevant to nuclear recoil, but they would add small τ/μ annihilation channels. |
| A18 | approximation | left out of the derivation: Higgs momentum dependence (q^2 << m_h^2) | minor | Recoil q² is well below m_h², so the momentum dependence is negligible. |
| A19 | approximation | left out of the derivation: Quartic hhSS term (loop-level only) | minor | The hhSS term enters direct detection only at loop level, which is negligible. |
| A2 | model | Coupling name y_q introduced for m_q/v; it is SM-fixed and mass-proportional, not universal. | minor | This is a naming choice; the mass-proportional Yukawa is standard and moves no number. |
| A20 | approximation | left out of the derivation: Higgs-photon loop couplings | minor | Photon couplings are irrelevant to σ_SI; they would add only a small γγ line for indirect detection. |
| A24 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through higgs, quark: Γ against H to be computed) | minor | For couplings large enough to give Ωh²≈0.12, S thermalises easily, so the assumption fails only for tiny lam_hs. |
| A29 | validity | Colliders: applies, not yet computed (couples to higgs, quark; mediators below 3 TeV (h) are produced on shell) | minor | Invisible h→SS is closed since m_S>m_h/2, so collider sensitivity is weak. |
| A3 | model | q stands for all six quarks; electric_charge left 0 as placeholder since charges differ per flavour. | minor | A placeholder charge of 0 does not enter tree-level Higgs exchange, but it would corrupt any photon-loop or collider use. |
| A30 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | minor | Solar-capture limits are subdominant to direct detection for spin-independent scalar couplings. |
| A31 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | minor | The Planck p_ann bound at 100 GeV lies well below thermal s-wave sensitivity and is not constraining. |
| A32 | validity | Vacuum structure: applies, not yet computed (new scalars: the potential is not yet part of the model) | minor | Vacuum stability could restrict lam_hs and λ_S, but it is unlikely to change the direct-detection conclusion. |
| A34 | prior | no priors: frequentist limits | minor | A frequentist treatment is standard; Bayesian priors would change only the presentation. |
| A4 | model | v = 246 GeV. | minor | v=246 vs 246.22 GeV shifts couplings by about 0.1%. |
| A6 | model | left out of the model: Quartic h h S S term (lam_hs/4) h² S² from H†H ⊃ h²/2. | minor | At m_S=100 GeV the SS→hh channel is closed, so the quartic barely affects relic density or direct detection; it matters only at higher mass. |
| A7 | model | left out of the model: Contribution lam_hs v²/2 to S mass (absorbed into physical 100 GeV). | minor | Absorbing this into the physical mass is consistent but fine-tunes μ_S; no observable shift. |
| A8 | model | left out of the model: S self-interaction λ_S S⁴. | minor | λ_S affects only vacuum stability and self-scattering, not annihilation or direct detection at leading order. |

Added by the audit agent (its own, not the code's inventory):
- S makes up 100% of dark matter (no rescaling of direct-detection rates by Ω_S/Ω_DM); a thermal underabundance would weaken limits.
- Standard halo model: ρ_local≈0.3 GeV/cm³ and Maxwellian velocities with v0≈220–238 km/s; this rescales limits linearly.
- S is a real scalar, so annihilation symmetry factors and coupling normalisation follow the real-field convention.
- The physical mass m_S=100 GeV is fixed at a single point; no mass scan is performed.
- Off-shell W*W (three-body) final states are neglected, as relevant near thresholds.


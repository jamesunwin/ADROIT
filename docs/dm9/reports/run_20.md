# DM9 agents: Path 1 for majorana_scalar

### Constraints proposed by the scout for majorana_scalar (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Planck relic abundance | relic_density | applies_with_assumptions | arXiv:1807.06209 (2018) | standard thermal freeze-out; no extra dark-sector states or entropy injection; S couples only as given (y_chi, g_q m_q/v) |
| ATLAS heavy-flavour plus missing ET, scalar mediator | collider | needs_calculation | arXiv:1710.11412 (2017) | Yukawa-proportional quark couplings |
| LHC mono-jet recast for Majorana DM | collider | needs_calculation | arXiv:1509.07867 (2015) | Derived for an axial-vector mediator. Recast the mono-jet analysis for gluon-fusion production of S through a top loop, with S -> chi chi. |
| Fermi-LAT dwarf spheroidals | indirect_detection | needs_calculation | arXiv:1503.02641 (2015) | b bbar final state dominant |
| Higgs-portal Majorana global fit | collider | needs_calculation | arXiv:1711.09912 (2017) | S-h mixing present |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | model | one universal coupling g_q for every quark, times m_q/v | critical | Non-universal or non-Yukawa couplings change the proton/neutron ratio and heavy-quark/gluon contributions; isospin-violating cancellation could weaken all μ_up, xenon and argon differently. |
| A11 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (S) are produced on shell) | critical | Collider limits on an on-shell mediator below 3 TeV are omitted. For light DM they could dominate the direct-detection limits. |
| A23 | data | Limit from XENONnT SR0+SR1: Xe, exposure 1.13228e+06 kg·day, window 0.01–100 keV, fidelity A | critical | XENONnT sets the strongest μ_up of 0.183 and therefore drives the conclusion. Any recast error propagates directly. |
| A7 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Not computed, so it is unknown whether the excluded couplings give Ωh² = 0.12; the overall viability conclusion could flip. |
| A10 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | An uncomputed indirect-detection limit could exclude parameter space beyond the direct-detection limits. The scalar coupling is likely p-wave suppressed, so the impact is probably small. |
| A14 | data | Limit from CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | material | Without a background model, the limit is conservative (weaker μ_up). Fidelity B recasting may also misstate the 38.4 result in either direction. |
| A15 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The halo parameters (ρ=0.3, v0=220) strongly affect low-mass limits near threshold. Higher ρ or v0 would strengthen CRESST's μ_up. |
| A17 | data | Limit from DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | material | The 50–100 keV window and lack of a background model make the 2.42 limit approximate. It is likely conservative but depends on the recast efficiency. |
| A18 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The DEAP window is sensitive to the high-velocity tail, so v_esc and v0 shift the limit appreciably at low mass. |
| A20 | data | Limit from PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | material | For bubble chambers, threshold efficiency and the lack of a background model make the recast 11.2 approximate. It is likely conservative. |
| A21 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The halo parameters shift the low-mass limit near the 2.45 keV threshold. |
| A24 | convention | XENONnT SR0+SR1: halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | material | v0=238 is inconsistent with the 220 used by the other modules, so the cross-experiment comparison is biased. XENONnT looks stronger at low mass. |
| A3 | model | left out of the model: mixing of S with the Higgs boson | material | Higgs mixing adds a Higgs-portal SI amplitude that can interfere with g_q, so all four limits could strengthen or weaken. |
| A5 | approximation | left out of the derivation: S propagation (contact limit; m_S ≫ q) | material | If m_S is near q (tens of MeV), the propagator suppresses rates at high recoil, weakening the limits. DEAP's 50–100 keV window is affected most, XENONnT least. |
| A6 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Uncertainties in the nucleon scalar matrix elements (light-quark sigma terms, heavy-quark/gluon terms) shift the SI rate by tens of percent in both directions; loop matching would add further corrections. |
| A12 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | minor | Scalar-mediated fermion annihilation is p-wave, so the CMB constraint is likely weak. It is still unverified. |
| A13 | validity | Vacuum structure: applies, not yet computed (new scalars: the potential is not yet part of the model) | minor | Vacuum stability could restrict the couplings but does not alter the recoil limits. |
| A16 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor is adequate at the low-q CaWO4 recoils of this window. |
| A19 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor for argon at q of about 100 MeV is accurate to roughly 10%. |
| A2 | model | left out of the model: couplings of S to leptons and gauge bosons | minor | Lepton or gauge couplings add little to nuclear recoil at tree level; they would mainly matter for relic and indirect constraints. |
| A22 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | minor | Shell-model SI responses for F and C should agree with Helm to within a few percent. |
| A25 | approximation | XENONnT SR0+SR1: nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor for xenon carries percent-level uncertainty at relevant q. |
| A26 | prior | no priors: frequentist limits | minor | This is a choice of frequentist interpretation; it does not change the ordering of the limits. |
| A4 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | minor | This does not affect the direct-detection μ_up values; it matters only once relic constraints are computed. |
| A8 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | minor | This affects only the relic interpretation, not the direct-detection limits. |
| A9 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | minor | This duplicates A4; it does not change the direct-detection results. |

Added by the audit agent (its own, not the code's inventory):
- The confidence level is assumed to be 90% CL as reported by each experiment; mixing it with 95% CL would rescale μ_up.
- Local DM density is assumed to be entirely χ, with no rescaling by relic fraction; underabundance would weaken all limits.
- χ is assumed to be a Dirac or Majorana fermion with a scalar–scalar SI operator; a pseudoscalar admixture would change the momentum and spin dependence.
- Detector responses and efficiencies are taken from public curves without systematic nuisance parameters.
- A single DM mass point or grid underlies the 'strongest' μ_up values; results may depend on the mass binning.


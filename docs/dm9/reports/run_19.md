# DM9 agents: Path 1 for majorana_scalar

### Constraints proposed by the scout for majorana_scalar (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Planck relic abundance | relic_density | needs_calculation | arXiv:1807.06209 (2018) | thermal freeze-out; no other DM component |
| Fermi-LAT dwarf spheroidal gamma rays | indirect_detection | needs_calculation | arXiv:1503.02641 (2015) | b bbar dominant channel, from mass-proportional couplings |
| Higgs-portal Majorana DM global fit | collider | needs_calculation | arXiv:1711.09912 (2017) | S behaves Higgs-like, with Yukawa-weighted quark couplings |
| LHC mono-jet recast method for Majorana DM | collider | needs_calculation | arXiv:1509.07867 (2015) | monojet analysis reusable for a scalar mediator |
| Singlet-fermion DM with singlet scalar mediator | relic_density | needs_calculation | arXiv:1305.3452 (2013) | S couplings to quarks arise from S-H mixing |
| White-dwarf capture in M4 | solar_capture | applies_with_assumptions | arXiv:2212.09785 (2022) | M4 dark matter density as assumed in the paper; capture-annihilation equilibrium; contact-limit SI nucleon coupling from m_S=500 GeV > m_chi |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | model | one universal coupling g_q for every quark, times m_q/v | critical | Non-universal or non-Yukawa quark couplings change the heavy-quark and gluon contributions to f_N, which can move every μ_up by large factors in either direction. |
| A11 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (S) are produced on shell) | critical | Uncomputed mono-jet and dijet bounds on an on-shell S below 3 TeV could dominate the direct-detection limits. |
| A23 | data | Limit from XENONnT SR0+SR1: Xe, exposure 1.13228e+06 kg·day, window 0.01–100 keV, fidelity A | critical | XENONnT sets the strongest limit (μ_up 0.183) and drives the conclusion; errors in its recast or efficiency move the headline result directly. |
| A7 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Not computed, so it is unknown whether the excluded parameter space is cosmologically relevant; viability could be overturned. |
| A10 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | An uncomputed indirect-detection constraint could be stronger than direct detection for scalar s-wave annihilation into quarks, changing the overall verdict. |
| A12 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | material | An uncomputed CMB bound may exclude light χ independently of direct detection. |
| A14 | data | Limit from CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | material | With no background model, the CRESST limit is conservative and too weak; at fidelity B the recast could be off by a factor of order one. |
| A15 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | v0 = 220 rather than 238 km/s, and the different v_E, changes the light-mass tail, where CRESST is sensitive, by large factors. |
| A17 | data | Limit from DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | material | A cut-and-count recast without a background model gives a conservative μ_up of 2.42; a proper likelihood would tighten it. |
| A18 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The halo convention differs from XENONnT's, so cross-experiment comparison is inconsistent at the 10–30% level, more at low mass. |
| A20 | data | Limit from PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | material | The bubble-chamber threshold and efficiency curve are approximated, so μ_up = 11.2 is uncertain by a factor of order one; the limit is conservative. |
| A21 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The halo choice shifts PICO's limit, especially near threshold. |
| A24 | convention | XENONnT SR0+SR1: halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | material | v0 = 238 km/s, unlike the other modules, gives XENONnT relatively stronger low-mass reach, which biases the ranking. |
| A3 | model | left out of the model: mixing of S with the Higgs boson | material | Higgs mixing adds a Higgs-exchange amplitude that can interfere with S exchange, raising or lowering the rate and therefore the limits. |
| A5 | approximation | left out of the derivation: S propagation (contact limit; m_S ≫ q) | material | If m_S is comparable to q (tens of MeV for Xe), propagator suppression lowers high-recoil rates and weakens the limits, most strongly for DEAP, whose window is 50–100 keV. |
| A6 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Uncertainties in nucleon matrix elements (the strange sigma term, heavy-quark matching) and loop corrections shift f_N by tens of percent, scaling all μ_up together. |
| A13 | validity | Vacuum structure: applies, not yet computed (new scalars: the potential is not yet part of the model) | minor | Vacuum stability does not change μ_up; it only restricts the parameter space. |
| A16 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | Helm form factors at CRESST's low recoils are close to 1, so the effect is small. |
| A19 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | The Helm approximation for argon in the 50–100 keV window carries an error of a few percent. |
| A2 | model | left out of the model: couplings of S to leptons and gauge bosons | minor | Lepton and gauge couplings add little to spin-independent nuclear scattering, so the direct-detection μ_up values barely move; they would matter for relic density and indirect detection. |
| A22 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | minor | Shell-model responses for F and C under spin-independent scalar coupling are reliable. |
| A25 | approximation | XENONnT SR0+SR1: nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor for Xe is accurate at the 10% level at high recoil. |
| A26 | prior | no priors: frequentist limits | minor | The frequentist choice affects interpretation, not the μ_up values. |
| A4 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | minor | Cosmological assumptions do not enter direct-detection μ_up, only the relic interpretation, which has not been computed. |
| A8 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | minor | Matters only for the freeze-out picture, not for the direct-detection limits. |
| A9 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | minor | Duplicates A4; it does not affect μ_up. |

Added by the audit agent (its own, not the code's inventory):
- Isospin-conserving f_p ≈ f_n is assumed when comparing targets; scalar Yukawa couplings give near-equal values, but violation would reorder targets.
- The confidence level and test statistic for μ_up (90% CL, Poisson or likelihood ratio) are assumed common across experiments.
- χ is assumed to make up all of the local dark matter (ρ fraction 1).
- Spin-dependent and momentum-suppressed operators are neglected; only the scalar spin-independent coupling is used.
- Detector efficiencies and energy-scale calibrations are taken from published curves without nuisance parameters.


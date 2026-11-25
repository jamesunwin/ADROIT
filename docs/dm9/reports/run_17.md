# DM9 agents: Path 1 for majorana_scalar

### Constraints proposed by the scout for majorana_scalar (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Planck relic abundance | relic_density | applies_with_assumptions | arXiv:1807.06209 (2018) | standard thermal freeze-out; chi is all of DM; no coannihilation |
| Fermi-LAT dwarf spheroidals | indirect_detection | applies_with_assumptions | arXiv:1503.02641 (2015) | b bbar final state; NFW J-factors |
| LHC scalar-mediator benchmarks (ttbar/bbbar+MET, monojet) | collider | applies_with_assumptions | arXiv:1507.00966 (2015) | S couples to quarks proportional to m_q/v (MFV); S width from y_chi, g_q only |
| LHC monojet and IceCube for Majorana DM | collider | needs_calculation | arXiv:1509.07867 (2015) | Recast monojet/dijet analysis from axial-vector to scalar Yukawa-like mediator; gg -> S via top loop dominates production. |
| Higgs-portal Majorana global fit | collider | needs_calculation | arXiv:1711.09912 (2017) | Map the 500 GeV singlet S with Yukawa-like quark couplings onto the Higgs-portal scalar-coupling likelihood. Recompute monojet and indirect likelihoods. |
| White-dwarf capture in M4 | solar_capture | applies_with_assumptions | arXiv:2212.09785 (2022) | M4 DM density as in paper; capture-annihilation equilibrium; SI scalar scattering |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | model | one universal coupling g_q for every quark, times m_q/v | critical | Non-universal or non-Yukawa couplings change the proton/neutron ratio and heavy-quark/gluon contribution, shifting every μ_up and possibly the experiment ordering. |
| A11 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (S) are produced on shell) | critical | Collider mono-jet or dijet searches for S below 3 TeV could exclude parameter space far below the XENONnT μ_up 0.183, and they also test the contact assumption. |
| A23 | data | Limit from XENONnT SR0+SR1: Xe, exposure 1.13228e+06 kg·day, window 0.01–100 keV, fidelity A | critical | XENONnT sets the strongest limit (0.183), so the claimed exposure and window drive the headline conclusion. |
| A7 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Without the relic computation, viability at Ωh²=0.12 is unknown, and rescaling local density by relic fraction would weaken limits. |
| A10 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | Scalar exchange to quarks is p-wave, so indirect limits are likely weak but remain unchecked. |
| A14 | data | Limit from CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | material | A background-free reconstruction with fidelity B over the 30 eV threshold likely mis-states the 38.4 limit by an O(1) factor, depending on mass. |
| A15 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | v0=220 with v_E=232 is inconsistent with XENONnT's 238, so low-mass CRESST sensitivity shifts in an inconsistent comparison. |
| A17 | data | Limit from DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | material | The 50–100 keV window reconstruction without a background model may misrepresent the 2.42 limit, especially near the threshold. |
| A18 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The differing v0 from XENONnT biases the DEAP versus XENONnT comparison by roughly 5–15%. |
| A20 | data | Limit from PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | material | A bubble-chamber threshold reconstruction with fidelity B makes the 11.2 limit uncertain at O(1) level, mainly from fluorine efficiency. |
| A24 | convention | XENONnT SR0+SR1: halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | material | v0=238 versus 220 elsewhere shifts XENONnT relative strength, mostly at low mass. |
| A3 | model | left out of the model: mixing of S with the Higgs boson | material | Higgs mixing adds an interfering Higgs-mediated scalar amplitude, strengthening or weakening the effective coupling and scaling all μ_up. |
| A5 | approximation | left out of the derivation: S propagation (contact limit; m_S ≫ q) | material | A light S gives q²-dependent suppression that changes rates, most for heavy targets like Xe and Ar at high recoil, so μ_up rises. |
| A6 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Nucleon sigma terms and heavy-quark/gluon matching uncertainties of tens of percent scale the SI coupling and move all μ_up together. |
| A12 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | minor | Scalar exchange gives p-wave Dirac-like suppression, so CMB injection is likely negligible but unverified. |
| A13 | validity | Vacuum structure: applies, not yet computed (new scalars: the potential is not yet part of the model) | minor | The scalar potential does not affect the limits and only restricts the model's consistency. |
| A16 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor is adequate for SI recoils on light CaWO4 targets at low recoil. |
| A19 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor for Ar SI scattering is a standard choice with percent-level effects. |
| A2 | model | left out of the model: couplings of S to leptons and gauge bosons | minor | Lepton or gauge couplings barely affect nuclear recoil limits but would add annihilation channels and collider constraints. |
| A21 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo choice affects PICO modestly, and PICO is not the strongest limit. |
| A22 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | minor | The shell-model SI response for F and C has little effect on the SI-dominated rate. |
| A25 | approximation | XENONnT SR0+SR1: nuclear responses helm (spin-dependent: shell_model) | minor | Helm for Xe SI scattering is standard, giving percent-level shifts at high recoil. |
| A26 | prior | no priors: frequentist limits | minor | A frequentist treatment is standard, and the CL choice scales μ_up modestly. |
| A4 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | minor | Cosmology does not enter the direct-detection μ_up; it matters only once the relic density is computed. |
| A8 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | minor | Failure of thermalization would change the relic estimate, not the direct-detection limits. |
| A9 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | minor | This duplicates A4 and does not affect the quoted μ_up values. |

Added by the audit agent (its own, not the code's inventory):
- The DM is a fermion whose scalar coupling to S gives an unsuppressed SI operator, with no velocity-suppressed pseudoscalar admixture.
- The local DM density is fixed at 0.3 GeV/cm³ for all experiments, ignoring the 0.4 GeV/cm³ alternative and any relic underabundance.
- Isospin-conserving nucleon couplings are implied by the Yukawa-like structure, with no interference treatment beyond DirectDM.
- Detector energy response, efficiencies and quenching models are reproduced from public curves without systematic nuisance parameters.
- A single DM mass and coupling point is used to define 'strongest μ_up' without scanning the mass dependence.


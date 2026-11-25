# DM9 agents: Path 1 for majorana_scalar

### Constraints proposed by the scout for majorana_scalar (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Planck relic abundance | relic_density | applies_with_assumptions | arXiv:1807.06209 (2018) | standard thermal freeze-out; chi is all of the dark matter; no extra annihilation channels beyond S-mediated chi chi -> q qbar |
| ATLAS monojet, scalar simplified model | collider | needs_calculation | arXiv:2102.10874 (2021) | Recast the jet+MET limit to a 500 GeV scalar with Yukawa-ordered g_q m_q/v couplings, mainly gluon fusion via a top loop. Include the Majorana width and cross-section factor for S -> chi chi. |
| Fermi-LAT dwarf spheroidals | indirect_detection | needs_calculation | arXiv:1503.02641 (2015) | Compute the late-time <sigma v>(b bbar) of the p-wave Majorana annihilation, about v^2 ~ 1e-6 suppressed. Compare with the b bbar limit at 100 GeV. |
| Higgs-portal Majorana global fit | relic_density | needs_calculation | arXiv:1711.09912 (2017) | Translate the Higgs-portal scalar-coupling results to a separate 500 GeV S with g_q m_q/v couplings. Rescale the relic and collider rates by the mediator propagator and couplings. |
| Singlet fermion with scalar mediator | relic_density | needs_calculation | arXiv:1305.3452 (2013) | Adapt the Dirac singlet-fermion relic computation to Majorana chi: halve the identical-particle counting and keep the p-wave scaling. Map the singlet-Higgs mixing to g_q. |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | model | one universal coupling g_q for every quark, times m_q/v | critical | Non-universal or non-Yukawa quark couplings change the nucleon couplings (heavy-quark and strange content), which could move every μ_up and the relative ranking of the targets. |
| A23 | data | Limit from XENONnT SR0+SR1: Xe, exposure 1.13228e+06 kg·day, window 0.01–100 keV, fidelity A | critical | XENONnT drives the strongest bound (μ_up=0.183 below 1); a likelihood mis-reproduction or efficiency error could flip whether the point is excluded. |
| A5 | approximation | left out of the derivation: S propagation (contact limit; m_S ≫ q) | critical | If m_S is near or below the momentum transfer q (tens of MeV), the rates are suppressed at high recoil, which weakens the limits, especially for DEAP-3600's 50–100 keV window and heavy targets. |
| A11 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (S) are produced on shell) | material | Colliders could exclude the parameter point regardless of the direct limits, which would change the overall verdict. |
| A14 | data | Limit from CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | material | Without a background model the limit is a conservative Poisson or optimum-interval limit, so μ_up=38.4 could be overstated; the small exposure dominates. |
| A15 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | For a light-mass-sensitive experiment, the halo tail parameters (v_esc, v_E) strongly affect the rate near threshold, which shifts μ_up. |
| A17 | data | Limit from DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | material | The 50–100 keV window and lack of a background model make the limit conservative; the true μ_up would be lower with backgrounds included. |
| A20 | data | Limit from PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | material | The bubble-chamber threshold treatment and missing background model affect μ_up=11.2, and fluorine is weak for SI couplings. |
| A24 | convention | XENONnT SR0+SR1: halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | material | v₀=238 differs from the 220 used by the other modules, so the experiments are compared under inconsistent halos and rates shift by about 10–30% at low mass. |
| A3 | model | left out of the model: mixing of S with the Higgs boson | material | S–Higgs mixing would add a Higgs-mediated SI amplitude that can interfere with the S exchange, raising or lowering all rates. |
| A6 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Nucleon inputs (σ_πN, strange content) and loop matching (the heavy-quark gluon term) can shift f_N by tens of percent, which scales every μ_up. |
| A10 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | minor | Indirect detection is not computed, so it cannot change the direct μ_up values, but it could exclude the model independently. |
| A12 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | minor | Scalar exchange to quarks is mostly p-wave, so the CMB bound likely adds little. |
| A13 | validity | Vacuum structure: applies, not yet computed (new scalars: the potential is not yet part of the model) | minor | Vacuum stability is unrelated to the recoil limits. |
| A16 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor is adequate for O, Ca and W at low q, so the change is a few percent. |
| A18 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The SHM choice changes the heavy-mass rate by about 10%. |
| A19 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor is reliable for Ar at these q values. |
| A2 | model | left out of the model: couplings of S to leptons and gauge bosons | minor | Lepton and gauge-boson couplings barely touch nuclear recoil limits at tree level, though loop photon or gluon couplings could shift the rates slightly. |
| A21 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The SHM choice changes the rate modestly. |
| A22 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | minor | Shell-model SI responses for F and C differ little from Helm. |
| A25 | approximation | XENONnT SR0+SR1: nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor for Xe is standard, with percent-level differences. |
| A26 | prior | no priors: frequentist limits | minor | The frequentist limits are well defined; the CL and test-statistic conventions shift μ_up slightly. |
| A4 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | minor | Cosmology does not enter the direct-detection μ_up values; it matters only for the relic-viability statements. |
| A7 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | minor | The relic density is uncomputed; this does not alter the quoted limits but leaves viability open. |
| A8 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | minor | Thermalization is unverified; it does not alter the direct limits. |
| A9 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | minor | This duplicates A4 and has no effect on the direct-detection numbers. |

Added by the audit agent (its own, not the code's inventory):
- Elastic scattering is assumed with no isospin violation beyond Yukawa-weighted couplings (f_p≈f_n).
- A fixed confidence level of 90% is presumably used for all μ_up values.
- The DM mass and coupling benchmark point are held fixed and not profiled.
- Detector efficiency and energy-response curves are taken from published tables without nuisance parameters.
- Interference with momentum- or velocity-suppressed operators generated at loop level is neglected.


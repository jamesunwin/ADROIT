# DM9 agents: Path 2 on LZ extended window (2026)

## Variants (DM9)

- L12s@4000: the best-fit coupling is above 4π
- O01s@1000,d=350: excluded by icecube-1612.05949-sd, icecube-1612.05949-si

| variant | deformation | reason | Z_joint | AIC (parent's) | joined |
|---|---|---|---|---|---|
| L12s@4000~O10 | nonrelativistic limit to O10 | Trigger: L12s@4000 best-fit coupling >4π. O10 (∝q/m_N) is less suppressed than O12 (∝v⊥) or O15 (∝q²v⊥), so it could fit the events with a perturbative coupling. | 3.12 | -5.76 (-10.33) | no |
| O01s@1000,d=350~d400 | splitting 400 keV | Trigger: IceCube [unverified reference removed] exclusion. A 400 keV splitting suppresses solar capture on light nuclei more than 350 keV while staying closer to the current best fit. | 0.00 | 4.00 (-10.14) | no |
| O01s@1000,d=350~d450 | splitting 450 keV | Trigger: IceCube [unverified reference removed] SD/SI exclusion. Raising the splitting from 350 to 450 keV raises the minimum speed, suppressing solar capture on light nuclei and weakening the IceCube limits. | 0.00 | 4.00 (-10.14) | no |

### Constraints proposed by the scout for O01v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Super-K/IceCube solar neutrinos, inelastic capture | solar_capture | needs_calculation | arXiv:2308.16134 (2023) | hadrophilic annihilation channel; capture-annihilation equilibrium in the Sun; symmetric Dirac population (chi chibar annihilation) |
| Halo-independent inelastic solar capture bound | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | annihilation channel to neutrinos; equilibrium in the Sun |
| Solar capture at TeV mass and sub-MeV splitting (LZ-event context) | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | W+W- or similar annihilation channel; equilibrium in the Sun; Standard Halo Model or simulated halo |
| Suppressed solar annihilation caveat for inelastic capture | solar_capture | needs_calculation | arXiv:2609.10636 (2026) | specific completion fixing annihilation and orbital thermalisation |
| White-dwarf capture of inelastic DM in M4 | indirect_detection | needs_calculation | arXiv:1001.2737 (2010) | annihilation to SM particles; primordial DM halo for M4 with high core density |
| Neutron-star heating by inelastic DM | indirect_detection | needs_calculation | arXiv:2301.08767 (2023) | future observation of cold old neutron stars |

### Constraints proposed by the scout for O04v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar-capture neutrino bounds on endothermic spin-dependent inelastic DM | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; annihilation channel to neutrino-producing final states (e.g. W+W-, tau+tau-) |
| NR-EFT neutrino-telescope limits on O4 couplings | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium in the Sun; specified annihilation channel |
| Solar SD dark matter-neutron capture constraints | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | annihilation channel choice; equilibrium in the Sun |
| Solar-capture neutrino tension for TeV inelastic DM with delta of a few hundred keV | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | higgsino-like annihilation to W+W-; Standard Halo Model or simulated halo |

### Constraints proposed by the scout for O04v@4000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Inelastic solar capture: endothermic SD bounds | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | Capture-annihilation equilibrium in the Sun; Neutrino-producing annihilation channel specified |
| Solar SD neutron-capture constraints | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | Equilibrium in the Sun; Annihilation channel chosen |
| NREFT neutrino-telescope limits on O4 | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | Equilibrium in the Sun; Annihilation channel chosen |
| Inelastic solar-capture neutrinos (DUNE, Super-K) | solar_capture | needs_calculation | arXiv:2308.16134 (2023) | Hadrophilic annihilation; Equilibrium in the Sun |
| IceCube SD-proton limits via micrOMEGAs | solar_capture | needs_calculation | arXiv:1507.07987 (2015) | Annihilation channel specified; Equilibrium in the Sun |
| Neutron-star heating by inelastic DM | cosmology | needs_calculation | arXiv:2301.08767 (2023) | Neutron-star temperature observations; Equilibrium heating |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | data | The search: LZ extended window (2026): Xe, exposure 1.0362e+06 kg·day, window 5.4–269.9 keV, fidelity B, no background model of its own | critical | The module has no background model, so the 0.0015-event background is taken on trust; a realistic background of order 0.1 events would collapse Z=3.50 for a single event. |
| A2 | convention | LZ extended window (2026): halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | critical | At d=300–350 keV only the high-velocity tail scatters, so v₀, v_esc and ρ set the rate and the coupling; A23–A33 show couplings shifting ×0.3 to ×130. |
| A25 | validity | halo (v_esc = 500 km/s): no events at all (for O04v@1000,d=350, O04v@400,d=300) | critical | For v_esc=500 km/s the O04 candidates predict zero events, so they exist only for a fast-tail halo and their ranking is not robust. |
| A30 | validity | coupling: the best fit needs 18 times the unit coupling of LZ extended window (2026)'s convention, above 4π (for L12s@4000) | critical | L12s@4000 needs a non-perturbative coupling of 18× unit, above 4π, so it should be dropped from the viable ranking. |
| A4 | statistics | an extended unbinned likelihood in recoil energy, with the module's resolution; the signal strength is the only free parameter of a candidate (k = 1) | critical | With one event, an unbinned fit with k=1 makes every candidate fit almost equally well; a mis-modelled resolution or energy scale moves the single event's likelihood. |
| A5 | statistics | global significance: one-event closed form (expected background 0.0015 events), toys as a check | critical | Z=3.50 follows from Poisson p(≥1|0.0015); the closed form ignores the look-elsewhere effect over the model space and depends entirely on the background value. |
| A6 | model | the model space: the search's published model space, or every operator and Lagrangian card in each isospin over the mass grid, with splittings [0.0] keV | critical | The splittings listed as [0.0] keV conflict with candidates at d=300/350; an undocumented scan over splitting inflates the trials factor and lowers the global Z. |
| A11 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | Its v₀=220 km/s is inconsistent with LZ's 238 km/s, so the combination is not halo-consistent; the effect is small given CRESST's insensitivity. |
| A16 | data | Null experiment: PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | material | The F target with a window up to 300 keV can constrain the O04 spin-dependent candidates if kinematics allow, which would disfavour them. |
| A17 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The halo mismatch alters PICO's inelastic reach, which depends on the high-velocity tail. |
| A18 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | material | The F spin structure functions set the O04 constraints. |
| A19 | data | Null experiment: DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | material | The Ar 50–100 keV window may probe d=300 keV at high mass, which could add tension with the O01 candidates. |
| A20 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The halo inconsistency with LZ shifts DEAP's inelastic tail rate. |
| A23 | validity | halo (v_esc = 500 km/s): Z -0.01, best-fit coupling ×36 (for O01v@1000,d=350) | material | The coupling rises ×36 for v_esc=500 km/s while Z barely changes, so the coupling is halo-dominated but the significance is stable. |
| A24 | validity | halo (v_esc = 600 km/s): Z -0.05, best-fit coupling ×0.48 (for O01v@1000,d=350) | material | The coupling halves for v_esc=600 km/s; the significance is stable. |
| A26 | validity | halo (v_esc = 600 km/s): Z -0.09, best-fit coupling ×0.35 (for O04v@1000,d=350) | material | The coupling shifts ×0.35 for v_esc=600 km/s; the ranking holds. |
| A27 | validity | halo (v_esc = 500 km/s): Z +0.07, best-fit coupling ×4.9 (for O04v@4000,d=350) | material | The coupling shifts ×4.9 for v_esc=500 km/s; the ranking holds. |
| A28 | validity | halo (v_esc = 500 km/s): Z +0.06, best-fit coupling ×20 (for O01v@400,d=300) | material | The coupling shifts ×20 for v_esc=500 km/s; the ranking holds. |
| A29 | validity | halo (v_esc = 600 km/s): Z -0.16, best-fit coupling ×0.43 (for O01v@400,d=300) | material | The coupling shifts ×0.43 for v_esc=600 km/s, with a slight drop in Z. |
| A3 | approximation | LZ extended window (2026): nuclear responses haxton_2022 (spin-dependent: haxton_2022) | material | The haxton_2022 Xe responses at the high momentum transfer of inelastic scattering set the O01/O04 rates and so shift the ΔAIC ordering, which is within 1. |
| A31 | validity | halo (v_esc = 600 km/s): Z -0.07, best-fit coupling ×0.46 (for O04v@400,d=300) | material | The coupling shifts ×0.46 for v_esc=600 km/s. |
| A32 | validity | halo (v_esc = 500 km/s): Z +0.10, best-fit coupling ×1.3e+02 (for O01s@1000,d=350) | material | A coupling of ×130 for v_esc=500 km/s approaches non-perturbative values, making O01s fragile. |
| A34 | validity | planck-2018-omega: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the annihilation cross-sections follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Relic abundance is unchecked, so a cosmological exclusion could remove candidates. |
| A35 | validity | cms-2405.13778-V1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | The collider bound is unapplied, so it could exclude candidates once a mediator is specified. |
| A36 | validity | cms-2405.13778-A1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A35: the collider bound could exclude candidates once a mediator is specified. |
| A37 | validity | cms-2405.13778-V2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A35: the collider bound could exclude candidates once a mediator is specified. |
| A38 | validity | cms-2405.13778-A2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A35: the collider bound could exclude candidates once a mediator is specified. |
| A40 | approximation | icecube-1612.05949-sd: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | If capture and annihilation are not in equilibrium, the neutrino flux and constraint are weaker; assuming equilibrium overstates the tension. |
| A41 | approximation | icecube-1612.05949-sd: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | With a large splitting, captured DM may not thermalize, so the constraint is likely overstated. |
| A42 | approximation | icecube-1612.05949-sd: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Solar capture of inelastic DM depends strongly on the halo tail, so the constraint is uncertain. |
| A45 | approximation | icecube-1612.05949-si: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A40: assuming equilibrium overstates the tension. |
| A46 | approximation | icecube-1612.05949-si: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A41: the constraint is likely overstated. |
| A47 | approximation | icecube-1612.05949-si: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A42: the constraint is uncertain because it depends on the halo tail. |
| A49 | validity | fermi-1503.02641-dsph: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which ⟨σv⟩ today and its final states follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | The indirect-detection limit is unapplied, so it could exclude candidates once a completion is specified. |
| A7 | approximation | candidates closer than 20 events (Jeffreys distance) form one degeneracy class; only the best of each of the leading classes is carried on | material | With one event the 20-event Jeffreys threshold merges nearly all candidates; pruning to class leaders may hide equally good alternatives. |
| A8 | statistics | the tournament ranks by AIC = −Z_joint² + 2k; within ΔAIC ≤ 2 candidates are indistinguishable | material | All ranked candidates lie within ΔAIC ≤ 1, so the ranking is uninformative; no model is preferred. |
| A9 | statistics | null experiments enter as limit-equivalent likelihoods; their tension with the signal is the parameter goodness of fit | material | Limit-equivalent null likelihoods are approximate; at high splitting, Xe-heavy kinematics leave the light targets nearly blind, so the tension is weak either way. |
| A10 | data | Null experiment: CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | minor | A light CaWO4 target with a 16 keV window cannot excite a 300 keV splitting, so it barely constrains the candidates. |
| A12 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor is irrelevant where the target is kinematically blind. |
| A13 | data | Null experiment: CDMSlite Run 2: Ge, exposure 70.1 kg·day, window 0.308763–7.76269 keV, fidelity B, no background model of its own | minor | Ge with a window below 8 keV is essentially blind to splittings of 300–350 keV. |
| A14 | convention | CDMSlite Run 2: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo mismatch with LZ has a negligible effect because CDMSlite is insensitive here. |
| A15 | approximation | CDMSlite Run 2: nuclear responses helm (spin-dependent: klos) | minor | The choice of form factor hardly matters for a target that sees no rate. |
| A21 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | The Helm form factor for Ar is adequate at modest momentum transfer. |
| A22 | prior | no priors: profile-likelihood fits and frequentist limits throughout | minor | A frequentist treatment throughout is consistent; there is no prior dependence. |
| A33 | validity | halo (v_esc = 600 km/s): Z -0.19, best-fit coupling ×0.28 (for O01s@1000,d=350) | minor | The coupling shifts ×0.28 for v_esc=600 km/s, with a small change in Z. |
| A39 | approximation | icecube-1612.05949-sd: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Using the weakest channel makes the solar constraint conservative, so it favours survival. |
| A43 | approximation | icecube-1612.05949-sd: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Solar model composition changes capture by tens of percent. |
| A44 | approximation | icecube-1612.05949-si: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The choice of weakest channel is conservative. |
| A48 | approximation | icecube-1612.05949-si: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As A43: solar model composition changes capture by tens of percent. |

Added by the audit agent (its own, not the code's inventory):
- A single event at the end of an extended window is assumed to be a nuclear recoil, not leakage from electron recoils or an accidental-coincidence event.
- The LZ efficiency and energy scale up to 270 keV are assumed known for the extended window.
- Inelastic kinematics are assumed to be up-scattering only, with no de-excitation signal or excited-state population.
- The trials factor from scanning mass, splitting and operator is assumed absent from the closed-form global Z.
- Each candidate is assumed to be a single isospin-fixed operator with no interference between operators.


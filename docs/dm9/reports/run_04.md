# DM9 agents: Path 2 on LZ extended window (2026)

## Variants (DM9)

- L12s@4000: the best-fit coupling is above 4π
- O01s@1000,d=350: excluded by icecube-1612.05949-sd, icecube-1612.05949-si

| variant | deformation | reason | Z_joint | AIC (parent's) | joined |
|---|---|---|---|---|---|
| L12s@4000~O10 | nonrelativistic limit to O10 | Trigger: L12s@4000 coupling >4π. Reducing it to O10 alone drops more suppressed terms, so the rate per unit coupling could rise and lower the best-fit coupling. | 3.12 | -5.76 (-10.33) | no |
| L12s@4000~O12 | nonrelativistic limit to O12 | Trigger: L12s@4000 coupling >4π. O12 has only velocity suppression and probes different nuclear responses, so it might need a smaller coupling. | 2.04 | -0.16 (-10.33) | no |
| O01s@1000,d=350~d300 | splitting 300 keV | Trigger: O01s@1000,d=350 is excluded by IceCube [unverified reference removed] SI/SD. A 300 keV splitting further suppresses scattering on light solar nuclei, so solar capture could drop. | 3.20 | -6.21 (-10.14) | no |
| O01s@1000,d=350~d400 | splitting 400 keV | Trigger: same IceCube exclusion. A 400 keV splitting suppresses capture on solar nuclei more, though Xe kinematics, with v_min near 790 km/s, are marginal. | 0.00 | 4.00 (-10.14) | no |

### Constraints proposed by the scout for O01v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture of inelastic DM with neutrino-telescope limits | solar_capture | applies_with_assumptions | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; annihilation channel to neutrino-producing final states (e.g. W+W-, b bbar); endothermic splitting of 350 keV |
| Solar-capture neutrino tension for ~TeV inelastic DM at δ~500 keV | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | equilibrium in the Sun; higgsino annihilation channels |
| Inelastic DM capture in M4 white dwarfs | solar_capture | needs_calculation | arXiv:1001.2737 (2010) | primordial formation of the M4 globular cluster in a DM halo; annihilation to SM particles; assumed DM density in the M4 core |

### Constraints proposed by the scout for O04v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture of inelastic SD dark matter vs neutrino telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; specified annihilation channel |
| Solar SD dark matter-neutron constraints | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | equilibrium in the Sun; annihilation channel choice |
| NR-EFT operator limits from neutrino telescopes | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium in the Sun; annihilation channel |
| Solar-capture neutrino tension for TeV inelastic dark matter | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | equilibrium in the Sun; W+W- or higgsino-like annihilation |

### Constraints proposed by the scout for O04v@4000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture of endothermic inelastic SD dark matter | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; annihilation channel to neutrino-producing final states |
| Solar SD neutron-scattering capture limits | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | equilibrium; specified annihilation channel |
| IceCube SD-proton limits via micrOMEGAs | solar_capture | needs_calculation | arXiv:1507.07987 (2015) | equilibrium; annihilation channel |
| Neutrino-telescope limits on NR operator O4 | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium; annihilation channel |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | data | The search: LZ extended window (2026): Xe, exposure 1.0362e+06 kg·day, window 5.4–269.9 keV, fidelity B, no background model of its own | critical | Without its own background model, the 0.0015-event expectation is assumed; any underestimated high-energy NR or ER leakage background lowers Z sharply. |
| A25 | validity | halo (v_esc = 500 km/s): no events at all (for O04v@1000,d=350, O04v@400,d=300) | critical | At v_esc=500 km/s O04v@1000/400 predict zero events, so these candidates vanish under plausible halo variation. |
| A5 | statistics | global significance: one-event closed form (expected background 0.0015 events), toys as a check | critical | One event on b=0.0015 gives p≈1.5e-3 (Z≈3.0) before trials, so the reported 3.50 depends on how the closed form and look-elsewhere are applied. |
| A6 | model | the model space: the search's published model space, or every operator and Lagrangian card in each isospin over the mass grid, with splittings [0.0] keV | critical | The stated splittings of [0.0] keV contradict candidates at d=300–350 keV; if the space or its trials count is misdescribed, the global Z and ranking are unreliable. |
| A2 | convention | LZ extended window (2026): halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | material | For d≈300–350 keV only the velocity tail scatters, so v₀=238 against 220 km/s shifts the required coupling strongly while barely moving the one-event Z. |
| A23 | validity | halo (v_esc = 500 km/s): Z -0.01, best-fit coupling ×36 (for O01v@1000,d=350) | material | At v_esc=500 km/s Z is stable but the coupling rises ×36, showing the leading candidate's viability is halo-tail dominated. |
| A27 | validity | halo (v_esc = 500 km/s): Z +0.07, best-fit coupling ×4.9 (for O04v@4000,d=350) | material | A coupling shift of ×4.9 shows strong halo dependence for O04v@4000. |
| A28 | validity | halo (v_esc = 500 km/s): Z +0.06, best-fit coupling ×20 (for O01v@400,d=300) | material | A coupling shift of ×20 makes O01v@400 halo-tail dependent. |
| A3 | approximation | LZ extended window (2026): nuclear responses haxton_2022 (spin-dependent: haxton_2022) | material | Xe form-factor suppression at tens to hundreds of keV recoil rescales the best-fit coupling and can reorder O01 against O04 within the ΔAIC≤2 band. |
| A30 | validity | coupling: the best fit needs 18 times the unit coupling of LZ extended window (2026)'s convention, above 4π (for L12s@4000) | material | A coupling above 4π makes L12s@4000 non-perturbative, so it should be dropped from the ranking. |
| A4 | statistics | an extended unbinned likelihood in recoil energy, with the module's resolution; the signal strength is the only free parameter of a candidate (k = 1) | material | With one event the unbinned spectral shape carries little information, so mass and splitting are poorly constrained and the ranking is largely arbitrary. |
| A40 | approximation | icecube-1612.05949-sd: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | For inelastic capture, equilibrium may fail, weakening the IceCube constraint and favouring survival. |
| A41 | approximation | icecube-1612.05949-sd: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | If the splitting prevents thermalisation, the annihilation rate drops and the limit weakens. |
| A45 | approximation | icecube-1612.05949-si: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As for A40. |
| A46 | approximation | icecube-1612.05949-si: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As for A41. |
| A8 | statistics | the tournament ranks by AIC = −Z_joint² + 2k; within ΔAIC ≤ 2 candidates are indistinguishable | material | Every listed candidate has ΔAIC≤1.02, so the ranking carries no discriminating power, and AIC from Z² is crude for k=1. |
| A10 | data | Null experiment: CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | minor | For Ca/O/W the reduced-mass kinematics and the 16 keV window give essentially no inelastic reach at d≥300 keV, so CRESST data barely matter. |
| A11 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo mismatch with A2 (220 against 238 km/s) is inconsistent, but CRESST sensitivity here is near zero anyway. |
| A12 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | Helm against shell-model responses are irrelevant where no kinematic reach exists. |
| A13 | data | Null experiment: CDMSlite Run 2: Ge, exposure 70.1 kg·day, window 0.308763–7.76269 keV, fidelity B, no background model of its own | minor | The Ge maximum splitting (~240 keV at 1 TeV) and the 7.8 keV window give no reach, so CDMSlite cannot constrain these candidates. |
| A14 | convention | CDMSlite Run 2: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The inconsistent halo against A2 is unimportant given no reach. |
| A15 | approximation | CDMSlite Run 2: nuclear responses helm (spin-dependent: klos) | minor | Response choice is irrelevant for these candidates. |
| A16 | data | Null experiment: PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | minor | F/C targets are too light to excite d≈350 keV, so PICO adds negligible tension. |
| A17 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo mismatch is immaterial given no reach. |
| A18 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | minor | Spin responses are irrelevant without kinematic access. |
| A19 | data | Null experiment: DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | minor | Ar kinematics (~135 keV maximum splitting) exclude d≥300 keV, so DEAP does not constrain these candidates. |
| A20 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo mismatch is immaterial. |
| A21 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | Response choice is immaterial. |
| A22 | prior | no priors: profile-likelihood fits and frequentist limits throughout | minor | A frequentist treatment is consistent; adopting priors would not change Z. |
| A24 | validity | halo (v_esc = 600 km/s): Z -0.05, best-fit coupling ×0.48 (for O01v@1000,d=350) | minor | At v_esc=600 km/s the coupling halves and Z falls only 0.05. |
| A26 | validity | halo (v_esc = 600 km/s): Z -0.09, best-fit coupling ×0.35 (for O04v@1000,d=350) | minor | The coupling shifts ×0.35 with a small Z change. |
| A29 | validity | halo (v_esc = 600 km/s): Z -0.16, best-fit coupling ×0.43 (for O01v@400,d=300) | minor | The Z shift of -0.16 is small. |
| A31 | validity | halo (v_esc = 600 km/s): Z -0.07, best-fit coupling ×0.46 (for O04v@400,d=300) | minor | This applies to a candidate outside the top six and has a small effect. |
| A32 | validity | halo (v_esc = 500 km/s): Z +0.10, best-fit coupling ×1.3e+02 (for O01s@1000,d=350) | minor | For O01s, not in the top ranks, the coupling rises ×130, which would likely make it implausible. |
| A33 | validity | halo (v_esc = 600 km/s): Z -0.19, best-fit coupling ×0.28 (for O01s@1000,d=350) | minor | This is a small Z shift for a non-leading candidate. |
| A34 | validity | planck-2018-omega: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the annihilation cross-sections follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The relic density is unassessed, so viability is open but Z is unaffected. |
| A35 | validity | cms-2405.13778-V1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The collider check is not concluded, leaving candidates unconstrained rather than excluded. |
| A36 | validity | cms-2405.13778-A1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As for A35. |
| A37 | validity | cms-2405.13778-V2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As for A35. |
| A38 | validity | cms-2405.13778-A2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As for A35. |
| A39 | approximation | icecube-1612.05949-sd: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The weakest b b̄ channel is conservative; harder channels could exclude candidates. |
| A42 | approximation | icecube-1612.05949-sd: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Halo uncertainty enters the solar capture tail, matching the LZ dependence. |
| A43 | approximation | icecube-1612.05949-sd: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Solar composition (Fe abundance) changes inelastic capture modestly. |
| A44 | approximation | icecube-1612.05949-si: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As for A39. |
| A47 | approximation | icecube-1612.05949-si: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As for A42. |
| A48 | approximation | icecube-1612.05949-si: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As for A43. |
| A49 | validity | fermi-1503.02641-dsph: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which ⟨σv⟩ today and its final states follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The indirect-detection check is unconcluded, so candidates remain viable by default. |
| A7 | approximation | candidates closer than 20 events (Jeffreys distance) form one degeneracy class; only the best of each of the leading classes is carried on | minor | A 20-event Jeffreys threshold is coarse for a one-event signal; merging classes may hide alternatives but does not change Z. |
| A9 | statistics | null experiments enter as limit-equivalent likelihoods; their tension with the signal is the parameter goodness of fit | minor | Limit-equivalent nulls are approximate, but light targets cannot kinematically excite 350 keV at 1 TeV, so tension is likely negligible. |

Added by the audit agent (its own, not the code's inventory):
- The signal rests on a single event; its energy, reconstruction and NR/ER classification are assumed correct.
- The LZ Earth velocity v_E is unstated yet controls the inelastic kinematic threshold; it likely differs from 232 km/s.
- Detection efficiency near the 269.9 keV upper window edge is assumed flat or known.
- The trials factor over mass, splitting and operator grid sets global Z; grid density is assumed.
- Annual modulation, strongly enhanced for inelastic DM, is not used as a cross-check.


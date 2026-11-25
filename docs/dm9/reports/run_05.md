# DM9 agents: Path 2 on LZ extended window (2026)

## Variants (DM9)

- L12s@4000: the best-fit coupling is above 4π
- O01s@1000,d=350: excluded by icecube-1612.05949-sd, icecube-1612.05949-si

| variant | deformation | reason | Z_joint | AIC (parent's) | joined |
|---|---|---|---|---|---|
| L12s@4000~O12 | nonrelativistic limit to O12 | L12s@4000 needs coupling >4π; its O12 limit is velocity-suppressed rather than q-suppressed like O10/O15, so the same rate could need a smaller coupling. | 2.04 | -0.16 (-10.33) | no |
| O01s@1000,d=350~d400 | splitting 400 keV | O01s@1000,d=350 is excluded by IceCube SD/SI solar capture; raising the splitting to 400 keV raises the minimum speed, further suppressing capture on light solar nuclei. | 0.00 | 4.00 (-10.14) | no |
| O01s@1000,d=350~d450 | splitting 450 keV | For the same IceCube exclusion, a 450 keV splitting kinematically closes more solar capture on H and light elements, weakening those limits. | 0.00 | 4.00 (-10.14) | no |

### Constraints proposed by the scout for O01v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Inelastic solar capture with neutrino-telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | equilibrium between capture and annihilation in the Sun; annihilation channel producing neutrinos (e.g. W+W-) |
| Solar-capture neutrino tension for TeV inelastic DM with δ~0.5 MeV | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | solar capture-annihilation equilibrium; higgsino-like annihilation to W+W- |
| Isospin-violating SI solar capture (IceCube/DeepCore) | solar_capture | needs_calculation | arXiv:1108.0518 (2011) | equilibrium in the Sun; annihilation channel to neutrinos |
| Inelastic DM capture in M4 white dwarfs | indirect_detection | needs_calculation | arXiv:1001.2737 (2010) | annihilation to SM particles heating the white dwarf; primordial dark-matter halo density in globular cluster M4 |

### Constraints proposed by the scout for O04v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar SD-neutron capture limits (IceCube/Super-K/gamma) | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | capture-annihilation equilibrium in the Sun; specified annihilation channel |
| Inelastic SD solar capture bounds | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | equilibrium in the Sun; neutrino-producing annihilation channel |
| Solar-capture neutrino tension for TeV inelastic DM | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | higgsino-like annihilation to W+W-; Standard Halo Model or simulated halo |
| Suppressed solar annihilation of captured inelastic DM | solar_capture | needs_calculation | arXiv:2609.10636 (2026) | full orbital evolution of the captured population rather than isothermal equilibrium |
| Neutrino-telescope limits on NR operators | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium in the Sun; annihilation channel |
| Inelastic DM solar neutrinos (DUNE/Super-K) | solar_capture | needs_calculation | arXiv:2308.16134 (2023) | hadrophilic annihilation |

### Constraints proposed by the scout for O04v@4000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture via SD neutron scattering | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | capture-annihilation equilibrium in the Sun; annihilation channel specified |
| Inelastic solar capture, SD exothermic/endothermic | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | equilibrium in the Sun; annihilation channel to neutrinos |
| NREFT O4 neutrino-telescope limits | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium; annihilation channel |
| IceCube SD-proton limits via micrOMEGAs | solar_capture | needs_calculation | arXiv:1507.07987 (2015) | annihilation channel; equilibrium |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | data | The search: LZ extended window (2026): Xe, exposure 1.0362e+06 kg·day, window 5.4–269.9 keV, fidelity B, no background model of its own | critical | With no background model of its own, the 0.0015 expected background is external; any underestimate, such as unmodelled high-energy tails, sharply lowers Z=3.50. |
| A2 | convention | LZ extended window (2026): halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | critical | For d=300–350 keV inelastic kinematics near threshold, v₀=238 and v_esc=544 control whether events exist at all; shifts move rates by orders of magnitude and can remove candidates. |
| A25 | validity | halo (v_esc = 500 km/s): no events at all (for O04v@1000,d=350, O04v@400,d=300) | critical | At v_esc=500 the O04v candidates predict zero events, so their existence depends entirely on the escape speed. |
| A30 | validity | coupling: the best fit needs 18 times the unit coupling of LZ extended window (2026)'s convention, above 4π (for L12s@4000) | critical | A coupling above 4π is non-perturbative, so L12s@4000 should be discarded from the indistinguishable set. |
| A5 | statistics | global significance: one-event closed form (expected background 0.0015 events), toys as a check | critical | The single-event Poisson closed form gives Z≈3.5 only if trials over the model space are properly counted; a look-elsewhere penalty would lower it. |
| A6 | model | the model space: the search's published model space, or every operator and Lagrangian card in each isospin over the mass grid, with splittings [0.0] keV | critical | The listed splittings [0.0] keV contradict the d=300/350 candidates; if the grid was ad hoc or coarse, the leading-model ranking and look-elsewhere factor are unreliable. |
| A11 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | Using v₀=220, against LZ's 238, makes the combination inconsistent; inelastic null rates are underestimated relative to the signal, weakening tension. |
| A16 | data | Null experiment: PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | material | PICO, with fluorine targets up to 300 keV, constrains O04v spin-dependent couplings; a mis-modelled efficiency would shift the O04v viability. |
| A17 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The lower v₀ underestimates PICO inelastic rates, possibly hiding tension with the O04v candidates. |
| A18 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | material | Fluorine spin structure uncertainty directly scales the PICO limits on O04v. |
| A19 | data | Null experiment: DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | material | DEAP's 50–100 keV Ar window and huge exposure could test the O01v inelastic candidates; a narrow window treatment matters. |
| A20 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The v₀ mismatch underestimates DEAP inelastic reach, weakening its tension with O01v. |
| A23 | validity | halo (v_esc = 500 km/s): Z -0.01, best-fit coupling ×36 (for O01v@1000,d=350) | material | A coupling ×36 at v_esc=500 shows the normalization is unstable even though Z barely moves; inferred couplings are untrustworthy. |
| A24 | validity | halo (v_esc = 600 km/s): Z -0.05, best-fit coupling ×0.48 (for O01v@1000,d=350) | material | A coupling ×0.48 at 600 km/s confirms tail dominance; physics parameters swing by a factor of 2. |
| A26 | validity | halo (v_esc = 600 km/s): Z -0.09, best-fit coupling ×0.35 (for O04v@1000,d=350) | material | A coupling ×0.35 shows strong halo-tail dependence for the second-ranked model. |
| A27 | validity | halo (v_esc = 500 km/s): Z +0.07, best-fit coupling ×4.9 (for O04v@4000,d=350) | material | A coupling ×4.9 shows halo sensitivity of the coupling; Z is stable. |
| A28 | validity | halo (v_esc = 500 km/s): Z +0.06, best-fit coupling ×20 (for O01v@400,d=300) | material | A coupling ×20 shows the normalization is tail-driven. |
| A29 | validity | halo (v_esc = 600 km/s): Z -0.16, best-fit coupling ×0.43 (for O01v@400,d=300) | material | A ΔZ of −0.16 and coupling ×0.43 are moderate shifts. |
| A3 | approximation | LZ extended window (2026): nuclear responses haxton_2022 (spin-dependent: haxton_2022) | material | Alternative Xe responses rescale the O04 spin-dependent rates and couplings, reshuffling ΔAIC between O01v and O04v at ≤0.5 separations. |
| A31 | validity | halo (v_esc = 600 km/s): Z -0.07, best-fit coupling ×0.46 (for O04v@400,d=300) | material | A coupling ×0.46 shows halo-tail dependence. |
| A32 | validity | halo (v_esc = 500 km/s): Z +0.10, best-fit coupling ×1.3e+02 (for O01s@1000,d=350) | material | A coupling ×130 at 500 km/s risks non-perturbativity for O01s. |
| A34 | validity | planck-2018-omega: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the annihilation cross-sections follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Relic-abundance consistency is untested; a completion could exclude or support candidates. |
| A35 | validity | cms-2405.13778-V1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Collider mediator bounds are unapplied; they could exclude TeV-scale candidates. |
| A36 | validity | cms-2405.13778-A1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Same as A35, for the axial-vector benchmark. |
| A37 | validity | cms-2405.13778-V2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Same as A35. |
| A38 | validity | cms-2405.13778-A2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Same as A35. |
| A4 | statistics | an extended unbinned likelihood in recoil energy, with the module's resolution; the signal strength is the only free parameter of a candidate (k = 1) | material | With one event, the shape term rests on that event's energy under the module resolution; resolution mis-modelling shifts which mass/splitting is preferred. |
| A40 | approximation | icecube-1612.05949-sd: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | If capture-annihilation equilibrium fails, the IceCube SD bounds weaken, favouring survival of O04v. |
| A41 | approximation | icecube-1612.05949-sd: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Inelastic thermalization may fail, so captured DM may not concentrate in the core; the solar bound is likely overestimated. |
| A42 | approximation | icecube-1612.05949-sd: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Solar capture of inelastic DM is tail-dominated, so halo choice moves the bound strongly. |
| A45 | approximation | icecube-1612.05949-si: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Equilibrium failure weakens the SI solar bound. |
| A46 | approximation | icecube-1612.05949-si: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A41, likely overstating the SI capture bound. |
| A47 | approximation | icecube-1612.05949-si: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Halo-tail sensitivity of inelastic capture, as in A42. |
| A49 | validity | fermi-1503.02641-dsph: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which ⟨σv⟩ today and its final states follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Indirect-detection constraints are unapplied; they could exclude candidates once ⟨σv⟩ is fixed. |
| A7 | approximation | candidates closer than 20 events (Jeffreys distance) form one degeneracy class; only the best of each of the leading classes is carried on | material | The 20-event Jeffreys merging threshold can drop distinct models, so the ranking may omit viable alternatives; Z itself is unaffected. |
| A8 | statistics | the tournament ranks by AIC = −Z_joint² + 2k; within ΔAIC ≤ 2 candidates are indistinguishable | material | All six leaders lie within ΔAIC 1.02 < 2, so no model is preferred; the ordering is not a conclusion. |
| A9 | statistics | null experiments enter as limit-equivalent likelihoods; their tension with the signal is the parameter goodness of fit | material | Limit-equivalent likelihoods approximate null data; true likelihoods could raise tension for the ~1 TeV candidates, especially with PICO for O04v. |
| A10 | data | Null experiment: CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | minor | CRESST's 16 keV ceiling and light targets cannot access d=300–350 keV upscattering, so errors here barely move the conclusion. |
| A12 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | CRESST is kinematically blind to these splittings, so its form factors are irrelevant. |
| A13 | data | Null experiment: CDMSlite Run 2: Ge, exposure 70.1 kg·day, window 0.308763–7.76269 keV, fidelity B, no background model of its own | minor | The Ge window below 7.8 keV cannot see large-splitting recoils; negligible impact. |
| A14 | convention | CDMSlite Run 2: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo inconsistency is irrelevant given CDMSlite has no sensitivity to these models. |
| A15 | approximation | CDMSlite Run 2: nuclear responses helm (spin-dependent: klos) | minor | Germanium form-factor choice is irrelevant for these candidates. |
| A21 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | Helm suffices for SI argon; small change only. |
| A22 | prior | no priors: profile-likelihood fits and frequentist limits throughout | minor | A frequentist treatment is consistent; priors would only matter for model-ranking interpretation. |
| A33 | validity | halo (v_esc = 600 km/s): Z -0.19, best-fit coupling ×0.28 (for O01s@1000,d=350) | minor | A coupling ×0.28 is a modest shift for a non-leading candidate. |
| A39 | approximation | icecube-1612.05949-sd: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The b b̄ channel is conservative, so it can only understate exclusion. |
| A43 | approximation | icecube-1612.05949-sd: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Solar composition uncertainty shifts capture by tens of percent. |
| A44 | approximation | icecube-1612.05949-si: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The b b̄ channel is conservative, as in A39. |
| A48 | approximation | icecube-1612.05949-si: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Small composition effect. |

Added by the audit agent (its own, not the code's inventory):
- The 0.0015 background expectation is taken from the published LZ analysis at high energy and is assumed applicable to an extended 5.4–269.9 keV window.
- The single candidate event's energy and NR/ER classification are assumed correct; misclassification removes the signal.
- Detection efficiency and acceptance near the 269.9 keV upper edge are assumed well known.
- Isospin choices treated as discrete grid points imply an unstated trials factor in global Z.
- The Earth's velocity and annual modulation are neglected in the LZ signal rate.


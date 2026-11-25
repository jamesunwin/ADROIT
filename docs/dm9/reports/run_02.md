# DM9 agents: Path 2 on LZ extended window (2026)

## Variants (DM9)

- L12s@4000: the best-fit coupling is above 4π
- O01s@1000,d=350: excluded by icecube-1612.05949-sd, icecube-1612.05949-si

| variant | deformation | reason | Z_joint | AIC (parent's) | joined |
|---|---|---|---|---|---|
| L12s@4000~O10 | nonrelativistic limit to O10 | For the coupling-above-4π trigger, an O10 limit keeps the spin response with only q/m_N suppression. That may give a larger rate per coupling than full L12s@4000, lowering the best-fit coupling. | 3.12 | -5.76 (-10.33) | no |
| L12s@4000~O12 | nonrelativistic limit to O12 | For the coupling-above-4π trigger, an O12 limit changes the momentum and velocity dependence and the nuclear responses. That could raise the rate per coupling and pull the coupling below 4π. | 2.04 | -0.16 (-10.33) | no |
| O01s@1000,d=350~isov | isospin v | For the IceCube [unverified reference removed] SI/SD exclusion, isovector couplings change the solar capture rates on targets with different neutron fractions. The untriggered O01v@1000,d=350 leader suggests this can evade the exclusion. | 3.65 | -9.32 (-10.14) | no |
| O01s@1000,d=350~d400 | splitting 400 keV | For the IceCube SI/SD exclusion, a 400 keV splitting raises the minimum speed. That further suppresses capture on light solar nuclei (H, He), weakening the neutrino limit while keeping the high-recoil spectrum. | 0.00 | 4.00 (-10.14) | no |

### Constraints proposed by the scout for O01v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture of inelastic DM with neutrino-telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | equilibrium between capture and annihilation in the Sun; annihilation channel to neutrinos specified |
| Solar-capture neutrino tension for ~TeV inelastic (higgsino-like) DM | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | annihilation to W+W- or similar hard channel; capture-annihilation equilibrium |
| Suppressed solar annihilation despite inelastic capture | solar_capture | needs_calculation | arXiv:2609.10636 (2026) | specific completion that sets the annihilation channels |
| White dwarf heating from inelastic SI capture (M4) | indirect_detection | needs_calculation | arXiv:1001.2737 (2010) | annihilation to SM particles; primordial globular-cluster DM density in M4 |
| Neutron star heating by inelastic DM | indirect_detection | needs_calculation | arXiv:2301.08767 (2023) | observation of cold old neutron stars (projected) |

### Constraints proposed by the scout for O04v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture of inelastic spin-dependent DM vs neutrino telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; annihilation channel to neutrino-producing final states |
| Solar SD dark matter-neutron capture constraints | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | equilibrium in the Sun; specified annihilation channel |
| Neutrino telescope limits on NR operator O4 | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium in the Sun; annihilation channel |
| Solar-capture neutrino bounds on ~TeV inelastic DM with sub-MeV splitting | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | equilibrium in the Sun; W+W- or similar annihilation channel |

### Constraints proposed by the scout for O04v@4000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture via spin-dependent DM-neutron scattering | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | capture-annihilation equilibrium in the Sun; annihilation channel specified |
| Inelastic spin-dependent solar capture with neutrino-telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | equilibrium in the Sun; annihilation channel to neutrinos specified |
| Neutrino-telescope limits on NR operator O4 | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium in the Sun; annihilation channel specified |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | data | The search: LZ extended window (2026): Xe, exposure 1.0362e+06 kg·day, window 5.4–269.9 keV, fidelity B, no background model of its own | critical | With no LZ background model, the assumed 0.0015-event background sets Z; any realistic leakage or neutron background in the 5.4–269.9 keV window would sharply lower Z=3.50. |
| A25 | validity | halo (v_esc = 500 km/s): no events at all (for O04v@1000,d=350, O04v@400,d=300) | critical | With v_esc=500 km/s these O04v candidates predict zero events and become non-viable, removing a ranked leader. |
| A30 | validity | coupling: the best fit needs 18 times the unit coupling of LZ extended window (2026)'s convention, above 4π (for L12s@4000) | critical | A coupling above 4π is non-perturbative; L12s@4000 should be dropped from the ranking. |
| A5 | statistics | global significance: one-event closed form (expected background 0.0015 events), toys as a check | critical | The closed form with b=0.0015 gives Z directly; an underestimated b or ignored trials would reduce Z, possibly below 3. |
| A19 | data | Null experiment: DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | material | Ar can marginally excite large splittings for TeV masses; an Ar exclusion would raise the tension for d=350 candidates. |
| A2 | convention | LZ extended window (2026): halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | material | For d=300–350 keV only the velocity tail contributes, so v₀=238 and v_esc=544 km/s strongly set rates and couplings (×0.3–×130 in A23–A33), with smaller shifts in Z. |
| A20 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | Using 220 km/s instead of 238 km/s understates DEAP's inelastic rate, biasing its tension low. |
| A23 | validity | halo (v_esc = 500 km/s): Z -0.01, best-fit coupling ×36 (for O01v@1000,d=350) | material | The ×36 coupling shift shows the rate rests on the halo tail; Z is stable but the inferred coupling is not. |
| A24 | validity | halo (v_esc = 600 km/s): Z -0.05, best-fit coupling ×0.48 (for O01v@1000,d=350) | material | The ×0.48 coupling shift shows halo sensitivity; Z changes by only 0.05. |
| A26 | validity | halo (v_esc = 600 km/s): Z -0.09, best-fit coupling ×0.35 (for O04v@1000,d=350) | material | The coupling drops ×0.35; Z falls slightly. |
| A27 | validity | halo (v_esc = 500 km/s): Z +0.07, best-fit coupling ×4.9 (for O04v@4000,d=350) | material | The coupling rises ×4.9; Z changes slightly. |
| A28 | validity | halo (v_esc = 500 km/s): Z +0.06, best-fit coupling ×20 (for O01v@400,d=300) | material | The coupling rises ×20; this is a tail-dominated candidate. |
| A29 | validity | halo (v_esc = 600 km/s): Z -0.16, best-fit coupling ×0.43 (for O01v@400,d=300) | material | The coupling drops ×0.43; Z falls by 0.16. |
| A3 | approximation | LZ extended window (2026): nuclear responses haxton_2022 (spin-dependent: haxton_2022) | material | Xe response choice rescales the fitted couplings and the relative O01/O04 rates, shifting ranks within ΔAIC<2 but not Z. |
| A31 | validity | halo (v_esc = 600 km/s): Z -0.07, best-fit coupling ×0.46 (for O04v@400,d=300) | material | The coupling drops ×0.46; Z falls slightly. |
| A32 | validity | halo (v_esc = 500 km/s): Z +0.10, best-fit coupling ×1.3e+02 (for O01s@1000,d=350) | material | The ×130 coupling shift makes this candidate fragile under a lower v_esc. |
| A33 | validity | halo (v_esc = 600 km/s): Z -0.19, best-fit coupling ×0.28 (for O01s@1000,d=350) | material | The coupling drops ×0.28; Z falls by 0.19. |
| A4 | statistics | an extended unbinned likelihood in recoil energy, with the module's resolution; the signal strength is the only free parameter of a candidate (k = 1) | material | With k=1 and one event, the result depends on the event energy matching the inelastic spectrum; a mismodeled resolution could reorder candidates. |
| A6 | model | the model space: the search's published model space, or every operator and Lagrangian card in each isospin over the mass grid, with splittings [0.0] keV | material | The listed splitting [0.0] keV contradicts the d=300/350 candidates; an incomplete or inconsistent grid changes the trials factor and the candidate set. |
| A7 | approximation | candidates closer than 20 events (Jeffreys distance) form one degeneracy class; only the best of each of the leading classes is carried on | material | The 20-event Jeffreys threshold may merge or drop distinct classes, changing which candidates appear in the ranking. |
| A8 | statistics | the tournament ranks by AIC = −Z_joint² + 2k; within ΔAIC ≤ 2 candidates are indistinguishable | material | All six listed candidates have ΔAIC ≤1.02, so the stated order is not meaningful; a different criterion could reorder it freely. |
| A10 | data | Null experiment: CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | minor | Light Ca/O/W at low energy cannot excite 300–350 keV splittings efficiently, so CRESST hardly constrains these candidates. |
| A11 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The v₀=220 halo is inconsistent with LZ's 238 km/s, but CRESST has negligible sensitivity here. |
| A12 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | Helm versus shell model matters little given CRESST's negligible reach for these candidates. |
| A13 | data | Null experiment: CDMSlite Run 2: Ge, exposure 70.1 kg·day, window 0.308763–7.76269 keV, fidelity B, no background model of its own | minor | Ge with a window below 7.8 keV sees essentially no inelastic d≥300 keV recoils; it is irrelevant to the conclusions. |
| A14 | convention | CDMSlite Run 2: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo mismatch with LZ is irrelevant given CDMSlite's lack of reach. |
| A15 | approximation | CDMSlite Run 2: nuclear responses helm (spin-dependent: klos) | minor | Form-factor choice is irrelevant at CDMSlite's reach. |
| A16 | data | Null experiment: PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | minor | Fluorine is too light to excite 300–350 keV splittings, so PICO adds negligible tension. |
| A17 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo mismatch is immaterial given PICO's weak reach. |
| A18 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | minor | Spin responses matter only for O04 and remain negligible at this kinematics. |
| A21 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | Helm suffices for Ar SI responses; spin responses are near zero. |
| A22 | prior | no priors: profile-likelihood fits and frequentist limits throughout | minor | A frequentist treatment throughout is self-consistent; priors would not change Z. |
| A34 | validity | planck-2018-omega: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the annihilation cross-sections follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The relic-density check is unapplied, so viability is untested but Z is unchanged. |
| A35 | validity | cms-2405.13778-V1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The collider check is unapplied; candidates may be excluded once completed. |
| A36 | validity | cms-2405.13778-A1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Same as A35: the collider check is unapplied and candidates may later be excluded. |
| A37 | validity | cms-2405.13778-V2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Same as A35: the collider check is unapplied and candidates may later be excluded. |
| A38 | validity | cms-2405.13778-A2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Same as A35: the collider check is unapplied and candidates may later be excluded. |
| A39 | approximation | icecube-1612.05949-sd: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The weakest channel is conservative; harder channels would only add tension. |
| A40 | approximation | icecube-1612.05949-sd: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Assuming equilibrium overstates the solar signal, making the constraint aggressive rather than conservative. |
| A41 | approximation | icecube-1612.05949-sd: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Inelastic thermalization failure would weaken the solar limits further. |
| A42 | approximation | icecube-1612.05949-sd: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Solar capture of d≥300 keV DM is tail-limited and highly halo-sensitive, but the constraint is already weak. |
| A43 | approximation | icecube-1612.05949-sd: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Solar-model composition, notably heavy elements for inelastic capture, shifts the limit modestly. |
| A44 | approximation | icecube-1612.05949-si: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Same as A39: the weakest channel is conservative. |
| A45 | approximation | icecube-1612.05949-si: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Same as A40: equilibrium makes the constraint aggressive. |
| A46 | approximation | icecube-1612.05949-si: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Same as A41: thermalization failure would weaken the limits. |
| A47 | approximation | icecube-1612.05949-si: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Same as A42: halo-sensitive but already weak. |
| A48 | approximation | icecube-1612.05949-si: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Same as A43: modest shift. |
| A49 | validity | fermi-1503.02641-dsph: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which ⟨σv⟩ today and its final states follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The indirect-detection check is unapplied; Z is unaffected. |
| A9 | statistics | null experiments enter as limit-equivalent likelihoods; their tension with the signal is the parameter goodness of fit | minor | A limit-equivalent treatment approximates tension; nulls barely reach heavy inelastic DM, so the effect on the conclusions is small. |

Added by the audit agent (its own, not the code's inventory):
- The single event's reconstructed energy and its ER/NR discrimination determine the fit; misclassification would erase the signal.
- LZ efficiency and acceptance across the extended 5.4–269.9 keV window are taken as known.
- The trials factor over the mass/operator/splitting grid is assumed captured by the one-event closed form.
- Earth-velocity and annual-modulation effects on the inelastic tail are taken as fixed; the tail amplifies them.
- A truncated-Maxwellian tail shape is assumed; substructure or streams near v_esc could dominate inelastic rates.


# DM9 agents: Path 2 on LZ extended window (2026)

## Variants (DM9)

- L12s@4000: the best-fit coupling is above 4π
- O01s@1000,d=350: excluded by icecube-1612.05949-sd, icecube-1612.05949-si

| variant | deformation | reason | Z_joint | AIC (parent's) | joined |
|---|---|---|---|---|---|
| L12s@4000~O10 | nonrelativistic limit to O10 | Trigger: coupling >4π. Reducing L12s to its O10 nonrelativistic piece keeps the q-dependent spin response without the extra suppression of O12/O15, which may need a smaller coupling for the same xenon rate. | 3.12 | -5.76 (-10.33) | no |
| O01s@1000,d=350~d400 | splitting 400 keV | Trigger: IceCube SD/SI exclusion. Raising δ from 350 to 400 keV raises the minimum speed, further suppressing capture on light solar nuclei (H, He) and weakening the solar-capture limit. | 0.00 | 4.00 (-10.14) | no |
| O01s@1000,d=350~d450 | splitting 450 keV | Trigger: IceCube exclusion. A 450 keV splitting makes up-scattering on light solar targets nearly kinematically forbidden, while heavy xenon at 1 TeV can still scatter at high recoil. | 0.00 | 4.00 (-10.14) | no |

### Constraints proposed by the scout for O01v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Inelastic solar capture with neutrino-telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; annihilation channel to neutrino-producing final states |
| Isospin-violating SI dark matter in the Sun | solar_capture | needs_calculation | arXiv:1108.0518 (2011) | equilibrium in the Sun; specified annihilation channel |
| Solar capture versus LZ high-recoil inelastic event | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | higgsino-like annihilation to W+W-; equilibrium in the Sun |
| Captured population with suppressed annihilation | solar_capture | needs_calculation | arXiv:2609.10636 (2026) | non-equilibrium orbital evolution; scalar B-3L_tau completion |
| White dwarf capture of inelastic DM in M4 | cosmology | needs_calculation | arXiv:1001.2737 (2010) | annihilation to SM particles; primordial DM halo for M4 |

### Constraints proposed by the scout for O04v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture of inelastic DM (endothermic, SD) with neutrino telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; annihilation channel to neutrinos specified |
| Solar SD neutron capture constraints | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | equilibrium in the Sun; annihilation channel |
| Neutrino-telescope limits on NR-EFT operators | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium in the Sun; annihilation channel |
| Solar neutrino limits on inelastic DM | solar_capture | needs_calculation | arXiv:2308.16134 (2023) | hadrophilic annihilation; equilibrium |

### Constraints proposed by the scout for O04v@4000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar SD-neutron capture, neutrino and gamma-ray limits | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | capture-annihilation equilibrium in the Sun; specified annihilation channel (needs completion) |
| Inelastic SD solar capture vs neutrino telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | equilibrium in the Sun; annihilation branching to neutrino-producing channels |
| Neutrino-telescope limits on NR-EFT operator couplings | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium in the Sun; annihilation channel (e.g. W+W-) from a completion |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | data | The search: LZ extended window (2026): Xe, exposure 1.0362e+06 kg·day, window 5.4–269.9 keV, fidelity B, no background model of its own | critical | With no background model of its own, the 0.0015-event expectation is imported; an underestimate would sharply lower Z=3.50 from a single event. |
| A25 | validity | halo (v_esc = 500 km/s): no events at all (for O04v@1000,d=350, O04v@400,d=300) | critical | With no events at v_esc=500, the O04v@1000/400 candidates are kinematically fragile and could be excluded outright. |
| A30 | validity | coupling: the best fit needs 18 times the unit coupling of LZ extended window (2026)'s convention, above 4π (for L12s@4000) | critical | A coupling 18× unit, above 4π, makes L12s@4000 non-perturbative; it should leave the ranking. |
| A5 | statistics | global significance: one-event closed form (expected background 0.0015 events), toys as a check | critical | The one-event Poisson closed form is fully driven by background; if toys or trials over the model space disagree, global Z drops. |
| A6 | model | the model space: the search's published model space, or every operator and Lagrangian card in each isospin over the mass grid, with splittings [0.0] keV | critical | Splittings are listed as [0.0] keV, yet the leaders have d=300–350; this inconsistency questions which space was scanned and the trials factor. |
| A16 | data | Null experiment: PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | material | Fluorine spin-dependent reach up to 300 keV can constrain O04v candidates; the missing background model affects the tension. |
| A17 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | v0=220 versus LZ's 238 km/s lowers the predicted PICO rate for inelastic scattering, understating tension. |
| A18 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | material | Fluorine shell-model SD responses directly set PICO tension for O04v. |
| A19 | data | Null experiment: DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | material | The large Ar exposure but narrow 50–101 keV window and heavy inelastic threshold set tension for the O01v candidates. |
| A2 | convention | LZ extended window (2026): halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | material | The halo v0=238 km/s, unlike 220 km/s for the null experiments, raises high-velocity flux for inelastic d=350 keV fits, shifting couplings and tensions. |
| A20 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | material | The halo mismatch with LZ biases the relative rate in the escape tail, where inelastic events live. |
| A23 | validity | halo (v_esc = 500 km/s): Z -0.01, best-fit coupling ×36 (for O01v@1000,d=350) | material | The coupling ×36 at v_esc=500 shows the leader sits in the escape tail; Z is stable but the physical coupling is not. |
| A27 | validity | halo (v_esc = 500 km/s): Z +0.07, best-fit coupling ×4.9 (for O04v@4000,d=350) | material | Coupling ×4.9 shows halo dependence of the third-ranked candidate. |
| A28 | validity | halo (v_esc = 500 km/s): Z +0.06, best-fit coupling ×20 (for O01v@400,d=300) | material | Coupling ×20 shows the O01v@400 coupling is halo-driven. |
| A3 | approximation | LZ extended window (2026): nuclear responses haxton_2022 (spin-dependent: haxton_2022) | material | Xe responses for O04 and spin-dependent cards set rates; a different set rescales couplings and could reorder the ΔAIC<1 ranking. |
| A32 | validity | halo (v_esc = 500 km/s): Z +0.10, best-fit coupling ×1.3e+02 (for O01s@1000,d=350) | material | Coupling ×130 at v_esc=500 indicates extreme tail dependence for O01s. |
| A34 | validity | planck-2018-omega: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the annihilation cross-sections follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Relic abundance is unchecked; candidates may be over- or under-abundant and could be disfavored. |
| A35 | validity | cms-2405.13778-V1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | The unchecked collider bound could exclude TeV mediators for some candidates. |
| A36 | validity | cms-2405.13778-A1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Same as A35, for the axial benchmark. |
| A37 | validity | cms-2405.13778-V2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Same as A35. |
| A38 | validity | cms-2405.13778-A2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Same as A35. |
| A4 | statistics | an extended unbinned likelihood in recoil energy, with the module's resolution; the signal strength is the only free parameter of a candidate (k = 1) | material | With k=1 and one event, the fit is essentially rate plus single-energy position; resolution errors move per-candidate Z slightly. |
| A41 | approximation | icecube-1612.05949-sd: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Inelastic thermalization may fail at d=300–350 keV, weakening the solar limit; the stated assumption overstates the constraint. |
| A42 | approximation | icecube-1612.05949-sd: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Inelastic solar capture depends on the high-velocity tail, which is sensitive to SHM parameters. |
| A46 | approximation | icecube-1612.05949-si: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A41. |
| A47 | approximation | icecube-1612.05949-si: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A42. |
| A49 | validity | fermi-1503.02641-dsph: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which ⟨σv⟩ today and its final states follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Indirect detection is unchecked; it could exclude candidates once a completion fixes ⟨σv⟩. |
| A8 | statistics | the tournament ranks by AIC = −Z_joint² + 2k; within ΔAIC ≤ 2 candidates are indistinguishable | material | All six candidates fall within ΔAIC≤2, so no model is preferred; the ordering is not a conclusion. |
| A9 | statistics | null experiments enter as limit-equivalent likelihoods; their tension with the signal is the parameter goodness of fit | material | Limit-equivalent likelihoods approximate the null data; real likelihoods could raise tension and disfavor some leaders. |
| A10 | data | Null experiment: CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | minor | Window ≤16 keV and small exposure barely probe 1–4 TeV inelastic candidates. |
| A11 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | CRESST's halo differs from LZ's, but its weak sensitivity here makes this negligible. |
| A12 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | Helm/shell-model responses for CaWO4 hardly matter, given negligible inelastic reach. |
| A13 | data | Null experiment: CDMSlite Run 2: Ge, exposure 70.1 kg·day, window 0.308763–7.76269 keV, fidelity B, no background model of its own | minor | A Ge window ≤7.8 keV cannot see d≈300–350 keV inelastic recoils; no effect. |
| A14 | convention | CDMSlite Run 2: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | Halo mismatch is irrelevant given no sensitivity. |
| A15 | approximation | CDMSlite Run 2: nuclear responses helm (spin-dependent: klos) | minor | Ge responses are irrelevant at this mass and splitting. |
| A21 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | Helm suffices for SI Ar; SD is null for Ar. |
| A22 | prior | no priors: profile-likelihood fits and frequentist limits throughout | minor | Frequentist profiling is consistent; no prior dependence. |
| A24 | validity | halo (v_esc = 600 km/s): Z -0.05, best-fit coupling ×0.48 (for O01v@1000,d=350) | minor | Coupling ×0.48 with Z −0.05; mild. |
| A26 | validity | halo (v_esc = 600 km/s): Z -0.09, best-fit coupling ×0.35 (for O04v@1000,d=350) | minor | Z −0.09, coupling ×0.35. |
| A29 | validity | halo (v_esc = 600 km/s): Z -0.16, best-fit coupling ×0.43 (for O01v@400,d=300) | minor | Z −0.16, coupling ×0.43. |
| A31 | validity | halo (v_esc = 600 km/s): Z -0.07, best-fit coupling ×0.46 (for O04v@400,d=300) | minor | Z −0.07, coupling ×0.46. |
| A33 | validity | halo (v_esc = 600 km/s): Z -0.19, best-fit coupling ×0.28 (for O01s@1000,d=350) | minor | Z −0.19, coupling ×0.28. |
| A39 | approximation | icecube-1612.05949-sd: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | The weakest channel (b b̄) is conservative; harder channels would only add tension. |
| A40 | approximation | icecube-1612.05949-sd: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Equilibrium maximizes the flux; if not reached, the solar limit weakens. |
| A43 | approximation | icecube-1612.05949-sd: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Solar composition changes capture by tens of percent. |
| A44 | approximation | icecube-1612.05949-si: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As A39. |
| A45 | approximation | icecube-1612.05949-si: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As A40. |
| A48 | approximation | icecube-1612.05949-si: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As A43. |
| A7 | approximation | candidates closer than 20 events (Jeffreys distance) form one degeneracy class; only the best of each of the leading classes is carried on | minor | Merging candidates within 20 events Jeffreys distance can drop distinct models from the ranking; Z is unaffected. |

Added by the audit agent (its own, not the code's inventory):
- The global Z apparently omits a trials factor over the operator×mass×splitting scan; any look-elsewhere correction lowers 3.50.
- The single event's energy relative to the inelastic spectrum endpoint drives candidate preference; energy-scale systematics are not inventoried.
- The Earth velocity and modulation phase for LZ's halo are unstated; inelastic rates in the escape tail are sensitive to v_E.
- LZ detection efficiency near the 269.9 keV upper window edge is assumed known; inelastic d=350 keV spectra peak at high recoil.
- Isospin choice per candidate is not reported; xenon/fluorine/argon tensions depend strongly on it.


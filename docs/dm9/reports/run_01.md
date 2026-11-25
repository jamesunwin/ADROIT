# DM9 agents: Path 2 on LZ extended window (2026)

## Variants (DM9)

- L12s@4000: the best-fit coupling is above 4π
- O01s@1000,d=350: excluded by icecube-1612.05949-sd, icecube-1612.05949-si

| variant | deformation | reason | Z_joint | AIC (parent's) | joined |
|---|---|---|---|---|---|
| L12s@4000~O12 | nonrelativistic limit to O12 | Trigger: coupling above 4π. The O12 limit avoids the explicit q suppression of the L12 reduction, so it could raise the rate and lower the required coupling. | 2.04 | -0.16 (-10.33) | no |
| O01s@1000,d=350~d400 | splitting 400 keV | Same IceCube trigger. A 400 keV splitting strongly suppresses solar capture on light elements, with a milder hit to the direct-detection signal. | 0.00 | 4.00 (-10.14) | no |
| O01s@1000,d=350~d450 | splitting 450 keV | Trigger: IceCube [unverified reference removed] SI/SD solar-capture exclusion. A 450 keV splitting blocks capture on light solar nuclei, especially hydrogen, while heavy direct-detection targets still scatter. | 0.00 | 4.00 (-10.14) | no |

### Constraints proposed by the scout for O01v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Solar capture of endothermic inelastic DM vs neutrino telescope limits | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; annihilation channel producing neutrinos (e.g. W+W- or b bbar) |
| Solar-capture neutrino tension for sub-MeV-split TeV inelastic DM | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | equilibrium in the Sun; higgsino-like annihilation to W+W- |
| Cold white dwarfs in M4: inelastic SI capture heating | solar_capture | needs_calculation | arXiv:1001.2737 (2010) | DM annihilates to SM particles; primordial globular-cluster formation in a DM halo (high core DM density); capture-annihilation equilibrium |

### Constraints proposed by the scout for O04v@1000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Inelastic solar capture, spin-dependent (endo/exothermic) | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | capture-annihilation equilibrium in the Sun; annihilation channel to neutrinos specified |
| Solar SD neutron capture limits | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | equilibrium in the Sun; annihilation channel |
| IceCube SD-proton limits by channel | solar_capture | needs_calculation | arXiv:1507.07987 (2015) | equilibrium in the Sun; specific annihilation channel |
| NR-EFT operator neutrino telescope limits | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | equilibrium in the Sun; annihilation channel |
| Solar capture of ~TeV inelastic DM, δ~500 keV | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | equilibrium; W+W- channel |

### Constraints proposed by the scout for O04v@4000,d=350 (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Inelastic solar capture with SD interactions | solar_capture | needs_calculation | arXiv:1512.03317 (2015) | annihilation channel to neutrinos specified by a completion; capture-annihilation equilibrium |
| Solar SD neutron capture limits | solar_capture | needs_calculation | arXiv:2609.00118 (2026) | annihilation channel from a completion; equilibrium in the Sun |
| NREFT neutrino-telescope limits on O4 | solar_capture | needs_calculation | arXiv:1512.06254 (2015) | annihilation channel; equilibrium |
| IceCube SD-proton limits via micrOMEGAs | solar_capture | needs_calculation | arXiv:1507.07987 (2015) | specific annihilation channel |
| Solar-capture neutrino tension for inelastic TeV DM | solar_capture | needs_calculation | arXiv:2609.15321 (2026) | higgsino-like completion and W+W- annihilation |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | data | The search: LZ extended window (2026): Xe, exposure 1.0362e+06 kg·day, window 5.4–269.9 keV, fidelity B, no background model of its own | critical | With no LZ background model of its own, the assumed 0.0015 expected background carries Z=3.50; a realistic high-energy background of ~0.1 events would drop Z below 2. |
| A2 | convention | LZ extended window (2026): halo Standard Halo Model (arXiv:2105.00599): ρ = 0.3 GeV/cm³, v₀ = 238 km/s, v_esc = 544 km/s | critical | Near threshold at d=350 keV, Xe rates hinge on v_esc and v₀ (A23, A25); other halo values change couplings by orders of magnitude and can erase candidates. |
| A23 | validity | halo (v_esc = 500 km/s): Z -0.01, best-fit coupling ×36 (for O01v@1000,d=350) | critical | Lowering v_esc to 500 km/s needs ×36 coupling for the top candidate, so its viability is halo-fragile. |
| A25 | validity | halo (v_esc = 500 km/s): no events at all (for O04v@1000,d=350, O04v@400,d=300) | critical | At v_esc=500 km/s, O04v@1000,d=350 (ranked 2nd) and O04v@400,d=300 predict zero events, so they are excluded under plausible halos. |
| A28 | validity | halo (v_esc = 500 km/s): Z +0.06, best-fit coupling ×20 (for O01v@400,d=300) | critical | A ×20 coupling at v_esc=500 km/s makes O01v@400,d=300 strongly halo-dependent. |
| A5 | statistics | global significance: one-event closed form (expected background 0.0015 events), toys as a check | critical | The one-event closed form fixes Z=3.50; any look-elsewhere factor over the model space, or background mis-modeling, lowers it. |
| A8 | statistics | the tournament ranks by AIC = −Z_joint² + 2k; within ΔAIC ≤ 2 candidates are indistinguishable | critical | All six leaders lie within ΔAIC 1.02, so by its own ≤2 rule the ranking cannot select a model; the order is noise. |
| A24 | validity | halo (v_esc = 600 km/s): Z -0.05, best-fit coupling ×0.48 (for O01v@1000,d=350) | material | At v_esc=600 km/s the coupling halves with little Z change; the coupling is uncertain by factors. |
| A26 | validity | halo (v_esc = 600 km/s): Z -0.09, best-fit coupling ×0.35 (for O04v@1000,d=350) | material | The coupling shifts ×0.35; ranking is barely affected. |
| A27 | validity | halo (v_esc = 500 km/s): Z +0.07, best-fit coupling ×4.9 (for O04v@4000,d=350) | material | The coupling shifts ×4.9 at lower v_esc; the heavier O04 candidate is more robust than the 1 TeV one. |
| A29 | validity | halo (v_esc = 600 km/s): Z -0.16, best-fit coupling ×0.43 (for O01v@400,d=300) | material | A ×0.43 coupling shift moves the numbers modestly. |
| A3 | approximation | LZ extended window (2026): nuclear responses haxton_2022 (spin-dependent: haxton_2022) | material | Alternative Xe responses at ~100–270 keV recoils would shift best-fit couplings and the relative AIC of O01 versus O04. |
| A30 | validity | coupling: the best fit needs 18 times the unit coupling of LZ extended window (2026)'s convention, above 4π (for L12s@4000) | material | L12s@4000 needs a coupling above 4π, so it is non-perturbative and should drop from the ranking. |
| A34 | validity | planck-2018-omega: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the annihilation cross-sections follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | The relic density is untested; a completion could exclude or favour candidates. |
| A35 | validity | cms-2405.13778-V1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Collider bounds are unevaluated and could exclude TeV mediators. |
| A36 | validity | cms-2405.13778-A1: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A35: an untested collider exclusion. |
| A37 | validity | cms-2405.13778-V2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A35: an untested collider exclusion. |
| A38 | validity | cms-2405.13778-A2: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which the mediator's production and decays follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A35: an untested collider exclusion. |
| A39 | approximation | icecube-1612.05949-sd: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | The bb̄ channel is conservative; harder channels would tighten solar bounds against the candidates. |
| A4 | statistics | an extended unbinned likelihood in recoil energy, with the module's resolution; the signal strength is the only free parameter of a candidate (k = 1) | material | With k=1 the scanned mass and splitting are not counted as free; the local fit, and so the ranking, is optimistic. |
| A40 | approximation | icecube-1612.05949-sd: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Non-equilibrium would weaken the solar bounds. |
| A41 | approximation | icecube-1612.05949-sd: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Inelastic thermalization may fail, weakening the bound; settling is optimistic for exclusion. |
| A44 | approximation | icecube-1612.05949-si: annihilation into b b̄ (the softest published channel: the weakest limit) (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A39 for the SI bound. |
| A45 | approximation | icecube-1612.05949-si: capture and annihilation in equilibrium (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A40 for the SI bound. |
| A46 | approximation | icecube-1612.05949-si: captured particles settle in the core, although every later scattering must also excite the splitting (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | As A41 for the SI bound. |
| A49 | validity | fermi-1503.02641-dsph: not concluded without a relativistic completion (a mediator model with couplings to Standard Model particles), from which ⟨σv⟩ today and its final states follow (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | material | Indirect detection is unevaluated; it could exclude TeV candidates once ⟨σv⟩ is known. |
| A6 | model | the model space: the search's published model space, or every operator and Lagrangian card in each isospin over the mass grid, with splittings [0.0] keV | material | Splittings listed as [0.0] keV conflict with the d=300/350 candidates; an incomplete splitting grid could miss better or competing models. |
| A7 | approximation | candidates closer than 20 events (Jeffreys distance) form one degeneracy class; only the best of each of the leading classes is carried on | material | A 20-event Jeffreys threshold with a one-event signal may merge distinct models, dropping alternatives from the ranking. |
| A9 | statistics | null experiments enter as limit-equivalent likelihoods; their tension with the signal is the parameter goodness of fit | material | Limit-equivalent likelihoods understate null tension relative to full likelihoods and may hide a goodness-of-fit failure. |
| A10 | data | Null experiment: CRESST-III 2019: CaWO4, exposure 5.594 kg·day, window 0.0301–16 keV, fidelity B, no background model of its own | minor | CRESST's 16 keV window and small exposure barely probe inelastic TeV candidates; errors here would not move the conclusion. |
| A11 | convention | CRESST-III 2019: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | Using v₀=220 rather than 238 km/s across experiments is inconsistent but irrelevant for an insensitive null. |
| A12 | approximation | CRESST-III 2019: nuclear responses helm (spin-dependent: shell_model) | minor | Helm/shell-model choices for CaWO4 do not matter where CRESST predicts essentially no inelastic events. |
| A13 | data | Null experiment: CDMSlite Run 2: Ge, exposure 70.1 kg·day, window 0.308763–7.76269 keV, fidelity B, no background model of its own | minor | CDMSlite's sub-8 keV window cannot see d=300–350 keV inelastic recoils. |
| A14 | convention | CDMSlite Run 2: halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo inconsistency with A2 is negligible for an insensitive null. |
| A15 | approximation | CDMSlite Run 2: nuclear responses helm (spin-dependent: klos) | minor | Ge response choices are irrelevant at these splittings. |
| A16 | data | Null experiment: PICO-60 C3F8 (2019): C3F8, exposure 2571 kg·day, window 2.45–300 keV, fidelity B, no background model of its own | minor | Fluorine's low reduced mass cannot excite 350 keV, so PICO does not constrain the O04 candidates. |
| A17 | convention | PICO-60 C3F8 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo mismatch matters little given PICO's kinematic blindness here. |
| A18 | approximation | PICO-60 C3F8 (2019): nuclear responses shell_model (spin-dependent: shell_model) | minor | F shell-model uncertainties do not affect a null predicting no events. |
| A19 | data | Null experiment: DEAP-3600 (2019): Ar, exposure 758000 kg·day, window 50.3649–100.84 keV, fidelity B, no background model of its own | minor | Ar's reduced mass (~36 GeV) gives a kinematic reach of ~120 keV, below 350 keV, so DEAP sees nothing. |
| A20 | convention | DEAP-3600 (2019): halo SHM: v0 = 220.0, v_E = 232.0, v_esc = 544.0 km/s: ρ = 0.3 GeV/cm³, v₀ = 220 km/s, v_esc = 544 km/s | minor | The halo mismatch is irrelevant for DEAP here. |
| A21 | approximation | DEAP-3600 (2019): nuclear responses helm (spin-dependent: shell_model) | minor | Ar Helm responses do not matter at zero predicted rate. |
| A22 | prior | no priors: profile-likelihood fits and frequentist limits throughout | minor | A Bayesian treatment would change interpretation, not the frequentist Z. |
| A31 | validity | halo (v_esc = 600 km/s): Z -0.07, best-fit coupling ×0.46 (for O04v@400,d=300) | minor | The candidate is outside the top six; the coupling shift is moderate. |
| A32 | validity | halo (v_esc = 500 km/s): Z +0.10, best-fit coupling ×1.3e+02 (for O01s@1000,d=350) | minor | A ×130 coupling disfavours O01s, which is unranked anyway. |
| A33 | validity | halo (v_esc = 600 km/s): Z -0.19, best-fit coupling ×0.28 (for O01s@1000,d=350) | minor | This affects only an unranked candidate. |
| A42 | approximation | icecube-1612.05949-sd: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Solar capture's halo dependence is secondary to A2. |
| A43 | approximation | icecube-1612.05949-sd: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | Solar composition shifts capture by tens of percent. |
| A47 | approximation | icecube-1612.05949-si: the Standard Halo Model seen from the Sun (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As A42. |
| A48 | approximation | icecube-1612.05949-si: the B16 AGSS09 solar model (for O01v@1000,d=350, O04v@1000,d=350, O04v@4000,d=350, O01v@400,d=300, L12s@4000, O01v@1000,d=300, O04v@400,d=300, O01s@1000,d=350) | minor | As A43. |

Added by the audit agent (its own, not the code's inventory):
- The global Z apparently ignores the trials factor over mass, splitting and operator grid; the true global significance is lower.
- LZ signal efficiency and ER/NR discrimination are assumed accurate near 270 keV, the window edge.
- The single event's reconstructed energy is assumed precise; a shift alters the preferred d and mass.
- Earth-velocity annual modulation is neglected, though threshold-dominated inelastic rates are highly modulated.
- The splitting grid is coarse (300, 350 keV); the best d may lie between grid points.


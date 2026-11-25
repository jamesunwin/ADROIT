# DM9 agents: Path 1 for Magnetic dipole Dirac fermion dark matter

### Constraints proposed by the scout for Magnetic dipole Dirac fermion dark matter (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Helioseismology bound on asymmetric dipolar DM | solar_capture | applies_with_assumptions | arXiv:1310.0673 (2013) | Asymmetric DM: no annihilation depleting the solar population; Captured DM accumulates and thermalizes in the Sun; Standard local DM density and halo |
| Thermal relic abundance of dipole DM | relic_density | applies_with_assumptions | arXiv:astro-ph/0406355 (2004) | Standard thermal freeze-out; Annihilation only via the dipole operator (chi chibar -> photon -> f fbar, gamma gamma); Operator valid at freeze-out energies (~m/20); no other channels from the completion; Symmetric (non-asymmetric) DM |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A1 | model | chi is electrically neutral and a gauge singlet; only the dipole couples it to the photon. | critical | Any charge or extra coupling (e.g. Z, Higgs portal) would add channels and strengthen every bound. |
| A14 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Uncomputed relic density means the thermal-target dipole and the A4 consistency are untested. |
| A17 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | critical | Direct detection is typically the strongest dipole bound for GeV–TeV masses; omitted, no limit exists. |
| A21 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | critical | s-wave dipole annihilation makes CMB the dominant sub-10 GeV bound; uncomputed. |
| A11 | approximation | left out of the derivation: UV completion generating the dipole. | material | Same as A6: UV states could dominate collider and annihilation phenomenology, tightening bounds. |
| A13 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Five-flavour matching misapplies below m_b and nucleon inputs/long-range photon treatment shift DD limits by tens of percent. |
| A15 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through photon: Γ against H to be computed) | material | If Γ<H, freeze-in applies and the relic-motivated coupling drops drastically. |
| A16 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | material | Duplicates A7: alternative histories rescale the relic-preferred coupling. |
| A18 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | Indirect bounds on s-wave annihilation to photons/fermions could exclude light masses once computed. |
| A19 | validity | Colliders: applies, not yet computed (couples to photon; mediators above 3 TeV: contact-interaction (mono-X) searches) | material | Mono-photon searches bound light-mass dipoles; EFT validity needs checking against Λ. |
| A3 | model | No stability symmetry stated; minimal Z2 (chi odd, photon even) assumed, which also follows from chi number conservation. | material | Without Z2/chi-number, decays would replace relic and annihilation constraints with lifetime bounds. |
| A4 | model | Relic fraction 1 and standard cosmology, as none stated. | material | A sub-unity relic fraction weakens direct and indirect bounds by f and f² respectively. |
| A5 | model | left out of the model: Electric dipole, anapole and charge-radius operators (not given). | material | Electric dipole or anapole terms would change DD recoil spectra and annihilation velocity scaling, shifting limits either way. |
| A6 | model | left out of the model: UV completion generating the dipole, and loop corrections. | material | Light charged UV states would add collider bounds and invalidate contact-operator treatment, usually tightening constraints. |
| A7 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | material | Non-standard history (low reheating, entropy release) shifts the dipole needed for Ωh²=0.12 by orders of magnitude. |
| A10 | approximation | left out of the derivation: Loop-induced operators, including two-photon and Rayleigh terms and RG mixing of the dipole beyond DirectDM's running. | minor | Loop-induced Rayleigh terms are suppressed by extra mu_chi powers; negligible at limit-scale couplings. |
| A12 | approximation | left out of the derivation: Electric dipole (C52), anapole and charge-radius operators, which are absent from the model. | minor | Consistent with model omission; matters only if the model is extended. |
| A2 | model | Written below electroweak symmetry breaking (photon field strength), so phase is broken. | minor | A hypercharge dipole above EWSB adds a Z dipole, mainly changing collider and heavy-mass annihilation rates. |
| A20 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | minor | Solar-capture neutrino bounds usually subdominant to DD for dipoles. |
| A22 | prior | no priors: frequentist limits | minor | Frequentist versus Bayesian treatment shifts limits only modestly. |
| A8 | approximation | mu_chi is defined at μ = m_Z in the five-flavour scheme. The running of a dipole is negligible at tree level. | minor | Scale choice for mu_chi shifts DD rates only at percent level since dipole running is tiny. |
| A9 | approximation | e > 0, with the F_μν sign convention of DirectDM. | minor | Sign conventions only affect interference with absent operators; limits on |mu_chi| unchanged. |

Added by the audit agent (its own, not the code's inventory):
- chi assumed a Dirac fermion; a Majorana fermion has vanishing magnetic dipole, killing all signals.
- DM mass range unspecified; five-flavour matching and DD validity depend on m_chi relative to m_b and nuclear thresholds.
- Standard Halo Model local density and velocity distribution assumed for DD and capture.
- Dipole long-range 1/q² photon exchange requires NR operator treatment beyond contact interactions in DD exclusion.


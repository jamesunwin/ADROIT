# DM9 agents: Path 1 for Dirac fermion dark matter with electric dipole moment

### Constraints proposed by the scout for Dirac fermion dark matter with electric dipole moment (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Relic abundance and cosmological/collider bounds on dark-matter dipole moments | cosmology | applies_with_assumptions | arXiv:astro-ph/0406355 (2004) | Dipole operator is valid up to the annihilation and collider energies; No other interactions or completion states lighter than the cutoff; Standard thermal freeze-out via chi chibar -> photons and fermions through the dipole |
| Loop-mediator completion: EDM, direct detection and relic density | relic_density | needs_calculation | arXiv:1808.06301 (2018) | CP-violating dark sector with colored or non-colored loop mediators generating d_chi |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A15 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Not computed: with relic_fraction=1 the relic target fixes d_chi versus mass, which defines which parameter space is excluded. |
| A18 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | critical | Not computed: the 1/q² enhanced EDM nuclear scattering is the strongest expected constraint, so no conclusion exists without it. |
| A4 | model | relic_fraction = 1 and standard cosmology, as nothing else stated. | critical | Direct and indirect signals scale with the relic fraction (and its square for annihilation), so a fraction below 1 weakens every limit proportionally. |
| A11 | approximation | left out of the derivation: Z-boson (hypercharge-dipole) component of the UV operator, per the ModelSpec. | material | Same as A5: omitting Z couplings underestimates heavy-mass annihilation and collider rates, making limits conservative there. |
| A13 | approximation | left out of the derivation: UV completion generating the dipole. | material | Same as A6: UV states could open extra channels and break EFT validity at collider energies. |
| A14 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Matching and running are fine for a dipole, but the nucleon and nuclear inputs (charge form factors) set the absolute scattering rate. |
| A16 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through photon: Γ against H to be computed) | material | If chi never thermalises at small d_chi, freeze-out does not apply and the relic-target interpretation fails. |
| A17 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | material | Duplicate of A7: the cosmological history fixes the relic-target coupling. |
| A19 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | Not computed: annihilation into photons and fermions may constrain light masses, but it is likely weaker than direct detection. |
| A2 | model | chi is electrically neutral and an SM gauge singlet. | material | A small charge or electroweak charge would add Coulomb or Z exchange, which dominates the dipole and tightens direct-detection and collider limits. |
| A20 | validity | Colliders: applies, not yet computed (couples to photon; mediators above 3 TeV: contact-interaction (mono-X) searches) | material | Not computed: mono-photon and LEP bounds dominate below a few GeV, where direct detection loses sensitivity. |
| A22 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | material | Not computed: if s-wave visible annihilation exists, it excludes the thermal relic below roughly 10 GeV. |
| A5 | model | left out of the model: Any hypercharge-dipole (Z-boson) component of the UV operator; only the photon coupling is kept. | material | A Z-dipole adds Z-mediated annihilation and collider channels at masses ≳ m_Z, raising relic depletion and strengthening collider bounds. |
| A6 | model | left out of the model: UV completion generating the dipole (heavy charged states in loops). | material | Light charged states would invalidate the contact treatment at colliders and add their own constraints, so mono-X limits could be overstated. |
| A7 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | material | A non-standard history (low reheating, entropy release) changes the coupling that yields Ωh²=0.12, moving the relic-target line. |
| A1 | model | Stability symmetry not stated; minimal Z2: chi → −chi, photon even, dipole term even. | minor | The dipole bilinear is even under chi→−chi anyway, so a different stabilising symmetry would not change the operator or any future limit. |
| A10 | approximation | d_chi is defined at mu = m_Z; dipole running is neglected. | minor | QED running of the dipole between m_Z and nuclear scales is a small logarithmic correction, at most a few percent on d_chi. |
| A12 | approximation | left out of the derivation: Loop-induced and RG-generated operators beyond the tree-level dipole; DirectDM's running handles the rest. | minor | Loop-generated operators are suppressed relative to the long-range tree-level dipole, so the effect on scattering is small. |
| A21 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | minor | Solar-capture neutrino bounds are typically subdominant to direct detection for an EDM. |
| A23 | prior | no priors: frequentist limits | minor | Frequentist versus Bayesian treatment changes limits by order-unity factors only. |
| A3 | model | Model written below electroweak symmetry breaking (photon field strength), so phase broken. | minor | This only matters for relic freeze-out above the electroweak scale (heavy chi), where the photon-only treatment shifts the annihilation rate. |
| A8 | approximation | Five-flavour scheme at mu = m_Z. The massless photon is not integrated out, so no mediator forces a lower scheme. | minor | The flavour scheme barely affects photon-mediated scattering; any shift is at the percent level. |
| A9 | approximation | i sigma^{mu nu} gamma5 is identified with sigma^{mu nu} i gamma5; sign of e > 0 as in DirectDM's covariant-derivative convention. | minor | Gamma5 commutes with sigma, so the identification is exact; the sign of e flips only the sign of d_chi, and rates go as d². |

Added by the audit agent (its own, not the code's inventory):
- chi is a Dirac fermion; a Majorana chi has an identically vanishing dipole moment.
- Standard Halo Model (local density 0.3 GeV/cm³, Maxwellian v0≈220 km/s, vesc≈544 km/s) for direct detection.
- Experimental exclusions recast for the long-range 1/q² recoil spectrum rather than the published contact-interaction curves.
- Dimension-5 EFT valid up to all energies probed, i.e. cutoff Λ ≫ collider √s.
- No dark-sector annihilation channels beyond the photon dipole.


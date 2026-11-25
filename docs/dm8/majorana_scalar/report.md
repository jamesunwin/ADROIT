# Path 1 for a bespoke model: majorana_scalar

Status: **complete**.

## Deterministic checks

- all passed

## The derivation (user; 5 flavours, dm_type M)

| coefficient | formula |
|---|---|
| C75u | `y_chi*g_q/(v*m_S**2)` |
| C75d | `y_chi*g_q/(v*m_S**2)` |
| C75s | `y_chi*g_q/(v*m_S**2)` |
| C75c | `y_chi*g_q/(v*m_S**2)` |
| C75b | `y_chi*g_q/(v*m_S**2)` |
| C71 | `-y_chi*g_q/(v*m_S**2)` |

- C75q: tree-level S exchange; the 1/2 of y_χ/2 and of DirectDM's Majorana operator cancel
- C71: the top's coupling through the heavy-quark relation m_t t̄t → −(α_s/12π) GG

Dimension check: passed.

Numerical cross-check (ADROIT's UFO file through MadDM): largest relative difference 0.00068; agree.

## The library

| card | verdict | residual | remainder (operator: share) |
|---|---|---|---|
| L01 | same | 2.5e-16 | — |
| O1 | same | 2.5e-16 | — |
| L05 | same | 4.5e-16 | — |
| M_scalar | same | 2.1e-12 | — |

# Exclusion limits: majorana_scalar

A bespoke interaction (DM8), splitting 0.0 keV; 2026-10-01.

| module | fidelity | route | validated masses (GeV) | strongest validated μ_up (at mass) |
|---|---|---|---|---|
| CRESST-III 2019 | B | direct | 10–100 | 38.4 (30 GeV) |
| DEAP-3600 (2019) | B | direct | 100–1e+03 | 2.42 (100 GeV) |
| PICO-60 C3F8 (2019) | B | direct | 10–1e+03 | 11.2 (30 GeV) |
| XENONnT SR0+SR1 | A | direct | 30–1e+03 | 0.183 (30 GeV) |

The envelope is the strongest validated limit at each mass, not a combination.

## Tier 2: neutrino telescopes, through capture in the Sun

Not in the envelope: each assumes equilibrium in the Sun and one annihilation channel.

| record | channel | strongest μ_up (at mass) | verified |
|---|---|---|---|
| icecube-1612.05949-sd | bb | 73.9 (1e+03 GeV) | yes |
| icecube-1612.05949-sd | tautau | 6.61 (1e+03 GeV) | yes |
| icecube-1612.05949-si | bb | 63.1 (1e+03 GeV) | yes |
| icecube-1612.05949-si | tautau | 5.64 (1e+03 GeV) | yes |


## Viability checklist (thermal freeze-out)

Each item for this model: checked or flagged here, assumed, applies (not yet computed: where it will be built), or does not apply (why).

**Thermal history and relic abundance**

| check | status | for this model | to be built |
|---|---|---|---|
| Relic abundance | applies, not yet computed | intended: 1 of Ωh² = 0.12; needs every annihilation channel | Bespoke models: the project's own UFO model files to MadDM (DM8's numerical cross-check; MadDM's licence to read). |
| Initial chemical equilibrium | applies, not yet computed | couples to the bath through quark: Γ against H to be computed | Next, with the relic code: Γ = n_eq⟨σv⟩ against H(T) from x ≈ 1 to freeze-out. |
| Coannihilation, resonances and thresholds | does not apply | no odd state within 20% above m_χ, no mediator near 2m_χ, no channel opening within 10% of m_χ | — |
| Sommerfeld enhancement and bound states | does not apply | every force carrier has α m_χ/M < 0.1: no long-range enhancement | — |
| Kinetic equilibrium | does not apply | no resonance or forbidden channel near m_χ = 100 GeV: scattering on the bath outlasts annihilation | — |
| Cosmological history | assumed | standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | — |
| Secluded-sector evolution | does not apply | no new state is lighter than the dark matter | — |

**Laboratory and observational searches**

| check | status | for this model | to be built |
|---|---|---|---|
| Direct detection | checked | nuclear recoils: Path 1's limits in the chosen modules | — |
| Indirect detection | applies, not yet computed | needs ⟨σv⟩ today by channel | Bespoke models through the UFO files and MadDM; antiprotons and positrons later. |
| Colliders | applies, not yet computed | couples to quark; mediators below 3 TeV (S) are produced on shell | Recasting (SModelS, CheckMATE, MadAnalysis 5), as the plan states. |
| Beam dumps and fixed-target experiments | does not apply | no new state below 3 GeV that couples to the Standard Model | — |
| Rare meson decays | does not apply | no new state below 4.79 GeV coupled to quarks | — |
| Neutrino fluxes | checked | capture in the Sun against IceCube (Path 1's telescope tier); Earth and halo not built | — |
| Flavour | does not apply | one coupling for every quark and lepton, or none | — |
| Precision measurements | does not apply | no light invisible Higgs or Z decay, no electroweak multiplet | — |
| Stellar and supernova cooling | does not apply | no new state below 1 GeV | — |

**Cosmology and astrophysics**

| check | status | for this model | to be built |
|---|---|---|---|
| Dark matter decay, if metastable | does not apply | stable under the stated symmetry, if it is exact (symmetry-breaking operators not checked) | — |
| Free streaming | does not apply | a freeze-out relic of 100 GeV is cold | — |
| BBN and dark radiation | does not apply | no new state below 0.02 GeV, so none is in equilibrium at BBN (mediator lifetimes not computed) | — |
| CMB energy injection | applies, not yet computed | s-wave annihilation into visible states at recombination: Planck's p_ann | Next: Planck's limit on p_ann = f_eff⟨σv⟩/m_χ, for the spin-1 models first. |
| Self-interactions | does not apply | σ/m ≈ 1.7e-15 cm²/g (Born, contact), below 0.01 cm²/g | — |
| Scattering with the cosmological plasma | does not apply | the dark matter is above 1 GeV and no state is below 1 MeV | — |

**Theoretical consistency**

| check | status | for this model | to be built |
|---|---|---|---|
| Unitarity | checked | no axial coupling of a massive vector breaks eq. 2.8 of arXiv:1510.02110 | — |
| Anomaly cancellation | checked | no anomalous U(1) and no unchecked axial coupling | — |
| Perturbativity | checked | every dimensionless coupling below √(4π) | — |
| Vacuum structure | applies, not yet computed | new scalars: the potential is not yet part of the model | Phase 2. |
| Stability mechanism | checked | the stated parity keeps the dark matter stable | — |
| EFT validity | checked | every mediator is heavy enough for the contact interaction | — |

Totals: checked 7, assumed 1, applies, not yet computed 6, does not apply 14.


## The contract

Dropped:
- couplings of S to leptons and gauge bosons
- mixing of S with the Higgs boson
- S propagation (contact limit; m_S ≫ q)

Assumptions:
- one universal coupling g_q for every quark, times m_q/v

Masses:
- chi: 100 GeV: a reference point; the limits are computed at masses_gev
- S: 500 GeV: heavy compared with the momentum transfer, so a contact interaction

Couplings:
- y_chi: 0.5: an illustrative value
- g_q: 1.0: Higgs-like alignment: each quark couples as its Yukawa coupling

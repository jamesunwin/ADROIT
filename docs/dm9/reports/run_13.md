# DM9 agents: Path 1 for Complex scalar DM with vector Z' portal to quarks

### Constraints proposed by the scout for Complex scalar DM with vector Z' portal to quarks (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Planck relic abundance | relic_density | applies_with_assumptions | arXiv:1807.06209 (2018) | standard thermal freeze-out; phi and phi* make up all DM |
| ATLAS monojet 139 fb^-1 | collider | needs_calculation | arXiv:2102.10874 (2021) | Recast the vector-mediator limits, given for Dirac fermion DM, to scalar DM. The Z' width and invisible cross section change for a complex scalar. |
| CMS monojet | collider | needs_calculation | arXiv:2107.13021 (2021) | Rescale the fermion-DM vector simplified-model limits to the complex scalar: Z'->phi phi* partial width and production cross section. |
| ATLAS dijet resonance | collider | applies_with_assumptions | arXiv:1910.08447 (2019) | narrow Z' width; the dijet branching ratio follows from g_q, g_chi and the scalar invisible width |
| CMS dijet resonance | collider | applies_with_assumptions | arXiv:1911.03947 (2019) | narrow-width leptophobic Z' with universal quark coupling |
| Monojet + dijet for vector mediator (Majorana, axial) | collider | needs_calculation | arXiv:1509.07867 (2015) | Redo the analysis for vector couplings and complex scalar DM. The study is for an axial-vector mediator with Majorana DM. |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A22 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Uncomputed relic density means it is unknown which couplings give viable DM; this could change all conclusions. |
| A25 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | critical | Tree-level vector SI scattering is strongly constrained; skipping this likely omits the dominant exclusion. |
| A27 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (Zp) are produced on shell) | critical | Dijet resonance searches at 2 TeV strongly constrain g_q; their absence could miss a dominant limit. |
| A4 | model | No stabilising symmetry stated; minimal Z2 with phi odd, all else even, chosen. | critical | Without Z2, phi could decay, removing the DM candidate; the choice is what makes the analysis exist. |
| A5 | model | relic_fraction = 1 and standard cosmology, as nothing else stated. | critical | Taking relic_fraction=1 sets the full local density in DD/ID; a smaller fraction weakens all exclusions proportionally. |
| A1 | model | q represents all six quark flavours (3 generations of up and down types) with one universal vector coupling; electric charge set to 0 as placeholder since it varies by flavour. | material | Flavour-universal coupling fixes isospin-symmetric nucleon couplings; non-universal charges would change DD rates and collider dijet constraints. |
| A10 | model | left out of the model: Dark Higgs/Stueckelberg mechanism for Zp mass and any anomaly-cancelling fermions. | material | A dark Higgs and anomaly fermions add states and channels; anomalies with quark-only charges require extra content affecting collider bounds. |
| A12 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | material | Nonstandard cosmology would shift the coupling required for Ωh²=0.12, moving the viable band. |
| A16 | approximation | The library cards describe fermion DM with nucleon couplings, so none matches this model. | material | No library card for scalar DM means the existing limits cannot be reused; recasting errors could shift exclusions. |
| A20 | approximation | left out of the derivation: Kinetic mixing, lepton couplings, seagull term and Higgs portal, as dropped in the ModelSpec. | material | Same omissions as A6–A9; their inclusion would typically tighten limits. |
| A23 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | material | If phi never thermalises, freeze-in replaces freeze-out, changing the relic coupling by orders of magnitude. |
| A24 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | material | Duplicates A12; it changes the coupling–relic mapping. |
| A6 | model | left out of the model: Higgs portal |phi|^2|H|^2 and phi quartic self-coupling. | material | A Higgs portal adds scalar SI scattering and annihilation channels, raising DD rates and changing the relic abundance. |
| A7 | model | left out of the model: Zp–photon/Z kinetic mixing. | material | Kinetic mixing adds lepton/proton-charge couplings and dilepton collider limits, generally tightening constraints. |
| A8 | model | left out of the model: Zp couplings to leptons (not specified). | material | Lepton couplings would add dilepton LHC bounds and annihilation channels; omitting them makes constraints conservative. |
| A11 | model | left out of the model: Loop-induced interactions. | minor | Loop effects are subleading next to the tree-level vector coupling, which already gives coherent SI scattering. |
| A13 | approximation | The ModelSpec term text phi* i∂phi − i(∂phi*)phi is identified with DirectDM's (phi* i∂↔_μ phi). | minor | A sign or normalisation error would rescale the DD rate by a factor of order 1–4. |
| A14 | approximation | The universal vector coupling g_q applies to all quarks. | minor | This restates A1 at the derivation level; it fixes f_p=f_n, so there is no interference cancellation. |
| A15 | approximation | Five-flavour scheme, since m_Zp = 2000 GeV > m_Z. | minor | The five-flavour matching is appropriate at the matching scale; it has negligible effect on SI vector rates. |
| A17 | approximation | left out of the derivation: Top-quark vector current: a heavy conserved vector current gives no tree-level gluon operator, so it does not appear in the 5-flavour basis. | minor | Correct: a conserved heavy vector current decouples, so dropping it has no effect on nucleon vector charges. |
| A18 | approximation | left out of the derivation: Zp propagator momentum dependence (q²/m_Zp² corrections). | minor | q²/m_Zp² ~1e-8 at DD momentum transfer, which is negligible. |
| A19 | approximation | left out of the derivation: Loop-induced operators, including running from m_Zp to m_Z. | minor | A vector current does not run at leading order; loop effects are percent-level. |
| A2 | model | Broken phase: model written with Dirac quarks and massive Zp. | minor | Broken-phase Dirac/massive Zp description is standard; it only matters if the mass origin adds states. |
| A21 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | minor | Vector nucleon charges are exact (2,1); hadronic uncertainty here is small. |
| A26 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | minor | Scalar vector-mediated annihilation is p-wave, so ID is weak; its omission barely matters. |
| A28 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | minor | Solar capture limits are subdominant to direct detection for SI scattering. |
| A29 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | minor | P-wave annihilation is suppressed at recombination, so CMB limits are weak. |
| A3 | model | U(1)' charges set to 1 for phi and q; strengths absorbed into g_chi and g_q. | minor | Unit charges are absorbed into couplings; this is a pure reparametrisation with no physical change. |
| A30 | validity | Vacuum structure: applies, not yet computed (new scalars: the potential is not yet part of the model) | minor | The missing potential leaves vacuum stability unassessed; this has little effect on the DM phenomenology given. |
| A31 | prior | no priors: frequentist limits | minor | Frequentist versus Bayesian treatment shifts limits only modestly; none were computed anyway. |
| A9 | model | left out of the model: Seagull term g_chi^2 Zp^2 |phi|^2 from covariant derivative. | minor | The seagull term affects only phi phi→ZpZp, open for m_phi>m_Zp=2 TeV; this modestly changes relic density there. |

Added by the audit agent (its own, not the code's inventory):
- Standard Halo Model local density 0.3 GeV/cm³ and Maxwellian velocities for direct detection.
- Zp width assumed narrow/perturbative, with g_q and g_chi in the perturbative range.
- phi taken as a complex (not real) scalar; a real scalar has no vector current and so no tree-level coupling.
- No Zp coupling to the chi/phi sector beyond the vector current, i.e. no mass splitting turning scattering inelastic.
- Heavy-quark contributions to nucleon vector charges set to zero (valence-only).


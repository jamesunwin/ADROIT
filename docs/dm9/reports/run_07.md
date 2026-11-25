# DM9 agents: Path 1 for Dirac fermion DM with vector Zp mediator coupling to quarks

### Constraints proposed by the scout for Dirac fermion DM with vector Zp mediator coupling to quarks (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| ATLAS monojet search, vector simplified model (139 fb^-1) | collider | applies_with_assumptions | arXiv:2102.10874 (2021) | benchmark g_q=0.25, g_chi=1, no lepton coupling; minimal Zp width; flavour-universal quark couplings |
| CMS monojet / mono-V search, vector mediator | collider | applies_with_assumptions | arXiv:1712.02345 (2017) | benchmark g_q=0.25, g_chi=1; minimal width |
| ATLAS dijet resonance search | collider | needs_calculation | arXiv:1910.08447 (2019) | Compute sigma(pp->Zp)×BR(Zp->qq) and width for the candidate's g_q, g_chi at M_Zp=2 TeV; compare with the published limit on the Zp quark coupling. |
| Relic density in s-channel Zp simplified model | relic_density | needs_calculation | arXiv:1509.07867 (2015) | Recompute freeze-out for Dirac DM with vector couplings (s-wave chi chī->qq̄ via Zp) at m_chi=100 GeV, M_Zp=2 TeV; paper treats Majorana axial-vector case. |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A13 | approximation | The card is left empty: M_vector is a nucleon-level card, while this model is specified at quark level. | critical | The empty card is why no direct-detection limit was produced; filling it gives SI vector coupling 3 g_q g_chi / m_Zp² and very strong exclusion. |
| A18 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Not computed; until it is, the parameter point is not validated against Ωh² = 0.12. |
| A20 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | critical | This is the same assumption as A9; a non-standard history changes the relic-motivated couplings. |
| A21 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | critical | Not computed; for vector SI coupling this is likely the dominant exclusion. |
| A23 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (Zp) are produced on shell) | critical | Not computed; dijet resonance searches on a 2 TeV Zp likely constrain g_q strongly. |
| A5 | model | relic_fraction = 1 and standard cosmology assumed. | critical | Every direct and indirect limit scales with the relic fraction (squared for annihilation); a subdominant fraction would weaken exclusions. |
| A9 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | critical | Non-standard cosmology would shift the coupling that gives the relic abundance, and so whether a parameter point is viable. |
| A1 | model | q represents all six quark flavours (3 generations of up- and down-type) with one universal vector coupling g_q; electric charge set to 0 as placeholder since only Zp couplings matter. | material | Non-universal or partial quark couplings would change nucleon couplings, LHC dijet rates and annihilation channels; the zero electric charge matters only for loop mixing. |
| A10 | approximation | g_q is universal and flavour-diagonal over all quarks. | material | This duplicates A1; flavour non-universality would change the u/d nucleon weights and could induce flavour constraints. |
| A12 | approximation | No Zp couplings to leptons, and no kinetic mixing. | material | Loop-induced kinetic mixing would give a lepton coupling and stronger dilepton resonance bounds, tightening limits. |
| A15 | approximation | left out of the derivation: Loop-induced mixing, including Zp–photon/Z mixing through quark loops. | material | Quark-loop mixing with photon/Z adds a small nucleon and lepton coupling, mainly affecting LHC dilepton reach. |
| A19 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | material | If chi never thermalizes, the freeze-out picture fails and the viable couplings change. |
| A22 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | Not computed; s-wave quark annihilation gives gamma-ray limits that matter at low m_chi. |
| A25 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | material | Not computed; for s-wave annihilation it excludes light m_chi below about 10 GeV. |
| A6 | model | left out of the model: Zp couplings to leptons, Higgs, or kinetic mixing with photon/Z (not stated). | material | Adding lepton couplings or kinetic mixing would bring in dilepton and electron-recoil limits, which are generally stronger. |
| A8 | model | left out of the model: Loop-induced couplings and anomaly-cancelling states. | material | Anomaly-cancelling fermions and loop couplings could add collider signatures and mixing that tighten bounds. |
| A11 | approximation | m_Zp = 2000 GeV is far above m_Z, so the five-flavour scheme applies at μ = m_Z. | minor | With m_Zp at 2 TeV the five-flavour scheme at μ = m_Z is well justified; matching errors are small. |
| A14 | approximation | left out of the derivation: Top-quark vector current: a conserved vector current of a heavy quark does not match onto the gluon operators at tree level, so it gives no term. | minor | This omission is correct at tree level; any residual top effect is loop-suppressed. |
| A16 | approximation | left out of the derivation: Momentum-dependent Zp propagator corrections of order q²/m_Zp². | minor | q²/m_Zp² is about 1e-8 for nuclear recoils, so the correction is negligible. |
| A17 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | minor | For vector couplings the nucleon inputs are exact charge counting; running uncertainty is small. |
| A2 | model | No stability symmetry stated; minimal Z2 chosen: chi odd, Zp and SM even. | minor | A different stabilizing symmetry would not change tree-level phenomenology unless it allowed extra decays or operators. |
| A24 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | minor | Solar neutrino bounds are subdominant to direct detection for SI vector coupling. |
| A26 | prior | no priors: frequentist limits | minor | Frequentist versus Bayesian treatment shifts limit boundaries only modestly. |
| A3 | model | Zp is a real massive vector; origin of its mass (Higgs/Stueckelberg) unspecified. | minor | How Zp gets its mass leaves tree-level rates unchanged but could add light states that open new channels. |
| A4 | model | Written in broken phase. | minor | Writing the model in the broken phase is a convention and does not move any result. |
| A7 | model | left out of the model: Dark Higgs or mass-generating sector for Zp. | minor | A light dark Higgs could open chi chi → Zp h' channels and lower the relic abundance. |

Added by the audit agent (its own, not the code's inventory):
- chi assumed Dirac fermion with vector coupling g_chi; if Majorana, the vector current vanishes and SI scattering disappears, removing direct-detection limits.
- Narrow-width Zp assumed; large couplings give a broad Zp, invalidating on-shell collider treatment.
- Pure vector couplings (no axial part) assumed; an axial part would add SD and velocity-suppressed terms and alter the CMB s-wave assumption.
- Perturbativity and unitarity of the g_q, g_chi values assumed, not checked.
- The specific m_chi and coupling values are assumed without stating them.


# DM9 agents: Path 1 for Dirac fermion DM with Yukawa-like scalar mediator to quarks

### Constraints proposed by the scout for Dirac fermion DM with Yukawa-like scalar mediator to quarks (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Thermal relic abundance (Planck Omega h^2) | relic_density | applies_with_assumptions | arXiv:1807.06209 (2018) | standard thermal freeze-out; simplified model with phi (500 GeV) as the full completion; phi width from g_chi, g_q only |
| Fermi-LAT dwarf spheroidal gamma rays | indirect_detection | applies_with_assumptions | arXiv:1503.02641 (2015) | bb final state dominant; symmetric chi/chibar population; J-factors as published |
| CMS monojet scalar-mediator limit | collider | applies_with_assumptions | arXiv:2107.13021 (2021) | benchmark couplings g_q=1, g_chi=1 or rescaled; minimal mediator width; production via gg to phi through top loop |
| ATLAS monojet search | collider | needs_calculation | arXiv:2102.10874 (2021) | Recast the model-independent visible cross-section limits for the gg to phi(to chi chibar)+jet signal at m_phi=500, m_chi=100 GeV. |
| Higgs-singlet mixing completion: Higgs data and EWPD | collider | needs_calculation | arXiv:1305.3452 (2013) | Map g_q to the Higgs-singlet mixing angle (g_q = sin theta) and compute the Higgs signal-strength reduction, h to phi phi, and oblique parameters. |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A13 | approximation | No M_scalar card matches: that card is nucleon-level, while this model is quark-level with Yukawa weighting. | critical | With no matching card, the direct-detection path is unvalidated, so the quark-to-nucleon mapping could be wrong by large factors. |
| A19 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Relic abundance is not computed, so no coupling is fixed and no viability verdict follows. |
| A22 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | critical | Direct detection is not run, so the leading constraint is missing. |
| A24 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (phi) are produced on shell) | critical | Collider bounds on an on-shell 500 GeV top-philic phi could exclude much of the parameter space and are not computed. |
| A4 | model | No stabilizing symmetry stated: minimal Z2 with chi odd, phi and SM even. | critical | Without the assumed Z2, chi could decay and every DM limit would be void. |
| A5 | model | DM supplies full relic abundance; standard cosmology. | critical | If chi is subdominant or cosmology is non-standard, the relic-fixed couplings and the rescaling of experimental limits change qualitatively. |
| A8 | model | left out of the model: Loop-induced phi-gluon and phi-photon couplings (e.g. via top loop) as explicit terms. | critical | The top-loop phi-gluon coupling drives gg→phi production at colliders and the gluon term in nucleon scattering; omitting it would badly underestimate both. |
| A1 | model | Single field q represents all six quark flavors (u,d,s,c,b,t), with flavor dependence entirely in the m_q/v factor and universal g_q. | material | Lumping all flavours with m_q/v weighting makes top and bottom dominate; a non-universal pattern would shift relic, collider and direct-detection rates either way. |
| A10 | approximation | Five-flavour scheme, since m_phi = 500 GeV > m_Z. | material | The justification is wrong: the top must be integrated out at matching; if its gluonic contribution is lost, the nucleon coupling is underestimated. |
| A11 | approximation | Coupling g_q is universal across quark flavours, with Yukawa weighting m_q/v. | material | Same as A1: flavour-specific couplings would reweight every channel. |
| A12 | approximation | GG denotes G^a_{mu nu}G^{a mu nu}; heavy-quark decoupling is taken at leading order. | material | Leading-order heavy-quark decoupling misses order 10–30% QCD corrections to the gluonic nucleon coupling. |
| A16 | approximation | left out of the derivation: phi couplings to leptons, gauge bosons, Higgs; Higgs-phi mixing | material | Same as A6/A7: extra couplings would add channels and nucleon scattering. |
| A18 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Tree-level matching and the chosen nucleon inputs (strange content, gluon fraction) move the cross-section by tens of percent. |
| A20 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | material | If chi is not in equilibrium, freeze-out fails and the relic calculation must change to a non-thermal production mechanism. |
| A23 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | material | Indirect detection is not computed, and the velocity dependence of annihilation decides its relevance. |
| A26 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | material | CMB bounds matter only for s-wave annihilation; they are not computed and depend on chi's spin and CP. |
| A6 | model | left out of the model: phi couplings to leptons, gauge bosons, and Higgs (not specified). | material | Extra phi couplings would add annihilation and decay channels, lowering the relic-preferred g and changing collider branching ratios. |
| A7 | model | left out of the model: phi self-interactions and Higgs-portal mixing. | material | Higgs-phi mixing would add a Higgs-mediated nucleon coupling, which could strengthen direct-detection bounds. |
| A9 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | material | A non-standard thermal history would shift the relic-preferred coupling by order-one factors. |
| A14 | approximation | left out of the derivation: Loop corrections beyond the leading heavy-top matching onto GG | minor | Higher-loop matching corrections are percent-level to tens of percent on the nucleon coupling. |
| A15 | approximation | left out of the derivation: phi momentum dependence (q^2/m_phi^2 corrections) | minor | Momentum transfer is far below m_phi = 500 GeV, so the correction is negligible. |
| A17 | approximation | left out of the derivation: Running from m_phi to m_Z (left to DirectDM) | minor | Running from m_phi down to m_Z gives modest logarithmic shifts, provided DirectDM handles it. |
| A2 | model | q electric_charge left as 0 placeholder since it lumps up-type (+2/3) and down-type (−1/3) quarks. | minor | A zero charge removes the quark-loop phi-photon coupling, which slightly underestimates gamma-line and diphoton signals. |
| A21 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | minor | This duplicates A9. |
| A25 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | minor | Solar-capture limits are usually weaker than direct detection for spin-independent scattering. |
| A27 | validity | Vacuum structure: applies, not yet computed (new scalars: the potential is not yet part of the model) | minor | Vacuum stability constrains phi couplings that are absent from the model. |
| A28 | prior | no priors: frequentist limits | minor | This is a statistical framing choice; there are no limits yet to affect. |
| A3 | model | v = 246 GeV (SM Higgs vev). | minor | The standard vev only sets the Yukawa normalisation; any other value would rescale g_q trivially. |

Added by the audit agent (its own, not the code's inventory):
- The DM spin and the CP of the chi-phi coupling are assumed; these set whether annihilation is s- or p-wave and whether scattering is spin-independent.
- phi is taken as a CP-even scalar rather than a pseudoscalar.
- A narrow phi width is assumed, set by quark and chi channels only.
- The standard halo model and local DM density are assumed for direct detection.
- Annihilation to phi phi is ignored when m_chi > m_phi.


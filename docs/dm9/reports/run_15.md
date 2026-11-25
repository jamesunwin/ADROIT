# DM9 agents: Path 1 for Dirac fermion DM with pseudoscalar mediator coupled to down-type quarks

### Constraints proposed by the scout for Dirac fermion DM with pseudoscalar mediator coupled to down-type quarks (to be verified by a person)

| constraint | class | applicability | reference | assumptions or calculation needed |
|---|---|---|---|---|
| Fermi-LAT dwarf spheroidal annihilation limits | indirect_detection | applies_with_assumptions | arXiv:1503.02641 (2015) | chi chibar -> a* -> b bbar dominates through the m_b/v Yukawa scaling; s-wave pseudoscalar annihilation; factor 1/2 in flux for Dirac DM with no asymmetry; chi chibar -> aa closed because m_a > m_chi |
| Planck relic abundance | relic_density | applies_with_assumptions | arXiv:1807.06209 (2018) | Standard thermal freeze-out; Symmetric Dirac population; Annihilation mainly to b bbar, plus s sbar and d dbar |
| Planck CMB energy-injection bound | cosmology | applies_with_assumptions | arXiv:1807.06209 (2018) | s-wave annihilation at recombination; f_eff for the b bbar channel |
| Fermi-LAT gamma-ray line limits for coy DM | indirect_detection | needs_calculation | arXiv:1702.02580 (2017) | Loop-induced chi chibar -> gamma gamma with only down-type quarks in the loop (b dominant), compared with the Fermi-LAT line limit at E = 100 GeV. |
| CMS monojet / mono-V pseudoscalar search | collider | needs_calculation | arXiv:1703.01651 (2017) | Recast with production through b-quark-loop gg -> a and b bbar -> a (no top coupling); the expected rate is strongly suppressed relative to the paper's benchmark. |
| Flavour constraints on pseudoscalar mediators | flavour | needs_calculation | arXiv:1412.5174 (2014) | Loop-induced b -> s and Bs-mixing contributions from the down-type-only coupling structure, for m_a = 500 GeV. |
| One-loop spin-independent scattering | direct_detection | needs_calculation | arXiv:2609.12336 (2026) | One-loop matching of the a-exchange operators onto SI quark and gluon operators, for input to ADROIT's existing direct-detection modules. |

## Assumption audit (DM9)

| item | category | assumption | impact | effect |
|---|---|---|---|---|
| A17 | validity | Relic abundance: applies, not yet computed (intended: 1 of Ωh² = 0.12; needs every annihilation channel) | critical | Ωh² is uncomputed; it fixes the target couplings, so viability is undetermined. |
| A21 | validity | Indirect detection: applies, not yet computed (needs ⟨σv⟩ today by channel) | critical | chi chi→bb via the pseudoscalar is s-wave, so dwarf and GC gamma limits likely exclude thermal masses below about 100 GeV. |
| A25 | validity | CMB energy injection: applies, not yet computed (s-wave annihilation into visible states at recombination: Planck's p_ann) | critical | s-wave bb annihilation injects energy at recombination, so Planck p_ann excludes thermal chi below about 30 GeV. |
| A3 | model | No stability symmetry stated: minimal Z2 with chi odd, a and SM even. | critical | Without Z2 stability, chi could decay or mix, and the whole DM interpretation and every limit would change. |
| A10 | approximation | No couplings of a to up-type quarks, leptons, or the top. | material | Adding up-type quark or lepton couplings opens channels such as tt and ττ, which strengthens indirect, collider and flavour limits. |
| A12 | approximation | left out of the derivation: Momentum dependence of the a propagator (q^2/m_a^2 corrections) | material | For m_a at or below about 100 MeV, propagator q² dependence changes recoil spectra and weakens the contact-limit approximation. |
| A13 | approximation | left out of the derivation: Quark-loop-induced a couplings to gluons and photons (C74-type, dipoles) | material | Loop-induced gluon and photon couplings add collider and gamma-line signals, so the omission makes constraints too weak. |
| A15 | approximation | left out of the derivation: Mediator self-interactions and Higgs mixing | material | As in A7, Higgs mixing would add unsuppressed spin-independent scattering, so omitting it underestimates direct-detection reach. |
| A16 | approximation | DirectDM in the 5-flavour theory, with its running to 2 GeV and its nucleon inputs; tree-level matching | material | Tree-level matching and nucleon pseudoscalar inputs (pion/eta poles) carry tens-of-percent uncertainty on the already q⁴-suppressed rates. |
| A18 | validity | Initial chemical equilibrium: applies, not yet computed (couples to the bath through quark: Γ against H to be computed) | material | If equilibrium fails for small couplings, freeze-in applies and the relic-to-coupling map changes completely. |
| A19 | convention | Cosmological history: assumed (standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release) | material | This duplicates A8; any deviation rescales the relic coupling. |
| A22 | validity | Colliders: applies, not yet computed (couples to quark; mediators below 3 TeV (a) are produced on shell) | material | bb+MET and mono-jet searches could exclude light m_a and sizable couplings. |
| A24 | validity | Flavour: applies, not yet computed (couplings single out flavours (individual fermions, or several in one term)) | material | Light a in B→K a or B_s mixing could exclude low m_a strongly. |
| A5 | model | relic_fraction = 1 and standard cosmology, as none stated. | material | If chi is subdominant, direct and indirect rates scale down by the fraction or its square, weakening the limits. |
| A6 | model | left out of the model: Loop-induced a couplings to gluons/photons via quark loops. | material | Omitting quark-loop a→gg/γγ underestimates collider gg→a production and alters a decays, so collider limits are too weak. |
| A7 | model | left out of the model: Mediator self-interactions and Higgs portal mixing (not specified). | material | Higgs-portal mixing would add unsuppressed spin-independent scattering and strengthen direct-detection limits greatly. |
| A8 | convention | cosmology: standard: radiation domination from a reheating temperature far above m_χ/20, Standard Model degrees of freedom, no late entropy release | material | Non-standard cosmology rescales the coupling that gives Ωh²=0.12, shifting the viable region either way. |
| A1 | model | Quarks d, s, b kept as separate fields because couplings scale with m_q/v (not universal). | minor | Treating d, s and b separately is exact for mass-proportional couplings; universal couplings would raise light-quark weight and strengthen nucleon-level limits. |
| A11 | approximation | M_pseudoscalar card is nucleon-level, so it is not an exact match; no library card used. | minor | Skipping a nucleon-level card avoids a mismatch; DirectDM does the matching instead, so the effect is small. |
| A14 | approximation | left out of the derivation: Running between m_a and m_Z beyond DirectDM's own treatment | minor | Extra running gives only percent-level shifts in Wilson coefficients. |
| A2 | model | v = 246 GeV; quark masses are PDG values (m_d=4.7 MeV, m_s=93 MeV, m_b=4.18 GeV). | minor | Quark-mass and v uncertainties shift the couplings by a few percent (more for m_s), moving rates slightly up or down. |
| A20 | validity | Direct detection: applies, not yet computed (nuclear recoils: run Path 1's exclusion) | minor | Pseudoscalar-pseudoscalar scattering is q⁴-suppressed, so direct detection is unlikely to drive the conclusion. |
| A23 | validity | Neutrino fluxes: applies, not yet computed (capture in the Sun: run Path 1's exclusion) | minor | Spin-dependent capture is velocity-suppressed for this operator, so solar neutrino limits are weak. |
| A26 | validity | Vacuum structure: applies, not yet computed (new scalars: the potential is not yet part of the model) | minor | An unspecified potential could add a–h mixing (cf. A7) but rarely changes DM limits directly. |
| A27 | prior | no priors: frequentist limits | minor | A Bayesian treatment would change limit interpretation only modestly. |
| A4 | model | Model written below EWSB (broken phase). | minor | A broken-phase Lagrangian is fine at low energy; gauge-invariance completions could add couplings that tighten constraints. |
| A9 | approximation | The i in both pseudoscalar bilinears is as written (a chi-bar i g5 chi, a q-bar i g5 q), so the sign is positive. | minor | The overall sign matters only for interference, and none is present with a single mediator. |

Added by the audit agent (its own, not the code's inventory):
- chi assumed Dirac (or Majorana) with a fixed normalization; this changes annihilation and scattering by a factor of 2–4.
- Pure CP-conserving pseudoscalar couplings assumed; any scalar admixture gives unsuppressed spin-independent scattering.
- Narrow-width a assumed, with width set only by quark and chi decays.
- Non-resonant freeze-out assumed; near m_a≈2m_chi the relic and indirect estimates fail.
- DM halo and local density standard (0.3–0.4 GeV/cm³, SHM velocities) for direct and indirect detection.


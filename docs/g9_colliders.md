# G9 — Colliders for a generic model (2026-10-15)

Milestone G9 of [`freeze_out_build.md`](freeze_out_build.md). The generic route's LHC search was undecided in G6
("the LHC (G9)"). It now comes from the model's own spectrum where a production table exists. Elsewhere it stays
undecided, with the reason.

## What was built

`adroit/parameter_space/portals/generic_lhc.py`, read by `searches.lhc_spectrum`, `lhc_search` and
`higgs_signal`:
- **An SLHA spectrum for SModelS.** Every Z₂-odd state of the model, at any mass, carries its quantum numbers. A
  heavy partner is produced whether or not it coannihilates, so the bath's mass cut does not apply here.
- **Production at 13 TeV by quantum numbers**, from the tables the library already uses:

  | the produced multiplet | the table | as the library's |
  |---|---|---|
  | a pure fermion SU(2) triplet, Y = 0 (wino-like dark matter) | C₁±C₁∓, C₁±N₂ (aNNLO+NNLL) | wino |
  | a pure fermion SU(2) doublet, Y = ½ (higgsino-like dark matter) | C₁C₁, N₁C₁±, N₂C₁±, N₁N₂ | higgsino |
  | a colour-triplet scalar partner decaying to χ and a quark | the stop table (QCD only: a lower bound) | t-channel uR, dR |
  | a charged singlet scalar partner decaying to χ and a lepton | the right-handed slepton table | t-channel eR, … |

  A wino- or higgsino-like multiplet is split at one loop (`generic_today.splitting`). Its charged state decays to
  the neutral one and a pion with the library's width, so SModelS sees disappearing tracks where they apply.
- **Named reasons where no table applies:**
  - a mixed dark matter state (singlet–doublet, doublet–triplet): the pure tables do not apply;
  - a partner with no two-body decay to the dark matter and an SM fermion, which gives SModelS no topology;
  - any other produced multiplet;
  - a mass outside the table.
- **The Higgs's signal strength** for a model whose SM-like h mixes with a new scalar: μ = c⁴Γ_SM/(c²Γ_SM + Γ_new),
  with c² the h's share of H⁰ and Γ_new its width into new states. It is tested against ATLAS's combined μ, the
  library's record. (Since RF23-01, 2026-10-23: the state is the one at the measured 125 GeV, and the formula is used
  only where its couplings are one common rescaling of the SM Higgs's, CP-even, with no new charged or coloured state
  in its loops; otherwise undecided, named: docs/hadronic_window.md.)
- **The invisible widths of h and Z**, the plan's other item here, were already computed for a generic model
  (`GenericModel.invisible`, `generic_checks.invisible_widths`) and read by the scan's invisible-width searches.
- **A coloured partner's production is QCD only**, as for the library's t-channel partners. An exclusion stands,
  but "allowed" is not shown (`searches._qcd_lower_bound` now reads the generic spectrum too).

## Validation (`scripts/g9_collider_gate.py`, `docs/g9/collider_gate.json`; offline)

**The library's families**, each at a point inside its table, through SModelS 3.2.1:

| family | point | σ (pb): library / generic | SModelS r: library / generic |
|---|---|---|---|
| wino | m = 600 GeV | 0.0305 / 0.0305 | 1.252 / 1.216 |
| higgsino | m = 600 GeV | 0.0158 / 0.0158 | 0.0089 / 0.0089 |
| t-channel uR (Majorana χ) | m_χ = 300, m_φ = 1200 GeV, y = 1 | 0.00188 / 0.00188 | 0.663 / 0.663 |
| t-channel eR (Majorana χ) | m_χ = 100, m_φ = 300 GeV, y = 1 | 0.00175 / 0.00175 | 0.487 / 0.487 |

The wino's r differs by 3%: the disappearing-track lifetime follows the splitting, which is 165.4 MeV (G1's one-loop
formula) against the library's 165 MeV. All four agree within the gate's 5%.

**The zoo's development half, with the tables alone (as first built):** each of its 12 models gets an LHC verdict
or a named reason. None gets a verdict at its benchmark:
- the wino's thermal mass (2.86 TeV) is beyond the electroweakino table;
- Dedes & Karamitros's dark matter is a 50% doublet–triplet mixture;
- De Simone et al.'s and Harz & Petraki's coloured partners have no stated decay to the dark matter;
- the other eight models produce states no table covers (singlets, a complex scalar triplet, a vector, a
  vectorlike lepton).

Choubey et al.'s mixing gives μ = 0.999. (Since RF23-01, 2026-10-23, undecided: its charged triplet scalar couples to
the 125 GeV state, and its h → γγ loop is outside the formula.)

With the tables alone, the gate was met in its wording only: the generic route decided the LHC only for the
library's own families. MadGraph's production per model (below) followed.

## MadGraph production per model (decision D22, 2026-10-15)

Where no table applies, or the dark matter is a mixed state, the model's own pair production comes from MadGraph
(`constraints.pair_production`):
- **The run.** G2's UFO export at the point (with u, d, s and c massless, the four-flavour proton's partons) goes
  through MadGraph 3.8 at 13 TeV, `generate p p > vis odd QCD<=2 QED<=2`. Here `vis` is every odd state but the dark
  matter, so a dark-matter pair, which leaves nothing to see, is not generated. The run is LO, NNPDF2.3 LO, scale
  H_T/2, 10,000 unweighted events, offline and on one core.
- **Every tree-level diagram** (the re-audit's R17-1, 2026-10-17). Until then the process line had no coupling
  orders, and MadGraph keeps only the lowest weighted order (QCD once, QED twice) across the whole multiprocess: a
  coloured partner's t-channel exchange of the dark matter and its interference with QCD were dropped, and a model
  with a coloured and an electroweak partner lost its electroweak pairs. The orders now admit every 2 → 2 tree
  diagram of the exported model (`pair_production.tree_orders`), every pair a tree diagram makes from the proton's
  partons must be among the subprocesses (`check_generated`), and both caches carry the command. On the way, the
  UFO's colour indices became the created particles' (as MadGraph's own models write them, each generator with the
  conjugate representation's sign): every colour-summed σ is unchanged (g g → φφ* equals the tree engine), but
  MadGraph could not assign the colour flow of g q → φχ, which complete production generates.
- **The cross-sections.** Each pair's σ is the total times its share of the events. Results are cached by the
  UFO's content (about 45 s a model).
- **The decays.** Every two-body channel of each new state comes from G2's vertices (`decay_table`), in the UFO's
  numbering (the export flips some Dirac fermions for MadGraph; the SLHA follows it). A new state with no open
  two-body channel would look stable to SModelS, which would wrongly test it against the long-lived searches; such
  a spectrum is not tested, and the reason is given.
- **Leading order is a lower bound.** NLO raises pair production at the LHC, so with every tree diagram and its
  interference in σ an exclusion stands and "allowed" is not shown (`searches.LO_ONLY`); the library's QCD-only
  partner tables are not a lower bound (decision D33). The assumption is checked against the tables
  (`scripts/g9_collider_gate.py`):

  | family | MadGraph LO (pb) | the table (pb) | K = table/LO |
  |---|---|---|---|
  | wino, 600 GeV (C₁C₁ + C₁N₂) | 0.0222 | 0.0305 (aNNLO+NNLL) | 1.37 |
  | slepton-like partner (eR), 300 GeV | 0.00130 | 0.00175 (NLO+NLL) | 1.35 |
  | stop-like partner (uR), 1200 GeV | 0.00138 | 0.00188 (NNLO+NNLL) | 1.36 |

**The zoo's development half with it:**

| model | LHC |
|---|---|
| Dedes & Karamitros (a doublet–triplet mixture near 100 GeV) | **excluded**: σ_LO = 0.82 pb, r = 4.4 (ATLAS-SUSY-2019-09) |
| Giacchino et al., scalar with a vectorlike lepton (Ψ± at 174 GeV) | undecided: σ_LO(Ψ⁺Ψ⁻) = 0.12 pb, r = 0.72 at LO, a lower bound |
| complex triplet, Yaguna, Choubey et al. | undecided: a charged state's decay goes through an off-shell boson |
| Das et al., the CP-violating Higgs portal, Feng et al., Athron et al. | undecided: only the dark matter is new and odd |
| De Simone et al., Harz & Petraki | undecided: the coloured partner has no stated decay |
| the wino at 2.86 TeV | undecided: beyond the electroweakino table |

**Gate: met.** Every model has its verdict or a named reason, and the library's families agree. Two development
models now reach SModelS through MadGraph.

## Off-shell decays, splittings and more verdicts (decision D26, 2026-10-15)

The owner asked for three-body widths, the pion formula for any multiplet and a wider range of verdicts.

- **Decays through an off-shell W** (`pair_production.soft_widths`, `soft_decay_table`). A new fermion with no open
  two-body channel, joined by a W vertex to a lighter new fermion with Δ < m_W, decays through W*. The widths, for
  Δ ≪ m_W and a heavy pair (Thomas & Wells; Ibe, Matsumoto & Sato):

      Γ(π) = w G_F² f_π² |V_ud|² Δ³/π · (1 − m_π²/Δ²)^{1/2}            (Δ < 1.5 GeV),
      Γ(ℓν) = w G_F² Δ⁵/(15π³) · F(m_ℓ/Δ),   F the muon-decay phase space (e, μ, and τ when Δ > m_τ),
      Γ(q q̄′) = 3 Γ(eν) · F(m_q/Δ)                                     (ud, and cs; Δ > 1.5 GeV),

  with w = (|c_L|² + |c_R|²)/g² of the pair's W vertex (2 for a wino, 1 for a higgsino), read from G2's vertices, so
  it holds for any multiplet or mixture. The decays go into the SLHA spectrum as W*'s final states.
- **The one-loop splittings** of a pure electroweak multiplet (`generic_lhc.with_loop_splittings`, the G8 formula):
  G1's tree-level masses are degenerate, so its charged states had nothing to decay to.
- **MadGraph beyond the tables**: a pure wino or higgsino outside the electroweakino table's mass range takes
  MadGraph's LO, as any other model.
- **The monojet recast for a generic model** (`searches._generic_monojet`): a model that reduces to the DMsimp spin-0
  mediator, a new even neutral scalar coupled to the dark matter and to all six quarks in proportion to the SM
  Yukawas (within 2%), CP-even or CP-odd, takes CMS's recast. The benchmark's invisible branching and width come
  from the library's scalar class at the same mediator mass; the model's own come from G2's decays.
- **MadGraph's process reused**: the generated process depends on the UFO's content apart from its parameters, so
  a scan generates it once per model and launches each point with its masses and widths (about 45 s a model,
  then a few seconds a point).

**The development half, rerun** (`docs/g9/collider_gate.json`):

| model | before | now |
|---|---|---|
| Yaguna (singlet–doublet Dirac) | undecided: N⁻ had no computed decay | reaches SModelS: σ_LO = 0.85 pb, r = 0.0049 (allowed is not shown at LO; r = 0.079 when first run, before the off-shell widths' axial weighting below) |
| Choubey et al. (singlet–triplet) | undecided: ρ⁺ had no computed decay | reaches SModelS: σ_LO = 10.4 pb, r = 0.68 |
| the wino at 2.86 TeV | undecided: beyond the table | MadGraph's σ_LO = 1.6 × 10⁻⁷ pb; no SModelS result covers it |
| the complex scalar triplet | undecided | undecided: χ⁺⁺ is a scalar, and the off-shell decays are built for fermions only |
| Dedes & Karamitros | excluded (r = 4.4) | excluded (r = 4.4) |
| Giacchino et al. | r = 0.72 at LO | r = 0.72 at LO |

The families' agreement (4 of 4) and LO's place below the tables (K = 1.35–1.37) are unchanged.

**Rerun with every tree-level diagram** (R17-1, 2026-10-17; `docs/g9/collider_gate.json` is that run): every verdict and reason as on the re-audited `25bca89`. The electroweak models' subprocesses were already complete (every diagram has the same order); the stop-like partner's LO σ moves by 0.1% (0.001383 → 0.001385 pb at y = 0.01, now with the Yukawa exchange and Φχ production), and Yaguna's r by MadGraph's sampling (0.004869 → 0.004852).

## Found on the way

| what | effect |
|---|---|
| The first version read the partners from the bath (states below 1.3 m_χ) | a heavy coloured partner was invisible to the LHC; now every odd state |
| The first version gave the higgsino three of the library's six production channels | σ 0.0106 against 0.0158 pb at 600 GeV; now the library's form |
| The first version read a mixed doublet–triplet state with the pure higgsino tables | Dedes & Karamitros "excluded" at 100 GeV with r = 1.66; now undecided, with the reason |

## Decays through an off-shell Z, and scalars' through W* or Z* (G12, the owner's point 3)

`pair_production.soft_widths` covers both bosons: for a fermion pair (|V|² + 3|A|²) with the heavy-limit width
Γ = N_c(|V|² + 3|A|²)(|f_L|² + |f_R|²)Δ⁵/(120π³m_B⁴) per SM fermion, the pion as |V|²Δ² + |A|²|q|² (the axial
current had been weighted as a vector one: the audit's G9-off-shell finding); for a scalar pair through VSS, the
same with the scalars' current. Checked against MadGraph's three-body widths (with `--hel_recycling=False`): W*
widths at Δ = 2 and 0.5 GeV, Z* at Δ ≈ 0.64 GeV, and a scalar doublet's Z* decay
(`tests/constraints/test_pair_production.py::test_the_off_shell_widths_are_madgraphs_three_body_widths`).

## Not built (the plan's other items)

- **Resonance searches for any s-channel mediator** through the width gates: the generic route has none of the
  library's dijet, dilepton, ZZ and WW recasts.
- **LEP's bounds on light charged states.** Both are planned in [`generic_route_next.md`](generic_route_next.md)
  (P1–P5).

Tests: `tests/parameter_space/test_generic_lhc.py`, `tests/constraints/test_pair_production.py` (the off-shell
widths against the library's wino width, and a pure wino's χ⁺ → χ⁰π; MadGraph's runs are marked slow).

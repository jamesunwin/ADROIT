# ADROIT: any freeze-out model — build plan

Plan of record for the owner's aim of 2026-10-13: an LLM-empowered system, with the experimental exclusions
preloaded, that adapts on the fly to any freeze-out dark matter model it is given. Drafted 2026-10-13, after the
model zoo's first development run.

Milestones are named **G0–G12, in build order**. They replace the first sketch in the release plan ("After R12",
G1–G7, written the same day). Mapping from the sketch:

| sketch | now |
|---|---|
| G7 (the zoo) | G0 |
| G1 (the perturbative route) | G1–G4 |
| G4 (direct detection) | G5 |
| G2 (long-range effects) | G7 |
| G3 (annihilation today) | G8 |
| G5 (the LHC) | G9 |
| G6 (the language-model layer) | G10–G11 |

The owner settled the decisions of section 9 on 2026-10-13. R12, the closure audit of 0.1.0, moved into G12, so
the build starts now.

## 1. Status (15 October 2026)

- **G0, the yardstick: started and running.** The model zoo (`docs/model_zoo.md`) holds 31 models and 58 sourced
  targets, with fixed development and held-out halves.
  - **New models, development half:** 0 of 6 computed; each refusal names what is missing.
  - **Controls, development half:** 6 of 6 computed, 5 of them only through the library route; 11 of 15 targets met.
- **G1: done** (2026-10-13, [`g1_mass_basis.md`](g1_mass_basis.md)): all 27 development-half benchmarks reproduce
  their papers' masses.
- **G2: done** (2026-10-13, [`g2_feynman_rules.md`](g2_feynman_rules.md)). The UFO export for MadDM comes with G4's
  cross-check.
- **G3: done** (2026-10-13, [`g3_tree.md`](g3_tree.md)): any 2 → 2 process, validated against MadGraph on 42
  processes.
- **G4: done** (2026-10-14, [`g4_generic.md`](g4_generic.md)): the generic engine and its relic density. On the
  development half, 4 of 6 new models are computed and 3 of 7 targets met; each miss is localised by MadDM or
  explained. The generic route agrees with the library's controls on 7 of 9 targets; the other two are the
  library's errors (Das et al.'s trilinears). Two departures from this plan:
  - the long-range criterion is the D4 bracket itself, since the planned screen let the wino through;
  - the generic route is opt-in in `classify` until G12 (the record says why); the owner made it the default on
    2026-10-15 (D27).

  The held-out half was run once (commit 4a410e2, ledgered): 4 of 11 new models computed, 4 of 5 targets met; the
  generic route agrees with the controls' engines on 11 of 12 targets. It found one G1 error (a charged Majorana
  field's axial current), carried to G7.
- **G5: done** (2026-10-14, [`g5_direct_detection.md`](g5_direct_detection.md)): tree-level matching of G2's vertices
  onto DirectDM's basis, the loop library (n-plets, coloured and lepton partners), inelastic scattering and the
  fallback. Validated against MadDM's quark-level coefficients (10⁻⁵–10⁻³) and the library's engines (≤ 1%). Zoo
  σ_SI: Das et al. and Bhattacharya et al. met; Choubey et al. a factor 2 in amplitude, localised to the paper's
  normalisation.
- **G6: done** (2026-10-14, [`g6_indirect.md`](g6_indirect.md)): σv today by final state, the Higgs's
  loop-induced gg, γγ and Zγ, two-body cascades through new states with boosted PPPC spectra, the CMB's f_eff
  range, the lines flagged, and the Sommerfeld effect today refused to G8. MadDM's tree-level σv today agrees to
  10⁻⁴ on every channel of nine models once its two conventions are corrected. The differences are the W and Z
  pairs near threshold, which the generic route integrates off shell. Every search reads a generic model. D11's
  pseudo-Dirac mass and pole-refinement optimisation are done. The off-shell quadrature's fix also changes the
  library's UFO portals. Zoo development half: new models 5 of 6 computed, 9 of 10 targets met (G5: 4, and 4 of 9).
- **G7: done** (2026-10-15, [`g7_long_range.md`](g7_long_range.md)): the Sommerfeld effect and bound states from the
  model's own representations, the potential read from G3's amplitudes. Gate met. The complex triplet is computed
  (2241 GeV against 2100) and met. The wino and the coloured controls agree with their library engines within 1%.
  On the development half, the new models are 6 of 6 computed with 10 of 11 targets met. The held-out half was run
  once (ledgered): the new models 9 of 11 computed, 9 of 13 met; the generic route agrees with the controls on 13 of
  14. Its one disagreement was a G6 error in the off-shell rate below threshold, now fixed. The fix moves Dedes &
  Karamitros's t1 back to 0.158 (MadDM 0.152), so the development half now stands at 9 of 11. Dark-U(1) bound
  states were added afterwards (hydrogen-like, validated on the Coulomb limit).
- **G8: done** (2026-10-15, [`g8_today.md`](g8_today.md)): the broken-phase multi-state Sommerfeld effect
  today, with the potentials boson by boson and the splittings at one loop. The wino's total σv agrees with the
  library's matrices within 4% off resonance, and the higgsino's within 4–7% to 2 TeV. A pure wino's or higgsino's
  lines take DMγSpec's resummed rate, in the library too (D21). Any pure Majorana odd n-plet's lines take ADROIT's
  own NLL resummation with the NLO Sommerfeld potential (D24, `constraints.endpoint_nll`). **The quintuplet's half
  of the gate is met:** its line at the thermal mass is the paper's within 1.7% (inside its ±4% band), and inside the band
  wherever the published figure resolves it. Other multiplets' tree-level Sommerfeld lines decide nothing since G12
  (G8-5: near a zero of the tree amplitude the resummed rate is far larger); a resummed rate carries a theory band
  (D30).
- **G9: done in part** (2026-10-15, [`g9_colliders.md`](g9_colliders.md)): an SLHA spectrum for SModelS, production
  by quantum numbers from the library's tables, and the Higgs's signal strength from mixing. The library's four
  families agree, and every development model has a verdict or a named reason. MadGraph's LO pair production per
  model followed (D22): Dedes & Karamitros's point is excluded (r = 4.4), and Giacchino et al.'s reaches SModelS
  (r = 0.72 at LO, a lower bound). Decays through an off-shell W for any fermion pair, the one-loop splittings and
  the DMsimp monojet mapping followed (D26): Yaguna's and Choubey et al.'s points now reach SModelS (r = 0.08,
  0.68). Decays through an off-shell Z, and scalars' through an off-shell W or Z, followed at G12 (MadGraph's
  three-body widths). The resonance recasts and LEP are not built.
- **G10: done** (2026-10-15, [`g10_intake.md`](g10_intake.md); $20.76 over all its passes). **Gate met as run:** in
  one final pass, all 31 agent models equal the hand-written ones under D19, 23 strictly. **Re-scored at G12** with
  the closure audit's corrected comparison (G1-1: chirality and signs resolved), 29 of 31: Okada et al.'s and Ipek
  et al.'s agent models have sign errors that the old comparison passed, so the gate is not met as re-scored.
  The gate found G2 errors (three-generation right-handed fields read as one; no Weyl currents), G1's merging of a
  vector named A with the photon, a scheme mismatch in e between a stated coupling and the kinetic mixing, and a
  doubly stated mass that G1 resolved silently; all fixed. Berlin et al.'s cos θ_W and the zoo's ε are stated, D19
  covers the vector portal, and Ipek et al.'s reference builds with a second doublet's Yukawas (D25).
- **G11: done** (2026-10-15, [`g11_benchmarks.md`](g11_benchmarks.md); $2.24, plus $0.65 for a draft that
  produced nothing and $0.18 for a draft that reproduced the n-plet splitting): 19 of 26 development targets
  recovered (18 as run). No quote fails the check after a fix to the check made after the run. Drafted code
  reaches no verdict.
- **G12: in progress** (2026-10-15, the G12 closure record). The closure audit's six reviews found 8
  critical, 29 major and 20 minor findings; all are fixed, each with a regression test. The owner's five points are
  settled (D29, D30, and the off-shell Z built).

## 2. The goal, and what "done" means

**The goal.** A model ADROIT has not seen goes in as a Lagrangian, typed or read from a paper. It comes out as:
- its relic density;
- every search's verdict on it, from the records already in the library;
- a statement of what physics was included and what was not.

No one should need to write an engine first. The owner's quintuplet showed where 0.1.0 stops: its perturbative part
is generic, but nothing generic computed it.

**Done means, measured on the zoo's held-out half, once, at G12:**
- **Coverage:** every model inside the scope of section 8 is computed or refused with a named missing piece. None
  is refused for want of a hand-written engine.
- **Accuracy:** every computed target lies within its source's uncertainty or the route's stated theory
  uncertainty. A miss outside both is a finding, recorded with its cause.
- **Agreement:** on the controls, the generic route agrees with the library's validated engines within the stated
  theory uncertainties. A disagreement is a finding.
- **Verdicts:** a generic model gets the same searches as a library model:
  - direct detection, γ rays, the CMB, antiprotons, the Sun, the LHC and invisible widths;
  - each search allowed, excluded, or undecided with its reason.

## 3. Principles

1. **The library stays first.** The standard library's engines and records are the trusted path. A model they cover
   is computed by them, as today. The generic route is the fallback for models they do not cover, and a cross-check
   on models they do (the owner, 2026-10-13: "this should enhance what we already have").
2. **The deterministic core computes; the language model translates and plans.** No number in a verdict comes from
   a language model. An agent's output, whether a model, a plan or a benchmark, is checked deterministically before
   it is used.
3. **Code an agent drafts is never run into a verdict unreviewed.** It enters the library only after a person
   reviews and validates it, as the n-plet engine did.
4. **No silent omissions.** Where a piece of physics matters and no module computes it, the report names the piece,
   and the affected numbers are refused, not guessed. Examples are the Sommerfeld effect, an off-shell final state,
   and a loop-dominated scattering rate.
5. **Every module is validated three ways:**
   - analytic limits;
   - an independent code (MadGraph, MadDM, micrOMEGAs, DirectDM);
   - the literature, through the zoo.
6. **Each step is gated on the zoo.** The development half guides the work. The held-out half is run once per gate
   milestone and ledgered.

## 4. The physics chain of the generic route

Each arrow is a milestone:

```
ModelSpec (fields, charges, Z₂ parities, couplings, terms; either phase)
  │ G1  symmetry breaking: vevs, the potential's minimum, mass matrices → physical states
  │     (masses, charges, spins, Z₂ parity) and the rotations
  ▼
the physical spectrum
  │ G2  Feynman rules in the mass basis: gauge couplings from the charges, Yukawas, the potential's
  │     trilinears and quartics, kinetic mixing — rotated; widths of every unstable state
  ▼
vertices (an in-process tree.Model; a UFO export for the independent codes)
  │ G3  every 2 → 2 process among the Z₂-odd states near m_χ, at tree level
  ▼
σ_ij→f(s) by channel
  │ G4  Gondolo–Gelmini average, Edsjö–Gondolo coannihilation, resonances, the Boltzmann equation
  ▼
Ωh²  ◄── G7 long-range effects (Sommerfeld, bound states) where α_eff m_χ/m_V ≳ 1
  │
  ├─ G5  direct detection: tree-level matching → DirectDM → the xenon and argon records
  ├─ G6  annihilation today: σv(v → 0) by final state, cascades → dwarfs, CMB, antiprotons, the Sun
  │      ◄── G8 long-range effects today (the broken phase), and lines
  └─ G9  colliders: spectrum, decays and production → SModelS, resonance searches, invisible and Higgs widths
```

A new engine class, `GenericModel` (G4), carries this chain behind the existing engine interface
(`portals/base.Portal`). The scan, the searches and the reports then treat it like any library engine.

**Where it plugs in.** `classify` keeps its order:
1. the explicit contracts;
2. the library maps;
3. the generic route, only where both refuse.

Every result says which route produced it. On request, the generic route also runs beside a library engine, as a
cross-check.

## 5. What is reused

From the survey of 2026-10-13 (file references as of commit e9a7163):

| piece | where | state, and what it lacks |
|---|---|---|
| Relic solver | `constraints/relic.py` | Exact Gondolo–Gelmini; Edsjö–Gondolo coannihilation with unequal masses; resonance grids; bound-state hook (`thermal`); BDF Boltzmann. **Lacks:** dark-sector degrees of freedom in g*; a test of the single-bath assumption beyond the t-channel |
| Tree engine | `constraints/tree.py` | Any 2 → 2 from particles and vertices (SSS … FFV), unitary gauge, explicit spinors. **Lacks:** Majorana fermion flow; unequal fermion masses in the initial state; exchange of fermions other than χ; χφ initial states; t-channel bosons into f f̄; four-fermion vertices; colour beyond multiplicity |
| Hand-written processes | `constraints/amplitudes.py`, `processes.py` | Ward-tested, including Majorana signs: the reference for G3 |
| UFO writer and reader | `library/interactions/ufo.py`, `constraints/ufo_model.py` | **Writer:** three-field terms, broken phase, neutral colourless states only. **Reader:** through MadGraph's Python. **Not connected:** writer → reader → tree → relic |
| Kinetic mixing | `constraints/kinetic_mixing.py` | Diagonalisation of B, W³ and X: the only mass-basis code |
| Long-range | `constraints/sommerfeld.py`, `portals/nplet.py` | **`enhancement`:** any multi-channel potential. **`nplet`:** fermion n-plets' group factors, Hulthén bound states, ionisation equilibrium. **Hand-written:** SU(3) factors for 3⊗3̄ and 3⊗3 only; wino and higgsino matrices |
| Direct detection | `library/interactions/derivation.py`, `quark_level.py`, `nr_projection.py`, `constraints/loops.py` | Path 1: formulas → DirectDM → nucleon operators. **Lacks:** a deterministic tree-level matcher. **Loops:** keyed by model, not structure |
| Indirect detection | `parameter_space/searches.py`, `spectra.py` | Everything reads `sigma_v_today` by final state. **Spectra:** PPPC channels and one scalar cascade. **`today_unknown`:** makes searches undecided |
| LHC | `searches.lhc_spectrum`, `constraints/lhc.py`, `production.py` | SLHA for the library's families; precomputed cross-section tables. **Lacks:** production per model at run time |
| Intake and agents | `agents/lagrangian.py` (IntakeAgent, DerivationAgent), `orchestrator/paper_model.py`, `model_intake.py`, `scout.py` | **Exists:** paper → ModelSpec; constraint scout. **Not found:** a planner; a literature-benchmark agent |
| Checks | `library/interactions/model_checks.py`, `model_building/audit.py` | Gauge invariance, hermiticity, anomalies, stability, unitarity |
| Independent codes | `~/agentic-dm-tools`: MadGraph 3.8, MadDM 3.3, micrOMEGAs 7.1, SModelS 3.2, DirectDM | MadDM's relic with coannihilators runs from a UFO (DM8 found 2.6% agreement). micrOMEGAs runs only its shipped models (it needs CalcHEP files) |
| The zoo | `evaluation/zoo.py`, `data/model_zoo.yaml` | Routes, engine switches, ledgered held-out half |

## 6. Milestones

Sizes: **S** is about one working session, **M** two or three, **L** four or more. "Expected on the zoo" is a
prediction written before the work. The gate is what must hold.

### G0 — The yardstick: the model zoo (started 2026-10-13)

- **Built:**
  - 31 models (17 new, 14 controls), each written as a typed model from the paper's Lagrangian;
  - 59 targets, each with its quote checked against the paper;
  - halves fixed by hash;
  - the typed and library routes; engine switches for the authors' physics; a thermal splitting for forbidden
    channels.
- **Still to do, before the milestone a model tests:**
  - add a MadDM column, the independent code's Ωh² for each model it covers, at G2;
  - add a `route agreement` measure for the controls, at G4;
  - add entries where a later milestone has fewer than three targets in the development half. New entries take
    their half from the hash, like the rest.
- **Rule:** an entry is corrected only for an error, and never to move a result. Each correction is noted in the
  entry.

### G1 — The mass basis (M)

**Purpose:** from a ModelSpec in either phase to the physical spectrum.
- **Builds** `model_building/spectrum.py`, which yields the physical spectrum:
  - **The vacuum:** the potential's minimum, from stated vevs or solved. For each scalar: a stationarity check, a
    positive-mass check and the Goldstone count.
  - **Mass matrices:**
    - scalars: CP-even, CP-odd and charged;
    - Dirac fermions: a singular-value decomposition;
    - Majorana fermions: a Takagi factorisation of the symmetric mass matrix, so all masses are positive;
    - vectors: from the vevs and charges, with kinetic mixing.
  - **The output:** a typed `Spectrum`. Each state has its mass, spin, electric charge, colour and Z₂ parity, and
    the rotation that defines it.
- **Validation:**
  - **Analytic:**
    - Cohen et al.'s 3×3 singlet–doublet matrix (their eq. 3);
    - the 2×2 mixings of Bhattacharya et al. and Das et al.;
    - the inert doublet's mass relations;
    - a dark Higgs (Kamon et al.);
    - the SM's W, Z and photon from H.
  - **Identities:** the rotations are unitary; Q = T₃ + Y holds for every state; charge is conserved by the vacuum.
- **Gate:** every development-half model's spectrum is computed, or refused with the reason (for example, a
  potential with no stable minimum). It must match the masses the papers print, to the precision they print. The
  held-out half is not touched before G4's held-out run.
- **Expected on the zoo:** no Ωh² yet. The spectra of the development half.
- **A labelling oddity, recorded and not fixed** (found while fixing the external audit's A02/A03, 2026-10-16): a
  scalar with Y = −2/3 in the 3̄ appears in the spectrum as `S(+0.667)` with colour 3̄, its charge the conjugate
  state's and its colour the field's. A 3 and a 3̄ give the same colour factors in the colour-summed rates computed
  from it, so no number changes; the label is to be made consistent when the spectrum's state records are next
  changed.

### G2 — Feynman rules in the mass basis (M)

**Purpose:** every vertex of the physical states, with its coupling.
- **Builds:**
  - **Gauge couplings from the charges:** the covariant derivative for any SU(3) × SU(2) × U(1)_Y × U(1)′
    representation, including W±, Z, γ, gluon and dark-vector vertices and the quartic seagulls.
  - **Yukawas, trilinears and quartics:** all rotated into the mass basis.
  - **Widths:** of every unstable state, two-body at tree level, with three-body flagged where it dominates.
  - **The output:** an in-process `tree.Model`.
  - **A complete UFO export:** both phases, charged and coloured states, quartic and four-field terms, chiral and
    Majorana structures. It is used only for the independent codes.
- **Validation:**
  - ADROIT's UFO for the inert doublet equals the shipped UFO of Goudelis et al., vertex by vertex;
  - the SM sector equals MadGraph's `sm` model;
  - the simplified models equal DMsimp, as DM8 already did for three-field terms;
  - Ward identities hold on the gauge vertices.
- **Gate:**
  - the zoo's vertices for every model with a complete spectrum;
  - the vertex-by-vertex equalities above;
  - MadDM's Ωh² column added to the zoo, where MadDM applies.

### G3 — The tree engine completed (L)

**Purpose:** σ(s) of every 2 → 2 process among the dark states, by final state.
- **Builds:**
  - Majorana fermion flow (Denner's rules);
  - unequal masses in fermion initial states;
  - exchange of any fermion or boson in the s-, t- and u-channels;
  - fermion–boson initial states (χφ → f V, coannihilation);
  - four-fermion contact vertices;
  - colour algebra: amplitudes by colour channel. G7 needs them for the singlet, octet, antitriplet and sextet
    pair states.
  - **Speed:** σ(s) tabulated on the relic grid once per model point and cached. The aim is under a minute per
    point for a model with ten coannihilating states, measured and recorded.
- **Validation:**
  - **Against MadGraph:** every process agrees with MadGraph's standalone matrix element at random phase-space
    points, to 10⁻⁶;
  - **Against ADROIT's own:** the hand-written processes of `amplitudes.py` are reproduced, including the Majorana
    signs;
  - **Gauge cancellations:** σ(χχ → W⁺W⁻) of a doublet stays bounded at high energy, which tests the unitary gauge.
- **Gate:** all of the above, on every process the zoo's development models need.

### G4 — The generic engine and the relic density (L) — **the first zoo gate**

**Purpose:** a typed model the library does not cover gets Ωh², with its route recorded.
- **Builds:**
  - **`GenericModel`** (a `Portal`):
    - channels by final state;
    - the coannihilating set: Z₂-odd states with e^{−Δm x_f/m} above 10⁻³;
    - resonances from every s-channel state and its width;
    - `domain`, `flags`, `family = "generic"`.
    - It is registered in `scan.ModelClass` and placed after the library maps in `classify` (opt-in until G12;
      `g4_generic.md`).
  - **Final states the 2 → 2 code would miss:**
    - forbidden channels (the thermal tail into heavier final states) come naturally from the Gondolo–Gelmini
      average;
    - off-shell W* and Z* below threshold reuse `UFOPortal`'s treatment;
    - other three-body states are flagged, not computed.
  - **Certificates:**
    - the dark sector is in kinetic contact with the SM, or flagged;
    - the coannihilators are in chemical equilibrium, generalising `chemical_equilibrium` from the t-channel to
      any conversion processes G3 computes;
    - dark-sector degrees of freedom are added to g* when they are light.
  - **The long-range criterion:** where α_eff m_χ/m_V ≳ 1 or α_eff/v ≳ 0.1 at freeze-out, and no long-range module
    applies, Ωh² is refused by default with the reason "needs the Sommerfeld effect (G7)" (decision D4).
  - **The estimate, on request** (decision D4). The perturbative Ωh² comes with a warning and a Sommerfeld bracket,
    and never reaches a verdict. The bracket is cheap because it needs only group theory:
    - from each state's gauge representation, the most attractive pair channel. For R ⊗ R̄ this is the singlet,
      with α_eff = α C₂(R) (plus α_Y Y² for a hypercharged pair; a dark U(1) or a Yukawa mediator alike);
    - the most repulsive channel, from the largest irreducible representation in the product;
    - the Boltzmann equation is re-solved with each extreme's thermally averaged Coulomb factor
      S = (πα_eff/v)/(1 − e^{−πα_eff/v}) on the whole rate. A mediator of mass m_V switches the factor off where
      m_V exceeds the Bohr momentum α_eff μ;
    - a central value weights the channels by their multiplicity.

    Bound states are not in the bracket, and lower Ωh² further. The bracket is calibrated, and the calibration
    recorded, against the cases ADROIT computes in full: the wino, the 5-plets and the coloured triplet.
  - **Cross-checks:** the generic route beside the library engine on the controls (`route agreement`), and beside
    MadDM.
- **Gate:**
  - **Development half:** the new models expected in scope (section 8) are computed, and every computed target is
    met or its miss explained;
  - **Controls:** within the controls' stated theory uncertainties of their library engines;
  - **MadDM:** within 10% where both apply and no long-range effect enters;
  - **Then:** one held-out run, ledgered.
- **Expected on the zoo** (development half, new models): five of six computed.
  - Bhattacharya et al., Choubey et al., Dedes & Karamitros, and Giacchino et al.'s scalar.
  - Feng & Smolinsky: the generic route reads their mass-basis dark-photon coupling directly, which the library map
    cannot.
  - The complex scalar triplet is refused for want of the Sommerfeld effect, until G7.

### G5 — Direct detection for a generic model (M)

- **Builds:**
  - **Tree-level matching:** the heavy states are integrated out at tree level from G2's vertices. This covers
    Higgs, Z, Z′ and scalar exchange in the s-channel, and partners Fierz-rearranged in the t-channel. The result
    goes onto DirectDM's quark- and gluon-level basis, then through the existing chain to the nucleon operators and
    every recoil record.
  - **Inelastic scattering:** when a Z₂-odd neutral splitting is below about 200 keV, the model goes to Path 1's
    inelastic treatment.
  - **A loop library keyed by structure:** electroweak multiplets (the n-plet formulae), coloured partners, Higgs
    and 2HDM triangles.
  - **The fallback:** where the tree level vanishes and no loop entry applies, "loop-dominated, not computed": the
    searches are undecided.
- **Validation:**
  - the library engines' `nucleon()` on the controls;
  - MadDM's direct-detection check, which already exists for three-field models;
  - the zoo's σ_SI targets (Bhattacharya et al., Choubey et al., Das et al.).
- **Gate:** the zoo's σ_SI targets, met or with their misses explained; the controls agree.

### G6 — Annihilation today and indirect detection (M)

- **Builds:**
  - **`sigma_v_today` by SM final state:** from G3 at the speeds the searches use (10⁻⁴, 10⁻³), with s-wave
    extraction.
  - **Cascades through new states:** for example χχ → φφ → b b̄ b b̄. The decay tables come from G2, and the
    spectra are boosted from the PPPC channels, generalising the scalar class's "SS".
  - **The CMB:** f_eff from the final states.
  - **Lines:** taken only from the loop library, or from G8; otherwise flagged.
  - **Undecided:** `today_unknown` where long-range effects today matter and G8 does not yet apply.
- **Validation:** the library engines' σv today on the controls, and the cascade spectra against PPPC's own where
  both exist.
- **Gate:** the controls agree, and every search reads a generic model without an exception.

### G7 — Long-range effects in the early universe (L) — **the second zoo gate**

**Purpose:** the Sommerfeld effect and bound-state formation from the model's own gauge representations and
mediators.
- **Builds:**
  - **Pair states decomposed into irreducible representations:**
    - SU(2) × U(1)_Y isospin;
    - SU(3) colour: 3⊗3̄ = 1⊕8, 3⊗3 = 3̄⊕6, 8⊗8 = 1⊕8⊕8⊕10⊕10̄⊕27, and mixed representations;
    - the potential's strength in each irreducible representation R, from the Casimirs:
      α_eff = α[C(R₁) + C(R₂) − C(R)]/2.
  - **Abelian and scalar Yukawa mediators:** Coulomb, Yukawa and Hulthén.
  - **The annihilation matrices Γ:** each partial wave's from G3 at threshold, replacing the hand-written formulae.
  - **Bound states:** 1s and 2s formation in ionisation equilibrium, generalising `nplet`'s machinery to scalars
    and to SU(3).
- **Validation:**
  - **Bottaro et al.'s tables:** the real scalar 5-plet (15.4 TeV) and the complex triplet (2.1 TeV);
  - **De Simone et al.:** the colour octet, 7–8 TeV;
  - **von Harling & Petraki:** dark QED, 1.04 TeV;
  - **Harz & Petraki:** a control;
  - **ADROIT's own engines:** the n-plet engine reproduced, and the wino and higgsino engines as a cross-check.
- **Gate:**
  - **Development half:** the complex scalar triplet is computed and met;
  - **Controls:** the wino and the coloured controls agree with their library engines;
  - **Then:** one held-out run, ledgered.

### G8 — Long-range effects today (M)

**Purpose:** the broken-phase multi-state Sommerfeld effect for annihilation today, with its potentials built from
the charge states. Today the wino's and higgsino's matrices are written by hand.
- **Builds:**
  - **Radiative splittings:** the one-loop electroweak formula for any multiplet, so that thresholds come from the
    spectrum.
  - **Potentials** from W, Z and γ exchange between G1's states.
  - **Today's σv by final state, including the lines γγ and Zγ:** into G6's searches.
  - **The owner's quintuplet:** its searches, undecided in 0.1.0, become decisions.
- **Validation:** the wino and higgsino matrices of `multiplet.py` are reproduced; the published tables of
  Hryczuk & Iengo and DMγSpec for the wino's lines.
- **Gate:** the controls agree, and the quintuplet's lines meet the published values within their stated
  uncertainty.

### G9 — Colliders for a generic model (L)

- **Builds:**
  - an SLHA spectrum and decay table from G1 and G2;
  - MadGraph LO production, generated and cached per model from G2's UFO export, for SModelS;
  - resonance searches for any s-channel mediator, through the existing width gates;
  - invisible widths of h and Z;
  - Higgs signal strengths from scalar mixing;
  - LEP's bounds on light charged states.
- **Validation:** the library's SLHA and production tables, for the families they cover.
- **Gate:** every zoo model in scope gets its LHC verdict or a named reason; the library families agree.

### G10 — The language-model layer I: intake and planning (M; paid gate)

- **Builds** (in `adroit/agents/`, behind `LLMClient`):
  - **An intake that canonicalises:** the paper's Lagrangian goes to a ModelSpec, reusing `IntakeAgent` and
    `paper_model`. It handles conventions: Q = T₃ + Y/2 against Q = T₃ + Y, Weyl against Dirac, and a mass-basis
    dark photon against kinetic mixing. **The deterministic check:** two writings of one model must give the same G1
    spectrum and G2 vertices, so an agent's rewrite is verified, not trusted.
  - **A planner:** a ModelSpec goes to a typed computation plan. The plan sets:
    - the route: library, generic or both;
    - the regime: whether long-range effects are needed and where the resonances are;
    - the theory uncertainties.

    The core recomputes every criterion the plan relies on.
- **Gate:** the zoo's 31 `lagrangian` fields are read by the agent. Each must reproduce the hand-written spec's
  spectrum and vertices, to the precision G1 and G2 test. The cost is recorded, and approved before the run
  (decision D6).

### G11 — The language-model layer II: benchmarks and gaps (M; paid gate)

- **Builds:**
  - **A literature-benchmark agent.** For a model, it finds published benchmarks and extracts the targets with
    their quotes, as the zoo's survey did by hand. **The deterministic check:** each quote's numbers must appear on
    the stated page, as checked for the zoo on 2026-10-13. ADROIT's result is then compared, and the report says
    what agrees.
  - **Gap drafting.** Where the core lacks a piece, an agent drafts the module with its tests. The draft stays
    quarantined: its numbers are marked provisional and every verdict that depends on it is undecided, until a
    person reviews it.
- **Gate:**
  - the benchmark agent recovers at least half of the zoo's development targets from the papers;
  - none of its quotes fails the check;
  - drafted code reaches no verdict in any test.

### G12 — Integration, the closure audit (R12) and the release (M)

- **Builds:**
  - **The workbench:** "Run this model" uses the planner, and a report shows the route, the physics included and
    what is missing.
  - **The rest:** the documentation, the CHANGELOG and the receipts.
- **The audit:** R12's closure re-audit (the release plan) over the whole tree, R0–R11 and G1–G11, with its
  usability sessions and release notes.
- **Gate:**
  - the held-out half once, against section 2's definition of done;
  - the release checks pass;
  - the release-ready definition of the release plan holds. The release is then tagged; pushing it is the owner's
    decision.

## 7. Build order and the critical path

```
G0 ─► G1 ─► G2 ─► G3 ─► G4 ═══► G5 ─► G6 ─► G9
                          ║
                          ╠═══► G7 ─► G8
                          ║
                          ╚═══► G10 ─► G11 ─────────► G12
```

- **The critical path is G1 → G2 → G3 → G4.** Nothing generic computes Ωh² until G4.
- **After G4,** three lines can proceed in any order:
  - verdicts: G5, G6, G9;
  - long-range effects: G7, G8;
  - agents: G10, G11.

  The order in section 6 puts first what most widens what a generic model gets:
  - its experimental verdicts (G5, G6), since the records are already in the library;
  - then the long-range physics (G7, G8) that the electroweak and coloured models need.
- **The zoo's held-out half is run three times, each ledgered:** at G4, at G7 and at G12.

## 8. Scope

**In scope:** 2 → 2 freeze-out of a Z₂-stabilised dark sector in a standard radiation-dominated history:
- any spins up to 1;
- any SU(3) × SU(2) × U(1)_Y representations, and new U(1)s;
- coannihilation, resonances and forbidden channels;
- secluded annihilation into mediators;
- the Sommerfeld effect and bound states (G7, G8).

**Flagged, not computed:**
- three-body final states other than off-shell W and Z;
- early kinetic decoupling near a resonance (Binder et al.: up to an order of magnitude);
- hadronic final states below about 10 GeV (DM7's relic gate);
- slow conversions between coannihilators: the certificate fails and the result is refused.

**Out of scope** (each needs a different Boltzmann system):
- 3 → 2 (cannibal, SIMP);
- freeze-in;
- asymmetric dark matter;
- several stable species;
- non-standard cosmologies (early matter domination, entropy release);
- conversion-driven freeze-out.

## 9. Decisions (settled by the owner, 2026-10-13)

| | decision | settled |
|---|---|---|
| D1 | Start before or after R12? | **Now.** R12's closure audit moves into G12, over the whole tree |
| D2 | Feynman rules in-process or through a UFO round trip | **In-process** (`tree.Model`). The UFO export is kept for the independent codes |
| D3 | The independent reference for Ωh² | **MadDM**, from ADROIT's UFO, with its coannihilators |
| D4 | When long-range effects matter and no module applies | **Refuse Ωh² by default**, and offer on request the perturbative estimate with a warning and a Sommerfeld bracket from group theory (G4) |
| D5 | Renumber the sketch's G-series in build order (the zoo becomes G0) | Applied with this plan, in the plan, the zoo, the release plan and the CHANGELOG. Easily reversed if you prefer the sketch's names |
| D6 | Language-model gates (G10, G11) | **$10 approved for G0–G12 together.** Each paid run is still logged with its cost |

**Settled by the owner, 2026-10-14** (after G5):

| | decision | settled |
|---|---|---|
| D7 | The generic route in `classify` | **Opt-in until G12** (`generic_route=True`); on by default when G12 integrates it |
| D8 | The long-range criterion | **Confirmed:** Ωh² is refused where the D4 bracket's centre moves it by more than 10% (the planned α_eff screen let the wino through) |
| D9 | Feng & Smolinsky's entries, refused by the long-range criterion | **Record the papers' perturbative treatment** (`sommerfeld: false`) on both. The held-out one is marked corrected after the G4 run, so it is not blind at G7 |
| D10 | G1's axial current of a charged Majorana field (found by the G4 held-out run) | **Fix now.** Okada et al.'s entry is not blind at G7 |
| D11 | A Majorana mass of a Dirac field; the pole refinement's cost | **Both in G6** |
| D12 | The misses localised to the inputs (Bhattacharya et al., Choubey et al., Dedes & Karamitros t1) | **Re-read the papers' conventions; fix an entry error, else report back** |
| D13 | Cascades through new states (G6) | **Two-body cascades** with boosted PPPC spectra; longer chains flagged |
| D14 | The cross-check of annihilation today (G6) | **MadDM's indirect mode; its downloads approved** (a deliberate install, then offline again) |
| — | Push to GitHub | **Pushed** 2026-10-14 |

**Settled by the owner, 2026-10-14** (after G6):

| | decision | settled |
|---|---|---|
| D12 | The re-read's outcomes | **Choubey et al.'s σ_SI retargeted** to the paper's eq. (23) (8.22×10⁻⁴⁸ cm² at BP1; the table is a quarter of it). **Dedes & Karamitros's t1** kept as the text quotes it, with the re-read as a note. Bhattacharya et al.: no change |
| D15 | Long particle names in MadGraph | **A code name** (n1, dm1, …) for any name longer than MadDM's output carries (five characters) |
| D16 | The 2024 dwarf recast and γ-ray lines | **Unchanged.** Its likelihoods read dΦ/dE at each bin's reference energy, which a line does not have; the 2015 mixture rule decides these mixtures rigorously (the line counted in its bin), or they stay undecided. No record's use changed |
| D17 | Antiprotons from a cascade through new states | **Undecided**, not bounded: the published limits are for pure channels, and no proxy bounds a cascade's spectrum in every bin |
| D18 | The singlet–doublet Dirac entry | **Withdrawn**, and replaced by Yaguna's singlet–doublet Dirac model (arXiv:1510.06151), with its eq. (9) for Z exchange checked against the matching |
| D19 | G10's comparison (the owner, 2026-10-15) | **The SM-like h is set aside where no vertex joins it to a new state, and a degenerate partner is compared at the paper's exact degeneracy** (not the zoo's 1.0001 regulator). Both counts are reported (strict and D19). The agent stays in the unbroken phase |
| D20 | The two held-out references that do not build | **Correct them from the papers and mark them not blind at G12.** Kamon et al.'s is corrected (a quartic's conjugate; the second benchmark's vacuum value). Ipek et al.'s needs a second doublet's Type-II Yukawas in G2 and the zoo's choice of tan β, m_A, θ and y_χ: left for the owner |
| D21 | The γ-ray lines (G8) | **The published resummed spectra where they exist (DMγSpec: the wino and higgsino, NLL′ with NLO potentials), the upper bound elsewhere.** No quintuplet spectrum is public, so the quintuplet keeps the upper bound. The library's own wino and higgsino lines are unchanged |
| D22 | LHC production for a generic model (G9) | **MadGraph at LO per model, taken as a lower bound:** an exclusion stands, "allowed" is not shown |
| D23 | Gap drafting (G11) | **A larger output budget, and a test on a gap with a known answer** (the n-plet splitting: reproduced) rather than another draft of the Sudakov factor |

**Settled by the owner, 2026-10-15** (the second round, after G7–G11):

| | decision | settled |
|---|---|---|
| D21 (revised) | The library's wino and higgsino lines | **DMγSpec, the more precise calculation, by default**, with the H.E.S.S. reference curves kept as its cross-check and fallback |
| D24 | The γ-ray lines of other multiplets | **Build the resummation for general odd n** (`constraints.endpoint_nll`: NLL, with the NLO Sommerfeld potential), checked against the quintuplet's published line. A pure Majorana odd n-plet's lines are then decisions, in the generic route and the library's n-plet |
| D25 | G10's open rows | **Extend D19 to an h joined to new states only through kinetic mixing; state the zoo's ε values and Berlin et al.'s cos θ_W in the benchmark inputs; give G2 a second doublet's Yukawas** (Ipek et al.'s entry rewritten with them, D20) |
| D26 | G9's open items | **Three-body widths through an off-shell W (π, eν, μν, τν, quarks) for any fermion pair, the one-loop splittings of pure multiplets, and more verdicts** (MadGraph beyond the tables, the DMsimp spin-0 monojet mapping, MadGraph's process reused across points) |
| D27 (D7 revised) | The generic route in `classify` | **On by default**: where a typed or library engine refuses a model by its domain, the generic route computes it (per target in the zoo, per point in a scan with two mass axes), and each result names its route |
| D28 | MadDM's neutrino counting (G6) | **Checked**: it writes χχ → ν_μν̄_μ and ν_τν̄_τ out with ν_eν̄_e as one process and counts one flavour. No relic cross-check had νν̄ near freeze-out, so none is affected (a B − L-like Z′ shows it: MadDM's Ωh² 15% high). The caveat is in `g6_indirect.md` |

**Taken at G12 on the owner's instruction to settle the five open points (2026-10-15); confirmed by the owner on
2026-10-16**
(the G12 closure record):

| | decision | settled |
|---|---|---|
| D29 | Which α the photon's couplings take for a sub-GeV dark sector | **ε is DarkCast's: a dark photon couples to the electromagnetic current as ε e(0) Q in both routes** (e(0) = √(4πα(0)) = 0.302822, DarkCast's ge). The library had taken e(m_Z), the generic route the G_F scheme's e, while the searches compared the same ε with DarkCast's. `e` and `α` in a stated coupling are e(0) and α(0); the Z's and the photon's own couplings are unchanged |
| D30 | DMγSpec above 13 TeV; bound states' lines; NLL against NLL′ | **A theory band on a resummed line rate, applied in the line decision** (undecided where it straddles the limit): ±5% for NLL against NLL′; +5% more for an n-plet with n ≥ 5 (bound states' line photons, a few percent except at isolated masses near the Sommerfeld peaks, which the reason names); ±25% for DMγSpec's rates above 13 TeV, where its tree line drifts 20% against its Sommerfeld table |

**The owner's decision after G12 (2026-10-16):**

| | decision | settled |
|---|---|---|
| D31 | A paper's relic formula that counts one species of a complex or Dirac particle | **Compared after doubling.** Such a formula solves dn/dt = −⟨σv⟩(n² − n_eq²) for one species; with the particle–antiparticle cross section, the total density obeys dn/dt = −(⟨σv⟩/2)(n² − n_eq²), so the total Ωh², which ADROIT computes, is twice the formula's (x_f unchanged, since the freeze-out condition depends on g⟨σv⟩). Applied to Feng et al.'s two entries, whose targets become Ωh² = 0.2398, a derived convention conversion, neither the paper's native target nor a blind reproduction (the G12 closure record, the Feng question; the external audit's A11). The other fourteen entries with non-self-conjugate dark matter were checked against their papers: none counts one species (`docs/model_zoo.md`) |

**The owner's decisions on the external audit (2026-10-16;
the audit fix plan of 2026-10-16):**

| | decision | settled |
|---|---|---|
| D32 | D30's allowed side for an n-plet with n ≥ 5 (audit A05) | **Pending.** Bound-state line photons are not computed and can dominate at isolated masses near the Sommerfeld peaks, so the band has no justified upper edge there; the excluded side keeps its lower edge, since bound states only add photons |
| D33 | R-20's premise, that QCD-only production of a coloured partner is a lower bound (audit R20) | **Withdrawn.** The t-channel interference's sign is not established, so an exclusion resting on QCD-only σ is pending unless the lower bound is established over a stated domain; a model excluded by another valid constraint stays excluded |
| D34 | How v0.1.0 is distributed (audit A12) | **From a source clone only** (`uv sync --locked`); no wheel or PyPI distribution is claimed, and wheel support is deferred |
| D35 | The O(1) disagreements of G12's held-out half (audit item 17) | **The label stays; the restriction is per calculation.** In each affected regime (identified from the generic route's own quantities) an exploratory result carries a prominent qualification, and a decisive verdict needs a justified uncertainty treatment or stays pending; the model class is not disabled |
| D36 | The trust model (audit item 20) | **A local, single-user workbench.** Imported UFO/Python code is trusted executable code; coupling formulas stay checked before SymPy reads them; PDFs, papers and model descriptions are data, never instructions. Isolation and resource limits are for any hosted or multi-user use |

Noted with the confirmation (2026-10-16):
- **D29:** for a dark photon above a few GeV the physical coupling at q² ~ m_A′² is a few per cent above ε e(0), so
  its rates are underestimated by at most about 7%; the published limits use the same convention, so the comparison
  with them stays consistent.
- **D30:** the bands are the measured differences, a minimum rather than a full scale variation. Near isolated
  Sommerfeld peaks (the quintuplet at 68.1 TeV) bound states dominate and +5% understates them (D32 since: no upper
  edge for n ≥ 5, the allowed side pending); the pure multiplets'
  thermal masses (the quintuplet's 13.6 TeV), where Track 1 gives its verdicts, are far from those peaks.

**D35's thresholds, kept by the owner (2026-10-17)** (`adroit/parameter_space/portals/generic_regimes.py`):

| threshold | what it means physically | why this value |
|---|---|---|
| a 5% "material" share (`MATERIAL`) | a regime counts where its physics carries ≥ 5% of the dark-matter pair's ⟨σv⟩ at x_f, or shifts Ωh² by ≥ 5% | A06's 5%. A channel with a 5% share, wrong by up to 2.5×, moves Ωh² by about 7%, comparable with the route's other uncertainties |
| forbidden splittings Δ > 0.309 (`FORBIDDEN_AGREED`), Δ = (m_c + m_d)/(2m_χ) − 1 | annihilation into final states heavier than the dark-matter pair | the route agreed with D'Agnolo et al. within 2% at Δ = 0.101 and 0.309 and missed by 2.5× at 0.651; nothing between was tested, so everything above the last agreement is flagged |
| the pole window ±10% (`POLE_WINDOW`), Majorana dark matter only | 2m_χ within 10% of an s-channel vector's mass | Okada et al.'s benchmarks sit about 5% below the Z′ pole, and the thermal motion at freeze-out spreads √s by about 4% (⟨v²⟩ ≈ 6/x_f); a Dirac case near a pole was not among the disagreements, so widening it would have no evidence |
| the relic target × 1/2.5 to × 2.5 (`TARGET_SCALES`) | inside a regime a decisive verdict stands only if the evaluated grid supports it at every target in the interval (the rule below) | 2.5 is the largest disagreement observed (the three ranged ×1.25–2.5) |

Two caveats, recorded with them:
- **The pole window is over-inclusive (a known, conservative limitation; the stacked audit of 2026-10-18).** It
  checks the masses of the parity-even massive vectors, not whether the dark-matter pair couples to each: a model
  coupled only to a 300 GeV Z′ is also flagged near the W and the Z. This adds pending or qualified outcomes only; no
  decisive result follows from it. Filtering by the nonzero χχV vertex is the repair if it is ever needed; removing
  the W by name would leave other uncoupled vectors.
- **Not blind for these regimes:** the thresholds were chosen after the held-out results were seen, so the held-out
  half no longer tests these three regimes blind. They can only make a result pending or qualified; they never widen
  an acceptance or make a model look better, so they cannot raise a success rate.
- **Only the regimes seen:** they recognise the three regimes where a disagreement was found. An O(1) disagreement
  in a regime nobody has compared would not be flagged.

**The interval rule (the re-audit's R17-2, the owner's conditions, 2026-10-17;** `parameter_space.verdict._across`,
`orchestrator.single_idea._band_across`**).** Checking the two ends of the interval does not establish the interval:
with Ωh² = m_χ/1000 and only 170 < m_χ < 190 GeV allowed, 0.048, 0.12 and 0.3 are excluded and 0.18 is viable on
the same grid. The contours of every target in [t/2.5, 2.5t] together fill the band t/2.5 ≤ Ωh² ≤ 2.5t, so a
decisive level stands only on the evaluated grid and at its resolution, and only where:
- the grid covers the interval: complete, Ωh² at every point and spanning the interval (otherwise part of it has no
  thermal solution on the grid), a grid point inside the band, and the roots at both ends resolved with none left
  unrefined;
- every grid point in the band, every root at its ends and every nominal crossing has the level's status: all fully
  allowed for viable (stronger than needed, since different points could serve different targets; accepted), all
  excluded for excluded. Any other point leaves the verdict pending: "viable (excluded) at the nominal target; not
  established across the O(1) disagreement";
- over- and underabundance are monotone in the target, so the interval's far end decides them exactly on the grid.

Every point is judged with its own engine, the generic fallback included (R17-5). The thresholds above are unchanged.

**The re-audit of 2026-10-18 (R18-1, R18-2, R18-4; the owner's clarifications of 2026-10-18).**
- **Where a regime is looked for (R18-4):** at the nominal thermal points and at every evaluated point a shifted
  target in the interval reaches: the grid points (fitted masses) whose Ωh² lies in the band and both ends of every
  grid edge (pair of neighbouring masses) whose Ωh² range overlaps it, the corners of the cells the shifted contours
  cross. This is on the evaluated grid and at its resolution; the edges' ends do not certify structure between
  samples. Where there is no nominal crossing, every computed point is checked, as before. For a dark-U(1) model the
  check costs one perturbative relic calculation per checked point.
- **The nominal search must be complete (R18-2):** any unresolved nominal item (a failed refinement, a bracket left
  out by the root budget, a relic density that changed when the constraints were evaluated) leaves the band-wide
  certificate unestablished. One surviving root may still make the nominal level viable outside a regime.
- **Explain a signal judges each point's fit before its status (R18-1):** every point evaluated in the band (the
  fitted masses inside it, the thermal points at its ends and the nominal thermal points, refined roots as well as
  samples). For viability each must meet the anomaly-fit criterion (√q0, or the verified inverse's local Z, at
  least 1, from a resolved, identifiable fit inside its range). For an exclusion, an undecided fit (unresolved,
  unidentifiable, at its range's edge or without a finite statistic) blocks; a resolved, identifiable fit inside its
  range whose finite statistic is below the declared anomaly-fit threshold is no explanation of the anomaly (√q0
  measures the improvement over the background alone, not absolute goodness of fit), is listed apart and cannot
  defeat the exclusion; if no eligible point remains, that is reported instead of an exclusion.

## 10. Risks

| risk | where | what guards against it |
|---|---|---|
| Gauge cancellations lost in the unitary gauge (χχ → W⁺W⁻ grows with s) | G2, G3 | Couplings from the covariant derivative only; high-energy boundedness tests; MadGraph matrix elements |
| Majorana signs and fermion flow | G3 | Denner's rules; the hand-written Majorana processes; MadGraph |
| Speed: tens of channels × the relic grid × a scan | G3, G4 | σ(s) tabulated once per point; cached; profiled against the one-minute aim; at most two workers |
| Degenerate or nearly massless states (Takagi with degeneracies; Goldstones) | G1 | Vacuum checks; degenerate subspaces treated explicitly; tests on the zoo's degenerate cases |
| Thresholds and resonances under-resolved | G4 | `energy_grid` nodes at every resonance and final-state threshold; the zoo's resonance entries |
| A rounding error landing on a threshold (as the wino's did, fixed 2026-10-13) | G7, G8 | The rounding tolerance in `sommerfeld.enhancement`; a non-finite rate is named by the relic solver |
| An agent's model differs from the paper's | G10 | The deterministic equivalence of spectrum and vertices; a human gate on any difference |
| Scope creep | all | Each milestone's gate; missing physics named, not added in passing |

## 11. Records

Each milestone gets a record, `docs/g<N>_<name>.md`, as the DM milestones did, and a line in the CHANGELOG. Each
held-out run goes in `docs/dm10/held_out_ledger.jsonl` with its declared reason.

**Paid runs (decision D6: $10 for G0–G12):**

| date | run | model | cost |
|---|---|---|---|
| 2026-10-15 | G10 intake gate, first pass (superseded: the message lacked the model's name) | Claude Opus 5.5 | $1.16 |
| 2026-10-15 | G10 intake gate, second pass (27 entries, stopped by its $3.80 cap) | Claude Opus 5.5 | $3.39 |
| 2026-10-15 | G10 intake gate, the last four entries | Claude Opus 5.5 | $0.33 |
| 2026-10-15 | G11 benchmark gate (12 development entries) | Claude Opus 5.5 | $2.24 |
| 2026-10-15 | G11 gap draft, the wino line's Sudakov factor (no output: all tokens spent reasoning) | Claude Opus 5.5 | $0.65 |
| 2026-10-15 | G11 gap draft test, the n-plet splitting (reproduced; D23) | Claude Opus 5.5 | $0.18 |
| 2026-10-15 | G10 third pass, first attempt (stopped after 3 entries: the account's credit ran out) | Claude Opus 5.5 | $0.28 |
| 2026-10-15 | G10 third pass (31 entries, D19 and the revised guide) | Claude Opus 5.5 | $3.17 |
| 2026-10-15 | G10 fourth pass (31 entries; the guide's Higgs-potential rule refined, 16,000-token replies) | Claude Opus 5.5 | $3.39 |
| 2026-10-15 | G10 fifth pass (D25; 22 of 31 before the account's credit ran out) | Claude Opus 5.5 | $3.26 |
| 2026-10-15 | G10 sixth pass (the nine not reached; Pospelov, D'Agnolo with the `kinetic_mixing` term) | Claude Opus 5.5 | $1.23 |
| 2026-10-15 | G10 seventh pass (Pospelov, D'Agnolo: the paper's field strength; Ipek: its inputs) | Claude Opus 5.5 | $0.56 |
| 2026-10-15 | G10 eighth pass (Ipek: the dropped quartics) | Claude Opus 5.5 | $0.18 |
| 2026-10-15 | G10 ninth pass (Ipek, with G1's mass check) | Claude Opus 5.5 | $0.22 |
| 2026-10-15 | G10 final pass (all 31, the final guide and engine: the gate met) | Claude Opus 5.5 | $3.59 |
| 2026-10-15 | G12 live checks L0–L9 (the G12 live protocol record; $2.00 allowance) | Claude Opus 5.5; GPT-5.6 Sol (L8b, $0.03) | $1.32 |
| 2026-10-16 | G10 tenth pass (Okada et al. alone, the guide's Majorana-current identity; the owner raised the cap to $0.70) | Claude Opus 5.5 | $0.15 |
| 2026-10-20 | G11 rerun, the quote instruction (10 of 12 entries; the last two refused before dispatch by the $2.40 cap's reservation; `g11_benchmarks.md`) | Claude Opus 5.5 | $1.77 |
| 2026-10-20 | G11 rerun's supplementary completion (the two entries the cap's reservation refused; cap $2.30) | Claude Opus 5.5 | $0.51 |
| | **total** | | **$27.58** (the owner's $10 of D6, a top-up for G10's rerun, and $10 more twice on 2026-10-15; the G11 rerun approved separately on 2026-10-19) |

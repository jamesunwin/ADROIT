# G10 — The language-model layer I: intake and planning (2026-10-15; paid gate)

Milestone G10 of [`freeze_out_build.md`](freeze_out_build.md). An agent reads a paper's Lagrangian into a ModelSpec
in ADROIT's conventions. A deterministic check then says whether the agent's model is the hand-written one, so its
rewrite is verified, not trusted. A planner proposes how to compute a model, and the core recomputes every
criterion the plan relies on.

## What was built

- **The canonical intake** (`adroit/agents/canonical_intake.py`). The message holds the paper's own text around its
  Lagrangian (the pages around it, from the PDF), the Lagrangian and equation number, the model's name, and the
  benchmark's inputs. The guide states G1's conventions:
  - Q = T₃ + Y, and ⟨H⁰⟩ = v/√2;
  - every sign and factor of the Lagrangian's coefficients;
  - Weyl against Dirac fields, and a mass-basis dark photon against kinetic mixing;
  - the index notation for contractions;
  - the rule that the agent computes no number: benchmark inputs are couplings, and Lagrangian masses are formulas
    in them.

  G1 builds the result, and one correction round returns any refusal to the agent.
- **The equivalence check** (`adroit/model_building/equivalence.py`). Two writings of a model are equal if they
  have the same mass-basis spectrum (each state's spin, charge, colour, Z₂ parity and mass, as a multiset) and the
  same vertices (by kind and legs, the size √(|c|² + |c₂|² + |c₃|²), invariant under a field's rephasing or chiral
  rotation). Masses agree to 10⁻⁵ and couplings to 10⁻⁴, the precision G1 and G2 test at. A diagnostic option sets
  the SM-like h aside (below); it is never counted as a pass.
- **The planner** (`adroit/agents/planner.py`). The agent proposes:
  - the route (library, generic, or both);
  - the regime (long-range effects, coannihilators, resonances);
  - the theory uncertainties.

  `check` recomputes the route from `classify` and the generic build, long-range effects from G7 (G4's bracket where
  G7 refuses), coannihilation from the bath, and resonances from the widths. Where the plan and the core differ, the
  core's value is used and the difference is recorded. The planner is tested offline; it was not run paid.
- **The gate's script** (`scripts/g10_intake_gate.py`). It has three modes:
  - `--dry-run` ($0): the zoo's models through the fake client;
  - the paid run;
  - `--rescore` ($0): the stored agent models compared again with today's G1, G2 and harness.

## The gate run (Claude Opus 5.5)

| pass | entries | cost |
|---|---|---|
| first: the message lacked the model's name, so the agent could not tell which multiplet a paper meant (a quintuplet read as a triplet) | 31 | $1.16 (superseded) |
| second: the name in the message | 27, then the budget's cap stopped it | $3.39 |
| second, the last four | 4 | $0.33 |
| **G10 total** | | **$4.88** |

Two zoo references do not build, so 29 are compared. Both are held-out entries (flagged below, not edited):
- `u1x_vector_dm_dark_higgs_kamon`: the term −λ_Φ(Φ†Φ − v_φ²/2)² carries net U(1)_X charge +2;
- `two_hdm_pseudoscalar_singlet_mediator_ipek`: the coupling y_χ has no value.

**As run: 13 of 29 equal.** One difference was ADROIT's own error, which the gate found:
- **G2 read a right-handed SM field (uR, dR, eR) as its first-generation flavour alone, whatever its `generations`.**
  ADROIT's own Standard Model content declares these fields with three generations (`spec.SM_FIELDS`). An agent's
  B − L model, written with uR, dR, eR × 3, so had the right-handed Z′ couplings of s, c, b, t, μ and τ missing.
  `feynman.sm_names` now reads three generations as all three flavours. Any other count is refused with a reason.
  With the fix, Okada et al.'s model is equal: **14 of 29.**

The harness had one error too. For a thermal-mass target, the zoo's spec carries only a starting mass, and the zoo
scans it. The agent was told the thermal mass while the reference stayed at the starting mass. The reference is now
built at the stated mass (`reference`), as the zoo computes it.

**The other 15, by cause** (from `--rescore`; `docs/g10/intake_results.json` has every difference):

| cause | entries | what differs |
|---|---|---|
| **the SM-like h only.** The guide asks for the unbroken phase, where G1 always has the h; the zoo writes these as broken-phase simplified models without it | dmwg Z′ (V1), von Harling & Petraki | the h and its SM vertices; nothing else |
| **the zoo's 0.01% regulator** on a degenerate partner's mass (m_φ = 1.0001 m_χ), plus the h | De Simone et al. × 2, Harz & Petraki | equal against the paper's exact degeneracy |
| **cos θ_W's scheme** in the kinetic mixing ε/(2 cos θ_W) | Berlin et al. | the zoo's MS-bar 0.8768 against the agent's M_W/M_Z; the A′'s SM couplings differ by 0.52% |
| **the agent left out the portal couplings** that the benchmark does not fix | Pospelov et al., D'Agnolo et al., Feng et al. × 2 | no kinetic mixing, or only the electron; the dark sector equal |
| **the benchmark message lacks inputs**, which the agent then assumed | the complex triplet (its splitting couplings), Yaguna (M_D 210 against the zoo's 212 GeV), Choubey et al. (the scalar quartics) | the masses of the states those inputs set |
| **the agent's model does not build** | Cohen et al. (a Weyl doublet and a four-component singlet in one bilinear, which G1 refuses), Holst et al. (L_μ and L_τ doublet names, which G2 does not know) | — |

In physics terms: 14 equal, 6 equal up to a convention (the h, the regulator, the cos θ_W scheme), 4 with the
portal left out, 3 where the message was incomplete, and 2 that do not build. **Gate: not met.** Its rule is that
every one of the 31 reproduces the hand-written spectrum and vertices.

## The third and fourth passes (2026-10-15, after the owner's decisions D19 and D20)

The changes between them:
- **D19** in the comparison (`equivalence.compare(..., d19=True)`, the gate's `judge`);
- **D20:** Kamon et al.'s reference corrected, so 30 of the 31 references now build;
- **the benchmark inputs:** the complex triplet's splitting couplings stated as the zoo's; a thermal-splitting
  target's splitting given; each entry's dropped terms given as "left out by the reference";
- **the guide:** G2's SM fermion names; keep every portal, never invent a dark self-coupling; G1 owns the SM's own
  terms unless a new scalar mixes with H; a mixing sector all in Weyl or all in four-component fields; a scalar
  sector inverted from its stated masses; no SM boson names for new vectors;
- **G1 and G2:**
  - the lepton-doublet names Le, Lmu, Ltau;
  - left-handed Weyl currents (Berlin et al.'s η, ξ writing now builds; it equals the four-component Dirac
    field, `test_a_dirac_fermion_written_as_two_weyl_fields_has_the_four_component_current`);
  - a new vector named A, Z, W or g refused (it had been merged with the SM boson);
- **the client:** a reply that spends its whole output on reasoning is not retried at a charge; the intake has
  16,000 tokens.

| pass | cost | compared | equal | equal under D19 |
|---|---|---|---|---|
| second (2026-10-15, before D19; re-scored with today's code) | $3.72 | 29 | 14 | 19 |
| third (the revised guide) | $3.17 | 29 | 16 | 24 |
| fourth (the guide's Higgs-potential rule refined, 16,000-token replies), as run | $3.39 | 30 | 18 | 26 |
| fourth, re-scored with today's G1 (the vector-name check) | $0 | 30 | 18 | 25 |

**What still differs in the fourth pass** (`docs/g10/intake_results_fourth_pass.json`):

| entry | difference | what would close it |
|---|---|---|
| Kamon et al. (held-out) | the agent took G1's m_h = 125.09 GeV; the reference is set for 125 | the benchmark now states m_H₁ = 125 (D20): the next pass |
| von Harling & Petraki (held-out) | the agent named its dark photon A, which G1 now refuses | the guide now says so: the next pass |
| Berlin et al. (held-out) | 0.5% in the A′'s SM couplings: cos θ_W in ε/(2 cos θ_W), M_W/M_Z against the zoo's MS-bar 0.8768 | the owner: state the zoo's scheme in the benchmark, or take G2's in the entry |
| Pospelov et al., D'Agnolo et al. (held-out) | kinetic mixing gives the unbroken-phase h an O(ε) vertex with the dark photon, so D19 keeps the h, which the zoo's broken-phase writing lacks; and ε is the zoo's choice (10⁻⁶; 5 × 10⁻⁶) where the benchmark gives none | the owner: extend D19 to an h joined to new states only through the vector portal, or rewrite the two entries in the unbroken phase; state ε |
| Ipek et al. (held-out) | the reference does not build (D20) | a second doublet's Type-II Yukawas in G2, and the zoo's choices |

**Gate: not met.** It needs Ipek et al.'s reference and the owner's decisions on the last three rows. A fifth pass
(about $3.40) would then close the first two.

## The fifth pass to the final pass (2026-10-15, after the owner's second round)

The owner's decisions:
- **D19 extended** to an h joined to new states only through kinetic mixing (`equivalence.portal_vectors`,
  `sm_higgs_alone`): an unbroken-phase writing's O(ε) h–Z–A′ vertex is set aside, as the broken-phase writing has no h;
- **the zoo's choices stated** in the benchmark inputs: Pospelov et al.'s κ = 10⁻⁶, D'Agnolo et al.'s ε = 10⁻⁵,
  Berlin et al.'s cos θ_W = 0.8768 (MS-bar);
- **a second doublet's Type-II Yukawas in G2** (in the Higgs basis), with complex couplings (`I`) in G1 and G2; Ipek
  et al.'s reference rewritten in the Higgs basis with them (D20; it builds, the light CP-odd state at 100 GeV with
  2.3% A⁰).

The fifth pass ($3.26, all 31 entries) ran out of the account's credit after 22. Twenty were equal under D19.
Pospelov et al. and D'Agnolo et al. differed by 1.8% in the dark photon's couplings to SM fermions. The agent wrote
the mixing out as currents ε e Q_f f̄γf V with e = √(4πα(0)); G1 translates the zoo's kinetic mixing with its own
e = g s_W (G_F scheme). Both are e, at two scales. What followed, each fix found by the gate:

| fix | why |
|---|---|
| **A vertex's stated coupling reads e, α, s_W², v, m_h, m_W and m_Z at G1's own values** (`gauge_basis.ELECTROWEAK`) | a current ε e Q f̄γf V written out is then the same coupling as the kinetic mixing it stands for (`test_a_current_eps_e_q_written_out_is_the_kinetic_mixing_it_stands_for`); a stated Higgs potential in m_h puts h at G1's 125.09 GeV, not the constants table's 125.25 |
| *(its effect on the zoo)* | the development half's counts are unchanged (new models 9 of 11 met, controls 11 of 15, the generic route agreeing on 13 of 15). Feng et al.'s complex-scalar entry, whose current −κ e q_f f̄A̸′f is written out, moves 3.2% (Ωh² 0.0726 → 0.0703; still met). Its dark matter is 33 MeV, where α(0) is the physical coupling; G1's photon couples with the G_F scheme's α ≈ 1/132 everywhere, 3.6% above α(0). Which α a sub-GeV dark sector should take is left for the owner |
| **The guide names the `kinetic_mixing` term** and says to write a paper's kinetic mixing as one term, never its O(ε) currents | the agent had written currents because "the spec has no field-strength mixing structure"; the currents leave out the mixing's V W⁺W⁻ |
| **The guide: keep the paper's field strength** (the photon's F with A, broken phase; hypercharge's B, unbroken) | told about the term, the agent rewrote −(ε/2)V F as −(ε/2c_W)V B, which adds a Z mixing (ε t_W/2)V Z that the paper does not have |
| **Ipek et al.'s target states the zoo's choices** (tan β = 10, sin 2θ = 0.3, y_χ = 0.8, m_A = 600 GeV), and its reference lists as left out the quartics of H₂ and the singlet's quartic | D20's correction said the target states them; it did not, so the agent chose its own (tan β = 3, θ = 0.2, m_A = 500 GeV). Then it wrote 2HDM quartics the reference leaves out (alignment, no H₂ quartics), which only the reference's assumptions said |
| **G1 refuses a new field whose mass is stated twice**: mass_gev beside a bilinear of the field with itself (`_one_mass_statement`) | in one Ipek pass the agent wrote a stray χ̄iγ⁵χ with coefficient y_χ = 0.8 next to χ's stated 30 GeV, and G1 silently took the term as χ's mass (0.8 GeV). The refusal goes back to the agent, which corrects it. A Dirac mass between two Weyl fields (Cohen et al.'s D, Dc) is not refused |

| pass | entries | cost | equal | equal under D19 |
|---|---|---|---|---|
| fifth (the owner's second round) | 22 of 31 (credit ran out) | $3.26 | 14 | 20 |
| sixth (the nine not reached, and Pospelov, D'Agnolo with the `kinetic_mixing` term) | 11 | $1.23 | 6 | 8 |
| seventh (Pospelov, D'Agnolo: the paper's field strength; Ipek: its inputs) | 3 | $0.56 | 2 | 2 |
| eighth (Ipek: the dropped quartics; a stray χ̄iγ⁵χ) | 1 | $0.18 | 0 | 0 |
| ninth (Ipek, with G1's mass check) | 1 | $0.22 | 1 | 1 |
| **final (all 31, the final guide and engine)** | 31 | $3.59 | 23 | **31** |
| tenth (2026-10-16: Okada et al., the Majorana-current identity) | 1 | $0.15 | 1 | 1 |

**Gate: met** (`docs/g10/intake_results_final_pass.json`). In one pass with the final guide and engine, all 31
agent models are the hand-written ones under D19, 23 of them strictly. Of the eight that need D19, five differ
only by an SM-like h that meets no new state, declared in one writing and not the other (the DMWG Z′, Feng et
al.'s two, von Harling & Petraki, Holst et al.). The three coloured-partner entries (De Simone et al.'s two, Harz &
Petraki) need that and the paper's exact degeneracy as well. Four agents' first answers were refused by G1 and corrected by the agent on G1's reason: Kamon et al.'s (a
saddle for the stated vacuum), Cohen et al.'s (a coupling with no value), Choubey et al.'s (a vacuum that was not
stationary) and De Simone et al.'s scalar triplet (an index too many). G10 has cost $20.76 over all its passes.

## Re-scored at G12 with the corrected comparison (2026-10-15, $0)

The closure audit (G1-1, the G12 closure record) found that the comparison kept √(|c|² + |c₂|²) per
vertex, so a vector coupling equalled an axial one, a scalar a pseudoscalar, and g_u = g_d equalled g_u = −g_d. It
now compares chirality-resolved invariants, and solves over GF(2) for every self-conjugate field's sign and every
complex field's charge conjugation (which flips a vector current's sign). Re-scored on the final pass's stored
models (`--rescore`, `docs/g10/intake_results_final_pass.json`):

| entry | as run | re-scored | cause |
|---|---|---|---|
| Okada et al. | equal | differs | the agent's right-handed Majorana current has the wrong sign: it wrote N̄_R γ N_R = −½ N̄γγ⁵N, where the identity is +½ (corrected 2026-10-16: this row had said the ½ was missing) |
| Ipek et al. | equal | differs | the relative sign of y_χ and the portal B; found on 2026-10-16 to be the reference's error, not the agent's (below) |
| Berlin et al. | equal | equal | the zoo's reference had lost the i of its own quoted i e_D χ̄₁γχ₂ (corrected); G1 now refuses a current that is not hermitian |
| the other 28 | equal (under D19) | unchanged | |

**29 of 31 equal under D19, 21 strictly: G10's gate is not met as re-scored.** The two are the agent's errors, which
the old comparison could not see. The intake's models need G1's checks and a person's review, which the workbench
requires before a model is approved. D29 (ε as DarkCast's) changes no comparison.

## Closing G10 (2026-10-16, the owner: "fix and spend the $0.40 to close the issue")

Each of the two differences was checked against its paper before anything was paid for:
- **Ipek et al. (arXiv:1404.3716): the reference's error.** The paper writes L_dark = y_χ a₀ χ̄iγ⁵χ (eq. (3)) and puts
  V_port = i B a₀H₁†H₂ + h.c. in the potential (eqs. (4)–(5)), which enters L as −V. The zoo's reference had written
  +i B in L; the agent wrote −i B, which also reproduces eq. (14), V_port = B v a₀A⁰ (with A⁰ = −Im of the
  Higgs-basis doublet's neutral component, as both writings take it), and both have the same Type-II Yukawas. The
  reference is corrected (`docs/model_zoo.md`); the stored agent model is then equal, strictly. Re-scored at $0:
  **30 of 31 under D19, 22 strictly.**
- **Okada et al. (arXiv:1601.07526): the agent's error.** Both writings give the SM currents one sign convention,
  the reference −g_BL q f̄γf Z′, the agent +g_BL q f̄γf Z′, and N's B − L charge is −1. With N̄_Rγ^μN_R = +½ N̄γ^μγ⁵N
  (P_R = (1 + γ⁵)/2, and N̄γ^μN = 0 for a Majorana N), the reference's +(g_BL/2) N̄γγ⁵N is consistent and the agent's
  is not: it used −½, and so wrote +(g_BL/2) where its own convention gives −(g_BL/2). The guide now states the
  identity with its sign (`agents/canonical_intake.py`, "A Majorana fermion N made of a right-handed Weyl field").
- **The tenth pass:** Okada et al. alone, with the corrected guide (`docs/g10/intake_results_tenth_pass.json`; $0.15,
  under a $0.70 cap the owner approved, since the request's worst-case reservation was $0.64). **Equal, strictly:** the
  agent now writes N's coupling as −g_BL/2 in its +g_BL q f̄γf Z′ convention. The other 30 entries were not re-run with
  the guide's new line, which concerns only a right-handed Majorana current.

**G10's gate: met, 31 of 31 under D19 and 23 strictly**: 30 from the final pass as re-scored, and Okada et al.'s from
the tenth. G10 has cost $20.91 over all its passes.

**Re-scored with the external audit's repaired comparison (2026-10-16, A02/A03; $0):** the final pass 30 of 31 under D19 (22 strictly), the tenth pass's Okada et al. equal, so 31 of 31 (23 strictly) again. This is an **assembled result**: 30 stored results re-scored after the corrections and one entry re-run, not one fresh, independent 31-case pass (the audit's item 16).

## For the owner

The second pass's questions were settled on 2026-10-15:
- the SM h and the degeneracy regulator: D19;
- the two references that did not build: D20;
- the benchmark messages, the guide and a full rerun: done (above).

Those of the fourth pass were settled in the owner's second round (above).

Tests: `tests/agents/test_canonical_intake.py`, `tests/agents/test_planner.py`,
`tests/model_building/test_equivalence.py` (D19), `tests/model_building/test_feynman.py` (the generations fix, the
lepton-doublet names, Weyl currents), `tests/model_building/test_spectrum.py` (the vector-name check),
`tests/evaluation/test_zoo.py` (a target's vacuum value), `tests/model_building/test_equivalence.py` (D19's vector
portal; ε e Q written out against the kinetic mixing), `tests/model_building/test_spectrum.py` (the mass stated
twice).

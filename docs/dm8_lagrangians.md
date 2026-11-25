# DM8: Path 1 for arbitrary Lagrangians

Started and built 2026-10-01. Cost: $0.84 for the gate (section 9) and about $0.45 for the intake
rerun (section 15).
Every number below comes from a script in `docs/dm8/` or from the tests.

DM8 lets a user bring a model the library does not have: a Lagrangian, or a
particle content from which one is built. Deriving its couplings to quarks is
the one step that needs a language model, so this milestone is opt-in
throughout. A user without API keys can supply the quark-level coefficients
directly, and everything after them is deterministic.

## 1. From quarks to nucleons: DirectDM (built)

`library/interactions/quark_level.py`. A model reaches the rate code through
the quark-level operator basis of DirectDM (arXiv:1708.02678), whose Wilson
coefficients it runs and matches onto the nucleon-level operators O_i, with
its own nucleon inputs.

- **Its own environment.** DirectDM (MIT, commit `b949fb6`) runs in
  `<tools>/.venv-directdm` (setuptools < 81 for `pkg_resources`), through a
  small driver, as DIAMX and the Mu2e scripts do.
- **Exact in q.** DirectDM composes each coefficient from a constant and
  terms in q², 1/q² (photon exchange), 1/(m_π² + q²) and q²/(m_π² + q²), and
  the same for the η. Each is a term of the rate code's coefficient form, so
  the conversion is exact: it reproduces DirectDM's own assembled
  coefficients to 10⁻¹⁶ at every momentum transfer tested, in the three- and
  five-flavour theories.
- **The operator mass.** DirectDM writes q/m_N with the mean nucleon mass,
  the rate code q/m_u. A coefficient whose operator carries (q/m_N)^k is
  multiplied by (m_u/m_N)^k.
- **Two defects of DirectDM, handled.**
  - Its four- and five-flavour Majorana classes index past the end of an
    array, which NumPy ≥ 1.19 rejects. The driver restores the old tolerance
    for that one call.
  - It silently ignores a coefficient name it does not know. The driver
    refuses unknown names, since a typo in a derived coefficient would
    otherwise vanish.

## 2. Recognising the library's cards (built)

`library/interactions/matching.py`. A derived interaction is compared with
every card by a linear fit of the card's nucleon couplings. Each operator is
weighted by its natural size in a rate: (q/m_N)^k, and 10⁻³ per power of v⊥.
The comparison runs over q from 1 to 300 MeV, for protons and neutrons. A
coupling whose fitted effect is below 0.1% is reported as undetermined.

What it finds on standard quark-level models (`docs/dm8/standard_models.py`,
m_χ = 100 GeV):
- **Universal axial couplings** (DMWG A1) are the axial card, O4 and L15
  exactly (residual 4×10⁻¹⁶) without DirectDM's running from m_Z to 2 GeV;
  with it, 3.5×10⁻⁵.
- **Scalar couplings** (Yukawa-like, C75q) are O1 and L01 exactly (3×10⁻¹⁶).
- **An isovector axial current is the axial card only up to its pion pole:**
  the induced pseudoscalar, an O6 term ∝ 1/(m_π² + q²), leaves a residual of
  0.29. The library's axial card is a nucleon-level coupling and omits it.
- **Pseudoscalar quark couplings** (C78q) differ from the nucleon-level
  pseudoscalar card by 0.14, through the same pion and η poles.
- **Universal vector couplings** (DMWG V1) are the vector card at its physical
  couplings (g_V = 3g_q, g_T = 3(κ_p + κ_n)g_q) to 0.6%. DirectDM reduces a
  quark vector current at its leading chiral order: the magnetic terms carry
  only the anomalous moments. The library's card keeps the full Dirac
  reduction (arXiv:1308.6288), with μ = g_V + g_T.
- **The free fit hides that 0.6%.** With g_T fitted, the residual is 5×10⁻⁵,
  but the fitted g_T/g_V is −0.99 against −0.12 physically: the Pauli
  coupling absorbs the Dirac magnetic terms DirectDM leaves out. A card's
  verdict ("same", "close") is the statement to read. Its fitted couplings
  are not physical values when a coupling's effect is small.

So for axial and pseudoscalar couplings the quark-level route carries
physics the nucleon-level cards lack. The cards stay as nucleon-level
descriptions.

## 3. The explicit reduction: a check that needs no table (built)

`library/interactions/nr_projection.py`. For any effective Lagrangian
(dark matter bilinear) × (nucleon bilinear), the amplitude is computed with
explicit Dirac spinors in the conventions of Anand et al.: ūu = 1,
q = p′ − p, and their v⊥ and O_i. It is projected onto the O_i between Pauli
spinors, at elastic centre-of-mass kinematics. It reproduces their two
worked reductions (O1, and −4 O4 for axial × axial) and the standard results
for every Lagrangian of Table 1, up to the sign noted below.

This is the deterministic check of rank one in the plan's verification of a
bespoke derivation: a Lagrangian term's reduction no longer depends on a
table or on sign bookkeeping.

## 4. What the explicit reduction found in the library

- **Table 1's one-q operators carry the opposite overall sign.** The
  library's transcriptions of L6, L9, L11, L12, L14 and L18 (each with one
  factor q^α) have the opposite overall sign to the explicit reduction with
  q = p′ − p. All other Lagrangians agree. Harmless for a card on its own.
- **Eight mediator cards were wrong where they combine those with other
  Lagrangians.** The terms odd in q had the wrong sign relative to the even
  ones. The rate errors where they interfere at leading order: the anapole
  ×11 on sodium (+40% on fluorine), the magnetic dipole ×5 on sodium, the
  axial–vector ×2.3 on sodium. Corrected in DM4's generator; record in
  `dm4_library.md`, section 4a.
- **The vector cards lacked the nucleon's spin–orbit term in O3,** which
  Table 1's leading-order L5 omits: c3 = g_T + g_V/2, not g_T + g_V. Added;
  effect on rates below 0.2%.
- **DirectDM agrees with the explicit reduction** in every sign tested. Its
  leading chiral order drops O3 and the Dirac magnetic-moment terms of a
  vector current; their weight is below 1%.
- **How this was found:** DirectDM's magnetic dipole disagreed with the
  library's dipole card in the sign of its spin terms. LZ's own L9 sided with
  DirectDM, and so did the explicit reduction. DM2's validation of the rate
  code against WimPyDD, with every operator and every interference switched
  on, ties the explicit conventions to the rate code's.

## 5. Models as data, and their checks (built)

- **`core/model_spec.py`.** A model as fields (spin, self-conjugacy,
  chirality, generations, mass with its justification, gauge charges above
  or below electroweak symmetry breaking, charges under new U(1)s), couplings
  (value, mass dimension, justification) and terms (the fields with
  conjugation, the Lorentz structure, the coupling, "+ h.c."). Nothing in it
  is a formula to parse.
- **`library/interactions/model_checks.py`.**
  - Gauge invariance per term: U(1) charges add to zero, colour triality, an
    SU(2) singlet is possible, no lone gauge charge, no charged
    self-conjugate field.
  - Hermiticity: a term not its own conjugate needs "+ h.c.".
  - An anomaly flag for each new U(1) (all six coefficients, left-handed
    convention), and for axial couplings to Standard Model fermions written
    without chiral charges.
  - Tested on known answers: hypercharge is anomaly-free; B − L needs
    right-handed neutrinos; baryon number has an [SU(2)]²B anomaly.
- **`library/interactions/derivation.py`.** A derivation is DirectDM's Wilson
  coefficients as formulas in the model's couplings, the masses m_⟨field⟩
  and named Standard Model constants.
  - Every number is evaluated by SymPy against a closed symbol table. The
    formulas are untrusted text, so before SymPy sees them a tokenizer admits
    only numbers, arithmetic, parentheses, known symbols and a few functions.
  - The dimension check scales every mass by λ and requires λ^{4−d} for an
    operator of dimension d.
  - Two derivations are compared coefficient by coefficient at random
    parameter points; they agree within 1%.

## 6. The two agents (built; tested offline only)

`agents/lagrangian.py`. Both return typed data, never numbers.

- **Intake** turns a description (a Lagrangian, or a particle content) into
  a `ModelSpec`. Its instructions require that every part of the model left
  out goes in `dropped`, every unstated choice in `assumptions`, and that no
  coupling or field is invented.
- **Derivation** matches a `ModelSpec` at tree level onto DirectDM's basis,
  as formulas. Its prompt carries:
  - the basis with each operator's normalisation, including the ½ of the
    Majorana and real-scalar operators;
  - the sign conventions for integrating out a scalar, +(g₁g₂/M²)O₁O₂, and
    a vector, −(g₁g₂/M²)J₁·J₂;
  - the symbols a formula may use;
  - the library's mediator cards, so that an exact match can be named.
- **Defaults** (build plan): Claude Opus 5.5 derives, GPT-5.6 Sol checks.
  Different model families, so their errors are less likely to be the same.

## 7. The pipeline: a bespoke model to its limits (built)

`orchestrator/lagrangian.py`, and on the command line
`adroit lagrangian <model.yaml>` ($0, the model and its derivation given), or
`adroit lagrangian <model.yaml> --derive --budget B` (paid, opt-in: the deriver
`--model`, default Claude Opus 5.5, and the checker `--checker`, default GPT-5.6
Sol, under one hard cap; `--description "…"` instead of the file for a model in
words). The workbench's Track 1 page has the same as "Derive couplings (paid)",
behind the budget gate. Each step either passes or stops the run for a person:

1. **The model:** given, or from the intake agent.
2. **The deterministic checks:** a failure stops the run; anomalies are
   flagged.
3. **The derivation:** given, or from the derivation agent. A dimension
   failure stops the run.
4. **A second derivation** by the other model, compared at random points.
   A disagreement stops the run.
5. **DirectDM** at each dark matter mass, then the match against every card.
   The report lists every exact card, or at least the best three.
6. **Path 1's exclusion** in the chosen modules (DM5's code, given the
   interaction directly), including the telescope tier.
7. **The contract:** what was dropped (by the model, the derivation and
   DirectDM), the assumptions, and each mass and coupling with its
   justification.

Without language models the command costs $0: the user gives the model and
its coefficients. The language models are called only from Python, with
`use_language_models=True` and a client for each.

**Worked example** (`docs/dm8/majorana_scalar.yaml`, its report in
`docs/dm8/majorana_scalar/`).
- **The model:** Majorana dark matter and a real scalar coupling to quarks
  as their Yukawas, (y_χ/2) S χ̄χ + (g_q m_q/v) S q̄q, with y_χ = 0.5, g_q = 1
  and m_S = 500 GeV.
- **The derivation:**
  - C75q = y_χ g_q/(v m_S²) for the five light quarks;
  - the top through the heavy-quark relation, C71 = −y_χ g_q/(v m_S²).
- **The result:** DirectDM gives c₁ = 2.35×10⁻⁹ GeV⁻² (f_N ≈ 0.31, as
  expected for Higgs-like couplings). The match is exact to O1, L01, L05 and
  M_scalar. M_higgs_portal is close (10⁻³): its f_N are fixed inputs, whose
  proton-to-neutron ratio differs from DirectDM's by 0.2%.
- **The limits:** the strongest is XENONnT's at 30 GeV, μ_up = 0.18. μ
  multiplies every coupling, so this is σ_p < 1.9×10⁻⁴⁷ cm², as XENONnT
  publishes there.
- **Runtime:** seven minutes, one worker.

## 8. Not yet built

Nothing that DM8 planned. The numerical cross-check is built (section 14).
The open items are listed in section 13.

## 9. The gate, declared before the paid run (2026-10-01)

The plan's gate: *ten models with known answers are matched correctly,
including three that are not in the library.* This section fixes what that
means before any language model is called. It is committed before the run,
and the run uses the prompts of that commit.

**The models** (`docs/dm8/gate_models.yaml`, with the full derivations):

| id | model | dark matter | in the library | the known answer |
|---|---|---|---|---|
| G1 | vector mediator, universal quarks (DMWG V1) | Dirac | yes: M_vector, O1 | C61q = −g_χg_q/M²; c₁ = 3g_χg_q/M² (arXiv:1603.04156) |
| G2 | axial mediator, universal quarks (DMWG A1) | Dirac | yes: M_axial, O4 | C64q = −g_χg_q/M²; σ_SD ∝ (Δu+Δd+Δs)² (arXiv:1603.04156) |
| G3 | scalar mediator, Yukawa-like quark couplings | Dirac | yes: M_scalar, O1 | C75q = g_χg_q/(vM²), and the top: C71 = −C75q |
| G4 | real-scalar Higgs portal | real scalar | yes: O1 | C63q = λ/m_h², C65 = −λ/m_h²; σ = λ²f_N²μ²m_N²/(4πm_h⁴m_S²) |
| G5 | magnetic dipole | Dirac | yes: M_magnetic_dipole | C51 = 4π²μ_χ/e |
| G6 | anapole | Majorana | yes: M_anapole | C62f = 2𝒜eQ_f, every charged fermion, leptons included |
| G7 | vector mediator, universal quarks | complex scalar | yes: O1 | C61q = −g_χg_q/M²; c₁ = 3g_χg_q/M² |
| G8 | isovector axial mediator (u and d opposite) | Dirac | **no**: the pion pole | C64u = −C64d = −g_χg_q/M² |
| G9 | pseudoscalar coupling to d, s, b as m_q/v | Dirac | **no**: the π and η poles | C78q = g_χg_d/(vM²), q = d, s, b |
| G10 | electric dipole | Dirac | **no**: the photon pole, c₁₁ ∝ 1/q² | C52 = 4π²d_χ/e |

The derivations behind each known answer are in the YAML. Where a
cross-section is quoted:
- the DMWG formulas are from arXiv:1603.04156;
- the Higgs-portal formula is derived there from the amplitude 2κ·2m_N
  with κ = λf_N m_N/(2m_h²).

**What the agents see.** The intake agent reads only the description. The
descriptions name the fields and couplings, so that a derivation can be
evaluated at the reference's parameter points; naming is therefore not
tested. The derivation agents read the intake's model and the library menu.

**Matched correctly** means all four of:
- (a) the intake's model passes the deterministic checks;
- (b) the run completes, with no stop for a person;
- (c) the derivation's nucleon-level interaction agrees with the reference's
  within 1%, up to one overall sign, in matching's weighted measure. The
  comparison is made at the stated values and at two random points of the
  reference (seed 20261002);
- (d) the library's verdict is as stated: one expected card "same" or
  "close", or, for G8–G10, no card "same" or "close".

**The gate passes if all ten are matched correctly.**

**The run's rules:**
- One run, each model once.
- A wrong or invalid answer is not rerun. An API failure (no response after
  the client's own retries) is not an answer: that model is rerun, and the
  rerun is reported.
- Deriver claude-opus-5-5; checker gpt-5.6-sol at its default reasoning
  effort; the owner confirms both model ids.
- Budget $12, half to each model (the owner's approval, 2026-10-01); the run
  stops at its budget.
- `uv run python docs/dm8/gate.py --live --budget 12` writes
  `gate_live.json`, holding every model's and derivation's output, and
  `gate_live.md`. Since R0 they go to a new `runs/gates/dm8/<UTC>` folder
  unless `--out` names one.
- *Correction (R11): this single run never took place, so there is no
  `docs/dm8/gate_live.json` or `gate_live.md`.* The gate was run in two halves
  (amended below, 2026-10-01). Their tracked results are
  the live gate's record (dm8) and `.md` (the deriver's half,
  `--live --no-checker`) and the live gate's record (dm8) and `.md` (the
  checker's half, `--checker-half`).

**The dry run** (`--dry-run`, $0; `docs/dm8/gate_dry_run.txt`). The
reference answers stand in for both models.
- **All ten pass.** This tests the harness and the references, not the
  agents.
- **Controls:**
  - both agents off by a factor 2 fail (c), at 0.50;
  - a checker off by a factor 2 stops the run, failing (b);
  - every anapole sign reversed passes;
  - reversing the signs and leaving out the leptons fails (c), at 1.9%.
    The leptons reach the nucleons through DirectDM's QED running from m_Z.
- **Normalisations against the closed forms:**
  - G1 and G7 give c₁ = 3g_χg_q/M² to 0.25%;
  - G3 gives f_N = 0.309, against the card's 0.307;
  - G4 gives the Higgs-portal c₁ to 0.6%;
  - G5's fitted μ_χ is 0.99 of the Lagrangian's (the overall sign is free);
  - G6: see section 10;
  - G8 carries the pion pole in O6, and G10 has only c₁₁ ∝ 1/q².

**What a pass would show:** that the two models derive tree-level matchings
correctly, for:
- mediators of spin 0 and 1, with the top integrated out;
- electromagnetic moments with their leptons;
- scalar and Majorana dark matter;

and that the system then tells library equivalents from models outside the
library.

**What it would not show:**
- loop-level matching;
- models written above electroweak symmetry breaking (DirectDM's SU(2)×U(1)
  stage is not wired in);
- t-channel mediators, which need a Fierz rearrangement;
- the naming of symbols;
- the spread between runs: one run measures none.

**Prompt changes made while preparing the gate.** Two conventions were added
to the derivation prompt before this declaration:
- the top quark is integrated out onto the gluon operators;
- the photon couples to every charged fermion, leptons included.

Neither names a gate model.

**Also changed while preparing it:**
- Two derivations are compared up to one overall sign, which no rate can
  see.
- Their agreement is decided at the nucleon level, after DirectDM: a
  coefficient that cannot reach a nuclear recoil (below 1%) no longer stops
  a run.
- The pipeline stops for a person, rather than failing, when a formula does
  not evaluate or DirectDM refuses a coefficient.

**Amended before the run (2026-10-01), after the owner's viability list
(section 11):**
- The intake now also records:
  - the stabilising symmetry, as a parity per field;
  - the intended relic fraction;
  - the cosmological history;
  - the Standard Model fields, under fixed names.

  The run uses these prompts.
- New deterministic checks are flags and do not enter criterion (a):
  stability, perturbativity, the contact interaction's validity, and the
  unitarity of axial couplings.
- The reference models carry their Z₂ parities. Their known answers and the
  four criteria are unchanged, and the dry run still passes 10/10.
- **Prices** (the owner's figures from the providers' pages):
  - claude-opus-5-5: $4 per million input tokens, $20 output, $0.20 cache
    read;
  - gpt-5.6-sol: $4 input, $20 output, $0.40 cached input.
- **Expected spend:** about $0.5 for Claude and up to about $2 for GPT,
  most of it GPT's reasoning tokens. The cap is $12.

**Amended before the run (2026-10-01), the owner's instruction: the gate in
two halves.** The owner has no OpenAI key yet.
- **Now, the deriver's half:** claude-opus-5-5 as intake and deriver, with
  no second derivation:
  - `gate.py --live --budget 6 --no-checker`, Claude's half of the approved
    $12;
  - criteria (a), (c) and (d) as declared; (b) is only "the run completes";
  - results in the live gate's record (dm8) and `.md`.
- **Later, the checker's half:** gpt-5.6-sol derives the same ten models from
  the same intake models. It is compared with Claude's derivations at the
  nucleon level, and then (b) holds as declared.
- The gate is passed only when both halves are done. The checker's half is
  the first of DM8's final checks (section 13).

**The deriver's half: 10 of 10 matched correctly (2026-10-01).** Results
store: the live gate's record (dm8) and `.md`.
- **Spend:** claude-opus-5-5, $0.58 (23,192 input tokens, 22,266 output),
  against its $6 cap.
- **The criteria:** every model passes (a), (b) and (d). On (c) the
  difference from the known answer is exactly zero for all ten: Claude's
  formulas evaluate to the reference's values.
- **What Claude got right that a careless derivation would miss:**
  - **G3 and G4:** the top quark integrated out onto the gluon operator,
    C71 = −C75q and C65 = −λ/m_h²;
  - **G4:** the ½ of DirectDM's real-scalar operator;
  - **G6:**
    - the Majorana factor 2;
    - all three leptons;
    - the opposite overall sign convention for the photon current,
      C62u = −4e𝒜/3, which the gate allows: no rate depends on it;
  - **G5 and G6:** the matching library card named (M_magnetic_dipole,
    M_anapole).
- **The intake:** every model gets the minimal Z₂, with the dark matter odd.
  Each records its assumptions and what it dropped. For example, in G4 it
  drops the hhSS quartic and the S self-coupling, and states its sign
  convention for the potential.
- **The checklist's flags fire where expected:**
  - anomalies for G2 and G8: axial couplings to Standard Model quarks need
    extra fermions;
  - the contact interaction for G4: freeze-out at √s ≈ 200 GeV resolves the
    Higgs.
- **Status:** the deriver's half is done; the checker's half follows.

**The checker's half: 10 of 10 agree (2026-10-01).** Results store:
the live gate's record (dm8) and `.md`.
- **Spend:** gpt-5.6-sol, $0.26 (17,278 input tokens, 9,256 output), with
  the owner's OpenAI key.
- **Agreement:** each derivation was made from the intake model of the
  deriver's half. Every one agrees with Claude's at the nucleon level, and
  with the known answer, exactly.
- **The sign convention:** GPT wrote the anapole (G6) with the opposite
  overall sign to Claude's, the reference's convention. No rate depends on
  it.
- **The gate passes: 10 of 10 matched correctly, with both halves,** for
  $0.84 in all of the approved $12. The owner's review is final check 4.

## 10. The cards' couplings for Majorana dark matter

The gate's anapole check found that the library's card couplings are
**Feynman-rule couplings, in the Dirac normalisation.** A Majorana field
with the Lagrangian g χ̄Γχ has twice the vertex of a Dirac field with the
same Lagrangian, because the field contracts with both χ̄ and χ.

- For G6, the M_anapole card fitted to DirectDM's output gives 𝒜_card =
  1.98 𝒜 without the running, and 1.90 with it.
- So a Majorana model enters a card with twice its Lagrangian coupling,
  2g, or equivalently with its Lagrangian written as (g/2) χ̄Γχ, the
  usual convention for Majorana fields.
- This was not stated anywhere. It affects only Majorana users of cards
  with spin-½ couplings, and only the meaning of the coupling: a limit on
  the card coupling is a limit on 2g.
- DM8's bespoke route is not affected: DirectDM's Majorana operators carry
  their ½, and the interaction goes straight to the rate code.

## 11. Viability of a freeze-out model: the owner's checklist (2026-10-01)

The owner listed 28 checks that a thermal freeze-out model must pass, in four
groups:
- the thermal history (7);
- laboratory and observational searches (9);
- cosmology and astrophysics (6);
- theoretical consistency (6).

Freeze-out is the working assumption for now. The list is data
(`constraints/data/viability.yaml`). For each item the file records what
ADROIT computes today and where the rest is to be built.

**Every Path 1 report for a bespoke model now carries the list**
(`constraints/viability.py`), so no check is passed over in silence. Each item
gets one status for the model:
- **checked** or **flagged:** computed here;
- **assumed:** a stated assumption, here the standard cosmology;
- **applies, not yet computed:** with where it is to be built;
- **does not apply:** with the reason, read from the model's masses and
  couplings.

The rules state their thresholds:
- coannihilation partners and resonances within 20%;
- channel thresholds within 10%, counted only for channels the model
  reaches;
- long-range forces where α m_χ/M > 0.1;
- beam dumps below 3 GeV, B → K X below 4.79 GeV, stars and supernovae below
  1 GeV, BBN below 20 MeV;
- self-interactions by the Born estimate σ/m ≈ 4πα² m_χ/M⁴.

"Does not apply" is an estimate of relevance, not a limit.

**Built now**, because these change what a model is and what the intake is
asked, and the gate tests the intake's prompts:
- the model records its stabilising parity, intended relic fraction and
  cosmology;
- deterministic flags in `model_checks`:
  - **stability:** every term even under the stated parity, the dark matter
    odd and the lightest odd state;
  - **perturbativity:** couplings below √(4π), and 4π for a scalar quartic;
  - **the contact interaction:** a mediator above 10 q_max for direct
    detection, and above 4m_χ (s-channel) or 2m_χ (t-channel) for
    freeze-out;
  - **axial unitarity:** m_f ≲ √(π/2) M/g_A for every fermion, and the
    completion scale √s ≈ πM²/(g_A² m_χ). These are eqs. 2.8–2.9 of
    Kahlhoefer, Schmidt-Hoberg, Schwetz and Vogl, arXiv:1510.02110, section 2
    read; g_A is the Feynman-rule coupling, twice the Lagrangian's for a
    Majorana field.

**Later** (the plan's "Viability checklist" section lists the order): the
calculators. They do not touch the prompts, so adding them never invalidates
the gate.

On the gate's reference models the list behaves as expected. G4, the Higgs
portal at 100 GeV, is flagged: freeze-out at √s ≈ 200 GeV resolves the
Higgs, so the contact interaction cannot give its relic density. It also has
the ZZ threshold within 10%. G9's down-type couplings turn on the flavour
item.

## 12. No Mathematica (the owner's decision, 2026-10-01)

FeynRules and SARAH need Mathematica, a paid licence, so ADROIT will not use
them. The plan's numerical cross-check (verification rank two) becomes:
- **The project's own generator of UFO model files from a `ModelSpec`.**
  UFO is an open Python format, which MadGraph and MadDM read. For the
  models ADROIT handles, deriving the Feynman rules is bookkeeping:
  - tree level, renormalisable terms of typed Lorentz structure, written
    below electroweak symmetry breaking;
  - each term gives a vertex: i × coupling × its Lorentz structure, times
    the symmetry factors of identical fields (2 for a Majorana bilinear or a
    real-scalar pair);
  - masses, widths and couplings become parameters.

  It is validated against the LHC Working Group's DMsimp UFO models, which
  FeynRules wrote, vertex by vertex. MadDM's relic densities for V1 and A1
  are checked against DM7's own code.
- **Where it is more than bookkeeping, and stays out of scope until needed:**
  - models written above electroweak symmetry breaking (mass mixing,
    Goldstone bosons, gauge fixing);
  - derivative and higher-dimension operators;
  - one-loop model files, with their counterterms.
- **Open alternatives, to read before use:**
  - LanHEP (C), which writes CalcHEP model files for micrOMEGAs;
  - MARTY (C++), which derives Feynman rules and one-loop Wilson
    coefficients.

  Their licences, and micrOMEGAs's and MadDM's, are still to be read.

**Built the same day** (section 14). The owner settled the licence question
the same day: MadDM and micrOMEGAs are used under fair use, as dependencies,
never bundled.

## 13. Final checks before DM8 is closed

1. **The checker's half of the gate: done.** 10 of 10 agree, for $0.26
   (2026-10-01, section 9).
2. **The numerical cross-check: done** (section 14).
   - ADROIT's UFO files equal DMsimp's vertex by vertex.
   - MadDM's relic density agrees with DM7's within 2.6%.
   - MadDM's quark-level coefficients agree with both agents' derivations
     within 0.4%, for the six gate models MadDM can treat.
3. **Licences: settled by the owner (2026-10-01).** MadDM and micrOMEGAs are
   used under fair use, as dependencies: called, never bundled, and cited.
   The tools used are recorded, with their versions, licences and
   references, in `adroit/external/tools.yaml` and `related_work.md`. The
   README acknowledges them.
4. **The owner's review** of the gate's two halves and of the cross-check.

**For the owner to decide:**
- **A rerun of the intake on the ten gate descriptions** with the corrected
  intake prompt (section 14, finding 1), to test that its terms now carry
  their full coefficients. It is about $0.3 at the recorded prices, and the
  paid calls need the owner's approval.
- **Whether to report the MadDM release candidate's three bookkeeping issues
  to its authors** (section 14, findings 2–4).

## 14. The numerical cross-check (2026-10-01)

Verification rank two, without Mathematica (section 12). All the numbers
are in `docs/dm8/crosscheck.txt`; the script is `docs/dm8/crosscheck.py`,
which takes about an hour.

**The tools,** installed in the tools folder, called and never bundled (the
owner's fair-use decision for MadDM):
- MadGraph5_aMC@NLO v3.8.0.
- MadDM's 3.3 release candidate (rc/3.3 at 6570bb5). The stable 3.2.13 is
  Python 2 only, and the release candidate's latest commits fix
  compatibility with MadGraph 3.8.0.
- Its RAPIDD (f471a10), and the GNU Scientific Library 2.8, built for arm64
  because MadDM loads RAPIDD from an arm64 Python.

**ADROIT's UFO writer** (`library/interactions/ufo.py`):
- It copies MadGraph's own Standard Model at run time and adds the
  `ModelSpec`'s dark sector: particles, masses, widths, couplings, and a
  vertex per term and flavour.
- Each vertex is i × the term's coefficient × its Lorentz structure × the
  symmetry factor of identical fields.
- The u, d and s quarks get their masses and Higgs Yukawa couplings, so that
  couplings in proportion to m_q/v do not vanish.
- MadGraph computes the widths of new states from the vertices
  (`compute_widths`), in a session of its own, because MadDM's mode cannot
  run it.
- It refuses what it does not cover: dipoles, the anapole, derivative and
  higher-dimension operators, flavour-changing terms, and models above
  electroweak symmetry breaking.

**The results:**
1. **Against DMsimp_s_spin1** (FeynRules), at matched parameters:
   - V1, A1 and complex scalar dark matter: 7 vertices each, identical to the
     last digit, with no vertex in one model only. DMsimp writes the scalar
     current with a ½, so its g_VXc is twice this convention's coupling.
   - MadGraph's numerical width of V1's Z′ at 2 TeV is 112.7299 GeV;
     DMsimp's analytic one is 112.7295 GeV.
2. **Relic density, MadDM (ADROIT's UFO) against DM7's own code,** at four
   points each:
   - V1: MadDM/DM7 between 1.009 and 1.026;
   - A1: between 0.993 and 1.004.

   The points are (m_χ, M) = (100, 2000), (500, 2000) and (950, 2000) GeV,
   the last on the resonance, and (1500, 1000), where Z′Z′ is open. The
   remaining percent is plausibly g*: MadDM's is an ideal gas without the
   QCD transition.
3. **The gate's derivations against MadDM's quark-level coefficients.** The
   coefficients MadDM matches from the full model at zero momentum are
   compared in MadDM's own normalisation (its EffOperators model), up to one
   overall sign. Only the coefficients with a nucleon form factor in MadDM,
   and the quarks the model couples, are compared.
   - **Within 0.4%, for both Claude's and GPT's derivations,** in six models:
     - G1 (0.32%), G2 (0.31%), G3 (0.28%), G7 (0.13%), G8 (0.13%): the
       residue is the mediator's width in MadDM's zero-momentum propagator;
     - G4 (0.40%, sign reversed): m_h is 125 GeV in MadGraph's SM against
       125.25 in the model, and the overall sign is the SM Yukawa
       convention.
   - **Not covered:**
     - G9: the pseudoscalar operator is not in MadDM's direct-detection
       basis;
     - G5, G6 and G10: photon exchange, which the writer refuses and a
       zero-momentum calculation cannot treat.

     These four rest on the dimension check, the explicit reduction
     (section 3) and the two models' agreement.

**What it found:**
1. **The intake's terms carried only coupling names.** For example, `g_q`
   for g_q(m_q/v) q̄q in G3, and `lam_hs` for −(λv/2) hSS in G4. The full
   coefficient sat in the free text, as the intake prompt then asked
   ("coupling (a name)").
   - The derivation agents read the text and derived correctly, so the gate
     could not see it. Deterministic code that reads `coupling`, as the UFO
     writer does, could.
   - **Corrected:** a term's coupling is now its full coefficient, as an
     expression (`g_q*m_q/v`). The intake prompt and the schema say so, and
     a deterministic check flags a coupling that does not evaluate.
   - The cross-check therefore wrote its UFO files from the reference
     models, which state the same physics as the descriptions.
2. **MadDM 3.3's nucleon cross-sections are four times too large for Dirac
   and complex dark matter.** Its RAPIDD code uses σ = 4μ²|f|²/π (and
   12μ²|f|²/π for spin-dependent) without the factor ½ on f that 3.2.13
   applied to such fields. For V1 at (100, 2000) GeV it gives
   σ_SI = 1.50×10⁻⁴¹ cm², against 3.77×10⁻⁴² from the Working Group's
   formula. ADROIT therefore takes MadDM's quark-level coefficients, which
   are right, and not its cross-sections.
3. **MadDM 3.3 gives coefficients to quarks the model does not couple.** In
   G8 (u and d only), s, c, b and t carry u's axial coefficient. Its own
   spin-dependent cross-section would then include a spurious Δs term.
4. **MadDM's g* counts every particle of the model as an ideal-gas species,**
   with the default card's masses. That includes the ghosts and Goldstone
   bosons of a Feynman-gauge model such as DMsimp.
   - For V1 at (100, 2000) GeV this lowers Ωh² by about 10%: 1.80 with
     DMsimp, against 2.02 with ADROIT's unitary-gauge model and 1.98 from
     DM7.
   - Published relic contours made with MadDM and DMsimp may carry this
     bias. This is an observation; it has not been checked against them.
5. MadDM's reported ⟨σv⟩ at freeze-out for Dirac dark matter is a quarter of
   the χχ̄ cross-section, which is a convention. MadDM's mode cannot compute
   "auto" widths.

**In the pipeline:**
- `LagrangianRequest.numerical_check` and `adroit lagrangian
  --numerical-check` run the same comparison on a user's model
  (`constraints.maddm.coefficients` and `check`).
- A covered disagreement above 1% stops the run for a person. A model MadDM
  does not cover says why.
- MadDM's work folder is in the tools folder (`maddm.workdir`), because
  MadGraph cannot use a path with spaces such as this repository's.
- **The worked example** (`docs/dm8/majorana_scalar`, Majorana dark matter
  with the top quark through the gluons) passes with
  `--numerical-check`: the largest difference is 0.07%.
  - This adds a Majorana model to the six gate models.
  - It needed MadDM's Majorana normalisation: its self-conjugate vertex is
    2iα, so α is half DirectDM's Dirac-normalised coefficient.

## 15. The intake rerun, with the corrected prompt (declared 2026-10-01, before the run)

The owner approved the rerun, and decided that MadDM's issues (section 14,
findings 2–4) are recorded here and not reported.

**The run:** claude-opus-5-5 turns each of the ten gate descriptions into a
model again, with the corrected intake prompt (a term's coupling is its full
coefficient). It is capped at $1, against about $0.3 expected, and run as
`docs/dm8/intake_rerun.py --live --budget 1`.

**A model passes when all of these hold:**
- (a) every term's coupling evaluates;
- (b) every term of the reference model has an intake term with the same
  fields, whose coefficient has the same magnitude at the reference's
  values. The sign is a convention: the SM writes −(m_q/v) h q̄q;
- (c) where the UFO writer covers the model, MadDM's quark-level
  coefficients from ADROIT's UFO file *of the intake's model* agree with the
  gate's derivation within 1%.

**The control** (the script's `judge` on the gate's original intake models):
5 of 10 fail (b).
- G3 and G9 lose their m_q/v.
- G4 writes `lam_hs` for −λv/2, and an undefined `y_q`.
- G5 and G10 lose the ½ of the dipole.

The dry run, with the references standing in, passes 10/10.

**First attempt (2026-10-01): crashed at G6 on a harness bug, so it is repeated
in full within the same $1 cap.**
- **The bug:** the anapole model's MadDM run gave no results file, which the
  script did not catch, and it saved its outputs only at the end. The six
  intake answers (G1–G6) were lost; their logged verdicts were all passes.
- **Fixed:**
  - the script saves after every model;
  - a failed MadDM run is recorded as such.
- **A physics gap the crash exposed:** the writer accepted the intake's G6,
  so the intake must have coupled the neutral χ to the photon field A_μ
  itself, not to F_μν. That is not gauge invariant.
  - The gauge check now requires the photon (gluon) to couple through A_μ
    (G_μ) only to fields carrying its charge.
  - The UFO writer refuses such vertices.
  - Under the rerun's rule (a)+(c) such a model now fails: an honest change
    to what passes.

**The rerun: 9 of 10 pass the declared rules** (`docs/dm8/intake_rerun.json`
and `.txt`).
- **Spend:** $0.27 for the full rerun, $0.03 for the G6 check below, and
  about $0.15 for the crashed first attempt, whose spend was not saved: about
  $0.45 of the $1 cap.
- **The coefficients:** every term now carries its full coefficient. That
  includes the five models that failed the control: G3 and G9's m_q/v, G4's
  −λv/2 and −m_q/v, and the ½ of G5 and G10's dipoles.
- **MadDM from the intake's own models** agrees with the gate's derivations
  within 0.13–0.40% for every covered model (G1–G4, G7, G8).
- **G9 fails rule (b) by 0.6%, on inputs, not structure.** Its coefficients
  have the reference's form (`g_d*m_d/v`), but the intake gave the d and s
  fields its own masses (4.7 and 93 MeV, against the table's 4.67 and
  93.4), and a field's mass overrides the table. Reported as declared.
- **G6 typed the anapole as `axial` with the photon field**, with ∂^νF_μν
  only in the text. The new gauge check (above) stops such a model for a
  person.
  - The schema had no name for that structure, so the intake prompt and the
    checks now have `anapole` and `charge_radius` beside `dipole`.
  - A targeted rerun of G6 alone ($0.03, within the cap) types it
    `anapole` and passes; the UFO writer declines it, as it declines every
    photon-exchange operator.

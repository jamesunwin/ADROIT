# DM12: the model front end (Track 1's inputs)

Started 2026-10-03. The owner's design and decisions are in the build plan
("The dual-track system"). This record covers what was built, the gate
(declared in section 6 before its first run) and its result.

## 1. Group theory (`model_building/groups.py`)

- **Representations as weights.** A representation of SU(3) × SU(2) is held
  as its states, one weight per state. An SU(3) irrep (p, q) is built exactly
  as the traceless part of Sym^p(3) ⊗ Sym^q(3̄), so no tables are needed.
- **Invariants.** They are counted with the Weyl character formula,
  n₀ = Σ_σ ε(σ) m(ρ − σρ), over both Weyl groups.
- **Identical fields** enter as symmetric (or antisymmetric) powers, with
  flavour as part of each state. So the count is the number of independent
  couplings.
- **Checks:**
  - SU(2): 2⊗2 holds one invariant; Sym²(2) none; Sym³(3) none, Sym⁴(3) one;
    5⊗2⊗2 none.
  - SU(3): Λ³(3) holds one invariant and Sym³(3) none; 8⊗8⊗8 two (d and f).
  - Flavour: LLΔ has 6 independent couplings.

## 2. The most general Lagrangian (`content.py`, `lagrangian.py`, `spec.py`)

- **Fields as components.**
  - Fermions become left-handed Weyl spinors: a Dirac field is ψ and ψᶜ, a
    right-handed field enters as its conjugate, and a Majorana field is one
    spinor in a real representation.
  - Scalars are complex (φ and φ* distinct) or real.
  - A neutral vector is either a new U(1)'s gauge boson (named like the
    U(1)), which couples through covariant derivatives, or a massive vector,
    which couples to currents.
  - The Standard Model's fields are added: Q, uR, dR, L, eR with three
    generations, H, and B for kinetic mixing.
- **Every operator of dimension ≤ 4** allowed by the charges (hypercharge and
  every new U(1)) and the stabilising Z2, each with its number of independent
  couplings:
  - the scalar potential;
  - fermion masses and Yukawa couplings;
  - currents and scalar currents of massive vectors;
  - V·V times scalars;
  - kinetic mixing.
- **As a typed model** (`general_spec`), in Dirac notation for DM8's
  pipeline:
  - a complex Yukawa of a Dirac pair becomes scalar and pseudoscalar
    couplings;
  - a Dirac field's two chiral currents become vector and axial couplings;
  - every coupling is symbolic, with its mass dimension 4 − d;
  - the Standard Model fields the terms use are added.
- **Example** (`adroit idea --fields docs/dm12/inert_doublet.yaml`): the
  inert doublet gets |Φ|², λ₂|Φ|⁴, λ₃ and λ₄ (the two invariants of
  H H* Φ Φ*), and λ₅ (H H Φ* Φ* + h.c.).

## 3. Effective operators (`eft.py`)

- **The operators.** For a dark matter field that is a Standard Model singlet:
  its bilinears times the Standard Model's gauge-invariant blocks, from
  dimension 5 to 6, each with c/Λ^{d−4}.
  - The bilinears are scalar, pseudoscalar, vector, axial and tensor for a
    Dirac fermion; a Majorana fermion's vector and tensor vanish.
  - The blocks are |H|², |H|⁴, H†iD↔H, the five fermion currents, ∂^νB_μν,
    B_μν and its dual.
  - This gives the Higgs-portal and dipole operators at dimension 5, and the
    current, anapole and charge-radius operators at 6.
  - A Dirac fermion has 20; a Majorana fermion 9.
- **EFT validity** (`eft_flags`): Λ against direct detection's momentum
  transfer (~0.3 GeV), the freeze-out energy 2m_χ and the LHC's reach
  (~2 TeV), and whether a perturbative completion (M ≲ 4πΛ) can lie above
  2m_χ.

## 4. The audit (`audit.py`)

- **Validity** (each problem an error):
  - statistics;
  - the Lorentz label against the fields' spins;
  - mass dimension against the coupling's (higher-dimension terms are
    allowed, with a negative-dimension coupling, and then flagged for EFT
    validity);
  - gauge invariance (charges, and a counted SU(3) × SU(2) invariant);
  - hermiticity;
  - identities of self-conjugate fields (a Majorana vector or tensor
    bilinear, a real scalar's current).
- **Flags** (not errors): DM8's stability, perturbativity, anomaly,
  contact-interaction and unitarity flags. Symbolic couplings, as the
  generator writes them, are not flagged.
- **Missing terms** (for a model written above electroweak symmetry
  breaking): the generator's terms that the model does not supply. Terms are
  compared by their fields, their conjugation (up to overall conjugation) and
  their class (scalar against pseudoscalar, and vector against axial, for a
  Dirac dark field).
  - A neutral Dirac fermion is noted as pseudo-Dirac unless a conserved
    charge forbids its Majorana masses.
  - Tadpoles are noted: they are removed by shifting the field.

## 5. Free text and the front end (`agents/ideas.py`, `orchestrator/ideas.py`, `adroit idea`)

- **The model builder** (opt-in, paid) proposes field contents only: quantum
  numbers, stabilising parity, a rationale, and literature keywords (never
  references). The generator writes every allowed term, the audit checks the
  result, and duplicate field contents are dropped.
- **`adroit idea`** takes:
  - `--fields` (a field content);
  - `--lagrangian` (a typed Lagrangian);
  - `--lagrangian-text` (DM8's intake);
  - `--text` (the builder);
  - and `--eft 5|6`.

  It writes `result.json` and a report. The paid inputs need `--budget`.
- **What "valid" means.** Validity here is theoretical consistency, the
  owner's definition. What the data allow is DM13's question.

## 6. The gate (declared 2026-10-03, before its first run)

`docs/dm12/gate.py`. The dry run (parts A–C deterministic, part D scripted)
passed before the live run.
- **A. Textbook inventories.** Nine field contents give exactly their textbook
  operators, couplings counted:
  - the Standard Model's Yukawas and potential;
  - a Z2-odd real singlet;
  - the inert doublet;
  - a Majorana singlet;
  - the fermion quintuplet (minimal dark matter, a mass term only);
  - the fermion triplet without a Z2 (type-III seesaw);
  - the scalar triplet (type II, with LLΔ's 6 couplings);
  - a dark photon;
  - a massive Z′.
- **B. Seeded errors and false alarms.**
  - Twelve seeded errors, each caught by the right check: Lorentz (6),
    dimension (2), identities (2), gauge (1), hermiticity (1).
  - No validity problem in DM8's ten gate models or in the generated models
    of A.
- **C. Omissions:**
  - the singlet's Higgs portal;
  - the inert doublet's λ₅;
  - a Z′'s kinetic mixing and axial coupling;
  - a neutral Dirac fermion's pseudoscalar Yukawa and Majorana masses.

  Each must be found.
- **D. Free text** (claude-opus-5-5, capped at $1). Six ideas with textbook
  answers:
  - a Higgs-portal scalar;
  - fermion dark matter with a heavy neutral vector;
  - minimal dark matter;
  - an inert doublet;
  - a hidden U(1) with kinetic mixing;
  - a wino.

  Every proposal must be built into a valid model or dropped with a stated
  reason, and in at least five of six the textbook field content must be
  among the proposals.

## 7. The gate's result (2026-10-03): passed

| part | result |
|---|---|
| A. textbook inventories | 9 of 9 exact |
| B. seeded errors | 12 of 12 caught by the right check |
| B. false alarms | none: DM8's ten gate models and the generated models are all valid |
| C. omissions | 4 of 4 found |
| D. proposals valid or dropped with a reason | 6 of 6 ideas |
| D. textbook content among the proposals | 6 of 6 ideas |

Part D (claude-opus-5-5) cost $0.27 (the live gate's record (dm12), `.json`).
- **The textbook models were found:**
  - a real singlet with the Higgs portal;
  - a Dirac fermion with a Z′;
  - the fermion 5-plet, beside 7-plets;
  - the inert doublet, beside the scotogenic model;
  - a fermion with a dark photon;
  - the pure wino, beside a mixed wino–higgsino.
- **Duplicates were dropped:** two proposals repeated an earlier field
  content (a pseudo-Goldstone scalar; a dark-photon variant of the Z′).
- **The seeded case's label.** One seeded case, first labelled "no SU(2)
  invariant", tests a dimension error (a dimension-5 quartic of a fermion
  quintuplet). It was relabelled after the declaration; the case and the
  gate's counts are unchanged.

**A limitation the run showed.** The generator holds the Standard Model's
charges fixed: its fields are neutral under every new U(1). A proposal such as
a gauged B − L is therefore built with the quarks coupled to the new boson only
through kinetic mixing. The report now says so for every model with a new
U(1). Standard Model charges under new U(1)s, with their anomaly
cancellation, are future work.

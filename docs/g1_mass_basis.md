# G1 — The mass basis (2026-10-13)

Milestone G1 of [`freeze_out_build.md`](freeze_out_build.md). A typed model, in either phase, goes to its physical
spectrum: the vacuum, the mass matrices, and the mass eigenstates with their charges, parities and compositions.
The rotations are kept for G2's vertices.

## What was built

| module | what it does |
|---|---|
| `adroit/model_building/indices.py` | SU(2) generators in any dimension (spherical basis, Condon–Shortley), the invariant bilinear of any dimension, SU(3) in 3, 3̄ and 8, the triplet's Cartesian map; the index notation `ModelTerm.indices`; the unique default contractions; the gauge-invariance check |
| `adroit/model_building/gauge_basis.py` | a model as components (real scalar coordinates, Weyl spinors, vectors) and its Lagrangian as polynomials: the potential, the fermion bilinears M_ij(x), the vectors' actions on the scalars, stated masses and kinetic mixing |
| `adroit/model_building/spectrum.py` | the vacuum and its tadpoles, the unbroken charges, the scalar (Goldstones removed), fermion (Takagi; SVD) and vector (kinetic mixing) mass eigenstates; `spectrum(spec)`, `compute(spec)` |
| `adroit/core/model_spec.py` | two optional fields: `ModelField.vev_gev`, `ModelTerm.indices` (backwards compatible) |

## The physics, in brief

- **Components.** A complex scalar component is F = (x_re + i x_im)/√2. A real multiplet obeys φ₋ₘ = (−1)^m φₘ*.
  Either way the kinetic term is ½(∂x)². Fermions are left-handed Weyl spinors:
  - a Dirac field is ξ in (R, Y) with its partner η in (R̄, −Y);
  - a Majorana field is one ξ in its real representation;
  - a right-handed field enters as its conjugate.
- **The Lagrangian as polynomials.** Each term is expanded through its index contraction into the components:
  - scalar terms build the potential V(x);
  - fermion bilinears build L ⊃ −½ M_ij(x) ψ_iψ_j + h.c. A four-component bilinear Ψ̄_a(αP_L + βP_R)Ψ_b gives
    η_aξ_b, and its h.c. gives η_bξ_a. The barred Majorana field's index is mapped through the invariant metric,
    since conj(ξ_m) transforms as (−1)^m ξ₋ₘ;
  - the Standard Model's gauge bosons act through D = ∂ − igT^aW^a − ig′YB. New vectors act through their stated
    currents and seagulls.
- **The vacuum.** The stated vacuum values go in the neutral components; H has v = 246.21965 GeV, the G_F value. A
  field with a vacuum value has its m² fixed by its tadpole. A real gauge singlet with zero vacuum value takes an
  implicit linear term. Any other non-stationary direction refuses the model.
- **Charges.** The states are sorted by electric charge and by every U(1) acting on whole fields that the terms
  conserve and the vacuum keeps. The latter are the null space of the terms' charge sums, so a vectorlike dark
  fermion stays Dirac. Charged sectors are complex or Dirac; the neutral sector is real or Majorana.
- **Diagonalisation:**
  - **Scalars:** the Hessian, with the Goldstone directions t^V v projected out (unitary gauge) and M² t^V v = 0
    checked.
  - **Fermions:** a Takagi factorisation for the neutral block, from the eigenvectors of
    [[Re M, Im M], [Im M, −Re M]]; an SVD for each charged pair of blocks. A mass entry across unbroken charges is
    refused.
  - **Vectors:** the kinetic matrix is brought to unity (Cholesky), then the mass matrix is diagonalised; W± comes
    from W¹ and W².
- **Gauge invariance.** Every contraction is checked against SU(2) × SU(3) by applying the generators, and its U(1)
  charges must cancel. Writing the zoo's terms showed why this check is needed: a plausible transcription of Dedes
  & Karamitros's triplet Yukawa had a charge −2 piece.

## Conventions a model must state

- `mass_gev` is the Lagrangian mass:
  - a scalar's m²|F|², or ½m²F² if real;
  - a Dirac fermion's M χ̄χ; a Majorana fermion's ½ M χ̄χ;
  - a vector's ½m²V².

  It is used only when no explicit two-field term involves the field. A negative m² is an explicit term. A field
  with a vacuum value states `vev_gev` and no mass.
- `indices` is needed when a term has more than one non-trivial pairing, or a pairing of two different fields
  through an invariant other than δ or ε. Examples: (H†φ)(φ†H) against (H†H)(φ†φ); the triplet Yukawas.
  The default pairs a field with its conjugate (δ), a real field with itself (the metric), or two different
  fields in the order listed. The notation's tensors are in `indices.py`.
- A Majorana bilinear Ψ̄_aΨ_b is its own conjugate, so "+ h.c." doubles it. A paper's mass matrix decides which it
  meant: Choubey et al.'s eq. (16) has no doubling.
- A term with Standard Model fermions is kept for G2. The Standard Model fermions are not mixed with dark ones,
  which the Z₂ forbids.

## Validation

| check | result |
|---|---|
| The Standard Model alone | m_h = 125.09, m_W = 80.37, m_Z = 91.1876 GeV, a massless photon, no Goldstones left; μ_H² = −m_h²/2 |
| Electroweak multiplets (wino, higgsino, real 5-plet, Dirac 5₁) | degenerate at tree level with the right charges, Majorana or Dirac |
| Cohen et al.'s singlet–doublet mass matrix (eq. 3) | the three neutral eigenvalues to 10⁻¹⁰; the dark matter exactly at M_D for λ′ = −λ |
| Dedes & Karamitros, eq. (2.12) | neutral and charged mass matrices reproduced; in the custodial limit a state at M_D |
| Bhattacharya et al. | M₁, M₂ and M_N± from {M₁, M₂, sin θ} |
| The inert doublet (Kalinowski et al. BP1) | M_H, M_A, M_H± to 10⁻⁹ from λ₂ … λ₅ |
| A mixing singlet (Das et al.'s structure) | m_h₂, sin²θ, and the implicit tadpole a₁ = −μ_hs v²/2 |
| Choubey et al., eqs. (14)–(18) | m_h₁, m_h₂, m_H±, sin²α; the singlet–triplet fermion masses; ρ± at M_ρ |
| A dark Higgs | m_X = g v_φ; its Goldstone eaten; m_φ² = 2λ v_φ² |
| Refusals | a non-stationary vacuum; a term that is not gauge invariant |

Tests: `tests/model_building/test_indices.py`, `tests/model_building/test_spectrum.py` (24).

**The gate** (`docs/g1/spectrum_gate.py`): every development-half benchmark of the zoo against the masses its
paper prints. All agree, to 10⁻⁶ or the paper's printed precision: the 12 models and 27 benchmarks of the
development half. The held-out half was not run, as the plan requires.

## Entry corrections made for G1 (before any result that uses them)

Each changed entry says so in its notes:
- **Explicit contractions:** the inert doublet's λ₃–λ₅; Cohen et al.'s terms (those reproducing their eq. (3));
  Bhattacharya et al.'s N̄H̃χ⁰; Dedes & Karamitros's Yukawas (invariant forms reproducing their eq. (2.12)).
- **Vacuum values:**
  - Choubey et al.'s triplet (v_Δ = v tan δ/2, the potential from their eq. (15));
  - Kamon et al.'s dark Higgs (v_φ = m_V/g_V, V's mass from it).
- **Lagrangian masses:**
  - GAMBIT's singlet μ_S and vector μ_V;
  - Das et al.'s negative μ_s², as an explicit term, with λ_H stated so that m_h₁ = 125 GeV.
- **Dropped, as not affecting freeze-out and unspecified by the papers:**
  - the higgsino's and the complex triplet's splitting operators;
  - the quartics λ_S, λ_V, λ_χ;
  - Okada & Okada's Φ.
- **Set small, with the paper's words:** Pospelov et al.'s κ and D'Agnolo & Ruderman's ε, unspecified kinetic
  mixings.

## Limits

- **Tree level.** Radiative splittings (the wino's 165 MeV) are not included; G8 adds them. Running couplings are
  not used: the SM is at its inputs, with g and g′ from m_W, m_Z and v.
- **No mixing of dark fermions with Standard Model fermions:** a Z₂-even vectorlike fermion would need it.
- **The SM's Yukawas and CKM** are not in the gauge basis: G2 adds the fermions in their mass basis.
- **Terms with more than two coloured fields** give no mass and are kept for G2. A coloured state's colour index is
  a label, never mixed.

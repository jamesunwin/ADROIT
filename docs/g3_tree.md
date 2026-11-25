# G3 — The tree engine completed (2026-10-13)

Milestone G3 of [`freeze_out_build.md`](freeze_out_build.md): a general tree-level 2 → 2 engine for any process of
a model given as particles and Feynman rules, the input every later step of the generic route uses (G4's
annihilation and coannihilation, G5's matching, G6's annihilation today, G7's hard annihilation matrices).

## What was built

- **`adroit/constraints/tree.py`**, rewritten behind its existing interface (`Particle`, `Vertex`, `Model`,
  `Process.sigma`, `Process.squared`):
  - **Every external-spin combination.** Spins 0, ½ (Dirac or Majorana) and 1 (massive or massless), with unequal
    masses in the initial and final states.
  - **Every tree diagram.** The contact term, and the s-, t- and u-channel exchange of any particle: scalar,
    vector or fermion.
  - **Majorana fermions by Denner's rules** (continuous fermion flow, Γ' = C Γᵀ C⁻¹ against a vertex's
    orientation, v = C ūᵀ for the same spin state). Fermi statistics come from the permutation of the external
    spinors.
  - **New vertex kinds:** FFSS, a four-point fermion–scalar contact (the dimension-5 Higgs portal), and VVVV
    with its three g·g pairings.
  - **Colour** (`adroit/constraints/tree_colour.py`). Particles carry their SU(3) representation, and vertices a
    UFO colour string or an inferred default. Each diagram's colour tensor is contracted over the internal line,
    and the colour-summed square is Σ K_dd' M_d M_d'*.
  - **One evaluation for all states.** Every spin, polarisation and angle is computed in a single batch, and
    fermion lines are evaluated as matrix–vector products.
- **`adroit/constraints/ufo_model.py`** gained:
  - **Full colour** (`to_model(..., full_colour=True)`): gluons, squarks and gluinos, with colour strings remapped
    to the engine's slots.
  - **Four-vector vertices.**
  - **Goldstones recognised as `goldstoneboson` as well as `goldstone`.** The SM and MSSM UFOs use that flag;
    before, it was missed and their Goldstones were exchanged in a unitary-gauge calculation.
  - **Negative Majorana masses** (SLHA) rotated into the couplings.
  - **Evaluation at an SLHA param card** (`dump(..., param_card=)`).
  - **Two-body widths of fermions as well as bosons,** with the vertex's colour sum averaged over the parent's.
  - **The correct reading of a UFO vertex** (below).

## The conventions (for G2, which writes the engine's models)

- **Vertices** (`tree.Vertex(kind, legs, c, c2, c3, colour)`):
  - **Legs.** Every leg is incoming, and the Feynman rule is i·V.
  - **V** is the Lagrangian coefficient times its combinatorial factor: ½χ̄Γχ of one Majorana field gives V = Γ.
  - **Fermion terms.** For ψ̄_i Γ ψ_j X the legs are (antiparticle of i, j, X): FFS Γ = c + i c₂γ⁵ (complex,
    so any chiral couplings), FFV Γ = γ^μ(c + c₂γ⁵).
  - **A Majorana pair i ≠ j** has one vertex, which serves a fermion line in either direction.
  - **The h.c. of a Dirac term** is its own vertex.
  - **Derivative couplings carry their i in c.** For example, V_ggg = −i g_s f^abc with VSS (G, φ, φ*) = −g_s and
    FFV (q̄, q, G) = −g_s γ^μ: the sign that makes φφ* → gg gauge invariant.
- **Particles** (`tree.Particle(..., colour="1"|"3"|"3bar"|"8")`):
  - `anti=""` for a self-conjugate particle, which for spin ½ is a Majorana fermion;
  - masses are positive (rotate a negative Majorana mass into the couplings, as the reader does).
- **Colour strings** are UFO's, over 1-based slot positions: `T(a,i,j)` with i the triplet slot and j the
  antitriplet slot, `f`, `d`, `Identity`, `Epsilon`. Left empty, the default is inferred:
  - δ for two coloured legs;
  - T for a triplet pair with an octet;
  - f for three octets;
  - {T^a, T^b} for a triplet pair with two octets.

## Reading a UFO vertex: what MadGraph showed

The first comparison left five MSSM processes in disagreement. Each diagram class matched alone, but their
interference did not. In every case the cause was the UFO's convention:
- **A UFO vertex names the particles its fields create**, and P(μ, j) is that particle's momentum. Read with
  all-incoming names, [n1, u, su1~] with P_R gave ũ_L a coupling to u_R, which is unphysical.
- **The correct reading** is ū P_R χ ũ_L.
- **For a Dirac particle–antiparticle vertex the two readings coincide**, since the UFO also lists the h.c. term.
  That is why every Dirac process agreed from the start.
- **For a derivative coupling of two real scalars (Z A h) the sign flips.** For a complex pair the name
  conjugation compensates.

The reader now conjugates every name, puts position 2 in the f̄ slot and position 1 in the f slot, and changes
the sign of VSS and VVV.

Three things in the references themselves had to be fixed before the comparison was fair:
- **Coupling orders.** MadGraph by default keeps only the leading coupling order (its WEIGHTED count), dropping
  for instance the photon and Z s-channel of q̃q̃* → qq̄ where the gluon's exists. The references now request
  every order.
- **Rounding.** MadGraph reads a param card written to 7 digits. A rounding of 10⁻⁷ in a mixing matrix spoils
  gauge cancellations differently in two codes, so ADROIT's dump is now evaluated at the same card.
- **Goldstones.** The `goldstoneboson` flag, above.

## Validation

**MadGraph 3.8** standalone matrix elements: |M|², summed over final and averaged over initial helicities and
colours, at 9 phase-space points each (√s = 1.2, 2 and 5 × threshold; cos θ = −0.7, 0.1, 0.6), for 42 processes.
The reference script is `docs/g3/madgraph_references.py`; the fixtures are in `tests/constraints/data/g3_*`.
Classes: S scalar, V vector, F Dirac fermion, M Majorana fermion.

| model | process | class | diagrams | max \|ratio − 1\| |
|---|---|---|---|---|
| sm | W+ W- → Z Z | VV→VV | 4 | 2e-11 |
| sm | a a → W+ W- | VV→VV | 3 | 2e-14 |
| sm | b b~ → t t~ | FF→FF | 5 | 3e-15 |
| sm | e+ e- → W+ W- | FF→VV | 4 | 4e-13 |
| sm | e+ e- → Z H | FF→VS | 3 | 1e-15 |
| sm | e+ e- → e+ e- | FF→FF | 6 | 4e-15 |
| sm | e+ e- → mu+ mu- | FF→FF | 3 | 1e-15 |
| sm | e- e- → e- e- | FF→FF | 6 | 4e-15 |
| sm | g g → t t~ | VV→FF | 3 | 2e-15 |
| sm | t t~ → Z H | FF→VS | 3 | 8e-15 |
| sm | t t~ → g g | FF→VV | 3 | 1e-15 |
| sm | t t~ → t t~ | FF→FF | 8 | 4e-15 |
| sm | u d~ → W+ a | FF→VV | 3 | 3e-14 |
| sm | u u~ → g g | FF→VV | 3 | 2e-15 |
| DMsimp_s_spin1 | Xd Xd~ → Y1 Y1 | FF→VV | 2 | 1e-13 |
| DMsimp_s_spin1 | Xd Xd~ → b b~ | FF→FF | 1 | 3e-16 |
| DMsimp_s_spin1 | Xd Xd~ → t t~ | FF→FF | 1 | 1e-15 |
| MSSM_SLHA2 | W+ h01 → W+ h01 | VS→VS | 7 | 6e-14 |
| MSSM_SLHA2 | Z Z → h01 h01 | VV→SS | 7 | 1e-13 |
| MSSM_SLHA2 | b b~ → Z h01 | FF→VS | 4 | 3e-14 |
| MSSM_SLHA2 | go go → g g | MM→VV | 3 | 2e-15 |
| MSSM_SLHA2 | go go → u u~ | MM→FF | 5 | 2e-15 |
| MSSM_SLHA2 | n1 n1 → W+ W- | MM→VV | 7 | 8e-15 |
| MSSM_SLHA2 | n1 n1 → Z Z | MM→VV | 10 | 4e-14 |
| MSSM_SLHA2 | n1 n1 → b b~ | MM→FF | 8 | 3e-15 |
| MSSM_SLHA2 | n1 n1 → e+ e- | MM→FF | 5 | 3e-15 |
| MSSM_SLHA2 | n1 n1 → h01 h01 | MM→SS | 10 | 2e-15 |
| MSSM_SLHA2 | n1 n2 → Z h01 | MM→VS | 10 | 5e-15 |
| MSSM_SLHA2 | n1 n2 → x1+ x1- | MM→FF | 8 | 5e-15 |
| MSSM_SLHA2 | n1 su1 → n1 su1 | MS→MS | 5 | 2e-15 |
| MSSM_SLHA2 | n1 su1 → u g | MS→FV | 2 | 2e-15 |
| MSSM_SLHA2 | n1 x1+ → W+ a | MF→VV | 2 | 1e-13 |
| MSSM_SLHA2 | n1 x1+ → u d~ | MF→FF | 3 | 1e-15 |
| MSSM_SLHA2 | su1 g → su1 g | SV→SV | 5 | 2e-15 |
| MSSM_SLHA2 | su1 g → u n1 | SV→FM | 2 | 1e-15 |
| MSSM_SLHA2 | su1 su1 → u u | SS→FF | 10 | 1e-15 |
| MSSM_SLHA2 | su1 su1~ → g g | SS→VV | 5 | 2e-15 |
| MSSM_SLHA2 | su1 su1~ → u u~ | SS→FF | 8 | 2e-15 |
| MSSM_SLHA2 | u u~ → su1 su1~ | FF→SS | 8 | 2e-15 |
| MSSM_SLHA2 | x1+ x1- → W+ H- | FF→VS | 7 | 1e-13 |
| MSSM_SLHA2 | x1+ x1- → W+ W- | FF→VV | 8 | 6e-12 |
| MSSM_SLHA2 | x1+ x1- → Z h01 | FF→VS | 6 | 2e-14 |

The largest deviations (10⁻¹¹ in WW → ZZ and χ̃⁺χ̃⁻ → W⁺W⁻) sit where the unitary-gauge cancellation is
deepest. The test asserts 10⁻⁹.

**The hand-written processes** of `processes.py` and `amplitudes.py` are reproduced to 10⁻¹²:
- t-channel annihilation, Dirac and Majorana (Fermi statistics);
- φφ → ff through a Majorana mass insertion, coloured and not;
- φφ* → gg, φφ* → qq̄ (gluon and χ exchange), χφ → q g;
- φφ* → VV massive, χχ̄ → Z′Z′, χχ̄ → Zh.

**Internal consistency:**
- **Flow independence.** |M|² is unchanged when every fermion line's arbitrary flow is reversed (to 10⁻¹²).
- **Ward identities** (ε → k gives zero) for scalar Compton scattering, φφ* → γγ and χφ → q g (to 10⁻¹²).
- **Unitary-gauge cancellation.** σ·s of e⁺e⁻ → W⁺W⁻ and tt̄ → W⁺W⁻ stays flat from 2 to 2000 TeV, with zero
  widths and an exactly gauge-consistent third generation. With the SM UFO as published, tt̄ → W⁺W⁻ grows like
  s, identically in MadGraph and here (6399.19 at 100 TeV in both): the model's top Yukawa is its own input,
  not √2 m_t/v, and its CKM entries are rounded. A fixed s-channel width breaks the cancellation too (the reason
  for the complex-mass scheme).

**Two-body widths** against MadGraph's `compute_widths` at the same card:
- the top, χ̃₁⁺, χ̃⁰₂, W and Z agree to MadGraph's 7 printed digits;
- ũ_L agrees once the four partial widths MadGraph set to zero ("below the QCD scale") are added back;
- the gluino is 1.2845 times MadGraph's in every channel: α_s(M_Z)/α_s(m_g̃), since MadGraph runs α_s to the
  parent's mass.

## Speed

Ten neutralino-annihilation channels of the MSSM, at the default 20 angular nodes:

| channel | σ(s) per call |
|---|---|
| χχ → b b̄, t t̄, e⁺e⁻, μ⁺μ⁻, hh, Zh; χχ̃⁺ → u d̄, W⁺γ | 0.8–2.2 ms |
| χχ → W⁺W⁻ | 4.2 ms |
| χχ → ZZ (ten diagrams, 36 polarisation states) | 5.9 ms |
| all ten | 20 ms per energy node |

Finding the diagrams takes 0.2–0.7 ms per process, once.

## Limits

- **Not supported:** four-fermion contact vertices; the four-gluon vertex unless stated as VVVV with an explicit
  colour string; loops; 2 → 3.
- **Massless gauge bosons** carry only their two physical polarisations. This is exact for external gluons and
  photons, since in the unitary gauge every exchanged boson is physical.
- **Fixed widths** in every propagator, as MadGraph uses with `zerowidth_tchannel False`. At very high energy a
  fixed s-channel width spoils gauge cancellations; the complex-mass scheme is not implemented.
- **α_s** is the model's fixed value. Its running to a process's scale is the caller's choice.

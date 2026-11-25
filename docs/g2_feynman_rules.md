# G2 — Feynman rules in the mass basis (2026-10-13)

Milestone G2 of [`freeze_out_build.md`](freeze_out_build.md). From G1's mass basis, every vertex of a typed model's
physical states, the widths of its bosons, and the model as the tree engine's input (`constraints.tree`, G3).

## What was built

`adroit/model_building/feynman.py`. Each vertex is a derivative of the Lagrangian expanded about the vacuum and
rewritten in the physical fields, V = ∂ⁿL/∂Φ_a∂Φ_b…, with the combinatorial factors included. The gauge-basis
fields are written in the physical ones (y = AΦ, ψ = Bw, V = RE), and:

| interaction | from | vertices |
|---|---|---|
| the scalar potential | −∂³V, −∂⁴V of V(v + y) | SSS, SSSS |
| fermion masses and Yukawas | L ⊃ −½ M_ij(y)ψ_iψ_j + h.c.: its first and second derivatives | FFS, FFSS |
| the scalars' gauge interactions | ½(Dy)², Dy = ∂y − Σt^V y V: the current, the vacuum term, the seagull | VSS, VVS, VVSS |
| the fermions' gauge interactions | ψ†σ̄ G^V ψ V, with G^V = gT^a (or −gT^a* on a conjugate block), g′Y, and stated currents | FFV |
| SU(2)'s own bosons | −g ε^{abc}(∂W^a)W^bW^c | VVV |
| the strong interaction | D = ∂ − ig_sT^aG^a for quarks and every coloured state; the gluon's own vertex | FFV, VSS, VVSS, VVV |
| SM fermions | their gauge currents, rotated with any mixing of the neutral vectors (Z–Z′, γ–A′); their Yukawas through each scalar state's H⁰ and H± components; stated currents and Yukawas (a mediator's, or a t-channel partner's) | FFV, FFS |
| below electroweak breaking | the W, Z, h couplings of the SM directly | FFV, VVS, VVSS, VVV |

**Fermions in four-component form.** Each mass-basis Weyl component is the upper component of one species' field:
- a Majorana λ_A is the upper component of Ψ_A;
- a Dirac fermion's χ_A is the upper component of Ψ_A, and its ζ_A of Ψ_Aᶜ (leg A~).

A Weyl bilinear w_p w_q is then Ψ̄ P_L Ψ on those legs, and its h.c. gives the P_R part. A current w_p†σ̄w_q is
Ψ̄γP_LΨ. For one Majorana field this is −½Ψ̄γγ⁵Ψ, so the vertex is γ(P_L − P_R)G after the identical-field factor
of 2. The two fermion slots are put in a fixed order, Ψ̄_XΓΨ_Y = Ψ̄_YᶜΓ′Ψ_Xᶜ with Γ′ = CΓᵀC⁻¹, so that each vertex
appears once. A Majorana pair has one vertex.

**Widths.** Every boson's tree-level two-body width comes from closed forms per vertex type (S → SS, S → ff̄,
V → ff̄, V → SS, S → VS, S → VV, V → VS), with colour sums. Fermions get no width here: dark fermions are exchanged
only in the t- and u-channels. G4 replaces the SM-like h's width with the SM width at its mass (off-shell
included, `constraints.higgs.width`), weighted by its H⁰ share, plus its decays into new states.

## Conventions

- **Leg names.** A real scalar, a Majorana fermion and a neutral vector are their own antiparticles; any other state
  s has antiparticle `s~`. The field Φ_s annihilates an incoming s.
- **Sign conventions.**
  - Covariant derivatives are D = ∂ − igT^aW^a − ig′YB − ig_sT^aG^a (the SM's).
  - Each eigenvector's largest component is made positive, so the photon couples as +eQ.
  - The SM is at its G_F-scheme inputs (m_W, m_Z, v), with g = 2m_W/v.
- **g_s** is α_s at the dark matter's mass.
- **QCD signs.** The strong vertices use the tree engine's colour structures (T(a, triplet, antitriplet), f(1,2,3))
  and its gauge-consistent signs, read from MadGraph's MSSM: q̄qg and a triplet's FFV and VSS have c = −g_s, an
  octet fermion's FFV and the gluon's VVV c = −ig_s, the seagull c = g_s². (G2 first had +g_s on the triplets:
  right at threshold, where only the seagull and t-channel matter, but φφ* → gg was off by 2 at √s = 5.7 m_φ.
  Found at G4.)

## Validation

| check | result |
|---|---|
| Higgs self-couplings | hhh = −3m_h²/v, hhhh = −3m_h²/v² |
| hWW, hZZ, hhWW, hhZZ | 2m_W²/v, 2m_Z²/v, 2m_W²/v², 2m_Z²/v² |
| WWγ, WWZ | −e, −g c_W (the convention's phase) |
| Z ē e | g_L, g_R = (g/c_W)(T₃ − s_W²Q), −(g/c_W)s_W²Q |
| W ν̄ e | (g/√2)γP_L |
| h t̄ t | −m_t/v |
| Inert doublet | γH⁺H⁻ = e, WH⁰H± = g/2, ZH⁰A⁰ = g/(2c_W), γγH⁺H⁻ = 2e² |
| Wino and higgsino | W, γ, Z couplings g, e, g c_W; g/√2, e, g/(2c_W), (g/c_W)(½ − s_W²) |
| Bhattacharya et al. (BP4) | the Z and W couplings of the mixed states carry sin²θ, cos²θ, sin θ |
| A Majorana Higgs-portal EFT | FFS = −λ cos ξ·v, c₂ = −λ sin ξ·v; FFSS = −λ cos ξ |
| Giacchino et al.'s lepton partner | a purely right-handed coupling of 1.17 = y_l |
| Widths at tree level | Γ_W = 2.044, Γ_Z = 2.44 GeV; Γ_h = 4.94 MeV from bb̄, cc̄, ττ̄ |
| The zoo | every development-half model gets its rules (44–135 vertices each, in milliseconds) |
| QCD (at G4) | φφ* → gg, φφ* → uū, χφ → ug, χχ → uū, φφ → uu equal the hand-written amplitudes (10⁻⁷ near threshold); a Majorana octet's χχ → gg, uū equal MadGraph's gluino |

Tests: `tests/model_building/test_feynman.py`.

The processes themselves are checked at G4, through the tree engine:
- gauge cancellation in χχ̄ → W⁺W⁻;
- the library's engines on the controls (route agreement);
- MadDM, through the UFO export (see "Still to do").

## Limits

- No fermion widths. No colour-octet scalars.
- Terms with more than two coloured fields: none of the zoo's models has one.
- Four-fermion and dipole operators.
- CKM = 1.

## Still to do

The UFO export, for MadDM (decision D3), is built for G4's independent cross-check.

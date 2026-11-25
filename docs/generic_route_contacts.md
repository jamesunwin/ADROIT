# Four-fermion contact interactions in the generic route (2026-10-20)

The batch plan's §5 asks the generic route for four-fermion contact interactions, "with their validity, √s ≪ Λ,
checked at freeze-out". Before, G1 refused any term with more than two fermions ("write its mediator").

## What a model may state

A term k (Ψ̄_D Γ Ψ_D)(f̄ Γ′ f): the dark bilinear first, of one colourless SU(2)-singlet four-component dark fermion,
then one Standard Model fermion field's, each barred field written first, with `lorentz` naming Γ ⊗ Γ′ from
S = 1, P = iγ⁵, V = γ^μ, A = γ^μγ⁵, T = σ^μν: `SS`, `SP`, `PS`, `PP`, `VV`, `VA`, `AV`, `AA`, `TT`. The coupling k has
mass dimension −2 and may use each flavour's mass (`c*m_q/v` for a Yukawa-like scalar operator).
- **Below electroweak breaking**, with four-component Standard Model fields (`q`, `l`, or a named flavour), every
  structure.
- **Above it**, with the Weyl fields (Q, u_R, d_R, L, e_R), only the currents (Γ′ = V, the field's chiral current
  f̄γ^μP_{L,R}f = ½(V ∓ A)): the gauge-invariant operators at dimension 6.
- **Refused, with the reason:** a dark self-interaction, four Standard Model fermions, a flavour-changing pair, a dark
  fermion that mixes with others or whose mass state is chirally rephased (a negative Majorana mass would exchange
  its S and P bilinears).

## How it is computed

- **G2** writes one FFFF vertex per Standard Model flavour (`feynman.contact_vertices`), its coefficient k itself.
- **The tree engine** (`tree`, kind `FFFF`) takes every Wick contraction of the external legs with the vertex's two
  fermion lines, each line either way when the names allow and the two lines exchanged, each with its Fermi sign (as
  for two-line exchange diagrams); a line run against its orientation takes CΓᵀC⁻¹, which reverses V and T. So the
  Fierz-crossed terms of identical fields and a Majorana bilinear's two contractions follow (its S, P and A doubled,
  its V and T cancelled), and the relic density and today's annihilation need nothing further.
- **Direct detection**: the contact is DirectDM's operator itself (`dd_matching._contacts`): C61–C64 for V and A,
  C75–C78 (m_q-weighted) for S and P, doubled for Majorana dark matter, whose DirectDM operators carry ½. A tensor
  contact is not in the matching: its direct detection is pending with that reason.
- **The LHC**: a contact term is not exported to MadGraph (its UFO Lorentz structures are not written), so a model
  with visible new states and a contact term has its pair production undecided with that reason; monojet limits on
  contact operators need their own records.

## Validity at freeze-out (declared)

The relic is computed where √s at freeze-out, 2m_χ(1 + 3/(2x_f)) with x_f = 20, is at most Λ/3, with
Λ = |c|^(−1/2) of the dark matter's strongest contact structure, c summed over every term with the same legs and
bilinears (so two halves are the whole, and two that cancel are none: the tactical audit's T20-04, 2026-10-20); above
that it is pending with the reason. Below it
the relic holds up to O(s/Λ²) corrections from whatever completes the contact: a unit-coupling s-channel mediator of
mass Λ changes the rate by 1/(1 − s/Λ²)² − 1, about 27% at the margin (s/Λ² = 1/9; an earlier text said about 20%) and
9% at Λ/5. The owner's decision (#6, 2026-10-20): keep Λ/3, and flag a
relic computed between Λ/5 and Λ/3, with that shift in the flag (`generic.CONTACT_FLAG_MARGIN`, `contact_shift`).

## Gates

- The engine (`tests/constraints/test_tree_contacts.py`): a heavy vector or scalar exchanged equals its contact
  operator for Dirac, Majorana and coloured final states (σ to 10⁻³); |M|² does not depend on the flow's direction;
  a Majorana vector bilinear vanishes.
- The generic route (`tests/parameter_space/test_generic_contacts.py`): a narrow heavy vector (Γ/M = 0.4%) and its
  contact give the same Ωh² to 2 × 10⁻³ (the mediator's s/M² and Γ²/M²), Dirac and Majorana; the same nucleon couplings
  (S, V, A; Majorana A) to 10⁻⁹; the relic refused beyond Λ/3 and flagged from Λ/5; the refusals above; a Weyl field's current.
- Found on the way: a broad mediator is not its contact. At Γ ≈ M the propagator's constant width term halves the
  exchange's rate at q² ≪ M², where a running width would vanish; the generic route's mediators take their tree-level
  width as a constant.

Not changed: the agents' guide (`agents/canonical_intake.py`) does not yet list the contact labels, so a model the
agents write will not use them until it does.

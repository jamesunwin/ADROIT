# DM4: the operator and model library

Built 2026-09-29. Cost: $0. Every number below comes from
`docs/dm4/lz_reduction.py` (output `docs/dm4/lz_reduction.txt` and
`.json`) or from the tests in `tests/library/test_interactions.py`.

## 1. What was built

**Coefficients that depend on the momentum transfer** (`core/dm_state.py`,
`physics/rates.py`). An operator coefficient may now carry a power of q and
a mediator propagator:

    c(q) = value × (q/q_scale)^n × m²/(q² + m²).

The reductions of many relativistic interactions need the first factor
(L6, L9, L10, L12 and L18 contain q²/m_M² terms). Every light mediator needs
the second, and photon exchange needs 1/q² (n = −2). The same operator may
appear more than once with different q-dependences, and the terms add as
amplitudes. The rate evaluates the coefficients isotope by isotope, since q
at a given recoil energy depends on the nucleus. Interactions with constant
coefficients take the same path as before.

**The cards** (`library/interactions/`, 48 cards in three layers). Each
card gives:
- the interaction and its parameters, with priors;
- its map to the layer below, as monomials in m_χ, m_N, the matching scale
  m_M, its parameters and q;
- the nuclear responses reached (layer 1 only);
- its validity conditions and the kinematic modifiers it allows;
- the tiers of constraint that apply;
- what its reduction drops;
- its neighbours;
- its references.

| layer | cards | source |
|---|---|---|
| 1, nonrelativistic operators | O1, O3–O15 (14) | arXiv:1203.3542, 1308.6288 |
| 2, relativistic interactions | L1–L20 (20) | arXiv:1308.6288, Table 1, transcribed from its TeX source |
| 3, mediator models | 14 | derived here in the conventions of arXiv:1308.6288 (below) |

The mediator cards:
- scalar, pseudoscalar and the two mixed spin-0 mediators;
- vector, axial and the two mixed spin-1 mediators, the vector with an
  optional nucleon Pauli coupling;
- pseudo-Dirac (inelastic) dark matter with a vector mediator;
- the Higgs portal and the Z portal;
- magnetic-dipole, anapole and charge-radius dark matter.

**How the mediator cards were derived.** Each is reduced onto L1–L20 by
exact identities, in the conventions of arXiv:1308.6288 (Bjorken–Drell;
q = p' − p = k − k'). This avoids mixing operator normalisations from
different papers. The ingredients:
- **Exchanging a heavy mediator** gives +g_χ g_N/m² (scalar) or −g_χ g_N/m²
  (vector) times the product of the two currents. The propagator
  m²/(q² + m²) is kept, so a light mediator needs no separate card.
- **The Gordon identities** χ̄γ^μχ = [P^μ χ̄χ + χ̄iσ^{μν}q_νχ]/2m_χ and
  N̄γ_μN = [K_μ N̄N − N̄iσ_{μα}q^αN]/2m_N turn vector currents into L5, L6,
  L9 and L10, or into L7, L11, L13 and L14 with an axial partner.
- **The nucleon's vector current with a Pauli coupling g_T** (e κ_N for the
  photon) becomes [g_V K_μ N̄N − (g_V + g_T) N̄iσ_{μα}q^αN]/2m_N.
- **Photon exchange** gives −J_χ·J_N/q².

The generator, `docs/dm4/make_mediator_cards.py`, writes the cards and
records these identities.

**Nucleon inputs.** They are DirectDM's (arXiv:1708.02678; its
`num_input.py`, updated from PDG 2020 and lattice results):
- **Higgs couplings:** f_p = 0.307 and f_n = 0.308, computed from its
  light-quark σ-terms with the heavy-quark term (2/9)(1 − Σ f_Tq).
- **Axial Z charges:** g_A^p = 0.655 and g_A^n = −0.620, from g_A = 1.2756,
  Δu + Δd = 0.440 and Δs = −0.035.
- **Other constants:** s_W² = 0.23121, G_F, the magnetic moments and the
  boson masses.

**The neighbour graph** (`registry.graph()`, a networkx multigraph, 165
edges). Each edge is one of the physical deformations of the build plan:
- integrate out the mediator (a mediator card to its L_j);
- take the nonrelativistic limit (an L_j to its O_i);
- add a mass splitting;
- change the isospin structure;
- make the mediator light;
- specialise the couplings (a vector mediator to the Z portal, say);
- change the Lorentz structure.

The last four also appear as self-loops on the cards that allow them.

**Kinematic modifiers** (`kinematics.py`): elastic, inelastic (δ > 0) and
exothermic (δ < 0). The modifier sets the particle's splitting, and each
card says which modifiers it allows. Pseudo-Dirac dark matter allows only
the two inelastic ones.

**Validity checks** (`checks.py`). A card's conditions are checked for
each use, and every one that fails comes back as a flag in words. The
conditions:
- a contact operator needs a mediator ten times heavier than q_max;
- the interaction is written for spin-1/2 dark matter;
- it vanishes for Majorana dark matter (vector currents, magnetic moment);
- it needs a mass splitting;
- couplings stay below 4π.

**Degeneracy** (`degeneracy.py`). Two interactions are compared by their
spectra on a target, weighted by a search's efficiency and normalised over
its window. For two such shapes the Jeffreys divergence
J = ∫(p − p′) ln(p/p′) dE is twice the expected log-likelihood ratio per
event. So N₂σ = 4/J events are needed to tell the two apart at 2σ. The
classes at N events are the connected sets of pairs with N₂σ > N.
Proportional coefficients are detected exactly (`proportional`).

## 2. Checks

`tests/library/test_interactions.py` (14 tests) and the q-dependence tests
in `tests/physics/test_rates.py` check the following:
- **The transcription of Table 1.** Exactly the five pairs LZ found to
  differ by a constant (L1/L5, L2/L8, L3/L17, L4/L20, L11/L14) come out
  proportional, and no other pair of the 190 does.
- **The responses on the layer-1 cards** are those the rate code gives each
  operator.
- **The matching scale m_M cancels** in every mediator card. This checks the
  powers of m_M in every derivation.
- **Contact limits.** A heavy vector mediator gives c1 = −g_χ g_V/m², an
  axial one c4 = 4 g_χ g_A/m², a scalar one c1 = g_χ g_N/m².
- **Magnetic dipole.** It gives:
  - c1 = −eμ_χ Q/2m_χ;
  - c5 = 2eμ_χ Q m_N/q²;
  - c4 = 2eμ_χ(Q + κ)/m_N;
  - c6 = −2eμ_χ(Q + κ)m_N/q².

  These are the known magnitudes. The charge part reproduces the
  textbook e²μ²[v²/q² − 1/4m_T² − 1/(2 m_T m_χ)], i.e. the
  Z²[1/E_R − (1/v²)(1/2m_T + 1/m_χ)] of the classic cross-section.
- **Anapole.** It gives c8 = 2eQ𝒜 and c9 = 2e(Q + κ)𝒜, with the same sign (corrected 2026-10-10: this line
  said −2e(Q + κ)𝒜, against the card's terms, which were right; Del Nobile's arXiv:1806.01291 map has the
  opposite sign of c9, `docs/portal_library_4.md`).
- **Charge radius.** It gives c1 = ebQ.
- **Higgs and Z portals.** They give their standard contact couplings.
- **The rest:** the graph's edges, the kinematic modifiers, the flags and
  the divergence.
- **LZ's isospin statement on xenon** (last test; section 3).

## 3. The gate: LZ's reduction of 616 models to 293

The gate is fixed in the build plan: "The library reproduces LZ's reduction
of 616 models to 293."

LZ's model space (arXiv:2609.02823, supplement) has 616 models:
- L1–L20, isoscalar and isovector, at 13 masses from 10 to 4000 GeV;
- inelastic O1 and O4, isoscalar and isovector, at 400, 1000 and 4000 GeV
  with eight splittings from 0 to 350 keV.

LZ states three degeneracies and a result of 293. The library builds all
616 from its cards and computes their xenon spectra with LZ's efficiency
(digitised Fig. S2). Four models have no events in the window (400 GeV,
δ = 350 keV), which LZ also marks as unphysical.

**1. Pairs that differ by a constant: reproduced exactly.** The five pairs
LZ names are proportional at every mass and isospin, and no other pair is.

**2. Isospin: reproduced exactly, with a clean gap.** For each Lagrangian
we took the smallest N₂σ between its isoscalar and isovector forms, over
masses from 30 GeV:

| LZ says indistinguishable | N₂σ |
|---|---|
| L15, L2/L8, L4/L20 | 7,300–11,100 |
| L7, L19, L11/L14, L10 | 296–503 |
| inelastic O4 | 4,160 |

| LZ says distinguishable | N₂σ |
|---|---|
| L1/L5 | 21 |
| L3/L17, L16, L13, L9, L12, L6, L18 | 1.7–6.6 |
| inelastic O1 | 0.95 |

Any threshold between 21 and 296 events reproduces LZ's list exactly. The
physics is clear: on xenon the operators with only spin responses (O4,
O6, O7, O9, O10, O14) see almost only the odd neutron, so the isovector
sign changes the normalisation and not the shape.

**3. Heavy masses: a blanket choice, not a threshold.** Between 400, 1000
and 4000 GeV the spectra need N₂σ ≥ 175 events to separate (median 327).
But between 200 and 400 GeV some Lagrangians are as degenerate (N₂σ up to
1,870; median 84). No single threshold reproduces LZ's mass rule together
with its unmerged low masses.

**4. Not stated by LZ.** The twelve inelastic models at δ = 0 are
identical to elastic ones. O1 at δ = 0 is L1 and O4 at δ = 0 is L15, at the
same mass and isospin (N₂σ > 10¹⁴).

**The count does not follow from the stated rules.** Applied literally
they leave 23 Lagrangian spectra per mass × 11 masses (10 below 400 GeV,
plus 1000 GeV) + 72 inelastic = **325** (322 without the four unphysical
points), not 293.

Only two readings give exactly 293. Both need 10 Lagrangian masses rather
than 11, and 63 inelastic models:
- the three operator-isospin combinations (O1s, O1v, O4) × 3 masses × 7
  splittings without δ = 100 keV, which the HEPData record omits; or
- with δ = 0 dropped as a duplicate of the elastic models.

Neither follows from the text. The numerical classes cannot give 293
either, whatever the threshold. Single linkage merges neighbouring light
masses: 88 classes at N = 100, 156 at 300, 243 at 1000.

**Result.** The library reproduces the substance of LZ's reduction:
- every degeneracy LZ states, exactly;
- one exact degeneracy LZ does not state.

The number 293 cannot be reproduced from LZ's description, whose own rules
give 325.

**Gate accepted by the owner (2026-09-30)** on the three stated
degeneracies. The discrepancy is recorded: LZ's stated rules give 325
models (322 physical), against the 293 it reports (writeup notes, DM4
item 1). Which models LZ's look-elsewhere computation actually used remains
a question for the collaboration.

**Addendum (DM5, 2026-09-30): with LZ's own nuclear responses.** DM5 found
that LZ uses revised xenon density matrices (`NuclearModel.haxton_2022`).
The analysis rerun with them (`docs/dm4/lz_reduction_haxton_2022.txt`)
confirms every conclusion above, and sharpens the isospin gap:
- the listed interactions need at least 6,730 events to separate;
- the others need at most 18;
- the heavy-mass numbers barely move (400 GeV and up: at least 169 events).

## 4. Found on the way, for DM6

DM6 must reproduce LZ's 616 local significances to within 0.3σ. Exactly
degenerate models must have equal significances, which tests LZ's tables:
- **Proportional pairs disagree in the paper.** Five pairs differ by more
  than 0.15σ in its Table S7:
  - L1v/L5v at 400 GeV, 0.3 against 0.7;
  - L2v/L8v at 200 GeV, 2.5 against 2.9;
  - L3v/L17v at 100 GeV, 0.2 against 0.0;
  - L4/L20 at 4000 GeV, 3.0–3.1 against 3.3.

  In HEPData two of these pairs differ (the L2v/L8v and L3v/L17v cases).
- **Duplicates disagree too.** Table S8 gives O1v at 400 GeV, δ = 0 as 0.8,
  while the identical L1v at 400 GeV is 0.3 in both the paper and HEPData.
  HEPData's O1v entry is 0.3.
- **The paper and HEPData disagree at 14 entries of Table S7.**
  - Five entries are missing from HEPData: L4s at 30 GeV, L4v at 17, L14s
    at 17 and 200, and L14v at 17.
  - Nine differ by 0.1–0.6σ. The largest is L9v at 100 GeV: 2.7 in the
    paper, 2.1 in HEPData.

So the reference values themselves scatter by up to 0.4σ between
identical models. DM6's tolerance of 0.3σ should be read against that.

## 4a. Corrected in DM8 (2026-10-01): the mediator cards that combine Lagrangians

DM8's explicit reduction (`library/interactions/nr_projection.py`: the
amplitude computed with explicit spinors, in Anand et al.'s conventions with
q = p′ − p, projected onto the O_i) showed two errors in eight mediator cards.

- **A sign.** The transcriptions of Table 1 for the six operators with one
  explicit factor q^α (L6, L9, L11, L12, L14, L18) carry the opposite overall
  sign to the explicit reduction; every other Lagrangian agrees. On its own a
  card's overall sign cancels in every rate, so the Lagrangian cards and
  every DM4–DM6 result built on them stand. But the generator combined those
  six with other Lagrangians through Gordon identities written for
  q = p′ − p. So in the vector, axial–vector, vector–axial, pseudo-Dirac
  vector, Z-portal, magnetic-dipole, anapole and charge-radius cards, the
  terms odd in q (O3, O5, O9) had the wrong sign relative to the even ones.

  Where the two interfere at leading order (through the spin–orbit response
  ΔΣ′), rates were wrong at 100 GeV:

  | card | ²³Na | ¹⁹F | Xe | Ge |
  |---|---|---|---|---|
  | anapole | ×11 | +40% | −9% | −5% |
  | magnetic dipole | ×5 | +37% | −4% | −2% |
  | axial–vector | ×2.3 | +8% | +0.4% | +11% |

  For the other five cards the effect was below 0.5%.
- **The spin–orbit term of the nucleon density.** Table 1 reduces L5 to O1
  alone. The scalar density also carries a spin–orbit term of the same order
  as O3, so a vector current on a nucleon gives c3 = g_T + g_V/2 (the
  Thomas-precession combination), not g_T + g_V. The vector-type cards now
  carry a direct O3 correction; the effect on rates is below 0.2%.

The generator (`docs/dm4/make_mediator_cards.py`) applies the sign rule in
one place (`term`), and the cards were regenerated. Every one of the eight
now agrees with the explicit reduction, operator by operator, to the recoil
corrections of order μ_N/m_χ (`tests/library/test_nr_projection.py`). It also
agrees with DirectDM and with LZ's own L9.

**Earlier results are unaffected beyond 0.5%.** DM5 and DM6 used the
Lagrangian and operator cards, whose overall signs cancel. DM7 used the
axial card (one Lagrangian), the vector card at q → 0 for its cross-sections,
and the vector card in capture, where the spin-independent part dominates and
the odd-q terms change rates by under 0.5%.

**Majorana dark matter (stated in DM8, 2026-10-01).** The couplings of the
mediator and Lagrangian cards are Feynman-rule couplings in the Dirac
normalisation. A Majorana field with the Lagrangian g χ̄Γχ has twice that
vertex, so it enters a card as 2g, or as g if its Lagrangian is written
(g/2) χ̄Γχ. DM8's gate found this for the anapole (`dm8_lagrangians.md`,
section 10).

## 5. Not done in DM4

- **A quark-level operator basis through DirectDM** (the build plan's
  layer 2 also names it). DirectDM is fetched, and its nucleon inputs are
  used here; its quark-level matching, with running, is left for DM8,
  where arbitrary Lagrangians need it.
- **The electric dipole moment.** It needs χ̄σ^{μν}γ⁵χ, which is not among
  the four-vector structures of Table 1; its reduction must be derived
  with care for the factors of i.
- **Spin-0 and spin-1 dark matter.** The Lagrangians are for spin-1/2; the
  operators O17–O20 are in phase 2.
- **A threshold for the degeneracy classes of DM6.** Section 3 shows what
  each choice does. The isospin gap (21–296 events) is one natural anchor.
  It should be fixed in advance, with DM6's injection gate at 20 events in
  mind.

## 6. Reproducing DM4

```bash
uv run python docs/dm4/make_mediator_cards.py     # rewrites cards/mediators.yaml
uv run python docs/dm4/lz_reduction.py            # the gate analysis, seconds
uv run pytest tests/library/test_interactions.py tests/physics/test_rates.py
```

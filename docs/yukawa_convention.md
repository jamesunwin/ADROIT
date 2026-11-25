# The Yukawa convention (the owner's decision #2, 2026-10-20)

The owner's decision: one declared Yukawa convention per equivalent model; pole masses where the reference card uses
them; Yukawa inputs kept apart from kinematic masses; supplied couplings preserved; light mediators tested. The
owner's answer (2026-10-20, after the auditor's review): "sm" for a generic model that declares none; the DMsimp convention
explicit in the library's simplified-mediator entries; four requirements, below.

## What a model declares

`ModelSpec.yukawa` (`model_building.yukawa`; schema era 5, default "sm", so every stored model reads as before) says
what m_q, m_l and m_f mean in the model's stated couplings (a coupling written g m_q/v), in the interaction basis,
before any mixing:

| convention | the masses in stated couplings (GeV) |
|---|---|
| `sm` (the default) | b and c MS-bar (one loop) at m_h, 3.007 and 0.776; the others at G2's table (u 0.00216, d 0.00467, s 0.0934, t 172.5, e, μ 0.10566, τ 1.77686) |
| `DMsimp_s_spin0_MD` | its UFO's YUKAWA block: u 0.00255, d 0.00504, s 0.101, c 1.27, b 4.7, t 172, e 0.000511, μ 0.10566, τ 1.777 (the directory `DMsimp_s_spin0_MD` in the tools folder, version 1.1 of 2016.06.02, its `parameters.py` defaults, no restriction card applied; the auditor's inspection of 2026-10-20, `Y`) |

A card is named exactly: "DMsimp" alone is ambiguous (the auditor's Y, 2026-10-20). The other local cards differ: the
default `DMsimp_s_spin0` has no b or c Yukawa (and MB = MC = 0); the two `_ybMSbar` variants have ymb = 4.7 and no c
or τ Yukawa (MB 4.7 in the four-flavour one, 0 in the five); `Pseudoscalar_2HDM`'s raw defaults equal the `_MD` card's,
but its restriction cards override them (`restrict_default.dat`: c Yukawa and MC 0; `restrict_WMET.dat`: MB = MC = 0;
`restrict_bbMET_5FS.dat`: both). The kinematic top, 172.5 GeV in both routes, is an explicit override of the cards'
MT = 172 (below).

"sm" is G2's former and only rule (the audit's G1-12: a 2HDM's stated m_q/v · tan β is then tan β times h's own
Yukawa). `yukawa.describe` gives the convention resolved, with its numbers; the Track 1 report's first section says
it.

## The four requirements

1. **The library's convention travels.** The library's Yukawa-like scalar mediator and ALP declare
   `DMsimp_s_spin0_MD`, on their class (`ScalarClass.yukawa`) and on their spec (`Entry.yukawa`), so the generic
   route's model from them keeps it; `classify` passes a spec's convention to the typed class, so a user's spec that
   declares none is "sm" on both routes.
2. **Resolved and shown.** As above.
3. **Matching, convention-aware.**
   - The 2HDM+a's type-II check takes each new scalar's couplings as multiples of the Higgs boson's taken in the
     declared inputs (h's own are "sm"; `generic_2hdma._yukawa_ratios`); the alignment is checked apart. Couplings
     that follow another convention's inputs than the declared one are named a convention mismatch, not a wrong
     Yukawa type, and are not corrected.
   - Direct detection divides each scalar's quark couplings by the masses they carry (`yukawa.carried_masses`): the
     Higgs boson's for the doublet's state, the declared convention's for a state without a doublet component, so a
     Yukawa-like scalar keeps its g/v gluon coupling under either; a state mixing the two under a card is named and
     its direct detection pending.
   - The B → K a and the CMS monojet readings take the same carried masses; the monojet's signal strength scales the
     top coupling in the DMsimp card's units, as CMS's benchmark has it.
   - Production: the gluon-fusion tables scale each loop by its coupling in the tables' own masses (t 172.5, b 4.7),
     on both routes now (the library's scalar had multiplied the combined table by g_q², exact only when its inputs were
     the tables'); a card model is not exactly Higgs-like in "sm" inputs, so it is produced through the loops, not as
     the Working Group's heavy Higgs.
4. **Apart from kinematics and supplied numbers.** A convention changes only the stated m_q, m_l, m_f: the kinematic
   masses (thresholds, phase space: `kinematics.KINEMATIC_MASSES`, below), an explicitly numeric coupling and the
   Higgs boson's own Yukawas are the same under either.

## Gates (`tests/parameter_space/test_yukawa_convention.py`)

- The same declared convention gives the same width, b b̄ and c c̄ branching fractions and lifetime on both routes, for
  "sm" and the card, at 5 GeV (a pseudoscalar between 2m_c and 2m_b), 8, 80 and 150 GeV.
- Different conventions need not agree: the b b̄ and c c̄ widths' ratios are exactly (3.007/4.7)² = 0.409 and
  (0.776/1.27)² = 0.373 on one route.
- Requirement 4; the library's entries carry the card and `classify` passes it on; "pole" refused; a stored model
  without the field reads as "sm"; a Higgs-mixed singlet under the card leaves its direct detection pending.
- The library-against-generic gates (`test_generic_portrait.py`): the scalar's and ALP's widths and production now agree
  without the rescaling they had needed (their b and c widths had differed by 2.44).

## The kinematic masses (the owner's answer, 2026-10-20)

"For these simplified-model comparisons, use m_b^kin = 4.7 GeV in both routes, explicitly described as the DMsimp
card's mass input." The kinematic masses (external legs, thresholds, phase space, propagators) are one table,
`kinematics.KINEMATIC_MASSES`, read by both routes (G2's `feynman.SM_FERMIONS`, the library's `spin1.FERMIONS`, the
model checks' `HEAVY_QUARKS`), and G2's UFO exports write the same values in their MASS block:

| fermion | kinematic mass (GeV) | what it is |
|---|---|---|
| b | 4.7 | the DMsimp card's MB (its MASS block), the shared benchmark kinematics |
| c | 1.27 | the DMsimp card's MC; numerically the MS-bar m̄_c(m̄_c), not a pole mass (that is about 1.67) |
| t | 172.5 | in both routes, an explicit override of the card's MT = 172 (the owner's approval) |
| u, d, s | 0.00255, 0.00504, 0.101 | the DMsimp card's MU, MD, MS (the owner's approval; G2 had the PDG MS-bar masses at 2 GeV, the library none) |
| e, μ, τ | 0.000511, 0.10566, 1.77686 | pole masses |

Kept apart from it, each under its own name:
- **The Yukawa inputs** (above): "sm" is still the default, its b and c run (one loop) from the MS-bar
  m̄_b(m̄_b) = 4.18 and m̄_c(m̄_c) = 1.27 GeV to m_h (`constraints.higgs`, `derivation.STANDARD_MODEL`); 4.18 is that
  MS-bar input, not a pole mass, and no longer any kinematic mass. A card convention takes the card's YUKAWA block.
- **The Standard Model Higgs widths' own prescription** (`constraints.higgs`): thresholds and loop masses at the pole
  masses 4.78 and 1.67 GeV with the running Yukawas, kept for h as that prescription's. The benchmarks' kinematics are
  not changed to 4.78.

### What separates (`test_yukawa_convention.py::test_the_yukawa_inputs_and_the_kinematic_b_mass_change_the_width_apart`)

A quark-only Yukawa-like mediator, g_q = 1, its decay into the dark matter closed (m_χ = 100 GeV); ratios of G2's
widths with one input changed at a time (the study: scratch `yukawa_study/kinematic_b.py`):

| m_med (GeV) | CP | b b̄: Yukawa only ("sm"/card) | b b̄: kinematics only (m_b^kin 4.18/4.7) | b b̄: both | Γ: Yukawa only | Γ: kinematics only | Γ: both |
|---|---|---|---|---|---|---|---|
| 12 | even | 0.409 | 1.537 (β³) | 0.629 | 0.402 | 1.418 | 0.573 |
| 20 | even | 0.409 | 1.090 | 0.446 | 0.406 | 1.082 | 0.440 |
| 40 | even | 0.409 | 1.0184 | 0.417 | 0.407 | 1.017 | 0.414 |
| 80 | even | 0.409 | 1.0044 | 0.411 | 0.407 | 1.004 | 0.409 |
| 12 | odd | 0.409 | 1.154 (β) | 0.472 | 0.406 | 1.138 | 0.463 |
| 40 | odd | 0.409 | 1.0061 | 0.412 | 0.407 | 1.006 | 0.409 |

The Yukawa ratio is (3.007/4.7)² = 0.409 at every mass (c c̄: (0.776/1.27)² = 0.373). The kinematic ratio is β³ for a
CP-even scalar and β for a pseudoscalar, so the CP-even figures (1.537 at 12 GeV, 1.0184 at 40) are not the
pseudoscalar's (1.154, 1.006). "Both" is the former cross-route comparison of the study of 2026-10-20 (its 0.574 at
12 GeV): 0.409 from the convention times 1.418 from the kinematic b, the latter now gone. Below 2 × 4.7 = 9.4 GeV b b̄ is
closed on both routes (a CP-even scalar at 8 GeV, a pseudoscalar at 5 GeV: c c̄ alone, Yukawa ratio 0.373).

## What it changes

- **The library** (the card exactly, against the table it had used: t 172 for 172.5, τ 1.777, u, d, s 0.00255,
  0.00504, 0.101 for 0): at the R3 crossings of the ALP and the scalar mediator (47), Ωh² moves by +0.5% to +0.6%
  above the top threshold (the top Yukawa) and σ(gg → S) by −0.2% to −0.6%; two ALP crossings at m_χ ≈ 1 GeV move by
  −20% and −33%, its s Yukawa now opening χχ → s s̄ at the quark level below 2 GeV (both excluded by other searches).
  No viable crossing is among them, so no status changes. (The library's ALP then had no hadronic-window refusal;
  the owner's answer of the same day gives it one: `docs/hadronic_window.md`.)
- **The kinematic b mass** (4.18 → the card's 4.7 GeV in G2; the library already had 4.7): of the development half's 12
  models, one Ωh² moves by more than 0.01%, `vector_higgs_portal_athron` at the Higgs pole, +0.10% (G2's own h → b b̄
  phase space). The R3 crossings are all the library's, whose kinematics were already these: none moves (the model
  checks' axial-unitarity bound, which now reads m_b = 4.7, is far from every axial crossing).
- **The light quarks** (the owner's approval: u, d, s at the card's MU, MD, MS in both routes; the library's had been
  massless, G2's the PDG MS-bar masses at 2 GeV): at the 256 R3 crossings nine Ωh² move by more than 0.01%, all at
  m_χ ≤ 9 GeV through DMWG's axial mediator and the Z portal, whose axial s-wave annihilation ∝ m_q² the massless
  quarks had set to zero: dmwg_A1#0 −5.0% (m_χ = 1 GeV, now in the hadronic window and not computed), dmwg_A1#1
  −0.26%, dmwg_A1#2 −0.19%, the rest within 0.1%. No status changes: dmwg_A1#0 was pending, and each of the others
  is excluded by searches that read neither Ωh² nor these masses (direct detection, CMS, SModelS, the invisible Z
  width).
- **The generic route**: unchanged ("sm" is its former rule). No development-half zoo model is routed to the
  library's scalar class.
- **A user's spec routed to the library's scalar class** takes "sm" now, as it declares none (its b and c Yukawas
  3.007 and 0.776 for 4.7 and 1.27).

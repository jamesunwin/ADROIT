# The library's searches in the generic route (P1–P5 of `generic_route_next.md`)

Part 2 of the plan: the searches the library decides by a model's family (`searches.EVALUATORS`,
`resonances.EVALUATORS`), brought to any model the generic route builds, each milestone with its gate declared before
it ran. The held-out half of the zoo is not used.

## P1 — the mediator's portrait (2026-10-20)

`parameter_space/portals/generic_portrait.py`: for every new Z₂-even, neutral, colourless boson of a generic model at
a point, what the library's searches read from a mediator: its mass and total width; its partial widths into each
final pair (from G2's own two-body widths), with the invisible part (pairs of dark matter and neutrinos) and the
unresolved part (pairs with any other new state, whose own decays decide whether it is seen); its coupling to each
Standard Model fermion and to the dark matter as the Lagrangian writes it, (g_V, g_A) for a vector and (g_S, g_P) for a
scalar; its CP character; and how far its couplings are the photon's, the Z's or the h's (a least-squares decomposition
over every Standard Model fermion, an absent coupling as zero, onto the unmixed Standard Model's photon, Z and h through
the same generator: a dark photon's kinetic mixing ε, a singlet's mixing angle sin θ, an ALP's Yukawa-like factor, with
the part they do not explain). Both as repaired after the tactical audit (2026-10-20, below).

**Gate (declared): the library families' own mediators reproduced, couplings to 10⁻⁶ and widths to 1%.** Each
library entry's spec at its benchmark, its couplings set from the benchmark's slots, through `GenericModel.for_spec`
(`tests/parameter_space/test_generic_portrait.py`):

| entry | total width, generic / library | couplings |
|---|---|---|
| `dmwg_V1` (vector, g_q = 0.25, g_DM = 1, 1 TeV) | 1.000000 | g_V = g_q for every quark, g_DM: exact |
| `dmwg_A1` (axial) | 1.000003 | g_A = g_q, g_DM: exact |
| `scalar_mediator` (Yukawa-like, 500 GeV) | 0.9995 | the quarks' κ = −1 (g_S = +m_f/v; G2's h couples as −m_f/v); no lepton coupling, so the residual over every fermion is the leptons' share of the h's, 0.0103 |
| `alp_portal` (pseudoscalar, 100 GeV) | 1.000 after the convention below | κ₅ = −1, residual 10⁻¹⁶ |
| `b_minus_l` (2 TeV) | 1.000000 | quarks g/3, charged leptons −g, left-handed ν (g_V, g_A) = (−g/2, g/2) |
| `lmu_minus_ltau` (1.5 GeV) | 0.997 | μ, ν_μ +g; τ, ν_τ −g |

Every partial width the library computes agrees to 1%, and the development-half zoo's Higgs-mixed singlet (Das et al.,
sin θ = 10⁻³) and dark photon (Feng et al.) are read as such (κ = 10⁻³ to 10⁻⁶; a pure photon-like coupling, no Z
part, its decay to the dark scalar pair invisible).

**What the gate found.**
- **Three library entries' specs lacked couplings their own Lagrangians state:** B − L and L_μ − L_τ had no neutrino
  terms (the generic B − L's width lacked its three νν̄ channels, 0.80 of 3.45 GeV), and the ALP portal no lepton term
  (Σ_f in its Lagrangian; the library class applies g_ℓ). The terms are added; the typed classes (`ChargedZPrime`,
  `ScalarClass`) always had them, so only the generic route's view of these entries (its fallback outside a class's
  domain) changes.
- **A declared mass convention, not tuned** (the owner's decision #2, `docs/yukawa_convention.md`): a model declares
  its Yukawa inputs ("sm" by default: b and c run to m_h; the library's Yukawa-like mediators declare the DMsimp
  card's, b 4.7 and c 1.27), and both routes take the same kinematic masses (b the card's 4.7 GeV). The gate compares
  equivalent models under the same declared convention, without a rescaling factor (it had been (4.7/3.007)² = 2.44).
- The dark photon's ε read from its couplings is 0.982 of the spec's kinetic-mixing parameter κ (Feng et al.'s
  benchmark). The cause is not yet established (a normalisation of the photon coupling G2 compares against is the
  likely one); P4 (light vectors), whose records take ε, settles it before any comparison uses it.

The dark photon and singlet-mixing library entries are written as general Lagrangians whose couplings are not the
library's slots (ε through the hypercharge mixing, sin θ through μ_Hs); they are compared in P4 and P2 respectively.

## P2 — production from the portrait (2026-10-20)

`parameter_space/portals/generic_production.py`: the portrait's mediator produced singly at 13 TeV through the
library's own MadGraph tables, decomposed by flavour so that any pattern of couplings is covered: a vector through
the per-flavour q q̄ → Z′ tables, σ = Σ_q (g_V,q² + g_A,q²) σ_q over u, d, s, c, b (leading order, as the library's Z′); a
scalar through the gluon-fusion tables at unit Yukawa-like coupling to the top, the bottom and both, for a scalar and
a pseudoscalar coupling, σ = κ_t² σ_t + κ_b² σ_b + κ_t κ_b (σ_tb − σ_t − σ_b), times the Working Group's K-factor; a scalar
whose couplings are exactly the h's times κ as a Standard-Model-like heavy Higgs, κ² times the NNLO+NNLL σ (as the
library's h₂). Outside a table's masses nothing is returned, with the reason.

**Gate (declared): the library's σ to 1%.** `dmwg_V1` and `dmwg_A1` 0.99986 (the per-flavour tables' sum against the
universal table), `b_minus_l` 0.99992 (against the B − L table), `scalar_mediator` 0.9995 (as a heavy Higgs; through the
tables with the library's b convention, within 1% too), `alp_portal` within 1% with the b coupling at the library's pole
mass; as G2 takes it (m_b run to m_h, P1's declared convention) the ALP's σ is 4.1% higher at 100 GeV, through the b
loop's interference with the top's. A mediator coupled to no quark (L_μ − L_τ) is not produced.

## P3 — the resonance searches through the generic route (2026-10-20)

`searches.generic_mediators` turns each new neutral boson of a generic model into what the library's resonance
searches read from a mediator: its production (P2), its partial widths keyed as the library keys them, and its own
mass in place of the plane's m_med. The searches and their records are the library's, unchanged:
- **dijets** (CMS's narrow limit from 0.6 TeV, ATLAS's Gaussian limits for broad vectors from 1.5 TeV) on every new
  neutral vector;
- **tt̄** (CMS, 400–750 GeV) on every new scalar coupling to the top, by its coupling in units of the Standard Model's
  Yukawa (in the gluon-fusion tables' masses); a scalar coupling to the top as both a scalar and a pseudoscalar is
  undecided (CMS's signal is one or the other);
- **dileptons** (ATLAS, 250 GeV–4.5 TeV, Γ/m ≤ 10%) on every new neutral vector with an e⁺e⁻ channel: σ·BR(ee) with
  σ from MadGraph's per-flavour tables brought to the record's own leading order (PDF4LHC21) by the ratio of their B − L
  cross sections, so that the record's fiducial/LO correction applies; LEP's contact bound, calibrated on B − L's
  charges, is not applied to another pattern;
- **ZZ and WW** (ATLAS) on every new scalar produced in gluon fusion, with the library's width conditions; beyond both
  searches' masses nothing applies.
Several mediators give the strongest outcome (an exclusion if any excludes, else undecided if any is).

**Gate (declared): the library's outcomes on its families through the generic route at test-plane points.**
`tests/parameter_space/test_generic_portrait.py`: the DMWG vector and axial Z′'s dijet outcomes at seven points
(0.7–3.5 TeV, narrow, broad and too broad for ATLAS's acceptance), the scalar mediator's tt̄ outcomes at four (decided
and between CMS's widths), and B − L's ATLAS dilepton outcomes at five (excluded and allowed, 1–4 TeV): the same decision
everywhere, ratios within 1% (most to 10⁻⁴).

These evaluators now apply to every generic-route scan: a generic model's verdict can gain a resonance exclusion or a
pending reason it did not have. The branch's verdict-change study records which documented results move.

## P4 — light vectors (2026-10-20)

A generic model's new vector is recognised by the pattern of its couplings (the portrait's decomposition), and then
goes through the library's own searches with numbers from its portrait:
- **a dark photon** (couplings photon-like: residual below 10⁻³, no Z part): DarkCast's visible and invisible limits
  and the BBN bound (thermalised or by freeze-in), with ε in DarkCast's convention, relative to the electron's charge
  at the Thomson limit (G2's photon couples at the electroweak scale, 0.30842 against 0.30282: this was P1's 0.982);
- **an L_μ − L_τ vector** (μ, ν_μ +g′, τ, ν_τ −g′, nothing else): muon g − 2, BaBar and Belle II, CCFR's trident limit,
  CMS's 4μ (pending) and the BBN bound;
- **a B − L vector** (quarks g/3, charged leptons and neutrinos −g): LEP's contact bound, beside ATLAS's dilepton
  limit (P3), and the BBN bound.
The library paths are refactored to take these numbers and are unchanged.

**Gate (declared): the library's dark photon, charged Z′ and L_μ − L_τ outcomes.** DarkCast on the library's Dirac
dark photon (α_D = 0.5, m_A′ = 3 m_χ) at seven points from 20 MeV to 300 GeV (pending above 200 GeV in both); the
L_μ − L_τ searches at six points (30 MeV to 30 GeV); BBN on the light dark photon, B − L and L_μ − L_τ vectors at six
(thermalised, freeze-in, excluded and allowed); B − L's LEP and ATLAS dilepton outcomes at five: the same decisions,
ratios within 2%.

**What it found: couplings below G2's resolution.** G2 drops a vertex below 10⁻¹⁰ (for couplings below 1, to clear
rotation noise), so a B − L vector at g = 10⁻¹² had no couplings at all, and at 2 × 10⁻¹⁰ only its lepton couplings
survived and it read as a dark photon. The generic route now refuses a model with a non-zero coupling below 10⁻¹⁰
(``generic._feeble``, its domain: "a coupling below the generic route's resolution") and its portrait reads no
mediator, so nothing is decided from a partly dropped pattern. Feebly coupled vectors (the BBN bounds' lowest
couplings, freeze-in) are therefore outside the generic route for now; the typed classes compute them.

**The rest of P4 (2026-10-20).**
- **B → K + invisible** for a generic light CP-odd scalar (below m_B − m_K) whose quark couplings are Yukawa-like
  (each quark's pseudoscalar coupling over the h's is one factor g_q, to 10⁻⁶; leptons may differ, as the library's
  g_ℓ): BaBar's limit through the record's top-loop b → s a with g_Y = g_q/√2, and the invisible fraction from the
  portrait, as the library's ALP; several such scalars, the strongest outcome. A light CP-odd scalar coupled to quarks
  otherwise (or a CP-even or mixed one) is undecided with the reason. Gate: the library's ALP at seven points below
  the c c̄ threshold (four excluded, one allowed, one decaying visibly, one above BaBar's signal region): the same
  native and 95% outcomes, ratios to 1%.
- **Muon g − 2 for any new neutral vector coupled to the muon**, its vector and axial couplings each through its
  one-loop function (`muon_g2_vector`, and the new `muon_g2_axial`, Jegerlehner & Nyffeler eq. (263): −5g_A²m_μ²/
  (12π²M²) for a heavy vector, growing as 1/M² for a light one), summed over the model's vectors; a vector with
  L_μ − L_τ's charges keeps `lmu_ltau`'s g − 2. CCFR's trident limit stays with the L_μ − L_τ charges it is
  calibrated on. Gate: a B − L vector's g − 2 is the vector formula at its muon charge, at three masses.
  The library's own dark photon and B − L classes state no g − 2: through the generic route those families now get
  one, a stricter judgement than the library's where it is the strongest bound (a verdict difference between the two
  routes, recorded here). (Replaced by one calculation for both routes, the owner's decision #11: see "Muon g − 2"
  below.)

## P5 — the model-specific combinations by a structural match (2026-10-20)

**What it found first: the general Lagrangian under-counted the two-doublet quartics.** DM12's generator wrote one
term per field content and left its gauge indices unstated, though its own count said how many independent couplings
the structure has. H H† H₂ H₂† has two, λ₃|H|²|H₂|² and λ₄|H†H₂|²: the second was dropped, and G1 refused λ₅'s
H H H₂* H₂* (no unique pairing), so the library's inert doublet and 2HDM+a could not be built by the generic route from
their fields. Each such term is now written once per independent contraction with its indices stated
(``indices.stated_contractions``: the products of δ and metric pairings, symmetrised over identical fields, kept while
independent, until there are as many as the term's invariants; a term that needs σ or ε is still left to be stated).
A second doublet now has λ₂, λ₃, λ₄ and λ₅. The zoo's entries state their terms and are unaffected.

**The inert doublet: LEP's limit (Lundström et al.).** It applies to a generic model whose new fields are one Z₂-odd
colourless scalar doublet with |Y| = ½ and nothing else: its gauge couplings, and so LEP's pair production and the
A₀ → H₀Z*, H± → H₀W* decays the limit assumes, are fixed by its quantum numbers whatever its potential. The masses are
the model's own at the point (H₀ the lighter neutral state). A dark doublet that comes with other new fields (or a
new gauge charge) is undecided with that reason; a model without one has no such outcome.

**Gate (declared): the library's inert doublet through the generic route.** Its fields only, DM12's general potential
with c₃ = −λ₃, c₄ = −λ₄, c₅ = −λ₅/2 and μ₂ from the library's (M_H₀, M_A₀, M_H±, λ₃₄₅), at six points: three LEP
excludes (the (H₀, A₀) region, a light H±, Z → H₀A₀) and three it allows (a small split, A₀ above 100 GeV, HP10). The
same masses to 10⁻⁵ and the same decisions; a doublet with a dark singlet is undecided, a Z′ model not judged.


**The 2HDM+a: ATLAS's combination, mono-h and mono-Z (`portals/generic_2hdma.py`).** The library's UFO
(Pseudoscalar_2HDM, Bauer, Haisch & Kahlhoefer) writes its potential in the Higgs basis, Φ₁ with the vacuum and Φ₂
without, with l₁…l₇, the portal P(i μ_P Φ₁†Φ₂ + h.c.) and the P² couplings l_P1, l_P2, l_P; its `parameters.py` maps
the Working Group's parameters (the masses, sin θ, tan β, sin(β − α), λ₃, λ_P1, λ_P2, y_χ) onto them. A generic model
whose new fields are a second scalar doublet (|Y| = ½) and a real singlet, both Z₂-even, and a Dirac fermion as the dark
matter is read at the point from its own rules: the five scalar masses; sin θ and y_χ from a's and A's couplings to χ;
tan β from H's, A's and a's Yukawa couplings relative to the Standard Model h's (the type-II pattern checked flavour by
flavour, with the θ it implies against the χ couplings', and the relative sign of a's and A's couplings); alignment
from h's couplings; λ₃, λ_P1 and λ_P2 from the trilinears h H⁺H⁻, h a a and H a a (the UFO's own vertex formulas,
with H H⁺H⁻ checked against the l₇ they imply). The library's UFO at those parameters must then give every scalar
trilinear and quartic coupling, and the gauge couplings between different states (VSS, VVS, each vector leg scaled by
the two codes' coupling of it to a lepton: their electroweak schemes differ, the UFO's W at 79.82 GeV against G1's
80.37 GeV), within 1%: every vertex either model has, a missing one as zero, and with its sign where no rephasing of
its fields can change it (H⁺H⁺H⁻H⁻), the others in magnitude, since the two codes' field phases may differ (as
repaired after the tactical audit, below). Then the library's three evaluators
run on that UFO model; otherwise each is undecided with what differs. The heavy states' Yukawa couplings are compared
as ratios to the same code's h coupling, since the two codes' Yukawa masses differ (G2 runs m_b and m_c to m_h, the UFO
keeps 4.7 and 1.27 GeV).

The generic route states the model only at alignment, where its Φ₁ is the Standard Model's H, and with a tachyonic P
mass where l_P1 v² exceeds the UFO's m_P² (ATLAS's scenario 1a at m_a ≲ 250 GeV): `generic_2hdma.spec` writes it.

**Gate (declared): the library's 2HDM+a through the generic route.** The model as a generic spec in the Higgs basis at
ten points (ATLAS's scenario 1a across its plane, including the allowed island at m_a = 500 GeV; tan β = 2 with
sin θ = 0.5; the library's benchmark, outside scenario 1a; and unequal λ's with split heavy masses) is read back to its
parameters (to 10⁻¹³), and the three searches give the library's own outcomes there: the same decisions and reasons.
Type-I Yukawas, or a different l₇, l_P2 or l₂, are undecided with what differs; a model without the fields is not
judged.

**Its endpoints (the audits of 2026-10-20).** At sin θ = 0 the pure singlet has no Standard Model coupling, so it takes
its CP from its coupling to the dark matter and is not held to the type-II pattern (B20-10); at sin θ = 1 the states
are relabelled by their doublet content. At an exact degeneracy of the heavy scalars (H = A = H±, with or without a)
a quartic that is analytically zero, l₄ at alignment, had come out −1.9 × 10⁻¹⁵ and been refused by the route's
resolution as a feeble coupling (RB20-05). The Higgs-basis parameters are now written so that nothing subtracts nearly
equal masses (RC20-03: a rule that had set every sum below 10⁻¹² of its terms to zero also erased a 0.5 MeV singlet's
m_P²): m_A² = m_H3² cos²θ + m_H4² sin²θ and m_P² = m_H3² sin²θ + m_H4² cos²θ, l₄ and l₅ from mass differences (exactly
zero at an exact degeneracy), the rest exactly rounded and never set to zero. A coupling the user supplies below the
resolution is still refused, the match giving the route's own reason. At sin θ = 10⁻⁶ the
singlet's light-quark couplings fall below G2's resolution: refused with that reason (pending).

**What it found in the library: mono-Z decided on an exact equality.** At ATLAS's mono-Z benchmark the point's rate is
exactly its contour's reference (the shift is 1), and the rule `ratio ≥ 1` decided; the same point read back to 10⁻¹³
fell to undecided. A rate within 10⁻⁹ of its reference is now at it (`resonances.RATE_PRECISION`), which changes
nothing outside that band.

## What P1–P5 change (2026-10-20)

- **The zoo's development half**, run at the generic route's base (`eae6d90`) and at P5 (`2fe722c`): the same counts
  (new models 9 of 11 targets met, controls 11 of 15, the generic route agreeing with the library on 13 of 15 controls)
  and every target within 2.8 × 10⁻⁵ of the base (the speed-ups' numerics: the off-shell integral stacked, the
  thermal root's tolerance; F's declared gate is 0.1%).
- **Verdicts**: each development-half model the generic route builds, judged at its benchmark with each experiment's
  published halo (records verified only), at the base and at the head (`535b4e1`): the same status for all twelve
  (four excluded, eight pending). One model gains outcomes: Feng et al.'s dark photon (a complex scalar) now has
  DarkCast's searches (undecided at its benchmark) and the muon's g − 2 (allowed). Scripts: the scratch
  `generic/verdict_study.py` and `speed_gate.py`'s model list.

## The tactical audit's repairs (T20-01–T20-05, 2026-10-20)

The auditor's tactical audit of this branch (the independent audit of 2026-10-20 (tactical)) found five defects; each is repaired with
its control as a test.
- **T20-01, the pattern over present fermions only.** The fit used only the fermions the mediator couples to, so a
  muon-only scalar read as a heavy Higgs (53 pb of gluon fusion from a top loop it does not have) and a muon-only
  vector as a dark photon (an electron-beam search applied). The fit now runs over every Standard Model fermion, an
  absent coupling as zero; gluon fusion's heavy-Higgs route asks of the six quarks alone, since they make it
  (`generic_production.heavy_higgs_kappa`), so the library's quark-only Yukawa-like scalar keeps that route.
- **T20-02, the mixed Higgs's reference.** κ was read against the model's own h, cos θ times the Standard Model's, so it
  was tan θ, and production took κ² times the Standard Model's heavy-Higgs σ: 9.9% too high at sin θ = 0.3, 56% at 0.6.
  The references are now the unmixed Standard Model's photon, Z and h (`generic_portrait._standard`).
- **T20-03, dark parity is not invisibility.** Every Z₂-odd pair had counted as invisible, so a vector decaying to a
  charged odd pair gave BR(invisible) = 0.9999. Only pairs of dark matter and neutrinos are invisible; a pair with any
  other new state is unresolved, and where more than 1% of the width is unresolved (`UNRESOLVED_SHARE`, declared
  here) DarkCast, B → K + invisible and Belle II's L_μ − L_τ search are pending with the decays named. Below 1% the
  unresolved part counts as visible. (Withdrawn by the owner's decision #7: see "Unresolved decays" below.)
- **T20-04, a contact split in two.** The validity scale Λ took the largest single term, so a contact refused as a
  whole (√s = 1290 GeV > Λ/3) was computed when written as two halves (Ωh² = 0.111). Terms with the same legs and
  bilinears are now summed first; two that cancel are no contact.
- **T20-05, quartics the P5 match did not see.** With λ_P1 = λ_P2 = 0, |H₂|⁴'s coupling set to zero (no vertex) or
  reversed (the same magnitude) still matched the library's 2HDM+a. The comparison now covers every vertex either
  model has, and compares rephasing-invariant vertices with their sign.

## Unresolved decays (the owner's decision #7, 2026-10-20)

A mediator's pair with a new state other than the dark matter is unresolved: whether it is seen depends on that
state's decays, which ADROIT does not follow. The 1% share below which such width counted as visible is withdrawn: a
sub-percent unknown share can still decide a point close to a limit. In its place (`generic_portrait`):
- **The Standard Model pairs' share is exact** (`visible_share`): the width into Standard Model pairs other than
  neutrinos, whatever the unresolved pairs do.
- **BR(invisible) has two extreme assignments** (`invisible_bounds`): the lower counts every unresolved pair as seen;
  the upper counts as unseen every unresolved pair whose states are all neutral and colourless. A pair with a charged
  or coloured state is never invisible, whatever its share.
- **A search is decided only where both assignments give the same decision** (`searches._edges`), from the
  assignment nearer the limit and flagged with the interval; else it is pending, with the decays named and the
  interval, and, where an assignment is itself pending, its own reason too. The native-CL decision is reconciled the
  same way: kept only where every assignment gives it (the auditor's RC20-04, 2026-10-20: a native exclusion at one
  assignment, Belle II at 90%, had been exported unqualified while the other assignment allowed).

Each search the unresolved decays reach:
- **DarkCast's visible prompt searches** read the Standard Model pairs' resonance (e⁺e⁻, μ⁺μ⁻ at m_A′), which a new
  state's cascade does not make: decided by the exact share.
- **DarkCast's invisible searches, BaBar's B → K + invisible and Belle II's invisible Z′** read the rate of decays
  that leave nothing seen. A new state's decay products can only remove an event from that signal, so its rate lies
  between the two assignments: decided where both agree.
- **DarkCast's displaced searches** are limits for the minimal dark photon's lifetime: applied only where the dark
  photon decays to Standard Model pairs alone (no invisible and no unresolved width).
- **BaBar's 4μ and Z → 4μ** (L_μ − L_τ) read the μ⁺μ⁻ resonance among the vanilla model's decays: g′ scaled by
  √(BR(μμ)/vanilla), the vanilla BR(μμ) among Standard Model pairs alone: Γ(μμ) over the width into Standard Model
  fermion pairs, neutrinos included, summed from those channels. An unresolved pair had been counted with the
  Standard Model's, raising the scaled coupling by √(1 + Γ_unresolved/Γ_SM pairs); and a Majorana dark matter's pair,
  χ⁰χ⁰, had stayed in the denominator, the dark pair having been subtracted by its Dirac spelling (the auditor's RC20-05:
  BR(μμ) 0.005 for 1/3, a false Z → 4μ exclusion where the record is eligible).
- **LHCb's B → K a(→ μμ)** reads BR(a → μμ) and the lifetime from the a's own widths, both exact: unchanged.

What it changes (2026-10-20): nothing at the benchmarks. The zoo's development half through the generic route, each
model the route builds judged at its benchmark with each experiment's published halo (the scratch `verdict_study.py`
of P1–P5), before (`31db564`) and after: the same status for all twelve (four excluded, eight pending), the same
pending reasons and the same decision from every search. None of their mediators has an unresolved decay where a
search decides. A library model's searches take the same path as before (its visible share is 1 − BR(invisible), its
BR(invisible) one value), so the 256 crossings are unchanged by construction; the gates are
`test_generic_portrait.py` (bounds, the edge rule, DarkCast's displaced searches, the 4μ share) and
`test_records_batch.py` (B → K + invisible).

## Muon g − 2 (the owner's decision #11, 2026-10-20)

One calculation for the library and the generic route (`searches.muon_g2`, `g2_parts`): every new state coupled to
the muon, its one-loop parts summed, and the total compared once with the signed record `muon-g2-2025` (the central
1.96σ interval, as before). Parts of opposite sign cancel; no mediator excludes by itself. It replaces the three
separate calculations (the generic route's vectors, `lmu_ltau`'s and `partner`'s).

Computed at one loop:
- a new neutral vector, from its vector and axial couplings to the muon (`muon_g2_vector` + `muon_g2_axial`): the
  library's dark photons (the A′ after the mixing's exact diagonalisation), B − L and L_μ − L_τ (with its loop-induced
  kinetic mixing εeQ, which its spec does not write: Δa_μ 0.88% above g′ alone) and the s-channel vectors' g_ℓ; the
  generic route's new vectors from their portraits;
- a charged scalar with a neutral, colourless fermion (the dark matter, a neutrino or another) joined to the muon with
  one chirality (`muon_g2_scalar_partner`): the library's μ_R lepton portal; the generic route's partners and a
  doublet's or triplet's charged scalar with a neutrino, read from their Yukawa vertices.

The applicability policy:
- **pending** where the model has a state coupled to the muon whose part is not computed: a partner coupled to both
  chiralities (its chirality flip), a new fermion joined to the muon, or a neutral scalar, alone or beside a computed
  part: "the neutral-scalar contribution, including relevant two-loop terms, is not computed" (the owner,
  2026-10-20: its Barr–Zee terms can be substantial, Ilisie arXiv:1502.04199, so a one-loop estimate does not give
  the total; a validated bound on the omitted part, deciding only where the whole interval agrees, is deferred). On
  the library's route: the ALP and the scalar mediator with g_ℓ ≠ 0, the singlet mixed with the Higgs boson
  (sin θ ≠ 0), the 2HDM+a's new neutral scalars (from its UFO's muon vertices). A scalar with no coupling to the
  muon does not count. The pending outcome blocks an allowed verdict and keeps an exclusion another search makes;
- A contact term contributes only beyond one loop: not counted.

Gates (`tests/parameter_space/test_generic_portrait.py`):
- equivalent models on both sides of the bound: the library's B − L and L_μ − L_τ vectors (three masses) and Dirac dark
  photon (two), each against the same model through the generic route, with Δa_μ at 0.9 and 1.1 times the upper edge:
  the same Δa_μ (10⁻⁹; the dark photon 10⁻⁴, its Z mixing) and the same decision, allowed and excluded; the μ_R
  partner likewise at the lower edge;
- a vector (Δa_μ > 0) and an axial vector (Δa_μ < 0), each excluded alone, allowed together;
- the policy's pending cases, and a scalar alone without an outcome.

What it changes (2026-10-20):
- **The 256 crossings** (each point's g − 2 before and after, records verified only; the scratch
  `d11/crossings_g2.py`): no status changes. The scalars' pending g − 2 reaches 50 of them, none viable: 9 ALP and 21
  singlet-mixing points excluded by other searches (still excluded) and 20 ALP points already pending. The 28 dark-photon points (Dirac, scalar, inelastic) and the 7 B − L
  points gain a g − 2 outcome, allowed at every one; the 9 L_μ − L_τ points keep their decisions (5 excluded, 4
  allowed). No μ_R partner is among them.
- **The zoo's development half** through the generic route (the verdict study, after #7 against after #11): no
  status changes. Feng et al.'s dark photon keeps its g − 2 (allowed). Choubey et al.'s singlet–triplet fermions gain a
  pending g − 2: its scalar triplet's Δ⁺ joins the muon to ν_μ (computed, −1.0 × 10⁻¹⁹) and its Δ⁰ is a neutral scalar
  coupled to the muon (not computed); the model stays excluded by its other searches.

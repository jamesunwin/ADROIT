# The hadronic window (the owner's decision, 2026-10-20)

The owner's answer: "Yes—refuse the unsupported hadronic calculation in the library too. A free-quark ss̄ calculation
in this region does not establish the physical hadronic rate." The refusal applies "according to the energy entering
the calculation: approximately √s = 2m_χ for annihilation, and m_a for mediator decays"; the uncertainty propagates
"to dependent relic densities, widths, branching fractions and searches", never by removing the hadronic channel and
treating it as zero. On the window's top: "option 1, with two qualifications" — the inclusive 3 GeV guard is ADROIT's
conservative policy, not a threshold the source proves, and the current is classified, not the mediator's spin.

## The policy (`constraints/hadronic_window.py`)

| current | free quarks and gluons computed | source of the edge |
|---|---|---|
| pure vector (an annihilation: every carrier spin 1 with vector quark couplings and no axial or spin-0 part at all; a decay: vector, its axial part ≤ 10⁻³) | √s or m > 2 GeV | parton–hadron duality is "roughly valid above 1 GeV for vector currents" (Aloni, Soreq & Williams, arXiv:1811.03474 p. 2); the library's dark photon keeps its measured R ratio below |
| anything else: scalar, pseudoscalar, axial, mixed, t-channel, contact, unclassified | √s or m > 3 GeV (3 GeV refused) | ADROIT's conservative policy. For a pseudoscalar the paper finds the one-loop correction as large as the leading one at m_a ≈ 2 GeV ("the smallest mass where Eq. (4) has O(1) validity"), "O(1) uncertainties" for 0.5 ≲ m_a ≲ 2 GeV, and treats the rates non-perturbatively up to 3 GeV; it leaves η_c mixing near 3 GeV aside (its footnote 1). |

- **The energy.** An annihilation's √s is taken at its threshold, 2m_χ (m_a + m_b for a coannihilating pair): the
  threshold approximation, since a thermal average also samples √s above it. A decay's is the decaying state's mass.
- **The opening.** Below 2m_π (3m_π for a CP-odd current: a → ππ is forbidden by CP and a → π⁰γ by C, the paper's
  p. 1) no pion pair (or triple) exists, and the quark and gluon channels are closed (zero). The radiative π⁰γ, open
  from m_π⁰ through a vector current, is left out: a declared approximation, at most 6 × 10⁻⁶ of e⁺e⁻ below 0.30 GeV
  for a photon-like current (DarkCast's model, the recheck of 2026-10-22; the measured R ratio starts at 0.30 GeV and
  does not include it), not bounded here for another current. An annihilation within
  10% below the opening is in the window (its thermal tail opens it), as the generic route had it. The generic route
  takes 2m_π for every annihilation current (its tables open quarks and gluons there).
- **What is not changed.** Purely leptonic and photonic channels; validated hadronic treatments (the library's dark
  photon and B − L: the R ratio and DarkCast; the Standard Model Higgs widths' prescription; the Higgs portals' own
  refusal below m_DM = 2 GeV, i.e. √s below about 4 GeV, now stated with its energy).

## The classes it applies to

Every calculation of free quarks or gluons without a validated hadronic treatment:
- the library's Yukawa-like scalar and ALP (`ScalarClass`: CP-even or CP-odd, to 3 GeV), DMWG's vector mediator
  (`Spin1Class`, vector: a pure vector current, to 2 GeV) and axial mediator (to 3 GeV), the Z portal (`ZPortal`: the
  Z couples to quarks vectorially and axially, to 3 GeV; below m_χ = 1 GeV its earlier R-ratio refusal stands), a quark
  partner's t-channel exchange (`TChannel`, to 3 GeV) and a UFO portal (`UFOPortal`, its current not classified, to
  3 GeV, its channels summed so annihilation today is undecided there);
- the generic route (`portals/generic_hadronic.py`), its current classified from the rules.

Kept as they were: the dark photons and B − L (the measured R ratio below 2 GeV, DarkCast), L_μ − L_τ (no quark), the
Higgs portals and the Higgs-mixed singlet (Ωh² refused below m_DM = 2 GeV, √s ≈ 4 GeV; annihilation today, since
2026-10-23, as the window has it: below, "The sixth re-audit's repairs") and the electroweak multiplets.

## What depends on an uncomputed rate

- **Ωh²** is not computed (the class's `domain`) where the annihilation into quarks at its threshold is in the window,
  or where a mediator's hadronic width is in its window and could move an s-channel propagator: the width is bounded,
  0 ≤ Γ_had ≤ m (beyond it the mediator is not a resonance the calculation describes), and Ωh² is kept only where no
  width in that range moves 1/((s − m²)² + m²Γ²) by more than 10⁻³ for every s ≥ 4m_χ² (far below or far above the
  resonance it does not; across it, it does).
- **Annihilation today**: the quark pairs in the window are left out of σv, and every search that needs the total
  (Fermi-LAT's dwarfs, γ-ray lines, antiprotons, the Sun) is undecided. The CMB decides where the other channels
  exclude by themselves: every f_eff is positive, so their p_ann at their smallest f_eff is a lower bound; it is never
  allowed there, since the hadronic σv has no upper bound. The library's ALP computes those channels at the width's
  upper bound (every σv falls as Γ rises with one s-channel diagram); the generic route, whose diagrams may interfere,
  leaves annihilation today undecided where the width moves the propagator.
- **Widths and branching fractions** are bounds: the library's `ScalarClass.width_bounds` (and `width` refuses in the
  window); the generic portrait's `assignments` (the hadronic width at 0 and at m, with decision #7's unresolved pairs
  seen and unseen), `invisible_bounds` their range, and `visible_share` refused as one number. A search is decided
  only where every assignment decides alike (`searches._edges`): B → K a (BaBar), DarkCast's dark-photon searches; the
  LHC's spectra omit a mediator in its window (no map reaches 3 GeV); a cascade through one is not computed
  (`generic_id.decays`).
- **LHCb's B → K a (→ μμ)** (250–410 MeV) lies below 3m_π = 419 MeV, where a CP-odd a has no hadronic decay: its
  width is now exact there (the library's u, d, s pairs, which the DMsimp card's light Yukawas had opened, closed).

## Effects

- **The R3 crossings** (a development receipt (halo_verdict_study_2026-10-20)): of the library scalar's and ALP's 47,
  exactly two change, alp_portal#0 (m_χ = 1.000, m_a = 1.078 GeV: √s = 2 GeV, and its a in the window) and #1
  (m_χ = 1.077, m_a = 2.68 GeV: √s ≈ 2.154 GeV, and its a in the window): their Ωh² is not computed, so their thermal
  crossings are not certified. #0's CMB exclusion stands on its leptonic channels alone, 2.64 × the limit at Γ_had = m_a;
  #1's leptonic channels give 0.44 × the limit at Γ_had = m_a (they exclude only with Γ_had near 0), so its CMB is
  undecided. Among the other library classes, dmwg_V1#0 (m_χ = 1.000 GeV, √s = 2 GeV: the vector window's
  inclusive top) and dmwg_A1#0 (m_χ = 1.000 GeV, axial) lose their relic certification too; dmwg_V1#0's exclusions
  (direct detection, CMS, SModelS) do not depend on the hadronic rate and stand, dmwg_A1#0 was pending. No other
  crossing's Ωh² moves.
- **The development half** (the generic route, its 12 models at their benchmarks and thermal targets): no Ωh² and
  no refusal changes.

## Tests

`tests/parameter_space/test_hadronic_window.py`: the edges (inclusive tops, openings, the margin); the library ALP's
two crossings; the exact 1.5 GeV annihilation edge and the propagator rule; the quark channels closed below 3m_π; the
width bounds and B → K; the same refusals through the generic route, with the current classified (a pure dark photon
computed from 2 GeV, an axial one not); a generic mediator's portrait in its window.

## The candidate audit's repairs (C21-01 to C21-03, 2026-10-21)

- **The current is read from the model's couplings** (C21-01). The library's spin-1 window (`spin1.annihilation_window`,
  `spin1.propagator_window`) reads the mediator's own quark couplings, a named flavour current's included: the
  flavour-vector class keeps its scan's g_q slot at zero, and had been taken for a quark-free model (g_u = 1 at
  m_χ = 0.8 GeV had an Ωh² and a uū rate). With every quark at one coupling it is refused and computed exactly as the
  universal vector mediator.
- **Closed is zero in every consumer** (C21-02). Below the opening the quark pairs are zero in the library's spin-1
  rates and widths (`annihilation`, `spin1.width`: 2m_π for a vector or axial current), today as in Ωh²; in the
  generic route's rates today (`generic_hadronic.today_closed`, as its Ωh² tables), its cascades (a boson's quark and
  gluon decays closed below its opening, `closed_decays`, as in its portrait) and its kinetic-contact rate (a new
  boson's quark and gluon pairs count only above its window; in it the sum is the lower bound certifying contact
  needs). The anomaly workflow's complementary verdicts (DM7, `constraints.verdicts`) refuse the window as the scan
  does: Ωh², the dwarfs and the Sun need a further calculation there, with the window's reason.
- **A coherent vector current** (C21-03). The generic route's annihilation current is vector only where, at the
  pair's threshold, the axial and spin-0 parts (summed in magnitude) are at most 10⁻³ of the whole with the vector
  part taken coherently, Σ_X g_abX v_qX/(s₀ − m_X² + i m_X Γ_X) per quark pair and per structure of the pair's
  vertex: two vectors whose quark couplings cancel no longer hide the axial coupling that carries the whole rate.
- Not changed: the 2 GeV and 3 GeV tops, the opening, the margin and the 10⁻³ rules.

## The recheck's repairs (RC21-01, RC21-02, RC21-06; 2026-10-22)

- **Closed in every portal** (RC21-01). The portal library's common rates (`base.close_partons`, read by `total` and
  `sigma_v_today`) close every quark and gluon final state below 2m_π, as do the t-channel partner's bath and the UFO
  portal's own table and rates: the Z portal and a quark partner's t-channel exchange had free-quark rates today below
  the opening.
- **A mixed current is not vector** (RC21-02). An annihilation current is pure vector only with no axial or spin-0
  quark part at all (above the rules' resolution): a ratio of couplings bounds no ratio of rates across Lorentz
  structures, an s-wave scalar or axial part outgrowing a p-wave vector one as v → 0 (a 10⁻⁶ scalar coupling beside a
  0.01 vector one carried 98.7% of the rate today at 2.5 GeV). A decaying state keeps the 10⁻³ rule (both of its
  currents' rates are unsuppressed on shell).
- **The dark photon's invisible branching fraction** (RC21-06) is its dark partial width over the model's own total
  width (the measured R ratio for its hadrons below 2 GeV), as its other consumers read it; it had summed free-quark
  widths (0.26 against 0.49 at m_A′ = 0.1 GeV). At the 28 R3 crossings with a dark photon no outcome changes.

## The re-audit's repairs (RR22-01, RR22-02, RR22-05; 2026-10-22)

- **A light coloured bath is refused** (RR22-01). A quark partner whose pairs with the dark matter start at or below
  3 GeV (m_χ + m_φ ≤ 3 GeV) has its χφ, φφ* and bound states in the hadronic regime, where coloured states are
  confined: `TChannel.domain` refuses Ωh² there, rather than closing the free-parton rates (the dark matter's own χχ
  stays closed below 2m_π, as before).
- **The UFO table closes the partons between its nodes** (RR22-02): below 2m_π it reads a table without the quark
  and gluon final states, at every √s, not only at its nodes (a bin across the opening had interpolated 2.8% of
  partons back). A node at the opening starts the open side: where the initial pair's threshold lies below 2m_π,
  the interval just above the opening is interpolated from it, where the old table had interpolated across from a
  closed node (the inert doublet at m_χ = 0.1 GeV: 3.10 against 0.74 × 10⁻¹⁴ GeV⁻² at 0.27914 GeV, the same by
  0.35 GeV; RV22-04). A table whose initial threshold is at or above 2m_π is tabulated and read as before.
- **L_μ − L_τ's invisible branching fraction** (RR22-05) is the dark matter's and the neutrinos' partial widths over
  the Z′'s own total width (the R ratio for its hadrons), not one minus its visible fermions' free-quark widths
  (0.0794% at 1.019 GeV). At its 9 R3 crossings no outcome changes.

## The third re-audit's repairs (RX22-01, RX22-02, RX22-06; 2026-10-22)

The rule behind all three: one inventory of what the relic solver and today's rates integrate, and every validity
check reading that inventory, not a parallel list.

- **The generic route's checks read the solver's own bath** (RX22-01). `generic_hadronic.bath_pairs` takes its
  species from `generic.bath_states`, the relic's (every odd state up to and including 1.3 m_χ, with its conjugate);
  it had its own cut, strictly below 1.3 m_χ, so a colour-triplet partner at exactly 1.3 m_χ (0.13 GeV beside
  0.1 GeV dark matter) reached the solver unchecked (Ωh² = 0.0043 Majorana, 0.012 Dirac). On the 26 development-half
  model points the two lists agree.
- **The UFO portal checks every bath pair and its light bosons' widths** (RX22-02). `UFOPortal.domain` checks every
  pair of the relic's species (`_bath`, which `coannihilation` now also reads: the dark matter, its partners and
  their conjugates): a coloured state at or below 3 GeV, or quark or gluon final states with the threshold in the
  window, the current not classified (to 3 GeV). And a new neutral, colourless, Z₂-even boson in its window with an
  open quark or gluon decay, whose width the portal computes from free partons, refuses Ωh² where Γ_had up to its
  mass moves the s-channel propagator of a bath pair by more than 0.1% (`propagator_insensitive`), as the generic
  route; today's rates (`today_unknown`) at s = 4m_χ². The inert doublet at M_H0 = 0.12 GeV with its partners at
  0.16 GeV (H⁺H⁻ → uū at 0.32 GeV) and the 2HDM+a at m_χ = 1.6 GeV with the a at 1 GeV (1.1% from its width) had an
  Ωh²; both are refused.
- **L_μ − L_τ's N_eff share** (RX22-06) is the dark matter's own partial width over the Z′'s own total, as its
  invisible fraction (RR22-05), not one minus every free fermion's width: its loop-induced u, d widths had counted at
  10–40 MeV, where its hadrons are closed (a 1.0001% share read 0.997%, below the 1% rule, and decided).

## The fourth re-audit's repair (RY23-01, 2026-10-23)

- **A closed boson's width is closed in its propagator too.** Below its hadronic opening a new neutral boson's quark
  and gluon decays are closed, and its portrait had left them out, but the width its propagators read was still the
  tree width with the free partons: the generic route's tree model (`generic._without_closed_partons`, before the
  Higgs's own prescription) and the UFO portal's computed widths (`UFOPortal._closed_boson`, `ufo_model.widths`'
  `closed`) now leave them out, so the portrait, every propagator, table and rate read one width. A 0.2 GeV generic
  vector's electron rate today near its pole had been 49 times too small, the 2HDM+a's muon rate with the a at
  0.24 GeV 16.6 times. In the window the free-parton width stays, with the propagator criterion (RX22-02); above it,
  as before. The development half's Feng & Smolinsky dark photon (m_A′ = 0.1 and 0.03 GeV) is the one model point
  with such a boson: its width moves by 5 × 10⁻⁹ relative and its Ωh² by 2 × 10⁻⁶; no R3 crossing has one.
- **A light scalar the mixing makes mostly doublet** (RZ23-03, 2026-10-23). The SM-like Higgs's width prescription
  (`higgs.width`, tabulated from `higgs.WIDTH_FROM` = 2 GeV) gives no width below 2 GeV, and a generic scalar with a
  doublet share above ½ there (named h by the mixing, so outside the new-boson checks) had taken that zero: its open
  lepton decays erased, and the Higgs signal strength divided by it. It keeps its tree width, its quark and gluon
  decays closed below its opening as any boson's; its Ωh² and today's rates are refused, each with the reason. No
  development-half point has such a scalar. (The Higgs signal strength, undecided here at first, is the 125 GeV
  state's since RF23-01, below.)

## The sixth re-audit's repairs (RF23-01, RF23-02, 2026-10-23)

- **The Higgs signal strength is the 125 GeV state's.** It had been taken from the state with the largest doublet
  share wherever that state lay: with eigenmasses 2.5 and 125 GeV and sin θ = 0.99, the 2.5 GeV state (98% doublet)
  gave μ = 0.98, allowed, while the 125 GeV state the measurement sees, 2% doublet, gives μ = 8.3 × 10⁻⁷, excluded.
  The measurement now binds by mass (`generic_lhc.measured_higgs`: the one neutral scalar within 3 GeV of
  125.09 GeV; none, or several, leaves it undecided, named), and the record's formula applies only where it holds
  (`_rescaling_reason`: the state's couplings to the SM fermions, W and Z one common multiple κ of the SM Higgs's with
  κ² its doublet share, CP-even, and no new charged or coloured state in its gg → h or h → γγ loop). In the development
  half this moves one model: Choubey et al.'s triplet makes the 125 GeV state's couplings non-universal (its vev
  enters the W coupling alone, 9 × 10⁻⁴) and its charged triplet scalar couples to it, so its signal strength
  (μ = 0.999, allowed) is now undecided, named.
  - **The owner's review of the declared choices (2026-10-23).** The 3 GeV window is an identification rule, not a
    compatible mass: μ is decided only for a state within 2σ of the measured m_h = 125.09 ± 0.24 GeV
    (`higgs.M_H_SIGMA`, `MASS_SIGMAS`), and is pending elsewhere (no mass likelihood is introduced). The couplings are
    compared to the generator's numerical accuracy (`KAPPA_NUMERICAL` = 10⁻⁴; a pure doublet reproduces the SM
    Higgs's to 5 × 10⁻⁷), not to a 2% physical tolerance: a small non-universality changes production, branching and
    interference by more than itself, and a small CP-odd part is physics, not a CP-even model; either is pending. A
    charged or coloured state is checked by its coupling to the state, at any mass.
- **The library's singlet-mixing h₂ below 2 GeV.** Its width took the SM table's zero below 2 GeV, an open muon decay
  erased, with no refusal (the dark-matter mass cut did not cover the mediator's). It is now decided as the generic
  route decides the same scalar (`SingletMixing.light_reason`): below 2m_π, sin²θ times a Higgs boson's open lepton
  widths (`higgs.leptonic_width`); mostly the doublet (sin²θ > ½) below 2 GeV, Ωh² and today refused; mostly the
  singlet in the window (2m_π to 3 GeV), its hadronic width (0 ≤ Γ_had ≤ m₂) refused where it moves the s-channel
  propagator. No R3 crossing has m₂ below 10 GeV.
- **The library Higgs portals' annihilation today below the width table** (the owner's follow-up, 2026-10-23). Below
  √s = 2 GeV (m_DM below 1 GeV) every Standard Model channel of the off-shell Higgs boson read the table's zero, so
  today's rates were empty and the CMB returned no outcome, as if out of reach. The lepton pairs (tree level) and γγ
  (the table's m³ scaling) are computed there (`higgs.light_channel_width`); the quark and gluon pairs are closed below
  2m_π and named as not computed in the window to 3 GeV (`today_hadronic` on the four classes), so the CMB decides
  only where the computed channels exclude alone, and the other searches that need the rates are undecided. Ωh² is
  unchanged (refused below m_DM = 2 GeV).

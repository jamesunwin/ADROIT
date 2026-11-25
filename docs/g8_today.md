# G8 — Long-range effects today for a generic model (2026-10-15)

Milestone G8 of [`freeze_out_build.md`](freeze_out_build.md). Where long-range forces change annihilation today
(G6 left those searches undecided), the generic route now computes the broken-phase multi-state Sommerfeld effect of
the dark-matter pair. The potentials, the annihilation matrices and the splittings come from the model itself.

## What was built

`adroit/parameter_space/portals/generic_today.py`:
- **The states:** the dark-matter pair and every two-particle state it reaches: the neutral block of its group in
  G7, as ordered pairs.
- **The thresholds.** G1's masses are tree-level, so a pure electroweak n-plet's components are split at one loop
  (M ≫ M_W; Cirelli, Fornengo & Strumia):

      M_Q − M_0 = (α₂/2)[Q² s_W² M_Z + Q(Q − 2Y)(M_W − M_Z)],   s_W² = 1 − M_W²/M_Z².

  This gives 165 MeV for the wino and 353 MeV for the higgsino (the library takes 165 and 341).
- **The potential, boson by boson.** In G7's heavy copy of the model with only one boson's vertices (W, Z, γ, h, a
  new mediator), the elastic amplitudes give that boson's coupling matrix α^B; then V(r) = −Σ_B α^B e^{−m_B r}/r. The
  photon's diagonal is each state's Coulomb tail. The W, Z and γ terms take the couplings at M_Z (α₂ = 0.0347,
  α = 1/128.9, after Beneke et al., as `portals.multiplet`). G2's G_F-scheme couplings are 2% weaker, and 2% in α
  moves a zero-energy resonance by 2% in mass.
- **Annihilation by final state:** Γ^f over the same states and spins from G3 (G7's annihilation matrix, one final
  state at a time), at the hard scale. With A the wave functions at the origin (`sommerfeld.enhancement`), σv_f is
  the trace of (A ⊗ 1)† Γ^f (A ⊗ 1) over the pair's allowed spins: S = 0 for identical fermions, every S otherwise.
  Without the potential this is G6's tree-level σv.
- **In the engine:** where G6 found long-range effects today, `sigma_v_today` takes G8's rates. `today_unknown` is
  then empty, and the dwarfs, the CMB and antiprotons decide as for any model.

**γ-ray lines.** γγ and Zγ come out at tree level with the Sommerfeld effect (the charged states at the origin).
The exclusive photon final state is suppressed by electroweak Sudakov logarithms (0.3–0.8 at 1–10 TeV for the
wino). These are resummed for a pure wino or higgsino (DMγSpec, D21) and for any pure Majorana odd n-plet
(`constraints.endpoint_nll`, D24; both below). Elsewhere the tree-level rate decides nothing: it had been taken as
an upper bound, which could allow, but near a zero of the tree amplitude b the resummed rate is far larger (the
quintuplet at 2.63 TeV: tree 2.5 × 10⁻²⁹, NLL 4.6 × 10⁻²⁶ cm³/s), so since G12 (the audit's G8-5) the line search is
undecided with the reason (`lines_upper_bound`, a hook the search reads).

## Validation

**Against the library's hand-written matrices** (`portals.multiplet`, the wino's and higgsino's Sommerfeld matrices
today), total σv at v = 10⁻³ through the engine (`sigma_v_today`, Sommerfeld on):

| m (TeV) | wino: generic / library | wino's lines (γγ + Zγ): generic / library | higgsino: generic / library |
|---|---|---|---|
| 1.0 | 0.999 | 0.905 | 0.961 |
| 1.1 | | | 0.958 |
| 2.0 | 1.026 | 0.909 | 0.935 |
| 2.3 (the wino's first resonance) | 0.811 | 0.715 | |
| 2.86 | 0.982 | 0.859 | |
| 4.0 | 0.995 | 0.861 | |
| 5.0 | | | 0.842 |
| 8.0 | 1.038 | 0.877 | |

- **The wino's total agrees within 4% off resonance.** On the resonance at 2.3 TeV it is 0.81. A zero-energy
  resonance's position moves with α and the splitting: 2% in α moves it by 2% in mass, and the peak is narrow
  there. The two calculations differ in their inputs there: G1's splitting is 165.4 MeV against the library's 165,
  and the potential's couplings are G2's rotated to M_Z. 0.81 on the peak's flank is consistent with those
  differences in the inputs; it was not traced further.
- **The wino's lines are 9–14% below the library's** off resonance. The difference is not localised. Both are
  tree-level Sommerfeld lines; the library's line matrix is written by hand.
- **The higgsino is 4–7% low at 1–2 TeV**, and 16% low at 5 TeV, as its first resonance (about 6 TeV) approaches.
  The splitting is 353 MeV here against the library's 341 MeV.

**Not done.** The plan's tables for the wino's lines are Hryczuk & Iengo's and DMγSpec's. Both include the
electroweak Sudakov resummation, which is not computed (Limits), so they were not compared. The gate's other half,
the quintuplet's lines within their published uncertainty, needs that resummation too. **Gate, as first run: the
controls agree (the totals); the quintuplet's lines were not met. With the n-plet resummation (D24, below) the
quintuplet's half is met.**

## Resummed lines for a pure wino or higgsino (decision D21, 2026-10-15)

The owner chose to take the published resummed spectra where they exist, and to keep the upper bound elsewhere.
**DMγSpec** (Beneke, Urban & Vollmann, arXiv:2203.01692; GPLv3) gives the wino's and higgsino's photon spectrum,
with the endpoint Sudakov-resummed at NLL′ and the Sommerfeld effect from the NLO electroweak potentials, for
0.5–100 TeV.
- **How ADROIT uses it.** The code is installed in the tools folder (`<tools>/dmyspec`, with its own environment
  `.venv-dmyspec`: it needs SciPy ≤ 1.13). It is never imported by ADROIT. `scripts/build_dmyspec_lines.py` runs it
  once and writes a table (`<tools>/dmyspec/adroit_lines.json`): at its 500 grid masses, the γγ-equivalent rate in
  the H.E.S.S. window x ∈ [0.9, 1],

      σv_line = ½ ∫ d(σv)/dx dx,

  at the single-particle speed 10⁻³ (the higgsino with a 20 MeV neutral splitting). `constraints.resummed_lines`
  reads it.
- **In the generic route.** A dark matter that is a pure wino- or higgsino-like multiplet (`generic_lhc.
  pure_dark_kind`), with the Sommerfeld effect on, takes this rate (`GenericModel.line_sigma_v`). Its lines are
  then decisions, not an upper bound. A Dirac higgsino's rate is doubled against the searches' halving, as the
  library's: its neutral states are split into Majorana states today.
- **A pure Majorana odd n-plet** (the quintuplet included) takes the NLL rate of `endpoint_nll` (D24, below).
  Everything else keeps the tree-level rate, which decides nothing (G8-5, above).

**Against the library's engine** (`portals.multiplet`, whose lines are digitised resummed curves):

| m (TeV) | wino: DMγSpec / library | higgsino: DMγSpec / library |
|---|---|---|
| 0.6 | 0.835 | 1.007 |
| 1.0 | 0.838 | 1.052 |
| 2.0 | 0.533 | 1.052 |
| 2.3 | 0.015 | |
| 2.86 | 1.78 | |
| 4.0 | 1.30 | |
| 5.0 | | 1.029 |
| 8.0 | 0.598 | |
| 13.6 | 1.75 | |

- **The higgsino agrees to 1–5%.** The library's higgsino curve is this same calculation, digitised from H.E.S.S.'s
  plot.
- **The wino does not.** The library multiplies its own tree-level Sommerfeld lines, from the LO potential, by Ovanesyan,
  Slatyer & Stewart's NLL/tree ratio; at 2.9 TeV that is Baumgart et al.'s NLL curve, which H.E.S.S. compares with.
  DMγSpec takes the Sommerfeld effect from the NLO potential, which moves the wino's resonances: the LO peak at 2.3
  TeV, where the library's rate is 70 times DMγSpec's, is no longer there, and DMγSpec rises towards its own near
  2.9 TeV. Off resonance the two differ by 0.5–1.8. Both are published predictions; DMγSpec's potential is the more
  precise. **The owner then chose DMγSpec for the library too** (2026-10-15): `ElectroweakMultiplet.line_sigma_v`
  takes DMγSpec's rate where its table is installed and its splitting applies (the wino's within 10 MeV of DMγSpec's
  164.1 MeV), and the H.E.S.S. reference curves are kept as its cross-check and fallback (`hess_reference_line`). The
  two routes now agree on the wino's and higgsino's lines.

## The resummed line of any pure odd n-plet (decision D24, 2026-10-15)

The owner asked for the resummation for general odd n. `adroit/constraints/endpoint_nll.py` builds it.

**The factorisation.** Baumgart et al.'s NLL endpoint factorisation for the wino (arXiv:1808.08956), as Baumgart,
Rodd, Slatyer & Vaidya extend it to the quintuplet (arXiv:2309.11562), separates the representation from everything
else. The hard, jet and soft evolutions (U_H, V_J, V_S, ω_J, ω_S, Λ^a–Λ^d) are those of SU(2) and the photon, the
same for every n. The dark matter enters only through the operator χᵀiσ₂{T^a, T^b}χ between the incoming χ⁰χ⁰ and
the vacuum. Charge conservation leaves two structures, M^{ab} = A δ^{ab}_⊥ + B δ^{a3}δ^{b3}. In terms of the
Sommerfeld amplitudes s₀Q of the pairs χ^{+Q}χ^{−Q} at the origin (j = (n − 1)/2):

    b = Σ_{Q≥1} Q² s₀Q,    a = ½ j(j + 1)(√2 s₀₀ + 2 Σ_{Q≥1} s₀Q) − b,
    𝓕₀ = 2Λ^d |a + b|² + r_HS^{12/β₀} Λ^c |a − 2b|²,
    𝓕₁ = r_H^{6/β₀} [r_HS^{6/β₀} Λ^a |a − 2b|² + c_H Λ^b (8|b|² − 4|a|² + 4 Re ab*) − 12 s_H Λ^b Im ab*].

These reproduce the wino's published 𝓕₀ and 𝓕₁ (1808.08956 eq. (4.7)) coefficient by coefficient, and the
quintuplet's a = 2s₀±± + 5s₀± + 3√2 s₀₀, b = 4s₀±± + s₀±. The tree-level line is 2πα₂²s_W²|b|²/M², and an SU(2)
singlet (A = B) has a = 2b. The rate is the cumulative cross-section of photons above z_cut M at the canonical
scales (1808.08956 eq. (4.6)); the line searches take z_cut = 0.9, the H.E.S.S. window, as DMγSpec's table does.
The quintuplet paper's restatement of the evolution has two typos, so the wino paper's forms are used: its U_H has
Γ₀/Γ₁ where Γ₁/Γ₀ belongs, and it defines Λ^c twice, the second being Λ^d. A third, its two-loop cusp Γ₁ = (8/9)(35 − π²)
for 280/9 − 8π²/3 = 4.79 (the wino paper's eq. (3.7)), was copied at first and corrected by the closure audit (G8-6):
the quintuplet's line at 13.6 TeV went from 8.633 to 8.774 × 10⁻²⁶ cm³/s, and the wino's checks against DMγSpec moved by
under 1%.

**The Sommerfeld amplitudes** solve the pairs' potential, arXiv:2309.11562 eq. (3.5), at NLO. The W and Z Yukawa
terms take Beneke et al.'s fitting functions (that paper's eq. (3.7)). They multiply the same group structure, so
they hold for any n. The splittings are M_Q − M₀ = Q²·164 MeV.

Three things were settled by the checks below:
- **The phases.** The charge basis of the generators writes the SU(2) singlet as Σ_m (−1)^{j−m}|m, −m⟩. The formulas
  take s₀Q = √2 s₀₀ for the singlet, so the code removes the (−1)^Q. Without it a resonance (singlet-dominated) had
  |a − 2b|/|a + b| = 2.1 for the wino instead of 0.01, and the interference terms had the wrong sign.
- **The coupling of the potential.** With α₂ = α(m_Z)/s_W² = 0.0338, the paper's own input, the quintuplet's thirteen
  Sommerfeld resonances from 1.8 to 90 TeV fall within 0.4% in mass of the paper's (its Fig. 15, digitised). Beneke
  et al.'s α̂₂(m_Z) = 0.0350, which DMγSpec uses for the wino, puts them 3–4% lower. ADROIT takes 0.0338.
- **The solver.** For a quintuplet above about 30 TeV, the closed χ⁺⁺χ⁻⁻ channel's regular solution grows as
  e^{κr} with κr_max up to 100. Every column of the solution matrix then turned towards it, and the matching lost
  them (a tree line of 10⁻³⁹ cm³/s at 70 TeV). `sommerfeld.enhancement` now integrates in stretches of κΔr = 4 when
  κr_max > 25, and re-orthonormalises the columns between stretches (a change of basis of the regular solutions,
  undone on the weights). Below that threshold nothing changes.

**Checks.**

| check | result |
|---|---|
| The wino against DMγSpec's NLL′, both with DMγSpec's NLO Sommerfeld factors, z_cut 0.7–0.99 | within 4% at 1–10 TeV at every z_cut (the shape agrees to 1%); 20–25% low above 15 TeV, where DMγSpec's own tree line drifts 20% against its Sommerfeld table between 13 and 18 TeV (not ADROIT's resummation) |
| The wino's first resonance, LO → NLO potential (α̂₂ = 0.0350) | 2.255 → 2.390 TeV; DMγSpec 2.282 → 2.421 (the same 6% shift; a common 1.2% offset in the inputs) |
| The quintuplet's |s₀₀|, |s₀±|, |s₀±±| against Fig. 15 off resonance (LO) | within 5–10% at 4 and 80 TeV (the NLO potential moves the peaks) |
| The quintuplet's line (z → 1) against Fig. 1 left, 1–100 TeV | NLL/tree within 1–3% at every mass except where the tree line passes through zero |
| **The quintuplet's line at the thermal mass, 13.6 TeV** | **8.774 × 10⁻²⁶ cm³/s against the paper's 8.624 × 10⁻²⁶ (band 8.26–8.89), 1.7% above its centre** |
| The quintuplet's line where the figure resolves it (82 masses; resolved where one point of the mass axis, 1%, moves the paper's curve by less than its band) | 19 of 19 inside the band (17 of 19 before the cusp Γ₁ was corrected at G12) |
| On the resonances' flanks (63 masses) | 28 within 10% of the paper's central curve; the rest are within a 1% shift in mass of it |

**Gate (G8's quintuplet half): met.** The quintuplet's line is within its published uncertainty at the thermal
mass, and wherever the figure resolves it to better than its band.

**Where it is used.** A pure Majorana odd n-plet (spin ½, Y = 0, no colour, every state pure) with the Sommerfeld
effect on takes `endpoint_nll.line_sigma_v` at 1–100 TeV, at the relative speed 10⁻³:
- the generic route, after DMγSpec (`GenericModel.resummed_line`, "nplet<n>"); the wino therefore falls back to it
  where DMγSpec's table is absent;
- the library's `ElectroweakNplet` (`resummed_lines`). Its other annihilation today is still not computed, so the
  line search is the one indirect search it decides.

The thermal quintuplet's line in the H.E.S.S. window is 1.84 × 10⁻²⁵ cm³/s, 9.7 times the H.E.S.S. limit for its
cuspy profile, as the paper finds (a core of a few kpc is needed).

**Conventions to note.**
- DMγSpec's tables are at the single-particle speed 10⁻³; this rate is at the relative speed 10⁻³, the library's
  and the quintuplet paper's. They differ only near resonances.
- Bound states' own lines are not included. The quintuplet paper finds them subdominant except at isolated masses
  near the Sommerfeld peaks (its Fig. 7). Since G12 (D30) the band below covers their few percent.

**The theory band (D30, G12).** The line search applies a band on a resummed rate: excluded only where its lower
edge is above the limit, allowed only where its upper edge is below, undecided with the reason otherwise
(`searches.lines`, `tests/parameter_space/test_line_band.py`):
- the NLL n-plet rate: ±5% (NLL against NLL′; DMγSpec's NLL′ wino is 4% above this NLL off resonance), and for
  n ≥ 5 a further +5% for bound states' line photons, except at isolated masses near the Sommerfeld peaks
  (`endpoint_nll.theory_band`). Since D32 (the external audit's A05, 2026-10-16) the band has no upper edge for
  n ≥ 5: bound-state photons are not computed and dominate near the peaks, so the allowed side is pending;
- DMγSpec's rates above 13 TeV: ±25%, the size of its own drift between 13 and 18 TeV
  (`resummed_lines.theory_band`).
- Below 1 TeV the factorisation's M ≫ m_W fails, and no rate is given.

## Limits

- No Sudakov resummation outside the pure wino, the pure higgsino and the pure Majorana odd n-plets (mixed
  multiplets, Dirac n-plets with Y ≠ 0 other than the higgsino, scalars, masses below 1 TeV): those lines are
  undecided (above).
- The n-plet resummation is NLL; DMγSpec's is NLL′ (4% higher for the wino off resonance): the ±5% band (D30).
- Bound states today (their annihilation and the line from their formation) are not included.
- The splitting formula is the heavy limit; G1's own masses carry any splitting from mixing.
- Coloured dark matter today is not computed.

Tests: `tests/parameter_space/test_generic_today.py`, `tests/constraints/test_resummed_lines.py`,
`tests/constraints/test_endpoint_nll.py`, `tests/constraints/test_sommerfeld_stability.py`,
`tests/parameter_space/test_nplet.py`.

# The model zoo (G0)

**Why.** The owner's aim (2026-10-13) is a system that adapts to any freeze-out model it is given. The zoo measures
how far ADROIT is from that. It holds freeze-out models from the literature, each with numbers its authors computed.
Each model is put to ADROIT as typed data, and two things are recorded:
- **coverage:** computed, or refused with the reason;
- **accuracy:** each published number met or missed.

The zoo is G0 of the build plan for any freeze-out model ([`freeze_out_build.md`](freeze_out_build.md)). It runs
first, because every later milestone (G1–G12) is gated on it.

The zoo measures additions to the standard library, not replacements for it. A model the library covers is computed
by its validated engine, as it is today. The zoo records, for every model:
- which path computed it: a standard engine, or (from G4) the generic route;
- where both apply, whether they agree.

## The rules, fixed before any result

- **Halves.** DM10's hash of the suite and the id (`adroit.evaluation.core.half_of`) puts each entry in the
  development or the held-out half. No entry moves afterwards.
  - The development half guides the work.
  - The held-out half runs only to confirm a declared step (`--held-out --reason`), and each run is entered in the
    ledger (`docs/dm10/held_out_ledger.jsonl`).
- **Controls.** Models ADROIT was built or validated against are marked `in_library` and summarised apart. They test
  the harness, not adaptation.
- **Targets** are numbers the authors printed: a table of benchmark points, or a stated thermal mass. A target read
  from a curve says so, with its reading error. Every target carries its arXiv id, 1-based PDF page, location and a
  verbatim quote.
- **When a target is met:** within the source's stated uncertainty, or else the default tolerance:
  - 10% for a thermal mass or a thermal splitting;
  - 20% for Ωh²;
  - a factor 2 for σ_SI.
- **What counts as an outcome:**
  - a refusal without a reason is a bug;
  - an exception is a bug;
  - a computed target outside its tolerance is a finding.

## Two routes

1. **The typed route.** The model goes in as typed data, and the map (`classify`) reads it, as an intake would. This
   is the route that has to grow if ADROIT is to adapt to new models.
2. **The library route.** Used only when the typed route refuses a model the standard library already holds. The
   entry names that library model (`library`), and each target gives the engine's parameters at its benchmark
   (`point`). The case records the typed route's refusal beside the result. It shows what the library already
   computes but the intake does not yet reach.

A case reports which route and which engine produced its numbers.

## The quantities

| quantity | how it is computed |
|---|---|
| `omega_h2` | Ωh² at the benchmark |
| `thermal_mass_gev` | m_χ at which Ωh² equals the paper's Ωh²; any mediator tied to m_χ as the paper ties it (`mediator_ratio`) |
| `thermal_splitting` | Δ = m_med/m_χ − 1 at which Ωh² equals the paper's Ωh², at fixed m_χ |
| `sigma_si_cm2` | σ_SI at the benchmark: the dark matter–proton cross-section, σ_p = (c₁ᵖ)²μ²/π (G5) |
| `sigma_v_cm3_s` | recorded, not compared |

`thermal_splitting` is for forbidden channels. There Ω ∝ exp(2Δx_f), so a reading error of 0.003 in Δ is about 12% in
Ω; the comparison is made in Δ.

**Finding the root.** Ωh² can cross the target more than once (below and above a resonance, say). The search takes
the crossing nearest the published value:
- it steps outward on the grid value × 3^(k/4), k = −4…4;
- it bisects the first bracket in ln x to 0.2%.

If there is no crossing within value × [1/3, 3], the case says so.

**The authors' physics.** Some papers print several numbers for one model with different physics: perturbative only,
with the Sommerfeld effect, with bound states. Each such target sets the engine's switches (`engine_options`, e.g.
`sommerfeld: false`), so that it is compared with the same physics. If the engine has no such switch, the target is
reported as not compared, with the reason.

## How the models are written as typed data

- **Masses.** A field's `mass_gev` is its Lagrangian mass. Where the paper gives physical masses after mixing, the
  entry derives the Lagrangian masses and couplings from them, and each field's `mass_justification` gives the
  relation. For example, the inert doublet's μ₂ = √(M_H² − λ₃₄₅v²/2), and the singlet–doublet masses come from
  {M₁, M₂, sin θ}.
- **Mixed multiplets** (singlet–doublet, doublet–triplet, singlet–triplet): every field whose neutral member mixes into
  the dark matter has the role `dark_matter`.
- **Terms** are written as the paper prints them, with the full coefficient in L. Exceptions are recorded in the
  entry's notes. For example, Kamon et al. print ½g_V m_V for the H–V–V coupling; the typed model keeps the
  covariant derivative's g_V m_V.
- **Ωh² normalisation.** A thermal mass is solved for the Ωh² the paper used:

  | Ωh² | papers |
  |---|---|
  | 0.1193 | Bottaro et al. |
  | 0.1188 | Beneke et al. |
  | 0.119 | Mitridate et al. |
  | 0.118 | the LHC DM WG |
  | 0.1197 | D'Agnolo & Ruderman's curves |
  | 0.1209 | von Harling & Petraki (their Ω = 0.26 with ρ_c = 4.9 × 10⁻⁶ GeV cm⁻³) |
  | ≈ 0.1 | Pospelov et al. |
  | 0.112 | Cohen et al.: the centre of their 0.1053–0.1193 window |
  | 0.12 | papers that print no value |

- **Curve readings.** Each reading's uncertainty is the reading error. One exception: for Feng & Smolinsky the
  uncertainty is 0.2 dex in κ² (≈ 58% in Ωh²). Their non-relativistic thermal average puts their m_A′ = 3m_X curve
  that far above the relativistic reference curve they overlay.
- **Quotes.** All 59 of the first version were checked against the paper text, 2026-10-13 (the replacement entry's two
  on 2026-10-14, verbatim ignoring whitespace):
  - 49 match the stated page verbatim, ignoring whitespace;
  - in the other 10, every number in the quote is on the stated page; the differences are ligatures, hyphenation
    and table layout in the text extraction.

## The split and the controls (fixed 2026-10-13, before any result)

| | development (12) | held-out (19) |
|---|---|---|
| new (17) | complex_scalar_triplet_y1_bottaro, dark_photon_complex_scalar_feng, doublet_triplet_fermion_dedes, real_scalar_dm_vectorlike_lepton_giacchino, singlet_doublet_dirac_yaguna, singlet_triplet_fermion_choubey | b_minus_l_rhn_zprime_okada, coloured_coannihilation_fermion_octet_desimone, dark_photon_scalar_resonance_feng, dark_qed_bound_states_vonharling, forbidden_dark_photon_dagnolo, majorana_dm_charged_scalar_lepton_partner_giacchino, real_scalar_quintuplet_bottaro, secluded_dirac_vector_pospelov, singlet_doublet_majorana_cohen, two_hdm_pseudoscalar_singlet_mediator_ipek, u1x_vector_dm_dark_higgs_kamon |
| controls (14) | coloured_coannihilation_bsf_harz, coloured_coannihilation_scalar_triplet_desimone, dirac_fermion_higgs_portal_eft_cpv_gambit, singlet_fermion_scalar_mediator_das, vector_higgs_portal_athron, wino_majorana_triplet_bottaro | dmwg_dirac_vector_zprime_v1, higgsino_dirac_doublet_bottaro, inelastic_pseudo_dirac_dark_photon_berlin, inert_doublet_kalinowski, lmu_minus_ltau_dirac_resonance_holst, majorana_fermion_higgs_portal_eft_resonance_gambit, majorana_quintuplet_mdm_bottaro, scalar_singlet_higgs_portal_gambit |

**Controls** are models whose papers ADROIT was built, benchmarked or validated against:
- the wino, the higgsino and the Majorana 5-plet (`docs/nplet.md`);
- the GAMBIT Higgs portals (scalar, Dirac with CP violation, Majorana, vector);
- the inert doublet (Kalinowski et al.'s benchmarks);
- the DM WG vector mediator;
- the coloured coannihilation of De Simone et al. and Harz & Petraki (the t-channel engine's validation);
- the inelastic dark photon (Berlin et al.);
- L_μ − L_τ (Holst et al.);
- the singlet fermion with a mixing scalar (Das et al.: the singlet_scalar_mixing engine).

**One change since** (2026-10-14, the owner's decision D18): `singlet_doublet_dirac_bhattacharya` was withdrawn and
`singlet_doublet_dirac_yaguna` added in its place (Yaguna, arXiv:1510.06151: the same field content, a Dirac singlet
and a Dirac doublet mixed by two chiral Yukawas). The new entry was written before any result. DM10's hash puts it
in the development half too. Its two targets are the paper's stated thermal relations: the splitting
M_χ2/M_χ1 − 1 "of order 6%" at M_χ1 = 200 GeV (±0.01 for "of order"), and the upper bound "of order 750 GeV" on the
dark matter mass as the states become degenerate. The paper prints no σ_SI at a parameter point. Its Z-exchange
formula, eq. (9), is checked against ADROIT's matching instead, exactly (`test_dd_matching.py`). In the G6 run it gives 0.0536 and
730 GeV: both met. The tables below
before this date record the withdrawn entry as it was run.

## The development baseline (2026-10-13, commit 142a0aa + the zoo)

**The new models** (development half): 0 of 6 computed, and every one refused with a reason. The refusals say which
generic step each model needs:

| model | refused because | needs |
|---|---|---|
| complex_scalar_triplet_y1_bottaro | the n-plet engine takes fermions only | long-range effects from group theory, for scalars too (G7) |
| singlet_doublet_dirac_bhattacharya | two dark-sector fields that mix | the mass basis and the generic route (G1–G4) |
| singlet_triplet_fermion_choubey | two dark-sector fields that mix | the mass basis and the generic route (G1–G4) |
| doublet_triplet_fermion_dedes | the multiplets differ, so this is not an n-plet | the mass basis and the generic route (G1–G4) |
| real_scalar_dm_vectorlike_lepton_giacchino | scalar dark matter with a fermion partner | the generic route (G1–G4) |
| dark_photon_complex_scalar_feng | the paper writes the dark photon's coupling to the SM current after mixing | the generic route, which reads the coupling as written (G4); or an intake that rewrites it as kinetic mixing (G10), after which the library's dark-photon engine applies |

**The controls** (development half): 6 of 6 computed, 11 of 15 targets met. Only the wino reached its engine
through the typed route. The other five were computed through the library route, and the typed route's refusal is
itself a finding: the intake does not reach these engines. The reasons were:
- a Higgs-portal fermion EFT has no mediator field;
- spin-1 dark matter;
- singlet mixing needs the potential matched;
- coloured coannihilation without a stated conversion Yukawa.

| control | target | published | computed | met |
|---|---|---|---|---|
| wino (Bottaro; Beneke) | M (TeV) | 2.86; 2.88 | 3.06; 3.05 | yes (+7%, ADROIT's known offset: `docs/portal_library_2.md` has 3.025 TeV with the Sommerfeld effect alone) |
| Dirac Higgs portal, ξ = 2.07 (GAMBIT) | Ωh² | 0.1155; 0.0381 | 0.1174; 0.0397 | yes |
| coloured scalar triplet (De Simone) | M (TeV), perturbative; Sommerfeld | 1.30; 1.70 | 1.33; 1.83 | yes |
| coloured scalar triplet (Harz & Petraki) | M (TeV), + bound states; Sommerfeld; perturbative | 3.30; 1.865; 1.33 | 3.24; 1.83; 1.33 | yes |
| vector Higgs portal (GAMBIT) | Ωh² at m_V = 62.46 GeV | 0.113; 0.093 | 0.067; 0.057 | **no** (−40%) |
| singlet fermion, mixing scalar (Das) | Ωh² BP2; σ_SI BP2; Ωh² BP8; Ωh² BP9 | 0.119; 6.72e-50; 0.120; 0.119 | 0.217; 7.06e-50; 0.121; 0.155 | **no**; yes; yes; **no** |

**The four misses:**
- **The vector Higgs portal** sits on the Higgs pole's tail (2m_V just below m_h). There, Ωh² depends steeply on
  m_h, which GAMBIT varies as a nuisance parameter without printing it. The spread near a resonance is already
  recorded as up to an order of magnitude (`docs/portal_library_5.md`).
- **Das BP2 (×1.8) and BP9 (+30%)**: the singlet-mixing engine sets the scalar potential's trilinear couplings to zero
  (its docstring says so). Das et al. have μ₃ = 100 GeV at BP2 and 20 GeV at BP9, and they enter χχ̄ → h₂h₂ through
  the s-channel. This is the likely cause, not yet verified. BP8, with the Higgs-mediated channel dominant, is met.

**An entry correction** (made before this baseline was recorded): the first development run stopped every
coloured-coannihilation target at the t-channel engine's domain (m_φ > m_χ). The papers' ΔM = 0 is now taken as
m_φ = 1.0001 m_χ, and the entries' notes say so. That first run remains in `runs/eval/model_zoo.jsonl`.

## G4: the generic route (2026-10-14)

The generic engine (`docs/g4_generic.md`) computes 4 of the 6 new development-half models: Bhattacharya et al.,
Choubey et al., Dedes & Karamitros and Giacchino et al.'s scalar. 3 of their 7 targets are met. It refuses the
complex scalar triplet and Feng & Smolinsky for want of the Sommerfeld effect (G7). MadDM on the exported models
localises the misses. Beside the controls it agrees with the library on 7 of 9 targets; the other two are Das et al.'s
BP2 and BP9, where it matches the paper and the library does not.

## G7: long-range effects (2026-10-15)

With G7's Sommerfeld effect and bound states (`docs/g7_long_range.md`), the generic route computes all 6 new
development-half models, and 10 of their 11 targets are met. The complex scalar triplet gives 2241 GeV against
2100. The controls: 11 of 15 met, as before; the generic route agrees with the controls' engines on 13 of 15.

**After G8–G11** (commit f70bc51, 2026-10-15): the new models 6 of 6 computed, **9 of 11** targets met. Dedes &
Karamitros's t1 moves from 0.134 (met) to 0.158 against 0.12. This comes entirely from the off-shell fix that the
held-out run found (checked by reverting that one change: 0.134 again). It returns t1 to G4's 0.156, beside MadDM's
0.152 (`docs/g4_generic.md`), so t1 is again a miss localised to its input point (D12: the point lies outside the
paper's plotted region). The controls are unchanged: 11 of 15, and the generic route agrees on 13 of 15.

**The held-out half, the second of its three runs** (G4, G7, G12; ledgered in `docs/dm10/results/model_zoo.jsonl`):
the new models 9 of 11 computed, 9 of 13 targets met; the generic route agrees with the controls on 13 of 14. The
misses and the error it found are listed in `docs/g7_long_range.md`. No entry was changed after it.

**G10's intake** also read every entry's Lagrangian (the spec only, no target; `docs/g10_intake.md`). Two held-out
references did not build in G1.

**Decision D20 (the owner, 2026-10-15): correct them from the papers, and mark them not blind at G12.**
- **`u1x_vector_dm_dark_higgs_kamon`: corrected.**
  - The quartic −λ_Φ(Φ†Φ − v_φ²/2)² had one Φ† too few (net U(1)_X charge +2).
  - The second benchmark (g_V = 1.91) kept the first one's vacuum value v_φ = 80/3.53 GeV, so its V came out at 43
    GeV. A target can now override a vacuum value (`overrides.vevs`), and it takes v_φ = 80/1.91 GeV.
  - Both benchmarks now state m_H₁ = 125 GeV, which is descriptive only.

  Both benchmarks now give m_V = 80, m_h₁ = 125 and m_H₂ = 200 / 500 GeV. Checking that meant building this
  held-out entry's spectrum (masses only; no target quantity was computed). The entry's notes record the correction.
- **`two_hdm_pseudoscalar_singlet_mediator_ipek`: corrected** (the owner's second round, 2026-10-15, D25). The paper
  fixes only the product y_χ sin 2θ tan β = 2.4, and its pseudoscalar couples to b quarks and τs through the second
  Higgs doublet's Type-II Yukawas, which G2 now reads. The entry is written in the Higgs basis (H takes the whole
  vacuum value; the alignment limit, with no quartics of H₂), with the portal i B a₀H†H₂ + h.c. (the i mixes a₀ with
  A⁰), and the zoo's choices tan β = 10, sin 2θ = 0.3, y_χ = 0.8 and m_A = 600 GeV. It builds: the light CP-odd
  state at 100 GeV with 2.3% A⁰. The target's `at` states those choices, and the reference lists the H₂ quartics and
  the singlet's quartic as left out. Both were added after G10's sixth and seventh passes showed the agent choosing
  its own (the correction had said the target states them; it had not). No target value changed.
- **`two_hdm_pseudoscalar_singlet_mediator_ipek`: the portal's sign corrected** (2026-10-16, closing G10). The entry
  had written the paper's V_port = i B a₀H₁†H₂ + h.c. as a term of L; the paper puts it in the potential (eqs.
  (4)–(5)), which enters L as −V, so L carries −i B, and the portal is then eq. (14)'s V_port = B v a₀A⁰. G10's
  re-score found it: the intake agent had written −i B. No target value changed (the entry's σv depends on
  (y_χ B)²), and no target of this held-out entry was computed.
- **`dark_photon_complex_scalar_feng` and `dark_photon_scalar_resonance_feng`: compared after doubling** (2026-10-16,
  the owner's decision D31). The paper's relic formula (eq. (8), with eq. (9)'s g = 1) counts one species, applied to
  the φφ* cross section; the total of φ and φ*, which ADROIT computes, is twice it. The targets become Ωh² = 0.2398
  (uncertainty doubled): a derived convention conversion, neither the paper's native target nor a fresh blind
  reproduction (the external audit's A11). Found by computing the held-out entry at the owner's request (the G12 closure record), so
  that entry is not blind after G12.

**Benchmark inputs for the intake (2026-10-15).** Where the paper leaves a value free and the reference fixes it,
the target's `at` now says so ("chosen by the zoo"): the complex triplet's splitting couplings y₀ = y₊ = 0;
Pospelov et al.'s κ = 10⁻⁶ (with m_ψ, α′ and m_V); D'Agnolo et al.'s ε = 10⁻⁵; Berlin et al.'s cos θ_W = 0.8768
(MS-bar); Ipek et al.'s tan β, sin 2θ, y_χ and m_A. The harness also passes each entry's `dropped` terms ("left out
by the reference") and a thermal-splitting target's stated splitting.

## An entry

`adroit/evaluation/data/model_zoo.yaml`, read by `adroit/evaluation/zoo.py`. The file was built from the research
agent's 31 candidates; each typed model was written from the paper's Lagrangian.

| key | content |
|---|---|
| `id`, `title`, `category`, `in_library` | identity; `in_library` marks a control |
| `library` | the standard-library portal entry that is this model (library route), if any |
| `reference`, `lagrangian` | the paper, and its Lagrangian as printed (equation, page), for the language-model intake path (G10) |
| `needs` | the capabilities the model needs: `ewsb_mixing`, `sommerfeld`, `coannihilation`, `annihilation_to_mediators`, … |
| `spec` | the model as ADROIT's typed data (fields with charges and parities, couplings, terms) at its first benchmark |
| `targets` | one per published number; the fields are listed below |
| `notes` | the survey's notes on the source, then the conventions chosen here |

Each target has:
- `quantity`, `value` and `uncertainty`;
- `at`: the paper's parameter values;
- `overrides`: field masses and couplings for this benchmark;
- `point`: the library route's engine parameters;
- `engine_options`: the switches that set the physics the authors included;
- `omega_target`, `mediator_ratio`;
- `source` and `tool`.

## Running it

```
uv run adroit eval model_zoo                                   # the development half, to runs/eval/model_zoo.jsonl
uv run adroit eval model_zoo --held-out --reason "G4: the generic engine and the relic density"   # ledgered
```

## The counting of particle and antiparticle, checked (2026-10-16, after D31)

D31 found that Feng et al.'s relic formula counts one species of a complex scalar. Every other entry whose dark matter
field is not self-conjugate was checked against its paper's own counting, by reading (no target was computed; the
ratios are the results already recorded, G12's held-out run and the development half at 7e31dad). A counting
mismatch would show as one factor across a paper's targets: 2 in Ωh², √2 in a thermal mass.

| entry | half | the dark matter | the target from | the counting | ADROIT / paper |
|---|---|---|---|---|---|
| `inert_doublet_kalinowski` | held out | H⁰, a real scalar | micrOMEGAs 4.3.5 | self-conjugate: none to check | 0.92, 1.00 |
| `singlet_doublet_majorana_cohen` | held out | a Majorana mass eigenstate | micrOMEGAs 2.4 | self-conjugate | 0.97 |
| `doublet_triplet_fermion_dedes` | development | "the lightest Majorana particle χ⁰" | the authors' tree level | self-conjugate | 1.13, 1.31 (off-shell W and Z; ADROIT agrees with MadDM) |
| `two_hdm_pseudoscalar_singlet_mediator_ipek` | held out | Dirac | eq. (28), "the velocity averaged annihilation cross section for χ̄χ → SM" | the target is the per-pair σv, as ADROIT's; the paper's "thermal relic" 3 × 10⁻²⁶ cm³/s is the self-conjugate value (a Dirac fermion's is about 4.4 × 10⁻²⁶), but it is not the target | not compared |
| `secluded_dirac_vector_pospelov` | held out | Dirac | analytic, eqs. (6)–(8) | correct: "⟨σv⟩ = ½ σv\|₊₋", the average over +−, ++ and −− collisions; the σv target is that average, half the ψψ̄ rate (already in the entry's notes) | thermal mass 1.07 |
| `secluded_dirac_vector_pospelov`'s σv | | | | σv targets are not yet compared by the harness; a comparison must take ½σv(ψψ̄) | |
| `dark_qed_bound_states_vonharling` | held out | Dirac | the authors' coupled Boltzmann equations | correct: eq. (4.1) for Y_X alone, and eq. (4.9) "Ω_X = 2mY_X s₀/ρ_c, where the factor of 2 accounts for the sum of X and X̄" | 0.87 (not counting) |
| `lmu_minus_ltau_dirac_resonance_holst` | held out | Dirac | the authors' Boltzmann solver | correct: eq. (7) for n ≡ n_χ + n_χ̄ with −½⟨σv⟩(n² − n_eq²) | 0.25, 0.97 (not counting) |
| `forbidden_dark_photon_dagnolo` | held out | "a Dirac fermion, ψ" | micrOMEGAs v4; eq. (2) per species | correct | 1.00, 1.02, 2.47 in the splitting (not counting: a factor 2 in Ωh² moves the splitting by about ln 2/2x_f ≈ 0.02) |
| `dirac_fermion_higgs_portal_eft_cpv_gambit` | development | Dirac | DarkSUSY in GAMBIT's DarkBit | correct: "In the case of non-self-conjugate DM, the right hand side of Eq. (11) is divided by two." | 1.02, 1.04 |
| `dmwg_dirac_vector_zprime_v1` | held out | Dirac | MadDM 2.0.6 (Fig. 2) | MadDM's, matching ADROIT's; the paper's analytic eq. (3.9) takes the self-conjugate thermal value, 2.2 × 10⁻²⁶ cm³/s, but is not the target | 1.00, 1.00 |
| `singlet_doublet_dirac_yaguna` | development | Dirac | micrOMEGAs | micrOMEGAs's (particle and antiparticle) | 0.97, 0.89 in the splitting |
| `singlet_fermion_scalar_mediator_das` | development | "a singlet Dirac fermion" | micrOMEGAs 6.0 | micrOMEGAs's | 1.01 at BP8; 1.82 and 1.30 at BP2 and BP9 (not counting: the same code agrees at BP8) |
| `higgsino_dirac_doublet_bottaro`, `complex_scalar_triplet_y1_bottaro` | held out, development | a Dirac doublet; a complex scalar triplet | the authors' own code with the Sommerfeld effect and bound states | not stated in arXiv:2205.04486 (its details are in the authors' earlier paper on real WIMPs); the doublet's 1.08 TeV is the standard pure-higgsino thermal mass | 1.03, 1.07 |

**Result: no other entry counts one species.** Feng et al.'s two entries (D31) were the only ones; no other target
changes. The Ωh² misses of D'Agnolo et al., von Harling & Petraki, Holst et al. and Das et al. are not this effect.

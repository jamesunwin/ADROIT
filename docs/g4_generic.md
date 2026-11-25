# G4 — The generic engine and the relic density (2026-10-14)

Milestone G4 of [`freeze_out_build.md`](freeze_out_build.md), and the first zoo gate. A typed model the library does
not cover now gets Ωh² from its own Feynman rules, with its route recorded. The library's engines stay first: the
generic route is the fallback and the cross-check (the owner's layering principle).

## What was built

**`GenericModel`** (`adroit/parameter_space/portals/generic.py`), a `Portal` with `family = "generic"`. At each point
the model is rebuilt: the scanned parameter is set (m_χ, and a tied mediator mass), then G1's spectrum, G2's rules and
G3's tree engine.
- **The bath:** the dark matter and every Z₂-odd state below 1.3 m_χ; a particle and its antiparticle are two
  species.
- **Each pair's σ_ij(s):** summed over every Z₂-even final pair with at least one tree diagram and conserved charge.
  σβ is tabulated in u = √s/(m_i + m_j) − 1, with nodes added around each s-channel pole, and interpolated.
- **Ωh²:** `relic.omega_h2_species`, Edsjö–Gondolo with the Gondolo–Gelmini average. Forbidden channels come from the
  thermal tail.
- **Final W and Z off shell** near and below threshold: `ufo.off_shell_sigma`, as `UFOPortal` does.
- **The SM-like h's width:** its H⁰ share of the SM width at its mass (off-shell W*, Z*, gluons and photons
  included), plus its decays into new states.
- **`invisible`:** Γ(h → DM DM̄) and Γ(Z → DM DM̄) where they are open.
- **Not computed yet:** direct detection (G5), annihilation today (G6), the LHC (G9). Each is `pending` at every
  point, so a verdict is pending, never viable, and no search is passed by an empty rate.

**Its place in the product.** `GenericModel` is in `scan.ModelClass`. `classify(spec, generic_route=True)` reaches
it last: only where the portal maps and the simplified classes both refuse, and only if G1 and G2 can build the
model; otherwise the library's refusal stands, with the generic route's reason added. Its notes keep the library's
refusal. The zoo routes typed → library → generic.

**Off by default until G12** (a deviation from the plan, which put the route in `classify` unconditionally). With
it on, a study of any model the library refuses becomes a scan of the generic engine, at 1–25 s a point, whose
direct detection, annihilation today and LHC verdicts are all pending until G5, G6 and G9. 26 tests encode the
refusals (the simplified maps that must not misread an input; Track 1 and DM14 calling an unsupported model
undetermined), and their intent still holds for the library's maps. G12 integrates the route into the product
flows and turns it on.

**On by default since 2026-10-15** (the owner's decision D27, ahead of G12). `classify` reaches the generic route
unless a caller passes `generic_route=False`; the simplified maps, the completions offered for a paper's model and
DM13's refusal check pass it, since they ask what the library alone computes. Where a typed or library engine
refuses a model by its domain (a mass, an n, a Y outside what it validates), the generic route computes it: in the
zoo per target (`zoo.computed_by`, whose route then reads "generic (fallback: …)"), and in a scan per point when
both axes are masses (`ScanRequest.fallback_class`; the points so computed are flagged). Each result names the
route that produced it.

## Long-range effects (decision D4)

**The criterion is the bracket itself** (`generic_checks.py`). The bath's pairs, grouped by the multiplets they come
from, go to G4's Sommerfeld bracket (`docs/g4_bracket.md`) with their representations and the forces they feel:
- SU(2), exchanged with m_W, and U(1)_Y, massless (electromagnetism for a broken-phase singlet with a charge);
- SU(3), massless;
- a new boson that couples a state to itself, with α = |c|²/4π. A vector attracts a particle–antiparticle pair and
  repels two particles; a scalar attracts every pair.

Where the bracket's centre moves Ωh² by more than 10% from the perturbative value, Ωh² is refused, and the reason
names α_eff, the perturbative value and the bracket.

**Why not the planned screen.** The plan's screen (α_eff μ ≳ m_V or α_eff/v ≳ 0.1) misses the wino. The library's
n-plet engine shows the Sommerfeld effect is large well below α_eff μ = m_W, because the Hulthén factor saturates at
2π²α_eff m/(κ m_V), about 11 α_eff m/m_V:

| m (TeV) | wino: Ωh²(Sommerfeld)/Ωh²(perturbative), library | screen | bracket criterion | higgsino: same ratio | bracket criterion |
|---|---|---|---|---|---|
| 0.5 | 0.766 | computed | refused | 0.999 | computed |
| 1.0 | 0.686 | computed | refused | 1.003 | computed |
| 1.5 | 0.640 | computed | refused | 1.003 | computed |
| 2.0 | 0.591 | computed | refused | 1.003 | computed |
| 2.5 | 0.605 | refused | refused | 1.002 | computed |
| 3.0 | 0.605 | refused | refused | 1.001 | computed |

The bracket's centre is a rough number (5–40% low in thermal mass, `docs/g4_bracket.md`), so as a criterion it errs
towards computing. On the two cases above it is right everywhere. At 1 TeV the wino's bracket, 0.0092–0.0325,
holds the library's Sommerfeld-only Ωh², 0.0155.

**The estimate on request** (`long_range = "estimate"`). Ωh² stays refused for every verdict. The point's flags gain
the perturbative Ωh², the bracket's edges, its rough centre, the bound-state caveat and `long_range_bracket.WARNING`.
So the estimate can be read but can never reach a verdict. Where Ωh² is computed but the bracket's edges still
spread by more than 10%, the same flag is given as information.

`sommerfeld = False` computes the perturbative value: an author's own perturbative treatment, which the zoo
compares with.

## Certificates (`flags`)

- **Chemical equilibrium of the bath.** Each coannihilator must convert to the dark matter faster than 10 H at
  x_f, by two-body decays or by scattering on the light Standard Model bath (G3's processes, n_f⟨σv⟩ at E_f = 3T).
  The wino's χ± converts by W exchange, far faster. De Simone et al.'s coloured partner, with no stated coupling to
  χ, is flagged: nothing converts it.
- **Kinetic contact.** Each new Z₂-even final state must decay to the Standard Model faster than H at x_f.
- **g\*.** New states lighter than T_f would add to g\*. They are flagged, not added: Ωh² uses the Standard Model's
  g\*.

## Fixes found on the way

| what | where | effect |
|---|---|---|
| The strong vertices of triplets had +g_s; the engine's gauge-consistent set is −g_s with its default colour structures | G2, `feynman.gluon_vertices` | φφ* → gg was right at threshold and off by 2 at √s = 5.7 m_φ; now equal to the hand-written amplitude at all energies |
| The photon's mass came out 5×10⁻⁷ GeV (eigenvalue rounding), and the tree engine gave it a longitudinal state ∝ 1/m | G1, `spectrum.vector_states` | χ⁺χ⁻ → γγ was 10¹⁰ GeV⁻², and Ωh² was 10⁹. Masses within eigh's rounding are now exactly zero |
| The tree engine does not raise for a fermion pair with no diagram | G4, `final_states` | χ⁰χ⁰ → e μ̄ and → γg were admitted as final states (with zero rate). Now a final state needs a diagram |
| Setting a parameter to its stated value raised "not a field" | G4, `generic._set` | a point at the benchmark itself failed |
| New particles were numbered from 9000001; MadDM takes 9000001–9000004 for FeynRules' ghosts and leaves them out of its Z₂ assignment | G2, `ufo_export.PDG_START` | MadDM refused χ± as coannihilators without stopping, and gave Ωh² = 0.0326 from χ⁰χ⁰ alone. Now numbered from 9000101 |
| New particles had capitals in their names; MadGraph lower-cases a model's names on import | G2, `ufo_export.names` | MadDM could not find Choubey et al.'s dark matter (`Np0`), and dropped Bhattacharya et al.'s partners. Names are now lower case and distinct |
| The export listed each vertex's legs as ADROIT's annihilated particles; a UFO vertex lists the particles its fields create (the reader's convention, checked against MadGraph at G3) | G2, `ufo_export._created` | for a vertex joining two species (a partner's Yukawa) the UFO held its conjugate with the chirality swapped: S Ψ⁺ → Z ē came back 39 times larger. Particle–antiparticle vertices read the same either way, so every gauge vertex had round-tripped |
| The colour indices were placed by the conjugated particles' representations | G2, `ufo_export._vertex_files` | φφ* → gg lost its gauge cancellation in the UFO (×2.2 at high energy). They now follow ADROIT's representations, moved with the legs |
| A Dirac partner can carry the opposite fermion number to the SM fermion it couples to (G1 calls the positive state the particle) | G2, `ufo_export.flipped` | MadGraph needs every fermion vertex to pair an antiparticle with a particle; such a partner is now written with its antiparticle as the UFO particle (…bar), and a model that violates fermion number is refused |
| A narrow pole was tabulated on 13 nodes and interpolated linearly | G4, `generic._nodes`, `_interpolated` | the chord over a Breit–Wigner's tails overestimates its area: Choubey et al.'s BP1 (Δ⁰, Γ/M = 10⁻⁴) came out 8% low in Ωh² against a converged reference (0.0749 against 0.0815). Now 39 nodes per pole the thermal average reaches, log(σβ) interpolated, and only poles with the pair's charge: 0.0818 |
| A broken-phase model with no scalar fields of its own (a colour-octet partner) took the maximum of an empty Hessian | G1, `spectrum` | it could not be built. (Found when a check script built the held-out octet entry's model by mistake; no target of it was computed, and the fix was made and tested on an independent spec) |

## Cross-checks

| check | result |
|---|---|
| The wino at 1 TeV, perturbative: generic against the library's n-plet engine | 0.0226 against 0.0230 (−1.5%; the library adds the 165 MeV radiative splitting) |
| The same against MadDM on the exported UFO, χ± as coannihilators | 0.0226 against 0.0237 (−4.7%, within G4's 10%) |
| Coloured scalar partner with a quark Yukawa: φφ* → gg, φφ* → uū, χφ → ug, χχ → uū, φφ → uu | equal to the hand-written amplitudes (10⁻⁷ near threshold) |
| A Majorana colour octet | χχ → gg and (without squarks) χχ → uū equal MadGraph's gluino |
| Γ(t → W⁺b) from the new fermion widths | the closed form, to 10⁻⁶ |
| The export read back through MadGraph's own loader (`ufo_model.dump`) | every bath pair's every channel equal to 10⁻¹⁵, for the wino, Bhattacharya, Choubey, Dedes, Giacchino, Feng, Das and a coloured partner |
| MadGraph's own σ(S Ψ⁺ → γ e⁺) at √s = 500 GeV from the exported Giacchino model | 5.502 ± 0.006 pb against 5.498 pb |

### MadDM on the new models (D3)

MadDM 3.3 ran on each exported model with its coannihilators:

| target | published | generic | MadDM | MadDM/generic |
|---|---|---|---|---|
| wino, 1 TeV, perturbative | — | 0.0226 | 0.0237 | 1.05 |
| Bhattacharya et al. BP4 | 0.104 | 0.585 | 0.636 | 1.09 |
| Bhattacharya et al. BP3 | 0.11 | 3.43 | 3.30 | 0.96 |
| Dedes & Karamitros, t0 | 0.12 | 0.134 | 0.132 | 0.98 |
| Dedes & Karamitros, t1 | 0.12 | 0.156 | 0.152 | 0.97 |
| Giacchino et al., scalar | 0.11 | 0.124 | 0.109 | 0.88 |
| Choubey et al. BP1 | 0.121 | 0.082 | 0.059 | 0.72 |
| Choubey et al. BP3 | 0.120 | 0.122 | 1.03 | 8.5 |

- **Within 10%:** five of eight. For Bhattacharya et al. and Dedes & Karamitros, MadDM reproduces the generic
  route, so their misses against the papers lie in the inputs, not the engine (below).
- **Giacchino et al. (12%).** The matrix elements are MadGraph's (the row above). MadDM's quoted ⟨σv⟩ at its x_f
  is about 15% above ours if it quotes half the effective rate for self-conjugate dark matter, as its Ωh² implies.
  It also lists ΨΨ̄ → SS, a conversion, among its channels. The difference is in the thermal average and its
  bookkeeping. The paper's micrOMEGAs value, 0.11, is 13% below ours too: this stays open.
- **Choubey et al.** Both benchmarks are set by narrow resonances of the triplet scalar Δ:
  - BP3 through Δ⁺ (Γ/M = 1.3×10⁻³) in χ⁰ρ± → W h, Z W, 18 GeV above that pair's threshold;
  - BP1 through the thermal tail into Δ⁰ (Γ/M = 9×10⁻⁵), 11% above the χ⁰χ⁰ threshold.

  At BP3 the paper's own micrOMEGAs agrees with the generic route (0.120 against 0.122), and MadDM is ×9 higher with
  any integration grid: it does not resolve a narrow resonance inside a coannihilation channel. At BP1, Ωh² ∝
  1/Γ(Δ⁰ → SM) ≈ 1/Γ(Δ⁰ → WW, ZZ) ∝ 1/v_Δ², since Δ⁰ → χ⁰χ⁰ dominates its width. MadDM is 28% below the generic route,
  close to the narrow tail's sensitivity; the paper's value is 1.48 times ours, which a 22% difference in v_Δ (the
  entry's v_Δ = v tan δ/2) would give.
- **What else this check found.** Four errors in the export: the ghost-range PDG codes, the capitals, the conjugate
  listing and the colour indices (the table of fixes above).

## The zoo (development half, 2026-10-14)

`uv run adroit eval model_zoo` at 21d6b48 with the pole resolution above (`runs/eval/model_zoo.jsonl`).

**The new models: 4 of 6 computed (all by the generic route), 3 of 7 targets met.**

| model | target | published | generic | met | MadDM | reading |
|---|---|---|---|---|---|---|
| Bhattacharya et al. | Ωh² BP4 | 0.104 | 0.585 | no | 0.636 | MadDM reproduces the generic route: the gap is in the inputs (the entry flags the paper's v = 174 GeV against its Table I), not settled |
| | Ωh² BP3 | 0.11 | 3.43 | no | 3.30 | as above |
| Choubey et al. | Ωh² BP1 | 0.121 | 0.082 | no | 0.059 | the tail into Δ⁰ (Γ/M = 10⁻⁴): Ωh² ∝ 1/v_Δ², a 1.5 in Ωh² is 22% in v_Δ |
| | Ωh² BP3 | 0.120 | 0.122 | yes | 1.03 | the Δ⁺ pole in χ⁰ρ± coannihilation; MadDM does not resolve it |
| Dedes & Karamitros | Ωh² t0 | 0.12 | 0.135 | yes | 0.132 | |
| | Ωh² t1 | 0.12 | 0.157 | no (+31%) | 0.152 | MadDM reproduces the generic route: in the inputs, not settled |
| Giacchino et al., scalar | Ωh² | 0.11 | 0.124 | yes (+13%) | 0.109 | |
| complex scalar triplet | M (TeV) | 2.1 | refused | | | needs the Sommerfeld effect (G7), as planned |
| Feng & Smolinsky | Ωh² ×2 | 0.12 | refused | | | α_X = 0.5 with m_A′ = 3m_X: the bracket's centre moves Ωh² by 42% (the Hulthén factor is 1.4–1.9 here). The paper's Ωh² is perturbative. Whether to record that treatment on the entry (`sommerfeld: false`) is the owner's call: it was noticed after the refusal |

The plan expected five of six computed. The fifth, Feng & Smolinsky, is refused by the long-range criterion, which
the plan's screen would have let through.

**The controls: 6 of 6 computed by their library engines, 11 of 15 targets met (as at G0). The generic route beside
them agrees on 7 of 9 targets within tolerance:**
- **Agreeing:**
  - the Dirac Higgs-portal EFT: −1.4%, −1.9%;
  - De Simone et al. and Harz & Petraki, perturbative: −0.8%, −0.9% in thermal mass;
  - the vector Higgs portal: −15% on the Higgs pole's tail;
  - Das et al. BP8: +3.9%.
- **The two disagreements are the library's errors:** Das et al. BP2 and BP9. The generic route gives 0.121 and
  0.120 against the published 0.119 and 0.119; the library gives 0.217 and 0.155. The library's singlet-mixing
  engine drops the scalar trilinear couplings, and the generic route keeps them. This confirms G0's suspected cause.
- **Refused correctly:** the wino's targets, and the Sommerfeld-dependent coloured targets.

**The gate:**
- **The development half:**
  - Every new model expected in scope is computed, except Feng & Smolinsky (above).
  - Every computed target is met, or its miss is localised by MadDM to the model's inputs (Bhattacharya et al.,
    Dedes & Karamitros t1) or to a narrow resonance's width (Choubey et al. BP1).
  - Two misses are localised, not explained: Bhattacharya et al.'s and Dedes & Karamitros's t1. They are carried as
    open.
- **The controls:** within tolerance where the library is right.
- **MadDM:** within 10% on 5 of 8 targets; the other three are explained above.

On that basis the held-out half was run once (below).

## The held-out half (once, 2026-10-14, commit 4a410e2; ledgered)

`adroit eval model_zoo --held-out --reason "G4: …"`; results in `docs/dm10/results/model_zoo.jsonl`.

**New models: 4 of 11 computed; 4 of 5 compared targets met.**

| model | target | published | computed | met |
|---|---|---|---|---|
| Cohen et al., singlet–doublet Majorana | M (GeV) | 1100 | 1067 (generic) | yes |
| De Simone et al., colour-octet fermion | M (TeV), perturbative | 3.7 | 3.86 (generic) | yes |
| | M (TeV), Sommerfeld | 7.5 | refused: needs G7 | |
| D'Agnolo et al., forbidden dark photon | Δ, three points | 0.309; 0.101; 0.651 | 0.310; 0.103; 1.85 (generic) | yes; yes; **no** |
| Giacchino et al., Majorana with a lepton partner | Ωh² | 0.10 | the t-channel engine's domain (m_φ ≳ 200 GeV) | |

**Refused:**
- **for want of the Sommerfeld effect (G7):** the scalar 5-plet; Feng & Smolinsky's resonance model (α_X = 0.5);
  von Harling & Petraki's dark QED; Pospelov et al.'s secluded model (α = 0.01 with a light mediator moves Ωh² by
  15%);
- **at build:**
  - Kamon et al.'s vector dark matter: its mass comes from the dark Higgs's vacuum value, and the entry names no
    scanned parameter;
  - Ipek et al.'s 2HDM+a: a coupling without a value;
  - Okada et al.'s B−L: G1 counts a U(1) charge of 2 on a Majorana field's axial current (N̄γ^μγ⁵N Z′). That is G1's
    error, carried to G7.

**Controls: all 8 computed by their engines, 9 of 14 targets met. The generic route agrees on 11 of 12 targets:**
- the inert doublet: +11% and +0.6%;
- the higgsino: −0.2%;
- the DMWG Z′: exact;
- the Majorana Higgs-portal EFT on its resonance: −17%;
- Berlin et al.: +1.7%, +1.9%;
- L_μ − L_τ: −2.4%, −0.5%;
- the GAMBIT scalar singlet: −0.6%, and **−22% on the Higgs pole** (beyond 20%).

The quintuplet's targets are refused, correctly.

**A disclosure.** Before this run, a check script built the held-out colour-octet entry's model (its build failed;
no target was computed). The fix to G1 that this exposed was made and tested on an independent spec, but this
entry's perturbative target, met above, is therefore not wholly blind.

**What G7 and G12 inherit from the held-out half:**
- G1's axial current of a charged Majorana field;
- the scan parameter of a model whose dark matter takes its mass from a vacuum value;
- D'Agnolo et al.'s third splitting;
- the singlet's Higgs-pole value.

## Cost

One tabulation per point is shared by Ωh², the bracket and the certificates, and the SM Higgs width is cached.
Each tabulated σ uses 16 Gauss points in cos θ (as `UFOPortal`; the values move by 10⁻⁵).
- **Simple models:** 1–3 s per point (the wino 1.6 s, Giacchino et al. 1.0 s).
- **Many final states and narrow poles:** 8–25 s (Dedes & Karamitros 14 s, Choubey et al. 8–23 s). Nearly all of it
  is the tree engine's cross-sections at the pole nodes.

A thermal mass takes 15–20 points. Refining the poles only for the final states that carry the rate would cut the
slow cases several-fold; it is left for G12.

## Limits

- Three-body final states other than W* and Z* are not computed. Where a final pair with a t or an h opens within
  25% above 2m_χ, the point is flagged.
- Light new states are flagged, not added to g\*.
- The long-range criterion inherits the bracket's approximations: the symmetric limit, no resonances of a massive
  mediator, no bound states.
- The conversion rate is an estimate (one energy per light species); it certifies, it does not enter Ωh².

Tests: `tests/parameter_space/test_generic.py`, `tests/model_building/test_ufo_export.py` (the MadDM round trip is
`slow`), and additions to `test_feynman.py` and `test_spectrum.py`.

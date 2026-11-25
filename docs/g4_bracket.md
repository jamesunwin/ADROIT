# G4: the Sommerfeld bracket (decision D4)

**What it is for.** Long-range forces can matter where no module computes them (G7 builds that module). By default
ADROIT then refuses Ωh². On request it gives the perturbative Ωh² with a warning and this bracket: a cheap estimate
from group theory of how far the Sommerfeld effect could move the result. It never reaches a verdict. Code:
`adroit/constraints/long_range_bracket.py`. Calibration: `docs/g4/bracket_calibration.py`, with its output in
`docs/g4/bracket_calibration.json`.

## The physics

**The potential.** For two dark states in representations R₁ and R₂, the symmetric-limit potential is diagonal in the
irreducible representations R of R₁ ⊗ R₂, with Coulomb strength

    α_eff(R) = α [C₂(R₁) + C₂(R₂) − C₂(R)]/2   (non-abelian),     −α q₁q₂   (abelian),

added group by group. This reproduces the n-plet engine's α₂(2n² − 1 − I²)/8 + Y²α_Y exactly, and
`sommerfeld.COLOUR`'s 4/3, −1/6, 2/3 and −1/3 (tests).

**The factor of one channel.**
- **Massless mediator:** Coulomb, S = X/(1 − e^{−X}) with X = 2πα/v.
- **Massive mediator:** Hulthén (κ = 1.74), with its resonance phase frozen at π/2 beyond the first quarter period.
  This removes the zero-energy resonances, saturates off resonance at 2π²αm/κm_V, and gives S → 1 once the Bohr
  momentum αμ falls below m_V. It is exact for a repulsive channel. It is Maxwell–Boltzmann averaged at T = m/x.

**The bracket.** If a pair's hard rate is shared among its channels with fractions f_R ≥ 0, its enhanced rate
Σ_R f_R S_R σv lies between min_R S_R σv and max_R S_R σv. Pair by pair, the Boltzmann equation (`relic.freeze_out`)
is re-solved with:
- each pair's rate × its most attractive channel's ⟨S⟩: low Ωh², the high thermal mass;
- × its least attractive channel's ⟨S⟩: high Ωh², the low thermal mass;
- × a central weighting.

**The central weighting has three versions:**
1. **State counting** (as first fixed): w_R = dim R/(dim R₁ dim R₂).
2. **The selection rule** `final_su2_max = 5` (added after the first 5-plet results; no free constant). Two Standard
   Model particles carry SU(2) dimension at most 5 (W ⊗ W), so a pair annihilates into them at tree level only from
   channels with I ≤ 5. The others carry no hard rate and are dropped from all three edges. This changes only n ≥ 4.
3. **Hard shares:** the hard rate's own channel shares, where an engine knows them (`PairRate.shares`). This is a
   check of the factor; the generic engine will know them only after G7.

**Conventions of the calibration, fixed before it ran:**
- α at the Bohr momentum λα(q)μ of the most attractive channel, solved self-consistently;
- SU(2)'s mediator m_W; U(1)_Y's and SU(3)'s massless;
- no Debye masses;
- Ωh² = 0.11933 throughout.

## Calibration (thermal masses in TeV, Ωh² = 0.11933)

| model | α_max / α_min | perturbative | bracket: high-Ω · central · low-Ω | with I ≤ 5 | central (hard shares) | ADROIT Sommerfeld only | ADROIT full | published (full; Sommerfeld only; tree) |
|---|---|---|---|---|---|---|---|---|
| wino | 0.0696 / -0.0348 | 2.33 | 1.89 · 2.57 · 3.80 | 1.89 · 2.57 · 3.80 | 3.00 | 3.02 | 3.06 | 2.86 ± 0.01 (Bottaro et al.); 2.88 (Beneke et al.); 2.22 (Beneke et al.) |
| higgsino | 0.0293 / -0.0065 | 1.11 | 1.07 · 1.15 · 1.37 | 1.07 · 1.15 · 1.37 | 1.11 | 1.11 | 1.11 | 1.08 ± 0.02 (Bottaro et al.); ≈ 1.1 (Cirelli et al.);  |
| quintuplet | 0.2028 / -0.1352 | 4.23 | 1.97 · 6.07 · 11.03 | 8.09 · 9.17 · 11.03 | 9.60 | 9.65 | 15.52 | 13.6 ± 0.8 (Bottaro et al.); 9.3 (Mitridate et al.); 4.4 (Cirelli et al.) |
| quintuplet_dirac | 0.2140 / -0.1258 | 3.09 | 1.53 · 4.65 · 8.34 | 6.20 · 6.99 · 8.34 | 7.33 | 7.40 | 10.69 | 9.9 ± 0.7 (Bottaro et al.); ;  |
| coloured_triplet | 0.1547 / -0.0387 | 1.33 | 1.15 · 1.47 · 2.77 | 1.15 · 1.47 · 2.77 | 1.83 | 1.82 | 3.24 | 3.3 (Harz & Petraki, band 3.16–3.31); 1.7 (De Simone et al.); 1.865 (Harz & Petraki); 1.3 (De Simone et al.); 1.33 (Harz & Petraki) |

The bracket columns list high-Ω · central · low-Ω, so they read from the smallest thermal mass to the largest.

## Verdict

**The bracket holds where it claims to.** In all five cases it contains ADROIT's own Sommerfeld-only thermal mass,
with or without the selection rule. It also contains every published Sommerfeld-only value: Beneke et al.'s 2.88 TeV
wino, Mitridate et al.'s 9.3 TeV 5-plet, and De Simone et al.'s 1.7 and Harz & Petraki's 1.865 TeV coloured triplet.

**Bound states fall outside it, as stated.** With bound-state formation the full thermal mass stays inside the
bracket for the wino and the higgsino, whose bound states are small effects. It lies above the bracket's top edge
where they are large:

| model | full mass above the top edge (ADROIT) | (published) |
|---|---|---|
| 5₀ | +41% | +23%, Bottaro et al. |
| 5₁ | +28% | +19% |
| coloured triplet | +17% | +19%, Harz & Petraki |

So the estimate must say: bound states can raise the thermal mass by up to about 40% beyond the top edge, or lower Ωh²
at a fixed mass by up to about a factor 2.

**The width.** For pairs with both attractive and repulsive channels the bracket is wide: a factor 2.0 in the
wino's thermal mass and 2.4 in the coloured triplet's. The selection rule narrows the 5-plets' bracket to a factor
1.36 (5₀) and 1.35 (5₁), since their repulsive channels carry no hard rate. The higgsino's is narrow, a factor 1.28.

**The centre.**
- **State counting is a poor ballpark.** In thermal mass it is 15% low for the wino, 37% low for the 5-plets and 19%
  low for the coloured triplet: it gives too much weight to the many repulsive states.
- **With the selection rule** it comes within 5–6% for the 5-plets; it does not affect the wino, the higgsino or
  the coloured triplet.
- **With the hard rate's own channel shares** it agrees with the Sommerfeld-only thermal masses to 1% everywhere
  (wino 3.00 against 3.02; 5₀ 9.60 against 9.65; 5₁ 7.33 against 7.40; coloured 1.83 against 1.82). The factor and
  its conventions are sound; what the cheap estimate lacks is the hard rate's split among channels. That split is
  tree-level group theory, the projection of G3's s-wave amplitudes onto the pair's irreducible representations. It
  belongs to G7, but could be built early as a cheap upgrade of the centre.

**Recommendation for G4's estimate:**
- report the perturbative value with the low and high edges, applying the selection rule wherever the final states
  are Standard Model pairs;
- report the state-counting centre only as "rough, typically 5–40% low in thermal mass";
- say that bound states can lie beyond the top edge. In the cases calibrated, by up to about 40% in thermal mass.

In short, the bracket gives the reach of the Sommerfeld effect honestly, but not a precise number. Within a factor
1.3–2.4 in thermal mass it is a useful order-of-magnitude statement, and it should never be read as Ωh².

## What it is not

- **Not a bound:** bound-state formation lowers Ωh² further, and in every case where it matters the full answer lies
  above the bracket's top thermal mass.
- **Not included:**
  - resonances of a massive mediator (removed by the frozen phase);
  - Debye masses;
  - mixing of channels by mass splittings (the broken phase).
- **Never in a verdict:** the estimate carries `long_range_bracket.WARNING`.

## The API that G4's generic engine calls

```python
from adroit.constraints.long_range_bracket import GaugeForce, PairRep, PairRate, bracket, thermal_masses, bohr_alpha

forces = [GaugeForce(group="SU2", alpha=a2, mediator_gev=80.4), GaugeForce(group="U1", name="Y", alpha=ay)]
pairs = [PairRate(pair=PairRep(su2=(n1, n2), su3=(c1, c2), charges={"Y": (y1, y2)}),
                  rate=contribution_on_x_nodes,          # this pair's share of ⟨σ_eff v⟩ (GeV⁻²)
                  final_su2_max=5)]                      # when its final states are Standard Model pairs
result = bracket(species, x_nodes, pairs, forces)        # → Bracket
masses = thermal_masses(lambda m: (species(m), x_nodes, pairs(m), forces(m)), target, guess)
```

The result, `Bracket`, holds:
- `omega_perturbative`, `omega_low`, `omega_central`, `omega_high`;
- `alpha_max`, `alpha_min`, `channels`;
- `warning`.

**What the generic engine must supply:**
- each pair of multiplets' perturbative contribution to ⟨σ_eff v⟩: the per-pair numerator of
  `relic.coannihilation_average`, summed over the pair's components;
- the pair's gauge representations;
- the selection rule's bound, from its final states.

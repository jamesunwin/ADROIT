# General electroweak n-plets

`adroit/parameter_space/portals/nplet.py` (2026-10-13, at the owner's request after their 5-plet model): the relic
density, direct detection and Track 1 scan of a Majorana SU(2) n-plet with Y = 0 or a Dirac one with Y ≠ 0, in the
SU(2)_L × U(1)_Y symmetric limit of Bottaro et al. (arXiv:2107.09688, 2205.04486). It takes the channel rates and
bound states from Mitridate, Redi, Smirnov & Strumia (arXiv:1702.01141). The module's docstring holds every formula
and choice; this page records what was checked and how.

## What the engine computes

- **Annihilation per isospin channel** with its s-wave Sommerfeld factor (Hulthén).
  - The Majorana split reproduces Mitridate et al.'s eqs. (17), (85) and (89) exactly.
  - The Dirac split sums to Cirelli, Strumia & Tamburini's eq. (39) (a test). The split itself is not published.
- **Bound-state formation** into the 1s and 2s states of every attractive channel.
  - W emission between I and I ± 2. The group factor Σ|C_J + γC_T|² = (I+1)(4n² − (I+1)²)/32 · (1 ∓ (I+1)γ/2)² was
    derived for this work and checked against Mitridate et al.'s eq. (48), computed directly, for every transition
    with n = 2–7 (a test).
  - B emission within a channel, for Dirac n-plets.
  - Below T_c: the Hulthén state, and massive-vector emission.
  - Ionisation by detailed balance, with widths ½|ψ(0)|²σ(I,S)g_χ²/I(2S+1). These reproduce Mitridate et al.'s
    3240, 15625/48, 567/4 and 8 α₂⁵M (a test).
- **Direct detection** at one loop (Bottaro et al. eqs. (17)–(18)), with an amplitude uncertainty.
- **Model mapping:** one Majorana field (Y = 0), one Dirac field (Y ≠ 0), or a vectorlike pair of Weyl fields with
  hypercharges Y and −Y. A stated mass coefficient must equal the fields' mass. The wino (3₀) and the higgsino (2₁/₂)
  go to their broken-phase engine.

## Validation

Thermal masses in TeV, for Ωh² = 0.11933, with the Sommerfeld effect and bound states:

| n_Y | ADROIT (α at α₂M) | α at M | α at m_Z | Bottaro et al. |
|---|---|---|---|---|
| 3₁ (Dirac) | 2.67 | 2.62 | 2.67 | 2.85 ± 0.14 |
| 4₁/₂ (Dirac) | 4.50 | 4.35 | 4.52 | 4.8 ± 0.3 |
| 5₀ (Majorana) | 15.5 | 13.5 | 16.3 | 13.6 ± 0.8 |
| 5₁ (Dirac) | 10.7 | 9.56 | 11.5 | 9.9 ± 0.7 |
| 7₀ (Majorana; not in the domain) | 43.3 | 40.3 | 46.1 | 48.8 ± 3.3 |

- **The coupling scale.** Mitridate et al. evaluate α at the inverse Bohr radius α₂M in the potentials. Bottaro et al.
  do not say. The choice moves the 5-plets by ±9%; that is the engine's theory uncertainty.
- **The 3₁ and 4₁/₂.** Bottaro et al. compute their Sommerfeld effect in the broken phase, so they come out 6–9% low
  here at any scale.
- **Sommerfeld effect alone (Majorana):** 9.65 and 22.1 TeV for n = 5 and 7, against Bottaro et al.'s Fig. 1 values of
  9.33 and 22.2 (digitised).
- **Born rates:** 5–7% above their dashed curve, and on the standard ⟨σv⟩ = 2.2 × 10⁻²⁶ cm³/s.

**Not validated, so outside the domain:**
- **n ≥ 6.** The bound states of channels I ≥ 7 reach the Standard Model only through chains of transitions, which
  are not computed. The 6₁/₂ comes out 18 TeV against their 31.8.
- **Y > 1.**
- **M < 1 TeV.**

**Direct detection.** ADROIT's σ_SI for the wino is 2.3 × 10⁻⁴⁷ cm², Hisano et al.'s value. It is 2.0–2.5 times
Bottaro et al.'s at Y = 0, and up to 6 times at the 5₁. There the Z and W loops partly cancel: the cancellation
coefficient ξ comes out 12.2 here against their 16.6. The amplitude uncertainty is 0.5 for Y = 0 and 1.0 for Y ≠ 0.

## Not computed

- **Annihilation today** (γ rays, lines, the CMB, antiprotons, the Sun). At v ≈ 10⁻³ it needs the broken-phase
  Sommerfeld effect with its resonances. Every search that uses it is undecided, with that reason, never allowed.
  (`today_unknown`; the same hook now serves any model class.)
- **Z-mediated inelastic scattering** of a Dirac n-plet whose δm₀ is below xenon's 450 keV reach: undecided.
- **2p states** (Mitridate et al.'s eq. (53) carries a factor not verified here), **excited-state chains**, the
  **LHC**.

## In Track 1

The standard library has the 5₀ (`quintuplet`) and the 5₁ (`quintuplet_dirac`). A 3 × 2 scan of the 5₁ finds its
thermal solution at 10.75 TeV (Ωh² = 0.12) and reaches *viable-pending*. Indirect detection, Z-mediated scattering
for δm₀ < 450 keV, and SI direct detection above the modules' validated range are pending.

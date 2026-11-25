# G7 — Long-range effects in the early universe for a generic model (2026-10-15)

Milestone G7 of [`freeze_out_build.md`](freeze_out_build.md), the second zoo gate. A typed model's Sommerfeld
effect and bound-state formation now come from its own gauge representations and mediators. G4 refused such models
(decision D4); the generic route now computes them.

## What was built

**Everything model-specific comes from G3.** `adroit/parameter_space/portals/generic_lr.py` groups the bath's states
into multiplets, by the field each is made of (at least 99%). A self-conjugate field is one multiplet; a complex one
is two (particles, antiparticles). Each pair of multiplets that a long-range force joins is a group. Its two-particle
states are the ordered pairs (a, b), with their colours and spins.

**The potential.** The model is copied with every Z₂-odd state at 10⁶ GeV and no widths: the symmetric limit, where
the W and Z masses drop out. In the copy, G3 computes the elastic amplitudes (a, b) → (a′, b′) at two momentum
transfers q ≪ p ≪ M (`Process.amplitudes`, new: every colour and spin explicit). The Born amplitude is
M = 16πM²α_eff/q² + O(q⁰), so the coefficient of 1/q² is read off exactly. For two fermions the engine's M carries
one more sign, that of the permutation of the two fermion lines. The coefficient, spin-diagonal and spin-averaged, is
a matrix α_eff over (pair, colour a, colour b):
- its eigenvectors are the irreducible channels, in the phases of the very amplitudes that annihilate;
- its eigenvalues must be group theory's α[C₂(R₁) + C₂(R₂) − C₂(R)]/2 for SU(2) and SU(3), and −αq₁q₂ for each
  U(1), at G2's couplings. Each cluster of eigenvalues is matched to a channel (I, R), and its number of states
  must be the channel's.

Nothing about the representations is assumed, so a new mediator, a hypercharge, or several groups at once go through
the same calculation.

**The hard rates.** At threshold (v = 10⁻³), G3 builds the annihilation matrix over the same states:

    Γ_kl = Σ_f ∫ M_k M_l* k/(8π s^{3/2}) dcos θ        (½ for identical final particles).

Interference between different charge and colour states is included. A channel's s-wave rate is Tr(P Γ) over its
states. By total spin S (σ/2 per leg; a fermion's label is its spin along z, for u and v = C ūᵀ alike) it also gives
the rates of the channel's bound states. The rates are taken at the hard scale 2m: × (α₂(2m)/α₂^{G2})² for an
electroweak multiplet (G2's couplings are at M_Z), as the library's engines take them. The strong coupling is
already α_s(m).

**The Sommerfeld effect.** Each channel's s-wave rate is multiplied by its thermally averaged factor:
- SU(2): α₂ at the inverse Bohr radius α₂(M)M, Hulthén with the W mass below T_c and the Debye mass above
  (`portals.nplet`, Mitridate et al.);
- U(1)_Y: at the same scale, with SU(2)'s mediator mass where both act, else Coulomb;
- SU(3): α_s at the momentum transfer, not below the Bohr momentum (`portals.tchannel`);
- a new mediator: its own coupling and mass.

The correction Σ_ch (r²⟨S_ch⟩ − 1)σ_ch enters ⟨σ_eff v⟩ through the relic solver's thermal pair rates. The
perturbative rate of every pair stays as G4 tabulates it, and only the group's s-wave part is replaced.

**Bound states** (1s and 2s, in ionisation equilibrium):
- a pure SU(2) multiplet with itself or its antiparticle, of spin 0 or ½: Mitridate et al.'s capture by W and B
  emission (`portals.nplet`'s formulae, now for scalars too), with the (I, S) rates from G3;
- a colour-triplet scalar with its antiparticle: Harz & Petraki's capture into the colour-singlet ground state
  (`sommerfeld.bound_state_rate`);
- otherwise not computed, and the flags say so.

- a particle–antiparticle pair of an SM singlet (spin 0 or ½) bound by a dark U(1) alone, with an effectively
  massless vector (below 1% of the binding energy): hydrogen-like capture into the ground state with the dark
  photon's emission (`dark_u1_bound_rate`, added 2026-10-15; below).

**Refused, with G4's bracket deciding as before:** a group of mixed states, a vector multiplet, a potential that
group theory does not reproduce, and an SU(2) n-plet with n > 5 (bound states in channels I ≥ 7 not computed).

## Validation

**The gate (development half and controls, commit f38f895).**

| check | generic (G7) | reference | ratio |
|---|---|---|---|
| wino, thermal mass (t0 / t1) | 3035 / 3031 GeV | library engine 3058 / 3053 GeV | 0.9925 / 0.9925 |
| De Simone et al., colour-triplet scalar (t0 / t1) | 1320 / 1828 GeV | library engine 1330 / 1828 GeV | 0.9925 / 1.000 |
| Harz & Petraki, with bound states (t0 / t1 / t2) | 3242 / 1826 / 1319 GeV | library engine 3242 / 1828 / 1331 GeV | 1.000 / 0.999 / 0.9915 |
| complex scalar triplet, Y = 1 (new model) | 2241 GeV | Bottaro et al. 2100 GeV, within the zoo's tolerance | met |

The controls agree with their library engines to better than 1%. The wino's library engine is itself 7% above
Bottaro et al.'s 2860 GeV, ADROIT's known offset (`docs/model_zoo.md`). **Gate: met.**

**The n-plet engine reproduced** (`portals.nplet`; Sommerfeld effect and bound states, then the Sommerfeld effect
alone):

| multiplet | n-plet engine | generic (G7) | ratio |
|---|---|---|---|
| 3₁ (Dirac triplet, Y = 1) | 2667 GeV (2589 GeV) | 2569 GeV (2494 GeV) | 0.963 (0.963) |
| 4₁/₂ (Dirac quadruplet) | 4501 GeV (4141 GeV) | 4426 GeV (4057 GeV) | 0.983 (0.980) |

The difference is the same with and without bound states, so it lies in the hard rates, not the potential. The
n-plet engine takes the hard rates from the symmetric-limit formulae; G7 takes them from G3 at G2's couplings with
one running factor (Limits).

**The zoo, development half** (commit f38f895): the new models 6 of 6 computed, all by the generic route, with 10
of 11 targets met (G6: 5 of 6 and 9 of 10). The controls: 6 of 6 computed, 11 of 15 targets met (unchanged), and
the generic route agrees with the controls' engines on 13 of 15 targets.

**The held-out half, run once** (ledgered, `docs/dm10/results/model_zoo.jsonl`, with `--held-out --reason`): the new
models 9 of 11 computed (8 by the generic route), 9 of 13 targets met. The controls: 8 of 8 computed, 9 of 14
targets met, and the generic route agrees with their engines on 13 of 14. What it found:
- **The inert doublet's t0, generic 0.041 against the library's 0.110.** This was a G6 error. Below a pair's on-shell
  threshold, `_off_shell` interpolated log σ across the 1/β of the initial state's flux, which diverges there. It
  now interpolates log(σ·flux) and divides by the flux. The inert doublet's generic Ωh² is 0.1205, and a regression
  test covers it (`test_the_off_shell_rate_is_right_at_the_initial_threshold`). The fix was made after the held-out
  run and motivated by it. The recorded held-out numbers are those from before the fix. On the development half it
  moves Dedes & Karamitros's t1 from 0.134 back to 0.158, near MadDM's 0.152, so 9 of 11 new targets are met
  (`docs/model_zoo.md`).
- **Von Harling & Petraki's dark QED:** 889 GeV against 1040 GeV. Bound states in a dark U(1) are not computed
  (only the structures above are), and the paper's result depends on them.
- **Okada et al.'s B − L model:** Ωh² 0.066 and 0.048 against 0.12. Not localised; G10's intake reproduces the
  zoo's model exactly, so the difference lies in the computation or in the paper's treatment, not in the spec.
- **D'Agnolo et al.'s forbidden dark photon, t2:** 1.868 against 0.651. Not localised.
- **Giacchino et al.'s Majorana dark matter with a charged scalar lepton partner, t0:** not computed.
- **The Majorana quintuplet:** the library engine's 15.5 TeV against Bottaro et al.'s 13.6 TeV, already known; the
  generic route agrees with the library.

**What was not used.** The plan's validations include Bottaro et al.'s real scalar 5-plet, De Simone et al.'s
colour octet and von Harling & Petraki's dark QED. All three are held-out entries, so none of them was used during
development. They appear only in the ledgered held-out run above.

## Dark-U(1) bound states (2026-10-15)

Von Harling & Petraki's dark QED missed in the held-out run (889 against 1040 GeV) because no bound states of a dark
U(1) were computed. They are now, from the hydrogen-like formulas, without reference to that entry. The
electric-dipole capture into the ground state is (von Harling & Petraki, arXiv:1407.7874; Petraki, Postma &
Wiechers, arXiv:1505.00109):

    σ_BSF v_rel = (2⁹/3) π α²/m² · S_BSF(ζ),   S_BSF = [2πζ/(1 − e^{−2πζ})] ζ⁴ e^{−4ζ arccot ζ}/(1 + ζ²)²,   ζ = α/v_rel,

with E_B = mα²/4. It is Harz & Petraki's capture shape with ζ_S = ζ_B (`sommerfeld.capture_shape`). The bound states
decay like positronium:
- a fermion pair's para state (¼ of the spins) to 2γ′, Γ = mα⁵/2;
- its ortho state (¾) to 3γ′, Γ = 2(π² − 9)mα⁶/9π;
- a scalar pair's single state to 2γ′, Γ = mα⁵/4.

Each is in ionisation equilibrium with the dark photons at the bath's temperature. Excited states and transitions
are left out.

Validation (`test_generic_lr.py`):
- in the Coulomb limit σ_BSF/σ_ann → (2⁹/3)e⁻⁴ = 3.13, the known ratio, to 10⁻⁴;
- no capture without binding;
- a synthetic dark-QED fermion (1 TeV, α = 0.03) has its Ωh² lowered;
- a dark photon heavier than 1% of E_B is not taken as massless.

**Found on the way: a new vector named A was merged with the photon.** G1 gives a vector state its field's name,
so a dark photon called "A" became ADROIT's photon. G1 now refuses a new vector named A, Z, W or g
(`spectrum.SM_VECTOR_NAMES`), and the intake guide says so. Scalars and fermions take a suffix (s → s0) and do not
clash.

## Checks outside the zoo (the owner's question 6, 2026-10-15)

The held-out misses were not debugged on their entries. Their physics was reproduced on models outside the zoo:
- **A B − L-like Majorana Z′ (for Okada et al.'s factor of 2).** The generic Ωh² against MadDM's at three points
  (on and off the resonance) is 1.15, 1.16 and 1.15. Channel by channel (MadDM's indirect mode) every final state
  agrees to 10⁻⁴, except that MadDM generates χχ → ν_μν̄_μ and ν_τν̄_τ but merges them with ν_eν̄_e as identical
  matrix elements and counts one flavour. With the Z′ coupled to ν_e alone, the two agree to 0.3% and 1.2%. So the
  generic engine's Z′ resonance is right, and **MadDM undercounts identical neutrino final states**. That matters for
  every MadDM Ωh² cross-check of a model that annihilates to neutrinos. Okada et al.'s factor of 2 is not this; G10
  shows the spec is the paper's.
- **Forbidden annihilation (for D'Agnolo et al.'s t2, Δ = 0.65).** χχ̄ → V V with m_V = m_χ(1 + Δ). The engine's
  thermal average from its tabulated σ(s) against an independent Gondolo–Gelmini integral of G3's σ(s) agrees to
  0.6–0.9% at Δ = 0.1, 0.3 and 0.65 (x = 15, 25). The forbidden channel is right, so that miss lies in the entry's
  other channels or the paper's treatment.
- **Giacchino et al.'s Majorana dark matter with a lepton partner, t0.** The typed route took it, and the library's
  t-channel engine refused that target by its own domain (the lepton partner's coannihilation only for m_φ ≳ 200
  GeV). A G12 integration item: where the typed route refuses a target by domain, fall back to the generic route.

## Found on the way

| what | where | effect |
|---|---|---|
| A state's composition is |amplitude|² already; the G5 loop library squared it again | `generic_dd._composition` | a mixed fermion's purity read low (a 99.5% state as 99.0%); now shared with G7 (`generic_lr._share`) |
| Below a pair's on-shell threshold, log σ was interpolated across the 1/β of the initial flux | `generic._off_shell` (G6) | the inert doublet's Ωh² 0.041 instead of 0.110 (found by the held-out run); now log(σ·flux) |

## Limits

- The symmetric limit: mass splittings within a multiplet, and the broken-phase thresholds, are not in the
  potential (G8 builds the broken phase for annihilation today).
- Bound states only for the structures above. Excited states beyond 2s, and 2p, are left out.
- A mixed sector (singlet–doublet, singlet–triplet) is not decomposed; where G4's bracket moves its Ωh² by less than
  10%, the perturbative value stands.
- A group's hard rates take one running factor (α₂, or α_Y for a hypercharged singlet); a model whose s-wave
  annihilation is not mostly gauge-coupled carries that as a theory uncertainty.

Tests: `tests/parameter_space/test_generic_lr.py`.

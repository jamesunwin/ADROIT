# SHM++: the scientific specification of ADROIT's benchmark (halo phase 2)

Written before the implementation, on 2026-11-10, from the full source of Evans, O'Hare and McCabe, *SHM++: A Refinement
of the Standard Halo Model for Dark Matter Searches in Light of the Gaia Sausage* (arXiv:1810.11468v3, PRD 99, 023012;
the arXiv TeX source as fetched, sha256 `ebb93648ec024df76f8e9b1ec36eb215e497620c76224f0134b20385ab52e9fe`).

Also read:
- the authors' public code, MIT licence (github.com/mccabech/SHMpp, master as fetched 2026-11-10, its archive's sha256
  `0c03b8071a8aa04c17babb0661817ca1bdd4d4afa9e79585be67a6a6986c9ff8`): `SHMpp_gvmin.py`, `SHMpp_hvmin.py` and their
  tables `gvmin_SHMpp.dat`, `hvmin_SHMpp.dat`. It is read as a reference only: nothing of it is copied or executed. The
  two tables are kept, with the licence, as a test reference (`tests/halo_models/data/shmpp_authors/`);
- McCabe, *The Earth's velocity for direct detection experiments* (arXiv:1312.1355, its TeX source sha256
  `e1ff6b72c593aa2c930e64665690b6c8757c76c242f83f9537e31b4d2eee06ad`), for the Earth's velocity.

Equation numbers are the paper's; McCabe's are cited by section.

## The distribution (Galactic rest frame)

**The mixture** (Eq. 3):

    f(v) = (1 − η) f_R(v) + η f_S(v),

with η the fraction of the local dark matter in the Sausage. Each component is normalised to one on its own, so the
weights are applied once. The local density ρ₀ multiplies the whole; no component has a density of its own.

**The round component** (Eqs. 1–2) is the SHM's truncated Maxwellian:
- f_R(v) = exp(−|v|²/2σ_v²) Θ(v_esc − |v|) / [(2πσ_v²)^{3/2} N_R,esc], with σ_v = v₀/√2;
- N_R,esc = erf(v_esc/√2σ_v) − √(2/π) (v_esc/σ_v) exp(−v_esc²/2σ_v²).

**The Sausage** (Eqs. 4–7): an anisotropic Gaussian aligned in Galactocentric spherical coordinates (r, θ, φ).
- σ_θ = σ_φ; the anisotropy is β = 1 − (σ_θ² + σ_φ²)/(2σ_r²).
- The dispersions follow from the flat rotation curve (Eq. 6): σ_r² = 3v₀²/[2(3 − 2β)] and
  σ_θ² = σ_φ² = 3v₀²(1 − β)/[2(3 − 2β)].
- f_S(v) = exp(−v_r²/2σ_r² − v_θ²/2σ_θ² − v_φ²/2σ_φ²) Θ(v_esc − |v|) / [(2π)^{3/2} σ_r σ_θ² N_S,esc].
- N_S,esc = erf(v_esc/√2σ_r) − √((1−β)/β) exp(−v_esc²/2σ_θ²) erfi[(v_esc/√2σ_r) √(β/(1−β))].

**Truncation.** Both components are cut at the same Galactic-frame escape speed |v| = v_esc and renormalised after the
cut. The cut is in the Galactic frame, never in the laboratory's.

**Axes** (the paper's footnote: Galactocentric spherical coordinates equal rectangular ones at the Earth's position), in
ADROIT's Galactic convention:
- x points toward the Galactic centre: v_r = −v_x, which the Gaussian's square makes immaterial;
- y points along the rotation: v_φ = v_y;
- z points toward the north Galactic pole: v_θ = −v_z.

The Sausage is elongated along the Sun–Galactic-centre axis. These are the authors' code's axes too
(`vdisSaus = [σ_r, σ_θ, σ_θ]`, the first along x).

## The benchmark values (Table I)

| | value | source |
|---|---|---|
| local density ρ₀ | 0.55 GeV cm⁻³ | Table I (its 30% systematic range not used: a fixed benchmark) |
| circular speed v₀ | 233 km s⁻¹ (σ_v = v₀/√2) | Table I, Section II B |
| escape speed v_esc | 528 km s⁻¹ | Table I (v3, Deason et al. arXiv:1901.02016; the authors' code updated to it in February 2019) |
| Sausage anisotropy β | 0.9 | Table I |
| Sausage fraction η | 0.2 | Table I |
| the Sun's peculiar velocity (U, V, W) | (11.1, 12.24, 7.25) km s⁻¹ | Schönrich et al., as the authors' code uses; the paper's text rounds it to (11.1, 12.2, 7.3) |
| the local standard of rest | (0, v₀, 0) | Section III A: v_E(t) = (0, v₀, 0) + (U, V, W) + u_E(t) |
| the Earth's velocity u_E | (28.574, −2.053, 9.109) km s⁻¹ at n = 7364.3 days after J2000.0 (2020 February 29, 19:12 UT) | the authors' code (`Day = 60.8`, "gives the average value of vE", with n = Day + 7303.5); McCabe's Section 3.3 form (below) |

**The Earth's velocity formula** (McCabe, arXiv:1312.1355): u_E,i = ⟨u_E⟩ cos b_i [sin(ℓ − λ_i) − e cos(λ_i − λ₀)], with
⟨u_E⟩ = 29.79 km s⁻¹, e = 0.9574°, λ₀ = ϖ − 270°, ℓ = L + 2e sin g + (5/4)e² sin 2g. L, g and ϖ are linear in n
(Section 2), and (b_i, λ_i) are linear in T = n/36525 (Section 3.2). This is McCabe's corrected form of Lewin and Smith's
expression (Section 3.3), which keeps ℓ to second order in e. The authors' code uses it, and so does ADROIT
(`halo_models.shm_plus_plus.earth_velocity`).

**The instant.** The authors' code evaluates it at `Day = 60.8`, with n = Day + 7303.5, so n = 7364.3. Its comment
reads "Day=0 is midnight 1 Jan 2020", but by McCabe's Appendix A that midnight is n = 7304.5: the comment is one day
off. The benchmark is defined by n, so the ambiguity does not reach it.

**The laboratory velocity:** v_E = (39.674, 243.187, 16.359) km s⁻¹, |v_E| = 246.94 km s⁻¹. The annual mean of
|v_E(t)| by the same formula is 247.19 km s⁻¹.

**The Sun's velocity** (capture in the Sun): v_⊙ = (0, v₀, 0) + (U, V, W) = (11.1, 245.24, 7.25) km s⁻¹, without the
Earth's.

## The time convention (a decision, recommended; the owner may change it)

The paper gives no unique prescription. Its Fig. 3 caption says the halo integrals are "averaged over time", while its
public code (which "matched the PRD version") evaluates them at one instant, n = 7364.3, where the laboratory speed is
near its annual mean. **ADROIT's benchmark takes the authors' code's fixed date.** It is the source's implementation, and it is
what the authors' reference tables (used here for validation) were computed with.

The alternatives, measured on g(v_min) = ∫ f/v d³v by the prototype
(`scratch_evidence/halo_phase2_2026-11-10/validation/prototype/time_convention.py`, its output beside it):
- **The annual average of g against the fixed date:** −0.1% at v_min = 0; +0.2% at 300 km/s; +0.3% at 500 km/s;
  −0.5% at 600 km/s; +3.4% at 700 km/s (the far tail, where the modulation is largest).
- **ADROIT's SHM benchmark vector** (the Earth on 9 March, arXiv:2105.00599 Eq. 12, |v_E| = 248.74 km s⁻¹ with
  v₀ = 233): −0.4% at 0; +1.6% at 500 km/s; +2.6% at 600 km/s; +5.3% at 700 km/s.

The convention is part of the benchmark's version: changing it is a new version, never a reinterpretation of a saved
result. **Annual modulation and directional rates are not supported.** The benchmark is one date's non-directional
distribution, and a request for either is refused (capabilities `annual-modulation`, `directional`).

## The laboratory transformation and the speed distributions

The distribution a detector sees is f_lab(u) = f(u + v_E). It is anisotropic, so its speed distribution depends on the
direction of v_E, not only its length:

    F(u) = u² ∮ f(u n̂ + v_E) dΩ_n̂.

**The round component** is isotropic: F_R depends only on |v_E|, and is the SHM's closed form at (v₀, v_esc, v_E)
(`physics.halo.speed_distribution` for a standard halo with these vectors).

**The Sausage** is integrated numerically, with the polar axis of n̂ along v_E.
- The escape cut |u n̂ + v_E| < v_esc is then a limit on cos α: cos α < (v_esc² − u² − |v_E|²)/(2u|v_E|). The angular
  integrand is smooth on the domain left: an anisotropic Gaussian.
- Quadrature: Gauss–Legendre in cos α on [−1, min(1, cos α_max)] (64 nodes), and the trapezoid rule in the azimuth
  (64 points; periodic, so spectrally accurate).
- F is zero above u_max = v_esc + |v_E|.

**The Sun's frame** is the same construction with v_⊙ in place of v_E. Capture in the Sun uses this table. A
detector-frame table is never passed to it, and changing the Earth's velocity on a detector-frame table is not a frame
transformation.

## Its numerical representation

- **Tables.** Each frame's F(u) is tabulated on a uniform grid of 1,601 speeds from 0 to u_max, and its mixture taken
  with weights (1 − η, η). The result is an ADROIT tabulated halo of density ρ₀: a `HaloModel(kind=tabulated)` in the
  detector's frame, a `SunFrameTable` (`halo_models/frames.py`, its record `frame: sun`) in the Sun's. The rate engine's integrals, η(v_min) = ∫ F/u du and η⊥(v_min) = ∫ F (u² − v_min²)/u du,
  are exact for the table's linear interpolant (`physics.halo`, unchanged). So every operator's rate, elastic or
  inelastic of either sign (any v_min), uses these two moments of the table.
- **Identity.** The table is an implementation of the declared distribution, not a replacement for it. Its grid (1,601
  speeds), angular nodes (64 × 64) and generator version are part of the benchmark's identity, with the sha256 of each
  generated table.
- **Snapshot.** A request records the parameters, the numerical settings and the tables' sha256. A run generates the
  tables once (a deterministic function), checks them against the request's sha256 (a differing implementation is
  refused as a new version), and uses that snapshot throughout.
  - The family decides the snapshot's form. An SHM++ snapshot without its parameters, numerical settings, Sun-frame
    table or tables' sha256 is refused as it is read, never calculated as another halo.
  - Every calculation that puts the snapshot in force checks it (`halo_region.using`): a run, a continuation, a
    verdict, a scan's worker, a replay (the halo phase 2 audit, 2026-11-11).
- **Convergence criteria (declared):** doubling the speed grid and the angular nodes changes g and h by less than
  1 × 10⁻⁴ (relative) for v_min below u_max − 50 km s⁻¹, and the normalisation ∫F du by less than 10⁻⁶.

## What it supports and what it does not

| capability | SHM++ | why |
|---|---|---|
| `recoil` (η, η⊥ in the detector frame) | yes | the detector-frame table |
| `solar` (a Sun-frame distribution) | yes | the Sun-frame table, boosted from the Galactic distribution with v_⊙ |
| `local-density` (the Galactic searches' fixed-profile rescaling) | yes, conditional | ρ₀ = 0.55 rescales each record's limit as (ρ_record/ρ₀)² with its own profile. The local anisotropy is not a Galactic J-factor model |
| `count-ratio` (the SHM accepted-count ratio) | no | a shape-changing distribution: the SHM's validation does not cover it, so the slow modules take their full procedure (within the point's budget) |
| `annual-modulation`, `directional` | no | one date's non-directional distribution (above) |
| `pair-velocity` | no | the local distribution supplies no relative-velocity distribution over a source region; velocity-dependent annihilation keeps ADROIT's fixed conventions, qualified |

The per-consumer treatment is in `docs/halo_constraint_support.md` (its SHM++ column).

## Validation (independent references and declared tolerances)

Declared before any production result:
1. **The normalisations** N_R,esc (2π)^{3/2} σ_v³ / v₀³ and N_S,esc (2π)^{3/2} σ_r σ_θ² / v₀³ equal the authors' quoted
   5.47699 and 2.09443 to 1 × 10⁻⁵.
2. **The isotropic limit.** At β → 0 the Sausage's numerical lab-frame F equals the round component's closed form within
   10⁻⁶. At η = 0 the SHM++ tables equal the SHM's closed form at the same parameters (v₀ = 233, v_esc = 528, the same
   v_E) within the table's interpolation error (10⁻⁵ in g and h).
3. **Each component normalised:** ∫F du = 1 within 10⁻⁶; positive and finite everywhere; zero above u_max.
4. **Against the authors' independent Monte Carlo tables** (10⁶ samples, same parameters and date): g and h within 0.5%
   for v_min ≤ 500 km s⁻¹ and within 3% for 500 < v_min ≤ 700 km s⁻¹, where their sampling noise grows.
5. **Against an independent three-dimensional cubature of my own** in the Galactic frame (a scrambled Sobol sequence of
   2²⁰ points per component, no angular reduction), at representative v_min: 0.3% (its own error, estimated by two
   scramblings).
6. **Convergence** under doubling the grid and the angular nodes, as declared above.
7. **Spectra and limits:**
   - A spin-independent recoil spectrum on xenon from the SHM++ table, against the same spectrum built from the authors'
     g table, within 0.5%.
   - A counting search's limit, which scales as the inverse of its accepted count, against that scaling from the
     independent spectrum.
   - A second detector response (germanium or argon) checked in the same way.
8. **Capture in the Sun:**
   - the Sun-frame table against an independent Monte Carlo of the Galactic distribution boosted by v_⊙, through the
     same capture kernel;
   - a case out of equilibrium, where the annihilation rate does not scale linearly with the density.

The results are in `docs/halo_phase_2_completion.md`.

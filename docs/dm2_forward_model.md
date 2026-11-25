# DM2: the forward model

Built and validated 2026-09-29. Cost: $0. The gate is met: reference spectra
are reproduced to better than 0.2% (section 4).

## 1. What was built

The rate per kg of target, per day, per keV of recoil energy:

    dR/dE_R = Σ_T x_T  ρ/(2π m_χ)  4π/(2J_T+1)
              Σ_k Σ_{ττ'} W_k^{ττ'}(q) [ R_k^{ττ'} η(v_min) + R⊥_k^{ττ'} η⊥(v_min) ] .

It factorises into three independent pieces, each in its own module under
`adroit/physics/`:

| factor | module | what it is |
|---|---|---|
| the halo | `halo.py` | η(v_min) = ∫ f(v)/v and η⊥(v_min) = ∫ f(v)(v² − v_min²)/v over v > v_min |
| the nucleus | `nuclear.py` | the eight response functions W_k^{ττ'}(q) of each isotope (arXiv:1308.6288) |
| the particle physics | `rates.py` | R_k and R⊥_k, quadratic in the operator coefficients (arXiv:1308.6288, Eq. 38) |
| the target | `targets.py` | natural isotopic compositions of Xe, Ar, Ge, Si, Na, I, F, Ca, W, O, C, and NaI, CaWO₄, C₃F₈, CF₃I |

**The halo.** The Standard Halo Model of arXiv:2105.00599 is the default: a
Maxwellian with v₀ = 238 km/s, truncated sharply at v_esc = 544 km/s in the
Galactic frame, seen from a detector moving at v_lab = 253.7 km/s. Both
integrals are in closed form (η is the standard result; η⊥ was derived here
and checked against quadrature to 10⁻⁸). Any other halo enters as a tabulated
detector-frame speed distribution, integrated exactly for its linear
interpolant; `halo.tabulate` turns the standard halo into a table to be
modified. The parameters ρ, v₀, v_esc and the solar and Earth velocities are
fields of `HaloModel`, ready to be nuisance parameters in DM6.

**Kinematics.** Inelastic (δ > 0) and exothermic (δ < 0) scattering enter only
through v_min = |m_T E_R/μ + δ|/√(2 m_T E_R). The transverse velocity is
v⊥² = v² − v_min² in all three cases (arXiv:1409.0536; WimPyDD does the same).
`rates.recoil_range_kev` gives the kinematic window
E± = μ²/(2 m_T) (v_max ± √(v_max² − 2δ/μ))².

**Annual modulation** is an output from the start
(`rates.annual_modulation`): the rate on 24 days of the year, with the
Earth's velocity from arXiv:2105.00599 Eq. (11), reduced to its mean,
amplitude and peak day. For 100 GeV on xenon the peak is on 2 June above
v_min ≈ 205 km/s and on 1 December below it, with amplitudes of 2–4% of the
mean.

**Operators.** O₁ and O₃–O₁₅, for dark matter of any spin, in any
combination, including every interference between them. O₂ has no
leading-order nuclear response. The spin-1 operators O₁₇–O₂₀
(arXiv:1505.03117) are left to phase 2.

## 2. Conventions fixed in DM2

- **The operator mass.** The momentum-dependent operators carry q/m_N. Here
  m_N is the atomic mass unit, as in WIMpy_NREFT and in WimPyDD, which
  produced LZ's published tables. A nucleus of mass number A has mass
  A atomic mass units. (`conventions.OPERATOR_MASS_GEV`; the development record, decision
  of 2026-09-29.)
- **The isospin normalisation of the responses.** In the published tables, τ = 0
  multiplies c^p + c^n and τ = 1 multiplies c^p − c^n: twice the isospin
  coefficients of `conventions`. The code converts once, in
  `rates.isospin_coefficients`.
- **The order of the interference responses.** They are stored as W_{Φ''M}^{ττ'}
  and W_{ΔΣ'}^{ττ'}, the order in which the rate multiplies them. The published
  tables hold the transposes, W_{MΦ''} and W_{Σ'Δ}; the extraction script
  transposes them once.

## 3. The nuclear input

**The shell model** (the default). These are the responses of Anand et al.
(arXiv:1308.6288) and Catena & Schwabe (arXiv:1501.03729), published as
polynomial fits W(y) = e^{−2y} Σ aₙ yⁿ, for 30 isotopes.
- **Source.** The coefficients were transcribed from WIMpy_NREFT (MIT
  licence), which holds them to full precision, by
  `docs/dm2/extract_responses.py`. They are shipped in
  `adroit/physics/data/shell_model_responses.json`, with the licence
  beside them.
- **Normalisation checked.** At q = 0 the tables give W_M = (2J+1)A²/(16π), and
  spin expectation values ⟨S_p⟩ = 0.475 for ¹⁹F, 0.248 for ²³Na and
  ⟨S_n⟩ = 0.475 for ⁷³Ge.

**The approximation**, for isotopes the shell model does not cover (and the
whole of the `helm` model):
- the Helm form factor for M, with the parameters of Lewin & Smith, which is
  what experiments use for spin-independent limits;
- where ⟨S_p⟩ and ⟨S_n⟩ are known, Σ'' and Σ' with a Gaussian form factor
  (arXiv:1505.01926, Appendix C), normalised to reproduce the shell-model
  tables at q = 0;
- the other five responses are absent.

Every spectrum records which isotopes used which input (`nuclear_input`).
For natural xenon this is the shell model for 99.8% of the target by mass,
with Helm for ¹²⁴Xe and ¹²⁶Xe. For CaWO₄ the approximation covers 64% by
mass, all of it tungsten plus the minor calcium and oxygen isotopes: only
¹⁸³W and ¹⁷O have spin values, and the spin response of ⁴³Ca is omitted.

## 4. Validation

**Analytic limits.** Tested in `tests/physics/test_rates.py` to 10⁻¹²:
- the spin-independent rate equals ρ c² A² F²(q) η/(2π m_χ), which is
  ρ σ_n A² F² η/(2 μ_n² m_χ) for σ_n = c² μ_n²/π;
- the spin-dependent rate equals
  ρ j_χ(j_χ+1)(J+1)/(6πJ) (c_p⟨S_p⟩ + c_n⟨S_n⟩)² G(q) η/m_χ.

**Reference codes** (`docs/dm2/reference_spectra.py`). Every case was run
through both codes twice:
- as published;
- patched, with their rounded constants (c = 3×10⁵ km/s, ħc = 0.197 GeV fm,
  m_N = 0.931 GeV, 6.02×10²³) replaced by CODATA values and, for WimPyDD, its
  six-figure response table replaced by the full-precision one.

The patched runs test the physics and are the gate's references; they are
stored in `tests/physics/fixtures/reference_spectra.json`. There were 51
cases, 49 of them in the gate (the two tungsten cases test the approximation,
section 3):
- each operator alone;
- all fourteen at once, with random isoscalar and isovector couplings, on
  thirteen isotopes;
- dark matter spins 0, ½ and 1, and masses of 10, 100 and 1000 GeV;
- inelastic and exothermic cases;
- the approximate responses for tungsten.

Deviation is the largest |ours/reference − 1| over 24 energies from 1 to
400 keV. The figures below come from the run of 2026-09-29, whose full output
is `docs/dm2/reference_summary.txt`. "Bulk" means energies where v_min lies at least 50 km/s below the
fastest particle.

| reference | cases | bulk | tail |
|---|---|---|---|
| WIMpy_NREFT, patched | 27 (it lacks Φ̃', so no O₁₂, O₁₃; no splitting) | ≤ 1.3×10⁻¹¹ | ≤ 1.2×10⁻¹¹ |
| WimPyDD, patched | 50 (all but the ¹⁸³W spin case, finding 3) | ≤ 1.3×10⁻³ | ≤ 3.0×10⁻³ |
| WIMpy_NREFT, as published | 27 | 1–17% | up to 18% |
| WimPyDD, as published | 47 (it fails on the 4 calcium and tungsten cases, finding 4) | 1–32%; 190% for inelastic O₁ near threshold | up to 190% |

The residual 10⁻³ against WimPyDD is the resolution of the 8000 velocity
streams it was given, not physics. **The gate** (1%) is enforced by
`test_reference_spectra_are_reproduced` for every gate case against every
code that computes it.

**Why the published versions differ.** The differences come from rounding,
amplified in two places:
- **near the minima of the nuclear response,** where a 0.2% shift in q (from
  ħc = 0.197) or in the tabulated coefficients moves W by tens of percent;
- **near the kinematic endpoint,** where c = 3×10⁵ km/s shifts v_min by 0.07%
  on the steep tail of η.

This matters for fits to events at high recoil energy, such as LZ's at
248 keV. It is noted for DM6, which compares with LZ's tables.

## 5. Findings about the reference codes

These are recorded for the owner, who may wish to tell the authors. None was
reported.

**WimPyDD 2.0.3:**
1. **Six-figure response table.** Its table holds the same fits as
   WIMpy_NREFT's, rounded to six significant figures. Near momentum transfers
   y ≈ 2, which is a 250 keV xenon recoil, the rounding moves some responses
   by several percent (¹³⁰Xe M: 4.5%) and up to 20% near a zero (¹⁶O M).
2. **A transcription slip for ²⁷Al.** W_{Σ'}^{00} has its y² coefficient
   0.210848 in place of 0.244466; the y¹ coefficient is repeated.
3. **Four times the spin-dependent normalisation for ¹⁸³W and ¹⁷O.** Its
   approximate Σ'' carries 4/(3π) where 1/(3π) reproduces its own shell-model
   table at q = 0 (checked on ¹⁹F). Its O₄ rate on ¹⁸³W is four times ours.
   Whether the factor comes from arXiv:1505.01926 or from the transcription
   was not checked.
4. **Calcium and tungsten fail.** The response files for ⁴²Ca, ⁴⁴Ca, ⁴⁶Ca,
   ¹⁸⁰W–¹⁸⁶W and ¹³³Cs use `np` without importing numpy, so any rate on
   calcium, tungsten or caesium (CRESST's CaWO₄, CsI) raises an error as
   published. The patched copy adds the import.
5. **Zero rate for some isotopes.** Isotopes with neither table entries nor a
   response file (¹²⁴Xe, ¹²⁶Xe, ²⁹Si, ³⁰Si, ³⁶Ar, ³⁸Ar, ⁴³Ca, ¹³C, ¹⁸O)
   contribute zero rate. For silicon that drops about 8% of the
   spin-independent rate. Here they take the Helm form factor instead.

**WIMpy_NREFT v1.2:**
1. It omits the Φ̃' response, so its rates for O₁₂ and O₁₃ are incomplete.
2. Its constants are rounded (c = 3×10⁵ km/s, ħc = 0.197 GeV fm, the atomic
   mass unit as 0.9315 GeV).
3. It imports two functions that current SciPy has removed (DM0).

**The cited sources of the approximate spin values** are at record level only.
WimPyDD takes ¹⁷O's values from arXiv:2309.02495, a paper on dark matter
heating planets, and ¹⁸³W's from the single-particle shell model as
tabulated in hep-ph/0406218. Both need a primary nuclear-structure source
before they are relied on. ¹⁷O is 0.04% of oxygen, so its value hardly
matters. ¹⁸³W carries almost all of a CaWO₄ target's neutron spin-dependent
rate, so its value matters for any spin-dependent use of CRESST (DM3).

## 6. Reproducing DM2

```bash
uv run python docs/dm2/extract_responses.py   # the shipped response data, and the table cross-check
uv run python docs/dm2/reference_spectra.py   # the reference spectra and the fixture
uv run pytest tests/physics                   # the gate and the analytic limits (0.5 s)
```

The reference codes and their environments are in `data/external/`, which git
ignores (docs/dm0_tool_audit.md):
- WIMpy_NREFT in `.venv-audit`;
- WimPyDD in `.venv-wimpydd`, a native arm64 Python with numpy, scipy and
  matplotlib.

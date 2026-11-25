# Coannihilation prerequisite at declared component accuracy (M27)

ADROIT's effective coannihilation solver assumes common chemical potentials.
M27 checks that assumption for one existing family: Majorana chi and a colourless
eR scalar partner. It does not replace the effective relic solver or introduce
a public non-equilibrium cosmology workflow.

The source-regulated component certificate is explicitly requested:

```bash
uv run adroit theory equilibrium docs/examples/tchannel_equilibrium.yaml --out RUN_DIR
```

```yaml
chemical_equilibrium:
  x_low: 10
  x_high: 50
  samples: 9
  rate_relative_uncertainty: 0.5
  include_odd_sector: true
  approximation: unbroken_hypercharge_vacuum_Born_MB
  source_born:
    scheme: garny_1705_appendix_A_full_angle_vacuum_mass_MB
    scope: retained_abelian_component_only
```

The retained component has the existing chiral Yukawa and Abelian vector gauge
vertex, vacuum masses and Maxwell–Boltzmann thermal averaging. The finite vacuum
electron mass is the declared collinear regulator, and since R5 (release audit M11)
the regulator bank also holds a thermal variant: the scattering with the electron's
asymptotic plasma mass, m_f = √(m_e² + m_∞²), m_∞ = g′T/2 for e_R. Since 2026-10-12
(algorithm version 4) the variant is consistent: the decay φ → χ e and its inverse carry
the same thermal mass, and close when m_φ < m_χ + m_f (thermal blocking); the scalar's own
thermal mass is not included. It cuts the scattering rates by roughly ×0.07–0.3, and the
conservative bound takes the lowest variant; at (8000, 8080 GeV, y = 1.6×10⁻⁵) it turns
"supported" (min Γ/H = 176) into unresolved (63). This is a bracket, not a matched
plasma calculation or a full broken-electroweak model. Source matching applies to the retained
processes, perturbative approximation and regulator prescription, rather than
reproducing a source paper's complete model/relic curves with additional interactions.

All retained conversion channels are required: finite-mass scalar decay/inverse
decay with K1/K2 dilation and detailed balance; both charge-conjugate gauge
crossings chi B ↔ phi e and chi ebar ↔ phi B; and chi chi ↔ phi phi†. The latter
has forward spin average 1/4 and reverse identical-Majorana final factor 1/2.
Its nonlinear collision appears only in private coupled validation; the public
certificate uses its independently checked equilibrium relaxation eigenvalue.
Omitting `include_odd_sector` prevents a passing source-component certificate.

The source prescription uses minimum sqrt(s)=M_phi+m_cut with independent
m_cut=0.1,0.5,5 GeV variations. It integrates the full angular range. Logarithmic
angular coordinates and stable invariant denominators resolve the collinear
region; no artificial angular exclusion remains in this mode. Energy and
angular refinements are separately checked. See
[Garny et al., Appendix A](https://arxiv.org/abs/1705.09292) and the
[leptophilic study, Appendix A](https://doi.org/10.1007/JHEP07(2019)136).

A complete `passed=true`, `component_prerequisite=supported` result means the
numerical criterion passes over the requested sampled interval and entire
finite regulator/declared-uncertainty bank. Its approximation, domain, version,
inputs and uncomputed corrections are retained. It is not a uniform relic-error
bound or an inclusive/plasma calculation. If even the upper envelope fails at
a sampled temperature, the component criterion is unsupported. A boundary,
straddling envelopes, unresolved quadrature or missing retained rate remains
unresolved/pending. Exact y=0 fails independently of the approximation.

The checked domain is m_chi=8–20 TeV, splitting 1–10%, |y|≤1e−3,
10≤x_low<x_high≤50, T≥160 GeV, the existing g_prime and at least 50% explicitly
declared residual rate uncertainty. The declared interval must bracket the relic
solver's freeze-out at the point, x_f (where Y = 2Y_eq), and the rates are sampled from
x_f to x_high: equilibrium must hold from freeze-out on. An interval that misses x_f is
refused and the pending item stays (until R5 a window such as [45, 50] could pass where
[10, 50] did not). Finite samples do not exclude arbitrarily narrow between-node
features. Threshold 100 was selected after 12 source-prescription development
references; fresh masses/splittings and independent cut variations confirm it.
Kinetic equilibrium and initial thermal/cosmological conditions remain separate.

`physical_prerequisite=pending` and `uncomputed_corrections` record the stronger
inclusive/plasma claim separately. Virtual/radiative/soft matching, plasma
properties and full EW/Higgs channels are excluded from the requested retained
component scope; they are not silently assigned rates or certified. A supported
component result removes the unresolved component prerequisite from the thermal
point's pending list, while its information flag and certificate keep these
accuracy limits visible. Experimental cuts, records and confidence levels remain
independent of this theory assessment.

Without `source_born`, the earlier diagnostic is preserved: it uses the correlated
relative energy/angular cut bank (0.1,0.5,1)*T and |cos(theta)|=0.9,0.95,0.98,
keeps `passed=None` and does not create a full/component certificate. Older inputs,
archive identities and replayed numerical results are retained. The default
new source field is omitted from the legacy parameter-identity convention.

micrOMEGAs/CalcHEP supplies an independent minimal Abelian conversion-sector
benchmark with matching vertices, masses, vacuum regulator and phase space.
The comparison covers widths, individual scattering kernels and the native
rest-decay chemical-relaxation normalization. Its checkTE rest-width convention
and EOS are explicitly translated for comparison with ADROIT's thermal K1/K2
quantity. It does not validate a differently regulated aggregate co-scattering
rate, the whole portal relic density or the unavailable inclusive/plasma treatment.
The installed tools are read only; model builds use isolated temporary folders.

## The physical prerequisite at leading order in the plasma (2026-10-19)

The owner's request of 2026-10-19: build the plasma rates and validate them only against their limits, working to
leading order. A request adds

```yaml
  plasma:
    scheme: leading_order_asymptotic_masses_quantum_statistics
```

(`docs/examples/tchannel_equilibrium_plasma.yaml`), and `theory/plasma_rates.py` then decides
`physical_prerequisite` as `supported`, `failed` or `unresolved`; without it the certificate, its identity and the
component result are unchanged.

**What changes from the vacuum Born rates**, all at leading order in the couplings (unbroken phase, Q = T₃ + Y):
- **thermal masses on every light or charged leg:** the e_R's asymptotic mass m_e = g′|Y|T/2 on the external and the
  exchanged electron (the existing thermal regulator); the B's transverse asymptotic mass m_B² = m_D²/2 with
  m_D² = (11/6) g′²T², which now regulates the soft B that the source prescription cut by hand; the partner's
  M_T² = M² + g′²Y²T²/4. B → e ē is closed (m_B ≈ 0.96 g′T < 2m_e), so the exchanged electron is never on shell;
- **quantum statistics in the plasma frame:** the incoming B (Bose–Einstein) or ē (Fermi–Dirac), the outgoing
  electron Pauli-blocked and the outgoing B Bose-enhanced, χ and φ Maxwell–Boltzmann;
- **decays** φ → χ e at the thermal masses with Pauli blocking (×0.64, 0.78, 0.90 at x = 10, 25, 45 for a 5%
  splitting near 8 TeV), the inverse decays by detailed balance;
- the odd sector χχ ↔ φφ† stays the vacuum Born rate (y⁴).

**The bank and the decision.** The thermal masses are scaled by ½, 1 and 2: the exchanged electron's asymptotic mass
fixes the coefficient of the collinear logarithm exactly and leaves the constant under it at O(1), and the soft-B
region is treated with the asymptotic mass rather than HTL resummation. The criterion is the component certificate's
(Γ/H > 100 with a 1% boundary band and the declared residual uncertainty, at least 50%): supported if the lower edge
of the lowest scale passes at every sampled temperature, failed if the upper edge of the highest scale fails at one,
else unresolved. Not a matched or HTL-resummed calculation, and kinetic equilibrium stays separate.

**Validation, against limits only** (`tests/theory/test_plasma_rates.py`):

| limit | result |
|---|---|
| a massless B: the cross section is `source_born`'s | to 10⁻⁹ (floating point) |
| the vacuum Maxwell–Boltzmann limit of the plasma integral (the source cut, no statistics) | within 0.08% of `source_born`'s converged rate, both channels, x = 10, 25, 45 |
| the collinear leading logarithm of χ B → φ e: the coefficient of ln(1/m_e²) | equals collinear factorisation, [x₀² + (1 − x₀)²]/(32π(s − m²)) (the Weyl splitting B → e_R ē, half the Dirac P_qγ, times σ(χ ē → φ) = (π/2) δ(ŝ − M²)), to 10⁻⁴ in the vacuum code and 0.05–0.13% as a thermal average in the plasma integrator |
| Maxwell–Boltzmann statistics at large ΔM/T | incoming occupations → MB (1.000000 at ΔM/T = 25); decay blocking → 1 |
| detailed balance | the inverse decays computed directly equal the blocked decays × n_φ/n_χ to 10⁻¹⁵ |

The outgoing light particle's factor does not tend to 1 at large ΔM/T: in a 2 → 2 conversion it can be soft however
heavy the partner, so the outgoing electron's blocking (×0.78) and the outgoing B's enhancement (×1.7) are genuine
leading-order plasma effects, the latter inside the scale band.

**What it decides.** For the example family (m_χ = 10 TeV, m_φ = 10.5 TeV, x = 15–40): y = 3 × 10⁻⁵ supported
(lowest Γ/H 2.4 × 10³), y = 10⁻⁶ and 10⁻⁷ failed, as the component certificate. Where the plasma rates were asked for
they decide the t-channel portal's flag and pending item (supported: no pending item; failed or unresolved: pending,
named); otherwise the component certificate does, as before. This completes M27 at leading order in the plasma; the
full electroweak/Higgs channels of the broken phase remain outside it.

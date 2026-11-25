# DM13: parameter space and the verdict (Track 1's output)

Started 2026-10-03. The owner's design is in the build plan ("The dual-track
system"). This record covers what was built, the gate (declared in section 5
before its first run) and its result.

## 1. The computable classes (`parameter_space/classes.py`, `classify.py`)

A scan needs the whole picture at every point (relic density, direct
detection, gamma rays, the Sun, colliders), so it works on classes of models
whose physics the system computes end to end:

- **Spin-1 mediator** (`Spin1Class`): Dirac dark matter and a neutral vector
  mediator with pure vector or pure axial couplings, one universal quark
  coupling g_q and optionally a lepton coupling g_ℓ. Everything is DM7's: the
  widths, σ(s) by channel including Z′Z′, the relic density, the
  direct-detection matching, and the CMS benchmarks (V1, A1, V2, A2).
- **Scalar mediator** (`ScalarClass`, new): Dirac dark matter and a real
  scalar S with couplings to fermions in proportion to their masses,
  S f̄(g_s + i g_p γ⁵)f · m_f/v, and a scalar or pseudoscalar coupling to the
  dark matter. In the centre-of-mass frame, for each fermion f,

  σ(s) = N_c s (y_s² β_χ² + y_p²)(g_s² β_f² + g_p²) β_f / (16π β_χ |s − m_S² + i m_S Γ_S|²),

  with Γ_S summed over open fermion pairs (including χχ̄). The nucleon
  coupling is g_N = g_q f_N m_N / v with f_N = 0.307, so a scalar-scalar
  model is spin-independent; any pseudoscalar factor makes it
  momentum-suppressed (not compared with the SI/SD envelopes, and said so).
  - **Not computed: χχ̄ → SS** (t-channel χ exchange). Its rate goes as g_χ⁴,
    with no m_f/v suppression, so its Boltzmann-suppressed tail matters even
    below threshold. Ωh² is therefore computed only for m_χ < (2/3) m_S
    (tail below e⁻²⁰ at freeze-out), and the report says so. This is the
    first extension for the next release.
- **Reading a model** (`classify`): a DM8 or DM12 model is read term by term.
  The two simplified classes above and the explicitly matched portals below
  are supported. Other models are *undetermined*, with the reason.
  Its validity verdict stands, and Path 1 still gives its direct-detection
  limits.

### Typed portal matching (audit M01, 2026-10-05)

`parameter_space/portal_matching.py` maps interactions and their supplied
coefficients, rather than selecting a benchmark from field content alone.
`ModelTerm.coupling` is the **full coefficient in L**, including its sign and
any symmetry factor. The supported maps are:

- **Real scalar Higgs portal:** C S² H†H in L gives λ_hs = −2C, since the
  numerical portal uses V ⊃ λ_hs S² H†H/2. In the broken phase both h S²
  and h² S² must be supplied and give the same λ_hs through coefficients
  −λ_hs v/2 and −λ_hs/4. The Higgs mass remains 125.09 GeV.
- **t-channel partner:** the chiral Yukawa plus its Hermitian conjugate
  supplies y directly. The SM field must identify one right-handed flavour
  (u, d, b, e, μ or τ), with matching charges. A three-generation `uR` or
  `eR` field is not an up-only or muon-only interaction.
- **Dark photon:** the explicit dark current supplies its effective
  coupling; the hypercharge-mixing coefficient is C = −ε/(2 cos θ_W).
  Complex-scalar dark matter also requires the gauge-related X²χ*χ
  coefficient g_χ². Gauge charges without a current value do not specify g_χ.

Each mapped coefficient and each permitted default is reported separately.
Defaults apply only to omitted masses or a supported bare symbolic coefficient
whose declared value is absent. Explicit zero, sign and flavour are preserved;
invalid coefficients and nonpositive/nonfinite masses cannot become defaults.
Scalar self-quartics stay in the typed model and are identified as absent from
the portal's tree-level annihilation to other particles and scattering.

Additional nonzero or unspecified interactions require a fuller calculation.
In particular, a general singlet scalar potential does not determine the
mass-eigenstate mixing angle and self-couplings used by `SingletMixing` without
an explicit matching. Such inputs return an actionable unsupported reason.
Choosing a portal library benchmark explicitly still selects its documented
parameters and approximations.

The simplified classes require a universal quark current, expressed as generic
q or all six named Dirac flavours with equal coefficients. A partial flavour
set, a chiral or flavour-changing current, or an extra unrepresented interaction
is unsupported. Scalar Yukawas must be linear in each fermion's own mass;
an explicitly supplied electroweak scale is retained in the mapped coefficient.
Generic l in the spin-1 benchmark includes its fixed left-handed neutrino
completion, which the mapping reports. Explicit charged-lepton-only currents
cannot silently acquire that completion.

## 2. Scans (`limits.py`, `scan.py`)

- **The grid:** two parameters (masses or couplings; log or linear axes), the
  others fixed. At most two worker processes.
- **Mass relations (audit M02):** grid points and reconstructed contour points
  use the same constructor: fixed values, then the two axes, then
  m_med = `mediator_ratio` × m_χ if requested. The ratio must be positive and
  finite. The axes must differ, and m_med cannot also be an independent axis
  when that relation determines it. The relation is retained when constraints
  are evaluated again at a crossing and when a scan is saved and reloaded.
- **Direct detection** at a point compares every non-zero channel of the model
  (SI, SD on the proton, SD on the neutron) with the system's own modules at
  that mass, computed at 95% by each module's statistical procedure, only
  inside its native-curve validated range (`parameter_space/dd_channels.py`;
  R2, 2026-10-10). Native 90% curves remain separate.
  - Any channel above its limit excludes the point.
  - If none is above, and a non-zero channel has no validated limit at the mass, the point is pending, with
    the channel named. Before R2, such a channel was dropped silently: the axial class A1 compared SD on
    protons only, and a portal with both SD channels kept only the one that had a limit.
  - SI couplings with c_p ≠ c_n are compared module by module, with each target's Z/A.
  - At a mass validated only by DM3's edge clause, a module's limit is floored at the published curve.
  - The two SD channels are compared per module, with the proton–neutron interference in each target: each
    published SD limit assumes the other nucleon's coupling vanishes. A module validated for both kinds uses
    Tovey et al.'s band. A module validated for one kind only (CRESST-III SD-n, PICO SD-p, CDMSlite) has its
    row scaled by its own rate ratio, F = rate(c₄ᵖ, c₄ⁿ)/rate(its published coupling alone), computed from its
    expected signal (`dd_channels.single_kind_factor`; the approach chosen by the owner, 2026-10-12).
  DIAMX inference results are cached by confidence level, spectrum and backend
  identity; template generation is serialized across workers.
- **Gamma rays (Fermi-LAT dwarfs):** a supported pure prompt channel only,
  halved for Dirac dark matter. Mixed, off-shell and cascade spectra need a
  spectral calculation; channel ratios are not summed.
- **The Sun (IceCube):** the capture rate times the equilibrium fraction
  against the rate IceCube's native 90% limit allows (DM7), shown separately.
  A 95% comparison remains pending without a source likelihood.
- **Colliders (CMS):** CMS's curated summary, only where the model is one of
  its benchmarks; elsewhere *not applicable*, and the verdict marks a contour
  point with a mediator below 10 TeV that couples to quarks as *pending a
  recast*.
- **Perturbativity:** any coupling above √(4π).

## 3. The verdict (`verdict.py`)

- **The thermal assumption:** the dark matter is a freeze-out relic, so the
  model is decided on the contour Ωh² = 0.12 × (its intended fraction).
  Adjacent grid brackets are refined using the actual relic solver, preserving
  scan relations. Every accepted root stores Ωh², target, convergence and
  `abs(omega/target - 1) <= 0.01`; internal coordinate tolerance is 1e-10.
  Exact target endpoints/plateaus survive. Every constraint is re-evaluated
  there. Theory-error band points are labelled separately from certified roots.
- **Each contour point** is:
  - *viable*: every applicable constraint is computed and allows it;
  - *pending*: everything computed allows it, but an applicable constraint is
    not computed there;
  - *excluded*: named by the constraints that exclude it.
- **The model's verdict:**
  - VIABLE if any point is viable;
  - VIABLE, PENDING A CALCULATION if none is viable but some are pending;
  - EXCLUDED if all resolved samples are excluded and no root/coverage is unresolved;
  - PENDING if relic calculations/refinement or sampling remain incomplete;
  - otherwise all computed grid samples are above/below the target, with no
    root resolved at this resolution. Unsampled narrow features are not ruled out.

## 4. Plots and the Track 1 report (`plots.py`, `orchestrator/track1.py`, `adroit track1`)

- **Plots:**
  - the plane, with each constraint's excluded region, the thermal contour,
    and certified contour points coloured by status; the interpolated grid line
    is explicitly labelled as an interpolation, not a root certificate;
  - direct detection along the contour against the new 95% calculation and
    the separately labelled native 90% envelope.
- **The report:**
  - the model and its DM12 audit;
  - the verdict, with what was fixed and scanned;
  - the plots and the contour table (status, what excludes it, what is still
    to compute);
  - what was and was not computed;
  - the literature:
    - the curated records each constraint uses;
    - prior work from an arXiv search, with titles as arXiv returns them (no
      network: the report says the search could not be made).
- **Command:** `adroit track1 MODEL.yaml --x m_med:10:10000:log:24 --y m_chi:1:2000:log:24`
- **Not yet built from the plan's list** (later releases):
  - projected sensitivities;
  - the neutrino fog (no curated record yet);
  - uncertainty bands on the excluded regions.

## 5. The gate (declared 2026-10-03, before its first run)

Run by `docs/dm13/gate.py` ($0; MadDM for G2). Grids are 20 × 20, m_med from
10 GeV to 10 TeV and m_χ from 10 GeV to 2 TeV, both logarithmic.

- **G1: direct detection agrees with DM7.** For each of V1 and A1 at
  m_DM = 10, 100 and 300 GeV, the largest mediator mass the scan's direct
  detection excludes is within 15% of DM7's combined picture:
  - V1: 31, 37 and 30 TeV;
  - A1: 420, 440 and 350 GeV.
- **G2: the new scalar class agrees with MadDM.** At three points, Ωh² from
  `ScalarClass` agrees within 20% with MadDM run on ADROIT's UFO files of
  DM8's scalar-mediator model (G3). MadDM's g* bookkeeping alone moves Ωh²
  by about 10% (DM8). The points are
  (m_χ, m_S) = (100, 500), (200, 500) and (300, 1000) GeV.
- **G3: verdicts that match the literature:**
  - (a) the Working Group's V1: the whole relic contour excluded;
  - (b) A1: not wholly excluded, and CMS excludes every contour point with
    200 GeV < m_med < 1.8 TeV inside its source plane. Points beyond its
    existing 0.5% frame guard must carry the source-edge flag and a pending
    collider cut; they cannot be called viable from that missing cut;
  - (c) a pseudoscalar mediator with Yukawa-like couplings (g_χ = g_q = 1):
    - direct detection excludes no contour point;
    - its c/b (and, above threshold, top/cascade) mixture cannot inherit a
      pure-bb̄ Fermi-LAT limit. Every contour point retains pending spectral
      coverage, with the actual channels saved. M05's pure-channel tests
      separately retain valid pure-bb̄ comparisons. This replaces the original
      80% expectation, which depended on the unsupported mixed-spectrum recast;
  - (d) The historical G4–G10 typed inputs are reported UNDETERMINED,
    with a reason. G4's cubic-only Higgs input labels h as a new mediator,
    uses 125.25 GeV and omits the gauge-related h²S² interaction. M01 must
    not silently substitute the Higgs benchmark for that input. The canonical
    scalar Higgs-portal typed model is separately required to map successfully.
- **G4: complete reports.** The Track 1 reports of the three models in
  `docs/dm13/` (vector, axial, scalar mediator) each hold:
  - validity;
  - the verdict;
  - the plane plot;
  - the computed and not-computed list;
  - the curated literature;
  - the arXiv search's result, or why it was not made.

## 6. The gate's result (2026-10-03): passed except G3(b), missed by one point

The historical results below retain their original interpretation. On
2026-10-05 the executable gate was corrected to test the already accepted
source-frame policy separately from interior exclusions, and to recognise
the now-supported scalar Higgs portal. This changes neither a contour nor
an exclusion tolerance. The old frame point's recomputed Ωh² is 0.112294,
so it also fails the new 1% thermal-root certificate and is not reused as a
certified crossing.

Run once, as declared ($0; record in `docs/dm13/gate.md` and `gate.json`).

- **G1: passed.** The scan's direct-detection boundary agrees with DM7's to
  within 5%:

  | model | m_DM = 10 GeV | 100 GeV | 300 GeV |
  |---|---|---|---|
  | V1 (TeV), scan / DM7 | 30.6 / 31 | 35.2 / 37 | 29.9 / 30 |
  | A1 (GeV), scan / DM7 | 423 / 420 | 440 / 440 | 352 / 350 |

- **G2: passed.** The new scalar class agrees with MadDM (ADROIT's UFO files of
  DM8's scalar-mediator model) to within 1.4%:

  | (m_χ, m_S) GeV | MadDM Ωh² | ADROIT Ωh² | ratio |
  |---|---|---|---|
  | (100, 500) | 141 | 141.0 | 1.000 |
  | (200, 500) | 0.0521 | 0.0528 | 0.987 |
  | (300, 1000) | 0.401 | 0.402 | 0.996 |

- **G3:**
  - (a) passed: V1 is EXCLUDED on its whole relic contour;
  - (b) **not met as declared**: A1 is not wholly excluded (VIABLE, PENDING),
    but CMS excludes 27 of the 28 contour points with
    200 GeV < m_med < 1.8 TeV, not all of them;
  - (c) passed: for the pseudoscalar mediator, direct detection excludes no
    contour point, Fermi-LAT excludes 9 of 9 below m_χ = 50 GeV and 0 of 14
    above 200 GeV;
  - (d) passed: DM8's G4–G10 are all UNDETERMINED, each with its reason.
- **G4: passed.** All three reports are complete, each with both plots.

**The miss in G3(b).**
- **Where:** the 28th point is (m_med, m_χ) = (1651, 2000) GeV. It lies on
  the upper branch of the relic contour (m_χ > m_med, where annihilation into
  two mediators opens), exactly on the scan's top edge.
- **Why:** that edge is also the frame of CMS's summary plane (m_DM ≤ 2 TeV).
  The digitised exclusion regions end at the frame, so the point fell just
  outside them and was reported "outside every observed exclusion".
- **The physics:** at m_χ > m_med/2 the dijet searches' reach does not depend
  on m_χ, so CMS's figure resolves nothing about the frame itself.
- **The fix:** points within 0.5% of the plane's frame are now outside the
  plane, so they are *pending* a recast, not *allowed*
  (`constraints/verdicts.collider`). The point is still not CMS-excluded,
  so G3(b) stays missed as declared. The verdict's logic never called the
  point viable: its direct detection is beyond PICO-60's validated range,
  so it was pending either way.

**The owner's decision (2026-10-03).** The miss at the top edge is
accepted: such points are to be flagged as unreliable, since the figure's
kinematic reach does not resolve them. Now built:
- **Which points are flagged:** a parameter point of a CMS benchmark model
  within 3% of the summary plane's edge (in ln m_med at 40 GeV and 10 TeV,
  and in m_DM below 2 TeV).
- **What the flag does:**
  - the point carries the flag (`verdicts.near_frame`, `EDGE_FLAG`);
  - the verdict's summary counts the flagged points;
  - the contour table marks them ⚠ and explains the flag;
  - the plane plot rings them with an open diamond.
- **What it does not change:** the point's status. At A1's point (1651,
  2000) GeV the status is still *pending* (on the frame itself). At
  (1624, 1966) GeV it is *excluded* by CMS, now with the flag.

**Changes since the gate (2026-10-03, with the portal library):**
- The scalar mediator class now computes χχ̄ → SS (t- and u-channel χ
  exchange, from the explicit amplitude). The restriction m_χ < (2/3) m_S of
  section 1 is lifted. The validation of the portal library (P2b) compares the
  new channel with MadDM.
- `classify` now also recognises the portal library's models. DM8's G4 (the
  scalar Higgs portal), reported UNDETERMINED in G3(d), is now computed as the
  library's scalar singlet. The gate's record is unchanged: it holds for the
  code as it was then.

**Audit correction (2026-10-05).** The historical G4 input cannot be mapped
to the canonical scalar Higgs portal: it supplies only the cubic hSS term,
labels h as a new mediator, and uses a different Higgs mass. It therefore
returns UNDETERMINED under the explicit interaction mapping. The library's
canonical scalar Higgs portal remains supported; G3(d) checks both results.

# The halo region: direct and indirect limits over the local halo's uncertainty

The owner's specification of 2026-10-19. Every Track 1 point (and Explain a signal's Track 1 plane) is evaluated
over a declared region of the Standard Halo Model's parameters, not at one halo. A point is **excluded** only if it is
excluded throughout the region, **allowed** only if it is allowed throughout it, and otherwise **pending**: either
*halo-sensitive* (the classification changes across the region; the classification at the region's centre is shown as
the nominal) or *halo coverage incomplete* (a halo of the region could not be evaluated). The region is on by default;
`--halo published` (or the setting `ADROIT_HALO_REGION=published`) keeps each experiment's published halo instead,
the **published-halo reproduction**, which is what each experiment module was validated against.

## The region

The preset (`halo_region.HaloPreset`; the owner's working priors, not a published joint measurement, the three treated
as independent, a declared approximation):

| parameter | distribution | central 68% | sources of the centre and width |
|---|---|---|---|
| ρ₀ | log-normal, median 0.40 GeV cm⁻³, σ_ln = 0.35 | 0.28–0.57 | McMillan (arXiv:1608.00971) 0.38 ± 0.04; Söding et al. (arXiv:2506.02956) 0.50 ± 0.15 |
| v₀ | Gaussian, 233 ± 20 km s⁻¹ | 213–253 | McMillan |
| v_esc | Gaussian, 528 ± 30 km s⁻¹ | 498–558 | Deason et al. (arXiv:1901.02016) 528 +24/−25 |

In the standardised coordinates (ln ρ₀, v₀, v_esc) the region is the ball of probability 0.95, radius
r = √χ²₃(0.95) = 2.796. Its 95% belongs to the halo region: it is not an experiment's confidence level, and no
overall 95% statement is made. The ball is finite, so nothing is minimised over a tail. At the central velocities it
spans ρ₀ = 0.15–1.07 GeV cm⁻³; on its boundary, v₀ = 177–289 and v_esc = 444–612 km s⁻¹ (all physical).

Within the Standard Halo Model the local circular speed moves with v₀ (v_LSR = v₀), and the laboratory velocity
(with the Sun's peculiar and the Earth's velocities) follows. Velocity-dependent spectra and limits are recomputed;
the density is never used to stand in for v₀ or v_esc. **Not covered:** changes of the velocity distribution's shape
(anisotropy, debris), streams and the Large Magellanic Cloud (which matter most for high recoils and endothermic
scattering; Das et al., arXiv:2609.35737, in the owner's specification), and for the Galactic searches the halo
profile's shape beyond ρ₀.

## Sampling

Every halo-dependent constraint strengthens with ρ₀, so at each velocity sample a point is evaluated at the two ends of
the density interval the ball allows there, ln ρ₀ = ln 0.40 ± 0.35 √(r² − d²) (d: the sample's standardised distance).
The velocity samples: the centre, the four extremes of v₀ and v_esc and the four diagonals on the boundary, and twelve
interior points from a scrambled Sobol sequence (fixed seed). A classification that holds throughout is checked again
with twelve further interior points; a sample that differs makes the point halo-sensitive (`converged` is recorded).

## What depends on the halo

- **Direct detection:** every module's 95% limit at each halo (`halo_limits`). The density is analytic: at fixed
  velocities every module's limit is ∝ 1/ρ₀, whatever its likelihood. The fast modules (CRESST-III, DEAP-3600,
  PICO-60) run their own procedure at each sample's velocities. The slow ones (LZ, XENONnT and PandaX-4T through DIAMX;
  CDMSlite's median over efficiency realisations) use a **validated count ratio** (below).
- **Capture in the Sun (IceCube):** the model's capture rate at each halo, against IceCube's bound on the annihilation
  rate, which does not move.
- **Galactic-halo indirect detection** (γ-ray lines from Fermi-LAT and H.E.S.S., AMS-02's antiprotons): each limit on
  ⟨σv⟩ is rescaled from the local density its record states to ρ₀, by (ρ_record/ρ₀)²
  (`constraints/data/local_densities.yaml`). Dwarf galaxies keep their own J-factors; the CMB, colliders, the relic
  density and the theory certificates do not depend on the local halo.

The whole point is evaluated at each common halo: no experiment is given a halo of its own. A halo-independent
exclusion (a collider search, say) excludes throughout.

## The slow modules: a validated count ratio

The owner's six conditions:

1. **Density analytic:** limits are ∝ 1/ρ₀; only (v₀, v_esc) need work.
2. **Accepted counts after the detector response:** L_h = L_ref · (ρ_ref/ρ₀) · N_ref/N_h, with N the signal counts the
   analysis accepts at unit reference cross-section. For a xenon search, the sum over its runs of exposure ×
   ∫ ε(E_R) dR/dE_R dE_R with each run's published efficiency curve (DIAMX's data); the module's own `total_events` is
   the recoil spectrum before the detector response and is not used. For CDMSlite, its best-fit-efficiency signal.
3. **ADROIT's own 95% limit** at the module's reference halo is what is scaled (its table or its direct calculation),
   never a published 90% curve.
4. **Validated per analysis and per interaction** at points declared before the full calculations ran
   (`parameter_space/data/halo_validation_points.yaml`: three masses per module and kind, seven halos including the
   region's boundary extremes), against the module's full procedure at each halo (`scripts/validate_halo_count_ratio.py`
   → `data/halo_count_ratio.yaml`). A module and kind is used only between its lowest and highest validated masses,
   and only if its largest discrepancy e there is at most 15% (the declared gate). Validation for elastic SI does
   not cover SD, and none covers other operators. An entry is used only if all of it holds (the audit's PX-06):
   every declared checkpoint present, each with finite positive reference, full and ratio limits (a NaN fails the
   entry); the declaration's sha256 and gate; e recomputed from the points; the inputs it was computed from (the
   module's own, as its limit tables fingerprint them, and the accepted-count code: `halo_limits.inputs_sha256`);
   and a halo inside the ellipse its boundary checkpoints span. A custom region outside it takes the full route.
5. **Full calculations where they matter:** a comparison the ratio decides must hold with every count-ratio limit at
   either end of its margin (the table's tolerance and 2e): excluded with all of them at their weakest, or not
   excluded with all at their strongest. Otherwise direct detection is undecided at that halo, whatever the central
   value says, and no exclusion of the point there stands in for it (the audit's PX-01: 42 marginal samples had been
   called "excluded throughout"). Then, or outside the validated masses, the module's full procedure at that halo
   decides, within the point's budget (`HaloPreset.full_calculations`, two by default). Every distinct calculation the
   point needs counts once, cached or not, so a point's result never depends on what another point computed first;
   one velocity calculation serves both ends of a density interval; a reference limit the count ratio needs without
   a current table is a budgeted full calculation too (PX-05). If the decided halos already differ, nothing more is
   computed: the point is halo-sensitive. Beyond the budget the module gives no limit at that halo, and the point's
   halo coverage is incomplete.
6. **Scope:** e is an empirical estimate at the sampled checkpoints, not a bound. A count ratio is a cut only: it never
   enters a significance, a fit or the combined likelihood (there, a comparison from a count ratio is applied as a
   cut, and only exactly computed ratios are combined). Exactness is decided per halo: direct detection's ratio there
   is combined only if no limit taken at that halo came from a count ratio, and each limit's construction is kept by
   module, interaction and mass, never by module alone (PX-03). A halo's combination uses the confidence level and
   sidedness of the limit deciding there, which can be another experiment's than at the centre (PX-04); a sample saved
   without them keeps direct detection as a cut and says so.

**A limit must be a number** (PX-02). A module's limit at a halo that is not finite and positive, or a procedure that
fails, leaves the module without a limit there: the halo is unresolved and, unless the budget resolves it, the point's
coverage incomplete. An infinite limit stands only where the analysis accepts no signal at all at that halo (zero
accepted counts: the module cannot see the point); non-finite accepted counts are an error.

## The validation's result

`scripts/validate_halo_count_ratio.py` at the declared points, every checkpoint kept in `data/halo_count_ratio.yaml`
(each entry with its declaration's and inputs' identities). First run on 2026-10-19 (`--summarise` after the PX-06
repair); every entry recomputed since with the stored tables whenever their fingerprint moved (last on 2026-11-13, at
the DX round, `d9cffc1`, and its xenon entries again for DY-03, `2798379`, every number the same). The table below is
the stored validation as the code reads it at 1.0.0 (the audit loop's AL1-15, 2026-11-14: it had shown the first run's
figures). The gate is the declared one, e ≤ 15%, and is not moved.

| module | kind | validated masses (GeV) | e | gate | where it is worst |
|---|---|---|---|---|---|
| CDMSlite Run 2 | SI | 1.5–20 | 45.8% | failed | 1.5 GeV, v₀ and v_esc both low (ratio too strong); 5 GeV 41.6% (too weak) |
| CDMSlite Run 2 | SD-proton | 1.5–20 | 90.3% | failed | 1.5 GeV, both low (too strong) |
| CDMSlite Run 2 | SD-neutron | 1.5–20 | 90.3% | failed | 1.5 GeV, both low (too strong) |
| LZ WS2022+WS2024 | SI | 10–90 | 40.1% | failed | 10 GeV, low v₀ (too strong); 90 GeV 12.9% |
| XENONnT SR0+SR1 | SI | 30–1000 | 21.2% | failed | 30 GeV, low v₀ (too weak); 150 GeV 9.4% |
| XENONnT SR0+SR1 | SD-proton | 25–5000 | 15.6% | failed | 25 GeV, low v₀ (too weak) |
| XENONnT SR0+SR1 | SD-neutron | 25–5000 | 12.6% | passed | 25 GeV, low v₀ |
| PandaX-4T Run0+Run1 | SI | 150–9000 | 1.3% | passed | |
| PandaX-4T Run0+Run1 | SD-proton | 150–1800 | 5.7% | passed | |
| PandaX-4T Run0+Run1 | SD-neutron | 350–10000 | 3.0% | passed | |

**Where it fails.** At the region's centre the ratio is within 3.7% at every checkpoint but CDMSlite's 5 GeV (7.4–7.7%).
It fails at the lowest validated masses and the lowest v₀ (177 km/s, the region's boundary): the recoil spectrum moves
towards the threshold, where the efficiency falls and the backgrounds differ, and a likelihood in (S1, S2) or in
energy responds to the spectrum's shape, not only to its accepted count. The error goes both ways: the ratio's limit
is too strong at CDMSlite's 1.5 GeV and LZ's 10 GeV, too weak at CDMSlite's 5 GeV and in every XENONnT failure.
PandaX's validated masses begin at 150 GeV, far from its threshold.

**What follows, as declared.** A failed entry is not used: every comparison it would decide at a halo other than the
module's own takes the module's full procedure there, within the point's budget (two by default), and beyond the
budget the module gives no limit at that halo and the point's halo coverage is incomplete. Near a boundary, a point
whose verdict rests on CDMSlite, LZ or XENONnT (SI, SD-proton) at these masses will often be "halo coverage
incomplete". The options (a larger budget, a count ratio refined in recoil energy with a newly declared gate, or the
incompleteness stated) are the owner's.

## Not varied yet (halo coverage incomplete)

A structure compared through Path 1 (`operator_limits`) and a flavour-vector model's own direct-detection limit keep
their published-halo comparison, so a point that depends on them is pending (halo coverage incomplete). A private
spin-independent curve and a private search hold only their paper's halo: a run over the region with either is refused
(use `--halo published`).

## Envelope, not profile likelihood

The region's classification is an envelope: it asks whether a point is excluded at every halo of a declared region,
and ignores how probable each halo is within it. It is not a profile likelihood, in which a halo constraint term would
be profiled consistently in the numerator and the denominator of each test statistic; that is a separate option, to be
built and validated later, and neither is ever labelled as the other.

## The halo choice (halo phase 1, 2026-11-10)

The region is one of three treatments of one shared choice (`adroit/core/halo_choice.py`; the inventory of every
consumer: `docs/halo_constraint_support.md`):
- **the region** above, Track 1's default and Explain a signal's for its constraints and plane;
- **the published halos**, each experiment's and record's own (`--halo published`), Track 2's reading unless asked
  otherwise;
- **a fixed common benchmark** (`--halo benchmark`, with `--halo-family shm`, the default): the SHM at the recommended
  conventions of arXiv:2105.00599 (ρ₀ = 0.3 GeV cm⁻³, v₀ = 238, v_esc = 544 km/s, v_LSR = v₀, the Sun's peculiar
  velocity (11.1, 12.2, 7.3), the Earth's on 9 March). Every comparison able to use it is calculated at it:
  - direct detection: a module whose published halo it is (the xenon searches) by its own published procedure; the fast
    modules by their procedure there; CDMSlite by its full procedure within the point's budget;
  - capture in the Sun, in its Sun frame;
  - the Galactic searches, their profiles kept and their density rescaled.

  In Track 2 the fit, the toys, the null limits, the flags, the complementary verdicts and the eligibility points all
  use it. A structure compared through Path 1, a flavour-vector model's own limit, a private curve or search, and the
  native joint fit cannot, and are named (pending, or refused at launch). It is not a confidence interval: the halo's
  uncertainty is not propagated.

SHM++ is built as a fixed benchmark only (halo phase 2; [`halo_shmplusplus.md`](halo_shmplusplus.md)). SHM + LMC is
listed and refused until halo phase 3 builds and validates it, which is deferred to a later release (the owner,
2026-11-13: the benchmark's data are not public); nothing is calculated under its name. A request records its
choice. A saved result records its resolution (numbers, frame, time convention and the halo data files' identities),
and every page, report, export and certificate shows and binds it. A result saved before the choice existed reads as
it was calculated, with the published halos.

## Where it shows

The report states the region (or the published halos); each point carries its label (excluded or allowed throughout
the tested halo region, halo-sensitive with its nominal, or halo coverage incomplete), and the point inspector and
`points.csv` show the reason. The saved evaluation keeps every sample (`PointResult.halo`), so the verdict classifies a
saved point without new physics.

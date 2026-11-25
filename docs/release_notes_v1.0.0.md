# ADROIT 1.0.0: release notes

The first public release of ADROIT, the Agentic Dark matter Reinterpretation and Operator Inference Toolkit. Licence:
BSD-3-Clause (`LICENSE`). How the code was validated and audited before release is in
[`validation_and_audits.md`](validation_and_audits.md).

## What it does

- **Direct detection for any interaction** (DM0–DM6): the non-relativistic operator basis, nuclear responses,
  experiment modules each validated against its published limit inside a stated mass range, exclusion limits (Path
  1) and signal fits with global significance (Path 2).
- **Two tracks for a model** (DM12–DM15): Track 1 judges a model on its thermal-relic contour against every
  applicable constraint (six verdict levels, README); Track 2 asks which models explain an anomaly, with recursion.
- **The portal library:** benchmark models from the literature, each validated, with the searches applied point by
  point (SModelS, micrOMEGAs, recasts, γ-ray lines, antiprotons, the CMB, DarkCast).
- **Any freeze-out model** (G0–G12, [`freeze_out_build.md`](freeze_out_build.md)): a model no engine covers is
  computed from its own Lagrangian — mass basis, Feynman rules, tree-level processes, relic density with
  coannihilation and poles, direct detection, annihilation today, the Sommerfeld effect and bound states, the LHC.
  Library-first: a validated engine is used where it applies; every result names its route.
- **Language models propose, code decides:** intake of a model from words, TeX, a figure or a paper's equation;
  a plan; a paper's benchmark numbers with their verbatim quote; a draft for a missing piece. Every proposal is
  checked deterministically, every paid call is budgeted and journalled, and no number from a language model
  reaches a verdict unchecked.
- **The workbench** (NiceGUI): the model library, both tracks, records review, saved studies and reanalysis. Every
  page says what it does and what comes out; a model's fields can be entered as a form or as YAML; the halo is chosen
  beside every model; "AI can make mistakes." stands under every model choice of a live call.

## Records

48 constraint records (`adroit records list`), every one verified and signed by the owner. The candidate's 38 were
verified against their sources (R9, 2026-10-13; two re-verified on 2026-10-17). The ten added since were verified on
2026-11-06 and 07: CMS's and ATLAS's Z → 4μ, LHCb's B → K μμ, the electroweak S and T, LEP's charginos, OPAL's
sleptons, b → sγ, B_s → μμ, N_eff and DAMPE's γ-ray lines (DAMPE's two-line assumption corrected on 2026-10-25 to the
50% guard the evaluator applies, before signing: CA-09; N_eff, LHCb's map and b → sγ repaired after the owner's
review, before signing: the record review repair record of 2026-11-06). A record not yet
verified leaves its search pending unless a run asks for `--unverified`, and says so. Some stored values are
approximate, digitised or borrowed from another analysis: unsigned audit notes mark them
(`adroit/constraints/data/audit_notes.yaml`, the external audit's item 18), apart from the signed records, and a result
that rests on one shows the note beside it with how good the result is. The owner decided each on 2026-10-17
(the audit proposals of 2026-10-16): where the approximation is an O(1) uncertainty
the result is stated as good up to an O(1) factor; CCFR's heavy limit is the figure's 567 GeV; ATLAS's Gaussian
dijet limits decide by ATLAS's own truncation recipe, validated against its Breit–Wigner Z′. Those two records'
signed content changed, and the owner re-verified both on 2026-10-17.

## Scope and limits

The README's "Scope and limits" section is the full list. In short:
- thermal freeze-out only; nuclear recoils only; LO collider cross-sections with stated K-factors; 95% CL hard cuts
  with each search's own confidence level kept where its conversion is unsafe;
- **the standard halo model over a declared region by default:** a Track 1 point is excluded only if excluded at
  every halo of the region, allowed only if allowed at every one, otherwise pending, halo-sensitive; `--halo
  published` uses each experiment's published halo, the setting its module was validated in; no fit profiles the
  halo ([`halo_region.md`](halo_region.md)); `--halo benchmark` calculates every comparison able to use it at one
  fixed common benchmark, the SHM at arXiv:2105.00599's recommended values, or SHM++ with `--halo-family
  shm-plus-plus` (arXiv:1810.11468; no annual modulation or directional rates;
  [`halo_shmplusplus.md`](halo_shmplusplus.md)), names the others pending, and does not propagate the benchmark's
  uncertainty; an LMC-affected benchmark is listed and refused, deferred to a later release
  ([`halo_constraint_support.md`](halo_constraint_support.md));
- **the generic route:** tree level, with the Sommerfeld effect and bound states where its group theory allows; a
  new field of several generations written as that many mass eigenstates, and a second stable component or an
  uncertified conversion refused ([`generic_route_generations.md`](generic_route_generations.md)); the library's
  resonance, light-vector and LEP searches applied to a generic model's states that meet each record's conditions,
  the others undecided, named ([`generic_route_searches.md`](generic_route_searches.md)); γ-ray lines decided only
  where resummed, with a theory band (D30) that has no upper edge for n ≥ 5 (D32); LHC production at LO, an
  approximation, not a bound;
- **undecided where a calculation's validity ends** (the external audit of 2026-10-16): a relic density resting on
  the thermal history below 1 MeV (A06); a monojet recast within five widths of the threshold (A07); a coloured
  partner's LHC limits from QCD-only production (D33); the generic route's three regimes of O(1) disagreement, where
  a verdict stands only if it survives the relic target rescaled by 2.5 either way (D35; its thresholds were chosen
  after the held-out results, so those regimes are no longer tested blind, and only the three regimes seen are
  recognised: `freeze_out_build.md` §9);
- **ε is DarkCast's** (D29): a dark photon couples to the electromagnetic current as ε e(0) Q;
- **installed from a source clone only** (D34): `uv sync --locked` in a clone of the repository; no wheel or PyPI
  package;
- **a local, single-user workbench** (D36): on 127.0.0.1; imported UFO and Python model files are trusted code;
  coupling formulas are checked before SymPy reads them; papers and model descriptions are data, never
  instructions; isolation and resource limits come before any hosted or multi-user use.

## Known limits and deferrals

**Deferred with the owner's sign-off:**
- T2-5 (R6): normalising the smeared signal shape at threshold. **Fixed since** by the external audit's A09
  (2026-10-16): the shape is normalised on the window as seen and the fitted count is the count seen inside it;
  the signed "under 0.01σ" concerned CDMS II Si only and did not bound an uploaded spectrum. Remeasured on CDMS II
  Si over the library space (748 candidates, the same 200,000 toys): global Z 2.765σ → 2.754σ, the largest local Z
  3.026σ → 3.063σ, fitted couplings up to 2.5% higher at 8.6 GeV and 17% at 5 GeV, where 21% of the window's
  events are smeared below its threshold;
- R-20: the full σ(pp → φφ*) of coloured t-channel partners (`docs/benchmark_limits.md`);
- R-21: M29–M31, the post-release inference programme (the broader extension plan);
- **the report review, to 1.1** (the owner, 2026-10-27): an opt-in final pass in which a model of the person's
  choosing reads a finished study's report with its evidence. It either finds no issue or flags statements to
  consider: a limit that may be out of date, a constraint that may be missing, a possible factor in a value another
  model produced. It is advisory only: it never changes a verdict, badge or certificate, and it cites nothing from
  memory. The agreed design is in the report review plan.
- **versioned scientific outputs, to 1.1** (the owner, 2026-11-03): completed results published immutable with their
  evidence and a hash inventory, every page, command, export and action given one resolved version, rerenders and
  resumes as new revisions of the calculation they present, live operational state kept separate, and older results
  read through an adapter. The rule: resolve a version once, then use that exact version for everything displayed,
  downloaded, exported or continued. The guidance and its limits are in
  the versioned outputs plan. The shared version handle it relies on is built before 1.0.0
  (the owner, 2026-11-03; the version handle plan; built 2026-11-04,
  the version handle build record of 2026-11-04).
- **a review of the workbench's navigation structure, its wording and its plots, to a later release** (the owner,
  2026-11-07): the workbench's appearance pass is static styling only (its palette, typography, panels, buttons, links
  and tables; the workbench appearance record of 2026-11-08). Restructuring the menu,
  changing the interface's wording and restyling the plots were excluded from it, to keep it small enough to check
  from its diff and the pages' screenshots; each is to be reviewed for a future version.
- **the equation of state's uncertainty, to 1.0.2** (the owner, 2026-11-23; the deferred list EOS-01): its band
  across Saikawa & Shirai's 2020 tables needs root tracking across grid cells before it can gate a claim;
- **the findings below the repair level of the audits of 2026-11-18 to 2026-11-23** (the owner): each in
  the deferred list with its repair and test, among them a Settings page (OT-03), stage checklists for
  Signal best fits and Explain a signal (OT-04), a parallel constraint stage (OT-05) and a badge for results over
  20 MB (OT-06);
- **the findings of 2026-11-24, to 1.0.1** (the owner; each in the deferred list with its repair and test):
  - three standard models are not offered for a signal fit, each named under the pickers with what it needs: the
    inelastic dark photon (its scattering is inelastic, and the physical fit predicts elastic recoils; SM-01), the
    CP-violating Higgs portal (its O₁₁ scattering is not computed; SM-02) and the μ_R lepton portal (its loop-induced
    scattering is not computed; SM-03);
  - the Z portals' engine keeps the axial–axial O₄ term only; the full set of operators is a physics decision for
    later (SM-04);
  - the real-browser journeys for the signal-qualified plane and the qualified exclusions (SD-01);
  - labels that say "undecided" or "pending" where the calculation has a central reading (OT-09);
  - higher electroweak multiplets and colour sextets (OT-08);
- **the audit loop's findings below its repair level, to 1.0.1** (the owner, 2026-11-16 and 2026-11-17;
  the deferred list, each with where it is and a repair): three high findings, each needing
  constructed input (cycle 8's AL8-01: an identifier in an HTML link's visible label passes the reference cleaning and
  its gate; AL8-02: an extreme time-zone offset in a damaged run record stops three pages; cycle 9's AL9-01: a generic
  model scanned in a coupling has its CMB velocity scales formed from the coupling as if it were the mass, so a
  two-pole model that should stay undecided is "not excluded"), whether before 1.0.0 or in 1.0.1 the owner's call;
  ten medium and seven low findings; three features (a search for similar models and
  analyses; native fit, withdrawn; the workbench in its own desktop window). What needs the owner's decision is in
  the post-1.0 backlog.
- **the LMC-affected halo benchmark (halo phase 3), to a later release** (the owner, 2026-11-13): listed in the halo
  choice and refused; nothing is calculated under its name. The benchmark its sources define (the Auriga Milky Way
  re-simulated with its LMC: Smith-Orlik et al., arXiv:2302.04281) is published only as figures, and its data are not
  public. Digitising the figures is excluded: boosting a speed distribution into the detector's or the Sun's frame
  needs the particles' directions. Building it waits for the authors' data, with terms permitting their use.

**Precomputed limit tables:** the slow searches' 95% limits (the xenon searches through DIAMX, CDMSlite, PICO) come
from precomputed tables, and any point whose verdict could change within a table's estimated accuracy (at least 1%) is
recomputed directly, so the verdicts are the direct ones wherever a table's error is within that estimate, which is
not a proven bound (nine direct DIAMX limits differed from their tables by up to 1.7%, each within its table's
estimate at that mass; the two beyond the former 0.5% floor by 0.91% and 0.67%).

**Kept as a known limit by the owner** (2026-11-12): DIAMX makes its signal templates for the xenon searches (LZ,
PandaX-4T and XENONnT) by a Monte Carlo that is not seeded, so a new DIAMX generation moves the xenon tables
coherently across their masses: by up to about 9% between two generations
(the DW repair record of 2026-11-11, the DX repair record of 2026-11-12).

**Tools data held for the process** (the DX repair record of 2026-11-12, BI-02): DarkCast's limits
and models are Python modules of the tool, imported once as any library is, so one replaced while the workbench or a
command runs is read after a restart. Saikawa and Shirai's equation-of-state tables are held only once their published
SHA-256 is checked: a running process keeps the published table, and a new one refuses a replaced table. A table that
one evaluation reads in several calls is read as it is at each call, not held to one version for the whole evaluation.

**Signed or decided by the owner on 2026-10-16** (the G12 closure record, the last section):
- **D29 and D30 confirmed**, with their caveats (`docs/freeze_out_build.md` §9);
- **the held-out accuracy:** D'Agnolo et al.'s third splitting, Okada et al.'s B − L and von Harling & Petraki's
  dark QED disagree with their papers by an O(1) factor (×1.25–2.5), recorded as such; Feng et al.'s resonance is
  localised: the paper's relic formula counts one species of the complex scalar, and its targets are compared after
  doubling (D31), which ADROIT meets — a derived convention conversion, not the paper's native target and not a
  blind reproduction (the external audit's A11);
- **the usability and timing sessions with researchers** (R12 item 2): planned for after the release and before any
  announcement or paper submission, then not run: the owner, 2026-10-22, skips them, now and later, unless the owner
  asks for them; neither the release, an announcement nor a paper waits on them;
- **the draft paper's revision** (DM11b): deferred;
- **21 functions** remain longer than the project's 60-line standard, all older code (the six the workbench rework had
  lengthened were split);
- **G10: 31 of 31, an assembled result** (the external audit's item 16): 30 stored results re-scored after the
  corrections, with the comparison repaired since (A02/A03), plus the formerly failed entry re-run ($0.15); 23 of
  them strict. It is not one fresh, independent 31-case pass. **G11: not met**, one quote not verbatim, recorded;
- **the live checks' usability findings: fixed** — the agents rehearse their requests at $0 and refuse a cap too small
  to finish, before any is sent, and a budget stop keeps the finished agents' work; a cited source is accepted when
  its description names the paper; G2 reads the generator's Weyl-form doublet Yukawas. Still open: the builder's
  two-mediator proposals, and its two-doublet quartics, which lack the index contraction G1 needs;
- **the closure table's items, signed as known limits:** DD-8 (sparse validation masses near thresholds), Rep-2
  (`idea` and `lagrangian` results not exportable as evidence; **fixed since**, 2026-10-20: both save their evidence
  and export and verify as bundles, [`evidence_export.md`](evidence_export.md)), R-5 (BaBar's binned B → K limits
  above s_B = 0.3: pending), R-10 (LZ's L12 convention), R-16 (viable-blocking coverage limits, each an honest
  pending); L1b n/a;
- **R-22, rechecked:** FeynRules is reachable again, with its files' physics identical to those installed; the fast
  suite passes under an x86_64 Python (Rosetta); DIAMX builds there but cannot run without AVX, which a real Intel Mac
  has and Rosetta on macOS 14 lacks (jaxlib 0.4.38 ships x86_64 macOS wheels; untested on Intel hardware).

**Independent verification** (the external audit's item 19): the Belle II part of `lmu-ltau-babar-belle2` and
`atlas-1910.08447-dijet-gaussian`, whose numerical sources the audit could not fetch (HEPData returned HTTP 403),
were compared with HEPData value by value on 2026-10-17: 953 of 953 stored values identical
(`scripts/compare_hepdata_records.py`).

## How to cite

Cite ADROIT and every code and data release a result used, including cross-checks: the README's "Citing ADROIT and
its dependencies" gives a LaTeX block, [`citations.md`](citations.md) the full manifest and the generic route's
physics sources, and [`dependencies.bib`](dependencies.bib) the BibTeX entries.

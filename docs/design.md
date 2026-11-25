# ADROIT: the design

ADROIT, the Agentic Dark matter Reinterpretation and Operator Inference Toolkit, relates models of particle dark matter to
data. It offers three workflows over one deterministic physics engine:

- **Track 1, "Constrain a model"** (`adroit idea`, `adroit track1`): a model is scanned over a plane of its
  parameters against every computed constraint and judged on its thermal-relic contour.
- **Track 2, "Signal best fits"** (`adroit signal`): candidate interactions are fitted to the events of a search
  with an excess, combined with the null searches and ranked in a tournament.
- **The single-idea report, "Explain a signal"** (`adroit single-idea`): one model is fitted to an anomaly, and
  Track 1 is then run in a window around its best fit.

This document describes how the system is built and why, as of milestone R11 (October 2026). The milestone records
in `docs/` hold the full account: DM0–DM15 in [`adroit_build.md`](adroit_build.md), the M-series in
[`extension_status.md`](extension_status.md), and R0–R12 in the release plan. Installation and
example commands are in the [README](../README.md). Each number quoted here names, after "run:" in parentheses, the
record or results file it comes from.

## 1. Principles

- **Deterministic physics; language models only read and write.** Rates, limits, fits, significances, relic
  densities, certificates and verdicts come from deterministic code. Optional language models turn words, TeX,
  screenshots and papers into typed drafts for a person to review, choose from fixed menus, search the literature and
  audit assumptions, all behind one interface in `adroit/agents/`, so the rest runs and is tested offline (§12).
- **Exchangeable experiments.** A search is a module with one interface. No pipeline names an experiment, target or
  energy window. LZ's 2026 extended-window event is one test case, not the design centre.
- **Validated before trusted.** A detector module's limit is a constraint only inside the mass range where it
  reproduces its collaboration's published limit; outside that range it is only a flag. A curated record is used only
  after a person has verified it against its source (§8).
- **Pending, never guessed.** A constraint that applies but cannot be decided makes a point pending, with the reason;
  it never becomes "allowed". A point excluded only under a stronger assumption is flagged, not excluded.
- **Provenance.** Every run records its typed inputs, results, cost and calculation dates, as verifiable evidence (§10).
- **External codes are called, not copied.** DIAMX, DirectDM, MadGraph, MadDM, micrOMEGAs, SModelS, DarkCast,
  Yellin's interval code and the data releases are fetched into a tools folder (`ADROIT_TOOLS_DIR`), cited and never
  redistributed; everything there is trusted as code. `adroit setup` lists each item, its status and its licence.
- **Deliberate scope.** Thermal freeze-out, nuclear recoils, the Standard Halo Model by default, leading-order
  collider production, verified records, validated ranges, and no Mathematica.

## 2. How the workflows connect

```
Track 2 (signal) ──promote class:N──► single-idea study ──contains──► Track 1 scan around the best fit
     │                                                                      ▲
     └──────── fitted physical points, judged by Track 1's evaluator ───────┘
idea / fields / Lagrangian / paper / catalog revision ──► either track
any saved study ──reanalyse──► a fresh child run in either track
```

- **Two paths underneath.** Path 1 carries an interaction (a library card or a bespoke Lagrangian) to its limits in
  every detector module (`adroit exclude`, `adroit lagrangian`). Path 2 carries a search's events to the interactions
  that could explain them. Track 1 uses Path 1's direct-detection machinery; Track 2 is Path 2 made general.
- **Recursion.** `adroit promote RUN class:N` turns a Track 2 candidate, or its degeneracy class, into single-idea
  studies of the full models that produce it at tree level. A candidate whose splitting or isospin no computable
  completion reproduces is refused with the reason. With `--budget`, the model builder proposes further completions.
- **Physical eligibility.** Track 2 judges matched fitted physical points with Track 1's evaluator, in eligible and
  provisional views beside the unchanged ranking ([physical_candidate_eligibility.md](physical_candidate_eligibility.md)).
- **The studies tree.** Every run writes `study.json` (kind, inputs, steps, cost, outputs, parent, children). A
  promotion writes its children inside the parent's `children/` folder; `adroit studies` and the workbench's Studies
  page show the tree with the total spent.

## 3. Typed state and conventions

- **Typed data.** Everything passed between modules is a Pydantic v2 model. `core/dm_state.py` holds the physics
  chain (particle, interaction, halo, target → recoil spectrum → likelihood per module → constraint verdicts);
  `core/model_spec.py` holds a model as fields, representations, stabilising parity and Lagrangian terms.
- **Couplings** (`physics/conventions.py`). Nonrelativistic couplings are in the nucleon basis in GeV⁻², with
  c^p = c^0 + c^1 and c^n = c^0 − c^1; a dimensionless coupling is in units of 1/m_v², m_v = 246.2 GeV.
  `ModelTerm.coupling` is the full coefficient in L, with its sign and symmetry factor. Library couplings are kept at
  the level of the Feynman rule, and each portal entry states its convention ([portal_library.md](portal_library.md)).
- **The halo.** The Standard Halo Model, with the Earth's motion of arXiv:2105.00599, unless a tabulated speed
  distribution replaces it (`physics/halo.py`).
- **Confidence levels.** Each limit carries its CL and statistical construction (one- or two-sided). Track 1 applies
  every constraint at 95% CL. A native limit at another CL converts only where the direction is safe
  (`Outcome.at95`): allowed at a native CL ≤ 95% stays allowed, excluded at a native CL ≥ 95% stays excluded, and
  anything else is undecided. Native 90% curves are kept and shown separately.

## 4. The forward model and the detector modules

### 4.1 The recoil rate (DM2; `adroit/physics/`)

For dark matter of mass m_χ (and splitting δ for inelastic or exothermic scattering) and an interaction given by the
coefficients of the operators O₁ and O₃–O₁₅ (isoscalar and isovector, possibly q-dependent),

    dR/dE_R = Σ_T x_T ρ/(2π m_χ) 4π/(2J_T+1) Σ_k Σ_{ττ'} W_k^{ττ'}(q) [ R_k^{ττ'} η(v_min) + R⊥_k^{ττ'} η⊥(v_min) ],

with q = √(2 m_T E_R) and v_min = |m_T E_R/μ_T + δ|/√(2 m_T E_R). Three factors are independent: the particle
physics (R_k, quadratic in the coefficients); the nucleus (the shell-model responses W_k of Anand, Fitzpatrick and
Haxton, Haxton and McElvain's revised densities, or Klos et al.'s SD structure factors where a collaboration used
them; the Helm form factor for other isotopes); and the halo (η, η⊥). Once the reference codes' rounded constants are
corrected, the rate agrees with WIMpy_NREFT to ≤ 1.3 × 10⁻¹¹ and with WimPyDD to ≤ 1.3 × 10⁻³ (run:
docs/dm2_forward_model.md#4. Validation).

### 4.2 Experiment modules (DM3, DM5; `adroit/experiments/`)

- **The interface.** An `ExperimentModule` predicts any interaction's signal in its own observable, sets an upper
  limit on its strength, and declares its collaboration's conventions and published limits. Fidelity A has events and
  a background model (a full likelihood); B has counts, efficiency and background (Poisson); C has a limit curve only.
- **The modules.** CRESST-III (CaWO₄; Yellin's optimum interval through Yellin's code), CDMSlite (Ge; the
  collaboration's procedure), PICO-60 (C₃F₈; a profile likelihood with free backgrounds), DEAP-3600 (Ar; a Poisson
  count), and the xenon searches LZ, XENONnT and PandaX-4T. Searches with events, for Track 2: LZ's extended window
  (2026); CDMS II Si (2013) and CDMS II Ge (2009) as historical records; any anomaly record (`record:<path>`, §6.2);
  reviewed private searches (§11).
- **The xenon modules through DIAMX** (`experiments/xenon.py`). DIAMX (arXiv:2512.05850) holds the three searches'
  public data, detector response and background models. ADROIT computes the recoil spectrum; DIAMX, in its own
  environment, simulates the signal in (S1, S2) and runs the profile likelihood with the backgrounds as nuisance
  parameters, giving alea's two-sided t̃ limits. Templates and results are cached by spectrum and request identity.
- **Validated ranges.** A module is validated, per kind of limit, over a contiguous run of masses where it reproduces
  the published limit within a factor 1.3 (or within a 3% shift in mass where the curve is steeper than
  |d ln σ/d ln m| = 8). The ranges are in `experiments/data/validated_ranges.yaml`. For SI: LZ 8.9–92 GeV, XENONnT
  28–1000 GeV, PandaX-4T only above 147 GeV; XENONnT's SD limits are validated from 21.5 GeV to 10 TeV (run:
  docs/dm3_experiments.md#2. Validation).
- **Validated response structures** (R6). A range validated with O₁ and O₄ spectra does not test other operators or
  splittings. The direct route for another structure needs a structure validated on the same target with the same
  responses, taken from LZ's 43 per-model tables (`experiments/structures.py`, `data/validated_structures.yaml`).
  Until then its limits are labelled unvalidated and left out of rankings.

### 4.3 Precomputed direct-detection limit tables (R10)

The slow modules (the three DIAMX searches, CDMSlite and PICO-60) take seconds to minutes per new mass. For each kind
they are validated for, `parameter_space/limit_tables.py` holds the 95% limit at sixteen masses per decade across the
validated range, each computed directly (`scripts/tabulate_reference_limits.py`), with a cubic spline in
(log m, log σ) between them. The measurements, tables and gate are in [`r10/README.md`](r10/README.md).

- **Accuracy and exact verdicts.** Each table records ε, the largest leave-one-out interpolation error, and is used
  with the tolerance η = max(2ε, 0.5%). `dd_channels.compare` recomputes a point with direct limits whenever its
  verdict could change within η, so the verdicts are the direct calculation's wherever a table's error is within η.
- **Currency.** A table carries a fingerprint of the code, data and external inputs its numbers depend on; a table
  whose fingerprint differs from the installed code's is ignored. `--exact-limits` uses no table, and `--likelihood`
  always uses exact limits.

## 5. The interaction library, Path 1 and Path 2

### 5.1 The interaction library (DM4; `adroit/library/interactions/`)

Interactions are cards in three layers, each reducing exactly to nonrelativistic coefficients (`registry.resolve`):
the 14 operators; the Lagrangians L1–L20 of Anand, Fitzpatrick and Haxton, plus LZ's own forms of L5–L9, L13 and L17
(used only for comparisons with LZ's tables); and 14 mediator models. A neighbour graph joins cards one step apart.
Two interactions are compared by the Jeffreys divergence J between their normalised spectra: N₂σ = 4/J events separate
them at 2σ, and single-linkage degeneracy classes at a chosen N state what a signal can and cannot tell apart.

### 5.2 Path 1: from an interaction to limits (DM5, DM8)

- **A library card** (`adroit exclude`): the upper limit on its strength μ in every module, marked validated or not,
  and their envelope (not a combination). An interaction proportional to a module's SI or SD reference uses the
  collaboration's own procedure, but only with the module's own halo and nuclear model.
- **A bespoke model** (`adroit lagrangian`): a typed `ModelSpec` is checked (gauge invariance and minimal coupling,
  hermiticity, perturbativity, validity of the contact interaction, axial unitarity). Its quark- and gluon-level
  Wilson coefficients are formulas evaluated by SymPy, given by the user or derived by a language model and checked by
  a second, different model (`--derive --budget`). DirectDM runs them to the nucleons, and the result is matched
  against every card. With `--numerical-check`, ADROIT's own UFO writer feeds MadDM as an independent check. The report
  gives the 28-item viability checklist and ends with a contract stating what the computed benchmark dropped.

### 5.3 Path 2: from events to ranked interactions (DM6, DM9, DM10, R6; `orchestrator/signal.py`)

1. **Fit.** Every candidate (the collaboration's own model space if published, else every O and L card, both
   isospins, eleven masses and optional splittings, or the user's models, §6.2) is fitted by an extended unbinned
   likelihood in recoil energy, with signal count s ≥ 0. Where the search states a background uncertainty, its scale θ
   is profiled under a bifurcated-Gaussian constraint in fits, toys and the combination.
2. **Global significance** from background-only toys over the whole model space, with a Clopper–Pearson 95% interval
   on p. A promoted child's global significance is capped by its parent's.
3. **Combination.** Every member of the leading classes (up to 32 per class, every interaction and isospin first) is
   combined with each null search's limit-equivalent likelihood q_i(μ) = 2 s₉₀ (μ/μ_up,i)², giving the joint evidence
   Z_J and the parameter-goodness-of-fit tension χ²_PG.
4. **Flags and verdicts.** Flags for halo and nuclear sensitivity, interaction validity, a coupling above 4π and a
   halo mismatch; a verdict per curated record, recorded beside the ranking and never moving it.
5. **Tournament.** Ranked by AIC = −Z_J² + 2k, with background alone always present. Candidates within ΔAIC ≤ 2 of the
   best are indistinguishable; no such set is formed when the background ranks first.
6. **Forecast:** which target and observable would separate the leading pairs, and how many events they would need.

Required model properties (`--require-style`) restrict the candidate space; preferences (`--prefer-style`) only
annotate it ([model_style_and_paper_intake.md](model_style_and_paper_intake.md)). The native joint likelihood pilot
fits one bounded physical coupling to a signal and a null search together (CDMS II Si with DEAP-3600, or with PICO-60
at low mass; `adroit single-idea --native-joint`, `adroit native-fit`; [native_joint_likelihood.md](native_joint_likelihood.md)).

## 6. The three workflows

### 6.1 Track 1: is a model consistent, and what do the data allow? (DM12, DM13, R5, R8)

- **Inputs** (`adroit idea`): a field content, from which ADROIT's own generator writes every renormalisable gauge-
  and Lorentz-invariant term (and, with `--eft 5` or `6`, the dark sector's effective operators with their validity);
  a Lagrangian, audited for validity and missing terms; or an idea in words (the model builder, paid). Each valid model
  is written as `models/<name>.yaml`; a zeroed coupling is flagged as natural only if a symmetry protects it. A model
  may also come from the personal library or a paper equation (§11).
- **Computable classes** (`classify.py`). A model is read term by term onto a class the engine computes end to end:
  the spin-1 and scalar simplified models, the portal library's classes (§7), explicit flavour-vector currents and the
  complete real Z2 scalar potential ([explicit_model_contracts.md](explicit_model_contracts.md)). Couplings sharing a
  Lagrangian symbol become relations imposed at every point (`relations.py`). A model no class covers is
  UNDETERMINED, with the reason; its validity verdict and its Path 1 limits stand.
- **The scan** (`scan.py`): two parameters on a grid or in adaptive cells
  ([detector_reuse_and_adaptive_scans.md](detector_reuse_and_adaptive_scans.md)), the others fixed, resumable from
  checkpoints. At each point: the relic density, direct detection, every applicable search (§7), perturbativity and
  the theory certificates (§9).
- **Direct detection** (`dd_channels.py`). Every non-zero channel is compared: SI module by module with each target's
  Z/A (a coupling that cancels on xenon is still seen by argon); SD with the proton–neutron interference (Tovey et
  al.'s band, or the module's own rate ratio where it is validated for one kind only); a coloured partner's twist-2
  term with a quantified band ([twist2/README.md](twist2/README.md)). A channel without a validated limit at the mass
  makes the point pending.
- **Indirect detection.** Fermi-LAT dwarfs, IceCube and AMS-02 antiprotons decide channel mixtures by conservative
  rules (`constraints/mixtures.py`): channel ratios summing to at most 1 are allowed (the allowed spectra are convex),
  one channel alone above its curve excludes, and otherwise the search is undecided. Antiprotons use a conservative
  (default), central or aggressive propagation model (`--propagation`); an exclusion only by a stronger model is a flag.
- **The thermal contour.** Grid brackets are refined with the relic solver to roots with |Ωh²/target − 1| ≤ 1%, the
  target being Planck's Ωh² times the declared relic fraction. Every constraint is re-evaluated at each root, which
  is viable (every applicable constraint computed and allowing), pending (one not decided) or excluded.
- **The combined likelihood** (`--likelihood`): the constraints added in the asymptotic Gaussian approximation, with
  log-normal theory nuisances and a 10% band on Ωh² by default, reported beside the 95% cuts.
- **The viability checklist** (`orchestrator/checklist.py`): each of the owner's 28 items for a thermal relic is
  computed (with its verdict over the grid and on the contour), undecided (compared but decided nowhere), checked or
  flagged by the model checks, assumed, applicable but not computed, or not applicable, each with its reason. The
  report adds the audit, the verdict, the plots, the contour table, the curated records and an arXiv search.

### 6.2 Track 2: what explains an anomaly? (DM14)

- **Anomaly records.** Any search that reports its events is one YAML file (target, exposure, window, events,
  resolution, background and its uncertainties, efficiency, halo, sources, `verified_by`), written and checked by
  `adroit anomaly template` and `check`, or drafted from a paper by `adroit anomaly draft` (paid). An unverified record
  is refused unless `--unverified` is given. Confirmed event inputs from the experimental library can also enter (§11).
- **Candidates**: the library, the user's typed models (one strength μ scales every coefficient, so μ̂ = 1 means the
  stated couplings explain the events), or both; then Path 2 (§5.3) and physical eligibility (§2).

### 6.3 The single-idea report (DM14; `orchestrator/single_idea.py`)

1. The fit at each mass, with the global significance from toys.
2. The tension with the null searches at the best mass.
3. The best-fit band: the model's actual NR coefficients solved for g_χ at fixed masses and verified against the fitted
   spectrum and likelihood, or fitted directly within a declared range
   ([bounded_physical_fitting.md](bounded_physical_fitting.md)). Every constraint is evaluated at the physical point.
4. Track 1 in a window around the band, with the anomaly re-fitted at each trial mass of a thermal intersection.

The verdict is NO FIT, RESOLVED THERMAL EXPLANATIONS EXCLUDED, A VIABLE THERMAL EXPLANATION (with or without a
pending calculation), NO RESOLVED THERMAL EXPLANATION, or UNDETERMINED. Fit quality, constraint compatibility of the
physical best fit, and thermal viability are separate fields; a good fit at the wrong relic density is not viable.

### 6.4 Verdict levels

| Track 1 level (`parameter_space/verdict.py`) | meaning |
|---|---|
| VIABLE | at least one certified root survives every applicable constraint |
| VIABLE, PENDING A CALCULATION | no root is viable, but some are pending rather than excluded |
| EXCLUDED | every resolved root is excluded, and nothing is unresolved |
| THERMAL CALCULATION PENDING | relic coverage or root refinement is incomplete |
| NO RESOLVED THERMAL ROOT (samples overabundant) | every computed sample is above the target |
| NO RESOLVED THERMAL ROOT (samples underabundant) | every computed sample is below the target |

UNDETERMINED is reported when no computable class covers the model. A root is viable, pending or excluded; a search's
outcome at a point is excluded, allowed, undecided (with the reason, making the point pending) or not applicable. A
flag (⚠) marks an unreliable verdict, such as at the edge of a record's plane or at the Higgs resonance, without
changing the status. Negative statements refer only to the sampled region and resolution.

## 7. The portal library and the searches applied point by point

**The entries** (`parameter_space/library.py`, `portals/`; `adroit portals`, `adroit track1 --portal ID`): 22
benchmark models from the literature and DM13's three simplified models (V1, A1, the Yukawa-like scalar mediator).
The families: Higgs portals (scalar, fermion and vector dark matter, and a singlet mixing with the Higgs); dark photons
(Dirac, scalar, inelastic); the Z portal; gauged B − L and L_μ − L_τ; an ALP-like pseudoscalar; t-channel partners of
u_R and μ_R; the inert doublet and the 2HDM+a, read from their published UFO files; the wino and the higgsino. Each
entry holds its benchmark, the plane its papers plot, its Lagrangian, references with exact arXiv titles, the
literature's result and what is not computed. Benchmarks older than LZ are starting points, not claims of viability.

**The engine built for them** ([portal_library.md](portal_library.md) to [portal_library_5.md](portal_library_5.md)):
the off-shell Higgs width by channel; coannihilation in the relic solver; interfering s-channel exchange and explicit
amplitudes; exact kinetic mixing with hypercharge; Sommerfeld factors (multi-state for the electroweak multiplets) and
bound-state formation; a general tree-level 2 → 2 engine on published UFO models; MadGraph production tables for the
mediators; loop-level scattering (twist-2, anapole, charge radius, Higgs triangles).

**The searches** (`constraints/searches.py`, `parameter_space/searches.py`, `resonances.py`): the CMB, BBN and N_eff;
dark-photon searches and beam dumps via DarkCast; B → K a; LHC dileptons, dijets and tt̄ resonances; heavy scalars to
ZZ and WW; monojet, mono-h and mono-Z; LEP-II contact interactions and LEP for the inert doublet; ATLAS's squark
search; the muon g − 2; BaBar and Belle II for L_μ − L_τ; CCFR tridents; the invisible Higgs and Z widths; γ-ray lines
(Fermi-LAT, H.E.S.S.); AMS-02 antiprotons. SModelS recasts the LHC for partners, multiplets and mediator spectra.
micrOMEGAs is an independent relic cross-check (`adroit crosscheck PORTAL`).

**Applicability.** A limit set for one signal shape or benchmark applies elsewhere only within the domain its paper
states. Outside it a point is undecided, never allowed. [widths.md](widths.md) gives each search's width domain and the
assumptions beyond the width that must also match (ZZ's interference modelling, tt̄'s top loop).
[benchmark_limits.md](benchmark_limits.md) gives how each benchmark-specific contour is extended: by a calculation
(mono-h and mono-Z, calibrated with MadGraph), only at the benchmark (the 2HDM+a combination, CMS's summary planes), or
one-sidedly where ADROIT's production cross-section is a lower bound (coloured partners).

## 8. Constraint records and their verification (DM7, M21, R9)

- **The records** (`constraints/data/records.yaml`, 37 entries) give the source, figure or table and page, the data,
  the assumptions under which the limit holds, its CL and construction, the transcription checks, and who verified it.
- **Signatures bind the payload.** `adroit records verify ID --by NAME --expected-hash HASH` writes the name, date and
  `verification_sha256`, a hash of the scientific payload (source, quantity, assumptions, benchmark, CL, data); it
  refuses if the record changed after the hash was shown, and a later edit makes the signature stale.
- **The verification gate.** Only records whose signature matches the current payload (or a labelled legacy
  baseline) are usable (`database.usable`). A search whose record is unverified or stale gives an undecided outcome,
  so the point is pending. `--unverified` admits such records on request, and the report says so. Under the defaults,
  viability therefore waits on verification: R3's 79 pending crossings, re-judged, give 0 viable points with verified
  records and 10 with unverified records allowed (run: a development receipt (rejudge)).
- **Review tools.** `adroit records show`, `review` and `queue`, and the workbench's Records page, show each record's
  curves beside its source, one quantity per panel; the queue ranks the records that block a saved study's conclusions
  ([record_review_workflow.md](record_review_workflow.md)). Signing never converts a CL or widens a validated range.
- **R9.** [r9_record_verification.md](r9_record_verification.md) is the signing packet: the order of review, each
  record's command with its current hash, and aids that are not verifications (`docs/r9/precheck.py`,
  `portal_dependencies.py`). The signatures are the owner's; agents may propose records but never verify them.

## 9. Theory certificates (`adroit/theory/`; `adroit theory vacuum | unitarity | running | equilibrium`)

The first three apply to the complete real Z2 singlet potential, the fourth to Majorana dark matter with an e_R scalar
partner. Each states its approximation and domain; a margin below numerical resolution is unresolved, not a pass.

- **Tree-level vacuum** (M24, [scalar_vacuum_certificate.md](scalar_vacuum_certificate.md)): copositivity, and an
  exact enumeration of the stationary points and families on the field domain, which decides whether the declared
  vacuum is global. A bounded vacuum above a deeper minimum is judged by its zero-temperature tunnelling lifetime
  (`vacuum_decay.py`, the O(4) bounce by path deformation): metastable passes with a flag, short-lived fails.
- **Partial-wave unitarity** (M25, [scalar_unitarity_certificate.md](scalar_unitarity_certificate.md)): all 15
  scalar-pair channels in the high-energy contact limit, |Re a₀| < ½.
- **Running** (M26, [scalar_running_certificate.md](scalar_running_certificate.md)): one-loop RGEs from explicitly
  supplied MSbar matching up to a declared scale, checking copositivity, unitarity and a 4π cap along the trajectory.
- **Chemical equilibrium** (M27, [chemical_equilibrium_certificate.md](chemical_equilibrium_certificate.md)): whether
  the conversion rates keep the partner and the dark matter in chemical equilibrium from freeze-out on, as the
  coannihilation solver assumes, over a bank of regulator variants including a thermal-mass one.

**In the verdict** (`verdict.theory_status`): a complete certificate that fails makes the point an invalid model
point, excluded whatever the data say; an unresolved or incomplete one makes it pending. For a t-channel partner the
chemical-equilibrium prerequisite stays pending unless its certificate supports it.

## 10. Evidence and provenance (`adroit/evidence/`, `core/evidence.py`, `core/provenance.py`)

- **Evidence sidecars.** Track 1, Track 2, single-idea and promoted runs write `result.evidence.json` beside
  `result.json`: typed inputs, engine mapping, source and data hashes with review signatures, software identities,
  settings, CLs, applicability, pending reasons, and the root, fit and coverage certificates.
- **Export, verify, replay** ([evidence_export.md](evidence_export.md)). `adroit evidence export` writes a ZIP of a
  study and its graph with content hashes. `verify` reconstructs the saved verdicts without rerunning physics and
  reports "internally consistent; provenance not verified". `replay` reruns one saved point with the installed code,
  treating the bundle as untrusted data: the model class is rebuilt from the typed model, never taken from the bundle.
- **Provenance.** An append-only SQLite store logs every language-model call, and paid sessions keep a ledger
  (`paid.jsonl`). Reports state UTC calculation dates apart from rendering dates (`core/chronology.py`).
- **Caches** (DIAMX templates and results, Yellin's interval code, other native statistics) are keyed by the exact
  inputs and code identity, so a cached result is the same calculation. The R10 tables (§4.3) are the one deliberate
  interpolation, and verdicts near their tolerance are recomputed.

## 11. Catalogs and reanalysis

- **The personal model library** (M35–M36; `library/personal.py`; `adroit models`). Private, immutable revisions
  (`catalog:MODEL_ID@REVISION_ID`) in a git-ignored folder, each with its canonical `ModelSpec`, approval identity,
  parent revision, source assets and a TeX view generated from the typed terms. Intake is from an idea, field content,
  TeX, a screenshot or a named equation in a paper PDF; all but typed and field input use an opt-in paid interpretation
  under one session budget. Saving needs review against the displayed hash; missing values stay unspecified.
- **The experimental library** (M36.5, M37; `library/experimental.py`; `adroit experiments`). Private, dated drafts of
  papers, tables, figures and descriptions (`experimental:EXPERIMENT_ID@REVISION_ID`), with typed claims that start
  unextracted; optional paid interpretation proposes source-linked claims. Source review (a named person's
  attestation) and numerical validation against independent anchors are separate steps. Reviewed, validated inputs
  become private limits (`private-limit:`) and event searches (`private-search:`), chosen through immutable personal
  profiles with explicit activation and rollback ([private_experimental_profiles.md](private_experimental_profiles.md)).
- **Reanalysis** (M39; `orchestrator/reanalysis.py`; `adroit reanalyse open | edit | model | review | run`; workbench
  `/reanalyse`). A saved study, model or confirmed anomaly is reopened as an immutable draft pinned to its original
  inputs. The researcher chooses the target track, a model revision and the options, reviews the differences, and
  launches a fresh child run under their name. The parent stays historical, and no input is replaced by a "latest" one
  silently ([reanalysis_and_release_journeys.md](reanalysis_and_release_journeys.md)).

## 12. Agents and the budget gate (`adroit/agents/`)

- **The interface.** `agents/llm.py` alone imports the Anthropic and OpenAI SDKs. Agents talk to a `StructuredLLM`,
  which returns JSON validated against a Pydantic schema; `FakeLLMClient` serves the tests. The offered models are
  Claude Opus 5.5 and GPT-5.6 Sol (`core/pricing.py`); an independent checker must differ from the deriver.
- **The agents**, each opt-in:
  - **drafters:** the model builder (`ideas.py`; an idea → field contents, from which the generator writes the
    terms), Lagrangian intake and derivation (`lagrangian.py`, with a second-model check), model intake
    (`model_intake.py`; TeX, screenshots, paper equations), the anomaly drafter (`anomaly.py`; quotes checked against
    the text) and experimental extraction (`experimental_extraction.py`);
  - **DM9's agents** on Track 1, Track 2 and single-idea results (`adroit agents`): variants chosen from a fixed
    neighbour-graph menu, a constraint scout (references confirmed against arXiv or Crossref; proposals become
    unverified records) and an assumption audit of a deterministic inventory;
  - the research assistant (`adroit assist`, with a free baseline) and DM10's direct-prompting baseline (`direct.py`).
- **What agents cannot do.** They compute no number: a value they transcribe from a source enters a calculation only
  after a person has reviewed it. They sign no record, approve no model and change no verdict.
- **The budget gate.** A paid command needs `--budget`. Before each request, `BudgetAccount` reserves its largest
  possible cost against the hard cap, and the command prints the model, the cap and the reservation (hard rule 6;
  `orchestrator/preflight.py`). A request that does not fit stops before dispatch, with exit code 3 and the partial
  record kept; uncertain billing stays committed. Sessions fix their budget at creation, and `raise-cap` records a
  confirmed increase. The workbench asks for at most $10 with a ticked approval before any paid run.

## 13. The workbench (DM15; `adroit/ui/`; `adroit workbench`)

A local NiceGUI application on 127.0.0.1 (`uv sync --extra ui`). Its menu: Home, Studies, Constrain a model, Signal
best fits, Explain a signal, Model library, Add a limit (the experimental library), Add a signal (the anomaly
record) and Records. Every wizard ends in one
command-line call, so the workbench and the CLI run the same code. A detached runner at `nice` 10 runs each command,
so a run outlives the page; the live view shows status, log and spend, with Cancel. A study page shows the report and
plots, parent and children, and the promote or approval form. Files outside the runs directory are refused. DM11's
simpler page remains as `adroit workbench --classic`.

**The trust model** (decision D36, the external audit of 2026-10-16, item 20). ADROIT is a local, single-user
workbench: the page is served on 127.0.0.1 only. Imported UFO and Python model files are trusted executable code.
Coupling formulas, wherever they come from (a paper, a language model, a form), pass `arithmetic.check_formula`
before SymPy reads them (AG-1). PDFs, papers and model descriptions are data: their text is never followed as an
instruction. No isolation or resource limit (expression complexity, parse time, memory, subprocesses) is applied;
they are needed, and revisited, before any hosted or multi-user use.

## 14. Evaluation and gates

- **DM10** (`adroit eval`; [dm10_evaluation.md](dm10_evaluation.md)): four suites (limit reproduction, LZ's 612
  published significances, injection and recovery on four targets, historical excesses), each split into development
  and held-out halves by a hash; the held-out half runs only with a stated reason, logged in a ledger. Baselines:
  exhaustive fitting without agents, and direct prompting. The rules G1–G5 were met on the held-out half (run:
  docs/dm10/gate.md).
- **Milestone gates** are declared in each record before their first run and not widened after a failure; a miss is
  recorded as a finding. For example, 579 of LZ's 612 local significances are reproduced within 0.3σ (run:
  docs/dm6_signal.md#2. The gate).
- **Release checks.** `scripts/release_checks.py` runs lint, the fast and slow suites, the validation scripts and a
  read-only `adroit setup`, and writes a dated receipt to `docs/receipts/`.

## 15. Known limits

- Thermal freeze-out only, and nuclear recoils only; freeze-in, electron recoils and the Migdal effect are listed in
  [adroit_phase2.md](adroit_phase2.md).
- Collider production is leading order from MadGraph tables: Drell–Yan Z′ production is left at LO (conservative), and
  gluon fusion carries the Higgs Working Group's K-factor ([portal_library_4.md](portal_library_4.md)).
- The historical records use the Helm form factor and see no spin-dependent scattering.
- The ΔAIC ≤ 2 set is not a calibrated confidence set (run: docs/dm10_evaluation.md#5. What DM10 found).
- LZ's L12 limits are not reproduced by any of the normalisations tried, and the card stays unvalidated
  ([notes/lz_model_cards.html](notes/lz_model_cards.html)).
- Open applicability questions (WW's reading of the mass resolution, SModelS's 10% width threshold, DarkCast's gates per
  search) are listed in [widths.md](widths.md).
- The plots do not yet show projected sensitivities, the neutrino fog or uncertainty bands.

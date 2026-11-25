# ADROIT: build plan

ADROIT is the **Agentic Dark matter Reinterpretation and Operator Inference Toolkit** (named 2026-09-30; working name agentic-DM).

Plan of record for building an agentic system for dark matter direct
detection on the foundations of Nomothetica. Drafted 2026-09-29. Milestones
are named DM0–DM11. The owner settled the decisions of section 7 on
2026-09-29. Ideas outside this build are kept in
[`adroit_phase2.md`](adroit_phase2.md).

Works and tools that inspired the design or are reused are recorded in
[`related_work.md`](related_work.md), so that they can be cited.

## Status (12 October 2026)

This plan was drafted for DM0–DM11 and has since been extended. Where the work
stands:

- **DM0–DM15: done.** Each milestone's status and record are in section 6.
  The owner added DM12 on 2026-10-02 and split it into DM12–DM15 on
  2026-10-03.
- **After DM15, the portal library:** parts 1–5, 2026-10-03 and 2026-10-04
  ([`portal_library.md`](portal_library.md) to
  [`portal_library_5.md`](portal_library_5.md)).
- **The M-series:**
  - M01–M18 resolve the 19 findings (F01–F19) of the first independent audit
    (the auditor, 2026-10-05): done (the audit remediation plan).
  - M19–M28 and M33–M40, with M36.5a–h and M37.5a–d: done at their declared
    scopes ([`extension_status.md`](extension_status.md),
    the broader extension plan,
    the user workflow plan).
  - M29–M31: deferred until after the first release.
  - M32, the release-closure audit: carried out on 2026-10-10 (summary:
    a development receipt (audit_2026-10-10_closure); the full report is local).
    Its findings are closed by
    R0–R12.
- **The release plan, R0–R12** (the release plan):
  - **R0–R8: done.**
    - R3's gate was missed as declared and is recorded as a finding. The
      owner's conservative mixture rules (2026-10-11) later made "viable"
      reachable with unverified records allowed; under the defaults it waits
      for R9.
    - R6 has one deferral, accepted by the owner: normalising the smeared
      shape at threshold (under 0.01σ on CDMS II Si's global significance).
      Fixed since by the external audit's A09 (2026-10-16).
    - The R7 gate passed (6 of 6, $0.557); the R8 gate passed ($0).
  - **R9, record verification: done** (2026-10-13): the owner verified all 38
    records ([`r9_record_verification.md`](r9_record_verification.md));
    `adroit records list` ends with the current count.
  - **R10 and R11: done** (2026-10-12, 2026-10-13; `r10/README.md`,
    `r11/README.md`). **R12** moved into G12 of
    [`freeze_out_build.md`](freeze_out_build.md) (the G12 closure record).
  - **The owner's follow-ups** of 2026-10-11 and 2026-10-12, recorded in
    the release plan:
    - conservative mixture rules for channel mixtures;
    - the metastable vacuum's tunnelling lifetime;
    - conservative, central and aggressive propagation models for
      antiprotons;
    - LZ-convention cards;
    - naturalness flags on zeroed couplings, and an "undecided" checklist
      status;
    - the mono-h band calibrated beyond ATLAS's benchmark;
    - the SD factor for modules validated for one SD kind, and a twist-2
      bound from PDF moments;
    - the search for LZ's L12 convention (none found).

    The latest closing receipt is
    a development receipt (release_checks_2026-10-12T082851Z) (PASSED; fast
    1,860, slow 34).
  - **R10, Track 1 throughput: in progress.** Precomputed direct-detection
    limit tables for the slow modules ([`r10/README.md`](r10/README.md)). Its
    gate has not been run.
  - **R11, documentation, code health and packaging: in progress.**
  - **R12, the closure re-audit and usability evidence: pending.**
- **Halo nuisance parameters: not built.** Section 3, DM2 and the risks
  table (section 8) planned the halo's parameters as nuisance parameters of a
  fit. No fit profiles them.
  - The halo is fixed in each run. Each module's limits use its
    collaboration's published halo, and a run may give another one
    (`HaloModel`, including a tabulated f(v)).
  - The nuisance parameters that are profiled:
    - the background rate in Track 2 (`inference/nuisance.py`, DM10);
    - a log-normal theory uncertainty in the combined likelihood
      (`parameter_space/likelihood.py`, R5);
    - the nuisance parameters inside a module's own likelihood, where it has
      them: for example, the backgrounds in DIAMX's xenon likelihoods.
  - What is built for the halo is a sensitivity flag (DM6). Path 2 refits
    each leading candidate with v₀ = 220 or 260 km/s and with v_esc = 500 or
    600 km/s. It flags the candidate when Z moves by more than 0.5, or the
    best-fit coupling by more than a factor 2 (`orchestrator/signal.py`,
    `ALTERNATIVE_HALOS`).
  - Since R6, a null experiment whose halo differs from the signal's is
    named in the combination's note.

## 1. Goal

Two paths share one physics core.

- **Path 1, model → exclusion.** Given a dark matter model, compute its
  direct-detection observables and apply the experimental bounds. The output
  is the exclusion plot for that model.
  - The model is a Lagrangian, or a particle content from which one is built.
    The default is the Standard Model plus new states.
  - An agent also flags the other classes of constraint that apply: collider,
    indirect detection, beam dump, flavour.
- **Path 2, signal → ranked candidates.** Given an excess in a
  direct-detection experiment, take every interaction in a library of
  operators and models, and:
  - fit it to the signal;
  - test it against every other experiment and against complementary
    constraints;
  - rank the viable interactions in a quantitative tournament.

The system is **not tailored to one experiment or one event**. The LZ
extended-window result (arXiv:2609.02823) is the first test case. The intended
use is a future signal: more events in LZ, or an excess elsewhere.
Experiments therefore enter as exchangeable modules (DM3).

## 2. Principles

1. **The core is free to run.** Every quantity is computed by deterministic
   code on the user's machine, with no call to a paid service. Both paths
   run to their results for any library model without a language model.
2. **Language models are an optional consistency check.** A user opts in
   call by call (section 5). Every number in a result still comes from
   tested code, never from a model's text. (Nomothetica's rule; also the
   conclusion of FERMIACC and DarkAgents.)
3. **Use existing tools.** Rates, matching, relic density and collider recasts
   come from established public codes behind thin typed wrappers (section 4).
4. **Nothing is trusted before it reproduces a published result.** Each
   experiment module must reproduce its collaboration's limit, and the signal
   fit must reproduce LZ's published significances, under tolerances fixed in
   advance.
5. **The core is experiment-agnostic.** What is specific to a search lives in
   its experiment module.
6. **State what cannot be concluded.** A constraint that cannot be applied
   without further calculation is reported as such, and candidates the data
   cannot separate are reported as indistinguishable.
7. **Evaluate without overfitting.** Decision rules are written before the
   comparison is run, and part of the test suite is locked.

## 3. The physics chain

The library is layered. Each layer maps to the one below:

| layer | content | source |
|---|---|---|
| 3. Mediator models | simplified models: scalar, pseudoscalar, vector and axial mediators; Higgs and Z portals; dipole and anapole moments; pseudo-Dirac (inelastic) states | to be compiled (DM4) |
| 2. Relativistic operators | the twenty Lagrangians L1–L20 of Anand, Fitzpatrick and Haxton (arXiv:1308.6288); a quark-level operator basis | arXiv:1308.6288; DirectDM |
| 1. Nonrelativistic operators | the nucleon-level operators O_i of the nonrelativistic effective theory, with isoscalar and isovector couplings | arXiv:1203.3542 |
| 0. Nuclear responses | response functions of each target nucleus | DMFormFactor density matrices, through WimPyDD |

**The rate.** For a dark matter mass m_χ, a target nucleus T and a mass
splitting δ (δ = 0 is elastic), the differential rate per unit target mass is

    dR/dE_R = ρ_χ / (m_χ m_T) ∫_{v > v_min} d³v  v f(v)  dσ_T/dE_R ,

    v_min = | m_T E_R / μ_T + δ | / √(2 m_T E_R) ,

with f(v) the velocity distribution in the detector frame and μ_T the reduced
mass. The cross-section dσ_T/dE_R is a quadratic form in the coefficients of
the nonrelativistic operators, weighted by the nuclear responses.

**The prediction of an experiment.** An experiment module turns dR/dE_R into
expected counts in its own observables, from its exposure, efficiency and
resolution:

    s = exposure × ∫ dE_R  ε(E_R)  dR/dE_R      (per bin, or as a density).

**The likelihood.** With background b(ν) and nuisance parameters ν (halo
parameters, background normalisations, detector response),

    L(θ, ν) = Poisson(data | s(θ, ν) + b(ν)) × constraint terms(ν),

in binned or unbinned form. Significances, limits and intervals come from the
profile likelihood ratio, as in the experiments' own analyses. (As built, the
halo parameters are not among the profiled ν; see the status above.)

**Which constraints apply at which layer:**

| tier | constraint | needs, beyond the nonrelativistic operator |
|---|---|---|
| 1 | other direct-detection experiments and targets | astrophysics and nuclear physics only |
| 2 | capture in the Sun and neutrino telescopes | an assumed annihilation channel |
| 3 | collider, indirect detection, relic density, beam dump, flavour | a relativistic completion (layer 2 or 3) |

## 4. What is reused

### From Nomothetica

The table records the plan of 2026-09-29 and what happened at the
retirement of the inherited engine (DM6, 2026-09-30). Much that the plan
kept could not run without the engine: the fitting stack integrates the
general simulators, the offline client and the validation gauntlet answer the
general agents' prompts, and the harness, the workbench and the dashboard
drive the general pipeline. Keeping them would have meant keeping the engine,
so they went with it. Everything removed is in the tag `pre-retirement`
(commit `533babe`), from which later milestones can take what they reuse.

| module | planned | at DM6 |
|---|---|---|
| `core/` (typed state, provenance, config) | keep, extend | kept; the general schemas stay in `state.py`, which provenance, the gates and the client record |
| `library/` registry, card schema, neighbour graph | keep the machinery | replaced: DM4's interaction library has its own registry, schema and graph; the twenty general families retired |
| `inference/` multi-start fitting, fit cache, process pools, budgets | keep | retired: built on the general simulators; DM2's rates and DM6's likelihoods replace them |
| `inference/tournament.py` | keep the structure | carried into `dm_tournament.py` (invariant ranking, flags, indistinguishable and contested records); the module retired |
| `agents/` client | keep, re-target | kept (`llm.py`: client, fake client, cache, budget) |
| `agents/` offline client, validation gauntlet, refinement | keep, re-target | retired: written for the general families; DM8 and DM9 write new agents |
| `retrieval/` | keep | kept; re-indexed on dark matter literature (DM9) |
| `orchestrator/` human gates, control file | keep the machinery | kept (`gates.py`, `control.py`) |
| `orchestrator/` pipeline, gate points, checkpoints, reports | keep the machinery | retired: the two new pipelines (DM5, DM6) replace it |
| `eval/` harness, results stores, pre-registered gates, tournament lab | keep | retired: the harness ran the general pipeline; DM10 builds the dark matter suites |
| `ui/` workbench, `apps/` dashboard | keep, adapt last | retired: both drove the general pipeline; DM11 builds the interface to the two paths |
| `ingest/` | `gridded` retired at DM1 | the rest retired: the experiment modules read their own data |
| the general library: response laws, shape search, driver scaling, time-series feature detectors, the general benchmark suites | retire in one cut at DM6 | retired |

### External tools

Each is to be verified in DM0 for installation on the development machine,
licence and interface, before anything depends on it.

| job | tool | used in |
|---|---|---|
| rates for any nonrelativistic operator, elastic or inelastic | WimPyDD (the code LZ used) | DM2 |
| nuclear responses | DMFormFactor density matrices (arXiv:1308.6288) | DM2 |
| quark-level operators → nonrelativistic operators, with running | DirectDM | DM4 |
| experiment likelihoods from public data | DIAMX (LZ, PandaX-4T, XENONnT); DDCalc (GAMBIT); the XENON collaboration's released likelihood tools | DM3 |
| detector response, where a module needs it | NEST, flamedisx | DM3 |
| Lagrangian → model files | the project's own UFO generator from a `ModelSpec` (no Mathematica: FeynRules and SARAH are not used, the owner's decision of 2026-10-01); LanHEP or MARTY as open alternatives | DM8 |
| relic density, indirect detection, tree-level direct detection from model files | micrOMEGAs, MadDM (DM7 uses its own calculators for the textbook models; these tools remain for DM8) | DM7, DM8 |
| capture in the Sun for general operators | Capt'n General (DM7 uses its solar model; capture is computed by the rate code) | DM7 |
| Lagrangian → likelihood code, without agents | GUM (GAMBIT); a reference for DM8 | DM8 |
| collider limits on mediator models | published summary limits first; recasting tools (SModelS, CheckMATE, MadAnalysis 5) later | DM7 |
| limit curves and event data | HEPData; the experiments' own data releases; community compilations of limit curves | DM3, DM7 |

## 5. Architecture

New packages beside the inherited ones:

- `adroit/physics/`: halo models, kinematics, the rate wrapper, units and
  conventions.
- `adroit/experiments/`: the experiment-module interface and one module
  per search.
- `adroit/constraints/`: the curated constraint database and the
  complementary-constraint calculators.
- `adroit/statistics/`: likelihoods, profile likelihood ratio, limits,
  toy Monte Carlo, combination.

**An experiment module** declares:
- **The search:** target nuclei, exposure, region of interest and
  observables.
- **The response:** efficiency and resolution.
- **The data:** observed events or counts, and the background model where it
  is public.
- **Its validation:** the collaboration's statistical method, the published
  limits it must reproduce, its references and data DOI.
- **Its fidelity level,** set by what the experiment has released:

  | level | what is public | how it is used |
  |---|---|---|
  | A | event-level data and a background model | full likelihood in the experiment's observables |
  | B | counts, efficiency and background expectation | binned Poisson likelihood |
  | C | a limit curve only | rescaled for the same recoil spectrum only; otherwise a flag, never a likelihood term |

**The halo model.** The Standard Halo Model is the default. A run may replace
it with any velocity distribution: other parameters, a tabulated f(v), or
added components such as a stream. The halo is part of every result's
record, because many explanations of a high-energy recoil depend on the tail
of the distribution.

**Opting in to a language-model check.** Nothing calls a paid service unless
the user confirms it. At the confirmation the user is shown:
- what will be checked, and an estimate of the cost;
- the model choice, with the defaults **Claude Opus 5.5**
  (`claude-opus-5-5`) and **OpenAI GPT-5.6 Sol** (`gpt-5.6-sol`), either or
  both of which can be changed or declined.

Each user supplies their own API keys. Without keys the option is not
offered, and nothing else is affected.

**The two pipelines:**

    Path 1:  model input → library match or bespoke derivation → coefficients
             → rates → every experiment module → exclusion plot
             → literature flags for other constraints → report

    Path 2:  signal (an experiment module with an excess) → fit every library
             entry → tier-1 combination → tier-2 and tier-3 constraints
             → tournament → ranked candidates, with the measurements that
             would separate them → report

## 6. Milestones

Costs are for language-model calls. Every paid run needs the owner's approval
in advance. A session is one working session.

| milestone | what | depends on | cost | sessions |
|---|---|---|---|---|
| DM0 | Tool audit and data inventory | – | $0 | 1 |
| DM1 | Prune and reshape; typed schemas | DM0 | $0 | 1 |
| DM2 | Forward model | DM1 | $0 | 1–2 |
| DM3 | Experiment modules and limit reproduction | DM2 | $0 | 2–3 |
| DM4 | Operator and model library | DM2 | $0 | 1–2 |
| DM5 | Path 1 for library models: exclusion plots | DM3, DM4 | $0 | 1 |
| DM6 | Signal fits and the tournament | DM3, DM4 | $0 | 2–3 |
| DM7 | Complementary constraints | DM4, DM6 | $0–2 | 2–3 |
| DM8 | Path 1 for arbitrary Lagrangians, with two-model verification | DM5 | ~$5–10 | 2–3 |
| DM9 | Path 2 agents: bespoke variants, literature, audit | DM6, DM7 | ~$5–10 | 2 |
| DM10 | Evaluation suite and baselines | DM6 onward | ~$10–20 | 2 |
| DM11 | Workbench, reports, documentation, paper | all | $0–2 | 2 |
| DM12 | The model front end: most general Lagrangian, audit, free text → models | DM8 | ~$1–3 | 1–2 |
| DM13 | Parameter space and the verdict: scans, overlay plots, Track 1 report | DM12, DM7 | ~$2–5 | 2 |
| DM14 | Track 2 made general: anomaly intake, user models, single-idea report, recursion | DM13, DM6, DM10 | ~$2–5 | 2 |
| DM15 | The workbench for the two tracks (NiceGUI) | DM12–DM14, DM11 | $0 | 1–2 |

The order is DM0 → DM1 → DM2 → (DM3, DM4) → DM5 → DM6 → DM7 → DM8 → DM9 →
DM10 → DM11 → DM12 → DM13 → DM14 → DM15 (DM12 added by the owner on
2026-10-02, and split into DM12–DM15 on 2026-10-03). DM10's suites are built
up from DM3 onward and used at every later milestone.

### DM0 — Tool audit and data inventory

**Done 2026-09-29; report in [`dm0_tool_audit.md`](dm0_tool_audit.md).** The
gate is met except in the kinematic tail, where the reference code's rounded
constants exceed the tolerance. Decisions 10–12 are settled and the two
manual downloads are in place.

- **Tools.** For each tool of section 4: install it, record its version,
  licence and interface, and run its own example. Decide for each whether it
  is called as a library, called as a subprocess, or used only to generate
  reference numbers for tests.
- **Data.** Inventory what each experiment has released. Start with the LZ
  HEPData record (DOI 10.17182/hepdata.182472).
- **References.** Verify every reference to be cited and record it in
  `related_work.md`.
- **Gate.** A spin-independent xenon spectrum computed through the chosen
  rate code agrees with an independent calculation to 1%.

### DM1 — Prune and reshape

**Done 2026-09-29.**

- **Retired:** the gridded ingestion with its `geo` dependencies, and the
  wildfire-era evaluation modules.
- **Kept for now: the inherited pipeline and its general library.** The
  response laws and their helpers are woven through the old pipeline, the
  agents and the workbench. Cutting them out piece by piece would be surgery
  on code that DM6 replaces whole, so they are removed in one cut then.
  Until DM6 the inherited pipeline is the working reference for the
  machinery that is kept. (Removed at DM6, with more of the machinery than
  planned; section 4.)
- **Typed schemas** (`adroit/core/dm_state.py`): dark matter particle,
  halo model, target, interaction model, recoil spectrum, experiment module,
  data set, likelihood result, constraint record, constraint verdict.
- **Units and conventions registry**
  (`adroit/physics/conventions.py`): constants, the coupling
  normalisation (unit coupling is 1/m_v² with m_v = 246.2 GeV, as in
  arXiv:1308.6288 and LZ), the isospin basis, the nucleon mass, and the
  conversions to cross-sections per nucleon.
- **The manifest of external tools and data**
  (`adroit/external/tools.yaml`): what is needed, how each item is
  obtained, and what the user must download by hand.
- **A native Python on Apple silicon** (decision 12), and a folder without
  spaces for compiled tools (decision 11; `ADROIT_TOOLS_DIR`).
- **Gate.** The suite passes and the quick start still runs.

### DM2 — Forward model

**Done 2026-09-29; record in [`dm2_forward_model.md`](dm2_forward_model.md).**
The gate is met: WIMpy_NREFT agrees to 10⁻¹¹ and WimPyDD to 1.3×10⁻³ once
their rounded constants are corrected, over 49 cases (every operator alone
and all together, 13 isotopes, spins 0 to 1, inelastic and exothermic).
Found on the way:
- as published, both reference codes differ from exact constants by percents
  near the minima of the nuclear response and near the kinematic endpoint;
- WimPyDD fails on calcium and tungsten, and its approximate spin response
  for ¹⁸³W is four times too large;
- the spin-1 operators O₁₇–O₂₀ are left to phase 2.

- **Halo models.** The Standard Halo Model with the recommended parameters of
  arXiv:2105.00599 is the default, its parameters exposed as nuisance
  parameters. Any other velocity distribution can replace it (section 5).
  (The parameters are exposed, but no fit profiles them; see the status
  above.)
- **Rates.** dR/dE_R for any vector of nonrelativistic coefficients, elastic,
  inelastic or exothermic, for the targets Xe, Ar, Ge, Si, Na, I, F, Ca, W and
  O. Annual modulation is an output from the start, since inelastic models
  modulate strongly.
- **Tests.** Analytic spin-independent and spin-dependent limits; reference
  spectra for each operator; the kinematic endpoint of inelastic scattering.
- **Gate.** Reference spectra are reproduced to 1%.

### DM3 — Experiment modules and limit reproduction

**Built 2026-09-29; record in [`dm3_experiments.md`](dm3_experiments.md). Gate
met** under the owner's refinements of the rule (record, section 3). They
are:
- an edge clause: a 3% shift in mass where the published slope exceeds 8;
- validation module by module, over validated mass ranges;
- a module counts if its range spans a decade and holds its strongest
  published limit.

What was built:
- the interface and statistics;
- CRESST-III, CDMSlite, PICO-60 and DEAP-3600 modules, and LZ, XENONnT and
  PandaX-4T through DIAMX;
- the Klos et al. structure factors as a second spin-dependent nuclear
  model;
- LZ's extended-window tables, as the reference for DM6.

Validated ranges (reproduced/published inside them):
- CRESST-III, SI and SD-neutron, 0.35–130 GeV (0.79–1.17), with the cut
  survival in true energy (an assumption);
- CDMSlite, SI, SD-proton and SD-neutron, 1.3–20 GeV (0.93–1.21 above the
  1.31 GeV edge point, which passes by the edge clause);
- PICO-60, SD-proton, 3–1000 GeV (1.16–1.23 above the 3.0 GeV edge point);
- DEAP-3600, SI, 50 GeV–10 TeV (0.78–0.96);
- XENONnT, SI, 28 GeV–1 TeV (0.97–1.12), and LZ, SI, 8.9–92 GeV (0.96–1.26);
- PandaX-4T, SI, 147 GeV–9.7 TeV (1.14–1.20). It does not count for the
  gate: it is up to 2.2 times weaker at 12–63 GeV, where its limit is
  strongest, as in DIAMX's own benchmarks.

- **The interface** of section 5, and the statistical methods: counting,
  binned likelihood, unbinned profile likelihood, optimum interval.
- **First modules.** the LZ extended window and LZ's
  standard search; XENONnT; PandaX-4T; one argon experiment; PICO-60
  (fluorine); CRESST-III; one germanium experiment.
- **Validation rule, fixed in advance.** A module's reproduced
  limit must lie within a factor 1.3 of the published limit across the
  published mass range.
  - A module that passes enters likelihoods.
  - A module that fails is used only as a flag.
- **Gate.** At least one xenon module at level A or B and three modules on
  other targets pass.

### DM4 — Operator and model library

**Built 2026-09-29; record in [`dm4_library.md`](dm4_library.md).** The
library has 48 cards in three layers, a neighbour graph, kinematic
modifiers, validity checks and a degeneracy measure. Operator coefficients
may now depend on q.

Gate:
- Every degeneracy LZ states is reproduced: the five constant pairs
  exactly, and the isospin list exactly, with a clean gap of 21 to 296
  events.
- One unstated exact degeneracy was found: δ = 0 inelastic models are
  elastic ones.
- LZ's count of 293 does not follow from its stated rules, which give 325
  (322 physical). The discrepancy is recorded.
- **Gate accepted by the owner, 2026-09-30.**

- **Cards for each layer** of section 3. A card holds:
  - the interaction and its parameters, with priors;
  - its map to the layer below;
  - its validity conditions, e.g. a contact operator needs a mediator much
    heavier than the momentum transfer q = √(2 m_T E_R), which is about
    250 MeV for a 248 keV recoil on xenon;
  - which tiers of constraint apply;
  - its references.
- **Kinematic modifiers:** elastic, inelastic, exothermic.
- **The neighbour graph.** Edges are physical deformations: integrate out the
  mediator, take the nonrelativistic limit, add a mass splitting, change the
  isospin structure, make the mediator light.
- **Degeneracy classes.** Interactions with the same recoil spectrum on a
  given target are found numerically and grouped.
- **Gate.** The library reproduces LZ's reduction of 616 models to 293.

### DM5 — Path 1 for library models

**Built 2026-09-30; record in [`dm5_exclusion.md`](dm5_exclusion.md).** What
was built:
- the Path 1 pipeline and the command `adroit exclude`;
- the revised xenon responses LZ uses (`NuclearModel.haxton_2022`), verified
  exactly against the published tables from the old density matrices;
- LZ's extended window as a fidelity-B module.

Gate:
- The spin-independent picture: met (30 masses, 0.93–1.26).
- LZ's L10 curve: met (every mass, 0.83–1.04).
- LZ's inelastic O1 curve: met at 6 of 7 splittings, failing at
  δ = 150 keV (0.65), in the electron-recoil leakage region the module does
  not model.
- **Gate accepted by the owner, 2026-09-30**, with δ = 150 keV recorded as
  outside the module's domain.

- **Pipeline:** a library card with chosen parameters → rates → every
  validated module → limits in the (mass, coupling) plane, per experiment and
  combined → the exclusion plot and a report.
- **Gate.** The plot for the standard spin-independent interaction matches
  the published combined picture, and LZ's published limit curves for the
  inelastic O1 and L10 interactions are reproduced within the DM3 tolerance.

### DM6 — Signal fits and the tournament

**Built 2026-09-30; record in [`dm6_signal.md`](dm6_signal.md).** Signal fits,
global significance, tier-1 combination, tournament, forecast, and the
Path 2 pipeline (`adroit signal`), run on LZ's event of interest.

Gate:
- LZ's local significances: met, 94.6% within 0.3σ.
- Injected signals at 20 events:
  - 91.6% under DM4's single-linkage classes;
  - 71.0% under the stricter pairwise reading declared before the run.
- **Gate accepted by the owner, 2026-09-30**, with DM4's classes; the pairwise
  result is recorded as a finding.

**The inherited engine retired, 2026-09-30** (the owner's go-ahead; tag
`pre-retirement`). What went and what stayed is in section 4.

- **Signal fits.** For each library entry: best fit, local significance
  against background only, and confidence intervals. The global significance
  comes from toy Monte Carlo over the degeneracy classes.
- **Validation rule, fixed in advance.** Tables S7 and S8 of
  arXiv:2609.02823 (616 local significances) are reproduced to within 0.3σ
  for at least 90% of entries.
- **Tier-1 combination.** The joint likelihood with every validated module,
  and a consistency measure between the signal experiment and the null
  experiments.
- **The tournament.** The criteria depend only on what a model predicts:

  | criterion | quantity |
  |---|---|
  | signal fit | likelihood ratio against background only, in the signal experiment |
  | global consistency | joint likelihood with the null experiments (tier 1) |
  | complementary constraints | tiers 2 and 3, once DM7 exists |
  | information | an information criterion, penalising free parameters |

  - **Flags:** sensitivity to the halo model, operator validity, size of the
    coupling, nuclear uncertainty.
  - **Records:** sets of indistinguishable candidates, and contested winners.
  - **The null:** the background-only hypothesis is always a candidate.
  - **Sidebands:** the low- and high-energy regions around a signal enter the
    signal fit, since a candidate must also explain what was not seen there.
- **Forecast.** For the leading candidates: which target or experiment would
  separate them, and how many events would be needed. This is the output that
  matters most if a signal grows.
- **Gate.** The validation rule above; and on synthetic signals injected into
  a module, the injected interaction's degeneracy class is ranked first in at
  least 80% of cases at 20 events.

### DM7 — Complementary constraints

**Built 2026-10-01; record in [`dm7_constraints.md`](dm7_constraints.md).**
- Completions: the spin-1 simplified models of the LHC DM Working Group.
- Calculators, all the project's own:
  - the relic density (checked against MadDM's published contours);
  - capture in the Sun for any operator (checked against DarkSUSY's
    published capture rates);
  - gamma rays from dwarf galaxies.
- A curated database of eight records, verified by the owner on 2026-10-01.
- Applicability verdicts, recorded beside Path 2's ranking. Path 1 lists the
  neutrino telescopes' limits on μ.

Gate, read as fixed in advance against CMS's summary (arXiv:2405.13778) for
V1, A1 and A2:
- the translation to direct detection: met;
- the collider records: met;
- the relic contours: met at every point above m_DM = 10 GeV (343 of 343),
  not met as declared overall (V1: 78 of 100 points; all its failures lie
  below 8.4 GeV).
- **Gate accepted by the owner, 2026-10-01**, with the region below 10 GeV
  recorded as unresolved by the published figure and listed as a future
  improvement. The owner also approved the project's own relic and capture
  calculators (micrOMEGAs and MadDM are left for DM8), verified the eight
  records, and confirmed that complementary verdicts sit beside the ranking.


- **The curated database.** Versioned records, each with its source, DOI,
  data file, the model assumptions under which it holds, and the date it was
  verified. Agents may propose additions; a person verifies each before it is
  used.
- **Calculators.**
  - Tier 2: capture in the Sun, and neutrino-telescope limits.
  - Tier 3: relic density and indirect detection through micrOMEGAs or
    MadDM; collider limits on mediator models from published summaries.
- **Applicability verdict** for every (model, constraint) pair:
  - applies;
  - applies under stated assumptions;
  - cannot be applied without a further calculation, which is named.
- **Gate.** For three textbook mediator models, the combined picture agrees
  with a published summary.

### DM8 — Path 1 for arbitrary Lagrangians

**Built 2026-10-01; record in [`dm8_lagrangians.md`](dm8_lagrangians.md); the
owner's review is the last check (record, section 13).**
- **Built:**
  - the DirectDM bridge and matching against the library;
  - the explicit nonrelativistic reduction, which corrected eight mediator
    cards of DM4;
  - typed models and their checks, including the freeze-out flags and the
    owner's 28-item viability checklist;
  - derivations as formulas, the two agents, the pipeline and
    `adroit lagrangian`.
- **The gate:** 10 of 10 matched correctly, for $0.84 in all:
  - the deriver's half (claude-opus-5-5): $0.58;
  - the checker's half (gpt-5.6-sol): $0.26.
- **The numerical cross-check, without Mathematica** (record, section 14):
  - ADROIT's own UFO files equal DMsimp's vertex by vertex;
  - MadDM's relic density agrees with DM7's within 2.6%;
  - MadDM's quark-level coefficients agree with both agents' derivations
    within 0.4%, for the six gate models MadDM covers.
  - It found that the intake recorded only coupling names in its terms
    (corrected), and three bookkeeping issues in MadDM's release candidate.

A bespoke derivation is the one step that needs a language model, so this
milestone is opt-in throughout. A user without API keys can still supply the
operator coefficients of a bespoke model directly.

- **Intake.** An agent turns a Lagrangian or a particle content into a typed
  model: fields, representations, charges, interactions. Deterministic
  checks follow: gauge invariance, hermiticity, and an anomaly flag.
- **Matching.** If the model is equivalent to a library card, the card is
  used. Otherwise an agent derives the coefficients of the quark-level
  operators, and DirectDM carries them to the nonrelativistic operators.
- **Verification of a bespoke derivation,** in order of weight:
  1. deterministic checks: dimensions, known limits, recovery of the standard
     spin-independent and spin-dependent results;
  2. a numerical cross-check through the project's own UFO model files → MadDM
     (or micrOMEGAs), where
     those codes cover the interaction;
  3. an independent derivation by a second language model, compared
     numerically at random parameter points. The defaults are Claude Opus 5.5
     for the derivation and GPT-5.6 Sol for the check.

  A disagreement stops the run at a human gate.
- **The contract.** Following FERMIACC, the report lists what of the full
  model was dropped in the computed benchmark, and every mass and coupling
  carries a justification.
- **Gate.** Ten models with known answers are matched correctly, including
  three that are not in the library.

### DM9 — Path 2 agents

**Built 2026-10-01, offline; record in [`dm9_agents.md`](dm9_agents.md).**
- **The three agents** choose and write; code decides:
  - the variant agent picks from a menu along the neighbour graph, and
    variants are fitted and accepted by AIC with one more parameter;
  - the constraint scout reads deterministic arXiv searches, its references
    are confirmed against arXiv or Crossref, DM7's rules are enforced, and
    its proposals become records a person must verify;
  - the assumption audit weighs a deterministic inventory and must address
    every item.
- **The gate is declared** (record, section 5): twenty runs, six of Path 2
  and fourteen of Path 1 on bespoke models. The dry run with misbehaving
  scripted agents: 20/20 reports clean.
- **The gate passed, 20/20** (2026-10-01, $3.54 of the $8 approved). The
  scout's 148 references were all confirmed. Every audit was complete. No
  variant improved on its parent.

- **Variant agent.** Proposes deviations from a library case along the
  neighbour graph when the fit or a constraint calls for one. A variant is
  fitted like any candidate, and joins the pool only if it improves on it.
- **Constraint scout.** Searches the literature for constraints on a
  candidate, with the applicability verdict of DM7. Every reference is checked
  to exist before it is reported; DarkAgents found invented references in
  agent reports.
- **Assumption audit.** Following DarkAgents, one agent lists every prior,
  approximation and validity limit that entered the result.
- **Gate.** No unverified reference in any report, over twenty runs.

### DM10 — Evaluation suite and baselines

**Done 2026-10-02; record in [`dm10_evaluation.md`](dm10_evaluation.md). The gate passed, 5 of 5 of the owner's rules on the held-out half; $6.99 of the $10 approved for it.**
- **The harness** (`adroit/evaluation/`, `adroit eval`): two halves fixed by a
  hash, the held-out ledger, a results store per suite.
- **The suites:** limits (DM3's rule, point by point), LZ's tables, injection
  against N on four targets, and historical excesses. The last uses new
  modules built from the papers: CDMS II Si 2013 and CDMS II Ge 2009, each
  reproducing its quoted limit and exposure to 7%.
- **The baselines:** exhaustive fitting, measured on the injection cases; and
  direct prompting of claude-opus-5-5 and gpt-5.6-sol, run on both halves.
- **The comparisons** with published analyses are made where the system holds
  the inputs. The rest are listed with what is missing.
- **The gate's rules,** G1–G5, were adopted by the owner (record, section 6).
- **Path 2 now profiles the background's rate** wherever a search states its
  uncertainty (approved 2026-10-01). With it, CDMS II Si agrees with the
  literature on both items.

The plan as written:

- **Suites:**
  - limit reproduction (DM3);
  - LZ's tables (DM6);
  - injection and recovery, as a function of the number of events;
  - historical excesses with the literature's verdict.
- **Development and held-out halves.** The owner keeps the held-out half,
  which is run only to confirm a change.
- **Baselines:** exhaustive likelihood fitting with no agents; direct
  prompting of a language model.
- **Comparison with published analyses.** Where a published analysis did
  the same comparison by hand, the system's result is set beside it: the
  operator fits to DAMA, the global operator fits, and the combined fits of
  high-energy recoil events (`related_work.md`).
- **Gate.** The pre-registered rules of the owner's choosing.

### DM11 — Workbench, reports, documentation, paper, release

**Built 2026-10-02, $0; record in [`dm11_release.md`](dm11_release.md).**
- **`adroit setup`:** every external tool and data set, needed or optional,
  present or missing, and its licence. It fetches and builds what it can.
  On the owner's machine 9 of 9 required items are present.
- **`adroit workbench`:** a local web page that runs Path 1 and Path 2
  through the same code as the command line (`orchestrator/runs.py`), with
  the runs, DM10's evaluation and the tools.
- **The documents:** the design document (`docs/design.md`) and a first draft
  of the paper, kept with the development records.
- **Left for the owner:** the paper's revision, ADROIT's own licence before
  release, and the documentation audit (record, section 4).

The plan as written:

- A workbench and a dashboard for the two pipelines. The inherited ones
  were retired at DM6 (section 4); their code is in the tag `pre-retirement`.
- Write the design document and the paper. Every number cites its run.
- **A set-up command for the public release.** It reads the manifest of
  external tools and data and:
  - fetches and builds everything it can;
  - for each item whose source blocks automated downloads, tells the user
    what to download and where to put it, then checks that it arrived;
  - reports each tool's licence.

### The dual-track system (the owner's design, 2026-10-03)

The owner's design for the full system has two tracks over one engine:
- **Track 1: is an idea consistent, and what do the data allow?** The input
  is one of:
  - a field content with its representations, from which the most general
    Lagrangian is built;
  - a Lagrangian, which is checked for missing terms and other problems;
  - an idea in plain words.

  The system first decides whether the model is **valid**: Lorentz and gauge
  invariant, spins and statistics consistent with each term's structure,
  hermitian, of consistent mass dimension (higher-dimension terms are allowed
  within a valid EFT), stable and anomaly free. It then compares the model
  with the existing constraints. Its report gives the relevant literature and
  parameter-space plots with the exclusion limits.
- **Track 2: what explains an anomaly?** The input is a direct-detection
  anomaly (LZ's event, for example). The system fits it with the library of
  standard models and with models the user supplies, compares each with the
  other limits, and reports either:
  - a ranking of candidates for further exploration; or
  - for a single user idea, parameter-space plots and the literature.
- **Recursion.** Track 2's ranked list can be explored item by item: the best
  or most interesting candidate becomes a full Track 1 study.

**The owner's decisions (2026-10-03):**
- four milestones, DM12–DM15, built in order;
- ADROIT's own deterministic generator of renormalizable terms;
- higher-dimension terms allowed within a valid EFT;
- thermal dark matter for now (extended in later releases);
- a NiceGUI workbench, taking what can be taken from the inherited one;
- the agent decides within each milestone and declares each gate before it
  is run;
- testing budgets for the day: $10 Anthropic, $10 OpenAI.

### DM12 — The model front end (Track 1's inputs)

**Done 2026-10-03; record in [`dm12_front_end.md`](dm12_front_end.md). The gate passed (A 9/9, B 12/12 with no false alarms, C 4/4, D 6/6); $0.27.**
- **Group theory** (deterministic): the irreducible representations of SU(3)
  and SU(2) as weight systems; tensor products, symmetric and antisymmetric
  powers; and the number of independent invariants of a set of fields.
  Identical fields are symmetrised as their statistics require.
- **The most general Lagrangian** of a field content:
  - every gauge- and Lorentz-invariant renormalizable term among the new
    fields and the Standard Model's (scalar potential, mass terms, Yukawa
    couplings, vector currents, kinetic mixing), allowed by the stated charges
    and stabilising parity, with its multiplicity;
  - optionally, the dark sector's effective operators up to dimension 6,
    each with its cutoff Λ.
- **The audit of a Lagrangian:**
  - **validity:** Lorentz structure against the fields' spins, gauge
    invariance (full invariant counting), hermiticity, mass dimension against
    the coupling's, identities of self-conjugate fields (a Majorana vector
    current vanishes), stability, anomalies;
  - **missing terms:** those the model's symmetries allow but it leaves out.
    A term no stated symmetry can forbid is generated radiatively.
  - **EFT validity** of higher-dimension terms: Λ against the momentum
    transfer, the annihilation energy and collider energies, and a
    perturbative completion.
- **Free text → models** (an agent, opt-in): the agent proposes field
  contents with a reason each. The generator builds each one's Lagrangian,
  the audit checks it, and duplicates are removed.
- **One front end:** `adroit idea` (field content, Lagrangian or text) →
  typed models, each with its audit.
- **Gate** (declared in the record before it is run): textbook field contents
  give their textbook Lagrangians; seeded errors are all caught with no false
  alarms; omitted terms are found; free-text ideas give valid models that
  include the textbook one.

### DM13 — Parameter space and the verdict (Track 1's output)

**Done 2026-10-03, $0; record in [`dm13_parameter_space.md`](dm13_parameter_space.md). The gate passed except G3(b), missed by one point on the frame of CMS's plane (27/28), explained in the record. Built: spin-1 and scalar-mediator classes; scans against DM3's validated envelope and the curated records; the thermal verdict; the Track 1 report. Not yet: projected sensitivities, the neutrino fog, uncertainty bands.**
- **From a valid model to the constraints at any parameter point:**
  - DM8's matching (library cards) or derivation (formulas, checked by a
    second model, once per model);
  - then direct detection through every module;
  - the relic density (thermal);
  - the curated complementary constraints.
- **Scans:** 2D grids over chosen parameters (masses, couplings), with a
  cache of experiment limits, since a xenon limit costs minutes.
- **Plots:** each constraint's excluded region overlaid in the chosen plane,
  with the thermal-relic contour, projected sensitivities and the neutrino
  fog where curated, and uncertainty bands.
- **The verdict:**
  - validity, from DM12;
  - then, under the thermal assumption, whether a region survives every
    applicable constraint (viable, excluded, or undetermined for want of a
    calculation), with that region drawn.
- **The Track 1 report:** the model, its audit, the plots, the verdict, and the
  literature (DM9's scout, verified references; and a novelty search for
  prior work on the model).
- **Gate:** declared in the record.

### DM14 — Track 2 made general, and recursion

**Done 2026-10-03; record in [`dm14_track2.md`](dm14_track2.md). The gate passed, 5 of 5; $0.08.**
- **Anomaly intake:** a record template for a search with events (events,
  exposure, efficiency, background with its uncertainty, halo), digitisation
  helpers, and an optional agent that drafts the record from the paper, for
  a person to verify.
- **User models as candidates:** a DM12 or DM8 model, at each mass, enters
  Path 2 beside the library.
- **The single-idea report:** Track 1's report centred on the anomaly's
  best-fit region.
- **Studies:** every run records its inputs, steps, cost, outputs, parent and
  children. A Track 2 candidate (or degeneracy class) is promoted to a Track 1
  study, optionally with UV completions proposed by DM12's builder.
- **Gate:** declared in the record.

### DM15 — The workbench for the two tracks (NiceGUI)

**Done 2026-10-03; record in [`dm15_workbench.md`](dm15_workbench.md). The gate passed, 6 of 6; $0.06. Rebuilt rather than ported (the inherited screens served the retired pipeline); DM11's page remains as `adroit workbench --classic`.**
- Port the inherited workbench (tag `pre-retirement`) onto the new
  pipelines:
  - studies in place of projects;
  - a wizard for each track and input;
  - a live view with progress, events and spend;
  - typed gate forms (approve a proposed model list, confirm a budget,
    promote a candidate);
  - results with reports, plots and literature, and a button for recursion.
- Runs execute as subprocesses of the command line, controlled through files.
- **Gate:** declared in the record.

### After DM15 — the portal library (the owner's request, 2026-10-03)

**Built 2026-10-03; record in [`portal_library.md`](portal_library.md).**
- **The three types DM15's model builder proposed:**
  - a singlet scalar mixing with the Higgs;
  - a dark photon;
  - Majorana dark matter with a coloured t-channel partner.
- **Fifteen more portals** from a literature survey, each with a benchmark
  and references.
- **The engine they need:**
  - the off-shell Higgs width;
  - coannihilation;
  - interfering mediators;
  - explicit amplitudes;
  - exact kinetic mixing.
- **The validation** was declared before it was run.

### The viability checklist (the owner's list, 2026-10-01)

Thermal freeze-out is the working assumption. Every bespoke report states the
status of all 28 checks (`constraints/data/viability.yaml`). Built with the
list:
- the model's stabilising parity, relic fraction and cosmology;
- the flags for stability, perturbativity, the contact interaction and axial
  unitarity.

**Status (12 October 2026).** The current state of each item, built and
planned, is in `constraints/data/viability.yaml` (refreshed in R8). Of the
calculators listed below:
- **built:** CMB energy injection (portal library part 2); the invisible
  Higgs and Z widths (part 1); the BBN mass bounds (part 3); coannihilation
  (part 1); collider recasts through SModelS with MadGraph's cross-sections
  (parts 3 and 4); Sommerfeld enhancement and bound states (part 2); the
  scalar potential's vacuum (M24, with the tunnelling lifetime added after
  R6) and the running of couplings (M26), both for the complete scalar
  portal;
- **in part:** initial chemical equilibrium, as a conversion certificate for
  t-channel partners (M27, revised in R5); the UFO files and MadDM, as DM8's
  numerical cross-check rather than a routine step;
- **not built:** kinetic equilibrium, mediator lifetimes for BBN, CheckMATE
  and MadAnalysis 5, and the remaining phase-2 items
  ([`adroit_phase2.md`](adroit_phase2.md)).

The calculators come in this order:

1. **Next, small (the DM7 code and records):**
   - CMB energy injection: Planck's limit on p_ann = f_eff⟨σv⟩/m_χ, which
     also bears on the region below 10 GeV left open by DM7;
   - initial chemical equilibrium (Γ against H from x ≈ 1);
   - kinetic equilibrium where the checklist says it matters (resonances,
     forbidden channels);
   - the invisible Higgs and Z widths for the Higgs- and Z-portal cards;
   - the BBN mass threshold.

   New records are verified by the owner before use, as in DM7.
2. **With the numerical cross-check (DM8, after its gate):**
   - the UFO generator and MadDM: relic density, today's ⟨σv⟩ by channel and
     indirect detection for bespoke models;
   - coannihilation;
   - mediator lifetimes for BBN;
   - recasting of collider searches (SModelS, CheckMATE, MadAnalysis 5).
3. **Phase 2, light dark sectors** (`adroit_phase2.md`): beam dumps, rare
   meson decays, stellar and supernova cooling, self-interactions beyond
   Born, scattering with the plasma, free streaming, and electron recoils
   with light mediators in bespoke models.
4. **Phase 2, theory:**
   - Sommerfeld enhancement and bound states;
   - non-standard cosmologies;
   - secluded-sector temperatures;
   - flavour observables;
   - electroweak precision data and dipole moments;
   - decay through symmetry-breaking operators;
   - the scalar potential and its vacuum;
   - the running of couplings;
   - the thermal-relic unitarity bound above 10 TeV.

### Later extensions

See [`adroit_phase2.md`](adroit_phase2.md).

## 7. Decisions

Settled by the owner on 2026-09-29.

| # | decision | outcome |
|---|---|---|
| 1 | Recoil type | Nuclear recoils only. Electron recoils are in `adroit_phase2.md`. |
| 2 | Mathematica | Not used (the owner's decision, 2026-10-01): only open tools. FeynRules and SARAH are replaced by the project's own UFO generator. |
| 3 | Language models | An optional consistency check, never required. The user opts in at each call and is shown the model choice; defaults Claude Opus 5.5 and GPT-5.6 Sol. Both clients sit behind the one interface in `adroit/agents/`. |
| 4 | Validation tolerances | Limits within a factor 1.3 (DM3); LZ's table entries within 0.3σ for 90% (DM6). |
| 5 | First experiment modules | Both LZ searches, XENONnT, PandaX-4T, one argon experiment, PICO-60, CRESST-III, one germanium experiment. |
| 6 | Historical excesses | DAMA, CoGeNT, CRESST-II, CDMS-Si. |
| 7 | Statistics | Profile likelihood. Bayesian evidence is in `adroit_phase2.md`. |
| 8 | Hosting and licences | A private GitHub repository. External tools are called as dependencies, never copied in. |
| 9 | Halo model | The Standard Halo Model by default; any other velocity distribution may replace it. |

Raised by DM0 (see [`dm0_tool_audit.md`](dm0_tool_audit.md)) and settled by
the owner on 2026-09-29:

| # | decision | outcome |
|---|---|---|
| 10 | The rate calculation | The project's own implementation, in `adroit/physics/`, checked against existing codes. |
| 11 | Where compiled external tools are built | `~/agentic-dm-tools`: a folder without spaces, outside Dropbox (`ADROIT_TOOLS_DIR`). |
| 12 | The project's Python on Apple silicon | A native (arm64) build. |
| 13 | Dependencies at public release | The system fetches what it can, and prompts the user for what it cannot (DM11). |

## 8. Risks

| risk | handled by |
|---|---|
| An experiment releases too little for a faithful likelihood | fidelity levels; the reproduction gate; level C is never a likelihood term |
| Convention errors in matching (signs, factors, normalisation) | the conventions registry; deterministic limits; cross-checks against existing codes |
| Two language models share a mistake | the second model is the weakest of three verification layers |
| Invented references | every reference is checked to exist; the curated database |
| Collider or indirect limits applied outside their validity | validity conditions on the cards; the applicability verdict |
| The system is tuned to the LZ event | experiment modules; injection tests on other targets; a locked held-out suite |
| A closed library misses the true interaction | the variant agent; the background-only candidate; reporting when nothing fits |
| Few events cannot separate candidates | indistinguishable sets; the forecast of what would separate them |
| Halo uncertainty for high-energy recoils | a halo-sensitivity flag (built, DM6); halo nuisance parameters (planned, not built: see the status) |
| Others build the same thing first: DarkAgents plans further pipelines, and over a hundred papers interpreted the LZ event in four weeks | the system's claim is the systematic, validated ranking across the whole library and all constraints, which no paper or system found does; DM6 is reached without any paid run |

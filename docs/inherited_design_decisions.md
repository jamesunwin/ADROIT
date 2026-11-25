# Design decisions inherited from Nomothetica

ADROIT (then agentic-DM) began on 2026-09-29 as a copy of the Nomothetica system at its
commit `2a4fa6f`. The entries below are Nomothetica's dated design decisions up
to that commit, kept because they explain why the inherited engine behaves as
it does. The package name in them has been changed to `adroit`.
- Documents they cite under `docs/` (plans, lab records, the paper), the
  wildfire case study and the banked runs belong to the Nomothetica repository
  and were not copied.
- Decisions made in this project are recorded in its development history, not here.
- The engine was retired from ADROIT at DM6 (2026-09-30). Its code is in the
  tag `pre-retirement`; the modules named below are there, not in the
  current tree.

- **2026-09-23 — adjudication ranks by weighted aggregate, not pairwise
  majority.** Closing the pre-authorized M4 decision rule with data: the R1
  offline lab (docs/tournament_lab.md) re-adjudicated all 72 banked stage-A
  runs under both rules; the weighted aggregate scored 0.528 vs 0.472
  equivalence-aware top-1 and won 11/12 leave-one-family-out folds.
  `TournamentConfig.pairwise` now defaults to False; the pairwise
  (Condorcet-style) machinery remains importable for research.
- **2026-09-23 — population models integrate in log coordinates; families
  may register a data-informed warm start.** Lotka–Volterra now integrates
  u = ln x, v = ln y (positivity structural; the (x, y) form stalled the
  integrator on large-amplitude orbits and cost every stage-A LV fit its
  300 s budget). Families with closed-form moment identities register a
  `warm_start(t, y, observable, config)` beside their simulator; `fit_map`
  adds it as one advisory restart when no `extra_start` is given. A
  log-uniform restart draw for wide scale priors was tested and rejected
  (no gain). Details: docs/remediation_plan.md, R0 outcome item 5.
- **2026-09-23 — feature detectors respect their regime; cards may declare
  limit-regime signatures.** A power-law tail is a property of a sample of
  sizes, never of a smooth trajectory (lag-1 autocorrelation > 0.9 scores
  0). An oscillation's decay/growth lives in its amplitude envelope, and a
  clearly decaying envelope is not "saturation". Bistability means a level
  is revisited (>= 3 dwelling transitions), and is not sought in a coherent
  oscillation. A family card may carry the signature of its degenerate
  limit (the double-well's D → 0 descent is a saturating relaxation), so
  the deterministic prior can offer it to the re-ranker; the narrative then
  decides. Prior-only recall@3 on the benchmark: 0.417 → 0.750
  (docs/remediation_plan.md, R4 outcome).
- **2026-09-24 — a nested parameter is "zero" only when the Occam pass removed
  it.** The equivalence-aware metric (`eval/equivalence.py`) relabels a
  candidate as its nested family (Duffing beta = 0 -> linear oscillator) only when
  the reduction pass dropped the parameter by its Delta-AIC <= 2 test, or the
  estimate is exactly 0. The previous 5%-of-prior-span tolerance let the prior's
  width decide: under the canonical Duffing prior beta in [-10, 10], a recovered
  beta = 0.96 (truth 1.0) was scored as the linear oscillator, overriding the
  engine's own likelihood test. This affected full (3 R6 Duffing cells) and
  fit_only (0/6 on Duffing); the corrected numbers are in
  docs/remediation_plan.md, A1 outcome. Collaborator-approved metric change.
- **2026-09-24 — adjudication scores evidence against the family card and fit
  as a pool ratio.** `TournamentConfig` defaults to `evidence_mode="card"`
  (the fraction of confidently observed features the family's card can
  produce; nested siblings sharing a feature set tie, so the criterion
  abstains between them) and `fit_quality_mode="relative"` (RMSE_best /
  RMSE_i, invariant under y -> c y). The legacy definitions matched feature
  names against LLM-written prose (a canonical candidate with no prose scored
  0) and used 1/(1+RMSE), which is flat at small RMSE. Chosen by the
  pre-authorized leave-one-family-out rule on the 72 pinned R6 runs
  (docs/tournament_lab_a1.md): 0.778 vs 0.722 pooled, 10/12 folds.
  Legacy modes remain selectable for reproduction.
- **2026-09-24 — a refinement revision must out-predict the whole pool.**
  `RefinementLoop` defaults to `acceptance="pool_best"`: a revision joins the
  pool only if it beats its parent AND every candidate already in the pool
  on held-out error (AIC fallback). On the R6 runs, 58 of the 79 accepted
  revisions were dominated in this sense. They changed no top-1 answer (0/72,
  paired against each run's stored pre-refinement ranking) but pushed the
  truth down the ranking in lost runs (G5 −0.31 → −0.19). Same-family
  restrictions were rejected: they would ban switch_family, which supplies most
  of the frontier-improving revisions (docs/remediation_plan.md, A3).
- **2026-09-24 — a critical onset is a detectable feature; an oscillation must
  turn around.** `detect_phase_transition` reads an order parameter vanishing
  at x_c, y ~ (1 - x/x_c)_+^beta with beta < 0.8 (divergent slope) and a flat
  zero region past x_c, preferred by AIC over the best smooth decay. It seeks
  only order vanishing at the top of a sweep: the mirrored onset matches
  time series rising from rest. `detect_oscillation` additionally requires
  two turning points larger than 10% of the smoothed range, because a
  detrended step can put its spectral peak on a harmonic. Families with
  scale-free priors register data-informed warm starts: Ising uses the
  half-magnetization temperature T_half = 0.910 Tc and the Curie-Weiss tail
  (docs/remediation_plan.md, A2).
- **2026-09-24 — a converged fit is never discarded because its diagnostics ran
  long.** The M11 wall-clock budget (300 s) now covers the FIT only ("a fit that
  cannot converge in time is a failed fit"); its diagnostics get their own 300 s
  budget and keep whatever completes: residual whiteness and conditioning, then
  the held-out score, then k-fold stability. A cut piece is recorded as
  unavailable, which the criteria score neutral. Before this split, all four R6
  truth_fit_failed cells were converged fits killed during diagnostics
  (coupled oscillators: fit 163 s + diagnostics 208 s). The van der Pol easy fit
  itself takes 684 s and still counts as a failed fit (an open fitting-cost item).
- **2026-09-25 — the stated equation must be the fitted one.** A candidate is
  fitted with its family's simulator, which reads only the card's parameters,
  so the validation gauntlet rejects any declared parameter outside the card
  (and any symbol outside the family's parameters and state variables). Before
  this, a hybridize construction could declare an extra parameter (A5 run
  33210dbd: a linear candidate stating alpha*x^3) that the simulator silently
  ignored: the fit was linear, the reported equation was Duffing-like. Physics
  a family's simulator does not implement is reached only by switching to a
  family that does.
- **2026-09-26 — scripts that launch evaluations must guard their entry point**
  (`if __name__ == "__main__":`). The fitting pools use the spawn start method,
  which re-imports the launching script in every worker; an unguarded script
  re-ran a C2 launch in 6 workers ($2.05 duplicated). `run_matrix` now raises if
  called with confirm=True inside a worker process. Prefer the CLI entry
  point (`python -m adroit.eval.harness`), which is guarded.
- **2026-09-25 — prompts are laid out for server-side caching.** An agent
  whose calls share context puts it FIRST, via `agents.llm.with_cached_prefix`
  (stable part, CACHE_SPLIT, per-call part); the stable part must be
  byte-identical across calls (no ids, timestamps or task text in it). The
  client marks the system prompt and the stable prefix; the harness uses the
  1-hour cache (prompts recur every ~10-15 min in a sweep), interactive runs the
  5-minute default. Check new or changed prompts with
  `python -m adroit.eval.cache_report --prefixes` (must reach the model
  minimum, 1,024 tokens on Sonnet 5). Evaluation runs log every model call to
  provenance, with cache reads/writes; per-cell token splits go in TaskMetrics.
- **2026-09-25 — version-1 refinement has two moves: switch to a declared
  neighbour, or widen a pinned prior** (`agents.refinement.V1_ACTIONS`;
  collaborator's decision). add_term / remove_term / hybridize /
  change_noise_model are no longer proposed or applied, and stay in
  `RevisionActionKind` only so that older provenance still loads. Why: a
  family's simulator implements its template and nothing else. A dropped family
  term is already restored by the canonical floor, and a zero-valued one is
  removed by the Occam pass. A noise-model change refitted the identical
  candidate. Across the 144 R6/A5 runs the four moves changed the winning family
  once, harmfully. Card failure modes whose remedy no simulator implements keep
  their symptom and cause with `suggested_revision: null` (known limitations);
  7 were re-pointed to switch_family where a declared neighbour's deformation IS
  the stated cause.
- **2026-09-26 — two kinds of family: mechanistic and response_law**
  (`ModelFamily.kind`; docs/response_laws_plan.md RL1). A response law
  y = f(x; theta) is fitted from the candidate's OWN symbolic form
  (`library/algebraic.AlgebraicLaw`, via `Registry.simulator_for(candidate)`),
  so the stated equation is the fitted one. The data's kind decides
  eligibility (`library/eligibility.data_kind`): data with a variable of role
  `predictor` admit only response laws, and all other data admit only
  mechanistic families; among response laws, one predictor admits the
  single-driver laws and 2-8 the multi-driver laws. Anything that enumerates
  families for selection (suitability, the no-suitability ablation, fit-only,
  the prompting baselines' catalogue) must use
  `library.eligibility.eligible_families(library, kind, n_drivers)`, never
  `all_families()`. Multi-driver laws see drivers scaled by their median
  magnitude, x_k = value / s_k (RL3); the symbol and scale live on the
  predictor's `VariableInfo`. `tests/library/test_benchmark_invariance.py` checks,
  against a pre-RL1 snapshot, that no benchmark view changed. Response laws
  are ranked but not pruned: the generic shapes all "rise", so the likelihood
  must separate them.
- **2026-09-26 — the tournament states what the data do not settle.** Two
  changes, measured on the banked runs at $0 (docs/tournament_lab_plausibility.md):
  - Parameter plausibility is the MINIMUM over parameters (was the mean, which
    let an idle mid-prior parameter lift a law above its Occam-reduced sibling).
    Pooled top-1 on 180 banked mechanistic runs is unchanged (147/180).
  - The final adjudication records `indistinguishable` rivals (other laws within
    ΔAIC 2 whose held-out error is within max(10%, 1/sqrt(2 n_held-out))) and
    `contested` rivals (another law ahead by more than 2 in AIC). The report
    states them and `TaskMetrics.ambiguous` counts them. Rankings are unchanged.
- **2026-09-26 — one vocabulary for variable roles** (`core/roles.py`: time,
  response, predictor, group, ignore; RL4). Read roles only through
  `role_of` / `role_problems`; never substring-match `role_guess` elsewhere. A
  scientist's declared roles (`DataSourceRef.roles`, problem.yaml
  `admissible_data[].roles`) override the ingestion model. A run without the
  evidence gate STOPS when the roles are ambiguous; it never guesses which
  column is the response (C2: right column in only 3 of 6 ambiguous tables).
- **2026-09-26 — real data enter through ADROIT's own ingestion**
  (collaborator's decision). No preprocessing script sits beside the system:
  deriving an observable (e.g. a spread rate from daily fire masks) is a
  modelling choice, so it happens in an ingest module, typed, recorded in
  provenance and shown at the evidence gate. When a source format is not
  supported, the work is to add that ingestion capability, written in general
  terms (e.g. "an evolving region on a grid", not "a fire"); see
  docs/response_laws_plan.md RL6.
- **2026-09-27 — sub-daily steps come from observations dated at each
  overpass, not from per-pixel daily time stamps.** WildfireSpreadTS' active-fire
  band keeps one detection time per pixel per day, and this reversed the fitted
  day/night sign. The gridded source's `perimeters` + `detections` options
  (ingest/gridded/perimeters.py) take a perimeter product redrawn after every
  overpass (FEDS layout). Each window is dated by the median time of its
  detections, and its period is the window's rank within the day.
- **2026-09-27 — the multiplicative response law is written about the
  drivers' medians:** y = exp(a + Σ b_k (x_k − 1)) × (power x^b or saturating
  (1+c)x/(c+x) factors), so every factor is 1 at x_k = 1, and a is the log of
  the response there (prior [−14, 14]).
  - The old a·exp(Σ b_k x_k) made the amplitude trade off against the rate of
    any driver with a large offset (a temperature in kelvin, which varies by
    ~3% once scaled).
  - It also put a realistic amplitude at the bottom of a 12-decade linear
    prior.
  - Both zeroed the tournament's identifiability and plausibility criteria
    (RL7c).
  - The family of functions is unchanged (a reparameterisation). What
    changes are the parameters' meaning, the optimiser's path and the
    tournament scores.
- **2026-09-28 — a driver is expressed by how it is measured**
  (library/drivers.py).
  - Ratio scale (non-negative, with a true zero): x = value/median.
  - Interval scale: x = 1 + (value − median)/IQR. This covers a driver that
    takes negative values, or whose IQR is under 10% of its median (a
    temperature in kelvin).
  - Either way the median sits at x = 1. Power and saturating shapes are only
    used for ratio drivers.
  - The scientist may declare `predictor:ratio` / `predictor:interval`.
  - This replaces the RL7 widening of rates and exponents to ±30, which was a
    patch for temperature in kelvin. They are now in [−10, 10], which admits
    r⁴ and T⁴. The multiplicative log amplitude spans [−50, 50], so any units
    of y are accepted.
- **2026-09-28 — log-scale plausibility for scale priors was REJECTED** by its
  rule fixed in advance: pooled top-1 146 against 147 on the banked runs
  (docs/tournament_lab_plausibility.md). `plausibility_scale="log_wide"` stays
  selectable.
- **2026-09-28 — invariant ranking and flags (open problem 4).**
  - `TournamentConfig.ranking="invariant"` / `RunConfig.ranking` ranks only
    on criteria a relabelling of the parameters cannot change: fit quality,
    residual cleanliness, evidence, scope, and exp(−ΔAIC/2) for complexity.
  - Plausibility, identifiability and stability are always reported as FLAGS
    (`AdjudicationRecord.flags`).
  - `ParameterSpec.scale` (declared, else inferred: log for a positive prior
    of two decades or more) is used by the flags and by the refinement
    agent's "pinned" test.
  - The pre-registered rule did NOT adopt `invariant`: +7 on the 180-run
    gate, −1 on the 70-run replication, and the rule required no loss on
    either.
  - The OWNER adopted it as the default anyway, as a correctness fix (net +7
    over 264 runs), to be re-tested on the real-data suite
    (docs/tournament_invariant.md).
  - Conditioning and fold dispersion are now measured on natural scales (fit
    cache `m12-natural-scale`).
  - The engine gate's new baselines are 154/180 and 42/70.
  - `ranking: weighted` reproduces every earlier published number.
- **2026-09-28 — engine code stays domain-neutral.** Dataset-specific code
  lives in `examples/<case>/`. For example, the `perimeters`/`detections`
  gridded options take declared column roles, not FEDS's column names.
  External collaborators work by the rules in CONTRIBUTING.md.

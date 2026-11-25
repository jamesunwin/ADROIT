# Development guide

## Project purpose
ADROIT, the **Agentic Dark matter Reinterpretation and Operator Inference Toolkit**, relates models of particle dark
matter to data (design: `docs/design.md`; build plan: `docs/adroit_build.md`; release plan:
the release plan). Three workflows share one deterministic physics core:
- **Track 1, "Constrain a model"** (`adroit idea`, `adroit track1`): a model's parameter plane against
  every computed constraint, judged on its thermal-relic contour.
- **Track 2, "Signal best fits"** (`adroit signal`): candidate interactions fitted to a search with events,
  combined with the null searches, ranked in a tournament; recursion into the models that produce them.
- **"Explain a signal"**, the single-idea report (`adroit single-idea`): one model fitted to an anomaly,
  then Track 1 around its best fit.

Underneath are DM5's Path 1 (an interaction → each experiment's limit) and DM6's Path 2 (a signal →
ranked candidates). Today: 7 limit-setting experiment modules and 3 searches with events, 25 portals in
the portal library, 37 constraint records (each used only once a person has verified it).

It started on 2026-09-29 as a copy of Nomothetica at commit `2a4fa6f`, and the
two projects are developed separately from that point. Nomothetica's general
engine (model families, fitting, agents, evaluation, workbench) was retired at
DM6; what remains of it is the typed state, provenance, the human gates, the
language-model client and retrieval.

## Module map
- adroit/core/         typed state (Pydantic v2; dm_state.py for dark matter; state.py the inherited schemas), provenance store, config
- adroit/physics/      conventions and constants; halo models, nuclear responses, recoil rates (DM2)
- adroit/experiments/  one exchangeable module per direct-detection search, validated ranges (DM3, DM5);
                      anomaly records as modules (`record:<path>`, DM14)
- adroit/statistics/   Poisson limits, profile likelihood, Yellin's intervals (DM3)
- adroit/inference/    signal fits, global significance, tier-1 combination, tournament, forecast (DM6)
- adroit/constraints/  complementary constraints: spin-1 completions, annihilation, relic density
                       (with coannihilation), capture in the Sun, the curated database and the
                       verdicts (DM7); higgs.py (off-shell Higgs width), exchange.py, processes.py
                       (explicit amplitudes), kinetic_mixing.py (the portal library); tree.py (a general
                       tree-level 2 → 2 engine), ufo_model.py (published UFO models as its input),
                       sommerfeld.py (Sommerfeld factors, the multi-state solver, bound states),
                       searches.py (the searches' formulas and data), hadrons.py (the R ratio below
                       2 GeV), lhc.py + smodels_driver.py (SModelS, a program in the tools folder),
                       micromegas.py + mo_omega.c (micrOMEGAs, a cross-check), review.py (records'
                       curves, sources and the written verification)
- adroit/external/     the manifest of external tools and data (tools.yaml), the fetcher
- adroit/retrieval/    literature indexing (ChromaDB) and search
- adroit/agents/       the LLM clients (llm.py: Anthropic and OpenAI, `client_for`), DM8's
                      agents (lagrangian.py), DM9's (variants, scout, audit), DM10's
                      direct-prompting baseline (direct.py), DM12's model builder (ideas.py),
                      DM14's anomaly drafter (anomaly.py), the model intake (model_intake.py),
                      the experimental extraction (experimental_extraction.py) and the research
                      assistant (research_assistant.py); all behind the budget gate
- adroit/evidence/     evidence and provenance: portable export, integrity checks, deterministic replay
- adroit/theory/       theory certificates: vacuum stability (with the metastable lifetime),
                      partial-wave unitarity, running couplings, chemical equilibrium
- adroit/library/      the interaction library (interactions/), the personal model library
                      (personal.py) and the experimental library with its profiles
- adroit/evaluation/   DM10: the harness (halves, held-out ledger, results store) and the
                      suites (limits, lz_tables, injection, historical) and baselines
- adroit/model_building/  DM12: group theory (SU(3)×SU(2) weights, invariant counting), the most
                      general renormalizable Lagrangian, dark-sector EFT to dimension 6, the audit
- adroit/parameter_space/ DM13: computable classes (spin-1, scalar mediator), scans against DM3's
                      validated envelope and the curated records, the thermal verdict, plots;
                      simplified models that complete library cards (DM14); portals/ and
                      library.py: the portal library (Higgs, vector, pseudoscalar, t-channel,
                      UFO models, electroweak multiplets); searches.py: the searches applied
                      point by point; resonances.py: the LHC resonance searches (dijets, tt̄,
                      mono-h, mono-Z); dd_channels.py and limits.py: direct detection per channel
                      and module, with limit_tables.py (R10's precomputed limits); likelihood.py:
                      the combined-likelihood mode; crosscheck.py
- adroit/ui/           DM15: the NiceGUI workbench (`adroit workbench`): engine and runner
                      (command-line subprocesses through files), forms (pure), pages, wizards
- adroit/workbench/    DM11: the classic local page (`adroit workbench --classic`), on the shared
                      orchestrator/runs.py; `adroit setup` is adroit/external/setup.py
- adroit/orchestrator/ the pipelines (exclusion.py, signal.py, lagrangian.py; ideas.py and
                      track1.py for Track 1; single_idea.py, user_models.py, promote.py and
                      studies.py for Track 2 and recursion; reanalysis.py; checklist.py, R8's
                      viability checklist), human gates, control file, CLI (cli.py with the
                      models, experiments, reanalyse, records, evidence and theory sub-apps)
- scripts/             one-off derivations of bundled data (derive_records.py) and validations
- tests/               mirrors the package layout

## Coding standards
- Python 3.12, full type hints everywhere.
- Pydantic v2 models for ALL data passed between modules.
- Google-style docstrings on public functions and classes.
- Every public function is unit-tested. No function longer than ~60 lines.
- Prefer pure functions; isolate side effects (I/O, network, DB).

## Hard rules
1. All LLM-calling code lives in adroit/agents/ behind interfaces
   (LLMClient / FakeLLMClient), so the rest of the system is fully
   testable offline. No other module may import the anthropic or openai
   SDKs.
2. Every module ships with tests. "uv run pytest" must pass before any
   task is considered done.
3. Never commit .env, the top-level data/, or runs/. Never print API keys.
4. Fast tests must not hit the network; mark real-API tests @pytest.mark.live
   and slow tests @pytest.mark.slow.
5. ADROIT began as a copy of Nomothetica and is developed separately; it does not
   import from that project.

6. The core runs without any paid service. A language model is called only
   when the user has opted in to that call and been shown the model choice
   and the estimated cost. Every number in a result comes from
   deterministic code.

# DM9: Path 2's agents

Started and built 2026-10-01. Cost: $3.54 for the gate, which passed 20/20 (section 6).

The plan (build plan, DM9) names three agents: a variant agent, a constraint
scout and an assumption audit. Its gate is *no unverified reference in any
report, over twenty runs*. DarkAgents (arXiv:2606.11157) found agents
inventing references in their reports. Here, as in DM8, the agents choose and
write, and deterministic code decides.

## 1. The variant agent

`agents/variants.py`; the deterministic half is `orchestrator/variants.py`.
- **Triggers** (code): a leader of a Path 2 result calls for a variant when:
  - it is in tension with the null experiments (p_PG < 0.05);
  - a complementary constraint excludes it;
  - its best-fit coupling is above 4π.
- **The menu** (code): one-step deformations of the leader's card along the
  neighbour graph:
  - the other isospin;
  - the five mass splittings nearest the current one (the grid 25–200 keV,
    and ±50 and ±100 keV about it);
  - a light mediator (0.01, 0.1 and 1 GeV) where the card has one;
  - a neighbouring card at the same mass.
  - Only options the search's coupling convention can express are listed.
- **The agent** picks from the menu by index, at most two per triggered
  leader, with a one-sentence physical reason. The prompt carries the physics
  of each deformation. A pick off the menu, for an untriggered leader, or
  beyond two is discarded (`choose`), and the discards are reported.
- **Evaluation** (code): a variant is a Path 2 candidate like any other:
  fitted to the search's events, combined with the null experiments,
  flagged, and judged against DM7's complementary constraints. One variant
  takes about 4 s.
- **Acceptance** (code): a variant is chosen after the data are seen, so it is
  charged one more free parameter (k = 2 in AIC = −Z_joint² + 2k). It joins
  only if its AIC beats its parent's by more than the tournament's
  indistinguishability threshold (ΔAIC > 2): Z_joint² must rise by more
  than 4.
  - The tournament now takes per-candidate extra parameters.
  - Path 2 candidates can carry card parameters (a light mediator's mass).
- **On DM6's stored LZ result,** two leaders trigger:
  - L12s@4000, whose best-fit coupling is above 4π;
  - O01s@1000,d=350, excluded by IceCube's capture limits.

  Fifteen menu items result. For example, raising O01's splitting to 400 keV
  evades IceCube (capture is suppressed) but can no longer produce the
  event (Z_joint = 0), so it does not join.

## 2. The constraint scout

`agents/scout.py`, `retrieval/literature.py`, `constraints/scouting.py`.
- **The literature** (code): deterministic arXiv queries built from the
  candidate:
  - its interaction's constraints;
  - inelastic scattering at its splitting;
  - capture in the Sun;
  - colliders and the relic density, when it has a mediator;
  - light dark matter (CMB, BBN, beam dumps) below 10 GeV.

  Five abstracts per query, cached under `data/`. The scout reads only what
  these return.
- **The agent** proposes constraints, each with a class, DM7's applicability
  verdict, and the paper's identifier and title. It is told never to say
  whether the candidate is excluded (ADROIT computes that), and never to
  cite by author and year.
- **Vetting** (code):
  - Each reference is confirmed against arXiv or Crossref with its *own*
    claimed title. A real identifier attached to the wrong paper is caught.
    Unconfirmed proposals are dropped, and reported only by count.
  - DM7's rules: a tier-3 constraint cannot simply apply without a
    relativistic completion (→ needs_calculation); "needs_calculation" must
    name the calculation; "applies with assumptions" must list them.
  - Survivors become *proposed* `ConstraintRecord`s with `verified_on`
    unset. ADROIT uses none until a person verifies it, as DM7 requires.

## 3. The assumption audit

`orchestrator/assumptions.py` (the inventory, code) and `agents/audit.py`.
- **The inventory** is read from the result and its experiment modules, not
  written by a model:
  - each module's data, halo and nuclear model;
  - the statistics (the likelihood, the global significance's method, the
    classes, the tournament's criterion, the combination);
  - the model space; that there are no priors;
  - each leader's validity flags;
  - each complementary verdict's assumptions and needed calculations,
    grouped across leaders.

  For a bespoke Path 1 model it comes instead from the model's and the
  derivation's assumptions and dropped terms, DirectDM's scheme, the checks'
  flags, and the viability checklist. DM6's LZ result has 49 items; the DM8
  models have 21–34.
- **The agent** gives each item an impact (critical, material, minor) and its
  effect on the conclusion. It may add assumptions, which are shown as its
  own. `complete` lists any item it left out, and that list is in the
  report.

## 4. References, and the report

`retrieval/references.py`.
- **Finding:** arXiv identifiers (new and old style, and arXiv's own DOIs)
  and DOIs are found in text, bare or as arxiv.org and doi.org links (a
  Markdown link's target included: the auditor's LT16-01, 2026-11-16).
- **Checking:** arXiv's API and Crossref are the only network calls. Results
  are cached under `data/`; no network means no confirmation.
- **Cleaning** (`clean`), applied to every piece of agent text that reaches a
  report:
  - removes every identifier not on the confirmed list; a link to one is
    removed whole, its label with it, and a link to a confirmed paper kept;
  - removes every "X et al. (year)" citation. Module names such as
    "DEAP-3600 (2019)" are left alone.
- **Measuring** (`unverified_in`): on the final report, the identifiers not
  confirmed plus the author–year citations. This is the gate's measure.

`adroit agents RESULT.json --budget N` runs the agents on a finished Path 2
or bespoke Path 1 result: `orchestrator/agents.py`, opt-in and paid.

## 5. The gate, declared before the paid run (2026-10-01)

**The twenty runs** (`docs/dm9/gate.py`), all with claude-opus-5-5:
- **Path 2, DM6's stored LZ result** (`docs/dm6/lz_case.json`): variants, the
  scout on the three leading candidates, and the audit. Six runs, which are
  repeats, to see how the agents vary.
- **Path 1, the scout and the audit on bespoke models:**
  - the ten DM8 gate models (the deriver's half), once each;
  - the worked Majorana example, four times.

**The measure:** `references.unverified_in` on each run's final report, with
the live arXiv and Crossref services.

**The gate passes if the twenty reports hold no unconfirmed reference.**

**Reported, not gating:**
- the scout's proposals, confirmed and dropped (its invention rate);
- the corrections DM7's rules made;
- the audit's completeness, and its additions;
- the variants chosen, joined and discarded;
- the spend.

**The budget:** $8 cap, about $3.3 expected (Path 2 about $0.30 a run, Path 1
about $0.11). The literature calls to arXiv are free and cached.

**The dry run** (`--dry-run`, $0; `docs/dm9/gate_dry_run.txt`) uses scripted
agents that misbehave: a hallucinated reference, a real identifier with the
wrong title, author–year citations, stray identifiers in free text, and a
pick off the menu.
- **20/20 reports clean.** 3 of 9 proposals are confirmed on Path 2 and 1 of
  3 on Path 1, and every audit is complete.
- **The control:** the measure on raw agent text finds the invented
  identifier and the "Smith et al. (2019)".

**Changed before the run (2026-10-01), on a free check of arXiv's search.**
Plain queries returned poor matches; "inelastic dark matter constraints"
returned the Dark Energy Survey. The queries now use arXiv's field syntax
(`abs:"dark matter" AND abs:"anapole"`) with deterministic keywords:
- a mediator card's own name;
- what an operator's nuclear responses probe (spin-independent,
  spin-dependent, velocity-dependent);
- a bespoke model's mediator type, its electromagnetic moments, and whether
  it is Majorana.

This changes what the scout reads, not the gate's measure. The dry run still
gives 20/20.

## 6. The gate: passed, 20/20 (2026-10-01)

The owner approved one run with an $8 cap. Results store:
the live gate's record (dm9) and `.md`, with each run's report in
`docs/dm9/reports/`.

**The measure: 20 of 20 final reports hold no unconfirmed reference.**
claude-opus-5-5 spent $3.54.

**Reported, not gating:**
- **References:** the scout proposed 148 and all 148 were confirmed against
  arXiv or Crossref with their titles; none were dropped.
  - Grounding the scout in the retrieved abstracts was enough on its own.
    The vetting, shown at work in the dry run, had nothing to catch.
  - Path 2 runs proposed 11–16 references each, Path 1 runs 2–8.
- **DM7's rules:** no corrections were needed; the scout gave
  "needs_calculation" or "applies with assumptions" where the rules require.
- **The cleaner:** it removed 5 identifiers from agent prose, where citations
  are not allowed, and found no author–year citations. The run kept the
  cleaned reports, not the raw agent text, so whether those 5 were real
  papers is not known.
- **The audit:** all 20 audits addressed every inventory item (49 for LZ,
  21–34 for the bespoke models). The agent added 99 assumptions of its own,
  shown as its own.
- **Variants:** in the six Path 2 runs the agent chose 20 variants, all from
  the menu, with none discarded; none joined.
  - For the IceCube-excluded inelastic O1 leader, raising the splitting
    suppresses capture in the Sun but also removes the event (Z_joint = 0).
  - For L12 at 4 TeV, the operator limits do not lower the needed coupling
    enough to beat its parent.
  - So the variants do not resolve either trigger: an answer, not a failure.
- **Repeats:** the six Path 2 runs agree on everything but the number of
  references (11–16) and of variants (3–4). The four runs of the worked
  example agree, with 5 or 6 references each.

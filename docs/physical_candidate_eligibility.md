# M38 — physical candidate eligibility

M38 complete: 129 focused/1463 fast/25 slow tests; $0 API. Receipt: local report (summary). This follows the open-vocabulary M37.5
correction, whose64 focused/1455 fast tests passed. No model-style preference is
selected by default or used to change likelihood scores.

M38 assesses **individual fitted physical hypotheses**, never an entire model
family from one point or one completion. Match the exact canonical model/catalog
revision, mass, coefficients, declared physical range, detector spectrum/profile
likelihood and constraint assumptions. Reuse an explicitly supplied Track1 study
only when its exact point, model, profile and current scientific provenance match;
otherwise recompute with the same deterministic Track1 evaluator and report why
the saved point was not reused. No nearest-point matching or extrapolation.

Keep the original unfiltered tournament, background hypothesis and unconstrained
NR significance. Add an eligibility view and a separate provisional view for
unresolved inputs/branches. An applicable supported exclusion removes that fitted
point from eligibility; it does not invent a new likelihood penalty or exclude
all parameter branches. Pending calculations, absent completions, failed physical
inversions, incomplete bounded fits, mismatched assumptions and incomplete null
coverage remain visible. A bounded physical alternative whose spectrum/likelihood
differs from the NR optimum cannot inherit that optimum's score.

Acceptance: independently fixed allowed/excluded/pending points; exclusion of a
leading point reveals the next eligible representative; other points of the same
model/class survive independently; raw ranking/scores/significance stay unchanged;
model/source/profile/range tampering and stale/nearby saved studies cannot prune;
private limits/nulls propagate; evidence/export/replay and CLI/UI preserve both
views. Bounded fit/point-assessment budgets are explicit and exhaustion is pending.
Run focused and full offline regression, a real supported model/experimental
profile workflow, exact saved-point reuse and stale-resume refusal. No paid calls,
packaged scientific baseline changes, git mutations or DM10 held-out work.

This milestone does not add general inference coverage or recalibrate significance
after physical filtering. M29–M31 remain deferred. Reanalysis and complete release
journeys remain M39–M40/remaining M32.

Usage: Track2 assesses supplied physical models by default, with32 additional
candidate assessments at most. Bare NR operators remain unresolved until a unique
physical completion is supplied. The report leads with the eligible/provisional
views and retains the original unfiltered tournament. A missing source/computation
cannot become an allowed point. Thermal compatibility is checked against the
declared target at the existing1% numerical resolution; that threshold is not a
new experimental confidence interval. Eligibility currently requires standard
cosmology/full density; other declared histories/fractions stay pending rather than
using an implicit rescaling. Unverified exploratory bounds do not prune candidates.

```bash
adroit signal --experiment SEARCH --model 'catalog:MODEL@REVISION' --eligibility-budget 32
adroit signal --experiment SEARCH --model MODEL.yaml --track1-result runs/old/result.json
adroit signal --experiment SEARCH --model MODEL.yaml --no-eligibility
adroit evidence replay evidence.zip --index 0 --eligibility
adroit promote runs/signal HYPOTHESIS --include-excluded
```

The workbench exposes assessment budget and saved-result inputs. Profile selection
continues to pin the exact private limits/nulls. `--include-excluded` is an explicit
request to investigate alternative branches from an excluded fitted point, not an
override of its recorded exclusion. Class promotion omits excluded points by
default while preserving other members/completions of that class. Normal replay
reproduces the NR fit; `--eligibility` recomputes the captured physical point's
Track1 comparisons using recorded compatible private payloads without the local
catalog. Neither replay recomputes global toys or proves a whole-domain exclusion.

The displayed eligible/provisional AIC values are the original NR scores within
that view. They are not a new physical joint likelihood, boundary-calibrated
significance or a constrained-domain trials calculation. A physical alternative
with different spectrum/likelihood remains pending for a separately scored study.

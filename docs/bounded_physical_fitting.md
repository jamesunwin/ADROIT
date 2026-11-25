# Bounded physical fitting in Track 2

Track 2's free NR amplitude can demand a coupling outside a model's physical
range, or fail to describe a changing/nonmonotone coupling dependence. A
single-idea study now fits the actual recoil likelihood directly in those cases.
This first increment varies the model class's **g_chi slot only**, at fixed mass,
mediator mass and other couplings. It does not guess additional fit parameters.

## Declaring the fit domain

Add this optional field to a typed model/YAML input:

```yaml
physical_fit:
  parameter: g_chi
  low: 0.0
  high: 0.02
```

The bounds refer to `Point.g_chi` in the computable class, including its documented
portal meaning. They are not bounds on an arbitrary Lagrangian symbol or an NR
normalisation. The model's perturbativity and domain rules apply at every trial.
An invalid region leaves the fit pending rather than silently extending or
clipping its domain. Other fit parameters are deliberately unsupported here.

With a declared range the study directly fits that range. Without one, a
successful, verified amplitude inversion keeps its existing behavior. If that
inversion fails, the fallback uses the existing original-sign branch
0 ≤ |g_chi| ≤ √(4π), taking the positive branch for a zero baseline. A different
range, including a wider range permitted by a particular portal or both signs,
must be declared explicitly. This does not change the model's numerical methods.

CLI usage is unchanged except for two optional numerical controls:

```bash
uv run adroit single-idea my_model.yaml --experiment "CDMS II Si (2013)" \
  --masses 7,10,12 --grid 4 --toys 1000 --no-literature \
  --fit-grid 33 --fit-evaluations 512 --out runs/bounded_fit
```

`--fit-evaluations` caps distinct spectrum evaluations plus independent final
verification **per fit**, not per entire study, and is not a dollar budget.
Thermal refinement can request additional fits at intermediate masses. The
Python request supports `physical_fit_settings=FitSettings(...)`. Promotion
preserves the typed model and its declared range in its single-idea children.

## What is fitted and checked

`parameter_space/physical_fit.py` maximises the search's same extended unbinned
likelihood, profiling its stated background-rate nuisance. Every trial constructs
the actual model interaction and detector spectrum; there is no free signal
strength at this stage. The model's masses and other couplings remain fixed.

Linear probes and, where the range reaches zero, logarithmic weak-coupling probes
locate candidate modes. Local maxima and both endpoints are checked, then the
probe mesh is refined. A changed maximum, missing/invalid predictions, a flat
unidentifiable likelihood, a failed optimiser or an exhausted evaluation budget
produce an explicit pending result. A fresh final prediction checks the maximum.
Finite resolution is declared evidence, not proof that all arbitrarily narrow
modes were found.

The output retains bounds, numerical settings, evaluated point/count/log likelihood,
boundary status, evaluation count, sampled modes and disconnected likelihood
regions. Multiple equally good physical modes remain unresolved for thermal
follow-up; the code does not choose an arbitrary sign and declare viability.
Nominal one-parameter 68% regions use the same likelihood-ratio threshold as the
existing signal fit. Regions truncated at a bound are identified explicitly;
their frequentist coverage at physical boundaries has not been calibrated.

A physical fit need not reproduce the unconstrained amplitude's likelihood:
a restricted model may fit worse, and a changing spectrum can fit differently.
Both results are retained, including their log-likelihood difference. Fit quality,
constraint judging, the physical-band plot and thermal follow-up use the resolved
physical point. The plot window respects a declared coupling range. Missing fits
are never bridged by a thermal root search, and roots retain density certificates.

## Statistical limits of this increment

The earlier NR fit, its mass-search global significance and its null-amplitude
combination remain separately labelled **unconstrained reference calculations**.
They are not relabelled as a constrained joint fit. Physical q0 is reported as a
likelihood-gain diagnostic; a new discovery significance for this bounded domain
would require appropriately fitted background-only toys. The existing fit-quality
threshold is a screening rule, not a discovery claim.

The opt-in [native joint pilot](native_joint_likelihood.md) now fits CDMS II Si
and DEAP coherently and calibrates its own bounded domain with background-only
toys. The signal-only band and its unconstrained NR references stay separate.
Additional native adapters, multi-parameter fitting, nuisance-coverage studies
and coverage of every alternative thermal branch remain further extensions.

## Validation evidence

Meaningful tests cover interior and both endpoint optima, disconnected regions,
equally good modes, invalid islands, budget exhaustion, flat likelihoods,
independently changed predictions, declared-range transport and failed/zero
amplitude inversion. Ordinary successful inversion still reproduces the original
full spectrum and likelihood. Real silicon fits are compared with independently
specified dense physical scans and a separate Brent background-nuisance solver.
The dated local report and logs (summary) record the exact cases,
results, tests and end-to-end single-idea/promotion runs. No paid LLM or held-out
DM10 evaluation is needed for this extension.

# Declared-scale scalar running (M26)

`adroit theory running docs/examples/complete_scalar_running.yaml --out RUN_DIR`
performs a free, deterministic one-loop check. Track 1 and single-idea Track 2
studies save the same certificate when `scalar_running` is supplied with a
complete singlet contract. There is no default upper scale or SM matching input.

The request gives MSbar `g_prime`, `g`, `g3`, `y_top` at the potential's scale,
their provenance, the requested upper scale, scalar matching quality and
`full_theory_no_decoupling`. Hypercharge is Q=T3+Y, without GUT normalization.
This mass-independent treatment keeps all model fields active at all scales;
it does not silently integrate out a heavy singlet. The existing tree-level
Higgs component accepts only `tree_level_identification`, explicitly retaining
its matching limitation. A standalone input can instead provide directly
specified MSbar coefficients:

```yaml
potential:
  scale_gev: 200
  v_gev: 246.22
  mu_h2_gev2: 7800
  mu_s2_gev2: 40000
  lambda_h: 0.13
  lambda_s: 0.2
  lambda_hs: 0.1
running:
  matching:
    scale_gev: 200
    g_prime: 0.36
    g: 0.65
    g3: 1.15
    y_top: 0.94
    provenance: Illustrative inputs only; replace with your matching calculation
  upper_scale_gev: 2000
  scalar_matching: declared_MSbar
  threshold_policy: full_theory_no_decoupling
  matching_note: Direct coefficient inputs; no precision matching inferred by ADROIT
```

These are illustrative numbers, not a precision matched SM benchmark.

The beta functions follow [Gonderinger et al., Appendix C](https://arxiv.org/abs/0910.3167):
source lambda=6 lambda_H, a2=lambda_HS/2, b4=lambda_S, m²=−mu_H²,
b2=mu_S². The top is the only retained Yukawa. Quadratic coefficients also run;
constant vacuum energy and field rescaling are unnecessary for the tested
quartic criteria and are not calculated.

The criteria are running strict quartic copositivity, the complete M25 scalar
contact partial waves, and a separately labelled gauge/Yukawa squared-coupling
cap of 4π. Marginal initial conditions or endpoint/crossing ambiguity remain
unresolved. Integration stops at the first criterion crossing. A numerical
magnitude guard is reported as `pole_guard`, never a measured Landau-pole
location. The certificate exports all inputs, identity, trajectories, crossing
scale/criterion, tolerances and the Radau/DOP853 comparison. That numerical
difference is a diagnostic, not a rigorous interval error bound.

Running quartic boundedness is separate from the M24 tree vacuum. This does not
compute a quantum effective potential, tunnelling lifetime, thermal history or
higher-order SM matching. It does not change relic rates or experimental limits.

[PyR@TE](https://github.com/LSartore/pyrate) was assessed: it generates general
RGEs from separate model files rather than supplying a ready ADROIT singlet
matching adapter. For this narrow milestone the published equations use existing
NumPy/SciPy dependencies; no Mathematica or new external generator is installed.

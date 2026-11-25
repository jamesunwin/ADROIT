# Tree-level scalar vacuum certificate (M24)

ADROIT now certifies boundedness and the declared vacuum for the complete real
Z2 singlet potential from M23. The result is tied to every coefficient, declared
vacuum, field identity and scale. It covers the tree-level scalar potential over
its entire physical field domain. Quantum lifetime, thermal history, partial-wave
unitarity and RG evolution are separate questions (M25–M27).

## Calculation and conventions

With `x=H†H>=0`, `y=S²/2>=0`, the complete potential is

```text
V(x,y) = -mu_H²*x + mu_S²*y + lambda_H*x² + lambda_HS*x*y + lambda_S*y².
Declared electroweak vacuum: x=v²/2, y=0.
```

Its quartic part is copositive when `lambda_H>=0`, `lambda_S>=0` and
`lambda_HS+2*sqrt(lambda_H*lambda_S)>=0`. The conditions follow from the
[2×2 copositivity criterion of Kannike](https://arxiv.org/abs/1205.3781).
At equality, ADROIT also checks the quadratic coefficient along every physical
quartic-null ray. A negative coefficient makes the full potential unbounded,
even though the quartic part is nonnegative. Exact flat directions with zero
quadratic slope can support continuous stationary families.

The global calculation enumerates the origin, both axes, the interior solution
of the two linear stationarity equations, and all singular stationary families,
intersected with `x>=0,y>=0`. Each family exports its equations, anchor,
directions and parameter interval. Field-space boundaries are therefore included.
Nonzero S describes two Z2-related signs; gauge-equivalent Higgs orientations
are identified. No field grid supplies the global-minimum proof.

Local classification uses radial curvatures and, where a curvature vanishes,
the relaxed-field quartic. For example, at the Higgs axis with zero singlet
curvature, the relevant quartic is `lambda_S-lambda_HS²/(4*lambda_H)`.
A nonnegative Hessian alone does not prove a minimum in that case.

Exact rational algebra uses the represented input floats to enumerate branches
and detect exact degeneracies. Nonzero margins below the declared relative
resolution (default `1e-10`) remain **unresolved**. This covers nearly singular
stationary matrices, near-flat copositivity boundaries, nearly vanishing
curvatures and indistinguishable depths. Exact equality is treated separately.
Finite-range conversion failure also remains unresolved. Parameters are retained;
small electroweak stationarity residuals are exported, and the canonical solved
stationary point is compared with the declared vacuum within the stated tolerance.
This prescription does not model parameter uncertainty.

## Reading the result

- **global:** the declared local minimum is the unique global gauge/Z2 orbit.
- **degenerate:** it shares the global depth with another physical orbit or a
  continuous family; this is a passing, marginal certificate with explicit detail.
- **local:** it is a local minimum, with a deeper competing vacuum or runaway;
  the declared vacuum fails the global test. No lifetime is inferred.
- **unstable:** the declared point is nonstationary or locally unstable.
- **unresolved / missing_input:** no passing certificate is issued.

`boundedness` and `quartic` are separate fields. A local vacuum in an unbounded
potential has `passed=false`; it has no finite global minimum. `complete=true`
can describe either a proved pass or a proved failure. `passed=null` means the
claim is unresolved/missing. Equations, competitors, exact family descriptions,
runaway witnesses, numerical residuals and the parameter SHA256 are exported.

## Use through either track

Complete scalar points automatically carry `vacuum_certificate` in `result.json`.
Both the Track 1 and single-idea reports show a separate tree-level assessment;
common evidence exports carry the same certificate. Structural `audit.valid`
and experimental confidence-level comparisons retain their own meanings. A
failed global-vacuum certificate invalidates the declared DM vacuum at tree level,
even when its separate thermal/experimental view has no exclusion.

The calculation uses the M23 family coordinates: vary `m_S` and `lambda_HS`,
derive `mu_S²=m_S²-lambda_HS*v²/2`, and fix Higgs inputs, lambda_S and scale.
There is no default lambda_S for old benchmark inputs. Loading or exporting an
older saved study never synthesizes a certificate. Explicit replay may calculate
one as additional current evidence; when absent originally, it is retained in the
actual replay and explicitly excluded from the comparison of saved conclusions.
A certificate saved in a new result is strictly compared during replay.

## Standalone check

```bash
uv run adroit theory vacuum docs/examples/complete_scalar_singlet.yaml \
  --out runs/scalar_vacuum
```

This writes `vacuum.json` and `report.md`, using no LLM or paid service. A legacy
model without `scalar_potential` receives a missing-input result. Explicit extra
interactions inconsistent with that potential are refused.

Theory-only inputs also accept complete coefficient YAML, which can describe
zero/tachyonic curvatures or an unstable declared vacuum:

```yaml
scale_gev: 100
v_gev: 1
mu_h2_gev2: 1
mu_s2_gev2: -2
lambda_h: 1
lambda_s: 1
lambda_hs: 5
```

This example has a locally stable electroweak vacuum at V=-0.25 GeV⁴ and a deeper
singlet vacuum at V=-1 GeV⁴. The declared vacuum is `local`, with a failed global
test. This theory-only input does not widen the positive-mass M23 engine map.
Missing coefficients, scale or vacuum are not filled in by the tool.

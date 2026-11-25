# Native joint signal/null likelihood pilot

For the separately labelled M28 named-parameter fit, see
[bounded multiparameter fitting](multiparameter_physical_fitting.md). The
one-parameter calibration below is unchanged and is not reused to calibrate
the larger physical search.

Track 2 can now fit one physical model coherently to **CDMS II Si (2013)** and
**DEAP-3600 (2019)**. This is native to ADROIT's declared public-data experiment
modules (fidelity B), rather than the collaborations' complete unreleased
likelihoods. The earlier limit-equivalent combination is retained separately.

## Run the pilot

Use a computable pure-SI vector mediator or scalar–scalar mediator model, and
declare the coupling domain in its typed YAML:

```yaml
physical_fit:
  parameter: g_chi
  low: 0.0
  high: 0.02
```

```bash
uv run adroit single-idea my_model.yaml --experiment "CDMS II Si (2013)" \
  --masses 50,70,90 --null "DEAP-3600 (2019)" \
  --native-joint "DEAP-3600 (2019)" --native-toys 1000 \
  --native-seed 20261007 --native-fit-budget 3000 \
  --toys 1000 --grid 4 --no-literature --out runs/native_pair
```

`--native-toys` controls the new calibration. `--toys` still controls the
unconstrained NR reference. `--native-fit-budget` limits the total number of
mass/coupling fits across native toys, **not dollars**. The example needs
3 × 1000 = 3000 toy fits. All these calculations cost $0 in API calls.
The same four `--native-*` options are available on `adroit promote`; promotion
uses its own recorded mass bank, which must also lie inside the detector envelope.

Python requests accept `SingleIdeaRequest(native_joint=JointSettings(...))`.
The result's `native_joint` field contains every per-mass physical fit, shared
best point, component log likelihoods, assumptions and calibration record.
The fitting controls remain `physical_fit_settings=FitSettings(...)`.

The domain is a **discrete supplied mass bank**, with continuous bounded g_chi;
mediator mass and all other couplings stay fixed. It is not a calibration of a
continuous mass scan or of arbitrarily chosen extra parameters. Bounds must
contain zero and occupy one sign branch. Without explicit bounds, the existing
original-sign perturbative branch is used. DEAP's validated SI envelope starts
at approximately 49.71 GeV and ends at 9942 GeV. The pilot refuses incomplete
coverage instead of dropping low masses. Other signal/null pairs, interaction
classes and both-sign domains remain pending, apart from the low-mass PICO adapter below.

The historical silicon signal module has public-event/response reconstruction
and checks of the paper's quoted numbers, rather than a DM3 continuous
published-limit envelope. No silicon limit curve is used or claimed validated
by this joint likelihood extension.

## The likelihood

At each physical point p, the same interaction predicts both the silicon event
intensity and argon expected count. There are no independent fitted detector
signal strengths. For silicon the extended unbinned likelihood is

\[
\ell_{\rm Si}(p,\theta;a)=-s_{\rm Si}(p)-\theta B
 +\sum_j\log\{s_{\rm Si}(p)f_p(E_j)+\theta b(E_j)\}
 -\frac12\left(\frac{\theta-a}{\sigma_{\pm}}\right)^2,
\qquad \theta\geq0.
\]

The background scale is profiled once. Its auxiliary likelihood uses sigma_plus
when θ > a and sigma_minus otherwise. The auxiliary observation a is real;
its toy draws are not clipped to positive values. The published three-event
list, 0.41 surface-event estimate and asymmetric errors come from
[the CDMS paper](https://arxiv.org/abs/1304.4279). The module's energy shape,
declared 0.5-keV resolution and omitted neutron/Pb upper-bound contributions
remain documented reconstruction choices; the pilot does not claim to reproduce
the collaboration's full significance.

DEAP observed zero candidates in its
[758-tonne-day search](https://arxiv.org/abs/1902.04048). Its component is

\[
\ell_{\rm Ar}(p)=\log\left\langle e^{-s_{\rm Ar}(p)\epsilon}\right\rangle.
\]

The average uses the module's positive, eight-sigma truncated Gaussian
Cousins–Highland sensitivity model, with the same propagated light-yield and
exposure uncertainties as its native counting limit. A stable analytic integral
replaces repeated numerical integration; no published exclusion curve is turned
into a surrogate likelihood. Unavailable quenching/acceptance errors remain
omitted. DEAP has zero assumed background in this pilot. The two modules use the
same fixed published SHM; detector nuisances are independent. No halo/theory
nuisance is fitted or counted twice.

Known quadratic SI dependence on g_chi permits exact reuse of prepared detector
spectra. Preparation checks direct predictions at two smaller couplings in both
detectors and checks that the DEAP relative uncertainty is unchanged. Unsupported
dependence is rejected. Both detectors' counts always scale together.

## Physical-domain significance

The observed statistic is twice the maximum joint log-likelihood gain over
background alone, searching the recorded masses and bounded coupling. Every
background-only toy repeats precisely that search, including its endpoints.
Silicon events are Poisson draws at the fitted null background rate and are drawn
from the module's exact piecewise-linear background density. Auxiliary draws use
the normalized asymmetric Gaussian model: below θ their probability and width
are sigma_plus/(sigma_plus + sigma_minus) and sigma_plus, respectively. DEAP's
zero-background null generates zero events.

This is a **conditional plug-in nuisance calibration**, not a proof of uniform
coverage over every nuisance value. Shared halo parameters are fixed by design.
For k exceedances in N completed toys, the output reports
`p_MC = (k + 1)/(N + 1)`, a binomial 95% interval, the seed, all toy maxima and
the smallest resolvable p-value `1/(N + 1)`. Z_MC is the nonnegative one-sided
Gaussian equivalent. Numerical ties use the recorded q0 tolerance, derived from
the log-likelihood fitting tolerance. Failed fits, missing masses or exhausted
toy budgets yield **no calibrated p-value**.

The existing global significance remains explicitly labelled an **unconstrained
NR reference**. Native-pair calibration is a separate result and does not cover
additional null constraints, the main signal-only fitted band, or its thermal
headline. The per-fit nominal 68% likelihood regions are not given new coverage
claims by this discovery calibration.

## Validation

Tests compare nuisance profiles with an independent optimizer, sensitivity
averaging with quadrature, physical maxima with dense scans, auxiliary draws and
background draws with their generating distributions, and calibration with an
exact Poisson tail. Missing detector coverage and incomplete simulations are
tested explicitly. Dated local evidence (summary) includes
fresh physical predictions for both detectors, reproduction of native counting
limits, the full regression suites and single-idea/promotion workflows. No DM10
held-out evaluation or paid LLM call is used.

## Low-mass coverage: CDMS Si + PICO-60

The second native adapter uses PICO-60's 3/0 observed bubbles at 2.45/3.29 keV
in 1404/1167 kg-days. The same point predicts both exposure counts and the
silicon spectrum. Independent nonnegative PICO backgrounds are profiled at
max(0,n_i−s_i). Its likelihood is relative to the saturated null maximum, an
observation-dependent constant that cancels from every likelihood ratio.

The existing best-fit C/F nucleation curves and common published halo are used.
Unavailable calibration/threshold covariance remains omitted: fidelity B.
[The source, section VI and Fig. 8](https://arxiv.org/pdf/1902.04031) supplies the
counting construction and SI comparison. The new native certificate passes the
unchanged 1.3/3%-edge rule at 27 masses from 4 to 80 GeV, with ratios
0.8254–1.0208. Changed response inputs invalidate it. It enables the native
likelihood only; existing DM3 limit masks and record verification stay unchanged.

```bash
uv run adroit single-idea docs/examples/native_low_mass_model.yaml \
  --experiment "CDMS II Si (2013)" --masses 6,8.6,12 \
  --null "PICO-60 C3F8 (2019)" --native-joint "PICO-60 C3F8 (2019)" \
  --native-toys 1000 --native-fit-budget 3000 --toys 1000 --grid 4 \
  --no-literature --out runs/native_low_mass
```

For promotion, `--mass-span 1.2 --mass-points 3` declares a smaller mass bank
around the candidate. Out-of-envelope masses are refused rather than dropped.

## Nested nuisance-coverage checks

```bash
uv run adroit native-coverage docs/examples/native_coverage.json --out runs/nuisance_check
```

Every outer dataset is generated at specified **true** silicon/PICO backgrounds.
Its own nuisance estimates are fitted, then its significance is recalibrated
with independent inner toys. Both stages retain the same mass bank and coupling
bounds. The diagnostic measures false positives at the declared alpha, with
simultaneous Bonferroni/Clopper–Pearson intervals over the supplied finite grid.
Budget/numerical failures remain incomplete and cannot certify coverage.

For PICO toys, the profiled likelihood is concave in the shared rate factor.
The exact optimizer works in total predicted events and uses an upper search
bound from total observed counts, retaining the physical coupling bound. Tests
match full bounded fits and extreme reference-count normalizations. DEAP's
sensitivity mixture retains the general solver.

Five scenarios with 200 outer datasets/199 inner toys required 600,000 maxima.
An independent confirmation of two nontrivial scenarios used 1000 outer datasets
each and another 1.2 million maxima. Confirmation rates were 3.6% and 5.4%,
with intervals [2.256%,5.403%] and [3.725%,7.513%]. They are compatible with
nominal 5%, but do not prove <=5%, uniform coverage elsewhere, or confidence-region
coverage. Native significance remains explicitly conditional.

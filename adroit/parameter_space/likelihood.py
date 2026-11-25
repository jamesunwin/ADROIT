"""The combined-likelihood mode: constraints added together, with theory uncertainties, beside the hard cuts.

The default verdict applies each constraint as its own 95% CL cut. This mode combines them,
as a fit would, in the asymptotic Gaussian approximation:

- **A limit** (most constraints): a 95% CL upper limit with no excess is a Gaussian likelihood
  for the signal s with σ = s₉₅/z, so a point predicting r = s/s₉₅ contributes q = (z r)².
  z = 1.645 for a one-sided limit; z = 1.96 for a two-sided interval's upper end (the xenon
  searches through DIAMX use alea's two-sided t̃; ``limits.sidedness``). With a relative theory
  uncertainty δ on the prediction, profiled as a log-normal nuisance (s → s e^{κθ}, θ ~ N(0, 1),
  κ = ln(1 + δ), so one standard deviation multiplies the prediction by 1 + δ), x = z r and
  q = min_θ [x² e^{2κθ} + θ²] = (2w + w²)/(4κ²), w = W₀(2κ²x²) (Lambert's W). For κx ≪ 1 this is
  x²(1 − κ²x² + …), the Gaussian result; for large r it grows as (ln r)²/κ², so no theory uncertainty
  hides an arbitrarily large excess. (The earlier Gaussian nuisance, s → s(1 + δθ), gave
  q = x²/(1 + x²δ²) → 1/δ², which never exceeds 2.71 for δ ≥ 0.61: audit M12.)
- **A measurement** (the muon's g − 2) contributes its Δχ² against the Standard Model.
- **A contour or a band without a ratio** (CMS's planes, ATLAS's squark contour, beam dumps,
  LEP's inert-doublet region, perturbativity) remains a cut.

The point is excluded if q = Σ q_i > 2.71 (one-sided 95% CL on a common signal strength:
r_comb = √Σ r_i² > 1 without theory uncertainties) or if a cut excludes it.

**The relic band.** Ωh² is compared with Planck's 0.120 ± 0.0012 with a relative theory
uncertainty δ_Ω on the prediction (10% by default: the spread between relic codes, and the
long-range effects' uncertainty where coannihilation dominates), χ²_Ω = ((Ωh² − 0.12)/σ)²,
σ² = 0.0012² + (δ_Ω Ωh²)². Grid points with χ²_Ω < 3.84 form the thermal band that replaces
the contour.
"""

from __future__ import annotations

import math

from adroit.core.state import StrictModel
from adroit.constraints.planck import read

Q_95 = 1.645 ** 2                # one-sided 95% CL
Z_95 = {"one-sided": 1.645, "two-sided": 1.959964}
BAND_95 = 3.84
# The relic target as this process read it: Ωh² and its error from one read of the density record, with that record's
# version, which every thermal claim decided against it is bound to (the auditor's CS recheck, CT-02, 2026-10-28). The
# target's value, its error and the coverage diagnostics' target are all this read, never a later one; whether the
# record, as read, was verified (``DENSITY_USABLE``) decides whether a thermal claim may rest on it (AL1-07).
DENSITY, DENSITY_VERSION, DENSITY_USABLE = read()
PLANCK_SIGMA = DENSITY.sigma


class LikelihoodSettings(StrictModel):
    """The combined-likelihood mode's theory uncertainties (relative)."""

    relic_theory: float = 0.10           # on Ωh²
    prediction_theory: float = 0.0       # on every constraint's prediction


def contribution(ratio: float, theory: float = 0.0, z: float = 1.645) -> float:
    """q of one limit at ratio r = prediction/limit, its relative theory uncertainty profiled as a log-normal
    nuisance (module docstring; z: 1.645 one-sided)."""
    if theory < 0 or not math.isfinite(theory):
        raise ValueError("a theory uncertainty is a finite relative uncertainty δ ≥ 0")
    x = z * ratio
    kappa2 = math.log1p(theory) ** 2
    if kappa2 == 0.0 or x == 0.0:
        return x * x
    from scipy.special import lambertw
    w = float(lambertw(2.0 * kappa2 * x * x).real)
    return (2.0 * w + w * w) / (4.0 * kappa2)


def combined(ratios: dict[str, float], chi2: dict[str, float], theory: float = 0.0,
             confidence_levels: dict[str, float | None] | None = None,
             sidedness: dict[str, str] | None = None) -> float:
    """q = Σ q_i of the limits plus the measurements' Δχ² (module docstring). Without ``sidedness`` every limit
    is taken as one-sided (results saved before limits recorded it)."""
    if confidence_levels is not None and any(confidence_levels.get(name) != 0.95 for name in ratios):
        raise ValueError("The 95% combination requires a justified 95% ratio for every limit")
    if sidedness is not None and any(sidedness.get(name) not in Z_95 for name in ratios):
        raise ValueError("The 95% combination requires each limit's construction (one- or two-sided)")
    z = {name: Z_95[sidedness[name]] if sidedness is not None else 1.645 for name in ratios}
    return sum(contribution(r, theory, z[name]) for name, r in ratios.items()) + sum(chi2.values())


def combined_ratio(q: float) -> float:
    """The equivalent r_comb (= 1 at the 95% CL boundary)."""
    return math.sqrt(max(q, 0.0) / Q_95)


def relic_chi2(omega_h2: float | None, target: float, settings: LikelihoodSettings) -> float:
    """χ²_Ω of a point's relic density against the target (∞ where it is not computed)."""
    if omega_h2 is None or omega_h2 <= 0:
        return math.inf
    density = DENSITY
    sigma2 = (density.sigma * target / density.value) ** 2 + (settings.relic_theory * omega_h2) ** 2
    return (omega_h2 - target) ** 2 / sigma2

"""The tier-1 combination: the signal experiment and the null experiments together (DM6).

Every quantity is a function of the candidate's strength μ, the factor on
all its couplings (rates go as μ²):
- **The signal experiment** contributes its profile likelihood,
  q_sig(μ) = −2[ln L(s(μ)) − ln L(ŝ)] with s(μ) = μ² s₁
  (``signal_fit``).
- **A null experiment** contributes a limit-equivalent likelihood,
  q_i(μ) = 2 s₉₀ (μ/μ_up,i)² with s₉₀ = −ln 0.1 = 2.303. This is the zero-event
  Poisson likelihood scaled so that its 90% limit is the module's own
  μ_up,i. It is exact for a counting search with no events and no
  background (DEAP-3600), and the usual approximation otherwise; the
  collaborations' full likelihoods are not all public.

The joint statistic is Q(μ) = q_sig(μ) + Σ_i q_i(μ). Its minimum at μ̂_J gives:
- the joint evidence for the candidate, Z_J = √(Q(0) − Q(μ̂_J));
- the parameter-goodness-of-fit test of whether the signal and null
  experiments agree (Maltoni & Schwetz, hep-ph/0304176): each term is
  minimised separately at zero, so χ²_PG = Q(μ̂_J), with one degree of
  freedom (μ).
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import chi2
from pydantic import Field

from adroit.core.state import StrictModel
from adroit.inference import signal_fit
from adroit.inference.nuisance import BackgroundRate

S90 = -math.log(0.1)


class Combination(StrictModel):
    """The joint fit of one candidate."""

    label: str
    mu_hat_signal: float          # the signal experiment alone
    mu_hat_joint: float
    z_signal: float
    z_joint: float
    chi2_pg: float                # Q(μ̂_J): the tension between signal and null experiments
    p_pg: float
    null_limits: dict[str, float]  # μ_up of each null experiment
    note: str = "null experiments by limit-equivalent likelihoods"
    omitted_nulls: dict[str, str] = Field(default_factory=dict)
    null_coverage: Literal["complete", "partial", "none", "not_requested"] = "not_requested"
    # requested nulls that cannot constrain this candidate: no coverage gap (left out when empty)
    insensitive_nulls: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)


def signal_q(mu: float, s_one: float, f: np.ndarray, b: np.ndarray, top: float,
             rate: BackgroundRate | None = None) -> float:
    """q_sig(μ) = −2[ln L(μ² s₁) − ln L(ŝ)], with the background's θ profiled if ``rate`` is free."""
    return 2.0 * (top - float(signal_fit.profile_log_likelihood(mu * mu * s_one, f, b, rate)[0]))


def null_q(mu: float, mu_up: float) -> float:
    """The limit-equivalent term of one null experiment (0 if it has no sensitivity)."""
    return 2.0 * S90 * (mu / mu_up) ** 2 if math.isfinite(mu_up) and mu_up > 0 else 0.0


def combine(label: str, s_one: float, f: np.ndarray, b: np.ndarray,
            null_limits: dict[str, float], rate: BackgroundRate | None = None) -> Combination:
    """The joint fit, given the signal experiment's events and the null experiments' limits.

    Args:
        label: the candidate.
        s_one: its expected signal count seen inside the signal experiment's window at μ = 1
            (``signal_fit.seen_events``).
        f, b: the signal and background densities at the observed events.
        null_limits: each null experiment's upper limit on μ.
        rate: the signal experiment's background count and its uncertainty, if stated.
    """
    fit = signal_fit.fit(label, f, b, rate)
    top = float(signal_fit.profile_log_likelihood(fit.s_hat, f, b, rate)[0])
    mu_signal = math.sqrt(fit.s_hat / s_one) if s_one > 0 else 0.0

    def joint(mu: float) -> float:
        return signal_q(mu, s_one, f, b, top, rate) + sum(null_q(mu, u) for u in null_limits.values())

    upper = max(10.0 * mu_signal, 1e-12)
    best = minimize_scalar(joint, bounds=(0.0, upper), method="bounded",
                           options={"xatol": 1e-9 * upper})
    mu_joint, q_min = float(best.x), float(best.fun)
    q_zero = joint(0.0)
    if q_zero < q_min:
        mu_joint, q_min = 0.0, q_zero
    return Combination(label=label, mu_hat_signal=mu_signal, mu_hat_joint=mu_joint,
                       z_signal=fit.z_local, z_joint=math.sqrt(max(q_zero - q_min, 0.0)),
                       chi2_pg=q_min, p_pg=float(chi2.sf(q_min, 1)), null_limits=null_limits)

"""Actual event/count likelihood components for the first native joint pilot."""

from __future__ import annotations

import math

import numpy as np
from pydantic import Field, model_validator
from scipy.optimize import brentq
from scipy.special import erfcx, log_ndtr

from adroit.core.state import StrictModel


class EventData(StrictModel):
    """Observed recoil energies, nominal background and auxiliary measurement.

    The auxiliary observation is real-valued; a negative toy observation
    does not imply a negative physical background rate.
    """

    energies: list[float]
    background_at_events: list[float]
    background_total: float = Field(gt=0, allow_inf_nan=False)
    sigma_minus: float = Field(gt=0, allow_inf_nan=False)
    sigma_plus: float = Field(gt=0, allow_inf_nan=False)
    auxiliary: float = Field(default=1.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _valid(self) -> EventData:
        if len(self.energies) != len(self.background_at_events) or any(
            not math.isfinite(x) or x <= 0 for x in self.background_at_events
        ):
            raise ValueError("positive background density required at every event")
        if any(not math.isfinite(x) for x in self.energies):
            raise ValueError("finite event energies required")
        return self


class EventProfile(StrictModel):
    """Profiled event log likelihood and nonnegative background scale."""

    log_l: float
    theta: float


def event_profile(
    signal_events: float, event_densities: np.ndarray, data: EventData
) -> EventProfile:
    """Profile θ≥0 with the source bifurcated-Gaussian constraint.

    Its normalising constant is independent of θ and cancels from ratios.
    Unlike legacy toy helpers, negative auxiliary observations are allowed.
    """
    f, b = np.asarray(event_densities, float), np.asarray(data.background_at_events, float)
    if (
        not math.isfinite(signal_events)
        or signal_events < 0
        or f.shape != b.shape
        or not np.isfinite(f).all()
        or (f < 0).any()
    ):
        raise ValueError("invalid event signal prediction")

    def sigma(theta: float) -> float:
        return data.sigma_plus if theta > data.auxiliary else data.sigma_minus

    def score(theta: float) -> float:
        mean = signal_events * f + theta * b
        if (mean == 0).any():
            return math.inf
        return float(
            -data.background_total + np.sum(b / mean) - (theta - data.auxiliary) / sigma(theta) ** 2
        )

    if score(0.0) <= 0:
        theta = 0.0
    else:
        high = max(1.0, data.auxiliary + 10 * data.sigma_plus, len(f) / data.background_total + 1.0)
        for _ in range(50):
            if score(high) < 0:
                break
            high *= 2
        else:
            raise ValueError("background profile has no supported upper bracket")
        theta = brentq(score, 0.0, high, xtol=1e-12)
    mean = signal_events * f + theta * b
    value = (
        -signal_events
        - theta * data.background_total
        + np.log(mean).sum()
        - 0.5 * ((theta - data.auxiliary) / sigma(theta)) ** 2
    )
    return EventProfile(log_l=float(value), theta=float(theta))


def auxiliary_toy(theta: float, data: EventData, rng: np.random.Generator) -> float:
    """Draw a from the same normalised density used by event_profile.

    For a<θ the pull uses sigma_plus; for a>θ it uses sigma_minus.
    Side probabilities are proportional to those widths, not both one half.
    """
    if theta < 0 or not math.isfinite(theta):
        raise ValueError("physical θ must be nonnegative")
    lower = rng.random() < data.sigma_plus / (data.sigma_plus + data.sigma_minus)
    return theta + (-data.sigma_plus if lower else data.sigma_minus) * abs(rng.standard_normal())


def sample_linear_density(
    grid: np.ndarray, density: np.ndarray, count: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw exactly from the piecewise-linear background used by the likelihood."""
    x, b = np.asarray(grid, float), np.asarray(density, float)
    if (
        x.ndim != 1
        or len(x) < 2
        or x.shape != b.shape
        or not np.isfinite(x).all()
        or not np.isfinite(b).all()
        or (b < 0).any()
        or (np.diff(x) <= 0).any()
        or count < 0
    ):
        raise ValueError("invalid background grid/density/count")
    dx = np.diff(x)
    areas = 0.5 * (b[1:] + b[:-1]) * dx
    cdf = np.r_[0.0, np.cumsum(areas)]
    if cdf[-1] <= 0:
        raise ValueError("positive background support required")
    u = rng.random(count) * cdf[-1]
    i = np.clip(np.searchsorted(cdf, u, side="right") - 1, 0, len(dx) - 1)
    local = u - cdf[i]
    slope = (b[i + 1] - b[i]) / dx[i]
    denominator = b[i] + np.sqrt(np.maximum(b[i] ** 2 + 2 * slope * local, 0.0))
    offset = np.divide(2 * local, denominator, out=np.zeros_like(local), where=denominator > 0)
    return x[i] + offset


def zero_count_log_l(signal_events: float, relative_uncertainty: float) -> float:
    """DEAP's zero-count Poisson likelihood with its native C-H sensitivity.

    Average exp(-s ε) over exactly the positive eight-sigma Gaussian window
    of poisson.cousins_highland_limit. The closed integral avoids interpolation
    and remains stable when the expected count is large.
    """
    s, d = signal_events, relative_uncertainty
    if not math.isfinite(s) or not math.isfinite(d) or s < 0 or d < 0:
        raise ValueError("finite nonnegative count and sensitivity uncertainty required")
    if s == 0:
        return 0.0
    if d == 0:
        return -s
    low = max(0.0, 1 - 8 * d)
    z0 = (low - 1) / d
    zlow = z0 + d * s
    zhigh = 8 + d * s
    width = 8 - z0
    log_ratio = (
        -width * zlow
        - 0.5 * width * width
        + math.log(float(erfcx(zhigh / math.sqrt(2))))
        - math.log(float(erfcx(zlow / math.sqrt(2))))
    )
    difference = math.log1p(-math.exp(log_ratio))
    norm = float(log_ndtr(-z0)) + math.log1p(-math.exp(float(log_ndtr(-8)) - float(log_ndtr(-z0))))
    return float(
        -low * s
        - 0.5 * z0 * z0
        + math.log(float(erfcx(zlow / math.sqrt(2))))
        - math.log(2)
        + difference
        - norm
    )


def binned_free_background_log_l(observed: list[int], expected: list[float]) -> float:
    """PICO's exact counting likelihood, relative to its profiled null maximum.

    Each independent background is free and nonnegative, b_hat=max(0,n-s).
    The observation-dependent constant cancels within every toy likelihood ratio.
    """
    from adroit.statistics.poisson import free_background_statistic

    n, s = np.asarray(observed, float), np.asarray(expected, float)
    if (
        n.ndim != 1
        or not len(n)
        or n.shape != s.shape
        or not np.isfinite(n).all()
        or not np.isfinite(s).all()
        or (n < 0).any()
        or (n != np.floor(n)).any()
        or (s < 0).any()
    ):
        raise ValueError("nonnegative integer observations and matched finite predictions required")
    return -0.5 * float(free_background_statistic(n, s, 1.0))

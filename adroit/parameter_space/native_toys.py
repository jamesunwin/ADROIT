"""Exact native PICO discovery maxima and typed background-only observations.

For this pure-SI pair the profiled log likelihood is concave in the shared
rate factor t=(g_chi/g_ref)^2. The two endpoints and its monotone score root
give the same bounded maximum without constructing unused toy LR regions.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from pydantic import Field
from scipy.optimize import brentq

from adroit.core.state import StrictModel
from adroit.inference.signal_fit import event_densities
from adroit.statistics.native_pair import (
    EventData,
    event_profile,
    auxiliary_toy,
    sample_linear_density,
    binned_free_background_log_l,
)

if TYPE_CHECKING:
    from adroit.parameter_space.native_joint import PairTemplate
    from adroit.parameter_space.physical_fit import FitSettings
    from adroit.experiments.historical import HistoricalSearch


class NativeObservation(StrictModel):
    """One silicon event/auxiliary dataset and the PICO exposure counts."""

    signal: EventData
    null_counts: list[int] = Field(default_factory=list)


class NativeMaximum(StrictModel):
    """Bounded discovery maximum; no interval-coverage claim is attached."""

    factor: float
    q0: float
    log_l: float
    evaluations: int


def draw_background(
    data: EventData,
    signal: HistoricalSearch,
    theta: float,
    null_backgrounds: list[float],
    rng: np.random.Generator,
) -> NativeObservation:
    """Generate all observations at specified true nuisances using the fitted likelihood model."""
    if (
        not math.isfinite(theta)
        or theta < 0
        or any(not math.isfinite(x) or x < 0 for x in null_backgrounds)
    ):
        raise ValueError("finite nonnegative true background nuisances required")
    count = int(rng.poisson(theta * data.background_total))
    energies = sample_linear_density(
        signal.signal_grid_kev(), signal.background_on_grid(), count, rng
    )
    toy = data.model_copy(
        update={
            "energies": energies.tolist(),
            "background_at_events": signal.background_at(energies).tolist(),
            "auxiliary": auxiliary_toy(theta, data, rng),
        }
    )
    return NativeObservation(signal=toy, null_counts=rng.poisson(null_backgrounds).tolist())


def pico_maximum(
    template: PairTemplate, observation: NativeObservation, settings: FitSettings
) -> NativeMaximum:
    """Find the exact concave shared-rate maximum, with a hard evaluation cap."""
    if template.null_experiment != "PICO-60 C3F8 (2019)":
        raise ValueError("concavity shortcut is only proved for the PICO counting pair")
    data, n = observation.signal, np.array(observation.null_counts)
    nu = np.array(template.null_counts)
    binned_free_background_log_l(observation.null_counts, template.null_counts)
    f = event_densities(
        np.array(template.signal_grid),
        np.array(template.signal_density),
        np.array(data.energies),
        template.resolution_kev,
    )
    total = template.signal_count + float(nu.sum())
    if not math.isfinite(total) or total <= 0 or template.signal_count <= 0:
        raise ValueError("positive finite physical reference signal required")
    si_weight, nu = template.signal_count / total, nu / total
    sf, b = si_weight * f, np.array(data.background_at_events)
    cache = {}
    evaluations = 0

    def at(t: float) -> tuple[float, float]:
        nonlocal evaluations
        if t not in cache:
            if evaluations >= settings.max_evaluations:
                raise ValueError("native discovery maximum evaluation budget exhausted")
            evaluations += 1
            profile = event_profile(si_weight * t, f, data)
            mean = t * sf + profile.theta * b
            slope = -si_weight + float(np.sum(sf / mean))
            active = (t * nu > n) | (n == 0)
            slope += float(np.sum(-nu[active] + (n[active] / t if t > 0 else 0)))
            value = profile.log_l + binned_free_background_log_l(n.tolist(), (t * nu).tolist())
            cache[t] = value, slope
        return cache[t]

    # Work in total predicted events, not a potentially microscopic fraction
    # of an enormous reference count. Profiled score <= -1 + N_total/t,
    # so no maximum can lie above the total observed event count.
    upper = min(total, float(len(data.energies) + n.sum()))
    lower = at(0.0)
    if lower[1] <= 0:
        best = 0.0
    elif at(upper)[1] >= 0:
        best = upper
    else:
        best = float(brentq(lambda t: at(t)[1], 0.0, upper, xtol=1e-14, rtol=1e-12))
    value = at(best)[0]
    return NativeMaximum(
        factor=best / total,
        q0=max(0.0, 2 * (value - lower[0])),
        log_l=value,
        evaluations=evaluations,
    )

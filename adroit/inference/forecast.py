"""The forecast: which target would separate the leading candidates, and with how many events (DM6).

Two candidates that both explain a signal in one experiment can differ
elsewhere in two ways, and the forecast measures both for each target:
- **The shape of the recoil spectrum.** N_shape = 4/J is the number of events
  on that target needed to tell the two apart at 2σ from their spectra
  (``degeneracy``), each weighted by a flat efficiency over the window.
- **The rate.** With both candidates normalised to the signal they explain in
  the signal experiment, the target sees n events under the candidate that
  predicts more and rn under the other, r ≤ 1. Telling them apart at 2σ
  from the count alone takes n_rate = 4/(1 − r)² events (Poisson), counted
  under the candidate that predicts more. Here r = min(ρ, 1/ρ), and ρ is the
  ratio of rate ratios, [R_B(T)/R_B(S)] / [R_A(T)/R_A(S)], for the target T
  and the signal experiment's target S.

For each pair the forecast reports the target and route that need the fewest
events. This is an estimate for planning, not a detector simulation: it
assumes no background and perfect energy resolution.
"""

from __future__ import annotations

import math

import numpy as np

from adroit.core.dm_state import DarkMatterParticle, HaloModel, InteractionModel, NuclearModel
from adroit.core.state import StrictModel
from adroit.library.interactions import degeneracy
from adroit.physics import rates, targets

TARGETS = ("Xe", "Ar", "Ge", "CaWO4", "C3F8", "NaI")
ENERGIES_KEV = np.linspace(1.0, 400.0, 800)


class Separation(StrictModel):
    """How to tell two candidates apart."""

    a: str
    b: str
    best_target: str
    route: str                       # "spectrum" or "rate"
    events_needed: float
    by_target: dict[str, tuple[float, float]]   # target → (N_shape, n_rate)


def target_spectrum(particle: DarkMatterParticle, interaction: InteractionModel, target: str,
                    halo: HaloModel, model: NuclearModel) -> tuple[np.ndarray, float]:
    """(normalised spectrum, total rate per kg per day) on the forecast window."""
    rate = np.asarray(rates.differential_rate(ENERGIES_KEV, particle, interaction,
                                              targets.target(target), halo, model).rate)
    total = float(np.trapezoid(rate, ENERGIES_KEV))
    return (rate / total if total > 0 else rate), total


def separate(label_a: str, a: tuple[DarkMatterParticle, InteractionModel],
             label_b: str, b: tuple[DarkMatterParticle, InteractionModel], signal_target: str,
             halo: HaloModel | None = None,
             model: NuclearModel = NuclearModel.haxton_2022) -> Separation:
    """The fewest events, on any target, that would separate a from b at 2σ."""
    halo = halo or HaloModel()
    spectra = {t: (target_spectrum(*a, t, halo, model), target_spectrum(*b, t, halo, model))
               for t in {*TARGETS, signal_target}}
    (_, ra_s), (_, rb_s) = spectra[signal_target]
    by_target = {}
    for t in TARGETS:
        (sa, ra), (sb, rb) = spectra[t]
        if ra_s <= 0 or rb_s <= 0 or (ra <= 0 and rb <= 0):     # no normalisation, or nothing on this target
            by_target[t] = (math.inf, math.inf)
            continue
        if ra <= 0 or rb <= 0:          # one predicts events here, the other none: the rate separates them, r = 0, N = 4
            by_target[t] = (math.inf, 4.0)   # (the limit of the rule below; the independent audit, NA15-09: ∞ had
            continue                         # been stored, and a less discriminating target recommended)
        j = degeneracy.jeffreys_matrix(np.array([sa, sb]), ENERGIES_KEV)[0, 1]
        rho = (rb / rb_s) / (ra / ra_s)
        r = min(rho, 1.0 / rho)
        n_rate = 4.0 / (1.0 - r) ** 2 if r < 1.0 else math.inf
        by_target[t] = (float(degeneracy.events_to_separate(j)), n_rate)
    options = [(n, t, route) for t, pair in by_target.items()
               for n, route in zip(pair, ("spectrum", "rate"))]
    n, t, route = min(options)
    return Separation(a=label_a, b=label_b, best_target=t, route=route, events_needed=n,
                      by_target=by_target)

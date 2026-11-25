"""Bounds for annihilation into a mixture of channels, from limits published channel by channel: an approximation.

A search that publishes the limit L_j on ⟨σv⟩ for annihilation entirely into channel j sees a mixture only
through the spectrum of its messenger, s = Σ_i ⟨σv⟩_i s_i, with s_i the yield per annihilation into i. The rule
below would be exact for a search whose statistic had these two properties:

- **convexity:** −2 ln L is convex in the expected counts (Poisson), so the allowed spectra form a convex set
  that contains s = 0. Each s_j L_j lies on its boundary, so a spectrum Σ_j r_j (s_j L_j) with Σ_j r_j ≤ 1 is
  a convex combination of allowed spectra and is itself allowed;
- **monotonicity:** more signal in any bin never makes a spectrum less excluded.

For a channel with its own curve, r_i = ⟨σv⟩_i / L_i exactly. A channel without one is bounded by a proxy
curve p and a factor c with s_i ≤ c s_p in every bin of the search; by monotonicity r_i ≤ c ⟨σv⟩_i / L_p.
Then, with r_i or its bound for every channel,

    upper = Σ_i r_i ≤ 1          ⇒ the mixture is allowed;
    lower = max_own r_j > 1      ⇒ it is excluded (its spectrum exceeds ⟨σv⟩_j s_j, already excluded);

and otherwise the search cannot decide. A channel with no curve, no proxy and no reason to give no signal
leaves the upper bound undefined. The rules for each search (``data/mixture_rules.yaml``) state every proxy,
factor and reason; for photons the factor is computed from PPPC yields (``photon_dominance``).

**Neither property is general.** Each published curve is set against the data's own best fit for that channel, not
one reference for every spectrum, and where the data fluctuate up in a bin, signal there can improve the fit: "no
significant excess" does not make the statistic monotone. The auditor's counterexample (its independent audit, NA15-07,
2026-11-16): two Poisson bins, backgrounds 10 and 10, observed 10 and 12, each channel in its own bin; channel A at
1.01 times its own limit is excluded alone (q = 2.752 against 2.706), yet with channel B added in the other bin the
mixture's q is 2.415, allowed, though its fitted excess is only 0.2σ. The searches' joint likelihoods are not
published, so ADROIT uses the rule as an approximation of them: good where the data show no upward fluctuation
where the channels put their signal, and able to err either way for a mixture near a limit. Every decision it
makes says so (``MixtureBound.why``).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from adroit.core.state import StrictModel

RULES = Path(__file__).with_name("data") / "mixture_rules.yaml"

# The ratio per unit ⟨σv⟩ of annihilation entirely into a curve's channel: r_i = per_rate(curve) · ⟨σv⟩_i.
# None when the curve does not cover the mass.
PerRate = Callable[[str], float | None]
# The factor c with s_channel ≤ c s_curve bin by bin (∞ when there is none).
Dominance = Callable[[str, str], float]


@lru_cache(maxsize=1)
def rules() -> dict:
    """Every search's mixture rule."""
    return yaml.safe_load(RULES.read_text())


def rule(record_id: str) -> dict:
    """One search's mixture rule."""
    return rules()[record_id]


class Term(StrictModel):
    """One channel's share of the mixture and its ratio to the search's limit (or an upper bound on it)."""

    channel: str
    fraction: float
    ratio: float | None = None
    how: str
    own: bool = False


APPROXIMATION = ("by the mixture rule, an approximation of the search's joint likelihood that can err either way near "
                 "a limit (constraints.mixtures)")


class MixtureBound(StrictModel):
    """The mixture's bounds: allowed if ``upper`` ≤ 1, excluded if ``lower`` > 1 (an approximation: module
    docstring)."""

    record_id: str
    upper: float | None
    lower: float
    terms: list[Term]

    @property
    def excluded(self) -> bool | None:
        """True, False, or None when the bounds straddle 1."""
        if self.lower > 1.0:
            return True
        return False if self.upper is not None and self.upper <= 1.0 else None

    @property
    def ratio(self) -> float | None:
        """The ratio a combination may take, when the bounds decide: the lower bound, a lower bound on the search's own
        ratio, so a combined likelihood never excludes on more than the mixture shows (the audit loop's AL4-07,
        2026-11-16: an allowed mixture's upper bound had entered the combination as its ratio, and excluded a point
        the lower bound left allowed); None when the bounds straddle 1. ``why`` states both bounds."""
        return None if self.excluded is None else self.lower

    def why(self) -> str:
        """The decision in words, naming the channels that set it."""
        parts = ", ".join(f"{t.channel} {t.fraction:.3g}: {t.how}" for t in self.terms)
        if self.excluded:
            return f"one channel alone exceeds its own curve (largest ratio {self.lower:.3g}), {APPROXIMATION} [{parts}]"
        if self.excluded is False:
            return f"mixture bound: Σ ratios ≤ {self.upper:.3g} ≤ 1, {APPROXIMATION} [{parts}]"
        if self.upper is None:
            missing = [t.channel for t in self.terms if t.ratio is None]
            return f"no mixture bound for {', '.join(missing)} [{parts}]"
        return (f"the mixture bound Σ = {self.upper:.3g} exceeds 1 while no channel with its own curve does "
                f"(largest {self.lower:.3g}) [{parts}]")


def bound(record_id: str, rates: dict[str, float], mass: float, per_rate: PerRate,
          dominance: Dominance | None = None) -> MixtureBound:
    """The mixture rule of one search at one mass.

    Args:
        record_id: the search's record (a key of ``data/mixture_rules.yaml``).
        rates: ⟨σv⟩ per channel, any common unit.
        mass: the dark-matter mass in GeV (for mass-dependent rules).
        per_rate: the ratio per unit rate of each published curve at this mass.
        dominance: the computed proxy factor, for rules that use ``by: dominance``.
    """
    spec = rule(record_id)
    # a rate that is not a finite number is never dropped (the audit loop's AL4-11: {"b": nan, "tau": 1e-30} had read
    # "allowed" on the τ alone): its channel is a term with no ratio, so the mixture is undecided and names it
    finite = {channel: rate for channel, rate in rates.items() if math.isfinite(rate)}
    unknown = [Term(channel=channel, fraction=0.0, how=f"its rate is not a finite number ({rate})")
               for channel, rate in rates.items() if channel not in finite]
    total = sum(v for v in finite.values() if v > 0)
    terms = [_term(spec, channel, rate, rate / total, mass, per_rate, dominance)
             for channel, rate in sorted(finite.items(), key=lambda kv: -kv[1]) if rate > 0] if total > 0 else []
    terms += unknown
    ratios = [t.ratio for t in terms]
    upper = None if any(r is None for r in ratios) else float(sum(ratios))
    lower = max((t.ratio for t in terms if t.own), default=0.0)
    return MixtureBound(record_id=record_id, upper=upper, lower=lower, terms=terms)


def _term(spec: dict, channel: str, rate: float, fraction: float, mass: float, per_rate: PerRate,
          dominance: Dominance | None) -> Term:
    curve = spec.get("own", {}).get(channel)
    k = per_rate(curve) if curve else None
    entries = spec.get("bounded", []) + ([{**spec["default"], "channels": [channel]}] if "default" in spec else [])
    if k is not None:
        return Term(channel=channel, fraction=fraction, ratio=k * rate, how=f"own curve {curve}", own=True)
    none = spec.get("none")
    if none and channel in none["channels"] and mass < none.get("below_gev", math.inf):
        return Term(channel=channel, fraction=fraction, ratio=0.0, how="no signal")
    for entry in entries:
        if channel in entry["channels"]:
            k, how = _proxy(spec, entry, channel, per_rate, dominance)
            return Term(channel=channel, fraction=fraction, ratio=None if k is None else k * rate, how=how)
    return Term(channel=channel, fraction=fraction, how="no curve, proxy or reason for no signal")


def _proxy(spec: dict, entry: dict, channel: str, per_rate: PerRate,
           dominance: Dominance | None) -> tuple[float | None, str]:
    """(ratio per unit rate, description) of a channel bounded by a proxy."""
    curves = sorted(set(spec.get("own", {}).values()))
    if entry["by"] == "dominance":
        if dominance is None:
            return None, "a computed proxy, not available here"
        found = [(c * k, curve, c) for curve in curves
                 if (k := per_rate(curve)) is not None and math.isfinite(c := dominance(channel, curve))]
        if not found:
            return None, "no published curve dominates it at this mass"
        k, curve, c = min(found)
        return k, f"≤ {c:.3g} × {curve} (PPPC dominance)"
    if isinstance(entry["by"], dict):                       # a weighted sum of curves: s_i ≤ Σ_c w_c s_c
        parts = [(w, curve, per_rate(curve)) for curve, w in entry["by"].items()]
        if any(k is None for _, _, k in parts):
            return None, "a proxy curve does not cover this mass"
        return sum(w * k for w, _, k in parts), "≤ " + " + ".join(f"{w:g} × {c}" for w, c, _ in parts)
    factor = float(entry.get("factor", 1.0))
    if entry["by"] == "strongest":
        found = [(k, curve) for curve in entry.get("among", curves) if (k := per_rate(curve)) is not None]
        if not found:
            return None, "no published curve at this mass"
        k, curve = max(found)
        return factor * k, f"≤ {factor:g} × the strongest curve ({curve})"
    k = per_rate(entry["by"])
    if k is None:
        return None, f"{entry['by']} does not cover this mass"
    return factor * k, f"≤ {factor:g} × {entry['by']}"


def photon_dominance(record_id: str, mass: float) -> Dominance:
    """The computed proxy factor for a photon search's ``by: dominance`` rule at one mass: the largest ratio,
    over the analysis's energy bins, of the channel's PPPC photons to the proxy curve's (∞ if the proxy has
    none in a bin where the channel does, or the spectra are unavailable)."""
    spec = rule(record_id)
    bins = next(e["bins"] for e in spec["bounded"] + [spec.get("default", {})] if e.get("by") == "dominance")
    channel_of = {}
    for channel, curve in spec["own"].items():
        channel_of.setdefault(curve, channel)
    return lambda channel, curve: _dominance(channel, channel_of[curve], mass, bins["low_gev"], bins["high_gev"],
                                             bins["count"])


def energy_budget(mass: float, edges: np.ndarray) -> np.ndarray:
    """The most photons any annihilation can put in each bin: its whole energy 2m_χ, in photons of the bin's lowest
    energy (none above m_χ, the most one photon can carry)."""
    low = np.asarray(edges[:-1], float)
    return np.where(low < mass, 2 * mass / low, 0.0)


@lru_cache(maxsize=8192)
def _dominance(channel: str, proxy: str, mass: float, low: float, high: float, count: int) -> float:
    """The largest bin ratio of the channel's photons to the proxy's; a channel without a PPPC spectrum (a cascade,
    an unknown state) is bounded by the energy budget."""
    from adroit.constraints import spectra
    edges = np.geomspace(low, high, count + 1)
    try:
        data = spectra.table()
        theirs = spectra.binned(mass, proxy, edges, data)
    except spectra.SpectrumUnavailable:
        return math.inf
    try:
        mine = spectra.binned(mass, channel, edges, data)
    except spectra.SpectrumUnavailable:
        mine = energy_budget(mass, edges)
    seen = mine > 0
    if not seen.any():
        return 0.0
    if (theirs[seen] <= 0).any():
        return math.inf
    return float(np.max(mine[seen] / theirs[seen]))

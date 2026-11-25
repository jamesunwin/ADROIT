"""Applicability of published pure-final-state indirect limits."""
from __future__ import annotations

import math
from typing import Any

from adroit.core.state import StrictModel
from adroit.constraints.dwarf_likelihood import SpectralLimit, RECORD

from adroit.constraints.database import interpolate_limit
from adroit.constraints.mixtures import MixtureBound

FERMI_CHANNELS = {"u": "uu", "b": "bb", "e": "ee", "mu": "mumu", "tau": "tautau", "W": "WW"}
THRESHOLDS = {"u": 0.0022, "d": 0.0047, "s": 0.096, "c": 1.27, "b": 4.18,
              "e": 0.000511, "mu": 0.105658, "tau": 1.77686, "W": 80.379, "hh": 125.09}


class SpectralComparison(StrictModel):
    """A gated spectral recast, or the specific missing input preventing it."""

    ratio: float | None = None
    limit: SpectralLimit | None = None
    why: str = ""
    record_id: str = RECORD


def spectral_comparison(channels: dict[str, float], mass: float, self_conjugate: bool,
                        include_unverified: bool = False, cls: Any = None,
                        point: Any = None) -> SpectralComparison:
    """Use the separate 2024 likelihood only when authorised by the record gate.

    Callers must first try the existing pure-channel comparison: overlapping
    2015 and 2024 data must never enter a combination twice.
    """
    from adroit.constraints import database, spectra, dwarf_likelihood
    from adroit.constraints.searches import admits
    if not admits(database.record(RECORD), include_unverified):
        return SpectralComparison(why="mixed/cascade 2024 dwarf spectral recast awaits a person's verification")
    try:
        request = spectra.from_rates(mass, channels, cls, point)
        result = dwarf_likelihood.upper_limit(spectra.spectrum(request),
                                             self_conjugate=self_conjugate)
    except (spectra.SpectrumUnavailable, OSError) as error:
        return SpectralComparison(why=str(error))
    return SpectralComparison(ratio=sum(channels.values()) / result.upper95_cm3_s, limit=result)


def pure_ratio(channels: dict[str, float], mass: float, curves: dict,
               mapping: dict[str, str], self_conjugate: bool) -> float | None:
    """Use a curve only for its actual pure prompt spectrum, above threshold.

    Mixtures need a spectral likelihood. A cascade's spectrum is not determined
    by its parent spin or by a nearest Standard Model final state.
    """
    if any(not math.isfinite(v) or v < 0 for v in channels.values()):
        return None
    active = [(k, v) for k, v in channels.items() if v > 0]
    if not active:
        return 0.0
    if len(active) != 1:
        return None
    name, rate = active[0]
    if name not in mapping or mass < THRESHOLDS.get(name, math.inf):
        return None
    curve = curves.get(mapping[name])
    if curve is None:
        return None
    limit = interpolate_limit(curve, mass)
    return None if limit is None else (1 if self_conjugate else 0.5) * rate / limit


FERMI_2015 = "fermi-1503.02641-dsph"


def fermi_mixture(channels: dict[str, float], mass: float, curves: dict, self_conjugate: bool) -> MixtureBound:
    """Fermi-LAT's 2015 dwarf curves applied to a channel mixture by the conservative rule
    (``constraints.mixtures``); a channel the paper did not publish is bounded by the published channel whose
    PPPC photons dominate it in every bin of the analysis.

    Args:
        channels: ⟨σv⟩ per channel today, in cm³/s.
        mass: the dark-matter mass in GeV.
        curves: the record's curves, channel name to [[m, ⟨σv⟩], ...] (self-conjugate dark matter).
        self_conjugate: whether the dark matter is its own antiparticle (else ⟨σv⟩ is compared × 1/2).
    """
    from adroit.constraints import mixtures
    scale = 1.0 if self_conjugate else 0.5

    def per_rate(curve: str) -> float | None:
        limit = interpolate_limit(curves[curve], mass) if curve in curves else None
        return scale / limit if limit else None

    return mixtures.bound(FERMI_2015, channels, mass, per_rate, mixtures.photon_dominance(FERMI_2015, mass))

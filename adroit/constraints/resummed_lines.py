"""Resummed γ-ray line rates of a pure wino or higgsino (G8), from DMγSpec's tables.

DMγSpec (Beneke, Urban & Vollmann, arXiv:2203.01692) gives the photon spectrum of wino and higgsino annihilation with
the endpoint Sudakov-resummed at NLL′ and the Sommerfeld effect from the NLO electroweak potentials. It is GPLv3
software that the user installs in the tools folder; ADROIT never imports it. ``scripts/build_dmyspec_lines.py`` runs
it once, in its own environment, and writes ``<tools>/dmyspec/adroit_lines.json``, which this module reads.

**The rate.** At DMγSpec's 500 masses from 0.5 to 100 TeV, the γγ-equivalent rate in the H.E.S.S. window x = E/M ∈
[0.9, 1] (``searches.HESS_LINE_RESOLUTION``):

    σv_line = ½ ∫ d(σv)/dx dx over the window,

counting 2 photons per γγ and 1 per Zγ, plus the resummed endpoint continuum. It is taken at the single-particle speed
10⁻³ (DMγSpec's 'NLO -3' tables), and for the higgsino with a neutral splitting of 20 MeV. Between grid masses it is
interpolated linearly in (M, ln σv). The grid resolves the Sommerfeld resonances, with steps of 5–20 GeV below 4 TeV.

Outside 0.5–100 TeV, or without the table, there is no value (None): the caller keeps its own rate, an upper bound.

**Above 13 TeV** DMγSpec's own tree-level line drifts by 20% against its Sommerfeld table between 13 and 18 TeV
(G8: ADROIT's resummation with DMγSpec's Sommerfeld factors is 20–25% below DMγSpec's rate there), so the rate
carries a ±25% theory band (``theory_band``; decision D30, G12, the owner's point 2), which the line search applies.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

from adroit.core.config import get_settings

MODELS = ("wino", "higgsino")


def path() -> Path:
    """The table ``scripts/build_dmyspec_lines.py`` writes."""
    return get_settings().tools_dir / "dmyspec" / "adroit_lines.json"


def available() -> bool:
    """Whether the table is in the tools folder."""
    return path().is_file()


def _tables() -> dict:
    """The table as it is now (``file_reads.stamp``: a rebuilt table is read again, BI-02)."""
    from adroit.core.file_reads import stamp
    return _read(*stamp(path()))


@lru_cache(maxsize=2)
def _read(where: str, size: int, mtime: int, ctime: int) -> dict:
    return json.loads(Path(where).read_text())["tables"]


DRIFT_GEV = 13000.0
DRIFT_BAND = 0.25


def theory_band(m_gev: float) -> tuple[float, float, str]:
    """(low, high, why): the factors bracketing ``line_sigma_v``'s rate (module docstring): ±25% above 13 TeV."""
    if m_gev <= DRIFT_GEV:
        return 1.0, 1.0, ""
    return 1.0 - DRIFT_BAND, 1.0 + DRIFT_BAND, "DMγSpec above 13 TeV, where its tree line drifts 20% against its " \
                                                "Sommerfeld table: ±25%"


def line_sigma_v(model: str, m_gev: float) -> float | None:
    """σv_line (cm³/s) of a pure ``model`` ("wino" or "higgsino") at mass ``m_gev``, or None (module docstring)."""
    if model not in MODELS or not available():
        return None
    rows = np.array(_tables()[model]["data"], dtype=float)
    masses, rates = rows[:, 0], rows[:, 2]
    if not masses[0] <= m_gev <= masses[-1] or not np.all(rates > 0):
        return None
    return float(math.exp(np.interp(m_gev, masses, np.log(rates))))

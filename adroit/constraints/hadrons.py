"""Hadronic final states below 2 GeV: the measured R ratio, in place of free quarks.

Below √s ≈ 2 GeV a vector's coupling to quarks makes hadrons through the ρ, ω and φ
resonances, not free u, d, s quarks. A vector mediator's annihilation into hadrons is

    σ(χχ̄ → V* → hadrons)(s) = σ(χχ̄ → V* → μ⁺μ⁻)(s) × R_V(√s),

with R_V the ratio of the vector's hadronic and muonic widths at mass √s:
- **photon-like couplings** (a dark photon, ε e Q_q; L_μ − L_τ's loop-induced mixing): the
  measured R = σ(e⁺e⁻ → hadrons)/σ(e⁺e⁻ → μ⁺μ⁻) with massless muons, the PDG's compilation
  of exclusive channels from 0.30 to 1.99 GeV (R. L. Workman et al., PTEP 2022, 083C01;
  COMPAS, hep-ph/0312114), fetched into the tools folder;
- **baryon-number couplings** (B − L, isoscalar: no ρ): DarkCast's vector-meson-dominance
  widths (Ilten et al. arXiv:1801.04847), from the tools folder.

Above 2 GeV the portals keep free quarks (R → N_c Σ Q_q² (1 + α_s/π)); at 2 GeV the two agree
to ≈1% (2.18 measured against 2.2).
"""

from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

LIGHT_GEV = 2.0                   # below: hadrons from R; above: free quarks
R_LOWEST_GEV = 0.30               # the compilation's first point (R ≈ 0.02 there; zero below)


def _pdg_table() -> tuple[np.ndarray, np.ndarray] | None:
    """The PDG's sum of exclusive channels (ShortCode 'EXCLSUM'): √s (GeV) and R; the file as it is now
    (``file_reads.stamp``: a replaced table is read again, BI-02)."""
    from adroit.constraints.searches import _tool
    from adroit.core.file_reads import stamp
    folder = _tool("PDG R ratio")
    if folder is None:
        return None
    return _pdg_rows(*stamp(folder / "rpp2022-hadronicrpp_page1001.dat"))


@lru_cache(maxsize=4)
def _pdg_rows(path: str, size: int, mtime: int, ctime: int) -> tuple[np.ndarray, np.ndarray]:
    energies, ratios = [], []
    for line in Path(path).read_text().splitlines():
        if line.startswith("*") or "EXCLSUM" not in line:
            continue
        fields = line.split()
        energies.append(float(fields[0]))
        ratios.append(float(fields[3]))
    order = np.argsort(energies)
    return np.array(energies)[order], np.array(ratios)[order]


def available() -> bool:
    """Whether the PDG's R-ratio table is in the tools folder."""
    return _pdg_table() is not None


def r_ratio(root_s: np.ndarray) -> np.ndarray:
    """The measured R at √s (GeV), interpolated; 0 below 0.30 GeV; for √s < 2 GeV only.

    Raises:
        FileNotFoundError: if the PDG's file is not in the tools folder (adroit setup --fetch).
    """
    table = _pdg_table()
    if table is None:
        raise FileNotFoundError("the PDG's R-ratio file is not in the tools folder (adroit setup --fetch)")
    energies, ratios = table
    root_s = np.asarray(root_s, dtype=float)
    return np.where(root_s < energies[0], 0.0, np.interp(root_s, energies, ratios))


@lru_cache(maxsize=4)
def _darkcast_model(name: str):
    from adroit.constraints.searches import _tool
    folder = _tool("DarkCast")
    if folder is None:
        raise FileNotFoundError("DarkCast is not in the tools folder (adroit setup --fetch)")
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    import darkcast
    return darkcast.Model(name)


@lru_cache(maxsize=4096)
def _darkcast_ratio(name: str, m: float) -> float:
    model = _darkcast_model(name)
    muons = model.width("mu_mu", m)
    return model.width("hadrons", m) / muons if muons > 0 else 0.0


def baryonic_ratio(root_s: np.ndarray) -> np.ndarray:
    """Γ(V → hadrons)/Γ(V → μ⁺μ⁻) at mass √s for a B − L vector (DarkCast); 0 below 2m_μ."""
    root_s = np.atleast_1d(np.asarray(root_s, dtype=float))
    grid = np.round(root_s, 4)                       # cached on a 0.1 MeV grid
    return np.array([_darkcast_ratio("B-L_boson", float(m)) if m > 2 * 0.10566 else 0.0 for m in grid])


def muon_width(m: float, coupling: float, massless: bool = False) -> float:
    """Γ(V → μ⁺μ⁻) of a vector coupling to muons with g (vector), massless as the R ratio is defined if asked."""
    m_mu = 0.0 if massless else 0.10566
    if m <= 2 * m_mu:
        return 0.0
    r = (m_mu / m) ** 2
    return coupling ** 2 * m / (12.0 * math.pi) * (1.0 + 2.0 * r) * math.sqrt(1.0 - 4.0 * r)

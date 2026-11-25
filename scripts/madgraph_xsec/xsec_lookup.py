"""Read the JSON tables, interpolate in mass, rescale by couplings/K and emit SLHA XSECTION blocks.

Interpolation: cubic spline in (ln M, ln sigma) by default (midpoint error <~0.5 % on the 25-point
grids, except within ~30 GeV of the t tbar threshold of the spin-0 tables, which is densely sampled
from 300 to 420 GeV); method="linear" gives log-log linear interpolation (up to ~6 % at 5-6 TeV for
the Z' grid and ~3 % above 1 TeV for spin-0).

Examples
--------
>>> from xsec_lookup import Table, xsection_block
>>> zp = Table("zprime_spin1_vector_13TeV_LO.json")
>>> s = zp(1500.0) * 0.25**2 * 1.3          # g_q = 0.25 universal vector, K = 1.3
>>> print(xsection_block(s, (5000001,), order_qcd=0, comment="Z' g_q=0.25, LO x K"))
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

OUT_DIR = Path.home() / "agentic-dm-tools/madgraph-xsec"


class Table:
    """sigma(M) from a one-mass-parameter JSON table (Z', spin-0, equal-mass inert doublet)."""

    def __init__(self, filename: str, mass_col: int = 0, sigma_col: int | None = None,
                 method: str = "cubic"):
        doc = json.loads((OUT_DIR / filename).read_text())
        cols = doc["columns"]
        sc = cols.index("sigma_pb") if sigma_col is None else sigma_col
        rows = sorted(doc["data"], key=lambda r: r[mass_col])
        self.meta = {k: v for k, v in doc.items() if k != "data"}
        self.m = np.array([float(r[mass_col]) for r in rows])
        self.s = np.array([float(r[sc]) for r in rows])
        self.method = method
        if method == "cubic":
            from scipy.interpolate import CubicSpline
            self._spl = CubicSpline(np.log(self.m), np.log(self.s))

    def __call__(self, mass: float) -> float:
        """Interpolated sigma in pb (raises outside the tabulated range)."""
        if not self.m[0] <= mass <= self.m[-1]:
            raise ValueError(f"mass {mass} outside table range {self.m[0]}-{self.m[-1]} GeV")
        if self.method == "cubic":
            return float(math.exp(self._spl(math.log(mass))))
        return float(math.exp(np.interp(math.log(mass), np.log(self.m), np.log(self.s))))


def spin0_sigma(mass: float, gt: float, gb: float, cp: str = "S") -> float:
    """LO sigma(gg -> S) for Yukawa multipliers (g_t, g_b), cp = 'S' (CP-even) or 'P' (CP-odd)."""
    st = Table(f"ggS_spin0_{cp}_t_13TeV_LO.json")(mass)
    sb = Table(f"ggS_spin0_{cp}_b_13TeV_LO.json")(mass)
    stb = Table(f"ggS_spin0_{cp}_tb_13TeV_LO.json")(mass)
    return gt * gt * st + gb * gb * sb + gt * gb * (stb - st - sb)


def zprime_sigma(mass: float, g2: dict[str, float]) -> float:
    """LO sigma(pp -> Z') for g2 = {'u': gVu^2 + gAu^2, 'd': ..., 's': ..., 'c': ..., 'b': ...}."""
    return sum(v * Table(f"zprime_spin1_{q}_13TeV_LO.json")(mass) for q, v in g2.items() if v)


def xsection_block(sigma_pb: float, final_pdgs: tuple[int, ...], sqrts_gev: float = 13000.0,
                   order_qcd: int = 0, code: str = "MG5_aMC@NLO-3.8.0", comment: str = "") -> str:
    """SLHA XSECTION block (format read by SModelS / pyslha).

    Line 2 integers: scale scheme, PDF set, QCD order (0 = LO, 1 = NLO, 2 = NLO+NLL), EW order,
    kappa_f, kappa_r (0 = central values).
    """
    head = f"XSECTION  {sqrts_gev:.2E}  2212 2212 {len(final_pdgs)} " + " ".join(str(p) for p in final_pdgs)
    if comment:
        head += f"  # {comment}"
    return head + f"\n  0  0  {order_qcd}  0  0  0    {sigma_pb:.6E} {code}\n"

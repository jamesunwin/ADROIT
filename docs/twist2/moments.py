"""The quark momentum moments ⟨x⟩ and ⟨x²⟩ at μ = m_Z, for the coloured partner's twist-2 remainder bound.

The coloured t-channel partner's twist-2 coefficient expands the partner propagator in ε x, x the struck quark's
momentum fraction; term n carries the moment ⟨x^{n+1}⟩ (quark plus antiquark). Since 0 ≤ x ≤ 1, every moment
beyond the second is at most ⟨x²⟩, so the remainder after the leading term is at most (⟨x²⟩/⟨x⟩) ε/(1 − ε)
(``adroit/constraints/loops.py``). This script integrates the central member of PDF4LHC21_40 (in the tools
folder, read from its LHAPDF grid file directly) at μ = m_Z and prints the ratios stored there. $0, no network:

    uv run python docs/twist2/moments.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

GRID = Path.home() / "agentic-dm-tools" / "lhapdf" / "PDF4LHC21_40" / "PDF4LHC21_40_0000.dat"
M_Z = 91.1876
QUARKS = {"d": 1, "u": 2, "s": 3, "c": 4, "b": 5}


def blocks(text: str):
    """Each subgrid: (x knots, Q knots, flavours, values[x, Q, flavour]) of x f(x, Q)."""
    parts = text.split("---")[1:]
    for part in parts:
        lines = [row for row in part.strip().splitlines() if row.strip()]
        if len(lines) < 4:
            continue
        x = np.array(lines[0].split(), float)
        q = np.array(lines[1].split(), float)
        flavours = [int(v) for v in lines[2].split()]
        values = np.array([row.split() for row in lines[3:]], float).reshape(len(x), len(q), len(flavours))
        yield x, q, flavours, values


def at_mz(grid: Path = GRID):
    for x, q, flavours, values in blocks(grid.read_text()):
        if q[0] <= M_Z <= q[-1]:
            j = int(np.searchsorted(q, M_Z)) - 1
            w = (math.log(M_Z) - math.log(q[j])) / (math.log(q[j + 1]) - math.log(q[j]))
            return x, flavours, (1 - w) * values[:, j, :] + w * values[:, j + 1, :]
    raise ValueError("no subgrid holds m_Z")


def moment(x: np.ndarray, xf: np.ndarray, k: int) -> float:
    """∫ dx x^{k−1} (x f) = ⟨x^k⟩, on the knots in ln x (dx = x d ln x), with the x → 1 end closed."""
    integrand = x ** (k - 1) * xf * x
    return float(np.trapezoid(integrand, np.log(x)))


def main() -> int:
    x, flavours, xf = at_mz()
    column = {f: xf[:, i] for i, f in enumerate(flavours)}
    total = sum(moment(x, column[f], 1) for f in flavours)
    print(f"momentum sum at m_Z: {total:.4f} (should be 1)")
    for name, pid in QUARKS.items():
        first = moment(x, column[pid], 1) + moment(x, column[-pid], 1)
        second = moment(x, column[pid], 2) + moment(x, column[-pid], 2)
        print(f"{name}: <x> = {first:.4f}, <x^2> = {second:.5f}, ratio = {second / first:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

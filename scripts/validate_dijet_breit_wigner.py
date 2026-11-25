"""The dijet Gaussian record against ATLAS's own Breit–Wigner Z′ limits (the external audit's item 18; $0, offline).

ATLAS's DM Z′ (universal quark coupling g_q, no dark-matter decay; Γ/m = 3g_q²/(2π)) is simulated by ATLAS with its
Breit–Wigner line shape, so its limits (arXiv:1910.08447, Table 2 and HEPData Table 10) test how ADROIT applies the
Gaussian limits to a Breit–Wigner:
- **the recipe** (the decision since 2026-10-17): A × the share inside 0.8–1.2 M against the 10% Gaussian;
- **the matching** (a flag since then): A against the Gaussian at σ_G = Γ/2.355.
At ATLAS's limit the true ratio is 1. Needs the Z′ production table in the tools folder.
Usage: ``uv run python scripts/validate_dijet_breit_wigner.py``.
"""

from __future__ import annotations

import math

import numpy as np

from adroit.parameter_space import resonances as rs
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point, Spin1Class

Z_PRIME = Spin1Class(name="ATLAS's DM Z′")


def ratios(m: float, g: float, acceptance_from: float | None = None) -> tuple[float | None, float | None, float]:
    """(recipe, matching, Γ/m) at (M, g_q); with ``acceptance_from``, A is that coupling's (an upper bound on A for a
    broader Z′, whose acceptance falls with the width)."""
    sigma, _, _, widths = ps._z_prime(Z_PRIME, Point(m_chi=2e4, m_med=m, g_q=g, g_chi=0.0, g_l=0.0))
    total = sum(widths.values())
    jj = sum(w for k, w in widths.items() if k != "dm" and abs(k[0]) <= 5) / total
    width = total / m
    if acceptance_from is None:
        recipe, matched, _ = rs._atlas_gaussian(Point(m_chi=2e4, m_med=m), sigma * jj, width)
        return recipe, matched, width
    data = ps.s._bundled(rs.ATLAS_GAUSSIAN)
    widths_pct = sorted(float(w) for w in data["gaussian_limits"])
    limits = [ps.s.interpolate(data["gaussian_limits"][str(w)], m) for w in widths_pct]
    accepted = sigma * jj * rs._acceptance(m, 3.0 * acceptance_from ** 2 / (2.0 * math.pi))[0]
    matched = accepted / float(np.interp(100 * width / rs.FWHM, widths_pct, limits))
    recipe = accepted * rs.window_fraction(m, width) / float(np.interp(15.0, widths_pct, limits))
    return recipe, matched, width


def crossing(g: float, masses: np.ndarray, which: int) -> float | None:
    """The mass below which the ratio exceeds 1 (log-linear between grid points)."""
    rows = [(m, ratios(m, g)[which]) for m in masses]
    rows = [(m, r) for m, r in rows if r is not None]
    for (m1, r1), (m2, r2) in zip(rows, rows[1:]):
        if r1 >= 1.0 > r2:
            return m1 + (m2 - m1) * math.log(r1) / (math.log(r1) - math.log(r2))
    return None


def main() -> int:
    print("| ATLAS's DM Z′ | Γ/m | ATLAS (observed) | recipe | matching |\n|---|---|---|---|---|")
    grid = np.arange(4000.0, 6001.0, 50.0)
    recipe_m, matched_m = crossing(0.5, grid, 0), crossing(0.5, grid, 1)
    r_at, m_at, width = ratios(4600.0, 0.5)
    print(f"| g_q = 0.5, excluded below | {100 * width:.1f}% | 4.6 TeV (Table 2) | {recipe_m / 1e3:.2f} TeV | "
          f"{matched_m / 1e3:.2f} TeV |")
    print(f"| g_q = 0.5 at 4.6 TeV: ratio | {100 * width:.1f}% | 1 | {r_at:.2f} | {m_at:.2f} |")
    r5, m5, w5 = ratios(5000.0, 0.716319, acceptance_from=0.5)
    print(f"| g_q = 0.716 at 5 TeV (Table 10): ratio, A of g_q = 0.5 | {100 * w5:.1f}% | 1 | ≤ {r5:.2f} (15% Gaussian) "
          f"| ≤ {m5:.2f} |")
    narrow = crossing(0.2, np.arange(3000.0, 4501.0, 50.0), 1)
    print(f"\nOutside the record's widths: g_q = 0.2 (Γ/m = 1.9%), the matching excludes below {narrow / 1e3:.2f} TeV, "
          "ATLAS below 3.8 TeV (Table 2).")
    print("\nShare of the selected dijets inside 0.8–1.2 M (Breit–Wigner × q q̄ luminosity, LO, parton level):")
    for m in (2000.0, 3000.0, 4000.0, 5000.0, 6000.0):
        print(f"  M = {m / 1e3:.0f} TeV: " + ", ".join(f"Γ/m = {w:.2f}: {rs.window_fraction(m, w):.3f}"
                                                    for w in (0.10, 0.11, 0.12)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

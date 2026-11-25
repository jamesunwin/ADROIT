"""Digitise Calore et al.'s propagation and halo-profile systematics for the AMS-02 antiproton bound.

Calore, Cirelli, Derome, Génolini, Maurin, Salati & Serpico, arXiv:2202.03076 (SciPost Phys. 12, 163), Fig. 4,
page 14. Both panels show the 95% CL bound on ⟨σv⟩ for b b̄ annihilation:
- **left:** the BIG transport scheme with three dark-matter profiles (Table 1): the benchmark NFW (blue, solid),
  a cored profile (green, dashed) and a contracted NFW (red, dash-dotted);
- **right:** the benchmark NFW with three transport schemes calibrated on AMS-02's secondary-to-primary ratios:
  BIG (blue, solid), SLIM (orange, dashed) and QUAINT (green, dash-dotted).

The bound already profiles the halo height L (σ_log L = 0.197) and the solar modulation within each scheme; these
panels are the paper's remaining "theoretical systematics" (Sec. 5.2). The figure is vector graphics but its tick
labels are glyph outlines, so each axis's decade spacing is read from its tick marks and the absolute position from
the blue BIG/NFW curve, which is the b b̄ curve of Fig. 2 already digitised in
``adroit/constraints/data/digitised/calore_2202.03076_pbar.yaml``. The legend identities follow the label widths
and the paper's text (the cored profile weakens the bound; QUAINT is tighter at low mass and weaker at high mass)
and are checked below.

Run from the repository root:

    uv run --with pymupdf python docs/dm7/digitise_calore_propagation.py

Writes adroit/constraints/data/propagation/calore-2202.03076-pbar.yaml: the six curves, and on a mass grid the
factors by which the conservative and aggressive bounds differ from the central one.
"""

from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pymupdf
import yaml

ROOT = Path(__file__).resolve().parents[2]
PAPER = Path.home() / "agentic-dm-tools" / "papers" / "2202.03076.pdf"
CENTRAL = ROOT / "adroit" / "constraints" / "data" / "digitised" / "calore_2202.03076_pbar.yaml"
OUT = ROOT / "adroit" / "constraints" / "data" / "propagation" / "calore-2202.03076-pbar.yaml"
PANELS = {"profiles": (90.0, 305.0), "schemes": (305.0, 530.0)}          # page x-ranges of the two panels
COLOURS = {"profiles": {(0.12, 0.47, 0.71): "benchmark NFW", (0.42, 0.63, 0.34): "cored",
                        (1.0, 0.0, 0.0): "contracted NFW"},
           "schemes": {(0.12, 0.47, 0.71): "BIG", (1.0, 0.5, 0.05): "SLIM", (0.17, 0.63, 0.17): "QUAINT"}}


def curves(page: pymupdf.Page, panel: str) -> dict[str, np.ndarray]:
    """Each named curve's page points (x increasing). A curve's legend sample is a long horizontal segment, which a
    curve sampled every ~1.2 pt never has, so such segments are left out."""
    lo, hi = PANELS[panel]
    out: dict[str, set] = {}
    for d in page.get_drawings():
        colour = tuple(round(c, 2) for c in (d.get("color") or ()))
        name = COLOURS[panel].get(colour)
        if name is None or (d.get("width") or 0) < 0.3 or not lo <= d["rect"].x0 <= hi:
            continue
        for it in d["items"]:
            if it[0] != "l":
                continue
            a, b = it[1], it[2]
            if abs(a.y - b.y) < 0.01 and abs(a.x - b.x) > 20:
                continue
            out.setdefault(name, set()).update({(round(a.x, 3), round(a.y, 3)), (round(b.x, 3), round(b.y, 3))})
    return {name: np.array(sorted(points)) for name, points in out.items()}


def decade_spacing(page: pymupdf.Page, panel: str) -> tuple[float, float]:
    """(points per decade in x, in y) from the major ticks (about 3 pt long; minor ones are 1.5 pt) that start on
    the frame's top and left edges. The frame's own edges are the segments longer than 150 pt."""
    lo, hi = PANELS[panel]
    segments = [(it[1], it[2]) for d in page.get_drawings()
                if lo <= d["rect"].x0 <= hi and tuple(d.get("color") or ()) == (0.0, 0.0, 0.0)
                for it in d["items"] if it[0] == "l"]
    left = min(a.x for a, b in segments if abs(a.x - b.x) < 0.01 and abs(a.y - b.y) > 150)
    top = min(min(a.y, b.y) for a, b in segments if abs(a.y - b.y) < 0.01 and abs(a.x - b.x) > 150)
    xs = sorted({round(a.x, 2) for a, b in segments if abs(a.x - b.x) < 0.01 and abs(min(a.y, b.y) - top) < 0.05
                 and 2.5 < abs(a.y - b.y) < 5})
    ys = sorted({round(a.y, 2) for a, b in segments if abs(a.y - b.y) < 0.01 and abs(min(a.x, b.x) - left) < 0.05
                 and 2.5 < abs(a.x - b.x) < 5})
    return float(np.median(np.diff(xs))), float(np.median(np.diff(ys)))


def calibrate(blue: np.ndarray, reference: np.ndarray, spacing: tuple[float, float]) -> tuple[float, float]:
    """(log₁₀ m at x = 0, log₁₀ σv at y = 0): the offsets that put the blue curve on Fig. 2's b b̄ curve."""
    dx, dy = spacing
    ref_x, ref_y = np.log10(reference[:, 0]), np.log10(reference[:, 1])

    def misfit(offsets):
        ox, oy = offsets
        lx, ly = ox + blue[:, 0] / dx, oy - blue[:, 1] / dy
        inside = (lx >= ref_x[0]) & (lx <= ref_x[-1])
        return float(np.mean((ly[inside] - np.interp(lx[inside], ref_x, ref_y)) ** 2)) if inside.sum() > 20 else 1e9

    best = None
    for ox in np.linspace(-15, 5, 2001):                        # coarse grid, then refine
        oy = float(np.median(np.interp(ox + blue[:, 0] / dx, ref_x, ref_y) + blue[:, 1] / dy))
        score = misfit((ox, oy))
        if best is None or score < best[0]:
            best = (score, ox, oy)
    from scipy.optimize import minimize
    fit = minimize(misfit, best[1:], method="Nelder-Mead", options={"xatol": 1e-7, "fatol": 1e-12})
    return float(fit.x[0]), float(fit.x[1])


def physical(points: np.ndarray, offsets: tuple[float, float], spacing: tuple[float, float]) -> np.ndarray:
    ox, oy = offsets
    dx, dy = spacing
    return np.column_stack([10 ** (ox + points[:, 0] / dx), 10 ** (oy - points[:, 1] / dy)])


def main() -> int:
    if not PAPER.exists():
        print(f"missing {PAPER}")
        return 2
    page = pymupdf.open(PAPER)[13]
    reference = np.array(yaml.safe_load(CENTRAL.read_text())["limits"]["bb"])
    out, residuals = {}, {}
    for panel in PANELS:
        found = curves(page, panel)
        spacing = decade_spacing(page, panel)
        blue_name = "benchmark NFW" if panel == "profiles" else "BIG"
        offsets = calibrate(found[blue_name], reference, spacing)
        out[panel] = {name: physical(points, offsets, spacing) for name, points in found.items()}
        blue = out[panel][blue_name]
        inside = (blue[:, 0] >= reference[0, 0]) & (blue[:, 0] <= reference[-1, 0])
        residuals[panel] = float(np.max(np.abs(np.log10(blue[inside, 1]) - np.interp(
            np.log10(blue[inside, 0]), np.log10(reference[:, 0]), np.log10(reference[:, 1])))))
        print(f"{panel}: {spacing[0]:.2f} pt/decade in m, {spacing[1]:.2f} in σv; blue against Fig. 2: "
              f"max {residuals[panel]:.4f} dex")
    grid = np.geomspace(max(c[0, 0] for p in out.values() for c in p.values()),      # where every curve is drawn
                        min(c[-1, 0] for p in out.values() for c in p.values()), 60)

    def at(curve: np.ndarray) -> np.ndarray:
        return 10 ** np.interp(np.log10(grid), np.log10(curve[:, 0]), np.log10(curve[:, 1]))

    profiles = {k: at(v) / at(out["profiles"]["benchmark NFW"]) for k, v in out["profiles"].items()}
    schemes = {k: at(v) / at(out["schemes"]["BIG"]) for k, v in out["schemes"].items()}
    weakest = np.max(list(profiles.values()), axis=0) * np.max(list(schemes.values()), axis=0)
    strongest = np.min(list(profiles.values()), axis=0) * np.min(list(schemes.values()), axis=0)
    low, high = grid < 100, grid > 1000
    checks = {
        "cored weakens the bound at every mass": bool((profiles["cored"] >= 0.999).all()),
        "contracted NFW strengthens it at every mass": bool((profiles["contracted NFW"] <= 1.001).all()),
        "profile shifts below a factor two": bool((np.abs(np.log10(list(profiles.values()))) < math.log10(2)).all()),
        "QUAINT tighter than BIG below 100 GeV": bool((schemes["QUAINT"][low] < 1).mean() > 0.5),
        "QUAINT weaker than BIG above 1 TeV": bool((schemes["QUAINT"][high] > 1).mean() > 0.5),
    }
    for text, ok in checks.items():
        print(f"  {'pass' if ok else 'FAIL'}: {text}")
    data = {
        "record": "calore-2202.03076-pbar",
        "source": "Calore et al., arXiv:2202.03076 (SciPost Phys. 12, 163), Fig. 4 (p. 14): b b̄, 95% CL; left panel the "
                  "dark-matter profiles of Table 1 with the BIG scheme, right panel the BIG, SLIM and QUAINT schemes "
                  "with the benchmark NFW",
        "digitised": str(date.today()), "by": "docs/dm7/digitise_calore_propagation.py, from the vector paths",
        "calibration": {"decade spacing": "from the major ticks", "anchor": "the BIG/NFW curve on Fig. 2's b b̄ curve",
                        "max residual dex": residuals},
        "checks": checks,
        "models": {
            "central": "the paper's fiducial bound: BIG transport, benchmark NFW (ρ⊙ = 0.385 GeV/cm³), halo height and "
                       "solar modulation profiled",
            "conservative": "the weakest bound over the paper's transport schemes (BIG, SLIM, QUAINT) times the weakest "
                            "over its profiles (benchmark NFW, cored, contracted NFW), mass by mass",
            "aggressive": "the strongest bound over the same schemes and profiles, mass by mass",
        },
        "assumptions": [
            "the scheme and profile shifts are read for b b̄ and applied to every channel (the paper: the profile "
            "shifts are 'rather similar' for the other channels; the scheme shifts change shape and are shown for "
            "b b̄ only)",
            "the two shifts multiply (each panel varies one choice with the other at its fiducial value)",
            "outside the figure's masses the conservative factor is its largest value and the aggressive its smallest",
            "ρ⊙ stays at the paper's 0.385 GeV/cm³; the bounds scale as ρ⊙⁻² (a 30% uncertainty in ρ⊙ is about 70% "
            "in the signal, the paper notes)",
        ],
        "curves": {panel: {name: [[float(f"{m:.5g}"), float(f"{s:.5g}")] for m, s in c[::2]]
                           for name, c in found.items()} for panel, found in out.items()},
        "factors": {"mass_gev": [float(f"{m:.5g}") for m in grid],
                    "conservative": [round(float(v), 4) for v in weakest],
                    "aggressive": [round(float(v), 4) for v in strongest]},
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120))
    print(f"conservative ×{weakest.min():.2f}–{weakest.max():.2f}, aggressive ×{strongest.min():.2f}–{strongest.max():.2f}"
          f" over {grid[0]:.3g}–{grid[-1]:.3g} GeV; wrote {OUT.relative_to(ROOT)}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

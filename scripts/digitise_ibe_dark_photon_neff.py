"""Planck's N_eff exclusion for a freeze-in dark photon: the red region of Ibe, Kobayashi, Nakayama & Shirai,
arXiv:1912.12152, Fig. 4(a), read from the PDF's vector paths (record ibe-1912.12152-dark-photon-neff).

    uv run --with pymupdf python scripts/digitise_ibe_dark_photon_neff.py [--write]       # $0, seconds

The figure is on PDF page 11 (printed page 10). Its left panel has exactly one red-filled path (fill (1, 0, 0),
opacity 0.5): the region excluded by Planck's N_eff = 2.99 +0.34 −0.33 (95% CL). Its vertices are mapped to
(m_γ′, ε) through the drawn axes: the major ticks at m = 1, 10, 100 MeV (x) and the frame's edges at ε = 10⁻² and
10⁻¹¹ (y; the tick labels sit on them, one decade per 15.68 points). Without --write it only prints the polygon.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "adroit" / "constraints" / "data" / "digitised" / "ibe_1912.12152_fig4a.yaml"
PAGE = 10                                   # 0-based: PDF page 11
X_MAJOR = {1.0: 112.344, 10.0: 205.694, 100.0: 299.025}    # the drawn major ticks (PDF points)
Y_TOP, Y_BOTTOM = (64.865, -2.0), (205.968, -11.0)          # the frame's edges: (PDF y, log10 ε)


def _log_m(x: float) -> float:
    per_decade = (X_MAJOR[100.0] - X_MAJOR[1.0]) / 2.0
    return (x - X_MAJOR[1.0]) / per_decade


def _log_eps(y: float) -> float:
    return Y_TOP[1] + (y - Y_TOP[0]) * (Y_BOTTOM[1] - Y_TOP[1]) / (Y_BOTTOM[0] - Y_TOP[0])


def digitise(pdf: Path) -> dict:
    """The red region's vertices, in order, as (m_γ′ in MeV, ε)."""
    import pymupdf
    with pymupdf.open(pdf) as doc:
        drawings = doc[PAGE].get_drawings()
    red = [d for d in drawings if d.get("fill") and tuple(round(v, 2) for v in d["fill"]) == (1.0, 0.0, 0.0)
           and d["rect"].x1 < 310]                                    # the left panel only
    if len(red) != 1 or {item[0] for item in red[0]["items"]} != {"l"}:
        raise ValueError("expected one red polygon of straight segments in Fig. 4(a)")
    points = []
    for item in red[0]["items"]:
        for vertex in (item[1], item[2]):
            point = (vertex.x, vertex.y)
            if not points or max(abs(point[0] - points[-1][0]), abs(point[1] - points[-1][1])) > 1e-6:
                points.append(point)
    return {
        "source": "Ibe, Kobayashi, Nakayama & Shirai, arXiv:1912.12152v3, Fig. 4(a) (freeze-in), PDF page 11: the red "
                  "region, Planck's N_eff = 2.99 +0.34 −0.33 (95% CL)",
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "method": "the PDF's vector path (one red-filled polygon, its vertices in order); x through the major ticks "
                  "at 1, 10, 100 MeV, y through the frame's edges at 10⁻² and 10⁻¹¹",
        "axes": {"x_major_ticks_points": X_MAJOR, "y_frame_points": [list(Y_TOP), list(Y_BOTTOM)]},
        "frame": {"mass_mev": [round(10 ** _log_m(103.301), 4), 100.0], "epsilon": [1.0e-11, 1.0e-2]},
        "mass_mev": [round(10 ** _log_m(x), 5) for x, _ in points],
        "epsilon": [float(f"{10 ** _log_eps(y):.5g}") for _, y in points],
    }


def main() -> None:
    from adroit.core.config import get_settings
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pdf", type=Path, default=get_settings().tools_dir / "record-sources" / "1912.12152.pdf")
    args = parser.parse_args()
    data = digitise(args.pdf)
    m, e = data["mass_mev"], data["epsilon"]
    print(f"{len(m)} vertices; m {min(m):.3g}–{max(m):.3g} MeV, ε {min(e):.3g}–{max(e):.3g}")
    lowest = min(range(len(e)), key=e.__getitem__)
    print(f"lowest ε {e[lowest]:.3g} at m = {m[lowest]:.3g} MeV; ε at its right edge near m = 9 MeV: "
          f"{[(round(a, 2), f'{b:.2g}') for a, b in zip(m, e) if a > 0.9 * max(m)][:6]}")
    if args.write:
        OUT.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
        print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

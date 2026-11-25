"""Digitise the published limits DM7's records rest on, from the figures' vector data.

- **IceCube, arXiv:1612.05949** (EPJC 77 (2017) 146), Fig. 7 (σ_SD,p) and
  Fig. 8 (σ_SI,p): the IceCube limits (thick solid lines) for annihilation into
  b b̄ (blue), W⁺W⁻ (green) and τ⁺τ⁻ (red), in equilibrium in the Sun. The
  caption: the SD limits are scaled up to the upper edge of the systematic
  band; the SI limits include the systematic uncertainties.
- **Fermi-LAT, arXiv:1503.02641** (PRL 115 (2015) 231301), Fig. 8: the 95% CL
  upper limits on ⟨σv⟩ from 15 dwarf spheroidal galaxies (solid black line),
  one panel per channel: e⁺e⁻, μ⁺μ⁻, τ⁺τ⁻ (left, top to bottom), u ū, b b̄,
  W⁺W⁻ (right).

Both figures are vector graphics: curves are read as path coordinates. Each
panel is calibrated from its major tick marks (the longer ticks on its bottom
and left edges), matched to the nearest numeric label of the axis ("10 N" or
"10 − N"). Label centres alone would bias a logarithmic axis by the
superscript's offset, up to 8% here.

Run from the repository root:

    uv run --with pymupdf python docs/dm7/digitise_limits.py

Writes adroit/constraints/data/digitised/{icecube_1612.05949,fermi_1503.02641}.yaml.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pymupdf
import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.config import get_settings  # noqa: E402

OUT = ROOT / "adroit/constraints/data/digitised"
BLACK = (0.0, 0.0, 0.0)
ICECUBE_CHANNELS = {(0.0, 0.0, 1.0): "bb", (0.0, 0.5, 0.0): "WW", (1.0, 0.0, 0.0): "tautau"}
FERMI_PANELS = [("ee", 0, 0), ("mumu", 0, 1), ("tautau", 0, 2), ("uu", 1, 0), ("bb", 1, 1), ("WW", 1, 2)]


def paper(arxiv_id: str) -> pymupdf.Document:
    """The paper's PDF, downloaded once into the tools folder."""
    path = get_settings().tools_dir / "papers" / f"{arxiv_id}.pdf"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(f"https://arxiv.org/pdf/{arxiv_id}", headers={"User-Agent": "adroit"},
                                timeout=120)
        response.raise_for_status()
        path.write_bytes(response.content)
    return pymupdf.open(path)


def colour(drawing: dict) -> tuple[float, ...]:
    return tuple(round(v, 2) for v in (drawing.get("color") or ()))


def frames(page: pymupdf.Page, width: float, height: float) -> list[pymupdf.Rect]:
    """White-filled rectangles of the given size: the plot areas."""
    return [d["rect"] for d in page.get_drawings()
            if d.get("fill") and tuple(round(v, 2) for v in d["fill"]) == (1.0, 1.0, 1.0)
            and abs(d["rect"].width - width) < 1 and abs(d["rect"].height - height) < 1]


def major_ticks(page: pymupdf.Page, frame: pymupdf.Rect) -> tuple[list[float], list[float]]:
    """Positions of the longest ticks on the bottom edge (x) and the left edge (y)."""
    xs, ys = {}, {}
    for d in page.get_drawings():
        if colour(d) != BLACK:
            continue
        for item in d["items"]:
            if item[0] != "l":
                continue
            p, q = item[1], item[2]
            length = abs(p.x - q.x) + abs(p.y - q.y)
            if abs(p.x - q.x) < 0.01 and min(abs(p.y - frame.y1), abs(q.y - frame.y1)) < 0.2 and length < 8:
                xs[round(p.x, 2)] = max(xs.get(round(p.x, 2), 0), length)
            if abs(p.y - q.y) < 0.01 and min(abs(p.x - frame.x0), abs(q.x - frame.x0)) < 0.2 and length < 8:
                ys[round(p.y, 2)] = max(ys.get(round(p.y, 2), 0), length)
    top_x, top_y = max(xs.values()), max(ys.values())
    return (sorted(x for x, n in xs.items() if n > 0.8 * top_x),
            sorted(y for y, n in ys.items() if n > 0.8 * top_y))


def decade_labels(page: pymupdf.Page) -> list[tuple[float, float, float]]:
    """Every "10 N" label on the page: (x centre, y centre, N)."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = " ".join(s["text"] for s in line["spans"]).replace("−", "-")
            match = re.fullmatch(r"\s*10\s*(-?)\s*(\d+)\s*", text)
            if match:
                bb = line["bbox"]
                out.append(((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2,
                            float(match.group(2)) * (-1 if match.group(1) else 1)))
    return out


def calibration(page: pymupdf.Page, frame: pymupdf.Rect) -> dict[str, float]:
    """log₁₀ of the axis values as linear functions of the page coordinates."""
    ticks_x, ticks_y = major_ticks(page, frame)
    labels = decade_labels(page)
    below = [(x, n) for x, y, n in labels if y > frame.y1 and frame.x0 - 10 < x < frame.x1 + 10]
    left = [(y, n) for x, y, n in labels if x < frame.x0 and frame.y0 - 10 < y < frame.y1 + 10]
    if not below:        # an upper panel: its column's labels are further down the page
        below = [(x, n) for x, y, n in labels if frame.x0 - 10 < x < frame.x1 + 10 and y > frame.y0]
    if not left:         # a right-hand panel: its row's labels are further left
        left = [(y, n) for x, y, n in labels if frame.y0 - 10 < y < frame.y1 + 10 and x < frame.x1]
    px = [(t, min(below, key=lambda b: abs(b[0] - t))) for t in ticks_x]
    py = [(t, min(left, key=lambda b: abs(b[0] - t))) for t in ticks_y]
    px = [(t, n) for t, (pos, n) in px if abs(pos - t) < 12]
    py = [(t, n) for t, (pos, n) in py if abs(pos - t) < 12]
    if len(px) < 2 or len(py) < 2:
        raise ValueError(f"cannot calibrate the frame at {frame}")
    x_slope, x_offset = np.polyfit([t for t, _ in px], [n for _, n in px], 1)
    y_slope, y_offset = np.polyfit([t for t, _ in py], [n for _, n in py], 1)
    return {"x_slope": float(x_slope), "x_offset": float(x_offset),
            "y_slope": float(y_slope), "y_offset": float(y_offset), "ticks": [len(px), len(py)]}


def curve(drawing: dict, cal: dict[str, float]) -> list[list[float]]:
    """The drawing's path as [x, y] in data units (one polyline, in drawing order)."""
    points = []
    for item in drawing["items"]:
        if item[0] == "l":
            for p in (item[1], item[2]):
                pt = [float(10 ** (cal["x_slope"] * p.x + cal["x_offset"])),
                      float(10 ** (cal["y_slope"] * p.y + cal["y_offset"]))]
                if not points or points[-1] != pt:
                    points.append(pt)
    return [[float(f"{x:.5g}"), float(f"{y:.5g}")] for x, y in points]


def icecube() -> dict:
    """IceCube's SD (Fig. 7) and SI (Fig. 8) limits by channel."""
    page = paper("1612.05949")[11]
    out = {}
    for label, frame, width in (("SD_proton", frames(page, 297.3, 219.5)[0], 3.08),
                                ("SI_proton", frames(page, 366.4, 220.9)[0], 2.47)):
        cal = calibration(page, frame)
        lines = {}
        for d in page.get_drawings():
            if (colour(d) in ICECUBE_CHANNELS and round(d.get("width") or 0, 2) == width
                    and d.get("dashes") in ("[] 0", None) and frame.contains(d["rect"])
                    and len(d["items"]) > 2):
                lines[ICECUBE_CHANNELS[colour(d)]] = curve(d, cal)
        out[label] = {"calibration": cal, "limits_cm2": lines}
    return out


def fermi() -> dict:
    """Fermi-LAT's 15-dwarf limits on ⟨σv⟩ by channel (Fig. 8)."""
    page = paper("1503.02641")[17]
    panels = sorted(frames(page, 197.8, 125.9), key=lambda r: (r.x0, r.y0))
    out = {}
    for channel, column, row in FERMI_PANELS:
        frame = panels[3 * column + row]
        cal = calibration(page, frame)
        (limit,) = [d for d in page.get_drawings()
                    if colour(d) == BLACK and round(d.get("width") or 0, 2) == 1.48
                    and frame.contains(d["rect"]) and len(d["items"]) > 5]
        out[channel] = {"calibration": cal, "limit_cm3_s": curve(limit, cal)}
    return out


def main() -> None:
    """Digitise and write both records."""
    today = str(date.today())
    records = {
        "icecube_1612.05949.yaml": {
            "source": "IceCube, EPJC 77 (2017) 146, arXiv:1612.05949, Figs. 7 and 8",
            "digitised": today, "by": "docs/dm7/digitise_limits.py, from the vector paths of the arXiv PDF",
            "axes": "points are [m_χ (GeV), σ (cm²)], 90% CL",
            "assumptions": ["capture–annihilation equilibrium in the Sun",
                            "annihilation entirely into the named channel"],
            "limits": icecube()},
        "fermi_1503.02641.yaml": {
            "source": "Fermi-LAT, PRL 115 (2015) 231301, arXiv:1503.02641, Fig. 8",
            "digitised": today, "by": "docs/dm7/digitise_limits.py, from the vector paths of the arXiv PDF",
            "axes": "points are [m_χ (GeV), ⟨σv⟩ (cm³/s)], 95% CL, 15 dwarf spheroidal galaxies",
            "assumptions": ["annihilation entirely into the named channel", "the paper's J-factors",
                            "self-conjugate dark matter (for Dirac dark matter ⟨σv⟩ is compared ×1/2)"],
            "limits": fermi()},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, record in records.items():
        (OUT / name).write_text(yaml.safe_dump(record, sort_keys=False, width=120, allow_unicode=True, default_flow_style=None))
        print("wrote", name)


if __name__ == "__main__":
    main()

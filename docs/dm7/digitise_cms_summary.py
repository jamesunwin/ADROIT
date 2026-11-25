"""Digitise CMS's summary of the spin-1 mediator models from the figures' vector data.

CMS, "Dark sector searches with the CMS experiment", Phys. Rept. 1115 (2025) 448,
arXiv:2405.13778: Fig. 11 (V1 upper, A1 lower; page 31) and Fig. 12 (V2 upper,
A2 lower; page 32). The figures are vector graphics, so every curve is read
as the coordinates of its drawn path (precision ~0.01 pt, far below the line
widths). Each panel is calibrated from its own tick marks: the three long
ticks of the logarithmic mediator-mass axis (10², 10³, 10⁴ GeV) and the long
ticks of the linear dark-matter-mass axis (every 200 GeV from 0 to 2000).

Read from each panel:
- the thermal-relic contour Ωh² = 0.12 (grey, solid);
- the line m_DM = m_med/2 (grey, dashed);
- every search's observed (solid) and expected (dashed) exclusion contour,
  named from the legend row of its colour;
- the filled excluded regions, where the figure fills them (the dijet
  searches), as closed polygons. The searches with missing energy are drawn
  as lines only; their excluded region lies between the line and m_DM = 0.

Run from the repository root:

    uv run --with pymupdf python docs/dm7/digitise_cms_summary.py

It downloads the PDF into the tools folder and writes
adroit/constraints/data/digitised/cms_2405.13778_spin1.yaml.
"""

from __future__ import annotations

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

OUT = ROOT / "adroit/constraints/data/digitised/cms_2405.13778_spin1.yaml"
URL = "https://arxiv.org/pdf/2405.13778v2"
PANELS = {30: ("V1", "A1"), 31: ("V2", "A2")}      # page index → (upper, lower)
GREY = (0.6, 0.6, 0.6)
BLACK = (0.0, 0.0, 0.0)


def paper() -> pymupdf.Document:
    """The report's PDF, downloaded once into the tools folder."""
    path = get_settings().tools_dir / "papers" / "2405.13778.pdf"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(URL, headers={"User-Agent": "adroit"}, timeout=120)
        response.raise_for_status()
        path.write_bytes(response.content)
    return pymupdf.open(path)


def colour(drawing: dict) -> tuple[float, ...]:
    return tuple(round(v, 2) for v in (drawing.get("color") or ()))


def frames(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """The plot frames: white rectangles about 249 × 171 pt, top to bottom."""
    found = {(round(d["rect"].x0, 1), round(d["rect"].y0, 1)): d["rect"] for d in page.get_drawings()
             if d.get("fill") and colour(d) == (1.0, 1.0, 1.0)
             and abs(d["rect"].width - 249.4) < 2 and abs(d["rect"].height - 171.3) < 2}
    return sorted(found.values(), key=lambda r: r.y0)


def calibration(page: pymupdf.Page, frame: pymupdf.Rect) -> dict[str, float]:
    """x ↦ log₁₀ m_med and y ↦ m_DM from the panel's long tick marks."""
    xs, ys = set(), set()
    for d in page.get_drawings():
        if colour(d) != BLACK or round(d.get("width") or 0, 2) != 0.6:
            continue
        for item in d["items"]:
            if item[0] != "l":
                continue
            p, q = item[1], item[2]
            if (abs(p.x - q.x) < 0.01 and abs(max(p.y, q.y) - frame.y1) < 0.2
                    and 3 < abs(p.y - q.y) < 12):
                xs.add(round(p.x, 3))
            if (abs(p.y - q.y) < 0.01 and abs(min(p.x, q.x) - frame.x0) < 0.2
                    and 10 < abs(p.x - q.x) < 12 and frame.y0 - 0.5 <= p.y <= frame.y1 + 0.5):
                ys.add(round(p.y, 3))
    xs, ys = sorted(xs), sorted(ys, reverse=True)
    if len(xs) != 3 or len(ys) != 11:
        raise ValueError(f"unexpected ticks: {xs}, {ys}")
    x_slope, x_offset = np.polyfit(xs, [2.0, 3.0, 4.0], 1)
    y_slope, y_offset = np.polyfit(ys, np.arange(0.0, 2001.0, 200.0), 1)
    return {"x_slope": x_slope, "x_offset": x_offset, "y_slope": y_slope, "y_offset": y_offset}


def polylines(drawing: dict) -> list[list[tuple[float, float]]]:
    """The drawing's path as polylines of page points (a new one at every break)."""
    lines: list[list[tuple[float, float]]] = []
    for item in drawing["items"]:
        if item[0] == "l":
            a, b = item[1], item[2]
        elif item[0] == "c":
            a, b = item[1], item[4]
        else:
            continue
        if lines and abs(lines[-1][-1][0] - a.x) < 0.01 and abs(lines[-1][-1][1] - a.y) < 0.01:
            lines[-1].append((b.x, b.y))
        else:
            lines.append([(a.x, a.y), (b.x, b.y)])
    return lines


def to_data(line: list[tuple[float, float]], cal: dict[str, float]) -> list[list[float]]:
    """Page points → [m_med (GeV), m_DM (GeV)]."""
    return [[round(float(10 ** (cal["x_slope"] * x + cal["x_offset"])), 3),
             round(float(cal["y_slope"] * y + cal["y_offset"]), 3)] for x, y in line]


def legend(page: pymupdf.Page, frame: pymupdf.Rect) -> tuple[dict, dict]:
    """Each search's line colour and fill colour → the text of its legend row (right of the frame)."""
    lines, fills = {}, {}
    spans = [(line["bbox"], " ".join(s["text"] for s in line["spans"]).strip())
             for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])]

    def row(r: pymupdf.Rect) -> str:
        texts = sorted((bb[0], t) for bb, t in spans
                       if r.x1 < bb[0] < 460.0 and abs((bb[1] + bb[3]) / 2 - (r.y0 + r.y1) / 2) < 7.0)
        return " ".join(" ".join(t for _, t in texts).split())
    for d in page.get_drawings():
        r = d["rect"]
        if r.x0 < frame.x1 or not frame.y0 < r.y0 < frame.y1:
            continue
        if d["type"] == "f" and d.get("fill") and r.height > 5 and r.width < 20:
            fills[tuple(round(v, 2) for v in d["fill"])] = row(r)
        elif (colour(d) not in (BLACK, GREY, ()) and r.height <= 0.5
              and d.get("dashes") in ("[] 0", None)):
            lines[colour(d)] = row(r)
    return lines, fills


def panel(page: pymupdf.Page, frame: pymupdf.Rect) -> dict:
    """Everything drawn inside one frame, in data coordinates."""
    cal = calibration(page, frame)
    names, fill_names = legend(page, frame)
    out = {"relic": [], "half_mass_line": [], "searches": {}}
    inside = pymupdf.Rect(frame.x0 - 0.5, frame.y0 - 0.5, frame.x1 + 0.5, frame.y1 + 0.5)
    for d in page.get_drawings():
        if not inside.contains(d["rect"]) or len(d["items"]) < 3:
            continue
        solid = d.get("dashes") in ("[] 0", None)
        lines = [to_data(line, cal) for line in polylines(d) if len(line) > 2]
        fill = tuple(round(v, 2) for v in (d.get("fill") or ()))
        if d["type"] == "f" and fill in fill_names:
            entry = out["searches"].setdefault(fill_names[fill], {"observed": [], "expected": []})
            entry.setdefault("excluded_regions", []).extend(lines)
            continue
        if colour(d) == GREY and round(d["width"], 2) == 0.6:
            out["relic" if solid else "half_mass_line"].extend(lines)
        elif colour(d) in names and round(d["width"], 2) == 1.2:
            entry = out["searches"].setdefault(names[colour(d)], {"observed": [], "expected": []})
            entry["observed" if solid else "expected"].extend(lines)
    out["calibration"] = {k: round(float(v), 8) for k, v in cal.items()}
    return out


def main() -> None:
    """Digitise both figures and write the YAML."""
    doc = paper()
    panels = {}
    for index, labels in PANELS.items():
        page = doc[index]
        for label, frame in zip(labels, frames(page)):
            panels[label] = panel(page, frame)
            p = panels[label]
            print(label, "relic lines:", [len(x) for x in p["relic"]],
                  "searches:", {k: len(v["observed"]) for k, v in p["searches"].items()})
    record = {
        "source": "CMS, Phys. Rept. 1115 (2025) 448, arXiv:2405.13778, Figs. 11 and 12",
        "digitised": str(date.today()),
        "by": "docs/dm7/digitise_cms_summary.py, from the vector paths of the arXiv PDF",
        "axes": "m_med (GeV, log) and m_DM (GeV, linear); points are [m_med, m_DM]",
        "models": "Dirac DM, s-channel spin-1 mediator, g_DM = 1: V1 and A1 with g_q = 0.25, g_l = 0; "
                  "V2 with g_q = 0.1, g_l = 0.01; A2 with g_q = g_l = 0.1",
        "relic": "the grey solid contour Ωh² = 0.12; half_mass_line is m_DM = m_med/2",
        "panels": panels,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(yaml.safe_dump(record, sort_keys=False, width=120, allow_unicode=True, default_flow_style=None))
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()

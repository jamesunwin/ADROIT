"""Digitise published inputs that exist only as figures, from the figures' vector data.

Both figures are vector graphics in their arXiv PDFs, so the curves are read
as the coordinates of the drawn paths, not traced from an image: the
precision is that of the PDF (about 0.01 pt), far below the line widths.
Axes are calibrated from the centres of the tick labels, and for PICO-60
also from the drawn Seitz-threshold lines, which fall where the labels put
2.45 and 3.29 keV.

- PICO-60, arXiv:1902.04031, Fig. 3: best-fit fluorine and carbon bubble-
  nucleation efficiencies at the 2.45 and 3.29 keV thresholds, with the 1σ
  bands. The curves are piecewise linear with vertices at efficiencies
  0, 0.2, 0.5, 0.8 and 1, so the vertices are the collaboration's
  efficiency-model parameters.
- PICO-60, Figs. 6 and 7: the best-fit integrated detection efficiencies,
  and the published SD-proton limit.
- DEAP-3600, arXiv:1902.04048, Fig. 21: WIMP acceptance against detected
  photoelectrons for the fiducial cut and for the Fprompt and background-
  rejection cuts combined, with the recoil-energy scale of the top axis;
  Fig. 24: the published SI limit, and DarkSide-50's (2018) as drawn there.
- LZ, arXiv:2609.02823, Fig. 1: LZ's recoil spectra for inelastic O1s and for
  L10s; Fig. S2: the extended window's signal efficiency.
- PandaX-4T, arXiv:2408.00664, Figs. 4 and 5: the published SD-neutron and
  SD-proton limits of Run0+Run1 (1.54 tonne-years), and their median
  sensitivities (2026-10-10, the xenon spin-dependent validation).

Run from the repository root:

    uv run --with pymupdf python docs/dm3/digitise_figures.py                 # every figure
    uv run --with pymupdf python docs/dm3/digitise_figures.py --only pandax4t_2024_fig4_fig5

It downloads the two PDFs into the tools folder and writes
adroit/experiments/data/digitised/*.yaml.
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

OUT = ROOT / "adroit/experiments/data/digitised"
PAPERS = {"1902.04031": "https://arxiv.org/pdf/1902.04031v1",
          "1902.04048": "https://arxiv.org/pdf/1902.04048v2",
          "2609.02823": "https://arxiv.org/pdf/2609.02823",
          "2408.00664": "https://arxiv.org/pdf/2408.00664v2"}


def paper(arxiv_id: str) -> pymupdf.Document:
    """The paper's PDF, downloaded once into the tools folder."""
    path = get_settings().tools_dir / "papers" / f"{arxiv_id}.pdf"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(PAPERS[arxiv_id], headers={"User-Agent": "adroit"}, timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
    return pymupdf.open(path)


def label_centres(page: pymupdf.Page, box: tuple[float, float, float, float]) -> dict[str, float]:
    """Numeric text labels inside ``box`` and their centres (x for a bottom or top axis, y for a side axis)."""
    x0, y0, x1, y1 = box
    out = {}
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                bx0, by0, bx1, by1 = span["bbox"]
                text = span["text"].strip()
                if x0 <= bx0 and bx1 <= x1 and y0 <= by0 and by1 <= y1 and text.replace(".", "").isdigit():
                    out[text] = ((bx0 + bx1) / 2, (by0 + by1) / 2)
    return out


def linear_map(pixels: list[float], values: list[float]) -> tuple[float, float]:
    """(slope, offset) of the least-squares line value = slope × pixel + offset."""
    slope, offset = np.polyfit(pixels, values, 1)
    return float(slope), float(offset)


def polyline(drawing: dict) -> np.ndarray:
    """The distinct vertices of a path of straight segments, in drawing order."""
    points = []
    for item in drawing["items"]:
        for point in item[1:]:
            if hasattr(point, "x") and (not points or (point.x, point.y) != points[-1]):
                points.append((point.x, point.y))
    return np.array(points)


def pico60() -> dict:
    """Fig. 3 of arXiv:1902.04031: nucleation efficiencies, fluorine and carbon, two thresholds."""
    page = paper("1902.04031")[3]
    drawings = page.get_drawings()
    ticks = label_centres(page, (85, 370, 290, 382))
    kev_per_pt, kev_offset = linear_map([ticks[k][0] for k in ticks], [float(k) for k in ticks])
    panels = {"2.45": {"top": 256.2, "bottom": 312.1, "curves": {"F": 5, "C": 6},
                       "bands": {"F": 3, "C": 2}, "seitz": 7},
              "3.29": {"top": 317.2, "bottom": 373.1, "curves": {"F": 16, "C": 17},
                       "bands": {"F": 14, "C": 13}, "seitz": 18}}
    out: dict = {}
    for threshold, panel in panels.items():
        def energy(x): return kev_per_pt * x + kev_offset
        def efficiency(y): return (panel["bottom"] - y) / (panel["bottom"] - panel["top"])
        seitz = energy(drawings[panel["seitz"]]["rect"].x0)
        entry = {"seitz_line_kev": round(seitz, 3)}
        for element, index in panel["curves"].items():
            vertices = polyline(drawings[index])
            entry[f"{element}_best_fit"] = {
                "efficiency": [round(abs(float(efficiency(y))), 3) for y in vertices[:, 1]],
                "energy_kev": [round(float(energy(x)), 3) for x in vertices[:, 0]]}
            band = polyline(drawings[panel["bands"][element]])
            entry[f"{element}_band_1sigma"] = {
                "outline_energy_kev": [round(float(energy(x)), 3) for x in band[:, 0]],
                "outline_efficiency": [round(abs(float(efficiency(y))), 3) for y in band[:, 1]],
                "note": "the band's outline, in drawing order; the figure clips it at 16 keV"}
        out[f"threshold_{threshold}_keV"] = entry
    return out


def deap3600() -> dict:
    """Fig. 21 of arXiv:1902.04048: WIMP acceptance against photoelectrons, and the energy axis."""
    page = paper("1902.04048")[23]
    drawings = page.get_drawings()
    bottom = label_centres(page, (340, 640, 545, 660))
    side = label_centres(page, (320, 520, 341, 652))
    top = label_centres(page, (340, 514, 545, 530))
    pe_per_pt, pe_offset = linear_map([bottom[k][0] for k in bottom], [float(k) for k in bottom])
    pct_per_pt, pct_offset = linear_map([side[k][1] for k in side], [float(k) for k in side])
    energy_axis = sorted((float(k), pe_per_pt * c[0] + pe_offset) for k, c in top.items())
    colours = {"fprompt_and_background_rejection": (0.65, 0.46, 0.11),
               "fiducial": (0.72, 0.09, 0.27), "background_rejection": (0.2, 0.63, 0.17),
               "fprompt_0p5_neck_alpha": (0.4, 0.4, 0.4)}
    curves = {}
    for name, colour in colours.items():
        candidates = [d for d in drawings if d.get("color") and len(d["items"]) > 100
                      and tuple(round(c, 2) for c in d["color"]) == colour]
        vertices = polyline(candidates[0])
        curves[name] = {"photoelectrons": [round(float(pe_per_pt * x + pe_offset), 2) for x in vertices[:, 0]],
                        "acceptance_percent": [round(float(pct_per_pt * y + pct_offset), 3)
                                               for y in vertices[:, 1]]}
    return {"curves": curves,
            "energy_axis": {"energy_kevnr": [e for e, _ in energy_axis],
                            "photoelectrons": [round(pe, 2) for _, pe in energy_axis]}}


def log_curve(drawing: dict, x_anchor: tuple[float, float, float], y_anchor: tuple[float, float, float],
              significant: int = 4) -> dict:
    """A curve on log-log axes. Each anchor is (position of decade A, of decade B, A's exponent), B = A + 1... n.

    ``x_anchor`` = (x of 10^a, points per decade, a); ``y_anchor`` likewise, with
    y growing downwards.
    """
    x0, per_decade_x, a = x_anchor
    y0, per_decade_y, b = y_anchor
    vertices = polyline(drawing)
    masses = 10.0 ** (a + (vertices[:, 0] - x0) / per_decade_x)
    sigmas = 10.0 ** (b - (vertices[:, 1] - y0) / per_decade_y)
    return {"mass_gev": [float(f"{m:.{significant}g}") for m in masses],
            "cross_section_cm2": [float(f"{v:.{significant}g}") for v in sigmas]}


def decade_positions(lines: list[float], guesses: dict[int, float]) -> dict[int, float]:
    """Snap each decade's approximate position (from its label) to the nearest drawn line."""
    return {e: min(lines, key=lambda x: abs(x - g)) for e, g in guesses.items()}


def pico60_limit() -> dict:
    """Fig. 7 (the SD-proton limit, thick maroon) and Fig. 6 (best-fit Φ markers) of arXiv:1902.04031."""
    page = paper("1902.04031")[6]
    drawings = page.get_drawings()
    x_ticks = [d["rect"].x0 for d in drawings if d["rect"].height > 2.5 and d["rect"].width < 0.1
               and 390 < d["rect"].x0 < 540 and 340 < d["rect"].y0 < 345]
    y_ticks = [d["rect"].y0 for d in drawings if d["rect"].width > 3.5 and d["rect"].height < 0.1
               and 343 < d["rect"].x0 < 345 and d["rect"].x1 < 349]
    xs = decade_positions(x_ticks, {1: 393.4, 2: 464.3, 3: 535.2})
    ys = decade_positions(y_ticks, {-41: 344.5, -40: 311.6, -39: 278.6, -38: 245.7, -37: 212.8})
    x_anchor = (xs[1], (xs[3] - xs[1]) / 2, 1)
    y_anchor = (ys[-41], (ys[-41] - ys[-37]) / 4, -41)
    maroon = [d for d in drawings if d.get("color") and tuple(round(c, 2) for c in d["color"]) == (0.6, 0.0, 0.2)
              and len(d["items"]) > 20][0]
    markers = [d for d in drawings if tuple(round(c, 2) for c in (d.get("color") or (9, 9, 9))) == (1.0, 0.0, 0.0)
               and len(d["items"]) == 12]
    panels = [("5 GeV SI", (2000.0, 97.2, 27.97 / 1000), (1500.0, 342.25, 23.25 / 500)),
              ("19 GeV SD-proton", (80.0, 109.9, 37.05 / 5), (75.0, 523.15, 38.85 / 5))]
    best = {}
    for marker, (label, (x_value, x_at, x_scale), (y_value, y_at, y_scale)) in zip(
            sorted(markers, key=lambda d: d["rect"].y0), panels):
        cx, cy = (marker["rect"].x0 + marker["rect"].x1) / 2, (marker["rect"].y0 + marker["rect"].y1) / 2
        best[label] = {"phi_2.45_keV": round(x_value + (cx - x_at) / x_scale, 1),
                       "phi_3.29_keV": round(y_value + (y_at - cy) / y_scale, 1)}
    return {"limit_sd_proton": log_curve(maroon, x_anchor, y_anchor),
            "fig6_best_fit_phi": {"units": "detected WIMPs per kg-day per pb", **best,
                                  "note": "calibrated from tick-label centres (about 1%)"}}


def deap3600_limit() -> dict:
    """Fig. 24 of arXiv:1902.04048: this work (red; the caption says blue) and DarkSide-50 (2018)."""
    page = paper("1902.04048")[25]
    drawings = page.get_drawings()
    grey = [d for d in drawings if tuple(round(c, 2) for c in (d.get("color") or (9, 9, 9))) == (0.8, 0.8, 0.8)]
    verticals = [d["rect"].x0 for d in grey if d["rect"].width < 0.1]
    horizontals = [d["rect"].y0 for d in grey if d["rect"].height < 0.1]
    xs = decade_positions(verticals, {2: 163.8, 3: 224.3, 4: 284.8})
    ys = decade_positions(horizontals, {-47: 208.3, -42: 92.7})
    x_anchor = (xs[2], (xs[4] - xs[2]) / 2, 2)
    y_anchor = (ys[-47], (ys[-47] - ys[-42]) / 5, -47)
    colours = {"deap3600_this_work": (0.89, 0.1, 0.11), "darkside50_2018": (0.2, 0.63, 0.17)}
    out = {}
    for name, colour in colours.items():
        path = [d for d in drawings if d.get("color") and len(d["items"]) > 20
                and tuple(round(c, 2) for c in d["color"]) == colour][0]
        out[name] = log_curve(path, x_anchor, y_anchor)
    return out


def ticks(drawings: list, axis: str, at: float, window: tuple[float, float], major: float) -> list[float]:
    """Positions of the major tick marks along an axis (tick length about ``major`` points).

    ``axis`` 'y' finds horizontal ticks drawn at x ≈ ``at``; 'x' vertical ticks at y ≈ ``at``.
    """
    out = []
    for d in drawings:
        r = d["rect"]
        if axis == "y" and abs(r.x0 - at) < 2 and r.height < 0.2 and abs(r.width - major) < 0.2:
            out.append(r.y0)
        if axis == "x" and abs(r.y1 - at) < 3 and r.width < 0.2 and abs(r.height - major) < 0.2:
            out.append(r.x0)
    return sorted(v for v in set(round(v, 3) for v in out) if window[0] <= v <= window[1])


def lz_fig1() -> dict:
    """Fig. 1 of arXiv:2609.02823: LZ's recoil spectra for inelastic O1s and for L10s."""
    page = paper("2609.02823")[2]
    drawings = page.get_drawings()
    x_major = ticks(drawings, "x", 177.41, (340.0, 560.0), 3.03)      # 0, 50, ..., 350 keV
    kev_per_pt = 350.0 / (x_major[-1] - x_major[0])
    y_major = ticks(drawings, "y", 348.85, (50.0, 300.0), 3.03)
    top = [y for y in y_major if y < 178]                              # 10^9 ... 10^-1, 2 decades apart
    bottom = [y for y in y_major if y > 200]                           # 10^-1, 10^-2, 10^-3
    top_decades = (top[-1] - top[0]) / (2 * (len(top) - 1))
    bottom_decades = (bottom[-1] - bottom[0]) / (len(bottom) - 1)
    boundary = top[-1]                                                 # the panels meet here

    def curve(drawing: dict, y0: float, per_decade: float, exponent0: float, keep) -> dict:
        v = polyline(drawing)
        v = v[[keep(y) for y in v[:, 1]]]
        energies = (v[:, 0] - x_major[0]) * kev_per_pt
        rates = 10.0 ** (exponent0 - (v[:, 1] - y0) / per_decade)
        return {"energy_kev": [round(float(e), 3) for e in energies],
                "rate_per_tonne_year_kev": [float(f"{r:.4g}") for r in rates]}

    colours = {"O1s_delta_0_keV_m_1000": (0.12, 0.47, 0.71), "O1s_delta_200_keV_m_1000": (1.0, 0.5, 0.05),
               "O1s_delta_300_keV_m_1000": (0.17, 0.63, 0.17), "L10s_m_50": (0.84, 0.15, 0.16),
               "L10s_m_200": (0.58, 0.4, 0.74), "L10s_m_1000": (0.55, 0.34, 0.29)}
    out = {}
    for name, colour in colours.items():
        path = [d for d in drawings if d.get("color") and len(d["items"]) > 100
                and tuple(round(c, 2) for c in d["color"]) == colour][0]
        if name.startswith("O1s"):
            out[name] = curve(path, top[-1], top_decades, -1.0, lambda y: y <= boundary)
        else:          # inside the lower panel: from the boundary down to its frame at 10^-3
            out[name] = curve(path, bottom[0], bottom_decades, -1.0,
                              lambda y: boundary <= y < bottom[-1] - 0.05)
    return {"spectra": out, "couplings": "c^s = 1/m_v^2 (O1s), d^s = 1/m_v^2 (L10s), m_v = 246.2 GeV",
            "halo": "the Standard Halo Model of arXiv:2105.00599", "rate_units": "events/(tonne year keV)"}


def lz_fig_s2() -> dict:
    """Fig. S2 of arXiv:2609.02823: the extended window's signal efficiency against recoil energy."""
    page = paper("2609.02823")[13]
    drawings = page.get_drawings()
    black = [d for d in drawings if tuple(round(c, 2) for c in (d.get("color") or (9, 9, 9))) == (0.0, 0.0, 0.0)
             and len(d["items"]) > 50 and d.get("width") and d["width"] > 0.9]
    main = [d for d in black if d["rect"].y0 < 100][0]          # the full curve, 0-300 keV
    inset = [d for d in black if d["rect"].y0 > 120][0]         # the 250-300 keV inset
    main_v, inset_v = polyline(main), polyline(inset)
    main_e = (main_v[:, 0] - 206.15) * (300.0 / (425.6 - 206.15))
    main_eff = (203.55 - main_v[:, 1]) / (203.55 - 62.65)
    inset_e = 250.0 + (inset_v[:, 0] - 243.45) * (50.0 / (357.6 - 243.45))
    inset_eff = (187.3 - inset_v[:, 1]) / (187.3 - 129.0)
    # only points inside each panel's frame; the drawn paths run past it
    keep_main = (main_e >= 0.0) & (main_e < 250.0) & (main_eff >= 0.0)
    keep_inset = (inset_e >= 250.0) & (inset_e <= 300.0) & (inset_eff >= 0.0) & (inset_eff <= 1.0)
    energies = np.concatenate([main_e[keep_main], inset_e[keep_inset]])
    efficiency = np.concatenate([main_eff[keep_main], inset_eff[keep_inset]])
    order = np.argsort(energies)
    return {"energy_kev": [round(float(e), 2) for e in energies[order]],
            "efficiency": [round(float(max(0.0, x)), 4) for x in efficiency[order]],
            "note": "below 250 keV the main panel; from 250 keV the inset, which the paper draws "
                    "at higher resolution. The paper quotes 50% at 5.4 keV and at 269.9 keV."}


def _log_axis(ticks: dict[float, float]) -> tuple[float, float]:
    """(slope, offset) of log10(value) = slope × point + offset, from drawn major ticks {point: log10 value}."""
    return linear_map(list(ticks), list(ticks.values()))


def pandax4t_sd() -> dict:
    """Figs. 4 and 5 of arXiv:2408.00664: Run0+Run1's SD-neutron and SD-proton limits (thick solid red) and
    median sensitivities (thick dashed red), each calibrated from its own drawn major ticks."""
    document = paper("2408.00664")
    page = document[7]
    drawings = page.get_drawings()
    panels = {"sd_neutron": {"rows": (0, 300), "x": {106.84: 1, 166.83: 2, 226.83: 3, 286.82: 4},
                             "y": {59.6: -38, 96.7: -39, 133.8: -40, 170.8: -41, 207.9: -42}},
              "sd_proton": {"rows": (300, 520), "x": {107.25: 1, 167.11: 2, 226.97: 3, 286.82: 4},
                            "y": {364.82: -37, 401.41: -38, 438.0: -39, 474.56: -40}}}
    out = {"pdf_sha256": __import__("hashlib").sha256(Path(document.name).read_bytes()).hexdigest()}
    for kind, panel in panels.items():
        xs, ys = _log_axis(panel["x"]), _log_axis(panel["y"])
        red = [d for d in drawings if d.get("color") == (1.0, 0.0, 0.0) and abs((d.get("width") or 0) - 1.27) < 0.01
               and panel["rows"][0] < d["rect"].y0 < panel["rows"][1] and len(d["items"]) >= 10]   # not the legend
        solid = [d for d in red if not d.get("dashes") or d["dashes"].startswith("[] ")]
        dashed = [d for d in red if d not in solid]
        if len(solid) != 1 or len(dashed) != 1:
            raise ValueError(f"{kind}: expected one solid and one dashed thick red path, found {len(solid)}, "
                             f"{len(dashed)}")
        for label, drawing in (("limit", solid[0]), ("median_sensitivity", dashed[0])):
            v = polyline(drawing)
            out[f"{kind}_{label}"] = {
                "mass_gev": [round(float(10 ** (xs[0] * x + xs[1])), 4) for x in v[:, 0]],
                "cross_section_cm2": [float(f"{10 ** (ys[0] * y + ys[1]):.4e}") for y in v[:, 1]]}
    return out


def write(name: str, source: str, figure: str, content: dict, note: str) -> None:
    """One digitised figure as YAML, with its provenance."""
    OUT.mkdir(parents=True, exist_ok=True)
    record = {"source": source, "figure": figure, "digitised_on": str(date.today()),
              "method": "vector coordinates of the drawn paths (PyMuPDF), axes calibrated from "
                        "tick-label centres; docs/dm3/digitise_figures.py",
              "note": note, **content}
    (OUT / f"{name}.yaml").write_text(yaml.safe_dump(record, sort_keys=False, width=100))
    print(f"wrote {name}.yaml")


FIGURES = ("pico60_2019_fig3", "pico60_2019_fig6_fig7", "deap3600_2019_fig24", "lz_2026_fig1", "lz_2026_figS2",
           "deap3600_2019_fig21", "pandax4t_2024_fig4_fig5")


def main() -> None:
    """Digitise every figure, or those named by --only."""
    import argparse
    parser = argparse.ArgumentParser(description="Digitise published figures from their vector data")
    parser.add_argument("--only", default="", help=f"figures, comma-separated: {', '.join(FIGURES)}")
    chosen = set(parser.parse_args().only.split(",")) if parser.parse_args().only else set(FIGURES)
    if chosen - set(FIGURES):
        raise SystemExit(f"unknown figures {sorted(chosen - set(FIGURES))}")
    if "pandax4t_2024_fig4_fig5" in chosen:
        write("pandax4t_2024_fig4_fig5", "PandaX-4T Collaboration, arXiv:2408.00664v2 (Phys. Rev. Lett. 134, 011805)",
              "Figs. 4 (SD-neutron) and 5 (SD-proton), the appendix", pandax4t_sd(),
              "Run0+Run1, 1.54 tonne-years. The thick solid red curve is 'this work' (the 90% CL limit); the thick "
              "dashed red curve its median sensitivity, as the captions say. SD structure factors of Klos et al. "
              "2013 (the paper's ref. [41]). Log axes calibrated from each panel's drawn major ticks.")
    chosen.discard("pandax4t_2024_fig4_fig5")
    if "pico60_2019_fig3" in chosen:
        write("pico60_2019_fig3", "PICO Collaboration, arXiv:1902.04031 (Phys. Rev. D 100, 022001)",
              "Fig. 3", pico60(),
              "Best-fit curves are piecewise linear in energy between efficiencies 0, 0.2, 0.5, 0.8, 1.")
    if "pico60_2019_fig6_fig7" in chosen:
        write("pico60_2019_fig6_fig7", "PICO Collaboration, arXiv:1902.04031 (Phys. Rev. D 100, 022001)",
              "Fig. 7 (SD-proton limit) and Fig. 6 (best-fit integrated efficiencies)", pico60_limit(),
              "Log axes calibrated from the drawn major ticks. The limit matches the paper's quoted "
              "2.5e-41 cm² at 25 GeV.")
    if "deap3600_2019_fig24" in chosen:
        write("deap3600_2019_fig24", "DEAP-3600 Collaboration, arXiv:1902.04048 (Phys. Rev. D 100, 022004)",
              "Fig. 24 (SI limits)", deap3600_limit(),
              "Log axes calibrated from the drawn grid. This work's curve is drawn red although the "
              "caption says blue; it matches the paper's quoted 3.9e-45 cm² (100 GeV) and "
              "1.5e-44 cm² (1 TeV). The DarkSide-50 curve is arXiv:1802.07198 as the figure shows it.")
    if "lz_2026_fig1" in chosen:
        write("lz_2026_fig1", "LZ Collaboration, arXiv:2609.02823", "Fig. 1 (recoil spectra)", lz_fig1(),
              "LZ's own spectra, computed with WimPyDD: a check of the rates and of the coupling "
              "normalisation of LZ's tables. Log axes calibrated from the drawn major ticks.")
    if "lz_2026_figS2" in chosen:
        write("lz_2026_figS2", "LZ Collaboration, arXiv:2609.02823 (supplement)", "Fig. S2 (signal efficiency)",
              lz_fig_s2(), "The total efficiency (the black '+ ROI' curve) of the extended window.")
    if "deap3600_2019_fig21" in chosen:
        write("deap3600_2019_fig21", "DEAP-3600 Collaboration, arXiv:1902.04048 (Phys. Rev. D 100, 022004)",
              "Fig. 21 (acceptance) and its top axis (recoil energy)", deap3600(),
              "Acceptance of the fiducial cut, and of the Fprompt and background-rejection cuts "
              "combined; the total acceptance is their product. The energy axis is the median "
              "photoelectron yield of a nuclear recoil, without resolution.")


if __name__ == "__main__":
    main()

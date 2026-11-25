"""Digitise CDMS-II's silicon analysis (arXiv:1304.4279) from the figures' vector data.

- **The efficiency (Fig. 1).** The figure draws the nuclear-recoil efficiency
  after each selection; the bottom, blue curve ("+Phonon Timing") is the final
  one. It is read as the vertices of its two drawn paths, not traced from an
  image (DM3's method, ``docs/dm3/digitise_figures.py``). The axes are
  calibrated by the drawn ticks: 0, 20, …, 100 keV and 0, 0.2, …, 1.
- **The surface events' energies (Fig. 3).** Every WIMP-search event passing the
  other criteria is a marker in the plane of normalised timing and normalised
  yield, coloured by recoil energy: 7–20, 20–30 and 30–100 keV. Counted here are
  those in the nuclear-recoil yield band (−1.8σ to +1.2σ) that fail the timing
  cut (timing < 0). This is the population the collaboration's pass-fail
  estimate of the leakage scales, so their energies give the shape of the 0.41
  misidentified surface events. The three candidates (in the band, timing > 0,
  all at 7–20 keV) check the reading.

Run from the repository root:

    uv run --with pymupdf python docs/dm10/digitise_cdms_si.py

It downloads the PDF into the tools folder and writes
adroit/experiments/data/digitised/cdms_ii_si_2013.yaml (Fig. 1) and
cdms_ii_si_2013_fig3.yaml (Fig. 3).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pymupdf
import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.config import get_settings  # noqa: E402

ARXIV = "1304.4279"
BLUE = (0.0, 0.0, 0.502)
OUT = ROOT / "adroit" / "experiments" / "data" / "digitised" / "cdms_ii_si_2013.yaml"
OUT_FIG3 = OUT.with_name("cdms_ii_si_2013_fig3.yaml")
FIG3_COLOURS = {(0.0, 0.0, 0.5): "7-20", (0.0, 0.0, 1.0): "20-30", (0.5, 0.5, 1.0): "30-100"}
YIELD_BAND = (-1.8, 1.2)


def paper() -> pymupdf.Document:
    path = get_settings().tools_dir / "papers" / f"{ARXIV}.pdf"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(f"https://arxiv.org/pdf/{ARXIV}v3", timeout=60,
                                headers={"User-Agent": "adroit (research software)"})
        response.raise_for_status()
        path.write_bytes(response.content)
    return pymupdf.open(path)


def axis(page: pymupdf.Page) -> tuple[np.ndarray, np.ndarray]:
    """(x of the ticks at 0…100 keV, y of the ticks at 0…1), from the drawn tick marks."""
    xs, ys = [], []
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] != "l":
                continue
            a, b = item[1], item[2]
            if abs(a.x - b.x) < 0.01 and 192.0 < min(a.y, b.y) and max(a.y, b.y) < 196.0:
                xs.append(a.x)                                    # a vertical tick on the energy axis
            if abs(a.y - b.y) < 0.01 and 343.0 < min(a.x, b.x) and max(a.x, b.x) < 346.5:
                ys.append(a.y)                                    # a horizontal tick on the efficiency axis
    return np.array(sorted(set(np.round(xs, 2)))), np.array(sorted(set(np.round(ys, 2)), reverse=True))


def fig3_axes(page: pymupdf.Page) -> tuple[np.ndarray, np.ndarray]:
    """(slope, intercept) of timing and of yield against page x and y, from the drawn ticks and their labels."""
    ticks_x, ticks_y = [], []
    for d in page.get_drawings():
        for item in d["items"]:
            if item[0] != "l":
                continue
            a, b = item[1], item[2]
            if abs(a.x - b.x) < 0.01 and 193.0 < min(a.y, b.y) and max(a.y, b.y) < 197.0 and 340 < a.x < 560:
                ticks_x.append(a.x)
            if abs(a.y - b.y) < 0.01 and 346.0 < min(a.x, b.x) and max(a.x, b.x) < 349.0:
                ticks_y.append(a.y)
    tx, ty = np.array(sorted(set(np.round(ticks_x, 2)))), np.array(sorted(set(np.round(ticks_y, 2))))
    words = page.get_text("words")
    xl = {float(w[4].replace("−", "-")): (w[0] + w[2]) / 2 for w in words
          if 198 < (w[1] + w[3]) / 2 < 205 and 335 < w[0] < 560 and w[4].lstrip("−").isdigit()}
    yl = {float(w[4].replace("−", "-")): (w[1] + w[3]) / 2 for w in words
          if 328 < (w[0] + w[2]) / 2 < 346 and 55 < (w[1] + w[3]) / 2 < 200 and w[4].lstrip("−").isdigit()}
    xv, xp = zip(*[(v, tx[np.argmin(abs(tx - c))]) for v, c in xl.items()])
    yv, yp = zip(*[(v, ty[np.argmin(abs(ty - c))]) for v, c in yl.items()])
    return np.polyfit(xp, xv, 1), np.polyfit(yp, yv, 1)


def surface_events() -> dict:
    """Fig. 3: events in the nuclear-recoil yield band, failing and passing the timing cut, by energy range."""
    page = paper()[2]
    (kx, cx), (ky, cy) = fig3_axes(page)
    out = {name: {"fail": 0, "pass": 0} for name in FIG3_COLOURS.values()}
    for d in page.get_drawings():
        name = FIG3_COLOURS.get(tuple(round(x, 3) for x in (d.get("fill") or ())))
        r = d["rect"]
        if name is None or not (346 < r.x0 < 556 and 60 < r.y0 < 197):
            continue
        timing, yield_ = kx * (r.x0 + r.x1) / 2 + cx, ky * (r.y0 + r.y1) / 2 + cy
        if YIELD_BAND[0] <= yield_ <= YIELD_BAND[1]:
            out[name]["fail" if timing < 0 else "pass"] += 1
    return out


def write_fig3() -> None:
    counts = surface_events()
    OUT_FIG3.write_text(yaml.safe_dump({
        "source": f"arXiv:{ARXIV} (CDMS II, PRL 111 (2013) 251301), Fig. 3",
        "method": ("markers counted in the nuclear-recoil yield band (-1.8 to +1.2 sigma), by colour "
                   "(recoil energy) and side of the timing cut; axes from the drawn ticks"),
        "edges_kev": [7.0, 20.0, 30.0, 100.0],
        "surface_events_failing_timing": [counts[k]["fail"] for k in ("7-20", "20-30", "30-100")],
        "candidates_passing_timing": [counts[k]["pass"] for k in ("7-20", "20-30", "30-100")],
    }, sort_keys=False, default_flow_style=None))
    print(f"Fig. 3, in the yield band: {counts}")


def main() -> None:
    write_fig3()
    page = paper()[1]
    tx, ty = axis(page)
    words = page.get_text("words")
    # each axis label snapped to its nearest drawn tick
    x_labels = {float(w[4]): (w[0] + w[2]) / 2 for w in words
                if w[4] in ("0", "20", "40", "60", "80", "100") and 198 < (w[1] + w[3]) / 2 < 205}
    y_labels = {float(w[4]): (w[1] + w[3]) / 2 for w in words
                if w[4] in ("0", "0.2", "0.4", "0.6", "0.8", "1") and 330 < (w[0] + w[2]) / 2 < 343}
    xv, xp = zip(*[(v, tx[np.argmin(abs(tx - c))]) for v, c in x_labels.items()])
    yv, yp = zip(*[(v, ty[np.argmin(abs(ty - c))]) for v, c in y_labels.items()])
    kx, cx = np.polyfit(xp, xv, 1)
    ky, cy = np.polyfit(yp, yv, 1)
    points = []
    for d in page.get_drawings():
        if d.get("color") and np.allclose(d["color"], BLUE, atol=0.01) and len(d["items"]) > 50:
            for item in d["items"]:
                points += [(p.x, p.y) for p in item[1:] if hasattr(p, "x")]
    xy = np.array(sorted(set(points)))
    e, eff = kx * xy[:, 0] + cx, ky * xy[:, 1] + cy
    keep = np.concatenate([[True], np.diff(e) > 1e-6])
    content = {"recoil_energy_kev": np.round(e[keep], 4).tolist(),
               "efficiency": np.round(np.clip(eff[keep], 0.0, 1.0), 4).tolist()}
    OUT.write_text(yaml.safe_dump({
        "source": f"arXiv:{ARXIV} (CDMS II, PRL 111 (2013) 251301), Fig. 1, the '+Phonon Timing' curve",
        "method": "the vertices of the drawn path; axes from the drawn ticks (0-100 keV, 0-1)",
        **content}, sort_keys=False, default_flow_style=None))
    print(f"{len(content['efficiency'])} points, {content['recoil_energy_kev'][0]:.2f}–"
          f"{content['recoil_energy_kev'][-1]:.2f} keV, efficiency at 10 and 50 keV: "
          f"{np.interp(10, e[keep], eff[keep]):.3f}, {np.interp(50, e[keep], eff[keep]):.3f}")


if __name__ == "__main__":
    main()

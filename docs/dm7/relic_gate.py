"""DM7 gate, part 1: the thermal-relic contours of CMS's summary (arXiv:2405.13778, Figs. 11, 12).

The rule was fixed in docs/dm7_constraints.md (section 1) before this was
first run. For each model the published Ωh² = 0.12 contour is resampled at
100 points equally spaced along its drawn length (all its pieces together).
A point passes if the system's Ωh² there is within a factor 1.3 of 0.12, or
if the system's own 0.12 contour passes within 3% of it in m_med or in m_DM
(Ωh² − 0.12 changes sign between the point and a point 3% away along either
axis). A model passes with at least 90% of its points. The gate models are
V1, A1 and A2; V2 is reported beside them.

Run from the repository root (about 5 minutes; two workers, low priority):

    nice -n 10 uv run python docs/dm7/relic_gate.py

Writes relic_gate.json and relic_gate.txt to a new runs/gates/dm7/<UTC> folder
unless --out names one (docs/dm7 only to re-record the tracked receipts). Exit
code: 0 when the gate is met, 1 when it is not.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.constraints import annihilation, spin1  # noqa: E402
from adroit.core.receipts import add_out_argument, exit_code, gate_output  # noqa: E402

DIGITISED = ROOT / "adroit/constraints/data/digitised/cms_2405.13778_spin1.yaml"
MODELS = ("V1", "A1", "A2", "V2")
GATE = ("V1", "A1", "A2")
TARGET, FACTOR, SHIFT, POINTS, FRACTION = 0.12, 1.3, 0.03, 100, 0.9


def to_page(point: list[float], cal: dict[str, float]) -> tuple[float, float]:
    """[m_med, m_DM] → page points, inverting the panel's calibration."""
    return ((math.log10(point[0]) - cal["x_offset"]) / cal["x_slope"],
            (point[1] - cal["y_offset"]) / cal["y_slope"])


def resample(lines: list[list[list[float]]], cal: dict[str, float], n: int) -> list[list[float]]:
    """n points equally spaced along the drawn length of all the pieces together."""
    segments = []
    for line in lines:
        page = np.array([to_page(p, cal) for p in line])
        data = np.array(line, dtype=float)
        for i in range(len(line) - 1):
            segments.append((page[i], page[i + 1], data[i], data[i + 1]))
    lengths = np.array([np.linalg.norm(b - a) for a, b, _, _ in segments])
    cumulative = np.concatenate([[0.0], np.cumsum(lengths)])
    out = []
    for target in (np.arange(n) + 0.5) / n * cumulative[-1]:
        i = min(int(np.searchsorted(cumulative, target, side="right")) - 1, len(segments) - 1)
        t = (target - cumulative[i]) / lengths[i] if lengths[i] > 0 else 0.0
        _, _, d0, d1 = segments[i]
        m_med = 10 ** ((1 - t) * math.log10(d0[0]) + t * math.log10(d1[0]))
        out.append([float(m_med), float((1 - t) * d0[1] + t * d1[1])])
    return out


def evaluate(task: tuple[str, float, float]) -> dict:
    """Ωh² at the point and at the four points 3% away along each axis."""
    name, m_med, m_dm = task

    def omega(med: float, dm: float) -> float:
        return annihilation.omega_h2(spin1.benchmark(name, med), dm)
    centre = omega(m_med, m_dm)
    shifted = {"m_med-": omega(m_med * (1 - SHIFT), m_dm), "m_med+": omega(m_med * (1 + SHIFT), m_dm),
               "m_dm-": omega(m_med, m_dm * (1 - SHIFT)), "m_dm+": omega(m_med, m_dm * (1 + SHIFT))}
    within = TARGET / FACTOR <= centre <= TARGET * FACTOR
    crosses = any((centre - TARGET) * (v - TARGET) <= 0 for v in shifted.values())
    return {"model": name, "m_med": m_med, "m_dm": m_dm, "omega_h2": centre, "shifted": shifted,
            "within_factor": within, "contour_within_3pct": crosses, "passes": within or crosses}


def model_passes(results: list[dict], name: str) -> bool:
    """A model passes with at least ``FRACTION`` of its points."""
    rows = [r for r in results if r["model"] == name]
    return bool(rows) and sum(r["passes"] for r in rows) >= FRACTION * len(rows)


def summary(results: list[dict]) -> str:
    """The text record."""
    lines = ["DM7 gate part 1: CMS's thermal-relic contours (arXiv:2405.13778, Figs. 11, 12)",
             f"rule: Ωh² within ×{FACTOR} of {TARGET}, or the system's contour within {SHIFT:.0%} "
             f"in m_med or m_DM; ≥ {FRACTION:.0%} of {POINTS} points per model", ""]
    verdicts = {}
    for name in MODELS:
        rows = [r for r in results if r["model"] == name]
        passed = sum(r["passes"] for r in rows)
        ratios = np.array([r["omega_h2"] / TARGET for r in rows])
        verdicts[name] = passed >= FRACTION * len(rows)
        lines.append(f"{name}{' (gate)' if name in GATE else ' (reported)'}: {passed}/{len(rows)} pass "
                     f"({sum(r['within_factor'] for r in rows)} within ×{FACTOR}); "
                     f"Ωh²/0.12 median {np.median(ratios):.3f}, range {ratios.min():.3f}–{ratios.max():.3f}")
        for r in rows:
            if not r["passes"]:
                lines.append(f"    fails at m_med = {r['m_med']:.1f}, m_DM = {r['m_dm']:.1f}: "
                             f"Ωh² = {r['omega_h2']:.4f}")
    met = all(verdicts[name] for name in GATE)
    lines += ["", f"gate part 1 {'met' if met else 'NOT met'}: " +
              ", ".join(f"{n} {'passes' if verdicts[n] else 'fails'}" for n in GATE)]
    return "\n".join(lines)


def main() -> int:
    """Resample, evaluate and write the record; returns the exit code."""
    parser = argparse.ArgumentParser(description="DM7 gate, part 1")
    add_out_argument(parser, "dm7")
    folder = gate_output("dm7", parser.parse_args().out)
    record = yaml.safe_load(DIGITISED.read_text())
    tasks = []
    for name in MODELS:
        panel = record["panels"][name]
        for m_med, m_dm in resample(panel["relic"], panel["calibration"], POINTS):
            tasks.append((name, m_med, m_dm))
    with ProcessPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(evaluate, tasks, chunksize=4))
    (folder / "relic_gate.json").write_text(json.dumps(results, indent=1))
    text = summary(results)
    (folder / "relic_gate.txt").write_text(text + "\n")
    print(text)
    print(f"written to {folder}")
    return exit_code(all(model_passes(results, name) for name in GATE))


if __name__ == "__main__":
    sys.exit(main())

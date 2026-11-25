"""The external audit's item 19: two records' stored values against HEPData, value by value (network; $0).

- ``atlas-1910.08447-dijet-gaussian``: HEPData ins1759712 v1, Table 15 (the observed Gaussian limits, by width) and
  Table 20 (the DM Z′'s acceptance, by g_q);
- ``lmu-ltau-babar-belle2``: Belle II's limits, HEPData ins2611344 v1, "Fig. 3 (top left)", the observed column.

HEPData limits its request rate, so the tables are fetched apart. Exit 0 when every stored value is identical to
HEPData's, 1 otherwise. Usage: ``uv run python scripts/compare_hepdata_records.py [--keep DIR]``.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "madgraph_xsec"))
from hepdata_tools import download_table  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "adroit" / "constraints" / "data" / "digitised"
TABLES = [(1759712, "Table 15", "json"), (1759712, "Table 20", "json"), (2611344, "Fig. 3 (top left)", "yaml")]


def fetch(folder: Path) -> dict[str, Path]:
    """Each table, spaced and retried (HEPData answers 429 when asked too fast)."""
    paths = {}
    for k, (inspire, name, fmt) in enumerate(TABLES):
        for attempt in range(4):
            try:
                paths[name] = download_table(inspire, name, folder, fmt, version=1)
                json.loads(paths[name].read_text()) if fmt == "json" else yaml.safe_load(paths[name].read_text())
                break
            except Exception:  # noqa: BLE001 - a rate limit or a truncated download: wait and retry
                if attempt == 3:
                    raise
                time.sleep(60)
        if k < len(TABLES) - 1:
            time.sleep(20)
    return paths


def _columns(path: Path) -> tuple[list[float], dict[str, list]]:
    d = json.loads(path.read_text())
    labels = [q["value"] for group in d["qualifiers"].values() for q in group if q["type"] in ("Limit", "EFF")]
    xs = [float(v["x"][0]["value"]) * 1000.0 for v in d["values"]]
    return xs, {label: [v["y"][i]["value"] for v in d["values"]] for i, label in enumerate(labels)}


def _compare(stored: list, xs: list[float], column: list) -> tuple[int, int]:
    hep = {round(x, 6): float(v) for x, v in zip(xs, column) if v not in ("-", None)}
    rows = [(round(x, 6), y) for x, y in stored if y is not None]
    same = sum(1 for x, y in rows if hep.get(x) == y)
    return same, len(rows) - same + len(set(hep) - {x for x, _ in rows})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep", type=Path, help="keep the downloaded tables in this folder")
    args = parser.parse_args()
    folder = args.keep or Path(tempfile.mkdtemp(prefix="adroit-hepdata-"))
    paths = fetch(folder)
    dijet = yaml.safe_load((DATA / "atlas_1910.08447_dijet_gaussian.yaml").read_text())
    same = differ = 0
    xs, cols = _columns(paths["Table 15"])
    for width, stored in dijet["gaussian_limits"].items():
        s, d = _compare(stored, xs, cols[f"Observed {float(width):g}% width"])
        print(f"Table 15, observed, σ_G/m = {float(width):g}%: {s} identical, {d} differ or missing")
        same, differ = same + s, differ + d
    xs, cols = _columns(paths["Table 20"])
    for g, stored in dijet["zprime_acceptance"].items():
        s, d = _compare(stored, xs, cols[f"DM Z' gq {round(100 * float(g)):d}"])
        print(f"Table 20, g_q = {g}: {s} identical, {d} differ or missing")
        same, differ = same + s, differ + d
    belle = yaml.safe_load((DATA / "belle2_2212.03066_invisible_zprime.yaml").read_text())["points"]
    fig = {v["header"]["name"]: [x.get("value") for x in v["values"]]
           for v in yaml.safe_load(paths["Fig. 3 (top left)"].read_text())["dependent_variables"]}
    rows = list(zip(fig["$M_{Z'}$"], fig["$g'$, Observed"]))
    s = sum(1 for a, b in zip(rows, belle) if list(a) == list(b))
    d = len(belle) - s + abs(len(rows) - len(belle))
    print(f"Belle II Fig. 3 (top left), observed: {s} identical, {d} differ or missing")
    same, differ = same + s, differ + d
    print(f"total: {same} identical, {differ} differ or missing (tables in {folder})")
    return 0 if differ == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

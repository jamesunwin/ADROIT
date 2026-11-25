"""Direct-detection outcomes at the portal library's benchmarks, to list what a change does (R2's gate).

    uv run python scripts/dd_outcomes.py --out runs/r2/before.json     # with the code as it is
    uv run python scripts/dd_outcomes.py --out runs/r2/after.json
    uv run python scripts/dd_outcomes.py --compare runs/r2/before.json runs/r2/after.json

Each library entry is evaluated at its benchmark and at m_χ = 10, 100, 300 and 1000 GeV, with the benchmark's
couplings (and its mediator-to-dark-matter mass ratio, when it has one). For each point it records whether direct
detection excludes it, the channel that decides, σ, the limit, the ratio and the direct-detection pending reasons.
Only direct detection is computed ($0; the module procedures run locally and can take minutes per new mass).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MASSES = (10.0, 100.0, 300.0, 1000.0)
DD_KINDS = ("SI", "SD-proton", "SD-neutron")


def _legacy(cls, p) -> dict:
    """The comparison as scan.evaluate made it before R2: one channel, from ``dd``."""
    from adroit.parameter_space import limits, operator_limits
    kind, sigma = cls.dd(p)
    stat = limits.at95(kind, p.m_chi) if kind in DD_KINDS else None
    limit = stat.value if stat else None
    ratio = operator_limits.ratio95(kind, p.m_chi, sigma) if kind in operator_limits.STRUCTURES else None
    excluded = (None if ratio is None else ratio > 1.0) if limit is None else bool(sigma > limit)
    return {"excluded": excluded, "kind": kind, "sigma_cm2": sigma, "limit_cm2": limit,
            "ratio": (sigma / limit) if limit else ratio,
            "pending": sorted(f"direct detection ({n}): {w}" for n, w in (stat.omitted.items() if stat else []))}


def outcome(cls, p) -> dict:
    """The direct-detection outcome at one point, by whichever comparison the installed code makes."""
    from adroit.parameter_space import scan
    try:
        if hasattr(scan, "direct_detection"):
            d = scan.direct_detection(cls, p)
            return {"excluded": d.excluded, "kind": d.kind, "sigma_cm2": d.sigma_cm2, "limit_cm2": d.limit_cm2,
                    "ratio": d.ratio, "pending": sorted(d.pending),
                    "channels": [c.model_dump(mode="json", exclude={"limit"}) for c in d.channels]}
        return _legacy(cls, p)
    except Exception as error:          # noqa: BLE001 - a failure at a point is part of the record
        return {"error": f"{type(error).__name__}: {error}"[:300]}


def points(entry) -> list:
    """The benchmark, then the four masses."""
    out = [entry.point]
    for m in MASSES:
        m_med = m * entry.mediator_ratio if entry.mediator_ratio else entry.point.m_med
        out.append(entry.point.model_copy(update={"m_chi": m, "m_med": m_med}))
    return out


def run(out: Path) -> None:
    """Every entry's outcomes, written as JSON."""
    from adroit.parameter_space import library
    rows = []
    for entry in library.ENTRIES:
        for p in points(entry):
            rows.append({"entry": entry.id, "point": p.model_dump(), **outcome(entry.model_class, p)})
            print(entry.id, p.m_chi, rows[-1].get("excluded"), rows[-1].get("kind"), rows[-1].get("error", ""),
                  flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1, default=str) + "\n")


def compare(before: Path, after: Path) -> list[str]:
    """Every point whose outcome, deciding channel or pending reasons changed."""
    old, new = json.loads(before.read_text()), json.loads(after.read_text())
    lines = []
    for a, b in zip(old, new):
        if (a["entry"], a["point"]) != (b["entry"], b["point"]):
            raise ValueError("the two runs list different points")
        keys = ("excluded", "kind", "error")
        changed = [k for k in keys if a.get(k) != b.get(k)] + (["pending"] if a.get("pending") != b.get("pending") else [])
        ratio_a, ratio_b = a.get("ratio"), b.get("ratio")
        if ratio_a and ratio_b and abs(ratio_b / ratio_a - 1.0) > 1e-6:
            changed.append("ratio")
        if changed:
            lines.append(f"| {a['entry']} | {a['point']['m_chi']:g} | {a.get('excluded')} → {b.get('excluded')} | "
                         f"{a.get('kind')} → {b.get('kind')} | {_ratio(ratio_a)} → {_ratio(ratio_b)} | "
                         f"{'; '.join(sorted(set(b.get('pending', [])) - set(a.get('pending', []))))[:160]} |")
    return lines


def _ratio(value) -> str:
    return "—" if value is None else f"{value:.3g}"


def main() -> int:
    """Run or compare."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--compare", nargs=2, type=Path)
    args = parser.parse_args()
    if args.compare:
        lines = compare(*args.compare)
        print("| entry | m_χ | excluded | deciding channel | ratio | new pending |\n|---|---|---|---|---|---|")
        print("\n".join(lines) or "| (no change) | | | | | |")
        return 0
    run(args.out or ROOT / "runs" / "dd_outcomes.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

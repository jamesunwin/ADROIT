"""The 25-portal acceptance: Track 1's verdict on every portal-library entry, crossing by crossing (R3's gate).

    uv run python scripts/portal_acceptance.py --out runs/r3/after.json            # with the code as it is
    uv run python scripts/portal_acceptance.py --out runs/r3/after.json --only b_minus_l wino
    uv run python scripts/portal_acceptance.py --compare runs/r3/before.json runs/r3/after.json

Each entry is run as the portal gate's P4 runs it (``docs/portals/gate.py``): its own plane on an 8 × 8 grid,
without the literature step ($0). For every crossing of the relic contour it records the point, the status
(viable, pending or excluded), what excludes it and what is pending, so that a change can be checked by hand
against the printed constraints. Entries already in ``--out`` are kept (a stopped run resumes).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def crossing_row(c) -> dict:
    """One crossing: its point, status and reasons."""
    p = c.point
    return {"point": {k: getattr(p, k) for k in ("m_chi", "m_med", "g_chi", "g_q", "g_l")},
            "status": c.status, "excluded_by": list(c.excluded_by), "pending": list(c.pending)}


def run_entry(entry_id: str, scratch: Path) -> dict:
    """Track 1 on one entry, as P4 runs it."""
    from adroit.orchestrator import track1
    from adroit.parameter_space import library
    e = library.entry(entry_id)
    started = time.time()
    request = track1.for_portal(e.id, x=e.x.model_copy(update={"n": 8}), y=e.y.model_copy(update={"n": 8}),
                                literature=False)
    try:
        result = track1.run(request, scratch / e.id)
        row = {"level": result.verdict.level, "crossings": [crossing_row(c) for c in result.verdict.crossings],
               "unresolved": result.verdict.unresolved}
    except Exception as error:                     # noqa: BLE001 - a failure is part of the record
        row = {"error": f"{type(error).__name__}: {error}"[:300]}
    row["seconds"] = round(time.time() - started, 1)
    return row


def counts(row: dict) -> dict:
    """Crossings by status."""
    return dict(Counter(c["status"] for c in row.get("crossings", [])))


def compare(before: dict, after: dict) -> str:
    """A markdown table of each entry's level and crossing counts, before and after, and the reasons that
    appeared or disappeared."""
    lines = ["| entry | level | viable | pending | excluded |", "|---|---|---|---|---|"]
    gone, new = Counter(), Counter()
    for entry in after:
        b, a = before.get(entry, {}), after[entry]
        cb, ca = counts(b), counts(a)
        level = a.get("level", a.get("error", "?"))
        if b.get("level", b.get("error")) != level:
            level = f"{b.get('level', b.get('error', '—'))} → {level}"
        cells = [f"{cb.get(s, 0)} → {ca.get(s, 0)}" if cb.get(s, 0) != ca.get(s, 0) else str(ca.get(s, 0))
                 for s in ("viable", "pending", "excluded")]
        lines.append(f"| {entry} | {level} | " + " | ".join(cells) + " |")
        reasons_b = Counter(r for c in b.get("crossings", []) for r in c["pending"] + c["excluded_by"])
        reasons_a = Counter(r for c in a.get("crossings", []) for r in c["pending"] + c["excluded_by"])
        gone.update({f"{entry}: {r}": n for r, n in (reasons_b - reasons_a).items()})
        new.update({f"{entry}: {r}": n for r, n in (reasons_a - reasons_b).items()})
    lines += ["", "**Reasons that disappeared (count of crossings):**", ""]
    lines += [f"- {r} ({n})" for r, n in sorted(gone.items())] or ["- none"]
    lines += ["", "**Reasons that appeared:**", ""]
    lines += [f"- {r} ({n})" for r, n in sorted(new.items())] or ["- none"]
    return "\n".join(lines)


def main() -> int:
    """Run or compare; returns the exit code (0, or 1 if an entry failed)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, help="the JSON file to write (and resume from)")
    parser.add_argument("--only", nargs="*", default=None, help="entry ids (default: all 25)")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()
    if args.compare:
        print(compare(*(json.loads(p.read_text()) for p in args.compare)))
        return 0
    if args.out is None:
        parser.error("--out or --compare is needed")
    from adroit.parameter_space import library
    rows = json.loads(args.out.read_text()) if args.out.exists() else {}
    ids = args.only or [e.id for e in library.ENTRIES]
    with tempfile.TemporaryDirectory() as scratch:
        for n, entry_id in enumerate(ids, start=1):
            if entry_id in rows:
                continue
            print(f"{entry_id} ({n}/{len(ids)})", flush=True)
            rows[entry_id] = run_entry(entry_id, Path(scratch))
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(rows, indent=1, default=str))
            print(f"  {rows[entry_id].get('level', rows[entry_id].get('error'))}: {counts(rows[entry_id])}, "
                  f"{rows[entry_id]['seconds']} s", flush=True)
    return 1 if any("error" in r for r in rows.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())

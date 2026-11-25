"""Re-judge recorded acceptance crossings (and the multiplets' thermal points) with whichever adroit is importable.

    uv run python scripts/acceptance_rejudge.py --out OUT.json --from ACCEPTANCE.json --entries a b ... \
        [--all-crossings] [--multiplets]

To judge with an older tree, run it with that tree first on PYTHONPATH (from the tree's folder).

Constraints do not move the relic contour, so a crossing recorded by an earlier full run is the same point now; its
status under the current constraints is what a full re-run would report. Each point is judged with the default
(verified) records and with unverified records allowed. Resumes from OUT.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from adroit.orchestrator import track1
from adroit.parameter_space import library
from adroit.parameter_space.classify import classify
from adroit.parameter_space.verdict import judge_point


def setup(entry_id: str):
    e = library.entry(entry_id)
    req = track1.for_portal(e.id, x=e.x.model_copy(update={"n": 8}), y=e.y.model_copy(update={"n": 8}),
                            literature=False)
    cls, fixed = req.model_class, req.fixed
    if cls is None or fixed is None:
        found, point, _ = classify(req.spec)
        cls, fixed = cls or found, fixed or point
    return e, cls, fixed


def judge(cls, p, unverified: bool) -> dict:
    started = time.time()
    try:
        c = judge_point(cls, p, unverified=unverified)
        return {"status": c.status, "excluded_by": list(c.excluded_by), "pending": list(c.pending),
                "seconds": round(time.time() - started, 1)}
    except Exception as error:  # noqa: BLE001 - recorded
        return {"error": f"{type(error).__name__}: {error}"[:300], "seconds": round(time.time() - started, 1)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--from", dest="source", type=Path)
    parser.add_argument("--entries", nargs="*", default=[])
    parser.add_argument("--all-crossings", action="store_true")
    parser.add_argument("--multiplets", action="store_true")
    args = parser.parse_args()
    rows = json.loads(args.out.read_text()) if args.out.exists() else {}
    jobs = []
    if args.source:
        recorded = json.loads(args.source.read_text())
        for entry_id in args.entries:
            for i, c in enumerate(recorded[entry_id].get("crossings", [])):
                if args.all_crossings or c["status"] != "excluded":
                    jobs.append((entry_id, f"{entry_id}#{i}", c["point"], c["status"]))
    if args.multiplets:
        for entry_id in ("wino", "higgsino"):
            e = library.entry(entry_id)
            for g in (e.y.low, (e.y.low + e.y.high) / 2, e.y.high):
                jobs.append((entry_id, f"{entry_id}@g_q={g:g}", {"m_chi": e.point.m_chi, "g_q": g}, None))
    cache = {}
    for entry_id, key, point, before in jobs:
        if key in rows:
            continue
        if entry_id not in cache:
            cache[entry_id] = setup(entry_id)
        _, cls, fixed = cache[entry_id]
        p = fixed.model_copy(update=point)
        rows[key] = {"entry": entry_id, "point": point, "recorded_status": before,
                     "default": judge(cls, p, False), "unverified": judge(cls, p, True)}
        args.out.write_text(json.dumps(rows, indent=1, default=str))
        print(key, rows[key]["default"].get("status", "error"), rows[key]["unverified"].get("status", "error"),
              rows[key]["default"]["seconds"] + rows[key]["unverified"]["seconds"], "s", flush=True)


if __name__ == "__main__":
    main()

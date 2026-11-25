"""R10's gate: a Track 1 scan with the precomputed limit tables against the same scan with every limit direct.

Runs ``adroit track1`` twice on the same plane (two workers, no literature search): first with the tables, then with
``--exact-limits``; times both, and compares every grid point's verdict per constraint and every thermal-contour
crossing (its status, what excludes it, and which constraints leave it pending). Ratios may differ within a table's
stated accuracy; verdicts may not. Writes docs/r10/gate_<label>.json and prints a summary.

    uv run python docs/r10/gate.py LABEL "--portal higgs_portal_scalar --x m_chi:11:9000:log:4 --y g_chi:1e-5:10:log:4"

Choose axes whose masses DIAMX has not seen, so that the direct run's time is a cold run's.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent


def run(arguments: list[str], out: Path) -> tuple[float, dict]:
    start = time.time()
    subprocess.run(["uv", "run", "adroit", "track1", *arguments, "--no-literature", "--out", str(out)], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL)
    return time.time() - start, json.loads((out / "result.json").read_text())


def _reasons(pending: list[str]) -> list[str]:
    """The constraints named by pending reasons, without their numbers (ratios move within a table's accuracy)."""
    return sorted({reason.split(":")[0].split(" (")[0] for reason in pending})


def verdicts(result: dict) -> dict:
    """What must be identical: each grid point's verdict per constraint and pending constraints, and the contour."""
    points = [{"point": p["point"], "excluded": p["excluded"], "pending": _reasons(p.get("pending", []))}
              for p in result["scan"]["points"]]
    verdict = result.get("verdict") or {}
    crossings = [{"point": c["point"], "status": c["status"], "excluded_by": sorted(c.get("excluded_by", [])),
                  "pending": _reasons(c.get("pending", []))} for c in verdict.get("crossings", [])]
    return {"level": verdict.get("level"), "points": points, "crossings": crossings}


def main(argv: list[str]) -> int:
    label, arguments = argv[0], shlex.split(argv[1])
    work = ROOT / "runs" / "r10_gate" / label
    tabulated_s, tabulated = run(arguments, work / "tabulated")
    exact_s, exact = run([*arguments, "--exact-limits"], work / "exact")
    a, b = verdicts(tabulated), verdicts(exact)
    differing = [i for i, (p, q) in enumerate(zip(a["points"], b["points"])) if p != q]
    crossings_equal = a["crossings"] == b["crossings"] and a["level"] == b["level"]
    notes = [n for n in tabulated["scan"].get("notes", []) if "precomputed tables" in n]
    summary = {"label": label, "arguments": arguments, "points": len(a["points"]), "tabulated_s": round(tabulated_s),
               "exact_s": round(exact_s), "speedup": round(exact_s / tabulated_s, 2), "level": a["level"],
               "points_differing": differing, "crossings_identical": crossings_equal, "tables_note": notes,
               "pass_identical": not differing and crossings_equal}
    (HERE / f"gate_{label}.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0 if summary["pass_identical"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

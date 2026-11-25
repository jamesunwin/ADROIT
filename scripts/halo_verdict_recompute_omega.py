"""Recompute Ωh² at the verdict study's crossings whose first Boltzmann solve had stopped short (Ωh² outside 0.08–0.2
on the old 0.12 contour), with the code of the checkout it runs from (the relic fix, e1389a2: a stalled solve retries,
else raises RelicUnresolved). Run from the main checkout after it is fast-forwarded:

    OMP_NUM_THREADS=2 nice -n 10 uv run python recompute_omega.py verdict_study.json OUT.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path.cwd()


def main() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from acceptance_rejudge import setup
    from adroit.constraints.relic import RelicUnresolved
    rows = json.loads(Path(sys.argv[1]).read_text())
    out = {}
    for key, row in sorted(rows.items()):
        old = row["published"].get("omega_h2")
        if not isinstance(old, (int, float)) or 0.08 < old < 0.2:
            continue
        _, cls, fixed = setup(row["entry"])
        p = fixed.model_copy(update=row["point"])
        try:
            new = cls.omega_h2(p)
            out[key] = {"old": old, "new": new}
        except RelicUnresolved as error:
            out[key] = {"old": old, "new": None, "why": str(error)[:300]}
        print(key, out[key], flush=True)
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

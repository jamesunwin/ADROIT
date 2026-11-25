"""The physics-extensions verdict-change study: every recorded acceptance crossing (R3's 22 portals,
docs/receipts/r3/acceptance_after.json; the points R9's gate re-judged) judged now with each experiment's published
halo and over the preset halo region, and its Ωh² under the new relic table (the crossing was on the old Ωh² = 0.12
contour). Two worker processes; resumes from OUT.

    OMP_NUM_THREADS=2 nice -n 10 uv run python scripts/halo_verdict_study.py OUT.json
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path.cwd()


def _setup(entry_id: str):
    sys.path.insert(0, str(ROOT / "scripts"))
    from acceptance_rejudge import setup
    return setup(entry_id)


def _judge(job: tuple) -> tuple[str, dict]:
    entry_id, key, point, recorded = job
    from adroit.parameter_space import halo_region
    from adroit.parameter_space.verdict import judge_point
    _, cls, fixed = _setup(entry_id)
    p = fixed.model_copy(update=point)
    out = {"entry": entry_id, "point": point, "recorded": recorded}
    for mode, preset in (("published", None), ("region", halo_region.HaloPreset())):
        started = time.time()
        try:
            with halo_region.using(preset):
                c = judge_point(cls, p)
            out[mode] = {"status": c.status, "excluded_by": list(c.excluded_by), "pending": list(c.pending)[:3],
                         "halo": c.halo, "nominal": c.nominal_status, "omega_h2": c.omega_h2,
                         "seconds": round(time.time() - started, 1)}
        except Exception as error:  # noqa: BLE001 - recorded
            out[mode] = {"error": f"{type(error).__name__}: {error}"[:300], "seconds": round(time.time() - started, 1)}
    return key, out


def main() -> None:
    out = Path(sys.argv[1])
    rows = json.loads(out.read_text()) if out.exists() else {}
    recorded = json.loads((ROOT / "docs" / "receipts" / "r3" / "acceptance_after.json").read_text())
    jobs = [(entry, f"{entry}#{i}", c["point"], c["status"]) for entry, data in recorded.items()
            for i, c in enumerate(data.get("crossings", [])) if f"{entry}#{i}" not in rows]
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_judge, job) for job in jobs]
        for future in as_completed(futures):
            key, row = future.result()
            rows[key] = row
            out.write_text(json.dumps(rows, indent=1, default=str))
            print(key, row["recorded"], row["published"].get("status", "error"), row["region"].get("status", "error"),
                  row["region"].get("halo", ""), flush=True)


if __name__ == "__main__":
    main()

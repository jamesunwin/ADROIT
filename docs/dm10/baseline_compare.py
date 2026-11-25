"""DM10: the system and each direct-prompting run, scored on the same cases.

Reads the latest injection run and each direct-prompting run from
docs/dm10/results/, keeps the cases they share, and prints each reading by
target. Run from the repository root (seconds, no cost):

    uv run python docs/dm10/baseline_compare.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
KEYS = [("passed", "pairwise"), ("same_class", "class"), ("exact", "exact"), ("in_top_set", "set holds truth")]


def latest(path: Path) -> dict:
    return json.loads(path.read_text().splitlines()[-1])


def scores(results: list[dict]) -> dict[str, float]:
    out = {name: sum(bool(r["passed"] if k == "passed" else r["metrics"][k]) for r in results) / len(results)
           for k, name in KEYS}
    out["mean set size"] = statistics.mean(r["metrics"]["top_set_size"] for r in results)
    return out


def table() -> str:
    system = {r["case_id"]: r for r in latest(RESULTS / "injection.jsonl")["results"]}
    runs = {p.stem.removeprefix("direct_prompting_"): latest(p) for p in sorted(RESULTS.glob("direct_prompting_*.jsonl"))}
    lines = []
    for model, run in runs.items():
        cases = [r["case_id"] for r in run["results"] if r["case_id"] in system]
        targets = sorted({c.split("|")[0] for c in cases})
        lines += [f"## the system against {model}: {len(cases)} cases ({run['reason']})", "",
                  "| target | who | " + " | ".join(n for _, n in KEYS) + " | mean set size |",
                  "|---|---|" + "---|" * (len(KEYS) + 1)]
        for t in [*targets, "all"]:
            ids = [c for c in cases if t == "all" or c.startswith(t)]
            llm = {r["case_id"]: r for r in run["results"]}
            for who, rows in (("system", [system[c] for c in ids]), (model, [llm[c] for c in ids])):
                s = scores(rows)
                lines.append(f"| {t} | {who} | " + " | ".join(f"{s[n]:.2f}" for _, n in KEYS)
                             + f" | {s['mean set size']:.1f} |")
        invented = sum(r["metrics"]["invented"] for r in run["results"])
        lines += ["", f"Labels off the list: {invented} in {len(run['results'])} answers.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    print(table())

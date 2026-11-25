"""R10's table summary for docs/r10/README.md: one row per stored limit table, read from the package's YAML files.

    uv run python docs/r10/tables.py          # prints Markdown; $0, seconds

For each table: its mass range and count; the leave-one-out error (largest, and median); the local tolerance η
(``limit_tables.tolerance``) at a mass in the table's upper half, where it is typical; the mass intervals where η
exceeds 5% (a point there is computed directly unless its ratio to the limit is more than 5% from 1); and whether the
table is current for the installed code.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adroit.parameter_space import limit_tables  # noqa: E402


def row(data: dict) -> str:
    masses, errors = data["masses_gev"], [abs(e) for e in data["leave_one_out"]]
    grid = np.geomspace(masses[0], masses[-1], 800)
    large = [limit_tables.tolerance(data, m) > 0.05 for m in grid]
    spans, start = [], None
    for m, flag, nxt in zip(grid, large, [*large[1:], False]):
        start = m if flag and start is None else start
        if flag and not nxt:
            spans.append(f"{start:.3g}–{m:.3g}")
            start = None
    typical = math.sqrt(masses[len(masses) // 2] * masses[-1])
    exact = ", ".join(spans) or "none"
    current = limit_tables.table(data["module"], data["kind"]) is not None
    return (f"| {data['module']} | {data['kind']} | {masses[0]:.3g}–{masses[-1]:.4g} | {len(masses)} | "
            f"{max(errors):.2%} | {float(np.median(errors)):.2%} | {limit_tables.tolerance(data, typical):.2%} | "
            f"{exact} | {'yes' if current else 'no'} |")


def main() -> int:
    limit_tables.clear_cache()
    print("| module | kind | masses (GeV) | count | largest left-out error | median | η, upper half | "
          "η > 5% (GeV) | current |")
    print("|---|---|---|---|---|---|---|---|---|")
    for path in sorted(limit_tables.TABLES.glob("*.yaml")):
        print(row(yaml.safe_load(path.read_text())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

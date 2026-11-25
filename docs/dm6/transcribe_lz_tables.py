"""Transcribe LZ's Tables S7 and S8 (local significances) from the paper's PDF (DM6).

The DM6 validation rule is written against these tables of arXiv:2609.02823,
not against the HEPData record, which differs from them in places
(docs/dm4_library.md, section 4). The script reads the text of the PDF
fetched in DM3 and writes adroit/experiments/data/lz_2026_tables_S7_S8.yaml,
with every entry the paper prints: 520 for the Lagrangians and 92 for the
inelastic operators, whose four dashed entries (400 GeV, δ = 350 keV, not
physical) are omitted.

    uv run --with pymupdf python docs/dm6/transcribe_lz_tables.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.config import get_settings  # noqa: E402

PDF = get_settings().tools_dir / "papers" / "2609.02823.pdf"
OUT = ROOT / "adroit" / "experiments" / "data" / "lz_2026_tables_S7_S8.yaml"
MASSES = [10, 12, 14, 17, 21, 30, 40, 50, 100, 200, 400, 1000, 4000]
SPLITTINGS = [0, 50, 100, 150, 200, 250, 300, 350]


def text() -> str:
    import pymupdf
    return "".join(page.get_text() for page in pymupdf.open(PDF))


def table_s7(tokens: list[str]) -> dict[str, list[float]]:
    rows, i = {}, 0
    while i < len(tokens):
        if tokens[i] in ("Ls", "Lv") and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            values, k = [], i + 2
            while k < len(tokens) and len(values) < len(MASSES) and re.fullmatch(r"\d\.\d", tokens[k]):
                values.append(float(tokens[k]))
                k += 1
            if len(values) != len(MASSES):
                raise ValueError(f"row {tokens[i]} {tokens[i + 1]}: {len(values)} values")
            rows[f"L{int(tokens[i + 1]):02d}{tokens[i][1]}"] = values
            i = k
        else:
            i += 1
    return rows


def table_s8(tokens: list[str]) -> dict[str, dict[int, list[float | None]]]:
    rows, i = {}, 0
    while i < len(tokens):
        if tokens[i] in ("Os", "Ov") and i + 1 < len(tokens) and tokens[i + 1] in ("1", "4"):
            name, k = f"O{int(tokens[i + 1]):02d}{tokens[i][1]}", i + 2
            rows[name] = {}
            for _ in range(3):
                mass, k = int(tokens[k]), k + 1
                values = [None if t == "-" else float(t) for t in tokens[k:k + len(SPLITTINGS)]]
                rows[name][mass], k = values, k + len(SPLITTINGS)
            i = k
        else:
            i += 1
    return rows


def main() -> None:
    source = text()
    s7 = source[source.index("TABLE S7. Local significance for Lagrangian"):source.index("TABLE S8.")]
    s8 = source[source.index("TABLE S8. Local significance"):]
    lagrangians, operators = table_s7(s7.split()), table_s8(s8.split())
    entries = [{"model": name, "mass_gev": m, "splitting_kev": 0, "significance": v}
               for name, values in lagrangians.items() for m, v in zip(MASSES, values)]
    entries += [{"model": name, "mass_gev": m, "splitting_kev": d, "significance": v}
                for name, by_mass in operators.items() for m, values in by_mass.items()
                for d, v in zip(SPLITTINGS, values) if v is not None]
    OUT.write_text(yaml.safe_dump({
        "source": "LZ Collaboration, arXiv:2609.02823, supplement, Tables S7 and S8",
        "note": "local significance in standard deviations (one-sided), as printed; the four "
                "entries the paper marks as not physical (400 GeV, 350 keV) are omitted",
        "method": "read from the text of the PDF by docs/dm6/transcribe_lz_tables.py",
        "entries": entries}, sort_keys=False, width=100))
    print(f"{len(entries)} entries: {len(lagrangians)} Lagrangian rows, {len(operators)} operator rows")


if __name__ == "__main__":
    main()

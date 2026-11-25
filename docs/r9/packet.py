"""R9: the record-verification packet (docs/r9_record_verification.md), regenerated from the current records.

Run after any record edit, since each verify command pins the record's current scientific hash. It reads the
pre-check (docs/r9/precheck.md) and the portal dependencies (docs/r9/portal_dependencies.md); run those first when
the records' data or the portals change. $0, no network:

    uv run python docs/r9/precheck.py && uv run python docs/r9/packet.py
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).parent
OUT = ROOT / "docs" / "r9_record_verification.md"
SIGNER = "James Unwin (owner)"
RESIGN = ["cms-2405.13778-V1", "cms-2405.13778-A1", "cms-2405.13778-V2", "cms-2405.13778-A2", "icecube-1612.05949-sd",
          "icecube-1612.05949-si", "fermi-1503.02641-dsph", "lep-hep-ex-0509008-zinv",     # R4's corrections applied
          "atlas-2009.14791-zz", "atlas-2004.14636-ww", "atlas-1910.08447-dijet-gaussian",  # widths, 2026-10-12
          "atlas-2010.14293-squark"]                                                       # QCD-only, 2026-10-12
NOTES = {
    "muon-g2-2025": "The abstract prints the numbers in another form (×10⁻¹¹); read them by eye.",
    "atlas-2004.14636-ww": "An auxiliary figure, not in the paper (the record says so); compare with HEPData Table 16. "
                           "Width domain corrected (2026-10-12): below the stated mass resolution (§5.6).",
    "atlas-2108.13391-monoh": "Auxiliary figures, not in the paper (the record says so); compare with the named HEPData table.",
    "ccfr-1406.2332-trident": "Read from the figure (stored about 2% stronger than the figure, as the record says).",
    "flavour-b-to-k-invisible": "The form-factor constants come from elsewhere; the limit itself is on the page.",
    "lep-inert-doublet": "m_Z is a constant, not from this page; the four mass bounds are on the page.",
    "fermi-2311.04982-spectral": "The page was corrected from 12 to 13 (2026-10-12): Fig. 6's caption is there.",
    "cms-2405.13778-V1": "R4 correction applied: the width wording (shared with A1, V2, A2).",
    "icecube-1612.05949-sd": "R4 correction applied: systematic inflation and the erratum, EPJC 79 (2019) 214 (shared with -si).",
    "fermi-1503.02641-dsph": "R4 correction applied: a mixture goes to the spectral dwarf likelihood.",
    "lep-hep-ex-0509008-zinv": "R4 correction applied: the limit is on page 173.",
    "atlas-2009.14791-zz": "Width domain corrected (2026-10-12, docs/widths.md): narrow below Γ/m = 0.5% (§9.1.1); large-width tables only for matching interference (§5).",
    "atlas-1910.08447-dijet-gaussian": "Width domain corrected (2026-10-12): to Γ/m = 12%, acceptance matched by width (§3).",
    "atlas-2010.14293-squark": "Corrected (2026-10-12): outside the contour undecided, not allowed (χ exchange adds production, not computed).",
}


def table(path: Path) -> dict[str, dict]:
    rows = {}
    for line in path.read_text().splitlines():
        if line.startswith("| `"):
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            rows[cells[0].strip("`")] = {"state": cells[1], "label": cells[3], "numbers": cells[4],
                                         "hash": cells[5].strip("`")}
    return rows


def dependencies(path: Path) -> dict[str, int]:
    text = path.read_text().split("## By record", 1)[-1]
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"- `([^`]+)`: (\d+) portal", text)}


def gated_by(rid: str, deps: dict) -> int | str:
    """The portals a record gates; a dependency key may name several records ('icecube-…-sd/-si')."""
    if rid in deps:
        return deps[rid]
    stem, _, kind = rid.rpartition("-")
    for key, n in deps.items():
        head, _, tail = key.rpartition("-")
        if head == stem and kind in tail.split("/"):
            return n
    return "—"


def row(rid: str, rows: dict, deps: dict) -> str:
    r = rows[rid]
    gated = "every relic verdict" if rid == "planck-2018-omega" else gated_by(rid, deps)
    return (f"| `{rid}` | {gated} | {r['label']} | {r['numbers'][:110]} | `adroit records verify {rid} --by \"{SIGNER}\" "
            f"--expected-hash {r['hash']}` | {NOTES.get(rid, '')} |")


def main() -> int:
    rows, deps = table(HERE / "precheck.md"), dependencies(HERE / "portal_dependencies.md")
    waiting = [k for k, v in rows.items() if not v["state"].startswith("verified")]
    verified = len(rows) - len(waiting)
    resign = [k for k in RESIGN if k in waiting]
    gating = sorted([k for k in waiting if gated_by(k, deps) != "—" and k != "planck-2018-omega" and k not in resign],
                    key=lambda k: (-gated_by(k, deps), k))
    rest = sorted(k for k in waiting if k not in gating and k not in resign and k != "planck-2018-omega")
    head = "| record | portals gated | label on page | numbers on page | command | note |\n|---|---|---|---|---|---|"
    out = [
        "# R9: record verification: the packet for the person who signs", "",
        f"**Status ({date.today()}): "
        + ("done: every record is verified" if not waiting else "prepared") + "; the signatures are the owner's.** "
        "A record counts as verified only "
        "when a person has compared it with its source and signed it; synthetic names never count, and nothing "
        "here signs on anyone's behalf. Regenerate this page after any record edit (`docs/r9/packet.py`): each "
        "command pins the record's current scientific hash.", "",
        f"Today: **{verified} of {len(rows)} records verified**; {len(waiting)} await verification. R4's text "
        "corrections were applied to the nine records signed earlier (eight entries, since the CMS and IceCube "
        "records share text), which made their signatures stale: they are listed first for re-signing, with the three "
        "records whose width domains, and the one whose QCD-only production, were corrected on 2026-10-12 after the "
        "owner had signed them (docs/widths.md, docs/benchmark_limits.md). "
        "`planck-2018-omega` lost its signature when it was corrected to Table 2's Ω_c h² = 0.1200 ± 0.0012 "
        "(2026-10-05).", "",
        "## How to verify one record", "", "```",
        "uv run adroit records review ID         # the source, the page, the data, the scientific hash",
        f"uv run adroit records verify ID --by \"{SIGNER}\" --expected-hash HASH", "```", "",
        "Each record has a `notes` section (Markdown) for where each stored value is in its source and anything "
        "else a reader should know; notes are outside the signed content, so adding or correcting them never "
        "voids a signature. The hash pins exactly what you reviewed: if the record changes before you sign, `verify` "
        "refuses. Every "
        "source PDF is in the tools folder (`~/agentic-dm-tools/record-sources/`); the workbench's Records page "
        "opens each at its cited page.", "",
        "Aids, which are not verifications:",
        "- `docs/r9/precheck.md`: whether each record's cited figure or table label is on the cited page, and "
        "whether its scalar numbers are printed there;",
        "- `docs/r9/portal_dependencies.md`: for each library portal at its benchmark, the constraints that wait "
        "for a record, and the verdict each then reaches.", "",
        "## 1. Re-sign: the records signed before, now corrected (R4's text corrections; the width domains of 2026-10-12)", "", head,
        *[row(k, rows, deps) for k in resign], "",
        "## 2. The relic density", "", head, row("planck-2018-omega", rows, deps), "",
        "## 3. The records behind the portals' default verdicts (most portals first)", "", head,
        *[row(k, rows, deps) for k in gating], "",
        "## 4. The other records awaiting verification", "", head, *[row(k, rows, deps) for k in rest], "",
        "## 5. The gate, after the signatures", "",
        "Run the README's example commands **without** `--unverified` and compare with their documented verdicts:", "",
        "```", "uv run adroit track1 --portal higgs_portal_scalar",
        "uv run adroit track1 docs/dm13/axial_mediator.yaml --x m_med:10:10000 --y m_chi:1:2000",
        "uv run adroit single-idea docs/dm13/vector_mediator.yaml --experiment \"CDMS II Si (2013)\" --masses 5:40:12",
        "uv run adroit exclude L10 --isospin s --masses 10,100,1000",
        "uv run adroit records list                            # ends with the verified count", "```", "",
        "The smallest set for the README's examples, beyond the re-signed records: `planck-2018-omega`, "
        "`planck-2018-pann`, `smodels-3.2.1`, `calore-2202.03076-pbar` and `cms-1806.00843-dijet`.",
    ]
    OUT.write_text("\n".join(out) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {verified} verified, {len(resign)} to re-sign, {len(waiting)} waiting")
    return 0


if __name__ == "__main__":
    sys.exit(main())

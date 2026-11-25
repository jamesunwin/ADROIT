"""Download heavy-scalar resonance limits (HEPData, CC0) into ~/agentic-dm-tools/heavy-higgs-limits/.

For each selected table the CSV and JSON versions are saved, and index.json lists
analysis, arXiv / INSPIRE ids, table name, description, column headers (with units) and
the qualifiers (production mode, width ...).  HEPData records are released under CC0.

Usage: python fetch_heavy_higgs_limits.py
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from hepdata_tools import download_table, record

OUT = Path.home() / "agentic-dm-tools/heavy-higgs-limits"

SELECTION = [
    {"key": "ATLAS_ZZ_139", "inspire": 1820316, "arxiv": "2009.14791", "decay": "H -> ZZ",
     "paper": "ATLAS, Eur. Phys. J. C 81 (2021) 332: heavy resonances -> ZZ -> 4l, 2l2nu, 139 fb-1",
     "tables": ["Table 10", "Table 11", "Table 12", "Table 13", "Table 14", "Table 15"]},
    {"key": "ATLAS_WW_36", "inspire": 1628411, "arxiv": "1710.01123", "decay": "H -> WW",
     "paper": "ATLAS, Eur. Phys. J. C 78 (2018) 24: heavy resonances -> WW -> e nu mu nu, 36.1 fb-1",
     "tables": ["Table 10", "Table 11", "Table 12", "Table 13", "Table 14"]},
    {"key": "ATLAS_VVsemilep_139", "inspire": 1793572, "arxiv": "2004.14636", "decay": "spin-0 (radion) -> WW, ZZ",
     "paper": ("ATLAS, Eur. Phys. J. C 80 (2020) 1165: heavy diboson resonances, semileptonic, 139 fb-1; "
               "spin-0 benchmark = narrow ggF/VBF radion (same kinematics as a narrow heavy scalar)"),
     "tables": ["Table 8", "Table 9", "Table 16", "Table 17", "Table 18", "Table 19"]},
    {"key": "ATLAS_HH_comb_139", "inspire": 2726938, "arxiv": "2311.15956", "decay": "X -> HH",
     "paper": "ATLAS, Phys. Rev. Lett. 132 (2024) 231801: resonant HH combination (bbbb, bbtautau, bbyy), 126-140 fb-1",
     "tables": ["Observed and expected upper limits at the 95% CL"]},
    {"key": "CMS_HH_comb_138", "inspire": 2771692, "arxiv": "2403.16926", "decay": "X -> HH",
     "paper": "CMS, Phys. Rept. 1115 (2025) 368: searches for Higgs production through heavy resonances, 138 fb-1",
     "tables": ["Figure 27(1)", "Figure 44(combination only)"]},
    {"key": "CMS_ttbar_36", "inspire": 1747886, "arxiv": "1908.01115", "decay": "H/A -> tt (coupling-modifier limits)",
     "paper": ("CMS, JHEP 04 (2020) 171: heavy H/A -> tt, 35.9 fb-1; limits on the top coupling modifier "
               "g_Htt (interference with QCD tt included), not on sigma x BR"),
     "tables": ["Figure 5-a", "Figure 5-b", "Figure 5-c", "Figure 5-d", "Figure 5-e", "Figure 5-f",
                "Figure 6-a", "Figure 6-b", "Figure 6-c", "Figure 6-d", "Figure 6-e", "Figure 6-f"]},
    {"key": "CMS_monojet_scalar_101", "inspire": 1894408, "arxiv": "2107.13021", "decay": "S -> invisible (DM simplified model)",
     "paper": ("CMS, JHEP 11 (2021) 153: monojet/mono-V, 101 fb-1; signal-strength limits for the DMsimp "
               "spin-0 mediator (ggF through top loop, g_q = 1, g_chi = 1) vs mediator mass"),
     "tables": ["Signal strength limits, scalar mediator", "Signal strength limits, pseudoscalar mediator"]},
]


def parse_csv_meta(text: str) -> dict:
    """Extract '#:' metadata and column headers from a HEPData CSV."""
    meta: dict = {"qualifiers": [], "headers": []}
    expect_header = True
    for line in text.splitlines():
        if not line.strip():
            expect_header = True
            continue
        if line.startswith("#:"):
            expect_header = True
            body = line[2:].strip()
            if ":" in body and body.split(":", 1)[0] in ("name", "description", "table_doi", "data_file"):
                k, v = body.split(":", 1)
                meta[k.strip()] = v.strip()
            elif body.startswith("keyword"):
                meta.setdefault("keywords", []).append(body)
            elif body not in meta["qualifiers"]:
                meta["qualifiers"].append(body)
        elif expect_header and not line.startswith("#"):
            hdr = next(csv.reader(io.StringIO(line)))
            if hdr not in meta["headers"]:
                meta["headers"].append(hdr)
            expect_header = False
    return meta


def main() -> None:
    """Download every selected table and write index.json."""
    OUT.mkdir(parents=True, exist_ok=True)
    index = {"licence": "HEPData records are CC0 (public domain); cite the papers.",
             "source": "https://www.hepdata.net", "analyses": []}
    for sel in SELECTION:
        rec = record(sel["inspire"])
        version = rec.get("version")
        entry = {k: sel[k] for k in ("key", "inspire", "arxiv", "decay", "paper")}
        entry["hepdata_version"] = version
        entry["record_url"] = f"https://www.hepdata.net/record/ins{sel['inspire']}"
        entry["tables"] = []
        sub = OUT / sel["key"]
        for t in sel["tables"]:
            p_csv = download_table(sel["inspire"], t, sub, "csv")
            download_table(sel["inspire"], t, sub, "json")
            meta = parse_csv_meta(p_csv.read_text())
            entry["tables"].append({"table": t, "csv": str(p_csv.relative_to(OUT)),
                                    "json": str(p_csv.with_suffix(".json").relative_to(OUT)),
                                    "description": meta.get("description", ""),
                                    "doi": meta.get("table_doi", ""),
                                    "column_headers": meta["headers"],
                                    "qualifiers": meta["qualifiers"]})
            print(sel["key"], t, "->", p_csv.name, flush=True)
        index["analyses"].append(entry)
    (OUT / "index.json").write_text(json.dumps(index, indent=1))
    print("wrote", OUT / "index.json")


if __name__ == "__main__":
    main()

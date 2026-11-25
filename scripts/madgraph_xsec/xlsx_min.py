"""Minimal .xlsx reader (stdlib only): sheet -> list of rows (strings / floats)."""

from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _col_index(ref: str) -> int:
    """'C12' -> 2."""
    letters = re.match(r"[A-Z]+", ref).group(0)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def read_sheet(path: str, sheet_name: str) -> list[list[object]]:
    """Return the cells of ``sheet_name`` as a ragged list of rows."""
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid = None
    for sh in wb.find("m:sheets", NS):
        if sh.get("name") == sheet_name:
            rid = sh.get(f"{{{NS['r']}}}id")
    if rid is None:
        raise KeyError(sheet_name)
    target = [r.get("Target") for r in rels if r.get("Id") == rid][0]
    target = target.lstrip("/")
    if not target.startswith("xl/"):
        target = "xl/" + target
    shared: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in sst.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    root = ET.fromstring(z.read(target))
    rows: list[list[object]] = []
    for row in root.iter(f"{{{NS['m']}}}row"):
        cells: dict[int, object] = {}
        for c in row.findall("m:c", NS):
            v = c.find("m:v", NS)
            t = c.get("t")
            if v is None:
                isel = c.find("m:is", NS)
                if isel is not None:
                    cells[_col_index(c.get("r"))] = "".join(x.text or "" for x in isel.iter(f"{{{NS['m']}}}t"))
                continue
            if t == "s":
                val: object = shared[int(v.text)]
            elif t in ("str", "inlineStr"):
                val = v.text
            else:
                try:
                    val = float(v.text)
                except (TypeError, ValueError):
                    val = v.text
            cells[_col_index(c.get("r"))] = val
        if cells:
            n = max(cells) + 1
            rows.append([cells.get(i, "") for i in range(n)])
    return rows

"""Extract all <table> elements from saved CERN TWiki pages to CSV files.

Usage: python twiki_tables.py OUTDIR page1.html page2.html ...
Each table is written as OUTDIR/<page>__tNN.csv, with the nearest preceding
heading recorded in OUTDIR/<page>__index.txt.
"""

import csv
import os
import re
import sys
from html.parser import HTMLParser


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.cur = None
        self.row = None
        self.cell = None
        self.heading = ""
        self.inh = False
        self.hbuf = ""
        self.depth = 0

    def handle_starttag(self, tag, a):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.inh = True
            self.hbuf = ""
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.cur = {"heading": self.heading.strip(), "rows": []}
        if self.cur is None:
            return
        if tag == "tr":
            self.row = []
        if tag in ("td", "th"):
            self.cell = ""

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.inh = False
            self.heading = re.sub(r"\s+", " ", self.hbuf)
        if self.cur is None:
            return
        if tag in ("td", "th") and self.row is not None and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            if any(self.row):
                self.cur["rows"].append(self.row)
            self.row = None
        if tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.tables.append(self.cur)
                self.cur = None

    def handle_data(self, d):
        if self.inh:
            self.hbuf += d
        if self.cell is not None:
            self.cell += d


out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for fn in sys.argv[2:]:
    p = P()
    p.feed(open(fn, encoding="utf-8", errors="replace").read())
    base = os.path.basename(fn).replace(".html", "")
    idx = []
    k = 0
    for t in p.tables:
        rows = t["rows"]
        if len(rows) < 4:
            continue
        # skip the attachment table
        if rows and any("Attachment" in c for c in rows[0]):
            continue
        k += 1
        name = f"{base}__t{k:02d}.csv"
        with open(os.path.join(out, name), "w", newline="") as f:
            csv.writer(f).writerows(rows)
        idx.append(
            f"{name}\t{len(rows)} rows\theading={t['heading']!r}\theader={rows[0]}\tfirst={rows[1]}\tlast={rows[-1]}"
        )
    open(os.path.join(out, base + "__index.txt"), "w").write("\n".join(idx) + "\n")
    print("\n".join(idx))

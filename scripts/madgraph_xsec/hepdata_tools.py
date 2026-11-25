"""Small HEPData client (stdlib only): list a record's tables and download them as JSON/CSV/YAML."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.hepdata.net"


def _get(url: str, retries: int = 3) -> bytes:
    """GET with a JSON Accept header and simple retries."""
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "curl/8.7.1"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception:  # noqa: BLE001 - network retry
            if k == retries - 1:
                raise
            time.sleep(3)
    return b""


def record(inspire: int | str, version: int | None = None) -> dict:
    """Return the record metadata JSON for INSPIRE id ``inspire``."""
    url = f"{BASE}/record/ins{inspire}?format=json"
    if version:
        url += f"&version={version}"
    return json.loads(_get(url))


def list_tables(inspire: int | str) -> list[dict]:
    """[{name, description, location, doi}] for every table of the record."""
    rec = record(inspire)
    return [{"name": t["name"], "description": t.get("description", ""),
             "location": t.get("location", ""), "doi": t.get("doi", "")}
            for t in rec.get("data_tables", [])]


def download_table(inspire: int | str, table: str, outdir: Path, fmt: str = "json",
                   version: int | None = None) -> Path:
    """Download one table (by its name) in ``fmt`` (json, csv or yaml) into ``outdir``."""
    outdir.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/download/table/ins{inspire}/{urllib.parse.quote(table)}"
    if version:
        url += f"/{version}"
    url += f"/{fmt}"
    data = _get(url)
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in table)
    path = outdir / f"ins{inspire}_{safe}.{fmt}"
    path.write_bytes(data)
    return path


if __name__ == "__main__":
    import sys
    for t in list_tables(sys.argv[1]):
        print(f"{t['name']!r:70s} | {t['location']} | {t['description'][:110]}")

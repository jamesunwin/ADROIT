"""The auditor's CU recheck, CV-03 (2026-10-28), through the rendered workbench: a saved study's current certification was
read against the tables' hashes kept by size and modification time, so after a table was replaced by other bytes of
the same length, its modification time kept, Studies and the point still read the study as certified, until a
restart. The study is written as the workbench writes one (``test_certification_journey._saved_study``), its
certificates bound to a copy of the tables (``eos_copy``)."""
from __future__ import annotations

import hashlib
import json
import os
from urllib.parse import urlencode

import pytest
from nicegui.testing import User

from adroit.constraints import relic
from tests.orchestrator.test_cv_recheck import _same_length
from tests.ui.acceptance.test_certification_journey import _saved_study

STALE = "VIABLE · STALE CERTIFICATION"


@pytest.mark.eos_band
@pytest.mark.needs("eos")
async def test_a_replaced_table_reads_stale_in_the_history_without_a_restart(user: User, tmp_path, monkeypatch,
                                                                             eos_copy):
    """The Studies badge and the thermal root's explanation read certified; the table the root is bound to replaced
    (same length, modification time kept), the same pages, not rebuilt, read stale and name the table; restored, they
    read certified again. Viewing changes no byte of the result."""
    from adroit.evidence.points import points
    from adroit.evidence.results import load_result
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder = _saved_study(root, monkeypatch, tables=True, between=(5.0, 6.0))
    result = folder / "result.json"
    before = hashlib.sha256(result.read_bytes()).hexdigest()
    workflow, saved = load_result(result)
    row = next(r for r in points(workflow, saved) if r.kind == "thermal root")
    crossing = next(c for c in json.loads(result.read_text())["verdict"]["crossings"]
                    if c["certificate"]["bound"].get("eos_tables"))
    name = sorted(crossing["certificate"]["bound"]["eos_tables"])[0]
    table = eos_copy / relic.EOS_TABLES[name][0]
    original, stat = table.read_bytes(), table.stat()
    point = "/study/point?" + urlencode({"path": folder.name, "point": row.point_id})

    def put(content: bytes) -> None:
        fresh = table.with_name(table.name + ".new")
        fresh.write_bytes(content)
        os.replace(fresh, table)
        os.utime(table, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    await user.open("/studies")                             # the current hashes read, and kept
    await user.should_see("a toy plane")
    await user.should_not_see(STALE)
    put(_same_length(original))
    assert (table.stat().st_size, table.stat().st_mtime_ns) == (stat.st_size, stat.st_mtime_ns)
    await user.open("/studies")
    await user.should_see(STALE)
    await user.open(point)
    await user.should_see("Certification: stale")
    await user.should_see(f"the equation of state's {name} table is not the one it was certified with")
    put(original)
    await user.open("/studies")
    await user.should_not_see(STALE)
    assert hashlib.sha256(result.read_bytes()).hexdigest() == before

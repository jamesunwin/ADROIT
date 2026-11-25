"""The auditor's CT recheck, CU-03 (2026-10-28): a saved result whose list of record ids (from before CT-01) held ``{}`` or
``[]`` raised TypeError past the readers' damage boundaries, so Studies, the study and its point were server errors.
Through the rendered pages: a bound study beside a healthy one, the damage in a point's records and in a check's
evidence, before and after a restart, then restored; no byte changed by viewing."""
from __future__ import annotations

import copy
import hashlib
import json
from urllib.parse import urlencode

import pytest
from nicegui.testing import User

from adroit.orchestrator import studies

TITLE = "a toy plane (no tables)"
NAMED = "its content is not a track1 result"


def _damaged(data: dict, where: str, member) -> dict:
    out = copy.deepcopy(data)
    crossing = out["verdict"]["crossings"][0]
    if where == "records":
        crossing["evaluation"]["records"] = [member]
    else:
        crossing["certificate"]["checks"][0]["evidence_records"] = [member]
    return out


@pytest.mark.parametrize("where,member", [("records", {}), ("evidence", [])], ids=["a point's records",
                                                                                  "a check's evidence"])
async def test_a_malformed_list_of_record_ids_leaves_the_history_readable(user: User, tmp_path, monkeypatch, where,
                                                                          member):
    from adroit.ui.app import build_pages
    from tests.ui.test_cs_history import _bound_study
    root = build_pages(tmp_path / "runs")
    bound = _bound_study(root, monkeypatch)
    healthy = root / "healthy"
    healthy.mkdir()
    studies.record(healthy, "idea", "a healthy study")
    result = bound / "result.json"
    original = result.read_bytes()
    result.write_text(json.dumps(_damaged(json.loads(original), where, member)))
    damaged = hashlib.sha256(result.read_bytes()).digest()
    page = "/study?" + urlencode({"path": bound.name})
    point = "/study/point?" + urlencode({"path": bound.name, "point": "contour:0"})
    for _ in range(2):                                      # before and after a restart
        build_pages(root)
        await user.open("/studies")
        await user.should_see(TITLE)
        await user.should_see(NAMED)
        await user.should_see("a healthy study")
        await user.open(page)
        await user.should_see(TITLE)
        await user.should_see(NAMED)
        await user.open(point)
        await user.should_see("Point unavailable")
        await user.should_see("not an id")
        await user.open("/study?" + urlencode({"path": healthy.name}))
        await user.should_see("a healthy study")
    assert hashlib.sha256(result.read_bytes()).digest() == damaged
    result.write_bytes(original)                            # restored
    await user.open("/studies")
    await user.should_not_see(NAMED)
    await user.open(point)
    await user.should_not_see("Point unavailable")

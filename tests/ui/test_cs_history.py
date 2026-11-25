"""The auditor's CR recheck (2026-10-27) through the rendered workbench:
- CS-01: a result of another kind's shape (``{"band": 3, "level": "viable"}``) had shown VIABLE on a study of every
  kind, and one whose named table support was missing had read certified;
- CS-05: the current records damaged after the server started had made the Studies page a server error.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.orchestrator import studies
from tests.unsigned_records import used

KINDS = ("track1", "single_idea", "signal", "idea", "promotion", "native_joint", "native_coverage", "exclusion",
         "lagrangian")
RECORD = "dampe-2112.08860-lines"



async def test_a_result_of_another_shape_shows_no_badge_on_any_page(user: User, tmp_path):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    for kind in KINDS:
        folder = root / kind
        folder.mkdir()
        studies.record(folder, kind, f"a {kind} study of another shape")
        (folder / "result.json").write_text(json.dumps({"band": 3, "level": "viable"}))
    await user.open("/studies")
    for kind in KINDS:
        await user.should_see(f"a {kind} study of another shape")
    await user.should_see(marker="unreadable_results")
    await user.should_not_see("VIABLE")
    for kind in ("track1", "single_idea", "signal", "promotion"):
        await user.open("/study?" + urlencode({"path": kind}))
        await user.should_see(f"a {kind} study of another shape")
        await user.should_not_see("VIABLE")


def _bound_study(root: Path, monkeypatch) -> Path:
    """A Track 1 study as the workbench writes one (``test_certification_journey._saved_study``), its constraints
    using an unverified record, so its claims are bound to that record's fingerprint."""
    import tests.ui.acceptance.test_certification_journey as journey
    original = journey.PointResult
    monkeypatch.setattr(journey, "PointResult", lambda **kw: original(**kw, unverified_records=[RECORD],
                                                                         records=used(RECORD)))
    return journey._saved_study(root, monkeypatch, tables=False, between=(5.0, 6.0))


async def test_damaged_current_records_leave_the_history_readable_and_bound_claims_stale(user: User, tmp_path,
                                                                                       monkeypatch):
    """CS-05, the auditor's case: the records damaged after the server started, a bound study beside an unrelated one. The
    Studies page, the bound study's card and its point read stale, naming the record; the unrelated study is
    unaffected; restored, the claims read as before; no result's bytes change."""
    from adroit.constraints import database
    from adroit.ui.app import build_pages
    original = database.RECORDS.read_bytes()
    copied = tmp_path / "records.yaml"
    copied.write_bytes(original)
    monkeypatch.setattr(database, "RECORDS", copied)
    root = build_pages(tmp_path / "runs")
    bound = _bound_study(root, monkeypatch)
    unrelated = root / "unrelated"
    unrelated.mkdir()
    studies.record(unrelated, "idea", "an unrelated study")
    before = {p: hashlib.sha256(p.read_bytes()).digest() for p in root.rglob("result.json")}
    data = json.loads((bound / "result.json").read_text())
    assert RECORD in data["verdict"]["crossings"][0]["certificate"]["bound"]["records"]
    point = "/study/point?" + urlencode({"path": bound.name, "point": "contour:0"})

    await user.open("/studies")
    await user.should_see("a toy plane (no tables)")
    await user.should_not_see("STALE CERTIFICATION")
    copied.write_text("records: [\n")                                 # damaged after the server started
    build_pages(root)
    await user.open("/studies")
    await user.should_see("a toy plane (no tables)")
    await user.should_see("an unrelated study")
    await user.should_see("STALE CERTIFICATION")
    await user.open("/study?" + urlencode({"path": bound.name}))
    await user.should_see(f"the record {RECORD} cannot be read since it was certified")
    await user.open(point)
    await user.should_see(f"stale: the record {RECORD} cannot be read")
    copied.write_bytes(original)                                       # restored
    await user.open("/studies")
    await user.should_see("a toy plane (no tables)")
    await user.should_not_see("STALE CERTIFICATION")
    assert before == {p: hashlib.sha256(p.read_bytes()).digest() for p in root.rglob("result.json")}

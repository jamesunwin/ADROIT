"""The auditor's CV recheck, CW-01 (2026-10-30), through the rendered workbench: a saved study's validation was kept by the
size and modification time of its result, so after the result was replaced by malformed bytes of the same length, its
modification time kept, Studies and the study still showed its badge (VIABLE, certified), while the point and the
export refused it. Studies, the study, the point and the export are checked together, warm, without a restart."""
from __future__ import annotations

import hashlib
from urllib.parse import urlencode

import pytest
from nicegui.testing import User

from tests.orchestrator.test_cw_recheck import TABLES, _malformed, _put, _toy_study

NAMED = "its content is not a track1 result"


@pytest.mark.parametrize("tables", TABLES)
@pytest.mark.parametrize("how", ["replaced", "rewritten in place"])
async def test_a_malformed_replacement_reads_as_damage_on_every_page_at_once(user: User, tmp_path, monkeypatch, how,
                                                                             tables):
    """The pages read the study (warm); the result replaced, its size and modification time kept. The same server's
    Studies, study and point name the damage, none shows the badge, and the export refuses it; restored, the badge is
    back. Viewing changes no byte."""
    from adroit.evidence.archive import export_run
    from adroit.evidence.points import points
    from adroit.evidence.results import load_result
    from adroit.orchestrator import study_headline
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder = _toy_study(root, monkeypatch, tables)
    result = folder / "result.json"
    original = result.read_bytes()
    badge = study_headline.headline_of(folder).words
    assert badge.startswith("VIABLE")
    row = points(*load_result(result))[0]
    study = "/study?" + urlencode({"path": folder.name})
    point = "/study/point?" + urlencode({"path": folder.name, "point": row.point_id})

    await user.open("/studies")                             # the validation read, and kept
    await user.should_see(badge)
    await user.open(study)
    await user.should_see(badge, marker="study_verdict")
    put = _put(result, how)
    put(_malformed(original))
    damaged = hashlib.sha256(result.read_bytes()).digest()
    await user.open("/studies")
    await user.should_see(NAMED)
    await user.should_not_see(badge)
    await user.open(study)
    await user.should_see(NAMED)
    await user.should_see("Points unavailable")
    await user.should_not_see(marker="study_verdict")       # the saved report still says what was concluded then
    await user.open(point)
    await user.should_see("Point unavailable")
    await user.should_see("not an id")
    with pytest.raises(ValueError, match="not an id"):
        export_run(folder, tmp_path / "bundle.zip")
    assert hashlib.sha256(result.read_bytes()).digest() == damaged
    put(original)
    await user.open("/studies")
    await user.should_see(badge)
    await user.should_not_see(NAMED)

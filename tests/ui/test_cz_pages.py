"""The auditor's CY recheck, CZ-02 (2026-11-01), through the rendered study page: a promotion's child writer had bound the
report of the result it held, A ("AUDIT CHILD A: viable"), to B, published meanwhile, and the page had shown it under
B's EXCLUDED badge. The writer now refuses; the folder it leaves is read as what it is: never A's report under B."""
from __future__ import annotations

from pathlib import Path

import pytest
from nicegui.testing import User

from adroit.evidence import build
from tests.orchestrator.test_cz_recheck import BOUNDARIES, _attempt, _child_versions, _group


@pytest.mark.parametrize("boundary", BOUNDARIES)
async def test_a_child_folder_left_by_a_refused_write_never_shows_a_s_report_under_b(user: User, tmp_path,
                                                                                      monkeypatch, boundary):
    """B (result, evidence and report) published at each boundary of the child writer's publication; the folder
    recorded as a study (as a folder written before is). Its page never shows A's report: under B's badge it says the
    report is of another version, or that the result and its evidence disagree, or that the publication was
    interrupted. B's parts were written from outside ADROIT's writers, so the child's publication, stopped by them
    (``Replaced``), keeps its mark, and its report is withheld (the auditor's merge-round audit, HE-01, 2026-11-12: this test
    had required B's report shown, the mark removed on ``Replaced``)."""
    from urllib.parse import urlencode
    from adroit.orchestrator import studies
    from adroit.orchestrator.signal import SignalResult
    from adroit.ui.app import build_pages
    from tests.ui.acceptance.test_journeys import _toy_signal_study
    root = build_pages(tmp_path / "runs")
    parent = root / "signal"
    label = _toy_signal_study(parent, monkeypatch)
    result = SignalResult.model_validate_json((parent / "result.json").read_bytes())
    promote, held = _child_versions(monkeypatch)
    c = promote.candidates_of(result)[label]
    origin, spec = promote.models_for(result, c)[0]

    def publish_b():
        return _group(held["folder"], "single_idea", held["b"], "# B\n\nAUDIT CHILD B report\n")[0]()
    done, raised = _attempt(lambda: promote._study(parent, result, c, origin, spec, {"masses": 2, "toys": 2,
                                                                                   "grid": 4}), boundary, publish_b)
    assert done == [True]
    folder: Path = held["folder"]
    studies.record(folder, "single_idea", "AUDIT child", parent=parent)
    await user.open("/study?" + urlencode({"path": str(folder.relative_to(root))}))
    await user.should_not_see("AUDIT CHILD A")
    if boundary in ("after its report", "before its report"):     # before its report: the writer, finding B, wrote
        await user.should_see(marker="report_interrupted")    # no report of its own (DE-02); its mark kept (HE-01)
        await user.should_not_see("AUDIT CHILD B report")
    assert isinstance(raised, build.Replaced)

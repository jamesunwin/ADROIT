"""The auditor's CS recheck, CT-04 (2026-10-28): a study whose result was missing opened as a server error, its approval
reading the absent file, though Studies listed it. Through the rendered pages: an idea and a signal study present,
their result removed, then restored; and a study whose run is still writing its result."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.orchestrator import studies

STATES = ("present", "missing", "restored")


def _idea_study(folder: Path) -> None:
    from adroit.orchestrator.ideas import IdeaRequest, IdeaResult
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(IdeaResult(request=IdeaRequest(text="a fixture"),
                                                   dropped=["synthetic: no model proposed"]).model_dump_json())
    studies.record(folder, "idea", "a saved idea")


async def _three_states(user: User, folder: Path, title: str, action: str) -> None:
    """The study through Studies and its page, its result present, missing and restored: the page opens each time,
    its report kept; missing, the result is named and ``action`` (what reads it) is withheld; no bytes change."""
    (folder / "report.md").write_text("# Its report\n\nThe report's own words.\n")
    result = folder / "result.json"
    original = result.read_bytes()
    page = "/study?" + urlencode({"path": folder.name})
    for state in STATES:
        if state == "missing":
            result.unlink()
        if state == "restored":
            result.write_bytes(original)
        await user.open("/studies")
        await user.should_see(title)
        await user.open(page)
        await user.should_see(title)
        await user.should_see("The report's own words.")
        if state == "missing":
            await user.should_see("result.json is missing")
            await user.should_see(marker="damaged_result")
            await user.should_not_see(action)
        else:
            await user.should_not_see(marker="damaged_result")
    assert result.read_bytes() == original


async def test_an_idea_study_whose_result_is_missing_opens_naming_it(user: User, tmp_path):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _idea_study(root / "idea")
    await _three_states(user, root / "idea", "a saved idea", "Approve models to constrain")


async def test_a_signal_study_whose_result_is_missing_opens_naming_it(user: User, tmp_path):
    from adroit.ui.app import build_pages
    from tests.ui.test_workflow_acceptance import _signal_study
    root = build_pages(tmp_path / "runs")
    _signal_study(root / "signal")
    await user.open("/study?path=signal")
    await user.should_see("Promote a candidate to studies")
    await _three_states(user, root / "signal", "Signal fits: CDMS II Si", "Promote a candidate to studies")


async def test_a_study_whose_run_is_still_writing_its_result_says_so(user: User, tmp_path):
    """A study record ahead of its result, its job running: the page says the run is still going, with its live view,
    not that the result is missing."""
    from adroit.ui import engine
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder = root / "idea"
    _idea_study(folder)
    (folder / "result.json").unlink()
    engine.save(engine.Job(title="idea", kind="idea", command=["idea"], folder=str(folder), pid=os.getpid(),
                           acknowledged=True))
    await user.open("/study?path=idea")
    await user.should_see(marker="result_pending")
    await user.should_see("the run's live view and log")
    await user.should_not_see("result.json is missing")

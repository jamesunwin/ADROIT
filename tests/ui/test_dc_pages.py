"""The auditor's DB/VI recheck (2026-11-03), DC-01 at the pages: the history's row had shown the record it listed (A's title
and cost) beside the verdict of the result read with another record (B's), and a study page holding A had shown a later
run's cost, in the same folder, as A's. Each study is published by the production writer (``runs._write``); nothing is
calculated, and no request is sent (the run's ledger is simulated)."""
from __future__ import annotations

import json
from unittest.mock import patch
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.orchestrator import studies
from tests.orchestrator.test_vi_audit import publish, versions


async def test_the_history_row_is_of_the_record_read_with_its_verdict(user: User, tmp_path):
    """DC-01, the auditor's history case (seen in Chrome): A listed, then B published whole before the row's facts are read.
    The row shows B's title, verdict and cost together, never A's title and cost beside B's verdict."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    a, b = versions(root / "study")
    a.verdict.level, b.verdict.level = "excluded", "viable_pending"
    publish(root / "study", a, "A", 1.25)
    real, fired = studies.tree, []

    def listed(at):
        found = real(at)
        if not fired:
            fired.append(True)
            publish(root / "study", b, "B", 9.5)
        return found
    with patch.object(studies, "tree", listed):
        await user.open("/studies")
    await user.should_see("B study")
    await user.should_see("$9.50 settled")
    await user.should_not_see("A study")
    await user.should_not_see("$1.25")


async def test_the_history_row_withholds_a_record_of_another_version(user: User, tmp_path):
    """DC-01: A's record written back over B's publication: the row names the study by its folder, says its record is
    of another version, and shows no title, date or cost from it."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    a, b = versions(root / "study")
    publish(root / "study", a, "A", 1.25)
    record = studies.load(root / "study")
    publish(root / "study", b, "B", 9.5)
    studies.save(record)
    await user.open("/studies")
    await user.should_see(marker="listed_record_of_another")
    await user.should_see("study (its study record describes another version of its result)")
    await user.should_not_see("A study")
    await user.should_not_see("$1.25")


async def test_the_study_page_does_not_show_a_later_run_s_cost_as_the_study_s(user: User, tmp_path):
    """DC-01, the auditor's cost case: the page holds A (its record, result and report); then B is published in the folder
    with a later run's record and settled ledger ($9.50, simulated). The page shows A with A's own recorded cost,
    saying the run in its folder is not the one that published it, never $9.50 as A's."""
    from adroit.evidence import version
    from adroit.ui import engine
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder = root / "study"
    a, b = versions(folder)
    publish(folder, a, "A", 1.25)
    real, fired = version.resolve, []

    def read(*args, **kwargs):                  # B published, by a later run, once the page holds A (its version)
        found = real(*args, **kwargs)
        if not fired:
            fired.append(True)
            publish(folder, b, "B", 9.5)
            engine.save(engine.Job(title="B attempt", kind="idea", folder=str(folder), status="completed",
                                   command=["idea", "--text", "SIMULATED", "--budget", "10"], returncode=0,
                                   attempt="a-later-attempt"))
            (folder / "paid.jsonl").write_text(json.dumps({"id": "b", "state": "settled", "cost_usd": 9.5}) + "\n")
        return found
    with patch.object(version, "resolve", read):
        await user.open("/study?" + urlencode({"path": "study"}))
    await user.should_see("A study")
    await user.should_see("A report body")
    await user.should_see("is not the one that published this study")
    await user.should_not_see("$9.50")

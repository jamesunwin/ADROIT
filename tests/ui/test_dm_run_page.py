"""The auditor's DL recheck (2026-11-07), DM-01 on the run's page: a discovery run whose request record is damaged, beside
an earlier survey's ``discovery.json``, shows no figure for the run, its session or its cap, and says why (the auditor's
``dl_followup_browser``: the page had shown A's "$1.25 … ($8.75 left)" as this run's). Simulated dollars; no
provider."""

from __future__ import annotations

import pytest

pytest.importorskip("nicegui")

from nicegui.testing import User  # noqa: E402

from tests.orchestrator import test_dl_fixes as dl  # noqa: E402
from tests.orchestrator.test_dm_fixes import DAMAGED, damaged_survey  # noqa: E402


async def test_the_run_page_of_a_survey_whose_request_record_is_damaged_shows_no_figure(user: User, tmp_path,
                                                                                         monkeypatch):
    from adroit.orchestrator import accounting
    from adroit.orchestrator.model_intake import REQUESTS
    from adroit.ui import engine
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    service, ids = dl.sessions(tmp_path)
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    for n, damage in enumerate(DAMAGED):
        out = damaged_survey(root / f"case {n}", ids, damage)
        engine.save(dl._job(out, ids, "discover"))
        await user.open(f"/live?path=case {n}/survey")
        await user.should_see(f"the run's request record ({REQUESTS}) cannot be read")
        await user.should_see("Session total: not available")
        for figure in ("$1.25", "$8.75", "$10.00", "$8.50"):
            await user.should_not_see(figure)

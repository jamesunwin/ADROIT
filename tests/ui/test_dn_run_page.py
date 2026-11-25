"""The auditor's DM recheck (2026-11-08), DN-01 on the run's page: a discovery run whose request record is a link that leads
nowhere, beside an earlier survey's ``discovery.json``, shows no figure for the run, its session or its cap, says why,
and offers no session to continue (the auditor's ``dl_followup_browser``, ``/live?path=dangling``: the page had shown A's
"$1.25 … ($8.75 left)" as this run's, and "Review the discovery session" linking to A's). With a record bound to the run
naming B's session, B's figures and B's session. Simulated dollars; no provider."""

from __future__ import annotations

import pytest

pytest.importorskip("nicegui")

from nicegui import ui  # noqa: E402
from nicegui.testing import User  # noqa: E402

from tests.orchestrator import test_dl_fixes as dl  # noqa: E402
from tests.orchestrator.test_dn_fixes import LINKS, linked_survey  # noqa: E402

CONTINUE = "Review the discovery session"


def _continuations(user: User) -> list[str]:
    """Where each link or button of the page leads that opens a discovery session (an outcome's primary action is a
    button carrying its target as its ``href``)."""
    found = [*user.find(kind=ui.link).elements, *user.find(kind=ui.button).elements]
    return [href for e in found if "/constraints/discovery?" in (href := str(e.props.get("href", "")))]


async def test_the_run_page_of_a_survey_whose_request_record_leads_nowhere_shows_no_figure_and_no_session(
        user: User, tmp_path, monkeypatch):
    from adroit.orchestrator import accounting
    from adroit.orchestrator.model_intake import REQUESTS
    from adroit.ui import engine
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    service, ids = dl.sessions(tmp_path)
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    for n, link in enumerate(LINKS):
        out = linked_survey(root / f"case {n}", ids, link)
        engine.save(dl._job(out, ids, "discover"))
        await user.open(f"/live?path=case {n}/survey")
        await user.should_see(f"the run's request record ({REQUESTS}) cannot be read (a link to ")
        await user.should_see("Session total: not available")
        for figure in ("$1.25", "$8.75", "$10.00", "$8.50"):
            await user.should_not_see(figure)
        await user.should_not_see(CONTINUE)
        assert _continuations(user) == []
    out = linked_survey(root / "bound", ids, "a link to a missing file")
    engine.save(dl._job(out, ids, "resume"))
    await user.open("/live?path=bound/survey")
    await user.should_see("Session total so far: $8.50 spent of its approved $10.00 cap ($1.50 left)")
    await user.should_see(f"the run's request record ({REQUESTS}) cannot be read (a link to ")
    await user.should_not_see("$1.25")
    await user.should_see(CONTINUE)
    assert _continuations(user) and all(href.endswith(f"session={ids['b']}") for href in _continuations(user))

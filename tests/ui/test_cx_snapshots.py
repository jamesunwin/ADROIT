"""The auditor's CW recheck, CX-02 (2026-10-31), through the rendered workbench: a saved result published between two reads
of one page. The point page had shown A's prediction beside B's limit (A parsed, then B's evidence read), and a signal
study's page had failed with a server error (its result checked, then replaced by ``null`` before the continuation
panel read it again). Each page now reads the result once: what it shows is of one version, or the damage is named."""
from __future__ import annotations

from urllib.parse import urlencode

from nicegui.testing import User

from adroit.core.durable import write_atomic
from tests.orchestrator.test_cx_recheck import _publish, _published_after_open, _versions


async def test_the_point_page_shows_one_version_while_another_is_published(user: User, tmp_path, monkeypatch):
    """The point page of a saved study, B (result and evidence) published just after the page first reads the result:
    its status, group, prediction and limit are B's together; read before, A's together. Never A's prediction beside
    B's limit."""
    from adroit.ui.app import build_pages
    from tests.orchestrator.test_cw_recheck import _toy_study
    root = build_pages(tmp_path / "runs")
    folder = _toy_study(root, monkeypatch, False)
    a, b = _versions(folder)
    _publish(folder, a)
    page = "/study/point?" + urlencode({"path": folder.name, "point": "grid:0"})
    await user.open(page)
    await user.should_see("prediction 0.05; limit 0.11")
    await user.should_not_see("limit 0.01")
    with _published_after_open(folder / "result.json", lambda: _publish(folder, b)) as done:
        await user.open(page)
    assert done
    await user.should_see("Status here: excluded")
    await user.should_see("prediction 0.2; limit 0.01")
    await user.should_not_see("prediction 0.05")


async def test_a_signal_study_replaced_after_its_page_checked_it_shows_what_it_checked(user: User, tmp_path):
    """The auditor's interleaving: a signal study's result replaced by ``null`` (atomically, as the auditor did) after the page has
    checked it and before the continuation panel is built (at the pin, its second read and its third). The page reads
    the result once, so there is no read to follow: the panel is of the result it checked (the global significance
    stated), with no server error. Replaced while the page is reading it, the page is of the ``null`` throughout:
    named, the panel withheld."""
    from adroit.ui.app import build_pages
    from tests.ui.test_workflow_acceptance import _signal_study
    root = build_pages(tmp_path / "runs")
    folder = root / "signal"
    _signal_study(folder)
    result = folder / "result.json"
    original = result.read_bytes()
    page = "/study?" + urlencode({"path": "signal"})
    opens: list[str] = []
    with _published_after_open(result, lambda: write_atomic(result, "null"), opens, after=2):
        await user.open(page)
    await user.should_see(marker="global_significance")
    await user.should_not_see(marker="damaged_result")
    assert opens.count("result.json") == 1 and result.read_bytes() == original
    with _published_after_open(result, lambda: write_atomic(result, "null")) as done:
        await user.open(page)
    assert done
    await user.should_see("result.json is not a JSON object (it holds null)")
    await user.should_see(marker="damaged_result")
    await user.should_not_see(marker="global_significance")

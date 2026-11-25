"""The auditor's DN recheck (2026-11-08), DO-02, on the run's live page and the Activity page: a run whose log is there but
cannot be read (a folder, a link to one, a file it may not read; or a link that leads nowhere) shows its page, naming
the log, with its status, its cost and its continuation as its other records give them; with a resume bound to B's
session, B's figures and B's session. The live page had read the log raw, and the auditor's six cases (a folder, a link to a
folder and a file it may not read, each with and without a bound resume) had made it a server error
(``IsADirectoryError``, ``PermissionError``), and so would the Activity page, which lists every run. A control
restores the raw reading. Simulated dollars; no provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("nicegui")

from nicegui.testing import User  # noqa: E402

from tests.orchestrator import test_dl_fixes as dl  # noqa: E402
from tests.orchestrator.test_dn_fixes import LINKS  # noqa: E402
from tests.ui.test_dn_run_page import CONTINUE, _continuations  # noqa: E402


def _folder(entry: Path) -> None:
    entry.mkdir()


def _folder_link(entry: Path) -> None:
    (entry.parent / "a folder").mkdir()
    entry.symlink_to("a folder")


def _unreadable(entry: Path) -> None:
    entry.write_text("known prior content\n")
    entry.chmod(0)


# The auditor's three (dn_family_browser), and the links that lead nowhere (DN-01's)
LOGS = {"a folder": _folder, "a link to a folder": _folder_link, "a file it may not read": _unreadable, **LINKS}
NAMED = "Its log, log.txt, cannot be read ("


def _run(root: Path, ids: dict, case: str, command: str) -> str:
    """The auditor's ``dn_family`` case: a survey folder holding an earlier survey's ``discovery.json`` (session A's), no
    request record, and its log ``case`` (``LOGS``); its job a discover, or a resume naming B. Its live page's path."""
    from adroit.ui import engine
    label = f"{list(LOGS).index(case)} {command}"
    out = root / label
    out.mkdir(parents=True)
    (out / "discovery.json").write_text(json.dumps({"session": ids["a"]}))
    LOGS[case](out / "log.txt")
    engine.save(dl._job(out, ids, command))
    return label


async def _shows(user: User, label: str, ids: dict, command: str) -> None:
    """The run's live page, as DO-02 requires it: the log named, never "no output yet"; with a resume bound, B's figures
    and B's session to continue; with none, no figure and no session; never A's."""
    await user.open(f"/live?path={label}")
    await user.should_see(NAMED)
    await user.should_see("the rest of this page is read from the run's other records")
    await user.should_not_see("(no output yet)")
    await user.should_not_see("$1.25")
    if command == "resume":
        await user.should_see("Session total so far: $8.50 spent of its approved $10.00 cap ($1.50 left)")
        await user.should_see(CONTINUE)
        assert _continuations(user) and all(href.endswith(f"session={ids['b']}") for href in _continuations(user))
    else:
        await user.should_see("Session total: not available")
        await user.should_not_see(CONTINUE)
        assert _continuations(user) == []


async def test_a_run_whose_log_cannot_be_read_shows_its_page_naming_the_log(user: User, tmp_path, monkeypatch):
    """DO-02, the auditor's six cases and the links that lead nowhere: each run's page is shown, naming its log; then the
    Activity page lists every one of them, and where its diagnosis quotes its log, the log is named as one that cannot
    be read."""
    from adroit.orchestrator import accounting
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    service, ids = dl.sessions(tmp_path)
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    for case in LOGS:
        for command in ("discover", "resume"):
            await _shows(user, _run(root, ids, case, command), ids, command)
    await user.open("/activity")
    assert len(user.find("SIMULATED survey B").elements) == 2 * len(LOGS)
    quoted = [e.text for e in user.find("log.txt").elements]
    assert quoted and all("its log, log.txt, cannot be read (" in text.lower() for text in quoted), quoted


async def test_the_page_test_detects_a_log_read_raw(user: User, tmp_path, monkeypatch, caplog):
    """DO-02's negative control: the log read raw again (``engine.read_log`` as the pin's ``tail`` read it), the page
    test fails at a log that is a folder, the page's server error the pin's (``IsADirectoryError``)."""
    from adroit.orchestrator import accounting
    from adroit.ui import engine
    from adroit.ui.app import build_pages

    def raw(folder, lines=40):
        log = Path(folder) / engine.LOG
        return (log.read_text(errors="replace").splitlines()[-lines:] if log.exists() else []), ""
    root = build_pages(tmp_path / "runs")
    service, ids = dl.sessions(tmp_path)
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    monkeypatch.setattr(engine, "read_log", raw)
    with pytest.raises((AssertionError, OSError)):
        await _shows(user, _run(root, ids, "a folder", "discover"), ids, "discover")
    errors = [r for r in caplog.get_records("call") if r.levelname == "ERROR"]
    assert any(r.exc_info and r.exc_info[0] is IsADirectoryError for r in errors), errors
    caplog.clear()                      # the server error expected here, which the fixture fails any test on

"""The auditor's DO recheck (2026-11-09), DP-03, on the Activity page: a run whose log cannot be read (a folder, a link to
one, a file it may not read, a link that leads nowhere), whatever its status, is listed with its log named on its own
card, and diagnosed from its record alone: never a missing dependency for want of a log, with setup offered. The log's
reason had been returned as one of its lines (``engine.tail``), and the diagnosis read a link that led nowhere
(``FileNotFoundError``) as a missing tool; other cards dropped it. The run's outcome names it the same way, apart from
what the command said. A control restores the reason read as a line of the log. Nothing is run."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("nicegui")

from nicegui.testing import User  # noqa: E402

from tests.ui.test_do_run_page import LOGS  # noqa: E402

# each status a run that did not complete may end with, and the diagnosis its record alone establishes
STATUSES = {"failed": ("failed", 1, "failed"), "ended without a word": ("failed", None, "interrupted"),
            "an input refused": ("failed", 2, "input"), "budget stopped": ("budget_stopped", 3, "budget"),
            "cancelled": ("cancelled", -15, "interrupted")}
NAMED = "its log, log.txt, cannot be read ("


def _runs(root: Path) -> list:
    """A run for each log that cannot be read (``LOGS``) and each status (``STATUSES``): their jobs."""
    from adroit.ui import engine
    jobs = []
    for i, case in enumerate(LOGS):
        for j, (status, code, _) in enumerate(STATUSES.values()):
            folder = root / f"{i}-{j}"
            folder.mkdir(parents=True)
            LOGS[case](folder / engine.LOG)
            job = engine.Job(title=f"SIMULATED {case}, {list(STATUSES)[j]}", kind="track1", command=["track1"],
                             folder=str(folder), status=status, returncode=code, finished=engine._now())
            engine.save(job)
            jobs.append(job)
    return jobs


def test_each_run_whose_log_cannot_be_read_is_diagnosed_from_its_record(tmp_path):
    """DP-03, each damage and each status: the diagnosis is the one the run's record establishes, never a missing
    dependency; the log's reason is carried apart, named; the outcome's stop line names it as such."""
    from adroit.orchestrator.recovery import diagnose
    from adroit.ui import engine, outcomes
    for job in _runs(tmp_path / "runs"):
        folder = Path(job.folder)
        lines, unreadable = engine.read_log(folder)
        assert lines == [] and unreadable.startswith(NAMED), (job.title, unreadable)
        found = diagnose(job, lines, folder, unreadable)
        wanted = next(kind for status, code, kind in STATUSES.values()
                      if (status, code) == (job.status, job.returncode))
        assert found.kind == wanted and found.log_unreadable == unreadable, (job.title, found)
        assert found.kind != "dependency" and not any("setup" in a.target for a in found.actions), job.title
        assert not found.evidence, (job.title, found.evidence)
        if job.status in ("failed", "budget_stopped"):
            said = outcomes.unfinished(job, "Run")[1]
            assert NAMED.capitalize() in said and "so why it stopped is not known here" in said, (job.title, said)


def _marked(user: User, marker: str) -> list:
    """The elements on the page with ``marker``, none where there are none (``User.find`` raises there)."""
    try:
        return list(user.find(marker=marker).elements)
    except AssertionError:
        return []


async def _every_card_names_its_log(user: User, jobs: list) -> None:
    """The Activity page: one card for each run, none headed a missing dependency and none offering setup, and each
    card naming its log as one that cannot be read."""
    await user.open("/activity")
    cards = [e for kind in ("failed", "interrupted", "input", "budget", "dependency")
             for e in _marked(user, f"job_{kind}")]
    assert len(cards) == len(jobs), [str(c) for c in cards]
    assert not _marked(user, "job_dependency"), "a log that cannot be read was read as a missing tool"
    await user.should_not_see("missing dependency")
    await user.should_not_see("adroit setup")
    for card in cards:
        named = [e for e in card.descendants() if "unreadable_log" in e._markers]
        assert len(named) == 1 and NAMED in named[0].text.lower(), str(card)


async def test_every_activity_card_names_a_log_that_cannot_be_read(user: User, tmp_path):
    """DP-03 on the page: each of the runs above has its card, naming its log; none says a dependency is missing."""
    from adroit.ui.app import build_pages
    root = tmp_path / "runs"
    jobs = _runs(root)
    build_pages(root)
    await _every_card_names_its_log(user, jobs)


async def test_the_page_test_detects_a_log_s_reason_read_as_its_line(user: User, tmp_path, monkeypatch):
    """DP-03's negative control: the log's reason returned as a line of the log, nothing carried apart (as the pin's
    ``engine.tail`` gave it to the diagnosis): the page test fails, a log that leads nowhere read as a missing tool."""
    from adroit.ui import engine
    from adroit.ui.app import build_pages
    real = engine.read_log

    def as_a_line(folder, lines=40):
        found, unreadable = real(folder, lines)
        return ([unreadable] if unreadable else found), ""
    root = tmp_path / "runs"
    jobs = _runs(root)
    build_pages(root)
    monkeypatch.setattr(engine, "read_log", as_a_line)
    with pytest.raises(AssertionError, match="a log that cannot be read was read as a missing tool"):
        await _every_card_names_its_log(user, jobs)

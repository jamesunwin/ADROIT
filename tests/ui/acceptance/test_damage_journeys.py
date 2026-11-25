"""Acceptance journey 6 of the consolidation plan (M4, begun with M3, 2026-10-25): a history with a damaged sibling of
every kind, then a healthy output opened, through the pages, before and after a restart (the workbench built afresh on
the same runs folder, as a new server would be).

What is substituted: no calculation runs; the healthy study's result and report are written as a finished Track 1 run
leaves them (``SUBSTITUTED`` below). Headless (NiceGUI's ``User``); the real-browser layer is M4's.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from nicegui.testing import User

from adroit.orchestrator import annotations, studies
from adroit.ui import batch, engine

SUBSTITUTED = {"the healthy study's result and report": "written directly as a finished run leaves them; no "
                                                        "calculation runs"}
REPORT = "A healthy report: the run's own words"


def _job(folder: Path, title: str, status: str = "completed") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    running = {"pid": os.getpid(), "acknowledged": True} if status == "running" else {}   # alive: never closed
    engine.save(engine.Job(title=title, kind="track1", folder=str(folder), command=["track1", "--out", "."],
                           status=status, returncode=0 if status == "completed" else None, **running))


@pytest.fixture(scope="module")
def history(tmp_path_factory) -> Path:
    """A runs folder: one healthy study, and beside it a damaged job, study, study graph (a self-child and a
    two-study loop), annotation, batch, batch draft, progress record and cancellation file."""
    root = tmp_path_factory.mktemp("journey6") / "runs"
    healthy = root / "healthy"
    _job(healthy, "the healthy run")
    (healthy / "result.json").write_text(json.dumps({"verdict": {"level": "viable"}}))
    (healthy / "report.md").write_text(f"# The healthy study\n\n{REPORT}\n")
    studies.record(healthy, "track1", "the healthy study")
    (root / "job_damaged").mkdir(parents=True)
    (root / "job_damaged" / engine.JOB).write_text("{}")
    (root / "study_damaged").mkdir()
    (root / "study_damaged" / studies.FILE).write_text("{")
    loop = root / "loop"
    for name in ("a", "b"):
        (loop / name).mkdir(parents=True)
        studies.record(loop / name, "idea", f"loop {name}")
    a, b = studies.load(loop / "a"), studies.load(loop / "b")
    studies.save(a.model_copy(update={"parent": b.folder, "children": [b.folder]}))
    studies.save(b.model_copy(update={"parent": a.folder, "children": [a.folder]}))
    selfish = root / "selfish"
    selfish.mkdir()
    s = studies.record(selfish, "idea", "a study naming itself")
    studies.save(s.model_copy(update={"children": [s.folder]}))
    annotations.save(root, healthy, annotations.Annotation(label="kept"))
    raw = json.loads((root / annotations.FILE).read_text())
    (root / annotations.FILE).write_text(json.dumps({**raw, "study_damaged": {"bogus": 1}}))
    (root / "batches" / "broken").mkdir(parents=True)
    (root / "batches" / "broken" / batch.BATCH).write_text("{")
    (root / batch.DRAFT).write_text("[{")
    _job(root / "going", "a run still going", status="running")
    (root / "going" / "progress.json").write_text("{")
    (root / "going" / engine.CONTROL).write_text("{")
    return root


async def _journey(user: User, root: Path) -> None:
    from adroit.ui.app import build_pages
    build_pages(root)
    await user.open("/")
    await user.open("/studies")
    for marker in ("unreadable_studies", "inconsistent_studies", "unreadable_runs", "unreadable_annotations"):
        await user.should_see(marker=marker)
    for title in ("the healthy study", "loop a", "loop b", "a study naming itself"):
        await user.should_see(title)
    await user.open("/activity")
    await user.should_see(marker="unreadable_runs")
    await user.open("/batches")
    await user.should_see(marker="unreadable_batches")
    await user.should_see(marker="unreadable_draft")
    await user.open("/live?path=going")
    await user.should_see(marker="unreadable_progress")
    await user.open("/live?path=job_damaged")
    await user.should_see("Run record unreadable")
    await user.open("/study?path=healthy")                     # the healthy output, opened
    await user.should_see("the healthy study")
    await user.should_see(REPORT)


async def test_history_with_damaged_siblings_still_opens_its_healthy_output(user: User, history):
    await _journey(user, history)


async def test_after_a_restart_the_same_history_reads_the_same(user: User, history):
    """A new server on the same folder: the damage named again, the healthy output opened again, nothing changed on
    disk by browsing (the damaged files are as they were)."""
    before = {p: p.read_bytes() for p in history.rglob("*") if p.is_file() and not p.name.startswith(".")}
    await _journey(user, history)
    after = {p: p.read_bytes() for p in before}
    assert after == before


def test_the_command_line_lists_the_same_history(history):
    from typer.testing import CliRunner
    from adroit.orchestrator.cli import app
    shown = CliRunner().invoke(app, ["studies", str(history)])
    assert shown.exit_code == 0 and "the healthy study" in shown.output
    assert "unreadable, not listed" in shown.output and "links loop or disagree" in shown.output

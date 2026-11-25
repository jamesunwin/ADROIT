"""The release carries none of its maker's own work (the owner, 2026-11-19): personal models, the personal experimental
library, studies, run records (the Activity page's log), paid ledgers and settings live in ``runs/``, ``projects/`` and
``data/``, which git ignores, so that a clone starts empty. These are the guard: the release checks' fast suite, and
the clean-install test's, fail if a file under one of them is ever tracked, if one stops being ignored, or if a
workbench started on empty folders lists anything.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PERSONAL = ("runs", "projects", "data")


def _git(*arguments: str) -> subprocess.CompletedProcess:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout: what the release tracks is read from git")
    return subprocess.run(["git", "-C", str(ROOT), *arguments], capture_output=True, text=True, timeout=60)


def test_the_release_tracks_no_file_of_its_makers_own_work() -> None:
    tracked = _git("ls-files", "--", *PERSONAL)
    assert tracked.returncode == 0, tracked.stderr
    assert tracked.stdout.split() == [], "tracked under runs/, projects/ or data/: " + tracked.stdout[:400]


@pytest.mark.parametrize("folder", PERSONAL)
def test_each_folder_of_personal_work_is_ignored(folder: str) -> None:
    for path in (f"{folder}/anything.json", f"{folder}/a/study.json"):
        assert _git("check-ignore", "-q", path).returncode == 0, f"{path} is not ignored"


def test_a_workbench_on_empty_folders_lists_nothing(tmp_path, monkeypatch) -> None:
    from adroit.library.personal import Catalog
    from adroit.orchestrator import studies
    from adroit.orchestrator.recovery import attention, summary
    from adroit.ui import engine
    runs, projects = tmp_path / "runs", tmp_path / "projects"
    runs.mkdir()
    monkeypatch.setenv("ADROIT_RUNS_DIR", str(runs))
    monkeypatch.setenv("ADROIT_PROJECTS_DIR", str(projects))
    monkeypatch.setenv("ADROIT_MODEL_LIBRARY_DIR", str(projects / "model_library"))
    assert engine.listing(runs) == ([], [])                       # no run: the Activity page's log is empty
    assert studies.tree(runs) == [] and studies.unreadable(runs) == []
    assert summary(runs) == {"running": 0, "attention": 0} and attention(runs) == {}
    models, damaged = Catalog(projects / "model_library").listing()
    assert list(models) == [] and list(damaged) == []             # no personal model

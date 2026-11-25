"""The running workbench names its version and git revision (the owner's report of 2026-10-23: testing an old
checkout must be apparent), read locally: git, else the repository's files, else "unknown"."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from nicegui.testing import User


def _git(folder: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A small local repository with one commit (no network)."""
    folder = tmp_path / "checkout"
    folder.mkdir()
    _git(folder, "init", "-q", "-b", "main")
    (folder / "a.txt").write_text("one\n")
    _git(folder, "add", "a.txt")
    _git(folder, "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "first")
    return folder


def test_the_revision_is_read_from_git_with_uncommitted_changes(repository: Path) -> None:
    from adroit import __version__
    from adroit.ui.about import read_build
    info = read_build(repository)
    assert info.revision == _git(repository, "rev-parse", "HEAD") and info.branch == "main" and info.source == "git"
    assert info.version == __version__ and info.dirty is False and info.short == info.revision[:7]
    (repository / "a.txt").write_text("two\n")
    assert read_build(repository).dirty is True and read_build(repository).short.endswith("+changes")


def test_without_git_the_repository_files_or_nothing(repository: Path, tmp_path: Path, monkeypatch) -> None:
    """No git on the path: the revision from HEAD and its ref (a worktree's .git file too, and packed refs); a folder
    without a repository says the revision is unknown."""
    from adroit.ui import about
    revision = _git(repository, "rev-parse", "HEAD")
    monkeypatch.setenv("PATH", str(tmp_path / "no-binaries"))
    info = about.read_build(repository)
    assert info.revision == revision and info.branch == "main" and info.source == "repository files"
    assert info.dirty is None and "uncommitted changes unknown" in info.note
    worktree = tmp_path / "worktree"
    gitdir = tmp_path / "gitdir"
    gitdir.mkdir()
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n")
    (gitdir / "HEAD").write_text("ref: refs/heads/feature\n")
    (gitdir / "commondir").write_text("common\n")
    (gitdir / "common").mkdir()
    (gitdir / "common" / "packed-refs").write_text(f"# pack-refs\n{'c' * 40} refs/heads/feature\n")
    assert about.read_build(worktree).revision == "c" * 40
    nothing = about.read_build(tmp_path / "no-binaries")
    assert nothing.revision == "" and nothing.short == "unknown" and nothing.source == "none" and nothing.note


async def test_every_page_shows_the_build_and_the_about_page_details_it(user: User, tmp_path: Path) -> None:
    from adroit.ui.about import build
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    info = build()
    await user.open("/")
    await user.should_see(f"v{info.version} · {info.short}")
    await user.open("/about")
    await user.should_see("About this workbench")
    await user.should_see(info.revision or "unknown")
    await user.should_see(info.checkout)

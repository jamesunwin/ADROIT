"""Tests for the reproducibility stamp (git SHA / dirty flag / timestamp)."""

from __future__ import annotations

import re
from datetime import datetime

import pytest

import adroit.core.repro as repro


@pytest.fixture(autouse=True)
def _fresh_code_state():
    repro.code_state.cache_clear()
    yield
    repro.code_state.cache_clear()


def test_git_stamp_fields_inside_the_repo() -> None:
    stamp = repro.git_stamp()
    assert re.fullmatch(r"[0-9a-f]{40}", stamp["git_sha"])
    assert isinstance(stamp["git_dirty"], bool)
    datetime.fromisoformat(stamp["stamp_time"])  # parses as ISO-8601


def test_git_stamp_outside_a_repo_returns_nones(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(repro, "PROJECT_ROOT", tmp_path)  # not a git repo
    stamp = repro.git_stamp()
    assert stamp["git_sha"] is None and stamp["git_dirty"] is None
    datetime.fromisoformat(stamp["stamp_time"])  # timestamp still present


def test_the_stamp_keeps_the_sha_the_process_started_with(monkeypatch) -> None:
    # A4: a commit made while a long run executes must not relabel the run.
    heads = iter(["a" * 40, "", "b" * 40, ""])
    monkeypatch.setattr(repro, "_git", lambda *args: next(heads))
    first = repro.git_stamp()
    later = repro.git_stamp()                    # HEAD "moved" -- not re-read
    assert first["git_sha"] == later["git_sha"] == "a" * 40
    assert first["git_dirty"] is False
    repro.code_state.cache_clear()               # only an explicit reset re-reads
    assert repro.git_stamp()["git_sha"] == "b" * 40


def test_git_is_asked_with_optional_locks_off(monkeypatch) -> None:
    """``git status`` takes the index lock to refresh it unless optional locks are off; one stopped by the timeout
    leaves the lock, refusing the owner's commits (2026-11-03). Every query this module makes turns them off."""
    import subprocess
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: seen.append(kw.get("env", {})) or
                        subprocess.CompletedProcess(args, 0, "a" * 40, ""))
    repro.code_state()
    assert seen and all(env.get("GIT_OPTIONAL_LOCKS") == "0" for env in seen)

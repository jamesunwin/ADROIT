"""Reproducibility stamps: tie every run and paid launch to an exact commit.

The July 2026 paid evaluations were made from an uncommitted working tree,
leaving an LLM-response cache no commit can regenerate. These helpers make
that impossible to repeat unnoticed: every pipeline run's ``meta.json`` and
every confirmed evaluation launch records the git SHA and whether the tree
was dirty, and the harness refuses to spend money from a dirty tree.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from functools import lru_cache

from adroit.core.config import child_environment
from adroit.core.config import PROJECT_ROOT


def _git(*args: str) -> str | None:
    """Run a git command at the project root; None on any failure (never raises). Optional locks are off
    (``GIT_OPTIONAL_LOCKS=0``, as ``ui.about`` reads git): ``git status`` otherwise takes the checkout's index lock to
    refresh it, and one stopped by the timeout leaves that lock behind, which then refuses the owner's own commits
    (found 2026-11-03, on a loaded machine: a stale ``index.lock`` in a worktree after a test run)."""
    try:
        out = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True,
                             text=True, timeout=10, env=child_environment({"GIT_OPTIONAL_LOCKS": "0"}))
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


@lru_cache(maxsize=1)
def code_state() -> tuple[str | None, bool | None]:
    """(HEAD sha, dirty) as first seen by this process: the code it loaded.

    Cached for the process lifetime and primed at import, so a commit made
    while a long run is executing cannot relabel it. R6's later cells were
    stamped with a docs commit made mid-run although the process ran ed1a700
    (A4). ``code_state.cache_clear()`` re-reads (tests only).
    """
    sha = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain") if sha is not None else None
    return sha, (bool(status.strip()) if status is not None else None)


code_state()  # prime: the stamp describes the code at process start


def git_stamp() -> dict:
    """A reproducibility stamp: {'git_sha', 'git_dirty', 'stamp_time'}.

    ``git_sha`` / ``git_dirty`` describe the code this process loaded (HEAD and
    tree state at process start, see :func:`code_state`; None outside a repo);
    ``stamp_time`` is the current ISO-8601 UTC time. Never raises.
    """
    sha, dirty = code_state()
    return {"git_sha": sha, "git_dirty": dirty,
            "stamp_time": datetime.now(timezone.utc).isoformat()}

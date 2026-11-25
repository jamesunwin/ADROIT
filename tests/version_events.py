"""Where a test puts a publication against the version handle (``adroit.evidence.version``): just after a consumer has
resolved its version (``after_resolution``: what it then shows or does must be that version's, never the folder's now),
or while it resolves, after one of the study's files was read (``during_resolution``: the whole read is made again, so
it is all of the publication after). The handle reads the folder in one transaction, so a test's publication goes at
one of these two places, not between two of a consumer's reads, which it no longer makes."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


@contextmanager
def after_resolution(action, times: int = 1):
    """``action()`` run just after each of the first ``times`` resolutions returns; yields the versions resolved."""
    from adroit.evidence import version
    real, resolved = version.resolve, []

    def resolve(*args, **kwargs):
        found = real(*args, **kwargs)
        resolved.append(found)
        if len(resolved) <= times:
            action()
        return found
    with patch.object(version, "resolve", resolve):
        yield resolved


@contextmanager
def during_resolution(name: str, action):
    """``action()`` run once, just after a resolution has read the study's file ``name`` (``result.json``,
    ``study.json``, ``report.md``, ``result.evidence.json``) the first time; yields whether it ran."""
    from adroit.evidence import version
    real, done = version._read, []

    def read(path, limit=None):
        found = real(path, limit)
        if Path(path).name == name and not done:
            done.append(True)
            action()
        return found
    with patch.object(version, "_read", read):
        yield done

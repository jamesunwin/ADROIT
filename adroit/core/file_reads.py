"""A file read as one version (the auditor's CU recheck, CV-03 and CV-04, 2026-10-28).

A version of a file is named by its identity: its device and inode, its size, and its modification and change times
(``identity``). A replacement gives a new inode or change time even where it keeps the size and the modification time,
as a copy that preserves timestamps does; size and modification time alone had named two contents as one, and the
history went on reading a replaced equation-of-state table as the published one (CV-03).

``read`` returns the bytes of the version asked for, read through one open descriptor whose identity is that version
before and after the read, or raises ``Moved``. A cache kept by identity therefore holds the bytes of exactly the
version it is keyed by, however its entries are evicted and refilled: a value and a hash cached apart, each by the same
identity, are of the same bytes (CV-04: an evicted value had been read again from a replaced file and joined to the
hash of the file it replaced). ``consistent`` asks for the version the file is now, and again where it changes
meanwhile.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
TRIES = 5


class Moved(Exception):
    """The file is no longer the version asked for, or changed while it was read."""


def identity(stat: os.stat_result) -> tuple[int, int, int, int, int]:
    """A file's version: its device, inode, size, and modification and change times (ns)."""
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def stamp(path) -> tuple[str, int, int, int]:
    """A file as it is now, for a cache kept by what the file is rather than by its name: its resolved path, size, and
    modification and change times (ns), any write moving the last (the auditor's bounded-interfaces audit, BI-02,
    2026-11-12: tables cached by name had kept a replaced table's values in a warm process). As ``spectra.table``."""
    from pathlib import Path
    path = Path(path)
    stat = path.stat()
    return str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def read(path: str, version: tuple[int, ...]) -> bytes:
    """The bytes of ``path`` in the version ``version`` (``identity``); ``Moved`` where the file open is another
    version, before or after the read."""
    with open(path, "rb") as handle:
        before = identity(os.fstat(handle.fileno()))
        content = handle.read()
        after = identity(os.fstat(handle.fileno()))
    if before != tuple(version) or after != tuple(version):
        raise Moved(path)
    return content


def consistent(path: str, use: Callable[..., T]) -> T:
    """``use(*version)`` with the version of ``path`` now (``identity``), asked again where the file changes before
    ``use`` has read it (``Moved``); ``OSError`` where the file does not settle in ``TRIES`` attempts, or cannot be
    read."""
    for _ in range(TRIES):
        try:
            return use(*identity(os.stat(path)))
        except Moved:
            continue
    raise OSError(f"{path} changed each time it was read ({TRIES} attempts)")

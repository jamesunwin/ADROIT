"""A file read as one version (``core.file_reads``; the auditor's CU recheck, CV-03 and CV-04, 2026-10-28)."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from adroit.core import file_reads


def test_a_replacement_keeping_size_and_modification_time_is_another_version(tmp_path):
    """A file renamed over another, or rewritten in place, its size and modification time kept, is another version:
    its inode or its change time differs."""
    path = tmp_path / "table.dat"
    path.write_bytes(b"1 2 3\n")
    before = path.stat()
    fresh = tmp_path / "table.new"
    fresh.write_bytes(b"1 2 4\n")
    os.replace(fresh, path)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    replaced = path.stat()
    assert (replaced.st_size, replaced.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert file_reads.identity(replaced) != file_reads.identity(before)
    path.write_bytes(b"1 2 5\n")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert file_reads.identity(path.stat()) not in (file_reads.identity(before), file_reads.identity(replaced))


def test_a_read_gives_the_version_asked_for_or_moved(tmp_path):
    """The bytes of the version asked for; ``Moved`` where the file is another version."""
    path = tmp_path / "data.yaml"
    path.write_bytes(b"a: 1\n")
    version = file_reads.identity(path.stat())
    assert file_reads.read(str(path), version) == b"a: 1\n"
    path.write_bytes(b"a: 2\n")
    with pytest.raises(file_reads.Moved):
        file_reads.read(str(path), version)


def test_a_file_changed_between_its_stat_and_its_read_is_read_in_its_new_version(tmp_path):
    """``consistent`` asks again for the version the file is now where it changed before its read, so what is read
    is one version's bytes, named by that version; a file that never settles is an ``OSError``."""
    path = tmp_path / "data.yaml"
    path.write_bytes(b"a: 1\n")
    real, changes = os.stat, iter([b"a: 2\n"])

    def stat_then_change(target, *args, **kwargs):
        out = real(target, *args, **kwargs)
        if os.fspath(target) == str(path) and (content := next(changes, None)) is not None:
            path.write_bytes(content)
        return out
    with patch.object(os, "stat", stat_then_change):
        version, content = file_reads.consistent(str(path), lambda *v: (v, file_reads.read(str(path), v)))
    assert content == b"a: 2\n" and version == file_reads.identity(path.stat())

    def always(target, *args, **kwargs):
        out = real(target, *args, **kwargs)
        if os.fspath(target) == str(path):
            path.write_bytes(path.read_bytes() + b"#")
        return out
    with patch.object(os, "stat", always), pytest.raises(OSError, match="changed each time it was read"):
        file_reads.consistent(str(path), lambda *v: file_reads.read(str(path), v))

"""The checkpoint writer published whole and synced (the gap plan's G1, 2026-10-25, with the owner's acceptance
criteria): the same bytes as before; the file synced before it replaces the old one and the folder after; a
serialisation, file-sync or replacement failure leaving the old file whole and no temporary file; an unsupported
directory sync tolerated and stated, a real I/O error raised."""
from __future__ import annotations

import errno
import json
import math
import os
import stat
import tempfile
from pathlib import Path

import pytest

from adroit.core import durable
from adroit.core.checkpoint import Checkpoint, atomic_json

CORPUS = [{"a": 1, "b": [1.5, -0.0, 1e-300, 1e300]}, {"nan": math.nan, "inf": math.inf, "minus": -math.inf},
          {"text": "Ωh² ≈ 0.12 — Saikawa & Shirai, μ, 𝒪(1)", "nested": {"x": [{"y": None, "z": True}]}}, {}]


def _previous(path: Path, value: dict) -> None:
    """The writer before G1, kept here to compare its bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, suffix=".tmp", delete=False,
                                     encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=True)
        name = Path(stream.name)
    name.replace(path)


def _leftovers(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir() if p.name.endswith(".tmp"))


@pytest.mark.parametrize("value", CORPUS)
def test_the_bytes_are_those_the_previous_writer_wrote(tmp_path, value):
    atomic_json(tmp_path / "new.json", value)
    _previous(tmp_path / "old.json", value)
    assert (tmp_path / "new.json").read_bytes() == (tmp_path / "old.json").read_bytes()
    assert _leftovers(tmp_path) == []


def test_the_file_is_synced_before_it_replaces_the_old_one_and_the_folder_after(tmp_path, monkeypatch):
    events = []
    fsync, replace = os.fsync, os.replace

    def recorded_fsync(fd):
        events.append(("fsync", "folder" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"))
        return fsync(fd)

    def recorded_replace(a, b):
        events.append(("replace", Path(b).name))
        return replace(a, b)
    monkeypatch.setattr(os, "fsync", recorded_fsync)
    monkeypatch.setattr(os, "replace", recorded_replace)
    atomic_json(tmp_path / "progress.json", {"phase": "scan"})
    assert events == [("fsync", "file"), ("replace", "progress.json"), ("fsync", "folder")]


def _old(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    atomic_json(path, {"identity": "old"})
    return path


def test_a_value_that_cannot_be_serialised_leaves_the_old_file_and_no_temporary_one(tmp_path):
    path = _old(tmp_path)
    with pytest.raises(TypeError):
        atomic_json(path, {"identity": object()})
    assert json.loads(path.read_text()) == {"identity": "old"} and _leftovers(tmp_path) == []


def test_a_failed_file_sync_leaves_the_old_file_and_no_temporary_one(tmp_path, monkeypatch):
    path = _old(tmp_path)
    fsync = os.fsync

    def failing(fd):
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(errno.EIO, "input/output error")
        return fsync(fd)
    monkeypatch.setattr(os, "fsync", failing)
    with pytest.raises(OSError, match="input/output"):
        atomic_json(path, {"identity": "new"})
    assert json.loads(path.read_text()) == {"identity": "old"} and _leftovers(tmp_path) == []


def test_a_failed_replacement_leaves_the_old_file_and_no_temporary_one(tmp_path, monkeypatch):
    path = _old(tmp_path)

    def failing(a, b):
        raise OSError(errno.EXDEV, "cross-device link")
    monkeypatch.setattr(os, "replace", failing)
    with pytest.raises(OSError, match="cross-device"):
        atomic_json(path, {"identity": "new"})
    assert json.loads(path.read_text()) == {"identity": "old"} and _leftovers(tmp_path) == []


def _folder_sync(monkeypatch, code: int) -> None:
    fsync = os.fsync

    def folder_fails(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(code, os.strerror(code))
        return fsync(fd)
    monkeypatch.setattr(os, "fsync", folder_fails)


@pytest.mark.parametrize("code", [errno.EINVAL, errno.ENOTSUP])
def test_an_unsupported_folder_sync_is_tolerated_and_stated(tmp_path, monkeypatch, code):
    monkeypatch.setattr(durable, "folder_sync_unsupported", {})
    _folder_sync(monkeypatch, code)
    with pytest.warns(RuntimeWarning, match="does not support syncing a directory"):
        atomic_json(tmp_path / "progress.json", {"phase": "scan"})
    assert json.loads((tmp_path / "progress.json").read_text()) == {"phase": "scan"}
    assert errno.errorcode[code] in durable.folder_sync_unsupported[str(tmp_path)]


def test_a_real_io_error_syncing_the_folder_is_raised(tmp_path, monkeypatch):
    _folder_sync(monkeypatch, errno.EIO)
    with pytest.raises(OSError, match=os.strerror(errno.EIO)):
        atomic_json(tmp_path / "progress.json", {"phase": "scan"})
    # the record was already replaced whole; what is not known is whether its name reached the disk
    assert json.loads((tmp_path / "progress.json").read_text()) == {"phase": "scan"}


def test_a_checkpoint_still_holds_its_run_lock(tmp_path):
    """Publishing whole does not prevent lost updates: the checkpoint keeps its run lock (``run_lock``)."""
    from adroit.core.checkpoint import run_lock
    with run_lock(tmp_path):
        with pytest.raises(RuntimeError):
            with run_lock(tmp_path):
                pass
    checkpoint = Checkpoint(tmp_path / "run", {"x": 1}, {"code": "a"})
    checkpoint.save("scan", "0", durable.Unreadable(path="p", why="w"))
    assert checkpoint.load("scan", "0", durable.Unreadable).why == "w"

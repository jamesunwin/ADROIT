"""Durable records (the consolidation plan's M3): a record published whole, a shared record changed under a lock, and
a damaged record that an operation depends on stopping it with the reason."""
from __future__ import annotations

import json
import threading
import time

import pytest

from adroit.core import durable


def test_a_record_is_published_whole_and_its_folder_made(tmp_path):
    path = durable.write_atomic(tmp_path / "new" / "record.json", '{"a": 1}')
    assert path.read_text() == '{"a": 1}' and not list(path.parent.glob("*.tmp"))
    durable.write_atomic(path, b'{"a": 2}')
    assert json.loads(path.read_text()) == {"a": 2}


@pytest.mark.parametrize("step", ["os.fsync", "os.replace"])
def test_a_write_cut_short_leaves_the_previous_record_and_no_temporary_file(tmp_path, monkeypatch, step):
    path = durable.write_atomic(tmp_path / "record.json", "before")

    def cut(*args):
        raise OSError("disk full")
    monkeypatch.setattr(step, cut)
    with pytest.raises(OSError):
        durable.write_atomic(path, "after")
    monkeypatch.undo()
    assert path.read_text() == "before" and not list(tmp_path.glob(".record.json.*"))


def test_a_read_modify_write_under_the_lock_loses_no_update(tmp_path):
    """Publishing whole does not prevent a lost update; the lock does: ten writers, each reading the list, waiting,
    and writing it back with its own entry added, all kept."""
    path = durable.write_atomic(tmp_path / "shared.json", "[]")

    def add(n: int) -> None:
        with durable.lock(tmp_path / ".shared.lock"):
            items = json.loads(path.read_text())
            time.sleep(0.01)
            durable.write_atomic(path, json.dumps(items + [n]))
    threads = [threading.Thread(target=add, args=(n,)) for n in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(json.loads(path.read_text())) == list(range(10))


def test_a_damaged_record_is_a_refused_input_naming_itself_and_what_to_do(tmp_path):
    error = durable.DamagedRecord(tmp_path / "x.json", "JSONDecodeError: torn", "repair it")
    assert isinstance(error, ValueError) and str(error) == f"{tmp_path / 'x.json'} cannot be read (JSONDecodeError: torn): repair it"


def test_the_lock_for_a_package_record_lives_in_the_runs_folder(tmp_path, monkeypatch):
    from adroit.constraints import database
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(), "runs_dir", tmp_path / "runs")
    found = durable.lock_for(database.RECORDS)
    assert found.parent == tmp_path / "runs" / ".adroit" / "locks" and found.name.startswith("records.yaml.")

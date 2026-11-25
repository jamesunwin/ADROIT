"""The owner (2026-11-22): scans had run their points in at most two processes, leaving most of a machine's cores idle
(8–12 hour scans). The count is a setting now, ``ADROIT_SCAN_WORKERS`` (default: the cores less two), applied at run
time so that a run's request, and its checkpoint identity, do not change with the machine."""
import os

import pytest

from adroit.core import config
from adroit.parameter_space import scan


def test_the_default_is_the_cores_less_two_and_a_setting_is_checked(monkeypatch) -> None:
    monkeypatch.delenv("ADROIT_SCAN_WORKERS", raising=False)
    monkeypatch.setattr(config, "variable", lambda name: os.environ.get(name))       # no .env read
    monkeypatch.setattr(os, "cpu_count", lambda: 10)
    assert config._scan_workers() == 8
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    assert config._scan_workers() == 1                                             # never below one
    monkeypatch.setenv("ADROIT_SCAN_WORKERS", "6")
    assert config._scan_workers() == 6
    for bad in ("0", "-3", "many"):
        monkeypatch.setenv("ADROIT_SCAN_WORKERS", bad)
        with pytest.raises(ValueError, match="ADROIT_SCAN_WORKERS"):
            config._scan_workers()


def test_one_worker_stays_serial_and_otherwise_the_setting_applies(monkeypatch) -> None:
    monkeypatch.setattr(config.get_settings(), "scan_workers", 7)
    assert scan.worker_count(1) == 1 and scan.worker_count(2) == 7
    assert scan.ScanRequest.model_fields["workers"].metadata[-1].le >= 64          # the schema allows the setting


def test_the_pools_workers_use_one_numerical_thread_each_and_the_setting_is_restored(monkeypatch) -> None:
    for name in scan.THREAD_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OMP_NUM_THREADS", "4")                                      # the person's own setting stays
    with scan.one_thread_each():
        assert os.environ["OMP_NUM_THREADS"] == "4" and os.environ["OPENBLAS_NUM_THREADS"] == "1"
    assert "OPENBLAS_NUM_THREADS" not in os.environ and os.environ["OMP_NUM_THREADS"] == "4"


def test_a_track1_request_keeps_its_own_worker_field() -> None:
    """The checkpoint identity hashes the request: its default is unchanged, so a run started before this change still
    resumes after it."""
    from adroit.orchestrator.track1 import Track1Request
    assert Track1Request.model_fields["workers"].default == 2

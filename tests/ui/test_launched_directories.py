"""A run reads the folders its launch read (an operating-conditions audit's IE-01, 2026-11-10; ``config``'s and
``engine``'s module docstrings).

The auditor launched from a foreign folder, "foreign A", with ``ADROIT_MODEL_LIBRARY_DIR=audit_relative/...`` (and the
other five directory settings so): the workbench read ``foreign A/audit_relative/...``, its run, started in the
project's folder, read the project's ``audit_relative/...``, and the job completed. Here the same settings, from a
folder with a space in its name, through the real engine, runner and gate, the command line a stand-in that writes the
settings it reads; and through a resume and a batch's start, whose processes are recorded, not started."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from adroit.core import config
from adroit.ui import batch, engine

READ = '''
import json, os
from pathlib import Path
from adroit.core.config import DIRECTORIES, get_settings
settings = get_settings()
read = {field: str(getattr(settings, field)) for field in DIRECTORIES.values()}
(Path(os.environ["ADROIT_JOB_FOLDER"]) / "read.json").write_text(json.dumps({"cwd": os.getcwd(), **read}))
'''

RUNNER = '''
import sys
from pathlib import Path
from adroit.ui import runner
gate = runner.GATE.replace("'-m', 'adroit.orchestrator.cli', ", repr(sys.argv[3]) + ", ")
assert gate != runner.GATE
runner.GATE = gate
runner.run(Path(sys.argv[1]), sys.argv[2])
'''


def _relative(monkeypatch, folder: Path, label: str) -> None:
    """Start "here" in ``folder``, every directory setting relative (``<label> relative/<name>``)."""
    folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(folder)
    for name in config.DIRECTORIES:
        monkeypatch.setenv(config.ENV_PREFIX + name, f"{label} relative/{name.lower()}")
    config.get_settings.cache_clear()


@pytest.fixture
def foreign(tmp_path, monkeypatch):
    folder = tmp_path / "foreign A"
    _relative(monkeypatch, folder, "audit")
    yield folder
    config.get_settings.cache_clear()          # the next reading is the environment's, restored


def _expected(folder: Path, label: str) -> dict[str, str]:
    return {field: str(folder / f"{label} relative" / name.lower()) for name, field in config.DIRECTORIES.items()}


def test_a_relative_directory_is_read_once_against_the_starting_folder(foreign):
    settings = config.get_settings()
    assert {field: str(getattr(settings, field)) for field in config.DIRECTORIES.values()} == _expected(foreign, "audit")
    assert config.launched() == {config.ENV_PREFIX + name: str(foreign / "audit relative" / name.lower())
                                 for name in config.DIRECTORIES}


def test_a_launched_run_reads_the_folders_its_launch_read(foreign, tmp_path):
    """The real runner and gate, started as ``engine`` starts them (in the project's folder, detached): the command
    line reads the six folders the launch read, under "foreign A", not the project's."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "read.py").write_text(READ)
    (scripts / "runner.py").write_text(RUNNER)
    started = []

    def popen(argv, **kwargs):
        started.append(subprocess.Popen([sys.executable, str(scripts / "runner.py"), *argv[-2:],
                                         str(scripts / "read.py")], **kwargs))
        return started[-1]
    folder = tmp_path / "job"
    engine.launch(["track1", "fixture.yaml"], folder, "the settings it reads", popen=popen)
    deadline = time.monotonic() + 60
    while engine.poll(folder).status == "running" and time.monotonic() < deadline:
        time.sleep(0.1)
    started[0].wait(timeout=30)
    assert engine.load(folder).status == "completed", (folder / engine.LOG).read_text()
    read = json.loads((folder / "read.json").read_text())
    assert Path(read.pop("cwd")).resolve() == config.PROJECT_ROOT.resolve()     # it did start elsewhere
    assert read == _expected(foreign, "audit")
    assert engine.load(folder).directories == config.launched()


def _recorded(calls: list):
    """A ``popen`` that records what it is given and starts nothing."""
    def popen(argv, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(pid=os.getpid())
    return popen


def _interrupted(folder: Path, directories: dict[str, str] | None) -> None:
    """An interrupted Track 1 job with a checkpoint, of a launch that read ``directories`` (None: a job from before)."""
    (folder / ".track1-checkpoint").mkdir(parents=True)
    (folder / ".track1-checkpoint" / "manifest.json").write_text("{}")
    engine.save(engine.Job(title="interrupted", kind="track1", command=["track1", "m.yaml"], folder=str(folder),
                           status="cancelled", directories=directories or {}))


def test_a_resume_gives_its_run_the_folders_of_its_launch(foreign, tmp_path, monkeypatch):
    """Resumed from another folder with other relative settings, the run is given its launch's; a job from before
    (no folders recorded) is given the resuming process's own, and keeps them."""
    calls = []
    folder = tmp_path / "job"
    launched_with = config.launched()
    _interrupted(folder, launched_with)
    _relative(monkeypatch, tmp_path / "foreign B", "other")
    assert config.launched() != launched_with
    engine.resume(folder, popen=_recorded(calls))
    assert {k: calls[-1]["env"][k] for k in launched_with} == launched_with
    assert calls[-1]["cwd"] == str(config.PROJECT_ROOT) and engine.load(folder).directories == launched_with
    older = tmp_path / "older"
    _interrupted(older, None)
    engine.resume(older, popen=_recorded(calls))
    assert {k: calls[-1]["env"][k] for k in launched_with} == config.launched()
    assert engine.load(older).directories == config.launched()


def test_a_batch_gives_its_runner_the_folders_of_its_start_and_again_on_resume(foreign, tmp_path, monkeypatch):
    """The batch runner starts in the project's folder and launches each request from there (``engine.launch`` in its
    own process): it is given the folders its batch's start read, at its start and at a resume from elsewhere."""
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")

    def fails(*a, **k):
        raise OSError("no process")
    started_with = config.launched()
    with pytest.raises(OSError):
        batch.start(root, "a batch", popen=fails)
    (b,) = batch.batches(root)
    assert b.directories == started_with
    _relative(monkeypatch, tmp_path / "foreign B", "other")
    calls = []
    batch.resume(Path(b.folder), popen=_recorded(calls))
    assert {k: calls[-1]["env"][k] for k in started_with} == started_with
    assert calls[-1]["cwd"] == str(config.PROJECT_ROOT)


def test_absolute_settings_are_kept_as_they_are(tmp_path, monkeypatch):
    """The auditor's absolute settings, which had agreed: unchanged, spaces and all."""
    for name in config.DIRECTORIES:
        monkeypatch.setenv(config.ENV_PREFIX + name, str(tmp_path / "an absolute folder" / name.lower()))
    config.get_settings.cache_clear()
    try:
        assert config.launched() == {config.ENV_PREFIX + name: str(tmp_path / "an absolute folder" / name.lower())
                                     for name in config.DIRECTORIES}
    finally:
        config.get_settings.cache_clear()

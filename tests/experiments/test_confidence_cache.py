"""Native and new confidence levels must never share an inference result."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from adroit.core.dm_state import DarkMatterParticle, ExpectedSignal
from adroit.experiments import xenon


def test_diamx_cache_separates_cl_and_backend_identity(tmp_path, monkeypatch):
    folder = tmp_path / "diamx"
    (folder / "diamx").mkdir(parents=True)
    source = folder / "diamx" / "context.py"
    source.write_text("version = 1")
    module = object.__new__(xenon.DiamxXenon)
    module.folder, module.python, module.batch_size = folder, tmp_path / "python", 100
    module.search = "LZ WS2022+WS2024"
    module.spec = xenon.SEARCHES[module.search]
    monkeypatch.setattr(xenon, "get_settings", lambda: SimpleNamespace(tools_dir=tmp_path))
    calls = []
    def run(command, **kwargs):
        request = json.loads(Path(command[2]).read_text())
        calls.append(request)
        Path(command[3]).write_text(json.dumps([
            {"label": label, "upper": request["confidence_level"]} for label in request["labels"]]))
    monkeypatch.setattr(xenon.subprocess, "run", run)
    signal = ExpectedSignal(experiment=module.search, particle=DarkMatterParticle(mass_gev=10),
        interaction_id="test", total_events=100, observable=xenon.ENERGIES_KEV.tolist(),
        density=[1.] * len(xenon.ENERGIES_KEV))
    first = module.run([signal], .9)
    second = module.run([signal], .95)
    assert first != second and len(calls) == 2
    assert module.run([signal], .95) == second and len(calls) == 2
    source.write_text("version = 2")
    module.run([signal], .95)
    assert len(calls) == 3
    # A partial cache is not a successful completed batch, and malformed fresh
    # output cannot enter the envelope as a valid limit.
    for result in tmp_path.glob("diamx-work/*/result-*.json"):
        result.write_text("[]")
    module.run([signal], .95)
    assert len(calls) == 4
    source.write_text("version = 3")
    def incomplete(command, **kwargs):
        Path(command[3]).write_text("[]")
    monkeypatch.setattr(xenon.subprocess, "run", incomplete)
    with pytest.raises(RuntimeError, match="incomplete"):
        module.run([signal], .95)


def test_a_finished_diamx_result_is_read_without_the_lock(tmp_path, monkeypatch):
    """Another process holding the lock for a long run must not stop a cache hit; a partly written result
    still waits for the lock."""
    folder = tmp_path / "diamx"
    (folder / "diamx").mkdir(parents=True)
    module = object.__new__(xenon.DiamxXenon)
    module.folder, module.python, module.batch_size = folder, tmp_path / "python", 100
    module.search = "LZ WS2022+WS2024"
    module.spec = xenon.SEARCHES[module.search]
    monkeypatch.setattr(xenon, "get_settings", lambda: SimpleNamespace(tools_dir=tmp_path))
    def run(command, **kwargs):
        request = json.loads(Path(command[2]).read_text())
        Path(command[3]).write_text(json.dumps([{"label": label, "upper": 2.0} for label in request["labels"]]))
    monkeypatch.setattr(xenon.subprocess, "run", run)
    signal = ExpectedSignal(experiment=module.search, particle=DarkMatterParticle(mass_gev=10),
        interaction_id="test", total_events=100, observable=xenon.ENERGIES_KEV.tolist(),
        density=[1.] * len(xenon.ENERGIES_KEV))
    first = module.run([signal], .9)
    locks = []
    monkeypatch.setattr(xenon.fcntl, "flock", lambda fd, how: locks.append(how))
    assert module.run([signal], .9) == first and locks == []
    for result in tmp_path.glob("diamx-work/*/result-*.json"):
        result.write_text('[{"label": ')
    assert module.run([signal], .9) == first and len(locks) == 1

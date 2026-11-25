"""What DIAMX reads beyond its request, in its result cache's identity and its tables' fingerprint (an operational
audit's IA-01, 2026-11-10; ``xenon.diamx_inputs``, ``xenon.diamx_versions``).

The auditor's control: the real ``DiamxXenon.upper_limit``, its request, cache file and validation, DIAMX's subprocess
alone replaced by a stand-in whose answer is the detector data's value plus the runtime's. Its limit was 3; with the
data changed, warm 3 and fresh 8; with the runtime changed, warm 8 and fresh 12. Now each change is a miss, warm equals
fresh, and DIAMX's own generated caches and ADROIT's work folder leave the identity alone."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from adroit.core.dm_state import DarkMatterParticle, ExpectedSignal
from adroit.experiments import xenon


class _Diamx:
    """A DIAMX installation in a folder of its own, its subprocess a stand-in (module docstring)."""

    def __init__(self, root: Path, monkeypatch) -> None:
        self.tools = root / "tools"
        self.folder = self.tools / "diamx"
        (self.folder / "diamx/data").mkdir(parents=True)
        (self.folder / "config").mkdir()
        self.source = self.folder / "diamx/model.py"
        self.source.write_text("version = 1\n")
        self.data = self.folder / "diamx/data/lz_ws2024_wimp_data.csv"
        self.data.write_text("2\n")
        self.config = self.folder / "config/lz_ws2024_wimp_config.json"
        self.config.write_text("{}")
        self.python = self.tools / ".venv-diamx/bin/python"
        self.python.parent.mkdir(parents=True)
        self.python.write_text("runtime 1")
        self.library = self.tools / ".venv-diamx/lib/python3.12/site-packages/numerics.py"
        self.library.parent.mkdir(parents=True)
        self.library.write_text("0")
        module = object.__new__(xenon.DiamxXenon)
        module.folder, module.python, module.batch_size = self.folder, self.python, 100
        module.search = "LZ WS2022+WS2024"
        module.spec = xenon.SEARCHES[module.search]
        self.module, self.calls = module, []
        monkeypatch.setattr(xenon, "get_settings", lambda: SimpleNamespace(tools_dir=self.tools))
        monkeypatch.setattr(xenon.subprocess, "run", self._backend)
        self.signal = ExpectedSignal(experiment=module.search, particle=DarkMatterParticle(mass_gev=10),
                                     interaction_id="fixture", total_events=100,
                                     observable=xenon.ENERGIES_KEV.tolist(), density=[1.0] * len(xenon.ENERGIES_KEV))

    def copied(self, command, path: Path) -> Path:
        """``path`` of the installation in the generation's copy the command runs from (its driver's folder): where
        DIAMX reads it (``xenon.stage``)."""
        return Path(command[1]).parent / path.relative_to(self.folder)

    def _backend(self, command, **kwargs):
        request = json.loads(Path(command[2]).read_text())
        value = (float(self.copied(command, self.data).read_text()) + int(self.python.read_text().split()[-1])
                 + float(self.library.read_text()))
        self.calls.append(value)
        Path(command[3]).write_text(json.dumps([{"label": label, "upper": value} for label in request["labels"]]))

    def limit(self) -> float:
        return self.module.upper_limit(self.signal)

    def fresh(self) -> float:
        """The limit with every cached result removed."""
        for path in (self.tools / "diamx-work").rglob("result-*.json"):
            path.unlink()
        return self.limit()


@pytest.fixture
def diamx(tmp_path, monkeypatch):
    return _Diamx(tmp_path, monkeypatch)


def test_unchanged_inputs_reuse_the_cached_limit(diamx):
    assert diamx.limit() == diamx.limit() == 3 and len(diamx.calls) == 1


@pytest.mark.parametrize("change", ["detector data", "interpreter", "runtime library", "source", "configuration"])
def test_each_input_s_change_is_a_miss_and_the_warm_limit_equals_the_fresh_one(diamx, change):
    """The auditor's data and runtime changes (now misses, warm equal to fresh) beside its source and configuration
    controls (misses before as now)."""
    assert diamx.limit() == 3
    if change == "detector data":
        diamx.data.write_text("7\n")
    elif change == "interpreter":
        diamx.python.write_text("runtime 5")
    elif change == "runtime library":
        diamx.library.write_text("4")
    elif change == "source":
        diamx.source.write_text("version = 2\n")
    else:
        diamx.config.write_text('{"changed": true}')
    warm = diamx.limit()
    assert len(diamx.calls) == 2 and warm == diamx.fresh()
    assert diamx.limit() == warm and len(diamx.calls) == 3                     # then reused again (fresh made one)


def test_generated_caches_beside_the_package_and_the_work_folder_leave_the_identity_alone(diamx):
    """DIAMX's own template cache (``pdf_cache``, beside its package) and ADROIT's work folder change as DIAMX runs:
    in the identity, every call would be a miss."""
    assert diamx.limit() == 3
    (diamx.folder / "pdf_cache").mkdir()
    (diamx.folder / "pdf_cache/0123").write_text("a template")
    (diamx.tools / "diamx-work" / "notes.txt").write_text("written by a run")
    assert diamx.limit() == 3 and len(diamx.calls) == 1


def _versions(diamx) -> tuple[list[str], str]:
    files, runtime = xenon.diamx_versions(diamx.folder, diamx.python)
    return [str(f.relative_to(diamx.folder)) for f in files], runtime


def test_a_table_s_fingerprint_takes_the_package_s_data_and_the_runtime_s_versions(diamx):
    """``limit_tables``' DIAMX inputs (``diamx_versions``): the bundled data byte for byte and the distributions'
    names and versions; not what a machine's own build makes, nor DIAMX's generated spectra, so a table computed on
    one machine is current on another with the same installation."""
    (diamx.library.parent / "jax-0.4.30.dist-info").mkdir()
    files, runtime = _versions(diamx)
    assert files == ["diamx/data/lz_ws2024_wimp_data.csv", "diamx/model.py"]
    assert json.loads(runtime) == {"python": ["python3.12"], "distributions": ["jax-0.4.30.dist-info"]}
    for built in ("diamx/nestDiamx.cpython-312-darwin.so", "diamx/nest/libnestDiamxCore.a",
                  "diamx/nest/CMakeFiles/x.dir/flags.make", "diamx/nest/cmake_install.cmake",
                  "diamx/data/wimp_200GeV.json", "diamx/__pycache__/model.cpython-312.pyc"):
        (diamx.folder / built).parent.mkdir(parents=True, exist_ok=True)
        (diamx.folder / built).write_text("made here")
    assert _versions(diamx) == (files, runtime)
    shutil.move(diamx.library.parent / "jax-0.4.30.dist-info", diamx.library.parent / "jax-0.4.31.dist-info")
    assert _versions(diamx)[1] != runtime
    (diamx.folder / "diamx/data/new_background.h5").write_text("data")
    assert "diamx/data/new_background.h5" in _versions(diamx)[0]


@pytest.mark.needs("diamx")
def test_a_table_s_fingerprint_moves_with_diamx_s_data(monkeypatch, tmp_path):
    """On the installed DIAMX: its data and its runtime's versions enter the xenon tables' fingerprint (read through
    ``diamx_versions``, which the fingerprint calls), and nothing of them enters another module's."""
    from adroit.parameter_space import limit_tables
    real = xenon.diamx_versions
    limit_tables.fingerprint.cache_clear()
    before = {m: limit_tables.fingerprint(m) for m in ("XENONnT SR0+SR1", "CDMSlite Run 2")}
    extra = tmp_path / "an added data file.csv"
    extra.write_text("1")
    monkeypatch.setattr(xenon, "diamx_versions", lambda folder, python: (
        real(folder, python)[0] + [extra], real(folder, python)[1]))
    limit_tables.fingerprint.cache_clear()
    assert limit_tables.fingerprint("XENONnT SR0+SR1") != before["XENONnT SR0+SR1"]
    assert limit_tables.fingerprint("CDMSlite Run 2") == before["CDMSlite Run 2"]
    monkeypatch.setattr(xenon, "diamx_versions", lambda folder, python: (
        real(folder, python)[0], real(folder, python)[1] + "a version changed"))
    limit_tables.fingerprint.cache_clear()
    assert limit_tables.fingerprint("XENONnT SR0+SR1") != before["XENONnT SR0+SR1"]
    monkeypatch.undo()
    limit_tables.fingerprint.cache_clear()
    assert limit_tables.fingerprint("XENONnT SR0+SR1") == before["XENONnT SR0+SR1"]
    limit_tables.fingerprint.cache_clear()

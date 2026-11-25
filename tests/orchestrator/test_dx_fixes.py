"""The auditor's DW recheck (the independent audit of 2026-11-12 (dw recheck)), its findings repaired (the record
the DX repair record of 2026-11-12).

- DX-01: a DIAMX generation reads the copy whose bytes named it; a runtime written while it runs sets it aside.
- DX-02: a start that is not a time, or not read, proves no process: nothing is signalled on it.
- DX-03: an optimum-interval result that is not a limit stops what its program left, as any call giving none.
- DX-04: two of the DW round's negative controls, made coherent, fail at the bound and the count they name: the bound
  here, the count in ``tests/ui/test_calculation_ownership.py``.
- DX-05: what DIAMX derives and keeps by its existence (its CSV conversions, XENONnT's cut acceptances) is made inside
  the generation.

The process cases start real processes, all the test's own, and end every one; the DIAMX cases marked
``needs("diamx")`` run DIAMX's installed code in its own environment, on copies in the test's folder (nothing is
written in the tools folder)."""

from __future__ import annotations

import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from adroit.experiments import xenon
from adroit.statistics import optimum_interval as oi
from adroit.ui import engine
from tests.experiments.test_diamx_inputs import _Diamx
from tests.orchestrator.test_dw_fixes import _descendant, _end, _gone, _program, _wait_gone


def _work(d: _Diamx) -> list[Path]:
    return sorted((d.tools / "diamx-work").iterdir())


def _results(root: Path) -> list[Path]:
    return sorted(root.rglob("result-*.json")) if root.exists() else []


# --- DX-01 -------------------------------------------------------------------------------------------------------------

def test_an_input_changed_while_its_generation_runs_is_never_read_under_its_old_identity(tmp_path, monkeypatch):
    """The auditor's ``diamx_input_interleaving``: the detector data changed from A (2) to B (7) once the generation is
    named, before DIAMX reads it. At the pin: 8 under A's identity, 8 warm after A was restored, 3 only once the work
    folder was removed by hand. Now DIAMX reads the copy that named the generation: A's answer, warm and clean alike;
    B kept is a generation of its own."""
    d = _Diamx(tmp_path, monkeypatch)
    plain = d._backend
    changed = []

    def interleaving(command, **kwargs):
        if not changed:
            d.data.write_text("7\n")
            changed.append(True)
        plain(command, **kwargs)
    monkeypatch.setattr(xenon.subprocess, "run", interleaving)
    assert d.limit() == 3                                                    # 8 at the pin
    d.data.write_text("2\n")
    assert d.limit() == 3 and len(d.calls) == 1                              # warm, its result reused
    shutil.rmtree(d.tools / "diamx-work")
    assert d.limit() == 3 and len(d.calls) == 2                              # clean
    d.data.write_text("7\n")
    assert d.limit() == 8 and len(_work(d)) == 2


def test_the_generation_reads_its_own_copy_and_the_installation_s_changes_never_reach_it(tmp_path, monkeypatch):
    d = _Diamx(tmp_path, monkeypatch)
    d.limit()
    [work] = _work(d)
    snapshot = work / xenon.SNAPSHOT
    assert (snapshot / xenon.DRIVER.name).read_bytes() == xenon.DRIVER.read_bytes()
    assert (snapshot / "config" / d.module.spec["config"]).read_text() == "{}"
    assert sorted(str(p.relative_to(snapshot)) for p in snapshot.rglob("*") if p.is_file()) == [
        "config/lz_ws2024_wimp_config.json", "diamx/data/lz_ws2024_wimp_data.csv", "diamx/model.py",
        xenon.DRIVER.name]
    d.data.write_text("7\n")
    d.source.write_text("version = 2\n")
    assert (snapshot / "diamx/data/lz_ws2024_wimp_data.csv").read_text() == "2\n"
    assert (snapshot / "diamx/model.py").read_text() == "version = 1\n"
    assert not list((d.tools / xenon.STAGING).iterdir())                     # each call's copy removed or kept


def test_a_linked_data_folder_is_copied_through_its_link(tmp_path, monkeypatch):
    """A package's ``data`` a link to a folder elsewhere: the copy holds its files (no link), and data changed behind
    the link names a generation of its own (DW-02's case, now by what the copy holds)."""
    d = _Diamx(tmp_path, monkeypatch)
    elsewhere = tmp_path / "detector data"
    shutil.move(d.folder / "diamx/data", elsewhere)
    (d.folder / "diamx/data").symlink_to(elsewhere, target_is_directory=True)
    assert d.limit() == 3
    [work] = _work(d)
    copied = work / xenon.SNAPSHOT / "diamx/data"
    assert copied.is_dir() and not copied.is_symlink() and (copied / d.data.name).read_text() == "2\n"
    (elsewhere / d.data.name).write_text("7\n")
    assert d.limit() == 8 and len(_work(d)) == 2


@pytest.mark.parametrize("write", ["changed", "restored"])
def test_a_runtime_written_while_its_generation_runs_sets_the_generation_aside(tmp_path, monkeypatch, write):
    """The runtime (DIAMX's environment's libraries) written during a run, to other bytes or back to its own
    (A → B → A): everything the generation made is set aside and nothing is published; the next call is a new
    generation."""
    d = _Diamx(tmp_path, monkeypatch)
    plain = d._backend
    writes = []

    def writing(command, **kwargs):
        plain(command, **kwargs)
        if not writes:
            d.library.write_text("4")
            if write == "restored":
                time.sleep(0.01)
                d.library.write_text("0")
            writes.append(True)
    monkeypatch.setattr(xenon.subprocess, "run", writing)
    with pytest.raises(xenon.DiamxInputsChanged, match="was written while this generation ran"):
        d.limit()
    assert _results(d.tools / "diamx-work") == [] and _work(d) == []
    [aside] = (d.tools / xenon.QUARANTINE).iterdir()
    assert "runtime was written" in (aside / "QUARANTINED.txt").read_text()
    assert _results(aside) == [] and list(aside.glob("pending-*.json"))      # its answer never published
    assert d.limit() == (7 if write == "changed" else 3) and len(d.calls) == 2


@pytest.mark.parametrize("runtime", ["written", "untouched"])
def test_an_interrupted_run_s_generation_is_set_aside_only_if_its_runtime_was_written(tmp_path, monkeypatch, runtime):
    """A run that ends without its end check (here its driver fails) leaves its lease: the next run in that generation
    sets it aside where the runtime was written since (even back to its bytes), and keeps what it made otherwise."""
    d = _Diamx(tmp_path, monkeypatch)
    plain = d._backend

    def failing(command, **kwargs):
        (Path(json.loads(Path(command[2]).read_text())["work_dir"]) / "templates").mkdir()
        if runtime == "written":
            d.library.write_text("4")
            time.sleep(0.01)
            d.library.write_text("0")
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(xenon.subprocess, "run", failing)
    with pytest.raises(subprocess.CalledProcessError):
        d.limit()
    [work] = _work(d)
    assert (work / xenon.LEASE).exists()
    monkeypatch.setattr(xenon.subprocess, "run", plain)
    if runtime == "written":
        with pytest.warns(UserWarning, match="set aside"):
            assert d.limit() == 3
        assert len(list((d.tools / xenon.QUARANTINE).iterdir())) == 1 and not (work / "templates").exists()
    else:
        assert d.limit() == 3 and (work / "templates").exists() and not (d.tools / xenon.QUARANTINE).exists()
    assert not (work / xenon.LEASE).exists()


def test_a_runtime_changed_while_a_call_waits_for_its_generation_is_named_again(tmp_path, monkeypatch):
    """The runtime written between naming the generation and running it: nothing runs under the old name."""
    d = _Diamx(tmp_path, monkeypatch)
    lock = xenon.fcntl.flock

    def waiting(handle, operation):
        lock(handle, operation)
        if operation == xenon.fcntl.LOCK_EX and d.library.read_text() == "0":
            d.library.write_text("4")
    monkeypatch.setattr(xenon.fcntl, "flock", waiting)
    assert d.limit() == 7 and len(d.calls) == 1
    folders = sorted(_work(d), key=lambda p: p.stat().st_mtime_ns)
    assert [bool(_results(f)) for f in folders] == [False, True]          # nothing under the old name; the new ran
    assert not (folders[0] / xenon.SNAPSHOT).exists()


def test_a_call_waiting_on_a_generation_set_aside_meanwhile_names_it_again(tmp_path, monkeypatch):
    """Another call sets the generation aside while this one waits on its lock: this one never runs in the folder set
    aside; it starts the generation again."""
    d = _Diamx(tmp_path, monkeypatch)
    lock = xenon.fcntl.flock
    done = []

    def waiting(handle, operation):
        lock(handle, operation)
        if operation == xenon.fcntl.LOCK_EX and not done:
            done.append(xenon.quarantine(Path(handle.name).parent, "set aside by another call"))
    monkeypatch.setattr(xenon.fcntl, "flock", waiting)
    assert d.limit() == 3 and len(d.calls) == 1
    assert _results(done[0]) == [] and len(_results(d.tools / "diamx-work")) == 1


def test_a_result_is_published_only_after_its_end_check(tmp_path, monkeypatch):
    d = _Diamx(tmp_path, monkeypatch)
    plain = d._backend
    seen = []

    def watching(command, **kwargs):
        seen.append((Path(command[3]).name, _results(d.tools / "diamx-work")))
        plain(command, **kwargs)
    monkeypatch.setattr(xenon.subprocess, "run", watching)
    d.limit()
    assert seen[0][0].startswith("pending-") and seen[0][1] == []
    assert len(_results(d.tools / "diamx-work")) == 1 and not list(_work(d)[0].glob("pending-*"))


def test_the_runtime_lease_changes_with_any_write_and_not_with_a_read(tmp_path, monkeypatch):
    d = _Diamx(tmp_path, monkeypatch)
    before = xenon.runtime_lease(d.python)
    d.library.read_text()
    assert xenon.runtime_lease(d.python) == before
    d.library.write_text("0")                                                # the same bytes again
    assert xenon.runtime_lease(d.python) != before


def test_a_copy_left_by_a_process_that_has_ended_is_swept(tmp_path, monkeypatch):
    """A call killed while it held its copy leaves it in the staging folder; the next call removes it, and leaves a
    living process's."""
    d = _Diamx(tmp_path, monkeypatch)
    ended = subprocess.Popen([sys.executable, "-c", "pass"])
    ended.wait()
    staging = d.tools / xenon.STAGING
    (staging / f"{ended.pid}-left").mkdir(parents=True)
    (staging / f"{os.getpid()}-held").mkdir()
    d.limit()
    assert sorted(p.name for p in staging.iterdir()) == [f"{os.getpid()}-held"]


# --- DX-05: what DIAMX derives, inside the generation (DIAMX's installed code) -----------------------------------------

PACKAGE = Path.home() / "agentic-dm-tools" / "diamx" / "diamx"

HELPER = '''
import json, sys
from pathlib import Path
command, case, fresh = json.loads(sys.argv[1]), sys.argv[2], sys.argv[3] == "fresh"
copy = Path(command[1]).parent
sys.path.insert(0, str(copy))
import diamx_driver as driver
request = json.loads(Path(command[2]).read_text())
driver.bind(str(copy))
if fresh:
    driver.fresh_conversions(request["work_dir"])
    driver.derive_here(str(copy))
import diamx.experiments.xenonnt as xn
package, maps = copy / "diamx", copy / "diamx/appletree/maps"
obj = object.__new__(xn.XENONnTSR0)
obj.config = {}
data = package / "data/lz_ws2024_wimp_data.csv"
generated = []

def resolve(name):
    if name in obj.default_cut_acc_file:
        if not (maps / name).exists():
            raise RuntimeError("absent")
        return str(maps / name)
    if name in obj.default_instruct_file.values():
        return str(package / "instruct.json")
    if name in obj.default_yield_file.values():
        return str(data if case == "maps" else package / "yield.json")
    if name in obj.default_param_file.values():
        return str(package / "params.json")
    raise AssertionError(name)

def calculate(**kwargs):                     # DIAMX's cut-acceptance calculation, its value the yield file's
    value = float(data.read_text())
    generated.append(value)
    for name in obj.default_cut_acc_file:
        (maps / name).write_text(json.dumps({"map": [value]}))

class Reached(Exception):
    pass

def simulate(*args, **kwargs):               # DIAMX's simulation, its value the map's it was given
    if case == "maps":
        raise Reached(json.loads(Path(resolve(obj.default_cut_acc_file[0])).read_text())["map"][0])
    raise Reached(json.loads(Path(args[1]["energy_spectrum"]).read_text())["map"][0])

xn.get_file_path_diamx = resolve
obj.calculate_cut_acceptance = calculate
obj.run_appletree = simulate
try:
    if case == "maps":
        obj.generate_template("neutron", 1.0, str(Path(request["work_dir"]) / "unused.h5"), batch_size=1)
    else:
        obj.generate_template("er_bkg", 1.0, str(Path(request["work_dir"]) / "unused.h5"), batch_size=1,
                              energy_spectrum=str(data))
except Reached as reached:
    value = float(reached.args[0]) + 1
Path(command[3]).write_text(json.dumps([{"label": label, "upper": value} for label in request["labels"]]))
print(json.dumps({"generated": generated, "upper": value}))
'''


_RUN = subprocess.run                     # the real one, before any stand-in replaces it


class _Installed(_Diamx):
    """The stand-in installation with DIAMX's installed package in it (copied), the auditor's synthetic detector
    inputs beside, and DIAMX's own code run on the generation's copy: its XENONnT template branch and CSV converter,
    its simulation and its map calculation scalars (as the auditor's controls)."""

    def __init__(self, root: Path, monkeypatch, case: str, fresh: bool = True) -> None:
        real = xenon.DiamxXenon("XENONnT SR0+SR1")                    # before the stand-in's settings and run
        self.run = _RUN
        super().__init__(root, monkeypatch)
        self.real_python, self.case, self.fresh, self.printed = real.python, case, fresh, []
        shutil.rmtree(self.folder / "diamx")
        shutil.copytree(real.folder / "diamx", self.folder / "diamx", symlinks=False,
                        ignore=shutil.ignore_patterns("__pycache__", "CMakeFiles"))
        self.module.search = "XENONnT SR0+SR1"
        self.module.spec = xenon.SEARCHES[self.module.search]
        self.config = self.folder / "config" / self.module.spec["config"]
        self.config.write_text("{}")
        for name in ("instruct", "yield", "params"):
            (self.folder / f"diamx/{name}.json").write_text("{}")
        self.data.write_text("2\n" if case == "maps" else "0,2\n1,2\n")
        self.helper = root / "helper.py"
        self.helper.write_text(HELPER)

    def _backend(self, command, **kwargs):
        done = self.run([str(self.real_python), str(self.helper), json.dumps(command), self.case,
                         "fresh" if self.fresh else "as installed"], check=True, capture_output=True, text=True,
                        timeout=300, env={**xenon.capped_environment(), "PYTHONDONTWRITEBYTECODE": "1"})
        self.printed.append(json.loads(done.stdout.strip().splitlines()[-1]))
        self.calls.append(self.printed[-1]["upper"])


@pytest.mark.needs("diamx")
def test_a_changed_csv_is_never_read_through_its_old_conversion(tmp_path, monkeypatch):
    """The auditor's ``diamx_csv_sidecar``: a background CSV changed from [2, 2] to [7, 7], its old conversion (map
    [2, 2]) beside it in the installation. At the pin: 3, 3 after the change, 3 with the work folder removed, 8 only
    once the conversion was removed by hand. DIAMX's own converter, run as installed on the generation's copy, still
    reads the old conversion (the control); the driver's converts afresh."""
    old = {"coordinate_system": [0.0, 1.0], "coordinate_type": "point", "coordinate_name": "pdf", "map": [2.0, 2.0]}
    control = _Installed(tmp_path / "control", monkeypatch, "csv", fresh=False)
    control.data.write_text("0,7\n1,7\n")
    control.data.with_suffix(".json").write_text(json.dumps(old))
    assert control.limit() == 3                                              # read through the old conversion
    d = _Installed(tmp_path / "repaired", monkeypatch, "csv")
    assert d.limit() == 3
    d.data.write_text("0,7\n1,7\n")
    d.data.with_suffix(".json").write_text(json.dumps(old))
    assert d.limit() == 8 and len(_work(d)) == 2
    assert json.loads(d.data.with_suffix(".json").read_text()) == old       # the installation's file never written
    converted = [json.loads(p.read_text())["map"] for p in (d.tools / "diamx-work").glob("*/converted/*.json")]
    assert sorted(converted) == [[2.0, 2.0], [7.0, 7.0]]


@pytest.mark.needs("diamx")
def test_a_changed_response_input_is_never_read_through_its_old_cut_acceptance(tmp_path, monkeypatch):
    """The auditor's ``diamx_package_cache``: XENONnT's cut-acceptance maps in the installation (value 2), its response
    input changed to 7. At the pin: 3, 3 after the change, 3 with the work folder removed, 8 only once the maps were
    removed by hand. DIAMX as installed, on the generation's copy, still reads the maps it finds (the control); the
    generation clears them before its first run and DIAMX makes its own, from the generation's inputs, once."""
    def placed(d):
        for name in ("median", "lower", "upper"):
            (d.folder / f"diamx/appletree/maps/xenonnt_sr0_cut_acc_{name}.json").write_text(json.dumps({"map": [2.0]}))
    control = _Installed(tmp_path / "control", monkeypatch, "maps", fresh=False)
    placed(control)
    control.data.write_text("7\n")
    assert control.limit() == 3 and control.printed[-1]["generated"] == []
    d = _Installed(tmp_path / "repaired", monkeypatch, "maps")
    placed(d)
    installed = {p.name: p.read_bytes() for p in (d.folder / "diamx/appletree/maps").glob("xenonnt_*cut_acc*")}
    assert d.limit() == 3 and d.printed[-1]["generated"] == [2.0]
    d.module.upper_limit(d.signal.model_copy(update={"density": [2.0] * len(xenon.ENERGIES_KEV)}))
    assert d.printed[-1]["generated"] == []                                  # the same generation: made once
    d.data.write_text("7\n")
    assert d.limit() == 8 and d.printed[-1]["generated"] == [7.0]
    assert {p.name: p.read_bytes() for p in (d.folder / "diamx/appletree/maps").glob("xenonnt_*cut_acc*")} \
        == installed                                                          # the installation's maps never written
    for work in _work(d):
        assert len(json.loads((work / xenon.SNAPSHOT / "DERIVED.json").read_text())) == 9


@pytest.mark.needs("diamx")
def test_the_driver_s_conversion_is_diamx_s_own_byte_for_byte(tmp_path):
    """The driver's converter writes what DIAMX's writes for the same CSV and coordinate, named by its bytes."""
    csv = tmp_path / "spectrum.csv"
    np.savetxt(csv, np.column_stack([xenon.ENERGIES_KEV, np.linspace(1, 2, len(xenon.ENERGIES_KEV))]), delimiter=",")
    real = xenon.DiamxXenon("XENONnT SR0+SR1")
    code = f'''
import json, sys
sys.path.insert(0, {str(xenon.DRIVER.parent)!r})
import diamx_driver as driver
import diamx.utils as utils
own = utils.csv_to_apt_map({str(csv)!r}, "pdf")
fresh = driver.fresh_conversions({str(tmp_path / "work")!r})({str(csv)!r}, "pdf")
print(json.dumps([own, fresh]))
'''
    done = subprocess.run([str(real.python), "-c", code], capture_output=True, text=True, check=True, timeout=300,
                          env={**xenon.capped_environment(), "PYTHONDONTWRITEBYTECODE": "1"})
    own, fresh = map(Path, json.loads(done.stdout.strip().splitlines()[-1]))
    assert own == csv.with_suffix(".json") and fresh.parent == tmp_path / "work" / "converted"
    assert own.read_bytes() == fresh.read_bytes()
    import hashlib
    assert fresh.stem == hashlib.sha256(csv.read_bytes() + b"\0pdf").hexdigest()


FINDER = '''
import importlib.machinery, sys

class Editable:
    """An editable install's finder: ``diamx`` from the installation whatever the path says."""
    known_packages = frozenset({{"diamx"}})

    def find_spec(self, name, path=None, target=None):
        if name.partition(".")[0] != "diamx":
            return None
        return importlib.machinery.PathFinder.find_spec(name, [{installed!r}] if path is None else path)

sys.meta_path.insert(0, Editable())
sys.path.insert(0, {driver!r})
import diamx_driver as driver
{body}
'''


def _package(root: Path, value: str) -> Path:
    (root / "diamx").mkdir(parents=True)
    (root / "diamx/__init__.py").write_text(f"VALUE = {value!r}\n")
    (root / "diamx/utils.py").write_text("def csv_to_apt_map(csv_file, coordinate_name='energy'):\n    return 'own'\n")
    return root


def _finder(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    installed, copy = _package(tmp_path / "installed", "installed"), _package(tmp_path / "copy", "copy")
    code = FINDER.format(installed=str(installed), driver=str(xenon.DRIVER.parent), body=body.replace("COPY",
                                                                                                    repr(str(copy))))
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def test_the_driver_imports_diamx_from_its_copy_past_an_editable_install_s_finder(tmp_path):
    """An editable install's finder leads ``diamx`` to the installation, whatever the path (the control); ``bind``
    imports it from the generation's copy."""
    control = _finder(tmp_path / "control", "sys.path.insert(0, COPY)\nimport diamx\nprint(diamx.VALUE)")
    assert control.stdout.strip() == "installed"
    bound = _finder(tmp_path / "bound", "print(driver.bind(COPY).VALUE)")
    assert bound.returncode == 0 and bound.stdout.strip() == "copy"


def test_the_driver_refuses_a_diamx_module_imported_from_elsewhere(tmp_path):
    refused = _finder(tmp_path, "import types\nsys.modules['diamx.extra'] = types.ModuleType('diamx.extra')\n"
                                "sys.modules['diamx.extra'].__file__ = '/elsewhere/extra.py'\ndriver.bind(COPY)")
    assert refused.returncode != 0 and "not from the generation's copy" in refused.stderr


@pytest.mark.needs("diamx")
def test_the_installed_diamx_is_imported_from_the_generation_s_copy(tmp_path):
    """DIAMX's own environment (its editable install leading to the installation): imported, compiled NEST extension
    and all, from the copy."""
    real = xenon.DiamxXenon("XENONnT SR0+SR1")
    copy = xenon.stage(real.folder, real.spec["config"], tmp_path)
    code = (f"import sys; sys.path.insert(0, {str(copy)!r}); import diamx_driver as d; m = d.bind({str(copy)!r}); "
            "import diamx.experiments.xenonnt, diamx.nestDiamx; d.confined(d.os.path.realpath(" + repr(str(copy)) +
            ")); print(m.__file__); print(diamx.nestDiamx.__file__)")
    done = subprocess.run([str(real.python), "-c", code], capture_output=True, text=True, timeout=300,
                          env={**xenon.capped_environment(), "PYTHONDONTWRITEBYTECODE": "1"})
    assert done.returncode == 0, done.stderr[-2000:]
    files = done.stdout.strip().splitlines()[-2:]
    assert all(Path(f).resolve().is_relative_to(copy.resolve()) for f in files)


# --- DX-02 -------------------------------------------------------------------------------------------------------------

def _sleeper() -> subprocess.Popen:
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    time.sleep(0.2)                                                          # started: ``ps`` lists it
    return process


STARTS = {"NaN": "NaN", "+inf": "Infinity", "-inf": "-Infinity", "zero": 0.0, "missing": None}


def _job(folder: Path, recorded, **fields) -> Path:
    folder.mkdir()
    raw = engine.Job(title="t", kind="track1", command=["track1"], folder=str(folder), **fields).model_dump(mode="json")
    for name in ("calculation_started", "runner_started"):
        raw.pop(name, None)
        if recorded is not None and name in fields.get("_which", ("calculation_started",)):
            raw[name] = recorded
    (folder / engine.JOB).write_text(json.dumps(raw))
    return folder


def _blind(monkeypatch) -> None:
    """``ps`` unable to give a start (the auditor's injection: ``lstart`` alone)."""
    real = engine._ps
    monkeypatch.setattr(engine, "_ps", lambda *args: "" if "lstart=" in args else real(*args))


@pytest.mark.parametrize("ps", ["read", "unreadable"])
@pytest.mark.parametrize("start", list(STARTS))
def test_a_calculation_group_whose_start_is_not_a_time_is_named_never_signalled(tmp_path, monkeypatch, start, ps):
    """The auditor's ``process_proof_edges``: a group led by a live process, its recorded start NaN, ±∞, 0 or missing,
    ``ps`` reading starts or not. At the pin NaN with ``ps`` reading, and 0 or missing with ``ps`` unreadable, were
    signalled (SIGTERM)."""
    sentinel = _sleeper()
    try:
        folder = tmp_path / "job"
        folder.mkdir()
        raw = engine.Job(title="t", kind="track1", command=["track1"], folder=str(folder), status="failed",
                         calculation=sentinel.pid).model_dump(mode="json")
        raw.pop("calculation_started", None)
        if STARTS[start] is not None:
            raw["calculation_started"] = STARTS[start]
        (folder / engine.JOB).write_text(json.dumps(raw))
        if ps == "unreadable":
            _blind(monkeypatch)
        job = engine.load(folder)
        assert engine.calculation_alive(job) == [] and engine.calculation_unproven(job) == [sentinel.pid]
        engine.cancel(folder)
        engine.cancel(folder)                                               # a second, forcible
        time.sleep(0.3)
        assert sentinel.poll() is None
        assert engine.START_UNPROVEN.format(pids=sentinel.pid, group=sentinel.pid) in engine.load(folder).note
    finally:
        sentinel.kill()
        sentinel.wait()


@pytest.mark.parametrize("ps", ["read", "unreadable"])
@pytest.mark.parametrize("start", list(STARTS))
def test_a_runner_whose_start_is_not_a_time_is_never_signalled(tmp_path, monkeypatch, start, ps):
    sentinel = _sleeper()
    try:
        folder = tmp_path / "job"
        folder.mkdir()
        raw = engine.Job(title="t", kind="track1", command=["track1"], folder=str(folder), status="running",
                         pid=sentinel.pid, acknowledged=True, started="2000-01-01T00:00:00").model_dump(mode="json")
        raw.pop("runner_started", None)
        if STARTS[start] is not None:
            raw["runner_started"] = STARTS[start]
        (folder / engine.JOB).write_text(json.dumps(raw))
        if ps == "unreadable":
            _blind(monkeypatch)
        assert not engine.runner_alive(engine.load(folder))
        engine.cancel(folder)
        time.sleep(0.3)
        assert sentinel.poll() is None
        assert engine.RUNNER_UNPROVEN.format(pid=sentinel.pid) in engine.load(folder).note
    finally:
        sentinel.kill()
        sentinel.wait()


@pytest.mark.parametrize("case", ["proven", "another start", "proven but ps unreadable"])
def test_only_a_start_both_recorded_and_read_alike_proves_a_group(tmp_path, monkeypatch, case):
    """The controls: the recorded start that ``ps`` gives proves the group, which Cancel stops; an hour earlier proves
    nothing; the right start with ``ps`` unable to read one proves nothing either (fail closed)."""
    sentinel = _sleeper()
    try:
        started = engine.process_started(sentinel.pid)
        assert math.isfinite(started) and started > 0
        job = engine.Job(title="t", kind="track1", command=["track1"], folder=str(tmp_path), status="failed",
                         calculation=sentinel.pid,
                         calculation_started=started - (3600 if case == "another start" else 0))
        engine.save(job)
        if case.endswith("unreadable"):
            _blind(monkeypatch)
        engine.cancel(tmp_path)
        if case == "proven":
            assert sentinel.wait(timeout=10) == -signal.SIGTERM
        else:
            time.sleep(0.3)
            assert sentinel.poll() is None
    finally:
        if sentinel.poll() is None:
            sentinel.kill()
        sentinel.wait()


def test_a_leader_ending_as_its_start_is_read_is_not_named_unproven(monkeypatch):
    """A cancel's own stop ends the leader between the group's listing and its start's reading: the group is listed
    again, not named as unproven while it is gone."""
    listings = iter([[101, 102], []])
    monkeypatch.setattr(engine, "_group", lambda pgid: next(listings))
    monkeypatch.setattr(engine, "process_started", lambda pid: 0.0)
    job = engine.Job(title="t", kind="track1", command=["track1"], folder="/nowhere", calculation=101,
                     calculation_started=1.7e9)
    assert engine.calculation_unproven(job) == []


# --- DX-03 -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("output", ["-1.0 0", "nan 0", "3.0 64", "inf 0", "3.0 2"])
def test_a_result_that_is_not_a_limit_stops_what_its_program_left_holding_its_files(tmp_path, monkeypatch, output):
    """The auditor's ``oi_cleanup_edges``, through the public entry: the program starts a helper in a session of its
    own, holding the call's files, prints a result that is not a limit, and exits. Refused, as before; its helper is
    now stopped (at the pin it kept running)."""
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", "30")
    program, record = _program(tmp_path, f"print({output!r})")
    monkeypatch.setattr(oi, "executable", lambda: program)
    with pytest.raises(oi.OptimumIntervalFailed):
        oi.optimum_interval_limit(np.array([0.2, 0.5, 0.8]), cache=False)
    descendant = _descendant(record)
    try:
        assert _wait_gone([descendant], 5.0)
    finally:
        _end([descendant])


@pytest.mark.parametrize("case", ["a limit", "no output", "the deadline"])
def test_the_public_entry_s_other_outcomes_are_as_before(tmp_path, monkeypatch, case):
    """Beside them: a limit is returned (its helper may run on, the stated policy; the test ends it); no output and the
    deadline are refused with the helper stopped."""
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", "2" if case == "the deadline" else "30")
    tail = {"a limit": "print('3.0 0')", "no output": "", "the deadline": "import time; time.sleep(20)"}[case]
    program, record = _program(tmp_path, tail)
    monkeypatch.setattr(oi, "executable", lambda: program)
    try:
        if case == "a limit":
            assert oi.optimum_interval_limit(np.array([0.2, 0.5, 0.8]), cache=False) == (3.0, 0)
        else:
            with pytest.raises(oi.OptimumIntervalFailed, match="deadline" if case == "the deadline" else "not a limit"):
                oi.optimum_interval_limit(np.array([0.2, 0.5, 0.8]), cache=False)
            assert _wait_gone([_descendant(record)], 5.0)
    finally:
        _end([_descendant(record)])


def test_an_accepted_flag_is_still_a_limit(tmp_path, monkeypatch):
    """Flag 4 (the extrapolation Yellin's code flags but the stated policy accepts) is a limit, as before."""
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", "30")
    program, record = _program(tmp_path, "print('3.0 4')")
    monkeypatch.setattr(oi, "executable", lambda: program)
    try:
        assert oi.optimum_interval_limit(np.array([0.2, 0.5, 0.8]), cache=False) == (3.0, 4)
    finally:
        _end([_descendant(record)])


# --- DX-04 -------------------------------------------------------------------------------------------------------------

def test_a_refused_call_returns_within_its_deadline_whatever_its_program_left(tmp_path, monkeypatch):
    """A program that leaves a helper holding the call's output and exits with no limit: refused within its deadline and
    a few seconds, whatever the refusal says. Before DW-04 the call read the output through pipes and, past its
    deadline, drained them without a bound, until the helper ended (20 s here). The DW round's negative control 10 had
    restored the pipes but not their reading, so its tests failed on an empty output, not on this bound (DX-04)."""
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", "2")
    program, record = _program(tmp_path)
    started = time.monotonic()
    with pytest.raises(oi.OptimumIntervalFailed):
        oi._calculate(program, "0.9 0\n")
    elapsed = time.monotonic() - started
    try:
        assert elapsed < 2.0 + 3.0
    finally:
        _end([_descendant(record)])


def test_no_process_is_left_by_the_tests(tmp_path):
    """The helpers above are each ended (``_end``); a check that ``_gone`` reads an ended process as gone."""
    sentinel = _sleeper()
    sentinel.kill()
    sentinel.wait()
    assert _gone(sentinel.pid)

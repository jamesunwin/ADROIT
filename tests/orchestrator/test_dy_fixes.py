"""The auditor's recheck of the DX repairs (the independent audit of 2026-11-13 (dx recheck)), its three findings repaired.

- DY-01: every cache of a direct-detection limit, or of anything computed from a module's detector inputs, is kept by
  the version of those inputs (``limit_tables.inputs``, ``held``): a warm comparison follows a changed input.
- DY-02: a production table is read once per call, its range and its spline of one version, however the cache is
  evicted and refilled (``production.table``).
- DY-03: a DIAMX run that ended without its end check leaves nothing it made for the next run to read
  (``xenon.restore``), and DIAMX's process holds its generation's lock.

The DIAMX installations are folders of the tests' own with a stand-in for DIAMX's process
(``tests.experiments.test_diamx_inputs._Diamx``); the production tables are synthetic. No real detector calculation.
"""
from __future__ import annotations

import ast
import fcntl
import functools
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
import yaml

from adroit.constraints import lhc, production
from adroit.experiments import registry, xenon
from adroit.parameter_space import (dd_channels, flavour_limits, halo_limits, limit_tables, limits,
                                    operator_limits, resonances)
from tests.experiments.test_diamx_inputs import _Diamx

ROOT = Path(__file__).resolve().parents[2]


# --- DY-01 -----------------------------------------------------------------------------------------------------

@pytest.fixture
def detector(tmp_path, monkeypatch):
    """One DIAMX search as the only module, its 95% limit its stand-in's value × 10⁻⁴⁵ cm², and a current table of
    3 × 10⁻⁴⁵ cm² for it (the auditor's ``limit_currency`` control)."""
    d = _Diamx(tmp_path, monkeypatch)
    monkeypatch.setattr(registry, "load_module", lambda name: d.module)
    monkeypatch.setattr(limits, "eligible", lambda kind, mass, excluded=(): [d.module.search])
    monkeypatch.setattr(limits, "edge_floor", lambda *a: None)
    monkeypatch.setattr(limits, "fallback", lambda *a: "")
    monkeypatch.setattr(d.module, "reference_limits", lambda *a, **kw: [d.limit() * 1e-45], raising=False)
    tables = tmp_path / "tables"
    tables.mkdir()
    monkeypatch.setattr(limit_tables, "TABLES", tables)
    limits.clear_cache()
    (tables / f"{limit_tables.slug(d.module.search, 'SI')}.yaml").write_text(yaml.safe_dump(dict(
        module=d.module.search, kind="SI", fingerprint=limit_tables.fingerprint(d.module.search),
        masses_gev=[1.0, 100.0], limits_cm2=[3e-45, 3e-45], interpolation_accuracy=0.001)))
    yield d
    limits.clear_cache()


def _compare():
    """4 × 10⁻⁴⁵ cm² compared at 10 GeV (cross-sections are compared with ``abs=0``: pytest's default absolute
    tolerance, 10⁻¹², would take any two of them as equal)."""
    return dd_channels.compare([dd_channels.Channel(kind="SI", sigma_cm2=4e-45)], 10.0)


def test_a_warm_comparison_follows_a_changed_detector_input(detector) -> None:
    """The auditor's DY-01: the table (3e-45) excludes 4e-45; the detector input then changes (the stand-in gives 8e-45).
    Without clearing anything, the next comparison is the uncached one: the table stale, the limit the module's own,
    the point allowed."""
    first = _compare()
    assert first.excluded and first.channels[0].limit.value == pytest.approx(3e-45, rel=1e-9, abs=0)
    assert "interpolated from its precomputed table" in first.channels[0].limit.construction
    detector.data.write_text("7\n")
    warm = _compare()
    assert limit_tables.lookup(detector.module.search, "SI", 10.0) is None          # the table is stale now
    assert warm.channels[0].limit.value == pytest.approx(8e-45, rel=1e-9, abs=0)
    assert not warm.excluded and warm.channels[0].ratio == pytest.approx(0.5)
    assert "interpolated" not in warm.channels[0].limit.construction
    limits.clear_cache()
    cold = _compare()
    assert (cold.excluded, cold.channels[0].limit.value, cold.channels[0].ratio) == \
        (warm.excluded, warm.channels[0].limit.value, warm.channels[0].ratio)


def test_an_input_changed_and_restored_is_read_again(detector) -> None:
    """A → B → A: each write is a new version, and the restored bytes make the stored table current again."""
    assert _compare().excluded
    detector.data.write_text("7\n")
    assert not _compare().excluded
    detector.data.write_text("2\n")
    again = _compare()
    assert again.excluded and again.channels[0].limit.value == pytest.approx(3e-45, rel=1e-9, abs=0)
    assert limit_tables.lookup(detector.module.search, "SI", 10.0) is not None


def test_a_changed_runtime_distribution_is_a_new_version(detector) -> None:
    """DIAMX's runtime enters by each installed distribution's record folder (a reinstall replaces it)."""
    before = limit_tables.inputs(detector.module.search)
    record = detector.python.parent.parent / "lib/python3.12/site-packages/numerics-1.0.dist-info"
    record.mkdir()
    assert limit_tables.inputs(detector.module.search) != before


def test_one_comparison_reads_each_modules_inputs_once(detector, monkeypatch) -> None:
    """A warm comparison reads each module's inputs once; a value computed in one reads them once more as it is kept
    (``held``: unchanged while it was computed)."""
    calls = []
    real = limit_tables._inputs_now
    monkeypatch.setattr(limit_tables, "_inputs_now", lambda module: calls.append(module) or real(module))
    _compare()
    computed = len(calls)
    calls.clear()
    _compare()
    assert calls == [detector.module.search] and computed > 1
    calls.clear()
    limit_tables.inputs(detector.module.search)                         # outside a comparison: as it is now
    limit_tables.inputs(detector.module.search)
    assert len(calls) == 2


def test_a_value_whose_inputs_change_while_it_is_computed_is_not_kept() -> None:
    versions, computed = iter(range(100)), []

    @limit_tables.held(4, lambda x: next(versions))
    def f(x):
        computed.append(x)
        return x
    with pytest.raises(limit_tables.InputsChanging):
        f(1)
    assert len(computed) == limit_tables.TRIES and f.cache_info().currsize == 0
    settled = iter([0, 0, 0])

    @limit_tables.held(4, lambda x: next(settled, 0))
    def g(x):
        return 2 * x
    assert g(3) == 6 and g(3) == 6 and g.cache_info().hits == 1


def test_a_limit_whose_inputs_keep_changing_is_none_with_its_reason(detector, monkeypatch) -> None:
    versions = iter(range(100))
    monkeypatch.setattr(limit_tables, "_inputs_now", lambda module: (str(next(versions)), ""))
    value, why = limits.reference_limit(detector.module.search, "SI", 10.0, False)
    assert value is None and "its inputs changed each time" in why


# cached functions of the limit code that read nothing of a module's detector inputs, or are kept current otherwise
NOT_A_LIMIT = {
    "halo_limits.accepted": "cleared whenever a module's inputs change (`counted`, which the calculation asks); its "
                            "source, decorator included, is the count ratio validation's input (inputs_sha256)",
    "limit_tables._stored_at": "a stored table by its file's version (file_reads)",
    "limits._stretch": "the DM3 validation store, ADROIT's own file",
    "limits.table": "the DM3 validation store, ADROIT's own file",
    "operator_limits.table": "a stored operator table, ADROIT's own file",
    "halo_region.radius": "a χ² quantile",
}


def test_every_limit_cache_is_kept_by_its_modules_inputs() -> None:
    """Every cached function of the direct-detection limit code is ``held`` by its modules' input versions, or reads
    nothing of a module's detector inputs (``NOT_A_LIMIT``, each with why)."""
    held = [limits._reference_limit, limits._per_module95, limits._at95, limit_tables.fingerprint,
                dd_channels._single_kind_factor, halo_limits.exact, halo_limits.exact_at_table, halo_limits.blind_at_table,
                halo_limits.inputs_sha256, halo_limits._usable_at, halo_limits._targeted_at, operator_limits.limit95,
                flavour_limits.limit95]
    assert all(isinstance(f, limit_tables._Held) for f in held)
    names = {f"{f.__module__.rsplit('.', 1)[-1]}.{f.__wrapped__.__name__}" for f in held}
    for name in ("limits", "limit_tables", "dd_channels", "halo_limits", "operator_limits", "flavour_limits",
                 "halo_region", "halo_evaluation"):
        tree = ast.parse((ROOT / "adroit/parameter_space" / f"{name}.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and any("lru_cache" in ast.unparse(d) or "held" in ast.unparse(d)
                                                         for d in node.decorator_list):
                assert f"{name}.{node.name}" in names | set(NOT_A_LIMIT), f"{name}.{node.name} is cached by name"


def test_the_accepted_counts_follow_a_changed_input(detector, monkeypatch) -> None:
    """The count ratio's accepted counts (``halo_limits.counted``): computed again once the module's inputs change."""
    calls = []

    @functools.lru_cache(maxsize=8)
    def accepted(module, kind, mass_gev, v0, ve):
        calls.append(module)
        return float(detector.data.read_text())
    monkeypatch.setattr(halo_limits, "accepted", accepted)
    monkeypatch.setattr(halo_limits, "_ACCEPTED_AT", {})
    search = detector.module.search
    assert halo_limits.counted(search, "SI", 10.0, None, None) == 2.0
    assert halo_limits.counted(search, "SI", 10.0, None, None) == 2.0 and len(calls) == 1
    detector.data.write_text("7\n")
    assert halo_limits.counted(search, "SI", 10.0, None, None) == 7.0 and len(calls) == 2


# --- DY-02 -----------------------------------------------------------------------------------------------------

def _write(path: Path, masses, value) -> None:
    path.write_text(json.dumps({"columns": ["mass_gev", "sigma_pb"], "data": [[m, value] for m in masses]}))


@pytest.fixture
def tables(tmp_path, monkeypatch):
    monkeypatch.setattr(production, "folder", lambda: tmp_path)
    for i in range(33):
        _write(tmp_path / f"other{i}.json", [100, 200, 300, 400], 1)
    caches = [getattr(production, n) for n in ("_read", "_parsed", "_spline_of") if hasattr(production, n)]
    for cache in caches:                                     # the repaired reading's cache, or the pin's two
        cache.cache_clear()
    yield tmp_path
    for cache in caches:
        cache.cache_clear()


def test_one_sigma_call_reads_one_table_even_after_eviction(tables, monkeypatch) -> None:
    """The auditor's DY-02 (its ``cache_eviction`` control): the table A (100–400 GeV, 2 pb) is replaced by B (500–800 GeV,
    6 pb) once the call has taken its reading, and 33 other tables then fill the cache. The call gives A's 2 pb (the
    version it read), never B's spline at A's range. The reading is taken through ``production.table`` (at the pin,
    through ``_table``, which read the values the call's range came from; its spline was read again)."""
    _write(tables / "subject.json", [100, 200, 300, 400], 2)
    wrapped = "table" if hasattr(production, "table") else "_table"
    real, done = getattr(production, wrapped), []

    def interleaved(name, *args, **kwargs):
        held = real(name, *args, **kwargs)
        if name == "subject" and not done:
            done.append(True)
            _write(tables / "subject.json", [500, 600, 700, 800], 6)
            for i in range(33):
                real(f"other{i}")
        return held
    monkeypatch.setattr(production, wrapped, interleaved)
    assert production.sigma_pb("subject", 200.0) == pytest.approx(2.0)
    monkeypatch.setattr(production, wrapped, real)
    assert production.sigma_pb("subject", 200.0) is None                    # B as it is now: 200 GeV outside it
    assert production.sigma_pb("subject", 600.0) == pytest.approx(6.0)


def test_a_grid_outside_its_reading_is_refused(tables) -> None:
    _write(tables / "subject.json", [100, 200, 300, 400], 2)
    span = production.mass_range("subject")
    _write(tables / "subject.json", [500, 600, 700, 800], 6)
    with pytest.raises(ValueError, match="outside the table as it is now"):
        production.sigma_pb_grid("subject", np.linspace(*span, 5))


def test_the_resonance_window_takes_its_range_and_grid_from_one_reading(tables, monkeypatch) -> None:
    from adroit.parameter_space import searches as ps
    _write(tables / "vector.json", [500, 1000, 2000, 4000, 6000], 3)
    monkeypatch.setattr(ps, "VECTOR_TABLES", {"vector": "vector"})
    reads = []
    real = production.table
    monkeypatch.setattr(production, "table", lambda name, column="sigma_pb": reads.append(name) or real(name, column))
    assert resonances.window_fraction(2000.0, 0.03) is not None
    assert reads == ["vector"]


def test_a_cached_reading_is_of_the_version_that_keys_it(tables, tmp_path, monkeypatch) -> None:
    """A refill reads exactly the version its key names, or refuses (``file_reads.Moved``): the SUSY tables too."""
    from adroit.core.file_reads import Moved, identity
    _write(tables / "subject.json", [100, 200, 300, 400], 2)
    path = str(tables / "subject.json")
    old = identity(os.stat(path))
    _write(tables / "subject.json", [500, 600, 700, 800], 6)
    with pytest.raises(Moved):
        production._read(path, old, "sigma_pb")
    susy = tmp_path / "susy-xsec/tables"
    susy.mkdir(parents=True)
    (susy / "x.json").write_text(json.dumps({"data": [[100, 2.0], [400, 2.0]]}))
    monkeypatch.setattr(lhc, "_tools", lambda: tmp_path)
    old = identity(os.stat(susy / "x.json"))
    assert lhc._table("x") == ((100, 400), (2.0, 2.0))
    assert lhc._parsed(str(susy / "x.json"), old) == ((100, 400), (2.0, 2.0))     # A's entry holds A's bytes
    (susy / "x.json").write_text(json.dumps({"data": [[500, 6.0], [800, 6.0]]}))
    lhc._parsed.cache_clear()                                                         # evicted: a refill of A
    with pytest.raises(Moved):
        lhc._parsed(str(susy / "x.json"), old)
    assert lhc._table("x") == ((500, 800), (6.0, 6.0))


# --- DY-03 -----------------------------------------------------------------------------------------------------

class _Templates:
    """A stand-in for DIAMX's process that keeps a template by its existence, as DIAMX does: it reads the template if
    the file exists, and makes it otherwise; ``fail`` makes it write a template's first bytes and stop."""

    def __init__(self, d: _Diamx) -> None:
        self.d, self.fail, self.made, self.kwargs = d, None, [], []

    def __call__(self, command, **kwargs):
        self.kwargs.append(kwargs)
        request = json.loads(Path(command[2]).read_text())
        folder = Path(request["work_dir"]) / "templates"
        folder.mkdir(exist_ok=True)
        template = folder / "background.h5"
        if not template.exists():
            self.made.append(template)
            if self.fail is not None:
                template.write_bytes(b"\x89HDF\r\n")                     # a half-written template
                raise self.fail
            template.write_text(json.dumps({"mu": 3.0}))
        (Path(request["work_dir"]) / "maps").mkdir(exist_ok=True)
        mu = json.loads(template.read_text())["mu"]                          # a partial file fails here
        Path(command[3]).write_text(json.dumps([{"label": label, "upper": mu} for label in request["labels"]]))


@pytest.fixture
def diamx(tmp_path, monkeypatch):
    d = _Diamx(tmp_path, monkeypatch)
    backend = _Templates(d)
    monkeypatch.setattr(xenon.subprocess, "run", backend)
    return d, backend


def _work(d: _Diamx) -> Path:
    (folder,) = (d.tools / "diamx-work").iterdir()
    return folder


def test_an_interrupted_template_is_made_again(diamx) -> None:
    """The auditor's DY-03: a run fails after writing a template's first bytes; the next run removes what that run made and
    DIAMX makes the template again, rather than every later run failing on it."""
    d, backend = diamx
    backend.fail = subprocess.CalledProcessError(1, "diamx")
    with pytest.raises(subprocess.CalledProcessError):
        d.limit()
    assert (_work(d) / xenon.LEASE).exists()
    backend.fail = None
    assert d.limit() == pytest.approx(3.0)
    assert len(backend.made) == 2                                            # made again, not read half-written
    assert not (_work(d) / xenon.LEASE).exists() and not (_work(d) / xenon.INVENTORY).exists()
    assert not list((d.tools / "diamx-quarantined").glob("*"))              # the generation is kept


def test_a_killed_run_leaves_nothing_it_made_and_keeps_what_was_finished(diamx) -> None:
    """A run killed mid-template (its process gone, the lease left): what earlier runs finished is kept, file for file,
    what the killed run made is removed, and a finished result stays."""
    d, backend = diamx
    assert d.limit() == pytest.approx(3.0)                                   # a finished run: its template kept
    work = _work(d)
    finished = os.stat(work / "templates/background.h5").st_ino
    results = sorted(p.name for p in work.glob("result-*.json"))
    (work / "templates/background.h5").rename(work / "templates/kept.h5")      # an earlier, finished template
    finished = os.stat(work / "templates/kept.h5").st_ino
    backend.fail = KeyboardInterrupt()                                        # the run stops as if killed
    d.signal = d.signal.model_copy(update={"density": [2.0] * len(xenon.ENERGIES_KEV)})
    with pytest.raises(KeyboardInterrupt):
        d.limit()
    assert (work / "templates/background.h5").read_bytes().startswith(b"\x89HDF")
    backend.fail = None
    assert d.limit() == pytest.approx(3.0)
    assert os.stat(work / "templates/kept.h5").st_ino == finished
    assert set(results) <= {p.name for p in work.glob("result-*.json")}
    assert json.loads((work / "templates/background.h5").read_text()) == {"mu": 3.0}


def test_a_left_lease_without_its_inventory_sets_the_generation_aside(diamx) -> None:
    d, backend = diamx
    assert d.limit() == pytest.approx(3.0)
    work = _work(d)
    (work / xenon.LEASE).write_text(xenon.runtime_lease(d.python))          # left by a run of earlier code
    d.signal = d.signal.model_copy(update={"density": [2.0] * len(xenon.ENERGIES_KEV)})
    with pytest.warns(UserWarning, match="what it began from cannot be read"):
        assert d.limit() == pytest.approx(3.0)
    (aside,) = (d.tools / "diamx-quarantined").iterdir()
    assert "cannot be read" in (aside / "QUARANTINED.txt").read_text()


def test_diamx_holds_its_generations_lock(diamx) -> None:
    """DIAMX's process is given the generation's lock (``pass_fds``), so the lock lasts as long as DIAMX does."""
    d, backend = diamx
    seen = []

    def run(command, **kwargs):
        (fd,) = kwargs["pass_fds"]
        lock = Path(command[2]).parent / "inference.lock"
        seen.append(os.fstat(fd).st_ino == os.stat(lock).st_ino)
        with open(lock, "a") as other:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return backend(command, **kwargs)
    xenon.subprocess.run = run
    assert d.limit() == pytest.approx(3.0) and seen == [True]


def test_the_lock_outlives_the_process_that_took_it(tmp_path) -> None:
    """The operating system's part: a lock passed to a child is held until the child ends, after its parent closes."""
    lock = tmp_path / "inference.lock"
    with lock.open("a") as held_:
        fcntl.flock(held_, fcntl.LOCK_EX)
        child = subprocess.Popen(["/bin/sleep", "2"], pass_fds=(held_.fileno(),))
    try:
        with lock.open("a") as other:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        child.wait()
    with lock.open("a") as other:
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

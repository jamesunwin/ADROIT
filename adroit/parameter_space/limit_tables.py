"""Precomputed 95% limits for the SI and SD reference structures of the slow modules (R10).

A scan compares each point with every validated module's 95% limit at its mass (``limits.per_module95``). For the
xenon searches that limit comes from DIAMX's full likelihood in (S1, S2), minutes per new mass; CDMSlite's takes
23 s per kind and PICO's 4 s (``SLOW``). Their reference structures (σ_SI and σ_SD at fixed couplings) are
therefore computed once on a mass grid spanning each module's validated range
(``scripts/tabulate_reference_limits.py``) and stored in ``data/reference_limits/``: sixteen masses per decade,
every one computed directly. Between them the limit is a cubic spline in (log m, log σ).

**Accuracy.** Each table records |spline/direct − 1| at each interior mass left out and predicted from the others,
and its largest value ε. Leaving a mass out doubles the spacing there, so ε overstates the
table's own error (a cubic's error grows as the spacing to the fourth power). A table's value at a mass is used with the local
tolerance η = max(2 × the larger error of the two tabulated masses around it, 1%), so a steep threshold costs
exact calculations there only, and ``dd_channels.compare`` recomputes a point exactly whenever a verdict could change
within η of any module's tabulated limit, so a tabulated scan's verdicts equal the direct ones wherever a table's error
is within η (R10's gate checks this on three scans; it is an estimate, not a proven bound). The floor is above the
scatter the tables show about their direct limits: the audit loop's AL1-12 (2026-11-14) measured nine single-mass DIAMX
limits against the xenon tables, the largest miss 0.91% (PandaX-4T SI, 389.9–448.4 GeV), where the floor had been
0.5%.

**Currency.** Each table carries a fingerprint of everything its numbers depend on: ADROIT's rate, nuclear and
statistics code and data, the experiments' shared code and data, the module's own code, and its external inputs
(DIAMX's driver, configuration and source, its bundled data and its runtime's versions; a data release in the tools
folder), and, for a module whose limits use Yellin's code, whether they would be set by the maximum gap in place of the
optimum interval the tables were computed with (AL1-03). Python files enter by their syntax
tree without docstrings, so editing a comment or docstring leaves a table current; any change to the code does not. A table
whose fingerprint differs from the installed code's is not used (the direct calculation is), so editing that code
can slow a scan but never makes it use stale limits.

**Versions** (the auditor's DX recheck, DY-01, 2026-11-13). A process reads a module's inputs from outside ADROIT's package
as they are at each comparison (``inputs``), and every cache of a limit, or of anything computed from a module's
detector inputs, is kept by that version as well as by its arguments (``held``): a detector input changed under a warm
process is fingerprinted, tabulated and calculated with again, never answered from what was computed before. Kept by
the module's name, a warm comparison had gone on excluding with a limit after the input it came from changed, labelled
a current table's. One comparison (``dd_channels.compare``) or one point's halo evaluation reads each module's inputs
once (``reading``). ADROIT's package (its code and the data shipped with it) is held for the process, as its imported
code is, except the stored tables, each read by its file's version (``file_reads``) and among its module's inputs, so
that a limit taken from a table is kept by the table's version too (the audit loop's AL1-05, 2026-11-14).
"""

from __future__ import annotations

import ast
import functools
import hashlib
import math
import re
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

TOLERANCE_FLOOR = 0.01             # η's floor: above the tables' scatter about their direct limits (AL1-12)
KINDS = ("SI", "SD-proton", "SD-neutron")
ROOT = Path(__file__).resolve().parents[1]                         # the adroit package
TABLES = Path(__file__).resolve().parent / "data" / "reference_limits"
CODE = [ROOT / "physics", ROOT / "statistics", ROOT / "experiments" / "base.py", ROOT / "experiments" / "digitised.py",
        ROOT / "experiments" / "data"]
# Files under CODE that no tabulated limit reads: the native likelihood's certificate (native_validation.py), a list of
# byte hashes of its own inputs, re-issued whenever one of them changes, docstrings included
NOT_INPUTS = ("native_pico_si_validation.yaml",)
# Paths under CODE that no tabulated limit reads: the neutrino fog (an overlay, never a direct-detection limit)
NOT_INPUT_PATHS = (ROOT / "physics" / "neutrino_fog.py", ROOT / "physics" / "data" / "neutrino_fog")
# the modules whose direct limit takes seconds to minutes per new mass (R10's measurements): DIAMX's xenon searches,
# CDMSlite's median over efficiency realisations (23 s per kind) and PICO's profile likelihood (4 s)
SLOW = ("LZ WS2022+WS2024", "XENONnT SR0+SR1", "PandaX-4T Run0+Run1", "CDMSlite Run 2", "PICO-60 C3F8 (2019)")


TRIES = 3
_READING: ContextVar[dict | None] = ContextVar("limit_inputs", default=None)
_METHODS: ContextVar[dict | None] = ContextVar("limit_methods", default=None)   # each module's method, held with them
_FRESH: ContextVar[bool] = ContextVar("limit_inputs_fresh", default=False)


class InputsChanging(RuntimeError):
    """A module's inputs changed each time a value computed from them was about to be kept (``held``)."""


@contextmanager
def reading() -> Iterator[None]:
    """Inside: each module's inputs (``inputs``) are read once, at their first use, and every limit inside is taken at
    that version: one comparison (``dd_channels.compare``) or one point's halo evaluation reads one version of each.
    Nested, the outer reading holds. A value computed inside whose inputs are found changed once it is computed is not
    kept, and is computed again at the new version (``held``)."""
    if _READING.get() is not None:
        yield
        return
    token, methods = _READING.set({}), _METHODS.set({})
    try:
        yield
    finally:
        _READING.reset(token)
        _METHODS.reset(methods)


def inputs(module: str) -> str:
    """The version of what ``module``'s limits read from outside ADROIT's package, as it is now (inside ``reading``, as
    it was at its first use there): a digest of the records of every file of DIAMX's configuration, its package and its
    interpreter (``track1_identity._entries``' walk: linked folders followed, compiled extensions included), each of
    its runtime's installed distributions (its record folder, which a reinstall replaces), and its batch size; else of
    every file of the module's data release in the tools folder (its ``folder``); else of nothing. A record is a
    file's path, device, inode, size, and modification and change times (``file_reads.identity``): any write moves its
    change time, so a file changed and restored (A → B → A) is a new version. With them, for every module, the records
    of its stored tables' files (each kind's, or that it has none), so that a limit taken from a table is never given
    once the table is replaced, removed or written (the audit loop's AL1-05, 2026-11-14); and for a module whose limits
    use Yellin's code (``experiments.base.interval_limit``), the method it uses now and the record of the optimum
    interval's compiled driver, so that a limit set by the maximum gap is never given once the optimum interval is
    there, nor the reverse (AL1-03: installed under a warm process, the maximum gap's limit had been kept without its
    "excludes only" flag, and allowed what a fresh process excludes). A module that cannot be loaded (its data not
    fetched) is versioned by its reason.

    Not in it: a library file of DIAMX's runtime rewritten in place without a reinstall (its distribution's record
    unchanged), which the generation's own lease sees when DIAMX next runs (``xenon.runtime_lease``, DX-01) but a limit
    computed before does not; and ADROIT's package, held for the process (module docstring)."""
    held_now = _READING.get()
    if held_now is not None and module in held_now and not _FRESH.get():
        return held_now[module]
    version, method = _inputs_now(module)
    if held_now is not None:
        held_now[module] = version
        _METHODS.get()[module] = method
    return version


def statistical_method(module: str) -> str:
    """The statistical method ``module``'s limits use, as it declares it when its inputs are read (``inputs``): inside
    ``reading``, as at their first use there, so that a limit kept by those inputs is described by the method it was
    set with (AL2-08: the optimum interval installed during one point's evaluation, a maximum-gap limit kept by the
    held inputs had lost its "excludes only" flag, which was asked of the module afresh); "" for a module that
    declares none or cannot be loaded."""
    inputs(module)
    held_now = _METHODS.get()
    if held_now is not None and module in held_now:
        return held_now[module]
    return _inputs_now(module)[1]


def _inputs_now(module: str) -> tuple[str, str]:
    """(``inputs``' version now, the module's declared statistical method from the same load). The method is kept
    where the module loads but its inputs cannot be walked (AL3-08: its maximum-gap flag had been lost there)."""
    from adroit.core.file_reads import identity
    from adroit.experiments import registry
    from adroit.experiments.base import DataUnavailable
    from adroit.orchestrator.track1_identity import _entries
    declared = ""
    try:
        loaded = registry.load_module(module)
        declared = getattr(getattr(loaded, "info", None), "statistical_method", "") or ""
        walked, stated, extra = _external(loaded)
        method, drivers = _yellin(loaded)
        digest = hashlib.sha256(f"{extra}\0method\0{method}".encode())
        entries = [entry for root in walked for entry in (_entries(root) if root.exists() else [("absent", root, "")])]
        tables = [TABLES / f"{slug(module, kind)}.yaml" for kind in KINDS]
        for kind, path, text in [*entries, *(("record", path, "") for path in [*stated, *drivers]),
                                 *(("table", path, "") for path in tables)]:
            try:
                record = (kind, path, text, *identity(path.stat()))
            except OSError as error:
                record = (kind, path, text, type(error).__name__)
            digest.update("\0".join(map(str, record)).encode() + b"\n")
        return digest.hexdigest(), declared
    except (DataUnavailable, KeyError, OSError, ValueError) as error:      # InputUnreadable is a ValueError
        return f"unreadable\0{type(error).__name__}\0{error}", declared


def _yellin(module) -> tuple[str, list[Path]]:
    """(the Yellin method a loaded module's limits use now, as it declares it, and the optimum interval's compiled
    driver, whose record versions it), or ("", []) for a module whose limits do not use Yellin's code (``inputs``)."""
    method = getattr(getattr(module, "info", None), "statistical_method", "") or ""
    if "Yellin" not in method:
        return "", []
    from adroit.statistics import optimum_interval
    folder = optimum_interval.code_folder()
    return method, [] if folder is None else [folder / optimum_interval.EXECUTABLE]


def _external(module) -> tuple[list[Path], list[Path], str]:
    """(the roots walked file by file, the folders taken by their own record, and what else names the version) of a
    loaded module's inputs from outside ADROIT's package (``inputs``)."""
    from adroit.experiments.xenon import DiamxXenon
    folder = getattr(module, "folder", None)
    if isinstance(module, DiamxXenon):
        folder = Path(folder)
        records = sorted((module.python.parent.parent / "lib").glob("python*/site-packages/*.dist-info"))
        return [folder / "config" / module.spec["config"], folder / "diamx", module.python], records, \
            f"batch\0{module.batch_size}"
    if folder is not None and Path(folder).is_dir():
        return [Path(folder)], [], ""
    return [], [], ""


def held(size: int, version: Callable[..., Hashable]):
    """A cache like ``functools.lru_cache`` (``cache_clear``, ``cache_info``) whose values are kept by the version of
    what they were computed from, ``version(*args)`` (built from ``inputs``), as well as by their arguments (DY-01). A
    value is kept only where ``version`` gives the same once it is computed (read afresh then, even inside a
    ``reading``); otherwise it is computed again at the new version, up to ``TRIES`` times, then ``InputsChanging``."""
    def decorate(function):
        return _Held(function, size, version)
    return decorate


class _Held:
    def __init__(self, function, size: int, version: Callable[..., Hashable]) -> None:
        functools.update_wrapper(self, function)
        self.size, self.version = size, version
        self.values: OrderedDict = OrderedDict()
        self.lock = threading.Lock()
        self.hits = self.misses = 0

    def __call__(self, *args):
        for _ in range(TRIES):
            key = (args, self.version(*args))
            with self.lock:
                if key in self.values:
                    self.values.move_to_end(key)
                    self.hits += 1
                    return self.values[key]
                self.misses += 1
            value = self.__wrapped__(*args)
            token = _FRESH.set(True)
            try:
                after = self.version(*args)
            finally:
                _FRESH.reset(token)
            if after == key[1]:
                with self.lock:
                    self.values[key] = value
                    while len(self.values) > self.size:
                        self.values.popitem(last=False)
                return value
        raise InputsChanging(f"{self.__wrapped__.__name__}{args}: its inputs changed each time it was calculated "
                             f"({TRIES} attempts)")

    def peek(self, *args):
        """The value kept for these arguments at their version now, else None: nothing computed, nothing counted."""
        key = (args, self.version(*args))
        with self.lock:
            return self.values.get(key)

    def __reduce__(self) -> str:                    # pickled by its name, as a function is (scan workers)
        return self.__qualname__

    def cache_clear(self) -> None:
        with self.lock:
            self.values.clear()
            self.hits = self.misses = 0

    def cache_info(self):
        return functools._CacheInfo(self.hits, self.misses, self.size, len(self.values))


def slug(module: str, kind: str) -> str:
    """The table's file name: 'XENONnT SR0+SR1', 'SD-proton' → 'xenonnt-sr0-sr1_sd-proton'."""
    return re.sub(r"[^a-z0-9]+", "-", module.lower()).strip("-") + "_" + kind.lower()


def _files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")


def _content(path: Path) -> bytes:
    """A file as the fingerprint sees it: Python by its syntax tree without docstrings, so that comments and
    docstrings never make a table stale; anything else byte for byte."""
    if path.suffix != ".py":
        return path.read_bytes()
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and body
                and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree).encode()


@held(16, lambda module: inputs(module))
def fingerprint(module: str) -> str:
    """The sha256 of everything the module's reference limits depend on (module docstring), kept by the version of the
    module's inputs from outside the package (``inputs``): a changed detector input is fingerprinted again (DY-01)."""
    return _digest(module, _content)


def legacy_fingerprint(module: str) -> str:
    """The first tables' fingerprint (every file byte for byte), kept to migrate them: a table whose stored value
    equals this for the installed code was computed from it (``scripts/tabulate_reference_limits.py --convert``)."""
    return _digest(module, Path.read_bytes)


def _digest(module: str, content) -> str:
    import inspect
    from adroit.experiments import registry
    from adroit.experiments.xenon import DiamxXenon
    m = registry.load_module(module)
    digest = hashlib.sha256(module.encode())
    sources = [f for path in CODE for f in _files(path)
               if f.name not in NOT_INPUTS and not any(f == q or q in f.parents for q in NOT_INPUT_PATHS)]
    sources.append(Path(inspect.getsourcefile(type(m))))
    folder = getattr(m, "folder", None)
    if isinstance(m, DiamxXenon):           # DIAMX: its driver, configuration, source and data, and its runtime's versions
        from adroit.experiments.xenon import diamx_versions    # (an operational audit's IA-01, 2026-11-10)
        package, runtime = diamx_versions(Path(folder), m.python)
        sources += [ROOT / "experiments" / "diamx_driver.py", Path(folder) / "config" / m.spec["config"], *package]
        digest.update(str(m.batch_size).encode())
        digest.update(runtime.encode())
    elif folder is not None and Path(folder).is_dir():             # a data release in the tools folder
        sources += _files(Path(folder))
    method, _ = _yellin(m)
    if method.startswith("maximum gap"):    # the tables were computed with the optimum interval: a module that would set
        digest.update(method.encode())      # its limits by the maximum gap has another fingerprint (AL1-03)
    for path in sources:
        digest.update(str(path.relative_to(ROOT) if ROOT in path.parents else path.name).encode())
        if path.is_file():
            digest.update(content(path))
    return digest.hexdigest()


def spline(masses: list[float], values: list[float]):
    """The cubic spline (not-a-knot) of log σ in log m through a table's masses."""
    from scipy.interpolate import CubicSpline
    return CubicSpline(np.log(np.asarray(masses, dtype=float)), np.log(np.asarray(values, dtype=float)))


def leave_one_out(masses: list[float], values: list[float]) -> list[float]:
    """spline/direct − 1 at each interior mass, predicted from all the others."""
    x, y = np.log(np.asarray(masses, dtype=float)), np.log(np.asarray(values, dtype=float))
    out = []
    for i in range(1, len(x) - 1):
        keep = np.arange(len(x)) != i
        out.append(float(np.exp(spline(np.exp(x[keep]), np.exp(y[keep]))(x[i]) - y[i]) - 1.0))
    return out


def _stored(module: str, kind: str) -> tuple[dict, object] | None:
    """The stored table and its spline, of one reading of its file (``file_reads``: its version's bytes, however the
    cache is evicted and refilled), or None without one."""
    from adroit.core.file_reads import consistent
    path = TABLES / f"{slug(module, kind)}.yaml"
    if not path.is_file():
        return None
    return consistent(str(path), lambda *version: _stored_at(str(path), version))


@lru_cache(maxsize=64)
def _stored_at(path: str, version: tuple[int, ...]) -> tuple[dict, object]:
    from adroit.core.file_reads import read
    data = yaml.safe_load(read(path, version))
    masses, values = data.get("masses_gev"), data.get("limits_cm2")
    return data, (spline(masses, values) if masses and values and len(masses) == len(values) >= 2 else None)


def _current(module: str, kind: str) -> tuple[dict, object] | None:
    """The stored table and its spline where the table is current (its fingerprint is that of the code and of the
    module's inputs as they are now), else None."""
    from adroit.experiments.base import DataUnavailable
    found = _stored(module, kind)
    if found is None:
        return None
    try:
        now = fingerprint(module)
    except (InputsChanging, DataUnavailable, KeyError, OSError, ValueError):   # its limit then by its own procedure,
        return None                                     # which names why there is none (the audit loop's AL1-14)
    return found if found[0].get("fingerprint") == now else None


def table(module: str, kind: str) -> dict | None:
    """The stored table, or None if there is none or it is stale (its fingerprint differs from the code's and the
    module's inputs' as they are now: ``inputs``, DY-01)."""
    found = _current(module, kind)
    return None if found is None else found[0]


def tolerance(data: dict, mass_gev: float | None = None) -> float:
    """η: the relative uncertainty a table's interpolated value is used with. At a mass, twice the larger
    leave-one-out error of the two tabulated masses around it (the error is local: large only where the limit turns
    steeply, at a kinematic threshold); without one, twice the table's largest."""
    errors = data.get("leave_one_out")
    if mass_gev is None or not errors:
        return max(2.0 * float(data["interpolation_accuracy"]), TOLERANCE_FLOOR)
    masses = data["masses_gev"]
    local = [0.0, *[abs(e) for e in errors], 0.0]       # the end masses are computed directly, never predicted
    local[0], local[-1] = local[1], local[-2]           # so they take their neighbour's error
    i = int(np.clip(np.searchsorted(masses, mass_gev) - 1, 0, len(masses) - 2))
    return max(2.0 * max(local[i], local[i + 1]), TOLERANCE_FLOOR)


def lookup(module: str, kind: str, mass_gev: float) -> tuple[float, float] | None:
    """(the interpolated 95% limit in cm², its tolerance η), or None where no current table covers the mass: the table
    and its spline of one reading."""
    found = _current(module, kind)
    if found is None or found[1] is None:
        return None
    data, curve = found
    masses = data["masses_gev"]
    if not masses[0] * (1 - 1e-9) <= mass_gev <= masses[-1] * (1 + 1e-9):
        return None
    mass = min(max(mass_gev, masses[0]), masses[-1])
    return float(np.exp(curve(math.log(mass)))), tolerance(data, mass)


def current() -> list[str]:
    """'module, kind' of every stored table that is current (its fingerprint matches the code)."""
    from adroit.experiments import registry
    if not TABLES.is_dir():
        return []
    stems = {p.stem for p in TABLES.glob("*.yaml")}
    return [f"{name} {kind}" for name in registry.module_names() for kind in KINDS
            if slug(name, kind) in stems and table(name, kind) is not None]


def clear_cache() -> None:
    """Clear the cached fingerprints, tables and splines, so tables are reread and their currency rechecked."""
    fingerprint.cache_clear()
    _stored_at.cache_clear()

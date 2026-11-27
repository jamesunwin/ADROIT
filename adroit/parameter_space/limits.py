"""The direct-detection envelope a scan compares with (DM13).

The strongest validated limit of the system's own modules at each mass, for a
kind of scattering (SI, SD-proton, SD-neutron). Native 90% validation curves
are read from DM3. The 95% verdict calls the actual module procedure via
``at95``; its likelihood calculations stay inside the native validated range.

**Each module's limit** (``per_module95``) is kept, so that a channel whose
rate depends on the target (spin-independent couplings with c_p ≠ c_n) is
compared module by module (``dd_channels``).

**Edge-clause masses.** DM3 validates a module at a mass where its curve
reaches the published one within a 3% shift in mass, on a steep threshold (the
edge clause). There, the module's limit can be stronger than the published
one: 0.64× for PICO at 3.02 GeV. At such masses the limit used is
max(module, published 90% curve), so no verdict there rests on a limit
stronger than the published one (``edge_floor``).

**Construction.** Each limit records its sidedness: DIAMX's xenon searches
use alea's two-sided t̃ (an interval from 2Φ(√t̃) − 1), so their 95% upper
limit sits at 1.96σ in the Gaussian approximation; the LZ extended window
quotes two-sided profile-likelihood intervals; the other modules set one-sided
upper limits (1.645σ at 95%). The combined likelihood uses this
(``likelihood.combined``).

**Precomputed tables** (R10). The xenon searches' limits come from tables where a current one covers the mass
(``limit_tables``), each with its tolerance η (``tolerance``); ``dd_channels.compare`` recomputes a point exactly
whenever its verdict could change within η. ``exact()`` (in this process) or ``ADROIT_EXACT_LIMITS=1`` (inherited
by scan workers) turns the tables off.

**At a halo of the region** (``halo_limits.using``; the owner's halo nuisances, 2026-10-19): ``per_module95`` and
``at95`` give each module's limit at that halo (``halo_limits.per_module95``: exactly for the fast modules, by a
validated count ratio for the slow ones), and ``tolerance`` the margin a comparison there must clear.
"""

from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

import numpy as np

from adroit.experiments import status
from adroit.core.state import StrictModel
from adroit.parameter_space import limit_tables
from pydantic import Field

STORE = Path(__file__).resolve().parents[2] / "docs" / "dm3" / "validation_results.json"
TWO_SIDED = frozenset({"LZ WS2022+WS2024", "XENONnT SR0+SR1", "PandaX-4T Run0+Run1", "LZ extended window (2026)"})
DD_KINDS = ("SI", "SD-proton", "SD-neutron")


def sidedness(module: str) -> str:
    """How a module's upper limit is constructed: "two-sided" or "one-sided" ("unknown" without a module)."""
    if not module:
        return "unknown"
    return "two-sided" if module in TWO_SIDED else "one-sided"


class StatisticalLimit(StrictModel):
    """A limit with its confidence level and actual statistical provenance."""

    value: float | None
    confidence_level: float
    source: str = ""
    construction: str
    omitted: dict[str, str] = Field(default_factory=dict)
    sidedness: str = "unknown"          # "one-sided", "two-sided" or "unknown" (module docstring)


_EXACT: ContextVar[bool] = ContextVar("exact_limits", default=False)
EXACT_VARIABLE = "ADROIT_EXACT_LIMITS"


def tabulated() -> bool:
    """Whether the precomputed tables may be used here (module docstring)."""
    return not _EXACT.get() and os.environ.get(EXACT_VARIABLE, "") not in ("1", "true", "yes")


@contextmanager
def exact():
    """Inside: every limit by the module's own procedure, never a table (this process only)."""
    token = _EXACT.set(True)
    try:
        yield
    finally:
        _EXACT.reset(token)


@contextmanager
def exact_environment(on: bool = True):
    """Inside: no tables in this process or in any scan worker it starts (an environment variable)."""
    before = os.environ.get(EXACT_VARIABLE)
    if on:
        os.environ[EXACT_VARIABLE] = "1"
    try:
        yield
    finally:
        if before is None:
            os.environ.pop(EXACT_VARIABLE, None)
        else:
            os.environ[EXACT_VARIABLE] = before


def limit_model(module, kind):
    """The nuclear model ``module``'s reference limit of ``kind`` is computed with: Klos et al.'s structure factors for
    the xenon searches' SD limits (``xenon.SD_MODEL``, as their ``reference_limits``), the conventions' model otherwise.
    Anything that rescales a prediction onto that limit (the SD proton–neutron correction) must use the same (1.0.1:
    the xenon correction had used the conventions' shell model, about 25 times too large). Kept here, outside the code
    the limit tables are fingerprinted by, so that it changes no stored table; ``tests/parameter_space/
    test_sd_nuclear_consistency.py`` checks it against what ``reference_limits`` uses."""
    from adroit.core.dm_state import CrossSectionKind
    from adroit.experiments.xenon import SD_MODEL, DiamxXenon
    k = CrossSectionKind(kind)
    if isinstance(module, DiamxXenon) and k in (CrossSectionKind.sd_proton, CrossSectionKind.sd_neutron):
        return SD_MODEL
    return module.conventions().model_for(k)


def tolerance(module: str, kind: str, mass_gev: float) -> float:
    """η of the module's limit at the mass as ``per_module95`` gives it now: 0 when computed directly; at a halo of
    the region, the margin its comparison there must clear (``halo_limits``)."""
    from adroit.parameter_space import halo_limits
    state = halo_limits.active()
    if state is not None:
        return state.margins.get((module, kind, mass_gev), 0.0)
    return reference_tolerance(module, kind, mass_gev)


def reference_tolerance(module: str, kind: str, mass_gev: float) -> float:
    """η of the module's limit at its own reference halo (0 when computed directly): of the table its limit was taken
    from, where that limit is kept (``_reference_limit``), so that a limit and its tolerance are of one reading of one
    table (the audit loop's AL1-05, 2026-11-14); else of the table as it is now."""
    from adroit.parameter_space import limit_tables
    if not tabulated():
        return 0.0
    kept = _reference_limit.peek(module, kind, mass_gev, True)
    if kept is not None:
        return kept[2]
    found = limit_tables.lookup(module, kind, mass_gev)
    return found[1] if found else 0.0


def per_module95(kind: str, mass_gev: float, excluded_modules: tuple[str, ...] = ()
                 ) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, str], ...]]:
    """Each validated module's 95% limit at the mass by its own procedure, ((module, σ), ...), and the
    modules that gave none, ((module, why), ...). At an edge-clause mass a limit is floored at the published
    curve (``edge_floor``). A xenon search's limit comes from its precomputed table where a current one covers
    the mass, unless exact limits are asked for (module docstring). At a halo of the region, each one there
    (``halo_limits.per_module95``)."""
    from adroit.parameter_space import halo_limits
    state = halo_limits.active()
    if state is not None:
        return halo_limits.per_module95(state, kind, mass_gev, tuple(excluded_modules))
    return _per_module95_now(kind, mass_gev, tuple(excluded_modules), tabulated())


def reference95(kind: str, mass_gev: float, excluded_modules: tuple[str, ...] = ()
                ) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, str], ...]]:
    """``per_module95`` at each module's own reference halo, the tables allowed unless the environment turns them off
    (a comparison recomputed directly at a halo of the region needs the modules, not their reference limits)."""
    return _per_module95_now(kind, mass_gev, tuple(excluded_modules), tables_allowed())


def tables_allowed() -> bool:
    """Whether the environment allows the precomputed tables (``ADROIT_EXACT_LIMITS``; ``exact()`` aside)."""
    return os.environ.get(EXACT_VARIABLE, "") not in ("1", "true", "yes")


def exact_requested() -> bool:
    """Whether this process asked for every limit by its own procedure (inside ``exact()``)."""
    return _EXACT.get()


def eligible(kind: str, mass_gev: float, excluded_modules: tuple[str, ...] = ()) -> list[str]:
    """The modules validated for the kind at the mass (each one ``per_module95`` asks), computing no limit."""
    from adroit.experiments import registry
    out = []
    for name in registry.module_names():
        if name in excluded_modules:
            continue
        span = status.validated_range(name, kind)
        if span is not None and span[0] <= mass_gev <= span[1]:
            out.append(name)
    return out


def reference_limit(name: str, kind: str, mass_gev: float, use_tables: bool) -> tuple[float | None, str]:
    """(the module's 95% limit at its own reference halo, edge-floored, or None; why there is none): its current
    table where one covers the mass and ``use_tables``, else its own procedure.

    Kept by the version of the module's inputs (``limit_tables.inputs``) as well as by its arguments: a limit computed
    before a detector input changed is not given after it, whether it came from a table (then stale) or from the
    module's procedure (the auditor's DX recheck, DY-01, 2026-11-13: kept by name, a warm comparison had excluded with the
    old limit, labelled a current table's)."""
    try:
        value, why, _ = _reference_limit(name, kind, mass_gev, use_tables)
    except limit_tables.InputsChanging as error:
        return None, str(error)
    return value, why


@limit_tables.held(4096, lambda name, kind, mass_gev, use_tables: limit_tables.inputs(name))
def _reference_limit(name: str, kind: str, mass_gev: float, use_tables: bool) -> tuple[float | None, str, float]:
    """``reference_limit``'s (limit, why there is none), with η of the table it was taken from (0 when computed
    directly): the limit and its tolerance of one reading (``reference_tolerance``, AL1-05). Kept by the module's
    inputs, its stored tables' files among them (``limit_tables.inputs``)."""
    from adroit.core.dm_state import CrossSectionKind
    from adroit.experiments import registry
    from adroit.experiments.base import DataUnavailable
    from adroit.parameter_space import limit_tables
    stored = limit_tables.lookup(name, kind, mass_gev) if use_tables else None
    if stored is not None:
        return max(stored[0], edge_floor(name, kind, mass_gev) or 0.0), "", stored[1]
    try:
        module = registry.load_module(name)
        value = module.reference_limits(CrossSectionKind(kind), [mass_gev], workers=1, cl=0.95)[0]
    except (DataUnavailable, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        return None, str(error), 0.0
    if np.isfinite(value) and value > 0:
        return max(value, edge_floor(name, kind, mass_gev) or 0.0), "", 0.0
    return None, "no finite 95% limit", 0.0


def _versions(kind: str, mass_gev: float, excluded_modules: tuple[str, ...], *_) -> tuple[tuple[str, str], ...]:
    """The input versions (``limit_tables.inputs``) of the modules a limit at the mass is taken from."""
    return tuple((name, limit_tables.inputs(name)) for name in eligible(kind, mass_gev, excluded_modules))


def _per_module95_now(kind: str, mass_gev: float, excluded_modules: tuple[str, ...], use_tables: bool
                      ) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, str], ...]]:
    try:
        return _per_module95(kind, mass_gev, excluded_modules, use_tables)
    except limit_tables.InputsChanging as error:
        return (), tuple((name, str(error)) for name in eligible(kind, mass_gev, excluded_modules))


@limit_tables.held(4096, _versions)
def _per_module95(kind: str, mass_gev: float, excluded_modules: tuple[str, ...], use_tables: bool
                  ) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, str], ...]]:
    found, omitted = [], {}
    for name in eligible(kind, mass_gev, excluded_modules):
        value, why = reference_limit(name, kind, mass_gev, use_tables)
        if value is None:
            omitted[name] = why
        else:
            found.append((name, value))
            if weaker := fallback(name):                  # it excludes; it never allows (D1)
                omitted[name] = weaker
    return tuple(found), tuple(omitted.items())


MAXIMUM_GAP_FALLBACK = ("the optimum interval code is not available here: its limit is Yellin's maximum gap, never "
                        "stronger, which decides an exclusion but not an allowed point")


def fallback(name: str) -> str:
    """Why a module's limit decides exclusions only, or "": an interval search whose limit is the maximum gap's in
    place of the optimum interval's (``experiments.base.interval_limit``, its method declared by ``interval_method``;
    the owner's decision on the fallback review's D1, 2026-10-20: the exclusions of a weaker valid limit stand, an
    allowed point on it is undecided, the method named). The method is the one the module's inputs were read with
    (``limit_tables.statistical_method``: inside a ``reading``, at their first use there), so the flag goes with the
    limit those inputs keep (AL2-08)."""
    from adroit.parameter_space import limit_tables
    return MAXIMUM_GAP_FALLBACK if limit_tables.statistical_method(name).startswith("maximum gap") else ""


def fallback_of(module) -> str:
    """``fallback`` for a loaded module (Path 1's rows carry it: ``exclusion.ModuleLimits.excludes_only``)."""
    info = getattr(module, "info", None)                    # a module that declares no method has none
    method = getattr(info, "statistical_method", "") or ""
    return MAXIMUM_GAP_FALLBACK if method.startswith("maximum gap") else ""


def excludes_only(statistic: StatisticalLimit | None) -> bool:
    """Whether a limit was set with a maximum-gap fallback among its modules (``fallback``): a prediction above it is
    excluded, one below it undecided (D1; C21-04 for the limits through Path 1)."""
    return statistic is not None and MAXIMUM_GAP_FALLBACK in statistic.omitted.values()


def at95(kind: str, mass_gev: float, excluded_modules: tuple[str, ...] = ()) -> StatisticalLimit:
    """Compute 95% with the experiment's procedure inside its native validated range: the strongest module.

    Native-90% curves remain unchanged in ``table``/``envelope``. This calculation
    asks each module for a new CL; it does not rescale a published curve. A tabulated value says so in its
    construction, with its tolerance. At a halo of the region, the strongest there (never cached).
    """
    from adroit.parameter_space import halo_limits
    state = halo_limits.active()
    if state is not None:
        found, omitted = per_module95(kind, mass_gev, excluded_modules)
        source = min(found, key=lambda item: item[1])[0] if found else ""
        at = f"; {halo_limits.describe(state)}: {state.constructions.get((source, kind, mass_gev), '')}"
        return _strongest(kind, mass_gev, found, omitted, at)
    try:
        return _at95(kind, mass_gev, tuple(excluded_modules), tabulated())
    except limit_tables.InputsChanging:
        return _strongest(kind, mass_gev, *per_module95(kind, mass_gev, excluded_modules))


@limit_tables.held(2048, _versions)
def _at95(kind: str, mass_gev: float, excluded_modules: tuple[str, ...], use_tables: bool) -> StatisticalLimit:
    return _strongest(kind, mass_gev, *per_module95(kind, mass_gev, excluded_modules))


def _strongest(kind: str, mass_gev: float, found, omitted, at: str = "") -> StatisticalLimit:
    """The strongest of the modules' limits, with its construction (``at``: the halo it was taken at)."""
    source, value = min(found, key=lambda item: item[1]) if found else ("", None)
    eta = tolerance(source, kind, mass_gev) if source and not at else 0.0
    return StatisticalLimit(value=value, confidence_level=0.95, source=source,
                            construction="module procedure evaluated at CL=0.95"
                            + (f" ({sidedness(source)})" if source else "")
                            + (f"; interpolated from its precomputed table (±{100 * eta:.1f}%)" if eta else "") + at,
                            omitted=dict(omitted), sidedness=sidedness(source))


def clear_cache() -> None:
    """Forget every computed 95% limit (tests that change the module list)."""
    from adroit.parameter_space import limit_tables
    _per_module95.cache_clear()
    _reference_limit.cache_clear()
    _at95.cache_clear()
    _stretch.cache_clear()
    limit_tables.clear_cache()


def _latest(kind: str) -> dict[str, dict]:
    """The latest DM3 rule comparison of each module for a kind."""
    latest = {}
    for entry in json.loads(STORE.read_text())["comparisons"]:
        r = entry["result"]
        if r.get("kind") == kind and entry.get("rule"):
            latest[r["experiment"]] = r
    return latest


@lru_cache(maxsize=64)
def _stretch(module: str, kind: str) -> tuple[float, float, tuple[float, ...], tuple[float, ...]] | None:
    """(first, last) validated masses that pass by the ratio rule, not the edge clause, and the published curve
    (masses, σ); None when the module has no validated range for the kind."""
    r, span = _latest(kind).get(module), status.validated_range(module, kind)
    if r is None or span is None:
        return None
    masses, published = r["masses_gev"], r["published_cm2"]
    edges = r.get("edge_passes") or [False] * len(masses)
    inside = [i for i, m in enumerate(masses) if span[0] * (1 - 1e-4) <= m <= span[1] * (1 + 1e-4)]
    by_ratio = [masses[i] for i in inside if not edges[i]]
    good = [(m, s) for m, s in zip(masses, published) if s and np.isfinite(s) and s > 0]
    if not good:
        return None
    low, high = (min(by_ratio), max(by_ratio)) if by_ratio else (np.inf, -np.inf)
    return low, high, tuple(m for m, _ in good), tuple(s for _, s in good)


def edge_floor(module: str, kind: str, mass_gev: float) -> float | None:
    """The published (90%) curve at a mass validated only by the edge clause, else None."""
    found = _stretch(module, kind)
    if found is None:
        return None
    low, high, masses, published = found
    if low <= mass_gev <= high:
        return None
    return float(np.exp(np.interp(np.log(mass_gev), np.log(masses), np.log(published))))


@lru_cache(maxsize=8)
def table(kind: str) -> tuple[tuple[float, ...], tuple[float, ...], tuple[str, ...]]:
    """(masses, the strongest validated limit at each, the module that sets it) on a log grid of 1 GeV–10 TeV."""
    store = json.loads(STORE.read_text())["comparisons"]
    latest = {}
    for entry in store:
        r = entry["result"]
        if r.get("kind") == kind and entry.get("rule"):
            latest[r["experiment"]] = r
    grid = np.geomspace(0.3, 1e4, 500)
    best, who = np.full(grid.size, np.inf), np.array([""] * grid.size, dtype=object)
    for name, r in latest.items():
        span = status.validated_range(name, kind)
        if span is None:
            continue
        m, s = np.array(r["masses_gev"]), np.array(r["reproduced_cm2"])
        ok = (m >= span[0] * (1 - 1e-4)) & (m <= span[1] * (1 + 1e-4)) & np.isfinite(s) & (s > 0)
        if ok.sum() < 2:
            continue
        inside = (grid >= m[ok].min()) & (grid <= m[ok].max())
        values = np.exp(np.interp(np.log(grid), np.log(m[ok]), np.log(s[ok])))
        better = inside & (values < best)
        best, who = np.where(better, values, best), np.where(better, name, who)
    return tuple(grid), tuple(best), tuple(who)


def envelope(kind: str, mass_gev: float) -> float | None:
    """The strongest validated limit (cm²) at a mass, or None outside every validated range."""
    grid, best, _ = table(kind)
    value = float(np.exp(np.interp(np.log(mass_gev), np.log(grid), np.log(best))))
    return value if np.isfinite(value) else None


def setter(kind: str, mass_gev: float) -> str:
    """The module that sets the envelope at a mass."""
    grid, _, who = table(kind)
    return str(who[int(np.argmin(np.abs(np.log(np.array(grid)) - np.log(mass_gev))))])

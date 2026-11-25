"""Mediator production at the LHC (13 TeV): cross-section tables computed with MadGraph, at unit couplings.

A portal's mediator is produced singly (pp → Z′ through q q̄; gg → S through the top and bottom
loops), and an inert doublet's scalars in pairs (Drell–Yan). Each process is tabulated once over
the mediator's mass at unit couplings by MadGraph 3.8 (LO, NNPDF2.3, μ = M) in the tools folder,
as JSON (``<tools>/madgraph-xsec/<name>.json``: ``columns`` and ``data`` with mass in GeV and σ in
pb). In the narrow-width approximation a point's cross-section is the table's times its couplings
squared; the branching fractions are the portal's own. Gluon fusion carries the Higgs Cross
Section Working Group's K-factor (≈ 2.5); q q̄ → Z′ is left at LO (K ≈ 1.2–1.35, conservative).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import numpy as np
from scipy.interpolate import CubicSpline

from adroit.core.config import get_settings


K_TABLE = "ggS_kfactors_13TeV"


def folder() -> Path:
    """The tools folder's directory of MadGraph cross-section tables."""
    return get_settings().tools_dir / "madgraph-xsec"


def available(name: str) -> bool:
    """Whether the table ``name`` is in the tools folder."""
    return (folder() / f"{name}.json").exists()


def _listed(names: list[str]) -> str:
    return ", ".join(names) if len(names) <= 3 else f"{', '.join(names[:3])} and {len(names) - 3} more"


def unavailable(*names: str) -> str:
    """Why these tables cannot be used: '' if each is in the tools folder, else which are not (a search then reports
    the point undecided with this reason, never silently)."""
    missing = [name for name in names if not available(name)]
    return (f"MadGraph's production table{'s' if len(missing) > 1 else ''} {_listed(missing)} not in the tools "
            "folder (adroit setup --fetch)") if missing else ""


class Table(NamedTuple):
    """One reading of a production table: its masses (ascending), one column's values, the whole file, and the column's
    cubic spline in (ln M, ln σ) (None with fewer than two masses)."""
    masses: np.ndarray
    values: np.ndarray
    data: dict
    spline: CubicSpline | None

    def covers(self, masses) -> bool:
        """Whether every mass lies within this reading's masses."""
        masses = np.asarray(masses, dtype=float)
        return len(self.masses) >= 2 and bool(np.all((masses >= self.masses[0]) & (masses <= self.masses[-1])))


def table(name: str, column: str = "sigma_pb") -> Table:
    """The table ``name`` as it is now, one reading: its values, range, metadata and spline are all of the bytes of one
    version of the file (``file_reads``: its device, inode, size, and modification and change times), however the
    cache's entries are evicted and refilled. A caller takes everything it uses from the one ``Table`` returned.

    the auditor's DX recheck (DY-02, 2026-11-13): the values and the spline had been cached apart, each by the table's stat,
    and an entry refilled after eviction had been read from the file as it then was, not the version that keyed it: a
    replaced table, its old range with its replacement's spline, gave 6 pb at 200 GeV where neither table did. Before
    that (BI-02, 2026-11-12), both had been cached by the table's name."""
    from adroit.core.file_reads import consistent
    path = str(folder() / f"{name}.json")
    return consistent(path, lambda *version: _read(path, version, column))


@lru_cache(maxsize=32)
def _read(path: str, version: tuple[int, ...], column: str) -> Table:
    from adroit.core.file_reads import read
    data = json.loads(read(path, version))             # the bytes of exactly this version, or Moved
    columns = data.get("columns", ["mass_gev", "sigma_pb"])
    rows = data.get("rows") or data.get("data")
    i_m, i_s = (columns.index("mass_gev") if "mass_gev" in columns else 0), columns.index(column)
    pairs = sorted((r[i_m], r[i_s]) for r in rows if isinstance(r[i_s], (int, float)) and r[i_s] > 0)
    masses, values = np.array([a for a, _ in pairs]), np.array([b for _, b in pairs])
    spline = CubicSpline(np.log(masses), np.log(values)) if len(masses) >= 2 else None
    return Table(masses, values, data, spline)


def sigma_pb(name: str, mass: float, column: str = "sigma_pb") -> float | None:
    """σ (pb) of a tabulated process at unit couplings, a cubic spline in (ln M, ln σ): 0.2% on the Z′ grid
    against 14% for linear interpolation, leaving every other node out (the MadGraph survey: 0.1% on the full
    grid). Another column of the table (a K-factor) is interpolated linearly in ln M. None outside the table."""
    if not available(name):
        return None
    held = table(name, column)                      # one reading: the range and the spline are of one version
    if not held.covers([mass]):
        return None
    if column.startswith("sigma") and len(held.masses) >= 4:
        return float(np.exp(held.spline(math.log(mass))))
    return float(np.exp(np.interp(math.log(mass), np.log(held.masses), np.log(held.values))))


def mass_range(name: str) -> tuple[float, float] | None:
    """The lowest and highest mass (GeV) of a tabulated process; None without the table."""
    if not available(name):
        return None
    masses = table(name).masses
    return (float(masses[0]), float(masses[-1])) if len(masses) >= 2 else None


def sigma_pb_grid(name: str, masses: np.ndarray) -> np.ndarray:
    """``sigma_pb`` at each of ``masses``, its cubic spline in (ln M, ln σ), from one reading of the table.

    Raises:
        ValueError: a mass outside that reading (a range taken from another reading, ``mass_range``, is not this
            one's: a caller that needs both takes them from one ``table``)."""
    held = table(name)
    if not held.covers(masses):
        raise ValueError(f"{name}: masses outside the table as it is now "
                         f"({held.masses[0] if len(held.masses) else 'none'}–"
                         f"{held.masses[-1] if len(held.masses) else 'none'} GeV); it was replaced since its range was read")
    return np.exp(held.spline(np.log(masses)))


def gluon_fusion_k(mass: float) -> float | None:
    """K = σ(NNLO+NNLL)/σ(LO) of gg → S through the top and bottom loops: the Higgs Cross Section Working
    Group's heavy-Higgs σ (YR4, arXiv:1610.07922) over MadGraph's LO in the same setup."""
    return sigma_pb(K_TABLE, mass, "K_loop")


def heavy_higgs_pb(mass: float) -> float | None:
    """σ(gg → H) (pb) of a Standard-Model-like heavy Higgs at NNLO+NNLL (the Working Group's quark-loop σ)."""
    return sigma_pb(K_TABLE, mass, "sigma_HXSWG_quarkloop_NNLO_NNLL_pb")


def describe(name: str) -> dict:
    """The table's metadata (process, couplings, PDF, scale, K-factor, MadGraph version)."""
    return {k: v for k, v in table(name).data.items() if k not in ("rows", "data")}

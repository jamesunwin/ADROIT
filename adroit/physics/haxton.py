"""Nuclear responses from the updated density matrices of Haxton and McElvain (DM5).

LZ computes its signal spectra with one-body density matrices for xenon that
were revised after the published shell-model tables (arXiv:2312.02030,
section II; github.com/Berkeley-Electroweak-Physics/Elastic). They change the
spin-dependent responses in particular. This module turns those density
matrices into the eight response functions W_k^{ττ'}(y) with the multipole
matrix elements of the Mu2e scripts of the same group (BSD-3), run in their
own environment (``haxton_driver.py``). Neither the density matrices nor the
scripts are copied into this repository: both are fetched into the tools
folder, and the tabulated form factors are cached there.

**Normalisation.** The driver returns the reduced matrix elements
F_k(J; τ) = ⟨J_i‖Σ_i O_J(i) t^τ(i)‖J_i⟩, with t^0 = 1 and t^1 = τ₃ (+1 for a
proton); at y = 0, F_M(0; 0) = A √(2J_i+1)/√(4π). The responses in the
normalisation of ``nuclear`` (τ = 0 multiplying c^p + c^n) are

    W_k^{ττ'}(y) = ¼ Σ_J F_k(J; τ) F_k(J; τ'),

and for the two interferences W_{Φ''M} = ¼ Σ_J F_Φ''(J; τ) F_M(J; τ') and
W_{ΔΣ'} = ¼ Σ_J F_Δ(J; τ) F_Σ'(J; τ'). The tests check these against the
published tables where the density matrices coincide.
"""

from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline

from adroit.core.config import get_settings
from adroit.core.dm_state import Isotope
from adroit.external import fetch
from adroit.physics.conventions import HBARC_GEV_FM

ELASTIC = "Elastic density matrices (Haxton & McElvain)"
MU2E = "Mu2e nuclear-response scripts (Berkeley-Electroweak-Physics)"
DRIVER = Path(__file__).with_name("haxton_driver.py")
Y_GRID = np.linspace(0.0, 6.0, 121)
# The shell-model interaction of each isotope's density matrix: LZ's GCN5082 for xenon.
INTERACTIONS = {"Xe": "GCN5082", "I": "GCN5082", "Cs": "GCN5082", "Ge": "GCN2850", "F": "usdb",
                "Na": "usdb", "Al": "usdb", "Si": "usdb", "C": "ck", "Ar": "Sussex"}
PAIRS = {  # response index in nuclear.RESPONSES → (left operator, right operator)
    0: ("M", "M"), 1: ("SigmaPP", "SigmaPP"), 2: ("SigmaP", "SigmaP"), 3: ("PhiPP", "PhiPP"),
    4: ("PhiTP", "PhiTP"), 5: ("Delta", "Delta"), 6: ("PhiPP", "M"), 7: ("Delta", "SigmaP")}


class ResponsesUnavailable(RuntimeError):
    """The density matrices or the scripts have not been fetched, or an isotope is not covered."""


def _paths() -> tuple[Path, Path, Path]:
    """(the Elastic folder, the Mu2e script, the Mu2e environment's Python)."""
    elastic, mu2e = fetch.locate(ELASTIC), fetch.locate(MU2E)
    if elastic is None or mu2e is None:
        raise ResponsesUnavailable(f"fetch {ELASTIC!r} and {MU2E!r} first")
    python = get_settings().tools_dir / ".venv-mu2e" / "bin" / "python"
    if not python.exists():
        raise ResponsesUnavailable(f"build the Mu2e environment at {python.parent.parent}")
    return elastic, mu2e / "python" / "mu2e.py", python


def density_matrix_file(isotope: Isotope) -> Path | None:
    """The isotope's density-matrix file in the Elastic folder, if there is one."""
    try:
        elastic = _paths()[0]
    except ResponsesUnavailable:
        return None
    interaction = INTERACTIONS.get(isotope.element)
    if interaction is None:
        return None
    for name in (interaction, interaction.lower(), interaction.upper()):
        path = elastic / f"{isotope.element}{isotope.mass_number}_{name}.txt"
        if path.is_file():
            return path
    return None


def _cache(isotope: Isotope, interaction: str) -> Path:
    folder = get_settings().tools_dir / "nuclear-responses"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"haxton_{isotope.name}_{interaction}.json"


def form_factors(isotope: Isotope, interaction: str | None = None) -> dict[str, np.ndarray]:
    """F_k(J; τ) on ``Y_GRID``, keyed "operator|J|τ", computed once and cached.

    Args:
        isotope: the nucleus.
        interaction: the shell-model interaction of the density matrix
            ("GCN5082", "bw", ...); by default ``INTERACTIONS[element]``.
    """
    interaction = interaction or INTERACTIONS[isotope.element]
    cache = _cache(isotope, interaction)
    if not cache.is_file():
        elastic, script, python = _paths()
        request = {"mu2e": str(script), "elastic": str(elastic), "y": Y_GRID.tolist(),
                   "isotopes": [{"symbol": isotope.element, "A": isotope.mass_number,
                                 "Z": isotope.atomic_number, "J": isotope.spin,
                                 "interaction": interaction}]}
        done = subprocess.run([str(python), str(DRIVER)], input=json.dumps(request),
                              capture_output=True, text=True, check=True)
        cache.write_text(json.dumps(json.loads(done.stdout)[isotope.name]))
    return {k: np.array(v) for k, v in json.loads(cache.read_text()).items()}


@lru_cache(maxsize=64)
def _splines(element: str, mass_number: int, atomic_number: int,
             spin: float) -> list[list[list[CubicSpline]]]:
    isotope = Isotope(element=element, mass_number=mass_number, atomic_number=atomic_number,
                      spin=spin, mass_fraction=1.0)
    table = responses_on_grid(isotope)
    return [[[CubicSpline(Y_GRID, table[k, t, u]) for u in (0, 1)] for t in (0, 1)]
            for k in range(table.shape[0])]


def responses_on_grid(isotope: Isotope, interaction: str | None = None) -> np.ndarray:
    """W_k^{ττ'} on ``Y_GRID``, shape (8, 2, 2, len(Y_GRID))."""
    f = form_factors(isotope, interaction)
    multipoles = sorted({int(key.split("|")[1]) for key in f})
    out = np.zeros((len(PAIRS), 2, 2, Y_GRID.size))
    for k, (left, right) in PAIRS.items():
        for t in (0, 1):
            for u in (0, 1):
                out[k, t, u] = 0.25 * sum(f.get(f"{left}|{j}|{t}", 0.0) * f.get(f"{right}|{j}|{u}", 0.0)
                                          for j in multipoles)
    return out


def responses(isotope: Isotope, q_gev: np.ndarray, b_fm: float) -> np.ndarray:
    """W_k^{ττ'}(q) for the isotope, shape (8, 2, 2, len(q)); zero beyond the tabulated y."""
    if density_matrix_file(isotope) is None:
        raise ResponsesUnavailable(f"no Haxton–McElvain density matrix for {isotope.name}")
    y = (np.asarray(q_gev, dtype=float) * b_fm / (2.0 * HBARC_GEV_FM)) ** 2
    splines = _splines(isotope.element, isotope.mass_number, isotope.atomic_number, isotope.spin)
    inside = y <= Y_GRID[-1]
    out = np.zeros((len(PAIRS), 2, 2, y.size))
    for k in range(len(PAIRS)):
        for t in (0, 1):
            for u in (0, 1):
                out[k, t, u] = np.where(inside, splines[k][t][u](np.minimum(y, Y_GRID[-1])), 0.0)
    return out

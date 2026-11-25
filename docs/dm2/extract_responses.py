"""Extract the shell-model nuclear responses into the project's data file.

The responses W_k^{ττ'}(y) of Anand et al. (arXiv:1308.6288) and Catena &
Schwabe (arXiv:1501.03729) are published as polynomial fits,
W(y) = exp(−2y) Σ_n a_n yⁿ. WIMpy_NREFT (MIT licence) carries them as Python
functions; this script reads those functions symbolically, writes the
coefficients to ``adroit/physics/data/shell_model_responses.json``, and
checks them against WimPyDD's table of the same fits, where the owner has
downloaded WimPyDD.

Run from the repository root, with the reference codes in data/external/:

    uv run python docs/dm2/extract_responses.py

Two index conventions are fixed here, once:
- The interference responses are tabulated as W_{MΦ''} and W_{Σ'Δ}. The rate
  formula needs W_{Φ''M}^{ττ'} = W_{MΦ''}^{τ'τ} and W_{ΔΣ'}^{ττ'} = W_{Σ'Δ}^{τ'τ}
  (the order both reference codes use), so those two are stored transposed.
- The isospin normalisation is that of both codes: the coefficients the
  responses multiply are c^p ± c^n.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import sympy

ROOT = Path(__file__).resolve().parents[2]
WIMPY = ROOT / "data/external/WIMpy_NREFT/WIMpy"
WIMPYDD = ROOT / "data/external/manual/WimPyDD"
OUT = ROOT / "adroit/physics/data/shell_model_responses.json"

# Our name → (WIMpy module, its calc function, transposed?)
RESPONSES = {
    "M": ("WM", "calcwm", False),
    "Sigma''": ("WS2", "calcws2", False),
    "Sigma'": ("WS1", "calcws1", False),
    "Phi''": ("WP2", "calcwp2", False),
    "PhiTilde'": ("WP1", "calcwp1", False),
    "Delta": ("WD", "calcwd", False),
    "Phi''M": ("WMP2", "calcwmp2", True),
    "DeltaSigma'": ("WS1D", "calcws1d", True),
}
# WimPyDD's index for each response and its target code (itar) for each isotope.
WIMPYDD_INDEX = {"M": 0, "Sigma''": 1, "Sigma'": 2, "Phi''": 3, "PhiTilde'": 4,
                 "Delta": 5, "Phi''M": 6, "DeltaSigma'": 7}
WIMPYDD_ITAR = {"C12": 1, "F19": 2, "Na23": 3, "Si28": 4, "Ge70": 5, "Ge72": 6, "Ge73": 7,
                "Ge74": 8, "Ge76": 9, "I127": 10, "Xe128": 11, "Xe129": 12, "Xe130": 13,
                "Xe131": 14, "Xe132": 15, "Xe134": 16, "Xe136": 17, "O16": 18, "Ar40": 19,
                "Ca40": 20, "H": 21, "He3": 22, "He4": 23, "N14": 24, "Ne20": 25, "Mg24": 26,
                "Al27": 27, "S32": 28, "Fe56": 29, "Ni58": 30}


def load_module(name: str) -> types.ModuleType:
    """Import one WIMpy response file with exp(2y) replaced by 1, leaving the polynomial."""
    spec = importlib.util.spec_from_file_location(f"wimpy_{name}", WIMPY / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.np = types.SimpleNamespace(exp=lambda _x: 1)
    return module


def isotope_table() -> dict[str, tuple[int, float]]:
    """WIMpy's isotopes: name → (mass number, nuclear spin)."""
    table = {}
    for line in (WIMPY / "Nuclei.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, a, j = line.split()[:3]
            table[name] = (int(float(a)), float(j))
    return table


def coefficients(module: types.ModuleType, func: str, isotope: str, i: int, j: int) -> list[float]:
    """The polynomial coefficients a_0 … a_n of one W^{ij}, or [] if it vanishes."""
    y = sympy.Symbol("y")
    expr = sympy.expand(getattr(module, func)(i, j, y, isotope))
    if expr == 0:
        return []
    return [float(c) for c in reversed(sympy.Poly(expr, y).all_coeffs())]


def extract() -> dict:
    """Every nonzero response of every WIMpy isotope, as polynomial coefficients."""
    modules = {name: load_module(module) for name, (module, _f, _t) in RESPONSES.items()}
    isotopes = {}
    for isotope, (a, spin) in isotope_table().items():
        responses = {}
        for name, (_m, func, transposed) in RESPONSES.items():
            grid = [[coefficients(modules[name], func, isotope, *((j, i) if transposed else (i, j)))
                     for j in (0, 1)] for i in (0, 1)]
            if any(grid[i][j] for i in (0, 1) for j in (0, 1)):
                responses[name] = grid
        isotopes[isotope] = {"mass_number": a, "spin": spin, "responses": responses}
    return isotopes


def evaluate(grid: list[list[list[float]]], y: float) -> np.ndarray:
    """W^{ττ'}(y) from stored coefficients."""
    return np.array([[np.polyval(list(reversed(c)), y) * np.exp(-2 * y) if c else 0.0
                      for c in row] for row in grid])


def check_against_wimpydd(isotopes: dict) -> dict[float, tuple[float, str]]:
    """The largest relative difference from WimPyDD's table at each y, and where it occurs.

    WimPyDD's table holds the same fits rounded to six significant figures, so
    the two agree closely at small y and drift apart at large y, where the
    polynomial terms cancel. Al27 is left out: WimPyDD's table repeats the y¹
    coefficient of W_{Σ'}^{00} as its y² coefficient (0.210848 for 0.244466),
    a transcription slip in that table.
    """
    table = WIMPYDD / "Targets/Nuclear_response_functions/nuclear_response_functions_coefficients_table.dat"
    if not table.exists():
        print("WimPyDD not present: cross-check skipped")
        return {}
    rows = np.array([[float(x) for x in line.split()]
                     for line in table.read_text().splitlines() if line.strip()])
    data = rows.reshape(-1, 8, 2, 2, 11)       # file order (itar, response, τ', τ)
    worst: dict[float, tuple[float, str]] = {}
    for y in (0.0, 0.1, 0.5, 1.0, 2.0, 3.0):
        worst[y] = (0.0, "")
        for isotope, itar in WIMPYDD_ITAR.items():
            if isotope == "Al27":
                continue
            for name, k in WIMPYDD_INDEX.items():
                ours = evaluate(isotopes[isotope]["responses"].get(name, [[[], []], [[], []]]), y)
                # WimPyDD transposes every matrix on reading, which puts the
                # interference responses in the order the rate needs.
                theirs = np.array([[np.polyval(data[itar - 1, k, j, i][::-1], y) * np.exp(-2 * y)
                                    for j in (0, 1)] for i in (0, 1)])
                diff = float(np.abs(ours - theirs).max() / max(np.abs(theirs).max(), 1e-30))
                if diff > worst[y][0]:
                    worst[y] = (diff, f"{isotope} {name}")
    return worst


def main() -> None:
    """Write the data file and report the cross-check."""
    isotopes = extract()
    payload = {
        "description": "Shell-model nuclear responses W_k^{tt'}(y) = exp(-2y) sum_n a_n y^n.",
        "variable": "y = (q b / (2 hbar c))^2, b = sqrt(41.467 / (45 A^(-1/3) - 25 A^(-2/3))) fm",
        "isospin": "the responses multiply the coefficients c^p + c^n (t = 0) and c^p - c^n (t = 1)",
        "interference_order": "Phi''M and DeltaSigma' are stored as W_{Phi''M}^{tt'} and "
                              "W_{DeltaSigma'}^{tt'}, the order the rate formula uses",
        "sources": [
            "N. Anand, A. L. Fitzpatrick, W. C. Haxton, Phys. Rev. C 89 (2014) 065501, arXiv:1308.6288",
            "R. Catena, B. Schwabe, JCAP 04 (2015) 042, arXiv:1501.03729",
        ],
        "transcribed_from": "WIMpy_NREFT v1.2 (B. J. Kavanagh), commit 50581c6, MIT licence, "
                            "https://github.com/bradkav/WIMpy_NREFT",
        "licence_notice": "Copyright (c) 2017 Bradley J. Kavanagh. Permission is hereby granted, free "
                          "of charge, to any person obtaining a copy of this software and associated "
                          "documentation files, to deal in the Software without restriction (MIT "
                          "licence; full text in adroit/physics/data/LICENSE-WIMpy_NREFT).",
        "isotopes": isotopes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(isotopes)} isotopes")
    for y, (diff, where) in check_against_wimpydd(isotopes).items():
        print(f"y = {y:.1f}: largest relative difference from WimPyDD's table {diff:.1e} ({where})")


if __name__ == "__main__":
    sys.exit(main())

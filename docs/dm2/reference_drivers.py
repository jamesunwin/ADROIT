"""Compute reference spectra with WIMpy_NREFT or WimPyDD, inside their own environments.

Called by reference_spectra.py, never imported by the project:

    python reference_drivers.py wimpy   CASES.json OUT.json CODE_ROOT
    python reference_drivers.py wimpydd CASES.json OUT.json CODE_ROOT

CODE_ROOT is the folder holding the (patched or original) ``WIMpy`` package, or
the folder holding ``WimPyDD``. Each case gives an isotope, the dark matter
mass, spin and splitting, the coefficients (c^p, c^n) of each operator in
GeV⁻², and the recoil energies; the output is the rate per kg of the pure
isotope, in events/(keV kg day).
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np


def run_wimpy(cases: list[dict], root: str, halo: dict) -> list[list[float]]:
    """WIMpy_NREFT's dRdE_NREFT for each case (elastic only: it has no mass splitting)."""
    import scipy.integrate as integrate
    integrate.trapz = integrate.trapezoid                     # removed from SciPy
    integrate.cumtrapz = integrate.cumulative_trapezoid
    sys.path.insert(0, root)
    import WIMpy.DMUtils as DMU
    out = []
    for case in cases:
        cp, cn = np.zeros(20), np.zeros(20)
        for op, (p, n) in case["coefficients"].items():
            cp[int(op) - 1], cn[int(op) - 1] = p, n
        rate = DMU.dRdE_NREFT(np.array(case["energies_kev"]), case["mass_gev"], cp, cn,
                              case["isotope"], j_x=case["spin"], vlag=halo["v_lab"],
                              sigmav=halo["v0"] / np.sqrt(2.0), vesc=halo["v_esc"])
        out.append(np.asarray(rate, dtype=float).tolist())
    return out


def _wimpydd_isotope(WD, name: str):
    """(element object, isotope index) of an isotope such as 'Xe131' or 'H1'."""
    symbol = name.rstrip("0123456789")
    a = int(name[len(symbol):])
    element = WD.element(symbol)
    return element, list(element.a).index(a)


def run_wimpydd(cases: list[dict], root: str, streams: dict) -> list[list[float] | str]:
    """WimPyDD's diff_rate for each case, for one isotope, with the given velocity streams."""
    os.chdir(root)
    sys.path.insert(0, root)
    import WimPyDD as WD
    vmin, delta_eta = np.array(streams["v"]), np.array(streams["delta_eta"])
    out = []
    for case in cases:
        try:
            out.append(_wimpydd_case(WD, case, vmin, delta_eta))
        except Exception as error:  # a failure of the reference code is a result to record
            out.append(f"{type(error).__name__}: {error}")
    return out


def _constant(c0: float, c1: float):
    """A coupling function without arguments.

    WimPyDD reads a coupling function's arguments as parameters of the model,
    shared across operators, so a constant must take none.
    """
    return lambda: [c0, c1]


def _wimpydd_case(WD, case: dict, vmin: np.ndarray, delta_eta: np.ndarray) -> list[float]:
    """One case through WimPyDD's diff_rate, per kg of the pure isotope."""
    coeffs = {int(op): _constant(p + n, p - n) for op, (p, n) in case["coefficients"].items()}
    hamiltonian = WD.eft_hamiltonian("case", coeffs)
    element, index = _wimpydd_isotope(WD, case["isotope"])
    # per kg of element → per kg of the pure isotope, with the code's own Avogadro number
    per_kg = element.nt_kg_average * element.average_a / element.a[index] / element.nt_kg[index]
    rates = []
    for energy in case["energies_kev"]:
        r = WD.diff_rate(element, hamiltonian, case["mass_gev"], energy, vmin, delta_eta,
                         j_chi=case["spin"], delta=case["splitting_kev"],
                         isotopes_list={0: [index]})
        rates.append(float(np.squeeze(r)) * per_kg)
    return rates


def main() -> None:
    """Dispatch on the code named in the first argument."""
    code, cases_path, out_path, root = sys.argv[1:5]
    payload = json.loads(open(cases_path).read())
    if code == "wimpy":
        result = run_wimpy(payload["cases"], root, payload["halo"])
    else:
        result = run_wimpydd(payload["cases"], root, payload["streams"])
    with open(out_path, "w") as handle:
        json.dump(result, handle)


if __name__ == "__main__":
    main()

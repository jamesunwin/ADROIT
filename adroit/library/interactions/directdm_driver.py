"""Run DirectDM in its own environment and print its nonrelativistic coefficients as JSON.

Executed by ``quark_level`` with the Python of ``<tools>/.venv-directdm``
(DirectDM needs setuptools < 81 for ``pkg_resources``, which the project's
environment does not carry). Reads a JSON request on stdin:

    {"directdm": path, "flavours": 3 | 4 | 5, "dm_type": "D" | "M" | "C" | "R",
     "coefficients": {name: value in GeV^-n}, "mass_gev": m, "rge": bool,
     "q_gev": [optional momentum transfers]}

and prints {"components": {key: value}, "mpi": m_π, "meta": m_η, "mN": m_N}:
DirectDM's own decomposition of each coefficient into a constant part and its
q², 1/q² (photon) and pion- and eta-pole parts (``_my_cNR``), at the scale of
the nuclear matrix elements. With ``q_gev`` it also prints DirectDM's own
assembled coefficients at those momentum transfers ("cNR"), for checks.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import warnings


def _lenient_delete():
    """np.delete that ignores out-of-range indices, as NumPy < 1.19 did.

    DirectDM's four- and five-flavour constructors for Majorana dark matter delete
    index ranges that run past the end of their arrays; old NumPy dropped such
    indices with a warning, current NumPy raises. Restoring the old behaviour, here
    only, leaves every in-range deletion unchanged.
    """
    import numpy as np
    strict = np.delete

    def delete(arr, obj, axis=None):
        size = np.asarray(arr).shape[axis if axis is not None else 0] if axis is not None else np.asarray(arr).size
        if isinstance(obj, (list, tuple, np.ndarray)):
            indices = np.asarray(obj)
            if indices.dtype.kind in "iu":
                obj = indices[(indices >= -size) & (indices < size)]
        return strict(arr, obj, axis)
    np.delete = delete


def main() -> None:
    """Read the request, run DirectDM quietly, print the components."""
    request = json.load(sys.stdin)
    sys.path.insert(0, request["directdm"])
    warnings.filterwarnings("ignore")
    _lenient_delete()
    import directdm as ddm
    classes = {3: ddm.WC_3f, 4: ddm.WC_4f, 5: ddm.WC_5f}
    with contextlib.redirect_stdout(io.StringIO()):
        cls = classes[int(request["flavours"])]
        known = set(cls({}, request["dm_type"]).wc_name_list)
        unknown = sorted(set(request["coefficients"]) - known)
        if unknown:        # DirectDM itself would drop them silently
            raise SystemExit(json.dumps({"error": f"unknown Wilson coefficients {unknown} for "
                                                  f"dm_type {request['dm_type']} with "
                                                  f"{request['flavours']} flavours"}))
        wc = cls(request["coefficients"], request["dm_type"])
        three = int(request["flavours"]) == 3
        rge = {} if three else {"RGE": request.get("rge", True)}
        components = wc._my_cNR(request["mass_gev"], **rge)
        assembled = [{k: float(v) for k, v in wc.cNR(request["mass_gev"], q, **rge).items()}
                     for q in request.get("q_gev", [])]
    ip = wc.ip
    print(json.dumps({"components": {k: float(v) for k, v in components.items()},
                      "mpi": float(ip["mpi0"]), "meta": float(ip["meta"]),
                      "mN": float((ip["mproton"] + ip["mneutron"]) / 2), "cNR": assembled}))


if __name__ == "__main__":
    main()

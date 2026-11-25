"""Tabulate nuclear form factors from the Haxton–McElvain density matrices (DM5).

Runs inside the Mu2e scripts' own environment (``<tools>/.venv-mu2e``), not
ADROIT's, and imports nothing from ADROIT. It reads a JSON request on
standard input:

    {"mu2e": "<tools>/mu2e/python/mu2e.py", "elastic": "<tools>/elastic",
     "y": [...], "isotopes": [{"symbol": "Xe", "A": 129, "Z": 54, "J": 0.5,
     "interaction": "GCN5082"}, ...]}

and writes to standard output, for each isotope, the form factors
F_k(J0, T0; y) of the six multipole operators (M, Σ', Σ'', Δ, Φ'', Φ̃'),
as the Mu2e scripts compute them (their functions FM, FSigmaP, ...): the
density matrices contracted with the single-nucleon matrix elements, with
the isospin projection for the isotope's M_T = (Z − N)/2.

The Mu2e script calls ``main()`` when it is loaded, so its source is run
without that final call.
"""

from __future__ import annotations

import contextlib
import json
import pathlib
import sys
import types

OPERATORS = {"M": "FM", "SigmaP": "FSigmaP", "SigmaPP": "FSigmaPP", "Delta": "FDelta",
             "PhiPP": "FPhiPP", "PhiTP": "FPhiTP"}


def load_mu2e(path: str) -> types.ModuleType:
    """The Mu2e script as a module, without its unconditional ``main()``."""
    source = pathlib.Path(path).read_text()
    head, _, tail = source.rpartition("main()")
    if tail.strip():
        raise RuntimeError("the Mu2e script no longer ends with main(); check the driver")
    module = types.ModuleType("mu2e")
    module.__file__ = path
    exec(compile(head, path, "exec"), module.__dict__)
    return module


def form_factors(mu2e: types.ModuleType, elastic: str, iso: dict, ys: list[float]) -> dict:
    """F_k(J0, T0; y) for one isotope, keyed "k|J0|T0"."""
    a, z = iso["A"], iso["Z"]
    t = abs(a - 2 * z) / 2.0
    mu2e.elasticDir = pathlib.Path(elastic)
    mu2e.elements = {"target": {"symbol": iso["symbol"], "Z": z, "isotopes": {
        a: {"JS": iso["J"], "TTMS": [t, (2 * z - a) / 2.0], "idx": 0,
            "interactions": [iso["interaction"]]}}}}
    data = {"Element": "target", "Interaction": iso["interaction"], "Isotope": a}
    mu2e.readint(data)
    out: dict[str, list[float]] = {}
    for meset in data["isotopeme"][a]:
        j0, t0 = round(meset.J0), round(meset.T0)
        for name, function in OPERATORS.items():
            evaluate = getattr(mu2e, function)
            out[f"{name}|{j0}|{t0}"] = [float(evaluate(data, a, meset, y)) for y in ys]
    return out


def main() -> None:
    """The subprocess's entry point: reads the request (the mu2e script's path, the isotopes, the elastic setting and
    the y values) as JSON on stdin; writes each isotope's response functions, by operator and (J₀, T₀), as JSON on
    stdout."""
    request = json.loads(sys.stdin.read())
    script = pathlib.Path(request["mu2e"])
    sys.path.insert(0, str(script.parent))
    import os
    os.chdir(script.parent)          # the script reads elements.yaml from its folder
    with contextlib.redirect_stdout(sys.stderr):     # the script prints as it reads
        mu2e = load_mu2e(str(script))
        result = {f"{i['symbol']}{i['A']}": form_factors(mu2e, request["elastic"], i, request["y"])
                  for i in request["isotopes"]}
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()

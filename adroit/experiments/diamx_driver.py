"""Run DIAMX on given recoil spectra: a script for DIAMX's own environment.

Never imported by the project, whose environment lacks DIAMX and its JAX
stack; ``xenon.py`` runs it with DIAMX's interpreter:

    python diamx_driver.py REQUEST.json RESULT.json

The request names a DIAMX configuration, the experiment classes to
register, the folder of spectra (``wimp_<label>GeV.csv``: recoil energy in
keV, rate in events per tonne-year per keV), their integer labels, the
simulation batch size and a persistent work folder, where DIAMX keeps its
templates. The result gives, per label, the lower and upper limits on the
spectrum's rate multiplier, the discovery significance and the best fit.

The driver runs from a generation's private copy of DIAMX (``xenon.stage``:
the driver, the configuration and the package side by side) and imports
DIAMX from beside itself alone (``bind``), never from its installation, to
which an editable install's import finder would otherwise lead. What DIAMX
derives and keeps by its existence alone is made inside the generation
(the auditor's DW recheck, DX-05, 2026-11-12): every CSV it converts to a map is
converted afresh into the work folder, named by its bytes
(``fresh_conversions``), and the maps it makes when they are absent are
cleared from the copy before its first run (``derive_here``).
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.machinery
import io
import json
import os
import sys

DERIVED = "DERIVED.json"      # in the copy: the maps cleared before its first run, so that DIAMX makes them there


def configure(config: dict, labels: list[int], spectra_dir: str, batch_size: int) -> dict:
    """DIAMX's configuration with our spectra and simulation statistics."""
    new = copy.deepcopy(config)
    for experiment in new["experiments"]:
        for background in experiment["bkgs"]:
            if "batch_size" in background.get("args", {}):
                background["args"]["batch_size"] = batch_size
        for shaped in experiment["shaped_bkgs"]:
            shaped["args"]["batch_size"] = batch_size
        experiment["eff"]["args"]["batch_size"] = batch_size
    new["signal"]["parameter_range"] = labels
    new["signal"]["args"]["batch_size"] = batch_size
    new["signal"]["args"]["eff_batch_size"] = batch_size
    new["signal"]["args"]["signal_spectrum_path"] = os.path.join(spectra_dir, "wimp_{mass:d}GeV.csv")
    return new


def _within(path: str, root: str) -> bool:
    return os.path.realpath(path).startswith(root + os.sep)


def _elsewhere(finder, root: str) -> bool:
    """Whether an import finder would import DIAMX from outside ``root``: an editable install's finder does, whatever
    the path says. The standard path finder never is (it follows ``sys.path``, which ``bind`` leads with ``root``)."""
    if finder is importlib.machinery.PathFinder or not hasattr(finder, "find_spec"):
        return False
    try:
        spec = finder.find_spec("diamx", None)
    except Exception:          # a finder that cannot say is left; ``confined`` checks what was imported
        return False
    origin = getattr(spec, "origin", None) if spec is not None else None
    return bool(origin) and not _within(origin, root)


def confined(root: str) -> None:
    """Refuse (exit) unless every DIAMX module imported came from ``root``."""
    for name, module in list(sys.modules.items()):
        if name == "diamx" or name.startswith("diamx."):
            origin = getattr(module, "__file__", None)
            if origin and not _within(origin, root):
                raise SystemExit(f"DIAMX's module {name} was imported from {origin}, not from the generation's copy "
                                 f"{root}: nothing is calculated")


def bind(copy: str):
    """DIAMX imported from the generation's copy ``copy`` (its ``diamx/``) and never from its installation: ``copy``
    leads the import path, and every import finder that would take DIAMX from elsewhere is removed; ``confined``
    refuses a module imported from anywhere else."""
    root = os.path.realpath(copy)
    if sys.path[:1] != [root]:
        sys.path.insert(0, root)
    sys.meta_path[:] = [finder for finder in sys.meta_path if not _elsewhere(finder, root)]
    importlib.invalidate_caches()
    import diamx
    confined(root)
    return diamx


def fresh_conversions(work: str):
    """Make DIAMX convert every CSV afresh: its converter (``diamx.utils.csv_to_apt_map``) keeps the map it writes
    beside the CSV and returns it whenever it exists, so a CSV changed since had been read through its old map (DX-05).
    The replacement reads the CSV's bytes once, converts them as DIAMX does, and keeps the map in the work folder's
    ``converted``, named by the SHA-256 of those bytes and the coordinate's name: a map is only ever of the bytes that
    name it. Every DIAMX module holding the converter is given the replacement; it is returned."""
    import diamx.utils as utils
    import numpy as np
    original = utils.csv_to_apt_map
    folder = os.path.join(work, "converted")

    def csv_to_apt_map(csv_file, coordinate_name="energy"):
        if os.path.splitext(str(csv_file))[1] != ".csv":
            raise ValueError(f"File name should end with .csv: {csv_file}")
        with open(csv_file, "rb") as handle:
            data = handle.read()
        path = os.path.join(folder, hashlib.sha256(data + b"\0" + coordinate_name.encode()).hexdigest() + ".json")
        if not os.path.exists(path):
            values = np.loadtxt(io.BytesIO(data), delimiter=",")
            os.makedirs(folder, exist_ok=True)
            partial = f"{path}.{os.getpid()}.partial"
            with open(partial, "w") as handle:
                json.dump({"coordinate_system": list(values[:, 0]), "coordinate_type": "point",
                           "coordinate_name": coordinate_name, "map": list(values[:, 1])}, handle)
            os.replace(partial, path)
        return path

    utils.csv_to_apt_map = csv_to_apt_map
    for name, module in list(sys.modules.items()):
        if (name == "diamx" or name.startswith("diamx.")) and getattr(module, "csv_to_apt_map", None) is original:
            module.csv_to_apt_map = csv_to_apt_map
    return csv_to_apt_map


def derive_here(copy: str) -> list[str]:
    """Clear from the generation's copy, once, before its first run, each map DIAMX makes when it is absent: an
    experiment's cut acceptances (``default_cut_acc_file`` of each class with ``calculate_cut_acceptance``, XENONnT's),
    which DIAMX finds by name and calculates from its response inputs only if none is found (DX-05). DIAMX then makes
    them in the copy, from the generation's own inputs; the copy is the generation's alone. The names cleared are
    kept in ``DERIVED``, which marks the copy as cleared; they are returned."""
    marker = os.path.join(copy, DERIVED)
    if os.path.exists(marker):
        with open(marker) as handle:
            return json.load(handle)
    import diamx.experiments as experiments
    names = sorted({name for cls in vars(experiments).values()
                    if isinstance(cls, type) and hasattr(cls, "calculate_cut_acceptance")
                    for name in getattr(cls, "default_cut_acc_file", [])})
    for folder in ("maps", "parameters", "instructs", "model"):         # where DIAMX looks for them
        for name in names:
            path = os.path.join(copy, "diamx", "appletree", folder, name)
            if os.path.exists(path):
                os.remove(path)
    with open(marker + ".partial", "w") as handle:
        json.dump(names, handle)
    os.replace(marker + ".partial", marker)
    return names


def main() -> None:
    """Build templates, run the inference, write the limits."""
    request = json.loads(open(sys.argv[1]).read())
    copy = os.path.dirname(os.path.realpath(__file__))
    diamx = bind(copy)
    convert = fresh_conversions(request["work_dir"])
    derive_here(copy)
    root = os.path.join(os.path.dirname(diamx.__file__), "..", "config")
    config = json.loads(open(os.path.join(root, request["config"])).read())
    config = configure(config, request["labels"], request["spectra_dir"], request["batch_size"])
    context = diamx.Context(config, request["work_dir"])
    for name in request["experiments"]:
        context.register_experiment(getattr(diamx.experiments, name))
    context.generate_templates()
    output = f"ci_{request['run_name']}.csv"
    context.run_inference(confidence_level=request["confidence_level"], output_file_name=output)
    confined(copy)
    import diamx.utils as utils
    if utils.csv_to_apt_map is not convert:
        raise SystemExit("DIAMX's CSV converter was replaced during the run: nothing is published")
    rows = []
    with open(os.path.join(context.output_path, output)) as handle:
        for line in handle:
            if line.strip():
                label, lower, upper, significance, best = (float(x) for x in line.split(","))
                rows.append({"label": int(round(label)), "lower": lower, "upper": upper,
                             "significance": significance, "best_fit": best})
    with open(sys.argv[2], "w") as handle:
        json.dump(rows, handle)


if __name__ == "__main__":
    main()

"""Tabulate μ₉₀(m) of a direct-detection structure (``parameter_space.operator_limits``) through Path 1.

    uv run python scripts/tabulate_operator_limits.py anapole            # every module, two processes
    uv run python scripts/tabulate_operator_limits.py anapole --revalidate   # only the validated marks

``--revalidate`` keeps each module's recorded μ₉₀ and recomputes which are validated, with the direct route's
current rule (``exclusion.direct_validation``, release audit M8), and the envelope from them.

Each experiment module computes the unit-strength interaction's signal and its limit at each mass
(``orchestrator.exclusion._module_limits``, the direct route); the envelope at a mass is the smallest
μ₉₀ over the modules validated there. Writes adroit/parameter_space/data/operator_limits/<name>.yaml.
Slow (minutes per mass per xenon module): run once per structure.
"""

from __future__ import annotations

import math
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "adroit/parameter_space/data/operator_limits"
MASSES = np.geomspace(5.0, 1.0e4, 12).round(3).tolist()


def one_module(args: tuple[str, str]) -> dict:
    name, module_name = args
    from adroit.experiments import registry
    from adroit.orchestrator import exclusion
    from adroit.parameter_space.operator_limits import STRUCTURES
    try:
        module = registry.load_module(module_name)
    except Exception as error:                          # noqa: BLE001 - a module whose data are missing
        return {"module": module_name, "error": str(error)}
    request = exclusion.ExclusionRequest(bespoke={str(m): STRUCTURES[name](m) for m in MASSES}, masses_gev=MASSES)
    limits = exclusion._module_limits(module, request, MASSES)
    return {"module": module_name, "mu_up": limits.mu_up, "validated": limits.validated}


def _commit() -> str:
    import subprocess
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    return git("rev-parse", "--short", "HEAD") + ("+dirty" if git("status", "--porcelain", "--untracked-files=no") else "")


def envelope(rows: list[dict], masses: list[float]) -> list[float | None]:
    """The smallest validated, finite μ₉₀ at each mass (None where no module is validated)."""
    out = []
    for i in range(len(masses)):
        usable = [r["mu_up"][i] for r in rows if "mu_up" in r and r["validated"][i] and math.isfinite(r["mu_up"][i])]
        out.append(min(usable) if usable else None)
    return out


def revalidate(name: str) -> dict:
    """The table with its validated marks and envelope recomputed under the current rule; μ₉₀ unchanged."""
    from adroit.core.dm_state import DarkMatterParticle
    from adroit.experiments import registry
    from adroit.orchestrator import exclusion
    from adroit.parameter_space.operator_limits import STRUCTURES
    path = OUT / f"{name}.yaml"
    table = yaml.safe_load(path.read_text())
    masses, rows = table["masses_gev"], []
    for module_name, row in table["modules"].items():
        if "mu_up" not in row:
            rows.append({"module": module_name, **row})
            continue
        module = registry.load_module(module_name)
        conventions, why = module.conventions(), {}
        for m in masses:
            interaction = STRUCTURES[name](m)
            why[m] = exclusion.direct_validation(module, interaction, DarkMatterParticle(mass_gev=m),
                                                 exclusion._direct_model(conventions, interaction))
        rows.append({"module": module_name, "mu_up": row["mu_up"], "validated": [not why[m] for m in masses],
                     "unvalidated": sorted({w for w in why.values() if w})})
    table.update({"revalidated": date.today().isoformat(), "revalidation_commit": _commit(),
                  "revalidation": "validated marks and envelope recomputed with exclusion.direct_validation (R6, "
                                  "audit M8); μ₉₀ as computed on the date above",
                  "mu_up": envelope(rows, masses),
                  "modules": {r["module"]: {k: v for k, v in r.items() if k != "module"} for r in rows}})
    return table


if __name__ == "__main__":
    name = sys.argv[1]
    if "--revalidate" in sys.argv:
        (OUT / f"{name}.yaml").write_text(yaml.safe_dump(revalidate(name), sort_keys=False, allow_unicode=True))
        print("revalidated", OUT / f"{name}.yaml")
        raise SystemExit(0)
    from adroit.experiments import registry
    with ProcessPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(one_module, [(name, m) for m in registry.module_names()]))
    OUT.mkdir(parents=True, exist_ok=True)
    commit = _commit()
    (OUT / f"{name}.yaml").write_text(yaml.safe_dump({
        "structure": name, "computed": date.today().isoformat(), "confidence_level": 0.9,
        "generated_by": f"scripts/tabulate_operator_limits.py {name}", "code_commit": commit,
        "method": "Path 1 direct route, each module's published halo and spin-dependent nuclear model; the envelope "
                  "is the smallest μ₉₀ over the modules validated at each mass",
        "masses_gev": MASSES, "mu_up": envelope(rows, MASSES),
        "modules": {r["module"]: {k: v for k, v in r.items() if k != "module"} for r in rows}}, sort_keys=False))
    print("wrote", OUT / f"{name}.yaml")

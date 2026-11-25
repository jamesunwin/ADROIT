"""R10: tabulate the slow modules' 95% limits for the SI and SD reference structures (``parameter_space.limit_tables``).

For each module of ``limit_tables.SLOW`` (DIAMX's xenon searches, CDMSlite, PICO) and each kind it is validated
for: the limit at eight masses per decade across the validated range (one DIAMX run), then directly at every
midpoint in log m (a second run); the table keeps all of them (sixteen per decade). Its accuracy is the largest
leave-one-out error of the spline (``limit_tables``). Two midpoints are also computed alone, to check that a batch
gives each spectrum the same limit as a single run. Writes ``adroit/parameter_space/data/reference_limits/``.

    nice -n 10 uv run python scripts/tabulate_reference_limits.py [MODULE ...]      # hours; $0
    uv run python scripts/tabulate_reference_limits.py --convert                    # tables of the first format

Rerun after any change to the code a table's fingerprint covers (``limit_tables.fingerprint``): a stale table is
not used, so scans fall back to direct (slow, still correct) calculations until then.
"""

from __future__ import annotations

import math
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "adroit" / "parameter_space" / "data" / "reference_limits"
PER_DECADE = 8
KINDS = ("SI", "SD-proton", "SD-neutron")


def grid(low: float, high: float) -> list[float]:
    n = max(3, math.ceil(math.log10(high / low) * PER_DECADE) + 1)
    return np.geomspace(low, high, n).tolist()


def limits_at(module, kind: str, masses: list[float]) -> list[float]:
    from adroit.core.dm_state import CrossSectionKind
    return module.reference_limits(CrossSectionKind(kind), masses, workers=1, cl=0.95)


def record(name: str, kind: str, masses: list[float], values: list[float], fingerprint: str, batch: float,
           note: str) -> dict:
    """The stored table: every direct mass, its leave-one-out accuracy (``limit_tables.leave_one_out``)."""
    from adroit.parameter_space import limit_tables
    order = np.argsort(masses)
    masses, values = [float(masses[i]) for i in order], [float(values[i]) for i in order]
    errors = limit_tables.leave_one_out(masses, values)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"module": name, "kind": kind, "confidence_level": 0.95, "computed": str(date.today()),
            "generated_by": "scripts/tabulate_reference_limits.py", "code_commit": commit, "fingerprint": fingerprint,
            "method": "the module's reference_limits (its own procedure and conventions) at CL 0.95 at every mass; "
                      "a cubic spline in (log m, log sigma) between them; " + note,
            "masses_gev": [float(f"{m:.8g}") for m in masses], "limits_cm2": [float(f"{v:.8g}") for v in values],
            "interpolation_accuracy": float(f"{max(abs(e) for e in errors):.4g}"),
            "leave_one_out": [float(f"{e:.4g}") for e in errors], "batch_vs_single_run": float(f"{batch:.3g}")}


def tabulate(name: str, kind: str) -> dict | None:
    from adroit.experiments import registry, status
    from adroit.parameter_space import limit_tables
    span = status.validated_range(name, kind)
    if span is None:
        return None
    module = registry.load_module(name)
    before = limit_tables.fingerprint.__wrapped__(name)            # the code the numbers come from
    masses = grid(*span)
    values = limits_at(module, kind, masses)
    midpoints = [math.sqrt(a * b) for a, b in zip(masses, masses[1:])]
    direct = limits_at(module, kind, midpoints)
    alone = {m: limits_at(module, kind, [m])[0] for m in (midpoints[0], midpoints[len(midpoints) // 2])}
    batch = max(abs(alone[m] / direct[midpoints.index(m)] - 1.0) for m in alone)
    if limit_tables.fingerprint.__wrapped__(name) != before:
        raise RuntimeError(f"{name}: the code its fingerprint covers changed during the run; not written")
    return record(name, kind, masses + midpoints, values + direct, before, batch,
                  "one run for the grid and one for its midpoints")


def convert(path: Path) -> None:
    """A table of the first format (a grid, with its midpoints kept only as interpolated/direct ratios) rewritten in
    the current one: the midpoints' direct limits recovered from those ratios, every mass in the table."""
    old = yaml.safe_load(path.read_text())
    if "check_interpolated_over_direct" not in old:
        return
    masses, values = old["masses_gev"], old["limits_cm2"]
    linear = np.exp(np.interp(np.log(old["check_masses_gev"]), np.log(masses), np.log(values)))
    direct = (linear / np.array(old["check_interpolated_over_direct"])).tolist()
    new = record(old["module"], old["kind"], masses + old["check_masses_gev"], values + direct, old["fingerprint"],
                 old["batch_vs_single_run"], "the midpoints' direct limits recovered from the first format's ratios "
                 "(six significant figures)")
    new["computed"], new["code_commit"] = old["computed"], old["code_commit"]
    path.write_text(yaml.safe_dump(new, sort_keys=False, allow_unicode=True))
    print(f"converted {path.name}: {len(new['masses_gev'])} masses, accuracy {new['interpolation_accuracy']:.2%}")


def refingerprint(path: Path) -> None:
    """A table fingerprinted the first way (bytes) given the current way (syntax trees), only if its stored value
    equals the first way's for the installed code, i.e. the code it was computed from is unchanged."""
    from adroit.parameter_space import limit_tables
    data = yaml.safe_load(path.read_text())
    current = limit_tables.fingerprint.__wrapped__(data["module"])
    if data["fingerprint"] == current:
        return
    if data["fingerprint"] != limit_tables.legacy_fingerprint(data["module"]):
        print(f"{path.name}: stale (its code changed since it was computed); retabulate")
        return
    data["fingerprint"] = current
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    print(f"{path.name}: fingerprint migrated to the syntax-tree form")


def main(argv: list[str]) -> int:
    from adroit.parameter_space import limit_tables
    if argv[:1] == ["--convert"]:
        for path in sorted(OUT.glob("*.yaml")):
            convert(path)
            refingerprint(path)
        return 0
    names = argv or list(limit_tables.SLOW)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        for kind in KINDS:
            start = time.time()
            data = tabulate(name, kind)
            if data is None:
                continue
            (OUT / f"{limit_tables.slug(name, kind)}.yaml").write_text(yaml.safe_dump(data, sort_keys=False,
                                                                                     allow_unicode=True))
            print(f"{name} {kind}: {len(data['masses_gev'])} masses, accuracy {data['interpolation_accuracy']:.2%}, "
                  f"batch vs single {data['batch_vs_single_run']:.1e}, {time.time() - start:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

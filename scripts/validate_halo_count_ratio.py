"""Validate the halo count ratio (``adroit.parameter_space.halo_limits``) at its predeclared points.

    OMP_NUM_THREADS=2 nice -n 10 uv run python scripts/validate_halo_count_ratio.py [--only MODULE] [--out PATH]
    uv run python scripts/validate_halo_count_ratio.py --summarise [--out PATH]   # no new calculation

For each slow module and kind in ``data/halo_validation_points.yaml``: the module's 95% limit computed directly at
its reference halo (L_ref), the count ratio's limit at each declared halo (L_ref x rho_ref/rho0 x N_ref/N_h, at
rho0 = rho_ref so only the velocities act), and the module's full procedure there (L_full). Writes
``data/halo_count_ratio.yaml``: every point, each module and kind's largest |L_ratio/L_full - 1| (its empirical error
e), its validated masses and whether it passed the declared gate, with the declaration's sha256 and the identity of
the inputs it was computed from (``halo_limits.inputs_sha256``) on each entry: an entry is used only if all of it
still holds (``halo_limits._usable``). A non-finite or missing value fails the entry (PX-06). ``--summarise`` redoes
every entry's summary and identities from its stored points (for points computed with the same inputs). Hours for
the xenon searches (DIAMX, minutes per spectrum); results already in DIAMX's work folder are reused.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POINTS = ROOT / "adroit" / "parameter_space" / "data" / "halo_validation_points.yaml"
TARGETED = ROOT / "adroit" / "parameter_space" / "data" / "halo_validation_points_targeted.yaml"
RESULTS = {POINTS: "halo_count_ratio.yaml", TARGETED: "halo_count_ratio_targeted.yaml"}
DECLARATION = POINTS


def _halos(declared: dict) -> dict[str, tuple[float, float]]:
    """Each declared halo's (v0, v_esc) in km/s: the boundary directions scaled to the region's radius."""
    from adroit.parameter_space.halo_region import HaloPreset, radius
    preset = HaloPreset()
    r = radius(preset.level)
    out = {}
    for name, (a, b) in declared["halos"].items():
        scale = 0.0 if name == "centre" else r
        out[name] = (preset.v0_km_s + scale * a * preset.sigma_v0_km_s,
                     preset.v_esc_km_s + scale * b * preset.sigma_v_esc_km_s)
    return out


def _module(name: str, kinds: dict[str, list[float]], halos: dict[str, tuple[float, float]], gate: float) -> dict:
    """One module's validation: per kind, every point and its summary."""
    from adroit.core.dm_state import CrossSectionKind
    from adroit.experiments import registry
    from adroit.parameter_space import halo_limits
    module = registry.load_module(name)
    rho_ref = module.conventions().halo.rho_gev_cm3
    out = {}
    for kind, masses in kinds.items():
        k = CrossSectionKind(kind)
        reference = module.reference_limits(k, masses, workers=1, cl=0.95)
        points = []
        for label, (v0, ve) in halos.items():
            full = halo_limits.at_halo(module, halo_limits.velocity_halo(v0, ve, rho_ref)).reference_limits(
                k, masses, workers=1, cl=0.95)
            for mass, l_ref, l_full in zip(masses, reference, full):
                n_ref = halo_limits.accepted(name, kind, mass, None, None)
                n_h = halo_limits.accepted(name, kind, mass, v0, ve)
                ratio = l_ref * n_ref / n_h if n_h > 0 else float("inf")
                points.append({"halo": label, "v0_km_s": round(v0, 4), "v_esc_km_s": round(ve, 4), "mass_gev": mass,
                               "reference_cm2": float(l_ref), "full_cm2": float(l_full), "ratio_cm2": float(ratio),
                               "discrepancy": float(abs(ratio / l_full - 1.0))})
                print(f"{name} {kind} {mass:g} GeV {label}: full {l_full:.4g}, ratio {ratio:.4g} "
                      f"({100 * points[-1]['discrepancy']:.2f}%)", flush=True)
        out[kind] = _summary(name, masses, points, gate, DECLARATION)
    return out


def _summary(module: str, masses: list[float], points: list[dict], gate: float, declared: Path = POINTS) -> dict:
    """One module and kind's entry: its masses, e and whether it passed (``halo_limits.summarise``: a non-finite value
    fails it), the identities it holds for, and every checkpoint."""
    from adroit.parameter_space import halo_limits
    e, passed = halo_limits.summarise(points, gate)
    return {"masses_gev": [min(masses), max(masses)], "max_discrepancy": e, "passed": passed,
            "declared_sha256": hashlib.sha256(declared.read_bytes()).hexdigest(),
            "inputs_sha256": halo_limits.inputs_sha256(module), "points": points}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", default="", help="one module (default: every declared one)")
    parser.add_argument("--targeted", action="store_true", help="the targeted declaration of 2026-11-24 "
                        "(halo_validation_points_targeted.yaml), written to halo_count_ratio_targeted.yaml")
    parser.add_argument("--out", default="")
    parser.add_argument("--summarise", action="store_true", help="redo the summaries from the stored points only")
    args = parser.parse_args()
    global DECLARATION
    DECLARATION = TARGETED if args.targeted else POINTS
    declared = yaml.safe_load(DECLARATION.read_text())
    halos = _halos(declared)
    out_path = Path(args.out or ROOT / "adroit" / "parameter_space" / "data" / RESULTS[DECLARATION])
    previous = yaml.safe_load(out_path.read_text()) if out_path.is_file() else {}
    modules = dict(previous.get("modules", {}))
    for name, kinds in declared["modules"].items():
        if args.only and name != args.only:
            continue
        if args.summarise:
            modules[name] = {k: _summary(name, kinds[k], v["points"], declared["gate_max_discrepancy"], DECLARATION)
                             for k, v in modules.get(name, {}).items() if k in kinds}
        else:
            modules[name] = _module(name, kinds, halos, declared["gate_max_discrepancy"])
    modules = {k: v for k, v in modules.items() if v}
    result = {"declared": str(DECLARATION.relative_to(ROOT)),
              "declared_sha256": hashlib.sha256(DECLARATION.read_bytes()).hexdigest(),
              "date": date.today().isoformat(), "gate_max_discrepancy": declared["gate_max_discrepancy"],
              "modules": modules}
    out_path.write_text(yaml.safe_dump(result, sort_keys=False, allow_unicode=True))
    failed = [f"{m} {k}" for m, kinds in modules.items() for k, v in kinds.items() if not v["passed"]]
    print(f"written to {out_path}; " + (f"not passed: {', '.join(failed)}" if failed else "every one passed"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

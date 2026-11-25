"""The direct route's per-structure validation against LZ's 43 published model tables (R6, audit M8).

LZ's extended-window search (arXiv:2609.02823, HEPData ins3199115) publishes, for L01–L20 in isoscalar and
isovector form and for inelastic O1 and O4, the 90% upper limit on the dimensionless coupling d at each mass
(and splitting). Each is a different nuclear-response structure on xenon. This script recomputes every entry
with the fidelity-B LZ module (``experiments.lz_extended_window``: LZ's conventions, the revised xenon responses
``haxton_2022``, its halo, and the one-event likelihood) by the direct route, d_up = √κ_up at unit coupling.

**The rule (declared before the first run, R6):**
- an entry passes if (d_ours/d_LZ)² lies within [1/1.3, 1.3]: DM3's factor 1.3 on the rate scale;
- a structure (model, and splitting for O1/O4) is validated on xenon over the span of its tabulated masses from
  the first to the last of the longest run of consecutive passing masses; a single passing mass validates only
  itself.

What the result validates: our xenon rates for that structure, with ``haxton_2022`` responses, and the LZ
module's statistics. A direct-route limit of another module counts as validated for a structure only if that
module computes it on xenon with the same responses (``exclusion._validated``).

    uv run python docs/dm6/validate_direct_route.py                 # writes docs/dm6/direct_route_validation.*
    uv run python docs/dm6/validate_direct_route.py --write         # and the status file (tracked)

Exit code: 0 when it ran (the per-structure outcome is a measurement, not a gate), 2 if the record is missing.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from adroit.core.dm_state import DarkMatterParticle  # noqa: E402
from adroit.experiments import lz_extended_window as lz  # noqa: E402
from adroit.experiments.validation import TOLERANCE  # noqa: E402
from adroit.library.interactions import registry  # noqa: E402

HERE = Path(__file__).parent
STATUS = ROOT / "adroit" / "experiments" / "data" / "validated_structures.yaml"


def card_of(model: str) -> tuple[str, str]:
    """(card, isospin) of a table: LZ's own L6 and L9 definitions."""
    card = f"L{int(model[1:3]):02d}" if model[0] == "L" else f"O{int(model[1:3])}"
    return lz.LZ_CARDS.get(card, card), model[3]


def entries(tables: dict) -> list[dict]:
    """Every (model, mass, splitting) with LZ's upper limit."""
    out = []
    for name, t in tables.items():
        splittings = t.splitting_kev or [0.0] * len(t.masses_gev)
        out += [dict(model=name, mass_gev=m, splitting_kev=d, published=u)
                for m, d, u in zip(t.masses_gev, splittings, t.upper)]
    return out


def ours(e: dict, module: lz.LzExtendedWindow) -> float:
    """Our 90% upper limit on d for one entry (∞ when no events are expected)."""
    card, isospin = card_of(e["model"])
    particle = DarkMatterParticle(mass_gev=float(e["mass_gev"]), mass_splitting_kev=float(e["splitting_kev"]))
    conventions = module.conventions()
    signal = module.expected_signal(particle, registry.resolve(card, particle, lz.lz_values(card, isospin)),
                                    conventions.halo, conventions.nuclear_model)
    return math.sqrt(module.upper_limit(signal, 0.9))


def passes(ratio_d: float) -> bool:
    return math.isfinite(ratio_d) and 1 / TOLERANCE <= ratio_d ** 2 <= TOLERANCE


def structures(rows: list[dict]) -> dict[str, dict]:
    """Each structure's validated span (the rule in the module docstring)."""
    out: dict[str, dict] = {}
    keys = sorted({(r["model"], r["splitting_kev"]) for r in rows})
    for model, splitting in keys:
        group = sorted((r for r in rows if r["model"] == model and r["splitting_kev"] == splitting),
                       key=lambda r: r["mass_gev"])
        best, run = [], []
        for r in group:
            run = run + [r] if r["pass"] else []
            best = run if len(run) > len(best) else best
        card, isospin = card_of(model)
        name = model if not splitting and model[0] == "L" else f"{model}_d{splitting:g}"
        out[name] = {"card": card, "isospin": isospin, "splitting_kev": splitting,
                     "validated_gev": [best[0]["mass_gev"], best[-1]["mass_gev"]] if best else None,
                     "tested_masses": [r["mass_gev"] for r in group],
                     "ratios_d": [round(r["ratio_d"], 4) for r in group]}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="also write the tracked status file")
    args = parser.parse_args()
    try:
        tables = lz.model_tables()
    except (OSError, FileNotFoundError) as error:
        print(f"the LZ record is missing: {error}")
        return 2
    module = lz.LzExtendedWindow()
    rows = []
    for e in entries(tables):
        value = ours(e, module)
        ratio = value / e["published"] if e["published"] > 0 else math.inf
        rows.append({**e, "ours": value, "ratio_d": ratio, "pass": passes(ratio)})
    found = structures(rows)
    validated = {k: v for k, v in found.items() if v["validated_gev"]}
    lines = [f"# The direct route against LZ's {len(tables)} model tables ({len(rows)} entries)", "",
             f"Rule: (d_ours/d_LZ)² within [1/{TOLERANCE}, {TOLERANCE}]; a structure is validated over its longest "
             "run of consecutive passing masses.", "",
             f"Entries passing: {sum(r['pass'] for r in rows)} of {len(rows)}; structures with a validated span: "
             f"{len(validated)} of {len(found)}.", "", "| structure | validated (GeV) | d_ours/d_LZ at the tested masses |",
             "|---|---|---|"]
    lines += [f"| {k} | {'–'.join(f'{m:g}' for m in v['validated_gev']) if v['validated_gev'] else 'none'} | "
              + ", ".join(f"{m:g}: {r:.3g}" for m, r in zip(v["tested_masses"], v["ratios_d"])) + " |"
              for k, v in found.items()]
    (HERE / "direct_route_validation.md").write_text("\n".join(lines) + "\n")
    (HERE / "direct_route_validation.json").write_text(json.dumps(rows, indent=0, default=str) + "\n")
    if args.write:
        STATUS.write_text(yaml.safe_dump({
            "generated_by": "docs/dm6/validate_direct_route.py",
            "source": "LZ arXiv:2609.02823, HEPData ins3199115 (CC0): 90% upper limits on d per model",
            "target": "Xe", "nuclear_model": "haxton_2022", "module": lz.EXPERIMENT,
            "rule": f"(d_ours/d_LZ)^2 within [1/{TOLERANCE}, {TOLERANCE}]; longest run of consecutive passing masses",
            "structures": validated}, sort_keys=False, allow_unicode=True))
    print("\n".join(lines[:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

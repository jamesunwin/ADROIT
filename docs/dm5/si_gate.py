"""The DM5 gate, part 1: the spin-independent exclusion plot against the published picture.

The standard spin-independent interaction is the library's card O1 with
c^p = c^n. The pipeline (``orchestrator.exclusion``) runs it through every
module, and its envelope over the validated modules is compared with the
envelope of the same collaborations' published limits, each over its
module's validated range. The rule is DM3's: within a factor 1.3 at every
mass. Each module runs at its DM3 validation masses, so that the xenon
searches reuse their cached templates.

    uv run python docs/dm5/si_gate.py                # computes the limits (about half an hour)
    uv run python docs/dm5/si_gate.py --from-store   # compares again from si_exclusion.json

It writes si_exclusion.json, si_exclusion.md, si_exclusion.png and si_gate.txt
to a new runs/gates/dm5/<UTC> folder unless --out names one (docs/dm5 only to
re-record the tracked receipts); --from-store reads the tracked si_exclusion.json
unless --out holds one. Exit code: 0 when the rule passes, 1 when it does not. The rule is applied where a module was computed and is the
strongest validated one, so that no interpolated curve decides the
envelope; a dense-grid comparison, which interpolates each module between
its computed masses, is printed beside it for information.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.dm_state import CrossSectionKind  # noqa: E402
from adroit.core.receipts import add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.experiments import registry, status, validation  # noqa: E402
from adroit.library.interactions import registry as library  # noqa: E402
from adroit.orchestrator import exclusion  # noqa: E402
from adroit.physics import conventions as cv  # noqa: E402

HERE = Path(__file__).parent
TOLERANCE = 1.3
WORKERS = 2          # for CDMSlite's official procedure; the machine is shared
MODULES = ["CRESST-III 2019", "CDMSlite Run 2", "PICO-60 C3F8 (2019)", "DEAP-3600 (2019)",
           "LZ WS2022+WS2024", "XENONnT SR0+SR1", "PandaX-4T Run0+Run1"]


def every(values: list[float], step: int) -> list[float]:
    kept = values[::step]
    return kept if kept[-1] == values[-1] else [*kept, values[-1]]


def published_si() -> dict[str, tuple[list[float], list[float]]]:
    """Each module's published spin-independent curve."""
    out = {}
    for name in MODULES:
        for curve in registry.load_module(name).published_limits():
            if curve.kind is CrossSectionKind.si:
                out[name] = (curve.masses_gev, curve.cross_sections_cm2)
    return out


def masses_by_module(curves: dict[str, tuple[list[float], list[float]]]) -> dict[str, list[float]]:
    """The DM3 validation masses of each module."""
    out = {"CRESST-III 2019": curves["CRESST-III 2019"][0],
           "CDMSlite Run 2": every(curves["CDMSlite Run 2"][0], 4),
           "DEAP-3600 (2019)": every(curves["DEAP-3600 (2019)"][0], 3),
           "PICO-60 C3F8 (2019)": [3.0, 5.0, 10.0, 30.0, 100.0, 300.0, 1000.0]}
    for name in ("LZ WS2022+WS2024", "XENONnT SR0+SR1", "PandaX-4T Run0+Run1"):
        module = registry.load_module(name)
        (curve,) = module.published_limits()
        out[name] = validation.trial_masses(curve, 10).tolist()
    return out


def published_envelope(curves, grid: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """The strongest published limit at each mass, each curve over its validated SI range."""
    best, source = np.full(grid.size, np.inf), [""] * grid.size
    for name, (m, s) in curves.items():
        span = status.validated_range(name, CrossSectionKind.si)
        if span is None:
            continue
        low, high = span[0] * (1 - exclusion.RANGE_TOLERANCE), span[1] * (1 + exclusion.RANGE_TOLERANCE)
        m, s = np.array(m), np.array(s)
        for i, x in enumerate(grid):
            if low <= x <= high and m.min() <= x <= m.max():
                value = float(np.exp(np.interp(np.log(x), np.log(m), np.log(s))))
                if value < best[i]:
                    best[i], source[i] = value, name
    return best, source


def compare(ours: list[tuple[float, float, str]], curves, sigma) -> tuple[list[str], list[float]]:
    """Lines 'mass: ours/published [module | module]' and the ratios."""
    masses = np.array([m for m, _, _ in ours])
    theirs, theirs_from = published_envelope(curves, masses)
    lines, ratios = [], []
    for (m, mu, source), b, fb in zip(ours, theirs, theirs_from):
        a = sigma(mu, m)
        if np.isfinite(a) and np.isfinite(b):
            ratios.append(a / b)
            lines.append(f"{m:8.3g} GeV: {a / b:5.2f}  [{source} | {fb}]")
    return lines, ratios


def main() -> int:
    """Compute (or re-read) the SI limits, compare the envelopes, and write the record; the exit code."""
    parser = argparse.ArgumentParser(description="DM5 gate, part 1")
    parser.add_argument("--from-store", action="store_true", help="compare again from si_exclusion.json")
    add_out_argument(parser, "dm5")
    args = parser.parse_args()
    folder = gate_output("dm5", args.out)
    curves = published_si()
    values = library.isospin_values("O1", "s", 1.0 / cv.M_V_GEV ** 2)
    store = folder / "si_exclusion.json"
    if args.from_store:
        source = store if store.exists() else HERE / "si_exclusion.json"
        result = exclusion.revalidate(exclusion.ExclusionResult.model_validate_json(source.read_text()))
    else:
        request = exclusion.ExclusionRequest(card_id="O1", values=values, modules=MODULES,
                                             masses_by_module=masses_by_module(curves),
                                             workers=WORKERS)
        result = exclusion.run(request)
    store.write_text(result.model_dump_json(indent=1))
    (folder / "si_exclusion.md").write_text(exclusion.report(result))

    def sigma(mu: float, mass: float) -> float:
        return cv.sigma_si_cm2(mu * values["c_p"], mass) if np.isfinite(mu) else np.inf

    exclusion.plot(result, folder / "si_exclusion.png", to_y=sigma,
                   y_label="σ_SI per nucleon, 90% upper limit (cm²)",
                   published={f"{k} (published)": v for k, v in curves.items()})
    rule_lines, ratios = compare(result.computed_envelope(), curves, sigma)
    passed = all(1 / TOLERANCE <= r <= TOLERANCE for r in ratios)
    grid = np.geomspace(0.3, 1e4, 60)
    _, env, env_from = result.envelope(grid.tolist())
    dense = [(m, mu, f) for m, mu, f in zip(grid, env, env_from) if np.isfinite(mu)]
    dense_lines, dense_ratios = compare(dense, curves, sigma)
    lines = ["# DM5 gate, part 1: the spin-independent envelope of the validated modules against "
             "the published envelope over the same validated ranges. mass: ours/published "
             "[our module | published module]", "",
             "## The rule: at each computed mass where its module is the strongest validated one", ""]
    lines += rule_lines
    lines += ["", f"compared at {len(ratios)} masses; ratio {min(ratios):.2f}–{max(ratios):.2f}; "
              f"{'PASS' if passed else 'FAIL'} (within {TOLERANCE} at every mass)", "",
              "## For information: a dense grid, each module interpolated between its masses", ""]
    lines += dense_lines
    lines += ["", f"dense grid: {len(dense_ratios)} masses; ratio "
              f"{min(dense_ratios):.2f}–{max(dense_ratios):.2f}"]
    (folder / "si_gate.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(rule_lines))
    print(next(line for line in lines if line.startswith("compared at")))
    print(lines[-1])
    print(f"written to {folder}")
    return exit_code(passed and bool(ratios))


if __name__ == "__main__":
    sys.exit(main())

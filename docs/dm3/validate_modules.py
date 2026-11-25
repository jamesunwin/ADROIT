"""The DM3 gate: each experiment module against its collaboration's published limits.

The rule (build plan, decision 4, with the owner's refinements of 2026-09-29;
adroit/experiments/validation.py): a mass passes if the reproduced
limit lies within a factor 1.3 of the published one, or, where the
published limit is steeper than |d ln σ/d ln m| = 8, if the reproduced
curve reaches it within a 3% shift in mass. Each module is validated over
the contiguous passing range around its strongest published limit, and
counts for the gate if that range spans a decade. Every comparison is made
under the collaboration's own halo, nuclear input and target. Comparisons
under other readings are printed beside the rule's, marked as such, and do
not enter the status file.

Run from the repository root, with the modules' data fetched:

    uv run python docs/dm3/validate_modules.py                # all modules
    uv run python docs/dm3/validate_modules.py --no-xenon     # without DIAMX (slow)
    uv run python docs/dm3/validate_modules.py --only xenon   # some stages, kept with the rest

Every comparison is stored in docs/dm3/validation_results.json (the results
store); the summary docs/dm3/validation_summary.txt and the status file
adroit/experiments/data/validated_ranges.yaml (``status``) are made from
it. A partial run replaces only its own stages there. Those three tracked files
are rewritten only with --write; otherwise the run writes its store, summary and
status file to a new runs/gates/dm3/<UTC> folder (or --out).

The exit code is 1 when a comparison that counts for the gate in the tracked
status file no longer counts in this run (a regression), else 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.dm_state import CrossSectionKind, LimitCurve, ValidationResult  # noqa: E402
from adroit.core.receipts import add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.experiments import status, validation  # noqa: E402
from adroit.experiments.base import read_columns  # noqa: E402

SUMMARY = Path(__file__).with_name("validation_summary.txt")
RESULTS = Path(__file__).with_name("validation_results.json")
WORKERS = 4                       # processes for CDMSlite's official procedure
STATUS = ROOT / "adroit" / "experiments" / status.STATUS_FILE
Comparison = tuple[ValidationResult, str, bool]      # result, label, whether it is the rule's


def describe(result: ValidationResult, label: str = "") -> list[str]:
    """Lines for one comparison: the verdict, then mass:ratio pairs (e: passed by the edge clause)."""
    span = result.validated_range
    unit = result.variable.split("(")[-1].rstrip(")") if "(" in result.variable else ""
    verdict = ("every point passes" if result.passed else
               "no validated range" if span is None else
               f"validated {span[0]:.3g}-{span[1]:.3g} {unit}")
    gate = "counts for the gate" if result.counts_for_gate else "does not count for the gate"
    head = (f"{result.experiment} | {result.key}{' | ' + label if label else ''} | "
            f"{verdict} | {gate} | {len(result.masses_gev)} masses")
    edges = result.edge_passes or [False] * len(result.ratios)
    pairs = " ".join(f"{m:.3g}:{r:.2f}{'e' if e else ''}"
                     for m, r, e in zip(result.masses_gev, result.ratios, edges))
    return [head, "    " + pairs, f"    {result.note}", f"    method: {result.method}"]


def every(curve: LimitCurve, step: int) -> list[float]:
    """Every ``step``-th published mass, always keeping the first and the last."""
    masses = curve.masses_gev[::step]
    return masses if masses[-1] == curve.masses_gev[-1] else [*masses, curve.masses_gev[-1]]


def cresst() -> list[Comparison]:
    """The owner's reading (cut survival in true energy), then Eq. 1 read literally."""
    from adroit.experiments.cresst_iii import CresstIII2019
    out = []
    for reading, rule in (("true", True), ("reconstructed", False)):
        module = CresstIII2019(cut_survival=reading)
        label = "" if rule else "for comparison: cut survival in reconstructed energy"
        for curve in module.published_limits():
            out.append((validation.validate(module, curve, curve.masses_gev), label, rule))
    return out


def cdmslite() -> list[Comparison]:
    """The official median by the official procedure (the rule's target), then the best fit."""
    from adroit.experiments.cdmslite import CdmsliteRun2
    module = CdmsliteRun2()
    out = []
    for curve in module.published_limits():
        def official(masses: list[float], kind: CrossSectionKind = curve.kind) -> list[float]:
            return module.official_limits(kind, masses, workers=WORKERS)

        result = validation.validate(module, curve, every(curve, 4), limits=official)
        result = result.model_copy(update={
            "method": "median of 300 realisations: sampled efficiency and k in [0.1, 0.2], "
                      "optimum interval each"})
        out.append((result, "the official procedure vs the official median", True))
    si = next(c for c in module.published_limits() if c.kind is CrossSectionKind.si)
    table = read_columns(module.folder / "limits_SI_GeVc2_cm2.txt", columns=2)
    table = table[np.isfinite(table[:, 1])]
    best = si.model_copy(update={"masses_gev": table[:, 0].tolist(),
                                 "cross_sections_cm2": table[:, 1].tolist(),
                                 "source": "the release's best-fit limit (second column)"})
    out.append((validation.validate(module, best, every(best, 4)),
                "for comparison: k = 0.157 and the best-fit efficiency vs the release's best fit",
                False))
    return out


def pico() -> list[Comparison]:
    from adroit.experiments.pico60 import Pico60
    module = Pico60()
    (curve,) = module.published_limits()
    return [(validation.validate(module, curve, every(curve, 5)), "", True)]


def deap() -> list[Comparison]:
    from adroit.experiments.deap3600 import Deap3600
    module = Deap3600()
    (curve,) = module.published_limits()
    return [(validation.validate(module, curve, every(curve, 3)), "", True)]


def xenon() -> list[Comparison]:
    from adroit.experiments.xenon import SEARCHES, DiamxXenon
    out = []
    for search in SEARCHES:
        module = DiamxXenon(search)
        (curve,) = module.published_limits()
        out.append((validation.validate(module, curve, validation.trial_masses(curve, 10)), "", True))
    return out


def xenon_sd() -> list[Comparison]:
    """The xenon searches' SD-neutron and SD-proton limits (2026-10-10).

    XENONnT and PandaX-4T used Klos et al.'s structure factors, as the module's reference SD limits do: the
    rule's comparisons. LZ used Hoferichter, Menéndez and Schwenk's (2020), which ADROIT does not have, so its
    comparison is another reading, outside the validated ranges.
    """
    from adroit.experiments.xenon import SD_PUBLISHED, SEARCHES, DiamxXenon
    out = []
    for search in SEARCHES:
        module = DiamxXenon(search)
        for curve in module.published_limits():
            if curve.kind is CrossSectionKind.si:
                continue
            matched = SD_PUBLISHED[search]["matched"]
            label = "" if matched else "another reading: Klos et al. 2013, not LZ's Hoferichter-Menendez-Schwenk 2020"
            result = validation.validate(module, curve, validation.trial_masses(curve, 10),
                                         limits=lambda values, k=curve.kind, m=module: m.reference_limits(k, values))
            out.append((result, label, matched))
    return out


def stored() -> list[dict]:
    """The results store's comparisons ([] before the first run)."""
    return json.loads(RESULTS.read_text())["comparisons"] if RESULTS.is_file() else []


def store(stage: str, comparisons: list[Comparison], old: list[dict]) -> list[dict]:
    """The store with ``stage``'s comparisons replaced by these."""
    kept = [c for c in old if c["stage"] != stage]
    return kept + [{"stage": stage, "date": str(date.today()), "label": label, "rule": rule,
                    "result": result.model_dump(mode="json")}
                   for result, label, rule in comparisons]


LZ_GATE = ("L10s", "O01s@1000GeV")     # the curves of LZ's Fig. 6: the DM5 gate


def _lz_points(module, tab, card: str, isospin: str) -> list[tuple[float, float, float, float]]:
    """(d_up, d_lo, significance, mass) at each tabulated point of one LZ model."""
    from adroit.core.dm_state import DarkMatterParticle
    from adroit.experiments.lz_extended_window import lz_values
    from adroit.library.interactions import registry
    conventions = module.conventions()
    splittings = tab.splitting_kev or [0.0] * len(tab.masses_gev)
    out = []
    for mass, delta in zip(tab.masses_gev, splittings):
        particle = DarkMatterParticle(mass_gev=mass, mass_splitting_kev=delta)
        signal = module.expected_signal(particle, registry.resolve(card, particle,
                                                                   lz_values(card, isospin)),
                                        conventions.halo, conventions.nuclear_model)
        low, high = module.interval(signal)
        out.append((high ** 0.5, low ** 0.5, module.significance(signal), mass))
    return out


def lz_ew() -> list[Comparison]:
    """LZ's extended window (DM5): the gate's two curves, then every model for information."""
    from adroit.experiments.lz_extended_window import LzExtendedWindow, model_tables
    module = LzExtendedWindow()
    out = []
    for name, tab in model_tables().items():
        card = f"L{int(name[1:3]):02d}" if name[0] == "L" else f"O{int(name[1:3])}"
        points = _lz_points(module, tab, card, name[3])
        groups = ({f"{name}": list(range(len(points)))} if name[0] == "L" else
                  {f"{name}@{m:g}GeV": [i for i, mm in enumerate(tab.masses_gev) if mm == m]
                   for m in sorted(set(tab.masses_gev))})
        for label, idx in groups.items():
            idx = sorted(idx, key=lambda i: (tab.splitting_kev or tab.masses_gev)[i])
            scan = [(tab.splitting_kev or tab.masses_gev)[i] for i in idx]
            lows = " ".join(f"{points[i][1]:.3g}/{tab.lower[i]:.3g}" for i in idx)
            sigs = " ".join(f"{points[i][2]:.2f}/{tab.local_significance[i]:.1f}" for i in idx)
            result = ValidationResult(
                experiment=module.name, model=label, masses_gev=scan,
                published_cm2=[tab.upper[i] for i in idx],
                reproduced_cm2=[points[i][0] for i in idx],
                quantity="dimensionless coupling d = c m_v², 90% upper limit",
                variable="splitting (keV)" if name[0] == "O" else "mass (GeV)",
                method=module.info.statistical_method,
                note=f"published: {tab.source}. Lower limits ours/LZ: {lows}. "
                     f"Local significance ours/LZ: {sigs}")
            out.append((result, "" if label in LZ_GATE else "for information", label in LZ_GATE))
    return out


STAGES = {"cresst": cresst, "cdmslite": cdmslite, "pico": pico, "deap": deap, "xenon": xenon, "xenon_sd": xenon_sd,
          "lz_ew": lz_ew}


def status_modules(comparisons: list[dict]) -> dict[str, dict]:
    """The status file's modules, from the rule's comparisons in the store."""
    modules: dict[str, dict] = {}
    for item in comparisons:
        if item["rule"]:
            result = ValidationResult.model_validate(item["result"])
            modules.setdefault(result.experiment, {})[result.key] = {
                **status.entry(result), "run": item["date"]}
    return modules


def regressions(modules: dict[str, dict], tracked: dict[str, dict]) -> list[str]:
    """Comparisons that count for the gate in the tracked status file but not in ``modules``."""
    return [f"{experiment} | {key}" for experiment, keys in tracked.items() for key, entry in keys.items()
            if entry.get("counts_for_gate") and not modules.get(experiment, {}).get(key, {}).get("counts_for_gate")]


def write_status(comparisons: list[dict], path: Path = STATUS) -> None:
    """The status file, from the rule's comparisons in the store."""
    modules = status_modules(comparisons)
    path.write_text(yaml.safe_dump({
        "generated": "by docs/dm3/validate_modules.py from docs/dm3/validation_results.json",
        "rule": f"ratio within [1/{validation.TOLERANCE}, {validation.TOLERANCE}], or a shift "
                f"of at most {validation.EDGE_SHIFT:.0%} in mass where the published slope "
                f"exceeds {validation.EDGE_SLOPE:g}; validated range: a contiguous run of "
                "passing masses, the one holding the strongest published limit if it passes, "
                "else the widest; the gate needs a decade that holds the strongest limit",
        "modules": modules}, sort_keys=False, allow_unicode=True, width=100))


def write_summary(comparisons: list[dict], path: Path = SUMMARY) -> None:
    """The readable summary, from the store, in the order of the stages."""
    lines = ["# DM3 validation: reproduced / published 90% limit, mass (GeV):ratio, "
             "'e' = passed by the edge clause. From docs/dm3/validation_results.json.",
             f"# Rule: ratio within [1/{validation.TOLERANCE}, {validation.TOLERANCE}], or a "
             f"{validation.EDGE_SHIFT:.0%} mass shift where |slope| > {validation.EDGE_SLOPE:g}; "
             "validated range and gate as in adroit/experiments/validation.py."]
    for stage in STAGES:
        for item in (c for c in comparisons if c["stage"] == stage):
            result = ValidationResult.model_validate(item["result"])
            lines += describe(result, item["label"]) + [f"    run: {item['date']}"]
    path.write_text("\n".join(lines) + "\n")


def chosen_stages(only: str, no_xenon: bool) -> list[str]:
    """The stages to run: all, all but xenon, or those named by --only."""
    if only:
        names = only.split(",")
        unknown = set(names) - set(STAGES)
        if unknown:
            raise SystemExit(f"unknown stages {sorted(unknown)}; known: {', '.join(STAGES)}")
        return names
    return [s for s in STAGES if not (s in ("xenon", "xenon_sd") and no_xenon)]


def main() -> int:
    """Run the chosen stages, store their comparisons, and write the store, summary and status file;
    returns the exit code."""
    parser = argparse.ArgumentParser(description="DM3: each experiment module against its published limits")
    parser.add_argument("--only", default="", help="stages, comma-separated")
    parser.add_argument("--no-xenon", action="store_true", help="without DIAMX (slow)")
    parser.add_argument("--write", action="store_true", help="rewrite the three tracked files")
    add_out_argument(parser, "dm3")
    args = parser.parse_args()
    if args.write and args.out:
        raise SystemExit("--write rewrites the tracked files; --out names another folder: give one")
    folder = None if args.write else gate_output("dm3", args.out)
    results_path, summary_path, status_path = ((RESULTS, SUMMARY, STATUS) if folder is None else
                                               (folder / RESULTS.name, folder / SUMMARY.name, folder / STATUS.name))
    tracked = yaml.safe_load(STATUS.read_text()).get("modules", {}) if STATUS.is_file() else {}
    comparisons = stored()
    for stage in chosen_stages(args.only, args.no_xenon):
        results = STAGES[stage]()
        for result, label, _rule in results:
            print("\n".join(describe(result, label)), flush=True)
        comparisons = store(stage, results, comparisons)
        results_path.write_text(json.dumps({"comparisons": comparisons}, indent=1) + "\n")
    write_summary(comparisons, summary_path)
    write_status(comparisons, status_path)
    lost = regressions(status_modules(comparisons), tracked)
    print(f"wrote {results_path}, {summary_path}, {status_path}")
    print("no comparison lost its place in the gate" if not lost else
          "REGRESSION: no longer counts for the gate: " + "; ".join(lost))
    return exit_code(not lost)


if __name__ == "__main__":
    sys.exit(main())

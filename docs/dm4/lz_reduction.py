"""The DM4 gate: LZ's reduction of its 616 models to 293 (arXiv:2609.02823, supplement).

LZ's model space: L1–L20 in isoscalar and isovector form at 13 masses
(10–4000 GeV), and the inelastic O1 and O4, isoscalar and isovector, at 400,
1000 and 4000 GeV with splittings 0–350 keV in steps of 50: 616 models. LZ
states three degeneracies:
1. L1/L5, L2/L8, L3/L17, L4/L20 and L11/L14 differ only by a constant;
2. isoscalar and isovector spectra are indistinguishable for L2, L4, L7, L8,
   L10, L11, L14, L15, L19, L20 and the inelastic O4;
3. masses of 400 GeV and above are nearly degenerate (1000 GeV kept),
and says they reduce the 616 models to 293.

This script builds the 616 models from the library's cards, computes their
spectra on xenon weighted by LZ's signal efficiency (digitised Fig. S2), and
measures every pair's distinguishability N₂σ = 4/J (``degeneracy``). It
reports, for each of LZ's statements, whether the numbers bear it out, and
counts the models under LZ's stated rules and under the numerical classes.

    uv run python docs/dm4/lz_reduction.py                  # the published responses
    uv run python docs/dm4/lz_reduction.py haxton_2022      # LZ's revised responses (DM5)

It writes docs/dm4/lz_reduction[_<model>].txt and .json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.dm_state import DarkMatterParticle, NuclearModel  # noqa: E402
from adroit.experiments import digitised  # noqa: E402
from adroit.library.interactions import degeneracy, registry  # noqa: E402
from adroit.physics import targets  # noqa: E402
from adroit.physics.conventions import M_V_GEV  # noqa: E402

MODEL = NuclearModel(sys.argv[1]) if len(sys.argv) > 1 else NuclearModel.shell_model
SUFFIX = "" if MODEL is NuclearModel.shell_model else f"_{MODEL.value}"
OUT = Path(__file__).with_name(f"lz_reduction{SUFFIX}.txt")
STORE = Path(__file__).with_name(f"lz_reduction{SUFFIX}.json")
LAGRANGIAN_MASSES = [10, 12, 14, 17, 21, 30, 40, 50, 100, 200, 400, 1000, 4000]   # HEPData ins3199115
INELASTIC_MASSES = [400, 1000, 4000]
SPLITTINGS = [0, 50, 100, 150, 200, 250, 300, 350]
PAIRS = [(1, 5), (2, 8), (3, 17), (4, 20), (11, 14)]
ISOSPIN_DEGENERATE = {2, 4, 7, 8, 10, 11, 14, 15, 19, 20}
ENERGIES = np.arange(1.5, 350.0, 0.5)
THRESHOLDS = [30, 100, 300, 1000, 3000, 10000]


def model_space() -> list[degeneracy.ModelPoint]:
    """LZ's 616 models, from the library's cards, at unit coupling 1/m_v²."""
    unit = 1.0 / M_V_GEV ** 2
    points = []
    for j in range(1, 21):
        for iso in "sv":
            values = registry.isospin_values(f"L{j:02d}", iso, unit)
            for mass in LAGRANGIAN_MASSES:
                particle = DarkMatterParticle(mass_gev=float(mass))
                points.append(degeneracy.ModelPoint(
                    label=f"L{j:02d}{iso}@{mass}", particle=particle,
                    interaction=registry.resolve(f"L{j:02d}", particle, values)))
    for op in (1, 4):
        for iso in "sv":
            values = registry.isospin_values(f"O{op}", iso, unit)
            for mass in INELASTIC_MASSES:
                for delta in SPLITTINGS:
                    particle = DarkMatterParticle(mass_gev=float(mass),
                                                  mass_splitting_kev=float(delta))
                    points.append(degeneracy.ModelPoint(
                        label=f"O{op:02d}{iso}@{mass},d={delta}", particle=particle,
                        interaction=registry.resolve(f"O{op}", particle, values)))
    return points


def shapes(points: list[degeneracy.ModelPoint]) -> tuple[list[str], np.ndarray, list[str]]:
    """The labels and shapes of the models with events in the window, and those without."""
    figure = digitised.load("lz_2026_figS2")
    efficiency = np.interp(ENERGIES, figure["energy_kev"], figure["efficiency"], left=0.0,
                           right=0.0)
    xenon = targets.target("Xe")
    labels, rows, empty = [], [], []
    for point in points:
        s = degeneracy.shape(point, xenon, ENERGIES, efficiency, model=MODEL)
        if s is None:
            empty.append(point.label)
        else:
            labels.append(point.label)
            rows.append(s)
    return labels, np.array(rows), empty


def n2(j: np.ndarray, index: dict[str, int], a: str, b: str) -> float:
    """N₂σ between two labelled models (inf if identical)."""
    return float(degeneracy.events_to_separate(j[index[a], index[b]]))


def stated_rule_count(empty: list[str]) -> dict[str, int]:
    """The number of models left by LZ's three stated rules, applied literally."""
    reps = [j for j in range(1, 21) if j not in {b for _, b in PAIRS}]
    lagrangian = sum(1 if j in ISOSPIN_DEGENERATE else 2 for j in reps)
    kept_masses = [m for m in LAGRANGIAN_MASSES if m < 400] + [1000]
    inelastic_all = 3 * len(INELASTIC_MASSES) * len(SPLITTINGS)          # O1s, O1v, O4
    unphysical = len({e.split("@")[1] for e in empty if e.startswith("O")})
    return {"lagrangian_spectra_per_mass": lagrangian, "lagrangian_masses_kept": len(kept_masses),
            "inelastic": inelastic_all, "total": lagrangian * len(kept_masses) + inelastic_all,
            "total_without_unphysical": lagrangian * len(kept_masses) + inelastic_all
            - 3 * unphysical}


def report(labels: list[str], j: np.ndarray, empty: list[str]) -> tuple[list[str], dict]:
    """The report's lines and the stored numbers."""
    index = {label: i for i, label in enumerate(labels)}
    lines = ["# DM4 gate: LZ's reduction of 616 models to 293. N = events to separate at 2σ "
             f"(4/J), on xenon with LZ's efficiency; nuclear responses: {MODEL.value}.", ""]
    lines.append(f"models: {len(labels) + len(empty)}; with no events in the window: "
                 f"{len(empty)} ({', '.join(empty)})")
    # 1. the pairs
    pairs = {}
    for a, b in PAIRS:
        exact = all(degeneracy.proportional(
            registry.resolve(f"L{a:02d}", DarkMatterParticle(mass_gev=float(m)),
                             registry.isospin_values(f"L{a:02d}", iso, 1.0)),
            registry.resolve(f"L{b:02d}", DarkMatterParticle(mass_gev=float(m)),
                             registry.isospin_values(f"L{b:02d}", iso, 1.0)))
            for iso in "sv" for m in LAGRANGIAN_MASSES)
        pairs[f"L{a}/L{b}"] = exact
    lines += ["", "1. Pairs differing by a constant (coefficients proportional at every mass):",
              "   " + ", ".join(f"{k}: {'yes' if v else 'NO'}" for k, v in pairs.items())]
    others = [(a, b) for a in range(1, 21) for b in range(a + 1, 21)
              if (a, b) not in PAIRS and degeneracy.proportional(
                  registry.resolve(f"L{a:02d}", DarkMatterParticle(mass_gev=100.0),
                                   registry.isospin_values(f"L{a:02d}", "s", 1.0)),
                  registry.resolve(f"L{b:02d}", DarkMatterParticle(mass_gev=100.0),
                                   registry.isospin_values(f"L{b:02d}", "s", 1.0)))]
    lines.append(f"   other proportional pairs: {others or 'none'}")
    # 2. isospin
    iso = {}
    for jj in range(1, 21):
        values = [n2(j, index, f"L{jj:02d}s@{m}", f"L{jj:02d}v@{m}") for m in LAGRANGIAN_MASSES
                  if m >= 30]
        iso[f"L{jj}"] = min(values)
    o4 = min(n2(j, index, f"O04s@{m},d={d}", f"O04v@{m},d={d}") for m in INELASTIC_MASSES
             for d in SPLITTINGS if f"O04s@{m},d={d}" in index)
    o1 = min(n2(j, index, f"O01s@{m},d={d}", f"O01v@{m},d={d}") for m in INELASTIC_MASSES
             for d in SPLITTINGS if f"O01s@{m},d={d}" in index)
    lines += ["", "2. Isoscalar against isovector: the smallest N over masses from 30 GeV "
              "(LZ's degenerate list marked *):"]
    for name, value in sorted(iso.items(), key=lambda kv: -kv[1]):
        star = "*" if int(name[1:]) in ISOSPIN_DEGENERATE else " "
        lines.append(f"   {star} {name:4s} N = {value:.3g}")
    lines.append(f"   * O4 (inelastic) N = {o4:.3g};   O1 (inelastic) N = {o1:.3g}")
    # 3. heavy masses
    heavy, step = [], []
    for jj in range(1, 21):
        for isospin in "sv":
            name = f"L{jj:02d}{isospin}"
            heavy.append(min(n2(j, index, f"{name}@400", f"{name}@1000"),
                             n2(j, index, f"{name}@1000", f"{name}@4000")))
            step.append(n2(j, index, f"{name}@200", f"{name}@400"))
    lines += ["", "3. Masses: N between 400 and 1000, and 1000 and 4000 GeV (the smaller), and "
              "between 200 and 400 GeV, over the 40 Lagrangian models:",
              f"   400–4000 GeV: min {min(heavy):.3g}, median {np.median(heavy):.3g}",
              f"   200–400 GeV:  min {min(step):.3g}, median {np.median(step):.3g}, "
              f"max {max(step):.3g}"]
    # the elastic limit of the inelastic models
    duplicates = {f"O{op}{iso}@{m}": n2(j, index, f"O{op:02d}{iso}@{m},d=0", f"L{lag:02d}{iso}@{m}")
                  for op, lag in ((1, 1), (4, 15)) for iso in "sv" for m in INELASTIC_MASSES}
    lines += ["", "4. Not stated by LZ: the inelastic models at δ = 0 are elastic O1 and O4, the "
              "nonrelativistic limits of L1 and L15 (L15 → −4 O4). N between O1(δ=0) and L1, and "
              "O4(δ=0) and L15, at the same mass and isospin:",
              "   " + ", ".join(f"{k}: {v:.3g}" for k, v in duplicates.items())]
    # counts
    stated = stated_rule_count(empty)
    lines += ["", "Counts:",
              f"   LZ's stated rules, applied literally: {stated['lagrangian_spectra_per_mass']} "
              f"Lagrangian spectra × {stated['lagrangian_masses_kept']} masses + "
              f"{stated['inelastic']} inelastic = {stated['total']} "
              f"({stated['total_without_unphysical']} without the unphysical points); LZ: 293"]
    counts = {n: len(degeneracy.classes(labels, j, n)) for n in THRESHOLDS}
    lines.append("   numerical classes at N events (single linkage, all "
                 f"{len(labels)} physical models): "
                 + ", ".join(f"N={n}: {c}" for n, c in counts.items()))
    store = {"pairs_exact": pairs, "other_proportional_pairs": others,
             "isospin_min_N": iso, "O4_isospin_min_N": o4, "O1_isospin_min_N": o1,
             "heavy_mass_min_N": min(heavy), "step_200_400_N": step,
             "delta0_duplicates_N": duplicates, "stated_rule_count": stated, "classes_by_threshold": counts, "empty": empty}
    return lines, store


def main() -> None:
    points = model_space()
    labels, rows, empty = shapes(points)
    j = degeneracy.jeffreys_matrix(rows, ENERGIES)
    lines, store = report(labels, j, empty)
    OUT.write_text("\n".join(lines) + "\n")
    STORE.write_text(json.dumps(store, indent=1, default=float) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

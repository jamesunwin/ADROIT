"""Injection and recovery, as a function of the number of events (DM10).

DM6's test (``docs/dm6/injection.py``) at 20 events on LZ's window, made general:
- **Targets.** Xenon (LZ's extended window and its 612 models, as in DM6),
  CaWO₄ (CRESST-III, 1–20 GeV), germanium (CDMSlite, 3–15 GeV) and argon
  (DEAP-3600, 50–3000 GeV). The other targets use the operators O1 and O3–O15
  in both isospins: their shapes are what discrimination rests on.
- **Injection.** N events drawn from one candidate's efficiency-weighted
  spectrum, plus Poisson background from a flat density: the module's own b*
  for LZ, one expected event over the window elsewhere.
- **Recovery.** Every candidate is fitted (``signal_fit.best_fits``). A case
  succeeds when the best is the injected candidate, or one that N events cannot
  tell from it at 2σ (N₂σ = 4/J > N between their shapes, DM4's measure): DM6's
  pre-declared, pairwise reading. Reported beside it: the reading the owner
  accepted for DM6 (the best is in the injected candidate's single-linkage class
  at N events), and exact recovery. A high success rate where candidates are
  mutually indistinguishable (argon's spin-independent family) means degeneracy,
  not discrimination; the exact rate tells the two apart.
- **The baseline of exhaustive fitting** (no agents, no classes) names the
  single best fit: its success is the exact rate. The system names the set the
  events cannot separate (the tournament's ΔAIC ≤ 2, with one parameter each:
  Δ ln L ≤ 1): its coverage and mean size are reported beside it.

The case's random state comes from its id, so every case is reproducible.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache

import numpy as np

from adroit.core.dm_state import DarkMatterParticle
from adroit.evaluation.core import Case, CaseResult, Suite
from adroit.experiments import lz_extended_window as lz
from adroit.experiments import registry as modules
from adroit.inference import dm_tournament, signal_fit
from adroit.library.interactions import degeneracy, registry

EVENTS = [3, 5, 10, 20, 50]
PER_POINT = 40
OPERATORS = [f"O{i}" for i in range(1, 16) if i != 2]
TARGETS = {
    "Xe (LZ extended window)": ("LZ extended window (2026)", None),
    "CaWO4 (CRESST-III)": ("CRESST-III 2019", [1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0]),
    "Ge (CDMSlite)": ("CDMSlite Run 2", [3.0, 5.0, 7.0, 10.0, 15.0]),
    "Ar (DEAP-3600)": ("DEAP-3600 (2019)", [50.0, 100.0, 200.0, 500.0, 1000.0, 3000.0]),
}


def _lz_models() -> list[tuple[str, str, str, float, float]]:
    masses = [10, 12, 14, 17, 21, 30, 40, 50, 100, 200, 400, 1000, 4000]
    inelastic = [(m, d) for m in (400, 1000, 4000) for d in range(0, 351, 50) if (m, d) != (400, 350)]
    cards = {"L06": "L06_LZ", "L09": "L09_LZ"}      # DM10's gated card set, frozen (see lz_tables.LZ_CARDS)
    out = []
    for j in range(1, 21):
        card = cards.get(f"L{j:02d}", f"L{j:02d}")
        out += [(f"L{j:02d}{iso}@{m}", card, iso, float(m), 0.0) for iso in "sv" for m in masses]
    for op in (1, 4):
        out += [(f"O{op:02d}{iso}@{m},d={d}", f"O{op}", iso, float(m), float(d))
                for iso in "sv" for m, d in inelastic]
    return out


def models(target: str) -> list[tuple[str, str, str, float, float]]:
    """The target's candidates: (label, card, isospin, mass in GeV, splitting in keV)."""
    masses = TARGETS[target][1]
    if masses is None:
        return _lz_models()
    return [(f"{op}{iso}@{m:g}", op, iso, m, 0.0) for op in OPERATORS for iso in "sv" for m in masses]


@lru_cache(maxsize=None)
def classes(target: str, n: int) -> dict[str, int]:
    """Single-linkage classes of the target's candidates at n events (DM4's measure)."""
    labels, _, _, _, n2 = table(target)
    with np.errstate(divide="ignore"):
        groups = degeneracy.classes(labels, 4.0 / n2, n)          # J = 4/N₂σ
    return {label: i for i, members in enumerate(groups) for label in members}


@lru_cache(maxsize=None)
def table(target: str) -> tuple[list[str], np.ndarray, np.ndarray, float, np.ndarray]:
    """(labels, energies, normalised shapes, background density, N₂σ matrix) for one target."""
    name, masses = TARGETS[target]
    module = modules.load_module(name)
    conventions = module.conventions()
    models_ = models(target)
    values = lz.lz_values if masses is None else lambda card, iso: registry.isospin_values(card, iso, 1.0)
    energies, rows = None, []
    for _, card, iso, mass, delta in models_:
        particle = DarkMatterParticle(mass_gev=mass, mass_splitting_kev=delta)
        s = module.expected_signal(particle, registry.resolve(card, particle, values(card, iso)),
                                   conventions.halo, conventions.nuclear_model)
        energies = np.asarray(s.observable, dtype=float) if energies is None else energies
        density = np.interp(energies, s.observable, s.density) if len(s.observable) else energies * 0.0
        rows.append(density / s.total_events if s.total_events > 0 else density * 0.0)
    shapes = np.array(rows)
    width = energies[-1] - energies[0]
    background = lz.background_density() if masses is None else 1.0 / width
    live = shapes.sum(axis=1) > 0
    j = degeneracy.jeffreys_matrix(np.where(live[:, None], shapes, 1.0 / width), energies)
    return [m[0] for m in models_], energies, shapes, background, degeneracy.events_to_separate(j)


def _draw(shape: np.ndarray, energies: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (shape[1:] + shape[:-1]) * np.diff(energies))])
    return np.interp(rng.uniform(0.0, cdf[-1], n), cdf, energies)


def cases() -> list[Case]:
    """For each target and number of events, PER_POINT injections of a candidate drawn by the case's own seed."""
    return [Case(suite="injection", id=f"{t}|N={n}|{i}", inputs={"target": t, "events": n, "index": i})
            for t in TARGETS for n in EVENTS for i in range(PER_POINT)]


def draw(case: Case) -> tuple[int, np.ndarray]:
    """(the injected candidate's index, the event energies): signal plus background, from the case's seed."""
    labels, energies, shapes, b_star, _ = table(case.inputs["target"])
    seed = int.from_bytes(hashlib.sha256(case.id.encode()).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    k = int(rng.choice(np.nonzero(shapes.sum(axis=1) > 0)[0]))
    background = rng.poisson(b_star * (energies[-1] - energies[0]))
    events = np.concatenate([_draw(shapes[k], energies, case.inputs["events"], rng),
                             rng.uniform(energies[0], energies[-1], background)])
    return k, events


def run_case(case: Case) -> CaseResult:
    """Fit every candidate to the case's events; the case passes when the best is the injected candidate or one that
    N events cannot tell from it at 2σ (N₂σ > N)."""
    target, n = case.inputs["target"], case.inputs["events"]
    labels, energies, shapes, b_star, n2 = table(target)
    k, events = draw(case)
    f = np.array([np.interp(events, energies, row, left=0.0, right=0.0) for row in shapes])
    _, gain = signal_fit.best_fits(f, np.full(events.size, b_star))
    gain = np.where(shapes.sum(axis=1) > 0, gain, -np.inf)
    top = int(np.argmax(gain))
    top_set = np.nonzero(gain >= gain[top] - 0.5 * dm_tournament.INDISTINGUISHABLE_DAIC)[0]
    success = top == k or n2[top, k] > n
    same_class = classes(target, n)[labels[top]] == classes(target, n)[labels[k]]
    return CaseResult(case_id=case.id, passed=bool(success),
                      metrics={"injected": labels[k], "top": labels[top], "exact": top == k,
                               "same_class": same_class, "in_top_set": bool(k in top_set),
                               "top_set_size": int(top_set.size),
                               "z_top": float(np.sqrt(2 * max(gain[top], 0.0)))},
                      note="" if success else f"injected {labels[k]}, top {labels[top]} (N₂σ {n2[top, k]:.3g})")


def _rate(rows: list[CaseResult], key: str) -> float:
    return sum(bool(r.metrics[key] if key != "passed" else r.passed) for r in rows) / max(len(rows), 1)


def summarise(results: list[CaseResult], cases_: list[Case]) -> dict[str, float | str]:
    """For each target and number of events: the three readings, the ΔAIC ≤ 2 set, the cases."""
    by = {c.id: c for c in cases_}
    out: dict[str, float | str] = {}
    for t in TARGETS:
        for n in EVENTS:
            rows = [r for r in results if by[r.case_id].inputs["target"] == t and by[r.case_id].inputs["events"] == n]
            if rows:
                size = float(np.mean([r.metrics["top_set_size"] for r in rows]))
                out[f"{t}, N = {n} (pairwise; class; exact; ΔAIC set: coverage, mean size; cases)"] = (
                    f"{_rate(rows, 'passed'):.2f}; {_rate(rows, 'same_class'):.2f}; {_rate(rows, 'exact'):.2f}; "
                    f"{_rate(rows, 'in_top_set'):.2f}, {size:.1f}; {len(rows)}")
    for key, name in [("passed", "pairwise"), ("same_class", "class"), ("exact", "exact"), ("in_top_set", "ΔAIC set")]:
        out[f"all, {name}"] = round(_rate(results, key), 3)
    return out


SUITE = Suite(name="injection", description="injection and recovery against the number of events, four targets",
              cases=cases, run_case=run_case, summarise=summarise)

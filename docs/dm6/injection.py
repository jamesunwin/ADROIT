"""The DM6 gate, part 2: injected signals are recovered by the ranking (≥ 80% at 20 events).

Fixed before the first run (2026-09-30):
- **Candidates.** LZ's 612 physical models (L1–L20, isoscalar and isovector,
  at 13 masses; inelastic O1 and O4 at 400, 1000 and 4000 GeV and δ = 0–350
  keV), with LZ's conventions and its own L6 and L9.
- **Search.** LZ's extended window: its efficiency and exposure, and the
  module's background density b* (flat), in true recoil energy. This is the
  same basis as the degeneracy measure of DM4.
- **Injection.** 500 injections, each of a model drawn uniformly from the
  candidates (seed 20260930): exactly 20 signal events drawn from its
  spectrum, plus Poisson background events.
- **Ranking.** Every candidate is fitted (``inference.signal_fit``) and the
  candidates are ranked by Δ ln L.
- **Success.** The top candidate is the injected model, or one that cannot be
  told from it at 2σ with 20 events: N₂σ = 4/J > 20 between their shapes.
  This pairwise reading of "its degeneracy class" avoids the chains of single
  linkage.
- **Required:** success in at least 80% of injections.

    uv run python docs/dm6/injection.py

It writes injection.txt and injection.json in docs/dm6/.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.dm_state import DarkMatterParticle  # noqa: E402
from adroit.experiments import lz_extended_window as lz  # noqa: E402
from adroit.inference import signal_fit  # noqa: E402
from adroit.library.interactions import degeneracy, registry  # noqa: E402

HERE = Path(__file__).parent
EVENTS = 20
INJECTIONS = 500
SEED = 20260930
REQUIRED = 0.80
MASSES = [10, 12, 14, 17, 21, 30, 40, 50, 100, 200, 400, 1000, 4000]
INELASTIC = [(m, d) for m in (400, 1000, 4000) for d in range(0, 351, 50) if (m, d) != (400, 350)]
LZ_CARDS = lz.LZ_CARDS                 # the interactions as LZ computes them (one source)


def candidates() -> list[tuple[str, str, str, float, float]]:
    """(label, card, isospin, mass, splitting) for LZ's physical models."""
    out = []
    for j in range(1, 21):
        card = LZ_CARDS.get(f"L{j:02d}", f"L{j:02d}")
        out += [(f"L{j:02d}{iso}@{m}", card, iso, float(m), 0.0) for iso in "sv" for m in MASSES]
    for op in (1, 4):
        out += [(f"O{op:02d}{iso}@{m},d={d}", f"O{op}", iso, float(m), float(d))
                for iso in "sv" for m, d in INELASTIC]
    return out


def shapes(models) -> tuple[np.ndarray, np.ndarray]:
    """The normalised, efficiency-weighted spectra of the candidates on the module's grid."""
    module = lz.LzExtendedWindow()
    conventions = module.conventions()
    rows = []
    for _, card, iso, mass, delta in models:
        particle = DarkMatterParticle(mass_gev=mass, mass_splitting_kev=delta)
        signal = module.expected_signal(particle, registry.resolve(card, particle, lz.lz_values(card, iso)),
                                        conventions.halo, conventions.nuclear_model)
        density = np.asarray(signal.density)
        rows.append(density / signal.total_events if signal.total_events > 0 else density * 0.0)
    return lz.ENERGIES_KEV, np.array(rows)


def draw(shape: np.ndarray, energies: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """n energies drawn from a normalised density on the grid (inverse transform)."""
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (shape[1:] + shape[:-1]) * np.diff(energies))])
    return np.interp(rng.uniform(0.0, cdf[-1], n), cdf, energies)


def main() -> None:
    models = candidates()
    energies, table = shapes(models)
    live = table.sum(axis=1) > 0
    j = degeneracy.jeffreys_matrix(np.where(live[:, None], table, 1.0 / (energies[-1] - energies[0])), energies)
    indistinguishable = degeneracy.events_to_separate(j) > EVENTS
    b_star = lz.background_density()
    window = (energies[0], energies[-1])
    rng = np.random.default_rng(SEED)
    chosen = rng.choice(np.nonzero(live)[0], size=INJECTIONS)
    classes = degeneracy.classes([m[0] for m in models], np.where(indistinguishable, 0.0, np.inf), 1.0)
    class_of = {label: n for n, members in enumerate(classes) for label in members}
    weights = np.gradient(energies)
    logs = np.log(np.maximum(table, degeneracy.FLOOR * table.max(axis=1, keepdims=True)))
    results = []
    for k in chosen:
        n_background = rng.poisson(b_star * (window[1] - window[0]))
        events = np.concatenate([draw(table[k], energies, EVENTS, rng),
                                 rng.uniform(*window, n_background)])
        f = np.array([np.interp(events, energies, row, left=0.0, right=0.0) for row in table])
        _, gain = signal_fit.best_fits(f, np.full(events.size, b_star))
        top = int(np.argmax(np.where(live, gain, -np.inf)))
        kl = float((table[k] * (logs[k] - logs[top]) * weights).sum())   # KL(injected ‖ top)
        results.append({"injected": models[k][0], "top": models[top][0], "exact": bool(top == k),
                        "success": bool(top == k or indistinguishable[top, k]),
                        "z_top": float(np.sqrt(2 * gain[top])),
                        # for information: other readings of "its class is ranked first"
                        "in_top_set": bool(2 * (gain[top] - gain[k]) <= 2.3),
                        "top_set_size": int(np.sum(2 * (gain[top] - gain[live]) <= 2.3)),
                        "same_linkage_class": bool(class_of[models[top][0]] == class_of[models[k][0]]),
                        "one_sided_n2": float(4.0 / (2.0 * kl)) if kl > 0 else float("inf")})
    rate = sum(r["success"] for r in results) / len(results)
    exact = sum(r["exact"] for r in results) / len(results)
    misses = Counter(r["injected"].split("@")[0] for r in results if not r["success"])
    lines = [f"# DM6 gate, part 2: {INJECTIONS} injections of {EVENTS} events into LZ's extended "
             f"window, ranked over {int(live.sum())} candidates.", "",
             f"success (top = injected or indistinguishable at {EVENTS} events): {rate:.1%}: "
             f"{'PASS' if rate >= REQUIRED else 'FAIL'} (≥ {REQUIRED:.0%} required)",
             f"exactly the injected model on top: {exact:.1%}",
             f"median local significance of the top candidate: "
             f"{np.median([r['z_top'] for r in results]):.1f}σ",
             f"misses by injected family: {dict(sorted(misses.items()))}", "",
             "For information, other readings of the gate (not the pre-declared one):",
             f"   injected model within the top set (2Δln L ≤ 2.3 of the best): "
             f"{np.mean([r['in_top_set'] for r in results]):.1%}; median top-set size "
             f"{np.median([r['top_set_size'] for r in results]):.0f}",
             f"   top candidate in the injected model's single-linkage class at {EVENTS} events: "
             f"{np.mean([r['same_linkage_class'] for r in results]):.1%} "
             f"({len(classes)} classes over {len(models)} models)",
             f"   one-sided: top indistinguishable given data from the injected model "
             f"(4/(2 KL) > {EVENTS}): "
             f"{np.mean([r['exact'] or r['one_sided_n2'] > EVENTS for r in results]):.1%}"]
    (HERE / "injection.txt").write_text("\n".join(lines) + "\n")
    (HERE / "injection.json").write_text(json.dumps(results, indent=0) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

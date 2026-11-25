"""The DM6 gate, part 1: LZ's 612 local significances (Tables S7 and S8) within 0.3σ for ≥ 90%.

Every entry is recomputed with the fidelity-B LZ module
(``experiments.lz_extended_window``): LZ's conventions (m_M = m_N, the
revised xenon responses), the library's cards, and the one-event
likelihood. L6 and L9 use LZ's own documented definitions
(arXiv:2404.17666, cards L06_LZ and L09_LZ). The same count with Table 1's
L6 and L9 is reported beside it.

    uv run python docs/dm6/lz_significances.py

It writes lz_significances.txt and lz_significances.json in docs/dm6/.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from importlib import resources
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.dm_state import DarkMatterParticle  # noqa: E402
from adroit.experiments import lz_extended_window as lz  # noqa: E402
from adroit.library.interactions import registry  # noqa: E402

HERE = Path(__file__).parent
TOLERANCE = 0.3
REQUIRED = 0.90
LZ_CARDS = lz.LZ_CARDS                 # the interactions as LZ computes them (one source)


def published() -> list[dict]:
    """The transcribed Tables S7 and S8."""
    text = resources.files("adroit.experiments").joinpath("data/lz_2026_tables_S7_S8.yaml").read_text()
    return yaml.safe_load(text)["entries"]


def card_of(model: str, lz_definitions: bool) -> str:
    card = f"L{int(model[1:3]):02d}" if model[0] == "L" else f"O{int(model[1:3])}"
    return LZ_CARDS.get(card, card) if lz_definitions else card


def significances(entries: list[dict], lz_definitions: bool) -> list[float]:
    module = lz.LzExtendedWindow()
    conventions = module.conventions()
    out = []
    for e in entries:
        card = card_of(e["model"], lz_definitions)
        particle = DarkMatterParticle(mass_gev=float(e["mass_gev"]),
                                      mass_splitting_kev=float(e["splitting_kev"]))
        values = lz.lz_values(card, e["model"][3])
        signal = module.expected_signal(particle, registry.resolve(card, particle, values),
                                        conventions.halo, conventions.nuclear_model)
        out.append(module.significance(signal))
    return out


def summary(entries: list[dict], ours: list[float]) -> tuple[float, Counter]:
    passed = [abs(z - e["significance"]) <= TOLERANCE for e, z in zip(entries, ours)]
    return sum(passed) / len(passed), Counter(e["model"] for e, ok in zip(entries, passed) if not ok)


def main() -> None:
    entries = published()
    ours = significances(entries, lz_definitions=True)
    table1 = significances(entries, lz_definitions=False)
    fraction, failures = summary(entries, ours)
    fraction_t1, failures_t1 = summary(entries, table1)
    lines = [f"# DM6 gate, part 1: {len(entries)} local significances of arXiv:2609.02823 "
             f"(Tables S7, S8), ours against LZ's; rule: |Δ| ≤ {TOLERANCE}σ for ≥ "
             f"{REQUIRED:.0%} of entries.", "",
             f"With LZ's own L6 and L9 (the rule's comparison): {fraction:.1%} within "
             f"{TOLERANCE}σ: {'PASS' if fraction >= REQUIRED else 'FAIL'}",
             f"   failures by model: {dict(sorted(failures.items()))}",
             f"With Table 1's L6 and L9 (for information): {fraction_t1:.1%}",
             f"   failures by model: {dict(sorted(failures_t1.items()))}", "",
             "Entries outside the tolerance (model, mass GeV, splitting keV: LZ, ours):"]
    lines += [f"   {e['model']} {e['mass_gev']} {e['splitting_kev']}: {e['significance']}, {z:.2f}"
              for e, z in zip(entries, ours) if abs(z - e["significance"]) > TOLERANCE]
    (HERE / "lz_significances.txt").write_text("\n".join(lines) + "\n")
    (HERE / "lz_significances.json").write_text(json.dumps(
        [{**e, "ours": round(z, 4), "ours_table1": round(t, 4)}
         for e, z, t in zip(entries, ours, table1)], indent=0) + "\n")
    print("\n".join(lines[:7]))


if __name__ == "__main__":
    main()

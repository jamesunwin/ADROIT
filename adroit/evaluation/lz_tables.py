"""LZ's tables (DM10): the 612 local significances of arXiv:2609.02823's Tables S7 and S8.

Each entry is recomputed with the fidelity-B LZ module, LZ's conventions and its own
L6 and L9 (DM6's gate, ``docs/dm6/lz_significances.py``). A case passes when the
significance is within 0.3σ of LZ's, DM6's tolerance.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml

from adroit.core.dm_state import DarkMatterParticle
from adroit.evaluation.core import Case, CaseResult, Suite
from adroit.experiments import lz_extended_window as lz
from adroit.library.interactions import registry

TOLERANCE = 0.3
# DM10's gated instrument keeps the cards of its gate (2026-10-02): its held-out half has been run and is not
# rerun. Comparisons with LZ use ``lz_extended_window.LZ_CARDS``, which adds L5, L7, L8, L13 and L17.
LZ_CARDS = {"L06": "L06_LZ", "L09": "L09_LZ"}


@lru_cache(maxsize=1)
def _module():
    return lz.LzExtendedWindow()


def entries() -> list[dict]:
    """The 612 entries of LZ's Tables S7 and S8 (``data/lz_2026_tables_S7_S8.yaml``)."""
    text = resources.files("adroit.experiments").joinpath("data/lz_2026_tables_S7_S8.yaml").read_text()
    return yaml.safe_load(text)["entries"]


def cases() -> list[Case]:
    """One case per table entry: the model, the mass and the splitting."""
    return [Case(suite="lz_tables", id=f"{e['model']}@{e['mass_gev']},d={e['splitting_kev']}", inputs=e)
            for e in entries()]


def run_case(case: Case) -> CaseResult:
    """The entry's local significance recomputed with the LZ module and the entry's card; the case passes within 0.3σ
    of LZ's."""
    e = case.inputs
    card = f"L{int(e['model'][1:3]):02d}" if e["model"][0] == "L" else f"O{int(e['model'][1:3])}"
    card = LZ_CARDS.get(card, card)
    particle = DarkMatterParticle(mass_gev=float(e["mass_gev"]), mass_splitting_kev=float(e["splitting_kev"]))
    module = _module()
    conventions = module.conventions()
    signal = module.expected_signal(particle, registry.resolve(card, particle, lz.lz_values(card, e["model"][3])),
                                    conventions.halo, conventions.nuclear_model)
    ours = module.significance(signal)
    delta = ours - e["significance"]
    return CaseResult(case_id=case.id, passed=abs(delta) <= TOLERANCE,
                      metrics={"lz": e["significance"], "ours": round(ours, 4), "delta": round(delta, 4)},
                      note=f"LZ {e['significance']}, ours {ours:.2f}")


def summarise(results: list[CaseResult], cases_: list[Case]) -> dict[str, float | str]:
    """The fraction within 0.3σ, the number of entries, and the median |Δ| in σ."""
    deltas = sorted(abs(float(r.metrics["delta"])) for r in results)
    return {"within 0.3σ": round(sum(bool(r.passed) for r in results) / max(len(results), 1), 3),
            "entries": len(results),
            "median |Δ| (σ)": round(deltas[len(deltas) // 2], 3) if deltas else float("nan")}


SUITE = Suite(name="lz_tables", description="LZ's 612 local significances (Tables S7, S8) within 0.3σ",
              cases=cases, run_case=run_case, summarise=summarise)

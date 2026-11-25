"""Which conventions LZ's L1–L20 limits follow: the analysis behind docs/notes/lz_model_cards.html.

LZ's extended-window search (arXiv:2609.02823) publishes 90% limits on a dimensionless coupling d for the twenty
covariant interactions L_j of Anand, Fitzpatrick & Haxton (arXiv:1308.6288, Table 1). Seven of them disagree with
ADROIT's recomputation (``validate_direct_route.py``) by factors from 3 to 10⁴. This script separates convention
from experiment, in three steps:

1. **Pair test.** LZ notes five pairs whose recoil spectra are identical up to a constant (L1/L5, L2/L8, L3/L17,
   L4/L20, L11/L14). For such a pair the ratio of (d_ours/d_LZ) between partners cancels everything on the
   experiment side (efficiency, halo, statistics) and measures LZ's relative normalisation directly.
2. **Gordon identity.** LZ's earlier paper (arXiv:2404.17666, Table I) writes L6 and L9 with vector currents where
   Table 1 has P^μ/m_M or K^μ/m_M, and sets m_M = m_N. Writing L5, L7, L8, L13 and L17 the same way,
   χ̄γ^μχ ≈ (P^μ/2m_χ) χ̄χ and N̄γ_μN ≈ (K_μ/2m_N) N̄N, predicts each card's factor. Those forms are now the
   cards ``*_LZ`` (``lz.LZ_CARDS``); this compares them with the previous comparison cards (``PREVIOUS``).
3. **Sign and cancellation tests** for L6 (the relative sign of its O1 and O3 terms) and L12 (its O12:O15 ratio).
4. **Significances.** LZ's local significances depend on the spectral shape, which the LZ forms change for L6,
   L7 and L13: an independent check, on the development half of DM10's split only.

    uv run python docs/dm6/lz_conventions.py          # writes docs/dm6/lz_conventions.json and prints a summary

Needs the LZ record (``experiments.lz_extended_window``). Runs in about a minute.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.dm_state import DarkMatterParticle  # noqa: E402
from adroit.experiments import lz_extended_window as lz  # noqa: E402
from adroit.experiments.validation import TOLERANCE  # noqa: E402
from adroit.library.interactions import registry  # noqa: E402

HERE = Path(__file__).parent
UNIT = 1 / 246.2**2                       # LZ's unit coupling, 1/m_v²
M_N = lz.OPERATOR_MASS_GEV                # the operators' nucleon mass, also LZ's m_M
PAIRS = {"L05/L01": "m_N/(4 m_χ)", "L08/L02": "m_N/(2 m_χ)", "L17/L03": "1/2", "L20/L04": "1", "L14/L11": "1"}
FACTOR = {"m_N/(4 m_χ)": lambda m: M_N / (4 * m), "m_N/(2 m_χ)": lambda m: M_N / (2 * m),
          "1/2": lambda m: 0.5, "1": lambda m: 1.0}

# The cards LZ's limits follow (lz.LZ_CARDS, built from this analysis), and what each one is.
FORMS = {
    "L05": "χ̄γ^μχ N̄γ_μN (card L05_LZ)",
    "L07": "χ̄γ^μχ N̄γ_μγ⁵N (card L07_LZ)",
    "L08": "i χ̄γ^μχ (K_μ/m_M) N̄γ⁵N (card L08_LZ)",
    "L13": "χ̄γ^μγ⁵χ N̄γ_μN (card L13_LZ)",
    "L17": "i (P^μ/m_M) χ̄γ⁵χ N̄γ_μN (card L17_LZ)",
    "L06": "χ̄γ^μχ N̄ iσ_μα (q^α/m_M) N with its O3 term reversed (card L06_LZ)",
}
# The comparison cards before the LZ forms: Anand et al.'s, with LZ's own L6 (as LZ's table prints it) and L9.
PREVIOUS = {"L06": "L06_LZ", "L09": "L09_LZ"}


class Calculator:
    """d_up for an interaction at a mass, with the fidelity-B LZ module and LZ's conventions."""

    def __init__(self) -> None:
        self.module = lz.LzExtendedWindow()
        self.conventions = self.module.conventions()
        self.tables = lz.model_tables()

    def limit(self, model, mass: float) -> float:
        particle = DarkMatterParticle(mass_gev=mass)
        signal = self.module.expected_signal(particle, model, self.conventions.halo, self.conventions.nuclear_model)
        return math.sqrt(self.module.upper_limit(signal, 0.9))

    def card(self, card: str, isospin: str, mass: float):
        """The interaction as LZ computes it (``lz.LZ_CARDS``)."""
        base = lz.LZ_CARDS.get(card, card)
        return registry.resolve(base, DarkMatterParticle(mass_gev=mass), lz.lz_values(base, isospin))

    def previous(self, card: str, isospin: str, mass: float):
        """The comparison card ADROIT used before the LZ forms (``PREVIOUS``; L6's O3 sign as LZ's table prints)."""
        base = PREVIOUS.get(card, card)
        model = registry.resolve(base, DarkMatterParticle(mass_gev=mass), lz.lz_values(base, isospin))
        if card != "L06":
            return model
        return model.model_copy(update={"coefficients": [
            c.model_copy(update={"proton": -c.proton, "neutron": -c.neutron}) if c.operator == 3 else c
            for c in model.coefficients]})

    def custom(self, card: str, isospin: str, mass: float, terms: list[tuple[int, float, int]]):
        """The card's model with its coefficients replaced: c_i = (c/d)·d, isovector with the neutron reversed."""
        model = self.card(card, isospin, mass)
        kind = type(model.coefficients[0])
        sign = 1.0 if isospin == "s" else -1.0
        return model.model_copy(update={"coefficients": [
            kind(operator=o, proton=f * UNIT, neutron=sign * f * UNIT, q_power=p, q_scale_gev=1.0)
            for o, f, p in terms]})


def comparison(calc: Calculator) -> dict[str, list[dict]]:
    """For every table and mass: LZ's limit, and ours with the previous card and with LZ's form (the new card)."""
    out = {}
    for j in range(1, 21):
        card = f"L{j:02d}"
        for isospin in "sv":
            table = calc.tables[f"{card}{isospin}"]
            rows = []
            for mass, published in zip(table.masses_gev, table.upper):
                before = calc.limit(calc.previous(card, isospin, mass), mass) / published
                after = calc.limit(calc.card(card, isospin, mass), mass) / published
                rows.append({"mass_gev": mass, "published_d": published, "ratio_card": before,
                             "ratio_lz_form": after})
            out[f"{card}{isospin}"] = rows
    return out


def significance_check(calc: Calculator) -> dict[str, dict]:
    """LZ's local significances (Table S7) for the cards whose spectral shape the LZ forms change (L6, L7, L13)
    and those they rescale (L5, L8, L17), with the previous and the new cards: entries within 0.3σ of LZ's. Only
    the development half of DM10's split is used; its held-out half is not run."""
    from adroit.evaluation import lz_tables
    from adroit.evaluation.core import Half, half_of
    out: dict[str, dict] = {}
    for case in lz_tables.cases():
        e = case.inputs
        card = e["model"][:3]
        if card not in FORMS or half_of("lz_tables", case.id) is not Half.development:
            continue
        mass, isospin = float(e["mass_gev"]), e["model"][3]
        particle = DarkMatterParticle(mass_gev=mass)
        row = out.setdefault(card, {"entries": 0, "before": 0, "after": 0, "worst_before": 0.0, "worst_after": 0.0})
        row["entries"] += 1
        for key, model in (("before", calc.previous(card, isospin, mass)), ("after", calc.card(card, isospin, mass))):
            signal = calc.module.expected_signal(particle, model, calc.conventions.halo, calc.conventions.nuclear_model)
            delta = abs(calc.module.significance(signal) - e["significance"])
            row[key] += delta <= lz_tables.TOLERANCE
            row[f"worst_{key}"] = max(row[f"worst_{key}"], round(delta, 3))
    return out


def pair_test(rows: dict[str, list[dict]]) -> dict[str, dict]:
    """Each pair's measured relative normalisation, divided by the factor the vector forms predict."""
    out = {}
    for pair, factor in PAIRS.items():
        a, b = pair.split("/")
        values = []
        for isospin in "sv":
            partner = {r["mass_gev"]: r["ratio_card"] for r in rows[f"{b}{isospin}"]}
            values += [r["ratio_card"] / partner[r["mass_gev"]] / FACTOR[factor](r["mass_gev"])
                       for r in rows[f"{a}{isospin}"] if r["mass_gev"] in partner]
        mean = sum(values) / len(values)
        spread = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
        out[pair] = {"predicted_factor": factor, "n": len(values), "mean": mean, "sd": spread,
                     "min": min(values), "max": max(values)}
    return out


def l12_detuning(calc: Calculator, offsets=(0.0, 0.01, -0.01, 0.03, 0.05, -0.05, 0.1)) -> dict[str, list[float]]:
    """L12's ratio to LZ when its O12:O15 ratio departs by ε from the value a vector identity fixes."""
    out = {}
    for eps in offsets:
        values = []
        for isospin in "sv":
            table = calc.tables[f"L12{isospin}"]
            published = dict(zip(table.masses_gev, table.upper))
            for mass in (14.0, 100.0, 1000.0):
                terms = [(10, 1 / (mass * M_N), 2), (12, 4 * (1 + eps) / M_N**2, 2), (15, 4.0, 0)]
                values.append(calc.limit(calc.custom("L12", isospin, mass, terms), mass) / published[mass])
        out[f"{eps:+.2f}"] = values
    return out


ALTERNATIVES = {
    "L07 O7 only": ("L07", lambda m: [(7, -2.0, 0)]),
    "L13 O8 only": ("L13", lambda m: [(8, 2.0, 0)]),
    "L06 O4 and O6 reversed": ("L06", lambda m: [(1, 0.5 / M_N, 2), (3, -2.0, 0), (4, -2.0 / m, 2),
                                                 (6, 2.0 * M_N**2 / m, 0)]),
}


def alternatives(calc: Calculator, masses=(10.0, 14.0, 30.0, 100.0, 1000.0)) -> dict[str, dict[str, list[float]]]:
    """Forms that separate the hypotheses: L7 without its O9 term, L13 without its O9 term, and L6 with the
    sign of its O4/O6 pair reversed instead of its O1/O3 pair."""
    out = {}
    for name, (card, terms) in ALTERNATIVES.items():
        out[name] = {}
        for isospin in "sv":
            table = calc.tables[f"{card}{isospin}"]
            published = dict(zip(table.masses_gev, table.upper))
            out[name][isospin] = [calc.limit(calc.custom(card, isospin, m, terms(m)), m) / published[m]
                                  for m in masses]
    return out


def passes(ratio: float) -> bool:
    return 1 / TOLERANCE <= ratio**2 <= TOLERANCE


def main() -> int:
    calc = Calculator()
    rows = comparison(calc)
    result = {"masses_for_l12": [14.0, 100.0, 1000.0], "rows": rows, "pairs": pair_test(rows),
              "l12_detuning": l12_detuning(calc), "alternatives": alternatives(calc),
              "alternative_masses": [10.0, 14.0, 30.0, 100.0, 1000.0],
              "forms": FORMS, "significances_development_half": significance_check(calc)}
    (HERE / "lz_conventions.json").write_text(json.dumps(result, indent=1) + "\n")
    for card, s in result["significances_development_half"].items():
        print(f"{card} significances within 0.3σ of LZ (DM10 development half): {s['before']} → {s['after']} of "
              f"{s['entries']}; worst |Δ| {s['worst_before']} → {s['worst_after']}σ")
    for pair, p in result["pairs"].items():
        print(f"{pair}: measured/predicted ({p['predicted_factor']}) = {p['mean']:.3f} ± {p['sd']:.3f} (n = {p['n']})")
    for key, values in rows.items():
        before, after = sum(passes(r["ratio_card"]) for r in values), sum(passes(r["ratio_lz_form"]) for r in values)
        print(f"{key}: passing {before} → {after} of {len(values)}; after "
              f"{min(r['ratio_lz_form'] for r in values):.3g}–{max(r['ratio_lz_form'] for r in values):.3g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

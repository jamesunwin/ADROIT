"""L12: which discrete convention reproduces LZ's published limits (the owner, 2026-10-12).

L12 = i χ̄ iσ^μν (q_ν/m_M) χ (K_μ/m_M) N̄γ⁵N reduces to O₁₀ + O₁₂ + O₁₅, with coefficients (per unit d)

  c₁₀ = q²/(m_χ m_N),  c₁₂ = 4 q²/m_N²,  c₁₅ = 4        (``lz_conventions.l12_detuning``, ε = 0),

and xenon's O₁₂ and O₁₅ responses nearly cancel at exactly c₁₂/c₁₅ = q²/m_N². ADROIT's limits are then
weaker than LZ's (1.75–16× in d), while a 5–6% detuning of that ratio comes close. A tuned ε is a fit, not a convention, so this
script tries only discrete, physically distinct conventions and accepts one only if it reproduces **every**
published mass for **both** isospins within the validation tolerance (a factor 1.3 in rate):

- **A, the nucleon mass in O₁₅ against the one in the reduction:** ADROIT uses the atomic mass unit for both
  (``lz.OPERATOR_MASS_GEV``); a code whose O₁₅ uses m_p, m_n or their mean while the reduction uses m_M rescales
  c₁₅ by (m'/m_N)², and so detunes the cancellation by 1.5–1.7%;
- **B, the O₁₀ coefficient:** at the bottom of the cancellation O₁₀ can carry the rate. Variants: ×0, ×½, ×2,
  and m_M in place of m_χ;
- **C, interference:** the O₁₂–O₁₅ interference left out (their rates added);
- **D, a sign:** O₁₅ reversed (no cancellation).

For scale only, it also fits the one continuous detuning ε (c₁₂ → (1 + ε) c₁₂) that ``lz_conventions`` found; a
tuned ε is a calibration to LZ, not a convention, and is not adopted.

    uv run python docs/dm6/lz_l12_conventions.py       # writes docs/dm6/lz_l12_conventions.json; $0, minutes
"""

from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from lz_conventions import M_N, Calculator, passes  # noqa: E402

from adroit.core.dm_state import DarkMatterParticle  # noqa: E402

OUT = Path(__file__).with_name("lz_l12_conventions.json")
NUCLEON_MASSES = {"m_N = amu (ADROIT)": M_N, "m_p": 0.93827208816, "m_n": 0.93956542052,
                  "(m_p + m_n)/2": 0.93891875434}
O10 = {"c10 as Anand et al.": lambda m: 1 / (m * M_N), "c10 = 0": lambda m: 0.0,
       "c10 × ½": lambda m: 0.5 / (m * M_N), "c10 × 2": lambda m: 2 / (m * M_N),
       "c10 with m_M for m_χ": lambda m: 1 / M_N ** 2}
INTERFERENCE = ("with O12–O15 interference", "O12–O15 interference left out")
SIGNS = ("O15 as Anand et al.", "O15 reversed")


def terms(mass: float, o15_mass: float, o10, sign: float) -> list[tuple[int, float, int]]:
    """(operator, coefficient per unit d, power of q) for one variant."""
    return [(10, o10(mass), 2), (12, 4 / M_N ** 2, 2), (15, sign * 4.0 * (M_N / o15_mass) ** 2, 0)]


def limit(calc: Calculator, isospin: str, mass: float, parts: list[tuple[int, float, int]],
          interference: bool) -> float:
    """d_up for the variant: one model, or (without the O12–O15 interference) the sum of two models' spectra."""
    particle = DarkMatterParticle(mass_gev=mass)
    groups = [parts] if interference else [[t for t in parts if t[0] != 15], [t for t in parts if t[0] == 15]]
    signals = [calc.module.expected_signal(particle, calc.custom("L12", isospin, mass, g), calc.conventions.halo,
                                           calc.conventions.nuclear_model) for g in groups]
    total = signals[0]
    for s in signals[1:]:
        total = total.model_copy(update={"total_events": total.total_events + s.total_events,
                                         "density": [a + b for a, b in zip(total.density, s.density)]})
    return math.sqrt(calc.module.upper_limit(total, 0.9))


def ratios_of(calc: Calculator, parts_at, interference: bool = True) -> dict[str, float]:
    """d_ours/d_LZ at every published mass, both isospins, for a variant given as ``parts_at(mass)``."""
    out = {}
    for isospin in "sv":
        table = calc.tables[f"L12{isospin}"]
        for mass, published in zip(table.masses_gev, table.upper):
            out[f"{isospin}@{mass:g}"] = limit(calc, isospin, mass, parts_at(mass), interference) / published
    return out


def tuned(calc: Calculator, offsets=(-0.06, -0.05, -0.04, 0.04, 0.05, 0.06)) -> list[dict]:
    """For scale: the continuous detuning ε of c₁₂ (the card's m_N throughout) — a fit, not a convention."""
    rows = []
    for eps in offsets:
        r = ratios_of(calc, lambda m: [(10, 1 / (m * M_N), 2), (12, 4 * (1 + eps) / M_N ** 2, 2), (15, 4.0, 0)])
        rows.append({"epsilon": eps, "matched": sum(passes(x) for x in r.values()), "of": len(r),
                     "worst ratio": max(r.values(), key=lambda x: abs(math.log(x))), "ratios": r})
        print(f"tuned ε = {eps:+.2f}: {rows[-1]['matched']}/{len(r)}, worst {rows[-1]['worst ratio']:.3f}", flush=True)
    return rows


def main() -> int:
    calc = Calculator()
    results = []
    for (mname, mvalue), (oname, o10), interference, sign in itertools.product(
            NUCLEON_MASSES.items(), O10.items(), INTERFERENCE, SIGNS):
        ratios = ratios_of(calc, lambda m: terms(m, mvalue, o10, -1.0 if sign == SIGNS[1] else 1.0),
                           interference == INTERFERENCE[0])
        matched = sum(passes(r) for r in ratios.values())
        worst = max(ratios.values(), key=lambda r: abs(math.log(r)))
        results.append({"nucleon mass in O15": mname, "O10": oname, "interference": interference, "O15 sign": sign,
                        "matched": matched, "of": len(ratios), "worst ratio": worst, "ratios": ratios})
        print(f"{matched:2d}/{len(ratios)}  worst {worst:7.3f}  {mname}; {oname}; {interference}; {sign}", flush=True)
    results.sort(key=lambda r: (-r["matched"], abs(math.log(r["worst ratio"]))))
    OUT.write_text(json.dumps({"tolerance": "a factor 1.3 in rate (d ratio within 0.877–1.140)",
                               "variants": results, "tuned_for_scale_only": tuned(calc)}, indent=1,
                              ensure_ascii=False))
    best = results[0]
    print(f"best: {best['matched']}/{best['of']} ({best['nucleon mass in O15']}; {best['O10']}; "
          f"{best['interference']}; {best['O15 sign']}), worst ratio {best['worst ratio']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

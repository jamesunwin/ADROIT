"""2HDM+a single production (gg -> a, gg -> A, gg -> H) at 13 TeV, LO, derived from the spin-0 tables.

LHC DM WG 2HDM+a benchmark (arXiv:1810.09420): type-II Yukawas, tan(beta) = 1, sin(theta) = 0.35,
alignment cos(beta - alpha) = 0.  In units of the SM-like Yukawa m_q/v:
    a :  g_t = sin(theta) cot(beta),  g_b = sin(theta) tan(beta)   (CP-odd, same sign)
    A :  g_t = cos(theta) cot(beta),  g_b = cos(theta) tan(beta)   (CP-odd, same sign)
    H :  g_t = -cot(beta),            g_b = +tan(beta)             (CP-even, OPPOSITE sign)
(Djouadi, Phys. Rept. 459 (2008) 1, Table 1, with beta - alpha = pi/2).  With the per-quark
tables s_t, s_b, s_tb (unit couplings) the LO cross section for any (g_t, g_b) is
    sigma = g_t^2 s_t + g_b^2 s_b + g_t g_b (s_tb - s_t - s_b).
So for tan(beta) = 1:  sigma(gg->a) = sin^2(theta) P_tb,  sigma(gg->A) = cos^2(theta) P_tb,
sigma(gg->H) = 2 S_t + 2 S_b - S_tb.   b bbar-associated production (5FS bbA) is ~ tan^2(beta)
suppressed relative to type-II large-tan(beta) scenarios and is negligible at tan(beta) = 1.

Usage: python twohdma_single.py [--tanb 1] [--sintheta 0.35]
"""

from __future__ import annotations

import argparse
import json
import math

from mgxsec_common import OUT_DIR, write_table


def load(table: str) -> dict[float, float]:
    """{mass: sigma_pb} from a spin-0 table."""
    d = json.loads((OUT_DIR / f"ggS_spin0_{table}_13TeV_LO.json").read_text())
    return {r[0]: r[1] for r in d["data"]}


def combine(gt: float, gb: float, st: float, sb: float, stb: float) -> float:
    """sigma for couplings (g_t, g_b) from the unit-coupling tables."""
    return gt * gt * st + gb * gb * sb + gt * gb * (stb - st - sb)


def main() -> None:
    """Write the derived 2HDM+a table."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--tanb", type=float, default=1.0)
    ap.add_argument("--sintheta", type=float, default=0.35)
    args = ap.parse_args()
    tb, st = args.tanb, args.sintheta
    ct = math.sqrt(1 - st * st)
    S = {k: load(f"S_{k}") for k in ("t", "b", "tb")}
    P = {k: load(f"P_{k}") for k in ("t", "b", "tb")}
    rows = []
    for m in sorted(S["tb"]):
        sa = combine(st / tb, st * tb, P["t"][m], P["b"][m], P["tb"][m])
        sA = combine(ct / tb, ct * tb, P["t"][m], P["b"][m], P["tb"][m])
        sH = combine(-1 / tb, tb, S["t"][m], S["b"][m], S["tb"][m])
        rows.append([m, sa, sA, sH])
    meta = {"name": "2HDMa_single_production_13TeV_LO",
            "description": ("gg -> a, gg -> A, gg -> H in the 2HDM+a (type II, alignment) at a common mass M, "
                            "derived from the MG5 spin-0 tables (DMsimp_s_spin0_4f_ybMSbar, t+b loops)."),
            "parameters": {"tan_beta": tb, "sin_theta": st, "cos_beta_minus_alpha": 0.0},
            "order": "LO (one loop); multiply by K(M) (ggS_kfactors_13TeV.json; for CP-odd use the same K)",
            "pdf": "nn23lo1", "scales": "mu_R = mu_F = M"}
    write_table("2hdma_single_production_13TeV_LO.json", meta,
                ["mass_gev", "sigma_gg_a_pb", "sigma_gg_A_pb", "sigma_gg_H_pb"], rows)
    for r in rows:
        print("  ".join(f"{x:.4g}" for x in r))


if __name__ == "__main__":
    main()

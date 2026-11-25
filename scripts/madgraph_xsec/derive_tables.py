"""Derived Z' tables from the per-flavour MG5 tables (exact at LO: flavours add incoherently).

  zprime_spin1_uptype_13TeV_LO.json    g_u = g_c (= g_t) = 1 :  sigma_u + sigma_c
  zprime_spin1_downtype_13TeV_LO.json  g_d = g_s = g_b = 1   :  sigma_d + sigma_s + sigma_b
  zprime_spin1_BminusL_13TeV_LO.json   g_q = g_BL/3, g_BL = 1 :  sigma_vector / 9
  (also a check column: sum of the five flavour tables / universal-vector table)
"""

from __future__ import annotations

import json

from mgxsec_common import OUT_DIR, write_table


def load(name: str) -> tuple[dict, dict[float, list]]:
    """Table metadata and {mass: row}."""
    d = json.loads((OUT_DIR / f"zprime_spin1_{name}_13TeV_LO.json").read_text())
    return d, {r[0]: r for r in d["data"]}


def main() -> None:
    """Write the derived tables."""
    base, vec = load("vector")
    fl = {q: load(q)[1] for q in ("u", "d", "s", "c", "b")}
    keep = {k: base[k] for k in ("model", "ufo_path", "order", "pdf", "scales", "lagrangian")}
    combos = {
        "uptype": (["u", "c"], "vector coupling 1 to up-type quarks (u, c; t irrelevant): sigma_u + sigma_c"),
        "downtype": (["d", "s", "b"], "vector coupling 1 to down-type quarks: sigma_d + sigma_s + sigma_b"),
    }
    for name, (qs, desc) in combos.items():
        rows = []
        for m in sorted(vec):
            s = sum(fl[q][m][1] for q in qs)
            e = sum(fl[q][m][2] ** 2 for q in qs) ** 0.5
            rows.append([m, s, e])
        write_table(f"zprime_spin1_{name}_13TeV_LO.json",
                    dict(keep, name=f"pp_to_Zprime_spin1_{name}_13TeV_LO", description=desc,
                         derived_from=[f"zprime_spin1_{q}_13TeV_LO.json" for q in qs]),
                    ["mass_gev", "sigma_pb", "sigma_err_pb"], rows)
    rows = []
    for m in sorted(vec):
        s5 = sum(fl[q][m][1] for q in fl)
        rows.append([m, vec[m][1] / 9.0, vec[m][2] / 9.0, s5 / vec[m][1]])
    write_table("zprime_spin1_BminusL_13TeV_LO.json",
                dict(keep, name="pp_to_Zprime_spin1_BminusL_13TeV_LO",
                     description=("B-L-like: every quark has vector coupling g_BL/3 with g_BL = 1 "
                                  "(sigma = sigma_universal/9; leptons do not enter production)"),
                     derived_from=["zprime_spin1_vector_13TeV_LO.json"]),
                ["mass_gev", "sigma_pb", "sigma_err_pb", "check_sum_of_flavours_over_universal"], rows)
    print("max |sum of flavours/universal - 1| =", max(abs(r[3] - 1) for r in rows))


if __name__ == "__main__":
    main()

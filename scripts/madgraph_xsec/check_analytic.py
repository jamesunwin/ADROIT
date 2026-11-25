"""Compare every MG5 table point with the independent analytic LO formula (analytic_lo.py).

Writes ~/agentic-dm-tools/madgraph-xsec/validation_analytic.json with ratio MG5/analytic per point.
"""

from __future__ import annotations

import json

import analytic_lo as an
from mgxsec_common import OUT_DIR

ZP = {"vector": {1: 1, 2: 1, 3: 1, 4: 1, 5: 1}, "axial": {1: 1, 2: 1, 3: 1, 4: 1, 5: 1},
      "u": {2: 1}, "d": {1: 1}, "s": {3: 1}, "c": {4: 1}, "b": {5: 1}}
S0 = {"S_tb": ({172.0: 1, 4.7: 1}, "even"), "S_t": ({172.0: 1}, "even"), "S_b": ({4.7: 1}, "even"),
      "P_tb": ({172.0: 1, 4.7: 1}, "odd"), "P_t": ({172.0: 1}, "odd"), "P_b": ({4.7: 1}, "odd")}


def main() -> None:
    """Loop over the tables that exist and record MG5/analytic ratios."""
    out = {"description": ("MG5 / analytic LO ratio for every tabulated point (same PDF grid NNPDF23_lo_as_0130_qed, "
                           "same scale; analytic alpha_s = exact 2-loop RGE, MG5 uses its own 2-loop formula)"),
           "tables": {}}
    for name, cps in ZP.items():
        f = OUT_DIR / f"zprime_spin1_{name}_13TeV_LO.json"
        if not f.exists():
            continue
        rows = [[r[0], r[1], an.sigma_zprime(r[0], cps)] for r in json.loads(f.read_text())["data"]]
        out["tables"][f.name] = {"columns": ["mass_gev", "mg5_pb", "analytic_pb"],
                                 "max_abs_dev": max(abs(a / b - 1) for _, a, b in rows), "data": rows}
    for name, (q, cp) in S0.items():
        f = OUT_DIR / f"ggS_spin0_{name}_13TeV_LO.json"
        if not f.exists():
            continue
        rows = [[r[0], r[1], an.sigma_ggs(r[0], q, cp), r[4]] for r in json.loads(f.read_text())["data"]]
        out["tables"][f.name] = {"columns": ["mass_gev", "mg5_pb", "analytic_pb", "method"],
                                 "max_abs_dev": max(abs(r[1] / r[2] - 1) for r in rows), "data": rows}
    (OUT_DIR / "validation_analytic.json").write_text(json.dumps(out, indent=1))
    for k, v in out["tables"].items():
        print(f"{k:45s} max |MG5/analytic - 1| = {v['max_abs_dev']:.4f}")


if __name__ == "__main__":
    main()

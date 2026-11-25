"""MG5 cross-check of the derived 2HDM+a table with the Pseudoscalar_2HDM UFO (loop-induced).

Benchmark (LHC DM WG, arXiv:1810.09420): tan(beta) = 1, sin(theta) = 0.35, sin(beta-alpha) = 1,
M_H = M_A = M_H+- = 600 GeV, M_a = 250 GeV, lambda_3 = lambda_P1 = lambda_P2 = 3, m_chi = 10 GeV.
  g g > h4 [noborn=QCD]   (a, M = 250)    vs  sin^2(theta) * P_tb(250)
  g g > h3 [noborn=QCD]   (A, M = 600)    vs  cos^2(theta) * P_tb(600)
  g g > h2 [noborn=QCD]   (H, M = 600)    vs  2 S_t + 2 S_b - S_tb  at 600
Writes validation_2hdma.json.
"""

from __future__ import annotations

import json

from mgxsec_common import OUT_DIR, UFO_DIR, generate_process, launch_point
from xsec_lookup import spin0_sigma

BENCH = {"tanbeta": 1.0, "sinbma": 1.0, "sinp": 0.35, "lam3": 3.0, "laP1": 3.0, "laP2": 3.0,
         "mh1": 125.0, "mh2": 600.0, "mh3": 600.0, "mhc": 600.0, "mh4": 250.0, "MXd": 10.0,
         "gPXd": 1.0, "MT": 172.0, "MB": 4.7, "ymt": 172.0, "ymb": 4.7}
WIDTHS = {"wh2": 1.0, "wh3": 1.0, "wh4": 1.0, "whc": 1.0}


def main() -> None:
    """Run the three loop-induced points and compare with the derived table."""
    out = {"benchmark": BENCH, "items": []}
    cases = [("h4", 250.0, 0.35 ** 2 * spin0_sigma(250.0, 1, 1, "P")),
             ("h3", 600.0, (1 - 0.35 ** 2) * spin0_sigma(600.0, 1, 1, "P")),
             ("h2", 600.0, spin0_sigma(600.0, -1, 1, "S"))]
    for name, m, derived in cases:
        procdir = generate_process(f"thdma_gg{name}", str(UFO_DIR / "Pseudoscalar_2HDM"), [f"g g > {name} [noborn=QCD]"],
                                   pre_commands=["set ninja None --no_save", "set collier None --no_save"])
        r = launch_point(procdir, dict(BENCH, **WIDTHS), {"nevents": 100}, tag=f"bench_{name}")
        out["items"].append({"process": f"g g > {name}", "mass_gev": m, "sigma_MG5_Pseudoscalar_2HDM_pb": r["sigma_pb"],
                             "sigma_derived_from_DMsimp_tables_pb": derived, "ratio": r["sigma_pb"] / derived,
                             "seconds": r["seconds"]})
        print(out["items"][-1], flush=True)
    (OUT_DIR / "validation_2hdma.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

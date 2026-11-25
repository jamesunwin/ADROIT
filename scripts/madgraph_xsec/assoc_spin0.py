"""Associated production of the DMsimp spin-0 mediator: sigma(pp -> t tbar S) and sigma(pp -> b bbar S), 13 TeV LO.

Model: DMsimp_s_spin0_4f_ybMSbar (massive b, 4-flavour scheme for b bbar S).
  p p > t t~ y0   with gSu33 = 1 (scalar) or gPu33 = 1 (pseudoscalar)
  p p > b b~ y0   with gSd33 = 1 or gPd33 = 1 (4FS, p = g u c d s; ymb = MB = 4.7 GeV)
Scales: mu_R = mu_F = H_T/2 (dynamical_scale_choice = 3), nn23lo1, 2000 events, no cuts.
Coupling scaling: sigma(ttS) ~ g_t^2 ; sigma(bbS) ~ g_b^2 (no interference with gg -> S at this order).
Caveat: LO 4FS b bbar S has a large scale uncertainty (factor ~2); the HXSWG 'Santander' matched
4FS/5FS bbH is ~1 % of ggF for an SM-like 125 GeV Higgs.

Usage: python assoc_spin0.py [--suffix A]
"""

from __future__ import annotations

import argparse

from mgxsec_common import UFO_DIR, generate_process, launch_point, write_table
from spin0_ggf import MB, MODEL, MT, couplings_for

MASSES = [10.0, 50.0, 125.0, 300.0, 500.0, 1000.0, 2000.0]
CASES = {
    "ttS_scalar": ("p p > t t~ y0", "S_t"),
    "ttS_pseudo": ("p p > t t~ y0", "P_t"),
    "bbS_scalar": ("p p > b b~ y0", "S_b"),
    "bbS_pseudo": ("p p > b b~ y0", "P_b"),
}


def main() -> None:
    """Run the associated-production grid."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", default="")
    ap.add_argument("cases", nargs="*", default=list(CASES))
    args = ap.parse_args()
    for case in args.cases:
        proc, table = CASES[case]
        procdir = generate_process(f"assoc_{proc.split('>')[1].strip().replace(' ', '').replace('~', 'x')}{args.suffix}",
                                   str(UFO_DIR / MODEL), [proc])
        rows = []
        for m in MASSES:
            params = dict(couplings_for(table), MY0=m, WY0=1.0, MT=MT, ymt=MT, MB=MB, ymb=MB)
            res = launch_point(procdir, params, {"dynamical_scale_choice": 3}, tag=f"{case}_M{m:g}")
            rows.append([m, res["sigma_pb"], res["sigma_err_pb"], res["seconds"]])
            print(f"[{case}] M={m:g} sigma={res['sigma_pb']:.5g} pb ({res['seconds']} s)", flush=True)
        meta = {"name": f"{case}_13TeV_LO", "process": proc, "model": MODEL,
                "couplings": {k: v for k, v in couplings_for(table).items() if v},
                "order": "LO (tree)", "pdf": "nn23lo1", "scales": "mu_R = mu_F = H_T/2",
                "note": "sigma scales as the square of the single Yukawa multiplier"}
        write_table(f"assoc_{case}_13TeV_LO.json", meta, ["mass_gev", "sigma_pb", "sigma_err_pb", "seconds"], rows)


if __name__ == "__main__":
    main()

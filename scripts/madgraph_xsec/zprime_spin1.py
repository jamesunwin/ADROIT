"""sigma(pp -> Z') at 13 TeV, LO, DMsimp_s_spin1 (LHC DM WG), unit quark couplings.

Lagrangian of the UFO (DMsimp_s_spin1 v2.1, FeynRules):
    L  >  Y1_mu  sum_q  qbar gamma^mu ( gVq + gAq gamma^5 ) q
(no factor 1/2).  For a narrow 2 -> 1 resonance and massless quarks the partonic
cross section is   sigma_hat(q qbar -> Y1) = (pi/3) (gVq^2 + gAq^2) delta(s_hat - M^2),
so vector and axial couplings give identical sigma and different flavours add
incoherently:   sigma(g) = sum_q (gVq^2 + gAq^2) * sigma_q(M)   [sigma_q from the
per-flavour tables at unit coupling].  B-L-like (g_q = g_BL/3 for every quark):
sigma = (g_BL/3)^2 * sigma_universal.  The Y1 width does not enter a 2 -> 1 LO
cross section (MadEvent fixes s_hat = M^2), so WY1 is set to an arbitrary fixed value.

MG5 settings: import model ~/agentic-dm-tools/ufo/DMsimp_s_spin1 ; generate p p > y1
(5-flavour proton: u d s c b and antiquarks, gluon);
run card: 13 TeV, nn23lo1, mu_R = mu_F = sqrt(s_hat) = M, 2000 events.

Usage:  python zprime_spin1.py [table ...] [--suffix A] [--n 25] [--midpoints | --masses M1 M2 ...]
Tables: vector, axial, u, d, s, c, b   (default: all)
"""

from __future__ import annotations

import argparse
import json

from mgxsec_common import OUT_DIR, UFO_DIR, generate_process, mass_grid, scan, write_table

QUARK_COUPLINGS = ["gVd11", "gVu11", "gVd22", "gVu22", "gVd33", "gVu33",
                   "gAd11", "gAu11", "gAd22", "gAu22", "gAd33", "gAu33",
                   "gVu31", "gAu31", "gVd31", "gAd31"]
OTHER_ZERO = ["gVXd", "gAXd", "gVXc", "gVh", "gVl11", "gVl22", "gVl33",
              "gAl11", "gAl22", "gAl33", "gnu11", "gnu22", "gnu33"]

#: table name -> couplings set to 1 (all others 0)
TABLES: dict[str, list[str]] = {
    "vector": ["gVd11", "gVu11", "gVd22", "gVu22", "gVd33", "gVu33"],
    "axial": ["gAd11", "gAu11", "gAd22", "gAu22", "gAd33", "gAu33"],
    "u": ["gVu11"],
    "d": ["gVd11"],
    "s": ["gVd22"],
    "c": ["gVu22"],
    "b": ["gVd33"],
}
DESCRIPTION = {
    "vector": "universal vector coupling gVq = 1 for all six quarks (top irrelevant for production)",
    "axial": "universal axial coupling gAq = 1 for all six quarks",
    "u": "vector coupling to the up quark only (gVu11 = 1)",
    "d": "vector coupling to the down quark only (gVd11 = 1)",
    "s": "vector coupling to the strange quark only (gVd22 = 1)",
    "c": "vector coupling to the charm quark only (gVu22 = 1)",
    "b": "vector coupling to the bottom quark only (gVd33 = 1), 5-flavour PDF",
}
RUN_SETTINGS = {"maxjetflavor": 5}


def couplings_for(table: str) -> dict[str, float]:
    """Return the full DMINPUTS coupling assignment for a table."""
    cps = {c: 0.0 for c in QUARK_COUPLINGS + OTHER_ZERO}
    for c in TABLES[table]:
        cps[c] = 1.0
    return cps


def main() -> None:
    """Generate the process once and scan the requested tables."""
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="*", default=list(TABLES))
    ap.add_argument("--suffix", default="", help="process-dir suffix (one dir per parallel job)")
    ap.add_argument("--n", type=int, default=25, help="number of masses (log grid 50-6000 GeV)")
    ap.add_argument("--masses", nargs="*", type=float, default=None,
                    help="explicit masses; rows are merged into an existing table")
    ap.add_argument("--midpoints", action="store_true",
                    help="add the geometric midpoints of the default grid (merged into existing tables)")
    args = ap.parse_args()
    procdir = generate_process(f"zp_spin1{args.suffix}", str(UFO_DIR / "DMsimp_s_spin1"), ["p p > y1"])
    grid = mass_grid(50.0, 6000.0, args.n)
    masses = args.masses or grid
    if args.midpoints:
        masses = [float(f"{(a * b) ** 0.5:.3g}") for a, b in zip(grid[:-1], grid[1:])]
    for table in args.tables:
        cps = couplings_for(table)
        fixed = dict(cps, WY1=1.0)
        rows = scan(procdir, masses, "MY1", fixed, RUN_SETTINGS, f"spin1_{table}")
        old = OUT_DIR / f"zprime_spin1_{table}_13TeV_LO.json"
        if (args.masses or args.midpoints) and old.exists():
            merged = {r[0]: r for r in json.loads(old.read_text())["data"]}
            merged.update({r[0]: r for r in rows})
            rows = [merged[k] for k in sorted(merged)]
        meta = {
            "name": f"pp_to_Zprime_spin1_{table}_13TeV_LO",
            "process": "p p > y1 (2 -> 1, narrow resonance), 5-flavour proton",
            "description": DESCRIPTION[table],
            "model": "DMsimp_s_spin1 v2.1 (LHC DM WG; FeynRules DMsimp page, DMsimp_s_spin1.zip)",
            "ufo_path": str(UFO_DIR / "DMsimp_s_spin1"),
            "lagrangian": "Y1_mu qbar gamma^mu (gVq + gAq gamma5) q",
            "couplings": {k: v for k, v in cps.items() if v != 0.0},
            "all_other_couplings": 0.0,
            "order": "LO (tree level)",
            "pdf": "nn23lo1 = NNPDF2.3 LO alpha_s(MZ)=0.130 QED (MG5 built-in)",
            "scales": "mu_R = mu_F = sqrt(s_hat) = M (dynamical_scale_choice = 4)",
            "nevents": 2000,
            "rescaling": "sigma = sum_q (gVq^2 + gAq^2) sigma_q ; narrow width ; multiply by BR yourself",
            "kfactor_note": "QCD K = sigma(NNLO)/sigma(LO, this setup) ~ 1.2-1.35 (Drell-Yan like); see README/report",
        }
        path = write_table(f"zprime_spin1_{table}_13TeV_LO.json", meta,
                           ["mass_gev", "sigma_pb", "sigma_err_pb", "seconds"], rows)
        print("wrote", path, flush=True)


if __name__ == "__main__":
    main()

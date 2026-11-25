"""sigma(gg -> S) at 13 TeV, LO (top + bottom loops), DMsimp spin-0 (LHC DM WG).

Model: DMsimp_s_spin0_4f_ybMSbar (FeynRules DMsimp page; 4-flavour version with a
massive b quark, MB = ymb = 4.7 GeV, MT = ymt = 172 GeV).  Lagrangian (Yukawa-like,
minimal flavour violation):
    L  >  - sum_q  (y_q / sqrt2) Y0 qbar ( gSq + i gPq gamma5 ) q ,   y_q = sqrt2 m_q / v
so gSq = 1 means the SM-Higgs-like coupling m_q / v.  Only t and b have Yukawas in this
model (u, d, s, c are massless), so the loop contains t and b.

Two MG5 methods, chosen by mass:
 * M >= M_SWITCH (50 GeV): exact one-loop, loop-induced MadEvent:
     set ninja None --no_save ; set collier None --no_save   (MadLoop with CutTools + IREGI only)
     import model .../DMsimp_s_spin0_4f_ybMSbar ; generate g g > y0 [noborn=QCD]
   (run card nevents = 100: the survey alone gives 0.5 % precision for a 2 -> 1 process;
    a refine of loop-induced 2 -> 1 trips an MG5 3.8.0 assertion 'ftn25').
 * M < M_SWITCH: MadLoop with CutTools only is numerically unstable for M << m_t (the
   quad-precision rescue returns ~0 at M ~ 10 GeV and is very slow at 40 GeV), so we use
   MG5's 'heft' model (g g > h, point-like ggh vertex) and rescale analytically:
     sigma = sigma_heft(M) * |(3/4) sum_q g_q A(tau_q)|^2 / F_heft(M, MT),
   with A = A_H (CP-even) or A_A (CP-odd) from analytic_lo.py, tau_q = M^2/(4 m_q^2), and
   F_heft = (1 + 7 r/120 + r^2/168 + 13 r^3/16800)^2, r = M^2/MT^2, the finite-mt factor
   that heft's GH coupling contains.  Exact at LO (2 -> 1: the loop only changes the
   normalisation, not the kinematics).
Run card: 13 TeV, nn23lo1 (alpha_s(MZ) = 0.130, 2-loop running), mu_R = mu_F = M.

Rescaling for arbitrary (g_t, g_b), same CP:
    sigma = g_t^2 sigma_t + g_b^2 sigma_b + g_t g_b (sigma_tb - sigma_t - sigma_b)
Tables: S_tb, S_t, S_b (CP-even, gS = 1) and P_tb, P_t, P_b (CP-odd, gP = 1).

Usage: python spin0_ggf.py [table ...] [--suffix A] [--n 25] [--low-only | --high-only]
                          [--midpoints | --masses M1 M2 ...]   (extra masses are merged into the tables)
"""

from __future__ import annotations

import argparse
import json

import analytic_lo as an
from mgxsec_common import OUT_DIR, UFO_DIR, generate_process, launch_point, mass_grid, write_table

MODEL = "DMsimp_s_spin0_4f_ybMSbar"
M_SWITCH = 50.0
MT, MB = 172.0, 4.7
ALL_COUPLINGS = ["gSd11", "gSu11", "gSd22", "gSu22", "gSd33", "gSu33",
                 "gPd11", "gPu11", "gPd22", "gPu22", "gPd33", "gPu33",
                 "gSXr", "gSXc", "gSXd", "gPXd", "gSg", "gPg", "gSh1", "gSh2",
                 "gSb", "gPb", "gSw", "gPw"]
TABLES: dict[str, list[str]] = {
    "S_tb": ["gSu33", "gSd33"],
    "S_t": ["gSu33"],
    "S_b": ["gSd33"],
    "P_tb": ["gPu33", "gPd33"],
    "P_t": ["gPu33"],
    "P_b": ["gPd33"],
}
#: quark content {mass: coupling} and CP for the analytic rescaling of each table
QUARKS = {"S_tb": ({MT: 1.0, MB: 1.0}, "even"), "S_t": ({MT: 1.0}, "even"), "S_b": ({MB: 1.0}, "even"),
          "P_tb": ({MT: 1.0, MB: 1.0}, "odd"), "P_t": ({MT: 1.0}, "odd"), "P_b": ({MB: 1.0}, "odd")}
RUN_SETTINGS: dict[str, object] = {"nevents": 100}


def couplings_for(table: str) -> dict[str, float]:
    """All DMINPUTS couplings zero except the table's (set to 1)."""
    cps = {c: 0.0 for c in ALL_COUPLINGS}
    for c in TABLES[table]:
        cps[c] = 1.0
    return cps


def make_procdir(suffix: str = ""):
    """Generate the loop-induced gg > y0 process directory."""
    return generate_process(f"ggS_loop{suffix}", str(UFO_DIR / MODEL), ["g g > y0 [noborn=QCD]"],
                            pre_commands=["set ninja None --no_save", "set collier None --no_save"])


def make_heft_procdir(suffix: str = ""):
    """Generate the heft g g > h process directory (low-mass method)."""
    return generate_process(f"ggH_heft{suffix}", str(UFO_DIR / "heft"), ["g g > h"])


def unstable_count(procdir) -> int:
    """Number of MadLoop 'exceptional unstable PS point' messages in the last run."""
    n = 0
    for log in procdir.glob("SubProcesses/P*/G*/log.txt"):
        n += log.read_text(errors="ignore").count("exceptional unstable PS point")
    return n


def run_loop(table: str, masses: list[float], suffix: str) -> list[list]:
    """Loop-induced MG5 runs (M >= M_SWITCH)."""
    procdir = make_procdir(suffix)
    rows = []
    for m in masses:
        params = dict(couplings_for(table), MY0=m, WY0=1.0, MT=MT, ymt=MT, MB=MB, ymb=MB)
        res = launch_point(procdir, params, RUN_SETTINGS, tag=f"spin0_{table}_M{m:g}")
        nun = unstable_count(procdir)
        rows.append([m, res["sigma_pb"], res["sigma_err_pb"], res["seconds"], "loop-induced", nun])
        print(f"[spin0_{table}] M={m:g} sigma={res['sigma_pb']:.5g} pb ({res['seconds']} s, unstable={nun})", flush=True)
    return rows


def run_heft(masses: list[float], suffix: str) -> dict[float, dict]:
    """heft g g > h at each low mass; returns {M: launch result}."""
    procdir = make_heft_procdir(suffix)
    out = {}
    for m in masses:
        res = launch_point(procdir, {"MH": m, "MT": MT, "WH": 1.0e-3}, {"nevents": 1000}, tag=f"heft_M{m:g}")
        out[m] = res
        print(f"[heft] M={m:g} sigma_heft={res['sigma_pb']:.5g} pb ({res['seconds']} s)", flush=True)
    return out


def heft_rows(table: str, heft: dict[float, dict]) -> list[list]:
    """Rescale heft results to the exact t+b (CP-even/odd) LO cross section."""
    quarks, cp = QUARKS[table]
    rows = []
    for m, res in sorted(heft.items()):
        factor = an.ggs_amp2(m, quarks, cp) / an.heft_factor(m, MT)
        rows.append([m, res["sigma_pb"] * factor, res["sigma_err_pb"] * factor, res["seconds"],
                     f"heft x {factor:.5g}", 0])
    return rows


def write(table: str, rows: list[list]) -> None:
    """Write one spin-0 table (merging with an existing file's rows at other masses)."""
    path = OUT_DIR / f"ggS_spin0_{table}_13TeV_LO.json"
    if path.exists():
        old = {r[0]: r for r in json.loads(path.read_text())["data"]}
    else:
        old = {}
    old.update({r[0]: r for r in rows})
    rows = [old[k] for k in sorted(old)]
    cps = couplings_for(table)
    cp = "CP-even scalar" if table.startswith("S") else "CP-odd pseudoscalar"
    meta = {
        "name": f"gg_to_S_spin0_{table}_13TeV_LO",
        "process": ("g g > y0 [noborn=QCD] (exact one loop, t and b) for M >= 50 GeV; "
                    "heft g g > h rescaled by |(3/4) sum g_q A(tau_q)|^2 / F_heft below 50 GeV"),
        "description": f"{cp}, Yukawa-like couplings {TABLES[table]} = 1 (multiples of m_q/v)",
        "model": f"{MODEL} (LHC DM WG DMsimp spin-0, 4-flavour, MB = ymb = 4.7 GeV, MT = ymt = 172 GeV); heft (MG5) below 50 GeV",
        "ufo_path": str(UFO_DIR / MODEL),
        "lagrangian": "-(y_q/sqrt2) Y0 qbar (gSq + i gPq gamma5) q, y_q = sqrt2 m_q/v",
        "couplings": {k: v for k, v in cps.items() if v != 0.0},
        "all_other_couplings": 0.0,
        "order": "LO (one loop, loop-induced)",
        "pdf": "nn23lo1 = NNPDF2.3 LO alpha_s(MZ)=0.130 QED (MG5 built-in); alpha_s 2-loop running",
        "scales": "mu_R = mu_F = M (dynamical_scale_choice = 4)",
        "rescaling": "sigma = g_t^2 s_t + g_b^2 s_b + g_t g_b (s_tb - s_t - s_b); narrow width",
        "kfactor_note": "multiply by K(M) from ggS_kfactors_13TeV.json (HXSWG / this LO); see report",
        "extra_columns": "method; unstable = number of MadLoop exceptional (zero-weighted) PS points",
    }
    write_table(path.name, meta, ["mass_gev", "sigma_pb", "sigma_err_pb", "seconds", "method", "unstable"], rows)
    print("wrote", path, flush=True)


def main() -> None:
    """Scan the requested spin-0 tables."""
    ap = argparse.ArgumentParser()
    ap.add_argument("tables", nargs="*", default=list(TABLES))
    ap.add_argument("--suffix", default="")
    ap.add_argument("--n", type=int, default=25, help="masses on a log grid 10-3000 GeV")
    ap.add_argument("--low-only", action="store_true")
    ap.add_argument("--high-only", action="store_true")
    ap.add_argument("--masses", nargs="*", type=float, default=None,
                    help="explicit masses (added to existing tables), e.g. a denser grid near 2 m_t")
    ap.add_argument("--midpoints", action="store_true",
                    help="add the geometric midpoints of the default grid (merged into existing tables)")
    args = ap.parse_args()
    grid = mass_grid(10.0, 3000.0, args.n)
    masses = args.masses or grid
    if args.midpoints:
        masses = [float(f"{(a * b) ** 0.5:.3g}") for a, b in zip(grid[:-1], grid[1:])]
    low = [m for m in masses if m < M_SWITCH]
    high = [m for m in masses if m >= M_SWITCH]
    if not args.high_only and low:
        heft = run_heft(low, args.suffix)
        for table in args.tables:
            write(table, heft_rows(table, heft))
    if not args.low_only:
        for table in args.tables:
            write(table, run_loop(table, high, args.suffix))


if __name__ == "__main__":
    main()

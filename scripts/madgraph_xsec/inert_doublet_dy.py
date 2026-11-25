"""Inert-doublet Drell-Yan pair production at 13 TeV, LO, with MG5 and InertDoublet_UFO_mg5.

The inert doublet  Phi_2 = (H+, (H0 + i A0)/sqrt2)  has hypercharge 1/2 and couples to the SM
only through gauge interactions (plus the Higgs portal), so the pair cross sections

    q qbar  -> Z*      -> H0 A0
    q qbar' -> W+-*    -> H+- H0 ,  H+- A0
    q qbar  -> gamma*/Z* -> H+ H-

have NO free coupling: they are fixed functions of (M_H0, M_A0, M_H+-) and of the SM gauge
couplings.  The scalar (p-wave) Drell-Yan threshold makes sigma ~ beta^3 near threshold.
Equal-mass identities (exact at LO): sigma(H+H-) = sigma(slepton_L pair) at the same mass,
sigma(H0 A0) = sigma(sneutrino pair); sigma(H+H0) = sigma(H+A0) for M_H0 = M_A0.

Model: ~/agentic-dm-tools/ufo/InertDoublet_UFO_mg5 (Goudelis-Herrmann-Stal FeynRules model,
MG5-compatibility edits documented in its README_mg5_edits.txt); MG5 names: h2 = H0 (35),
h3 = A0 (36), h+/h- = H+- (37).  5-flavour proton (u d s c b, MMC = MMB = 0).
Run card: 13 TeV, nn23lo1, mu_R = mu_F = H_T/2 = sum m_T/2 (dynamical_scale_choice = 3), 2000 events.
The UFO also contains an effective g g h vertex, so g g -> h* -> H+H- / H0H0 / A0A0 exists at tree level with
strength lambda_3 (= 2(M_H+-^2 - M_H0^2)/v^2 + 2 lamL); it is portal-dependent, so the gluon is removed
from the proton here (define p = u c d s b + antiquarks): the tables are the pure gauge (Drell-Yan) part.

Usage: python inert_doublet_dy.py [equal|split|all] [--suffix A] [--channels H0A0 HpH0 ...]
"""

from __future__ import annotations

import argparse

from mgxsec_common import UFO_DIR, generate_process, launch_point, mass_grid, write_table

MODEL = UFO_DIR / "InertDoublet_UFO_mg5"
CHANNELS: dict[str, list[str]] = {
    "H0A0": ["p p > h2 h3"],
    "HpmH0": ["p p > h+ h2", "p p > h- h2"],
    "HpmA0": ["p p > h+ h3", "p p > h- h3"],
    "HpHm": ["p p > h+ h-"],
}
FIXED = {"mmh": 125.0, "MMT": 172.5, "MMC": 0.0, "MMB": 0.0, "lamL": 0.0, "lam2": 0.1,
         "WA0": 1.0, "WHch": 1.0, "WH0": 0.0, "Wh": 0.00407, "WT": 1.42}
RUN_SETTINGS = {"dynamical_scale_choice": 3, "maxjetflavor": 5}
#: split-spectrum examples (M_H0, M_A0, M_H+-) in GeV
SPLIT_POINTS = [(60.0, 120.0, 120.0), (65.0, 100.0, 150.0), (70.0, 300.0, 300.0),
                (100.0, 200.0, 250.0), (200.0, 210.0, 220.0), (500.0, 510.0, 520.0),
                (60.0, 500.0, 500.0), (300.0, 400.0, 350.0)]


def procdir_for(channel: str, suffix: str = ""):
    """Generate (once) the process directory for one channel."""
    return generate_process(f"idm_{channel}{suffix}", str(MODEL), CHANNELS[channel],
                            post_import=["define p = u c d s b u~ c~ d~ s~ b~"])


def run_points(channel: str, points: list[tuple[float, float, float]], suffix: str) -> list[list[float]]:
    """Integrate one channel at the given (M_H0, M_A0, M_H+-) points."""
    procdir = procdir_for(channel, suffix)
    rows = []
    for mh0, ma0, mhc in points:
        params = dict(FIXED, mmH0=mh0, mmA0=ma0, mmHch=mhc)
        res = launch_point(procdir, params, RUN_SETTINGS, tag=f"{channel}_{mh0:g}_{ma0:g}_{mhc:g}")
        rows.append([mh0, ma0, mhc, res["sigma_pb"], res["sigma_err_pb"], res["seconds"]])
        print(f"[{channel}] ({mh0:g},{ma0:g},{mhc:g}) sigma={res['sigma_pb']:.5g} pb ({res['seconds']} s)", flush=True)
    return rows


def main() -> None:
    """Equal-mass scans and split examples."""
    ap = argparse.ArgumentParser()
    ap.add_argument("what", nargs="?", default="all", choices=["equal", "split", "all"])
    ap.add_argument("--suffix", default="")
    ap.add_argument("--channels", nargs="*", default=list(CHANNELS))
    ap.add_argument("--n", type=int, default=16)
    args = ap.parse_args()
    for ch in args.channels:
        meta = {
            "process": " ; ".join(CHANNELS[ch]) + "  (p = u c d s b + antiquarks, no gluon: pure Drell-Yan)",
            "model": "InertDoublet_UFO_mg5 (Goudelis, Herrmann, Stal; FeynRules 2.3.49) - MG5-compatible copy",
            "ufo_path": str(MODEL),
            "couplings": "none free: pure SM gauge couplings (alpha=1/128.9, MW=79.947, MZ=91.1876 inputs of the UFO)",
            "fixed_parameters": FIXED,
            "order": "LO (tree level)",
            "pdf": "nn23lo1 = NNPDF2.3 LO alpha_s(MZ)=0.130 QED (MG5 built-in)",
            "scales": "mu_R = mu_F = H_T/2 (dynamical_scale_choice = 3)",
            "nevents": 2000,
            "kfactor_note": "NLO(+NLL) K ~ 1.15-1.3 (cf. slepton pairs, Resummino); see validation_idm.json",
        }
        cols = ["mH0_gev", "mA0_gev", "mHpm_gev", "sigma_pb", "sigma_err_pb", "seconds"]
        if args.what in ("equal", "all"):
            pts = [(m, m, m) for m in mass_grid(50.0, 1000.0, args.n)]
            rows = run_points(ch, pts, args.suffix)
            write_table(f"idm_{ch}_equal_masses_13TeV_LO.json",
                        dict(meta, name=f"idm_{ch}_equal_masses_13TeV_LO",
                             description=f"{ch}, M_H0 = M_A0 = M_H+- = M; columns repeat M for clarity"),
                        cols, rows)
        if args.what in ("split", "all"):
            rows = run_points(ch, SPLIT_POINTS, args.suffix)
            write_table(f"idm_{ch}_split_examples_13TeV_LO.json",
                        dict(meta, name=f"idm_{ch}_split_examples_13TeV_LO",
                             description=f"{ch}, non-degenerate example spectra"), cols, rows)


if __name__ == "__main__":
    main()

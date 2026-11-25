"""Validation runs and K-factor tables.

  python validate.py zprime   # SM-Z check with DMsimp_s_spin1, scale variations, analytic comparison
  python validate.py spin0    # 125 GeV and HXSWG comparison, K(M) table, scale variations
  python validate.py kfactor  # (no MG5) K(M) = sigma_HXSWG / sigma_LO from the finished spin-0 tables
  python validate.py idm      # inert doublet vs MSSM slepton/sneutrino pairs; K from SUSY XS WG slepton table

Writes validation_*.json into ~/agentic-dm-tools/madgraph-xsec/.
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np

import analytic_lo as an
from mgxsec_common import OUT_DIR, UFO_DIR, generate_process, launch_point, write_table

# ---- SM Z couplings in the DMsimp convention  L = Y1 qbar gamma^mu (gV + gA gamma5) q -------------
GF, MZ, SW2_EFF = 1.1663787e-5, 91.1876, 0.23153
GZ = math.sqrt(math.sqrt(2) * GF * MZ ** 2)          # g / (2 cos theta_W) in the G_mu scheme
BR_Z_LL = 0.033658                                     # PDG, per lepton flavour


def z_couplings(t3: float, q: float) -> tuple[float, float]:
    """(gV, gA) of the SM Z in the DMsimp normalisation for a fermion with (T3, Q)."""
    return GZ * (t3 - 2 * q * SW2_EFF), -GZ * t3


def zssm_params(mass: float) -> dict[str, float]:
    """DMsimp_s_spin1 parameter set reproducing a sequential-SM Z' (quark couplings only)."""
    gvu, gau = z_couplings(0.5, 2 / 3)
    gvd, gad = z_couplings(-0.5, -1 / 3)
    from zprime_spin1 import couplings_for
    p = couplings_for("u")                               # all zero except gVu11 ...
    p.update({k: 0.0 for k in p})
    for gen in ("11", "22", "33"):
        p[f"gVu{gen}"], p[f"gAu{gen}"] = gvu, gau
        p[f"gVd{gen}"], p[f"gAd{gen}"] = gvd, gad
    p.update(MY1=mass, WY1=0.03 * mass)
    return p


def validate_zprime() -> None:
    """SM-Z normalisation check and scale variations for the Z' tables."""
    procdir = generate_process("zp_spin1_valid", str(UFO_DIR / "DMsimp_s_spin1"), ["p p > y1"])
    out = {"description": "Validation of sigma(pp -> Y1) machinery", "items": []}
    # 1. SM Z with DMsimp couplings
    r = launch_point(procdir, zssm_params(MZ), {"maxjetflavor": 5}, tag="smZ")
    gvu, gau = z_couplings(0.5, 2 / 3)
    gvd, gad = z_couplings(-0.5, -1 / 3)
    g2 = {2: gvu ** 2 + gau ** 2, 4: gvu ** 2 + gau ** 2, 1: gvd ** 2 + gad ** 2,
          3: gvd ** 2 + gad ** 2, 5: gvd ** 2 + gad ** 2}
    ana = an.sigma_zprime(MZ, g2)
    sig_ll = r["sigma_pb"] * BR_Z_LL
    out["items"].append({
        "check": "SM Z boson: DMsimp Y1 with SM-Z quark couplings at M = MZ (narrow width, mu = MZ)",
        "couplings": {"gVu": gvu, "gAu": gau, "gVd": gvd, "gAd": gad, "sin2theta_eff": SW2_EFF},
        "sigma_LO_MG5_pb": r["sigma_pb"], "sigma_LO_analytic_pb": ana,
        "sigma_LO_times_BRll_pb": sig_ll,
        "ATLAS_measured_sigmaZ_BRll_pb": 1981.0, "ATLAS_unc_pb": 58.0,
        "ATLAS_ref": "ATLAS, PLB 759 (2016) 601, arXiv:1603.09222 (66 < m_ll < 116 GeV)",
        "CMS_FEWZ_NNLO_pb": 1928.0,
        "CMS_ref": "CMS, JHEP 07 (2021) 208, arXiv:2103.02708 (sigma(pp->Z+X->ll+X), 60-120 GeV, NNLO FEWZ)",
        "K_measured_over_LO": 1981.0 / sig_ll, "K_NNLO_over_LO": 1928.0 / sig_ll})
    # 2. scale variation (mu_R = mu_F = xi * M) for the universal-vector table
    from zprime_spin1 import couplings_for
    for m in (100.0, 1000.0, 3000.0):
        row = {"check": f"scale variation, universal vector, M = {m:g} GeV"}
        for xi in (0.5, 1.0, 2.0):
            rr = launch_point(procdir, dict(couplings_for("vector"), MY1=m, WY1=1.0),
                              {"maxjetflavor": 5, "scalefact": xi}, tag=f"scale_{m:g}_{xi}")
            row[f"sigma_pb_xi{xi}"] = rr["sigma_pb"]
        row["analytic_xi1_pb"] = an.sigma_zprime(m, {q: 1.0 for q in (1, 2, 3, 4, 5)})
        out["items"].append(row)
    (OUT_DIR / "validation_zprime.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def _load(name: str) -> dict:
    return json.loads((OUT_DIR / name).read_text())


def kfactor_table() -> None:
    """K(M) = sigma_HXSWG / sigma_LO(MG5, S_tb) on the MG5 grid, plus EFT-based K."""
    hx_loop = json.loads((OUT_DIR.parent / "hxswg/hxswg_yr4_bsm13_ggF_quarkloop_NNLO_NNLL.json").read_text())
    hx_eft = json.loads((OUT_DIR.parent / "hxswg/hxswg_yr4_bsm13_ggF_pointlike_N3LO.json").read_text())
    ml, sl = np.array([r[0] for r in hx_loop["data"]]), np.array([r[1] for r in hx_loop["data"]])
    me, se = np.array([r[0] for r in hx_eft["data"]]), np.array([r[1] for r in hx_eft["data"]])
    s_tb = _load("ggS_spin0_S_tb_13TeV_LO.json")
    rows = []
    for m, sig, *_ in s_tb["data"]:
        hl = float(np.exp(np.interp(math.log(m), np.log(ml), np.log(sl))))
        he = float(np.exp(np.interp(math.log(m), np.log(me), np.log(se))))
        lo_eft = an.sigma_ggs(m, {1e9: 1.0})      # heavy-top-limit LO, same PDF/scale as MG5
        lo_exact = an.sigma_ggs(m, {172.0: 1.0, 4.7: 1.0})
        k_eft = he / lo_eft
        rows.append([m, sig, lo_exact, hl, hl / sig, lo_eft, he, k_eft, k_eft * sig])
    meta = {
        "name": "ggS_kfactors_13TeV",
        "description": ("K-factors for gg -> S relative to the MG5 LO setup (nn23lo1, mu = M). "
                        "K_loop = sigma_HXSWG(quark-loop, NNLO+NNLL, t+b(+c), mu=M, PDF4LHC15) / sigma_LO(S_tb). "
                        "K_EFT = sigma_HXSWG(point-like, N3LO, heavy-top EFT, mu=M/2) / sigma_LO(heavy-top EFT, "
                        "same PDF/scale as MG5); sigma_N3LO_rescaled = K_EFT * sigma_LO(S_tb, exact t+b) is the "
                        "'rescaled EFT' N3LO estimate (HXSWG practice at 125 GeV)."),
        "hxswg_source": "LHC HXSWG YR4 BSM 13 TeV sheet (arXiv:1610.07922); interpolated log-linearly in M",
    }
    write_table("ggS_kfactors_13TeV.json", meta,
                ["mass_gev", "sigma_LO_MG5_S_tb_pb", "sigma_LO_analytic_S_tb_pb",
                 "sigma_HXSWG_quarkloop_NNLO_NNLL_pb", "K_loop",
                 "sigma_LO_analytic_EFT_pb", "sigma_HXSWG_pointlike_N3LO_pb", "K_EFT",
                 "sigma_N3LO_rescaled_pb"], rows)
    for r in rows:
        print("  ".join(f"{x:.4g}" for x in r))


def validate_spin0() -> None:
    """125 GeV checks and scale variations for gg -> S."""
    from spin0_ggf import RUN_SETTINGS, couplings_for, make_procdir
    procdir = make_procdir("_valid")
    out = {"description": "Validation of gg -> S (loop-induced, DMsimp_s_spin0_4f_ybMSbar)", "items": []}
    for table in ("S_tb", "P_tb", "S_t", "P_t"):
        fixed = dict(couplings_for(table), WY0=1.0)
        row = {"check": f"{table} at M = 125 GeV, scale variations"}
        for xi in (0.5, 1.0, 2.0):
            r = launch_point(procdir, dict(fixed, MY0=125.0), dict(RUN_SETTINGS, scalefact=xi),
                             tag=f"{table}_125_{xi}")
            row[f"sigma_pb_xi{xi}"] = r["sigma_pb"]
        quarks = {"S_tb": {172.0: 1, 4.7: 1}, "S_t": {172.0: 1}, "P_tb": {172.0: 1, 4.7: 1},
                  "P_t": {172.0: 1}}[table]
        row["analytic_xi1_pb"] = an.sigma_ggs(125.0, quarks, "even" if table[0] == "S" else "odd")
        out["items"].append(row)
    out["references"] = {
        "HXSWG_YR4_SM_ggF_125GeV_13TeV_pb": 48.58,
        "HXSWG_YR4_SM_ggF_ref": "YR4 sheet 'YR4 SM 13TeV': N3LO QCD + NLO EW, mH = 125.00 GeV (48.52 pb at 125.09)",
        "HXSWG_YR4_BSM_pointlike_N3LO_125GeV_pb": 45.2,
        "HXSWG_YR4_BSM_quarkloop_NNLO_NNLL_125GeV_pb": 41.98,
    }
    (OUT_DIR / "validation_spin0.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def validate_idm() -> None:
    """Inert doublet vs MSSM sleptons/sneutrinos (identical gauge quantum numbers) and K-factor."""
    from inert_doublet_dy import FIXED, RUN_SETTINGS, procdir_for
    post = ["define p = u c d s b u~ c~ d~ s~ b~"]
    slep = generate_process("mssm_slepL", "MSSM_SLHA2-no_b_mass", ["p p > el- el+"], post_import=post)
    snu = generate_process("mssm_snu", "MSSM_SLHA2-no_b_mass", ["p p > sve sve~"], post_import=post)
    out = {"description": ("LO cross-check of the inert-doublet UFO against MG5's MSSM_SLHA2 (no_b_mass): "
                           "H+H- has the same gamma/Z couplings as a left-handed charged slepton, H0A0 (degenerate) "
                           "the same Z coupling as a sneutrino pair."), "items": []}
    for m in (100.0, 300.0, 500.0):
        r1 = launch_point(slep, {"mass 1000011": m}, RUN_SETTINGS, tag=f"slepL_{m:g}")
        r2 = launch_point(procdir_for("HpHm"), dict(FIXED, mmH0=m, mmA0=m, mmHch=m), RUN_SETTINGS, tag=f"valid_HpHm_{m:g}")
        r3 = launch_point(snu, {"mass 1000012": m}, RUN_SETTINGS, tag=f"snu_{m:g}")
        r4 = launch_point(procdir_for("H0A0"), dict(FIXED, mmH0=m, mmA0=m, mmHch=m), RUN_SETTINGS, tag=f"valid_H0A0_{m:g}")
        out["items"].append({"mass_gev": m, "sigma_slepL_pair_MSSM_pb": r1["sigma_pb"],
                             "sigma_HpHm_IDM_pb": r2["sigma_pb"], "sigma_snu_pair_MSSM_pb": r3["sigma_pb"],
                             "sigma_H0A0_IDM_pb": r4["sigma_pb"]})
    # K-factor from the LHC SUSY XS WG slepton_L NLO+NLL table (Resummino, PDF4LHC15)
    slt = json.loads((OUT_DIR.parent / "susy-xsec/tables/13TeV_slepton_L_pair_NLO+NLL.json").read_text())
    ours = _load("idm_HpHm_equal_masses_13TeV_LO.json")
    mo, so = np.array([r[0] for r in ours["data"]]), np.array([r[3] for r in ours["data"]])
    kt = []
    for m, s_nlo, *_ in slt["data"]:
        if mo[0] <= m <= mo[-1]:
            s_lo = float(np.exp(np.interp(math.log(m), np.log(mo), np.log(so))))
            kt.append([m, s_nlo, s_lo, s_nlo / s_lo])
    out["K_factor_HpHm"] = {"source": slt["source"] + " (" + slt["order"] + ", " + slt["tool"] + ", " + slt["pdf"] + ")",
                            "columns": ["mass_gev", "sigma_slepL_NLO_NLL_pb", "sigma_HpHm_LO_this_pb", "K"],
                            "data": kt}
    (OUT_DIR / "validation_idm.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "zprime"
    {"zprime": validate_zprime, "spin0": validate_spin0, "kfactor": kfactor_table,
     "idm": validate_idm}[what]()

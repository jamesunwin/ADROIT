"""Build uniform JSON cross-section tables from the downloaded SUSY xsec WG sources.

Output: ~/agentic-dm-tools/susy-xsec/tables/<name>.json with schema
  {name, process, sqrts_gev, order, pdf, tool, source, units, columns, data}
  data rows: [mass_GeV, sigma_pb, rel_unc_up, rel_unc_down]   (rel. uncertainties >= 0)
"""
from __future__ import annotations

import csv
import json
import os

BASE = os.environ.get("SUSY_XSEC_DIR", os.path.expanduser("~/agentic-dm-tools/susy-xsec"))
TW = os.path.join(BASE, "twiki_csv")
HEPI = os.path.join(BASE, "HEPi/hepi/data/json")
OUT = os.path.join(BASE, "tables")
TWIKI = "https://twiki.cern.ch/twiki/bin/view/LHCPhysics/"
HEPI_URL = "https://github.com/APN-Pucky/HEPi/blob/master/hepi/data/json/"
os.makedirs(OUT, exist_ok=True)


def pct(s: str) -> float:
    return abs(float(s.replace("%", "").strip())) / 100.0


def from_twiki_pct(csvname: str) -> list[list[float]]:
    """Rows: mass, sigma[pb], +-unc[%] (symmetric)."""
    rows = list(csv.reader(open(os.path.join(TW, csvname))))[1:]
    return [[float(r[0]), float(r[1]), pct(r[2]), pct(r[2])] for r in rows]


def from_twiki_updown(csvname: str) -> list[list[float]]:
    """Rows: mass, sigma[pb], unc down[%], unc up[%]."""
    rows = list(csv.reader(open(os.path.join(TW, csvname))))[1:]
    return [[float(r[0]), float(r[1]), pct(r[3]), pct(r[2])] for r in rows]


def from_twiki_fb_scale_pdf(csvname: str) -> list[list[float]]:
    """Rows: mass, sigma[fb], +scale%, +pdf%, -scale%, -pdf%  (13x0TeV pages); quadrature sum."""
    rows = list(csv.reader(open(os.path.join(TW, csvname))))[1:]
    out = []
    for r in rows:
        up = (pct(r[2]) ** 2 + pct(r[3]) ** 2) ** 0.5
        dn = (pct(r[4]) ** 2 + pct(r[5]) ** 2) ** 0.5
        out.append([float(r[0]), float(r[1]) / 1000.0, up, dn])
    return out


def from_twiki_fb_abs(csvname: str) -> list[list[float]]:
    """Rows: mass, sigma[fb], unc[fb] (old NLO+NLL EW pages)."""
    rows = list(csv.reader(open(os.path.join(TW, csvname))))[1:]
    return [[float(r[0]), float(r[1]) / 1e3, float(r[2]) / float(r[1]), float(r[2]) / float(r[1])]
            for r in rows]


def from_hepi(fname: str) -> list[list[float]]:
    """A HEPi table (GPL-3, optional): empty if HEPi has not been fetched."""
    if not os.path.exists(os.path.join(HEPI, fname)):
        return []
    d = json.load(open(os.path.join(HEPI, fname)))["data"]
    out = []
    for k, v in d.items():
        if not isinstance(v, dict) or "xsec_pb" not in v:
            continue
        x = v["xsec_pb"]
        out.append([float(k), x, abs(v.get("unc_up_pb", 0.0)) / x, abs(v.get("unc_down_pb", 0.0)) / x])
    return sorted(out)


def save(name: str, process: str, sqrts: float, order: str, pdf: str, tool: str,
         source: str, data: list[list[float]], note: str = "") -> None:
    doc = {"name": name, "process": process, "sqrts_gev": sqrts, "order": order, "pdf": pdf,
           "tool": tool, "source": source, "note": note,
           "units": {"mass": "GeV", "sigma": "pb", "uncertainties": "relative (fraction of sigma)"},
           "columns": ["mass_gev", "sigma_pb", "rel_unc_up", "rel_unc_down"], "data": data}
    if not data:                                   # an optional source (HEPi) not fetched: no table, no crash
        print(f"{name:42s} skipped: its source is not in the tools folder ({source})")
        return
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        json.dump(doc, f, indent=1)
    print(f"{name:42s} {len(data):4d} rows  {data[0][0]:g}-{data[-1][0]:g} GeV")


if __name__ == "__main__":
    nnllfast = "NNLL-fast 2.0 (Beenakker, Borschensky, Kraemer, Kulesza, Laenen); SciPost Phys. Core 7, 072 (2024)"
    save("13TeV_stop_sbottom_pair_NNLOapprox+NNLL", "pp -> stop stop* (= any single colour-triplet scalar pair, gluinos/squarks decoupled)",
         13000, "NNLOapprox+NNLL", "PDF4LHC21_40_pdfas", nnllfast, TWIKI + "SUSYCrossSections13TeVstopsbottom",
         from_twiki_pct("SUSYCrossSections13TeVstopsbottom__t01.csv"),
         "2024 update; differs by +5-30% from the 2016 PDF4LHC15 numbers still in the fuenfundachtzig/xsec and HEPi pp13_stopsbottom json")
    save("13p6TeV_stop_sbottom_pair_NNLOapprox+NNLL", "pp -> stop stop*", 13600, "NNLOapprox+NNLL",
         "PDF4LHC21_40_pdfas", nnllfast, TWIKI + "SUSYCrossSections13x6TeVstopsbottom",
         from_twiki_pct("SUSYCrossSections13x6TeVstopsbottom__t01.csv"))
    save("13TeV_squark_antisquark_10fold_NNLOapprox+NNLL", "pp -> sq sq* summed over 10 degenerate squarks (uL,uR,dL,dR,sL,sR,cL,cR,bL,bR), gluinos decoupled",
         13000, "NNLOapprox+NNLL", "PDF4LHC21_40_pdfas", nnllfast, TWIKI + "SUSYCrossSections13TeVsquarkantisquark",
         from_twiki_pct("SUSYCrossSections13TeVsquarkantisquark__t01.csv"),
         "Sum over 10 squarks. With gluinos decoupled each flavour is pure QCD pair production: sigma/10 is within 4-5% of the stop table (stop table recommended for a single scalar).")
    for lab, t in (("L", "01"), ("R", "02"), ("LplusR", "03")):
        save(f"13TeV_slepton_{lab}_pair_NLO+NLL", f"pp -> slepton_{lab} slepton_{lab}* (one generation)", 13000, "NLO+NLL",
             "PDF4LHC15", "Resummino 2.0.1", TWIKI + "SUSYCrossSections13TeVslepslep",
             from_twiki_updown(f"SUSYCrossSections13TeVslepslep__t{t}.csv"))
    save("13TeV_slepton_R_pair_aNNLO+NNLL", "pp -> eR eR* (one generation of right-handed sleptons)", 13000,
         "NNLOapprox+NNLL", "PDF4LHC21_40", "Resummino 3.1.2-dev via HEPi", HEPI_URL + "13000_sleptons_2000011_-2000011_NNLL.json",
         from_hepi("13000_sleptons_2000011_-2000011_NNLL.json"))
    save("13TeV_slepton_L_pair_aNNLO+NNLL", "pp -> eL eL* (one generation of left-handed sleptons)", 13000,
         "NNLOapprox+NNLL", "PDF4LHC21_40", "Resummino 3.1.2-dev via HEPi", HEPI_URL + "13000_sleptons_1000011_-1000011_NNLL.json",
         from_hepi("13000_sleptons_1000011_-1000011_NNLL.json"))
    tw13 = TWIKI + "SUSYCrossSections13x0TeVn2x1wino"
    for nm, t, proc in (("C1pN2", "01", "chi2^0 chi1^+"), ("C1mN2", "02", "chi2^0 chi1^-"), ("C1C1", "03", "chi1^+ chi1^-")):
        save(f"13TeV_wino_{nm}_aNNLO+NNLL", f"pp -> {proc} (pure wino, degenerate)", 13000, "NNLOapprox+NNLL", "PDF4LHC21_40",
             "Resummino (Fiaschi, Fuks, Klasen, Neuwirth, EPJC 83 (2023) 707)", tw13,
             from_twiki_fb_scale_pdf(f"SUSYCrossSections13x0TeVn2x1wino__t{t}.csv"))
    save("13TeV_wino_C1pmN2_NLO+NLL", "pp -> chi2^0 chi1^+- (pure wino)", 13000, "NLO+NLL", "CTEQ6.6/MSTW2008 envelope",
         "Resummino", TWIKI + "SUSYCrossSections13TeVn2x1wino", from_twiki_fb_abs("SUSYCrossSections13TeVn2x1wino__t01.csv"))
    save("13TeV_wino_C1C1_NLO+NLL", "pp -> chi1^+ chi1^- (pure wino)", 13000, "NLO+NLL", "CTEQ6.6/MSTW2008 envelope",
         "Resummino", TWIKI + "SUSYCrossSections13TeVx1x1wino", from_twiki_fb_abs("SUSYCrossSections13TeVx1x1wino__t01.csv"))
    tw13h = TWIKI + "SUSYCrossSections13x0TeVhinosplit"
    for nm, t, proc in (("N1C1p", "01", "chi1^0 chi1^+"), ("N1C1m", "02", "chi1^0 chi1^-"),
                        ("C1C1", "03", "chi1^+ chi1^-"), ("N1N2", "04", "chi1^0 chi2^0")):
        save(f"13TeV_higgsino_{nm}_aNNLO+NNLL", f"pp -> {proc} (pure higgsino, fully degenerate)", 13000, "NNLOapprox+NNLL",
             "PDF4LHC21_40", "Resummino (Fiaschi, Fuks, Klasen, Neuwirth 2023)", tw13h,
             from_twiki_fb_scale_pdf(f"SUSYCrossSections13x0TeVhinosplit__t{t}.csv"),
             "N2C1+- equal N1C1+- for a pure higgsino; N1N1 and N2N2 vanish")
    save("13TeV_higgsino_sum_NLO+NLL", "sum N1N2 + N1C1 + N2C1 + C1C1 (pure higgsino, degenerate)", 13000, "NLO+NLL",
         "PDF4LHC (envelope)", "Resummino", TWIKI + "SUSYCrossSections13TeVhino",
         from_twiki_fb_abs("SUSYCrossSections13TeVhino__t01.csv"))

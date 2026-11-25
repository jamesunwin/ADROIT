"""Download the LHC Higgs WG (YR4) BSM 13 TeV cross sections and extract JSON tables.

Source: https://twiki.cern.ch/twiki/pub/LHCPhysics/LHCHWG/Higgs_XSBR_YR4_update.xlsx
(linked from https://twiki.cern.ch/twiki/bin/view/LHCPhysics/CERNYellowReportPageBSMAt13TeV),
sheet 'YR4 BSM 13TeV'; reference: LHC Higgs XS WG, CERN Yellow Report 4,
CERN-2017-002-M, arXiv:1610.07922.

Writes into ~/agentic-dm-tools/hxswg/:
  hxswg_yr4_bsm13_ggF_pointlike_N3LO.json      (heavy-top EFT, N3LO, mu = M/2, PDF4LHC15_nnlo_100)
  hxswg_yr4_bsm13_ggF_quarkloop_NNLO_NNLL.json (t, b, c loops like the SM Higgs, NNLO+NNLL, NWA,
                                                 mu = M, PDF4LHC15_nnlo_30, with 1+delta_EW)
  hxswg_yr4_bsm13_all_processes.json           (ggF, VBF, WH, ZH, ttH, bbH, tH columns)
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from xlsx_min import read_sheet

URL = "https://twiki.cern.ch/twiki/pub/LHCPhysics/LHCHWG/Higgs_XSBR_YR4_update.xlsx"
OUT = Path.home() / "agentic-dm-tools/hxswg"
SHEET = "YR4 BSM 13TeV"
REF = ("LHC Higgs Cross Section Working Group, D. de Florian et al., 'Handbook of LHC Higgs Cross "
       "Sections: 4. Deciphering the Nature of the Higgs Sector', CERN-2017-002-M, arXiv:1610.07922")
LICENCE = ("YR4 (arXiv:1610.07922, CERN-2017-002-M, DOI 10.23731/CYRM-2017-002) is distributed under "
           "CC BY 4.0 (arXiv licence); the twiki spreadsheet itself carries no separate licence statement - "
           "cite YR4 and the twiki page.")

# column blocks in the sheet (0-based column of the 'MH' cell) and their sub-columns
BLOCKS = {
    "ggF_pointlike_N3LO": (0, ["mass_gev", "sigma_pb", "theory_up_pct", "theory_down_pct",
                               "theory_gauss_pct", "pdf_alphas_pct"]),
    "ggF_quarkloop_NNLO_NNLL": (7, ["mass_gev", "sigma_pb", "scale_up_pct", "scale_down_pct",
                                    "pdf_alphas_pct", "pdf_pct", "alphas_pct", "one_plus_delta_EW"]),
    "VBF": (16, ["mass_gev", "sigma_pb", "scale_up_pct", "scale_down_pct", "pdf_alphas_pct",
                 "pdf_pct", "alphas_pct", "one_plus_delta_EW"]),
    "WH": (25, ["mass_gev", "sigma_pb", "scale_up_pct", "scale_down_pct", "pdf_alphas_pct",
                "pdf_pct", "alphas_pct", "one_plus_delta_EW", "sigma_WplusH_pb", "sigma_WminusH_pb"]),
    "ZH": (36, ["mass_gev", "sigma_pb", "scale_up_pct", "scale_down_pct", "pdf_alphas_pct",
                "pdf_pct", "alphas_pct", "one_plus_delta_EW", "sigma_ggZH_pb"]),
    "ttH": (46, ["mass_gev", "sigma_pb", "scale_up_pct", "scale_down_pct", "pdf_alphas_pct",
                 "pdf_pct", "alphas_pct", "one_plus_delta_EW"]),
    "bbH": (55, ["mass_gev", "sigma_pb", "scale_up_pct", "scale_down_pct", "pdf_alphas_pct",
                 "pdf_pct", "alphas_pct", "one_plus_delta_EW"]),
}

NOTES = {
    "ggF_pointlike_N3LO": ("Scalar S with point-like ggS operator equal to the SM Higgs-gluon one in the "
                           "heavy-top limit; N3LO QCD, no quark-mass or EW effects; mu_F = mu_R = M/2 "
                           "varied in [M/4, M]; PDF4LHC15_nnlo_100; narrow width."),
    "ggF_quarkloop_NNLO_NNLL": ("Scalar coupling to gluons through top and bottom (and charm) loops exactly "
                                "like the SM Higgs; t/b mass effects up to NLO, higher orders in the heavy-top "
                                "limit; NNLO+NNLL QCD; narrow width (NWA, not CPS); mu = M; PDF4LHC15_nnlo_30. "
                                "NLO EW factor 1+delta_EW given separately (0 = not provided) for 100-2500 GeV. "
                                "Use for a Higgs-mixed singlet: sigma(gg->H) = sin^2(theta) * sigma(M)."),
}


def main() -> None:
    """Download (if needed) and convert the spreadsheet."""
    OUT.mkdir(parents=True, exist_ok=True)
    xlsx = OUT / "Higgs_XSBR_YR4_update.xlsx"
    if not xlsx.exists():
        urllib.request.urlretrieve(URL, xlsx)
    rows = read_sheet(str(xlsx), SHEET)
    every = {}
    for name, (c0, cols) in BLOCKS.items():
        data = []
        for r in rows[5:]:
            if len(r) <= c0 or not isinstance(r[c0], float):
                continue
            vals = []
            for k, col in enumerate(cols):
                if col is None:
                    continue
                v = r[c0 + k] if c0 + k < len(r) else ""
                vals.append(v if isinstance(v, float) else None)
            data.append(vals)
        columns = [c for c in cols if c is not None]
        every[name] = {"columns": columns, "data": data}
        if name in NOTES:
            doc = {"name": f"hxswg_yr4_bsm13_{name}", "sqrts_gev": 13000, "source": URL,
                   "sheet": SHEET, "reference": REF, "licence": LICENCE, "note": NOTES[name],
                   "units": {"mass": "GeV", "sigma": "pb", "uncertainties": "percent"},
                   "columns": columns, "data": data}
            (OUT / f"hxswg_yr4_bsm13_{name}.json").write_text(json.dumps(doc, indent=1))
    doc = {"name": "hxswg_yr4_bsm13_all_processes", "sqrts_gev": 13000, "source": URL,
           "sheet": SHEET, "reference": REF, "licence": LICENCE, "notes": NOTES,
           "units": {"mass": "GeV", "sigma": "pb", "uncertainties": "percent"}, "blocks": every}
    (OUT / "hxswg_yr4_bsm13_all_processes.json").write_text(json.dumps(doc, indent=1))
    print("wrote", sorted(p.name for p in OUT.glob("hxswg_*.json")))


if __name__ == "__main__":
    main()

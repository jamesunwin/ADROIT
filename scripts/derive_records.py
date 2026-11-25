"""Derive the bundled data files of the portal library's search records from their public sources.

Run once by hand (not by the tests): ``uv run --with parton==0.2.2 python scripts/derive_records.py SOURCES``,
or ``uv run python scripts/derive_records.py --dilepton-limits SOURCES`` to add only the dilepton limits at full
resolution (2026-10-10, R4: every one of HEPData's 1,101 masses, ``limits_full``, beside the subsampled σ rows),
with SOURCES a folder holding the HEPData downloads named below, and the PDF set PDF4LHC21_40
in ``<tools>/lhapdf``. Every output names its source; the HEPData records are CC0 (ATLAS) or
CC BY 4.0 (Belle II, attributed in its record).

Outputs, in adroit/constraints/data/digitised/:
- atlas_1903.06248_dilepton.yaml: ATLAS's fiducial σB limits (139 fb⁻¹) for six relative widths,
  every 5th mass; the Z′_SSM fiducial σB that ATLAS's own ratio table implies (limit at 3% width
  ÷ the ratio); and our leading-order σ(pp → Z′) at 13 TeV for B − L with g = 1 and for the SSM
  (narrow width, PDF4LHC21_40), so that σB(B − L) = g² σ_LO(B − L) BR_ℓℓ × σ_fid,SSM / (σ_LO,SSM BR_ℓℓ,SSM).
- atlas_2010.14293_squark.yaml: the observed contour for one non-degenerate light-flavour squark.
- belle2_2212.03066_invisible_zprime.yaml: g′ limits (90% CL) for the fully invisible L_μ − L_τ Z′.
- atlas_2306.00641_2hdma.yaml: the observed (m_a, m_A) exclusion boundary of the 2HDM+a (sin θ = 0.35).
"""

from __future__ import annotations

import csv
import io
import math
import sys
from pathlib import Path

import numpy as np
import yaml

OUT = Path(__file__).resolve().parents[1] / "adroit/constraints/data/digitised"
S = 13000.0 ** 2
GEV2_TO_FB = 0.3894e12
SW2, G_Z = 0.2312, 0.7434


def blocks(path: Path) -> list[tuple[dict, list[list[str]]]]:
    """HEPData CSV: (header qualifiers, rows) of each block."""
    out, head, rows = [], {}, []
    for line in path.read_text().splitlines():
        if line.startswith("#:"):
            if rows:
                out.append((head, rows))
                head, rows = {}, []
            key, _, value = line[3:].partition(",")
            head[key.strip()] = value.strip()
        elif line.strip() and not line.startswith(("#", "$")) and not line[0].isalpha():
            rows.append(next(csv.reader(io.StringIO(line))))
    if rows:
        out.append((head, rows))
    return out


def dilepton(src: Path) -> dict:
    from parton import PLumi, mkPDF
    from adroit.core.config import get_settings
    limits = {}
    for head, rows in blocks(src / "Observeddileptoncross-sectionlimits.csv"):
        limits[float(head["RELATIVE WIDTH [%]"])] = {float(r[0]): float(r[1]) for r in rows}
    ratio_blocks = [b for b in blocks(src / "RatioofobservedlimitstoSSMcrosssection.csv")
                    if b[0].get("EE LUMINOSITY [fb$^{-1}$]") == "139"]
    ratio = {1e3 * float(r[0]): float(r[1]) for r in ratio_blocks[0][1] if r[1].strip() not in ("-", "")}
    masses = sorted(limits[0.0])[::5]
    pdf = mkPDF("PDF4LHC21_40", 0, pdfdir=str(get_settings().tools_dir / "lhapdf"))
    ferm = {"u": (0.5, 2 / 3), "d": (-0.5, -1 / 3)}

    def ssm_width(t3: float, q: float, nc: int, m: float) -> float:
        return nc * G_Z ** 2 * m * ((t3 - 2 * q * SW2) ** 2 + t3 ** 2) / (48 * math.pi)

    def sigma(m: float, width_of) -> float:
        lumi, total = PLumi(pdf, Q2=m * m), 0.0
        for pid, q in ((2, "u"), (4, "u"), (1, "d"), (3, "d"), (5, "d")):
            total += 4 * math.pi ** 2 / 3 * width_of(q, m) / m / S * (lumi.L(pid, -pid, m * m / S) + lumi.L(-pid, pid, m * m / S))
        return total * GEV2_TO_FB

    rows = []
    rm = np.array(sorted(ratio))
    rv = np.array([ratio[k] for k in rm])
    for m in masses:
        sig_bl = sigma(m, lambda q, mm: mm / (36 * math.pi))          # B − L, g = 1: Γ_qq̄ = g²M/36π
        sig_ssm = sigma(m, lambda q, mm: ssm_width(*ferm[q], 3, mm))
        top = 3 * G_Z ** 2 * m / (48 * math.pi) * math.sqrt(max(1 - 4 * 172.5 ** 2 / m ** 2, 0)) * \
            ((0.5 - 4 / 3 * SW2) ** 2 * (1 + 2 * 172.5 ** 2 / m ** 2) + 0.25 * (1 - 4 * 172.5 ** 2 / m ** 2))
        total = (2 * ssm_width(0.5, 2 / 3, 3, m) + 3 * ssm_width(-0.5, -1 / 3, 3, m) + 3 * ssm_width(-0.5, -1, 1, m)
                 + 3 * ssm_width(0.5, 0, 1, m) + top)
        br_ssm = ssm_width(-0.5, -1, 1, m) / total
        fid = limits[3.0][m] / float(np.interp(m / 1e3 * 1e3, rm, rv)) if rm[0] <= m <= rm[-1] else None
        values = [m, *(limits[w][m] for w in sorted(limits)), sig_bl, sig_ssm * br_ssm, fid]
        rows.append([None if v is None else float(f"{float(v):.6g}") for v in values])
    ratios = [r[-1] / r[-2] for r in rows if r[-1] is not None and 1000.0 <= r[0] <= 5000.0]
    correction = float(f"{float(np.median(ratios)):.4g}")
    return {"correction_fid_over_lo": correction,
            "correction_note": "the median over 1–5 TeV of ATLAS's implied fiducial Z′_SSM σB over our leading-order "
                               "SSM σB (below 1 TeV the two tables' sampling makes the ratio noisy)",
            "source": "ATLAS, arXiv:1903.06248 (PLB 796 (2019) 68), HEPData ins1725190 v3 (CC0): tables "
                      "'Observed dilepton cross-section limits' and 'Ratio of observed limits to SSM cross section' "
                      "(139 fb⁻¹, 3% width); leading-order cross-sections ours (PDF4LHC21_40, parton 0.2.2)",
            "columns": ["mass_gev", *(f"limit_fb_width_{w:g}pct" for w in sorted(limits)), "sigma_lo_bl_g1_fb",
                        "sigma_br_lo_ssm_fb", "sigma_br_fid_ssm_fb"],
            "widths_pct": sorted(limits), "rows": rows}


def squark(src: Path) -> dict:
    (_, rows), = blocks(src / "Obs.Contour2.csv")
    return {"source": "ATLAS, arXiv:2010.14293 (JHEP 02 (2021) 143), HEPData ins1827025 v2 (CC0), table 'Obs.Contour 2': "
                      "one non-degenerate light-flavour squark, q̃ → q χ̃₁⁰, 139 fb⁻¹, 95% CL (nominal observed line)",
            "columns": ["m_squark_gev", "m_lsp_gev"], "points": [[float(a), float(b)] for a, b in rows]}


def belle(src: Path) -> dict:
    data = yaml.safe_load((src / "fig._3_(top_left).yaml").read_text())
    deps = data["dependent_variables"]                # the record stores the mass as a dependent variable
    mass, = [d for d in deps if "M_{Z" in d["header"]["name"]]
    values = [v["value"] for v in mass["values"]]
    observed, = [d for d in deps if d["header"]["name"].strip() == "$g'$, Observed"]
    limits = [v["value"] for v in observed["values"]]
    return {"source": "Belle II, arXiv:2212.03066 (PRL 130 (2023) 231801), HEPData ins2611344 v1 ("
                      "CC0 on HEPData), Fig. 3 (top left): g′ at 90% CL, fully invisible L_μ − L_τ Z′, "
                      "negligible width",
            "columns": ["m_zprime_gev", "g_prime"], "points": [[float(m), float(g)] for m, g in zip(values, limits)]}


def two_hdma(src: Path) -> dict:
    (_, rows), = blocks(src / "figure_4a_Obs.csv")
    return {"source": "ATLAS, arXiv:2306.00641 (Sci. Bull. 69 (2024) 3005), HEPData ins2664553 v1 (CC0), "
                      "'Figure 4a (Observed)': scenario 1a, sin θ = 0.35, tan β = 1, m_χ = 10 GeV, y_χ = 1, "
                      "m_A = m_H = m_H±, λ₃ = λ_P1 = λ_P2 = 3; excluded inside the contour closed along the plane's "
                      "lower edge (it folds back at m_a ≈ 470–558 GeV)",
            "columns": ["m_a_gev", "m_A_gev"], "points": [[float(a), float(b)] for a, b in rows]}


def dilepton_limits_full(src: Path) -> dict[str, list[list[float]]]:
    """Every observed limit of the HEPData table, {relative width (%): [[mass, limit (fb)], ...]}."""
    out = {}
    for head, rows in blocks(src / "ins1725190_Observed_dilepton_cross-section_limits.csv"):
        out[f"{float(head['RELATIVE WIDTH [%]']):g}"] = [[float(r[0]), float(r[1])] for r in rows]
    return out


if __name__ == "__main__" and sys.argv[1] == "--dilepton-limits":
    target = OUT / "atlas_1903.06248_dilepton.yaml"
    content = yaml.safe_load(target.read_text())
    content["limits_full"] = dilepton_limits_full(Path(sys.argv[2]))
    content["limits_full_note"] = ("every observed limit of HEPData ins1725190 v3 'Observed dilepton cross-section "
                                   "limits' (1,101 masses per width); the rows keep every 5th mass for the σ columns")
    target.write_text(yaml.safe_dump(content, sort_keys=False, width=120))
    print(f"added limits_full to {target.name}")
elif __name__ == "__main__":
    root = Path(sys.argv[1])
    outputs = {"atlas_1903.06248_dilepton.yaml": dilepton(root / "atlas_1903.06248"),
               "atlas_2010.14293_squark.yaml": squark(root / "atlas_2010.14293"),
               "belle2_2212.03066_invisible_zprime.yaml": belle(root / "belle2_2212.03066"),
               "atlas_2306.00641_2hdma.yaml": two_hdma(root / "atlas_2306.00641")}
    for name, content in outputs.items():
        (OUT / name).write_text(yaml.safe_dump(content, sort_keys=False, allow_unicode=True, width=120))
        print("wrote", name)

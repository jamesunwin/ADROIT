"""The 2HDM+a mono-Z beyond ATLAS's benchmarks: the full loop-induced gg → Z a in MadGraph (docs/benchmark_limits.md).

ATLAS publishes mono-Z contours only at its benchmark couplings (sin θ = 0.35 and 0.7, tan β = 1, λ's = 3;
arXiv:2111.08372). ADROIT compares a point there with the contour's reference by their resonant rates
σ(gg → H) BR(H → a Z) BR(a → χχ̄) (``resonances.monoz``). Away from the benchmarks ATLAS's full signal also has
the top-quark boxes, interfering with the H s-channel, whose share changes with the couplings (there is no s-channel
A or a: CP forbids a Z a a or Z A a vertex). This script computes the full σ(gg → Z a) (a narrow, so × BR(a → χχ̄)
for Z χχ̄) with MG5 on a grid of (sin θ, tan β) at nodes of ATLAS's plane where H is narrow, with ADROIT's two-body
widths, as ``monoh_calibration`` does for mono-h. The s-channel h₁ is excluded (``/ h1``): its h₁ Z a vertex is
∝ cos(β − α) sin θ = 0 in the alignment limit, so it vanishes identically, but its empty integration channel stalled
MadLoop (three points past 20 minutes each, 2026-10-12), as the s-channel Z did for mono-h. The shift of the
resonant-to-full ratio relative to each contour's benchmark,

    s_P(θ, β) = [σ_res(θ, β)/σ_res(P)] / [σB_MG(θ, β)/σB_MG(P)],    P = (0.35, 1) or (0.7, 1),

with σB = σ(gg → Z a) BR(a → χχ̄) (ADROIT's BR at the same point: the narrow-a factorisation, as for mono-h),

turns the monotone rule into: excluded inside contour P if σ_res/σ_res(P) ≥ max s_P; allowed outside it if
σ_res/σ_res(P) ≤ min s_P; otherwise undecided.

    nice -n 10 uv run python scripts/madgraph_xsec/monoz_calibration.py [--summarize]       # about 3 h; $0
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import monoh_calibration as mh  # noqa: E402
from mgxsec_common import UFO_DIR, WORK_DIR, generate_process  # noqa: E402

# MadGraph rewrites a model's pickles when it imports it; a copy under work/ keeps that out of the UFO folder, which
# Track 1's run identity covers (a scan running alongside would otherwise stop with a checkpoint mismatch)
MODEL = WORK_DIR / "ufo_copy" / "Pseudoscalar_2HDM"

# (m_H = m_A = m_H±, m_a) nodes inside both of ATLAS's contours with H narrow at both benchmarks (Γ_H/m_H ≤ 9%),
# and (800, 300), narrow at sin θ = 0.35 only
NODES = [(500.0, 150.0), (600.0, 200.0), (700.0, 250.0), (800.0, 300.0)]
BENCHMARKS = [(0.35, 1.0), (0.7, 1.0)]
SIN_THETA = [0.2, 0.35, 0.5, 0.7]
TAN_BETA = [1.0, 2.0, 3.0, 5.0]
OUT = WORK_DIR / "monoz_calibration_za.json"
SUMMARY = mh.ROOT / "docs" / "monoz" / "calibration.json"


def key_of(m_big: float, m_a: float, sin_theta: float, tan_beta: float) -> str:
    return f"Z {m_big:g} {m_a:g} {sin_theta:g} {tan_beta:g}"


def narrow_h(m_big: float, m_a: float, sin_theta: float, tan_beta: float) -> bool:
    """Whether ADROIT treats H as narrow there (only then does the mono-Z rule apply)."""
    from adroit.parameter_space import resonances as rs
    cls, p = mh.point(m_big, m_a, sin_theta, tan_beta)
    return rs._relative_width(cls.model(p), "h2") <= rs.NARROW_2HDMA


def summarize(done: dict) -> int:
    """docs/monoz/calibration.json: per point the MG σ, ADROIT's resonant σ and the shift for each benchmark."""
    from adroit.parameter_space import resonances as rs
    rows, cells = [], {}
    for key, r in sorted(done.items()):
        if not r.get("sigma_pb"):
            continue
        node = (r["mh3"], r["mh4"])
        cls, p = mh.point(*node, r["sinp"], r["tanbeta"])
        resonant, br = rs._resonant_rates(cls, p)["Z"], mh.invisible(cls, p)
        row = {"key": key, "m_H": node[0], "m_a": node[1], "sin_theta": r["sinp"], "tan_beta": r["tanbeta"],
               "full_mg_pb": r["sigma_pb"], "br_a_invisible": br, "resonant_pb": resonant,
               "narrow_H": narrow_h(*node, r["sinp"], r["tanbeta"])}
        for plane in BENCHMARKS:
            bench = done.get(key_of(*node, *plane))
            if bench and bench.get("sigma_pb") and narrow_h(*node, *plane):
                cls0, p0 = mh.point(*node, *plane)
                full_ratio = (r["sigma_pb"] * br) / (bench["sigma_pb"] * mh.invisible(cls0, p0))
                row[f"shift_{plane[0]:g}"] = (resonant / rs._resonant_rates(cls0, p0)["Z"]) / full_ratio
                if row["narrow_H"]:
                    cell = cells.setdefault((plane[0], r["sinp"], r["tanbeta"]), [])
                    cell.append(row[f"shift_{plane[0]:g}"])
        rows.append(row)
    shifts = {f"{k[0]:g}": {} for k in cells}
    for (plane, st, tb), values in cells.items():
        shifts[f"{plane:g}"][f"{st:g},{tb:g}"] = [min(values), max(values), len(values)]
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps({"shift_range": shifts, "rows": rows}, indent=1, ensure_ascii=False))
    for plane, table in shifts.items():
        print(f"SHIFTS_Z[{plane}] =", {k: (round(v[0], 3), round(v[1], 3)) for k, v in sorted(table.items())})
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args(argv)
    mh.OUT = OUT                                                   # mh.run writes its results here
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    if args.summarize:
        return summarize(done)
    if not MODEL.is_dir():
        shutil.copytree(UFO_DIR / "Pseudoscalar_2HDM", MODEL)
    procdir = generate_process("thdma_monoz_za_noh1", str(MODEL), ["g g > z h4 / h1 [noborn=QCD]"],
                               pre_commands=["set ninja None --no_save", "set collier None --no_save"])
    for sin_theta in SIN_THETA:
        for tan_beta in TAN_BETA:
            for m_big, m_a in NODES:
                if (sin_theta, tan_beta) in BENCHMARKS or narrow_h(m_big, m_a, sin_theta, tan_beta):
                    mh.run(procdir, done, key_of(m_big, m_a, sin_theta, tan_beta),
                           mh.params(m_big, m_a, sin_theta, tan_beta))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

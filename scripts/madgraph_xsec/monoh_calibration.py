"""The 2HDM+a mono-Higgs calibration beyond ATLAS's benchmark: the full loop-induced gg → h a in MadGraph.

ADROIT compares its resonant mono-h rate, σ(gg → A) BR(A → a h) BR(a → χχ̄), with ATLAS's σ95 (arXiv:2108.13391).
ATLAS's full benchmark σ includes non-resonant diagrams, so the comparison is decided only outside the band of
resonant/full ratios (``resonances.RESONANT_OVER_FULL``), calibrated at ATLAS's benchmark (sin θ = 0.35,
tan β = 1). This script computes the full σ away from it with MG5 (Pseudoscalar_2HDM UFO).

**The process.** ATLAS generated g g > h1 xd xd~ [noborn=QCD]; with CutTools as the only loop library that took
over 20 minutes per survey channel (eleven channels, then refinement), days for a grid. Since a is narrow
(Γ_a/m_a ≈ 3–4% here), χχ̄ comes from an on-shell a and σ(gg → h χχ̄) = σ(gg → h a) BR(a → χχ̄) up to the
off-shell A* → χχ̄ diagrams (suppressed by m_A ≫ √ŝ − m_h). So the script runs g g > h1 h4 [noborn=QCD], which
keeps every h a diagram (the A and a s-channels and the box) and their interference. The s-channel Z is excluded
(``/ z``): its Z h a vertex is ∝ cos(β − α) = 0 in the alignment limit, so it vanishes identically, but its empty
integration channel stalled MadLoop at some points (2026-10-12; the points before then, with it, are unchanged).
MadGraph's σ(gg → h a) is multiplied by ADROIT's BR(a → χχ̄) at the same point (the narrow-a factorisation), so that
it is the full rate of the final state ATLAS sees, as ADROIT's resonant σ is; the benchmark nodes check it against
ATLAS's full σ.

``--summarize`` compares ADROIT's resonant σ with the full σ. PDF and scale choices are made to cancel: at each
node the full σ is ATLAS's benchmark σ times MadGraph's σB(sin θ, tan β)/σB(0.35, 1), with σB = σ(gg → h a)
BR(a → χχ̄), so the shift of the resonant-to-full ratio away from the benchmark is the double ratio

    s = [σ_res(θ, β)/σ_res(0.35, 1)] / [σB_MG(θ, β)/σB_MG(0.35, 1)].

(Before 2026-10-12 the denominator lacked the BRs, so s carried BR(θ, β)/BR(0.35, 1), 0.97–1.03 on the grid.)

and the calibrated band is (0.4189 min s, 1.2400 max s) over the narrow-A points run. Points where ADROIT finds A
broad (Γ_A/m_A > 10%) are not run: the rule leaves them undecided whatever the band. Writes
<tools>/madgraph-xsec/work/monoh_calibration_ha.json (each run; work/ is outside Track 1's fingerprint of the tables) and docs/monoh/calibration.json (the summary).

Run from the repository root, at low priority (one MadEvent job at a time, $0):

    nice -n 10 uv run python scripts/madgraph_xsec/monoh_calibration.py [--validate-only | --summarize]
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from mgxsec_common import UFO_DIR, WORK_DIR, generate_process, launch_point  # noqa: E402

BASE = {"sinbma": 1.0, "lam3": 3.0, "laP1": 3.0, "laP2": 3.0, "mh1": 125.0, "MXd": 10.0, "gPXd": 1.0,
        "MT": 172.0, "MB": 4.7, "ymt": 172.0, "ymb": 4.7}
WIDTHS = {"wh2": "h2", "wh3": "h3", "wh4": "h4", "whc": "h+"}     # MG's width parameter: ADROIT's particle
# ATLAS's narrow-A nodes (Γ_A/m_A ≤ 10% at its benchmark), spanning m_A 600–1200 GeV and m_a 150–300 GeV. Heavier
# A is broad at the benchmark; (1500, 400) also stalled in CutTools' quadruple-precision rescue (m_a > 2 m_t).
VALIDATION_NODES = [(600.0, 250.0), (1000.0, 300.0), (1200.0, 300.0), (800.0, 150.0)]
GRID_NODES = VALIDATION_NODES
POINT_TIMEOUT = 1200.0            # s; a point that takes longer is recorded as failed and skipped
SIN_THETA = [0.2, 0.35, 0.5, 0.7]
TAN_BETA = [1.0, 2.0, 3.0, 5.0]
OUT = WORK_DIR / "monoh_calibration_ha.json"       # in work/: outside the tables Track 1 fingerprints
SUMMARY = ROOT / "docs" / "monoh" / "calibration.json"
BENCHMARK = (0.35, 1.0)


def params(m_big: float, m_a: float, sin_theta: float, tan_beta: float) -> dict:
    """MG's parameters, with ADROIT's two-body total widths (GeV): its resonant σ uses them, so the resonant and
    full σ share Γ_A and their ratio measures the non-resonant diagrams alone. (MadWidth's "auto" widths also
    went to 3- and 4-body decays, minutes per point.)"""
    from adroit.parameter_space import resonances as rs
    cls, p = point(m_big, m_a, sin_theta, tan_beta)
    model = cls.model(p)
    widths = {w: rs._relative_width(model, n) * model.particles[n].mass for w, n in WIDTHS.items()}
    return dict(BASE, mh2=m_big, mh3=m_big, mhc=m_big, mh4=m_a, sinp=sin_theta, tanbeta=tan_beta, **widths)


def key_of(m_big: float, m_a: float, sin_theta: float, tan_beta: float) -> str:
    """The results' key; ATLAS's benchmark (sin θ, tan β) is the validation run itself."""
    kind = "bench" if (sin_theta, tan_beta) == BENCHMARK else "grid"
    return f"{kind} {m_big:g} {m_a:g} {sin_theta:g} {tan_beta:g}"


def survey_sigma(procdir: Path, since: float) -> tuple[float, float]:
    """σ and its error (pb), summed over the survey's channels (every G*/results.dat, written after ``since``)."""
    files = list(procdir.glob("SubProcesses/P*/G*/results.dat"))
    if not files or any(f.stat().st_mtime < since for f in files):
        raise RuntimeError(f"the survey did not complete in {procdir}")
    values = [tuple(float(x) for x in f.read_text().split()[:2]) for f in files]
    return sum(v for v, _ in values), math.sqrt(sum(e * e for _, e in values))


def stop_surveys(procdir: Path) -> None:
    """Kill the survey jobs a timed-out MG5 call leaves behind (madevent is a child of survey.sh)."""
    found = subprocess.run(["pgrep", "-f", f"{procdir}/SubProcesses/survey.sh"], capture_output=True, text=True)
    for pid in found.stdout.split():
        subprocess.run(["pkill", "-P", pid], check=False)
        subprocess.run(["kill", pid], check=False)
    (procdir / "RunWeb").unlink(missing_ok=True)


def run(procdir: Path, done: dict, key: str, values: dict) -> dict:
    """One point: σ from the survey alone (0.3–0.5% here). MG 3.8.0's refine asserts on the channel whose
    multichannel weight vanishes identically (the s-channel Z: its Z h a vertex ∝ cos(β − α) = 0 in the alignment
    limit), so it is not relied on."""
    if key in done:
        return done[key]
    t = time.time()
    try:
        result = launch_point(procdir, values, {"nevents": 100}, tag=key.replace(" ", "_"), timeout=POINT_TIMEOUT)
        result = {"refined_sigma_pb": result["sigma_pb"], "refined_sigma_err_pb": result["sigma_err_pb"]}
    except RuntimeError:
        result = {}
    except subprocess.TimeoutExpired:
        stop_surveys(procdir)
        result = {}
    for events in (procdir / "Events").glob("run_*"):
        shutil.rmtree(events, ignore_errors=True)
    try:
        result["sigma_pb"], result["sigma_err_pb"] = survey_sigma(procdir, t)
    except RuntimeError as error:
        result["failed"] = str(error)
    result["wall_s"] = round(time.time() - t, 1)
    done[key] = {**result, **{k: values[k] for k in ("mh3", "mh4", "sinp", "tanbeta")}}
    OUT.write_text(json.dumps(done, indent=1))
    print(key, result, flush=True)
    return done[key]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args(argv)
    if args.summarize:
        return summarize(json.loads(OUT.read_text()))
    procdir = generate_process("thdma_monoh_ha_noz", str(UFO_DIR / "Pseudoscalar_2HDM"),
                               ["g g > h1 h4 / z [noborn=QCD]"],
                               pre_commands=["set ninja None --no_save", "set collier None --no_save"])
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    for m_big, m_a in VALIDATION_NODES:
        run(procdir, done, key_of(m_big, m_a, *BENCHMARK), params(m_big, m_a, *BENCHMARK))
    if args.validate_only:
        return 0
    for sin_theta in SIN_THETA:
        for tan_beta in TAN_BETA:
            for m_big, m_a in GRID_NODES:
                if not narrow(m_big, m_a, sin_theta, tan_beta):
                    continue
                run(procdir, done, key_of(m_big, m_a, sin_theta, tan_beta), params(m_big, m_a, sin_theta, tan_beta))
    return 0


def point(m_big: float, m_a: float, sin_theta: float, tan_beta: float):
    """ADROIT's 2HDM+a at a calibration point: m_H = m_A = m_H±, m_χ = 10 GeV, y_χ = 1, λ's = 3."""
    sys.path.insert(0, str(ROOT))
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.library import TWO_HDM_A
    heavy = {k: repr(float(m_big)) for k in ("mh2", "mh3", "mhc")}
    cls = TWO_HDM_A.model_copy(update={"parameters": {**TWO_HDM_A.parameters, **heavy}})
    return cls, Point(m_chi=10.0, m_med=m_a, g_chi=1.0, g_q=sin_theta, g_l=tan_beta)


def narrow(m_big: float, m_a: float, sin_theta: float, tan_beta: float) -> bool:
    """Whether ADROIT treats A as narrow there (only then does the mono-h rule use the band)."""
    from adroit.parameter_space import resonances as rs
    cls, p = point(m_big, m_a, sin_theta, tan_beta)
    return rs._relative_width(cls.model(p), "h3") <= rs.NARROW_2HDMA


def invisible(cls, p) -> float:
    """ADROIT's BR(a → χχ̄) at the point."""
    from adroit.parameter_space import resonances as rs
    model = cls.model(p)
    return rs._branching(model, "h4", {abs(model.particles[cls.dm].pdg)})


def rows_of(done: dict) -> list[dict]:
    """Per point: MadGraph's full σ, ADROIT's resonant σ, A's width and the double ratio s (module docstring)."""
    from adroit.constraints import searches as s
    from adroit.parameter_space import resonances as rs
    atlas = {(r[0], r[1]): r[2] for r in s._bundled("atlas-2108.13391-monoh")["benchmark_sigma"]}
    rows = []
    for key, r in sorted(done.items()):
        if "sigma_pb" not in r or not r["sigma_pb"]:
            continue
        node = (r["mh3"], r["mh4"])
        bench = done.get(key_of(*node, *BENCHMARK))
        cls, p = point(*node, r["sinp"], r["tanbeta"])
        cls0, p0 = point(*node, *BENCHMARK)
        resonant, resonant0 = rs._resonant_rates(cls, p)["h"], rs._resonant_rates(cls0, p0)["h"]
        br, br0 = invisible(cls, p), invisible(cls0, p0)
        row = {"key": key, "m_A": node[0], "m_a": node[1], "sin_theta": r["sinp"], "tan_beta": r["tanbeta"],
               "full_mg_pb": r["sigma_pb"], "full_mg_err_pb": r.get("sigma_err_pb"), "resonant_pb": resonant,
               "width_over_mass_A": rs._relative_width(cls.model(p), "h3")}
        row["narrow_A"] = row["width_over_mass_A"] <= rs.NARROW_2HDMA
        if node in atlas:
            row["atlas_benchmark_fb"] = atlas[node]
            if bench:
                full = 1e-3 * atlas[node] * (r["sigma_pb"] * br) / (bench["sigma_pb"] * br0)
                row["resonant_over_full"] = resonant / full
                row["shift"] = (resonant / resonant0) / ((r["sigma_pb"] * br) / (bench["sigma_pb"] * br0))
            if key == key_of(*node, *BENCHMARK):
                row["mg_over_atlas"] = 1e3 * r["sigma_pb"] * br / atlas[node]
        row["br_a_invisible"] = br
        rows.append(row)
    return rows


def summarize(done: dict) -> int:
    """Write docs/monoh/calibration.json: every point, and the band widened by the narrow-A shifts."""
    from adroit.parameter_space import resonances as rs
    rows = rows_of(done)
    narrow_rows = [r for r in rows if r.get("narrow_A") and "shift" in r]
    shifts = [r["shift"] for r in narrow_rows]
    low, high = rs.RESONANT_OVER_FULL
    band = [low * min(shifts + [1.0]), high * max(shifts + [1.0])]
    cells = {}
    for r in narrow_rows:
        cell = cells.setdefault((r["sin_theta"], r["tan_beta"]), [r["shift"], r["shift"], 0])
        cell[0], cell[1], cell[2] = min(cell[0], r["shift"]), max(cell[1], r["shift"]), cell[2] + 1
    out = {"benchmark_band": [low, high], "calibrated_band": band, "points": len(rows), "narrow_points": len(shifts),
           "sin_theta": sorted({r["sin_theta"] for r in rows}), "tan_beta": sorted({r["tan_beta"] for r in rows}),
           "shift_range": [{"sin_theta": k[0], "tan_beta": k[1], "min": v[0], "max": v[1], "nodes": v[2]}
                           for k, v in sorted(cells.items())],
           "rows": rows}
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for r in rows:
        print(f"{r['key']:28s} MG(h a) {r['full_mg_pb']:.4g} pb  res {r['resonant_pb']:.4g} pb  Γ/m {r['width_over_mass_A']:.3f}"
              f"  s {r.get('shift', float('nan')):.3f}  MG/ATLAS {r.get('mg_over_atlas', float('nan')):.3f}")
    print(f"band {band[0]:.4f}–{band[1]:.4f} from {len(shifts)} narrow-A points")
    print("SHIFTS = {" + ", ".join(f"({k[0]:g}, {k[1]:g}): ({v[0]:.3f}, {v[1]:.3f})" for k, v in sorted(cells.items()))
          + "}")
    print("σ(gg → h a) BR(a → χχ̄) / ATLAS's full σ at the benchmark:",
          ", ".join(f"({r['m_A']:g}, {r['m_a']:g}) {r['mg_over_atlas']:.3f}" for r in rows if "mg_over_atlas" in r))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

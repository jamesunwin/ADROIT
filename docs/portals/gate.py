"""The portal library's validation, as declared in docs/portal_library.md (section 5). $0.

    uv run python docs/portals/gate.py              # P1–P4 (MadDM and the arXiv lookups need the network/tools)

Each part is saved to gate_partial.json as it ends, so a stopped run can resume (--resume, with the
--out of the stopped run). It writes to a new runs/gates/portals/<UTC> folder unless --out names one
(docs/portals only to re-record the tracked receipts). Exit code: 0 passed, 1 not passed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.constraints import annihilation, exchange, processes, relic, spin1  # noqa: E402
from adroit.constraints import amplitudes as amp  # noqa: E402
from adroit.core.receipts import add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.parameter_space.classes import Point  # noqa: E402
from adroit.parameter_space.scan import Axis, ScanRequest, evaluate, run  # noqa: E402
from adroit.parameter_space.verdict import verdict  # noqa: E402

HERE = Path(__file__).parent
TOOLS = Path.home() / "agentic-dm-tools"


def p1() -> dict:
    out = {}
    x, w = np.polynomial.legendre.leggauss(24)
    meds, chi, f = [(91.19, 2.5), (60.0, 0.3)], [(0.02, 0.05), (0.7, 0.2)], [(-0.1, 0.18), (0.03, 0.01)]
    worst = 0.0
    for m, mf, s in [(40.0, 4.7, 120.0 ** 2), (100.0, 1.77, 230.0 ** 2), (30.0, 0.0, 70.0 ** 2)]:
        sq = amp.s_channel_squared_many(s, m, mf, meds, chi, f, x)
        num = amp.cross_section(sq, w, s, math.sqrt(s / 4 - m * m), math.sqrt(s / 4 - mf * mf), identical=False) * 3
        ana = exchange.vector_to_fermions(np.array([s]), m, "fermion", chi, mf, 3, f,
                                          [exchange.Mediator(*md) for md in meds])[0]
        worst = max(worst, abs(ana / num - 1))
    out["interference"] = {"worst": worst, "pass": worst < 1e-10}
    xs = np.array([-0.7, -0.1, 0.3, 0.9])
    ward = 0.0
    for s, m in ((900.0 ** 2, 400.0), (2100.0 ** 2, 1000.0)):
        p1_, p2_, k1, k2, _, _ = processes.frame(s, m, m, 0, 0, xs)
        for e1, e2 in ((k1, processes._transverse(k2)[1]), (processes._transverse(k1)[0], k2)):
            a1, a2 = processes.gauge_pair_amplitudes(p1_, p2_, k1, k2, e1, e2, m)
            ward = max(ward, np.abs(a1).max(), np.abs(a2).max())
    p1_, p2_, k1, k2, _, _ = processes.frame(700.0 ** 2, 300.0, 330.0, 0.0, 0.0, xs)
    for xi in processes._BASIS:
        for eta in processes._BASIS:
            ward = max(ward, np.abs(processes.dm_partner_amplitude(p1_, p2_, k1, k2, k2, 300.0, 330.0, 0.0, xi,
                                                                   eta)).max())
    out["ward"] = {"worst": float(ward), "pass": ward < 1e-10}
    m, M, y, g = 500.0, 600.0, 1.0, 0.3
    alpha = g * g / (4 * math.pi)

    def at(v: float) -> float:
        return 4 * m * m / (1 - (v / 2) ** 2)
    checks = {
        "scalar QED": processes.partners_to_gauge_bosons(at(1e-3), m, g, False) * 1e-3 / (2 * math.pi * alpha ** 2 / m ** 2),
        "scalar QCD": processes.partners_to_gauge_bosons(at(1e-3), m, g, True) * 1e-3 / (14 * math.pi * alpha ** 2 / (27 * m * m)),
        "Dirac t-channel": processes.t_channel_to_fermions(at(1e-3), m, 0.0, M, y, False) * 1e-3
        / (y ** 4 * m * m / (32 * math.pi * (m * m + M * M) ** 2)),
        "Majorana t-channel p-wave": processes.t_channel_to_fermions(at(1e-2), m, 0.0, M, y, True) * 1e-2
        / (y ** 4 * 1e-4 * m * m * (m ** 4 + M ** 4) / (48 * math.pi * (m * m + M * M) ** 4)),
        "Majorana t-channel s-wave (m_f)": processes.t_channel_to_fermions(at(1e-3), m, 172.5, M, y, True) * 1e-3
        / (y ** 4 * 172.5 ** 2 * math.sqrt(1 - 172.5 ** 2 / m ** 2) / (32 * math.pi * (m * m + M * M - 172.5 ** 2) ** 2)),
    }
    out["textbook"] = {"ratios": checks, "pass": all(abs(r - 1) < 1e-3 for r in checks.values())}
    out["WW width"] = _ww()
    rows = []
    for name, mmed, mdm in (("V1", 1000.0, 300.0), ("A1", 2000.0, 950.0), ("A1", 500.0, 100.0)):
        model = spin1.benchmark(name, mmed)
        old = annihilation.omega_h2(model, mdm)
        new = relic.omega_h2_single(lambda s: annihilation.total(s, model, mdm), mdm, 0.5, False,
                                    [(mmed, spin1.width(model, mdm))])
        rows.append(abs(new / old - 1))
    out["coannihilation solver"] = {"worst": max(rows), "pass": max(rows) < 1e-3}
    return out


def _ww() -> dict:
    from adroit.constraints.amplitudes import METRIC, polarisations
    mw, worst = 80.37, 0.0
    for M in (200.0, 500.0, 2000.0):
        cos, w = np.polynomial.legendre.leggauss(16)
        k, e = math.sqrt(M * M / 4 - mw * mw), M / 2
        one, zero, sin = np.ones(16), np.zeros(16), np.sqrt(1 - cos ** 2)
        k1 = np.stack([e * one, k * sin, zero, k * cos], 1)
        k2 = np.stack([e * one, -k * sin, zero, -k * cos], 1)
        q = k1 + k2
        dot = lambda a, b: np.sum(a * b * METRIC, axis=-1)                      # noqa: E731
        tot = np.zeros(16)
        for ev in (np.stack([zero, one, zero, zero], 1), np.stack([zero, zero, one, zero], 1),
                   np.stack([zero, zero, zero, one], 1)):
            for e1 in polarisations(k1, mw):
                for e2 in polarisations(k2, mw):
                    a = dot(ev, e1) * dot(-q - k1, e2) + dot(e1, e2) * dot(k1 - k2, ev) + dot(e2, ev) * dot(k2 + q, e1)
                    tot += a ** 2
        beta = math.sqrt(1 - 4 * mw * mw / M / M)
        gamma = (1 / (2 * M)) * (1 / 3) * np.sum(w * tot) / 2 * beta / (8 * math.pi)
        x = mw * mw / M / M
        worst = max(worst, abs(gamma / (M / (192 * math.pi) * (M / mw) ** 4 * beta ** 3 * (1 + 20 * x + 12 * x * x)) - 1))
    return {"worst": worst, "pass": worst < 1e-10}


def p2() -> dict:
    from adroit.constraints import maddm
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.portals.higgs import HiggsPortalScalar
    from adroit.parameter_space.portals.tchannel import TChannel
    sys.path.insert(0, str(ROOT / "docs" / "dm8"))
    import crosscheck
    out = {}
    rows = []
    for m_s in (90.0, 100.0, 110.0):
        model, params = crosscheck._point("G4", m_s, 125.0)
        r = maddm.run(model, "dms", params, f"portal_hps_{m_s:g}", crosscheck.WORK, direct=False)
        ours = HiggsPortalScalar().omega_h2(Point(m_chi=m_s, m_med=125.09, g_chi=0.1))
        rows.append({"m_S": m_s, "maddm": r.omega_h2, "adroit": ours, "ratio": r.omega_h2 / ours})
    out["a: scalar Higgs portal"] = {"rows": rows, "pass": all(abs(x["ratio"] - 1) <= 0.2 for x in rows)}
    rows = []
    g3 = ModelSpec.model_validate(crosscheck.REFERENCE["G3"]["reference"]["spec"])
    cls, point, _ = classify(g3)
    for m_dm, m_med in ((600.0, 500.0), (800.0, 300.0)):
        model, params = crosscheck._point("G3", m_dm, m_med)
        r = maddm.run(model, "dmchi", params, f"portal_ss_{m_dm:g}_{m_med:g}", crosscheck.WORK, direct=False)
        ours = cls.omega_h2(point.model_copy(update={"m_chi": m_dm, "m_med": m_med}))
        rows.append({"m_chi": m_dm, "m_S": m_med, "maddm": r.omega_h2, "adroit": ours, "ratio": r.omega_h2 / ours})
    out["b: scalar mediator SS"] = {"rows": rows, "pass": all(abs(x["ratio"] - 1) <= 0.2 for x in rows)}
    ufo = TOOLS / "dmsimpt" / "UFO_S3M_uR"
    if not ufo.exists():
        out["c: t-channel S3M_uR (DMSimpt)"] = {"note": "not run: DMSimpt not fetched", "pass": None}
        return out
    rows = []
    for m, M, y, coann in ((500.0, 1500.0, 1.0, False), (500.0, 550.0, 0.5, True)):
        width = y * y * M * (1 - m * m / (M * M)) ** 2 / (16 * math.pi)
        params = {"MXm": m, "MYS3u1": M, "lamS3u1x1": y, "WYS3u1": width, "MXd": 1e8, "MXs": 1e8, "MXv": 1e8}
        # MadGraph lowercases names and gives the PDG code 2000002 (the u_R partner) its MSSM name, ur
        r = maddm.run(ufo, "xm", params, f"portal_s3m_{m:g}_{M:g}", TOOLS / "maddm-work" / "portals", direct=False,
                      coannihilators=["ur"] if coann else None)
        ours = TChannel().omega_h2(Point(m_chi=m, m_med=M, g_chi=y))
        rows.append({"m_chi": m, "m_phi": M, "y": y, "maddm": r.omega_h2, "adroit": ours, "ratio": r.omega_h2 / ours,
                     "tolerance": 0.25 if coann else 0.2})
    out["c: t-channel S3M_uR (DMSimpt)"] = {"rows": rows,
                                            "pass": all(abs(x["ratio"] - 1) <= x["tolerance"] for x in rows)}
    return out


def _contour(cls, fixed: Point, x: Axis, y: Axis, unverified: bool = False):
    return verdict(run(ScanRequest(model_class=cls, fixed=fixed, x=x, y=y, workers=2, unverified_records=unverified)))


def p3() -> dict:
    from adroit.parameter_space.portals.higgs import HiggsPortalFermion, HiggsPortalScalar
    from adroit.parameter_space.portals.vector import ChargedZPrime, ZPortal
    out = {}
    hps = HiggsPortalScalar()
    low = hps.omega_h2(Point(m_chi=62.27, m_med=125.09, g_chi=2.9e-4))
    high = hps.omega_h2(Point(m_chi=9790.0, m_med=125.09, g_chi=3.1))
    resonance = evaluate(hps, Point(m_chi=62.27, m_med=125.09, g_chi=2.9e-4), unverified=True)
    v = _contour(hps, Point(m_chi=100, m_med=125.09, g_chi=0.1), Axis(parameter="m_chi", low=10, high=1e4, n=30),
                 Axis(parameter="g_chi", low=1e-5, high=10, n=30))
    mid = [c for c in v.crossings if 110 < c.point.m_chi < 1000]
    out["a: scalar singlet"] = {
        "omega_62.27": low, "omega_9790": high, "resonance_excluded_by": [k for k, e in resonance.excluded.items() if e],
        "contour_110_1000": f"{sum(c.status == 'excluded' for c in mid)}/{len(mid)}",
        "pass": abs(low / 0.12 - 1) <= 0.3 and abs(high / 0.12 - 1) <= 0.3
        and not any(resonance.excluded.values()) and bool(mid) and all(c.status == "excluded" for c in mid)}
    vec = _contour(ZPortal(), Point(m_chi=100, m_med=91.19, g_chi=0.01), Axis(parameter="m_chi", low=1, high=1e4, n=30),
                   Axis(parameter="g_chi", low=1e-5, high=1, n=24))
    below = [c for c in vec.crossings if c.point.m_chi < 5000]
    ax = _contour(ZPortal(coupling="axial"), Point(m_chi=100, m_med=91.19, g_chi=0.01),
                  Axis(parameter="m_chi", low=1, high=1e4, n=30), Axis(parameter="g_chi", low=1e-5, high=1, n=24))
    band = [c for c in ax.crossings if 50 < c.point.m_chi < 150]
    above = [c for c in ax.crossings if c.point.m_chi > 300]
    out["b: Z portal"] = {
        "vector_below_5TeV": f"{sum(c.status == 'excluded' for c in below)}/{len(below)}",
        "axial_50_150": f"{sum(c.status == 'excluded' for c in band)}/{len(band)}",
        "axial_above_300_not_excluded": sum(c.status != "excluded" for c in above),
        "pass": bool(below) and all(c.status == "excluded" for c in below) and bool(band)
        and all(c.status == "excluded" for c in band) and any(c.status != "excluded" for c in above)}
    cp = _contour(HiggsPortalFermion(), Point(m_chi=100, m_med=125.09, g_chi=1e-3),
                  Axis(parameter="m_chi", low=10, high=1e4, n=30), Axis(parameter="g_chi", low=1e-6, high=1, n=24))
    outside = [c for c in cp.crossings if not 55 <= c.point.m_chi <= 65]
    cpv = _contour(HiggsPortalFermion(xi=math.pi / 2), Point(m_chi=100, m_med=125.09, g_chi=1e-3),
                   Axis(parameter="m_chi", low=10, high=1e4, n=30), Axis(parameter="g_chi", low=1e-6, high=1, n=24))
    out["c: fermion Higgs portal"] = {
        "cp_conserving_outside_55_65": f"{sum(c.status == 'excluded' for c in outside)}/{len(outside)}",
        "cp_violating_dd_excluded": sum("direct detection" in c.excluded_by for c in cpv.crossings),
        "cp_violating_points": len(cpv.crossings),
        "pass": bool(outside) and all(c.status == "excluded" for c in outside) and bool(cpv.crossings)
        and not any("direct detection" in c.excluded_by for c in cpv.crossings)}
    bl = _contour(ChargedZPrime(), Point(m_chi=1000, m_med=2000, g_chi=0.1 / 3, g_q=0.1),
                  Axis(parameter="m_med", low=100, high=1e4, n=30), Axis(parameter="m_chi", low=10, high=5000, n=30))
    off = [c for c in bl.crossings if abs(c.point.m_med - 2 * c.point.m_chi) > 0.2 * c.point.m_med]
    out["d: B - L"] = {"off_resonance_excluded": f"{sum(c.status == 'excluded' for c in off)}/{len(off)}",
                       "contour_points": len(bl.crossings),
                       "pass": all(c.status == "excluded" for c in off)}
    return out


def typed_mapping_check(cases: dict) -> dict:
    """Require physical mapping, or a specific refusal of underspecified input."""
    from adroit.core.model_spec import ModelSpec
    from adroit.orchestrator.ideas import from_fields
    from adroit.parameter_space import library
    from adroit.parameter_space.classify import Unsupported, classify
    expected_pending = {"dark photon": "pure dark current coefficient",
                        "mixing singlet": "mass-eigenstate/potential matching",
                        "coloured partner": "one explicit SM flavour",
                        "charged partner": "one explicit SM flavour"}
    checked, pending = {}, {}
    for name, (expected, fields) in cases.items():
        general = from_fields(ModelSpec.model_validate({"name": name, "phase": "unbroken", "fields": fields})).general
        try:
            cls, _, _ = classify(general)
            reference = library.entry(expected).model_class
            checked[name] = (name not in expected_pending and type(reference) is type(cls)
                             and reference.model_dump(exclude={"name"}) == cls.model_dump(exclude={"name"}))
        except Unsupported as error:
            pending[name] = str(error)
            checked[name] = name in expected_pending and expected_pending[name] in str(error)
    return {"cases": checked, "pending_reasons": pending, "pass": all(checked.values())}


def p4(folder: Path) -> dict:
    import re
    from adroit.model_building.audit import audit
    from adroit.orchestrator import track1
    from adroit.parameter_space import library
    from adroit.parameter_space.references import REFERENCES
    from adroit.retrieval.corpus import fetch_arxiv
    out = {}
    audits = {e.id: audit(e.spec()).valid for e in library.ENTRIES}
    out["audits"] = {"invalid": [k for k, v in audits.items() if not v], "pass": all(audits.values())}
    ids = sorted({re.match(r"arXiv:(\S+)", r).group(1) for e in library.ENTRIES for r in e.references})
    found = {re.sub(r"v\d+$", "", p.source_id): " ".join(p.title.split()) for p in fetch_arxiv(id_list=ids, max_results=len(ids))}
    wrong = [i for i in ids if found.get(i) != REFERENCES[i][0]]
    out["references"] = {"count": len(ids), "unresolved_or_different": wrong, "pass": not wrong}
    runs = {}
    with tempfile.TemporaryDirectory() as scratch:
        for e in library.ENTRIES:
            started = time.time()
            print(f"P4: {e.id} ({len(runs) + 1}/{len(library.ENTRIES)})", flush=True)
            request = track1.for_portal(e.id, x=e.x.model_copy(update={"n": 8}), y=e.y.model_copy(update={"n": 8}),
                                        literature=False)
            try:
                result = track1.run(request, Path(scratch) / e.id)
                runs[e.id] = {"level": result.verdict.level, "plot": (Path(scratch) / e.id / "parameter_plane.png").exists(),
                              "crossings": len(result.verdict.crossings),
                              "residuals": [c.relative_residual for c in result.verdict.crossings if c.kind == "contour"],
                              "unresolved": result.verdict.unresolved}
            except Exception as error:                                            # noqa: BLE001 - recorded as a failure
                runs[e.id] = {"error": f"{type(error).__name__}: {error}"[:300]}
            runs[e.id]["seconds"] = time.time() - started
            (folder / "p4_progress.json").write_text(json.dumps(runs, indent=2, default=str))
            print(f"P4: {e.id}: {runs[e.id]}", flush=True)
    out["track1"] = {"runs": runs, "pass": all("level" in r and r["plot"] for r in runs.values())}
    cases = {
        "singlet scalar": ("higgs_portal_scalar", [{"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True,
                                                    "dark_parity": -1}]),
        "dark photon": ("dark_photon_dirac", [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1,
                                               "charges": {"extra": {"Xd": 1}}},
                                              {"name": "Xd", "role": "mediator", "spin": 1, "self_conjugate": True}]),
        "mixing singlet": ("singlet_scalar_mixing", [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1},
                                                     {"name": "s", "role": "mediator", "spin": 0, "self_conjugate": True}]),
        "coloured partner": ("tchannel_uR_majorana", [{"name": "chi", "role": "dark_matter", "spin": 0.5,
                                                       "self_conjugate": True, "dark_parity": -1},
                                                      {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1,
                                                       "charges": {"su3": "3", "hypercharge": 0.6666667}}]),
        "charged partner": ("lepton_portal_muR", [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True,
                                                   "dark_parity": -1},
                                                  {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1,
                                                   "charges": {"hypercharge": -1}}]),
    }
    out["recognised"] = typed_mapping_check(cases)
    return out


def main() -> int:
    """P1–P4 ($0); returns the exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="keep the parts in --out's gate_partial.json")
    parser.add_argument("--summarise", action="store_true",
                        help="recompute the summary from gate.json (--out's, else the tracked receipt)")
    add_out_argument(parser, "portals")
    args = parser.parse_args()
    if args.resume and not args.out:
        raise SystemExit("--resume needs --out: the folder of the stopped run")
    folder = gate_output("portals", args.out)
    if args.summarise:
        source = folder / "gate.json" if (folder / "gate.json").exists() else HERE / "gate.json"
        return summarise(json.loads(source.read_text()), folder)
    partial = folder / "gate_partial.json"
    parts = json.loads(partial.read_text()) if args.resume and partial.exists() else {}
    for key, part in (("P1", p1), ("P4", lambda: p4(folder)), ("P3", p3), ("P2", p2)):
        if key not in parts:
            try:
                parts[key] = part()
            except Exception as error:                                        # noqa: BLE001 - recorded, then reported
                parts[key] = {"error": f"{type(error).__name__}: {error}"[:600], "pass": False}
            partial.write_text(json.dumps(parts, indent=1, default=str))
    code = summarise(parts, folder)
    partial.unlink(missing_ok=True)
    return code


def verdict_of(value) -> bool | None:
    """A part's "pass", read strictly: True, False, or None (not run); numpy booleans and their text included."""
    if value is None or value == "None":
        return None
    if isinstance(value, str):
        return value == "True"
    return bool(value)


def summarise(parts: dict, folder: Path) -> int:
    """Write gate.json and gate.md to ``folder``; the exit code."""
    ok = {}
    for key in ("P1", "P2", "P3", "P4"):
        items = [v for v in parts[key].values() if isinstance(v, dict) and "pass" in v] or [parts[key]]
        results = [verdict_of(item["pass"]) for item in items]
        ok[key] = all(r is not False for r in results) and any(r is True for r in results)
    (folder / "gate.json").write_text(json.dumps(parts, indent=1, default=str))
    lines = ["# The portal library's validation", ""] + [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in ok.items()]
    lines += ["", f"**{'PASSED' if all(ok.values()) else 'NOT PASSED'}** ($0)", "", "```",
              json.dumps(parts, indent=1, default=str)[:12000], "```"]
    (folder / "gate.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))
    print(f"written to {folder}")
    return exit_code(all(ok.values()))


if __name__ == "__main__":
    sys.exit(main())

"""DM13's gate: the parameter-space scan and the Track 1 verdict, checked four ways ($0).

    uv run python docs/dm13/gate.py            # all parts (minutes; MadDM for G2 if installed)

It writes to a new runs/gates/dm13/<UTC> folder unless --out names one (docs/dm13 only to
re-record the tracked receipts). Exit code: 0 passed, 1 not passed.

Declared in docs/dm13_parameter_space.md (section 5) before the first run:
- G1. The direct-detection boundary of the scan reproduces DM7's combined picture: the largest
  mediator mass excluded at m_DM = 10, 100, 300 GeV, for V1 (31, 37, 30 TeV) and A1 (420, 440,
  350 GeV), within 15%.
- G2. The scalar class's relic density (new code) agrees with MadDM run on ADROIT's UFO files of
  DM8's scalar-mediator model at three points, within 20% (MadDM's g* bookkeeping alone moves it ~10%).
- G3. Verdicts that match the literature:
  (a) the Working Group's V1: the whole relic contour excluded (m_χ 10–2000 GeV);
  (b) A1: not wholly excluded; CMS excludes every contour point with 200 GeV < m_med < 1.8 TeV
      inside its source plane. Source-frame points must retain the flag and pending collider cut;
  (c) a pseudoscalar mediator with Yukawa-like couplings (g_χ = g_q = 1): direct detection excludes
      no contour point; its mixed final states cannot inherit a pure-bb̄ Fermi-LAT cut and must
      retain pending spectral coverage at every contour point;
  (d) DM8's models outside the computed classes are reported UNDETERMINED, with a reason.
- G4. Each Track 1 report (V1, A1, the scalar mediator) holds validity, the verdict, the plots, the
  contour table, what was and was not computed, the curated literature, and the arXiv search's
  result or the reason it was not made.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from adroit.constraints import spin1, verdicts  # noqa: E402
from adroit.core.model_spec import ModelSpec  # noqa: E402
from adroit.core.receipts import add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class  # noqa: E402
from adroit.parameter_space.classify import classify  # noqa: E402
from adroit.parameter_space.scan import DWARF_SPEED, Axis, ScanRequest, evaluate, run  # noqa: E402
from adroit.parameter_space.verdict import Verdict, verdict  # noqa: E402

HERE = Path(__file__).parent
DM7 = {"V1": {10: 31000.0, 100: 37000.0, 300: 30000.0}, "A1": {10: 420.0, 100: 440.0, 300: 350.0}}


def dd_boundary(cls, m_dm: float) -> float:
    """The largest mediator mass direct detection excludes at m_dm (bisection in ln m_med)."""
    lo, hi = math.log(10.0), math.log(2e5)
    if not evaluate(cls, Point(m_chi=m_dm, m_med=math.exp(lo), g_chi=1.0, g_q=0.25)).excluded["direct detection"]:
        return 0.0
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        hit = evaluate(cls, Point(m_chi=m_dm, m_med=math.exp(mid), g_chi=1.0, g_q=0.25)).excluded["direct detection"]
        lo, hi = (mid, hi) if hit else (lo, mid)
    return math.exp(lo)


def g1() -> list[dict]:
    rows = []
    for name, kind in (("V1", spin1.Spin1Kind.vector), ("A1", spin1.Spin1Kind.axial)):
        cls = Spin1Class(kind=kind, name=name)
        for m_dm, expected in DM7[name].items():
            found = dd_boundary(cls, float(m_dm))
            rows.append({"model": name, "m_dm": m_dm, "dm7": expected, "scan": round(found, 1),
                         "ratio": round(found / expected, 3), "pass": abs(found / expected - 1) <= 0.15})
    return rows


def g2() -> list[dict]:
    from adroit.constraints import maddm
    if not maddm.available():
        return [{"note": "MadDM is not installed: G2 not run", "pass": False}]
    sys.path.insert(0, str(ROOT / "docs" / "dm8"))
    import crosscheck
    rows = []
    for m_dm, m_med in ((100.0, 500.0), (200.0, 500.0), (300.0, 1000.0)):
        model, params = crosscheck._point("G3", m_dm, m_med)
        r = maddm.run(model, "dmchi", params, f"dm13_scalar_{m_dm:g}_{m_med:g}", crosscheck.WORK, direct=False)
        cls, point, _ = classify(ModelSpec.model_validate(crosscheck.REFERENCE["G3"]["reference"]["spec"]))
        ours = cls.omega_h2(point.model_copy(update={"m_chi": m_dm, "m_med": m_med}))
        ratio = (r.omega_h2 / ours) if (r.omega_h2 and ours) else None
        rows.append({"m_dm": m_dm, "m_med": m_med, "maddm": r.omega_h2, "adroit": ours,
                     "ratio": ratio, "pass": ratio is not None and abs(ratio - 1) <= 0.20})
    return rows


def scan(cls, fixed: Point, n: int = 20):
    request = ScanRequest(model_class=cls, fixed=fixed, x=Axis(parameter="m_med", low=10.0, high=1e4, n=n),
                          y=Axis(parameter="m_chi", low=10.0, high=2000.0, n=n), workers=2)
    result = run(request)
    return result, verdict(result)


def cms_contour_check(v: Verdict) -> dict:
    """Require interior CMS exclusions and enforce the existing source-frame policy.

    The upper CMS frame does not resolve a cut; it must never become an allowed
    point. This separates that domain assertion from the interior exclusion rule.
    """
    low = [c for c in v.crossings if 200 < c.point.m_med < 1800]
    edge = [c for c in low if c.point.m_chi > verdicts.PLANE_M_DM * (1 - verdicts.FRAME)]
    interior = [c for c in low if c not in edge]
    edge_pass = all(verdicts.EDGE_FLAG in c.flags and "colliders (CMS)" not in c.excluded_by
                    and any("colliders (CMS)" in reason and "outside the summary" in reason
                            for reason in c.pending)
                    and c.status != "viable" for c in edge)
    return {"level": v.level, "cases": [c.model_dump() for c in low],
            "cms_200_1800": f"{sum('colliders (CMS)' in c.excluded_by for c in low)}/{len(low)}",
            "cms_in_source_plane": f"{sum('colliders (CMS)' in c.excluded_by for c in interior)}/{len(interior)}",
            "source_frame_cases": len(edge), "source_frame_policy_pass": edge_pass,
            "pass": v.level != "excluded" and bool(interior) and edge_pass
                    and all("colliders (CMS)" in c.excluded_by for c in interior)}


def pseudoscalar_contour_check(cls: ScalarClass, v: Verdict) -> dict:
    """Check actual final states rather than assuming the dominant channel is pure.

    The original 80% exclusion expectation used the pure-bb curve for a mixed
    c/b spectrum. M05 removed that unsupported recast. A mixed spectrum must
    either stay pending on the missing spectral likelihood or be decided by the
    conservative mixture rule (constraints.mixtures: a channel alone above its
    own curve excludes, a bounded sum below one allows), which never applies
    one channel's curve to the whole rate. Each computed channel is saved.
    """
    from adroit.constraints.indirect import fermi_mixture
    from adroit.parameter_space.scan import _fermi_limits
    curves = {k: c["limit_cm3_s"] for k, c in _fermi_limits().items()}
    fermi = "gamma rays (Fermi-LAT dwarfs)"
    cases = []
    for crossing in v.crossings:
        channels = cls.sigma_v_today(crossing.point, DWARF_SPEED)
        active = {name: rate for name, rate in channels.items() if rate > 0}
        pending = any("Fermi-LAT dwarfs" in reason and "mixed" in reason
                      for reason in crossing.pending)
        bound = fermi_mixture(channels, crossing.point.m_chi, curves, False)
        decided = crossing.evaluation.excluded.get(fermi) if crossing.evaluation else None
        by_rule = decided is not None and decided == bound.excluded
        cases.append({"crossing": crossing.model_dump(), "channels": channels,
                      "mixed": len(active) > 1, "spectral_coverage_pending": pending,
                      "mixture_rule": bound.why() if by_rule else ""})
    below = [c for c in v.crossings if c.point.m_chi < 50]
    above = [c for c in v.crossings if c.point.m_chi > 200]
    dd = sum("direct detection" in c.excluded_by for c in v.crossings)
    return {"level": v.level, "cases": cases, "dd_excludes": dd,
            "fermi_below_50": f"{sum(fermi in c.excluded_by for c in below)}/{len(below)}",
            "fermi_above_200": f"{sum(fermi in c.excluded_by for c in above)}/{len(above)}",
            "pass": bool(below) and bool(above) and dd == 0
                    and all(c["mixed"] and c["crossing"]["status"] != "viable"
                            and ((c["spectral_coverage_pending"] and fermi not in c["crossing"]["excluded_by"])
                                 or c["mixture_rule"]) for c in cases)}


def unsupported_class_check(folder: Path) -> dict:
    """Distinguish the incomplete historical G4 input from a supported Higgs portal."""
    from adroit.parameter_space import library
    rows = []
    # Since the owner's decision of 2026-10-15 a model outside the classes goes to the generic route by default, so
    # the gate asks the classes themselves (generic_route=False) and records what the generic route does.
    from adroit.parameter_space.classify import Unsupported
    for g in yaml.safe_load((ROOT / "docs/dm8/gate_models.yaml").read_text())["models"]:
        if g["id"] in ("G4", "G5", "G6", "G7", "G8", "G9", "G10"):
            model = ModelSpec.model_validate(g["reference"]["spec"])
            try:
                classify(model, generic_route=False)
                reason = ""
            except Unsupported as error:
                reason = str(error)
            try:
                generic = type(classify(model)[0]).__name__
            except Unsupported as error:
                generic = f"refused: {str(error)[:80]}"
            rows.append({"id": g["id"], "reason": reason, "generic_route": generic, "pass": bool(reason)})
    supported, _, _ = classify(library.entry("higgs_portal_scalar").spec())
    canonical = getattr(supported, "family", None) == "higgs_portal_scalar"
    return {"cases": rows, "undetermined": f"{sum(r['pass'] for r in rows)}/{len(rows)}",
            "canonical_higgs_portal_supported": canonical, "pass": len(rows) == 7
            and all(r["pass"] for r in rows) and canonical}


def g3(folder: Path) -> dict:
    out = {}
    _, v = scan(Spin1Class(kind=spin1.Spin1Kind.vector, name="V1"), Point(m_chi=100, m_med=1000, g_chi=1, g_q=0.25))
    out["a"] = {"level": v.level, "pass": v.level == "excluded"}
    _, v = scan(Spin1Class(kind=spin1.Spin1Kind.axial, name="A1"), Point(m_chi=100, m_med=1000, g_chi=1, g_q=0.25))
    out["b"] = cms_contour_check(v)
    cls = ScalarClass(dm_pseudoscalar=True, sm_pseudoscalar=True, name="pseudoscalar")
    _, v = scan(cls, Point(m_chi=100, m_med=1000, g_chi=1, g_q=1))
    out["c"] = pseudoscalar_contour_check(cls, v)
    out["d"] = unsupported_class_check(folder)
    return out


def g4(folder: Path) -> list[dict]:
    from adroit.orchestrator import runs
    from adroit.orchestrator.track1 import Track1Request
    rows = []
    for name in ("vector_mediator", "axial_mediator", "scalar_mediator"):
        spec = ModelSpec.model_validate(yaml.safe_load((HERE / f"{name}.yaml").read_text()))
        request = Track1Request(spec=spec, x=Axis(parameter="m_med", low=10.0, high=1e4, n=20),
                                y=Axis(parameter="m_chi", low=10.0, high=2000.0, n=20))
        written, text = runs.track1(request, folder / "reports" / name, name)
        needed = ["## 1. The model", "## 2. The verdict", "parameter_plane.png", "## 4. What was computed",
                  "Curated records", "Prior work"]
        rows.append({"model": name, "missing": [n for n in needed if n not in text],
                     "plots": sorted(p.name for p in written.glob("*.png")),
                     "pass": all(n in text for n in needed) and (written / "parameter_plane.png").exists()})
    return rows


def main() -> int:
    """G1–G4 ($0); returns the exit code."""
    parser = argparse.ArgumentParser()
    add_out_argument(parser, "dm13")
    folder = gate_output("dm13", parser.parse_args().out)
    parts = {"G1": g1(), "G2": g2(), "G3": g3(folder), "G4": g4(folder)}
    passed = {"G1": all(r["pass"] for r in parts["G1"]), "G2": all(r["pass"] for r in parts["G2"]),
              "G3": all(v["pass"] for v in parts["G3"].values()), "G4": all(r["pass"] for r in parts["G4"])}
    (folder / "gate.json").write_text(json.dumps(parts, indent=1, default=str))
    lines = ["# DM13 gate", ""] + [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in passed.items()]
    lines += ["", f"**{'PASSED' if all(passed.values()) else 'NOT PASSED'}** ($0)", "", "```",
              json.dumps(parts, indent=1, default=str)[:6000], "```"]
    (folder / "gate.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))
    print(f"written to {folder}")
    return exit_code(all(passed.values()))


if __name__ == "__main__":
    sys.exit(main())

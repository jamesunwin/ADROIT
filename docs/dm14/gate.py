"""DM14's gate: anomaly intake, users' models, the single-idea report, recursion and the drafter.

    uv run python docs/dm14/gate.py                     # G1-G4 ($0)
    uv run python docs/dm14/gate.py --live --budget 1   # and G5 with claude-opus-5-5 (paid)

Declared in docs/dm14_track2.md (section 6) before the first run.

It writes to a new runs/gates/dm14/<UTC> folder unless --out names one (docs/dm14 only to re-record the
tracked receipts); --resume needs the --out of the stopped run. Exit code: 0 passed, 1 not passed, 3 G5
stopped at the budget.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from adroit.core.receipts import BUDGET_STOPPED, add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.experiments import anomaly, historical, registry  # noqa: E402
from adroit.inference import signal_fit  # noqa: E402
from adroit.orchestrator import promote, signal, single_idea, studies  # noqa: E402
from adroit.parameter_space import simplified  # noqa: E402

HERE = Path(__file__).parent
SI = "CDMS II Si (2013)"
sys.path.insert(0, str(ROOT / "tests" / "experiments"))
from test_anomaly import SEEDED  # noqa: E402  (the eight seeded errors, shared with the unit tests)


def user_copy(folder: Path, verified: str) -> str:
    """The CDMS II Si record as a user's file, its efficiency as a digitiser's CSV."""
    data = dict(historical.record("cdms_ii_si_2013"))
    table = historical.digitised.load(data["efficiency"]["digitised"])
    (folder / "efficiency.csv").write_text("energy_kev,efficiency\n" + "\n".join(
        f"{e},{x}" for e, x in zip(table["recoil_energy_kev"], table["efficiency"])))
    data.update(efficiency={"csv": "efficiency.csv"}, verified_by=verified)
    (folder / "cdms_si.yaml").write_text(yaml.safe_dump(data))
    return f"record:{folder / 'cdms_si.yaml'}"


def fit(module, c: signal.Candidate) -> signal_fit.SignalFit:
    events, sigma = module.observations()
    s = signal._signal(module, c)
    f = signal_fit.event_densities(np.asarray(module.signal_grid_kev()), s.density, events, sigma)
    return signal_fit.fit(c.label, f, module.background_at(events), module.background_rate())


def g1(folder: Path) -> dict:
    a = {k: anomaly.check(anomaly.AnomalyRecord.model_validate(historical.record(k))) for k in historical.records()}
    caught = {}
    for name, seed in SEEDED.items():
        data = yaml.safe_load(anomaly.template())
        seed(data)
        caught[name] = anomaly.check(anomaly.AnomalyRecord.model_validate(data))
    name = user_copy(folder, "the DM14 gate (a copy of the verified record)")
    mine, theirs = registry.load_module(name), registry.load_module(SI)
    rows = []
    for m in (5.0, 10.0, 20.0):
        c = signal.Candidate(label=f"O1s@{m:g}", card_id="O1", isospin="s", mass_gev=m)
        x, y = fit(mine, c), fit(theirs, c)
        rows.append({"mass": m, "s_hat": [x.s_hat, y.s_hat], "z": [x.z_local, y.z_local],
                     "pass": abs(x.s_hat / y.s_hat - 1) <= 1e-3 and abs(x.z_local / y.z_local - 1) <= 1e-3})
    draft = user_copy(folder, "")
    small = [signal.Candidate(label="O1s@10", card_id="O1", isospin="s", mass_gev=10.0)]
    try:
        signal.run(signal.SignalRequest(experiment=draft, candidates=small, null_modules=[], toys=200))
        refused = False
    except ValueError:
        refused = True
    accepted = signal.run(signal.SignalRequest(experiment=draft, candidates=small, null_modules=[], toys=200,
                                               unverified_records=True)).fits[0].z_local > 0
    return {"a": {"problems": a, "pass": not any(a.values())},
            "b": {"caught": {k: v[:1] for k, v in caught.items()}, "pass": all(caught.values())},
            "c": {"rows": rows, "pass": all(r["pass"] for r in rows)},
            "d": {"refused": refused, "accepted_when_asked": accepted, "pass": refused and accepted}}


def g2() -> dict:
    masses = [5.0, 10.0, 20.0, 50.0]
    request = signal.SignalRequest(
        experiment=SI, null_modules=[], toys=2000, leaders=2,
        candidates=[signal.Candidate(label=f"O1s@{m:g}", card_id="O1", isospin="s", mass_gev=m) for m in masses],
        user_models=[signal.UserModel(spec=simplified.model(k, 10, 1000), masses_gev=masses)
                     for k in ("vector", "scalar")])
    result = signal.run(request)
    z = {f.label: f.z_local for f in result.fits}
    rows = []
    for kind in ("vector", "scalar"):
        for m in masses:
            mine, lib = f"{kind}_mediator@{m:g}", f"O1s@{m:g}"
            rows.append({"model": mine, "z": z[mine], "z_O1": z[lib],
                         "same_class": result.classes[mine] == result.classes[lib],
                         "pass": abs(z[mine] - z[lib]) <= 0.01 and result.classes[mine] == result.classes[lib]})
    return {"rows": rows, "pass": all(r["pass"] for r in rows)}


def g3(folder: Path) -> dict:
    out = folder / "single_idea_vector_cdms_si"
    request = single_idea.SingleIdeaRequest(experiment=SI, spec=simplified.model("vector", 10, 1000),
                                            masses_gev=np.geomspace(5, 40, 12).tolist(), toys=20_000, grid=16)
    from adroit.orchestrator import runs
    folder, text = runs.single_idea(request, out)
    r = single_idea.SingleIdeaResult.model_validate_json((folder / "result.json").read_text())
    return single_idea_check(r, text)


def single_idea_check(r: single_idea.SingleIdeaResult, text: str) -> dict:
    """Keep this benchmark's physical-fit compatibility separate from thermal viability.

    M10/M11 preserve the 1000 GeV mediator and solve a perturbative g_chi.
    The 5 GeV fit lies outside that branch; eleven resolved fits remain
    DD-excluded, but incomplete thermal coverage cannot certify exclusion.
    """
    if any(b.physical_fit is not None for b in r.band):
        return _bounded_single_idea_check(r,text)
    best_mass = float(r.best.rsplit("@", 1)[1])
    best = next(b for b in r.band if b.m_chi == best_mass)
    fitted = [b for b in r.band if b.z_local >= 1.0]
    resolved = [b for b in fitted if b.point is not None and b.omega_h2 is not None]
    unresolved = [b for b in fitted if b not in resolved]
    physical = all(b.point.m_med == 1000 and 0 <= b.point.g_chi <= np.sqrt(4 * np.pi)
                   and b.fitted_parameter == "g_chi"
                   and b.fitted_value == b.point.g_chi
                   and b.spectrum_relative_error is not None and 0 <= b.spectrum_relative_error <= 1e-6
                   and b.delta_log_l_error is not None and 0 <= b.delta_log_l_error <= 1e-6
                   for b in resolved)
    dd = bool(resolved) and all("direct detection" in b.excluded_by for b in resolved)
    outside_branch = (len(unresolved) == 1 and unresolved[0].m_chi == 5.0
                      and "outside the perturbative g_chi branch" in unresolved[0].inversion_reason
                      and unresolved[0].status == "pending")
    return {"a": {"best_mass": best.m_chi, "pass": 7.0 <= best.m_chi <= 11.0},
            "b": {"level": r.level, "fit_quality": r.fit_quality,
                  "constraint_compatibility": r.constraint_compatibility,
                  "thermal_viability": r.thermal_viability, "fitted": len(fitted),
                  "resolved": len(resolved), "dd_everywhere_resolved": dd,
                  "unresolved": [{"mass": b.m_chi, "reason": b.inversion_reason} for b in unresolved],
                  "physical_fit_checks": physical,
                  "pass": len(fitted) == 12 and len(resolved) == 11 and dd and physical
                  and outside_branch and r.fit_quality == "fits" and r.constraint_compatibility == "pending"
                  and r.level == r.thermal_viability == "undetermined" and bool(r.thermal_pending)
                  and not r.thermal},
            "c": {"thermal_pending": r.thermal_pending,
                  "pass": f"thermal viability: {r.thermal_viability}" in text
                  and bool(r.thermal_pending) and all(reason in text for reason in r.thermal_pending)
                  and all(b.inversion_reason in text for b in unresolved)}}


def _bounded_single_idea_check(r: single_idea.SingleIdeaResult, text: str) -> dict:
    """The same benchmark after direct bounded fits replace failed inversions.

    A smaller constrained fit can lose fit quality; a complete physical fit
    need not match the free-amplitude likelihood. Thermal claims still need
    certified roots; resolved grid sampling alone never establishes viability.
    """
    best_mass = float(r.best.rsplit("@",1)[1])
    fitted = [b for b in r.band if single_idea._fit_z(b)>=1]
    resolved = [b for b in fitted if b.point is not None and b.omega_h2 is not None]
    def checked(b):
        if b.point is None or b.point.m_med!=1000 or b.fitted_value!=b.point.g_chi:
            return False
        fit = b.physical_fit
        if fit is None:
            return (b.spectrum_relative_error is not None and 0<=b.spectrum_relative_error<=1e-6
                    and b.delta_log_l_error is not None and 0<=b.delta_log_l_error<=1e-6)
        return (fit.resolved and fit.identifiable and fit.point==b.point
                and fit.bounds.low<=b.point.g_chi<=fit.bounds.high
                and fit.log_l is not None and np.isfinite(fit.log_l)
                and fit.null_log_l is not None and np.isfinite(fit.null_log_l)
                and fit.q0 is not None and np.isfinite(fit.q0)
                and 0<fit.evaluations<=fit.settings.max_evaluations and bool(fit.regions))
    physical = bool(resolved) and all(checked(b) for b in resolved)
    dd = bool(resolved) and all("direct detection" in b.excluded_by for b in resolved)
    complete = all(b.point is not None and b.omega_h2 is not None and checked(b) for b in r.band)
    certified = [b for b in r.thermal if b.converged and b.relative_residual is not None
                 and b.relative_residual<=.01 and single_idea._fit_z(b)>=1]
    headline = ((r.level=="no_thermal" and complete and not r.thermal)
                or (r.level=="undetermined" and bool(r.thermal_pending))
                or (r.level=="excluded" and bool(certified) and not r.thermal_pending
                    and all(b.status=="excluded" for b in certified)))
    return {"a":{"best_mass":best_mass,"pass":7<=best_mass<=11},
            "b":{"level":r.level,"fitted":len(fitted),"resolved":len(resolved),
                 "physical_fit_checks":physical,"dd_everywhere_resolved":dd,
                 "bounded_fit_checks":True,"pass":physical and dd and headline
                     and r.fit_quality=="fits" and r.thermal_viability==r.level},
            "c":{"thermal_pending":r.thermal_pending,
                 "pass":bool(r.physical_significance_note) and r.physical_significance_note in text
                     and f"thermal viability: {r.thermal_viability}" in text
                     and all(reason in text for reason in r.thermal_pending)}}


def g4(folder: Path) -> dict:
    parent = folder / "recursion" / "signal_cdms_si"
    if parent.exists():
        shutil.rmtree(parent)
    parent.mkdir(parents=True)
    cands = [signal.Candidate(label=f"{c}{i}@{m:g}", card_id=c, isospin=i, mass_gev=m)
             for c in ("O1", "L01") for i in "sv" for m in (5.0, 10.0, 20.0)]
    # The declaration also listed M_vector; mediator cards have no isospin variants and are not in Path 2's
    # space, so the first run stopped here. Changed after that run, as recorded in docs/dm14_track2.md.
    from adroit.orchestrator import runs
    runs._write(parent, signal.run(signal.SignalRequest(experiment=SI, candidates=cands, null_modules=[],
                                                        toys=5000, leaders=3)),
                "(see result.json)", "signal", f"Path 2: {SI}")
    result = signal.SignalResult.model_validate_json((parent / "result.json").read_text())
    leader = max(result.fits, key=lambda f: f.z_local).label
    which = f"class:{result.classes[leader]}"
    members = promote.labels_of(result, which)
    p = promote.promote(parent, [which], {"toys": 5000, "grid": 10, "masses": 7})
    (parent / "promotion.md").write_text(promote.report(p))
    pool = promote.candidates_of(result)
    expected = {s.name for label in members for _, s in promote.models_for(result, pool[label])}
    kids = [studies.load(Path(c.folder)) for c in p.children]
    tree = studies.tree(folder / "recursion")
    depth = {s.folder: d for d, s in tree}
    isovector = [label for label in members if pool[label].isospin == "v"]
    return {"leader": leader, "class": which, "members": members, "children": [c.model for c in p.children],
            "undetermined": p.undetermined,
            "pass": ({c.model for c in p.children} == expected and bool(expected)
                     and all(k.parent == str(parent.resolve()) for k in kids)
                     and sorted(studies.load(parent).children) == sorted(k.folder for k in kids)
                     and all(depth.get(k.folder) == 1 for k in kids)
                     and all(label in p.undetermined for label in isovector))}


def g5(llm, folder: Path) -> dict:
    from adroit.agents.anomaly import AnomalyDrafter, to_yaml, unquoted
    from adroit.retrieval import corpus
    text = corpus.fetch_arxiv_pdf_text("1304.4279")
    draft = AnomalyDrafter(llm, "claude-opus-5-5").run(text, "arXiv:1304.4279")
    (folder / "drafted_cdms_si.yaml").write_text(to_yaml(draft))
    truth = historical.record("cdms_ii_si_2013")
    same = {"target": draft.target == truth["target"],
            "exposure": draft.exposure_kg_day == truth["exposure_kg_day"],
            "window": list(draft.window_kev) == list(truth["window_kev"]),
            "events": sorted(draft.events_kev) == sorted(truth["events_kev"]),
            "background": draft.background_events == truth["background_events"]}
    flagged = unquoted(draft, text)
    eff = any(item.lower().startswith("efficiency") for item in draft.needs_person) and draft.efficiency_points is None
    return {"same": same, "efficiency_for_a_person": eff, "unfound_quotes_flagged": flagged,
            "pass": all(same.values()) and eff and all(any(item.startswith(f) for item in draft.needs_person)
                                                       for f in flagged)}


def main() -> int:
    """G1–G4 ($0), and G5 with --live (paid); returns the exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--budget", type=float, default=0.0)
    parser.add_argument("--resume", action="store_true", help="keep the parts already in the partial record")
    add_out_argument(parser, "dm14")
    args = parser.parse_args()
    if args.resume and not args.out:
        raise SystemExit("--resume needs --out: the folder of the stopped run")
    folder = gate_output("dm14", args.out)
    name = "gate_live" if args.live else "gate"
    partial = folder / f"{name}_partial.json"
    parts = json.loads(partial.read_text()) if args.resume and partial.exists() else {}
    if "G1" not in parts:
        with tempfile.TemporaryDirectory() as scratch:
            parts["G1"] = g1(Path(scratch))
    for key, part in (("G2", g2), ("G3", lambda: g3(folder)), ("G4", lambda: g4(folder))):
        if key not in parts:
            parts[key] = part()
        partial.write_text(json.dumps(parts, indent=1, default=str))
    spent = 0.0
    if args.live:
        from adroit.agents.llm import BudgetedLLMClient, BudgetExceeded, LLMClient
        llm = BudgetedLLMClient(LLMClient(model="claude-opus-5-5", max_tokens=8192), dollar_budget=args.budget)
        try:
            parts["G5"] = g5(llm, folder)
        except BudgetExceeded as error:
            parts["G5"] = {"pass": False, "status": "budget_exhausted", "reason": str(error),
                           "paid_response_ledger": str(llm.ledger_path)}
        spent = llm.spent
    ok = {"G1": all(v["pass"] for v in parts["G1"].values()), "G2": parts["G2"]["pass"],
          "G3": all(v["pass"] for v in parts["G3"].values()), "G4": parts["G4"]["pass"]}
    if "G5" in parts:
        ok["G5"] = parts["G5"]["pass"]
    partial.unlink(missing_ok=True)
    (folder / f"{name}.json").write_text(json.dumps({**parts, "spent": spent}, indent=1, default=str))
    lines = ["# DM14 gate", ""] + [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in ok.items()]
    lines += ["", f"**{'PASSED' if all(ok.values()) else 'NOT PASSED'}**; spent ${spent:.2f}", "", "```",
              json.dumps(parts, indent=1, default=str)[:8000], "```"]
    (folder / f"{name}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:9]))
    print(f"written to {folder}")
    if parts.get("G5", {}).get("status") == "budget_exhausted":
        return BUDGET_STOPPED
    return exit_code(all(ok.values()))


if __name__ == "__main__":
    sys.exit(main())

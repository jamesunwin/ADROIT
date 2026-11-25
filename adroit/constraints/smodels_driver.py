#!/usr/bin/env python3
"""JSON-in / JSON-out driver for SModelS v3 (tested with smodels 3.2.1, database 3.2.1).

Run it with the Python of the SModelS virtual environment, e.g.

    ~/agentic-dm-tools/.venv-smodels/bin/python smodels_driver.py input.json
    echo '{"slha_path": "point.slha"}' | .../python smodels_driver.py -
    .../python smodels_driver.py --slha point.slha [--db /path/official321.pcl]

Input: one JSON object (a single point) or {"points": [obj, obj, ...], <shared keys>}.
The database is loaded once per invocation (official 3.2.1 pickle, 1.1 GB: ~4 s warm,
~20 s cold on Apple silicon; ~1.5 GB RAM), so batch several points per call. Database
path and selection keys are taken from the first point. Only the final JSON is written
to stdout; all SModelS chatter goes to stderr. Exit code 0 unless a global error.

Output (single point; batch mode puts the per-point part in a "points" list):
    versions{smodels,database,python}, database_path, database_load_s,
    slha_path, status ("ok" | "no_results" | "error"), error, warnings, input_warnings,
    input{bsm_particles[...], xsections[...]}  (what SModelS actually read),
    n_topologies, n_results, r_max, excluded (r_max >= 1), analysis, txnames, dataset,
    best_expected{analysis,r_exp,r_obs,txnames},
    results_above_threshold[{analysis, sqrts_tev, lumi_ifb, dataset, data_type, txnames,
        r_obs, r_exp, theory_xsec_fb, ul_obs_fb, ul_exp_fb, max_condition_violation,
        likelihood{nll_mu1, nll_sm, nll_min, muhat, sigma_mu, CLs_mu1, model} | null}],
    combination{analyses, available, r_obs, r_exp, CLs_mu1, nll_mu1, nll_sm} | null,
    coverage{<group>: {description, total_xsec_fb, top[{sms, xsec_fb}]}}, timing_s{...}

Per-point keys (all optional except slha_path):
    slha_path            SLHA file with QNUMBERS, MASS, DECAY and XSECTION blocks
    database             .pcl file, text-database directory, or label "official"
                         (default: $SMODELS_DATABASE or ~/agentic-dm-tools/smodels-db/official321.pcl)
    model                null -> particle content from the QNUMBERS blocks of slha_path;
                         otherwise a SModelS model ("share.models.mssm", "idm", path)
    sqrts_tev            restrict reported results/coverage to this sqrt(s) (default: all)
    sigmacut_fb          0.005    minimal sigma*BR of a simplified-model topology
    minmassgap_gev       5.0      mass compression threshold
    minmassgap_isr_gev   1.0      compression threshold for ISR-type topologies
    maxcond              0.2      maximal condition violation
    prompt_width_gev     1e-11    widths above: prompt decay
    stable_width_gev     1e-25    widths below: detector-stable
    analyses / txnames / datasets / data_types   database selection lists (default ["all"])
    combine_srs          false    use combined-SR likelihoods (pyhf/SLv1/ONNX) where available (slower)
    compute_statistics   true     likelihood information per result
    r_threshold          0.1      list all results with r_obs (or r_exp) >= this
    combine_analyses     null | [ids...] | "atlas_cms_best"  (approximate, assumes uncorrelated analyses)
    coverage             true     missing-topology summary
    n_missing            5        number of missing topologies reported per group
"""
from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import sys
import time
from typing import Any

DEFAULT_DB = os.environ.get(
    "SMODELS_DATABASE",
    os.path.expanduser("~/agentic-dm-tools/smodels-db/official321.pcl"))

DEFAULTS: dict[str, Any] = {
    "database": DEFAULT_DB, "model": None, "sqrts_tev": None,
    "sigmacut_fb": 0.005, "minmassgap_gev": 5.0, "minmassgap_isr_gev": 1.0,
    "maxcond": 0.2, "prompt_width_gev": 1e-11, "stable_width_gev": 1e-25,
    "analyses": ["all"], "txnames": ["all"], "datasets": ["all"],
    "data_types": ["all"], "use_non_validated": False,
    "combine_srs": False, "compute_statistics": True, "r_threshold": 0.1,
    "combine_analyses": None, "coverage": True, "n_missing": 5,
}


class _Collector(logging.Handler):
    """Collects SModelS warnings/errors so they can be returned in the JSON."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Keep each distinct warning or error message once."""
        msg = f"{record.levelname}: {record.getMessage()}"
        if msg not in self.messages:
            self.messages.append(msg)


def _clean(x: Any) -> Any:
    """Make values JSON-safe (NaN/inf -> None, numpy -> python, Unum -> str)."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if isinstance(x, int):
        return x
    return f if math.isfinite(f) else None


def _num(x: Any, unit: Any = None) -> float | None:
    """Unum (or number) -> float in `unit`, None if undefined."""
    if x is None:
        return None
    try:
        v = float(x.asNumber(unit)) if unit is not None and hasattr(x, "asNumber") else float(x)
    except (TypeError, ValueError, AttributeError):
        return None
    return v if math.isfinite(v) else None


def load_database(path: str, cfg: dict[str, Any]) -> Any:
    """Load the SModelS database and apply the result selection.

    Args:
        path: .pcl file, text database folder, or a label such as "official".
        cfg: point configuration (selection keys).

    Returns:
        smodels Database object.
    """
    from smodels.experiment.databaseObj import Database
    with contextlib.redirect_stdout(sys.stderr):
        db = Database(path)
        db.selectExpResults(analysisIDs=cfg["analyses"], txnames=cfg["txnames"],
                            datasetIDs=cfg["datasets"], dataTypes=cfg["data_types"],
                            useNonValidated=cfg["use_non_validated"])
    return db


def build_model(cfg: dict[str, Any]) -> Any:
    """Build the SModelS Model (BSM content from QNUMBERS or a model file) and read the SLHA."""
    from smodels.base.model import Model
    from smodels.base.physicsUnits import GeV
    from smodels.share.models.SMparticles import SMList
    from smodels.tools import particlesLoader
    slha = cfg["slha_path"]
    if cfg["model"] is None:
        bsm = particlesLoader.getParticlesFromSLHA(slha)
    else:  # SModelS copies a model file given by path into the cwd: use a scratch cwd
        import tempfile
        from smodels.base import runtime
        model_file = cfg["model"]
        if os.path.exists(os.path.expanduser(model_file)):
            model_file = os.path.abspath(os.path.expanduser(model_file))
        runtime.modelFile = model_file
        with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
            bsm = particlesLoader.load()
    model = Model(BSMparticles=bsm, SMparticles=SMList)
    model.updateParticles(inputFile=slha, promptWidth=cfg["prompt_width_gev"] * GeV,
                          stableWidth=cfg["stable_width_gev"] * GeV)
    return model


def describe_model(model: Any) -> dict[str, Any]:
    """Masses, widths, decays and cross sections as SModelS understood them."""
    from smodels.base.physicsUnits import GeV, TeV, fb
    parts = []
    for p in model.BSMparticles:
        if not hasattr(p, "pdg") or p.pdg is None or p.pdg < 0:
            continue
        decs = [{"br": d.br, "daughters": list(d.ids)} for d in p.decays if d is not None]
        width = _num(p.totalwidth, GeV)
        status = "stable" if p.isStable() else ("prompt" if p.isPrompt() else "long-lived")
        parts.append({"pdg": p.pdg, "label": p.label, "mass_gev": _num(p.mass, GeV),
                      "width_gev": width, "status": status, "decays": decs})
    xs = [{"pids": list(x.pid), "sqrts_tev": _num(x.info.sqrts, TeV),
           "order": x.info.order, "sigma_fb": _num(x.value, fb)} for x in model.xsections.xSections]
    return {"bsm_particles": parts, "xsections": xs}


def decompose(model: Any, cfg: dict[str, Any]) -> Any:
    """Decompose the model into simplified-model topologies (SMS)."""
    from smodels.base.physicsUnits import GeV, fb
    from smodels.decomposition import decomposer
    return decomposer.decompose(model, cfg["sigmacut_fb"] * fb, massCompress=True,
                                invisibleCompress=True, minmassgap=cfg["minmassgap_gev"] * GeV,
                                minmassgapISR=cfg["minmassgap_isr_gev"] * GeV)


def predictions(db: Any, toplist: Any, cfg: dict[str, Any]) -> list[Any]:
    """Theory predictions (one per analysis: best SR or SR combination), maxcond-filtered."""
    from smodels.matching.theoryPrediction import TheoryPredictionList, theoryPredictionsFor
    preds = theoryPredictionsFor(db, toplist, useBestDataset=True,
                                 combinedResults=cfg["combine_srs"])
    if cfg["compute_statistics"]:
        for tp in preds:
            tp.computeStatistics()
    tpl = TheoryPredictionList(preds, cfg["maxcond"])
    out = [tp for tp in tpl if "CR" not in os.path.basename(str(tp.dataset.path))]
    if cfg["sqrts_tev"] is not None:
        out = [tp for tp in out if abs(_sqrts(tp) - float(cfg["sqrts_tev"])) < 1e-3]
    return out


def _sqrts(tp: Any) -> float:
    from smodels.base.physicsUnits import TeV
    return float(tp.expResult.globalInfo.sqrts.asNumber(TeV))


def _likelihood_info(tp: Any) -> dict[str, Any] | None:
    """nll at mu=1 and mu=0, nll_min, muhat, sigma_mu and CLs(mu=1); None if no likelihood."""
    from smodels.statistics.basicStats import observed
    if tp.statsComputer == "N/A":
        return None
    try:
        st = tp.computeStatistics(observed) or {}
        cls = tp.CLs(1.0, observed)
    except Exception as e:  # noqa: BLE001 - statistical back-ends raise many types
        return {"error": f"{type(e).__name__}: {e}"}
    return {"nll_mu1": st.get("nllbsm"), "nll_sm": st.get("nllsm"),
            "nll_min": st.get("nll_min"), "muhat": st.get("muhat"),
            "sigma_mu": st.get("sigma_mu"), "CLs_mu1": cls,
            "model": sorted({type(c).__name__ for c in getattr(tp.statsComputer, "subComputers", [])})}


def describe_prediction(tp: Any, with_llhd: bool) -> dict[str, Any]:
    """One row of the results table."""
    from smodels.base.physicsUnits import fb
    from smodels.statistics.basicStats import apriori, observed
    gi = tp.expResult.globalInfo
    txn = list(dict.fromkeys(tx.txName for tx in tp.txnames))
    row = {"analysis": gi.id, "sqrts_tev": _sqrts(tp),
           "lumi_ifb": _num(getattr(gi, "lumi", None), 1 / fb),
           "dataset": tp.dataId(), "data_type": tp.dataType(), "txnames": txn,
           "r_obs": _num(tp.getRValue(observed)), "r_exp": _num(tp.getRValue(apriori)),
           "theory_xsec_fb": _num(tp.xsection, fb),
           "ul_obs_fb": _num(tp.getUpperLimit(observed), fb),
           "ul_exp_fb": _num(tp.getUpperLimit(apriori), fb),
           "max_condition_violation": _num(tp.getmaxCondition())}
    if with_llhd:
        row["likelihood"] = _likelihood_info(tp)
    return row


def combine(preds: list[Any], spec: Any) -> dict[str, Any] | None:
    """Approximate analysis combination (product of likelihoods, assumes no correlations)."""
    from smodels.matching.theoryPrediction import TheoryPredictionsCombiner
    from smodels.statistics.basicStats import apriori, observed
    if not spec:
        return None
    if spec == "atlas_cms_best":
        ids = []
        for exp in ("ATLAS", "CMS"):
            cands = [tp for tp in preds if tp.analysisId().startswith(exp) and _sqrts(tp) > 10
                     and tp.statsComputer != "N/A" and tp.getRValue(apriori) is not None]
            if cands:
                ids.append(max(cands, key=lambda t: t.getRValue(apriori)).analysisId())
    else:
        ids = list(spec)
    comb = TheoryPredictionsCombiner.selectResultsFrom(preds, ids)
    if comb is None:
        return {"analyses": ids, "available": False}
    used = [t.analysisId() for t in getattr(comb, "theoryPredictions", [comb])]
    return {"analyses": used, "available": True,
            "r_obs": _num(comb.getRValue(observed)), "r_exp": _num(comb.getRValue(apriori)),
            "CLs_mu1": _num(comb.CLs(1.0, observed)),
            "nll_mu1": _num(comb.nll(1.0)), "nll_sm": _num(comb.nll(0.0))}


def coverage_summary(toplist: Any, cfg: dict[str, Any]) -> dict[str, Any]:
    """Cross section not covered by any database result, by group, plus leading topologies."""
    from smodels.base.physicsUnits import TeV, fb
    from smodels.tools.coverage import Uncovered
    sq = cfg["sqrts_tev"] * TeV if cfg["sqrts_tev"] is not None else None
    unc = Uncovered(toplist, sqrts=sq, sigmacut=cfg["sigmacut_fb"] * fb)
    out: dict[str, Any] = {}
    for g in unc.groups:
        out[g.label] = {"description": g.description,
                        "total_xsec_fb": _num(g.getTotalXSec()),
                        "top": [{"sms": str(s), "xsec_fb": _num(s.missingX)}
                                for s in g.finalStateSMS[:cfg["n_missing"]]]}
    return out


def precheck(path: str) -> list[str]:
    """Cheap textual checks SModelS does not make loudly.

    pyslha silently gives width 0 (i.e. *stable*) to any MASS entry without a DECAY
    block, which would turn e.g. a forgotten coloured mediator into an R-hadron.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"SLHA file not found: {path}")
    masses, decays, nxsec, block = set(), set(), 0, ""
    with open(path) as f:
        for line in f:
            s = line.split("#")[0].strip()
            if not s:
                continue
            tok = s.split()
            head = tok[0].upper()
            if head == "BLOCK":
                block = tok[1].upper() if len(tok) > 1 else ""
            elif head == "DECAY":
                block = "DECAY"
                decays.add(abs(int(tok[1])))
            elif head == "XSECTION":
                block, nxsec = "XSECTION", nxsec + 1
            elif block == "MASS" and line[:1].isspace():
                masses.add(abs(int(tok[0])))
    sm = set(range(1, 7)) | set(range(11, 17)) | set(range(21, 26))
    warn = [f"no DECAY block for PDG {p}: SModelS will treat it as STABLE"
            for p in sorted(masses - decays - sm)]
    if nxsec == 0:
        warn.append("no XSECTION blocks in file")
    return warn


def run_point(db: Any, cfg: dict[str, Any]) -> dict[str, Any]:
    """Run decomposition, matching, statistics and coverage for one SLHA file."""
    t: dict[str, float] = {}
    t0 = time.perf_counter()
    input_warnings = precheck(cfg["slha_path"])
    model = build_model(cfg)
    res: dict[str, Any] = {"slha_path": cfg["slha_path"], "input": describe_model(model),
                           "input_warnings": input_warnings}
    t["model"] = time.perf_counter() - t0
    toplist = decompose(model, cfg)
    t["decomposition"] = time.perf_counter() - t0 - sum(t.values())
    res["n_topologies"] = len(toplist.getSMSList())
    preds = sorted(predictions(db, toplist, cfg),
                   key=lambda p: (p.getRValue() is not None, p.getRValue() or 0.0), reverse=True)
    rows = [describe_prediction(tp, cfg["compute_statistics"]) for tp in preds]
    t["predictions"] = time.perf_counter() - t0 - sum(t.values())
    res.update(_summarise(rows, cfg))
    res["combination"] = combine(preds, cfg["combine_analyses"])
    t["combination"] = time.perf_counter() - t0 - sum(t.values())
    if cfg["coverage"]:
        res["coverage"] = coverage_summary(toplist, cfg)
        res["coverage_sigmacut_fb"] = cfg["sigmacut_fb"]
    t["coverage"] = time.perf_counter() - t0 - sum(t.values())
    t["total"] = time.perf_counter() - t0
    res["timing_s"] = t
    return res


def _summarise(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """r_max, best analysis and the list of results above threshold."""
    thr = cfg["r_threshold"]
    above = [r for r in rows if (r["r_obs"] or 0) >= thr or (r["r_exp"] or 0) >= thr]
    best = next((r for r in rows if r["r_obs"] is not None), None)
    best_exp = max((r for r in rows if r["r_exp"] is not None), key=lambda r: r["r_exp"], default=None)
    return {"status": "ok" if rows else "no_results", "n_results": len(rows),
            "r_max": best["r_obs"] if best else None,
            "excluded": bool(best and best["r_obs"] >= 1.0),
            "analysis": best["analysis"] if best else None,
            "txnames": best["txnames"] if best else None,
            "dataset": best["dataset"] if best else None,
            "best_expected": {k: best_exp[k] for k in ("analysis", "r_exp", "r_obs", "txnames")}
            if best_exp else None,
            "results_above_threshold": above}


def _versions(db: Any) -> dict[str, Any]:
    from smodels import installation
    return {"smodels": installation.version(), "database": db.databaseVersion,
            "python": sys.version.split()[0]}


def _read_input(argv: list[str]) -> dict[str, Any]:
    """Parse CLI: a JSON file, '-' for stdin, or --slha FILE [--db PATH] [--sqrts X]."""
    if len(argv) >= 2 and argv[1] == "--slha":
        cfg: dict[str, Any] = {"slha_path": argv[2]}
        rest = argv[3:]
        for k, key in (("--db", "database"), ("--sqrts", "sqrts_tev")):
            if k in rest:
                v = rest[rest.index(k) + 1]
                cfg[key] = float(v) if key == "sqrts_tev" else v
        return cfg
    if len(argv) < 2 or argv[1] == "-":
        return json.load(sys.stdin)
    with open(argv[1]) as f:
        return json.load(f)


def main(argv: list[str]) -> int:
    """Entry point: prints one JSON document to stdout."""
    collector = _Collector()
    from smodels.base.smodelsLogging import logger, setLogLevel
    setLogLevel("error" if os.environ.get("SMODELS_DRIVER_QUIET", "1") == "1" else "warning")
    logger.addHandler(collector)
    out: dict[str, Any] = {}
    try:
        raw = _read_input(argv)
        shared = {k: v for k, v in raw.items() if k != "points"}
        pts = [{**DEFAULTS, **shared, **p} for p in raw.get("points", [{}])]
        db_path = os.path.expanduser(pts[0]["database"])
        t0 = time.perf_counter()
        db = load_database(db_path, pts[0])
        out = {"versions": _versions(db), "database_path": db_path,
               "database_load_s": time.perf_counter() - t0, "points": []}
        for cfg in pts:
            collector.messages.clear()
            cfg["slha_path"] = os.path.abspath(os.path.expanduser(cfg["slha_path"]))
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    res = run_point(db, cfg)
            except Exception as e:  # noqa: BLE001 - report any failure as JSON
                res = {"slha_path": cfg["slha_path"], "status": "error",
                       "error": f"{type(e).__name__}: {e}"}
            res["warnings"] = list(collector.messages)
            out["points"].append(res)
        if "points" not in raw:
            single = out.pop("points")[0]
            out = {**out, **single}
    except Exception as e:  # noqa: BLE001
        out = {**out, "status": "error", "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(_clean(out), indent=1))
    return 0 if out.get("status", "ok") != "error" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

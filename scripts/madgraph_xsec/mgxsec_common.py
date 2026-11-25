"""Shared helpers for regenerating 13 TeV LO cross-section tables with MadGraph5_aMC@NLO.

Every table is produced the same way:

1. ``generate_process`` writes an MG5 command file (``import model`` / ``generate`` /
   ``output``) and runs it once, producing a MadEvent (or loop-induced MadEvent)
   process directory.
2. ``launch_point`` runs one MG5 ``launch`` per parameter point, setting the
   param-card entries (masses, couplings, widths) and run-card entries (13 TeV,
   PDF, scale choice, number of events) through ``set`` commands, and parses the
   integrated cross-section (pb) from the MG5 output.  Wall time per point is
   recorded.
3. ``write_table`` stores the result as JSON in ``~/agentic-dm-tools/madgraph-xsec``.

Environment assumptions (override with environment variables):
    MG5_PYTHON   python used to run MG5 (default ~/agentic-dm-tools/.venv-mg5/bin/python)
    MG5_DIR      MG5_aMC installation (default ~/agentic-dm-tools/mg5amcnlo-3.8.0)
    XSEC_OUT     output folder for JSON tables (default ~/agentic-dm-tools/madgraph-xsec)
    XSEC_WORK    folder for MG5 process directories (default $XSEC_OUT/work)

The Fortran compiler is whatever MG5's input/mg5_configuration.txt names
(here /usr/local/bin/gfortran, an x86_64 build that runs under Rosetta 2).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

HOME = Path.home()
MG5_PYTHON = Path(os.environ.get("MG5_PYTHON", HOME / "agentic-dm-tools/.venv-mg5/bin/python"))
MG5_DIR = Path(os.environ.get("MG5_DIR", HOME / "agentic-dm-tools/mg5amcnlo-3.8.0"))
UFO_DIR = Path(os.environ.get("UFO_DIR", HOME / "agentic-dm-tools/ufo"))
OUT_DIR = Path(os.environ.get("XSEC_OUT", HOME / "agentic-dm-tools/madgraph-xsec"))
WORK_DIR = Path(os.environ.get("XSEC_WORK", OUT_DIR / "work"))

#: Run-card settings shared by every table (MG5 3.8.0 run_card names).
BASE_RUN_SETTINGS: dict[str, Any] = {
    "ebeam1": 6500.0,            # 13 TeV pp
    "ebeam2": 6500.0,
    "lpp1": 1,
    "lpp2": 1,
    "pdlabel": "nn23lo1",       # NNPDF2.3 LO, alpha_s(MZ)=0.130, MG5 built-in (no LHAPDF here)
    "nevents": 2000,             # only the integral is used
    "use_syst": False,           # systematics module needs LHAPDF
    "dynamical_scale_choice": 4,  # mu_R = mu_F = sqrt(s_hat)  (= M for 2 -> 1)
    "scalefact": 1.0,
    "iseed": 12345,
    "hel_recycling": False,      # avoids a recompilation at every point when some couplings are 0
}

XSEC_RE = re.compile(r"Cross-section :\s+([0-9.eE+\-]+)\s+\+-\s+([0-9.eE+\-]+)\s+pb")


def mg5_binary() -> list[str]:
    """Return the argv prefix that runs MG5_aMC under ``nice``."""
    return ["nice", "-n", "10", str(MG5_PYTHON), str(MG5_DIR / "bin" / "mg5_aMC")]


def run_mg5(commands: str, cmd_file: Path, log_file: Path, timeout: float = 3600.0) -> str:
    """Write ``commands`` to ``cmd_file``, run MG5 on it and return the combined output.

    Args:
        commands: MG5 command script.
        cmd_file: where to store the script (kept for reproducibility).
        log_file: where to store the MG5 stdout/stderr.
        timeout: seconds before the run is killed.

    Returns:
        The MG5 output text.
    """
    cmd_file.parent.mkdir(parents=True, exist_ok=True)
    cmd_file.write_text(commands)
    proc = subprocess.run(mg5_binary() + [str(cmd_file)], cwd=cmd_file.parent,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=timeout)
    log_file.write_text(proc.stdout)
    return proc.stdout


def generate_process(name: str, model: str, processes: Iterable[str],
                     pre_commands: Iterable[str] = (), force: bool = False,
                     post_import: Iterable[str] = ()) -> Path:
    """Create (once) an MG5 process directory ``WORK_DIR/name``.

    Args:
        name: directory name.
        model: argument of ``import model`` (UFO path or MG5 model name, may carry a restriction).
        processes: process lines; the first is passed to ``generate``, the rest to ``add process``.
        pre_commands: MG5 commands issued before ``import model`` (e.g. ``set ninja None``).
        force: regenerate even if the directory exists.
        post_import: MG5 commands issued right after ``import model`` (e.g. ``define p = ...``).

    Returns:
        Path of the process directory.
    """
    procdir = WORK_DIR / name
    if procdir.exists() and (procdir / "bin" / "generate_events").exists() and not force:
        return procdir
    procs = list(processes)
    lines = list(pre_commands) + [f"import model {model}"] + list(post_import)
    lines.append(f"generate {procs[0]}")
    lines += [f"add process {p}" for p in procs[1:]]
    lines.append(f"output {procdir} -f")
    out = run_mg5("\n".join(lines) + "\n", WORK_DIR / f"{name}_generate.mg5",
                  WORK_DIR / f"{name}_generate.log")
    if not (procdir / "bin" / "generate_events").exists():
        raise RuntimeError(f"MG5 output failed for {name}; see log\n{out[-3000:]}")
    return procdir


def configure_single_core(procdir: Path) -> None:
    """Force MadEvent to run sequentially on one core (run_mode = 0, nb_core = 1)."""
    cfg = procdir / "Cards" / "me5_configuration.txt"
    lines = []
    for ln in cfg.read_text().splitlines():
        key = ln.lstrip("# ").split("=")[0].strip()
        if key == "run_mode":
            ln = "run_mode = 0"
        elif key == "nb_core":
            ln = "nb_core = 1"
        lines.append(ln)
    cfg.write_text("\n".join(lines) + "\n")


def _fmt(value: Any) -> str:
    """Format a value for an MG5 ``set`` command."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        return f"{value:.10g}"
    return str(value)


def launch_point(procdir: Path, params: Mapping[str, Any], run_settings: Mapping[str, Any] | None = None,
                 tag: str = "pt", keep_events: bool = False, timeout: float = 3600.0) -> dict[str, Any]:
    """Run one MadEvent integration and return the cross-section.

    Args:
        procdir: MG5 process directory.
        params: param-card entries by UFO parameter name (e.g. {"MY1": 1000, "gVu11": 1}).
        run_settings: run-card overrides on top of :data:`BASE_RUN_SETTINGS`.
        tag: label used for the command/log file names.
        keep_events: keep the Events/run_* folder (default: delete to save disk).
        timeout: seconds before the run is killed.

    Returns:
        dict with sigma_pb, sigma_err_pb, seconds (wall time of the MG5 call) and run name.
    """
    settings = dict(BASE_RUN_SETTINGS)
    settings.update(run_settings or {})
    configure_single_core(procdir)
    (procdir / "RunWeb").unlink(missing_ok=True)   # stale lock from an interrupted run (one job per dir)
    lines = [f"launch {procdir}"]
    lines += [f"set {k} {_fmt(v)}" for k, v in settings.items()]
    lines += [f"set {k} {_fmt(v)}" for k, v in params.items()]
    lines.append("done")
    logdir = procdir / "point_logs"
    logdir.mkdir(exist_ok=True)
    t0 = time.time()
    out = run_mg5("\n".join(lines) + "\n", logdir / f"{tag}.mg5", logdir / f"{tag}.log", timeout)
    seconds = time.time() - t0
    matches = XSEC_RE.findall(out)
    if not matches:
        raise RuntimeError(f"no cross-section found for {tag} in {procdir}; see {logdir / (tag + '.log')}")
    sigma, err = (float(x) for x in matches[-1])
    runs = re.findall(r"Results Summary for run: (\S+)", out)
    run_name = runs[-1] if runs else ""
    if run_name and not keep_events:
        shutil.rmtree(procdir / "Events" / run_name, ignore_errors=True)
    return {"sigma_pb": sigma, "sigma_err_pb": err, "seconds": round(seconds, 1), "run": run_name}


def write_table(filename: str, meta: Mapping[str, Any], columns: list[str], rows: list[list[Any]]) -> Path:
    """Write a JSON table to ``OUT_DIR/filename``.

    Args:
        filename: output file name (``.json``).
        meta: metadata (process, model, couplings, PDF, scales, references ...).
        columns: column names.
        rows: data rows matching ``columns``.

    Returns:
        Path of the written file.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = dict(meta)
    doc.setdefault("sqrts_gev", 13000)
    doc.setdefault("generator", f"MadGraph5_aMC@NLO {(MG5_DIR / 'VERSION').read_text().split()[2]}")
    doc.setdefault("created", _dt.date.today().isoformat())
    doc["units"] = {"mass": "GeV", "sigma": "pb", "seconds": "wall-clock s per MG5 launch (1 core)"}
    doc["columns"] = columns
    doc["data"] = rows
    path = OUT_DIR / filename
    path.write_text(json.dumps(doc, indent=1))
    return path


def mass_grid(lo: float, hi: float, n: int) -> list[float]:
    """Log-spaced grid rounded to 3 significant figures (end points exact)."""
    import math
    pts = []
    for i in range(n):
        x = math.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * i / (n - 1))
        digits = 2 - int(math.floor(math.log10(x)))
        pts.append(float(round(x, digits)))
    pts[0], pts[-1] = float(lo), float(hi)
    return pts


def scan(procdir: Path, masses: list[float], mass_param: str, fixed: Mapping[str, Any],
         run_settings: Mapping[str, Any] | None, label: str,
         extra_params=None) -> list[list[Any]]:
    """Scan one mass parameter; returns rows [mass, sigma_pb, err_pb, seconds].

    ``extra_params(mass)`` may return additional mass-dependent settings (e.g. widths).
    """
    rows = []
    for m in masses:
        params = dict(fixed)
        params[mass_param] = m
        if extra_params:
            params.update(extra_params(m))
        res = launch_point(procdir, params, run_settings, tag=f"{label}_M{m:g}")
        rows.append([m, res["sigma_pb"], res["sigma_err_pb"], res["seconds"]])
        print(f"[{label}] M={m:g} GeV  sigma={res['sigma_pb']:.6g} +- {res['sigma_err_pb']:.2g} pb"
              f"  ({res['seconds']} s)", flush=True)
    return rows

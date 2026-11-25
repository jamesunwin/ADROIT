"""DM15's gate: the workbench's pages, commands, runs, gates, served app and a paid recursion.

    uv run python docs/dm15/gate.py                     # G1-G5 ($0)
    uv run python docs/dm15/gate.py --live --budget 1   # and G6 (the model builder; paid)

Declared in docs/dm15_workbench.md (section 5).

It writes to a new runs/gates/dm15/<UTC> folder unless --out names one (docs/dm15 only to re-record the
tracked receipts). Exit code: 0 passed, 1 not passed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.receipts import add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.orchestrator import studies  # noqa: E402
from adroit.ui import engine, forms  # noqa: E402

HERE = Path(__file__).parent
DOCS = ROOT / "docs"
PORT = 8799
TESTS = {
    "G1": ["tests/ui/test_workbench.py"],
    "G2": ["tests/ui/test_engine_and_forms.py", "-k", "every_wizard_command"],
    "G3": ["tests/ui/test_engine_and_forms.py", "-k", "launched_run or cancelled"],
    "G4": ["tests/ui/test_engine_and_forms.py", "-k", "budget or approved"],
}


def tests(args: list[str]) -> dict:
    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args], cwd=ROOT,
                         capture_output=True, text=True)
    last = (run.stdout.strip().splitlines() or [""])[-1]
    return {"result": last, "pass": run.returncode == 0 and "passed" in last and "skipped" not in last}


def workspace(root: Path) -> Path:
    """G1's runs directory: DM14's promoted tree, a Track 1 study and an idea."""
    shutil.copytree(DOCS / "dm14" / "recursion" / "signal_cdms_si", root / "signal_cdms_si")
    shutil.copytree(DOCS / "dm13" / "reports" / "axial_mediator", root / "track1_axial")
    studies.record(root / "track1_axial", "track1", "Track 1: axial_mediator")
    return root


def get(path: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b""


def g5(root: Path) -> dict:
    env = {**os.environ, "ADROIT_RUNS_DIR": str(root)}
    server = subprocess.Popen([sys.executable, "-m", "adroit.orchestrator.cli", "workbench", "--no-browser",
                               "--port", str(PORT)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                get("/")
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                time.sleep(1.0)
        listen = subprocess.run(["lsof", "-nP", f"-iTCP:{PORT}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
        pages = {p: get(p)[0] for p in ("/", "/study?path=signal_cdms_si", "/new/track1",
                                       "/files/track1_axial/parameter_plane.png")}
        outside = {p: get(p) for p in ("/files/../../../../etc/passwd", "/files/%2e%2e/%2e%2e/etc/passwd")}
        leaked = any(code == 200 and b"root:" in body for code, body in outside.values())
        local = "127.0.0.1:" + str(PORT) in listen and "*:" + str(PORT) not in listen
        return {"pages": pages, "listening_on_localhost_only": local,
                "outside": {p: c for p, (c, _) in outside.items()},
                "pass": local and all(code == 200 for code in pages.values()) and not leaked}
    finally:
        server.terminate()
        server.wait(timeout=30)


def g6(root: Path, budget: float) -> dict:
    parent = root / "signal_cdms_si"
    command = forms.promote_command(parent, ["O1s@10"], budget=budget, uv_models=3, toys=5000, grid=10,
                                    literature=False)
    job_folder = forms.new_folder(parent / "children", "promotion", "O1s@10 with the builder")
    engine.launch(command, job_folder, "promote O1s@10 with the model builder", confirmed_budget=budget)
    deadline = time.time() + 3600
    while engine.poll(job_folder).status == "running" and time.time() < deadline:
        time.sleep(5)
    job = engine.poll(job_folder)
    promotion = json.loads(next(parent.glob("promotion_O1s_10*.json")).read_text())
    idea_studies = [s for _, s in studies.tree(root) if s.kind == "idea"]
    proposals = []
    for s in idea_studies:
        proposals += [m["spec"]["name"] for m in json.loads((Path(s.folder) / "result.json").read_text())["models"]]
    studied = {c["model"] for c in promotion["children"]}
    accounted = all(name in studied or name in promotion["undetermined"] or
                    any(c["model"].startswith(name) for c in promotion["children"]) for name in proposals)
    reported = engine.SPENT.findall((job_folder / engine.LOG).read_text())
    total = studies.total_cost(root)
    return {"status": job.status, "idea_studies": len(idea_studies), "idea_cost": [s.cost_usd for s in idea_studies],
            "proposals": proposals, "studied": sorted(studied), "undetermined": promotion["undetermined"],
            "reported_spend": reported[-1] if reported else None, "tree_total": total,
            "pass": (job.status == "completed" and len(idea_studies) == 1 and idea_studies[0].cost_usd > 0
                     and bool(proposals) and accounted and bool(reported)
                     and abs(float(reported[-1]) - round(total, 2)) < 0.006)}


def main() -> int:
    """G1–G5 ($0), and G6 with --live (paid); returns the exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--budget", type=float, default=1.0)
    add_out_argument(parser, "dm15")
    args = parser.parse_args()
    receipts = gate_output("dm15", args.out)
    parts = {key: tests(spec) for key, spec in TESTS.items()}
    with tempfile.TemporaryDirectory() as folder:
        parts["G5"] = g5(workspace(Path(folder) / "runs"))
    spent = 0.0
    if args.live:
        with tempfile.TemporaryDirectory() as folder:
            parts["G6"] = g6(workspace(Path(folder) / "runs"), args.budget)
            spent = parts["G6"]["tree_total"]
    name = "gate_live" if args.live else "gate"
    (receipts / f"{name}.json").write_text(json.dumps({**parts, "spent": spent}, indent=1, default=str))
    lines = ["# DM15 gate", ""] + [f"- {k}: {'PASS' if v['pass'] else 'FAIL'}" for k, v in parts.items()]
    passed = all(v["pass"] for v in parts.values())
    lines += ["", f"**{'PASSED' if passed else 'NOT PASSED'}**; spent ${spent:.2f}", "", "```",
              json.dumps(parts, indent=1, default=str)[:8000], "```"]
    (receipts / f"{name}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:10]))
    print(f"written to {receipts}")
    return exit_code(passed)


if __name__ == "__main__":
    sys.exit(main())

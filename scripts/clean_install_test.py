"""R11's clean-machine install test: a fresh clone, an empty tools folder, the documented install, the fast suite and
one example of each track. Writes a receipt to docs/receipts/clean_install_<UTC>.md.

    nice -n 10 uv run python scripts/clean_install_test.py WORK_DIR [PYTHON]      # hours (it builds the tools); $0

PYTHON is passed to ``uv sync --python`` (e.g. cpython-3.12-macos-aarch64-none or cpython-3.12-macos-x86_64-none, to
test Apple Silicon and Intel Macs on one machine); by default uv chooses. The tools' own environments follow the
architecture of ADROIT's (``adroit setup``'s {python}).

WORK_DIR must be a path without spaces (Makefile-based tools fail otherwise, docs/dm0_tool_audit.md). The clone is of
the committed HEAD, so uncommitted work is not tested. Every step is run in order and timed; a failing step is
recorded and the test goes on where it can.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Required items are missing until fetched, and the fetch reports the manual ones (MANUAL_REQUIRED) still missing;
# the setup after the documented manual step must exit 0
EXPECTED_NONZERO = {"adroit setup (before fetching)", "adroit setup --fetch"}
# Required items no program may fetch (HEPData serves "Download All" to a browser only): the documented manual step,
# done as a user does it, from this checkout's data/external/manual
MANUAL_REQUIRED = ["lz_2609.02823"]
STEPS = [
    ("clone", ["git", "clone", "--quiet", str(ROOT), "{repo}"], "{work}"),
    ("uv sync (with the ui and retrieval extras)", ["uv", "sync", "--extra", "ui", "--extra", "retrieval", "{python}"],
     "{repo}"),
    ("adroit setup (before fetching)", ["uv", "run", "adroit", "setup"], "{repo}"),
    ("adroit setup --fetch", ["uv", "run", "adroit", "setup", "--fetch"], "{repo}"),
    ("the documented manual downloads (required ones)", ["bash", "-c", "{manual}"], "{repo}"),
    ("adroit setup (after fetching)", ["uv", "run", "adroit", "setup"], "{repo}"),
    ("fast suite", ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider"], "{repo}"),
    ("Track 1 example", ["uv", "run", "adroit", "track1", "--portal", "higgs_portal_scalar", "--no-literature",
                         "--x", "m_chi:10:10000:log:4", "--y", "g_chi:1e-5:10:log:4", "--out", "{work}/runs/track1"],
     "{repo}"),
    ("Track 2 example (the single-idea report)", ["uv", "run", "adroit", "single-idea", "docs/dm13/vector_mediator.yaml",
                                                  "--experiment", "CDMS II Si (2013)", "--masses", "5:40:4", "--toys",
                                                  "2000", "--grid", "4", "--no-literature", "--out", "{work}/runs/single_idea"], "{repo}"),
]


def run(name: str, command: list[str], cwd: str, env: dict[str, str], log: Path) -> tuple[int, float]:
    start = time.time()
    with log.open("a") as handle:
        handle.write(f"\n===== {name}: {' '.join(command)}\n")
        handle.flush()
        code = subprocess.run(command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT).returncode
    return code, time.time() - start


def after_fetching(log: Path) -> list[str]:
    """From the last `adroit setup`'s report: the required/optional count and each item still missing, with why."""
    text = log.read_text(errors="replace").split("===== adroit setup (after fetching)")[-1].split("\n=====")[0]
    lines = [line.strip() for line in text.splitlines()]
    counts = [line for line in lines if line.startswith("Required:")]
    missing = [line[:240] for line in lines if line.startswith("- **")]
    return counts[:1] + missing


def manual_copy(repo: Path) -> str:
    """The shell command that puts each required manual download where the user is told to (``MANUAL_REQUIRED``)."""
    source, target = ROOT / "data" / "external" / "manual", repo / "data" / "external" / "manual"
    copies = " && ".join(f"cp -R {shlex.quote(str(source / name))} {shlex.quote(str(target))}/"
                         for name in MANUAL_REQUIRED)
    return f"mkdir -p {shlex.quote(str(target))} && {copies}"


def passed(rows: list[tuple[str, int, float]]) -> bool:
    return len(rows) == len(STEPS) and all(code == 0 or name in EXPECTED_NONZERO for name, code, _ in rows)


def main(argv: list[str]) -> int:
    work, python = Path(argv[0]).resolve(), (argv[1:] or [""])[0]
    if " " in str(work):
        raise SystemExit("WORK_DIR must not contain spaces")
    work.mkdir(parents=True, exist_ok=True)
    repo, tools = work / "adroit", work / "tools"
    tools.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ADROIT_", "VIRTUAL_ENV"))}
    env.update({"ADROIT_TOOLS_DIR": str(tools), "ADROIT_RUNS_DIR": str(work / "runs"), "OMP_NUM_THREADS": "2"})
    log = work / "clean_install.log"
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rows = []
    for name, command, cwd in STEPS:
        fill = {"repo": str(repo), "work": str(work), "python": f"--python={python}" if python else "",
                "manual": manual_copy(repo)}
        code, seconds = run(name, [c.format(**fill) for c in command if c.format(**fill)], cwd.format(**fill), env, log)
        rows.append((name, code, seconds))
        print(f"{name}: exit {code}, {seconds:.0f} s", flush=True)
        if name in ("clone", "uv sync (with the ui and retrieval extras)") and code != 0:
            break
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    machine = subprocess.run(["uv", "run", "--no-sync", "python", "-c", "import platform; print(platform.machine())"],
                             cwd=repo, env=env, capture_output=True, text=True).stdout.strip() or "unknown"
    lines = [f"# Clean-machine install test ({stamp})", "",
             f"A fresh clone of `{head}` into an empty work folder, with an empty tools folder "
             f"(`ADROIT_TOOLS_DIR`), on {sys.platform}, ADROIT's Python {machine}"
             f"{f' (uv sync --python {python})' if python else ''}; generated by `scripts/clean_install_test.py`. "
             "The full log is "
             "local (`clean_install.log` in the work folder).", "", "| step | exit | time |", "|---|---|---|",
             *[f"| {name} | {code} | {seconds / 60:.1f} min |" for name, code, seconds in rows], "",
             f"**{'PASSED' if passed(rows) else 'FAILED'}** (the first `adroit setup` and the fetch are expected to "
             "exit 1: required items are missing until fetched, and the manual ones until the documented manual step; "
             "the setup after it must exit 0)", "", "After fetching:", "",
             *[f"- {line.lstrip('- ')}" for line in after_fetching(log)]]
    out = ROOT / "docs" / "receipts" / f"clean_install_{stamp}.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0 if passed(rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

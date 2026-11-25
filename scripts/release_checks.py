"""The release checks (R0): one niced command for ruff, the fast and slow suites, the validation scripts and
a read-only ``adroit setup``.

    uv run python scripts/release_checks.py                       # every step (about an hour)
    uv run python scripts/release_checks.py --only ruff,fast      # some steps
    uv run python scripts/release_checks.py --skip slow,optional_backends

Each step runs as its own process at low priority (nice 10) with at most two numerical threads and one
pytest worker. The runner writes a dated receipt, ``docs/receipts/release_checks_<UTC>.md`` and ``.json``
(or to ``--out``): the commit, the tree identities of ``adroit/`` and ``tests/``, and per step its command,
exit code, time, one-line summary and verdict. Full logs go to ``runs/release_checks/<UTC>/`` (not tracked).

Verdicts: ``pass``; ``FAIL``; ``expected failure`` (every failing gate of a validation script is listed in
:data:`EXPECTED` with the document that records it; any other failing gate is a FAIL); ``skipped`` (an optional
step whose preflight, run first, finds its backend unavailable offline, with the reason); ``not established`` (the
browser acceptance layer where this machine has no Chrome: never green, the release's acceptance not established;
the consolidation plan's M4 and the owner's direction D-5, 2026-10-25). Once the preflight passes, any failure of the
step is a FAIL: until the external audit of 2026-10-17 (R17-9) a failed optional step was skipped whenever its log
held a word such as "offline" or "FileNotFoundError". The exit code is 0 when every step passes (or is a documented
failure, or an optional step skipped), else 1.

``fast_without_tools`` runs the fast suite again with an empty tools folder (``ADROIT_TOOLS_DIR``, a fresh temporary
folder), as on a fresh clone before ``adroit setup``: a test needing the tools must say so (``needs``) and skip, never
fail (the audit loop's AL3-16, 2026-11-15).

The acceptance gate (M4): ``acceptance``, the headless journeys of ``tests/ui/acceptance`` (also part of ``fast``,
run again here for their own line), and ``browser_acceptance``, the release layer of ``scripts/browser_acceptance.py``
(a real browser, a real server and the runs' real child processes), run twice in fresh Chrome profiles and followed by
its mutation controls (each audited defect restored in the children must make its journey fail at its invariant).
What each journey substitutes is printed on the receipt.

Ruff is a ratchet: the step passes while the count of violations is at most :data:`RUFF_BASELINE` (the
count at the baseline commit). R11 lowered it to zero (2026-10-12): ruff is clean.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RUFF_BASELINE = 0
THREADS = {name: "2" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                  "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}
# step -> {failing gate (prefix of its row): where it is documented}. Empty since part 2's reference gates were
# re-declared against matched references (docs/portal_library_2.md, 2026-10-10).
EXPECTED: dict[str, dict[str, str]] = {}
TIMEOUT_S = 3 * 3600
# The browser layer's own budget: with the halo journeys (40 journey runs and 20 controls) it takes about 3.2 h on
# this laptop, and on 2026-11-18 it passed 3 h in its last control; the other steps keep 3 h.
BROWSER_TIMEOUT_S = 6 * 3600
NOT_ESTABLISHED = "not established"
BROWSER_NOT_ESTABLISHED = 3           # browser_acceptance.py's exit code without a Chrome
PREFLIGHT_TIMEOUT_S = 900


class Step(BaseModel):
    """One check: its name, its command (from the repository root) and, for an optional backend, the preflight
    command whose failure (and only that) skips it."""

    name: str
    command: list[str]
    optional: bool = False
    preflight: list[str] = Field(default_factory=list)
    empty_tools: bool = False          # run with an empty tools folder (a fresh temporary one)
    timeout_s: int = TIMEOUT_S


class StepResult(BaseModel):
    """What one check did."""

    name: str
    command: str
    returncode: int | None
    seconds: float
    summary: str
    verdict: str
    log: str = ""


class Receipt(BaseModel):
    """The release checks' record."""

    started_utc: str
    commit: str
    adroit_tree: str
    tests_tree: str
    python: str
    ruff_baseline: int
    steps: list[StepResult]

    @property
    def passed(self) -> bool:
        """True when no step failed and the acceptance was established."""
        return all(s.verdict not in ("FAIL", NOT_ESTABLISHED) for s in self.steps)


def steps(log_root: Path) -> list[Step]:
    """Every check, in the order they run."""
    python, scripts = sys.executable, "scripts"
    out = [Step(name="ruff", command=[str(Path(python).parent / "ruff"), "check", "--output-format", "concise", "."]),
           Step(name="fast", command=[python, "-m", "pytest", "-q", "-p", "no:cacheprovider"]),
           Step(name="fast_without_tools", command=[python, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                empty_tools=True),
           Step(name="slow", command=[python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "slow"])]
    out += [Step(name=f"validate_portal_library_{n}", command=[python, f"{scripts}/validate_portal_library_{n}.py"])
            for n in (2, 3, 4, 5)]
    pico = ["uv", "run", "--offline", "--with", "pymupdf", "python", f"{scripts}/validate_native_pico_si.py"]
    backends = [python, f"{scripts}/validate_optional_backends.py"]
    out += [Step(name="validate_native_pico_si", optional=True, command=pico, preflight=[*pico, "--preflight"]),
            Step(name="optional_backends", optional=True,
                 command=[*backends, "--out", str(log_root / "optional_backends")],
                 preflight=[*backends, "--preflight"]),
            Step(name="setup", command=[python, "-m", "adroit.orchestrator.cli", "setup"]),
            Step(name="acceptance", command=[python, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                             "tests/ui/acceptance"]),
            Step(name="browser_acceptance", command=[python, f"{scripts}/browser_acceptance.py", "--repeat", "2",
                                                     "--mutation-controls"], timeout_s=BROWSER_TIMEOUT_S)]
    return out


def summarise(name: str, output: str) -> str:
    """The one-line summary of a step's output."""
    noise = ("it/s]", "Warning:", "warnings.warn")      # progress bars and library warnings are not results
    lines = [line.strip() for line in output.splitlines() if line.strip() and not any(n in line for n in noise)]
    if name == "ruff":
        return ruff_summary(output)
    # a pytest result line whole, its failures and errors first ("2 failed, 3493 passed"): the summary had kept only
    # "3493 passed", hiding the failures beside a FAIL verdict
    tests = r"(?:\d+ \w+, )*\d+ passed.*"
    patterns = {"fast": tests, "fast_without_tools": tests, "slow": tests, "acceptance": tests, "setup": r"Required: .*?present\.",
                "browser_acceptance": r"(?:\d+ of \d+ browser journeys pass.*|release acceptance not established.*)"}
    pattern = patterns.get(name, r"\d+ of \d+ gates pass.*")
    hits = [m.group(0) for line in lines if (m := re.search(pattern, line))]
    return (hits[-1] if hits else lines[-1] if lines else "no output")[:200]


def ruff_summary(output: str) -> str:
    """"N violations" when ruff reported its result, else "ruff did not report a result" (the external audit's A10,
    2026-10-16: a configuration error or a missing command, with no "Found" line, had read as 0 violations)."""
    found = re.search(r"Found (\d+) error", output)
    if found:
        return f"{found.group(1)} violations"
    if "All checks passed!" in output:
        return "0 violations"
    return "ruff did not report a result"


def failing_gates(output: str) -> list[str]:
    """The names of a validation table's failing gates."""
    return [line.split("|")[1].strip() for line in output.splitlines()
            if line.startswith("|") and line.rstrip().endswith("| FAIL |")]


def expected(step: str, output: str) -> bool:
    """True when the step failed only at gates listed as documented failures."""
    allowed = EXPECTED.get(step, {})
    failing = failing_gates(output)
    return bool(failing) and all(any(gate.startswith(name) for name in allowed) for gate in failing)


def verdict(step: Step, returncode: int | None, summary: str, output: str) -> str:
    """pass, FAIL, expected failure or skipped."""
    if step.name == "ruff":
        # exit 0 is clean, exit 1 is violations (within the ratchet's baseline); any other exit is ruff failing to run
        reported = summary.endswith(" violations")
        count = int(summary.split()[0]) if reported else None
        ok = reported and ((returncode == 0 and count == 0) or (returncode == 1 and 0 < count <= RUFF_BASELINE))
    else:
        ok = returncode == 0
    if ok:
        return "pass"
    if step.name == "browser_acceptance" and returncode == BROWSER_NOT_ESTABLISHED:
        return NOT_ESTABLISHED
    if returncode == 1 and expected(step.name, output):
        return "expected failure"
    return "FAIL"


def unavailable(step: Step, env: dict) -> str:
    """Why an optional step's backend is unavailable offline, from its preflight ("" when it is available)."""
    if not step.preflight:
        return ""
    try:
        done = subprocess.run(step.preflight, cwd=ROOT, env=env, capture_output=True, text=True,
                              timeout=PREFLIGHT_TIMEOUT_S, preexec_fn=lambda: os.nice(10))
    except (subprocess.TimeoutExpired, FileNotFoundError) as error:
        return f"preflight did not run: {error}"
    if done.returncode == 0:
        return ""
    lines = [line.strip() for line in (done.stdout + done.stderr).splitlines() if line.strip()]
    return lines[-1] if lines else f"preflight exit {done.returncode}"


def run_step(step: Step, log_root: Path) -> StepResult:
    """Run one check at low priority with at most two threads, and log its output; an optional step whose
    preflight fails is skipped with the preflight's reason."""
    env = {**os.environ, **THREADS, "PYTHONUNBUFFERED": "1"}
    log = log_root / f"{step.name}.log"
    start = time.time()
    if why := unavailable(step, env):
        log.write_text(f"preflight: {why}\n")
        return StepResult(name=step.name, command=" ".join(step.command).replace(str(ROOT) + "/", ""),
                          returncode=None, seconds=round(time.time() - start, 1),
                          summary=f"unavailable offline: {why}"[:200], verdict="skipped",
                          log=str(log.relative_to(ROOT)) if log.is_relative_to(ROOT) else log.name)
    with tempfile.TemporaryDirectory(prefix="adroit-empty-tools-") as empty:
        if step.empty_tools:
            env["ADROIT_TOOLS_DIR"] = empty
        try:
            process = subprocess.run(step.command, cwd=ROOT, env=env, capture_output=True, text=True,
                                     timeout=step.timeout_s, preexec_fn=lambda: os.nice(10))
            output, code = process.stdout + process.stderr, process.returncode
        except subprocess.TimeoutExpired as error:
            output, code = f"{error.stdout or ''}{error.stderr or ''}\ntimed out after {step.timeout_s} s", None
        except FileNotFoundError as error:
            output, code = f"FileNotFoundError: {error}", None
    log.write_text(output)
    summary = summarise(step.name, output)
    if code == 1 and expected(step.name, output):
        summary += f"; documented failures: {', '.join(failing_gates(output))}"
    return StepResult(name=step.name, command=" ".join(step.command).replace(str(ROOT) + "/", ""),
                      returncode=code, seconds=round(time.time() - start, 1), summary=summary,
                      verdict=verdict(step, code, summary, output),
                      log=str(log.relative_to(ROOT)) if log.is_relative_to(ROOT) else log.name)


def identity() -> tuple[str, str, str]:
    """The commit (with '+dirty' when tracked files changed) and the tree identities of adroit/ and tests/."""
    from adroit.orchestrator.track1_identity import tree_identity
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()  # noqa: E731
    head = git("rev-parse", "--short", "HEAD") or "unknown"
    dirty = git("status", "--porcelain", "--untracked-files=no")
    return head + ("+dirty" if dirty else ""), tree_identity(ROOT / "adroit"), tree_identity(ROOT / "tests")


def markdown(receipt: Receipt) -> str:
    """The receipt as Markdown."""
    lines = [f"# Release checks, {receipt.started_utc}", "",
             f"- Commit: `{receipt.commit}`", f"- Tree identity of `adroit/`: `{receipt.adroit_tree}`",
             f"- Tree identity of `tests/`: `{receipt.tests_tree}`", f"- Python: {receipt.python}",
             f"- Ruff ratchet: at most {receipt.ruff_baseline} violations", "",
             "| step | result | summary | exit | seconds |", "|---|---|---|---|---|"]
    lines += [f"| {s.name} | {s.verdict} | {s.summary.replace('|', '/')} | {s.returncode} | {s.seconds:.0f} |"
              for s in receipt.steps]
    lines += ["", f"**{'PASSED' if receipt.passed else 'NOT PASSED'}**: "
              f"{sum(s.verdict == 'pass' for s in receipt.steps)} pass, "
              f"{sum(s.verdict == 'FAIL' for s in receipt.steps)} fail, "
              f"{sum(s.verdict == 'expected failure' for s in receipt.steps)} expected failure, "
              f"{sum(s.verdict == 'skipped' for s in receipt.steps)} skipped"
              + (f", {sum(s.verdict == NOT_ESTABLISHED for s in receipt.steps)} not established (release acceptance "
                 "is not established without the browser layer)" if any(s.verdict == NOT_ESTABLISHED
                                                                         for s in receipt.steps) else "") + ".", "",
              "Commands are run from the repository root at nice 10 with at most two numerical threads.", ""]
    substituted = substitutions(receipt)
    if substituted:
        lines += ["What the acceptance journeys substitute (each journey's `SUBSTITUTED`):", ""] + \
                 [f"- {line}" for line in substituted] + [""]
    return "\n".join(lines)


def substitutions(receipt: Receipt) -> list[str]:
    """The acceptance steps' "SUBSTITUTED" lines, from their logs (the headless gate's conftest prints them; the
    browser layer prints its own), each once."""
    out: list[str] = []
    for step in receipt.steps:
        if step.name not in ("acceptance", "browser_acceptance") or not step.log:
            continue
        path = ROOT / step.log if not Path(step.log).is_absolute() else Path(step.log)
        try:
            text = path.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("SUBSTITUTED"):
                entry = f"{step.name}: {line.removeprefix('SUBSTITUTED').strip(' |:')}"
                if entry not in out:
                    out.append(entry)
    return out


def chosen(all_steps: list[Step], only: str, skip: str) -> list[Step]:
    """The steps named by --only (default all), less those named by --skip."""
    names = {s.name for s in all_steps}
    wanted = set(only.split(",")) if only else names
    dropped = set(skip.split(",")) if skip else set()
    unknown = (wanted | dropped) - names
    if unknown:
        raise SystemExit(f"unknown steps {sorted(unknown)}; known: {', '.join(s.name for s in all_steps)}")
    return [s for s in all_steps if s.name in wanted - dropped]


def main(argv: list[str] | None = None) -> int:
    """Run the chosen steps and write the receipt; returns the exit code."""
    parser = argparse.ArgumentParser(description="ADROIT's release checks")
    parser.add_argument("--only", default="", help="steps, comma-separated (default: all)")
    parser.add_argument("--skip", default="", help="steps to leave out, comma-separated")
    parser.add_argument("--out", default=str(ROOT / "docs" / "receipts"), help="folder for the receipt")
    args = parser.parse_args(argv)
    from adroit.core.config import get_settings
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    log_root = get_settings().runs_dir / "release_checks" / stamp
    log_root.mkdir(parents=True, exist_ok=True)
    commit, adroit_tree, tests_tree = identity()
    results = []
    for step in chosen(steps(log_root), args.only, args.skip):
        print(f"{step.name}: running", flush=True)
        results.append(run_step(step, log_root))
        print(f"{step.name}: {results[-1].verdict}, {results[-1].summary} ({results[-1].seconds:.0f} s)", flush=True)
    receipt = Receipt(started_utc=stamp, commit=commit, adroit_tree=adroit_tree, tests_tree=tests_tree,
                      python=sys.version.split()[0], ruff_baseline=RUFF_BASELINE, steps=results)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"release_checks_{stamp}.json").write_text(receipt.model_dump_json(indent=1))
    (out / f"release_checks_{stamp}.md").write_text(markdown(receipt))
    print(markdown(receipt))
    print(f"receipt: {out / f'release_checks_{stamp}.md'}; logs: {log_root}")
    return 0 if receipt.passed else 1


if __name__ == "__main__":
    sys.exit(main())

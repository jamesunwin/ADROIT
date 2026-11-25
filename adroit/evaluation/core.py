"""The evaluation harness of DM10: cases, halves, runs, the results store and the held-out ledger.

- **Halves.** Every case belongs to the development half or the held-out half,
  by a hash of its suite and id (``half_of``), fixed before any result is seen:
  no case can be moved after the fact.
- **The held-out half** is run only to confirm a change, with a stated reason;
  each such run is written to a ledger (``docs/dm10/held_out_ledger.jsonl``), so
  that how often it was looked at is on record. The owner keeps it: the gate's
  rules, which the owner chooses, are applied to it.
- **The results store.** Every run of a suite is one line of
  ``<store>/<suite>.jsonl``: the commit, the date, the half, each case's result
  and the summary. A held-out run always goes to the tracked store
  ``docs/dm10/results/``, which the gate reads; a development run goes where the
  caller says (``adroit eval`` defaults to ``runs/eval/``, so a routine run never
  changes a tracked receipt).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Callable

from pydantic import Field

from adroit.core.config import child_environment
from adroit.core.state import StrictModel
from adroit.core.chronology import dated_report

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "dm10" / "results"
LEDGER = ROOT / "docs" / "dm10" / "held_out_ledger.jsonl"
SALT = "adroit-dm10-2026-10-01"


class Half(str, Enum):
    """The two halves of a suite: development, and held-out (run only to confirm a change)."""
    development = "development"
    held_out = "held_out"


class Case(StrictModel):
    """One case of a suite: its suite, its id and its inputs."""
    suite: str
    id: str
    inputs: dict = Field(default_factory=dict)

    @property
    def half(self) -> Half:
        """The case's half, fixed by a hash of its suite and id (``half_of``)."""
        return half_of(self.suite, self.id)


class CaseResult(StrictModel):
    """One case's result: passed (None for a measurement, not a verdict), its metrics and a note."""
    case_id: str
    passed: bool | None = None                 # None: the case gives a measurement, not a verdict
    metrics: dict[str, bool | int | float | str] = Field(default_factory=dict)
    note: str = ""


class SuiteRun(StrictModel):
    """One run of a suite: the half, the commit, the date, the reason, each case's result and the summary."""
    suite: str
    half: Half
    commit: str
    date: str
    reason: str = ""
    results: list[CaseResult] = Field(default_factory=list)
    summary: dict[str, int | float | str] = Field(default_factory=dict)


class Suite(StrictModel):
    """A suite: its cases, how one is run, and how the results are summarised."""

    model_config = {"arbitrary_types_allowed": True}
    name: str
    description: str
    cases: Callable[[], list[Case]]
    run_case: Callable[[Case], CaseResult]
    summarise: Callable[[list[CaseResult], list[Case]], dict[str, float | str]]


def half_of(suite: str, case_id: str) -> Half:
    """The case's half, fixed by a hash of the salt, the suite and the id."""
    digest = hashlib.sha256(f"{SALT}:{suite}:{case_id}".encode()).digest()
    return Half.development if digest[0] % 2 == 0 else Half.held_out


OWN_OUTPUTS = ("docs/dm10/results", "docs/dm10/held_out_ledger.jsonl", "docs/dm10/*.md")


def commit() -> str:
    """The repository's commit, with '+dirty' when the working tree has changes.

    The evaluation's own outputs (the results store, the ledger, the reports) are
    not counted: a run that writes them leaves the code at the same commit.
    """
    def git(*args: str) -> str:          # optional locks off: ``core.repro._git``
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              env=child_environment({"GIT_OPTIONAL_LOCKS": "0"})).stdout.strip()
    head = git("rev-parse", "--short", "HEAD") or "unknown"
    excluded = [f":(exclude,glob){path}" + ("/**" if not path.endswith((".jsonl", ".md")) else "")
                for path in OWN_OUTPUTS]
    changed = git("status", "--porcelain", "--untracked-files=no", "--", ".", *excluded)
    return head + ("+dirty" if changed else "")


def run(suite: Suite, half: Half = Half.development, reason: str = "", limit: int | None = None,
        store: bool = True, results_dir: Path | None = None) -> SuiteRun:
    """Run one half of a suite. The held-out half needs a reason, and is entered in the ledger.

    ``results_dir`` is the store for a development run (default: the tracked store); a held-out run
    always goes to the tracked store.
    """
    if half is Half.held_out and not reason.strip():
        raise ValueError("the held-out half is run only to confirm a change: give the reason")
    if half is Half.held_out and results_dir is not None:
        raise ValueError("a held-out run is recorded in the tracked store, which the gate reads: no other folder")
    cases = [c for c in suite.cases() if c.half is half][:limit]
    if half is Half.held_out:            # entered before it runs, so a crashed or unstored run leaves a trace
        _append(LEDGER, json.dumps({"date": date.today().isoformat(), "commit": commit(), "suite": suite.name,
                                    "cases": len(cases), "reason": reason, "event": "started",
                                    "stored": store}))
    out = finish(suite, half, [suite.run_case(c) for c in cases], cases, reason)
    if store:
        save(out, results_dir)
    return out


def finish(suite: Suite, half: Half, results: list[CaseResult], cases: list[Case], reason: str = "") -> SuiteRun:
    """A run from its results (``cases`` those run, in order): the commit, the date and the summary."""
    return SuiteRun(suite=suite.name, half=half, commit=commit(), date=date.today().isoformat(), reason=reason,
                    results=results, summary=suite.summarise(results, cases[:len(results)]))


def save(run_: SuiteRun, results_dir: Path | None = None) -> None:
    """Append the run to its suite's store (``results_dir``, default the tracked one) and, for the held-out
    half, to the ledger."""
    _append((results_dir or RESULTS) / f"{run_.suite}.jsonl", run_.model_dump_json())
    if run_.half is Half.held_out:
        _append(LEDGER, json.dumps({"date": run_.date, "commit": run_.commit, "suite": run_.suite,
                                    "cases": len(run_.results), "reason": run_.reason, "event": "completed"}))


def _append(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(line + "\n")




@dated_report
def report(run_: SuiteRun) -> str:
    """One run in Markdown: the summary, then the failed cases."""
    lines = [f"# {run_.suite}: the {run_.half.value.replace('_', '-')} half", "",
             f"Commit {run_.commit}, {run_.date}" + (f"; reason: {run_.reason}" if run_.reason else "") + ".", "",
             "| measure | value |", "|---|---|", *(f"| {k} | {v} |" for k, v in run_.summary.items())]
    failed = [r for r in run_.results if r.passed is False]
    if failed:
        lines += ["", f"Failed cases ({len(failed)}):", *(f"- {r.case_id}: {r.note}" for r in failed[:40])]
    return "\n".join(lines) + "\n"

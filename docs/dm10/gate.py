"""DM10's gate: the owner's rules G1–G5 (adopted 2026-10-01), applied to the held-out half.

The rules, exactly as adopted (record, section 6):
- G1 limits: every held-out point inside a validated range passes DM3's rule.
- G2 LZ's tables: at least 90% of held-out entries within 0.3σ.
- G3 injection: the class holds the truth in at least 85% of held-out cases,
  and in at least 75% for each target at N ≥ 20 (pooled).
- G4 historical: the system agrees with the literature on every held-out case.
- G5 baselines: on the held-out direct-prompting cases, the system's class
  reading beats each language model's by at least 10 percentage points.

It reads the latest held-out run of each suite from docs/dm10/results/ and runs
nothing itself. It writes gate.md to a new runs/gates/dm10/<UTC> folder unless
--out names one (docs/dm10 only to re-record the tracked receipt). It exits 0 only
when every rule is met. Run from the repository root:

    uv run python docs/dm10/gate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.receipts import add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.evaluation import core  # noqa: E402

MODELS = ["claude-opus-5-5", "gpt-5.6-sol"]


def held_out(suite: str) -> core.SuiteRun | None:
    """The latest held-out run of a suite, if there is one."""
    path = core.RESULTS / f"{suite}.jsonl"
    if not path.exists():
        return None
    runs = [core.SuiteRun.model_validate_json(line) for line in path.read_text().splitlines()]
    runs = [r for r in runs if r.half is core.Half.held_out]
    return runs[-1] if runs else None


def g1(run: core.SuiteRun) -> tuple[bool, str]:
    inside = [r for r in run.results if r.metrics.get("in_validated_range")]
    failed = [r.case_id for r in inside if not r.passed]
    return not failed and bool(inside), f"{len(inside) - len(failed)}/{len(inside)} inside the validated ranges pass" + (
        f"; failed: {', '.join(failed)}" if failed else "") + f" (all points: {sum(bool(r.passed) for r in run.results)}/{len(run.results)})"


def g2(run: core.SuiteRun) -> tuple[bool, str]:
    rate = sum(bool(r.passed) for r in run.results) / len(run.results)
    return rate >= 0.90, f"{rate:.1%} of {len(run.results)} within 0.3σ (rule: ≥ 90%)"


def g3(run: core.SuiteRun) -> tuple[bool, str]:
    rows = [(r.case_id.split("|")[0], int(r.case_id.split("|")[1][2:]), bool(r.metrics["same_class"])) for r in run.results]
    overall = sum(c for _, _, c in rows) / len(rows)
    per = {}
    for target in dict.fromkeys(t for t, _, _ in rows):
        high = [c for t, n, c in rows if t == target and n >= 20]
        per[target] = sum(high) / len(high)
    ok = overall >= 0.85 and all(v >= 0.75 for v in per.values())
    detail = f"class {overall:.1%} of {len(rows)} (rule: ≥ 85%); at N ≥ 20: " + ", ".join(
        f"{t.split()[0]} {v:.1%}" for t, v in per.items()) + " (rule: each ≥ 75%)"
    return ok, detail


def g4(run: core.SuiteRun) -> tuple[bool, str]:
    return all(bool(r.passed) for r in run.results), "; ".join(f"{r.case_id}: {r.note}" for r in run.results)


def g5(system: core.SuiteRun, models: dict[str, core.SuiteRun]) -> tuple[bool, str]:
    mine = {r.case_id: bool(r.metrics["same_class"]) for r in system.results}
    ok, parts = True, []
    for model, run in models.items():
        shared = [r for r in run.results if r.case_id in mine]
        ours = sum(mine[r.case_id] for r in shared) / len(shared)
        theirs = sum(bool(r.metrics["same_class"]) for r in shared) / len(shared)
        ok &= ours - theirs >= 0.10
        parts.append(f"{model}: system {ours:.1%} against {theirs:.1%} on {len(shared)} cases "
                     f"(margin {100 * (ours - theirs):+.1f} points; rule: ≥ +10)")
    return ok and len(models) == len(MODELS), "; ".join(parts)


SUITE_OF = {"G1": "limits", "G2": "lz_tables", "G3": "injection", "G4": "historical", "G5": "injection"}
NAMES = {"G1": "limits", "G2": "LZ's tables", "G3": "injection", "G4": "historical", "G5": "baselines"}


def main(folder: Path | None = None) -> tuple[str, int]:
    """Apply G1–G5 once to the stored held-out runs; the text and the exit code (0 only when every rule is met)."""
    runs = {s: held_out(s) for s in set(SUITE_OF.values())}
    models = {m: run for m in MODELS if (run := held_out(f"direct_prompting_{m}"))}
    apply = {"G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": lambda run: g5(run, models)}
    lines = ["# DM10 gate: the held-out half", "",
             "The owner's rules G1–G5 (adopted 2026-10-01), applied once (`docs/dm10/gate.py`).", "",
             "| rule | suite | held-out run | result | detail |", "|---|---|---|---|---|"]
    verdicts = []
    for rule, suite in SUITE_OF.items():
        run = runs[suite]
        if run is None or (rule == "G5" and not models):
            verdicts.append(None)
            lines.append(f"| {rule} | {NAMES[rule]} | — | not run | |")
            continue
        passed, detail = apply[rule](run)
        verdicts.append(passed)
        lines.append(f"| {rule} | {NAMES[rule]} | {run.commit}, {run.date} | {'PASS' if passed else 'FAIL'} | {detail} |")
    done = [v for v in verdicts if v is not None]
    ending = ("the gate passes." if len(done) == len(verdicts) and all(done) else
              "the gate is not yet complete." if len(done) < len(verdicts) else "the gate does not pass.")
    lines += ["", f"**{sum(done)} of {len(verdicts)} rules met**; {ending}"]
    text = "\n".join(lines) + "\n"
    (gate_output("dm10", folder) / "gate.md").write_text(text)
    return text, exit_code(len(done) == len(verdicts) and all(done))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DM10's held-out gate, applied to stored runs")
    add_out_argument(parser, "dm10")
    report, code = main(parser.parse_args().out or None)
    print(report)
    sys.exit(code)

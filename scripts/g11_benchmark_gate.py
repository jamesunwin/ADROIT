"""G11's gate, the literature-benchmark agent: for every development-half zoo entry, the agent reads the paper and
extracts its benchmarks (``agents.benchmarks``); a zoo target is recovered if a target that passes the quote check
has the same quantity and a value within ``MATCH`` (in ADROIT's units). The gate: at least half the development
targets recovered, and no quote failing the check.

Paid (the owner's $10 for G10–G11); ``--dry-run`` feeds the zoo's own targets through the offline fake ($0).

    .venv/bin/python scripts/g11_benchmark_gate.py --dry-run
    .venv/bin/python scripts/g11_benchmark_gate.py --budget 3 --out docs/g11/benchmark_results.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from g10_intake_gate import pdf  # noqa: E402

MATCH = 0.02
PAPER_CHARS = 110_000                      # the paper's first ~40 pages: the cost's bound


def pages(arxiv: str) -> list[str]:
    """The paper's text page by page (pdftotext's form feeds), cut at ``PAPER_CHARS`` in total."""
    text = subprocess.run(["pdftotext", str(pdf(arxiv)), "-"], capture_output=True, text=True, timeout=300).stdout
    out, total = [], 0
    for page in text.split("\f"):
        if total + len(page) > PAPER_CHARS:
            break
        out.append(page)
        total += len(page)
    return out


def description(entry) -> str:
    """What the agent is told about the model: its title, its paper's Lagrangian, its fields."""
    fields = ", ".join(f"{f['name']} (spin {f['spin']}, {f.get('role')})" for f in entry.spec.get("fields", []))
    return f"{entry.title}\nLagrangian: {entry.lagrangian.get('latex', '')}\nFields: {fields}"


def recovered(target, found: list) -> bool:
    from adroit.agents.benchmarks import in_adroit_units
    for t in found:
        if t.quantity == target.quantity:
            value = in_adroit_units(t)
            if abs(value - target.value) <= MATCH * abs(target.value):
                return True
    return False


def run(dry: bool, budget: float, out: Path, model: str) -> dict:
    from adroit.agents.benchmarks import BenchmarkAgent, Benchmarks, BenchmarkTarget
    from adroit.agents.llm import BudgetedLLMClient, FakeLLMClient, LLMClient
    from adroit.evaluation import core, zoo
    entries = [e for e in zoo.entries() if core.half_of("model_zoo", e.id).value == "development"]
    if dry:
        canned = []
        for e in entries:
            for arxiv in sorted({t.source.arxiv or e.reference["arxiv"] for t in e.targets}):
                canned.append(Benchmarks(targets=[BenchmarkTarget(
                    quantity=t.quantity, value=t.value, page=t.source.page, quote=t.source.quote,
                    location=t.source.location or "",
                    unit="cm2" if t.quantity == "sigma_si_cm2" else "GeV" if t.quantity == "thermal_mass_gev" else "")
                    for t in e.targets if (t.source.arxiv or e.reference["arxiv"]) == arxiv]))
        llm = FakeLLMClient(canned)
    else:
        llm = BudgetedLLMClient(LLMClient(model=model, max_tokens=8192), dollar_budget=budget)
    agent = BenchmarkAgent(llm, model)
    rows, total, hits, failures = [], 0, 0, 0
    for e in entries:
        sources = sorted({t.source.arxiv or e.reference["arxiv"] for t in e.targets})
        row = {"id": e.id, "papers": sources, "targets": len(e.targets), "kept": [], "dropped": []}
        kept_all = []
        try:
            for arxiv in sources:                       # each target is sought in its own source paper
                kept, dropped = agent.run(description(e), pages(arxiv), run_id=f"g11-{e.id}-{arxiv}")
                kept_all += kept
                row["kept"] += [t.model_dump() | {"paper": arxiv} for t in kept]
                row["dropped"] += [{"target": t.model_dump(), "why": why, "paper": arxiv} for t, why in dropped]
            found = [recovered(t, kept_all) for t in e.targets]
            row["recovered"] = sum(found)
            total, hits, failures = total + len(e.targets), hits + sum(found), failures + len(row["dropped"])
        except Exception as error:                     # noqa: BLE001 - a failure is a finding
            row["error"] = f"{type(error).__name__}: {error}"[:400]
            total, failures = total + len(e.targets), failures + len(row["dropped"])
        row["spent"] = getattr(llm, "spent", 0.0)
        rows.append(row)
        print(f"{e.id}: {row.get('recovered', 0)}/{len(e.targets)} recovered, {len(row.get('dropped', []))} dropped "
              f"(spent ${row['spent']:.3f})", flush=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"model": model, "dry_run": dry, "results": rows}, indent=1))
    summary = {"development_targets": total, "recovered": hits, "quotes_failing": failures,
               "gate": hits * 2 >= total and failures == 0, "spent": getattr(llm, "spent", 0.0),
               "budget_stopped": any("BudgetExceeded" in r.get("error", "") for r in rows)}
    out.write_text(json.dumps({"model": model, "dry_run": dry, "summary": summary, "results": rows}, indent=1))
    return summary


def recheck(path: Path) -> dict:
    """Every stored target, kept or dropped, through today's quote check again ($0), and the gate recomputed."""
    from adroit.agents.benchmarks import BenchmarkTarget, quote_check
    from adroit.evaluation import zoo
    data = json.loads(path.read_text())
    by = {e.id: e for e in zoo.entries()}
    cache: dict[str, list[str]] = {}
    total = hits = failures = 0
    for row in data["results"]:
        if "error" in row:                              # an entry that failed counts its targets, as ``run`` does
            total += len(by[row["id"]].targets)
            continue
        passing, failing = [], []
        for item in row["kept"] + [d["target"] | {"paper": d["paper"]} for d in row["dropped"]]:
            target = BenchmarkTarget.model_validate({k: v for k, v in item.items() if k != "paper"})
            why = quote_check(target, cache.setdefault(item["paper"], pages(item["paper"])))
            (failing if why else passing).append((target, why))
        e = by[row["id"]]
        found = [recovered(t, [x for x, _ in passing]) for t in e.targets]
        row["recheck"] = {"passing": len(passing), "failing": [{"quote": x.quote, "why": w} for x, w in failing],
                          "recovered": sum(found)}
        total, hits, failures = total + len(e.targets), hits + sum(found), failures + len(failing)
    data["recheck_summary"] = {"development_targets": total, "recovered": hits, "quotes_failing": failures,
                               "gate": hits * 2 >= total and failures == 0,
                               "note": "the stored targets through the quote check as it is now ($0)"}
    path.write_text(json.dumps(data, indent=1))
    return data["recheck_summary"]


def main() -> int:
    """Run (or re-check) the gate; the exit code is 0 met, 1 not met, 3 stopped at the budget
    (``core.receipts``)."""
    from adroit.core.receipts import BUDGET_STOPPED, exit_code
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--budget", type=float, default=3.0)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--out", default="runs/g11/benchmark_dry.json")
    parser.add_argument("--recheck", action="store_true", help="check the stored targets in --out again ($0)")
    args = parser.parse_args()
    summary = recheck(Path(args.out)) if args.recheck else run(args.dry_run, args.budget, Path(args.out), args.model)
    print(summary)
    return BUDGET_STOPPED if summary.get("budget_stopped") else exit_code(summary["gate"])


if __name__ == "__main__":
    sys.exit(main())

"""The DM9 gate: no unverified reference in any report, over twenty runs.

The runs (declared in docs/dm9_agents.md, section 5, before the paid run):
- Path 2, DM6's stored LZ result (docs/dm6/lz_case.json): variants, the scout on the
  three leading candidates, and the audit; six runs, to see how the agents vary;
- Path 1, the scout and the audit on bespoke models: the ten DM8 gate models (the
  deriver's half, the live gate's record (dm8)), once each, and the worked example
  (docs/dm8/majorana_scalar/result.json), four times.

The measure, on each run's final report: ``references.unverified_in``. It counts every
arXiv identifier or DOI not confirmed by arXiv or Crossref, and every author–year
citation. The gate passes if the twenty reports hold none.

    uv run python docs/dm9/gate.py --dry-run           # $0: scripted agents, fake services
    uv run python docs/dm9/gate.py --live --budget 8   # paid: only with the owner's approval

Both write to a new runs/gates/dm9/<UTC> folder unless --out names one (docs/dm9 only to
re-record the tracked receipts). Exit code: 0 passed, 1 not passed, 3 stopped at the budget.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.agents.audit import AuditEntry, AuditReport  # noqa: E402
from adroit.agents.llm import FakeLLMClient  # noqa: E402
from adroit.agents.scout import ProposedConstraint, ScoutReport  # noqa: E402
from adroit.agents.variants import VariantChoices, VariantPick  # noqa: E402
from adroit.core.receipts import BUDGET_STOPPED, add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.orchestrator import agents, assumptions, lagrangian, signal  # noqa: E402
from adroit.retrieval import literature  # noqa: E402
from adroit.retrieval import references as refs  # noqa: E402

HERE = Path(__file__).parent
DOCS = HERE.parent
TITLE = "Implications of unitarity and gauge invariance for simplified dark matter models"


def subjects() -> list[tuple[str, str, object]]:
    """(name, path, result) for the twenty runs, in order."""
    lz = signal.SignalResult.model_validate_json((DOCS / "dm6/lz_case.json").read_text())
    gate = json.loads((DOCS / "the live gate's record (dm8)").read_text())["models"]
    example = lagrangian.LagrangianResult.model_validate_json((DOCS / "dm8/majorana_scalar/result.json").read_text())
    out = [(f"LZ (Path 2), run {i + 1}", "path2", lz) for i in range(6)]
    out += [(f"{g['id']} (Path 1)", "path1", lagrangian.LagrangianResult.model_validate(g["result"])) for g in gate]
    out += [(f"majorana_scalar (Path 1), run {i + 1}", "path1", example) for i in range(4)]
    return out


def _scripted(kind: str, result) -> FakeLLMClient:
    """Agents that misbehave: a hallucinated reference, a wrong title, author–year text, a stray identifier."""
    scout = ScoutReport(proposals=[
        ProposedConstraint(name="unitarity, as Smith et al. (2019) found", constraint_class="collider",
                           reference="1510.02110", title=TITLE, applicability="applies"),
        ProposedConstraint(name="invented", constraint_class="relic_density", reference="2612.99999",
                           title="A paper that does not exist", applicability="applies"),
        ProposedConstraint(name="real identifier, wrong paper", constraint_class="cosmology",
                           reference="1510.02110", title="Neutrino masses in extra dimensions",
                           applicability="needs_calculation", needed_calculation="x")])
    inv = assumptions.path2(result) if kind == "path2" else assumptions.path1(result)
    audit = AuditReport(entries=[AuditEntry(id=i.id, impact="minor", effect="see arXiv:9999.12345")
                                 for i in inv.items], additional=["Jones et al. 2020 disagree"])
    if kind == "path2":
        return FakeLLMClient([VariantChoices(picks=[VariantPick(index=0, rationale="per Brown et al.")]),
                              scout, scout, scout, audit])
    return FakeLLMClient([scout, audit])


def run(kind: str, result, llm, tools: agents.Tools) -> agents.AgentResult:
    if kind == "path2":
        return agents.run_path2(result, llm, agents.AgentRequest(), tools)
    return agents.run_path1(result, llm, agents.AgentRequest(), tools)


def row(name: str, r: agents.AgentResult) -> dict:
    """What one run shows."""
    vetted = [v for vs in r.scouting.values() for v in vs]
    return {"run": name, "unverified_in_report": r.report_unverified,
            "proposed": len(vetted), "confirmed": sum(v.kept for v in vetted),
            "dropped": [v.reason for v in vetted if not v.kept],
            "rule_corrections": sum(len(v.changes) for v in vetted),
            "audit_items": len(r.inventory.items) if r.inventory else 0, "audit_missing": r.audit_missing,
            "audit_additional": len(r.audit.additional) if r.audit else 0,
            "variants_chosen": len(r.variants), "variants_joined": sum(o.joined for o in r.variants),
            "picks_discarded": len(r.discarded_picks)}


def line(x: dict) -> str:
    verdict = "PASS" if not x["unverified_in_report"] else f"FAIL {x['unverified_in_report']}"
    return (f"{x['run']:40s} {verdict}  references {x['confirmed']}/{x['proposed']} confirmed; "
            f"audit {x['audit_items'] - len(x['audit_missing'])}/{x['audit_items']}; variants "
            f"{x['variants_joined']}/{x['variants_chosen']} joined, {x['picks_discarded']} picks discarded")


def dry_run() -> tuple[str, bool]:
    """Scripted agents and fake services; the text, and whether every report is clean while the control on raw
    agent text still finds the planted references."""
    known = {"1510.02110": refs.Reference(kind="arxiv", id="1510.02110", title=TITLE, year=2015, verified=True),
             **{i: refs.Reference(kind="arxiv", id=i, title="cited by ADROIT's code", verified=True)
                for i in ("2105.00599", "1612.05949", "2405.13778", "1503.02641", "1308.6288")}}
    tmp = Path(tempfile.mkdtemp())
    tools = agents.Tools(resolver=lambda asked: {a.id: known[a.id] for a in asked if a.id in known},
                         fetch=lambda q, n: [literature.Abstract(arxiv_id="1510.02110", title=TITLE, query=q)],
                         literature_cache=tmp / "lit.json")
    rows = [row(name, run(kind, result, _scripted(kind, result), tools)) for name, kind, result in subjects()]
    passed = sum(not x["unverified_in_report"] for x in rows)
    control = refs.unverified_in("raw agent text: arXiv:2612.99999, as Smith et al. (2019) say",
                                 resolver=tools.resolver)
    ok = passed == len(rows) == 20 and bool(control)
    return ("DM9 gate, dry run: scripted agents that misbehave, fake literature and reference services ($0)\n\n"
            + "\n".join(map(line, rows))
            + f"\n\n{passed}/{len(rows)} reports hold no unconfirmed reference.\n"
            + f"Control: the measure on raw agent text finds {control}.\n"
            + f"Gate: {'PASSED' if ok else 'NOT PASSED'}\n"), ok


def live(budget: float, model: str, folder: Path) -> tuple[str, int]:
    """The paid run; the text and the exit code."""
    from adroit.agents.llm import BudgetedLLMClient, BudgetExceeded, LLMClient
    llm = BudgetedLLMClient(LLMClient(model=model, max_tokens=8192), dollar_budget=budget)
    tools = agents.Tools(cache=refs.ReferenceCache())
    (folder / "reports").mkdir(exist_ok=True)
    rows, stopped = [], False
    for n, (name, kind, result) in enumerate(subjects(), start=1):
        try:
            r = run(kind, result, llm, tools)
        except BudgetExceeded as error:
            stopped = True
            (folder / "gate_live.json").write_text(json.dumps({"rows": rows, "spent": llm.spent,
                "status": "budget_exhausted", "reason": str(error), "paid_response_ledger": str(llm.ledger_path)}, indent=1))
            break
        (folder / "reports" / f"run_{n:02d}.md").write_text(agents.report(r))
        rows.append(row(name, r))
        (folder / "gate_live.json").write_text(json.dumps({"rows": rows, "spent": llm.spent}, indent=1))
        print(line(rows[-1]), flush=True)
    passed = sum(not x["unverified_in_report"] for x in rows)
    text = (f"# DM9 gate, live run ({model})\n\n" + "\n".join(map(line, rows))
            + f"\n\n{passed}/{len(rows)} reports hold no unconfirmed reference; spent ${llm.spent:.2f}.\n")
    (folder / "gate_live.md").write_text(text)
    return text, BUDGET_STOPPED if stopped else exit_code(passed == len(rows) == len(subjects()))


def main() -> int:
    """--dry-run ($0) or --live (paid); returns the exit code."""
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--model", default="claude-opus-5-5")
    add_out_argument(parser, "dm9")
    args = parser.parse_args()
    if args.live and args.budget is None:
        raise SystemExit("--live needs --budget")
    folder = gate_output("dm9", args.out)
    if args.dry_run:
        text, passed = dry_run()
        (folder / "gate_dry_run.txt").write_text(text)
        code = exit_code(passed)
    else:
        text, code = live(args.budget, args.model, folder)
    print(text)
    print(f"written to {folder}")
    return code


if __name__ == "__main__":
    sys.exit(main())

"""The live gate of "only usable models from the model builder" (the owner, 2026-11-21; the usable models plan,
section 5, declared before the first run):

- twelve varied ideas, the owner's two models of 2026-11-21 included, go through the real builder (``ideas.run``: the
  proposals, then the values, then the deterministic completion);
- it passes if **every offered model is usable** (``library.personal.usable``, with a Track 1 engine) **and at least 10
  of the 12 ideas give at least one usable model**;
- cap: $3.

    uv run python docs/usable_models/gate.py --dry-run               # a scripted builder ($0): the mechanics only
    uv run python docs/usable_models/gate.py --live --budget 3        # claude-opus-5-5 (paid)

Writes to a new runs/gates/usable_models/<UTC> folder unless --out names one. Exit code: 0 passed, 1 not passed,
3 stopped at the budget.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.receipts import BUDGET_STOPPED, add_out_argument, exit_code, gate_output  # noqa: E402

IDEAS = [
    "scalar dark matter that talks to the Standard Model only through the Higgs boson",
    "a Dirac fermion dark matter particle that interacts with quarks through a new heavy neutral vector boson",
    "dark matter as the neutral component of a single electroweak multiplet, stable without any new symmetry",
    "an inert second Higgs doublet whose lightest neutral component is the dark matter",
    "hidden-sector Dirac dark matter charged under a dark U(1) whose gauge boson kinetically mixes with hypercharge",
    "a wino-like dark matter candidate",
    "Majorana dark matter coupling to right-handed up quarks through a coloured scalar mediator (t-channel)",
    "Majorana dark matter coupling to right-handed muons through a charged scalar partner",
    "Dirac fermion dark matter with a pseudoscalar mediator coupling to Standard Model fermions in proportion to "
    "their Yukawas",
    "Dirac dark matter charged under a gauged L_mu - L_tau symmetry",
    "Vectorlike Y=1 quintuplet with dimension-7 Majorana splitting",                       # the owner's, 2026-11-21
    "Tau-philic U(1) Z' with Dirac singlet DM (simplified model)",                        # the owner's, 2026-11-21
]


def one(idea: str, llm) -> dict:
    """One idea through the builder: what was offered (each re-checked) and what was not, with why."""
    from adroit.library.personal import support, usable
    from adroit.orchestrator import ideas
    result = ideas.run(ideas.IdeaRequest(text=idea), llm)
    offered = []
    for m in result.models:
        verdict, s = usable(m.general), support(m.general)
        offered.append({"name": m.general.name, "usable": verdict.ok and bool(s["track1_engine"]),
                        "blocking": verdict.blocking, "engine": s.get("track1_engine"),
                        "fields": [f.name for f in m.general.fields],
                        "values": {c.name: c.value for c in m.general.couplings},
                        "left_out": m.general.dropped})
    return {"idea": idea, "offered": offered, "not_offered": result.dropped,
            "usable_count": sum(o["usable"] for o in offered)}


def run_all(llm) -> list[dict]:
    from adroit.agents.llm import BudgetExceeded
    rows = []
    for idea in IDEAS:
        try:
            rows.append(one(idea, llm))
        except BudgetExceeded as error:
            rows.append({"idea": idea, "offered": [], "not_offered": [], "usable_count": 0,
                         "status": "budget_exhausted", "reason": str(error)})
            break
    return rows


def scripted():
    """The dry run's builder: the singlet, the tau-philic Z′ and the quintuplet of the tests, in turn."""
    from adroit.agents.ideas import ModelProposal, ModelProposals, ValueProposals
    from adroit.agents.llm import FakeLLMClient
    from tests.model_building.test_usable_models import CHI, QUINTUPLET, TAU_L, TAU_R, ZP, values
    from tests.ui.test_usable_models_ui import SINGLET
    replies = [
        [ModelProposals(proposals=[ModelProposal(name="singlet", fields=[SINGLET])]),
         ValueProposals(models=[values(("lam_H_S", 0.1))])],
        [ModelProposals(proposals=[ModelProposal(name="Tau-philic Z'", fields=[CHI, ZP, TAU_L, TAU_R])]),
         ValueProposals(models=[values(("g_Zp_chi_v", 0.5), ("g_Zp_L_1", 0.3), ("g_Zp_eR_1", 0.3))])],
        [ModelProposals(proposals=[ModelProposal(name="Y=1 quintuplet", fields=[QUINTUPLET])]),
         ValueProposals(models=[values()])],
    ]
    return FakeLLMClient([r for i in range(len(IDEAS)) for r in replies[i % 3]])


def verdict(rows: list[dict]) -> tuple[bool, str]:
    checks = {
        "every offered model is usable": all(o["usable"] for r in rows for o in r["offered"]),
        f"at least 10 of {len(IDEAS)} ideas give a usable model": sum(r["usable_count"] > 0 for r in rows) >= 10,
        "every idea ran": len(rows) == len(IDEAS) and not any(r.get("status") for r in rows),
    }
    return all(checks.values()), "\n".join(f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in checks.items())


def report(rows: list[dict], label: str, passed: bool, lines: str, spent: float) -> str:
    out = [f"# Usable models: the live gate, {label}", "", lines, "",
           f"**{'PASSED' if passed else 'NOT PASSED'}**; spent ${spent:.4f}.", ""]
    for r in rows:
        out.append(f"## {r['idea']}")
        out.append(f"usable models offered: {r['usable_count']}" + (f" ({r['status']})" if r.get("status") else ""))
        for o in r["offered"]:
            out.append(f"- offered: **{o['name']}** (usable: {o['usable']}; engine: {o['engine']}); "
                       f"fields {', '.join(o['fields'])}; values {o['values']}")
            out += [f"  - left out: {d}" for d in o["left_out"]]
        out += [f"- not offered: {d}" for d in r["not_offered"]]
        out.append("")
    return "\n".join(out)


def main() -> int:
    """Run the twelve ideas; returns the exit code."""
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--budget", type=float, default=3.0)
    parser.add_argument("--model", default="claude-opus-5-5")
    add_out_argument(parser, "usable_models")
    args = parser.parse_args()
    if args.budget > 3.0:
        parser.error("the owner's cap for this gate is $3")
    folder = gate_output("usable_models", args.out)
    if args.dry_run:
        rows, spent, label = run_all(scripted()), 0.0, "dry run (scripted builder)"
    else:
        from adroit.agents.llm import BudgetedLLMClient, client_for
        llm = BudgetedLLMClient(client_for(args.model), dollar_budget=args.budget)
        rows, label = run_all(llm), f"live ({args.model})"
        spent = llm.spent
    passed, lines = verdict(rows)
    name = "gate_dry_run" if args.dry_run else "gate_live"
    (folder / f"{name}.json").write_text(json.dumps({"rows": rows, "spent": spent, "passed": passed}, indent=1,
                                                    default=str))
    text = report(rows, label, passed, lines, spent)
    (folder / f"{name}.md").write_text(text)
    print(text)
    print(f"written to {folder}")
    return BUDGET_STOPPED if any(r.get("status") == "budget_exhausted" for r in rows) else exit_code(passed)


if __name__ == "__main__":
    sys.exit(main())

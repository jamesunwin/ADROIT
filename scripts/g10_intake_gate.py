"""G10's gate: every zoo entry's Lagrangian read by the canonical intake agent (``agents.canonical_intake``), from
the paper's own text around it and the benchmark's inputs, and compared with the zoo's hand-written model
(``model_building.equivalence``: the same spectrum and vertices).

Paid (the owner's $10 for G10–G11); ``--dry-run`` replays the hand-written models through the offline fake ($0).
Papers are fetched once from arXiv into the tools folder, with a generic User-Agent.

    .venv/bin/python scripts/g10_intake_gate.py --dry-run
    .venv/bin/python scripts/g10_intake_gate.py --budget 4 --out docs/g10/intake_results.json
"""

from __future__ import annotations

import argparse
import sys
import json
import subprocess
import time
from pathlib import Path

UA = "adroit (research software; fetches public papers)"
EXCERPT_CHARS = 14000


def papers_dir() -> Path:
    from adroit.core.config import get_settings
    folder = get_settings().tools_dir / "papers"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def pdf(arxiv: str) -> Path:
    """The paper's PDF, fetched once (generic User-Agent; no name or address in the request)."""
    import requests
    path = papers_dir() / f"{arxiv.replace('/', '_')}.pdf"
    if not path.exists() or path.stat().st_size < 10_000:
        response = requests.get(f"https://arxiv.org/pdf/{arxiv}", headers={"User-Agent": UA}, timeout=120)
        response.raise_for_status()
        path.write_bytes(response.content)
        time.sleep(3.0)                                   # arXiv's courtesy interval
    return path


def excerpt(arxiv: str, page: int, around: int = 1) -> str:
    """The text of the pages around the Lagrangian's (1-based), from pdftotext."""
    first, last = max(1, page - around), page + around
    done = subprocess.run(["pdftotext", "-f", str(first), "-l", str(last), str(pdf(arxiv)), "-"],
                          capture_output=True, text=True, timeout=120)
    return done.stdout[:EXCERPT_CHARS]


REGULATOR = 1e-3        # a partner ratio this close to 1 is the engine's device for an exact degeneracy (D19)


def reference(e, exact: bool = False):
    """The zoo's model at the benchmark the agent is told: for a thermal-mass target, the spec with the dark matter
    (or the scanned field) at the stated mass and a tied partner at ``mediator_ratio`` times it, as the zoo
    computes it (the spec's own mass is only a starting value there). With ``exact`` (decision D19), a ratio within
    ``REGULATOR`` of 1, the engine's regulator (it needs m_φ > m_χ), is the paper's exact degeneracy."""
    from adroit.evaluation import zoo
    from adroit.parameter_space.portals import generic as gm
    target = e.targets[0]
    spec = zoo._spec(e, target)
    if target.quantity == "thermal_splitting" and target.tied:     # the partner at the stated splitting
        light = spec.field(target.scan or gm._dm_field(spec)).mass_gev
        return gm._set(spec, target.tied, light * (1.0 + target.value))
    if target.quantity != "thermal_mass_gev":
        return spec
    spec = gm._set(spec, target.scan or gm._dm_field(spec), target.value)
    if target.tied and target.mediator_ratio:
        ratio = target.mediator_ratio
        if exact and abs(ratio - 1.0) <= REGULATOR:
            ratio = 1.0
        spec = gm._set(spec, target.tied, ratio * target.value)
    return spec


def judge(agent, e) -> dict:
    """The strict comparison and decision D19's (the SM-like h set aside where it meets no new state; a degenerate
    partner at the paper's exact degeneracy)."""
    from adroit.model_building import equivalence
    strict = equivalence.compare(agent, reference(e))
    d19 = strict if strict.equal else equivalence.compare(agent, reference(e, exact=True), d19=True)
    return {"equal": strict.equal, "differences": strict.differences[:6], "equal_d19": d19.equal,
            "differences_d19": d19.differences[:6]}


def cases(only: list[str] | None = None) -> list[tuple]:
    """(entry, reference model, the agent's message) for each zoo entry."""
    from adroit.agents.canonical_intake import source_message
    from adroit.evaluation import zoo
    out = []
    for e in zoo.entries():
        if only and e.id not in only:
            continue
        ref, lag, target = e.reference, e.lagrangian, e.targets[0]
        text = excerpt(ref["arxiv"], int(lag.get("page") or 1))
        benchmark = dict(target.at)
        if target.quantity == "thermal_mass_gev":       # the benchmark is the stated thermal mass itself
            benchmark["dark matter mass (GeV)"] = target.value
        if target.quantity == "thermal_splitting":      # or the stated splitting of the coannihilating partner
            benchmark["relative mass splitting of the coannihilating partner, M_2/M_1 - 1"] = target.value
        if e.spec.get("dropped"):                       # the reference's own choices beyond the paper
            benchmark["left out by the reference"] = list(e.spec["dropped"])
        message = source_message(f"{ref.get('title', '')} — the model: {e.title}", lag["latex"],
                                 str(lag.get("equation", "")), text, benchmark)
        out.append((e, reference(e), message))
    return out


def run(dry: bool, budget: float, out: Path, only: list[str] | None, model: str) -> dict:
    from adroit.agents.canonical_intake import CanonicalIntake, PaperModel
    from adroit.agents.llm import BudgetedLLMClient, FakeLLMClient, LLMClient
    from adroit.model_building import spectrum
    found = cases(only)

    def builds(spec) -> str:
        try:
            spectrum.compute(spec)
            return ""
        except Exception as error:                     # noqa: BLE001 - recorded, not compared
            return str(error)
    if dry:
        llm = FakeLLMClient([PaperModel(spec=ref) for _, ref, _ in found if not builds(ref)])
    else:
        # 16,000 output tokens: a scalar sector's inversion takes a long reasoning (8,192 ran out, 2026-10-15)
        llm = BudgetedLLMClient(LLMClient(model=model, max_tokens=16_000, timeout_s=600), dollar_budget=budget)
    agent = CanonicalIntake(llm, model)
    results = []
    for e, reference, message in found:
        why = builds(reference)
        row = {"id": e.id, "reference_builds": not why}
        if why:                                         # nothing to compare with: the agent is not asked
            row["verdict"] = f"the reference does not build ({why})"
            results.append(row)
            print(f"{e.id}: {row['verdict']}", flush=True)
            continue
        try:
            got, refusals = agent.run(message, run_id=f"g10-{e.id}")
            row |= {"refusals": refusals, "conventions": got.conventions if got else [],
                    "assumptions": got.assumptions if got else []}
            if got is None:
                row["verdict"] = "no model"
            else:
                row |= judge(got.spec, e) | {"agent_spec": got.spec.model_dump(mode="json")}
                row["verdict"] = ("equal" if row["equal"] else "equal under D19" if row["equal_d19"] else "differs")
        except Exception as error:                     # noqa: BLE001 - a failure is a finding, the run goes on
            row["verdict"] = f"error: {type(error).__name__}: {error}"[:400]
        row["spent"] = getattr(llm, "spent", 0.0)
        results.append(row)
        print(f"{e.id}: {row['verdict']} (spent ${row['spent']:.3f})", flush=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"model": model, "dry_run": dry, "results": results}, indent=1))
    compared = [r for r in results if r.get("reference_builds") and "equal" in r]
    summary = {"entries": len(results), "compared": len(compared), "equal": sum(r["equal"] for r in compared),
               "equal_d19": sum(r["equal_d19"] for r in compared), "spent": getattr(llm, "spent", 0.0),
               "gate": len(compared) == len(results) and all(r["equal_d19"] for r in compared),
               "budget_stopped": any("BudgetExceeded" in str(r.get("verdict", "")) for r in results)}
    out.write_text(json.dumps({"model": model, "dry_run": dry, "summary": summary, "results": results}, indent=1))
    return summary


def rescore(path: Path) -> dict:
    """The stored agent models compared again ($0): with today's G1 and G2 and ``reference``. A difference that only
    the SM Higgs doublet makes (one writing declares it, the other not) is marked, not counted as equal."""
    from adroit.core.model_spec import ModelSpec
    from adroit.evaluation import zoo
    data = json.loads(path.read_text())
    by = {e.id: e for e in zoo.entries()}
    for row in data["results"]:
        if "agent_spec" not in row:
            continue
        out = judge(ModelSpec.model_validate(row["agent_spec"]), by[row["id"]])
        row["rescored"] = out
        print(f"{row['id']}: {'equal' if out['equal'] else 'equal under D19' if out['equal_d19'] else 'differs'}"
              f" (as run: {row['verdict']})", flush=True)
    rows = [r for r in data["results"] if "rescored" in r]
    data["rescored_summary"] = {"entries": len(data["results"]), "compared": len(rows),
                                "equal": sum(r["rescored"]["equal"] for r in rows),
                                "equal_d19": sum(r["rescored"]["equal_d19"] for r in rows),
                                "gate": len(rows) == len(data["results"]) and all(r["rescored"]["equal_d19"]
                                                                                  for r in rows)}
    path.write_text(json.dumps(data, indent=1))
    return data["rescored_summary"]


def main() -> int:
    """Run (or re-score) the gate; the exit code is 0 met, 1 not met, 3 stopped at the budget
    (``core.receipts``)."""
    from adroit.core.receipts import BUDGET_STOPPED, exit_code
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--budget", type=float, default=4.0)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--out", default="runs/g10/intake_dry.json")
    parser.add_argument("--rescore", action="store_true", help="compare the stored agent models in --out again ($0)")
    args = parser.parse_args()
    summary = rescore(Path(args.out)) if args.rescore else run(args.dry_run, args.budget, Path(args.out), args.only,
                                                                args.model)
    print(summary)
    return BUDGET_STOPPED if summary.get("budget_stopped") else exit_code(summary["gate"])


if __name__ == "__main__":
    sys.exit(main())

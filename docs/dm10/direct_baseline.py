"""The direct-prompting baseline of DM10 (paid: run live only with the owner's approval).

A language model is told each injection case's events and the candidate list,
and names its best candidate and plausible set (``adroit.evaluation.baselines``).

    uv run python docs/dm10/direct_baseline.py --dry-run
    uv run python docs/dm10/direct_baseline.py --live --budget 2 --model claude-opus-5-5

--dry-run calls no model: it measures the prompts and estimates the cost of a
live run on the development half. --live runs the development half with one
model, stops cleanly at the budget, and stores what it ran
(docs/dm10/results/direct_prompting_<model>.jsonl). The held-out half is the
owner's to run, for the gate: --held-out --reason "..." (entered in the ledger).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.agents.direct import DIRECT_SYSTEM, DirectAgent, DirectAnswer  # noqa: E402
from adroit.agents.llm import BudgetExceeded, FakeLLMClient  # noqa: E402
from adroit.core.pricing import CACHE_READ_PRICES, price_per_token  # noqa: E402
from adroit.evaluation import baselines, core, injection  # noqa: E402

OUTPUT_TOKENS = 400        # an answer of a best label, up to 30 plausible labels and a sentence
REASONING_FACTOR = 3.0     # allowance for a reasoning model's hidden output tokens


def development(half: core.Half = core.Half.development) -> list:
    """The baseline's cases in one half (the development half by default)."""
    return [c for c in baselines.cases() if c.half is half]


def dry_run(model: str) -> str:
    """Prompt sizes (about 4 characters a token) and the estimated cost on the development half."""
    cases = development()
    targets = {c.inputs["target"] for c in cases}
    stable = {t: len(DIRECT_SYSTEM + baselines.candidate_text(t)) / 4 for t in targets}
    variable = [len(baselines.case_text(c, injection.draw(c)[1])) / 4 for c in cases]
    price_in, price_out = price_per_token(model)
    cached = CACHE_READ_PRICES.get(model, price_in)
    # the first case of each target writes the cache; the rest read it
    cost = sum(stable[t] * price_in for t in targets) + sum(stable[c.inputs["target"]] * cached for c in cases)
    cost += sum(variable) * price_in + len(cases) * OUTPUT_TOKENS * REASONING_FACTOR * price_out
    # one offline call, to check the suite runs end to end
    fake = DirectAgent(FakeLLMClient([DirectAnswer(best="O1s@1", plausible=["O1s@1"])]), model="fake")
    result = baselines.suite(fake).run_case(next(c for c in cases if c.inputs["target"].startswith("CaWO4")))
    lines = [f"Direct prompting, development half: {len(cases)} cases, {model}.",
             *(f"- {t}: stable prompt about {stable[t]:,.0f} tokens" for t in sorted(targets)),
             f"- case text: {min(variable):.0f}-{max(variable):.0f} tokens",
             f"- estimated cost: ${cost:.2f} (output {OUTPUT_TOKENS} tokens × {REASONING_FACTOR:g} per case)",
             f"- offline check: {result.case_id} → {result.metrics}"]
    return "\n".join(lines)


def finished(model: str, half: core.Half = core.Half.development) -> dict[str, core.CaseResult]:
    """The cases of the model's latest stored run in ``half``, by id (for ``--resume``)."""
    path = core.RESULTS / f"direct_prompting_{model}.jsonl"
    if not path.exists():
        return {}
    runs = [core.SuiteRun.model_validate_json(line) for line in path.read_text().splitlines()]
    runs = [r for r in runs if r.half is half]
    return {r.case_id: r for r in runs[-1].results} if runs else {}


def live(budget: float, model: str, timeout_s: float, resume: bool,
         half: core.Half = core.Half.development, why: str = "") -> str:
    """Run the development half; whatever stops it (the budget, an error), the finished cases are saved.

    OpenAI models run in background mode (queued, then polled), so no connection
    is held open while the model reasons. With ``resume``, the cases of the latest
    stored run are kept and only the rest are asked.
    """
    from adroit.agents.llm import BudgetedLLMClient, LLMClient, OpenAIClient
    inner = (OpenAIClient(model=model, timeout_s=timeout_s, background=True) if model.startswith("gpt")
             else LLMClient(model=model, max_tokens=4096))
    llm = BudgetedLLMClient(inner, dollar_budget=budget)
    suite = baselines.suite(DirectAgent(llm, model=model))
    kept = finished(model, half) if resume else {}
    label = half.value.replace("_", "-") + " half" + (f" ({why})" if why else "")
    cases, reason = development(half), label + (f", resumed with {len(kept)} cases kept" if kept else "")
    results = [kept[c.id] for c in cases if c.id in kept]
    for case in [c for c in cases if c.id not in kept]:
        try:
            results.append(suite.run_case(case))
        except BudgetExceeded:
            reason = f"{label}, stopped at the budget after {len(results)} of {len(cases)} cases"
            break
        except Exception as error:  # noqa: BLE001 - any failure: keep what was finished
            reason = f"{label}, stopped by {type(error).__name__} after {len(results)} of {len(cases)} cases"
            print(f"stopped: {type(error).__name__}: {error}", flush=True)
            break
        print(f"{len(results)}/{len(cases)} ${llm.spent:.3f} {case.id}: {results[-1].metrics}", flush=True)
    done = {r.case_id for r in results}
    run_ = core.finish(suite, half, results, [c for c in cases if c.id in done], reason)
    core.save(run_)
    return core.report(run_) + f"\nSpent ${llm.spent:.2f} of ${budget:.2f} (completed requests only).\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--timeout", type=float, default=180.0,
                        help="seconds per HTTP request for OpenAI models")
    parser.add_argument("--resume", action="store_true",
                        help="keep the cases of the model's latest stored run and ask only the rest")
    parser.add_argument("--held-out", action="store_true", help="the held-out half (the gate; logged)")
    parser.add_argument("--reason", default="", help="why the held-out half is run (required with it)")
    args = parser.parse_args()
    if args.dry_run:
        print(dry_run(args.model))
        return
    if args.budget is None:
        raise SystemExit("--live needs --budget")
    if args.held_out and not args.reason.strip():
        raise SystemExit("--held-out needs --reason")
    half = core.Half.held_out if args.held_out else core.Half.development
    text = live(args.budget, args.model, args.timeout, args.resume, half, args.reason)
    suffix = "_held_out" if args.held_out else ""
    (ROOT / "docs" / "dm10" / f"direct_baseline_{args.model}{suffix}.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()

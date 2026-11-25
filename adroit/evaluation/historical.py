"""Historical excesses (DM10): Path 2 on searches whose verdict the literature has reached.

Each case is one historical search (``experiments.historical``) with the
literature's verdict on it (``data/historical_verdicts.yaml``, each with its
source). Path 2 runs as on any search with events: the library's own model
space, the global significance by background-only toys, the leading classes
combined with the null searches. The system's verdict is then set beside the
literature's, item by item:
- **significance** ("below evidence"): the system agrees if its global
  significance is below 3σ;
- **the standard reading** ("excluded"): the reading the literature tested
  (e.g. spin-independent, isospin-conserving at the paper's best-fit mass) is
  combined with the null searches; the system agrees if the joint test
  rejects it, p_PG < 0.01.
A case passes when every item agrees. Reported beside the verdicts: which
leaders survive the null searches (p_PG ≥ 0.01). A survivor is a finding to
examine, not a failure: the literature's verdict covers the readings it tested.

The null searches are today's (``NULLS``), not those of the time: the verdict
is the system's on the evidence it holds.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml

from adroit.evaluation.core import Case, CaseResult, Suite
from adroit.experiments import historical
from adroit.orchestrator import signal

NULLS = ["CRESST-III 2019", "CDMSlite Run 2", "PICO-60 C3F8 (2019)", "DEAP-3600 (2019)", "LZ WS2022+WS2024"]
EVIDENCE_Z = 3.0
EXCLUDED_P = 0.01
LEADERS = 4
TOYS = 200_000


@lru_cache(maxsize=1)
def verdicts() -> dict:
    """The literature's verdict on each historical search (``data/historical_verdicts.yaml``)."""
    text = resources.files("adroit.evaluation").joinpath("data/historical_verdicts.yaml").read_text()
    return yaml.safe_load(text)


def cases() -> list[Case]:
    """One case per historical search that has a verdict in the literature."""
    return [Case(suite="historical", id=key, inputs={"search": historical.record(key)["name"], **verdicts()[key]})
            for key in historical.records() if key in verdicts()]


def request(case: Case, nulls: list[str] | None = None) -> signal.SignalRequest:
    """Path 2's request for the case: the library's space, the null searches, no complementary records."""
    return signal.SignalRequest(experiment=case.inputs["search"], null_modules=NULLS if nulls is None else nulls,
                                leaders=LEADERS, toys=TOYS, complementary=False)


def judge(case: Case, result: signal.SignalResult, standard_p: float | None) -> dict[str, bool]:
    """Whether the system agrees with each item of the literature's verdict."""
    out = {}
    if case.inputs["significance"]["verdict"] == "below_evidence":
        out["significance"] = result.global_z < EVIDENCE_Z
    if "standard" in case.inputs and case.inputs["standard"]["verdict"] == "excluded":
        out["standard"] = standard_p is not None and standard_p < EXCLUDED_P
    return out


def run_case(case: Case) -> CaseResult:
    """Path 2 on the case's search, and the standard reading combined with the null searches; the case passes when
    every item of the verdict agrees."""
    req = request(case)
    result = signal.run(req)
    standard = case.inputs.get("standard")
    combo = signal.combine(req, signal.Candidate(**standard["candidate"])) if standard else None
    agreed = judge(case, result, combo.p_pg if combo else None)
    survivors = [c.label for c in result.combinations if c.p_pg >= EXCLUDED_P]
    metrics: dict[str, float | str | bool] = {
        "global_z": round(result.global_z, 3), "max_local_z": round(result.max_local_z, 3),
        "leader": result.tournament.signal_fit_leader, "background_rank": result.tournament.null_rank,
        "leaders_surviving_nulls": ", ".join(survivors) or "none", **{f"agrees: {k}": v for k, v in agreed.items()}}
    if combo:
        strongest = min(combo.null_limits, key=combo.null_limits.get) if combo.null_limits else "none"
        metrics |= {"standard_p_pg": float(f"{combo.p_pg:.3g}"), "standard_mu_hat": float(f"{combo.mu_hat_signal:.3g}"),
                    "standard_strongest_null": strongest}
    note = "; ".join(f"{k}: {'agrees' if v else 'DISAGREES'}" for k, v in agreed.items())
    return CaseResult(case_id=case.id, passed=all(agreed.values()), metrics=metrics, note=note)


def summarise(results: list[CaseResult], cases_: list[Case]) -> dict[str, float | str]:
    """Each case's agreement, item by item, and how many cases agree with the literature."""
    out: dict[str, float | str] = {r.case_id: r.note for r in results}
    out["cases agreeing with the literature"] = f"{sum(bool(r.passed) for r in results)}/{len(results)}"
    return out


SUITE = Suite(name="historical", description="Path 2 on historical excesses, against the literature's verdict",
              cases=cases, run_case=run_case, summarise=summarise)

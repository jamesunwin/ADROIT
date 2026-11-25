"""The DM8 gate: ten models with known answers, three of them not in the library.

Each model's description (docs/dm8/gate_models.yaml) goes through Path 1 for a
bespoke model with the language models on: intake → checks → derivation →
dimension check → a second derivation by the other model → DirectDM → the
library. A model is matched correctly when all four hold (declared in
docs/dm8_lagrangians.md, section 9, before the paid run):

(a) the intake's model passes the deterministic checks;
(b) the run completes: no stop for a person;
(c) the derivation's nucleon-level interaction agrees with the reference's
    within 1%, up to one overall sign, at the stated values and at two random
    parameter points;
(d) the library's verdict is the expected one: one of the expected cards
    "same" or "close", or, for a model not in the library, no card "same" or
    "close".

Run from the repository root:

    uv run python docs/dm8/gate.py --dry-run
        $0. The reference answers stand in for the agents, plus three wrong
        "agents" as controls. Writes gate_dry_run.txt.

    uv run python docs/dm8/gate.py --live --budget 12
        Paid; only with the owner's approval. Needs both models' prices in
        core/pricing.py and both API keys. Writes gate_live.json and
        gate_live.md.

    uv run python docs/dm8/gate.py --live --budget 6 --no-checker
        The first half (2026-10-01, no OpenAI key yet): the deriver only, no
        second derivation, so (b) is only "the run completes". Writes
        gate_live_deriver.json and .md; the checker's half is a final check of
        DM8.

    uv run python docs/dm8/gate.py --checker-half --budget 6
        The second half: the checker derives each model from the intake's model
        of the deriver's half; (b) is the two derivations' agreement at the
        nucleon level. Reads gate_live_deriver.json from --out when it is
        there, else the tracked docs/dm8 receipt. Writes
        gate_live_checker.json and .md.

Every mode writes to a new runs/gates/dm8/<UTC> folder unless --out names one;
name docs/dm8 only to re-record the tracked receipts. The exit code is 0 when
the gate passes, 1 when it does not, and 3 when a paid run stopped at its budget.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.agents.llm import FakeLLMClient  # noqa: E402
from adroit.core.dm_state import DarkMatterParticle  # noqa: E402
from adroit.core.model_spec import ModelSpec  # noqa: E402
from adroit.core.receipts import BUDGET_STOPPED, add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.core.state import StrictModel  # noqa: E402
from adroit.library.interactions import derivation as dv  # noqa: E402
from adroit.library.interactions import matching, quark_level, registry  # noqa: E402
from adroit.orchestrator import lagrangian  # noqa: E402

HERE = Path(__file__).parent
MODELS = HERE / "gate_models.yaml"
SEED = 20261002
TOLERANCE = dv.AGREEMENT


class Reference(StrictModel):
    """The known answer."""

    spec: ModelSpec
    derivation: dv.Derivation


class GateModel(StrictModel):
    """One model of the gate."""

    id: str
    name: str
    in_library: bool
    expected: dict[str, list[str]]
    description: str
    reference: Reference


class Verdict(StrictModel):
    """The four criteria for one model, and what was seen."""

    id: str
    checks: bool = False
    complete: bool = False
    nucleon_difference: float | None = None
    library: bool = False
    best_cards: list[str] = []
    status: str = ""
    error: str = ""

    @property
    def passed(self) -> bool:
        """(a)–(d) all hold."""
        return (self.checks and self.complete and self.library and self.nucleon_difference is not None
                and self.nucleon_difference <= TOLERANCE)


def load() -> list[GateModel]:
    """The ten models."""
    return [GateModel.model_validate(m) for m in yaml.safe_load(MODELS.read_text())["models"]]


def points(model: GateModel) -> list[dict[str, float]]:
    """The stated values (no overrides) and two random points of the reference."""
    return [{}, *dv.random_points(model.reference.spec, 2, SEED)]


def nucleon_agreement(model: GateModel, spec: ModelSpec, derivation: dv.Derivation) -> float:
    """(c): the largest difference from the reference after DirectDM, at the better overall sign."""
    ref = model.reference
    dm = ref.spec.dark_matter
    grid = points(model)
    masses = [p.get(f"m_{dm.name}", dm.mass_gev) for p in grid]
    mine = [dv.evaluate(derivation, spec, p) for p in grid]
    theirs = [dv.evaluate(ref.derivation, ref.spec, p) for p in grid]
    return dv.nucleon_difference(mine, theirs, masses)


def library_verdict(model: GateModel, particle: DarkMatterParticle, interaction) -> tuple[bool, list[str]]:
    """(d), and the cards that are "same" or "close"."""
    good = [f.card_id for f in matching.match(particle, interaction) if f.verdict in ("same", "close")]
    expected = model.expected.get("cards", [])
    return (any(c in good for c in expected) if model.in_library else not good), good


def judge(model: GateModel, result: lagrangian.LagrangianResult) -> Verdict:
    """The four criteria for one pipeline result."""
    verdict = Verdict(id=model.id, status=result.status,
                      checks=bool(result.checks and result.checks.passed),
                      complete=result.status == "complete")
    if result.spec is None or result.derivation is None:
        return verdict
    try:
        verdict.nucleon_difference = nucleon_agreement(model, result.spec, result.derivation)
    except ValueError as exc:
        verdict.error = f"(c) does not evaluate: {exc}"
    if result.interactions:
        mass = result.spec.dark_matter.mass_gev
        particle, interaction = quark_level.to_interaction(
            dv.evaluate(result.derivation, result.spec), mass)
        verdict.library, verdict.best_cards = library_verdict(model, particle, interaction)
    return verdict


def run_one(model: GateModel, primary, checker) -> tuple[lagrangian.LagrangianResult | None, Verdict]:
    """One model through the pipeline; an exception is a failure, recorded. ``checker`` None: no
    second derivation."""
    dm_mass = model.reference.spec.dark_matter.mass_gev
    request = lagrangian.LagrangianRequest(description=model.description, use_language_models=True,
                                           run_exclusion=False, masses_gev=[dm_mass],
                                           second_derivation=checker is not None)
    try:
        result = lagrangian.run(request, primary=primary, checker=checker)
    except Exception as exc:  # noqa: BLE001 - every failure is the gate's to record
        return None, Verdict(id=model.id, error=f"{type(exc).__name__}: {exc}")
    return result, judge(model, result)


def line(v: Verdict) -> str:
    """One model's verdict in a line."""
    diff = "—" if v.nucleon_difference is None else f"{v.nucleon_difference:.1e}"
    cards = ", ".join(v.best_cards[:4]) or "none"
    return (f"{v.id:4s} {'PASS' if v.passed else 'FAIL'}  (a) {'y' if v.checks else 'n'}  "
            f"(b) {'y' if v.complete else 'n'}  (c) {diff:>8s}  (d) {'y' if v.library else 'n'}  "
            f"same/close: {cards}{'  ' + v.error if v.error else ''}"
            f"{'  [' + v.status + ']' if not v.complete and v.status else ''}")


def _scaled(derivation: dv.Derivation, factor: str) -> dv.Derivation:
    terms = [t.model_copy(update={"expression": f"{factor}*({t.expression})"}) for t in derivation.terms]
    return derivation.model_copy(update={"terms": terms})


def _reduced(model: GateModel, rge: bool = True):
    ref = model.reference
    quark = dv.evaluate(ref.derivation, ref.spec).model_copy(update={"rge": rge})
    return quark_level.to_interaction(quark, ref.spec.dark_matter.mass_gev)


def _c(interaction, operator: int, q: float = 1e-4) -> float:
    return sum(c.proton * float(c.q_factor(np.array([q]))[0]) for c in interaction.coefficients
               if c.operator == operator)


def normalisations(models: list[GateModel]) -> list[str]:
    """The references against closed-form answers (proton, q → 0); 1 means agreement."""
    by_id = {m.id: m for m in models}
    f_n = registry.card("M_higgs_portal").parameter("fN_p").default    # DirectDM's σ-terms (DM4)
    m_n = 0.938918747
    out = ["Normalisations of the references (proton, q → 0; ±1 is agreement, the sign being free):"]
    for mid in ("G1", "G7"):
        _, i = _reduced(by_id[mid])
        out.append(f"  {mid}: c1 / (3 g_χ g_q/M²) = {_c(i, 1) / (3 * 0.25 / 2000 ** 2):.4f}")
    _, i = _reduced(by_id["G3"])
    out.append(f"  G3: c1 / (g_χ g_q m_N f_N/(v M²)) = {_c(i, 1) * 246.22 * 500 ** 2 / (m_n * f_n):.4f}")
    _, i = _reduced(by_id["G4"])
    out.append(f"  G4: c1 / (λ f_N m_N/(2 m_h² m_S)) = {_c(i, 1) / (0.1 * f_n * m_n / (2 * 125.25 ** 2 * 100)):.4f}"
               "  (σ = μ² c1²/π = λ² f_N² μ² m_N²/(4π m_h⁴ m_S²))")
    for mid, card, name, rge in (("G5", "M_magnetic_dipole", "mu_chi", True), ("G6", "M_anapole", "anapole", True),
                                 ("G6", "M_anapole", "anapole", False)):
        particle, i = _reduced(by_id[mid], rge)
        fitted = matching.fit_card(card, particle, i).values[name] / 1e-5
        out.append(f"  {mid}: {card}'s fitted {name} / the Lagrangian's = {fitted:.4f}"
                   f"{'' if rge else ' (without the running from m_Z)'}")
    out.append("  (G6 is Majorana: its Lagrangian coupling is half the card's, which is a Feynman-rule coupling.)")
    for mid in ("G8", "G10"):
        _, i = _reduced(by_id[mid])
        terms = sorted({(c.operator, c.q_power, round(c.mediator_mass_gev, 3) if c.mediator_mass_gev else None)
                        for c in i.coefficients})
        out.append(f"  {mid}: (operator, power of q, pole mass) = {terms}")
    return out


CONTROLS_PASS = (False, False, False, True)     # what each control must do, as its label states


def dry_run() -> tuple[str, bool]:
    """The references as the agents, then three controls that must fail or pass as stated; the text and
    whether every model passed and every control behaved as declared."""
    models = load()
    out = ["DM8 gate, dry run: the reference answers stand in for both language models ($0)", ""]
    verdicts = []
    for m in models:
        ref = m.reference
        _, v = run_one(m, FakeLLMClient([ref.spec, ref.derivation]), FakeLLMClient([ref.derivation]))
        verdicts.append(v)
        out.append(line(v))
    out += ["", f"{sum(v.passed for v in verdicts)}/{len(verdicts)} pass", "", "Controls:"]
    g1, g6 = models[0], models[5]
    controls = [
        ("G1, both agents off by a factor 2 (must fail (c))", g1, _scaled(g1.reference.derivation, "2"),
         _scaled(g1.reference.derivation, "2")),
        ("G1, the checker off by a factor 2 (must stop: fail (b))", g1, g1.reference.derivation,
         _scaled(g1.reference.derivation, "2")),
        ("G6, every sign reversed and the leptons left out by both (must fail (c): 2%)", g6,
         _scaled(g6.reference.derivation.model_copy(update={"terms": g6.reference.derivation.terms[:5]}), "-1"),
         _scaled(g6.reference.derivation.model_copy(update={"terms": g6.reference.derivation.terms[:5]}), "-1")),
        ("G6, every sign reversed (must pass)", g6, _scaled(g6.reference.derivation, "-1"),
         _scaled(g6.reference.derivation, "-1")),
    ]
    seen = []
    for label, m, first, second in controls:
        _, v = run_one(m, FakeLLMClient([m.reference.spec, first]), FakeLLMClient([second]))
        seen.append(v.passed)
        out += [f"  {label}", "  " + line(v)]
    passed = all(v.passed for v in verdicts) and tuple(seen) == CONTROLS_PASS
    out += ["", *normalisations(models), "", f"Gate: {'PASSED' if passed else 'NOT PASSED'}"]
    return "\n".join(out) + "\n", passed


def _spend(client, model: str) -> dict:
    return {"model": model, "spent": client.spent, "input_tokens": client.input_tokens,
            "output_tokens": client.output_tokens} if client else {"model": "deferred", "spent": 0.0}


def live(budget: float, deriver: str, checker_model: str | None, folder: Path) -> tuple[str, int]:
    """The paid run. Refuses to start without the prices and an explicit budget. ``checker_model`` None:
    the deriver alone, with the whole budget. Returns the text and the exit code."""
    from adroit.agents.llm import BudgetedLLMClient, LLMClient, OpenAIClient
    from adroit.core.pricing import TOKEN_PRICES
    missing = [m for m in (deriver, checker_model) if m and m not in TOKEN_PRICES]
    if missing:
        raise SystemExit(f"no price in core/pricing.py for {missing}: add the owner's figures first")
    from adroit.agents.budget import BudgetAccount
    account = BudgetAccount(budget)
    primary = BudgetedLLMClient(LLMClient(model=deriver, max_tokens=8192), account=account)
    checker = BudgetedLLMClient(OpenAIClient(model=checker_model), account=account) if checker_model else None
    records, verdicts, stopped = [], [], False
    for m in load():
        result, v = run_one(m, primary, checker)
        verdicts.append(v)
        records.append({"id": m.id, "verdict": v.model_dump(), "passed": v.passed,
                        "result": json.loads(result.model_dump_json()) if result else None})
        print(line(v), flush=True)
        if v.error.startswith("BudgetExceeded:"):
            stopped = True
            break
    spend = {"deriver": _spend(primary, deriver), "checker": _spend(checker, checker_model or "")}
    stem = "gate_live" if checker_model else "gate_live_deriver"
    (folder / f"{stem}.json").write_text(json.dumps({"models": records, "spend": spend, "paid_response_ledgers": [str(c.ledger_path) for c in (primary, checker) if c]}, indent=1))
    passed = sum(v.passed for v in verdicts)
    total = primary.spent + (checker.spent if checker else 0.0)
    title = "# DM8 gate, live run" + ("" if checker_model else ": the deriver alone (the checker deferred)")
    text = "\n".join([title, "", *map(line, verdicts), "",
                      f"{passed}/{len(verdicts)} pass; spent ${total:.2f} ({deriver} ${primary.spent:.2f}"
                      + (f", {checker_model} ${checker.spent:.2f})" if checker else "; no checker)")]) + "\n"
    (folder / f"{stem}.md").write_text(text)
    return text, BUDGET_STOPPED if stopped else exit_code(passed == len(verdicts) == len(load()))


def _check_one(model: GateModel, record: dict, checker, checker_model: str) -> dict:
    """The checker's derivation of one model, against the deriver's and against the known answer."""
    from adroit.agents.lagrangian import DerivationAgent
    first = lagrangian.LagrangianResult.model_validate(record["result"])
    try:
        second = DerivationAgent(checker, checker_model).run(first.spec)
        comparison = dv.compare(first.derivation, second, first.spec, nucleon=True)
        own = nucleon_agreement(model, first.spec, second)
    except Exception as exc:  # noqa: BLE001 - recorded, and an API failure is rerun
        return {"id": model.id, "agree": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"id": model.id, "agree": comparison.agree, "deriver_passed": record["passed"],
            "passed": comparison.agree and record["passed"], "nucleon_difference": comparison.nucleon_difference,
            "coefficient_difference": comparison.max_relative_difference, "sign": comparison.sign,
            "only_in_deriver": comparison.only_in_first, "only_in_checker": comparison.only_in_second,
            "checker_vs_reference": own, "second": json.loads(second.model_dump_json()), "error": ""}


def _checker_line(row: dict) -> str:
    if row["error"]:
        return f"{row['id']:4s} ERROR {row['error']}"
    extra = "".join(f"; only in the {w}: {', '.join(n)}" for w, n in
                    (("deriver", row["only_in_deriver"]), ("checker", row["only_in_checker"])) if n)
    return (f"{row['id']:4s} {'PASS' if row['passed'] else 'FAIL'}  (b) {'agree' if row['agree'] else 'DISAGREE'}: "
            f"nucleon level {row['nucleon_difference']:.1e}, coefficients {row['coefficient_difference']:.1e}"
            f"{' (sign reversed)' if row['sign'] < 0 else ''}{extra}; checker vs known answer "
            f"{row['checker_vs_reference']:.1e}")


def checker_half(budget: float, checker_model: str, folder: Path) -> tuple[str, int]:
    """The second half of the gate, on the intake models and derivations of the first; the text and the
    exit code."""
    from adroit.agents.llm import BudgetedLLMClient, OpenAIClient
    from adroit.core.pricing import TOKEN_PRICES
    if checker_model not in TOKEN_PRICES:
        raise SystemExit(f"no price in core/pricing.py for {checker_model}")
    first_half = folder / "gate_live_deriver.json"
    first = json.loads((first_half if first_half.exists() else HERE / "gate_live_deriver.json").read_text())
    checker = BudgetedLLMClient(OpenAIClient(model=checker_model), dollar_budget=budget)
    by_id = {m.id: m for m in load()}
    rows, stopped = [], False
    for record in first["models"]:
        rows.append(_check_one(by_id[record["id"]], record, checker, checker_model))
        print(_checker_line(rows[-1]), flush=True)
        if rows[-1].get("error", "").startswith("BudgetExceeded:"):
            stopped = True
            break
    spend = _spend(checker, checker_model)
    (folder / "gate_live_checker.json").write_text(json.dumps({"models": rows, "spend": spend, "paid_response_ledger": str(checker.ledger_path)}, indent=1))
    passed = sum(r.get("passed", False) for r in rows)
    text = "\n".join(["# DM8 gate, the checker's half", "", *map(_checker_line, rows), "",
                      f"{passed}/{len(rows)} matched correctly with both halves; {checker_model} spent "
                      f"${checker.spent:.2f}"]) + "\n"
    (folder / "gate_live_checker.md").write_text(text)
    return text, BUDGET_STOPPED if stopped else exit_code(passed == len(rows) == len(first["models"]))


def main() -> int:
    """--dry-run ($0) or --live (paid, with the owner's approval); returns the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--checker-half", action="store_true")
    parser.add_argument("--budget", type=float, default=None, help="dollars; required with --live")
    parser.add_argument("--deriver", default=lagrangian.DEFAULT_DERIVER)
    parser.add_argument("--checker", default=lagrangian.DEFAULT_CHECKER)
    parser.add_argument("--no-checker", action="store_true", help="the deriver alone, no second derivation")
    add_out_argument(parser, "dm8")
    args = parser.parse_args()
    if not args.dry_run and args.budget is None:
        raise SystemExit(f"{'--checker-half' if args.checker_half else '--live'} needs --budget (dollars)")
    folder = gate_output("dm8", args.out)
    if args.dry_run:
        text, passed = dry_run()
        (folder / "gate_dry_run.txt").write_text(text)
        code = exit_code(passed)
    elif args.checker_half:
        text, code = checker_half(args.budget, args.checker, folder)
    else:
        text, code = live(args.budget, args.deriver, None if args.no_checker else args.checker, folder)
    print(text)
    print(f"written to {folder}")
    return code


if __name__ == "__main__":
    sys.exit(main())

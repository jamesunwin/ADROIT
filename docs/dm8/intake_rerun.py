"""DM8: the intake rerun with the corrected prompt (a term's coupling is its full coefficient).

The owner approved the rerun on 2026-10-01 (record, section 15, where the rule
was declared before this ran). claude-opus-5-5 turns each of the ten gate
descriptions into a ModelSpec again. A model passes when:

(a) every term's coupling evaluates (``model_checks.coefficient_flags`` is empty);
(b) every term of the reference model has a term in the intake's model with the
    same fields whose coefficient has the same magnitude, at the reference's
    values (the sign is a convention: the SM writes −(m_q/v) h q̄q);
(c) where the UFO writer covers the model, MadDM's quark-level coefficients
    from ADROIT's UFO file *of the intake's model* agree with the gate's
    derivation within 1% (``maddm.check``).

Run from the repository root:

    uv run python docs/dm8/intake_rerun.py --live --budget 1     # paid; approved
    uv run python docs/dm8/intake_rerun.py --dry-run             # $0: the reference models stand in

Writes docs/dm8/intake_rerun.json and .txt.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.agents.lagrangian import IntakeAgent  # noqa: E402
from adroit.agents.llm import FakeLLMClient  # noqa: E402
from adroit.constraints import maddm  # noqa: E402
from adroit.core.model_spec import ModelSpec  # noqa: E402
from adroit.library.interactions import derivation as dv  # noqa: E402
from adroit.library.interactions import model_checks  # noqa: E402

HERE = Path(__file__).parent
REFERENCE = {m["id"]: m for m in yaml.safe_load((HERE / "gate_models.yaml").read_text())["models"]}
GATE = {r["id"]: r for r in json.loads((HERE / "gate_live_deriver.json").read_text())["models"]}


def _coefficient(spec: ModelSpec, text: str, values: dict[str, float], fields: set[str]) -> float:
    """A term's coefficient; m_q is the term's own quark's mass (1 for a group such as q)."""
    own = next((dv.STANDARD_MODEL[f"m_{f}"][0] for f in fields if f"m_{f}" in dv.STANDARD_MODEL and len(f) == 1), 1.0)
    table = {**dv.symbol_table(spec, values), "m_q": (own, 1), "m_f": (own, 1), "m_l": (own, 1)}
    return dv.evaluate_expression(text, table)


def matching_terms(intake: ModelSpec, reference: ModelSpec) -> list[str]:
    """(b): problems with the intake's terms against the reference's, at the reference's values."""
    values = {c.name: c.value for c in reference.couplings if c.value is not None}
    problems = []
    for ref in reference.terms:
        fields = Counter(o.field for o in ref.fields)
        mine = [t for t in intake.terms if Counter(o.field for o in t.fields) == fields]
        if not mine:
            problems.append(f"no term with the fields {sorted(fields.elements())}")
            continue
        try:
            want = abs(_coefficient(reference, ref.coupling, values, set(fields)))
            got = abs(_coefficient(intake, mine[0].coupling, values, set(fields)))
        except ValueError as exc:
            problems.append(f"{mine[0].coupling!r}: {exc}")
            continue
        if abs(got - want) > 1e-6 * max(want, 1e-300):
            problems.append(f"{mine[0].coupling!r} is {got:.4g} where the reference's {ref.coupling!r} is {want:.4g}")
    return problems


def judge(gid: str, intake: ModelSpec, numerical: bool) -> dict:
    """(a), (b) and (c) for one model."""
    reference = ModelSpec.model_validate(REFERENCE[gid]["reference"]["spec"])
    flags = model_checks.coefficient_flags(intake)
    terms = matching_terms(intake, reference)
    row = {"id": gid, "coefficients": flags, "terms": terms, "maddm": "not run"}
    if numerical:
        try:
            found = maddm.coefficients(intake, maddm.workdir(f"intake_{gid}"))
            c = maddm.check(intake, dv.Derivation.model_validate(GATE[gid]["result"]["derivation"]), found)
            row["maddm"] = (f"{c.max_relative_difference:.1e}" if c.covered else f"not covered: {c.reason}")
            row["maddm_agree"] = c.agree
        except ValueError as exc:
            row["maddm"] = f"not covered: not written as UFO ({exc})"
        except RuntimeError as exc:
            row["maddm"] = f"MadDM failed: {str(exc).splitlines()[0]}"
            row["maddm_agree"] = False
    row["passed"] = not flags and not terms and row.get("maddm_agree", True)
    return row


def line(row: dict) -> str:
    """One model's verdict in a line."""
    problems = "; ".join(row["coefficients"] + row["terms"]) or "terms as the reference"
    return f"{row['id']:4s} {'PASS' if row['passed'] else 'FAIL'}  {problems}  | MadDM: {row['maddm']}"


def main() -> None:
    """--dry-run ($0) or --live (paid; approved by the owner)."""
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--no-maddm", action="store_true")
    parser.add_argument("--only", default="", help="models, comma-separated (a targeted check)")
    args = parser.parse_args()
    if args.live:
        from adroit.agents.llm import BudgetedLLMClient, LLMClient
        if args.budget is None:
            raise SystemExit("--live needs --budget")
        client = BudgetedLLMClient(LLMClient(model="claude-opus-5-5", max_tokens=8192), dollar_budget=args.budget)
    rows, specs = [], {}
    chosen = [g for g in args.only.split(",") if g] or list(REFERENCE)
    for gid, model in ((g, REFERENCE[g]) for g in chosen):
        if args.dry_run:
            client = FakeLLMClient([ModelSpec.model_validate(model["reference"]["spec"])])
        try:
            spec = IntakeAgent(client, "claude-opus-5-5").run(model["description"])
        except Exception as exc:  # noqa: BLE001 - an API failure is recorded, and rerun
            rows.append({"id": gid, "passed": False, "coefficients": [f"{type(exc).__name__}: {exc}"], "terms": [],
                         "maddm": "not run"})
            if type(exc).__name__ == "BudgetExceeded":
                break
            continue
        specs[gid] = json.loads(spec.model_dump_json())
        stem = ("intake_rerun" if args.live else "intake_rerun_dry") + (f"_{'_'.join(chosen)}" if args.only else "")
        (HERE / f"{stem}.json").write_text(json.dumps({"rows": rows, "specs": specs}, indent=1))   # as it goes
        rows.append(judge(gid, spec, numerical=not args.no_maddm and maddm.available()))
        print(line(rows[-1]), flush=True)
    spend = client.spent if args.live else 0.0
    stem = ("intake_rerun" if args.live else "intake_rerun_dry") + (f"_{'_'.join(chosen)}" if args.only else "")
    (HERE / f"{stem}.json").write_text(json.dumps({"rows": rows, "specs": specs, "spent": spend}, indent=1))
    text = "\n".join(map(line, rows)) + f"\n\n{sum(r['passed'] for r in rows)}/{len(rows)} pass; spent ${spend:.2f}\n"
    (HERE / f"{stem}.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()

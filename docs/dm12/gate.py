"""DM12's gate: the model front end against textbook models, seeded errors, omissions and free text.

    uv run python docs/dm12/gate.py --dry-run          # parts A–C, and D with a scripted model ($0)
    uv run python docs/dm12/gate.py --live --budget 1  # part D with claude-opus-5-5 (paid)

Declared in docs/dm12_front_end.md (section 6) before the first run:
- A. Nine textbook field contents give exactly their textbook operator inventories.
- B. Twelve seeded errors are each caught by the right check; DM8's ten gate models and seven generated
  models raise no validity problem.
- C. Four deliberate omissions are each found.
- D. Six ideas in words: every proposal is built into a valid model or dropped with a stated reason, and
  in at least five of six the textbook field content is among the proposals.

Both write to a new runs/gates/dm12/<UTC> folder unless --out names one (docs/dm12 only to re-record
the tracked receipts). Exit code: 0 passed, 1 not passed, 3 stopped at the budget.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from adroit.core.model_spec import Charges, FieldRole, ModelField, ModelSpec  # noqa: E402
from adroit.core.receipts import BUDGET_STOPPED, add_out_argument, exit_code, gate_output  # noqa: E402
from adroit.model_building.audit import audit  # noqa: E402
from adroit.model_building.content import STANDARD_MODEL, content, new_fields  # noqa: E402
from adroit.model_building.lagrangian import general_lagrangian  # noqa: E402
from adroit.model_building.spec import general_spec  # noqa: E402

HERE = Path(__file__).parent


def f(name: str, spin: float, role: FieldRole = FieldRole.dark_matter, **kw) -> ModelField:
    return ModelField(name=name, role=role, spin=spin, charges=Charges(**kw.pop("charges", {})), **kw)


def m(*fields: ModelField, name: str = "m") -> ModelSpec:
    return ModelSpec(name=name, phase="unbroken", fields=list(fields))


def inventory(ops) -> set[tuple]:
    return {(o.structure, tuple(sorted(o.blocks)), o.count) for o in ops}


CHI_D = f("chi", 0.5, dark_parity=-1, charges={"extra": {"D": 1.0}})
ZP = f("Zp", 1, role=FieldRole.mediator, self_conjugate=True)
TEXTBOOK = {
    "Standard Model (Yukawas and potential)": (None, {
        ("mass", ("H", "H*"), 1), ("potential", ("H", "H", "H*", "H*"), 1), ("yukawa", ("H", "Q", "uR^c"), 9),
        ("yukawa", ("H*", "Q", "dR^c"), 9), ("yukawa", ("H*", "L", "eR^c"), 9)}),
    "real singlet scalar, Z2-odd": (m(f("S", 0, self_conjugate=True, dark_parity=-1)), {
        ("mass", ("S", "S"), 1), ("potential", ("H", "H*", "S", "S"), 1), ("potential", ("S", "S", "S", "S"), 1)}),
    "inert doublet": (m(f("Phi", 0, charges={"su2": 2, "hypercharge": 0.5}, dark_parity=-1)), {
        ("mass", ("Phi", "Phi*"), 1), ("potential", ("H", "H", "Phi*", "Phi*"), 1),
        ("potential", ("H", "H*", "Phi", "Phi*"), 2), ("potential", ("Phi", "Phi", "Phi*", "Phi*"), 1)}),
    "Majorana singlet, Z2-odd": (m(f("chi", 0.5, self_conjugate=True, dark_parity=-1)), {("mass", ("chi", "chi"), 1)}),
    "fermion quintuplet (minimal dark matter)": (m(f("X", 0.5, self_conjugate=True, charges={"su2": 5})),
                                                 {("mass", ("X", "X"), 1)}),
    "fermion triplet, no Z2 (type-III seesaw)": (m(f("Sigma", 0.5, self_conjugate=True, charges={"su2": 3})), {
        ("mass", ("Sigma", "Sigma"), 1), ("yukawa", ("H", "L", "Sigma"), 3)}),
    "scalar triplet Y = 1 (type II), with a Majorana dark matter": (
        m(f("chi", 0.5, self_conjugate=True, dark_parity=-1), f("Delta", 0, role=FieldRole.other,
                                                                charges={"su2": 3, "hypercharge": 1.0})), {
            ("mass", ("chi", "chi"), 1), ("mass", ("Delta", "Delta*"), 1), ("potential", ("Delta*", "H", "H"), 1),
            ("potential", ("Delta", "Delta*", "H", "H*"), 2), ("potential", ("Delta", "Delta", "Delta*", "Delta*"), 2),
            ("yukawa", ("Delta", "L", "L"), 6)}),
    "dark photon gauging the dark matter's U(1)": (
        m(f("chi", 0.5, dark_parity=-1, charges={"extra": {"Ap": 1.0}}), f("Ap", 1, role=FieldRole.mediator,
                                                                          self_conjugate=True)), {
            ("mass", ("chi", "chi^c"), 1), ("kinetic_mixing", ("Ap", "B"), 1), ("mass", ("Ap", "Ap"), 1)}),
    "massive Z′ and a Dirac fermion with dark number": (m(CHI_D, ZP), {
        ("mass", ("chi", "chi^c"), 1), ("kinetic_mixing", ("B", "Zp"), 1), ("mass", ("Zp", "Zp"), 1),
        ("vector_current", ("Q", "Q*", "Zp"), 9), ("vector_current", ("Zp", "uR^c", "uR^c*"), 9),
        ("vector_current", ("Zp", "dR^c", "dR^c*"), 9), ("vector_current", ("L", "L*", "Zp"), 9),
        ("vector_current", ("Zp", "eR^c", "eR^c*"), 9), ("vector_current", ("Zp", "chi", "chi*"), 1),
        ("vector_current", ("Zp", "chi^c", "chi^c*"), 1), ("scalar_current", ("H", "H*", "Zp"), 1),
        ("vector_scalar", ("H", "H*", "Zp", "Zp"), 1)}),
}


def part_a() -> list[dict]:
    rows = []
    for name, (spec, expected) in TEXTBOOK.items():
        ops = (general_lagrangian(list(STANDARD_MODEL), include_standard_model=True) if spec is None
               else general_lagrangian(content(spec)))
        found = inventory(ops)
        rows.append({"case": name, "pass": found == expected, "extra": sorted(map(str, found - expected)),
                     "absent": sorted(map(str, expected - found))})
    return rows


def part_b() -> dict:
    from tests.model_building.test_audit import SEEDED, with_terms
    extra = [("missing + h.c.", m(CHI_D, f("S", 0, role=FieldRole.mediator, charges={"extra": {"D": 1.0}})),
              (["S", "~chi", "chi"], "scalar", "y"), "hermiticity"),
             ("anapole without a vector", m(CHI_D, f("S", 0, role=FieldRole.mediator, self_conjugate=True)),
              (["~chi", "chi", "S"], "anapole", "a"), "Lorentz")]
    seeded = []
    for what, spec, term, check in [*SEEDED, *extra]:
        report = audit(with_terms(spec, term))
        seeded.append({"error": what, "caught": not report.valid and check in {p.check for p in report.problems},
                       "checks": sorted({p.check for p in report.problems})})
    clean = []
    for g in yaml.safe_load((ROOT / "docs/dm8/gate_models.yaml").read_text())["models"]:
        report = audit(ModelSpec.model_validate(g["reference"]["spec"]))
        clean.append({"model": f"DM8 {g['id']}", "valid": report.valid})
    for name, (spec, _) in TEXTBOOK.items():
        if spec is not None:
            report = audit(general_spec(spec, general_lagrangian(content(spec))))
            clean.append({"model": f"generated: {name}", "valid": report.valid and not report.missing})
    return {"seeded": seeded, "clean": clean}


def part_c() -> list[dict]:
    from tests.model_building.test_audit import with_terms
    singlet = with_terms(m(f("S", 0, self_conjugate=True, dark_parity=-1)), (["S", "S", "S", "S"], "scalar", "lam"))
    idm = with_terms(m(f("Phi", 0, charges={"su2": 2, "hypercharge": 0.5}, dark_parity=-1),
                       f("H", 0, role=FieldRole.standard_model, charges={"su2": 2, "hypercharge": 0.5})),
                     (["H", "~H", "Phi", "~Phi"], "scalar", "lam3"), (["Phi", "Phi", "~Phi", "~Phi"], "scalar", "lam2"))
    zp = with_terms(m(CHI_D, ZP), (["Zp", "~chi", "chi"], "vector", "g"))
    dirac = with_terms(m(f("chi", 0.5, dark_parity=-1), f("S", 0, role=FieldRole.mediator, self_conjugate=True)),
                       (["S", "~chi", "chi"], "scalar", "y"))
    cases = [("Higgs portal of a singlet", singlet, lambda r: any(t.text == "H H* S S" for t in r.missing)),
             ("λ5 of the inert doublet", idm, lambda r: any(t.text == "H H Phi* Phi*" for t in r.missing)),
             ("Z′'s kinetic mixing and axial coupling", zp,
              lambda r: {"kinetic_mixing", "axial"} <= {t.lorentz for t in r.missing}),
             ("pseudoscalar Yukawa and Majorana masses of a neutral Dirac fermion", dirac,
              lambda r: any(t.lorentz == "pseudoscalar" for t in r.missing) and any("pseudo-Dirac" in n for n in r.notes))]
    return [{"omission": what, "found": bool(test(audit(spec)))} for what, spec, test in cases]


IDEAS = [
    ("scalar dark matter that talks to the Standard Model only through the Higgs boson",
     lambda fs: len(fs) == 1 and fs[0].spin == 0 and fs[0].charges.su2 == 1 and fs[0].charges.hypercharge == 0),
    ("a fermionic dark matter particle that interacts with quarks through a new heavy neutral vector boson",
     lambda fs: any(x.spin == 0.5 and x.role is FieldRole.dark_matter for x in fs) and any(x.spin == 1 for x in fs)),
    ("dark matter as the neutral component of a single electroweak multiplet, stable without any new symmetry",
     lambda fs: any(x.spin == 0.5 and x.charges.su2 == 5 and x.charges.hypercharge == 0 for x in fs)
     or any(x.spin == 0 and x.charges.su2 == 7 and x.charges.hypercharge == 0 for x in fs)),
    ("an inert second Higgs doublet whose lightest neutral component is the dark matter",
     lambda fs: any(x.spin == 0 and x.charges.su2 == 2 and abs(abs(x.charges.hypercharge) - 0.5) < 1e-9
                    and x.dark_parity == -1 for x in fs)),
    ("hidden-sector dark matter charged under a dark U(1) whose gauge boson kinetically mixes with hypercharge",
     lambda fs: any(x.spin == 1 for x in fs) and any(x.charges.extra for x in fs if x.spin in (0, 0.5))),
    ("a wino-like dark matter candidate",
     lambda fs: any(x.spin == 0.5 and x.charges.su2 == 3 and x.charges.hypercharge == 0 for x in fs)),
]


def part_d(llm) -> list[dict]:
    from adroit.orchestrator import ideas
    from adroit.agents.llm import BudgetExceeded
    rows = []
    for idea, textbook in IDEAS:
        try:
            result = ideas.run(ideas.IdeaRequest(text=idea, models=4), llm)
        except BudgetExceeded as error:
            rows.append({"idea": idea, "models": [], "all_valid": False, "dropped": 0,
                         "textbook_found": False, "status": "budget_exhausted", "reason": str(error),
                         "paid_response_ledger": str(llm.ledger_path)})
            break
        built = [new_fields(r.spec) for r in result.models]
        rows.append({"idea": idea, "models": [r.spec.name for r in result.models],
                     "all_valid": all(r.audit.valid for r in result.models),
                     "dropped": result.dropped, "textbook_found": any(textbook(fs) for fs in built)})
    return rows


def scripted():
    """Part D's dry run: a scripted model that proposes the textbook content for each idea."""
    from adroit.agents.ideas import ModelProposal, ModelProposals
    from adroit.agents.llm import FakeLLMClient
    answers = [[f("S", 0, self_conjugate=True, dark_parity=-1)], [CHI_D, ZP],
               [f("X", 0.5, self_conjugate=True, charges={"su2": 5})],
               [f("Phi", 0, charges={"su2": 2, "hypercharge": 0.5}, dark_parity=-1)],
               [f("chi", 0.5, dark_parity=-1, charges={"extra": {"Ap": 1.0}}), f("Ap", 1, role=FieldRole.mediator,
                                                                                 self_conjugate=True)],
               [f("W", 0.5, self_conjugate=True, charges={"su2": 3}, dark_parity=-1)]]
    return FakeLLMClient([ModelProposals(proposals=[ModelProposal(name=f"textbook{i}", fields=a)])
                          for i, a in enumerate(answers)])


def verdict(a, b, c, d) -> tuple[bool, str]:
    checks = {
        "A textbook inventories": all(r["pass"] for r in a),
        "B seeded errors caught": all(r["caught"] for r in b["seeded"]),
        "B no false alarms": all(r["valid"] for r in b["clean"]),
        "C omissions found": all(r["found"] for r in c),
        "D every proposal valid or dropped with a reason": all(r["all_valid"] for r in d),
        "D textbook content in ≥ 5 of 6": sum(r["textbook_found"] for r in d) >= 5,
    }
    lines = [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in checks.items()]
    return all(checks.values()), "\n".join(lines)


def main() -> int:
    """Parts A–D; returns the exit code."""
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--budget", type=float, default=1.0)
    parser.add_argument("--model", default="claude-opus-5-5")
    add_out_argument(parser, "dm12")
    args = parser.parse_args()
    folder = gate_output("dm12", args.out)
    a, b, c = part_a(), part_b(), part_c()
    if args.dry_run:
        d, spent, label = part_d(scripted()), 0.0, "dry run (part D scripted)"
    else:
        from adroit.agents.llm import BudgetedLLMClient, LLMClient
        llm = BudgetedLLMClient(LLMClient(model=args.model, max_tokens=8192), dollar_budget=args.budget)
        d, label = part_d(llm), f"live ({args.model})"
        spent = llm.spent
    passed, lines = verdict(a, b, c, d)
    name = "gate_dry_run" if args.dry_run else "gate_live"
    (folder / f"{name}.json").write_text(json.dumps({"A": a, "B": b, "C": c, "D": d, "spent": spent}, indent=1))
    text = (f"# DM12 gate, {label}\n\n{lines}\n\n**{'PASSED' if passed else 'NOT PASSED'}**; spent ${spent:.2f}.\n\n"
            + "\n".join(f"- D: {r['idea']} → {r['models']} (textbook: {r['textbook_found']}; dropped: {r['dropped']})"
                        for r in d) + "\n")
    (folder / f"{name}.md").write_text(text)
    print(text)
    print(f"written to {folder}")
    return BUDGET_STOPPED if any(r.get("status") == "budget_exhausted" for r in d) else exit_code(passed)


if __name__ == "__main__":
    sys.exit(main())

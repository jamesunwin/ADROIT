"""The auditor's audit of "only usable models" at e567d81 (audit/usable_models_open_items_audit.md): UO-01 and UO-02, each
reproduced as found and held repaired (UO-03 and UO-04 are in tests/ui/test_usable_models_ui.py; UO-05 and UO-06 are
deferred, the deferred list)."""

import pytest
import yaml
from typer.testing import CliRunner

from adroit.agents.ideas import ModelProposal, ModelProposals, ValueProposals
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import FieldRole, ModelField
from adroit.library.interactions import derivation as dv
from adroit.library.personal import Catalog, usable
from adroit.model_building import usable_models as um
from adroit.orchestrator import ideas
from adroit.orchestrator.model_approval import SCHEMA_VERSION, ModelApproval, model_identity
from tests.library.test_derivation import z_prime_model
from tests.model_building.test_usable_models import CHI, TAU_L, TAU_R, ZP, generated, values


@pytest.fixture(autouse=True)
def _own_library(tmp_path, monkeypatch):
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(), "model_library_dir", tmp_path / "model_library")


def approve(spec) -> ModelApproval:
    return ModelApproval(model_sha256=model_identity(spec), source_model_sha256=model_identity(spec), choice="supplied",
                         schema_version=SCHEMA_VERSION)


# --- UO-01: a zero gauge coupling is no route --------------------------------------------------------------------------

def charged(f: ModelField) -> ModelField:
    return f.model_copy(update={"charges": f.charges.model_copy(update={"extra": {"Zp": 1.0}})})


LIGHT = ModelField(name="a", role=FieldRole.mediator, spin=0, self_conjugate=True, mass_gev=10.0, dark_parity=1)
FIELDS = [charged(CHI), ZP, charged(TAU_L), charged(TAU_R), LIGHT]


def test_a_zero_gauge_coupling_is_no_route_however_the_fields_are_charged() -> None:
    """The auditor's fixture: Dirac χ at 50 GeV, a Z′ at 200 GeV, a 10 GeV scalar; χ and the taus of charge 1 under the Z′;
    g_Zp = 0 and the dark Yukawa 1, so χχ̄ → aa annihilates and the engine's domain does not refuse it. It had been
    offered and saved, the charges alone joining χ to the taus. With g_Zp = 0.1 the currents join them."""
    spec = generated(*FIELDS)
    yukawa = next(c.name for c in spec.couplings if c.name.startswith("y_chi_a") and c.name.endswith("_p"))
    dead, _ = um.finish(spec, {"g_Zp": (0.0, ""), yukawa: (1.0, "")}, [])
    assert {c.name: c.value for c in dead.couplings}["g_Zp"] == 0.0                  # the currents present, at zero
    assert um.unreachable(dead).startswith("its dark sector (")
    assert any("has no route to the Standard Model" in b for b in usable(dead).blocking)
    with pytest.raises(ValueError, match="no route to the Standard Model"):
        Catalog().save(dead, approve(dead))
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="tau Z'", fields=FIELDS)]),
                          ValueProposals(models=[values(("g_Zp", 0.0), (yukawa, 1.0))]), ValueProposals()])
    result = ideas.run(ideas.IdeaRequest(text="a tau-philic Z' with a light dark scalar"), fake)
    assert result.models == [] and "has no route to the Standard Model" in result.dropped[0]
    live, _ = um.finish(spec, {"g_Zp": (0.1, ""), yukawa: (1.0, "")}, [])
    assert um.unreachable(live) == ""


# --- UO-02: a matching with no finite value ----------------------------------------------------------------------------

def matching(*expressions: str) -> dv.Derivation:
    return dv.Derivation(model_name="V1", derived_by="user",
                         terms=[dv.WilsonTerm(name=f"C61{q}", expression=e) for q, e in zip("udscb", expressions)])


POLE = "-g_chi*g_q/(m_Zp**2-4*m_chi**2)"


def pole_model():
    """V1 with m_Zp = 2 m_χ: the auditor's pole, 1/(m_Zp² − 4m_χ²) at 200 and 100 GeV."""
    spec = z_prime_model()
    return spec.model_copy(update={"fields": [f.model_copy(update={"mass_gev": 200.0}) if f.name == "Zp" else f
                                              for f in spec.fields]})


@pytest.mark.parametrize("spec, expressions", [
    (z_prime_model(), ["sqrt(-1)*sqrt(-1)*0/0/m_Zp**2"] * 5),                         # undefined (NaN)
    (z_prime_model(), ["exp(1000)/m_Zp**2"] * 5),                                     # an overflow (infinity)
    (pole_model(), [POLE] * 5),                                                       # an exact pole
    (pole_model(), ["-g_chi*g_q/m_Zp**2"] * 4 + [POLE]),                              # one finite, one at the pole
], ids=["nan", "infinity", "pole", "mixed"])
def test_a_matching_with_no_finite_value_is_refused_by_the_gate_and_the_catalog(spec, expressions) -> None:
    """The auditor's UO-02: NaN and ∞ satisfy v != 0, and evalf turned the pole into −2.2 × 10¹²⁷; each had been saved."""
    supplied = matching(*expressions)
    verdict = usable(spec, derivation=supplied)
    assert not verdict.ok and any(b.startswith("its own matching has no finite value at the stated values")
                                  for b in verdict.blocking)
    with pytest.raises(ValueError, match="no finite value"):
        Catalog().save(spec, approve(spec), derivation=supplied)
    assert not Catalog().list()


def test_models_import_refuses_a_matching_at_its_pole_and_keeps_a_finite_one(tmp_path) -> None:
    from adroit.orchestrator.cli import app
    for name, spec, supplied, ok in (("pole", pole_model(), matching(*[POLE] * 5), False),
                                     ("finite", z_prime_model(), matching(*["-g_chi*g_q/m_Zp**2"] * 5), True)):
        path = tmp_path / f"{name}.yaml"
        path.write_text(yaml.safe_dump({"spec": spec.model_dump(mode="json"), "derivation": supplied.model_dump(mode="json")}))
        run = CliRunner().invoke(app, ["models", "import", str(path)])
        said = "".join(x for x in run.output if x not in "│╭╮╰╯─ \n")
        assert (run.exit_code == 0) is ok, run.output
        if not ok:
            assert "nofinitevalue" in said
    assert [r.spec.name for r in Catalog().list()] == ["V1"]


def test_a_finite_formula_keeps_its_value_exactly() -> None:
    """The exact check adds no change to a finite value: the evaluator still returns evalf's number."""
    table = dv.symbol_table(z_prime_model())
    assert dv.evaluate_expression("-g_chi*g_q/m_Zp**2", table) == -0.25 / 2000.0 ** 2
    with pytest.raises(dv.NotFinite):
        dv.evaluate_expression(POLE, dv.symbol_table(pole_model()))


# --- UO-07 (the auditor's recheck at 5f26f74, severe): every stated mass holds in the final spectrum, or the model is refused

A_FIELD = ModelField(name="a", role=FieldRole.mediator, spin=0, self_conjugate=True, dark_parity=1, mass_gev=400.0,
                     vev_gev=1000.0)
B_FIELD = ModelField(name="b", role=FieldRole.mediator, spin=0, self_conjugate=True, dark_parity=1, mass_gev=700.0,
                     vev_gev=1500.0)
DIRAC = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, dark_parity=-1, mass_gev=300.0)


def two_scalars(cross: float) -> tuple[list, ValueProposals]:
    """The auditor's fixture: Dirac χ at 300 GeV, real scalars a (400 GeV, v = 1000 GeV) and b (700 GeV, v = 1500 GeV), the
    a²b² coupling ``cross`` in V, Higgs portals 0.001 and a dark Yukawa 0.1."""
    pairs = [("lam_a_b_2", cross), ("lam_H_a", 0.001), ("lam_H_b", 0.001), ("y_chi_a_2_s", 0.1), ("lam_a", 0.02),
             ("lam_b", 0.03)]
    return [DIRAC, A_FIELD, B_FIELD], ValueProposals(models=[values(*pairs)])


def test_two_mixed_scalars_have_both_stated_masses_in_the_final_spectrum_or_are_refused() -> None:
    """UO-07: solved one after the other, b's solve had moved a: "a's stated mass, 400 GeV, is its physical mass" was
    said of a model whose a was at 272.3 GeV, below the dark matter, and the model was offered. Solved together:
    at a²b² = 0.005 both hold; at 0.03 no quartics give both (the mixing 4λv_a v_b = 1.8 × 10⁵ GeV² leaves
    A + B = 6.5 × 10⁵, AB = 1.108 × 10¹¹ with no real root), and it is refused with why."""
    from adroit.model_building.spectrum import spectrum
    fields, reply = two_scalars(0.005)
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="two", fields=fields)]), reply, ValueProposals()])
    result = ideas.run(ideas.IdeaRequest(text="dark matter with two dark Higgs mediators"), fake)
    assert result.dropped == [] and len(result.models) == 1
    states = spectrum(result.models[0].general)                       # recomputed from the offered model itself
    assert um._state_of(states, "a", 0) == pytest.approx(400.0, rel=1e-6)
    assert um._state_of(states, "b", 0) == pytest.approx(700.0, rel=1e-6)
    fields, reply = two_scalars(0.03)
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="two", fields=fields)]), reply, ValueProposals()])
    result = ideas.run(ideas.IdeaRequest(text="dark matter with two dark Higgs mediators"), fake)
    assert result.models == [] and um.UNSOLVED + "after 40 steps" in result.dropped[0]
    assert "may not be reachable together" in result.dropped[0]


def test_the_intake_offers_the_coupled_model_only_where_its_masses_hold() -> None:
    from adroit.orchestrator.model_intake import Intake
    svc = Intake()
    for cross, offered in ((0.005, 1), (0.03, 0)):
        fields, reply = two_scalars(cross)
        s = svc.start(1)
        d = svc.step(s.session_id, "idea", "two dark Higgs mediators", llm=FakeLLMClient(
            [ModelProposals(proposals=[ModelProposal(name="two", fields=fields)]), reply, ValueProposals()]))
        assert len(d.choices) == offered
        assert offered or any(um.UNSOLVED in x for x in d.not_offered)


def test_a_standard_model_vacuum_is_never_rescaled() -> None:
    """UO-07: a vector Higgsed only by an explicitly supplied SM H had its vacuum multiplied to 10³⁴ GeV, and an
    exhausted loop said it had given the vector its mass. The engine fixes H's vacuum: it is not the completion's."""
    higgs = ModelField(name="H", role=FieldRole.standard_model, spin=0, vev_gev=246.22,
                       charges=CHI.charges.model_copy(update={"su2": 2, "hypercharge": 0.5, "extra": {"Zp": 1.0}}))
    spec = generated(charged(CHI), ZP.model_copy(update={"mass_gev": 1000.0}), higgs)
    done, notes, problems, targets = um.vacuum_masses(spec)
    assert targets == {} and done.field("H").vev_gev == 246.22 and not notes


def test_a_solve_that_runs_out_of_steps_is_refused_not_claimed(monkeypatch) -> None:
    fields, reply = two_scalars(0.005)
    monkeypatch.setattr(um, "PHYSICAL_STEPS", 1)
    spec = generated(*fields)
    done, problems = um.finish(spec, {c.name: (c.value, "") for c in reply.models[0].couplings}, [])
    assert problems and problems[0].startswith(um.UNSOLVED + "after 1 steps")
    assert not [a for a in done.assumptions if "is its physical mass" in a]          # no success said


def test_the_final_check_reads_every_target_from_the_final_model() -> None:
    fields, reply = two_scalars(0.005)
    done, problems = um.finish(generated(*fields), {c.name: (c.value, "") for c in reply.models[0].couplings}, [])
    assert problems == []
    assert um.final_check(done, {("a", 0): 400.0, ("b", 0): 700.0}, None) == []
    moved = done.model_copy(update={"couplings": [c.model_copy(update={"value": c.value * 2}) if c.name == "lam_a"
                                                  else c for c in done.couplings]})
    (said,) = um.final_check(moved, {("a", 0): 400.0, ("b", 0): 700.0}, None)
    assert said.startswith(um.UNSOLVED) and "a is at" in said and "not 400 GeV" in said

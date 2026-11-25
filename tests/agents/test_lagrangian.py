"""DM8: the intake and derivation agents, offline (FakeLLMClient)."""

from __future__ import annotations

from adroit.agents import lagrangian
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import FieldRole, ModelCoupling, ModelField, ModelSpec
from adroit.core.prompts import TERSE_CLAUSE
from adroit.library.interactions import derivation as dv

SPEC = ModelSpec(name="toy", fields=[ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5,
                                                mass_gev=50.0)],
                 couplings=[ModelCoupling(name="g", value=0.1)])


def test_intake_returns_the_typed_model() -> None:
    fake = FakeLLMClient([SPEC])
    out = lagrangian.IntakeAgent(fake).run("Dirac dark matter of 50 GeV coupling to ...")
    call = fake.calls[0]
    assert out == SPEC and call["response_model"] is ModelSpec
    assert TERSE_CLAUSE in call["system"] and "Dirac dark matter of 50 GeV" in call["messages"][0]["content"]


def test_derivation_prompt_carries_the_basis_and_the_library() -> None:
    answer = dv.Derivation(model_name="toy", terms=[dv.WilsonTerm(name="C61u", expression="g/m_chi**2")])
    fake = FakeLLMClient([answer])
    out = lagrangian.DerivationAgent(fake, model="claude-opus-5-5").run(SPEC)
    call = fake.calls[0]
    assert out.derived_by == "claude-opus-5-5" and call["response_model"] is dv.Derivation
    for needle in ("C75f: m_f(χ̄χ)(f̄f)", "Majorana", "Real scalar", "−(g1 g2/M²) J1·J2", TERSE_CLAUSE,
                   "m_t t̄t → −(α_s/12π) G G", "leptons included"):
        assert needle in call["system"]
    assert "M_vector" in call["messages"][0]["content"] and '"name": "toy"' in call["messages"][0]["content"]


def test_the_library_menu_lists_every_mediator_card() -> None:
    menu = lagrangian.library_menu().splitlines()
    assert len(menu) == 14 and all(line.startswith("- M_") for line in menu)

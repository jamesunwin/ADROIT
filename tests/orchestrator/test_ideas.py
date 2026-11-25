"""Track 1's front end: a field content, a Lagrangian, or an idea (with a scripted model)."""

import pytest
from typer.testing import CliRunner

from adroit.agents.ideas import CouplingValue, ModelProposal, ModelProposals, ModelValues, ValueProposals
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import Charges, FieldRole, ModelField, ModelSpec
from adroit.orchestrator import cli, ideas


def _singlet(name: str = "S") -> ModelField:
    return ModelField(name=name, role=FieldRole.dark_matter, spin=0, self_conjugate=True, dark_parity=-1, mass_gev=60.0)


def test_a_field_content_gets_its_most_general_lagrangian() -> None:
    result = ideas.run(ideas.IdeaRequest(fields_spec=ModelSpec(name="singlet", fields=[_singlet()]), eft_dimension=6))
    m = result.models[0]
    assert m.audit.valid and m.general is not None and {o.text for o in m.operators} == {"S S", "H H* S S", "S S S S"}
    assert [o.text for o in m.eft] == ["(S²)(|H|⁴) / Λ^2"]          # S²|H|² is renormalizable; S²|H|⁴ is d = 6
    assert "Track 1" in ideas.report(result) and "H H* S S" in ideas.report(result)


def test_a_lagrangian_is_audited() -> None:
    spec = ModelSpec.model_validate({"name": "bad", "phase": "unbroken", "fields": [_singlet().model_dump()],
                                     "terms": [{"fields": [{"field": "S"}, {"field": "S"}, {"field": "S"}],
                                                "lorentz": "vector", "coupling": "g"}]})
    m = ideas.run(ideas.IdeaRequest(lagrangian_spec=spec)).models[0]
    assert not m.audit.valid and any(p.check == "Lorentz" for p in m.audit.problems)
    assert "Not valid" in ideas.report(ideas.IdeaResult(request=ideas.IdeaRequest(lagrangian_spec=spec), models=[m]))


def test_an_idea_becomes_proposals_built_audited_and_deduplicated() -> None:
    proposals = ModelProposals(proposals=[
        ModelProposal(name="singlet", rationale="Higgs portal", fields=[_singlet()], keywords=["scalar singlet"]),
        ModelProposal(name="same", fields=[_singlet("X")]),
        ModelProposal(name="bad", fields=[ModelField(name="W2", role=FieldRole.dark_matter, spin=1,
                                                     charges=Charges(su2=3))]),
        ModelProposal(name="idm", fields=[ModelField(name="Phi", role=FieldRole.dark_matter, spin=0, dark_parity=-1,
                                                     charges=Charges(su2=2, hypercharge=0.5))])])
    values = ValueProposals(models=[ModelValues(model=1, couplings=[CouplingValue(name="lam_H_S", value=0.1,
                                                                                   reason="a Higgs-portal benchmark")])])
    fake = FakeLLMClient([proposals, values])
    result = ideas.run(ideas.IdeaRequest(text="dark matter through the Higgs"), fake)
    # the owner, 2026-11-21: only usable models are offered; the inert doublet has no mass, so it is named, not offered
    assert [m.spec.name for m in result.models] == ["singlet"]
    assert any("same field content" in d for d in result.dropped) and any("bad" in d for d in result.dropped)
    assert any(d.startswith("idm: not offered") and "no value for the mass of Phi" in d for d in result.dropped)
    assert result.models[0].keywords == ["scalar singlet"] and fake.call_count == 2
    singlet = result.models[0].general
    # the builder quotes the potential, V ⊃ 0.1 S²|H|²; the model's coefficient is in L, so −0.1 (L-1)
    assert [(c.name, c.value) for c in singlet.couplings] == [("lam_H_S", -0.1)]
    assert any("S S S S is left out (lam_S = 0)" in a for a in singlet.assumptions)


def test_words_need_a_model_and_a_request_needs_an_input() -> None:
    with pytest.raises(ValueError, match="language model"):
        ideas.run(ideas.IdeaRequest(text="anything"))
    with pytest.raises(ValueError, match="give a field content"):
        ideas.run(ideas.IdeaRequest())


def test_the_command_line(tmp_path) -> None:
    out = CliRunner().invoke(cli.app, ["idea", "--fields", "docs/dm12/inert_doublet.yaml", "--out", str(tmp_path)])
    assert out.exit_code == 0 and "H H Phi* Phi*" in out.output and (tmp_path / "report.md").exists()
    assert CliRunner().invoke(cli.app, ["idea", "--text", "something"]).exit_code != 0     # no budget

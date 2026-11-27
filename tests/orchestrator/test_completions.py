"""Computable completions of a builder's proposal (R7 item 11, live check L9): explicit flavours and stated zeroed
couplings, presented as choices; never a silent change."""

import pytest

from adroit.agents.llm import FakeLLMClient
from adroit.agents.ideas import CouplingValue, ModelProposal, ModelProposals, ModelValues, ValueProposals
from adroit.core.model_spec import Charges, FieldRole, ModelField, ModelSpec, Phase
from adroit.orchestrator import ideas, promote, signal
from adroit.orchestrator.completions import completions, mixing_choice, single_flavours, zero_unrepresented
from adroit.parameter_space import simplified
from adroit.parameter_space.classify import Unsupported, classify

CHI = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, self_conjugate=True, dark_parity=-1, mass_gev=10.0)


def partner(hypercharge: float, su3: str) -> ModelField:
    return ModelField(name="phi", role=FieldRole.mediator, spin=0, dark_parity=-1, mass_gev=500.0,
                      charges=Charges(su3=su3, hypercharge=hypercharge))


def general(*fields: ModelField) -> ModelSpec:
    return ideas.from_fields(ModelSpec(name="tchannel", phase=Phase.unbroken, fields=list(fields))).general


@pytest.mark.parametrize("hypercharge,su3,flavours", [(2 / 3, "3", ["u"]), (-1 / 3, "3", ["d", "b"]),
                                                      (-1.0, "1", ["e", "mu", "tau"])])
def test_a_generation_multiplet_becomes_one_explicit_flavour_per_completion(hypercharge, su3, flavours) -> None:
    spec = general(CHI, partner(hypercharge, su3))
    with pytest.raises(Unsupported, match="one explicit SM flavour"):
        classify(spec)
    found = completions(spec)
    assert [o.choices[0].split(":")[1].split("(")[0].strip() for o in found] == flavours
    for o in found:
        cls, _, _ = classify(o.spec)
        assert cls.family.startswith("tchannel") or type(cls).__name__ == "TChannel"
        assert any(c.startswith("lam_H_phi = 0") for c in o.choices) and not o.flavour_only
        assert set(o.choices) <= set(o.spec.assumptions)                       # every choice is stated in the model
        assert {f.name for f in o.spec.fields} >= {flavours[found.index(o)]}


def test_a_zeroed_coupling_is_a_stated_choice_and_a_computable_model_needs_none() -> None:
    vector = simplified.model("vector", 10.0, 1000.0)
    assert zero_unrepresented(vector) == (vector, []) and single_flavours(vector) == []
    assert [o.choices for o in completions(vector)] == [[]]


def test_the_mixing_choice_is_named_for_the_researcher() -> None:
    assert "mixing angle" in mixing_choice("singlet scalar mixing needs an explicit mass-eigenstate/potential "
                                           "matching; a Higgs interaction does not specify a mixing angle")
    assert mixing_choice("something else") == ""


def test_promotion_says_why_no_completion_is_studied_live_check_l9(tmp_path, monkeypatch) -> None:
    """L9: two proposals refused and no child study, with no word on why. Since the owner's rule of 2026-11-21 a
    proposal the model builder gives no coupling value is not offered at all, and the promotion says why."""
    proposal = ModelProposal(name="MajoranaUpPartner", fields=[CHI, partner(2 / 3, "3")], rationale="t-channel")
    llm = FakeLLMClient([ModelProposals(proposals=[proposal]), ValueProposals(models=[])])
    from adroit.orchestrator import studies
    monkeypatch.setattr(studies, "record", lambda *a, **k: None)
    c = signal.Candidate(label="O1v@10", card_id="O1", isospin="v", mass_gev=10.0)
    request = signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=[])
    folder, ready, why, cost, offered = promote._proposals(tmp_path, c, llm, 1, request)
    assert ready == [] and offered == []
    text = why["MajoranaUpPartner"]
    assert "not offered" in text and "its dark matter (chi) has no interaction left" in text


def test_a_reproducing_completion_waits_for_the_researcher_with_its_file(tmp_path, monkeypatch) -> None:
    from adroit.orchestrator.completions import Completion
    spec = general(CHI, partner(-1 / 3, "3"))
    monkeypatch.setattr(promote, "_reproduces", lambda s, c: "b" in {f.name for f in s.fields})
    c = signal.Candidate(label="O4s@10", card_id="O4", isospin="s", mass_gev=10.0)
    now, waiting, why = promote._completed(spec, Unsupported("the t-channel portal needs one explicit SM flavour"), c)
    assert now == [] and len(waiting) == 1 and "wait for your choice" in why          # lam_H_phi = 0 is a choice
    request = signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=[])
    offered = promote._offer(tmp_path, request, c, "proposal", waiting)
    import shlex                         # the request a child of the candidate is studied with, run as saved (HC-02)
    from adroit.orchestrator.single_idea import SingleIdeaRequest
    assert offered[0].file.endswith(".yaml") and offered[0].request.endswith(".request.json")
    import hashlib                       # and the request offered, by its SHA-256 (HD-02)
    assert offered[0].command == (f"adroit single-idea --request {shlex.quote(offered[0].request)} "
                                  f"--request-sha256 {offered[0].request_sha256}")
    assert hashlib.sha256(open(offered[0].request, "rb").read()).hexdigest() == offered[0].request_sha256
    saved = SingleIdeaRequest.model_validate_json(open(offered[0].request).read())
    assert saved.experiment == "CDMS II Si (2013)" and saved.spec == waiting[0].spec
    out = promote.Promotion(parent=str(tmp_path), labels=[c.label], choices=offered)
    assert "## Computable completions that need your choice" in promote.report(out)
    flavour_only = Completion(spec=spec, choices=["one flavour: b (right-handed, bR) for the generator's dR"])
    from adroit.orchestrator import completions as module
    monkeypatch.setattr(module, "completions", lambda s: [flavour_only])
    monkeypatch.setattr(promote, "_reproduces", lambda s, c: True)
    now, waiting, why = promote._completed(spec, Unsupported("x"), c)
    assert now == [spec] and waiting == [] and "the one flavour that reproduces O4s@10" in why


def test_an_intake_idea_step_offers_the_completions_as_choices(tmp_path) -> None:
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service = Intake(Catalog(tmp_path / "library"))
    s = service.start(1)
    proposal = ModelProposal(name="MajoranaLeptonPartner", fields=[CHI, partner(-1.0, "1")], rationale="t-channel")
    values = ValueProposals(models=[ModelValues(model=1, couplings=[
        CouplingValue(name="y_eR_chi_phi_1", value=0.5, reason="a t-channel benchmark")])])
    draft = service.step(s.session_id, "idea", "a Majorana fermion with a slepton-like partner",
                         llm=FakeLLMClient([ModelProposals(proposals=[proposal]), values]))
    names = [c.spec.name for c in draft.choices]
    assert names == ["MajoranaLeptonPartner", "MajoranaLeptonPartner (e)", "MajoranaLeptonPartner (mu)",
                     "MajoranaLeptonPartner (tau)"]
    # the Higgs-portal quartic the idea does not call for is left out, and said so, before any flavour is chosen
    assert any(a.startswith("H H* phi phi* is left out (lam_H_phi = 0)") for a in draft.choices[0].spec.assumptions)
    assert all(c.ambiguities[0].startswith("one flavour:") for c in draft.choices[1:])
    assert all(c.applicability["track1_engine"] for c in draft.choices) and not draft.not_offered


def paper_lepton_portal() -> ModelSpec:
    """Live check L4 (the R7 gate): a paper's λ φ χ̄ P_R l, with a generic charged lepton l and φ of charge +1,
    written below electroweak breaking."""
    from adroit.core.model_spec import ModelCoupling, ModelTerm, Occurrence
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, self_conjugate=True, dark_parity=-1, mass_gev=50.0)
    phi = ModelField(name="phi", role=FieldRole.mediator, spin=0, dark_parity=-1, mass_gev=200.0,
                     charges=Charges(electric_charge=1.0))
    lepton = ModelField(name="l", role=FieldRole.standard_model, spin=0.5, charges=Charges(electric_charge=-1.0))
    term = ModelTerm(fields=[Occurrence(field="phi"), Occurrence(field="chi", conjugate=True), Occurrence(field="l")],
                     lorentz="chiral", coupling="lam", plus_hc=True, text="lam phi chibar P_R l + h.c.")
    return ModelSpec(name="paper", phase=Phase.broken, fields=[chi, phi, lepton], terms=[term],
                     couplings=[ModelCoupling(name="lam", value=0.5)])


def test_a_generic_lepton_gets_each_flavour_and_the_conjugate_convention_is_an_equivalence() -> None:
    spec = paper_lepton_portal()
    with pytest.raises(Unsupported, match="flavour 'l'"):
        classify(spec, generic_route=False)
    found = completions(spec)
    assert [classify(o.spec)[0].partner for o in found] == ["eR", "muR", "tauR"]
    for o in found:
        assert o.flavour_only and any(c.startswith("relabelled: phi ↔ phi*") for c in o.choices)
        assert o.spec.field("phi").charges.electric_charge == -1.0               # the portal's convention
        assert classify(o.spec)[1].g_chi == pytest.approx(0.5)                   # the coupling is untouched


def test_an_idea_run_says_which_model_files_are_computed_and_writes_completions(tmp_path) -> None:
    """The R7 gate's L1 finding: valid model files that Track 1 does not compute as written, without a word."""
    from adroit.orchestrator import runs
    result = ideas.IdeaResult(request=ideas.IdeaRequest(text="x"),
                              models=[ideas.from_fields(ModelSpec(name="lepton portal", phase=Phase.unbroken,
                                                                  fields=[CHI, partner(-1.0, "1")]))])
    lines = runs.write_models(tmp_path, result)
    text = "\n".join(lines)
    assert "not computed as it stands: the t-channel portal needs one explicit SM flavour" in text
    assert text.count("computable completion") == 3 and "lam_H_phi = 0" in text
    written = sorted(p.name for p in (tmp_path / "models").iterdir())
    assert written == ["lepton_portal.yaml"] + [f"lepton_portal_completion_{k}.yaml" for k in (1, 2, 3)]
    from adroit.orchestrator.model_approval import read_model
    import yaml
    completion = read_model(yaml.safe_load((tmp_path / "models" / "lepton_portal_completion_2.yaml").read_text()))
    assert type(classify(completion)[0]).__name__ == "TChannel"
    singlet = ideas.IdeaResult(request=ideas.IdeaRequest(text="x"), models=[ideas.from_fields(ModelSpec(
        name="singlet", phase=Phase.unbroken, fields=[ModelField(name="S", role=FieldRole.dark_matter, spin=0,
                                                                 self_conjugate=True, dark_parity=-1, mass_gev=300.0)]))])
    assert "computed by Track 1 as it stands" in "\n".join(runs.write_models(tmp_path / "s", singlet))


@pytest.mark.needs("poppler")
def test_a_paper_step_offers_the_completions(tmp_path) -> None:
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    from adroit.orchestrator.paper_model import PaperInterpretation, step
    from tests.experimental_fixtures import paper
    service = Intake(Catalog(tmp_path / "models"))
    session = service.start(.5)
    fake = FakeLLMClient([PaperInterpretation(transcription="Eq (1)", source_equation_tex=r"\lambda \phi \bar\chi_L e_R",
                                              equation_found=True, spec=paper_lepton_portal(), ambiguities=["flavour"])])
    draft = step(service, session.session_id, pdf=paper(tmp_path / "source.pdf"), pages=[2], equation="1", llm=fake)
    assert [c.spec.name for c in draft.choices] == ["paper", "paper (e)", "paper (mu)", "paper (tau)"]
    assert draft.choices[0].ambiguities == ["flavour"] and draft.choices[2].applicability["track1_engine"]


def test_a_zeroed_coupling_states_its_naturalness() -> None:
    spec = general(CHI, partner(2 / 3, "3"))
    choice = next(c for o in completions(spec) for c in o.choices if c.startswith("lam_H_phi = 0"))
    assert "technically natural only if a symmetry protects this zero" in choice

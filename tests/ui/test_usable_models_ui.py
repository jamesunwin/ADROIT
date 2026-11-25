"""Only usable models are offered and saved by the model-building step (the owner, 2026-11-21;
the usable models plan): the intake's offer and its approval, the review page's status and completion boxes,
the proposals not offered, and the library's label for a model saved before that cannot run."""

from urllib.parse import urlencode

import pytest
import yaml
from nicegui.testing import User

from adroit.agents.ideas import CouplingValue, ModelProposal, ModelProposals, ModelValues, ValueProposals
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import Charges, FieldRole, ModelField, ModelSpec
from adroit.library.personal import Catalog, usable
from adroit.orchestrator import ideas
from adroit.orchestrator.model_approval import SCHEMA_VERSION, ModelApproval, model_identity
from adroit.orchestrator.model_intake import NOT_SAVED, Intake
from adroit.ui.app import build_pages
from adroit.ui.model_library import missing_values, with_values

SINGLET = ModelField(name="S", role=FieldRole.dark_matter, spin=0, self_conjugate=True, dark_parity=-1, mass_gev=70.0)
DOUBLET = ModelField(name="Phi", role=FieldRole.dark_matter, spin=0, dark_parity=-1,
                     charges=Charges(su2=2, hypercharge=0.5))                          # no mass: cannot run


def fields_draft():
    """A field list ($0): its general Lagrangian, every coupling without a value: shown, not yet usable."""
    svc = Intake()
    s = svc.start()
    d = svc.step(s.session_id, "fields", yaml.safe_dump(ModelSpec(name="singlet", fields=[SINGLET]).model_dump(mode="json")))
    return svc, s, d


def idea_draft(*proposals: ModelProposal, values: ValueProposals | None = None):
    svc = Intake()
    s = svc.start(1)
    llm = FakeLLMClient([ModelProposals(proposals=list(proposals)), values or ValueProposals()])
    return svc, s, svc.step(s.session_id, "idea", "dark matter through the Higgs", llm=llm)


def page(s, d) -> str:
    return "/models/intake?" + urlencode({"session": s.session_id, "step": d.step_id})


def test_an_idea_step_offers_only_usable_models_and_names_the_others() -> None:
    values = ValueProposals(models=[ModelValues(model=1, couplings=[CouplingValue(name="lam_H_S", value=0.1)])])
    svc, s, d = idea_draft(ModelProposal(name="singlet", fields=[SINGLET]), ModelProposal(name="idm", fields=[DOUBLET]),
                           values=values)
    assert [c.spec.name for c in d.choices] == ["singlet"] and all(usable(c.spec).ok for c in d.choices)
    assert d.not_offered == ["idm: not offered, since it cannot run as built: no value for the mass of Phi"]
    assert svc.load(s.session_id, d.step_id).not_offered == d.not_offered          # stored, and its hash holds


def test_the_intakes_offer_keeps_only_usable_candidates_whatever_made_them() -> None:
    """A second line behind the builder's own (``ideas.complete``): a completion or any other candidate that cannot run
    is not offered either."""
    from adroit.orchestrator.model_intake import offer
    svc, s, d = fields_draft()
    unusable = d.choices[0]
    done = svc.choice(with_values(unusable.spec, {("coupling", "lam_H_S"): 0.1, ("coupling", "lam_S"): 0.2}))
    offered, refused = offer([unusable, done])
    assert offered == [done]
    assert refused == ["singlet: not offered, since it cannot run as built: no value for the coefficient lam_H_S; "
                       "no value for the coefficient lam_S"]


def test_an_idea_with_no_usable_model_is_a_draft_that_says_so_not_an_error() -> None:
    svc, s, d = idea_draft(ModelProposal(name="idm", fields=[DOUBLET]))
    assert d.choices == [] and d.not_offered[0].startswith("idm: not offered")


def test_an_unusable_model_is_not_saved_and_its_missing_values_make_one_that_is() -> None:
    svc, s, d = fields_draft()
    c = d.choices[0]
    assert missing_values(c.spec) == [("coupling", "lam_H_S"), ("coupling", "lam_S")]
    with pytest.raises(ValueError, match="this model cannot run yet, so it is not saved") as refused:
        svc.approve(s.session_id, d.step_id, 0, confirmed=True, expected_model_hash=model_identity(c.spec), tex=c.tex)
    assert str(refused.value).startswith(NOT_SAVED) and "no value for the coefficient lam_H_S" in str(refused.value)
    assert not Catalog().list()
    done = with_values(c.spec, {("coupling", "lam_H_S"): 0.1, ("coupling", "lam_S"): 0.2})
    d2 = svc.step(s.session_id, "typed", yaml.safe_dump(done.model_dump(mode="json")), parent_step=d.step_id)
    c2 = d2.choices[0]
    assert usable(c2.spec).ok
    r = svc.approve(s.session_id, d2.step_id, 0, confirmed=True, expected_model_hash=model_identity(c2.spec), tex=c2.tex)
    assert r.applicability["numerically_declared"] and r.applicability["track1_engine"]


async def test_the_review_page_says_it_cannot_run_and_completes_it_with_typed_values(user: User, tmp_path) -> None:
    svc, s, d = fields_draft()
    build_pages(tmp_path / "runs")
    await user.open(page(s, d))
    await user.should_see("Cannot run yet: it can be saved once these are settled")
    await user.should_see("• no value for the coefficient lam_H_S")
    assert not user.find("Save reviewed revision").elements.pop().enabled
    await user.should_see("Complete this model ($0)")
    user.find("value of lam_H_S").elements.pop().value = 0.1
    user.find("value of lam_S").elements.pop().value = 0.2
    user.find("Apply these values as a new draft").click()
    await user.should_see("Ready to constrain")
    assert user.find("Save reviewed revision").elements.pop().enabled
    user.find("I reviewed the transcription").click()
    user.find("Save reviewed revision").click()
    await user.should_see("One saved model")
    assert usable(Catalog().list()[0].spec).ok


async def test_the_review_page_lists_the_proposals_not_offered(user: User, tmp_path) -> None:
    svc, s, d = idea_draft(ModelProposal(name="idm", fields=[DOUBLET]))
    build_pages(tmp_path / "runs")
    await user.open(page(s, d))
    await user.should_see("No usable model could be built from this idea.")
    await user.should_see("Proposals not offered (1)")
    await user.should_see("• idm: not offered, since it cannot run as built: no value for the mass of Phi")
    link = user.find(marker="typed_model").elements.pop()           # phase C: the offer of a typed model, $0
    assert link.props.get("href") == "/models/intake" and "typed model" in link.text


async def test_a_proposed_value_and_what_was_left_out_are_shown_with_their_reasons(user: User, tmp_path) -> None:
    values = ValueProposals(models=[ModelValues(model=1, couplings=[
        CouplingValue(name="lam_H_S", value=0.1, reason="a Higgs-portal benchmark")], not_encoded=["a loop effect"])])
    svc, s, d = idea_draft(ModelProposal(name="singlet", fields=[SINGLET]), values=values)
    build_pages(tmp_path / "runs")
    await user.open(page(s, d))
    await user.should_see("Ready to constrain")
    # the builder quotes the potential; the model holds L's coefficient, and the line says both (L-1)
    await user.should_see("• lam_H_S = -0.1: a Higgs-portal benchmark (given in the potential, V ⊃ 0.1 × the term, so "
                          "-0.1 in L)")
    await user.should_see("Left out of the idea:")
    await user.should_see("• a loop effect")


async def test_a_flavour_universal_value_is_said_to_apply_to_every_generation(user: User, tmp_path) -> None:
    """The live gate's L-4: a quark coupling applies to u, c and t alike, and the review page says so."""
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=50.0, dark_parity=-1)
    v = ModelField(name="V", role=FieldRole.mediator, spin=1, self_conjugate=True, mass_gev=1000.0)
    values = ValueProposals(models=[ModelValues(model=1, couplings=[CouplingValue(name="g_V_chi_v", value=1.0),
                                                                    CouplingValue(name="g_V_Q_1", value=0.1)])])
    svc, s, d = idea_draft(ModelProposal(name="vector", fields=[chi, v]), values=values)
    build_pages(tmp_path / "runs")
    await user.open(page(s, d))
    await user.should_see("Ready to constrain")
    await user.should_see("Flavour (one coupling for every generation):")
    await user.should_see("• g_V_Q_1 = 0.1 applies alike to all three generations of Q")


async def test_a_draft_with_an_older_applicability_shows_one_answer_for_its_badge_and_its_save(user: User, tmp_path,
                                                                                              monkeypatch) -> None:
    """The auditor's UM-07: a draft stored under an older ``support`` (here: one that called the singlet's mass missing) had
    shown Ready while Save stayed disabled from the stored answer. Both now follow one answer, computed now."""
    from adroit.orchestrator import model_intake
    real = model_intake.support
    monkeypatch.setattr(model_intake, "support", lambda spec, *a: {**real(spec, *a), "missing_parameters": ["mass of S"],
                                                                     "numerically_declared": False})
    values = ValueProposals(models=[ModelValues(model=1, couplings=[CouplingValue(name="lam_H_S", value=0.1)])])
    svc, s, d = idea_draft(ModelProposal(name="singlet", fields=[SINGLET]), values=values)
    assert d.choices[0].applicability["missing_parameters"] == ["mass of S"]          # the stored, older answer
    monkeypatch.setattr(model_intake, "support", real)
    build_pages(tmp_path / "runs")
    await user.open(page(s, d))
    await user.should_see("Ready to constrain")
    assert user.find("Save reviewed revision").elements.pop().enabled


async def test_a_saved_model_that_cannot_run_is_labelled_incomplete(user: User, tmp_path) -> None:
    from tests.library.legacy import saved_before_the_rule
    spec = ideas.from_fields(ModelSpec(name="old singlet", fields=[SINGLET])).general           # every coupling empty
    identity = model_identity(spec)
    approval = ModelApproval(model_sha256=identity, source_model_sha256=identity, choice="supplied",
                             schema_version=SCHEMA_VERSION)
    with pytest.raises(ValueError, match="cannot run yet, so it is not saved"):
        Catalog().save(spec, approval)                                        # today's rule (the auditor's UM-02)
    saved_before_the_rule(Catalog(), spec, approval)                         # legacy data, as written before it
    build_pages(tmp_path / "runs")
    await user.open("/models?view=personal")
    await user.should_see("old singlet")
    await user.should_see("incomplete")


# --- the auditor's audit at e567d81: UO-03 and UO-04 ---------------------------------------------------------------------

def g5():
    """The DM8 gate's G5: a supplied matching with no Track 1 engine (a dipole), as the auditor used it."""
    from pathlib import Path
    from adroit.library.interactions.derivation import Derivation
    found = yaml.safe_load((Path(__file__).resolve().parents[2] / "docs/dm8/gate_models.yaml").read_text())["models"]
    m = next(m for m in found if m["id"] == "G5")
    return ModelSpec.model_validate(m["reference"]["spec"]), Derivation.model_validate(m["reference"]["derivation"])


def approve(spec) -> ModelApproval:
    return ModelApproval(model_sha256=model_identity(spec), source_model_sha256=model_identity(spec), choice="supplied",
                         schema_version=SCHEMA_VERSION)


async def test_an_unchanged_track2_model_refined_keeps_its_matching_and_saves(user: User, tmp_path) -> None:
    """UO-03: G5 refined unchanged had been judged without its matching: Save disabled, approval refused. It keeps
    it now, the same answer on the page and in approval; an edited model keeps none and is refused."""
    spec, supplied = g5()
    saved = Catalog().save(spec, approve(spec), derivation=supplied)
    assert not usable(spec).ok                                       # no Track 1 engine: Track 2 by its matching
    svc = Intake()
    s = svc.start(parent=saved.reference)
    d = svc.step(s.session_id, "typed", yaml.safe_dump(spec.model_dump(mode="json")))
    choice = d.choices[0]
    assert choice.spec == spec and svc.inherited_matching(s.session_id, d, choice) == supplied
    build_pages(tmp_path / "runs")
    await user.open(page(s, d))
    await user.should_see("Ready: it brings its own matching (Signal best fits)")
    assert user.find("Save reviewed revision").elements.pop().enabled
    r = svc.approve(s.session_id, d.step_id, 0, confirmed=True, expected_model_hash=model_identity(choice.spec),
                    tex=choice.tex)
    assert r.derivation == supplied and r.parent_revision == saved.revision_id
    edited = spec.model_copy(update={"fields": [f.model_copy(update={"mass_gev": f.mass_gev * 1.1})
                                                if f.role is FieldRole.dark_matter else f for f in spec.fields]})
    e = svc.step(s.session_id, "typed", yaml.safe_dump(edited.model_dump(mode="json")), parent_step=d.step_id)
    assert svc.inherited_matching(s.session_id, e, e.choices[0]) is None      # it must be derived again
    with pytest.raises(ValueError, match="cannot run yet"):
        svc.approve(s.session_id, e.step_id, 0, confirmed=True, expected_model_hash=model_identity(e.choices[0].spec),
                    tex=e.choices[0].tex)


async def test_old_models_are_ready_only_where_they_can_run_and_the_pickers_agree(user: User, tmp_path) -> None:
    """UO-04: an old 500 GeV n-plet (below its engine's domain) had been listed "incomplete" and "Constrain a model:
    ready"; an old all-zero matching "Signal best fits: ready" and in its picker. A Track-2-only model stays in the
    Track 2 picker and out of Track 1's."""
    from adroit.model_building import usable_models as um
    from adroit.ui.model_library import options
    from tests.library.legacy import saved_before_the_rule
    from tests.library.test_derivation import vector_derivation, z_prime_model
    from tests.model_building.test_usable_models import QUINTUPLET
    nplet, _ = um.finish(um.prepare(ideas.from_fields(ModelSpec(name="old n-plet", fields=[
        QUINTUPLET.model_copy(update={"mass_gev": 500.0})])).general), {}, [])
    old_nplet = saved_before_the_rule(Catalog(), nplet, approve(nplet))
    v1 = z_prime_model()
    silent = v1.model_copy(update={"name": "old silent", "couplings": [
        c.model_copy(update={"value": 0.0}) if c.name == "g_q" else c for c in v1.couplings]})
    old_silent = saved_before_the_rule(Catalog(), silent, approve(silent), derivation=vector_derivation())
    spec, supplied = g5()
    track2_only = Catalog().save(spec, approve(spec), derivation=supplied)
    assert old_nplet.reference not in options("track1")
    assert old_silent.reference not in options("track2")
    assert track2_only.reference in options("track2") and track2_only.reference not in options("track1")
    build_pages(tmp_path / "runs")
    await user.open("/models?view=personal")
    await user.should_see("old n-plet")
    await user.should_not_see("Constrain a model: ready")           # neither old model, nor G5, can be constrained
    await user.should_see("Signal best fits: ready")                 # G5 and the n-plet's own engine
    await user.open("/models/view?" + urlencode({"reference": old_nplet.reference}))
    await user.should_see("Constrain this model (Track 1): not yet")
    await user.open("/models/view?" + urlencode({"reference": old_silent.reference}))
    await user.should_see("Signal best fits with this model (Track 2): not yet")

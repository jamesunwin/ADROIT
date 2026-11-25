"""The auditor's audit of "only usable models" (2026-11-21, ``audit/usable_models_audit.md``, pin 345c209): UM-01 to UM-07,
each reproduced as it was found and held repaired. The builder's replies are scripted (FakeLLMClient); everything
else (generation, completion, classification, the engines' domains, the intake, the catalog, the command line) is
ADROIT's own."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest
import yaml
from typer.testing import CliRunner

from adroit.agents.ideas import CouplingValue, ModelProposal, ModelProposals, ModelValues, ValueProposals
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import Charges, FieldRole, ModelField, ModelSpec
from adroit.library.personal import Catalog, usable
from adroit.model_building import feynman
from adroit.model_building import gauge_basis as gbm
from adroit.model_building import usable_models as um
from adroit.orchestrator import ideas
from adroit.orchestrator.model_approval import select_model
from adroit.orchestrator.model_intake import Intake
from adroit.parameter_space.classify import classify
from tests.model_building.test_usable_models import CHI, QUINTUPLET, TAU_L, TAU_R, ZP, generated, values
from tests.orchestrator.test_completions import CHI as MAJORANA, partner

@pytest.fixture(autouse=True)
def _own_library(tmp_path, monkeypatch):
    """Each test its own empty model library (as ``tests/ui/conftest.py`` gives the pages' tests)."""
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(), "model_library_dir", tmp_path / "model_library")


SINGLET = ModelField(name="S", role=FieldRole.dark_matter, spin=0, self_conjugate=True, dark_parity=-1, mass_gev=70.0)
TAU_IDEA = "a tau-philic Z' with Dirac dark matter"


def built(fields, *pairs, text: str = TAU_IDEA, reply: ValueProposals | None = None) -> ideas.IdeaResult:
    """One proposal through the builder's calls (scripted) and the deterministic completion; a repair round, where one
    is made (phase C), gets no new values, so the first values' verdict stands."""
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="m", fields=list(fields))]),
                          reply or ValueProposals(models=[values(*pairs)]), ValueProposals()])
    return ideas.run(ideas.IdeaRequest(text=text), fake)


# --- UM-01: the engine's own refusal at the model's values ---------------------------------------------------------

@pytest.mark.parametrize("fields, pairs, reason", [
    ([SINGLET], [("lam_S", 0.2)], "no annihilation channel at tree level"),                   # a self-coupling only
    ([CHI, ZP, TAU_L, TAU_R], [("g_Zp_chi_v", 0.0), ("g_Zp_L_1", 0.0), ("g_Zp_eR_1", 0.0)],
     "no annihilation channel at tree level"),                                                # explicit zero currents
    ([QUINTUPLET.model_copy(update={"mass_gev": 500.0})], [], "applies from 1000 GeV"),      # below the n-plet's domain
    ([CHI, ZP, TAU_L, TAU_R], [("g_Zp_chi_v", 1e-12), ("g_Zp_L_1", 0.3), ("g_Zp_eR_1", 0.3)],
     "below the generic route's resolution"),
], ids=["self-coupling only", "zero currents", "n-plet below its domain", "coupling below resolution"])
def test_a_model_its_engine_refuses_at_its_values_is_not_offered(fields, pairs, reason) -> None:
    result = built(fields, *pairs)
    assert result.models == [] and len(result.dropped) == 1
    assert "its engine does not compute it at the stated values" in result.dropped[0] and reason in result.dropped[0]


def test_a_zero_valued_portal_is_not_a_route_whatever_engine_maps_it() -> None:
    """A singlet with its Higgs portal at 0: its class's domain does not see it, the route check does."""
    spec, _ = um.finish(um.prepare(ideas.from_fields(ModelSpec(name="s", fields=[SINGLET])).general),
                        {"lam_H_S": (0.0, ""), "lam_S": (0.2, "")}, [])
    assert any(b.startswith("its dark sector (S) has no route to the Standard Model") for b in usable(spec).blocking)
    live, _ = um.finish(um.prepare(ideas.from_fields(ModelSpec(name="s", fields=[SINGLET])).general),
                        {"lam_H_S": (0.1, ""), "lam_S": (0.2, "")}, [])
    assert usable(live).ok


def test_the_intakes_suggested_completions_are_refused_where_the_partner_is_lighter() -> None:
    svc = Intake()
    s = svc.start(1)
    light = partner(-1, "1").model_copy(update={"mass_gev": 5.0})
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="light partner", fields=[MAJORANA, light])]),
                          ValueProposals(models=[values(("y_eR_chi_phi_1", 0.5))])])
    d = svc.step(s.session_id, "idea", "a Majorana thermal relic with a charged scalar partner", llm=fake)
    assert d.choices == [] and d.not_offered
    assert all("its engine does not compute it at the stated values" in x for x in d.not_offered)


def test_a_model_completed_by_hand_that_cannot_annihilate_is_not_saved() -> None:
    """The manual route: two Z₂-odd scalars, every coupling zero but S's self-coupling."""
    t = SINGLET.model_copy(update={"name": "T", "mass_gev": 500.0})
    svc = Intake()
    s = svc.start()
    d = svc.step(s.session_id, "fields", yaml.safe_dump(ModelSpec(name="two", fields=[SINGLET, t]).model_dump(mode="json")))
    from adroit.ui.model_library import missing_values, with_values
    given = {key: (0.2 if key == ("coupling", "lam_S") else 0.0) for key in missing_values(d.choices[0].spec)}
    done = svc.step(s.session_id, "typed", yaml.safe_dump(with_values(d.choices[0].spec, given).model_dump(mode="json")),
                    parent_step=d.step_id)
    assert not usable(done.choices[0].spec).ok
    from adroit.orchestrator.model_approval import model_identity
    with pytest.raises(ValueError, match="cannot run yet, so it is not saved"):
        svc.approve(s.session_id, done.step_id, 0, confirmed=True, expected_model_hash=model_identity(done.choices[0].spec),
                    tex=done.choices[0].tex)
    assert not Catalog().list()


def _gate():
    path = Path(__file__).resolve().parents[2] / "docs/usable_models/gate.py"
    spec = importlib.util.spec_from_file_location("usable_models_gate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_live_gate_fails_when_the_builder_offers_only_models_that_cannot_annihilate() -> None:
    gate = _gate()
    replies = [r for _ in gate.IDEAS for r in (ModelProposals(proposals=[ModelProposal(name="self", fields=[SINGLET])]),
                                              ValueProposals(models=[values(("lam_S", 0.2))]),
                                              ValueProposals(models=[values(("lam_S", 0.3))]))]   # repair: still self
    rows = gate.run_all(FakeLLMClient(replies))
    passed, lines = gate.verdict(rows)
    assert not passed and "at least 10 of 12 ideas give a usable model: FAIL" in lines


def test_a_legacy_revision_its_engine_refuses_is_left_out_of_the_track1_picker() -> None:
    from adroit.ui.model_library import options
    from tests.library.legacy import saved_before_the_rule
    spec, _ = um.finish(um.prepare(ideas.from_fields(ModelSpec(name="self only", fields=[SINGLET])).general),
                        {"lam_S": (0.2, "")}, [])
    old = saved_before_the_rule(Catalog(), *select_model(ideas.from_lagrangian(spec)))
    assert old.reference not in options("track1")


# --- UM-02: every save refuses a model that cannot run --------------------------------------------------------------

def test_models_import_refuses_a_model_with_missing_couplings(tmp_path) -> None:
    from adroit.orchestrator.cli import app
    spec = ideas.from_fields(ModelSpec(name="incomplete", fields=[SINGLET])).general      # lam_H_S, lam_S empty
    path = tmp_path / "incomplete.yaml"
    path.write_text(yaml.safe_dump(spec.model_dump(mode="json")))
    run = CliRunner().invoke(app, ["models", "import", str(path)])
    said = "".join(x for x in run.output if x not in "│╭╮╰╯─ \n")          # the message, out of its box
    assert run.exit_code != 0 and "cannotrunyet,soitisnotsaved" in said
    assert "novalueforthecoefficientlam_H_S" in said and not Catalog().list()


def test_a_model_with_its_own_matching_needs_every_value_but_not_a_track1_engine() -> None:
    """The library keeps a model that brings its own matching (Track 2) without a Track 1 engine, as before (the owner
    confirmed it, 2026-11-21); a missing value or a failed audit still refuses it."""
    from tests.library.test_derivation import vector_derivation, z_prime_model
    spec, matching = z_prime_model(), vector_derivation()
    no_engine = {"missing_parameters": [], "structural_valid": True, "problems": [], "track1_engine": False}
    assert usable(spec, derivation=matching, ready=no_engine).ok
    assert not usable(spec, ready=no_engine).ok
    assert not usable(spec, derivation=matching, ready={**no_engine, "missing_parameters": ["coefficient c"]}).ok


def test_a_model_whose_own_matching_is_zero_at_its_values_is_not_saved() -> None:
    """The owner's tightening of the Track 2 exemption (2026-11-21): a matching whose every quark-level coefficient is
    zero at the stated values predicts no signal, so the model cannot run on any track. V1 with g_q = 0."""
    from tests.library.test_derivation import vector_derivation, z_prime_model
    from adroit.orchestrator.model_approval import SCHEMA_VERSION, ModelApproval, model_identity
    live = z_prime_model()
    dead = live.model_copy(update={"couplings": [c.model_copy(update={"value": 0.0}) if c.name == "g_q" else c
                                                 for c in live.couplings]})
    verdict = usable(dead, derivation=vector_derivation())
    assert not verdict.ok and any(b.startswith("its own matching gives every quark-level coefficient as zero")
                                  and "C61u" in b for b in verdict.blocking)
    approve = lambda s: ModelApproval(model_sha256=model_identity(s), source_model_sha256=model_identity(s),  # noqa: E731
                                      choice="supplied", schema_version=SCHEMA_VERSION)
    with pytest.raises(ValueError, match="cannot run yet, so it is not saved: .*predicts no signal"):
        Catalog().save(dead, approve(dead), derivation=vector_derivation())
    assert not Catalog().list()
    assert Catalog().save(live, approve(live), derivation=vector_derivation()).derivation is not None


# --- UM-03 and UM-04: the gauge currents' numerical vertices --------------------------------------------------------

def _charged(f: ModelField, q: float) -> ModelField:
    return f.model_copy(update={"charges": f.charges.model_copy(update={"extra": {"Zp": q}})})


@pytest.mark.parametrize("q", [-1.0, 1 / 3, -2 / 3, 0.01, 0.02, 0.123456])
def test_a_gauge_current_carries_its_charge_exactly(q) -> None:
    done, _ = um.finish(generated(_charged(CHI, q), ZP, _charged(TAU_L, 1.0), _charged(TAU_R, 1.0)),
                        {"g_Zp": (0.4, "")}, [])
    engine, p, _ = classify(done)
    diagonal = np.real(np.diag(feynman._weyl_currents(engine.at(p)[0])["Zp"]))
    assert diagonal == pytest.approx([0.4 * q, -0.4 * q], rel=1e-9)           # chi and chi^c: g q and −g q
    term = next(t for t in done.terms if t.fields[0].field == "Zp" and t.fields[1].field == "chi")
    assert f"(charge {um._exact(q)})" in term.text and "(charge 0)" not in term.text


def test_a_scalars_u1_charge_has_the_sign_of_its_hypercharge() -> None:
    """A complex scalar with Y = 1 and X = 1: its X generator, divided by g_X, is its hypercharge generator divided by
    g₁, read on the same real components; and a fermion with X = 1 keeps +g_X."""
    phi = ModelField(name="phi", role=FieldRole.mediator, spin=0, mass_gev=300.0, dark_parity=1,
                     charges=Charges(hypercharge=1.0, extra={"Zp": 1.0}))
    spec, _ = um.finish(generated(_charged(CHI, 1.0), ZP, phi), {"g_Zp": (0.4, "")}, [])
    engine, p, _ = classify(spec)
    mb = engine.at(p)[0]
    idx = [i for i, c in enumerate(mb.gauge.comp.coordinates) if c.field == "phi"]
    b = mb.gauge.gauge["B"][np.ix_(idx, idx)] / gbm.G1
    x = mb.gauge.gauge["Zp"][np.ix_(idx, idx)] / 0.4
    assert np.allclose(b, x) and not np.allclose(x, 0)
    assert np.real(np.diag(feynman._weyl_currents(mb)["Zp"]))[0] == pytest.approx(0.4)


# --- UM-05: the values reply checked -----------------------------------------------------------------------------

def test_a_value_for_no_coupling_is_named_on_the_offered_model() -> None:
    result = built([CHI, ZP, TAU_L, TAU_R], ("g_Zp_chi_v", 0.5), ("g_Zp_L_1", 0.3), ("g_Zp_eR_1", 0.3),
                   ("not_a_coupling", 0.7), ("m_chi", 999.0))
    spec = result.models[0].general
    assert spec.field("chi").mass_gev == 50.0
    assert ("a value was proposed for not_a_coupling, which is not one of this model's couplings: it was not used"
            in spec.assumptions)
    assert any(a.startswith("a value was proposed for m_chi") and "a mass is the proposal's own" in a
               for a in spec.assumptions)


def test_conflicting_values_are_never_chosen_between() -> None:
    reply = ValueProposals(models=[values(("g_Zp_chi_v", 0.5), ("g_Zp_L_1", 0.3), ("g_Zp_eR_1", 0.3)),
                                   values(("g_Zp_chi_v", 0.9))])
    result = built([CHI, ZP, TAU_L, TAU_R], reply=reply)
    assert result.models == []
    assert "conflicting values were proposed for g_Zp_chi_v (0.5, 0.9): none was used" in result.dropped[0]
    same = ValueProposals(models=[values(("g_Zp_chi_v", 0.5), ("g_Zp_L_1", 0.3), ("g_Zp_eR_1", 0.3)),
                                  values(("g_Zp_chi_v", 0.5))])                         # a repeat that agrees
    assert len(built([CHI, ZP, TAU_L, TAU_R], reply=same).models) == 1


def test_values_addressed_to_no_model_are_said() -> None:
    reply = ValueProposals(models=[ModelValues(model=9, couplings=[CouplingValue(name="g", value=0.1)])])
    result = built([QUINTUPLET], reply=reply, text="a quintuplet")
    assert len(result.models) == 1
    assert result.dropped == ["the model builder's values named model 9, but there are 1: they were not used (g = 0.1)"]


# --- UM-06: a Standard Model alias renamed only when nothing else changes ----------------------------------------

@pytest.mark.parametrize("field", [TAU_L.model_copy(update={"chirality": "R"}), TAU_L.model_copy(update={"generations": 3})],
                         ids=["right-handed tauL", "tauL in three generations"])
def test_a_field_that_contradicts_its_alias_keeps_its_own_name(field) -> None:
    out, notes = um.canonical_fields([field])
    assert out == [field] and notes == []


def test_an_alias_without_a_chirality_says_the_one_it_is_given() -> None:
    out, notes = um.canonical_fields([TAU_L.model_copy(update={"chirality": ""})])
    assert (out[0].name, out[0].chirality, out[0].generations) == ("Ltau", "L", 1)
    assert notes == ["tauL is written Ltau, the name ADROIT's engines give this Standard Model field (its chirality, "
                     "not stated, is L)"]
    out, notes = um.canonical_fields([TAU_L])
    assert notes == ["tauL is written Ltau, the name ADROIT's engines give this Standard Model field"]

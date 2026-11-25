"""Only usable models from the model builder (the owner, 2026-11-21; the usable models plan): the gate
``library.personal.usable``, the deterministic completion ``model_building.usable_models``, and the two models that
could not run (a tau-philic Z′, a Y = 1 quintuplet) built again through the builder's two calls, offline."""

import math

import pytest
import yaml

from adroit.agents.ideas import (CouplingValue, ModelProposal, ModelProposals, ModelValues, ValueProposals,
                                 ValuesAgent)
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import Charges, FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm, Occurrence, Phase
from adroit.library.personal import support, usable
from adroit.model_building import usable_models as um
from adroit.orchestrator import ideas
from adroit.orchestrator.model_approval import read_model

CHI = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=50.0, dark_parity=-1)
ZP = ModelField(name="Zp", role=FieldRole.mediator, spin=1, self_conjugate=True, mass_gev=200.0, dark_parity=1)
TAU_L = ModelField(name="tauL", role=FieldRole.standard_model, spin=0.5, chirality="L",
                   charges=Charges(su2=2, hypercharge=-0.5))
TAU_R = ModelField(name="tau_R", role=FieldRole.standard_model, spin=0.5, chirality="R", charges=Charges(hypercharge=-1.0))
QUINTUPLET = ModelField(name="psi5", role=FieldRole.dark_matter, spin=0.5, mass_gev=10000.0, dark_parity=-1,
                        charges=Charges(su2=5, hypercharge=1.0))


def generated(*fields: ModelField) -> ModelSpec:
    """The builder's fields, named as the engines name them, through the generator, prepared."""
    named, notes = um.canonical_fields(list(fields))
    spec = ModelSpec(name="m", phase=Phase.unbroken, fields=named, assumptions=notes)
    return um.prepare(ideas.from_fields(spec).general)


def values(*pairs: tuple[str, float], model: int = 1, not_encoded=()) -> ModelValues:
    return ModelValues(model=model, couplings=[CouplingValue(name=n, value=v, reason="a benchmark") for n, v in pairs],
                       not_encoded=list(not_encoded))


# --- the gate -----------------------------------------------------------------------------------------------------

def test_a_model_without_a_mass_or_a_coupling_value_is_not_usable_and_says_which() -> None:
    spec = generated(CHI.model_copy(update={"mass_gev": None}), ZP, TAU_L, TAU_R)
    verdict = usable(spec)
    assert not verdict.ok and "no value for the mass of chi" in verdict.blocking
    assert "no value for the coefficient eps_Zp_B" in verdict.blocking
    assert not any(b.startswith("no engine") for b in verdict.blocking)   # the engine's refusal only once all are given


def test_a_mass_its_scalar_potential_contract_states_is_not_missing() -> None:
    spec = read_model(yaml.safe_load(open("docs/examples/complete_scalar_running.yaml")))
    assert spec.field("S").mass_gev is None and spec.scalar_potential.singlet_mass_gev == 200.0
    ready = support(spec)
    assert ready["missing_parameters"] == [] and ready["numerically_declared"] and usable(spec, ready=ready).ok


# --- the completion -----------------------------------------------------------------------------------------------

def test_a_flavour_is_named_as_the_engines_name_it_only_with_its_quantum_numbers() -> None:
    fields, notes = um.canonical_fields([CHI, TAU_L, TAU_R])
    assert [f.name for f in fields] == ["chi", "Ltau", "tauR"] and fields[1].chirality == "L"
    assert notes == ["tauL is written Ltau, the name ADROIT's engines give this Standard Model field",
                     "tau_R is written tauR, the name ADROIT's engines give this Standard Model field"]
    wrong = TAU_L.model_copy(update={"charges": Charges(su2=2, hypercharge=0.5)})       # not the τ doublet's Y
    assert um.canonical_fields([wrong])[0][0].name == "tauL"
    new = CHI.model_copy(update={"name": "tauL"})                                    # not a Standard Model field
    assert um.canonical_fields([new])[0][0].name == "tauL"


def test_a_massive_vectors_standard_model_currents_are_written_in_dirac_form() -> None:
    spec = generated(CHI, ZP, TAU_L, TAU_R)
    tau = {t.coupling: t for t in spec.terms if {o.field for o in t.fields} & {"Ltau", "tauR"}}
    assert {(t.lorentz, tuple(o.field for o in t.fields), tuple(o.conjugate for o in t.fields)) for t in tau.values()} \
        == {("vector", ("Zp", "Ltau", "Ltau"), (False, True, False)), ("vector", ("Zp", "tauR", "tauR"), (False, True, False))}
    assert not any(t.lorentz == "chiral" and len(t.fields) == 3 and t.fields[0].field == "Zp"
                   and spec.field(t.fields[1].field).role is FieldRole.standard_model for t in spec.terms)


def test_a_gauge_u1_gets_its_currents_from_the_charges_with_one_gauge_coupling() -> None:
    charged = lambda f, q: f.model_copy(update={"charges": f.charges.model_copy(update={"extra": {"Zp": q}})})  # noqa: E731
    scalar = ModelField(name="phi", role=FieldRole.mediator, spin=0, mass_gev=300.0, dark_parity=1,
                        charges=Charges(extra={"Zp": 2.0}))
    spec = generated(charged(CHI, 1 / 3), ZP, scalar)
    currents = {t.fields[1].field: (t.lorentz, t.coupling) for t in spec.terms if t.fields[0].field == "Zp"
                and len(t.fields) == 3 and t.fields[1].field == t.fields[2].field}
    # the scalar's coefficient is −g Q in scalar_current's convention (D = ∂ + i k X): the same covariant derivative
    # as the fermion's +g Q current (the auditor's UM-04; its generator is checked against hypercharge's below)
    assert currents["chi"] == ("vector", "(1/3)*g_Zp") and currents["phi"] == ("scalar_current", "(-2)*g_Zp")
    assert [c.name for c in spec.couplings].count("g_Zp") == 1
    assert any(a.startswith("Zp is the gauge boson of a new U(1)") for a in spec.assumptions)


def test_values_are_given_checked_and_every_other_coupling_is_zero_and_said() -> None:
    spec = generated(CHI, ZP, TAU_L, TAU_R)
    done, problems = um.finish(spec, {"g_Zp_chi_v": (0.5, "a benchmark"), "g_Zp_L_1": (0.3, ""),
                                      "g_Zp_eR_1": (4.0, "too big"), "g_nope": (1.0, "")}, ["the neutrino's mass"])
    assert {c.name: c.value for c in done.couplings} == {"g_Zp_chi_v": 0.5, "g_Zp_L_1": 0.3, "g_Zp_eR_1": None}
    assert done.field("chi") and next(c for c in done.couplings if c.name == "g_Zp_chi_v").justification == \
        "proposed by the model builder: a benchmark"
    assert any("exceeds the perturbative bound" in p for p in problems)            # |g| > √(4π): not used
    assert any("g_nope, which is not one of this model's couplings" in p for p in problems)
    assert "no value for the coefficient g_Zp_eR_1" in usable(done).blocking      # so not offered
    left = [a for a in done.assumptions if " is left out (" in a]
    assert any(a.startswith("Zp_μν B^μν is left out (eps_Zp_B = 0)") for a in left)
    assert {t.coupling for t in done.terms} == {"g_Zp_chi_v", "g_Zp_L_1", "g_Zp_eR_1"}
    assert done.dropped == ["the neutrino's mass"]


def test_a_zero_inside_a_term_that_remains_is_kept_as_zero() -> None:
    term = ModelTerm(fields=[Occurrence(field="Zp"), Occurrence(field="chi", conjugate=True), Occurrence(field="chi")],
                     lorentz="vector", coupling="g_a + g_b", text="(g_a + g_b) Zp chibar gamma chi")
    spec = ModelSpec(name="m", phase=Phase.broken, fields=[CHI, ZP], terms=[term],
                     couplings=[ModelCoupling(name="g_a"), ModelCoupling(name="g_b")])
    done, _ = um.finish(spec, {"g_a": (0.4, "")}, [])
    assert {c.name: c.value for c in done.couplings} == {"g_a": 0.4, "g_b": 0.0} and done.terms == [term]


def test_an_operator_above_dimension_four_named_in_the_idea_is_said_left_out() -> None:
    flags = um.dimension_flags("a quintuplet with a dimension-7 Majorana splitting and a d = 5 operator, dim 4 too")
    assert flags == ["a dimension-5 operator named in the idea: the model holds renormalizable terms only (dimension ≤ 4)",
                     "a dimension-7 operator named in the idea: the model holds renormalizable terms only (dimension ≤ 4)"]


def test_dark_matter_left_without_an_interaction_is_named() -> None:
    spec, _ = um.finish(generated(CHI, ZP, TAU_L, TAU_R), {}, [])
    assert um.inert(spec) == "its dark matter (chi) has no interaction left: no coupling of it was given a value"
    assert um.inert(generated(QUINTUPLET)) == ""                   # an electroweak multiplet keeps its gauge couplings


def test_the_values_call_shows_each_coupling_with_its_term() -> None:
    fake = FakeLLMClient([ValueProposals()])
    ValuesAgent(fake).run("a tau-philic Z'", [generated(CHI, ZP, TAU_L, TAU_R)])
    text = fake.calls[0]["messages"][0]["content"]
    assert "Model 1: m" in text and "chi (dark_matter, spin 0.5, mass 50 GeV)" in text
    assert "- g_Zp_L_1: Zp_μ Ltaū γ^μ Ltau; 0" in text and "- eps_Zp_B: Zp_μν B^μν; 0" in text


# --- the two models of 2026-11-21, built again ------------------------------------------------------------------

TAU_IDEA = ("Tau-philic U(1) Z' with Dirac singlet DM (simplified model): independent vector couplings of the Z' to "
            "chi and to taus, with no tree-level electron, muon or quark coupling")


def test_the_tau_philic_z_prime_is_offered_usable_with_only_the_couplings_it_asks_for() -> None:
    proposal = ModelProposal(name="Tau-philic Z'", simplified="the Z' mass's origin", fields=[CHI, ZP, TAU_L, TAU_R],
                             stability="Z2: chi odd")
    fake = FakeLLMClient([ModelProposals(proposals=[proposal]),
                          ValueProposals(models=[values(("g_Zp_chi_v", 0.5), ("g_Zp_L_1", 0.3), ("g_Zp_eR_1", 0.3))])])
    result = ideas.run(ideas.IdeaRequest(text=TAU_IDEA), fake)
    assert result.dropped == [] and len(result.models) == 1
    spec = result.models[0].general
    assert usable(spec).ok and support(spec)["track1_engine"]
    assert {t.coupling for t in spec.terms} == {"g_Zp_chi_v", "g_Zp_L_1", "g_Zp_eR_1"}       # no ε, no quarks
    assert {f.name for f in spec.fields} >= {"chi", "Zp", "Ltau", "tauR"}


def test_the_quintuplet_is_offered_with_its_mass_and_its_splitting_is_said_left_out() -> None:
    idea = "Vectorlike Y=1 quintuplet with dimension-7 Majorana splitting"
    proposal = ModelProposal(name="Y=1 quintuplet", fields=[QUINTUPLET], stability="its quantum numbers")
    split = "dimension-7 Majorana splitting: it enters the n-plet engine as the neutral splitting δm₀, set in the study"
    fake = FakeLLMClient([ModelProposals(proposals=[proposal]), ValueProposals(models=[values(not_encoded=[split])])])
    result = ideas.run(ideas.IdeaRequest(text=idea), fake)
    spec = result.models[0].general
    assert usable(spec).ok and support(spec)["engine"]["name"] == "5-plet, Y = 1"
    assert spec.dropped == [split]               # the builder's note names dimension 7: the flag is not said again (L-6)
    alone = ideas.run(ideas.IdeaRequest(text=idea), FakeLLMClient([ModelProposals(proposals=[proposal]),
                                                                    ValueProposals(models=[values()])]))
    assert alone.models[0].general.dropped[0].startswith("a dimension-7 operator named in the idea")   # else flagged


def test_a_proposal_without_a_mass_is_not_offered_and_says_why() -> None:
    proposal = ModelProposal(name="Y=1 quintuplet", fields=[QUINTUPLET.model_copy(update={"mass_gev": None})])
    fake = FakeLLMClient([ModelProposals(proposals=[proposal]), ValueProposals()])
    result = ideas.run(ideas.IdeaRequest(text="a quintuplet"), fake)
    assert result.models == []
    assert result.dropped == ["Y=1 quintuplet: not offered, since it cannot run as built: no value for the mass of psi5"]
    assert "## Proposals not offered" in ideas.report(result)


@pytest.mark.parametrize("value", [math.inf, -5.0])
def test_a_value_outside_the_bound_leaves_the_proposal_not_offered(value) -> None:
    proposal = ModelProposal(name="Z'", fields=[CHI, ZP, TAU_L, TAU_R])
    fake = FakeLLMClient([ModelProposals(proposals=[proposal]),
                          ValueProposals(models=[values(("g_Zp_chi_v", value), ("g_Zp_L_1", 0.3))])])
    result = ideas.run(ideas.IdeaRequest(text=TAU_IDEA), fake)
    assert result.models == [] and "no value for the coefficient g_Zp_chi_v" in result.dropped[0]


# --- the live gate's findings L-4 and L-5 (plan, section 9) -------------------------------------------------------

PSEUDOSCALAR = ModelField(name="a", role=FieldRole.mediator, spin=0, self_conjugate=True, mass_gev=300.0, dark_parity=1)
VECTOR = ModelField(name="V", role=FieldRole.mediator, spin=1, self_conjugate=True, mass_gev=1000.0)


def test_a_dark_sector_with_no_route_to_the_standard_model_is_not_offered() -> None:
    """L-5: the live gate offered a pseudoscalar mediator whose every Standard Model coupling was zero; its only
    process was χχ̄ → aa. Such a model is not offered; with its Higgs portal kept, it is."""
    proposal = ModelProposal(name="pseudoscalar", fields=[CHI, PSEUDOSCALAR])
    alone = FakeLLMClient([ModelProposals(proposals=[proposal]), ValueProposals(models=[values(("y_chi_a_2_p", 1.0))]),
                           ValueProposals()])                      # phase C's repair round: no new values
    result = ideas.run(ideas.IdeaRequest(text="Dirac dark matter with a pseudoscalar mediator"), alone)
    assert result.models == []
    assert result.dropped == ["pseudoscalar: not offered, since it cannot run as built: its dark sector (a, chi) has no "
                              "route to the Standard Model: no remaining term joins it to a Standard Model field, and "
                              "none of it carries a Standard Model charge, so no constraint sees it; after a repair "
                              "round: the model builder gave no new values"]
    portal = FakeLLMClient([ModelProposals(proposals=[proposal]),
                            ValueProposals(models=[values(("y_chi_a_2_p", 1.0), ("mu_H_a", 10.0))])])
    result = ideas.run(ideas.IdeaRequest(text="Dirac dark matter with a pseudoscalar mediator"), portal)
    assert [m.general.name for m in result.models] == ["pseudoscalar"] and result.dropped == []


def test_a_route_is_a_term_a_standard_model_charge_or_a_u1_the_standard_model_carries() -> None:
    chi_d = CHI.model_copy(update={"charges": Charges(extra={"UD": 1.0})})
    ud = ModelField(name="UD", role=FieldRole.mediator, spin=1, self_conjugate=True, mass_gev=100.0)
    mixed, _ = um.finish(generated(chi_d, ud), {"g_UD": (0.1, ""), "eps_UD_B": (1e-4, "")}, [])
    unmixed, _ = um.finish(generated(chi_d, ud), {"g_UD": (0.1, "")}, [])
    assert um.unreachable(mixed) == "" and um.unreachable(unmixed).startswith("its dark sector (UD, chi) has no route")
    assert um.unreachable(generated(QUINTUPLET)) == ""                         # an electroweak multiplet
    lmu = ModelField(name="Lmu", role=FieldRole.standard_model, spin=0.5, chirality="L",
                     charges=Charges(su2=2, hypercharge=-0.5, extra={"X": 1.0}))
    x = ModelField(name="X", role=FieldRole.mediator, spin=1, self_conjugate=True, mass_gev=100.0)
    chi_x = CHI.model_copy(update={"charges": Charges(extra={"X": 1.0})})
    # charges alone join nothing (the auditor's UO-01): no engine builds an interaction from them; the currents do
    gauged = ModelSpec(name="m", phase=Phase.unbroken, fields=[chi_x, x, lmu])
    assert um.unreachable(gauged).startswith("its dark sector (chi) has no route")


def test_a_flavour_universal_coupling_is_marked_for_the_builder_and_stated_in_the_model() -> None:
    """L-4: the builder read g_V_Q_1 as a first-generation coupling; it applies to all three generations."""
    spec = generated(CHI, VECTOR)
    fake = FakeLLMClient([ValueProposals()])
    ValuesAgent(fake).run("a leptophobic vector", [spec])
    text = fake.calls[0]["messages"][0]["content"]
    assert "- g_V_Q_1: V_μ Q̄ γ^μ Q [all 3 generations of Q alike]; 0" in text
    assert "a coupling's numeric suffix (_1, _2) numbers the term, never a generation" in fake.calls[0]["system"]
    tau = FakeLLMClient([ValueProposals()])                       # Ltau is one generation: not marked
    ValuesAgent(tau).run("a tau-philic Z'", [generated(CHI, ZP, TAU_L, TAU_R)])
    sent = tau.calls[0]["messages"][0]["content"]
    assert "γ^μ Ltau; 0" in sent and "generations of Ltau" not in sent and "[all 3 generations of Q alike]" in sent
    done, _ = um.finish(spec, {"g_V_chi_v": (1.0, ""), "g_V_Q_1": (0.1, "")}, [])
    assert ("g_V_Q_1 = 0.1 applies alike to all three generations of Q: the model takes the Standard Model's flavour "
            "structure universal (one coupling per structure)") in done.assumptions
    assert not [a for a in done.assumptions if a.startswith("g_V_chi_v =")]   # the dark matter is one field

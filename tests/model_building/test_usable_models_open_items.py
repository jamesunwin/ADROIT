"""The open items of "only usable models" (the usable models plan, sections 9 and 10), closed before the public
release (the owner, 2026-11-21: no deferrals): L-1, L-2, L-3, L-6, L-7 and phase C. The builder's replies are scripted
(FakeLLMClient); everything else is ADROIT's own."""

import pytest

from adroit.agents.ideas import ModelProposal, ModelProposals, ValueProposals, ValuesAgent
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import Charges, FieldRole, ModelField
from adroit.library.personal import usable
from adroit.model_building import usable_models as um
from adroit.model_building.spectrum import spectrum
from adroit.orchestrator import ideas
from tests.model_building.test_usable_models import generated, values


@pytest.fixture(autouse=True)
def _own_library(tmp_path, monkeypatch):
    """Each test its own empty model library."""
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(), "model_library_dir", tmp_path / "model_library")


PHI = ModelField(name="phi", role=FieldRole.dark_matter, spin=0, self_conjugate=False, dark_parity=-1, mass_gev=300.0)


# --- L-7: a complex singlet's portal ---------------------------------------------------------------------------------

def test_a_term_that_breaks_a_complex_fields_number_is_marked_and_the_true_portal_runs() -> None:
    """L-7: H H* phi phi (+ h.c.) splits phi into two real states, ±λv² about m², that no interaction joins: two
    relics, which the engine rightly refuses. H H* phi phi* is the portal, and with it the complex singlet runs."""
    spec = generated(PHI)
    breaking = {t.coupling for t in spec.terms if um.breaks_number(spec, t)}
    assert breaking == {"lam_phi", "lam_H_phi", "lam_phi_2", "lam_phi_3"}           # phi², H†H phi², phi⁴, phi³phi*
    fake = FakeLLMClient([ValueProposals()])
    ValuesAgent(fake).run("a complex scalar singlet with a Higgs portal", [spec])
    text = fake.calls[0]["messages"][0]["content"]
    assert "- lam_H_phi: in V: H H* phi phi [breaks phi's number: splits phi into separate particles]; 0" in text
    assert "- lam_H_phi_2: in V: H H* phi phi*; 0" in text
    assert "A Higgs portal to a complex scalar X is the term with both X and X*" in fake.calls[0]["system"]
    split, _ = um.finish(spec, {"lam_H_phi": (0.1, "")}, [])
    assert not usable(split).ok
    assert any(a.startswith("lam_H_phi = -0.1 breaks the number of phi") for a in split.assumptions)   # in L
    portal, _ = um.finish(spec, {"lam_H_phi_2": (0.1, "")}, [])
    assert usable(portal).ok and not [a for a in portal.assumptions if "breaks the number" in a]


def test_a_term_joining_two_complex_fields_is_never_called_breaking() -> None:
    """phi₁ phi₂* may keep a combined number: only a term in which one complex field alone moves is named."""
    other = PHI.model_copy(update={"name": "eta", "role": FieldRole.mediator, "mass_gev": 500.0})
    spec = generated(PHI, other)
    mixed = [t for t in spec.terms if {o.field for o in t.fields} == {"phi", "eta"} and len(t.fields) == 2]
    assert mixed and not any(um.breaks_number(spec, t) for t in mixed)


# --- L-1: the inert doublet ------------------------------------------------------------------------------------------

H2 = ModelField(name="H2", role=FieldRole.dark_matter, spin=0, self_conjugate=False, dark_parity=-1, mass_gev=70.0,
                charges=Charges(su2=2, hypercharge=0.5))
# a textbook light inert doublet, its potential quoted in V: λ₃|H|²|H₂|² + λ₄|H†H₂|² + λ₅[(H₂†H)² + h.c.] + λ₂|H₂|⁴
TEXTBOOK = [("lam_H_H2_2", 0.1), ("lam_H_H2_2_c2", -0.1), ("lam_H_H2", -0.05), ("lam_H2", 0.1)]


def built(fields, *pairs) -> ideas.IdeaResult:
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="IDM", fields=list(fields))]),
                          ValueProposals(models=[values(*pairs)])])
    return ideas.run(ideas.IdeaRequest(text="an inert second Higgs doublet"), fake)


def test_the_inert_doublet_is_offered_with_its_potential_in_v_and_its_stated_mass_physical() -> None:
    """L-1: every inert-doublet proposal had been a saddle (m² = −9044 GeV²). The model's coefficients are in L
    (V ⊃ −k P) and its mass_gev is the Lagrangian mass, while the builder quoted V and the physical mass."""
    result = built([H2], *TEXTBOOK)
    assert result.dropped == [] and len(result.models) == 1
    spec = result.models[0].general
    assert usable(spec).ok
    assert {c.name: c.value for c in spec.couplings}["lam_H_H2_2"] == -0.1                 # +0.1 in V is −0.1 in L
    assert "(given in the potential, V ⊃ 0.1 × the term, so -0.1 in L)" in \
        next(c.justification for c in spec.couplings if c.name == "lam_H_H2_2")
    states = spectrum(spec)
    dm = states.dark_matter()
    assert dm.mass_gev == pytest.approx(70.0, rel=1e-6)                                     # the stated, physical mass
    assert min(s.mass_gev for s in states.states if s.parity == -1 and s.charge) > dm.mass_gev   # H⁰ below H⁺
    assert any(a.startswith("H2's stated mass, 70 GeV, is the dark matter's physical mass: its Lagrangian mass is")
               for a in spec.assumptions)


def test_the_values_call_asks_for_the_potential_in_v_with_each_terms_indices() -> None:
    fake = FakeLLMClient([ValueProposals()])
    ValuesAgent(fake).run("an inert doublet", [generated(H2)])
    text, system = fake.calls[0]["messages"][0]["content"], fake.calls[0]["system"]
    assert "- lam_H_H2_2_c2: in V: H H* H2 H2* (contraction 2) (indices H[i] H*[j] H2[j] H2*[i]); 0" in text
    assert "- lam_H_H2_2: in V: H H* H2 H2* (indices H[i] H*[i] H2[j] H2*[j]); 0" in text
    assert 'a coupling marked "in V" is the coefficient of its term in the scalar potential V' in system
    assert "The dark matter's stated mass is its physical mass" in system


def test_a_physical_mass_no_real_lagrangian_mass_gives_is_refused_with_why() -> None:
    """A 20 GeV doublet with λ₃ = 1 in V: the Higgs alone gives it about 174 GeV, so μ² < 0 would be needed."""
    result = built([H2.model_copy(update={"mass_gev": 20.0})], ("lam_H_H2_2", 1.0), ("lam_H2", 0.1))
    assert result.models == [] and len(result.dropped) == 1
    assert "the dark matter's stated mass, 20 GeV, cannot be its physical mass at these couplings" in result.dropped[0]
    assert "no value for the mass of H2" in result.dropped[0]


def test_a_library_map_keeps_the_stated_mass_and_its_portal_sign_reads_the_potential() -> None:
    """The real singlet's Higgs-portal map reads the stated mass as physical already (no conversion), and its λ_HS is
    −2C from L: the builder's V ⊃ 0.1 S² |H|² is C = −0.1 in L, so λ_HS = 0.2 > 0 (V ⊃ ½ λ_HS S²|H|²)."""
    singlet = ModelField(name="S", role=FieldRole.dark_matter, spin=0, self_conjugate=True, dark_parity=-1,
                         mass_gev=300.0)
    spec = built([singlet], ("lam_H_S", 0.1)).models[0].general
    assert next(f for f in spec.fields if f.name == "S").mass_gev == 300.0
    assert not [a for a in spec.assumptions if "Lagrangian mass is" in a]
    from adroit.parameter_space.classify import classify
    _, point, _ = classify(spec)
    assert point.g_chi == pytest.approx(0.2)


# --- L-2: a Higgsed U(1) ---------------------------------------------------------------------------------------------

DARK = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=300.0, dark_parity=-1,
                  charges=Charges(extra={"Zp": 1.0}))
VECTOR = ModelField(name="Zp", role=FieldRole.mediator, spin=1, self_conjugate=True, mass_gev=1000.0, dark_parity=1)
DARK_HIGGS = ModelField(name="phiD", role=FieldRole.mediator, spin=0, mass_gev=500.0, dark_parity=1, vev_gev=3000.0,
                        charges=Charges(extra={"Zp": 1.0}))


def test_a_higgsed_vector_keeps_its_stated_mass_from_the_vacuum_and_the_dark_higgs_its_own() -> None:
    """L-2: seven dark-Higgs proposals were refused ("Zp states its mass twice: mass_gev and a vacuum value it couples
    to"). The vector's mass is kept and the vacuum value scaled for it (m = g q v); the dark Higgs's stated mass is
    physical and its self-quartic solved for it."""
    result = built([DARK, VECTOR, DARK_HIGGS], ("g_Zp", 0.5), ("lam_H_phiD", 0.01))
    assert result.dropped == [] and len(result.models) == 1
    spec = result.models[0].general
    assert usable(spec).ok
    assert spec.field("Zp").mass_gev is None and spec.field("phiD").mass_gev is None
    assert spec.field("phiD").vev_gev == pytest.approx(2000.0)                               # 1000 GeV / (0.5 × 1)
    states = spectrum(spec)
    assert next(s for s in states.states if s.name == "Zp").mass_gev == pytest.approx(1000.0, rel=1e-6)
    assert um._state_of(states, "phiD", 0) == pytest.approx(500.0, rel=1e-6)
    assert any(a.startswith("Zp's stated mass, 1000 GeV, comes from the vacuum: the vacuum values are set to phiD 2000")
               for a in spec.assumptions)
    assert any(a.startswith("phiD's stated mass, 500 GeV, is its physical mass: its self-coupling lam_phiD =")
               for a in spec.assumptions)
    assert "solved from phiD's stated mass" in next(c.justification for c in spec.couplings if c.name == "lam_phiD")


def test_a_mass_the_vacuum_gives_is_not_called_missing() -> None:
    """A scalar with a vacuum value and the vector it Higgses take their masses from the vacuum (G1's convention)."""
    from adroit.library.personal import support
    spec = generated(DARK, VECTOR.model_copy(update={"mass_gev": None}),
                     DARK_HIGGS.model_copy(update={"mass_gev": None}))
    missing = support(spec)["missing_parameters"]
    assert not [m for m in missing if m.startswith("mass of")]


# --- phase C: the repair round and the plain "none could be built" --------------------------------------------------

SINGLET = ModelField(name="S", role=FieldRole.dark_matter, spin=0, self_conjugate=True, dark_parity=-1, mass_gev=300.0)


def scripted(*replies) -> FakeLLMClient:
    return FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="singlet", fields=[SINGLET])]), *replies])


def test_a_model_its_values_cannot_run_gets_one_repair_round_that_sees_why() -> None:
    """The first values give the singlet its self-coupling only (no annihilation channel); the builder sees that and
    gives the portal; the model is offered, saying it was repaired. One more call, for all such models."""
    fake = scripted(ValueProposals(models=[values(("lam_S", 0.2))]), ValueProposals(models=[values(("lam_H_S", 0.1))]))
    result = ideas.run(ideas.IdeaRequest(text="a scalar singlet"), fake)
    assert fake.call_count == 3 and result.dropped == [] and len(result.models) == 1
    asked = fake.calls[2]["messages"][0]["content"]
    assert "These models could not run with the values given before" in asked
    assert "Values given before: lam_S = 0.2" in asked and "Why it cannot run: its engine does not compute it" in asked
    spec = result.models[0].general
    assert usable(spec).ok and {c.name: c.value for c in spec.couplings} == {"lam_H_S": -0.1}
    assert any(a.startswith("repaired: its first values could not run (its engine does not compute it")
               for a in spec.assumptions)


def test_a_repair_that_does_not_help_is_said_with_both_rounds_reasons() -> None:
    fake = scripted(ValueProposals(models=[values(("lam_S", 0.2))]), ValueProposals(models=[values(("lam_S", 0.5))]))
    result = ideas.run(ideas.IdeaRequest(text="a scalar singlet"), fake)
    assert result.models == [] and len(result.dropped) == 1
    assert "no annihilation channel" in result.dropped[0] and "; after a repair round: " in result.dropped[0]
    assert "No usable model could be built from this idea." in ideas.report(result)
    silent = scripted(ValueProposals(models=[values(("lam_S", 0.2))]), ValueProposals())
    assert ideas.run(ideas.IdeaRequest(text="a scalar singlet"), silent).dropped[0].endswith(
        "after a repair round: the model builder gave no new values")


def test_a_model_its_structure_stops_gets_no_repair_round() -> None:
    """A mass the proposal did not give cannot be repaired by values: no further call is made."""
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="m", fields=[SINGLET.model_copy(
        update={"mass_gev": None})])]), ValueProposals(models=[values(("lam_H_S", 0.1))])])
    result = ideas.run(ideas.IdeaRequest(text="a scalar singlet"), fake)
    assert fake.call_count == 2 and "after a repair round" not in result.dropped[0]
    assert ideas.repairable(["no engine computes it: x"]) is False
    assert ideas.repairable(["its dark sector (S) has no route to the Standard Model: x"]) is True


def test_a_repair_round_the_budget_refuses_is_said_and_the_cap_kept() -> None:
    from adroit.agents.budget import BudgetExceeded

    class Capped(FakeLLMClient):
        def complete_structured(self, system, messages, response_model, *args, **kwargs):
            if len(self.calls) == 2:
                self.calls.append({"system": system, "messages": messages})
                raise BudgetExceeded(0.9, 1.0, 0.2)
            return super().complete_structured(system, messages, response_model, *args, **kwargs)
    fake = Capped([ModelProposals(proposals=[ModelProposal(name="singlet", fields=[SINGLET])]),
                   ValueProposals(models=[values(("lam_S", 0.2))])])
    result = ideas.run(ideas.IdeaRequest(text="a scalar singlet"), fake)
    assert result.models == [] and "after a repair round: the repair round could not be made (" in result.dropped[0]


# --- L-6: notes said once ------------------------------------------------------------------------------------------

def test_an_omission_said_twice_in_other_words_is_said_once_the_fuller_way() -> None:
    """L-6: the live gate's wino had "Loop mass splitting" from one call and "Radiative mass splittings (~166 MeV per
    charge step) from electroweak loops; enter as parameters" from the other. Distinct omissions are all kept."""
    short, full = "Loop mass splitting", ("Radiative mass splittings (~166 MeV per charge step) from electroweak loops; "
                                         "enter as parameters")
    other = "Sommerfeld enhancement of the 2 TeV triplet's annihilation"
    assert um.distinct([short, other, full, short]) == [full, other]
    merged, _ = um.finish(generated(SINGLET).model_copy(update={"dropped": [short]}), {"lam_H_S": (0.1, "")},
                          [full, other])
    assert merged.dropped == [full, other]                         # finish says each omission once
    assert um.distinct(["Charged-neutral splittings set by gauge loops only",
                        "Dim-7 operator (chi chi)(H*)^4/Lambda^3 giving the Majorana mass"]) == [
        "Charged-neutral splittings set by gauge loops only",
        "Dim-7 operator (chi chi)(H*)^4/Lambda^3 giving the Majorana mass"]


def test_the_values_call_is_shown_what_the_proposal_already_left_out() -> None:
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="w", fields=[PHI], not_encoded=["Loop splitting"])]),
                          ValueProposals()])
    ideas.run(ideas.IdeaRequest(text="a complex singlet"), fake)
    assert "Already noted as left out: Loop splitting" in fake.calls[1]["messages"][0]["content"]
    assert 'Never repeat what a model lists as "Already noted as left out"' in " ".join(fake.calls[1]["system"].split())


# --- L-3: SU(2) contractions that are not pairings -----------------------------------------------------------------

TRIPLET = ModelField(name="T", role=FieldRole.dark_matter, spin=0.5, self_conjugate=True, mass_gev=300.0,
                     dark_parity=-1, charges=Charges(su2=3))
DOUBLET = ModelField(name="D", role=FieldRole.mediator, spin=0.5, mass_gev=1000.0, dark_parity=-1,
                     charges=Charges(su2=2, hypercharge=0.5))


def test_the_triplet_doublet_yukawas_take_their_unique_invariant_and_the_model_runs() -> None:
    """L-3: "the term T D H* has no unique pairing of its su2 indices": 3 ⊗ 2 ⊗ 2 has one invariant, but it is not a
    product of pairings. It is now computed, its normalisation stated, and the model is offered."""
    result = built([TRIPLET, DOUBLET], ("y_T_D_H", 0.3), ("y_T_D_H_2", 0.3))
    assert result.dropped == [] and len(result.models) == 1
    spec = result.models[0].general
    assert usable(spec).ok
    assert {t.text for t in spec.terms if t.coupling.startswith("y_T_D_H")} == {
        "T D H* (the unique SU(2) invariant, unit-normalised: Σ|C|² = 1)",
        "T D^c H (the unique SU(2) invariant, unit-normalised: Σ|C|² = 1)"}


def test_a_majorana_triplets_conjugate_components_conserve_charge_in_every_mass_term() -> None:
    """The gauge basis's h.c. had used ξ_m for the conjugate of a Majorana multiplet's component m, which only a
    metric-paired tensor tolerates: the triplet–doublet mass matrix joined T⁺ to D⁺. Each state has one charge."""
    spec = built([TRIPLET, DOUBLET], ("y_T_D_H", 0.3), ("y_T_D_H_2", 0.3)).models[0].general
    states = spectrum(spec)
    odd = sorted((round(s.charge), round(s.mass_gev, 3)) for s in states.states if s.parity == -1)
    assert {q for q, _ in odd} == {0, 1}                           # three neutral Majorana states, two charged Dirac
    assert sum(q == 0 for q, _ in odd) == 3 and sum(q == 1 for q, _ in odd) == 2
    dm = states.dark_matter()
    assert dm.mass_gev == pytest.approx(300.0, rel=1e-6)           # the stated, physical mass (L-1's reading)
    assert 0 < sum(w for k, w in dm.composition.items() if k.startswith("D.")) < 0.01   # mixed with the doublet


def test_a_unique_invariant_beyond_pairings_is_computed_and_a_term_with_several_is_still_refused() -> None:
    """A quintuplet completion's 5 ⊗ 4 ⊗ 2 has one invariant (computed and checked invariant); 2 ⊗ 2 ⊗ 2 ⊗ 2 of four
    different doublets has two, and stays refused for its indices to be stated."""
    from adroit.core.model_spec import ModelSpec, Phase
    from adroit.model_building import indices as ix
    five = ModelField(name="F", role=FieldRole.dark_matter, spin=0.5, self_conjugate=True, charges=Charges(su2=5))
    four = ModelField(name="Q4", role=FieldRole.mediator, spin=0.5, charges=Charges(su2=4, hypercharge=0.5))
    higgs = ModelField(name="H", role=FieldRole.standard_model, spin=0, charges=Charges(su2=2, hypercharge=0.5))
    spec = ModelSpec(name="q", phase=Phase.unbroken, fields=[five, four, higgs])
    occ = [("F", False), ("Q4", False), ("H", True)]
    tensor = ix.unique_invariant(spec, occ, "su2")
    assert tensor is not None and abs((abs(tensor) ** 2).sum() - 1) < 1e-12
    ix.check_invariant(spec, ix.Contraction(occ, tensor, ix.np.ones((1, 1, 1))), "5 4 2")
    doublets = [ModelField(name=n, role=FieldRole.dark_matter if n == "A" else FieldRole.mediator, spin=0,
                           charges=Charges(su2=2)) for n in "ABCD"]
    four_spec = ModelSpec(name="d", phase=Phase.unbroken, fields=doublets)
    assert ix.unique_invariant(four_spec, [(n, False) for n in "ABCD"], "su2") is None


# --- the second live gate's findings (2026-11-21, runs/gates/usable_models/20261121T181250133469Z) ------------------

def test_a_trial_mass_at_a_saddle_is_raised_until_the_dark_matter_has_its_stated_mass() -> None:
    """L-8: the plain inert doublet had been refused at a saddle (m² = −18.7 GeV²): at the builder's couplings the first
    trial, μ = m, has λ_L v²/2 < −m², and both the classification and the solver had stopped there. A 60 GeV doublet with
    λ₃ + λ₄ + λ₅ ≈ −0.13 in V: μ² = 7540 GeV² gives its dark matter 60 GeV, H⁰ below A⁰ and H⁺."""
    light = H2.model_copy(update={"mass_gev": 60.0})
    pairs = [("lam_H_H2_2", -0.03), ("lam_H_H2_2_c2", -0.08), ("lam_H_H2", -0.01), ("lam_H2", 0.1)]
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="IDM", fields=[light])]),
                          ValueProposals(models=[values(*pairs)]), ValueProposals()])
    result = ideas.run(ideas.IdeaRequest(text="an inert doublet"), fake)
    assert result.dropped == [] and len(result.models) == 1
    states = spectrum(result.models[0].general)
    odd = sorted((s.mass_gev, s.charge) for s in states.states if s.parity == -1)
    assert odd[0] == (pytest.approx(60.0, rel=1e-6), 0.0) and odd[1][0] > 60.0 and odd[-1][1] == 1.0
    assert any("its Lagrangian mass is 86.8" in a for a in result.models[0].general.assumptions)


def test_a_saddle_the_dark_matters_mass_cannot_lift_is_named() -> None:
    """A saddle in another scalar (a singlet whose portal is −1 in V, v²/2 > its m²): no dark-matter mass removes it."""
    other = ModelField(name="S", role=FieldRole.mediator, spin=0, self_conjugate=True, dark_parity=1, mass_gev=100.0)
    spec = generated(H2.model_copy(update={"mass_gev": 300.0}), other)
    done, problems = um.finish(spec, {"lam_H_S": (-1.0, ""), "lam_H2": (0.1, ""), "lam_S": (0.1, "")}, [])
    assert any("is a saddle" in p and "whatever the Lagrangian mass of H2" in p for p in problems)
    assert not usable(done).ok


def test_a_right_handed_fields_current_carries_minus_q_g_on_its_conjugate_block() -> None:
    """L-9: a right-handed Weyl field's vector current had been refused. ψ_R = η†, so ψ_R†σψ_R = −η†σ̄η: its η block
    carries −q g, as a Dirac field's η does (the auditor's UM-03 test: χ gives [g q, −g q])."""
    from adroit.model_building import feynman
    from adroit.parameter_space.classify import classify
    from tests.model_building.test_usable_models import CHI, TAU_L, TAU_R, ZP

    def charged(f, q):
        return f.model_copy(update={"charges": f.charges.model_copy(update={"extra": {"Zp": q}})})
    nu = ModelField(name="nuR", role=FieldRole.mediator, spin=0.5, chirality="R", dark_parity=1, mass_gev=1000.0)
    done, _ = um.finish(generated(charged(CHI, 1.0), ZP, charged(nu, -1.0), charged(TAU_L, 1.0), charged(TAU_R, 1.0)),
                        {"g_Zp": (0.2, "")}, [])
    engine, point, _ = classify(done)
    mb = engine.at(point)[0]
    current = feynman._weyl_currents(mb)["Zp"]
    eta = [i for i, w in enumerate(mb.gauge.comp.weyl) if w.field == "nuR" and w.block == "eta"]
    assert eta and [current[i, i].real for i in eta] == [pytest.approx(0.2)]          # −q g with q = −1
    assert not [w for w in mb.gauge.comp.weyl if w.field == "nuR" and w.block == "xi"]   # a right-handed field: η only


B_MINUS_L = "BmL"


def bl(q: float, **charges) -> Charges:
    return Charges(extra={B_MINUS_L: q}, **charges)


def test_a_b_minus_l_model_with_its_standard_model_charges_and_right_handed_neutrinos_is_offered() -> None:
    """L-9: the live gate's B − L was refused twice over: its ν_R current, and no route, its Standard Model fermions
    unlisted (the proposal prompt had said to list only new fields). Listed with their charges, the model is offered."""
    sm = [ModelField(name="Q", role=FieldRole.standard_model, spin=0.5, chirality="L", generations=3,
                     charges=bl(1 / 3, su3="3", su2=2, hypercharge=1 / 6)),
          ModelField(name="uR", role=FieldRole.standard_model, spin=0.5, chirality="R", generations=3,
                     charges=bl(1 / 3, su3="3", hypercharge=2 / 3)),
          ModelField(name="dR", role=FieldRole.standard_model, spin=0.5, chirality="R", generations=3,
                     charges=bl(1 / 3, su3="3", hypercharge=-1 / 3)),
          ModelField(name="L", role=FieldRole.standard_model, spin=0.5, chirality="L", generations=3,
                     charges=bl(-1.0, su2=2, hypercharge=-0.5)),
          ModelField(name="eR", role=FieldRole.standard_model, spin=0.5, chirality="R", generations=3,
                     charges=bl(-1.0, hypercharge=-1.0))]
    fields = [ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, dark_parity=-1, mass_gev=500.0, charges=bl(1.0)),
              ModelField(name=B_MINUS_L, role=FieldRole.mediator, spin=1, self_conjugate=True, mass_gev=3000.0,
                         dark_parity=1),
              ModelField(name="nuR", role=FieldRole.mediator, spin=0.5, chirality="R", generations=3, dark_parity=1,
                         mass_gev=1000.0, charges=bl(-1.0)), *sm]
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="B-L", fields=fields)]),
                          ValueProposals(models=[values(("g_BmL", 0.2))]), ValueProposals()])
    result = ideas.run(ideas.IdeaRequest(text="a B-L Z' with Dirac dark matter"), fake)
    assert result.dropped == [] and [m.general.name for m in result.models] == ["B-L"]
    assert "A second exception: when Standard Model fermions carry charge under a new gauged U(1)" in \
        fake.calls[0]["system"]


def test_a_field_stating_its_mass_twice_keeps_one_and_says_so() -> None:
    """L-10: the scotogenic N gave mass_gev and per-generation masses_gev, and was refused. The builder's field keeps
    the per-generation masses; one value given twice is kept once; two that disagree leave none (not offered)."""
    n = ModelField(name="N", role=FieldRole.dark_matter, spin=0.5, self_conjugate=True, dark_parity=-1, generations=3,
                   mass_gev=500.0, masses_gev=[500.0, 800.0, 1200.0])
    (kept,), notes = um.canonical_fields([n])
    assert kept.mass_gev is None and kept.masses_gev == [500.0, 800.0, 1200.0]
    assert notes == ["N stated mass_gev = 500 GeV and per-generation masses (500, 800, 1200 GeV): the per-generation "
                     "masses are kept, 500 GeV being the lightest's"]
    one = n.model_copy(update={"generations": 1, "masses_gev": [500.0]})
    assert um.canonical_fields([one])[0][0].masses_gev is None and um.canonical_fields([one])[0][0].mass_gev == 500.0
    clash = one.model_copy(update={"masses_gev": [400.0]})
    (none,), said = um.canonical_fields([clash])
    assert none.mass_gev is None and none.masses_gev is None and said == [
        "N stated two masses, 500 and 400 GeV: neither is used"]


def test_per_generation_masses_count_as_given_and_the_scotogenic_model_reaches_its_own_reason() -> None:
    """The per-generation masses had been called missing. The scotogenic model now gets past its masses; it is still
    refused, for the generic route's Yukawa of SM fermions through a doublet (recorded, plan section 13)."""
    from adroit.library.personal import support
    n = ModelField(name="N", role=FieldRole.dark_matter, spin=0.5, self_conjugate=True, dark_parity=-1, generations=3,
                   mass_gev=500.0, masses_gev=[500.0, 800.0, 1200.0])
    eta = ModelField(name="eta", role=FieldRole.mediator, spin=0, dark_parity=-1, mass_gev=700.0,
                     charges=Charges(su2=2, hypercharge=0.5))
    spec = generated(n, eta)
    assert not [m for m in support(spec)["missing_parameters"] if m.startswith("mass of")]
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="Scotogenic", fields=[n, eta])]),
                          ValueProposals(models=[values(("y_L_N_eta_1", 0.1), ("lam_H_eta_2", 0.1),
                                                        ("lam_H_eta_2_c2", -0.1), ("lam_H_eta", 0.01),
                                                        ("lam_eta", 0.1))]), ValueProposals()])
    result = ideas.run(ideas.IdeaRequest(text="the scotogenic model"), fake)
    assert result.models == [] and "no value for the mass" not in result.dropped[0]
    assert "a stated Yukawa with SM fermions needs a gauge-singlet scalar" in result.dropped[0]


def test_a_repaired_model_keeps_what_the_first_values_reply_said_was_left_out() -> None:
    """The auditor's UO-08: the first values reply disclosed an omission and failed numerically; the repair succeeded on
    coefficients, and the omission was lost from the model. It is kept, and the repair round is told it."""
    first = ValueProposals(models=[values(("lam_S", 0.2), not_encoded=["the second dark matter species is absent"])])
    fake = scripted(first, ValueProposals(models=[values(("lam_H_S", 0.1))]))
    result = ideas.run(ideas.IdeaRequest(text="two-component scalar dark matter"), fake)
    assert result.dropped == [] and len(result.models) == 1
    assert "the second dark matter species is absent" in result.models[0].general.dropped
    assert "Already noted as left out: the second dark matter species is absent" in fake.calls[2]["messages"][0]["content"]


def test_different_omissions_are_never_merged() -> None:
    """The auditor's UO-09: notes sharing most words had merged ("Electron coupling omitted" with "Muon coupling omitted"),
    and numbers and negations were dropped. Only a note wholly within another, alike in negation, merges."""
    for pair in (["Electron coupling omitted", "Muon coupling omitted"],
                 ["Sommerfeld enhancement from scalar exchange", "Sommerfeld enhancement from vector exchange"],
                 ["Neutral mass splitting of 100 keV omitted", "Neutral mass splitting of 200 keV omitted"],
                 ["The splitting is computed", "The splitting is not computed"]):
        assert um.distinct(pair) == pair
        done, _ = um.finish(generated(SINGLET), {"lam_H_S": (0.1, "")}, pair)
        assert done.dropped == pair


def test_the_no_model_statement_never_claims_a_repair_round_that_was_not_made() -> None:
    """The auditor's UO-15: the report said "after the model builder's one repair round" where every proposal failed for its
    structure and no repair was asked. It says "including any repair round" now."""
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="m", fields=[SINGLET.model_copy(
        update={"mass_gev": None})])]), ValueProposals(models=[values(("lam_H_S", 0.1))])])
    result = ideas.run(ideas.IdeaRequest(text="a scalar singlet"), fake)
    report = ideas.report(result)
    assert fake.call_count == 2 and "including any repair round the model builder made" in report
    assert "one repair round" not in report

"""DM8: typed models and their deterministic checks."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adroit.core.model_spec import (Charges, FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm,
                                    Occurrence, Phase)
from adroit.library.interactions import model_checks

DM = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=100.0)


def standard_model_fermions(charge: dict[str, float], right_neutrino: bool) -> list[ModelField]:
    """One generation, left-handed convention fields with a new U(1) charge per multiplet."""
    def f(name, su3, su2, y, chirality):
        return ModelField(name=name, role=FieldRole.standard_model, spin=0.5, chirality=chirality,
                          generations=3, charges=Charges(su3=su3, su2=su2, hypercharge=y,
                                                         extra={"X": charge[name]}))
    out = [f("Q", "3", 2, 1 / 6, "L"), f("u", "3", 1, 2 / 3, "R"), f("d", "3", 1, -1 / 3, "R"),
           f("L", "1", 2, -1 / 2, "L"), f("e", "1", 1, -1, "R")]
    if right_neutrino:
        out.append(f("nu", "1", 1, 0.0, "R"))
    return out


def model(fields, terms=()) -> ModelSpec:
    return ModelSpec(name="test", phase=Phase.unbroken, fields=[DM, *fields], terms=list(terms))


def test_hypercharge_itself_is_anomaly_free() -> None:
    y = {"Q": 1 / 6, "u": 2 / 3, "d": -1 / 3, "L": -1 / 2, "e": -1.0}
    assert model_checks.anomaly_flags(model(standard_model_fermions(y, False))) == []


def test_b_minus_l_needs_right_handed_neutrinos() -> None:
    bl = {"Q": 1 / 3, "u": 1 / 3, "d": 1 / 3, "L": -1.0, "e": -1.0, "nu": -1.0}
    flags = model_checks.anomaly_flags(model(standard_model_fermions(bl, False)))
    assert any("[X]³" in f for f in flags) and any("gravity" in f for f in flags)
    assert model_checks.anomaly_flags(model(standard_model_fermions(bl, True))) == []


def test_baryon_number_is_anomalous_with_su2() -> None:
    b = {"Q": 1 / 3, "u": 1 / 3, "d": 1 / 3, "L": 0.0, "e": 0.0}
    flags = model_checks.anomaly_flags(model(standard_model_fermions(b, False)))
    assert any("[SU(2)]²X" in f for f in flags)


def test_a_yukawa_coupling_is_invariant_and_hermitian() -> None:
    phi = ModelField(name="phi", role=FieldRole.mediator, spin=0.0, self_conjugate=True)
    term = ModelTerm(fields=[Occurrence(field="chi", conjugate=True), Occurrence(field="chi"),
                             Occurrence(field="phi")], lorentz="scalar", coupling="g_chi")
    report = model_checks.check(ModelSpec(name="S", fields=[DM, phi], terms=[term],
                                          couplings=[ModelCoupling(name="g_chi", value=1.0)]))
    assert report.passed and report.anomalies == []


def test_a_t_channel_coupling_needs_its_conjugate_and_colour() -> None:
    """φ* χ̄ u_R: a coloured, charged mediator; it needs + h.c., and its charges must balance."""
    phi = ModelField(name="phi", role=FieldRole.mediator, spin=0.0,
                     charges=Charges(su3="3", electric_charge=2 / 3))
    up = ModelField(name="u", role=FieldRole.standard_model, spin=0.5, chirality="R",
                    charges=Charges(su3="3", electric_charge=2 / 3))
    term = ModelTerm(fields=[Occurrence(field="phi", conjugate=True), Occurrence(field="chi", conjugate=True),
                             Occurrence(field="u")], lorentz="chiral", coupling="lam")
    report = model_checks.check(ModelSpec(name="t", fields=[DM, phi, up], terms=[term]))
    assert report.gauge == [] and report.hermiticity
    fixed = term.model_copy(update={"plus_hc": True})
    assert model_checks.check(ModelSpec(name="t", fields=[DM, phi, up], terms=[fixed])).passed
    lone = term.model_copy(update={"fields": [Occurrence(field="chi", conjugate=True), Occurrence(field="u")],
                                   "plus_hc": True})
    assert any("colour" in p for p in model_checks.gauge_problems(ModelSpec(name="t", fields=[DM, phi, up],
                                                                            terms=[lone])))


def test_a_self_conjugate_field_carries_no_charge() -> None:
    bad = ModelField(name="s", role=FieldRole.mediator, spin=0.0, self_conjugate=True,
                     charges=Charges(electric_charge=1.0))
    assert model_checks.gauge_problems(ModelSpec(name="x", fields=[DM, bad]))


def test_an_axial_coupling_to_quarks_is_flagged() -> None:
    zp = ModelField(name="Zp", role=FieldRole.mediator, spin=1.0, self_conjugate=True)
    q = ModelField(name="q", role=FieldRole.standard_model, spin=0.5)
    term = ModelTerm(fields=[Occurrence(field="q", conjugate=True), Occurrence(field="q"),
                             Occurrence(field="Zp")], lorentz="axial", coupling="g_q")
    flags = model_checks.anomaly_flags(ModelSpec(name="A", fields=[DM, zp, q], terms=[term]))
    assert flags and "axial" in flags[0]


def test_a_model_must_name_its_fields_and_its_dark_matter() -> None:
    with pytest.raises(ValidationError):
        ModelSpec(name="x", fields=[ModelField(name="a", role=FieldRole.mediator, spin=0.0)])
    with pytest.raises(ValidationError):
        ModelSpec(name="x", fields=[DM], terms=[ModelTerm(fields=[Occurrence(field="chi"),
                                                                  Occurrence(field="ghost")],
                                                          lorentz="scalar", coupling="g")])


# --- the freeze-out flags (2026-10-01) ---------------------------------------------------

def z_prime(m_dm: float = 100.0, m_med: float = 2000.0, lorentz: str = "vector", g_chi: float = 1.0,
            majorana: bool = False, parities: tuple[int | None, int | None] = (-1, 1),
            g_q: float = 0.25) -> ModelSpec:
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=m_dm, self_conjugate=majorana,
                     dark_parity=parities[0])
    zp = ModelField(name="Zp", role=FieldRole.mediator, spin=1.0, self_conjugate=True, mass_gev=m_med,
                    dark_parity=parities[1])
    q = ModelField(name="q", role=FieldRole.standard_model, spin=0.5)
    terms = [ModelTerm(fields=[Occurrence(field="chi", conjugate=True), Occurrence(field="chi"),
                               Occurrence(field="Zp")], lorentz=lorentz, coupling="g_chi"),
             ModelTerm(fields=[Occurrence(field="q", conjugate=True), Occurrence(field="q"),
                               Occurrence(field="Zp")], lorentz=lorentz, coupling="g_q")]
    return ModelSpec(name="zp", fields=[chi, zp, q], terms=terms, stability="Z2" if parities[0] else "",
                     couplings=[ModelCoupling(name="g_chi", value=g_chi), ModelCoupling(name="g_q", value=g_q)])


def test_stability_under_the_stated_parity() -> None:
    assert model_checks.stability_flags(z_prime()) == []
    assert "no stabilising symmetry stated" in model_checks.stability_flags(z_prime(parities=(None, None)))[0]
    odd_mediator = model_checks.stability_flags(z_prime(parities=(-1, -1)))
    assert sum("not a symmetry of the model" in f for f in odd_mediator) == 2    # χ̄χZp and q̄qZp are both odd
    lighter = model_checks.stability_flags(z_prime(m_med=50.0, parities=(-1, -1)))
    assert any("odd and lighter than the dark matter" in f for f in lighter)


def test_perturbativity_flags_large_couplings() -> None:
    assert model_checks.perturbativity_flags(z_prime(g_chi=3.0)) == []
    assert "exceeds √(4π)" in model_checks.perturbativity_flags(z_prime(g_chi=4.0))[0]


def test_the_contact_interaction_at_direct_detection_and_freeze_out() -> None:
    assert model_checks.contact_flags(z_prime()) == []
    light = model_checks.contact_flags(z_prime(m_med=1.0))
    assert any("needs its propagator" in f for f in light) and any("freeze-out" in f for f in light)
    assert any("freeze-out" in f for f in model_checks.contact_flags(z_prime(m_med=300.0)))
    t_channel = z_prime(m_med=250.0, parities=(-1, -1))
    assert model_checks.contact_flags(t_channel) == []


def test_unitarity_of_axial_couplings() -> None:
    """m_f ≲ √(π/2) M/g_A (arXiv:1510.02110, eq. 2.8): √(π/2) × 200 GeV = 250.7 GeV at g_A = 1."""
    assert model_checks.unitarity_flags(z_prime(m_dm=200.0, m_med=200.0, lorentz="axial"))[0] == []
    heavy, notes = model_checks.unitarity_flags(z_prime(m_dm=300.0, m_med=200.0, lorentz="axial"))
    assert heavy and "m_chi = 300" in heavy[0] and "needs completing" in notes[0]
    majorana, _ = model_checks.unitarity_flags(z_prime(m_dm=200.0, m_med=200.0, lorentz="axial", majorana=True))
    assert majorana, "a Majorana field's Feynman-rule coupling is twice its Lagrangian coupling"
    top, _ = model_checks.unitarity_flags(z_prime(m_dm=10.0, m_med=200.0, lorentz="axial", g_q=2.0))
    assert any("m_q = 172.5" in f for f in top)
    assert model_checks.unitarity_flags(z_prime(m_dm=300.0, m_med=200.0))[0] == []   # vector: no bound


def test_the_new_flags_never_stop_a_run() -> None:
    report = model_checks.check(z_prime(m_dm=300.0, m_med=200.0, lorentz="axial", g_chi=4.0, parities=(1, 1)))
    assert report.passed and report.unitarity and report.perturbativity and report.stability


def test_a_coupling_must_be_an_expression_in_known_symbols() -> None:
    """A term's coupling is its full coefficient; m_q stands for each quark's own mass."""
    good = z_prime()
    assert model_checks.coefficient_flags(good) == []
    yukawa = good.model_copy(update={"terms": [good.terms[0], good.terms[1].model_copy(update={"coupling": "g_q*m_q/v"})]})
    assert model_checks.coefficient_flags(yukawa) == []
    unknown = good.model_copy(update={"terms": [good.terms[0], good.terms[1].model_copy(update={"coupling": "y_q"})]})
    assert "does not evaluate" in model_checks.coefficient_flags(unknown)[0]


def test_a_neutral_field_couples_to_the_photon_only_through_its_field_strength() -> None:
    a = ModelField(name="A", role=FieldRole.standard_model, spin=1.0, self_conjugate=True)
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=100.0)

    def anapole(lorentz: str) -> ModelSpec:
        return ModelSpec(name="a", phase=Phase.broken, fields=[chi, a], couplings=[ModelCoupling(name="k", value=1e-5)],
                         terms=[ModelTerm(fields=[Occurrence(field="chi", conjugate=True), Occurrence(field="chi"),
                                                  Occurrence(field="A")], lorentz=lorentz, coupling="k")])
    assert any("only to charged fields" in p for p in model_checks.gauge_problems(anapole("axial")))
    assert model_checks.gauge_problems(anapole("other")) == []


def test_a_chiral_yukawa_without_its_conjugate_is_not_hermitian() -> None:
    """The audit loop's AL4-13(a): y S χ̄P_Rχ without + h.c. had passed (its fields are their own conjugate set), then
    been dropped by the gauge basis. (χ̄P_Rχ)† = χ̄P_Lχ: a chiral bilinear needs + h.c. whatever its fields."""
    phi = ModelField(name="phi", role=FieldRole.mediator, spin=0.0, self_conjugate=True)
    legs = [Occurrence(field="chi", conjugate=True), Occurrence(field="chi"), Occurrence(field="phi")]
    alone = ModelSpec(name="S", fields=[DM, phi], terms=[ModelTerm(fields=legs, lorentz="chiral", coupling="y")],
                      couplings=[ModelCoupling(name="y", value=1.0)])
    problems, _ = model_checks.hermiticity_problems(alone)
    assert problems and "not hermitian as written; add + h.c." in problems[0]
    paired = alone.model_copy(update={"terms": [ModelTerm(fields=legs, lorentz="chiral", coupling="y", plus_hc=True)]})
    problems, notes = model_checks.hermiticity_problems(paired)
    assert problems == [] and notes == []                            # + h.c. is not a doubling here

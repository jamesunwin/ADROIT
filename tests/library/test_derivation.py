"""DM8: derivations as formulas, evaluated and checked deterministically."""

from __future__ import annotations

import pytest

from adroit.core.model_spec import FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm, Occurrence
from adroit.library.interactions import derivation as dv
from adroit.library.interactions import matching
from adroit.library.interactions import quark_level as ql

QUARKS = "udscb"


def z_prime_model() -> ModelSpec:
    """Dirac dark matter and a vector Z′ coupling to every quark (the Working Group's V1)."""
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=100.0)
    zp = ModelField(name="Zp", role=FieldRole.mediator, spin=1.0, self_conjugate=True, mass_gev=2000.0,
                    mass_justification="the benchmark of arXiv:1703.05703")
    q = ModelField(name="q", role=FieldRole.standard_model, spin=0.5)
    terms = [ModelTerm(fields=[Occurrence(field="chi", conjugate=True), Occurrence(field="chi"),
                               Occurrence(field="Zp")], lorentz="vector", coupling="g_chi"),
             ModelTerm(fields=[Occurrence(field="q", conjugate=True), Occurrence(field="q"),
                               Occurrence(field="Zp")], lorentz="vector", coupling="g_q")]
    return ModelSpec(name="V1", fields=[chi, zp, q], terms=terms,
                     couplings=[ModelCoupling(name="g_chi", value=1.0), ModelCoupling(name="g_q", value=0.25)])


def vector_derivation(expression: str = "-g_chi*g_q/m_Zp**2") -> dv.Derivation:
    return dv.Derivation(model_name="V1", terms=[dv.WilsonTerm(name=f"C61{q}", expression=expression)
                                                 for q in QUARKS], derived_by="user")


def test_formulas_are_evaluated_from_the_model() -> None:
    quark_model = dv.evaluate(vector_derivation(), z_prime_model())
    assert quark_model.coefficients["C61u"] == pytest.approx(-0.25 / 2000.0 ** 2)
    assert quark_model.flavours == 5 and set(quark_model.coefficients) == {f"C61{q}" for q in QUARKS}


def test_the_dimension_check() -> None:
    assert dv.dimension_problems(vector_derivation(), z_prime_model()) == []
    wrong = dv.dimension_problems(vector_derivation("-g_chi*g_q/m_Zp"), z_prime_model())
    assert wrong and "needs mass^-2" in wrong[0]


@pytest.mark.parametrize("bad", ["__import__('os').system('true')", "open('x')", "g_q.__class__",
                                 "lam*g_q", "g_q; import os", "[g_q]"])
def test_untrusted_text_never_reaches_eval(bad) -> None:
    with pytest.raises(ValueError):
        dv.evaluate_expression(bad, dv.symbol_table(z_prime_model()))


def test_functions_and_standard_model_constants() -> None:
    table = dv.symbol_table(z_prime_model())
    assert dv.evaluate_expression("sqrt(4*pi*alpha)", table) == pytest.approx(table["e"][0])
    assert dv.evaluate_expression("1/v**2", table) == pytest.approx(1 / 246.22 ** 2)


def test_two_derivations_compared() -> None:
    model = z_prime_model()
    same = dv.compare(vector_derivation(), vector_derivation("-(g_q*g_chi)/(m_Zp*m_Zp)"), model)
    assert same.agree and same.max_relative_difference < 1e-12
    double = dv.compare(vector_derivation(), vector_derivation("-2*g_chi*g_q/m_Zp**2"), model)
    assert not double.agree and double.max_relative_difference == pytest.approx(0.5)
    short = dv.Derivation(model_name="V1", terms=vector_derivation().terms[:2])
    assert dv.compare(vector_derivation(), short, model).only_in_first


@pytest.mark.skipif(not ql.available(), reason="DirectDM is not set up")
def test_a_derivation_reaches_the_library() -> None:
    """V1 through DirectDM is the library's vector mediator, to the reductions' sub-percent difference."""
    particle, interaction = ql.to_interaction(dv.evaluate(vector_derivation(), z_prime_model()), 100.0)
    fit = matching.fit_card("M_vector", particle, interaction)
    assert fit.verdict in ("same", "close")


def test_one_overall_sign_is_not_a_disagreement() -> None:
    """Every rate is quadratic in the coefficients, so reversing all of them changes nothing."""
    reversed_ = dv.compare(vector_derivation(), vector_derivation("g_chi*g_q/m_Zp**2"), z_prime_model())
    assert reversed_.agree and reversed_.sign == -1
    mixed = dv.Derivation(model_name="V1", terms=[dv.WilsonTerm(name="C61u", expression="g_chi*g_q/m_Zp**2"),
                                                  *vector_derivation().terms[1:]])
    assert not dv.compare(vector_derivation(), mixed, z_prime_model()).agree


@pytest.mark.skipif(not ql.available(), reason="DirectDM is not set up")
def test_agreement_is_decided_at_the_nucleon_level() -> None:
    """A coefficient too small to reach a recoil does not stop a run; a factor of two does."""
    model = z_prime_model()
    extra = vector_derivation().model_copy(update={"terms": [
        *vector_derivation().terms, dv.WilsonTerm(name="C61e", expression="-1e-3*g_chi*g_q/m_Zp**2")]})
    small = dv.compare(vector_derivation(), extra, model, points=2, nucleon=True)
    assert small.only_in_second == ["C61e"] and not small.agree_coefficients
    assert small.agree and small.nucleon_difference < 1e-3
    double = dv.compare(vector_derivation(), vector_derivation("-2*g_chi*g_q/m_Zp**2"), model, points=2,
                        nucleon=True)
    assert not double.agree and double.nucleon_difference == pytest.approx(0.5, rel=0.01)

"""DM8: Path 1 for a bespoke model, end to end."""

from __future__ import annotations

import pytest

from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import (Charges, FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm,
                                    Occurrence)
from adroit.library.interactions import derivation as dv
from adroit.library.interactions import quark_level as ql
from adroit.orchestrator import lagrangian

needs_directdm = pytest.mark.skipif(not ql.available(), reason="DirectDM is not set up")


def spec() -> ModelSpec:
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=100.0,
                     mass_justification="the benchmark point")
    zp = ModelField(name="Zp", role=FieldRole.mediator, spin=1.0, self_conjugate=True, mass_gev=2000.0,
                    mass_justification="above the dijet reach of the benchmark")
    q = ModelField(name="q", role=FieldRole.standard_model, spin=0.5)
    terms = [ModelTerm(fields=[Occurrence(field="chi", conjugate=True), Occurrence(field="chi"),
                               Occurrence(field="Zp")], lorentz="vector", coupling="g_chi"),
             ModelTerm(fields=[Occurrence(field="q", conjugate=True), Occurrence(field="q"),
                               Occurrence(field="Zp")], lorentz="vector", coupling="g_q")]
    return ModelSpec(name="V1", fields=[chi, zp, q], terms=terms, dropped=["lepton couplings"],
                     couplings=[ModelCoupling(name="g_chi", value=1.0, justification="the benchmark"),
                                ModelCoupling(name="g_q", value=0.25, justification="the benchmark")])


def derivation(factor: str = "") -> dv.Derivation:
    return dv.Derivation(model_name="V1", derived_by="user",
                         terms=[dv.WilsonTerm(name=f"C61{q}", expression=f"-{factor}g_chi*g_q/m_Zp**2")
                                for q in "udscb"])


@needs_directdm
def test_a_bespoke_model_reaches_its_limits() -> None:
    request = lagrangian.LagrangianRequest(spec=spec(), derivation=derivation(), masses_gev=[100.0, 300.0],
                                           modules=["DEAP-3600 (2019)"])
    result = lagrangian.run(request)
    assert result.status == "complete" and set(result.interactions) == {"100", "300"}
    assert result.matches[0].verdict in ("same", "close") and len(result.matches) >= 3
    assert result.exclusion.per_module[0].experiment == "DEAP-3600 (2019)"
    assert result.contract.masses["Zp"].startswith("2000 GeV: above the dijet reach")
    assert "lepton couplings" in result.contract.dropped
    text = lagrangian.report(result)
    assert "## The contract" in text and "C61u" in text and "DEAP-3600" in text


def test_without_a_model_or_permission_it_refuses() -> None:
    with pytest.raises(ValueError, match="typed model"):
        lagrangian.run(lagrangian.LagrangianRequest(description="some model"))
    with pytest.raises(ValueError, match="Wilson coefficients"):
        lagrangian.run(lagrangian.LagrangianRequest(spec=spec()))


def test_a_model_that_fails_its_checks_stops() -> None:
    broken = spec()
    charged = broken.fields[1].model_copy(update={"charges": Charges(electric_charge=1.0)})
    broken = broken.model_copy(update={"fields": [broken.fields[0], charged, broken.fields[2]]})
    result = lagrangian.run(lagrangian.LagrangianRequest(spec=broken, derivation=derivation()))
    assert result.status.startswith("stopped") and result.checks.gauge


def test_a_derivation_with_the_wrong_dimension_stops() -> None:
    wrong = dv.Derivation(model_name="V1", terms=[dv.WilsonTerm(name="C61u", expression="g_chi*g_q/m_Zp")])
    result = lagrangian.run(lagrangian.LagrangianRequest(spec=spec(), derivation=wrong))
    assert "dimension" in result.status


@needs_directdm
@pytest.mark.parametrize("checker_factor,agree", [("", True), ("2*", False)])
def test_two_language_models_must_agree(checker_factor, agree) -> None:
    primary = FakeLLMClient([spec(), derivation()])
    checker = FakeLLMClient([derivation(checker_factor)])
    request = lagrangian.LagrangianRequest(description="a Z′ model", use_language_models=True,
                                           run_exclusion=False)
    result = lagrangian.run(request, primary=primary, checker=checker)
    assert result.comparison.agree is agree
    assert (result.status == "complete") is agree
    assert result.second.derived_by == lagrangian.DEFAULT_CHECKER


@needs_directdm
def test_a_coefficient_directdm_does_not_know_stops() -> None:
    top = dv.Derivation(model_name="V1", terms=[dv.WilsonTerm(name="C61t", expression="-g_chi*g_q/m_Zp**2")])
    result = lagrangian.run(lagrangian.LagrangianRequest(spec=spec(), derivation=top, run_exclusion=False))
    assert result.status.startswith("stopped for a person: DirectDM refused")


def test_a_formula_with_an_unknown_symbol_stops() -> None:
    bad = dv.Derivation(model_name="V1", terms=[dv.WilsonTerm(name="C61u", expression="-g_x*g_q/m_Zp**2")])
    result = lagrangian.run(lagrangian.LagrangianRequest(spec=spec(), derivation=bad))
    assert "dimension" in result.status and "unknown symbol" in result.dimension_problems[0]


@needs_directdm
def test_every_report_carries_the_viability_checklist() -> None:
    result = lagrangian.run(lagrangian.LagrangianRequest(spec=spec(), derivation=derivation(),
                                                         run_exclusion=False))
    assert len(result.viability) == 28
    assert "## Viability checklist (thermal freeze-out)" in lagrangian.report(result)
    stopped = lagrangian.run(lagrangian.LagrangianRequest(spec=spec(), derivation=dv.Derivation(
        model_name="V1", terms=[dv.WilsonTerm(name="C61u", expression="g_chi")])))
    assert stopped.status.startswith("stopped") and len(stopped.viability) == 28



@needs_directdm
@pytest.mark.parametrize("difference,stops", [(0.003, False), (0.2, True)])
def test_the_numerical_cross_check_can_stop_a_run(monkeypatch, difference, stops) -> None:
    from adroit.constraints import maddm
    found = maddm.AlphaComparison(covered=True, max_relative_difference=difference)
    monkeypatch.setattr(lagrangian, "_numerical", lambda spec, derivation: found)
    result = lagrangian.run(lagrangian.LagrangianRequest(spec=spec(), derivation=derivation(), run_exclusion=False,
                                                         numerical_check=True))
    assert result.numerical == found and result.status.startswith("stopped") is stops
    assert "Numerical cross-check" in lagrangian.report(result)


def test_an_uncovered_model_does_not_stop(monkeypatch) -> None:
    from adroit.constraints import maddm
    monkeypatch.setattr(maddm, "available", lambda: False)
    assert not lagrangian._numerical(spec(), derivation()).covered

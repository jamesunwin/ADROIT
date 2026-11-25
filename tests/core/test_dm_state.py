"""Typed state for dark matter direct detection."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from adroit.core.dm_state import (
    Applicability,
    ConstraintClass,
    ConstraintRecord,
    ConstraintVerdict,
    DarkMatterParticle,
    DataKind,
    DataSet,
    ExperimentInfo,
    Fidelity,
    HaloKind,
    HaloModel,
    InteractionModel,
    Isotope,
    LikelihoodResult,
    ModelLayer,
    ModulationSpectrum,
    OperatorCoefficient,
    RecoilSpectrum,
    Target,
)


def test_a_particle_names_its_kinematics() -> None:
    assert DarkMatterParticle(mass_gev=100.0).kinematics == "elastic"
    assert DarkMatterParticle(mass_gev=100.0, mass_splitting_kev=150.0).kinematics == "inelastic"
    assert DarkMatterParticle(mass_gev=100.0, mass_splitting_kev=-5.0).kinematics == "exothermic"
    for bad in ({"mass_gev": 0.0}, {"mass_gev": 10.0, "spin": 0.3},
                {"mass_gev": 10.0, "spin": -1.0}):
        with pytest.raises(ValidationError):
            DarkMatterParticle(**bad)


def test_the_default_halo_is_the_standard_halo_model() -> None:
    halo = HaloModel()
    assert halo.is_default and halo.kind is HaloKind.standard
    assert (halo.rho_gev_cm3, halo.v0_km_s, halo.v_esc_km_s) == (0.3, 238.0, 544.0)
    # |(0, 238, 0) + (11.1, 12.2, 7.3) + (29.2, -0.1, 5.9)|
    assert halo.v_lab_km_s == pytest.approx(253.7, abs=0.1)
    assert not HaloModel(v_esc_km_s=600.0).is_default


def test_any_speed_distribution_can_replace_the_default() -> None:
    stream = HaloModel(kind=HaloKind.tabulated, label="a stream",
                       speeds_km_s=[0.0, 300.0, 600.0], speed_density=[0.0, 0.0033, 0.0])
    assert not stream.is_default
    for bad in ({"speeds_km_s": [0.0, 1.0], "speed_density": [1.0]},
                {"speeds_km_s": [1.0, 0.0], "speed_density": [1.0, 1.0]},
                {"speeds_km_s": [0.0, 1.0], "speed_density": [1.0, -1.0]}, {}):
        with pytest.raises(ValidationError):
            HaloModel(kind=HaloKind.tabulated, **bad)


def test_a_target_is_a_set_of_isotopes_that_sum_to_one() -> None:
    xe = [Isotope(element="Xe", mass_number=a, atomic_number=54, spin=j, mass_fraction=f)
          for a, j, f in ((129, 0.5, 0.5), (132, 0.0, 0.5))]
    assert Target(name="xenon", isotopes=xe).isotopes[0].name == "Xe129"
    with pytest.raises(ValidationError, match="sum to"):
        Target(name="xenon", isotopes=xe[:1])


def test_an_interaction_holds_its_nonrelativistic_coefficients() -> None:
    c = OperatorCoefficient(operator=1, proton=3.0, neutron=1.0)
    assert (c.isoscalar, c.isovector) == (2.0, 1.0)
    model = InteractionModel(name="spin-independent", layer=ModelLayer.nonrelativistic,
                             coefficients=[c])
    assert InteractionModel.from_json(model.to_json()) == model
    with pytest.raises(ValidationError, match="twice"):
        InteractionModel(name="x", layer=ModelLayer.nonrelativistic, coefficients=[c, c])
    with pytest.raises(ValidationError):
        OperatorCoefficient(operator=0)


def test_a_spectrum_records_its_halo_and_nuclear_input() -> None:
    particle = DarkMatterParticle(mass_gev=1000.0)
    spectrum = RecoilSpectrum(target="xenon", energies_kev=[1.0, 2.0], rate=[1e-5, 5e-6],
                              particle=particle, nuclear_input="shell model, arXiv:1308.6288")
    assert spectrum.halo.is_default and spectrum.nuclear_input
    assert RecoilSpectrum.from_json(spectrum.to_json()) == spectrum
    for bad in ([1e-5], [1e-5, -1.0], [1e-5, float("nan")]):
        with pytest.raises(ValidationError):
            RecoilSpectrum(target="xenon", energies_kev=[1.0, 2.0], rate=bad, particle=particle)


def test_a_modulation_spectrum_keeps_its_columns_aligned() -> None:
    particle = DarkMatterParticle(mass_gev=100.0)
    spectrum = ModulationSpectrum(target="Xe", energies_kev=[5.0, 60.0], mean_rate=[2.0, 0.1],
                                  amplitude=[0.05, 0.004], peak_day=[335.5, 152.9],
                                  particle=particle)
    assert ModulationSpectrum.from_json(spectrum.to_json()) == spectrum
    with pytest.raises(ValidationError, match="must match"):
        ModulationSpectrum(target="Xe", energies_kev=[5.0], mean_rate=[2.0, 0.1],
                           amplitude=[0.05], peak_day=[335.5], particle=particle)
    with pytest.raises(ValidationError, match="reversal"):
        ModulationSpectrum(target="Xe", energies_kev=[5.0], mean_rate=[2.0],
                           amplitude=[-0.05], peak_day=[152.9], particle=particle)


def test_only_a_validated_module_above_level_c_enters_likelihoods() -> None:
    def info(**kwargs) -> ExperimentInfo:
        return ExperimentInfo(name="a search", target="xenon", exposure_kg_day=1.0e6,
                              energy_window_kev=(5.4, 270.0), **kwargs)
    assert info(fidelity=Fidelity.A, validated=True).enters_likelihoods
    assert not info(fidelity=Fidelity.A).enters_likelihoods
    assert not info(fidelity=Fidelity.C, validated=True).enters_likelihoods
    with pytest.raises(ValidationError, match="energy window"):
        ExperimentInfo(name="x", target="xenon", exposure_kg_day=1.0,
                       energy_window_kev=(10.0, 5.0), fidelity=Fidelity.B)
    data = DataSet(experiment="a search", kind=DataKind.events, path="events.csv",
                   source="10.17182/hepdata.182472", licence="CC0")
    assert info(fidelity=Fidelity.A, data=[data]).data[0].kind is DataKind.events


def test_a_likelihood_result_round_trips() -> None:
    result = LikelihoodResult(experiment="a search", interaction_id="m",
                              particle=DarkMatterParticle(mass_gev=1000.0),
                              expected_signal=1.0, local_significance=3.4,
                              upper_limit=0.52, lower_limit=0.13, limit_on="coupling")
    assert LikelihoodResult.from_json(result.to_json()) == result
    assert result.confidence_level == 0.9


def test_constraints_have_tiers_and_need_verification() -> None:
    record = ConstraintRecord(name="a monojet search", constraint_class=ConstraintClass.collider,
                              source="arXiv:0000.00000")
    assert record.tier == 3 and not record.usable
    named = record.model_copy(update={"verified_on": date(2026, 9, 29), "verified_by": "JU"})
    assert not named.usable                  # a name and date bound to nothing (the audit loop's AL1-08, 2026-11-14)
    from adroit.constraints.review_identity import fingerprint
    verified = named.model_copy(update={"verification_sha256": fingerprint(record)})
    assert verified.usable
    assert ConstraintRecord(name="x", constraint_class=ConstraintClass.direct_detection,
                            source="s").tier == 1
    assert ConstraintRecord(name="x", constraint_class=ConstraintClass.solar_capture,
                            source="s").tier == 2


def test_a_verdict_states_what_cannot_be_concluded() -> None:
    needs = ConstraintVerdict(constraint_id="c", interaction_id="m",
                              applicability=Applicability.needs_calculation,
                              needed_calculation="the mediator's width and lifetime")
    assert needs.excluded is None
    with pytest.raises(ValidationError, match="no verdict yet"):
        ConstraintVerdict(constraint_id="c", interaction_id="m", excluded=True,
                          applicability=Applicability.needs_calculation,
                          needed_calculation="x")
    with pytest.raises(ValidationError, match="name the calculation"):
        ConstraintVerdict(constraint_id="c", interaction_id="m",
                          applicability=Applicability.needs_calculation)
    with pytest.raises(ValidationError, match="assumptions"):
        ConstraintVerdict(constraint_id="c", interaction_id="m", excluded=False,
                          applicability=Applicability.applies_with_assumptions)
    assert ConstraintVerdict(constraint_id="c", interaction_id="m", excluded=True,
                             applicability=Applicability.applies).excluded

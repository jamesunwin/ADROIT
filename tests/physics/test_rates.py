"""Differential recoil rates."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from adroit.core.dm_state import (DarkMatterParticle, HaloModel, InteractionModel, ModelLayer,
                                      OperatorCoefficient)
from adroit.physics import conventions as cv
from adroit.physics import halo as halos
from adroit.physics import nuclear, rates, targets
from adroit.physics.nuclear import NuclearModel

FIXTURE = Path(__file__).parent / "fixtures/reference_spectra.json"
C = cv.coupling_gev2(1.0)


def _interaction(**coefficients: tuple[float, float]) -> InteractionModel:
    """An interaction from keyword arguments such as o1=(c_p, c_n)."""
    return InteractionModel(name="test", layer=ModelLayer.nonrelativistic,
                            coefficients=[OperatorCoefficient(operator=int(k[1:]), proton=p,
                                                              neutron=n)
                                          for k, (p, n) in coefficients.items()])


def _eta(energies: np.ndarray, mass_number: int, dm_mass: float) -> np.ndarray:
    m_t = cv.nuclear_mass_gev(mass_number)
    v_min = np.array([cv.v_min_km_s(e, m_t, dm_mass) for e in energies])
    return halos.velocity_integrals(v_min, HaloModel())[0]


def test_the_rate_unit_matches_an_independent_derivation() -> None:
    # WIMpy_NREFT's conversion of GeV⁻⁴ cm⁻³ s/km to events/(keV kg day) is 1.69612985e14.
    assert rates.RATE_UNIT * cv.C_KM_S == pytest.approx(1.69612985e14, rel=1e-7)
    assert cv.OPERATOR_MASS_GEV == cv.AMU_GEV


def test_the_spin_independent_rate_is_the_textbook_formula() -> None:
    # dR/dE = ρ c² A² F²(q) η / (2π m_χ): with σ_n = c² μ_n²/π, the usual ρ σ_n A² F² η/(2 μ_n² m_χ).
    energies = np.array([1.0, 10.0, 40.0, 120.0])
    spectrum = rates.differential_rate(energies, DarkMatterParticle(mass_gev=100.0),
                                       _interaction(o1=(C, C)), targets.single_isotope("Xe132"),
                                       model=NuclearModel.helm)
    q = np.sqrt(2 * cv.nuclear_mass_gev(132) * energies * cv.KEV)
    expected = (0.3 / 100.0 * C ** 2 * 132 ** 2 * nuclear.helm_form_factor(q, 132) ** 2
                * _eta(energies, 132, 100.0) * cv.C_KM_S / (2 * math.pi) * rates.RATE_UNIT)
    assert spectrum.rate == pytest.approx(expected, rel=1e-12)


def test_the_spin_dependent_rate_is_the_textbook_formula() -> None:
    # With the approximate responses, O4 gives ρ j(j+1)(J+1)/(6πJ) (c_p⟨S_p⟩ + c_n⟨S_n⟩)² G(q) η / m_χ.
    energies = np.array([1.0, 10.0, 40.0])
    isotope = targets.single_isotope("O17")
    spectrum = rates.differential_rate(energies, DarkMatterParticle(mass_gev=50.0),
                                       _interaction(o4=(C, 0.5 * C)), isotope)
    q = np.sqrt(2 * cv.nuclear_mass_gev(17) * energies * cv.KEV)
    radius = nuclear._spin_radius_fm(17)
    g = np.exp(-0.25 * (q * radius / cv.HBARC_GEV_FM) ** 2)
    j, big_j, s_n = 0.5, 2.5, 0.5
    expected = (0.3 / 50.0 * j * (j + 1) * (big_j + 1) / (6 * math.pi * big_j)
                * (0.5 * C * s_n) ** 2 * g * _eta(energies, 17, 50.0) * cv.C_KM_S * rates.RATE_UNIT)
    assert spectrum.rate == pytest.approx(expected, rel=1e-12)


def test_the_rate_is_quadratic_in_the_couplings_and_linear_in_the_density() -> None:
    e, p, xe = [5.0, 30.0], DarkMatterParticle(mass_gev=200.0), targets.target("Xe")
    base = np.array(rates.differential_rate(e, p, _interaction(o1=(C, C)), xe).rate)
    double = np.array(rates.differential_rate(e, p, _interaction(o1=(2 * C, 2 * C)), xe).rate)
    dense = np.array(rates.differential_rate(e, p, _interaction(o1=(C, C)), xe,
                                             halo=HaloModel(rho_gev_cm3=0.6)).rate)
    assert double == pytest.approx(4 * base) and dense == pytest.approx(2 * base)


def test_spin_zero_dark_matter_feels_no_spin_dependent_operator() -> None:
    spectrum = rates.differential_rate([10.0], DarkMatterParticle(mass_gev=100.0, spin=0.0),
                                       _interaction(o4=(C, C)), targets.target("Xe"))
    assert spectrum.rate == [0.0]


def test_inelastic_scattering_stays_between_its_kinematic_endpoints() -> None:
    particle = DarkMatterParticle(mass_gev=1000.0, mass_splitting_kev=100.0)
    xe131 = targets.single_isotope("Xe131")
    low, high = rates.recoil_range_kev(particle, xe131.isotopes[0])
    assert 0.0 < low < high
    inside = np.linspace(low, high, 12)[1:-1]
    outside = [0.98 * low, 1.02 * high]
    interaction = _interaction(o1=(C, C))
    assert all(r > 0 for r in rates.differential_rate(inside, particle, interaction, xe131).rate)
    assert rates.differential_rate(outside, particle, interaction, xe131).rate == [0.0, 0.0]


def test_the_kinematic_range_of_each_kind_of_scattering() -> None:
    xe = targets.single_isotope("Xe131").isotopes[0]
    elastic = rates.recoil_range_kev(DarkMatterParticle(mass_gev=100.0), xe)
    assert elastic[0] == 0.0 and elastic[1] > 0.0
    exothermic = rates.recoil_range_kev(DarkMatterParticle(mass_gev=100.0,
                                                           mass_splitting_kev=-50.0), xe)
    assert exothermic[0] > 0.0
    # too little kinetic energy to excite the state
    assert rates.recoil_range_kev(DarkMatterParticle(mass_gev=10.0, mass_splitting_kev=300.0),
                                  xe) is None


def test_uncovered_operators_are_rejected() -> None:
    for operator in (2, 16):
        with pytest.raises(ValueError, match="not covered"):
            rates.isospin_coefficients(InteractionModel(
                name="x", layer=ModelLayer.nonrelativistic,
                coefficients=[OperatorCoefficient(operator=operator, proton=1.0)]))
    with pytest.raises(ValueError, match="positive"):
        rates.differential_rate([0.0], DarkMatterParticle(mass_gev=10.0), _interaction(o1=(C, C)),
                                targets.target("Ar"))


def test_the_spectrum_records_what_it_assumed() -> None:
    interaction = _interaction(o1=(C, C))
    spectrum = rates.differential_rate([10.0], DarkMatterParticle(mass_gev=100.0), interaction,
                                       targets.target("Xe"))
    assert spectrum.interaction_id == interaction.id and spectrum.halo.is_default
    assert "Helm form factor for Xe124, Xe126" in spectrum.nuclear_input


def test_a_tabulated_halo_gives_the_same_rate() -> None:
    e, p, xe = [3.0, 20.0, 60.0], DarkMatterParticle(mass_gev=80.0), targets.target("Xe")
    interaction = _interaction(o1=(C, C), o8=(C, -C))
    exact = rates.differential_rate(e, p, interaction, xe).rate
    table = rates.differential_rate(e, p, interaction, xe, halo=halos.tabulate(HaloModel(), 4000))
    assert table.rate == pytest.approx(exact, rel=1e-4)


def test_annual_modulation_peaks_in_june_and_reverses_at_low_speed() -> None:
    # For 100 GeV on xenon the phase reverses near v_min ≈ 205 km/s (about 23 keV).
    interaction, xe = _interaction(o1=(C, C)), targets.target("Xe")
    spectrum = rates.annual_modulation([5.0, 60.0], DarkMatterParticle(mass_gev=100.0),
                                       interaction, xe)
    slow, fast = 0, 1
    assert spectrum.peak_day[fast] == pytest.approx(152.0, abs=5.0)          # about 2 June
    assert spectrum.peak_day[slow] == pytest.approx(152.0 + 365.25 / 2, abs=5.0)
    assert 0.01 < spectrum.amplitude[fast] / spectrum.mean_rate[fast] < 0.1
    # the yearly mean is close to the rate for the 9 March velocity (arXiv:2105.00599)
    average = rates.differential_rate([5.0, 60.0], DarkMatterParticle(mass_gev=100.0),
                                      interaction, xe)
    assert spectrum.mean_rate == pytest.approx(average.rate, rel=5e-3)


def _reference_cases() -> list[tuple[str, dict]]:
    cases = json.loads(FIXTURE.read_text())["cases"]
    return [(code, case) for case in cases if case["gate"] for code in case["codes"]]


@pytest.mark.parametrize(("code", "case"), _reference_cases(),
                         ids=lambda x: x if isinstance(x, str) else f"{x['name']}-{x['isotope']}")
def test_reference_spectra_are_reproduced(code: str, case: dict) -> None:
    """The DM2 gate: WIMpy_NREFT and WimPyDD spectra to 1% (docs/dm2_forward_model.md).

    Compared wherever v_min is at least 50 km/s below the fastest particle,
    and the reference rate is above 10⁻¹² of its peak.
    """
    particle = DarkMatterParticle(mass_gev=case["mass_gev"], spin=case["spin"],
                                  mass_splitting_kev=case["splitting_kev"])
    interaction = InteractionModel(
        name=case["name"], layer=ModelLayer.nonrelativistic,
        coefficients=[OperatorCoefficient(operator=int(op), proton=p, neutron=n)
                      for op, (p, n) in case["coefficients"].items()])
    isotope = targets.single_isotope(case["isotope"]).isotopes[0]
    energies = np.array(case["energies_kev"])
    mine = rates.isotope_rate(energies, particle, rates.isospin_coefficients(interaction), isotope,
                              HaloModel(), NuclearModel.shell_model)
    reference = np.array(case[code])
    m_t = cv.nuclear_mass_gev(isotope.mass_number)
    v_min = np.array([cv.v_min_km_s(e, m_t, particle.mass_gev, particle.mass_splitting_kev)
                      for e in energies])
    bulk = (v_min < halos.max_speed_km_s(HaloModel()) - 50.0) & (reference > 1e-12 * reference.max())
    assert bulk.sum() >= 3
    assert mine[bulk] == pytest.approx(reference[bulk], rel=1e-2)


# --- coefficients that depend on the momentum transfer ---------------------------------


def _o1(**q_dependence: float) -> InteractionModel:
    return InteractionModel(name="O1(q)", layer=ModelLayer.nonrelativistic,
                            coefficients=[OperatorCoefficient(operator=1, proton=1e-5,
                                                              neutron=1e-5, **q_dependence)])


def test_a_power_of_q_and_a_propagator_scale_the_rate_as_their_squares() -> None:
    xe131 = targets.single_isotope("Xe131")
    particle, energies = DarkMatterParticle(mass_gev=100.0), np.array([5.0, 20.0, 60.0])
    q = np.sqrt(2.0 * cv.nuclear_mass_gev(131) * energies * cv.KEV)
    plain = rates.differential_rate(energies, particle, _o1(), xe131).rate
    powered = rates.differential_rate(energies, particle, _o1(q_power=2, q_scale_gev=0.1),
                                      xe131).rate
    assert np.array(powered) / plain == pytest.approx((q / 0.1) ** 4, rel=1e-10)
    light = rates.differential_rate(energies, particle, _o1(mediator_mass_gev=0.02), xe131).rate
    assert np.array(light) / plain == pytest.approx((0.02 ** 2 / (q * q + 0.02 ** 2)) ** 2,
                                                    rel=1e-10)


def test_terms_of_one_operator_add_as_amplitudes() -> None:
    xe131 = targets.single_isotope("Xe131")
    particle, energies = DarkMatterParticle(mass_gev=100.0), np.array([5.0, 40.0])
    q = np.sqrt(2.0 * cv.nuclear_mass_gev(131) * energies * cv.KEV)
    both = InteractionModel(name="O1 + q² O1", layer=ModelLayer.nonrelativistic, coefficients=[
        OperatorCoefficient(operator=1, proton=1e-5, neutron=1e-5),
        OperatorCoefficient(operator=1, proton=-2e-5, neutron=-2e-5, q_power=2, q_scale_gev=0.1)])
    plain = rates.differential_rate(energies, particle, _o1(), xe131).rate
    summed = rates.differential_rate(energies, particle, both, xe131).rate
    assert np.array(summed) / plain == pytest.approx((1.0 - 2.0 * (q / 0.1) ** 2) ** 2, rel=1e-10)
    with pytest.raises(ValueError, match="depends on q"):
        rates.isospin_coefficients(both)
    with pytest.raises(ValueError, match="same q-dependence"):
        InteractionModel(name="twice", layer=ModelLayer.nonrelativistic,
                         coefficients=[OperatorCoefficient(operator=1, proton=1.0)] * 2)

"""Missing rates never pass and a conditional diagnostic does not certify plasma physics."""

import pytest
from adroit.theory.chemical_equilibrium import certify, BORN_THRESHOLD
from adroit.theory.chemical_report import report, study_section
from adroit.core.chemical_equilibrium import ConversionRequest
from test_conversion_rates import example


def test_missing_family_request_and_zero():
    p = example()
    assert certify(p.model_copy(update={"partner": "uR"})).status == "missing_rates"
    assert certify(p.model_copy(update={"majorana": False})).passed is None
    assert certify(p.model_copy(update={"request": None})).status == "missing_input"
    p.point.g_chi = 0
    c = certify(p)
    assert c.passed is False and c.complete and c.physical_prerequisite == "failed"
    assert study_section([]) == [] and "failed" in report(c)
    p.point.m_med = p.point.m_chi
    assert certify(p).status == "outside_domain"


def test_pending_inclusive_rates_even_when_born_strong():
    p = example(3e-5)
    c = certify(p)
    assert c.born_diagnostic_passed is True and c.minimum_relaxation_over_h > BORN_THRESHOLD
    assert c.status == "missing_rates" and not c.complete and c.passed is None
    assert c.physical_prerequisite == "pending" and len(c.missing_channels) == 3
    c.rates.clear()
    assert certify(p).rates
    weak = certify(example(1e-7))
    assert weak.born_diagnostic_passed is False and weak.passed is None
    assert weak.status == "missing_rates"


def test_interval_and_domain_are_explicit():
    p = example()
    p.point.m_chi = 200
    p.point.m_med = 220
    assert certify(p).status == "outside_domain"
    with pytest.raises(ValueError):
        ConversionRequest(
            x_low=40,
            x_high=20,
            rate_relative_uncertainty=0.5,
            approximation="unbroken_hypercharge_vacuum_Born_MB",
        )
    with pytest.raises(ValueError):
        ConversionRequest(
            x_low=10,
            x_high=40,
            rate_relative_uncertainty=0.5,
            approximation="unbroken_hypercharge_vacuum_Born_MB",
            angular_cuts=(0.5, 0.6, 0.7),
        )

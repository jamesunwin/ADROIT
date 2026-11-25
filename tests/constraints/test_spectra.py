"""Branching, units, finite-mass boosts and refusal of unsupported inputs."""

import numpy as np
import pytest

from adroit.constraints.spectra import (
    Component,
    Decay,
    SpectrumRequest,
    SpectrumUnavailable,
    prompt,
    boost,
    spectrum,
    table,
    from_rates,
)


@pytest.fixture
def shower(tmp_path):
    rows = []
    for mass in (5.0, 10.0, 20.0, 100.0, 500.0, 1000.0):
        for logx in np.linspace(-8.9, 0, 180):
            row = np.zeros(30)
            row[:2] = (mass, logx)
            # Independent analytic dN/dE = 0.1 / mass on its source interval.
            row[2:] = 0.1 * 10**logx * np.log(10)
            row[12] = 2 * row[13]
            rows.append(row)
    path = tmp_path / "showers.dat"
    np.savetxt(path, rows, header="fixture", comments="")
    return path


def test_mixture_is_sum_of_actual_showers_and_has_correct_units(shower):
    energy = np.geomspace(0.001, 99, 1000)
    data = table(shower)
    request = SpectrumRequest(
        mass_gev=100,
        components=[Component(channel="b", branching=0.3), Component(channel="c", branching=0.7)],
    )
    result = spectrum(request, energy, shower)
    expected = 0.3 * prompt(100, "b", energy, data) + 0.7 * prompt(100, "c", energy, data)
    assert np.array_equal(result.dnde_per_gev, expected)
    assert prompt(100, "b", np.array([1.0]), data)[0] == pytest.approx(0.001, rel=0.004)
    with pytest.raises(ValueError, match="sum to one"):
        SpectrumRequest(mass_gev=100, components=[Component(channel="b", branching=0.5)])
    with pytest.raises(ValueError, match="ignored"):
        SpectrumRequest(
            mass_gev=100, components=[Component(channel="b", branching=1, mediator_mass_gev=50)]
        )


def test_boost_preserves_two_mediator_multiplicity_and_energy():
    rest = np.geomspace(0.01, 10.0, 12001)
    yield_ = np.ones_like(rest) * 0.1
    energy = np.geomspace(0.0005, 100.0, 25001)
    result = boost(rest, yield_, energy, 100.0, 20.0)
    assert np.trapezoid(result, energy) == pytest.approx(2 * np.trapezoid(yield_, rest), rel=2e-4)
    assert np.trapezoid(energy * result, energy) == pytest.approx(
        10 * np.trapezoid(rest * yield_, rest), rel=2e-4
    )
    assert np.array_equal(boost(rest, yield_, rest, 20.0, 20.0), 2 * yield_)
    with pytest.raises(SpectrumUnavailable, match="on shell"):
        boost(rest, yield_, energy, 10.0, 20.0)


def test_cascade_at_threshold_is_two_actual_pair_showers(shower):
    energy = np.geomspace(0.001, 99, 1001)
    request = SpectrumRequest(
        mass_gev=100,
        components=[
            Component(
                channel="SS",
                branching=1,
                mode="scalar_pair",
                mediator_mass_gev=100,
                decays=[Decay(channel="b", branching=1)],
            )
        ],
    )
    result = spectrum(request, energy, shower)
    # At beta=0 both rest-frame pair showers remain at their own half-mass.
    expected = 2 * prompt(50, "b", energy, table(shower))
    assert np.array_equal(result.dnde_per_gev, expected)


def test_unknown_channels_and_mass_extrapolation_are_refused(shower):
    data = table(shower)
    with pytest.raises(SpectrumUnavailable):
        prompt(100, "unknown", np.array([1.0]), data)
    with pytest.raises(SpectrumUnavailable):
        prompt(2, "b", np.array([1.0]), data)
    with pytest.raises(SpectrumUnavailable):
        prompt(1001, "b", np.array([1.0]), data)
    with pytest.raises(SpectrumUnavailable, match="description"):
        from_rates(100, {"b": 1e-26, "A'A'": 1e-26})
    with pytest.raises(SpectrumUnavailable, match="rates"):
        from_rates(100, {"b": float("nan")})
    with pytest.raises(SpectrumUnavailable, match="rates"):
        from_rates(100, {"b": 1e308, "c": 1e308})


def test_two_identical_new_daughters_are_the_scalar_pair(shower):
    """G6's two-body topology with two identical states is the scalar class's SS cascade, to the bit."""
    from adroit.constraints.spectra import Daughter
    energy = np.geomspace(0.001, 99, 801)
    decays = [Decay(channel="b", branching=0.7), Decay(channel="tau", branching=0.3)]
    pair = Component(channel="SS", branching=1, mode="scalar_pair", mediator_mass_gev=40, decays=decays)
    two = Component(channel="S S", branching=1, mode="two_body",
                    daughters=[Daughter(mass_gev=40, decays=decays), Daughter(mass_gev=40, decays=decays)])
    a = spectrum(SpectrumRequest(mass_gev=100, components=[pair]), energy, shower).dnde_per_gev
    b = spectrum(SpectrumRequest(mass_gev=100, components=[two]), energy, shower).dnde_per_gev
    assert np.allclose(a, b, rtol=1e-12, atol=0)


def test_standard_daughters_shower_at_their_own_energies(shower):
    """χχ → Z h at m_χ = 600: half the ZZ shower at E_Z and half the hh shower at E_h; an invisible decay gives none."""
    from adroit.constraints.spectra import Daughter
    energy = np.geomspace(0.01, 590, 801)
    data = table(shower)
    m, mz, mh = 600.0, 91.1876, 125.09
    e_z, e_h = (4 * m * m + mz * mz - mh * mh) / (4 * m), (4 * m * m + mh * mh - mz * mz) / (4 * m)
    zh = Component(channel="Zh", branching=1, mode="two_body",
                   daughters=[Daughter(mass_gev=mz, channel="Z"), Daughter(mass_gev=mh, channel="hh")])
    got = spectrum(SpectrumRequest(mass_gev=m, components=[zh]), energy, shower).dnde_per_gev
    expected = 0.5 * prompt(e_z, "Z", energy, data) + 0.5 * prompt(e_h, "hh", energy, data)
    assert np.allclose(got, expected)
    dark = Component(channel="S h", branching=1, mode="two_body",
                     daughters=[Daughter(mass_gev=40, decays=[Decay(channel="invisible", branching=1.0)]),
                                Daughter(mass_gev=mh, channel="hh")])
    alone = spectrum(SpectrumRequest(mass_gev=m, components=[dark]), energy, shower).dnde_per_gev
    e_h2 = (4 * m * m + mh * mh - 40 ** 2) / (4 * m)
    assert np.allclose(alone, 0.5 * prompt(e_h2, "hh", energy, data))


def test_a_line_is_refused_by_the_reference_energy_likelihood_with_its_reason():
    """The 2024 release reads dΦ/dE at each bin's reference energy, which a line cannot give; the 2015 rule bins it."""
    from adroit.constraints.spectra import SpectrumUnavailable, from_rates
    with pytest.raises(SpectrumUnavailable, match="line"):
        from_rates(100.0, {"b": 1e-26, "gamma": 1e-29})

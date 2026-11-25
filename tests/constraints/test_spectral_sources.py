"""Offline validation against installed, pinned public author releases."""

import numpy as np
import pytest
from scipy.integrate import cumulative_trapezoid

from adroit.constraints import dwarf_likelihood as dl, spectra
from adroit.external.fetch import locate

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        locate(dl.ITEM) is None or locate(spectra.PPPC_ITEM) is None,
        reason="install the optional PPPC and McDaniel spectral releases",
    ),
]


def test_eight_pure_limits_recover_the_authors_independent_ts_grids():
    root = locate(dl.ITEM)
    masses, rates = np.logspace(0, 4, 40), np.logspace(-28, -22, 60)
    for channel, label in (("b", "bb"), ("tau", "tau")):
        reference = sum(
            np.load(root / "dSphs/TS_profiles" / f"{name}_Jprior_{label}.npy")
            for name in dl.BENCHMARK
        )
        for index in (10, 19, 25, 31):
            photons = spectra.spectrum(spectra.from_rates(float(masses[index]), {channel: 1.0}))
            limit = dl.upper_limit(photons)
            ts = reference[index]
            peak = int(np.argmax(ts))
            target = ts[peak] - 2.71
            j = next(j for j in range(peak + 1, len(ts)) if ts[j] <= target)
            expected = np.interp(target, ts[j - 1 : j + 1][::-1], rates[j - 1 : j + 1][::-1])
            # Published coarse sigma-v grids and linear-mass showers differ from
            # our continuous root and log-mass interpolation; 2% is the tested envelope.
            assert limit.upper95_cm3_s == pytest.approx(expected, rel=0.02)


def test_cascade_boost_against_two_million_independent_photon_samples():
    mass, med = 500.0, 100.0
    photons = spectra.spectrum(
        spectra.SpectrumRequest(
            mass_gev=mass,
            components=[
                spectra.Component(
                    channel="SS",
                    branching=1.0,
                    mode="scalar_pair",
                    mediator_mass_gev=med,
                    decays=[spectra.Decay(channel="b", branching=1.0)],
                )
            ],
        )
    )
    rest = np.geomspace(1e-7, med / 2, 20001)
    yield_ = spectra.prompt(med / 2, "b", rest, spectra.table())
    cdf = cumulative_trapezoid(yield_, rest, initial=0.0)
    rng = np.random.default_rng(20261007)
    samples = np.interp(rng.random(2000000) * cdf[-1], cdf, rest)
    gamma = mass / med
    lab = gamma * samples * (1 + np.sqrt(1 - 1 / gamma**2) * rng.uniform(-1, 1, len(samples)))
    energy, predicted_yield = np.array(photons.energies_gev), np.array(photons.dnde_per_gev)
    bins = np.geomspace(0.5, mass, 61)
    observed = np.histogram(lab, bins)[0] * 2 * cdf[-1] / len(lab)
    predicted = np.diff(
        np.interp(bins, energy, cumulative_trapezoid(predicted_yield, energy, initial=0.0))
    )
    assert np.sum(abs(observed - predicted)) / np.sum(predicted) < 0.01
    assert np.trapezoid(predicted_yield, energy) / (2 * cdf[-1]) == pytest.approx(1.0, rel=0.0001)
    fraction = np.trapezoid(energy * predicted_yield, energy) / (2 * mass)
    assert fraction < 1.0
    assert np.trapezoid(energy * predicted_yield, energy) / (
        2 * gamma * np.trapezoid(rest * yield_, rest)
    ) == pytest.approx(1.0, rel=0.0001)

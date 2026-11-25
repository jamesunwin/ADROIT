"""The signal density normalised on the window as seen (the external audit of 2026-10-16, A09).

The likelihood −s + Σ ln(s f̃_i + b_i) needs ∫_W f̃ = 1 for s to be the expected count inside the window W.
The density is given in true energy on W; smeared by a resolution σ, a share 1 − ε_W of it is seen outside W.
Before the fix that share was taken out of f̃ but not out of s."""

from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.core.dm_state import DarkMatterParticle, ExpectedSignal
from adroit.inference import signal_fit
from adroit.orchestrator import signal as path2

# the audit's synthetic control (evidence/threshold_normalization.py): a spectrum falling on 0.01 keV, seen
# through σ = 0.2 keV, in a window [0, 5] keV, with three events near the threshold on a flat 0.1/keV background
ENERGIES = np.linspace(0.0, 5.0, 1001)
STEEP = np.exp(-ENERGIES / 0.01)
SIGMA = 0.2
EVENTS = np.array([0.02, 0.06, 0.1])


def test_the_smeared_density_integrates_to_one_on_the_window() -> None:
    seen = np.linspace(0.0, 5.0, 20001)
    for density in (STEEP, np.ones_like(ENERGIES), np.exp(-ENERGIES / 1.5)):
        f = signal_fit.event_densities(ENERGIES, density, seen, SIGMA)
        assert np.trapezoid(f, seen) == pytest.approx(1.0, abs=1e-6)


def test_the_audits_threshold_control() -> None:
    """ε_W = 0.5199 (the exponential's own, finely integrated: 0.519898); the local Z is 4.718 normalised, where the
    leak had given 4.287. Until the audit of 2026-10-17 (R17-3) ε_W was a trapezoid sum on the grid, 0.519090."""
    epsilon = signal_fit.seen_fraction(ENERGIES, STEEP, SIGMA)
    assert epsilon == pytest.approx(0.5198976, abs=1e-5)
    f = signal_fit.event_densities(ENERGIES, STEEP, EVENTS, SIGMA)
    b = np.full(3, 0.1)
    assert signal_fit.fit("normalised", f, b).z_local == pytest.approx(4.71752, abs=1e-4)
    assert signal_fit.fit("as before", f * epsilon, b).z_local == pytest.approx(4.28728, abs=1e-4)


def test_the_seen_share_is_what_a_monte_carlo_smearing_keeps() -> None:
    """Draw true energies from the density on the window, smear each by σ, and count those still inside."""
    rng = np.random.default_rng(20261016)
    density = np.exp(-ENERGIES / 0.3)
    cumulative = np.concatenate([[0.0], np.cumsum((density[1:] + density[:-1]) / 2 * np.diff(ENERGIES))])
    u = rng.uniform(0.0, cumulative[-1], 1_000_000)
    i = np.clip(np.searchsorted(cumulative, u) - 1, 0, ENERGIES.size - 2)       # inverse of the piecewise-linear CDF
    a, h = density[i], ENERGIES[i + 1] - ENERGIES[i]
    slope = (density[i + 1] - a) / h
    du = u - cumulative[i]
    x = np.where(np.abs(slope) > 0, (np.sqrt(a * a + 2 * slope * du) - a) / np.where(slope == 0, 1, slope), du / a)
    seen = ENERGIES[i] + x + rng.normal(0.0, SIGMA, u.size)
    kept = float(np.mean((seen >= 0.0) & (seen <= 5.0)))
    assert signal_fit.seen_fraction(ENERGIES, density, SIGMA) == pytest.approx(kept, abs=2e-3)


def test_the_seen_count_is_the_window_count_times_the_seen_share() -> None:
    total = float(np.trapezoid(STEEP * 30.0, ENERGIES))
    assert signal_fit.seen_events(ENERGIES, STEEP * 30.0, SIGMA) == pytest.approx(
        total * signal_fit.seen_fraction(ENERGIES, STEEP, SIGMA), rel=1e-12)


def test_without_a_resolution_nothing_changes() -> None:
    density = np.exp(-ENERGIES / 1.5)
    assert signal_fit.seen_fraction(ENERGIES, density, 0.0) == 1.0
    f = signal_fit.event_densities(ENERGIES, density, EVENTS)
    assert f == pytest.approx(np.interp(EVENTS, ENERGIES, density / np.trapezoid(density, ENERGIES)))


def test_far_from_the_edges_the_share_is_one() -> None:
    density = np.exp(-0.5 * ((ENERGIES - 2.5) / 0.3) ** 2)
    assert signal_fit.seen_fraction(ENERGIES, density, SIGMA) == pytest.approx(1.0, abs=1e-9)


def test_the_toys_see_the_same_normalisation() -> None:
    """Path 2's toys smear on the grid; their shapes integrate to one on the window too, so the toy statistic is
    the data's."""
    shape = STEEP / np.trapezoid(STEEP, ENERGIES)
    toy = path2._smeared(shape, ENERGIES, np.full(ENERGIES.size, SIGMA))
    assert np.trapezoid(toy, ENERGIES) == pytest.approx(1.0, abs=1e-4)


def test_a_reconstructed_spectrum_is_not_smeared_again() -> None:
    signal = ExpectedSignal(experiment="x", particle=DarkMatterParticle(mass_gev=10.0), total_events=1.0,
                            observable=[0.0, 1.0], density=[1.0, 1.0], energy_scale="reconstructed")
    with pytest.raises(ValueError, match="reconstructed energy"):
        signal_fit.true_energy(signal)
    assert signal_fit.true_energy(signal.model_copy(update={"energy_scale": "true"})).energy_scale == "true"


@pytest.mark.parametrize("name", [pytest.param("CRESST-III 2019", marks=pytest.mark.needs("cresst")), "DEAP-3600 (2019)"])
def test_the_searches_that_smear_themselves_say_so(name: str) -> None:
    """CRESST-III and DEAP-3600 return their spectra in reconstructed energy (photoelectrons for DEAP)."""
    from adroit.experiments import registry as modules
    from adroit.experiments.base import reference_interaction
    from adroit.core.dm_state import CrossSectionKind
    module = modules.load_module(name)
    conventions = module.conventions()
    s = module.expected_signal(DarkMatterParticle(mass_gev=30.0),
                               reference_interaction(CrossSectionKind.si, 1e-44, 30.0), conventions.halo,
                               conventions.nuclear_model)
    assert s.energy_scale == "reconstructed"
    assert math.isfinite(s.total_events)


def test_the_result_says_how_the_signal_was_smeared() -> None:
    """The plan's A09 (2): a module gives its density on the window only, so the smearing is window-truncated, and
    the global significance's method says so."""
    from adroit.experiments import registry
    module = registry.load_module("CDMS II Si (2013)")
    energies = np.asarray(module.signal_grid_kev(), float)
    shape = np.exp(-energies / 5.0)
    *_, method = path2._global_significance(module, (shape / np.trapezoid(shape, energies))[None, :], energies,
                                            1.0, 20)
    assert method.endswith(path2.WINDOW_SMEARING)


# The external audit of 2026-10-17, R17-3 (evidence root/smearing_controls.py): a flat density on [0, 5] keV, σ =
# 0.001 keV on the anomaly records' 800-point grid (spacing 0.00626 keV), three events, a flat 0.1/keV background.
# The Gaussian had been sampled on the grid: events on grid nodes gave f̃ = 0.4996 and Z = 3.26, the same events half
# a cell along f̃ = 0.0075 and Z = 0; exactly, f̃ = 0.20003 and Z = 2.398 wherever they sit.
NARROW_GRID = np.linspace(0.0, 5.0, 800)


def test_a_width_narrower_than_the_grid_does_not_depend_on_where_the_events_sit() -> None:
    flat = np.ones_like(NARROW_GRID)
    edge = 5.0 / 0.001
    count = 5.0 * (2 * float(signal_fit.ndtr(edge)) - 1) + 2 * 0.001 * (math.exp(-edge ** 2 / 2) - 1) / math.sqrt(2 * math.pi)
    assert signal_fit.seen_events(NARROW_GRID, flat, 0.001) == pytest.approx(count, rel=1e-12)       # 4.99920
    step = NARROW_GRID[1] - NARROW_GRID[0]
    zs = []
    for shift in (0.0, 0.25, 0.5):
        events = NARROW_GRID[[160, 400, 640]] + shift * step
        f = signal_fit.event_densities(NARROW_GRID, flat, events, 0.001)
        assert f == pytest.approx(np.full(3, 1.0 / count), rel=1e-9)                                      # 0.20003
        zs.append(signal_fit.fit("narrow", f, np.full(3, 0.1)).z_local)
    assert zs == pytest.approx([2.39820] * 3, abs=1e-4)


def test_a_vanishing_width_gives_the_unsmeared_density() -> None:
    density = 1.0 + np.sin(3.0 * NARROW_GRID)
    events = np.array([0.3, 1.234567, 2.5, 4.4])
    unsmeared = np.interp(events, NARROW_GRID, density / np.trapezoid(density, NARROW_GRID))
    for sigma in (1e-5, 1e-8):                     # the window's edges leak ∝ σ (≈ 2·10⁻⁴ at σ = 10⁻³)
        assert signal_fit.event_densities(NARROW_GRID, density, events, sigma) == pytest.approx(unsmeared, rel=10 * sigma)


def test_the_window_share_is_exact_for_any_width() -> None:
    """ε_W against a fine integration of the smeared density over the window, from σ ≪ spacing to σ ≫ the window."""
    from adroit.experiments.base import smear
    density = 1.0 + np.sin(ENERGIES)
    shape = density / np.trapezoid(density, ENERGIES)
    seen = np.linspace(0.0, 5.0, 40001)
    for sigma in (0.003, 0.05, 0.7, 3.0):
        brute = np.trapezoid(smear(ENERGIES, shape, seen, sigma), seen)
        assert signal_fit.seen_fraction(ENERGIES, density, sigma) == pytest.approx(brute, abs=1e-6)


def test_the_narrow_toy_density_is_normalised() -> None:
    """The toys' shape on the grid (``signal._smeared``) integrates to one up to the grid's own trapezoid rule at
    the window's edges, where the seen density halves within σ (it had integrated to 2.497)."""
    shape = path2._smeared(np.ones_like(NARROW_GRID), NARROW_GRID, np.full(NARROW_GRID.size, 0.001))
    assert np.trapezoid(shape, NARROW_GRID) == pytest.approx(1.0, abs=1e-3)


def test_an_energy_dependent_resolution_is_refused() -> None:
    """σ(e) normalised with the events' median is not normalised on the window (the audit's σ = 0.1 + 0.4E control
    integrated to 2.007); until that normalisation is computed it is refused."""
    seen = np.linspace(0.0, 5.0, 2001)
    with pytest.raises(ValueError, match="energy-dependent resolution"):
        signal_fit.event_densities(ENERGIES, np.exp(-ENERGIES / 0.1), seen, 0.1 + 0.4 * seen)
    with pytest.raises(ValueError, match="energy-dependent resolution"):
        signal_fit.seen_fraction(ENERGIES, np.exp(-ENERGIES / 0.1), np.array([0.5, 0.6]))

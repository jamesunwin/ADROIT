"""Counting statistics, the profile likelihood, and Yellin's interval methods."""

from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.statistics import intervals, optimum_interval, poisson, profile


def test_the_poisson_upper_limit() -> None:
    # no events: −ln(1 − CL); three events and no background: 6.68 (standard tables)
    assert poisson.poisson_upper_limit(0) == pytest.approx(-math.log(0.1), rel=1e-10)
    assert poisson.poisson_upper_limit(3) == pytest.approx(6.6808, abs=1e-4)
    for n in (0, 1, 5, 20):
        assert poisson.poisson_upper_limit(n) == pytest.approx(
            poisson.poisson_upper_limit_zero_background(n), rel=1e-9)
    # background lowers the limit on the signal, but never below zero
    assert poisson.poisson_upper_limit(3, background=1.0) == pytest.approx(5.6808, abs=1e-4)
    assert poisson.poisson_upper_limit(0, background=5.0) == 0.0
    with pytest.raises(ValueError):
        poisson.poisson_upper_limit(-1)


def test_the_binned_log_likelihood() -> None:
    observed, expected = np.array([0, 2, 5]), np.array([0.5, 2.0, 4.0])
    manual = sum(n * math.log(m) - m for n, m in zip(observed, expected))
    assert poisson.binned_log_likelihood(observed, expected) == pytest.approx(manual)
    assert poisson.binned_log_likelihood([1], [0.0]) == -math.inf
    with pytest.raises(ValueError):
        poisson.binned_log_likelihood([1], [-1.0])


def test_the_profile_likelihood_on_a_gaussian_measurement() -> None:
    # κ measured as 3 ± 1: the 90% one-sided limit is 3 + 1.2816, the significance 3.
    def nll(kappa: float) -> float:
        return 0.5 * (kappa - 3.0) ** 2

    assert profile.one_sided_threshold(0.9) == pytest.approx(1.2815516 ** 2, rel=1e-6)
    assert profile.upper_limit(nll, scale=1.0) == pytest.approx(3.0 + 1.2815516, rel=1e-6)
    assert profile.discovery_significance(nll, scale=1.0) == pytest.approx(3.0, rel=1e-6)


def test_a_best_fit_below_zero_is_held_at_zero() -> None:
    def nll(kappa: float) -> float:
        return 0.5 * (kappa + 2.0) ** 2

    assert profile.best_fit(nll, 1.0)[0] == 0.0
    assert profile.discovery_significance(nll) == 0.0
    # the limit is then measured from κ = 0
    assert 0.0 < profile.upper_limit(nll) < 1.2815516


def test_the_maximum_gap_probability() -> None:
    # with no events the one gap is everything: C0(μ, μ) = 1 − e^{−μ}
    assert intervals.maximum_gap_probability(2.0, 2.0) == pytest.approx(1.0 - math.exp(-2.0))
    # C0 rises with x at fixed μ, and is 0 for an empty gap
    values = [intervals.maximum_gap_probability(x, 10.0) for x in (0.5, 1.0, 2.0, 4.0, 8.0)]
    assert all(b > a for a, b in zip(values, values[1:])) and 0.0 < values[0]
    assert intervals.maximum_gap_probability(0.0, 5.0) == 0.0


def test_the_maximum_gap_limit() -> None:
    assert intervals.maximum_gap_limit(np.array([])) == pytest.approx(-math.log(0.1), rel=1e-8)
    # one event at the midpoint: largest gap 1/2, and the limit solves C0(μ/2, μ) = 0.9
    mu = intervals.maximum_gap_limit(np.array([0.5]))
    assert intervals.maximum_gap_probability(mu / 2, mu) == pytest.approx(0.9, abs=1e-9)
    # events crowded at one end leave a large gap and a limit near the no-event one
    assert intervals.maximum_gap_limit(np.array([0.98, 0.99])) < 2.5


def test_cumulative_fractions_and_gaps() -> None:
    grid = np.linspace(0.0, 10.0, 1001)
    fractions = intervals.cumulative_fractions(np.array([5.0, 2.5, 20.0]), grid, np.ones_like(grid))
    assert fractions == pytest.approx([0.25, 0.5, 1.0])
    assert intervals.largest_gap(np.array([0.25, 0.5])) == pytest.approx(0.5)
    with pytest.raises(ValueError, match="no weight"):
        intervals.cumulative_fractions(np.array([1.0]), grid, np.zeros_like(grid))


@pytest.mark.skipif(not optimum_interval.available(), reason="optimum interval code not fetched")
def test_the_optimum_interval_reproduces_its_published_example() -> None:
    """The CDMSlite release's own input and output (ULinput, ULoutput), mass by mass."""
    folder = optimum_interval.code_folder()
    inputs = [line.split() for line in (folder / "ULinput").read_text().splitlines() if line.strip()]
    outputs = [line.split() for line in (folder / "ULoutput").read_text().splitlines() if line.strip()]
    for row, out in list(zip(inputs, outputs))[::10]:
        sigma0, mu0 = float(row[0]), float(row[2])
        fractions = np.array([float(x) for x in row[3:]])
        above = np.nonzero(fractions > 0.9999)[0]
        if above.size:
            fractions = fractions[: above[0] + 1]
        mu, flag = optimum_interval.optimum_interval_limit(fractions)
        # the release prints three significant figures
        assert sigma0 / mu0 * mu == pytest.approx(float(out[0].replace("D", "E")), rel=5e-3)
        assert flag == 0
    assert optimum_interval.optimum_interval_limit(np.array([]))[0] == pytest.approx(
        -math.log(0.1), rel=1e-6)


def test_the_free_background_limit_reduces_to_classical_limits() -> None:
    # one bin: no events gives 2.30, three events with the background free gives 6.68
    assert poisson.free_background_limit([0], [1.0], toys=20_000) == pytest.approx(2.3026, rel=5e-3)
    assert poisson.free_background_limit([3], [1.0], toys=20_000) == pytest.approx(6.6808, rel=5e-3)
    # the answer does not depend on the unit of the expected signal
    assert poisson.free_background_limit([0, 3], [1e-6, 1e-6]) == pytest.approx(
        1e6 * poisson.free_background_limit([0, 3], [1.0, 1.0]), rel=1e-6)
    # the statistic is zero while the signal stays below the counts
    assert poisson.free_background_statistic(np.array([3.0]), np.array([1.0]), 2.0) == 0.0


def test_the_cousins_highland_limit() -> None:
    assert poisson.cousins_highland_limit(0, 0.0) == pytest.approx(-math.log(0.1))
    # for no events and a Gaussian sensitivity: s − s²σ²/2 = −ln(1 − CL)
    for sigma in (0.05, 0.1, 0.2):
        exact = (1.0 - math.sqrt(1.0 - 2.0 * (-math.log(0.1)) * sigma ** 2)) / sigma ** 2
        assert poisson.cousins_highland_limit(0, sigma) == pytest.approx(exact, rel=2e-3)
    with pytest.raises(ValueError):
        poisson.cousins_highland_limit(0, -0.1)

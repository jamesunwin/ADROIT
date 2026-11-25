"""Native likelihood reproduction and auxiliary-generating-model consistency."""

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import minimize_scalar

from adroit.statistics.native_pair import (
    EventData,
    event_profile,
    auxiliary_toy,
    zero_count_log_l,
    sample_linear_density,
)


@pytest.mark.parametrize("s,d", [(0.0, 0.1), (1.0, 0.0), (0.4, 0.1), (3.0, 0.3), (40.0, 0.1)])
def test_zero_count_native_ch_integral(s, d):
    if d == 0:
        expected = -s
    else:
        lo, hi = max(0, 1 - 8 * d), 1 + 8 * d

        def weight(e):
            return np.exp(-0.5 * ((e - 1) / d) ** 2)

        expected = np.log(
            quad(lambda e: np.exp(-s * e) * weight(e), lo, hi, epsabs=1e-16)[0]
            / quad(weight, lo, hi)[0]
        )
    assert zero_count_log_l(s, d) == pytest.approx(expected, abs=1e-8)
    assert np.isfinite(zero_count_log_l(1e12, 0.1))


@pytest.mark.parametrize("auxiliary", [-1.0, 0.0, 1.0, 2.0])
def test_event_profile_against_independent_bounded_optimisation(auxiliary):
    data = EventData(
        energies=[1.0, 2.0],
        background_at_events=[0.2, 0.1],
        background_total=0.4,
        sigma_minus=0.3,
        sigma_plus=0.7,
        auxiliary=auxiliary,
    )
    f = np.array([0.4, 0.3])
    s = 0.8

    def value(theta):
        sigma = data.sigma_plus if theta > auxiliary else data.sigma_minus
        return (
            -s
            - theta * 0.4
            + np.log(s * f + theta * np.array([0.2, 0.1])).sum()
            - 0.5 * ((theta - auxiliary) / sigma) ** 2
        )

    result = event_profile(s, f, data)
    reference = minimize_scalar(lambda t: -value(t), bounds=(0, 10), method="bounded")
    assert result.log_l == pytest.approx(max(value(0), -reference.fun), abs=1e-7)
    empty = data.model_copy(update={"energies": [], "background_at_events": []})
    assert event_profile(0, np.array([]), empty).theta >= 0


def test_auxiliary_draw_has_correct_sides_and_no_clipping():
    data = EventData(
        energies=[], background_at_events=[], background_total=0.4, sigma_minus=0.3, sigma_plus=0.7
    )
    rng = np.random.default_rng(7)
    draws = np.array([auxiliary_toy(0, data, rng) for _ in range(40000)])
    assert (draws < 0).mean() == pytest.approx(0.7, abs=0.01)
    assert np.std(draws[draws < 0]) > np.std(draws[draws > 0])
    assert (draws < 0).any() and not (draws == 0.001).any()
    with pytest.raises(ValueError):
        zero_count_log_l(-1, 0.1)
    with pytest.raises(ValueError):
        event_profile(-1, np.array([]), data)


def test_background_sampling_matches_linear_pdf():
    rng = np.random.default_rng(13)
    draws = sample_linear_density(np.array([0.0, 1.0]), np.array([0.0, 2.0]), 100000, rng)
    assert np.mean(draws) == pytest.approx(2 / 3, abs=0.004)
    assert (draws < 0.5).mean() == pytest.approx(0.25, abs=0.004)
    assert len(sample_linear_density(np.array([0.0, 1.0]), np.ones(2), 0, rng)) == 0
    with pytest.raises(ValueError):
        sample_linear_density(np.array([0.0, 1.0]), np.zeros(2), 1, rng)

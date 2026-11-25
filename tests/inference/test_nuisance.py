"""The background rate as a nuisance parameter: limits, consistency and the toys."""

import math

import numpy as np
import pytest
from pydantic import ValidationError

from adroit.inference import combination, look_elsewhere, nuisance, signal_fit
from adroit.inference.nuisance import BackgroundRate

B = 0.4                                   # expected background over a 10 keV window
b = np.full(3, B / 10.0)                  # its density at three events
f = np.array([0.30, 0.25, 0.20])          # a candidate peaked where the events are


def test_a_rate_needs_both_uncertainties_or_neither() -> None:
    assert not BackgroundRate(total=B).free
    assert BackgroundRate(total=B, minus=0.2, plus=0.3).free
    with pytest.raises(ValidationError):
        BackgroundRate(total=B, minus=0.2)


def test_without_an_uncertainty_nothing_changes() -> None:
    fixed = signal_fit.fit("x", f, b)
    assert signal_fit.fit("x", f, b, BackgroundRate(total=B)) == fixed
    assert np.allclose(signal_fit.profile_log_likelihood([0.0, 1.0], f, b), signal_fit.log_likelihood([0.0, 1.0], f, b))


def test_a_vanishing_uncertainty_gives_the_fixed_fit() -> None:
    fixed = signal_fit.fit("x", f, b)
    tight = signal_fit.fit("x", f, b, BackgroundRate(total=B, minus=1e-5, plus=1e-5))
    assert tight.z_local == pytest.approx(fixed.z_local, rel=1e-4)
    assert tight.s_hat == pytest.approx(fixed.s_hat, rel=1e-4) and tight.theta_hat == pytest.approx(1.0, abs=1e-4)


def test_an_uncertain_background_weakens_an_excess() -> None:
    fixed = signal_fit.fit("x", f, b)
    loose = signal_fit.fit("x", f, b, BackgroundRate(total=B, minus=0.6, plus=0.8))
    assert loose.z_local < fixed.z_local
    theta0, _ = nuisance.null_fit(b, BackgroundRate(total=B, minus=0.6, plus=0.8))
    assert theta0 > 1.0                    # background alone is pulled up to meet three events


def test_the_profile_is_the_maximum_over_theta() -> None:
    rate = BackgroundRate(total=B, minus=0.6, plus=0.8)
    grid = np.linspace(0.05, 6.0, 4000)

    def ln_l(s: float, theta: float) -> float:
        sigma = rate.plus if theta > 1.0 else rate.minus
        return -s - theta * B + np.log(s * f + theta * b).sum() - 0.5 * ((theta - 1.0) / sigma) ** 2

    for s in (0.0, 1.0, 3.0):
        brute = max(ln_l(s, t) for t in grid)
        assert float(signal_fit.profile_log_likelihood(s, f, b, rate)[0]) == pytest.approx(brute, abs=1e-5)


def test_many_candidates_at_once_match_one_at_a_time() -> None:
    rate = BackgroundRate(total=B, minus=0.3, plus=0.5)
    rows = np.array([f, f[::-1], np.full(3, 0.01), np.zeros(3) + 0.1])
    s_hat, gain = signal_fit.best_fits(rows, b, rate=rate)
    for row, s, g in zip(rows, s_hat, gain):
        one = signal_fit.fit("x", row, b, rate)
        assert s == pytest.approx(one.s_hat, rel=1e-6, abs=1e-9) and math.sqrt(2 * g) == pytest.approx(one.z_local, abs=1e-6)


def test_the_combination_profiles_the_background_too() -> None:
    rate = BackgroundRate(total=B, minus=0.6, plus=0.8)
    fixed = combination.combine("x", 4.0, f, b, {"null": 0.5})
    loose = combination.combine("x", 4.0, f, b, {"null": 0.5}, rate)
    assert loose.z_signal < fixed.z_signal and loose.z_joint < fixed.z_joint   # the evidence weakens
    assert loose.chi2_pg == pytest.approx(fixed.chi2_pg, rel=0.05)              # the tension barely moves


def test_toys_with_a_free_rate_draw_more_background_when_theta0_is_high() -> None:
    energies = np.linspace(0.0, 10.0, 200)
    background = np.full(energies.size, B / 10.0)
    shapes = np.array([np.exp(-energies / 2.0) / 2.0, np.full(energies.size, 0.1)])
    rate = BackgroundRate(total=B, minus=0.6, plus=0.8)
    fixed = look_elsewhere.toys(shapes, energies, background, 3000)
    free = look_elsewhere.toys(shapes, energies, background, 3000, rate=rate, theta0=2.0)
    assert (free > 0).mean() > (fixed > 0).mean()
    assert np.isfinite(free).all() and (free >= 0).all()


def test_a_toy_centre_is_positive_and_scattered_about_theta0() -> None:
    rng = np.random.default_rng(1)
    rate = BackgroundRate(total=B, minus=0.6, plus=0.8)
    draws = np.array([nuisance.toy_centre(1.5, rate, rng) for _ in range(4000)])
    # R6 (audit M5): drawn from the likelihood's density, below θ̂₀ with probability σ₊/(σ₊ + σ₋), and not clipped
    assert np.mean(draws < 1.5) == pytest.approx(0.8 / 1.4, abs=0.03) and 1.3 < np.median(draws) < 1.6

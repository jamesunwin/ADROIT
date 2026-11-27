"""DM6: signal fits, the global significance, the combination, the tournament and the forecast."""

from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.core.dm_state import DarkMatterParticle
from adroit.inference import combination, dm_tournament, forecast, look_elsewhere, signal_fit
from adroit.library.interactions import registry


def test_the_signal_fit_on_known_cases() -> None:
    # one event, no background: ŝ = 1 and the interval of q = 2(s − 1 − ln s)
    fit = signal_fit.fit("x", np.array([1.0]), np.array([1e-12]))
    assert fit.s_hat == pytest.approx(1.0, rel=1e-6)
    assert fit.interval_90 == pytest.approx((0.10571, 3.64655), rel=1e-4)
    # n events all where only the signal lives: ŝ = n
    f, b = np.full(5, 0.01), np.full(5, 1e-9)
    assert signal_fit.fit("y", f, b).s_hat == pytest.approx(5.0, rel=1e-6)
    # a background that explains the events as well as the signal: no significance
    assert signal_fit.fit("z", np.array([1e-6]), np.array([1e-3])).z_local == 0.0
    # the vectorised fit agrees with the scalar one
    rows = np.array([[0.02, 0.01], [0.001, 0.03]])
    s_hat, gain = signal_fit.best_fits(rows, np.array([1e-4, 1e-4]))
    for row, s, g in zip(rows, s_hat, gain):
        single = signal_fit.fit("r", row, np.array([1e-4, 1e-4]))
        assert s == pytest.approx(single.s_hat, rel=1e-6)
        assert g == pytest.approx(single.delta_log_l, rel=1e-6)


def test_smeared_event_densities() -> None:
    energies = np.linspace(0.0, 100.0, 2001)
    density = np.where(energies < 50.0, 2.0, 0.0)                 # flat on [0, 50]
    exact = signal_fit.event_densities(energies, density, np.array([25.0]))
    assert exact[0] == pytest.approx(1.0 / 50.0, rel=1e-3)
    smeared = signal_fit.event_densities(energies, density, np.array([50.0]), 5.0)
    # half the kernel inside, normalised on the window as seen: σ/√(2π) of the 50 keV leaks below 0 (audit A09)
    seen = 1.0 - 5.0 / (50.0 * math.sqrt(2.0 * math.pi))
    assert signal_fit.seen_fraction(energies, density, 5.0) == pytest.approx(seen, rel=1e-4)
    assert smeared[0] == pytest.approx(0.5 / 50.0 / seen, rel=1e-2)


def test_the_one_event_look_elsewhere_closed_form() -> None:
    energies = np.linspace(0.0, 100.0, 401)
    narrow = np.exp(-0.5 * ((energies - 50.0) / 2.0) ** 2)
    shapes = np.array([narrow / np.trapezoid(narrow, energies)])
    background = np.full(energies.size, 1e-5)
    # only events near 50 can be significant: the p-value is the background mass there
    z_obs = look_elsewhere.max_significance(shapes, energies, np.array([50.0]), background)
    p = look_elsewhere.one_event_p_value(z_obs - 1e-9, shapes, energies, background)
    assert 0.0 < p < 1e-5 * 100.0
    assert look_elsewhere.p_to_z(0.5) == pytest.approx(0.0, abs=1e-12)
    maxima = look_elsewhere.toys(shapes, energies, background, 20_000)
    assert np.mean(maxima >= z_obs - 1e-9) <= 1e-3


def test_the_combination_and_its_tension() -> None:
    f, b = np.array([4e-3]), np.array([5e-6])
    alone = combination.combine("a", 10.0, f, b, {})
    assert alone.z_joint == pytest.approx(alone.z_signal) and alone.chi2_pg == pytest.approx(0.0, abs=1e-8)
    tense = combination.combine("b", 10.0, f, b, {"null": 0.2 * alone.mu_hat_signal})
    assert tense.chi2_pg > 1.0 and tense.p_pg < 0.3 and tense.mu_hat_joint < alone.mu_hat_signal
    assert combination.null_q(1.0, math.inf) == 0.0


def test_the_tournament_ranks_by_aic_with_the_null() -> None:
    f, b = np.array([4e-3]), np.array([5e-6])
    strong = combination.combine("strong", 10.0, f, b, {})
    weak = combination.combine("weak", 10.0, np.array([2e-5]), b, {})
    result = dm_tournament.run([weak, strong], classes={"strong": 1, "weak": 2})
    assert [e.label for e in result.ranking][0] == "strong"
    assert dm_tournament.NULL in [e.label for e in result.ranking]
    assert result.ranking[0].delta_aic == 0.0 and result.signal_fit_leader == "strong"
    assert "strong" in result.indistinguishable and result.contested == ""


def test_the_tournament_refuses_an_infinite_joint_evidence() -> None:
    """RF23-03: a zero background at an event makes Z_J infinite for every candidate; the AIC against the background
    then orders nothing (a label order and NaN ΔAIC had been exported), so the tournament refuses it."""
    f, b = np.array([4e-3, 1e-3]), np.array([0.0, 5e-6])
    infinite = combination.combine("a", 10.0, f, b, {})
    assert not math.isfinite(infinite.z_joint)
    with pytest.raises(ValueError, match="joint evidence of a is not finite"):
        dm_tournament.run([infinite])


@pytest.mark.needs("revised_xenon")
def test_the_forecast_separates_isospin_through_rates() -> None:
    p = DarkMatterParticle(mass_gev=100.0)
    s = (p, registry.resolve("O1", p, registry.isospin_values("O1", "s", 1e-5)))
    v = (p, registry.resolve("O1", p, registry.isospin_values("O1", "v", 1e-5)))
    result = forecast.separate("O1s", s, "O1v", v, "Xe")
    # the isovector coupling counts Z − N: its rate relative to xenon differs most on light,
    # nearly isoscalar nuclei (Ar, Ge, F, ...), so the rate is the route
    assert result.route == "rate" and result.events_needed < 50
    assert result.by_target["Xe"][1] == math.inf         # the signal target itself: no rate test

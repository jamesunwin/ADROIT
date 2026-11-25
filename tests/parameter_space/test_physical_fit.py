"""Independent likelihood scans and refusal of incomplete physical fit coverage."""

import math

import numpy as np
import pytest

from adroit.core.model_spec import PhysicalFitRange
from adroit.parameter_space import physical_fit as pf
from adroit.parameter_space.classes import Point, Spin1Class


class Module:
    def observations(self):
        return np.array([1.0]), 0.0

    def background_at(self, events):
        return np.ones(len(events))

    def background_rate(self):
        return None


def likelihood(monkeypatch, function):
    def prediction(cls, point, module, spin):
        value = function(point.g_chi)
        return pf.FitTrial(
            point=point, log_l=value, signal_events=point.g_chi**2, densities_at_events=[1.0]
        )

    monkeypatch.setattr(pf, "predict", prediction)


@pytest.mark.parametrize("peak,boundary", [(0.37, False), (2.0, True), (-1.0, True)])
def test_interior_and_both_boundary_maxima_against_independent_dense_scan(
    monkeypatch, peak, boundary
):
    likelihood(monkeypatch, lambda g: -20 * (g - peak) ** 2)
    bounds = PhysicalFitRange(low=0, high=1)
    result = pf.fit(None, Point(m_chi=10, m_med=100), Module(), 0.5, bounds)
    grid = np.linspace(0, 1, 200001)
    dense = grid[np.argmax(-20 * (grid - peak) ** 2)]
    assert result.resolved and result.identifiable, result.reason
    assert result.point.g_chi == pytest.approx(dense, abs=2e-5)
    assert result.at_boundary is boundary
    assert result.evaluations <= result.settings.max_evaluations
    assert all(bounds.low <= r.low <= r.high <= bounds.high for r in result.regions)
    if boundary:
        assert result.regions[0].low_at_bound or result.regions[-1].high_at_bound


def test_multimodal_fit_retains_disconnected_regions_and_ambiguity(monkeypatch):
    likelihood(monkeypatch, lambda g: -200 * (g * g - 1) ** 2)
    result = pf.fit(
        None, Point(m_chi=10, m_med=100), Module(), 0.5, PhysicalFitRange(low=-2, high=2)
    )
    assert result.resolved and not result.identifiable
    assert len(result.modes) == 2 and len(result.regions) == 2
    assert result.regions[0].high < 0 < result.regions[1].low
    assert sorted(p.g_chi for p in result.modes) == pytest.approx([-1, 1], abs=1e-5)


def test_nearly_equal_samples_on_one_slope_are_not_fictitious_modes(monkeypatch):
    likelihood(monkeypatch, lambda g: -1000 * g * g)
    result = pf.fit(
        None, Point(m_chi=10, m_med=100), Module(), 0.5, PhysicalFitRange(low=0, high=1)
    )
    assert result.resolved and result.identifiable, result.reason
    assert result.point.g_chi == 0 and len(result.modes) == 1 and result.at_boundary


def test_lower_local_maximum_can_supply_a_second_likelihood_region(monkeypatch):
    likelihood(monkeypatch, lambda g: max(-1e7 * (g - 0.3) ** 2, -1e7 * (g - 0.68) ** 2 - 0.2))
    result = pf.fit(
        None, Point(m_chi=10, m_med=100), Module(), 0.5, PhysicalFitRange(low=0, high=1)
    )
    assert result.resolved and result.identifiable, result.reason
    assert result.point.g_chi == pytest.approx(0.3, abs=1e-6)
    assert len(result.regions) == 2
    assert result.regions[1].low < 0.68 < result.regions[1].high


def test_invalid_island_budget_flat_fit_and_changed_verification_are_pending(monkeypatch):
    def invalid(g):
        if 0.2 < g < 0.4:
            raise ValueError("closed physical region")
        return -((g - 0.7) ** 2)

    likelihood(monkeypatch, invalid)
    result = pf.fit(
        None, Point(m_chi=10, m_med=100), Module(), 0.5, PhysicalFitRange(low=0, high=1)
    )
    assert not result.resolved and result.invalid
    likelihood(monkeypatch, lambda g: -((g - 0.7) ** 2))
    result = pf.fit(
        None,
        Point(m_chi=10, m_med=100),
        Module(),
        0.5,
        PhysicalFitRange(low=0, high=1),
        pf.FitSettings(max_evaluations=5),
    )
    assert not result.resolved and "budget" in result.reason
    likelihood(monkeypatch, lambda g: 1.0)
    result = pf.fit(
        None, Point(m_chi=10, m_med=100), Module(), 0.5, PhysicalFitRange(low=0, high=1)
    )
    assert not result.resolved and "degenerate" in result.reason
    seen = {}

    def unstable(g):
        seen[g] = seen.get(g, 0) + 1
        return -20 * (g - 0.7) ** 2 + (1.0 if seen[g] > 1 else 0.0)

    likelihood(monkeypatch, unstable)
    result = pf.fit(
        None, Point(m_chi=10, m_med=100), Module(), 0.5, PhysicalFitRange(low=0, high=1)
    )
    assert not result.resolved and "verification" in result.reason
    assert result.evaluations == sum(seen.values())


def test_range_schema_and_original_sign_defaults():
    assert PhysicalFitRange.perturbative_branch(-1).low == -math.sqrt(4 * math.pi)
    assert PhysicalFitRange.perturbative_branch(0).low == 0
    for data in [
        dict(low=1, high=0),
        dict(low=0, high=float("inf")),
        dict(low=0, high=1, parameter="m_med"),
    ]:
        with pytest.raises(ValueError):
            PhysicalFitRange(**data)


def test_real_detector_likelihood_matches_independent_count_and_profile():
    from adroit.experiments import registry
    from adroit.inference import signal_fit
    from adroit.orchestrator import single_idea as idea

    cls, p = Spin1Class(), Point(m_chi=10, m_med=1000, g_chi=0.001, g_q=0.25)
    module = registry.load_module("CDMS II Si (2013)")
    trial = pf.predict(cls, p, module, 0.5)
    signal = idea.path2._signal(module, idea._candidate(cls, p, 0.5))
    events, resolution = module.observations()
    density = signal_fit.event_densities(
        module.signal_grid_kev(), signal.density, events, resolution
    )
    # the count seen inside the window (the audit's A09): the window's count times the share not smeared out of it
    seen = signal.total_events * signal_fit.seen_fraction(module.signal_grid_kev(), signal.density, resolution)
    assert 0.9 * signal.total_events < seen < signal.total_events
    expected = signal_fit.profile_log_likelihood(
        seen, density, module.background_at(events), module.background_rate()
    )[0]
    assert trial.signal_events == pytest.approx(seen, rel=1e-12) and trial.log_l == pytest.approx(expected, rel=1e-12)
    with pytest.raises(ValueError, match="perturbative"):
        pf.predict(cls, p.model_copy(update={"g_chi": 4.0}), module, 0.5)

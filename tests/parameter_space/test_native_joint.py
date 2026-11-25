"""Physical coherence, bounded-domain calibration and honest missing coverage."""

import numpy as np
import pytest

from adroit.core.model_spec import PhysicalFitRange
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.physical_fit import FitSettings
from adroit.parameter_space import native_joint as joint
from adroit.statistics.native_pair import EventData, event_profile, zero_count_log_l
from adroit.experiments import registry


def template(mass=60.0, null_count=2.0):
    return joint.PairTemplate(
        point=Point(m_chi=mass, m_med=125, g_chi=1, g_q=0.25),
        bounds=PhysicalFitRange(low=0, high=1),
        signal_count=3.0,
        signal_grid=[0.0, 1.0],
        signal_density=[3.0, 3.0],
        null_count=null_count,
        null_relative_uncertainty=0.1,
        resolution_kev=0.0,
        scaling_verified_relative_error=0.0,
    )


def data():
    return EventData(
        energies=[0.2, 0.7],
        background_at_events=[0.4, 0.4],
        background_total=0.4,
        sigma_minus=0.3,
        sigma_plus=0.6,
    )


class Module:
    def signal_grid_kev(self):
        return np.array([0.0, 1.0])

    def background_on_grid(self):
        return np.array([0.4, 0.4])

    def background_at(self, events):
        return np.full(len(events), 0.4)


def test_native_pair_has_one_shared_coupling_and_matches_independent_dense_scan():
    t, d = template(), data()
    result = joint.fit_pair(t, d, FitSettings())

    def value(g):
        return event_profile(3 * g * g, np.ones(2), d).log_l + zero_count_log_l(2 * g * g, 0.1)

    grid = np.linspace(0, 1, 10001)
    dense = grid[np.argmax([value(g) for g in grid])]
    assert result.resolved and result.identifiable, result.reason
    assert result.point.g_chi == pytest.approx(dense, abs=0.0002)
    assert result.log_l == pytest.approx(value(result.point.g_chi), abs=1e-8)
    alone = joint.fit_pair(template(null_count=0.0), d, FitSettings())
    assert result.point.g_chi < alone.point.g_chi


def test_calibration_repeats_exact_domain_has_seed_and_finite_tail_resolution():
    templates = [template(), template(70, 1.0)]
    d = data()
    settings = joint.JointSettings(toys=30, seed=17, max_toy_fits=100)
    observed = max(joint.fit_pair(t, d, FitSettings()).q0 for t in templates)
    a = joint._calibrate(templates, d, Module(), observed, settings, FitSettings())
    b = joint._calibrate(templates, d, Module(), observed, settings, FitSettings())
    assert a.complete and a.toys_completed == 30 and a.toy_fits == 60, a.reason
    assert a == b and 1 / 31 <= a.p_mc <= 1 and np.isfinite(a.z_mc)
    assert a.p_interval_95[0] <= a.p_interval_95[1]
    limited = joint._calibrate(
        templates,
        d,
        Module(),
        observed,
        settings.model_copy(update={"max_toy_fits": 3}),
        FitSettings(),
    )
    assert not limited.complete and limited.p_mc is None and limited.toy_fits == 3
    assert "budget" in limited.reason


def test_joint_request_does_not_trim_ineligible_masses_or_guess_likelihoods():
    cls, p = Spin1Class(), Point(m_chi=10, m_med=125, g_chi=0.001, g_q=0.25)
    bounds = PhysicalFitRange(low=0, high=0.02)
    missing = joint.run(cls, p, [10.0], bounds, joint.JointSettings(toys=3), FitSettings(), 0.5)
    assert not missing.complete and missing.calibration is None and "10.0" in missing.omitted
    assert missing.bounds == bounds and missing.reference_point == p
    unknown = joint.run(
        cls,
        p,
        [60.0],
        bounds,
        joint.JointSettings(null_experiment="CDMSlite Run 2"),
        FitSettings(),
        0.5,
    )
    assert not unknown.complete and "no native" in unknown.omitted["CDMSlite Run 2"]


def test_real_pair_preparation_preserves_both_coupling_sign_branches():
    signal, null = registry.load_module(joint.SIGNAL), registry.load_module(joint.NULL)
    observed = joint.observed_data(signal)
    assert observed.energies == [8.2, 9.5, 12.3]
    p = Point(m_chi=50, m_med=125.09, g_chi=0.001, g_q=0.25)
    positive = joint.prepare(Spin1Class(), p, PhysicalFitRange(low=0, high=0.02), signal, null, 0.5)
    negative = joint.prepare(
        Spin1Class(), p, PhysicalFitRange(low=-0.02, high=0), signal, null, 0.5
    )
    assert positive.signal_count > 0 and positive.null_count > 0
    assert positive.scaling_verified_relative_error < 1e-8
    assert positive.signal_count == negative.signal_count
    assert positive.null_count == negative.null_count
    with pytest.raises(ValueError, match="one coupling-sign"):
        joint.prepare(Spin1Class(), p, PhysicalFitRange(low=-0.02, high=0.02), signal, null, 0.5)


def test_failed_toy_attempt_is_counted_and_never_produces_a_tail(monkeypatch):
    def fail(*args):
        raise ValueError("unavailable physical prediction")

    monkeypatch.setattr(joint, "fit_pair", fail)
    result = joint._calibrate(
        [template()], data(), Module(), 1.0, joint.JointSettings(toys=3), FitSettings()
    )
    assert result.toy_fits == 1 and result.toys_completed == 0
    assert not result.complete and result.p_mc is None and "unavailable" in result.reason


@pytest.mark.slow
def test_calibrated_tail_matches_independent_exact_poisson_case():
    from scipy.stats import poisson

    # Nearly known background, constant signal shape, no sensitivity uncertainty.
    # One coupling produces 3g² signal events and 2g² null events. With n_null=0,
    # q0 grows monotonically with n_signal; observing 2 has tail P(Pois(.4)>=2).
    d = data().model_copy(update={"sigma_minus": 1e-7, "sigma_plus": 1e-7})
    t = template().model_copy(update={"null_relative_uncertainty": 0.0})
    observed = joint.fit_pair(t, d, FitSettings()).q0
    result = joint._calibrate(
        [t],
        d,
        Module(),
        observed,
        joint.JointSettings(toys=2000, seed=123, max_toy_fits=2000),
        FitSettings(),
    )
    assert result.complete, result.reason
    exact = float(poisson.sf(1, 0.4))
    assert result.p_interval_95[0] < exact < result.p_interval_95[1]
    assert result.p_mc == pytest.approx(exact, abs=0.015)

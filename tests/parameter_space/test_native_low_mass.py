"""Low-mass source response, exact coherent count fits and nested nuisance checks."""

import numpy as np
import pytest
import yaml

from adroit.core.model_spec import PhysicalFitRange
from adroit.experiments import registry, native_validation
from adroit.parameter_space import native_joint as joint
from adroit.parameter_space.native_toys import NativeObservation, pico_maximum
from adroit.parameter_space.native_coverage import study, CoverageSettings, NuisanceScenario
from adroit.parameter_space.physical_fit import FitSettings
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.statistics.native_pair import EventData, binned_free_background_log_l


def template():
    return joint.PairTemplate(
        point=Point(m_chi=8.6, m_med=125, g_chi=1, g_q=0.25),
        bounds=PhysicalFitRange(low=0, high=1),
        signal_count=3,
        signal_grid=[0, 1],
        signal_density=[3, 3],
        null_count=3,
        null_relative_uncertainty=0,
        resolution_kev=0,
        scaling_verified_relative_error=0,
        null_experiment=joint.LOW_MASS_NULL,
        null_counts=[2, 1],
        null_observed=[3, 0],
    )


def data(count=2, auxiliary=1.0):
    return EventData(
        energies=[0.2] * count,
        background_at_events=[0.4] * count,
        background_total=0.4,
        sigma_minus=0.3,
        sigma_plus=0.6,
        auxiliary=auxiliary,
    )


class Module:
    def signal_grid_kev(self):
        return np.array([0.0, 1.0])

    def background_on_grid(self):
        return np.array([0.4, 0.4])

    def background_at(self, events):
        return np.full(len(events), 0.4)


@pytest.mark.parametrize(
    "count,auxiliary,null",
    [
        (0, -1, [0, 0]),
        (1, 1, [3, 0]),
        (2, 1, [3, 2]),
        (4, 1, [3, 2]),
        (10, 1, [30, 30]),
        (2, -1, [1, 1]),
        (3, 3, [0, 0]),
    ],
)
def test_concave_maximum_matches_full_bounded_physical_solver(count, auxiliary, null):
    t, d = template(), data(count, auxiliary)
    fast = pico_maximum(t, NativeObservation(signal=d, null_counts=null), FitSettings())
    full = joint.fit_pair(t, d, FitSettings(), null_observed=null)
    assert full.resolved and full.identifiable, full.reason
    assert fast.q0 == pytest.approx(full.q0, abs=1e-6)
    assert fast.log_l == pytest.approx(full.log_l, abs=1e-6)
    assert fast.factor == pytest.approx(full.point.g_chi**2, abs=1e-6)
    assert fast.evaluations <= FitSettings().max_evaluations


def test_low_mass_template_has_source_counts_and_honest_native_only_envelope(tmp_path):
    si, pico = registry.load_module(joint.SIGNAL), registry.load_module(joint.LOW_MASS_NULL)
    assert pico.validated_range("SI") is None
    assert native_validation.certified_range(pico.name) == (4.0, 80.0)
    t = joint.prepare(
        Spin1Class(),
        Point(m_chi=8.6, m_med=125, g_chi=0.001, g_q=0.25),
        PhysicalFitRange(low=0, high=0.02),
        si,
        pico,
        0.5,
    )
    assert t.null_observed == [3, 0] and len(t.null_counts) == 2 and min(t.null_counts) > 0
    assert t.scaling_verified_relative_error < 1e-8
    content = yaml.safe_load(native_validation.CERTIFICATE.read_text())
    content["response_hashes"]["adroit/physics/rates.py"] = "0" * 64
    path = tmp_path / "changed.yaml"
    path.write_text(yaml.safe_dump(content))
    assert native_validation.certified_range(pico.name, path) is None
    with pytest.raises(ValueError, match="validated native SI"):
        joint.prepare(
            Spin1Class(), t.point.model_copy(update={"m_chi": 3.0}), t.bounds, si, pico, 0.5
        )


def test_count_likelihood_matches_pico_native_profile_and_never_double_profiles():
    from adroit.experiments.pico60 import Pico60
    from adroit.core.dm_state import ExpectedSignal, DarkMatterParticle

    signal = ExpectedSignal(
        experiment=joint.LOW_MASS_NULL,
        interaction_id="test",
        particle=DarkMatterParticle(mass_gev=8.6),
        total_events=5,
        observable=[0, 1],
        density=[3, 2],
    )
    native = Pico60.profiled_nll(signal)
    assert binned_free_background_log_l([3, 0], [1.5, 1.0]) == pytest.approx(
        -native(0.5) + native(0)
    )
    assert binned_free_background_log_l([3, 0], [0, 0]) == 0
    with pytest.raises(ValueError):
        binned_free_background_log_l([3, -1], [1, 1])


def test_maximum_remains_correct_for_an_enormous_reference_count():
    t = template()
    # Both reference domains contain the unconstrained maximum: total N=4<6.
    observed = NativeObservation(signal=data(4), null_counts=[0, 0])
    expected = pico_maximum(t, observed, FitSettings())
    large = t.model_copy(update={"signal_count": 3e20, "null_counts": [2e20, 1e20]})
    actual = pico_maximum(large, observed, FitSettings())
    assert actual.q0 == pytest.approx(expected.q0, abs=1e-9)
    assert actual.factor * 1e20 == pytest.approx(expected.factor, rel=1e-9)


def test_nested_coverage_recalibrates_each_outer_dataset_and_refuses_partial_counts():
    settings = CoverageSettings(outer_trials=12, inner_toys=19, max_fits=1000, seed=17)
    scenarios = [NuisanceScenario(theta=0, null_backgrounds=[0, 0])]
    result = study([template()], data(), Module(), scenarios, settings)
    assert result.complete and result.fits == 12 * 20
    assert result.cases[0].trials == 12 and len(result.cases[0].p_values) == 12
    assert result.cases[0].rejections == 0
    assert "not uniform" in result.construction
    partial = study(
        [template()], data(), Module(), scenarios, settings.model_copy(update={"max_fits": 10})
    )
    assert (
        not partial.complete
        and partial.cases[0].fraction is None
        and "budget" in partial.cases[0].reason
    )
    assert result == study([template()], data(), Module(), scenarios, settings)

"""R6 (audit M5 and the Monte Carlo minor): the toys draw the auxiliary measurement from the likelihood's own
density, fits start from a positive θ, failed toys raise, and every global p carries its binomial interval."""

import json
import math
import re
from pathlib import Path

import numpy as np
import pytest

from adroit.inference import look_elsewhere, nuisance
from adroit.inference.nuisance import BackgroundRate

ROOT = Path(__file__).resolve().parents[2]


def test_the_toy_measurement_falls_below_theta_with_probability_sigma_plus_share() -> None:
    rate = BackgroundRate(total=0.41, minus=0.62, plus=0.84)
    rng = np.random.default_rng(1)
    draws = np.array([nuisance.toy_centre(1.85, rate, rng) for _ in range(40_000)])
    below = np.mean(draws < 1.85)
    assert below == pytest.approx(0.84 / (0.84 + 0.62), abs=0.01)          # not ½
    assert (draws <= 0).any()                                              # no clip at 1e-3


def test_a_non_positive_measurement_still_gives_a_positive_finite_fit() -> None:
    rate = BackgroundRate(total=2.0, minus=0.6, plus=0.8, centre=-0.3)
    theta, value = nuisance.null_fit(np.array([0.5, 1.0]), rate)
    assert theta > 0 and math.isfinite(value)


def test_a_failed_toy_raises_instead_of_scoring_zero(monkeypatch) -> None:
    from adroit.inference import signal_fit
    monkeypatch.setattr(signal_fit, "best_fits", lambda f, b, rate=None: (None, np.array([np.nan])))
    with pytest.raises(ArithmeticError):
        look_elsewhere.max_significance(np.ones((1, 3)), np.array([1.0, 2.0, 3.0]), np.array([2.0]), np.ones(3))


def test_the_clopper_pearson_interval_and_the_three_over_n_bound() -> None:
    low, high = look_elsewhere.p_interval(52, 20_000)
    assert low < 52 / 20_000 < high and low == pytest.approx(1.94e-3, rel=0.02) and high == pytest.approx(3.41e-3, rel=0.02)
    assert look_elsewhere.p_interval(0, 200_000)[1] == pytest.approx(3 / 200_000, rel=0.01)
    assert look_elsewhere.p_to_z(look_elsewhere.p_interval(0, 200_000)[1]) == pytest.approx(4.17, abs=0.01)


@pytest.mark.slow
def test_independent_toys_reproduce_the_corrected_cdms_si_p() -> None:
    """The audit's likelihood-consistent draw gave p = 2.58e-3 (100,000 toys); the old draw 1.42e-3."""
    from adroit.experiments import registry as modules
    from adroit.orchestrator import single_idea, user_models
    from adroit.core.model_spec import ModelSpec
    stored = json.loads((ROOT / "docs/dm14/single_idea_vector_cdms_si/result.json").read_text())["request"]
    module = modules.load_module(stored["experiment"])
    candidates = user_models.candidates(ModelSpec.model_validate(stored["spec"]), stored["masses_gev"], None)
    _, _, _, method, interval = single_idea._fit_masses(module, candidates, 20_000)
    low, high = map(float, re.search(r"95% interval ([0-9.e-]+)–([0-9.e-]+)", method).groups())
    assert low <= 2.58e-3 <= high and not low <= 1.42e-3 <= high, method

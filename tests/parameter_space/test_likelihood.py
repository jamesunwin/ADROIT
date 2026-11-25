"""The combined-likelihood mode (parameter_space.likelihood, and the verdict's likelihood mode)."""

import math

import pytest

from adroit.parameter_space import likelihood as lk
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.scan import PointResult
from adroit.parameter_space.verdict import classify

V1 = Spin1Class(name="V1")


def _point(ratios, chi2=None, excluded=None):
    names = {**{k: v > 1 for k, v in ratios.items()}, **(excluded or {})}
    return PointResult(point=Point(m_chi=500.0, m_med=3000.0), omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=1e-48,
                       dd_limit_cm2=1e-47, excluded={"colliders (CMS)": False, "perturbativity": False, **names},
                       ratios=ratios, chi2=chi2 or {})


def test_one_limit_at_its_boundary_gives_the_one_sided_95_percent_value():
    assert lk.contribution(1.0) == pytest.approx(lk.Q_95)
    assert lk.combined_ratio(lk.combined({"a": 0.6, "b": 0.8}, {})) == pytest.approx(1.0)


def test_a_theory_uncertainty_weakens_a_limit():
    assert lk.contribution(1.2, 0.3) < lk.contribution(1.2) and lk.contribution(1.2, 0.0) > lk.Q_95


def test_two_constraints_each_allowed_can_exclude_together():
    r = _point({"direct detection": 0.8, "gamma rays (Fermi-LAT dwarfs)": 0.8})
    assert classify(V1, r).status != "excluded"
    combined = classify(V1, r, lk.LikelihoodSettings())
    assert combined.status == "excluded" and combined.r_combined == pytest.approx(math.sqrt(1.28))
    assert classify(V1, r, lk.LikelihoodSettings(prediction_theory=1.0)).status != "excluded"


def test_a_measurement_adds_its_delta_chi2_and_a_cut_stays_a_cut():
    better = _point({"direct detection": 0.9}, chi2={"muon g−2": -0.5})
    assert classify(V1, better, lk.LikelihoodSettings()).status != "excluded"
    cut = _point({"direct detection": 0.1}, excluded={"colliders (CMS)": True})
    assert "colliders (CMS)" in classify(V1, cut, lk.LikelihoodSettings()).excluded_by


def test_the_relic_band_widens_with_the_theory_uncertainty():
    settings = lk.LikelihoodSettings(relic_theory=0.1)
    assert lk.relic_chi2(0.12, 0.12, settings) == 0.0
    assert lk.relic_chi2(0.14, 0.12, settings) < lk.BAND_95 < lk.relic_chi2(0.16, 0.12, settings)
    assert lk.relic_chi2(0.125, 0.12, lk.LikelihoodSettings(relic_theory=0.0)) > lk.BAND_95
    assert lk.relic_chi2(None, 0.12, settings) == math.inf


def test_a_large_theory_uncertainty_no_longer_hides_a_large_excess():
    """Audit M12: the Gaussian nuisance saturated at q → 1/δ² < 2.71 for δ ≥ 0.61; the log-normal one grows as
    (ln r)², so r = 1000 at δ = 0.7 excludes."""
    assert lk.contribution(1000.0, 0.7) == pytest.approx(143.928, rel=1e-4) and lk.contribution(1000.0, 0.7) > lk.Q_95
    r = _point({"direct detection": 1000.0})
    assert classify(V1, r, lk.LikelihoodSettings(prediction_theory=0.7)).status == "excluded"


@pytest.mark.parametrize("ratio,theory", [(0.5, 0.2), (1.0, 0.3), (5.0, 0.7), (40.0, 1.0)])
def test_the_closed_form_is_the_profiled_minimum(ratio, theory):
    import numpy as np
    x, kappa = 1.645 * ratio, math.log1p(theory)
    theta = np.linspace(-30.0, 5.0, 1_000_001)
    assert lk.contribution(ratio, theory) == pytest.approx((x * x * np.exp(2 * kappa * theta) + theta ** 2).min(),
                                                           rel=1e-6)


def test_a_small_theory_uncertainty_approaches_the_gaussian_result():
    x2 = (1.645 * 0.5) ** 2
    assert lk.contribution(0.5, 1e-4) == pytest.approx(x2, rel=1e-6)
    with pytest.raises(ValueError):
        lk.contribution(1.0, -0.1)


def test_the_headline_labels_theory_band_points_as_unrooted():
    from adroit.parameter_space.verdict import Crossing, _counts_text
    root = Crossing(point=Point(m_chi=1.0, m_med=2.0), status="pending", kind="contour")
    band = Crossing(point=Point(m_chi=1.0, m_med=2.0), status="viable", kind="theory_band")
    text = _counts_text([root, band], "viable")
    assert "(0 viable, 1 pending, 0 excluded on the relic contour; theory band, unrooted: 1 viable" in text
    assert "rests on theory-band points only" in text
    assert _counts_text([root], "viable_pending") == " (0 viable, 1 pending, 0 excluded)"

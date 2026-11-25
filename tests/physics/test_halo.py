"""Velocity distributions and their integrals."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad

from adroit.core.dm_state import HaloKind, HaloModel
from adroit.physics import halo as halos

SHM = HaloModel()


def _numerical(v_min: float, weight) -> float:
    """∫_{v_min} f(v) weight(v) dv by quadrature, split at the kink of the truncation."""
    kink = SHM.v_esc_km_s - SHM.v_lab_km_s
    top = halos.max_speed_km_s(SHM)

    def integrand(v: float) -> float:
        return float(halos.speed_distribution(np.array([v]), SHM)[0]) * weight(v)

    pieces = [(v_min, kink), (kink, top)] if v_min < kink else [(v_min, top)]
    return sum(quad(integrand, a, b, limit=200, epsabs=0.0, epsrel=1e-12)[0] for a, b in pieces)


def test_the_earth_velocity_on_9_march_is_the_recommended_average() -> None:
    # arXiv:2105.00599, Eq. 12: v(March 9) = (29.2, -0.1, 5.9) km/s; 9 March is day 67.
    assert halos.earth_velocity_km_s(67.0) == pytest.approx((29.2, -0.1, 5.9), abs=0.06)


def test_the_detector_speed_of_the_standard_halo() -> None:
    assert SHM.v_lab_km_s == pytest.approx(253.67, abs=0.01)
    assert halos.max_speed_km_s(SHM) == pytest.approx(544.0 + 253.67, abs=0.01)


def test_the_speed_distribution_is_normalised() -> None:
    assert _numerical(0.0, lambda v: 1.0) == pytest.approx(1.0, rel=1e-10)


@pytest.mark.parametrize("v_min", [0.0, 150.0, 290.0, 500.0, 700.0, 790.0])
def test_the_closed_forms_match_numerical_integration(v_min: float) -> None:
    eta, eta_perp = halos.velocity_integrals(np.array([v_min]), SHM)
    assert eta[0] == pytest.approx(_numerical(v_min, lambda v: 1.0 / v if v > 0 else 0.0),
                                   rel=1e-8)
    assert eta_perp[0] == pytest.approx(
        _numerical(v_min, lambda v: (v * v - v_min ** 2) / v if v > 0 else 0.0), rel=1e-8)


def test_the_integrals_fall_to_zero_at_the_fastest_particle() -> None:
    v = np.linspace(0.0, 900.0, 400)
    eta, eta_perp = halos.velocity_integrals(v, SHM)
    assert np.all(np.diff(eta) <= 1e-15) and np.all(np.diff(eta_perp) <= 1e-12)
    beyond = v >= halos.max_speed_km_s(SHM)
    assert np.all(eta[beyond] == 0.0) and np.all(eta_perp[beyond] == 0.0)


def test_a_tabulated_halo_reproduces_the_standard_one() -> None:
    table = halos.tabulate(SHM, points=4000)
    assert table.kind is HaloKind.tabulated
    v = np.array([0.0, 50.0, 250.0, 450.0, 650.0, 760.0])
    exact, exact_perp = halos.velocity_integrals(v, SHM)
    approx, approx_perp = halos.velocity_integrals(v, table)
    assert approx == pytest.approx(exact, rel=1e-4)
    assert approx_perp == pytest.approx(exact_perp, rel=1e-4)


def test_a_tabulated_halo_is_normalised_and_must_vanish_at_rest() -> None:
    doubled = HaloModel(kind=HaloKind.tabulated, speeds_km_s=[0.0, 300.0, 600.0],
                        speed_density=[0.0, 2.0, 0.0])
    # a triangle of unit area once normalised: f = v/300² rising, then falling
    assert halos.speed_distribution(np.array([300.0]), doubled)[0] == pytest.approx(1 / 300.0)
    bad = HaloModel(kind=HaloKind.tabulated, speeds_km_s=[0.0, 300.0], speed_density=[1.0, 1.0])
    with pytest.raises(ValueError, match="vanish"):
        halos.velocity_integrals(np.array([10.0]), bad)


def test_a_tabulated_halo_has_no_annual_modulation() -> None:
    with pytest.raises(ValueError, match="no time dependence"):
        halos.halo_on_day(halos.tabulate(SHM, points=50), 100.0)


def test_the_standard_halo_moves_with_the_earth() -> None:
    june, december = halos.halo_on_day(SHM, 152.0), halos.halo_on_day(SHM, 335.0)
    assert june.v_lab_km_s > SHM.v_lab_km_s > december.v_lab_km_s


def test_a_detector_faster_than_the_escape_speed_is_rejected() -> None:
    with pytest.raises(ValueError, match="escape speed"):
        halos.velocity_integrals(np.array([10.0]), HaloModel(v_esc_km_s=200.0))
    with pytest.raises(ValueError, match="negative"):
        halos.velocity_integrals(np.array([-1.0]), SHM)

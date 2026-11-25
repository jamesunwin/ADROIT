"""The zero-temperature decay of a metastable vacuum (theory.vacuum_decay): the one-field bounce against
Coleman's thin wall, the two-field path deformation against exact and independent results, the rigorous
bounds, and the vacuum certificate's use of the lifetime."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq, minimize

from adroit.core.theory import ScalarVacuumInput
from adroit.theory import vacuum_decay as vd
from adroit.theory.scalar_vacuum import certify

V_EW, M_H = 246.22, 125.09


def tilted(lam: float = 1.0, a: float = 1.0, eps: float = 0.05):
    """λ/8 (φ² − a²)² + ε/2a (φ + a): true vacuum near −a, false near +a, split by ε; wall tension 2√λ a³/3."""
    def u(f):
        return lam / 8 * (f**2 - a**2) ** 2 + eps / (2 * a) * (f + a)

    def du(f):
        return lam / 2 * f * (f**2 - a**2) + eps / (2 * a)
    return u, du, brentq(du, -1.5 * a, -0.5 * a), brentq(du, 0.5 * a, 1.5 * a)


def one_field(eps: float) -> tuple[vd.Profile, float]:
    u, du, true, false = tilted(eps=eps)
    xs = np.linspace(0.0, false - true, vd.SAMPLES)
    profile = vd.bounce(CubicSpline(xs, u(true + xs)), CubicSpline(xs, du(true + xs)), false - true)
    return profile, u(false) - u(true)


@pytest.mark.parametrize("eps,tolerance", [(0.05, 0.03), (0.02, 0.005)])
def test_the_one_field_bounce_approaches_colemans_thin_wall(eps: float, tolerance: float) -> None:
    profile, split = one_field(eps)
    tension = 2 / 3
    assert profile.action == pytest.approx(vd.thin_wall_action(tension, split), rel=tolerance)
    assert profile.radius == pytest.approx(3 * tension / split, rel=tolerance)
    assert profile.direct == pytest.approx(profile.action, rel=1e-3)              # Derrick's identity


def test_the_thin_wall_overestimates_a_thicker_wall() -> None:
    profile, split = one_field(0.2)
    assert profile.action < vd.thin_wall_action(2 / 3, split)


class Rotated:
    """A tilted double well along the unit vector n, with mass² M² across it: the bounce path is straight."""

    def __init__(self, angle: float, eps: float = 0.3, mass2: float = 2.0) -> None:
        self.n = np.array([math.cos(angle), math.sin(angle)])
        self.m = np.array([-math.sin(angle), math.cos(angle)])
        self.u, self.du, self.true, self.false = tilted(eps=eps)
        self.mass2 = mass2

    def value(self, phi: np.ndarray) -> np.ndarray:
        return self.u(phi @ self.n) + self.mass2 * (phi @ self.m) ** 2 / 2

    def gradient(self, phi: np.ndarray) -> np.ndarray:
        return self.du(phi @ self.n)[..., None] * self.n + self.mass2 * (phi @ self.m)[..., None] * self.m


def test_deformation_keeps_an_exactly_straight_bounce_and_its_action() -> None:
    field = Rotated(0.7)
    xs = np.linspace(0.0, field.false - field.true, vd.SAMPLES)
    exact = vd.bounce(CubicSpline(xs, field.u(field.true + xs)), CubicSpline(xs, field.du(field.true + xs)),
                      field.false - field.true).action
    best, path, converged, _ = vd.deform(field, field.true * field.n, field.false * field.n)
    assert converged and best.action == pytest.approx(exact, rel=1e-3)
    assert np.max(np.abs(path @ field.m)) < 1e-6
    assert vd.envelope_bound(field, field.true * field.n, field.false * field.n).action <= exact * (1 + 1e-6)


def higgs_singlet(m_s: float, lambda_s: float = 0.2, lambda_hs: float = 0.5) -> tuple[ScalarVacuumInput, float]:
    """The Higgs portal with its singlet's mass m_S at the electroweak vacuum; w the singlet-axis vev."""
    mu_s2 = m_s**2 - lambda_hs * V_EW**2 / 2
    inputs = ScalarVacuumInput(scale_gev=V_EW, v_gev=V_EW, mu_h2_gev2=M_H**2 / 2, mu_s2_gev2=mu_s2,
                               lambda_h=M_H**2 / (2 * V_EW**2), lambda_s=lambda_s, lambda_hs=lambda_hs)
    return inputs, math.sqrt(-mu_s2 / lambda_s)


def scaled(inputs: ScalarVacuumInput, w: float) -> tuple[vd.Field, np.ndarray, np.ndarray]:
    scale = max(inputs.v_gev, w)
    field = vd.Field(inputs.mu_h2_gev2 / scale**2, inputs.mu_s2_gev2 / scale**2, inputs.lambda_h,
                     inputs.lambda_s, inputs.lambda_hs)
    return field, np.array([0.0, w / scale]), np.array([inputs.v_gev / scale, 0.0])


def test_a_light_singlet_with_a_strong_portal_decays_fast_by_the_upper_bound_alone() -> None:
    inputs, w = higgs_singlet(8.0, lambda_hs=2.0)
    found = vd.decay(inputs, "singlet_axis", (0.0, w))
    assert found.status == "short_lived" and "upper bound" in found.decided_by
    assert found.bounce_action < 50 and found.log_probability > 10


def test_a_heavier_singlet_outlives_the_universe_by_the_lower_bound_alone() -> None:
    inputs, w = higgs_singlet(40.0)
    found = vd.decay(inputs, "singlet_axis", (0.0, w))
    assert found.status == "long_lived" and "lower bound" in found.decided_by
    assert found.action_lower_bound <= found.action_upper_bound and found.log_probability < -10


def test_the_certificate_passes_a_metastable_vacuum_and_fails_a_short_lived_one() -> None:
    from adroit.parameter_space.verdict import theory_status
    from types import SimpleNamespace
    long_lived = certify(higgs_singlet(40.0)[0])
    assert long_lived.vacuum == "metastable" and long_lived.complete and long_lived.passed is True
    assert long_lived.minima == ["singlet_axis"] and long_lived.decay.status == "long_lived"
    short = certify(higgs_singlet(8.0, lambda_hs=2.0)[0])
    assert short.vacuum == "short_lived" and short.complete and short.passed is False
    row = SimpleNamespace(vacuum_certificate=short, unitarity_certificate=None, running_certificate=None)
    excluded, pending = theory_status(row)
    assert excluded and "short_lived" in excluded[0] and not pending
    assert theory_status(SimpleNamespace(vacuum_certificate=long_lived, unitarity_certificate=None,
                                         running_certificate=None)) == ([], [])


def test_a_metastable_point_is_flagged_in_its_verdict() -> None:
    from types import SimpleNamespace
    from adroit.parameter_space.verdict import metastable_flag
    row = SimpleNamespace(vacuum_certificate=certify(higgs_singlet(40.0)[0]))
    assert "metastable" in metastable_flag(row)[0]
    assert metastable_flag(SimpleNamespace(vacuum_certificate=None)) == []


def test_ln_p_falls_with_the_action_and_crosses_zero_near_four_hundred() -> None:
    radius = 1 / 100.0
    assert vd.log_probability(300.0, radius) > 0 > vd.log_probability(500.0, radius)
    assert 380 < brentq(lambda s: vd.log_probability(s, radius), 300.0, 500.0) < 430


@pytest.mark.slow
@pytest.mark.parametrize("m_s,status", [(12.0, "short_lived"), (25.0, "unresolved"), (30.0, "long_lived")])
def test_near_the_threshold_the_deformed_bounce_lies_between_the_bounds(m_s: float, status: str) -> None:
    inputs, w = higgs_singlet(m_s)
    field, true, false = scaled(inputs, w)
    best, _, converged, _ = vd.deform(field, true, false)
    lower = vd.envelope_bound(field, true, false).action
    straight = vd._normal_force(field, vd.SmoothPath(true, false, np.zeros((1, 2))), np.array([0.5]))[0].action
    assert converged and lower <= best.action <= straight
    assert abs(best.direct - best.action) / best.action < 1e-3
    assert vd.decay(inputs, "singlet_axis", (0.0, w)).status == status


@pytest.mark.slow
def test_no_quadratic_path_beats_the_deformed_bounce() -> None:
    """An independent minimisation: the one-field action over paths with one quadratic control point."""
    inputs, w = higgs_singlet(30.0)
    field, true, false = scaled(inputs, w)
    best = vd.deform(field, true, false)[0].action

    def along(control: np.ndarray) -> float:
        t = np.linspace(0.0, 1.0, vd.SAMPLES)[:, None]
        phi = (1 - t) ** 2 * true + 2 * t * (1 - t) * control + t**2 * false
        d1 = 2 * (1 - t) * (control - true) + 2 * t * (false - control)
        speed = np.linalg.norm(d1, axis=1)
        s = np.r_[0.0, np.cumsum((speed[1:] + speed[:-1]) / 2 / (vd.SAMPLES - 1))]
        du = np.sum(field.gradient(phi) * d1, axis=1) / speed
        try:
            return vd.bounce(CubicSpline(s, field.value(phi)), CubicSpline(s, du), float(s[-1])).action
        except (ArithmeticError, ValueError):
            return math.inf

    found = minimize(along, (true + false) / 2, method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-3})
    assert best <= found.fun * (1 + 1e-2)
    assert found.fun < 1.2 * best

"""Zero-temperature decay of a metastable electroweak vacuum: the O(4) bounce, by path deformation.

Fields φ = (h, s), with H = (0, h/√2) and a canonically normalised real singlet S = s:

    V(h, s) = −μ_H² h²/2 + μ_S² s²/2 + λ_H h⁴/4 + λ_HS h² s²/4 + λ_S s⁴/4,

the vacuum certificate's V(x, y) with x = h²/2, y = s²/2. The false vacuum is the declared (v, 0); the true
vacuum is the certificate's deepest minimum.

**The bounce** (Coleman 1977; Callan & Coleman 1977) solves φ'' + (3/ρ) φ' = ∇V with φ'(0) = 0 and φ(∞) at
the false vacuum. Its Euclidean action is S_E = 2π² ∫ ρ³ [½|φ'|² + V(φ) − V_false] dρ, which for an exact
bounce equals (π²/2) ∫ ρ³ |φ'|² dρ (Derrick's scaling identity); the two are compared as a check.

**Two fields.** The bounce runs along a path in field space. Along a fixed path the profile x(ρ) solves the
one-field problem for V restricted to the path (overshoot/undershoot shooting); the path is then moved by the
force normal to it, ∇_⊥V − x'² φ_xx, until that force vanishes (Wainwright, CosmoTransitions,
arXiv:1109.4189). The bounce is the mountain pass of the action, so the one-field action along *any* path is an
upper bound on S_E: the smallest action found bounds S_E from above even if the deformation stalls.

**The lifetime.** Γ/V ≈ (S_E/2π)² R⁻⁴ e^{−S_E}, with R the bounce radius (the fluctuation determinant is not
computed). The vacuum survives if the probability of a bubble in our past light cone, P ≈ (Γ/V) t_U⁴, is
small: ln P < −margin is long-lived, ln P > +margin short-lived, and between them unresolved. The margin
absorbs the prefactor. Thermal history (which vacuum the early universe chose) is not addressed.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq
from scipy.special import ive

from adroit.core.theory import ScalarVacuumInput, VacuumDecay

T_UNIVERSE_GEV_INV = 13.787e9 * 3.15576e7 / 6.582119569e-25     # 13.787 Gyr in ħ/GeV
POINTS = 41                                                      # nodes on the field-space path
SAMPLES = 801                                                    # samples of V along the path
START = 1e-3                                                     # leave the linear regime at x = START·L
STATIONARY = 1e-5          # a deformation step this small that still raises S_E: the action is at its minimum


class Field(NamedTuple):
    """The potential in units of a field scale Φ (fields/Φ, V/Φ⁴): S_E is invariant under the rescaling."""

    mu_h2: float
    mu_s2: float
    lambda_h: float
    lambda_s: float
    lambda_hs: float

    def value(self, phi: np.ndarray) -> np.ndarray:
        """V(h, s) at the field points ``phi``, whose last axis is (h, s)."""
        h, s = phi[..., 0], phi[..., 1]
        return (-self.mu_h2 * h**2 / 2 + self.mu_s2 * s**2 / 2 + self.lambda_h * h**4 / 4
                + self.lambda_hs * h**2 * s**2 / 4 + self.lambda_s * s**4 / 4)

    def gradient(self, phi: np.ndarray) -> np.ndarray:
        """∇V = (∂V/∂h, ∂V/∂s) at the field points ``phi``, along the last axis."""
        h, s = phi[..., 0], phi[..., 1]
        return np.stack([-self.mu_h2 * h + self.lambda_h * h**3 + self.lambda_hs * h * s**2 / 2,
                         self.mu_s2 * s + self.lambda_s * s**3 + self.lambda_hs * h**2 * s / 2], axis=-1)


class Profile(NamedTuple):
    """The one-field bounce along a path: x from the true vacuum (0) to the false one (L)."""

    action: float
    direct: float
    radius: float
    x: np.ndarray
    speed: np.ndarray
    start: float


def decay(inputs: ScalarVacuumInput, true_vacuum: str, true_field_gev: tuple[float, float],
          margin: float = 10.0) -> VacuumDecay:
    """The bounce and lifetime of the declared vacuum (v, 0) against the deeper minimum at ``true_field_gev``.

    Decided in stages, each rigorous where it decides: the straight path's action (an upper bound on S_E)
    can show the vacuum short-lived; the radial envelope's (``envelope_bound``, a lower bound) can show it
    long-lived; otherwise the deformed path's converged bounce decides.

    Args:
        inputs: the complete potential.
        true_vacuum: the deeper minimum's name in the vacuum certificate.
        true_field_gev: its (h, s) in GeV, with s ≥ 0 (the s < 0 copy gives the same bounce).
        margin: the band in ln P left unresolved for the prefactor.
    """
    scale = max(inputs.v_gev, math.hypot(*true_field_gev))
    field = Field(inputs.mu_h2_gev2 / scale**2, inputs.mu_s2_gev2 / scale**2, inputs.lambda_h, inputs.lambda_s,
                  inputs.lambda_hs)
    false, true = np.array([inputs.v_gev / scale, 0.0]), np.array(true_field_gev) / scale
    result = VacuumDecay(true_vacuum=true_vacuum, false_field_gev=[inputs.v_gev, 0.0],
                         true_field_gev=list(true_field_gev), margin=margin)
    try:
        straight = _normal_force(field, SmoothPath(true, false, np.zeros((1, 2))), np.array([0.5]))[0]
        result.action_upper_bound = straight.action
        if log_probability(straight.action, straight.radius / scale) > margin:
            return _decided(result, straight, scale, "short_lived", "the straight path's action, an upper bound")
        lower = envelope_bound(field, true, false)
        result.action_lower_bound = lower.action
        if log_probability(lower.action, lower.radius / scale) < -margin:
            return _decided(result, lower, scale, "long_lived", "the radial envelope's action, a lower bound")
        best, path, converged, iterations = deform(field, true, false)
    except (ArithmeticError, ValueError, RuntimeError) as error:
        result.reasons.append(f"the bounce was not found: {error}")
        return result
    agreement = abs(best.direct - best.action) / best.action
    result.action_upper_bound = min(best.action, straight.action)
    result.converged, result.iterations, result.virial_mismatch = converged, iterations, agreement
    result.path_gev = [[float(a * scale), float(b * scale)] for a, b in path[:: max(1, len(path) // 10)]]
    log_p = log_probability(best.action, best.radius / scale)
    status = _status(log_p, margin, converged and agreement < 0.05, result.reasons)
    return _decided(result, best, scale, status, "the deformed path's bounce")


def log_probability(action: float, radius_gev_inv: float) -> float:
    """ln P, P = (Γ/V) t_U⁴ with Γ/V = (S_E/2π)² R⁻⁴ e^(−S_E): the chance of a bubble in our past light cone."""
    return 2 * math.log(action / (2 * math.pi)) + 4 * math.log(T_UNIVERSE_GEV_INV / radius_gev_inv) - action


def _decided(result: VacuumDecay, profile: Profile, scale: float, status: str, how: str) -> VacuumDecay:
    result.bounce_action, result.radius_gev_inv = profile.action, profile.radius / scale
    result.log_probability = log_probability(profile.action, profile.radius / scale)
    result.status, result.decided_by = status, how
    return result


def _status(log_p: float, margin: float, trusted: bool, reasons: list[str]) -> str:
    """Short-lived needs only an upper bound on S_E; long-lived needs a converged, self-consistent bounce."""
    if log_p > margin:
        return "short_lived"
    if log_p < -margin and trusted:
        return "long_lived"
    reasons.append("ln P lies within the prefactor margin" if abs(log_p) <= margin else
                   "the path deformation did not converge to a self-consistent bounce")
    return "unresolved"


def envelope_bound(field, true: np.ndarray, false: np.ndarray, angles: int = 721) -> Profile:
    """The bounce of the radial envelope Ṽ(r) = min of V on the circle |φ − φ_false| = r, a lower bound on S_E.

    r is 1-Lipschitz in φ (|∂r| ≤ |∂φ|) and Ṽ(r(φ)) ≤ V(φ), so every configuration's action is at least
    the one-field action of r(ρ) in Ṽ, and so is the mountain pass: S_E ≥ S̃_E. The Higgs doublet's other
    components only add kinetic energy (|∂H|² ≥ (∂|H|)²). Ṽ runs from V_false at r = 0 to V_true at
    r = |φ_true − φ_false|, where the true vacuum lies on the circle.
    """
    reach = float(np.linalg.norm(true - false))
    r = np.linspace(0.0, reach, SAMPLES)
    theta = np.linspace(0.0, 2 * math.pi, angles, endpoint=False)
    width = theta[1] - theta[0]
    sampled = field.value(_circle(false, r, theta))
    low = theta[np.argmin(sampled, axis=1)] - width
    high = low + 2 * width
    golden = (math.sqrt(5) - 1) / 2
    for _ in range(60):                                  # golden-section refinement at every radius at once
        a, b = high - golden * (high - low), low + golden * (high - low)
        left = _on_circle(field, false, r, a) < _on_circle(field, false, r, b)
        high, low = np.where(left, b, high), np.where(left, low, a)
    envelope = np.minimum(_on_circle(field, false, r, (low + high) / 2), sampled.min(axis=1))
    envelope[0], envelope[-1] = field.value(false), field.value(true)
    x = reach - r[::-1]
    u = CubicSpline(x, envelope[::-1], bc_type=((1, 0.0), (1, 0.0)))
    return bounce(u, u.derivative(), reach)


def _circle(centre: np.ndarray, r: np.ndarray, theta: np.ndarray) -> np.ndarray:
    return centre + r[:, None, None] * np.stack([np.cos(theta), np.sin(theta)], axis=-1)[None, :, :]


def _on_circle(field, centre: np.ndarray, r: np.ndarray, theta: np.ndarray) -> np.ndarray:
    return field.value(centre + np.stack([r * np.cos(theta), r * np.sin(theta)], axis=-1))


class SmoothPath(NamedTuple):
    """A field-space path φ(t) = φ_true + t (φ_false − φ_true) + Σ_k a_k sin(kπt), t ∈ [0, 1]: smooth, with
    analytic derivatives, so the curvature in the normal force carries no node-to-node noise."""

    true: np.ndarray
    false: np.ndarray
    modes: np.ndarray                                  # (K, fields)

    def at(self, t: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(φ, dφ/dt, d²φ/dt²) at each t."""
        k = np.arange(1, len(self.modes) + 1) * math.pi
        sin, cos = np.sin(np.outer(t, k)), np.cos(np.outer(t, k))
        line = self.false - self.true
        return (self.true + np.outer(t, line) + sin @ self.modes, line + (cos * k) @ self.modes,
                -(sin * k**2) @ self.modes)


def deform(field, true: np.ndarray, false: np.ndarray, iterations: int = 80, tolerance: float = 0.02,
           modes: int = 8) -> tuple[Profile, np.ndarray, bool, int]:
    """(smallest-action profile, its path's nodes, converged, iterations).

    The path starts straight and moves against the normal force projected onto its sine modes, until that
    projected force is below ``tolerance`` of the largest |∇V| on the path, or the action is stationary (no
    step down to ``STATIONARY`` lowers it) with the force below ten times that. ``field`` is any potential with
    ``value`` and ``gradient`` on arrays of field points. A step that raises the action is undone and halved.
    """
    nodes = np.linspace(0.0, 1.0, POINTS)[1:-1]
    basis = np.sin(np.outer(nodes, np.arange(1, modes + 1) * math.pi))
    path = SmoothPath(true, false, np.zeros((modes, len(true))))
    best = best_path = best_force = None
    step = 0.05
    for iteration in range(1, iterations + 1):
        profile, force, scale = _normal_force(field, path, nodes)
        if best is None or profile.action <= best.action:
            best, best_path, best_force = profile, path, force
        else:
            path, force, step = best_path, best_force, step / 2
        projected = basis @ np.linalg.lstsq(basis, force, rcond=None)[0]
        largest = float(np.max(np.linalg.norm(projected, axis=1)))
        if largest < tolerance * scale or (step < STATIONARY and largest < 10 * tolerance * scale):
            return best, best_path.at(np.linspace(0, 1, POINTS))[0], True, iteration
        if step < STATIONARY:
            break
        length = float(np.sum(np.linalg.norm(np.diff(path.at(np.linspace(0, 1, POINTS))[0], axis=0), axis=1)))
        change = np.linalg.lstsq(basis, -step * length * projected / largest, rcond=None)[0]
        path = path._replace(modes=path.modes + change)
    return best, best_path.at(np.linspace(0, 1, POINTS))[0], False, iteration


def _normal_force(field, path: SmoothPath, nodes: np.ndarray) -> tuple[Profile, np.ndarray, float]:
    """(bounce along the path, the normal force ∇_⊥V − x'² κ at each node, the largest |∇V| on the path), with
    x the arc length from the true vacuum and κ the path's curvature vector."""
    t = np.linspace(0.0, 1.0, SAMPLES)
    phi, d1, _ = path.at(t)
    speed = np.linalg.norm(d1, axis=1)
    s = np.r_[0.0, np.cumsum((speed[1:] + speed[:-1]) / 2 * np.diff(t))]
    du = np.sum(field.gradient(phi) * d1, axis=1) / speed
    profile = bounce(CubicSpline(s, field.value(phi)), CubicSpline(s, du), float(s[-1]))
    at, d1n, d2n = path.at(nodes)
    v2 = np.interp(np.interp(nodes, t, s), profile.x, profile.speed**2, left=0.0, right=0.0)
    tangent = d1n / np.linalg.norm(d1n, axis=1, keepdims=True)
    curvature = (d2n - np.sum(d2n * tangent, axis=1, keepdims=True) * tangent) / np.sum(d1n**2, axis=1,
                                                                                         keepdims=True)
    g = field.gradient(at)
    perpendicular = g - np.sum(g * tangent, axis=1, keepdims=True) * tangent
    return profile, perpendicular - v2[:, None] * curvature, float(np.max(np.linalg.norm(field.gradient(phi),
                                                                                          axis=1)))


def bounce(u: CubicSpline, du: CubicSpline, length: float) -> Profile:
    """The one-field bounce for the potential u(x), true vacuum at x = 0 and false vacuum at x = L, by
    overshoot/undershoot shooting on ln x(0)."""
    top = float(u(length))
    if not float(u(0.0)) < top:
        raise ValueError("the true vacuum is not deeper than the false one along the path")
    xs = np.linspace(0.0, length, SAMPLES)
    above = np.nonzero(u(xs) >= top)[0]
    edge = xs[above[0]] if len(above) and above[0] > 0 else length
    mass2 = float(du(1e-6 * length) / (1e-6 * length))
    if not mass2 > 0:
        raise ValueError("the true vacuum is not a minimum along the path")
    low, high = math.log(1e-250 * length), math.log(edge)
    if _shoot(low, u, du, length, mass2)[0] < 0:
        raise ArithmeticError("thin wall beyond the shooting's resolution")
    for _ in range(200):
        middle = (low + high) / 2
        if _shoot(middle, u, du, length, mass2)[0] > 0:
            low = middle
        else:
            high = middle
        if high - low < 1e-12 * max(1.0, abs(low)):
            break
    return _profile(low, u, du, length, mass2)


def _start(log_delta: float, length: float, mass2: float) -> tuple[float, float, float]:
    """(ρ, x, x') where the linear solution x = δ·2I₁(mρ)/(mρ) near the true vacuum reaches START·L
    (x' = δ·m·2I₂(mρ)/(mρ)), in logarithms so that a thin wall's exponentially small δ does not overflow."""
    m, target = math.sqrt(mass2), START * length

    def log_shape(z: float, order: int = 1) -> float:        # ln[2 I_order(z)/z]
        return math.log(2 * ive(order, z)) + z - math.log(z)

    z = 1e-6 if log_delta >= math.log(target) else brentq(
        lambda z: log_delta + log_shape(z) - math.log(target), 1e-6, 2000.0)
    return z / m, math.exp(log_delta + log_shape(z)), m * math.exp(log_delta + log_shape(z, 2))


def _shoot(log_delta: float, u, du, length: float, mass2: float):
    """(+1 overshoot / −1 undershoot, the solution) for x(0) = δ."""
    rho, x, slope = _start(log_delta, length, mass2)

    def over(r, y):
        return y[0] - length
    over.terminal, over.direction = True, 1

    def back(r, y):
        return y[1]
    back.terminal, back.direction = True, -1
    span = rho + 200.0 / math.sqrt(mass2) + 50.0 * length / math.sqrt(max(float(u(length) - u(0.0)), 1e-300))
    solution = solve_ivp(lambda r, y: [y[1], float(du(min(max(y[0], 0.0), length))) - 3 * y[1] / r],
                         (rho, rho + span), [x, slope], events=(over, back), rtol=1e-9, atol=1e-12 * length,
                         dense_output=True)
    if len(solution.t_events[0]):
        return 1, solution
    return -1, solution


def _profile(log_delta: float, u, du, length: float, mass2: float) -> Profile:
    """The bounce's profile and action from the overshooting side of the converged bracket."""
    rho0, _, _ = _start(log_delta, length, mass2)
    _, solution = _shoot(log_delta, u, du, length, mass2)
    rho = np.unique(np.r_[solution.t, np.linspace(solution.t[0], solution.t[-1], 4 * SAMPLES)])
    x, speed = solution.sol(rho)
    kinetic = math.pi**2 / 2 * np.trapezoid(rho**3 * speed**2, rho)
    inside = 2 * math.pi**2 * float(u(0.0) - u(length)) * rho0**4 / 4        # the interior, at the true vacuum
    direct = inside + 2 * math.pi**2 * np.trapezoid(rho**3 * (speed**2 / 2 + u(np.clip(x, 0, length))
                                                               - float(u(length))), rho)
    radius = float(rho[np.argmax(speed)])
    keep = np.r_[True, np.diff(x) > 0]
    return Profile(action=float(kinetic), direct=float(direct), radius=radius, x=x[keep], speed=speed[keep],
                   start=float(x[0]))


def thin_wall_action(tension: float, splitting: float) -> float:
    """Coleman's thin-wall action 27π²σ⁴/(2ε³) for wall tension σ and vacuum splitting ε (any consistent units)."""
    return 27 * math.pi**2 * tension**4 / (2 * splitting**3)

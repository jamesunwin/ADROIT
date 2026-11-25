"""Narrow published one-loop Z2-singlet RGEs in the existing potential convention."""

from __future__ import annotations

from functools import lru_cache
import math
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import OptimizeResult
from typing import Callable
from adroit.core.evidence import content_hash
from adroit.core.running import RGRequest, RunningPoint, RGCrossing, ScalarRGCertificate
from adroit.core.theory import ScalarVacuumInput
from adroit.core.model_contracts import ResolvedScalarPotential

NAMES = (
    "g_prime",
    "g",
    "g3",
    "y_top",
    "lambda_h",
    "lambda_s",
    "lambda_hs",
    "mu_h2_gev2",
    "mu_s2_gev2",
)
CRITERIA = ("lambda_H", "lambda_S", "mixed_copositivity", "scalar_a0", "gauge_yukawa", "pole_guard")


def beta(values: np.ndarray) -> np.ndarray:
    """d/dln(mu), Eq29-37 converted: lambda=6H, a2=P/2, b4=S, m2=-muH2."""
    a, b, c, y, h, s, p, m, n = values
    top = 6 * y * y - 4.5 * b * b - 1.5 * a * a
    return np.array(
        [
            41 * a**3 / 6,
            -19 * b**3 / 6,
            -7 * c**3,
            y * (4.5 * y * y - 8 * c * c - 2.25 * b * b - 17 * a * a / 12),
            24 * h * h
            + 0.5 * p * p
            - 6 * y**4
            + 2 * h * top
            + 3 * (a**4 + 2 * a * a * b * b + 3 * b**4) / 8,
            18 * s * s + 2 * p * p,
            p * (4 * p + 6 * s + 12 * h + top),
            m * (12 * h + top) - p * n,
            6 * s * n - 4 * p * m,
        ]
    ) / (16 * math.pi**2)


def _margins(z: np.ndarray) -> np.ndarray:
    h, s, p = z[4:7]
    mixed = p + 2 * math.sqrt(max(h, 0) * max(s, 0))
    ev = np.linalg.eigvalsh([[6 * h, p], [p, 3 * s]])
    maximum = max(float(np.max(abs(ev))), abs(2 * h), abs(p)) / (16 * math.pi)
    return np.array(
        [
            h,
            s,
            mixed,
            0.5 - maximum,
            4 * math.pi - float(np.max(z[:4] ** 2)),
            1000 - float(np.max(abs(z[:7]))),
        ]
    )


def _initial(p: ScalarVacuumInput, r: RGRequest) -> np.ndarray:
    sm = r.matching
    return np.array(
        [
            sm.g_prime,
            sm.g,
            sm.g3,
            sm.y_top,
            p.lambda_h,
            p.lambda_s,
            p.lambda_hs,
            p.mu_h2_gev2 / p.scale_gev**2,
            p.mu_s2_gev2 / p.scale_gev**2,
        ]
    )


def _solve(p: ScalarVacuumInput, r: RGRequest, method: str) -> OptimizeResult:
    def event(index: int) -> Callable[[float, np.ndarray], float]:
        def boundary(t: float, z: np.ndarray) -> float:
            return float(_margins(z)[index])

        boundary.terminal = True
        boundary.direction = -1
        return boundary

    return solve_ivp(
        lambda t, z: beta(z),
        (0, math.log(r.upper_scale_gev) - math.log(p.scale_gev)),
        _initial(p, r),
        method=method,
        dense_output=True,
        events=[event(i) for i in range(6)],
        rtol=r.relative_tolerance,
        atol=r.absolute_tolerance,
        max_step=r.max_log_step,
    )


def _point(t: float, z: np.ndarray, p: ScalarVacuumInput) -> RunningPoint:
    values = dict(zip(NAMES, map(float, z)))
    values["mu_h2_gev2"] *= p.scale_gev**2
    values["mu_s2_gev2"] *= p.scale_gev**2
    margins = _margins(z)
    return RunningPoint(
        scale_gev=math.exp(math.log(p.scale_gev) + t),
        **values,
        boundedness_margin=float(min(margins[:3])),
        scalar_a0_margin=float(margins[3]),
        gauge_yukawa_margin=float(margins[4]),
    )


def _trajectory(c: ScalarRGCertificate, p: ScalarVacuumInput, r: RGRequest) -> None:
    one, two = _solve(p, r, "DOP853"), _solve(p, r, "Radau")
    endpoint = min(float(one.t[-1]), float(two.t[-1]))
    nodes = np.union1d(
        np.linspace(0, endpoint, max(2, int(endpoint / r.max_log_step) + 1)),
        one.t[one.t <= endpoint],
    )
    a, b = one.sol(nodes), two.sol(nodes)
    c.integration_error = float(np.max(abs(a - b) / (1 + abs(a))))
    c.trajectory = [_point(float(t), z, p) for t, z in zip(nodes, a.T)]
    first = [(float(ts[0]), i) for i, ts in enumerate(one.t_events) if len(ts)]
    second = [(float(ts[0]), i) for i, ts in enumerate(two.t_events) if len(ts)]
    if not one.success or not two.success or c.integration_error > r.comparison_tolerance:
        c.status = "unresolved"
        c.reasons = ["integration failed or independent solutions exceed error tolerance"]
    elif bool(first) != bool(second) or (
        first
        and (
            min(first)[1] != min(second)[1]
            or abs(min(first)[0] - min(second)[0]) > r.comparison_tolerance
        )
    ):
        c.status = "unresolved"
        c.reasons = ["first crossing does not resolve consistently between integrators"]
    elif first:
        t, i = min(first)
        c.first_crossing = RGCrossing(
            scale_gev=math.exp(math.log(p.scale_gev) + t),
            criterion=CRITERIA[i],
            log_scale_difference=abs(t - min(second)[0]),
        )
        c.status = "pole_guard" if i == 5 else "failed"
        c.passed = False
        c.complete = i != 5
        c.reasons = [
            "requested domain crosses the declared criterion; running stopped at first crossing"
        ]
    elif min(_margins(a[:, -1])[:5]) <= r.comparison_tolerance:
        c.status = "unresolved"
        c.reasons = ["requested endpoint lies within a criterion boundary tolerance"]
    else:
        c.status = "passed"
        c.passed = True
        c.complete = True
        c.reasons = [
            "both integrators reach the requested scale without a resolved criterion crossing"
        ]


def _safe_initial(c: ScalarRGCertificate, p: ScalarVacuumInput, r: RGRequest) -> np.ndarray | None:
    try:
        scale2 = p.scale_gev**2
        if scale2 == 0 or not math.isfinite(scale2):
            raise ArithmeticError("quadratic normalization scale cannot be represented")
        z = _initial(p, r)
        if not np.isfinite(z).all() or any(
            a != 0 and b == 0 for a, b in zip((p.mu_h2_gev2, p.mu_s2_gev2), z[7:])
        ):
            raise ArithmeticError("quadratic normalization loses a finite coefficient")
    except ArithmeticError as error:
        c.status = "invalid_matching"
        c.reasons = [f"unrepresentable matching inputs: {error}"]
        return None
    if np.max(abs(z[:7])) >= 1000:
        c.status = "pole_guard"
        c.reasons = ["initial dimensionless coupling reaches numerical pole guard"]
        return None
    try:
        c.trajectory = [_point(0, z, p)]
    except (ArithmeticError, ValueError, np.linalg.LinAlgError) as error:
        c.status = "invalid_matching"
        c.reasons = [f"unrepresentable matching trajectory: {error}"]
        return None
    return z


def certify(inputs: ScalarVacuumInput | None, request: RGRequest | None) -> ScalarRGCertificate:
    """Check exactly the requested range, refusing missing or scale-inconsistent matching."""
    c = ScalarRGCertificate(inputs=inputs, request=request)
    if inputs is None or request is None:
        c.reasons = ["complete potential and explicit RG request/matching/upper scale required"]
        return c
    c.parameter_sha256 = content_hash(
        {"inputs": inputs.model_dump(mode="json"), "request": request.model_dump(mode="json")}
    )
    if not math.isclose(inputs.scale_gev, request.matching.scale_gev, rel_tol=1e-12):
        c.status = "invalid_matching"
        c.reasons = ["potential and SM matching scales differ; no implicit rematching"]
        return c
    z = _safe_initial(c, inputs, request)
    if z is None:
        return c
    margins = _margins(z)
    if min(margins[:5]) < -request.comparison_tolerance:
        c.status = "failed"
        c.passed = False
        c.complete = True
        c.first_crossing = RGCrossing(
            scale_gev=inputs.scale_gev,
            criterion=CRITERIA[int(np.argmin(margins[:5]))],
            log_scale_difference=0,
        )
        c.reasons = ["declared criterion already fails at matching scale"]
        return c
    if min(margins[:5]) <= request.comparison_tolerance:
        c.status = "unresolved"
        c.reasons = ["initial condition is marginal or near a criterion boundary"]
        return c
    try:
        _trajectory(c, inputs, request)
    except (ValueError, ArithmeticError, np.linalg.LinAlgError) as error:
        c.status = "unresolved"
        c.reasons = [f"integration unresolved: {error}"]
    return c


def for_potential(
    potential: ResolvedScalarPotential, request: RGRequest | None
) -> ScalarRGCertificate:
    """Point-bound cached result; callers receive independent certificate copies."""
    p = ScalarVacuumInput.model_validate(
        potential.model_dump(exclude={"higgs_mass_gev", "singlet_mass_gev", "convention"})
    )
    return _cached(p.model_dump_json(), request.model_dump_json() if request else None).model_copy(
        deep=True
    )


@lru_cache(maxsize=512)
def _cached(p: str, r: str | None) -> ScalarRGCertificate:
    return certify(
        ScalarVacuumInput.model_validate_json(p), RGRequest.model_validate_json(r) if r else None
    )

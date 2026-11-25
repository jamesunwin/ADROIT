"""Analytic global minimization of the complete Z2 scalar potential on its quadrant.

Exact rational arithmetic uses the represented input floats. Nonzero margins below
stated numerical resolution stay unresolved; exact equalities admit flat families.
Enumeration of every face and interior stationary family supplies the global proof.
A bounded declared vacuum above a deeper minimum is then judged by its zero-temperature
tunnelling lifetime (``theory.vacuum_decay``): metastable (passes), short-lived (fails)
or unresolved.
"""

from __future__ import annotations

from fractions import Fraction as F
from functools import lru_cache
import math
from typing import NamedTuple

from adroit.core.evidence import content_hash
from adroit.core.model_contracts import ResolvedScalarPotential
from adroit.core.theory import (
    ScalarVacuumInput,
    VacuumSettings,
    ScalarVacuumCertificate,
    ScalarExtremum,
    StationaryFamily,
    RunawayDirection,
)


class _Polynomial(NamedTuple):
    a: F
    b: F
    A: F
    B: F
    C: F


def _value(p: _Polynomial, x: F, y: F) -> F:
    return p.a * x + p.b * y + p.A * x * x + p.B * y * y + p.C * x * y


def _near(value: F, scale: F, tol: F) -> bool:
    return value != 0 and abs(value) <= tol * abs(scale)


def _float(value: F) -> float:
    result = float(value)
    if not math.isfinite(result) or (result == 0 and value != 0):
        raise ArithmeticError("finite-range conversion lost a nonzero exact quantity")
    return result


def _ray(p: _Polynomial, d: tuple[F, F], leading: str) -> RunawayDirection:
    x, y = d
    q = p.A * x * x + p.B * y * y + p.C * x * y
    return RunawayDirection(
        direction_exact=[str(x), str(y)],
        quartic_exact=str(q),
        quadratic_exact=str(p.a * x + p.b * y),
        leading=leading,
        explanation="V(t*d)=quartic*t²+quadratic*t, t>=0 in squared-field coordinates",
    )


def _bounded(p: _Polynomial, c: ScalarVacuumCertificate, tol: F) -> None:
    """Copositivity plus all exact quartic-null rays' lower-order terms."""
    A, B, C = p.A, p.B, p.C
    if A < 0 or B < 0:
        c.quartic = c.boundedness = "unbounded"
        c.runaway = _ray(p, (F(1), F(0)) if A < 0 else (F(0), F(1)), "quartic")
        return
    scale = max(A, B, abs(C))
    if any(_near(z, scale, tol) for z in (A, B)):
        c.quartic = c.boundedness = "unresolved"
        c.reasons.append("quartic axis coefficient is below numerical sign resolution")
        return
    det = 4 * A * B - C * C
    if C < 0 and det < 0 and not _near(det, 4 * A * B + C * C, tol):
        d = (F(1), -C / (2 * B)) if B else (F(1), max(F(1), 2 * A / abs(C)))
        c.quartic = c.boundedness = "unbounded"
        c.runaway = _ray(p, d, "quartic")
        return
    if C < 0 and _near(det, 4 * A * B + C * C, tol):
        c.quartic = c.boundedness = "unresolved"
        c.reasons.append("copositivity boundary is below numerical sign resolution")
        return
    flat = []
    if A == 0:
        flat.append((F(1), F(0)))
    if B == 0:
        flat.append((F(0), F(1)))
    if C < 0 and det == 0:
        flat.append((-C, 2 * A))
    c.quartic = "marginal" if flat else "strict"
    c.flat_directions_exact = [[str(x), str(y)] for x, y in flat]
    c.boundedness = "bounded"
    for x, y in flat:
        slope = p.a * x + p.b * y
        if _near(slope, abs(p.a * x) + abs(p.b * y), tol):
            c.boundedness = "unresolved"
            c.reasons.append("quadratic slope on quartic-flat ray is unresolved")
        elif slope < 0:
            c.boundedness = "unbounded"
            c.runaway = _ray(p, (x, y), "quadratic")
            return


def _local(p: _Polynomial, x: F, y: F, tol: F) -> str:
    """Constrained local minimum including marginal Hessians' reduced quartics."""
    gx, gy = p.a + 2 * p.A * x + p.C * y, p.b + 2 * p.B * y + p.C * x
    if x > 0 and y > 0:
        if p.A < 0 or p.B < 0 or 4 * p.A * p.B - p.C * p.C < 0:
            return "saddle_or_maximum"
        return "strict_local_minimum" if 4 * p.A * p.B - p.C * p.C > 0 else "flat_local_minimum"
    if x == 0 and y > 0:
        return _local(_Polynomial(p.b, p.a, p.B, p.A, p.C), y, x, tol)
    if x > 0:
        if p.A < 0:
            return "unstable"
        if _near(gy, abs(p.b) + abs(p.C * x), tol):
            return "unresolved"
        if gy < 0:
            return "unstable"
        if gy > 0:
            return "strict_local_minimum" if p.A > 0 else "flat_local_minimum"
        if p.A > 0:
            det = 4 * p.A * p.B - p.C * p.C
            if _near(det, 4 * abs(p.A * p.B) + p.C * p.C, tol):
                return "unresolved"
            return "flat_local_minimum" if det >= 0 else "unstable"
        return "flat_local_minimum" if p.C == 0 and p.B >= 0 else "unstable"
    if gx < 0 or gy < 0:
        return "unstable"
    if any(_near(z, abs(gx) + abs(gy), tol) for z in (gx, gy)):
        return "unresolved"
    if gx > 0 and gy > 0:
        return "strict_local_minimum"
    if gx == 0 and p.A < 0 or gy == 0 and p.B < 0:
        return "unstable"
    if gx == gy == 0 and (p.A < 0 or p.B < 0 or (p.C < 0 and p.C * p.C > 4 * p.A * p.B)):
        return "unstable"
    return "flat_local_minimum"


def _extremum(p: _Polynomial, name: str, x: F, y: F, tol: F) -> ScalarExtremum:
    gx, gy = p.a + 2 * p.A * x + p.C * y, p.b + 2 * p.B * y + p.C * x
    residual = max(abs(gx) if x else F(0), abs(gy) if y else F(0))
    scale = max(
        abs(p.a) + 2 * abs(p.A * x) + abs(p.C * y), abs(p.b) + 2 * abs(p.B * y) + abs(p.C * x)
    )
    return ScalarExtremum(
        name=name,
        x_gev2=_float(x),
        y_gev2=_float(y),
        potential_gev4=_float(_value(p, x, y)),
        exact_coordinates=[str(x), str(y)],
        exact_potential=str(_value(p, x, y)),
        local_classification=_local(p, x, y, tol),
        stationarity_residual=_float(residual / scale) if scale else 0.0,
        singlet_sign_multiplicity=2 if y > 0 else 1,
    )


def _interval(anchor: tuple[F, F], direction: tuple[F, F]) -> tuple[F | None, F | None] | None:
    low = high = None
    for z, n in zip(anchor, direction):
        if n == 0 and z < 0:
            return None
        if n > 0:
            low = max(low, -z / n) if low is not None else -z / n
        if n < 0:
            high = min(high, -z / n) if high is not None else -z / n
    return None if low is not None and high is not None and high <= low else (low, high)


def _family(
    p: _Polynomial,
    name: str,
    anchor: tuple[F, F],
    directions: list[tuple[F, F]],
    bounds: tuple[F | None, F | None] | None = None,
) -> StationaryFamily:
    return StationaryFamily(
        name=name,
        dimension=len(directions),
        equations=[f"2*({p.A})*x+({p.C})*y={-p.a}", f"({p.C})*x+2*({p.B})*y={-p.b}"],
        anchor_exact=[str(z) for z in anchor],
        directions_exact=[[str(z) for z in n] for n in directions],
        parameter_low_exact=str(bounds[0]) if bounds and bounds[0] is not None else None,
        parameter_high_exact=str(bounds[1]) if bounds and bounds[1] is not None else None,
        potential_gev4=_float(_value(p, *anchor)),
        exact_potential=str(_value(p, *anchor)),
    )


def _rank_family(p: _Polynomial) -> StationaryFamily | None:
    rows = [(2 * p.A, p.C, -p.a), (p.C, 2 * p.B, -p.b)]
    row = next((r for r in rows if r[0] or r[1]), None)
    if row is None:
        return (
            _family(p, "entire_quadrant", (F(0), F(0)), [(F(1), F(0)), (F(0), F(1))])
            if p.a == p.b == 0
            else None
        )
    r, s, d = row
    if any(r * v - s * u != 0 or r * w - d * u != 0 or s * w - d * v != 0 for u, v, w in rows):
        return None
    anchor = (d / r, F(0)) if r else (F(0), d / s)
    normal = max(abs(r), abs(s))
    direction = (-s / normal, r / normal)
    bounds = _interval(anchor, direction)
    if bounds is None:
        return None
    lo, hi = bounds
    t = (
        (lo + hi) / 2
        if lo is not None and hi is not None
        else lo + 1
        if lo is not None
        else hi - 1
        if hi is not None
        else F(0)
    )
    if not all(z + n * t > 0 for z, n in zip(anchor, direction)):
        return None
    return _family(p, "mixed_stationary_family", anchor, [direction], bounds)


def _enumerate(p: _Polynomial, c: ScalarVacuumCertificate, tol: F) -> None:
    c.extrema = [_extremum(p, "origin", F(0), F(0), tol)]
    for name, A, a, axis in [("higgs_axis", p.A, p.a, 0), ("singlet_axis", p.B, p.b, 1)]:
        if A and -a / (2 * A) > 0:
            z = [F(0), F(0)]
            z[axis] = -a / (2 * A)
            c.extrema.append(_extremum(p, name, *z, tol))
        elif A == a == 0:
            d = [F(0), F(0)]
            d[axis] = F(1)
            family = _family(p, name + "_family", (F(0), F(0)), [tuple(d)], (F(0), None))
            family.equations = [f"{'y' if axis == 0 else 'x'}=0", f"{a}=0"]
            c.families.append(family)
    det = 4 * p.A * p.B - p.C * p.C
    if det:
        x, y = (p.C * p.b - 2 * p.B * p.a) / det, (p.C * p.a - 2 * p.A * p.b) / det
        if x > 0 and y > 0:
            c.extrema.append(_extremum(p, "mixed", x, y, tol))
        if _near(det, 4 * abs(p.A * p.B) + p.C * p.C, tol):
            c.reasons.append(
                "stationary matrix is nearly singular; global enumeration is unresolved"
            )
    else:
        family = _rank_family(p)
        if family:
            c.families.append(family)


def _declared(p: _Polynomial, c: ScalarVacuumCertificate, tol: F) -> tuple[F, F] | None:
    x = F(c.inputs.v_gev) ** 2 / 2
    value = _value(p, x, F(0))
    gx = p.a + 2 * p.A * x
    scale = abs(p.a) + 2 * abs(p.A * x)
    residual = abs(gx) / scale if scale and x else F(0)
    c.declared_x_gev2 = _float(x)
    c.declared_potential_gev4 = _float(value)
    c.declared_stationarity_residual = _float(residual)
    if x and residual > tol:
        c.vacuum = "unstable"
        c.local_classification = "not_stationary"
        c.reasons.append(
            "declared electroweak vacuum is not stationary within the stated tolerance"
        )
        return None
    canonical = -p.a / (2 * p.A) if x and p.A else x
    c.local_classification = _local(p, canonical, F(0), tol)
    for point in c.extrema:
        point.lower_than_declared = F(point.exact_potential) < value
    return canonical, _value(p, canonical, F(0))


def _classify(p: _Polynomial, c: ScalarVacuumCertificate, tol: F) -> None:
    declared = _declared(p, c, tol)
    if c.boundedness == "unresolved" or c.reasons and any("unresolved" in r for r in c.reasons):
        c.vacuum = "unresolved"
        return
    candidates = [(e.name, F(e.exact_potential)) for e in c.extrema] + [
        (f.name, F(f.exact_potential)) for f in c.families
    ]
    minimum = min(z for _, z in candidates)
    energy_scale = max(abs(z) for _, z in candidates)
    if c.boundedness == "bounded":
        c.global_minimum_gev4 = _float(minimum)
        c.minima = [name for name, z in candidates if z == minimum]
    if declared is None:
        c.complete = True
        c.passed = False
        return
    x, depth = declared
    if c.local_classification == "unresolved":
        c.vacuum = "unresolved"
        return
    if c.local_classification not in ("strict_local_minimum", "flat_local_minimum"):
        c.vacuum = "unstable"
        c.complete = True
        c.passed = False
        return
    if c.boundedness == "unbounded":
        c.vacuum = "local"
        c.complete = True
        c.passed = False
        return
    if any(_near(z - minimum, max(abs(z), abs(minimum)), tol) for _, z in candidates) or _near(
        depth - minimum, energy_scale, tol
    ):
        c.vacuum = "unresolved"
        c.reasons.append("competing depths are below numerical comparison resolution")
        return
    c.minima = [name for name, z in candidates if z == minimum]
    if depth > minimum:
        _lifetime(c)
        return
    if any(f.name in c.minima for f in c.families) or len(c.minima) > 1:
        c.vacuum = "degenerate"
    else:
        c.vacuum = "global"
    c.complete = True
    c.passed = True if c.vacuum == "global" else None if c.vacuum == "degenerate" else False
    if c.vacuum == "degenerate":                       # audit minor: an exact tie is not a pass
        c.reasons.append("the declared vacuum is exactly degenerate with another minimum or a flat stationary "
                         "family (Z2- or electroweak-breaking); which one is the vacuum is not decided at tree level")


def _lifetime(c: ScalarVacuumCertificate) -> None:
    """A bounded declared vacuum above a deeper minimum: its zero-temperature tunnelling decides
    (``theory.vacuum_decay``). Long-lived is metastable and passes, short-lived fails, and a lifetime within
    the prefactor margin, or a deeper minimum that is a flat family, leaves the vacuum unresolved."""
    from adroit.theory.vacuum_decay import decay
    c.complete = True
    deepest = [e for e in c.extrema if e.name in c.minima]
    if not deepest:
        c.vacuum, c.passed = "local", None
        c.reasons.append("the deeper minimum is a flat stationary family; no single bounce endpoint")
        return
    true = deepest[0]
    c.decay = decay(c.inputs, true.name, (math.sqrt(2 * true.x_gev2), math.sqrt(2 * true.y_gev2)),
                    c.settings.lifetime_margin)
    if c.decay.status == "long_lived":
        c.vacuum, c.passed = "metastable", True
        c.reasons.append(f"metastable: the declared vacuum lies above {true.name} but outlives the universe "
                         f"(ln P = {c.decay.log_probability:.4g} by {c.decay.decided_by})")
    elif c.decay.status == "short_lived":
        c.vacuum, c.passed = "short_lived", False
        c.reasons.append(f"the declared vacuum decays to {true.name} within the age of the universe "
                         f"(ln P = {c.decay.log_probability:.4g} by {c.decay.decided_by})")
    else:
        c.vacuum, c.passed = "local", None
        c.reasons += [f"the lifetime is unresolved: {r}" for r in c.decay.reasons] or ["the lifetime is unresolved"]


def certify(
    inputs: ScalarVacuumInput | None, settings: VacuumSettings | None = None
) -> ScalarVacuumCertificate:
    """Prove boundedness and enumerate all extrema, or report exact missing/ambiguous input."""
    c = ScalarVacuumCertificate(
        inputs=inputs,
        settings=settings or VacuumSettings(),
        equations={
            "potential": "V(x,y)=-mu_H²*x+mu_S²*y+lambda_H*x²+lambda_HS*x*y+lambda_S*y²",
            "domain": "x=H†H>=0, y=S²/2>=0; declared point (v²/2,0)",
            "copositivity": "lambda_H>=0, lambda_S>=0, lambda_HS+2*sqrt(lambda_H*lambda_S)>=0",
            "stationary": "h*(-mu_H²+2*lambda_H*x+lambda_HS*y)=0; S*(mu_S²+2*lambda_S*y+lambda_HS*x)=0",
            "completeness": "origin, each axis, interior linear-system solution, and every singular stationary family",
            "flat_ray": "when V4(d)=0 require V2(d)>=0; V(t*d)=t²*V4(d)+t*V2(d)",
            "lifetime": "metastable declared vacuum: O(4) bounce S_E; ln P = 2 ln(S_E/2π) + 4 ln(t_U/R) - S_E "
                        "< -margin passes, > +margin fails",
        },
    )
    if inputs is None:
        c.reasons = ["complete potential, declared vacuum and scale are required"]
        return c
    c.parameter_sha256 = content_hash(inputs.model_dump(mode="json"))
    p = _Polynomial(
        -F(inputs.mu_h2_gev2),
        F(inputs.mu_s2_gev2),
        F(inputs.lambda_h),
        F(inputs.lambda_s),
        F(inputs.lambda_hs),
    )
    tol = F(c.settings.relative_tolerance)
    try:
        _bounded(p, c, tol)
        _enumerate(p, c, tol)
        _classify(p, c, tol)
    except (ArithmeticError, ValueError) as error:
        c.complete = False
        c.passed = None
        c.vacuum = "unresolved"
        c.reasons.append(f"numerical range/representation unresolved: {error}")
    return c


def for_potential(potential: "ResolvedScalarPotential") -> ScalarVacuumCertificate:
    """Bind the certificate to the complete numerical potential at this exact point."""
    inputs = ScalarVacuumInput.model_validate(
        potential.model_dump(exclude={"higgs_mass_gev", "singlet_mass_gev", "convention"})
    )
    return _cached(inputs.model_dump_json()).model_copy(deep=True)


@lru_cache(maxsize=2048)
def _cached(payload: str) -> ScalarVacuumCertificate:
    return certify(ScalarVacuumInput.model_validate_json(payload))

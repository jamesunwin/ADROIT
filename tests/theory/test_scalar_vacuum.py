"""Analytic boundaries and independent field-space minimization for M24."""

from __future__ import annotations

from fractions import Fraction
import math
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from scipy.optimize import minimize, root
import sympy as sy
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.core.theory import ScalarVacuumInput, VacuumSettings
from adroit.theory.scalar_vacuum import certify, for_potential


def model(**changes: float) -> ScalarVacuumInput:
    return ScalarVacuumInput(
        scale_gev=100,
        v_gev=1,
        mu_h2_gev2=1,
        mu_s2_gev2=changes.get("mu_s2", 1),
        lambda_h=changes.get("A", 1),
        lambda_s=changes.get("B", 1),
        lambda_hs=changes.get("C", 0),
    )


def test_decoupled_global_local_and_saddle() -> None:
    c = certify(model())
    assert c.complete and c.passed and c.vacuum == "global" and c.boundedness == "bounded"
    assert c.global_minimum_gev4 == -0.25 and c.minima == ["higgs_axis"]
    unstable = certify(model(mu_s2=-1, C=0))
    assert unstable.vacuum == "unstable" and not unstable.passed
    assert any(e.name == "mixed" and e.potential_gev4 == -0.5 for e in unstable.extrema)
    local = certify(model(mu_s2=-2, C=5))                # a deeper singlet minimum, reached by tunnelling
    assert local.vacuum == "short_lived" and local.global_minimum_gev4 == -1
    assert local.minima == ["singlet_axis"] and local.passed is False and local.decay.status == "short_lived"
    assert next(e for e in local.extrema if e.name == "singlet_axis").singlet_sign_multiplicity == 2


def test_exact_competing_vacuum_degeneracy_and_nearby_ambiguity() -> None:
    c = certify(model(mu_s2=-1, C=3))
    assert c.vacuum == "degenerate" and c.complete and c.passed is None
    assert set(c.minima) == {"higgs_axis", "singlet_axis"}
    near = certify(model(mu_s2=-1 - 1e-12, C=3))
    assert near.vacuum == "unresolved" and near.passed is None
    assert any("depths" in r for r in near.reasons)
    assert certify(model(mu_s2=-1.001, C=3)).vacuum in ("metastable", "short_lived", "local")


@pytest.mark.parametrize(
    "C,result", [(-2.1, "unbounded"), (-2, "marginal"), (-1.9, "strict"), (3, "strict")]
)
def test_independent_copositivity_boundary(C: float, result: str) -> None:
    c = certify(model(C=C, mu_s2=3))
    assert c.quartic == result
    # Independent minimization of V4 on x+y=1 gives its sign everywhere on the cone.
    x = sy.symbols("x", real=True)
    q = x * x + (1 - x) ** 2 + C * x * (1 - x)
    stationary = sy.solve(sy.diff(q, x), x)
    candidates = [sy.Integer(0), sy.Integer(1), *[z for z in stationary if 0 <= z <= 1]]
    exact = min(float(q.subs(x, z)) for z in candidates)
    assert (exact < 0) == (result == "unbounded")
    if c.runaway:
        dx, dy = map(Fraction, c.runaway.direction_exact)
        assert dx >= 0 and dy >= 0 and Fraction(c.runaway.quartic_exact) < 0


@pytest.mark.parametrize("mass,status", [(1, "bounded"), (0, "bounded"), (-1, "unbounded")])
def test_axis_flat_direction_lower_order_terms(mass: float, status: str) -> None:
    c = certify(model(B=0, C=0, mu_s2=mass))
    assert c.quartic == "marginal" and c.boundedness == status
    assert ["0", "1"] in c.flat_directions_exact
    if mass == 0:
        assert c.vacuum == "degenerate" and any(
            f.name == "mixed_stationary_family" for f in c.families
        )
    if mass < 0:
        assert c.runaway.leading == "quadratic" and c.vacuum == "unstable" and not c.passed


@pytest.mark.parametrize("b,status", [(2, "bounded"), (1, "bounded"), (0, "unbounded")])
def test_negative_portal_flat_ray_with_quadratic_slope(b: float, status: str) -> None:
    c = certify(model(C=-2, mu_s2=b))
    assert c.quartic == "marginal" and c.boundedness == status
    if b == 1:
        assert c.vacuum == "degenerate"
        f = next(f for f in c.families if f.name == "mixed_stationary_family")
        assert f.parameter_high_exact is None and f.potential_gev4 == -0.25
    if b == 0:
        assert c.runaway.leading == "quadratic"


def test_positive_portal_rank_one_stationary_segment() -> None:
    c = certify(model(C=2, mu_s2=-1))
    assert c.quartic == "strict" and c.vacuum == "degenerate" and c.passed is None
    f = next(f for f in c.families if f.name == "mixed_stationary_family")
    assert f.parameter_low_exact is not None and f.parameter_high_exact is not None
    assert Fraction(f.parameter_high_exact) > Fraction(f.parameter_low_exact)


def test_zero_potential_and_axis_families_are_complete() -> None:
    p = ScalarVacuumInput(
        scale_gev=1, v_gev=0, mu_h2_gev2=0, mu_s2_gev2=0, lambda_h=0, lambda_s=0, lambda_hs=0
    )
    c = certify(p)
    assert c.vacuum == "degenerate" and c.passed is None and c.global_minimum_gev4 == 0
    assert any(f.dimension == 2 for f in c.families)
    p = p.model_copy(update={"lambda_s": 1, "mu_s2_gev2": -2})
    c = certify(p)
    assert c.vacuum == "unstable" and any(f.name == "mixed_stationary_family" for f in c.families)


def test_marginal_hessian_can_be_locally_unstable_at_fourth_order() -> None:
    c = certify(model(mu_s2=-2, C=4))
    # At h=1, S=0 the singlet curvature is zero but relaxed-H quartic is 1-16/4<0.
    assert c.vacuum == "unstable" and c.local_classification == "unstable"
    for s in (1e-3, 1e-2):
        x = (1 - 4 * s * s / 2) / 2
        v = -x - 2 * s * s / 2 + x * x + 4 * x * s * s / 2 + s**4 / 4
        assert v < -0.25


def test_near_flat_matrices_curvatures_and_mass_ambiguity_are_unresolved() -> None:
    for p in [
        model(C=-2 + 1e-12, mu_s2=3),
        model(C=2 + 1e-12, mu_s2=-1),
        model(C=4, mu_s2=-2 + 1e-12),
        model(B=1e-20, C=0),
    ]:
        c = certify(p)
        assert c.vacuum == "unresolved" and not c.complete and c.passed is None, c.model_dump()


def test_nonstationary_vacuum_missing_inputs_and_finite_range() -> None:
    p = model().model_copy(update={"v_gev": 2})
    assert certify(p).local_classification == "not_stationary"
    c = certify(None)
    assert c.vacuum == "missing_input" and c.passed is None
    with pytest.raises(ValidationError):
        ScalarVacuumInput(scale_gev=100, v_gev=1)
    huge = model().model_copy(update={"mu_h2_gev2": 1e308, "v_gev": 1e154, "lambda_h": 1e-308})
    c = certify(huge)
    assert c.vacuum == "unresolved" and c.reasons


def test_full_m23_contract_identity_and_serialization() -> None:
    data = yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    spec = ModelSpec.model_validate(data)
    c = for_potential(spec.scalar_potential.resolve())
    assert c.vacuum == "global" and c.passed and c.declared_stationarity_residual < 1e-14, (
        c.model_dump()
    )
    other = c.inputs.model_copy(update={"lambda_s": 0.6})
    assert certify(other).parameter_sha256 != c.parameter_sha256
    other = c.inputs.model_copy(update={"scale_gev": 1000})
    assert certify(other).parameter_sha256 != c.parameter_sha256
    assert type(c).model_validate_json(c.model_dump_json()) == c
    assert (
        certify(c.inputs, VacuumSettings(relative_tolerance=1e-8)).settings.relative_tolerance
        == 1e-8
    )


def _numeric_extrema(p: ScalarVacuumInput) -> list[tuple[np.ndarray, float]]:
    # Independently work with actual radial fields (h,S), not exact x/y formulas.
    def value(z: np.ndarray) -> float:
        h, s = z
        return (
            -p.mu_h2_gev2 * h * h / 2
            + p.mu_s2_gev2 * s * s / 2
            + p.lambda_h * h**4 / 4
            + p.lambda_s * s**4 / 4
            + p.lambda_hs * h * h * s * s / 4
        )

    def gradient(z: np.ndarray) -> np.ndarray:
        h, s = z
        return np.array(
            [
                h * (-p.mu_h2_gev2 + p.lambda_h * h * h + p.lambda_hs * s * s / 2),
                s * (p.mu_s2_gev2 + p.lambda_s * s * s + p.lambda_hs * h * h / 2),
            ]
        )

    found = []
    for start in ([0, 0], [1, 0], [0, 1], [1, 1], [2, 0.3], [0.3, 2], [2, 2]):
        solution = root(gradient, np.array(start, dtype=float), tol=1e-11)
        if solution.success and np.max(abs(gradient(solution.x))) < 1e-8:
            found.append((solution.x, value(solution.x)))
    for start in ([1, 0.2], [0.2, 1], [2, 2]):
        minimum = minimize(
            value, np.array(start), jac=gradient, method="BFGS", options={"gtol": 1e-10}
        )
        found.append((minimum.x, float(minimum.fun)))
    return found


@pytest.mark.parametrize("C,b", [(0, 1), (0.8, -1), (3, -2), (-1.5, 2), (3, -1), (1.9, -1)])
def test_independent_radial_root_finding_and_optimisation(C: float, b: float) -> None:
    p = model(C=C, mu_s2=b)
    c = certify(p)
    assert c.boundedness == "bounded" and c.global_minimum_gev4 is not None
    numerical = _numeric_extrema(p)
    assert min(v for _, v in numerical) == pytest.approx(c.global_minimum_gev4, rel=1e-8, abs=1e-9)
    for e in c.extrema:
        h, s = math.sqrt(2 * e.x_gev2), math.sqrt(2 * e.y_gev2)
        assert any(np.allclose(abs(z), [h, s], rtol=1e-6, atol=1e-6) for z, _ in numerical), e.name


def test_unbounded_has_no_finite_global_minimum_or_global_minimizers() -> None:
    c = certify(model(B=-1, C=0, mu_s2=1))
    assert c.boundedness == "unbounded" and c.global_minimum_gev4 is None and c.minima == []
    assert c.vacuum == "local" and c.complete and not c.passed


def test_cache_is_input_bound_and_returns_independent_certificates() -> None:
    spec = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    )
    potential = spec.scalar_potential.resolve()
    a = for_potential(potential)
    a.reasons.append("mutated returned copy")
    b = for_potential(potential)
    assert "mutated returned copy" not in b.reasons
    assert for_potential(potential.model_copy(update={"lambda_s": -0.2})).passed is False


def test_report_and_cli_do_not_claim_uncomputed_certificates(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from adroit.orchestrator.cli import app
    from adroit.theory.report import report, study_section
    from adroit.parameter_space import library

    c = certify(model(mu_s2=-2, C=5))
    assert "singlet_axis" in report(c) and "global minimum V=-1.0" in report(c)
    assert "not" not in c.scope or "no" in c.scope
    assert study_section([]) == [] and "local" in "\n".join(study_section([c]))
    runner = CliRunner()
    response = runner.invoke(
        app,
        [
            "theory",
            "vacuum",
            "docs/examples/complete_scalar_singlet.yaml",
            "--out",
            str(tmp_path / "complete"),
        ],
    )
    assert response.exit_code == 0, response.output
    result = type(c).model_validate_json((tmp_path / "complete/vacuum.json").read_text())
    assert result.passed and result.inputs.lambda_s == 0.2
    source = tmp_path / "old.yaml"
    source.write_text(
        yaml.safe_dump(library.entry("higgs_portal_scalar").spec().model_dump(mode="json"))
    )
    response = runner.invoke(
        app, ["theory", "vacuum", str(source), "--out", str(tmp_path / "legacy")]
    )
    assert response.exit_code == 0, response.output
    result = type(c).model_validate_json((tmp_path / "legacy/vacuum.json").read_text())
    assert result.vacuum == "missing_input" and result.passed is None

"""Source convention, analytic limits, cutoff and failed-input regressions."""

from pathlib import Path
import math
import numpy as np
import pytest
from adroit.core.theory import ScalarVacuumInput
from adroit.core.running import RGRequest, SMMatching
from adroit.theory.scalar_running import beta, certify, for_potential


def potential(**kw):
    return ScalarVacuumInput(
        scale_gev=200,
        v_gev=246.22,
        mu_h2_gev2=7800,
        mu_s2_gev2=40000,
        lambda_h=0.13,
        lambda_s=0.2,
        lambda_hs=0.1,
        **kw,
    )


def request(upper=1e6, **kw):
    return RGRequest(
        matching=SMMatching(
            scale_gev=200,
            g_prime=0.358,
            g=0.65,
            g3=1.21,
            y_top=0.94,
            provenance="explicit illustrative inputs, not precision SM matching",
        ),
        upper_scale_gev=upper,
        scalar_matching="tree_level_identification",
        threshold_policy="full_theory_no_decoupling",
        matching_note="same tree-level contract identified with MSbar; no threshold corrections",
        **kw,
    )


def source_beta(z):
    a, g, c, y, H, S, P, m, n = z
    lam = 6 * H
    A = P / 2
    m2 = -m
    top = 6 * y * y - 4.5 * g * g - 1.5 * a * a
    B = np.array(
        [
            41 * a**3 / 6,
            -19 * g**3 / 6,
            -7 * c**3,
            4.5 * y**3 - 8 * c * c * y - 2.25 * g * g * y - 17 * a * a * y / 12,
            (
                4 * lam * lam
                + 12 * A * A
                - 36 * y**4
                + 2 * lam * top
                + 2.25 * a**4
                + 4.5 * g * g * a * a
                + 6.75 * g**4
            )
            / 6,
            8 * A * A + 18 * S * S,
            2 * (8 * A * A + 6 * A * S + A * top + 2 * A * lam),
            -(m2 * (2 * lam + top) + 2 * A * n),
            8 * m2 * A + 6 * n * S,
        ]
    ) / (16 * math.pi**2)
    return B


def test_published_equations_conversion():
    rng = np.random.default_rng(26)
    for _ in range(100):
        z = rng.uniform(-2, 2, 9)
        assert np.allclose(beta(z), source_beta(z), rtol=2e-14, atol=1e-15)


def test_decoupling_and_analytic_running():
    z = np.array([0.35, 0.65, 1.2, 0.95, 0.13, 0.2, 0.0, 2.0, 3.0])
    assert beta(z)[6] == 0
    p = potential().model_copy(update={"lambda_hs": 0})
    # Exactly zero portal is allowed; singlet stays decoupled despite SM running.
    c = certify(p, request(2000))
    assert c.passed
    t = math.log(10)
    final = c.trajectory[-1]
    assert final.lambda_s == pytest.approx(0.2 / (1 - 18 * 0.2 * t / (16 * math.pi**2)), rel=1e-9)
    for name, g, b in [("g_prime", 0.358, 41 / 6), ("g", 0.65, -19 / 6), ("g3", 1.21, -7)]:
        assert getattr(final, name) == pytest.approx(
            g / math.sqrt(1 - 2 * b * g * g * t / (16 * math.pi**2)), rel=1e-9
        )
    assert c.integration_error < 2e-8


def test_requested_cutoff_and_boundary():
    p = potential().model_copy(update={"lambda_s": 2.0})
    short = certify(p, request(300))
    long = certify(p, request(1e8))
    assert short.passed and long.status == "failed"
    assert 300 < long.first_crossing.scale_gev < 1e8
    assert long.first_crossing.criterion == "scalar_a0"
    assert short.parameter_sha256 != long.parameter_sha256
    end = long.first_crossing.scale_gev
    assert certify(p, request(end)).status in ("failed", "unresolved")


def test_missing_matching_pole_and_marginal():
    assert certify(None, None).status == "missing_input"
    assert (
        certify(potential().model_copy(update={"scale_gev": 100}), request()).status
        == "invalid_matching"
    )
    assert (
        certify(potential().model_copy(update={"lambda_s": 1e4}), request()).status == "pole_guard"
    )
    assert certify(potential().model_copy(update={"lambda_s": 0}), request()).status == "unresolved"
    with pytest.raises(ValueError):
        request(100)
    with pytest.raises(ValueError):
        SMMatching(scale_gev=200, g_prime=float("nan"), g=0.65, g3=1.2, y_top=0.9, provenance="x")


def test_cached_copies():
    from adroit.core.model_spec import ModelSpec
    import yaml

    resolved = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    ).scalar_potential.resolve()
    a = for_potential(resolved, request(1000))
    a.reasons.clear()
    assert for_potential(resolved, request(1000)).reasons


def test_overflow_is_reported_before_matrix_or_integration():
    p = potential().model_copy(update={"lambda_h": 1e308, "lambda_s": 1e308})
    assert certify(p, request()).status == "pole_guard"
    p = potential().model_copy(update={"scale_gev": 1e-200})
    r = request().model_copy(
        update={"matching": request().matching.model_copy(update={"scale_gev": 1e-200})}
    )
    assert certify(p, r).status == "invalid_matching"
    p = potential().model_copy(update={"scale_gev": 1e200})
    r = request().model_copy(
        update={
            "upper_scale_gev": 1e201,
            "matching": request().matching.model_copy(update={"scale_gev": 1e200}),
        }
    )
    assert certify(p, r).status == "invalid_matching"

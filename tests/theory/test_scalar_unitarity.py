"""Complete basis, independent potential differentiation and source-convention checks."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import sympy as sy
import yaml
from pydantic import ValidationError

from adroit.core.model_spec import ModelSpec
from adroit.core.theory import ScalarVacuumInput, UnitaritySettings, ScalarUnitarityCertificate
from adroit.theory.scalar_unitarity import certify, for_potential, channel_basis, CHANNEL_IDS


def inputs(H: float = 0.13, S: float = 0.2, HS: float = 0.1) -> ScalarVacuumInput:
    return ScalarVacuumInput(
        scale_gev=100, v_gev=1, mu_h2_gev2=H, mu_s2_gev2=1, lambda_h=H, lambda_s=S, lambda_hs=HS
    )


def independent_matrix(p: ScalarVacuumInput) -> np.ndarray:
    phi = sy.symbols("h z x y s")
    total = sum(f * f for f in phi[:4])
    potential = (
        p.lambda_h * total**2 / 4
        + p.lambda_s * phi[4] ** 4 / 4
        + p.lambda_hs * total * phi[4] ** 2 / 4
    )
    pairs = [(i, j) for i in range(5) for j in range(i, 5)]
    # Different construction: differentiate the polynomial, then integrate the contact partial wave.
    vertices = np.array(
        [
            [float(sy.diff(potential, phi[i], phi[j], phi[k], phi[m])) for k, m in pairs]
            for i, j in pairs
        ]
    )
    sym = np.array([1 / math.sqrt(2) if i == j else 1 for i, j in pairs])
    return -vertices * np.outer(sym, sym) / (16 * math.pi)


@pytest.mark.parametrize("H,S,HS", [(0.13, 0.2, 0.1), (1.2, 2.3, -3), (-0.4, -0.2, 1.8), (0, 0, 0)])
def test_separate_derivative_matrix_matches_full_15_channel_result(
    H: float, S: float, HS: float
) -> None:
    p = inputs(H, S, HS)
    c = certify(p)
    assert len(c.channels) == 15 and len(c.eigenvalues_a0) == 15 and c.complete
    assert np.allclose(c.a0_matrix, independent_matrix(p), rtol=1e-14, atol=1e-15)
    assert c.eigenpair_residual < 1e-13 and c.orthogonality_residual < 1e-13
    by_id = {b.id: i for i, b in enumerate(c.channels)}
    assert c.amplitude_matrix[by_id["4:4"]][by_id["4:4"]] == pytest.approx(-3 * S)
    assert c.amplitude_matrix[by_id["0:0"]][by_id["4:4"]] == pytest.approx(-HS / 2)
    assert c.amplitude_matrix[by_id["0:4"]][by_id["0:4"]] == pytest.approx(-HS)


@pytest.mark.parametrize("H,S", [(0.13, 0.2), (1, 0), (0, 1), (-0.2, 0.3)])
def test_independent_analytic_decoupling_eigenvalues_and_sm_limit(H: float, S: float) -> None:
    c = certify(inputs(H, S, 0))
    expected = sorted(
        [-6 * H / (16 * math.pi), -3 * S / (16 * math.pi)] + [-2 * H / (16 * math.pi)] * 9 + [0] * 4
    )
    assert c.eigenvalues_a0 == pytest.approx(expected, rel=1e-13, abs=1e-15)
    assert certify(inputs(H=4 * math.pi / 3 * 0.999, S=0, HS=0)).passed
    assert certify(inputs(H=4 * math.pi / 3 * 1.001, S=0, HS=0)).passed is False


@pytest.mark.parametrize("H,S,HS", [(0.13, 0.2, 0.1), (1.8, 2.1, 4), (-2, 3, -7)])
def test_goodsell_staub_eq25_after_explicit_coefficient_conversion(
    H: float, S: float, HS: float
) -> None:
    c = certify(inputs(H, S, HS))
    # Source V=Hsrc |H|^4/2 + Ssrc S^4/2 + HS |H|^2 S^2/2.
    Hsrc, Ssrc = 2 * H, S / 2
    disc = math.sqrt(4 * HS**2 + 36 * Ssrc**2 + 9 * Hsrc**2 - 36 * Ssrc * Hsrc)
    source = sorted(
        [
            -x / (16 * math.pi)
            for x in [(6 * Ssrc + 3 * Hsrc + disc) / 2, (6 * Ssrc + 3 * Hsrc - disc) / 2]
            + [Hsrc] * 9
            + [HS] * 4
        ]
    )
    assert c.eigenvalues_a0 == pytest.approx(source, rel=1e-13, abs=1e-15)


def test_portal_only_eigenvalues_basis_permutations_and_species_relabel() -> None:
    p = inputs(0, 0, 3)
    c = certify(p)
    expected = sorted([-3 / (16 * math.pi)] * 5 + [3 / (16 * math.pi)] + [0] * 9)
    assert c.eigenvalues_a0 == pytest.approx(expected, abs=1e-15)
    rng = np.random.default_rng(25)
    perm = rng.permutation(15)
    shuffled = certify(p, channels=[CHANNEL_IDS[i] for i in perm])
    assert np.allclose(shuffled.a0_matrix, np.array(c.a0_matrix)[np.ix_(perm, perm)], atol=1e-15)
    assert shuffled.eigenvalues_a0 == pytest.approx(c.eigenvalues_a0, abs=1e-15)
    renamed = certify(p.model_copy(update={"higgs_field": "doublet", "singlet_field": "dark"}))
    assert (
        renamed.eigenvalues_a0 == c.eigenvalues_a0
        and renamed.parameter_sha256 != c.parameter_sha256
    )
    # Real-doublet species rotations/permutations also preserve the full spectrum.
    field_perm = [3, 0, 2, 1, 4]
    rotated = []
    for b in c.channels:
        i, j = sorted(field_perm[k] for k in b.species)
        rotated.append(CHANNEL_IDS.index(f"{i}:{j}"))
    assert np.linalg.eigvalsh(np.array(c.a0_matrix)[np.ix_(rotated, rotated)]) == pytest.approx(
        c.eigenvalues_a0, abs=1e-15
    )


@pytest.mark.parametrize("factor,status", [(0.999, "passed"), (1, "unresolved"), (1.001, "failed")])
def test_singlet_boundary_and_heuristic_not_a_certificate(factor: float, status: str) -> None:
    c = certify(inputs(S=8 * math.pi / 3 * factor, HS=0))
    assert c.status == status
    if status == "unresolved":
        assert c.passed is None and not c.complete
    else:
        assert c.passed is (status == "passed")
    assert certify(inputs(S=10, HS=0)).passed is False  # 10 < 4*pi, but fails actual partial wave.


def test_omitted_goldstones_or_singlet_and_invalid_bases_cannot_pass() -> None:
    p = inputs()
    for subset in (["0:0", "0:4", "4:4"], list(CHANNEL_IDS[:-1]), []):
        c = certify(p, channels=subset)
        assert c.status == "incomplete_basis" and c.passed is None and not c.complete
        assert c.missing_channel_ids
    with pytest.raises(ValueError):
        certify(p, channels=["0:0", "0:0"])
    with pytest.raises(ValueError):
        certify(p, channels=["unknown"])
    assert certify(None).status == "missing_input"
    with pytest.raises(ValidationError):
        ScalarVacuumInput(scale_gev=100, lambda_h=0.1)


def test_potential_binding_unused_parameters_scope_and_cache_independence() -> None:
    spec = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    )
    p = spec.scalar_potential.resolve()
    c = for_potential(p)
    assert c.passed and c.inputs.lambda_s == 0.2 and "finite-energy" in c.scope
    changed = for_potential(p.model_copy(update={"scale_gev": 1000}))
    assert (
        changed.eigenvalues_a0 == c.eigenvalues_a0
        and changed.parameter_sha256 != c.parameter_sha256
    )
    mass = for_potential(p.model_copy(update={"mu_s2_gev2": p.mu_s2_gev2 + 1}))
    assert mass.eigenvalues_a0 == c.eigenvalues_a0 and mass.parameter_sha256 != c.parameter_sha256
    c.reasons.append("mutated cache output")
    assert "mutated cache output" not in for_potential(p).reasons
    assert ScalarUnitarityCertificate.model_validate_json(changed.model_dump_json()) == changed
    basis = channel_basis(changed.inputs)
    assert sum(b.identical for b in basis) == 5 and all(
        b.normalization == pytest.approx(1 / math.sqrt(2)) for b in basis if b.identical
    )


def test_extreme_range_refuses_and_settings_are_explicit() -> None:
    c = certify(inputs(S=1e308))
    assert c.status == "unresolved" and c.passed is None and not c.complete
    assert (
        certify(inputs(), UnitaritySettings(relative_tolerance=1e-8)).settings.relative_tolerance
        == 1e-8
    )

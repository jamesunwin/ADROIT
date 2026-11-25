"""Full 15-channel scalar contact matrix in the gaugeless high-energy limit.

V4=lambda_H/4*(sum_a phi_a²)²+lambda_S/4*S⁴+lambda_HS/4*(sum_a phi_a²)*S².
Only quartic vertices survive this declared limit. This does not bound finite-s
exchange effects or perform RG evolution.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations_with_replacement
import math

import numpy as np

from adroit.core.evidence import content_hash
from adroit.core.model_contracts import ResolvedScalarPotential
from adroit.core.theory import (
    ScalarVacuumInput,
    ScalarPairChannel,
    UnitaritySettings,
    ScalarUnitarityCertificate,
)

PAIRS = tuple(combinations_with_replacement(range(5), 2))
CHANNEL_IDS = tuple(f"{i}:{j}" for i, j in PAIRS)


def channel_basis(inputs: ScalarVacuumInput) -> list[ScalarPairChannel]:
    """Every symmetric pair of four real H components and S, including Goldstones."""
    labels = [f"{inputs.higgs_field}.{name}" for name in ("h", "G0", "G1", "G2")] + [
        inputs.singlet_field
    ]
    return [
        ScalarPairChannel(
            id=f"{i}:{j}",
            species=(i, j),
            labels=(labels[i], labels[j]),
            normalization=1 / math.sqrt(2) if i == j else 1.0,
            identical=i == j,
        )
        for i, j in PAIRS
    ]


def _vertex(inputs: ScalarVacuumInput, indices: tuple[int, int, int, int]) -> float:
    counts = Counter(indices)
    if 4 in counts:
        if counts[4] == 4:
            return 6 * inputs.lambda_s
        return inputs.lambda_hs if counts[4] == 2 and len(counts) == 2 else 0.0
    i, j, k, last = indices
    return (
        2
        * inputs.lambda_h
        * (int(i == j and k == last) + int(i == k and j == last) + int(i == last and j == k))
    )


def _matrix(inputs: ScalarVacuumInput, basis: list[ScalarPairChannel]) -> np.ndarray:
    return np.array(
        [
            [
                -_vertex(inputs, (*a.species, *b.species)) * a.normalization * b.normalization
                for b in basis
            ]
            for a in basis
        ],
        dtype=float,
    )


def _diagonalize(c: ScalarUnitarityCertificate, matrix: np.ndarray) -> None:
    if not np.isfinite(matrix).all():
        raise ArithmeticError("contact matrix overflows the finite numerical range")
    a0 = matrix / (16 * math.pi)
    if np.any((matrix != 0) & (a0 == 0)):
        raise ArithmeticError("partial-wave conversion loses a nonzero matrix entry")
    values, vectors = np.linalg.eigh(a0)
    if not np.isfinite(values).all() or not np.isfinite(vectors).all():
        raise ArithmeticError("nonfinite eigensystem")
    scale = max(float(np.max(abs(a0))), np.finfo(float).tiny)
    residual = float(np.max(abs(a0 @ vectors - vectors * values)) / scale)
    orthogonal = float(np.max(abs(vectors.T @ vectors - np.eye(len(values)))))
    c.amplitude_matrix = matrix.tolist()
    c.a0_matrix = a0.tolist()
    c.eigenvalues_a0 = values.tolist()
    c.eigenvectors = vectors.T.tolist()
    c.maximum_abs_a0 = float(np.max(abs(values)))
    c.boundary_margin = 0.5 - c.maximum_abs_a0
    c.eigenpair_residual = residual
    c.orthogonality_residual = orthogonal
    if max(residual, orthogonal) > c.settings.relative_tolerance:
        c.status = "unresolved"
        c.reasons.append("eigensystem residual exceeds declared numerical resolution")
    elif abs(c.boundary_margin) <= c.settings.relative_tolerance * max(0.5, c.maximum_abs_a0):
        c.status = "unresolved"
        c.reasons.append("largest partial wave is at/near the declared unitarity boundary")
    else:
        c.complete = True
        c.passed = c.boundary_margin > 0
        c.status = "passed" if c.passed else "failed"


def certify(
    inputs: ScalarVacuumInput | None,
    settings: UnitaritySettings | None = None,
    channels: list[str] | None = None,
) -> ScalarUnitarityCertificate:
    """Build and check the complete basis; explicit omissions never yield a pass."""
    c = ScalarUnitarityCertificate(
        inputs=inputs,
        settings=settings or UnitaritySettings(),
        required_channel_ids=list(CHANNEL_IDS),
        equations={
            "V4": "lambda_H*(sum_a phi_a^2)^2/4+lambda_S*S^4/4+lambda_HS*(sum_a phi_a^2)*S^2/4",
            "tensor_H": "d^4V_H=2*lambda_H*(delta_ij*delta_kl+delta_ik*delta_jl+delta_il*delta_jk)",
            "tensor_S": "d^4V_SS=6*lambda_S; d^4V_phi_a_phi_b_SS=lambda_HS*delta_ab",
            "partial_wave": "a0_ab=(1/(32*pi))*integral_-1^1 M_ab dcos(theta)=M_ab/(16*pi)",
            "analytic_blocks": "T singlet block [[6*lambda_H,lambda_HS],[lambda_HS,3*lambda_S]]; 2*lambda_H (x9), lambda_HS (x4); M=-T",
            "source_conversion": "Goodsell-Staub Eq24: lambda_H_source=2*lambda_H, lambda_S_source=lambda_S/2, lambda_HS_source=lambda_HS",
        },
    )
    if inputs is None:
        c.reasons = ["complete scalar potential, declared scale and vacuum inputs are required"]
        return c
    c.parameter_sha256 = content_hash(inputs.model_dump(mode="json"))
    ids = list(CHANNEL_IDS) if channels is None else channels
    if len(set(ids)) != len(ids) or any(i not in CHANNEL_IDS for i in ids):
        raise ValueError("basis must contain unique known scalar-pair IDs")
    c.missing_channel_ids = [i for i in CHANNEL_IDS if i not in ids]
    by_id = {b.id: b for b in channel_basis(inputs)}
    c.channels = [by_id[i] for i in ids]
    if not ids:
        c.status = "incomplete_basis"
        c.reasons = ["all scalar-pair channels were omitted"]
        return c
    try:
        _diagonalize(c, _matrix(inputs, c.channels))
    except (ArithmeticError, np.linalg.LinAlgError) as error:
        c.complete = False
        c.passed = None
        c.status = "unresolved"
        c.reasons.append(f"numerical matrix calculation unresolved: {error}")
    if c.missing_channel_ids:
        c.complete = False
        c.passed = None
        c.status = "incomplete_basis"
        c.reasons.append("omitted scalar channels prevent a certificate for the complete potential")
    return c


def for_potential(potential: ResolvedScalarPotential) -> ScalarUnitarityCertificate:
    """Certify the unchanged full declared point, with input-bound cache and independent copy."""
    inputs = ScalarVacuumInput.model_validate(
        potential.model_dump(exclude={"higgs_mass_gev", "singlet_mass_gev", "convention"})
    )
    return _cached(inputs.model_dump_json()).model_copy(deep=True)


@lru_cache(maxsize=2048)
def _cached(payload: str) -> ScalarUnitarityCertificate:
    return certify(ScalarVacuumInput.model_validate_json(payload))

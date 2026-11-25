"""Scoped tree-level scalar certificates, independent of experimental verdicts."""

from __future__ import annotations

from typing import Literal
from pydantic import Field
from adroit.core.state import StrictModel


class ScalarVacuumInput(StrictModel):
    """Complete Z2 potential; coefficients may describe an unstable declared vacuum.

    x=H†H, y=S²/2: V=-mu_h2*x+mu_s2*y+lambda_h*x²+lambda_hs*x*y+lambda_s*y².
    This theory input does not widen the positive-mass numerical-engine contract.
    """

    scale_gev: float = Field(gt=0, allow_inf_nan=False)
    v_gev: float = Field(ge=0, allow_inf_nan=False)
    mu_h2_gev2: float = Field(allow_inf_nan=False)
    mu_s2_gev2: float = Field(allow_inf_nan=False)
    lambda_h: float = Field(allow_inf_nan=False)
    lambda_s: float = Field(allow_inf_nan=False)
    lambda_hs: float = Field(allow_inf_nan=False)
    singlet_vev_gev: Literal[0.0] = 0.0
    higgs_field: str = "H"
    singlet_field: str = "S"


class VacuumSettings(StrictModel):
    """Conservative relative resolution of signs, stationarity and depth comparisons; the band in ln P (the
    probability of a bubble in our past light cone) left unresolved for a metastable vacuum's prefactor."""

    relative_tolerance: float = Field(default=1e-10, gt=0, le=1e-4, allow_inf_nan=False)
    lifetime_margin: float = Field(default=10.0, ge=0, allow_inf_nan=False)


class ScalarExtremum(StrictModel):
    """One physical gauge orbit; y>0 includes the two Z2-related singlet signs."""

    name: str
    x_gev2: float = Field(ge=0, allow_inf_nan=False)
    y_gev2: float = Field(ge=0, allow_inf_nan=False)
    potential_gev4: float = Field(allow_inf_nan=False)
    exact_coordinates: list[str]
    exact_potential: str
    local_classification: str
    stationarity_residual: float = Field(ge=0, allow_inf_nan=False)
    singlet_sign_multiplicity: int = 1
    lower_than_declared: bool = False


class StationaryFamily(StrictModel):
    """Complete affine stationary family in x/y, intersected with the quadrant."""

    name: str
    dimension: int = Field(ge=1, le=2)
    equations: list[str]
    anchor_exact: list[str]
    directions_exact: list[list[str]]
    parameter_low_exact: str | None = None
    parameter_high_exact: str | None = None
    domain: str = "x>=0, y>=0; physical S=±sqrt(2y); gauge-equivalent H orientations identified"
    potential_gev4: float = Field(allow_inf_nan=False)
    exact_potential: str


class RunawayDirection(StrictModel):
    """Analytic physical ray with a negative leading polynomial coefficient."""

    direction_exact: list[str]
    quartic_exact: str
    quadratic_exact: str
    leading: Literal["quartic", "quadratic"]
    explanation: str


class VacuumDecay(StrictModel):
    """Zero-temperature decay of a metastable declared vacuum (``theory.vacuum_decay``): the O(4) bounce found
    by path deformation and the probability ln P = ln[(Γ/V) t_U⁴] of a bubble in our past light cone."""

    true_vacuum: str
    false_field_gev: list[float]
    true_field_gev: list[float]
    bounce_action: float | None = Field(default=None, allow_inf_nan=False)
    action_upper_bound: float | None = Field(default=None, allow_inf_nan=False)
    action_lower_bound: float | None = Field(default=None, allow_inf_nan=False)
    decided_by: str = ""
    radius_gev_inv: float | None = Field(default=None, allow_inf_nan=False)
    log_probability: float | None = Field(default=None, allow_inf_nan=False)
    margin: float = 10.0
    status: Literal["long_lived", "short_lived", "unresolved"] = "unresolved"
    converged: bool = False
    iterations: int = 0
    virial_mismatch: float | None = Field(default=None, allow_inf_nan=False)
    path_gev: list[list[float]] = Field(default_factory=list)
    method: str = ("O(4) bounce by path deformation; Γ/V ≈ (S_E/2π)² R⁻⁴ e^(−S_E); P = (Γ/V) t_U⁴, "
                   "t_U = 13.787 Gyr; prefactor determinant not computed")
    reasons: list[str] = Field(default_factory=list)


class ScalarVacuumCertificate(StrictModel):
    """Numerical/theory claim with explicit scope, completeness and parameter identity."""

    kind: Literal["scalar_tree_vacuum"] = "scalar_tree_vacuum"
    algorithm_version: Literal[1, 2] = 2
    inputs: ScalarVacuumInput | None = None
    parameter_sha256: str = ""
    settings: VacuumSettings = Field(default_factory=VacuumSettings)
    complete: bool = False
    passed: bool | None = None
    boundedness: Literal["bounded", "unbounded", "unresolved", "missing_input"] = "missing_input"
    quartic: Literal["strict", "marginal", "unbounded", "unresolved", "missing_input"] = (
        "missing_input"
    )
    vacuum: Literal["global", "degenerate", "metastable", "short_lived", "local", "unstable", "unresolved",
                    "missing_input"] = "missing_input"
    local_classification: str = "unknown"
    declared_x_gev2: float | None = Field(default=None, allow_inf_nan=False)
    declared_potential_gev4: float | None = Field(default=None, allow_inf_nan=False)
    declared_stationarity_residual: float | None = Field(default=None, allow_inf_nan=False)
    global_minimum_gev4: float | None = Field(default=None, allow_inf_nan=False)
    minima: list[str] = Field(default_factory=list)
    extrema: list[ScalarExtremum] = Field(default_factory=list)
    families: list[StationaryFamily] = Field(default_factory=list)
    flat_directions_exact: list[list[str]] = Field(default_factory=list)
    runaway: RunawayDirection | None = None
    decay: VacuumDecay | None = None
    equations: dict[str, str] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    domain: str = "entire nonnegative quadrant x=H†H, y=S²/2; fixed coefficients at declared scale"
    scope: str = ("tree-level scalar potential only; a metastable vacuum's zero-temperature tunnelling lifetime "
                  "(tree-level bounce); no loop/RG, finite-temperature history or full-theory certificate")
    references: list[str] = Field(default_factory=lambda: ["https://arxiv.org/abs/1205.3781",
                                                           "https://doi.org/10.1103/PhysRevD.15.2929",
                                                           "https://arxiv.org/abs/1109.4189"])


class ScalarPairChannel(StrictModel):
    """Normalized unordered two-body channel of the O(4) Higgs and real singlet."""

    id: str
    species: tuple[int, int]
    labels: tuple[str, str]
    normalization: float = Field(gt=0, allow_inf_nan=False)
    identical: bool


class UnitaritySettings(StrictModel):
    """Relative resolution for boundary decisions and numerical eigensystem checks."""

    relative_tolerance: float = Field(default=1e-10, gt=0, le=1e-4, allow_inf_nan=False)


class ScalarUnitarityCertificate(StrictModel):
    """Complete scalar-channel high-energy test, separate from heuristic caps."""

    kind: Literal["scalar_high_energy_unitarity"] = "scalar_high_energy_unitarity"
    algorithm_version: Literal[1] = 1
    inputs: ScalarVacuumInput | None = None
    parameter_sha256: str = ""
    settings: UnitaritySettings = Field(default_factory=UnitaritySettings)
    status: Literal["passed", "failed", "unresolved", "missing_input", "incomplete_basis"] = (
        "missing_input"
    )
    complete: bool = False
    passed: bool | None = None
    required_channel_ids: list[str] = Field(default_factory=list)
    channels: list[ScalarPairChannel] = Field(default_factory=list)
    missing_channel_ids: list[str] = Field(default_factory=list)
    amplitude_matrix: list[list[float]] = Field(default_factory=list)
    a0_matrix: list[list[float]] = Field(default_factory=list)
    eigenvalues_a0: list[float] = Field(default_factory=list)
    eigenvectors: list[list[float]] = Field(default_factory=list)  # one eigenvector per row
    maximum_abs_a0: float | None = Field(default=None, allow_inf_nan=False)
    boundary_margin: float | None = Field(default=None, allow_inf_nan=False)  # .5-max|a0|
    eigenpair_residual: float | None = Field(default=None, allow_inf_nan=False)
    orthogonality_residual: float | None = Field(default=None, allow_inf_nan=False)
    criterion: str = "all |Re(a0_i)| < 1/2; within numerical boundary tolerance unresolved"
    normalization: str = (
        "|ij>/sqrt(1+delta_ij); M_ij,kl=-d^4V/(sqrt(1+delta_ij)*sqrt(1+delta_kl)); a0=M/(16*pi)"
    )
    equations: dict[str, str] = Field(default_factory=dict)
    scope: str = "tree-level high-energy scalar-potential contact limit at fixed declared scale; no gauge/Yukawa, finite-energy exchanges, running, vacuum or full-theory unitarity claim"
    domain: str = "formal high-energy limit s/m_i^2 -> infinity with fixed coefficients; four real doublet components plus S; all unordered J=0 pairs"
    reasons: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=lambda: ["https://arxiv.org/abs/1805.07306"])

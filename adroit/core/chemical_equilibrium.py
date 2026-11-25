"""Typed, scoped chemical-equilibrium prerequisite and rate diagnostics."""

from __future__ import annotations
from typing import Literal
from pydantic import Field, model_validator
from adroit.core.state import StrictModel
from adroit.parameter_space.classes import Point


class SourceBornSettings(StrictModel):
    """Explicit literature energy-cut prescription for the retained Abelian component."""

    scheme: Literal["garny_1705_appendix_A_full_angle_vacuum_mass_MB"]
    energy_cuts_gev: tuple[Literal[0.1], Literal[0.5], Literal[5.0]] = (0.1, 0.5, 5.0)
    scope: Literal["retained_abelian_component_only"]


class PlasmaSettings(StrictModel):
    """An explicit request for the leading-order plasma rates (``theory.plasma_rates``): thermal masses on every light
    or charged leg, quantum statistics for the light particles, the thermal masses scaled by ½ and 2."""

    scheme: Literal["leading_order_asymptotic_masses_quantum_statistics"]
    scales: tuple[Literal[0.5], Literal[1.0], Literal[2.0]] = (0.5, 1.0, 2.0)


class ConversionRequest(StrictModel):
    """Explicit interval and Born regulator variations; no assumed freeze-out window."""

    x_low: float = Field(gt=3, le=100, allow_inf_nan=False)
    x_high: float = Field(gt=3, le=200, allow_inf_nan=False)
    samples: int = Field(default=17, ge=9, le=101)
    minimum_root_excess_over_T: tuple[float, float, float] = (0.1, 0.5, 1.0)
    angular_cuts: tuple[float, float, float] = (0.9, 0.95, 0.98)
    rate_relative_uncertainty: float = Field(ge=0, lt=1, allow_inf_nan=False)
    include_odd_sector: bool = False
    source_born: SourceBornSettings | None = None
    approximation: Literal["unbroken_hypercharge_vacuum_Born_MB"]
    # the leading-order plasma rates (M27, 2026-10-19); left out when absent, so earlier requests keep their identity
    plasma: PlasmaSettings | None = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def _limits(self) -> ConversionRequest:
        if self.x_high <= self.x_low:
            raise ValueError("x_high must exceed x_low")
        if self.minimum_root_excess_over_T != (0.1, 0.5, 1.0) or self.angular_cuts != (
            0.9,
            0.95,
            0.98,
        ):
            raise ValueError("only the validated regulator variation bank is supported")
        return self


class ConversionInput(StrictModel):
    """Existing t-channel coordinates and exact selected family."""

    point: Point
    partner: str
    majorana: bool
    g_prime: float = Field(gt=0, allow_inf_nan=False)
    request: ConversionRequest | None = None
    # the relic solver's freeze-out x_f at this point: the window must bracket it and starts there (audit M11);
    # left out of the serialised form when absent, so earlier inputs keep their identity
    freeze_out_x: float | None = Field(default=None, gt=0, allow_inf_nan=False, exclude_if=lambda v: v is None)


class ConversionRatePoint(StrictModel):
    """Decay, scattering and thermal-population contributions in GeV."""

    x: float
    temperature_gev: float
    hubble_gev: float
    partner_to_chi_equilibrium_ratio: float
    decay_down_gev: float
    inverse_decay_up_gev: float
    scatter_up_gev: dict[str, float]
    relaxation_over_h: float
    conservative_over_h: float
    regulator_relative_spread: float
    quadrature_relative_difference: float
    odd_sector_sigma_v_gev2: float | None = None
    odd_sector_relaxation_gev: float | None = None
    odd_sector_quadrature_difference: float | None = None
    regulator_rates_over_h: dict[str, float] = Field(default_factory=dict)
    upper_envelope_over_h: float | None = None


class PlasmaRatePoint(StrictModel):
    """The leading-order plasma relaxation rate over H at one temperature, for each scale of the thermal masses."""

    x: float
    temperature_gev: float
    hubble_gev: float
    rates_over_h: dict[str, float]
    odd_sector_relaxation_gev: float | None = None


class ChemicalEquilibriumCertificate(StrictModel):
    """Conditional Born diagnostic separated from the physical prerequisite."""

    kind: Literal["coannihilation_chemical_equilibrium"] = "coannihilation_chemical_equilibrium"
    algorithm_version: Literal[1, 2, 3, 4, 5] = 1
    inputs: ConversionInput
    parameter_sha256: str = ""
    status: Literal[
        "passed", "failed", "unresolved", "missing_input", "missing_rates", "outside_domain"
    ] = "missing_input"
    complete: bool = False
    passed: bool | None = None
    physical_prerequisite: Literal["pending", "failed", "supported", "unresolved"] = "pending"
    born_diagnostic_passed: bool | None = None
    component_prerequisite: Literal["supported", "unsupported", "unresolved"] | None = None
    uncomputed_corrections: list[str] = Field(default_factory=list)
    minimum_relaxation_over_h: float | None = None
    calibrated_threshold: float | None = None
    rates: list[ConversionRatePoint] = Field(default_factory=list)
    plasma_rates: list[PlasmaRatePoint] = Field(default_factory=list, exclude_if=lambda v: not v)
    required_channels: list[str] = Field(
        default_factory=lambda: ["phi<->chi e", "chi B<->phi e", "chi ebar<->phi B"]
    )
    missing_channels: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    approximation: str = "leading y^2 vacuum Born conversion rates with MB kinetic distributions; soft and collinear phase-space cuts varied explicitly"
    scope: str = "conditional chemical-relaxation diagnostic for eR Majorana hypercharge component; finite-temperature inclusive rates, kinetic equilibrium, reheating/initial equilibrium and late cosmology are not certified"
    criterion: str = "minimum (1+n_phi,tot_eq/n_chi_eq)*Gamma_down/H over explicit sampled freeze-out interval; finite probes do not bound between-node extrema; finite-case calibration, no uniform relic error guarantee"
    references: list[str] = Field(default_factory=lambda: ["https://arxiv.org/abs/1705.09292"])

"""Explicit one-loop inputs and results; no implicit UV scale or SM matching."""

from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator
from adroit.core.state import StrictModel
from adroit.core.theory import ScalarVacuumInput


class SMMatching(StrictModel):
    """User-supplied MSbar gauge/top inputs, with non-GUT hypercharge normalization."""

    scale_gev: float = Field(gt=0, allow_inf_nan=False)
    g_prime: float = Field(ge=0, allow_inf_nan=False)
    g: float = Field(ge=0, allow_inf_nan=False)
    g3: float = Field(ge=0, allow_inf_nan=False)
    y_top: float = Field(ge=0, allow_inf_nan=False)
    provenance: str = Field(min_length=1)
    scheme: Literal["MSbar"] = "MSbar"
    hypercharge: Literal["Q=T3+Y; g_prime not GUT normalized"] = (
        "Q=T3+Y; g_prime not GUT normalized"
    )


class RGRequest(StrictModel):
    """Declared full-theory treatment; matching quality is not upgraded by running."""

    matching: SMMatching
    upper_scale_gev: float = Field(gt=0, allow_inf_nan=False)
    scalar_matching: Literal["declared_MSbar", "tree_level_identification"]
    threshold_policy: Literal["full_theory_no_decoupling"]
    matching_note: str = Field(min_length=1)
    relative_tolerance: float = Field(default=1e-8, ge=1e-12, le=1e-4)
    absolute_tolerance: float = Field(default=1e-11, ge=1e-15, le=1e-6)
    comparison_tolerance: float = Field(default=2e-6, ge=1e-10, le=1e-3)
    max_log_step: float = Field(default=0.05, gt=0, le=0.2)

    @model_validator(mode="after")
    def _ordered(self) -> RGRequest:
        if self.upper_scale_gev <= self.matching.scale_gev:
            raise ValueError("upper scale must exceed the explicit matching scale")
        return self


class RunningPoint(StrictModel):
    """One trajectory point in ADROIT's potential convention and GeV units."""

    scale_gev: float = Field(allow_inf_nan=False)
    g_prime: float = Field(allow_inf_nan=False)
    g: float = Field(allow_inf_nan=False)
    g3: float = Field(allow_inf_nan=False)
    y_top: float = Field(allow_inf_nan=False)
    lambda_h: float = Field(allow_inf_nan=False)
    lambda_s: float = Field(allow_inf_nan=False)
    lambda_hs: float = Field(allow_inf_nan=False)
    mu_h2_gev2: float = Field(allow_inf_nan=False)
    mu_s2_gev2: float = Field(allow_inf_nan=False)
    boundedness_margin: float = Field(allow_inf_nan=False)
    scalar_a0_margin: float = Field(allow_inf_nan=False)
    gauge_yukawa_margin: float = Field(allow_inf_nan=False)


class RGCrossing(StrictModel):
    """First boundary of the requested scoped running test."""

    scale_gev: float = Field(allow_inf_nan=False)
    criterion: str
    log_scale_difference: float = Field(allow_inf_nan=False)


class ScalarRGCertificate(StrictModel):
    """Running quartic boundedness/perturbativity, not a quantum-vacuum result."""

    kind: Literal["scalar_one_loop_running"] = "scalar_one_loop_running"
    algorithm_version: Literal[1] = 1
    inputs: ScalarVacuumInput | None = None
    request: RGRequest | None = None
    parameter_sha256: str = ""
    status: Literal[
        "passed", "failed", "unresolved", "invalid_matching", "pole_guard", "missing_input"
    ] = "missing_input"
    passed: bool | None = None
    complete: bool = False
    trajectory: list[RunningPoint] = Field(default_factory=list)
    first_crossing: RGCrossing | None = None
    integration_error: float | None = None
    error_construction: str = "DOP853 versus independent Radau integration; max |delta z|/(1+|z|), mass z=mu^2/matching_scale^2; diagnostic, not rigorous error bound"
    reasons: list[str] = Field(default_factory=list)
    criteria: dict[str, str] = Field(
        default_factory=lambda: {
            "boundedness": "lambda_H>0, lambda_S>0, lambda_HS+2*sqrt(lambda_H*lambda_S)>0; marginal boundary unresolved",
            "scalar_perturbativity": "running scalar contact |a0|<1/2, same complete basis as M25",
            "gauge_yukawa": "g_prime^2,g^2,g3^2,y_top^2 < 4*pi; declared heuristic loop-expansion cap",
            "pole_guard": "stop at dimensionless magnitude 1000; no finite Landau-pole location claimed",
        }
    )
    convention: str = "Gonderinger lambda=6*lambda_H, a2=lambda_HS/2, b4=lambda_S, m2=-mu_H^2, b2=mu_S^2; Appendix C Eqs29-37; top Yukawa only"
    scope: str = "one-loop MSbar full-theory running with declared matching and no decoupling; running quartic criteria only, no quantum vacuum, tunnelling, finite-temperature or precision SM matching claim"
    references: list[str] = Field(default_factory=lambda: ["https://arxiv.org/abs/0910.3167"])

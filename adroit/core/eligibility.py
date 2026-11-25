"""Point-scoped physical eligibility, separate from NR statistical ranking."""
from __future__ import annotations
from typing import Literal
from pydantic import Field
from adroit.core.certificate import Certificate
from adroit.core.state import StrictModel
from adroit.parameter_space.classes import Point
from adroit.parameter_space.scan import PointResult
from adroit.parameter_space.physical_fit import FitSettings,PhysicalFit

class EligibilitySettings(StrictModel):
    """Hard limits on additional physical calculations in one signal run."""
    enabled: bool = True
    max_candidates: int = Field(default=32,ge=1,le=1000)
    fit_settings: FitSettings = Field(default_factory=FitSettings)

class CandidateEligibility(StrictModel):
    """Decision for one fitted hypothesis, not all branches of its model."""
    label: str
    status: Literal['eligible','excluded_point','pending'] = 'pending'
    model_sha256: str = ''
    catalog_reference: str = ''
    model_class: dict = Field(default_factory=dict)
    point: Point | None = None
    evaluation: PointResult | None = None
    physical_fit: PhysicalFit | None = None
    excluded_by: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    source_identity: str = ''
    source_sha256: str = ''
    constraints_origin: Literal['not_computed','fresh_track1_point','saved_exact_track1_point'] = 'not_computed'
    reused_result: str = ''
    # the reused result's bytes and its evidence's, as the reuse read them (one snapshot): the version the point is
    # of, reconciled with the run's captured inputs (the auditor's CX recheck, CY-01, 2026-11-01); absent in older results,
    # which kept only the path
    reused_result_sha256: str = Field(default='', exclude_if=lambda v: not v)
    reused_evidence_sha256: str = Field(default='', exclude_if=lambda v: not v)
    reuse_notes: list[str] = Field(default_factory=list)
    spectrum_relative_error: float | None = None
    delta_log_l_error: float | None = None
    thermal_status: Literal['not_checked','at_declared_target','off_target','uncomputed'] = 'not_checked'
    thermal_target: float | None = None
    # the claim's certificate (M1): Path 2's thermal eligibility, or an exclusion of the fixed point; absent where the
    # point was not judged, and in older results
    certificate: Certificate | None = Field(default=None, exclude_if=lambda v: v is None)
    scope: str = 'This exact fitted physical point only; untested parameter branches and other UV completions remain unresolved. Scores/significance retain their original NR reference meaning.'

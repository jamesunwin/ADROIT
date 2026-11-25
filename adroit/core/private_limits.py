"""Exact private published-limit contracts, source reviews and validation receipts."""
from __future__ import annotations
import math
from typing import Literal
from pydantic import Field,model_serializer,model_validator
from adroit.core.state import StrictModel

SHA=r'^[a-f0-9]{64}$'

class LimitContract(StrictModel):
    """The contract of a private published limit: a spin-independent isoscalar σ_nucleon curve (cm²) in mass, or a
    bound on BR(h → invisible), with its CL, construction, dataset overlap, scales, origin and assumptions."""
    adapter: Literal['si_isoscalar_curve','sm_higgs_invisible']
    benchmark: str
    quantity: Literal['sigma_nucleon_cm2','BR_h_invisible']
    confidence_level: float = Field(gt=0,lt=1,allow_inf_nan=False)
    construction: str = Field(min_length=1)
    selection: Literal['observed','expected']
    dataset_id: str = Field(min_length=1)
    # the constituent datasets of a combined result, named explicitly (the focused audit's FA-02: punctuation in an
    # identifier is not evidence of a combination); empty for one dataset, and left out then
    datasets: list[str] = Field(default_factory=list,exclude_if=lambda v: not v)
    overlap: Literal['unknown','disjoint_from_selected','supersedes']
    supersedes: list[str] = Field(default_factory=list)
    units: str
    x_scale: Literal['log','linear'] = 'log'
    y_scale: Literal['log','linear'] = 'log'
    points: list[tuple[float,float]] = Field(default_factory=list)
    value: float | None = Field(default=None,gt=0,allow_inf_nan=False)
    mass_range: tuple[float,float] | None = None
    origin: Literal['machine_table','printed_scalar','figure_digitised']
    x_relative_error: float | None = Field(default=None,ge=0,lt=1,allow_inf_nan=False)
    y_relative_error: float | None = Field(default=None,ge=0,lt=1,allow_inf_nan=False)
    halo: dict[str,float] = Field(default_factory=dict)
    assumptions: list[str] = Field(min_length=1)
    source_panel: str = Field(min_length=1)
    figure_axes: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def correct_shape(self) -> LimitContract:
        """Refuse data that do not fit the adapter: an SI curve needs increasing positive points, a mass range inside
        them and the halo's parameters; the Higgs bound one branching ratio ≤ 1; a digitised limit its relative
        errors; a replacement its targets."""
        if any(not math.isfinite(n) for pair in self.points for n in pair):
            raise ValueError('nonfinite curve')
        if self.adapter=='si_isoscalar_curve':
            if self.quantity!='sigma_nucleon_cm2' or self.units!='cm2':
                raise ValueError('SI contract needs nucleon cross-section in cm2')
            if len(self.points)<2 or any(x<=0 or y<=0 for x,y in self.points) or any(b[0]<=a[0] for a,b in zip(self.points,self.points[1:])):
                raise ValueError('curve needs strictly increasing positive masses and positive limits')
            if self.value is not None:
                raise ValueError('curve is not a scalar bound')
            if not self.mass_range or not self.points[0][0]<=self.mass_range[0]<self.mass_range[1]<=self.points[-1][0]:
                raise ValueError('declared mass domain must lie inside the actual curve')
            if set(self.halo)!={'rho_gev_cm3','v0_km_s','v_earth_km_s','v_esc_km_s'} or any(not math.isfinite(v) or v<=0 for v in self.halo.values()):
                raise ValueError('declare the published halo assumptions')
        elif self.quantity!='BR_h_invisible' or self.units!='dimensionless' or self.value is None or self.value>1 or self.points:
            raise ValueError('Higgs contract needs one positive branching-ratio bound <=1')
        if self.origin=='figure_digitised' and (self.x_relative_error is None or self.y_relative_error is None):
            raise ValueError('digitised limits require declared axis/value uncertainties')
        if self.overlap=='supersedes' and not self.supersedes:
            raise ValueError('state which existing inputs are superseded')
        if self.overlap!='supersedes' and self.supersedes:
            raise ValueError('replacement targets need supersedes relationship')
        return self

class SourceReview(StrictModel):
    """A signed review of selected claims of one result, bound to their scientific hash: a researcher's, or a language
    model's check of it where the researcher chose one (the owner, 2026-11-18, the post-review changes item 2),
    which then names the model and its check and says it is not a person's (``researcher``)."""
    review_id: str
    signed_revision: str
    result_id: str
    keys: list[str]
    scientific_sha256: str = Field(pattern=SHA)
    researcher: str
    reviewed_at: str
    checklist: list[str]
    note: str = ''
    # a model's check: the model, and its check's receipt (``record_check.RecordCheck``); absent from a person's
    # review, which hashes as before (its review identity, ``content_hash`` of the rest, unchanged)
    checked_by_model: str = Field(default='', exclude_if=lambda v: not v)
    check_id: str = Field(default='', exclude_if=lambda v: not v)

    @property
    def by_model(self) -> bool:
        return bool(self.checked_by_model)

class AnchorCheck(StrictModel):
    """One validation anchor's own evidence: its document, page, method and quotation (or table row), whether it is a
    separate source or the same paper's printed text, its printed rounding, and the allowance set from them (and from
    a digitised curve's declared reading errors) before the comparison."""
    point: tuple[float,float]
    asset_sha256: str = Field(pattern=SHA)
    page: int | None = None
    method: str
    excerpt: str = ''
    basis: Literal['separate_source','same_paper_text']
    x_rounding: float = Field(default=0.,ge=0,allow_inf_nan=False)
    y_rounding: float = Field(default=0.,ge=0,allow_inf_nan=False)
    allowance: float = Field(gt=0,allow_inf_nan=False)
    # the anchor's declared derivation (printed_text or published_table, the document and where in it) and, for a
    # machine table, its cell (the focused audit's FA-01); left out when absent, so earlier receipts keep their identity
    lineage: dict = Field(default_factory=dict,exclude_if=lambda v: not v)
    table: str = Field(default='',exclude_if=lambda v: not v)
    row: int | None = Field(default=None,exclude_if=lambda v: v is None)
    column: str = Field(default='',exclude_if=lambda v: not v)

class FigureVerification(StrictModel):
    """A researcher's manual verification of a curve digitised from a figure with fewer printed anchors than the
    ordinary validation needs: their name, the attested checklist, the declared mass range restated in full, and the
    receipt this one renews under newer code (if any)."""
    researcher: str = Field(min_length=1)
    signed_at: str
    checklist: list[str]
    reviewed_range: tuple[float,float]
    anchors_required: int = Field(ge=1)
    renewed_from: str = ''
    # what the researcher looked at (the focused audit's FA-06): the rendered source page and the decoded curve's
    # geometry on it through the calibration; a renewal carries the verification only while both are unchanged
    source_image_sha256: str = Field(default='',exclude_if=lambda v: not v)
    geometry_sha256: str = Field(default='',exclude_if=lambda v: not v)
    # the review packet's overlay image itself (the recheck's FR-04: the verification binds to what was shown)
    overlay_sha256: str = Field(default='',exclude_if=lambda v: not v)

COMPACT={'basis':'separate_source','anchors':[],'manual':None}

class LimitValidation(StrictModel):
    """A validation receipt for a published-limit adapter: the reference anchors, the interpolated values, their
    relative errors, the tolerance and whether all pass; with each anchor's evidence and allowance, the basis
    (separate sources, the same paper's printed text, both, or a manual figure verification) and, for the manual
    route, the researcher's verification. Fields at their defaults are left out of the serialised receipt, so that
    receipts saved before they existed keep their identities."""
    validation_id: str
    revision: str
    result_id: str
    scientific_sha256: str = Field(pattern=SHA)
    adapter_version: Literal[1] = 1
    code_sha256: str = Field(pattern=SHA)
    created_at: str
    reference: list[tuple[float,float]]
    reproduced: list[float]
    relative_errors: list[float]
    tolerance: float = Field(gt=0,le=.3,allow_inf_nan=False)
    passed: bool
    scope: str = 'Published-value transcription/adapter interpolation; no reconstructed experimental likelihood.'
    basis: Literal['separate_source','same_paper_text','mixed','manual_figure'] = 'separate_source'
    anchors: list[AnchorCheck] = Field(default_factory=list)
    manual: FigureVerification | None = None

    @model_serializer(mode='wrap')
    def compact(self,handler):
        """Leave out the fields added for figure anchors while they hold their defaults."""
        data=handler(self)
        for key,default in COMPACT.items():
            if key in data and data[key]==default:
                del data[key]
        return data

class BoundPrivateLimit(StrictModel):
    """A frozen private limit: its contract, with the source review and validation that admit it."""
    limit_id: str
    revision: str
    result_id: str
    name: str
    contract: LimitContract
    review: SourceReview
    validation: LimitValidation
    scientific_sha256: str = Field(pattern=SHA)
    created_at: str

    @property
    def reference(self) -> str:
        """The pinned ``private-limit:`` reference of this binding."""
        return 'private-limit:'+self.limit_id

"""Private experimental dossiers; extraction is not scientific approval."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from adroit.core.state import StrictModel

SHA = r'^[a-f0-9]{64}$'
ID = r'^[a-f0-9]{32}$'
Category = Literal['identity', 'detector', 'background', 'observation', 'limit',
                   'combination', 'availability']


class ExperimentalAsset(StrictModel):
    """An explicitly selected original or deterministic derived local file."""
    name: str
    sha256: str = Field(pattern=SHA)
    suffix: str
    size_bytes: int = Field(ge=0, le=25_000_000)
    role: Literal['paper', 'supplement', 'data', 'image', 'page_preview', 'ingestion']


class SourceLocator(StrictModel):
    """Physical page or machine-table position; printed labels are separate."""
    asset_sha256: str = Field(pattern=SHA)
    page: int | None = Field(default=None, ge=1)
    printed_page: str = ''
    section: str = ''
    table: str = ''
    figure: str = ''
    panel: str = ''
    row: int | None = Field(default=None, ge=1)
    column: str = ''
    region: tuple[float, float, float, float] | None = None
    excerpt: str = ''
    method: Literal['text', 'table', 'visual', 'structured'] = 'text'

    @model_validator(mode='after')
    def region_valid(self) -> SourceLocator:
        """Refuse a PDF region without a physical page or with non-finite or non-increasing coordinates."""
        if self.region is not None:
            import math
            x0,y0,x1,y1=self.region
            if self.page is None or not all(math.isfinite(v) for v in self.region) or not (x0<x1 and y0<y1):
                raise ValueError('a PDF region needs a physical page and finite increasing point coordinates')
        return self


class ExperimentalClaim(StrictModel):
    """A value with explicit origin/unknown state, not an agent confidence score."""
    key: str = Field(min_length=1)
    category: Category
    value: JsonValue = None
    units: str = ''
    status: Literal['unextracted', 'sourced', 'converted', 'digitised', 'assumed',
                    'conflicting', 'not_reported', 'not_applicable'] = 'unextracted'
    sources: list[SourceLocator] = Field(default_factory=list)
    note: str = ''
    requested_unit: str = ''

    @model_validator(mode='after')
    def evidence_required(self) -> ExperimentalClaim:
        """Refuse a non-finite value, an extracted value (sourced, converted, digitised) without its sources, and a
        value on an unknown or inapplicable claim."""
        from adroit.retrieval.experimental_ingestion import finite_json
        finite_json(self.value)
        if self.status in ('sourced','converted','digitised') and (self.value is None or not self.sources):
            raise ValueError('an extracted value requires source evidence')
        if self.status in ('unextracted','not_reported','not_applicable') and self.value is not None:
            raise ValueError('unknown/inapplicable claims cannot carry a numerical value')
        return self


class CapabilityContract(StrictModel):
    """Requirements for a future deterministic adapter; no activation implicit."""
    track: Literal['track1', 'track2']
    adapter_id: str = ''
    benchmark: str = ''
    observable: str = ''
    units: str = ''
    confidence_level: float | None = Field(default=None, gt=0, lt=1)
    construction: str = ''
    domain: dict[str, JsonValue] = Field(default_factory=dict)
    required_claims: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    state: Literal['unavailable', 'requires_validation'] = 'unavailable'

    @model_validator(mode='after')
    def finite_domain(self) -> CapabilityContract:
        """Refuse a non-finite number in the declared domain."""
        from adroit.retrieval.experimental_ingestion import finite_json
        finite_json(self.domain)
        return self


class ExperimentalResult(StrictModel):
    """One channel/result; dataset overlap and replacement must be explicit."""
    result_id: str = Field(min_length=1)
    kind: Literal['limit', 'events', 'binned', 'likelihood', 'response', 'background', 'reference']
    dataset_ids: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    overlap: Literal['unknown', 'disjoint', 'overlapping'] = 'unknown'
    claims: list[ExperimentalClaim] = Field(default_factory=list)
    capabilities: list[CapabilityContract] = Field(default_factory=list)


def checklist() -> list[ExperimentalClaim]:
    """Independent completeness inventory; importing bytes never fills physics."""
    keys={
        'identity': ['publication_version','analysis_period','dataset_relationships'],
        'detector': ['target_isotopes','exposure','observable_energy_scale','selection',
                     'threshold_window','efficiency','resolution_response','calibration'],
        'background': ['components_counts_shapes','control_regions','uncertainties_correlations','nuisance_treatment'],
        'observation': ['events_or_bin_edges_counts','excess_region','published_significance'],
        'limit': ['observed_expected_bands','benchmark_normalization','halo','confidence_construction','valid_domain'],
        'combination': ['dataset_overlap','systematic_correlations','combination_prescription'],
        'availability': ['public_data_likelihood','missing_inputs','adapter_scope'],
    }
    return [ExperimentalClaim(key=k,category=c) for c,items in keys.items() for k in items]


class ExperimentalDossier(StrictModel):
    """Scientific content distinct from upload/revision/calculation dates."""
    title: str = Field(min_length=1, max_length=500)
    collaboration: str = ''
    detector: str = ''
    analysis: str = ''
    publication_date: date | None = None
    references: list[str] = Field(default_factory=list)
    claims: list[ExperimentalClaim] = Field(default_factory=checklist)
    results: list[ExperimentalResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_keys(self) -> ExperimentalDossier:
        """Refuse repeated claim keys within one list of claims and repeated result identifiers."""
        for claims in [self.claims,*(r.claims for r in self.results)]:
            if len({c.key for c in claims})!=len(claims):
                raise ValueError('duplicate claim keys')
        if len({r.result_id for r in self.results})!=len(self.results):
            raise ValueError('duplicate result identifiers')
        return self


class ExperimentalRevision(StrictModel):
    """Immutable private draft; later milestones separately review and activate."""
    experiment_id: str = Field(pattern=ID)
    revision_id: str = Field(pattern=SHA)
    parent_revision: str = ''
    created_at: datetime
    dossier: ExperimentalDossier
    sources: list[ExperimentalAsset]
    ingestions: list[ExperimentalAsset] = Field(default_factory=list)
    source_review: Literal['unreviewed'] = 'unreviewed'
    adapter_validation: Literal['not_validated'] = 'not_validated'
    activation: Literal['inactive'] = 'inactive'
    provenance: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode='after')
    def utc_date(self) -> ExperimentalRevision:
        """Refuse a creation time not recorded in UTC."""
        if self.created_at.tzinfo is None or self.created_at.utcoffset().total_seconds()!=0:
            raise ValueError('revision creation must be recorded in UTC')
        return self

    @property
    def reference(self) -> str:
        """The pinned ``experimental:<experiment>@<revision>`` reference."""
        return f'experimental:{self.experiment_id}@{self.revision_id}'

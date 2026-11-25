"""Exact private event adapter selection and independent validation receipts."""
from typing import Literal
import math
from pydantic import Field,model_validator
from adroit.core.state import StrictModel
from adroit.core.private_limits import SourceReview
from adroit.experiments.anomaly import AnomalyRecord

class SearchContract(StrictModel):
    """The declared scope of a private event adapter: signal or null role, the elastic O₁ benchmark with c_p = c_n,
    the mass range (GeV), dataset identity and overlap, the limit construction and the assumptions."""
    adapter: Literal['historical_unbinned'] = 'historical_unbinned'
    role: Literal['signal','null']
    benchmark: Literal['elastic_contact_O1_cp_equals_cn']
    mass_range: tuple[float,float]
    dataset_id: str = Field(min_length=1)
    overlap: Literal['unknown','disjoint_from_selected','supersedes']
    supersedes: list[str] = Field(default_factory=list)
    limit_construction: Literal['optimum_interval_no_background_subtraction','maximum_gap_no_background_subtraction']
    assumptions: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def domain(self):
        """Refuse a non-positive or non-increasing mass range, an inconsistent replacement declaration, and blank
        assumptions."""
        lo,hi=self.mass_range
        if not all(math.isfinite(x) for x in (lo,hi)) or not 0<lo<hi:
            raise ValueError('positive finite increasing adapter mass range required')
        if self.overlap=='supersedes' and not self.supersedes:
            raise ValueError('explicit replacement targets required')
        if self.overlap!='supersedes' and self.supersedes:
            raise ValueError('replacement targets require supersedes policy')
        if any(not a.strip() for a in self.assumptions):
            raise ValueError('adapter assumptions must be explicit')
        return self

class SearchAnchor(StrictModel):
    """An independent reference point for the adapter: at a mass (GeV) and σ (cm²), the expected total events, event
    densities, best-fit ŝ, its log-likelihood, and the 90% and 95% CL upper limits.

    The total is in true energy over the window; the densities are smeared and normalised on the window as seen,
    and ŝ counts the events seen inside it (the external audit of 2026-10-16, A09). An anchor computed before
    that, with the densities normalised in true energy, is refused by name (``experimental_search_review``)."""
    mass_gev: float = Field(gt=0,allow_inf_nan=False)
    sigma_cm2: float = Field(gt=0,allow_inf_nan=False)
    total_events: float = Field(gt=0,allow_inf_nan=False)
    event_densities: list[float]
    s_hat: float = Field(ge=0,allow_inf_nan=False)
    log_l_hat: float = Field(allow_inf_nan=False)
    kappa90: float = Field(gt=0,allow_inf_nan=False)
    kappa95: float = Field(gt=0,allow_inf_nan=False)

    @model_validator(mode='after')
    def finite_densities(self):
        """Refuse non-finite or negative event densities."""
        if any(not math.isfinite(x) or x<0 for x in self.event_densities):
            raise ValueError('finite nonnegative event densities required')
        return self

class SearchValidation(StrictModel):
    """A validation receipt for a private event adapter: the anchors, what the code reproduced, the relative errors,
    the tolerance and whether all pass."""
    validation_id: str
    revision: str
    result_id: str
    scientific_sha256: str
    code_sha256: str
    created_at: str
    tolerance: float = Field(gt=0,le=.3,allow_inf_nan=False)
    anchors: list[SearchAnchor]
    reproduced: list[dict]
    errors: list[dict]
    passed: bool
    scope: str = 'Declared fidelity-B response/event likelihood and interval procedure; not an official collaboration workspace or statistical coverage certificate.'

class BoundPrivateSearch(StrictModel):
    """A frozen private search: the reviewed and validated event record with its contract."""
    search_id: str
    revision: str
    result_id: str
    created_at: str
    scientific_sha256: str
    contract: SearchContract
    record: AnomalyRecord
    review: SourceReview
    validation: SearchValidation

    @property
    def reference(self):
        """The pinned ``private-search:`` reference of this binding."""
        return 'private-search:'+self.search_id

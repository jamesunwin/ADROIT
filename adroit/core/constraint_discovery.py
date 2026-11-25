"""Model-driven constraint discovery: its typed records (the owner's request and handover of 2026-10-18).

A discovery session surveys which published limits bear on one pinned model: what the libraries already hold, what
the literature adds, what an existing adapter could compute once a person has reviewed it, and what needs new
machinery. Nothing here signs, validates, binds or calculates: those remain the experimental library's own steps.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from adroit.core.dm_state import Applicability
from adroit.core.state import StrictModel

SHA = r'^[a-f0-9]{64}$'
Category = Literal['existing_applicable', 'existing_needs_review', 'existing_outside_domain', 'missing_supported',
                   'needs_new_machinery', 'uncertain', 'inapplicable', 'superseded']
ADAPTERS = ('si_isoscalar_curve', 'sm_higgs_invisible')
# the user-facing stage of each category (the owner's JU1, 2026-11-16: "needs_new_machinery" reads as what it is, a
# result whose observable ADROIT does not yet calculate for the model; "uncertain" had read "source needed")
STAGES = {'existing_applicable': 'existing result', 'existing_outside_domain': "outside this model's domain",
          'inapplicable': "outside this model's domain", 'needs_new_machinery': 'not currently supported',
          'uncertain': 'unclear whether it applies', 'existing_needs_review': 'needs your review',
          'superseded': 'superseded by a newer result'}


class ModelDomain(StrictModel):
    """The deterministic summary of a pinned model and its intended domain, read from the canonical model (never from
    the intake conversation); unknowns stay unknown."""
    model_reference: str
    model_sha256: str = Field(pattern=SHA)
    name: str
    dark_matter: dict = Field(default_factory=dict)
    mediators: list[dict] = Field(default_factory=list)
    couples_to: list[str] = Field(default_factory=list)       # the Standard Model fields in a term with the dark sector
    interactions: list[str] = Field(default_factory=list)     # the terms' Lorentz structures
    has_completion: bool = False                              # a Lagrangian with terms, not an operator alone
    engine: str = ''                                          # the class the engines map it to, or why none does
    higgs_portal: bool = False
    direct_detection: str = 'unknown'                         # elastic_isoscalar_O1, other, or unknown
    domain: dict[str, tuple[float, float]] = Field(default_factory=dict)   # the intended scan ranges, GeV
    unknowns: list[str] = Field(default_factory=list)


class ResultIdentity(StrictModel):
    """What a published result is, as far as it is stated: the quantity bounded, observed or expected, the confidence
    level, the benchmark it holds for, the channel, the dataset and the panel (figure or table). An empty field is
    unknown, never a wildcard (the fresh audit's F19-01: identity must be positive)."""
    quantity: str = ''
    selection: Literal['', 'observed', 'expected'] = ''
    confidence_level: float | None = Field(default=None, gt=0, lt=1)
    benchmark: str = ''
    channel: str = ''
    dataset: str = ''
    panel: str = ''


class InventoryEntry(StrictModel):
    """One entry of the unified, read-only records index: its exact reference in its own store."""
    reference: str
    kind: Literal['standard_record', 'experiment_module', 'signal_search', 'personal_revision', 'personal_limit',
                  'personal_search', 'profile']
    library: Literal['standard', 'personal']
    title: str
    constraint_class: str = ''
    source_ids: list[str] = Field(default_factory=list)       # normalised: arxiv:NNNN.NNNNN, doi:…
    review: str = ''
    adapter: str = ''
    domain: dict = Field(default_factory=dict)
    origin: str = ''
    quantity: str = ''                                        # a standard record's bounded quantity, as it states it
    benchmark: str = ''                                       # set when the record holds for one model only
    confidence_level: float | None = None
    result: ResultIdentity = Field(default_factory=ResultIdentity)   # its result's identity, where stated (F19-01)


class Acquisition(StrictModel):
    """What was retrieved for one candidate, with the exact identities and hashes, or why nothing was."""
    status: Literal['retrieved', 'failed', 'retryable', 'not_attempted'] = 'not_attempted'   # retryable: in transit
    arxiv_id: str = ''
    version: str = ''
    title: str = ''
    published: str = ''
    url: str = ''
    retrieved_at: str = ''
    sha256: str = ''
    size_bytes: int = 0
    hepdata: list[dict] = Field(default_factory=list)          # record, version, table, url, sha256
    licence: str = ''
    revision: str = ''                                         # the experimental draft it was imported into
    reason: str = ''


class Candidate(StrictModel):
    """One vetted proposal, its category (decided by code) and its separate states."""
    candidate_id: str
    name: str
    constraint_class: str
    reference: str                                             # arXiv:NNNN.NNNNN or doi:…
    title: str
    relevance: str = ''
    applicability: Applicability
    assumptions: list[str] = Field(default_factory=list)
    needed_calculation: str = ''
    hepdata: str = ''                                          # the agent's hint: an INSPIRE record, ins…
    tables: list[str] = Field(default_factory=list)            # the agent's hint: table names in that record
    matches: list[str] = Field(default_factory=list)           # inventory references with the same source identity
    category: Category
    adapter: str = ''
    missing: str = ''                                          # the named missing prediction, recast or input
    domain: dict[str, tuple[float, float]] = Field(default_factory=dict)  # where the result applies, if declared
    acquisition: Acquisition = Field(default_factory=Acquisition)
    extraction_session: str = ''
    draft: str = ''                                            # the latest draft revision from the extraction
    result_id: str = ''
    superseded_by: str = ''                                    # the newer result: an inventory reference or candidate:<id>
    held_as: str = ''                                          # the held entry the relevance step named as this result
    result: ResultIdentity = Field(default_factory=ResultIdentity)   # the result as the relevance step described it
    resolvers: list[str] = Field(default_factory=list)         # bound limits shown to be this result (F19-02)


class Decision(StrictModel):
    """A researcher's recorded decision on a candidate: justified inapplicability, an explicit scope omission, a
    confirmed supersession, or the inclusion of an unclear result ADROIT can calculate, to be fetched and drafted
    (``included``: JU1)."""
    candidate_id: str
    kind: Literal['inapplicable', 'omitted', 'superseded', 'included']
    reason: str = Field(min_length=1)
    researcher: str = Field(min_length=1)
    at: str
    replacement: str = Field(default='', exclude_if=lambda v: not v)   # 'superseded': the newer result confirmed


class Requirement(StrictModel):
    """A relevant constraint left unresolved for the runs that pin an assessment."""
    candidate_id: str
    name: str
    reference: str
    constraint_class: str
    reason: str
    resolved_by: list[str] = Field(default_factory=list)       # private-limit references that would resolve it
    domain: dict[str, tuple[float, float]] = Field(default_factory=dict)


class DiscoveryCoverage(StrictModel):
    """A frozen assessment: the model it belongs to, when the survey ran, and every unresolved requirement."""
    session_id: str
    assessment_sha256: str = Field(pattern=SHA)
    model_sha256: str = Field(pattern=SHA)
    model_reference: str
    searched_at: str
    requirements: list[Requirement] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    domain: dict[str, tuple[float, float]] = Field(default_factory=dict)   # the surveyed scan ranges, GeV (S18-06)
    complete: bool = True                     # every stage finished; an incomplete one adds an everywhere requirement
    stages: dict[str, str] = Field(default_factory=dict)                   # each stage's state when frozen
    scope: str = ('A dated, bounded survey; constraints it did not find are not shown to be absent. Unresolved '
                  'requirements keep an allowed point pending; they never exclude.')

    @property
    def reference(self) -> str:
        """``discovery:<session>@<assessment hash>``, the pin a run carries."""
        return f'discovery:{self.session_id}@{self.assessment_sha256}'

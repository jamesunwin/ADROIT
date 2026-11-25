"""Confirmed interpretation is separate from source verification/activation."""
from pydantic import Field
from typing import Literal
from adroit.core.state import StrictModel
from adroit.experiments.anomaly import AnomalyRecord

class AnomalyInterpretation(StrictModel):
    """One experimental result read as an anomaly record (none while blocked), with its blockers, assumptions and
    evidence warnings."""
    revision: str
    result_id: str
    kind: str
    explanation: str
    record: AnomalyRecord | None = None
    blockers: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    evidence_warnings: list[str] = Field(default_factory=list)
    interpretation_sha256: str = ''

class AnomalyConfirmation(StrictModel):
    """A researcher's confirmation of an interpretation and its assumptions, for exploratory use; not a source
    review."""
    confirmation_id: str
    created_at: str
    researcher: str
    interpretation: AnomalyInterpretation
    accepted_assumptions: list[str]
    source_review: Literal['unreviewed'] = 'unreviewed'
    use: str = 'exploratory interpretation; not source verification or experiment activation'

    @property
    def reference(self) -> str:
        """The pinned ``anomaly:`` reference of this confirmation."""
        return 'anomaly:'+self.confirmation_id

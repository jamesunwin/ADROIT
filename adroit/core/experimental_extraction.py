"""Source scope and immutable assisted-extraction receipts."""
from pydantic import Field
from adroit.core.state import StrictModel
from adroit.core.experimental_input import ExperimentalAsset


class SourceUnit(StrictModel):
    """One bounded original-page/text/table chunk, with explicit image identity."""
    unit_id: str
    asset_sha256: str
    source_name: str = ''
    page: int | None = None
    row_low: int | None = None
    row_high: int | None = None
    text: str = ''
    image: ExperimentalAsset | None = None
    vision: bool = False
    notes: list[str] = Field(default_factory=list)
    bounds: tuple[float,float,float,float] | None = None


class ExtractionScope(StrictModel):
    """An extraction session's scope: the selected source units of a revision and their batches."""
    session_id: str
    revision: str
    created_at: str
    units: list[SourceUnit]
    batches: list[list[str]]
    integrity_sha256: str = ''
    # the session whose cap and ledger the steps use (a discovery session's one cap); left out when the scope's own
    budget_session: str = Field(default='', exclude_if=lambda v: not v)


class ExtractionStep(StrictModel):
    """The receipt of one assisted-extraction step: the revision it read and the one it wrote, the units read, the
    agent's explanation and raw answer, ambiguities and evidence problems."""
    step_id: str
    session_id: str
    created_at: str
    parent_step: str = ''
    input_revision: str
    output_revision: str
    unit_ids: list[str]
    explanation: str
    ambiguities: list[str] = Field(default_factory=list)
    evidence_problems: list[str] = Field(default_factory=list)
    raw_answer: dict
    instructions: str = ''
    read_units: list[SourceUnit] = Field(default_factory=list)
    trimmed_prior: bool = False          # the request carried the compacted prior dossier (stored only when true)

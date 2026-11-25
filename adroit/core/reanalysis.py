"""Immutable reanalysis drafts, pinned to their original scientific input."""
from typing import Literal
from pydantic import Field,JsonValue
from adroit.core.state import StrictModel

class ReanalysisDraft(StrictModel):
    """An immutable reanalysis draft: its source and hashes, the workflow, the original and edited requests, and the
    index of the saved physical model."""
    draft_id: str
    created_at: str
    parent_draft: str = ''
    source: str
    source_kind: str
    source_sha256: str
    source_evidence_sha256: str = ''
    workflow: Literal['track1','signal','single_idea']
    original_request: dict[str,JsonValue]
    request: dict[str,JsonValue]
    model_index: int = Field(default=0,ge=0)

    @property
    def reference(self)->str:
        """The pinned ``reanalysis:`` reference of this draft."""
        return 'reanalysis:'+self.draft_id

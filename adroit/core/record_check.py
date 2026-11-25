"""The record check's receipts (the owner, 2026-11-18, the post-review changes item 2): a language model's
check of a user-added experimental record, in place of a person's review at the researcher's choice.

- ``CheckRun``: what a check session was asked (``record_check.json`` in its session folder): the record and result,
  the checking model, the model that re-reads the record after a major defect, how many re-readings, and a
  researcher's suggestion where one was given.
- ``RecordCheck``: one check (``checks/<check_id>.json`` in the experimental library): the model's answer, each
  newer paper it named and whether ADROIT confirmed it, the literature search, the major and minor defects, and
  whether it passed.
- ``CheckOutcome``: how the session ended (``outcome.json``): approved by the model (with the review it signed), or
  back to the researcher with the mismatches, or stopped (its budget, an error).
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, JsonValue

from adroit.core.state import StrictModel


class CheckRun(StrictModel):
    """A record check session's request."""
    session_id: str
    revision: str                         # the record's revision as the check began
    result_id: str
    model: str                            # the checking model
    reanalysis_model: str                 # the record assistant's model, for a re-reading after a major defect
    retries: int = Field(ge=0, le=2)      # re-readings before it comes back to the researcher
    instruction: str = ""                 # the researcher's suggested route, applied before the first check
    created_at: str


class Citation(StrictModel):
    """A newer paper the checking model named, and whether arXiv confirmed it (identifier, title, year)."""
    arxiv_id: str
    claimed_title: str
    relation: str                         # superseded, stronger_elsewhere or related (the model's word)
    confirmed: bool
    found_title: str = ""
    found_year: int | None = None
    why: str = ""                         # why it is not confirmed


class RecordCheck(StrictModel):
    """One check of one result of one revision."""
    check_id: str
    session_id: str
    revision: str
    result_id: str
    keys: list[str]
    scientific_sha256: str
    model: str
    round: int
    created_at: str
    answer: dict[str, JsonValue]
    citations: list[Citation] = Field(default_factory=list)
    search: dict[str, JsonValue] = Field(default_factory=dict)      # its query, when, what it found, or why it failed
    library: list[str] = Field(default_factory=list)                # the library records compared
    major: list[str] = Field(default_factory=list)
    minor: list[str] = Field(default_factory=list)
    passed: bool
    previous_check: str = ""


class CheckOutcome(StrictModel):
    """How a check session ended."""
    session_id: str
    status: Literal["approved", "needs_you", "stopped"]
    checks: list[str] = Field(default_factory=list)
    revisions: list[str] = Field(default_factory=list)              # the record's revisions, the first as checked
    final_revision: str
    result_id: str
    review_id: str = ""                                             # the model's signed review, where approved
    mismatches: list[str] = Field(default_factory=list)             # the last check's major defects
    notes: list[str] = Field(default_factory=list)                  # its minor ones, and its unconfirmed citations
    why: str = ""
    finished_at: str

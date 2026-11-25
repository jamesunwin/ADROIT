"""Unsigned audit notes on record values (the external audit of 2026-10-16, item 18).

``data/audit_notes.yaml`` marks how some stored values stand against their sources: approximate, digitised,
borrowed from another analysis, or awaiting an independent comparison. The notes are kept apart from the records,
whose ``verification_sha256`` covers their data, assumptions and checks: adding a field there would make every
signature stale. A result that rests on a noted record carries the note beside it (``flags``), with how good the result
is; whether a value can support a decisive result is the owner's decision (the audit proposals of 2026-10-16,
decided 2026-10-17).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from adroit.core.state import StrictModel

FILE = Path(__file__).resolve().parent / "data" / "audit_notes.yaml"
STATUS = {"exact": "exact", "approximate": "approximate", "digitised": "digitised",
          "borrowed": "borrowed from another analysis", "outstanding": "awaiting an independent comparison"}


class AuditNote(StrictModel):
    """One stored value's status against its source, why, and where a result uses it."""

    value: str
    status: Literal["exact", "approximate", "digitised", "borrowed", "outstanding"]
    reason: str
    used: str = ""
    accuracy: str = ""          # how good a result resting on it is (the owner's decisions of 2026-10-17)


@lru_cache(maxsize=1)
def notes() -> dict[str, tuple[AuditNote, ...]]:
    """Every record's notes, by record id; a note on a record that does not exist is refused."""
    from adroit.constraints import database
    raw = yaml.safe_load(FILE.read_text())["notes"]
    known = {r.id for r in database.records()}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ValueError(f"audit notes name records that do not exist: {unknown}")
    return {rid: tuple(AuditNote.model_validate(n) for n in items) for rid, items in raw.items()}


def flags(record_ids: list[str]) -> list[str]:
    """The notes of these records, one line each, as a result that rests on them shows them."""
    found = notes()
    return [f"record {rid}: {n.value} is {STATUS[n.status]} ({n.reason}; used for {n.used})"
            + (f"; {n.accuracy}" if n.accuracy else "") + "; an unsigned audit note"
            for rid in record_ids for n in found.get(rid, ())]

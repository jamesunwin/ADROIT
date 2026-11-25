"""Scientific review bindings; recorded dates are never manufactured by a hash."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

from pydantic import Field, JsonValue
import yaml

from adroit.core import file_reads
from adroit.core.config import PROJECT_ROOT
from adroit.core.evidence import content_hash
from adroit.core.state import StrictModel

if TYPE_CHECKING:
    from adroit.core.dm_state import ConstraintRecord

LEGACY_BINDINGS = Path(__file__).with_name("data") / "review_bindings.yaml"
# Outside the signed scientific payload: the signature itself, the display name, and the reviewer's notes (documentation
# of where each value is in the source), so that notes can be added or corrected without voiding a signature
REVIEW_FIELDS = {"verified_on", "verified_by", "verification_sha256", "verification_history", "name", "notes"}


class LegacyBinding(StrictModel):
    """Migration baseline of an existing approval, not a new human verification."""

    record_id: str
    on: date
    by: str
    payload_sha256: str


class LegacyBindings(StrictModel):
    """Immutable labelled migration snapshots for existing curated approvals."""

    schema_version: Literal[1] = 1
    captured_on: date
    interpretation: str
    bindings: list[LegacyBinding] = Field(default_factory=list)


class SignatureStatus(StrictModel):
    """Current eligibility and the exact reason a historical signature is stale."""

    state: Literal["unreviewed", "current", "stale", "unavailable", "legacy_baseline", "legacy_unbound"]
    usable: bool = False
    current_sha256: str = ""
    signed_sha256: str = ""
    reason: str


def scientific_payload(record: ConstraintRecord) -> dict[str, JsonValue]:
    """Canonical scientific metadata; omit signature history, the display-only name and the reviewer's notes."""
    return record.model_dump(mode="json", exclude=REVIEW_FIELDS)


@lru_cache(maxsize=128)
def _data(path: str, *version: int) -> dict:
    """The data file ``path`` parsed, in the version ``version`` (``file_reads.identity``), or ``file_reads.Moved``: an
    entry evicted and filled again is the same version's or none (the auditor's CU recheck, CV-04, 2026-10-28)."""
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    return yaml.load(file_reads.read(path, version).decode("utf-8"), Loader=loader)


def _declared(path: Path) -> str:
    """The resolved path of a record's data file, or ``ValueError`` where it is not a declared project input."""
    if not path.resolve().is_relative_to(PROJECT_ROOT.resolve()) or path.name.startswith(".env"):
        raise ValueError("review data must be a declared project input")
    return str(path.resolve())


def selected_data(record: ConstraintRecord) -> dict[str, JsonValue]:
    """Return only this record's panel/channels from a shared published data file."""
    if not record.data_file:
        return {}
    from adroit.constraints.review import _own_part
    where = _declared(PROJECT_ROOT / record.data_file)
    return _own_part(record, file_reads.consistent(where, lambda *version: _data(where, *version)))


def fingerprint(record: ConstraintRecord, data: dict | None = None) -> str:
    """Bind physical assumptions, source/figure, native CL, benchmark and selected data. ``data``: the record's data
    file as one reading of it parsed it (``review.Reading``; the auditor's DJ recheck, DK-02), else read here; the version
    is the same formula's (``_formula``) either way."""
    metadata=json.dumps(scientific_payload(record),sort_keys=True,separators=(",",":"))
    if not record.data_file:
        return content_hash({"record":json.loads(metadata),"data":{}})
    where=_declared(PROJECT_ROOT/record.data_file)
    if data is not None:
        return _formula(json.loads(metadata),data)
    return file_reads.consistent(where,lambda *version:_fingerprint(metadata,where,*version))


def snapshot(record: ConstraintRecord) -> tuple[dict, str]:
    """The record's data file as read once (read again whenever the file changes: ``file_reads.identity``), and the
    version of the record with exactly those data (``fingerprint``; "" where it cannot be taken): a calculation uses
    the one and a claim resting on it is bound to the other, both from the same read (the auditor's CT recheck, CU-01 and
    CU-04, 2026-10-28). Both are kept by the file's version and each is of that version's bytes, so they agree however
    either cache is evicted (the auditor's CU recheck, CV-04, 2026-10-28). Raises ``OSError`` where the file cannot be
    read."""
    if not record.data_file:
        return {}, version(record)
    path = PROJECT_ROOT / record.data_file
    where = str(path.resolve())

    def held(*version: int) -> tuple[dict, str]:
        data = _data(where, *version)
        try:
            _declared(path)
            metadata = json.dumps(scientific_payload(record), sort_keys=True, separators=(",", ":"))
            return data, _fingerprint(metadata, where, *version)
        except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
            return data, ""
    return file_reads.consistent(where, held)


def version(record: ConstraintRecord) -> str:
    """The fingerprint of the record as held (``fingerprint``), or "" where it cannot be taken: what a claim that used
    this record is bound to (the auditor's CS recheck, CT-01, 2026-10-28)."""
    try:
        return fingerprint(record)
    except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
        return ""


@lru_cache(maxsize=512)
def _fingerprint(metadata: str,path: str,*version: int) -> str:
    return _formula(json.loads(metadata),_data(path,*version))


def _formula(record: dict, data: dict) -> str:
    """The version of a record: its scientific payload ``record`` and its own part of its data file ``data``."""
    from adroit.core.dm_state import ConstraintRecord
    from adroit.constraints.review import _own_part
    projected=_own_part(ConstraintRecord.model_validate({**record,"name":""}),data)
    return content_hash({"record":record,"data":projected})


def captured_version(payload: dict, data_sha256: str) -> str:
    """The version (``fingerprint``) of a record as a run's evidence captured it: its metadata ``payload`` (the
    record as captured) and the data file whose SHA-256 is ``data_sha256``. The file is read once and its bytes used
    only if they have that digest, so the version is the captured pair's, whenever it is taken; "" where the file is
    another version now, or the version cannot be taken (the auditor's CW recheck, CX-01, 2026-10-31: the library read again
    after the run's end had been taken as what its evidence captured)."""
    import hashlib
    from adroit.core.dm_state import ConstraintRecord
    try:
        record = ConstraintRecord.model_validate(payload)
        metadata = json.loads(json.dumps(scientific_payload(record), sort_keys=True, separators=(",", ":")))
        if not record.data_file:
            return content_hash({"record": metadata, "data": {}})
        content = Path(_declared(PROJECT_ROOT / record.data_file)).read_bytes()
        if hashlib.sha256(content).hexdigest() != data_sha256:
            return ""
        loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        return _formula(metadata, yaml.load(content.decode("utf-8"), Loader=loader))
    except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
        return ""


@lru_cache(maxsize=4)
def _bindings(text: str) -> LegacyBindings:
    return LegacyBindings.model_validate(yaml.safe_load(text))


def signature_status(record: ConstraintRecord, version_of: Callable[[], str] | None = None) -> SignatureStatus:
    """Validate a current seal or a labelled legacy baseline, keeping the human stamp. ``version_of``: the record's
    version as one reading of it gives it (``review.Reading.version``; DK-02), else ``fingerprint`` of it now."""
    if record.verified_on is None or not record.verified_by.strip():
        return SignatureStatus(state="unreviewed", reason="awaits a person's verification")
    legacy = None
    if not record.verification_sha256 and LEGACY_BINDINGS.exists():
        legacy = next((b for b in _bindings(LEGACY_BINDINGS.read_text()).bindings if b.record_id == record.id), None)
        if legacy and (legacy.on != record.verified_on or legacy.by != record.verified_by):
            return SignatureStatus(state="stale",signed_sha256=legacy.payload_sha256,
                reason="historical approval identity changed without a new payload-bound human review")
    signed = record.verification_sha256 or (legacy.payload_sha256 if legacy else "")
    if not signed:         # a name and date bound to nothing: not usable, whatever the record holds (AL1-08)
        return SignatureStatus(state="legacy_unbound",
            reason="a name and date with no binding to what was verified (no verification hash, no legacy binding): "
                   "what it approved cannot be told, so a person must verify the record again")
    try:
        current = version_of() if version_of is not None else fingerprint(record)
    except (OSError, ValueError, yaml.YAMLError) as error:
        return SignatureStatus(state="unavailable", signed_sha256=signed,
                               reason=f"reviewed scientific input unavailable: {error}")
    if signed != current:
        return SignatureStatus(state="stale", current_sha256=current, signed_sha256=signed,
            reason="scientific metadata or this record's data changed since the review binding; human re-review required")
    state = "legacy_baseline" if legacy else "current"
    reason = ("existing historical approval matches the M21 migration baseline; no new human review claimed"
              if legacy else "human approval matches the current scientific payload")
    return SignatureStatus(state=state, usable=True, current_sha256=current, signed_sha256=signed, reason=reason)

"""The unified records index (the owner's request, 2026-10-18): standard records and personal additions read from
their own stores, with exact references and origins; nothing is copied into or shadows the packaged records."""

from __future__ import annotations

import hashlib

from adroit.library import records_index as ri
from tests.private_limit_fixtures import eligible, fixture


def test_source_identities_are_normalised() -> None:
    assert ri.source_ids('arXiv:2301.10731v2 (Phys. Lett. B)', 'doi:10.17182/HEPData.1.v1.') == [
        'arxiv:2301.10731', 'doi:10.17182/hepdata.1.v1']


def test_the_standard_view_holds_the_packaged_records_and_modules() -> None:
    from adroit.constraints.database import RECORDS
    before = hashlib.sha256(RECORDS.read_bytes()).hexdigest()
    entries = ri.standard()
    hinv = next(e for e in entries if e.reference == 'record:atlas-2301.10731-hinv')
    assert hinv.library == 'standard' and 'arxiv:2301.10731' in hinv.source_ids
    assert any(e.kind == 'experiment_module' and e.source_ids for e in entries)
    assert hashlib.sha256(RECORDS.read_bytes()).hexdigest() == before


def test_personal_additions_carry_their_state_and_origin(tmp_path) -> None:
    catalog, draft = fixture(tmp_path)
    entries = {e.reference: e for e in ri.personal(catalog)}
    assert entries[draft.reference].review == 'draft' and entries[draft.reference].origin == 'manual import'
    bound = eligible(catalog, draft)
    entries = {e.reference: e for e in ri.personal(catalog)}
    assert entries[draft.reference].review == 'bound'
    assert entries[bound.reference].kind == 'personal_limit' and entries[bound.reference].domain == {'mass_range': [10, 40]}
    assert all(e.library == 'personal' for e in entries.values())


def test_the_index_reads_a_records_review_as_its_evaluator_does(monkeypatch) -> None:
    """The consistency audit's CA-10 (2026-10-24): a record signed and then changed without a new signature is stale
    and unusable, but the index called it verified (a date's presence). Signed in memory only: a synthetic signature
    on the record's current content, then one assumption changed."""
    import datetime
    from adroit.constraints import database
    from adroit.constraints.review_identity import fingerprint
    from adroit.experiments import registry
    unsigned = database.record('dampe-2112.08860-lines').model_copy(update={
        'verified_on': None, 'verified_by': '', 'verification_sha256': ''})
    signed = unsigned.model_copy(update={'verified_on': datetime.date(2026, 10, 25), 'verified_by': 'TEST SYNTHETIC',
                                         'verification_sha256': fingerprint(unsigned)})
    changed = signed.model_copy(update={'assumptions': signed.assumptions + ['a changed assumption']})
    assert [ri.record_review(r) for r in (unsigned, signed, changed)] == ['unverified', 'verified', 'stale']
    assert signed.usable and not changed.usable
    monkeypatch.setattr(database, 'records', lambda: [changed])
    monkeypatch.setattr(registry, 'MODULES', {})
    monkeypatch.setattr(registry, 'SIGNAL_SEARCHES', {})
    assert [e.review for e in ri.standard()] == ['stale']

"""Unsigned audit notes on record values (the external audit of 2026-10-16, item 18)."""

from __future__ import annotations

import hashlib

from adroit.constraints import audit_notes, database
from adroit.constraints.searches import Outcome


def test_every_note_names_a_record_and_states_its_status() -> None:
    found = audit_notes.notes()
    assert {"ccfr-1406.2332-trident", "sabti-1910.01649-bbn", "darkcast-dark-photon", "atlas-1910.08447-dijet-gaussian",
            "atlas-1903.06248-dilepton", "atlas-2004.14636-ww"} <= set(found)
    assert {n.status for notes in found.values() for n in notes} <= set(audit_notes.STATUS)
    # item 19: both records were compared with HEPData value by value (2026-10-17), so none awaits a comparison
    assert not any(n.status == "outstanding" for notes in found.values() for n in notes)
    # the owner's decisions (2026-10-17): each note states how good a result resting on it is
    assert all(n.accuracy for notes in found.values() for n in notes)


def test_the_notes_leave_every_signature_as_it_was() -> None:
    """The notes live in their own file; no record's verification covers it, so loading them changes no signature's
    state (records whose signed content changed await the owner's re-verification either way)."""
    from adroit.constraints.review_identity import signature_status
    before = {r.id: (r.verification_sha256, signature_status(r).state) for r in database.records()}
    audit_notes.notes.cache_clear()
    audit_notes.notes()
    assert {r.id: (r.verification_sha256, signature_status(r).state) for r in database.records()} == before
    assert hashlib.sha256(audit_notes.FILE.read_bytes()).hexdigest()           # a file of its own
    assert "adroit/constraints/data/audit_notes.yaml" not in {r.data_file for r in database.records()}


def test_a_result_that_rests_on_a_noted_record_shows_the_note(monkeypatch) -> None:
    from adroit.parameter_space import searches
    decided = Outcome(name=searches.LMU, excluded=True, why="above the heavy limit")
    undecided = Outcome(name=searches.DILEPTON, excluded=None, why="outside the width range")
    monkeypatch.setattr(searches, "EVALUATORS", (lambda cls, p, unverified: [decided, undecided],))
    from adroit.parameter_space import resonances
    monkeypatch.setattr(resonances, "EVALUATORS", ())
    out = {o.name: o for o in searches.outcomes(None, None)}
    assert any("record ccfr-1406.2332-trident: heavy_m_over_g_gev = 567 GeV is digitised" in f and "good to about 2%" in f
               for f in out[searches.LMU].flags)
    assert not any("audit note" in f for f in out[searches.DILEPTON].flags)      # it decided nothing
    assert audit_notes.flags(["planck-2018-omega"]) == []


def test_the_dijet_notes_go_only_with_the_record_that_decided(monkeypatch) -> None:
    """The dijet's two records decide apart (CMS when narrow, ATLAS's Gaussian limits when broad): a CMS decision does
    not carry the notes on ATLAS's record."""
    from adroit.parameter_space import resonances, searches
    cms = Outcome(name=resonances.DIJET, excluded=False, ratio=0.3)
    monkeypatch.setattr(searches, "EVALUATORS", ())
    monkeypatch.setattr(resonances, "EVALUATORS", (lambda cls, p, unverified: cms,))
    out = {o.name: o for o in searches.outcomes(None, None)}
    assert not any("atlas-1910.08447-dijet-gaussian" in f for f in out[resonances.DIJET].flags)

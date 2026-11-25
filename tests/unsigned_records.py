"""The records the owner signs after 1.0.0's audits, as they stood before: for tests of an unsigned record's behaviour
that read the real records (prepared 2026-10-24, so that the owner's signatures do not fail them)."""
from __future__ import annotations

AWAITING = ("cms-1808.03684-4mu", "atlas-2301.09342-4mu", "lhcb-1612.07818-b-to-k-mumu", "pdg-2024-electroweak-st",
            "lep-charginos", "opal-hep-ex-0309014-sleptons", "li-2412.04572-bsgamma", "dmwg-1810.09420-bsmumu",
            "escudero-1901.02010-neff", "dampe-2112.08860-lines")


def as_unsigned(monkeypatch, ids: tuple[str, ...] = AWAITING) -> None:
    """The database's records ``ids`` without their verification, whether or not the owner has signed them since."""
    from adroit.constraints import database
    read = database._records

    def unsigned(text: str):
        return tuple(r.model_copy(update={"verified_on": None, "verified_by": "", "verification_sha256": "",
                                          "verification_history": []}) if r.id in ids else r for r in read(text))
    monkeypatch.setattr(database, "_records", unsigned)


def used(record_id: str) -> dict[str, str]:
    """A record as an evaluation notes its use: its id and the version used (CT-01)."""
    from adroit.constraints import database
    from adroit.constraints.review_identity import version
    return {record_id: version(database.record(record_id))}

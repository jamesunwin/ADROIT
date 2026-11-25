"""The cited Planck estimator shared by relic cuts and thermal likelihoods."""

from adroit.constraints import database
from adroit.core.state import StrictModel


class DensityMeasurement(StrictModel):
    """Cold-dark-matter density and its one-sigma error in base ΛCDM."""

    value: float
    sigma: float
    estimator: str
    source: str


ID = 'planck-2018-omega'


def measurement() -> DensityMeasurement:
    """Read Table 2, TT,TE,EE+lowE+lensing, from the curated record.

    Reading the target does not grant permission to apply an unverified cut;
    the caller retains the record-eligibility policy.
    """
    return _of(database.record(ID))


def versioned() -> tuple[DensityMeasurement, str]:
    """The measurement and the version of the record it was read from (``review_identity.version``), from one read:
    what a thermal claim decided against this target is bound to (the auditor's CS recheck, CT-02, 2026-10-28)."""
    return read()[:2]


def read() -> tuple[DensityMeasurement, str, bool]:
    """``versioned``'s measurement and version, and whether that record, as read, may decide a claim (a person verified
    it as it is: ``usable``), from one read: a thermal claim decided against a target awaiting verification is pending
    unless its run enables unverified records, and then says it depends on it (the audit loop's AL1-07, 2026-11-14)."""
    from adroit.constraints.review_identity import version
    record = database.record(ID)
    return _of(record), version(record), record.usable


def _of(record) -> DensityMeasurement:
    return DensityMeasurement(value=record.data['value'], sigma=record.data['sigma'],
                              estimator=record.source, source=record.source)

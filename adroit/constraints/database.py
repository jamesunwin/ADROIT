"""The curated database of complementary constraints (DM7).

Records live in ``data/records.yaml``: each gives its source, the data it
rests on (inline, or a digitised file beside it), the assumptions under which
the published constraint holds, the checks made on the transcription, the
reviewer's notes (``notes``, Markdown: where each stored value is in its source,
and anything else a reader should know; every record has the section, and notes
are outside the signed content, so adding them never voids a signature), and who
verified it when. The build plan's rule: agents may propose records; a person
verifies each before it is used. ``usable`` enforces it.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from pathlib import Path

import numpy as np
import yaml

from adroit.core.dm_state import ConstraintClass, ConstraintRecord


RECORDS = Path(str(resources.files("adroit.constraints").joinpath("data/records.yaml")))


def records() -> tuple[ConstraintRecord, ...]:
    """Every record of the database, verified or not (from ``RECORDS``)."""
    return _records(RECORDS.read_text(encoding="utf-8"))      # as ``review.verify`` writes it


@lru_cache(maxsize=4)
def _records(text: str) -> tuple[ConstraintRecord, ...]:
    return tuple(ConstraintRecord(**entry) for entry in yaml.safe_load(text)["records"])


records.cache_clear = _records.cache_clear  # retain the established cache-reset API


def record(record_id: str) -> ConstraintRecord:
    """One record by its id, its version noted in the evaluation in force (``searches.consulted``): a search that reads
    a record's values after its admission may hold another version of it, read from a changed records file (the auditor's
    CU recheck, CV-02, 2026-10-28: LEP's bounds were read as B after their admission as A, and the claim bound A)."""
    for r in records():
        if r.id == record_id:
            from adroit.constraints.searches import consulted
            consulted(r)
            return r
    raise KeyError(f"no constraint record {record_id!r}")


def usable(include_unverified: bool = False,
           constraint_class: ConstraintClass | None = None) -> list[ConstraintRecord]:
    """The records that may be used: those a person has verified, unless told otherwise."""
    return [r for r in records()
            if (include_unverified or r.usable)
            and (constraint_class is None or r.constraint_class is constraint_class)]


def data(record_id: str) -> dict:
    """The digitised data file of a record, as one read whose version is noted in the evaluation in force
    (``searches._bundled``): every reader of a record's data, the complementary verdicts' too, which a scan's collider
    comparison calls (the auditor's CU recheck, CV-02, 2026-10-28: read apart, CMS's panel was read as B and the claim bound
    the A restored after it)."""
    from adroit.constraints.searches import _bundled
    return _bundled(record_id)


def _forget() -> None:
    from adroit.constraints.searches import _bundled
    _bundled.cache_clear()


data.cache_clear = _forget


# A digitised curve's end points carry its calibration's error: IceCube's 10 TeV end reads 9999.2 GeV.
EDGE = 1e-3


def interpolate_limit(points: list[list[float]], mass_gev: float) -> float | None:
    """A limit curve at one mass, interpolated in log–log; None outside the curve's range, whose end points are
    read with the digitisation's tolerance (``EDGE``)."""
    masses = np.array([p[0] for p in points])
    values = np.array([p[1] for p in points])
    order = np.argsort(masses)
    masses, values = masses[order], values[order]
    if not masses[0] * (1 - EDGE) <= mass_gev <= masses[-1] * (1 + EDGE):
        return None
    return float(10 ** np.interp(np.log10(mass_gev), np.log10(masses), np.log10(values)))

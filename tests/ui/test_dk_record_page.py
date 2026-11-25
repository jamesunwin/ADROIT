"""The auditor's DJ recheck (DK-02) on the records page, where a person verifies a curated record: the figure the page shows
and the hash its verification is bound to are of one reading of the record and its data file. The record is an
unsigned copy (``awaiting``); the verification is intercepted, nothing signed; $0."""
from __future__ import annotations

import base64

import pytest

pytest.importorskip("nicegui")

from nicegui import ElementFilter, ui  # noqa: E402
from nicegui.testing import User  # noqa: E402

from tests.orchestrator.test_dk_fixes import _while, scaled, scratch_payload  # noqa: E402
from tests.orchestrator.test_dj_fixes import A  # noqa: E402


async def test_a_record_page_shows_and_binds_one_reading_of_its_record(user: User, tmp_path, monkeypatch,
                                                                       awaiting) -> None:
    """DK-02's class on the page a verification is made on: record A (Fermi-LAT's dwarfs, unsigned in the copy), its
    data file B (every ordinate a hundred times A's) while the page draws its figure, A's very bytes before and after.
    The page shows A's figure, drawn from the reading its verification's hash is of: the hash a person's click binds is
    A's version, and the figure beside it A's. Before, the hash was A's and the figure B's."""
    from adroit.constraints import database, review
    from adroit.constraints.review_identity import version
    from adroit.ui.app import build_pages
    awaiting(A)
    path = scratch_payload(tmp_path, monkeypatch)
    a = path.read_bytes()
    record = database.record(A)
    figure, bound = review.figure(record), version(record)
    path.write_bytes(scaled(a))
    database.data.cache_clear()
    other = review.figure(database.record(A))
    path.write_bytes(a)
    database.data.cache_clear()
    assert figure != other
    captured = {}
    monkeypatch.setattr(review, "verify", lambda record_id, by, path=None, expected_sha256="": captured.update(
        record=record_id, hash=expected_sha256))
    (tmp_path / "runs").mkdir()
    build_pages(tmp_path / "runs", records_path=database.RECORDS)
    with _while(review, "figure", path, scaled(a)):
        await user.open(f"/record?id={A}")
    assert path.read_bytes() == a
    with user:
        shown = [element.source for element in ElementFilter(kind=ui.image)]
    assert [base64.b64decode(source.split(",", 1)[1]) for source in shown] == [figure]
    user.find("your name, as it will be written into the record").type("A. Tester")
    user.find("I have compared the data and assumptions with the source").click()
    user.find("Mark as verified").click()
    assert captured == {"record": A, "hash": bound}

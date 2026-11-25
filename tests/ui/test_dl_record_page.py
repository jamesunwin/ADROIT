"""The auditor's DK recheck (DL-01) on the records page, where a person verifies a curated record: the figure the page shows,
its signature's state and the hash its verification binds are of one reading of the record and its data file; and the
matrix's row ``records.page`` (``record_page``). Record A is the owner's signed Fermi-LAT dwarfs, on a scratch copy of
its data file; its unsigned form is a scratch copy of the records file; every write of a records file is intercepted:
nothing is signed. $0."""
from __future__ import annotations

import base64
import re
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("nicegui")

from nicegui import ElementFilter, ui  # noqa: E402
from nicegui.testing import User  # noqa: E402

from tests.orchestrator.test_dj_fixes import A  # noqa: E402
from tests.orchestrator.test_dk_fixes import _while  # noqa: E402
from tests.orchestrator.test_dl_fixes import unbound_reads_see, versions  # noqa: E402

STATE = {"A": "current", "B": "stale"}          # the owner's signature of A, read against A's data and B's


def unsigned_copy(tmp: Path, record_id: str) -> Path:
    """A copy of the records file with ``record_id``'s signature lines taken out (as ``tests/conftest.awaiting``)."""
    from adroit.constraints import database
    text = database.RECORDS.read_text()
    start = text.index(f"  - id: {record_id}\n")
    end = text.find("\n  - id: ", start + 1)
    end = len(text) if end < 0 else end + 1
    block = re.sub(r"^    (verified_on|verified_by|verification_sha256):[^\n]*\n", "", text[start:end], flags=re.M)
    path = tmp / "records_unsigned.yaml"
    path.write_text(text[:start] + block + text[end:])
    return path


def shown(user: User) -> tuple[list[bytes], str]:
    """(the figures the page shows, decoded; the signature state it shows: "current" where it says the signature
    matches, else the state its "Signature: …" line names, "unreviewed" for one awaiting a person's)."""
    with user:
        images = [base64.b64decode(e.source.split(",", 1)[1]) for e in ElementFilter(kind=ui.image)
                  if e.source.startswith("data:")]
        texts = [e.text for e in ElementFilter(kind=ui.label)]
        badges = [e.text for e in ElementFilter(kind=ui.badge)]
    if "The signature matches the record as shown here." in texts and any(b.startswith("verified") for b in badges):
        return images, "current"
    said = next((t.removeprefix("Signature: ").split(";")[0] for t in texts if t.startswith("Signature: ")), "none")
    return images, said


class Clicks:
    """``review.verify`` as the page calls it, run for real against the scratch records file, its write intercepted:
    the hash each click bound, and whether verify accepted it ("accepted": it reached the write) or refused it."""

    def __init__(self, monkeypatch, records: Path) -> None:
        from adroit.constraints import review
        from adroit.core import durable
        self.bound, self.outcomes = [], []
        real, write = review.verify, durable.write_atomic

        def verify(record_id, by, path=None, expected_sha256=""):
            self.bound.append(expected_sha256)
            try:
                real(record_id, by, path=path, expected_sha256=expected_sha256)
            except ValueError as error:
                self.outcomes.append(f"refused: {error}")
                raise
        monkeypatch.setattr(review, "verify", verify)
        monkeypatch.setattr(durable, "write_atomic", lambda target, data: self.outcomes.append("accepted")
                            if Path(target) == records else write(target, data))


def click(user: User) -> None:
    user.find("your name, as it will be written into the record").type("A. Tester")
    user.find("I have compared the data and assumptions with the source").click()
    user.find("Mark as verified").click()


def after_reading(path: Path, data: bytes):
    """The data file ``data`` from the return of the page's reading on (``review.reading``), not restored."""
    import os

    from adroit.constraints import review
    real = review.reading

    def read(record_id):
        held = real(record_id)
        stamp = path.stat().st_mtime_ns + 13_000_000_000
        path.write_bytes(data)
        os.utime(path, ns=(stamp, stamp))
        return held
    return patch.object(review, "reading", read)


def read_as(path: Path, data: bytes, after: bytes):
    """The page's reading made while the data file holds ``data``, ``after`` from its return on (the auditor's
    ``dk_review_status_server``: B captured, A restored)."""
    import os

    from adroit.constraints import review
    real = review.reading

    def read(record_id):
        stamp = path.stat().st_mtime_ns
        path.write_bytes(data)
        os.utime(path, ns=(stamp + 17_000_000_000, stamp + 17_000_000_000))
        try:
            return real(record_id)
        finally:
            path.write_bytes(after)
            os.utime(path, ns=(stamp + 19_000_000_000, stamp + 19_000_000_000))
    return patch.object(review, "reading", read)


def _figures(path: Path, data: dict[str, bytes]) -> dict[str, bytes]:
    """Each version's figure, drawn from a reading of it alone."""
    from adroit.constraints import review
    drawn = {}
    for label in "AB":
        path.write_bytes(data[label])
        held = review.reading(A)
        drawn[label] = review.figure(held.record, held)
    path.write_bytes(data["A"])
    assert drawn["A"] != drawn["B"]
    return drawn


async def record_page(user: User, tmp_path: Path, monkeypatch, case: str) -> str:
    """The matrix's row ``records.page``: what the record page shows, read against A's figure, state and version.
    B: the signed record's page shows A's figure and its current signature; the unsigned copy's click binds A's
    version, accepted. T1: the data file B from the page's reading on, not restored: the signed record's page shows A
    whole, and, read as B with A restored after (the auditor's order), B's figure with its stale state; the unsigned copy's
    page shows A's figure, and its click, bound to A's version, is refused. ABA: B while its figure is drawn and at
    every signature check not bound to its reading, A's very bytes after: the page shows A whole, and the click binds
    A's version, accepted. Returns "A", "A then refused", or what was seen."""
    from adroit.constraints import database
    from adroit.constraints.review_identity import fingerprint
    from adroit.ui.app import build_pages
    path, data = versions(tmp_path, monkeypatch)
    figures, version = _figures(path, data), fingerprint(database.record(A))
    unsigned = unsigned_copy(tmp_path, A)
    clicks = Clicks(monkeypatch, unsigned)
    (tmp_path / "runs").mkdir()
    build_pages(tmp_path / "runs", records_path=unsigned)

    def changes() -> ExitStack:
        stack = ExitStack()
        if case == "T1":
            stack.enter_context(after_reading(path, data["B"]))
        elif case == "ABA":
            from adroit.constraints import review, review_identity, review_packets
            from adroit.ui import records
            stack.enter_context(_while(review, "figure", path, data["B"]))
            status = unbound_reads_see(path, data["B"])
            for module in (review_identity, review_packets, records):      # each name a signature is checked by
                stack.enter_context(patch.object(module, "signature_status", status))
        return stack
    seen = []
    with changes():
        await user.open(f"/record?id={A}")
    signed = shown(user)
    seen.append(f"signed: {'A' if signed[0] == [figures['A']] else 'B' if signed[0] == [figures['B']] else '?'}'s "
                f"figure, {signed[1]}")
    whole = signed == ([figures["A"]], STATE["A"])
    if case == "T1":
        path.write_bytes(data["A"])
        with read_as(path, data["B"], data["A"]):
            await user.open(f"/record?id={A}")
        reverse = shown(user)
        seen.append(f"read as B: {reverse[1]}")
        whole = whole and reverse == ([figures["B"]], STATE["B"])
        path.write_bytes(data["A"])
    monkeypatch.setattr(database, "RECORDS", unsigned)
    with changes():
        await user.open(f"/record?id={A}")
    first = shown(user)
    whole = whole and first == ([figures["A"]], "unreviewed")
    click(user)
    seen.append(f"unsigned: {first[1]}; bound {'A' if clicks.bound == [version] else clicks.bound}; {clicks.outcomes}")
    bound = clicks.bound == [version]
    if case == "T1":
        refused = len(clicks.outcomes) == 1 and clicks.outcomes[0].startswith("refused: scientific content changed")
        return "A then refused" if whole and bound and refused else "; ".join(seen)
    return "A" if whole and bound and clicks.outcomes == ["accepted"] else "; ".join(seen)


@pytest.mark.parametrize("captured", ["A", "B"])
async def test_a_record_page_shows_the_signature_state_of_the_version_it_shows(user: User, tmp_path, monkeypatch,
                                                                               captured) -> None:
    """DL-01 on the page, the auditor's ``dk_review_status_browser``: the page's reading made while the data file holds
    ``captured``, the other from its return on. The page shows ``captured``'s figure beside its own signature state:
    A's current signature, or B's stale one, never "verified" beside B's figure. Before, the state was read again
    from the file as it then stood: B's figure was shown as verified, "the signature matches the record as it is
    now"."""
    from adroit.constraints import database
    from adroit.ui.app import build_pages
    path, data = versions(tmp_path, monkeypatch)
    figures = _figures(path, data)
    other = "B" if captured == "A" else "A"
    (tmp_path / "runs").mkdir()
    build_pages(tmp_path / "runs", records_path=database.RECORDS)
    with read_as(path, data[captured], data[other]):
        await user.open(f"/record?id={A}")
    assert shown(user) == ([figures[captured]], STATE[captured])
    if captured == "B":
        with user:
            assert not [e for e in ElementFilter(kind=ui.badge) if e.text.startswith("verified")]


async def test_a_verification_shows_its_new_state_only_while_the_record_is_as_shown(user: User, tmp_path,
                                                                                   monkeypatch) -> None:
    """DL-01, after a verification: the record is read again, and its state shown only while its version is the one
    the page showed. Here the data file is changed between the click and that reading: the page says the record has
    changed since it was drawn, and shows no state of the changed record. (The click itself is accepted: its write is
    intercepted, nothing signed.)"""
    from adroit.constraints import database, review
    from adroit.ui.app import build_pages
    path, data = versions(tmp_path, monkeypatch)
    unsigned = unsigned_copy(tmp_path, A)
    monkeypatch.setattr(database, "RECORDS", unsigned)
    clicks = Clicks(monkeypatch, unsigned)
    (tmp_path / "runs").mkdir()
    build_pages(tmp_path / "runs", records_path=unsigned)
    await user.open(f"/record?id={A}")
    real = review.reading
    monkeypatch.setattr(review, "reading", lambda record_id: (path.write_bytes(data["B"]), real(record_id))[1])
    click(user)
    assert clicks.outcomes == ["accepted"]
    await user.should_see("The record has changed since this page was drawn")
    with user:
        assert not [e for e in ElementFilter(kind=ui.badge) if e.text.startswith("verified")]

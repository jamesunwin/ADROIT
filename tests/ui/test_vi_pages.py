"""The auditor's version-identity audit (2026-11-03), at the study page and the point page: VI-01, the page had shown A's
title and cost beside B's report, the study record and the result read apart; VI-02, a point link had named a point
by its name in the study, which names another point in another version; VI-03, the downloads had required the result's
digest only, not the evidence and the report the page read. Each study is published by the production writer
(``runs._write``); nothing is calculated."""
from __future__ import annotations

import hashlib
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse

from nicegui.testing import User

from adroit.orchestrator import studies
from tests.orchestrator.test_vi_audit import publish, versions


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def test_the_study_page_reads_its_record_again_with_a_result_published_since(user: User, tmp_path):
    """VI-01, the auditor's page case: the page has read A's record, and B is published whole before the page has finished
    reading. Its files are read again together (the version handle, 2026-11-03): B's title, cost and report, never A's
    title and cost beside B's report."""
    from tests.version_events import during_resolution
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    a, b = versions(root / "study")
    publish(root / "study", a, "A", 1.25)
    with during_resolution("study.json", lambda: publish(root / "study", b, "B", 9.5)) as fired:
        await user.open("/study?" + urlencode({"path": "study"}))
    assert fired
    await user.should_see("B study")
    await user.should_see("cost $9.50 settled")
    await user.should_see("B report body")
    await user.should_not_see("A study")
    await user.should_not_see("cost $1.25 settled")
    await user.should_not_see(marker="study_record_of_another")


async def test_the_study_page_withholds_a_record_of_another_version(user: User, tmp_path):
    """VI-01: A's record written back over B's publication (A's writer recording after B's published): the page shows
    B's result and report, and says its record is of another version, with no title, cost or dates from it."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    a, b = versions(root / "study")
    publish(root / "study", a, "A", 1.25)
    old = studies.load(root / "study")
    publish(root / "study", b, "B", 9.5)
    studies.save(old)
    await user.open("/study?" + urlencode({"path": "study"}))
    await user.should_see("This study was replaced while it was read")
    await user.should_see(marker="study_record_of_another")
    await user.should_see("B report body")
    await user.should_not_see(marker="study_cost")
    await user.should_not_see("A study")


async def test_the_study_page_shows_a_record_written_before_as_found_saying_so(user: User, tmp_path):
    """VI-01's legacy case: a record naming no result (written before ADROIT tied them) is shown as found, saying so;
    one naming the result is shown with no qualification."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    a, _ = versions(root / "study")
    publish(root / "study", a, "A", 1.25)
    await user.open("/study?" + urlencode({"path": "study"}))
    await user.should_see("A study")
    await user.should_not_see(marker="study_record_unchecked")
    studies.save(studies.load(root / "study").model_copy(update={"result_sha256": ""}))
    await user.open("/study?" + urlencode({"path": "study"}))
    await user.should_see("A study")
    await user.should_see(marker="study_record_unchecked")


async def test_a_point_link_names_the_version_it_was_chosen_from(user: User, tmp_path):
    """VI-02, the auditor's case: grid:0 is (50, 500), excluded, in A. The link the table offers names A's digest (and its
    evidence's identity, the version handle); B
    published, following that link is refused, saying the point may be another one now, never B's grid:0 shown as
    the point chosen. Following it unraced shows A's point."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    a, b = versions(root / "study")
    held = sha(publish(root / "study", a, "A"))
    await user.open("/study?" + urlencode({"path": "study"}))
    table = user.find(marker="points").elements.pop()
    link = next(r for r in table.rows if r["point"] == "grid:0")["open"]
    evidence = sha((root / "study" / "result.evidence.json").read_bytes())      # and the evidence it read (VI-03)
    assert parse_qs(urlparse(link).query) == {"path": ["study"], "point": ["grid:0"], "sha256": [held],
                                              "evidence": [evidence]}
    await user.open(link)
    await user.should_see("m_chi = 50")
    publish(root / "study", b, "B")
    await user.open(link)
    await user.should_see("Point unavailable")
    await user.should_see("changed since the point was chosen")
    await user.should_not_see("m_chi = 900")


async def test_the_downloads_require_the_evidence_and_the_report_the_page_read(user: User, tmp_path):
    """VI-03: the page passes its downloads the identities of the evidence and the report it read with the result
    (``build.evidence_identity``, ``bindings.presentation``), and its "Run again" links the evidence's."""
    from adroit.evidence.bindings import presentation, read_report
    from adroit.evidence.build import evidence_identity
    from adroit.ui import exports
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    a, _ = versions(root / "study")
    content = publish(root / "study", a, "A")
    seen = []
    with patch.object(exports, "download_menu", lambda *args: seen.append(args)):
        await user.open("/study?" + urlencode({"path": "study"}))
    folder = root / "study"
    (found,), = seen                                    # the page's version, whose token each download narrows
    token = found.token()
    assert (token.result, token.evidence, token.presentation) == (
        sha(content), evidence_identity(folder / "result.json", content),
        presentation(read_report(folder / "report.md", sha(content))))
    assert token.evidence not in ("", "none") and token.presentation not in ("", "none") and token.record

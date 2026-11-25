"""The auditor's CX recheck, CY-02 and CY-03 (2026-11-01), through the rendered workbench: a study page holding one version of
its result had shown another version's report and input history, and its Promote had acted on another version's
candidate. Everything the page shows of the result, and every action it starts, is now of its one read: the report and
its figures as bound to that result, its evidence as the evidence of those bytes, and its continuations and downloads
carrying their digest."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from urllib.parse import urlencode

from nicegui import ui
from nicegui.testing import User

from adroit.core.durable import write_atomic
from adroit.ui import engine
from tests.orchestrator.test_cx_recheck import _publish, _published_after_open, _versions


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cited(folder, version: tuple[bytes, ...], source: str) -> tuple[bytes, bytes, bytes]:
    """A version whose evidence cites the invisible-width record, with ``source`` as its recorded source (as the auditor's
    case: A's as it is now, B's "AUDIT B-only source history")."""
    from adroit.constraints.database import records
    from adroit.core.evidence import EvidenceEnvelope, EvidenceObservation, SourceEvidence
    from adroit.parameter_space.scan import HIGGS_INVISIBLE
    current = next(r for r in records() if r.id == HIGGS_INVISIBLE).model_dump(mode="json")
    envelope = EvidenceEnvelope.model_validate_json(version[1])
    context = envelope.context.model_copy(update={"sources": [SourceEvidence(
        id=HIGGS_INVISIBLE, version=str(current["version"]), metadata={**current, "source": source or current["source"]},
        review="not_required")]})
    cited = EvidenceObservation(subject_id="s", physical_input={}, observable="x", source_ids=[HIGGS_INVISIBLE])
    return version[0], envelope.model_copy(update={"context": context, "observations": [
        *envelope.observations, cited]}).model_dump_json().encode(), version[2]


def _audited_study(root, monkeypatch):
    from tests.orchestrator.test_cw_recheck import _toy_study
    folder = _toy_study(root, monkeypatch, False)
    a, b = _versions(folder)
    a, b = _cited(folder, a, ""), _cited(folder, b, "AUDIT B-only source history")
    _publish(folder, a)
    return folder, a, b


def _reanalysis_targets(user: User) -> list[str]:
    """Where the page's links to a reanalysis go."""
    from nicegui import ElementFilter
    with user:
        links = list(ElementFilter(kind=ui.link))
    return [e.props.get("href", "") for e in links if "/reanalyse?" in e.props.get("href", "")]


async def test_a_study_page_holding_a_shows_neither_b_s_report_nor_b_s_input_history(user: User, tmp_path, monkeypatch):
    """CY-03, the auditor's case: B (result, evidence and report; B alone recording another source history) published just
    after the page has read A. The page reads A whole, in one version (the version handle, 2026-11-03), and shows A
    throughout: A's report, never B's report nor B's history; no link of it names B. Opened again (warm), the
    page is B's throughout: B's report, B's history. B published while the page reads its files: B's throughout too.
    Stable A: A's report, no update. (Before the handle, the page read its report after its result, and a report of
    another version found there was withheld; the report is now read with the result.)"""
    from tests.version_events import after_resolution
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder, a, b = _audited_study(root, monkeypatch)
    page = "/study?" + urlencode({"path": folder.name})
    await user.open(page)
    await user.should_see("A report")
    await user.should_not_see(marker="study_updates")
    with after_resolution(lambda: _publish(folder, b)) as resolved:
        await user.open(page)
    assert resolved and resolved[0].content == a[0]
    await user.should_see("A report")
    await user.should_not_see("B report")
    await user.should_not_see("AUDIT B-only source history")
    await user.should_not_see(marker="report_of_another")
    await user.should_not_see(marker="study_updates")               # A's history: nothing to update, as stable A
    assert not any(f"sha256={sha(b[0])}" in href for href in _reanalysis_targets(user))
    await user.open(page)                                            # warm, B settled: B's throughout
    await user.should_see("B report")
    await user.should_see("AUDIT B-only source history")
    await user.should_not_see(marker="report_of_another")
    assert _reanalysis_targets(user) and all(f"sha256={sha(b[0])}" in href for href in _reanalysis_targets(user))
    _publish(folder, a)
    with _published_after_open(folder / "result.json", lambda: _publish(folder, b)) as done:
        await user.open(page)                                        # B published during the page's read
    assert done
    await user.should_see("B report")
    await user.should_not_see(marker="report_of_another")


async def test_an_unbound_report_is_read_with_the_result_it_is_shown_beside(user: User, tmp_path, monkeypatch):
    """CY-03, with reports recording no binding (as every report written before): B published just after the page has
    read A. The report was read with A, in one version (the version handle, 2026-11-03): A's report is shown as found,
    said to be unchecked, never B's report under A; B published while the page reads its files, B's report beside B's
    result. (Before the handle, the report was read after the result, and one recording no binding was withheld where
    the result had changed since: "unsettled".)"""
    from tests.version_events import after_resolution, during_resolution
    from adroit.ui.app import build_pages
    from tests.orchestrator.test_cy_recheck import _unbound
    root = build_pages(tmp_path / "runs")
    folder, a, b = _audited_study(root, monkeypatch)
    a, b = _unbound(a), _unbound(b)
    _publish(folder, a)
    page = "/study?" + urlencode({"path": folder.name})
    with after_resolution(lambda: _publish(folder, b)):
        await user.open(page)
    await user.should_not_see("B report")
    await user.should_see("A report")
    await user.should_see(marker="report_unchecked")
    _publish(folder, a)
    with during_resolution("result.json", lambda: _publish(folder, b)) as done:
        await user.open(page)
    assert done
    await user.should_see("B report")
    await user.should_not_see("A report")


async def test_a_bound_report_s_figure_is_shown_from_its_checked_bytes_or_withheld(user: User, tmp_path, monkeypatch):
    """CY-03: a report's figure is embedded from its bytes as read once, checked against the report's binding, never
    served from the folder later; replaced since the report was written, it is withheld, saying so. A report written
    before ADROIT bound them is shown as found, saying it is not checked."""
    from adroit.evidence.bindings import unbound
    from adroit.ui.app import build_pages
    from tests.orchestrator.test_cy_recheck import figured
    root = build_pages(tmp_path / "runs")
    folder = figured(root, monkeypatch)
    page = "/study?" + urlencode({"path": str(folder.relative_to(root))})
    await user.open(page)
    shown = [e.content for e in user.find(kind=ui.markdown).elements]
    assert any("data:image/png;base64," in text for text in shown)
    assert not any("/files/" in text for text in shown)
    figure = folder / "parameter_plane.png"
    figure.write_bytes(figure.read_bytes() + b"\0")
    await user.open(page)
    await user.should_see("is not the one this report was written with")
    write_atomic(folder / "report.md", unbound((folder / "report.md").read_text()))
    await user.open(page)
    await user.should_see(marker="report_unchecked")


async def test_promote_acts_on_the_candidates_the_page_showed_or_on_none(user: User, tmp_path, monkeypatch):
    """CY-02, the auditor's case: class 0 chosen on a page showing A; the command carries A's digest. B (class 0 another
    candidate) published after the page was read and before the click: nothing is launched, saying why."""
    from adroit.ui.app import build_pages
    from tests.ui.test_workflow_acceptance import _signal_study
    root = build_pages(tmp_path / "runs")
    folder = root / "signal"
    _signal_study(folder)
    a = (folder / "result.json").read_bytes()
    launched = []
    monkeypatch.setattr(engine, "launch", lambda command, folder, title, **kw: launched.append(command) or
                        SimpleNamespace(folder=str(folder)))
    await user.open("/study?path=signal")
    user.find("candidate or class").elements.pop().value = "class:0"
    user.find(kind=ui.button, content="Promote").click()
    command = launched.pop()
    assert command[command.index("--parent-sha256") + 1] == sha(a) and "class:0" in command
    await user.open("/study?path=signal")
    data = json.loads(a)
    data["classes"] = {"scalar @ 10": 1, "scalar @ 20": 0}
    write_atomic(folder / "result.json", json.dumps(data))
    user.find("candidate or class").elements.pop().value = "class:0"
    user.find(kind=ui.button, content="Promote").click()
    await user.should_see("has changed since its candidates were selected")
    assert not launched


async def test_a_reanalysis_opened_from_a_page_refuses_another_version(user: User, tmp_path, monkeypatch):
    """CY-03: the reanalysis form opened from a study page (with the digest the page showed) says which version it
    reopens, and with B published since, drafts nothing, saying why."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folder, a, b = _audited_study(root, monkeypatch)
    _publish(folder, b)
    source = str(folder / "result.json")
    await user.open("/reanalyse?" + urlencode({"source": source, "sha256": sha(a[0])}))
    await user.should_see(marker="reanalysis_version")
    user.find(kind=ui.button, content="Reopen saved inputs").click()
    await user.should_see("has changed since its page was opened")


def test_an_approval_saves_the_reviewed_source_not_the_file_read_again(tmp_path, monkeypatch):
    """The approval panel's library copy of its idea study's result is of the bytes the models were reviewed from (the
    page's one read), never the file read again after its check (the auditor's CX recheck, 2026-11-01)."""
    from adroit.library import personal
    from adroit.orchestrator import model_approval
    from adroit.ui import forms, pages
    held = b'{"held": "the reviewed version"}'
    write_atomic(tmp_path / "result.json", b'{"other": "published since"}')
    saved = {}

    class Library:
        def asset(self, path, role="user_source"):
            return ("file", path.name, role)

        def asset_bytes(self, name, data, role="user_source"):
            return ("bytes", name, data, role)

        def save(self, spec, approval, tex, sources, provenance):
            saved["sources"] = sources
    monkeypatch.setattr(personal, "Catalog", Library)
    monkeypatch.setattr(model_approval, "write_approved", lambda path, spec, approval: None)
    monkeypatch.setattr("adroit.model_building.tex.render", lambda spec: "")
    monkeypatch.setattr(forms, "track1_command", lambda *a, **k: ["track1"])
    spec = SimpleNamespace(name="m", model_dump=lambda mode: {})
    row = {"state": {"spec": spec, "approval": SimpleNamespace(model_sha256="a" * 64, choice="supplied"),
                     "unsupported": True}, "save_catalog": SimpleNamespace(value=True),
           "ratio": SimpleNamespace(value=0), "x": SimpleNamespace(value=""), "y": SimpleNamespace(value="")}
    pages._approved_run(tmp_path, row, held)
    assert ("bytes", "result.json", held, "idea_source") in saved["sources"]

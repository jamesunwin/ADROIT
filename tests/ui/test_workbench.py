"""DM15: the workbench's pages, headless (NiceGUI's User), on a synthetic runs directory."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("nicegui")

from nicegui import ui  # noqa: E402
from nicegui.testing import User  # noqa: E402

from adroit.orchestrator import studies  # noqa: E402
from adroit.ui import engine  # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A Path 2 run with three promoted children (DM14's gate), a Track 1 study, an idea and a failed job."""
    root = tmp_path / "runs"
    shutil.copytree(DOCS / "dm14" / "recursion" / "signal_cdms_si", root / "signal_cdms_si")
    t1 = root / "track1_axial"
    shutil.copytree(DOCS / "dm13" / "reports" / "axial_mediator", t1)
    studies.record(t1, "track1", "Track 1: axial_mediator")
    from adroit.core.model_spec import ModelSpec
    from adroit.orchestrator import ideas, runs
    spec = ModelSpec.model_validate({"name": "singlet", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1},
        {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True}]})
    runs.idea(ideas.IdeaRequest(fields_spec=spec), folder=root / "idea_singlet", name="singlet")
    failed = root / "track1_broken"
    failed.mkdir()
    engine.save(engine.Job(title="a broken run", kind="track1", command=["track1", "x.yaml"], folder=str(failed),
                           status="failed"))
    (failed / engine.LOG).write_text("Traceback: something\n")
    return root


@pytest.fixture
def pages(user: User, workspace: Path) -> Path:
    from adroit.ui.app import build_pages
    return build_pages(workspace)


async def test_home_shows_the_name_the_acronym_and_the_menu_as_buttons(user: User, pages: Path) -> None:
    from adroit.ui.pages import ACRONYM, NAV
    await user.open("/")
    await user.should_see("ADROIT")
    await user.should_see(ACRONYM)
    assert [n for n, _ in NAV[:5]] == ["Home", "Studies", "Constrain a model", "Signal best fits", "Explain a signal"] and len(NAV) == 9
    assert ("Add a limit", "/experiments") in NAV and ("Add a signal", "/new/anomaly") in NAV       # the owner, 2026-10-13
    for name, _ in NAV[1:]:
        await user.should_see(name, kind=ui.button)
    user.find(kind=ui.button, content="Studies").click()
    await user.should_see("studies to revisit after updates")
    await user.should_not_see("total spent")             # no running total of spending (the owner, 2026-10-23)


async def test_studies_shows_the_tree_of_studies_and_failed_runs(user: User, pages: Path) -> None:
    await user.open("/studies")
    await user.should_see("Path 2: CDMS II Si (2013)")
    await user.should_see("scalar_mediator_for_O1 for CDMS II Si (2013)")
    await user.should_see("Track 1: axial_mediator")
    await user.should_not_see("total spent")
    await user.should_see("a broken run")


async def test_a_path_two_study_offers_promotion_and_lists_its_children(user: User, pages: Path) -> None:
    await user.open("/study?path=signal_cdms_si")
    await user.should_see("Promote a candidate to studies (recursion)")
    await user.should_see("Studies made from this one:")
    await user.should_see("vector_mediator_for_O1_O1s_10")


async def test_a_child_links_to_its_parent_and_shows_its_report(user: User, pages: Path) -> None:
    folder = pages / "signal_cdms_si/children/vector_mediator_for_O1_O1s_10"
    (folder / "report.md").write_text("# Child report\n\nSaved report for the promoted vector model.\n")
    await user.open("/study?path=signal_cdms_si/children/vector_mediator_for_O1_O1s_10")
    await user.should_see("from")
    await user.should_see("Saved report for the promoted vector model.")


async def test_an_idea_study_offers_its_valid_models_for_track_one(user: User, pages: Path) -> None:
    await user.open("/study?path=idea_singlet")
    await user.should_see("Approve models to constrain")
    await user.should_see("valid")


async def test_the_live_view_shows_status_and_log(user: User, pages: Path) -> None:
    await user.open("/live?path=track1_broken")
    await user.should_see("failed")
    await user.should_see("Traceback: something")


async def test_a_path_outside_the_runs_directory_is_refused(user: User, pages: Path) -> None:
    from adroit.ui.pages import inside
    with pytest.raises(ValueError):
        inside(pages, "../../etc")


async def test_the_wizards_render(user: User, pages: Path) -> None:
    await user.open("/new/track1")
    await user.should_see("Check a dark matter model against every search")          # each page says what it does
    await user.should_see("A library model")
    await user.should_see("Build from fields")
    await user.should_see("Build from words (paid)")
    await user.should_see("Derive couplings (paid)")
    await user.open("/new/track2")
    await user.should_see("the library's space as well")
    await user.open("/new/single")
    await user.should_see("Run the study")
    await user.open("/new/anomaly")
    await user.should_see("Draft")
    await user.should_see("AI can make mistakes.")                    # under every live call's model choice


def test_every_live_call_chooses_its_model_with_the_reminder() -> None:
    """The owner (2026-10-16): "AI can make mistakes." small, wherever a live call is made. Every paid panel takes
    its model from ``model_select``, which carries the note; a paid panel with a model menu of its own would not."""
    import re
    root = Path(__file__).resolve().parents[2] / "adroit" / "ui"
    for path in root.glob("*.py"):
        text = path.read_text()
        if "budget_form(" in text and path.name != "pages.py":
            assert "model_select(" in text, path.name
        assert not re.search(r"ui\.select\(PRIMARY_MODELS", text) or path.name == "pages.py", path.name


async def test_the_reports_plots_are_served_from_the_runs_directory(user: User, pages: Path) -> None:
    from adroit.ui.pages import with_files
    text = with_files("![p](parameter_plane.png) and ![q](https://x/y.png)", pages, pages / "track1_axial")
    assert "(/files/track1_axial/parameter_plane.png)" in text and "(https://x/y.png)" in text


async def test_the_records_page_lists_records_and_a_record_can_be_verified(user: User, workspace: Path,
                                                                           tmp_path: Path, monkeypatch,
                                                                           awaiting) -> None:
    from adroit.constraints import database
    from adroit.ui.app import build_pages
    awaiting("lep-inert-doublet")                                       # unsigned in the copy, whatever the owner has signed
    copy = tmp_path / "records.yaml"
    copy.write_text(database.RECORDS.read_text())
    monkeypatch.setattr(database, "RECORDS", copy)
    database.records.cache_clear()
    build_pages(workspace, records_path=copy)
    await user.open("/records")
    await user.should_see("await a person's verification")
    await user.open("/record?id=lep-inert-doublet")
    await user.should_see("Compare with arXiv:0810.3924")
    user.find("your name, as it will be written into the record").type("A. Physicist")
    user.find("I have compared the data and assumptions with the source").click()
    user.find("Mark as verified").click()
    await user.should_see("verified by A. Physicist")
    assert 'verified_by: "A. Physicist"' in copy.read_text()      # always a string (the audit loop's AL1-09)
    database.records.cache_clear()
    await user.open("/record?id=sabti-1910.01649-bbn")                   # the reviewer's notes (2026-10-13)
    await user.should_see("Notes")


async def test_a_record_page_names_a_curve_its_tool_cannot_supply(user: User, workspace: Path, monkeypatch) -> None:
    """The fallback review's D4: DarkCast's record had read "single numbers" without DarkCast, L_μ − L_τ's lost
    BaBar's curve without a word."""
    from adroit.constraints import searches
    from adroit.ui.app import build_pages
    monkeypatch.setattr(searches, "_tool", lambda name: None)
    build_pages(workspace)
    await user.open("/record?id=lmu-ltau-babar-belle2")
    await user.should_see("Not shown: BaBar's curve (from DarkCast")
    await user.open("/record?id=darkcast-dark-photon")
    await user.should_see("Not shown: every search's excluded region (from DarkCast")
    await user.should_not_see("This record holds single numbers")


async def test_selected_review_queue_shows_exact_pending_action(user: User,workspace: Path,
                                                                       tmp_path: Path,monkeypatch) -> None:
    from adroit.constraints import database
    from adroit.core.evidence import EvidenceContext,SourceEvidence
    from adroit.evidence.build import save
    from adroit.model_building.audit import audit
    from adroit.orchestrator.track1 import for_portal,Track1Result
    from adroit.parameter_space.scan import ScanRequest,ScanResult,PointResult
    from adroit.parameter_space.verdict import Verdict,Crossing
    from adroit.parameter_space.limits import StatisticalLimit
    from adroit.ui.app import build_pages
    request=for_portal("higgs_portal_scalar",literature=False)
    record=database.record("hess-1805.05741-lines")
    why=f"its record ({record.id}) awaits a person's verification"
    row=PointResult(point=request.fixed,omega_h2=.12,dd_kind="SI",dd_sigma_cm2=1e-46,dd_limit_cm2=1e-44,
        excluded={"gamma rays":None},pending=[why],statistical_limits={"gamma rays":StatisticalLimit(
            value=None,confidence_level=.95,source=record.source,construction="source curve")})
    scan=ScanResult(request=ScanRequest(model_class=request.model_class,fixed=request.fixed,x=request.x,y=request.y),
                    xs=[],ys=[],points=[])
    crossing=Crossing(point=row.point,status="pending",pending=[why],omega_h2=.12,kind="contour",evaluation=row)
    result=Track1Result(request=request,audit=audit(request.spec),scan=scan,
        verdict=Verdict(level="viable_pending",target=.12,summary="review pending",crossings=[crossing]))
    folder=workspace/"review_pending"
    folder.mkdir()
    path=folder/"result.json"
    path.write_text(result.model_dump_json())
    import importlib
    evidence_build=importlib.import_module("adroit.evidence.build")
    monkeypatch.setattr(evidence_build,"finish",lambda c,read=None,consumed=None:c)
    save(path,context=EvidenceContext(origin="captured",sources=[SourceEvidence(id=record.id,reference=record.source,
        metadata=record.model_dump(mode="json"),review="unreviewed")]))
    studies.record(folder,"track1","pending review study")
    build_pages(workspace)
    await user.open("/records?study=review_pending")
    await user.should_see("1 blocked points")
    await user.should_see(f"source verification: {record.id}")
    await user.open(f"/record?id={record.id}&study=review_pending")
    await user.should_see(why)
    await user.should_see("Saved comparisons and source changes")
    await user.should_not_see("Optional researcher review timer")       # dropped from the page (the owner, 2026-10-12)

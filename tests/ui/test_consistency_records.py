"""The consistency audit of 2026-10-24 (the independent audit of 2026-10-24 (consistency)): CA-07 and CA-08, a damaged record
named and contained. One healthy and one damaged record of each durable family, through the listing, the page that
shows it and the command that lists it; and study histories whose records are each valid but whose links loop or
disagree. Every record is written directly in the test's own folders; no provider, request or calculation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.orchestrator import annotations, studies
from adroit.ui import batch, engine


def _job(folder: Path, title: str = "a healthy run") -> engine.Job:
    folder.mkdir(parents=True, exist_ok=True)
    job = engine.Job(title=title, kind="track1", folder=str(folder), command=["track1", "--out", "."],
                     status="completed", returncode=0)
    engine.save(job)
    return job


def _broken_job(folder: Path) -> Path:
    folder.mkdir(parents=True)
    (folder / engine.JOB).write_text("{}")
    return folder


# --- CA-07: jobs, batches, annotations ------------------------------------------------------------------------------

def test_a_damaged_job_is_named_and_the_healthy_ones_listed(tmp_path):
    _job(tmp_path / "good")
    _broken_job(tmp_path / "broken")
    jobs, damaged = engine.listing(tmp_path)
    assert [j.title for j in jobs] == ["a healthy run"] and engine.jobs(tmp_path) == jobs
    assert len(damaged) == 1 and damaged[0].path.endswith("broken/job.json") and "ValidationError" in damaged[0].why
    with pytest.raises(ValueError):
        engine.load(tmp_path / "broken")                   # opening it directly stays strict


async def test_a_damaged_job_beside_a_study_leaves_every_page_usable(user: User, tmp_path):
    """CA-07: one ``{}`` job record made the Home and Studies pages fail (a 500); the menu's counts on every page read
    every job. Now Home, Studies and Activity load and name it, the healthy study opens, and the damaged run's own
    page says its record cannot be read."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _job(root / "healthy")
    studies.record(root / "healthy", "track1", "a healthy study")
    _broken_job(root / "broken")
    await user.open("/")
    await user.open("/studies")
    await user.should_see("a healthy study")
    await user.should_see(marker="unreadable_runs")
    await user.should_see("broken/job.json")
    await user.open("/activity")
    await user.should_see(marker="unreadable_runs")
    await user.open("/study?path=healthy")
    await user.should_see("a healthy study")
    await user.open("/live?path=broken")
    await user.should_see("Run record unreadable")


async def test_a_study_whose_own_job_record_is_damaged_still_lists(user: User, tmp_path):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _job(root / "study")
    studies.record(root / "study", "track1", "a study whose job record broke")
    (root / "study" / engine.JOB).write_text("{")
    await user.open("/studies")
    await user.should_see("a study whose job record broke")
    await user.should_see("cost not available")
    await user.open("/study?path=study")
    await user.should_see("its run's record, job.json, cannot be read")


def _batch(root: Path, name: str, body: str | None = None) -> None:
    folder = root / "batches" / name
    folder.mkdir(parents=True)
    if body is None:
        body = batch.Batch(title=name, folder=str(folder), created="2026-10-25T00:00:00", status="completed",
                           items=[]).model_dump_json()
    (folder / batch.BATCH).write_text(body)


def test_a_truncated_batch_is_named_and_the_healthy_ones_listed(tmp_path):
    _batch(tmp_path, "good")
    _batch(tmp_path, "broken", "{")
    found, damaged = batch.listing(tmp_path)
    assert [b.title for b in found] == ["good"] and len(damaged) == 1 and "broken/batch.json" in damaged[0].path


async def test_the_batch_page_names_a_damaged_batch(user: User, tmp_path):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _batch(root, "good")
    _batch(root, "broken", "{")
    await user.open("/batches")
    await user.should_see(marker="unreadable_batches")
    await user.should_see("good")


def test_an_invalid_annotation_is_named_kept_as_written_and_the_rest_read(tmp_path):
    """CA-07: one entry that is not an annotation made every annotation unreadable. It is named, the others read, and
    saving another study's annotation leaves the damaged entry exactly as it was (never dropped by a rewrite)."""
    path = tmp_path / annotations.FILE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"good": {"label": "ok"}, "bad": {"bogus": 1}}))
    notes, damaged = annotations.listing(tmp_path)
    assert list(notes) == ["good"] and annotations.load(tmp_path) == notes
    assert len(damaged) == 1 and damaged[0].path.endswith("[bad]")
    (tmp_path / "new").mkdir()
    annotations.save(tmp_path, tmp_path / "new", annotations.Annotation(label="later"))
    assert json.loads(path.read_text())["bad"] == {"bogus": 1}
    assert set(annotations.load(tmp_path)) == {"good", "new"}


def test_an_annotations_file_that_is_not_json_is_named_and_not_overwritten(tmp_path):
    path = tmp_path / annotations.FILE
    path.parent.mkdir(parents=True)
    path.write_text("{ not json")
    notes, damaged = annotations.listing(tmp_path)
    assert notes == {} and len(damaged) == 1
    (tmp_path / "s").mkdir()
    with pytest.raises(ValueError):
        annotations.save(tmp_path, tmp_path / "s", annotations.Annotation(label="x"))
    assert path.read_text() == "{ not json"


# --- CA-07: a session's steps, and the two libraries ---------------------------------------------------------------

def _typed_session():
    from adroit.orchestrator.model_intake import Intake
    from adroit.parameter_space.simplified import model
    service = Intake()
    s = service.start()
    service.step(s.session_id, "typed", yaml.safe_dump(model("vector", 10, 125, .001, .25).model_dump(mode="json")))
    return service, s.session_id


async def test_a_damaged_intake_step_is_named_and_the_session_shown(user: User, tmp_path):
    """CA-07: one ``{}`` step beside a valid one made the session's steps unreadable. The page shows the valid draft
    and names the damaged one; the strict ``steps`` (a refinement's parent is the last step) still refuses."""
    from adroit.ui.app import build_pages
    service, session = _typed_session()
    (service.folder(session) / "steps" / ("0" * 64 + ".json")).write_text("{}")
    found, damaged = service.listing(session)
    assert len(found) == 1 and len(damaged) == 1
    with pytest.raises(ValueError):
        service.steps(session)
    build_pages(tmp_path / "runs")
    await user.open(f"/models/intake?session={session}")
    await user.should_see(marker="unreadable_steps")


def _approved_revision():
    from adroit.orchestrator.model_approval import model_identity
    service, session = _typed_session()
    d = service.steps(session)[-1]
    c = d.choices[0]
    return service.approve(session, d.step_id, 0, confirmed=True, expected_model_hash=model_identity(c.spec), tex=c.tex)


async def test_a_damaged_model_revision_is_named_and_the_library_listed(user: User, tmp_path):
    """CA-07: one damaged revision stopped the personal library's page, its pickers and ``adroit models list``."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.catalog_cli import app as catalog_app
    from adroit.ui.app import build_pages
    good = _approved_revision()
    bad = Catalog().root / "models" / ("1" * 32) / "revisions"
    bad.mkdir(parents=True)
    (bad / ("2" * 64 + ".json")).write_text("{}")
    found, damaged = Catalog().listing()
    assert [r.reference for r in found] == [good.reference] and len(damaged) == 1
    listed = CliRunner().invoke(catalog_app, ["list"])
    assert listed.exit_code == 0 and good.reference in listed.output and "unreadable, not listed" in listed.output
    build_pages(tmp_path / "runs")
    await user.open("/models?view=personal")                 # the standard library is the default view (JU1)
    await user.should_see(marker="unreadable_revisions")
    await user.should_see(good.spec.name)


async def test_a_damaged_experimental_revision_is_named_and_the_library_listed(user: User, tmp_path):
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator.experimental_cli import app as experimental_app
    from adroit.ui.app import build_pages
    catalog = ExperimentalCatalog()
    source = tmp_path / "source.txt"
    source.write_text("a synthetic source")
    good = catalog.import_files([source], "a valid source")
    bad = catalog.path("experiments") / ("3" * 32) / ("4" * 64 + ".json")
    bad.parent.mkdir()
    bad.write_text("{}")
    found, damaged = catalog.listing()
    assert [r.reference for r in found] == [good.reference] and len(damaged) == 1
    with pytest.raises(ValueError):
        catalog.list()                                     # a calculation over the library stops on it
    listed = CliRunner().invoke(experimental_app, ["list"])
    assert listed.exit_code == 0 and good.reference in listed.output and "unreadable, not listed" in listed.output
    build_pages(tmp_path / "runs")
    await user.open("/experiments")
    await user.should_see(marker="unreadable_revisions")
    await user.should_see("a valid source")


# --- CA-08: the study history's links ------------------------------------------------------------------------------

def _study(folder: Path, parent: Path | None = None, children: list[Path] | None = None) -> studies.Study:
    """A study recorded as the workbench records one (``studies.record``: its parent, if given, lists it), its
    children then written as given."""
    folder.mkdir(parents=True, exist_ok=True)
    s = studies.record(folder, "idea", folder.name, parent=parent)
    if children is not None:
        studies.save(s.model_copy(update={"children": [str(c) for c in children]}))
    return s


GRAPHS = {
    # links written into otherwise valid records: the studies whose link problem is named
    "a study naming itself as its child": (lambda r: _study(r / "a", children=[r / "a"]), {"a"}),
    "two studies, each the other's parent": (
        lambda r: (_study(r / "a"), _study(r / "b"), _study(r / "a", parent=r / "b", children=[r / "b"]),
                   _study(r / "b", parent=r / "a", children=[r / "a"])), {"a", "b"}),
    "a child two parents list": (
        lambda r: (_study(r / "p"), _study(r / "q"), _study(r / "p" / "c", parent=r / "p"),
                   _study(r / "q", children=[r / "p" / "c"])), {"q"}),
    "a child its parent does not list": (
        lambda r: (_study(r / "p"), _study(r / "p" / "c", parent=r / "p"), _study(r / "p", children=[])), {"c"}),
    "a parent that is not there": (lambda r: _study(r / "orphan", parent=r / "gone"), set()),
}


@pytest.mark.parametrize("case", GRAPHS)
def test_a_history_whose_links_loop_or_disagree_lists_each_study_once_and_names_them(tmp_path, case):
    """CA-08: a study naming itself as its child made the history recurse without end (a RecursionError), and two
    studies each the other's parent vanished from it, named nowhere. Each study is now listed once, an unrelated one
    with them, and the links that loop or disagree are named."""
    from adroit.orchestrator.cli import app
    make, named = GRAPHS[case]
    make(tmp_path / "s")
    _study(tmp_path / "s" / "unrelated")
    listed = studies.tree(tmp_path / "s")
    folders = [Path(s.folder).name for _, s in listed]
    assert sorted(folders) == sorted({p.parent.name for p in (tmp_path / "s").rglob(studies.FILE)})
    assert len(folders) == len(set(folders)) and "unrelated" in folders
    assert {p.parent.name for p, _ in studies.inconsistent(tmp_path / "s")} == named
    assert studies.unreadable(tmp_path / "s") == []
    shown = CliRunner().invoke(app, ["studies", str(tmp_path / "s")])
    assert shown.exit_code == 0 and ("links loop or disagree" in shown.output) is bool(named)


async def test_the_studies_page_names_a_loop_and_still_lists_the_rest(user: User, tmp_path):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    GRAPHS["two studies, each the other's parent"][0](root)
    _study(root / "unrelated")
    await user.open("/studies")
    await user.should_see(marker="inconsistent_studies")
    for name in ("a", "b", "unrelated"):
        await user.should_see(name)

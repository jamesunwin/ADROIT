"""Deleting a personal model or a study (the owner, 2026-11-18, the post-review changes item 3): a confirmation
window names what goes; a model's studies go with it; the studies inside a study's folder go with it; every deleted
run's money records are kept; nothing is deleted while a run it touches runs; a deleted model's pages say so."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from nicegui.testing import User

from adroit.library.personal import Catalog, MissingRevision
from adroit.orchestrator import annotations as an
from adroit.orchestrator import studies
from adroit.ui import batch, deletion, engine
from adroit.ui.app import build_pages
from tests.orchestrator.test_annotations import _study
from tests.ui.test_model_library import stored


POLL = engine.poll                       # the real poll, for the test that needs a process looked for (MF-01)


@pytest.fixture(autouse=True)
def _jobs_as_recorded(monkeypatch):
    """A job's status as its record says (no process to look for)."""
    monkeypatch.setattr(engine, "poll", lambda folder: engine.load(folder))


def _job(folder: Path, status: str = "completed", command=("track1", "x.yaml")) -> None:
    engine.save(engine.Job(title=f"run {folder.name}", kind=command[0], command=list(command), folder=str(folder),
                           status=status))


def _money(folder: Path) -> None:
    (folder / "paid.jsonl").write_text('{"state": "opened"}\n')
    (folder / "paid.jsonl.held").write_text("mark")
    (folder / "paid_requests.json").write_text("{}")


def _tree(root: Path) -> tuple[Path, Path, Path]:
    """A study with a child, which has its own child, each a workbench run with its money records."""
    parent = Path(_study(root, "parent").folder)
    child = Path(_study(parent / "children", "child").folder)
    grandchild = Path(_study(child / "children", "grandchild").folder)
    studies.record(child, "track1", "study child", parent=parent)
    studies.record(grandchild, "track1", "study grandchild", parent=child)
    for folder in (parent, child, grandchild):
        _job(folder)
        _money(folder)
    return parent, child, grandchild


def _kept(root: Path) -> tuple[Path, dict]:
    [record] = list((root / deletion.DELETED).iterdir())
    return record, json.loads((record / "deleted.json").read_text())


def test_a_study_goes_with_the_studies_inside_it_and_its_money_records_are_kept(tmp_path):
    root = tmp_path / "runs"
    parent, child, grandchild = _tree(root)
    plan = deletion.plan_study(root, parent)
    assert plan.studies == [str(parent), str(child), str(grandchild)] and not plan.running
    deletion.delete_study(root, parent, plan)
    assert not parent.exists() and studies.tree(root) == []
    record, written = _kept(root)
    assert written["studies"] == ["parent", "parent/children/child", "parent/children/child/children/grandchild"]
    for folder in ("parent", "parent/children/child", "parent/children/child/children/grandchild"):
        for name in ("paid.jsonl", "paid.jsonl.held", "paid_requests.json", "job.deleted.json"):
            assert (record / "kept" / folder / name).is_file(), (folder, name)
    assert engine.listing(root)[0] == []                    # a kept job record is not read as a run


def test_a_child_alone_leaves_its_parent_and_its_parent_s_annotation(tmp_path):
    root = tmp_path / "runs"
    parent, child, grandchild = _tree(root)
    an.save(root, parent, an.Annotation(label="keep me"))
    an.save(root, child, an.Annotation(label="mine"))
    an.save(root, grandchild, an.Annotation(label="mine too"))
    deletion.delete_study(root, child, deletion.plan_study(root, child))
    assert parent.exists() and not child.exists()
    assert studies.load(parent).children == []
    assert list(an.load(root)) == ["parent"]


def test_nothing_is_deleted_while_a_run_inside_runs_or_after_the_plan_changed(tmp_path):
    root = tmp_path / "runs"
    parent, child, grandchild = _tree(root)
    _job(grandchild, status="running")
    plan = deletion.plan_study(root, parent)
    assert plan.running == ["run grandchild is running"]
    with pytest.raises(ValueError, match="is running"):
        deletion.delete_study(root, parent, plan)
    _job(grandchild)
    stale = deletion.plan_study(root, child)
    _study(child / "children", "another")
    with pytest.raises(ValueError, match="changed since you confirmed"):
        deletion.delete_study(root, child, stale)
    assert child.exists() and not (root / deletion.DELETED).exists()


def test_only_a_study_in_the_runs_folder_can_be_deleted(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "study.json").write_text("{}")
    for folder in (root, tmp_path / "elsewhere", root / "absent"):
        with pytest.raises(ValueError):
            deletion.plan_study(root, folder)


def test_a_model_goes_with_its_studies_and_its_batch_requests(tmp_path):
    root = tmp_path / "runs"
    r = stored()
    other = stored()
    used = Path(_study(root, "used", models=(r.reference,)).folder)
    nested = Path(_study(used / "children", "nested").folder)
    studies.record(nested, "track1", "study nested", parent=used)
    kept = Path(_study(root, "unrelated", models=(other.reference,)).folder)
    _job(used)
    _money(used)
    prepared = root / "prepared"
    prepared.mkdir()
    batch.add_to_draft(root, ["track1", r.reference, "--out", str(prepared / "out")], prepared, "queued scan")
    plan = deletion.plan_model(root, r.model_id)
    assert plan.studies == [str(used), str(nested)] and plan.batch_items == ["queued scan"] and plan.revisions == 1
    deletion.delete_model(root, r.model_id, plan)
    assert not used.exists() and kept.exists() and batch.draft(root) == []
    with pytest.raises(MissingRevision) as missing:
        Catalog().load(r.reference)
    assert isinstance(missing.value, ValueError) and isinstance(missing.value, FileNotFoundError)
    assert Catalog().load(other.reference).model_id == other.model_id
    record, written = _kept(root)
    assert written["kind"] == "model" and written["model_id"] == r.model_id
    assert (record / "kept" / "used" / "paid.jsonl").is_file()


def test_a_model_used_by_a_running_run_is_not_deleted(tmp_path):
    root = tmp_path / "runs"
    r = stored()
    running = root / "running"
    running.mkdir(parents=True)
    _job(running, status="running", command=("track1", r.reference))
    plan = deletion.plan_model(root, r.model_id)
    assert plan.running == ["run running is running"]
    with pytest.raises(ValueError, match="is running"):
        deletion.delete_model(root, r.model_id, plan)
    assert Catalog().load(r.reference).model_id == r.model_id


async def test_the_studies_page_deletes_a_study_after_its_window(user: User, tmp_path):
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    alone = Path(_study(root, "alone").folder)
    build_pages(root)
    await user.open("/studies?" + urlencode({}))
    assert len(user.find(marker="delete_study").elements) == 4          # one per study listed
    await user.open("/study?" + urlencode({"path": "parent/children/child"}))
    user.find(marker="delete_this_study").click()
    await user.should_see("Delete the study “study child”?")
    await user.should_see("This will also delete the 1 study made from it: study grandchild.")
    await user.should_see(deletion.KEPT_NOTE)
    user.find(marker="delete_cancel").click()
    assert child.exists()
    user.find(marker="delete_this_study").click()
    user.find(marker="delete_confirm").click()
    await user.should_see("Studies")
    assert not child.exists() and parent.exists() and alone.exists()


async def test_the_studies_list_s_delete_opens_the_same_window(user: User, tmp_path):
    root = tmp_path / "runs"
    alone = Path(_study(root, "alone").folder)
    build_pages(root)
    await user.open("/studies")
    user.find(marker="delete_study").click()
    await user.should_see("Delete the study “study alone”?")
    user.find(marker="delete_confirm").click()
    await user.should_see("No studies yet")
    assert not alone.exists()


async def test_the_library_deletes_a_model_and_says_its_studies_go_too(user: User, tmp_path):
    root = tmp_path / "runs"
    r = stored()
    used = Path(_study(root, "used", models=(r.reference,)).folder)
    build_pages(root)
    await user.open("/models?view=personal")
    user.find(marker="delete_model").click()
    await user.should_see(f"Delete the model “{r.spec.name}”?")
    await user.should_see("This will also delete the study made with it (1): study used. Do you want to proceed?")
    user.find(marker="delete_confirm").click()
    await user.should_see("No models yet")
    assert not used.exists()
    await user.open("/models/view?" + urlencode({"reference": r.reference}))
    await user.should_see("Model not found")
    await user.open("/new/track1?" + urlencode({"catalog": r.reference}))
    await user.should_see("no such model revision")
    await user.open("/new/track2?" + urlencode({"catalog": r.reference}))
    await user.should_see("2. What will be searched")


async def test_a_running_study_s_window_only_closes(user: User, tmp_path):
    root = tmp_path / "runs"
    parent, _, grandchild = _tree(root)
    _job(grandchild, status="running")
    build_pages(root)
    await user.open("/study?" + urlencode({"path": "parent"}))
    user.find(marker="delete_this_study").click()
    await user.should_see("It cannot be deleted now: run grandchild is running.")
    await user.should_not_see(marker="delete_confirm")
    assert parent.exists()


# --- the auditor's post-review audit (2026-11-18): the deletion blockers ------------------------------------------------

def _batch_of(root: Path, folder: Path) -> None:
    """A finished batch whose one run was ``folder``."""
    item = batch.BatchItem(title="a batch run", command=["track1", "x.yaml"], folder=str(folder.resolve()),
                           status="completed")
    batch._save(batch.Batch(title="the night's runs", folder=str(root / "batches" / "b1"), created=batch._now(),
                            items=[item], status="completed", finished=batch._now()))


def test_a_batch_s_run_is_not_deleted_so_the_batch_keeps_its_spending(tmp_path):
    """PR-02: the batch counts its spending from its run's folder; deleting it would lower the batch's total."""
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    (root / "batches" / "b1").mkdir(parents=True)
    _batch_of(root, child)
    for folder in (child, parent):                      # the run itself, and a study holding it
        plan = deletion.plan_study(root, folder)
        assert plan.blocked and "the night's runs" in plan.blocked[0]
        with pytest.raises(ValueError, match="lower the batch's total"):
            deletion.delete_study(root, folder, plan)
    r = stored()
    used = Path(_study(root, "used", models=(r.reference,)).folder)
    _batch_of(root, used)
    assert deletion.plan_model(root, r.model_id).blocked
    assert child.exists() and used.exists() and Catalog().load(r.reference)


def test_a_publication_cannot_start_while_the_delete_holds_its_studies(tmp_path, monkeypatch):
    """PR-04: the study's publication lock is held from the plan made again to the removal: a writer that tries to
    publish into it meanwhile is refused, and nothing unconfirmed is removed."""
    import threading
    from adroit.core.durable import Busy, publishing
    root = tmp_path / "runs"
    parent, child, grandchild = _tree(root)
    seen = {}
    real = deletion._aside

    def competing(*args, **kwargs):
        def writer():
            try:
                with publishing(child, wait=0):
                    seen["admitted"] = True
            except Busy:
                seen["admitted"] = False
        thread = threading.Thread(target=writer)
        thread.start()
        thread.join()
        return real(*args, **kwargs)
    monkeypatch.setattr(deletion, "_aside", competing)
    deletion.delete_study(root, parent, deletion.plan_study(root, parent))
    assert seen == {"admitted": False} and not parent.exists()


def test_a_study_made_inside_after_the_plan_is_never_removed(tmp_path, monkeypatch):
    """PR-04: a study that appears inside the folder after the plan was made again (before it is moved aside) makes
    the moved tree differ from the plan: everything is moved back, nothing deleted."""
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    real = deletion._aside

    def late_child(root_, record, tops, folders):
        _study(child / "children", "late")
        return real(root_, record, tops, folders)
    monkeypatch.setattr(deletion, "_aside", late_child)
    with pytest.raises(ValueError, match="changed since you confirmed"):
        deletion.delete_study(root, parent, deletion.plan_study(root, parent))
    assert (child / "children" / "late" / "study.json").is_file() and (parent / "study.json").is_file()
    assert not any((root / ".adroit" / "deleting").glob("*/*")) if (root / ".adroit" / "deleting").exists() else True


def test_a_revision_added_after_the_plan_keeps_the_model(tmp_path, monkeypatch):
    """PR-04: the model's revisions are counted again under the library's lock, after the folder is moved aside: one
    more than confirmed puts it back and deletes nothing."""
    root = tmp_path / "runs"
    root.mkdir()
    r = stored()
    plan = deletion.plan_model(root, r.model_id)
    folder = Catalog().root / "models" / r.model_id / "revisions"
    (folder / ("f" * 64 + ".json")).write_text((folder / f"{r.revision_id}.json").read_text())
    real = deletion.plan_model
    monkeypatch.setattr(deletion, "plan_model", lambda *a, **k: real(*a, **k).model_copy(update={"revisions": 1}))
    with pytest.raises(ValueError, match="changed since you confirmed"):
        deletion.delete_model(root, r.model_id, plan)
    assert len(list(folder.glob("*.json"))) == 2


def test_a_delete_refused_at_its_last_check_leaves_no_record_of_a_delete(tmp_path, monkeypatch):
    """A refusal after the plan was made again (the moved tree, or a model's revisions, not the ones confirmed) puts
    everything back and keeps no ``deleted.json``: only a delete that went ahead is recorded."""
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    real = deletion._aside
    monkeypatch.setattr(deletion, "_aside", lambda r, rec, tops, folders: (
        _study(child / "children", "late"), real(r, rec, tops, folders))[1])
    with pytest.raises(deletion.NothingDeleted):
        deletion.delete_study(root, parent, deletion.plan_study(root, parent))
    deleted = root / deletion.DELETED
    assert not deleted.exists() or not any(deleted.iterdir())


def test_while_a_batch_record_cannot_be_read_nothing_is_deleted(tmp_path):
    """PS-04: which runs a damaged batch record holds is not known, so no study is deleted until it is repaired."""
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    (root / "batches" / "b1").mkdir(parents=True)
    _batch_of(root, child)
    (root / "batches" / "b1" / "batch.json").write_text("{")
    plan = deletion.plan_study(root, parent)
    assert plan.blocked and "a batch record cannot be read" in plan.blocked[0]
    with pytest.raises(ValueError, match="cannot be read"):
        deletion.delete_study(root, parent, plan)
    assert child.exists()


def test_a_run_or_publication_begun_inside_before_its_study_record_keeps_the_folder(tmp_path, monkeypatch):
    """PS-05: a run (its job running) or a publication (its lock held) begun inside after the plan, before its study
    record exists, makes the moved tree busy: it is moved back, nothing deleted."""
    import os
    import threading
    from adroit.core.durable import publishing
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    real = deletion._aside
    late = child / "children" / "promotion_new"

    def a_run(r, rec, tops, folders):
        late.mkdir(parents=True)
        engine.save(engine.Job(title="a new promotion", kind="promote", command=["promote"], folder=str(late),
                               status="running", pid=os.getpid()))
        return real(r, rec, tops, folders)
    monkeypatch.setattr(deletion, "_aside", a_run)
    with pytest.raises(deletion.NothingDeleted, match="the run a new promotion"):
        deletion.delete_study(root, parent, deletion.plan_study(root, parent))
    assert (late / "job.json").is_file() and (parent / "study.json").is_file()
    engine.save(engine.load(late).model_copy(update={"status": "completed"}))
    started, release = threading.Event(), threading.Event()

    def writer():
        with publishing(late, wait=0):
            started.set()
            release.wait(10)
    thread = threading.Thread(target=writer)

    def a_publication(r, rec, tops, folders):
        thread.start()
        started.wait(10)
        return real(r, rec, tops, folders)
    monkeypatch.setattr(deletion, "_aside", a_publication)
    try:
        with pytest.raises(deletion.NothingDeleted, match="a publication into"):
            deletion.delete_study(root, parent, deletion.plan_study(root, parent))
    finally:
        release.set()
        thread.join()
    assert late.is_dir() and (parent / "study.json").is_file()


# --- the auditor's post-review recheck 2 (2026-11-18): the move back ---------------------------------------------------

def test_a_path_made_again_during_the_move_keeps_both_and_names_where(tmp_path, monkeypatch):
    """PT-02: a run that makes the old path again in the instant of the move keeps its write there; the study, as it
    was, is kept where it was moved, named in RECOVERY.json; no delete is recorded, and the refusal says where."""
    import json
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    real = deletion._block

    def raced(top):
        (top / "children" / "promotion_new").mkdir(parents=True)          # a run's folder, made in the instant
        (top / "children" / "promotion_new" / "job.json").write_text("{}")
        real(top)
    monkeypatch.setattr(deletion, "_block", raced)
    with pytest.raises(deletion.DeleteStranded, match="kept, as it was, at") as refused:
        deletion.delete_study(root, parent, deletion.plan_study(root, parent))
    [recovery] = list((root / ".adroit" / "deleting").glob("*/RECOVERY.json"))
    stranded = json.loads(recovery.read_text())["stranded"]
    kept = Path(stranded[0]["kept_at"])
    assert stranded[0]["original"] == str(parent) and str(kept) in str(refused.value)
    assert (kept / "study.json").is_file() and (kept / "children" / "child" / "study.json").is_file()
    assert (parent / "children" / "promotion_new" / "job.json").is_file()          # the run's write, kept
    assert not (root / deletion.DELETED).exists() or not any((root / deletion.DELETED).iterdir())


def test_the_placeholder_stops_a_run_making_the_folder_again_and_the_folder_comes_back(tmp_path, monkeypatch):
    """PT-02: while the folder is aside its old path holds the delete's placeholder: a run cannot make the folder
    again (its write fails, loudly); on a refusal the placeholder goes and the folder is moved back whole."""
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    seen = {}

    def busy(moved, folders):
        top = moved[0][0]
        try:
            (top / "children" / "late").mkdir(parents=True, exist_ok=True)
            seen["made"] = True
        except OSError as error:
            seen["made"] = type(error).__name__
        return "a run"
    monkeypatch.setattr(deletion, "_busy", busy)
    with pytest.raises(deletion.NothingDeleted, match="a run began inside it"):
        deletion.delete_study(root, parent, deletion.plan_study(root, parent))
    assert seen["made"] in ("FileExistsError", "NotADirectoryError")
    assert parent.is_dir() and (parent / "study.json").is_file() and (child / "study.json").is_file()


def test_a_finished_delete_leaves_no_placeholder(tmp_path):
    root = tmp_path / "runs"
    parent, _, _ = _tree(root)
    deletion.delete_study(root, parent, deletion.plan_study(root, parent))
    assert not parent.exists() and not parent.is_symlink()


# --- a run that ended without a study (the owner, 2026-11-19: "no option to start over or abandon") -----------------

def _ended(root: Path, name: str = "failed", status: str = "failed") -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    _job(folder, status=status, command=("signal", "x.yaml"))
    _money(folder)
    (folder / "log.txt").write_text("anthropic.APITimeoutError: Request timed out\n")
    return folder


def test_a_run_without_a_study_is_deleted_with_its_folder_and_its_money_records_kept(tmp_path):
    root = tmp_path / "runs"
    folder = _ended(root)
    plan = deletion.plan_run(root, folder)
    assert plan.kind == "run" and plan.runs == [str(folder.resolve())] and plan.studies == [] and not plan.running
    deletion.delete_run(root, folder, plan)
    assert not folder.exists() and not folder.is_symlink() and engine.listing(root) == ([], [])
    record, written = _kept(root)
    assert written["kind"] == "run" and written["runs"] == ["failed"] and written["studies"] == []
    for name in ("paid.jsonl", "paid.jsonl.held", "paid_requests.json", "job.deleted.json"):
        assert (record / "kept" / "failed" / name).is_file(), name
    deleting = root / ".adroit" / "deleting"
    assert not deleting.exists() or not any(deleting.iterdir())


def test_a_running_run_or_one_whose_calculation_is_left_running_is_not_deleted(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    running = _ended(root, "running", status="running")
    plan = deletion.plan_run(root, running)
    assert plan.running == ["run running is running"]
    with pytest.raises(ValueError, match="Wait for it to finish"):
        deletion.delete_run(root, running, plan)
    left = _ended(root, "left")
    engine.save(engine.load(left).model_copy(update={"calculation": 4242}))
    monkeypatch.setattr(engine, "calculation_alive", lambda job: [4242] if job.calculation == 4242 else [])
    plan = deletion.plan_run(root, left)
    assert plan.running and "calculation still runs" in plan.running[0]
    with pytest.raises(ValueError, match="not deleted"):
        deletion.delete_run(root, left, plan)
    assert running.exists() and left.exists() and not (root / deletion.DELETED).exists()


def test_a_run_whose_folder_holds_a_study_is_the_study_s_to_delete(tmp_path):
    root = tmp_path / "runs"
    parent, _, _ = _tree(root)
    with pytest.raises(ValueError, match="delete the study instead"):
        deletion.plan_run(root, parent)
    folder = _ended(root)
    plan = deletion.plan_run(root, folder)
    studies.record(folder, "signal", "published after the plan")        # it became a study after the window opened
    with pytest.raises(ValueError, match="delete the study instead"):
        deletion.delete_run(root, folder, plan)
    assert (folder / "study.json").is_file() and not (root / deletion.DELETED).exists()


def test_only_a_run_in_the_runs_folder_can_be_deleted(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    outside = _ended(tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="is not a run in"):
        deletion.plan_run(root, outside)
    with pytest.raises(ValueError, match="is not a run in"):
        deletion.plan_run(root, root)
    (root / "link").symlink_to(outside)
    with pytest.raises(ValueError, match="is a link"):
        deletion.plan_run(root, root / "link")
    assert outside.exists()


def test_a_batch_s_run_without_a_study_is_not_deleted(tmp_path):
    root = tmp_path / "runs"
    folder = _ended(root)
    (root / "batches" / "b1").mkdir(parents=True)
    _batch_of(root, folder)
    plan = deletion.plan_run(root, folder)
    assert plan.blocked and "the night's runs" in plan.blocked[0]
    with pytest.raises(ValueError, match="lower the batch's total"):
        deletion.delete_run(root, folder, plan)
    assert folder.exists()


def test_a_run_begun_again_after_the_plan_keeps_its_folder(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    folder = _ended(root)
    plan = deletion.plan_run(root, folder)
    real = deletion._aside

    def resumed_meanwhile(root_, record, tops, folders):           # its record says it runs again, being launched
        engine.save(engine.load(folder).model_copy(update={"status": "running", "pid": 0}))
        return real(root_, record, tops, folders)
    monkeypatch.setattr(deletion, "_aside", resumed_meanwhile)
    with pytest.raises(deletion.NothingDeleted):
        deletion.delete_run(root, folder, plan)
    assert (folder / "job.json").is_file() and (folder / "paid.jsonl").is_file()
    assert not (root / deletion.DELETED).exists() or not any((root / deletion.DELETED).iterdir())


async def test_activity_offers_a_failed_run_its_form_and_deletes_it_after_its_window(user: User, tmp_path):
    root = tmp_path / "runs"
    folder = _ended(root)
    build_pages(root)
    await user.open("/activity")
    await user.should_see("open the form again")
    await user.should_see(marker="not_resumable")
    user.find(marker="delete_run").click()
    await user.should_see("Delete the run “run failed”?")
    await user.should_see(deletion.KEPT_NOTE)
    user.find(marker="delete_cancel").click()
    assert folder.exists()
    user.find(marker="delete_run").click()
    user.find(marker="delete_confirm").click()
    await user.should_see("No runs yet")
    assert not folder.exists()


async def test_the_studies_page_offers_a_run_without_a_study_its_form_and_its_delete(user: User, tmp_path):
    root = tmp_path / "runs"
    folder = _ended(root)
    build_pages(root)
    await user.open("/studies")
    await user.should_see("Runs that ended without a study")
    assert [e.props.get("href") for e in user.find("start over").elements] == ["/new/track2"]
    user.find(marker="delete_run").click()
    await user.should_see("Delete the run “run failed”?")
    user.find(marker="delete_confirm").click()
    await user.should_not_see("Runs that ended without a study")
    assert not folder.exists()


async def test_a_completed_run_and_a_study_get_no_run_delete(user: User, tmp_path):
    root = tmp_path / "runs"
    done = root / "done"
    done.mkdir(parents=True)
    _job(done)
    parent, _, _ = _tree(root)
    _job(parent, status="failed")                    # a failed rerun in a study's folder: the study's delete applies
    build_pages(root)
    await user.open("/activity")
    await user.should_not_see(marker="delete_run")


# --- MF-01 (the auditor's audit of 2026-11-19): a run inside the folder whose calculation outlived its run ---------------

def _orphan(root: Path) -> tuple[Path, Path, subprocess.Popen]:
    """A failed parent run, and inside its folder a failed child run whose calculation still runs: a real process in a
    group of its own, recorded as the child's calculation with its start, as the runner records one."""
    parent = _ended(root, "parent")
    child = parent / "child"
    child.mkdir()
    _job(child, status="failed", command=("signal", "x.yaml"))
    (child / "output.json").write_text("{}")
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
    for _ in range(50):                              # its start as ps reads it, to the second
        started = engine.process_started(process.pid)
        if started:
            break
        time.sleep(0.1)
    engine.save(engine.load(child).model_copy(update={"calculation": process.pid, "calculation_started": started}))
    return parent, child, process


def _stop(process: subprocess.Popen) -> None:
    process.kill()
    process.wait(timeout=10)


def test_a_parent_whose_child_s_calculation_still_runs_is_not_deleted(tmp_path):
    root = tmp_path / "runs"
    parent, child, process = _orphan(root)
    try:
        plan = deletion.plan_run(root, parent)
        assert plan.running and "run child: its calculation still runs" in plan.running[0]
        stale = plan.model_copy(update={"running": []})          # a window opened before the child was orphaned
        with pytest.raises(ValueError, match="calculation still runs"):
            deletion.delete_run(root, parent, stale)
        assert (child / "output.json").is_file() and (parent / "paid.jsonl").is_file()
        assert not (root / deletion.DELETED).exists() or not any((root / deletion.DELETED).iterdir())
    finally:
        _stop(process)
    plan = deletion.plan_run(root, parent)                       # once it has ended, the delete goes ahead
    assert not plan.running
    deletion.delete_run(root, parent, plan)
    assert not parent.exists()


def test_a_calculation_left_running_after_the_plan_keeps_the_folder(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    parent = _ended(root, "parent")
    child = parent / "child"
    child.mkdir()
    _job(child, status="failed", command=("signal", "x.yaml"))
    plan = deletion.plan_run(root, parent)
    assert not plan.running
    real, made = deletion._aside, []

    def orphaned_meanwhile(root_, record, tops, folders):    # the child's calculation outlives its run, now
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
        made.append(process)
        started = 0.0
        for _ in range(50):
            started = engine.process_started(process.pid)
            if started:
                break
            time.sleep(0.1)
        engine.save(engine.load(child).model_copy(update={"calculation": process.pid,
                                                           "calculation_started": started}))
        return real(root_, record, tops, folders)
    monkeypatch.setattr(deletion, "_aside", orphaned_meanwhile)
    try:
        with pytest.raises(deletion.NothingDeleted, match="not deleted: a calculation that still runs, of the run "
                                                          "run child, began inside it meanwhile; look again"):
            deletion.delete_run(root, parent, plan)
        assert (child / "job.json").is_file() and (parent / "paid.jsonl").is_file()
    finally:
        for process in made:
            _stop(process)


def test_a_parent_is_kept_when_polling_finds_its_child_s_runner_gone_and_its_calculation_alive(tmp_path, monkeypatch):
    """The auditor's MF-01 route (``live_child_recovery.py``): the child's runner really exits, ordinary polling marks the
    child failed with its calculation still running, then its parent is deleted from a fresh plan."""
    monkeypatch.setattr(engine, "poll", POLL)                   # processes looked for, as in the workbench
    root = tmp_path / "runs"
    parent = _ended(root, "parent")
    child = parent / "child"
    child.mkdir()
    calculation = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
    runner = subprocess.Popen([sys.executable, "-c", "pass"])
    runner.wait()
    try:
        started = 0.0
        for _ in range(50):
            started = engine.process_started(calculation.pid)
            if started:
                break
            time.sleep(0.1)
        engine.save(engine.Job(title="child", kind="track1", folder=str(child), command=["track1", "x.yaml"],
                               pid=runner.pid, status="running", acknowledged=True, calculation=calculation.pid,
                               calculation_started=started))
        (child / "output.json").write_text("{}")
        closed = engine.poll(child)
        assert closed.status == "failed" and "calculation still runs" in closed.note
        plan = deletion.plan_run(root, parent)
        assert plan.running and "calculation still runs" in plan.running[0]
        with pytest.raises(ValueError, match="calculation still runs"):
            deletion.delete_run(root, parent, plan)
        assert (child / "output.json").is_file() and calculation.poll() is None
    finally:
        _stop(calculation)


def test_a_study_whose_folder_holds_a_run_with_a_live_calculation_is_not_deleted(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    parent, child, _ = _tree(root)
    engine.save(engine.load(child).model_copy(update={"status": "failed", "calculation": 4243}))
    monkeypatch.setattr(engine, "calculation_alive", lambda job: [4243] if job.calculation == 4243 else [])
    plan = deletion.plan_study(root, parent)
    assert plan.running and "its calculation still runs (processes 4243)" in plan.running[0]
    with pytest.raises(ValueError, match="not deleted"):
        deletion.delete_study(root, parent, plan)
    assert parent.exists() and child.exists()


def test_a_calculation_group_not_proven_its_own_is_never_taken_as_ended(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    folder = _ended(root)
    engine.save(engine.load(folder).model_copy(update={"calculation": 4244}))
    monkeypatch.setattr(engine, "calculation_alive", lambda job: [])
    monkeypatch.setattr(engine, "calculation_unproven", lambda job: [4244, 4245] if job.calculation == 4244 else [])
    plan = deletion.plan_run(root, folder)
    assert plan.running and "not proven its own" in plan.running[0]


async def test_activity_refuses_to_delete_a_parent_while_its_child_s_calculation_runs(user: User, tmp_path,
                                                                                     monkeypatch):
    root = tmp_path / "runs"
    parent = _ended(root, "parent")
    child = parent / "child"
    child.mkdir()
    _job(child, status="failed", command=("signal", "x.yaml"))
    engine.save(engine.load(child).model_copy(update={"calculation": 4246}))
    monkeypatch.setattr(engine, "calculation_alive", lambda job: [4246] if job.calculation == 4246 else [])
    build_pages(root)
    await user.open("/activity")
    assert len(user.find(marker="delete_run").elements) == 2      # the parent's card and the child's
    user.find(marker="delete_run").click()                         # each window says why it cannot delete now
    await user.should_see(marker="delete_refused")
    await user.should_see("its calculation still runs (processes 4246)")
    await user.should_not_see(marker="delete_confirm")
    assert parent.exists() and child.exists()

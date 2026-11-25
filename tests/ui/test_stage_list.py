"""The owner (2026-11-23): a long Constrain a model run's live page lists every stage of the calculation, in order,
and ticks each off as it finishes, the current one with its count ("check the thermal points against every
constraint · 44 of 48"). The plan is declared from the request; ``Checkpoint.update`` keeps each stage's state."""
import json

from nicegui.testing import User

from adroit.core.checkpoint import Checkpoint, Progress
from adroit.orchestrator import track1
from adroit.ui.app import build_pages
from tests.ui.test_consistency_records import _job


def test_each_stage_is_ticked_when_the_next_begins_and_a_failure_is_marked(tmp_path) -> None:
    point = Checkpoint(tmp_path, {"a": 1}, {"d": 1})
    point.declare(["scan", "refinement", "cuts-points", "plots"])
    point.update("scan", 3, 48, "completed parameter points")
    point.update("scan", 48, 48, "completed parameter points")
    point.update("verdict", detail="refining")                      # a transition, not a planned stage
    point.update("refinement", 5, 5, "thermal brackets refined")
    point.update("cuts-points", 44, 48, "certified roots checked")
    stages = point.progress.stages
    assert (stages["scan"].state, stages["scan"].completed, stages["scan"].total) == ("done", 48, 48)
    assert stages["refinement"].state == "done" and stages["cuts-points"].state == "running"
    assert stages["cuts-points"].completed == 44 and "plots" not in stages
    point.update("cuts-points", 44, 48, "boom", status="failed")
    assert point.progress.stages["cuts-points"].state == "failed"
    saved = Progress.model_validate_json((tmp_path / "progress.json").read_text())
    assert saved.plan == ["scan", "refinement", "cuts-points", "plots"] and saved.stages["scan"].state == "done"


def test_a_completed_run_ticks_its_plan_and_an_old_record_still_reads(tmp_path) -> None:
    point = Checkpoint(tmp_path, {"a": 1}, {"d": 1})
    point.declare(["scan", "plots"])
    point.update("scan", 2, 4)
    point.update("completed", status="completed", detail="scientific result saved")
    assert {name: mark.state for name, mark in point.progress.stages.items()} == {"scan": "done", "plots": "done"}
    old = Progress.model_validate({"phase": "scan", "completed": 3, "total": 9})     # written before the plan
    assert old.plan == [] and old.stages == {}


def test_the_plan_follows_the_request() -> None:
    from types import SimpleNamespace
    base = SimpleNamespace(coverage=None, likelihood=None, literature=False)
    assert track1.stage_plan(base) == ["scan", "refinement", "cuts-points", "plots"]
    full = SimpleNamespace(coverage=object(), likelihood=object(), literature=True)
    assert track1.stage_plan(full) == ["scan", "coverage", "refinement", "cuts-points", "likelihood-points", "plots",
                                       "literature"]
    assert set(track1.stage_plan(full)) <= set(track1.STAGE_NAMES)


async def test_the_live_page_lists_the_stages_and_ticks_them(user: User, tmp_path) -> None:
    root = build_pages(tmp_path / "runs")
    job = _job(root / "running", "a long scan")
    job.status = "running"
    from adroit.ui import engine
    engine.save(job)
    progress = Progress(phase="cuts-points", completed=44, total=48, detail="certified roots checked",
                        plan=["scan", "refinement", "cuts-points", "plots"],
                        stages={"scan": {"state": "done", "completed": 48, "total": 48},
                                "refinement": {"state": "done", "completed": 5, "total": 5},
                                "cuts-points": {"state": "running", "completed": 44, "total": 48}})
    (root / "running" / "progress.json").write_text(json.dumps(progress.model_dump(mode="json")))
    await user.open("/live?path=running")
    await user.should_see(marker="stage_list")
    await user.should_see("✓ scan the parameter plane (points) · 48 of 48")
    await user.should_see("▸ check the thermal points against every constraint · 44 of 48")
    await user.should_see("○ draw the plots")

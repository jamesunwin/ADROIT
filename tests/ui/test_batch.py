"""The workbench's batch queue and bundle viewer (the batch plan's §7)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("nicegui")

from nicegui import ui  # noqa: E402
from nicegui.testing import User  # noqa: E402

from adroit.ui import batch, engine  # noqa: E402
from tests.ui.test_workbench import workspace  # noqa: E402,F401  (the fixture)


def _prepared(root: Path, name: str) -> Path:
    folder = root / f"prepared_{name}"
    folder.mkdir(parents=True)
    return folder


def test_the_draft_keeps_requests_and_a_paid_one_needs_its_budget(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "a.yaml"], _prepared(root, "a"), "first")
    with pytest.raises(engine.BudgetNotConfirmed):
        batch.add_to_draft(root, ["idea", "x", "--budget", "0.50"], _prepared(root, "b"), "paid", budget=0.1)
    batch.add_to_draft(root, ["idea", "x", "--budget", "0.50"], _prepared(root, "c"), "paid", budget=0.5)
    assert [x.title for x in batch.draft(root)] == ["first", "paid"]
    batch.remove_from_draft(root, batch.draft(root)[0])
    assert [x.title for x in batch.draft(root)] == ["paid"]


def test_starting_a_batch_needs_its_total_confirmed_and_empties_the_draft(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    with pytest.raises(ValueError, match="empty"):
        batch.start(root, "nothing")
    batch.add_to_draft(root, ["idea", "x", "--budget", "0.50"], _prepared(root, "a"), "paid", budget=0.5)
    with pytest.raises(engine.BudgetNotConfirmed):
        batch.start(root, "two", confirmed_budget=0.2)
    started = []
    b = batch.start(root, "two", confirmed_budget=0.5, popen=lambda cmd, **_: started.append(cmd) or
                    SimpleNamespace(pid=4242))
    assert b.pid == 4242 and b.budget_usd == pytest.approx(0.5) and batch.draft(root) == []
    assert started[0][-5:-3] == ["-m", "adroit.ui.batch"] and Path(started[0][-3]) == Path(b.folder)
    assert started[0][-2] == b.approval_sha256 == batch._digest(b.approval)          # handed over, not read back
    assert started[0][-1] == "1" == str(b.generation)                               # this start's (RX22-07)
    assert [x.title for x in batch.batches(root)[0].items] == ["paid"]


def _batch(root: Path, titles: list[str], commands: list[list[str]] | None = None, confirmed: float = 0.0):
    for t, command in zip(titles, commands or [["track1", f"{t}.yaml"] for t in titles]):
        batch.add_to_draft(root, command, _prepared(root, t), t, budget=engine.paid(command))
    b = batch.start(root, "b", confirmed, popen=lambda *a, **k: SimpleNamespace(pid=1))
    return Path(b.folder), b.approval_sha256


def test_the_runner_takes_one_request_after_another_and_a_failure_does_not_stop_it(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["a", "b", "c"])
    order, polls = [], {}

    def launch(command, item_folder, title, confirmed_budget=0.0, owner=""):
        order.append(title)
        if title == "b":
            raise engine.JobExists("already holds a job")

    def poll(item_folder):
        polls[item_folder] = polls.get(item_folder, 0) + 1
        return SimpleNamespace(status="running" if polls[item_folder] < 2 else "completed")
    done = _run(folder, approval, launch=launch, poll=poll, stop=lambda f: None, sleep=lambda s: None)
    assert order == ["a", "b", "c"] and done.status == "completed"
    assert [x.status for x in done.items] == ["completed", "failed", "completed"]
    assert "already held a job" in done.items[1].error


def test_cancelling_stops_the_running_request_and_leaves_the_rest_unstarted(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["a", "b"])
    stopped = []

    def poll(item_folder):
        batch.cancel(folder)                                   # cancelled while the first request runs
        return SimpleNamespace(status="cancelled" if stopped else "running")
    done = _run(folder, approval, launch=lambda *a, **k: None, poll=poll, stop=stopped.append,
                     sleep=lambda s: None)
    assert done.status == "cancelled" and stopped == [Path(done.items[0].folder)]
    assert [x.status for x in done.items] == ["cancelled", "cancelled"]


def _run(folder, approval, **kwargs):
    """The runner of the batch's current start, as its launcher gives it its generation (RX22-07, RY23-04)."""
    return batch.run(folder, approval, generation=batch.load(Path(folder)).generation, **kwargs)


def _completed(item_folder):
    return SimpleNamespace(status="completed")


def test_a_request_edited_after_confirmation_is_not_launched(tmp_path: Path) -> None:
    """The batch audit's B20-01: the command and the item's budget raised to $5 in batch.json after a $0.50
    confirmation had launched with $5. The approval's digest comes from the confirming process."""
    import json
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["paid"], [["idea", "--text", "x", "--budget", "0.5"]], confirmed=0.5)
    data = json.loads((folder / batch.BATCH).read_text())
    data["items"][0]["command"][-1], data["items"][0]["budget_usd"] = "5", 5.0
    (folder / batch.BATCH).write_text(json.dumps(data))
    launched = []
    done = _run(folder, approval, launch=lambda c, f, t, confirmed_budget: launched.append(confirmed_budget),
                     poll=_completed, sleep=lambda s: None)
    assert launched == [] and done.items[0].status == "failed" and "changed after the batch" in done.items[0].error
    data["approval"]["items"][0]["budget_usd"] = 5.0                 # editing the approval too: not the one confirmed
    (folder / batch.BATCH).write_text(json.dumps(data))
    assert _run(folder, approval, launch=lambda *a, **k: launched.append(1), poll=_completed).status == "refused"
    assert launched == []


def test_a_budget_is_read_as_the_command_line_reads_it(tmp_path: Path) -> None:
    """B20-01: `--budget .5 --budget 5` had been confirmed as $0.50 while the command line takes the last, $5."""
    for command in (["idea", "--text", "x", "--budget", ".5", "--budget", "5"],
                    ["idea", "--text", "x", "--budget=nan"], ["idea", "--text", "x", "--budget", "-1"],
                    ["idea", "--text", "x", "--budget"]):
        with pytest.raises(ValueError):
            engine.paid(command)
    with pytest.raises(ValueError, match="more than once"):
        batch.add_to_draft(tmp_path / "runs", ["idea", "--budget", ".5", "--budget", "5"], _prepared(tmp_path, "x"),
                           "x", budget=5.0)
    with pytest.raises(ValueError, match="finite"):
        batch.start(tmp_path / "runs", "x", confirmed_budget=float("inf"))


def test_a_draft_changed_after_a_request_was_added_needs_it_added_again(tmp_path: Path) -> None:
    import json
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["idea", "--text", "x", "--budget", ".5"], _prepared(root, "a"), "a", budget=.5)
    path = root / batch.DRAFT
    data = json.loads(path.read_text())
    data[0]["budget_usd"] = 0.0
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="changed after it was added"):
        batch.start(root, "zero", confirmed_budget=0.0, popen=lambda *a, **k: SimpleNamespace(pid=1))


def test_a_restarted_runner_follows_the_running_request_and_a_second_runner_stops(tmp_path: Path) -> None:
    """B20-02: a restarted runner had skipped an item marked running and called the batch completed; a second
    runner had raced the first. The runner lock keeps one; a running item's own job is followed to its end."""
    import fcntl
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["a", "b"])
    first = Path(batch.load(folder).items[0].folder)
    owner = f"{folder.resolve()}#0#{approval}"                      # what the predecessor recorded, then launched
    assert batch._reserve(folder, owner, first)
    engine.launch(["track1", "a.yaml"], first, "a", popen=lambda *a, **k: SimpleNamespace(pid=1), owner=owner)
    batch._update(folder, 0, status="running")
    polls, launched = [], []

    def poll(item_folder):
        polls.append(Path(item_folder))
        return SimpleNamespace(status="completed" if len(polls) > 2 else "running")
    done = _run(folder, approval, launch=lambda c, f, t, confirmed_budget, owner: launched.append(t), poll=poll,
                     sleep=lambda s: None)
    assert polls[:3] == [first] * 3 and launched == ["b"] and done.status == "completed"
    assert "own job was followed" in done.items[0].error and [i.status for i in done.items] == ["completed", "completed"]
    with (folder / batch.RUNNER_LOCK).open("a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        with pytest.raises(batch.RunnerBusy):
            _run(folder, approval, launch=lambda *a, **k: None, poll=_completed)


def test_an_already_launched_approved_request_is_followed_not_failed(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["a"])
    item = Path(batch.load(folder).items[0].folder)
    owner = f"{folder.resolve()}#0#{approval}"                      # its predecessor's launch, before it recorded so
    engine.launch(["track1", "a.yaml"], item, "a", popen=lambda *a, **k: SimpleNamespace(pid=1), owner=owner)
    done = _run(folder, approval, launch=engine.launch, poll=_completed, sleep=lambda s: None)
    assert done.items[0].status == "completed" and done.status == "completed"
    root2 = tmp_path / "other"
    folder2, approval2 = _batch(root2, ["a"])
    item2 = Path(batch.load(folder2).items[0].folder)
    engine.launch(["track1", "someone-else.yaml"], item2, "x", popen=lambda *a, **k: SimpleNamespace(pid=1))
    done2 = _run(folder2, approval2, launch=engine.launch, poll=_completed, sleep=lambda s: None)
    assert done2.items[0].status == "failed" and "holds no job this batch launched" in done2.items[0].error


def test_an_interrupted_batch_resumes_only_with_a_new_confirmation(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["paid"], [["idea", "--text", "x", "--budget", "0.5"]], confirmed=0.5)
    batch._update(folder, status="running", pid=2 ** 22 + 12345)       # a runner that no longer exists
    (stale,) = batch.batches(root)
    assert stale.status == "interrupted"
    with pytest.raises(engine.BudgetNotConfirmed):
        batch.resume(folder, confirmed_budget=0.1, popen=lambda *a, **k: SimpleNamespace(pid=3))
    started = []
    resumed = batch.resume(folder, 0.5, popen=lambda cmd, **k: started.append(cmd) or SimpleNamespace(pid=3))
    assert resumed.status == "running" and started[0][-2:] == [resumed.approval_sha256, str(resumed.generation)]


def test_a_confirmation_launches_a_request_once(tmp_path: Path) -> None:
    """The recheck's RB20-01 (2026-10-20), its control: after an approved $0.50 request completed, its item put back
    in the queue and pointed at another folder had been launched again under the same confirmation ($1.00 against
    $0.50). Now the request's folder is in the approval, the dispatch is in the batch's ledger, a completed batch is
    not run again, and a request put back in its own folder is followed through its own job, not launched."""
    root = tmp_path / "runs"
    command = ["idea", "--text", "x", "--budget", "0.5"]
    folder, approval = _batch(root, ["paid"], [command], confirmed=0.5)
    spent = []

    def launch(command, item_folder, title, confirmed_budget=0.0, owner=""):
        spent.append(confirmed_budget)
        engine.launch(command, item_folder, title, confirmed_budget, popen=lambda *a, **k: SimpleNamespace(pid=1),
                      owner=owner)
    done = _run(folder, approval, launch=launch, poll=_completed, sleep=lambda s: None)
    assert done.status == "completed" and spent == [0.5]
    assert _run(folder, approval, launch=launch, poll=_completed, sleep=lambda s: None) == done   # not again
    elsewhere = _prepared(root, "elsewhere")

    def edited(**fields):                              # the batch's file edited by hand, as the audit's control did
        b = batch.load(folder)
        batch._save(b.model_copy(update={"status": "running", "items": [b.items[0].model_copy(update=fields)]}))
    edited(status="queued", folder=str(elsewhere))
    moved = _run(folder, approval, launch=launch, poll=_completed, sleep=lambda s: None)
    assert spent == [0.5] and moved.items[0].status == "failed" and "folder" in moved.items[0].error
    edited(status="queued", folder=done.items[0].folder)
    back = _run(folder, approval, launch=launch, poll=_completed, sleep=lambda s: None)
    assert spent == [0.5] and back.items[0].status == "completed" and "own job was followed" in back.items[0].error


def test_two_batches_of_the_same_request_launch_it_once(tmp_path: Path) -> None:
    """Two batches confirmed for the same request in one folder: their approvals differ (each names its own batch), the
    folder takes one job, and the second batch finds it another's: failed, not followed or launched again."""
    root = tmp_path / "runs"
    prepared = _prepared(root, "shared")
    spent, approvals = [], []
    for title in ("one", "two"):
        batch.add_to_draft(root, ["track1", "a.yaml"], prepared, title)
        b = batch.start(root, title, popen=lambda *a, **k: SimpleNamespace(pid=1))
        approvals.append((Path(b.folder), b.approval_sha256))
    assert approvals[0][1] != approvals[1][1]

    def launch(command, item_folder, title, confirmed_budget=0.0, owner=""):
        spent.append(title)
        engine.launch(command, item_folder, title, popen=lambda *a, **k: SimpleNamespace(pid=1), owner=owner)
    first, second = (_run(f, a, launch=launch, poll=_completed, sleep=lambda s: None) for f, a in approvals)
    assert spent == ["one", "two"] and first.items[0].status == "completed"
    assert second.items[0].status == "failed" and "holds no job this batch launched" in second.items[0].error


def test_a_launch_that_dies_before_its_run_starts_is_closed_not_followed_forever(tmp_path: Path) -> None:
    """The recheck's RB20-02 (2026-10-20), its control: a launch stopped (SystemExit) between writing its job and
    starting its run had left the job running with PID 0, so a recovered batch waited forever. The launch now closes its
    job on the way out; a job whose launcher died without a word is closed by poll after the grace period ("launch not
    confirmed"), and its run, starting late, does nothing. The batch reaches its next request."""
    from datetime import datetime, timedelta
    from adroit.ui import runner
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["a", "b"])
    items = [Path(i.folder) for i in batch.load(folder).items]

    def dies(*args, **kwargs):
        raise SystemExit("killed at the spawn")
    with pytest.raises(SystemExit):
        engine.launch(["track1", "a.yaml"], items[0], "a", popen=dies, owner=f"{folder.resolve()}#0#{approval}")
    assert engine.load(items[0]).status == "failed" and "before its run started" in engine.load(items[0]).note
    lost = items[0].parent / "lost"
    engine.launch(["track1", "lost.yaml"], lost, "lost", popen=lambda *a, **k: SimpleNamespace(pid=0))
    engine.update(lost, pid=0, launcher_pid=2 ** 22 + 12345,
                  started=(datetime.now() - timedelta(seconds=engine.LAUNCH_GRACE_SECONDS + 5)).isoformat())
    closed = engine.poll(lost)
    assert closed.status == "failed" and closed.note.startswith("launch not confirmed")
    assert runner.run(lost).status == "failed" and not (lost / engine.LOG).exists()   # the late run does nothing
    starting = items[0].parent / "starting"
    engine.launch(["track1", "s.yaml"], starting, "s", popen=lambda *a, **k: SimpleNamespace(pid=0))
    assert engine.poll(starting).status == "running"                  # its launcher (this process) lives: starting
    batch._reserve(folder, f"{folder.resolve()}#0#{approval}", items[0])
    batch._update(folder, 0, status="running")
    done = _run(folder, approval, launch=lambda c, f, t, confirmed_budget, owner: engine.launch(
        c, f, t, popen=lambda *a, **k: SimpleNamespace(pid=1), owner=owner),
        poll=lambda f: engine.poll(f) if Path(f) == items[0] else _completed(f), sleep=lambda s: None)
    assert [i.status for i in done.items] == ["failed", "completed"] and done.status == "completed"


def test_the_run_is_the_command_its_launch_confirmed(tmp_path: Path, monkeypatch) -> None:
    """The auditor's RC20-01 (2026-10-20), its first control: the job's command edited between launch and start ($0.50 to
    $5) had run. The launcher hands the runner the confirmed command's sha256; the runner refuses another command and
    starts nothing, and runs the confirmed one."""
    from adroit.ui import runner
    ran = []
    monkeypatch.setattr(runner.subprocess, "Popen", lambda argv, **k: ran.append(argv) or SimpleNamespace(pid=0, wait=lambda: 0,
                                                                                                    terminate=lambda: 0))
    started = []
    folder = tmp_path / "run"
    job = engine.launch(["idea", "--text", "x", "--budget", "0.5"], folder, "paid", confirmed_budget=0.5,
                        popen=lambda argv, **k: started.append(argv) or SimpleNamespace(pid=0))
    confirmed = started[0][-1]
    assert confirmed == engine.command_sha256(job.command) and started[0][-2] == str(folder.resolve())
    engine.update(folder, command=["idea", "--text", "x", "--budget", "5.0"])
    refused = runner.run(folder, confirmed)
    assert refused.status == "failed" and refused.note.startswith("refused") and ran == []
    other = tmp_path / "other"
    engine.launch(["track1", "a.yaml"], other, "free", popen=lambda argv, **k: started.append(argv) or
                  SimpleNamespace(pid=0))
    assert runner.run(other, "").status == "failed" and ran == []               # no confirmation given: not run
    fine = tmp_path / "fine"
    engine.launch(["track1", "b.yaml"], fine, "free", popen=lambda argv, **k: started.append(argv) or
                  SimpleNamespace(pid=0))
    assert runner.run(fine, started[-1][-1]).status == "completed" and ran[0][-1] == "b.yaml"


def test_an_erased_dispatch_history_does_not_dispatch_again(tmp_path: Path) -> None:
    """The auditor's RC20-01, its second control: after an approved $0.50 request completed, ``dispatched.json`` emptied,
    the finished job removed and the batch and item put back to running and queued had dispatched it again. The runs
    folder's own ledger, its path frozen in the approval, still holds the dispatch: not launched again."""
    root = tmp_path / "runs"
    command = ["idea", "--text", "x", "--budget", "0.5"]
    folder, approval = _batch(root, ["paid"], [command], confirmed=0.5)
    spent = []

    def launch(command, item_folder, title, confirmed_budget=0.0, owner=""):
        spent.append(confirmed_budget)
        engine.launch(command, item_folder, title, confirmed_budget, popen=lambda *a, **k: SimpleNamespace(pid=1),
                      owner=owner)
    done = _run(folder, approval, launch=launch, poll=_completed, sleep=lambda s: None)
    assert done.status == "completed" and spent == [0.5] and (root / batch.DISPATCHES).exists()
    (folder / batch.LEDGER).write_text("{}")
    (Path(done.items[0].folder) / engine.JOB).unlink()
    b = batch.load(folder)
    batch._save(b.model_copy(update={"status": "running", "finished": "",
                                     "items": [b.items[0].model_copy(update={"status": "queued", "error": ""})]}))
    again = _run(folder, approval, launch=launch, poll=_completed, sleep=lambda s: None)
    assert spent == [0.5] and again.items[0].status == "failed" and "confirm a new batch" in again.items[0].error


def test_a_resume_that_fails_to_start_closes_its_job(tmp_path: Path) -> None:
    """The auditor's RC20-02 (2026-10-20), its control: a resume whose process creation failed had left the job running with
    PID 0, and every later resume was refused. It is closed with the reason and can be resumed again."""
    folder = tmp_path / "t1"
    engine.launch(["track1", "a.yaml"], folder, "t1", popen=lambda *a, **k: SimpleNamespace(pid=0))
    engine.update(folder, status="failed", finished=engine._now())
    (folder / ".track1-checkpoint").mkdir()
    (folder / ".track1-checkpoint" / "manifest.json").write_text("{}")

    def fails(*args, **kwargs):
        raise OSError("synthetic process-creation failure")
    with pytest.raises(OSError):
        engine.resume(folder, popen=fails)
    job = engine.load(folder)
    assert job.status == "failed" and "the resume failed before its run started" in job.note
    again = engine.resume(folder, popen=lambda *a, **k: SimpleNamespace(pid=7))
    assert again.status == "running" and again.pid == 7 and "--resume" in again.command


def test_a_run_that_never_starts_is_closed_after_its_bound_whoever_holds_the_launchers_pid(tmp_path: Path) -> None:
    """The auditor's RC20-02: a two-day-old PID-0 job whose launcher PID a live process held (here this one) stayed running.
    Starting is acknowledged within the bound or the job is closed; a job inside the bound is still starting."""
    from datetime import datetime, timedelta
    import os
    folder = tmp_path / "old"
    engine.launch(["track1", "a.yaml"], folder, "old", popen=lambda *a, **k: SimpleNamespace(pid=0))
    engine.update(folder, pid=0, launcher_pid=os.getpid(), started=(datetime.now() - timedelta(days=2)).isoformat())
    closed = engine.poll(folder)
    assert closed.status == "failed" and closed.note.startswith("launch not confirmed")
    young = tmp_path / "young"
    engine.launch(["track1", "b.yaml"], young, "young", popen=lambda *a, **k: SimpleNamespace(pid=0))
    assert engine.poll(young).status == "running"


async def test_the_batches_page_shows_the_draft_and_the_batches(user: User, workspace: Path) -> None:  # noqa: F811
    from adroit.ui.app import build_pages
    batch.add_to_draft(workspace, ["track1", "a.yaml"], _prepared(workspace, "a"), "a drafted request")
    build_pages(workspace)
    await user.open("/batches")
    await user.should_see("a drafted request")
    await user.should_see("Start the batch")
    await user.should_see("No batches yet.")


async def test_the_bundle_page_checks_an_exported_bundle_read_only(user: User, workspace: Path,  # noqa: F811
                                                                    tmp_path: Path) -> None:
    from adroit.evidence.archive import export_run
    from adroit.ui.app import build_pages
    bundle = tmp_path / "study.zip"
    export_run(workspace / "track1_axial", bundle)
    build_pages(workspace)
    await user.open(f"/bundle?path={bundle}")
    await user.should_see("hashes agree")
    await user.should_see("not who made them", retries=3)
    await user.open(f"/bundle?path={tmp_path / 'missing.zip'}")
    await user.should_see("Not found")
    assert ui is not None


def test_a_batch_whose_runner_never_starts_is_interrupted_and_can_be_resumed_or_cancelled(tmp_path):
    """The recheck's RC21-05 (2026-10-22): a runner that could not be created left the batch running for ever (PID 0,
    its draft emptied, its resume refused, its cancel not finishing). Now a failed spawn interrupts it with the
    reason, its requests kept; a runner that never acknowledges its start is interrupted after the bound when the
    batches are listed, and a late one runs nothing; it resumes with a new confirmation; cancelled with no runner it
    closes, its queued requests cancelled."""
    import os
    from datetime import datetime, timedelta
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")

    def fails(*a, **k):
        raise OSError("no process")
    with pytest.raises(OSError):
        batch.start(root, "failed launch", popen=fails)
    (b,) = batch.batches(root)
    assert b.status == "interrupted" and "could not be started" in b.note and len(b.items) == 1
    folder = Path(b.folder)
    resumed = batch.resume(folder, popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    assert resumed.status == "running" and resumed.acknowledged is False
    batch._update(folder, spawned=(datetime.now() - timedelta(seconds=engine.LAUNCH_GRACE_SECONDS + 5)).isoformat())
    (b,) = batch.batches(root)                                    # a live PID is not an acknowledged start
    assert b.status == "interrupted" and b.note == batch.START_NOT_CONFIRMED
    launched = []
    late = _run(folder, b.approval_sha256, launch=lambda *a, **k: launched.append(a), poll=_completed)
    assert late.status == "interrupted" and not launched
    batch.resume(folder, popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    batch.cancel(folder)
    (b,) = batch.batches(root)
    assert b.status == "cancelled" and [i.status for i in b.items] == ["cancelled"] and not launched


def test_an_acknowledged_runner_that_dies_leaves_its_batch_resumable(tmp_path):
    """The re-audit's RR22-04 (2026-10-22): a runner that acknowledged its start and died, its launcher dying before
    it recorded the PID, left the batch running for ever (PID 0, acknowledged), its resume refused. The runner now
    records its own process with its acknowledgement, and an acknowledged batch that no runner holds (the runner
    holds its lifetime lock from acknowledgement to final status) is interrupted, whatever process holds its PID, and
    resumes with a new confirmation."""
    import os
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")
    b = batch.start(root, "dies", popen=lambda *a, **k: SimpleNamespace(pid=0))     # the launcher's PID never lands

    def dies(*a, **k):
        raise RuntimeError("the runner dies after acknowledging")
    with pytest.raises(RuntimeError):
        _run(Path(b.folder), b.approval_sha256, launch=dies)
    held = batch.load(Path(b.folder))
    assert held.status == "running" and held.acknowledged is True and held.pid == os.getpid()   # alive: reused
    (b,) = batch.batches(root)
    assert b.status == "interrupted"
    batch._update(Path(b.folder), status="running", pid=0)                       # the same with no PID at all
    (b,) = batch.batches(root)
    assert b.status == "interrupted"
    assert batch.resume(Path(b.folder), popen=lambda *a, **k: SimpleNamespace(pid=1)).status == "running"


def test_a_stale_listing_does_not_interrupt_a_resumed_live_batch(tmp_path):
    """The re-audit's RV22-03 (2026-10-22): a listing that saw a dead runner, delayed while another listing recovered
    the batch and it was resumed, marked the new live run interrupted. Recovery is bound to the runner's start (its
    generation) and to no runner holding the batch, both read again under the batch's lock."""
    import os
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")
    b = batch.start(root, "stale", popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    folder = Path(b.folder)
    batch._update(folder, acknowledged=True, pid=987654321)                      # the first runner died
    seen = batch.load(folder).generation                                          # listing A's observation
    assert batch._interrupt(folder, "", generation=seen).status == "interrupted"  # listing B recovers it
    resumed = batch.resume(folder, popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    assert resumed.generation == seen + 1
    stale = []

    def launch(*a, **k):                                   # the new runner holds the batch; listing A resumes
        stale.append(batch._interrupt(folder, "", generation=seen).status)
        stale.append(batch._interrupt(folder, "").status)  # without a generation: the held lock alone refuses it
    done = _run(folder, resumed.approval_sha256, launch=launch, poll=_completed, sleep=lambda _: None)
    assert stale == ["running", "running"] and done.status == "completed"


def test_a_late_launch_failure_leaves_a_resumed_live_batch_running(tmp_path):
    """The RV22 audit's RX22-07 (2026-10-22): the first launcher stalls, a listing interrupts its start, the batch is
    resumed and its new runner holds it; the first Popen then fails, and its handler marked the live run interrupted.
    The launcher's writes belong to its own start."""
    import os
    from threading import Event, Thread
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")
    ready, release, seen, errors = Event(), Event(), {}, []

    def stalled(argv, **_):
        folder = seen["folder"] = Path(argv[-3])
        batch._update(folder, spawned="2000-01-01T00:00:00")                 # past the grace: the listing interrupts
        assert batch._checked(folder).status == "interrupted"
        newer = batch.resume(folder, popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))

        def launch(*a, **k):
            ready.set()
            assert release.wait(10)

        def run_new():
            try:
                seen["done"] = batch.run(folder, newer.approval_sha256, launch=launch, poll=_completed,
                                         sleep=lambda _: None, generation=newer.generation).status
            except BaseException as error:                                      # pragma: no cover - reported
                errors.append(repr(error))
        seen["thread"] = Thread(target=run_new)
        seen["thread"].start()
        assert ready.wait(5)
        raise OSError("the first launch fails late")

    with pytest.raises(OSError):
        batch.start(root, "late failure", popen=stalled)
    current = batch.load(seen["folder"])
    assert (current.generation, current.status, current.acknowledged) == (2, "running", True)
    release.set()
    seen["thread"].join(10)
    assert not errors and seen["done"] == "completed"


def test_a_launch_failure_after_a_cancellation_keeps_it_cancelled(tmp_path):
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")
    seen = {}

    def cancelled_then_fails(argv, **_):
        seen["folder"] = Path(argv[-3])
        batch.cancel(seen["folder"])
        raise OSError("the launch fails after the cancellation")

    with pytest.raises(OSError):
        batch.start(root, "cancelled", popen=cancelled_then_fails)
    assert batch.load(seen["folder"]).status == "cancelled"


def test_a_late_launcher_does_not_overwrite_its_runners_own_pid(tmp_path):
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")

    def runner_first(argv, **_):                       # the runner acknowledges before Popen returns
        batch._update(Path(argv[-3]), acknowledged=True, pid=222)
        return SimpleNamespace(pid=111)

    b = batch.start(root, "ordering", popen=runner_first)
    assert (b.pid, batch.load(Path(b.folder)).pid) == (222, 222)


def test_a_runner_of_an_earlier_start_leaves_the_resumed_batch_alone(tmp_path):
    """A runner delayed past a resume had acknowledged the new start with its own PID, then found the approval
    changed and marked the batch refused, so the new runner never ran it."""
    import os
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")
    b = batch.start(root, "two starts", popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    folder = Path(b.folder)
    batch._update(folder, spawned="2000-01-01T00:00:00")
    assert batch._checked(folder).status == "interrupted"
    resumed = batch.resume(folder, popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))

    def never(*a, **k):                                # pragma: no cover - the stale runner must not launch
        raise AssertionError("an earlier start's runner launched a request")
    stale = batch.run(folder, b.approval_sha256, launch=never, poll=_completed, sleep=lambda _: None,
                      generation=b.generation)
    assert (stale.status, stale.acknowledged, stale.generation) == ("running", False, 2)
    done = batch.run(folder, resumed.approval_sha256, launch=lambda *a, **k: None, poll=_completed,
                     sleep=lambda _: None, generation=resumed.generation)
    assert done.status == "completed"


def test_a_delayed_runner_without_a_generation_leaves_a_resumed_batch_alone(tmp_path):
    """The RX22 audit's RY23-04 (2026-10-23): a runner from the old command line (no generation), delayed past an
    expiry and a resume with a new confirmation, acknowledged the new start and, its old digest no longer matching,
    marked it refused. A runner without a generation acts only on a batch from before generations (0)."""
    import os
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")
    b = batch.start(root, "legacy", popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    folder = Path(b.folder)
    batch._update(folder, spawned="2000-01-01T00:00:00")
    assert batch._checked(folder).status == "interrupted"
    resumed = batch.resume(folder, confirmed_budget=1.0, popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    assert resumed.approval_sha256 != b.approval_sha256 and resumed.generation == 2

    def never(*a, **k):                                # pragma: no cover - the legacy runner must not launch
        raise AssertionError("a runner of another start launched a request")
    legacy = batch.run(folder, b.approval_sha256, launch=never, poll=_completed, sleep=lambda _: None)
    assert (legacy.status, legacy.acknowledged, legacy.generation) == ("running", False, 2)
    done = _run(folder, resumed.approval_sha256, launch=lambda *a, **k: None, poll=_completed, sleep=lambda _: None)
    assert done.status == "completed"


def test_a_runner_without_a_generation_still_runs_a_batch_from_before_generations(tmp_path):
    import os
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")
    b = batch.start(root, "old", popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    folder = Path(b.folder)
    batch._update(folder, generation=0)                   # as written before RV22-03
    done = batch.run(folder, b.approval_sha256, launch=lambda *a, **k: None, poll=_completed, sleep=lambda _: None)
    assert done.status == "completed"


def test_a_runner_with_a_wrong_digest_is_refused_before_it_acknowledges(tmp_path):
    import os
    root = tmp_path / "runs"
    batch.add_to_draft(root, ["track1", "fixture.yaml"], root / "item", "request")
    b = batch.start(root, "digest", popen=lambda *a, **k: SimpleNamespace(pid=os.getpid()))
    refused = _run(Path(b.folder), "0" * 64, launch=lambda *a, **k: None, poll=_completed, sleep=lambda _: None)
    assert refused.status == "refused" and refused.acknowledged is False

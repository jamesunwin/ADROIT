"""The auditor's DV–IE recheck (the independent audit of 2026-11-11 (dv ie recheck)), its findings repaired (the record
the DW repair record of 2026-11-11); DW-01's tests are ``tests/experiments/test_diamx_templates.py``, DW-06's
``tests/ui/test_calculation_ownership.py``.

- DW-02: a table's fingerprint takes the detector data behind a link to a folder, under its names, not its target.
- DW-03: nothing is signalled that is not proven the job's: a runner's number held by another process, a group whose
  leader has ended.
- DW-04: an optimum-interval call is bounded when what its program started holds on after it, and stops it.
- DW-05: the optimum interval's refusal reaches the person through the private search's review, named.

The process cases start real processes, all the test's own, and end every one."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from adroit.experiments import registry, xenon
from adroit.orchestrator.track1_identity import InputUnreadable
from adroit.parameter_space import limit_tables
from adroit.statistics import optimum_interval as oi
from adroit.ui import engine
from tests.experiments.test_diamx_inputs import _Diamx


def _gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip() \
        .startswith("Z")


def _wait_gone(pids, seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + seconds
    while not all(_gone(p) for p in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    return all(_gone(p) for p in pids)


def _end(pids) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


# --- DW-02 -------------------------------------------------------------------------------------------------------------

def _linked(root: Path, monkeypatch) -> _Diamx:
    """A DIAMX installation whose ``diamx/data`` is a link to a folder elsewhere."""
    d = _Diamx(root, monkeypatch)
    target = root / "elsewhere" / "detector"
    target.parent.mkdir()
    d.data.parent.rename(target)
    d.data.parent.symlink_to(target, target_is_directory=True)
    return d


def _fingerprint(d) -> str:
    limit_tables.fingerprint.cache_clear()
    return limit_tables.fingerprint(d.module.search)


def test_a_stored_table_is_stale_once_data_behind_a_folder_link_changes(tmp_path, monkeypatch):
    """The auditor's ``linked_table_data``: the table, current when stored, is no longer current once the linked data
    changed, read cold; the package's files are named through the link."""
    d = _linked(tmp_path / "a", monkeypatch)
    monkeypatch.setattr(registry, "load_module", lambda name: d.module)
    files = [str(p.relative_to(d.folder)) for p in xenon.diamx_versions(d.folder, d.python)[0]]
    assert files == ["diamx/data/lz_ws2024_wimp_data.csv", "diamx/model.py"]
    before, limit = _fingerprint(d), d.limit()
    tables = tmp_path / "tables"
    tables.mkdir()
    monkeypatch.setattr(limit_tables, "TABLES", tables)
    (tables / (limit_tables.slug(d.module.search, "SI") + ".yaml")).write_text(yaml.safe_dump(
        {"fingerprint": before, "masses_gev": [1.0, 100.0], "limits_cm2": [limit, limit], "interpolation_accuracy": 0.001}))
    limit_tables.clear_cache()
    assert limit_tables.lookup(d.module.search, "SI", 10.0) is not None             # current as stored
    d.data.write_text("7\n")
    assert _fingerprint(d) != before
    limit_tables.clear_cache()
    assert limit_tables.lookup(d.module.search, "SI", 10.0) is None                 # 3 at the pin: the old table
    limit_tables.fingerprint.cache_clear()
    limit_tables.clear_cache()


def test_the_fingerprint_names_linked_files_not_where_the_link_leads(tmp_path, monkeypatch):
    """Two installations with the same files, their data linked to folders at different places: one fingerprint, so a
    table made on one machine is current on another (no machine's link target is taken); and other data, another."""
    held = {}
    monkeypatch.setattr(registry, "load_module", lambda name: held["module"])
    prints = []
    for root in (tmp_path / "one", tmp_path / "two" / "deeper"):
        d = _linked(root, monkeypatch)
        held["module"] = d.module
        prints.append(_fingerprint(d))
    assert prints[0] == prints[1]
    d.data.write_text("7\n")
    assert _fingerprint(d) != prints[0]
    limit_tables.fingerprint.cache_clear()


def test_a_link_back_into_the_package_is_refused_not_passed_over(tmp_path, monkeypatch):
    d = _Diamx(tmp_path, monkeypatch)
    (d.folder / "diamx" / "data" / "loop").symlink_to(d.folder / "diamx", target_is_directory=True)
    with pytest.raises(InputUnreadable, match="leads back into itself"):
        xenon.diamx_versions(d.folder, d.python)


# --- DW-03 -------------------------------------------------------------------------------------------------------------

def _sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)


def test_a_runner_s_number_held_by_another_process_is_never_signalled(tmp_path):
    """The auditor's ``reused_runner_pid``: a running job whose runner's number is now another process's (its start
    not the one the launch recorded, or none recorded): Cancel signals nothing, says so, and the job is closed."""
    for recorded in (lambda pid: engine.process_started(pid) - 3600, lambda pid: 0.0):
        sentinel = _sleeper()
        try:
            time.sleep(0.2)                                                     # started: ``ps`` lists it
            folder = tmp_path / f"job-{sentinel.pid}"
            folder.mkdir()
            engine.save(engine.Job(title="stale", kind="track1", command=["track1"], folder=str(folder),
                                   status="running", pid=sentinel.pid, acknowledged=True,
                                   started="2000-01-01T00:00:00", runner_started=recorded(sentinel.pid)))
            assert not engine.runner_alive(engine.load(folder))
            engine.cancel(folder)
            time.sleep(0.3)
            assert sentinel.poll() is None                                      # -15 at the pin
            assert engine.RUNNER_UNPROVEN.format(pid=sentinel.pid) in engine.load(folder).note
            if recorded(sentinel.pid):                                          # its runner gone: closed, not running
                assert engine.poll(folder).status == "cancelled"
        finally:
            sentinel.kill()
            sentinel.wait()


def test_a_launched_runner_is_proven_by_the_start_its_launcher_read_and_cancel_ends_it(tmp_path):
    """``launch`` records its runner's start as ``ps`` gives it (here the runner a sleeper, started as the launcher
    starts one): proven, and the one a cancel signals."""
    spawned = []

    def popen(argv, **kwargs):
        spawned.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True))
        time.sleep(0.2)
        return spawned[-1]
    try:
        job = engine.launch(["track1", "m.yaml"], tmp_path / "job", "t", popen=popen)
        assert job.runner_started and job.runner_started == engine.process_started(job.pid)
        engine.update(tmp_path / "job", acknowledged=True)
        assert engine.runner_alive(engine.load(tmp_path / "job"))
        engine.cancel(tmp_path / "job")
        assert spawned[0].wait(timeout=10) == -signal.SIGTERM
    finally:
        for process in spawned:
            if process.poll() is None:
                process.kill()
                process.wait()


GROUP = '''
import subprocess, sys, time
from pathlib import Path
if len(sys.argv) > 2:
    time.sleep(60)
else:
    child = subprocess.Popen([sys.executable, __file__, sys.argv[1], "child"])
    Path(sys.argv[1]).write_text(str(child.pid))
'''


def test_a_group_whose_leader_has_ended_is_named_never_signalled(tmp_path):
    """The auditor's ``reused_group_leader_gone``: a new session's leader that started a child and ended; a job naming
    the leader's number with another start. The child is not taken as the job's calculation: Cancel leaves it, and the
    job names it as not proven."""
    script, record = tmp_path / "group.py", tmp_path / "child"
    script.write_text(GROUP)
    leader = subprocess.Popen([sys.executable, str(script), str(record)], start_new_session=True)
    leader.wait(timeout=10)
    child = int(record.read_text())
    try:
        folder = tmp_path / "job"
        folder.mkdir()
        job = engine.Job(title="t", kind="track1", command=["track1"], folder=str(folder), status="failed",
                         calculation=leader.pid, calculation_started=946684800.0)
        engine.save(job)
        assert engine.calculation_alive(job) == [] and engine.calculation_unproven(job) == [child]
        engine.cancel(folder)
        engine.cancel(folder)                                                  # a second, forcible
        time.sleep(0.3)
        assert not _gone(child)                                                # SIGTERMed at the pin
        assert engine.UNPROVEN.format(pids=child, group=leader.pid) in engine.load(folder).note
        assert engine.left_running(engine.load(folder)) == ""                  # no Cancel offered for it
    finally:
        _end([child])


def test_a_live_leader_with_its_start_still_proves_its_group(tmp_path):
    script, record = tmp_path / "group.py", tmp_path / "child"
    script.write_text(GROUP.replace("Path(sys.argv[1]).write_text(str(child.pid))",
                                    "Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"))
    leader = subprocess.Popen([sys.executable, str(script), str(record)], start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while not record.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        child = int(record.read_text())
        job = engine.Job(title="t", kind="track1", command=["track1"], folder=str(tmp_path), status="failed",
                         calculation=leader.pid, calculation_started=engine.process_started(leader.pid))
        assert sorted(engine.calculation_alive(job)) == sorted([leader.pid, child])
        assert engine.calculation_unproven(job) == []
        engine.stop_calculation(job, forcibly=True)
        assert _wait_gone([leader.pid, child])
    finally:
        if leader.poll() is None:
            leader.kill()
        leader.wait()


# --- DW-04 -------------------------------------------------------------------------------------------------------------

ORPHAN = '''#!{python}
import subprocess, sys
subprocess.Popen([sys.executable, "-c",
                  "import os, time; open({record!r}, 'w').write(str(os.getpid())); time.sleep(20)"],
                 start_new_session=True)
{tail}
'''


def _program(tmp_path: Path, tail: str = "") -> tuple[Path, Path]:
    record = tmp_path / "descendant"
    program = tmp_path / "oi"
    program.write_text(ORPHAN.format(python=sys.executable, record=str(record), tail=tail))
    program.chmod(0o700)
    return program, record


def _descendant(record: Path) -> int:
    deadline = time.monotonic() + 10
    while not (record.exists() and record.read_text()) and time.monotonic() < deadline:
        time.sleep(0.02)
    return int(record.read_text())


def test_a_program_that_exits_leaving_a_session_of_its_own_is_neither_waited_for_nor_left(tmp_path, monkeypatch):
    """The auditor's ``oi_orphan_deadline``: the program starts a child in its own session, holding the call's output,
    and exits. The call returns at once (4.2 s at a 0.5 s deadline at the pin), refused, and the child is stopped. A 2 s
    deadline, not 0.5 s: under a loaded machine the program's own interpreter had not started and exited within 0.5 s,
    and the call was refused for its deadline before it could be refused for its output (the merged branch's run,
    2026-11-12); at the pin the call waits for the child past any deadline."""
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", "2")
    program, record = _program(tmp_path)
    started = time.monotonic()
    with pytest.raises(oi.OptimumIntervalFailed, match="not a limit and a flag"):
        oi._calculate(program, "0.9 0\n")
    elapsed = time.monotonic() - started
    descendant = _descendant(record)
    try:
        assert elapsed < 3.0 and _wait_gone([descendant], 5.0)
    finally:
        _end([descendant])


def test_a_program_past_its_deadline_is_stopped_with_what_it_left_in_another_session(tmp_path, monkeypatch):
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", "0.5")
    program, record = _program(tmp_path, "import time; time.sleep(20)")
    started = time.monotonic()
    with pytest.raises(oi.OptimumIntervalFailed, match="deadline of 0.5 s"):
        oi._calculate(program, "0.9 0\n")
    elapsed = time.monotonic() - started
    descendant = _descendant(record)
    try:
        assert elapsed < 0.5 + 3.0 and _wait_gone([descendant], 5.0)
    finally:
        _end([descendant])


def test_a_limit_is_returned_without_waiting_for_what_its_program_left(tmp_path, monkeypatch):
    """A program that prints its limit and leaves a process: the limit at once (the pin had waited for that process to
    end, unbounded). What it left is not sought on this path (``optimum_interval``'s docstring); the test ends it."""
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", "30")
    program, record = _program(tmp_path, "print('3.0 0')")
    started = time.monotonic()
    assert oi._calculate(program, "0.9 0\n") == oi._Limit(mu=3.0, flag=0)
    assert time.monotonic() - started < 3.0
    _end([_descendant(record)])


# --- DW-05 -------------------------------------------------------------------------------------------------------------

REFUSALS = {"a negative μ": lambda: oi.usable(-1.0, 0), "a refused flag": lambda: oi.usable(3.0, 64),
            "the deadline": lambda: (_ for _ in ()).throw(oi.OptimumIntervalFailed(
                "the optimum interval code passed its deadline of 60 s (ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S) and was "
                "stopped"))}


@pytest.mark.parametrize("case", list(REFUSALS))
def test_the_review_s_validation_refuses_in_its_own_words_with_no_receipt(tmp_path, monkeypatch, case):
    """Through the real ``validate`` (the fixture's dossier, approved): an anchor's interval refused by the tool is the
    review's ordinary refusal, its reason kept; no validation receipt is written."""
    from adroit.constraints.experimental_review import CHECKLIST, approve, packet
    from adroit.constraints.experimental_search_review import validate
    from adroit.experiments import private_search
    from tests.private_search_fixtures import fixture
    catalog, revision = fixture(tmp_path)
    value = packet(revision.reference, "signal", catalog=catalog)
    approve(revision.reference, "signal", value["scientific_sha256"], "Fixture", confirmed=True, checks=CHECKLIST,
            catalog=catalog)

    def refused(*args, **kwargs):
        REFUSALS[case]()
    monkeypatch.setattr(private_search, "interval_upper", refused)
    with pytest.raises(ValueError, match="could not be calculated .*not validated") as error:
        validate(revision.reference, "signal", 0.001, value["scientific_sha256"], catalog)
    assert not isinstance(error.value, RuntimeError)
    receipts = catalog.path("search_validations")
    assert not receipts.exists() or not list(receipts.glob("*.json"))


def test_the_workbench_and_the_command_line_name_the_tool_s_refusal(monkeypatch):
    """The auditor's ``oi_review_refusal``: ``validate`` itself raising the tool's refusal (``usable(-1, 0)``) through
    the Validate callback and the ``validate-search`` command: named in a notification, and on the command line with
    exit 1, never an escaped exception."""
    from typer.testing import CliRunner
    from adroit.constraints import experimental_search_review as review
    from adroit.orchestrator.cli import app
    from adroit.ui import experimental_review as page
    callbacks, notified = {}, []

    def failing(*args, **kwargs):
        oi.usable(-1.0, 0)
    monkeypatch.setattr(page.ui, "button", lambda label, on_click: callbacks.__setitem__(label, on_click))
    monkeypatch.setattr(page.ui, "notify", notified.append)
    monkeypatch.setattr(page.ui, "label", notified.append)
    monkeypatch.setattr(page, "packet", lambda *a, **k: {"scientific_sha256": "0" * 64})
    monkeypatch.setattr(review, "validate", failing)
    page._search_tools(SimpleNamespace(reference="synthetic:1"), SimpleNamespace(result_id="synthetic"), None,
                       SimpleNamespace(value=0.05), SimpleNamespace(value=""), SimpleNamespace(value=""), lambda: None)
    next(on_click for label, on_click in callbacks.items() if label.startswith("Validate independent"))()
    assert len(notified) == 1 and notified[0].startswith("Not validated: ") and "μ = -1.0" in notified[0]
    done = CliRunner().invoke(app, ["experiments", "validate-search", "synthetic:1", "--result", "synthetic",
                                    "--expected-hash", "0" * 64, "--tolerance", "0.05"])
    assert done.exit_code == 1 and not isinstance(done.exception, oi.OptimumIntervalUnavailable)
    assert "Not validated: " in done.output and "μ = -1.0" in done.output

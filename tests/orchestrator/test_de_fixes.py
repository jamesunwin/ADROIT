"""The auditor's DD recheck (the independent audit of 2026-11-05 (dd recheck), pin 5e2d8da): DE-01, another run's bill counted as a held
study's where that run's records were read between two readings of the study's run record and the study's then
restored byte for byte; DE-02, two reanalyses into one folder both succeeding, and a publication's parts written over
another's. (DE-03, the matrix's oracle of a page's fields, is repaired in ``tests/version_matrix.py`` and its
harnesses.) Every calculation, review and provider is stood in for: no request is sent, and $0 is spent; the dollars
are simulated."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from adroit.evidence.version import resolve
from adroit.orchestrator import accounting, preflight
from adroit.ui import engine
from tests.orchestrator.test_vi_audit import publish, versions

A, B = "attempt-a", "attempt-b"
PAID = ["idea", "--text", "SIMULATED", "--budget", "10"]
SOURCES = ("ledger", "log", "stop", "receipt")       # each record a paid run's cost can be read from


# --- DE-01: each record of a run's money is that run's -----------------------------------------------------------

def _in_job(folder: Path, attempt: str):
    return patch.dict(os.environ, {"ADROIT_JOB_FOLDER": str(folder), "ADROIT_JOB_ATTEMPT": attempt})


def _session(tmp: Path) -> tuple[object, str]:
    """A model-library session (its service and identifier) whose paid ledger holds two simulated requests, one of
    each run: attempt-a's $1.25 and attempt-b's $8.50 (within its $10 cap)."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service = Intake(Catalog(tmp / "models"))
    session = service.start(budget=10).session_id
    events = []
    for attempt, dollars in ((A, 1.25), (B, 8.5)):
        events += [{"id": f"r-{attempt}", "state": "reserved", "provider": "anthropic", "model": "SIMULATED fixture",
                    "reserved_usd": dollars}, {"id": f"r-{attempt}", "state": "settled", "cost_usd": dollars}]
    (service.folder(session) / "paid.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    return service, session


def _records(folder: Path, attempt: str, dollars: float, source: str, session: str = "") -> None:
    """Run ``attempt``'s records in ``folder`` as its writers leave them, each naming it: its job record
    (``engine.save``) and its log (the runner's two first lines); and the record its cost is read from (``source``): its
    own paid ledger, opened by it (``preflight.open_job_ledger``) and settling ``dollars``; its log's closing line; a
    budget stop's record in the partial folder its log names; or, a session step's, its request record."""
    from adroit.core.durable import write_atomic
    from adroit.orchestrator.model_intake import REQUESTS, RunRequests
    command = ["models", "step", session, "--kind", "idea", "--budget", "10"] if source == "receipt" else PAID
    engine.save(engine.Job(title="a run", kind=command[0], command=command, folder=str(folder), status="completed",
                           returncode=0, attempt=attempt))
    log = [f"$ adroit {' '.join(command)}", f"# run attempt {attempt}"]
    (folder / "paid.jsonl").unlink(missing_ok=True)
    (folder / "paid.jsonl.held").unlink(missing_ok=True)    # and its mark, which its writer leaves with it (DO-01)
    if source == "ledger":
        with _in_job(folder, attempt):
            preflight.open_job_ledger(folder / "paid.jsonl")
        with (folder / "paid.jsonl").open("a") as stream:
            stream.write(json.dumps({"id": f"r-{attempt}", "state": "reserved", "provider": "SIMULATED",
                                     "model": "fixture", "reserved_usd": 10}) + "\n")
            stream.write(json.dumps({"id": f"r-{attempt}", "state": "settled", "cost_usd": dollars}) + "\n")
    elif source == "log":
        log.append(accounting.live_text(dollars, 0.0))
    elif source == "stop":
        partial = folder / f"partial_{attempt}"
        partial.mkdir(exist_ok=True)
        write_atomic(partial / "result.json", json.dumps({
            "status": "budget_stopped", "committed_usd": dollars, "settled_usd": dollars, "uncertain_usd": 0.0,
            "attempt": attempt}).encode())
        log.append(f"LLM budget stopped before dispatch. Partial results: {partial}; paid responses: none")
    else:
        write_atomic(folder / REQUESTS, RunRequests(session_id=session, request_ids=[f"r-{attempt}"],
                                                    attempt=attempt).model_dump_json().encode())
    (folder / "log.txt").write_text("\n".join(log) + "\n")


def _study(tmp: Path, source: str):
    """Study A ($1.25 in its record), published in its folder by the workbench run attempt-a, whose records of its
    money (``source``) settle $1.25; (its folder, its held version, the session service or None, the session)."""
    folder = tmp / "runs" / "study"
    a, _ = versions(folder)
    with _in_job(folder, A):
        publish(folder, a, "A", 1.25)
    service, session = _session(tmp) if source == "receipt" else (None, "")
    _records(folder, A, 1.25, source, session)
    return folder, resolve(folder), service, session


def _between_readings(folder: Path, source: str, session: str, every: bool):
    """The auditor's A→B→A (DE-01): once the cost has read its run's record, B's records written (its job record and the
    record of its money, $8.50); once the cost has read them, A's restored byte for byte. ``every``: at each reading,
    so that none is of one run's records throughout; else once."""
    kept = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    real_job, real_cost, state = accounting.read_job, accounting.cost, {"pending": False, "done": False, "reads": 0}

    def read(where):
        found = real_job(where)
        if Path(where) == folder:
            state["reads"] += 1                     # a reading's first read of its run record is the odd one
            if state["reads"] % 2 and not state["pending"] and (every or not state["done"]):
                state["pending"] = True
                _records(folder, B, 8.5, source, session)
        return found

    def cost(*args, **kw):
        out = real_cost(*args, **kw)
        if state["pending"]:
            for path, data in kept.items():
                path.write_bytes(data)
            state.update(pending=False, done=True)
        return out
    return patch.object(accounting, "read_job", read), patch.object(accounting, "cost", cost)


def _surfaces(folder: Path, service) -> dict:
    """Each surface's reading of the held study's cost, each in a fresh reading: ``held_cost``, the card, the line in
    Studies, ``adroit studies``."""
    from adroit.orchestrator.cli import app
    from adroit.ui import pages
    budgets = patch.object(accounting, "_budgets", return_value=service) if service is not None else patch.dict({})
    with budgets:
        return {"cost": lambda: accounting.held_cost(resolve(folder)),
                "card": lambda: pages.study_cost(resolve(folder)),
                "list": lambda: pages.list_cost(resolve(folder)),
                "cli": lambda: CliRunner().invoke(app, ["studies", str(folder.parent)]).output}


@pytest.mark.parametrize("every", [False, True], ids=["restored once", "restored at every reading"])
@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("surface", ["cost", "card", "list", "cli"])
def test_another_run_s_records_restored_over_while_its_cost_is_read_are_never_the_study_s(tmp_path, source, every,
                                                                                         surface):
    """DE-01, the auditor's A→B→A for each record of a run's money (its paid ledger, its log, a budget stop's record, a
    session step's request record): B's $8.50 is never shown as the study's, nor counted in a total. Restored once, the
    cost is read again and is A's own run's $1.25, from A's records; restored at every reading, it is the study record's
    $1.25, saying that its run's records changed while read."""
    folder, held, service, session = _study(tmp_path, source)
    job, cost = _between_readings(folder, source, session, every)
    from adroit.orchestrator.cli import app
    from adroit.ui import pages
    budgets = patch.object(accounting, "_budgets", return_value=service) if service is not None else patch.dict({})
    with budgets, job, cost:
        if surface == "cost":
            out = accounting.held_cost(held)
            assert out.run_usd == 1.25 and not out.other_run and out.unsettled == every, out
            assert out.settled_only == every and ("8.50" not in accounting.run_line(out))
            return
        shown = (pages.study_cost(held) if surface == "card" else pages.list_cost(held) if surface == "list" else
                 CliRunner().invoke(app, ["studies", str(folder.parent)]).output)
    assert "$1.25" in shown and "8.50" not in shown, shown
    assert ("changed while read" in shown or "written while its cost was read" in shown) == every, shown
    if surface == "cli":
        assert "total: $1.25" in shown or "$1.25 more settled in older records" in shown, shown


@pytest.mark.parametrize("source", SOURCES)
def test_another_run_s_record_read_beside_the_study_s_run_record_is_not_counted(tmp_path, source):
    """DE-01: the study's run record (``job.json``) never rewritten, but the record of its money replaced by another
    run's, which names that run: it is not counted, and the cost is the study record's, naming the record. A run page
    reading that run's folder (``cost``) names the record and shows no figure from it."""
    folder, held, service, session = _study(tmp_path, source)
    job = (folder / "job.json").read_bytes()
    _records(folder, B, 8.5, source, session)
    (folder / "job.json").write_bytes(job)                     # A's run record, as A's run left it
    budgets = patch.object(accounting, "_budgets", return_value=service) if service is not None else patch.dict({})
    with budgets:
        out = accounting.held_cost(held)
        live = accounting.cost(folder, accounting.read_job(folder))
    assert out.run_usd == 1.25 and out.other_run and "names another run" in out.note, out
    assert "8.50" not in accounting.run_line(out) and "8.50" not in accounting.short_line(out)
    assert live.foreign and "names another run" in live.note and "8.50" not in accounting.run_line(live), live


@pytest.mark.parametrize("source", SOURCES)
def test_a_run_s_own_records_restored_unchanged_are_its_own(tmp_path, source):
    """DE-01, what stays: the study's own run's records, rewritten with their own bytes while the cost is read (its run
    record saved again, say), are read again and are the study's own run's $1.25."""
    folder, held, service, session = _study(tmp_path, source)
    real, done = accounting.read_job, []

    def read(where):
        found = real(where)
        if not done and Path(where) == folder:
            done.append(True)
            _records(folder, A, 1.25, source, session)        # its own records, written again
        return found
    budgets = patch.object(accounting, "_budgets", return_value=service) if service is not None else patch.dict({})
    with budgets, patch.object(accounting, "read_job", read):
        out = accounting.held_cost(held)
    assert done and out.run_usd == 1.25 and not out.other_run and not out.unsettled and not out.foreign, out


def test_each_record_of_a_run_s_money_names_its_run(tmp_path, monkeypatch):
    """DE-01, the writers: in a workbench run, its paid ledger opens with an entry naming it (``read_owned``), its
    request record names it, a budget stop's record names it, and its log's second line names it; outside a run, none
    is named, and a ledger from before (no entry) is read as found."""
    from adroit.agents.budget import BudgetExceeded, read_owned
    from adroit.orchestrator import cli
    from adroit.orchestrator.model_intake import REQUESTS, RunRequests
    from adroit.ui import runner
    folder = tmp_path / "run"
    folder.mkdir()
    monkeypatch.setenv("ADROIT_JOB_FOLDER", str(folder))
    monkeypatch.setenv("ADROIT_JOB_ATTEMPT", A)

    @preflight.paid_command
    def step(budget=1.0, model=""):
        return "done"
    step(budget=1.0)
    step(budget=1.0)                                            # resumed: the same run, opened again
    assert read_owned(folder / "paid.jsonl") == ({}, [A, A])
    preflight.record_requests(folder, type("S", (), {"request_ids": lambda self: ["r1"]})(), "s1")
    assert RunRequests.model_validate_json((folder / REQUESTS).read_text()).attempt == A

    @cli._budget_boundary
    def stopped(out):
        error = BudgetExceeded(.1, .25, .2)
        error.ledger_path = str(folder / "paid.jsonl")
        raise error
    with pytest.raises(BaseException):
        stopped(out=str(folder / "stop"))
    assert json.loads((folder / "stop" / "result.json").read_text())["attempt"] == A
    job = engine.Job(title="a run", kind="idea", folder=str(folder), command=PAID, acknowledged=False, attempt=A)
    engine.save(job)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **k: type("P", (), {"pid": 0, "wait": lambda self: 0})())
    runner.run(folder, engine.command_sha256(job.command))
    assert (folder / "log.txt").read_text().splitlines()[1] == f"# run attempt {A}"
    assert accounting._log_text(folder, A)[1] == [] and accounting._log_text(folder, B)[0] == ""
    monkeypatch.delenv("ADROIT_JOB_FOLDER")
    assert preflight.run_attempt() == ""
    (tmp_path / "old.jsonl").write_text(json.dumps({"id": "r", "state": "reserved", "provider": "x",
                                                    "reserved_usd": 1}) + "\n")
    assert read_owned(tmp_path / "old.jsonl")[1] == []


# --- DE-02: a reanalysis's folder is its own; a publication's parts are never written over another's -------------

def _reanalysis(tmp: Path):
    """A signal study and a reanalysis service with its draft of it (``test_version_matrix._signal_world``): (the
    world, the service, the draft, the child folder)."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.reanalysis import Reanalysis
    from tests.evidence.test_version_matrix import _signal_world
    world = _signal_world(tmp)
    service = Reanalysis(Catalog(tmp / "catalog"))
    return world, service, service.open(str(world.path)), world.folder / "child"


def _stood_in(service, world, calculate=None):
    """The reanalysis's review, catalogue, context and calculation stood in for (the auditor's control): the calculation
    returns A, after ``calculate()`` where given."""
    from contextlib import ExitStack
    from adroit.core.evidence import EvidenceContext
    from adroit.evidence import runtime
    from adroit.orchestrator import signal

    def run(request):
        if calculate is not None:
            calculate()
        return world.a
    stack = ExitStack()
    for target, name, kw in ((service, "preview", {"return_value": {"review_sha256": "r", "blockers": []}}),
                             (service, "_catalogue_models", {"side_effect": lambda request, *a: request}),
                             (runtime, "capture_request", {"return_value": EvidenceContext(notes=["simulated, $0"])}),
                             (signal, "run", {"side_effect": run}),
                             (signal, "report", {"return_value": "A computed report"})):
        stack.enter_context(patch.object(target, name, **kw))
    return stack


def _run(service, draft, child) -> str:
    return service.run(draft.reference, child, "r", confirmed=True, reviewer="SIMULATED")[1]


def _b(child: Path, world) -> None:
    """B, an unrelated signal study, published in the child's folder by the production writer."""
    from adroit.orchestrator import runs
    runs._write(child, world.b, "B report", "signal", "B study")


def _files(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file() and p.name != ".study.lock"}


def test_of_two_reanalyses_into_one_folder_exactly_one_owns_it(tmp_path):
    """DE-02, the auditor's reproducer 1: two reanalyses (two drafts) into one new child folder, held at a barrier once each
    has passed its fresh-folder check: exactly one runs and publishes; the other is refused before it calculates,
    and nothing of it is written."""
    import threading
    from adroit.orchestrator import runs
    world, service, draft, child = _reanalysis(tmp_path)
    other = service.open(str(world.path))
    barrier, local, real = threading.Barrier(2, timeout=30), threading.local(), runs.fresh

    def fresh(folder):
        found = real(folder)
        if not getattr(local, "done", False):
            local.done = True
            barrier.wait()                  # both past the fresh-folder check before either claims the folder
        return found
    outcomes, calculations = {}, []

    def one(name, d):
        try:
            outcomes[name] = _run(service, d, child)
        except ValueError as error:
            outcomes[name] = error
    with _stood_in(service, world, calculate=lambda: calculations.append(1)), patch.object(runs, "fresh", fresh):
        threads = [threading.Thread(target=one, args=pair) for pair in (("A", draft), ("B", other))]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
    won = [o for o in outcomes.values() if isinstance(o, str)]
    lost = [o for o in outcomes.values() if isinstance(o, ValueError)]
    assert len(won) == 1 and len(lost) == 1, outcomes
    assert "another process is writing into this folder" in str(lost[0]) and calculations == [1]
    found = resolve(child)
    assert found.record_state == "bound" and found.envelope().certificates["reanalysis_lineage"]["fresh_run"]


@pytest.mark.parametrize("thread", ["another thread", "the same thread"])
@pytest.mark.parametrize("boundary", ["calculation", "result", "evidence", "report", "record"])
def test_another_adroit_writer_into_a_reanalysis_s_folder_never_joins_its_publication(tmp_path, boundary, thread):
    """DE-02: another of ADROIT's writers publishing B into the child's folder while the reanalysis runs (during its
    calculation, or after any of its parts): from another thread (another process, as the lock is a file's), it waits
    for the run to end, and is then published whole; from the run's own thread, it is refused at once, nothing of it
    written. Either way the run returns A, its check passing, and A's parts are never joined by B's."""
    import threading
    from adroit.core.durable import Busy
    from adroit.evidence import build
    from adroit.orchestrator import studies
    world, service, draft, child = _reanalysis(tmp_path)
    started, refused, done = [], [], []

    def b():
        if started:
            return
        started.append(True)
        if thread == "the same thread":
            try:
                _b(child, world)
            except Busy as error:
                refused.append(error)
            return
        worker = threading.Thread(target=lambda: (_b(child, world), done.append(True)))
        worker.start()
        started.append(worker)
        worker.join(0.5)                    # it waits for the folder
        assert not done
    real_parts, real_record = build.kept_parts, studies.record
    count = {"result": 1, "evidence": 2, "report": 3}.get(boundary)

    def parts(path, content, wrote, *args, **kw):
        real_parts(path, content, wrote, *args, **kw)
        if Path(path).parent == child and len(wrote) == count and not started:
            b()

    def record(folder, *args, **kw):
        out = real_record(folder, *args, **kw)
        if boundary == "record" and Path(folder) == child:
            b()
        return out
    with _stood_in(service, world, calculate=b if boundary == "calculation" else None), \
            patch.object(build, "kept_parts", parts), patch.object(studies, "record", record):
        text = _run(service, draft, child)
    assert "A computed report" in text and started
    if thread == "the same thread":
        assert refused and "nothing was written" in str(refused[0])
        assert resolve(child).typed().request.experiment == "MatrixResultA"
    else:
        started[1].join(60)
        assert done, "B's writer did not finish"
        found = resolve(child, presentation=True)
        assert found.typed().request.experiment == "MatrixResultB" and found.record_state == "bound"
        assert "reanalysis_lineage" not in found.envelope().certificates


EDGES = ("result", "evidence", "report", "before its record", "at its record", "after its record", "after its check")


@pytest.mark.parametrize("boundary", EDGES)
def test_a_writer_outside_adroit_s_between_a_reanalysis_s_parts_is_left_as_it_wrote(tmp_path, boundary):
    """DE-02, the auditor's publication edges: B published whole in the child's folder between the reanalysis's parts by a
    process outside ADROIT's writers (one that takes no lock): the run stops there, refusing, says what it had written
    and that it wrote nothing more, and B's publication is left byte for byte as B's writer left it, without A's
    lineage beside it. The one window a lockless writer can use, between the check before the record and the record
    (``at its record``), is said: the run's record is written over B's, and its refusal names its record and its
    lineage's file among what it wrote. After the run's check, the run returns A, and B is left whole."""
    from adroit.evidence import build
    from adroit.orchestrator import studies
    from tests import version_matrix as vm
    world, service, draft, child = _reanalysis(tmp_path)
    left: dict[str, bytes] = {}
    begun: list[bool] = []

    def b():
        if not begun:
            begun.append(True)              # B's own writer records too
            with vm.outside():
                _b(child, world)
            left.update(_files(child))
    from adroit.orchestrator import reanalysis
    real_parts, real_record, real_still = build.kept_parts, studies.record, reanalysis._still
    count = {"result": 1, "evidence": 2, "report": 3, "before its record": 4}.get(boundary)
    calls = {"n": 0}

    def parts(path, content, wrote, *args, **kw):
        if Path(path).parent == child:
            calls["n"] += 1
            if calls["n"] == count:
                b()                         # after the part, before the check that guards the next
        return real_parts(path, content, wrote, *args, **kw)

    def record(folder, *args, **kw):
        if boundary == "at its record" and Path(folder) == child:
            b()                             # between the check that guards the record and the record
        out = real_record(folder, *args, **kw)
        if boundary == "after its record" and Path(folder) == child:
            b()
        return out

    def still(token):
        real_still(token)
        if boundary == "after its check":
            b()
    with _stood_in(service, world), patch.object(build, "kept_parts", parts), \
            patch.object(studies, "record", record), patch.object(reanalysis, "_still", still):
        if boundary == "after its check":
            assert "A computed report" in _run(service, draft, child)
            assert left and _files(child) == left
            return
        with pytest.raises(ValueError, match="replaced by another process") as refused:
            _run(service, draft, child)
    said = str(refused.value)
    assert "wrote nothing more" in said, said
    if boundary == "at its record":
        assert [n for n, data in left.items() if _files(child).get(n) != data] == ["study.json"]
        assert "reanalysis.json beside them, record" in said, said
        return
    assert left and _files(child) == left, boundary
    assert ("record" in said) == (boundary == "after its record"), said

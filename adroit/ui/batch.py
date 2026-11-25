"""The workbench's batch queue (the batch plan's §7): several requests, run one after another.

- **The draft.** A request a wizard prepares can join the draft instead of starting (the wizards' "Add to the batch"
  switch): its folder and inputs are written as for a run, and its command, title and confirmed budget are added to
  ``<runs>/.adroit/batch_draft.json``.
- **Starting.** The draft becomes ``batch.json`` in a new folder under ``<runs>/batches/``, the person confirming the
  batch's total budget (the sum of its items'), and the batch's runner starts, detached and at low priority as a run's
  does (``python -m adroit.ui.batch FOLDER``).
- **Running.** The runner launches each item in turn through ``engine.launch`` (its job file, its lock and its budget
  gate: an item never spends more than the person confirmed for it) and waits for its final status before the next;
  a failed item does not stop the batch. A batch outlives the workbench: its state is its file, changed under its
  lock.
- **Cancelling** writes the batch's control file: the running item is cancelled through its own control and the
  items not started are marked cancelled.

**What a confirmation binds** (the batch audit's B20-01, 2026-10-20). Starting a batch freezes its approval: each
request's command (by its sha256) with the budget its command line gives, and the total the person confirmed. The
approval's own sha256 is handed to the runner by the confirming process, on its command line, never read back from the
batch's file. Before each launch the runner checks that the approval is the one confirmed and that the request's
command is still the approved one: a request edited afterwards (its command, its budget) is not launched and needs a
new confirmation. A budget is read as the command line reads it, and a command with two ``--budget`` options is
refused (``engine.paid``).

**One runner, and recovery** (B20-02). The runner holds the batch's runner lock for its whole life: a second runner of
the same batch stops at once. A runner that starts over an item marked running (its predecessor died) follows that
item's own job to its end before going on, and a request whose folder already holds the approved command's job is that
job, not a failure. The batch is completed only when every item has a final status. Its file is replaced whole.

**One use of a confirmation** (the recheck's RB20-01, 2026-10-20). The approval binds each request to its folder and
to the batch's own folder, and the runner records each request's dispatch in the batch's ledger (``dispatched.json``,
under the batch's lock) before launching it: a confirmation launches a request once. A request found already
dispatched is followed only through the job its batch launched for it (the job's ``owner``: this batch and item); a
request moved to another folder, put back in the queue, or whose job is gone or another's, is not launched again and
needs a new confirmation (``resume``). A completed or cancelled batch is never run again. A launch whose run never
started is closed by ``engine.poll`` after its grace period ("launch not confirmed"), not launched again (RB20-02).

**A record the batch cannot roll back** (the auditor's RC20-01, 2026-10-20: emptying ``dispatched.json``, removing the
finished job and requeueing the item had dispatched one $0.50 approval twice). Each dispatch is also appended to the
runs folder's own ledger, ``<runs>/.adroit/dispatches.jsonl``, whose path the approval freezes; a request found in
either record is not launched again. The runner it launches runs only the confirmed command (``engine``). The trust
boundary is ``engine``'s: crashes, restarts and a batch's own files changing are covered; a person editing every
record by hand is not.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from pydantic import Field, field_validator

from adroit.core.config import run_environment as _run_environment
from adroit.core.config import PROJECT_ROOT, launched
from adroit.core.state import StrictModel
from adroit.orchestrator.runs import slug, unique_folder
from adroit.ui import engine

DRAFT, BATCH, CONTROL, RUNNER_LOCK = ".adroit/batch_draft.json", "batch.json", "control.json", ".runner.lock"
LEDGER = "dispatched.json"               # each approved request's one dispatch (module docstring, RB20-01)
DISPATCHES = ".adroit/dispatches.jsonl"  # the runs folder's append-only record of every dispatch (RC20-01)
POLL_SECONDS = 10.0


class BatchItem(StrictModel):
    """One request of a batch: its command, its prepared folder, its title and the budget confirmed for it."""
    title: str
    command: list[str]
    folder: str
    budget_usd: float = 0.0
    command_sha256: str = ""                # the command as added (``command_sha256``)
    status: str = "queued"                  # queued, running, or a job's final status (engine.DONE)
    error: str = ""


class Batch(StrictModel):
    """Several requests run one after another (module docstring)."""
    title: str
    folder: str
    created: str
    items: list[BatchItem] = Field(default_factory=list)
    budget_usd: float = 0.0                 # the requests' total, which the person confirmed
    approval: dict = Field(default_factory=dict)     # frozen at the start (module docstring)
    approval_sha256: str = ""                # shown to the person; the runner takes it from its command line
    status: str = "running"                 # running, completed (every item reached a final status), cancelled,
    pid: int = 0                             # refused (the approval is not the one confirmed), interrupted
    finished: str = ""
    acknowledged: bool | None = None         # its runner has started (``run``); None: a batch from before (RC21-05)
    spawned: str = ""                        # when its runner was last started (``start``, ``resume``)
    generation: int = 0                      # each start or resume of its runner (recovery binds to it: RV22-03)
    note: str = ""                           # why it stopped where no runner said
    # the directory settings its start read, as absolute paths, given to its runner at each start and so to each run it
    # launches (``engine.Job.directories``; an operating-conditions audit's IE-01, 2026-11-10); absent from a batch
    # from before, whose runner is given its launcher's own
    directories: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)

    @field_validator("created")
    @classmethod
    def _created(cls, value: str) -> str:
        return engine.moment(value)                # each time checked as a run's is (NP17-03)

    @field_validator("spawned", "finished")
    @classmethod
    def _optional(cls, value: str) -> str:
        return engine.moment(value, empty=True)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


command_sha256 = engine.command_sha256          # a command's identity: the sha256 of its words, in order


def _digest(approval: dict) -> str:
    return hashlib.sha256(json.dumps(approval, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --- the draft --------------------------------------------------------------------------------------------------

def _draft_lock(root: Path):
    """The draft's lock (``<runs>/.adroit``, made if absent)."""
    (Path(root) / ".adroit").mkdir(parents=True, exist_ok=True)
    return engine.job_lock(Path(root) / ".adroit")


def draft(root: Path) -> list[BatchItem]:
    """The requests waiting to be started as a batch."""
    path = Path(root) / DRAFT
    return [BatchItem(**x) for x in json.loads(path.read_text())] if path.exists() else []


def draft_listing(root: Path) -> tuple[list[BatchItem], str]:
    """(the draft's requests, ""), or ([], why the draft cannot be read): for the batch page, which names it and
    offers nothing to start (the consolidation plan's M3). Adding to a draft that cannot be read is refused
    (``draft`` raises), never written over."""
    try:
        return draft(root), ""
    except (OSError, ValueError, TypeError) as error:
        from adroit.core.durable import reason
        return [], f"the batch draft, {DRAFT}, cannot be read ({reason(error)}): repair it or move it aside"


def _write_draft(root: Path, items: list[BatchItem]) -> None:
    from adroit.core.durable import write_atomic
    write_atomic(Path(root) / DRAFT, json.dumps([x.model_dump() for x in items], indent=1))


def add_to_draft(root: Path, command: list[str], folder: Path, title: str, budget: float = 0.0) -> BatchItem:
    """Add a prepared request to the draft; a paid request needs its budget confirmed now, as a launch would."""
    from adroit.ui.forms import output_clash
    cost = engine.paid(command)
    if cost > 0 and cost > budget + 1e-9:
        raise engine.BudgetNotConfirmed(f"this run may spend ${cost:.2f}; the person confirmed ${budget:.2f}")
    item = BatchItem(title=title, command=command, folder=str(Path(folder).resolve()), budget_usd=cost,
                     command_sha256=command_sha256(command))
    with _draft_lock(root):
        items = draft(root)
        clash = output_clash(command, [x.command for x in items])
        if clash:                             # two requests writing one file (WA-05)
            raise ValueError(clash)
        _write_draft(root, [*items, item])
    return item


class DraftChanged(ValueError):
    """The draft is not the one a page showed (NP17-02): nothing was removed or started, and the draft is kept."""


def _identity(item: BatchItem) -> tuple[str, str]:
    """A draft request's identity: its prepared folder (each request has its own) and its command's sha256."""
    return item.folder, item.command_sha256


def draft_digest(items: list[BatchItem]) -> str:
    """The identity of a draft as shown: its requests in order, each by its identity and its budget (NP17-02)."""
    return hashlib.sha256(json.dumps([[*_identity(x), x.budget_usd] for x in items]).encode()).hexdigest()


def remove_from_draft(root: Path, item: BatchItem) -> None:
    """Remove ``item``, the request a page showed, by its identity (never by its place in the draft, which another
    page or wizard may have changed: the non-physics audit's NP17-02, 2026-11-17, where a stale page's Remove had
    removed another request). Raises DraftChanged if the draft no longer holds it."""
    with _draft_lock(root):
        items = draft(root)
        kept = [x for x in items if _identity(x) != _identity(item)]
        if len(kept) == len(items):
            raise DraftChanged(f"{item.title}: no longer in the draft (removed or changed elsewhere); the page shows "
                               "the draft as it is now")
        _write_draft(root, kept)


# --- a batch ----------------------------------------------------------------------------------------------------

def load(folder: Path) -> Batch:
    return Batch.model_validate_json((Path(folder) / BATCH).read_text())


def _save(batch: Batch) -> None:
    """Replace the batch's file whole (never half-written, B20-02: ``durable.write_atomic``)."""
    from adroit.core.durable import write_atomic
    write_atomic(Path(batch.folder) / BATCH, batch.model_dump_json(indent=1))


def _update(folder: Path, index: int | None = None, **fields) -> Batch:
    """Change the batch's fields (or one item's) as it is now, under its lock."""
    with engine.job_lock(folder):
        batch = load(folder)
        if index is None:
            batch = batch.model_copy(update=fields)
        else:
            items = list(batch.items)
            items[index] = items[index].model_copy(update=fields)
            batch = batch.model_copy(update={"items": items})
        _save(batch)
        return batch


def start(root: Path, title: str, confirmed_budget: float = 0.0, popen=subprocess.Popen, shown: str = "") -> Batch:
    """The draft as a batch in its own folder, its approval frozen and its runner started with the approval's digest;
    the draft is emptied. Raises ValueError for an empty draft, an invalid budget, a request changed since it was
    added or two whose file outputs clash (``forms.output_clash``), and BudgetNotConfirmed if the batch's total exceeds
    what the person confirmed (module docstring). ``shown``: the ``draft_digest`` of the draft the person confirmed
    (the batch page's); a draft changed since, even to the same total, raises DraftChanged and is kept (NP17-02: a
    stale page had started another set of requests than it showed)."""
    if not math.isfinite(confirmed_budget) or confirmed_budget < 0:
        raise ValueError("a confirmed budget is a finite number of dollars, at least 0")
    with _draft_lock(root):
        items = draft(root)
        if shown and draft_digest(items) != shown:
            raise DraftChanged("the draft has changed since this page showed it (a request added or removed "
                               "elsewhere): nothing was started; review the requests as they are now and confirm again")
        if not items:
            raise ValueError("the batch is empty: add requests from the wizards first")
        from adroit.ui.forms import output_clash
        for i, item in enumerate(items):      # a file written since the request was added, or shared (WA-05)
            clash = output_clash(item.command, [x.command for x in items[:i]])
            if clash:
                raise ValueError(f"{item.title}: {clash}")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        folder = unique_folder(Path(root) / "batches", f"{stamp}_batch_{slug(title)[:60]}")
        approval = _approval(items, confirmed_budget, folder.resolve(), Path(root).resolve() / DISPATCHES)
        folder.mkdir(parents=True, exist_ok=True)
        batch = Batch(title=title, folder=str(folder.resolve()), created=_now(), items=items,
                      budget_usd=approval["total_usd"], approval=approval, approval_sha256=_digest(approval),
                      acknowledged=False, spawned=_now(), generation=1, directories=launched())
        _save(batch)
        _write_draft(root, [])
    return _spawn(batch, popen)


def _spawn(batch: Batch, popen) -> Batch:
    """Start the batch's runner with its approval's digest and this start's generation, and record its process; a
    runner that cannot be started leaves the batch interrupted with the reason, its requests kept, to be resumed with
    a new confirmation (the recheck's RC21-05, 2026-10-22: it had stayed running for ever, its draft emptied and its
    resume refused). Both writes belong to this start (``_for_start``): a launcher returning late, after its start
    was recovered, resumed or cancelled, changes nothing (the RV22 audit's RX22-07, 2026-10-22: a late failure had
    marked a newer live run interrupted, and a cancelled batch resumable)."""
    folder = Path(batch.folder)
    try:
        process = popen(["nice", "-n", "10", sys.executable, "-m", "adroit.ui.batch", batch.folder,
                         batch.approval_sha256, str(batch.generation)], cwd=str(PROJECT_ROOT),
                        start_new_session=True, env=_run_environment(batch.directories),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except BaseException as error:
        _for_start(folder, batch.generation, status="interrupted", finished=_now(),
                   note=f"its runner could not be started: {type(error).__name__}: {error}"[:300])
        raise
    return _for_start(folder, batch.generation, pid=process.pid)


def _for_start(folder: Path, generation: int, **fields) -> Batch:
    """Change the batch's ``fields`` under its lock only while the start of ``generation`` is still the batch's own
    and unconfirmed: running, of that generation, not acknowledged by its runner and held by none (a runner's own
    PID, recorded with its acknowledgement, stands); else the batch as it is."""
    with engine.job_lock(folder):
        batch = load(folder)
        if batch.status != "running" or batch.generation != generation or batch.acknowledged \
                or _runner_held(folder):
            return batch
        batch = batch.model_copy(update=fields)
        _save(batch)
        return batch


def _approval(items: list[BatchItem], confirmed_budget: float, batch_folder: Path, ledger: Path,
              checked: bool = True) -> dict:
    """The frozen approval: the batch's folder, the runs folder's dispatch ledger, and each request's command
    identity, its folder and the budget its command line gives (recomputed now, never taken from the draft's numbers),
    within the confirmed total; with ``checked``, each request as it was added to the draft."""
    approved = []
    for item in items:
        sha, cost = command_sha256(item.command), engine.paid(item.command)
        if checked and (sha != item.command_sha256 or abs(cost - item.budget_usd) > 1e-9):
            raise ValueError(f"the request {item.title!r} changed after it was added to the draft: add it again")
        approved.append({"command_sha256": sha, "budget_usd": cost, "folder": str(Path(item.folder).resolve())})
    total = sum(a["budget_usd"] for a in approved)
    if total > confirmed_budget + 1e-9:
        raise engine.BudgetNotConfirmed(f"this batch may spend ${total:.2f}; the person confirmed "
                                        f"${confirmed_budget:.2f}")
    return {"batch": str(Path(batch_folder)), "ledger": str(ledger), "items": approved, "total_usd": total,
            "confirmed_usd": confirmed_budget}


def cancel(folder: Path) -> None:
    """Ask the batch to stop: the running item is cancelled, the rest are not started. With no runner holding the
    batch (it never started, or died), the batch is closed here (RC21-05): a running request's job is asked to stop
    (or keeps the final status it reached), the queued ones are cancelled, and the batch is cancelled; a runner
    starting later finds it closed. No request is launched."""
    folder = Path(folder)
    from adroit.core.durable import write_atomic
    write_atomic(folder / CONTROL, json.dumps({"cancel": True}))
    if _runner_held(folder):
        return
    with engine.job_lock(folder):
        batch = load(folder)
        if batch.status not in ("running", "interrupted", "refused"):
            return
        items = []
        for item in batch.items:
            status = item.status
            if status == "running":
                job = _job_as_found(Path(item.folder))
                if job is not None and job.status not in engine.DONE:
                    engine.cancel(Path(item.folder))
                status = job.status if job is not None and job.status in engine.DONE else "cancelled"
            items.append(item.model_copy(update={"status": "cancelled" if status == "queued" else status}))
        _save(batch.model_copy(update={"items": items, "status": "cancelled", "finished": _now(),
                                       "note": "cancelled with no runner holding the batch"}))


def _job_as_found(folder: Path):
    """A running item's job (``engine.poll``), None where its folder has no job record at all; where one is there but
    cannot be read (a link leading nowhere among them), its run may be going: it is asked to stop, and None (the auditor's
    DM recheck, DN-01: it had read as no job, and the item was marked cancelled with nothing asked of its run)."""
    from adroit.core.durable import absent, write_atomic
    if absent(folder / engine.JOB):
        return None
    try:
        return engine.poll(folder)
    except (OSError, ValueError):
        write_atomic(folder / engine.CONTROL, json.dumps({"cancel": True, "at": _now()}))
        return None


def cancelled(folder: Path) -> bool:
    """Whether the batch has been asked to stop; a control file that cannot be read stops it too, never permission
    to dispatch the next request (``engine.control_unreadable``; the consolidation plan's M3: it had raised in the
    runner, which then left the batch running with no runner)."""
    return engine.cancelled(folder)


def resume(folder: Path, confirmed_budget: float = 0.0, popen=subprocess.Popen) -> Batch:
    """Start a stopped batch's runner again (one that was interrupted or refused) with a new confirmation: the
    approval is frozen again from the requests as they now are, and the items not finished run (module docstring)."""
    if not math.isfinite(confirmed_budget) or confirmed_budget < 0:
        raise ValueError("a confirmed budget is a finite number of dollars, at least 0")
    with engine.job_lock(Path(folder)):
        batch = load(folder)
        if batch.status not in ("interrupted", "refused"):
            raise ValueError(f"the batch is {batch.status}: only an interrupted or refused batch is resumed")
        ledger = batch.approval.get("ledger") or str(Path(batch.folder).resolve().parent.parent / DISPATCHES)
        approval = _approval(batch.items, confirmed_budget, Path(batch.folder), Path(ledger), checked=False)
        batch = batch.model_copy(update={"approval": approval, "approval_sha256": _digest(approval),
                                         "status": "running", "finished": "", "pid": 0, "acknowledged": False,
                                         "spawned": _now(), "note": "", "generation": batch.generation + 1,
                                         "directories": batch.directories or launched()})
        _save(batch)
    return _spawn(batch, popen)


class RunnerBusy(RuntimeError):
    """Another runner holds the batch."""


def run(folder: Path, approval_sha256: str, launch=engine.launch, poll=engine.poll, stop=engine.cancel,
        sleep=time.sleep, generation: int | None = None) -> Batch:
    """Run the batch's items one after another (module docstring), under its runner lock; the batch's final
    status when it ends. A runner of another start (``generation``, as its launcher gave it; none: a batch from before
    generations, 0) leaves the batch as it is (RX22-07, RY23-04: one delayed past a resume had acknowledged the new
    start and marked it refused); its approval is checked before it acknowledges. Raises RunnerBusy if another
    runner holds it."""
    folder = Path(folder)
    with (folder / RUNNER_LOCK).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RunnerBusy(f"{folder}: another runner is running this batch") from None
        batch = load(folder)
        if batch.status != "running":          # completed or cancelled never run again (RB20-01); interrupted or
            return batch                       # refused only through resume's new confirmation (RC21-05)
        if batch.generation != (generation if generation is not None else 0):
            return batch       # a runner of another start; one without a generation runs only a batch from before
            #                    generations (0): the RX22 audit's RY23-04, 2026-10-23, a delayed old command line had
            #                    acknowledged a resumed batch and marked it refused
        if batch.acknowledged is False and _start_lost(batch):         # its start acknowledged within the bound,
            return _update(folder, status="interrupted", finished=_now(), note=START_NOT_CONFIRMED)  # (RR22-04)
        if not batch.approval or _digest(batch.approval) != approval_sha256 or \
                batch.approval.get("batch") != str(folder.resolve()) or \
                len(batch.approval.get("items", [])) != len(batch.items) or \
                sum(a["budget_usd"] for a in batch.approval["items"]) > batch.approval["confirmed_usd"] + 1e-9:
            return _update(folder, status="refused", finished=_now())   # checked before it acknowledges (RY23-04)
        if batch.acknowledged is False:                                 # with its own process (RR22-04)
            batch = _update(folder, acknowledged=True, pid=os.getpid())
        for index, item in enumerate(batch.items):
            if cancelled(folder):
                break
            if item.status not in engine.DONE:
                owner = f"{folder.resolve()}#{index}#{approval_sha256}"
                approved = {**batch.approval["items"][index], "ledger": batch.approval.get("ledger", "")}
                _run_item(folder, index, item, approved, owner, launch, poll, stop, sleep)
        return _finish(folder)


def _run_item(folder: Path, index: int, item: BatchItem, approved: dict, owner: str, launch, poll, stop,
              sleep) -> None:
    """One request: launched once under its confirmation (``_reserve``), or followed to its end through its own job."""
    item_folder = Path(item.folder)
    if str(item_folder.resolve()) != approved.get("folder") or command_sha256(item.command) != \
            approved["command_sha256"] or engine.paid(item.command) > approved["budget_usd"] + 1e-9:
        _update(folder, index, status="failed", error="the request changed after the batch was confirmed (its "
                "command, budget or folder): confirm a new batch to run it")
        return
    try:
        reserved = _reserve(folder, owner, item_folder, approved["ledger"])
    except DispatchUnknown as error:          # whether it was sent is not known: it is not sent (DN-01)
        _update(folder, index, status="failed", error=str(error)[:300])
        return
    if not reserved:                          # dispatched already under this confirmation
        _follow(folder, index, item, owner, poll, stop, sleep, "this confirmation already launched the request")
        return
    try:
        launch(item.command, item_folder, item.title, confirmed_budget=approved["budget_usd"], owner=owner)
    except engine.JobExists:
        _follow(folder, index, item, owner, poll, stop, sleep, "the folder already held a job")
        return
    except (engine.BudgetNotConfirmed, OSError, ValueError) as error:
        _update(folder, index, status="failed", error=str(error)[:300])
        return
    _update(folder, index, status="running")
    _update(folder, index, status=_wait(folder, item_folder, poll, stop, sleep))


UNKNOWN = "whether this request was already sent is not known, so it is not sent"


class DispatchUnknown(ValueError):
    """A record of a batch's dispatches that is there but cannot be read: whether a request was sent is not known, so
    it is not sent (the auditor's DM recheck, DN-01, 2026-11-08: a record that was a link leading nowhere had read as no
    dispatch at all, and one that could not be read had raised in the runner)."""


def _reserve(folder: Path, owner: str, item_folder: Path, ledger: str = "") -> bool:
    """Record a request's dispatch under this confirmation before its launch, in the batch's ledger and in the runs
    folder's (``ledger``, appended), under their locks; False if either holds it already (the confirmation has been
    used for it: RB20-01, RC20-01). ``DispatchUnknown`` where either is there but cannot be read."""
    with engine.job_lock(folder):
        path = Path(folder) / LEDGER
        used = _used(path)
        if owner in used or (ledger and _dispatched(Path(ledger), owner)):
            return False
        record = {"owner": owner, "folder": str(item_folder.resolve()), "at": _now()}
        if ledger:
            Path(ledger).parent.mkdir(parents=True, exist_ok=True)
            with engine.job_lock(Path(ledger).parent), Path(ledger).open("a") as stream:
                stream.write(json.dumps(record) + "\n")
        used[owner] = {k: v for k, v in record.items() if k != "owner"}
        from adroit.core.durable import write_atomic
        write_atomic(path, json.dumps(used, indent=1))
        return True


def _used(path: Path) -> dict:
    """The batch's record of its dispatches (``LEDGER``): {} where nothing at all is at its path (``durable.absent``);
    ``DispatchUnknown`` where an entry there cannot be read (a link leading nowhere among them) or is not that record."""
    from adroit.core.durable import absent, linked, reason
    if absent(path):
        return {}
    try:
        used = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise DispatchUnknown(f"{UNKNOWN}: the batch's dispatch record ({LEDGER}) cannot be read "
                              f"({linked(path)}{reason(error)})") from error
    if not isinstance(used, dict):
        raise DispatchUnknown(f"{UNKNOWN}: the batch's dispatch record ({LEDGER}) is not a record of dispatches")
    return used


def _dispatched(ledger: Path, owner: str) -> bool:
    """Whether the runs folder's ledger records a dispatch for ``owner`` (a line that is not JSON is read as one:
    a damaged record never permits a second dispatch); ``DispatchUnknown`` where the ledger is there but cannot be
    read (a link leading nowhere among them: it had read as no ledger, DN-01)."""
    from adroit.core.durable import absent, linked, reason
    if absent(ledger):
        return False
    try:
        text = ledger.read_text()
    except OSError as error:
        raise DispatchUnknown(f"{UNKNOWN}: the runs folder's dispatch record ({ledger.name}) cannot be read "
                              f"({linked(ledger)}{reason(error)})") from error
    for line in text.splitlines():
        try:
            if json.loads(line).get("owner") == owner:
                return True
        except (ValueError, AttributeError):
            if owner in line:
                return True
    return False


def _follow(folder: Path, index: int, item: BatchItem, owner: str, poll, stop, sleep, why: str) -> None:
    """A request already dispatched: followed to its end through the job its batch launched for it (this batch and
    item, under any of its confirmations), else failed, needing a new confirmation; never launched again."""
    if _owned(Path(item.folder), owner, item.command):
        _update(folder, index, status="running", error=item.error)
        _update(folder, index, status=_wait(folder, Path(item.folder), poll, stop, sleep),
                error=item.error + f"{why}; its own job was followed to its end")
        return
    _update(folder, index, status="failed", error=f"{why}, and the folder holds no job this batch launched for it: "
            "confirm a new batch to run it")


def _owned(item_folder: Path, owner: str, command: list[str]) -> bool:
    """Whether the folder's job is the one this batch launched for this item (``owner``'s batch and item) for this
    command."""
    try:
        job = engine.load(item_folder)
    except (OSError, ValueError):
        return False
    item = owner.rsplit("#", 1)[0]                                   # "<batch folder>#<item>": a path may hold "#"
    return job.command == list(command) and bool(job.owner) and job.owner.rsplit("#", 1)[0] == item


def _finish(folder: Path) -> Batch:
    """The batch's end: items not started are cancelled if it was cancelled; completed only when every item has a
    final status."""
    batch = load(folder)
    stopped = cancelled(folder)
    for index, item in enumerate(batch.items):
        if item.status == "queued" and stopped:
            batch = _update(folder, index, status="cancelled")
    done = all(item.status in engine.DONE for item in batch.items)
    why = {"note": engine.control_unreadable(folder)} if stopped and engine.control_unreadable(folder) else {}
    return _update(folder, status="cancelled" if stopped else "completed" if done else "interrupted", finished=_now(),
                   **why)


def _wait(batch_folder: Path, item_folder: Path, poll, stop, sleep) -> str:
    """The item's final status, cancelling it if the batch is cancelled meanwhile."""
    asked = False
    while True:
        job = poll(item_folder)
        if job.status in engine.DONE:
            return job.status
        if cancelled(batch_folder) and not asked:
            stop(item_folder)
            asked = True
        sleep(POLL_SECONDS)


def batches(root: Path) -> list[Batch]:
    """Every readable batch under ``<runs>/batches``, newest first (``listing``)."""
    return listing(root)[0]


def listing(root: Path):
    """(every readable batch under ``<runs>/batches``, newest first, one whose runner has died without a word marked
    interrupted (B20-02), so that it can be resumed with a new confirmation; each batch record that cannot be read,
    named with why: ``durable.read_each``, the consistency audit's CA-07, 2026-10-24: one truncated batch.json had
    stopped the listing). Opening a batch (``load``) stays strict."""
    from adroit.core.durable import read_each
    base = Path(root) / "batches"
    files = sorted(f / BATCH for f in base.iterdir() if (f / BATCH).exists()) if base.is_dir() else []
    found, damaged = read_each(files, lambda path: _checked(path.parent))
    return sorted(found, key=lambda b: b.created, reverse=True), damaged


def _checked(folder: Path) -> Batch:
    """The batch, interrupted where its runner died (its process gone, or, once acknowledged, no runner holding the
    batch's lifetime lock: the runner holds it from its acknowledgement to its final status), or where none
    acknowledged its start within the bound (RC21-05: a runner that never started had left it running for ever;
    RR22-04: an acknowledged runner that died with its launcher before the launcher recorded its PID had too). The
    state is read again under the batch's lock before it is changed, so a runner's final status is never
    overwritten."""
    batch = load(folder)
    if batch.status != "running" or _runner_held(folder):
        return batch
    if batch.acknowledged or (batch.pid and not engine._alive(batch.pid)):
        return _interrupt(folder, "", generation=batch.generation)
    if _start_lost(batch):
        return _interrupt(folder, START_NOT_CONFIRMED, generation=batch.generation)
    return batch


def _interrupt(folder: Path, note: str, generation: int | None = None) -> Batch:
    """Mark a running batch interrupted with ``note``, under its lock, only if what was observed still holds: it is
    running, it is the same start of its runner (``generation``, when given), and no runner holds it (a new runner
    takes the lifetime lock, without waiting, before it acknowledges). The re-audit's RV22-03, 2026-10-22: a listing
    that had seen a dead runner, delayed while another listing recovered the batch and it was resumed, had marked the
    new live run interrupted."""
    with engine.job_lock(folder):
        batch = load(folder)
        if batch.status != "running" or (generation is not None and batch.generation != generation) \
                or _runner_held(folder):
            return batch
        batch = batch.model_copy(update={"status": "interrupted", "finished": _now(), "note": note})
        _save(batch)
        return batch


START_NOT_CONFIRMED = (f"start not confirmed: its runner did not start within {engine.LAUNCH_GRACE_SECONDS:g} s; "
                       "resume it with a new confirmation")


def _start_lost(batch: Batch) -> bool:
    """Whether a batch whose runner has not acknowledged its start is past the bound (``engine.LAUNCH_GRACE_SECONDS``
    from its runner's start; from its creation for a batch from before acknowledgements whose PID is 0)."""
    if batch.acknowledged is None and batch.pid:
        return False
    if batch.acknowledged:
        return False
    since = batch.spawned or batch.created
    return (datetime.now() - datetime.fromisoformat(since)).total_seconds() > engine.LAUNCH_GRACE_SECONDS


def _runner_held(folder: Path) -> bool:
    """Whether a runner holds the batch's runner lock now."""
    path = Path(folder) / RUNNER_LOCK
    if not path.exists():
        return False
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock, fcntl.LOCK_UN)
        return False


if __name__ == "__main__":
    run(Path(sys.argv[1]), sys.argv[2], generation=int(sys.argv[3]) if len(sys.argv) > 3 else None)

"""Deleting a personal model, a study, or a run that ended without one (the owner, 2026-11-18,
the post-review changes item 3; a run, 2026-11-19, the minor repair record of 2026-11-19 item 4).

- **A study** is deleted with every study inside its folder: its promotions and reanalyses, which are made there.
- **A run that ended without a study** (failed, cancelled or stopped at its budget) is deleted with its folder: its
  log and everything it wrote. A folder that holds a study is not one: that study is deleted instead.
- **A model** is deleted with all its revisions and every study that used any of them, each with the studies inside
  its folder; its requests in the batch draft are removed. The source files it cited stay in the library's
  ``assets/``, which other models and sessions share.

Each is shown first (``plan_study``, ``plan_run``, ``plan_model``): a confirmation window names what will be deleted, and the delete
goes ahead only on the plan the person confirmed. It is refused where the plan has changed since.

**Kept:** every deleted run's money records: its paid ledger and the files beside it (its mark, a recovered original,
a notice of an unjournalled request), its record of a session's requests, and its job record. They are moved into
``<runs>/.adroit/deleted/<when>_<what>/kept/``, at their paths in the runs folder, beside a record of what was deleted
(``deleted.json``). The money was spent, and a session's spending is still found from them (``model_intake``).

**Refused while running:** nothing is deleted while a run that would lose its folder, or that uses the model, is
running (a run's calculation left running after its runner ended included), or while a batch still to run uses the model, or while a study's folder is being published.

**Refused for a batch's run** (the auditor's post-review audit, PR-02): a study that ran in a batch is not deleted: the
batch counts its spending from that run's folder, so deleting it would lower the batch's total. The batch's reader is
not deletion-aware yet (deferred).

**Held through the removal** (PR-04): each study folder's publication lock (``durable.publishing``) and, for a model,
the library's lock are taken first; the plan is made again under them and must be the one confirmed; each study folder
is then moved aside (one rename) and the moved tree must hold exactly the confirmed studies, and nothing in it may be
running or publishing (a run or a publication begun inside after the plan, before its study record: the auditor's
post-review recheck, PS-05), else it is moved back and nothing is deleted; only then are its money records kept and
the rest removed. A run or publication that begins after the move writes at the old path, outside what is removed.
While any batch record cannot be read, nothing is deleted (PS-04).
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from nicegui import ui
from pydantic import Field

from adroit.core.state import StrictModel

DELETED = Path(".adroit") / "deleted"
KEPT_NOTE = ("Its paid-call records are kept (in the runs folder's .adroit/deleted); everything else is deleted. This "
             "cannot be undone.")


class Plan(StrictModel):
    """What a delete would remove, as the confirmation window shows it."""
    kind: Literal["model", "study", "run"]
    name: str
    model_id: str = ""
    revisions: int = 0
    studies: list[str] = Field(default_factory=list)       # every study folder deleted, children included
    runs: list[str] = Field(default_factory=list)          # a run deleted that holds no study (its folder)
    titles: dict[str, str] = Field(default_factory=dict)   # their titles, by folder
    running: list[str] = Field(default_factory=list)       # why it cannot be deleted now
    blocked: list[str] = Field(default_factory=list)       # why it cannot be deleted (a batch's run: PR-02)
    batch_items: list[str] = Field(default_factory=list)   # the batch draft's requests that name the model


class Deleted(StrictModel):
    """The record of a delete (``deleted.json``), beside the money records it kept."""
    kind: Literal["model", "study", "run"]
    name: str
    deleted_at: str
    model_id: str = ""
    revisions: int = 0
    studies: list[str] = Field(default_factory=list)       # relative to the runs folder
    runs: list[str] = Field(default_factory=list)          # relative to the runs folder
    kept: list[str] = Field(default_factory=list)          # relative to the record's folder
    batch_items: list[str] = Field(default_factory=list)


def _money(name: str) -> bool:
    """A money record by its name: a paid ledger and what is kept beside it, a session's request record."""
    return (name == "paid.jsonl" or name.startswith("paid.jsonl.") or name.startswith(".unjournalled-")
            or name == "paid_requests.json")


def _inside(folder: Path, other: Path) -> bool:
    return folder == other or folder in other.parents


def _studies_in(folder: Path) -> list[Path]:
    """Every study folder in ``folder``, itself first (links not followed)."""
    found = []
    for at, _dirs, files in os.walk(folder):
        if "study.json" in files:
            found.append(Path(at))
    return sorted(found, key=lambda p: (len(p.parts), str(p)))


def _outermost(folders: list[Path]) -> list[Path]:
    return [f for f in folders if not any(o != f and _inside(o, f) for o in folders)]


def _listing(root: Path) -> dict[str, object]:
    """Every readable study under ``root`` as the Studies page lists it (``studies.tree``), by its folder."""
    from adroit.orchestrator import studies
    return {str(Path(s.folder).resolve()): s for _, s in studies.tree(root)}


def _titles(listed: dict, folders: list[Path]) -> dict[str, str]:
    return {str(f): getattr(listed.get(str(f)), "title", f.name) for f in folders}


def _calculation_left(calculation: int, started) -> str:
    """Why a run's calculation still counts as running though its run has ended, or "": its process group still runs,
    proven the run's (``engine.calculation_alive``), or a live group of its number that cannot be proven the run's or
    another's (``engine.calculation_unproven``), which is never taken as ended (MF-01, the auditor's audit of 2026-11-19: a
    failed run's calculation outlives its runner, and its folder was deleted under it)."""
    from types import SimpleNamespace

    from adroit.ui import engine
    if not calculation:
        return ""
    job = SimpleNamespace(calculation=calculation, calculation_started=started)
    alive = engine.calculation_alive(job)
    if alive:
        return (f"its calculation still runs (processes {', '.join(map(str, alive))}); cancel it on Activity, then "
                "delete once it has ended")
    unproven = engine.calculation_unproven(job)
    if unproven:
        return (f"processes {', '.join(map(str, unproven))} of its calculation's group still run, not proven its own "
                "or another's; delete once they have ended")
    return ""


def _running(root: Path, touches) -> list[str]:
    """Each job that ``touches`` (its folder, its command) names and that still runs, by title: its run (status
    running), or its calculation after its run has ended (``_calculation_left``), whichever run it is in the folder
    deleted, the one chosen or one inside it (MF-01). Refused while either runs."""
    from adroit.ui import engine
    listed, _ = engine.listing(root)
    now, _ = engine.polled(listed)
    found = []
    for job in now:
        if not touches(job):
            continue
        if job.status == "running":
            found.append(f"{job.title} is running")
        elif left := _calculation_left(job.calculation, job.calculation_started):
            found.append(f"{job.title}: {left}")
    return found


def _study_folder(root: Path, folder: Path) -> Path:
    """``folder`` as a study folder inside the runs folder, refused otherwise."""
    root, folder = Path(root).resolve(), Path(folder)
    if folder.is_symlink():
        raise ValueError(f"{folder} is a link, not a study's folder")
    folder = folder.resolve()
    if folder == root or root not in folder.parents or not (folder / "study.json").is_file():
        raise ValueError(f"{folder} is not a study in {root}")
    return folder


def _batch_runs(root: Path, folders: list[Path], titles: dict[str, str]) -> list[str]:
    """Each of ``folders`` (or a run inside one) that ran in a batch, said: the batch counts its spending from that
    folder (module docstring, PR-02)."""
    from adroit.ui import batch
    found, damaged = batch.listing(root)
    if damaged:                  # which runs it holds is not known: none is deleted (the auditor's post-review recheck, PS-04)
        return [f"a batch record cannot be read ({d.path}: {d.why}), so whether a run here counts in a batch's "
                "spending is not known; repair or move that record first" for d in damaged]
    out = []
    for b in found:
        for item in b.items:
            at = Path(item.folder).resolve()
            hit = next((f for f in folders if _inside(f, at)), None)
            if hit is not None:
                out.append(f"{titles.get(str(hit), hit.name)} ran in the batch “{b.title}”, which counts its spending "
                           "from its folder: deleting it would lower the batch's total")
    return list(dict.fromkeys(out))


def plan_study(root: Path, folder: Path) -> Plan:
    """A study's delete: it and the studies inside its folder; refused while a run there runs, or for a batch's run."""
    folder = _study_folder(root, folder)
    inside = _studies_in(folder)
    running = _running(root, lambda job: _inside(folder, Path(job.folder).resolve()))
    titles = _titles(_listing(root), inside)
    return Plan(kind="study", name=titles[str(folder)], studies=[str(f) for f in inside], titles=titles,
                running=running, blocked=_batch_runs(root, [folder], titles))


def _run_folder(root: Path, folder: Path) -> Path:
    """``folder`` as a run's folder inside the runs folder that holds no study, refused otherwise: a folder that holds
    one is the study's to delete (``plan_study``)."""
    root, folder = Path(root).resolve(), Path(folder)
    if folder.is_symlink():
        raise ValueError(f"{folder} is a link, not a run's folder")
    folder = folder.resolve()
    if folder == root or root not in folder.parents or not (folder / "job.json").is_file():
        raise ValueError(f"{folder} is not a run in {root}")
    if _studies_in(folder):
        raise ValueError("this run's folder holds a study: delete the study instead (from Studies)")
    return folder


def plan_run(root: Path, folder: Path) -> Plan:
    """A run's delete, for a run that ended without a study: its folder; refused while it, or any run inside its
    folder, runs or has a calculation that still runs after its run ended (``_running``, MF-01), or for a batch's
    run."""
    from adroit.ui import engine
    folder = _run_folder(root, folder)
    job = engine.load(folder)
    running = _running(root, lambda other: _inside(folder, Path(other.folder).resolve()))
    titles = {str(folder): job.title}
    return Plan(kind="run", name=job.title, runs=[str(folder)], titles=titles, running=running,
                blocked=_batch_runs(root, [folder], titles))


def _model_name(catalog, model_id: str) -> tuple[str, int]:
    """A model's name (its latest readable revision's) and how many revision files it has."""
    from adroit.library.personal import TOKEN
    if not TOKEN.fullmatch(model_id):
        raise ValueError("invalid model identifier")
    folder = catalog.root / "models" / model_id
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError(f"model {model_id[:8]} is not in the personal library")
    files = sorted((folder / "revisions").glob("*.json"))
    found, _ = catalog.listing()
    named = [r for r in found if r.model_id == model_id]
    return (named[-1].spec.name if named else f"model {model_id[:8]}"), len(files)


def plan_model(root: Path, model_id: str, catalog=None) -> Plan:
    """A model's delete: its revisions, every study that used any of them (with the studies inside its folder), its
    batch-draft requests; refused while a run uses it or would lose its folder, or a batch still to run uses it."""
    from adroit.library.personal import Catalog
    from adroit.ui import batch
    catalog = catalog or Catalog()
    root = Path(root).resolve()
    name, revisions = _model_name(catalog, model_id)
    prefix = f"catalog:{model_id}@"
    listed = _listing(root)
    used = [Path(f) for f, s in listed.items() if any(r.startswith(prefix) for r in s.model_references)]
    tops = _outermost(used)
    every = [f for top in tops for f in _studies_in(top)]
    names = lambda command: any(prefix in str(part) for part in command)           # noqa: E731
    running = _running(root, lambda job: names(job.command) or any(_inside(t, Path(job.folder).resolve())
                                                                    for t in tops))
    found, _ = batch.listing(root)
    running += [f"the batch {b.title} still has a request using it" for b in found if b.status == "running"
                and any(item.status == "queued" and names(item.command) for item in b.items)]
    drafted = [item.title for item in batch.draft(root) if names(item.command)]
    titles = _titles(listed, every)
    return Plan(kind="model", name=name, model_id=model_id, revisions=revisions, studies=[str(f) for f in every],
                titles=titles, running=running, blocked=_batch_runs(root, tops, titles), batch_items=drafted)


def _confirmed(plan: Plan, expected: Plan) -> None:
    """Refuse a delete while something runs, for a batch's run, or where it would remove other than the person
    confirmed."""
    if plan.blocked:
        raise ValueError("not deleted: " + "; ".join(plan.blocked) + ".")
    if plan.running:
        raise ValueError("not deleted: " + "; ".join(plan.running) + ". Wait for it to finish or stop it first.")
    if (plan.studies, plan.runs, plan.revisions, plan.batch_items) != (expected.studies, expected.runs,
                                                                       expected.revisions, expected.batch_items):
        raise ValueError("not deleted: what it would delete has changed since you confirmed; look again")


def _record_folder(root: Path, what: str) -> Path:
    from adroit.orchestrator.runs import slug
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path(root) / DELETED / f"{stamp}_{slug(what)[:60]}"
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def _keep_money(root: Path, folder: Path, record: Path, origin: Path | None = None) -> list[str]:
    """Move ``folder``'s money records into ``record``'s ``kept/`` at their paths in the runs folder (``origin``: where
    ``folder`` was before it was moved aside); copy each job record there (``job.deleted.json``, so that no listing
    reads it as a run). Returns them, relative to ``record``."""
    kept = []
    for at, _dirs, files in os.walk(folder):
        for name in files:
            source = Path(at) / name
            if source.is_symlink() or not (_money(name) or name == "job.json"):
                continue
            target = record / "kept" / ((origin or folder) / source.relative_to(folder)).relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            if name == "job.json":
                target = target.with_name("job.deleted.json")
                shutil.copy2(source, target)
            else:
                os.replace(source, target)
            kept.append(str(target.relative_to(record)))
    return sorted(kept)


@contextlib.contextmanager
def _holding(folders: list[str]):
    """Each study folder's publication lock (``durable.publishing``), not waited for, held until the delete ends: no
    publication into them meanwhile (PR-04). A folder no longer a study's is refused, never made again."""
    from adroit.core.durable import publishing
    with contextlib.ExitStack() as held:
        for folder in sorted(folders):
            if not (Path(folder) / "study.json").is_file():
                raise ValueError("not deleted: what it would delete has changed since you confirmed; look again")
            held.enter_context(publishing(Path(folder), wait=0))
        yield


def _unlink_from_parent(folder: Path, gone: list[Path], listed: dict) -> None:
    """Remove a deleted study from its parent's children, where the parent stays (``studies.forget_child``)."""
    from adroit.orchestrator import studies
    parent = getattr(listed.get(str(folder)), "parent", "")
    if parent and not any(_inside(g, Path(parent).resolve()) for g in gone):
        studies.forget_child(Path(parent), folder)


class NothingDeleted(ValueError):
    """A delete refused at its last check, everything put back: nothing was deleted, and no record of it is kept."""


CHANGED = "not deleted: what it would delete has changed since you confirmed; look again"


class DeleteStranded(ValueError):
    """A delete refused at its last check whose folder could not be moved back: a run made its old path again while it
    was moved aside. Nothing was deleted; each study as it was is kept where it was moved, named in a recovery record
    (``RECOVERY.json``) and in the message (the auditor's post-review recheck 2, PT-02)."""


PLACEHOLDER = b"ADROIT is deleting the study that was here; its folder is under .adroit/deleting until the delete ends.\n"


def _block(top: Path) -> None:
    """A placeholder file at a moved folder's old path, made only if nothing is there (``O_EXCL``): no run or
    publication can make the folder again while the delete holds it aside, so it can be moved back (PT-02).
    ``FileExistsError`` where something already made it again."""
    fd = os.open(top, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    try:
        os.write(fd, PLACEHOLDER)
    finally:
        os.close(fd)


def _unblock(top: Path) -> None:
    """Remove the delete's own placeholder at ``top`` (never anything else put there)."""
    try:
        if top.is_file() and not top.is_symlink() and top.read_bytes() == PLACEHOLDER:
            top.unlink()
    except OSError:
        pass


def _restore(aside: Path, moved: list[tuple[Path, Path]], why: BaseException) -> None:
    """Move each moved folder back (its placeholder removed first); one whose old path something made again stays
    where it was moved, named in ``RECOVERY.json`` beside it, and ``DeleteStranded`` says where (PT-02)."""
    stranded = []
    for top, target in reversed(moved):
        _unblock(top)
        try:
            os.rename(target, top)
        except OSError as error:
            stranded.append({"original": str(top), "kept_at": str(target), "why": f"{type(error).__name__}: {error}"})
    if stranded:
        from adroit.core.durable import write_atomic
        write_atomic(aside / "RECOVERY.json", json.dumps({
            "what": "a delete refused at its last check could not move these folders back: a run made their old paths "
                    "again meanwhile. Nothing was deleted. Move each back when that run has finished.",
            "refused_because": str(why), "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stranded": stranded}, indent=1) + "\n")
        first = stranded[0]
        raise DeleteStranded(f"not deleted: {why}; and a run made {first['original']} again while the study was moved "
                             f"aside, so it is kept, as it was, at {first['kept_at']} (named in {aside / 'RECOVERY.json'})"
                             "; move it back once that run has finished") from why


def _aside(root: Path, record: Path, tops: list[Path], folders: list[str]) -> list[tuple[Path, Path]]:
    """Move each of ``tops`` aside (one rename each, into ``<runs>/.adroit/deleting``), a placeholder at its old path
    (``_block``); the moved trees must hold exactly ``folders``' studies, with nothing in them running or publishing,
    else each is moved back (``_restore``) and nothing is deleted (PR-04, PS-05, PT-02)."""
    aside = root / ".adroit" / "deleting" / record.name
    moved: list[tuple[Path, Path]] = []
    try:
        for top in tops:
            target = aside / top.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.rename(top, target)
            moved.append((top, target))
            try:
                _block(top)
            except FileExistsError:
                raise NothingDeleted(f"not deleted: a run made {top} again while it was being moved aside") from None
        found = {str(top / s.relative_to(target)) for top, target in moved for s in _studies_in(target)}
        if found != set(folders):
            raise NothingDeleted(CHANGED)
        busy = _busy(moved, folders)
        if busy:
            raise NothingDeleted(f"not deleted: {busy} began inside it meanwhile; look again when it has finished")
    except BaseException as error:
        _restore(aside, moved, error)
        raise
    return moved


def _busy(moved: list[tuple[Path, Path]], folders: list[str]) -> str:
    """What in the moved trees is running or publishing, or "": a job whose record says it runs and whose process
    lives or is not yet started; a job whose calculation still runs after its run ended, or whose calculation's
    record cannot be read (``_calculation_left``, MF-01); or a publication lock (``durable.PUBLICATION_LOCK``) held by
    another writer, on a folder the delete does not hold (the confirmed studies' locks are its own: ``_holding``).
    PS-05."""
    import fcntl
    from adroit.core.durable import PUBLICATION_LOCK
    from adroit.ui import engine
    held = set(folders)
    for top, target in moved:
        for at, _dirs, files in os.walk(target):
            original = str(top / Path(at).relative_to(target))
            if "job.json" in files:
                try:
                    job = json.loads((Path(at) / "job.json").read_text())
                except (OSError, ValueError):
                    return f"a run whose record cannot be read ({original})"
                pid = int(job.get("pid") or 0)           # 0: being launched, its process not yet started
                if job.get("status") == "running" and (pid <= 0 or engine._alive(pid)):
                    return f"the run {job.get('title') or original}"
                try:                                     # its calculation, which can outlive its run (MF-01)
                    left = _calculation_left(int(job.get("calculation") or 0), job.get("calculation_started"))
                except (TypeError, ValueError):
                    return f"a run whose calculation's record cannot be read ({original})"
                if left:                                 # said as a noun, as the refusal's sentence needs
                    return f"a calculation that still runs, of the run {job.get('title') or original},"
            if PUBLICATION_LOCK in files and original not in held:
                with (Path(at) / PUBLICATION_LOCK).open("a") as stream:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(stream, fcntl.LOCK_UN)
                    except BlockingIOError:
                        return f"a publication into {original}"
    return ""


def _delete_studies(root: Path, folders: list[str], record: Path, recorded) -> list[str]:
    """Delete each outermost study folder of ``folders``, its publication locks held by the caller (``_holding``):
    moved aside and checked (``_aside``; ``NothingDeleted`` otherwise), the delete recorded (``recorded()``: from here
    a delete stopped half-way is still recorded), its money records kept, then removed; returns what was kept."""
    from adroit.orchestrator import annotations
    tops = _outermost([Path(f) for f in folders])
    listed, kept = _listing(root), []
    moved = _aside(root, record, tops, folders)
    recorded()
    for top, target in moved:
        kept += _keep_money(root, target, record, origin=top)
        _unlink_from_parent(top, tops, listed)
        shutil.rmtree(target)
        _unblock(top)
    shutil.rmtree(root / ".adroit" / "deleting" / record.name, ignore_errors=True)
    annotations.forget(root, tops)
    return kept


def _write(record: Path, deleted: Deleted) -> Deleted:
    from adroit.core.durable import write_atomic
    write_atomic(record / "deleted.json", json.dumps(deleted.model_dump(mode="json"), indent=1) + "\n")
    return deleted


def delete_study(root: Path, folder: Path, expected: Plan) -> Deleted:
    """Delete a study as ``expected`` (the plan the person confirmed) says, its money records kept (module docstring)."""
    root = Path(root).resolve()
    _confirmed(plan_study(root, folder), expected)
    with _holding(expected.studies):                 # the plan again, under the locks, then the removal (PR-04)
        plan = plan_study(root, folder)
        _confirmed(plan, expected)
        record = _record_folder(root, "study_" + plan.name)
        deleted = Deleted(kind="study", name=plan.name,
                          deleted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          studies=[os.path.relpath(f, root) for f in plan.studies])
        try:
            kept = _delete_studies(root, plan.studies, record, lambda: _write(record, deleted))
        except (NothingDeleted, DeleteStranded):
            shutil.rmtree(record, ignore_errors=True)    # nothing deleted: no record of a delete
            raise
    return _write(record, deleted.model_copy(update={"kept": kept}))


def _delete_run_folder(root: Path, folder: Path, record: Path, recorded) -> list[str]:
    """Delete a run's folder: moved aside and checked to hold no study and nothing running or publishing (``_aside``;
    ``NothingDeleted`` otherwise), the delete recorded (``recorded()``), its money records kept, then removed; returns
    what was kept."""
    moved = _aside(root, record, [folder], [])
    recorded()
    kept: list[str] = []
    for top, target in moved:
        kept += _keep_money(root, target, record, origin=top)
        shutil.rmtree(target)
        _unblock(top)
    shutil.rmtree(root / ".adroit" / "deleting" / record.name, ignore_errors=True)
    return kept


def delete_run(root: Path, folder: Path, expected: Plan) -> Deleted:
    """Delete a run that ended without a study as ``expected`` (the plan the person confirmed) says, its money records
    kept (module docstring)."""
    root = Path(root).resolve()
    plan = plan_run(root, folder)
    _confirmed(plan, expected)
    record = _record_folder(root, "run_" + plan.name)
    deleted = Deleted(kind="run", name=plan.name, deleted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      runs=[os.path.relpath(f, root) for f in plan.runs])
    try:
        kept = _delete_run_folder(root, Path(plan.runs[0]), record, lambda: _write(record, deleted))
    except (NothingDeleted, DeleteStranded):
        shutil.rmtree(record, ignore_errors=True)        # nothing deleted: no record of a delete
        raise
    return _write(record, deleted.model_copy(update={"kept": kept}))


def delete_model(root: Path, model_id: str, expected: Plan, catalog=None) -> Deleted:
    """Delete a personal model as ``expected`` says: its studies (money records kept), its batch-draft requests, then
    its revisions (module docstring)."""
    from adroit.core.checkpoint import run_lock
    from adroit.library.personal import Catalog
    from adroit.ui import batch
    catalog = catalog or Catalog()
    root = Path(root).resolve()
    _confirmed(plan_model(root, model_id, catalog), expected)
    # no library change, and no publication into its studies, from the plan made again to the removal (PR-04)
    with run_lock(catalog.root), _holding(expected.studies):
        plan = plan_model(root, model_id, catalog)
        _confirmed(plan, expected)
        record = _record_folder(root, "model_" + plan.name)
        deleted = Deleted(kind="model", name=plan.name,
                          deleted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), model_id=model_id,
                          revisions=plan.revisions, batch_items=plan.batch_items,
                          studies=[os.path.relpath(f, root) for f in plan.studies])
        model = catalog.root / "models" / model_id
        aside = catalog.root / ".deleting" / f"{record.name}_{model_id}"
        aside.parent.mkdir(parents=True, exist_ok=True)
        os.rename(model, aside)                      # moved aside first; its revisions must be the ones confirmed
        try:
            if len(list((aside / "revisions").glob("*.json"))) != expected.revisions:
                raise NothingDeleted(CHANGED)
            kept = _delete_studies(root, plan.studies, record, lambda: _write(record, deleted))
        except BaseException as error:
            os.rename(aside, model)                  # the model put back (its studies, if any went, recorded)
            if isinstance(error, (NothingDeleted, DeleteStranded)):
                shutil.rmtree(record, ignore_errors=True)
            raise
        prefix = f"catalog:{model_id}@"
        for item in [x for x in batch.draft(root) if any(prefix in str(part) for part in x.command)]:
            try:
                batch.remove_from_draft(root, item)
            except batch.DraftChanged:
                pass
        shutil.rmtree(aside)
    return _write(record, deleted.model_copy(update={"kept": kept}))


# --- the confirmation windows --------------------------------------------------------------------------------------

def _listed(plan: Plan, folders: list[str]) -> str:
    shown = [plan.titles.get(f, Path(f).name) for f in folders[:8]]
    return "; ".join(shown) + (f"; and {len(folders) - 8} more" if len(folders) > 8 else "")


def _window(title: str, lines: list[str], plan: Plan, act, done, button: str) -> None:
    """A confirmation window: what will be deleted, then Cancel or the delete; only Close while something runs."""
    with ui.dialog() as dialog, ui.card().classes("max-w-xl").mark("delete_window"):
        ui.label(title).classes("text-lg font-medium")
        if plan.blocked:
            ui.label("It cannot be deleted: " + "; ".join(plan.blocked) + ".").classes("text-orange-800") \
                .mark("delete_refused")
            ui.button("Close", on_click=dialog.close)
        elif plan.running:
            ui.label("It cannot be deleted now: " + "; ".join(plan.running) + ". Wait for it to finish or stop it "
                     "first.").classes("text-orange-800").mark("delete_refused")
            ui.button("Close", on_click=dialog.close)
        else:
            for line in lines:
                ui.label(line).classes("text-sm")
            ui.label(KEPT_NOTE).classes("text-sm text-gray-600")

            def go() -> None:
                try:
                    act()
                except (ValueError, OSError, RuntimeError) as error:
                    ui.notify(str(error))
                    dialog.close()
                    return
                dialog.close()
                ui.notify(f"deleted: {plan.name}")
                done()

            with ui.row().classes("gap-2 mt-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").mark("delete_cancel")
                ui.button(button, on_click=go).props("color=negative").mark("delete_confirm")
    dialog.open()


def confirm_study(root: Path, folder: Path, done) -> None:
    """The window after Delete on a study."""
    try:
        plan = plan_study(root, folder)
    except (ValueError, OSError) as error:
        ui.notify(str(error))
        return
    others = plan.studies[1:]
    lines = ([f"This will also delete the {len(others)} stud{'y' if len(others) == 1 else 'ies'} made from it: "
              + _listed(plan, others) + "."] if others else [])
    _window(f"Delete the study “{plan.name}”?", lines, plan, lambda: delete_study(root, folder, plan), done,
            "Delete the study" + (f" and {len(others)} more" if others else ""))


def confirm_run(root: Path, folder: Path, done) -> None:
    """The window after Delete on a run that ended without a study."""
    try:
        plan = plan_run(root, folder)
    except (ValueError, OSError) as error:
        ui.notify(str(error))
        return
    _window(f"Delete the run “{plan.name}”?", ["Its folder, its log and everything it wrote will be deleted."], plan,
            lambda: delete_run(root, folder, plan), done, "Delete the run")


def confirm_model(root: Path, model_id: str, done) -> None:
    """The window after Delete on a personal model: "this will also delete the study, do you want to proceed?" where
    studies used it (the owner's words, 2026-11-18)."""
    try:
        plan = plan_model(root, model_id)
    except (ValueError, OSError) as error:
        ui.notify(str(error))
        return
    n = len(plan.studies)
    lines = [f"Its {plan.revisions} saved revision{'' if plan.revisions == 1 else 's'} will be deleted."]
    if n:
        lines.append(f"This will also delete the stud{'y' if n == 1 else 'ies'} made with it ({n}): "
                     + _listed(plan, plan.studies) + ". Do you want to proceed?")
    if plan.batch_items:
        lines.append(f"Its {len(plan.batch_items)} request(s) in the batch draft will be removed.")
    _window(f"Delete the model “{plan.name}”?", lines, plan, lambda: delete_model(root, model_id, plan), done,
            "Delete the model" + (f" and {n} stud{'y' if n == 1 else 'ies'}" if n else ""))


def delete_button(on_click, what: str):
    """A small Delete button (its window opens on click)."""
    return ui.button(icon="delete", on_click=on_click).props("flat dense round color=negative size=sm") \
        .tooltip(f"Delete this {what}…").mark(f"delete_{what}")

"""Durable records: written whole, listed around damage, never calculated through it (the consistency audit's CA-07,
2026-10-24, and the consolidation plan's M3, 2026-10-25).

One ``{}`` job record had made the workbench's Home and Studies pages fail (a 500), one damaged batch the batch page,
one invalid annotation every annotation, one damaged step or revision a session's steps or a whole library. A listing
for browsing reads each record on its own (``read_each``): a damaged one is left out of the items and named with why,
never raised and never dropped silently, and the page or command that lists says so. Opening a record directly stays
strict (each family's ``load``), and so does anything that calculates from a collection: a damaged record that a
calculation depends on stops it, with the reason, rather than being skipped (``DamagedRecord``).

A record is published whole (``write_atomic``): written to a temporary file beside it, flushed and synced to the disk,
then put in place in one step, so a reader sees the previous record or the new one, never part of one, and a crash
leaves one of the two. Publishing whole does not stop two writers from losing each other's update: a read-modify-write
of a shared record (``records.yaml``) holds ``lock`` across all three steps.

A study's publication (its result, evidence, report and record, and its parent's list of children) is written under
its folder's own lock (``publishing``), which every writer of a study's parts takes: no part of another publication is
written between them (the auditor's DD recheck, DE-02, 2026-11-05: a writer's later parts had been written over another
publication completed meanwhile, and two reanalyses into one folder had both succeeded, one result lost). A writer
holds it from before it writes anything into the folder, its figures and checkpoints included, to its record; and the
figures it draws are named by its hold (``Claim.drawn``), never by a map of this process's draws by path (the auditor's DE
recheck, DF-01, 2026-11-05: a writer refused at its record had first drawn its figure over the holder's, which the
holder's report then bound as its own). A figure drawn where its writer holds no folder is drawn under a hold taken for
it, from before it is rendered (``evidence.bindings.write_figure``; the auditor's DF recheck, DG-02, 2026-11-06: the folder
had only been probed, and a figure still rendering when another writer took it had been written over that writer's).
"""
from __future__ import annotations

import contextlib
import errno
import fcntl
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, TypeVar

from adroit.core.state import StrictModel

T = TypeVar("T")


class Unreadable(StrictModel):
    """A durable record a listing could not read: where it is, and why."""
    path: str
    why: str


def reason(error: BaseException) -> str:
    """Why a record could not be read, in one line: the error's kind and the first line of its message."""
    text = str(error).splitlines()[0] if str(error) else ""
    return f"{type(error).__name__}: {text}" if text else type(error).__name__


def read_each(paths: Iterable[Path], load: Callable[[Path], T]) -> tuple[list[T], list[Unreadable]]:
    """(each record ``load`` reads from ``paths``, in order; each one it cannot read, named with why). A record is
    damaged where reading it fails (``OSError``) or what it holds is not the record (``ValueError``, which a
    validation error is, ``KeyError``, ``TypeError``)."""
    items: list[T] = []
    damaged: list[Unreadable] = []
    for path in paths:
        try:
            items.append(load(path))
        except (OSError, ValueError, KeyError, TypeError) as error:
            damaged.append(Unreadable(path=str(path), why=reason(error)))
    return items, damaged


def summary(damaged: list[Unreadable], what: str, shown: int = 5, relative: Callable[[str], str] = str) -> str:
    """One sentence naming the damaged records of a listing ("" if none): how many, the first few with why, and that
    the rest are listed."""
    if not damaged:
        return ""
    names = "; ".join(f"{relative(d.path)} ({d.why})" for d in damaged[:shown])
    more = f"; and {len(damaged) - shown} more" if len(damaged) > shown else ""
    return (f"{len(damaged)} {what} could not be read and {'is' if len(damaged) == 1 else 'are'} not listed: "
            f"{names}{more}. The rest are listed; repair or move the file named to list it again.")


def absent(path: Path | str, folder: int | None = None) -> bool:
    """Whether nothing at all is at ``path``: no entry of that name in its folder. An entry that is there but leads to
    nothing that can be read (a link to a missing file, a link to itself, a link through a file) is not absent: a
    reader names it as damage (the auditor's DM recheck, DN-01, 2026-11-08: ``Path.exists`` follows a link and answers False
    for those, so a run whose request record was a link to nothing had read as a run from before request records, and
    been charged with another session's dollars and cap). ``folder``: the open folder it is in, whose writers' lock is
    held, in which it is looked for by its name (``_in``)."""
    name, at = _in(path, folder)
    try:
        os.stat(name, dir_fd=at, follow_symlinks=False)
    except (OSError, ValueError):
        return True
    return False


def linked(path: Path | str, folder: int | None = None) -> str:
    """Words for an entry that is a link (what it names, to go before why it cannot be read), or "" for another
    (``folder``: as ``absent``'s)."""
    name, at = _in(path, folder)
    try:
        return f"a link to {os.readlink(name, dir_fd=at)}: "
    except OSError:
        return ""


def _in(path: Path | str, folder: int | None) -> tuple[Path | str, int | None]:
    """How a record's writer reaches the entry at ``path``: by its path, where it holds no lock (``folder`` None); else
    by its name in ``folder``, the open folder whose writers' lock it holds (``_writers_lock``), as (its name, the
    folder) for an operation's ``dir_fd``. Once it holds the lock, a writer reads and writes the record, its mark and
    every file beside them only so, never by their path again: the folder at their path may since be another, put in
    its place, whose lock it does not hold (the auditor's DT recheck, DU-01, 2026-11-10: a recovery, holding the lock of a
    folder renamed away, had written its mark by its path into the equal copy put in its place, over the mark of a
    request another writer had journalled and sent there under the copy's own lock)."""
    return (path, None) if folder is None else (Path(path).name, folder)


def read_object(path: Path | str) -> tuple[dict | None, str]:
    """A JSON record read three ways (the auditor's CO recheck, CR-03 and CR-06, 2026-10-26: a record holding ``null``, a
    list or a number had read as absent, so an empty journal said "no paid request was sent", and a study's page
    failed): (None, "") where it is absent (``absent``: a link to nothing is not); (the object, "") where it is present
    and a JSON object; (None, why) where it is present but cannot be read, or holds something other than an object."""
    path = Path(path)
    if absent(path):
        return None, ""
    try:
        content = path.read_bytes()
    except OSError as error:
        return None, f"cannot be read ({linked(path)}{reason(error)})"
    return parse_object(content)


def parse_object(content: bytes | str) -> tuple[dict | None, str]:
    """``read_object`` of content already read: (the object, "") where it is a JSON object, else (None, why)."""
    import json
    try:
        data = json.loads(content)
    except ValueError as error:
        return None, f"cannot be read ({reason(error)})"
    if not isinstance(data, dict):
        held = ("null" if data is None else "a list" if isinstance(data, list) else "a string" if isinstance(data, str)
                else "true or false" if isinstance(data, bool) else "a number")
        return None, f"is not a JSON object (it holds {held})"
    return data, ""


class DamagedRecord(ValueError):
    """A record that an operation depends on cannot be read: the operation stops, naming the record, why and what to
    do, never carrying on without it (a damaged active profile never falls back to the packaged defaults). A
    ``ValueError``, so that every handler of a refused input handles it; the command line prints it in one line."""

    def __init__(self, path: Path | str, why: str, fix: str = "repair it or move it aside"):
        self.path, self.why, self.fix = str(path), why, fix
        super().__init__(f"{path} cannot be read ({why}): {fix}")


def write_atomic(path: Path | str, data: str | bytes, *, folder: int | None = None) -> Path:
    """Publish ``data`` as the whole of ``path`` (module docstring): a temporary file in the same folder, flushed and
    synced, then ``os.replace``; the folder synced too where the platform allows it. The folder is made if absent.
    If anything fails before the replacement, the previous file is untouched and the temporary one removed. Where
    ``folder``, the open folder ``path`` is in, whose writers' lock its writer holds, is given, both are made in that
    folder, by ``path``'s name, wherever it is now, never in another put at its path since (``_in``; DU-01); it is not
    made."""
    path = Path(path)
    payload = data.encode() if isinstance(data, str) else data
    _, at = _in(path, folder)
    if at is not None:
        _write_in(at, path, payload)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(name)
        raise
    _sync_folder(path.parent)
    return path


def _write_in(folder: int, path: Path, payload: bytes) -> None:
    """``write_atomic`` in the open folder ``folder``, by ``path``'s name: a temporary file made there where no entry
    is, flushed and synced, then renamed over the name there, and the folder synced."""
    import secrets
    name = f".{path.name}.{secrets.token_hex(8)}.tmp"
    handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=folder)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(name, path.name, src_dir_fd=folder, dst_dir_fd=folder)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(name, dir_fd=folder)
        raise
    _sync_folder(path.parent, folder)


def write_new(path: Path | str, data: str | bytes) -> Path:
    """Publish ``data`` as a new file at ``path``, never replacing an entry there (``publish_new``): written whole to a
    temporary file beside it, then put in place only where no file or link is. Refused (``FileExistsError``) where
    one is, nothing of this one kept; the folder is made if absent."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = data.encode() if isinstance(data, str) else data
    handle, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return publish_new(name, path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(name)


def publish_new(staged: Path | str, path: Path | str) -> Path:
    """``staged``, a whole file in ``path``'s folder, published at ``path`` only where no entry is (the auditor's DK recheck,
    DL-05, 2026-11-07: an export that checked its new path, then replaced whatever was there when it finished, had
    overwritten another export's bundle completed meanwhile). A hard link is made there: one step that fails where any
    entry is, a file or a link, and replaces nothing, so a reader sees no file or the whole of it. On a file system
    without hard links the file is created only where none is (``O_EXCL``) and ``staged``'s bytes copied into it.
    Refused (``FileExistsError``, naming the path) where an entry is; ``staged`` is left for its caller to remove."""
    staged, path = Path(staged), Path(path)
    try:
        try:
            os.link(staged, path)
        except OSError as error:
            if isinstance(error, FileExistsError) or error.errno not in NO_HARD_LINKS:
                raise
            _copy_new(staged, path)
    except FileExistsError:
        raise FileExistsError(errno.EEXIST, "another file was written there meanwhile; nothing of this one was kept",
                              str(path)) from None
    _sync_folder(path.parent)
    return path


NO_HARD_LINKS = frozenset({errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EMLINK})


def _copy_new(staged: Path, path: Path) -> None:
    """``publish_new`` where hard links are not supported: ``path`` created only where no entry is, then filled."""
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(handle, "wb") as stream, staged.open("rb") as source:
            while chunk := source.read(1 << 20):
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        with contextlib.suppress(OSError):
            path.unlink()
        raise


@dataclass(frozen=True)
class Held:
    """What an append-only record held when it was last read or written whole: its length and its bytes' SHA-256. The
    record still holds that history where its bytes begin with those (``begins``): another writer's lines appended
    since keep it; a record replaced, emptied, cut short or removed does not (the auditor's DN recheck, DO-01, 2026-11-08)."""
    size: int
    sha256: str

    @classmethod
    def of(cls, data: bytes) -> Held:
        """What a record whose whole bytes are ``data`` holds."""
        import hashlib
        return cls(len(data), hashlib.sha256(data).hexdigest())

    def begins(self, data: bytes) -> bool:
        """Whether a record's whole bytes ``data`` still begin with what was held."""
        return len(data) >= self.size and Held.of(data[:self.size]) == self


class ChangedRecord(ValueError):
    """An append-only record that is not, or no longer, one its writer may append to (``append_held``): nothing was
    written to it."""


class UnfinishedAppend(OSError):
    """An append that failed once its writing had begun (``append_held``): the record may hold none, part or all of
    it, so its writer no longer knows what the record holds (the auditor's DO recheck, DP-01, 2026-11-09)."""


def append_held(path: Path | str, data: bytes, held: Held | None, *,
                whole: Callable[[bytes, Path], None]) -> Held:
    """Append ``data`` whole to an append-only record of lines, synced to the disk, only where the record is the one
    last read or written and is whole, and return what it holds after, recorded beside it (``marked``). Where something
    was (``held``), its bytes must still begin with what it held; where nothing was (None), nothing at all may be at its
    path, and the record is made there, never through a link; either way its bytes must begin with what its mark
    records its writers last wrote. Refused (``ChangedRecord``, saying how), nothing written and nothing made, where an
    entry there cannot be opened or read (a link leading nowhere, a folder, a file it may not write), where nothing is
    there now or something is now, or where its bytes no longer begin with those held or marked (it was replaced,
    emptied or cut short): a record of money is never made anew under its writer (the auditor's DN recheck, DO-01,
    2026-11-08: a paid journal's append had made a link's missing target, or written on in an empty file put in the
    journal's place, and what was spent before was lost from it). Refused too where its whole bytes, what another
    writer appended since included, are not a record its writers could have kept (``whole``, which raises
    ``ValueError`` for them: a torn last line, a line that is not one of its entries): nothing is written after a
    torn or damaged line, which stays as it is until it is recovered (the auditor's DO recheck, DP-01, 2026-11-09: a
    reservation's write cut short, and then the next appended after it, had made a recoverable torn line damage in the
    middle of the journal, and the next request was sent). A whole last line without its newline (a record from before,
    written so) is ended before ``data``, never joined to it. The check and the write are of one open file, and its path
    must still lead to that file (``_displaced``): where another entry is put in its place while it is checked, refused,
    nothing written; where once the write began, or as it is recorded beside it, ``UnfinishedAppend``, so that what the
    record at its path holds is never taken to hold what was written to another file, nor its mark to describe it
    (the auditor's DP recheck, DQ-02, 2026-11-09: a journal renamed away once checked, and its earlier bytes put back at its
    path, had had a reservation appended to the file renamed, the mark beside the other written for it, and the request
    sent). Where the write fails once begun, ``UnfinishedAppend``: the record may hold part of it. The folder is made if
    absent where nothing was.

    The record is appended to only by its own name (``_displaced``): the entry at its path must be the file opened, not
    a link to it, the file must have no other name (a hard link), and its folder must be the one whose lock is held;
    else refused, nothing written (``UnfinishedAppend`` once the write began). Its mark is beside that name, so that one
    mark records every append to it (the auditor's DS recheck, DT-01, 2026-11-10: a request appended to a session's journal
    through a link to it, or by a hard link's name, had been marked beside the link, and the journal's own mark, still
    recording less, read the journal cut back to it as less spent).

    Once its writers' lock is held, the record is opened, and its mark read and written, by their names in the folder
    locked (``_in``), never by their path again: where that folder is moved away meanwhile, and another put at its
    path, the append writes nothing in the other, whose lock it does not hold (a mark there may be another writer's);
    the checks above then refuse it (the auditor's DT recheck, DU-01, 2026-11-10).

    The record is checked, written and marked under its writers' lock (``_locked``), which every writer of an
    append-only record takes (``writing``), taken before the record is opened, its mark read once it is held: no other
    writer checks, writes, replaces or marks it meanwhile. It is a lock on the folder the record is in
    (``_writers_lock``), never on its own file, in whose place a writer that replaces it whole puts another (the auditor's DR
    recheck, DS-01, 2026-11-09). What the append acknowledges is only what it checked and wrote: once written and
    synced, the record must hold exactly the bytes it checked, followed by its own (``_as_written``); the mark records
    those, never whatever the file then holds; and the mark, once written, must be read back as it was written, the
    record still holding what it records (``_recorded``). Where either is not so, ``UnfinishedAppend``, nothing more
    recorded: a record rewritten in place as it is appended to is never marked as its writers' history, nor its request
    sent against a mark that cannot be read (the auditor's DQ recheck, DR-01, 2026-11-09: a journal emptied, or its earlier
    lines removed, in place, once its append had checked it or once the line was synced, had had a fresh mark written
    for what was left, the request sent, and a paid request forgotten: every account read from it since held less). What
    is changed after the append returns is read against its mark by the next append and by every reading."""
    path = Path(path)
    if held is None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:                    # nothing is written before the record is open and checked
            raise ChangedRecord(str(error)) from error
    with _locked(path, held) as (mark, folder):
        name, at = _in(path, folder)
        try:
            handle = os.open(name, os.O_RDWR | os.O_APPEND | (os.O_CREAT | os.O_EXCL if held is None else 0), 0o666,
                             dir_fd=at)
        except OSError as error:
            raise ChangedRecord(_unopened(path, held, error, folder)) from error
        try:
            found, data = _appendable(path, handle, data, held, mark, whole)
            if why := _displaced(path, handle, folder):
                raise ChangedRecord(f"{path}: {why}; nothing is written to it")
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(handle, view):]
                os.fsync(handle)
                now = _read_whole(handle)
            except OSError as error:
                raise UnfinishedAppend(f"{path}: its append failed once begun ({reason(error)}): it may hold part of "
                                       "it") from error
            after = _as_written(path, found, data, now)
            _written_at(path, handle, folder, "once its append began")
            try:
                if held is None:
                    _sync_folder(path.parent, at)
                write_atomic(mark_of(path), json.dumps({"size": after.size, "sha256": after.sha256}), folder=folder)
            except OSError as error:
                raise UnfinishedAppend(f"{path}: its append was written, but not recorded beside it "
                                       f"({reason(error)})") from error
            _written_at(path, handle, folder, "as its append was recorded beside it")
            _recorded(path, handle, after, folder)
        finally:
            os.close(handle)
    return after                                    # its writers' lock released once its mark is read back


@contextlib.contextmanager
def _locked(path: Path, held: Held | None):
    """The writers' lock of the record at ``path`` (``_writers_lock``) held while an append opens, checks, writes and
    marks it (``append_held``): (what its mark records once the lock is held (``marked``), what its last writer
    recorded, none of its writers writing now, read in the folder locked (``_in``); the open folder whose lock it is).
    ``ChangedRecord`` where the mark cannot be read, or, where nothing was (``held`` None), records bytes written to
    it: nothing is opened or written."""
    with _writers_lock(path) as folder:
        try:
            mark = marked(path, folder)
        except ValueError as error:
            raise ChangedRecord(str(error)) from error
        if held is None and mark is not None and mark.size:
            raise ChangedRecord(f"{path}: nothing is there, although its mark ({mark_of(path).name}) records "
                                f"{mark.size} bytes written to it")
        yield mark, folder


def _as_written(path: Path, found: bytes, data: bytes, now: bytes) -> Held:
    """What a record holds once an append wrote ``data`` after the ``found`` bytes it checked (``append_held``),
    ``now`` being its whole bytes as read once written and synced: those, by length and SHA-256, where ``now`` is
    exactly ``found`` followed by ``data``. Else ``UnfinishedAppend``: the record was changed in place as it was
    appended to (emptied, cut short, its lines removed or changed), under its writers' lock, so by none of them; what it
    holds is not known, and nothing is recorded beside it (DR-01)."""
    if now != found + data:
        raise UnfinishedAppend(f"{path}: it was changed in place as it was appended to: written and synced, it holds "
                               f"{len(now)} bytes, not the {len(found)} it was checked to hold followed by this "
                               f"append's {len(data)}; what it holds is not known, and nothing is recorded beside it")
    return Held.of(now)


def _recorded(path: Path, handle: int, after: Held, folder: int) -> None:
    """``UnfinishedAppend`` where, once an append's mark is written (``append_held``), the mark is not read back as
    what it recorded (``after``: it cannot be read, or records another length or SHA-256), or the record no longer
    holds exactly that: an append is acknowledged, and its request sent, only where the record and its mark are read
    as one, as every reading reads them (DR-01). The mark is read in ``folder``, the folder locked (``_in``); once read
    back, that folder must still be the one at the record's path, and the record there the file written
    (``_written_at``): an append is acknowledged only as the record at its path, never as one in a folder moved away
    meanwhile (the auditor's DU recheck, DV-02, 2026-11-10: the folder renamed away as its readback began, and an older
    coherent copy put at its path, the readback had read the moved folder as one, the request had been sent, and the
    run's accounting had read the copy as all it spent). What changes after this last check, before the append
    returns or its request is sent, it does not see: the client's next entry, checked against what it held, is then
    refused, and leaves its notice beside the ledger (``budget.leave_unjournalled``)."""
    try:
        mark, now = marked(path, folder), _read_whole(handle)
    except (OSError, ValueError) as error:
        raise UnfinishedAppend(f"{path}: its append was recorded beside it, but cannot be read back as recorded "
                               f"({reason(error) if isinstance(error, OSError) else error})") from error
    if mark != after or Held.of(now) != after:
        raise UnfinishedAppend(f"{path}: its append was recorded beside it, but "
                               + ("the mark there now records another history" if mark != after else
                                  "the record was changed in place since: it is not what its mark records")
                               + "; what it holds is not known")
    _written_at(path, handle, folder, "as its append was read back")


@contextlib.contextmanager
def writing(path: Path | str):
    """The writers' lock of the append-only record at ``path`` (``_writers_lock``), for another of its writers, which
    replaces it whole (``budget.recover_torn_tail``): held while it reads it, puts the record rewritten in its place and
    writes its mark, so that no append opens, checks, writes or marks it meanwhile; waited for. ``ChangedRecord`` where
    its folder was moved, or replaced, while it waited (DT-01).

    The open folder whose lock is held is yielded: the writer reads and writes the record, its mark and the files
    beside them in it, by their names (``_in``: ``budget.ledger_bytes``'s and ``write_atomic``'s ``folder``), never
    by their path, and checks it is still at the record's path before it writes anything (``in_place``). Once the block
    ends, ``ChangedRecord`` where it is not: the folder was moved or replaced while the lock was held, and what was
    written is in the folder locked, no longer at the record's path, nothing of it in the folder there now (the auditor's DT
    recheck, DU-01, 2026-11-10: a recovery whose folder was so replaced had written its mark by its path over the mark
    of a request journalled and sent in the folder put in its place, and said it was done)."""
    with _writers_lock(path) as folder:
        yield folder
        if not _folder_at(path, folder):
            raise ChangedRecord(f"{path}: its folder was moved or removed, or another put in its place, while its "
                                "writer held its writers' lock: what it wrote is in the folder it locked, no longer at "
                                "this path, and nothing in the folder there now was written by it; read the record "
                                "there as it is")


def in_place(path: Path | str, folder: int) -> None:
    """``ChangedRecord``, nothing written, where the open folder ``folder``, whose writers' lock is held (``writing``),
    is no longer the folder at ``path`` (``_folder_at``): checked by a writer that replaces the record whole before
    it writes anything (DU-01)."""
    if not _folder_at(path, folder):
        raise ChangedRecord(f"{path}: nothing is written to it: its folder was moved or removed, or another put in its "
                            "place, while its writer held its writers' lock, which is the lock of the folder that was "
                            "there")


@contextlib.contextmanager
def _writers_lock(path: Path | str):
    """The writers' lock of the append-only record at ``path``, which every writer of it takes (``_locked``,
    ``writing``): an exclusive lock (``flock``) on the folder it is in, opened by its path, waited for and held until
    the block ends. The folder's, not the record's own file's: a writer that replaces the record whole puts another
    file at its path, and a writer that opened the record meanwhile would lock that one, so the two would not exclude
    each other; the folder stays as the record is replaced in it (the auditor's DR recheck, DS-01, 2026-11-09: a recovery
    held the lock of a journal's file and put the recovered journal in its place; a request's append, in another
    process, locked the new file, wrote and marked its lines and was sent, and the recovery's mark, of the journal
    before them, was then written over its own, so that they could be cut away unseen). The open folder is yielded.
    Once the lock is taken, the folder at the record's path must still be the one locked (``_folder_at``): a writer
    that waited for the lock of a folder since moved or removed, another put in its place, holds a lock no other
    writer of the record takes now, and is refused (the auditor's DS recheck, DT-01, 2026-11-10: a waiter whose folder was
    renamed away, and an equal copy put at its path, had appended and sent its request while another held the lock of
    the folder there). ``ChangedRecord`` where it cannot be opened or locked, or is no longer there: nothing is
    written."""
    try:
        handle = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as error:
        raise ChangedRecord(f"{path}: nothing is written to it: its folder cannot be opened for its writers' lock "
                            f"({reason(error)})") from error
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
        except OSError as error:
            raise ChangedRecord(f"{path}: nothing is written to it: its writers' lock cannot be taken "
                                f"({reason(error)})") from error
        if not _folder_at(path, handle):
            raise ChangedRecord(f"{path}: nothing is written to it: its folder was moved or removed, or another put in "
                                "its place, while its writer waited for its writers' lock, which is the lock of the "
                                "folder that was there")
        yield handle
    finally:
        os.close(handle)                            # the lock is released with it


def _folder_at(path: Path | str, folder: int) -> bool:
    """Whether the folder ``path`` is in, as its path leads now, is the open folder ``folder``: not another put in its
    place."""
    try:
        there, opened = os.stat(Path(path).parent), os.fstat(folder)
    except OSError:
        return False
    return (there.st_dev, there.st_ino) == (opened.st_dev, opened.st_ino)


def one_entry(one: Path | str, other: Path | str) -> bool:
    """Whether two paths name one entry, as they lead now: their folders are one folder, however each is reached (a
    link to it, or to a folder above it, on the way), and their names one name in it (the same, or the same entry spelt
    otherwise, as a folder that ignores case reads it: one file of one name). A paid ledger is so known by each path a
    client is given to it, not by its spelling (the auditor's DT recheck, DU-02, 2026-11-10)."""
    one, other = Path(one), Path(other)
    try:
        first, second = os.stat(one.parent), os.stat(other.parent)
    except OSError:
        return False
    if (first.st_dev, first.st_ino) != (second.st_dev, second.st_ino):
        return False
    if one.name == other.name:
        return True
    try:
        first, second = os.lstat(one), os.lstat(other)
    except OSError:
        return False
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino) and first.st_nlink == 1


def _displaced(path: Path, handle: int, folder: int) -> str:
    """Why the record at ``path`` is no longer the open file ``handle``, in the open folder ``folder`` whose writers'
    lock is held (``append_held``), by its own name: "" where it is. Else what is so: its folder moved or another put in
    its place (``_folder_at``); a link at its path, or a file with another name (``own``); or another entry put in its
    place (DQ-02)."""
    if not _folder_at(path, folder):
        return "its folder was moved or removed, or another put in its place"
    if why := own(path, handle):
        return why
    try:
        entry, opened = os.lstat(path), os.fstat(handle)
    except OSError:
        return "nothing is at its path now"
    if (entry.st_dev, entry.st_ino) != (opened.st_dev, opened.st_ino):
        return "another entry was put in its place"
    return ""


def own(path: Path | str, handle: int, folder: int | None = None) -> str:
    """Why the open file ``handle``, opened by ``path``, is not a record read or written by its own name: "" where it
    is. The entry at ``path``, not followed, must not be a link, and the file must have no other name. An append-only
    record and its mark (``mark_of``) are one by its name: appended to through a link, or by another name of its file
    (a hard link), it is marked beside that name, and the mark beside its own then records less than it holds, so that
    what was appended can be cut away unseen; read so, it is read against a mark its writers did not write (the auditor's DS
    recheck, DT-01, 2026-11-10). Its writers (``append_held``) and its readers (``budget.ledger_bytes``) so read and
    write it only by its own name. ``folder``: as ``absent``'s."""
    import stat
    name, at = _in(path, folder)
    try:
        entry, opened = os.stat(name, dir_fd=at, follow_symlinks=False), os.fstat(handle)
    except OSError as error:
        return f"nothing that can be read is at its path now ({reason(error)})"
    if stat.S_ISLNK(entry.st_mode):
        return (f"it is {linked(path, folder)[:-2] or 'a link'}, not a file of its own: it is read and written only by "
                "its own name, beside its mark, never through a link")
    if opened.st_nlink != 1:
        return (f"its file has {opened.st_nlink} names (another is a hard link to it): it is read and written only by "
                "its own name, beside its mark, never by another")
    return ""


def read_own(path: Path | str, folder: int | None = None) -> bytes:
    """An append-only record's whole bytes, read by its own name (``own``). ``OSError`` where it cannot be opened or
    read; ``ValueError``, saying why, where the entry at ``path`` is a link, or its file has another name. ``folder``:
    as ``absent``'s."""
    name, at = _in(path, folder)
    handle = os.open(name, os.O_RDONLY, dir_fd=at)
    try:
        data = _read_whole(handle)                  # a folder there is refused here, as it cannot be read
        if why := own(path, handle, folder):
            raise ValueError(why)
        return data
    finally:
        os.close(handle)


def _written_at(path: Path, handle: int, folder: int, when: str) -> None:
    """``UnfinishedAppend`` where ``path`` no longer leads to the file just appended to, by its own name, in the folder
    whose lock is held (``_displaced``)."""
    if why := _displaced(path, handle, folder):
        raise UnfinishedAppend(f"{path}: {when}, {why}: what was written is not in the record at its path by its own "
                               "name, and what that holds is not known")


def _appendable(path: Path, handle: int, data: bytes, held: Held | None, mark: Held | None,
                whole: Callable[[bytes, Path], None]) -> tuple[bytes, bytes]:
    """(the open record ``handle``'s whole bytes as checked, ``data`` as it may be appended to them) (``append_held``):
    refused (``ChangedRecord``) where the record cannot be read, does not begin with what was held or marked, or is
    not whole; ``data`` after a newline where its whole last line has none."""
    try:
        found = _read_whole(handle)
    except OSError as error:
        raise ChangedRecord(f"{path}: it is there but cannot be read ({reason(error)})") from error
    for what, kept in (("held when it was last read or written", held), (f"its mark ({mark_of(path).name}) "
                                                                         "records written to it", mark)):
        if kept is not None and not kept.begins(found):
            raise ChangedRecord(f"{path}: it no longer begins with the {kept.size} bytes it {what} (it was "
                                "replaced, emptied or cut short)")
    try:
        whole(found, path)
    except ValueError as error:
        raise ChangedRecord(f"{path}: nothing is written after what it holds, which is not whole: {error}") from error
    return found, b"\n" + data if data and found and not found.endswith(b"\n") else data


def mark_of(path: Path | str) -> Path:
    """Where an append-only record's mark is (``marked``): beside it, its name with ``.held`` added."""
    path = Path(path)
    return path.with_name(f"{path.name}.held")


def marked(path: Path | str, folder: int | None = None) -> Held | None:
    """What an append-only record held when a writer last appended to it (``append_held``), as recorded beside it
    (``mark_of``): its whole bytes then, by length and SHA-256. The mark is written after each append, so a record
    read after its mark begins with what the mark records, unless it was replaced, emptied, cut short or removed since:
    a second record that tells a record of money still being written from one put in its place (DO-01). None where no
    mark is (a record from before marks, or never appended to by ``append_held``); ``ValueError`` where a mark is there
    but cannot be read, or is not a mark. ``folder``: as ``absent``'s."""
    mark = mark_of(path)
    if absent(mark, folder):
        return None
    try:
        name, at = _in(mark, folder)
        handle = os.open(name, os.O_RDONLY, dir_fd=at)
        try:
            found = json.loads(_read_whole(handle))
        finally:
            os.close(handle)
        size, sha256 = found["size"], found["sha256"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0 or not isinstance(sha256, str) \
                or len(sha256) != 64 or set(sha256) - set("0123456789abcdef"):
            raise ValueError("not a length and a SHA-256")
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise ValueError(f"{mark}: the mark of what {Path(path).name} held when last written cannot be read "
                         f"({linked(mark, folder)}{reason(error)})") from error
    return Held(size, sha256)


def _unopened(path: Path, held: Held | None, error: OSError, folder: int) -> str:
    """Why an append-only record could not be opened to append to (``append_held``), as found in ``folder``, the folder
    locked (``_in``)."""
    if held is None and isinstance(error, FileExistsError):
        found = linked(path, folder)[:-2] if linked(path, folder) else "an entry"
        return f"{path}: {found} is there now, where nothing was when it was read"
    if held is not None and absent(path, folder):
        return f"{path}: nothing is there now, where it held {held.size} bytes when it was last read or written"
    return f"{path}: it is there but cannot be opened ({linked(path, folder)}{reason(error)})"


def _read_whole(handle: int) -> bytes:
    """An open file's whole bytes, from its start."""
    chunks, offset = [], 0
    while chunk := os.pread(handle, 1 << 20, offset):
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


UNSUPPORTED_FOLDER_SYNC =frozenset({errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP})
folder_sync_unsupported: dict[str, str] = {}     # each folder whose filesystem cannot sync a directory, and why


def _sync_folder(folder: Path, opened: int | None = None) -> None:
    """Sync a folder's entries to the disk (the replacement's name). A filesystem or platform that does not support
    syncing a directory (``UNSUPPORTED_FOLDER_SYNC``: EINVAL, ENOTSUP; a platform that cannot open one) is tolerated
    and stated: the folder is named in ``folder_sync_unsupported`` and a warning is issued once for it; the record is
    then replaced whole, but its new name may not survive a power loss. Any other error (an I/O error) is raised: the
    record was replaced, but whether its name is on the disk is not known. ``opened``: the folder already open (the
    folder a writer holds the lock of, synced wherever it is now: ``_in``)."""
    if os.name == "nt":                          # a directory cannot be opened for syncing there
        return _unsupported(folder, "this platform cannot sync a directory")
    try:
        handle = os.open(folder, os.O_RDONLY) if opened is None else opened
    except OSError as error:
        if error.errno in UNSUPPORTED_FOLDER_SYNC:
            return _unsupported(folder, f"{errno.errorcode.get(error.errno, error.errno)}: {error.strerror}")
        raise
    try:
        os.fsync(handle)
    except OSError as error:
        if error.errno not in UNSUPPORTED_FOLDER_SYNC:
            raise
        _unsupported(folder, f"{errno.errorcode.get(error.errno, error.errno)}: {error.strerror}")
    finally:
        if opened is None:
            os.close(handle)


def _unsupported(folder: Path, why: str) -> None:
    """Record and state, once per folder, that its directory sync is not supported (``_sync_folder``)."""
    import warnings
    key = str(folder)
    if key not in folder_sync_unsupported:
        folder_sync_unsupported[key] = why
        warnings.warn(f"{folder}: the filesystem does not support syncing a directory ({why}); records here are "
                      "replaced whole, but a new name may not survive a power loss", RuntimeWarning, stacklevel=3)


@contextlib.contextmanager
def lock(path: Path | str):
    """An exclusive lock on ``path`` (a lock file, made if absent), waited for: held across a read-modify-write of a
    shared record, so that two writers never lose each other's update."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


PUBLICATION_LOCK = ".study.lock"      # a study folder's publication lock (``publishing``)
PUBLISH_WAIT = 60.0                   # seconds a writer waits for another's publication into its folder to end


class Busy(ValueError):
    """A folder another writer is publishing into, or that a run owns (a reanalysis, until it ends): nothing is written
    into it (``publishing``; DE-02)."""


@dataclass
class Claim:
    """A folder's publication, held (``publishing``): its holder passes it to its own writers' parts, which then write
    under it; any other writer, in this process or another, waits for it or is refused. ``drawn``: each figure its
    holder drew into the folder (its resolved path: the SHA-256 of the bytes written), which its report is bound to
    (``evidence.bindings``; DF-01)."""
    folder: Path
    stream: object
    thread: int
    drawn: dict[str, str] = field(default_factory=dict)


_HELD: dict[Path, Claim] = {}
_HELD_GUARD = threading.Lock()


@contextlib.contextmanager
def publishing(folder: Path | str, claim: Claim | None = None, wait: float = PUBLISH_WAIT):
    """A study folder's publication, held for its writer (``PUBLICATION_LOCK``, an exclusive lock its every writer
    takes: ``build.publish``, ``build.save``, ``studies.save``, ``runs._write``, a reanalysis's run; and each run that
    writes into a study's folder, from before its first file: ``track1.run``, ``single_idea.run``, the native fit and
    coverage, the wrappers in ``runs``, a promotion's children; DF-01). ``claim``: the
    writer's own, held already (its parts write under it). Otherwise the lock is taken, waiting up to ``wait`` seconds
    for another writer's publication to end; then ``Busy``, nothing written. A writer of this very thread holding it
    and not passing it is another version's, written inside a publication, and is refused at once (it cannot wait for
    itself). The lock does not bind a process outside ADROIT's writers: a file changed by hand is detected by its
    readers (``evidence.version``), not prevented."""
    folder = Path(folder).resolve()
    if claim is not None and claim.folder == folder:
        yield claim
        return
    with _HELD_GUARD:
        holder = _HELD.get(folder)
    if holder is not None and holder.thread == threading.get_ident():
        raise Busy(f"{folder} is being published by another writer of this process: another version is not written "
                   "into it meanwhile; nothing was written")
    folder.mkdir(parents=True, exist_ok=True)
    stream = (folder / PUBLICATION_LOCK).open("a")
    deadline = time.monotonic() + wait
    while True:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                stream.close()
                raise Busy(f"another writer is publishing into {folder}, or a run owns it until it ends (a "
                           f"reanalysis, say){f', for more than {wait:g} s' if wait else ''}: nothing was written; "
                           "write into another folder, or again once it is done") from None
            time.sleep(0.05)
    held = Claim(folder, stream, threading.get_ident())
    with _HELD_GUARD:
        _HELD[folder] = held
    try:
        yield held
    finally:
        with _HELD_GUARD:
            if _HELD.get(folder) is held:
                del _HELD[folder]
        fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


STUDY_FILES = ("result.json", "study.json")    # a saved study's own records: an export never writes beside them
INCOMPLETE = "EXPORT_INCOMPLETE.txt"           # in a folder whose export's writer stopped while replacing its files
RECORD = "EXPORT_FILES.json"                   # in a folder exports wrote: each whole export's files, and their digests


class ExportFailed(OSError):
    """An export that could not be written (``export``): the folder's earlier files were put back as they were."""


def export(folder: Path | str, members: dict[str, str | bytes | None], wait: float = PUBLISH_WAIT,
           fresh=None) -> Path:
    """An export of several files into a folder a person names (``--out``: a curated record's review packet, a review
    queue, a theory check's or the neutrino fog's results, a session command's draft or report with its request
    record), each member prepared whole before anything is written: written under one hold of the folder
    (``publishing``), from the first member to the last, each to its own entry (``write_atomic``: a link there is
    replaced, never written through to its target), and a member with nothing to write (None) has its entry removed,
    so that no earlier export's file is left beside this one's. Another export into the folder waits for it, then
    replaces it whole. Refused (``ValueError``, nothing written) in a folder that holds a saved study
    (``STUDY_FILES``): its report would be replaced (the auditor's DI recheck, DJ-01, 2026-11-07: two curated review exports
    into one folder had left one record's packet beside another's report and curve, and each member had been written
    through a link into a folder another writer held). Returns the folder, resolved.

    Its failure contract (the auditor's DJ recheck, DK-05, 2026-11-07: a write that failed partway had left B's record beside
    A's report and figure, looking complete). When the export returns, the folder holds this export whole. When it
    raises, the folder holds what it held before, whole: each entry it replaces is kept first (a file's bytes, a
    link's target) and, on any failure, every entry it reached and changed is put back as it was, one it never
    replaced left alone (``ExportFailed``, saying so, for a failed write). Two failures are said apart, the folder then
    marked incomplete (``ExportFailed``, saying so): an entry that could not be put back; and the mark itself, which
    could not be removed or rewritten once this export's last file was written (the auditor's DK recheck, DL-03).

    A writer killed partway cannot put anything back: before its first entry is replaced the folder gains
    ``INCOMPLETE``, naming the export's files, so that a folder whose writer stopped says so to a person, and every
    ADROIT reader of an export's files (``interrupted``) reads it as incomplete. The mark names each interrupted
    export's files, and an export removes from it only the interrupted exports whose every file it has written whole
    again: another export into the folder, of other files, keeps the mark (the auditor's DK recheck, DL-02, 2026-11-07: a
    review queue exported beside a review packet whose writer had been killed had removed the mark, and the packet,
    one review's record beside another's report and figure, then read as whole).

    Its files are its own, and another export's are left whole (the auditor's DL recheck, DM-03, 2026-11-07: a review queue
    exported as ``report.json`` beside a curated review packet had replaced the packet's ``report.md``, and the packet,
    one record's review beside the queue's report, then read as whole). Once its files are written, the folder's
    ``RECORD`` names them and their digests, beside each other export there that shares no file with it. An export
    replaces only files that ``RECORD`` names, and only all of one export's together: refused (``ValueError``, nothing
    written, saying which) where it would leave part of a recorded export beside its own (one sharing a file with it
    whose other files are still there), or replace an entry that no export recorded there wrote (an earlier ADROIT's
    export, a person's file, a link) and that no interrupted export named, or where ``RECORD`` cannot be read. Its
    readers (``exported``) read a file as one whole export's only where ``RECORD`` names it, and every file of its
    export is as written. ``fresh``: a test of the folder (``runs.fresh``) made again once it is held, for an export
    that writes only into a new or empty folder; one that fails it is refused, nothing written."""
    folder = Path(folder)
    if reserved := sorted({INCOMPLETE, RECORD} & set(members)):
        raise ValueError(f"an export cannot write {', '.join(reserved)}: ADROIT keeps that file in the folder")
    with publishing(folder, wait=wait) as claim:
        not_a_study(claim.folder)
        if fresh is not None and not fresh(claim.folder):
            raise ValueError(f"{claim.folder} is no longer new or empty: another wrote there meanwhile; nothing was "
                             "written")
        earlier = _interrupted_exports(claim.folder)
        others = _others(claim.folder, members, earlier)
        names = [*dict.fromkeys([*members, INCOMPLETE])]
        before = {name: _kept(claim.folder / name) for name in names}
        reached: list[str] = []
        try:
            write_atomic(claim.folder / INCOMPLETE, _incomplete([*earlier, tuple(members)]))
            for name, data in members.items():
                reached.append(name)
                path = claim.folder / name
                if data is not None:
                    write_atomic(path, data)
                elif os.path.lexists(path):
                    path.unlink()                              # the entry itself: a link, not its target
        except BaseException as error:
            failed = []
            for name in [*reached, INCOMPLETE]:                # each entry reached, the mark last: kept if any fails
                try:
                    if (name != INCOMPLETE or not failed) and _changed(claim.folder / name, before[name]):
                        _put_back(claim.folder / name, before[name])           # one never replaced is left as it is
                except OSError as again:
                    failed.append(f"{name}: {again}")
            if failed:
                raise ExportFailed(f"the export into {claim.folder} failed ({error}), and its earlier files could not "
                                   f"all be put back ({'; '.join(failed)}): the folder is incomplete ({INCOMPLETE}); "
                                   "export again, or discard it") from error
            if isinstance(error, OSError):
                raise ExportFailed(f"the export into {claim.folder} failed ({error}): nothing of it was kept; the "
                                   "folder's earlier files were put back as they were") from error
            raise
        _finished(claim.folder, members, [names for names in earlier if not names or not set(names) <= set(members)],
                  [*others, {name: _digest_of(data) for name, data in members.items()}])
    return claim.folder


def _finished(folder: Path, members: dict, remaining: list[tuple[str, ...]], recorded: list[dict]) -> None:
    """``export``'s last steps: ``RECORD`` written to name its files beside the other exports it left (``recorded``),
    then its mark removed, or rewritten to name the interrupted exports it did not write again (``remaining``); where
    either fails, ``ExportFailed``, saying the export's files were written and the folder still reads as incomplete
    (the auditor's DK recheck, DL-03: an ordinary I/O error had been raised)."""
    try:
        write_atomic(folder / RECORD, _record(recorded))
    except OSError as error:
        raise ExportFailed(f"the export into {folder} wrote each of its files ({', '.join(members)}), but the record "
                           f"of them ({RECORD}) could not be written ({error}): the folder reads as incomplete "
                           f"({INCOMPLETE}); export again into it, or discard it") from error
    try:
        if remaining:
            write_atomic(folder / INCOMPLETE, _incomplete(remaining))
        else:
            (folder / INCOMPLETE).unlink(missing_ok=True)
    except OSError as error:
        raise ExportFailed(f"the export into {folder} wrote each of its files ({', '.join(members)}), but its mark "
                           f"({INCOMPLETE}) could not be {'rewritten' if remaining else 'removed'} ({error}): the "
                           "folder reads as incomplete; export again into it, or discard it") from error


def interrupted(folder: Path | str) -> bool:
    """Whether a folder's export was interrupted (``export``'s ``INCOMPLETE``): its files may be of two exports, and
    are read as incomplete."""
    return os.path.lexists(Path(folder) / INCOMPLETE)


def exported(folder: Path | str, name: str, data: bytes | None = None) -> str:
    """Why ``name`` in ``folder`` is not one whole export's file, or "" where it is (``export``, DM-03): ``RECORD``
    names it, and every file of its export is as that export wrote it (a file it removed still absent), the folder not
    interrupted. ``data``: ``name``'s bytes as its reader read them, checked in place of reading it again."""
    folder = Path(folder)
    if interrupted(folder):
        return f"the export holding {name} was interrupted ({INCOMPLETE} beside it): its files may be of two exports"
    exports, why = _read_record(folder)
    if why:
        return why
    files = next((files for files in exports if name in files), None)
    if files is None:
        return (f"no export recorded in its folder ({RECORD}) wrote {name}: it may be an earlier ADROIT's export's, "
                "or beside another export's files")
    changed = [n for n, digest in files.items()
               if (_digest_of(data) if n == name and data is not None else _digest(folder / n)) != digest]
    return (f"{', '.join(changed)} {'is' if len(changed) == 1 else 'are'} no longer as the export of {name} wrote "
            f"{'it' if len(changed) == 1 else 'them'}: its folder no longer holds that export whole") if changed else ""


def _others(folder: Path, members: dict, interrupted_exports: list[tuple[str, ...]]) -> list[dict]:
    """The exports ``RECORD`` names that ``export`` leaves as they are: each sharing no file with ``members``. Refused
    (``ValueError``, saying which) where the export would leave part of a recorded one beside its own: one sharing a
    file with it whose other files are still there (DM-03); or replace an entry ``RECORD`` does not name, and no
    interrupted export named (an earlier ADROIT's export, a person's file, a link); or where ``RECORD`` cannot be
    read. A recorded export whose every file it writes again, or whose other files are gone, is replaced."""
    exports, why = _read_record(folder)
    if why:
        raise ValueError(f"{why}: an export into {folder} cannot tell another's files from its own; nothing was written. "
                         "Export into another folder")
    mine, kept, replaced = set(members), [], set()
    for files in exports:
        if not mine & set(files):
            kept.append(files)
            continue
        if left := sorted(n for n in set(files) - mine if os.path.lexists(folder / n)):
            raise ValueError(f"{folder} holds another export ({', '.join(files)}): this one would replace its "
                             f"{', '.join(sorted(mine & set(files)))} and leave its {', '.join(left)} beside its own "
                             "files; nothing was written. Export into another folder")
        replaced |= set(files)
    named = {n for names in interrupted_exports for n in names}
    if strangers := sorted(n for n in members if os.path.lexists(folder / n) and n not in replaced | named):
        raise ValueError(f"{folder} holds {', '.join(strangers)}, which no export recorded there ({RECORD}) wrote (an "
                         "earlier ADROIT's export, or another file): an export does not replace it; nothing was "
                         "written. Export into another folder, or remove it first")
    return kept


ABOUT = ("ADROIT's record of the exports written whole into this folder: each export's files, with the SHA-256 of "
         "each (null: a file it removed). An export replaces only files named here, and only all of one export's "
         "together; ADROIT reads a file as an export's only while every file of that export is as written.")


def _record(exports: list[dict]) -> str:
    """``RECORD``'s text: each export's files and their digests (``_read_record`` reads it back)."""
    import json
    return json.dumps({"about": ABOUT, "exports": [{"files": files} for files in exports]}, indent=1) + "\n"


def _read_record(folder: Path) -> tuple[list[dict], str]:
    """(each export ``RECORD`` names, by its files and their digests; why it cannot be read, or ""). None where there
    is no record. A link, or a file ADROIT did not write, cannot be read as it."""
    import json
    path = Path(folder) / RECORD
    if not os.path.lexists(path):
        return [], ""
    why = f"the folder's record of its exports ({RECORD}) cannot be read"
    if os.path.islink(path):
        return [], f"{why} (it is a link)"
    try:
        exports = [entry["files"] for entry in json.loads(path.read_text())["exports"]]
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [], f"{why} ({type(error).__name__}: {error})"
    if not all(isinstance(files, dict) and files and all(
            isinstance(n, str) and (d is None or isinstance(d, str)) for n, d in files.items()) for files in exports):
        return [], f"{why} (an export in it is not a set of files and digests)"
    return exports, ""


def _digest_of(data: str | bytes | None) -> str | None:
    """A member's SHA-256, as ``RECORD`` holds it; None for one removed."""
    import hashlib
    return None if data is None else hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def _digest(path: Path) -> str | None:
    """An entry's SHA-256, None where there is none; a link, or what cannot be read, matches no digest."""
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        return "a link"
    try:
        return _digest_of(path.read_bytes())
    except OSError as error:
        return f"unreadable ({error})"


INTERRUPTED_LINE = "Interrupted exports' files (for ADROIT): "


def _incomplete(exports: list[tuple[str, ...]]) -> str:
    """The mark's words: each interrupted export's files, and the same as one line ADROIT reads back
    (``_interrupted_exports``)."""
    import json
    said = [("An export into this folder was interrupted while it was replacing these files, so they may be from two "
             f"exports: {', '.join(names)}. Export them again into this folder, or discard it.") if names else
            ("An export into this folder was interrupted, and which of its files it had replaced is not recorded: "
             "discard the folder, or remove this file once you have checked them.") for names in exports]
    return "\n".join([*said, "(ADROIT removes this file once an export has written each interrupted export's files "
                      "whole again.)", INTERRUPTED_LINE + json.dumps([list(names) for names in exports])]) + "\n"


def _interrupted_exports(folder: Path) -> list[tuple[str, ...]]:
    """The interrupted exports a folder's mark names, each by its files; one whose files cannot be read from it (a
    mark ADROIT did not write, or damaged) as ``()``, which no export removes."""
    import json
    import re
    path = folder / INCOMPLETE
    if not os.path.lexists(path):
        return []
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return [()]
    line = next((line for line in reversed(text.splitlines()) if line.startswith(INTERRUPTED_LINE)), None)
    try:
        exports = json.loads(line[len(INTERRUPTED_LINE):]) if line is not None else None
    except ValueError:
        exports = None
    if isinstance(exports, list) and exports and all(
            isinstance(names, list) and all(isinstance(n, str) for n in names) for names in exports):
        return [tuple(names) for names in exports]
    found = re.search(r"so they may be from two exports: (.+?)\. Export again", text)     # a mark of 9055e67's
    return [tuple(found.group(1).split(", "))] if found else [()]


def _kept(path: Path) -> tuple[str, bytes | str] | None:
    """A directory entry as it is (``export``): a link's target, a file's bytes, or None where there is none."""
    if os.path.islink(path):
        return "link", os.readlink(path)
    return ("file", path.read_bytes()) if os.path.lexists(path) else None


def _changed(path: Path, kept: tuple[str, bytes | str] | None) -> bool:
    """Whether a directory entry is no longer as ``_kept`` found it (one that cannot be read is)."""
    try:
        return _kept(path) != kept
    except OSError:
        return True


def _put_back(path: Path, kept: tuple[str, bytes | str] | None) -> None:
    """A directory entry put back as ``_kept`` found it, replacing what is there now."""
    if kept is None:
        if os.path.lexists(path):
            path.unlink()
        return
    kind, value = kept
    if kind == "file":
        write_atomic(path, value)
        return
    staged = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.link")
    with contextlib.suppress(FileNotFoundError):
        staged.unlink()
    os.symlink(value, staged)
    os.replace(staged, path)


def not_a_study(folder: Path | str | None) -> None:
    """Refuse (``ValueError``) an export's folder that holds a saved study (``STUDY_FILES``; ``export``): a paid
    command checks it before its request is sent, so that nothing is spent on an output it would refuse."""
    if folder is None:
        return
    held = next((name for name in STUDY_FILES if os.path.lexists(Path(folder) / name)), None)
    if held is not None:
        raise ValueError(f"{folder} holds a saved study ({held}): write the export into a folder of its own; nothing "
                         "was written")


def entry(path: Path | str) -> Path:
    """The directory entry ``path`` names, its folder resolved and its own name kept: the entry an atomic write
    replaces (``write_atomic``), never a link's target, whose folder may be another (the auditor's DG recheck, DH-04,
    2026-11-06: a figure that was a link had been drawn under its target folder's lock, over an entry in a folder
    another writer held)."""
    path = Path(path)
    return path.parent.resolve() / path.name


def holding(path: Path | str) -> Claim | None:
    """The hold this thread's writer has of the folder ``path`` is in (``publishing``; the folder of its entry,
    ``entry``), or None (DF-01)."""
    folder = entry(path).parent
    with _HELD_GUARD:
        claim = _HELD.get(folder)
    return claim if claim is not None and claim.thread == threading.get_ident() else None


def lock_for(path: Path | str) -> Path:
    """The lock file for a record that lives where nothing else may be written (``records.yaml`` in the package):
    in the runs folder's ``.adroit/locks``, named by the record's resolved path, so the checkout gains no file."""
    import hashlib
    from adroit.core.config import get_settings
    key = hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()[:24]
    return get_settings().runs_dir / ".adroit" / "locks" / f"{Path(path).name}.{key}.lock"

"""Atomic request reservations shared by the clients of one paid command."""

from __future__ import annotations

import json
import math
import threading
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from adroit.core.durable import Held
from adroit.core.state import StrictModel


class BudgetExceeded(RuntimeError):
    """A request cannot fit within the remaining committed budget."""

    def __init__(self, spent: float, budget: float, required: float = 0.0) -> None:
        super().__init__(f"LLM budget stopped before dispatch: ${spent:.6f} committed of "
                         f"${budget:.6f}; next request needs up to ${required:.6f}")
        self.spent, self.budget, self.required = spent, budget, required
        self.ledger_path: str | None = None


class BudgetAccount:
    """One command's total cap and optional independent provider caps.

    Outstanding requests and requests with uncertain billing retain their full
    reservation. Only a response carrying usage can settle it down to actual cost.
    """

    def __init__(self, cap: float | None = None,
                 provider_caps: dict[str, float] | None = None) -> None:
        for value in [cap, *(provider_caps or {}).values()]:
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("Budgets must be finite and nonnegative")
        self.cap = cap
        self.provider_caps = dict(provider_caps or {})
        self.spent: dict[str, float] = {}
        self.reservations: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        # the paid ledger it was rebuilt from (``model_intake.Intake.account``), and what that ledger held as read:
        # what a client appending to it must find it still begins with (the auditor's DN recheck, DO-01, 2026-11-08)
        self.journal: Path | None = None
        self.held: Held | None = None
        # why a write to its paid ledger failed once begun, or an entry of a request already sent was not journalled,
        # or "": what the ledger holds is then not known to it, and it reserves, and its clients send, nothing more
        # (``reserve``; ``BudgetedLLMClient.request``; the auditor's DO recheck, DP-01, and DP recheck, DQ-01, 2026-11-09)
        self.unjournalled = ""
        # the whole-ledger check its clients append to its own ledger (``journal``) under: a session's, its cap raises
        # its record's (``model_intake.Intake.account``; DQ-03); None: ``journal_whole``
        self.whole: Callable[[bytes, Path], None] | None = None

    def committed(self) -> float:
        """Settled plus outstanding costs: what counts against the cap now."""
        with self._lock:
            return sum(self.spent.values()) + sum(v for _, v in self.reservations.values())

    def reserve(self, provider: str, cost: float) -> str:
        """Atomically reserve a bounded request, refusing it before dispatch."""
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("Cannot bound request cost")
        with self._lock:
            if self.unjournalled:
                raise UnknownLedger(self.unjournalled)
            committed = sum(self.spent.values()) + sum(v for _, v in self.reservations.values())
            if self.cap is not None and committed + cost > self.cap:
                raise BudgetExceeded(committed, self.cap, cost)
            used = self.spent.get(provider, 0) + sum(
                v for p, v in self.reservations.values() if p == provider)
            cap = self.provider_caps.get(provider)
            if cap is not None and used + cost > cap:
                raise BudgetExceeded(used, cap, cost)
            key = uuid4().hex
            self.reservations[key] = (provider, cost)
            return key

    def settle(self, key: str, actual: float) -> None:
        """Replace a reservation with billed usage; never discard a paid answer."""
        if not math.isfinite(actual) or actual < 0:
            raise ValueError("Billed usage must be finite and nonnegative")
        with self._lock:
            provider, bound = self.reservations.pop(key)
            self.spent[provider] = self.spent.get(provider, 0) + actual
            if actual > bound:
                self.provider_caps[provider] = self.spent[provider]

    def release(self, key: str) -> None:
        """Release a request cancelled before dispatch (never an uncertain bill)."""
        with self._lock:
            self.reservations.pop(key)


class UnknownLedger(ValueError):
    """An account whose paid ledger's last write failed once begun, or one of whose requests already sent could not
    have an entry journalled (``BudgetedLLMClient._journal``): the ledger may hold part or all of a line its account
    does not, or less than happened, so the account reserves, and its clients send, nothing more (the auditor's DO recheck,
    DP-01, 2026-11-09: a reservation written whole whose sync then failed had been released from the live account and
    kept in the ledger, and the next request was sent, the two accounts apart). What it reserved is kept, uncertain, as
    the ledger may hold it, a request reserved before and not yet sent among it (DQ-04); the session is read again from
    its ledger for its next step."""

    def __init__(self, why: str):
        super().__init__(f"{why}: what the paid ledger holds is not known to this command, so nothing more is reserved "
                         "or sent under its account; what it reserved stays reserved, uncertain. Run the step again: "
                         "its account is read from the ledger (a torn last line is named there, with its recovery)")


class LedgerRequest(StrictModel):
    """One request in a paid ledger: its provider and model, the bound reserved before dispatch, and whether its bill
    is settled (``cost_usd``), uncertain (no usage known: the reservation stays committed) or open (reserved, no
    answer journalled yet)."""
    request_id: str
    provider: str
    model: str = ''
    reserved_usd: float
    state: str = 'open'              # open, settled or uncertain
    cost_usd: float | None = None
    bound_exceeded: bool = False     # its settled cost exceeded its bound: the provider is frozen there
    settled_line: int | None = None  # the journal line that settled it (the provider caps follow settlement order)


LEDGER_STATES = ('reserved', 'received', 'settled', 'billing_uncertain', 'background_received', 'cap_raised',
                 'recovered', 'opened')


class MissingJournal(ValueError):
    """A session's paid journal that should exist and does not (the auditor's consolidation audit, CO-05, 2026-10-25: a
    lost journal had read as an empty one, the session's approved cap restored in full, so that a request beyond it
    was sent). What the session spent cannot be known without it: its budget stays blocked, and a new or empty
    journal is never made in its place, by a request or by ``recover_torn_tail``."""

    def __init__(self, path: Path, evidence: list[str]):
        self.path, self.evidence = Path(path), list(evidence)
        super().__init__(f"the session's paid ledger {path} is missing, although {'; '.join(evidence)}: what the "
                         "session spent cannot be known, so its budget is blocked and nothing more is sent. Restore "
                         "the original ledger file to continue; no new or empty ledger is made in its place, and "
                         "`adroit ledger recover` cannot recreate it")


class TornLedger(ValueError):
    """A paid journal whose last line was cut short while it was written (a crash mid-write): named, with the
    recovery command, never read past or repaired silently (the owner's direction D-7, 2026-10-25)."""

    def __init__(self, path: Path, number: int):
        self.path, self.number = Path(path), number
        super().__init__(f"paid ledger line {number} is torn (cut short while it was written, nothing after it): "
                         f"recover it with `adroit ledger recover {path}`, which keeps the original bytes and every "
                         "reservation and never resends a request")


def read_ledger(path: Path) -> dict[str, LedgerRequest]:
    """Every request of a paid ledger (``BudgetedLLMClient``'s journal) by its identifier; a missing ledger has none.
    Read-only. The journal is checked as its writer keeps it (``BudgetedLLMClient.request``): a request is reserved
    once, with a finite, nonnegative bound, before anything else is journalled for it; it is settled at most once, with
    a finite, nonnegative cost, and nothing follows its settlement; a response kept while a background request is
    polled (``background_received``, which carries no identifier) is journalled while one is open. A ledger that breaks
    this is damaged, not empty (the combined audit's V1-03, 2026-10-24: a settlement without its reservation had been
    skipped, and a ledger holding a charge read as one with no request; the consistency audit's CA-06: a background
    response with no open request had been skipped, and the run read as having sent nothing). Every reader of a paid
    ledger's money reads it here: the run pages, the session accounts (``model_intake.Intake.account``) and a budget
    stop's record.

    Raises:
        ValueError: if a line is not a journal entry, or the journal is not one its writer could have kept.
    """
    return read_owned(path)[0]


def read_owned(path: Path) -> tuple[dict[str, LedgerRequest], list[str]]:
    """``read_ledger``, and the runs that opened the ledger (its ``opened`` entries' attempts, in order: a workbench
    job's own ledger, ``preflight.open_job_ledger``), both of one reading of its bytes, so that the requests counted are
    those of the run it names (the auditor's DD recheck, DE-01, 2026-11-05). A ledger from before names none."""
    path = Path(path)
    opened: list[str] = []
    return _read_text(ledger_text(path), path, opened), opened


def read_raised(path: Path) -> tuple[dict[str, LedgerRequest], list[dict]]:
    """``read_ledger``, and the cap raises it journals (its ``cap_raised`` entries, in order, each without its
    state), both of one reading of its bytes: a session's spending and the cap changes it was spent under (the auditor's DF
    recheck, DG-01, 2026-11-06; ``model_intake.Intake.snapshot``). A missing ledger has neither."""
    requests, raised, _ = read_held(path)
    return requests, raised


def read_held(path: Path) -> tuple[dict[str, LedgerRequest], list[dict], Held | None]:
    """``read_raised``, and what the ledger held as read (``durable.Held``; None where nothing at all is at its path),
    all of one reading of its bytes: what a session's account is rebuilt from, and what a client appending to the
    ledger must find it still begins with (``durable.append_held``; the auditor's DN recheck, DO-01, 2026-11-08)."""
    from adroit.core.durable import absent
    path = Path(path)
    there = not absent(path)
    data = ledger_bytes(path)
    raised: list[dict] = []
    return _read_text(_text(data), path, raised=raised), raised, Held.of(data) if there else None


def ledger_held(path: Path) -> Held | None:
    """What a paid ledger holds now (``durable.Held``): None where nothing at all is at its path; ``ValueError`` where
    an entry there cannot be read, or it is not what its mark records (``ledger_bytes``)."""
    from adroit.core.durable import absent
    data = ledger_bytes(Path(path))
    return None if absent(path) else Held.of(data)


# each workbench job's paid ledger this process opened (``preflight.open_job_ledger``), by its absolute path, and what
# it held once opened: what the run's budgeted client must find it still begins with (DO-01)
OPENED: dict[str, Held] = {}


UNJOURNALLED = ".unjournalled-"     # a notice beside a paid ledger: a request sent through it lacks an entry (DV-02)


def leave_unjournalled(ledger: Path, request: str, state: str, why: str) -> str:
    """Leave beside the paid ledger ``ledger``, by its path (in the folder there now), a notice that the request
    ``request``, sent through it, has an entry (``state``) its client could not journal, and why, with the run's
    attempt: the ledger holds less than was spent (the auditor's DU recheck, DV-02, 2026-11-10: the journal's folder replaced
    by an older coherent copy once its append was acknowledged, the request had been sent, its next entry refused, and
    every later reading had read the copy as all that was spent). Made anew, never over another, synced. Every reading
    of the ledger then refuses it (``ledger_bytes``, ``unjournalled``): no total is read from it as complete, no
    account rebuilt from it, nothing appended to it, until a person reconciles it with the provider's records and
    removes the notice. "" once left; else why it could not be (its folder gone, say)."""
    import json
    import os
    from adroit.core.chronology import utc_now
    from adroit.core.durable import reason
    notice = Path(ledger).parent / f"{Path(ledger).name}{UNJOURNALLED}{request or 'unknown'}.json"
    body = json.dumps({"ledger": str(ledger), "request": request, "entry": state, "why": why, "at": utc_now(),
                       "attempt": os.environ.get("ADROIT_JOB_ATTEMPT", "")}, sort_keys=True).encode()
    try:
        handle = os.open(notice, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        return ""                                   # this request's notice is there already
    except OSError as error:
        return f"no notice could be left beside it ({reason(error)})"
    try:
        os.write(handle, body)
        os.fsync(handle)
    except OSError as error:
        return f"its notice may be incomplete ({reason(error)})"
    finally:
        os.close(handle)
    return ""


def unjournalled(path: Path, folder: int | None = None) -> str:
    """Why the paid ledger at ``path`` holds less than was spent, read from the notices beside it
    (``leave_unjournalled``), "" where there is none: listed in ``folder``, the open folder its reader has locked,
    where given (``durable._in``), else in the folder at its path."""
    import json
    import os
    path = Path(path)
    prefix = f"{path.name}{UNJOURNALLED}"
    try:
        names = sorted(n for n in os.listdir(folder if folder is not None else path.parent) if n.startswith(prefix))
    except OSError:
        return ""
    if not names:
        return ""
    try:
        first = json.loads((path.parent / names[0]).read_text()) if folder is None else {}
        said = f": its {first['entry']} entry, {first['why']}" if first else ""
    except (OSError, ValueError, KeyError, TypeError):
        said = ""
    return (f"{path}: {len(names)} request(s) sent through this paid ledger have an entry their client could not "
            f"journal ({names[0]}{said}): it holds less than was spent, and what was spent is not known; reconcile it "
            "with the provider's records, then remove the notice(s)")


def ledger_text(path: Path) -> str:
    """A paid ledger's text (``ledger_bytes``), as ``Path.read_text`` reads it."""
    return _text(ledger_bytes(path))


def ledger_bytes(path: Path, folder: int | None = None) -> bytes:
    """A paid ledger's bytes: b"" where nothing at all is at its path (``durable.absent``: there is no ledger). An
    entry there that cannot be read, a link to a missing file among them, is a damaged ledger (``ValueError``), never
    an empty one: what it holds may be what was spent (the auditor's DM recheck, DN-01, 2026-11-08: ``Path.exists`` had read
    a link to nothing as no ledger). So is one that does not begin with what its writers last wrote to it, as the mark
    beside it records (``durable.marked``, read before it): one emptied, replaced or cut short since, and one missing
    beside its mark (the auditor's DN recheck, DO-01, 2026-11-08: an empty file put in a session's ledger's place had read as
    a session that had spent nothing). It is read only by its own name (``durable.read_own``): a link to a ledger, and
    a ledger whose file has another name (a hard link), cannot be read, as they cannot be written to: the mark beside
    the name read would not be its writers' (the auditor's DS recheck, DT-01, 2026-11-10). ``folder``: the open folder it is
    in, whose writers' lock its reader holds (``durable.writing``), in which it and its mark are read by their names
    (``durable._in``; the auditor's DT recheck, DU-01, 2026-11-10)."""
    from adroit.core.durable import absent, linked, mark_of, marked, read_own, reason
    path = Path(path)
    if notices := unjournalled(path, folder):
        raise ValueError(notices)
    mark = marked(path, folder)         # read first: a mark is written after its ledger, never ahead of it
    if absent(path, folder):
        if mark is not None and mark.size:
            raise ValueError(f"{path}: the paid ledger is missing, although the mark beside it ({mark_of(path).name}) "
                             f"records {mark.size} bytes written to it: what it records was spent is not known")
        return b""
    try:
        data = read_own(path, folder)
    except OSError as error:
        raise ValueError(f"{path}: the paid ledger is there but cannot be read ({linked(path, folder)}"
                         f"{reason(error)}): what it records was spent is not known") from error
    except ValueError as error:
        raise ValueError(f"{path}: the paid ledger is there but cannot be read ({error}): what it records was spent is "
                         "not known") from error
    if mark is not None and not mark.begins(data):
        raise ValueError(f"{path}: the paid ledger does not begin with the {mark.size} bytes last written to it, as the "
                         f"mark beside it ({mark_of(path).name}) records (it holds {len(data)}): it was replaced, emptied "
                         "or cut short since, and what it records was spent is not known")
    return data


def journal_whole(data: bytes, path: Path) -> None:
    """``ValueError`` where a paid ledger's whole bytes are not a journal its writers could have kept (``read_ledger``'s
    rules): a torn last line (``TornLedger``, naming its recovery), a line that is not one of its entries, entries out
    of their writers' order. What each writer of a paid ledger checks it against, what another writer appended since
    included, before appending to it (``durable.append_held``; the auditor's DO recheck, DP-01, 2026-11-09: only its first
    bytes had been checked, and a line was appended after a torn or damaged one, and its request sent)."""
    journal_raises(data, path)


def journal_raises(data: bytes, path: Path) -> list[dict]:
    """``journal_whole``'s check, and the cap raises the journal holds (``read_raised``'s), of the same bytes: what a
    session's spending checks its record's cap raises against before each append (``model_intake.Intake.account``).
    Every writer's whole check is this one: a ledger with a notice beside it (``unjournalled``) is refused too, nothing
    appended to it (DV-02)."""
    if notices := unjournalled(Path(path)):
        raise ValueError(notices)
    raised: list[dict] = []
    _read_text(_text(data), Path(path), raised=raised)
    return raised


def _text(data: bytes) -> str:
    """A ledger's bytes as ``Path.read_text`` reads a file: in its default encoding, with universal newlines."""
    import io
    return io.TextIOWrapper(io.BytesIO(data), encoding=io.text_encoding(None)).read()


def _read_text(text: str, path: Path, opened: list[str] | None = None,
               raised: list[dict] | None = None) -> dict[str, LedgerRequest]:
    """``read_ledger`` of a journal's text, the attempts of its ``opened`` entries added to ``opened`` and its cap
    raises to ``raised``; a last line that is not JSON and has no newline after it is torn (``TornLedger``)."""
    found: dict[str, LedgerRequest] = {}
    lines = text.splitlines()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            if number == len(lines) and not text.endswith("\n"):
                raise TornLedger(path, number) from None
            raise
        _journal_event(row, found, number)
        if row.get('state') == 'opened' and opened is not None:
            opened.append(row['attempt'])
        if row.get('state') == 'cap_raised' and raised is not None:
            raised.append({k: v for k, v in row.items() if k != 'state'})
    return found


def _amount(row: dict, field: str, number: int) -> float:
    """A journal line's dollar amount, finite and nonnegative."""
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'paid ledger line {number}: {field} is not a finite, nonnegative amount')
    return float(value)


def _journal_event(row: object, found: dict[str, LedgerRequest], number: int) -> None:
    """One journal line applied to the requests ``found`` so far (``read_ledger``)."""
    if not isinstance(row, dict) or row.get('state') not in LEDGER_STATES:
        raise ValueError(f'paid ledger line {number}: not a journal entry its writer makes')
    state, key = row['state'], row.get('id')
    if state == 'cap_raised':                                  # a session's new cap: no request
        _cap_raised(row, number)
        return
    if state == 'opened':                                      # a job's ledger opened by a run: no request
        if not isinstance(row.get('attempt'), str) or not row['attempt']:
            raise ValueError(f'paid ledger line {number}: an opened entry without the run that opened it')
        return
    if state == 'recovered':                                   # a torn line recovered (``recover_torn_tail``)
        _recovered(row, found, number)
        return
    if state == 'background_received':                         # a response kept while its request is polled
        if not any(r.state == 'open' for r in found.values()):
            raise ValueError(f'paid ledger line {number}: a background response with no request open')
        return
    if not isinstance(key, str) or not key:
        raise ValueError(f'paid ledger line {number}: a {state} entry without its request')
    if state == 'reserved':
        if key in found or not isinstance(row.get('provider'), str):
            raise ValueError(f'paid ledger line {number}: a request reserved twice, or without its provider')
        found[key] = LedgerRequest(request_id=key, provider=row['provider'], model=str(row.get('model', '')),
                                   reserved_usd=_amount(row, 'reserved_usd', number))
        return
    if key not in found or found[key].state == 'settled':
        raise ValueError(f'paid ledger line {number}: a {state} entry for a request '
                         + ('already settled' if key in found else 'never reserved'))
    if state == 'settled':
        found[key] = LedgerRequest(**{**found[key].model_dump(), 'state': 'settled', 'settled_line': number,
                                      'cost_usd': _amount(row, 'cost_usd', number),
                                      'bound_exceeded': row.get('bound_exceeded') is True})
    elif state == 'billing_uncertain':
        found[key] = LedgerRequest(**{**found[key].model_dump(), 'state': 'uncertain'})


SESSION_CAP_LIMIT = 10.0     # the most a session's cap may be (``model_intake.Session.budget``, ``Intake.raise_cap``)


def _cap_raised(row: dict, number: int) -> None:
    """A cap raise's entry as its writer journals it (``model_intake.Intake.raise_cap``, ``CapChange``): the cap before
    and the new one, finite, the new above it and at most ``SESSION_CAP_LIMIT``; when, and why. Any other is not an
    entry its writer makes (the auditor's DP recheck, DQ-03, 2026-11-09: a cap raise without its caps, and one to $100, had
    been read as entries, and a session spent on after them while its budget's reading refused them)."""
    if set(row) - {'state', 'previous', 'new', 'at', 'reason'} or not isinstance(row.get('at'), str) \
            or not row['at'] or not isinstance(row.get('reason', ''), str):
        raise ValueError(f'paid ledger line {number}: a cap raise not as its writer journals one (its caps before '
                         'and after, when and why)')
    for field in ('previous', 'new'):
        value = row.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'paid ledger line {number}: a cap raise whose {field} cap is not a finite, nonnegative '
                             'amount')
    previous, new = float(row['previous']), float(row['new'])
    if not previous < new <= SESSION_CAP_LIMIT:
        raise ValueError(f'paid ledger line {number}: a cap raise from ${previous:g} to ${new:g}, which its writer '
                         f'never makes (a raise is above the cap before, and at most ${SESSION_CAP_LIMIT:g})')


def settled_and_uncertain(requests: dict[str, LedgerRequest]) -> tuple[float, float]:
    """(the settled dollars, the dollars still reserved for requests whose bill is not known or not yet in)."""
    values = list(requests.values())
    return (sum(r.cost_usd or 0.0 for r in values if r.state == 'settled'),
            sum(r.reserved_usd for r in values if r.state != 'settled'))


def _recovered(row: dict, found: dict[str, LedgerRequest], number: int) -> None:
    """A recovery event: its request is uncertain, its reservation kept in full until its bill is resolved; a torn
    reservation's own bound, provider and model are those the recovery read from the torn bytes."""
    key = row.get('id')
    if not isinstance(key, str) or not key:
        raise ValueError(f'paid ledger line {number}: a recovered entry without its request')
    if key in found:
        if found[key].state == 'settled':
            raise ValueError(f'paid ledger line {number}: a recovered entry for a request already settled')
        found[key] = LedgerRequest(**{**found[key].model_dump(), 'state': 'uncertain'})
        return
    if not isinstance(row.get('provider'), str):
        raise ValueError(f'paid ledger line {number}: a recovered reservation without its provider')
    found[key] = LedgerRequest(request_id=key, provider=row['provider'], model=str(row.get('model', '')),
                               reserved_usd=_amount(row, 'reserved_usd', number), state='uncertain')


def recover_torn_tail(path: Path) -> str:
    """Recover a paid journal's torn last line (``TornLedger``; the owner's direction D-7, 2026-10-25), under the
    journal's run lock, and say what was done. The original bytes are kept whole in a side copy beside it. The torn
    bytes are cut and a ``recovered`` entry journalled in their place, naming the side copy and the torn bytes' sha256,
    only where they identify their request: an entry for a request reserved and not settled (its reservation then kept
    in full, the request uncertain, a torn settlement's cost never guessed), a background response while exactly one
    request is open, or a reservation whose request, provider and bound are all legible (kept in full, uncertain).
    Otherwise nothing is changed and the budget stays blocked (``ValueError``). Nothing is ever sent again. The
    journal is read as every reading reads it (``ledger_bytes``), before anything is written: one that does not begin
    with what its mark records its writers last wrote is refused, nothing changed, since a legible torn line does not
    show that what comes before it is the history written there (the auditor's DO recheck, DP-02, 2026-11-09: such a journal
    had been rewritten with its recovery entry, and only then refused). Once recovered, the mark records the journal
    as recovered. It is read, put in place rewritten and marked under the journal's writers' lock
    (``durable.writing``), which every append takes before it opens the journal (the auditor's DQ recheck, DR-01,
    2026-11-09): a lock on the journal's folder, which stays as the journal is replaced in it, so that no append is
    made to the recovered journal before its mark is written, nor its mark written over the recovery's (the auditor's DR
    recheck, DS-01, 2026-11-09: the lock had been the first file's, and an append in another process, locking the
    recovered one, had been written, marked and sent before the recovery's mark was written over its own). A journal
    reached by another name (a link to it, or its file with another name) is refused as it is read, and a recovery that
    waited for the lock of a folder moved, or replaced, meanwhile is refused once it holds it: nothing is written
    (the auditor's DS recheck, DT-01, 2026-11-10). Once it holds the lock, it reads and writes the journal, its side copy and
    its mark only in the folder locked, by their names (``durable._in``), and checks that folder is still at the
    journal's path before it writes anything (``durable.in_place``): a folder moved away while it holds the lock, and
    another put at its path, is never read or written by it, so that a mark another writer wrote there, under that
    folder's own lock, is never written over. It is refused once done where its folder is no longer there
    (``ChangedRecord``, from ``durable.writing``): what it wrote is in the folder it locked (the auditor's DT recheck, DU-01,
    2026-11-10: a recovery so displaced had written its mark over the mark of a request journalled and sent in the
    folder put in its place, which the journal cut back to the recovery's mark then lost, and said it was done).

    Raises:
        ValueError: if the journal has no torn last line, the rest of it is damaged, a run is using it, or the torn
            bytes do not identify their request and its amount; ``durable.ChangedRecord`` where its folder was moved
            or replaced while it waited for its lock or held it.
    """
    import hashlib
    from datetime import datetime, timezone
    from adroit.core.checkpoint import run_lock
    from adroit.core.durable import in_place, mark_of, write_atomic, writing
    path = Path(path)
    if not path.is_file():                  # nothing to recover from; never an empty history in its place (CO-05)
        raise ValueError(f'{path}: there is no journal here to recover; if it was lost, restore the original file. '
                         'A new or empty journal is never made in its place: what was spent would be forgotten')
    try:
        with run_lock(path.parent), writing(path) as folder:   # no append opens, writes or marks it meanwhile (DS-01)
            _refuse_if_running(path.parent)
            raw = ledger_bytes(path, folder)    # one not beginning with what its mark records is refused, unchanged
            if not raw or raw.endswith(b'\n'):
                raise ValueError(f'{path}: its last line is whole; there is no torn line to recover')
            cut = raw.rfind(b'\n') + 1
            body, tail = raw[:cut], raw[cut:]
            if _whole(tail):
                raise ValueError(f'{path}: its last line is a whole entry without its newline, not a torn one; '
                                 'nothing to recover')
            requests = _read_text(body.decode(), path)        # the rest must read as its writer kept it
            event = _identify(tail, requests, path)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            side = path.with_name(f'{path.name}.torn-{stamp}')
            event.update(state='recovered', side_copy=side.name, torn_sha256=hashlib.sha256(tail).hexdigest(),
                         at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
            recovered = body + (json.dumps(event) + '\n').encode()
            _read_text(_text(recovered), path)                 # as it will be read, before anything is written
            in_place(path, folder)                             # in the folder locked, by their names (DU-01)
            write_atomic(side, raw, folder=folder)
            write_atomic(path, recovered, folder=folder)
            write_atomic(mark_of(path), json.dumps({'size': len(recovered),
                                                    'sha256': hashlib.sha256(recovered).hexdigest()}), folder=folder)
    except RuntimeError as error:                          # the lock is held: a run is writing to it
        raise ValueError(f'{path}: a run is using this journal ({error}); recover it once that run has ended') \
            from None
    kept = event.get('reserved_usd', requests[event['id']].reserved_usd if event['id'] in requests else 0.0)
    return (f"recovered {path.name}: its torn last line ({len(tail)} bytes, sha256 {event['torn_sha256'][:12]}…) "
            f"was cut and a recovery entry journalled; request {event['id']} is uncertain, its ${kept:.4f} "
            f"reservation kept in full until its bill is known; the original bytes are in {side.name}; nothing was "
            "sent again")


def _whole(tail: bytes) -> bool:
    """Whether a last line without its newline is nonetheless a whole JSON entry."""
    try:
        json.loads(tail)
    except ValueError:
        return False
    return True


def _identify(tail: bytes, requests: dict[str, LedgerRequest], path: Path) -> dict:
    """The recovery entry's request (and, for a torn reservation, its provider, model and bound) from the torn
    bytes, or ``ValueError`` where they do not identify it (``recover_torn_tail``): the request's identifier, where it
    is reserved and not settled (any entry for it keeps its reservation in full, so its torn state need not be read);
    a background response's single open request; a torn reservation's identifier, provider and bound together."""
    import math
    import re
    blocked = f'{path}: its torn last line cannot be recovered'
    state = re.search(rb'"state":\s*"([a-z_]+)"', tail)
    found = re.search(rb'"id":\s*"([^"\\]+)"', tail)
    state = state.group(1).decode() if state else None
    if state == 'background_received':
        open_ = [k for k, r in requests.items() if r.state == 'open']
        if len(open_) != 1:
            raise ValueError(f'{blocked}: a background response with {len(open_)} requests open, so its request '
                             'is not identified; the budget stays blocked until a person repairs the journal')
        return {'id': open_[0]}
    if found is None:
        raise ValueError(f'{blocked}: it names no request; the budget stays blocked until a person repairs the '
                         'journal (the original is unchanged)')
    key = found.group(1).decode()
    if key in requests:                     # whatever its state, an entry for an open request: kept uncertain
        if requests[key].state == 'settled':
            raise ValueError(f'{blocked}: it is for request {key}, already settled; the budget stays blocked')
        return {'id': key}
    if state != 'reserved':
        raise ValueError(f'{blocked}: it is for request {key}, never reserved; the budget stays blocked')
    provider = re.search(rb'"provider":\s*"([a-z]+)"', tail)
    model = re.search(rb'"model":\s*"([^"\\]+)"', tail)
    bound = re.search(rb'"reserved_usd":\s*([0-9.eE+-]+)[,}\s]', tail)
    try:
        amount = float(bound.group(1)) if bound else math.nan
    except ValueError:
        amount = math.nan
    if provider is None or not math.isfinite(amount) or amount < 0:
        raise ValueError(f'{blocked}: the reservation of request {key} is torn before its provider or bound; the '
                         'budget stays blocked until a person repairs the journal')
    return {'id': key, 'provider': provider.group(1).decode(), 'model': model.group(1).decode() if model else '',
            'reserved_usd': amount}


def _refuse_if_running(folder: Path) -> None:
    """``ValueError`` where the folder is a workbench job that is still running (its journal may still be written)."""
    from adroit.core.durable import absent
    job = folder / 'job.json'
    if not absent(job):                     # a record there that cannot be read: running, for all that is known
        try:
            running = json.loads(job.read_text()).get('status') == 'running'
        except (OSError, ValueError, AttributeError):
            running = True
        if running:
            raise ValueError(f'{folder}: its run is still going (or its job record cannot be read); recover the '
                             'journal once it has ended')

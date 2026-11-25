"""One interpretation of money: what a run, a session or a set of runs cost, read once from the authoritative records
and worded in one place (the consolidation plan's M2, 2026-10-25; the consolidation m2 accounting record of 2026-10-25).

The workbench's run page, card and Studies list read a run's cost here, and so do the command line's closing lines,
``adroit studies`` and its total, the promotion report, the session pages of the model library, the experimental
library and constraint discovery, and the batch page. Nothing else computes money (the consistency plan's survey had
found eleven surfaces that did, and the auditor's consistency audit three of them wrong: CA-04, CA-05, CA-06).

**The facts beneath the words** (``Cost``), each with the record it came from:

- the scope: a run's own requests, or a session's (a discovery run opened or resumed its session, and the session is
  what it is charged with, the runs that share it included), and the session holding the budget (``budget_owner``);
  beside a session's figure, the run's own requests where its request record names them (``own_usd``: the survey's
  own cost, unchanged when an extraction that shares the budget spends; the gap plan's G5);
- the settled dollars and their precision: to $0.0001 from a paid ledger (``journal``) or a "spent" line (``log``),
  to the cent from an older line (``cent``, approximate), the settled dollars alone from a study record
  (``study record``), or the session's totals before and after (``session totals``);
- the dollars still reserved for requests whose bill is not known;
- a committed bound that is not split into settled and reserved (a budget stop's record);
- what could not be read (``damaged``) and which records disagree (``conflicts``), each named;
- the record that shows no paid request was sent (``none_sent_evidence``), never inferred from a record's absence;
- each identifiable request (``requests``: its ledger and identifier, its state and dollars), so that a total counts
  it once however many runs or studies name it (D-6);
- a record that names another run than the one read (``foreign``): each record of a workbench run's money names the
  run that wrote it (its paid ledger's ``opened`` entry, its log's second line, its request record, a budget stop's
  record), and is counted only as that run's (the auditor's DD recheck, DE-01, 2026-11-05).

The labels (free, none sent, settled, reserved, approximate, committed, not available) combine: "about $0.12, and up to
$0.40 reserved" is one reading. Records that conflict are shown as a conflict, never resolved by taking the most
precise. The formatters (``run_line``, ``short_line``, ``cost_lines``, ``session_text``, ``live_text``,
``total_text``) are the only places money is worded, and they do no arithmetic that decides what happened: what is
left of a session's cap is its account's (``Intake.budget_status``), never the cap less the settled dollars.

Reading here is $0: no request is made, and nothing is written. No workbench module is imported: the command line
uses it as the pages do, a run given as its command and status (``JobFacts``; a workbench ``Job`` serves).
"""
from __future__ import annotations

import ast
import json
import math
import os
import re
from pathlib import Path
from typing import Iterable

from pydantic import Field

from adroit.core.durable import absent, linked
from adroit.core.state import StrictModel
from adroit.orchestrator.preflight import JOB_LEDGER

JOB, LOG = "job.json", "log.txt"            # the workbench's records in a run's folder (``ui.engine``)
KINDS = {("models", "step"): "model_intake", ("models", "paper"): "model_intake",
         ("experiments", "extract"): "source_interpretation", ("experiments", "import"): "source_import",
         ("constraints", "discover"): "discovery", ("constraints", "resume"): "discovery",
         ("anomaly", "draft"): "signal_draft"}
SESSION_KINDS = ("model_intake", "source_interpretation", "discovery")
PREFLIGHT = re.compile(r"paid request: .*?; committed \$([0-9]+(?:\.[0-9]+)?) of")
DISCOVERY_SESSION = re.compile(r"discovery session ([0-9a-f]{32}) for")
PARTIAL = re.compile(r"Partial results: (.+?); paid responses:")
SPENT_LINE = re.compile(r"spent \$([0-9]+(?:\.[0-9]+)?)([^\n]*)")
RESERVED = re.compile(r"up to \$([0-9]+(?:\.[0-9]+)?) reserved")
LOG_ATTEMPT = re.compile(r"# run attempt (\S+)")     # the runner's second line: whose log it is (DE-01)
NOT_AVAILABLE = "not available"
SPLIT_TOLERANCE = 1e-6       # the writer's split adds up to its committed dollars to 10⁻⁹ (``cli._committed_parts``)


class JobFacts(StrictModel):
    """What accounting needs of a run: its command (the arguments after ``adroit``), its status and its folder."""
    command: list[str]
    status: str = "completed"
    folder: str = ""
    attempt: str = ""                        # the launch's own identity (``engine.Job.attempt``; DC-01)
    # the record's file as read (device, inode, size, modified and changed times): two readings are equal only where
    # nothing wrote it between them, not even its own bytes again (the auditor's DD recheck, DE-01, 2026-11-05)
    seen: tuple[int, ...] = ()


def facts_of(job) -> JobFacts:
    """A run as ``JobFacts``: one already, or anything with a command, a status, a folder and an attempt (a workbench
    ``Job``)."""
    if isinstance(job, JobFacts):
        return job
    return JobFacts(command=list(job.command), status=str(getattr(job, "status", "completed")),
                    folder=str(getattr(job, "folder", "")), attempt=str(getattr(job, "attempt", "") or ""))


def read_job(folder: Path) -> JobFacts | None:
    """A run folder's workbench record (``job.json``) as ``JobFacts``, with its file's identity as read (``seen``);
    None where there is none or it cannot be read (``study_cost`` says so)."""
    try:
        with (Path(folder) / JOB).open("rb") as stream:
            stat = os.fstat(stream.fileno())
            raw = json.loads(stream.read())
        return JobFacts(command=[str(a) for a in raw["command"]], status=str(raw.get("status", "completed")),
                        folder=str(raw.get("folder", folder)), attempt=str(raw.get("attempt") or ""),
                        seen=(stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def budget_of(command: list[str]) -> float:
    """The dollars a command may spend (its ``--budget``), 0 for a free one. Read as the command line reads it: a
    command giving ``--budget`` more than once is refused, since the command line would take the last and a gate the
    first (the batch audit's B20-01), as is a budget that is missing, not finite or negative (ValueError)."""
    values = []
    for i, arg in enumerate(command):
        if arg == "--budget":
            values.append(command[i + 1] if i + 1 < len(command) else "")
        elif arg.startswith("--budget="):
            values.append(arg.split("=", 1)[1])
    if len(values) > 1:
        raise ValueError("the command gives --budget more than once: give it once")
    if not values:
        return 0.0
    try:
        cost = float(values[0])
    except ValueError:
        raise ValueError(f"--budget {values[0]!r} is not a number of dollars") from None
    if not math.isfinite(cost) or cost < 0:
        raise ValueError(f"--budget {values[0]!r} is not a finite number of dollars, at least 0")
    return cost


class RequestFact(StrictModel):
    """One identifiable paid request: its state in its ledger (settled, uncertain, open) and its dollars."""
    state: str
    settled_usd: float = 0.0
    reserved_usd: float = 0.0


class Cost(StrictModel):
    """A run's money (module docstring), each figure from its authoritative record, or None where that record is
    missing or cannot be read (``damaged``, ``note``)."""
    run_usd: float | None = None             # the settled dollars of the scope
    run_uncertain_usd: float = 0.0           # reserved for its requests whose bill is not known
    run_source: str = ""                     # where run_usd was read
    run_approximate: bool = False            # run_usd read from a line rounded to the cent
    run_committed_usd: float | None = None   # settled and reserved together, where a record does not split them
    committed_source: str = ""               # the record that bound comes from, where not the budget stop's (CO-04)
    settled_only: bool = False               # run_usd from a record of settled dollars alone (a study record)
    sent_none: bool = False                  # a record shows that no paid request was sent (``none_sent_evidence``)
    paid: bool = False                       # the command could spend (a --budget, or a paid session step)
    session_id: str = ""
    session_spent_usd: float | None = None   # every settled request of the session, this run's included
    session_reserved_usd: float = 0.0        # the session's reservations whose bill is not known
    session_cap_usd: float | None = None     # the session's approved cap, as last raised
    session_remaining_usd: float | None = None   # what its account leaves of the cap (never the cap less spent)
    budget_usd: float = 0.0                  # a non-session paid command's confirmed budget
    note: str = ""                           # every reason below in words, and why a figure is missing
    scope: str = "run"                       # run: this run's requests; session: every request of its session
    budget_owner: str = ""                   # the session holding the budget (a linked extraction's discovery session)
    own_usd: float | None = None             # a session-scope run's own requests, settled (its request record), or None
    own_uncertain_usd: float = 0.0           # its own requests reserved whose bill is not known
    settled_precision: str = ""              # journal, log, cent, study record, session totals; "" where none
    damaged: list[str] = Field(default_factory=list)      # records that could not be read, and why
    conflicts: list[str] = Field(default_factory=list)    # records that disagree, each named
    none_sent_evidence: str = ""             # the record that shows no paid request was sent
    requests: dict[str, RequestFact] = Field(default_factory=dict)    # identifiable requests, for counting each once
    other_run: bool = False                  # the run in its study's folder is not the one that published it (DC-01)
    foreign: list[str] = Field(default_factory=list)      # records naming another run than the one read (DE-01)
    unsettled: bool = False                  # its run's records changed at every reading: its study record's (DE-01)


def usd(value: float) -> str:
    """Dollars at the precision an interpretation's cents need: "$0.0541", "$1.25"."""
    return f"${value:.4f}" if abs(value) < 1 else f"${value:.2f}"


def kind_of(job) -> str:
    """What a command makes: its entry in ``KINDS``, "promotion", or "study" (Track 1, an idea, a derivation, Signal
    best fits, Explain a signal, a native fit, a reanalysis)."""
    command = facts_of(job).command
    found = KINDS.get(tuple(command[:2]))
    if found:
        return found
    return "promotion" if command[:1] == ["promote"] else "study"


def _option(command: list[str], flag: str) -> str:
    """A command's value for ``flag`` ("" if absent)."""
    return command[command.index(flag) + 1] if flag in command[:-1] else ""


def _argument(job) -> str:
    """A session command's session (its third word), "" if there is none."""
    command = facts_of(job).command
    return command[2] if len(command) > 2 and not command[2].startswith("-") else ""


def _budgets(library: str):
    """The session budget service of a library: the model library's intake, or the experimental library's."""
    if library == "source":
        from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
        return ExperimentalExtraction().budgets
    from adroit.orchestrator.model_intake import Intake
    return Intake()


def _read_json(path: Path) -> dict | None:
    """A JSON object from a file, None if it is missing or unreadable."""
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def discovery_session(folder: Path, job=None, expected: str | None = None) -> tuple[str, list[str]]:
    """(a discovery run's session, or "" where none is established; what disagrees with it, each named). Its own
    records name it: its request record where it is this run's (``expected``: its attempt, the job's own where None),
    the line its command logged on starting where the log is this run's, and the session a resume names. Where they
    agree, theirs; a ``discovery.json`` naming another session is then named as not this run's where one of them is
    bound to the run (a record naming its attempt, or its command), and otherwise neither is taken. Where they
    disagree, none, each named. Only a run with none of these, from before them, is given its ``discovery.json``'s
    session, and not where its folder holds another run's record or an interrupted export (the auditor's DK recheck, DL-04,
    2026-11-07:
    ``discovery.json`` had been read first, so a run whose export was interrupted after its request record was charged
    with the session of an earlier export's companion, its dollars labelled this run's). A request record that is
    there but cannot be read (torn, or not a record: ``null``, a list, ``{}``) is damage, never a run from before it:
    the session is then this run's only where a record bound to the run names it (its log, its command), and otherwise
    none, the record named (the auditor's DL recheck, DM-01, 2026-11-07: the damage had been set aside, and the run then
    charged with its ``discovery.json``'s earlier session, its dollars and cap shown as this run's). So too a request
    record or a log whose entry is there but leads to nothing that can be read, a link to a missing file among them:
    only a folder with no such entry at all is a run's from before them (``durable.absent``; the auditor's DM recheck,
    DN-01, 2026-11-08: a request record that was a link to nothing had read as none, and the run been charged with
    its ``discovery.json``'s session)."""
    from adroit.core.durable import interrupted
    from adroit.orchestrator.model_intake import REQUESTS
    folder = Path(folder)
    facts = facts_of(job) if job is not None else None
    expected = (facts.attempt if facts is not None else "") if expected is None else expected
    named: dict[str, str] = {}                  # each session the run's own records name: the first record naming it
    bound = False                               # whether one of them is bound to this run: its attempt, its command
    receipt, damage, foreign = _receipt(folder, expected)
    text, other_log, unread = _log_text(folder, expected)
    damaged = "; ".join(([damage] if damage and not foreign else []) + unread)  # there, and not readable as a record
    if receipt is not None and receipt.session_id:
        named.setdefault(receipt.session_id, f"its request record ({REQUESTS})")
        bound |= bool(expected) and receipt.attempt == expected
    if found := DISCOVERY_SESSION.search(text):
        named.setdefault(found.group(1), f"its log ({LOG})")
        bound |= bool(expected) and _log_owner(text) == expected
    if facts is not None and facts.command[1:2] == ["resume"] and _argument(facts):
        named.setdefault(_argument(facts), "its command")
        bound = True
    view = _read_json(folder / "discovery.json")
    companion = view["session"] if view and isinstance(view.get("session"), str) else ""
    if len(named) > 1:
        return "", ["the run's records name different sessions (" + "; ".join(
            f"{record}: {session[:8]}…" for session, record in named.items()) + "): its session is not established"]
    if named:
        session = next(iter(named))
        if damaged and not bound:
            return "", [f"{damaged}, and {named[session]}, which names session {session[:8]}…, is not bound to this "
                        "run: its session is not established"]
        if not companion or companion == session:
            return session, unread                      # a log that cannot be read named beside its figure
        if bound:
            return session, [*unread, f"its discovery.json names another session ({companion[:8]}…): it is not this "
                                      "run's"]
        return "", [f"{named[session]} names session {session[:8]}… and its discovery.json {companion[:8]}…, neither "
                    "bound to this run: its session is not established"]
    if damaged:
        return "", [f"{damaged}, and nothing else of this run's names its session"
                    + (f" (its discovery.json names {companion[:8]}…, which is not this run's record)" if companion
                       else "") + ": its session is not established"]
    if companion and (foreign or other_log or interrupted(folder)):
        return "", [f"its discovery.json names a session ({companion[:8]}…), but nothing of this run's names one, and "
                    "its folder holds " + ("an interrupted export" if not (foreign or other_log) else
                                           "another run's records") + ": its session is not established"]
    return companion, []


def ledger_session(folder: Path, job, expected: str | None = None) -> tuple[str, str]:
    """(the session whose paid ledger holds a run's requests, its library: "model" or "source"), or ("", "");
    ``expected``, a discovery run's attempt (``discovery_session``)."""
    job = facts_of(job)
    kind = kind_of(job)
    if kind == "model_intake":
        return _argument(job), "model"
    if kind == "source_interpretation" and _argument(job):
        try:
            from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
            return ExperimentalExtraction().budget_owner(_argument(job)), "source"
        except (ValueError, OSError):
            return _argument(job), "source"
    if kind == "discovery":
        return discovery_session(Path(folder), job, expected)[0], "source"
    return "", ""


def _with_notes(c: Cost) -> Cost:
    """``c`` with its ``note`` holding its damage and conflicts in words, after any reason already there."""
    words = [w for w in [c.note, *c.damaged, *c.conflicts] if w]
    return c.model_copy(update={"note": "; ".join(dict.fromkeys(words)), "sent_none": bool(c.none_sent_evidence)})


# --- one run ---------------------------------------------------------------------------------------------------------

def cost(folder: Path, job, held: Held | None = None, expected: str | None = None) -> Cost:
    """A run's cost (module docstring): a session run's from its session's ledger, another's from its own ledger, or,
    for a run from before it, its study, log or stop records; a free command's $0. ``held``: the study record and
    result of the version a page holds (``held_cost``), read in place of the folder's. ``expected``: the run whose
    records are counted (its attempt; the job's own where None): a record naming another is not, and is named
    (``foreign``; DE-01); "" counts each record as found (a run from before records named it)."""
    folder, job = Path(folder), facts_of(job)
    expected = job.attempt if expected is None else expected
    if kind_of(job) == "discovery":
        return _with_notes(_discovery_cost(folder, job, *discovery_session(folder, job, expected), expected))
    session, library = ledger_session(folder, job)
    if session or kind_of(job) in SESSION_KINDS:
        return _with_notes(session_cost(folder, job, session, library, expected))
    budget = budget_of(job.command)
    if budget <= 0:
        return _with_notes(Cost(run_usd=0.0, run_source="a free command (no --budget: it cannot make a paid request)",
                                none_sent_evidence="its command has no --budget"))
    return _with_notes(reconciled(folder, job, budget, held, expected))


def _another(record: str, theirs: str, expected: str) -> str:
    """Words for a record that names another run than the one whose cost is read (DE-01)."""
    return f"{record} names another run (attempt {theirs[:8]}…), not this one ({expected[:8]}…): it is not counted"


def _log_text(folder: Path, expected: str = "") -> tuple[str, list[str], list[str]]:
    """A run's log, read once: (its text, or "" where it names another run than ``expected`` or cannot be read; why it
    names another run, if so; why it cannot be read, if so). A log from before logs named their run is read as found;
    a folder with no log at all has none, and one whose log is there but cannot be read (a link to nothing among them:
    ``durable.absent``, DN-01) has a damaged one."""
    log = Path(folder) / LOG
    if absent(log):
        return "", [], []
    try:
        text = log.read_text(errors="replace")
    except OSError as error:
        return "", [], [f"its log ({LOG}) cannot be read ({linked(log)}{str(error).splitlines()[0]})"]
    owner = _log_owner(text)
    if expected and owner and owner != expected:
        return "", [_another(f"its log ({LOG})", owner, expected)], []
    return text, [], []


def _log_owner(text: str) -> str:
    """The run a log names as its own (``LOG_ATTEMPT``, on its first two lines), "" where it names none."""
    return next((m.group(1) for line in text.splitlines()[:2] if (m := LOG_ATTEMPT.fullmatch(line.strip()))), "")


def reconciled(folder: Path, job, budget: float, held: Held | None = None, expected: str = "") -> Cost:
    """A paid run's cost from every record it left, gathered before any figure is chosen (the auditor's consolidation audit,
    CO-04, 2026-10-25: the run's paid ledger, where present, had been read alone, so that a budget stop's larger
    commitment, a log's reservation, or an empty ledger beside a record of spending had vanished, and a damaged
    budget-stop record had gone unnamed). The paid ledger, or else a budget stop's record split into settled and
    reserved dollars, gives the figures and the requests' identities; every other record (the budget stop's, the
    log's last "spent" line, the study record) is then checked against them (``_cross_checked``): a difference is
    named as a conflict and the largest commitment any record shows is kept as a bound, never added to the rest; a
    record that cannot be read is named as damage. "No paid request was sent" stands only where nothing contradicts
    it. A run with neither keeps its records' combined facts (``_recorded_spend``). A record naming another run than
    ``expected`` is left out and named (DE-01)."""
    folder, job = Path(folder), facts_of(job)
    records = run_records(folder, held, expected)
    running = job.status == "running"
    if not absent(folder / JOB_LEDGER):                # a ledger there that cannot be read is damage (DN-01)
        base = job_ledger_cost(folder, job, budget, expected)
        if base.run_usd is None:                       # the ledger cannot be read, or is another run's: not available
            return base.model_copy(update={"damaged": base.damaged + records.damaged,
                                           "foreign": base.foreign + records.foreign})
        return _cross_checked(base, records, running, "its paid ledger", against_stop=True)
    if records.split is not None:
        base = Cost(run_usd=records.split[0], run_uncertain_usd=records.split[1], run_source="the budget-stop record",
                    settled_precision="journal", paid=True, budget_usd=budget)
        return _cross_checked(base, records, running, "its budget-stop record", against_stop=False)
    recorded = _recorded_spend(folder, budget, records)
    if recorded is not None:
        return recorded
    return Cost(paid=True, budget_usd=budget, note="this run has not reported its spending" +
                (" yet" if running else ""), foreign=records.foreign)


class RunRecords(StrictModel):
    """What a paid run's records other than its paid ledger say about its money (``run_records``)."""
    split: tuple[float, float] | None = None      # a budget stop's settled and reserved dollars, adding up
    committed: float | None = None                # a budget stop's committed dollars
    damaged: list[str] = Field(default_factory=list)   # a result or budget-stop record that cannot be read, and why
    spent: str = ""                               # the log's last "spent" figure, as written
    precise: bool = False                         # that figure to $0.0001 (else to the cent)
    reserved: float | None = None                 # the reservation that line states
    recorded: float | None = None                 # the study record's settled dollars
    study: bool = False                           # a study record exists
    foreign: list[str] = Field(default_factory=list)   # records naming another run, left out (also in ``damaged``)


class Held(StrictModel):
    """A held version's own records, for its run's cost (``held_cost``): its result's bytes, as a budget stop's record
    may be (parsed only where a paid run's cost needs them, ``_held_stop``), or why it holds none; and its study
    record's settled dollars, or why it cannot be read: as the version holds them, never the folder's files read again
    (the auditor's version-handle audit, DD-02, 2026-11-04)."""
    content: bytes | None = None
    unheld: str = ""
    recorded: float | None = None
    study: bool = False
    damaged: list[str] = Field(default_factory=list)


def run_records(folder: Path, held: Held | None = None, expected: str = "") -> RunRecords:
    """A paid run's other records (``RunRecords``): its budget stop's (the run's ``result.json``, or that of the
    partial results its log names), its log's last "spent" line, and its study record; a result record that exists
    but cannot be read is named, since it may be the budget stop's (CO-04). A log or a budget stop's record naming
    another run than ``expected`` is left out, and named (DE-01)."""
    folder = Path(folder)
    text, foreign, unread = _log_text(folder, expected)
    stop, damaged = _held_stop(held) if held is not None else _read_record(folder / "result.json", "result.json")
    damaged = [*unread, *damaged]
    if held is None:
        stop = _owned(stop, "its budget-stop record (result.json)", expected, foreign)
    if not (stop and stop.get("status") == "budget_stopped") and PARTIAL.search(text):
        partial = Path(PARTIAL.search(text).group(1).strip()) / "result.json"
        stop, more = _read_record(partial, str(partial))
        stop = _owned(stop, f"the budget-stop record its log names ({partial})", expected, foreign)
        damaged += more
    damaged += foreign
    split, committed, broken = _stop_facts(stop if stop and stop.get("status") == "budget_stopped" else None)
    lines = SPENT_LINE.findall(text)
    value, rest = lines[-1] if lines else ("", "")
    reserved = RESERVED.search(rest)
    if held is not None:
        recorded, has_study = held.recorded, held.study
        damaged += held.damaged
    else:
        study, unreadable = _read_record(folder / "study.json", "study.json", "study",
                                         "what it records the run cost is not known")
        damaged += unreadable
        recorded, has_study = (_dollars(study.get("cost_usd")) if study else None), study is not None
    return RunRecords(split=split, committed=committed, damaged=damaged + broken, spent=value,
                      precise=bool(value) and len(value.partition(".")[2]) >= 4,
                      reserved=float(reserved.group(1)) if reserved else None,
                      recorded=recorded, study=has_study, foreign=foreign)


def _owned(stop: dict | None, record: str, expected: str, foreign: list[str]) -> dict | None:
    """A budget stop's record, or None where it names another run than ``expected`` (said in ``foreign``: DE-01)."""
    theirs = stop.get("attempt") if isinstance(stop, dict) else None
    if expected and isinstance(theirs, str) and theirs and theirs != expected:
        foreign.append(_another(record, theirs, expected))
        return None
    return stop


def _held_stop(held: Held) -> tuple[dict | None, list[str]]:
    """``_read_record`` of a held version's result: (its object, or None; why it cannot be read, if so)."""
    from adroit.core.durable import parse_object
    unknown = "whether it records a budget stop, and what that committed, is not known"
    if held.content is None:
        return None, [f"its result record (result.json) {held.unheld}: {unknown}"] if held.unheld else []
    stop, why = parse_object(held.content)
    return stop, [f"its result record (result.json) {why}: {unknown}"] if why else []


def _read_record(path: Path, label: str, record: str = "result",
                 unknown: str = "whether it records a budget stop, and what that committed, is not known"
                 ) -> tuple[dict | None, list[str]]:
    """(a JSON object from a run's ``record`` record, or None where it is missing or damaged; why it is damaged, the
    record named as ``label``): present but unreadable, or holding something other than an object (``null``, a list,
    a number: the auditor's CO recheck, CR-03, 2026-10-26, where those had read as absent and an empty journal had then
    certified "no paid request was sent"), it may be the budget stop's, so it is named (``durable.read_object``)."""
    from adroit.core.durable import read_object
    data, why = read_object(path)
    if why:
        return None, [f"its {record} record ({label}) {why}: {unknown}"]
    return data, []


def _cross_checked(c: Cost, r: RunRecords, running: bool, base: str, against_stop: bool) -> Cost:
    """``c`` (from ``base``: the paid ledger, or a budget stop's split) checked against the run's other records
    (``reconciled``): each difference named as a conflict; the largest commitment a record shows, where it exceeds
    ``c``'s settled and reserved dollars, kept as the run's committed bound with its record named
    (``committed_source``); damage named; "no paid request was sent" withdrawn where anything contradicts it or a
    record cannot be read. A running command's log is not read: its closing line is not written yet."""
    settled, reserved = c.run_usd or 0.0, c.run_uncertain_usd
    known = settled + reserved
    conflicts, bounds = list(c.conflicts), []
    if against_stop and r.committed is not None:
        if r.split is not None and (abs(r.split[0] - settled) > SPLIT_TOLERANCE
                                    or abs(r.split[1] - reserved) > SPLIT_TOLERANCE):
            conflicts.append(f"its budget-stop record shows {usd(r.split[0])} settled and {usd(r.split[1])} reserved, "
                             f"where {base} shows {usd(settled)} settled and {usd(reserved)} reserved")
        elif r.split is None and abs(r.committed - known) > SPLIT_TOLERANCE:
            conflicts.append(f"its budget-stop record shows {usd(r.committed)} committed, where {base} shows "
                             f"{usd(known)}")
        bounds.append((r.committed, "its budget-stop record"))
    if r.spent and not running:
        value, tolerance = float(r.spent), (5e-5 if r.precise else 0.005)
        if abs(value - settled) > tolerance:
            conflicts.append(f"its log says {'' if r.precise else 'about '}{usd(value)} spent, where {base} shows "
                             f"{usd(settled)} settled")
        if abs((r.reserved or 0.0) - reserved) > 5e-5:
            conflicts.append(f"its log says up to {usd(r.reserved or 0.0)} reserved whose bill is not known, where "
                             f"{base} shows {usd(reserved)}")
        bounds.append((value + (r.reserved or 0.0), "its log"))
    if r.recorded and abs(r.recorded - settled) > 5e-5:
        conflicts.append(f"its study record says {usd(r.recorded)} settled, where {base} shows {usd(settled)}")
        bounds.append((r.recorded, "its study record"))
    top = None
    for bound in bounds:                  # the largest; on a tie (to the writers' rounding), the first named
        if top is None or bound[0] > top[0] + SPLIT_TOLERANCE:
            top = bound
    update: dict = {"conflicts": conflicts, "damaged": [*c.damaged, *r.damaged], "foreign": [*c.foreign, *r.foreign]}
    if top is not None and top[0] > known + SPLIT_TOLERANCE:
        update.update(run_committed_usd=top[0], committed_source=top[1])
    if conflicts or r.damaged:
        update["none_sent_evidence"] = ""
    return c.model_copy(update=update)


def _facts(requests: dict, key: str) -> dict[str, RequestFact]:
    """A ledger's requests as identifiable facts, each keyed by its ledger (``key``) and identifier."""
    return {f"{key}#{rid}": RequestFact(state=r.state, settled_usd=(r.cost_usd or 0.0) if r.state == "settled" else 0.0,
                                        reserved_usd=r.reserved_usd if r.state != "settled" else 0.0)
            for rid, r in requests.items()}


def job_ledger_cost(folder: Path, job, budget: float, expected: str = "") -> Cost:
    """A paid run's cost from its own paid ledger (``preflight.job_ledger``): every request in it is the run's, the
    settled apart from the reserved whose bill is not known (or not yet in, while the run goes on). A ledger opened by
    another run than ``expected`` (its ``opened`` entries, read with its requests: ``budget.read_owned``) is not this
    run's: not available, and named (DE-01); one from before ledgers named their run is read as found."""
    from adroit.agents.budget import read_owned, settled_and_uncertain
    out = Cost(paid=True, budget_usd=budget)
    try:
        requests, opened = read_owned(Path(folder) / JOB_LEDGER)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return out.model_copy(update={"damaged": [f"the run's paid ledger could not be read ({error})"]})
    others = [a for a in opened if a != expected] if expected else []
    if others:
        why = _another(f"its paid ledger ({JOB_LEDGER})", others[0], expected)
        return out.model_copy(update={"damaged": [why], "foreign": [why]})
    settled, uncertain = settled_and_uncertain(requests)
    source = (f"the run's own paid ledger: {len(requests)} request(s)" if requests else
              "the run's own paid ledger: it holds no request")
    return out.model_copy(update={
        "run_usd": settled, "run_uncertain_usd": uncertain, "run_source": source, "settled_precision": "journal",
        "none_sent_evidence": "" if requests else "the run's own paid ledger, opened empty before any request",
        "requests": _facts(requests, str(Path(folder).resolve() / JOB_LEDGER))})


def _recorded_spend(folder: Path, budget: float, records: RunRecords | None = None) -> Cost | None:
    """A paid run from before its own paid ledger: what its other records establish, each fact kept for what it is;
    None if there is no record. A budget stop's record split into settled and reserved dollars that add up to its
    committed dollars gives the figures, checked against the log and the study record (``reconciled``). Otherwise the
    facts are combined, none dropped for another's precision: the settled
    dollars, from the log's last "spent" line to $0.0001, else the study record's (settled ones alone), else the line
    to the cent (approximate; at $0.00 unknown: WA-03); the dollars that line says are still reserved, whatever its
    precision; a budget stop's committed dollars, an upper bound kept beside the rest where its split is missing or
    does not add up; and, named, a split that cannot be read (``damaged``) and records that disagree
    (``conflicts``). A study record of $0, or without a cost, establishes nothing (it keeps settled dollars alone, so
    it cannot show that no request was sent). The combined audit's V1-02 and the consistency audit's CA-05; a result
    record that cannot be read is named (CO-04)."""
    base = {"paid": True, "budget_usd": budget}
    r = records or run_records(folder)
    if r.split is not None:
        return _cross_checked(Cost(run_usd=r.split[0], run_uncertain_usd=r.split[1], run_source="the budget-stop record",
                                   settled_precision="journal", **base), r, False, "its budget-stop record", False)
    committed, damaged, value, precise, recorded = r.committed, r.damaged, r.spent, r.precise, r.recorded
    if not value and not r.study and committed is None and not damaged:
        return None
    found = {"run_uncertain_usd": r.reserved or 0.0, "run_committed_usd": committed}
    conflicts, notes = [], []
    source = "the run's log (its \"spent\" line)"
    if precise:
        found.update(run_usd=float(value), run_source=source, settled_precision="log")
        if recorded and abs(recorded - float(value)) > 5e-5:
            conflicts.append(f"its study record says {usd(recorded)} settled")
    elif recorded:
        found.update(run_usd=recorded, settled_only=True, run_source="its study record", settled_precision="study record")
        if value and abs(float(value) - recorded) > 0.005:
            conflicts.append(f"its log says about {usd(float(value))}, rounded to the cent")
    elif value and float(value) > 0:
        found.update(run_usd=float(value), run_approximate=True, run_source=source + ", rounded to the cent",
                     settled_precision="cent")
    elif value:
        notes.append("its log says \"spent $0.00\", rounded to the cent: under half a cent settled, or nothing; a "
                     "request whose bill is not known is not in that line")
    elif r.study and committed is None:
        notes.append("its study record shows no settled dollars, and it keeps settled dollars alone: it cannot show "
                     "whether a request was sent whose bill is not known")
    shown = (found.get("run_usd") or 0.0) + found["run_uncertain_usd"]
    if committed is not None and shown > committed + SPLIT_TOLERANCE:      # a commitment below what was spent (CO-04)
        conflicts.append(f"its budget-stop record shows {usd(committed)} committed, less than the {usd(shown)} its "
                         "other records show")
    return Cost(**found, note="; ".join(notes), damaged=damaged, conflicts=conflicts, foreign=r.foreign, **base)


def _stop_facts(stop: dict | None) -> tuple[tuple[float, float] | None, float | None, list[str]]:
    """A budget stop's record: ((settled, reserved) where its split adds up to its committed dollars, else None; its
    committed dollars where readable, else None; why what it holds cannot be read, if so)."""
    if not stop:
        return None, None, []
    committed = _dollars(stop.get("committed_usd"))
    if committed is None:
        return None, None, [f"its budget-stop record's committed dollars ({stop.get('committed_usd')!r}) are not an "
                            "amount"]
    if "settled_usd" not in stop and "uncertain_usd" not in stop:          # a record from before the split
        return None, committed, []
    settled, uncertain = _dollars(stop.get("settled_usd")), _dollars(stop.get("uncertain_usd"))
    if settled is None or uncertain is None:
        return None, committed, [f"its budget-stop record's split into settled and reserved dollars cannot be read "
                                 f"({stop.get('settled_usd')!r} settled, {stop.get('uncertain_usd')!r} reserved)"]
    if abs(settled + uncertain - committed) > SPLIT_TOLERANCE:
        return None, committed, [f"its budget-stop record's split ({usd(settled)} settled + {usd(uncertain)} "
                                 f"reserved) does not add up to its {usd(committed)} committed"]
    return (settled, uncertain), committed, []


def _dollars(value: object) -> float | None:
    """A record's dollar amount, finite and nonnegative, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def session_cost(folder: Path, job, session: str, library: str, expected: str = "") -> Cost:
    """A session run's cost: its own requests from the session's paid ledger, the session's spending and its cap. A
    discovery run (``constraints discover`` or ``resume``) is charged with its whole session, and says so (``scope``
    "session"): the extractions that share the session's budget are in it. Its request record and its log are this
    run's only where they do not name another than ``expected`` (DE-01). The session's spending, reserved and remaining
    dollars and its requests are of one reading of its journal, and its cap of the record that stood while it was read
    (``Intake.snapshot``; the auditor's DE recheck, DF-02, 2026-11-05: read twice, a request settled between them had been in
    the total and not in the spending shown; the auditor's DF recheck, DG-01, 2026-11-06: the cap read before a raise, and
    the spending after it). A session that could not be read as one state is named, with no figure."""
    job = facts_of(job)
    free = job.command[:2] == ["models", "step"] and _option(job.command, "--kind") in ("typed", "fields")
    out = Cost(session_id=session, paid=not free, budget_owner=session)
    if not session:
        return out.model_copy(update={"note": "the run's session is not recorded yet"})
    try:
        status, requests = _budgets(library).snapshot(session)
    except (ValueError, OSError, KeyError, TypeError) as error:
        return out.model_copy(update={"damaged": [f"the session's ledger could not be read ({error})"]})
    out = out.model_copy(update={"session_spent_usd": float(status["spent"]), "session_cap_usd": float(status["cap"]),
                                 "session_reserved_usd": float(status["reserved_uncertain"]),
                                 "session_remaining_usd": float(status["remaining"])})
    if kind_of(job) == "discovery":
        opened = job.command[1:2] != ["resume"]
        out = out.model_copy(update={
            "run_usd": out.session_spent_usd, "run_uncertain_usd": out.session_reserved_usd, "scope": "session",
            "settled_precision": "journal", "requests": _facts(requests, f"session:{session}"),
            "run_source": "the session's paid ledger: every request of the session, which this run "
                          + ("opened" if opened else "resumed") + " (the extractions that share its budget included)",
            "none_sent_evidence": "" if requests else "the session's paid ledger holds no request"})
        return _own(out, folder, requests, expected)
    receipt, damage, foreign = _receipt(folder, expected)
    if damage:
        return out.model_copy(update={"damaged": [damage], "foreign": [damage] if foreign else []})
    if receipt is not None:
        return _from_receipt(out, receipt, requests)
    if free:
        return out.model_copy(update={"run_usd": 0.0, "run_source": "a free step (typed or field content: no "
                                                                    "language-model request)",
                                      "none_sent_evidence": "a typed or field-content step sends no request"})
    return _from_log(out, folder, job, expected)


def _discovery_cost(folder: Path, job, session: str, disagree: list[str], expected: str) -> Cost:
    """A discovery run's cost, of the session its own records name (``discovery_session``), with what disagrees named
    beside it (a conflict: "records incomplete"); where its session is not established, no figure for the run or its
    session, and why (DL-04)."""
    if not session and disagree:
        return Cost(paid=True, scope="session", damaged=disagree)
    out = session_cost(folder, job, session, "source", expected)
    return out.model_copy(update={"conflicts": [*out.conflicts, *disagree]}) if disagree else out


def _own(out: Cost, folder: Path, requests: dict, expected: str = "") -> Cost:
    """A session-scope run's own requests beside its session's figure (``own_usd``), from its request record
    (``preflight.record_requests``): the survey's own cost stays what it was when an extraction that shares the
    session's budget spends, while the session's figure rises (the gap plan's G5 and H9). A run from before the record
    has none; a record that cannot be read, does not match the ledger or names another run is named, and gives none."""
    receipt, damage, foreign = _receipt(folder, expected)
    if receipt is None:
        return out.model_copy(update={"damaged": [*out.damaged, damage], "foreign": [damage] if foreign else []}) \
            if damage else out
    own = _from_receipt(out, receipt, requests)
    if own.damaged and own.damaged != out.damaged:
        return out.model_copy(update={"damaged": [*out.damaged, *own.damaged]})
    return out.model_copy(update={"own_usd": own.run_usd, "own_uncertain_usd": own.run_uncertain_usd})


def _receipt(folder: Path, expected: str = ""):
    """(the run's own requests, ``model_intake.RunRequests``, or None for a run from before the record; why the record
    cannot be read or is not this run's, or ""; whether it names another run). An unreadable or invalid record is
    damage, never a run from before it (M2: it had been read as one, and the cost then taken from the log), and so is
    an entry there that leads to nothing, a link to a missing file (DN-01); one naming another run than ``expected``
    is not this run's (DE-01)."""
    from adroit.orchestrator.model_intake import REQUESTS, RunRequests
    path = Path(folder) / REQUESTS
    if absent(path):                                   # no entry at all: a link to nothing is damage (DN-01)
        return None, "", False
    try:
        receipt = RunRequests.model_validate_json(path.read_text())
    except (OSError, ValueError) as error:
        return None, (f"the run's request record ({REQUESTS}) cannot be read "
                      f"({linked(path)}{str(error).splitlines()[0]})"), False
    if expected and receipt.attempt and receipt.attempt != expected:
        return None, _another(f"its request record ({REQUESTS})", receipt.attempt, expected), True
    return receipt, "", False


def _from_receipt(out: Cost, receipt, requests: dict) -> Cost:
    """This run's settled and uncertain dollars: its own requests, as the session's ledger records them. The receipt
    is a set: one naming a request twice is not the record its writer keeps (CA-06)."""
    if receipt.session_id != out.session_id:
        return out.model_copy(update={"damaged": ["the run's request record names another session"]})
    if len(set(receipt.request_ids)) != len(receipt.request_ids):
        return out.model_copy(update={"damaged": ["the run's request record names a request more than once: it is not "
                                                  "the record its writer keeps"]})
    mine = {key: requests.get(key) for key in receipt.request_ids}
    if any(r is None for r in mine.values()):
        return out.model_copy(update={"damaged": ["the session's ledger lacks some of this run's requests"]})
    settled = sum(r.cost_usd for r in mine.values() if r.state == "settled")
    uncertain = sum(r.reserved_usd for r in mine.values() if r.state != "settled")
    source = (f"the session's paid ledger: {len(mine)} request(s) of this run" if mine
              else "the run's request record: it names no request")
    return out.model_copy(update={"run_usd": settled, "run_uncertain_usd": uncertain, "run_source": source,
                                  "settled_precision": "journal", "requests": _facts(mine, f"session:{out.session_id}"),
                                  "none_sent_evidence": "" if mine else "the run's request record names no request"})


def _from_log(out: Cost, folder: Path, job: JobFacts, expected: str = "") -> Cost:
    """A run from before the request record: the session's committed dollars its log printed before its first
    request, and the session's spending it printed at the end (both read from the ledger then); not where its log
    names another run (DE-01)."""
    text, foreign, unread = _log_text(folder, expected)
    if foreign:
        return out.model_copy(update={"damaged": foreign, "foreign": foreign})
    if unread:
        return out.model_copy(update={"damaged": [*out.damaged, *unread]})
    before = PREFLIGHT.search(text)
    after = _last_status(text)
    if after is None or before is None:
        reason = ("the run is still going" if job.status == "running" else
                  "the run recorded no request list, and its log does not show the session's totals before and after")
        return out.model_copy(update={"note": f"this run's own cost is {NOT_AVAILABLE}: {reason}"})
    committed = float(after["spent"]) + float(after.get("reserved_uncertain", 0.0) or 0.0) - float(before.group(1))
    if after.get("reserved_uncertain"):      # settled and reserved cannot be told apart from the two totals
        return out.model_copy(update={"run_committed_usd": max(committed, 0.0),
                                      "run_source": "the session ledger's totals before and after this run, as its "
                                                    "log printed them"})
    return out.model_copy(update={"run_usd": max(committed, 0.0), "settled_precision": "session totals",
                                  "run_source": "the session ledger's totals before and after this run, as its log "
                                                "printed them (to $0.0001)"})


def _last_status(text: str) -> dict | None:
    """The last budget status a session command printed (one line with cap and spent, as JSON or as a Python dict),
    or None."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and "spent" in line and "cap" in line):
            continue
        for parse in (json.loads, ast.literal_eval):
            try:
                data = parse(line)
            except (ValueError, SyntaxError):
                continue
            if isinstance(data, dict) and isinstance(data.get("spent"), (int, float)):
                return data
    return None


OTHER_RUN = ("the run recorded in its folder (job.json) is not the one that published this study, so its cost is not "
             "this study's")


def study_cost(folder: Path, recorded_usd: float = 0.0, attempt: str | None = None, held: Held | None = None) -> Cost:
    """A study's cost: its run's (``cost``), where the study is a workbench run's folder; where its run's record
    cannot be read, not available, and why; else the study record's dollars, settled ones alone (a study run from the
    command line keeps no request list beside it).

    ``attempt``: for a study record that names its result, the run it names as its publisher (``Study.attempt``; ""
    for none). The run in the folder is read as the study's only where it is that run; otherwise the study record's own
    dollars are its cost, saying so (``other_run``). The auditor's DB/VI recheck, DC-01 (2026-11-03): a page holding study
    A had shown, as A's, the cost of a later run in the same folder. None: a record written before records named their
    run, read as found, or no study (a batch item's run).

    The run is the one named over the whole read (the auditor's version-handle audit, DD-02, 2026-11-04: checked once, before
    its ledger and records were read, a later run's bill had been shown as the study's): its record is read again after
    them, and the cost is that run's only where the record still names it; otherwise its study record's dollars, saying
    so. And every record read is that run's (the auditor's DD recheck, DE-01, 2026-11-05: another run's records read between
    two readings of the study's run's record, then the study's restored byte for byte, had been counted as the study's
    and their bill shown as its own): each record of a run's money names the run that wrote it, and one naming another
    is not counted (``cost``'s ``expected``); and the two readings of the run's record agree only where nothing wrote it
    between them, not even its own bytes again (``JobFacts.seen``). Where either fails, the cost is read again, up to
    ``TRIES`` times; then its study record's dollars, saying why (another run's records in its folder, or its run's
    records changing at every reading). ``held``: the study record and result of the version a page holds
    (``held_cost``)."""
    folder = Path(folder)
    if absent(folder / JOB):                           # a run record there that cannot be read is damage (DN-01)
        return _recorded(recorded_usd)
    for _ in range(TRIES):
        job = read_job(folder)
        if job is None:
            return _with_notes(Cost(paid=True, damaged=[f"its run's record, {JOB}, cannot be read"]))
        if attempt is not None and not (attempt and job.attempt == attempt):
            return _other_run(recorded_usd)
        found = cost(folder, job, held, attempt)
        again = read_job(folder)
        if again is None:
            return _with_notes(Cost(paid=True, damaged=[f"its run's record, {JOB}, cannot be read"]))
        if attempt is not None and again.attempt != attempt:
            return _other_run(recorded_usd)
        if again == job and not found.foreign:
            return found
        changed = again != job
    if found.foreign and not changed:            # its run record steady, beside another run's records
        return _other_run(recorded_usd, found.foreign)
    return _unsettled(recorded_usd, attempt is not None)


TRIES = 4                        # readings of a run whose records change while its cost is read (its status, say)
UNSETTLED = (f"its run's record ({JOB}) was written while its cost was read, at each of {TRIES} readings, so no reading "
             "is of one run's records throughout")
FOREIGN = "records in its folder name another run than the one that published this study, so they are not its cost"


def _other_run(recorded_usd: float, foreign: list[str] | None = None) -> Cost:
    """A study's own record's dollars, where the run in its folder is not the one that published it (DC-01, DD-02),
    or where records read beside its run's record name another run (``foreign``, DE-01), saying which."""
    own = _recorded(recorded_usd)
    words = [FOREIGN, *foreign] if foreign else [OTHER_RUN]
    return own.model_copy(update={"other_run": True, "foreign": list(foreign or []),
                                  "note": "; ".join(filter(None, [*words, own.note]))})


def _unsettled(recorded_usd: float, study: bool) -> Cost:
    """Where its run's records changed at every reading (DE-01): a study's own record's dollars, saying so; a run with
    no study record (a batch item's), not available."""
    if not study:
        return _with_notes(Cost(paid=True, unsettled=True, note=f"this run's cost is {NOT_AVAILABLE} now: {UNSETTLED}"))
    own = _recorded(recorded_usd)
    return own.model_copy(update={"unsettled": True, "note": "; ".join(filter(None, [UNSETTLED, own.note]))})


NOT_THE_RESULTS = {"other": "describes another version of its result",
                   "interrupted": "may be an earlier publication's (its last publication was interrupted)"}


def held_cost(version) -> Cost:
    """The cost of a held study (an ``evidence.version.Version``): ``study_cost`` of the run its record names, its
    record's dollars and its result (a budget stop's record) as the version holds them (``Held``), never the folder's
    files read again (the auditor's version-handle audit, DD-02, 2026-11-04). The study's card, its line in Studies and
    ``adroit studies`` read it.

    A record that is not the result's (another version's, or an interrupted publication's: ``Version.record_state``)
    gives no cost: its dollars and the run it names may be another publication's, so the cost is not known, saying why
    (the auditor's portability audit, IC-01, 2026-11-10: an interrupted publication's card and list had given the earlier
    publication's $0.08)."""
    if (why := NOT_THE_RESULTS.get(version.record_state)) is not None:
        return _with_notes(Cost(paid=True, damaged=[f"its study record {why}: its cost is not known"]))
    study = version.study()
    return study_cost(version.folder, study.cost_usd if study is not None else 0.0, version.publisher(),
                      _held(version, study))


def _held(version, study) -> Held:
    """A version's own records for its run's cost (``Held``), named where it cannot read them."""
    unheld = {"unreadable": "cannot be read", "unread": "was not read with its study (too large)"}
    damaged = (["its study record (study.json) cannot be read: what it records the run cost is not known"]
               if study is None and version.record_state in ("unreadable", "damaged") else [])
    return Held(content=version.content, unheld=unheld.get(version.result_state, ""), damaged=damaged,
                recorded=_dollars(study.cost_usd) if study is not None else None, study=study is not None)


def _recorded(recorded_usd: float) -> Cost:
    """A study record's own dollars, settled ones alone."""
    if recorded_usd:
        return Cost(run_usd=float(recorded_usd), settled_only=True, paid=True, run_source="its study record",
                    settled_precision="study record")
    return Cost(note="no settled cost recorded")


# --- the words ---------------------------------------------------------------------------------------------------

def _who(c: Cost) -> str:
    """Whose cost a line gives: this run's, or (a discovery run) its whole session's."""
    return "This run's session" if c.scope == "session" else "This run"


def short_line(c: Cost) -> str:
    """A run's cost in a few words, for a list (``run_line`` in full): "$0.0024", "$0.0024 settled + up to $0.40
    reserved", "about $0.12", "up to $0.31 committed", "cost not available", or "" for a run that sent nothing; a
    reservation or committed bound beside another figure is kept, and records that are damaged or disagree are said
    to be so (CA-05); a session's figure says so."""
    reserved = f" + up to {usd(c.run_uncertain_usd)} reserved" if c.run_uncertain_usd else ""
    if c.run_usd is None:
        text = (f"settled {NOT_AVAILABLE}{reserved}" if reserved else f"up to {usd(c.run_committed_usd)} committed"
                if c.run_committed_usd is not None else "")
    else:
        text = (f"about {usd(c.run_usd)}" if c.run_approximate else f"{usd(c.run_usd)} settled"
                if reserved or c.settled_only or _beyond(c) else usd(c.run_usd) if c.run_usd else "") + reserved
    if _beyond(c):
        text += f" (up to {usd(c.run_committed_usd)} committed)"
    if c.other_run or (c.unsettled and (c.settled_only or not c.paid)):    # its study record's figure (DC-01, DE-01)
        why = ("its run's records changed while read" if not c.other_run else
               "another run's records are in its folder" if c.foreign else "the run in its folder is another")
        return (f"{text} (its study record's; " if text else "no cost in its study record (") + why + ")"
    if not text:
        return f"cost {NOT_AVAILABLE}" if c.run_usd is None else ""
    if c.scope == "session":
        own = "" if c.own_usd is None else f"; this run's own {_own_words(c, short=True)}"
        text += f" (its whole session{own})"
    return text + (" · records incomplete" if c.damaged or c.conflicts or c.note and c.run_usd is not None else "")


def _beyond(c: Cost) -> bool:
    """Whether a committed bound says more than the settled and reserved dollars beside it."""
    return (c.run_committed_usd is not None and c.run_usd is not None
            and c.run_committed_usd > c.run_usd + c.run_uncertain_usd + SPLIT_TOLERANCE)


def run_line(c: Cost) -> str:
    """This run's cost in words: settled, reserved whose bill is not known, approximate, committed together, or not
    available, each figure a record gives kept beside the others, with any damage or disagreement named; $0 is "no
    paid request was sent" only where a record shows it."""
    who = _who(c)
    if c.run_usd is None and c.run_committed_usd is not None and not c.run_uncertain_usd:
        return (f"{who}: up to {usd(c.run_committed_usd)} committed, settled and still-reserved dollars together "
                "(its record does not tell them apart)" + (f"; {c.note}" if c.note else ""))
    if c.run_usd is None and not c.run_uncertain_usd:
        return f"{who}: {NOT_AVAILABLE}" + (f" ({c.note})" if c.note else "")
    if c.run_usd is None:
        run = f"{who}: settled dollars {NOT_AVAILABLE}"
    elif c.run_approximate:
        run = f"{who}: about {usd(c.run_usd)} (rounded to the cent in its log)"
    elif c.settled_only:
        run = (f"{who}: {usd(c.run_usd)} settled, as {c.run_source} shows (it keeps settled dollars alone: a "
               "request whose bill is not known is not in it)")
    elif c.run_uncertain_usd or _beyond(c):
        run = f"{who}: {usd(c.run_usd)} settled"
    elif c.run_usd:
        run = f"{who}: {usd(c.run_usd)}"
    elif not c.paid:
        run = f"{who}: $0 (no paid request)"
    elif c.sent_none or c.none_sent_evidence:
        run = f"{who}: $0 (no paid request was sent)"
    else:
        run = f"{who}: $0 settled, as {c.run_source or 'its record'} shows"
    if c.run_uncertain_usd:
        run += f", and up to {usd(c.run_uncertain_usd)} reserved whose bill is not yet known"
    if _beyond(c):
        run += f"; {c.committed_source or 'its budget-stop record'} shows up to {usd(c.run_committed_usd)} committed in all"
    if c.scope == "session" and c.own_usd is not None:
        run += f"; this run's own requests: {_own_words(c)}"
    return run + (f" ({c.note})" if c.note else "")


def _own_words(c: Cost, short: bool = False) -> str:
    """A session-scope run's own requests in words (``own_usd``): "$0.0008", "$0 settled, and up to $0.40 reserved
    whose bill is not yet known" ("+ up to $0.40 reserved", ``short``)."""
    if not c.own_uncertain_usd:
        return usd(c.own_usd) if c.own_usd else "$0"
    reserved = (f" + up to {usd(c.own_uncertain_usd)} reserved" if short
                else f", and up to {usd(c.own_uncertain_usd)} reserved whose bill is not yet known")
    return f"{usd(c.own_usd or 0.0)} settled{reserved}"


def cost_lines(c: Cost) -> list[str]:
    """The cost in words: this run's, then its session's spending and approved cap, or a run's approved budget."""
    lines = [run_line(c)]
    if c.session_id and c.session_spent_usd is not None:
        lines.append("Session total so far: " + session_text(c.session_spent_usd, c.session_cap_usd or 0.0,
                                                             c.session_reserved_usd, c.session_remaining_usd))
    elif c.session_id or c.scope == "session":         # a session not established is named so (DL-04)
        lines.append(f"Session total: {NOT_AVAILABLE}")
    elif c.budget_usd:
        lines.append(f"Approved budget for this run: {usd(c.budget_usd)}")
    return lines


def session_text(spent: float, cap: float, reserved: float, remaining: float | None = None) -> str:
    """A paid session's money in words, the one wording of every page that shows it (the run page, the model
    library's, the experimental library's and constraint discovery's sessions, their command lines): "$0.0008 spent
    of its approved $1.00 cap ($0.9582 left); $0.0410 reserved whose bill is not yet known". What is left is the
    account's (``remaining``, ``budget_status``); a caller without it gets the cap less the settled and the reserved
    dollars, which is how the account computes it (the consistency audit's CA-04, 2026-10-24: the experimental
    session showed "$0.00 of $1.00 spent · $1.00 left", its reservation dropped and its settled cents rounded away)."""
    if cap == 0 and spent == 0 and reserved == 0:
        return "$0 (no paid budget: typed and field-content steps only)"
    left = max(cap - spent - reserved, 0.0) if remaining is None else remaining
    return (f"{usd(spent)} spent of its approved {usd(cap)} cap ({usd(left)} left)"
            + (f"; {usd(reserved)} reserved whose bill is not yet known" if reserved else ""))


def status_text(status: dict) -> str:
    """``session_text`` of a session's ``budget_status``."""
    return session_text(float(status["spent"]), float(status["cap"]), float(status["reserved_uncertain"]),
                        float(status["remaining"]) if "remaining" in status else None)


def session_money(budgets, session: str) -> str:
    """``session_text`` of a session's own paid ledger (``budgets``: its library's session service), or "spending not
    available (why)". The session given must be the one that holds the budget (an extraction sharing a discovery
    session's budget: that session, ``ExperimentalExtraction.budget_owner``)."""
    try:
        return status_text(budgets.budget_status(session))
    except (TypeError, KeyError, ValueError, OSError) as error:
        return f"spending {NOT_AVAILABLE} ({error})"


def live_text(settled: float, reserved: float) -> str:
    """A running command's spending from its own account, as its closing line prints it and the workbench reads it
    back (``SPENT_LINE``, ``RESERVED``): "spent $0.0024", or "spent $0.0024 settled, and up to $0.4000 reserved for
    requests whose bill is not known"."""
    return f"spent ${settled:.4f}" + (f" settled, and up to ${reserved:.4f} reserved for requests whose bill is "
                                      "not known" if reserved > 0 else "")


def account_text(account) -> str:
    """``live_text`` of a command's budget account (``agents.budget.BudgetAccount``): its settled dollars and its
    open or uncertain reservations, as the account holds them."""
    return live_text(sum(account.spent.values()), sum(v for _, v in account.reservations.values()))


# --- several runs (D-6) ------------------------------------------------------------------------------------------

class Total(StrictModel):
    """What several runs cost together (D-6): each identifiable request counted once, however many runs or studies
    name it (a discovery and the extractions sharing its session; a run and its study), and apart from it what older
    records give without naming their requests."""
    settled_usd: float = 0.0              # identifiable requests' settled dollars, each request once
    reserved_usd: float = 0.0             # identifiable requests whose bill is not known, each once
    requests: int = 0
    legacy_settled_usd: float = 0.0       # settled dollars of records naming no request: overlap with the rest unknown
    legacy_reserved_usd: float = 0.0      # reservations stated by such records
    approximate_usd: float = 0.0          # read from lines rounded to the cent
    committed_usd: float = 0.0            # budget-stop bounds not split (each run's settled dollars inside its bound)
    beyond_usd: float = 0.0               # what records commit beyond their runs' identifiable requests (CO-04)
    unavailable: int = 0                  # paid runs whose accounting cannot be read or was not reported
    incomplete: int = 0                   # runs counted above whose records are damaged or disagree


def total(costs: Iterable[Cost]) -> Total:
    """The facts of several runs together (``Total``): requests deduplicated by their ledger and identifier; older
    records counted apart and qualified; nothing summed twice by a parent and its children."""
    seen: dict[str, RequestFact] = {}
    out = Total()
    legacy = {"legacy_settled_usd": 0.0, "legacy_reserved_usd": 0.0, "approximate_usd": 0.0, "committed_usd": 0.0}
    for c in costs:
        if c.requests:
            seen.update(c.requests)
            out.incomplete += bool(c.damaged or c.conflicts)
            if _beyond(c):                     # a record commits more than the requests show: kept, not added twice
                out.beyond_usd += c.run_committed_usd - (c.run_usd or 0.0) - c.run_uncertain_usd
            continue
        if c.run_usd is None and c.run_committed_usd is None and not c.run_uncertain_usd:
            out.unavailable += c.paid or bool(c.damaged) or c.unsettled
            continue
        out.incomplete += bool(c.damaged or c.conflicts)
        if c.run_committed_usd is not None and (c.run_usd is None or _beyond(c)):
            legacy["committed_usd"] += c.run_committed_usd       # its settled and reserved dollars are inside it
            continue
        if c.run_approximate:
            legacy["approximate_usd"] += c.run_usd or 0.0
        else:
            legacy["legacy_settled_usd"] += c.run_usd or 0.0
        legacy["legacy_reserved_usd"] += c.run_uncertain_usd
    return out.model_copy(update={"settled_usd": sum(f.settled_usd for f in seen.values()),
                                  "reserved_usd": sum(f.reserved_usd for f in seen.values()),
                                  "requests": len(seen), **legacy})


def total_text(t: Total) -> str:
    """A total in words: the identifiable requests' settled and reserved dollars, each request once, then what older
    records add with their overlap unknown, the approximate and committed-only figures, and the runs whose accounting
    is not available. Never "$0 spent" where a run's accounting is missing."""
    parts = [f"{usd(t.settled_usd)} settled over {t.requests} identifiable request(s), each counted once"
             + (f", and up to {usd(t.reserved_usd)} reserved whose bill is not yet known" if t.reserved_usd else "")]
    if t.legacy_settled_usd:
        parts.append(f"{usd(t.legacy_settled_usd)} more settled in older records that name no request (their overlap "
                     "with the rest is not known)")
    if t.legacy_reserved_usd:
        parts.append(f"up to {usd(t.legacy_reserved_usd)} more reserved, as older records state")
    if t.approximate_usd:
        parts.append(f"about {usd(t.approximate_usd)} more, rounded to the cent")
    if t.committed_usd:
        parts.append(f"up to {usd(t.committed_usd)} committed in records that do not split it into settled and "
                     "reserved dollars")
    if t.beyond_usd:
        parts.append(f"up to {usd(t.beyond_usd)} more committed, as runs' other records show beyond their paid "
                     "ledgers (records that disagree)")
    if t.unavailable:
        parts.append(f"{t.unavailable} run(s) whose accounting is {NOT_AVAILABLE}")
    if t.incomplete:
        parts.append(f"{t.incomplete} run(s) whose records are damaged or disagree (see each)")
    return "; ".join(parts)

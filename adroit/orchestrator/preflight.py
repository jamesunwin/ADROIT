"""Hard rule 6 at the command line: before any paid dispatch, the model, the hard cap and the estimated cost.

A paid command first states its model and hard cap (``start_line``). Then, before each request is sent, the
budgeted client reserves the request's largest possible cost against the cap and the command shows that
reservation (``agents.llm.preflight_line``), so the cost of every dispatch is visible before it happens. The lines
go to standard error, which keeps a command's standard output (JSON drafts, reports) machine-readable.
"""

from __future__ import annotations

import math
from functools import wraps

import typer


def start_line(model: str, cap: float) -> str:
    """A paid command's opening statement: its model, its hard cap, and the reminder the workbench shows under
    every model choice (the owner, 2026-10-16)."""
    return (f"Opt-in paid command: {model}; hard cap ${cap:.2f}. Before each request is sent, its largest possible "
            "cost is reserved against the cap and shown here. AI can make mistakes.")


def show(line: str) -> None:
    """Show a preflight line (on standard error)."""
    typer.echo(line, err=True)


JOB_LEDGER = "paid.jsonl"
JOB_OUTPUT = "file_output.json"     # a workbench job's file output outside its folder: its path and sha256


def job_folder():
    """The workbench job a command runs in (the folder its runner names in ADROIT_JOB_FOLDER), None outside one."""
    from pathlib import Path
    from adroit.core.config import env
    folder = env("JOB_FOLDER")
    return Path(folder) if folder else None


def job_attempt(folder) -> str:
    """The attempt of the workbench job a command runs in (ADROIT_JOB_ATTEMPT, ``engine.Job.attempt``), where
    ``folder`` is that job's folder; "" outside a job, or for another folder: what a study record written in ``folder``
    names as the run that published it (``studies.record``; the auditor's DB/VI recheck, DC-01, 2026-11-03)."""
    from pathlib import Path
    from adroit.core.config import env
    job = job_folder()
    return env("JOB_ATTEMPT") if job is not None and job.resolve() == Path(folder).resolve() else ""


def run_attempt() -> str:
    """The attempt of the workbench job a command runs in, "" outside one: what each record of the run's money names
    as the run that wrote it (its paid ledger, its request record, a budget stop's record), wherever it is written, so
    that a study's cost counts only records of the run that published it (the auditor's DD recheck, DE-01, 2026-11-05)."""
    from adroit.core.config import env
    return env("JOB_ATTEMPT") if job_folder() is not None else ""


def open_job_ledger(ledger) -> None:
    """A workbench job's own paid ledger, opened by this run before any request: made where nothing at all is at its
    path (never through a link: ``durable.append_held``), and an ``opened`` entry naming the run's attempt journalled,
    whole and synced as the budgeted client journals (``budget.read_owned`` reads it), so that the requests a reading
    counts are known to be this run's (DE-01). An entry there that cannot be read (a link leading nowhere among them)
    is a damaged ledger: refused (``ValueError``), nothing made or written, so that what the run spent stays unknown
    rather than read as nothing (the auditor's DN recheck, DO-01, 2026-11-08: ``touch`` had made a link's missing target, and
    the run's page then said that no paid request was sent). What it holds once opened is what the run's budgeted client must find it
    still begins with (``budget.OPENED``). One that is there but not whole (a torn last line, a line that is not one of
    its entries) is refused as well (``ValueError``, naming it and, for a torn line, its recovery), nothing written,
    so that the run sends nothing through it (the auditor's DO recheck, DP-01, 2026-11-09: a torn ledger had been held as
    opened, and the run's first request sent after its torn line)."""
    import json
    import os
    from pathlib import Path
    from adroit.agents.budget import OPENED, journal_whole, ledger_bytes
    from adroit.core.durable import Held, absent, append_held
    ledger = Path(os.path.abspath(ledger))
    data = ledger_bytes(ledger)               # one that cannot be read, or missing beside its mark, raises
    journal_whole(data, ledger)               # and one that is not whole
    held = append_held(ledger, b"", None, whole=journal_whole) if absent(ledger) else Held.of(data)
    attempt = run_attempt()
    if attempt:
        held = append_held(ledger, (json.dumps({"state": "opened", "attempt": attempt}) + "\n").encode(), held,
                           whole=journal_whole)
    OPENED[str(ledger)] = held


def job_ledger(default=None):
    """Where a paid command that has no session journals its requests: in a workbench run, the job's own paid ledger
    (``JOB_LEDGER`` in its folder), so that the run's cost is read from its own requests, the settled and the
    uncertain apart (the workflow audit's WA-03, 2026-10-24: a settled $0.0024 had been read from the log's "spent
    $0.00" as no request sent); else ``default`` (None: the client's own file under runs/budgets)."""
    folder = job_folder()
    return folder / JOB_LEDGER if folder is not None else default


def spent_text(llm) -> str:
    """A paid command's spending, to the hundredth of a cent: what is settled, and what stays reserved for requests
    whose bill is not known, as its account holds them (``accounting.account_text``; a whole-cent "spent $0.00" had
    hidden a settled $0.0024, WA-03)."""
    from adroit.orchestrator.accounting import account_text
    return account_text(llm.account)


def paid_command(function):
    """Run a command with every paid request's preflight shown; a command that takes ``--model`` and a positive
    ``--budget`` first shows its start line (session commands show theirs from the session). In a workbench job, a
    paid command first opens the job's paid ledger, naming its run and holding no request, so that a ledger with no
    request says no request was sent (``job_ledger``) and whose requests it holds is known (``open_job_ledger``)."""
    @wraps(function)
    def run(*args, **kwargs):
        from adroit.agents.llm import preflight
        if kwargs.get("budget") and kwargs.get("model"):
            show(start_line(kwargs["model"], kwargs["budget"]))
        ledger = job_ledger()
        if kwargs.get("budget") and ledger is not None:
            try:
                open_job_ledger(ledger)
            except ValueError as error:                   # a damaged ledger: nothing is sent (DO-01)
                raise typer.BadParameter(str(error)) from None
        with preflight(show):
            return function(*args, **kwargs)
    return run


def cap_options(app: str, session: str, reserved: float, committed: float, cap: float,
                trimmed: float | None = None) -> list[str]:
    """What a researcher can do when a session's cap cannot cover its next request: raise the cap (a confirmed,
    journalled change) or, for a refinement, send the compacted prior dossier (``--trim``)."""
    need = math.ceil((committed + reserved) * 100) / 100
    lines = [f"The session cap cannot cover the next request: ${committed:.4f} committed + ${reserved:.4f} "
             f"reserved exceeds the ${cap:.2f} cap. Nothing was sent.",
             f"- raise the cap (kept in the session and its paid ledger): adroit {app} raise-cap {session} "
             f"--budget {need:.2f} --confirmed"]
    if trimmed is not None:
        fits = "fits the current cap" if committed + trimmed <= cap else "still above the current cap"
        lines.append(f"- or refine with the compacted prior dossier (--trim): reserves up to ${trimmed:.4f}, {fits}")
    return lines


def raise_cap_command(service, session: str, budget: float, confirmed: bool, reason: str) -> None:
    """The shared body of ``models raise-cap`` and ``experiments raise-cap``."""
    try:
        before = service.session(session).budget
        s = service.raise_cap(session, budget, confirmed=confirmed, reason=reason)
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(f"session {session}: cap raised from ${before:.2f} to ${s.budget:.2f} (recorded); "
               f"pass --budget {s.budget:g} to its paid commands")


def _requests(service, session: str) -> str:
    """A session command's own paid requests (``model_intake.RunRequests``: the ledger identifiers its budgeted clients
    reserved), as its output folder keeps them, so that the workbench reads that run's cost from the session's ledger,
    apart from the session's other requests (the owner's report of 2026-10-23)."""
    from adroit.orchestrator.model_intake import RunRequests
    return RunRequests(session_id=session, request_ids=service.request_ids(),
                       attempt=run_attempt()).model_dump_json(indent=2)


def session_export(out, service, session: str, members: dict) -> None:
    """A session command's export, ``members`` (its files by name, each prepared whole) and its request record
    (``model_intake.REQUESTS``) written as one export (``durable.export``: under one hold of the folder, each file whole
    to its own entry, never beside a saved study's records), so that the record beside a draft or a report is that
    run's (the auditor's DJ recheck, DK-01, 2026-11-07: it had been written apart, outside the export's hold). The record
    first: a run killed while its export is written still records its requests (the folder then reads as incomplete,
    ``durable.interrupted``). Nothing without ``out``; ``ValueError`` (``Busy`` too) or ``OSError`` where it cannot be
    written, the folder's earlier files put back."""
    if out is None:
        return
    from adroit.core.durable import export
    from adroit.orchestrator.model_intake import REQUESTS
    export(out, {REQUESTS: _requests(service, session), **members})


def record_requests(out, service, session: str, members=()) -> None:
    """A session command that stopped: its request record (``session_export``) in its output folder, with each of its
    export's files (``members``, by name) removed, so that no earlier export's draft or report is left beside it as
    this run's. Written only where the run has something to record, a request it reserved, or the folder is its own
    (its workbench job's, which the runner made for it): a command refused before it sent anything (an output folder
    holding a saved study, a session it cannot open, a budget it was not given) writes nothing there (the auditor's DJ
    recheck, DK-01, 2026-11-07: a refused command's empty record had replaced a study's own, outside the folder's
    hold, and the study's $1.25 was then read as no request sent). Nothing is written without ``out``; a failure to
    write is said, and the ledger still holds every request."""
    from pathlib import Path
    if out is None:
        return
    job = job_folder()
    own = job is not None and job.resolve() == Path(out).resolve()
    if not (own or service.request_ids()):
        return
    try:
        session_export(out, service, session, dict.fromkeys(members))
    except (OSError, ValueError) as error:
        typer.echo(f"The run's request record was not written ({error}); the session ledger keeps every request.")

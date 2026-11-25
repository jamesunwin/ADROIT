"""Why a workbench job did not complete, and the existing action that recovers it (the owner's workbench plan of
2026-10-18, part 2 §F).

``diagnose`` reads only the job's record (``job.json``), its log's last lines, whether a Track 1 checkpoint
exists and whether the calculation its record names still runs. It sorts the job into one of a few kinds, each with the action ADROIT already has: a budget stop (the cap
command the log printed), a missing dependency (the exact ``adroit setup`` command), invalid input (back to the form
or a reanalysis), an interruption (Resume for an interrupted Track 1 run with a checkpoint, else run again), or an
ordinary failure (the log, and its form again: starting over guesses nothing about the cause; the owner, 2026-11-19). A failed or cancelled job whose calculation still runs is that, with Cancel, before
anything else (``engine.left_running``; a feature audit's ID-01, 2026-11-10: it had read "the process ended without
a word", with Resume, which the running calculation refused). Text it does not recognise never gets a guessed action.

**What has been seen** (the owner, 2026-11-19: the menu's "need attention" had no way to be cleared). Opening the
Activity page records each item that needs attention as it then is (``mark_seen``, the runs folder's ``SEEN``), and
the menu counts only what that record does not hold (``summary``): a run that fails afterwards, or one seen that has
since changed, is counted again. The Activity page lists every item as before. A record that is missing or cannot be
read holds nothing, so that damage to it can only show more, never hide a failure.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field

from adroit.core.state import StrictModel

Kind = Literal['running', 'completed', 'budget', 'dependency', 'input', 'interrupted', 'failed']
# every target is a served page: a native fit's form is withdrawn (OR-03), so it is offered none (MF-05: a 404)
FORMS = {'track1': '/new/track1', 'signal': '/new/track2', 'single-idea': '/new/single',
         'idea': '/new/track1', 'lagrangian': '/new/track1'}
DEPENDENCY = re.compile(r'not in the tools|backend unavailable|not installed|No module named|FileNotFoundError|'
                        r'adroit setup|pdftoppm|command not found|is not on this machine', re.I)
RAISE_CAP = re.compile(r'adroit \S+ raise-cap \S+ --budget [0-9.]+ --confirmed')
RECENT = timedelta(days=7)
SEEN = '.activity_seen.json'           # in the runs folder: what the Activity page last showed as needing attention


class Action(StrictModel):
    """One recovery action: a page, an exact command, Resume (``engine.resume``) or Cancel (``engine.cancel``)."""
    label: str
    target: str = ''
    kind: Literal['page', 'command', 'resume', 'cancel']


class Diagnosis(StrictModel):
    """A job's state in plain words, the log lines that show it, what to do, and why its log cannot be read, or ""."""
    kind: Kind
    summary: str
    actions: list[Action] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    log_unreadable: str = ''


UNREAD = 'its log cannot be read, so what it said is not known here'


def _tool(lines: list[str]) -> str:
    """The name of a setup-manifest item the log mentions, if any."""
    from adroit.external.manifest import load_manifest
    text = '\n'.join(lines)
    return next((item.name for item in load_manifest().items() if item.name in text), '')


def diagnose(job, lines: list[str], folder: Path, unreadable: str = '') -> Diagnosis:
    """The job's diagnosis (module docstring); ``lines`` are its log's last lines, the command's own words, and
    ``unreadable`` why its log cannot be read, or "" (``engine.read_log``). A log that cannot be read is carried apart
    (``Diagnosis.log_unreadable``), never read as what the command said: the diagnosis is then what the job's record
    establishes, and never a missing tool for want of a log (the auditor's DO recheck, DP-03, 2026-11-09: a log that led
    nowhere had been diagnosed as a missing dependency, with setup offered)."""
    found = _diagnose(job, lines, Path(folder))
    if not unreadable:
        return found
    summary = found.summary if found.kind != 'failed' else f'failed; {UNREAD}'
    return found.model_copy(update={'summary': summary, 'log_unreadable': unreadable})


def _diagnose(job, lines: list[str], folder: Path) -> Diagnosis:
    """``diagnose`` from the job's record and its log's own lines."""
    form = FORMS.get(job.kind, '')
    again = [Action(label='open the form again', target=form, kind='page')] if form else []
    if job.status == 'running':
        return Diagnosis(kind='running', summary='running')
    left = _left_running(job)
    if left:
        return Diagnosis(kind='interrupted', summary=left[:1].lower() + left[1:],
                         actions=[Action(label='cancel its calculation', kind='cancel')])
    if job.status == 'completed':
        study = (folder / 'study.json').exists()
        return Diagnosis(kind='completed', summary='completed', actions=[
            Action(label='open the study', target='study', kind='page')] if study else [])
    if job.status == 'budget_stopped' or job.returncode == 3:
        commands = list(dict.fromkeys(m.group(0) for line in lines for m in RAISE_CAP.finditer(line)))
        return Diagnosis(kind='budget', summary='stopped before a paid request that the cap could not cover; nothing '
                         'beyond the cap was sent, and what was done is kept',
                         actions=[Action(label='raise the cap (recorded), then run again', target=c, kind='command')
                                  for c in commands] or again,
                         evidence=[line for line in lines if 'cap' in line.lower()][-3:])
    resumable = job.kind == 'track1' and (folder / '.track1-checkpoint' / 'manifest.json').exists()
    resume = [Action(label='resume from the completed checkpoints', kind='resume')] if resumable else again
    if job.status == 'cancelled':
        return Diagnosis(kind='interrupted', summary='cancelled', actions=resume)
    hits = [line for line in lines if DEPENDENCY.search(line)]
    if hits:
        name = _tool(lines)
        command = f'uv run adroit setup --only "{name}" --fetch' if name else 'uv run adroit setup'
        return Diagnosis(kind='dependency', summary='a data set, tool or backend is missing on this machine',
                         actions=[Action(label='check and fetch it', target=command, kind='command')], evidence=hits[-3:])
    if job.returncode is None:
        return Diagnosis(kind='interrupted', summary='the process ended without a word (the machine slept, or it was '
                         'stopped)', actions=resume)
    if job.returncode == 2:
        message = [line for line in lines if re.search(r'Invalid value|Error|stopped:|BadParameter', line)]
        actions = list(again)
        if (folder / 'result.json').exists():
            actions.append(Action(label='review the inputs in a reanalysis', target='reanalyse', kind='page'))
        return Diagnosis(kind='input', summary='an input was refused: correct it and run again', actions=actions,
                         evidence=message[-3:] or lines[-3:])
    return Diagnosis(kind='failed', summary='failed; the log shows why', actions=resume,
                     evidence=[line for line in lines if line.strip()][-5:])


def _left_running(job) -> str:
    """``engine.left_running``: "" for a job record that names no calculation."""
    from adroit.ui import engine
    return engine.left_running(job) if getattr(job, 'calculation', 0) else ''


def recent(job, now: datetime | None = None) -> bool:
    """Whether a job finished in the last week (older failures are listed apart, not counted as needing attention)."""
    try:
        finished = datetime.fromisoformat(job.finished or job.started)
    except ValueError:
        return False
    return (now or datetime.now()) - finished <= RECENT


def _read(root: Path) -> tuple[list, dict[str, str]]:
    """(every readable job under ``root`` as it is now; each item that needs attention, by a name of its own, with a
    mark that changes when it does): recent jobs that did not complete (their status, when they ended and their
    attempt), and run records that cannot be read (why), listed or damaged since (CA-07, NP17-03)."""
    from adroit.ui import engine
    listed, damaged = engine.listing(root) if Path(root).is_dir() else ([], [])
    jobs, lost = engine.polled(listed)                   # NP17-03: one damaged since listed is counted, not raised
    items = {f'record:{u.path}': u.why for u in [*damaged, *lost]}
    items.update({f'job:{j.folder}': f'{j.status}|{j.finished or j.started}|{j.attempt}' for j in jobs
                  if j.status in ('failed', 'budget_stopped', 'cancelled') and recent(j)})
    return jobs, items


def attention(root: Path) -> dict[str, str]:
    """Each item under ``root`` that needs attention now, by its name, with its mark (``_read``)."""
    return _read(root)[1]


def seen(root: Path) -> dict[str, str]:
    """What the Activity page last showed as needing attention (``mark_seen``): each item's name and mark. Nothing where
    the record is missing, cannot be read or is not such a record, so that every item is then counted."""
    try:
        held = json.loads((Path(root) / SEEN).read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(held, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in held.items()):
        return {}
    return held


def mark_seen(root: Path) -> None:
    """Record every item that needs attention now as seen (the Activity page, as it opens), published whole
    (``durable.write_atomic``). Where the runs folder is absent or cannot be written nothing is recorded: the menu
    then goes on counting, and the page is shown all the same."""
    from adroit.core.durable import write_atomic
    if not Path(root).is_dir():
        return
    try:
        write_atomic(Path(root) / SEEN, json.dumps(attention(root), indent=1, sort_keys=True))
    except OSError:
        return


def summary(root: Path) -> dict[str, int]:
    """The menu's counts: jobs running, and those that need attention and have not been seen as they are now on the
    Activity page (module docstring): recent jobs that did not complete, and run records that cannot be read
    (Activity names them; the consistency audit's CA-07)."""
    jobs, items = _read(root)
    shown = seen(root)
    return {'running': sum(j.status == 'running' for j in jobs),
            'attention': sum(shown.get(name) != mark for name, mark in items.items())}

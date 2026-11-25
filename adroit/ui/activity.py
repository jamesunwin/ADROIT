"""The activity page: running jobs, jobs that need attention with their diagnosis and recovery action, and the
recently finished (``orchestrator.recovery``; the owner's workbench plan of 2026-10-18, part 2 §F). The full log stays
one click away on each job's live view."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from nicegui import ui

COLOUR = {'running': 'blue', 'completed': 'green', 'budget': 'orange', 'dependency': 'red', 'input': 'red',
          'interrupted': 'grey', 'failed': 'red'}
WORD = {'running': 'running', 'completed': 'completed', 'budget': 'budget stopped', 'dependency': 'missing dependency',
        'input': 'invalid input', 'interrupted': 'interrupted', 'failed': 'failed'}


def _card(root: Path, job, diagnosis) -> None:
    """One job: its state, what it made (``outcomes``: a completed model intake is a draft to review, not a study),
    the evidence, the recovery actions and the page that opens its output."""
    from adroit.ui import engine, outcomes
    from adroit.ui.pages import rel
    folder = Path(job.folder)
    path = rel(root, folder)
    result = outcomes.outcome(root, folder, job)
    with ui.card().classes('w-full').mark(f'job_{diagnosis.kind}'):
        with ui.row().classes('items-center gap-2'):
            ui.badge(WORD[diagnosis.kind], color=COLOUR[diagnosis.kind])
            ui.label(job.title).classes('font-medium')
            ui.label(job.finished or job.started).classes('text-xs text-gray-500')
        ui.label(result.headline if diagnosis.kind == 'completed' else diagnosis.summary).classes('text-sm')
        if diagnosis.log_unreadable:                # always named, apart from what the command said (DP-03)
            ui.label(f'{diagnosis.log_unreadable[:1].upper()}{diagnosis.log_unreadable[1:]}: this card is read from '
                     "the run's record alone.").classes('text-xs text-orange-700').mark('unreadable_log')
        for line in diagnosis.evidence:
            ui.label(line[:200]).classes('text-xs font-mono text-gray-600')
        with ui.row().classes('items-center gap-3'):
            for action in diagnosis.actions:
                if action.kind == 'cancel':
                    def cancel(folder=folder) -> None:
                        engine.cancel(folder)
                        ui.notify('cancelling its calculation')
                    ui.button(action.label, on_click=cancel).props('outline dense color=negative').mark('cancel_left')
                elif action.kind == 'resume':
                    def resume(folder=folder) -> None:
                        try:
                            engine.resume(folder)
                            ui.notify('resuming from the completed checkpoints')
                        except ValueError as error:
                            ui.notify(str(error))
                    ui.button(action.label, on_click=resume).props('outline dense').mark('resume')
                elif action.kind == 'command':
                    ui.label(f'{action.label}: {action.target}').classes('text-xs font-mono')
                elif action.target == 'study':
                    ui.link(action.label, '/study?' + urlencode({'path': path}))
                elif action.target == 'reanalyse':
                    ui.link(action.label, '/reanalyse?' + urlencode({'source': str(folder / 'result.json')}))
                else:
                    ui.link(action.label, action.target)
            if diagnosis.kind not in ('running', 'completed') and not (folder / 'study.json').exists():
                from adroit.ui.deletion import confirm_run
                ui.button('Delete this run', on_click=lambda folder=folder: confirm_run(
                    root, folder, lambda: ui.navigate.to('/activity'))).props('outline dense color=negative') \
                    .mark('delete_run')
            if result.primary and result.output != 'study' and diagnosis.kind != 'running':
                ui.link(result.primary.label, result.primary.target).mark('outcome_action')
            ui.link('the full log', '/live?' + urlencode({'path': path})).classes('text-sm')
        if diagnosis.kind in ('failed', 'interrupted') and not any(a.kind in ('resume', 'cancel')
                                                                   for a in diagnosis.actions):
            ui.label('It cannot be continued from here: the workbench resumes only a Constrain-a-model run that kept '
                     'a checkpoint. Start it over, or delete it.').classes('text-xs text-gray-500') \
                .mark('not_resumable')


def page(root: Path) -> None:
    """Every job of this workbench: running, needing attention (the last week), finished, and earlier failures."""
    from adroit.orchestrator.recovery import diagnose, mark_seen, recent
    from adroit.ui import engine
    from adroit.ui.pages import header
    mark_seen(root)                 # before the menu is drawn: its "need attention" is cleared by opening this page
    header('Activity', 'Every run started from this workbench: what is running, what needs your attention and why, '
           'with the action that recovers it, and what finished. Runs continue when you leave the page.')
    listed, damaged = engine.listing(root)
    now, lost = engine.polled(listed)                    # one damaged since it was listed: named too (NP17-03)
    jobs = sorted(now, key=lambda j: j.started, reverse=True)
    from adroit.ui.pages import _damaged
    _damaged(root, 'run record(s)', damaged + lost, 'unreadable_runs')      # CA-07: named; the rest are listed
    groups: dict[str, list] = {'Running': [], 'Needs attention': [], 'Finished': [], 'Earlier': []}
    for job in jobs:
        lines, unreadable = engine.read_log(Path(job.folder))
        diagnosis = diagnose(job, lines, Path(job.folder), unreadable)
        group = ('Running' if diagnosis.kind == 'running' else 'Finished' if diagnosis.kind == 'completed'
                 else 'Needs attention' if recent(job) else 'Earlier')
        groups[group].append((job, diagnosis))
    if not jobs:
        ui.label('No runs yet.').classes('text-gray-500')
    for title, members in groups.items():
        if members:
            ui.label(f'{title} ({len(members)})').classes('text-lg font-medium mt-2')
            for job, diagnosis in members[:50]:
                _card(root, job, diagnosis)

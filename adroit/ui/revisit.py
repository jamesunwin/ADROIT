"""Studies to revisit after an update (``orchestrator.revisit``; the owner's workbench plan of 2026-10-18, part 2 §H):
what changed in each input, and the existing reanalysis that picks it up. Nothing reruns."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from nicegui import ui

WORD = {'model': 'model revision', 'record': 'constraint record', 'profile': 'profile', 'private limit': 'private limit'}


def update_card(root: Path, update) -> None:
    """One changed input: what it was, what it is now, what changed, and the reanalysis, which requires the version the
    update was read from: its result's digest (the auditor's CX recheck, CY-03) and its evidence's identity (the auditor's DB/VI
    recheck, DC-04, 2026-11-03), as the update names them."""
    from adroit.orchestrator.revisit import CAVEAT
    folder = Path(root) / update.study
    with ui.card().classes('w-full').mark('update'):
        with ui.row().classes('items-center gap-2'):
            ui.badge(WORD[update.kind], color='teal')
            ui.link(update.title, '/study?' + urlencode({'path': update.study}))
        ui.label(f'used: {update.old}').classes('text-xs font-mono')
        ui.label(f'now: {update.new}').classes('text-xs font-mono')
        for line in update.changes:
            ui.label('• ' + line).classes('text-sm')
        ui.label(CAVEAT).classes('text-xs text-gray-600')
        with ui.row().classes('items-center gap-3'):
            version = {'sha256': update.sha256, **({'evidence': update.evidence} if update.evidence else {})} \
                if update.sha256 else {}
            ui.link('Prepare reanalysis with this update',
                    '/reanalyse?' + urlencode({'source': str(folder / 'result.json'), **version})
                    ).mark('prepare_reanalysis')
            if update.hint:
                ui.label(f'({update.hint})').classes('text-xs text-gray-600')


def page(root: Path) -> None:
    """Every study whose inputs have changed since it ran."""
    from adroit.orchestrator.revisit import updates
    from adroit.ui.pages import header
    header('Studies to revisit', 'Studies whose model, constraint records, profile or private limits have changed since '
           'they ran, with what changed. Results stay historical: nothing reruns until you prepare a reanalysis.')
    found = updates(root)
    from adroit.ui.wizards import _unoffered
    _unoffered(root)
    if not found:
        ui.label('No study used an input that has changed since.').classes('text-gray-500')
    for update in found:
        update_card(root, update)


def study_updates(root: Path, version) -> None:
    """On a study page: its own changed inputs, if any, of the page's version (``version``): its request, its evidence
    and its record (``revisit.for_study``), whose identities each card's reanalysis requires (DC-04)."""
    from adroit.orchestrator.revisit import for_study
    try:
        found = for_study(root, version)
    except (OSError, ValueError):
        return
    if found:
        with ui.expansion(f'Inputs updated since this study ran ({len(found)})', value=True).classes('w-full') \
                .mark('study_updates'):
            for update in found:
                update_card(root, update)

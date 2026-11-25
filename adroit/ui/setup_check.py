"""The setup check above Run (``orchestrator.setup_check``; the owner's workbench plan of 2026-10-18, §B): what the
analysis will use, what is missing (with the fix), what may stay pending, its size, a labelled estimate and its cost.
$0: nothing is calculated, asked or fetched."""
from __future__ import annotations

from nicegui import ui

SECTIONS = (('missing', 'Missing (fix before running)'), ('pending', 'May stay pending'), ('uses', 'This analysis will use'),
            ('size', 'Size'))
COLOUR = {'blocking': 'text-red-700', 'pending': 'text-amber-800', 'info': 'text-gray-700'}


def render(check) -> None:
    """The check as a card; a blocking item is red, with its fix (a page link or an exact command)."""
    with ui.card().classes('w-full').mark('setup_check'):
        ui.label('Setup check: blocked' if check.blocked else 'Setup check: ready').classes(
            'text-lg font-bold ' + ('text-red-700' if check.blocked else 'text-green-700'))
        for key, title in SECTIONS:
            items = [i for i in check.items if i.section == key]
            if not items:
                continue
            ui.label(title).classes('font-medium mt-1')
            for item in items:
                with ui.row().classes('items-baseline gap-2 no-wrap'):
                    ui.label('• ' + item.message).classes('text-sm ' + COLOUR[item.severity])
                    if item.fix_kind == 'page' and item.fix.startswith('/'):
                        ui.link('fix', item.fix).classes('text-sm')
                    elif item.fix:
                        ui.label(item.fix).classes('text-xs font-mono text-gray-600')
        ui.label(f'Duration: {check.estimate_basis}').classes('text-sm text-gray-600')
        ui.label(f'Cost: {check.cost}').classes('text-sm text-gray-600')


def masses(text: str) -> list[float]:
    """low:high:n (logarithmic), or comma-separated masses, as the command line reads them."""
    import numpy as np
    if ':' in text:
        low, high, n = text.split(':')
        return np.geomspace(float(low), float(high), int(n)).tolist()
    return [float(m) for m in text.split(',') if m.strip()]

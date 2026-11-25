"""The scan editor: one row per parameter instead of axis strings (the owner's workbench plan, 2026-10-18, §C).

Rows come from ``parameter_space.scan_table`` (the engine's own mapping): only the engine's active, non-derived
coordinates can be scanned; fixed values come from the model; derived parameters show their relation; parameters the
engine does not use are greyed with the reason. Each edit hands the new axes to ``on_change`` (which clears the scan
review); the axis strings and YAML stay available as the advanced view.
"""
from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from adroit.parameter_space.scan_table import ParameterRow, axes, scannable, table

ROLES = {'x': 'scanned (x)', 'y': 'scanned (y)', 'fixed': 'fixed'}


def scan_editor(setup, on_change: Callable[[object, object, float | None], None],
                on_invalid: Callable[[str], None] | None = None) -> list[ParameterRow]:
    """The editable table of a scan setup; returns its live rows. ``on_change(x, y, mediator_ratio)`` receives
    validated axes after each edit; an invalid edit shows its reason on the table and is passed to ``on_invalid``, so
    the caller withdraws the review and refuses to launch until the table is valid again (S18-08)."""
    rows = table(setup)
    free = scannable(rows)
    message = ui.label('').classes('text-sm text-red-700')

    def changed() -> None:
        try:
            x, y, ratio = axes(rows)
        except ValueError as error:
            message.text = str(error)
            if on_invalid is not None:
                on_invalid(str(error))
            return
        message.text = ''
        on_change(x, y, ratio)

    def update(i: int, **values) -> None:
        role = values.get('role')
        if role in ('x', 'y'):                      # the row that held this role becomes fixed
            for j, other in enumerate(rows):
                if j != i and other.role == role:
                    rows[j] = other.model_copy(update={'role': 'fixed'})
            if rows[i].low is None:
                start = abs(rows[i].value or 1.0) or 1.0
                values.update(low=start / 10, high=start * 10, spacing='log', points=12)
        rows[i] = rows[i].model_copy(update=values)
        if role is not None:                        # a new role changes the row's inputs; a typed value does not
            grid.refresh()
        changed()

    @ui.refreshable
    def grid() -> None:
        with ui.grid(columns=7).classes('w-full items-center gap-2').mark('scan_table'):
            for head in ('parameter', 'units', 'role', 'value or low', 'high', 'spacing', 'points'):
                ui.label(head).classes('text-xs text-gray-600 font-medium')
            for i, r in enumerate(rows):
                _cells(i, r, free, update)
    grid()
    return rows


def _cells(i: int, r: ParameterRow, free: list[str], update: Callable[..., None]) -> None:
    """One row of the table: its name and units, its role, then its range if scanned or its fixed value."""
    ui.label(f'{r.label} ({r.parameter})' if r.label != r.parameter else r.parameter)
    ui.label(r.units or '—').classes('text-gray-600')
    if r.parameter in free:
        ui.select(ROLES, value=r.role, on_change=lambda e, i=i: update(i, role=e.value)) \
            .props('dense').mark(f'role_{r.parameter}')
    else:
        ui.label(r.relation or r.note or r.role).classes('text-gray-500 text-sm')
    if r.role in ('x', 'y'):
        ui.number(value=r.low, on_change=lambda e, i=i: update(i, low=e.value)).props('dense') \
            .mark(f'low_{r.parameter}')
        ui.number(value=r.high, on_change=lambda e, i=i: update(i, high=e.value)).props('dense') \
            .mark(f'high_{r.parameter}')
        ui.select({'log': 'log', 'lin': 'linear'}, value=r.spacing,
                  on_change=lambda e, i=i: update(i, spacing=e.value)).props('dense')
        ui.number(value=r.points, min=2, max=200, step=1,
                  on_change=lambda e, i=i: update(i, points=int(e.value or 2))).props('dense') \
            .mark(f'points_{r.parameter}')
    else:
        ui.label('—' if r.value is None else f'{r.value:.6g}').classes('text-gray-600')
        for _ in range(3):
            ui.label('')

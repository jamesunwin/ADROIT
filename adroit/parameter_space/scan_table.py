"""A scan setup as a table of parameters, and back (the owner's workbench plan, 2026-10-18; §C).

One row per ``Point`` slot: its label and units, its role (scanned on x or y, fixed, derived from a mass ratio or a
coupling relation, or inactive because the engine does not use it), its value or range, spacing and number of points.
The rows are made from ``scan_setup.preview`` and turned back into the axes that ``preview`` validates, so the table
and the run agree exactly; the review token (``setup_identity``) is unchanged by the round trip and changes with any
scientific edit.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from adroit.core.state import StrictModel
from adroit.parameter_space.scan_setup import SLOTS, ScanSetup

UNITS = {'m_chi': 'GeV', 'm_med': 'GeV', 'g_chi': '', 'g_q': '', 'g_l': ''}
Role = Literal['x', 'y', 'fixed', 'derived', 'inactive']


class ParameterRow(StrictModel):
    """One parameter of the scan."""
    parameter: str
    label: str
    units: str
    role: Role
    value: float | None = None                  # a fixed parameter's value
    low: float | None = None                    # a scanned parameter's range
    high: float | None = None
    spacing: Literal['log', 'lin'] | None = None
    points: int | None = Field(default=None, ge=2, le=200)
    relation: str = ''                          # a derived parameter's formula
    note: str = ''                              # why a parameter is inactive, or the engine's label source


def table(setup: ScanSetup) -> list[ParameterRow]:
    """The rows of a scan setup, in slot order."""
    out = []
    for slot in SLOTS:
        label = setup.labels.get(slot, slot)
        if slot in (setup.x['parameter'], setup.y['parameter']):
            axis = setup.x if slot == setup.x['parameter'] else setup.y
            out.append(ParameterRow(parameter=slot, label=label, units=UNITS[slot],
                                    role='x' if axis is setup.x else 'y', low=axis['low'], high=axis['high'],
                                    spacing='log' if axis['log'] else 'lin', points=axis['n']))
        elif slot in setup.derived:
            out.append(ParameterRow(parameter=slot, label=label, units=UNITS[slot], role='derived',
                                    relation=f'{slot} = {setup.derived[slot]}'))
        elif slot in setup.inactive:
            out.append(ParameterRow(parameter=slot, label=label, units=UNITS[slot], role='inactive',
                                    value=setup.fixed.get(slot), note='this engine does not use it'))
        else:
            out.append(ParameterRow(parameter=slot, label=label, units=UNITS[slot], role='fixed',
                                    value=setup.fixed.get(slot), note='from the model'))
    return out


def axes(rows: list[ParameterRow]):
    """(x, y, mediator ratio) from edited rows; ValueError unless exactly one row is x and one is y, each with a
    range, spacing and number of points, and no derived or inactive row is scanned."""
    from adroit.parameter_space.scan import Axis
    found = {}
    for r in rows:
        if r.role in ('x', 'y') and r.relation:
            raise ValueError(f'{r.label} is derived ({r.relation}) and cannot be scanned; remove the relation first')
        if r.role in ('x', 'y') and r.note == 'this engine does not use it':
            raise ValueError(f'{r.label} is not used by this engine and cannot be scanned')
    for role in ('x', 'y'):
        chosen = [r for r in rows if r.role == role]
        if len(chosen) != 1:
            raise ValueError(f'choose exactly one parameter to scan on {role}')
        r = chosen[0]
        if None in (r.low, r.high, r.spacing, r.points):
            raise ValueError(f'{r.label}: give its range, spacing and number of points')
        found[role] = Axis(parameter=r.parameter, low=r.low, high=r.high, log=r.spacing == 'log', n=r.points)
    ratio = next((r.relation for r in rows if r.parameter == 'm_med' and r.relation.endswith('* m_chi')), '')
    mediator_ratio = float(ratio.split('=')[1].split('*')[0]) if ratio else None
    return found['x'], found['y'], mediator_ratio


def scannable(rows: list[ParameterRow]) -> list[str]:
    """The parameters that may be scanned: the engine's active coordinates that are not derived (a fixed value comes
    from the model and is changed by editing the model, not here)."""
    return [r.parameter for r in rows if r.role in ('x', 'y', 'fixed') and r.note != 'this engine does not use it']


def setup_of(spec, x=None, y=None, mediator_ratio: float | None = None, n: int = 24) -> ScanSetup:
    """The scan setup of a typed model with optional axes, as execution builds it (the engine's mapping, the
    model's coupling relations and the validated axes)."""
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.scan_setup import model_relations, preview
    cls, point, notes = classify(spec)
    return preview(cls, point, x, y, mediator_ratio, notes=notes, n=n,
                   coupling_relations=model_relations(spec, '', x, y))

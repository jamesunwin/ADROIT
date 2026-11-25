"""The workbench's point table and point explanation (``evidence.points``; the owner's plan of 2026-10-18, §A).

Read-only: the saved result and its evidence only; nothing is calculated, asked or fetched.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from nicegui import ui

KINDS = ('track1', 'single_idea', 'signal')
CENTRAL = 'excluded at the central SHM'     # ``evidence.points.CENTRAL``: a point only the region's centre excludes
GROUPS = (('excluded', 'Excluded here', 'red'), ('pending', 'Pending here', 'orange'), ('allowed', 'Allowed here', 'green'))


def _number(value) -> str:
    return '—' if value is None else f'{value:.4g}'


def _where(coordinates: dict) -> str:
    from adroit.evidence.points import UNITS
    return ', '.join(f"{k} = {v:.4g}{' ' + UNITS[k] if UNITS.get(k) else ''}" for k, v in coordinates.items())


def points_panel(root: Path, version) -> None:
    """On a study page: every point of the study, searchable and filterable by status; each opens its explanation.
    Of the page's version of the study (``version``: the badge and the points of the same bytes, the auditor's CV recheck,
    CW-01, 2026-10-30). Each link, from the table and from the chart, names the version it was chosen from, its result
    and its evidence, which the explanation requires (``point_link``; the auditor's version-identity audit, VI-02,
    2026-11-03: a point chosen on A had opened B's point of that name)."""
    from adroit.evidence.points import points
    from adroit.evidence.version import Token
    try:
        held = version.saved()
        found = points(held.workflow, held.result)
    except (ValueError, OSError) as error:
        ui.label(f'Points unavailable: {error}').classes('text-gray-600')
        return
    if not found:
        return
    workflow, result = held.workflow, held.result
    token = version.token()
    chosen = Token(token.path, result=token.result, evidence=token.evidence).query(root)   # what a point's page shows
    rows = [{'point': p.point_id, 'kind': p.kind, 'where': _where(p.coordinates), 'omega': _number(p.omega_h2),
             'status': p.status, 'reason': p.reason[:160], 'halo': p.halo, 'open': point_link(chosen, p.point_id)}
            for p in found]
    columns = [{'name': 'point', 'label': 'point', 'field': 'point', 'sortable': True},
               {'name': 'kind', 'label': 'kind', 'field': 'kind', 'sortable': True},
               {'name': 'where', 'label': 'coordinates', 'field': 'where'},
               {'name': 'omega', 'label': 'Ωh²', 'field': 'omega'},
               {'name': 'status', 'label': 'status', 'field': 'status', 'sortable': True},
               {'name': 'reason', 'label': 'first exclusion or pending reason', 'field': 'reason'},
               {'name': 'halo', 'label': 'halo', 'field': 'halo'},
               {'name': 'open', 'label': '', 'field': 'open'}]
    with ui.expansion(f'Explain a point ({len(rows)} points)').classes('w-full'):
        ui.label('Every point of this study, from its saved result: open one to see what was calculated there and '
                 'what each constraint decided. Nothing is recalculated.').classes('text-sm text-gray-600')
        with ui.row().classes('items-center gap-3'):
            search = ui.input('search', placeholder='a point, a kind, a constraint…').classes('w-72')
            status = ui.select(['all', 'allowed', 'pending', 'excluded', CENTRAL], value='all',
                               label='status').classes('w-56')
        plane_chart(workflow, result, found, chosen)
        table = ui.table(columns=columns, rows=rows, row_key='point', pagination=25).classes('w-full').mark('points')
        table.add_slot('body-cell-open', '<q-td :props="props"><a :href="props.value">explain</a></q-td>')

        def refilter() -> None:
            text = (search.value or '').lower()
            table.rows = [r for r in rows if (status.value == 'all' or r['status'] == status.value)
                          and (not text or text in ' '.join(map(str, r.values())).lower())]
            table.update()
        search.on_value_change(lambda _: refilter())
        status.on_value_change(lambda _: refilter())


def point_link(chosen: dict, point: str) -> str:
    """The link that explains ``point`` of the version of a study it was chosen from (``chosen``: its token as a link's
    parameters, ``Token.query``, naming its result and its evidence: VI-02, VI-03)."""
    return '/study/point?' + urlencode({**chosen, 'point': point})


COLOURS = {'allowed': '#2e7d32', 'pending': '#ef6c00', 'excluded': '#c62828', CENTRAL: '#ad1457',
           'not evaluated': '#9e9e9e'}


def chart_options(workflow: str, result, rows) -> dict | None:
    """An interactive parameter plane: every point of the study's scan at its two scanned coordinates, one series per
    status, each item named by its point (clicking opens its explanation); thermal roots drawn larger. None without
    a scan."""
    track1 = result if workflow == 'track1' else getattr(result, 'track1', None)
    scan = getattr(track1, 'scan', None)
    if scan is None:
        return None
    x, y = scan.request.x, scan.request.y
    prefix = '' if workflow == 'track1' else 'plane-'
    series = []
    for status, colour in COLOURS.items():
        for roots in (False, True):
            data = [{'value': [r.coordinates.get(x.parameter), r.coordinates.get(y.parameter)], 'name': r.point_id}
                    for r in rows if r.status == status and r.point_id.startswith(prefix)
                    and r.point_id.removeprefix(prefix).startswith(('contour:', 'likelihood:', 'table-root:',
                                                                    'likelihood-table-root:')) == roots
                    and None not in (r.coordinates.get(x.parameter), r.coordinates.get(y.parameter))]
            if data:
                series.append({'type': 'scatter', 'name': f"{status}{' (thermal roots)' if roots else ''}",
                               'data': data, 'symbolSize': 14 if roots else 7, 'itemStyle': {'color': colour},
                               'symbol': 'diamond' if roots else 'circle'})
    def axis(a) -> dict:
        # a logarithmic axis needs positive values: a negative or mixed-sign scan (the engine allows all-negative log
        # branches) is drawn on a linear axis, named as such (the stacked audit's nonblocking note)
        log = a.log and a.low > 0 and a.high > 0
        return {'type': 'log' if log else 'value', 'name': a.parameter + (' (linear axis)' if a.log and not log else ''),
                'nameLocation': 'middle', 'nameGap': 28, 'min': a.low, 'max': a.high}
    return {'tooltip': {'trigger': 'item'}, 'legend': {'top': 0}, 'xAxis': axis(x), 'yAxis': axis(y), 'series': series}


def plane_chart(workflow: str, result, rows, chosen: dict) -> None:
    """The interactive plane on the study page; a click opens the point's explanation, of the version the chart drew
    (``chosen``: its token as a link's parameters: VI-02)."""
    options = chart_options(workflow, result, rows)
    if options is None or not options['series']:
        return

    def opened(event) -> None:
        name = getattr(event, 'name', '') or (event.data or {}).get('name', '')
        if name:
            ui.navigate.to(point_link(chosen, name))
    ui.label('Click a point to explain it (the saved figure in the report is the reference).') \
        .classes('text-sm text-gray-600')
    ui.echart(options, on_point_click=opened).classes('w-full h-96').mark('plane_chart')


def point_page(root: Path, query: dict, point: str) -> None:
    """One point of a saved study, explained, of the version its link names (``query``: the link's parameters, its
    token, ``Token.from_query``: its result and its evidence; another version is refused, VI-02 and VI-03); a link
    naming none (an old one) explains the point of the version saved now."""
    from adroit.evidence.points import explain
    from adroit.evidence.version import Token
    from adroit.ui.pages import header
    path = str(query.get('path', ''))
    try:
        found = explain(Token.from_query(root, query), point)
    except (ValueError, OSError) as error:
        header('Point unavailable', str(error))
        return
    row = found.row
    header(f'{row.kind}: {row.point_id}', f'Status here: {row.status}. From {found.origin}; nothing is recalculated.')
    ui.link('back to the study (as saved now)', '/study?' + urlencode({'path': path}))
    ui.label(_where(row.coordinates)).classes('font-mono')
    if found.certification:
        ui.label(f'Certification: {found.certification}').classes(
            'text-sm' + ('' if found.certification.startswith('certified') else ' text-amber-800')) \
            .mark('point_certification')
    for line in found.context:
        ui.label(line).classes('text-sm')
    if found.calculated:
        ui.label('Calculated here').classes('text-lg font-medium mt-2')
        for c in found.calculated:
            value = _number(c['value']) + (f" {c['units']}" if c['units'] not in ('', 'dimensionless') else '')
            ui.label(f"{c['observable']}: {value} ({c['calculation']})").classes('text-sm')
    for line in found.missing:
        ui.label('missing: ' + line).classes('text-sm text-amber-800')
    if found.fog:
        where = 'beneath' if found.fog['beneath'] else 'above'
        ui.label(f"Neutrino fog: σ_SI {found.fog['prediction_cm2']:.3g} cm² lies {where} xenon's floor "
                 f"{found.fog['floor_cm2']:.3g} cm² at this mass ({found.fog['source']}; an annotation, not a "
                 'constraint)').classes('text-sm').mark('neutrino_fog')
    for group, title, colour in GROUPS:
        items = [c for c in found.comparisons if c.group == group]
        with ui.expansion(f'{title} ({len(items)})', value=group != 'allowed').classes('w-full').mark(group):
            for c in items:
                with ui.card().classes('w-full'):
                    ui.label(c.constraint).classes(f'font-medium text-{colour}-800')
                    facts = [f'prediction {_number(c.prediction)}', f'limit {_number(c.limit)}',
                             f'ratio {_number(c.ratio)}' + (f' ({c.units})' if c.units else '')]
                    if c.native_confidence_level:
                        facts.append(f'native CL {c.native_confidence_level:g}')
                    if c.required_confidence_level:
                        facts.append(f'required CL {c.required_confidence_level:g}')
                    ui.label('; '.join(facts)).classes('text-sm')
                    if c.construction:
                        ui.label(c.construction).classes('text-xs text-gray-600')
                    if c.sources:
                        ui.label('source: ' + ', '.join(c.sources) + (f' ({c.review})' if c.review else '')) \
                            .classes('text-xs')
                    for reason in c.reasons:
                        ui.label('why pending: ' + reason).classes('text-sm text-amber-800')
                    for link in c.links:
                        if link.kind == 'page':
                            ui.link(link.label, link.target)
                        else:
                            ui.label(f'{link.label}: {link.target}').classes('text-xs font-mono')

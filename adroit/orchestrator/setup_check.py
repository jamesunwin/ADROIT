"""One setup check before a run: what it will use, what is missing, what may stay pending, its size, its likely
duration and its cost (the owner's workbench plan, 2026-10-18; the workbench inspection plan of 2026-10-18 §B).

It composes the existing checks only (``library.personal.support``, ``parameter_space.route_report``,
``parameter_space.scan_setup``, the profile and private-limit loaders, the records' verification states and
``external.setup``) and never evaluates physics, asks a language model or fetches anything. Each item says how to fix
it; a blocking item stops the run.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from adroit.core.state import StrictModel

Severity = Literal['blocking', 'pending', 'info']
# What an analysis needs from the machine, by what its route uses (``external/tools.yaml`` names). Anything an
# analysis may need that is not here is reported as not checked, never as present.
REQUIREMENTS = {
    'direct detection': ['CRESST-III data release (arXiv:1905.07335)', 'CDMSlite Run 2 data release (arXiv:1707.01632)',
                         'Optimum interval code (Yellin)'],
    'solar capture': ['B16 standard solar model (AGSS09)'],
    'LHC searches (SModelS)': ['SModelS', 'LHC SUSY cross sections'],
    'generic LHC production': ['MadGraph5_aMC@NLO'],
    'dark photon searches': ['DarkCast'],
    'LZ extended window': ['LZ extended window (arXiv:2609.02823)'],
}


class Item(StrictModel):
    """One line of the check."""
    section: Literal['uses', 'missing', 'pending', 'size', 'cost']
    severity: Severity = 'info'
    message: str
    fix: str = ''                       # a workbench page or an exact command
    fix_kind: Literal['', 'page', 'command'] = ''


class SetupCheck(StrictModel):
    """The whole check, with its points, fits and toys and the estimate's basis."""
    items: list[Item] = Field(default_factory=list)
    points: int = 0
    fits: int = 0
    toys: int = 0
    estimate_s: float | None = None
    estimate_basis: str = 'duration unknown: no comparable earlier run'
    cost: str = '$0 (no paid step)'
    review_token: str = ''

    @property
    def blocked(self) -> bool:
        """Whether a blocking item stops the run."""
        return any(i.severity == 'blocking' for i in self.items)


def _model_items(spec) -> list[Item]:
    from adroit.library.personal import support
    from adroit.parameter_space.route_report import report
    out = []
    ready = support(spec)
    for missing in ready['missing_parameters']:
        out.append(Item(section='missing', severity='blocking', message=f'{missing} has no value',
                        fix='give it a value in the model (Refine as a new revision, or the YAML)', fix_kind='page'))
    if not ready['structural_valid']:
        out += [Item(section='missing', severity='blocking', message='structural audit: ' + p.get('message', str(p)),
                     fix='correct the model') for p in ready['problems']]
    route = report(spec)
    out.append(Item(section='uses', message=f'engine: {route.engine or route.route}' + (f' ({route.why})' if route.why else '')))
    if route.route == 'none':
        out.append(Item(section='missing', severity='blocking', message='no engine computes this model: ' + route.why))
    out += [Item(section='uses', message='includes: ' + x) for x in route.included]
    out += [Item(section='pending', severity='pending', message='not computed for this model: ' + x) for x in route.missing]
    return out


def _scan_items(spec, x: str, y: str, ratio: float, reviewed: str) -> tuple[list[Item], int, str]:
    from adroit.ui.forms import review_scan
    try:
        _, setup, token = review_scan(spec if isinstance(spec, str) else _yaml(spec), x, y, ratio)
    except (ValueError, KeyError, TypeError) as error:
        return [Item(section='missing', severity='blocking', message=f'scan setup: {error}',
                     fix='choose two active coordinates with valid ranges')], 0, ''
    out = [Item(section='uses', message=f"scanned: {setup.x['parameter']} {setup.x['low']:g}–{setup.x['high']:g} "
                                        f"({setup.x['n']} points), {setup.y['parameter']} {setup.y['low']:g}–"
                                        f"{setup.y['high']:g} ({setup.y['n']} points)")]
    out += [Item(section='uses', message=f'fixed: {k} = {v:g}') for k, v in setup.fixed.items()]
    out += [Item(section='uses', message=f'derived: {k} = {v}') for k, v in setup.derived.items()]
    if reviewed != token:
        out.append(Item(section='missing', severity='blocking', message='the scan setup is not the one shown as '
                        'it now stands', fix='press Scan again: it runs the setup shown', fix_kind='page'))
    return out, setup.x['n'] * setup.y['n'], token


def _yaml(spec) -> str:
    import yaml
    return yaml.safe_dump(spec.model_dump(mode='json'), sort_keys=False)


def _selection_items(private_limits: list[str], profile: str) -> list[Item]:
    out = []
    from adroit.constraints.experimental_review import load_bound
    for ref in private_limits:
        try:
            item = load_bound(ref)
            out.append(Item(section='uses', message=f'private limit: {item.name} ({ref[:26]}…)'))
        except (ValueError, OSError) as error:
            out.append(Item(section='missing', severity='blocking', message=f'{ref[:26]}…: {error}',
                            fix='/records', fix_kind='page'))
    if profile:
        from adroit.library.experimental_profiles import load
        try:
            p = load(profile)
            out.append(Item(section='uses', message=f'profile: {p.name} ({len(p.limits)} limits, '
                                                    f'{len(p.null_modules)} nulls)'))
        except (ValueError, OSError) as error:
            out.append(Item(section='missing', severity='blocking', message=f'profile {profile[:20]}…: {error}',
                            fix='/experiments/profiles', fix_kind='page'))
    return out


def _record_items(unverified: bool) -> list[Item]:
    """Records awaiting a person's verification: unused (pending) unless the run accepts unverified records."""
    from adroit.constraints.database import records
    waiting = [r for r in records() if not r.usable]
    if not waiting or unverified:
        return [Item(section='uses', message=f'{len(waiting)} unverified records accepted (--unverified)')] if waiting else []
    return [Item(section='pending', severity='pending', message=f'record {r.id} awaits verification; where it applies '
                 'the comparison stays pending', fix=f'/record?id={r.id}', fix_kind='page') for r in waiting]


def machine_items(needs: list[str], tools_dir: Path | None = None) -> list[Item]:
    """The external items these needs require, present or not (``external.setup``), and each need this table does
    not know, as not checked."""
    from adroit.external import setup
    out = []
    for need in needs:
        names = REQUIREMENTS.get(need)
        if names is None:
            out.append(Item(section='pending', severity='info', message=f'{need}: its machine requirements are not '
                            'checked here'))
            continue
        for name in names:
            status = setup.run(only=name, tools_dir=tools_dir)[0]
            if status.present:
                out.append(Item(section='uses', message=f'{name} (present on this machine; {need})'))
            else:
                out.append(Item(section='missing', severity='blocking' if status.required else 'pending',
                                message=f'{name} is not on this machine ({need})',
                                fix=f'uv run adroit setup --only "{name}" --fetch', fix_kind='command'))
    return out


def needs(spec_route, kind: str, experiment: str = '') -> list[str]:
    """What an analysis's route uses from the machine, in ``REQUIREMENTS``'s terms."""
    found = ['direct detection'] if kind in ('track1', 'single_idea') else []
    text = ' '.join([spec_route.engine, *spec_route.included]).lower()
    if 'solar' in text or kind in ('track1', 'single_idea'):
        found.append('solar capture')
    if 'lhc' in text:
        found.append('LHC searches (SModelS)' if spec_route.route == 'library' else 'generic LHC production')
    if 'dark photon' in text:
        found.append('dark photon searches')
    if 'LZ extended window' in experiment:
        found.append('LZ extended window')
    return list(dict.fromkeys(found))


def estimate(kind: str, engine: str, points: int, root: Path) -> tuple[float | None, str]:
    """A runtime estimate from earlier comparable studies (the same kind, and a scan of the same engine class: their
    recorded seconds per grid point), stating its basis; None without one. A study's duration is its record's, and its
    grid the result's, of one version (``evidence.version``: the record and the result read together); a record naming
    another version of the result than the one read is left out (the auditor's version-identity audit, VI-01, 2026-11-03:
    A's duration over B's grid had given a rate neither run had)."""
    from datetime import datetime
    from adroit.evidence.version import resolve
    from adroit.orchestrator.studies import tree
    rates = []
    for _, listed in tree(root):
        if listed.kind != kind or not (Path(listed.folder) / 'result.json').exists():
            continue
        try:
            found = resolve(Path(listed.folder), evidence=False)
            study = found.study()
            if found.record_state not in ('bound', 'unbound') or study is None or study.kind != kind \
                    or not study.calculation_completed_at or not study.calculation_started_at:
                continue
            data = found.data()
            took = (datetime.fromisoformat(study.calculation_completed_at)
                    - datetime.fromisoformat(study.calculation_started_at)).total_seconds()
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        scan = data.get('scan') or (data.get('track1') or {}).get('scan') or {}
        n = len(scan.get('points', []))
        if n and took > 0 and engine and data.get('class_name', (data.get('track1') or {}).get('class_name')) == engine:
            rates.append(took / n)
    if not rates or not points:
        return None, 'duration unknown: no comparable earlier run'
    rates.sort()
    rate = rates[len(rates) // 2]
    from adroit.ui.style import seconds_text
    return rate * points, (f'about {seconds_text(rate * points)}: the median rate of {len(rates)} earlier {kind} '
                           'run(s) of this engine, per grid point (an estimate, not a promise)')


def check_track1(spec, x: str = '', y: str = '', ratio: float = 0.0, reviewed: str = '', private_limits=(),
                 profile: str = '', unverified: bool = False, root: Path | None = None,
                 tools_dir: Path | None = None) -> SetupCheck:
    """The setup check of a Track 1 run of a typed model."""
    from adroit.parameter_space.route_report import report
    items = _model_items(spec)
    scan, points, token = _scan_items(spec, x, y, ratio, reviewed)
    items += scan + _selection_items(list(private_limits), profile) + _record_items(unverified)
    route = report(spec)
    items += machine_items(needs(route, 'track1'), tools_dir)
    seconds, basis = estimate('track1', _class_name(spec), points, root) if root else (None, 'duration unknown')
    items.append(Item(section='size', message=f'{points} grid points, then the thermal roots on the contour'))
    return SetupCheck(items=items, points=points, estimate_s=seconds, estimate_basis=basis, review_token=token)


def _class_name(spec) -> str:
    """The engine class's name, as a Track 1 result records it (``Track1Result.class_name``)."""
    from adroit.parameter_space.classify import Unsupported, classify
    try:
        return classify(spec)[0].name
    except (Unsupported, ValueError):
        return ''


def check_single(spec, experiment: str, masses: list[float], toys: int, grid: int, unverified: bool = False,
                 root: Path | None = None, tools_dir: Path | None = None) -> SetupCheck:
    """The setup check of an Explain-a-signal study: the model, the anomaly's search, the fits, the toys and its
    Track 1 plane."""
    from adroit.parameter_space.route_report import report
    items = _model_items(spec) + _record_items(unverified)
    items += _experiment_items(experiment)
    items += machine_items(needs(report(spec), 'single_idea', experiment), tools_dir)
    items.append(Item(section='size', message=f'{len(masses)} fits, {toys} background-only simulations, and a {grid} × {grid} '
                                              'Track 1 plane around the band'))
    return SetupCheck(items=items, points=grid * grid, fits=len(masses), toys=toys)


def check_signal(experiment: str, models: int, toys: int, tools_dir: Path | None = None) -> SetupCheck:
    """The setup check of a Signal best fits run: the search, the library's classes plus the researcher's models,
    and the toys."""
    items = _experiment_items(experiment)
    items += machine_items(['LZ extended window'] if 'LZ extended window' in experiment else [], tools_dir)
    from adroit.orchestrator.signal import library_model_space
    space = f"the library's space ({len(library_model_space())} candidates, or the search's own published space)"
    items.append(Item(section='size', message=(f'{space} and {models} model(s) of yours' if models else space)
                      + f', then {toys} background-only simulations for the global significance'))
    return SetupCheck(items=items, toys=toys)


REFERENCE_KINDS = {'private-search:': 'personal, reviewed search', 'anomaly:': 'confirmed anomaly interpretation',
                   'record:': 'anomaly record'}


def _experiment_items(experiment: str) -> list[Item]:
    """The signal search: packaged, or a reference (a reviewed private search, a confirmed anomaly interpretation, an
    anomaly record) resolved as the run resolves it (``registry.load_module``), so that what the check accepts is
    what the run can load (the workflow audit's WA-01, 2026-10-24: a confirmed ``anomaly:`` interpretation, which the
    run loads, had been blocked here as "not a known search or record"); its review or confirmation is shown."""
    if not experiment:
        return [Item(section='missing', severity='blocking', message='choose the signal search or anomaly record')]
    from adroit.experiments.registry import load_module, signal_search_names
    if experiment in signal_search_names():
        return [Item(section='uses', message=f'signal search: {experiment} (packaged)')]
    kind = next((k for k in REFERENCE_KINDS if experiment.startswith(k)), None)
    if kind is None:
        return [Item(section='missing', severity='blocking', message=f'{experiment!r} is not a known search or record')]
    try:
        module = load_module(experiment)
        name = module.info.name
    except (ValueError, OSError, KeyError, RuntimeError) as error:
        return [Item(section='missing', severity='blocking',
                     message=f'{REFERENCE_KINDS[kind]} {experiment[:40]}… cannot be used: {error}')]
    items = [Item(section='uses', message=f'signal search: {name} ({REFERENCE_KINDS[kind]})')]
    if kind == 'anomaly:' and not getattr(module, 'verified', False):
        items.append(Item(section='pending', severity='pending', message='its source values are not yet reviewed: '
                          'the report is exploratory (a confirmed interpretation, not a source verification)'))
    if kind == 'record:':
        items.append(Item(section='pending', severity='pending', message='an anomaly record must be confirmed by a '
                          'person; unconfirmed, the report is provisional'))
    return items

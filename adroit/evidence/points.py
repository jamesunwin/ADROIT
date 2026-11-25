"""Explain a point of a saved study: what was calculated there and what each constraint decided (the owner's
workbench plan, 2026-10-18; the workbench inspection plan of 2026-10-18 §A).

Everything comes from the saved result and its evidence (``evidence.build.read``: the sidecar when there is one,
otherwise the same adapters on the saved objects): no physics is evaluated, no language model is asked and nothing
is fetched. A value that was not calculated stays missing, with its reason.
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field

from adroit.evidence.observations import review_label
from adroit.core.evidence import EvidenceObservation, physical_identity
from adroit.core.state import StrictModel

SLOTS = ('m_chi', 'm_med', 'g_chi', 'g_q', 'g_l')
UNITS = {'m_chi': 'GeV', 'm_med': 'GeV', 'g_chi': '', 'g_q': '', 'g_l': ''}
STATUS = {'viable': 'allowed', 'pending': 'pending', 'excluded': 'excluded', 'eligible': 'allowed',
          'excluded_point': 'excluded'}


class Link(StrictModel):
    """Where a pending item can be resolved: a workbench page or an exact command."""
    label: str
    target: str
    kind: Literal['page', 'command']


class PointRow(StrictModel):
    """One point of a study, as the point table shows it."""
    point_id: str      # grid:i, contour:j, likelihood:j, table-root:j, fitted:k, thermal:k, upper-thermal:k, plane-…
    kind: str
    coordinates: dict[str, float]
    omega_h2: float | None = None
    status: str                               # allowed, pending, excluded, not evaluated
    reason: str = ''                          # the first exclusion or pending reason
    subject_id: str = ''
    # the point's halo: its label over the region, at the fixed benchmark, or the published halos (``evidence.halo``)
    halo: str = Field(default='', exclude_if=lambda v: not v)


class Comparison(StrictModel):
    """One constraint at the point: its group, what was compared, the limit, the source and why it is pending."""
    constraint: str
    group: Literal['excluded', 'allowed', 'pending']
    prediction: float | None = None
    limit: float | None = None
    ratio: float | None = None
    units: str = ''
    native_confidence_level: float | None = None
    required_confidence_level: float | None = None
    construction: str = ''
    sources: list[str] = Field(default_factory=list)
    review: str = ''
    reasons: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)


class PointExplanation(StrictModel):
    """A point: where it is, what was calculated there, each constraint's decision and the verdict's context."""
    row: PointRow
    origin: str                               # the evidence sidecar, or reconstructed from the saved result
    engine: dict = Field(default_factory=dict)
    calculated: list[dict] = Field(default_factory=list)
    comparisons: list[Comparison] = Field(default_factory=list)
    context: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    fog: dict = Field(default_factory=dict)          # the neutrino fog at this point (an annotation)
    # a claim's stored certificate in words, against the data as they are now ("certified", "not certified: …",
    # "stale: …", "legacy, not assessed"); "" for a point that is not a claim (a grid point): CO-07
    certification: str = ""


def _finite(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _coordinates(point) -> dict[str, float]:
    return {k: getattr(point, k) for k in SLOTS if getattr(point, k, None) is not None}


def _status(excluded: bool, pending: bool) -> str:
    return 'excluded' if excluded else 'pending' if pending else 'allowed'


# The points of a study --------------------------------------------------------------------------------------------

def discovery_of(result) -> list:
    """The discovery requirements a saved Track 1 result applies to its points (S18-03): those its scan carries, or,
    for a result saved before they were carried, those of its pinned assessment for its selected private limits."""
    scan = getattr(result, 'scan', None)
    if scan is not None and scan.request.discovery:
        return list(scan.request.discovery)
    coverage = getattr(result, 'discovery_coverage', None)
    if coverage is None:
        return []
    from adroit.orchestrator.constraint_discovery import pending_spans
    return pending_spans(coverage, list(getattr(getattr(result, 'request', None), 'private_limits', []) or []))


def _scan_rows(result, prefix: str = '') -> list[tuple[PointRow, object, object]]:
    """(row, the saved PointResult, the engine) for a Track 1 result's grid and evaluated crossings; every point's
    status includes the run's discovery requirements, as the verdict's does."""
    from adroit.parameter_space.verdict import classify_saved, discovered
    out = []
    scan = getattr(result, 'scan', None)
    if scan is None:
        return out
    spans = discovery_of(result)
    engine = scan.request.model_class.model_dump(mode='json')
    for i, r in enumerate(scan.points):
        c = discovered(classify_saved(scan, r), spans)
        out.append((PointRow(point_id=f'{prefix}grid:{i}', kind='grid sample', coordinates=_coordinates(r.point),
                             omega_h2=_finite(r.omega_h2), status=STATUS[c.status],
                             reason=(c.excluded_by or c.pending or [''])[0],
                             subject_id=physical_identity(engine, r.point.model_dump(mode='json'))), r, scan))
    for view, name in ((result.verdict, 'contour'), (result.likelihood_verdict, 'likelihood')):
        for j, c in enumerate(view.crossings if view else []):
            c = discovered(c, spans)
            kind = {'contour': 'thermal root', 'theory_band': 'theory-band point'}.get(c.kind, c.kind)
            by = experimental_exclusion(c)          # excluded by its comparisons, only its thermal claim open
            central = central_exclusion(c)           # excluded at the region's centre, not shown robust (2026-11-24)
            out.append((PointRow(point_id=f'{prefix}{name}:{j}', kind=kind + (' (combined mode)' if name == 'likelihood' else ''),
                                 coordinates=_coordinates(c.point), omega_h2=_finite(c.omega_h2),
                                 status='excluded' if by else CENTRAL if central else STATUS.get(c.status, c.status),
                                 reason=(by or ([central] if central else []) or c.excluded_by or c.pending or [''])[0],
                                 subject_id=physical_identity(engine, c.point.model_dump(mode='json'))), c, scan))
        # the roots only a table has, each with its own certificate (the auditor's CO recheck, CR-02, 2026-10-26)
        for j, c in enumerate(view.table_roots if view else []):
            by = experimental_exclusion(c)
            out.append((PointRow(point_id=f'{prefix}{"table-root" if name == "contour" else name + "-table-root"}:{j}',
                                 kind='thermal root only a table has' + (' (combined mode)' if name == 'likelihood' else ''),
                                 coordinates=_coordinates(c.point), omega_h2=_finite(c.omega_h2),
                                 status='excluded' if by else STATUS.get(c.status, c.status),
                                 reason=(by or c.excluded_by or c.pending or [''])[0],
                                 subject_id=physical_identity(engine, c.point.model_dump(mode='json'))), c, scan))
    return out


def _single_rows(result) -> list[tuple[PointRow, object, object]]:
    out = []
    groups = [(result.band, 'fitted', 'fitted mass'), (result.thermal, 'thermal', 'thermal point'),
              *((rows, f'{table}-thermal', f'thermal point with the {table} table')      # CR-02's single-idea twin
                for table, rows in (getattr(result, 'eos_thermal', None) or {}).items())]
    for group, label, kind in groups:
        for k, b in enumerate(group):
            out.append((PointRow(point_id=f'{label}:{k}', kind=kind,
                                 coordinates=_coordinates(b.point) if b.point else {'m_chi': b.m_chi},
                                 omega_h2=_finite(b.omega_h2), status=STATUS.get(b.status, b.status or 'not evaluated'),
                                 reason=(b.excluded_by or b.pending or [b.inversion_reason])[0]), b, None))
    if result.track1 is not None:
        out += _scan_rows(result.track1, 'plane-')
    return out


def _signal_rows(result) -> list[tuple[PointRow, object, object]]:
    out = []
    for label, row in getattr(result, 'eligibility', {}).items():
        e = row.evaluation
        out.append((PointRow(point_id=f'candidate:{label}', kind='fitted candidate (physical point)',
                             coordinates=_coordinates(e.point) if e else _coordinates(row.point) if row.point else {},
                             omega_h2=_finite(e.omega_h2) if e else None, status=STATUS.get(row.status, row.status),
                             reason=(row.excluded_by or row.reasons or [''])[0]), row, None))
    return out


def rows(workflow: str, result) -> list[tuple[PointRow, object, object]]:
    """Every point of a saved result with its saved object (see ``points``)."""
    if workflow == 'track1':
        return _scan_rows(result)
    if workflow == 'single_idea':
        return _single_rows(result)
    if workflow == 'signal':
        return _signal_rows(result)
    return []


def points(workflow: str, result) -> list[PointRow]:
    """The point table of a saved result: Track 1's grid samples and evaluated crossings; Explain a signal's fitted
    masses, thermal points and its Track 1 plane; Signal best fits' physical candidates; each with its halo
    (``evidence.halo.point_label``)."""
    from adroit.evidence.halo import point_label, resolution_of
    resolution = resolution_of(workflow, result)[0]
    return [row.model_copy(update={'halo': point_label(_evaluation(saved), resolution)})
            for row, saved, _ in rows(workflow, result)]


# One point ------------------------------------------------------------------------------------------------------

def _evaluation(saved) -> object | None:
    """The saved comparisons of a point (a ``PointResult``), wherever the result keeps them."""
    from adroit.parameter_space.scan import PointResult
    if isinstance(saved, PointResult):
        return saved
    return getattr(saved, 'evaluation', None)


def links(reason: str, sources: list[str], session: str = '') -> list[Link]:
    """Where a pending item is resolved, from its structured references only; free text matching none gets no link.
    While the records cannot be read, none of them is linked (the auditor's CR recheck, CS-05, 2026-10-27: a damaged records
    file had made the point page a server error)."""
    import yaml
    from adroit.constraints.database import records
    from adroit.library.records_index import source_ids
    found: list[Link] = []
    try:
        known = {r.id: source_ids(r.source) for r in records()}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError):
        known = {}
    cited = source_ids(reason)
    for ref in sources + re.findall(r'(?:private-limit|private-search):[a-f0-9]{64}', reason):
        if ref in known:
            found.append(Link(label=f'review the record {ref}', target=f'/record?id={ref}', kind='page'))
        elif ref.startswith(('private-limit:', 'private-search:')):
            found.append(Link(label=f'the personal addition {ref[:24]}…', target='/records', kind='page'))
    for ref, ids in sorted(known.items()):
        named = ref in reason or (cited and set(cited) & set(ids))
        if named and not any(link.target.endswith(ref) for link in found):
            found.append(Link(label=f'review the record {ref}', target=f'/record?id={ref}', kind='page'))
    if reason.startswith('discovery:') and session:
        found.append(Link(label='the constraint-discovery session', target=f'/constraints/discovery?session={session}',
                          kind='page'))
    if any(word in reason.lower() for word in ('not in the tools', 'backend unavailable', 'not installed')):
        found.append(Link(label='check the machine', target='uv run adroit setup', kind='command'))
    return found


def own_observations(evaluation, engine: dict, envelope) -> list[EvidenceObservation]:
    """The observations of exactly this saved evaluation, built by the evidence's own adapter with the run's captured
    context (S18-09): a grid sample and a refined root at the same coordinates are different evaluations, so they are
    never joined by coordinates."""
    from adroit.evidence.observations import point_observations
    from adroit.parameter_space.scan import PointResult
    return point_observations(evaluation, engine, envelope.context) if isinstance(evaluation, PointResult) else []


def _record_value(context, record_id: str, key: str) -> float | None:
    for source in getattr(context, 'sources', []) or []:
        if source.id == record_id:
            return _finite(((source.metadata or {}).get('data') or {}).get(key))
    return None


def _numbers(name: str, evaluation, coverage: dict, stat: dict, context) -> tuple[float | None, float | None, str]:
    """(prediction, limit, units) of one comparison, from the fields that hold them (S18-10): a saved outcome's own
    prediction and limit first (a private limit's coverage, F19-06), then direct detection's own σ fields, the
    invisible widths' saved predictions and their records' bounds in the captured context; a statistic whose value is
    the prediction/limit ratio is never shown as a limit, and what was not saved stays missing."""
    from adroit.parameter_space.scan import HIGGS_INVISIBLE, INVISIBLE_H, INVISIBLE_Z, Z_INVISIBLE
    if coverage.get('limit') is not None or coverage.get('prediction') is not None:
        # the saved outcome's own numbers first: a private limit replacing a standard comparison keeps the standard
        # name, and its bound is not the standard record's (the fresh audit's F19-06)
        units = {'direct detection': 'cm²', INVISIBLE_H: 'branching ratio', INVISIBLE_Z: 'MeV'}.get(name, '')
        return _finite(coverage.get('prediction')), _finite(coverage.get('limit')), units
    if name == 'direct detection' and evaluation is not None:
        return _finite(evaluation.dd_sigma_cm2), _finite(evaluation.dd_limit_cm2), 'cm²'
    if name == INVISIBLE_H and evaluation is not None:
        return (_finite(evaluation.values.get('BR(h → invisible)')), _record_value(context, HIGGS_INVISIBLE, 'br_limit'),
                'branching ratio')
    if name == INVISIBLE_Z and evaluation is not None:
        return (_finite(evaluation.values.get('Γ(Z → invisible, new) (MeV)')),
                _record_value(context, Z_INVISIBLE, 'width_limit_mev'), 'MeV')
    construction = str(stat.get('construction', ''))
    ratio_valued = 'value is prediction/' in construction or 'rate multiplier' in construction
    return None, None if ratio_valued else _finite(stat.get('value')), ''


def _comparison(name: str, group: str, obs: EvidenceObservation | None, evaluation, reasons: list[str],
                session: str, context=None) -> Comparison:
    outcome = (obs.details.get('outcome') if obs else None) or {}
    coverage = outcome.get('coverage') or {}
    stat = (obs.details.get('statistical_limit') if obs else None) or {}
    prediction, limit, units = _numbers(name, evaluation, coverage, stat, context)
    ratio = _finite(obs.value) if obs and obs.value is not None else _finite(outcome.get('ratio'))
    sources = (obs.source_ids if obs else []) or ([s for s in [stat.get('source') or outcome.get('source')] if s])
    every = list(dict.fromkeys([*reasons, *(obs.reasons if obs else [])]))
    return Comparison(constraint=name, group=group, prediction=prediction, limit=limit, ratio=ratio,
                      units=units, native_confidence_level=obs.native_confidence_level if obs else None,
                      required_confidence_level=obs.required_confidence_level if obs else None,
                      construction=obs.construction if obs else '', sources=sources,
                      review=review_label(obs.review, obs.source_ids, context) if obs else '',
                      reasons=every if group == 'pending' else [],
                      links=[link for r in every for link in links(r, sources, session)] if group == 'pending' else [])


CHANGED = ("this study's result has changed since the point was chosen, so its name may be another point now; "
           "nothing is shown: reopen the study and choose the point again")
EVIDENCE_CHANGED = ("this study's evidence has changed since the point was chosen (its result the same), so what was "
                    "calculated there may be told otherwise now; nothing is shown: reopen the study and choose the "
                    "point again")


def explain(where, point_id: str) -> PointExplanation:
    """One point of a saved study, from its result and its evidence: the coordinates, what was calculated, every
    constraint sorted into excluded / allowed / pending with its prediction, limit, units, confidence levels, source
    and review state, and each pending item's reasons and links. ``where``: the study's version
    (``evidence.version.Version``), a token naming the version the point was chosen from (``Token``: another version's
    result or evidence is refused, ``CHANGED``, ``EVIDENCE_CHANGED``), or its result file (the version saved now, read
    once). A point's name (``grid:0``) means a point only within one version (the auditor's version-identity audit, VI-02,
    2026-11-03: a point chosen on A had opened B's point of that name), and its explanation is of one read of the
    result and the evidence (the auditor's CW recheck, CX-02, 2026-10-31: A's prediction beside B's limit)."""
    from adroit.evidence.version import Changed, Version, resolve
    try:
        found = where if isinstance(where, Version) else resolve(where)
    except Changed as changed:
        raise ValueError(EVIDENCE_CHANGED if changed.part == 'evidence' else CHANGED) from None
    snapshot = found.saved()
    workflow, result, envelope = snapshot.workflow, snapshot.result, snapshot.envelope
    found = {row.point_id: (row, saved, scan) for row, saved, scan in rows(workflow, result)}
    if point_id not in found:
        raise ValueError(f'no point {point_id!r} in this study')
    row, saved, scan = found[point_id]
    origin = 'the evidence sidecar' if snapshot.sidecar_sha256 else 'reconstructed from the saved result'
    evaluation = _evaluation(saved)
    session = _session(result)
    out = PointExplanation(row=row, origin=origin, engine=engine_of(workflow, saved, envelope),
                           certification=_certification(saved))
    if evaluation is None:
        return out.model_copy(update={'missing': ['no comparisons were saved at this point (a legacy result, or a '
                                                  'fit without a physical point)'], 'context': _context(saved)})
    observations = {o.observable: o for o in own_observations(evaluation, out.engine, envelope)}
    track1 = result.track1 if point_id.startswith('plane-') else result
    excluded, pending = decision(saved, evaluation, scan, discovery_of(track1) if workflow != 'signal' else [])
    comparisons = []
    # a comparison that excludes stands where only the point's thermal claim is open (the owner, 2026-11-23)
    waiting = [] if experimental_exclusion(saved) else _waiting(saved)
    for name, value in evaluation.excluded.items():
        mine = [p for p in pending if _concerns(name, p)]
        if value and name not in excluded and waiting:     # the stored decision, not the raw comparison (M1)
            group, mine = 'pending', [*mine, f'{name}: excluded by its own comparison (nominal); the point\'s claim '
                                             f'waits for its certificate: {waiting[0]}']
        else:
            group = 'excluded' if name in excluded or value else 'pending' if value is None or mine else 'allowed'
        comparisons.append(_comparison(name, group, observations.get(name), evaluation, mine, session,
                                       envelope.context))
    covered = {p for c in comparisons for p in c.reasons}
    for reason in pending:
        if reason not in covered:
            comparisons.append(Comparison(constraint=reason.split(':')[0], group='pending', reasons=[reason],
                                          links=links(reason, [], session)))
    for name in sorted(excluded - set(evaluation.excluded)):
        comparisons.append(Comparison(constraint=name, group='excluded', reasons=[]))
    calculated = [{'observable': o.observable, 'value': o.value, 'units': o.units, 'calculation': o.calculation,
                   'reasons': o.reasons, 'details': {k: v for k, v in o.details.items() if k in ('kind', 'limit_cm2')}}
                  for o in observations.values()
                  if o.observable in ('omega_h2', 'direct_detection_prediction') or o.observable.startswith('scalar_')]
    missing = [f"{c['observable']}: not calculated ({'; '.join(c['reasons']) or c['calculation']})"
               for c in calculated if c['value'] is None and c['observable'] in ('omega_h2', 'direct_detection_prediction')]
    missing += [f'relic validity: {r}' for r in evaluation.relic_validity]
    order = {'excluded': 0, 'pending': 1, 'allowed': 2}
    from adroit.evidence.halo import point_label, resolution_of
    halo = point_label(evaluation, resolution_of(workflow, result)[0])
    return out.model_copy(update={'calculated': calculated, 'missing': missing,
                                  'context': _context(saved) + ([f'halo: {halo}'] if halo else []),
                                  'fog': fog_of(evaluation),
                                  'comparisons': sorted(comparisons, key=lambda c: (order[c.group], c.constraint))})


def fog_of(evaluation) -> dict:
    """Where a spin-independent prediction lies against xenon's neutrino floor (O'Hare 2021's published n = 2 curve):
    an annotation, never a decision ({} for another interaction or outside the curve's masses)."""
    if evaluation is None or getattr(evaluation, 'dd_kind', '') != 'SI' or not _finite(evaluation.dd_sigma_cm2):
        return {}
    from adroit.physics.neutrino_fog import floor_at
    floor = floor_at(evaluation.point.m_chi, 'Xe')
    if floor is None:
        return {}
    sigma = float(evaluation.dd_sigma_cm2)
    return {'target': 'Xe', 'floor_cm2': floor, 'prediction_cm2': sigma, 'beneath': sigma < floor,
            'source': "O'Hare 2021 (arXiv:2109.03116), the published n = 2 floor"}


def _concerns(name: str, reason: str) -> bool:
    """Whether a pending reason is about this constraint: it names it, it is the verdict's record text for it
    (``verdict.RECORD_PENDING``), or its subject (before the colon) is the constraint's name."""
    from adroit.parameter_space.verdict import RECORD_PENDING
    subject = reason.split(':')[0].strip().lower().removeprefix('the ')
    return name in reason or RECORD_PENDING.get(name) == reason or bool(subject) and subject in name.lower()


def engine_of(workflow: str, saved, envelope) -> dict:
    """The engine description the evidence keyed this point's observations by: a signal candidate's own model
    class, else the result's engine mapping."""
    if workflow == 'signal':
        return dict(getattr(saved, 'model_class', {}) or {})
    return dict(envelope.engine_mapping)


def _certification(saved) -> str:
    """A saved claim's certificate read against the data as they are now (``core.certificate.reading``); "" for a
    point that carries no certificate field (a grid point is not a claim)."""
    if 'certificate' not in getattr(type(saved), 'model_fields', {}):
        return ''
    from adroit.core.certificate import reading
    from adroit.parameter_space.certification import current_bound
    c = saved.certificate
    return reading(c, current_bound(c) if c is not None else None)


CENTRAL = 'excluded at the central SHM'      # a point's status where only the region's centre excludes it


def central_exclusion(saved) -> str:
    """``certification.central_exclusion`` of a saved point ("" for one without its fields)."""
    from adroit.parameter_space.certification import central_exclusion as words
    return words(saved) if 'nominal_status' in getattr(type(saved), 'model_fields', {}) else ''


def experimental_exclusion(saved) -> list[str]:
    """``certification.experimental_exclusion`` of a saved point ([] for one without a certificate)."""
    from adroit.parameter_space.certification import experimental_exclusion as excluded_by
    return excluded_by(saved) if 'certificate' in getattr(type(saved), 'model_fields', {}) else []


def _waiting(saved) -> list[str]:
    """The open checks' reasons of a saved point its certificate left waiting (its computed constraints decided it,
    its claim is not certified: M1), else []."""
    c = getattr(saved, 'certificate', None)
    if c is None or getattr(saved, 'status', '') != 'pending' or c.computed_status in ('', 'pending'):
        return []
    return c.open_reasons() or ['its certificate is not complete']


def decision(saved, evaluation, scan, spans=()) -> tuple[set[str], list[str]]:
    """(the constraints that exclude the point, its pending reasons): the decision saved with the point (a
    crossing, a fitted or thermal point, a candidate), or, for a grid sample, which has none saved, the verdict's own
    classification of its saved comparisons (``verdict.classify_saved``: no model is called, F19-07); either with the run's
    discovery requirements (``spans``, ``verdict.discovered``)."""
    from adroit.parameter_space.scan import PointResult
    from adroit.parameter_space.verdict import Crossing, classify_saved, discovered
    if isinstance(saved, PointResult) and scan is not None:
        decided = discovered(classify_saved(scan, evaluation), spans)
        return set(decided.excluded_by), list(decided.pending)
    if isinstance(saved, Crossing):
        decided = discovered(saved, spans)
        return set(decided.excluded_by), list(decided.pending)
    pending = list(getattr(saved, 'pending', None) or getattr(saved, 'reasons', None) or [])
    return set(getattr(saved, 'excluded_by', [])), pending


def _context(saved) -> list[str]:
    """How the point entered the verdict: a refined root's target and residual, a band point's fit."""
    lines = []
    if getattr(saved, 'target', None) is not None:
        lines.append(f'refined thermal root for Ωh² = {saved.target:.4g} (relative residual '
                     f'{saved.relative_residual:.2g}; {"converged" if saved.converged else "not converged"})')
    if getattr(saved, 'physical_fit', None) is not None:
        fit = saved.physical_fit
        lines.append(f'bounded physical fit: q0 = {fit.q0}, resolved = {fit.resolved}, identifiable = '
                     f'{fit.identifiable}, at the range edge = {fit.at_boundary}')
    if getattr(saved, 'inversion_reason', ''):
        lines.append(saved.inversion_reason)
    return lines


def _session(result) -> str:
    coverage = getattr(result, 'discovery_coverage', None)
    return coverage.session_id if coverage is not None else ''

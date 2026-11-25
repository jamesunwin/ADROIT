"""A study's results as files: numerical tables, figures, references and the exact request (the owner's workbench
plan, 2026-10-18; the workbench inspection plan of 2026-10-18 §D).

Everything is read from the saved result and its evidence (``evidence.build.read``); figures are redrawn from the
saved scan and verdict by the existing plotting functions. Nothing is calculated, and a value that was not calculated
is an empty cell with its reason, never 0.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from adroit.evidence.observations import review_label
from adroit.evidence.points import SLOTS, rows

COLUMNS = ['point', 'kind', *SLOTS, 'status', 'observable', 'value', 'units', 'calculation', 'excluded',
           'native_confidence_level', 'required_confidence_level', 'construction', 'sources', 'review', 'reasons',
           'halo']
README = """Columns of points.csv (one row per point and observable; written by ADROIT from a saved result):
point            the point's identifier in the study (grid:i, contour:j, table-root:j, fitted:k, …)
kind             grid sample, thermal root, theory-band point, thermal root only a table has, fitted mass, thermal
                 point, thermal point with the upper (lower) table, fitted candidate
m_chi, m_med     masses in GeV; g_chi, g_q, g_l couplings (dimensionless); empty where the point has none
status           the point's status in the saved result: allowed, pending, excluded
observable       omega_h2, direct_detection_prediction, or a constraint's name
value            omega_h2: Ωh²; direct_detection_prediction: σ in cm²; a constraint: prediction / limit
units            the value's units
calculation      computed, or why there is no value (unresolved, missing_input, unavailable_backend, not_calculated)
excluded         the comparison's own result at the point: true, false, or empty (undecided); for a point its
                 certificate leaves waiting (status pending), a true here is its nominal exclusion, not the decision
*_confidence_level, construction, sources, review: the comparison's statistics and provenance
reasons          why it is pending or undecided
halo             the point's halo: its label over the halo region (excluded or allowed throughout, halo-sensitive,
                 halo coverage incomplete), at the fixed benchmark, or the published halos (halo.json: the study's
                 halo as its run resolved it, or as read from an older result's request)
An empty value is a value that was not calculated; it is never zero.
"""


CHANGED = ("this study's result has changed since its page was opened; nothing was made from it: reload the page for "
           "the version now saved")
EVIDENCE_CHANGED = ("this study's evidence has changed since its page was opened (its result is the same); nothing was "
                    "made from it: reload the page for the version now saved")
REPORT_CHANGED = ("this study's report has changed since its page was opened (its result is the same); nothing was made "
                  "from it: reload the page for the version now saved")


RECORD_CHANGED = ("this study's record has changed since its page was opened (its title, cost or dates; its result the "
                  "same); nothing was made from it: reload the page for the version now saved")
MESSAGES = {"result": CHANGED, "evidence": EVIDENCE_CHANGED, "presentation": REPORT_CHANGED, "record": RECORD_CHANGED}
NEEDS = {"tables": ("result", "evidence"), "figures": ("result", "presentation"),
         "references": ("result", "evidence", "record"), "bundle": ("result", "evidence", "presentation", "record")}


def held(where, presentation: bool = False):
    """The version a download is made of (``evidence.version``): ``where`` as it is where it is one; a token's version,
    each part it names checked (another is refused, naming it: ``CHANGED``, ``EVIDENCE_CHANGED``, ``REPORT_CHANGED``,
    ``RECORD_CHANGED``: the auditor's CX recheck, CY-03, 2026-11-01, and its version-identity audit, VI-03, 2026-11-03); a
    result file's, the version saved now, read once. ``presentation``: its report and figures read with it."""
    from adroit.evidence.version import Changed, Version, resolve
    if isinstance(where, Version):
        return where
    try:
        return resolve(where, presentation=presentation)
    except Changed as changed:
        raise ValueError(MESSAGES[changed.part]) from None


def needed(token, kind: str):
    """The token a download of ``kind`` requires of its page's (``NEEDS``): the parts it makes its files of. A table is
    of the result and its evidence; the figures, of the result and its report; the references, of the result, its
    evidence and its study record; the bundle, of all four."""
    from adroit.evidence.version import Token
    return Token(token.path, **{part: getattr(token, part) for part in NEEDS[kind]})


def table(where) -> list[dict]:
    """The rows of ``points.csv`` (see ``README``): each point's own saved evaluation (S18-09: never joined by
    coordinates to another evaluation at the same point), its status with the run's discovery requirements (S18-03),
    and a row naming those requirements where they keep it pending. Of one version's result and evidence (``held``;
    the auditor's CW recheck, CX-02, 2026-10-31)."""
    from adroit.evidence.halo import point_label, resolution_of
    from adroit.evidence.points import _concerns, _evaluation, decision, discovery_of, engine_of, own_observations
    snapshot = held(where).saved()
    workflow, result, envelope = snapshot.workflow, snapshot.result, snapshot.envelope
    resolution = resolution_of(workflow, result)[0]
    out = []
    for row, saved, scan in rows(workflow, result):
        evaluation = _evaluation(saved)
        engine = engine_of(workflow, saved, envelope)
        observations = own_observations(evaluation, engine, envelope) if evaluation is not None else []
        base = {'point': row.point_id, 'kind': row.kind, **{k: row.coordinates.get(k, '') for k in SLOTS},
                'status': row.status, 'halo': point_label(evaluation, resolution)}
        if not observations:
            out.append({**base, 'observable': 'omega_h2', 'value': '' if row.omega_h2 is None else row.omega_h2,
                        'units': 'dimensionless', 'calculation': 'computed' if row.omega_h2 is not None else
                        'not_calculated', 'reasons': row.reason})
        for o in observations:
            reasons = list(dict.fromkeys([*(p for p in evaluation.pending if _concerns(o.observable, p)), *o.reasons]))
            out.append({**base, 'observable': o.observable, 'value': '' if o.value is None else o.value,
                        'units': o.units, 'calculation': o.calculation,
                        'excluded': '' if o.excluded is None else str(o.excluded).lower(),
                        'native_confidence_level': o.native_confidence_level or '',
                        'required_confidence_level': o.required_confidence_level or '',
                        'construction': o.construction, 'sources': '; '.join(o.source_ids),
                        'review': review_label(o.review, o.source_ids, envelope.context),
                        'reasons': '; '.join(reasons)})
        if workflow != 'signal' and evaluation is not None:
            track1 = result.track1 if row.point_id.startswith('plane-') else result
            found = [p for p in decision(saved, evaluation, scan, discovery_of(track1))[1] if p.startswith('discovery:')]
            if found:
                out.append({**base, 'observable': 'constraint discovery', 'value': '', 'units': '',
                            'calculation': 'not_calculated', 'reasons': '; '.join(found)})
    return out


def tables(where) -> dict[str, bytes]:
    """``points.csv`` (full precision), ``points.json``, a plain numeric ``points_numeric.csv`` (status codes and
    numbers only, empty where missing; convenient for Mathematica's Import), ``README.txt`` and, for a workflow with a
    halo, ``halo.json`` (its resolution, recorded or read from an older result's request, and which: ``evidence.halo``),
    of one version (``held``)."""
    version = held(where)
    data = table(version)
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=COLUMNS, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    for row in data:
        writer.writerow({k: repr(v) if isinstance(v, float) else v for k, v in row.items()})
    numeric = io.StringIO()
    keys = ['point_index', *SLOTS, 'status_code', 'observable', 'value']
    plain = csv.writer(numeric, lineterminator='\n')
    plain.writerow(keys)
    codes = {'allowed': 0, 'pending': 1, 'excluded': 2}
    names = {p: i for i, p in enumerate(dict.fromkeys(r['point'] for r in data))}
    for row in data:
        plain.writerow([names[row['point']], *[repr(row[k]) if isinstance(row[k], float) else row[k] for k in SLOTS],
                        codes.get(row['status'], ''), row['observable'],
                        repr(row['value']) if isinstance(row['value'], float) else row['value']])
    legend = README + '\npoints_numeric.csv: point_index numbers the points in order of points.csv; status_code 0 ' \
                      'allowed, 1 pending, 2 excluded.\n'
    out = {'points.csv': text.getvalue().encode(), 'points.json': json.dumps(data, indent=1).encode(),
           'points_numeric.csv': numeric.getvalue().encode(), 'README.txt': legend.encode()}
    from adroit.evidence.halo import resolution_of
    snapshot = version.saved()
    found, how = resolution_of(snapshot.workflow, snapshot.result)
    if found is not None:
        out['halo.json'] = json.dumps({'how': how, 'resolution': found.model_dump(mode='json')}, indent=1,
                                      ensure_ascii=False).encode()
    return out


def figures(where, formats: tuple[str, ...] = ('pdf', 'svg')) -> dict[str, bytes]:
    """The parameter plane (with Explain a signal's band) and direct detection redrawn from the saved scan and verdict
    in each format, with the saved PNGs. Nothing is evaluated and no current limit is read (S18-11): direct
    detection shows the σ and limit saved with each relic-contour point. A result without a scan has none.

    Of one version, its report and figures read with its result (``held``; a token's report checked:
    ``REPORT_CHANGED``, the auditor's version-identity audit, VI-03, 2026-11-03). A saved PNG is included only as the figure
    of that result: where the report is bound to it, each PNG its binding names, with the bytes it names
    (``evidence.bindings``; the auditor's CX recheck, CY-03, 2026-11-01); where the report records no binding (written before
    ADROIT recorded one), each as read with it, as found; ``figures.txt`` says which were left out, or not checked, and
    why."""
    import tempfile
    from adroit.evidence.results import typed
    from adroit.parameter_space import plots
    found = held(where, presentation=True)
    data = found.data()                                 # FileNotFoundError or OSError without a readable result
    if not isinstance(data, dict):
        raise ValueError(f'{found.path.name} is not a JSON object')
    digest = found.result_sha256
    workflow, result = typed(data)
    report = found.report()
    out, notes = {}, []
    for name in sorted(n for n in found.figures if n.endswith('.png')):
        if found.figure_as_found(name) is None:
            continue
        if report.state == 'bound':
            data = found.figure(name)
            if data is None:
                notes.append(f'{name}: left out: not the figure the report of this result was written with')
            else:
                out[name] = data
        elif report.state in ('other', 'unreadable', 'interrupted'):
            notes.append(f'{name}: left out: the report beside the result is of another version of it'
                         if report.state == 'other' else
                         f'{name}: left out: the study\'s last publication was interrupted, so its report and figures '
                         'may be an earlier publication\'s' if report.state == 'interrupted' else
                         f'{name}: left out: the report beside the result cannot be read, so this figure cannot be '
                         'checked against it')
        else:
            out[name] = found.figure_as_found(name)
            notes.append(f'{name}: included as found: the report records no link to the result (written before '
                         'ADROIT recorded one), so this figure is not checked against it')
    if notes:
        out['figures.txt'] = ('\n'.join([f'Figures of the result with SHA-256 {digest}', *notes]) + '\n').encode()
    track1 = result if workflow == 'track1' else getattr(result, 'track1', None)
    if track1 is None or track1.scan is None or track1.verdict is None:
        return out
    single = workflow == 'single_idea'
    from adroit.orchestrator.single_idea import plane_overlays
    overlays = plane_overlays(result) if single else {}      # the band and the stored signal assessment, as the study
    title = result.request.spec.name if single else track1.request.spec.name
    with tempfile.TemporaryDirectory(prefix='adroit-figures-') as folder:
        for fmt in formats:
            plane = plots.plane(track1.scan, track1.verdict, Path(folder) / f'parameter_plane.{fmt}', title=title,
                                **overlays)
            out[plane.name] = plane.read_bytes()
            dd = plots.direct_detection_saved(track1.verdict, Path(folder) / f'direct_detection.{fmt}')
            if dd:
                out[Path(dd).name] = Path(dd).read_bytes()
    return out



def request(where) -> dict[str, bytes]:
    """The exact saved request and the study record, of one version (``held``): the result's own request, else the
    inputs its evidence captured (a native fit's request among them). A ``request.json`` beside the result is never
    read: it is not bound to the result, and a valid other request there had been downloaded as the exact request of a
    native fit whose evidence names another (the auditor's CY recheck, CZ-03, 2026-11-01). The study record, read with the
    result, is included where it names this result (``Version.record_state``), and as found where it names none
    (written before), saying so in ``study_record.txt``; one naming another version is left out, saying so (the auditor's
    version-identity audit, VI-01, 2026-11-03: B's title and cost had been downloaded beside A's request). The record
    beside a promotion is its parent study's, checked against the parent result the promotion records, by the export's
    rule (``studies.described``; the auditor's DB/VI recheck, DC-05, 2026-11-03)."""
    found = held(where)
    snapshot = found.saved()
    result = snapshot.result
    out = {}
    if hasattr(result, 'request'):
        out['request.json'] = json.dumps(result.request.model_dump(mode='json'), indent=1).encode()
    else:
        inputs = snapshot.envelope.original_inputs
        if inputs:
            out['request.json'] = json.dumps(inputs, indent=1).encode()
    from adroit.evidence.archive import ATTACHED
    state = found.record_state
    if state == 'absent':
        return out
    if state in ATTACHED:
        out['study.json'] = found.record_bytes
    if state in STUDY_NOTES:
        whose = 'the parent result this promotion records' if snapshot.workflow == 'promotion' else 'this result'
        out['study_record.txt'] = (STUDY_NOTES[state].format(whose=whose) + '\n').encode()
    return out


STUDY_NOTES = {
    'unbound': 'study.json is included as found: it was written before ADROIT tied a study record to its result, so it '
               'is not checked against {whose}',
    'unread': 'study.json is included as found: {whose} has no recorded digest to check it against',
    'other': 'study.json is not included: it describes another version of {whose} (one was replaced since the other '
             'was written)',
    'interrupted': 'study.json is not included: the last publication of {whose} was interrupted while it wrote its '
                   'parts, so the record may be an earlier publication\'s (the auditor\'s portability audit, IC-01)',
    'damaged': 'study.json is not included: it cannot be read as a study record',
    'unreadable': 'study.json is not included: it cannot be read'}



def _bib_entries() -> dict[str, str]:
    """``docs/dependencies.bib`` by arXiv identifier and DOI."""
    from adroit.core.config import PROJECT_ROOT
    path = PROJECT_ROOT / 'docs' / 'dependencies.bib'
    entries = {}
    for block in re.split(r'\n(?=@)', path.read_text()) if path.exists() else []:
        for key in re.findall(r'(?:eprint|arxiv)\s*=\s*[{"]([^}"]+)', block, re.I):
            entries['arxiv:' + key.strip().lower()] = block.strip()
        for key in re.findall(r'doi\s*=\s*[{"]([^}"]+)', block, re.I):
            entries['doi:' + key.strip().lower()] = block.strip()
    return entries


def references(where) -> dict[str, bytes]:
    """``references.bib`` (the entries ``docs/dependencies.bib`` has for the run's sources) and ``sources.txt``
    (every source the evidence names, with whether an entry was found; none is invented), of one version (``held``)."""
    from adroit.library.records_index import source_ids
    envelope = held(where).saved().envelope
    known = _bib_entries()
    found, lines = [], []
    for source in envelope.context.sources:
        ids = source_ids(source.reference, source.id)
        entry = next((known[i] for i in ids if i in known), None)
        if entry and entry not in found:
            found.append(entry)
        review = review_label(source.review, [source.id], envelope.context)
        lines.append(f"{source.id}\t{source.reference}\t{review}\t{'bib entry' if entry else 'no bib entry'}")
    return {'references.bib': ('\n\n'.join(found) + '\n').encode(),
            'sources.txt': ('\n'.join(['id\treference\treview\tbibliography', *lines]) + '\n').encode()}


def bundle(where, destination: Path) -> Path:
    """The portable evidence bundle (``evidence.archive.export_run``) of one version (``held``: a token's every part
    checked, VI-03), verified after writing."""
    from adroit.evidence.archive import export_run, verify_bundle
    export_run(held(where, presentation=True), destination)
    checked = verify_bundle(destination)
    if not checked.valid:
        raise ValueError(f'the exported bundle did not verify: {"; ".join(checked.issues)}')
    return destination


def archive(files: dict[str, bytes]) -> bytes:
    """Several exported files as one ZIP (for a single download), each checked for credentials as the evidence bundle
    checks its members (``archive.refuse_credentials``; the security addendum's AL3-28: these downloads had been
    zipped unchecked)."""
    import zipfile
    from adroit.evidence.archive import refuse_credentials
    for name, data in files.items():
        refuse_credentials(name, data)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
    return stream.getvalue()

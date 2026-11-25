"""A study's results as files (the owner's workbench plan, 2026-10-18, §D): tables that keep missing values missing
and reproduce the saved numbers exactly, vector figures redrawn from the saved scan, references without invention,
a verified bundle, and a study folder left untouched."""

from __future__ import annotations

import csv
import hashlib
import io
import json

from adroit.evidence import exports
from tests.evidence.test_points import _result


def _digest(folder) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file()}


def test_tables_keep_missing_values_missing_and_the_saved_numbers_exact(tmp_path) -> None:
    path = _result(tmp_path)
    files = exports.tables(path)
    assert set(files) == {'points.csv', 'points.json', 'points_numeric.csv', 'README.txt', 'halo.json'}
    halo = json.loads(files['halo.json'])            # an older result: its halo read from its request, said so
    assert halo['resolution']['treatment'] == 'published' and 'older result' in halo['how']
    rows = list(csv.DictReader(io.StringIO(files['points.csv'].decode())))
    assert {r['halo'] for r in rows} == {halo['resolution']['label']}
    omega = next(r for r in rows if r['point'] == 'grid:2' and r['observable'] == 'omega_h2')
    assert omega['value'] == '' and omega['calculation'] == 'unresolved' and 'unavailable' in omega['reasons']
    dd = next(r for r in rows if r['point'] == 'grid:0' and r['observable'] == 'direct detection')
    assert float(dd['value']) == 2.0 and dd['excluded'] == 'true' and dd['native_confidence_level'] == '0.9'
    hinv = next(r for r in rows if r['point'] == 'grid:1' and r['observable'] == 'invisible Higgs width (ATLAS)')
    assert hinv['value'] == '' and hinv['excluded'] == '' and 'awaits' in hinv['reasons']
    assert not any(r['value'] == '0' for r in rows if r['calculation'] != 'computed')
    numeric = list(csv.reader(io.StringIO(files['points_numeric.csv'].decode())))
    assert numeric[0][:2] == ['point_index', 'm_chi'] and {row[6] for row in numeric[1:]} <= {'0', '1', '2'}
    assert 'never zero' in files['README.txt'].decode()


def test_figures_are_redrawn_in_vector_formats_from_the_saved_scan(tmp_path) -> None:
    path = _result(tmp_path)
    files = exports.figures(path, ('pdf', 'svg'))
    assert files['parameter_plane.pdf'].startswith(b'%PDF') and b'<svg' in files['parameter_plane.svg'][:400]


def test_references_list_every_source_and_invent_none(tmp_path) -> None:
    from adroit.core.evidence import EvidenceContext, SourceEvidence
    from adroit.evidence.build import save
    path = _result(tmp_path)
    context = EvidenceContext(sources=[SourceEvidence(id='planck-2018-omega', reference='arXiv:1807.06209',
                                                      review='not_required'),
                                       SourceEvidence(id='made-up', reference='arXiv:9999.99999', review='not_required')])
    save(path, 'track1', context)
    files = exports.references(path)
    lines = files['sources.txt'].decode().splitlines()
    assert lines[0].startswith('id\t') and len(lines) == 3
    assert 'made-up\tarXiv:9999.99999\tnot_required\tno bib entry' in lines
    assert b'9999.99999' not in files['references.bib']
    assert set(exports.request(path)) == {'request.json'}


def test_the_bundle_verifies_and_the_study_folder_is_unchanged(tmp_path) -> None:
    (tmp_path / 'study').mkdir()
    path = _result(tmp_path / 'study')
    before = _digest(path.parent)
    exports.tables(path)
    exports.figures(path)
    exports.references(path)
    bundle = exports.bundle(path, tmp_path / 'out' / 'evidence.zip')
    assert bundle.exists() and _digest(path.parent) == before


def test_a_native_fit_downloads_its_verified_request(tmp_path, monkeypatch) -> None:
    """The stacked audit's nonblocking note: a native-fit result has no .request; its download is the request its
    evidence captured, not left out. The request.json beside it is never read (the auditor's CY recheck, CZ-03): with
    evidence capturing none, no request is downloaded rather than an unchecked file."""
    import hashlib
    from adroit.core.durable import write_atomic
    from adroit.evidence import build, exports
    from tests.orchestrator.test_db_recheck import _native_fit
    captured = {"null_experiment": "PICO-60 C3F8 (2019)"}
    fit, _ = _native_fit(tmp_path)
    path = tmp_path / 'native' / 'result.json'
    path.parent.mkdir()
    content = fit.model_dump_json().encode()
    write_atomic(path, content)
    (path.parent / 'request.json').write_text('{"null_experiment": "another"}')
    sidecar = build.build("native_joint", fit, hashlib.sha256(content).hexdigest(), original_inputs=captured)
    write_atomic(build.sidecar_path(path), sidecar.model_dump_json().encode())
    assert json.loads(exports.request(path)['request.json']) == captured
    sidecar = build.build("native_joint", fit, hashlib.sha256(content).hexdigest(), original_inputs={})
    write_atomic(build.sidecar_path(path), sidecar.model_dump_json().encode())
    assert 'request.json' not in exports.request(path)

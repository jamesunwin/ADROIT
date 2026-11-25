"""Studies to revisit after an update (the owner's workbench plan of 2026-10-18, part 2 §H): each changed input with
what actually changed; nothing reruns and no study changes."""
from __future__ import annotations

import hashlib
import json

from adroit.core.evidence import EvidenceContext, EvidenceEnvelope, EvidenceObservation, SourceEvidence
from adroit.library.experimental import ExperimentalCatalog
from adroit.library.personal import Catalog
from adroit.orchestrator import revisit, studies

RECORD = 'atlas-2301.10731-hinv'


def _study(root, name, request=None, models=()):
    folder = root / name
    folder.mkdir(parents=True)
    (folder / 'result.json').write_text(json.dumps({'request': request or {}}))
    studies.record(folder, 'track1', f'study {name}', model_references=list(models))
    return studies.load(folder)


def _revisions(tmp_path):
    from adroit.orchestrator.model_approval import SCHEMA_VERSION, ModelApproval, model_identity
    from adroit.parameter_space.library import entry
    catalog = Catalog(tmp_path / 'models')
    spec = entry('higgs_portal_scalar').spec()        # with values: only a model that can run is saved (the auditor's UM-02)
    spec = spec.model_copy(update={'couplings': [c.model_copy(update={'value': 0.1}) if c.name in ('lam_H_S', 'lam_S')
                                                 else c for c in spec.couplings]})
    approve = lambda s: ModelApproval(model_sha256=model_identity(s), source_model_sha256=model_identity(s),  # noqa: E731
                                      choice='supplied', schema_version=SCHEMA_VERSION)
    first = catalog.save(spec, approve(spec))
    changed = spec.model_copy(update={'couplings': [c.model_copy(update={'value': 0.3}) if c.name == 'lam_H_S' else c
                                                    for c in spec.couplings]})
    second = catalog.save(changed, approve(changed), parent=first.reference)
    return catalog, first, second


def test_differences_match_named_items_and_say_what_changed() -> None:
    old = {'couplings': [{'name': 'g', 'value': 1}, {'name': 'h', 'value': 2}], 'name': 'm'}
    new = {'couplings': [{'name': 'g', 'value': 1.5}, {'name': 'k', 'value': 3}], 'name': 'm'}
    assert revisit.differences(old, new) == ['couplings: added k', 'couplings: removed h', 'couplings[g].value: 1 → 1.5']


def test_a_newer_model_revision_is_shown_with_its_changes(tmp_path) -> None:
    catalog, first, second = _revisions(tmp_path)
    study = _study(tmp_path / 'runs', 'a', models=[first.reference])
    before = hashlib.sha256((tmp_path / 'runs' / 'a' / 'result.json').read_bytes()).hexdigest()
    (update,) = revisit.for_study(tmp_path / 'runs', study, ExperimentalCatalog(tmp_path / 'private'), catalog)
    assert (update.kind, update.old, update.new) == ('model', first.reference, second.reference)
    assert any(line.startswith('couplings[lam_H_S].value:') and line.endswith('→ 0.3') for line in update.changes)
    assert hashlib.sha256((tmp_path / 'runs' / 'a' / 'result.json').read_bytes()).hexdigest() == before


def test_a_record_that_changed_since_the_run_is_shown_field_by_field(tmp_path) -> None:
    from adroit.constraints.database import records
    from adroit.evidence.build import sidecar_path
    current = next(r for r in records() if r.id == RECORD).model_dump(mode='json')
    then = {**current, 'confidence_level': 0.9, 'version': 1}
    study = _study(tmp_path / 'runs', 'a')
    held = hashlib.sha256((tmp_path / 'runs' / 'a' / 'result.json').read_bytes()).hexdigest()   # the evidence of it
    envelope = EvidenceEnvelope(workflow='track1', result_sha256=held, input_sha256='0' * 64,
                                context=EvidenceContext(sources=[SourceEvidence(id=RECORD, version='1', metadata=then,
                                                                                review='not_required')]),
                                observations=[EvidenceObservation(subject_id='s', physical_input={}, observable='x',
                                                                  source_ids=[RECORD])])
    sidecar_path(tmp_path / 'runs' / 'a' / 'result.json').write_text(envelope.model_dump_json())
    (update,) = revisit.for_study(tmp_path / 'runs', study, ExperimentalCatalog(tmp_path / 'private'),
                                  Catalog(tmp_path / 'models'))
    assert update.kind == 'record' and f'confidence_level: 0.9 → {json.dumps(current["confidence_level"])}' in update.changes
    # evidence of another version of the result (the auditor's CX recheck, CY-03): its history is not shown as this one's
    sidecar_path(tmp_path / 'runs' / 'a' / 'result.json').write_text(
        envelope.model_copy(update={'result_sha256': '0' * 64}).model_dump_json())
    (update,) = revisit.for_study(tmp_path / 'runs', study, ExperimentalCatalog(tmp_path / 'private'),
                                  Catalog(tmp_path / 'models'))
    assert (update.kind, update.new) == ('record', 'not known') and not any('confidence_level' in c for c in update.changes)


def test_a_successor_profile_lists_what_it_adds_and_removes(tmp_path) -> None:
    catalog = ExperimentalCatalog(tmp_path / 'private')
    (catalog.root / 'profiles').mkdir(parents=True)
    old, new = 'a' * 64, 'b' * 64
    (catalog.root / 'profiles' / f'{old}.json').write_text(json.dumps({'limits': ['private-limit:1'], 'null_modules': [],
                                                                       'signal': '', 'created_at': '1'}))
    (catalog.root / 'profiles' / f'{new}.json').write_text(json.dumps({'limits': ['private-limit:2'], 'parent': f'profile:{old}',
                                                                       'null_modules': ['LZ'], 'signal': '', 'created_at': '2'}))
    study = _study(tmp_path / 'runs', 'a', request={'experimental_profile': f'profile:{old}'})
    (update,) = revisit.for_study(tmp_path / 'runs', study, catalog, Catalog(tmp_path / 'models'))
    assert update.new == f'profile:{new}' and set(update.changes) == {
        'limits: added private-limit:2', 'limits: removed private-limit:1', 'null_modules: added LZ'}


def test_an_explicitly_superseded_private_limit_is_shown(tmp_path) -> None:
    from tests.private_limit_fixtures import eligible, fixture
    old = 'private-limit:' + 'c' * 64
    catalog, r = fixture(tmp_path / 'fixture', 'sm_higgs_invisible', overlap='supersedes', supersedes=[old])
    bound = eligible(catalog, r)
    study = _study(tmp_path / 'runs', 'a', request={'private_limits': [old]})
    (update,) = revisit.for_study(tmp_path / 'runs', study, catalog, Catalog(tmp_path / 'models'))
    assert (update.kind, update.old, update.new) == ('private limit', old, bound.reference)
    assert revisit.for_study(tmp_path / 'runs', _study(tmp_path / 'runs', 'b'), catalog, Catalog(tmp_path / 'models')) == []

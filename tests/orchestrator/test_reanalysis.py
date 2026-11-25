import json
import pytest
from adroit.orchestrator.reanalysis import Reanalysis
from adroit.library.personal import Catalog
from adroit.orchestrator.track1 import Track1Request,Track1Result
from adroit.model_building.audit import audit
from tests.orchestrator.test_physical_eligibility import spec

def parent(tmp_path):
    s=spec()
    req=Track1Request(spec=s,literature=False,workers=1)
    result=Track1Result(request=req,audit=audit(s),created='2025-01-02')
    folder=tmp_path/'original'
    folder.mkdir()
    path=folder/'result.json'
    path.write_text(result.model_dump_json())
    return path

def test_reopen_revise_cross_track_and_original_bytes_unchanged(tmp_path):
    path=parent(tmp_path)
    before=path.read_bytes()
    service=Reanalysis(Catalog(tmp_path/'models'))
    first=service.open(str(path))
    assert first.workflow=='track1' and first.original_request==first.request
    changed={**first.request,'workers':2}
    second=service.revise(first.reference,changed)
    assert second.parent_draft==first.draft_id and service.load(first.reference)==first
    assert path.read_bytes()==before and service.preview(second.reference)['differences']
    signal=service.open(str(path),'signal')
    assert signal.request['user_models'][0]['spec']==first.request['spec']
    assert any('select the signal' in b for b in service.preview(signal.reference)['blockers'])
    reverse_request={**signal.request,'experiment':'LZ extended window (2026)'}
    revised=service.revise(signal.reference,reverse_request)
    assert not service.preview(revised.reference)['blockers']

def test_parent_tampering_stale_review_and_output_overwrite_refused(tmp_path,monkeypatch):
    service=Reanalysis(Catalog(tmp_path/'models'))
    path=parent(tmp_path)
    draft=service.open(str(path))
    review=service.preview(draft.reference)
    with pytest.raises(ValueError,match='explicit review'):
        service.run(draft.reference,tmp_path/'child',review['review_sha256'],confirmed=False,reviewer='Fixture')
    with pytest.raises(ValueError,match='review changed'):
        service.run(draft.reference,tmp_path/'child','wrong',confirmed=True,reviewer='Fixture')
    with pytest.raises(ValueError,match='fresh empty'):
        service.run(draft.reference,path.parent,review['review_sha256'],confirmed=True,reviewer='Fixture')
    with pytest.raises(ValueError,match='inside its source study'):
        service.run(draft.reference,tmp_path/'sibling',review['review_sha256'],confirmed=True,reviewer='Fixture')
    path.write_text(path.read_text().replace('2025-01-02','2025-01-03'))
    assert service.preview(draft.reference)['blockers']
    with pytest.raises(ValueError):
        service.run(draft.reference,tmp_path/'child',review['review_sha256'],confirmed=True,reviewer='Fixture')

def test_exact_catalog_revision_selection_and_paid_free_run_boundary(tmp_path,monkeypatch):
    from adroit.orchestrator.model_intake import Intake
    from adroit.orchestrator.model_approval import model_identity
    from adroit.orchestrator import runs
    import yaml
    catalog=Catalog(tmp_path/'models')
    intake=Intake(catalog)
    session=intake.start()
    s=spec()
    d=intake.step(session.session_id,'typed',yaml.safe_dump(s.model_dump(mode='json')))
    revision=intake.approve(session.session_id,d.step_id,0,confirmed=True,expected_model_hash=model_identity(s),tex=d.choices[0].tex)
    service=Reanalysis(catalog)
    draft=service.open(revision.reference)
    assert draft.source_kind=='catalog'
    chosen=service.choose_model(draft.reference,revision.reference)
    assert chosen.request['catalog_reference']==revision.reference
    review=service.preview(chosen.reference)
    assert not review['blockers']
    calls=[]
    def run(request,out,**kwargs):              # the writer's contract (``runs._write``): certify, then publish
        from adroit.evidence.version import resolve
        calls.append(request)
        out.mkdir(exist_ok=True)
        kwargs['certify']('fake')
        (out/'result.json').write_text('{}')
        for name,data in kwargs['beside'].items():     # what its writer puts beside its parts (DE-02)
            (out/name).write_text(json.dumps(data))
        kwargs['published']['token']=resolve(out/'result.json').token()
        return out,'controlled fake run'
    monkeypatch.setattr(runs,'track1',run)
    folder,_=service.run(chosen.reference,tmp_path/'child',review['review_sha256'],confirmed=True,reviewer='Fixture')
    assert calls[0].approved_model_sha256==revision.model_sha256 and calls[0].reviewed_scan_sha256
    assert json.loads((folder/'reanalysis.json').read_text())['source_result_sha256']==revision.revision_id
    bad=catalog.root/'reanalysis/drafts'/f'{chosen.draft_id}.json'
    payload=json.loads(bad.read_text())
    payload['request']['workers']=3
    bad.write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='modified'):
        service.load(chosen.reference)

def test_bare_operator_result_cannot_become_unique_physical_model(tmp_path):
    from adroit.orchestrator.signal import SignalRequest,SignalResult
    from adroit.inference.dm_tournament import run
    path=tmp_path/'result.json'
    result=SignalResult(request=SignalRequest(experiment='CDMS II Si (2013)'),fits=[],classes={},n_classes=0,
        max_local_z=0,global_p_toys=1,global_p_closed_form=None,global_z=0,combinations=[],tournament=run([]),separations=[])
    path.write_text(result.model_dump_json())
    service=Reanalysis(Catalog(tmp_path/'models'))
    with pytest.raises(ValueError,match='bare NR card'):
        service.open(str(path),'track1')

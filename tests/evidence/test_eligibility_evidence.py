from adroit.core.evidence import EvidenceContext
from adroit.orchestrator import signal,physical_eligibility
from adroit.evidence import build
from adroit.evidence.archive import export_run,verify_bundle
from adroit.evidence.replay import replay_bundle
from tests.orchestrator.test_signal import ToyGermanium
from tests.orchestrator.test_physical_eligibility import spec,point_result
from adroit.parameter_space.classify import classify
from adroit.orchestrator.model_approval import model_identity

def test_eligibility_decisions_are_bound_and_replayed_without_catalog(tmp_path,monkeypatch):
    from adroit.parameter_space import scan
    s=spec()
    cls,p,_=classify(s)
    user=signal.UserModel(spec=s,masses_gev=[20])
    monkeypatch.setitem(signal.modules.SIGNAL_SEARCHES,'toy germanium',ToyGermanium)
    context=EvidenceContext(origin='captured',identity='current',code_sha256='code')
    monkeypatch.setattr(physical_eligibility,'_current_context',lambda *a:context)
    monkeypatch.setattr(scan,'evaluate',lambda cls,p,*a,**k:point_result(p,excluded=True))
    result=signal.run(signal.SignalRequest(experiment='toy germanium',user_models=[user],null_modules=[],toys=20,complementary=True))
    row=next(iter(result.eligibility.values()))
    assert row.status=='excluded_point' and row.evaluation
    out=tmp_path/'run'
    out.mkdir()
    path=out/'result.json'
    path.write_text(result.model_dump_json())
    monkeypatch.setattr(build,'finish',lambda c,read=None,consumed=None:c)
    envelope=build.save(path,'signal',context)
    assert envelope.summary['eligibility'][row.label]['status']=='excluded_point'
    assert envelope.certificates['physical_eligibility'][row.label]['model_sha256']==model_identity(s)
    assert any(o.details.get('candidate_label')==row.label for o in envelope.observations)
    archive=tmp_path/'point.zip'
    export_run(path,archive)
    assert verify_bundle(archive).valid
    replay=replay_bundle(archive,eligibility=True)
    assert replay.status=='matched' and 'no global toys' in replay.calculation
    path.write_text(path.read_text().replace('"status":"excluded_point"','"status":"eligible"'))
    import pytest
    with pytest.raises(ValueError,match='mismatch'):
        build.read(path)

def test_legacy_signal_evidence_does_not_invent_eligibility(tmp_path):
    from adroit.inference.dm_tournament import run
    from adroit.evidence.results import summary,summary_matches
    result=signal.SignalResult(request=signal.SignalRequest(experiment='legacy'),fits=[],classes={},n_classes=0,
        max_local_z=0,global_p_toys=1,global_p_closed_form=None,global_z=0,combinations=[],tournament=run([]),separations=[])
    old=summary('signal',result)
    assert 'eligibility' not in old and summary_matches('signal',old,result)

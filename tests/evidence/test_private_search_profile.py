from tests.private_search_fixtures import fixture,eligible
from tests.library.test_experimental_profiles import make_profile
from adroit.core.config import get_settings
from adroit.orchestrator import signal
from adroit.core.dm_state import CrossSectionKind
from adroit.experiments.base import reference_interaction
from adroit.evidence.archive import export_run,verify_bundle
from adroit.evidence.replay import replay_bundle
from adroit.evidence.runtime import capture_request,finish
from adroit.library import experimental_profiles as profiles

def test_private_profile_sources_dates_and_library_independent_replay(tmp_path,monkeypatch):
    catalog,r=fixture(tmp_path/'signal')
    sig=eligible(catalog,r)
    _,r=fixture(tmp_path/'null','null',catalog=catalog)
    null=eligible(catalog,r,'null')
    p=make_profile(catalog,sig,null)
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    request=signal.SignalRequest(experiment=sig.reference,null_modules=[null.reference],experimental_profile=p.reference,
        candidates=[signal.Candidate(label='SI20',mass_gev=20,interaction=reference_interaction(CrossSectionKind.si,1e-40,20))],
        toys=30,complementary=False)
    result=signal.run(request)
    context=capture_request(result.request)
    assert finish(context).identity==context.identity
    assert next(s for s in context.sources if s.id==p.reference).payload_sha256==p.profile_id
    from adroit.evidence.build import save
    out=tmp_path/'run'
    out.mkdir()
    path=out/'result.json'
    path.write_text(result.model_dump_json())
    save(path,'signal',context)
    archive=tmp_path/'evidence.zip'
    export_run(path,archive)
    assert verify_bundle(archive).valid
    monkeypatch.setattr(get_settings(),'experimental_library_dir',tmp_path/'absent')
    assert replay_bundle(archive).status=='matched'

def test_activation_does_not_change_an_already_pinned_context(tmp_path,monkeypatch):
    catalog,r=fixture(tmp_path/'signal')
    sig=eligible(catalog,r)
    _,r=fixture(tmp_path/'null','null',catalog=catalog)
    null=eligible(catalog,r,'null')
    p=make_profile(catalog,sig,null)
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    request=signal.SignalRequest(experiment=sig.reference,experimental_profile=p.reference,null_modules=p.null_modules)
    context=capture_request(request)
    profiles.activate(p.reference,'',confirmed=True,catalog=catalog)
    profiles.activate('',p.reference,confirmed=True,catalog=catalog)
    assert finish(context).identity==context.identity

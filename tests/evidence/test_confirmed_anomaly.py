from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
from adroit.orchestrator.anomaly_intake import interpretation,confirm
from adroit.agents.llm import FakeLLMClient
from adroit.orchestrator import runs,signal
from adroit.orchestrator.signal import Candidate,SignalRequest
from adroit.evidence.archive import export_run,verify_bundle
from adroit.evidence.replay import replay_bundle
from adroit.evidence.build import read
from tests.experimental_extraction_fixtures import TEXT,answer

def test_confirmed_anomaly_fit_and_replay_do_not_need_the_local_library(tmp_path,monkeypatch):
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(),'experimental_library_dir',tmp_path/'private')
    catalog=ExperimentalCatalog()
    file=tmp_path/'source.txt'
    file.write_text(TEXT)
    r=catalog.import_files([file],'Self-contained input')
    svc=ExperimentalExtraction(catalog)
    scope=svc.start(r.reference,1,vision=False)
    step=svc.step(scope.session_id,llm=FakeLLMClient([answer(r.sources[0].sha256)]))
    v=interpretation(step.output_revision,'signal',catalog)
    receipt=confirm(step.output_revision,'signal',v.interpretation_sha256,'Reviewer',confirmed=True,accepted_assumptions=v.assumptions,catalog=catalog)
    candidate=Candidate(label='O1_10',card_id='O1',isospin='s',mass_gev=10)
    request=SignalRequest(experiment=receipt.reference,candidates=[candidate],null_modules=[],leaders=1,toys=19)
    from adroit.evidence.runtime import capture_request
    context=capture_request(request)
    result=signal.run(request)
    folder=tmp_path/'run'
    folder.mkdir()
    runs._write(folder,result,signal.report(result),'signal','Confirmed example',evidence_context=context)
    envelope=read(folder/'result.json')
    assert next(s for s in envelope.context.sources if s.id=='experiment:'+receipt.reference).review=='unreviewed'
    assert not request.unverified_records and len(result.fits)==1
    bundle=tmp_path/'evidence.zip'
    export_run(folder/'result.json',bundle)
    assert verify_bundle(bundle).valid
    monkeypatch.setattr(get_settings(),'experimental_library_dir',tmp_path/'unavailable')
    replay=replay_bundle(bundle)
    assert replay.status=='matched',replay.model_dump()

from urllib.parse import urlencode
from types import SimpleNamespace
from nicegui.testing import User
from adroit.ui.app import build_pages
from adroit.ui import engine
from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
from adroit.orchestrator.anomaly_intake import interpretation,confirm
from adroit.agents.llm import FakeLLMClient
from tests.experimental_extraction_fixtures import TEXT,answer

def source(tmp_path):
    catalog=ExperimentalCatalog()
    file=tmp_path/'source.txt'
    file.write_text(TEXT)
    r=catalog.import_files([file],'UI source')
    return catalog,r

def extracted(tmp_path):
    catalog,r=source(tmp_path)
    svc=ExperimentalExtraction(catalog)
    scope=svc.start(r.reference,1,vision=False)
    step=svc.step(scope.session_id,llm=FakeLLMClient([answer(r.sources[0].sha256)]))
    return catalog,catalog.load(step.output_revision),scope

async def test_session_budget_gate_scope_preview_and_paid_job(user: User,tmp_path,monkeypatch):
    catalog,r=source(tmp_path)
    build_pages(tmp_path/'runs')
    await user.open('/experiments/view?'+urlencode({'reference':r.reference}))
    user.find('Text-only PDF extraction').elements.pop().value=True
    user.find('Start assisted interpretation').click()
    await user.should_see('approve this spend')
    user.find('I approve this spend').click()
    user.find('Start assisted interpretation').click()
    await user.should_see('Experimental interpretation session')
    user.find('Preview source coverage and cost ($0)').click()
    await user.should_see('Request bound $')
    calls=[]
    def launch(command,folder,title,**kwargs):
        calls.append(command)
        folder.mkdir(parents=True,exist_ok=True)
        engine.save(engine.Job(folder=str(folder),command=command,title=title,kind=command[0],status='completed',returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine,'launch',launch)
    user.find('Interpret / refine selected batch').click()
    await user.should_see('Run: Interpret experimental source batch')
    assert calls[0][:2]==['experiments','extract'] and '--budget' in calls[0]

async def test_dirty_dossier_cannot_confirm_old_interpretation(user: User,tmp_path):
    catalog,r,scope=extracted(tmp_path)
    build_pages(tmp_path/'runs')
    await user.open('/experiments/view?'+urlencode({'reference':r.reference}))
    user.find('Researcher name').elements.pop().value='Reviewer'
    user.find('Accept assumed value/approximation').click()
    user.find('I checked the interpretation').click()
    user.find('Dossier JSON').elements.pop().value=r.dossier.model_copy(update={'title':'changed'}).model_dump_json()
    user.find('Confirm this interpretation').click()
    await user.should_see('save edited dossier')
    assert not list(catalog.path('confirmations').glob('*.json'))

async def test_confirmed_anomaly_is_the_exact_track2_selection(user: User,tmp_path,monkeypatch):
    catalog,r,scope=extracted(tmp_path)
    v=interpretation(r.reference,'signal',catalog)
    receipt=confirm(r.reference,'signal',v.interpretation_sha256,'Reviewer',confirmed=True,accepted_assumptions=v.assumptions,catalog=catalog)
    build_pages(tmp_path/'runs')
    await user.open('/new/track2?'+urlencode({'anomaly':receipt.reference}))
    calls=[]
    def launch(command,folder,title,**kwargs):
        calls.append(command)
        folder.mkdir(parents=True,exist_ok=True)
        engine.save(engine.Job(folder=str(folder),command=command,title=title,kind=command[0],status='completed',returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine,'launch',launch)
    user.find('Fit, combine and rank').click()
    await user.should_see('Run:')
    assert calls[0][calls[0].index('--experiment')+1]==receipt.reference and '--unverified' not in calls[0]

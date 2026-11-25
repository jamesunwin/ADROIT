"""Review is mandatory; corrections are immutable and budgets survive restarts."""
import json
import pytest
import yaml
from PIL import Image

from adroit.library.personal import Catalog
from adroit.orchestrator.model_intake import Intake
from adroit.parameter_space.simplified import model
from adroit.orchestrator.model_approval import model_identity
from adroit.agents.llm import FakeLLMClient
from adroit.agents.model_intake import Interpretation

def approve(service,s,d,index=0):
    c=d.choices[index]
    return service.approve(s.session_id,d.step_id,index,confirmed=True,expected_model_hash=model_identity(c.spec),tex=c.tex)

def test_typed_correction_retains_model_identity_as_new_revision(tmp_path):
    service=Intake(Catalog(tmp_path/'library'))
    s=service.start()
    original=model('vector',10,125,.001,.25)
    d=service.step(s.session_id,'typed',yaml.safe_dump(original.model_dump(mode='json')))
    first=approve(service,s,d)
    updated=model('vector',12,125,.002,.25)
    next_=service.step(s.session_id,'typed',yaml.safe_dump(updated.model_dump(mode='json')),parent_step=d.step_id)
    second=approve(service,s,next_)
    assert first.model_id==second.model_id and second.parent_revision==first.revision_id
    assert service.load(s.session_id,d.step_id).choices[0].spec==original
    assert service.catalog.load(first.reference).spec==original
    assert second.spec==updated and len(service.catalog.list())==2

def test_edited_tex_or_model_requires_a_new_review(tmp_path):
    service=Intake(Catalog(tmp_path/'library'))
    s=service.start()
    d=service.step(s.session_id,'typed',yaml.safe_dump(model('vector',10,125).model_dump(mode='json')))
    c=d.choices[0]
    with pytest.raises(ValueError,match='review the transcription'):
        service.approve(s.session_id,d.step_id,0,confirmed=False,expected_model_hash=model_identity(c.spec),tex=c.tex)
    with pytest.raises(ValueError,match='edited model or TeX'):
        service.approve(s.session_id,d.step_id,0,confirmed=True,expected_model_hash=model_identity(c.spec),tex=c.tex+' changed')

def test_screenshot_is_attached_and_transcription_and_original_are_retained(tmp_path):
    source=tmp_path/'lagrangian.png'
    Image.new('RGB',(400,200),'white').save(source)
    service=Intake(Catalog(tmp_path/'library'))
    s=service.start(1)
    spec=model('vector',10,125,.001,.25)
    fake=FakeLLMClient([Interpretation(transcription='source transcription',spec=spec,ambiguities=['verify gamma index'])])
    d=service.step(s.session_id,'image',source=source,llm=fake)
    assert fake.calls[0]['images'] and d.transcription=='source transcription'
    r=approve(service,s,d)
    assert r.provenance['ambiguities_reviewed']==['verify gamma index']
    assert any(a.suffix=='.png' for a in r.sources)
    assert r.spec==spec

def test_tex_refinement_preserves_previous_model_in_prompt(tmp_path):
    service=Intake(Catalog(tmp_path/'library'))
    s=service.start(1)
    original=model('vector',10,125,.001,.25)
    d=service.step(s.session_id,'typed',yaml.safe_dump(original.model_dump(mode='json')))
    updated=model('vector',10,125,.002,.25)
    fake=FakeLLMClient([Interpretation(transcription='edited TeX',spec=updated)])
    refined=service.step(s.session_id,'tex','g_chi=0.002',parent_step=d.step_id,llm=fake)
    assert 'Previous canonical model' in fake.calls[0]['messages'][0]['content']
    assert refined.choices[0].spec==updated and service.load(s.session_id,d.step_id).choices[0].spec==original

def test_session_budget_restores_settlement_and_uncertain_reservation(tmp_path):
    from adroit.agents.budget import BudgetExceeded
    service=Intake(Catalog(tmp_path/'library'))
    s=service.start(.5)
    rows=[{'id':'a','state':'reserved','provider':'anthropic','reserved_usd':.2},
          {'id':'a','state':'settled','cost_usd':.1},
          {'id':'b','state':'reserved','provider':'anthropic','reserved_usd':.25},
          {'id':'b','state':'billing_uncertain'}]
    (service.folder(s.session_id)/'paid.jsonl').write_text('\n'.join(json.dumps(x) for x in rows)+'\n')
    restarted=Intake(service.catalog)
    status=restarted.budget_status(s.session_id)
    assert status['spent']==.1 and status['reserved_uncertain']==.25
    assert status['remaining']==pytest.approx(.15)
    with pytest.raises(BudgetExceeded):
        restarted.account(s).reserve('anthropic',.2)
    manifest=service.folder(s.session_id)/'session.json'
    data=json.loads(manifest.read_text())
    data['budget']=5
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='configuration was modified'):
        restarted.session(s.session_id)


def test_negative_journal_cost_cannot_refund_a_paid_session(tmp_path):
    service=Intake(Catalog(tmp_path/'library'))
    s=service.start(.5)
    ledger=service.folder(s.session_id)/'paid.jsonl'
    ledger.write_text(json.dumps({'id':'a','state':'reserved','provider':'anthropic','reserved_usd':.2})+'\n'+
                      json.dumps({'id':'a','state':'settled','cost_usd':-.1})+'\n')
    with pytest.raises(ValueError,match='cost_usd is not a finite, nonnegative amount'):   # read_ledger's (CA-06)
        service.budget_status(s.session_id)

def test_manual_edit_retains_source_zero_and_contract(tmp_path):
    from pathlib import Path
    service=Intake(Catalog(tmp_path/'library'))
    s=service.start()
    d=service.step(s.session_id,'typed',Path('docs/examples/complete_scalar_running.yaml').read_text())
    r=approve(service,s,d)
    assert r.spec.scalar_potential and r.spec.scalar_running and 'potential' in r.tex


def test_tex_field_content_uses_deterministic_general_lagrangian(tmp_path):
    from adroit.core.model_spec import ModelSpec
    service=Intake(Catalog(tmp_path/'library'))
    s=service.start(1)
    spec=ModelSpec.model_validate({'name':'S','fields':[{'name':'S','role':'dark_matter','spin':0,
        'self_conjugate':True,'dark_parity':-1,'mass_gev':70}]})
    fake=FakeLLMClient([Interpretation(transcription='real singlet S, Z2 odd',spec=spec,representation='field_content')])
    d=service.step(s.session_id,'tex','S is a real singlet, Z2 odd',llm=fake)
    assert d.choices[0].spec.terms and d.choices[0].spec.couplings
    assert all(c.value is None for c in d.choices[0].spec.couplings)
    assert not d.choices[0].applicability['numerically_declared']


def test_step_and_draft_print_the_hash_that_approve_needs_live_check_l3(tmp_path,monkeypatch):
    """Live check L3: `approve --expected-hash` needed model_identity(spec), which no command printed."""
    import re
    from typer.testing import CliRunner
    from adroit.orchestrator import catalog_cli,cli
    service=Intake(Catalog(tmp_path/'library'))
    monkeypatch.setattr(catalog_cli,'Intake',lambda:service)
    s=service.start()
    source=tmp_path/'model.yaml'
    source.write_text(yaml.safe_dump(model('vector',10,125,.001,.25).model_dump(mode='json')))
    out=CliRunner().invoke(cli.app,['models','step',s.session_id,'--kind','typed','--text',source.read_text(),'--out',str(tmp_path/'run')])
    assert out.exit_code==0,out.output
    identity=re.search(r'model identity: ([0-9a-f]{64})',out.output).group(1)
    draft=service.steps(s.session_id)[-1]
    assert identity==model_identity(draft.choices[0].spec) and identity in (tmp_path/'run/report.md').read_text()
    assert '*Read as found.*' in (tmp_path/'run/report.md').read_text()       # a diagnostic output (2026-11-03)
    shown=CliRunner().invoke(cli.app,['models','draft',s.session_id,draft.step_id])
    assert f'--expected-hash {identity} --confirmed' in shown.output
    approved=CliRunner().invoke(cli.app,['models','approve',s.session_id,draft.step_id,'--expected-hash',identity,'--confirmed'])
    assert approved.exit_code==0 and approved.output.strip().startswith('catalog:')


def test_models_raise_cap_and_a_budget_stop_names_it(tmp_path,monkeypatch):
    from typer.testing import CliRunner
    from adroit.agents.budget import BudgetExceeded
    from adroit.orchestrator import catalog_cli,cli
    service=Intake(Catalog(tmp_path/'library'))
    monkeypatch.setattr(catalog_cli,'Intake',lambda:service)
    s=service.start(.5)
    refused=CliRunner().invoke(cli.app,['models','raise-cap',s.session_id,'--budget','.8'])
    assert refused.exit_code==2 and service.session(s.session_id).budget==.5
    out=CliRunner().invoke(cli.app,['models','raise-cap',s.session_id,'--budget','.8','--confirmed'])
    assert out.exit_code==0 and 'cap raised from $0.50 to $0.80' in out.output and service.session(s.session_id).budget==.8
    def stop(*a,**k):raise BudgetExceeded(.3,.8,.6)
    monkeypatch.setattr(service,'step',stop)
    out=CliRunner().invoke(cli.app,['models','step',s.session_id,'--kind','idea','--text','x','--budget','.8'])
    assert out.exit_code==3 and f'adroit models raise-cap {s.session_id} --budget 0.90 --confirmed' in out.output

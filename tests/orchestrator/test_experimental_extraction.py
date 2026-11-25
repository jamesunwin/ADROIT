import json
import pytest
from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator.experimental_extraction import ExperimentalExtraction,convert,printed_numbers
from adroit.core.experimental_input import ExperimentalClaim,ExperimentalResult,SourceLocator
from adroit.agents.experimental_extraction import ExtractionAnswer
from adroit.agents.llm import FakeLLMClient
from tests.experimental_extraction_fixtures import TEXT,answer

def setup(tmp_path):
    catalog=ExperimentalCatalog(tmp_path/'private')
    source=tmp_path/'source.txt'
    source.write_text(TEXT)
    r=catalog.import_files([source],'Known source')
    svc=ExperimentalExtraction(catalog)
    scope=svc.start(r.reference,2,vision=False)
    return catalog,r,svc,scope

def test_extraction_preserves_sources_records_coverage_and_durable_budget(tmp_path):
    catalog,r,svc,s=setup(tmp_path)
    preview=svc.preview(s.session_id)
    assert preview['request_bound_usd']>0 and len(preview['unread'])==1
    step=svc.step(s.session_id,llm=FakeLLMClient([answer(r.sources[0].sha256)]))
    updated=catalog.load(step.output_revision)
    assert not step.evidence_problems and updated.experiment_id==r.experiment_id and updated.parent_revision==r.revision_id
    assert updated.dossier.results[0].claims[4].value==[8.6,10.4,14.2]
    assert updated.source_review=='unreviewed' and updated.activation=='inactive' and catalog.load(r.reference)==r
    assert not svc.preview(s.session_id)['unread']
    with pytest.raises(ValueError,match='already interpreted'):
        svc.step(s.session_id,llm=FakeLLMClient([]))
    manifest=svc.budgets.folder(s.session_id)/'session.json'
    data=json.loads(manifest.read_text())
    data['budget']=9
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='modified'):
        svc.scope(s.session_id)

def test_bad_numerical_quote_and_foreign_source_do_not_enter_trusted_dossier(tmp_path):
    catalog,r,svc,s=setup(tmp_path)
    a=answer(r.sources[0].sha256)
    a.results[0].claims[4].value=[9.9]
    a.results[0].claims[0].sources[0].asset_sha256='1'*64
    step=svc.step(s.session_id,llm=FakeLLMClient([a]))
    updated=catalog.load(step.output_revision)
    claims={c.key:c for c in updated.dossier.results[0].claims}
    assert claims['events'].status=='unextracted' and claims['events'].value is None
    assert claims['target'].status=='unextracted' and len(step.evidence_problems)==2

def test_conflicts_are_visible_and_explicit_refinement_creates_new_revision(tmp_path):
    catalog,r,svc,s=setup(tmp_path)
    first=svc.step(s.session_id,llm=FakeLLMClient([answer(r.sources[0].sha256)]))
    # Explicitly read another batch selection on a new scoped session to compare sources.
    a=answer(r.sources[0].sha256)
    a.results[0].claims[6].value=.5
    refined=svc.step(s.session_id,instructions='Use the alternative 0.5 background estimate',llm=FakeLLMClient([a]))
    assert catalog.load(refined.output_revision).dossier.results[0].claims[6].value==.5
    assert catalog.load(first.output_revision).dossier.results[0].claims[6].value==.4
    from adroit.orchestrator.experimental_extraction import merge_claims
    conflict=merge_claims([answer(r.sources[0].sha256).results[0].claims[6]],[a.results[0].claims[6]])[0]
    assert conflict.status=='conflicting' and conflict.value=={'previous':.4,'proposal':.5}

def test_conversions_are_deterministic_and_do_not_convert_electron_recoil_scale():
    claim=ExperimentalClaim(key='exposure',category='detector',value=.1,units='tonne year',requested_unit='kg day',
                            status='assumed',note='Explicit investigator assumption')
    result=convert(claim)
    assert result.value==36525 and result.units=='kg day'
    with pytest.raises(ValueError):
        convert(claim.model_copy(update={'units':'keVee','requested_unit':'keVnr'}))

def test_table_bin_centres_are_not_accepted_as_events(tmp_path):
    from adroit.orchestrator.experimental_extraction import checked_claim,source_units
    catalog=ExperimentalCatalog(tmp_path/'private')
    source=tmp_path/'bins.csv'
    source.write_text('bin_center_keVnr,counts\n8.6,2\n')
    r=catalog.import_files([source],'Histogram')
    c=ExperimentalClaim(key='events',category='observation',value=[8.6],units='keVnr',status='sourced',
        sources=[SourceLocator(asset_sha256=r.sources[0].sha256,method='table',row=1,column='bin_center_keVnr')])
    result,issues=checked_claim(catalog,r,c,source_units(catalog,r.reference,False))
    assert result.status=='unextracted' and 'not unbinned' in issues[0]


def test_a_trimmed_refinement_sends_the_compacted_prior_and_records_it(tmp_path):
    """Live check L6: refinement reservations grow with the prior dossier; --trim sends it without excerpts or notes."""
    from adroit.agents.experimental_extraction import compact, messages
    catalog,r,svc,s=setup(tmp_path)
    svc.step(s.session_id,llm=FakeLLMClient([answer(r.sources[0].sha256)]))
    plan=svc.preview(s.session_id,0,'refine')
    assert 0<plan['trimmed_request_bound_usd']<plan['request_bound_usd']
    a=answer(r.sources[0].sha256)
    a.results[0].claims[6].value=.5
    fake=FakeLLMClient([a])
    refined=svc.step(s.session_id,instructions='Use the 0.5 background estimate',llm=fake,trimmed=True)
    body=json.loads(fake.calls[0]['messages'][0]['content'])
    assert 'excerpt' not in json.dumps(body['prior_dossier']) and 'compacted' in body['note']
    assert refined.trimmed_prior and catalog.load(refined.output_revision).dossier.results[0].claims[6].value==.5
    assert [step.trimmed_prior for step in svc.steps(s.session_id)]==[False,True]          # receipts keep integrity
    prior=catalog.load(refined.input_revision).dossier.model_dump(mode='json')
    assert any(loc['excerpt'] for c in prior['results'][0]['claims'] for loc in c['sources'])  # the store is intact
    assert compact({'a':'','b':[{'excerpt':'x','page':3}],'notes':['n']})=={'b':[{'page':3}]}
    assert 'note' not in json.loads(messages([],prior)[0]['content'])


def test_a_session_cap_is_raised_only_with_confirmation_and_is_recorded(tmp_path):
    catalog,r,svc,s=setup(tmp_path)
    with pytest.raises(ValueError,match='explicit confirmation'):
        svc.budgets.raise_cap(s.session_id,3,confirmed=False)
    with pytest.raises(ValueError,match='must exceed'):
        svc.budgets.raise_cap(s.session_id,1.5,confirmed=True)
    raised=svc.budgets.raise_cap(s.session_id,3,confirmed=True,reason='refinement needs more')
    assert raised.budget==3 and svc.budgets.session(s.session_id).budget==3 and svc.budgets.budget_status(s.session_id)['cap']==3
    assert [(c.previous,c.new,c.reason) for c in raised.cap_history]==[(2,3,'refinement needs more')]
    ledger=(svc.budgets.folder(s.session_id)/'paid.jsonl').read_text()
    assert '"state": "cap_raised"' in ledger and svc.budgets.account(raised).cap==3
    manifest=svc.budgets.folder(s.session_id)/'session.json'
    data=json.loads(manifest.read_text())
    data['cap_history'][0]['new']=9
    data['budget']=9
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='modified'):
        svc.budgets.session(s.session_id)

def test_a_printed_percentage_is_also_its_fraction(tmp_path):
    """A limit contract's confidence level is a fraction and papers print it as a percentage: the live discovery
    pilot (2026-10-18) lost every limit it read because 0.95 was refused against "at 95% CL". A level the cited text
    does not print is still refused."""
    assert {95.,.95,.25,2.2e-46,.9}<=set(printed_numbers('a limit of 0.33 (0.25) at 95% CL; 2.2× 10−46 cm2, 90 per cent'))
    assert .95 not in printed_numbers('0.33 at 95 GeV') and .5 not in printed_numbers('50 events')
    catalog=ExperimentalCatalog(tmp_path/'private')
    source=tmp_path/'paper.txt'
    source.write_text('An observed (expected) upper limit of 0.33 (0.25), at 95% confidence level, is set on B(H→inv).')
    r=catalog.import_files([source],'Known source')
    svc=ExperimentalExtraction(catalog)
    s=svc.start(r.reference,2,vision=False)
    excerpt='upper limit of 0.33 (0.25), at 95% confidence level'
    def claim(key,value):
        return ExperimentalClaim(key=key,category='limit',value=value,units='dimensionless',status='sourced',
                                 sources=[SourceLocator(asset_sha256=r.sources[0].sha256,method='text',excerpt=excerpt)])
    a=ExtractionAnswer(results=[ExperimentalResult(result_id='hinv',kind='limit',claims=[
        claim('limit_contract',{'confidence_level':.95,'value':.33}),claim('expected_limit',{'confidence_level':.9,'value':.25})])],
        explanation='The printed observed limit and its level.')
    step=svc.step(s.session_id,llm=FakeLLMClient([a]))
    claims={c.key:c for c in catalog.load(step.output_revision).dossier.results[0].claims}
    assert claims['limit_contract'].status=='sourced' and claims['limit_contract'].value=={'confidence_level':.95,'value':.33}
    assert claims['expected_limit'].status=='unextracted' and step.evidence_problems==[
        'expected_limit: numerical value absent from cited raw evidence']

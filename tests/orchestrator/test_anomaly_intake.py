import pytest
from adroit.orchestrator.anomaly_intake import interpretation,confirm,load_confirmation,readiness
from adroit.agents.llm import FakeLLMClient
from tests.orchestrator.test_experimental_extraction import setup
from tests.experimental_extraction_fixtures import answer

def stored(tmp_path):
    catalog,r,svc,s=setup(tmp_path)
    step=svc.step(s.session_id,llm=FakeLLMClient([answer(r.sources[0].sha256)]))
    return catalog,catalog.load(step.output_revision)

def test_confirmation_requires_exact_review_and_assumptions_and_remains_unreviewed(tmp_path):
    catalog,r=stored(tmp_path)
    value=interpretation(r.reference,'signal',catalog)
    assert value.record and not value.blockers and not value.record.verified_by
    with pytest.raises(ValueError):
        confirm(r.reference,'signal','bad','Reviewer',confirmed=True,accepted_assumptions=value.assumptions,catalog=catalog)
    with pytest.raises(ValueError):
        confirm(r.reference,'signal',value.interpretation_sha256,'Reviewer',confirmed=False,accepted_assumptions=value.assumptions,catalog=catalog)
    with pytest.raises(ValueError):
        confirm(r.reference,'signal',value.interpretation_sha256,'Reviewer',confirmed=True,accepted_assumptions=[],catalog=catalog)
    receipt=confirm(r.reference,'signal',value.interpretation_sha256,'Reviewer',confirmed=True,accepted_assumptions=value.assumptions,catalog=catalog)
    assert readiness(receipt.reference,catalog)==receipt and receipt.source_review=='unreviewed'

def test_bins_limits_missing_response_energy_scale_and_zero_background_are_blocked(tmp_path):
    catalog,r=stored(tmp_path)
    for kind in ('binned','limit','likelihood'):
        dossier=r.dossier.model_copy(deep=True)
        dossier.results[0].kind=kind
        revised=catalog.save(dossier,r.sources,r.ingestions,r.reference)
        value=interpretation(revised.reference,'signal',catalog)
        assert value.record is None and value.blockers
    for key,value in [('energy_scale','keVee'),('exposure_selection','after_selection'),('background_count',0),('resolution',True)]:
        dossier=r.dossier.model_copy(deep=True)
        next(c for c in dossier.results[0].claims if c.key==key).value=value
        revised=catalog.save(dossier,r.sources,r.ingestions,r.reference)
        assert interpretation(revised.reference,'signal',catalog).blockers

def test_source_modification_invalidates_confirmed_handoff(tmp_path):
    catalog,r=stored(tmp_path)
    v=interpretation(r.reference,'signal',catalog)
    receipt=confirm(r.reference,'signal',v.interpretation_sha256,'Reviewer',confirmed=True,accepted_assumptions=v.assumptions,catalog=catalog)
    catalog.asset_path(r.sources[0]).write_text('changed source')
    with pytest.raises(ValueError):
        load_confirmation(receipt.reference,catalog)


def test_an_assumed_value_is_accepted_only_as_displayed_with_its_value(tmp_path):
    """R1: blanket acceptance by key is not enough for an assumed value; the researcher accepts key=value units."""
    from adroit.orchestrator.anomaly_intake import acknowledgements
    catalog,r=stored(tmp_path)
    dossier=r.dossier.model_copy(deep=True)
    claim=next(c for c in dossier.results[0].claims if c.key=='exposure')
    claim.status='assumed'
    claim.sources=[]
    claim.note='researcher: the full exposure before cuts'
    revised=catalog.save(dossier,r.sources,r.ingestions,r.reference)
    value=interpretation(revised.reference,'signal',catalog)
    tokens=acknowledgements(revised.reference,'signal',catalog)
    assert 'exposure' in value.assumptions and f'exposure={claim.value} kg day' in tokens
    with pytest.raises(ValueError,match='exposure='):
        confirm(revised.reference,'signal',value.interpretation_sha256,'Reviewer',confirmed=True,
                accepted_assumptions=value.assumptions,catalog=catalog)
    receipt=confirm(revised.reference,'signal',value.interpretation_sha256,'Reviewer',confirmed=True,
                    accepted_assumptions=tokens,catalog=catalog)
    assert f'exposure={claim.value} kg day' in receipt.accepted_assumptions


def test_the_interpretation_command_lists_what_confirmation_must_accept(tmp_path,monkeypatch):
    import json
    from typer.testing import CliRunner
    from adroit.orchestrator import anomaly_intake,cli
    catalog,r=stored(tmp_path)
    monkeypatch.setattr(anomaly_intake,'ExperimentalCatalog',lambda *a,**k:catalog)
    out=CliRunner().invoke(cli.app,['experiments','interpretation',r.reference,'--result','signal'])
    assert out.exit_code==0,out.output
    assert json.loads(out.output)['required_acknowledgements']==['historical_unbinned_fidelity_B']

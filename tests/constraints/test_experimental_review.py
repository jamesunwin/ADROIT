import json
import pytest
from adroit.constraints.experimental_review import packet,approve,validate,bind,load_bound,CHECKLIST,plot_packet
from tests.private_limit_fixtures import fixture,eligible

def test_review_and_numerical_validation_are_separate_source_bound_receipts(tmp_path):
    catalog,r=fixture(tmp_path)
    value=packet(r.reference,'limit',catalog=catalog)
    with pytest.raises(ValueError):
        approve(r.reference,'limit',value['scientific_sha256'],'Reviewer',confirmed=False,checks=CHECKLIST,catalog=catalog)
    with pytest.raises(ValueError):
        approve(r.reference,'limit','bad','Reviewer',confirmed=True,checks=CHECKLIST,catalog=catalog)
    review=approve(r.reference,'limit',value['scientific_sha256'],'Synthetic reviewer',confirmed=True,checks=CHECKLIST,catalog=catalog)
    assert review.reviewed_at and r.source_review=='unreviewed' and r.activation=='inactive'
    validation=validate(r.reference,'limit',.02,value['scientific_sha256'],catalog)
    assert validation.passed and max(validation.relative_errors)<1e-12
    result=bind(r.reference,'limit',review.review_id,validation.validation_id,catalog)
    assert load_bound(result.reference,catalog)==result
    catalog.asset_path(r.sources[0]).write_text('changed')
    with pytest.raises(ValueError):
        load_bound(result.reference,catalog)

def test_failed_or_same_asset_validation_cannot_enable_limit(tmp_path):
    catalog,r=fixture(tmp_path)
    dossier=r.dossier.model_copy(deep=True)
    wrong=[[10,1e-44],[15,1.5e-44],[40,4e-44]]
    dossier.results[0].claims[1].value={'points':wrong,'lineage':[
        {'derivation':'published_table','document':'wrong_reference.json','row':i,'mass_column':'mass',
         'limit_column':'limit'} for i in (1,2,3)]}
    table={'independent_variables':[{'header':{'name':'mass'},'values':[{'value':x} for x,_ in wrong]}],
           'dependent_variables':[{'header':{'name':'limit'},'values':[{'value':y} for _,y in wrong]}]}
    source=catalog.asset_bytes('wrong_reference.json',json.dumps(table).encode(),'data')
    # Parse the independently declared wrong anchors, preserving their actual bytes.
    from adroit.retrieval.experimental_ingestion import ingest
    parsed=ingest(catalog.asset_path(source),source)
    payload=catalog.asset_bytes('wrong_ingestion.json',parsed.model_dump_json().encode(),'ingestion')
    dossier.results[0].claims[1].sources[0].asset_sha256=source.sha256
    dossier.results[0].claims[1].sources[0].excerpt=catalog.asset_path(source).read_text()
    retrieved=[{'url':'https://www.hepdata.net/download/table/ins0000001/limit/1/json','sha256':source.sha256}]
    updated=catalog.save(dossier,[*r.sources,source],[*r.ingestions,payload],r.reference,provenance={'retrieved':retrieved})
    value=packet(updated.reference,'limit',catalog=catalog)
    proof=validate(updated.reference,'limit',.02,value['scientific_sha256'],catalog)
    assert not proof.passed
    review=approve(updated.reference,'limit',value['scientific_sha256'],'Synthetic',confirmed=True,checks=CHECKLIST,catalog=catalog)
    with pytest.raises(ValueError,match='failed'):
        bind(updated.reference,'limit',review.review_id,proof.validation_id,catalog)

def test_changed_confidence_benchmark_or_source_metadata_invalidates_review(tmp_path):
    catalog,r=fixture(tmp_path)
    bound=eligible(catalog,r)
    for change in ({'confidence_level':.9},{'benchmark':'isospin_violating'}, {'selection':'expected'}):
        dossier=r.dossier.model_copy(deep=True)
        dossier.results[0].claims[0].value.update(change)
        updated=catalog.save(dossier,r.sources,r.ingestions,r.reference)
        with pytest.raises(ValueError):
            bind(updated.reference,'limit',bound.review.review_id,bound.validation.validation_id,catalog)
    data=r.dossier.model_copy(update={'references':['changed publication identity']})
    updated=catalog.save(data,r.sources,r.ingestions,r.reference)
    assert packet(updated.reference,'limit',catalog=catalog)['scientific_sha256']!=bound.scientific_sha256

def test_plot_preserves_declared_source_axes_and_independent_anchors(tmp_path):
    catalog,r=fixture(tmp_path)
    out=plot_packet(r.reference,'limit',tmp_path/'plots',catalog)
    from pathlib import Path
    assert Path(out['plot']).is_file() and out['source_overlay'] is None

def test_calibrated_overlay_and_unrelated_result_edit_preserve_scoped_review(tmp_path):
    import matplotlib.pyplot as plt
    from adroit.retrieval.experimental_ingestion import ingest
    from adroit.core.experimental_input import ExperimentalResult
    catalog,r=fixture(tmp_path)
    fig,ax=plt.subplots(figsize=(8,5),dpi=100)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(8,50)
    ax.set_ylim(.8e-43,5e-43)
    ax.plot([10,20,40],[1e-43,2e-43,4e-43])
    fig.canvas.draw()
    x0,y0,w,h=ax.bbox.bounds
    width,height=fig.canvas.get_width_height()
    path=tmp_path/'source_panel.png'
    fig.savefig(path)
    plt.close(fig)
    asset=catalog.asset(path,'image')
    parsed=ingest(catalog.asset_path(asset),asset)
    info=catalog.asset_bytes('panel_ingestion.json',parsed.model_dump_json().encode(),'ingestion')
    dossier=r.dossier.model_copy(deep=True)
    dossier.results[0].claims[0].value['figure_axes']={'asset_sha256':asset.sha256,'pixel_box':[x0,height-y0-h,x0+w,height-y0],
        'x_range':[8,50],'y_range':[.8e-43,5e-43]}
    revised=catalog.save(dossier,[*r.sources,asset],[*r.ingestions,info],r.reference)
    rendered=plot_packet(revised.reference,'limit',tmp_path/'overlay',catalog)
    from pathlib import Path
    assert Path(rendered['source_overlay']).is_file()
    bound=eligible(catalog,revised)
    other=dossier.model_copy(deep=True)
    other.results.append(ExperimentalResult(result_id='unrelated',kind='reference'))
    updated=catalog.save(other,[*r.sources,asset],[*r.ingestions,info],revised.reference)
    assert packet(updated.reference,'limit',catalog=catalog)['scientific_sha256']==bound.scientific_sha256

def test_complete_event_source_review_is_distinct_from_interpretation_confirmation(tmp_path,monkeypatch):
    from tests.orchestrator.test_anomaly_intake import stored
    from adroit.orchestrator.anomaly_intake import interpretation,confirm
    from adroit.experiments.registry import load_module
    from adroit.core.config import get_settings
    from adroit.evidence.runtime import capture
    catalog,r=stored(tmp_path)
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    value=interpretation(r.reference,'signal',catalog)
    receipt=confirm(r.reference,'signal',value.interpretation_sha256,'Synthetic',confirmed=True,accepted_assumptions=value.assumptions,catalog=catalog)
    assert not load_module(receipt.reference).verified
    data=packet(r.reference,'signal',catalog=catalog)
    approve(r.reference,'signal',data['scientific_sha256'],'Synthetic source checker',confirmed=True,checks=CHECKLIST,catalog=catalog)
    assert load_module(receipt.reference).verified
    context=capture(experiments=[receipt.reference])
    src=next(s for s in context.sources if s.id=='experiment:'+receipt.reference)
    assert src.review=='verified' and src.reviewed_by=='Synthetic source checker'

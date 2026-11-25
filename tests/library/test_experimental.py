import json
from datetime import timezone
import pytest
from typer.testing import CliRunner

from adroit.core.experimental_input import ExperimentalClaim,SourceLocator
from adroit.library.experimental import ExperimentalCatalog


def table(tmp_path):
    file=tmp_path/'limit.csv'
    file.write_text('m_GeV,sigma_cm2\n10,1e-43\n20,0\n')
    return file


def test_private_revisions_dates_and_sources_are_immutable(tmp_path):
    catalog=ExperimentalCatalog(tmp_path/'private')
    first=catalog.import_files([table(tmp_path)],'First limit')
    old=catalog.path(f'experiments/{first.experiment_id}/{first.revision_id}.json').read_bytes()
    second=catalog.save(first.dossier.model_copy(update={'title':'Updated description'}),first.sources,first.ingestions,first.reference)
    assert first.experiment_id==second.experiment_id and second.parent_revision==first.revision_id
    assert second.created_at>=first.created_at and first.created_at.tzinfo==timezone.utc
    assert catalog.load(first.reference)==first and catalog.list('Updated')==[second]
    assert old==catalog.path(f'experiments/{first.experiment_id}/{first.revision_id}.json').read_bytes()
    assert first.activation=='inactive' and first.source_review=='unreviewed' and first.adapter_validation=='not_validated'
    assert all(c.status=='unextracted' and c.value is None for c in first.dossier.claims)
    assert 'No physics calculation performed' in catalog.report(first.reference)
    with pytest.raises(ValueError):
        catalog.load(first.reference.split('@')[0])


def test_claim_locators_need_actual_selected_pages_rows_and_columns(tmp_path):
    from tests.experimental_fixtures import paper
    catalog=ExperimentalCatalog(tmp_path/'private')
    r=catalog.import_files([paper(tmp_path/'paper.pdf'),table(tmp_path)],'test',preview_pages=[])
    claim=ExperimentalClaim(key='exposure',category='detector',value=1000,units='kg day',status='sourced',
                            sources=[SourceLocator(asset_sha256=r.sources[0].sha256,page=1,excerpt='1000 kg day')])
    dossier=r.dossier.model_copy(update={'claims':[claim]})
    catalog.save(dossier,r.sources,r.ingestions,r.reference)
    for loc in [dict(page=3),dict(page=1,excerpt='invented'),dict(page=1,region=(0,0,700,400))]:
        bad=claim.model_copy(update={'sources':[SourceLocator(asset_sha256=r.sources[0].sha256,**loc)]})
        with pytest.raises(ValueError):
            catalog.save(dossier.model_copy(update={'claims':[bad]}),r.sources,r.ingestions,r.reference)
    bad=claim.model_copy(update={'sources':[SourceLocator(asset_sha256=r.sources[1].sha256,row=3,column='wrong')]})
    with pytest.raises(ValueError):
        catalog.save(dossier.model_copy(update={'claims':[bad]}),r.sources,r.ingestions)
    with pytest.raises(ValueError):
        ExperimentalClaim(key='a',category='limit',status='sourced',value=1)


def test_corruption_credential_symlink_and_path_traversal_are_refused(tmp_path):
    catalog=ExperimentalCatalog(tmp_path/'private')
    file=table(tmp_path)
    r=catalog.import_files([file],'test')
    stored=catalog.asset_path(r.sources[0])
    stored.write_text('changed')
    with pytest.raises(ValueError):
        catalog.load(r.reference)
    secret=tmp_path/'.env'
    secret.write_text('do not read')
    link=tmp_path/'link.csv'
    link.symlink_to(file)
    for path in [secret,link,tmp_path]:
        with pytest.raises(ValueError):
            catalog.asset(path,'data')
    for path in ['../../outside','/etc/passwd']:
        with pytest.raises(ValueError):
            catalog.path(path)
    with pytest.raises(ValueError):
        catalog.asset_bytes('wrong.pdf',b'not a pdf','paper')


def test_derived_ingestion_corruption_does_not_upgrade_source(tmp_path):
    catalog=ExperimentalCatalog(tmp_path/'private')
    r=catalog.import_files([table(tmp_path)],'test')
    path=catalog.asset_path(r.ingestions[0])
    body=json.loads(path.read_text())
    body['source_sha256']='1'*64
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError):
        catalog.load(r.reference)


def test_same_bytes_with_conflicting_formats_are_not_silently_deduplicated(tmp_path):
    catalog=ExperimentalCatalog(tmp_path/'private')
    csv=table(tmp_path)
    tsv=tmp_path/'limit.tsv'
    tsv.write_bytes(csv.read_bytes())
    with pytest.raises(ValueError,match='conflicting declared formats'):
        catalog.import_files([csv,tsv],'ambiguous formats')


def test_cli_import_edit_and_report_remain_private_and_inactive(tmp_path,monkeypatch):
    from adroit.core.config import get_settings
    from adroit.orchestrator.cli import app
    monkeypatch.setattr(get_settings(),'experimental_library_dir',tmp_path/'private')
    runner=CliRunner()
    out=tmp_path/'out'
    run=runner.invoke(app,['experiments','import',str(table(tmp_path)),'--title','My search','--out',str(out)])
    assert run.exit_code==0,run.output
    ref=run.output.strip()
    catalog=ExperimentalCatalog()
    r=catalog.load(ref)
    assert 'Revision saved (UTC)' in (out/'report.md').read_text()
    assert '*Read as found.*' in (out/'report.md').read_text() and ref in (out/'report.md').read_text()
    body=r.dossier.model_copy(update={'analysis':'corrected channel'})
    file=tmp_path/'dossier.json'
    file.write_text(body.model_dump_json())
    changed=runner.invoke(app,['experiments','revise',ref,'--dossier',str(file)])
    assert changed.exit_code==0,changed.output
    assert catalog.load(changed.output.strip()).parent_revision==r.revision_id
    for command in [['list'],['show',ref],['source',ref],['report',ref]]:
        assert runner.invoke(app,['experiments',*command]).exit_code==0
    assert r.activation=='inactive'


def test_structured_and_image_sources_are_not_interpreted(tmp_path):
    from PIL import Image
    catalog=ExperimentalCatalog(tmp_path/'private')
    data=tmp_path/'data.json'
    data.write_text('{"counts":[0,1],"units":"unknown"}')
    image=tmp_path/'figure.png'
    Image.new('RGB',(200,100),'white').save(image)
    r=catalog.import_files([data,image],'unsupported figure')
    items=[catalog.ingestion(a) for a in r.ingestions]
    assert items[0].structured['counts']==[0,1] and items[1].kind=='image'
    assert all(c.value is None for c in r.dossier.claims)

"""Immutable catalog identity, sources and both-track pinned reuse."""
import json
import pytest
import yaml

from adroit.library.personal import Catalog
from adroit.orchestrator import ideas
from adroit.orchestrator.model_approval import select_model
from adroit.parameter_space.simplified import model

def save(catalog,spec=None,**kwargs):
    spec=spec or model('vector',10,125,.001,.25)
    selected,approval=select_model(ideas.from_lagrangian(spec))
    return catalog.save(selected,approval,**kwargs)

def test_revisions_pin_sources_and_do_not_overwrite_each_other(tmp_path):
    c=Catalog(tmp_path/'library')
    source=tmp_path/'model.tex'
    source.write_text('source TeX')
    asset=c.asset(source)
    first=save(c,sources=[asset],tex='source TeX')
    updated=first.spec.model_copy(update={'name':'renamed model'})
    second=save(c,updated,parent=first.reference,tex='new TeX',sources=[asset])
    assert first.model_id==second.model_id and first.revision_id!=second.revision_id
    assert second.parent_revision==first.revision_id
    assert c.load(first.reference)==first and c.load(second.reference)==second
    source.write_text('edited outside catalog')
    assert c.asset_path(asset).read_text()=='source TeX'
    assert len(c.list())==2 and c.list('renamed')[0]==second
    with pytest.raises(ValueError,match='pinned'):
        c.load('catalog:'+first.model_id)

def test_modified_source_or_revision_is_not_reused(tmp_path):
    c=Catalog(tmp_path/'library')
    asset=c.asset_bytes('source.txt',b'original')
    r=save(c,sources=[asset])
    p=c.root/'models'/r.model_id/'revisions'/f'{r.revision_id}.json'
    original=p.read_text()
    data=json.loads(original)
    data['spec']['name']='changed'
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='integrity'):
        c.load(r.reference)
    p.write_text(original)
    c.asset_path(asset).write_text('changed')
    with pytest.raises(ValueError,match='source missing or modified'):
        c.load(r.reference)

def test_zero_is_known_and_missing_parameter_stays_unresolved(tmp_path):
    from adroit.library.personal import support
    from tests.library.legacy import saved_before_the_rule
    c=Catalog(tmp_path/'library')
    spec=model('vector',10,125,0,.25)
    assert support(spec)['numerically_declared']                  # a zero is a value, never a missing one
    with pytest.raises(ValueError,match=r'its dark sector \(chi\) has no route to the Standard Model'):
        save(c,spec)                    # but g_chi = 0 joins chi to nothing: not saved now (the auditor's UM-01)
    zero=saved_before_the_rule(c,*select_model(ideas.from_lagrangian(spec)))       # one saved before the rule
    assert zero.applicability['numerically_declared']
    c.verify_calculation(zero.reference,zero.spec,'track1')
    changed=zero.spec.model_copy(update={'couplings':[x.model_copy(update={'value':None}) if x.name=='g_chi' else x for x in zero.spec.couplings]})
    with pytest.raises(ValueError,match='cannot run yet, so it is not saved: no value for the coefficient g_chi'):
        save(c,changed)                     # the owner's rule, 2026-11-21 (the auditor's UM-02): never saved now
    incomplete=saved_before_the_rule(c,*select_model(ideas.from_lagrangian(changed)))     # one saved before the rule
    assert not incomplete.applicability['numerically_declared']
    with pytest.raises(ValueError,match='unresolved parameters'):
        c.verify_calculation(incomplete.reference,incomplete.spec,'track1')

def test_credential_inputs_are_refused_and_export_is_immutable(tmp_path):
    c=Catalog(tmp_path/'library')
    key=tmp_path/'.env'
    key.write_text('secret fixture, not a real key')
    with pytest.raises(ValueError):
        c.asset(key)
    with pytest.raises(ValueError):
        c.asset_bytes('.env.txt',b'fake')
    r=save(c)
    path=tmp_path/'export.yaml'
    c.export_model(r.reference,path)
    assert yaml.safe_load(path.read_text())['spec']==r.spec.model_dump(mode='json')
    with pytest.raises(ValueError,match='overwrite'):
        c.export_model(r.reference,path)

def test_cli_pinned_model_is_identical_in_both_tracks(tmp_path,monkeypatch):
    from adroit.core.config import get_settings
    from adroit.orchestrator import cli,runs
    from typer.testing import CliRunner
    monkeypatch.setattr(get_settings(),'model_library_dir',tmp_path/'library')
    r=save(Catalog())
    captured=[]
    monkeypatch.setattr(runs,'track1',lambda request,*a,**k:captured.append(request) or (tmp_path,'ok'))
    out=CliRunner().invoke(cli.app,['track1',r.reference,'--no-literature'])
    assert out.exit_code==0,out.output
    assert captured[0].spec==r.spec and captured[0].catalog_reference==r.reference
    captured.clear()
    monkeypatch.setattr(runs,'signal',lambda *a,**k:captured.extend(a[5]) or (tmp_path,'ok'))
    out=CliRunner().invoke(cli.app,['signal','--experiment','CDMS II Si (2013)','--model',r.reference,'--masses','10'])
    assert out.exit_code==0,out.output
    assert captured[0].spec==r.spec and captured[0].catalog_reference==r.reference


def test_same_named_revisions_have_distinct_track2_identity(tmp_path,monkeypatch):
    from adroit.core.config import get_settings
    from adroit.orchestrator.signal import SignalRequest,UserModel,candidates_for
    from adroit.experiments.registry import load_module
    monkeypatch.setattr(get_settings(),'model_library_dir',tmp_path/'library')
    c=Catalog()
    a=save(c)
    b=save(c,model('vector',10,125,.002,.25),parent=a.reference)
    request=SignalRequest(experiment='CDMS II Si (2013)',user_models=[
        UserModel(spec=r.spec,masses_gev=[10],catalog_reference=r.reference) for r in (a,b)])
    candidates=candidates_for(request,load_module(request.experiment))
    assert len(candidates)==2 and len({x.label for x in candidates})==2
    assert {x.model for x in candidates}=={a.reference,b.reference}


def test_a_revision_stored_before_a_schema_field_existed_still_loads(tmp_path):
    """The owner's 500 errors (2026-10-15, "catalog revision integrity mismatch"): a revision saved before G1 added a
    field's vev_gev and a term's indices was re-serialised with them, so its hash and its approval no longer matched.
    Recreated here: the stored file without those keys, hashed and approved as the earlier code did. It loads; a model
    that sets one of them to a value is a change and is refused."""
    from adroit.core.evidence import content_hash
    from adroit.orchestrator.model_approval import SCHEMA_ERAS, verify_identity
    c=Catalog(tmp_path/'library')
    r=save(c)
    folder=c.root/'models'/r.model_id/'revisions'
    data=json.loads((folder/f'{r.revision_id}.json').read_text())
    for where,key,_ in (added for era in SCHEMA_ERAS for added in era.added):
        found=data['spec']                           # "" is the spec itself (era 5's yukawa), else a path into it
        for step in (w for w in where.split('.') if w):
            found=found.get(step) if isinstance(found,dict) else None
        for item in found if isinstance(found,list) else [found] if isinstance(found,dict) else []:
            item.pop(key,None)
    data['model_sha256']=data['approval']['model_sha256']=content_hash(data['spec'])
    data.pop('schema_version',None)                 # the earlier code wrote no era (A14)
    data['approval'].pop('schema_version',None)
    data.pop('revision_id')
    old_id=content_hash(data)
    (folder/f'{r.revision_id}.json').unlink()
    (folder/f'{old_id}.json').write_text(json.dumps({**data,'revision_id':old_id}))
    loaded=c.load(f'catalog:{r.model_id}@{old_id}')
    assert loaded.spec==r.spec and len(c.list())==1
    term=loaded.spec.terms[0]
    changed=loaded.spec.model_copy(update={'terms':[term.model_copy(update={'indices':'chi*[a] chi[a]'}),
                                                    *loaded.spec.terms[1:]]})
    with pytest.raises(ValueError,match='model changed'):
        verify_identity(changed,data['model_sha256'])

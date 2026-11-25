"""Regression for the independent workflow audit's million-fold approval error."""
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from adroit.core.model_spec import ModelSpec
from adroit.orchestrator import ideas,track1
from adroit.orchestrator.model_approval import select_model,write_approved,model_identity,read_model,verify_request
from adroit.parameter_space.classify import classify


def supplied():
    fields=ModelSpec.model_validate({'name':'supplied_singlet','fields':[{'name':'S','role':'dark_matter',
        'spin':0,'self_conjugate':True,'dark_parity':-1,'mass_gev':70}]})
    general=ideas.from_fields(fields).general
    spec=general.model_copy(update={'couplings':[c.model_copy(update={'value':.2}) for c in general.couplings]})
    return ideas.from_lagrangian(spec)


def test_supplied_lagrangian_roundtrips_exactly_without_benchmark_replacement(tmp_path):
    m=supplied()
    before=m.spec.model_dump(mode='json')
    selected,approval=select_model(m)
    assert selected.model_dump(mode='json')==before and approval.choice=='supplied' and not approval.changes
    path=tmp_path/'approved.yaml'
    write_approved(path,selected,approval)
    actual=read_model(yaml.safe_load(path.read_text()))
    old_cls,old_point,_=classify(m.spec)
    cls,p,_=classify(actual)
    assert actual==m.spec and p==old_point and p.g_chi==pytest.approx(-.4)
    assert cls.dd(p)[1]==pytest.approx(2.947728787324616e-43,rel=1e-12)
    assert cls.dd(p)==old_cls.dd(old_point)
    assert m.spec.model_dump(mode='json')==before


def test_general_completion_is_distinct_explicit_and_shows_parameter_changes():
    m=supplied()
    spec,a=select_model(m,general_completion=True)
    assert a.choice=='general_completion' and spec==m.general and spec!=m.spec
    assert a.model_sha256!=a.source_model_sha256
    assert any('couplings' in change and 'None' in change and '0.2' in change for change in a.changes)
    assert select_model(m)[0]==m.spec


def test_field_content_still_selects_the_generated_lagrangian():
    m=ideas.from_fields(supplied().spec)
    selected,a=select_model(m)
    assert selected==m.general and selected.terms and a.choice=='generated_from_fields'
    with pytest.raises(ValueError,match='only to supplied'):
        select_model(m,general_completion=True)


def test_changed_file_and_changed_cli_expected_hash_refuse_calculation(tmp_path,monkeypatch):
    from adroit.orchestrator import cli,runs
    spec,a=select_model(supplied())
    path=tmp_path/'model.yaml'
    write_approved(path,spec,a)
    parsed=yaml.safe_load(path.read_text())
    parsed['spec']['couplings'][0]['value']=.1
    path.write_text(yaml.safe_dump(parsed))
    import typer
    with pytest.raises(typer.BadParameter,match='changed since approval'):   # a usage error since the audit's phase 4
        cli._spec(path)
    # Even changing the file's own digest cannot change the identity reviewed in the UI.
    parsed['approval']['model_sha256']=model_identity(ModelSpec.model_validate(parsed['spec']))
    path.write_text(yaml.safe_dump(parsed))
    called=[]
    monkeypatch.setattr(runs,'track1',lambda *a,**k:called.append(a))
    response=CliRunner().invoke(cli.app,['track1',str(path),'--approved-model-hash',a.model_sha256])
    assert response.exit_code!=0 and not called


def test_python_boundary_refuses_spec_or_mapping_override_before_running(tmp_path):
    from adroit.parameter_space.classes import Spin1Class
    spec,a=select_model(supplied())
    request=track1.Track1Request(spec=spec,approved_model_sha256=a.model_sha256,literature=False)
    changed=request.model_copy(update={'spec':spec.model_copy(update={'assumptions':['changed']})})
    with pytest.raises(ValueError,match='changed since approval'):
        track1.run(changed,tmp_path/'changed')
    with pytest.raises(ValueError,match='numerical mapping'):
        verify_request(request.model_copy(update={'model_class':Spin1Class()}))
    assert not (tmp_path/'changed').exists()


def test_approval_keeps_complete_contract_fields_and_legacy_yaml_loads():
    path=Path('docs/examples/complete_scalar_running.yaml')
    spec=ModelSpec.model_validate(yaml.safe_load(path.read_text()))
    selected,a=select_model(ideas.from_lagrangian(spec))
    assert selected==spec and selected.scalar_potential==spec.scalar_potential and selected.scalar_running==spec.scalar_running
    assert read_model(spec.model_dump(mode='json'))==spec
    assert read_model({'spec':spec.model_dump(mode='json')})==spec

"""Simplified-class mapping cannot add flavours or discard a supplied current."""
from pathlib import Path

import pytest
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.parameter_space.classify import Unsupported, classify
from adroit.parameter_space.classes import Spin1Class
from adroit.constraints import spin1

ROOT = Path(__file__).resolve().parents[2]


def vector(quarks=('q',), leptons=(), values=None):
    raw = yaml.safe_load((ROOT/'docs/dm13/vector_mediator.yaml').read_text())
    current = raw['terms'].pop()
    raw['fields'].pop()
    for name in (*quarks,*leptons):
        raw['fields'].append({'name':name,'role':'standard_model','spin':.5})
        coefficient = f'g_{name}'
        raw['couplings'].append({'name':coefficient,'value':(values or {}).get(name,.25)})
        raw['terms'].append({**current,'coupling':coefficient,
                            'fields':[{'field':name,'conjugate':True},{'field':name},{'field':'Zp'}]})
    return raw


@pytest.mark.parametrize('flavours',[('u',),('u','d'),('c','b'),('uR',)])
def test_named_quarks_do_not_acquire_all_six_flavours(flavours):
    with pytest.raises(Unsupported,match='quark|current'):
        classify(ModelSpec.model_validate(vector(flavours)), generic_route=False)


def test_complete_universal_quarks_match_the_explicit_benchmark():
    cls,point,_ = classify(ModelSpec.model_validate(vector(('u','d','s','c','b','t'))))
    reference,p,_ = classify(ModelSpec.model_validate(vector()))
    assert isinstance(cls,Spin1Class) and point==p
    assert spin1.width(cls.completion(point),point.m_chi)==pytest.approx(
        spin1.width(reference.completion(p),p.m_chi))


def test_nonuniversal_tiny_difference_is_not_rounded_to_one_coupling():
    with pytest.raises(Unsupported,match='values differ'):
        classify(ModelSpec.model_validate(vector(('u','d','s','c','b','t'),values={'b':.25+1e-14})), generic_route=False)


def test_generic_quarks_cannot_silently_discard_a_supplied_mass():
    raw=vector()
    raw['fields'][-1]['mass_gev']=4.18
    with pytest.raises(Unsupported,match='individual SM flavour masses'):
        classify(ModelSpec.model_validate(raw), generic_route=False)


@pytest.mark.parametrize('coupling',['g_q*m_q**2/v**2','g_q*m_b/v','g_q*m_q/v**2'])
def test_scalar_mapping_does_not_erase_non_yukawa_mass_dependence(coupling):
    raw=yaml.safe_load((ROOT/'docs/dm13/scalar_mediator.yaml').read_text())
    raw['terms'][-1]['coupling']=coupling
    with pytest.raises(Unsupported,match='own mass|linear'):
        classify(ModelSpec.model_validate(raw), generic_route=False)


def test_scalar_mapping_preserves_an_explicit_electroweak_scale():
    from adroit.parameter_space.classes import V_HIGGS
    raw=yaml.safe_load((ROOT/'docs/dm13/scalar_mediator.yaml').read_text())
    raw['couplings'].append({'name':'v','value':240.})
    _,point,_=classify(ModelSpec.model_validate(raw))
    assert point.g_q/V_HIGGS==pytest.approx(1/240.)


def test_generic_yukawa_cannot_discard_a_numerical_mass_parameter():
    raw=yaml.safe_load((ROOT/'docs/dm13/scalar_mediator.yaml').read_text())
    raw['couplings'].append({'name':'m_q','value':3.,'mass_dimension':1})
    with pytest.raises(Unsupported,match='own flavour mass'):
        classify(ModelSpec.model_validate(raw), generic_route=False)


@pytest.mark.parametrize('leptons',[('e',),('e','mu','tau')])
def test_charged_lepton_subset_does_not_acquire_a_neutrino_completion(leptons):
    with pytest.raises(Unsupported,match='lepton|neutrino'):
        classify(ModelSpec.model_validate(vector(leptons=leptons)), generic_route=False)


def test_declared_generic_lepton_benchmark_keeps_its_coefficient_and_completion_note():
    _,point,notes = classify(ModelSpec.model_validate(vector(leptons=('l',),values={'l':.01})))
    assert point.g_l==.01 and point.g_q==.25
    assert any('neutrino completion' in n for n in notes)


@pytest.mark.parametrize('change',['axial_lepton','duplicate_quark','chiral_quark','additional_hc','extra_mediator_term','zero_mass','charged_dm','complex_mediator'])
def test_unrepresented_input_remains_unsupported(change):
    raw=vector(leptons=('l',))
    if change=='axial_lepton':
        raw['terms'][-1]['lorentz']='axial'
    elif change=='duplicate_quark':
        raw['terms'].append(raw['terms'][1].copy())
    elif change=='chiral_quark':
        raw['fields'][2]['chirality']='R'
    elif change=='additional_hc':
        raw['terms'][1]['plus_hc']=True
    elif change=='extra_mediator_term':
        raw['terms'].append({'fields':[{'field':'Zp'}]*4,'lorentz':'scalar','coupling':'0.1'})
    elif change=='zero_mass':
        raw['fields'][0]['mass_gev']=0.
    elif change=='charged_dm':
        raw['fields'][0]['charges']={'electric_charge':1.}
    elif change=='complex_mediator':
        raw['fields'][1]['self_conjugate']=False
    with pytest.raises(Unsupported):
        classify(ModelSpec.model_validate(raw), generic_route=False)

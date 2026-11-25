"""Declared coordinate validation and defaults without changing any physics kernel."""
import pytest
import yaml
from pathlib import Path

from adroit.parameter_space import library,scan
from adroit.parameter_space.classes import Point,Spin1Class
from adroit.parameter_space.classify import classify
from adroit.parameter_space.portals.higgs import HiggsPortalScalar,HiggsPortalFermion,HiggsPortalVector
from adroit.parameter_space.portals.vector import ZPortal,InelasticDarkPhoton,DarkPhoton
from adroit.parameter_space.scan_setup import active_coordinates,default_axes,preview,validate_axes
from adroit.core.model_spec import ModelSpec


@pytest.mark.parametrize('cls',[HiggsPortalScalar(),HiggsPortalFermion(),HiggsPortalVector(),ZPortal()])
def test_fixed_sm_mediator_is_not_a_scan_axis_or_a_mass_relation(cls):
    p=Point(m_chi=70,m_med=125.09,g_chi=.2)
    x,y=default_axes(cls,p,n=2)
    assert {x.parameter,y.parameter}=={'m_chi','g_chi'}
    setup=preview(cls,p,x,y)
    assert setup.fixed['m_med']==125.09 and 'm_med' not in setup.active
    with pytest.raises(ValueError,match='fixed or unused'):
        validate_axes(cls,scan.Axis(parameter='m_med',low=10,high=1000,n=2),y)
    with pytest.raises(ValueError,match='mass is fixed'):
        preview(cls,p,mediator_ratio=3)


def test_all_library_planes_remain_active_and_unchanged():
    for e in library.ENTRIES:
        validate_axes(e.model_class,e.x,e.y,e.mediator_ratio)
        setup=preview(e.model_class,e.point,e.x,e.y,e.mediator_ratio)
        assert setup.x==e.x.model_dump(mode='json') and setup.y==e.y.model_dump(mode='json')


def test_signed_coupling_and_derived_mass_preview_preserve_reference_inputs():
    p=Point(m_chi=70,m_med=125.09,g_chi=-.4)
    setup=preview(HiggsPortalScalar(),p)
    coupling=next(a for a in (setup.x,setup.y) if a['parameter']=='g_chi')
    assert coupling['low']<coupling['high']<0 and coupling['log']
    p=Point(m_chi=10,m_med=30,g_chi=.5,g_q=.001)
    setup=preview(DarkPhoton(),p,mediator_ratio=3)
    assert setup.derived=={'m_med':'3 * m_chi'} and 'm_med' not in setup.active
    assert setup.fixed['g_chi']==.5
    with pytest.raises(ValueError,match='independent axis'):
        validate_axes(DarkPhoton(),scan.Axis(parameter='m_med',low=10,high=100,n=2),
                      scan.Axis(parameter='m_chi',low=1,high=10,n=2),3)


def test_flavour_unused_slots_refused_and_inelastic_splitting_remains_active():
    spec=ModelSpec.model_validate(yaml.safe_load(Path('docs/examples/flavour_vector.yaml').read_text()))
    cls,p,_=classify(spec)
    assert active_coordinates(cls)==['m_chi','m_med','g_chi']
    with pytest.raises(ValueError,match='fixed or unused'):
        validate_axes(cls,scan.Axis(parameter='g_l',low=.1,high=.2,n=2),scan.Axis(parameter='m_chi',low=10,high=100,n=2))
    assert 'g_l' in active_coordinates(InelasticDarkPhoton())


def test_scan_boundary_refuses_inactive_coordinate_before_any_prediction(monkeypatch):
    called=[]
    monkeypatch.setattr(scan,'evaluate',lambda *args,**kwargs:called.append(args))
    request=scan.ScanRequest(model_class=HiggsPortalScalar(),fixed=Point(m_chi=70,m_med=125.09,g_chi=.1),
        x=scan.Axis(parameter='m_med',low=10,high=10000,n=2),y=scan.Axis(parameter='m_chi',low=70,high=90,n=2),workers=1)
    # Archived requests still decode; executing a new inactive scan is refused.
    assert scan.ScanRequest.model_validate_json(request.model_dump_json())==request
    with pytest.raises(ValueError,match='fixed or unused'):
        scan.run(request)
    assert not called


def test_reviewed_mapping_and_fixed_values_are_bound_before_scan(tmp_path,monkeypatch):
    from adroit.ui.forms import review_scan
    from adroit.orchestrator import track1
    from adroit.orchestrator.track1 import Track1Request,run
    from adroit.parameter_space.simplified import model
    spec=model('vector',10,125,g_chi=.001)
    _,setup,token=review_scan(yaml.safe_dump(spec.model_dump(mode='json')),
                            'm_med:100:200:log:2','m_chi:8:12:log:2')
    request=Track1Request(spec=spec,literature=False,workers=1,
        x=scan.Axis.model_validate(setup.x),y=scan.Axis.model_validate(setup.y),reviewed_scan_sha256=token)
    called=[]
    monkeypatch.setattr(track1,'scan',lambda *a,**k:called.append(a))
    changed=request.model_copy(update={'fixed':Point(m_chi=10,m_med=125,g_chi=.002),'model_class':Spin1Class(name=spec.name)})
    with pytest.raises(ValueError,match='changed since review'):
        run(changed,tmp_path)
    assert not called


def test_review_roundtrip_retains_full_bounds_and_distinguishes_close_mass_ratios():
    from adroit.ui.forms import review_scan,axis_text
    from adroit.parameter_space.simplified import model
    text=yaml.safe_dump(model('vector',10,125).model_dump(mode='json'))
    _,a,token=review_scan(text,'g_chi:0.123456789123:0.987654321987:lin:2','m_chi:7.123456789:11.123456789:log:2',3.14159265358)
    _,b,repeated=review_scan(text,axis_text(a.x),axis_text(a.y),3.14159265358)
    assert a==b and token==repeated
    _,c,different=review_scan(text,axis_text(a.x),axis_text(a.y),3.14159265359)
    assert token!=different and a.mediator_ratio!=c.mediator_ratio

"""Independent references for bounded maxima, profiles, ambiguity and failure."""
from itertools import product

import numpy as np
import pytest
from scipy.optimize import differential_evolution

from adroit.core.fit_domain import PhysicalDomain, FitCoordinate, FitBranch, FitRelation, DomainFitSettings
from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
from adroit.parameter_space.classes import Point
from adroit.parameter_space.physical_fit import FitTrial, FitSettings, fit_trials
from adroit.parameter_space.multiparameter_fit import fit_domain

P = Point(m_chi=10,m_med=100,g_chi=.3,g_q=.25)


def trial(function):
    return lambda p: FitTrial(point=p,log_l=float(function(p)),signal_events=p.g_chi**2,
                              densities_at_events=[1.])


def domain(*axes, **kwargs):
    return PhysicalDomain(coordinates=[FitCoordinate(**a) for a in axes],**kwargs)


def test_named_domain_matches_dense_scan_optimizer_and_analytic_profiles():
    d = domain(dict(parameter='m_chi',values=[8,10,12]),dict(parameter='g_chi',low=0,high=1),
               dict(parameter='m_med',low=50,high=150))
    def fun(p):
        return -(p.m_chi-10)**2-30*(p.g_chi-.37)**2-(p.m_med-82)**2/100
    r = fit_domain(P,d,DomainFitSettings(),-50,trial(fun))
    assert r.resolved and r.identifiable,r.reason
    dense = max((fun(P.model_copy(update={'g_chi':g,'m_med':m})),g,m)
                for g,m in product(np.linspace(0,1,101),np.linspace(50,150,101)))
    separate = differential_evolution(lambda x:-fun(P.model_copy(update={'g_chi':x[0],'m_med':x[1]})),
                                     [(0,1),(50,150)],seed=72,tol=1e-9)
    assert r.log_l == pytest.approx(-separate.fun,abs=1e-8)
    assert r.point.g_chi == pytest.approx(dense[1],abs=.011)
    assert r.point.m_med == pytest.approx(dense[2],abs=1.01)
    assert len(r.modes)==3
    for value in r.profiles['g_chi']:
        assert value.log_l == pytest.approx(-30*(value.value-.37)**2,abs=1e-7)
    for value in r.profiles['m_med']:
        assert value.log_l == pytest.approx(-(value.value-82)**2/100,abs=1e-7)


def test_correlated_valley_does_not_stop_at_an_artificial_grid_cell_wall():
    d=domain(dict(parameter='g_chi',low=0,high=1),dict(parameter='m_med',low=50,high=150))
    e=trial(lambda p:-900*((p.g_chi-.37)-.006*(p.m_med-82))**2-(p.m_med-82)**2/100)
    r=fit_domain(P,d,DomainFitSettings(grid=7,max_evaluations=20000),-100,e)
    assert r.resolved and r.identifiable,r.reason
    assert r.point.g_chi==pytest.approx(.37,abs=1e-5)
    assert r.point.m_med==pytest.approx(82,abs=1e-3)


def test_three_continuous_coordinates_recover_full_rank_reference():
    d=domain(dict(parameter='g_chi',low=0,high=1),dict(parameter='g_q',low=0,high=1),
             dict(parameter='m_med',low=50,high=150))
    r=fit_domain(P,d,DomainFitSettings(max_evaluations=20000),-100,
        trial(lambda p:-40*(p.g_chi-.413)**2-17*(p.g_q-.681)**2-(p.m_med-87.3)**2/31))
    assert r.resolved and r.identifiable,r.reason
    assert r.modes[0].local_rank==3
    assert r.point.g_chi==pytest.approx(.413,abs=1e-5)
    assert r.point.g_q==pytest.approx(.681,abs=1e-5)
    assert r.point.m_med==pytest.approx(87.3,abs=1e-3)


@pytest.mark.parametrize('peak,edge',[(.37,False),(2.,True),(-1.,True)])
def test_one_dimensional_restriction_recovers_existing_solver(peak,edge):
    from adroit.core.model_spec import PhysicalFitRange
    d=domain(dict(parameter='g_chi',low=0,high=1))
    evaluator=trial(lambda p:-20*(p.g_chi-peak)**2)
    r=fit_domain(P,d,DomainFitSettings(),-100,evaluator)
    old=fit_trials(P,PhysicalFitRange(low=0,high=1),FitSettings(),-100,evaluator)
    assert r.resolved and old.resolved,(r.reason,old.reason)
    assert r.log_l == pytest.approx(old.log_l,abs=1e-7)
    assert r.point.g_chi == pytest.approx(old.point.g_chi,abs=1e-5)
    assert bool(r.modes[0].boundaries)==edge


def test_disconnected_modes_lower_modes_and_explicit_branches_survive():
    d=domain(dict(parameter='g_chi',low=-2,high=2),dict(parameter='m_med',low=50,high=150),
             branches=[FitBranch(label='plus',fixed={'g_q':.25}),FitBranch(label='minus',fixed={'g_q':-.25})])
    e=trial(lambda p:-50*(p.g_chi**2-1)**2-(p.m_med-100)**2/50)
    r=fit_domain(P,d,DomainFitSettings(grid=9),-100,e)
    assert r.resolved and not r.identifiable,r.reason
    assert len(r.modes)==4
    assert {m.branch for m in r.modes}=={'plus','minus'}
    assert sorted(m.point.g_chi for m in r.modes)==pytest.approx([-1,-1,1,1],abs=1e-5)
    unequal=fit_domain(P,domain(dict(parameter='g_chi',low=-2,high=2)),DomainFitSettings(grid=9),-100,
                     trial(lambda p:-50*(p.g_chi**2-1)**2-.1*p.g_chi))
    assert unequal.resolved and len(unequal.modes)==2,unequal.reason
    assert abs(unequal.modes[0].log_l-unequal.modes[1].log_l)>.1


def test_product_degeneracy_never_becomes_a_unique_fit():
    d=domain(dict(parameter='g_chi',low=.1,high=1),dict(parameter='g_q',low=.1,high=1))
    r=fit_domain(P,d,DomainFitSettings(grid=5,max_evaluations=30000),-50,
                 trial(lambda p:-100*(p.g_chi*p.g_q-.25)**2))
    assert not r.identifiable
    if r.resolved:
        assert r.log_l == pytest.approx(0,abs=1e-5)
        assert any(m.local_rank==1 for m in r.modes)
    else:
        assert 'mode' in r.reason or 'profile' in r.reason or 'resolution' in r.reason


def test_relations_fixed_values_and_log_transform_are_explicit():
    d=domain(dict(parameter='g_chi',low=1e-5,high=1,scale='log'),fixed={'m_chi':12,'g_l':0},
             relations=[FitRelation(target='m_med',source='m_chi',scale=2)])
    e=trial(lambda p:-(np.log(p.g_chi/.001))**2)
    r=fit_domain(P,d,DomainFitSettings(),-100,e)
    assert r.resolved and r.point.m_med==24 and r.point.m_chi==12,r.reason
    assert r.point.g_chi == pytest.approx(.001,rel=1e-5)
    for bad in [dict(parameter='m_chi',values=[0,10]),dict(parameter='g_chi',low=0,high=1,scale='log'),
                dict(parameter='m_med',low=1,high=2,values=[1,2]),dict(parameter='g_q',values=[float('nan')])]:
        with pytest.raises(ValueError):
            FitCoordinate(**bad)
    with pytest.raises(ValueError,match='chained'):
        domain(dict(parameter='g_chi',low=0,high=1),relations=[FitRelation(target='m_med',source='m_chi'),
                                                           FitRelation(target='m_chi',source='m_med')])
    with pytest.raises(ValueError,match='free'):
        domain(dict(parameter='g_chi',low=0,high=1),fixed={'g_chi':.2})


def test_budget_invalid_island_and_fresh_verification_are_unresolved():
    d=domain(dict(parameter='g_chi',low=0,high=1))
    r=fit_domain(P,d,DomainFitSettings(max_evaluations=5),-50,trial(lambda p:-(p.g_chi-.37)**2))
    assert not r.resolved and r.evaluations==5 and 'budget' in r.reason
    def island(p):
        if .4<=p.g_chi<=.6:
            raise ValueError('missing response')
        return -(p.g_chi-.9)**2
    r=fit_domain(P,d,DomainFitSettings(),-50,trial(island))
    assert not r.resolved and r.invalid
    seen={}
    def changing(p):
        key=p.g_chi
        seen[key]=seen.get(key,0)+1
        return -(key-.37)**2+(1 if seen[key]>1 else 0)
    r=fit_domain(P,d,DomainFitSettings(),-50,trial(changing))
    assert not r.resolved and 'verification' in r.reason


def test_partial_checkpoint_resumes_and_refuses_changed_contract(tmp_path):
    d=domain(dict(parameter='g_chi',low=0,high=1))
    s=DomainFitSettings()
    cp=Checkpoint(tmp_path,{'domain':d.model_dump(mode='json'),'settings':s.model_dump(mode='json')},{'source':'a'})
    calls=[]
    def interrupted(p):
        calls.append(p.g_chi)
        if len(calls)==12:
            raise KeyboardInterrupt
        return trial(lambda p:-(p.g_chi-.37)**2)(p)
    with pytest.raises(KeyboardInterrupt):
        fit_domain(P,d,s,-50,interrupted,cp)
    resumed=Checkpoint(tmp_path,cp.manifest.inputs,{'source':'a'},resume=True)
    actual=[]
    def evaluate(p):
        actual.append(p.g_chi)
        return trial(lambda p:-(p.g_chi-.37)**2)(p)
    r=fit_domain(P,d,s,-50,evaluate,resumed)
    standalone=fit_domain(P,d,s,-50,trial(lambda p:-(p.g_chi-.37)**2))
    assert r==standalone and len(actual)<r.evaluations and r.resolved
    with pytest.raises(CheckpointMismatch):
        Checkpoint(tmp_path,cp.manifest.inputs,{'source':'b'},resume=True)


def test_valid_cached_payload_under_wrong_point_key_cannot_corrupt_profiles(tmp_path):
    from adroit.core.evidence import content_hash
    from adroit.parameter_space.multiparameter_fit import TrialRecord
    d=domain(dict(parameter='g_chi',low=0,high=1))
    cp=Checkpoint(tmp_path,{'domain':d.model_dump(mode='json')},{'source':'fixture'})
    evaluator=trial(lambda p:-(p.g_chi-.37)**2)
    first=P.model_copy(update={'g_chi':0.})
    wrong=P.model_copy(update={'g_chi':1.})
    cp.save('domain_trials',content_hash(first.model_dump(mode='json')),TrialRecord(trial=evaluator(wrong)))
    r=fit_domain(P,d,DomainFitSettings(),-10,evaluator,cp)
    assert not r.resolved and 'cached physical trial' in r.reason
    assert not r.profiles

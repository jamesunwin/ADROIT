from types import SimpleNamespace
import pytest
from adroit.core.evidence import EvidenceContext
from adroit.core.eligibility import CandidateEligibility,EligibilitySettings
from adroit.orchestrator import signal,physical_eligibility as eligibility
from adroit.parameter_space.library import entry
from adroit.parameter_space.classify import classify
from adroit.parameter_space.scan import PointResult
from tests.orchestrator.test_signal import ToyGermanium

def spec():
    s=entry('higgs_portal_scalar').spec()
    return s.model_copy(update={'fields':[f.model_copy(update={'mass_gev':20}) if f.name=='S' else f for f in s.fields],
        'couplings':[c.model_copy(update={'value':-.5 if c.name=='lam_H_S' else -.025}) for c in s.couplings]})

def point_result(point,excluded=False,pending=None,omega=.12):
    return PointResult(point=point,omega_h2=omega,dd_kind='SI',dd_sigma_cm2=1e-45,dd_limit_cm2=2e-45,
        excluded={'direct detection':excluded,'perturbativity':False},pending=pending or [])

def test_real_spectrum_likelihood_match_and_different_model_mapping_rejected():
    from adroit.orchestrator.user_models import candidates
    from adroit.inference.signal_fit import fit,event_densities
    s=spec()
    user=signal.UserModel(spec=s,masses_gev=[20])
    c=candidates(s,[20])[0]
    module=ToyGermanium()
    prediction=signal._signal(module,c)
    events,res=module.observations()
    fitted=fit(c.label,event_densities(prediction.observable,prediction.density,events,res),module.background_at(events))
    req=signal.SignalRequest(experiment='toy',user_models=[user])
    cls,point,bounded,error,ll_error=eligibility._physical(req,c,fitted,module,user)
    assert point is not None and error<1e-6 and ll_error<1e-6
    wrong=c.interaction.model_copy(deep=True)
    wrong.coefficients[0].proton*=2
    with pytest.raises(ValueError,match='exact model mapping'):
        eligibility._physical(req,c.model_copy(update={'interaction':wrong}),fitted,module,user)

def test_exact_point_decisions_pending_assumptions_and_budget(monkeypatch):
    s=spec()
    cls,p,_=classify(s)
    users=[signal.UserModel(spec=s,masses_gev=[20,30,40])]
    candidates=[signal.Candidate(label=str(m),mass_gev=m,model=s.name,spin=0) for m in (20,30,40)]
    req=signal.SignalRequest(experiment='toy',user_models=users,eligibility_settings=EligibilitySettings(max_candidates=2))
    monkeypatch.setattr(eligibility,'_physical',lambda req,c,f,module,model:(cls,p.model_copy(update={'m_chi':c.mass_gev}),None,0.,0.))
    monkeypatch.setattr(eligibility,'_current_context',lambda *a:EvidenceContext(origin='captured',identity='current',code_sha256='code'))
    from adroit.parameter_space import scan
    monkeypatch.setattr(scan,'evaluate',lambda cls,p,*a,**k:point_result(p,excluded=p.m_chi==20))
    band(monkeypatch,{'upper':.1205,'lower':.1196})
    rows=eligibility.assess(req,candidates,[SimpleNamespace(label=c.label) for c in candidates],object())
    assert rows['20'].status=='excluded_point' and rows['20'].point.m_chi==20
    assert rows['30'].status=='eligible' and rows['40'].status=='pending'
    assert 'budget exhausted' in rows['40'].reasons[-1]
    assert rows['30'].source_identity=='current' and rows['30'].thermal_status=='at_declared_target'
    monkeypatch.setattr(scan,'evaluate',lambda cls,p,*a,**k:point_result(p,pending=['missing response'],omega=.2))
    row=eligibility.assess(req,candidates[:1],[SimpleNamespace(label='20')],object())['20']
    assert row.status=='pending' and row.thermal_status=='off_target'
    exploratory=eligibility.assess(req.model_copy(update={'unverified_records':True}),candidates[:1],[SimpleNamespace(label='20')],object())['20']
    assert exploratory.status=='pending' and exploratory.evaluation is None

def band(monkeypatch,values,missing=''):
    """The equation of state's band as given: its tables present (or ``missing``), Ωh² with each ``values``."""
    from adroit.constraints import relic
    monkeypatch.setattr(relic,'band_unavailable',lambda:missing)
    monkeypatch.setattr(relic,'band_values',lambda compute:dict(values))

@pytest.mark.eos_band
@pytest.mark.parametrize('case',['missing','damaged','disagreeing','uncomputed','agreeing'])
def test_a_point_at_the_target_is_eligible_only_across_the_equation_of_states_band(monkeypatch,case):
    """The consistency audit's CA-02 (2026-10-24): with the tables missing, a fitted point at the target was eligible,
    "at_declared_target", with no reason, where the plane's root waits for them. Its thermal status now has the band's
    certification, at the point the fit fixes: the tables missing or damaged, or Ωh² off the target (or not computed)
    with one of them, leave it pending with the nominal fact stated; an exclusion at the point stands without them."""
    s=spec()
    cls,p,_=classify(s)
    users=[signal.UserModel(spec=s,masses_gev=[30])]
    candidates=[signal.Candidate(label='30',mass_gev=30,model=s.name,spin=0),signal.Candidate(label='20',mass_gev=20,model=s.name,spin=0)]
    req=signal.SignalRequest(experiment='toy',user_models=users)
    monkeypatch.setattr(eligibility,'_physical',lambda req,c,f,module,model:(cls,p.model_copy(update={'m_chi':c.mass_gev}),None,0.,0.))
    monkeypatch.setattr(eligibility,'_current_context',lambda *a:EvidenceContext(origin='captured',identity='current',code_sha256='code'))
    from adroit.parameter_space import scan
    monkeypatch.setattr(scan,'evaluate',lambda cls,p,*a,**k:point_result(p,excluded=p.m_chi==20))
    values={'missing':{},'damaged':{},'disagreeing':{'upper':.114,'lower':.1201},'uncomputed':{'upper':None,'lower':.12},
            'agreeing':{'upper':.1195,'lower':.1206}}[case]
    missing={'missing':"the equation of state's band is not computed: Saikawa & Shirai's equation-of-state tables are not installed: run `adroit setup --fetch`",
             'damaged':"the equation of state's band is not computed: Saikawa & Shirai's upper equation-of-state table, x, is not the table as published"}.get(case,'')
    band(monkeypatch,values,missing)
    rows=eligibility.assess(req,candidates,[SimpleNamespace(label=c.label) for c in candidates],object())
    row=rows['30']
    assert row.thermal_status=='at_declared_target' and rows['20'].status=='excluded_point'
    # M1: the claims' certificates; the exclusion of a fixed point stands without the tables
    assert rows['20'].certificate.claim_kind=='fixed_point_exclusion' and rows['20'].certificate.decided
    assert row.certificate.claim_kind=='path2_thermal_eligibility'
    assert row.certificate.check('eos_band').state=={'missing':'unknown','damaged':'unknown','disagreeing':'failed',
                                                     'uncomputed':'unknown','agreeing':'satisfied'}[case]
    assert row.certificate.decided==(case=='agreeing')
    if case=='agreeing':
        assert row.status=='eligible' and not row.reasons
        assert any("the equation of state's band: at the declared target also" in a for a in row.assumptions)
        return
    assert row.status=='pending' and len(row.reasons)==1
    assert 'nominal Ωh² is at the target (0.12)' in row.reasons[0] and 'is not established' in row.reasons[0]
    if missing:
        assert row.reasons[0].endswith(missing)
    else:
        assert row.reasons[0].startswith('EOS-sensitive') and ('0.114 with the upper table' in row.reasons[0]
                                                               or 'not computed with the upper table' in row.reasons[0])

def test_no_completion_incomplete_physical_fit_and_score_mismatch_cannot_prune(monkeypatch):
    s=spec()
    cls,p,_=classify(s)
    req=signal.SignalRequest(experiment='toy',user_models=[signal.UserModel(spec=s)])
    card=signal.Candidate(label='bare',card_id='O1',mass_gev=20)
    assert eligibility.assess(req,[card],[SimpleNamespace(label='bare')],object())['bare'].status=='pending'
    c=card.model_copy(update={'label':'physical','model':s.name})
    for result in [(cls,None,None,None,None),(cls,p,None,.2,.01)]:
        monkeypatch.setattr(eligibility,'_physical',lambda *a,result=result:result)
        row=eligibility.assess(req,[c],[SimpleNamespace(label='physical')],object())['physical']
        assert row.status=='pending' and row.evaluation is None

def test_pruning_does_not_change_raw_tournament_and_reveals_next_class_representative(monkeypatch):
    monkeypatch.setitem(signal.modules.SIGNAL_SEARCHES,'toy germanium',ToyGermanium)
    candidates=[signal.Candidate(label=label,card_id=card,isospin='s',mass_gev=m) for label,card,m in
        [('a','O1',20),('b','O1',20),('c','O4',30)]]
    req=signal.SignalRequest(experiment='toy germanium',candidates=candidates,null_modules=[],toys=20,leaders=1,complementary=False)
    monkeypatch.setattr(eligibility,'assess',lambda req,c,fit,module:{x.label:CandidateEligibility(label=x.label,status='pending') for x in c})
    base=signal.run(req)
    monkeypatch.setattr(eligibility,'assess',lambda req,c,fit,module:{x.label:CandidateEligibility(label=x.label,
        status='excluded_point' if x.label=='a' else 'eligible' if x.label=='b' else 'pending') for x in c})
    changed=signal.run(req)
    assert changed.tournament==base.tournament and changed.fits==base.fits and changed.global_z==base.global_z
    assert 'b' in [e.label for e in changed.eligible_tournament.ranking]
    assert 'a' not in [e.label for e in changed.eligible_tournament.ranking]
    assert 'c' in [e.label for e in changed.unresolved_tournament.ranking]
    assert signal.dm_tournament.NULL in [e.label for e in changed.eligible_tournament.ranking]
    assert changed.classes['a']==changed.classes['b']
    from adroit.orchestrator.promote import labels_of
    assert 'a' not in labels_of(changed,f'class:{changed.classes["a"]}')
    assert 'b' in labels_of(changed,f'class:{changed.classes["a"]}')
    assert labels_of(changed,'a',include_excluded=True)==['a']
    with pytest.raises(KeyError,match='fitted point is excluded'):
        labels_of(changed,'a')

def test_saved_track1_requires_exact_point_model_profile_and_current_provenance(tmp_path,monkeypatch):
    from adroit.orchestrator.track1 import Track1Request,Track1Result
    from adroit.parameter_space.scan import Axis,ScanRequest,ScanResult
    from adroit.model_building.audit import audit
    from adroit.evidence import build
    s=spec()
    cls,p,_=classify(s)
    user=signal.UserModel(spec=s)
    source=EvidenceContext(origin='captured',identity='current',code_sha256='code')
    monkeypatch.setattr(build,'finish',lambda context,read=None,consumed=None:context)
    def write(name,request=None,point=None,context=None):
        req=request or Track1Request(spec=s)
        row=point_result(point or p)
        scan=ScanResult(request=ScanRequest(model_class=cls,fixed=p,x=Axis(parameter='m_chi',low=20,high=30,n=2),
            y=Axis(parameter='g_chi',low=1,high=2,n=2)),xs=[20,30],ys=[1,2],points=[row])
        result=Track1Result(request=req,audit=audit(s),scan=scan)
        path=tmp_path/(name+'.json')
        path.write_text(result.model_dump_json())
        build.save(path,'track1',context or source)
        return path
    path=write('exact')
    request=signal.SignalRequest(experiment='toy',user_models=[user],track1_results=[str(path)])
    row,reused,_,notes=eligibility._saved(request,user,cls,p,source)
    assert row.point==p and reused==str(path.resolve()) and not notes
    for saved in [write('nearby',point=p.model_copy(update={'g_chi':p.g_chi+1e-12})),
                  write('stale',context=source.model_copy(update={'identity':'old'})),
                  write('profile',request=Track1Request(spec=s,experimental_profile='profile:'+'a'*64)),
                  write('model',request=Track1Request(spec=s.model_copy(update={'name':'other revision'})))]:
        req=request.model_copy(update={'track1_results':[str(saved)]})
        result,reused,_,notes=eligibility._saved(req,user,cls,p,source)
        assert result is None and not reused and notes
    path.write_text(path.read_text().replace('"omega_h2":0.12','"omega_h2":0.2'))
    assert eligibility._saved(request,user,cls,p,source)[0] is None

@pytest.mark.eos_band
@pytest.mark.needs('eos')
def test_thermal_eligibility_is_bound_to_the_tables_and_a_fixed_point_exclusion_is_not(monkeypatch,eos_copy):
    """The auditor's CO recheck, CR-01 (2026-10-26): Path 2's thermal eligibility, decided across the equation of state's
    band, had no tables bound, so a changed table left it current. Bound now through the common producer; a
    fixed-point exclusion, which the tables do not decide, is bound to none and stays current."""
    from adroit.constraints import relic
    from adroit.parameter_space import certification
    s=spec()
    cls,p,_=classify(s)
    candidates=[signal.Candidate(label=str(m),mass_gev=m,model=s.name,spin=0) for m in (30,20)]
    req=signal.SignalRequest(experiment='toy',user_models=[signal.UserModel(spec=s,masses_gev=[30])])
    monkeypatch.setattr(eligibility,'_physical',lambda req,c,f,module,model:(cls,p.model_copy(update={'m_chi':c.mass_gev}),None,0.,0.))
    monkeypatch.setattr(eligibility,'_current_context',lambda *a:EvidenceContext(origin='captured',identity='current',code_sha256='code'))
    from adroit.parameter_space import scan
    monkeypatch.setattr(scan,'evaluate',lambda cls,p,*a,**k:point_result(p,excluded=p.m_chi==20))
    monkeypatch.setattr(relic,'band_values',lambda compute:{'upper':.1195,'lower':.1206})
    rows=eligibility.assess(req,candidates,[SimpleNamespace(label=c.label) for c in candidates],object())
    thermal,fixed=rows['30'].certificate,rows['20'].certificate
    assert rows['30'].status=='eligible' and set(thermal.bound.eos_tables)==set(relic.EOS_TABLES)
    assert rows['20'].status=='excluded_point' and fixed.bound.eos_tables=={}
    central=eos_copy/relic.EOS_TABLES['central'][0]
    central.write_bytes(central.read_bytes()+b'\n# changed\n')
    assert certification.reading(thermal,certification.current_bound(thermal)).startswith(
        "stale: the equation of state's central table is not the one it was certified with")
    assert certification.reading(fixed,certification.current_bound(fixed))=='certified'

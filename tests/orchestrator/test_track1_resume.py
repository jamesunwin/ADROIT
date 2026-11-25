"""Real checkpoint transitions with cheap independent model/constraint fixtures."""
import importlib

import pytest
from typer.testing import CliRunner

from adroit.core.checkpoint import Checkpoint
from adroit.core.model_spec import ModelSpec
from adroit.orchestrator import track1, cli, runs
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.coverage import CoverageSettings
from adroit.parameter_space.scan import Axis, PointResult


def request(coverage=None):
    return track1.Track1Request(spec=ModelSpec(name='fixture', fields=[{'name':'chi','role':'dark_matter','spin':.5,
                                                                   'dark_parity':-1}]), model_class=Spin1Class(),
        fixed=Point(m_chi=10,m_med=30), x=Axis(parameter='m_chi',low=10,high=40,n=2,log=False),
        y=Axis(parameter='g_chi',low=.1,high=.2,n=2,log=False), mediator_ratio=3,
        literature=False,workers=1,coverage=coverage)


def fixtures(monkeypatch):
    scan=importlib.import_module('adroit.parameter_space.scan')
    verdict=importlib.import_module('adroit.parameter_space.verdict')
    monkeypatch.setattr('adroit.orchestrator.track1_identity.dependencies',lambda:{'software':'fixture'})
    monkeypatch.setattr(Spin1Class,'omega_h2',lambda self,p:.006*p.m_chi)
    monkeypatch.setattr('adroit.parameter_space.searches.prefetch_lhc',lambda cls,points,*a:[None]*len(points))
    calls=[]
    def evaluate(cls,p,*args):
        calls.append(p)
        return PointResult(point=p,omega_h2=.006*p.m_chi,dd_kind='SI',dd_sigma_cm2=0,dd_limit_cm2=1,
                           excluded={'colliders (CMS)':False})
    monkeypatch.setattr(scan,'evaluate',evaluate)
    monkeypatch.setattr(verdict,'evaluate',evaluate)
    def plane(s,v,path,**kwargs):
        path.write_bytes(b'plot')
        return path
    monkeypatch.setattr(track1.plots,'plane',plane)
    monkeypatch.setattr(track1.plots,'direct_detection',lambda *a:None)
    return calls


@pytest.mark.needs("diamx", "cdmslite")
def test_partial_points_survive_interruption_and_complete_result_resumes_without_physics(tmp_path,monkeypatch):
    calls=fixtures(monkeypatch)
    original=Checkpoint.save
    def interrupted(self,phase,key,value):
        original(self,phase,key,value)
        if phase=='scan' and key=='1':
            raise RuntimeError('injected interruption')
    monkeypatch.setattr(Checkpoint,'save',interrupted)
    with pytest.raises(RuntimeError,match='injected'):
        track1.run(request(),tmp_path)
    assert len(calls)==2 and (tmp_path/'.track1-checkpoint/scan/1.json').exists()
    monkeypatch.setattr(Checkpoint,'save',original)
    resumed=track1.run(request(),tmp_path,resume=True)
    count=len(calls)
    assert len(resumed.scan.points)==4 and len(calls[:4])==4
    assert track1.run(request(),tmp_path,resume=True)==resumed and len(calls)==count
    assert all(point.m_med==3*point.m_chi for point in calls)


@pytest.mark.needs("diamx", "cdmslite")
@pytest.mark.needs("eos")
def test_optional_coverage_is_constrained_and_partial_coverage_prevents_exclusion(tmp_path,monkeypatch):
    fixtures(monkeypatch)
    verdict=importlib.import_module('adroit.parameter_space.verdict')
    original=verdict.evaluate
    def excluded(*args):
        return original(*args).model_copy(update={'excluded':{'test limit':True}})
    monkeypatch.setattr(verdict,'evaluate',excluded)
    result=track1.run(request(CoverageSettings(max_evaluations=3)),tmp_path)
    assert result.coverage.status=='partial' and result.verdict.level=='pending'
    assert any('coverage budget' in reason for reason in result.verdict.unresolved)
    text=track1.report(result)
    assert 'Optional resolution check' in text and 'normal constraint evaluation is additional' in text


@pytest.mark.needs("diamx", "cdmslite")
def test_bare_cli_resume_restores_request_and_refuses_silent_overrides(tmp_path,monkeypatch):
    fixtures(monkeypatch)
    track1.run(request(),tmp_path)
    called=[]
    monkeypatch.setattr(runs,'track1',lambda req,*a,**k:called.append((req,k)) or (tmp_path,'resumed'))
    runner=CliRunner()
    # R1: the fixture's explicit engine cannot be rebuilt from its one-field model, so resume refuses it...
    refused=runner.invoke(cli.app,['track1','--resume','--out',str(tmp_path)])
    assert refused.exit_code!=0 and 'cannot map the typed model' in refused.output and not called
    # ...unless the installed mapping gives that same engine (here a stand-in for classify).
    monkeypatch.setattr(track1,'rebuilt_class',lambda req:Spin1Class())
    result=runner.invoke(cli.app,['track1','--resume','--out',str(tmp_path)])
    # the saved request states the propagation model and the halo the run resolved (constraints.propagation,
    # parameter_space.halo_region: the tests' setting is the published halos)
    from adroit.constraints.propagation import chosen
    assert result.exit_code==0 and called[0][0]==request().model_copy(update={'propagation':chosen(),'halo':'published'})
    assert called[0][1]['resume']
    result=runner.invoke(cli.app,['track1','--resume','--out',str(tmp_path),'--coverage-depth','2'])
    assert result.exit_code!=0 and 'do not override' in result.output


@pytest.mark.eos_band
@pytest.mark.needs("diamx", "cdmslite")
def test_finer_closed_curve_roots_receive_actual_constraint_checks(tmp_path,monkeypatch):
    fixtures(monkeypatch)
    verdict=importlib.import_module('adroit.parameter_space.verdict')
    scan=importlib.import_module('adroit.parameter_space.scan')
    def omega(self,p):
        x,y=(p.m_chi-10)/30,(p.g_chi-.1)/.1
        return .12+.1*((x-.5)**2+(y-.5)**2-.16)
    monkeypatch.setattr(Spin1Class,'omega_h2',omega)
    checked=[]
    def evaluate(cls,p,*args):
        checked.append(p)
        return PointResult(point=p,omega_h2=omega(cls,p),dd_kind='SI',dd_sigma_cm2=0,dd_limit_cm2=1,
                           excluded={'colliders (CMS)':False})
    monkeypatch.setattr(scan,'evaluate',evaluate)
    monkeypatch.setattr(verdict,'evaluate',evaluate)
    result=track1.run(request(CoverageSettings()),tmp_path)
    assert len(result.coverage.root_attempts)==4 and result.verdict.level=='viable'
    # the 4 grid points, the 4 roots, and each root again at the upper and lower tables' roots in its cell (CA-01:
    # coverage roots are judged across the equation of state's band as the plane's are)
    assert len(result.verdict.crossings)==4 and len(checked)==16
    assert all(any(f.startswith("the equation of state's band: viable also") for f in c.flags) for c in result.verdict.crossings)
    assert all(root.kind=='contour' and root.converged for root in result.verdict.crossings)


@pytest.mark.needs("diamx", "cdmslite")
def test_changes_during_run_invalidate_epoch_and_prevent_resume(tmp_path,monkeypatch):
    fixtures(monkeypatch)
    calls=[]
    def dependencies():
        calls.append(1)
        return {'software':'a' if len(calls)==1 else 'b'}
    monkeypatch.setattr('adroit.orchestrator.track1_identity.dependencies',dependencies)
    with pytest.raises(ValueError,match='changed during'):
        track1.run(request(),tmp_path)
    monkeypatch.setattr('adroit.orchestrator.track1_identity.dependencies',lambda:{'software':'a'})
    with pytest.raises(ValueError,match='Resume refused'):
        track1.run(request(),tmp_path,resume=True)

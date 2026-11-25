"""Adaptive sampling compared with independently evaluated dense reference scans."""
import math

import numpy as np
import pytest
from scipy.ndimage import label

from adroit.core.checkpoint import Checkpoint
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.coverage import CoverageSettings, diagnose
from adroit.parameter_space.scan import Axis, ScanRequest


def request():
    return ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10,m_med=30),
        x=Axis(parameter='m_chi', low=10,high=40,n=3,log=False),
        y=Axis(parameter='g_chi',low=.1,high=.2,n=3,log=False), mediator_ratio=3, workers=1)


def xy(point):
    return (point.m_chi-10)/30, (point.g_chi-.1)/.1


def surface(x, y):
    return .12 + .3*min((x-cx)**2+(y-cy)**2-radius**2
                       for cx,cy,radius in ((.25,.25,.16),(.75,.75,.09)))


def settings(**changes):
    return CoverageSettings(strategy='adaptive',refinement_depth=3,max_evaluations=1500,**changes)


def test_two_disconnected_branches_match_independent_dense_scan(monkeypatch):
    monkeypatch.setattr(Spin1Class,'omega_h2',lambda self,p:surface(*xy(p)))
    coordinates = np.linspace(0,1,201)
    dense = np.array([[surface(x,y) for x in coordinates] for y in coordinates])
    assert label(dense < .12)[1] == 2
    result = diagnose(request(),settings())
    roots = [root for root in result.root_attempts if root.converged]
    assert result.status == 'adaptive_sampling_complete'
    assert roots and all(root.relative_residual < 1e-7 for root in roots)
    for cx,cy,radius in ((.25,.25,.16),(.75,.75,.09)):
        assert any(abs(math.hypot(xy(r.point)[0]-cx,xy(r.point)[1]-cy)-radius)<1e-6 for r in roots)
    assert len(result.samples) < result.planned_samples
    assert any(c.decision=='not_selected' for c in result.cells)
    assert all(r.point.m_med==3*r.point.m_chi for r in roots)


def test_tangent_and_a_narrow_loop_found_with_declared_exploration(monkeypatch):
    # The first-resolution nodes do not encounter the small loop; depth-two
    # exploration puts a probe at its independently specified centre.
    def narrow(x,y):
        return .12 + .2*((x-.125)**2+(y-.125)**2-.035**2)
    monkeypatch.setattr(Spin1Class,'omega_h2',lambda self,p:narrow(*xy(p)))
    dense = np.array([[narrow(x,y) for x in np.linspace(0,1,257)] for y in np.linspace(0,1,257)])
    assert label(dense<.12)[1]==1
    result=diagnose(request(),settings(exploration_depth=2))
    assert any(r.converged for r in result.root_attempts)
    monkeypatch.setattr(Spin1Class,'omega_h2',lambda self,p:.12+(xy(p)[0]-.25)**2+(xy(p)[1]-.25)**2)
    tangent=diagnose(request(),settings())
    assert any(r.converged and xy(r.point)==pytest.approx((.25,.25),abs=1e-12) for r in tangent.root_attempts)


def test_partial_budget_and_unavailable_region_remain_explicit(monkeypatch):
    calls=[]
    def omega(self,p):
        calls.append(p)
        return surface(*xy(p))
    monkeypatch.setattr(Spin1Class,'omega_h2',omega)
    result=diagnose(request(),settings().model_copy(update={'max_evaluations':30}))
    assert result.status=='partial' and result.unresolved
    assert len(calls)==result.evaluations<=30
    assert any(c.decision=='not_sampled' for c in result.cells)
    monkeypatch.setattr(Spin1Class,'omega_h2',lambda self,p:None if xy(p)[0]<.3 else surface(*xy(p)))
    missing=diagnose(request(),settings())
    assert missing.status=='partial' and any(c.decision=='unresolved' for c in missing.cells)
    assert all(r.point and r.omega_h2 is not None for r in missing.root_attempts if r.converged)


def test_interrupted_adaptive_run_reuses_samples_and_preserves_cap(tmp_path,monkeypatch):
    req, opts=request(),settings()
    checkpoint=Checkpoint(tmp_path,{'request':req.model_dump(mode='json'),'settings':opts.model_dump()}, {})
    calls=[]
    def omega(self,p):
        calls.append(p)
        return surface(*xy(p))
    monkeypatch.setattr(Spin1Class,'omega_h2',omega)
    expected=diagnose(req,opts)
    calls.clear()
    original=Checkpoint.save
    def save(self,phase,key,value):
        original(self,phase,key,value)
        if phase=='coverage-samples' and len(calls)==5:
            raise RuntimeError('injected interruption')
    monkeypatch.setattr(Checkpoint,'save',save)
    with pytest.raises(RuntimeError,match='injected'):
        diagnose(req,opts,checkpoint)
    monkeypatch.setattr(Checkpoint,'save',original)
    restored=Checkpoint(tmp_path,checkpoint.manifest.inputs,{},resume=True)
    actual=diagnose(req,opts,restored)
    assert actual==expected and actual.evaluations==len(calls)
    count=len(calls)
    assert diagnose(req,opts,restored)==actual and len(calls)==count


def test_discontinuous_threshold_is_not_certified_and_log_nodes_stay_exact(monkeypatch):
    monkeypatch.setattr(Spin1Class,'omega_h2',lambda self,p:.05 if p.m_chi<23. else .2)
    result=diagnose(request(),settings())
    assert result.status=='partial' and not any(r.converged for r in result.root_attempts)
    assert any('residual' in r.reason for r in result.root_attempts)
    req=request().model_copy(update={'x':Axis(parameter='m_chi',low=50,high=200,n=3,log=True)})
    monkeypatch.setattr(Spin1Class,'omega_h2',lambda self,p:.12+p.g_chi-.15)
    result=diagnose(req,settings())
    assert result.xs[::8]==req.x.values()
    assert all(r.point.m_med==3*r.point.m_chi for r in result.root_attempts if r.converged)
    with pytest.raises(ValueError,match='exploration'):
        CoverageSettings(strategy='adaptive',refinement_depth=1,exploration_depth=2)

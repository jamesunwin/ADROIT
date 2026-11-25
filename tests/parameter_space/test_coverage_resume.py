"""Coverage checkpoints preserve sampled data and budget reservations across interruption."""
import pytest

from adroit.core.checkpoint import Checkpoint
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.coverage import CoverageSettings, diagnose
from adroit.parameter_space.scan import ScanRequest, Axis


def test_completed_samples_are_reused_and_density_cap_does_not_reset(tmp_path,monkeypatch):
    request=ScanRequest(model_class=Spin1Class(),fixed=Point(m_chi=10,m_med=30),
        x=Axis(parameter='m_chi',low=10,high=40,n=2,log=False),
        y=Axis(parameter='g_chi',low=.1,high=.2,n=2,log=False),mediator_ratio=3)
    settings=CoverageSettings(max_evaluations=50)
    checkpoint=Checkpoint(tmp_path,{'request':request.model_dump(mode='json'),'settings':settings.model_dump()}, {})
    calls=[]
    def omega(self,p):
        calls.append(p)
        return .006*p.m_chi
    monkeypatch.setattr(Spin1Class,'omega_h2',omega)
    original=Checkpoint.save
    def interrupted(self,phase,key,value):
        original(self,phase,key,value)
        if phase=='coverage-samples' and key=='2':
            raise RuntimeError('interruption after a completed sample')
    monkeypatch.setattr(Checkpoint,'save',interrupted)
    with pytest.raises(RuntimeError,match='interruption'):
        diagnose(request,settings,checkpoint)
    assert len(calls)==3
    monkeypatch.setattr(Checkpoint,'save',original)
    resumed=Checkpoint(tmp_path,checkpoint.manifest.inputs,{},resume=True)
    result=diagnose(request,settings,resumed)
    count=len(calls)
    assert result.evaluations==count and count<=50
    assert all(p.m_med==3*p.m_chi for p in calls)
    assert diagnose(request,settings,resumed)==result and len(calls)==count


def test_a_cached_root_is_keyed_by_its_bracket_and_checked_against_it(tmp_path,monkeypatch):
    """Release audit minor: roots were reused by their index in the candidate list."""
    from adroit.core.checkpoint import CheckpointMismatch
    request=ScanRequest(model_class=Spin1Class(),fixed=Point(m_chi=10,m_med=30),
        x=Axis(parameter='m_chi',low=10,high=40,n=3,log=False),
        y=Axis(parameter='g_chi',low=.1,high=.2,n=3,log=False),mediator_ratio=3)
    settings=CoverageSettings(max_evaluations=400)
    monkeypatch.setattr(Spin1Class,'omega_h2',lambda self,p:.006*p.m_chi)
    checkpoint=Checkpoint(tmp_path,{'request':request.model_dump(mode='json'),'settings':settings.model_dump()},{})
    saved={}
    original=Checkpoint.save
    def spy(self,phase,key,value):
        if phase=='coverage-roots':
            saved[key]=value
        original(self,phase,key,value)
    monkeypatch.setattr(Checkpoint,'save',spy)
    diagnose(request,settings,checkpoint)
    assert saved and all('-' in key and '_' in key for key in saved)
    key,root=next((k,r) for k,r in saved.items() if r.point is not None and r.coordinate is not None)
    moved=root.model_copy(update={'point':root.point.model_copy(update={'g_chi':root.point.g_chi*1.5})})
    load=Checkpoint.load
    monkeypatch.setattr(Checkpoint,'load',lambda self,phase,k,model:moved if (phase,k)==('coverage-roots',key) else load(self,phase,k,model))
    resumed=Checkpoint(tmp_path,checkpoint.manifest.inputs,{},resume=True)
    with pytest.raises(CheckpointMismatch,match='bracket'):
        diagnose(request,settings,resumed)

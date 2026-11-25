"""Real detector coherence, legacy restrictions and honest native-domain limits."""
import pytest

from adroit.core.fit_domain import PhysicalDomain, FitCoordinate, DomainFitSettings
from adroit.core.model_spec import PhysicalFitRange
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.physical_fit import FitSettings
from adroit.parameter_space import native_joint as j
from adroit.experiments.registry import load_module


@pytest.mark.parametrize('null,masses',[(j.NULL,[50.,70.]),(j.LOW_MASS_NULL,[6.,10.])])
def test_native_named_domain_retains_pair_physics_and_one_dimensional_restrictions(null,masses):
    p=Point(m_chi=masses[0],m_med=125,g_chi=.001,g_q=.25)
    bounds=PhysicalFitRange(low=0,high=.003)
    domain=PhysicalDomain(coordinates=[FitCoordinate(parameter='m_chi',values=masses),
                                       FitCoordinate(parameter='g_chi',low=0,high=.003)])
    r=j.run(Spin1Class(),p,masses,bounds,j.JointSettings(null_experiment=null,domain=domain),FitSettings(),.5)
    assert r.complete and r.domain_fit.resolved,r.omitted
    assert r.calibration is None and r.bounds is None
    signal,search=load_module(j.SIGNAL),load_module(null)
    for mode in r.domain_fit.modes:
        template=j.prepare(Spin1Class(),mode.point,bounds,signal,search,.5)
        old=j.fit_pair(template,j.observed_data(signal),FitSettings())
        assert old.resolved,old.reason
        assert mode.log_l==pytest.approx(old.log_l,abs=1e-5)
    assert sum(r.log_l_components.values())==pytest.approx(r.domain_fit.log_l,abs=1e-6)


def test_missing_mass_coverage_and_continuous_mass_are_not_silently_trimmed():
    p=Point(m_chi=10,m_med=125,g_chi=.001)
    for axis,masses in [(FitCoordinate(parameter='m_chi',values=[10,50]),[10.,50.]),
                        (FitCoordinate(parameter='m_chi',low=50,high=70),[50.,70.])]:
        d=PhysicalDomain(coordinates=[axis,FitCoordinate(parameter='g_chi',low=0,high=.001)])
        r=j.run(Spin1Class(),p,masses,PhysicalFitRange(low=0,high=.001),
                j.JointSettings(domain=d),FitSettings(),.5)
        assert not r.complete and r.calibration is None and 'domain' in r.omitted
        assert r.domain_fit is None


def test_domain_budget_exhaustion_preserves_incomplete_status_and_no_tail():
    p=Point(m_chi=10,m_med=125,g_chi=.001)
    d=PhysicalDomain(coordinates=[FitCoordinate(parameter='g_chi',low=0,high=.003)])
    r=j.run(Spin1Class(),p,[10.],PhysicalFitRange(low=0,high=.003),
        j.JointSettings(null_experiment=j.LOW_MASS_NULL,domain=d,
                        domain_settings=DomainFitSettings(max_evaluations=5)),FitSettings(),.5)
    assert not r.complete and not r.domain_fit.resolved and r.calibration is None
    assert 'budget' in r.domain_fit.reason


@pytest.mark.parametrize('wrong_point,wrong_search',[(True,False),(False,True)])
def test_saved_native_template_must_match_point_and_search(wrong_point,wrong_search):
    from adroit.parameter_space.native_domain import evaluator
    from adroit.core.checkpoint import CheckpointMismatch
    signal,null=load_module(j.SIGNAL),load_module(j.LOW_MASS_NULL)
    p=Point(m_chi=50,m_med=125,g_chi=.001,g_q=.25)
    t=j.prepare(Spin1Class(),p.model_copy(update={'m_med':100 if wrong_point else 125}),
                PhysicalFitRange(low=0,high=1),signal,load_module(j.NULL) if wrong_search else null,.5)
    class Cache:
        def load(self,*args):return t
    evaluate,_=evaluator(Spin1Class(),.5,signal,null,j.observed_data(signal),Cache())
    with pytest.raises(CheckpointMismatch,match='Point/search'):
        evaluate(p)

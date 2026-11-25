"""Gate failures and effective record policy must survive orchestration."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.orchestrator import single_idea as idea

ROOT = Path(__file__).resolve().parents[2]


def test_dm13_injected_failure_exits_nonzero(tmp_path) -> None:
    source = f'''import importlib.util,sys
from pathlib import Path
s=importlib.util.spec_from_file_location("gate",{str(ROOT/'docs/dm13/gate.py')!r})
g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
g.g1=lambda:[{{"pass":False}}]
g.g2=lambda:[{{"pass":True}}]
g.g4=lambda folder:[{{"pass":True}}]
g.g3=lambda folder:{{"test":{{"pass":True}}}}
sys.argv=["gate","--out",{str(tmp_path)!r}]
sys.exit(g.main())
'''
    process = subprocess.run([sys.executable,'-c',source],capture_output=True,text=True)
    assert process.returncode == 1
    assert 'NOT PASSED' in process.stdout


def test_dm13_cms_rule_keeps_interior_exclusions_and_requires_pending_frame() -> None:
    import importlib.util
    from adroit.constraints import verdicts
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.verdict import Crossing, Verdict
    spec = importlib.util.spec_from_file_location('dm13_gate',ROOT/'docs/dm13/gate.py')
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    interior = Crossing(point=Point(m_chi=100,m_med=500),status='excluded',
                        excluded_by=['colliders (CMS)'])
    edge = Crossing(point=Point(m_chi=2000,m_med=1651),status='pending',
                    flags=[verdicts.EDGE_FLAG],pending=['colliders (CMS): outside the summary source plane'])
    v = Verdict(level='viable_pending',summary='test',target=.12,crossings=[interior,edge])
    result = gate.cms_contour_check(v)
    assert result['pass'] and result['cms_in_source_plane']=='1/1'
    assert result['cms_200_1800']=='1/2' and result['source_frame_policy_pass']
    for broken in (edge.model_copy(update={'flags':[]}),edge.model_copy(update={'status':'viable'}),
                   edge.model_copy(update={'pending':[]}),
                   edge.model_copy(update={'pending':['colliders (SModelS): missing coverage']})):
        assert not gate.cms_contour_check(v.model_copy(update={'crossings':[interior,broken]}))['pass']
    assert not gate.cms_contour_check(v.model_copy(update={'crossings':[
        interior.model_copy(update={'excluded_by':[]}),edge]}))['pass']


@pytest.mark.usefixtures("resigned")
@pytest.mark.needs("solar_model")
def test_dm13_pseudoscalar_rule_requires_actual_mixture_and_pending_spectrum(awaiting) -> None:
    # The gate's premise: without the 2023 spectral likelihood, a mixed spectrum is pending (or decided by the
    # mixture rule), whether or not the owner has since signed that record.
    awaiting("fermi-2311.04982-spectral")
    import importlib.util
    from adroit.parameter_space.classes import Point, ScalarClass
    from adroit.parameter_space.scan import evaluate
    from adroit.parameter_space.verdict import Verdict, classify
    spec = importlib.util.spec_from_file_location('dm13_gate',ROOT/'docs/dm13/gate.py')
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    cls = ScalarClass(dm_pseudoscalar=True,sm_pseudoscalar=True,name='pseudoscalar')
    crossings = [classify(cls,evaluate(cls,Point(m_chi=m,m_med=100,g_chi=1,g_q=1)))
                 for m in (25.,300.)]
    v = Verdict(level='viable_pending',summary='test',target=.12,crossings=crossings)
    result = gate.pseudoscalar_contour_check(cls,v)
    assert result['pass'] and all(c['channels']['c'] > 0 and c['channels']['b'] > 0
                                  for c in result['cases'])
    # 25 GeV: its b-quark share alone exceeds the bb curve (the conservative mixture rule), never the whole rate
    assert "exceeds its own curve" in result['cases'][0]['mixture_rule']
    assert result['cases'][1]['spectral_coverage_pending'] and not result['cases'][1]['mixture_rule']
    for broken in (crossings[1].model_copy(update={'pending':[]}),
                   crossings[1].model_copy(update={'status':'viable'}),
                   crossings[1].model_copy(update={'excluded_by':['gamma rays (Fermi-LAT dwarfs)']})):
        assert not gate.pseudoscalar_contour_check(cls,v.model_copy(
            update={'crossings':[crossings[0],broken]}))['pass']
    assert not gate.pseudoscalar_contour_check(cls,v.model_copy(
        update={'crossings':[crossings[0].model_copy(update={'status':'viable'}),crossings[1]]}))['pass']


@pytest.mark.usefixtures("resigned")
@pytest.mark.needs("diamx", "solar_model")
def test_cms_frame_reason_survives_an_independent_pending_smodels_record(awaiting) -> None:
    """The dijet records are held unverified: once signed they exclude this point (A1, 1.68 TeV, g_q = 0.25), and the
    test is about the CMS frame's reason beside a pending SModelS record."""
    awaiting("cms-1806.00843-dijet", "atlas-1910.08447-dijet-gaussian")
    from adroit.constraints import verdicts
    from adroit.constraints.spin1 import Spin1Kind
    from adroit.parameter_space.classes import Point, Spin1Class
    from adroit.parameter_space.scan import evaluate
    from adroit.parameter_space.verdict import classify
    cls=Spin1Class(kind=Spin1Kind.axial,name='A1')
    p=Point(m_chi=2000.,m_med=1681.7063311461354,g_chi=1.,g_q=.25)
    point=evaluate(cls,p)
    crossing=classify(cls,point)
    assert point.excluded['colliders (CMS)'] is None
    assert verdicts.EDGE_FLAG in crossing.flags and crossing.status=='pending'
    assert any('colliders (CMS)' in reason and 'outside the summary' in reason for reason in crossing.pending)
    assert any('SModelS' in reason for reason in crossing.pending)


def test_dm13_distinguishes_the_historical_higgs_input_from_the_canonical_portal(tmp_path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location('dm13_gate',ROOT/'docs/dm13/gate.py')
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    result=gate.unsupported_class_check(tmp_path)
    assert result['pass'] and result['undetermined']=='7/7'
    assert result['canonical_higgs_portal_supported']
    assert next(r for r in result['cases'] if r['id']=='G4')['reason']


def test_portal_gate_refuses_underspecified_field_sketches(monkeypatch) -> None:
    import ast
    import importlib.util
    from adroit.parameter_space import classify, library
    path = ROOT/'docs/portals/gate.py'
    spec = importlib.util.spec_from_file_location('portal_gate',path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    fn = next(n for n in ast.parse(path.read_text()).body
              if isinstance(n,ast.FunctionDef) and n.name=='p4')
    cases = ast.literal_eval(next(n.value for n in fn.body if isinstance(n,ast.Assign)
                                  and any(isinstance(t,ast.Name) and t.id=='cases' for t in n.targets)))
    result = gate.typed_mapping_check(cases)
    assert result['pass'] and len(result['pending_reasons'])==4
    original = classify.classify
    def substituted(spec):
        if spec.name=='dark photon':
            e = library.entry('dark_photon_dirac')
            return e.model_class,e.point,[]
        return original(spec)
    monkeypatch.setattr(classify,'classify',substituted)
    assert not gate.typed_mapping_check(cases)['pass']


@pytest.mark.parametrize('unverified',[False,True])
@pytest.mark.needs("diamx", "cdmslite", "solar_model")
def test_single_idea_effective_policy_reaches_point_thermal_and_nested_track(tmp_path,monkeypatch,unverified) -> None:
    spec = ModelSpec.model_validate(yaml.safe_load((ROOT/'docs/dm13/vector_mediator.yaml').read_text()))
    seen = {'point':[], 'thermal':[], 'null':[]}
    judge, thermal, combine = idea.judge_point, idea._thermal, idea.path2._combine
    def point(cls,p,flag,*args,**kwargs):
        seen['point'].append(flag)
        return judge(cls,p,flag,*args,**kwargs)
    def roots(cls,p,band,target,module,spin,flag):
        seen['thermal'].append(flag)
        return thermal(cls,p,band,target,module,spin,flag)
    def null(module,c,fit,request):
        seen['null'].append(request.unverified_records)
        return combine(module,c,fit,request)
    monkeypatch.setattr(idea,'judge_point',point)
    monkeypatch.setattr(idea,'_thermal',roots)
    monkeypatch.setattr(idea.path2,'_combine',null)
    result = idea.run(idea.SingleIdeaRequest(spec=spec,experiment='CDMS II Si (2013)',
        masses_gev=[7.,9.,12.],null_modules=[],toys=20,grid=4,workers=1,literature=False,
        unverified_records=unverified),tmp_path)
    assert result.track1.request.unverified_records is unverified
    assert result.track1.scan.request.unverified_records is unverified
    assert all(flags and all(f is unverified for f in flags) for flags in seen.values())


def test_legacy_reference_discovery_matches_driver(monkeypatch,tmp_path) -> None:
    from adroit.external import fetch
    from adroit.external.manifest import ExternalItem
    legacy = tmp_path/'data/external/WIMpy_NREFT'
    legacy.mkdir(parents=True)
    monkeypatch.setattr(fetch,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(fetch,'get_settings',lambda:type('S',(),{'tools_dir':tmp_path/'tools'})())
    item = ExternalItem(name='WIMpy_NREFT',purpose='reference',obtain='git',source='upstream',
                        repo_folder='data/external/WIMpy_NREFT')
    assert fetch.folder_of(item) == legacy


def test_dm14_gate_separates_resolved_fit_exclusions_from_incomplete_thermal_coverage() -> None:
    import importlib.util
    import numpy as np
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space import simplified
    loader = importlib.util.spec_from_file_location('dm14_gate', ROOT/'docs/dm14/gate.py')
    gate = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(gate)
    masses = np.geomspace(5, 40, 12).tolist()
    rows = [idea.BandPoint(m_chi=m, s_hat=1, events_at_unit=1, mu_hat=1, mu_68=(.5, 1.5),
            z_local=2, point=Point(m_chi=m, m_med=1000, g_chi=1, g_q=.25), m_med=1000, fitted_value=1,
            spectrum_relative_error=0, delta_log_l_error=0, omega_h2=10, status='excluded',
            excluded_by=['direct detection']) for m in masses]
    rows[0] = rows[0].model_copy(update={'point':None, 'omega_h2':None, 'fitted_value':None, 'm_med':None,
        'excluded_by':[], 'status':'pending',
        'inversion_reason':'fitted amplitude lies outside the perturbative g_chi branch'})
    result = idea.SingleIdeaResult(request=idea.SingleIdeaRequest(experiment='CDMS II Si (2013)',
        spec=simplified.model('vector', 10, 1000), masses_gev=masses), band=rows,
        best=f'vector_mediator@{masses[3]!r}', level='undetermined', fit_quality='fits',
        constraint_compatibility='pending', thermal_viability='undetermined',
        thermal_pending=['some fitted masses lack a physical inversion or relic calculation'])
    assert all(row['pass'] for row in gate.single_idea_check(result, idea.report(result)).values())
    for broken in (result.model_copy(update={'level':'excluded'}),
                   result.model_copy(update={'thermal_pending':[]}),
                   result.model_copy(update={'band':[rows[0].model_copy(update={'inversion_reason':''})]+rows[1:]}),
                   result.model_copy(update={'band':rows[:1]+[rows[1].model_copy(update={'excluded_by':[]})]+rows[2:]}),
                   result.model_copy(update={'band':rows[:1]+[rows[1].model_copy(update={'spectrum_relative_error':.01})]+rows[2:]})):
        assert not gate.single_idea_check(broken, idea.report(broken))['b']['pass']
    assert not gate.single_idea_check(result, 'thermal-relic contour')['c']['pass']


def test_dm14_injected_failure_exits_nonzero(tmp_path) -> None:
    source = f'''import importlib.util,sys
from pathlib import Path
s=importlib.util.spec_from_file_location("gate",{str(ROOT/'docs/dm14/gate.py')!r})
g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
g.g1=lambda folder:{{"case":{{"pass":False}}}}
g.g2=lambda:{{"pass":True}}
g.g4=lambda folder:{{"pass":True}}
g.g3=lambda folder:{{"case":{{"pass":True}}}}
sys.argv=["gate","--out",{str(tmp_path)!r}]
sys.exit(g.main())
'''
    process = subprocess.run([sys.executable, '-c', source], capture_output=True, text=True)
    assert process.returncode == 1
    assert 'NOT PASSED' in process.stdout


def test_dm15_injected_failure_exits_nonzero(tmp_path) -> None:
    source = f'''import importlib.util,sys
from pathlib import Path
s=importlib.util.spec_from_file_location("gate",{str(ROOT/'docs/dm15/gate.py')!r})
g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
g.tests=lambda spec:{{"pass":False}}
g.workspace=lambda root:root
g.g5=lambda root:{{"pass":True}}
sys.argv=["gate","--out",{str(tmp_path)!r}]
sys.exit(g.main())
'''
    process = subprocess.run([sys.executable, '-c', source], capture_output=True, text=True)
    assert process.returncode == 1
    assert 'NOT PASSED' in process.stdout

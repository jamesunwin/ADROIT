"""Adaptive CLI/workbench requests and resume overrides are unambiguous."""
from typer.testing import CliRunner
import pytest

from adroit.orchestrator.cli import app
from adroit.orchestrator import runs
from adroit.ui import forms


def test_cli_carries_adaptive_settings_and_refuses_resume_overrides(tmp_path,monkeypatch):
    found=[]
    def run(request,folder,*args,**kwargs):
        found.append(request)
        return folder,'report'
    monkeypatch.setattr(runs,'track1',run)
    args=['track1','--portal','higgs_portal_scalar','--coverage-strategy','adaptive','--coverage-depth','3',
          '--coverage-exploration','2','--coverage-budget','1500','--out',str(tmp_path)]
    result=CliRunner().invoke(app,args)
    assert result.exit_code==0,result.output
    assert found[0].coverage.strategy=='adaptive' and found[0].coverage.exploration_depth==2
    assert found[0].coverage.max_evaluations==1500
    result=CliRunner().invoke(app,['track1','--resume','--out',str(tmp_path),'--coverage-strategy','adaptive'])
    assert result.exit_code!=0 and 'override' in result.output
    result=CliRunner().invoke(app,['track1','--portal','higgs_portal_scalar','--coverage-strategy','adaptive'])
    assert result.exit_code!=0 and 'coverage-depth' in result.output


def test_workbench_forms_carry_strategy_and_validate_depths(tmp_path):
    command=forms.portal_command('higgs_portal_scalar',tmp_path,coverage_depth=3,coverage_budget=1500,
                                 coverage_strategy='adaptive',coverage_exploration=2)
    assert command[command.index('--coverage-strategy')+1]=='adaptive'
    assert command[command.index('--coverage-exploration')+1]=='2'
    with pytest.raises(ValueError,match='exploration'):
        forms.portal_command('higgs_portal_scalar',tmp_path,coverage_depth=1,
                             coverage_strategy='adaptive',coverage_exploration=2)

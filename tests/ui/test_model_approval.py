"""Actual UI approvals and scan review preserve canonical models and fixed coordinates."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from nicegui.testing import User

from adroit.orchestrator import ideas,studies,cli
from adroit.core.model_spec import ModelSpec
from adroit.ui import engine
from adroit.ui.app import build_pages


def workspace(tmp_path):
    root=tmp_path/'runs'
    folder=root/'idea'
    folder.mkdir(parents=True)
    fields=ModelSpec.model_validate({'name':'supplied_singlet','fields':[{'name':'S','role':'dark_matter',
        'spin':0,'self_conjugate':True,'dark_parity':-1,'mass_gev':70}]})
    general=ideas.from_fields(fields).general
    spec=general.model_copy(update={'couplings':[c.model_copy(update={'value':.2}) for c in general.couplings]})
    result=ideas.run(ideas.IdeaRequest(lagrangian_spec=spec))
    (folder/'result.json').write_text(result.model_dump_json())
    studies.record(folder,'idea','Supplied singlet')
    return root,folder,spec


def launches(monkeypatch):
    found=[]
    def launch(command,folder,title,**kwargs):
        found.append((command,folder,title))
        folder.mkdir(parents=True,exist_ok=True)
        engine.save(engine.Job(folder=str(folder),command=command,title=title,kind=command[0],status='completed',returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine,'launch',launch)
    return found


async def test_ui_approval_passes_exact_model_and_model_aware_review_to_cli(user:User,tmp_path,monkeypatch):
    root,folder,spec=workspace(tmp_path)
    calls=launches(monkeypatch)
    build_pages(root)
    await user.open('/study?path=idea')
    await user.should_see('Supplied Lagrangian preserved')
    await user.should_see('Scan setup: active coordinates')
    user.find('Constrain the approved models').click()
    await user.should_see('run(s) constraining the reviewed models started')
    assert len(calls)==1
    command=calls[0][0]
    actual=cli._spec(Path(command[1]))
    assert actual==spec
    assert '--approved-model-hash' in command and '--reviewed-scan-hash' in command
    axes=[command[command.index(option)+1].split(':')[0] for option in ('--x','--y')]
    assert set(axes)=={'m_chi','g_chi'} and 'm_med' not in axes


async def test_generated_completion_requires_explicit_choice_and_displays_changes(user:User,tmp_path,monkeypatch):
    root,folder,spec=workspace(tmp_path)
    calls=launches(monkeypatch)
    build_pages(root)
    await user.open('/study?path=idea')
    user.find('Use generated general completion for supplied_singlet').click()
    # the owner, 2026-11-21: the generated completion's couplings have no values, so it cannot run, is said so, and
    # cannot be constrained (it had been launched with every coupling empty)
    await user.should_see('Cannot run yet: it can be saved once these are settled')
    await user.should_see('Complete it in the model library')
    user.find('Constrain the approved models').click()
    await user.should_see('tick at least one valid model')
    assert not calls


async def test_changed_source_list_refuses_stale_approval(user:User,tmp_path,monkeypatch):
    root,folder,spec=workspace(tmp_path)
    calls=launches(monkeypatch)
    build_pages(root)
    await user.open('/study?path=idea')
    (folder/'result.json').write_text((folder/'result.json').read_text()+'\n')
    user.find('Constrain the approved models').click()
    await user.should_see('source model list changed')
    assert not calls


async def test_inactive_axis_is_shown_and_cannot_launch(user:User,tmp_path,monkeypatch):
    root,folder,spec=workspace(tmp_path)
    calls=launches(monkeypatch)
    build_pages(root)
    await user.open('/study?path=idea')
    user.find('supplied_singlet: x axis').type('m_med:10:10000:log:2')
    await user.should_see('m_med is fixed or unused')
    user.find('Constrain the approved models').click()
    await user.should_see('tick at least one valid model')
    assert not calls


@pytest.mark.needs("cresst", "cdmslite", "optimum_interval", "solar_model")
async def test_the_scan_setup_is_shown_and_scan_accepts_it(user:User,tmp_path,monkeypatch):
    """The owner (2026-11-22): no separate "Review scan setup" button; the setup is shown as soon as there is a model,
    and pressing Scan accepts it. The run receives the hash of the setup it scans."""
    root,folder,spec=workspace(tmp_path)
    calls=launches(monkeypatch)
    (root/'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('Scan setup: active coordinates')
    await user.should_see('pressing Scan accepts it')
    await user.should_not_see('Review scan setup')
    user.find(marker='run_model_scan').click()
    await user.should_see('Run: model')
    assert len(calls)==1 and '--reviewed-scan-hash' in calls[0][0]


@pytest.mark.needs("cresst", "cdmslite", "optimum_interval", "solar_model")
async def test_a_changed_axis_is_what_scan_runs(user:User,tmp_path,monkeypatch):
    """An axis typed directly is what Scan runs (its setup computed when Scan is pressed): never the setup shown
    before the change (S18-08's guarantee, without a review step)."""
    root,folder,spec=workspace(tmp_path)
    calls=launches(monkeypatch)
    (root/'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('Scan setup: active coordinates')
    user.find('x axis').elements.pop().value='m_chi:70:90:log:2'
    user.find(marker='run_model_scan').click()
    await user.should_see('Run: model')
    assert len(calls)==1 and 'm_chi:70:90:log:2' in calls[0][0]

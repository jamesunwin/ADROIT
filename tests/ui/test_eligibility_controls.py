from nicegui.testing import User
from adroit.ui.app import build_pages
from tests.ui.test_model_library import capture

async def test_physical_budget_and_exact_reuse_inputs_reach_cli(user:User,tmp_path,monkeypatch):
    calls=capture(monkeypatch)
    build_pages(tmp_path/'runs')
    await user.open('/new/track2')
    user.find('Physical candidate assessment budget').elements.pop().value=7
    user.find('Saved results of constraining a model').elements.pop().value='saved/a/result.json\nsaved/b/result.json'
    user.find('Fit, combine and rank').click()
    await user.should_see('Run:')
    command=calls[0]
    assert command[command.index('--eligibility-budget')+1]=='7'
    assert [command[i+1] for i,v in enumerate(command) if v=='--track1-result']==['saved/a/result.json','saved/b/result.json']

from nicegui.testing import User
from adroit.ui.app import build_pages
from tests.orchestrator.test_reanalysis import parent
from tests.ui.test_model_library import capture

async def test_reopen_review_fresh_run_and_stale_editor_gate(user:User,tmp_path,monkeypatch):
    root=tmp_path/'runs'
    root.mkdir()
    path=parent(root)
    calls=capture(monkeypatch)
    build_pages(root)
    await user.open('/reanalyse')
    user.find('Saved study/result').elements.pop().value=str(path)
    user.find('Reopen saved inputs').click()
    await user.should_see('Immutable draft:')
    user.find('Run fresh reviewed child analysis').click()
    assert not calls
    user.find('Save changes / review this draft').click()
    user.find('Analysis reviewer name').elements.pop().value='Fixture'
    user.find('I reviewed the exact model').click()
    user.find('Run fresh reviewed child analysis').click()
    await user.should_see('Run: Reanalysis track1')
    assert calls[0][:2]==['reanalyse','run'] and '--expected-hash' in calls[0] and '--confirmed' in calls[0]
    assert '--budget' not in calls[0]

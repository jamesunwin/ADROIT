from urllib.parse import urlencode
from nicegui.testing import User
from adroit.ui.app import build_pages
from adroit.core.config import get_settings
from tests.private_search_fixtures import fixture,eligible
from adroit.library import experimental_profiles as profiles
from tests.ui.test_model_library import capture

async def test_explicit_profile_review_save_activate_and_pinned_track2(user:User,tmp_path,monkeypatch):
    catalog,r=fixture(tmp_path/'signal')
    sig=eligible(catalog,r)
    _,r=fixture(tmp_path/'null','null',catalog=catalog)
    null=eligible(catalog,r,'null')
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    calls=capture(monkeypatch)
    build_pages(tmp_path/'runs')
    await user.open('/experiments/profiles')
    user.find('Profile name').elements.pop().value='Controlled profile'
    user.find('Exact signal search').elements.pop().value=sig.reference
    user.find('Complete null-search selection').elements.pop().value=[null.reference]
    user.find('Selection reviewer name').elements.pop().value='Fixture'
    user.find('Review exact selection').click()
    user.find('Save reviewed profile').click()
    assert not list(catalog.path('profiles').glob('*.json'))
    user.find('I checked independence').click()
    user.find('I reviewed the source and adapter').click()
    user.find('Save reviewed profile').click()
    await user.should_see('Immutable profile saved')
    user.find('Apply this pinned selection').click()
    user.find('Activate saved profile').click()
    selected=profiles.active(catalog)
    assert selected
    await user.open('/new/track2')
    await user.should_see('Pinned personal experimental profile')
    user.find('Fit, combine and rank').click()
    await user.should_see('Run:')
    assert calls[0][calls[0].index('--profile')+1]==selected
    assert calls[0][calls[0].index('--experiment')+1]==sig.reference

async def test_private_event_review_validation_is_separate(user:User,tmp_path,monkeypatch):
    catalog,r=fixture(tmp_path/'signal')
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    build_pages(tmp_path/'runs')
    await user.open('/experiments/view?'+urlencode({'reference':r.reference}))
    user.find('Validate independent event/response/interval anchors ($0)').click()
    await user.should_see('Event adapter validation: True')
    assert not list(catalog.path('reviews').glob('*.json'))
    user.find('Prepare pinned private-search selection').click()
    assert not list(catalog.path('searches').glob('*.json'))

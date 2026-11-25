from urllib.parse import urlencode
from types import SimpleNamespace
from nicegui.testing import User
from adroit.ui.app import build_pages
from adroit.ui import engine
from adroit.core.config import get_settings
from tests.private_limit_fixtures import fixture,eligible

async def test_expert_review_gate_and_independent_validation_are_distinct(user: User,tmp_path,monkeypatch):
    catalog,r=fixture(tmp_path)
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    build_pages(tmp_path/'runs')
    await user.open('/experiments/view?'+urlencode({'reference':r.reference}))
    user.find('Expert reviewer name').elements.pop().value='Synthetic reviewer'
    user.find('Sign this source-review scope').click()
    await user.should_see('all displayed checks')
    user.find('Validate independent published anchors ($0)').click()
    await user.should_see('Anchor validation: True')
    assert not list(catalog.path('reviews').glob('*.json'))
    assert list(catalog.path('validations').glob('*.json'))

async def test_private_selector_passes_exact_limit_and_preserves_default_gate(user: User,tmp_path,monkeypatch):
    catalog,r=fixture(tmp_path,'sm_higgs_invisible',overlap='supersedes',supersedes=['atlas-2301.10731-hinv'])
    bound=eligible(catalog,r)
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    build_pages(tmp_path/'runs')
    await user.open('/new/track1')
    user.find('Reviewed private limits for this run').elements.pop().value=[bound.reference]
    calls=[]
    def launch(command,folder,title,**kwargs):
        calls.append(command)
        folder.mkdir(parents=True,exist_ok=True)
        engine.save(engine.Job(folder=str(folder),command=command,title=title,kind=command[0],status='completed',returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine,'launch',launch)
    user.find('Scan the portal').click()
    await user.should_see('Run:')
    assert calls[0][calls[0].index('--private-limit')+1]==bound.reference and '--unverified' not in calls[0]

async def test_a_figure_with_one_printed_anchor_is_verified_by_hand(user: User,tmp_path,monkeypatch):
    import adroit.retrieval.experimental_ingestion as ingestion
    from adroit.constraints.experimental_review import FIGURE_CHECKLIST
    from tests.constraints.test_figure_anchors import figure_curve,QUOTES,ANCHORS,_figure_png
    monkeypatch.setattr(ingestion,'render_page',lambda path,page:_figure_png())
    catalog,r=figure_curve(tmp_path,QUOTES[1:2],ANCHORS[1:2])
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    build_pages(tmp_path/'runs')
    await user.open('/experiments/view?'+urlencode({'reference':r.reference}))
    user.find('Expert reviewer name').elements.pop().value='Synthetic verifier'
    user.find('Source-anchor tolerance (relative)').elements.pop().value=.1
    user.find('Reviewed mass range from (GeV)').elements.pop().value=10
    user.find('Reviewed mass range to (GeV)').elements.pop().value=40
    for name in FIGURE_CHECKLIST:
        user.find('Figure check: '+name).elements.pop().value=True
    user.find('I compared the calibrated overlay with the figure over the whole declared range').elements.pop().value=True
    user.find('Verify the figure by hand ($0)').click()
    await user.should_see('Figure verification: True; Manually verified against the figure')

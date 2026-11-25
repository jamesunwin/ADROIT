"""The activity page and the menu's indicator (the owner's workbench plan of 2026-10-18, part 2 §F)."""
import os

from nicegui.testing import User

from adroit.ui import engine
from adroit.ui.app import build_pages


def _jobs(root):
    for name, status, code, log in (('running', 'running', None, ''),
                                    ('missing', 'failed', 1, 'FileNotFoundError: SModelS is not on this machine'),
                                    ('track', 'cancelled', -15, '')):
        folder = root / name
        folder.mkdir(parents=True)
        engine.save(engine.Job(title=f'job {name}', kind='track1', command=['track1'], folder=str(folder), status=status,
                               returncode=code, pid=os.getpid() if status == 'running' else 0,
                               finished='' if status == 'running' else engine._now()))
        (folder / engine.LOG).write_text(log + '\n')
    (root / 'track' / '.track1-checkpoint').mkdir()
    (root / 'track' / '.track1-checkpoint' / 'manifest.json').write_text('{}')


async def test_the_menu_counts_and_the_page_offers_each_recovery(user: User, tmp_path, monkeypatch):
    root = tmp_path / 'runs'
    _jobs(root)
    resumed = []
    monkeypatch.setattr(engine, 'resume', lambda folder, **k: resumed.append(folder))
    build_pages(root)
    await user.open('/studies')                     # any page's menu: what needs attention and has not been seen
    await user.should_see('1 running')
    await user.should_see('2 need attention')
    await user.open('/activity')                    # opening Activity clears the menu's count (the owner, 2026-11-19)
    await user.should_see('1 running')
    await user.should_not_see('2 need attention')
    await user.should_see('Needs attention (2)')    # and still lists each one
    await user.should_see('missing dependency')
    await user.should_see('uv run adroit setup --only "SModelS" --fetch')
    user.find(marker='resume').click()
    assert resumed and resumed[0].name == 'track'


async def test_the_menu_is_cleared_by_opening_activity_and_counts_what_fails_afterwards(user: User, tmp_path):
    root = tmp_path / 'runs'
    _jobs(root)
    build_pages(root)
    await user.open('/activity')
    await user.open('/studies')
    await user.should_see('1 running')
    await user.should_not_see('need attention')
    later = root / 'later'
    later.mkdir()
    engine.save(engine.Job(title='job later', kind='signal', command=['signal'], folder=str(later), status='failed',
                           returncode=1, finished=engine._now()))
    (later / engine.LOG).write_text('ZeroDivisionError: division by zero\n')
    await user.open('/studies')
    await user.should_see('1 need attention')


async def test_every_page_carries_the_sign_that_a_link_was_followed_once(user: User, tmp_path):
    from adroit.ui.style import LOADING_HTML, LOADING_ID
    build_pages(tmp_path / 'runs')
    for path in ('/', '/studies', '/activity'):
        text = (await user.http_client.get(path)).text
        assert text.count('window.adroitLoading = true') == 1, path
    assert LOADING_ID in LOADING_HTML and "closest('a[href]')" in LOADING_HTML and 'pageshow' in LOADING_HTML


async def test_a_study_whose_folder_name_holds_a_reserved_character_is_linked_and_opens(user: User, tmp_path):
    from nicegui import ui

    from adroit.orchestrator import studies
    root = tmp_path / 'runs'
    folder = root / 'a&b#c d'
    folder.mkdir(parents=True)
    studies.record(folder, 'idea', 'the odd one')
    build_pages(root)
    await user.open('/studies')
    hrefs = [e.props.get('href') for e in user.find(kind=ui.link).elements if 'the odd one' in e.text]
    assert hrefs == ['/study?path=a%26b%23c%20d']
    await user.open(hrefs[0])
    await user.should_not_see('is not a study')
    await user.should_see('the odd one')

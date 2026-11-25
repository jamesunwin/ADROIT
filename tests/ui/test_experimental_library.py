from types import SimpleNamespace
from urllib.parse import urlencode
from nicegui import ui
from nicegui.testing import User
from nicegui.events import UploadEventArguments
from nicegui.elements.upload_files import SmallFileUpload

from adroit.ui import engine
from adroit.ui.app import build_pages
from adroit.library.experimental import ExperimentalCatalog
from tests.experimental_fixtures import paper


async def test_experimental_upload_uses_private_files_without_paid_calls(user: User,tmp_path,monkeypatch):
    calls=[]
    def launch(command,folder,title,**kwargs):
        calls.append((command,kwargs))
        folder.mkdir(parents=True,exist_ok=True)
        engine.save(engine.Job(folder=str(folder),command=command,title=title,kind=command[0],status='completed',returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine,'launch',launch)
    build_pages(tmp_path/'runs')
    await user.open('/experiments')
    uploader=user.find(ui.upload).elements.pop()
    for name,data in [('original_paper.pdf',paper(tmp_path/'paper.pdf').read_bytes()),('limits.csv',b'm_GeV,sigma_cm2\n10,1e-43\n')]:
        await uploader._upload_handlers[0](UploadEventArguments(sender=uploader,client=uploader.client,
            file=SmallFileUpload(name=name,content_type='application/octet-stream',_data=data)))
    user.find('Analysis title').elements.pop().value='My updated search'
    user.find('Ingest sources ($0)').click()
    await user.should_see('Run: Ingest experimental sources')
    command,kwargs=calls[0]
    assert command[:2]==['experiments','import'] and '--budget' not in command
    assert 'original_paper.pdf' in command and 'limits.csv' in command and kwargs['confirmed_budget']==0
    assert not ExperimentalCatalog().list()  # upload/launch is not approval or activation


async def test_draft_date_source_coverage_and_edit_create_linked_revision(user: User,tmp_path):
    catalog=ExperimentalCatalog()
    r=catalog.import_files([paper(tmp_path/'paper.pdf')],'Synthetic source',preview_pages=[])
    build_pages(tmp_path/'runs')
    await user.open('/experiments/view?'+urlencode({'reference':r.reference}))
    await user.should_see('One saved reading of an experiment')
    await user.should_see('Selectable in a run')
    await user.should_see('Physical page 1: text_extracted')
    editor=user.find('Dossier JSON').elements.pop()
    updated=r.dossier.model_copy(update={'analysis':'new channel'})
    editor.value=updated.model_dump_json()
    user.find('Save as a new inactive draft revision').click()
    await user.should_see('refines an earlier revision')
    all_revisions=catalog.list()
    assert len(all_revisions)==2
    assert all_revisions[-1].parent_revision==r.revision_id and all_revisions[-1].dossier.analysis=='new channel'
    assert catalog.load(r.reference)==r


async def test_an_extreme_image_header_is_refused_by_the_upload_and_the_next_upload_is_stored(user: User,tmp_path):
    """A feature audit's ID-03: a 65-byte PNG declaring 50,000 × 50,000 pixels, through the page's own upload callback,
    is refused with its reason (it had raised Pillow's error out of the callback); nothing is stored, and the next
    ordinary upload is."""
    from tests.core.test_images import HUGE
    build_pages(tmp_path/'runs')
    await user.open('/experiments')
    uploader=user.find(ui.upload).elements.pop()

    def event(name,data):
        return UploadEventArguments(sender=uploader,client=uploader.client,
                                    file=SmallFileUpload(name=name,content_type='application/octet-stream',_data=data))
    await uploader._upload_handlers[0](event('huge_header.png',HUGE))
    await user.should_see('image format or dimensions exceed supported limits: Image size (2500000000 pixels)')
    assets=ExperimentalCatalog().root/'assets'
    assert not (assets.exists() and list(assets.iterdir()))
    await uploader._upload_handlers[0](event('limits.csv',b'm_GeV,sigma_cm2\n10,1e-43\n'))
    await user.should_see('Stored private source: limits.csv')

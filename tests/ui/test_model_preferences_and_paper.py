from urllib.parse import urlencode
from nicegui.testing import User
from nicegui import ui
from nicegui.events import UploadEventArguments
from nicegui.elements.upload_files import SmallFileUpload
from adroit.ui.app import build_pages
from tests.ui.test_model_library import capture,draft
from tests.experimental_fixtures import paper

async def test_track2_style_and_splitting_controls_are_explicit(user:User,tmp_path,monkeypatch):
    calls=capture(monkeypatch)
    build_pages(tmp_path/'runs')
    await user.open('/new/track2')
    user.find('Required model properties').elements.pop().value='with Hidden-sector U(1)\nshould be composite dark matter'
    user.find('Preferred model properties').elements.pop().value='prefer leptophilic mediator'
    user.find('Library mass splittings').elements.pop().value='0,50,100'
    user.find('Fit, combine and rank').click()
    await user.should_see('Run:')
    command=calls[0]
    assert [command[i+1] for i,v in enumerate(command) if v=='--require-style']==['hidden-sector u(1)','composite dark matter']
    assert command[command.index('--prefer-style')+1]=='leptophilic mediator'
    assert command[command.index('--splittings')+1]=='0,50,100'

async def test_pdf_equation_upload_launches_budgeted_review(user:User,tmp_path,monkeypatch):
    calls=capture(monkeypatch)
    build_pages(tmp_path/'runs')
    await user.open('/models/intake')
    user.find('Model input kind').elements.pop().value='paper'
    source=paper(tmp_path/'model.pdf')
    uploader=user.find(ui.upload).elements.pop()
    await uploader._upload_handlers[0](UploadEventArguments(sender=uploader,client=uploader.client,
        file=SmallFileUpload(name='model.pdf',content_type='application/pdf',_data=source.read_bytes())))
    user.find('Paper equation label').elements.pop().value='3.1'
    user.find('Physical PDF pages').elements.pop().value='2'
    user.find('I approve this spend').click()
    user.find('Start reviewed intake').click()
    await user.should_see('Run: Interpret paper equation')
    command=calls[0]
    assert command[:2]==['models','paper']
    assert '--pdf' in command and command[command.index('--pages')+1]=='2'
    assert command[command.index('--equation')+1]=='3.1' and '--budget' in command

async def test_general_declaration_needs_reviewed_source_and_scope(user:User,tmp_path):
    service,s,d=draft()
    build_pages(tmp_path/'runs')
    await user.open('/models/intake?'+urlencode({'session':s.session_id,'step':d.step_id}))
    import json
    field=user.find('Reviewed model property declarations').elements.pop()
    field.value=json.dumps([{'property':'arbitrary reviewed property','state':'yes','source':'','scope':'','reviewed_by':''}])
    user.find('I reviewed the transcription').click()
    user.find('Save reviewed revision').click()
    assert not service.catalog.list()
    field.value=json.dumps([{'property':'arbitrary reviewed property','state':'yes','source':'Controlled source','scope':'Illustrative declaration','reviewed_by':'Fixture reviewer'}])
    user.find('Save reviewed revision').click()
    await user.should_see('One saved model')
    assert service.catalog.list()[0].provenance['model_styles'][0]['reviewed_by']=='Fixture reviewer'

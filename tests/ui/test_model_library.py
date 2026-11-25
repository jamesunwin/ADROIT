"""Private library selection and editable review are actual UI actions."""
from types import SimpleNamespace
from urllib.parse import urlencode
import pytest
import yaml
from pathlib import Path
from nicegui.testing import User

from adroit.ui.app import build_pages
from adroit.ui import engine
from adroit.library.personal import Catalog
from adroit.orchestrator.model_intake import Intake
from adroit.orchestrator.model_approval import model_identity
from adroit.parameter_space.simplified import model

def draft():
    svc=Intake()
    s=svc.start()
    d=svc.step(s.session_id,'typed',yaml.safe_dump(model('vector',10,125,.001,.25).model_dump(mode='json')))
    return svc,s,d

def stored():
    svc,s,d=draft()
    c=d.choices[0]
    return svc.approve(s.session_id,d.step_id,0,confirmed=True,expected_model_hash=model_identity(c.spec),tex=c.tex)

def capture(monkeypatch):
    calls=[]
    def launch(command,folder,title,**kwargs):
        calls.append(command)
        folder.mkdir(parents=True,exist_ok=True)
        engine.save(engine.Job(folder=str(folder),command=command,title=title,kind=command[0],status='completed',returncode=0))
        return SimpleNamespace(folder=str(folder))
    monkeypatch.setattr(engine,'launch',launch)
    return calls

async def test_library_lists_pinned_versions_and_links_both_tracks(user:User,tmp_path):
    r=stored()
    build_pages(tmp_path/'runs')
    await user.open('/models?view=personal')
    await user.should_see(r.spec.name)
    await user.open('/models/view?'+urlencode({'reference':r.reference}))
    await user.should_see('Constrain this model')
    await user.should_see('Signal best fits with this model')
    await user.should_see('Refine as a new revision')

async def test_the_model_page_typesets_the_model_and_says_why_a_track_cannot_run(user:User,tmp_path):
    """The owner (2026-10-13): the model as a Lagrangian and a field table, not code; and why a track is unavailable."""
    from adroit.ui.model_library import run_status
    from adroit.ui import typeset
    r=stored()
    build_pages(tmp_path/'runs')
    await user.open('/models/view?'+urlencode({'reference':r.reference}))
    await user.should_see('Run this model')
    if not typeset.available():
        await user.should_see('Typeset view unavailable')
    ready={'missing_parameters':['coefficient m2_F5P_F5M'],'structural_valid':True,'problems':[],'track1_engine':False,
           'track2_engine':False,'reason':'a portal map needs exactly one dark-matter species'}
    why=run_status(ready,'track1')
    assert 'give a value to coefficient m2_F5P_F5M' in why and 'exactly one dark-matter species' in why
    assert 'Derive couplings' in run_status(ready,'track2')
    assert run_status({**ready,'missing_parameters':[],'track1_engine':True},'track1')==''

async def test_review_does_not_allow_edited_tex_to_be_saved_as_old_model(user:User,tmp_path):
    svc,s,d=draft()
    build_pages(tmp_path/'runs')
    await user.open('/models/intake?'+urlencode({'session':s.session_id,'step':d.step_id}))
    user.find('I reviewed the transcription').click()
    user.find('Editable TeX').elements.pop().value='different TeX'
    user.find('Save reviewed revision').click()
    await user.should_see('edited model or TeX requires a new interpretation')
    assert not Catalog().list()

async def test_apply_typed_edit_then_review_saves_new_version(user:User,tmp_path):
    svc,s,d=draft()
    build_pages(tmp_path/'runs')
    await user.open('/models/intake?'+urlencode({'session':s.session_id,'step':d.step_id}))
    updated=model('vector',12,125,.002,.25)
    user.find('Canonical model YAML').elements.pop().value=yaml.safe_dump(updated.model_dump(mode='json'))
    user.find('Apply typed corrections').click()
    await user.should_see('Changes from prior draft')
    user.find('I reviewed the transcription').click()
    user.find('Save reviewed revision').click()
    await user.should_see('One saved model')                # the model's page (its revision is a short chip)
    assert Catalog().list()[0].spec==updated

@pytest.mark.needs("cresst", "cdmslite", "optimum_interval", "solar_model")
async def test_catalog_track1_launch_is_pinned_and_reviewed(user:User,tmp_path,monkeypatch):
    r=stored()
    calls=capture(monkeypatch)
    build_pages(tmp_path/'runs')
    await user.open('/new/track1?'+urlencode({'catalog':r.reference}))
    await user.should_see('Scan setup: active coordinates')
    user.find(marker='run_model_scan').click()
    await user.should_see('Run: model')
    assert calls[0][1]==r.reference and '--approved-model-hash' in calls[0]

async def test_catalog_track2_uses_selected_revision(user:User,tmp_path,monkeypatch):
    r=stored()
    calls=capture(monkeypatch)
    build_pages(tmp_path/'runs')
    await user.open('/new/track2?'+urlencode({'catalog':r.reference}))
    user.find('Fit, combine and rank').click()
    await user.should_see('Run:')
    command=calls[0]
    assert '--model' in command and command[command.index('--model')+1]==r.reference

async def test_free_fields_intake_starts_a_review_job_without_paid_gate(user:User,tmp_path,monkeypatch):
    calls=capture(monkeypatch)
    build_pages(tmp_path/'runs')
    await user.open('/models/intake')
    user.find('Model input kind').elements.pop().value='typed'
    user.find('Idea, TeX or typed field/model YAML').elements.pop().value=yaml.safe_dump(model('vector',10,125,.001,.25).model_dump(mode='json'))
    user.find('Start reviewed intake').click()
    await user.should_see('Run: Interpret model')
    assert calls[0][:2]==['models','step'] and '--budget' not in calls[0]


async def test_screenshot_upload_and_caption_both_reach_budgeted_job(user:User,tmp_path,monkeypatch):
    from io import BytesIO
    from PIL import Image
    from nicegui import ui
    from nicegui.events import UploadEventArguments
    from nicegui.elements.upload_files import SmallFileUpload
    calls=capture(monkeypatch)
    build_pages(tmp_path/'runs')
    await user.open('/models/intake')
    user.find('Model input kind').elements.pop().value='image'
    data=BytesIO()
    Image.new('RGB',(400,200),'white').save(data,format='PNG')
    uploader=user.find(ui.upload).elements.pop()
    await uploader._upload_handlers[0](UploadEventArguments(sender=uploader,client=uploader.client,
        file=SmallFileUpload(name='original_model.png',content_type='image/png',_data=data.getvalue())))
    await user.should_see('Source stored locally for review')
    user.find('Idea, TeX or typed field/model YAML').elements.pop().value='Use the screenshot and check its signs'
    user.find('I approve this spend').click()
    user.find('Start reviewed intake').click()
    await user.should_see('Run: Interpret model')
    command=calls[0]
    assert command[command.index('--source')+1].endswith('.png')
    assert command[command.index('--source-name')+1]=='original_model.png'
    assert command[command.index('--text')+1]=='Use the screenshot and check its signs'
    assert command[command.index('--budget')+1]=='1.0'

async def test_review_shows_each_candidates_approval_hash(user:User,tmp_path):
    svc,s,d=draft()
    build_pages(tmp_path/'runs')
    await user.open('/models/intake?'+urlencode({'session':s.session_id,'step':d.step_id}))
    await user.should_see(model_identity(d.choices[0].spec))

async def test_a_paid_session_cap_is_raised_from_the_workbench_with_approval(user:User,tmp_path):
    svc=Intake()
    s=svc.start(.5)
    d=svc.step(s.session_id,'typed',yaml.safe_dump(model('vector',10,125,.001,.25).model_dump(mode='json')))
    build_pages(tmp_path/'runs')
    await user.open('/models/intake?'+urlencode({'session':s.session_id,'step':d.step_id}))
    await user.should_see('Raise cap')
    user.find('Raise cap').click()
    assert svc.session(s.session_id).budget==.5                      # the cap is unchanged without approval
    user.find('raise the session cap to ($)').clear().type('0.8')
    user.find('I approve the higher cap').click()
    user.find('Raise cap').click()
    assert svc.session(s.session_id).budget==.8 and svc.session(s.session_id).cap_history[0].reason=='raised from the workbench'


async def test_the_library_switches_between_personal_and_standard(user:User,tmp_path):
    """The owner (2026-10-13): a frozen switch between the personal and the standard library; the standard one shown
    first and by default (the owner's JU1, 2026-11-16)."""
    from adroit.ui.model_library import LIBRARIES
    r=stored()
    build_pages(tmp_path/'runs')
    assert list(LIBRARIES) == ['standard', 'personal']
    await user.open('/models')
    await user.should_see('Personal library')
    await user.should_see('Standard library')
    await user.should_see('Real scalar singlet (Higgs portal)')
    await user.should_see('Electroweak multiplets (4)')
    await user.should_not_see(r.spec.name)
    await user.open('/models?view=personal')
    await user.should_see(r.spec.name)


async def test_a_standard_model_page_runs_or_copies_it(user:User,tmp_path):
    build_pages(tmp_path/'runs')
    await user.open('/models/standard?id=dark_photon_dirac')
    await user.should_see('Constrain this model (Track 1)')
    await user.should_see('Copy into my personal library')
    await user.should_see('Not computed by ADROIT')
    await user.open('/models/standard?id=L01')
    await user.should_see('Nucleon-level reduction')
    await user.should_see('uv run adroit exclude L01')
    await user.open('/models/standard?id=nothing')
    await user.should_see("No standard model 'nothing'.")


def test_a_standard_model_is_copied_as_a_draft_to_review():
    from urllib.parse import parse_qs, urlsplit
    from adroit.parameter_space import library
    from adroit.ui.model_library import copy_to_personal
    spec=library.entry('dmwg_V1').spec()
    query=parse_qs(urlsplit(copy_to_personal(spec)).query)
    draft=Intake().load(query['session'][0],query['step'][0])
    assert draft.choices[0].spec==spec


async def test_constrain_this_model_opens_its_portal(user:User,tmp_path):
    from adroit.parameter_space import library
    build_pages(tmp_path/'runs')
    await user.open('/new/track1?portal=wino')
    await user.should_see(library.entry('wino').benchmark[:40])


def test_run_this_model_shows_the_route_and_its_physics():
    """G12: the box names the route that computes a model, the physics included and what is missing ($0)."""
    import math
    from adroit.core.model_spec import ModelSpec
    from adroit.ui.model_library import route_lines
    spec=ModelSpec.model_validate({'name':'dark_qed','phase':'broken','fields':[
        {'name':'X','role':'dark_matter','spin':0.5,'dark_parity':-1,'mass_gev':1000.0,'charges':{'extra':{'Ad':1.0}}},
        {'name':'Ad','role':'mediator','spin':1,'self_conjugate':True,'mass_gev':0.0}],
        'couplings':[{'name':'e_d','value':math.sqrt(4*math.pi*0.03)}],
        'terms':[{'fields':[{'field':'X','conjugate':True},{'field':'X'},{'field':'Ad'}],'lorentz':'vector',
                  'coupling':'e_d'}]})
    lines=route_lines(spec)
    assert lines[0].startswith('Route: the generic route')
    assert any(x.startswith('Included: ') and 'hydrogen-like' in x for x in lines)
    assert any(x.startswith('Not included: ') and 'resonance recasts' in x for x in lines)


async def test_explain_a_signal_runs_an_unchanged_library_model_as_its_pinned_revision(user: User, tmp_path, monkeypatch):
    """The external audit's A13 (2026-10-16): Explain a signal had submitted the chosen revision's spec alone, losing
    the pinned reference, its approval and its derivation. Unchanged, it runs as the reference; edited, it is a new
    model, refined in the model library first."""
    import asyncio
    from nicegui import ui
    r = stored()
    calls = capture(monkeypatch)
    build_pages(tmp_path / 'runs')
    await user.open('/new/single')
    picker = next(e for e in user.find(kind=ui.select).elements if e.props.get('label') == 'a model from the library')
    await filled(picker, r.reference)
    picker.value = r.reference
    for _ in range(50):
        if any('fields' in (e.value or '') for e in user.find(kind=ui.textarea).elements):
            break
        await asyncio.sleep(0.02)
    user.find('Run the study').click()
    await user.should_see('Run:')
    assert calls and calls[0][0] == 'single-idea' and calls[0][1] == r.reference
    await user.open('/new/single')
    picker = next(e for e in user.find(kind=ui.select).elements if e.props.get('label') == 'a model from the library')
    await filled(picker, r.reference)
    picker.value = r.reference
    area = next(e for e in user.find(kind=ui.textarea).elements if e.props.get('label', '').startswith('the model'))
    for _ in range(50):
        if area.value:
            break
        await asyncio.sleep(0.02)
    area.value = area.value.replace('name:', 'name: edited_', 1)
    user.find('Run the study').click()
    await user.should_see('was edited')
    assert len(calls) == 1                                  # nothing launched for the edited model


async def test_the_signal_pages_offer_the_standard_librarys_runnable_models(user: User, tmp_path, monkeypatch):
    """The owner's JU1 (2026-11-16): Explain a signal and Signal best fits had offered the personal library alone (an
    empty list for a new user). The standard library's models that run as they stand (their couplings at their
    papers' benchmark) are listed first, and a chosen one runs as its typed model."""
    import asyncio
    from nicegui import ui
    from adroit.library.personal import support
    from adroit.ui.model_library import STANDARD, model_choices, standard_options, standard_spec
    for track in ('track1', 'track2'):
        listed = standard_options(track)
        assert STANDARD + 'scalar_mediator' in listed and STANDARD + 'higgsino' in listed
        assert STANDARD + 'two_hdm_a' in listed                       # its complete benchmark (OB-11)
        assert STANDARD + 'inelastic_dark_photon' not in listed       # it cannot be computed here, and says why
        assert list(model_choices(track))[:len(listed)] == list(listed)
    spec = standard_spec('scalar_mediator')
    assert support(spec)['numerically_declared'] and {c.name: c.value for c in spec.couplings} == {'g_chi': 1.0,
                                                                                                    'g_q': 1.0}
    calls = capture(monkeypatch)
    build_pages(tmp_path / 'runs')
    await user.open('/new/single')
    picker = next(e for e in user.find(kind=ui.select).elements if e.props.get('label') == 'a model from the library')
    await filled(picker, STANDARD + 'scalar_mediator')
    picker.value = STANDARD + 'scalar_mediator'
    area = next(e for e in user.find(kind=ui.textarea).elements if e.props.get('label', '').startswith('the model'))
    for _ in range(50):
        if area.value:
            break
        await asyncio.sleep(0.02)
    assert 'scalar_mediator' in area.value
    user.find('Run the study').click()
    await user.should_see('Run:')
    assert calls[0][0] == 'single-idea' and calls[0][1].endswith('model.yaml')          # run as its typed model
    await user.open('/new/track2')
    picker = next(e for e in user.find(kind=ui.select).elements
                  if e.props.get('label') == 'Models to compare (standard and personal library)')
    await filled(picker, STANDARD + 'higgsino')
    picker.value = [STANDARD + 'higgsino']
    user.find('Fit, combine and rank').click()
    await user.should_see('Run:')
    command = calls[1]
    assert command[command.index('--model') + 1].endswith('standard_higgsino.yaml')


def test_a_yaml_naming_a_catalog_revision_is_honoured_only_if_it_matches(tmp_path):
    """The CLI side of A13: the model library's export names its revision; a matching export runs pinned, an edited
    one or one naming a revision this library lacks is refused rather than run unpinned."""
    import typer
    from adroit.orchestrator.cli import _catalog_reference
    r = stored()
    exported = tmp_path / 'm.yaml'
    Catalog().export_model(r.reference, exported)
    assert _catalog_reference(exported) == r.reference
    data = yaml.safe_load(exported.read_text())
    data['spec']['fields'][0]['mass_gev'] = 11.0
    edited = tmp_path / 'edited.yaml'
    edited.write_text(yaml.safe_dump(data))
    import pytest
    with pytest.raises(typer.BadParameter, match='changed since approval'):     # its own approval refuses it
        _catalog_reference(edited)
    data.pop('approval')
    edited.write_text(yaml.safe_dump(data))
    with pytest.raises(typer.BadParameter, match='differs from that revision'):  # and without one, so does the check
        _catalog_reference(edited)
    data['catalog_reference'] = 'catalog:nobody@0000'
    unknown = tmp_path / 'unknown.yaml'
    unknown.write_text(yaml.safe_dump(data))
    with pytest.raises(typer.BadParameter, match='cannot load'):
        _catalog_reference(unknown)
    plain = tmp_path / 'plain.yaml'
    plain.write_text(yaml.safe_dump(r.spec.model_dump(mode='json')))
    assert _catalog_reference(plain) == ''                  # a model without a reference runs as itself


def test_an_edited_export_is_refused_cleanly_by_every_command(tmp_path):
    """Found running the external audit's phase 4 workflows (2026-10-16): `adroit single-idea` on an exported model
    whose content was edited stopped with a traceback from its approval check; it is now a usage error naming the
    file, before anything is computed."""
    import pytest
    import typer
    from typer.testing import CliRunner
    from adroit.orchestrator import cli
    r = stored()
    exported = tmp_path / 'm.yaml'
    Catalog().export_model(r.reference, exported)
    data = yaml.safe_load(exported.read_text())
    data['spec']['fields'][0]['mass_gev'] = 11.0
    edited = tmp_path / 'edited.yaml'
    edited.write_text(yaml.safe_dump(data))
    with pytest.raises(typer.BadParameter, match='edited.yaml: model changed since approval'):
        cli._spec(edited)
    result = CliRunner().invoke(cli.app, ['single-idea', str(edited), '--experiment', 'CDMS II Si (2013)',
                                          '--masses', '10', '--out', str(tmp_path / 'run')])
    shown = ' '.join(result.output.replace('│', ' ').split())        # the message as one line, out of its box
    assert result.exit_code == 2 and 'changed since approval' in shown and 'Traceback' not in result.output
    assert not (tmp_path / 'run' / 'result.json').exists()


async def filled(picker, choice, tries: int = 100) -> None:
    """Wait until the library picker, filled off the page's event loop (the auditor's OL-01), offers ``choice``: a person cannot
    choose a model before the list has loaded either."""
    import asyncio
    for _ in range(tries):
        if choice in (picker.options or {}):
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"the picker never offered {choice!r}")



def _offered() -> list[str]:
    """The standard entries the signal pages offer (OB-11): every one computed with a recoil spectrum."""
    from adroit.parameter_space import library
    return [e.id for e in library.ENTRIES if not e.typed.unsupported and not e.typed.no_recoil]


def test_every_standard_model_with_a_recoil_spectrum_is_offered_and_hands_over_its_exact_benchmark():
    """OB-11 (the owner, 2026-11-24): every standard model Explain a signal and Signal best fits can compute is offered
    (24 of 27), and the typed model a choice hands over is the entry's complete benchmark, value for value; the three
    the pages cannot compute are named with why."""
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space import library
    from adroit.ui.model_library import STANDARD, choice_yaml, standard_options, standard_unsupported
    offered = _offered()
    assert len(offered) == 24 and len(library.ENTRIES) == 27
    for track in ('track1', 'track2'):
        assert list(standard_options(track)) == [STANDARD + i for i in offered]
    for entry_id in offered:
        handed = ModelSpec.model_validate(yaml.safe_load(choice_yaml(STANDARD + entry_id)))
        assert handed == library.entry(entry_id).benchmark_spec()
    note = standard_unsupported()
    assert all(library.entry(i).title in note for i in ('inelastic_dark_photon', 'higgs_portal_dirac_cpv',
                                                         'lepton_portal_muR'))


async def test_explain_a_signal_shows_and_submits_each_standard_benchmark(user: User, tmp_path, monkeypatch):
    """Each offered standard model, chosen in Explain a signal, fills the editor with its benchmark's values; a
    submission hands the real command that exact typed model (the Z portal's axial benchmark, m_χ = 500 GeV and
    g_A = 0.1, among the submitted ones)."""
    import asyncio
    from nicegui import ui
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space import library
    from adroit.ui.model_library import STANDARD
    calls = capture(monkeypatch)
    build_pages(tmp_path / 'runs')
    submitted = ('z_portal_axial', 'dmwg_A1', 'inert_doublet', 'wino', 'b_minus_l', 'higgs_portal_vector')
    for entry_id in _offered():
        await user.open('/new/single')
        await user.should_see(marker='standard_unsupported')
        picker = next(e for e in user.find(kind=ui.select).elements if e.props.get('label') == 'a model from the library')
        await filled(picker, STANDARD + entry_id)
        picker.value = STANDARD + entry_id
        area = next(e for e in user.find(kind=ui.textarea).elements if e.props.get('label', '').startswith('the model'))
        for _ in range(100):
            if area.value and f'name: {entry_id}\n' in area.value:
                break
            await asyncio.sleep(0.02)
        shown = ModelSpec.model_validate(yaml.safe_load(area.value))
        assert shown == library.entry(entry_id).benchmark_spec(), entry_id
        if entry_id in submitted:
            before = len(calls)
            user.find('Run the study').click()
            await user.should_see('Run:')
            command = calls[before]
            assert command[0] == 'single-idea'
            sent = ModelSpec.model_validate(yaml.safe_load(Path(command[1]).read_text()))
            assert sent == library.entry(entry_id).benchmark_spec(), entry_id
            if entry_id == 'z_portal_axial':
                assert {c.name: c.value for c in sent.couplings} == {'g_A': 0.1} and sent.dark_matter.mass_gev == 500.0

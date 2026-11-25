"""Private catalog, pinned selection and reviewed editable model intake."""
from __future__ import annotations
import base64
import json
from pathlib import Path
from urllib.parse import urlencode
import yaml
from nicegui import ui

from adroit.library.personal import Catalog,support,usable
from adroit.orchestrator.model_intake import Draft,DraftChoice,Intake,Session
from adroit.orchestrator.model_approval import model_identity,read_model
from adroit.ui import forms,engine,submission

def options(track=''):
    """The personal library's revisions by reference, optionally only those a track can run: for Constrain a model,
    ``usable`` (its engine computes it at its own values; the auditor's UM-01), for Signal best fits numerically declared
    with an engine."""
    result={}
    for r in Catalog().listing()[0]:                  # a damaged revision is named on the library's page (CA-07)
        if track and run_status(support(r.spec,r.derivation),track,r.spec,r.derivation):   # one answer (UO-04)
            continue                                  # (support only where a track filters: it can take a minute)
        result[r.reference]=f'{r.spec.name} · {r.model_id[:8]} / {r.revision_id[:10]}'
    return result


LOADING='loading your models…'


def filled_later(select, compute) -> None:
    """Fill ``select``'s choices from ``compute()`` in a worker thread, after the page is drawn (the auditor's OL-01: listing
    the library for a track works out each revision's support, a generic engine's domain included, which had frozen
    the whole workbench for 73 s on a cold saved model). The select shows "loading your models…" meanwhile and keeps
    a preselected choice the listing still offers; a failure is said in the select's hint, never left loading."""
    from nicegui import run
    select.props(f'hint="{LOADING}"').mark('choices_loading')

    async def fill() -> None:
        try:
            found=await run.io_bound(compute)
        except Exception as error:                    # noqa: BLE001 - said, never a select stuck on "loading"
            select.props(f'hint="the models could not be listed: {type(error).__name__}"')
            return
        chosen=select.value if isinstance(select.value,list) else [select.value] if select.value else []
        kept=[v for v in chosen if v in found]
        select.set_options(found,value=kept if isinstance(select.value,list) else (kept[0] if kept else None))
        select.props(remove='hint')
    ui.timer(0.01,fill,once=True)

STANDARD='standard:'          # a standard model's key in a picker: run as its typed model at its benchmark (JU1)
UNLISTED=('Listed: the standard library\'s models, each at its paper\'s complete benchmark (its couplings in its own '
          'notation, editable in the box below), and your own models with every mass and coupling value given. To run '
          'one of your own that is not listed, open it in the model library: it says what is missing.')


def standard_unsupported() -> str:
    """The standard models no page can compute, each with what it would need (OB-11: listed here, never silently
    left out); from each entry's declaration, so the page computes nothing to show it."""
    from adroit.parameter_space import library
    rows=[f'{e.title}: {e.typed.unsupported or e.typed.no_recoil}' for e in library.ENTRIES
          if e.typed.unsupported or e.typed.no_recoil]
    return ('Not offered: '+'; '.join(rows)+'.') if rows else ''


def standard_spec(model_id: str):
    """A standard model as its complete typed model at its benchmark (``library.Entry.benchmark_spec``, OB-11): every
    coupling given its value in the model's own notation, with the benchmark's assumptions. The one definition the
    model library shows and every picker (Explain a signal, Signal best fits' additional models) runs."""
    from adroit.parameter_space import library
    return library.entry(model_id).benchmark_spec()


def standard_options(track: str) -> dict[str,str]:
    """The standard library's portal models a track can run as they stand at their benchmark (``standard_spec``), by
    ``STANDARD`` + id (the owner's JU1, 2026-11-16: Explain a signal and Signal best fits had offered the personal
    library alone)."""
    return {STANDARD+e.id:f'Standard library · {e.title}' for e, ready, _ in standard_readiness(track) if ready}


def standard_readiness(track: str) -> list[tuple]:
    """Every standard entry, (entry, whether the track can run its typed benchmark, why not): a model that cannot run
    stays visible with its specific reason (OB-11), never silently left out."""
    from adroit.parameter_space import library
    out=[]
    for e in library.ENTRIES:
        try:
            ready=support(standard_spec(e.id))
        except (ValueError,KeyError) as error:
            out.append((e,False,f'its typed benchmark could not be built: {error}'))
            continue
        if e.typed.no_recoil:
            out.append((e,False,e.typed.no_recoil))
        elif not ready['numerically_declared']:
            out.append((e,False,'a benchmark value is missing: '+', '.join(ready['missing_parameters'])))
        elif not ready[f'{track}_engine']:
            out.append((e,False,ready.get('reason') or 'no engine computes it'))
        else:
            out.append((e,True,''))
    return out


def standard_unavailable(track: str) -> str:
    """The standard models a track's picker does not offer, each with why (shown under the picker)."""
    rows=[f'{e.title}: {why}' for e,ready,why in standard_readiness(track) if not ready]
    return ('Not offered here: '+'; '.join(rows)) if rows else ''


def model_choices(track: str) -> dict[str,str]:
    """A track's picker: the standard library's runnable models, then the user's own."""
    return {**standard_options(track),**options(track)}


def choice_yaml(key: str) -> str:
    """The typed model (YAML) a picker's key names: a standard model at its benchmark, or a personal revision."""
    spec=standard_spec(key.removeprefix(STANDARD)) if key.startswith(STANDARD) else Catalog().load(key).spec
    return yaml.safe_dump(spec.model_dump(mode='json'),sort_keys=False,allow_unicode=True)

LIBRARIES={'standard':'Standard library','personal':'Personal library'}     # the standard one first and by default (JU1)


def library_switch(view: str) -> None:
    """The switch between the standard and the personal library, frozen at the top of the page as it scrolls."""
    with ui.row().classes('sticky top-0 z-10 w-full bg-white py-2 items-center gap-4 border-b'):
        ui.toggle(LIBRARIES,value=view if view in LIBRARIES else 'standard',
                  on_change=lambda e:ui.navigate.to('/models?'+urlencode({'view':e.value}))).props('no-caps')
        ui.link('Create or refine a model','/models/intake')


def catalog_page(root,view='standard'):
    """The model library: the standard library (every model ADROIT has the code to formulate; shown by default) or the
    personal library (the user's own model revisions), switched at the top."""
    from adroit.ui.pages import header
    header('Model library','Your own models, each saved revision kept, and the standard library of benchmark models and '
           'interactions. Open one to see its Lagrangian, what can run it, and its analyses.',
           facts=('$0 to browse and save','making a model from words, TeX or a screenshot is paid'))
    library_switch(view)
    if view=='personal':
        _personal_list(root)
    else:
        _standard_list()


def _personal_list(root: Path) -> None:
    """The user's own models, one card per model (its latest revision, and its earlier ones folded), searchable, with
    whether each page can run it and, if not, why."""
    from adroit.ui.style import when
    ui.label('Your own models. Editing one saves a new revision and keeps the old; make one from TeX, a screenshot, '
             'words, a paper or YAML with "Create or refine a model".').classes('text-gray-700')
    query=ui.input('Find a model').classes('w-full')
    @ui.refreshable
    def rows():
        models={}
        found,damaged=Catalog().listing(query.value or '')
        from adroit.ui.pages import _damaged
        _damaged(None,'model revision(s)',damaged,'unreadable_revisions')
        for r in found:
            models.setdefault(r.model_id,[]).append(r)
        if not models:
            ui.label('No models yet. "Create or refine a model" makes one; or copy one from the standard library.') \
                .classes('text-gray-500')
        for revisions in models.values():
            latest=revisions[-1]
            ready=support(latest.spec,latest.derivation)
            with ui.column().classes('w-full border rounded p-3 gap-1'):
                ui.link(latest.spec.name,'/models/view?'+urlencode({'reference':latest.reference})).classes('font-medium')
                ui.label(f'Latest revision saved {when(latest.created)}'
                         +(f' · {len(revisions)} revisions' if len(revisions)>1 else '')).classes('text-sm text-gray-600')
                with ui.row().classes('gap-2 items-center'):
                    verdict=usable(latest.spec,latest.derivation,ready=ready)
                    if not verdict.ok:
                        with ui.badge('incomplete',color='orange').mark('incomplete'):
                            ui.tooltip('It cannot run yet: '+'; '.join(verdict.blocking)
                                       +'. Open it and refine it to complete it.').classes('text-sm max-w-md')
                    for track,name in (('track1','Constrain a model'),('track2','Signal best fits')):
                        why=run_status(ready,track,latest.spec,latest.derivation)
                        with ui.badge(f'{name}: {"ready" if not why else "not yet"}',color='green' if not why else 'grey'):
                            if why:
                                ui.tooltip('To run it, '+why).classes('text-sm max-w-md')
                    from adroit.ui.deletion import confirm_model,delete_button
                    delete_button(lambda model_id=latest.model_id:confirm_model(root,model_id,rows.refresh),'model')
                if len(revisions)>1:
                    with ui.expansion('Earlier revisions').classes('w-full text-sm'):
                        for r in reversed(revisions[:-1]):
                            ui.link(f'{r.spec.name}, saved {when(r.created)}','/models/view?'+urlencode({'reference':r.reference}))
    rows()
    query.on_value_change(lambda _:rows.refresh())


def _standard_list() -> None:
    """Every standard model, by category and subcategory, searchable."""
    from adroit.library import standard
    ui.label('Every model ADROIT has the code to formulate: complete models from the literature, which Constrain a '
             'model scans, and the interactions Signal best fits searches.').classes('text-gray-700')
    query=ui.input('Find a standard model').classes('w-full')
    @ui.refreshable
    def rows():
        found=standard.grouped(query.value or '')
        if not found:
            ui.label('No standard model matches.')
        for category,subcategories in found.items():
            ui.label(category).classes('text-lg font-bold mt-4')
            for subcategory,items in subcategories.items():
                opened=bool(query.value) or category==standard.PORTALS
                with ui.expansion(f'{subcategory} ({len(items)})',value=opened).classes('w-full'):
                    for e in items:
                        with ui.row().classes('w-full items-baseline gap-3 no-wrap'):
                            ui.link(e.title,'/models/standard?'+urlencode({'id':e.id})).classes('shrink-0')
                            ui.label(e.summary).classes('text-sm text-gray-600 truncate')
    rows()
    query.on_value_change(lambda _:rows.refresh())


def standard_page(root,model_id:str) -> None:
    """One standard model: typeset with its benchmark, plane and references (a portal model), or its interaction and
    nucleon-level reduction (an interaction card); and how to run it."""
    from adroit.library import standard
    from adroit.ui.pages import header
    if not model_id:
        ui.navigate.to('/models?view=standard')
        return
    try:
        e=standard.entry(model_id)
    except KeyError:
        header('Model library')
        ui.label(f'No standard model {model_id!r}.')
        return
    header(e.title,'A model from the standard library: its Lagrangian, its benchmark and the plane its papers plot, '
           'and how to run it. To change it, copy it into your own library.')
    library_switch('standard')
    ui.label(f'{e.subcategory} · standard library').classes('text-gray-600')
    if e.kind=='portal':
        _portal_detail(root,e.id)
    else:
        _interaction_detail(e.id)


def _section(title: str, lines) -> None:
    lines=[lines] if isinstance(lines,str) else list(lines)
    if lines:
        ui.label(title).classes('font-bold mt-3')
        for line in lines:
            ui.label(str(line)).classes('text-gray-800')


def _portal_detail(root,portal_id:str) -> None:
    from adroit.parameter_space import library
    from adroit.ui.typeset import show_model
    p=library.entry(portal_id)
    with ui.card().classes('w-full'):
        ui.label('Run this model').classes('text-lg font-bold')
        ui.link('Constrain this model (Track 1): its plane, as its papers plot it','/new/track1?'+
                urlencode({'portal':portal_id}))
        ui.label('Signal best fits (Track 2) searches the interactions of this library and your own models. To fit '
                 'this model, or to change it, copy it into your personal library.').classes('text-gray-700')
        ui.button('Copy into my personal library (review, then approve; $0)',
                  on_click=lambda:ui.navigate.to(copy_to_personal(p.spec())))
    show_model(p.spec(),root/'.typeset')
    _section('As written in its papers',p.lagrangian)
    _section('Dark matter',p.dark_matter)
    _section('Parameters',p.parameters)
    _section('Benchmark',p.benchmark)
    _section('The plane',f'{_axis(p.x)} against {_axis(p.y)}')
    _section('What the literature found',p.literature)
    _section('Not computed by ADROIT',p.not_computed)
    _section('References',p.references)


def _axis(a) -> str:
    return f'{a.parameter} from {a.low:g} to {a.high:g}{" (log)" if a.log else ""}'


def copy_to_personal(spec) -> str:
    """Open a standard model as a typed draft in model creation ($0), where the user reviews and approves it as a
    personal revision; returns the draft's page."""
    service=Intake()
    session=service.start()
    draft=service.step(session.session_id,'typed',yaml.safe_dump(spec.model_dump(mode='json'),sort_keys=False,
                                                                   allow_unicode=True))
    return '/models/intake?'+urlencode({'session':session.session_id,'step':draft.step_id})


def _interaction_detail(card_id:str) -> None:
    from adroit.library.interactions import registry
    c=registry.card(card_id)
    with ui.card().classes('w-full'):
        ui.label('Run this interaction').classes('text-lg font-bold')
        import re
        searched=re.fullmatch(r'O\d+|L\d\d',c.id)          # the library's space (``signal.library_model_space``)
        ui.link('Signal best fits (Track 2): '+('every run searches it, isoscalar and isovector, at the library\'s '
                'masses' if searched else 'not in the space every run searches; the agent-led search may reach it as '
                'a neighbour of a leading candidate'),'/new/track2')
        ui.label(f'Its exclusion limits from every experiment (Path 1): uv run adroit exclude {c.id}') \
            .classes('text-gray-700')
    _section('Interaction',c.interaction)
    _section('Description',c.description)
    _section('Parameters',[f'{q.name} ({q.unit or "dimensionless"}): {q.description}; default {q.default:g}'
                            for q in c.parameters])
    _section('Nucleon-level reduction',[f'{t.target}: {t.factor:g} × {" ".join(t.couplings) or "1"}'
                                        + (f' × q^{t.q_power}' if t.q_power else '') for t in c.terms])
    _section('Kinematics',', '.join(k.value for k in c.kinematics))
    _section('Validity',[f'{v.kind.value}: {v.note}' for v in c.validity])
    _section('References',c.references)

def _held(held,study):
    """A study's version as a list reads it (``study_headline.held``), or None where it does not settle."""
    from adroit.evidence.version import Unsettled
    try:
        return held(Path(study.folder))
    except Unsettled:
        return None

def analyses(root,reference):
    """The studies made with a model revision (``reference``), each a version as a list reads it, named by its record read
    with its result, and only where that record, of that result, says it used this revision (the auditor's DB/VI recheck,
    DC-01, 2026-11-03; the version handle)."""
    from adroit.orchestrator.studies import tree
    from adroit.orchestrator.study_headline import SHOWN,held
    return [found for found in (_held(held,study) for _,study in tree(root) if reference in study.model_references)
            if found is not None and found.record_state in SHOWN and reference in found.study().model_references]

def model_page(root,reference):
    """One pinned model revision: its Lagrangian, what can run it and how, its analyses, the actions on it, and its
    provenance (TeX, YAML, sources) folded away."""
    from adroit.ui.pages import header,rel
    from adroit.ui.style import short_ref,when
    try:
        r=Catalog().load(reference)
    except (ValueError,OSError) as error:            # deleted, or never there: said, not an internal error
        header('Model not found','This model revision cannot be opened.')
        ui.label(str(error)).classes('text-orange-800').mark('model_not_found')
        ui.link('The model library','/models?view=personal')
        return
    header(r.spec.name,'One saved model: its Lagrangian, what can run it and how, and the analyses made with it. '
           'Editing it saves a new revision; this one stays as it is.')
    with ui.row().classes('items-center gap-4'):
        short_ref(r.reference,'revision')
        ui.label(f'saved {when(r.created)}').classes('text-gray-600')
    from adroit.ui.typeset import show_model
    show_model(r.spec,root/'.typeset')
    ready=support(r.spec,r.derivation)
    _run_box(r,ready)
    from adroit.ui.discovery import discovery_box
    discovery_box(root,r.reference,r.spec.name)
    from adroit.orchestrator.study_headline import listed
    found_analyses=analyses(root,r.reference)
    from adroit.ui.wizards import _unoffered
    _unoffered(root)
    if found_analyses:
        ui.label('Analyses made with this revision').classes('text-lg font-medium mt-2')
        for found in found_analyses:
            study=found.study()
            with ui.row().classes('items-baseline gap-2'):
                ui.link(listed(found),'/study?'+urlencode({'path':rel(root,Path(study.folder))}))
                ui.label('calculated '+when(study.calculation_completed_at or study.created)).classes('text-sm text-gray-600')
    with ui.row().classes('gap-3 mt-2'):
        ui.button('Refine as a new revision',on_click=lambda:ui.navigate.to('/models/intake?'+urlencode({'reference':r.reference}))).props('outline')
        ui.button('Start a new analysis from it',on_click=lambda:ui.navigate.to('/reanalyse?'+urlencode({'source':r.reference}))).props('outline')
        from adroit.ui.deletion import confirm_model
        ui.button('Delete this model',on_click=lambda:confirm_model(root,r.model_id,lambda:ui.navigate.to(
            '/models?view=personal'))).props('outline color=negative').mark('delete_this_model')
    if r.provenance.get('model_styles'):
        ui.label('Reviewed model-style declarations: '+str(r.provenance['model_styles'])).classes('text-sm')
    if r.provenance.get('paper_equations'):
        ui.label('Pinned paper equations: '+str(r.provenance['paper_equations'])).classes('text-sm')
    with ui.expansion('Provenance: the stored TeX, the model data (YAML), the engine check and the sources').classes('w-full'):
        ui.label('Original sources and model revisions are private local files.').classes('text-sm text-gray-600')
        ui.code(r.tex,language='latex').classes('w-full')
        ui.code(yaml.safe_dump(r.spec.model_dump(mode='json'),sort_keys=False,allow_unicode=True),language='yaml')
        ui.label(str(ready)).classes('text-xs text-gray-600')
        for a in r.sources:
            ui.label(f'Source: {a.name} ({a.role}, {a.sha256})').classes('text-xs font-mono')
            if a.suffix=='.pdf':
                ui.button('Download original PDF '+a.name,on_click=lambda a=a:ui.download(Catalog().asset_path(a).read_bytes(),a.name))
            if a.suffix in ('.png','.jpg','.jpeg','.webp'):
                media={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}[a.suffix]
                ui.image('data:'+media+';base64,'+base64.b64encode(Catalog().asset_path(a).read_bytes()).decode())

def run_status(ready: dict, track: str, spec=None, derivation=None) -> str:
    """'' if a track can run this model, else why not in plain words (from ``support``). Given the model (``spec``
    and its own matching), the same answer as ``usable`` for that track is added (the auditor's UO-04: an old model the
    engine refuses at its values had been called ready, and an all-zero matching listed for Signal best fits): for
    Constrain a model, the engine's domain at the stated values and the route to the Standard Model; for Signal best
    fits, a matching with a finite, non-zero coefficient."""
    reasons=[]
    if ready['missing_parameters']:
        reasons.append('give a value to '+', '.join(ready['missing_parameters'])+' (Refine as a new revision)')
    if not ready['structural_valid']:
        reasons.append('the audit found problems: '+'; '.join(p.get('message',str(p)) for p in ready['problems']))
    if not ready[f'{track}_engine']:
        reasons.append("ADROIT's engines do not cover it"+(': '+ready['reason'] if ready.get('reason') else '')
                       +('; Signal best fits can use it after its nucleon couplings are derived (Constrain a '
                         'model → Derive couplings)' if track=='track2' else ''))
    if spec is not None and not reasons:
        reasons+=usable(spec,derivation,ready=ready,track1=track=='track1').blocking
    return '; '.join(reasons)


def route_lines(spec) -> list[str]:
    """The route that computes the model and its physics, as lines (``parameter_space.route_report``; $0, no
    language model): what the planner's check recomputes (G12)."""
    from adroit.parameter_space.route_report import report
    try:
        found=report(spec)
    except Exception as error:                     # noqa: BLE001 - the box still shows the tracks
        return [f'Route: not determined ({type(error).__name__}: {error})']
    head={'library':f'Route: {found.engine}.','generic':'Route: the generic route, from the model\'s own Lagrangian.',
          'none':'Route: none computes this model yet.'}[found.route]
    lines=[head+(f' Why: {found.why}.' if found.why and found.route!='library' else '')]
    lines+=['Included: '+item for item in found.included]
    lines+=['Not included: '+item for item in found.missing]
    lines+=['How ADROIT reads this model: '+item for item in found.notes]
    return lines


def _run_box(r,ready: dict) -> None:
    """Run this model: the route and its physics (``route_lines``), then a link per page that can run it, or why it
    cannot yet."""
    from adroit.ui.style import term
    with ui.card().classes('w-full'):
        with ui.row().classes('items-center gap-2'):
            ui.label('Run this model').classes('text-lg font-bold')
            term('route')
        lines=route_lines(r.spec)
        ui.label(lines[0]).classes('font-medium')
        for title,prefix,colour in (('Physics included','Included: ','text-gray-800'),
                                    ('Not included','Not included: ','text-amber-800'),
                                    ('How ADROIT reads this model','How ADROIT reads this model: ','text-gray-600')):
            items=[line[len(prefix):] for line in lines if line.startswith(prefix)]
            if items:
                ui.label(title).classes('text-sm font-medium mt-1')
                for item in items:
                    ui.label('• '+item).classes(f'text-sm {colour}')
        for track,name,what,target in (
                ('track1','Constrain this model (Track 1)','its parameter space against every constraint','/new/track1'),
                ('track2','Signal best fits with this model (Track 2)','fit it, beside the library, to a signal',
                 '/new/track2')):
            why=run_status(ready,track,r.spec,r.derivation)
            if why:
                ui.label(f'{name}: not yet. To run it, {why}.').classes('text-gray-700')
            else:
                ui.link(f'{name}: {what}',target+'?'+urlencode({'catalog':r.reference}))


def _launch(root,service,session,kind,text,source,parent='',candidate=0,source_name=''):
    from adroit.ui.pages import rel
    folder=forms.new_folder(root,'model_intake',session.session_id[:8])
    cmd=['models','step',session.session_id,'--kind',kind,'--candidate',str(candidate),'--out',str(folder)]
    if text:
        if kind=='image':
            cmd+=['--text',text]
        else:
            asset=service.catalog.asset_bytes('input.tex' if kind=='tex' else 'input.txt',text.encode(),'user_edit')
            source=service.catalog.asset_path(asset)
    if source:
        cmd+=['--source',str(source)]
    if source_name:
        cmd+=['--source-name',source_name]
    if parent:
        cmd+=['--parent-step',parent]
    if kind not in ('fields','typed'):
        cmd+=['--budget',str(session.budget)]
    job=engine.launch(cmd,folder,'Interpret model',confirmed_budget=session.budget,approval=session.approval)
    submission.go('/live?path='+rel(root,job.folder))

def _paper_pages(equation:ui.input,pages:ui.input,arxiv:ui.input,upload_state:dict)->list[int]:
    """The physical pages of a paper intake, its form checked first (before a session is made: NP17-01)."""
    selected=[int(p.strip()) for p in pages.value.split(',')]
    if not equation.value or not selected or bool(arxiv.value)==bool(upload_state.get('path')):
        raise ValueError('select one PDF upload or arXiv identifier, equation label and physical pages')
    return selected

def _paper(root:Path,s:Session,text:ui.textarea,equation:ui.input,pages:ui.input,arxiv:ui.input,
           upload_state:dict)->None:
    """Launch the budgeted interpretation of one equation in an uploaded or arXiv PDF."""
    from adroit.ui.pages import rel
    selected=_paper_pages(equation,pages,arxiv,upload_state)
    folder=forms.new_folder(root,'model_intake',s.session_id[:8])
    cmd=['models','paper',s.session_id,'--equation',equation.value,'--pages',','.join(map(str,selected)),
         '--budget',str(s.budget),'--out',str(folder)]
    cmd+=['--arxiv',arxiv.value] if arxiv.value else ['--pdf',str(upload_state['path'])]
    if text.value:
        cmd+=['--text',text.value]
    job=engine.launch(cmd,folder,'Interpret paper equation',confirmed_budget=s.budget,approval=s.approval)
    submission.go('/live?path='+rel(root,job.folder))

def _intake_form(root:Path,service:Intake,reference:str)->None:
    """A new intake session: the input, its source, the interpretation model and the budget gate."""
    from adroit.ui.pages import budget_form
    from adroit.ui.style import hint
    kind=ui.select({'idea':'An idea in words (paid)','tex':'TeX (paid)','fields':'A field list (YAML, $0)',
                    'typed':'A typed model (YAML, $0)','image':'A screenshot (paid)',
                    'paper':'An equation in a paper (PDF or arXiv, paid)'},value='idea',label='Model input kind')
    text=ui.textarea('Idea, TeX or typed field/model YAML').classes('w-full').props('rows=12')
    equation=ui.input('Paper equation label (for example 3.1)').bind_visibility_from(kind,'value',backward=lambda v:v=='paper')
    pages=ui.input('Physical PDF pages, comma-separated',value='1').bind_visibility_from(kind,'value',backward=lambda v:v=='paper')
    arxiv=ui.input('Retrieve arXiv identifier instead of uploading (optional)').bind_visibility_from(kind,'value',backward=lambda v:v=='paper')
    upload_state={}
    async def upload(event):
        try:
            asset=service.catalog.asset_bytes(event.file.name,await event.file.read(),'uploaded_source')
            upload_state.update(path=service.catalog.asset_path(asset),name=asset.name)
            ui.notify('Source stored locally for review')
        except (ValueError,OSError) as error:
            ui.notify(str(error))
    ui.upload(label='Or upload a file: TeX, text, YAML, a screenshot or a PDF',on_upload=upload,max_file_size=25_000_000,auto_upload=True) \
        .props('accept=.tex,.txt,.yaml,.yml,.png,.jpg,.jpeg,.webp,.pdf').classes('w-96')
    from adroit.ui.pages import model_select
    intake_model=hint(model_select('Interpretation model (paid)'),'a screenshot needs an Anthropic model')
    gate=budget_form('Session budget ($)',models=(intake_model,))
    ui.label('One budget covers this draft and every refinement of it; a field list or a typed model costs nothing.') \
        .classes('text-sm text-gray-600')
    made={}         # NP17-01: the session this form made, kept for a corrected press if that press's launch failed
    def begin():
        try:
            paid=kind.value not in ('fields','typed')
            verdict=gate() if paid else forms.check_budget(0,False)
            if paid and not verdict.ok:
                ui.notify(verdict.message)
                return
            if kind.value=='paper':                  # the form checked before a session is made
                if reference:
                    raise ValueError('use paper intake for a new model, then refine the saved revision')
                _paper_pages(equation,pages,arxiv,upload_state)
            key=(verdict.amount if paid else 0,intake_model.value)
            if made.get('key')!=key:
                made.update(key=key,session=service.start(key[0],intake_model.value,parent=reference,
                                                          approval=verdict.approval if paid else ''))
            s=made['session']
            parent=service.steps(s.session_id)[-1].step_id if reference else ''
            if kind.value=='paper':
                _paper(root,s,text,equation,pages,arxiv,upload_state)
            else:
                _launch(root,service,s,kind.value,text.value or '',upload_state.get('path'),parent,source_name=upload_state.get('name',''))
        except (ValueError,OSError) as error:
            ui.notify(str(error))
    ui.button('Start reviewed intake',on_click=submission.once(begin)).props('color=primary')
    if reference:
        r=service.catalog.load(reference)
        ui.label(f'Refining pinned model {reference}')
        text.value=r.tex
        kind.value='tex'

def _source_images(service:Intake,d:Draft)->None:
    """Each distinct original source image of the draft, shown once."""
    shown=set()
    for asset in d.sources:
        if asset.suffix in ('.png','.jpg','.jpeg','.webp') and asset.sha256 not in shown:
            shown.add(asset.sha256)
            media={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}[asset.suffix]
            ui.label('Original source image: '+asset.name)
            ui.image('data:'+media+';base64,'+base64.b64encode(service.catalog.asset_path(asset).read_bytes()).decode())

def usable_status(spec,ready:dict|None=None,derivation=None)->bool:
    """The model's status for Constrain a model, plainly (the owner, 2026-11-21: only usable models are offered and
    saved): "Ready to constrain", or "Cannot run yet" with each reason; the values the model builder proposed, with
    its reasons; and what the model leaves out of the idea. Whether it is usable. A model with its own matching
    (``derivation``, kept from an unchanged parent: the auditor's UO-03) is judged as Signal best fits takes it (D6)."""
    verdict=usable(spec,derivation,ready=ready)
    with ui.column().classes('w-full gap-1 my-1').mark('usable_status'):
        if verdict.ok:
            ui.badge('Ready to constrain' if derivation is None else 'Ready: it brings its own matching (Signal best '
                     'fits)',color='green').classes('text-sm')
        else:
            ui.badge('Cannot run yet: it can be saved once these are settled',color='orange').classes('text-sm')
            for reason in verdict.blocking:
                ui.label('• '+reason).classes('text-sm text-amber-900')
        proposed=[c for c in spec.couplings if c.justification.startswith('proposed by the model builder')]
        if proposed:
            ui.label('Values proposed by the model builder (inputs you may change):').classes('text-sm font-medium')
            for c in proposed:
                ui.label(f'• {c.name} = {c.value:g}: '+c.justification.removeprefix('proposed by the model builder')
                         .lstrip(': ')).classes('text-sm text-gray-700')
        universal=[a for a in spec.assumptions if 'applies alike to all three generations' in a]
        if universal:
            ui.label('Flavour (one coupling for every generation):').classes('text-sm font-medium')
            for a in universal:
                ui.label('• '+a).classes('text-sm text-gray-700')
        if spec.dropped:
            ui.label('Left out of the idea:').classes('text-sm font-medium')
            for item in spec.dropped:
                ui.label('• '+item).classes('text-sm text-amber-800')
    return verdict.ok


def missing_values(spec)->list[tuple[str,str]]:
    """What a model still needs a number for: ('mass', field) and ('coupling', name), in the model's order."""
    return ([('mass',f.name) for f in spec.fields if f.role.value!='standard_model' and f.mass_gev is None]
            +[('coupling',c.name) for c in spec.couplings if c.value is None])


def with_values(spec,given:dict[tuple[str,str],float]):
    """The model with the numbers typed for its missing masses (GeV) and couplings; one left empty stays missing."""
    fields=[f.model_copy(update={'mass_gev':float(given[('mass',f.name)]),'mass_justification':'given at review'})
            if given.get(('mass',f.name)) is not None else f for f in spec.fields]
    couplings=[c.model_copy(update={'value':float(given[('coupling',c.name)]),'justification':'given at review'})
               if given.get(('coupling',c.name)) is not None else c for c in spec.couplings]
    return spec.model_copy(update={'fields':fields,'couplings':couplings})


def _completion_panel(service:Intake,session:str,d:Draft,index:int,choice:DraftChoice)->None:
    """A box for each missing number; applying them makes a new draft ($0, no language model), as a typed correction."""
    needed=missing_values(choice.spec)
    if not needed:
        return
    with ui.card().classes('w-full').mark('complete_model'):
        ui.label('Complete this model ($0)').classes('font-medium')
        boxes={key:ui.number(f'mass of {key[1]} (GeV)' if key[0]=='mass' else f'value of {key[1]}')
               for key in needed}
        def apply():
            try:
                given={k:b.value for k,b in boxes.items() if b.value is not None}
                if not given:
                    raise ValueError('give at least one value')
                spec=with_values(choice.spec,given)
                text=yaml.safe_dump(spec.model_dump(mode='json'),sort_keys=False,allow_unicode=True)
                draft=service.step(session,'typed',text,parent_step=d.step_id,candidate=index)
                submission.go('/models/intake?'+urlencode({'session':session,'step':draft.step_id}))
            except (ValueError,OSError) as error:
                ui.notify(str(error))
        ui.button('Apply these values as a new draft',on_click=submission.once(apply)).props('outline')


def _candidate_summary(service:Intake,session:str,d:Draft,choice:DraftChoice)->bool:
    """The candidate's explanation, changes from the prior draft, support, identity and ambiguities; whether it is
    usable, judged now (the same answer its Save button follows: the auditor's UM-07)."""
    ui.label(choice.explanation)
    if choice.simplified:                       # the owner, 2026-11-17: said in its name and here
        ui.label(f'A simplified model: it leaves out {choice.simplified}.').classes('text-amber-800').mark('simplified')
    if d.parent_step:
        from adroit.orchestrator.model_approval import _changes
        previous=service.load(session,d.parent_step).choices[d.parent_candidate].spec
        changed=_changes(previous.model_dump(mode='json'),choice.spec.model_dump(mode='json'))
        if changed:
            ui.code('Changes from prior draft:\n'+'\n'.join(changed))
    matching=service.inherited_matching(session,d,choice)     # an unchanged parent's own matching (UO-03)
    ready=support(choice.spec,matching)
    ok=usable_status(choice.spec,ready,matching)
    why=run_status(ready,'track2',choice.spec,matching)
    ui.label('Signal best fits: '+('ready' if not why else 'not yet; to run it, '+why)).classes('text-sm text-gray-700')
    for issue in choice.ambiguities:
        ui.label('Interpretation uncertainty: '+issue).classes('text-amber-800')
    ui.label(f'Model identity (the approval hash; `adroit models approve --expected-hash`): {model_identity(choice.spec)}').classes('font-mono text-xs text-gray-500')
    return ok

def _candidate_panel(root:Path,service:Intake,s:Session,session:str,d:Draft,index:int,choice:DraftChoice)->None:
    """One candidate: its review, typed corrections, a new interpretation, and approval as a revision."""
    if index:                                       # a medium rule between candidates (JU1)
        ui.element('hr').classes('w-full my-4').style('border:none;border-top:3px solid #9AA5AE').mark('candidate_rule')
    with ui.expansion(f'Candidate {index+1}: {choice.spec.name}',value=True).classes('w-full') \
            .props('header-class="text-weight-bold text-base"').mark('candidate'):
        from adroit.ui.typeset import show_model
        show_model(choice.spec,root/'.typeset')
        ok=_candidate_summary(service,session,d,choice)
        _completion_panel(service,session,d,index,choice)
        tex=ui.textarea('Editable TeX',value=choice.tex).classes('w-full').props('rows=10')
        canonical=ui.textarea('Canonical model YAML',value=yaml.safe_dump(choice.spec.model_dump(mode='json'),sort_keys=False,allow_unicode=True)) \
            .classes('w-full font-mono').props('rows=15')
        instructions=ui.textarea('Refinement or clarification instructions').classes('w-full')
        confirmed=ui.checkbox('I reviewed the transcription, assumptions, parameters and canonical model')
        from adroit.ui.discovery import approval_option
        discover=approval_option()
        style_declarations=ui.textarea(label='Reviewed model property declarations (JSON)',value='').classes('w-full').props('rows=6')
        def typed_edit():
            try:
                draft=service.step(session,'typed',canonical.value,parent_step=d.step_id,candidate=index)
                submission.go('/models/intake?'+urlencode({'session':session,'step':draft.step_id}))
            except (ValueError,OSError) as error:
                ui.notify(str(error))
        def reinterpret(kind):
            try:
                if read_model(yaml.safe_load(canonical.value))!=choice.spec:
                    raise ValueError('apply typed corrections before asking for another interpretation')
                _launch(root,service,s,kind,tex.value if kind=='tex' else instructions.value,None,d.step_id,index)
            except (ValueError,OSError) as error:
                ui.notify(str(error))
        def approve():
            try:
                spec=read_model(yaml.safe_load(canonical.value))
                if spec!=choice.spec:
                    raise ValueError('apply typed corrections as a new draft before approval')
                from adroit.core.model_preferences import StyleDeclaration
                raw=json.loads(style_declarations.value) if (style_declarations.value or '').strip() else None
                if raw is not None and not isinstance(raw,list):
                    raise ValueError('model property declarations must be a JSON list')
                declarations=[StyleDeclaration.model_validate(d) for d in raw] if raw is not None else None
                r=service.approve(session,d.step_id,index,confirmed=confirmed.value,
                    expected_model_hash=model_identity(spec),tex=tex.value,style_declarations=declarations)
                from adroit.ui.pages import rel
                job=discover(root,r.reference,r.spec.name)      # after the approval, as its own job, if opted in
                submission.go(f'/live?path={rel(root,job.folder)}' if job else
                               '/models/view?'+urlencode({'reference':r.reference}))
            except (ValueError,OSError,TypeError) as error:
                ui.notify(str(error))
        ui.label('Edit the YAML and apply your corrections ($0), or ask the language model to reinterpret the TeX or to '
                 'refine the model with your instructions (paid); when it is right, tick the review box and save it.') \
            .classes('text-sm text-gray-600')
        with ui.row().classes('gap-2'):
            ui.button('Apply typed corrections',on_click=submission.once(typed_edit)).props('outline')
            ui.button('Interpret edited TeX',on_click=submission.once(lambda:reinterpret('tex'))).props('outline')
            ui.button('Refine this candidate',on_click=submission.once(lambda:reinterpret('refine'))).props('outline')
            save=ui.button('Save reviewed revision',on_click=submission.once(approve)).props('color=primary')
            if not ok:
                save.disable()                      # the owner, 2026-11-21: an unusable model is not saved
                save.tooltip('It cannot run yet: complete it first (its status above says what is missing)')

def _session_money(service:Intake,session:str)->str:
    """A session's spending from its paid ledger, against its approved cap (``accounting.session_money``)."""
    from adroit.orchestrator.accounting import session_money
    return session_money(service,session)

def _session_runs(root:Path,session:str)->list:
    """The workbench runs of an intake session (``models step``/``models paper`` with its identifier), newest first."""
    return [j for j in engine.jobs(root) if j.command[:1]==['models'] and j.command[2:3]==[session]]

def _no_draft(root:Path,service:Intake,s:Session)->None:
    """A session with no draft yet: its spending, its runs (running, or why each ended without a draft) and what to
    do next; "pending" only while a run of it is running (the owner's report of 2026-10-23)."""
    from adroit.ui import outcomes
    from adroit.ui.pages import rel
    ui.label('This session: '+_session_money(service,s.session_id)).classes('text-gray-700').mark('session_money')
    runs,lost=engine.polled(_session_runs(root,s.session_id))      # one that cannot be read is named (NP17-03)
    from adroit.ui.pages import _damaged
    _damaged(root,'run record(s) of this session',lost,'unreadable_runs')
    if any(j.status=='running' for j in runs):
        ui.label('Interpretation is running: its draft appears here when the run completes.').mark('no_draft')
    elif runs:
        ui.label('No draft yet: the runs of this session ended without one.').mark('no_draft')
    else:
        ui.label('No draft in this session yet, and no workbench run of it is recorded.').mark('no_draft')
    for job in runs:
        result=outcomes.outcome(root,Path(job.folder),job)
        with ui.row().classes('items-baseline gap-2'):
            ui.badge(job.status)
            ui.link(f'{job.title}: {result.headline}','/live?'+urlencode({'path':rel(root,job.folder)}))
    if s.budget>0:
        from adroit.ui.pages import cap_controls
        cap_controls(service,s.session_id,'/models/intake?'+urlencode({'session':s.session_id}))
    ui.link('Start a new model intake','/models/intake')

def not_offered(d:Draft)->None:
    """The model builder's proposals not offered, each with why (never dropped in silence); and, where none was
    usable, that plainly, with what to do."""
    if not d.choices and d.kind=='idea':
        ui.label('No usable model could be built from this idea.').classes('text-lg text-amber-900').mark('no_usable')
        ui.label('Each proposal is listed below with why it cannot run, including any repair round the model builder made. '
                 'Reword the idea (name the couplings and masses it needs), or write the model as a typed model ($0).'
                 ).classes('text-sm text-gray-700')
        ui.link('Write it as a typed model ($0)','/models/intake').mark('typed_model')     # phase C: the offer
    if d.not_offered:
        with ui.expansion(f'Proposals not offered ({len(d.not_offered)})',value=not d.choices).classes('w-full') \
                .mark('not_offered'):
            for item in d.not_offered:
                ui.label('• '+item).classes('text-sm text-gray-700')


def intake_page(root,session='',step='',reference=''):
    """Reviewed model intake: the form for a new session, or a session's pinned draft with its candidates to correct,
    refine or approve."""
    from adroit.ui.pages import header
    header('Create or refine a model','Turn an idea, TeX, a field list, a screenshot or an equation in a paper into a '
           'model: a language model drafts it, you review and correct it, and the approved model is saved to your '
           'library as a revision.',facts=('a field list or typed model: $0','words, TeX, screenshots, papers: paid',
           'next: the model\'s page, to run it'))
    service=Intake()
    if not session:
        _intake_form(root,service,reference)
        return
    s=service.session(session)
    drafts,damaged=service.listing(session)
    from adroit.ui.pages import _damaged
    _damaged(root,'draft step(s) of this session',damaged,'unreadable_steps')       # CA-07: named, the rest shown
    if not drafts:
        _no_draft(root,service,s)
        return
    d=service.load(session,step) if step else drafts[-1]
    ui.label('This session: '+_session_money(service,session)).classes('text-gray-700').mark('session_money')
    with ui.row().classes('items-center gap-1 text-xs text-gray-500'):
        ui.label(f'session {session[:8]}… · draft {d.step_id[:10]}…')
    if s.budget>0:
        from adroit.ui.pages import cap_controls
        cap_controls(service,session,'/models/intake?'+urlencode({'session':session,'step':d.step_id}))
    ui.code(d.transcription,language='latex').classes('w-full')
    _source_images(service,d)
    not_offered(d)
    for index,choice in enumerate(d.choices):
        _candidate_panel(root,service,s,session,d,index,choice)

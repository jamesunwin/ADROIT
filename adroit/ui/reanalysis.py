"""Saved inputs and explicit review, through the same public reanalysis service."""
from urllib.parse import urlencode
from pathlib import Path
from typing import Any, Callable
import yaml
from nicegui import ui
from adroit.orchestrator.reanalysis import Reanalysis
from adroit.ui import forms,engine,submission

def page(root:Path,source:str='',reference:str='',target:str='',model_index:int=0,sha256:str='',
         evidence:str='')->None:
    """Present saved inputs and require review of a fresh child calculation; ``sha256``, the digest of the saved
    study's result as the page that linked here showed it, and ``evidence``, the identity of its evidence as that page
    read it (VI-03), which the draft then requires."""
    from adroit.ui.pages import header
    header('Start a new run from saved inputs','Reopen a saved study, model or confirmed signal with its inputs filled '
           'in, review and change them, then run a fresh analysis; the original result and its dates are kept as they '
           'are.',facts=('$0','next: review the inputs, then run'))
    service=Reanalysis()
    if not reference:
        _reopen_form(root,service,source,target,model_index,sha256,evidence)
        return
    draft=service.load(reference)
    ui.label('Immutable draft: '+reference+'; created UTC '+draft.created_at)
    ui.label('Source '+draft.source+'; '+draft.source_sha256)
    ui.label('A fresh child analysis will retain the original result and calculation dates. Source/profile changes are explicit; no automatic latest selection.')
    _model_choice(service,reference,draft)
    edited_request=_inputs(draft)
    _review_and_run(root,service,reference,draft,edited_request)


def _reopen_form(root:Path,service:Reanalysis,source:str,target:str,model_index:int,sha256:str='',
                 evidence:str='')->None:
    """The choice of saved inputs to reopen, and how to run them; ``sha256``, the version of ``source`` its study page
    showed, and ``evidence``, its evidence as that page read it, required while that source is the one chosen (the auditor's
    CX recheck, CY-03, 2026-11-01; its version-identity audit, VI-03, 2026-11-03)."""
    from adroit.ui.style import hint
    picks=_sources(root)
    from adroit.ui.wizards import _unoffered
    _unoffered(root)
    if picks:
        pick=ui.select(picks,label='A saved study or model').classes('w-full')
        pick.on_value_change(lambda e: setattr(source_field,'value',e.value or ''))
    source_field=hint(ui.input('Saved study/result, catalog model or confirmed anomaly',value=source).classes('w-full'),
                      'filled in by the choice above, or paste a result path, a catalog: reference or an anomaly: one')
    choice=ui.select({'':'the same kind as the original','track1':'Constrain a model','signal':'Signal best fits'},
                     value=target,label='Run it as')
    index=hint(ui.number('Saved physical model index',value=model_index,min=0),
               'for a study with several models: which one (0 is the first)')
    if sha256 and source:
        ui.label(f'From the version of this study its page showed (result SHA-256 {sha256[:12]}…); if it has changed '
                 'since, nothing is drafted.').classes('text-xs text-gray-600').mark('reanalysis_version')

    def reopen()->None:
        try:
            from adroit.evidence.version import Token
            same=source_field.value==source and bool(sha256)
            draft=service.open(source_field.value,choice.value,int(index.value),
                               token=Token(source,sha256,evidence) if same else None)
            ui.navigate.to('/reanalyse?'+urlencode({'reference':draft.reference}))
        except (ValueError,OSError,KeyError,RuntimeError) as error:
            ui.notify(str(error))
    ui.button('Reopen saved inputs',on_click=reopen).props('color=primary')


def _model_choice(service:Reanalysis,reference:str,draft)->None:
    """Replace a model of the draft by an approved revision, and the links to refine models and sources."""
    from adroit.ui.model_library import filled_later, options
    track='track1' if draft.workflow=='track1' else 'track2'
    selected=ui.select({},label='Replace with an approved personal model revision').classes('w-full')
    filled_later(selected,lambda:options(track))                        # off the event loop (OL-01)
    index=ui.number('Model slot to replace',value=0,min=0)
    def choose_model()->None:
        try:
            revised=service.choose_model(reference,selected.value or '',int(index.value))
            ui.navigate.to('/reanalyse?'+urlencode({'reference':revised.reference}))
        except (ValueError,OSError,KeyError,RuntimeError) as error:
            ui.notify(str(error))
    ui.button('Select revised model',on_click=choose_model)
    models=draft.request.get('user_models',[]) if draft.workflow=='signal' else [draft.request]
    for model in models:
        if model.get('catalog_reference'):
            ui.link('Refine this model before reanalysis','/models/intake?'+urlencode({'reference':model['catalog_reference']}))
    ui.link('Review experimental sources/updates','/experiments')
    ui.link('Review experimental profiles','/experiments/profiles')


def _scan_table(draft,holder:dict)->None:
    """A Track 1 request's scan as the parameter table (``ui.scan_editor``); edits rewrite the request's axes in the
    YAML below, which stays the advanced view and what is reviewed."""
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.scan import Axis
    from adroit.parameter_space.scan_table import setup_of
    from adroit.ui.scan_editor import scan_editor
    request=draft.request
    try:
        setup=setup_of(ModelSpec.model_validate(request['spec']),*(Axis.model_validate(request[k]) if request.get(k) else None
                       for k in ('x','y')),request.get('mediator_ratio'))
    except (ValueError,KeyError,TypeError) as error:
        ui.label(f'The scan cannot be shown as a table ({error}); edit it in the YAML.').classes('text-sm text-gray-600')
        return
    ui.label('The scan, as a table of parameters').classes('font-medium')
    def edited(x,y,ratio)->None:
        holder.pop('invalid',None)
        data=yaml.safe_load(holder['editor'].value)
        data.update(x=x.model_dump(mode='json'),y=y.model_dump(mode='json'),mediator_ratio=ratio)
        holder['editor'].value=yaml.safe_dump(data,sort_keys=False)
    def invalid(reason)->None:                 # an invalid table never leaves the old axes runnable (S18-08)
        holder['invalid']=reason
    scan_editor(setup,edited,invalid)


def _inputs(draft)->Callable[[],dict[str,Any]]:
    """The profile, the experiment and the request's YAML; returns the request as edited."""
    from adroit.ui.experimental_profiles import options as profile_options,search_options
    profiles=profile_options()
    old_profile=draft.request.get('experimental_profile','')
    if old_profile and old_profile not in profiles:
        profiles[old_profile]='Recorded profile (renew validation if stale)'
    profile=ui.select(profiles,value=old_profile or 'none',label='Exact experimental profile for this new run').classes('w-full')
    experiment=None
    if draft.workflow!='track1':
        from adroit.experiments.registry import signal_search_names
        names={n:n for n in signal_search_names()}
        names.update(search_options('signal'))
        old=draft.request.get('experiment','')
        names[old]=old or 'Select a supported anomaly/search'
        experiment=ui.select(names,value=old,label='Experimental input for this new analysis').classes('w-full')
    holder:dict={}
    if draft.workflow=='track1':
        _scan_table(draft,holder)
    editor=ui.textarea('Prepopulated numerical/scientific request (YAML)',value=yaml.safe_dump(draft.request,sort_keys=False)).classes('w-full font-mono').props('rows=18')
    holder['editor']=editor
    def edited_request()->dict[str,Any]:
        if holder.get('invalid'):              # saving or running the old axes is refused (S18-08)
            raise ValueError(f"the scan table is invalid ({holder['invalid']}): correct it, then save and review")
        data=yaml.safe_load(editor.value)
        data['experimental_profile']='' if profile.value=='none' else profile.value
        if experiment is not None:
            data['experiment']=experiment.value
        return data
    return edited_request


def _review_and_run(root:Path,service:Reanalysis,reference:str,draft,edited_request)->None:
    """Save and review the draft, then run the reviewed child analysis under the reviewer's name."""
    from adroit.ui.pages import rel
    state={}
    view=ui.column()
    reviewer=ui.input('Analysis reviewer name')
    confirmed=ui.checkbox('I reviewed the exact model, source/profile, assumptions and numerical changes')
    def review()->None:
        try:
            changed=edited_request()
            if changed!=draft.request:
                revised=service.revise(reference,changed)
                ui.navigate.to('/reanalyse?'+urlencode({'reference':revised.reference}))
                return
            state['review']=service.preview(reference)
            view.clear()
            with view:
                ui.code(yaml.safe_dump(state['review'],sort_keys=False))
        except (ValueError,OSError,KeyError,TypeError) as error:
            ui.notify(str(error))
    def start()->None:
        try:
            if edited_request()!=draft.request:
                raise ValueError('save and review changed inputs as a new draft before running')
            reviewed=state.get('review')
            if not reviewed or reviewed['blockers'] or not confirmed.value or not (reviewer.value or '').strip():
                raise ValueError('review a calculable exact draft and enter your name/confirmation before running')
            output_root=Path(draft.source).parent if draft.source_kind=='study' else root
            if not output_root.resolve().is_relative_to(root.resolve()):
                raise ValueError('saved study is outside the workbench runs directory; use reanalyse CLI or set ADROIT_RUNS_DIR to its containing directory')
            folder=forms.new_folder(output_root,'reanalysis',draft.workflow)
            command=['reanalyse','run',reference,'--expected-hash',reviewed['review_sha256'],'--by',reviewer.value,'--confirmed','--out',str(folder)]
            job=engine.launch(command,folder,'Reanalysis '+draft.workflow)
            submission.go('/live?path='+rel(root,job.folder))
        except (ValueError,OSError,KeyError,TypeError) as error:
            ui.notify(str(error))
    ui.button('Save changes / review this draft',on_click=review)
    ui.button('Run fresh reviewed child analysis',on_click=submission.once(start))


def _sources(root: Path) -> dict[str, str]:
    """Saved studies (by their result) and personal models (by their reference), for the picker; each study named as
    its record read with its result names it (``study_headline.listed``; DC-01)."""
    from adroit.orchestrator.study_headline import listed, offered
    out={str(found.path):f'study: {listed(found)}' for found in offered(root,('track1','signal','single_idea'))}
    from adroit.ui.model_library import options
    out.update({ref:f'model: {name}' for ref,name in options().items()})
    return out

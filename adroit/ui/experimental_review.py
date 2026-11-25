"""Expert source checks and numerical validation remain separate UI actions."""
import json
from pathlib import Path
from nicegui import ui
from adroit.constraints.experimental_review import (packet,approve,validate,bind,rendered_packet,CHECKLIST,load_bound,
                                                    verify_figure,FIGURE_CHECKLIST)
from adroit.library.experimental import ExperimentalCatalog
from adroit.statistics.optimum_interval import OptimumIntervalUnavailable
from adroit.ui import forms
from adroit.ui.style import embedded

def limit_options() -> dict[str,str]:
    """Only current eligible immutable bindings are offered for explicit selection."""
    catalog=ExperimentalCatalog()
    result={}
    for path in catalog.path('limits').glob('*.json'):
        try:
            bound=load_bound('private-limit:'+path.stem,catalog)
            result[bound.reference]=bound.name+'; '+str(bound.contract.confidence_level)+' CL; '+bound.created_at
        except (ValueError,OSError):
            continue
    return result

def review_tools(root: Path,catalog,revision,editor) -> None:
    """Display scoped data/source differences, six review checks and independent validation."""
    for item in revision.dossier.results:
        def panel(item):
            with ui.expansion('Expert source review: '+item.result_id):
                state=_review_packet(root,catalog,revision,item)
                from adroit.ui.record_check import model_check_tools
                model_check_tools(root,catalog,revision,item)       # a person first; a model's check at your choice
                reviewer=ui.input('Expert reviewer name')
                checks={name:ui.checkbox('Checked: '+name) for name in CHECKLIST}
                consent=ui.checkbox('I personally checked the selected source values and scientific assumptions')
                review_id=ui.input('Source review receipt ID')
                validation_id=ui.input('Numerical validation receipt ID')
                tolerance=ui.number('Source-anchor tolerance (relative)',value=.02,min=1e-8,max=.3)
                def unchanged():
                    if json.loads(editor.value)!=revision.dossier.model_dump(mode='json'):
                        raise ValueError('save scientific edits as a new revision before review/validation')
                def sign():
                    try:
                        unchanged()
                        data=state['packet']
                        receipt=approve(revision.reference,item.result_id,data['scientific_sha256'],reviewer.value or '',
                            confirmed=consent.value,checks=[k for k,v in checks.items() if v.value],keys=data['keys'],catalog=catalog)
                        review_id.value=receipt.review_id
                        ui.notify('Source assertion recorded; numerical validation remains separate')
                    except (ValueError,OSError,KeyError) as error:
                        ui.notify(str(error))
                ui.button('Sign this source-review scope',on_click=sign)
                def check_numbers():
                    try:
                        unchanged()
                        data=packet(revision.reference,item.result_id,['limit_contract','validation_reference'],catalog)
                        receipt=validate(revision.reference,item.result_id,float(tolerance.value),data['scientific_sha256'],catalog)
                        validation_id.value=receipt.validation_id
                        ui.label('Anchor validation: '+str(receipt.passed)+'; errors '+str(receipt.relative_errors)+'; '+receipt.scope)
                    except (ValueError,OSError,KeyError) as error:
                        ui.notify(str(error))
                def select_limit():
                    try:
                        unchanged()
                        receipt=bind(revision.reference,item.result_id,review_id.value or '',validation_id.value or '',catalog)
                        ui.notify('Pinned private limit ready to select when constraining a model: '+receipt.reference)
                        ui.link('Open Constrain a model','/new/track1')
                    except (ValueError,OSError) as error:
                        ui.notify(str(error))
                if {'limit_contract','validation_reference'}<=set(c.key for c in item.claims):
                    ui.button('Validate independent published anchors ($0)',on_click=check_numbers)
                    contract=next(c.value for c in item.claims if c.key=='limit_contract')
                    if isinstance(contract,dict) and contract.get('origin')=='figure_digitised':
                        figure_tools(revision,item,catalog,reviewer,tolerance,validation_id,unchanged,state)
                    ui.button('Prepare pinned private-limit selection',on_click=select_limit)
                if {'search_contract','adapter_validation_reference'}<=set(c.key for c in item.claims):
                    _search_tools(revision,item,catalog,tolerance,review_id,validation_id,unchanged)
        panel(item)

def _review_packet(root: Path,catalog,revision,item) -> dict:
    """The packet of the selected scientific fields, re-rendered on each selection (with the plots once the limit and
    its validation reference are selected); returns the state the review actions read. Its images are the bytes its
    rendering wrote, embedded in the page, never its files named for the browser to read later; and the figure
    verification is bound to the packet shown (``shown``: its digests) and its folder (the auditor's DH recheck, DI-01,
    2026-11-06: another packet written into the folder after the rendering returned had been shown, its plots beside
    this source's text)."""
    selected=ui.select([c.key for c in item.claims],multiple=True,value=[c.key for c in item.claims],label='Scientific fields to review')
    state={}
    view=ui.column()
    def render():
        view.clear()
        for name in ('packet','plots','shown'):             # a rendering that fails leaves nothing shown to review
            state.pop(name,None)
        try:
            data=packet(revision.reference,item.result_id,selected.value,catalog)
            state['packet']=data
            with view:
                ui.code(json.dumps(data,indent=2),language='json')
                if {'limit_contract','validation_reference'}<=set(selected.value):
                    out=forms.new_folder(root,'source_review',item.result_id)
                    plots,images=rendered_packet(revision.reference,item.result_id,out,catalog)
                    ui.image(embedded(images['plot'])).mark('review_image')
                    if images['source_overlay'] is not None:
                        ui.image(embedded(images['source_overlay'])).mark('review_image')
                        state['shown']=tuple(plots[k] for k in ('source_image_sha256','geometry_sha256','overlay_sha256'))
                    state['plots']=out                      # the packet shown: verify-figure binds to it
                    ui.label(plots['overlay_status'])
        except (ValueError,OSError,KeyError) as error:
            ui.notify(str(error))
    render()
    selected.on_value_change(lambda _:render())
    return state

def _search_tools(revision,item,catalog,tolerance,review_id,validation_id,unchanged) -> None:
    """The event-search route: validate the adapter's independent anchors, then pin the private search."""
    def check_search():
        try:
            from adroit.constraints.experimental_search_review import validate as validate_search
            unchanged()
            data=packet(revision.reference,item.result_id,catalog=catalog)
            receipt=validate_search(revision.reference,item.result_id,float(tolerance.value),data['scientific_sha256'],catalog)
            validation_id.value=receipt.validation_id
            ui.label('Event adapter validation: '+str(receipt.passed)+'; errors '+str(receipt.errors))
        except (ValueError,OSError,KeyError,OptimumIntervalUnavailable) as error:    # a tool's refusal named (DW-05)
            ui.notify(f'Not validated: {error}' if isinstance(error,OptimumIntervalUnavailable) else str(error))
    def select_search():
        try:
            from adroit.constraints.experimental_search_review import bind as bind_search
            unchanged()
            receipt=bind_search(revision.reference,item.result_id,review_id.value or '',validation_id.value or '',catalog)
            ui.notify('Pinned private search ready: '+receipt.reference)
            ui.link('Review a personal profile','/experiments/profiles')
        except (ValueError,OSError) as error:
            ui.notify(str(error))
    ui.button('Validate independent event/response/interval anchors ($0)',on_click=check_search)
    ui.button('Prepare pinned private-search selection',on_click=select_search)

def figure_tools(revision,item,catalog,reviewer,tolerance,validation_id,unchanged,state) -> None:
    """The manual figure-verification route for a curve digitised from a figure with one or two printed anchors:
    the declared mass range restated, the five checks attested, under the reviewer's name."""
    ui.label('A curve digitised from a figure with fewer than three printed anchors can be verified by hand against '
             'the calibrated overlay above; the receipt says so and is not the ordinary validation.')
    low=ui.number('Reviewed mass range from (GeV)')
    high=ui.number('Reviewed mass range to (GeV)')
    checks={name:ui.checkbox('Figure check: '+name) for name in FIGURE_CHECKLIST}
    consent=ui.checkbox('I compared the calibrated overlay with the figure over the whole declared range')
    def verify():
        try:
            unchanged()
            data=packet(revision.reference,item.result_id,['limit_contract','validation_reference'],catalog)
            receipt=verify_figure(revision.reference,item.result_id,float(tolerance.value),data['scientific_sha256'],
                                  reviewer.value or '',confirmed=consent.value,checks=[k for k,v in checks.items() if v.value],
                                  reviewed_range=(float(low.value or 0),float(high.value or 0)),
                                  packet=state.get('plots') or Path('.'),catalog=catalog,shown=state.get('shown',()))
            validation_id.value=receipt.validation_id
            ui.label('Figure verification: '+str(receipt.passed)+'; '+receipt.scope)
        except (ValueError,OSError,KeyError) as error:
            ui.notify(str(error))
    ui.button('Verify the figure by hand ($0)',on_click=verify)

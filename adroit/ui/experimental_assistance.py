"""Budgeted source interpretation and explicit exploratory-anomaly confirmation."""
import json
from pathlib import Path
from urllib.parse import urlencode
from nicegui import ui
from adroit.core.experimental_input import ExperimentalDossier
from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
from adroit.orchestrator.anomaly_intake import acknowledgements,interpretation,confirm
from adroit.ui import forms,engine,submission


def revision_tools(root: Path,catalog,revision,editor) -> None:
    """Attach assisted extraction and dirty-edit-safe result confirmation controls."""
    from adroit.ui.pages import budget_form
    from adroit.ui.style import section
    card=section('Interpret it with a language model (optional, paid)','The selected pages, text and images are sent '
                 'to the provider, which proposes each value with its source location. One session budget covers every '
                 'batch and refinement.')
    with card:
        from adroit.ui.pages import model_select
        model=model_select('Interpretation model (paid)')
        gate=budget_form('Session budget ($)',models=(model,))
        text_only=ui.checkbox('Text-only PDF extraction (scans require vision)')
    def begin():
        try:
            budget=gate()
            if not budget.ok:
                ui.notify(budget.message)
                return
            scope=ExperimentalExtraction(catalog).start(revision.reference,budget.amount,model.value,not text_only.value,
                                                        approval=budget.approval)
            ui.navigate.to('/experiments/session?'+urlencode({'session':scope.session_id}))
        except (ValueError,OSError) as error:
            ui.notify(str(error))
    with card:
        ui.button('Start assisted interpretation',on_click=begin).props('color=primary')
    for result in revision.dossier.results:
        def panel(result):
            value=interpretation(revision.reference,result.result_id,catalog)
            with ui.expansion('Confirm understanding: '+result.result_id,value=True):
                ui.label(value.explanation)
                for warning in [*value.evidence_warnings,*value.blockers]:
                    ui.label(warning)
                ui.code(value.record.model_dump_json(indent=2) if value.record else result.model_dump_json(indent=2))
                person=ui.input('Researcher name')
                accepted={token:ui.checkbox('Accept assumed value/approximation: '+token)
                          for token in acknowledgements(revision.reference,result.result_id,catalog)}
                consent=ui.checkbox('I checked the interpretation and accept exploratory use; source verification remains pending')
                def approve():
                    try:
                        if ExperimentalDossier.model_validate_json(editor.value)!=revision.dossier:
                            raise ValueError('save edited dossier as a new revision before confirmation')
                        receipt=confirm(revision.reference,result.result_id,value.interpretation_sha256,person.value or '',
                            confirmed=consent.value,accepted_assumptions=[k for k,c in accepted.items() if c.value],catalog=catalog)
                        ui.notify('Interpretation confirmed: '+receipt.reference)
                        if receipt.interpretation.record and not receipt.interpretation.blockers:
                            ui.link('Continue: signal best fits','/new/track2?'+urlencode({'anomaly':receipt.reference}))
                            ui.link('Reopen this confirmed anomaly for a new analysis','/reanalyse?'+urlencode({'source':receipt.reference}))
                    except (ValueError,OSError) as error:
                        ui.notify(str(error))
                ui.button('Confirm this interpretation',on_click=approve)
        panel(result)


def session_page(root: Path,session: str) -> None:
    """Display coverage/cost and run batches/refinements under the durable cap."""
    from adroit.ui.pages import header,rel
    service=ExperimentalExtraction()
    scope=service.scope(session)
    owner=service.budget_owner(session)       # a linked discovery session's budget is that session's (CA-04)
    s=service.budgets.session(owner)
    header('Experimental interpretation session','A language model reads the selected source pages in batches and '
           'proposes the dossier; preview a batch\'s cost ($0), interpret it, and refine with your instructions. Every '
           'value it proposes stays unreviewed until you review it.')
    from adroit.orchestrator.accounting import session_money
    steps,damaged_steps=service.step_listing(session)           # a damaged step named, the rest shown (M3)
    from adroit.ui.pages import _damaged
    _damaged(None,'interpretation step(s) of this session',damaged_steps,'unreadable_steps')
    read={i for step in steps for i in step.unit_ids}
    selected={i for batch in scope.batches for i in batch}
    shared=f' (the budget of discovery session {owner[:8]}, which this session shares)' if owner!=session else ''
    ui.label(f'Budget{shared}: {session_money(service.budgets,owner)}.').classes('text-gray-700').mark('session_money')
    ui.label(f'Read {len(read)} of {len(selected)} selected source units.').classes('text-gray-700')
    from adroit.ui.pages import cap_controls
    cap_controls(service.budgets,owner,'/experiments/session?'+urlencode({'session':session}))
    ui.label(f'Not selected {len(scope.units)-len(selected)}; unread {len(selected-read)}. Partial coverage is not complete-paper verification.')
    if steps:
        ui.label(steps[-1].explanation)
        for issue in [*steps[-1].ambiguities,*steps[-1].evidence_problems]:
            ui.label(issue)
        ui.link('Review interpreted dossier and anomalies','/experiments/view?'+urlencode({'reference':steps[-1].output_revision}))
    names={u.unit_id:(u.source_name or 'source')+(f' p.{u.page}' if u.page else '') for u in scope.units}
    batch=ui.select({i:f'Batch {i+1}: '+', '.join(sorted({names.get(x,x[:10]) for x in ids})) for i,ids in enumerate(scope.batches)},
                    value=0,label='Source batch').classes('w-full')
    instruction=ui.textarea('Refinement / clarification instructions',
                            placeholder='e.g. the exposure is quoted after cuts; use the efficiency of Fig. 2') \
        .classes('w-full').props('rows=4')
    bound=ui.label('Preview source scope and cost before interpreting.')
    def preview():
        try:
            plan=service.preview(session,int(batch.value),instruction.value or '')
            from adroit.orchestrator.accounting import status_text, usd
            bound.text=(f'Request bound {usd(plan["request_bound_usd"])} (retries separately reserved); the budget: '
                        +status_text(plan['budget'])+'.')
            ui.code(json.dumps(plan,indent=2)).classes('w-full')
        except (ValueError,OSError) as error:
            ui.notify(str(error))
    with ui.row().classes('gap-2'):
        ui.button('Preview source coverage and cost ($0)',on_click=preview).props('outline')
        ui.button('Interpret / refine selected batch',on_click=submission.once(lambda:run())).props('color=primary')
    def run():
        try:
            service.preview(session,int(batch.value),instruction.value or '')
            folder=forms.new_folder(root,'experimental_extract',session[:8])
            cmd=['experiments','extract',session,'--batch',str(batch.value),'--budget',str(s.budget),'--out',str(folder)]
            if instruction.value:
                cmd+=['--instruction',instruction.value]
            job=engine.launch(cmd,folder,'Interpret experimental source batch',confirmed_budget=s.budget,
                              approval=s.approval)
            submission.go('/live?path='+rel(root,job.folder))
        except (ValueError,OSError) as error:
            ui.notify(str(error))

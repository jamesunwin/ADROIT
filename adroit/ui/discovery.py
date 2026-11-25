"""The workbench's constraint discovery (the owner's request, 2026-10-18): the continuation offered on a personal
model, with one scoped consent, and a session's page with every candidate's stage and separate states.

The paid work runs as an ordinary command-line job (``adroit constraints discover``), never inside the model's
approval; reviewing, validating and binding a retrieved limit happen on the experimental library's existing pages.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from nicegui import ui

from adroit.ui import submission

SCOPE = ('What this does: reads the model\'s summary (its particles, couplings and engine; not its file or your '
         'notes), lists what the libraries already hold, searches arXiv by physics terms, asks the language model '
         'which published results bear on the model, retrieves absent papers (arXiv) and data tables (HEPData) that '
         'an existing adapter could compute, and drafts them for your review. Sent to the provider: that summary, the '
         'held records\' titles and identifiers, the abstracts and, for extraction, the retrieved pages and tables. '
         'Network: arXiv and HEPData only. Nothing is signed, validated, bound or applied without you.')
FIGURES = ('Read figures: where a spin-independent limit has no data table, also send the pages whose figure '
           'captions name it as page images (at most three per paper; Anthropic models; larger requests, each bound '
           'still reserved against the cap)')



def _checked_by(states: dict) -> str:
    """The model that checked the candidate's source in place of a person (PR-09: shown as such, bound or unbound), or
    "" for a person's review."""
    from adroit.core.pricing import model_name
    return model_name(states['review_by']) if states.get('review') == 'checked' and states.get('review_by') else ''

def command(reference: str, budget: float, model: str, out: Path, domain: list[str] | None = None,
            vision: bool = False) -> list[str]:
    """The command line a discovery launch runs."""
    if budget <= 0:
        raise ValueError('constraint discovery needs a budget')
    return (['constraints', 'discover', reference, '--budget', f'{budget:g}', '--model', model, '--out', str(out)]
            + [x for d in domain or [] for x in ('--domain', d)] + (['--vision'] if vision else []))


def launch(root: Path, reference: str, name: str, budget: float, model: str, vision: bool = False,
           approval: str = '') -> object:
    """Start a discovery job in a new run folder (``forms.new_folder``) with the confirmed budget (``approval``: how
    it was approved, ``forms.BudgetCheck.approval``)."""
    from adroit.ui import engine, forms
    folder = forms.new_folder(root, 'discovery', name)
    return engine.launch(command(reference, budget, model, folder, vision=vision), folder,
                         f'Find relevant limits: {name}', confirmed_budget=budget, approval=approval)


def sessions_for(reference: str) -> list[dict]:
    """Earlier discovery sessions of this model revision, newest first (``session_listing``)."""
    return session_listing(reference)[0]


def session_listing(reference: str):
    """(earlier discovery sessions of this model revision, newest first; each discovery session record that cannot
    be read, any of which may be this revision's, named with why: ``durable.read_each``; the consolidation plan's M3:
    they had been left out without a word)."""
    from adroit.core.durable import read_each
    from adroit.orchestrator.constraint_discovery import Discovery
    service = Discovery()
    folder = service.catalog.root / 'discovery'
    found, damaged = read_each(sorted(folder.glob('*/session.json')) if folder.is_dir() else [],
                               lambda path: service.session(path.parent.name))
    out = [{'session': s.session_id, 'created_at': s.created_at, 'state': service._read(s.session_id, 'state.json') or {}}
           for s in found if s.model_reference == reference]
    return sorted(out, key=lambda x: x['created_at'], reverse=True), damaged


def discovery_box(root: Path, reference: str, name: str) -> None:
    """On a model's page: earlier sessions and the scoped consent that starts a new one."""
    from adroit.ui.pages import budget_form, model_select, rel
    with ui.card().classes('w-full'):
        ui.label('Find relevant limits for this model').classes('text-lg font-bold')
        ui.label(SCOPE).classes('text-sm text-gray-600')
        rows, damaged = session_listing(reference)
        from adroit.ui.pages import _damaged
        _damaged(None, 'discovery session record(s), any of which may be this model\'s,', damaged,
                 'unreadable_sessions')
        for row in rows:
            done = [k for k, v in row['state'].items() if v.get('status') == 'done']
            ui.link(f"session {row['session'][:8]} ({row['created_at'][:16]}; {len(done)} of 7 stages done)",
                    '/constraints/discovery?' + urlencode({'session': row['session']}))
        model = model_select()
        figures = ui.checkbox(FIGURES).mark('figures')
        check = budget_form('the most this discovery may spend in all ($)', models=(model,))

        def go() -> None:
            verdict = check()
            if not verdict.ok:
                ui.notify(verdict.message)
                return
            try:
                job = launch(root, reference, name, verdict.amount, model.value, figures.value, verdict.approval)
            except (ValueError, OSError) as error:
                ui.notify(str(error))
                return
            submission.go(f'/live?path={rel(root, job.folder)}')

        ui.button('Find relevant limits', on_click=submission.once(go)).mark('discover')


def approval_option():
    """At a model's approval: the opt-in that starts discovery as its own job once the model is saved (its consent:
    the scope, the language model and a separate cap). Returns ``start(root, reference, name)``, which gives the job
    or None when not opted in."""
    from adroit.ui import forms
    from adroit.ui.pages import auto_tick, model_select
    with ui.expansion('Then find relevant limits for this model (optional, paid)').classes('w-full'):
        ui.label(SCOPE).classes('text-sm text-gray-600')
        wanted = ui.checkbox('Start constraint discovery after saving')
        model = model_select()
        figures = ui.checkbox(FIGURES)
        with ui.row().classes('items-center gap-3'):
            amount = ui.number('the most it may spend in all ($)', value=1.0, min=0.0, max=forms.CAP_USD, step=0.5)
            confirm = ui.checkbox('I approve this spend')
            how = auto_tick(confirm, (model,))

    def start(root: Path, reference: str, name: str):
        if not wanted.value:
            return None
        approval = how()             # first: a box the setting ticked, unticked if it no longer applies (PR-03)
        verdict = forms.check_budget(amount.value, confirm.value)
        if not verdict.ok:
            ui.notify(f'the model is saved; discovery did not start: {verdict.message}')
            return None
        return launch(root, reference, name, verdict.amount, model.value, figures.value, approval)
    return start


# A category in plain words (the owner's JU1, 2026-11-16: the page had shown the code's names, "needs_new_machinery")
CATEGORY = {'existing_applicable': "in ADROIT's records", 'existing_outside_domain': "in ADROIT's records, for part of "
            "the masses", 'existing_needs_review': 'a draft awaits your review', 'missing_supported': 'ADROIT can add it',
            'needs_new_machinery': 'not currently supported', 'uncertain': 'unclear whether it applies',
            'inapplicable': 'not applicable', 'superseded': 'superseded by a newer result'}


def guidance(c: dict) -> tuple[str, str]:
    """(what a found result means for the analysis, what to do next), in plain words, for a candidate as
    ``Discovery.show`` gives it (JU1)."""
    category, states, acquisition = c['category'], c['states'], c['acquisition']
    missing = f" ({c['missing']})" if c.get('missing') else ''
    fixed = {'existing_applicable': ("ADROIT already holds this limit.", "Nothing to do: Constrain a model uses it."),
             'existing_outside_domain': ("ADROIT holds this limit for only part of your model's masses.",
                                         "Nothing to do; outside its range it is named as not covered."),
             'existing_needs_review': ("A draft record of this limit is waiting for your review.",
                                       "Check it against the paper and verify it (below)."),
             'superseded': ("A newer result supersedes this one.", "Nothing to do: the newer result counts."),
             'inapplicable': ("It does not apply to this model.", "Nothing to do."),
             'needs_new_machinery': ("Not currently supported: ADROIT does not yet calculate this observable for your "
                                     f"model{missing}, so a record of the limit could not be used; it is not fetched.",
                                     "Nothing to do here: your analysis can proceed without it (it is named in the "
                                     "report). Or record that it does not apply, with your reason (below).")}
    if category in fixed:
        return fixed[category]
    if category == 'uncertain':
        return (f"ADROIT could not tell whether this result applies to your model, or what it limits{missing}.",
                "If it applies, fetch its paper and draft its record (below); if not, record why (below)."
                if c.get('includable') else "ADROIT has no calculation for its quantity yet, so a record of it could not "
                "be used; record why it does not apply, or leave it out of this study (below).")
    by=_checked_by(states)
    if states['selection'] == 'bound':
        return (f"Ready: its source was checked by {by}, not by a person; it is selected when you proceed." if by
                else "Verified and ready: it is selected when you proceed."), "Nothing to do."
    if states['review'] in ('signed','checked'):
        return ((f"Checked by {by}, not by a person; " if by else "Verified; ")
                + "it still needs validating and binding before a run can use it.",
                "Open its record to validate and bind it (below).")
    if c.get('draft') or acquisition['status'] == 'retrieved':
        return ("ADROIT fetched the paper and drafted this limit's record.",
                "Check every number against the paper and verify it, then validate and bind it (below).")
    if acquisition['status'] == 'retryable':
        return "Fetching the paper failed in transit.", "Fetch and draft again: resume the survey (below)."
    if acquisition['status'] == 'failed':
        return (f"The paper could not be fetched: {acquisition['reason']}.",
                "Add it yourself on Add a limit (upload the paper), or record why it does not apply (below).")
    return ("ADROIT can add this limit: its paper is to be fetched and its record drafted.",
            "Fetch and draft it: resume the survey (below)." + (f" ({acquisition['reason']})"
                                                                if acquisition.get('reason') else ''))


def session_page(root: Path, session: str) -> None:
    """One survey: what it found, in plain words, with what each means and what to do next; the actions (verify a
    draft, fetch and draft an unclear result, record a decision); fetching and drafting what remains; and proceeding
    to the analysis with the verified limits and the survey's assessment (the owner's JU1, 2026-11-16: the page had
    stopped at a table of needed limits)."""
    from adroit.orchestrator.constraint_discovery import Discovery
    from adroit.ui.pages import header
    service = Discovery()
    view = service.show(session)
    header('Constraint discovery: ' + view['domain']['name'],
           'ADROIT searched the published literature for limits that bear on this model. Each result it found is below, '
           'with what it means for your analysis and what to do next; then fetch and draft what remains, verify the '
           'drafts, and proceed. The search is bounded: a limit it did not find is not shown to be absent.')
    from adroit.orchestrator.accounting import session_money
    ui.label(f"Model {view['model']}; searched {view['searched_at'] or 'not yet'}").classes('text-sm')
    ui.label('Session spending: ' + session_money(service.budgets, session)).classes('text-sm').mark('session_money')
    with ui.row().classes('gap-3'):
        for name, row in view['state'].items():
            ui.badge(f"{name}: {row['status']}", color='green' if row['status'] == 'done' else 'orange')
    _overview(view)
    _actions(service, session, view)
    _fetch_panel(root, session, view)
    _proceed_panel(service, session, view)
    with ui.expansion('Gaps and decisions').classes('w-full').mark('gaps'):
        for gap in view['gaps'] or ['none recorded']:
            ui.label('• ' + gap).classes('text-sm')
        names = {c['candidate_id']: c['name'] for c in view['candidates']}
        for d in view['decisions']:
            ui.label(f"• {names.get(d['candidate_id'], d['candidate_id'])}: {DECIDED[d['kind']]} by {d['researcher']}"
                     f" ({d['at'][:10]}): {d['reason']}").classes('text-sm').mark('decision')


DECIDED = {'inapplicable': 'does not apply', 'omitted': 'left out of this study', 'superseded': 'superseded, confirmed',
           'included': 'included, to fetch and draft'}


def _overview(view: dict) -> None:
    """Every result found: its status, what it means and what to do, in a table that wraps."""
    columns = [{'name': k, 'label': label, 'field': k, 'align': 'left'}
               for k, label in (('result', 'result found'), ('status', 'status'), ('meaning', 'what it means'),
                                ('next', 'what to do'))]
    rows = []
    for c in view['candidates']:
        meaning, todo = guidance(c)
        rows.append({'result': f"{c['name']} ({c['reference']})", 'status': c['stage'],
                     'category': CATEGORY.get(c['category'], c['category']), 'stage': c['stage'],
                     'meaning': meaning, 'next': todo})
    ui.label('What ADROIT found').classes('text-lg font-medium mt-2')
    ui.table(columns=columns, rows=rows).classes('w-full').props('wrap-cells flat bordered').mark('candidates')


def _actions(service, session: str, view: dict):
    """Each result's actions: verify its draft; fetch and draft an unclear one ADROIT can calculate; record that one
    does not apply or is left out of this study. Returns the researcher's name field."""
    decided = {d['candidate_id'] for d in view['decisions'] if d['kind'] != 'included'}
    acting = [c for c in view['candidates'] if c['draft'] or c['acquisition']['revision']
              or c['category'] in ('uncertain', 'needs_new_machinery', 'missing_supported', 'existing_needs_review')]
    if not acting:
        return None
    ui.label('Your actions').classes('text-lg font-medium mt-2')
    researcher = ui.input('your name (recorded with each decision)').classes('w-80').mark('researcher')

    def act(do) -> None:
        if not (researcher.value or '').strip():
            ui.notify('give your name: it is recorded with the decision')
            return
        try:
            do()
        except ValueError as error:
            ui.notify(str(error))
            return
        ui.navigate.reload()
    for c in acting:
        with ui.card().classes('w-full gap-1').mark('action'):
            ui.label(c['name']).classes('font-medium')
            draft = c['draft'] or c['acquisition']['revision']
            if draft:
                ui.link(f"Review and verify the draft of {c['name']}", '/experiments/view?' + urlencode({'reference': draft}))
            if c.get('includable'):
                ui.button('It applies: fetch and draft its record', on_click=lambda c=c: act(lambda: service.include(
                    session, c['candidate_id'], 'judged by the researcher to apply to this model', researcher.value))) \
                    .props('outline').mark('include')
            if c['category'] in ('uncertain', 'needs_new_machinery', 'missing_supported') and \
                    c['candidate_id'] not in decided:
                with ui.expansion('It does not apply, or leave it out of this study').classes('w-full'):
                    reason = ui.input('why').classes('w-full')

                    def decide(kind, c=c, reason=reason) -> None:
                        if not (reason.value or '').strip():
                            raise ValueError('give the reason: it is recorded with the decision')
                        service.decide(session, c['candidate_id'], kind, reason.value, researcher.value)
                    with ui.row():
                        ui.button('It does not apply to this model', on_click=lambda d=decide: act(lambda: d('inapplicable'))) \
                            .props('flat').mark('inapplicable')
                        ui.button('Leave it out of this study', on_click=lambda d=decide: act(lambda: d('omitted'))) \
                            .props('flat').mark('omitted')
    return researcher


def _fetch_panel(root: Path, session: str, view: dict) -> None:
    """Fetch and draft what remains: resume the survey within its approved cap (the papers from arXiv and HEPData, the
    drafts by the experimental library's assisted extraction, which is paid)."""
    remaining = [c for c in view['candidates'] if c['category'] == 'missing_supported' and not c['draft']
                 and c['acquisition']['status'] not in ('retrieved', 'failed')]
    unfinished = [k for k, row in view['state'].items() if row.get('status') != 'done']
    if not remaining and not unfinished:
        return
    budget = view['budget']
    cap = budget.get('cap', 0.0)
    with ui.card().classes('w-full').mark('fetch_panel'):
        ui.label('Fetch and draft what remains').classes('text-lg font-medium')
        ui.label(f"{len(remaining)} result(s) ADROIT can add are not yet fetched or drafted"
                 + (f"; stages not finished: {', '.join(unfinished)}" if unfinished else '') +
                 ". Resuming fetches their papers (arXiv, HEPData) and drafts their records with the language model "
                 f"(paid), within this survey's approved ${cap:g} cap"
                 + (f" (${budget['remaining']:.4f} left)" if 'remaining' in budget else '') + '.').classes('text-sm')
        confirm = ui.checkbox(f"I approve resuming within this survey's ${cap:g} cap").mark('approve_resume')

        def resume() -> None:
            if not confirm.value:
                ui.notify('approve the resumption first')
                return
            from adroit.ui import engine, forms
            from adroit.ui.pages import rel
            folder = forms.new_folder(root, 'discovery', view['domain']['name'])
            try:
                job = engine.launch(['constraints', 'resume', session, '--budget', f'{cap:g}', '--out', str(folder)],
                                    folder, f"Fetch and draft limits: {view['domain']['name']}", confirmed_budget=cap)
            except (ValueError, OSError) as error:
                ui.notify(str(error))
                return
            submission.go(f'/live?path={rel(root, job.folder)}')
        ui.button('Fetch and draft (resume the survey)', on_click=submission.once(resume)).props('color=primary').mark('resume')


def _proceed_panel(service, session: str, view: dict) -> None:
    """Proceed to the analysis: Constrain a model on this model, with the survey's verified (bound) limits selected
    and its frozen assessment pinned, which keeps an allowed point pending while a limit found here is unresolved."""
    verified = list(dict.fromkeys(ref for c in view['candidates'] for ref in c['states'].get('bindings') or []
                                  if c['states'].get('selection') == 'bound'))
    open_ = [c['name'] for c in view['candidates'] if c['category'] in
             ('needs_new_machinery', 'uncertain', 'missing_supported', 'existing_needs_review')
             and c['states'].get('selection') != 'bound'
             and c['candidate_id'] not in {d['candidate_id'] for d in view['decisions'] if d['kind'] != 'included'}]
    with ui.card().classes('w-full').mark('proceed_panel'):
        ui.label('Proceed with your analysis').classes('text-lg font-medium')
        ui.label((f"{len(verified)} verified limit(s) from this survey will be selected. " if verified else
                  "No limit from this survey is verified yet: you can proceed now, or verify the drafts first. ")
                 + (f"Not resolved: {', '.join(open_)}. With the survey's assessment pinned (you can untick it on the "
                    "next page) these keep allowed points pending; they never exclude." if open_ else
                    "Every result found is resolved.")).classes('text-sm')

        def proceed() -> None:
            try:
                pin = service.coverage(session).reference
            except ValueError as error:          # an unfinished survey is not pinned: said, the analysis goes on
                pin = ''
                ui.notify(f'the survey is not finished, so its assessment is not pinned: {error}', multi_line=True)
            ui.navigate.to(proceed_target(view['model'], verified, pin, session))
        ui.button('Constrain this model', on_click=proceed).props('color=primary').mark('proceed')


def proceed_target(model: str, verified: list[str], pin: str, session: str = '') -> str:
    """Constrain a model's page for a survey's model, its verified limits selected and its assessment pinned: a
    library revision (``catalog:…``) loaded there; a model file the survey pinned by its hash taken from the survey's
    own record of it (``survey``: its session, whose typed model is checked against its integrity hash), never from
    the page's default. AL5-03 (the auditor's cycle 5): a file model's survey had led to the library tab, which launched the
    default library model without the survey's assessment."""
    query = {'catalog': model} if model.startswith('catalog:') else {'survey': session} if session else {}
    return '/new/track1?' + urlencode({**query, 'limits': ','.join(verified), 'discovery': pin})

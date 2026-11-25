"""Private experimental drafts and deterministic file ingestion (no API calls)."""
from pathlib import Path
import typer

from adroit.core.experimental_input import ExperimentalDossier
from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator.preflight import paid_command
from adroit.core.durable import write_atomic

app=typer.Typer(pretty_exceptions_show_locals=False, help='Private experimental source drafts; extraction is not activation.')

@app.command('profile-review')
def profile_review(limit:list[str]=typer.Option([],'--limit',help='a pinned private published limit (private-limit:SHA); repeatable'),
                   signal:str=typer.Option('','--signal',help='the signal search: a packaged search name or private-search:SHA'),
                   null:list[str]=typer.Option([],'--null',help='a null experiment: a packaged module name or private-search:SHA; repeatable')):
    """Display exact selection/replacements and its review hash. $0."""
    import json
    from adroit.library.experimental_profiles import review_selection
    try:
        typer.echo(json.dumps(review_selection(limit,signal,null),indent=2))
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('profile-create')
def profile_create(name:str,expected_hash:str=typer.Option(...,'--expected-hash',help='the review hash shown by '
                                                         'profile-review; a changed selection is refused'),
                   researcher:str=typer.Option(...,'--by',help='your name, recorded as the profile\'s reviewer'),
                   limit:list[str]=typer.Option([],'--limit',help='a pinned private published limit (private-limit:SHA); repeatable'),
                   signal:str=typer.Option('','--signal',help='the signal search: a packaged search name or private-search:SHA'),
                   null:list[str]=typer.Option([],'--null',help='a null experiment: a packaged module name or private-search:SHA; repeatable'),
                   parent:str=typer.Option('','--parent',help='the profile this one revises (profile:SHA)'),
                   confirmed:bool=typer.Option(False,'--confirmed',help='confirm that you reviewed these exact '
                                               'datasets, replacements and scopes (required)'),
                   independent:bool=typer.Option(False,'--independent',help='confirm that you checked the '
                                                 'selected datasets\' independence (required)')):
    """Save a reviewed selection as an immutable personal profile under your name; not activated. $0."""
    from adroit.library.experimental_profiles import create
    try:
        typer.echo(create(name,limit,signal,null,expected_hash,researcher,confirmed=confirmed,
                          independence_confirmed=independent,parent=parent).reference)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('profile-activate')
def profile_activate(reference:str,expected_current:str=typer.Option('','--expected-current',help='the active '
                         'profile as you last saw it (empty: the packaged defaults); a stale view is refused'),
                     confirmed:bool=typer.Option(False,'--confirmed',help='confirm the activation or rollback '
                                                 '(required)')):
    """Activate/roll back a pinned fresh-run profile; 'none' restores packaged defaults. $0."""
    from adroit.library.experimental_profiles import activate
    try:
        typer.echo(activate('' if reference=='none' else reference,expected_current,confirmed=confirmed))
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('validate-search')
def validate_search(reference:str,result:str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier'),
                    expected_hash:str=typer.Option(...,'--expected-hash',help='the scientific hash shown by experiments review'),
                    tolerance:float=typer.Option(...,'--tolerance',min=1e-12,max=.3,help='largest relative error '
                        'accepted in every anchor quantity (fitted count and log-likelihood: unit floor)')):
    """Check independently source-linked response/fit/interval anchors. $0."""
    from adroit.constraints.experimental_search_review import validate
    from adroit.statistics.optimum_interval import OptimumIntervalUnavailable
    try:
        value=validate(reference,result,tolerance,expected_hash)
        typer.echo(value.model_dump_json(indent=2))
        if not value.passed:
            raise typer.Exit(1)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None
    except OptimumIntervalUnavailable as error:     # an external tool's refusal: named, no receipt, exit 1 (DW-05)
        typer.echo(f'Not validated: {error}',err=True)
        raise typer.Exit(1) from None

@app.command('bind-search')
def bind_search(reference:str,result:str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier'),
                review:str=typer.Option(...,'--review',help='the source review ID (from verify-source)'),
                validation:str=typer.Option(...,'--validation',help='the passed validation ID (from '
                                            'validate-search)')):
    """Freeze a supported private event signal/null input; defaults unchanged. $0."""
    from adroit.constraints.experimental_search_review import bind
    try:
        typer.echo(bind(reference,result,review,validation).reference)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('review')
def review_source(reference: str,result: str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier'),
                  out: Path=typer.Option(...,'--out',help='folder for review.json (and a limit\'s comparison plots)'),
                  key: list[str]=typer.Option([],'--key',help='a claim key to review; repeatable (default: every '
                                              'claim of the result)')) -> None:
    """Prepare selected source/curve/assumption review, differences and plots. $0."""
    import json
    from adroit.constraints.experimental_review import packet,plot_packet
    from adroit.core.durable import publishing
    try:
        value=packet(reference,result,key or None)
        with publishing(out) as held:              # the packet and its review.json, one writer's (DH-01)
            from adroit.core.durable import not_a_study
            not_a_study(held.folder)                # never beside a saved study's own records (DJ-01)
            if {'limit_contract','validation_reference'}<=set(value['keys']):
                value['plots']=plot_packet(reference,result,out,claim=held)
            write_atomic(out/'review.json',json.dumps(value,indent=2))
        typer.echo(json.dumps(value,indent=2))
    except (ValueError,OSError,KeyError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('verify-source')
def verify_source(reference: str,result: str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier'),
                  expected_hash: str=typer.Option(...,'--expected-hash',help='the scientific hash shown by experiments review'),
                  researcher: str=typer.Option(...,'--by',help='your name, signed into the review'),
                  confirmed: bool=typer.Option(False,'--confirmed',help='attest that you compared these claims '
                                               'with the source (required)'),
                  checked: list[str]=typer.Option([],'--checked',help='a completed check; repeat for all six: '
                      'source_values, source_units_axes, confidence_construction, benchmark_assumptions, '
                      'dataset_overlap, digitisation_uncertainty'),
                  key: list[str]=typer.Option([],'--key',help='a claim key, as in the reviewed packet; repeatable '
                                              '(default: every claim)')) -> None:
    """Record the researcher's scoped source assertion; never validate an adapter. $0."""
    from adroit.constraints.experimental_review import approve
    try:
        typer.echo(approve(reference,result,expected_hash,researcher,confirmed=confirmed,checks=checked,keys=key or None).model_dump_json(indent=2))
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('validate-limit')
def validate_limit(reference: str,result: str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier'),
                   tolerance: float=typer.Option(...,'--tolerance',min=1e-12,max=.3,help='largest relative error '
                                                 '|interpolated/source − 1| accepted at each anchor'),
                   expected_hash: str=typer.Option(...,'--expected-hash',help='the scientific hash shown by experiments review')) -> None:
    """Check source anchors at a declared tolerance: separate sources, or, for a curve digitised from a figure,
    quotations of the same paper's text (each anchor with evidence of its own). $0."""
    from adroit.constraints.experimental_review import validate
    try:
        receipt=validate(reference,result,tolerance,expected_hash)
        typer.echo(receipt.model_dump_json(indent=2))
        if not receipt.passed:
            raise typer.Exit(1)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('verify-figure')
def verify_figure(reference: str,result: str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier'),
                  tolerance: float=typer.Option(...,'--tolerance',min=1e-12,max=.3,help='largest relative error '
                                                '|interpolated/printed − 1| accepted at each printed anchor'),
                  expected_hash: str=typer.Option(...,'--expected-hash',help='the scientific hash shown by experiments review'),
                  researcher: str=typer.Option(...,'--by',help='your name, signed into the verification'),
                  low: float=typer.Option(...,'--from',help='the declared mass range\'s lower end you reviewed (GeV)'),
                  high: float=typer.Option(...,'--to',help='the declared mass range\'s upper end you reviewed (GeV)'),
                  confirmed: bool=typer.Option(False,'--confirmed',help='attest that you compared the calibrated '
                                               'overlay with the figure over the whole range (required)'),
                  checked: list[str]=typer.Option([],'--checked',help='a completed check; repeat for all five: '
                      'calibrated_overlay_inspected, full_mass_range_reviewed, printed_anchors_checked, '
                      'axes_units_and_scales, same_result_as_anchors'),
                  packet: Path=typer.Option(...,'--packet',help='the review packet you inspected: the folder '
                                            'experiments review wrote (--out)')) -> None:
    """Verify by hand an SI curve digitised from a figure with one or two printed anchors (the overlay from
    experiments review); recorded as manually verified with limited anchors, not as the ordinary validation. $0."""
    from adroit.constraints.experimental_review import verify_figure as verify
    try:
        receipt=verify(reference,result,tolerance,expected_hash,researcher,confirmed=confirmed,checks=checked,
                       reviewed_range=(low,high),packet=packet)
        typer.echo(receipt.model_dump_json(indent=2))
        if not receipt.passed:
            raise typer.Exit(1)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('renew-figure')
def renew_figure(validation: str) -> None:
    """Renew a manual figure verification under the current code: its anchors checked again, the signature carried
    over; refused if the verified source changed. $0."""
    from adroit.constraints.experimental_review import renew_figure as renew
    try:
        receipt=renew(validation)
        typer.echo(receipt.model_dump_json(indent=2))
        if not receipt.passed:
            raise typer.Exit(1)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('bind-limit')
def bind_limit(reference: str,result: str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier'),
               review: str=typer.Option(...,'--review',help='the source review ID (from verify-source)'),
               validation: str=typer.Option(...,'--validation',help='the passed validation ID (from '
                                            'validate-limit)')) -> None:
    """Create a pinned reviewed/validated selection; default studies stay unchanged. $0."""
    from adroit.constraints.experimental_review import bind
    try:
        typer.echo(bind(reference,result,review,validation).reference)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('start')
@paid_command
def start_extraction(reference: str,budget: float=typer.Option(...,'--budget',min=0,max=10,help='the session\'s '
                         'total hard cap in dollars (at most 10), repeated by its paid extract steps'),
                     model: str=typer.Option('claude-opus-5-5','--model',help='the interpreting language model '
                                             '(page images need claude-…)'),
                     text_only: bool=typer.Option(False,'--text-only',help='send PDF pages with extracted text '
                                                  'without their images; scans and image files still go as images')) -> None:
    """Fix total budget/source scope without making a provider call. $0."""
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    try:
        typer.echo(ExperimentalExtraction().start(reference,budget,model,not text_only).model_dump_json(indent=2))
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('preview')
def preview_extraction(session: str,batch: int=typer.Option(0,'--batch',min=0,help='the source batch (0-based; '
                                                              'the preview reports batch_count)'),
                       instruction: str=typer.Option('','--instruction',help='the refinement instruction the '
                                                     'request would carry')) -> None:
    """Show coverage/request bound and remaining budget. $0."""
    import json
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    try:
        typer.echo(json.dumps(ExperimentalExtraction().preview(session,batch,instruction),indent=2))
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('raise-cap')
def raise_cap(session: str,budget: float=typer.Option(...,'--budget',min=0,max=10,help='the new session cap (dollars)'),
              confirmed: bool=typer.Option(False,'--confirmed',help='confirm the increase (required)'),
              reason: str=typer.Option('','--reason',help='why the cap is raised; kept in the session and its '
                                       'paid ledger')) -> None:
    """Raise an extraction session's cap, with your confirmation; the change is recorded. $0."""
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    from adroit.orchestrator.preflight import raise_cap_command
    raise_cap_command(ExperimentalExtraction().budgets,session,budget,confirmed,reason)

@app.command('extract')
def extract_sources(session: str,budget: float=typer.Option(...,'--budget',min=0,max=10,help='dollars: the '
                                                                'session\'s cap as started or last raised'),
                    batch: int=typer.Option(0,'--batch',min=0,help='the source batch to interpret (0-based; see '
                                            'preview)'),
                    instruction: str=typer.Option('','--instruction',help='a refinement instruction; needed to '
                                                  're-read a batch already interpreted'),
                    trim: bool=typer.Option(False,'--trim',help='send the compacted prior dossier (no excerpts or notes)'),
                    out: Path | None=typer.Option(None,'--out',help='folder for extraction.json and report.md '
                                                  '(optional)')) -> None:
    """Interpret or refine one bounded source batch; paid: calls a language model behind the budget gate.

    The next request's reservation is shown first; a cap that cannot cover it stops before dispatch, with options."""
    from adroit.core.receipts import BUDGET_STOPPED
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    from adroit.orchestrator.preflight import record_requests,session_export
    files=('extraction.json','report.md')                           # its export, beside its request record (DK-01)
    service=ExperimentalExtraction()
    owner=session                                                   # the session whose ledger holds the requests
    try:
        from adroit.core.durable import not_a_study
        not_a_study(out)                                            # before anything is spent (DJ-01)
        owner=service.budget_owner(session)
        s=service.budgets.session(owner)                            # a discovery session's one cap, if shared
        if s.budget!=budget:
            raise ValueError('supply the originally approved session budget (or the cap as last raised)')
        from adroit.agents.llm import preflight
        from adroit.orchestrator.preflight import cap_options,show,start_line
        show(start_line(s.model,s.budget))
        plan=service.preview(session,batch,instruction)
        status=plan['budget']
        reserved=plan['trimmed_request_bound_usd' if trim else 'request_bound_usd']
        committed=status['spent']+status['reserved_uncertain']
        show(f"next request: reserves up to ${plan['request_bound_usd']:.4f} (${plan['trimmed_request_bound_usd']:.4f} with "
             f"--trim){'; sending the compacted prior' if trim else ''}; ${status['remaining']:.4f} of the ${s.budget:.2f} cap remains")
        if committed+reserved>s.budget:
            typer.echo('\n'.join(cap_options('experiments',session,reserved,committed,s.budget,
                                              None if trim or not service.steps(session) else plan['trimmed_request_bound_usd'])))
            record_requests(out,service.budgets,owner,files)        # nothing sent: only in its own job's folder
            raise typer.Exit(BUDGET_STOPPED)
        with preflight(show):
            step=service.step(session,batch,instruction,trimmed=trim)
        if out:                                 # with its request record, under one hold of the folder (DJ-01, DK-01)
            from adroit.evidence.version import as_found
            session_export(out,service.budgets,owner,{'extraction.json':step.model_dump_json(indent=2),'report.md':f'# Experimental interpretation\n\nCreated (UTC): {step.created_at}\n\n'+step.explanation+
                '\n\nRevision: '+step.output_revision+'\n\nNo source verification, activation or physics calculation performed.\n'
                +as_found(f'It is the session {session} as it was read when this report was written; what is used later '
                          f'is its revision, {step.output_revision}, by that name.')})
        typer.echo(step.model_dump_json(indent=2))
        from adroit.orchestrator.accounting import status_text
        status=service.budgets.budget_status(owner)               # the budget's owner's, not a linked session's (CA-04)
        typer.echo(str(status))
        typer.echo('session spending'+(f' (discovery session {owner}, whose budget this session shares)'
                                       if owner!=session else '')+': '+status_text(status))
    except typer.Exit:
        raise
    except Exception as error:
        record_requests(out,service.budgets,owner,files)            # only if it sent a request, or the folder is its own
        from adroit.orchestrator.stops import stop
        message,code=stop(error,'Extraction','Drafts and paid receipts remain stored.')
        typer.echo(message)
        raise typer.Exit(code) from None

@app.command('check')
def check_record(session: str,budget: float=typer.Option(...,'--budget',min=0,max=10,help='dollars: the check '
                                                           'session\'s cap as started'),
                 out: Path | None=typer.Option(None,'--out',help='folder for record_check.json and report.md '
                                               '(optional)')) -> None:
    """Check a user-added record with a language model in place of a person's review, as its session asks
    (``orchestrator.record_check``); paid: every request is reserved against the session's cap first.

    A passed check signs the result's review as the model's; a failed one is re-read by the record assistant and
    checked again (at most twice), then comes back to you with each mismatch."""
    from adroit.orchestrator.preflight import record_requests,session_export,show,start_line
    from adroit.orchestrator.record_check import RecordChecker
    files=('record_check.json','report.md')
    service=RecordChecker()
    try:
        from adroit.core.durable import not_a_study
        not_a_study(out)                                            # before anything is spent (DJ-01)
        s=service.budgets.session(session)
        if s.budget!=budget:
            raise ValueError('supply the originally approved session budget (or the cap as last raised)')
        from adroit.agents.llm import preflight
        show(start_line(s.model,s.budget))
        with preflight(show):
            outcome=service.run(session)
        session_export(out,service.budgets,session,{'record_check.json':outcome.model_dump_json(indent=2),
                                                    'report.md':_check_report(service,outcome)})
        typer.echo(outcome.model_dump_json(indent=2))
        from adroit.orchestrator.accounting import status_text
        typer.echo('session spending: '+status_text(service.budgets.budget_status(session)))
        if outcome.status=='stopped':
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as error:
        record_requests(out,service.budgets,session,files)
        from adroit.orchestrator.stops import stop
        message,code=stop(error,'Record check','Checks and revisions made so far remain stored.')
        typer.echo(message)
        raise typer.Exit(code) from None

def _check_report(service,outcome) -> str:
    """The record check's report (report.md): its outcome, each mismatch and note, and its checks."""
    from adroit.core.pricing import model_name
    run=service.request(outcome.session_id)
    head={'approved':f'Approved by {model_name(run.model)}: a model check, not a person\'s review '
                     f'(review {outcome.review_id}).',
          'needs_you':'Back to you: the check and the record assistant did not agree. Approve the record yourself, '
                      'or suggest another route.',
          'stopped':'Stopped before an outcome: '+outcome.why}[outcome.status]
    lines=['# Record check','',head,'',f'Result {outcome.result_id}; revisions {", ".join(outcome.revisions)}.','']
    lines+=(['## Mismatches',''] + [f'- {m}' for m in outcome.mismatches] + [''] if outcome.mismatches else [])
    lines+=(['## Notes',''] + [f'- {n}' for n in outcome.notes] + [''] if outcome.notes else [])
    lines+=['## Checks','']+[f'- {c}' for c in outcome.checks]
    return '\n'.join(lines)+'\n'

@app.command('interpretation')
def show_interpretation(reference: str,result: str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier')) -> None:
    """Explain classification, assumptions and calculation blockers, and what confirmation must accept. $0."""
    import json
    from adroit.orchestrator.anomaly_intake import acknowledgements,interpretation
    try:
        typer.echo(json.dumps({**interpretation(reference,result).model_dump(mode='json'),
                               'required_acknowledgements':acknowledgements(reference,result)},indent=2))
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('confirm')
def confirm_interpretation(reference: str,result: str=typer.Option(...,'--result',help='the result\'s ID in the revision\'s dossier'),
                           expected_hash: str=typer.Option(...,'--expected-hash',help='the interpretation hash '
                                                           'shown by experiments interpretation'),
                           researcher: str=typer.Option(...,'--by',help='your name, recorded with the confirmation'),
                           confirmed: bool=typer.Option(False,'--confirmed',help='confirm that you understood the '
                                                        'interpretation (required)'),
                           accept: list[str]=typer.Option([],'--accept-assumption',help="one per required acknowledgement, exactly as `interpretation` shows it (an assumed value as 'key=value units')")) -> None:
    """Confirm understanding; source review and activation stay pending. $0."""
    from adroit.orchestrator.anomaly_intake import confirm
    try:
        typer.echo(confirm(reference,result,expected_hash,researcher,confirmed=confirmed,accepted_assumptions=accept).reference)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None


@app.command('import')
def import_files(files: list[Path]=typer.Argument(...),
                 title: str=typer.Option(...,'--title',help='the dossier\'s title, e.g. \'My experiment, run 2\''),
                 parent: str=typer.Option('','--parent',help='a revision (experimental:ID@REVISION) this import '
                                          'adds to; its sources carry over'),
                 pages: str=typer.Option('1','--preview-pages',help='PDF pages to render as preview images '
                                         '(1-based), comma-separated'),
                 dossier: Path | None=typer.Option(None,'--dossier',help='a typed dossier (JSON) to store '
                                                   '(default: the parent\'s, or an empty one)'),
                 out: Path | None=typer.Option(None,'--out',help='a new or empty folder for experimental.json '
                                               'and report.md'),
                 source_name: list[str]=typer.Option([],'--source-name',help='a display name per file, in order '
                                                     '(same suffix); repeat once for every file')) -> None:
    """Import PDFs/supplements/tables; create an immutable inactive revision. $0."""
    try:
        selected=[int(n) for n in pages.split(',') if n.strip()]
        content=ExperimentalDossier.model_validate_json(dossier.read_text()) if dossier else None
        from adroit.orchestrator.runs import fresh
        if out and not fresh(out):                  # a workbench job's own record and log aside
            raise ValueError('output directory must be new or empty')
        catalog=ExperimentalCatalog()
        r=catalog.import_files(files,title,parent=parent,preview_pages=selected,dossier=content,names=source_name)
        if out:                                 # both whole, under one hold of the folder (DJ-01), still new once held
            from adroit.core.durable import export  # (DM-02's class: another import there meanwhile had been replaced)
            from adroit.evidence.version import as_found
            export(out,{'experimental.json':r.model_dump_json(indent=2),'report.md':catalog.report(r.reference)+as_found(
                f'It is the experimental revision {r.reference} as it was read when this report was written.')},
                fresh=fresh)
        typer.echo(r.reference)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None


@app.command('list')
def list_revisions(query: str=typer.Option('','--query',help='case-insensitive text matched in titles and '
                                           'analysis descriptions')) -> None:
    """Search titles/analyses, retaining every old revision. $0."""
    found,damaged=ExperimentalCatalog().listing(query)
    for r in found:
        typer.echo(f'{r.reference}  {r.created_at.isoformat()}  {r.dossier.title}  inactive/unreviewed')
    for d in damaged:                                  # named, the rest listed (CA-07)
        typer.echo(f'unreadable, not listed: {d.path} ({d.why})')


@app.command('show')
def show(reference: str) -> None:
    """Show the exact dossier, creation date and source identifiers. $0."""
    try:
        typer.echo(ExperimentalCatalog().load(reference).model_dump_json(indent=2))
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None


@app.command('source')
def source(reference: str,index: int=typer.Option(0,'--index',min=0,help='the ingested source to show '
                                                   '(0-based, in import order)')) -> None:
    """Show parsed source pages/rows; no implicit event/limit interpretation. $0."""
    try:
        catalog=ExperimentalCatalog()
        r=catalog.load(reference)
        typer.echo(catalog.ingestion(r.ingestions[index]).model_dump_json(indent=2))
    except (ValueError,OSError,IndexError) as error:
        raise typer.BadParameter(str(error)) from None


@app.command('report')
def report(reference: str) -> None:
    """Show the dated extraction/completeness report. $0."""
    try:
        typer.echo(ExperimentalCatalog().report(reference))
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None


@app.command('revise')
def revise(reference: str,dossier: Path=typer.Option(...,'--dossier',help='the edited dossier '
                                                     '(ExperimentalDossier JSON)')) -> None:
    """Save edited dossier content as a linked unreviewed revision. $0."""
    try:
        catalog=ExperimentalCatalog()
        prior=catalog.load(reference)
        content=ExperimentalDossier.model_validate_json(dossier.read_text())
        typer.echo(catalog.save(content,prior.sources,prior.ingestions,parent=reference).reference)
    except (ValueError,OSError) as error:
        raise typer.BadParameter(str(error)) from None

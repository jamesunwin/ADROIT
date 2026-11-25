"""Local model catalog and reviewed model-intake commands."""
from pathlib import Path
import json
import typer

from adroit.library.personal import Catalog
from adroit.orchestrator.model_intake import Intake
from adroit.orchestrator.preflight import paid_command,record_requests,session_export

DRAFT_FILES=('intake.json','report.md')      # an intake command's export, beside its request record (DK-01)

app=typer.Typer(pretty_exceptions_show_locals=False, help='Private versioned models and reviewed intake; no implicit physics run.')

def approval_lines(session:str,draft)->list[str]:
    """Each candidate's model identity, which `approve --expected-hash` needs, and the command that approves it
    once a person has reviewed it (live check L3)."""
    from adroit.orchestrator.model_approval import model_identity
    lines=[]
    for index,choice in enumerate(draft.choices):
        identity=model_identity(choice.spec)
        lines+=[f'Candidate {index}: {choice.spec.name}',f'  model identity: {identity}',
                f'  after review: adroit models approve {session} {draft.step_id} --candidate {index} '
                f'--expected-hash {identity} --confirmed']
    return lines


def _draft_report(title:str,session:str,draft)->str:
    return (f'# {title}\n\nDraft created (UTC): {draft.created}\n\nNo physics calculation performed.\n\n'
            f'Session: {session}\n\nStep: {draft.step_id}\n\n'+'\n'.join(approval_lines(session,draft))+
            f'\n\nReview at /models/intake?session={session}&step={draft.step_id}\n'+_as_found(session,draft))


def _as_found(session:str,draft)->str:
    """The draft report's statement of what it was made of, read as found (``evidence.version.as_found``)."""
    from adroit.evidence.version import as_found
    return as_found(f'It is the draft {draft.step_id} as the intake session {session} held it when this report was '
                    'written; the session can advance since, and its approval names the step it approves.')



def _money(service,session):
    """A session command's closing lines: its budget status as JSON (what a log reader parses) and in words
    (``accounting.status_text``, the pages' wording)."""
    from adroit.orchestrator.accounting import status_text
    status=service.budget_status(session)
    typer.echo(json.dumps(status))
    typer.echo('session spending: '+status_text(status))

@app.command('list')
def list_models(query:str=typer.Option('','--query',help='case-insensitive text matched in the name, TeX and source')):
    """Every catalog revision: its pinned reference, name, creation date (UTC) and numerical applicability. $0."""
    found,damaged=Catalog().listing(query)
    for r in found:
        typer.echo(f'{r.reference}  {r.spec.name}  {r.created}  {r.applicability}')
    for d in damaged:                                  # named, the rest listed (CA-07)
        typer.echo(f'unreadable, not listed: {d.path} ({d.why})')

@app.command('show')
def show(reference:str):
    """One catalog revision in full (JSON), by its pinned reference catalog:MODEL@REVISION. $0."""
    try:
        r=Catalog().load(reference)
    except (ValueError,OSError) as e:
        raise typer.BadParameter(str(e)) from None
    typer.echo(r.model_dump_json(indent=2))

@app.command('import')
def import_model(path:Path,parent:str=typer.Option('','--parent',help='the catalog revision this one revises '
                                                  '(catalog:MODEL@REVISION); the new revision joins its model'),
                 source:list[Path]=typer.Option([],'--source',help='an original source file kept with the revision '
                                                '(TeX, text, YAML, image or PDF; at most 25 MB); repeatable')):
    """Save a typed model (YAML) as a new catalog revision, after its structural audit. $0.

    A supplied Lagrangian is kept exactly, with its derivation if the file has one."""
    import yaml
    from adroit.orchestrator.model_approval import read_model,select_model
    from adroit.orchestrator.ideas import from_lagrangian
    from adroit.library.interactions.derivation import Derivation
    from adroit.model_building.tex import render
    try:
        data=yaml.safe_load(path.read_text())
        spec=read_model(data)
        spec,approval=select_model(from_lagrangian(spec))
        catalog=Catalog()
        assets=[catalog.asset(path),*[catalog.asset(p) for p in source]]
        d=Derivation.model_validate(data['derivation']) if 'derivation' in data else None
        r=catalog.save(spec,approval,parent=parent,tex=render(spec),sources=assets,derivation=d,
                       provenance={'origin':'explicit typed model import'})
    except (ValueError,OSError) as e:
        raise typer.BadParameter(str(e)) from None
    typer.echo(r.reference)

@app.command('export')
def export(reference:str,out:Path=typer.Option(...,'--out',help='the YAML file to write; never overwritten')):
    """Write a catalog revision as a portable typed model (YAML) with its approval and provenance. $0."""
    try:
        Catalog().export_model(reference,out)
    except (ValueError,OSError) as e:
        raise typer.BadParameter(str(e)) from None
    typer.echo(str(out))

@app.command('start')
@paid_command
def start(budget:float=typer.Option(0.,'--budget',min=0,max=10,help='the session\'s total hard cap in dollars '
                                    '(at most 10); 0 allows only the free typed and fields steps'),
          parent:str=typer.Option('','--parent',help='a catalog revision (catalog:MODEL@REVISION) to refine; '
                                  'it becomes the session\'s first draft'),
          model:str=typer.Option('claude-opus-5-5','--model',help='the language model for the session\'s paid '
                                 'steps (claude-… or gpt-…; screenshots and papers need claude-…)')):
    """Open a model-intake session with its total budget fixed up front; no model call is made. $0."""
    try:
        s=Intake().start(budget,model,parent)
    except (ValueError,OSError) as e:
        raise typer.BadParameter(str(e)) from None
    typer.echo(s.model_dump_json())

@app.command('raise-cap')
def raise_cap(session:str,budget:float=typer.Option(...,'--budget',min=0,max=10,help='the new session cap (dollars)'),
              confirmed:bool=typer.Option(False,'--confirmed',help='confirm the increase (required)'),
              reason:str=typer.Option('','--reason',help='why the cap is raised; kept in the session and its '
                                      'paid ledger')):
    """Raise an intake session's cap, with your confirmation; the change is recorded. $0."""
    from adroit.orchestrator.preflight import raise_cap_command
    raise_cap_command(Intake(),session,budget,confirmed,reason)

@app.command('step')
def step(session:str,kind:str=typer.Option(...,'--kind',help='idea, tex, image or refine (paid); fields or '
                                           'typed (a YAML model; $0)'),
         text:str=typer.Option('','--text',help='the input itself: an idea, TeX, YAML or refinement '
                               'instructions (default: the text of --source)'),
         source:Path|None=typer.Option(None,'--source',help='a source file (TeX, text, YAML, or a PNG/JPEG/WebP '
                                       'screenshot for --kind image), kept as a catalog asset'),
         parent_step:str=typer.Option('','--parent-step',help='the draft step this one refines (its step ID); '
                                      'its sources carry over'),
         candidate:int=typer.Option(0,'--candidate',min=0,help='the candidate of --parent-step to refine '
                                    '(0-based)'),
         models:int=typer.Option(2,'--models',min=1,max=6,help='with --kind idea and no --parent-step: how '
                                 'many models the builder proposes'),
         source_name:str=typer.Option('','--source-name',help='the name recorded for --source (default: its '
                                      'file name)'),
         budget:float=typer.Option(0.,'--budget',min=0,max=10,help='dollars: for a paid kind, the session\'s '
                                   'cap as started or last raised'),
         out:Path|None=typer.Option(None,'--out',help='folder for intake.json and report.md (optional)')):
    """A draft model from an idea, TeX, a screenshot, field content or typed YAML; paid except fields and typed.

    idea, tex, image and refine are paid: calls a language model behind the session's budget gate; fields and typed are $0.

    Prints each candidate's model identity and the command that approves it."""
    service=Intake()
    try:
        from adroit.core.durable import not_a_study
        not_a_study(out)                        # before anything is spent (DJ-01)
        s=service.session(session)
        if kind not in ('typed','fields') and budget!=s.budget:
            raise ValueError('paid commands must supply the originally approved session --budget')
        from adroit.agents.llm import preflight
        from adroit.orchestrator.preflight import show,start_line
        if kind not in ('typed','fields'):
            show(start_line(s.model,s.budget))
        with preflight(show):
            draft=service.step(session,kind,text,parent_step=parent_step,candidate=candidate,source=source,models=models,source_name=source_name)
        session_export(out,service,session,{'intake.json':draft.model_dump_json(indent=2),   # with its request record,
                                            'report.md':_draft_report('Model intake draft',session,draft)})  # one hold
        typer.echo(draft.model_dump_json(indent=2))
        typer.echo('\n'.join(approval_lines(session,draft)))
        _money(service,session)
    except Exception as error:
        record_requests(out,service,session,DRAFT_FILES)           # only if it sent a request, or the folder is its own
        from adroit.orchestrator.stops import stop
        message,code=stop(error,'Intake','Existing drafts and budget receipts are retained.')
        typer.echo(message)
        from adroit.agents.budget import BudgetExceeded
        if isinstance(error,BudgetExceeded) and error.budget is not None and error.required is not None:
            from adroit.orchestrator.preflight import cap_options
            typer.echo('\n'.join(cap_options('models',session,error.required,error.spent,error.budget)))
        raise typer.Exit(code) from None

@app.command('draft')
def show_draft(session:str,step:str):
    """A saved intake draft (JSON) and, for each candidate, its model identity and approval command. $0."""
    draft=Intake().load(session,step)
    typer.echo(draft.model_dump_json(indent=2))
    typer.echo('\n'.join(approval_lines(session,draft)))

@app.command('approve')
def approve(session:str,step:str,candidate:int=typer.Option(0,'--candidate',min=0,help='the candidate to '
                                                           'approve (0-based, as draft lists them)'),
            expected_hash:str=typer.Option(...,'--expected-hash',help='the candidate\'s model identity '
                                           '(SHA-256) shown by draft; a changed model is refused'),
            confirmed:bool=typer.Option(False,'--confirmed',help='confirm that you reviewed the transcription, '
                                        'assumptions and canonical model (required)'),
            styles:Path|None=typer.Option(None,'--styles',help='reviewed StyleDeclaration JSON list')):
    """Save a reviewed draft candidate as a new immutable catalog revision (your explicit approval). $0."""
    service=Intake()
    draft=service.load(session,step)
    from adroit.core.model_preferences import StyleDeclaration
    try:
        declarations=[StyleDeclaration.model_validate(d) for d in json.loads(styles.read_text())] if styles else None
        r=service.approve(session,step,candidate,confirmed=confirmed,expected_model_hash=expected_hash,tex=draft.choices[candidate].tex,
                          style_declarations=declarations)
    except (ValueError,OSError,IndexError) as e:
        raise typer.BadParameter(str(e)) from None
    typer.echo(r.reference)

@app.command('paper')
def paper(session:str,equation:str=typer.Option(...,'--equation',help='the equation\'s label as printed, '
                                                 'e.g. 3.1'),
          pages:str=typer.Option(...,'--pages',help='one to four physical PDF pages (1-based), '
                                 'comma-separated, e.g. 2,3'),
          pdf:Path|None=typer.Option(None,'--pdf',help='the paper as a local PDF (or --arxiv)'),
          arxiv:str=typer.Option('','--arxiv',help='a modern arXiv identifier, optionally versioned '
                                 '(e.g. 2101.01234v2); the PDF is fetched and pinned by its SHA-256'),
          text:str=typer.Option('','--text',help='further instructions for the interpreter'),
          budget:float=typer.Option(...,'--budget',min=0,max=10,help='dollars: the session\'s cap as started '
                                    'or last raised'),
          out:Path|None=typer.Option(None,'--out',help='folder for intake.json and report.md (optional)')):
    """A draft model from one equation on selected pages of a paper (PDF or arXiv); paid.

    Paid: calls a language model (Anthropic vision) behind the session's budget gate.

    The source equation is kept beside the model's TeX; approve the draft with models approve."""
    service=Intake()
    try:
        from adroit.core.durable import not_a_study
        not_a_study(out)                        # before anything is spent (DJ-01)
        s=service.session(session)
        if s.budget!=budget:
            raise ValueError('supply the originally approved session --budget')
        from adroit.agents.llm import preflight
        from adroit.orchestrator.paper_model import step
        from adroit.orchestrator.preflight import show,start_line
        show(start_line(s.model,s.budget))
        with preflight(show):
            draft=step(service,session,pdf=pdf,arxiv=arxiv,pages=[int(p.strip()) for p in pages.split(',')],equation=equation,instructions=text)
        session_export(out,service,session,{'intake.json':draft.model_dump_json(indent=2),   # with its request record,
                                            'report.md':_draft_report('Paper equation model draft',session,draft)})
        typer.echo(draft.model_dump_json(indent=2))
        typer.echo('\n'.join(approval_lines(session,draft)))
        _money(service,session)
    except Exception as error:
        record_requests(out,service,session,DRAFT_FILES)           # only if it sent a request, or the folder is its own
        from adroit.orchestrator.stops import stop
        message,code=stop(error,'Paper intake','Existing drafts and paid receipts are retained.')
        typer.echo(message)
        raise typer.Exit(code) from None

"""Free immutable reanalysis commands; scientific review precedes execution."""
import json
from pathlib import Path
import typer
from adroit.orchestrator.reanalysis import Reanalysis

app=typer.Typer(pretty_exceptions_show_locals=False, help='Reopen saved inputs, review changes and run a fresh child analysis.')

@app.command('open')
def open_saved(source:str,target:str=typer.Option('','--target',help='track1, signal or single_idea (default: '
                                                  'the source\'s own workflow)'),
               model_index:int=typer.Option(0,'--model-index',min=0,help='the saved physical model to carry '
                                            'into the other track (0-based)'))->None:
    """Open saved inputs as a pinned editable reanalysis draft. $0."""
    try:
        typer.echo(Reanalysis().open(source,target,model_index).model_dump_json(indent=2))
    except (ValueError,OSError,KeyError,RuntimeError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('edit')
def edit(reference:str,request:Path=typer.Option(...,'--request',help='YAML: the edited request, based on the '
                                                 'draft\'s returned request object'))->None:
    """Save a validated request file as a new immutable draft. $0."""
    import yaml
    try:
        if request.is_symlink() or not request.is_file() or request.name.startswith('.env'):
            raise ValueError('select a regular non-credential request file')
        typer.echo(Reanalysis().revise(reference,yaml.safe_load(request.read_text())).model_dump_json(indent=2))
    except (ValueError,OSError,KeyError,TypeError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('model')
def select_model(reference:str,model:str=typer.Option(...,'--model',help='an approved catalog revision '
                                                     '(catalog:MODEL@REVISION)'),
                 index:int=typer.Option(0,'--index',min=0,help='the Track 2 model slot to replace (0-based)'))->None:
    """Select a pinned personal model revision for one draft slot. $0."""
    try:
        typer.echo(Reanalysis().choose_model(reference,model,index).model_dump_json(indent=2))
    except (ValueError,OSError,KeyError,RuntimeError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('review')
def review(reference:str)->None:
    """Display changes, applicability blockers and the required review hash. $0."""
    try:
        typer.echo(json.dumps(Reanalysis().preview(reference),indent=2))
    except (ValueError,OSError,KeyError,RuntimeError) as error:
        raise typer.BadParameter(str(error)) from None

@app.command('run')
def run(reference:str,out:Path=typer.Option(...,'--out',help='a fresh empty child folder (for a saved study, '
                                           'inside its folder)'),
        expected_hash:str=typer.Option(...,'--expected-hash',help='the review hash shown by reanalyse review'),
        reviewer:str=typer.Option(...,'--by',help='your name, recorded as the reviewer'),
        confirmed:bool=typer.Option(False,'--confirmed',help='confirm that you reviewed the changes (required)'))->None:
    """Run an explicitly reviewed draft in a fresh child directory. $0."""
    try:
        folder,report=Reanalysis().run(reference,out,expected_hash,confirmed=confirmed,reviewer=reviewer)
        typer.echo(report)
        typer.echo('written to '+str(folder))
    except (ValueError,OSError,KeyError,RuntimeError) as error:
        raise typer.BadParameter(str(error)) from None

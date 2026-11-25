"""``adroit ledger``: a paid journal's explicit recovery (the owner's direction D-7, 2026-10-25). $0: nothing is sent."""
from pathlib import Path

import typer

app = typer.Typer(pretty_exceptions_show_locals=False, help="Paid journals (paid.jsonl): recover a torn last line. $0; nothing is ever sent again.",
                  no_args_is_help=True)


@app.command("recover")
def recover(path: Path = typer.Argument(..., help="the paid journal (a session's or a run's paid.jsonl)")) -> None:
    """Recover a paid journal whose last line was cut short while it was written: the original kept in a side copy,
    the torn bytes replaced by a recovery entry where they identify their request (its reservation kept in full, the
    request uncertain); otherwise nothing changes and the budget stays blocked. Never resends a request."""
    from adroit.agents.budget import recover_torn_tail
    try:
        typer.echo(recover_torn_tail(path))
    except (ValueError, OSError) as error:
        typer.echo(f"Not recovered: {error}", err=True)
        raise typer.Exit(1) from None

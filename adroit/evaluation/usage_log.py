"""The opt-in command log of the usability sessions (R-24; ``docs/usability/protocol.md``).

Off unless ``ADROIT_USAGE_LOG`` names a file. When it does, each ``adroit`` command appends one JSON line to it: the
command's name (``track1``, ``evidence export``), when it started (UTC), how long it ran, whether it ended in an
error, and the session's label (``ADROIT_USAGE_SESSION``, the protocol's pseudonym ``Pnn[-Tn[-condition]]``, as
``P03-T2-assisted``; any other label is not recorded). Never its
arguments, paths, inputs, outputs or anything typed. The workbench's runs are logged too: its runner calls the same
commands, and the environment is inherited.

The log measures where a session's time goes (waiting on a calculation or not); the researcher's active effort is
the paired timer's (``adroit assist-session``), not this.
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import typer
from pydantic import Field

from adroit.core.state import StrictModel

LOG, SESSION = "ADROIT_USAGE_LOG", "ADROIT_USAGE_SESSION"
# The protocol's pseudonymous labels only: P01, P01-T2, P01-T2-assisted (the batch audit's B20-07: a name written with
# an underscore had passed a character filter)
LABEL = re.compile(r"^P\d{2,3}(-T\d{1,2}(-(manual|assisted))?)?$")


class UsageEntry(StrictModel):
    """One command: its name, start, duration and outcome; nothing it was given or made."""
    command: str
    started: datetime
    seconds: float = Field(ge=0, allow_inf_nan=False)
    outcome: Literal["ok", "error"]
    session: str = ""


def command_path(group: Any, first: str, argv: list[str]) -> str:
    """The command's name only: ``first`` and, while each next word of ``argv`` names a subcommand of the group
    before it, that word. An argument, an option or a path is never a subcommand's name, so it is never kept."""
    names, command = [first], group.commands.get(first)
    words = argv[argv.index(first) + 1:] if first in argv else []
    for word in words:
        if word not in getattr(command, "commands", {}):            # a group has commands (typer's own click)
            break
        names.append(word)
        command = command.commands[word]
    return " ".join(names)


def begin(ctx: typer.Context) -> None:
    """Called by the CLI before each command: when the log is on, the command's entry is written when it ends."""
    path = os.environ.get(LOG, "")
    if not path or not ctx.invoked_subcommand or not hasattr(ctx.command, "commands"):
        return
    started, clock = datetime.now(timezone.utc), time.monotonic()
    name = command_path(ctx.command, ctx.invoked_subcommand, sys.argv[1:])
    ctx.call_on_close(lambda: record(Path(path), name, started, time.monotonic() - clock,
                                     outcome(sys.exc_info()[1])))


def outcome(error: BaseException | None) -> Literal["ok", "error"]:
    """"ok" for a command that returned or exited with status 0 (``typer.Exit()``), else "error"."""
    if error is None or (isinstance(error, typer.Exit) and error.exit_code == 0):
        return "ok"
    return "error"


def record(path: Path, command: str, started: datetime, seconds: float, result: Literal["ok", "error"]) -> UsageEntry:
    """Append one entry; a label that is not pseudonymous is left out, and a log that cannot be written never stops
    the command."""
    label = os.environ.get(SESSION, "")
    entry = UsageEntry(command=command, started=started, seconds=round(max(seconds, 0.0), 3), outcome=result,
                       session=label if LABEL.match(label) else "")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(entry.model_dump_json() + "\n")
    except OSError:
        pass
    return entry


def read(path: Path) -> list[UsageEntry]:
    """Every entry of a log, in order."""
    return [UsageEntry.model_validate_json(line) for line in Path(path).read_text().splitlines() if line.strip()]

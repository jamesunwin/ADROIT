"""Cooperative pause/cancel for a running investigation (``runs/<id>/control.json``).

The workbench (or a human with a text editor) writes ``control.json`` with
``{"action": "pause" | "cancel", "requested_at": <unix time>}``; the pipeline
honors it at every stage boundary and while it waits at a human gate. An
honored request is renamed to ``control.<action>.<ms>.honored.json`` -- kept as
part of the record, and out of the way so a resumed run does not immediately
stop again. Lives in the orchestrator (not the UI) because the engine must
never import UI code; the workbench (DM11) will re-export the client helpers.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

CONTROL_FILE = "control.json"
ACTIONS = ("pause", "cancel")


def request(run_dir: str | Path, action: str) -> Path:
    """Client side: ask the run to pause or cancel (atomic write).

    Raises:
        ValueError: for an action other than ``pause`` / ``cancel``.
    """
    if action not in ACTIONS:
        raise ValueError(f"unknown control action {action!r}; expected one of {ACTIONS}")
    from adroit.core.durable import write_atomic
    return write_atomic(Path(run_dir) / CONTROL_FILE, json.dumps({"action": action, "requested_at": time.time()}))


def read(run_dir: str | Path) -> str | None:
    """The pending action (``pause`` / ``cancel``), or None where there is no request. A request that cannot be read,
    or names no known action, is ``cancel``: never permission to keep going (the consolidation plan's M3; it had read
    as no request). ``consume`` archives it as it is, so its bytes stay in the record."""
    path = Path(run_dir) / CONTROL_FILE
    if not path.is_file():
        return None
    try:
        action = json.loads(path.read_text(encoding="utf-8")).get("action")
    except (ValueError, OSError, AttributeError):
        return "cancel"
    return action if action in ACTIONS else "cancel"


def consume(run_dir: str | Path) -> str | None:
    """Engine side: return the pending action and archive the request, else None."""
    action = read(run_dir)
    if action is None:
        return None
    path = Path(run_dir) / CONTROL_FILE
    stamp = int(time.time() * 1000)
    try:
        os.replace(path, path.with_name(f"control.{action}.{stamp}.honored.json"))
    except OSError:
        path.unlink(missing_ok=True)
    return action

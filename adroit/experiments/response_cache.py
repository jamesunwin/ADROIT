"""The shell-model nuclear responses' cache in the tools folder (``physics.haxton``), kept readable from outside it.

``physics.haxton.form_factors`` computes an isotope's responses once and keeps them in
``<tools>/nuclear-responses/haxton_<isotope>_<interaction>.json``, a file it keeps by its existence and writes in
place. Cut short by an interrupted write, the file stopped every calculation that reads it until it was removed by
hand (the audit loop's AL2-16, 2026-11-14). ``physics/`` is fingerprinted by the limit tables (``limit_tables.CODE``)
and is changed only by the owner, so its writer is left as it is (the record names it for the owner), and the cache is
healed here instead: at the first module loaded in a process (``registry.load_module``), a file that cannot be read
as JSON and was last written over a minute ago (no write in progress) is set aside, renamed
``<name>.unreadable-<UTC time>`` and never deleted, so the responses are computed again when next needed, and a
warning says so (the owner's condition, 2026-11-14: self-healing, with a message). A tools folder that cannot be
searched gives a warning, never an error, and a file passed over as too young is looked at again at a later load: the
folder is done with, for the process, only once neither happened (AL3-19).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

SETTLED_S = 60.0          # a file last written this long ago is no write in progress
_HEALED: dict[Path, tuple[str, ...]] = {}       # the folders done with in this process, and what was done


def heal_now() -> tuple[str, ...]:
    """``heal`` for the tools folder in force."""
    from adroit.core.config import get_settings
    return heal(Path(get_settings().tools_dir))


def heal(tools_dir: Path) -> tuple[str, ...]:
    """Set aside each unreadable response file in ``tools_dir`` (module docstring); what was done, one line each.
    Remembered for the process only once the folder was searched and no unreadable file was passed over as young."""
    if tools_dir in _HEALED:
        return _HEALED[tools_dir]
    folder = tools_dir / "nuclear-responses"
    try:
        if not folder.is_dir():
            _HEALED[tools_dir] = ()
            return ()
        paths = sorted(folder.glob("haxton_*.json"))
    except OSError as error:
        logging.getLogger("adroit").warning("nuclear responses: the folder %s could not be searched (%s): a cut-short "
                                            "file there is not set aside", folder, type(error).__name__)
        return ()
    done, young = [], False
    for path in paths:
        try:
            json.loads(path.read_text())
            continue
        except (OSError, ValueError):
            pass
        try:
            if time.time() - path.stat().st_mtime < SETTLED_S:
                young = True                         # looked at again at a later load
                continue
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            aside = path.with_name(f"{path.name}.unreadable-{stamp}")
            path.rename(aside)
        except OSError:
            continue
        done.append(f"{path.name} could not be read (cut short) and was set aside as {aside.name}; it is computed "
                    "again when next needed")
        logging.getLogger("adroit").warning("nuclear responses: %s", done[-1])
    if not young:
        _HEALED[tools_dir] = tuple(done)
    return tuple(done)

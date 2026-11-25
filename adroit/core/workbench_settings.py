"""The researcher's own workbench choices, kept between restarts: ``workbench_settings.json`` in the projects folder
(``Settings.projects_dir``, which ``ADROIT_PROJECTS_DIR`` moves).

One choice so far (the owner, 2026-11-18, the post-review changes item 1): **auto-approve paid calls with the
default models**. When it is on, every spend box ("I approve this spend") starts ticked while each of its page's model
choices holds its default; the box's amount is still the hard cap, a session's cap is still raised only by hand, and
every scientific choice still waits for the researcher. It is off by default, and off where the file is absent or
cannot be read: a damaged file never approves spending.
"""
from __future__ import annotations

import json
from pathlib import Path

from adroit.core.config import get_settings
from adroit.core.durable import write_atomic
from adroit.core.state import StrictModel

FILE = "workbench_settings.json"


class WorkbenchSettings(StrictModel):
    """The workbench's saved choices."""
    auto_approve_default_models: bool = False


def settings_file() -> Path:
    """Where the choices are kept: the projects folder's ``workbench_settings.json``."""
    return get_settings().projects_dir / FILE


def load() -> WorkbenchSettings:
    """The saved choices; the defaults (nothing auto-approved) where the file is absent or cannot be read."""
    try:
        return WorkbenchSettings.model_validate_json(settings_file().read_bytes())
    except (OSError, ValueError):
        return WorkbenchSettings()


def save(settings: WorkbenchSettings) -> Path:
    """Keep ``settings``, written whole (``durable.write_atomic``)."""
    return write_atomic(settings_file(), json.dumps(settings.model_dump(mode="json"), indent=1) + "\n")


def auto_approve() -> bool:
    """Whether paid calls with the default models are approved by the setting (module docstring)."""
    return load().auto_approve_default_models


def set_auto_approve(on: bool) -> WorkbenchSettings:
    """Turn the auto-approval on or off, and keep it."""
    settings = load().model_copy(update={"auto_approve_default_models": bool(on)})
    save(settings)
    return settings

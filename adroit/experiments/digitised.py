"""Published inputs that exist only as figures, digitised from the figures' vector data.

The tables are in ``data/digitised/``, one YAML file per figure with its
source, figure number, date and method; ``docs/dm3/digitise_figures.py``
regenerates them from the arXiv PDFs.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    """One digitised figure, e.g. ``"pico60_2019_fig3"``."""
    text = resources.files("adroit.experiments").joinpath(
        f"data/digitised/{name}.yaml").read_text()
    return yaml.safe_load(text)

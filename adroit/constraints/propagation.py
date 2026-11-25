"""Transport and halo uncertainty in bounds from charged cosmic rays: three declared propagation models.

A charged messenger such as an antiproton does not travel straight from where dark matter annihilates. It diffuses
through the Galaxy's turbulent magnetic field, is convected and reaccelerated, and escapes through the boundary of a
diffusive halo of half-height L, so its flux at Earth depends on transport parameters fitted to secondary-to-primary
ratios (B/C) and on the dark-matter density within a few kpc. A bound inherits those uncertainties. Each record of
this kind states three versions of its bound, from its source's own systematics
(``data/propagation/<record>.yaml``):

- **conservative:** the weakest bound over the source's transport schemes and halo profiles, mass by mass;
- **central:** the source's fiducial bound;
- **aggressive** (also called *relaxed*): the strongest bound over the same choices.

The verdict uses one model: a run's ``propagation``, else the setting ``ADROIT_CR_PROPAGATION`` (default
conservative). A point that the chosen model allows but a stronger model excludes is flagged, never excluded, so a
model is not ruled out by the most aggressive assumptions alone.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import yaml

Model = Literal["conservative", "central", "aggressive"]
MODELS: tuple[Model, ...] = ("conservative", "central", "aggressive")      # weakest bound first
ALIASES = {"relaxed": "aggressive"}
DATA = Path(__file__).with_name("data") / "propagation"
# the records whose bounds are from charged cosmic rays: each ships its propagation file (AL2-10: without it the central
# bound had been applied under the chosen model's name)
CHARGED = ("calore-2202.03076-pbar",)
_CHOICE: ContextVar[str | None] = ContextVar("adroit_cr_propagation", default=None)


def normalise(name: str) -> Model:
    """The model a name means (``relaxed`` is ``aggressive``); a ValueError for anything else."""
    model = ALIASES.get(name.strip().lower(), name.strip().lower())
    if model not in MODELS:
        raise ValueError(f"unknown propagation model {name!r}: choose one of {', '.join(MODELS)} (or relaxed)")
    return model  # type: ignore[return-value]


def chosen() -> Model:
    """The model in force: the one a run set (``using``), else the setting ``ADROIT_CR_PROPAGATION``."""
    from adroit.core.config import get_settings
    return normalise(_CHOICE.get() or getattr(get_settings(), "cr_propagation", "conservative"))


@contextmanager
def using(model: str | None) -> Iterator[None]:
    """Evaluate with this model (None: leave the current choice)."""
    if model is None:
        yield
        return
    token = _CHOICE.set(normalise(model))
    try:
        yield
    finally:
        _CHOICE.reset(token)


def resolved(request):
    """The request with its propagation model stated: its own, else the one in force (``chosen``)."""
    return request.model_copy(update={"propagation": getattr(request, "propagation", None) or chosen()})


def stronger(model: str) -> list[Model]:
    """The models whose bounds are stronger than this one's."""
    return list(MODELS[MODELS.index(normalise(model)) + 1:])


class Unavailable(FileNotFoundError):
    """A bound from charged cosmic rays whose propagation file is missing (a damaged installation)."""


def unavailable(record_id: str) -> str:
    """Why a record's bound cannot be taken under any propagation model (one of ``CHARGED`` whose file is missing),
    or "": a search on it is then undecided with this reason, never decided under a model it cannot state."""
    try:
        load(record_id)
    except Unavailable as error:
        return str(error)
    return ""


@lru_cache(maxsize=8)
def load(record_id: str) -> dict | None:
    """A record's propagation file, or None if it has none (its bound is not from charged cosmic rays); for one of
    ``CHARGED``, ``Unavailable`` where its file is missing."""
    path = DATA / f"{record_id}.yaml"
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text())
        except (OSError, yaml.YAMLError) as error:
            data = error
        if record_id not in CHARGED or (isinstance(data, dict) and "factors" in data and "models" in data):
            return data if isinstance(data, dict) else None
        raise Unavailable(f"the propagation models of {record_id} cannot be stated: its file ({path}) is empty or "
                          "unreadable, so its bound is not known under any of them (reinstall ADROIT)")   # AL3-11
    if record_id in CHARGED:
        raise Unavailable(f"the propagation models of {record_id} cannot be stated: its file ({path}) is missing, "
                          "so its bound is not known under any of them (reinstall ADROIT)")
    return None


def factor(record_id: str, model: str, mass: float) -> float:
    """limit(model) / limit(central) at this dark-matter mass: above 1 for the conservative model, below 1 for the
    aggressive one. Outside the source's masses the conservative factor is its largest value and the aggressive its
    smallest, so neither claims more than the source shows anywhere. ``Unavailable`` for a record of ``CHARGED``
    whose file is missing."""
    model = normalise(model)
    data = load(record_id)
    if model == "central" or data is None:
        return 1.0
    table = data["factors"]
    masses, values = np.array(table["mass_gev"]), np.array(table[model])
    if not masses[0] <= mass <= masses[-1]:
        return float(values.max() if model == "conservative" else values.min())
    return float(10 ** np.interp(np.log10(mass), np.log10(masses), np.log10(values)))


def describe(record_id: str, model: str) -> str:
    """The model's definition for this record, as its file states it (where the file is missing, that it is)."""
    model = normalise(model)
    if why := unavailable(record_id):
        return f"{model}: {why}"
    data = load(record_id)
    return data["models"][model] if data else model

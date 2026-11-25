"""The standard model library (the owner, 2026-10-13): every model ADROIT has the code to formulate, beside the
personal library of the user's own models.

Two kinds, each in its subcategories (eighty entries in all, so the list is grouped):
- **Portal models** (``parameter_space.library``): complete dark-matter models from the literature (fields,
  Lagrangian, benchmark and the plane its papers plot) that Constrain a model (Track 1) scans; by family.
- **Interactions** (``library.interactions``): the cards Signal best fits (Track 2) searches, from nucleon-level
  operators O_i to relativistic interactions and mediator models; by layer.

Pure functions of the two registries; nothing is copied or computed here.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from adroit.core.state import StrictModel

PORTALS = "Portal models: constrain a model (Track 1)"
INTERACTIONS = "Interactions: searched by Signal best fits (Track 2)"
FAMILIES = {"Higgs portal": "Higgs portal", "vector portal": "Vector portals (dark photon, Z, B − L, L_μ − L_τ)",
            "pseudoscalar portal": "Pseudoscalar portal", "s-channel mediator": "s-channel mediators",
            "t-channel": "t-channel (coloured and lepton partners)", "extended scalar sector": "Extended scalar sectors",
            "electroweak multiplet": "Electroweak multiplets"}
LAYERS = {"nonrelativistic": "Nucleon-level operators O_i", "relativistic": "Relativistic interactions (Anand et al.)",
          "relativistic_lz": "Relativistic interactions in LZ's conventions", "mediator": "Mediator models",
          "quark": "Quark- and gluon-level operators"}


class StandardModel(StrictModel):
    """One entry of the standard library."""

    id: str
    kind: Literal["portal", "interaction"]
    title: str
    category: str
    subcategory: str
    summary: str                      # one line: the benchmark, or the interaction as written


def _layer(card) -> str:
    layer = card.layer.value
    return "relativistic_lz" if layer == "relativistic" and card.id.endswith("_LZ") else layer


@lru_cache(maxsize=1)
def entries() -> tuple[StandardModel, ...]:
    """Every standard model: the portal models by family, then the interactions by layer, each in registry order."""
    from adroit.library.interactions import registry
    from adroit.parameter_space import library
    out = [StandardModel(id=e.id, kind="portal", title=e.title, category=PORTALS,
                         subcategory=FAMILIES.get(e.family, e.family), summary=e.benchmark)
           for e in library.ENTRIES]
    out += [StandardModel(id=c.id, kind="interaction", title=c.name, category=INTERACTIONS,
                          subcategory=LAYERS.get(_layer(c), _layer(c)), summary=c.interaction or c.description)
            for c in registry.cards().values()]
    return tuple(out)


def entry(model_id: str) -> StandardModel:
    """One standard model by its id.

    Raises:
        KeyError: if no standard model has this id.
    """
    found = next((e for e in entries() if e.id == model_id), None)
    if found is None:
        raise KeyError(f"no standard model {model_id!r}")
    return found


def grouped(query: str = "") -> dict[str, dict[str, list[StandardModel]]]:
    """category → subcategory → entries, keeping only those whose id, title, subcategory or summary contains every
    word of ``query`` (case-insensitive)."""
    words = query.lower().split()
    out: dict[str, dict[str, list[StandardModel]]] = {}
    for e in entries():
        text = " ".join((e.id, e.title, e.subcategory, e.summary)).lower()
        if all(w in text for w in words):
            out.setdefault(e.category, {}).setdefault(e.subcategory, []).append(e)
    return out

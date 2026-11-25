"""Literature for a candidate (DM9): arXiv abstracts found by deterministic queries.

The constraint scout reads only what this module retrieves, and its citations are
then checked by ``references``. The queries are built from the candidate (its
interaction, mass, splitting) and from the classes of constraint DM7 knows. arXiv's
API (through ``corpus.fetch_arxiv``) is the only network call; results are cached
under the data folder, so a query is asked once.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from pydantic import Field

from adroit.core.config import get_settings
from adroit.core.state import StrictModel

PER_QUERY = 5
TEXT_LIMIT = 1200                        # characters of each abstract shown to the agent


class CandidateSketch(StrictModel):
    """What the scout and the queries need to know about a candidate."""

    label: str
    interaction: str                     # in words, e.g. "anapole dark matter (O8, O9)"
    mass_gev: float
    splitting_kev: float = 0.0
    spin: float = 0.5
    self_conjugate: bool = False
    mediator: str = ""                   # e.g. "a 2 TeV vector coupling to quarks", or ""
    couples_to: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)      # search phrases, most specific first
    details: dict[str, str] = Field(default_factory=dict)


class Abstract(StrictModel):
    """One arXiv result: identifier, title, authors, year, the abstract's text and the query that found it."""
    arxiv_id: str
    title: str
    authors: str = ""
    year: int = 0
    text: str = ""
    query: str = ""


Fetch = Callable[[str, int], list[Abstract]]


def _abs(*phrases: str) -> str:
    return " AND ".join(f'abs:"{p}"' for p in phrases)


def queries(c: CandidateSketch) -> list[str]:
    """arXiv searches for one candidate, in arXiv's field syntax: its own keywords first, then the
    constraint classes."""
    words = c.keywords or [c.interaction]
    out = [_abs("dark matter", w) for w in words[:2]]
    if c.splitting_kev > 0:
        out.append(_abs("inelastic dark matter", "constraint"))
    out.append(_abs("dark matter", "solar capture", "neutrino"))
    if c.mediator:
        out.append(_abs("dark matter", words[0], "relic"))
    if c.mass_gev < 10:
        out.append(_abs("light dark matter", "constraints"))
    return list(dict.fromkeys(out))


def fetch_arxiv_abstracts(query: str, n: int) -> list[Abstract]:
    """arXiv's API (network)."""
    from adroit.retrieval.corpus import fetch_arxiv
    return [Abstract(arxiv_id=re.sub(r"v\d+$", "", p.source_id), title=p.title, authors=p.authors, year=p.year, text=p.text[:TEXT_LIMIT], query=query)
            for p in fetch_arxiv(query=query, max_results=n)]


def search(c: CandidateSketch, fetch: Fetch | None = None, cache_path: Path | None = None,
           per_query: int = PER_QUERY) -> list[Abstract]:
    """The distinct abstracts the candidate's queries return, cached by query."""
    path = cache_path or get_settings().data_dir / "literature_cache.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    found: dict[str, Abstract] = {}
    for q in queries(c):
        if q not in cache:
            cache[q] = [a.model_dump() for a in (fetch or fetch_arxiv_abstracts)(q, per_query)]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cache, indent=1))
        for a in cache[q]:
            found.setdefault(a["arxiv_id"], Abstract.model_validate(a))
    return list(found.values())

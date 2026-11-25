"""Seed the literature collection with ~30 arXiv abstracts (a run-on-demand script).

Fetches abstracts relevant to the model-library families so retrieval is
demonstrable offline afterwards. This makes network calls to arXiv; it is not run
in CI. Usage:

    uv run python -m adroit.retrieval.seed_corpus            # into data/chroma
    uv run python -m adroit.retrieval.seed_corpus --path /tmp/chroma --per-query 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from adroit.retrieval.corpus import (
    default_corpus_path,
    fetch_arxiv,
    ingest_papers,
    open_collection,
)

# One query per family cluster; abstracts cover our library's domains.
SEED_QUERIES = [
    "van der Pol oscillator limit cycle weakly nonlinear",
    "SIR compartmental epidemic model basic reproduction number threshold",
    "SEIR epidemic incubation latent period dynamics",
    "mean-field Ising model phase transition critical temperature",
    "percolation on lattices and random networks spreading threshold",
    "multinomial logit discrete choice model random utility",
    "Rabi oscillations two-level system decoherence T1 T2",
    "Lotka-Volterra predator prey population cycles",
    "Duffing oscillator nonlinear resonance",
    "double-well potential Kramers escape noise-driven bistability",
]


def seed(path: Path, per_query: int = 3) -> int:
    """Fetch abstracts for each seed query and ingest them; return total chunk count."""
    collection = open_collection(path)
    papers = []
    for query in SEED_QUERIES:
        fetched = fetch_arxiv(query=query, max_results=per_query)
        print(f"  {len(fetched):2d} results for: {query}")
        papers.extend(fetched)
    total = ingest_papers(papers, collection)
    print(f"Ingested {len(papers)} papers as {total} chunks into {path}")
    return total


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI entry
    """Fetch arXiv abstracts for the seed queries into the literature index at ``--path``."""
    parser = argparse.ArgumentParser(description="Seed the literature corpus from arXiv.")
    parser.add_argument("--path", type=Path, default=default_corpus_path())
    parser.add_argument("--per-query", type=int, default=3)
    args = parser.parse_args(argv)
    seed(args.path, args.per_query)


if __name__ == "__main__":
    main()

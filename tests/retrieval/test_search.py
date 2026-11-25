"""Tests for literature search and mechanism-driven retrieval (offline + one live)."""

from __future__ import annotations

import pytest

from adroit.core.state import (
    EvidenceState,
    QualitativeFeature,
    QualitativeFeatureKind,
    VariableInfo,
)
from adroit.retrieval.corpus import Paper, fetch_arxiv, ingest_papers, open_collection
from adroit.retrieval.search import RetrievedPassage, search, search_for_mechanisms

_CORPUS = [
    Paper(source_id="sir", title="SIR epidemic threshold",
          text="An epidemic threshold arises in a compartmental model. Susceptible individuals "
               "become infected and then recovered. The basic reproduction number sets the "
               "epidemic threshold of the SIR compartmental epidemic model."),
    Paper(source_id="vdp", title="van der Pol",
          text="The van der Pol oscillator exhibits oscillatory dynamics that saturate onto a "
               "stable limit cycle, a weakly nonlinear self-sustained oscillation with amplitude "
               "saturation to a steady state."),
    Paper(source_id="ising", title="Ising transition",
          text="The mean-field Ising model shows a phase transition at a critical temperature "
               "with spontaneous magnetization vanishing above the critical point."),
    Paper(source_id="rabi", title="Rabi oscillations",
          text="A driven two-level system undergoes Rabi oscillations with decoherence "
               "characterised by relaxation and dephasing times."),
    Paper(source_id="choice", title="Discrete choice",
          text="The multinomial logit discrete choice model gives choice probabilities via a "
               "softmax over utilities of the alternatives."),
]


@pytest.fixture()
def collection():
    col = open_collection()
    ingest_papers(_CORPUS, col)
    return col


def test_search_returns_typed_passages(collection) -> None:
    results = search(collection, "phase transition critical temperature", k=2)
    assert results and all(isinstance(p, RetrievedPassage) for p in results)
    assert results[0].source == "ising" and -1.0 <= results[0].score <= 1.0


def test_retrieval_sanity_sir_in_top_three(collection) -> None:
    results = search(collection, "epidemic threshold compartmental model", k=3)
    assert "sir" in {p.source for p in results}


def test_search_with_metadata_filter(collection) -> None:
    results = search(collection, "oscillation", k=5, filters={"source_id": "vdp"})
    assert results and all(p.source == "vdp" for p in results)


def test_search_for_mechanisms_from_evidence(collection) -> None:
    evidence = EvidenceState(
        problem_id="prob-1", summary="A self-sustained oscillation that saturates.",
        variables=[VariableInfo(name="x", role_guess="observable")],
        qualitative_features=[
            QualitativeFeature(feature=QualitativeFeatureKind.oscillation, confidence=0.9),
            QualitativeFeature(feature=QualitativeFeatureKind.saturation, confidence=0.8)])
    passages = search_for_mechanisms(collection, evidence, k=3)
    assert passages and passages[0].source == "vdp"
    ids = [p.id for p in passages]
    assert len(ids) == len(set(ids))  # deduplicated by passage id


@pytest.mark.live
def test_fetch_arxiv_live() -> None:
    papers = fetch_arxiv(query="van der Pol oscillator", max_results=2)
    assert len(papers) >= 1
    assert papers[0].title and papers[0].text and papers[0].source_id


def test_equal_scores_are_ordered_by_passage_id() -> None:
    # A4: ChromaDB returns equal-distance hits in arbitrary order; the prompt
    # bytes (and so cached replay) must not depend on it.
    from adroit.retrieval.search import RetrievedPassage, _ranked

    def p(pid: str, score: float) -> RetrievedPassage:
        return RetrievedPassage(id=pid, text=pid, source="s", score=score)

    shuffled = [p("c", 0.5), p("a", 0.9), p("b", 0.5), p("d", 0.1)]
    assert [x.id for x in _ranked(shuffled)] == ["a", "b", "c", "d"]
    assert _ranked(shuffled) == _ranked(list(reversed(shuffled)))

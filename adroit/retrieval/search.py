"""Search the literature collection and build mechanism queries from evidence.

:func:`search` runs a similarity query and returns typed
:class:`RetrievedPassage` objects. :func:`search_for_mechanisms` turns an
:class:`EvidenceState` into natural-language queries built from its qualitative
features and variables (e.g. "oscillatory dynamics and saturation to a steady
state in x, v"), runs them, and returns deduplicated passages ranked by score.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from adroit.core.state import EvidenceState, QualitativeFeatureKind
from adroit.retrieval.embeddings import backend_for_collection, get_embedding_function

_FEATURE_PHRASES = {
    QualitativeFeatureKind.oscillation: "oscillatory dynamics",
    QualitativeFeatureKind.decay: "exponential decay",
    QualitativeFeatureKind.growth: "exponential growth",
    QualitativeFeatureKind.saturation: "saturation to a steady state",
    QualitativeFeatureKind.bistability: "bistable switching between two states",
    QualitativeFeatureKind.phase_transition: "phase transition at a critical threshold",
    QualitativeFeatureKind.power_law: "power-law scaling",
    QualitativeFeatureKind.network_structure: "dynamics on a network",
    QualitativeFeatureKind.collective_motion: "collective motion of interacting agents",
    QualitativeFeatureKind.noise_dominated: "noise-driven fluctuations",
    QualitativeFeatureKind.other: "dynamical behaviour",
}


class RetrievedPassage(BaseModel):
    """A single passage returned from the literature collection."""

    id: str
    text: str
    source: str
    title: str = ""
    section: str = ""
    score: float = Field(ge=-1.0, le=1.0)


def search(collection, query: str, k: int = 5, filters: dict | None = None
           ) -> list[RetrievedPassage]:
    """Return the ``k`` most similar passages to ``query`` (optionally filtered)."""
    embed = get_embedding_function(backend_for_collection(collection))
    result = collection.query(
        query_embeddings=[embed([query])[0]], n_results=k,
        where=filters or None, include=["documents", "metadatas", "distances"])
    passages = []
    ids = result["ids"][0]
    for i, doc in enumerate(result["documents"][0]):
        meta = result["metadatas"][0][i]
        passages.append(RetrievedPassage(
            id=ids[i], text=doc, source=str(meta.get("source_id", "")),
            title=str(meta.get("title", "")), section=str(meta.get("section", "")),
            score=1.0 - float(result["distances"][0][i])))
    return _ranked(passages)


def _ranked(passages: list[RetrievedPassage]) -> list[RetrievedPassage]:
    """Best score first; equal scores in passage-id order.

    The id tie-break makes the order a pure function of the scores: ChromaDB
    returns equal-distance hits in arbitrary order, which changed the prompt
    bytes and broke cached replay (13 calls paid on a "cached" rerun, M11).
    """
    return sorted(passages, key=lambda p: (-p.score, p.id))


def _mechanism_queries(evidence: EvidenceState, min_confidence: float = 0.5) -> list[str]:
    """Build natural-language mechanism queries from an evidence state.

    Only confident features (>= ``min_confidence``) drive the queries, so
    low-confidence detector noise does not pollute the retrieval; if nothing
    clears the bar, the single most-confident feature is used.
    """
    ranked = sorted(evidence.qualitative_features, key=lambda f: f.confidence, reverse=True)
    features = [f for f in ranked if f.confidence >= min_confidence] or ranked[:1]
    features = features[:3]
    phrases = [_FEATURE_PHRASES.get(f.feature, "dynamical behaviour") for f in features]
    variables = ", ".join(dict.fromkeys(v.name for v in evidence.variables if v.name))
    suffix = f" in {variables}" if variables else ""
    queries = [" and ".join(phrases) + suffix] if phrases else []
    queries += [phrase + suffix for phrase in phrases]
    return list(dict.fromkeys(q for q in queries if q.strip()))


def search_for_mechanisms(collection, evidence: EvidenceState, k: int = 5
                          ) -> list[RetrievedPassage]:
    """Retrieve passages relevant to the evidence's mechanisms, deduplicated by passage id."""
    best: dict[str, RetrievedPassage] = {}
    for query in _mechanism_queries(evidence):
        for passage in search(collection, query, k=k):
            if passage.id not in best or passage.score > best[passage.id].score:
                best[passage.id] = passage
    return _ranked(list(best.values()))[:k]

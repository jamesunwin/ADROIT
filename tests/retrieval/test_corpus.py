"""Tests for corpus chunking, deterministic embedding, and index round-trip (offline)."""

from __future__ import annotations

from adroit.retrieval.corpus import (
    Paper,
    chunk_paper,
    chunk_text,
    embed_texts,
    ingest_papers,
    open_collection,
)
from adroit.retrieval.search import search

_LONG_TEXT = " ".join(f"word{i}" for i in range(2000))


def test_embedding_is_deterministic_and_normalised() -> None:
    a = embed_texts(["the quick brown fox"])
    b = embed_texts(["the quick brown fox"])
    assert a == b
    norm = sum(v * v for v in a[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_chunking_is_deterministic_with_overlap() -> None:
    first = chunk_text(_LONG_TEXT, chunk_words=750, overlap_words=120)
    second = chunk_text(_LONG_TEXT, chunk_words=750, overlap_words=120)
    assert first == second and len(first) > 1
    # Consecutive chunks share the overlap window.
    tail = first[0].split()[-120:]
    head = first[1].split()[:120]
    assert tail == head


def test_short_text_is_a_single_chunk() -> None:
    assert chunk_text("just a few words") == ["just a few words"]


def test_chunk_paper_sets_metadata_and_sections() -> None:
    text = "Abstract " + "a " * 800 + "Methods " + "b " * 800 + "Results " + "c " * 100
    paper = Paper(source_id="p1", title="A study", authors="Ada L.", year=2021, text=text)
    chunks = chunk_paper(paper, chunk_words=750, overlap_words=100)
    assert len(chunks) > 2
    assert chunks[0].id == "p1#0" and chunks[0].metadata["source_id"] == "p1"
    assert chunks[0].metadata["section"] == "abstract"
    sections = {c.metadata["section"] for c in chunks}
    assert {"abstract", "methods", "results"} & sections
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_index_round_trip_insert_then_find() -> None:
    papers = [
        Paper(source_id="quantum", title="Qubits", text="quantum computing qubits entanglement "
              "superposition and quantum error correction on a quantum processor"),
        Paper(source_id="ocean", title="Tides", text="ocean currents tides and thermohaline "
              "circulation drive heat transport across the ocean basins"),
    ]
    collection = open_collection()  # in-memory
    count = ingest_papers(papers, collection)
    assert count == collection.count() == 2

    results = search(collection, "qubit entanglement superposition", k=1)
    assert len(results) == 1 and results[0].source == "quantum"

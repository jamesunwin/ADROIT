"""Tests for the embedding backends (hash regression, backend plumbing)."""

from __future__ import annotations

import sys

import pytest

from adroit.retrieval import corpus
from adroit.retrieval.embeddings import (
    backend_for_collection,
    collection_name,
    embed_texts,
    get_embedding_function,
)

_SENTENCE = "epidemic threshold in compartmental network models"


def test_hash_vectors_match_the_pre_move_implementation() -> None:
    # Regression anchor captured from corpus.embed_texts BEFORE the relocation:
    # existing on-disk collections must remain queryable byte-for-byte.
    v = embed_texts([_SENTENCE])[0]
    nonzero = {i: round(x, 6) for i, x in enumerate(v) if x != 0.0}
    assert len(v) == 1024
    assert nonzero == {284: 0.447214, 452: 0.447214, 637: 0.447214,
                       720: 0.447214, 893: 0.447214}


def test_corpus_reexport_is_the_same_function() -> None:
    assert corpus.embed_texts is embed_texts
    assert get_embedding_function("hash") is embed_texts


def test_collection_names_keep_hash_unsuffixed() -> None:
    assert collection_name("hash") == "adroit_literature"   # existing data readable
    assert collection_name("st") == "adroit_literature_st"  # separate space
    with pytest.raises(ValueError, match="unknown embedding backend"):
        collection_name("word2vec")


def test_open_collection_derives_name_and_search_matches_backend(monkeypatch) -> None:
    col = corpus.open_collection(backend="hash")
    assert col.name == "adroit_literature"
    assert backend_for_collection(col) == "hash"
    st_named = corpus.open_collection(backend="st", name=collection_name("st"))
    assert backend_for_collection(st_named) == "st"
    # Settings-driven selection.
    monkeypatch.setattr(corpus, "get_settings",
                        lambda: type("S", (), {"embedding_backend": "st"})())
    assert corpus.open_collection().name == "adroit_literature_st"


def test_the_cached_model_is_read_with_no_request_to_the_hub() -> None:
    """The first load asks for the local cache only; the hub only where that fails."""
    import adroit.retrieval.embeddings as emb
    calls = []

    def model(name, revision=None, local_files_only=False):
        calls.append(local_files_only)
        if local_files_only and len(calls) == 1 and name == "missing":
            raise OSError("not cached")
        return (name, revision)
    assert emb._load_st(model) == (emb._ST_MODEL_NAME, emb._ST_MODEL_REVISION) and calls == [True]


def test_st_backend_without_the_package_raises_actionably(monkeypatch) -> None:
    import adroit.retrieval.embeddings as emb
    monkeypatch.setattr(emb, "_st_model", None)
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # simulate absence
    fn = get_embedding_function("st")
    with pytest.raises(ImportError, match=r"\[retrieval\]"):
        fn(["hello"])


def _cached_model(monkeypatch) -> None:
    """The hub's library offline (it had fetched its agent registry from huggingface.co to build a header, even for a
    cached model), and a skip where the pinned model is not in the local cache: fetching it is a download, which the
    tests' fence refuses (the backend reads the cache with no request to the hub where the model is there)."""
    pytest.importorskip("sentence_transformers")
    import huggingface_hub.constants
    monkeypatch.setattr(huggingface_hub.constants, "HF_HUB_OFFLINE", True)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer
    import adroit.retrieval.embeddings as emb
    try:
        SentenceTransformer(emb._ST_MODEL_NAME, revision=emb._ST_MODEL_REVISION, local_files_only=True)
    except Exception:  # noqa: BLE001
        pytest.skip("the sentence-transformers model is not in the local cache (it is fetched at its first use)")


@pytest.mark.slow
def test_st_backend_is_semantic_when_installed(monkeypatch) -> None:
    _cached_model(monkeypatch)
    import numpy as np
    embed = get_embedding_function("st")
    a, b, c = embed(["an epidemic spreading through a town",
                     "an outbreak of infectious disease in a city",
                     "a pendulum swinging on a frictionless pivot"])
    related = float(np.dot(a, b))
    unrelated = float(np.dot(a, c))
    assert related > unrelated  # the semantic win the hash embedder cannot deliver


@pytest.mark.slow
def test_st_ranks_a_dark_matter_recoil_passage_above_an_unrelated_one(monkeypatch) -> None:
    _cached_model(monkeypatch)
    import numpy as np
    query, relevant, unrelated = get_embedding_function("st")([
        "dark matter particles scattering off nuclei in a xenon detector",
        "WIMP nuclear recoil direct detection in liquid xenon",
        "the orbit of Jupiter around the Sun"])
    assert np.dot(query, relevant) > np.dot(query, unrelated)

"""Embedding backends for the literature index.

Two backends, selected by ``Settings.embedding_backend`` (env
``ADROIT_EMBEDDINGS``):

* ``"hash"`` (default) -- the deterministic hashed bag-of-stemmed-words
  embedder. Fully offline and reproducible; the CI backend. Purely lexical:
  "epidemic threshold" matches an SIR passage only through shared stems.
* ``"st"`` -- local sentence-transformers (``all-MiniLM-L6-v2``), a real
  semantic embedder for the Stage-8 case studies. Optional dependency
  (``pip install -e ".[retrieval]"``); one-time model download, then offline.

The two spaces have different dimensions and must never mix, so collections
are name-suffixed per backend (:func:`collection_name`) and the query side
derives its backend from the collection's name (:func:`backend_for_collection`)
-- an index is always searched with the embedder that built it.
"""

from __future__ import annotations

import math
import re
from hashlib import md5
from typing import Callable

_EMBED_DIM = 1024
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STEM_LEN = 8  # prefix length: collapses "oscillator/oscillation/oscillatory" -> "oscillat"
_MIN_TOKEN = 3  # drop 1-2 char tokens (single-letter variable names, "in", "of", ...)
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "are", "was", "were", "from", "have",
    "has", "not", "but", "can", "its", "our", "using", "used", "use", "which", "also",
    "between", "into", "over", "than", "then", "such", "these", "those", "their", "them",
    "been", "more", "most", "each", "via", "per", "one", "two", "we", "of", "in", "on",
    "to", "as", "by", "is", "an", "at", "or", "be",
}

# Storage name of the literature index on disk (under the project's data directory).
_BASE_COLLECTION = "adroit_literature"
_ST_MODEL_NAME = "all-MiniLM-L6-v2"
_ST_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
_st_model = None  # lazy singleton (the model load is the expensive part)


def _hash_index(token: str) -> int:
    """Stable (cross-process) hash of a token into the embedding dimension."""
    return int(md5(token.encode("utf-8")).hexdigest(), 16) % _EMBED_DIM


def _stems(text: str) -> list[str]:
    """Content tokens (stopwords/short words dropped) truncated to a prefix stem."""
    stems = []
    for token in _TOKEN_RE.findall(text.lower()):
        if len(token) >= _MIN_TOKEN and token not in _STOPWORDS:
            stems.append(token[:_STEM_LEN])
    return stems


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts as L2-normalised hashed bag-of-stemmed-words vectors (deterministic)."""
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * _EMBED_DIM
        for token in _stems(text):
            vec[_hash_index(token)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        vectors.append([v / norm for v in vec] if norm > 0 else vec)
    return vectors


def _embed_st(texts: list[str]) -> list[list[float]]:
    """Semantic embeddings via a local sentence-transformers model (lazy load)."""
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "the 'st' embedding backend needs sentence-transformers; install the "
                "optional extras with:  pip install -e \".[retrieval]\"  "
                "(or uv sync --extra retrieval); on an Intel Mac it is not available (PyTorch's last x86_64 macOS "
                "build needs NumPy 1.x; docs/installation.md), so use the 'hash' backend") from exc
        _st_model = _load_st(SentenceTransformer)
    return [list(map(float, v)) for v in
            _st_model.encode(list(texts), normalize_embeddings=True)]


def _load_st(sentence_transformer):
    """The pinned model from the local cache where it is there, with no request to the hub (a cached model had still
    been checked against it at every load, so offline the tests could not pass: the audit loop's cycle 3); else fetched,
    at its first use."""
    try:
        return sentence_transformer(_ST_MODEL_NAME, revision=_ST_MODEL_REVISION, local_files_only=True)
    except Exception:  # noqa: BLE001 - not in the cache: fetched (the library raises several kinds here)
        return sentence_transformer(_ST_MODEL_NAME, revision=_ST_MODEL_REVISION)


def get_embedding_function(backend: str) -> Callable[[list[str]], list[list[float]]]:
    """The embedding callable for a backend name ("hash" or "st")."""
    if backend == "hash":
        return embed_texts
    if backend == "st":
        return _embed_st
    raise ValueError(f"unknown embedding backend {backend!r}; choose 'hash' or 'st'")


def collection_name(backend: str, base: str = _BASE_COLLECTION) -> str:
    """Backend-suffixed collection name; "hash" keeps the ORIGINAL unsuffixed name
    so every collection built before backends existed remains resolvable."""
    if backend == "hash":
        return base
    if backend == "st":
        return f"{base}_st"
    raise ValueError(f"unknown embedding backend {backend!r}; choose 'hash' or 'st'")


def backend_for_collection(collection) -> str:
    """The backend that built (and must query) a collection, from its name."""
    name = getattr(collection, "name", "") or ""
    return "st" if name.endswith("_st") else "hash"

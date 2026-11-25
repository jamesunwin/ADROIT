"""Ingest literature into a local ChromaDB collection for mechanism retrieval.

Sources are local PDFs dropped into ``data/papers/`` (text extracted with pypdf)
and arXiv results fetched by query or id list. Each paper is chunked into
overlapping ~1000-token windows with metadata (title, authors, year, source id,
a guessed section) and stored in ChromaDB.

Embeddings are computed here with a deterministic hashing bag-of-words embedder
rather than a downloaded neural model: this keeps ingestion and retrieval fully
offline and reproducible (no network, no onnxruntime model download), which is
what the tests and the offline demo require. The embedding is passed to ChromaDB
explicitly, so the collection never invokes its own embedding function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from adroit.core.config import get_settings

# Backward-compatible re-export: the embedders live in retrieval.embeddings now
# (two backends -- deterministic hash for CI, optional sentence-transformers).
from adroit.retrieval.embeddings import (  # noqa: F401
    backend_for_collection,
    collection_name,
    embed_texts,
    get_embedding_function,
)

_HEADINGS = {
    "abstract", "introduction", "background", "methods", "method", "model",
    "results", "experiment", "experiments", "discussion", "conclusion",
    "conclusions", "references",
}


def default_corpus_path() -> Path:
    """Default on-disk location for the persistent literature collection."""
    return get_settings().data_dir / "chroma"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _windows(n: int, size: int, overlap: int) -> list[tuple[int, int]]:
    """Sliding (start, end) word windows covering ``n`` words."""
    stride = max(1, size - overlap)
    windows, start = [], 0
    while start < n:
        end = min(start + size, n)
        windows.append((start, end))
        if end == n:
            break
        start += stride
    return windows


def chunk_text(text: str, chunk_words: int = 750, overlap_words: int = 120) -> list[str]:
    """Split text into overlapping word windows (~1000 tokens each). Deterministic."""
    words = text.split()
    if not words:
        return []
    return [" ".join(words[s:e]) for s, e in _windows(len(words), chunk_words, overlap_words)]


def _heading_positions(words: list[str]) -> list[tuple[int, str]]:
    """Word indices where a recognised section heading appears."""
    positions = []
    for i, word in enumerate(words):
        canonical = word.strip(".:").lower()
        if canonical in _HEADINGS:
            positions.append((i, canonical))
    return positions


def _section_for(headings: list[tuple[int, str]], start: int) -> str:
    """The last section heading at or before word index ``start``."""
    section = "unknown"
    for pos, name in headings:
        if pos <= start:
            section = name
        else:
            break
    return section


@dataclass
class Paper:
    """A source document to be chunked and indexed."""

    source_id: str
    title: str = ""
    authors: str = ""
    year: int = 0
    text: str = ""


@dataclass
class Chunk:
    """One indexed chunk with its ChromaDB id, text, and metadata."""

    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def chunk_paper(paper: Paper, chunk_words: int = 750, overlap_words: int = 120) -> list[Chunk]:
    """Chunk a paper into overlapping windows with per-chunk section metadata."""
    words = paper.text.split()
    headings = _heading_positions(words)
    chunks = []
    for index, (start, end) in enumerate(_windows(len(words), chunk_words, overlap_words)):
        chunks.append(Chunk(
            id=f"{paper.source_id}#{index}", text=" ".join(words[start:end]),
            metadata={"title": paper.title or paper.source_id, "authors": paper.authors,
                      "year": int(paper.year), "source_id": paper.source_id,
                      "section": _section_for(headings, start), "chunk_index": index}))
    return chunks


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def extract_pdf_text(path: str | Path) -> str:
    """Extract concatenated text from a PDF using pypdf."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def read_local_pdfs(directory: str | Path) -> list[Paper]:
    """Read every ``*.pdf`` in a directory into Paper objects (metadata best-effort)."""
    papers = []
    for pdf in sorted(Path(directory).glob("*.pdf")):
        text = extract_pdf_text(pdf)
        papers.append(Paper(source_id=f"pdf:{pdf.stem}", title=pdf.stem, text=text))
    return papers


def fetch_arxiv(query: str | None = None, id_list: list[str] | None = None,
                max_results: int = 10) -> list[Paper]:
    """Fetch papers from arXiv by query and/or id list, using their abstracts as text."""
    import arxiv

    search = arxiv.Search(query=query or "", id_list=id_list or [], max_results=max_results)
    papers = []
    for result in arxiv.Client().results(search):
        papers.append(Paper(
            source_id=result.get_short_id(), title=result.title,
            authors=", ".join(a.name for a in result.authors),
            year=result.published.year if result.published else 0,
            text=f"{result.title}\n\n{result.summary}"))
    return papers


def fetch_arxiv_pdf_text(arxiv_id: str) -> str:
    """The full text of an arXiv paper, from its PDF (downloaded to a temporary folder and discarded)."""
    import tempfile

    import requests

    response = requests.get(f"https://arxiv.org/pdf/{arxiv_id}", timeout=60)
    response.raise_for_status()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "paper.pdf"
        path.write_bytes(response.content)
        return extract_pdf_text(path)


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------


def open_collection(path: str | Path | None = None, name: str | None = None,
                    backend: str | None = None):
    """Open (creating if needed) a ChromaDB collection; in-memory if ``path`` is None.

    ``backend`` defaults to ``Settings.embedding_backend`` (env
    ``ADROIT_EMBEDDINGS``); when ``name`` is not given it is derived per
    backend so the two embedding spaces never share a collection -- and the
    "hash" default resolves to the ORIGINAL collection name, keeping every
    pre-existing index readable.
    """
    import chromadb

    backend = backend or get_settings().embedding_backend
    name = name or collection_name(backend)
    client = chromadb.PersistentClient(path=str(path)) if path else chromadb.EphemeralClient()
    return client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})


def ingest_papers(papers: list[Paper], collection, chunk_words: int = 750,
                  overlap_words: int = 120) -> int:
    """Chunk and upsert papers into the collection with explicit embeddings.

    The embedder is chosen FROM THE COLLECTION (by its backend-suffixed name),
    so a collection is always populated with the space it will be queried in.
    Returns the chunk count.
    """
    ids, docs, metas = [], [], []
    for paper in papers:
        for chunk in chunk_paper(paper, chunk_words, overlap_words):
            ids.append(chunk.id)
            docs.append(chunk.text)
            metas.append(chunk.metadata)
    if not ids:
        return 0
    embed = get_embedding_function(backend_for_collection(collection))
    collection.upsert(ids=ids, documents=docs, embeddings=embed(docs), metadatas=metas)
    return len(ids)

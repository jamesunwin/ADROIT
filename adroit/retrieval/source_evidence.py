"""Primary PDF excerpts, with content identities and independent reference checks."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from adroit.core.assistance import EvidencePacket, SourceRequest
from adroit.retrieval.references import Reference, ReferenceCache, identify, verify


def fetch_pdf(identifier: str) -> bytes:
    """Download a validated arXiv PDF with bounded size and timeout, no retries."""
    if not re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", identifier):
        raise ValueError("arXiv identifier required")
    import requests

    with requests.get(f"https://arxiv.org/pdf/{identifier}", timeout=30, stream=True) as response:
        response.raise_for_status()
        chunks = []
        size = 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 15_000_000:
                raise ValueError("PDF exceeds the source size cap")
            chunks.append(chunk)
    return b"".join(chunks)


def gather(
    requests: list[SourceRequest],
    folder: Path,
    *,
    resolver=None,
    download: Callable[[str], bytes] = fetch_pdf,
) -> list[EvidencePacket]:
    """Read at most four actual papers; matching content never verifies a physics claim."""
    if len(requests) > 4:
        raise ValueError("at most four source reads")
    folder.mkdir(parents=True, exist_ok=True)
    cache = ReferenceCache(folder / "references.json")
    result = []
    seen = set()
    for request in requests:
        if request.arxiv_id in seen:
            continue  # one <=25-word excerpt per paper
        seen.add(request.arxiv_id)
        packet = EvidencePacket(
            id=f"arxiv:{request.arxiv_id}:p{request.page}",
            reference=request.arxiv_id,
            title=request.title,
            page=request.page,
            url=f"https://arxiv.org/abs/{request.arxiv_id}",
        )
        try:
            _read(packet, request, folder, resolver, cache, download)
        except (ValueError, RuntimeError, OSError, PyPdfError) as error:
            packet.note = str(error)
        result.append(packet)
    return result


def _read(
    packet: EvidencePacket,
    request: SourceRequest,
    folder: Path,
    resolver,
    cache: ReferenceCache,
    download: Callable[[str], bytes],
) -> None:
    """Fill one packet from its verified paper's cited page; a refusal raises with its reason."""
    refs = verify(
        [Reference(kind="arxiv", id=request.arxiv_id, title=request.title)], resolver, cache
    )
    reference = refs[0]
    if not reference.verified:
        raise ValueError(reference.note or "reference not confirmed")
    packet.exists = True
    packet.identity, why = identify(request.title, reference) if request.title else ("", "no title cited")
    if packet.identity in ("contradicted", ""):
        raise ValueError(why)
    packet.reference_checked = packet.identity == "title"
    packet.title = reference.title
    path = _pdf(request, folder, download)
    reader = PdfReader(path)
    if not 1 <= request.page <= len(reader.pages):
        raise ValueError("page outside actual PDF")
    text = " ".join((reader.pages[request.page - 1].extract_text() or "").split())
    if not text:
        raise ValueError("source page contains no usable text")
    anchor = " ".join(request.anchor.split())            # as ``SourceRequest`` (I17-2): spaces are no anchor
    if anchor and not any(ch.isalnum() for ch in anchor):
        raise ValueError("a source anchor needs letters or digits to check")
    offset = text.casefold().find(anchor.casefold()) if anchor else 0
    if offset < 0:
        raise ValueError("requested source anchor absent")
    packet.excerpt = " ".join(text[offset:].split()[:25])
    packet.document_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    packet.content_checked = bool(anchor)
    packet.note = "; ".join(x for x in (
        "literal fetched passage only; scientific entailment requires a probe or expert" if anchor
        else "no anchor: the page was fetched and nothing on it was checked",
        why if packet.identity == "description" else "") if x)


def _pdf(request: SourceRequest, folder: Path, download: Callable[[str], bytes]) -> Path:
    """The paper's PDF in the folder, downloaded again unless its provenance record matches its bytes."""
    path = folder / f"{request.arxiv_id}.pdf"
    manifest = path.with_suffix(".provenance.json")
    proof = json.loads(manifest.read_text()) if manifest.is_file() else {}
    if (
        not path.is_file()
        or proof.get("identifier") != request.arxiv_id
        or hashlib.sha256(path.read_bytes()).hexdigest() != proof.get("sha256")
    ):
        content = download(request.arxiv_id)
        path.write_bytes(content)
        manifest.write_text(
            json.dumps(
                {
                    "identifier": request.arxiv_id,
                    "url": f"https://arxiv.org/pdf/{request.arxiv_id}",
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
        )
    return path

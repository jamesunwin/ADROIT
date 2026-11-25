"""An image whose bytes came from outside ADROIT, opened for its checks (a feature audit's ID-03, 2026-11-10).

Pillow refuses an image whose header declares more pixels than its own limit (``Image.DecompressionBombError``) while
it opens it, before ADROIT's dimension checks run. That refusal is neither a ``ValueError`` nor an ``OSError``, so it
had escaped every caller whose contract is to refuse a bad input with a ``ValueError``: a 65-byte PNG declaring
50,000 × 50,000 pixels raised out of the experimental library's upload instead of being refused. ``opened`` keeps
Pillow's protection (no pixel is allocated) and gives its refusal as the caller's ordinary one.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO


@contextmanager
def opened(data: bytes, refusal: str) -> Iterator:
    """The image ``data`` holds, opened lazily; a header Pillow refuses as too large raises ``ValueError(refusal)``,
    naming Pillow's reason."""
    from PIL import Image
    try:
        image = Image.open(BytesIO(data))
    except Image.DecompressionBombError as error:
        raise ValueError(f"{refusal}: {error}") from None
    with image:
        try:
            yield image
        except Image.DecompressionBombError as error:     # a refusal raised while it was being checked
            raise ValueError(f"{refusal}: {error}") from None

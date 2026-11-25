"""A feature audit's ID-03 (2026-11-10): an image whose header Pillow refuses as too large is refused by each upload's
own contract (a ``ValueError`` naming why), never raised out of it; Pillow's protection is kept (no pixel is allocated)
and nothing is stored. The 65-byte PNG declares 50,000 × 50,000 pixels, as the audit's did."""
from __future__ import annotations

import base64
import struct
import zlib
from io import BytesIO

import pytest
from PIL import Image

from adroit.core.images import opened


def png(width: int, height: int) -> bytes:
    """A PNG whose header declares ``width`` × ``height`` and carries no pixels."""
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"")) + chunk(b"IEND", b""))


HUGE = png(50_000, 50_000)


def ordinary() -> bytes:
    data = BytesIO()
    Image.new("RGB", (40, 20), "white").save(data, format="PNG")
    return data.getvalue()


def test_pillows_refusal_is_the_callers_and_an_ordinary_image_opens():
    with pytest.raises(ValueError, match=r"too large: Image size \(2500000000 pixels\) exceeds limit"):
        with opened(HUGE, "too large"):
            pass
    with opened(ordinary(), "too large") as image:
        assert image.size == (40, 20) and image.format == "PNG"
    with pytest.raises(ValueError, match="mine"):              # the caller's own refusal passes through unchanged
        with opened(ordinary(), "too large"):
            raise ValueError("mine")


def test_each_upload_refuses_the_header_by_its_own_message(tmp_path):
    from adroit.agents.llm import _bounded_image_material
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.library.personal import Catalog
    experimental = ExperimentalCatalog(tmp_path / "experimental")
    with pytest.raises(ValueError, match="image format or dimensions exceed supported limits: Image size"):
        experimental.asset_bytes("huge.png", HUGE, "data")
    assert not list(tmp_path.glob("experimental/assets/*"))
    assert experimental.asset_bytes("small.png", ordinary(), "data").suffix == ".png"      # the next one is stored
    with pytest.raises(ValueError, match="source image dimensions exceed supported limits: Image size"):
        Catalog(tmp_path / "personal").asset_bytes("huge.png", HUGE)
    assert not list(tmp_path.glob("personal/assets/*"))
    block = {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.b64encode(HUGE).decode()}}
    with pytest.raises(ValueError, match="image exceeds the supported dimension limit: Image size"):
        _bounded_image_material({"messages": [{"role": "user", "content": [block]}]}, "anthropic")

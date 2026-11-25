"""The auditor's DH recheck, DI-01 (the independent audit of 2026-11-06 (dh recheck), pin 5c99f14): the expert source review's page
(``ui/experimental_review._review_packet``) named its packet's images by their paths (``/files/...``), and the browser,
reading them after the rendering had returned, could show another packet's plots beside this source's text. Run here
on the workbench's own page (``/experiments/view``), its figure verification clicked as a researcher would: the matrix
row ``review.page`` (``tests/version_matrix.py``) runs its cells through ``review_page``. The sources are synthetic
papers (``tests/constraints/test_figure_anchors.figure_curve``), labelled simulated; nothing is signed; $0."""
from __future__ import annotations

import base64
import hashlib
import threading
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import pytest
from nicegui.testing import User

FALLING = [(10, 4e-43), (20, 3e-43), (40, 2e-43)]      # B's curve, on the same page's axes


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shown_images(user: User, root: Path, marker: str | None = "review_image") -> list[bytes]:
    """The bytes of each image the page shows of its packet (those ``marker`` marks; before DI-01's repair, which marks
    them, those the runs folder served; every image, with no ``marker``), as its browser would receive them now: its
    own (a data URL) decoded, or the file its path names under the runs folder (``/files``), read now."""
    from nicegui import ElementFilter, ui
    found = []
    with user:
        images = list(ElementFilter(kind=ui.image)) if marker is None else \
            list(ElementFilter(kind=ui.image, marker=marker)) or \
            [image for image in ElementFilter(kind=ui.image) if str(image.source).startswith("/files/")]
        for image in images:
            source = str(image.source)
            if source.startswith("data:"):
                found.append(base64.b64decode(source.split(",", 1)[1]))
            elif source.startswith("/files/"):
                found.append((root / source.removeprefix("/files/")).read_bytes())
    return found


def _sources(tmp_path: Path, monkeypatch):
    """A's source (the workbench's library) and B's, another revision's falling curve on the same figure."""
    import adroit.retrieval.experimental_ingestion as ingestion
    from adroit.core.config import get_settings
    from tests.constraints.test_figure_anchors import ANCHORS, QUOTES, _figure_png, figure_curve
    monkeypatch.setattr(ingestion, "render_page", lambda path, page: _figure_png())
    a = figure_curve(tmp_path / "a", QUOTES[1:2], ANCHORS[1:2])
    b = figure_curve(tmp_path / "b", QUOTES[1:2], ANCHORS[1:2], points=FALLING)
    monkeypatch.setattr(get_settings(), "experimental_library_dir", a[0].root)
    return a, b


async def _verify(user: User) -> str:
    """The figure verification clicked as the researcher would, every check made: what the page said."""
    from adroit.constraints.experimental_review import FIGURE_CHECKLIST
    user.find("Expert reviewer name").elements.pop().value = "Synthetic verifier"
    user.find("Source-anchor tolerance (relative)").elements.pop().value = .1
    user.find("Reviewed mass range from (GeV)").elements.pop().value = 10
    user.find("Reviewed mass range to (GeV)").elements.pop().value = 40
    for name in FIGURE_CHECKLIST:
        user.find("Figure check: " + name).elements.pop().value = True
    user.find("I compared the calibrated overlay with the figure over the whole declared range").elements.pop() \
        .value = True
    user.notify.messages.clear()
    user.find("Verify the figure by hand ($0)").click()
    from nicegui import ElementFilter, ui
    with user:
        said = [e.text for e in ElementFilter(kind=ui.label) if e.text.startswith("Figure verification:")]
    return said[-1] if said else " | ".join(user.notify.messages)


async def review_page(user: User, tmp_path: Path, monkeypatch, case: str) -> str:
    """The review page opened on A's source, ``case`` made (``tests/version_matrix.py``'s CASES: T1, B's whole packet
    written into the folder after A's rendering returned, before the page is shown; T2, A's own source's packet drawn
    otherwise (its lines thicker), whole and intact, once it is shown: not the packet the researcher saw; P,
    A's overlay replaced by B's once the page is shown; ABA, B's whole packet written then A's very bytes restored, once
    it is shown; W, another packet writer, B's, into
    the folder at A's overlay's return, given 3 s while A's packet is being written), then the figure verification
    clicked: "A" (the page showing A's source and A's images, as A's rendering wrote them, and the verification
    accepted), "A then refused" (shown so, the verification refused), "one owner" (shown so, and B writing nothing
    while A's writer held the folder), or what it showed."""
    from adroit.constraints import experimental_review as review
    from adroit.core.durable import write_atomic
    from adroit.ui import experimental_review as page
    from adroit.ui.app import build_pages
    (catalog_a, a), (catalog_b, b) = _sources(tmp_path, monkeypatch)
    root = tmp_path / "runs"
    build_pages(root)
    name = "rendered_packet" if hasattr(page, "rendered_packet") else "plot_packet"       # the page's renderer
    real, seen = getattr(page, name), {}

    def b_packet(out: Path) -> None:
        review.plot_packet(b.reference, "limit", out, catalog_b)

    def rendered(reference, result_id, out, catalog, *args, **kwargs):
        if case == "W":
            seen["out"] = out
        found = real(reference, result_id, out, catalog, *args, **kwargs)
        seen["out"] = out
        seen["A"] = {n: (out / n).read_bytes() for n in ("published_values.png", "source_overlay.png")}
        if case == "W":
            seen["B"].join(90)
        if case == "T1":
            b_packet(out)                                 # after A's rendering returned, before its images are shown
        return found
    overlay = review._source_overlay

    def drawn(reference, *args, **kwargs):                # W: B starts at A's overlay's return, A's packet unfinished
        path = overlay(reference, *args, **kwargs)
        if case == "W" and reference == a.reference:
            seen["B"] = threading.Thread(target=b_packet, args=(seen["out"],))
            seen["B"].start()
            seen["B"].join(3)
            seen["B written while A held"] = not seen["B"].is_alive() or \
                (seen["out"] / "review_packet.json").exists()
        return path
    with patch.object(page, name, rendered), patch.object(review, "_source_overlay", drawn):
        await user.open("/experiments/view?" + urlencode({"reference": a.reference}))
    out = seen["out"]
    if case == "P":
        kept = (out / "source_overlay.png").read_bytes()
        review.plot_packet(b.reference, "limit", tmp_path / "b packet", catalog_b)
        write_atomic(out / "source_overlay.png", (tmp_path / "b packet" / "source_overlay.png").read_bytes())
        assert (out / "source_overlay.png").read_bytes() != kept
    if case == "T2":                                      # A's source drawn otherwise, whole, once A's is shown
        import matplotlib
        with matplotlib.rc_context({"lines.linewidth": 5}):
            review.plot_packet(a.reference, "limit", out, catalog_a)
    if case == "ABA":
        kept = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
        b_packet(out)                                     # once the page is shown, before its verification
        for n, data in kept.items():
            write_atomic(out / n, data)
    from nicegui import ElementFilter, ui
    with user:
        text = "\n".join(str(getattr(e, "content", "")) for e in ElementFilter(kind=ui.code))
    images = shown_images(user, root)
    whole = a.reference in text and b.reference not in text and images == [seen["A"]["published_values.png"],
                                                                           seen["A"]["source_overlay.png"]]
    if not whole:
        return f"shown: A's text {a.reference in text}, B's {b.reference in text}; images A's " \
               f"{[i in seen['A'].values() for i in images]}"
    said = await _verify(user)
    if case == "W":
        return "one owner" if not seen["B written while A held"] else "B written inside A's packet"
    return "A" if said.startswith("Figure verification: True") else "A then refused"


@pytest.mark.parametrize("case, wanted", [("B", "A"), ("T1", "A then refused"), ("T2", "A then refused"),
                                          ("P", "A then refused"), ("ABA", "A"), ("W", "one owner")])
async def test_the_review_page_shows_the_packet_its_rendering_wrote(user: User, tmp_path, monkeypatch, case, wanted):
    """DI-01, the auditor's case (T1): B's whole packet written into the folder after A's rendering returned, before its
    images were shown, the page still shows A's text and A's images, as A's rendering wrote them, and its figure
    verification, now bound to the packet shown, is refused. Before, the page named the images by their paths, and the
    browser read B's plots beside A's text. And the page's other cases: its baseline (A shown, verified); A's source's
    packet drawn otherwise once the page is shown (T2: A's still shown, the verification refused, since the packet in
    the folder is not the one shown, though whole and A's source's); A's overlay replaced once the page is shown (P: A's
    still shown, refused); B's packet written and A's very bytes restored (ABA:
    the packet shown, verified); and another packet writer into the folder as A's is written (W: it waits)."""
    assert await review_page(user, tmp_path, monkeypatch, case) == wanted


async def test_a_record_s_page_shows_the_figure_drawn_for_it(user: User, tmp_path):
    """DI-01's class, the curated record's page (``ui/records.record_page``): its figure is the one drawn for the page,
    shown as drawn (its own image), and nothing is written under the runs folder; before, it was written to
    ``.records/<id>.png`` there and named by its path for the browser to read later."""
    from adroit.constraints import database, review
    from adroit.ui.app import build_pages
    root = tmp_path / "runs"
    build_pages(root)
    record = database.record("fermi-1503.02641-dsph")
    await user.open("/record?" + urlencode({"id": record.id}))
    images = shown_images(user, root, None)
    from nicegui import ElementFilter, ui
    with user:
        sources = [str(image.source) for image in ElementFilter(kind=ui.image)]
    assert review.figure(record) in images and any(s.startswith("data:image/png") for s in sources), sources
    assert not (root / ".records").exists()

"""The auditor's DH recheck (the independent audit of 2026-11-06 (dh recheck), pin 5c99f14): DI-01, a review page naming its packet's
images by their paths, so that the browser, reading them later, showed another packet's plots beside this source's
text, and a figure verification that bound no packet shown; DI-03, a packet's values plot, source page and record
written through links into a folder another writer held. (DI-01's page is run in ``tests/ui/test_di_review_page.py``;
DI-02, the plane's legend and tooltip, in ``tests/version_matrix.py`` and its harnesses.) No calculation, provider or
signature: the curves and pages are fixtures, labelled simulated; $0 is spent."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from adroit.core.durable import publishing
from tests.orchestrator import test_dh_fixes as dh

MEMBERS = ("published_values.png", "source_page.bin", "source_overlay.png", "review_packet.json")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _files(folder: Path) -> dict[str, str]:
    """Each file of ``folder`` (its own entries, a link read through) and its digest."""
    return {p.name: sha(p.read_bytes()) for p in sorted(folder.iterdir()) if p.is_file()}


# --- DI-03: each member of a packet is written to its own entry ------------------------------------------------------

@pytest.mark.parametrize("name", MEMBERS)
@pytest.mark.parametrize("held", ["its target's folder", "its own folder"])
@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_a_packet_member_that_is_a_link_is_written_in_its_own_folder(tmp_path, by, held, name):
    """DI-03, the auditor's case: A's packet in ``held``; B's packet folder holds ``name``, a link to A's file there; B's whole
    packet writer runs (another thread, or another process) while A's folder is held by this thread's writer (its
    target's), or while B's own folder is (its own). With its target's folder held, B writes its packet in its own
    folder, the link replaced by B's file, and A's held folder is untouched; with its own held, B waits for that hold,
    writing nothing, then does the same. Before, B's values plot, source page and record were written through the link
    into A's held folder (its overlay, by ``write_figure``, was already its own: DH-04)."""
    from adroit.constraints import experimental_review as review
    target, out = tmp_path / "held", tmp_path / "writer"
    with dh.packets() as contracts:
        review.plot_packet("synthetic:A", "limit", target, object())
        out.mkdir()
        (out / name).symlink_to(target / name)
        a = _files(target)
        with publishing(target if held == "its target's folder" else out):
            trying, waiting, finish = dh._b_packet(out, by)
            assert trying()
            if held == "its own folder":
                waiting(3)
                assert _files(target) == a and (out / name).is_symlink() and len(list(out.iterdir())) <= 2
            else:
                b = finish()
            assert _files(target) == a                  # nothing written into the held folder, through any link
        if held == "its own folder":
            b = finish()
        reviewed = review._reviewed(out, "synthetic:B", "limit", contracts["synthetic:B"])
    assert _files(target) == a
    assert not (out / name).is_symlink(), f"{name} still the link"
    assert reviewed[1:] == (b["geometry_sha256"], b["overlay_sha256"])


# --- DI-01: a page shows the packet its rendering wrote, and its verification binds to it ---------------------------

def test_a_rendered_packet_gives_the_images_it_wrote(tmp_path):
    """DI-01, the producer: ``rendered_packet`` gives the bytes of each image it wrote, the overlay's those its draw
    kept (its record's digest); another packet written into the folder after it has returned leaves them A's."""
    from adroit.constraints import experimental_review as review
    out = tmp_path / "packet"
    with dh.packets():
        report, images = review.rendered_packet("synthetic:A", "limit", out, object())
        written = {name: (out / name).read_bytes() for name in ("published_values.png", "source_overlay.png")}
        review.plot_packet("synthetic:B", "limit", out, object())
    assert images["plot"] == written["published_values.png"]
    assert images["source_overlay"] == written["source_overlay.png"]
    assert sha(images["source_overlay"]) == report["overlay_sha256"]
    assert sha((out / "source_overlay.png").read_bytes()) != report["overlay_sha256"]       # the folder is B's now


def test_a_rendered_packet_whose_overlay_changed_as_it_was_drawn_shows_nothing(tmp_path):
    """DI-01: an overlay whose file is not what its draw kept (changed by hand between its draw and its reading for the
    page) is refused: the packet is rendered again, never shown with another overlay."""
    from unittest.mock import patch
    from adroit.constraints import experimental_review as review
    out = tmp_path / "packet"
    real = review._source_overlay

    def overlay(*args, **kwargs):
        path = real(*args, **kwargs)
        Path(path).write_bytes(b"changed by hand")
        return path
    with dh.packets(), patch.object(review, "_source_overlay", overlay), \
            pytest.raises(ValueError, match="changed as it was drawn"):
        review.rendered_packet("synthetic:A", "limit", out, object())


def _figure_source(tmp_path, monkeypatch):
    """A synthetic paper's digitised curve with one printed anchor (``tests/constraints/test_figure_anchors``), its page
    rendered as the fixture's figure: SIMULATED."""
    import adroit.retrieval.experimental_ingestion as ingestion
    from tests.constraints.test_figure_anchors import ANCHORS, QUOTES, _figure_png, figure_curve
    monkeypatch.setattr(ingestion, "render_page", lambda path, page: _figure_png())
    return figure_curve(tmp_path, QUOTES[1:2], ANCHORS[1:2])


def test_a_figure_verification_is_bound_to_the_packet_shown(tmp_path, monkeypatch):
    """DI-01, the review action: the packet shown is A's; its folder then holds another packet of the same source, whole
    and intact but drawn otherwise (its lines thicker): verified as shown, it is refused, since the researcher did not
    see it; verified as that packet, or without a packet shown (the command), it is accepted as that one."""
    import matplotlib
    from adroit.constraints import experimental_review as review
    from tests.constraints.test_figure_anchors import _verify
    catalog, r = _figure_source(tmp_path, monkeypatch)
    folder = Path(catalog.root) / "packet"
    report, _ = review.rendered_packet(r.reference, "limit", folder, catalog)
    shown = tuple(report[k] for k in ("source_image_sha256", "geometry_sha256", "overlay_sha256"))
    assert _verify(catalog, r, packet=folder, shown=shown).manual.overlay_sha256 == shown[2]
    with matplotlib.rc_context({"lines.linewidth": 5}):
        other = review.plot_packet(r.reference, "limit", folder, catalog)
    assert other["overlay_sha256"] != shown[2] and other["geometry_sha256"] == shown[1]
    with pytest.raises(ValueError, match="not the one you were shown"):
        _verify(catalog, r, packet=folder, shown=shown)
    with pytest.raises(ValueError, match="not the one you were shown"):
        _verify(catalog, r, packet=folder, shown=())                 # a page that showed no overlay
    again = tuple(other[k] for k in ("source_image_sha256", "geometry_sha256", "overlay_sha256"))
    assert _verify(catalog, r, packet=folder, shown=again).manual.overlay_sha256 == other["overlay_sha256"]
    assert _verify(catalog, r, packet=folder).manual.overlay_sha256 == other["overlay_sha256"]


# --- DI-01, the class: the curated record's preview is drawn for its page --------------------------------------------

def test_a_record_s_preview_is_drawn_whole_to_its_own_entry(tmp_path):
    """DI-01 and DI-03's class, the curated record's figure (``review.plot``): drawn to bytes (``review.figure``),
    written whole to its own entry, a link there replaced, never written through."""
    from adroit.constraints import database, review
    record = database.record("fermi-1503.02641-dsph")
    elsewhere = tmp_path / "elsewhere.png"
    elsewhere.write_bytes(b"another folder's file")
    (tmp_path / "preview.png").symlink_to(elsewhere)
    path = review.plot(record, tmp_path / "preview.png")
    assert path.read_bytes() == review.figure(record) and not path.is_symlink()
    assert elsewhere.read_bytes() == b"another folder's file"

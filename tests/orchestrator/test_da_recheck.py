"""The auditor's CZ recheck, DA-01 and DA-03 (2026-11-02); DA-02's pages are in tests/ui/test_da_pages.py. DA-01: a Track 1
checkpoint had recorded its figures as read back after they were drawn, so that a replacement written in between was,
on resume, bound to the result as the figure drawn, shown and exported. DA-03: a valid promotion bundle made before
the manifest named a promotion's parent had been refused as inconsistent. Each case runs through the real run,
checkpoint, writer, reader, exporter or verifier; only the expensive calculation is substituted by a saved result."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from adroit.core.durable import write_atomic
from adroit.evidence import archive, bindings, build
from adroit.evidence.bindings import figure, read_report

NAME = "parameter_plane.png"
REPORT = "# Track 1 A\n\nAUDIT figure computed for A.\n\n![A](parameter_plane.png)\n"
FIXTURE = Path(__file__).parents[1] / "fixtures" / "bundles" / "promotion_v1_stable_A_1c039e0.zip"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- DA-01 ------------------------------------------------------------------------------------------------------


def _replacement() -> bytes:
    """B: another image, a valid PNG (the auditor's)."""
    from PIL import Image
    stream = io.BytesIO()
    Image.new("RGB", (30, 30), (200, 0, 0)).save(stream, format="PNG")
    return stream.getvalue()


def _first_run(tmp_path: Path, monkeypatch, replace: bool) -> tuple[Path, object, bytes, bytes]:
    """A Track 1 run whose calculation (``_run``) is substituted by a saved toy result, its figure A drawn through
    ``bindings.write_figure``; with ``replace``, B written over it after the finished result's checkpoint and before
    its figures' (the auditor's boundary). Its report written by the workbench's writer. (folder, request, A, B)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adroit.core.checkpoint import Checkpoint
    from adroit.evidence.results import load_result
    from adroit.orchestrator import runs, track1
    from tests.orchestrator.test_cw_recheck import _toy_study
    _, saved = load_result(_toy_study(tmp_path / "runs", monkeypatch, False) / "result.json")
    saved = saved.model_copy(update={"plots": [NAME]})
    monkeypatch.setattr("adroit.orchestrator.track1_identity.dependencies", lambda: {"software": "fixture"})
    monkeypatch.setattr(track1.plots, "direct_detection", lambda *args, **kwargs: None)   # reads the searches' data
    folder, b, drawn = tmp_path / "study", _replacement(), {}

    def calculation(request, folder, fetch, checkpoint):
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        bindings.write_figure(fig, folder / NAME, 50)
        plt.close(fig)
        drawn["a"] = (folder / NAME).read_bytes()
        return saved.model_copy(update={"request": request})
    real = Checkpoint.save

    def save(self, phase, key, value, **dated):         # with the dates a finished result is saved with (VI-05)
        real(self, phase, key, value, **dated)
        if replace and (phase, key) == ("finished", "result"):
            write_atomic(folder / NAME, b)                  # another process, before the figures' checkpoint
    monkeypatch.setattr(track1, "_run", calculation)
    monkeypatch.setattr(Checkpoint, "save", save)
    from adroit.core.durable import publishing
    with publishing(folder) as held:        # calculated and published under one hold, as ``runs.track1`` does (DF-01)
        first = track1.run(saved.request, folder, claim=held)
        monkeypatch.setattr(Checkpoint, "save", real)
        runs._write(folder, first, REPORT, "track1", "AUDIT checkpoint figure", claim=held)
    return folder, saved.request, drawn["a"], b


def _resumed(folder: Path, request, monkeypatch):
    """The run resumed as a fresh process resumes it (it has drawn no figure), its calculation forbidden, and its
    report written again by the workbench's writer: the report, as read against the result."""
    from adroit.orchestrator import runs, track1
    # a fresh process has drawn nothing: draws are kept only by the hold they were drawn under (DH-01), and none is held

    def forbidden(*args):
        raise AssertionError("a resume of a finished result calculates nothing")
    monkeypatch.setattr(track1, "_run", forbidden)
    from adroit.core.durable import publishing
    with publishing(folder) as held:        # as ``runs.track1`` resumes it (DF-01)
        resumed = track1.run(request, folder, resume=True, claim=held)
        runs._write(folder, resumed, REPORT, "track1", "AUDIT checkpoint figure", claim=held)
    return read_report(folder / "report.md", sha((folder / "result.json").read_bytes()))


def _exported_figure(folder: Path, destination: Path) -> bytes | None:
    """The figure the folder's bundle holds as the result's, where any; the bundle verifies."""
    archive.export_run(folder, destination)
    assert archive.verify_bundle(destination).valid
    _, files = archive.read_bundle(destination)
    return files.get(f"studies/n0/{NAME}")


def test_a_figure_replaced_before_its_checkpoint_is_never_bound_as_drawn_on_resume(tmp_path, monkeypatch):
    """DA-01, the auditor's case: A drawn, B written over it before the figures' checkpoint. The first report binds A and
    withholds B. Resumed in a fresh process, B is never bound, shown or exported as the result's figure: the figure is
    drawn again from the result, and that is what the report binds."""
    folder, request, a, b = _first_run(tmp_path, monkeypatch, replace=True)
    first = read_report(folder / "report.md", sha((folder / "result.json").read_bytes()))
    assert first.binding.figures[NAME] == sha(a) and figure(folder, NAME, first) is None
    found = _resumed(folder, request, monkeypatch)
    now = (folder / NAME).read_bytes()
    assert found.state == "bound" and found.binding.figures[NAME] != sha(b)
    assert now != b and figure(folder, NAME, found) == now          # drawn again from the result's scan
    assert _exported_figure(folder, tmp_path / "bundle.zip") == now


def test_an_older_checkpoint_s_figures_as_read_back_are_drawn_again_on_resume(tmp_path, monkeypatch):
    """DA-01, a checkpoint written before: its figures' digests read back from the files after the draw (B's, the
    replacement's). Resumed, they are not taken as the draw: the figure is drawn again, and B is never bound."""
    from adroit.orchestrator import track1

    def read_back(folder, names):                                  # as the checkpoint recorded them before
        return track1._Artifacts(hashes={name: sha((folder / name).read_bytes()) for name in names})
    real = getattr(track1, "_as_drawn", None)
    monkeypatch.setattr(track1, "_as_drawn", read_back, raising=False)
    folder, request, _, b = _first_run(tmp_path, monkeypatch, replace=True)
    if real is not None:
        monkeypatch.setattr(track1, "_as_drawn", real)
    found = _resumed(folder, request, monkeypatch)
    now = (folder / NAME).read_bytes()
    assert found.binding.figures[NAME] != sha(b) and now != b and figure(folder, NAME, found) == now


def test_an_unchanged_figure_is_kept_as_drawn_on_resume(tmp_path, monkeypatch):
    """DA-01's positive control: nothing replaced. Resumed, the figure is kept as drawn (not drawn again), bound,
    shown and exported."""
    folder, request, a, _ = _first_run(tmp_path, monkeypatch, replace=False)
    found = _resumed(folder, request, monkeypatch)
    assert (folder / NAME).read_bytes() == a and found.binding.figures[NAME] == sha(a)
    assert figure(folder, NAME, found) == a and _exported_figure(folder, tmp_path / "bundle.zip") == a


def test_a_review_packet_names_its_overlay_as_drawn(tmp_path, monkeypatch):
    """DA-01's class in the experimental review's packet: its overlay replaced after it was drawn and before the packet
    was written. The replacement is never recorded as what the researcher reviewed: the packet's rendering reads its
    overlay once, under its hold, against the digest its draw kept, and refuses (the auditor's DH recheck, DI-01, 2026-11-06:
    the page shows the bytes the packet's writer drew), writing no record; the verification then refuses the folder.
    (Before DI-01, the record named the overlay drawn, and the verification refused the replacement.)"""
    from adroit.constraints import experimental_review as er
    from tests.constraints.test_figure_anchors import ANCHORS, QUOTES, _figure_png, _verify, figure_curve
    monkeypatch.setattr("adroit.retrieval.experimental_ingestion.render_page", lambda *args: _figure_png())
    catalog, r = figure_curve(tmp_path, QUOTES[1:2], ANCHORS[1:2])
    real = er._source_overlay

    def overlay(*args):
        path = real(*args)
        write_atomic(Path(path), _replacement())               # another process, before the packet is written
        return path
    monkeypatch.setattr(er, "_source_overlay", overlay)
    with pytest.raises(ValueError, match="changed as it was drawn"):
        er.plot_packet(r.reference, "limit", tmp_path / "packet", catalog)
    assert not (tmp_path / "packet" / "review_packet.json").exists()
    with pytest.raises(ValueError, match="name the review packet you inspected"):
        _verify(catalog, r, packet=tmp_path / "packet")


# --- DA-03 ------------------------------------------------------------------------------------------------------


def _forged(destination: Path, replace: dict[str, bytes], edit=None, source: Path = FIXTURE) -> Path:
    """The bundle with members replaced and its manifest edited (``edit``), its hashes updated to match."""
    from tests.orchestrator.test_cz_recheck import _forged as forged
    return forged(source, destination, replace, edit)


def _other_parent(files: dict[str, bytes]) -> dict[str, bytes]:
    """B: a coherent other version of the version 1 bundle's parent (n1), its result and that result's evidence."""
    from adroit.evidence.results import typed
    data = json.loads(files["studies/n1/result.json"])
    data["created"] = "2026-10-30"
    content = json.dumps(data).encode()
    kind, result = typed(data, "signal")
    return {"studies/n1/result.json": content,
            "studies/n1/evidence.json": build.build(kind, result, sha(content)).model_dump_json().encode()}


def test_a_promotion_bundle_made_before_its_parent_was_named_verifies_as_it_did():
    """DA-03, the auditor's case: the untouched bundle of a promotion made at 1c039e0 (its manifest version 1: the parent
    linked, unnamed; the record naming no children, and its parent's digest). It verifies, as it did then."""
    assert sha(FIXTURE.read_bytes()) == "c2933fa17687721b90426b2d90243f2cbcc5168f82e8e304a6873cf677854a02"
    manifest, _ = archive.read_bundle(FIXTURE)
    assert manifest.schema_version == 1 and not manifest.nodes[0].parent and manifest.nodes[0].children == ["n1"]
    found = archive.verify_bundle(FIXTURE)
    assert found.valid and not found.issues


def test_a_version_1_bundle_whose_parent_was_replaced_does_not_verify(tmp_path):
    """DA-03's negative control: the version 1 bundle with its parent replaced by B, coherent, its hashes updated (as
    the export CZ-01 repaired had made it: the parent then saved, attached as the promotion's). It does not verify: a
    version 1 manifest's parent is read where its export linked it, and checked."""
    _, files = archive.read_bundle(FIXTURE)
    found = archive.verify_bundle(_forged(tmp_path / "parent.zip", _other_parent(files)))
    assert not found.valid and "promotion/parent mismatch" in found.issues[0]


@pytest.mark.parametrize("edit", ["links another study", "says version 3"])
def test_a_version_1_manifest_holds_only_what_its_export_wrote(tmp_path, edit):
    """DA-03: a version 1 manifest naming no parent and linking more studies than its record's children and its parent,
    or claiming a version that does not exist, does not verify. (A version 1 manifest naming a parent is dba8e6c's
    layout, checked by that name: the auditor's DA recheck, DB-01, in test_db_recheck.py.)"""
    def edited(manifest):
        if edit == "links another study":
            manifest.nodes[0].children.append("n1")
        else:
            manifest.schema_version = 3
    if edit == "says version 3":
        target = tmp_path / "v3.zip"
        with zipfile.ZipFile(FIXTURE) as source, zipfile.ZipFile(target, "w") as out:
            for name in source.namelist():
                content = source.read(name)
                if name == "manifest.json":
                    data = json.loads(content)
                    data["schema_version"] = 3
                    content = json.dumps(data).encode()
                out.writestr(name, content)
        assert not archive.verify_bundle(target).valid
        return
    found = archive.verify_bundle(_forged(tmp_path / "edited.zip", {}, edited))
    assert not found.valid and "invalid study graph" in found.issues[0]


def test_a_version_1_reading_of_a_new_bundle_keeps_its_edges(tmp_path, monkeypatch):
    """DA-03: a new bundle (version 2, its parent named) verifies; rewritten as version 1 wrote it (the name removed,
    the version 1), it reads the same parent and verifies; with the name removed and the version kept, the parent is
    linked unnamed, and it does not verify (CZ-01's forgery)."""
    from tests.orchestrator.test_cz_recheck import _child_run, _exported, _promote, _signal_versions
    folder = tmp_path / "runs" / "signal"
    a, _ = _signal_versions(folder, monkeypatch)
    _child_run(monkeypatch)
    manifest, _, root, _ = _exported(_promote(folder, "scalar @ 20", a), tmp_path / "a.zip")
    assert manifest.schema_version == 2 and root.parent and archive.verify_bundle(tmp_path / "a.zip").valid
    if root.children[-1] != root.parent:
        pytest.skip("the export links the parent after the children, as version 1 did")

    def as_version_1(manifest):
        manifest.schema_version, manifest.nodes[0].parent = 1, ""
    assert archive.verify_bundle(_forged(tmp_path / "v1.zip", {}, as_version_1, tmp_path / "a.zip")).valid

    def unnamed(manifest):
        manifest.nodes[0].parent = ""
    found = archive.verify_bundle(_forged(tmp_path / "unnamed.zip", {}, unnamed, tmp_path / "a.zip"))
    assert not found.valid and "promotion/parent mismatch" in found.issues[0]

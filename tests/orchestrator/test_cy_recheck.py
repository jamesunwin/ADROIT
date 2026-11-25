"""The auditor's CX recheck (the independent audit of 2026-11-01 (cx recheck), 2026-11-01), each finding through its real producer and
consumers:
- CY-01: a signal study reusing a saved Track 1 point kept only its path, so B reused between A at both captures left
  the run "captured", naming A, and its bundle verified;
- CY-02: Promote acted on the parent's result as read again by the child, not the version its page showed;
- CY-03: a study's report (and figures, and evidence) were read apart from its result, so a page or an export holding
  A showed or attached B's;
- CY-04 (a test's assurance) is in ``test_cx_recheck.test_the_export_writes_one_snapshot``.

The rendered pages are in ``tests/ui/test_cy_pages.py``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from adroit.core.durable import write_atomic
from adroit.core.evidence import EvidenceContext
from adroit.evidence import build
from tests.orchestrator.test_cx_recheck import _publish, _study


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- CY-01 ------------------------------------------------------------------------------------------------------

SAVED = EvidenceContext(origin="captured", identity="current", code_sha256="code")


def _reuse(tmp_path, monkeypatch, masses=(20,)):
    """A signal study's physical eligibility through ``signal.run``, with a selected saved Track 1 result to reuse:
    the fitted point fixed at each candidate's mass, the saved results' identity the run's, and no fresh point
    evaluation allowed (a tripwire). Returns (the selected result's path, A, B, the request): A and B are two valid
    saved versions at the same points, with the same captured identity, Ωh² 0.2 (A) and 0.456 (B)."""
    from adroit.model_building.audit import audit
    from adroit.orchestrator import physical_eligibility, signal
    from adroit.orchestrator.track1 import Track1Request, Track1Result
    from adroit.parameter_space import scan
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.scan import Axis, ScanRequest, ScanResult
    from tests.orchestrator.test_physical_eligibility import point_result, spec
    from tests.orchestrator.test_signal import ToyGermanium
    s = spec()
    cls, p, _ = classify(s)
    monkeypatch.setitem(signal.modules.SIGNAL_SEARCHES, "toy germanium", ToyGermanium)
    monkeypatch.setattr(physical_eligibility, "_current_context", lambda *a: SAVED)
    monkeypatch.setattr(physical_eligibility, "_physical",
                        lambda req, c, f, module, model: (cls, p.model_copy(update={"m_chi": c.mass_gev}), None, 0., 0.))

    def tripwire(*args, **kwargs):
        raise AssertionError("a fresh point evaluation: the saved point was not reused")
    monkeypatch.setattr(scan, "evaluate", tripwire)

    def saved(omega: float) -> tuple[bytes, bytes]:
        rows = [point_result(p.model_copy(update={"m_chi": float(m)}), omega=omega) for m in masses]
        plane = ScanResult(request=ScanRequest(model_class=cls, fixed=p, x=Axis(parameter="m_chi", low=10, high=40, n=2),
                                               y=Axis(parameter="g_chi", low=1, high=2, n=2)),
                           xs=[10, 40], ys=[1, 2], points=rows)
        work = tmp_path / f"work_{omega}" / "result.json"
        work.parent.mkdir()
        work.write_text(Track1Result(request=Track1Request(spec=s), audit=audit(s), scan=plane).model_dump_json())
        with patch.object(build, "finish", lambda c, read=None, consumed=None: c):
            build.save(work, "track1", SAVED)
        return work.read_bytes(), build.sidecar_path(work).read_bytes()
    a, b = saved(0.2), saved(0.456)
    path = tmp_path / "selected" / "result.json"
    path.parent.mkdir()
    _publish(path.parent, a)
    request = signal.SignalRequest(experiment="toy germanium", user_models=[signal.UserModel(spec=s, masses_gev=list(masses))],
                                   null_modules=[], toys=20, complementary=True, track1_results=[str(path)])
    return path, a, b, request


def _saved_signal(tmp_path, result, context, name="signal"):
    """The signal study saved through the real evidence producer (``build.save``: its reconciliation included)."""
    out = tmp_path / name
    out.mkdir()
    write_atomic(out / "result.json", result.model_dump_json(indent=1))
    return out, build.save(out / "result.json", "signal", context)


def test_a_point_reused_as_b_between_a_at_both_captures_is_named_and_not_captured(tmp_path, monkeypatch):
    """CY-01, the auditor's A→B→A: the run captures its selected Track 1 result as A, B is published, the reuse takes B's
    point (Ωh² 0.456), and A is restored before the evidence is saved. The point keeps the digests of the version it
    reused (B's), the evidence reads "changed during run" with a note naming the file, and the exported bundle says
    so; it is never "captured" with A. The positive controls, A or B unchanged throughout, are captured, each binding
    the version it reused."""
    from adroit.evidence.archive import export_run, read_bundle, verify_bundle
    from adroit.evidence.runtime import capture_request
    from adroit.orchestrator import signal
    path, a, b, request = _reuse(tmp_path, monkeypatch)
    context = capture_request(request)
    _publish(path.parent, b)
    result = signal.run(request)
    _publish(path.parent, a)
    row = next(iter(result.eligibility.values()))
    assert row.constraints_origin == "saved_exact_track1_point" and row.evaluation.omega_h2 == 0.456
    out, envelope = _saved_signal(tmp_path, result, context)
    assert envelope.context.origin == "changed_during_run"
    assert any(str(path.resolve()) in note and "consumed" in note for note in envelope.context.notes)
    assert (row.reused_result_sha256, row.reused_evidence_sha256) == (sha(b[0]), sha(b[1]))
    export_run(out, tmp_path / "aba.zip")
    checked = verify_bundle(tmp_path / "aba.zip")
    assert checked.valid and any("changed_during_run" in r for r in checked.reproduction_reasons)
    manifest, files = read_bundle(tmp_path / "aba.zip")
    saved = json.loads(files["studies/n0/result.json"])
    assert next(iter(saved["eligibility"].values()))["reused_result_sha256"] == sha(b[0])   # B named, never relabelled
    for version, label in ((a, "A"), (b, "B")):                 # the controls: unchanged throughout
        _publish(path.parent, version)
        context = capture_request(request)
        result = signal.run(request)
        row = next(iter(result.eligibility.values()))
        assert row.reused_result_sha256 == sha(version[0]), label
        _, envelope = _saved_signal(tmp_path, result, context, f"stable_{label}")
        assert envelope.context.origin == "captured" and not envelope.context.notes, label


def test_a_point_reused_in_two_versions_or_replaced_after_its_reuse_is_not_captured(tmp_path, monkeypatch):
    """CY-01: two candidates reuse the same selected file, B published between the two reuses: the result keeps both
    versions, and the evidence names the file read in two versions. A replaced by B after the reuse, B to the end: the
    run's inputs changed during it (and A's reuse no longer matches what the end holds); not captured either."""
    from adroit.evidence.runtime import capture_request
    from adroit.orchestrator import physical_eligibility, signal
    path, a, b, request = _reuse(tmp_path, monkeypatch, masses=(20, 30))
    real, reads = physical_eligibility._saved, []

    def then_b(*args):
        found = real(*args)
        if not reads:
            _publish(path.parent, b)
        reads.append(found)
        return found
    context = capture_request(request)
    with patch.object(physical_eligibility, "_saved", then_b):
        result = signal.run(request)
    _publish(path.parent, a)
    _, envelope = _saved_signal(tmp_path, result, context, "two")
    assert envelope.context.origin == "changed_during_run"
    assert any(str(path.resolve()) in note and "two versions" in note for note in envelope.context.notes)
    from adroit.evidence.results import inputs_read
    assert len(reads) == 2 and {r.reused_result_sha256 for r in result.eligibility.values()} == {sha(a[0]), sha(b[0])}
    assert inputs_read("signal", result)[str(path.resolve())] == ""
    context = capture_request(request)                            # A captured and reused; B from then to the end
    result = signal.run(request)
    _publish(path.parent, b)
    _, envelope = _saved_signal(tmp_path, result, context, "after")
    assert envelope.context.origin == "changed_during_run"


def test_a_result_saved_before_names_its_reused_path_and_no_version(tmp_path):
    """CY-01: a result saved before ADROIT kept the reused version keeps only the path: no version is made up for it
    (``inputs_read`` names none, so nothing reads the path now), and its report says the version is not recorded."""
    from adroit.core.eligibility import CandidateEligibility
    from adroit.evidence.results import inputs_read
    from adroit.orchestrator.signal import _constraint_origin
    old = CandidateEligibility(label="x", constraints_origin="saved_exact_track1_point",
                               reused_result=str(tmp_path / "t1" / "result.json"))
    assert "reused_result_sha256" not in old.model_dump(mode="json")      # older results' bytes unchanged
    assert inputs_read("signal", SimpleNamespace(eligibility={"x": old})) == {}
    assert _constraint_origin(old) == "saved Track 1 point of `t1`; the version reused is not recorded (saved before " \
                                      "ADROIT kept it)"
    new = old.model_copy(update={"reused_result_sha256": "ab" * 32, "reused_evidence_sha256": "cd" * 32})
    assert inputs_read("signal", SimpleNamespace(eligibility={"x": new})) == {
        new.reused_result: "ab" * 32, str(build.sidecar_path(Path(new.reused_result))): "cd" * 32}
    assert "SHA-256 abababababab…" in _constraint_origin(new)


# --- CY-02 ------------------------------------------------------------------------------------------------------


def _parent(tmp_path) -> tuple[Path, bytes, bytes]:
    """A saved Path 2 study (``test_workflow_acceptance._signal_study``) as A, and B: its class 0 now another
    candidate."""
    from tests.ui.test_workflow_acceptance import _signal_study
    folder = tmp_path / "runs" / "signal"
    _signal_study(folder)
    a = (folder / "result.json").read_bytes()
    data = json.loads(a)
    data["classes"] = {"scalar @ 10": 1, "scalar @ 20": 0}
    return folder, a, json.dumps(data).encode()


def test_a_promotion_refuses_a_parent_changed_since_its_candidates_were_chosen(tmp_path, monkeypatch):
    """CY-02: Promote's command carries the digest of the parent's result its page showed; with B published before the
    command reads the parent (before the click, or after the launch), nothing is promoted, reserved or computed: no
    child, no promotion record, refused naming it, by the command line too. With A, the promotion records the version
    it was taken from, and its report is bound to its record."""
    from typer.testing import CliRunner
    from adroit.orchestrator import cli, promote, runs
    folder, a, b = _parent(tmp_path)
    write_atomic(folder / "result.json", b)
    studied = []
    monkeypatch.setattr(promote, "candidates_of", lambda result: {label: SimpleNamespace(
        label=label, mass_gev=10.0, model="", card_id="", splitting_kev=0.0, values={}, isospin="s")
        for label in result.classes})
    monkeypatch.setattr(promote, "models_for", lambda result, c: [("simplified completion", SimpleNamespace(name="m"))])
    monkeypatch.setattr(promote, "_study", lambda *args, **kw: studied.append(args) or promote.Child(
        label=args[2].label, model="m", origin="o", folder=str(folder / "children" / "c")))
    with pytest.raises(promote.ParentChanged, match="has changed since its candidates were selected"):
        promote.promote(folder, ["class:0"], {}, parent_sha256=sha(a))
    out = CliRunner().invoke(cli.app, ["promote", str(folder), "class:0", "--parent-sha256", sha(a)])
    assert out.exit_code == 2 and "has changed" in out.output
    assert not studied and not (folder / "children").exists() and not list(folder.glob("promotion_*"))
    write_atomic(folder / "result.json", a)
    runs.promote(folder, ["scalar @ 10"], {}, None, 3, parent_sha256=sha(a))
    record = folder / "promotion_scalar_10.json"
    assert json.loads(record.read_bytes())["parent_sha256"] == sha(a) and [c[2].label for c in studied] == ["scalar @ 10"]
    report = (folder / "promotion_scalar_10.md").read_text()
    from adroit.evidence.bindings import binding
    assert binding(report).result_sha256 == sha(record.read_bytes()) and sha(a) in report


# --- CY-03 ------------------------------------------------------------------------------------------------------


def figured(tmp_path, monkeypatch) -> Path:
    """A Track 1 study written by the workbench's writer (``runs._write``) with a figure, its report embedding it."""
    import io
    from PIL import Image
    from adroit.evidence.results import load_result
    from adroit.orchestrator import runs
    from tests.orchestrator.test_cw_recheck import _toy_study
    folder = _toy_study(tmp_path / "runs", monkeypatch, False)
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(stream, format="PNG")
    (folder / "parameter_plane.png").write_bytes(stream.getvalue())
    _, result = load_result(folder / "result.json")
    runs._write(folder, result.model_copy(update={"plots": ["parameter_plane.png"]}),
                "# Track 1\n\nThe plane:\n\n![parameter_plane.png](parameter_plane.png)\n", "track1", "a toy plane")
    return folder


def test_a_report_is_bound_to_the_result_it_was_written_from_and_its_figures(tmp_path, monkeypatch):
    """CY-03: the workbench's writer binds each report to its result's bytes and its figures (``evidence.bindings``);
    read against that result it is "bound", each figure verified; against another, "other"; a report written before,
    "unbound"; a figure replaced since, not taken as the report's."""
    from adroit.evidence.bindings import bind, binding, figure, read_report, unbound
    folder = figured(tmp_path, monkeypatch)
    content = (folder / "result.json").read_bytes()
    found = read_report(folder / "report.md", sha(content))
    assert found.state == "bound" and set(found.binding.figures) >= {"parameter_plane.png"}
    assert figure(folder, "parameter_plane.png", found) == (folder / "parameter_plane.png").read_bytes()
    assert read_report(folder / "report.md", "0" * 64).state == "other"
    assert read_report(folder / "report.md", None).state == "other"
    text = unbound(found.text)
    assert "adroit-binding" not in text and binding(text) is None
    write_atomic(folder / "report.md", text)
    assert read_report(folder / "report.md", sha(content)).state == "unbound"
    write_atomic(folder / "report.md", found.data)
    (folder / "parameter_plane.png").write_bytes(b"\x89PNG another figure")
    assert figure(folder, "parameter_plane.png", read_report(folder / "report.md", sha(content))) is None
    again = bind(found.text, "f" * 64, folder, [])
    assert binding(again) == ("f" * 64, {}) and again.count("adroit-binding") == 1


def test_the_export_attaches_only_the_report_of_its_result(tmp_path, monkeypatch):
    """CY-03, the auditor's export case: A's result and evidence held, B's report (settled: nothing being replaced) is left
    out, naming it, never attached to A's node; a figure replaced since its report was written is left out too. A
    bundle whose report describes another result (or whose figure is not the report's) does not verify."""
    import io
    import zipfile
    from adroit.evidence.archive import export_run, read_bundle, verify_bundle
    folder, a, b = _study(tmp_path, monkeypatch)
    write_atomic(folder / "report.md", b[2])
    manifest = export_run(folder, tmp_path / "settled.zip")
    assert "studies/n0/report.md" not in read_bundle(tmp_path / "settled.zip")[1]
    assert any("report.md: of another version of the result" in w for w in manifest.warnings)
    assert verify_bundle(tmp_path / "settled.zip").valid
    write_atomic(folder / "report.md", a[2])
    export_run(folder, tmp_path / "a.zip")
    _, files = read_bundle(tmp_path / "a.zip")
    assert files["studies/n0/report.md"] == a[2]

    def forged(member: str, data: bytes) -> Path:
        with zipfile.ZipFile(tmp_path / "a.zip") as zipped:
            held = {n: zipped.read(n) for n in zipped.namelist()}
        held[member] = data
        listed = json.loads(held["manifest.json"])
        for artifact in listed["artifacts"]:
            if artifact["path"] == member:
                artifact.update(sha256=sha(data), size=len(data))
        held["manifest.json"] = json.dumps(listed).encode()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as zipped:
            for name, value in held.items():
                zipped.writestr(name, value)
        target = tmp_path / f"forged_{len(list(tmp_path.glob('forged_*')))}.zip"
        target.write_bytes(stream.getvalue())
        return target
    checked = verify_bundle(forged("studies/n0/report.md", b[2]))
    assert not checked.valid and "report/result mismatch" in checked.issues[0]


def test_a_figure_replaced_after_its_report_is_not_exported_or_downloaded_as_its_results(tmp_path, monkeypatch):
    """CY-03: a study written by the workbench (its report bound to its result and its figures), one figure replaced
    afterwards: the export and the figures download leave it out, saying so; restored, both include it."""
    from adroit.evidence.archive import export_run, read_bundle
    from adroit.evidence.exports import figures
    folder = figured(tmp_path, monkeypatch)
    original = (folder / "parameter_plane.png").read_bytes()
    (folder / "parameter_plane.png").write_bytes(original + b"\0")
    manifest = export_run(folder, tmp_path / "changed.zip")
    assert "studies/n0/parameter_plane.png" not in read_bundle(tmp_path / "changed.zip")[1]
    assert any("parameter_plane.png: not the figure the report" in w for w in manifest.warnings)
    shown = figures(folder / "result.json", formats=())
    assert "parameter_plane.png" not in shown and b"parameter_plane.png: left out" in shown["figures.txt"]
    (folder / "parameter_plane.png").write_bytes(original)
    export_run(folder, tmp_path / "restored.zip")
    assert read_bundle(tmp_path / "restored.zip")[1]["studies/n0/parameter_plane.png"] == original
    shown = figures(folder / "result.json", formats=())
    assert shown["parameter_plane.png"] == original and "figures.txt" not in shown


@pytest.mark.parametrize("kind", ["bundle", "tables", "figures", "references"])
def test_a_download_from_a_page_is_of_the_version_the_page_showed(tmp_path, monkeypatch, kind):
    """CY-03: each download from a study page carries the digest of the result the page showed: with B published
    since, refused, naming it; with A, made."""
    from adroit.evidence.version import Token
    from adroit.ui.exports import files
    folder, a, b = _study(tmp_path, monkeypatch)
    path = folder / "result.json"
    _publish(folder, b)
    with pytest.raises(ValueError, match="has changed since its page was opened"):
        files(kind, Token(str(path), result=sha(a[0])))
    _publish(folder, a)
    name, data = files(kind, Token(str(path), result=sha(a[0])))
    assert data


def test_a_reanalysis_from_a_page_requires_the_version_the_page_showed(tmp_path, monkeypatch):
    """CY-03: a reanalysis opened from a study page (its "Run again", or an update's "Prepare reanalysis") carries the
    digest of the result the page showed: B published since, nothing is drafted; A, the draft pins A."""
    from adroit.evidence.version import Token
    from adroit.library.personal import Catalog
    from adroit.orchestrator.reanalysis import Reanalysis
    folder, a, b = _study(tmp_path, monkeypatch)
    service = Reanalysis(Catalog(tmp_path / "models"))
    _publish(folder, b)
    with pytest.raises(ValueError, match="has changed since its page was opened"):
        service.open(str(folder / "result.json"), token=Token(str(folder / "result.json"), sha(a[0])))
    assert not (service.root / "drafts").exists() or not list((service.root / "drafts").iterdir())
    _publish(folder, a)
    shown = Token(str(folder / "result.json"), sha(a[0]))
    assert service.open(str(folder / "result.json"), token=shown).source_sha256 == sha(a[0])


def test_the_inputs_updated_card_reads_the_evidence_of_the_result_held(tmp_path, monkeypatch):
    """CY-03, the auditor's update-card case: A's cited record is as it is now; B alone records another source history. The
    card's input history is from the evidence of the page's version: B (result and evidence) published after the page
    resolved A, the card is A's, its evidence read with A's result (no update), never B's history beside A; A settled,
    no update; B settled, B's history (the control: the fixture shows it where it belongs). (Before the version handle,
    the card read the evidence apart, and B's found there was said "not known".)"""
    from adroit.constraints.database import records
    from adroit.core.evidence import EvidenceEnvelope, EvidenceObservation, SourceEvidence
    from adroit.orchestrator import revisit
    from adroit.parameter_space.scan import HIGGS_INVISIBLE
    folder, a, b = _study(tmp_path, monkeypatch)
    current = next(r for r in records() if r.id == HIGGS_INVISIBLE).model_dump(mode="json")

    def citing(version: tuple[bytes, ...], source: str) -> tuple[bytes, bytes]:
        envelope = EvidenceEnvelope.model_validate_json(version[1])
        context = envelope.context.model_copy(update={"sources": [SourceEvidence(
            id=HIGGS_INVISIBLE, version=str(current["version"]), metadata={**current, "source": source},
            review="not_required")]})
        cited = EvidenceObservation(subject_id="s", physical_input={}, observable="x", source_ids=[HIGGS_INVISIBLE])
        return version[0], envelope.model_copy(update={"context": context, "observations": [
            *envelope.observations, cited]}).model_dump_json().encode()
    from adroit.evidence.version import resolve
    a, b = citing(a, current["source"]), citing(b, "AUDIT B-only source history")
    _publish(folder, a)
    page = resolve(folder)                                   # the page's version: A
    _publish(folder, b)
    assert [u for u in revisit.for_study(tmp_path / "runs", page) if u.kind == "record"] == []
    _publish(folder, a)
    assert [u for u in revisit.for_study(tmp_path / "runs", resolve(folder)) if u.kind == "record"] == []
    _publish(folder, b)
    (update,) = [u for u in revisit.for_study(tmp_path / "runs", resolve(folder)) if u.kind == "record"]
    assert any("AUDIT B-only source history" in line for line in update.changes)


def _unbound(version: tuple[bytes, ...]) -> tuple[bytes, bytes, bytes]:
    """A version whose report records no binding, as every report written before CY-03 (and the auditor's control's)."""
    try:
        from adroit.evidence.bindings import unbound
    except ImportError:                     # before CY-03 no report recorded one: the tests run against that code too
        return version
    return version[0], version[1], unbound(version[2].decode()).encode()


def test_an_unbound_report_is_not_attached_to_a_result_replaced_while_it_was_read(tmp_path, monkeypatch):
    """CY-03, the auditor's export control, whose reports record no binding (as every report written before): B (result,
    evidence and report) published while the exporter reads A. A report recording no binding cannot be checked by its
    content, so the study's files are read again together (the version handle): the bundle is B's, its report B's, said
    to be unchecked; never A's result beside B's report. Still changing at every attempt, nothing is exported. Settled,
    A's report is attached as found, said to be unchecked. (Before the handle, a report still changing at the last
    attempt was left out of a bundle of the result; now the whole read is refused.)"""
    from adroit.evidence import version
    from adroit.evidence.archive import export_run, read_bundle, verify_bundle
    from tests.version_events import during_resolution
    folder, a, b = _study(tmp_path, monkeypatch)
    a, b = _unbound(a), _unbound(b)
    _publish(folder, a)
    with during_resolution("result.json", lambda: _publish(folder, b)) as done:
        manifest = export_run(folder, tmp_path / "once.zip")
    _, files = read_bundle(tmp_path / "once.zip")
    assert done and (files["studies/n0/result.json"], files["studies/n0/report.md"]) == (b[0], b[2])
    assert any("records no link to its result" in w for w in manifest.warnings)
    assert verify_bundle(tmp_path / "once.zip").valid
    _publish(folder, a)
    real, turn = version._read, [0]

    def always(path, limit=None):                       # another publication at every reading of the result
        found = real(path, limit)
        if Path(path).name == "result.json":
            turn[0] += 1
            _publish(folder, (a, b)[turn[0] % 2])
        return found
    with patch.object(version, "_read", always), pytest.raises(OSError, match="changed each time"):
        export_run(folder, tmp_path / "always.zip")
    assert not (tmp_path / "always.zip").exists()
    _publish(folder, a)
    manifest = export_run(folder, tmp_path / "settled.zip")
    assert read_bundle(tmp_path / "settled.zip")[1]["studies/n0/report.md"] == a[2]
    assert any("records no link to its result" in w for w in manifest.warnings)


def test_unbound_figures_are_downloaded_as_read_with_their_result(tmp_path, monkeypatch):
    """CY-03: a study whose report records no binding (as every report written before): its saved PNGs are downloaded as
    found, said to be unchecked. A figure and the result replaced while the download reads them, the study's files are
    read again together (the version handle): the figure downloaded is the one saved with the result it names, never
    the figure before beside the result after. (Before the handle, the figures were left out where the result was
    replaced while it was read.)"""
    from adroit.evidence import bindings
    from adroit.evidence.exports import figures
    from tests.version_events import during_resolution
    folder = figured(tmp_path, monkeypatch)
    write_atomic(folder / "report.md", bindings.unbound((folder / "report.md").read_text()))
    shown = figures(folder / "result.json", formats=())
    assert "parameter_plane.png" in shown and b"included as found" in shown["figures.txt"]
    replaced = (folder / "parameter_plane.png").read_bytes() + b"\0"

    def replace() -> None:
        write_atomic(folder / "parameter_plane.png", replaced)
        write_atomic(folder / "result.json", (folder / "result.json").read_bytes())    # another version of the file
    with during_resolution("report.md", replace) as done:
        shown = figures(folder / "result.json", formats=())
    assert done and shown["parameter_plane.png"] == replaced and b"included as found" in shown["figures.txt"]

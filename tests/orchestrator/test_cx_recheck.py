"""The auditor's CW recheck (the independent audit of 2026-10-31 (cw recheck), 2026-10-31), each finding through its real producer and
consumers:
- CX-01: a run's evidence was reconciled against the library read once more after its end capture, so a record put
  back to B in between left B's limits "captured" with A's data;
- CX-02: the consumers of a saved result read it once to parse it and again, with its evidence, to explain, export or
  continue it, so a result published between the reads showed A's prediction beside B's limit, exported a bundle of
  two versions, or failed a page (the rendered pages are in ``tests/ui/test_cx_snapshots.py``).

A swap between reads is made at the first open of the result: its handle is open, so that read is of the version
before, and B is then published atomically (result and evidence), as the auditor's controls did.
"""
from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from adroit.constraints import database, review_identity
from adroit.constraints.review_identity import version
from adroit.core.durable import write_atomic
from adroit.core.evidence import EvidenceContext, SourceEvidence
from adroit.evidence import build, runtime
from adroit.evidence.results import load_result
from adroit.orchestrator import exclusion, studies
from adroit.parameter_space.scan import HIGGS_INVISIBLE, INVISIBLE_H
from tests.orchestrator.test_cw_recheck import ICECUBE, _icecube, _linear_capture, _request, _toy_study

try:
    from adroit.evidence.bindings import bind
except ImportError:         # before the auditor's CX recheck (CY-03, 2026-11-01) a report recorded no binding: these tests
    def bind(report, result_sha256, folder, figures):      # run against that code too
        return report

# --- CX-01 ------------------------------------------------------------------------------------------------------


def test_a_record_put_back_after_the_end_capture_leaves_b_s_limits_changed(tmp_path, monkeypatch):
    """CX-01, the auditor's interleaving through ``exclusion.run``, ``build.save``, the export and its verification: the
    curve A at the start capture, B for the whole calculation, A at the end capture, and B again just after it (before
    the reconciliation had read the library once more). B's limits are kept with B's version, and the evidence and the
    bundle say the provenance is not certified, as in the ordinary A→B→A case; neither is "captured"."""
    from adroit.evidence.archive import export_run, verify_bundle
    path, record, reading, a, b, limit = _icecube(tmp_path, monkeypatch)
    _linear_capture(monkeypatch, limit)
    request = _request()
    real_capture = runtime.capture

    def end_capture(*args, **kwargs):
        captured = real_capture(*args, **kwargs)
        path.write_bytes(b)                          # B, between the end capture and anything read after it
        return captured
    with reading, patch.object(database, "usable", lambda *args, **kwargs: [record]):
        path.write_bytes(b)
        version_b = version(record)
        path.write_bytes(a)
        context = runtime.capture_request(request, experiments=False)
        path.write_bytes(b)
        result = exclusion.run(request)
        path.write_bytes(a)
        folder = tmp_path / "study"
        folder.mkdir()
        (folder / "result.json").write_text(result.model_dump_json(indent=1))
        ordinary = build.save(folder / "result.json", "exclusion", context=context)
        with patch.object(runtime, "capture", end_capture):
            raced = build.save(folder / "result.json", "exclusion", context=context)
        path.write_bytes(a)
        studies.record(folder, "exclusion", "CX-01")
        export_run(folder, tmp_path / "bundle.zip")
        bundle = verify_bundle(tmp_path / "bundle.zip")
    assert {t.record_version for t in result.telescopes} == {version_b}
    assert {t.channel: t.mu_up[0] for t in result.telescopes}["bb"] == pytest.approx(50 ** .5)      # B's numbers
    for envelope in (ordinary, raced):
        assert envelope.context.origin == "changed_during_run"
        assert any(ICECUBE in note and "provenance cannot certify" in note for note in envelope.context.notes)
    source = next(s for s in raced.context.sources if s.id == ICECUBE)
    assert source.data_sha256 == hashlib.sha256(a).hexdigest()           # the context names A's data, as captured
    assert bundle.valid and bundle.nodes[0].provenance == "changed_during_run"


def test_the_captured_version_is_the_records_version_from_what_the_context_holds(tmp_path, monkeypatch):
    """CX-01: each library record's version taken from a captured context (its metadata, and the data its digest
    names) is ``version(record)``: one formula. A scratch record captured as A gives A's version while its file is A,
    and none ("") once the file is B: the context's version is never another file's."""
    from adroit.constraints.review_identity import captured_version
    for source in runtime._sources():
        record = database.record(source.id)
        assert captured_version(source.metadata, source.data_sha256) == version(record), source.id
    path, record, reading, a, b, _ = _icecube(tmp_path, monkeypatch)
    with reading:
        source = next(s for s in runtime._sources() if s.id == ICECUBE)
        version_a = version(record)
        assert captured_version(source.metadata, source.data_sha256) == version_a != ""
        path.write_bytes(b)
        assert captured_version(source.metadata, source.data_sha256) == ""
        assert runtime.finish(runtime.capture_request(_request(), experiments=False),
                              {ICECUBE: version(record)}).origin == "captured"          # B captured, B read
        path.write_bytes(a)
    monkeypatch.setattr(review_identity, "PROJECT_ROOT", tmp_path / "elsewhere")
    assert captured_version(source.metadata, source.data_sha256) == ""                  # not a declared input


# --- CX-02 ------------------------------------------------------------------------------------------------------


@contextmanager
def _published_after_open(path: Path, publish=None, opens: list[str] | None = None, after: int = 1):
    """``publish()`` run once, just after ``path`` is opened for reading the ``after``-th time: its handle is open, so
    that read is of the version before. Every open of ``path`` and of its evidence for reading is noted in ``opens``."""
    real = io.open
    watched = {os.path.realpath(path): path.name, os.path.realpath(build.sidecar_path(path)): "evidence"}
    done: list[bool] = []
    seen: list[str] = []

    def opener(file, mode="r", *args, **kwargs):
        handle = real(file, mode, *args, **kwargs)
        if isinstance(file, (str, os.PathLike)) and "r" in mode and "+" not in mode:
            name = watched.get(os.path.realpath(file))
            if name:
                seen.append(name)
                if opens is not None:
                    opens.append(name)
            if name == path.name and publish is not None and not done and seen.count(name) == after:
                done.append(True)
                publish()
        return handle
    with patch.object(io, "open", opener), patch.object(builtins, "open", opener):
        yield done


def _versions(folder: Path) -> tuple[tuple[bytes, bytes, bytes], tuple[bytes, bytes, bytes]]:
    """A and B of one saved Track 1 study, each its result's bytes, its own evidence and its own report (bound to it,
    as ADROIT writes one: ``evidence.bindings``): at ``grid:0`` the invisible Higgs width allowed in A (prediction 0.05
    against the limit its evidence holds, 0.11), excluded in B (0.2 against 0.01). The prediction is the result's, the
    limit the evidence's: a point read across the two shows it; the report says "A report" or "B report"."""
    kind, result = load_result(folder / "result.json")

    def one(br: float, limit: float, excluded: bool, origin: str, name: str) -> tuple[bytes, bytes, bytes]:
        points = list(result.scan.points)
        points[0] = points[0].model_copy(update={"excluded": {INVISIBLE_H: excluded},
                                                 "values": {"BR(h → invisible)": br}})
        saved = result.model_copy(update={"scan": result.scan.model_copy(update={"points": points})})
        content = saved.model_dump_json(indent=1).encode()
        context = EvidenceContext(origin=origin, sources=[SourceEvidence(id=HIGGS_INVISIBLE,
                                                                         metadata={"data": {"br_limit": limit}})])
        envelope = build.build(kind, saved, hashlib.sha256(content).hexdigest(), context)
        report = bind(f"# Track 1\n\n{name} report: the saved {'excluded' if excluded else 'allowed'} point\n",
                      hashlib.sha256(content).hexdigest(), folder, [])
        return content, envelope.model_dump_json(indent=1).encode(), report.encode()
    return one(0.05, 0.11, False, "legacy_unknown", "A"), one(0.2, 0.01, True, "changed_during_run", "B")


def _publish(folder: Path, version: tuple[bytes, ...]) -> None:
    """A version published as its writer publishes it: the result, its evidence, then its report (where it has one)."""
    write_atomic(folder / "result.json", version[0])
    write_atomic(build.sidecar_path(folder / "result.json"), version[1])
    if len(version) > 2:
        write_atomic(folder / "report.md", version[2])


def _study(tmp_path, monkeypatch):
    folder = _toy_study(tmp_path / "runs", monkeypatch, False)
    a, b = _versions(folder)
    _publish(folder, a)
    return folder, a, b


def _invisible(found) -> tuple:
    c = next(c for c in found.comparisons if c.constraint.startswith("invisible Higgs"))
    return found.row.status, c.group, c.prediction, c.limit


A_SHOWN = ("pending", "allowed", 0.05, 0.11)
B_SHOWN = ("excluded", "excluded", 0.2, 0.01)


def test_the_point_explanation_is_of_one_snapshot(tmp_path, monkeypatch):
    """CX-02, the auditor's case: the point's explanation while B (result and evidence) is published just after the result is
    first read. Its status, group, prediction and limit are all B's (the result read again, since it changed before its
    evidence was read), never A's prediction beside B's limit; published after the snapshot, all A's. One read each of
    the result and its evidence."""
    from adroit.evidence.points import explain
    folder, a, b = _study(tmp_path, monkeypatch)
    path = folder / "result.json"
    opens: list[str] = []
    with _published_after_open(path, opens=opens):
        assert _invisible(explain(path, "grid:0")) == A_SHOWN
    assert opens == ["result.json", "evidence"]
    with _published_after_open(path, lambda: _publish(folder, b)) as done:
        assert _invisible(explain(path, "grid:0")) == B_SHOWN
    assert done
    _publish(folder, a)
    from tests.version_events import after_resolution
    with after_resolution(lambda: _publish(folder, b)) as calls:      # just after the point's version is resolved
        assert _invisible(explain(path, "grid:0")) == A_SHOWN
    assert len(calls) == 1                               # the publication after the snapshot happened, once


def test_a_result_and_evidence_that_disagree_are_refused_not_joined(tmp_path, monkeypatch):
    """CX-02: A's result beside B's evidence, settled (no replacement under way), is refused by every consumer, naming
    the mismatch; the shared reader reads it twice at most, never joining them."""
    from adroit.evidence.exports import table
    from adroit.evidence.points import explain
    folder, a, b = _study(tmp_path, monkeypatch)
    write_atomic(build.sidecar_path(folder / "result.json"), b[1])
    for consumer in (lambda p: explain(p, "grid:0"), table, build.read):
        with pytest.raises(ValueError, match="evidence/result content mismatch"):
            consumer(folder / "result.json")


def test_the_export_writes_one_snapshot(tmp_path, monkeypatch):
    """CX-02, the auditor's export case, and CY-03's: B (result, evidence and report) published just after the exporter
    first reads the result, just after it reads the evidence (before the report), or just after it has resolved its
    version. The export returns a bundle that verifies, its result, evidence and report one version: B, B (its files
    read again together, the version handle), or A; none of two. Each publication is checked to have happened once
    (the auditor's CX recheck, CY-04, 2026-11-01: a patch at a name the exporter does not call never ran)."""
    from adroit.evidence.archive import export_run, read_bundle, verify_bundle
    from tests.version_events import after_resolution, during_resolution
    folder, a, b = _study(tmp_path, monkeypatch)
    path = folder / "result.json"

    def one_version(zipped: str, written: tuple[bytes, bytes, bytes]) -> None:
        checked = verify_bundle(tmp_path / zipped)
        assert checked.valid, checked.issues
        manifest, files = read_bundle(tmp_path / zipped)
        node = manifest.nodes[0]
        assert files[node.result_path] == written[0]
        assert json.loads(files[node.evidence_path])["result_sha256"] == hashlib.sha256(written[0]).hexdigest()
        assert files["studies/n0/report.md"] == written[2]
    with _published_after_open(path, lambda: _publish(folder, b)) as done:
        export_run(folder, tmp_path / "during.zip")
    assert done
    one_version("during.zip", b)
    _publish(folder, a)
    with during_resolution("result.evidence.json", lambda: _publish(folder, b)) as done:
        export_run(folder, tmp_path / "after_evidence.zip")
    assert done
    one_version("after_evidence.zip", b)
    _publish(folder, a)
    with after_resolution(lambda: _publish(folder, b)) as calls:
        export_run(folder, tmp_path / "after_resolution.zip")
    assert len(calls) == 1
    one_version("after_resolution.zip", a)


def test_the_downloaded_tables_are_of_one_snapshot(tmp_path, monkeypatch):
    """CX-02: the points table (``exports.table``: each point's status from the result, each comparison's observation
    from its evidence) while B is published just after the result is first read: ``grid:0``'s status and its invisible
    width's row are B's together."""
    from adroit.evidence.exports import table
    folder, a, b = _study(tmp_path, monkeypatch)
    with _published_after_open(folder / "result.json", lambda: _publish(folder, b)) as done:
        rows = table(folder / "result.json")
    assert done
    row = next(r for r in rows if r["point"] == "grid:0" and r["observable"].startswith("invisible Higgs"))
    assert (row["status"], row["excluded"]) == ("excluded", "true")


def test_the_review_queue_reads_each_result_with_its_own_evidence(tmp_path, monkeypatch):
    """CX-02: the review queue's loader, B published just after the result is first read: its evidence and result are
    one version (the evidence's summary is the result's)."""
    from adroit.constraints.review_queue import load_selected
    from adroit.evidence.results import summary_matches, typed
    folder, a, b = _study(tmp_path, monkeypatch)
    with _published_after_open(folder / "result.json", lambda: _publish(folder, b)) as done:
        [selected] = load_selected(folder / "result.json")
    assert done
    kind, result = typed(selected.result, selected.envelope.workflow)
    assert summary_matches(kind, selected.envelope.summary, result)
    assert selected.envelope.context.origin == "changed_during_run"
    assert selected.result["scan"]["points"][0]["values"] == {"BR(h → invisible)": 0.2}


@pytest.mark.parametrize("after", [1, 2, 3, 4])
def test_a_reanalysis_draft_pins_one_snapshot(tmp_path, monkeypatch, after):
    """CX-02: a reanalysis draft's source (``Reanalysis._source``), B (another request, its own evidence) published just
    after the result's ``after``-th read, whichever read that is: the digests and the request it pins are all A's or all
    B's (the shared reader reads once, and again only where the result changed meanwhile). The result alone replaced
    (no evidence of its own): refused, never pinning its request and digest beside A's evidence."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.reanalysis import Reanalysis
    folder = _toy_study(tmp_path / "runs", monkeypatch, False)
    a, _ = _versions(folder)
    _publish(folder, a)
    path = folder / "result.json"
    data = json.loads(a[0])
    data["request"]["literature"] = not data["request"]["literature"]
    kind, result = load_result(folder / "result.json")
    content = json.dumps(data).encode()
    b = content, build.build(kind, type(result).model_validate(data), hashlib.sha256(content).hexdigest(),
                             EvidenceContext(origin="legacy_unknown")).model_dump_json().encode()
    service = Reanalysis(Catalog(tmp_path / "models"))
    with _published_after_open(path, lambda: _publish(folder, b), after=after):
        kind, digest, evidence, workflow, request = service._source(str(path))
    assert (kind, workflow) == ("study", "track1")
    pinned = {name: (hashlib.sha256(v[0]).hexdigest(), hashlib.sha256(v[1]).hexdigest(), json.loads(v[0])["request"])
              for name, v in (("A", a), ("B", b))}
    assert (digest, evidence, request) in pinned.values()
    _publish(folder, a)
    data = json.loads(a[0])
    data["request"]["literature"] = not data["request"]["literature"]
    with _published_after_open(path, lambda: write_atomic(path, json.dumps(data))) as done:
        with pytest.raises(ValueError, match="evidence/result"):
            service._source(str(path))
    assert done


def test_physical_eligibility_reuses_a_saved_point_only_with_its_own_evidence(tmp_path, monkeypatch):
    """CX-02: Path 2's reuse of a saved Track 1 point (``physical_eligibility._saved``). A is reusable (captured,
    current); B, published just after the result is first read, has another point value and stale evidence. The point
    is A's with A's evidence, or not reused: never B's point on A's evidence."""
    from adroit.orchestrator import physical_eligibility as eligibility
    from adroit.orchestrator import signal
    from adroit.parameter_space.classify import classify
    from tests.orchestrator.test_physical_eligibility import point_result, spec
    from adroit.model_building.audit import audit
    from adroit.orchestrator.track1 import Track1Request, Track1Result
    from adroit.parameter_space.scan import Axis, ScanRequest, ScanResult
    s = spec()
    cls, p, _ = classify(s)
    user = signal.UserModel(spec=s)
    current = EvidenceContext(origin="captured", identity="current", code_sha256="code")
    monkeypatch.setattr(build, "finish", lambda context, read=None, consumed=None: context)

    def saved(omega: float, context: EvidenceContext) -> tuple[bytes, bytes]:
        row = point_result(p).model_copy(update={"omega_h2": omega})
        scan = ScanResult(request=ScanRequest(model_class=cls, fixed=p, x=Axis(parameter="m_chi", low=20, high=30, n=2),
                                              y=Axis(parameter="g_chi", low=1, high=2, n=2)),
                          xs=[20, 30], ys=[1, 2], points=[row])
        work = tmp_path / f"work_{omega}" / "result.json"
        work.parent.mkdir()
        work.write_text(Track1Result(request=Track1Request(spec=s), audit=audit(s), scan=scan).model_dump_json())
        build.save(work, "track1", context)
        return work.read_bytes(), build.sidecar_path(work).read_bytes()
    a = saved(0.12, current)
    b = saved(0.2, current.model_copy(update={"identity": "old"}))
    path = tmp_path / "study" / "result.json"
    path.parent.mkdir()
    _publish(path.parent, a)
    request = signal.SignalRequest(experiment="toy", user_models=[user], track1_results=[str(path)])
    assert eligibility._saved(request, user, cls, p, current)[0].omega_h2 == 0.12
    with _published_after_open(path, lambda: _publish(path.parent, b)) as done:
        row, reused, _, notes = eligibility._saved(request, user, cls, p, current)
    assert done
    assert row is None and not reused and notes          # B, read with its own (stale) evidence: not reused


def test_the_shared_reader_reads_the_result_and_its_evidence_once_each(tmp_path, monkeypatch):
    """CX-02: every consumer of a saved result with its evidence reads ``result.json`` once and its evidence once
    (``build.read_saved``): the point, the tables, the references with the request, the export and the review queue."""
    from adroit.constraints.review_queue import load_selected
    from adroit.evidence import exports
    from adroit.evidence.archive import export_run
    from adroit.evidence.points import explain
    from adroit.ui.exports import files
    folder, a, b = _study(tmp_path, monkeypatch)
    path = folder / "result.json"
    consumers = {"the point": lambda: explain(path, "grid:0"), "the tables": lambda: exports.table(path),
                 "the references and the request": lambda: files("references", path),
                 "the export": lambda: export_run(folder, tmp_path / "once.zip"),
                 "the review queue": lambda: load_selected(path)}
    for name, consumer in consumers.items():
        opens: list[str] = []
        with _published_after_open(path, opens=opens):
            consumer()
        assert opens == ["result.json", "evidence"], name

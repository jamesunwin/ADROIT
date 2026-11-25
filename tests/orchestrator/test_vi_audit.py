"""The auditor's version-identity audit (2026-11-03), VI-01 to VI-05: one resolved version of a study, used for everything
shown, downloaded, exported or continued from it. VI-01: a study record, kept apart from its result, had given a page,
a download and a verified bundle one result with another publication's title and cost. VI-02: a point link and the
classic page's result link had named a folder, not a version, and opened another. VI-03: the result's digest alone had
let downloads and a reanalysis take replaced evidence, a replaced report and its figures. VI-04: the review queue had
followed a promotion's paths, not the versions its record names, and lost a replaced child's review tasks. VI-05: a
resume had dated the checkpoint it restored with another publication's dates. Each result here is a typed saved result
(a small Track 1 grid, a native fit), written by the production writers; nothing is calculated."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from adroit.core.durable import write_atomic
from adroit.evidence import archive, bindings, build, exports
from adroit.orchestrator import runs, studies


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def versions(folder: Path):
    """A and B, two valid Track 1 results of one folder (the auditor's fixture): B's grid is elsewhere, so ``grid:0`` names
    another physical point, and its root and status differ."""
    from adroit.evidence.results import load_result
    from tests.evidence.test_points import _result
    folder.mkdir(parents=True, exist_ok=True)
    _, a = load_result(_result(folder))
    b = a.model_copy(deep=True)
    b.scan.xs, b.scan.ys = [1900, 2000], [900, 1000]
    b.scan.request.x.low, b.scan.request.x.high = 1900, 2000
    b.scan.request.y.low, b.scan.request.y.high = 900, 1000
    b.request.x, b.request.y = b.scan.request.x.model_copy(), b.scan.request.y.model_copy()
    for p, (m_chi, m_med) in zip(b.scan.points, [(900, 1900), (900, 2000), (1000, 1900), (1000, 2000)]):
        p.point.m_chi, p.point.m_med = m_chi, m_med
    crossing = b.verdict.crossings[0]
    crossing.point.m_chi, crossing.point.m_med = 950, 1950
    crossing.evaluation.point = crossing.point.model_copy()
    row = b.scan.points[0]
    row.excluded, row.pending, row.ratios, row.values = {"direct detection": False}, [], {"direct detection": .1}, \
        {"direct detection": .1}
    a.request.spec.name, b.request.spec.name = "A model", "B model"
    return a, b


def publish(folder: Path, result, label: str, cost: float = 0.0) -> bytes:
    """``result`` published at ``folder`` by the production writer (``runs._write``: its result, evidence, bound report
    and study record), as ``label``; the bytes published."""
    runs._write(folder, result, f"# {label} report\n\n{label} report body\n", "track1", f"{label} study",
                {"fixture_model": label}, cost_usd=cost)
    return (folder / "result.json").read_bytes()


# --- VI-01: the study record ------------------------------------------------------------------------------------


def test_a_study_record_names_the_result_its_writer_published_and_keeps_it_through_navigation(tmp_path):
    """VI-01: the writer records the digest of the bytes it published; a child recorded under the study changes its
    navigation (its children), never which result it describes."""
    folder = tmp_path / "study"
    a, _ = versions(folder)
    content = publish(folder, a, "A", 1.25)
    assert studies.load(folder).result_sha256 == sha(content)
    child, _ = versions(folder / "children" / "c")
    runs._write(folder / "children" / "c", child, "# child\n", "track1", "child", parent=folder)
    record = studies.load(folder)
    assert record.children and record.title == "A study"
    assert studies.binding(record, content) == "bound"


@pytest.mark.parametrize("case", ["stable", "replaced after the result was held", "a record written before"])
def test_the_references_download_attaches_only_the_record_of_the_result_it_holds(tmp_path, case):
    """VI-01, the auditor's reference download: A held, then B published whole. The study record attached is the one that
    names A; B's is left out, saying so, never attached as A's. A record written before records named their result is
    attached as found, saying so."""
    folder = tmp_path / "study"
    a, b = versions(folder)
    publish(folder, a, "A", 1.25)
    if case == "a record written before":
        record = studies.load(folder)
        studies.save(record.model_copy(update={"result_sha256": ""}))
    from adroit.evidence.version import resolve
    held = resolve(folder)                  # the version the download is made of: its record read with its result
    if case == "replaced after the result was held":
        publish(folder, b, "B", 9.5)
    files = exports.request(held)
    assert json.loads(files["request.json"])["spec"]["name"] == "A model"
    record = json.loads(files["study.json"])            # A's record, read with A's result: never B's beside A
    assert record["title"] == "A study" and record["cost_usd"] == 1.25
    assert ("study_record.txt" in files) == (case == "a record written before")


def _bundle(folder: Path, out: Path, b=None):
    """The production export of ``folder``'s result; with ``b``, B published whole once A is held (the auditor's
    interleaving: just after the export has resolved its version, ``tests.version_events``)."""
    from tests.version_events import after_resolution
    with after_resolution(lambda: publish(folder, b, "B", 9.5) if b is not None else None):
        return archive.export_run(folder / "result.json", out)


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "replaced after the result was held"])
def test_a_bundle_attaches_only_the_record_of_the_result_it_holds(tmp_path, replace):
    """VI-01, the auditor's bundle: A held, then B published whole. The bundle holds A's result with A's study record, read
    with it (the version handle), never B's record beside A's result, and verifies; unraced, A's record, naming A, is
    attached. (Before the handle, the record was read after the result, and B's, found there, was left out.)"""
    folder = tmp_path / "study"
    a, b = versions(folder)
    publish(folder, a, "A", 1.25)
    manifest = _bundle(folder, tmp_path / "out.zip", b if replace else None)
    with zipfile.ZipFile(tmp_path / "out.zip") as z:
        result = z.read("studies/n0/result.json")
        record = json.loads(z.read("studies/n0/study.json")) if "studies/n0/study.json" in z.namelist() else None
    assert json.loads(result)["request"]["spec"]["name"] == "A model"
    assert record["title"] == "A study" and record["result_sha256"] == sha(result)
    assert not any("study.json" in w for w in manifest.warnings)
    assert archive.verify_bundle(tmp_path / "out.zip").valid


def test_a_bundle_whose_study_record_describes_another_result_does_not_verify(tmp_path):
    """VI-01: a bundle with B's record (naming B) beside A's result, its hashes updated, does not verify; one with A's
    record does. A record naming none (written before) is not checked."""
    from tests.orchestrator.test_cz_recheck import _forged
    folder = tmp_path / "study"
    a, b = versions(folder)
    publish(folder, a, "A", 1.25)
    _bundle(folder, tmp_path / "a.zip")
    other = tmp_path / "other"
    publish(other, b, "B", 9.5)
    forged = _forged(tmp_path / "a.zip", tmp_path / "forged.zip", {"studies/n0/study.json": (other / "study.json")
                                                                   .read_bytes()})
    found = archive.verify_bundle(forged)
    assert not found.valid and "study record/result mismatch" in found.issues[0]
    legacy = json.loads((other / "study.json").read_bytes())
    legacy.pop("result_sha256")
    unbound = _forged(tmp_path / "a.zip", tmp_path / "legacy.zip", {"studies/n0/study.json": json.dumps(legacy)
                                                                    .encode()})
    assert archive.verify_bundle(unbound).valid


def test_an_untouched_export_whose_records_name_their_results_refuses_another_record(tmp_path):
    """VI-01, on the repairs' own export (``tests/fixtures/bundles/promotion_v2_children_3f00efc.zip``): a child's study
    record replaced by its sibling's, which names the sibling's result, the hashes updated, does not verify."""
    from tests.evidence.test_bundle_formats import BUNDLES
    from tests.orchestrator.test_cz_recheck import _forged
    source = BUNDLES / "promotion_v2_children_3f00efc.zip"
    _, files = archive.read_bundle(source)
    forged = _forged(source, tmp_path / "swapped.zip", {"studies/n1/study.json": files["studies/n2/study.json"]})
    found = archive.verify_bundle(forged)
    assert not found.valid and "studies/n1/study.json describes another version" in found.issues[0]


def test_history_facts_are_of_one_publication_or_name_the_mismatch(tmp_path):
    """VI-01, the auditor's history facts: the record listed is A's, and B has been published whole since: the facts are
    read again as B's (B's title, B's model). With A's record written back over B's publication, the facts name the
    mismatch, and A's models are not taken as B's result's."""
    from adroit.orchestrator.annotations import facts
    folder = tmp_path / "runs" / "study"
    a, b = versions(folder)
    publish(folder, a, "A", 1.25)
    old = studies.load(folder)
    publish(folder, b, "B", 9.5)
    found = facts(tmp_path / "runs", old)
    assert (found.title, found.models, found.damage) == ("B study", ["B model"], "")
    studies.save(old.model_copy(update={"model_references": ["catalog:A"]}))
    found = facts(tmp_path / "runs", studies.load(folder))
    assert "another version" in found.damage and found.models == ["B model"]


def test_the_setup_estimate_leaves_out_a_record_of_another_result(tmp_path):
    """VI-01, the auditor's estimate: A's record (60 s) beside B's result of twice A's grid gives no rate; A's own record and
    result give A's (four points, 60 s)."""
    from adroit.orchestrator.setup_check import estimate
    root = tmp_path / "runs"
    folder = root / "study"
    a, b = versions(folder)
    large = b.model_copy(deep=True)
    large.scan.points = [p.model_copy(deep=True) for p in b.scan.points] * 2
    publish(folder, a, "A")
    dated = studies.load(folder).model_copy(update={"calculation_started_at": "2026-11-01T00:00:00+00:00",
                                                    "calculation_completed_at": "2026-11-01T00:01:00+00:00"})
    studies.save(dated)
    assert estimate("track1", a.class_name, 4, root)[0] == 60
    write_atomic(folder / "result.json", large.model_dump_json(indent=1))
    assert estimate("track1", a.class_name, 4, root)[0] is None


# --- VI-02: point and classic links ------------------------------------------------------------------------------


def test_a_point_chosen_on_one_version_opens_on_it_or_is_refused(tmp_path):
    """VI-02, the auditor's point navigation: grid:0 chosen on A (50, 500, excluded); B published. The explanation asked for
    as A's is refused, never B's grid:0 (900, 1900) under A's choice; asked for as B's, or without a version (the
    command line's fresh selection), B's."""
    from adroit.evidence.points import CHANGED, explain
    from adroit.evidence.version import Token
    folder = tmp_path / "study"
    a, b = versions(folder)
    held = Token(str(folder / "result.json"), result=sha(publish(folder, a, "A")))
    assert explain(held, "grid:0").row.coordinates["m_chi"] == 50
    now = Token(str(folder / "result.json"), result=sha(publish(folder, b, "B")))
    with pytest.raises(ValueError, match="changed since the point was chosen"):
        explain(held, "grid:0")
    assert CHANGED.startswith("this study's result has changed")
    assert explain(now, "grid:0").row.coordinates["m_chi"] == 900
    assert explain(folder / "result.json", "grid:0").row.coordinates["m_chi"] == 900


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "replaced after the page was shown"])
def test_the_classic_result_link_sends_the_version_its_page_showed_or_refuses(tmp_path, replace):
    """VI-02, the auditor's classic download: the run page shows A's report and links to A's result; B published before the
    click. The link sends A, or refuses with 409 Conflict; never B under A's page."""
    from http import HTTPStatus
    from types import SimpleNamespace
    from adroit.workbench import pages, server
    from adroit.workbench.jobs import Job
    folder = tmp_path / "runs" / "job1"
    a, b = versions(folder)
    content = publish(folder, a, "A")
    html = pages.job_page(Job(id="job1", kind="track1", title="fixture"), *server.report_view(folder))
    assert "A report body" in html
    link = html.split("href='")[1].split("'")[0].replace("&amp;", "&")
    assert link == f"/file/job1/result.json?sha256={sha(content)}"
    if replace:
        publish(folder, b, "B")
    data, status, _ = server.route(SimpleNamespace(runs_dir=tmp_path / "runs"), link)
    if replace:
        assert status is HTTPStatus.CONFLICT and b"changed since its page was shown" in data.encode()
    else:
        assert (data, status) == (content, HTTPStatus.OK)


# --- VI-03: evidence and presentation ----------------------------------------------------------------------------


def _evidence(path: Path, result, label: str) -> str:
    """A valid synthetic evidence of ``result`` naming source ``label`` (the auditor's), the result's bytes unchanged; its
    identity (``build.evidence_identity``)."""
    from adroit.core.evidence import EvidenceContext, SourceEvidence
    context = EvidenceContext(origin="legacy_unknown", notes=[f"Synthetic context {label}"], sources=[SourceEvidence(
        id="atlas-2301.10731-hinv", reference=f"Synthetic source {label}", version=label, review="unreviewed")])
    content = path.read_bytes()
    write_atomic(build.sidecar_path(path), build.build("track1", result, sha(content), context).model_dump_json())
    return build.evidence_identity(path, content)


@pytest.mark.parametrize("kind", ["references", "tables", "bundle"])
@pytest.mark.parametrize("replace", [False, True], ids=["stable", "evidence replaced, the result the same"])
def test_downloads_keep_the_evidence_their_page_read(tmp_path, kind, replace):
    """VI-03, the auditor's case: the page read A's evidence; B's (another source) written beside the same result bytes
    before the click. Each download holding the evidence is refused, saying the evidence changed; unraced, it holds
    A's."""
    from adroit.evidence.version import Token
    from adroit.ui.exports import files
    folder = tmp_path / "study"
    a, _ = versions(folder)
    held = sha(publish(folder, a, "A"))
    token = _evidence(folder / "result.json", a, "A")
    if replace:
        _evidence(folder / "result.json", a, "B")
        with pytest.raises(ValueError, match="evidence has changed"):
            files(kind, Token(str(folder / "result.json"), result=held, evidence=token))
        return
    name, data = files(kind, Token(str(folder / "result.json"), result=held, evidence=token))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        text = b"".join(z.read(n) for n in z.namelist())
    assert b"Synthetic source A" in text or kind == "tables"


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "report replaced, the result the same"])
def test_the_figures_download_keeps_the_report_its_page_read(tmp_path, replace):
    """VI-03, the auditor's presentation case: the page read report A, bound to the result and naming figure A; report B
    and figure B written since, the result the same. The figures download is refused, saying the report changed;
    unraced, it holds figure A."""
    from adroit.evidence.version import Token
    folder = tmp_path / "study"
    a, _ = versions(folder)
    digest = sha(publish(folder, a, "A"))

    def presentation(label: str) -> str:
        data = f"SIMULATED FIGURE {label}".encode()
        write_atomic(folder / "preview.png", data)
        bindings.drawn(folder / "preview.png", sha(data))
        write_atomic(folder / "report.md", bindings.bind(f"Presentation {label}", digest, folder, ["preview.png"]))
        return bindings.presentation(bindings.read_report(folder / "report.md", digest))
    shown = presentation("A")
    if replace:
        presentation("B")
        with pytest.raises(ValueError, match="report has changed"):
            exports.figures(Token(str(folder / "result.json"), result=digest, presentation=shown), formats=())
        return
    assert exports.figures(Token(str(folder / "result.json"), result=digest, presentation=shown),
                           formats=())["preview.png"] == b"SIMULATED FIGURE A"


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "evidence replaced, the result the same"])
def test_a_reanalysis_drafts_from_the_evidence_its_page_read(tmp_path, replace):
    """VI-03, the auditor's reanalysis case: the draft requires the evidence the page read, as it requires the result."""
    from adroit.evidence.version import Token
    from adroit.library.personal import Catalog
    from adroit.orchestrator.reanalysis import Reanalysis
    folder = tmp_path / "study"
    a, _ = versions(folder)
    held = sha(publish(folder, a, "A"))
    token = _evidence(folder / "result.json", a, "A")
    service = Reanalysis(Catalog(tmp_path / "catalog"))
    if replace:
        _evidence(folder / "result.json", a, "B")
        with pytest.raises(ValueError, match="evidence has changed"):
            service.open(str(folder / "result.json"), token=Token(str(folder / "result.json"), held, token))
        return
    shown = Token(str(folder / "result.json"), held, token)
    assert service.open(str(folder / "result.json"), token=shown).source_evidence_sha256 == token


# --- VI-04: a promotion's graph ----------------------------------------------------------------------------------


def _promotion(root: Path, recorded: bool = True):
    """The auditor's review graph: a promotion record naming its parent (a signal result) and child A (a Track 1 result with
    a pending thermal root), with their digests where ``recorded``; and B, a valid other child with no thermal root."""
    from adroit.inference.dm_tournament import run as empty_tournament
    from adroit.orchestrator.promote import Child, Promotion
    from adroit.orchestrator.signal import SignalRequest, SignalResult
    root.mkdir(parents=True)
    parent = SignalResult(request=SignalRequest(experiment="synthetic fixture"), fits=[], classes={}, n_classes=0,
                          max_local_z=0, global_p_toys=1, global_p_closed_form=None, global_z=0, combinations=[],
                          tournament=empty_tournament([]), separations=[])
    build.publish(root / "result.json", parent.model_dump_json().encode(), parent, lambda e: "Parent",
                  workflow="signal")
    a, b = versions(root / "child")
    child = sha(publish(root / "child", a, "A child"))
    b.verdict.crossings, b.verdict.level, b.verdict.summary = [], "undetermined", "B has no thermal root"
    record = Promotion(parent=".", parent_sha256=sha((root / "result.json").read_bytes()) if recorded else "",
                       labels=["c"], children=[Child(label="c", model="fixture", origin="synthetic", folder="child",
                                                     level="viable_pending", result_sha256=child if recorded else "")])
    path = root / "promotion_c.json"
    build.publish(path, record.model_dump_json().encode(), record, lambda e: "Promotion", workflow="promotion")
    return path, b, parent


def _review(path: Path):
    from adroit.constraints.review_queue import build_queue, load_selected
    return build_queue(load_selected(path))


@pytest.mark.parametrize("case", ["child replaced", "parent replaced", "child absent"])
def test_review_and_export_follow_the_versions_a_promotion_records(tmp_path, case):
    """VI-04, the auditor's review graph and its regression: the review queue and the export select the same versions, and
    name the same edges unavailable: a child or parent replaced since the promotion, or a child no longer saved, is not
    reviewed (or exported) in place of the one the record names, and both say so. Unraced, the child's review tasks
    are listed."""
    import shutil
    path, b, parent = _promotion(tmp_path / "graph")
    before = _review(path)
    assert before.tasks and not any("another version" in w for w in before.warnings)
    if case == "child replaced":
        publish(tmp_path / "graph" / "child", b, "B child")
    elif case == "parent replaced":
        other = parent.model_copy(update={"max_local_z": 1.0})
        build.publish(path.parent / "result.json", other.model_dump_json().encode(), other, lambda e: "Parent B",
                      workflow="signal")
    else:
        shutil.rmtree(tmp_path / "graph" / "child")
    queue = _review(path)
    manifest = archive.export_run(path, tmp_path / "out.zip")
    what = "the parent result" if case == "parent replaced" else "the study of fixture for c"
    named = "now saved is another version" if "replaced" in case else "is not saved"
    assert any(what in w and named in w and "not reviewed" in w for w in queue.warnings)
    assert any(what in w and named in w and "not exported" in w for w in manifest.warnings)
    reviewed = {s for s in queue.selected_results}
    exported = {sha(z) for z in _results(tmp_path / "out.zip")}
    assert reviewed == exported
    if case != "parent replaced":
        assert not queue.tasks
    assert archive.verify_bundle(tmp_path / "out.zip").valid


def _results(bundle: Path) -> list[bytes]:
    with zipfile.ZipFile(bundle) as z:
        return [z.read(n) for n in z.namelist() if n.endswith("/result.json")]


def test_a_promotion_recording_no_digests_is_reviewed_and_exported_as_found_saying_so(tmp_path):
    """VI-04's legacy edges: a promotion made before ADROIT recorded its edges' digests is followed as found by the
    review and the export alike, each saying so."""
    path, _, _ = _promotion(tmp_path / "graph", recorded=False)
    queue = _review(path)
    manifest = archive.export_run(path, tmp_path / "out.zip")
    for text in ("records no digest of its children's results", "records no digest of the result it was promoted"):
        assert any(text in w for w in queue.warnings) and any(text in w for w in manifest.warnings)
    assert queue.tasks
    assert set(queue.selected_results) == {sha(z) for z in _results(tmp_path / "out.zip")}


# --- VI-05: a resumed checkpoint's dates -------------------------------------------------------------------------


def _context(day: int):
    from adroit.core.evidence import EvidenceContext
    return EvidenceContext(origin="legacy_unknown", identity="same-input-software-identity",
                           calculation_started_at=f"2026-11-0{day}T01:00:00Z",
                           calculation_completed_at=f"2026-11-0{day}T01:01:00Z")


def _beside(path: Path, result, kind: str, day: int, original=None) -> None:
    """A publication of ``result`` beside the checkpoint, dated ``day`` (the auditor's)."""
    content = result.model_dump_json().encode()
    write_atomic(path, content)
    write_atomic(build.sidecar_path(path), build.build(kind, result, sha(content), _context(day), original)
                 .model_dump_json())


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "another publication beside it"])
@pytest.mark.parametrize("dated", [True, False], ids=["checkpoint with its dates", "checkpoint saved before"])
def test_a_resumed_track1_checkpoint_keeps_its_own_dates(tmp_path, replace, dated):
    """VI-05, the auditor's Track 1 case: the finished checkpoint A, calculated on 1 November, beside B's publication dated
    2 November, the contexts' identities alike. Resumed, A is published with A's dates, saved with its checkpoint; one
    saved before ADROIT kept them is dated only where the publication beside it is A, else by the restored result's own
    saved date alone, saying so."""
    from adroit.core.checkpoint import Checkpoint
    from adroit.evidence import runtime
    from adroit.orchestrator import track1, track1_identity

    def forbidden(*args, **kwargs):
        raise AssertionError("a resume must not calculate")
    folder = tmp_path / "t1"
    a, b = versions(folder)
    request = a.request.model_copy(update={"halo": "published", "propagation": "conservative", "workers": 1})
    a.request, b.request = request, b.request.model_copy(update={"halo": "published", "propagation": "conservative",
                                                                 "workers": 1})
    a.fixed, b.fixed = a.scan.request.fixed, b.scan.request.fixed
    checkpoint = Checkpoint(folder, request.model_dump(mode="json"), {}, False, {})
    checkpoint.save("finished", "result", a, dates=("2026-11-01T01:00:00Z", "2026-11-01T01:01:00Z") if dated else None)
    checkpoint.save("finished", "artifacts", track1._Artifacts(hashes={}, drawn=True))
    _beside(folder / "result.json", b if replace else a, "track1", 2 if replace else 1)
    with patch.object(track1_identity, "dependencies", return_value={}), \
            patch.object(runs, "capture_request", return_value=_context(3)), patch.object(track1, "_run", forbidden), \
            patch.object(runtime, "finish", side_effect=lambda c, **k: c):
        runs.track1(request, folder=folder, resume=True)
    saved = build.read_saved(folder / "result.json")
    assert saved.result.scan.points[0].point.m_chi == 50
    started = saved.envelope.context.calculation_started_at
    if dated or not replace:
        assert started == "2026-11-01T01:00:00Z"
        assert studies.load(folder).calculation_started_at == started
    else:
        assert started == "" and any("not recorded" in n for n in saved.envelope.context.notes)
        report = (folder / "report.md").read_text()     # dated only by the restored result's own saved date
        assert f"Calculation date: {a.created} (saved date; time not recorded)" in report
        assert "2026-11-02" not in report


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "another publication beside it"])
def test_a_resumed_native_fit_keeps_its_own_dates(tmp_path, replace):
    """VI-05, the auditor's native-fit case: the checkpoint's q0 = 2, calculated on 1 November, beside B's publication
    (q0 = 99) dated 2 November. Resumed, A is published with A's dates, its checkpoint's."""
    from adroit.core.checkpoint import Checkpoint
    from adroit.evidence import runtime
    from adroit.orchestrator import native_fit, track1_identity
    from adroit.parameter_space import native_joint
    from tests.orchestrator.test_db_recheck import _native_fit

    def forbidden(*args, **kwargs):
        raise AssertionError("a resume must not calculate")
    folder = tmp_path / "native"
    a, b = _native_fit(tmp_path)
    request = native_fit.NativeFitRequest(spec=__import__("adroit.parameter_space.simplified", fromlist=["model"])
                                          .model("vector", 60, 125), masses_gev=[60], settings=a.settings)
    folder.mkdir()
    Checkpoint(folder, request.model_dump(mode="json"), {}, False).save(
        "finished", "native", a, dates=("2026-11-01T01:00:00Z", "2026-11-01T01:01:00Z"))
    _beside(folder / "result.json", b if replace else a, "native_joint", 2 if replace else 1,
            request.model_dump(mode="json"))
    with patch.object(track1_identity, "dependencies", return_value={}), \
            patch.object(runtime, "capture_request", return_value=_context(3)), \
            patch.object(native_joint, "run", forbidden), patch.object(runtime, "finish", side_effect=lambda c, **k: c):
        native_fit.run(request, folder, resume=True)
    saved = build.read_saved(folder / "result.json")
    assert saved.result.observed_max_q0 == 2.0
    assert saved.envelope.context.calculation_started_at == "2026-11-01T01:00:00Z"


def test_a_finished_run_saves_its_dates_with_its_checkpoint(tmp_path):
    """VI-05: the dates a checkpoint keeps are of the artifact it keeps: a value saved with them is dated, and read
    back with them in a resume (of the same read: DC-03); one saved without them is not."""
    from adroit.core.checkpoint import Checkpoint, Chronology
    folder = tmp_path / "f"
    a, _ = versions(folder)
    checkpoint = Checkpoint(folder, {"x": 1}, {}, False, {"calculation_started_at": "2026-11-01T01:00:00Z"})
    assert checkpoint.started("now") == "2026-11-01T01:00:00Z"
    checkpoint.save("finished", "result", a, dates=(checkpoint.started("now"), "2026-11-01T02:00:00Z"))
    assert checkpoint.chronology("finished", "result", a) == Chronology("2026-11-01T01:00:00Z", "2026-11-01T02:00:00Z",
                                                                        False)
    resumed = Checkpoint(folder, {"x": 1}, {}, True)
    assert resumed.load("finished", "result", type(a)) == a
    assert resumed.chronology("finished", "result", a) == Chronology("2026-11-01T01:00:00Z", "2026-11-01T02:00:00Z",
                                                                     True)
    checkpoint.save("finished", "result", a)
    again = Checkpoint(folder, {"x": 1}, {}, True)
    again.load("finished", "result", type(a))
    assert again.chronology("finished", "result", a) == Chronology("", "", True)

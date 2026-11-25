"""The auditor's CY recheck, CZ-01 to CZ-03 (2026-11-01): identities a writer or an exporter already held, dropped at the
next boundary. A promotion bundle had attached the parent result now saved, B, as the parent of a promotion made from
A, and verified (CZ-01). Two writers had bound the report of the result they held, A, to the digest of the file read
again, B (CZ-02). A native fit's "exact request" download had been the request.json beside it, another request than
its evidence captured (CZ-03). Each case is run through the real writer, exporter, verifier or download, with only
the expensive calculation substituted by a typed saved result."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from adroit.core.durable import write_atomic
from adroit.evidence import archive, build
from adroit.evidence.bindings import bind, read_report


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- CZ-01 ------------------------------------------------------------------------------------------------------


def _coherent(folder: Path, content: bytes) -> bytes:
    """A signal result published with its evidence, as its writer publishes it; the evidence's bytes."""
    write_atomic(folder / "result.json", content)
    build.save(folder / "result.json", "signal")
    return build.sidecar_path(folder / "result.json").read_bytes()


def _signal_versions(folder: Path, monkeypatch) -> tuple[bytes, bytes]:
    """A, a real Signal best fits study on the synthetic germanium search (``signal.run``), saved with its evidence;
    and B, another run of it whose candidate is at 40 GeV, not 20."""
    from adroit.orchestrator import signal
    from tests.ui.acceptance.test_journeys import _toy_signal_study
    _toy_signal_study(folder, monkeypatch)
    a = (folder / "result.json").read_bytes()
    _coherent(folder, a)
    b = signal.run(signal.SignalRequest(experiment="toy germanium", null_modules=[], toys=20, leaders=1,
                                        complementary=False, candidates=[signal.Candidate(
                                            label="scalar @ 40", card_id="O1", isospin="s", mass_gev=40)]))
    return a, b.model_dump_json().encode()


def _child_run(monkeypatch, level: str = "viable_pending", summary: str = "AUDIT CHILD A: a saved fixture"):
    """Each child's calculation substituted by a typed saved result (as journey 2 substitutes it)."""
    from adroit.orchestrator import single_idea

    def child(request, folder, fetch=None, **claim):                # claim: its writer's hold of the folder (DF-01)
        Path(folder).mkdir(parents=True, exist_ok=True)
        return single_idea.SingleIdeaResult(request=request, level=level, summary=summary, fit_quality="fits",
                                            constraint_compatibility="viable", thermal_viability="viable_pending")
    monkeypatch.setattr(single_idea, "run", child)


def _promote(folder: Path, label: str, parent: bytes) -> Path:
    from adroit.orchestrator import runs
    from adroit.orchestrator.promote import slug
    runs.promote(folder, [label], {"masses": 2, "toys": 20, "grid": 4}, None, 3, parent_sha256=sha(parent))
    return folder / f"promotion_{slug(label)}.json"


def _exported(record: Path, destination: Path):
    """The bundle of a promotion: its manifest, its files, its root node, and the digest of each node's result."""
    manifest = archive.export_run(record, destination)
    _, files = archive.read_bundle(destination)
    digests = {n.id: sha(files[n.result_path]) for n in manifest.nodes}
    return manifest, files, manifest.nodes[0], digests


def test_a_promotion_bundle_attaches_only_the_parent_it_was_made_from(tmp_path, monkeypatch):
    """CZ-01, the auditor's case: a promotion made from A, exported unchanged, attaches A as its parent and verifies. B, a
    coherent result with its evidence, published at the parent's path since: exported again, the bundle attaches no
    parent, saying so, and B nowhere; it verifies. A second promotion made from B, at the same path, attaches B."""
    from adroit.evidence.archive import verify_bundle
    folder = tmp_path / "runs" / "signal"
    a, b = _signal_versions(folder, monkeypatch)
    _child_run(monkeypatch)
    first = _promote(folder, "scalar @ 20", a)
    manifest, _, stable, at_a = _exported(first, tmp_path / "a.zip")
    assert stable.workflow == "promotion" and sha(a) in {at_a[k] for k in stable.children}
    assert verify_bundle(tmp_path / "a.zip").valid and not any("parent" in w for w in manifest.warnings)
    _coherent(folder, b)
    manifest, _, root, digests = _exported(first, tmp_path / "b.zip")
    assert sha(b) not in digests.values() and sha(a) not in digests.values()
    assert any("the parent result now saved is another version" in w and sha(b) in w for w in manifest.warnings)
    assert verify_bundle(tmp_path / "b.zip").valid
    second = _promote(folder, "scalar @ 40", b)
    _, _, other, at_b = _exported(second, tmp_path / "second.zip")
    assert at_b[other.parent] == sha(b) and verify_bundle(tmp_path / "second.zip").valid
    assert at_a[stable.parent] == sha(a) and not root.parent           # the parent link (``ArchiveNode.parent``)
    children = [key for key in stable.children if key != stable.parent]
    made = {c["result_sha256"] for c in json.loads(first.read_bytes())["children"]}
    assert children and {at_a[k] for k in children} == made and root.children == children


def _forged(bundle: Path, destination: Path, replace: dict[str, bytes | None], edit=None) -> Path:
    """A bundle with members replaced (None: removed) and its manifest's hashes updated to match, as a forger would."""
    from adroit.evidence.archive_models import ArchiveArtifact
    manifest, files = archive.read_bundle(bundle)
    files = {k: v for k, v in {**files, **replace}.items() if v is not None and k != "manifest.json"}
    if edit:
        edit(manifest)
    manifest.artifacts = [ArchiveArtifact(path=a.path, sha256=sha(files[a.path]), size=len(files[a.path]),
                                          role=a.role) for a in manifest.artifacts if a.path in files]
    with zipfile.ZipFile(destination, "w") as out:
        for name, data in sorted({**files, "manifest.json": archive._bytes(manifest.model_dump(mode="json"))}.items()):
            out.writestr(name, data)
    return destination


def _other_child(files: dict[str, bytes], node) -> dict[str, bytes]:
    """A coherent other version of a child node: its result with another summary, and that result's evidence."""
    from adroit.evidence.results import typed
    data = json.loads(files[node.result_path])
    data["summary"] = "AUDIT CHILD B: another version"
    content = json.dumps(data).encode()
    kind, result = typed(data, "single_idea")
    return {node.result_path: content,
            node.evidence_path: build.build(kind, result, sha(content)).model_dump_json().encode()}


def test_a_promotion_bundle_whose_parent_or_child_was_replaced_does_not_verify(tmp_path, monkeypatch):
    """CZ-01: a promotion's bundle with its parent node replaced by A (coherent: A's result and evidence), its
    manifest's hashes updated, does not verify: its parent is not the result it was promoted from. Nor with a child
    replaced by another coherent version, nor with its parent link removed and B left among its studies."""
    from adroit.evidence.archive import verify_bundle
    folder = tmp_path / "runs" / "signal"
    a, b = _signal_versions(folder, monkeypatch)
    a_evidence = build.sidecar_path(folder / "result.json").read_bytes()
    _child_run(monkeypatch)
    _coherent(folder, b)
    _, files, root, _ = _exported(_promote(folder, "scalar @ 40", b), tmp_path / "b.zip")
    assert verify_bundle(tmp_path / "b.zip").valid
    nodes = {n.id: n for n in archive.read_bundle(tmp_path / "b.zip")[0].nodes}
    parent = next(nodes[k] for k in root.children if nodes[k].workflow == "signal")
    forged = _forged(tmp_path / "b.zip", tmp_path / "parent.zip",
                     {parent.result_path: a, parent.evidence_path: a_evidence})
    found = verify_bundle(forged)
    assert not found.valid and "promotion/parent mismatch" in found.issues[0]
    child = next(nodes[k] for k in root.children if nodes[k].workflow == "single_idea")
    report = child.result_path.replace("result.json", "report.md")
    record = child.result_path.replace("result.json", "study.json")     # it names the child it replaces (VI-01)
    forged = _forged(tmp_path / "b.zip", tmp_path / "child.zip", {**_other_child(files, child), report: None,
                                                                  record: None})
    found = verify_bundle(forged)
    assert not found.valid and "promotion/child mismatch" in found.issues[0]

    def unlinked(manifest):
        manifest.nodes[0].parent = ""
    found = verify_bundle(_forged(tmp_path / "b.zip", tmp_path / "unlinked.zip", {}, unlinked))
    assert not found.valid and "without naming it its parent" in found.issues[0]      # DA-03's version 2 rule


def test_a_child_replaced_since_its_promotion_is_not_exported_as_its_child(tmp_path, monkeypatch):
    """CZ-01: a child study replaced since the promotion wrote it (a coherent other version: result and evidence) is
    left out of the promotion's bundle, saying so; the bundle verifies. A promotion recorded before ADROIT kept these
    digests is exported as found, saying that its parent and children are not checked against it."""
    from adroit.evidence.archive import verify_bundle
    folder = tmp_path / "runs" / "signal"
    a, _ = _signal_versions(folder, monkeypatch)
    _child_run(monkeypatch)
    record = _promote(folder, "scalar @ 20", a)
    child = Path(json.loads(record.read_bytes())["children"][0]["folder"])
    content = json.loads((child / "result.json").read_bytes())
    content["summary"] = "AUDIT CHILD B: another version"
    replaced = json.dumps(content).encode()
    write_atomic(child / "result.json", replaced)
    build.save(child / "result.json", "single_idea")
    manifest, _, root, digests = _exported(record, tmp_path / "child.zip")
    assert sha(replaced) not in {digests[k] for k in root.children} and root.parent   # the parent's study only
    assert verify_bundle(tmp_path / "child.zip").valid
    assert any("now saved is another version" in w and sha(replaced) in w for w in manifest.warnings)
    older = json.loads(record.read_bytes())
    older.pop("parent_sha256")
    for c in older["children"]:
        c.pop("result_sha256")
    write_atomic(record, json.dumps(older).encode())
    build.save(record, "promotion")
    manifest, _, root, digests = _exported(record, tmp_path / "older.zip")
    assert digests[root.parent] == sha(a) and sha(replaced) in digests.values()
    assert any("records no digest of the result it was promoted from" in w for w in manifest.warnings)
    assert any("records no digest of its children's results" in w for w in manifest.warnings)
    assert verify_bundle(tmp_path / "older.zip").valid


def test_a_result_reached_before_is_held_to_the_digest_an_edge_names(tmp_path, monkeypatch):
    """CZ-01: a result the export has already reached is not attached by a later edge naming another version of it:
    the edge's digest is checked against the version reached, not bypassed."""
    from adroit.evidence.archive_models import BundleManifest
    from tests.orchestrator.test_cx_recheck import _study
    from adroit.evidence.version import resolve
    folder, a, _ = _study(tmp_path, monkeypatch)
    manifest, files, seen = BundleManifest(root="n0", nodes=[], artifacts=[]), {}, {}
    held = resolve(folder, presentation=True)
    node = archive._node(held, folder.resolve(), files, manifest, seen, False, False)
    with pytest.raises(ValueError):                                        # archive._Other
        archive._node(held, folder.resolve(), files, manifest, seen, False, False, "0" * 64)
    assert archive._node(held, folder.resolve(), files, manifest, seen, False, False,
                         sha(a[0])) == node and len(manifest.nodes) == 1


# --- CZ-02 ------------------------------------------------------------------------------------------------------


BOUNDARIES = ("before its evidence", "before its report", "after its report")


@contextmanager
def _published_at(boundary: str, publish_b):
    """B published by another process at one boundary of a writer's publication (``build.publish``): after the
    result's bytes are written and before its evidence; after its evidence and before its report; after its report
    and before the writer's check."""
    real_save, real_kept = build.save, getattr(build, "kept", None)
    done = []

    def save(*args, **kwargs):
        if boundary == "before its evidence":
            done.append(publish_b())
        envelope = real_save(*args, **kwargs)
        if boundary == "before its report":
            done.append(publish_b())
        return envelope

    def kept(*args, **kwargs):
        if boundary == "after its report":
            done.append(publish_b())
        return real_kept(*args, **kwargs)
    with patch.object(build, "save", save), patch.object(build, "kept", kept, create=real_kept is None):
        yield done


def _attempt(write, boundary: str, publish_b) -> tuple[list, Exception | None]:
    """``write()`` with B published at ``boundary``: whether B was published, and what the writer raised."""
    try:
        with _published_at(boundary, publish_b) as done:
            write()
    except Exception as error:      # the writer's refusal, checked after the folder it left
        return done, error
    return done, None


def _group(folder: Path, kind: str, result, report: str, inputs=None):
    """A publication of ``result`` as another writer publishes it: its bytes, their evidence, then a report bound to
    them."""
    content = result.model_dump_json(indent=1).encode()

    def publish():
        envelope = build.build(kind, result, sha(content), original_inputs=inputs)
        write_atomic(folder / "result.json", content)
        write_atomic(build.sidecar_path(folder / "result.json"), envelope.model_dump_json())
        write_atomic(folder / "report.md", bind(report, sha(content), folder, []))
        return True
    return publish, content


def _never_a_s_report_as_b_s(folder: Path, a_mark: str, b_mark: str) -> None:
    """The folder as left: its readers take no report of A as the report of the result saved, nor A's evidence as its
    evidence; the export either refuses the mismatch or attaches only a report of the result it holds, and verifies."""
    from adroit.evidence.archive import export_run, verify_bundle
    content = (folder / "result.json").read_bytes()
    found = read_report(folder / "report.md", sha(content))
    assert not (found.state == "bound" and a_mark in found.text)
    try:
        assert build.read_saved(folder / "result.json").envelope.result_sha256 == sha(content)
    except ValueError as error:
        assert "mismatch" in str(error)
    try:
        manifest = export_run(folder / "result.json", folder.parent / f"{folder.name}.zip")
    except (ValueError, OSError):
        return
    files = archive.read_bundle(folder.parent / f"{folder.name}.zip")[1]
    assert verify_bundle(folder.parent / f"{folder.name}.zip").valid
    report = files.get(manifest.nodes[0].result_path.replace("result.json", "report.md"), b"").decode()
    assert a_mark not in report or b_mark in report


def _child_versions(monkeypatch):
    """The child writer's inputs: a promoted candidate of a real signal study, and A and B of its child's result."""
    from adroit.orchestrator import promote, single_idea
    held = {}

    def child(request, folder, fetch=None, **claim):                # claim: its writer's hold of the folder (DF-01)
        Path(folder).mkdir(parents=True, exist_ok=True)
        held["a"] = single_idea.SingleIdeaResult(request=request, level="viable", summary="AUDIT CHILD A: viable",
                                                 fit_quality="fits", constraint_compatibility="viable",
                                                 thermal_viability="viable")
        held["b"] = held["a"].model_copy(update={"level": "excluded", "summary": "AUDIT CHILD B: excluded",
                                                 "thermal_viability": "excluded"})
        held["folder"] = Path(folder)
        return held["a"]
    monkeypatch.setattr(single_idea, "run", child)
    return promote, held


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_a_child_s_report_is_never_bound_to_a_result_published_meanwhile(tmp_path, monkeypatch, boundary):
    """CZ-02, the auditor's child case through ``promote._study``: B (result, evidence and report) published at each
    boundary of the child writer's publication. The writer refuses, naming the replacement; the folder holds no
    report of A bound to B, and its readers and its export refuse the mismatch or show B's. Unraced, A's group."""
    from adroit.evidence.results import load_result
    from adroit.orchestrator.signal import SignalResult
    from tests.ui.acceptance.test_journeys import _toy_signal_study
    parent = tmp_path / "runs" / "signal"
    label = _toy_signal_study(parent, monkeypatch)
    result = SignalResult.model_validate_json((parent / "result.json").read_bytes())
    promote, held = _child_versions(monkeypatch)
    c = promote.candidates_of(result)[label]
    origin, spec = promote.models_for(result, c)[0]

    def publish_b():
        return _group(held["folder"], "single_idea", held["b"], "# B\n\nAUDIT CHILD B report\n")[0]()
    done, raised = _attempt(lambda: promote._study(parent, result, c, origin, spec, {"masses": 2, "toys": 2,
                                                                                   "grid": 4}), boundary, publish_b)
    assert done == [True]
    _never_a_s_report_as_b_s(held["folder"], "AUDIT CHILD A", "AUDIT CHILD B")
    assert isinstance(raised, build.Replaced) and "replaced by another" in str(raised)
    child = promote._study(parent, result, c, origin, spec, {"masses": 2, "toys": 2, "grid": 4})
    content = (Path(child.folder) / "result.json").read_bytes()
    found = read_report(Path(child.folder) / "report.md", sha(content))
    assert found.state == "bound" and "AUDIT CHILD A" in found.text and child.result_sha256 == sha(content)
    assert load_result(Path(child.folder) / "result.json")[1].level == "viable"


def _native(monkeypatch):
    """A native fit's request, and A and B of its result (the auditor's fixture: q0 2 against 99, distinct assumptions)."""
    from adroit.core.fit_domain import FitCoordinate, PhysicalDomain
    from adroit.orchestrator import native_fit
    from adroit.parameter_space import native_joint, simplified
    settings = native_joint.JointSettings(toys=20, domain=PhysicalDomain(coordinates=[
        FitCoordinate(parameter="g_chi", low=0.01, high=1)]))
    request = native_fit.NativeFitRequest(spec=simplified.model("vector", 60, 125), masses_gev=[50, 70],
                                          settings=settings)
    a = native_joint.JointResult(settings=settings, masses_gev=[50, 70], complete=True, observed_max_q0=2.0,
                                 calibration=native_joint.Calibration(complete=True, toys_requested=20,
                                                                      toys_completed=20, seed=3, p_mc=2 / 21,
                                                                      z_mc=1.3, minimum_resolvable_p=1 / 21),
                                 assumptions=["AUDIT A: native fit assumptions"])
    b = a.model_copy(update={"observed_max_q0": 99.0, "assumptions": ["AUDIT B: other native fit assumptions"]})
    monkeypatch.setattr(native_joint, "run", lambda *args, **kwargs: a)
    return native_fit, request, a, b


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_a_native_fit_s_report_is_never_bound_to_a_result_published_meanwhile(tmp_path, monkeypatch, boundary):
    """CZ-02, the auditor's native case through ``native_fit.run``: B published at each boundary of its publication. The
    run refuses, naming the replacement; no report of A is bound to B. Unraced, A's report is bound to A."""
    native_fit, request, a, b = _native(monkeypatch)
    folder = tmp_path / "native"
    publish_b, _ = _group(folder, "native_joint", b, "# B\n\nAUDIT B report\n", request.model_dump(mode="json"))
    done, raised = _attempt(lambda: native_fit.run(request, folder), boundary, publish_b)
    assert done == [True]
    _never_a_s_report_as_b_s(folder, "AUDIT A", "AUDIT B")
    assert isinstance(raised, build.Replaced)
    stable = tmp_path / "stable"
    assert native_fit.run(request, stable).observed_max_q0 == 2.0
    found = read_report(stable / "report.md", sha((stable / "result.json").read_bytes()))
    assert found.state == "bound" and "AUDIT A" in found.text and "AUDIT B" not in found.text


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_the_workbench_writer_never_binds_a_report_to_a_result_published_meanwhile(tmp_path, monkeypatch, boundary):
    """CZ-02 through the workbench's writer (``runs._write``), every study's: B published at each boundary. It
    refuses, and records no study; no report of A is bound to B."""
    from adroit.evidence.results import load_result
    from adroit.orchestrator import runs, studies
    from tests.orchestrator.test_cx_recheck import _study
    folder, a, b = _study(tmp_path, monkeypatch)
    result_a = load_result(folder / "result.json")[1]
    result_b = load_result(folder / "result.json")[1].model_validate_json(b[0])
    publish_b, _ = _group(folder, "track1", result_b, "# Track 1\n\nB report\n")
    recorded = []
    monkeypatch.setattr(studies, "record", lambda *args, **kwargs: recorded.append(args))
    done, raised = _attempt(lambda: runs._write(folder, result_a, "# Track 1\n\nA report\n", "track1",
                                                "a toy plane"), boundary, publish_b)
    assert done == [True]
    _never_a_s_report_as_b_s(folder, "A report", "B report")
    assert isinstance(raised, build.Replaced) and not recorded


def test_a_report_binds_its_figures_as_its_writer_drew_them(tmp_path, monkeypatch):
    """CZ-02, the figures: a figure the run drew (``bindings.write_figure``), replaced before its report is written,
    is bound as drawn; its readers then withhold the replacement as not the report's figure."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adroit.evidence import bindings
    from adroit.evidence.bindings import figure
    from adroit.evidence.results import load_result
    from adroit.orchestrator import runs
    from tests.orchestrator.test_cw_recheck import _toy_study
    from adroit.core.durable import publishing
    folder = _toy_study(tmp_path / "runs", monkeypatch, False)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    with publishing(folder) as held:        # drawn and published under one hold, as its writers do (DF-01)
        bindings.write_figure(fig, folder / "parameter_plane.png", 50)
        plt.close(fig)
        drawn = (folder / "parameter_plane.png").read_bytes()
        write_atomic(folder / "parameter_plane.png", drawn + b"\0")           # another process, before the report
        _, result = load_result(folder / "result.json")
        runs._write(folder, result.model_copy(update={"plots": ["parameter_plane.png"]}),
                    "# Track 1\n\n![parameter_plane.png](parameter_plane.png)\n", "track1", "a toy plane", claim=held)
    found = read_report(folder / "report.md", sha((folder / "result.json").read_bytes()))
    assert found.state == "bound" and found.binding.figures["parameter_plane.png"] == sha(drawn)
    assert figure(folder, "parameter_plane.png", found) is None
    write_atomic(folder / "parameter_plane.png", drawn)
    assert figure(folder, "parameter_plane.png", found) == drawn


# --- CZ-03 ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("beside", ["unchanged", "another valid request", "missing", "null", "torn"])
def test_a_native_fit_s_exact_request_is_the_request_its_evidence_captured(tmp_path, monkeypatch, beside):
    """CZ-03, the auditor's case: a native fit written by its real writer (the fit substituted), its result and evidence
    unchanged, and the request.json beside it as given. The exact request downloaded, through the export and through
    the page's download, is the request its evidence captured, every time; the stored files are not changed."""
    from adroit.evidence import exports
    from adroit.ui.exports import files
    native_fit, request, _, _ = _native(monkeypatch)
    folder = tmp_path / "native"
    native_fit.run(request, folder)
    captured = request.model_dump(mode="json")
    content, evidence = (folder / "result.json").read_bytes(), build.sidecar_path(folder / "result.json").read_bytes()
    other = {**captured, "masses_gev": [1000.0, 2000.0]}
    native_fit.NativeFitRequest.model_validate(other)
    put = {"unchanged": json.dumps(captured), "another valid request": json.dumps(other), "null": "null",
           "torn": json.dumps(captured)[:40]}
    if beside == "missing":
        (folder / "request.json").unlink()
    else:
        write_atomic(folder / "request.json", put[beside])
    assert json.loads(exports.request(folder / "result.json")["request.json"]) == captured
    from adroit.evidence.version import Token
    name, payload = files("references", Token(str(folder / "result.json"), result=sha(content)))
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        assert json.loads(z.read("request.json")) == captured
    assert (folder / "result.json").read_bytes() == content
    assert build.sidecar_path(folder / "result.json").read_bytes() == evidence


def test_every_report_written_beside_a_result_is_bound_to_it(tmp_path, monkeypatch):
    """CZ-02, the record's claim kept: the writers outside the studies' that write a report beside a result.json, the
    agents' run, a budget stop's record and the research assistant's run, each bind it to the bytes they wrote."""
    from typer.testing import CliRunner
    from adroit.agents import llm
    from adroit.evidence.bindings import binding
    from adroit.orchestrator import agents as dm9, cli, lagrangian, research_assistance
    from tests.orchestrator.test_research_assistance import request
    monkeypatch.setattr(llm, "LLMClient", lambda **kw: llm.FakeLLMClient())
    source = tmp_path / "result.json"
    source.write_text(lagrangian.LagrangianResult(request=lagrangian.LagrangianRequest()).model_dump_json())
    monkeypatch.setitem(dm9.RUNNERS, "lagrangian", lambda *args: dm9.AgentResult(subject="x"))
    assert CliRunner().invoke(cli.app, ["agents", str(source), "--budget", "1", "--out", str(tmp_path / "a")]).exit_code == 0

    def stop(*args, **kwargs):
        error = llm.BudgetExceeded(.1, .25, .2)
        error.ledger_path = str(tmp_path / "paid-answers.jsonl")
        raise error
    monkeypatch.setitem(dm9.RUNNERS, "lagrangian", stop)
    assert CliRunner().invoke(cli.app, ["agents", str(source), "--budget", ".25", "--out", str(tmp_path / "s")]).exit_code == 3
    research_assistance.run(request(), tmp_path / "r")
    for folder in ("a", "s", "r"):
        written = binding((tmp_path / folder / "report.md").read_text())
        assert written and written.result_sha256 == sha((tmp_path / folder / "result.json").read_bytes()), folder

"""The shared version handle (``evidence.version``; the version-handle plan's step 1, decided by the owner on
2026-11-03): each part of a saved study read once, as one checked transaction, with each part it does not hold in an
explicit state; a token resolving to its version or naming the part that changed; and the untouched historical exports,
read as the saved folders they came from, resolving with their qualifications. Each study is written by the production
writers; nothing is calculated."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from adroit.core.durable import write_atomic
from adroit.evidence import bindings, build, version
from adroit.evidence.version import NONE, Changed, Token, Unsettled, resolve
from adroit.orchestrator import studies
from tests.orchestrator.test_vi_audit import _evidence, _promotion, publish, versions

BUNDLES = Path(__file__).parents[1] / "fixtures" / "bundles"
PNG = b"\x89PNG\r\n\x1a\nfigure A"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def figured(folder: Path, result, label: str, png: bytes = PNG) -> bytes:
    """``result`` published by the production writer with a figure its report embeds, drawn first; its bytes."""
    folder.mkdir(parents=True, exist_ok=True)
    write_atomic(folder / "plane.png", png)
    content = result.model_dump_json(indent=1).encode()
    build.publish(folder / "result.json", content, result,
                  lambda e: f"# {label} report\n\n![plane](plane.png)\n", workflow="track1")
    studies.record(folder, "track1", f"{label} study", result_sha256=sha(content))
    return content


# --- each part held, of one publication ---------------------------------------------------------------------------


def test_a_version_holds_each_part_of_one_publication(tmp_path):
    folder = tmp_path / "study"
    a, _ = versions(folder)
    content = figured(folder, a, "A")
    found = resolve(folder, presentation=True)
    assert (found.result_state, found.evidence_state, found.record_state) == ("held", "bound", "bound")
    assert found.content == content and found.result_sha256 == sha(content)
    assert found.typed() == a and found.study().title == "A study"
    assert found.report().state == "bound" and found.figure("plane.png") == PNG
    assert found.figures == ("plane.png",)
    token = found.token()
    assert token.result == sha(content) and token.evidence == sha(build.sidecar_path(folder / "result.json")
                                                                   .read_bytes())
    assert token.presentation == sha((folder / "report.md").read_bytes())
    assert token.record == studies.header((folder / "study.json").read_bytes())
    assert resolve(token).result_sha256 == sha(content)


def test_its_views_are_fresh_copies(tmp_path):
    """A consumer cannot change the version it was handed: each view is a fresh copy of what its bytes give."""
    folder = tmp_path / "study"
    a, _ = versions(folder)
    figured(folder, a, "A")
    found = resolve(folder, presentation=True)
    found.typed().request.spec.name = "changed"
    found.data()["request"] = None
    found.study().title = "changed"
    found.envelope().warnings.append("changed")
    found.report().binding.figures.clear()
    assert found.typed() == a and found.data()["request"] is not None and found.study().title == "A study"
    assert "changed" not in found.envelope().warnings and found.figure("plane.png") == PNG


def test_a_list_reads_no_evidence_and_no_large_result(tmp_path):
    """A list's version (``evidence=False``, ``limit``): its evidence unread, never assumed; a result larger than the
    limit not read, said so in its headline's words."""
    folder = tmp_path / "study"
    a, _ = versions(folder)
    publish(folder, a, "A")
    listed = resolve(folder, evidence=False)
    assert listed.evidence_state == "unread" and listed.token().evidence == ""
    with pytest.raises(ValueError, match="evidence was not read"):
        listed.saved()
    large = resolve(folder, evidence=False, limit=10)
    assert large.result_state == "unread" and "larger than" in large.headline().damage
    assert large.record_state == "unread"


# --- each part it does not hold, named ----------------------------------------------------------------------------


def _drop(path: Path) -> None:
    path.unlink()


CASES = {
    "no sidecar": (lambda f: _drop(build.sidecar_path(f / "result.json")), "evidence_state", "legacy"),
    "sidecar of another version": (lambda f: write_atomic(build.sidecar_path(f / "result.json"),
                                   build.read_saved(f / "result.json").envelope.model_copy(
                                       update={"result_sha256": "0" * 64}).model_dump_json().encode()),
                                   "evidence_state", "other"),
    "sidecar damaged": (lambda f: write_atomic(build.sidecar_path(f / "result.json"), b"{"), "evidence_state",
                        "damaged"),
    "no record": (lambda f: _drop(f / "study.json"), "record_state", "absent"),
    "record written before": (lambda f: studies.save(studies.load(f).model_copy(update={"result_sha256": ""})),
                              "record_state", "unbound"),
    "record of another version": (lambda f: studies.save(studies.load(f).model_copy(
        update={"result_sha256": "0" * 64})), "record_state", "other"),
    "record damaged": (lambda f: write_atomic(f / "study.json", b"{}"), "record_state", "damaged"),
}


@pytest.mark.parametrize("case", CASES)
def test_each_part_it_does_not_hold_is_in_an_explicit_state(tmp_path, case):
    folder = tmp_path / "study"
    a, _ = versions(folder)
    figured(folder, a, "A")
    change, attribute, state = CASES[case]
    change(folder)
    found = resolve(folder, presentation=True)
    assert getattr(found, attribute) == state
    if state in ("other", "damaged") and attribute == "evidence_state":
        assert found.evidence_why
        with pytest.raises(ValueError):
            found.saved()
    if case == "no sidecar":
        assert found.identity("evidence") == NONE and found.saved().envelope.context.origin == "legacy_unknown"
    if attribute == "record_state" and state in ("absent", "damaged"):
        assert found.study() is None and found.publisher() is None
    if case == "record damaged":
        assert found.identity("record").startswith("damaged:")


def test_the_presentation_in_each_state(tmp_path):
    """The report bound, of another version, recording none (written before), or absent; a figure replaced after the
    report bound it is not the report's (as found, it is held)."""
    folder = tmp_path / "study"
    a, b = versions(folder)
    figured(folder, a, "A")
    write_atomic(folder / "plane.png", b"another figure")
    found = resolve(folder, presentation=True)
    assert found.report().state == "bound" and found.figure("plane.png") is None
    assert found.figure_as_found("plane.png") == b"another figure"
    text = (folder / "report.md").read_text()
    write_atomic(folder / "report.md", bindings.unbound(text).encode())
    assert resolve(folder, presentation=True).report().state == "unbound"
    write_atomic(folder / "report.md", bindings.bind(text, "0" * 64, folder, []).encode())
    assert resolve(folder, presentation=True).report().state == "other"
    _drop(folder / "report.md")
    gone = resolve(folder, presentation=True)
    assert gone.report().state == "absent" and gone.identity("presentation") == NONE
    with pytest.raises(ValueError, match="report was not read"):
        resolve(folder).report()


def test_a_study_without_a_result_or_with_a_damaged_one(tmp_path):
    """No result: the record is held, the result absent (``FileNotFoundError`` for what needs it), and a token names
    that; a result that is not a JSON object is named damaged."""
    folder = tmp_path / "study"
    a, _ = versions(folder)
    publish(folder, a, "A")
    _drop(folder / "result.json")
    found = resolve(folder)
    assert found.result_state == "absent" and found.study().title == "A study" and found.token().result == NONE
    with pytest.raises(FileNotFoundError):
        found.saved()
    write_atomic(folder / "result.json", b"null")
    damaged = resolve(folder)
    assert damaged.result_state == "held" and damaged.evidence_state == "damaged"
    with pytest.raises(ValueError, match="not a JSON object"):
        damaged.saved()


# --- the token ----------------------------------------------------------------------------------------------------


def _another_report(folder: Path) -> None:
    text = bindings.unbound((folder / "report.md").read_text())
    write_atomic(folder / "report.md", bindings.bind(text + "\nedited\n", sha((folder / "result.json").read_bytes()),
                                                     folder, ["plane.png"]).encode())


CHANGES = {
    "result": lambda folder, b: publish(folder, b, "B"),
    "evidence": lambda folder, b: _evidence(folder / "result.json", build.read_saved(folder / "result.json").result,
                                           "another"),
    "presentation": lambda folder, b: _another_report(folder),
    "record": lambda folder, b: studies.save(studies.load(folder).model_copy(update={"title": "retitled"})),
}


@pytest.mark.parametrize("part", CHANGES)
def test_a_token_resolves_its_version_or_names_the_part_changed(tmp_path, part):
    """The R, E, P and S cases at the handle itself: after the token was taken, the part changed, the others the same
    where the change allows; resolving the token names that part, never returning the version now saved as the
    token's."""
    folder = tmp_path / "study"
    a, b = versions(folder)
    figured(folder, a, "A")
    token = resolve(folder, presentation=True).token()
    CHANGES[part](folder, b)
    with pytest.raises(Changed) as raised:
        resolve(token)
    assert raised.value.part == part and raised.value.expected == getattr(token, part)


def test_a_token_survives_navigation_and_a_byte_identical_restore(tmp_path):
    """A child added to the record changes its navigation, not its header: the token still resolves. A then B then A
    again: the token of A resolves only to A's very bytes restored; A published anew (its record and evidence written
    again) is another version, named."""
    folder = tmp_path / "study"
    a, b = versions(folder)
    figured(folder, a, "A")
    token = resolve(folder, presentation=True).token()
    child, _ = versions(folder / "children" / "c")
    publish(folder / "children" / "c", child, "child")
    studies.save(studies.load(folder).model_copy(update={"children": [str(folder / "children" / "c")]}))
    assert resolve(token).study().children
    kept = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    publish(folder, b, "B")
    with pytest.raises(Changed):
        resolve(token)
    for name, data in kept.items():
        write_atomic(folder / name, data)
    assert resolve(token).result_sha256 == token.result
    figured(folder, a, "A")
    studies.save(studies.load(folder).model_copy(update={"created": "2026-11-04T00:00:00+00:00"}))
    with pytest.raises(Changed) as raised:
        resolve(token)
    assert raised.value.part in ("evidence", "presentation", "record")


def test_a_token_as_a_link_and_as_a_line(tmp_path):
    folder = tmp_path / "runs" / "study"
    a, _ = versions(folder)
    publish(folder, a, "A")
    token = resolve(folder).token()
    query = token.query(tmp_path / "runs")
    assert query["path"] == "study" and query["sha256"] == token.result and "report" not in query
    back = Token.from_query(tmp_path / "runs", query)
    assert back == Token(str((folder / "result.json").resolve()), token.result, token.evidence, "", token.record)
    assert Token.parse(token.text()) == token
    with pytest.raises(ValueError):
        Token.from_query(tmp_path / "runs", {"path": "../elsewhere"})
    with pytest.raises(ValueError):
        Token.parse(json.dumps({"path": "x", "other": "y"}))


@pytest.mark.parametrize("name", ["result.json", "study.json", "report.md", "result.evidence.json"])
def test_a_link_to_a_study_whose_file_links_out_of_the_runs_directory_is_refused(tmp_path, name):
    """The auditor's version-handle audit, its observation made a case (the locator's policy): a link names a study inside
    the runs directory, every file of it there; one of them a symbolic link out of it is refused, as a folder linking
    out was; a link from one study to a file of another inside the runs directory stays a study's own file."""
    runs = tmp_path / "runs"
    folder = runs / "study"
    a, _ = versions(folder)
    publish(folder, a, "A")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / name).write_bytes((folder / name).read_bytes())
    (folder / name).unlink()
    (folder / name).symlink_to(outside / name)
    with pytest.raises(ValueError, match="outside the runs directory"):
        Token.from_query(runs, {"path": "study"})
    inside = runs / "kept" / name
    inside.parent.mkdir()
    inside.write_bytes((outside / name).read_bytes())
    (folder / name).unlink()
    (folder / name).symlink_to(inside)
    assert Token.from_query(runs, {"path": "study"}).path == str(folder.resolve() / "result.json")


# --- the transaction ----------------------------------------------------------------------------------------------


def test_a_publication_during_resolution_is_read_again_whole(tmp_path, monkeypatch):
    """The auditor's DC-01 interleaving at the handle: B published whole after A's result was read, before its record was.
    The version is all of B, never A's result with B's record and evidence."""
    folder = tmp_path / "study"
    a, b = versions(folder)
    publish(folder, a, "A")
    real, fired = version._read, []

    def read(path, limit=None):
        found = real(path, limit)
        if Path(path).name == "result.json" and not fired:
            fired.append(True)
            publish(folder, b, "B")
        return found
    monkeypatch.setattr(version, "_read", read)
    found = resolve(folder)
    assert fired and found.study().title == "B study" and found.record_state == "bound"
    assert found.evidence_state == "bound" and found.typed() == build.read_saved(folder / "result.json").result


def test_a_folder_that_never_settles_is_refused(tmp_path, monkeypatch):
    folder = tmp_path / "study"
    a, b = versions(folder)
    publish(folder, a, "A")
    real, turn = version._read, [0]

    def read(path, limit=None):
        found = real(path, limit)
        if Path(path).name == "study.json":
            turn[0] += 1
            studies.save(studies.load(folder).model_copy(update={"title": f"title {turn[0]}"}))
        return found
    monkeypatch.setattr(version, "_read", read)
    with pytest.raises(Unsettled):
        resolve(folder)


# --- the graph ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["as recorded", "child replaced", "parent replaced", "child absent", "legacy"])
def test_a_promotion_s_edges_resolve_to_the_versions_its_record_names(tmp_path, case):
    """``follow``: each edge to the version the promotion records, or named unavailable (another version saved there,
    or none), never followed in its place; a record keeping no digests followed as found."""
    path, b, parent = _promotion(tmp_path / "graph", recorded=case != "legacy")
    child_sha = sha((tmp_path / "graph" / "child" / "result.json").read_bytes())
    if case == "child replaced":
        publish(tmp_path / "graph" / "child", b, "B child")
    elif case == "parent replaced":
        other = parent.model_copy(update={"max_local_z": 1.0})
        build.publish(path.parent / "result.json", other.model_dump_json().encode(), other, lambda e: "Parent B",
                      workflow="signal")
    elif case == "child absent":
        shutil.rmtree(tmp_path / "graph" / "child")
    promotion = resolve(path)
    assert promotion.record_state == "absent"            # the fixture's parent has no study record
    followed = {f.edge.role: f for f in version.follow(promotion)}
    if case in ("as recorded", "legacy"):
        assert followed["child"].version.result_sha256 == child_sha and not followed["child"].note
        assert followed["parent"].version is not None
    elif case == "child replaced":
        assert followed["child"].version is None and "now saved is another version" in followed["child"].note
    elif case == "child absent":
        assert followed["child"].version is None and "is not saved" in followed["child"].note
    else:
        assert followed["parent"].version is None and "the parent result now saved is another version" in \
            followed["parent"].note


# --- the untouched historical exports, as saved folders -------------------------------------------------------------


def _unpack(bundle: Path, into: Path) -> list[tuple[Path, str, bool]]:
    """Each node of an untouched export written back as the saved folder it came from: its result under its original
    name (a promotion's from its report's), its evidence beside it, its report and study record. (folder's result file,
    workflow, whether it has a study record)."""
    out = []
    with zipfile.ZipFile(bundle) as z:
        manifest = json.loads(z.read("manifest.json"))
        names = z.namelist()
        for node in manifest["nodes"]:
            prefix = f"studies/{node['id']}/"
            folder = into / node["id"]
            folder.mkdir(parents=True)
            reports = [n for n in names if n.startswith(prefix) and n.endswith(".md") and "/review_queue" not in n
                       and "/" not in n[len(prefix):]]
            stem = Path(reports[0]).stem if reports and node["workflow"] == "promotion" else "result"
            target = folder / f"{stem}.json"
            target.write_bytes(z.read(prefix + "result.json"))
            build.sidecar_path(target).write_bytes(z.read(prefix + "evidence.json"))
            for name in reports:
                (folder / Path(name).name).write_bytes(z.read(name))
            if prefix + "study.json" in names:
                (folder / "study.json").write_bytes(z.read(prefix + "study.json"))
            out.append((target, node["workflow"], prefix + "study.json" in names))
    return out


@pytest.mark.parametrize("name", sorted(p.name for p in BUNDLES.glob("*.zip")))
def test_each_untouched_export_resolves_as_the_folders_it_came_from(tmp_path, name):
    """L at the handle: each historical export's nodes, written back as saved folders, resolve with their evidence
    bound; a record from before records named their results (before 3f00efc) is "unbound", as found; a later one
    "bound"; a report "bound" where it records its result. Read without its sidecar, a result is legacy, rebuilt, said
    so, and its bytes are never rewritten."""
    records_name = name.endswith("3f00efc.zip")
    for target, workflow, has_record in _unpack(BUNDLES / name, tmp_path):
        before = target.read_bytes()
        found = resolve(target, presentation=True)
        assert found.evidence_state == "bound", found.evidence_why
        assert found.workflow == workflow
        if has_record:
            assert found.record_state == ("bound" if records_name else "unbound")
        assert found.report().state in ("bound", "absent")
        build.sidecar_path(target).unlink()
        legacy = resolve(target)
        assert legacy.evidence_state == "legacy" and legacy.identity("evidence") == NONE
        assert target.read_bytes() == before and not build.sidecar_path(target).exists()

"""The version handle's acceptance matrix, run (``tests/version_matrix.py`` fixes its rows, cases and each cell's
expected outcome; ``docs/version_matrix.md`` writes them out): every cell of the rows that are not pages, each executed
here or marked not applicable with its reason, and the negative controls showing that the harness detects each fault it
tests. The pages' rows run in ``tests/ui/test_version_matrix_pages.py``. Each study is written by the production
writers; nothing is calculated and no request is sent (the agents' calls are stood in for, as their own tests do)."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests import version_matrix as vm

REFERENCE = vm.REFERENCE
PAGES = {row.id for row in vm.ROWS if row.page}


def _cells(kinds: tuple[str, ...]) -> list:
    return [pytest.param(row, case, id=f"{row}-{case}") for row, case, _ in vm.cells()
            if vm.BY_ID[row].kind in kinds and row not in PAGES]


# --- the held rows: each resolves the study itself ---------------------------------------------------------------

def _cli(done):
    """A command's output, or its refusal: its own message where it raised, else what it printed."""
    if done.exit_code:
        if done.exception is not None and not isinstance(done.exception, SystemExit):
            raise ValueError(str(done.exception) or type(done.exception).__name__)
        raise ValueError(done.output)
    return done.output


def _held(row_id: str, world: vm.World, tmp: Path):
    """The output of a held row, read now."""
    from adroit.orchestrator import annotations, studies
    root, folder = world.root, world.folder
    if row_id == "history.facts":
        return annotations.held_facts(root, studies.load(folder))[0]
    if row_id == "cli.studies":
        from adroit.orchestrator.cli import app
        return _cli(CliRunner().invoke(app, ["studies", str(root)]))
    if row_id == "pickers.track1":
        from adroit.ui.wizards import _track1_studies
        return _track1_studies(root)
    if row_id == "pickers.reanalysis":
        from adroit.ui import reanalysis
        with patch("adroit.ui.model_library.options", return_value={}):
            return reanalysis._sources(root)
    if row_id == "models.analyses":
        from adroit.orchestrator.study_headline import listed
        from adroit.ui.model_library import analyses
        return [listed(found) for found in analyses(root, REFERENCE)]
    if row_id == "study.cost":
        from adroit.orchestrator.study_headline import held
        from adroit.ui.pages import study_cost
        return study_cost(held(folder))
    if row_id == "setup.estimate":
        from adroit.orchestrator.setup_check import estimate
        rate, _ = estimate("track1", "vector", 1, root)      # A: 100 s over 4 points; B: 900 s over 4
        return {25.0: "MatrixRecordA", 225.0: "MatrixRecordB"}.get(rate, f"rate {rate}")
    if row_id == "revisit.updates":
        from adroit.library.experimental import ExperimentalCatalog
        from adroit.library.personal import Catalog
        from adroit.orchestrator import revisit
        changed = lambda study, key, models: [revisit.Update(study=key, title=study.title, kind="model",  # noqa: E731
                                                             old="r1", new="r2")]
        with patch.object(revisit, "_models", changed):
            return revisit.updates(root, ExperimentalCatalog(tmp / "private"), Catalog(tmp / "models"))
    if row_id == "classic.report":
        from adroit.workbench.server import report_view
        return report_view(folder)
    if row_id == "live.report":
        from adroit.ui.pages import _live_report
        return _live_report(folder, "file")
    if row_id == "export.cli":
        from adroit.evidence.cli import app
        out = tmp / f"export{len(list(tmp.glob('export*')))}.zip"
        _cli(CliRunner().invoke(app, ["export", str(folder), "--out", str(out)]))
        return out.read_bytes()
    if row_id in ("point.cli", "tables.cli", "figures.cli"):
        from adroit.evidence.cli import app
        if row_id == "point.cli":
            return _cli(CliRunner().invoke(app, ["point", str(folder), "--point", "grid:0"]))
        out = tmp / f"{row_id}{len(list(tmp.glob(row_id + '*')))}"
        _cli(CliRunner().invoke(app, [row_id.removesuffix(".cli"), str(folder), "--out", str(out)]))
        return {p.name: p.read_bytes() for p in sorted(out.iterdir())}
    if row_id == "review.queue":
        from adroit.constraints.review_queue import load_selected
        return load_selected(folder)
    if row_id == "agents.saved":
        from adroit.orchestrator import agents
        from adroit.orchestrator.cli import app
        out = tmp / f"agents{len(list(tmp.glob('agents*')))}"
        with patch.dict(agents.RUNNERS, {"track1": lambda r, llm, *a: agents.AgentResult(subject="track1")}):
            _cli(CliRunner().invoke(app, ["agents", str(world.path), "--budget", "0.1", "--out", str(out)]))
        return (out / "report.md").read_text()
    if row_id == "assist.saved":                # its deterministic templates, $0: no provider
        from adroit.orchestrator.cli import app
        out = tmp / f"assist{len(list(tmp.glob('assist*')))}"
        text = _cli(CliRunner().invoke(app, ["assist", str(world.folder), "--out", str(out), "--budget", "0"]))
        return [text, (out / "request.json").read_text()]
    if row_id == "reuse.track1":
        from adroit.orchestrator.physical_eligibility import _saved
        a = world.a
        request = SimpleNamespace(track1_results=[str(world.path)], experimental_profile=a.request.experimental_profile,
                                  unverified_records=a.request.unverified_records)
        model = SimpleNamespace(spec=a.request.spec, catalog_reference=a.request.catalog_reference)
        row, _, digests, notes = _saved(request, model, a.scan.request.model_class, a.scan.points[0].point,
                                        world.context)
        if row is None:
            raise ValueError("; ".join(notes))
        return [row.model_dump_json(), *digests]
    raise ValueError(f"no held row {row_id}")


@pytest.mark.parametrize("row_id, case", _cells(("held",)))
def test_a_held_row(tmp_path, row_id, case):
    row = vm.BY_ID[row_id]
    wanted = vm.expected(row, case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    if case == "W":
        found = _destinations(tmp_path, row_id)
        assert found == wanted, f"{row_id} × {case}: expected {wanted}, observed {found}"
        return
    world = vm.world_for(row_id, tmp_path, legacy=case == "L")
    with vm.at(world, case):
        out = vm.run(lambda: _held(row_id, world, tmp_path))
    found = vm.outcome(world, out, vm.required(row, case), exact=case == "B")
    assert vm.agrees(found, wanted), f"{row_id} × {case}: expected {wanted}, observed {found}: {out.refused or out.text[:600]}"


def _destinations(tmp: Path, row_id: str) -> str:
    """W for a bundle's export to a new path (DL-05): A's export, its row's (``adroit evidence export``, or the
    study page's download), prepared, and B's completed meanwhile, at A's temporary file. The command's two exports
    name one new path: A's is refused, and B's bundle is left as B's export returned it, B's whole. The downloads are
    each written in a folder of their own: each returns its own version's bundle, whole. "one owner", or what was
    seen."""
    from adroit.evidence import archive
    from adroit.evidence.cli import app as evidence
    from adroit.ui.exports import files
    a, b = vm.make(tmp / "a"), vm.make(tmp / "b")
    vm.publish(b, "B")
    real, returned = archive.tempfile.NamedTemporaryFile, {}
    destination = tmp / "one.zip"
    if row_id == "export.cli":
        def other() -> bytes:
            done = CliRunner().invoke(evidence, ["export", str(b.folder), "--out", str(destination)])
            assert done.exit_code == 0, done.output
            return destination.read_bytes()
        mine = lambda: CliRunner().invoke(evidence, ["export", str(a.folder), "--out", str(destination)])  # noqa: E731
    else:
        tokens = {label: _token(world, vm.BY_ID[row_id]) for label, world in (("A", a), ("B", b))}
        other = lambda: files("bundle", tokens["B"])[1]                                         # noqa: E731
        mine = lambda: files("bundle", tokens["A"])[1]                                          # noqa: E731

    def meanwhile(*args, **kwargs):
        if not returned:
            with patch.object(archive.tempfile, "NamedTemporaryFile", real):
                returned["B"] = other()
        return real(*args, **kwargs)
    with patch.object(archive.tempfile, "NamedTemporaryFile", meanwhile):
        done = mine()
    theirs = vm.outcome(b, vm.Output(vm.text_of(returned["B"])), vm.PARTS)
    if row_id == "export.cli":
        said = " ".join(done.output.translate(str.maketrans("│╭╮╰╯─", "      ")).split())
        kept = destination.read_bytes() == returned["B"]
        refused = done.exit_code == 2 and "written by another export while this one was prepared" in said
        return "one owner" if refused and kept and theirs == "B" else \
            f"A's export exit {done.exit_code} ({said[-160:]}); B's bundle kept: {kept}, {theirs}"
    ours = vm.outcome(a, vm.Output(vm.text_of(done)), vm.PARTS)
    return "one owner" if vm.agrees(ours, "A") and theirs == "B" else f"A's download {ours}; B's {theirs}"


# --- the token rows: each acts on the version its page named -----------------------------------------------------

def _token(world: vm.World, row: vm.Row):
    """The page's version of the study, as a token naming the parts this row requires."""
    from adroit.evidence.version import Token, resolve
    held = resolve(world.folder, presentation=True).token()
    return Token(held.path, **{part: getattr(held, part) for part in row.needs})


def _taken(row_id: str, world: vm.World, tmp: Path):
    """What a token row takes from the page before anything changes: its token, and for the draft and the card, what
    they hold."""
    from adroit.evidence.version import Token, resolve
    row = vm.BY_ID[row_id]
    token = _token(world, row)
    if row_id == "reanalysis.preview":
        from adroit.library.personal import Catalog
        from adroit.orchestrator.reanalysis import Reanalysis
        service = Reanalysis(Catalog(tmp / "catalog"))
        return service, service.open(str(world.path), token=token)
    if row_id == "revisit.card":
        from adroit.library.experimental import ExperimentalCatalog
        from adroit.library.personal import Catalog
        from adroit.orchestrator import revisit
        changed = lambda study, key, models: [revisit.Update(study=key, title=study.title, kind="model",  # noqa: E731
                                                             old="r1", new="r2")]
        with patch.object(revisit, "_models", changed):
            (update,) = revisit.for_study(world.root, resolve(world.folder), ExperimentalCatalog(tmp / "private"),
                                          Catalog(tmp / "models"))
        return Token(str(world.path), update.sha256, update.evidence)
    return token


def _act(row_id: str, world: vm.World, taken, tmp: Path):
    """A token row's action, on what it took."""
    if row_id == "point.link":
        from adroit.evidence.points import explain
        return explain(taken, "grid:0")
    if row_id.startswith("download."):
        from adroit.ui.exports import files
        return files(row_id.removeprefix("download."), taken)[1]
    if row_id in ("reanalysis.open", "revisit.card"):
        from adroit.library.personal import Catalog
        from adroit.orchestrator.reanalysis import Reanalysis
        return Reanalysis(Catalog(tmp / "catalog")).open(str(world.path), token=taken)
    if row_id == "reanalysis.preview":
        service, draft = taken
        review = service.preview(draft.reference)
        parent = [b for b in review["blockers"] if "parent study" in b or "changed each time" in b]
        if parent:
            raise ValueError(parent[0])
        return draft
    if row_id == "classic.file":
        from http import HTTPStatus
        from adroit.workbench import server
        data, status, _ = server.route(SimpleNamespace(runs_dir=world.root),
                                       f"/file/study/result.json?sha256={taken.result}")
        if status is HTTPStatus.CONFLICT:
            raise ValueError(f"the study's result {data}")
        return data
    if row_id == "promote.parent":
        from adroit.orchestrator.promote import parent_result
        result, digest = parent_result(world.folder, taken.result)
        return digest
    raise ValueError(f"no token row {row_id}")


def _signal_world(tmp: Path) -> vm.World:
    """The promotion's parent: a signal study published as A (``promote.parent``); B, another. Its marks are its
    digests (``World.identities``)."""
    from adroit.evidence import build
    from adroit.inference.dm_tournament import run as empty_tournament
    from adroit.orchestrator import studies
    from adroit.orchestrator.signal import SignalRequest, SignalResult
    folder = tmp / "runs" / "study"
    folder.mkdir(parents=True)
    a = SignalResult(request=SignalRequest(experiment="MatrixResultA"), fits=[], classes={}, n_classes=0,
                     max_local_z=0, global_p_toys=1, global_p_closed_form=None, global_z=0, combinations=[],
                     tournament=empty_tournament([]), separations=[])
    b = a.model_copy(update={"request": SignalRequest(experiment="MatrixResultB"), "max_local_z": 1.0})
    world = vm.World(tmp / "runs", folder, a, b)

    def publish(label: str, **_):
        result = a if label == "A" else b
        content = result.model_dump_json().encode()
        build.publish(folder / "result.json", content, result, lambda e: f"MatrixReport{label}", workflow="signal")
        studies.record(folder, "signal", f"MatrixRecord{label}", result_sha256=vm.sha(content))
        world.identities[label] = {"result": {vm.sha(content)}}
    world.publish = publish
    publish("A")
    return world


def _change(world: vm.World, case: str) -> None:
    if getattr(world, "publish", None) is not None and case == "R":
        world.publish("B")
    else:
        vm.change(world, case)


@pytest.mark.parametrize("row_id, case", _cells(("token",)))
def test_a_token_row(tmp_path, row_id, case):
    from tests.version_events import after_resolution
    row = vm.BY_ID[row_id]
    wanted = vm.expected(row, case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    if case == "W":
        found = _destinations(tmp_path, row_id)
        assert found == wanted, f"{row_id} × {case}: expected {wanted}, observed {found}"
        return
    world = _signal_world(tmp_path) if row_id == "promote.parent" else vm.make(tmp_path, legacy=case == "L")
    taken = _taken(row_id, world, tmp_path)
    if case == "ABA":
        found = _aba(row_id, world, taken, tmp_path)
    else:
        if case in vm.CHANGED:
            _change(world, case)
        if case == "T1":
            from tests.version_events import during_resolution
            publish = getattr(world, "publish", None) or (lambda label: vm.publish(world, label))
            context = during_resolution("result.json", lambda: publish("B"))
        elif case == "T2":
            publish = getattr(world, "publish", None) or (lambda label: vm.publish(world, label))
            context = after_resolution(lambda: publish("B"))
        elif case == "T3":
            context = vm.always(world) if getattr(world, "publish", None) is None else _always_signal(world)
        else:
            context = _nothing()
        with context:
            out = vm.run(lambda: _act(row_id, world, taken, tmp_path))
        found = vm.outcome(world, out, vm.required(row, case), exact=case == "B")
    assert vm.agrees(found, wanted), f"{row_id} × {case}: expected {wanted}, observed {found}: {out.refused if case != 'ABA' else ''}"


def _aba(row_id: str, world: vm.World, taken, tmp: Path) -> str:
    """A, then B, then A's very bytes restored: the token's version again; then A's record written anew (another date):
    another version where the token names the record."""
    from adroit.core.durable import write_atomic
    from adroit.orchestrator import studies
    kept = {p.name: p.read_bytes() for p in world.folder.iterdir() if p.is_file()}
    (world.publish if getattr(world, "publish", None) else lambda label: vm.publish(world, label))("B")
    for name, data in kept.items():
        write_atomic(world.folder / name, data)
    first = vm.outcome(world, vm.run(lambda: _act(row_id, world, taken, tmp)), vm.BY_ID[row_id].shows)
    record = studies.load(world.folder)
    studies.save(record.model_copy(update={"created": "2026-11-05T00:00:00+00:00"}))
    second = vm.outcome(world, vm.run(lambda: _act(row_id, world, taken, tmp)), vm.BY_ID[row_id].shows)
    if first.startswith("A") and second.startswith("refused"):
        return "A then refused"
    return first if first == second else f"{first}, then {second}"


class _nothing:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def _always_signal(world: vm.World):
    from adroit.evidence import version
    real, turn = version._read, [0]

    def read(path, limit=None):
        found = real(path, limit)
        if Path(path).name == "result.json" and Path(path).parent == world.folder:
            turn[0] += 1
            world.publish("AB"[turn[0] % 2])
        return found
    return patch.object(version, "_read", read)


# --- the publication row: what follows a publication requires the version its writer wrote -----------------------

def _reanalysis(tmp: Path, after=None, during=None) -> tuple[vm.World, vm.Output, dict]:
    """A reanalysis of a signal study (``_signal_world``) run into its child folder by the production path (its draft,
    its lineage, ``runs._write``, its check), its calculation, review and catalogue stood in for (the auditor's control,
    DD-01). ``after(world)``: a change made once its writer has published; ``during(world)``: a context in which it
    publishes. (the child's world: A as the run published it, B another publication there; the run's output, the
    child's parts by their identities as it left them; B's files as B left them, where B was published.)"""
    from contextlib import nullcontext
    from adroit.core.evidence import EvidenceContext
    from adroit.evidence import runtime
    from adroit.evidence.version import resolve
    from adroit.library.personal import Catalog
    from adroit.orchestrator import runs, signal
    from adroit.orchestrator.reanalysis import Reanalysis
    parent = _signal_world(tmp)
    service = Reanalysis(Catalog(tmp / "catalog"))
    draft = service.open(str(parent.path))
    world = vm.World(parent.root, parent.folder / "child", parent.a, parent.b, kind="signal")
    real, left = runs._write, {}

    def write(folder, result, *args, **kw):
        text = real(folder, result, *args, **kw)
        if kw.get("published") is not None and Path(folder) == world.folder:
            world.identities["A"] = {part: {v, v[:12]} for part, v in kw["published"]["token"].named().items()
                                     if len(v) == 64}
            if after is not None:
                after(world)
                if world.identities.get("B"):
                    left.update(_files(world.folder))
        return text
    review = {"review_sha256": "simulated-review", "blockers": []}
    with patch.object(service, "preview", return_value=review), \
            patch.object(service, "_catalogue_models", side_effect=lambda request, *a: request), \
            patch.object(runtime, "capture_request", return_value=EvidenceContext(notes=["simulated, $0"])), \
            patch.object(signal, "run", return_value=parent.a), \
            patch.object(signal, "report", return_value="MatrixReportA body"), \
            patch.object(runs, "_write", write), (during(world) if during else nullcontext()):
        out = vm.run(lambda: service.run(draft.reference, world.folder, "simulated-review", confirmed=True,
                                         reviewer="SIMULATED")[1])
    if not out.refused:                 # the child as the run left it: its parts by their identities, its report
        found = resolve(world.folder, presentation=True)
        lineage = found.envelope().certificates.get("reanalysis_lineage")
        assert lineage and lineage == json.loads((world.folder / "reanalysis.json").read_text()), "its lineage"
        out = vm.Output(vm.text_of([out.text, found.token().text(), found.content]))
    return world, out, left


def _changed(case: str):
    """The change of a generic case, made once the run's writer has published A, by a process outside ADROIT's writers
    (``vm.outside``: ADROIT's own wait for the run, or are refused, its case W): B whole (R), or a part of it."""
    def change(world):
        with vm.outside():
            if case == "R":
                vm.publish(world, "B")
            else:
                world.identities["B"] = {}
                vm.change(world, case)
    return change


@contextmanager
def _while_published(world: vm.World):
    """T1: B published whole in the child's folder while the run's writer publishes A, once A's evidence is written,
    by a process outside ADROIT's writers; its files as it left them kept (``world.left``), for the run to leave so."""
    from adroit.evidence import build
    real, done = build.save, []

    def save(result_path, *args, **kw):
        envelope = real(result_path, *args, **kw)
        if not done and Path(result_path) == world.path:
            done.append(True)
            with vm.outside():
                vm.publish(world, "B")
            world.left = _files(world.folder)
        return envelope
    with patch.object(build, "save", save):
        yield


@contextmanager
def _always(world: vm.World):
    """T3: the child's files replaced at every reading once its writer has published (``vm.always``), by a process
    outside ADROIT's writers."""
    with vm.always(world, by_another=True):
        yield


def _files(folder: Path) -> dict[str, bytes]:
    """A folder's files as bytes (its publication lock aside, which holds nothing)."""
    from adroit.core.durable import PUBLICATION_LOCK
    return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file() and p.name != PUBLICATION_LOCK}


def _restored(world: vm.World) -> None:
    """ABA, first: B published, then A's very bytes restored, by a process outside ADROIT's writers."""
    from adroit.core.durable import write_atomic
    kept = _files(world.folder)
    with vm.outside():
        vm.publish(world, "B")
    for name, data in kept.items():
        write_atomic(world.folder / name, data)


def _rewritten(world: vm.World) -> None:
    """ABA, then: A's record written anew (another date), by a process outside ADROIT's writers."""
    from adroit.orchestrator import studies
    record = studies.load(world.folder)
    with vm.outside():
        studies.save(record.model_copy(update={"created": "2026-11-05T00:00:00+00:00"}))


@pytest.mark.parametrize("row_id, case", _cells(("publication",)))
def test_a_publication_row(tmp_path, row_id, case):
    """A reanalysis's child: its lineage is in the evidence it was first published with, and the run returns only where
    its folder still holds what it published; otherwise it refuses, naming the part, and adds nothing to another
    publication (the auditor's version-handle audit, DD-01)."""
    from adroit.evidence.version import resolve
    row = vm.BY_ID[row_id]
    wanted = vm.expected(row, case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    if case == "W":                     # ADROIT's own writers (the auditor's DD recheck, DE-02), its regression tests
        _writer_cells(tmp_path)
        return
    if case == "ABA":
        first = vm.outcome(*_reanalysis(tmp_path / "restored", after=_restored)[:2], row.shows)
        second = vm.outcome(*_reanalysis(tmp_path / "rewritten", after=_rewritten)[:2], row.shows)
        found = ("A then refused" if vm.agrees(first, "A") and second == "refused:record"
                 else f"{first}, then {second}")
        out = vm.Output()
    else:
        after = _changed(case) if case in vm.CHANGED else None
        during = {"T1": _while_published, "T3": _always}.get(case)
        world, out, left = _reanalysis(tmp_path, after=after, during=during)
        found = vm.outcome(world, out, row.shows, exact=case == "B")
        left = left or getattr(world, "left", {})
        if left:                        # nothing added to another publication: B's files as B left them (DE-02)
            assert _files(world.folder) == left, case
        held = resolve(world.folder) if out.refused and world.path.exists() else None
        if held is not None and held.result_sha256 not in world.identities.get("A", {}).get("result", set()):
            assert held.evidence_state != "bound" or "reanalysis_lineage" not in held.envelope().certificates, \
                "its lineage on another version"
        if case == "T1":                # and between each pair of its parts, B left byte for byte (DE-02)
            _edge_cells(tmp_path)
    assert vm.agrees(found, wanted), f"{row_id} × {case}: expected {wanted}, observed {found}: {out.refused[:300]}"


# --- the packet row: a calibrated review packet, written whole and read whole (DH-01) ------------------------------

@pytest.mark.parametrize("row_id, case", _cells(("packet",)))
def test_a_packet_row(tmp_path, row_id, case):
    """A calibrated review packet (``review.packet``): its baseline read as its writer wrote it; its overlay replaced
    since (P), and another packet written whole while it is read (T1), refused as changed; and W, another packet writer
    into its folder at its overlay's return, from another thread and another process, waiting for it, and the packet
    command's listing written under the same hold (``test_dh_fixes``; the auditor's DG recheck, DH-01); and each of its
    files a link into another folder, with that folder held or its own, from another thread and another process,
    written to its own entry (``test_di_fixes``; the auditor's DH recheck, DI-03)."""
    from tests.orchestrator import test_dh_fixes as dh
    from tests.orchestrator import test_di_fixes as di
    wanted = vm.expected(vm.BY_ID[row_id], case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    if case == "W":
        for by in ("another thread", "another process"):
            dh.test_a_review_packet_is_its_writer_s_whole(_fresh(tmp_path), by)
        with pytest.MonkeyPatch.context() as monkeypatch:
            dh.test_a_review_packet_and_its_review_listing_are_one_writer_s(_fresh(tmp_path), monkeypatch)
        for by in ("another thread", "another process"):
            for held in ("its target's folder", "its own folder"):
                for name in di.MEMBERS:
                    di.test_a_packet_member_that_is_a_link_is_written_in_its_own_folder(_fresh(tmp_path), by, held,
                                                                                         name)
        return
    {"B": dh.test_a_review_packet_is_read_as_its_writer_wrote_it,
     "P": dh.test_a_review_packet_s_overlay_replaced_since_is_refused,
     "T1": dh.test_a_review_packet_read_while_another_is_written_is_refused}[case](tmp_path)



# --- the export rows: written whole into a folder a person names (DJ-01; DK-01, DK-02, DK-05) ---------------------

def _session_writers(tmp: Path) -> None:
    """The session export's W: another session's export into its folder at its first file's return, from another
    thread and another process; each of the auditor's four commands refused into a saved study's folder, held by another
    process or not, from the installed command and in this process, writing nothing there, the study's cost the same;
    and a stopped run's record waiting while a study is published there, refused (``test_dk_fixes``; DK-01); and an
    export of another kind into its folder, or its export into another kind's, refused, the first whole
    (``test_dm_fixes``; DM-03)."""
    from tests.orchestrator import test_dk_fixes as dk
    for by in ("another thread", "another process"):
        dk.test_a_session_export_and_its_request_record_are_one_export(_fresh(tmp), by)
    _refusals(tmp)
    dk.test_a_study_published_while_a_stopped_run_waits_refuses_its_record(_fresh(tmp))
    _other_kinds(tmp, "a discovery's")


def _other_kinds(tmp: Path, kind: str) -> None:
    """An export of another kind into the folder of one of ``kind``, and one of ``kind`` into another's (the review,
    the queue as ``report.json``, a discovery's, a theory check's): refused, saying so, the first whole, a review
    packet still read whole by the review timer (``test_dm_fixes``; the auditor's DL recheck, DM-03)."""
    from tests.orchestrator import test_dm_fixes as dm
    for first, then in dm.PAIRS:
        if kind in (first, then):
            dm.test_an_export_of_another_kind_never_replaces_part_of_one_in_its_folder(_fresh(tmp), first, then)


def _refusals(tmp: Path) -> None:
    """The auditor's four commands refused into a saved study's folder: nothing written, its cost the same (DK-01)."""
    from tests.orchestrator import test_dk_fixes as dk
    for command in dk.COMMANDS:
        for held in dk.HELD:
            for where in dk.WHERE:
                dk.test_a_command_refused_into_a_saved_study_s_folder_changes_nothing(_fresh(tmp), command, held, where)


def _damaged_records(tmp: Path) -> None:
    """A survey run's request record damaged (torn, null, a list, an empty object) beside an earlier survey's
    discovery.json: no figure without a record bound to the run; with its log or its command, its own session's; and a
    run from before request records, its discovery.json's (``test_dm_fixes``; the auditor's DL recheck, DM-01). And its
    request record, or its log, a link that leads nowhere (to a missing file, to itself, through a file): the same, the
    record named, the run's continuation agreeing (``test_dn_fixes``; the auditor's DM recheck, DN-01)."""
    from tests.orchestrator import test_dm_fixes as dm
    for damage in dm.DAMAGED:
        with pytest.MonkeyPatch.context() as monkeypatch:
            dm.test_a_damaged_request_record_charges_the_run_with_no_session(_fresh(tmp), monkeypatch, damage)
        for bound in ("its log", "its command"):
            with pytest.MonkeyPatch.context() as monkeypatch:
                dm.test_a_damaged_request_record_beside_a_bound_record_is_charged_with_that_session(
                    _fresh(tmp), monkeypatch, damage, bound)
    with pytest.MonkeyPatch.context() as monkeypatch:
        dm.test_a_damaged_request_record_beside_a_log_that_names_no_run_charges_no_session(_fresh(tmp), monkeypatch)
    for record in ("none", "one naming no run"):
        with pytest.MonkeyPatch.context() as monkeypatch:
            dm.test_a_run_from_before_the_request_record_is_still_charged_with_its_discovery_json_s_session(
                _fresh(tmp), monkeypatch, record)
    from tests.orchestrator import test_dn_fixes as dn          # a record that is a link leading nowhere (DN-01)
    for link in dn.LINKS:
        with pytest.MonkeyPatch.context() as monkeypatch:
            dn.test_a_request_record_that_leads_nowhere_charges_the_run_with_no_session(_fresh(tmp), monkeypatch, link)
        for bound in ("its log", "its command"):
            with pytest.MonkeyPatch.context() as monkeypatch:
                dn.test_a_request_record_that_leads_nowhere_beside_a_bound_record_is_charged_with_that_session(
                    _fresh(tmp), monkeypatch, link, bound)
        for receipt in ("none", "one bound to the run"):
            with pytest.MonkeyPatch.context() as monkeypatch:
                dn.test_a_log_that_leads_nowhere_is_damage_not_a_run_from_before_logs(_fresh(tmp), monkeypatch, link,
                                                                                      receipt)


def _failures(tmp: Path, row_id: str) -> None:
    """F: the export's replacement failing once before or after each of its files (the earlier export whole, put
    back), and its writer killed after its first file (the folder incomplete, read so by each reader of it), from
    ``test_dk_fixes`` (DK-05); its mark failing, written, removed or rewritten (said, and the folder as it says), and,
    after a killed writer, another export into the folder keeping the mark (a review's, then the queue's, another
    export's or one of some of its files), or a session's run charged with the session its own records name, from
    ``test_dl_fixes`` (DL-02, DL-03, DL-04); and its request record damaged, no session without a record bound to the
    run (``_damaged_records``, DM-01)."""
    from tests.orchestrator import test_dk_fixes as dk
    from tests.orchestrator import test_dl_fixes as dl
    for when in ("before", "after"):
        if row_id == "records.export":
            for name in ("record_review.json", "report.md", "current_curves.png"):
                dk.test_a_review_export_failing_part_way_leaves_the_earlier_packet_whole(_fresh(tmp), name, when)
        elif row_id == "queue.export":
            for name in ("queue.json", "queue.md"):
                dk.test_a_queue_export_failing_part_way_leaves_the_earlier_queue_whole(_fresh(tmp), name, when)
        else:
            for name in (dk.REQUESTS, *dk.DRAFT_FILES):
                dk.test_a_session_export_failing_part_way_leaves_the_earlier_one_whole(_fresh(tmp), name, when)
    dk.test_an_export_whose_writer_is_killed_part_way_reads_as_incomplete(_fresh(tmp))
    if row_id == "session.export":
        for command in ("resume", "discover"):
            for killed in dl.KILLED:
                with pytest.MonkeyPatch.context() as monkeypatch:
                    dl.test_an_interrupted_discovery_is_charged_with_its_own_session(_fresh(tmp), monkeypatch, command,
                                                                                     killed)
        with pytest.MonkeyPatch.context() as monkeypatch:
            dl.test_a_discovery_whose_session_is_not_established_shows_no_figure(_fresh(tmp), monkeypatch)
        _damaged_records(tmp)
    else:
        for other in dl.OTHERS:
            dl.test_another_export_into_the_folder_keeps_an_interrupted_export_s_mark(_fresh(tmp), other)
        dl.test_an_export_removes_only_the_interrupted_exports_it_writes_again(_fresh(tmp))
    for step, when in dl.MARK_STEPS:
        dl.test_an_export_whose_mark_fails_says_what_it_left(_fresh(tmp), step, when)


@pytest.mark.parametrize("row_id, case", _cells(("export",)))
def test_an_export_row(tmp_path, row_id, case):
    """A curated record's review export (``records.export``), the review queue's (``queue.export``) and a session
    command's (``session.export``): B, each written whole, a later export replacing it whole (a record with no figure
    leaving none of an earlier one's); the review's T1, its record, or its data file at either of its reads, changed
    while it is prepared, refused, nothing written; its ABA, its data file B at either read and A's very bytes restored,
    the export A's whole; W, another export into its folder at its first file's return, from another thread and
    another process, waiting for it, each of its files a link into another folder, with that folder held or its own,
    written to its own entry, the installed command's export beside a held study reached through a link, and, for a
    session command's, the auditor's four commands refused into a saved study's folder (``test_dj_fixes``, DJ-01;
    ``test_dk_fixes``, DK-01 and DK-02; its approval of its reading, ``test_dl_fixes``, DL-01), and an export of another
    kind into its folder, after it or at once, or an entry there no export recorded, refused, the review timer reading
    the packet whole only as written (``test_dm_fixes``, DM-03); and F, its replacement failing part way or its writer
    killed (DK-05), its mark failing, and another export or the cost reader after it (DL-02 to DL-04), its request
    record damaged (DM-01)."""
    from tests.orchestrator import test_dj_fixes as dj, test_dk_fixes as dk, test_dl_fixes as dl, test_dm_fixes as dm
    wanted = vm.expected(vm.BY_ID[row_id], case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    if case == "F":
        _failures(tmp_path, row_id)
        return
    if row_id == "session.export":
        if case == "B":
            dk.test_a_session_export_is_its_request_record_and_its_files_whole(_fresh(tmp_path))
            dk.test_a_stopped_run_records_its_own_requests_and_no_earlier_draft_beside_them(_fresh(tmp_path))
        else:
            _session_writers(tmp_path)
        return
    command = "review" if row_id == "records.export" else "queue"
    if case == "B":
        (dj.test_an_export_replaces_an_earlier_one_whole if command == "review" else
         dj.test_a_queue_export_is_its_queue_whole)(tmp_path)
    elif case in ("T1", "ABA"):
        if case == "T1":
            dj.test_a_record_changed_while_its_review_is_prepared_is_refused(_fresh(tmp_path))
        for boundary in dk.BOUNDARIES:
            with pytest.MonkeyPatch.context() as monkeypatch:
                (dk.test_a_review_whose_data_changed_while_it_was_prepared_is_refused if case == "T1" else
                 dk.test_a_review_export_is_one_reading_of_its_record_and_data)(_fresh(tmp_path), monkeypatch,
                                                                                 boundary)
        for captured in "AB":           # its approval: one status, of its reading, signed A or stale B (DL-01)
            with pytest.MonkeyPatch.context() as monkeypatch:
                (dl.test_a_packet_s_review_state_and_its_binding_are_one_status if case == "T1" else
                 dl.test_a_review_export_s_approval_is_of_the_version_it_read)(_fresh(tmp_path), monkeypatch, captured)
    else:
        for by in ("another thread", "another process"):
            (dj.test_a_curated_review_export_is_one_record_s_whole if command == "review" else
             dj.test_a_queue_export_is_one_queue_s_whole)(_fresh(tmp_path), by)
            for held in ("its target's folder", "its own folder"):
                for which, name in dj.MEMBERS:
                    if which == command:
                        dj.test_an_export_member_that_is_a_link_is_written_in_its_own_folder(_fresh(tmp_path), by,
                                                                                             held, which, name)
        for member in (("record_review.json", "report.md") if command == "review" else ("queue.json", "queue.md")):
            dj.test_the_cli_s_export_leaves_a_held_study_reached_through_a_link(_fresh(tmp_path), command, member)
        _other_kinds(tmp_path, "the review" if command == "review" else "the queue as report.json")
        dm.test_two_exports_of_different_kinds_at_once_leave_one_whole(_fresh(tmp_path))
        if command == "review":         # an entry no export recorded; the packet's reader after another's export
            for there in dm.THERE:
                dm.test_an_export_never_replaces_an_entry_no_export_recorded_there(_fresh(tmp_path), there)
            for change in dm.TAMPERED:
                dm.test_the_review_timer_reads_a_packet_only_as_its_export_wrote_it(_fresh(tmp_path), change)
        else:
            dm.test_the_queue_command_refuses_a_report_json_beside_a_review_packet(_fresh(tmp_path))


def test_the_harness_detects_an_export_written_apart(tmp_path):
    """DJ-01's defect restored, its negative control: each member of the export written directly into its folder, with
    no hold of it (``durable.export`` as the pin had it): the review row's W cell fails."""
    from unittest.mock import patch

    from adroit.core import durable

    def apart(folder, members, wait=0):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in members.items():                  # as the pin wrote them: text by write_text
            if isinstance(data, str):
                (folder / name).write_text(data)
            elif data is not None:
                (folder / name).write_bytes(data)
        return folder
    with patch.object(durable, "export", apart), pytest.raises(AssertionError):
        test_an_export_row(tmp_path, "records.export", "W")


def test_the_harness_detects_a_refused_command_s_record_written(tmp_path):
    """DK-01's defect restored, its negative control: a stopped command's request record written whatever it sent,
    outside the folder's hold (``record_requests`` as the pin had it): the session export's W cell fails, at a
    command refused into a saved study's folder."""
    from unittest.mock import patch

    from adroit.core.durable import write_atomic
    from adroit.orchestrator import catalog_cli, discovery_cli, preflight

    def always(out, service, session, members=()):
        if out is not None:
            Path(out).mkdir(parents=True, exist_ok=True)
            write_atomic(Path(out) / "paid_requests.json", preflight._requests(service, session))
    with patch.object(preflight, "record_requests", always), patch.object(catalog_cli, "record_requests", always), \
            patch.object(discovery_cli, "record_requests", always), pytest.raises(AssertionError):
        _refusals(tmp_path)


def test_the_harness_detects_a_review_read_apart(tmp_path):
    """DK-02's defect restored, its negative control: the review's figure and curves read from the data file afresh
    (as the pin read them), not from its one reading: the review export's ABA cell fails."""
    from unittest.mock import patch

    from adroit.constraints import review
    figure, curves = review.figure, review.curves
    with patch.object(review, "figure", lambda record, held=None: figure(record)), \
            patch.object(review, "curves", lambda record, held=None: curves(record)), pytest.raises(AssertionError):
        test_an_export_row(tmp_path, "records.export", "ABA")


def test_the_harness_detects_an_export_not_put_back(tmp_path):
    """DK-05's defect restored, its negative control: an export written under its hold but with nothing put back on a
    failure and no mark of an incomplete one (``durable.export`` as the pin had it): the session export's F cell
    fails."""
    from unittest.mock import patch

    from adroit.core import durable

    def unguarded(folder, members, wait=durable.PUBLISH_WAIT):
        with durable.publishing(Path(folder), wait=wait) as claim:
            durable.not_a_study(claim.folder)
            for name, data in members.items():
                if data is not None:
                    durable.write_atomic(claim.folder / name, data)
                elif os.path.lexists(claim.folder / name):
                    (claim.folder / name).unlink()
        return claim.folder
    with patch.object(durable, "export", unguarded), pytest.raises((AssertionError, OSError)):  # the raw I/O error
        test_an_export_row(tmp_path, "session.export", "F")                                   # left through, or B's


def test_the_harness_detects_a_review_approval_read_apart(tmp_path):
    """DL-01's defect restored, its negative control: the packet's review state taken from the record's signature
    checked again against its data file as it then stands (``record.usable``, as the pin took it), not from its
    reading: the review export's ABA cell fails."""
    from adroit.constraints import database, review_cli, review_packets
    real = review_packets.packet_for

    def apart(record_id, *args, **kwargs):
        packet = real(record_id, *args, **kwargs)
        held = kwargs.get("held", args[3] if len(args) > 3 else None)        # (selection, task, selected, held)
        record = held.record if held is not None else database.record(record_id)
        packet.current = packet.current.model_copy(update={"review": "verified" if record.usable else "unreviewed"})
        return packet
    with patch.object(review_packets, "packet_for", apart), patch.object(review_cli, "packet_for", apart), \
            pytest.raises(AssertionError):
        test_an_export_row(tmp_path, "records.export", "ABA")


def test_the_harness_detects_an_interrupted_mark_removed_by_another_export(tmp_path):
    """DL-02's defect restored, its negative control: an export removing the mark whatever it names (as the pin did):
    the review export's F cell fails, at another export after a killed writer."""
    from adroit.core import durable
    real = durable._finished
    with patch.object(durable, "_finished", lambda folder, members, remaining, recorded: real(folder, members, [],
                                                                                          recorded)), \
            pytest.raises(AssertionError):
        test_an_export_row(tmp_path, "records.export", "F")


def test_the_harness_detects_a_mark_failure_raised_raw(tmp_path):
    """DL-03's defect restored, its negative control: the mark removed or rewritten at the export's end with its
    failure raised as an ordinary I/O error (as the pin did): the queue export's F cell fails."""
    from adroit.core import durable

    def raw(folder, members, remaining, recorded):
        durable.write_atomic(folder / durable.RECORD, durable._record(recorded))        # its record, as now (DM-03)
        if remaining:
            durable.write_atomic(folder / durable.INCOMPLETE, durable._incomplete(remaining))
        else:
            (folder / durable.INCOMPLETE).unlink(missing_ok=True)
    with patch.object(durable, "_finished", raw), pytest.raises((AssertionError, OSError)):
        test_an_export_row(tmp_path, "queue.export", "F")


def test_the_harness_detects_a_discovery_charged_with_its_companion_s_session(tmp_path):
    """DL-04's defect restored, its negative control: a discovery run's session read from its discovery.json first
    (as the pin read it): the session export's F cell fails, at the cost read after a killed writer."""
    from adroit.orchestrator import accounting

    def companion_first(folder, job=None, expected=None):
        view = accounting._read_json(Path(folder) / "discovery.json")
        if view and isinstance(view.get("session"), str):
            return view["session"], []
        found = accounting.DISCOVERY_SESSION.search(accounting._log_text(Path(folder))[0])
        facts = accounting.facts_of(job) if job is not None else None
        resumed = facts is not None and facts.command[1:2] == ["resume"]
        return (found.group(1) if found else accounting._argument(facts) if resumed else ""), []
    with patch.object(accounting, "discovery_session", companion_first), pytest.raises(AssertionError):
        test_an_export_row(tmp_path, "session.export", "F")


def test_the_harness_detects_a_bundle_put_over_another(tmp_path):
    """DL-05's defect restored, its negative control: the bundle's ZIP put in place by replacing whatever is there (as
    the pin did): the evidence export's W cell fails."""
    from adroit.evidence import archive
    with patch.object(archive, "publish_new", lambda staged, path: Path(staged).replace(path)), \
            pytest.raises(AssertionError):
        test_a_held_row(tmp_path, "export.cli", "W")


def test_the_harness_detects_a_damaged_request_record_read_as_from_before_it(tmp_path):
    """DM-01's defect restored, its negative control: a discovery run's session resolved with its request record's
    damage set aside (as the pin resolved it): the session export's F cell fails, at the damaged record."""
    from adroit.orchestrator import accounting
    real, read = accounting.discovery_session, accounting._receipt

    def set_aside(folder, expected=""):
        receipt, damage, foreign = read(folder, expected)
        return (receipt, "", False) if damage and not foreign else (receipt, damage, foreign)

    def pin(folder, job=None, expected=None):
        with patch.object(accounting, "_receipt", set_aside):
            return real(folder, job, expected)
    with patch.object(accounting, "discovery_session", pin), pytest.raises(AssertionError):
        test_an_export_row(tmp_path, "session.export", "F")


@pytest.mark.parametrize("row_id, case", [("session.export", "F"), ("cost.attempt", "OA")])
def test_the_harness_detects_a_request_record_that_leads_nowhere_read_as_none(tmp_path, row_id, case):
    """DN-01's defect restored, its negative control: whether a run's records are there asked by following a link (as
    the pin asked it, ``Path.exists``), so that one leading nowhere reads as none: the session export's F cell and the
    attempt cost's OA cell fail, at a request record that is such a link."""
    from adroit.orchestrator import accounting
    with patch.object(accounting, "absent", lambda path: not Path(path).exists()), pytest.raises(AssertionError):
        (test_an_export_row if case == "F" else test_a_resume_or_cost_row)(tmp_path, row_id, case)


def _pin_journal(self, event: dict) -> None:
    """The pin's ``BudgetedLLMClient._journal``: an append that follows the ledger's path (``open("a")``)."""
    import json
    import os
    from adroit.agents.llm import _JOURNAL_LOCK
    with self._lock, _JOURNAL_LOCK:
        self.ledger.append(event)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a") as stream:
            stream.write(json.dumps(event, default=lambda x: vars(x)) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def _pin_opener(ledger) -> None:
    """The pin's ``preflight.open_job_ledger``: ``touch``, then an append, each following the ledger's path."""
    import json
    from adroit.orchestrator.preflight import run_attempt
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.touch()
    attempt = run_attempt()
    if not attempt or ledger.read_bytes()[-1:] not in (b"", b"\n"):
        return
    with ledger.open("a") as stream:
        stream.write(json.dumps({"state": "opened", "attempt": attempt}) + "\n")


@pytest.mark.parametrize("writer", ["the client's append", "the run's opening of its ledger"])
def test_the_harness_detects_a_ledger_made_anew_by_its_writer(tmp_path, writer):
    """DO-01's defect restored, its negative control: a paid ledger's writer appending by following its path, as the
    pin's did (the client's ``open("a")``, the opener's ``touch``), so that a ledger put in its place is written on or
    made anew: the attempt cost's OA cell fails, at its paid-ledger lifecycle (the second request sent; the damaged
    ledger made anew)."""
    from adroit.agents.llm import BudgetedLLMClient
    from adroit.orchestrator import preflight
    target, name, pin = ((BudgetedLLMClient, "_journal", _pin_journal) if writer == "the client's append" else
                         (preflight, "open_job_ledger", _pin_opener))
    named = "the second request was sent" if writer == "the client's append" else "the damaged ledger was made anew"
    with patch.object(target, name, pin), pytest.raises(AssertionError, match=named):
        test_a_resume_or_cost_row(tmp_path, "cost.attempt", "OA")


def _unchecked(data: bytes, path: Path) -> list[dict]:
    """DP-01's defect: the whole journal unchecked, every line taken as it is; its cap raises read, as a session's
    spending reconciles them with its record (DQ-03)."""
    import json
    raised = []
    for line in data.decode(errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("state") == "cap_raised":
            raised.append({k: v for k, v in row.items() if k != "state"})
    return raised


def _recovered_raw(real):
    """The pin's ``budget.recover_torn_tail``: its journal read raw, its mark not checked before it writes."""
    from adroit.agents import budget

    def recover(path):
        with patch.object(budget, "ledger_bytes", lambda ledger, folder=None: Path(ledger).read_bytes()):
            return real(path)
    return recover


# DP-01's and DP-02's defects restored: (what is patched, its pin, the OA cell's assertion that fails)
EXTENSION_CONTROLS = {
    "the whole journal unchecked": ("adroit.agents.budget.journal_raises", lambda real: _unchecked,
                                    "a request was sent after a line that is not whole"),   # every writer's check
    "a failed write forgotten": ("adroit.agents.budget.BudgetAccount.unjournalled",
                                 lambda real: property(lambda self: "", lambda self, value: None),
                                 "the reservation whose write failed was released"),
    "recovery before its mark": ("adroit.agents.budget.recover_torn_tail", _recovered_raw,
                                 "recovery changed a journal its mark refuses"),
    # DQ-01 to DQ-04's (the auditor's DP recheck, 2026-11-09)
    "an entry of a request sent, refused, forgotten": ("adroit.agents.llm.BudgetedLLMClient._journal",
                                                       lambda real: _refusal_forgotten(real),
                                                       "an entry failed and its account was not frozen"),
    "the journal's path unchecked during its append": ("adroit.core.durable._displaced",
                                                       lambda real: lambda path, handle, folder: "",
                                                       "a request was sent without its reservation in the journal at "
                                                       "its path"),
    "a cap raise read as its writer never makes it": ("adroit.agents.budget._cap_raised",
                                                      lambda real: lambda row, number: None,
                                                      "a cap raise its writer never makes was read as an entry"),
    "spending not reconciled with its record": ("adroit.orchestrator.model_intake.Intake._agreed",
                                                lambda real: lambda self, s, raised, refused: None,
                                                "the session spent while its budget's reading refused it"),
    "the freeze unread before a request is sent": ("adroit.agents.llm.BudgetedLLMClient._sendable",
                                                   lambda real: lambda self: None,
                                                   "a request reserved before its account froze was sent"),
    # DR-01's (the auditor's DQ recheck, 2026-11-09)
    "an append's mark taken of what its file then holds": ("adroit.core.durable._as_written",
                                                           lambda real: lambda path, found, data, now: _held_of(now),
                                                           "a request was sent after this change during its append: "
                                                           "emptied once checked"),
    "an append's mark not read back": ("adroit.core.durable._recorded",
                                       lambda real: lambda path, handle, after, folder: None,
                                       "a request was sent after this change during its append: its paid request "
                                       "removed once marked"),
    "an append outside its writers' lock": ("adroit.core.durable._locked", lambda real: _unlocked,
                                            "an append wrote while another writer held the journal's lock"),
    "a recovery outside its writers' lock": ("adroit.core.durable.writing", lambda real: _no_lock,
                                             "a recovery rewrote the journal while an append held its lock"),
    # DS-01's (the auditor's DR recheck, 2026-11-09)
    "the writers' lock on the journal's own file": ("adroit.core.durable._writers_lock", lambda real: _file_lock,
                                                    "an append was made to the journal a recovery had put in its "
                                                    "place, its mark not yet written"),
    # DT-01's (the auditor's DS recheck, 2026-11-10)
    "a journal read and written by another of its names": ("adroit.core.durable.own",
                                                           lambda real: lambda path, handle, folder=None: "",
                                                           "a request was sent through another name of its journal"),
    # restored with the DT pin's reading and writing by path: since DU-01, a writer in the folder it locked is refused
    # by the entry check too, apart from the folder check (two barriers, each restored)
    "the folder locked not checked once its lock is taken": (("adroit.core.durable._folder_at",
                                                              "adroit.core.durable._in"),
                                                             (lambda real: lambda path, folder: True,
                                                              lambda real: lambda path, folder: (Path(path), None)),
                                                             "a request was journalled and sent in a folder put in "
                                                             "its place while its writer waited"),
    # DU-01's and DU-02's (the auditor's DT recheck, 2026-11-10)
    "a writer's reads and writes by its path once it holds its lock": ("adroit.core.durable._in",
                                                                       lambda real: lambda path, folder: (Path(path),
                                                                                                          None),
                                                                       "a recovery wrote in a folder put in its place "
                                                                       "while it held its lock"),
    "a client's ledger known by its path's spelling": ("adroit.agents.llm.BudgetedLLMClient._ledger",
                                                       lambda real: lambda self: Path(os.path.abspath(
                                                           self.ledger_path)),
                                                       "a request was sent by another route to its session's ledger "
                                                       "while its record and ledger disagree"),
}


def _held_of(data: bytes):
    """The pin's mark of an append (DR-01's defect): of whatever its file holds once written."""
    from adroit.core.durable import Held
    return Held.of(data)


@contextmanager
def _unlocked(path: Path, held):
    """An append's check made without its writers' lock: its mark read, and its folder opened, no lock taken."""
    from adroit.core.durable import marked
    folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        yield marked(path), folder
    finally:
        os.close(folder)


@contextmanager
def _no_lock(path):
    """A recovery made without its writers' lock: its folder opened, not locked, and yielded, as the lock yields it."""
    folder = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        yield folder
    finally:
        os.close(folder)


_OPEN = os.open             # as it is before a test makes the append's own opening of its record fail (DQ-01)


@contextmanager
def _file_lock(path):
    """The pin's writers' lock (DS-01's defect): a lock on the record's own file, which a recovery replaces; none where
    it cannot be opened (still to be made, which the pin locked once made, or an entry the append's own opening
    refuses). Opened apart from the append's own opening (``_OPEN``), which a fault made in that opening still
    reaches, as at the pin, which locked the file the append had opened. Its folder is opened, not locked, and yielded,
    as the folder's lock yields it."""
    import fcntl
    folder = _OPEN(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            handle = _OPEN(path, os.O_RDONLY)
        except OSError:
            yield folder
            return
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield folder
        finally:
            os.close(handle)
    finally:
        os.close(folder)


def _refusal_forgotten(real):
    """The pin's ``BudgetedLLMClient._journal`` for an entry refused before anything was written: its account left
    unfrozen, though its request was sent (DQ-01)."""
    def journal(self, event):
        frozen = self.account.unjournalled
        try:
            return real(self, event)
        except ValueError:
            if not frozen:
                self.account.unjournalled = ""
            raise
    return journal


@pytest.mark.parametrize("name", EXTENSION_CONTROLS)
def test_the_harness_detects_a_ledger_written_past_what_is_whole(tmp_path, name):
    """DP-01's and DP-02's defects restored, their negative controls: a writer that checks only the ledger's first bytes
    (the whole journal unchecked), a client that forgets that its write failed once begun (its reservation released,
    its next request sent), and a recovery that writes before it reads the journal as every reading does; and DQ-01 to
    DQ-04's: an entry of a request already sent, refused, leaving its account unfrozen; an append that does not check
    that its path still leads to the file it writes; a cap raise its writer never makes read as an entry; a session's
    spending not reconciled with its record's cap raises; and the freeze not read again before a request is sent; and
    DR-01's: an append whose mark is taken of whatever its file then holds; one whose mark is not read back once
    written; an append, and a recovery, made without the journal's writers' lock; and DS-01's: the writers' lock on
    the journal's own file, which a recovery replaces; and DT-01's: a journal read and written by another of its names,
    and the folder locked not checked once its lock is taken; and DU-01's: a writer that reads and writes by its path
    once it holds its lock, not in the folder it locked; and DU-02's: a client's ledger known by its path's spelling:
    the attempt cost's OA cell fails, each at its own assertion."""
    import contextlib
    import importlib
    target, pin, named = EXTENSION_CONTROLS[name]
    with contextlib.ExitStack() as restored:        # one defect, restored where each of its barriers is
        for each, its in ([(target, pin)] if isinstance(target, str) else zip(target, pin)):
            module, attribute = each.rsplit(".", 1)
            try:
                owner = importlib.import_module(module)
            except ModuleNotFoundError:
                module, cls = module.rsplit(".", 1)
                owner = getattr(importlib.import_module(module), cls)
            restored.enter_context(patch.object(owner, attribute, its(getattr(owner, attribute, None)), create=True))
        with pytest.raises(AssertionError, match=named):
            test_a_resume_or_cost_row(tmp_path, "cost.attempt", "OA")


def test_the_harness_detects_an_export_over_part_of_another(tmp_path):
    """DM-03's defect restored, its negative control: an export replacing whatever entries its files name, whatever
    export wrote them (as the pin did): the review export's W cell fails, at another kind's export into its folder."""
    from adroit.core import durable
    with patch.object(durable, "_others", lambda folder, members, interrupted: []), \
            pytest.raises((AssertionError, pytest.fail.Exception)):
        test_an_export_row(tmp_path, "records.export", "W")


# --- the graph rows ------------------------------------------------------------------------------------------------

def _graph(tmp: Path, case: str, variant: str):
    """The promotion of ``tests.orchestrator.test_vi_audit._promotion`` (its child A recorded, B another), changed by
    ``variant``; (the promotion's path, A child's digest, B child's digest, the replaced parent's digest or "")."""
    import shutil
    from adroit.evidence import build
    from tests.orchestrator.test_vi_audit import _promotion, publish
    path, b, parent = _promotion(tmp / "graph", recorded=case != "L")
    child = tmp / "graph" / "child"
    a_child = vm.sha((child / "result.json").read_bytes())
    b_child, other = "", ""
    if variant == "child replaced":
        b_child = vm.sha(publish(child, b, "B child"))
    elif variant == "parent replaced":
        replaced = parent.model_copy(update={"max_local_z": 1.0})
        content = replaced.model_dump_json().encode()
        build.publish(path.parent / "result.json", content, replaced, lambda e: "Parent B", workflow="signal")
        other = vm.sha(content)
    elif variant == "child absent":
        shutil.rmtree(child)
    return path, a_child, b_child, other


def _graph_output(row_id: str, path: Path, tmp: Path) -> tuple[set[str], list[str]]:
    """(the digests of the results a graph row reads, its warnings)."""
    from adroit.constraints.review_queue import load_selected
    from adroit.evidence import archive
    if row_id == "graph.review":
        selected = load_selected(path)
        return {s.envelope.result_sha256 for s in selected}, selected[0].warnings
    out = tmp / "graph.zip"
    manifest = archive.export_run(path, out)
    with zipfile.ZipFile(out) as z:
        exported = {vm.sha(z.read(n)) for n in z.namelist() if n.endswith("/result.json")}
    if row_id == "graph.export":
        return exported, manifest.warnings
    selected = load_selected(out)
    if row_id == "graph.bundle_review":
        return {s.envelope.result_sha256 for s in selected}, selected[0].warnings
    from adroit.constraints.review_packets import packet_for
    from adroit.constraints.review_queue import build_queue
    from adroit.constraints.database import records
    task = next((t for t in build_queue(selected).tasks if t.record_id), None)
    packet = packet_for(task.record_id if task else records()[0].id, selected[0], task, selected)
    return {s.envelope.result_sha256 for s in selected}, packet.warnings


GRAPH_VARIANTS = {"B": ("as recorded",), "L": ("as recorded",), "G": ("child replaced", "parent replaced", "child absent"),
                  "GW": ("child replaced", "child absent")}


@pytest.mark.parametrize("row_id, case", _cells(("graph",)))
def test_a_graph_row(tmp_path, row_id, case):
    wanted = vm.expected(vm.BY_ID[row_id], case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    for variant in GRAPH_VARIANTS[case]:
        where = tmp_path / variant.replace(" ", "_")
        path, a_child, b_child, other = _graph(where, case, variant)
        digests, warnings = _graph_output(row_id, path, where)
        text = "\n".join(warnings)
        assert not (b_child and b_child in digests) and not (other and other in digests), (row_id, case, variant)
        if wanted == "A":
            assert a_child in digests and not any("another version" in w or "not saved" in w for w in warnings)
        elif wanted == "A, as found":
            assert a_child in digests and "records no digest" in text
        elif wanted == "named":
            assert ("now saved is another version" in text) if "replaced" in variant else ("is not saved" in text)
        elif wanted == "carried":
            assert "not reviewed: its review tasks are not shown" in text
        else:
            raise AssertionError(wanted)
    if (row_id, case) == ("graph.export", "B"):       # a promotion's child as its writer publishes it (DG-04)
        _child_capture_cells(tmp_path / "capture")


def _child_capture_cells(tmp: Path) -> None:
    """The promotion's baseline, its child as its writer publishes it: the request its evidence captured is the one it
    calculated and saved, its defaults resolved first, and its calculation identity and its exported bundle are
    unqualified; a request changed after its capture is still named (``test_dg_fixes``; the auditor's DF recheck, DG-04);
    and its typed result records when its calculation started and completed, within its evidence's, and its report
    says so (``test_dh_fixes``; the auditor's DG recheck, DH-03)."""
    from tests.orchestrator import test_dg_fixes as dg
    tmp.mkdir()
    for test in (dg.test_a_single_idea_study_captures_the_request_it_calculates,
                 dg.test_a_request_changed_after_its_capture_is_still_named):
        with pytest.MonkeyPatch.context() as monkeypatch:
            test(_fresh(tmp), monkeypatch, "a promotion's child")
    from tests.orchestrator import test_dh_fixes as dh           # and when it was calculated (DH-03)
    with pytest.MonkeyPatch.context() as monkeypatch:
        dh.test_a_promotion_child_s_dates_are_its_calculation_s(_fresh(tmp), monkeypatch)


# --- the archive rows: a bundle is read once, as bytes -----------------------------------------------------------

@pytest.mark.parametrize("row_id, case", _cells(("archive",)))
def test_an_archive_row(tmp_path, row_id, case):
    from adroit.evidence import archive
    wanted = vm.expected(vm.BY_ID[row_id], case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    world = vm.make(tmp_path)
    bundle_a, bundle_b = tmp_path / "a.zip", tmp_path / "b.zip"
    archive.export_run(world.folder, bundle_a)
    vm.publish(world, "B")
    archive.export_run(world.folder, bundle_b)
    path = tmp_path / "selected.zip"
    path.write_bytes(bundle_a.read_bytes())
    real = archive.held_bundle

    def replaced(where):                         # B's bundle saved over the file once its bytes are held (R, T1)
        data = real(where)
        if case in ("R", "T1"):
            path.write_bytes(bundle_b.read_bytes())
        return data
    held_a = tmp_path / "held_a.zip"            # A's bundle alone, verified apart: what the selected file held
    held_a.write_bytes(bundle_a.read_bytes())
    expected_a = archive.verify_bundle(held_a)
    with patch.object(archive, "held_bundle", replaced):
        if row_id == "bundle.verify":
            checked = archive.verify_bundle(path)
            # all of it A's: its digest, and the decisions reconstructed, node by node (DD-03: a check of the digest
            # alone had passed A's digest beside B's nodes)
            assert checked.valid and checked.archive_sha256 == vm.sha(bundle_a.read_bytes()), checked.issues
            assert checked == expected_a, "the verification is not A's whole"
            return
        from adroit.evidence import replay
        seen = []

        def stop(data):
            seen.append(archive.read_bundle(data)[0])
            raise RuntimeError("read")
        with patch.object(replay, "held_bundle", replaced), patch.object(replay, "read_bundle", stop), \
                pytest.raises(RuntimeError):
            replay.replay_bundle(path, node_id="n0", index=0)
    a_nodes = archive.read_bundle(bundle_a.read_bytes())[0].nodes
    assert [n.model_dump() for n in seen[0].nodes] == [n.model_dump() for n in a_nodes]


# --- the resumes and the attempt-bound cost: cells run by the regression tests that fix them -----------------------

def _resume_cells(tmp: Path) -> None:
    """The CK cells: a completed Track 1 and native checkpoint, dated and saved before ADROIT kept dates, each stable and
    beside another publication; a native fit resumed part way; a checkpoint replaced after its restore; dates written
    into a checkpoint after its restore. Each is the regression test that fixes it, called here."""
    from tests.orchestrator import test_dc_recheck as dc, test_vi_audit as vi
    for replace in (False, True):
        for dated in (True, False):
            vi.test_a_resumed_track1_checkpoint_keeps_its_own_dates(_fresh(tmp), replace, dated)
        vi.test_a_resumed_native_fit_keeps_its_own_dates(_fresh(tmp), replace)
    dc.test_a_native_fit_resumed_part_way_is_dated_from_its_first_start(_fresh(tmp))
    dc.test_a_native_checkpoint_replaced_after_its_restore_keeps_its_own_dates(_fresh(tmp))
    dc.test_a_track1_checkpoint_replaced_after_its_restore_keeps_its_own_dates(_fresh(tmp))
    dc.test_dates_written_into_a_checkpoint_after_its_restore_are_not_taken(_fresh(tmp))


def _writer_cells(tmp: Path) -> None:
    """The W cell: a second reanalysis into the child's folder is refused before it calculates; B published by the
    production writer during the run waits for it (another thread) or is refused (its own), at each boundary
    (``test_de_fixes``; the auditor's DD recheck, DE-02); a Track 1 run into a folder another holds, from this thread,
    another or another process, draws nothing and A's plane is its report's, page's and bundle's; and each writer that
    calculates, draws or writes into a study's folder writes nothing into one another thread or process holds
    (``test_df_fixes``; the auditor's DE recheck, DF-01); and a figure rendering where no writer held its folder when
    another writer, another thread or process, takes it is written before that writer's, never under its hold
    (``test_dg_fixes``; the auditor's DF recheck, DG-02); and a figure that is a link, drawn by another writer while its own
    folder is held (refused) or its target's (drawn, the target untouched), and by its own folder's holder
    (``test_dh_fixes``; the auditor's DG recheck, DH-04)."""
    from tests.orchestrator import test_de_fixes as de, test_df_fixes as df
    de.test_of_two_reanalyses_into_one_folder_exactly_one_owns_it(_fresh(tmp))
    for boundary in ("calculation", "result", "evidence", "report", "record"):
        for thread in ("another thread", "the same thread"):
            de.test_another_adroit_writer_into_a_reanalysis_s_folder_never_joins_its_publication(_fresh(tmp), boundary,
                                                                                               thread)
    for where in ("the same thread", "another thread", "another process"):
        df.test_a_track1_run_refused_from_a_held_folder_never_draws_into_it(_fresh(tmp), where)
    for writer in df.WRITERS:
        for by in ("another thread", "another process"):
            with pytest.MonkeyPatch.context() as monkeypatch:
                df.test_a_writer_into_a_folder_another_holds_writes_nothing(_fresh(tmp), monkeypatch, writer, by)
    df.test_a_report_is_bound_to_the_figures_its_own_writer_drew(_fresh(tmp))
    from tests.orchestrator import test_dg_fixes as dg           # a figure rendering when the folder is taken (DG-02)
    for by in ("another thread", "another process"):
        dg.test_a_figure_rendering_when_another_writer_takes_its_folder_is_never_written_under_that_hold(_fresh(tmp), by)
    dg.test_a_figure_drawn_under_its_writer_s_hold_is_the_writer_s(_fresh(tmp))
    from tests.orchestrator import test_dh_fixes as dh           # a figure that is a link (DH-04)
    for by in ("another thread", "another process"):
        dh.test_a_figure_that_is_a_link_is_drawn_under_its_own_folder_s_hold(_fresh(tmp), by)
        dh.test_a_figure_that_is_a_link_is_not_held_by_its_target_s_folder(_fresh(tmp), by)
    dh.test_a_writer_s_draw_over_a_link_in_its_folder_is_its_own(_fresh(tmp))


def _edge_cells(tmp: Path) -> None:
    """T1 at every boundary: B published whole between the run's parts by a process outside ADROIT's writers, the run
    refusing and B left as it wrote it (``test_de_fixes``; DE-02)."""
    from tests.orchestrator import test_de_fixes as de
    for boundary in de.EDGES:
        de.test_a_writer_outside_adroit_s_between_a_reanalysis_s_parts_is_left_as_it_wrote(_fresh(tmp), boundary)


def _cost_cells(tmp: Path) -> None:
    """The OA cells: a study's cost is its own run's, its record's where a later run is in its folder, never the later
    run's (``test_dc_recheck.test_a_study_s_cost_is_the_run_its_record_names``, called here for each case); and so
    when the later run's record and ledger are written while the cost is read, after its run's record was read, with
    or without a new publication, on the card, in Studies and by ``adroit studies``, and when the same run settles
    more (``test_dd_fixes``; the auditor's version-handle audit, DD-02); each record of a run's money another run's, restored
    over it (``test_de_fixes``; DE-01); and a request settled in a shared session's ledger before, after or about the
    cost's one reading of it, every figure of that reading (``test_df_fixes``; the auditor's DE recheck, DF-02); and the
    session's cap raised between the readings of its record and of its ledger, spent or reserved under, or its record
    then restored, a raise half made or interrupted, a record changed at every reading and a writer raising and
    spending meanwhile: every figure of one state of the session, or the session named (``test_dg_fixes``; the auditor's DF
    recheck, DG-01); and a session command refused into the study's folder, held or not, from the installed command
    and in this process: the study's every byte, and its $1.25 on the card, in Studies and by ``adroit studies``, the
    same (``test_dk_fixes``; the auditor's DJ recheck, DK-01); and a survey run's request record damaged beside an earlier
    survey's discovery.json: no figure but of a session a record bound to the run names (``_damaged_records``; the auditor's
    DL recheck, DM-01)."""
    from tests.orchestrator import test_dc_recheck as dc, test_dd_fixes as dd
    for case in ("its own run", "a later run", "published outside a run", "a record written before"):
        with pytest.MonkeyPatch.context() as monkeypatch:
            dc.test_a_study_s_cost_is_the_run_its_record_names(_fresh(tmp), monkeypatch, case)
    for whole in (False, True):
        with pytest.MonkeyPatch.context() as monkeypatch:
            dd.test_a_later_run_written_while_a_cost_is_read_is_not_the_study_s(_fresh(tmp), monkeypatch, whole)
    with pytest.MonkeyPatch.context() as monkeypatch:
        dd.test_the_same_run_settling_more_while_its_cost_is_read_is_the_study_s(_fresh(tmp), monkeypatch)
    from tests.orchestrator import test_de_fixes as de           # A, B, A; another run's record beside (DE-01)
    for source in de.SOURCES:
        for every in (False, True):
            for surface in ("cost", "card", "list", "cli"):
                de.test_another_run_s_records_restored_over_while_its_cost_is_read_are_never_the_study_s(
                    _fresh(tmp), source, every, surface)
        de.test_another_run_s_record_read_beside_the_study_s_run_record_is_not_counted(_fresh(tmp), source)
        de.test_a_run_s_own_records_restored_unchanged_are_its_own(_fresh(tmp), source)
    with pytest.MonkeyPatch.context() as monkeypatch:
        de.test_each_record_of_a_run_s_money_names_its_run(_fresh(tmp), monkeypatch)
    from tests.orchestrator import test_df_fixes as df           # a shared session's ledger, settled meanwhile (DF-02)
    for change in df.CHANGES:
        for surface in ("cost", "card", "list", "cli"):
            df.test_a_session_s_cost_is_of_one_reading_of_its_journal(_fresh(tmp), change, surface)
    from tests.orchestrator import test_dg_fixes as dg           # its cap raised between its readings (DG-01)
    for change in dg.CAP_CHANGES:
        for surface in dg.SURFACES:
            dg.test_a_session_s_cap_and_spending_are_of_one_state_of_it(_fresh(tmp), change, surface)
    for test in (dg.test_a_raise_being_made_is_read_once_its_record_is_written,
                 dg.test_a_raise_interrupted_between_its_ledger_and_its_record_is_named,
                 dg.test_a_session_whose_record_changes_at_every_reading_is_named):
        with pytest.MonkeyPatch.context() as monkeypatch:
            test(_fresh(tmp), monkeypatch)
    dg.test_a_session_read_while_another_thread_raises_and_spends_is_always_one_of_its_states(_fresh(tmp))
    _refusals(tmp)                                          # a refused command beside the study's record (DK-01)
    _damaged_records(tmp)                                   # a damaged request record beside a companion (DM-01)
    _journal_lifecycle(tmp)                                 # a paid ledger put in its writer's place (DO-01)


def _journal_lifecycle(tmp: Path) -> None:
    """The OA cells' paid-ledger lifecycle (the auditor's DN recheck, DO-01, 2026-11-08), from a ledger's making through each
    append between requests: a session's ledger put in its live client's place between two requests, each way
    (``test_do_fixes.REPLACEMENTS``): the second request never sent, nothing written in the ledger's place or made
    there, every new reading naming it, and the original restored, the session's totals the first request's and then
    spent on; another writer appending meanwhile, the client writing on; a ledger emptied, cut short or replaced since
    its last writer, every later reading naming it; a run's own ledger damaged or lost when its run opens it, or
    replaced after, before its first request; and a run's cost from a ledger emptied since, never "no paid request was
    sent"."""
    from tests.orchestrator import test_do_fixes as do
    for replacement in do.REPLACEMENTS:
        do.test_a_live_client_never_writes_on_in_a_ledger_put_in_its_place(_fresh(tmp), replacement)
    do.test_a_live_client_writes_on_after_the_session_s_other_writers_append(_fresh(tmp))
    for replacement in ("no entry", *do.READABLE):
        do.test_every_reading_of_a_ledger_that_is_not_what_was_last_written_to_it_names_it(_fresh(tmp), replacement)
    do.test_a_paid_run_whose_ledger_is_emptied_since_is_not_read_as_one_that_sent_nothing(_fresh(tmp))
    for damage in do.DAMAGED:
        do.test_a_damaged_job_ledger_is_never_opened_anew(_fresh(tmp), damage)
    do.test_a_job_ledger_missing_beside_its_mark_is_never_opened_anew(_fresh(tmp))
    for replacement in do.OPENED_REPLACEMENTS:
        do.test_a_job_ledger_replaced_after_its_run_opened_it_is_never_written_on(_fresh(tmp), replacement)
    _journal_extensions(tmp)


def _journal_extensions(tmp: Path) -> None:
    """The OA cells' paid ledger past its writer's last line (the auditor's DO recheck, DP-01 and DP-02, 2026-11-09): a
    reservation's write cut short before its bound and after it, and one written whole whose sync failed (its
    reservation kept by the live account, as the ledger holds it, and the next request never sent); a line after the
    client's last that is not JSON, not an entry, a settlement never reserved, or torn (nothing written or sent after
    it); a whole last entry without its newline (the next line written after one); a run's torn ledger refused at its
    opening, then recovered and spent on, and one whose last entry has no newline opened; a journal's recovery refused,
    nothing changed, where it does not begin with what its mark records, and done, the mark recording it, where it
    does."""
    from tests.orchestrator import test_dp_fixes as dp
    for after in (120, 170):
        dp.test_a_reservation_whose_write_is_cut_short_is_kept_and_nothing_more_is_sent(_fresh(tmp), after)
    dp.test_a_reservation_written_whole_whose_sync_fails_is_kept_and_the_accounts_agree(_fresh(tmp))
    for extension in dp.EXTENSIONS:
        dp.test_nothing_is_written_or_sent_after_what_is_not_whole(_fresh(tmp), extension)
    dp.test_a_whole_last_entry_without_its_newline_is_ended_before_the_next(_fresh(tmp))
    dp.test_a_run_s_torn_ledger_is_refused_at_its_opening_and_nothing_is_sent(_fresh(tmp))
    dp.test_a_run_opens_a_ledger_whose_whole_last_entry_has_no_newline(_fresh(tmp))
    for mismatch in dp.MISMATCHED:
        dp.test_recovery_of_a_journal_its_mark_refuses_changes_nothing(_fresh(tmp), mismatch)
    dp.test_recovery_behind_its_mark_recovers_and_records_it(_fresh(tmp))
    _journal_failures(tmp)


def _journal_failures(tmp: Path) -> None:
    """The OA cells' paid ledger at each failure of its writing (the auditor's DP recheck, DQ-01 to DQ-04, 2026-11-09): each
    entry of a request (its reservation, its response, its bill uncertain, its settlement) refused before it is
    written, cut short, unsynced or unmarked, then the same client's next request (sent only after a reservation refused
    before anything was written; else its account frozen, never holding less than its ledger); the journal put in its
    place while its append checks it, once it has written and once it has marked (nothing sent without its reservation
    in the journal at its path); a cap raise its writer never makes, and one its record lacks (refused by every reading
    and by its spending alike), and the raises a person makes (spent under); a request reserved before its account
    froze (never sent), and two clients of one account (both settled)."""
    from tests.orchestrator import test_dq_fixes as dq
    for event in dq.EVENTS:
        for fault in dq.FAULTS:
            dq.test_a_failed_entry_leaves_the_accounts_agreeing_or_the_account_frozen(_fresh(tmp), event, fault)
    for moment in dq.MOMENTS:
        dq.test_a_journal_put_in_its_place_during_an_append_is_never_sent_past(_fresh(tmp), moment)
    for case in dq.UNMADE:
        dq.test_a_cap_raise_its_writer_never_makes_is_refused_by_every_reading_and_writing(_fresh(tmp), case)
    dq.test_a_cap_raise_its_record_lacks_stops_spending_as_it_stops_the_reading(_fresh(tmp))
    dq.test_a_session_spends_under_the_cap_raises_its_writer_makes(_fresh(tmp))
    dq.test_a_request_reserved_before_its_account_froze_is_never_sent(_fresh(tmp))
    dq.test_two_clients_of_one_account_both_settle(_fresh(tmp))
    _journal_rewrites(tmp)


def _journal_rewrites(tmp: Path) -> None:
    """The OA cells' paid ledger changed in place as its append is made (the auditor's DQ recheck, DR-01, 2026-11-09): the
    journal emptied, its paid request removed or its bill lowered, once its append checked it, once its line was
    written and synced, or once it was marked, or its mark damaged or shortened once written (nothing sent; the account
    frozen; every reading refusing the journal, never reading it as less); a healthy append's every earlier request and
    bill at each send, and its mark; an append and a recovery while another writer holds the journal's lock (neither
    writes until it is released); ``durable.append_held`` itself, never marking a record changed in place. And (the auditor's
    DR recheck, DS-01, 2026-11-09) a request asked by another process once a recovery has put the recovered journal in
    its place, before its mark is written: neither journalled nor sent until the recovery is done, then marked with
    the whole journal, which cut back is refused; the writers' lock one through a linked folder. And (the auditor's DS
    recheck, DT-01, 2026-11-10) a request asked by another name of the journal (a link to it or a hard link's name, in
    its folder or another), with no recovery and during one: refused before it is sent, the journal and its own mark
    as they were, no mark beside the other name (through a linked folder, its own folder, it waits and is marked with
    the whole journal); a hard link made while an append checks the journal (refused); and an append, and a recovery,
    whose folder is replaced while it waits for its lock (refused, nothing written in either folder). And its writers
    holding the lock and its clients' routes (``_journal_holders``)."""
    from tests.orchestrator import test_dr_fixes as dr
    from tests.orchestrator import test_ds_fixes as ds
    from tests.orchestrator import test_dt_fixes as dt
    for case in dr.REWRITES:
        dr.test_a_journal_changed_in_place_during_an_append_is_never_sent_past_nor_read_as_less(_fresh(tmp), case)
    dr.test_an_append_acknowledges_what_it_checked_and_wrote(_fresh(tmp))
    dr.test_an_append_waits_while_another_writer_holds_its_journal(_fresh(tmp))
    dr.test_a_recovery_waits_while_an_append_holds_its_journal(_fresh(tmp))
    dr.test_an_append_alone_marks_only_what_it_wrote(_fresh(tmp))
    ds.test_an_append_waits_while_a_recovery_that_replaced_its_journal_holds_its_lock(_fresh(tmp))
    ds.test_the_writers_lock_is_one_through_a_linked_folder(_fresh(tmp))
    for alias in dt.ALIASES:
        dt.test_a_request_by_another_name_of_its_journal_is_refused_before_it_is_sent(_fresh(tmp), alias)
    dt.test_a_hard_link_made_while_its_append_checks_it_is_refused(_fresh(tmp))
    for route in dt.ROUTES:
        dt.test_a_request_by_another_route_during_a_recovery_waits_or_is_refused(_fresh(tmp), route)
    dt.test_a_writer_whose_folder_is_replaced_while_it_waits_for_its_lock_is_refused(_fresh(tmp))
    dt.test_a_recovery_whose_folder_is_replaced_while_it_waits_for_its_lock_is_refused(_fresh(tmp))
    _journal_holders(tmp)
    _bindings(tmp)


def _bindings(tmp: Path) -> None:
    """The OA cells' paid ledger kept by its client and acknowledged at its path (the auditor's DU recheck, DV-01 and DV-02,
    2026-11-10): a run's client given its ledger through a link to its folder or one above it, the link led to an empty
    folder or another opened run's, before its first request, between two, and between a reservation and its receipt
    (refused before anything is sent; after it is sent, frozen and noticed), and kept (both journalled); a
    reservation's readback begun with its folder, the folder above it or a link to a copy put in its place (never
    sent); a folder replaced once the readback has checked (sent, its receipt refused, a notice every reading refuses);
    a session's account and spending beside a notice."""
    from tests.orchestrator import test_dv_fixes as dv
    for how in dv.LINKS:
        for where in dv.ELSEWHERE:
            dv.test_a_run_s_client_whose_link_is_led_elsewhere_between_requests_is_refused(_fresh(tmp), how, where)
        dv.test_a_run_s_client_whose_link_is_led_elsewhere_before_its_first_request_is_refused(_fresh(tmp), how)
    dv.test_a_run_s_client_whose_link_is_led_elsewhere_between_its_reservation_and_receipt_freezes(_fresh(tmp))
    dv.test_a_run_s_client_through_a_link_that_keeps_leading_to_its_ledger_journals_every_request(_fresh(tmp))
    for kind in ("a run's ledger", "a client's own ledger"):
        for how in dv.REPLACEMENTS:
            dv.test_a_reservation_whose_folder_is_replaced_before_its_readback_is_never_sent(_fresh(tmp), kind, how)
    dv.test_a_folder_replaced_after_the_readback_leaves_a_notice_every_reading_refuses(_fresh(tmp))
    dv.test_a_session_whose_request_lacks_an_entry_spends_nothing_more_until_it_is_reconciled(_fresh(tmp))


def _journal_holders(tmp: Path) -> None:
    """The OA cells' paid ledger written by a writer that holds its lock, and reached by its clients' routes (the auditor's DT
    recheck, DU-01 and DU-02, 2026-11-10): a recovery whose folder is renamed away and an equal copy put at its path
    while it holds the lock, before its side copy, its journal or its mark is written and once its mark is, another
    process asking a request in the copy meanwhile (nothing written in the copy by the recovery, which is refused once
    done; its journal and mark whole in the folder it locked; the copy's request marked whole, never cut away unseen);
    a request's append so, once it has checked, before it marks and once it has marked (nothing written in the copy;
    refused, or its account frozen, its request never sent); a session's client given its ledger by its own path, a
    link to its folder and a link to a folder above it, refused alike while its record and ledger disagree, or where
    its ledger was put in its place since its account was read, and spending alike when healthy, by the name its
    account was read by; a client of a session's account given another ledger (refused); a run's ledger given through
    a link to its folder, put in its place since its run opened it (refused) or healthy (journalled as opened)."""
    from tests.orchestrator import test_do_fixes as do
    from tests.orchestrator import test_du_fixes as du
    for stage in du.STAGES:
        du.test_a_recovery_whose_folder_is_replaced_while_it_holds_its_lock_writes_nothing_there(_fresh(tmp), stage)
    for stage in du.APPEND_STAGES:
        du.test_an_append_whose_folder_is_replaced_while_it_holds_its_lock_writes_nothing_there(_fresh(tmp), stage)
    for route in du.SESSION_ROUTES:
        du.test_a_session_s_client_by_any_route_is_refused_while_its_record_and_ledger_disagree(_fresh(tmp), route)
        for replacement in du.SESSION_REPLACEMENTS:
            du.test_a_session_s_ledger_put_in_its_place_since_its_account_was_read_is_refused_by_any_route(
                _fresh(tmp), route, replacement)
        du.test_a_session_s_client_by_any_route_spends_under_its_account(_fresh(tmp), route)
    du.test_a_client_of_a_session_s_account_given_another_ledger_is_refused(_fresh(tmp))
    for replacement in do.OPENED_REPLACEMENTS:
        du.test_a_run_s_ledger_by_a_link_to_its_folder_is_held_as_its_run_opened_it(_fresh(tmp), replacement)
    du.test_a_run_s_client_by_a_link_to_its_folder_journals_in_its_ledger_as_opened(_fresh(tmp))


def _fresh(tmp: Path) -> Path:
    folder = tmp / f"cell{len(list(tmp.iterdir()))}"
    folder.mkdir()
    return folder


@pytest.mark.parametrize("row_id, case", _cells(("resume", "cost")))
def test_a_resume_or_cost_row(tmp_path, row_id, case):
    """A resume's dates are its checkpoint's own (CK), a study's cost its own run's (OA); the baseline is each stable
    case among them."""
    wanted = vm.expected(vm.BY_ID[row_id], case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    (_cost_cells if row_id == "cost.attempt" else _resume_cells)(tmp_path)


# --- the diagnostic rows: read as found --------------------------------------------------------------------------

DIAGNOSTIC = {"theory.report": "test_a_theory_check_s_report_is_read_as_found",
              "discovery.report": "test_a_discovery_report_is_read_as_found",
              "advisory.report": "test_an_assistance_report_names_the_saved_result_it_read",
              "fog.report": None, "intake.report": None}


@pytest.mark.parametrize("row_id, case", _cells(("diagnostic",)))
def test_a_diagnostic_row(tmp_path, monkeypatch, row_id, case):
    wanted = vm.expected(vm.BY_ID[row_id], case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    from tests.evidence import test_as_found as af
    if DIAGNOSTIC[row_id]:
        test = getattr(af, DIAGNOSTIC[row_id])
        args = {"tmp_path": tmp_path, "monkeypatch": monkeypatch}
        test(**{k: v for k, v in args.items() if k in test.__code__.co_varnames[:test.__code__.co_argcount]})
        return
    if row_id == "fog.report":
        from adroit.orchestrator.cli import app
        done = CliRunner().invoke(app, ["fog", "map", "--masses", "20:1000:2", "--sigmas", "1e-50:1e-44:8",
                                        "--out", str(tmp_path / "map")])
        assert done.exit_code == 0, done.output
        assert "*Read as found.* It was computed from" in (tmp_path / "map" / "report.md").read_text()
        return
    from adroit.orchestrator.catalog_cli import _draft_report
    draft = SimpleNamespace(created="2026-11-04T00:00:00Z", step_id="step1", choices=[])
    with patch("adroit.orchestrator.catalog_cli.approval_lines", return_value=[]):
        text = _draft_report("Model intake draft", "session1", draft)
    assert "*Read as found.* It is the draft step1 as the intake session session1 held it" in text


# --- the matrix as written, and the harness's negative controls ---------------------------------------------------

def test_the_written_matrix_is_the_fixed_one():
    """``docs/version_matrix.md`` is ``tests/version_matrix.py``'s table: the cells run are the cells written."""
    doc = Path(__file__).parents[2] / "docs" / "version_matrix.md"
    assert doc.read_text() == vm.table(), "write docs/version_matrix.md from tests.version_matrix.table()"


def test_the_fixed_fields_are_the_world_s(tmp_path):
    """The fields the page oracle compares (``vm.POINTS``, ``vm.SUMMARY``, ``vm.CHART``; the auditor's DD recheck, DE-03) are
    the world's as published, by the production projection of each version alone: its point table's rows, its
    headline, its certification's line, its cost and its record's dates, each whole (the auditor's DE recheck, DF-03), and its
    interactive plane, each point and both axes (the auditor's DF recheck, DG-03); and each version's differ where the oracle
    tells them apart."""
    import json
    from adroit.evidence.points import points
    from adroit.evidence.version import resolve
    from adroit.ui import pages
    from adroit.ui.points import _number, _where, chart_options
    from adroit.ui.style import duration
    world = vm.make(tmp_path)
    for label in "AB":
        if label == "B":
            vm.publish(world, "B")
        found = resolve(world.folder)
        rows = [(p.point_id, p.kind, _where(p.coordinates), _number(p.omega_h2), p.status, p.reason[:160], p.halo)
                for p in points("track1", found.typed())]
        assert rows == vm.POINTS[label], label
        assert vm.chart_of(chart_options("track1", found.typed(), points("track1", found.typed()))) == \
            vm.CHART[label], label
        study, fixed = found.study(), vm.SUMMARY[label]
        assert found.headline().words == fixed["verdict"]
        assert fixed["certification"] == pages.CERTIFICATION_WORDS[found.headline().certification] + \
            pages._stale_on(json.loads(found.content))
        assert fixed["calculated"] == f"UTC: {study.calculation_completed_at}"
        assert fixed["took"] == f"took {duration(study.calculation_started_at, study.calculation_completed_at)}"
        assert fixed["cost"] == f"cost ${study.cost_usd:.2f} settled"
    assert vm.POINTS["A"][0][4:] != vm.POINTS["B"][0][4:]                       # grid:0's decision
    assert all(vm.SUMMARY["A"][k] != vm.SUMMARY["B"][k] for k in vm.SUMMARY["A"])
    assert all(vm.CHART["A"]["points"][k] != vm.CHART["B"]["points"][k] for k in vm.CHART["A"]["points"])
    assert all(vm.CHART["A"][axis] != vm.CHART["B"][axis] for axis in ("x axis", "y axis"))


def test_every_cell_is_run_or_says_why_not():
    """No cell is left without an outcome: each is expected an outcome the harness checks, or is not applicable with a
    reason; and no row or case is left out of the table."""
    seen = vm.cells()
    assert len(seen) == len(vm.ROWS) * len(vm.CASES)
    for row, case, wanted in seen:
        assert wanted in ("A", "A, as found", "B", "A then refused", "named", "carried", "dated", "own cost",
                          "as found", "left out", "one owner", "whole or incomplete") or wanted.startswith(
            ("refused:", "N/A: ")), \
            (row, case, wanted)
        if wanted.startswith("N/A: "):
            assert len(wanted) > len("N/A: ") + 10, (row, case)


CONTROLS = {
    "a record read again": ("history.facts", "R", "adroit.evidence.version.Version.study",
                            lambda real: lambda self: __import__("adroit.orchestrator.studies", fromlist=["load"])
                            .load(self.folder)),
    "a result read again": ("export.cli", "R", "adroit.evidence.version.Version.saved",
                            lambda real: lambda self: __import__("adroit.evidence.build", fromlist=["read_saved"])
                            .read_saved(self.path)),
    "a report read again": ("classic.report", "P", "adroit.evidence.version.Version.report",
                            lambda real: lambda self: __import__("adroit.evidence.bindings", fromlist=["read_report"])
                            .read_report(self.folder / "report.md", self.result_sha256 or None)),
}


@pytest.mark.parametrize("name", CONTROLS)
def test_the_harness_detects_a_reread_part(tmp_path, name):
    """A negative control: a version made to read a part from the folder again (the defect the handle removes) is
    caught by its cell: the cell's outcome is not its expected one."""
    row_id, case, target, make = CONTROLS[name]
    world = vm.make(tmp_path)
    module, cls, attribute = target.rsplit(".", 2)
    owner = getattr(__import__(module, fromlist=[cls]), cls)
    with patch.object(owner, attribute, make(getattr(owner, attribute))), vm.at(world, case):
        out = vm.run(lambda: _held(row_id, world, tmp_path))
    found = vm.outcome(world, out, vm.BY_ID[row_id].shows)
    assert not vm.agrees(found, vm.expected(vm.BY_ID[row_id], case)), f"{name}: not detected ({found})"


def test_the_harness_detects_a_token_not_checked(tmp_path):
    """A negative control: a resolver that ignores what a token names (each part unchecked) is caught by a token
    row's cell: the action proceeds on B where it must refuse."""
    from adroit.evidence import version
    real = version.resolve
    world = vm.make(tmp_path)
    row = vm.BY_ID["download.references"]
    taken = _taken(row.id, world, tmp_path)
    vm.change(world, "R")
    with patch.object(version, "resolve", lambda where, **kw: real(version.Token(where.path) if isinstance(
            where, version.Token) else where, **kw)):
        out = vm.run(lambda: _act(row.id, world, taken, tmp_path))
    assert not vm.agrees(vm.outcome(world, out, row.shows), vm.expected(row, "R"))


def test_the_harness_detects_a_read_not_settled(tmp_path):
    """A negative control: a resolution that does not look again at what it read (no transaction) is caught by a T1
    cell: the result read before B's publication beside B's record."""
    from adroit.evidence import version
    world = vm.make(tmp_path)
    with patch.object(version.Version, "_settled", lambda self: True), vm.at(world, "T1"):
        out = vm.run(lambda: _held("history.facts", world, tmp_path))
    found = vm.outcome(world, out, vm.BY_ID["history.facts"].shows)
    assert not vm.agrees(found, vm.expected(vm.BY_ID["history.facts"], "T1")), found


def test_the_harness_detects_an_edge_not_held(tmp_path):
    """A negative control: following a promotion's edges as found (their recorded digests dropped) is caught by a G
    cell: the replaced child is read in place of the one the promotion made."""
    from adroit.evidence import archive
    real = archive.promotion_edges

    def as_found(path, result):
        return [edge._replace(expected="") for edge in real(path, result)]
    path, a_child, b_child, _ = _graph(tmp_path, "G", "child replaced")
    with patch.object(archive, "promotion_edges", as_found):
        digests, _ = _graph_output("graph.export", path, tmp_path)
    assert b_child in digests


# --- the negative controls of the auditor's version-handle audit (DD-03), and of DD-01 and DD-02 -----------------------

def _latest_headline(real):
    """A defect: a version's headline (its verdict and certification) read from the study as saved now, beside the
    record it holds (the auditor's planted fault)."""
    from adroit.evidence import version
    resolve = version.resolve
    return lambda self: real(resolve(self.path, evidence=False))


def test_the_harness_detects_a_headline_of_another_version(tmp_path):
    """DD-03: B's verdict beside A's record is caught by the history's cell (it had passed: the row declared only its
    record, and an A title satisfied it)."""
    from adroit.evidence import version
    world = vm.make(tmp_path)
    with patch.object(version.Version, "headline", _latest_headline(version.Version.headline)), vm.at(world, "R"):
        out = vm.run(lambda: _held("history.facts", world, tmp_path))
    found = vm.outcome(world, out, vm.BY_ID["history.facts"].shows)
    assert found.startswith("mixed"), found


def test_the_harness_detects_a_verification_of_two_bundles(tmp_path):
    """DD-03: A's archive digest beside the decisions reconstructed from B's bundle is caught by the archive's cell (it
    had passed: the cell checked validity and the digest alone)."""
    from adroit.evidence import archive
    real = archive.verify_bundle

    def split(path, **kw):            # the auditor's planted fault: the digest of the first read, the nodes of a second
        first = real(path, **kw)
        return real(path, **kw).model_copy(update={"archive_sha256": first.archive_sha256})
    with patch.object(archive, "verify_bundle", split), pytest.raises(AssertionError, match="not A's whole"):
        test_an_archive_row(tmp_path, "bundle.verify", "R")


def test_the_harness_detects_a_cost_checked_once(tmp_path):
    """DD-02: a cost whose run is checked once, before its ledger is read (the defect: the record read once and kept),
    is caught by the OA cell's transition."""
    from adroit.orchestrator import accounting
    real, first = accounting.read_job, {}

    def once(where):                  # the run's record as first read, whatever it holds by the end of the read
        return first.setdefault(str(where), real(where))
    with patch.object(accounting, "read_job", once), pytest.raises(AssertionError):
        _cost_cells(tmp_path)


def test_the_harness_detects_a_lineage_added_after_publication(tmp_path):
    """DD-01: a reanalysis that adds its lineage after its child's publication, to the folder as saved then (the
    defect), without checking the version its writer wrote, is caught by the publication row's R cell: B acquires
    the lineage and the run returns."""
    from adroit.core.checkpoint import atomic_json
    from adroit.evidence.build import sidecar_path
    from adroit.evidence.version import resolve
    from adroit.orchestrator import reanalysis

    def as_before(token):
        found = resolve(Path(token.path))
        envelope = found.envelope()
        envelope.certificates["reanalysis_lineage"] = json.loads((found.folder / "reanalysis.json").read_text())
        atomic_json(sidecar_path(found.path), envelope.model_dump(mode="json"))
    with patch.object(reanalysis, "_still", as_before), pytest.raises(AssertionError):
        test_a_publication_row(tmp_path, "reanalysis.run", "R")

"""The auditor's DE recheck (the independent audit of 2026-11-05 (de recheck), pin b68e390): DF-01, a writer refused only at its record
had first drawn its figure over the holder's, and the holder's report, its page and a bundle that verified had bound it
as the holder's own; DF-02, a session's spending read apart from its requests, a request settled between the two
readings counted in a cost's total and not in the spending shown. (DF-03, the page oracle's destinations, whole fields
and required fields, is repaired in ``tests/version_matrix.py`` and its harnesses.) Every calculation and provider is
stood in for: no request is sent, and $0 is spent; the dollars are simulated."""
from __future__ import annotations

import hashlib
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from adroit.core import durable
from adroit.core.durable import Busy, publishing
from adroit.core.evidence import EvidenceContext
from adroit.evidence.version import resolve
from adroit.orchestrator import accounting
from tests import version_matrix as vm

FIGURE = "parameter_plane.png"
ROOT = Path(__file__).parents[2]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _files(folder: Path) -> dict[str, bytes]:
    """Every file under ``folder``, by its path there: what a writer has written into it."""
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


@contextmanager
def _waiting(seconds: float = 0.2):
    """A writer's wait for another's hold of a folder shortened (from ``durable.PUBLISH_WAIT``); the lock unchanged."""
    target = durable.publishing.__wrapped__
    kept = target.__defaults__
    target.__defaults__ = (None, seconds)
    try:
        yield
    finally:
        target.__defaults__ = kept


HOLDER = """
import sys, time
from pathlib import Path
from adroit.core.durable import publishing
folder, release = Path(sys.argv[1]), Path(sys.argv[2])
with publishing(folder):
    print("held", flush=True)
    end = time.monotonic() + 60
    while not release.exists() and time.monotonic() < end:
        time.sleep(0.02)
"""


@contextmanager
def _held(folder: Path, by: str):
    """``folder`` held for the block by another writer (``durable.publishing``): another thread of this process, or
    another process."""
    folder.mkdir(parents=True, exist_ok=True)
    if by == "another thread":
        taken, release = threading.Event(), threading.Event()

        def hold():
            with publishing(folder):
                taken.set()
                release.wait(30)
        worker = threading.Thread(target=hold)
        worker.start()
        assert taken.wait(10)
        try:
            yield
        finally:
            release.set()
            worker.join(10)
        return
    release = folder.parent / f".{folder.name}.release"
    process = subprocess.Popen([sys.executable, "-c", HOLDER, str(folder), str(release)], cwd=ROOT,
                               stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "held"
        yield
    finally:
        release.write_text("")
        process.wait(30)


# --- DF-01: a writer draws into a study's folder only while it holds it --------------------------------------------

def _track1_runs(tmp: Path):
    """A and B, two Track 1 results of one study (``vm.versions``), each naming the plane its run draws, and the
    stand-in for Track 1's calculation (``track1._run``), which draws the run's own plane with the production plotter;
    (the folder, A, B, the stand-in, its draws: each run's name and the bytes it drew)."""
    folder = tmp / "study"
    a, b = vm.versions(folder)
    a.plots = b.plots = [FIGURE]
    draws: list[tuple[str, bytes]] = []

    def numerical(request, *args, **kwargs):
        from adroit.parameter_space.plots import plane
        result = a if request.spec.name == a.request.spec.name else b
        plane(result.scan, result.verdict, folder / FIGURE, title=result.request.spec.name)
        draws.append((result.request.spec.name, (folder / FIGURE).read_bytes()))
        return result
    return folder, a, b, numerical, draws


B_RUN = """
import sys
from pathlib import Path
from unittest.mock import patch
from adroit.core import durable
from adroit.core.evidence import EvidenceContext
from adroit.orchestrator import runs, track1, track1_identity
from adroit.parameter_space.plots import plane
folder, given = Path(sys.argv[1]), Path(sys.argv[2])
b = track1.Track1Result.model_validate_json(given.read_text())
durable.publishing.__wrapped__.__defaults__ = (None, 0.2)


def numerical(request, *args, **kwargs):
    plane(b.scan, b.verdict, folder / "parameter_plane.png", title=b.request.spec.name)
    return b
with patch.object(track1, "_run", numerical), patch.object(track1_identity, "dependencies", return_value={}), \\
        patch.object(runs, "capture_request", return_value=EvidenceContext()):
    try:
        runs.track1(b.request, folder)
    except durable.Busy as error:
        print(error)
        sys.exit(3)
"""


@pytest.mark.parametrize("where", ["the same thread", "another thread", "another process"])
def test_a_track1_run_refused_from_a_held_folder_never_draws_into_it(tmp_path, where):
    """DF-01, the auditor's case: A holds the study's folder, as a reanalysis does, and runs the real Track 1 writer (its
    calculation stood in for, its plane drawn by the production plotter); at A's report, B, another Track 1 run into the
    folder through the same writer, in this thread, another thread or another process. B is refused before it writes
    anything: no plane of B's is drawn and the folder's files are as A left them; A's report binds A's plane, and its
    page and its bundle, which verifies, hold A's plane."""
    from adroit.evidence import archive
    from adroit.orchestrator import runs, track1, track1_identity
    folder, a, b, numerical, draws = _track1_runs(tmp_path)
    given = tmp_path / "b.json"
    given.write_text(b.model_dump_json())
    seen: dict = {}

    def b_run():
        try:
            runs.track1(b.request, folder)
            seen["b"] = "published"
        except Busy as error:
            seen["b"] = f"refused: {error}"

    def report(result):
        if result.request.spec.name == a.request.spec.name and "b" not in seen:
            before = _files(folder)
            if where == "the same thread":
                b_run()
            elif where == "another thread":
                with _waiting():
                    worker = threading.Thread(target=b_run)
                    worker.start()
                    worker.join(30)
            else:
                done = subprocess.run([sys.executable, "-c", B_RUN, str(folder), str(given)], cwd=ROOT,
                                      capture_output=True, text=True, timeout=300)
                seen["b"] = (f"refused: {done.stdout}" if done.returncode == 3 else
                             f"exit {done.returncode}: {done.stdout}{done.stderr[-2000:]}")
            seen["unchanged"] = _files(folder) == before
        return f"# {result.request.spec.name}\n\n![plane]({FIGURE})\n"
    with publishing(folder) as claim, patch.object(track1, "_run", numerical), patch.object(track1, "report", report), \
            patch.object(track1_identity, "dependencies", return_value={}), \
            patch.object(runs, "capture_request", return_value=EvidenceContext()):
        runs.track1(a.request, folder, claim=claim)
    assert seen["b"].startswith("refused") and "nothing was written" in seen["b"], seen
    assert seen["unchanged"] and [name for name, _ in draws] == [a.request.spec.name], [n for n, _ in draws]
    drawn = draws[0][1]
    held = resolve(folder, presentation=True)
    assert held.typed().request.spec.name == a.request.spec.name
    assert held.report().state == "bound" and held.report().binding.figures[FIGURE] == sha(drawn)
    assert held.figure(FIGURE) == drawn
    archive.export_run(folder, tmp_path / "export.zip")
    assert archive.verify_bundle(tmp_path / "export.zip").valid
    files = archive.read_bundle(tmp_path / "export.zip")[1]
    assert [data for name, data in files.items() if name.endswith(FIGURE)] == [drawn]


def _writer(tmp: Path, monkeypatch, writer: str):
    """One of ADROIT's writers into a study's folder (``WRITERS``), its calculation and drawing stood in for and noted
    if reached; (its folder, the call, what it reached)."""
    from adroit.evidence import runtime
    from adroit.orchestrator import runs, single_idea, track1, track1_identity
    reached: list[str] = []
    monkeypatch.setattr(track1_identity, "dependencies", lambda: {})
    for module in (runs, runtime):
        monkeypatch.setattr(module, "capture_request", lambda *a, **k: EvidenceContext())
    folder = tmp / "study"
    if writer in ("track1", "track1.run"):
        _, b = vm.versions(folder)
        monkeypatch.setattr(track1, "_run", lambda *a, **k: reached.append("calculated") or b)
        return folder, (lambda: runs.track1(b.request, folder)) if writer == "track1" else \
            (lambda: track1.run(b.request, folder)), reached
    if writer in ("single idea", "single_idea.run"):
        item = vm.single_idea_versions()[1]
        monkeypatch.setattr(single_idea, "_study", lambda *a, **k: reached.append("calculated") or item)
        return folder, (lambda: runs.single_idea(item.request, folder)) if writer == "single idea" else \
            (lambda: single_idea.run(item.request, folder)), reached
    if writer == "native fit":
        from adroit.orchestrator import native_fit
        from adroit.parameter_space import native_joint, simplified
        from tests.orchestrator.test_db_recheck import _native_fit
        (tmp / "fixture").mkdir()
        a, _ = _native_fit(tmp / "fixture")
        request = native_fit.NativeFitRequest(spec=simplified.model("vector", 60, 125), masses_gev=[60],
                                              settings=a.settings)
        monkeypatch.setattr(native_joint, "run", lambda *a_, **k: reached.append("calculated") or a)
        return folder, lambda: native_fit.run_reported(request, folder), reached
    if writer == "native coverage":
        from adroit.orchestrator import native_coverage as nc
        from adroit.parameter_space import simplified
        request = nc.CoverageRequest(spec=simplified.model("vector", 60, 125), masses_gev=[60],
                                     scenarios=[nc.NuisanceScenario(theta=1.0, null_backgrounds=[1.0, 1.0])],
                                     settings=nc.CoverageSettings(outer_trials=1, inner_toys=19))
        monkeypatch.setattr(nc, "prepare", lambda *a, **k: None)
        monkeypatch.setattr(nc, "observed_data", lambda *a, **k: None)
        monkeypatch.setattr(nc, "study", lambda *a, **k: reached.append("calculated"))
        return folder, lambda: nc.run_reported(request, folder), reached
    if writer == "promotion child":
        from adroit.orchestrator import promote
        from adroit.orchestrator.runs import slug
        from adroit.orchestrator.signal import SignalResult
        from tests.ui.acceptance.test_journeys import _toy_signal_study
        parent = tmp / "runs" / "signal"
        label = _toy_signal_study(parent, monkeypatch)
        result = SignalResult.model_validate_json((parent / "result.json").read_bytes())
        c = promote.candidates_of(result)[label]
        origin, spec = promote.models_for(result, c)[0]
        monkeypatch.setattr(single_idea, "run", lambda *a, **k: reached.append("calculated"))
        return parent / "children" / slug(f"{spec.name}_{c.label}"), \
            lambda: promote._study(parent, result, c, origin, spec, {"masses": 2, "toys": 2, "grid": 4}), reached
    if writer == "exclusion":
        from adroit.orchestrator import exclusion
        monkeypatch.setattr(exclusion, "run", lambda request: object())        # its limits: before its folder
        monkeypatch.setattr(exclusion, "plot", lambda *a, **k: reached.append("drawn"))
        return folder, lambda: runs.exclusion("O1", masses_gev=[10], folder=folder), reached
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adroit.evidence.bindings import write_figure
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    return folder, lambda: write_figure(fig, folder / FIGURE, 40), reached


WRITERS = ("track1", "track1.run", "single idea", "single_idea.run", "native fit", "native coverage",
           "promotion child", "exclusion", "a figure")


@pytest.mark.parametrize("by", ["another thread", "another process"])
@pytest.mark.parametrize("writer", WRITERS)
def test_a_writer_into_a_folder_another_holds_writes_nothing(tmp_path, monkeypatch, writer, by):
    """DF-01, each of ADROIT's writers that writes into a study's folder (the auditor's writer sweep: the native fit had
    written its request and its working state before its refusal): with the folder held by another writer, in another
    thread or another process, it is refused (``Busy``) before it calculates into the folder, draws or writes
    anything; the folder's files are as they were."""
    folder, call, reached = _writer(tmp_path, monkeypatch, writer)
    with _held(folder, by), _waiting():
        before = _files(folder)
        with pytest.raises(Busy, match="nothing was (written|drawn)"):
            call()
        assert _files(folder) == before and reached == [], (writer, reached, set(_files(folder)) ^ set(before))


def test_a_report_is_bound_to_the_figures_its_own_writer_drew(tmp_path):
    """DF-01, a figure's identity: its digest is its writer's, kept by its hold of the folder (``Claim.drawn``), never
    taken from a map of this process's draws by path. Under a writer's hold, a figure drawn where none held the folder
    is not its writer's draw: it is bound as read; one its writer drew is bound as drawn, a replacement since withheld;
    and a draw's digest is kept by its hold alone, never once the hold has ended (the auditor's DG recheck, DH-01: there is
    no map of this process's draws)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adroit.evidence import bindings
    from adroit.evidence.bindings import bind, binding, drawn_digest, write_figure
    folder = tmp_path / "study"
    folder.mkdir()
    path = folder / FIGURE
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    write_figure(fig, path, 40)                                # no writer holds the folder
    unheld = path.read_bytes()
    assert drawn_digest(path) == ""                            # kept by the hold taken for the draw, ended with it
    path.write_bytes(unheld + b"\0")                           # replaced since
    with publishing(folder) as claim:
        assert drawn_digest(path) == ""
        assert binding(bind("r", "x", folder, [FIGURE], claim)).figures[FIGURE] == sha(unheld + b"\0")
        write_figure(fig, path, 60)
        own = path.read_bytes()
        path.write_bytes(own + b"\0")                          # replaced after its draw
        assert binding(bind("r", "x", folder, [FIGURE], claim)).figures[FIGURE] == sha(own)
        assert claim.drawn == {str(path.resolve()): sha(own)}
    plt.close(fig)
    assert drawn_digest(path) == "" and not hasattr(bindings, "_DRAWN")


# --- DF-02: a session's figures are of one reading of its journal ------------------------------------------------

def _discovery(tmp: Path):
    """Study A published by a discovery run (attempt-a), charged with its whole session (``accounting.session_cost``),
    whose paid ledger holds A's own request, $1.25 settled; B, a linked extraction's $8.50 request in the same session,
    is settled while the cost is read (the auditor's DE recheck, DF-02). (its folder, its held version, the session service,
    the ledger, the ledger without B's request, and with it, the session.)"""
    from adroit.ui import engine
    from tests.orchestrator import test_de_fixes as de
    folder, held, service, session = de._study(tmp, "receipt")
    journal = service.folder(session) / "paid.jsonl"
    lines = journal.read_text().splitlines(True)
    without, settled = "".join(lines[:2]), "".join(lines)
    journal.write_text(without)
    engine.save(engine.load(folder).model_copy(update={"command": ["constraints", "discover", "--budget", "10"]}))
    (folder / "log.txt").write_text(f"$ adroit constraints discover --budget 10\n# run attempt {de.A}\n"
                                    f"discovery session {session} for SIMULATED\n")
    return folder, held, service, journal, without, settled, session


CHANGES = ("settled after its reading", "settled before its reading", "settled after it, then restored")


@contextmanager
def _settled(service, journal: Path, without: str, settled: str, change: str):
    """B's request settled in the session's ledger at ``change``, about the cost's reading of the session's journal
    (``Intake._journal``, the one reading of the session's paid ledger: its requests and the cap raises it journals,
    DG-01): after it; before it; or after it, and the ledger without it restored at the next reading (the auditor's A→B→A).
    Yields each reading's count."""
    real, reads = service._journal, []

    def read(s):
        if change == "settled before its reading" and not reads:
            journal.write_text(settled)
        if change == "settled after it, then restored" and reads:
            journal.write_text(without)
        found = real(s)
        reads.append(len(found[0]))
        if change != "settled before its reading" and len(reads) == 1:
            journal.write_text(settled)
        return found
    with patch.object(service, "_journal", read):
        yield reads


@pytest.mark.parametrize("surface", ["cost", "card", "list", "cli"])
@pytest.mark.parametrize("change", CHANGES)
def test_a_session_s_cost_is_of_one_reading_of_its_journal(tmp_path, change, surface):
    """DF-02, the auditor's case: a linked extraction's request settled in a discovery's session while the discovery study's
    cost is read, before or after that reading, or after it and then undone. The session's spending, its reserved and
    remaining dollars, the requests counted and the total are all of one reading of its journal, which is read once: the
    reading before B's request ($1.25, $8.75 left) or after it ($9.75, $0.25 left), never one beside the other; and so
    on the card, in Studies and by ``adroit studies``, its line and its total."""
    from adroit.orchestrator.cli import app
    from adroit.ui import pages
    folder, held, service, journal, without, settled, _ = _discovery(tmp_path)
    wanted = 9.75 if change == "settled before its reading" else 1.25
    with patch.object(accounting, "_budgets", return_value=service), \
            _settled(service, journal, without, settled, change) as reads:
        if surface == "cost":
            c = accounting.held_cost(held)
        else:
            shown = (pages.study_cost(held) if surface == "card" else pages.list_cost(held) if surface == "list" else
                     CliRunner().invoke(app, ["studies", str(folder.parent)]).output)
    assert len(reads) == 1, reads
    if surface == "cost":
        facts = c.requests.values()
        assert not c.damaged and c.scope == "session" and c.own_usd == 1.25, c
        assert c.session_spent_usd == c.run_usd == pytest.approx(wanted), c
        assert sum(f.settled_usd for f in facts) == pytest.approx(wanted)
        assert c.session_reserved_usd == pytest.approx(sum(f.reserved_usd for f in facts)) == 0.0
        assert c.session_remaining_usd == pytest.approx(c.session_cap_usd - wanted)
        assert accounting.total([c]).settled_usd == pytest.approx(wanted)
        return
    other = "9.75" if wanted == 1.25 else None
    assert f"${wanted:.2f}" in shown and (other is None or other not in shown), shown
    if surface == "cli":
        assert f"total: ${wanted:.2f} settled" in shown, shown


def test_a_session_s_status_and_requests_are_one_reading_of_its_ledger(tmp_path, monkeypatch):
    """DF-02, the reading: ``Intake.snapshot`` gives a session's status and its requests from one read of its paid
    ledger, its status computed from the requests it returns."""
    from adroit.orchestrator import model_intake
    _, _, service, journal, _, settled, session = _discovery(tmp_path)
    journal.write_text(settled)
    real, reads = model_intake.read_held, []             # the ledger's one reading (DG-01: with its cap raises; DO-01:
    monkeypatch.setattr(model_intake, "read_held", lambda path: reads.append(path) or real(path))   # and what it held)
    status, requests = service.snapshot(session)
    assert len(reads) == 1
    assert status["spent"] == pytest.approx(sum(r.cost_usd for r in requests.values() if r.state == "settled"))
    assert status == service._status(service.session(session), requests)

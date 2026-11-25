"""The auditor's DF recheck (the independent audit of 2026-11-06 (df recheck), pin d6d0cbe): DG-01, a session's cap read from its record
before a raise, and its spending from its paid ledger after it, the cost showing the old cap with the new spending;
DG-02, a figure drawn where no writer held its folder, still rendering when another writer took the folder, written
over that writer's own; DG-04, a promotion's child capturing its request before its halo and propagation defaults were
resolved, so that its provenance was downgraded to "changed during the run". (DG-03, the page oracle's destinations
and chart, is repaired in ``tests/version_matrix.py`` and its harnesses.) Every calculation and provider is stood in
for: no request is sent, and $0 is spent; the dollars are simulated."""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from adroit.orchestrator import accounting, model_intake
from tests.orchestrator import test_de_fixes as de, test_df_fixes as df


# --- DG-01: a session's cap and its spending are of one state of the session --------------------------------------

def _request(journal: Path, name: str, dollars: float, settled: bool = True) -> None:
    """A simulated request journalled in a session's paid ledger as its writer leaves it: reserved, then settled (or
    its bill not yet in)."""
    rows = [{"id": name, "state": "reserved", "provider": "anthropic", "model": "SIMULATED fixture",
             "reserved_usd": dollars}]
    rows += [{"id": name, "state": "settled", "cost_usd": dollars}] if settled else []
    with journal.open("a") as ledger:
        ledger.write("".join(json.dumps(r) + "\n" for r in rows))


def _two_dollar_session(tmp: Path) -> tuple[object, str]:
    """``test_de_fixes._session`` with a $2 cap and A's $1.25 request alone: a cap that can be raised."""
    from adroit.library.personal import Catalog
    service = model_intake.Intake(Catalog(tmp / "models"))
    session = service.start(budget=2).session_id
    _request(service.folder(session) / "paid.jsonl", f"r-{de.A}", 1.25)
    return service, session


def _discovery(tmp: Path):
    """Study A, published by a discovery run charged with its whole session (``test_df_fixes._discovery``), whose
    session's cap is $2, $1.25 of it spent: (its folder, its held version, the session service, its ledger, the
    session)."""
    with patch.object(de, "_session", _two_dollar_session):
        folder, held, service, journal, _, settled, session = df._discovery(tmp)
    journal.write_text(settled)
    return folder, held, service, journal, session


CAP_CHANGES = ("raised, then spent under", "raised, then reserved under", "raised alone",
               "raised and spent under, its record then restored")


def _change(service, session: str, journal: Path, change: str) -> None:
    """``change`` made to the session: its cap raised to $10 by ``Intake.raise_cap``, then (or not) a linked
    extraction's $8.50 request settled or reserved under it; or the raise and the request made, and the session's
    record then restored as it was before the raise (the auditor's "a cap update restored")."""
    record = service.folder(session) / "session.json"
    before = record.read_bytes()
    service.raise_cap(session, 10, confirmed=True, reason="SIMULATED fixture")
    if change != "raised alone":
        _request(journal, f"r-{de.B}", 8.5, settled=change != "raised, then reserved under")
    if change.endswith("restored"):
        record.write_bytes(before)


@contextmanager
def _reading(journal: Path, act):
    """``act`` (given the number of readings so far) done before each reading of a session's paid ledger, its bytes
    read (``durable.read_own``, ``budget.ledger_bytes``: after its record has been read, as every reader of a session
    reads it; ``Path.read_bytes`` before the auditor's DS recheck, DT-01, and ``Path.read_text`` before its DN recheck,
    DO-01), outside the readings ``act`` makes itself (``raise_cap`` reads the ledger too). Yields the readings."""
    from adroit.core import durable
    real, reads, acting = durable.read_own, [], []

    def read_own(path, folder=None):
        if Path(path) == journal and not acting:
            acting.append(True)
            try:
                act(len(reads))
            finally:
                acting.clear()
            reads.append(Path(path))
        return real(path, folder)
    with patch.object(durable, "read_own", read_own):
        yield reads


@contextmanager
def _between(service, session: str, journal: Path, change: str):
    """The auditor's DG-01 window: ``change`` made once, after the session's record is read and before its paid ledger is.
    Yields the readings of the ledger."""
    with _reading(journal, lambda n: n or _change(service, session, journal, change)) as reads, \
            patch.object(model_intake, "SETTLING", (0.0,) * 6, create=True):
        yield reads


SURFACES = ("cost", "lines", "session", "card", "list", "cli")


def _shown(surface: str, folder: Path, held, service, session: str):
    """The held study's cost on ``surface``: the cost itself; its lines on the run's page (this run's, then the
    session's total and cap); the session's money on its own page (``session_money``); the card, its line in Studies,
    ``adroit studies`` (its spending alone)."""
    from adroit.orchestrator.cli import app
    from adroit.ui import outcomes, pages
    if surface == "cost":
        return accounting.held_cost(held)
    if surface == "lines":
        return "\n".join(outcomes.cost_lines(accounting.held_cost(held)))
    if surface == "session":
        return accounting.session_money(service, session)
    if surface == "card":
        return pages.study_cost(held)
    if surface == "list":
        return pages.list_cost(held)
    return CliRunner().invoke(app, ["studies", str(folder.parent)]).output


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("change", CAP_CHANGES)
def test_a_session_s_cap_and_spending_are_of_one_state_of_it(tmp_path, change, surface):
    """DG-01, the auditor's case: a discovery study's session ($2 cap, $1.25 spent) has its cap raised to $10, and $8.50
    spent or reserved under it, after the cost has read the session's record and before it reads its ledger. Every
    figure the cost shows, on every surface, is the session's state after the change ($10 cap, $9.75 spent or $8.50
    reserved, $0.25 left), as a reading after it shows it, never the old cap with the new spending (the auditor's "$9.75 spent
    of its approved $2.00 cap ($0.0000 left)"); a record restored to before the raise, its ledger journalling the raise
    and the spending under it, is named and shows no figure."""
    folder, held, service, journal, session = _discovery(tmp_path)
    with patch.object(accounting, "_budgets", return_value=service):
        with _between(service, session, journal, change) as reads:
            shown = _shown(surface, folder, held, service, session)
        assert reads, "the session's ledger was read"
        with patch.object(model_intake, "SETTLING", (0.0,) * 6, create=True):
            after = _shown(surface, folder, held, service, session)
    assert shown == after
    restored = change.endswith("restored")
    if surface != "cost":
        assert "$2.00" not in shown, shown
        if surface in ("lines", "session"):
            assert ("of its approved $10.00 cap" in shown) is not restored, shown
            assert ("not available" in shown) is restored, shown
        return
    if restored:
        assert shown.session_cap_usd is None and shown.session_spent_usd is None, shown
        assert any("cap raise to $10.00" in d and "record does not have" in d for d in shown.damaged), shown.damaged
        return
    spent, reserved = {"raised, then spent under": (9.75, 0.0), "raised, then reserved under": (1.25, 8.5),
                       "raised alone": (1.25, 0.0)}[change]
    status = service.snapshot(session)[0]
    assert not shown.damaged, shown.damaged
    assert shown.session_cap_usd == status["cap"] == 10
    assert shown.session_spent_usd == pytest.approx(status["spent"]) == spent
    assert shown.session_reserved_usd == pytest.approx(status["reserved_uncertain"]) == reserved
    assert shown.session_remaining_usd == pytest.approx(status["remaining"]) == 10 - spent - reserved
    assert any("$10.00 cap" in line for line in accounting.cost_lines(shown)), accounting.cost_lines(shown)


def _journalled_only(service, session: str) -> bytes:
    """``raise_cap`` to $10 stopped between its two writes: the raise journalled in the session's ledger, its record
    as before the raise. (The raised record's bytes, as ``raise_cap`` writes them.)"""
    record = service.folder(session) / "session.json"
    before = record.read_bytes()
    service.raise_cap(session, 10, confirmed=True, reason="SIMULATED fixture")
    raised = record.read_bytes()
    record.write_bytes(before)
    return raised


def test_a_raise_being_made_is_read_once_its_record_is_written(tmp_path, monkeypatch):
    """DG-01, the raise's own window: ``raise_cap`` journals a raise in the ledger, then writes the record. A reading
    between the two is read again after a pause, and is the raised session's once its record is written; no reading of
    the two halves is returned."""
    service, session = _two_dollar_session(tmp_path)
    raised, pauses = _journalled_only(service, session), []

    def pause(seconds):
        pauses.append(seconds)
        (service.folder(session) / "session.json").write_bytes(raised)
    monkeypatch.setattr(model_intake.time, "sleep", pause)
    status, _ = service.snapshot(session)
    assert pauses == [model_intake.SETTLING[0]]
    assert status == {"cap": 10, "spent": 1.25, "reserved_uncertain": 0, "remaining": 8.75}


def test_a_raise_interrupted_between_its_ledger_and_its_record_is_named(tmp_path, monkeypatch):
    """DG-01: a raise journalled whose record was never written (its writer stopped between the two, or the record
    restored) is read again after each pause, about a second in all, and then named: its cap is not known with its
    spending."""
    service, session = _two_dollar_session(tmp_path)
    _journalled_only(service, session)
    pauses = []
    monkeypatch.setattr(model_intake.time, "sleep", pauses.append)
    with pytest.raises(model_intake.UnsettledSession, match=r"a cap raise to \$10\.00 .* that its record does not have"):
        service.snapshot(session)
    assert pauses == list(model_intake.SETTLING) and sum(pauses) < 1.0


def test_a_session_whose_record_changes_at_every_reading_is_named(tmp_path, monkeypatch):
    """DG-01: a session whose record is rewritten during each reading of its ledger is read again after each pause,
    about a second in all, and then named, never read as the record before beside the ledger after."""
    service, session = _two_dollar_session(tmp_path)
    caps = iter(2 + k / 10 for k in range(1, 21))
    monkeypatch.setattr(model_intake.time, "sleep", lambda s: None)
    with _reading(service.folder(session) / "paid.jsonl",
                  lambda n: service.raise_cap(session, next(caps), confirmed=True, reason="SIMULATED fixture")):
        with pytest.raises(model_intake.UnsettledSession, match="its record changed while its paid ledger was read"):
            service.snapshot(session)
        assert accounting.session_money(service, session).startswith(
            "spending not available (its record and its paid ledger were not of one state")
    assert sum(model_intake.SETTLING) < 1.0


def test_a_session_read_while_another_thread_raises_and_spends_is_always_one_of_its_states(tmp_path):
    """DG-01, unscripted: one thread raises the session's cap a dollar at a time from $2 to $10 and spends $0.50
    under each new cap; meanwhile this thread reads the session's status, again and again. Each reading is a state the
    session was in (a cap, and the spending made under it or before), or names the session as not settled."""
    service, session = _two_dollar_session(tmp_path)
    journal = service.folder(session) / "paid.jsonl"
    states = {(2.0, 1.25)}
    for cap in range(3, 11):
        states |= {(float(cap), 1.25 + 0.5 * (cap - 3)), (float(cap), 1.25 + 0.5 * (cap - 2))}
    done = threading.Event()

    def writer():
        for cap in range(3, 11):
            service.raise_cap(session, cap, confirmed=True, reason="SIMULATED fixture")
            _request(journal, f"r-{cap}", 0.5)
        done.set()
    thread = threading.Thread(target=writer)
    seen, named = set(), 0
    thread.start()
    while not done.is_set() or len(seen) < 1:
        try:
            status = service.budget_status(session)
        except model_intake.UnsettledSession:
            named += 1
            continue
        seen.add((float(status["cap"]), round(status["spent"], 2)))
    thread.join()
    assert seen <= states, seen - states
    assert (float(service.budget_status(session)["cap"]), service.budget_status(session)["spent"]) == (10.0, 5.25)


# --- DG-02: a figure is drawn under a hold of its folder from before it is rendered ---------------------------------

A_DRAWS = """
import hashlib, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from adroit.core.durable import publishing
from adroit.evidence.bindings import write_figure
path = Path(sys.argv[1])
fig, ax = plt.subplots()
ax.plot([0, 1], [0, 2])
print("trying", flush=True)
with publishing(path.parent) as claim:
    write_figure(fig, path, 40)
    print(claim.drawn[str(path.resolve())], hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
"""


def _a_draws(path: Path, by: str):
    """A, a writer that takes ``path``'s folder (``publishing``) and draws its own figure there under its hold, in
    another thread or another process: (a callable that waits until A is trying to take the folder, a callable that
    waits for A to finish and gives (the digest A's hold keeps for its figure, the digest of the file as A read it under
    its hold))."""
    import hashlib
    import subprocess
    import sys
    if by == "another process":
        process = subprocess.Popen([sys.executable, "-c", A_DRAWS, str(path)], cwd=df.ROOT, stdout=subprocess.PIPE,
                                   text=True)
        return (lambda: process.stdout.readline().strip() == "trying",
                lambda: (process.wait(60), tuple(process.stdout.readline().split()))[1])
    import matplotlib.pyplot as plt
    from adroit.core.durable import publishing
    from adroit.evidence.bindings import write_figure
    trying, out = threading.Event(), []

    def a():
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 2])
        trying.set()
        with publishing(path.parent) as claim:
            write_figure(fig, path, 40)
            out.append((claim.drawn[str(path.resolve())], hashlib.sha256(path.read_bytes()).hexdigest()))
        plt.close(fig)
    thread = threading.Thread(target=a)
    thread.start()
    return trying.wait, lambda: (thread.join(60), out[0])[1]


@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_a_figure_rendering_when_another_writer_takes_its_folder_is_never_written_under_that_hold(tmp_path, by):
    """DG-02, the auditor's case: B draws a figure into a folder no writer holds and is still rendering it when A, another
    writer (another thread or another process), takes the folder to draw its own. B's draw holds the folder from before
    it renders until its digest is kept, so A waits for it: B's figure is written, then A's under A's hold, and A's
    is the figure in the folder and the one its hold names; B's draw, its hold ended, is named by no map of this
    process's draws (DH-01). Before, B had only probed the folder, and wrote over A's figure under A's hold."""
    import hashlib
    import time
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adroit.evidence.bindings import drawn_digest, write_figure
    path = tmp_path / "study" / df.FIGURE
    path.parent.mkdir()
    rendering, release, written = threading.Event(), threading.Event(), []
    fig, ax = plt.subplots()
    ax.plot([0, 1], [1, 0])
    real = fig.savefig

    def render(*args, **kwargs):
        rendering.set()
        assert release.wait(30)
        return real(*args, **kwargs)
    fig.savefig = render

    def b():
        write_figure(fig, path, 40)
        written.append(hashlib.sha256(path.read_bytes()).hexdigest())
    thread = threading.Thread(target=b)
    thread.start()
    assert rendering.wait(10)
    trying, finished = _a_draws(path, by)
    assert trying()
    time.sleep(0.5)                                  # A, trying to take the folder, while B is still rendering
    release.set()
    thread.join(30)
    a_drawn, a_read = finished()
    plt.close(fig)
    final = hashlib.sha256(path.read_bytes()).hexdigest()
    assert a_drawn == a_read == final != written[0], (a_drawn, a_read, final, written)
    assert drawn_digest(path) == ""                  # B's draw was kept by the hold taken for it, now ended (DH-01)


def test_a_figure_drawn_under_its_writer_s_hold_is_the_writer_s(tmp_path):
    """DG-02: a writer holding its folder draws under its own hold (no second hold taken, so no wait on itself), and
    the figure's digest is its hold's; a figure drawn where no writer holds the folder leaves no hold behind, and no
    digest in any map of this process's draws (DH-01: there is none)."""
    import hashlib
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adroit.core import durable
    from adroit.core.durable import publishing
    from adroit.evidence import bindings
    from adroit.evidence.bindings import write_figure
    path = tmp_path / "study" / df.FIGURE
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    with publishing(path.parent) as claim:
        write_figure(fig, path, 40)
        assert claim.drawn == {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()}
        assert bindings.drawn_digest(path) == claim.drawn[str(path.resolve())]
    assert bindings.drawn_digest(path) == ""
    write_figure(fig, path, 40)
    plt.close(fig)
    assert bindings.drawn_digest(path) == "" and not hasattr(bindings, "_DRAWN")
    assert durable.holding(path) is None and not durable._HELD


# --- DG-04: a single-idea study captures the request it calculates -------------------------------------------------

def _calculation(changed: bool = False):
    """``single_idea._study`` stood in for (no fit, scan or search runs): a typed result of the request it is given,
    after ``single_idea.run``'s own resolution of its defaults; ``changed``: its request changed after its capture (a
    genuine change during the run: one more toy)."""
    from adroit.orchestrator import single_idea

    def study(request, folder, fetch=None, claim=None):
        Path(folder).mkdir(parents=True, exist_ok=True)
        request = request.model_copy(update={"toys": request.toys + 1}) if changed else request
        return single_idea.SingleIdeaResult(request=request, level="undetermined", summary="SIMULATED calculation",
                                            fit_quality="not_computed", constraint_compatibility="undetermined",
                                            thermal_viability="undetermined", unsupported="SIMULATED calculation")
    return study


def _captured(folder: Path):
    """(the child's published evidence, the request its result saved) in ``folder``."""
    from adroit.core.evidence import EvidenceEnvelope
    from adroit.orchestrator.single_idea import SingleIdeaResult
    envelope = EvidenceEnvelope.model_validate_json((folder / "result.evidence.json").read_text())
    saved = SingleIdeaResult.model_validate_json((folder / "result.json").read_bytes()).request
    return envelope, saved


def _promotion_child(tmp: Path, monkeypatch, changed: bool) -> Path:
    """A real promotion's child (``promote._study``: the parent a toy signal study, as journey 2's), its calculation
    alone stood in for (``_calculation``): its folder."""
    from adroit.orchestrator import promote, single_idea
    from adroit.orchestrator.signal import SignalResult
    from tests.ui.acceptance.test_journeys import _toy_signal_study
    parent = tmp / "runs" / "signal"
    label = _toy_signal_study(parent, monkeypatch)
    result = SignalResult.model_validate_json((parent / "result.json").read_bytes())
    c = promote.candidates_of(result)[label]
    origin, spec = promote.models_for(result, c)[0]
    monkeypatch.setattr(single_idea, "_study", _calculation(changed))
    return Path(promote._study(parent, result, c, origin, spec, {"masses": 2, "toys": 2, "grid": 4}).folder)


def _assistant_study(tmp: Path, monkeypatch, changed: bool) -> Path:
    """The research assistant's single-idea study (``research_assistance._execute_single``) of a request whose halo
    and propagation are left to their defaults, its calculation alone stood in for: its folder."""
    from adroit.orchestrator import research_assistance as service, single_idea
    from tests.orchestrator.test_research_assistance import request
    original = request()
    asked = original.model_copy(update={"study": original.study.model_copy(update={"native_joint": None})})
    result = service.run(asked, tmp, execute_plan=False)
    monkeypatch.setattr(single_idea, "_study", _calculation(changed))
    service._execute_single(asked, result, tmp)
    return tmp / "single_idea"


WRITERS = {"a promotion's child": _promotion_child, "the assistant's single idea": _assistant_study}


def _exported(folder: Path, tmp: Path):
    """The study in ``folder`` exported by the production exporter (``archive.export_run``) and verified: (whether
    its bundle is valid, the reasons its reproduction gives that name its calculation's provenance)."""
    from adroit.evidence import archive
    from adroit.evidence.version import resolve
    bundle = tmp / "bundle.zip"
    archive.export_run(resolve(folder, presentation=True), bundle)
    verification = archive.verify_bundle(bundle)
    return verification.valid, [r for r in verification.reproduction_reasons if "provenance" in r]


@pytest.mark.parametrize("writer", WRITERS)
def test_a_single_idea_study_captures_the_request_it_calculates(tmp_path, monkeypatch, writer):
    """DG-04, the auditor's case: a promotion's child (and the research assistant's single-idea study) of a request whose
    halo and propagation are left to their defaults. Its request is prepared (its defaults resolved) before it is
    captured, as the single idea's own writer does: its evidence's captured request is the request it calculated and
    saved, its calculation identity "captured", with no note that its request changed during the run; and so its
    bundle. Before, its request had been captured with the defaults unresolved, and its provenance downgraded to
    "changed during the run" though nothing had changed."""
    from adroit.core.evidence import content_hash
    folder = WRITERS[writer](tmp_path, monkeypatch, False)
    envelope, saved = _captured(folder)
    assert saved.halo is not None and saved.propagation is not None, saved
    assert envelope.context.request_sha256 == content_hash(saved.model_dump(mode="json")) == envelope.input_sha256
    assert envelope.context.origin == "captured", envelope.context
    assert not any("changed since calculation start" in n for n in envelope.context.notes), envelope.context.notes
    assert not any("calculation identity" in w for w in envelope.warnings), envelope.warnings
    valid, reasons = _exported(folder, tmp_path)
    assert valid and not any("changed_during_run" in r for r in reasons), reasons


@pytest.mark.parametrize("writer", WRITERS)
def test_a_request_changed_after_its_capture_is_still_named(tmp_path, monkeypatch, writer):
    """DG-04's negative control: a request that does change after its capture (its calculation saved one more toy)
    is still named, its calculation identity "changed during the run": resolving defaults first suppresses no genuine
    change."""
    folder = WRITERS[writer](tmp_path, monkeypatch, True)
    envelope, _ = _captured(folder)
    assert envelope.context.origin == "changed_during_run", envelope.context
    assert any("changed since calculation start" in n for n in envelope.context.notes), envelope.context.notes
    valid, reasons = _exported(folder, tmp_path)
    assert valid and any("changed_during_run" in r for r in reasons), reasons

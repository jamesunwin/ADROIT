"""Two operating-system processes contending for one budget (the gap plan's H6, from the auditor's consistency audit,
inventory C: "no two-OS-process account race claim tested"; the owner's review of 2026-10-25 asked for real contention,
not timing). Each process builds its account from the shared journal, so two that both reserved would each see the
cap's whole remainder. The paid paths take the budget owner's run lock before they build the account; these
controls check that the lock really serialises them.

How the contention is made real: both processes wait at one barrier placed just before the budget owner's run lock
(the last step before the account is built and the request reserved); the one that reaches its reservation first
waits there, holding the lock, until the other's attempt has ended (refused, or, were the lock not to hold, reaching
its own reservation, after which both go on). Each refusal names the lock it came from. The cap admits one request and
not two. Cases: two processes on one intake session; constraint discovery and a linked extraction (two session
identifiers, one budget owner); each with an uncertain bill already in the journal; each with the journal lost
(CO-05's refusal). Expected throughout: the journal's commitment never exceeds the cap, and a refused process
reserves nothing. The provider is a scripted SDK in each process; no request leaves the machine, $0.
"""
from __future__ import annotations

import json
import multiprocessing
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from adroit.agents.budget import read_ledger

TEX = r"\mathcal{L} = \bar\chi i\gamma^\mu\partial_\mu\chi - m_\chi\bar\chi\chi"
HOLD = 30.0          # seconds the first process waits, inside its reservation, for the other's attempt


@contextmanager
def _scripted(hold=None, reserved: list | None = None, before_send=None):
    """Every language model a scripted SDK (an answer that is no schema's, 100 input and 20 output tokens); each
    reservation preceded by ``hold()`` and, once made, noted in ``reserved``; the first request, once journalled as
    reserved, held by ``before_send()`` before it is sent."""
    import adroit.agents.llm as llm
    from adroit.agents import budget
    sent = []

    def create(**kw):
        if before_send is not None and not sent:
            before_send()
        sent.append(True)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="not an answer")],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))
    sdk = SimpleNamespace(messages=SimpleNamespace(create=create))
    real, real_for, real_reserve = llm.LLMClient, llm.client_for, budget.BudgetAccount.reserve

    def reserve(self, provider, cost):
        if hold is not None:
            hold()
        key = real_reserve(self, provider, cost)
        if reserved is not None:
            reserved.append(cost)
        return key
    llm.LLMClient = lambda model, max_tokens=8192, **k: real(model=model, max_tokens=max_tokens, client=sdk)
    llm.client_for = lambda model, **k: real(model=model, max_tokens=8192, client=sdk)
    budget.BudgetAccount.reserve = reserve
    try:
        yield
    finally:
        llm.LLMClient, llm.client_for, budget.BudgetAccount.reserve = real, real_for, real_reserve


def _attempt(kind: str, paths: dict, session: str) -> str:
    """One paid step through its real entry point; what came of it."""
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.library.personal import Catalog
    if kind == "intake":
        from adroit.orchestrator.model_intake import Intake
        Intake(Catalog(Path(paths["models"]))).step(session, "tex", TEX)
        return "completed"
    if kind == "discovery":
        from adroit.orchestrator import constraint_discovery as cd
        from tests.orchestrator.test_constraint_discovery import Web, _abstracts, _resolver
        state = cd.Discovery(ExperimentalCatalog(Path(paths["private"])), abstracts=_abstracts, fetch=Web(),
                             resolver=_resolver).run(session)
        stage = state.get("relevance", {})
        return f"relevance {stage.get('status')}: {stage.get('detail', '')}"
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    ExperimentalExtraction(ExperimentalCatalog(Path(paths["private"]))).step(session, 0)
    return "completed"


def _gated(owner: Path, start, unlocked: bool):
    """The paid paths' run lock, wrapped (module docstring): on the budget owner's folder, both processes first meet at
    the barrier, then contend for it (``unlocked``: the negative control, no lock there); a refusal names the lock it
    came from, so that a control is not passed by another lock (the catalog's brief asset lock is one)."""
    import sys
    from contextlib import contextmanager
    from adroit.core.checkpoint import run_lock as real
    met = []

    @contextmanager
    def lock(folder):
        mine = Path(folder).resolve() == owner.resolve()
        if mine and not met:
            met.append(True)
            start.wait(timeout=120)
        if mine and unlocked:
            yield
            return
        held = real(Path(folder))
        try:
            held.__enter__()
        except RuntimeError as error:
            raise RuntimeError(f"refused at {'the budget owner' if mine else Path(folder).name}'s lock: {error}") \
                from None
        try:
            yield
        finally:
            held.__exit__(*sys.exc_info())
    return lock


def _child(kind: str, paths: dict, session: str, owner: str, which: int, start, done, out, hold: float = HOLD,
           unlocked: bool = False, paired=None) -> None:
    """A process's paid step (``_attempt``) through the barrier at the budget owner's lock (``_gated``); its first
    reservation held until the other process's attempt has ended (module docstring). The second process starts half
    a second after the first, so that their steps' earlier, unrelated locks (the catalog's asset lock) do not meet;
    the contention itself is at the barrier."""
    import time
    from adroit.orchestrator import constraint_discovery, experimental_extraction, model_intake
    lock = _gated(Path(owner), start, unlocked)
    for module in (model_intake, constraint_discovery, experimental_extraction):
        module.run_lock = lock
    reserved: list[float] = []
    time.sleep(0.5 * which)
    with _scripted(lambda: done[1 - which].wait(timeout=hold), reserved,
                   None if paired is None else lambda: paired.wait(timeout=30)):
        try:
            outcome = _attempt(kind, paths, session)
        except Exception as error:                     # noqa: BLE001 - every outcome is reported, then judged
            outcome = f"{type(error).__name__}: {str(error)[:300]}"
        finally:
            done[which].set()
    out.put((which, kind, outcome, reserved))


def _contend(kinds: tuple[str, str], sessions: tuple[str, str], owner: Path, paths: dict, **options) -> list[tuple]:
    """The two processes, through the barrier; each one's (index, kind, outcome, the dollars it reserved)."""
    context = multiprocessing.get_context("spawn")
    start, done, out = context.Barrier(2), [context.Event(), context.Event()], context.Queue()
    if options.pop("paired", False):                 # the negative control: both reserve before either sends
        options["paired"] = context.Barrier(2)
    procs = [context.Process(target=_child, args=(kinds[i], paths, sessions[i], str(owner), i, start, done, out),
                             kwargs=options) for i in range(2)]
    for p in procs:
        p.start()
    results = [out.get(timeout=300) for _ in procs]
    for p in procs:
        p.join(timeout=60)
    return sorted(results)


def _peak(ledger: Path) -> float:
    """The largest commitment the shared journal ever held, replayed line by line in the order written: settled
    dollars and every open or uncertain reservation at each moment (a cap breached while two requests were in flight
    is not hidden by their small settlements afterwards). The journal is checked whole first (``read_ledger``)."""
    read_ledger(ledger)
    reserved, settled, peak = {}, 0.0, 0.0
    for line in ledger.read_text().splitlines():
        row = json.loads(line) if line.strip() else {}
        if row.get("state") == "reserved":
            reserved[row["id"]] = row["reserved_usd"]
        elif row.get("state") == "settled":
            reserved.pop(row["id"], None)
            settled += row["cost_usd"]
        peak = max(peak, settled + sum(reserved.values()))
    return peak


def _bound(ledger: Path) -> float:
    """The first reservation a journal holds."""
    return next(json.loads(line)["reserved_usd"] for line in ledger.read_text().splitlines()
                if json.loads(line).get("state") == "reserved")


def _uncertain(ledger: Path, dollars: float) -> None:
    """A request already in the journal whose bill is not known."""
    with ledger.open("a") as stream:
        stream.write(json.dumps({"id": "earlier", "state": "reserved", "provider": "anthropic",
                                 "model": "claude-opus-5-5", "reserved_usd": dollars}) + "\n")
        stream.write(json.dumps({"id": "earlier", "state": "billing_uncertain", "error": "TimeoutError"}) + "\n")


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Every writable folder of both processes under the test's own (the processes read them from ADROIT_*)."""
    out = {name: tmp_path / name for name in ("models", "private", "runs", "data")}
    for name, folder in out.items():
        folder.mkdir()
    for variable, name in (("ADROIT_MODEL_LIBRARY_DIR", "models"), ("ADROIT_EXPERIMENTAL_LIBRARY_DIR", "private"),
                           ("ADROIT_RUNS_DIR", "runs"), ("ADROIT_DATA_DIR", "data")):
        monkeypatch.setenv(variable, str(out[name]))
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(), "data_dir", out["data"])
    return {k: str(v) for k, v in out.items()}


def _judge(results: list[tuple], ledger: Path, cap: float, lost: bool = False) -> None:
    """The invariants: the commitment within the cap; a refused process reserved nothing; with the journal lost,
    both refused, nothing reserved and no journal made."""
    refused = [r for r in results if not r[3]]
    if lost:
        assert len(refused) == 2 and not ledger.exists(), results
        assert all("is missing" in r[2] or "refused at the budget owner's lock" in r[2] for r in results), results
        return
    assert _peak(ledger) <= cap + 1e-9, (results, _peak(ledger), cap)
    winners = [r for r in results if r[3]]
    assert len(winners) == 1 and len(refused) == 1, results          # the contention was real: one went first
    assert "refused at the budget owner's lock" in refused[0][2], results     # at the owner's lock, before reserving


@pytest.mark.parametrize("variant", ["plain", "uncertain", "lost"])
def test_two_processes_on_one_intake_session(paths, variant):
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service = Intake(Catalog(Path(paths["models"])))
    probe = service.start(10.0)
    with _scripted():
        try:
            _attempt("intake", paths, probe.session_id)
        except ValueError:
            pass
    bound = _bound(service.folder(probe.session_id) / "paid.jsonl")
    earlier = bound / 2 if variant == "uncertain" else 0.0
    cap = round(earlier + 1.5 * bound, 6)                          # one request fits, two do not
    s = service.start(cap)
    ledger = service.folder(s.session_id) / "paid.jsonl"
    if variant == "uncertain":
        _uncertain(ledger, earlier)
    if variant == "lost":
        ledger.unlink()
    results = _contend(("intake", "intake"), (s.session_id, s.session_id), service.folder(s.session_id), paths)
    _judge(results, ledger, cap, lost=variant == "lost")


def _linked(paths: dict, cap: float) -> tuple[str, str]:
    """A discovery session (the budget owner, ``cap``) and an extraction sharing its budget: two identifiers."""
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator import constraint_discovery as cd
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    from tests.orchestrator.test_constraint_discovery import Web, _abstracts, _model, _resolver
    from tests.experimental_extraction_fixtures import TEXT
    catalog = ExperimentalCatalog(Path(paths["private"]))
    discovery = cd.Discovery(catalog, abstracts=_abstracts, fetch=Web(), resolver=_resolver)
    folder = Path(paths["runs"]) / f"model_{len(list(Path(paths['runs']).iterdir()))}"
    folder.mkdir()
    path, _ = _model(folder)
    owner = discovery.start(str(path), cd.Options(budget=cap)).session_id
    source = folder / "source.txt"
    source.write_text(TEXT)
    revision = catalog.import_files([source], "a source")
    child = ExperimentalExtraction(catalog).start(revision.reference, 0, vision=False, budget_session=owner).session_id
    return owner, child


@pytest.mark.parametrize("variant", ["plain", "uncertain", "lost"])
def test_discovery_and_a_linked_extraction_sharing_one_budget_owner(paths, variant):
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    budgets = ExperimentalExtraction(ExperimentalCatalog(Path(paths["private"]))).budgets
    bounds = []
    for kind in ("discovery", "extraction"):                         # each path's first reservation, measured
        owner, child = _linked(paths, 10.0)
        with _scripted():
            try:
                _attempt(kind, paths, owner if kind == "discovery" else child)
            except ValueError:
                pass
        bounds.append(_bound(budgets.folder(owner) / "paid.jsonl"))
    earlier = min(bounds) / 2 if variant == "uncertain" else 0.0
    cap = round(earlier + max(bounds) + 0.5 * min(bounds), 6)       # either request fits, both do not
    owner, child = _linked(paths, cap)
    assert child != owner
    ledger = budgets.folder(owner) / "paid.jsonl"
    if variant == "uncertain":
        _uncertain(ledger, earlier)
    if variant == "lost":
        ledger.unlink()
    results = _contend(("discovery", "extraction"), (owner, child), budgets.folder(owner), paths)
    _judge(results, ledger, cap, lost=variant == "lost")


def test_the_control_fails_without_the_owners_lock(paths):
    """The negative control: with the run lock taken away, both processes reserve against accounts each built
    alone, and together they commit beyond the cap. The controls above would fail so."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service = Intake(Catalog(Path(paths["models"])))
    probe = service.start(10.0)
    with _scripted():
        try:
            _attempt("intake", paths, probe.session_id)
        except ValueError:
            pass
    bound = _bound(service.folder(probe.session_id) / "paid.jsonl")
    cap = round(1.5 * bound, 6)
    s = service.start(cap)
    ledger = service.folder(s.session_id) / "paid.jsonl"
    results = _contend(("intake", "intake"), (s.session_id, s.session_id), service.folder(s.session_id), paths,
                       hold=3.0, unlocked=True, paired=True)
    assert all(r[3] for r in results), results                     # both reserved
    assert _peak(ledger) > cap, (results, _peak(ledger), cap)
    with pytest.raises(AssertionError):
        _judge(results, ledger, cap)

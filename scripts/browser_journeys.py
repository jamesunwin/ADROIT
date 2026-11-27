"""The release browser layer's run journeys (the gap plan's G3–G5, with the owner's acceptance criteria of
2026-10-25): an interrupted batch resumed (journey 3), a promotion (journey 2) and linked discovery and extraction
money (journey 5), each in the installed Chrome with the workbench's real child processes
(``scripts/browser_acceptance.py`` runs them; ``scripts/browser_harness.py`` serves and fences them).

Stopping points are reached by barriers, never by timing: the provider fixture holding a request until released
(``scripts/provider_fixture.py``), or the batch's runner frozen (SIGSTOP) once the state wanted is observed, the state
checked again while it is frozen, then killed (SIGKILL). What a journey substitutes is in ``SUBSTITUTED``.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from browser_harness import Workbench, ended, follow, helper, study_path, submit, wait_finished  # noqa: E402

SUBSTITUTED = {
    "journey 3's requests": "the requests join the draft through batch.add_to_draft, the function the wizards' "
                            "\"Add to the batch\" switch calls (no wizard offers a free listing, and no paid wizard has "
                            "the switch); the free ones are adroit portals, which reads no tools, so the journey does "
                            "not depend on this machine's (the auditor's CO recheck, CR-05); the batch is started, resumed "
                            "and read in the browser",
    "journey 3's paid request": "a model intake (an idea in words) answered by the provider fixture on 127.0.0.1, "
                                "held until released, then its connection closed after receipt (its bill unknown)",
}
SUBSTITUTED.update({
    "journey 2's parent": "a real signal study of CDMS II Si (2013) restricted to one candidate (O1 isoscalar at "
                          "10 GeV, 500 toys), written by signal.run in a helper rather than through the Signal best "
                          "fits form; its children are real single-idea studies (adroit promote from the form: 2 "
                          "masses, 100 toys, a 4 × 4 plane, the smallest a child accepts; literature off)",
    "journey 2 without the tables": "a tools folder of links to every tool on this machine but the equation-of-state "
                                    "tables",
    "journey 2's calculation cache": "the checkout's own (data/calculation-cache, with data/external), as a person's "
                                     "later run has it: ADROIT reuses an entry only where its inputs and code identity "
                                     "match; in the release checks the fast suite's real promotion "
                                     "(tests/orchestrator/test_dm14.py) warms it first; a gate run apart from them "
                                     "may start cold, as each promotion's line says",
    "journey 2's stale and legacy records": "copies of a promoted child: legacy, the fields added later removed; "
                                            "stale, its conclusion as an earlier ADROIT decided it before the "
                                            "equation-of-state precondition; their reports re-rendered",
    "journey 2's calculations": "none substituted: each promoted child computes its own signal fits, its 4 × 4 "
                                "Track 1 scan and its search for thermal points, its xenon likelihoods with two "
                                "detector workers",
    "journey 2's DIAMX generations": "warmed first, a stated precondition timed apart (warm_diamx: one reference limit "
                                     "for each xenon search, in the tools folder the promotion reads); the promotion "
                                     "keeps its 1,800 s deadline, and passing it is a failure (the owner's decision on "
                                     "the auditor's DW recheck, 2026-11-12)",
})
DONE = ("completed", "budget_stopped", "failed", "cancelled")

DRAFT_FREE = """
from adroit.core.config import get_settings
from adroit.ui import batch, forms
root = get_settings().runs_dir
for name in ("first", "second"):
    batch.add_to_draft(root, ["portals"], forms.new_folder(root, "portals", name), f"the {name} request")
"""
DRAFT_PAID = """
from adroit.core.config import get_settings
from adroit.orchestrator.model_intake import Intake
from adroit.ui import batch, forms
root = get_settings().runs_dir
batch.add_to_draft(root, ["portals"], forms.new_folder(root, "portals", "first"), "the free request")
service = Intake()
session = service.start(1.0, "claude-opus-5-5")
folder = forms.new_folder(root, "model_intake", session.session_id[:8])
asset = service.catalog.asset_bytes("input.txt", b"a Z2-odd real scalar singlet", "user_edit")
command = ["models", "step", session.session_id, "--kind", "idea", "--candidate", "0", "--out", str(folder),
           "--source", str(service.catalog.asset_path(asset)), "--budget", str(session.budget)]
batch.add_to_draft(root, command, folder, "the paid request", session.budget)
print(session.session_id)
"""


# --- reading the records ------------------------------------------------------------------------------------------

def _json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _batch_folder(bench: Workbench) -> Path:
    found = [p.parent for p in (bench.root / "runs" / "batches").glob("*/batch.json")]
    if len(found) != 1:
        raise AssertionError(f"expected one batch, found {len(found)}")
    return found[0]


def _until(condition, what: str, timeout: float = 300.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = condition()
        if found:
            return found
        time.sleep(0.25)
    raise TimeoutError(f"waited {timeout:.0f} s for {what}")


def _job(folder: str | Path) -> dict:
    return _json(Path(folder) / "job.json", {}) or {}


def _dispatches(bench: Workbench) -> list[str]:
    path = bench.root / "runs" / ".adroit" / "dispatches.jsonl"
    return path.read_text().splitlines() if path.exists() else []


def _starts(bench: Workbench, *words: str) -> list[dict]:
    """The processes started under this workbench whose command line holds every one of ``words`` (the guard's
    process log: each Python child records its own start)."""
    path = bench.root / "process_starts.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [r for r in rows if all(any(w == a or w in a for a in r["argv"]) for w in words)
            and "-c" not in r["argv"][1:2]]


def _kill(pid: int, folder: Path) -> None:
    """Kill the batch's runner (SIGKILL) and wait until its runner lock is free (a killed child of the workbench stays
    a zombie until the workbench reaps it, but holds nothing)."""
    import fcntl
    os.kill(pid, signal.SIGKILL)

    def free() -> bool:
        with (folder / ".runner.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            fcntl.flock(lock, fcntl.LOCK_UN)
            return True
    _until(free, "the killed runner's lock to be released", 30)


def _finished_free(folder: str) -> None:
    """Wait for a batch's free request to end, and require that it completed: one that failed (a missing input, say)
    makes the journey not established at once, with its log's last line, never an interruption race or a wait for a
    completion that cannot come (the auditor's CO recheck, CR-05, 2026-10-26)."""
    from browser_harness import NotEstablished
    status = _until(lambda: _job(folder).get("status") if _job(folder).get("status") in DONE else None,
                    "the free request to finish")
    if status != "completed":
        log = Path(folder) / "log.txt"
        lines = [x for x in (log.read_text(errors="replace") if log.exists() else "").splitlines() if x.strip()]
        raise NotEstablished(f"the batch's free request ended {status} ({lines[-1] if lines else 'no log'}): its "
                             "interruption journey cannot begin")


def _freeze_and_kill(pid: int, folder: Path, still_holds, what: str) -> None:
    """Freeze the runner (SIGSTOP), check ``still_holds()`` while it cannot act, then kill it (SIGKILL): the stopping
    point is the state observed, never a moment guessed."""
    os.kill(pid, signal.SIGSTOP)
    try:
        if not still_holds():
            raise AssertionError(f"the runner moved past the stopping point ({what}) before it was frozen")
    finally:
        _kill(pid, folder)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _resume(page, bench: Workbench, budget: str = "") -> None:
    """The batches page after a restart: the batch interrupted, the damaged sibling named; Resume clicked (the total
    confirmed again where it is paid)."""
    page.goto("about:blank", ready=False)
    bench.restart()
    page.goto(bench.url + "/batches")
    page.wait_text("interrupted")
    page.wait_text("batch record(s) could not be read")
    if budget:
        page.type_into(f"Confirm the total again ($): {budget}", budget)
    page.click_text("Resume")


def _append_only(before: list[str], after: list[str]) -> None:
    assert after[:len(before)] == before, "the runs folder's dispatch ledger was rewritten, not appended to"


def _grew(before: list[str], after: list[str]) -> str:
    return (f"appended to ({len(before)} → {len(after)} records)" if len(after) > len(before)
            else f"unchanged ({len(after)} records)")


def _owners(lines: list[str], item: int) -> list[str]:
    return [json.loads(line)["owner"] for line in lines if json.loads(line)["owner"].split("#")[-2] == str(item)]


# --- journey 3 ------------------------------------------------------------------------------------------------------

def journey_batch_free(browser, root: Path) -> list[str]:
    """Journey 3, free requests, stopping point (a): two free requests started as a batch on the batches page; once
    the first has finished and before the second is dispatched, the runner is frozen, the state checked, and killed;
    beside a damaged batch record; the server restarted: the batch interrupted, the damage named; Resume clicked: a
    real runner completes the second request. The first is never started again, the second once (the process log),
    and the dispatch ledger is only appended to."""
    bench = Workbench(root / "batch_free", warm=("/batches",))
    helper(DRAFT_FREE, bench.env)
    bench.start()
    seen = []
    try:
        page = browser.page()
        page.goto(bench.url + "/batches")
        page.wait_text("the second request")
        page.click_text("Start the batch")
        folder = _until(lambda: _batch_folder(bench) if list((bench.root / "runs" / "batches").glob("*/batch.json"))
                        else None, "the batch to be written")
        batch = _until(lambda: (b := _json(folder / "batch.json")) and b.get("acknowledged") and b, "its runner")
        first, second = (item["folder"] for item in batch["items"])
        _finished_free(first)
        _freeze_and_kill(batch["pid"], folder, lambda: _job(first).get("status") == "completed"
                         and not (Path(second) / "job.json").exists() and len(_dispatches(bench)) == 1,
                         "the second request not dispatched yet")
        seen.append("stopping point (a): the runner killed after the first request finished, before the second "
                    "was dispatched (checked while frozen)")
        before = _dispatches(bench)
        broken = bench.root / "runs" / "batches" / "broken"
        broken.mkdir(parents=True)
        (broken / "batch.json").write_text("{")
        _resume(page, bench)
        _until(lambda: _json(folder / "batch.json", {}).get("status") == "completed", "the resumed batch to complete")
        page.goto(bench.url + "/batches")
        page.wait_text("completed")
        after = _dispatches(bench)
        _append_only(before, after)
        assert len(_owners(after, 0)) == 1 and len(_owners(after, 1)) == 1, after
        runs = {name: len(_starts(bench, "adroit.ui.runner", f)) for name, f in (("first", first), ("second", second))}
        assert runs == {"first": 1, "second": 1}, f"each request started once: {runs}"
        assert len(_starts(bench, "adroit.orchestrator.cli", "portals")) == 2
        seen.append(f"resumed from the page: completed; each request's run started once ({runs}); the dispatch "
                    f"ledger {_grew(before, after)}")
        page.click_text("the second request", "a")
        page.wait(lambda: "/live" in page.url(), "the request's run page")
        page.wait_text("no paid request")
        seen.append("the second request's run page: $0, no paid request")
    finally:
        bench.stop(runs=True)
    return seen


def journey_batch_provider(browser, root: Path) -> list[str]:
    """Journey 3 with a paid request through the provider fixture, stopping points (b) and (c), the bill uncertain:
    a free request and a paid intake started as a batch (its total confirmed on the page); (b) once the free request
    has finished and the intake's request is held at the fixture (its child alive), the runner is killed; the server
    restarted, Resume clicked with the total confirmed again: the new runner follows the live child, never starts
    another; (c) that runner frozen, the held request released and its connection closed after receipt, the child
    ending with its bill unknown, and the runner killed before it records the end; restarted and resumed again: the
    batch completes. The fixture received one request; the intake's child started once; the reservation is shown on
    the run page and the batch's card after both interruptions."""
    from provider_fixture import ProviderFixture
    fixture = ProviderFixture(root / "batch_provider_requests.jsonl").start()
    fixture.plan("hold", "close")
    bench = Workbench(root / "batch_provider", keys={"ANTHROPIC_API_KEY": "sk-ant-simulated-not-a-key",
                                                     "ANTHROPIC_BASE_URL": fixture.url}, warm=("/batches",))
    session = helper(DRAFT_PAID, bench.env).strip().splitlines()[-1]
    bench.start()
    seen = []
    try:
        page = browser.page()
        page.goto(bench.url + "/batches")
        page.wait_text("the paid request")
        page.type_into("Confirm the batch's total budget ($): 1.00", "1")
        page.click_text("Start the batch")
        folder = _until(lambda: _batch_folder(bench) if list((bench.root / "runs" / "batches").glob("*/batch.json"))
                        else None, "the batch to be written")
        batch = _until(lambda: (b := _json(folder / "batch.json")) and b.get("acknowledged") and b, "its runner")
        free, paid = (item["folder"] for item in batch["items"])
        _finished_free(free)
        fixture.wait_for(1)
        child = _job(paid).get("pid")
        assert child and _alive(child), "the intake's run is alive, its request held"
        _kill(batch["pid"], folder)
        seen.append("stopping point (b): the runner killed while the intake's child was alive, its request held at "
                    "the fixture")
        before = _dispatches(bench)
        broken = bench.root / "runs" / "batches" / "broken"
        broken.mkdir(parents=True)
        (broken / "batch.json").write_text("{")
        _resume(page, bench, "1.00")
        resumed = _until(lambda: (b := _json(folder / "batch.json")) and b.get("generation") == 2
                         and b.get("acknowledged") and b, "the resumed runner to acknowledge")
        time.sleep(3)                    # its item loop runs at once; a second launch would show within this
        assert _alive(child) and len(_starts(bench, "adroit.ui.runner", paid)) == 1, "no second intake run"
        assert len(fixture.received) == 1, "no second request"
        assert _dispatches(bench) == before, "the same approval (the same requests and total) dispatches nothing new"
        assert _json(folder / "batch.json")["items"][1]["status"] == "running", \
            "the resumed runner follows the live child: its request stays running, never closed"
        seen.append("resumed from the page: the new runner follows the live child; no second run, no second "
                    "request, no new dispatch (the confirmation is the same)")
        _freeze_and_kill(resumed["pid"], folder, lambda: (fixture.release() or True) and _until(
            lambda: _job(paid).get("status") in DONE, "the intake to end with its bill unknown", 120)
            and _json(folder / "batch.json")["items"][1]["status"] == "running", "the end not yet recorded")
        seen.append("stopping point (c): the held request released, its connection closed after receipt; the runner "
                    "killed after the child ended and before it recorded the end (checked while frozen)")
        _resume(page, bench, "1.00")
        final = _until(lambda: (b := _json(folder / "batch.json")) and b.get("status") in ("completed", "interrupted")
                       and b.get("generation") == 3 and b, "the batch to finish after the second resume")
        assert final["items"][1]["status"] in DONE, final["items"][1]
        after = _dispatches(bench)
        _append_only(before, after)
        assert len(fixture.received) == 1, f"the fixture received {len(fixture.received)} requests"
        assert len(_starts(bench, "adroit.ui.runner", paid)) == 1
        assert len(_starts(bench, "adroit.orchestrator.cli", "models", "step", session)) == 1
        journal = Path(bench.root / "model_library" / "intake" / session / "paid.jsonl")
        events = [json.loads(line)["state"] for line in journal.read_text().splitlines()] if journal.exists() else []
        assert "reserved" in events and "billing_uncertain" in events and "settled" not in events, events
        seen.append(f"after two interruptions: one request received, the intake's child started once, the journal "
                    f"{' → '.join(events)}; the dispatch ledger {_grew(before, after)}")
        page.goto(bench.url + "/batches")
        page.wait_text("reserved")
        page.click_text("the paid request", "a")
        page.wait(lambda: "/live" in page.url(), "the intake's run page")
        page.wait_text("reserved whose bill is not yet known")
        assert "no paid request was sent" not in page.text()
        seen.append("the batch's card and the intake's run page show the reservation, never $0")
    finally:
        bench.stop(runs=True)
        fixture.stop()
    return seen


# --- journey 2 ------------------------------------------------------------------------------------------------------

PRESENT = """
import json
from adroit.external import fetch
from importlib import import_module
items = {"DIAMX": ("adroit.experiments.xenon", "ITEM"), "CDMSlite": ("adroit.experiments.cdmslite", "ITEM"),
         "the solar model": ("adroit.constraints.capture", "SOLAR_MODEL"),
         "the equation-of-state tables": ("adroit.constraints.relic", "EOS_ITEM")}
print(json.dumps({name: fetch.locate(getattr(import_module(m), a)) is not None for name, (m, a) in items.items()}))
"""
PARENT = """
from adroit.core.config import get_settings
from adroit.orchestrator import signal, studies
folder = get_settings().runs_dir / "signal"
request = signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=[], toys=500, leaders=1,
                               candidates=[signal.Candidate(label="O1s@10", card_id="O1", isospin="s", mass_gev=10.0)])
folder.mkdir(parents=True)
(folder / "result.json").write_text(signal.run(request).model_dump_json())
studies.record(folder, "signal", "Signal fits: CDMS II Si, one candidate")
"""
AGED = """
import json, shutil, sys
from pathlib import Path
from adroit.core.config import get_settings
from adroit.orchestrator import single_idea, studies
child, kind, root = Path(sys.argv[1]), sys.argv[2], get_settings().runs_dir
folder = root / f"aged_{kind}"
shutil.copytree(child, folder, ignore=shutil.ignore_patterns("study.json", "children"))
data = json.loads((folder / "result.json").read_text())
if kind == "legacy":            # a result from before the fields added later
    for field in ("thermal_pending", "eos_thermal", "viability", "global_toys", "global_p_interval",
                  "calculation_started_at", "calculation_completed_at", "discovery_coverage"):
        data.pop(field, None)
    title = "a promoted child from before its later fields"
else:                           # decided before the equation-of-state precondition, as an earlier ADROIT wrote it
    data.update(level="no_thermal", thermal_viability="no_thermal", thermal_pending=[],
                summary="no thermal intersection fitting the anomaly was resolved over the searched masses")
    title = "a promoted child decided before the equation-of-state precondition"
(folder / "result.json").write_text(json.dumps(data))
(folder / "report.md").write_text(single_idea.report(single_idea.SingleIdeaResult.model_validate(data)))
studies.record(folder, "single_idea", title)
"""
SHORT = {"viable": "VIABLE", "viable_pending": "VIABLE PENDING", "excluded": "EXCLUDED", "no_fit": "NO FIT",
         "no_thermal": "NO RESOLVED THERMAL EXPLANATION", "undetermined": "UNDETERMINED"}   # the badge's words


def _open_checks(point: dict) -> list[dict]:
    certificate = point.get("certificate") or {}
    return [c for c in certificate.get("checks", []) if c.get("state") in ("failed", "unknown")]


def _fit_state(point: dict) -> str:
    """One stored fit read against the anomaly-fit criterion (significance ≥ 1), from its own stored numbers: a
    physical fit's √q0 recomputed from its log-likelihoods (q0 = 2 (ln L − ln L_null), checked against the stored q0);
    held at its range's edge it counts as below only under 1; unresolved or unidentifiable it decides nothing; without
    a physical fit, the band's local Z. "eligible", "below" or why it is undecided."""
    import math
    fit = point.get("physical_fit")
    if not fit:
        z = point.get("z_local")
        return "no statistic" if z is None or not math.isfinite(z) else "eligible" if z >= 1 else "below"
    if not fit.get("resolved") or not fit.get("identifiable"):
        return "unresolved"
    if fit.get("log_l") is None or fit.get("null_log_l") is None:
        return "no statistic"
    q0 = 2 * (fit["log_l"] - fit["null_log_l"])
    assert fit.get("q0") is None or abs(q0 - fit["q0"]) < 1e-3 * max(1.0, abs(q0)), \
        f"the stored q0 {fit.get('q0')} is not 2 (ln L − ln L_null) = {q0}"
    z = math.sqrt(max(q0, 0.0))
    if fit.get("at_boundary"):
        return "below" if z < 1 else "at the edge of its range"
    return "eligible" if z >= 1 else "below"


def expected_level(data: dict, tables: bool, policy: str) -> tuple[set[str], str]:
    """The journey's own reading of a promoted child's stored supporting evidence (an oracle independent of the
    workbench's readers): the levels that evidence allows, and why. The fit first (``_fit_state``, over the band and
    the certified thermal points): none reaching significance 1, every one decided, is no fit, whatever else; one
    undecided leaves it undetermined. Then the thermal evidence: under the nominal equation-of-state policy the tables
    decide nothing, and each thermal point's band check is the policy's; where the band is assessed, without the tables the band of the
    equation of state is not computed, so the stored pending reasons must name the tables and no thermal conclusion
    (viable, excluded, none resolved) may be decided; with them, a thermal point counts only with a certificate under
    the current ``policy`` and every check satisfied or not applicable."""
    band = [b for b in data.get("band") or [] if isinstance(b, dict)]
    assert band, "a promoted child stores its fit at each mass"
    thermal = [t for t in data.get("thermal") or [] if isinstance(t, dict)]
    states = [_fit_state(b) for b in band + [t for t in thermal if t.get("certificate")
                                              and t["certificate"].get("policy") == policy and not _open_checks(t)]]
    if "eligible" not in states:
        if all(state == "below" for state in states):
            return {"no_fit"}, f"no fit reaches √q0 ≥ 1 at its {len(states)} mass(es), read from the stored likelihoods"
        return {"undetermined"}, f"a fit undecided ({', '.join(sorted(set(states) - {'below'}))})"
    pending = " ".join(data.get("thermal_pending") or [])
    from adroit.core.certificate import EOS_NOT_ASSESSED, eos_band_assessed
    if not eos_band_assessed():         # the nominal policy (the owner, 2026-11-23): the tables decide nothing
        for t in thermal:
            band_check = next((c for c in (t.get("certificate") or {}).get("checks", []) if c["name"] == "eos_band"),
                              None)
            assert band_check is not None and band_check["state"] == "not_applicable" \
                and band_check.get("reason") == EOS_NOT_ASSESSED, f"a thermal point's band check is the policy's: {band_check}"
        tables = True                  # with the tables or without, read as decided on the nominal
    if not tables:
        assert "equation of state's band is not computed" in pending and "adroit setup" in pending, \
            f"without the tables, the stored evidence names them as pending: {pending!r}"
        for t in thermal:
            band_check = next((c for c in (t.get("certificate") or {}).get("checks", []) if c["name"] == "eos_band"),
                              None)
            assert band_check is not None and band_check["state"] == "unknown", \
                f"without the tables a thermal point's band check is open: {band_check}"
        return {"undetermined", "viable_pending"}, "a fit, its thermal claim waiting for the tables"
    assert "equation of state" not in pending, f"with the tables installed nothing waits for them: {pending!r}"
    certified = [t for t in thermal if t.get("certificate") and t["certificate"].get("policy") == policy
                 and not _open_checks(t)]
    if not thermal:
        return {"no_thermal"}, "a fit, and no thermal intersection resolved"
    if any(t.get("status") == "viable" for t in certified):
        return {"viable"}, f"{len(certified)} certified thermal point(s), one viable"
    if certified and all(t.get("status") == "excluded" for t in thermal):
        return {"excluded"}, f"every thermal point certified excluded ({len(certified)})"
    return {"viable_pending", "undetermined"}, f"{len(certified)} of {len(thermal)} thermal points certified"


def judge_child(data: dict, tables: bool, policy: str) -> str:
    """The stored conclusion against the evidence's own reading (``expected_level``); why it is allowed."""
    allowed, why = expected_level(data, tables, policy)
    assert data.get("level") in allowed, (f"the stored conclusion {data.get('level')!r} is not what its evidence "
                                          f"allows ({' or '.join(sorted(allowed))}: {why})")
    return why


def _children(parent: Path) -> list[Path]:
    record = _json(parent / "study.json", {}) or {}
    return [(parent / c).resolve() for c in record.get("children", [])]


def _tools_without_eos(root: Path) -> Path:
    """A tools folder of links to every tool on this machine but the equation-of-state tables."""
    from adroit.core.config import get_settings
    real, out = Path(get_settings().tools_dir), root / "tools_without_eos"
    out.mkdir(parents=True, exist_ok=True)
    for entry in real.iterdir():
        if entry.name != "relic-ss2020":
            (out / entry.name).symlink_to(entry)
    return out


def _cache_line() -> str:
    """What the promotion will compute (the auditor's CO recheck, 2026-10-26: in a fresh checkout it unexpectedly started
    DIAMX's detector workers). The checkout's calculation cache (``data/calculation-cache``) holds the statistical
    calculations by an identity that includes the native libraries' absolute paths, so a copy made in another checkout
    is not reused: cold, the promotion computes its xenon likelihoods afresh, with two worker processes."""
    cache = ROOT / "data" / "calculation-cache"
    counts = {d.name: sum(1 for _ in d.glob("*.json")) for d in sorted(cache.iterdir()) if d.is_dir()} \
        if cache.is_dir() else {}
    if not any(counts.values()):
        return ("calculation cache: cold (none in data/calculation-cache); the promotion computes its xenon "
                "likelihoods afresh with two worker processes")
    return "calculation cache: " + ", ".join(f"{n} {k}" for k, n in counts.items()) + \
        " entries in this checkout (reused only where their identity, absolute paths included, matches)"


WARM = """
import json, time
from adroit.core.dm_state import CrossSectionKind
from adroit.experiments.xenon import SEARCHES, DiamxXenon
times = {}
for search in SEARCHES:
    started = time.monotonic()
    DiamxXenon(search).reference_limits(CrossSectionKind.si, [100.0])
    times[search] = round(time.monotonic() - started)
print(json.dumps(times))
"""


WARM_S = 4 * 3600          # the warm-up's own bound: a cold XENONnT generation makes its cut acceptances (~26 min)


def warm_diamx(bench: Workbench) -> str:
    """DIAMX's generations warmed for the xenon searches, before a promotion: one reference limit (SI, 100 GeV) each,
    in the tools folder the promotion reads, so that its generation (its copy of DIAMX, XENONnT's cut acceptances,
    the background templates) is made before the promotion's clock starts. A stated precondition, timed apart: the
    promotion keeps its deadline of 1,800 s (``wait_promoted``) and passing it is a failure. The auditor's DW recheck had
    found a promotion from an empty work folder past that deadline (the owner's decision, 2026-11-12: warm first, say
    so). Where it is warm already this takes seconds; a calculation that fails here fails the journey."""
    started = time.monotonic()
    done = subprocess.run([sys.executable, "-c", WARM], cwd=ROOT, env=bench.env, timeout=WARM_S, capture_output=True,
                          text=True)
    if done.returncode:
        raise RuntimeError(f"DIAMX's warm-up before the promotion (a stated precondition) failed ({done.returncode}): "
                           f"{done.stderr[-1500:]}")
    times = json.loads(done.stdout.strip().splitlines()[-1])
    return (f"DIAMX warmed first, a stated precondition outside the promotion's 1,800 s ({time.monotonic() - started:.0f}"
            " s: " + ", ".join(f"{search} {seconds} s" for search, seconds in times.items()) + ")")


def _promotion(browser, root: Path, name: str, tables: bool) -> list[str]:
    from adroit.core.certificate import POLICY
    from browser_harness import NotEstablished
    probe = Workbench(root / f"{name}_probe")
    present = json.loads(helper(PRESENT, probe.env).strip().splitlines()[-1])
    needed = [k for k, v in present.items() if not v and (tables or "equation" not in k)]
    if needed:
        raise NotEstablished(f"a real promotion needs {', '.join(needed)} on this machine (adroit setup)")
    bench = Workbench(root / name, tools=None if tables else _tools_without_eos(root), warm=("/studies",),
                      share_cache=True)
    seen = [_cache_line()]
    print(f"  {name}: {seen[0]}", flush=True)
    seen.append(warm_diamx(bench))
    print(f"  {name}: {seen[-1]}", flush=True)
    started = time.monotonic()
    helper(PARENT, bench.env)
    bench.start()
    seen.append(f"the parent: a real signal study written in {time.monotonic() - started:.0f} s")
    try:
        page = browser.page()
        page.goto(bench.url + "/study?path=signal")

        def fill() -> None:
            page.choose("candidate or class", "class 0 (every member)")
            for label, value in SIZE.items():
                page.type_into(label, value)
        began = time.monotonic()
        submit(page, fill, "Promote", lambda: "/live" in page.url(), "the promotion's live page", timeout=120)
        text = wait_promoted(page)
        assert "Promotion complete" in text, text[:1200]
        seen.append(f"Promote clicked ({', '.join(f'{k} {v}' for k, v in SIZE.items())}): adroit promote ran as a "
                    f"child, {time.monotonic() - began:.0f} s")
        page.click_text(PROMOTED)                                               # the primary completion action
        page.wait_text("Studies made from this one")
        assert study_path(page.url()) == "signal", f"the primary action opens the parent study: {page.url()}"
        children = _children(bench.root / "runs" / "signal")
        assert children, "the parent lists its children"
        for child in children:
            data = _json(child / "result.json")
            why = judge_child(data, tables, POLICY)
            level = data["level"]
            # each child reached through the parent's own link, and the parent through the child's (CS-07)
            follow(page, str(child.relative_to(bench.root / "runs")), "the parent's link to its child")
            page.wait_text(SHORT.get(level, level.upper()))
            report = page.text()
            from adroit.core.certificate import eos_band_assessed
            if not eos_band_assessed():   # the nominal policy: nothing waits for the tables, and the policy is said
                assert "band is not computed" not in report, f"nothing waits for the tables: {report[:1500]}"
                if data.get("thermal"):
                    assert "nominal equation of state" in report, f"the page states the policy: {report[:1500]}"
            elif not tables and level != "no_fit":
                assert "adroit setup" in report and "equation" in report, \
                    f"without the tables the page names them: {report[:1500]}"
            follow(page, "signal", "the child's link back to its parent")
            page.wait_text("Studies made from this one")
            seen.append(f"{child.name}: its evidence ({why}) allows {level}; stored {level}; the page shows "
                        f"{SHORT.get(level, level)}" + ("" if tables or level == "no_fit" or not eos_band_assessed()
                                            else ", naming the tables")
                        + "; reached by the parent's link, and the parent by its own")
        vector = next((c for c in children if c.name.startswith("vector")), children[0])
        seen += _aged(page, bench, vector, "legacy" if tables else "stale")
    finally:
        bench.stop(runs=True)
    return seen


SIZE = {"background-only simulations per child study": "100", "each child's Track 1 plane: n × n": "4",
        "masses per candidate": "2"}        # the smallest a child accepts (its plane: at least 4 × 4; the form
#                                             offers 2, which the child refuses: reported to pages.py's owner)


PROMOTED = "Open the signal study and its promoted studies"      # a completed promotion's primary action


def wait_promoted(page) -> str:
    """The promotion's live page once its run has ended and the page says so (``wait_finished``: a real promotion
    takes minutes), and, where it completed, once that frame also offers its primary action (``promoted``): the
    outcome's words and its actions are drawn as two parts, so the action can follow the words by a frame (the auditor's CR
    recheck, CS-06, 2026-10-27). A completed promotion that never offers it fails after a minute."""
    wait_finished(page, 1800)
    return page.wait(lambda: promoted(page), "the completed promotion's primary action beside its outcome", 60)


def promoted(page) -> str:
    """A live page's frame (``ended``) once it has ended and, if completed, offers ``PROMOTED``; "" before."""
    text = ended(page)
    return text if text and ("\ncompleted\n" not in text or PROMOTED.lower() in text.lower()) else ""


def _aged(page, bench: Workbench, child: Path, kind: str) -> list[str]:
    """An aged copy of a child (``AGED``): legacy (from before the fields added later) or stale (decided before the
    equation-of-state precondition): its stored level shown, never re-derived, and its bytes unchanged by viewing."""
    import hashlib
    subprocess_run(AGED, bench, child, kind)
    folder = bench.root / "runs" / f"aged_{kind}"
    before = hashlib.sha256((folder / "result.json").read_bytes()).hexdigest()
    level = _json(folder / "result.json")["level"]
    page.goto(bench.url + "/study?path=" + f"aged_{kind}")
    page.wait_text(SHORT.get(level, level.upper()))
    page.goto(bench.url + "/studies")
    page.wait_text("a promoted child")
    after = hashlib.sha256((folder / "result.json").read_bytes()).hexdigest()
    assert before == after, "viewing never rewrites a stored result"
    return [f"a {kind} copy: its stored {level} shown on its page and in Studies, never re-derived; its bytes "
            "unchanged by viewing"]


def journey_promotion(browser, root: Path) -> list[str]:
    """Journey 2 with the equation-of-state tables as installed: a real signal study → Promote (the form) → `adroit
    promote` as a child process → its children, real single-idea studies, recorded under the parent → each child's
    page judged against its stored evidence (``judge_child``) → stale and legacy copies."""
    return _promotion(browser, root, "promotion", tables=True)


def journey_promotion_no_eos(browser, root: Path) -> list[str]:
    """Journey 2 without the equation-of-state tables: every child's thermal points wait for them, no conclusion is
    decided on them, and the page says so."""
    return _promotion(browser, root, "promotion_no_eos", tables=False)


# --- journey 5 ------------------------------------------------------------------------------------------------------

DISCOVERY_SEED = """
import json, sys
from pathlib import Path
from adroit.core.config import get_settings
from adroit.library.personal import Catalog
from adroit.orchestrator.constraint_discovery import queries, summary
from tests.library.test_personal import save
from tests.orchestrator.test_constraint_discovery import _abstracts, _model
spec = _model(Path(sys.argv[1]))[1]
# every coupling given, as the library saves only a model that can run (the owner, 2026-11-21: the usable gate)
spec = spec.model_copy(update={"couplings": [c.model_copy(update={"value": 0.1}) for c in spec.couplings]})
revision = save(Catalog(), spec)
cache = {q: [a.model_dump(mode="json") for a in _abstracts(q, 5)] for q in queries(summary(spec, revision.reference))}
(get_settings().data_dir / "literature_cache.json").write_text(json.dumps(cache))
print(revision.reference)
"""
LINKED = """
import json, sys
from pathlib import Path
from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator.constraint_discovery import Discovery
from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
(owner,) = [p.parent.name for p in (Discovery().catalog.root / "discovery").glob("*/session.json")]
model = Discovery().session(owner).options.model
source = Path(sys.argv[1])
source.write_text("A synthetic experimental source. Exposure 1 kg day; no events above threshold.")
catalog = ExperimentalCatalog()
revision = catalog.import_files([source], "a local source, in place of the paper discovery would retrieve")
scope = ExperimentalExtraction(catalog).start(revision.reference, 0, model, False, budget_session=owner)
print(json.dumps({"owner": owner, "child": scope.session_id}))
"""
SUBSTITUTED.update({
    "journey 5's survey": "the discovery job runs whole through the workbench (adroit constraints discover): its "
                          "literature from a seeded literature cache, its relevance request answered by the provider "
                          "fixture (the headless tests' DiscoveryReport); its reference checks and retrievals reach "
                          "arXiv and HEPData only through the guard, which refuses them (named gaps)",
    "journey 5's linked extraction": "opened in a helper on a local source, linked to the discovery's budget as "
                                     "discovery's own _open does (the paper it would retrieve is outside this "
                                     "machine); its batch run from the experimental session page, its request "
                                     "answered by the fixture",
})
PROMOTIONS, ACCOUNTING = ("promotion", "promotion_no_eos"), ("accounting", "accounting_uncertain", "accounting_retry",
                                                             "accounting_torn", "accounting_lost")
# The journeys each entry describes (``browser_acceptance.DESCRIBES``; the auditor's CT recheck, CU-05)
DESCRIBES = {"journey 3's requests": ("batch_free", "batch_provider"), "journey 3's paid request": ("batch_provider",),
             "journey 2's parent": PROMOTIONS, "journey 2 without the tables": ("promotion_no_eos",),
             "journey 2's calculation cache": PROMOTIONS, "journey 2's stale and legacy records": PROMOTIONS,
             "journey 2's calculations": PROMOTIONS, "journey 2's DIAMX generations": PROMOTIONS,
             "journey 5's survey": ACCOUNTING,
             "journey 5's linked extraction": ACCOUNTING}
MONEY = __import__("re").compile(r"\$\s?([0-9]+(?:\.[0-9]+)?)")


def _journal_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def reconcile(journal: Path, fixture) -> dict:
    """The money's own reconciliation: the journal's reservations (request ids), the dispatch attempts (one per
    reservation: the budgeted client dispatches once and the SDK may not retry, its retry count 0 on every request),
    the requests the fixture received, the settlements and the reservations left unresolved."""
    rows = _journal_rows(journal)
    reserved = [r["id"] for r in rows if r.get("state") == "reserved"]
    settled = {r["id"]: r["cost_usd"] for r in rows if r.get("state") == "settled"}
    uncertain = {r["id"] for r in rows if r.get("state") in ("billing_uncertain", "recovered")}
    received = list(fixture.received)
    assert len(set(reserved)) == len(reserved), "a request id reserved twice"
    assert len(received) == len(reserved), (f"{len(reserved)} reservations but {len(received)} requests received: "
                                            "a dispatch without a reservation, or a reservation dispatched twice")
    assert all(r.get("retry") in ("", "0") for r in received), "the SDK retried a request invisibly"
    assert set(settled) <= set(reserved) and not set(settled) & uncertain
    unresolved = [k for k in reserved if k not in settled]
    assert set(unresolved) == uncertain & set(reserved), "every unsettled reservation is named uncertain"
    return {"reserved": len(reserved), "received": len(received), "settled": len(settled),
            "settled_usd": round(sum(settled.values()), 6), "unresolved": len(unresolved),
            "schemas": [r["schema"] for r in received]}


def _amounts(text: str) -> list[float]:
    return [float(m) for m in MONEY.findall(text)]


def _own(line: str) -> float | None:
    """A discovery run's own requests, as its cost line gives them beside its session's ("this run's own requests:
    $0.0008"), or None where the line gives none."""
    found = line.partition("this run's own requests:")[2]
    return _amounts(found)[0] if found and _amounts(found) else None


def _line(page, mark_words: str) -> str:
    """The page line holding ``mark_words`` (its money)."""
    return next((line for line in page.text().splitlines() if mark_words in line), "")


def _discover(page, bench: Workbench, reference: str) -> Path:
    """The model's page → Find relevant limits (the cap confirmed) → the discovery job, a real child, to its end;
    its run folder."""
    page.goto(bench.url + "/models/view?" + __import__("urllib.parse").parse.urlencode({"reference": reference}))
    page.wait_text("Find relevant limits for this model")
    page.type_into("the most this discovery may spend in all ($)", "1")
    page.tick("I approve this spend")
    page.click_text("Find relevant limits", "button")
    page.wait(lambda: "/live" in page.url(), "the discovery's live page")
    wait_finished(page)
    folders = sorted((bench.root / "runs").glob("discovery_*"))
    assert len(folders) == 1, folders
    return folders[0]


def _accounting(browser, root: Path, name: str, extraction: str = "answer", after=None) -> list[str]:
    """Journey 5's body: discovery (its survey settled through the fixture) → a linked extraction sharing its budget,
    its batch run from the experimental session page (``extraction``: the fixture's behaviour for its request) →
    every page's money read and reconciled with the journal and the fixture's log; ``after`` then runs a variant on
    the journal."""
    from provider_fixture import ProviderFixture
    fixture = ProviderFixture(root / f"{name}_requests.jsonl").start()
    bench = Workbench(root / name, keys={"ANTHROPIC_API_KEY": "sk-ant-simulated-not-a-key",
                                         "ANTHROPIC_BASE_URL": fixture.url}, warm=("/models",))
    reference = subprocess_run(DISCOVERY_SEED, bench, root / name).strip().splitlines()[-1]
    bench.start()
    seen = []
    try:
        page = browser.page()
        job = _discover(page, bench, reference)
        page.goto(bench.url + "/live?path=" + job.name)
        run_session = _line(page, "This run's session:")
        linked = json.loads(subprocess_run(LINKED, bench, root / name / "source.txt").strip().splitlines()[-1])
        journal = next((bench.root / "experimental_library").rglob(f"{linked['owner']}/paid.jsonl"))
        survey_id = next(r["id"] for r in _journal_rows(journal) if r.get("state") == "reserved")
        survey_cost = {r["id"]: r["cost_usd"] for r in _journal_rows(journal) if r.get("state") == "settled"}[survey_id]
        page.goto(bench.url + "/constraints/discovery?session=" + linked["owner"])
        before_total = _line(page, "Session spending:")
        assert _amounts(run_session)[:1] == _amounts(before_total)[:1] == [round(survey_cost, 4)], \
            (run_session, before_total, survey_cost)
        assert _own(run_session) == round(survey_cost, 4), f"the survey's own cost on its run page: {run_session!r}"
        seen.append(f"discovery: {run_session.strip()} (the survey, settled ${survey_cost:.4f}); the session "
                    f"{before_total.strip()}")
        fixture.plan(extraction)
        page.goto(bench.url + "/experiments/session?session=" + linked["child"])
        page.wait_text("which this session shares")
        page.click_text("Interpret / refine selected batch")
        page.wait(lambda: "/live" in page.url(), "the extraction's live page")
        wait_finished(page)
        extraction_text = page.text()
        facts = reconcile(journal, fixture)
        assert facts["schemas"] == ["DiscoveryReport", "ExtractionAnswer"], facts
        settled = {r["id"]: r["cost_usd"] for r in _journal_rows(journal) if r.get("state") == "settled"}
        assert settled[survey_id] == survey_cost, "the completed survey's own cost is unchanged in its journal"
        page.goto(bench.url + "/constraints/discovery?session=" + linked["owner"])
        after_total = _line(page, "Session spending:")
        page.goto(bench.url + "/live?path=" + job.name)
        run_after = _line(page, "This run's session:")
        assert "the extractions that share its budget included" in page.text(), "the run's figure is the session's"
        assert _own(run_after) == round(survey_cost, 4), \
            f"the completed survey's own cost unchanged on its run page while the session's rises: {run_after!r}"
        page.goto(bench.url + "/experiments/session?session=" + linked["child"])
        shared = _line(page, "which this session shares")
        assert _amounts(after_total)[:1] == _amounts(run_after)[:1] == _amounts(shared.split(":", 1)[1])[:1], \
            (after_total, run_after, shared)
        if extraction == "answer":
            assert facts["unresolved"] == 0 and _amounts(after_total)[0] > _amounts(before_total)[0], \
                "the shared session's total rises by the extraction's settled cost"
            assert abs(_amounts(after_total)[0] - round(facts["settled_usd"], 4)) < 1e-4, (after_total, facts)
        else:
            assert facts["unresolved"] == 1 and "reserved" in after_total and "reserved" in shared, \
                f"the session's total shows the reservation whose bill is unknown ('reserved'): {after_total!r}; " \
                f"{shared!r}"
            assert "reserved whose bill is not yet known" in extraction_text, extraction_text[:1500]
            assert "no paid request was sent" not in extraction_text
        seen.append(f"the linked extraction's run ended; the session now {after_total.strip()}: the same on the "
                    "discovery run's page (labelled the session's, the extractions included) and the experimental "
                    f"session's; the survey's own cost unchanged on its run page (${_own(run_after):.4f}) and in "
                    "the journal")
        seen.append(f"reconciled: {facts}")
        if after is not None:
            seen += after(page, bench, journal, linked, fixture)
    finally:
        bench.stop(runs=True)
        fixture.stop()
    return seen


def subprocess_run(code: str, bench: Workbench, *args) -> str:
    """``code`` in a child with the workbench's environment and ``args``; its output (its error output on failure)."""
    import subprocess as sp
    done = sp.run([sys.executable, "-c", code, *map(str, args)], cwd=ROOT, env=bench.env, timeout=600,
                  capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"a helper failed ({done.returncode}): {done.stderr[-1500:]}")
    return done.stdout


def _torn(page, bench: Workbench, journal: Path, linked: dict, fixture) -> list[str]:
    """A crash mid-write: the journal's last line cut inside a new reservation. Every page says its money is not
    available; ``adroit ledger recover`` (the command line, as the guide says) keeps the original bytes and the
    reservation in full; the pages read again, the reservation shown."""
    import subprocess as sp
    with journal.open("a") as stream:
        stream.write('{"id": "torn0001", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", '
                     '"reserved_usd": 0.05, "invoc')
    for url, words in ((f"/constraints/discovery?session={linked['owner']}", "Session spending:"),
                       (f"/experiments/session?session={linked['child']}", "which this session shares")):
        page.goto(bench.url + url)
        assert "not available" in _line(page, words), (url, _line(page, words))
    out = sp.run([sys.executable, "-m", "adroit.orchestrator.cli", "ledger", "recover", str(journal)], cwd=ROOT,
                 env=bench.env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "reservation kept in full" in out.stdout, out.stdout + out.stderr
    assert list(journal.parent.glob(f"{journal.name}.torn-*")), "the original bytes are kept beside the journal"
    page.goto(bench.url + f"/constraints/discovery?session={linked['owner']}")
    total = _line(page, "Session spending:")
    assert "not available" not in total and "reserved" in total, total
    return ["a torn journal: every page 'not available'; adroit ledger recover kept the original bytes and the "
            f"torn reservation in full; the session reads again: {total.strip()}"]


def _lost(page, bench: Workbench, journal: Path, linked: dict, fixture) -> list[str]:
    """The journal lost whole (the auditor's CO-05; its repair is the accounting branch's: a session that has spent and has
    no journal is refused before anything is reserved): another batch is asked for; nothing reaches the fixture, and
    the run says why."""
    received = len(fixture.received)
    journal.rename(journal.with_name("paid.jsonl.lost-by-the-journey"))
    page.goto(bench.url + "/experiments/session?session=" + linked["child"])
    page.wait_text("which this session shares")
    page.type_into("Refinement / clarification instructions", "the exposure is quoted after cuts")   # a new request
    refusal = "Restore the original ledger file"          # ``MissingJournal``'s words; the budget line shows them too
    shown = page.text().count(refusal)
    page.click_text("Interpret / refine selected batch")
    page.wait(lambda: "/live" in page.url() or page.text().count(refusal) > shown, "the refusal or the run")
    launched = "/live" in page.url()
    if launched:
        wait_finished(page)
    assert len(fixture.received) == received, ("CO-05: with its journal lost, the session sent another request "
                                               "(its approved budget reset)")
    assert shown >= 1, "the session's budget line names the missing ledger before anything is asked"
    assert not launched or refusal in page.text(), "the run's page names the missing ledger"
    return ["a lost journal: the session's budget line names it; the batch asked for was refused on the click, its "
            "notice naming the missing ledger; nothing reached the fixture"]


def journey_accounting(browser, root: Path) -> list[str]:
    """Journey 5: discovery's survey and a linked extraction, both settled; the survey's own cost unchanged, the shared
    total risen, every page the same, the journal reconciled with the fixture's log."""
    return _accounting(browser, root, "accounting")


def journey_accounting_uncertain(browser, root: Path) -> list[str]:
    """Journey 5 with the extraction's connection lost after receipt: its reservation shown on every page and left
    unresolved in the reconciliation; the survey's own cost unchanged."""
    return _accounting(browser, root, "accounting_uncertain", extraction="close")


def journey_accounting_retry(browser, root: Path) -> list[str]:
    """Journey 5 with the provider overloaded (529) on the extraction's request: the SDK does not retry it (one
    request received, its retry count 0), and its reservation stays, uncertain."""
    return _accounting(browser, root, "accounting_retry", extraction="error")


def journey_accounting_torn(browser, root: Path) -> list[str]:
    return _accounting(browser, root, "accounting_torn", after=_torn)


def journey_accounting_lost(browser, root: Path) -> list[str]:
    return _accounting(browser, root, "accounting_lost", after=_lost)


def journey_standard_models(browser, root: Path) -> list[str]:
    """OB-11 (the owner, 2026-11-24): in Explain a signal, in Chrome, every standard model the page offers is chosen in
    turn and the model editor then shows that entry's complete benchmark, value for value; the models the page cannot
    compute are named with why; the Z portal's axial benchmark is submitted, and the real run's saved model is that
    benchmark (m_χ = 500 GeV, g_A = 0.1). The run is stopped once its model is written: its calculation is the smoke
    runs' and the tests' to check, not this journey's."""
    import yaml
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space import library
    offered = [e for e in library.ENTRIES if not e.typed.unsupported and not e.typed.no_recoil]
    label, editor = "a model from the library", "the model (YAML, with coupling values)"
    bench = Workbench(root / "standard_models", warm=("/new/single",))
    bench.start()
    seen = []
    try:
        page = browser.page()
        page.goto(bench.url + "/new/single")
        page.wait_text("Not offered:")
        text = " ".join(page.text().split())
        missing = [e.title for e in library.ENTRIES if (e.typed.unsupported or e.typed.no_recoil)
                   and " ".join(f"{e.title}: {e.typed.unsupported or e.typed.no_recoil}".split()) not in text]
        assert not missing, f"not named under the picker with its reason: {missing}"      # (R9-07: names and reasons)
        seen.append(f"the {len(library.ENTRIES) - len(offered)} standard models the page cannot compute are named "
                    "under the picker, each with why")
        for entry in offered:
            page.choose(label, f"Standard library · {entry.title}")
            page.wait(lambda e=entry: f"name: {e.id}\n" in page.value_of(editor), f"the editor to show {entry.id}")
            shown = ModelSpec.model_validate(yaml.safe_load(page.value_of(editor)))
            assert shown == entry.benchmark_spec(), f"{entry.id}: the editor's model is not its benchmark"
        seen.append(f"each of the {len(offered)} offered standard models, chosen, shows its complete benchmark in "
                    "the editor")
        z = library.entry("z_portal_axial")
        page.choose(label, f"Standard library · {z.title}")
        page.wait(lambda: "name: z_portal_axial\n" in page.value_of(editor), "the editor to show the Z portal")
        page.click_text("Run the study")
        model = _until(lambda: next(iter((bench.root / "runs").glob("*/model.yaml")), None), "the run's model.yaml")
        sent = ModelSpec.model_validate(yaml.safe_load(model.read_text()))
        assert sent == z.benchmark_spec(), "the submitted model is not the Z portal's benchmark"
        assert {c.name: c.value for c in sent.couplings} == {"g_A": 0.1} and sent.dark_matter.mass_gev == 500.0
        assert [t.lorentz for t in sent.terms] == ["axial"]
        seen.append("the Z portal's axial benchmark submitted: the run's model.yaml is it (m_χ = 500 GeV, g_A = 0.1, "
                    "axial), the run then stopped")
    finally:
        bench.stop(runs=True)
    return seen


JOURNEYS = {"batch_free": journey_batch_free, "batch_provider": journey_batch_provider,
            "promotion": journey_promotion, "promotion_no_eos": journey_promotion_no_eos,
            "accounting": journey_accounting, "accounting_uncertain": journey_accounting_uncertain,
            "accounting_retry": journey_accounting_retry, "accounting_torn": journey_accounting_torn,
            "accounting_lost": journey_accounting_lost, "standard_models": journey_standard_models}

"""The release browser layer's own machinery, offline (the auditor's consolidation audit, CO-08 and section E, 2026-10-25):
its network boundary (negative controls: every connection outside this machine refused beneath every client), the
children's environment (no credential, the guard first), Chrome's fence, and how the release checks read the step."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_connection_outside_this_machine_is_refused_by_the_guard_and_loopback_works(tmp_path):
    """The negative controls, as the layer runs them first: each attempt is made only once the guard is confirmed
    installed, at a reserved documentation address (192.0.2.1) or name (.invalid) that reaches no one."""
    gate = _load("browser_acceptance")
    env = gate.child_environment(tmp_path)
    found = json.loads(subprocess.run([sys.executable, "-c", gate.NEGATIVE], cwd=ROOT, env=env, capture_output=True,
                                      text=True, timeout=120, check=True).stdout.strip().splitlines()[-1])
    assert found.pop("guard") == "ADROIT network guard" and found.pop("loopback") == "connected"
    assert found.pop("urllib through the proxy variables") == "refused at the closed local proxy"
    assert set(found.values()) == {"refused by the guard"} and len(found) == 6, found
    logged = [json.loads(line) for line in (tmp_path / "network_refusals.jsonl").read_text().splitlines()]
    assert {r["target"] for r in logged} >= {"192.0.2.1", "example.invalid"}


def test_without_the_guard_nothing_is_attempted(tmp_path):
    gate = _load("browser_acceptance")
    env = {k: v for k, v in gate.child_environment(tmp_path).items() if k != "PYTHONPATH"}
    found = json.loads(subprocess.run([sys.executable, "-c", gate.NEGATIVE], cwd=tmp_path, env=env,
                                      capture_output=True, text=True, timeout=120, check=True).stdout.splitlines()[-1])
    assert not found.pop("guard") and found.pop("loopback") == "connected"
    assert set(found.values()) == {"not attempted: the guard is not installed"}


def test_the_children_get_no_credential_and_the_guard_first(tmp_path, monkeypatch):
    gate = _load("browser_acceptance")
    for name, value in {"ANTHROPIC_API_KEY": "sk-real", "OPENAI_API_KEY": "sk-real", "GITHUB_TOKEN": "t",
                        "AWS_SECRET_ACCESS_KEY": "s", "SOME_PASSWORD": "p", "ADROIT_RUNS_DIR": "/owner/runs",
                        "HTTPS_PROXY": "http://corp:8080", "PYTHONPATH": "/elsewhere"}.items():
        monkeypatch.setenv(name, value)
    env = gate.child_environment(tmp_path, keys={"ANTHROPIC_API_KEY": "sk-ant-simulated-not-a-key"})
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-simulated-not-a-key" and env["OPENAI_API_KEY"] == ""
    assert not {"GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "SOME_PASSWORD", "ADROIT_RUNS_DIR"} & set(env)
    assert env["PYTHONPATH"].split(os.pathsep) == [str(ROOT / "scripts" / "netguard"), "/elsewhere"]
    assert env["HTTPS_PROXY"].startswith("http://127.0.0.1:") and env["NO_PROXY"] == "127.0.0.1,localhost"


def test_chrome_is_fenced_to_this_machine():
    browser = _load("browser")
    flags = browser.Chrome("chrome").fence()
    assert any(f.startswith("--proxy-server=http://127.0.0.1:") for f in flags)
    assert "--proxy-bypass-list=127.0.0.1" in flags
    assert "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1" in flags


def test_a_run_has_ended_only_once_its_outcome_says_so_beside_its_badge():
    """The auditor's CR recheck (2026-10-26): the live page's badge is updated in place and its outcome rebuilt, and Chrome
    drew "completed" a frame before the outcome, still "Promotion: running"; the promotion journey, waiting on the
    badge alone, read the page there and failed. A run has ended for the journeys once both say so, in one frame."""
    harness = _load("browser_harness")

    class Page:
        def __init__(self, frames):
            self.frames = iter(frames)

        def wait(self, ready, what, timeout):
            while True:
                self.badge, self.headline = next(self.frames)
                if found := ready():
                    return found

        def evaluate(self, script):
            assert script == harness.SNAPSHOT
            return [f"Run: promote class:0\n{self.badge}\nelapsed 8 min\n{self.headline}\nThis run: $0",
                    self.headline]

    frames = [("running", "Promotion: running"), ("completed", "Promotion: running"),
              ("completed", "Promotion complete")]
    assert "Promotion complete" in harness.wait_finished(Page(frames))
    for badge, headline in (*frames[:2], ("failed", "Interpretation: failed")):
        page = Page([])
        page.badge, page.headline = badge, headline
        assert bool(harness.ended(page)) is (headline == "Interpretation: failed"), (badge, headline)


def test_the_frame_judged_ended_is_the_frame_returned():
    """The auditor's CR recheck, CS-06 (2026-10-27), its control: the outcome changed between the page's text and its
    headline, read in two calls, and the text returned as final still said "Promotion: running". One evaluation
    returns both; a page whose every later read says complete cannot make an earlier running frame final."""
    harness = _load("browser_harness")
    old = "ADROIT\ncompleted\nPromotion: running\nThis page refreshes every second\n"

    class Advancing:
        """A page whose outcome turns complete after its first read."""
        reads = 0

        def text(self):
            return old

        def evaluate(self, script):
            self.reads += 1
            if script == harness.SNAPSHOT:
                return [old, "Promotion: running"] if self.reads == 1 else \
                    [old.replace(": running", " complete"), "Promotion complete"]
            return "Promotion complete"

    page = Advancing()
    assert harness.ended(page) == "" and page.reads == 1
    assert "Promotion complete" in harness.ended(page)


def test_a_completed_promotion_waits_for_its_primary_action_beside_its_outcome():
    """CS-06: the outcome's words and its actions are two parts of the page; a frame with the words alone is not the
    end of the wait, and a completed promotion that never offers its action fails rather than passing."""
    journeys = _load("browser_journeys")

    def frame(action: bool):
        text = "Run: promote class:0\ncompleted\nPromotion complete\n" + \
            ("OPEN THE SIGNAL STUDY AND ITS PROMOTED STUDIES\n" if action else "") + "This run: $0"
        return type("P", (), {"evaluate": lambda self, s: [text, "Promotion complete"]})()
    assert journeys.promoted(frame(False)) == "" and "PROMOTED" in journeys.promoted(frame(True))
    failed = "Run: promote class:0\nfailed\nPromotion failed\nThis run: $0"
    assert journeys.promoted(type("P", (), {"evaluate": lambda self, s: [failed, "Promotion failed"]})()) == failed


def test_a_journey_follows_only_the_link_to_exactly_the_study_it_names():
    """The auditor's CR recheck, CS-07 (2026-10-27): "a link whose address contains path=signal" held on a child's page
    with every link to the parent removed, its links to itself containing that prefix. The journey follows the page's
    own link to exactly the parent (or child), parsed; removed or misdirected, the journey fails there."""
    harness = _load("browser_harness")
    base = "http://127.0.0.1:1/study?path="
    parent, child, sibling = base + "signal", base + "signal/children/vector", base + "signal/children/scalar"
    assert harness.study_link([child, parent], "signal") == parent
    for links in ([child], [child, sibling], [base + "signal2"], ["http://127.0.0.1:1/live?path=signal"], []):
        assert harness.study_link(links, "signal") == "", links
    assert harness.study_link([parent, child], "signal/children/vector") == child
    assert harness.study_path(child) == "signal/children/vector" and harness.study_path(parent.replace("study", "live")) == ""

    class Page:
        def __init__(self, links):
            self.links, self.at = links, child

        def evaluate(self, script):
            if script == harness.LINKS:
                return self.links
            self.at = next(link for link in self.links if f'"{link}"' in script)      # the click

        def url(self):
            return self.at

        def wait(self, ready, what, timeout=0):
            assert ready(), what

    page = Page([sibling, child, parent])
    harness.follow(page, "signal", "the child's link back to its parent")
    assert page.at == parent
    for links in ([sibling, child], [child, base + "signal/children"]):                  # removed; misdirected
        with pytest.raises(AssertionError, match="the child's link back to its parent"):
            harness.follow(Page(links), "signal", "the child's link back to its parent")


def test_cleanup_stops_only_the_processes_this_workbench_started(tmp_path):
    """The auditor's CR recheck, CS-08 (2026-10-27): an entry of the process log whose command named the journey, beside any
    process alive at its pid, was enough to stop it, so a pid reused by an unrelated process could be stopped. Now the
    process at a logged pid is stopped only where it is the one that logged it: its command line, and a start no
    later than it logged. Simulated reuse: entries pointing at this test's own children."""
    import time
    harness = _load("browser_harness")
    bench = harness.Workbench.__new__(harness.Workbench)
    bench.root = tmp_path
    argv = [sys.executable, "-c", "import time; time.sleep(60)"]
    owned, unrelated, later = (subprocess.Popen(argv) for _ in range(3))
    try:
        time.sleep(1.2)                       # started at least a second before the entries below are logged
        now = time.time()
        entries = [{"pid": owned.pid, "time": now, "argv": argv},                          # its own: stopped
                   {"pid": unrelated.pid, "time": now, "argv": [sys.executable, "-m", "adroit.ui.runner",
                                                                 str(tmp_path / "old_job")]},     # another command
                   {"pid": later.pid, "time": now - 3600, "argv": argv},                     # started after it logged
                   {"pid": later.pid, "argv": argv}]                                         # no start time: unproved
        (tmp_path / "process_starts.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
        left = bench.stop_runs()
        assert owned.wait(timeout=10) == -15
        time.sleep(0.5)
        assert unrelated.poll() is None and later.poll() is None
        assert len(left) == 3 and all("not stopped" in note for note in left)
    finally:
        for child in (owned, unrelated, later):
            if child.poll() is None:
                child.kill()
                child.wait()


def test_the_release_checks_read_the_browser_step_whole_and_never_as_a_pass_without_chrome():
    checks = _load("release_checks")
    line = "8 of 8 browser journeys pass (network, intake, no_key; 2 repetitions, each a fresh Chrome profile)"
    assert checks.summarise("browser_acceptance", f"PASS intake\n{line}\nkept: /tmp/x") == line
    step = next(s for s in checks.steps(Path("/tmp/logs")) if s.name == "browser_acceptance")
    assert checks.verdict(step, checks.BROWSER_NOT_ESTABLISHED, "", "") == checks.NOT_ESTABLISHED
    assert checks.verdict(step, 1, "1 of 2 browser journeys pass", "") == "FAIL"
    assert checks.summarise("acceptance", "x\n2 failed, 3493 passed in 9.0s\n") == "2 failed, 3493 passed in 9.0s"


def _fixture():
    return _load("provider_fixture").ProviderFixture()


def _ask(url: str):
    import anthropic
    client = anthropic.Anthropic(api_key="sk-ant-simulated-not-a-key", base_url=url, max_retries=0, timeout=10)
    schema = json.dumps({"title": "ModelProposals", "type": "object"})
    return client.messages.create(model="claude-opus-5-5", max_tokens=16, messages=[{"role": "user", "content": "x"}],
                                  system="a\n\nRespond with ONLY a single JSON object conforming to this JSON schema, "
                                         f"with no prose and no code fences:\n{schema}")


def test_the_provider_fixture_answers_by_schema_with_known_usage_and_logs_every_request():
    fixture = _fixture().start()
    try:
        reply = _ask(fixture.url)
        assert reply.usage.input_tokens == 100 and reply.usage.output_tokens == 20
        assert json.loads(reply.content[0].text)["proposals"]
        assert fixture.received[0]["schema"] == "ModelProposals" and fixture.received[0]["retry"] == "0"
    finally:
        fixture.stop()


def test_the_provider_fixture_holds_closes_and_errs_as_planned():
    import threading
    import anthropic
    import pytest
    fixture = _fixture().start()
    try:
        fixture.plan("hold", "close", "error")
        outcome = {}
        thread = threading.Thread(target=lambda: outcome.setdefault("error", _raises(lambda: _ask(fixture.url))))
        thread.start()
        fixture.wait_for(1, timeout=10)
        assert thread.is_alive(), "held until released"
        fixture.release()
        thread.join(10)
        assert isinstance(outcome["error"], anthropic.APIConnectionError)       # closed after receipt
        with pytest.raises(anthropic.APIStatusError) as raised:
            _ask(fixture.url)
        assert raised.value.status_code == 529 and len(fixture.received) == 2   # not retried
    finally:
        fixture.stop()


def _raises(call):
    try:
        call()
    except Exception as error:          # noqa: BLE001 - returned for the assertion
        return error
    return None


def test_a_mutation_applies_only_in_the_processes_it_names_and_when_its_module_loads(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts" / "netguard"))
    import acceptance_mutations as m
    workbench = [sys.executable, "-m", "adroit.orchestrator.cli", "workbench", "--port", "1"]
    resumed = [sys.executable, "-m", "adroit.ui.batch", "/b", "sha", "2"]
    first = [sys.executable, "-m", "adroit.ui.batch", "/b", "sha", "1"]
    assert m._workbench(workbench) and not m._workbench(resumed)
    assert m._resumed_runner(resumed) and not m._resumed_runner(first)
    (tmp_path / "mutated_target.py").write_text("def kind_of(job):\n    return 'run'\n")
    sys.path.insert(0, str(tmp_path))
    hook = m._Hook("mutated_target", m._intake_read_as_study)
    sys.meta_path.insert(0, hook)
    try:
        import mutated_target
        assert mutated_target.kind_of(None) == "study"
    finally:
        sys.meta_path.remove(hook)
        sys.modules.pop("mutated_target", None)


# a session with one request settled, then a reservation left open after it ("uncertain") or its ledger lost ("lost"),
# in a fresh process with the mutation's hook installed first, as the workbench's children have it: the session's
# status, then, with its ledger lost, whether a client built from its account sends a request
_SESSION = """
import json, sys
from pathlib import Path
scenario, name, tmp = sys.argv[1], sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, sys.argv[4])
import acceptance_mutations as m
if name:
    module, _, patch = m.MUTATIONS[name]
    sys.meta_path.insert(0, m._Hook(module, patch))
from adroit.agents.budget import journal_whole, ledger_held
from adroit.core.durable import append_held
from tests.orchestrator.test_do_fixes import _client, _session, ask
service, session, llm, _ = _session(tmp)
ask(llm)
ledger = service.folder(session) / "paid.jsonl"
if scenario == "uncertain":
    first = json.loads(ledger.read_bytes().splitlines()[0])
    append_held(ledger, json.dumps({**first, "id": "open"}).encode() + b"\\n", ledger_held(ledger),
                whole=journal_whole)
else:
    ledger.rename(ledger.with_name("paid.jsonl.lost"))
found = {}
try:
    found["status"] = service.budget_status(session)
    if scenario == "lost":
        again, sent = _client(ledger, account=service.account(service.session(session)))
        ask(again)
        found["sent"] = len(sent)
except Exception as error:
    found["error"] = f"{type(error).__name__}: {error}"
print(json.dumps(found))
"""


def _mutated_session(scenario: str, name: str, tmp: Path, netguard: Path = ROOT / "scripts" / "netguard") -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
    env["ADROIT_RUNS_DIR"] = str(tmp / "runs")
    out = subprocess.run([sys.executable, "-c", _SESSION, scenario, name, str(tmp), str(netguard)], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_each_money_mutation_restores_its_defect_where_a_session_is_read(tmp_path):
    """The release layer's money controls restore their defects where the session's pages read its money, not only in
    readings they no longer use (the auditor's DN recheck, DO-01, 2026-11-08: a session's account is read through
    ``read_held``, and a lost ledger is named by the mark beside it too, so the browser controls for an unknown bill
    read as settled and for a lost journal read as empty no longer restored either, and their journeys passed or
    failed elsewhere). Without the mutation, the reservation is uncertain and the lost ledger refused; with it, the
    reservation reads as settled at $0, and the lost ledger as an empty one, the whole cap left and a request sent."""
    plain = _mutated_session("uncertain", "", tmp_path / "plain")
    assert plain["status"]["reserved_uncertain"] > 0, plain
    settled = _mutated_session("uncertain", "reservation_read_as_settled", tmp_path / "settled")
    assert settled["status"]["reserved_uncertain"] == 0, settled
    refused = _mutated_session("lost", "", tmp_path / "refused")
    assert "Restore the original ledger file" in refused["error"], refused
    lost = _mutated_session("lost", "lost_journal_read_as_empty", tmp_path / "lost")
    assert lost.get("status", {}).get("remaining") == lost.get("status", {}).get("cap") == 0.05, lost
    assert lost["sent"] == 1, lost


def test_the_oracle_under_the_nominal_eos_policy_reads_the_policys_band_check():
    """Under 1.0.0's nominal equation-of-state policy the tables decide nothing: a certified thermal point whose band
    check is the policy's is read as decided, with or without the tables; one without that check is refused."""
    import pytest
    from adroit.core.certificate import EOS_NOT_ASSESSED
    journeys = _load("browser_journeys")
    fits = [{"z_local": 0.4}, {"z_local": 2.1}]
    nominal = {"name": "eos_band", "state": "not_applicable", "reason": EOS_NOT_ASSESSED}
    certified = {"status": "viable", "certificate": {"policy": "p", "checks": [
        {"name": "root", "state": "satisfied"}, nominal]}}
    for tables in (True, False):
        assert "one viable" in journeys.judge_child({"level": "viable", "band": fits, "thermal": [certified]}, tables,
                                                    "p")
    unchecked = {**certified, "certificate": {**certified["certificate"], "checks": [{"name": "root",
                                                                                         "state": "satisfied"}]}}
    with pytest.raises(AssertionError, match="band check is the policy's"):
        journeys.judge_child({"level": "viable", "band": fits, "thermal": [unchecked]}, False, "p")


@pytest.mark.eos_band
def test_the_journeys_own_reading_of_a_childs_evidence():
    """The promotion journey's oracle reads the stored evidence itself: the fit, then the thermal evidence, then
    whether the stored conclusion is one that evidence allows (the band assessed: its deferred reading)."""
    import pytest
    journeys = _load("browser_journeys")
    policy, setup = "p", "the equation of state's band is not computed: run `adroit setup --fetch --only 'x'`"
    fits, no_fit = [{"z_local": 0.4}, {"z_local": 2.1}], [{"z_local": 0.4}, {"z_local": 0.9}]
    edge = {"z_local": 1.28, "physical_fit": {"resolved": True, "identifiable": True, "at_boundary": True,
                                              "log_l": -10.5132, "null_log_l": -10.5181, "q0": 0.0098}}
    assert journeys._fit_state(edge) == "below"              # the physical fit's √q0, not the NR local Z, decides
    with pytest.raises(AssertionError, match="stored q0"):
        journeys._fit_state({**edge, "physical_fit": {**edge["physical_fit"], "q0": 4.0}})
    certified = {"status": "viable", "certificate": {"policy": policy, "checks": [{"name": "root", "state": "satisfied"}]}}
    assert journeys.judge_child({"level": "no_fit", "band": no_fit}, True, policy).startswith("no fit reaches")
    journeys.judge_child({"level": "no_thermal", "band": fits, "thermal": []}, True, policy)
    journeys.judge_child({"level": "viable", "band": fits, "thermal": [certified]}, True, policy)
    journeys.judge_child({"level": "undetermined", "band": fits, "thermal_pending": [setup]}, False, policy)
    with pytest.raises(AssertionError, match="not what its evidence allows"):       # decided without the tables
        journeys.judge_child({"level": "no_thermal", "band": fits, "thermal_pending": [setup]}, False, policy)
    with pytest.raises(AssertionError, match="without the tables, the stored evidence names them"):
        journeys.judge_child({"level": "no_thermal", "band": fits, "thermal_pending": []}, False, policy)
    stale = {**certified, "certificate": {**certified["certificate"], "policy": "older"}}
    with pytest.raises(AssertionError, match="not what its evidence allows"):
        journeys.judge_child({"level": "viable", "band": fits, "thermal": [stale]}, True, policy)


def test_the_money_is_reconciled_with_the_journal_and_the_providers_log(tmp_path):
    import pytest
    from types import SimpleNamespace
    journeys = _load("browser_journeys")
    journal = tmp_path / "paid.jsonl"
    rows = [{"id": "a", "state": "reserved"}, {"id": "a", "state": "received"}, {"id": "a", "state": "settled",
            "cost_usd": 0.0008}, {"id": "b", "state": "reserved"}, {"id": "b", "state": "billing_uncertain"}]
    journal.write_text("".join(json.dumps(r) + "\n" for r in rows))
    log = [{"schema": "DiscoveryReport", "retry": "0"}, {"schema": "ExtractionAnswer", "retry": "0"}]
    facts = journeys.reconcile(journal, SimpleNamespace(received=log))
    assert facts["reserved"] == facts["received"] == 2 and facts["settled"] == 1 and facts["unresolved"] == 1
    with pytest.raises(AssertionError, match="reservations but"):
        journeys.reconcile(journal, SimpleNamespace(received=log[:1]))
    with pytest.raises(AssertionError, match="retried"):
        journeys.reconcile(journal, SimpleNamespace(received=[log[0], {**log[1], "retry": "1"}]))


def test_the_substitutions_printed_are_those_of_the_journeys_run():
    """The auditor's CT recheck, CU-05 (2026-10-28): the receipt's inventory said "no scan runs in the browser layer" beside
    the promotions' real scans. Each entry names the journeys it describes, and only the chosen journeys' are printed:
    the promotions' say their children compute their own scans; the history's toy calculation is its own."""
    gate = _load("browser_acceptance")
    assert set(gate.SUBSTITUTED) == set(gate.DESCRIBES)
    assert all(set(journeys) <= set(gate.JOURNEYS) for journeys in gate.DESCRIBES.values())
    every = gate.substituted(list(gate.JOURNEYS))
    assert every == gate.SUBSTITUTED and not any("in the browser layer" in w for w in every.values())
    promotion = gate.substituted(["promotion"])
    assert "history's studies" not in promotion and "4 × 4 Track 1 scan" in promotion["journey 2's calculations"]
    history = gate.substituted(["history"])
    assert list(history) == ["history's studies"] and "no scan runs for them" in history["history's studies"]


def test_the_history_journey_heads_the_point_table_as_the_column_contract_does():
    """The browser's copy of the point table's headers is the version matrix's contract (``tests/version_matrix.
    COLUMNS``), the halo column among them: on the merged branch the copy had lacked it, and only the gate found it."""
    from tests.version_matrix import COLUMNS
    assert _load("browser_acceptance").POINT_HEADS == [c["label"] for c in COLUMNS]


def test_a_promotion_warms_diamx_first_and_keeps_its_deadline(monkeypatch):
    """DIAMX's generations are warmed before a promotion, a stated precondition timed apart (the owner's decision on
    the auditor's DW recheck, 2026-11-12): its line names each search's time; a failing warm-up fails the journey in its own
    words; the promotion's wait keeps its 1,800 s, and the warm-up comes before the parent study and the Promote."""
    import inspect
    from types import SimpleNamespace
    journeys = _load("browser_journeys")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"LZ WS2022+WS2024": 3, "XENONnT SR0+SR1": 1600}\n', stderr="")
    monkeypatch.setattr(journeys.subprocess, "run", run)
    line = journeys.warm_diamx(SimpleNamespace(env={"X": "1"}))
    assert "a stated precondition outside the promotion's 1,800 s" in line
    assert "LZ WS2022+WS2024 3 s" in line and "XENONnT SR0+SR1 1600 s" in line
    assert calls[0][0][1:] == ["-c", journeys.WARM] and calls[0][1]["env"] == {"X": "1"}
    assert calls[0][1]["timeout"] == journeys.WARM_S
    monkeypatch.setattr(journeys.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="",
                                                                                    stderr="DIAMX failed"))
    with pytest.raises(RuntimeError, match="warm-up before the promotion .*DIAMX failed"):
        journeys.warm_diamx(SimpleNamespace(env={}))
    assert "wait_finished(page, 1800)" in inspect.getsource(journeys.wait_promoted)
    source = inspect.getsource(journeys._promotion)
    assert source.index("warm_diamx(bench)") < source.index("helper(PARENT, bench.env)") < source.index('"Promote"')

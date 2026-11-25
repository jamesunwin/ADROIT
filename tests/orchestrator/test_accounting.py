"""The one interpretation of money (the consolidation plan's M2, ``orchestrator.accounting``): no workbench import, the
command line's figures, the budget-stop record, D-6's total. Every record is written directly; no provider, $0."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from adroit.orchestrator import accounting
from adroit.orchestrator.accounting import Cost, JobFacts, RequestFact

IDEA = ["idea", "--text", "x", "--budget", "1", "--out", "."]
RESERVED = {"id": "r", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.4}


def test_accounting_imports_no_workbench_module():
    """The command line reads money as the pages do: the module imports nothing of ``adroit.ui``."""
    code = ("import sys, adroit.orchestrator.accounting; "
            "print(sorted(m for m in sys.modules if m.startswith('adroit.ui')))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]"


def test_a_run_is_plain_data_and_the_budget_is_read_as_the_command_line_reads_it(tmp_path):
    from adroit.ui import engine
    assert engine.paid(IDEA) == accounting.budget_of(IDEA) == 1.0
    with pytest.raises(ValueError, match="more than once"):
        accounting.budget_of(["idea", "--budget", "1", "--budget=2"])
    (tmp_path / "paid.jsonl").write_text("")
    c = accounting.cost(tmp_path, JobFacts(command=IDEA, status="completed"))
    assert accounting.run_line(c) == "This run: $0 (no paid request was sent)"
    assert c.none_sent_evidence and c.sent_none and c.settled_precision == "journal"


def test_a_free_command_is_free_because_its_command_has_no_budget(tmp_path):
    c = accounting.cost(tmp_path, JobFacts(command=["track1", "m.yaml"]))
    assert c.run_usd == 0.0 and not c.paid and c.none_sent_evidence == "its command has no --budget"


def _ledger(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_a_provider_caps_stop_records_the_whole_commands_commitment(tmp_path):
    """M2: a provider's own cap stops with that provider's commitment; the stop record had kept it alone, unsplit,
    so the run read "up to" the provider's dollars and the other provider's were lost. It now keeps the whole
    command's, split, and the stopping cap's apart."""
    from adroit.agents.budget import BudgetExceeded
    from adroit.orchestrator.cli import _committed_parts
    ledger = tmp_path / "paid.jsonl"
    _ledger(ledger, [{**RESERVED, "id": "a", "reserved_usd": 0.1}, {"id": "a", "state": "settled", "cost_usd": 0.03},
                     {**RESERVED, "id": "b", "provider": "openai", "reserved_usd": 0.2},
                     {"id": "b", "state": "billing_uncertain", "error": "TimeoutError"}])
    provider = BudgetExceeded(0.03, 0.05, 0.04)        # the anthropic cap: its own $0.03 committed
    provider.ledger_path = str(ledger)
    parts = _committed_parts(provider)
    assert parts == {"settled_usd": pytest.approx(0.03), "uncertain_usd": pytest.approx(0.2),
                     "committed_usd": pytest.approx(0.23), "cap_committed_usd": pytest.approx(0.03)}
    whole = BudgetExceeded(0.23, 0.25, 0.1)            # the command's cap: its whole commitment
    whole.ledger_path = str(ledger)
    assert _committed_parts(whole) == {"settled_usd": pytest.approx(0.03), "uncertain_usd": pytest.approx(0.2)}
    short = BudgetExceeded(0.5, 1.0, 0.1)              # a ledger missing committed dollars: nothing split
    short.ledger_path = str(ledger)
    assert _committed_parts(short) == {}
    stop = {"status": "budget_stopped", "committed_usd": 0.03, **parts}
    (tmp_path / "result.json").write_text(json.dumps(stop))
    ledger.unlink()
    c = accounting.cost(tmp_path, JobFacts(command=IDEA, status="budget_stopped"))
    assert (c.run_usd, c.run_uncertain_usd) == (pytest.approx(0.03), pytest.approx(0.2))


def test_an_unreadable_request_record_is_damage_never_a_run_from_before_it(tmp_path, monkeypatch):
    """M2: an unreadable ``paid_requests.json`` read as a run from before the record, its cost then taken from the
    session totals its log printed. It is now not available, and why."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import REQUESTS, Intake
    service = Intake(Catalog(tmp_path / "models"))
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    session = service.start(budget=1).session_id
    _ledger(service.folder(session) / "paid.jsonl", [{**RESERVED, "id": "a", "reserved_usd": 0.1},
                                                     {"id": "a", "state": "settled", "cost_usd": 0.05}])
    run = tmp_path / "run"
    run.mkdir()
    line = "paid request: claude-opus-5-5; reserving up to $0.1 before dispatch; committed $0.0000 of the $1.00 hard cap"
    (run / accounting.LOG).write_text(line + "\n" + json.dumps({"cap": 1.0, "spent": 0.05, "reserved_uncertain": 0,
                                                                "remaining": 0.95}) + "\n")
    job = JobFacts(command=["models", "step", session, "--kind", "idea", "--budget", "1"])
    assert accounting.cost(run, job).run_usd == pytest.approx(0.05)          # no record: the log's totals
    (run / REQUESTS).write_text("{ damaged")
    c = accounting.cost(run, job)
    assert c.run_usd is None and c.damaged and "cannot be read" in accounting.run_line(c)
    assert accounting.cost_lines(c)[1].startswith("Session total so far: $0.0500 spent")


def test_a_discovery_resume_is_a_discovery_charged_with_its_session(tmp_path, monkeypatch):
    """``constraints resume`` is a known kind (it had read as a study, "no paid request was sent"); like the survey
    that opened it, it is charged with its whole session, and says so."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service = Intake(Catalog(tmp_path / "experimental"))
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    session = service.start(1.0, "claude-opus-5-5").session_id
    _ledger(service.folder(session) / "paid.jsonl", [{**RESERVED, "id": "a", "reserved_usd": 0.1},
                                                     {"id": "a", "state": "settled", "cost_usd": 0.07}])
    job = JobFacts(command=["constraints", "resume", session, "--budget", "1", "--out", "x"])
    assert accounting.kind_of(job) == "discovery"
    c = accounting.cost(tmp_path / "resume", job)
    assert c.scope == "session" and c.run_usd == pytest.approx(0.07) and "resumed" in c.run_source
    assert accounting.run_line(c).startswith("This run's session: $0.0700")
    assert accounting.short_line(c) == "$0.0700 (its whole session)"



def test_a_discovery_run_shows_its_own_requests_beside_its_sessions(tmp_path, monkeypatch):
    """The gap plan's G5 (H9): a discovery run is charged with its whole session, which rises when a linked extraction
    spends from the shared budget; beside it, the survey's own requests (its request record) keep their cost. A run
    from before the record shows the session's figure alone. A request record and a discovery.json naming different
    sessions, neither bound to the run (an attempt, a resume's command), are both named, and neither's figure is used
    (the auditor's DK recheck, DL-04: the discovery.json's had been used)."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import REQUESTS, Intake, RunRequests
    service = Intake(Catalog(tmp_path / "experimental"))
    monkeypatch.setattr(accounting, "_budgets", lambda library: service)
    session = service.start(1.0, "claude-opus-5-5").session_id
    ledger = service.folder(session) / "paid.jsonl"
    survey = [{**RESERVED, "id": "a", "reserved_usd": 0.1}, {"id": "a", "state": "settled", "cost_usd": 0.0008}]
    _ledger(ledger, survey)
    run = tmp_path / "survey"
    run.mkdir()
    (run / "discovery.json").write_text(json.dumps({"session": session}))
    job = JobFacts(command=["constraints", "discover", "catalog:m@r", "--budget", "1", "--out", "x"])
    assert accounting.cost(run, job).own_usd is None                       # from before the record
    assert accounting.short_line(accounting.cost(run, job)) == "$0.0008 (its whole session)"
    (run / REQUESTS).write_text(RunRequests(session_id=session, request_ids=["a"]).model_dump_json())
    before = accounting.cost(run, job)
    assert (before.run_usd, before.own_usd) == (pytest.approx(0.0008), pytest.approx(0.0008))
    _ledger(ledger, [*survey, {**RESERVED, "id": "b", "reserved_usd": 0.1},
                     {"id": "b", "state": "settled", "cost_usd": 0.0008}])  # the linked extraction spends
    after = accounting.cost(run, job)
    assert (after.run_usd, after.own_usd) == (pytest.approx(0.0016), pytest.approx(0.0008))
    assert accounting.run_line(after).startswith("This run's session: $0.0016; this run's own requests: $0.0008")
    assert accounting.short_line(after) == "$0.0016 (its whole session; this run's own $0.0008)"
    _ledger(ledger, [*survey, {**RESERVED, "id": "c", "reserved_usd": 0.4},
                     {"id": "c", "state": "billing_uncertain", "error": "TimeoutError"}])
    (run / REQUESTS).write_text(RunRequests(session_id=session, request_ids=["a", "c"]).model_dump_json())
    uncertain = accounting.cost(run, job)
    assert "this run's own requests: $0.0008 settled, and up to $0.4000 reserved whose bill is not yet known" \
        in accounting.run_line(uncertain)
    (run / REQUESTS).write_text(RunRequests(session_id="another", request_ids=["a"]).model_dump_json())
    other = accounting.cost(run, job)
    assert other.own_usd is None and other.run_usd is None and other.session_spent_usd is None
    assert "names session another… and its discovery.json" in accounting.run_line(other)
    assert accounting.cost_lines(other)[1] == "Session total: not available"

def _session_cost(session: str, ids: dict[str, tuple[str, float]], scope: str = "run") -> Cost:
    facts = {f"session:{session}#{k}": RequestFact(state=s, settled_usd=v if s == "settled" else 0.0,
                                                   reserved_usd=v if s != "settled" else 0.0)
             for k, (s, v) in ids.items()}
    return Cost(run_usd=sum(f.settled_usd for f in facts.values()), paid=True, scope=scope, session_id=session,
                run_uncertain_usd=sum(f.reserved_usd for f in facts.values()), requests=facts)


def test_d6_the_total_counts_each_identifiable_request_once_and_older_records_apart():
    """D-6: a discovery charged with its whole session and the extraction that shares its budget name the same
    requests; the total counts them once. A study record naming no request is counted apart, its overlap unknown;
    a run whose accounting cannot be read is counted, never summed as $0."""
    survey = _session_cost("s", {"a": ("settled", 0.03), "b": ("settled", 0.0008), "c": ("uncertain", 0.04)},
                           scope="session")
    extraction = _session_cost("s", {"b": ("settled", 0.0008), "c": ("uncertain", 0.04)})
    legacy = Cost(run_usd=0.0024, settled_only=True, paid=True)
    cents = Cost(run_usd=0.12, run_approximate=True, paid=True)
    stopped = Cost(run_committed_usd=0.31, paid=True)
    lost = Cost(paid=True, damaged=["the run's paid ledger could not be read"])
    free = Cost(run_usd=0.0)
    t = accounting.total([survey, extraction, legacy, cents, stopped, lost, free])
    assert (t.settled_usd, t.reserved_usd, t.requests) == (pytest.approx(0.0308), pytest.approx(0.04), 3)
    assert (t.legacy_settled_usd, t.approximate_usd, t.committed_usd) == (0.0024, 0.12, 0.31)
    assert (t.unavailable, t.incomplete) == (1, 0)          # a damaged run counted once, as unavailable
    text = accounting.total_text(t)
    for words in ("$0.0308 settled over 3 identifiable request(s), each counted once", "up to $0.0400 reserved",
                  "$0.0024 more settled in older records", "about $0.1200 more", "up to $0.3100 committed",
                  "1 run(s) whose accounting is not available"):
        assert words in text, text
    assert "$0.0316" not in text                        # the shared requests are not counted twice


def test_what_is_left_of_a_cap_is_the_accounts_never_the_cap_less_the_settled_dollars():
    assert accounting.status_text({"cap": 1.0, "spent": 0.0008, "reserved_uncertain": 0.040952,
                                   "remaining": 0.958248}) == (
        "$0.0008 spent of its approved $1.00 cap ($0.9582 left); $0.0410 reserved whose bill is not yet known")
    assert accounting.session_text(0, 0, 0) == "$0 (no paid budget: typed and field-content steps only)"


def test_a_commands_closing_line_is_its_accounts_settled_and_reserved_dollars():
    """``preflight.spent_text`` reads the account through ``accounting.account_text``, in the line the workbench
    reads back (``SPENT_LINE``, ``RESERVED``)."""
    from types import SimpleNamespace
    from adroit.agents.budget import BudgetAccount
    from adroit.orchestrator.preflight import spent_text
    account = BudgetAccount(1.0)
    account.spent = {"anthropic": 0.0024}
    account.reservations = {"x": ("anthropic", 0.4)}
    line = spent_text(SimpleNamespace(account=account, spent=0.0024))
    assert line == "spent $0.0024 settled, and up to $0.4000 reserved for requests whose bill is not known"
    value, rest = accounting.SPENT_LINE.findall(line)[-1]
    assert value == "0.0024" and accounting.RESERVED.search(rest).group(1) == "0.4000"

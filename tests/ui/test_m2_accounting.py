"""One interpretation of money on every surface (the consolidation plan's M2): a matrix of run folders, each as the
workbench leaves it, read on the run page, the study card, the Studies list, ``adroit studies`` (each line and the
total) and the batch page; each shows the same facts in the same words, and every reservation or committed bound a
record holds survives on every surface. What survives is asserted, not an order of precedence. Records are written
directly; no provider, request or calculation, $0.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.orchestrator import accounting, studies
from adroit.ui import batch, engine

IDEA = ["idea", "--text", "x", "--budget", "1", "--out", "."]
RES = {"id": "r", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.4}
SETTLE = {"id": "r", "state": "settled", "cost_usd": 0.0008, "bound_exceeded": False}
STOP = {"status": "budget_stopped", "committed_usd": 0.4024}

MATRIX = {
    # name: (records, the dollars that must survive on every surface)
    "an empty ledger": ({"ledger": []}, []),
    "no record at all": ({}, []),
    "a damaged ledger": ({"ledger": "{ not json\n"}, []),
    "a transport failure": ({"ledger": [RES, {"id": "r", "state": "billing_uncertain", "error": "TimeoutError"}]},
                            [0.4]),
    "a tiny charge": ({"ledger": [RES, {"id": "r", "state": "received", "response": {}}, SETTLE]}, [0.0008]),
    "a split budget stop": ({"stop": {**STOP, "settled_usd": 0.0024, "uncertain_usd": 0.4}}, [0.0024, 0.4]),
    "an unsplit budget stop": ({"stop": STOP}, [0.4024]),
    "a line to the cent with a reservation": ({"log": "spent $0.12; up to $0.4000 reserved whose bill is not yet known\n"},
                                              [0.12, 0.4]),
    "several lines, the last precise": ({"log": "spent $0.10\nspent $0.0024 settled, and up to $0.4000 reserved for "
                                                "requests whose bill is not known\n"}, [0.0024, 0.4]),
    "a study record against an unsplit stop": ({"stop": STOP, "study": 0.0024}, [0.0024, 0.4024]),
    "an invalid split": ({"stop": {**STOP, "settled_usd": 0.0024, "uncertain_usd": float("nan")},
                          "log": "spent $0.0024\n"}, [0.0024, 0.4024]),
    "a terminal state out of order": ({"ledger": [RES, SETTLE, {"id": "r", "state": "billing_uncertain"}]}, []),
}


def _run(folder: Path, records: dict) -> engine.Job:
    """A finished paid workbench run (``adroit idea --budget 1``) with its study record and the records given."""
    folder.mkdir(parents=True)
    job = engine.Job(title=folder.name, kind="idea", command=IDEA, folder=str(folder), status="failed", returncode=2)
    engine.save(job)
    if "log" in records:
        (folder / engine.LOG).write_text(records["log"])
    if "stop" in records:
        (folder / "result.json").write_text(json.dumps(records["stop"]))
    if "ledger" in records:
        ledger = records["ledger"]
        (folder / "paid.jsonl").write_text(ledger if isinstance(ledger, str) else
                                           "".join(json.dumps(r) + "\n" for r in ledger))
    studies.record(folder, "idea", folder.name, cost_usd=records.get("study", 0.0))
    return job


def _slug(name: str) -> str:
    return name.replace(" ", "_").replace(",", "")


@pytest.fixture
def matrix(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    for name, (records, _) in MATRIX.items():
        _run(root / _slug(name), records)
    return root


def test_every_surface_reads_one_set_of_facts_and_keeps_every_bound(matrix):
    """The run page's lines, the card, the Studies list's line and ``adroit studies``' line come from one ``Cost``;
    each reservation or committed bound a run's records hold appears on all of them."""
    from adroit.orchestrator.cli import app
    from adroit.ui import pages
    from adroit.orchestrator.study_headline import held
    shown = CliRunner().invoke(app, ["studies", str(matrix)])
    assert shown.exit_code == 0, shown.output
    for name, (_, survive) in MATRIX.items():
        folder = matrix / _slug(name)
        c = accounting.cost(folder, engine.load(folder))
        s = studies.load(folder)
        detail, short = accounting.run_line(c), accounting.short_line(c)
        assert pages.study_cost(held(folder)) == "cost: " + detail.removeprefix("This run: ")
        assert pages.list_cost(held(folder)) == short
        line = next(x for x in shown.output.splitlines() if x.endswith(str(folder)))
        assert (f", {short})" in line) if short else line.endswith(f"{s.created}): {folder}"), (name, line)
        for dollars in survive:
            for surface in (detail, short, line):
                assert accounting.usd(dollars) in surface, (name, surface)
        assert "no paid request was sent" not in detail or name == "an empty ledger", (name, detail)


def test_damage_and_unknown_money_are_said_on_every_surface(matrix):
    from adroit.ui import pages
    from adroit.orchestrator.study_headline import held
    for name in ("no record at all", "a damaged ledger", "a terminal state out of order"):
        folder = matrix / _slug(name)
        assert "not available" in pages.study_cost(held(folder)) and pages.list_cost(held(folder)) == \
            "cost not available"
    folder = matrix / _slug("an invalid split")
    assert "records incomplete" in pages.list_cost(held(folder))
    folder = matrix / _slug("a study record against an unsplit stop")      # compatible: the bound holds the $0.0024
    assert pages.list_cost(held(folder)) == "$0.0024 settled (up to $0.4024 committed)"


def test_the_studies_total_counts_known_unknown_and_approximate_apart(matrix):
    """D-6 on the matrix: the ledgers' requests each once; older records' settled and reserved dollars, the cent line
    and the unsplit stops apart (a stop's bound holding its run's settled dollars, counted once as the bound); the
    three runs whose accounting cannot be read counted, never $0."""
    from adroit.orchestrator.cli import app
    out = CliRunner().invoke(app, ["studies", str(matrix)]).output
    total = next(x for x in out.splitlines() if x.startswith("total: "))
    assert "$0.0008 settled over 2 identifiable request(s), each counted once" in total
    assert "and up to $0.4000 reserved whose bill is not yet known" in total
    assert "$0.0048 more settled in older records that name no request" in total
    assert "up to $1.20 more reserved, as older records state" in total
    assert "about $0.1200 more, rounded to the cent" in total
    assert "up to $1.21 committed in records that do not split it into settled and reserved dollars" in total
    assert "3 run(s) whose accounting is not available" in total
    assert "1 run(s) whose records are damaged or disagree" in total
    assert "total spent: $" not in out


async def test_the_studies_page_and_the_batch_page_show_the_same_figures(user: User, tmp_path):
    """The Studies list and the batch page (each item's run cost, and the batch's spending in all: M2, it had shown
    budgets alone) read the same facts."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    names = ["a transport failure", "a tiny charge", "a line to the cent with a reservation", "a damaged ledger"]
    items = []
    for name in names:
        job = _run(root / _slug(name), MATRIX[name][0])
        items.append(batch.BatchItem(title=name, command=IDEA, folder=job.folder, budget_usd=1.0, status="failed"))
    folder = root / "batches" / "b"
    folder.mkdir(parents=True)
    (folder / batch.BATCH).write_text(batch.Batch(title="four runs", folder=str(folder), created="2026-10-25T00:00:00",
                                                  items=items, budget_usd=4.0, status="completed").model_dump_json())
    costs = [accounting.cost(root / _slug(n), engine.load(root / _slug(n))) for n in names]
    await user.open("/studies")
    for c in costs:
        await user.should_see(accounting.short_line(c))
    await user.open("/batches")
    for c in costs:
        await user.should_see(accounting.short_line(c))
    await user.should_see("spent: " + accounting.total_text(accounting.total(costs)))
    await user.should_see("approved budget $4.00")


async def test_the_run_page_shows_the_same_lines(user: User, tmp_path):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    for name in ("a split budget stop", "a study record against an unsplit stop"):
        job = _run(root / _slug(name), MATRIX[name][0])
        await user.open(f"/live?path={_slug(name)}")
        for line in accounting.cost_lines(accounting.cost(Path(job.folder), job)):
            await user.should_see(line)


async def test_a_session_run_and_its_refinement_read_alike_on_every_surface(user: User, tmp_path):
    """A model-intake session: a first run (one settled request) and a refinement (one settled, one whose bill is
    not known), each with its own request record. Each run page shows its own requests and the session's line; the
    session's page shows the same session line; the two runs together count each request once, and equal the
    session's ledger."""
    from adroit.orchestrator.model_intake import REQUESTS, Intake, RunRequests
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    service = Intake()
    session = service.start(budget=1).session_id
    rows = [{**RES, "id": "a", "reserved_usd": 0.1}, {"id": "a", "state": "settled", "cost_usd": 0.03},
            {**RES, "id": "b", "reserved_usd": 0.1}, {"id": "b", "state": "settled", "cost_usd": 0.0008},
            {**RES, "id": "c", "reserved_usd": 0.05}, {"id": "c", "state": "billing_uncertain", "error": "TimeoutError"}]
    (service.folder(session) / "paid.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    costs = []
    for name, ids in (("first", ["a"]), ("refine", ["b", "c"])):
        folder = root / name
        folder.mkdir()
        job = engine.Job(title=name, kind="models", folder=str(folder), status="completed", returncode=0,
                         command=["models", "step", session, "--kind", "idea" if name == "first" else "refine"])
        engine.save(job)
        (folder / REQUESTS).write_text(RunRequests(session_id=session, request_ids=ids).model_dump_json())
        costs.append(accounting.cost(folder, job))
    assert [c.run_usd for c in costs] == [pytest.approx(0.03), pytest.approx(0.0008)]
    assert costs[1].run_uncertain_usd == pytest.approx(0.05) and costs[0].run_uncertain_usd == 0
    t = accounting.total(costs)
    status = service.budget_status(session)
    assert (t.settled_usd, t.reserved_usd, t.requests) == (pytest.approx(status["spent"]),
                                                           pytest.approx(status["reserved_uncertain"]), 3)
    session_line = "Session total so far: " + accounting.status_text(status)
    for name, c in zip(("first", "refine"), costs):
        await user.open(f"/live?path={name}")
        await user.should_see(accounting.run_line(c))
        await user.should_see(session_line)
    await user.open(f"/models/intake?session={session}")
    await user.should_see("This session: " + accounting.status_text(status))

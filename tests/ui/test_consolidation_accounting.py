"""The auditor's consolidation audit, CO-04 (2026-10-25): the run's paid ledger, where present, had been read alone, so
that a budget stop's larger commitment and a log's reservation vanished beside a complete-looking ledger, an empty
ledger read "no paid request was sent" beside a record committing $0.40, a valid budget-stop split hid a log's
larger "spent" line, and an unreadable budget-stop record went unnamed. The auditor's four cases, each through the run
page, the study card, the Studies list (page and line), ``adroit studies`` (line and total): every record's
commitment kept, every disagreement and damage named, and "no paid request was sent" only where nothing contradicts
it. Records are written directly, as the auditor's control wrote them; no provider, request or calculation, $0.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.orchestrator import accounting, studies
from adroit.ui import engine

IDEA = ["idea", "--text", "x", "--budget", "1", "--out", "."]
CASES = {
    # name: (paid ledger or None, the run's result record, its log; what must survive on every surface; conflicts)
    "complete prefix": ([{"id": "r", "state": "reserved", "provider": "anthropic", "reserved_usd": 0.1},
                         {"id": "r", "state": "settled", "cost_usd": 0.0024}],
                        {"status": "budget_stopped", "committed_usd": 0.4024},
                        "spent $0.0024; up to $0.4000 reserved whose bill is not yet known\n", [0.0024, 0.4024], 2),
    "empty journal": ([], {"status": "budget_stopped", "committed_usd": 0.4}, "", [0.4], 1),
    "valid split conflict": (None, {"status": "budget_stopped", "committed_usd": 0.01, "settled_usd": 0.01,
                                    "uncertain_usd": 0}, "spent $0.2000\n", [0.01, 0.2], 1),
    "damaged stop": (None, "{", "spent $0.0024\n", [0.0024], 0),
    "a ledger nothing contradicts": ([], None, "spent $0.0000\n", [], 0),
}


def _slug(name: str) -> str:
    return name.replace(" ", "_")


def _run(folder: Path, ledger, result, log: str) -> engine.Job:
    """A finished paid run (``adroit idea --budget 1``) as the auditor's control left it, with its study record."""
    folder.mkdir(parents=True)
    job = engine.Job(title=folder.name, kind="idea", command=IDEA, folder=str(folder), status="failed", returncode=3)
    engine.save(job)
    if ledger is not None:
        (folder / "paid.jsonl").write_text("".join(json.dumps(x) + "\n" for x in ledger))
    if result is not None:
        (folder / "result.json").write_text(result if isinstance(result, str) else json.dumps(result))
    (folder / engine.LOG).write_text(log)
    studies.record(folder, "idea", folder.name)
    return job


@pytest.fixture
def runs(tmp_path):
    root = tmp_path / "runs"
    root.mkdir()
    for name, (ledger, result, log, *_rest) in CASES.items():
        _run(root / _slug(name), ledger, result, log)
    return root


def test_each_case_keeps_every_commitment_and_names_what_disagrees(runs):
    for name, (*_records, survive, conflicts) in CASES.items():
        folder = runs / _slug(name)
        c = accounting.cost(folder, engine.load(folder))
        assert len(c.conflicts) == conflicts, (name, c.conflicts)
        detail = accounting.run_line(c)
        for dollars in survive:
            assert accounting.usd(dollars) in detail, (name, detail)
        if name == "a ledger nothing contradicts":
            assert detail == "This run: $0 (no paid request was sent)" and not c.damaged
        else:
            assert "no paid request was sent" not in detail and not c.sent_none, (name, detail)
    damaged = accounting.cost(runs / "damaged_stop", engine.load(runs / "damaged_stop"))
    assert damaged.damaged and damaged.damaged[0].startswith("its result record (result.json) cannot be read")
    prefix = accounting.cost(runs / "complete_prefix", engine.load(runs / "complete_prefix"))
    assert (prefix.run_usd, prefix.run_committed_usd, prefix.committed_source) == (
        pytest.approx(0.0024), pytest.approx(0.4024), "its budget-stop record")
    split = accounting.cost(runs / "valid_split_conflict", engine.load(runs / "valid_split_conflict"))
    assert split.run_committed_usd == pytest.approx(0.2) and split.committed_source == "its log"


def test_the_card_the_studies_line_and_the_command_line_say_the_same(runs):
    from adroit.orchestrator.cli import app
    from adroit.ui import pages
    from adroit.orchestrator.study_headline import held
    shown = CliRunner().invoke(app, ["studies", str(runs)])
    assert shown.exit_code == 0, shown.output
    for name, (*_records, survive, conflicts) in CASES.items():
        folder = runs / _slug(name)
        c, s = accounting.cost(folder, engine.load(folder)), studies.load(folder)
        detail, short = accounting.run_line(c), accounting.short_line(c)
        assert pages.study_cost(held(folder)) == "cost: " + detail.removeprefix("This run: ")
        assert pages.list_cost(held(folder)) == short
        line = next(x for x in shown.output.splitlines() if x.endswith(str(folder)))
        assert (f", {short})" in line) if short else line.endswith(f"{s.created}): {folder}"), (name, line)
        for dollars in survive:
            assert accounting.usd(dollars) in short and accounting.usd(dollars) in line, (name, short)
        if conflicts or c.damaged:
            assert short.endswith("· records incomplete"), (name, short)


def test_the_total_keeps_the_commitments_and_counts_the_disagreements(runs):
    from adroit.orchestrator.cli import app
    out = CliRunner().invoke(app, ["studies", str(runs)]).output
    total = next(x for x in out.splitlines() if x.startswith("total: "))
    assert "$0.0024 settled over 1 identifiable request(s), each counted once" in total
    assert "up to $0.4000 more committed, as runs' other records show beyond their paid ledgers" in total
    assert "up to $0.6000 committed in records that do not split it into settled and reserved dollars" in total
    assert "$0.0024 more settled in older records that name no request" in total
    assert "4 run(s) whose records are damaged or disagree" in total


async def test_the_run_page_and_the_studies_page_show_the_same_facts(user: User, tmp_path):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    costs = {}
    for name, (ledger, result, log, *_rest) in CASES.items():
        job = _run(root / _slug(name), ledger, result, log)
        costs[name] = accounting.cost(Path(job.folder), job)
    for name, c in costs.items():
        await user.open(f"/live?path={_slug(name)}")
        for line in accounting.cost_lines(c):
            await user.should_see(line)
        if name != "a ledger nothing contradicts":
            await user.should_not_see("no paid request was sent")
    await user.open("/studies")
    for c in costs.values():
        if accounting.short_line(c):
            await user.should_see(accounting.short_line(c))

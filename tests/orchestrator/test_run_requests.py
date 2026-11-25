"""A session command's own paid requests (``model_intake.RunRequests``) and the fresh output folders a workbench job
may use (2026-10-23)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from adroit.library.personal import Catalog
from adroit.orchestrator.model_intake import Intake


def test_the_ledger_reads_each_requests_state(tmp_path: Path) -> None:
    service = Intake(Catalog(tmp_path / "library"))
    session = service.start(1.0, "claude-opus-5-5").session_id
    rows = [{"id": "a", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.2},
            {"id": "a", "state": "received", "response": {}},
            {"id": "a", "state": "settled", "cost_usd": 0.05},
            {"id": "b", "state": "reserved", "provider": "openai", "reserved_usd": 0.3},
            {"id": "b", "state": "billing_uncertain", "error": "TimeoutError"},
            {"id": "c", "state": "reserved", "provider": "anthropic", "reserved_usd": 0.1},
            {"state": "cap_raised", "previous": 1.0, "new": 2.0, "at": "now"}]
    (service.folder(session) / "paid.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    found = service.requests(session)
    assert {k: (v.state, v.cost_usd) for k, v in found.items()} == {"a": ("settled", 0.05), "b": ("uncertain", None),
                                                                     "c": ("open", None)}
    assert Intake(Catalog(tmp_path / "library")).requests("0" * 32) == {}


def test_a_command_records_only_its_own_requests(tmp_path: Path) -> None:
    """The ids its budgeted clients reserved, written beside its output, also when it stopped; none without --out."""
    from adroit.orchestrator.model_intake import REQUESTS, RunRequests
    from adroit.orchestrator.preflight import record_requests
    service = Intake(Catalog(tmp_path / "library"))
    service.clients.append(SimpleNamespace(ledger=[{"id": "x", "state": "reserved"}, {"id": "x", "state": "settled"},
                                                   {"id": "y", "state": "reserved"}]))
    record_requests(tmp_path / "out", service, "s" * 32)
    assert RunRequests.model_validate_json((tmp_path / "out" / REQUESTS).read_text()).request_ids == ["x", "y"]
    record_requests(None, service, "s" * 32)


def test_a_workbench_job_folder_counts_as_fresh(tmp_path: Path) -> None:
    from adroit.orchestrator.runs import fresh
    folder = tmp_path / "run"
    assert fresh(folder)
    folder.mkdir()
    for name in ("job.json", ".job.lock", "log.txt"):
        (folder / name).write_text("")
    assert fresh(folder)
    (folder / "result.json").write_text("{}")
    assert not fresh(folder) and not fresh(folder / "job.json")


def test_experiments_import_runs_in_a_workbench_job_folder(tmp_path: Path, monkeypatch) -> None:
    """``experiments import`` had refused every workbench launch: its folder holds the job's record and log before
    the command starts. It now writes its draft there; a folder holding other output is still refused."""
    from adroit.core.config import get_settings
    from adroit.orchestrator.cli import app
    monkeypatch.setattr(get_settings(), "experimental_library_dir", tmp_path / "private")
    table = tmp_path / "limit.csv"
    table.write_text("m_GeV,sigma_cm2\n10,1e-43\n20,0\n")
    out = tmp_path / "run"
    out.mkdir()
    (out / "job.json").write_text("{}")
    (out / "log.txt").write_text("$ adroit experiments import\n")
    run = CliRunner().invoke(app, ["experiments", "import", str(table), "--title", "A search", "--out", str(out)])
    assert run.exit_code == 0, run.output
    assert (out / "experimental.json").is_file() and (out / "report.md").is_file()
    again = CliRunner().invoke(app, ["experiments", "import", str(table), "--title", "A search", "--out", str(out)])
    assert again.exit_code != 0 and "new or empty" in again.output

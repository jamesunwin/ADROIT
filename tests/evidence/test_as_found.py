"""The diagnostic outputs state their weaker guarantee (the owner's decision 3 on the version-handle plan, 2026-11-03):
the theory checks, the neutrino fog, the intake, extraction and discovery reports and the advisory outputs are read as
found, each saying what it was made of, and an advisory output bundled with a scientific conclusion is attached saying
it is not checked against it. (The fog, an intake draft, an experimental import and ``adroit agents`` are checked
where their own tests run them: ``tests/physics/test_neutrino_fog.py``, ``tests/orchestrator/test_model_intake.py``,
``tests/library/test_experimental.py``, ``tests/orchestrator/test_agents.py``.) Nothing is calculated or sent."""
from __future__ import annotations

import json
import zipfile

import yaml
from typer.testing import CliRunner

from adroit.evidence.version import as_found


def test_the_statement_says_what_it_was_made_of():
    text = as_found("It was made of m.yaml.")
    assert text.strip().startswith("*Read as found.* It was made of m.yaml.") and "not a held version" in text


def test_a_theory_check_s_report_is_read_as_found(tmp_path):
    from adroit.parameter_space.library import entry
    from adroit.theory.cli import app
    source = tmp_path / "model.yaml"
    source.write_text(yaml.safe_dump(entry("higgs_portal_scalar").spec().model_dump(mode="json")))
    done = CliRunner().invoke(app, ["vacuum", str(source), "--out", str(tmp_path / "vacuum")])
    assert done.exit_code == 0, done.output
    assert "*Read as found.* It was made of model.yaml" in (tmp_path / "vacuum" / "report.md").read_text()


def test_a_discovery_report_is_read_as_found(tmp_path, monkeypatch):
    from adroit.orchestrator import accounting, discovery_cli

    from types import SimpleNamespace

    from adroit.orchestrator.model_intake import REQUESTS, RunRequests

    class Service:
        budgets = SimpleNamespace(request_ids=lambda: [])      # the run's requests, written with its report (DK-01)

        def show(self, session):
            return {"session": session, "model": "catalog:m@r", "state": "searched", "budget": {},
                    "domain": {"name": "m"}, "searched_at": "", "candidates": [], "gaps": []}
    monkeypatch.setattr(accounting, "session_money", lambda budgets, session: "none")
    discovery_cli._report(Service(), "s1", tmp_path / "out")
    text = (tmp_path / "out" / "report.md").read_text()
    assert "*Read as found.* It is the discovery session s1 as it was read" in text
    assert RunRequests.model_validate_json((tmp_path / "out" / REQUESTS).read_text()).session_id == "s1"


def test_an_assistance_report_names_the_saved_result_it_read(tmp_path):
    from adroit.orchestrator import research_assistance as service
    from tests.orchestrator.test_research_assistance import request
    given = service.run(request(), tmp_path / "given")
    assert "It is an advisory reading of the request given, as found." in service.report(given)
    read = service.run(request().model_copy(update={"source_sha256": "a" * 64}), tmp_path / "read")
    assert read.source_sha256 == "a" * 64 and f"SHA-256 {'a' * 64}, read once" in service.report(read)


def test_an_advisory_output_bundled_with_a_result_says_it_is_not_checked_against_it(tmp_path):
    from adroit.evidence.archive import ADVISORY, export_run
    from tests.orchestrator.test_vi_audit import publish, versions
    folder = tmp_path / "study"
    a, _ = versions(folder)
    publish(folder, a, "A")
    (folder / "agents.json").write_text(json.dumps({"subject": "track1"}))
    manifest = export_run(folder, tmp_path / "out.zip", include_agents=True)
    assert f"studies/n0/agents.json: {ADVISORY}" in manifest.warnings
    with zipfile.ZipFile(tmp_path / "out.zip") as z:
        assert "studies/n0/agents.json" in z.namelist()

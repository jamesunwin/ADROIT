"""R7's researcher journeys, offline (FakeLLMClient in place of the paid model):

- words → typed model file → ``track1``;
- a paper → an anomaly draft → ``anomaly check`` passes once a person supplies the resolution.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from adroit.agents import llm as llm_module
from adroit.agents.anomaly import AnomalyDraft
from adroit.agents.ideas import CouplingValue, ModelProposal, ModelProposals, ModelValues, ValueProposals
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import FieldRole, ModelField
from adroit.orchestrator import cli

SINGLET = ModelField(name="S", role=FieldRole.dark_matter, spin=0, self_conjugate=True, dark_parity=-1, mass_gev=300.0)


def _offline(monkeypatch, tmp_path: Path, responses: list) -> dict:
    """The paid client replaced by a scripted one; the paid-response ledger kept in the test's folder."""
    made: dict = {}

    def fake(**kw):
        made["client"] = FakeLLMClient(list(responses), model=kw["model"])
        return made["client"]
    monkeypatch.setattr(llm_module, "LLMClient", fake)
    settings = llm_module.get_settings().model_copy(update={"runs_dir": tmp_path})
    monkeypatch.setattr(llm_module, "get_settings", lambda: settings)
    return made


def _words_to_model_file(monkeypatch, tmp_path: Path) -> Path:
    proposal = ModelProposal(name="RealSinglet", fields=[SINGLET], rationale="the minimal Z2-odd scalar",
                             keywords=["Higgs portal"], stability="Z2 under which S is odd", assumptions=[])
    values = ValueProposals(models=[ModelValues(model=1, couplings=[CouplingValue(name="lam_H_S", value=0.1)])])
    _offline(monkeypatch, tmp_path, [ModelProposals(proposals=[proposal]), values])
    from adroit.agents import ideas as builder
    asked, original = [], builder.IdeaAgent.__init__
    monkeypatch.setattr(builder.IdeaAgent, "__init__", lambda self, llm, model: asked.append(model) or
                        original(self, llm, model))
    out = CliRunner().invoke(cli.app, ["idea", "--text", "a Z2-odd real scalar singlet as the dark matter",
                                       "--budget", "0.5", "--model", "claude-sonnet-5", "--out", str(tmp_path / "idea")])
    assert out.exit_code == 0, out.output
    assert asked == ["claude-sonnet-5"]                                    # --model reaches the builder
    path = tmp_path / "idea" / "models" / "RealSinglet.yaml"
    assert path.is_file() and f"adroit track1 {path}" in out.output
    assert "## Runnable models" in (tmp_path / "idea" / "report.md").read_text()
    return path


def test_words_become_a_model_file_that_track1_takes(tmp_path, monkeypatch) -> None:
    from adroit.model_building.audit import audit
    from adroit.orchestrator import track1
    from adroit.orchestrator.model_approval import read_model
    from adroit.parameter_space.classify import classify
    path = _words_to_model_file(monkeypatch, tmp_path)
    spec = read_model(yaml.safe_load(path.read_text()))                  # the approval digest is checked
    cls, point, _ = classify(spec)
    assert cls.family == "higgs_portal_scalar" and point.m_chi == 300.0
    seen = {}

    def calculation(request, folder, **kwargs):                           # Track 1's scan, stood in for
        seen["request"] = request
        return track1.Track1Result(request=request, audit=audit(request.spec), unsupported="stood in for")
    monkeypatch.setattr(track1, "run", calculation)
    out = CliRunner().invoke(cli.app, ["track1", str(path), "--no-literature", "--out", str(tmp_path / "t1")])
    assert out.exit_code == 0, out.output
    assert seen["request"].spec == spec and (tmp_path / "t1" / "report.md").is_file()


@pytest.mark.slow
def test_words_to_a_track1_verdict(tmp_path, monkeypatch) -> None:
    """The same journey with Track 1's real calculation on a 2 × 2 grid away from the Higgs resonance."""
    path = _words_to_model_file(monkeypatch, tmp_path)
    out = CliRunner().invoke(cli.app, ["track1", str(path), "--x", "m_chi:200:400:lin:2", "--y", "g_chi:0.1:1:log:2",
                                       "--no-literature", "--out", str(tmp_path / "t1")])
    assert out.exit_code == 0, out.output
    text = (tmp_path / "t1" / "report.md").read_text()
    assert text.startswith("# Track 1: RealSinglet") and "## 2. The verdict" in text


PAPER = """We report 140.2 kg days of exposure. The signal region spans recoil energies from 7 to 100 keV.
Three WIMP-candidate events were ob-
served, with recoil energies of 8.2, 9.5, and 12.3 keV. The expected background is 0.41 events."""


def test_a_paper_becomes_a_draft_that_checks_once_a_person_gives_the_resolution(tmp_path, monkeypatch) -> None:
    from adroit.retrieval import corpus
    draft = AnomalyDraft(name="CDMS II Si", target="Si", references=["arXiv:1304.4279"], exposure_kg_day=140.2,
                         window_kev=[7.0, 100.0], events_kev=[8.2, 9.5, 12.3], background_events=0.41,
                         efficiency_figure="Fig. 1",
                         sources={"exposure_kg_day": "140.2 kg days of exposure",
                                  "events_kev": "Three WIMP-candidate events were observed, with recoil energies of "
                                                "8.2, 9.5, and 12.3 keV"},
                         needs_person=["efficiency: digitise Fig. 1"])
    _offline(monkeypatch, tmp_path, [draft])
    monkeypatch.setattr(corpus, "extract_pdf_text", lambda path: PAPER)
    pdf, record = tmp_path / "paper.pdf", tmp_path / "draft.yaml"
    pdf.write_bytes(b"%PDF")
    out = CliRunner().invoke(cli.app, ["anomaly", "draft", "--pdf", str(pdf), "--out", str(record), "--budget", "0.5"])
    assert out.exit_code == 0, out.output
    assert "its quoted source is not in the paper's text" not in out.output          # the hyphenated quote matches
    first = CliRunner().invoke(cli.app, ["anomaly", "check", str(record)])
    assert first.exit_code == 1 and "- resolution_kev: not given yet" in first.output
    data = yaml.safe_load(record.read_text())                                        # what the person does
    data.update(resolution_kev=0.5, resolution_note="the detectors' phonon resolution, from the paper's Sec. 2")
    record.write_text(yaml.safe_dump(data, allow_unicode=True))
    (tmp_path / "efficiency.csv").write_text("7,0.3\n100,0.3\n")
    second = CliRunner().invoke(cli.app, ["anomaly", "check", str(record)])
    assert second.exit_code == 0, second.output
    assert "no problems found" in second.output and "a DRAFT (no verified_by)" in second.output

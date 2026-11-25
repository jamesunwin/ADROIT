"""Unitarity claims in both tracks, CLI, exports and explicitly additive legacy replay."""

from pathlib import Path
import json

import pytest
import yaml
from typer.testing import CliRunner

from adroit.evidence.archive import export_run, verify_bundle
from adroit.evidence.build import read, save, build
from adroit.orchestrator.cli import app
from adroit.orchestrator.single_idea import (
    SingleIdeaRequest,
    SingleIdeaResult,
    BandPoint,
    report as idea_report,
)
from adroit.orchestrator.track1 import report as track_report
from adroit.theory.unitarity_report import report, study_section
from test_vacuum_integration import result


def saved():
    s = result()
    cls = s.scan.request.model_class
    s.scan.points = [
        p.model_copy(update={"unitarity_certificate": cls.unitarity_certificate(p.point)})
        for p in s.scan.points
    ]
    return s


def test_actual_certificate_separate_from_vacuum_and_heuristic_bound() -> None:
    s = saved()
    cls = s.scan.request.model_class
    p = s.fixed
    certificate = cls.unitarity_certificate(p)
    assert certificate.passed and len(certificate.channels) == 15
    potential = cls.potential.model_copy(update={"lambda_s": 10})
    other = type(cls)(potential=potential)
    assert other.perturbative(p) and other.unitarity_certificate(p).passed is False
    assert other.vacuum_certificate(p).passed  # Tree vacuum can pass while partial wave fails.
    assert s.audit.valid
    assert "High-energy scalar partial-wave assessment" in track_report(s)
    assert study_section([]) == [] and "15" in report(certificate)
    band = BandPoint(
        m_chi=p.m_chi,
        s_hat=3,
        events_at_unit=1,
        mu_hat=1,
        mu_68=(0.5, 2),
        z_local=3,
        point=p,
        fitted_value=p.g_chi,
        m_med=p.m_med,
        evaluation=s.scan.points[0],
    )
    idea = SingleIdeaResult(
        request=SingleIdeaRequest(experiment="CDMS II Si (2013)", spec=s.request.spec),
        band=[band],
        level="viable",
        summary="experimental view",
    )
    assert "High-energy scalar partial-wave assessment" in idea_report(idea)
    e = build("single_idea", idea, "sha")
    assert e.certificates["band_scalar_high_energy_unitarity"][0]["passed"]
    obs = next(o for o in e.observations if o.observable == "scalar_high_energy_unitarity")
    assert (
        obs.excluded is None
        and obs.required_confidence_level is None
        and obs.review == "not_required"
    )


def test_cli_source_input_and_legacy_missing_input(tmp_path: Path) -> None:
    r = CliRunner()
    response = r.invoke(
        app,
        [
            "theory",
            "unitarity",
            "docs/examples/complete_scalar_singlet.yaml",
            "--out",
            str(tmp_path / "complete"),
        ],
    )
    assert response.exit_code == 0, response.output
    data = json.loads((tmp_path / "complete/unitarity.json").read_text())
    assert data["passed"] and len(data["channels"]) == 15
    from adroit.parameter_space import library

    src = tmp_path / "legacy.yaml"
    src.write_text(
        yaml.safe_dump(library.entry("higgs_portal_scalar").spec().model_dump(mode="json"))
    )
    response = r.invoke(app, ["theory", "unitarity", str(src), "--out", str(tmp_path / "old")])
    assert response.exit_code == 0, response.output
    assert json.loads((tmp_path / "old/unitarity.json").read_text())["passed"] is None


def test_legacy_export_never_calculates_and_new_replay_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    replay = importlib.import_module("adroit.evidence.replay")
    s = saved()
    row = s.scan.points[0]
    path = tmp_path / "new/result.json"
    path.parent.mkdir()
    path.write_text(s.model_dump_json())
    save(path)
    archive = tmp_path / "new.zip"
    export_run(path, archive)
    assert verify_bundle(archive).valid
    assert read(path).certificates["scalar_high_energy_unitarity"][0]["passed"]
    expected = row.model_dump(mode="json")
    actual = row.model_dump(mode="json")
    actual["unitarity_certificate"]["passed"] = False
    monkeypatch.setattr(replay, "_calculate", lambda *args: (expected, actual))
    assert replay.replay_bundle(archive).status == "different"
    legacy = s.model_copy(deep=True)
    legacy.scan.points = [
        p.model_copy(update={"unitarity_certificate": None}) for p in legacy.scan.points
    ]
    path = tmp_path / "old/result.json"
    path.parent.mkdir()
    path.write_text(legacy.model_dump_json())
    save(path)
    archive = tmp_path / "old.zip"
    export_run(path, archive)
    assert read(path).certificates["scalar_high_energy_unitarity"] == []
    expected = legacy.scan.points[0].model_dump(mode="json")
    actual = row.model_dump(mode="json")
    monkeypatch.setattr(replay, "_calculate", lambda *args: (expected, actual))
    check = replay.replay_bundle(archive)
    assert check.status == "matched" and check.actual["unitarity_certificate"]["passed"]
    assert any("unitarity_certificate" in text for text in check.reasons)
    actual["flags"].append("new genuine numerical unreliability")
    assert replay.replay_bundle(archive).status == "different"

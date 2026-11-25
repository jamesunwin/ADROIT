"""Requested UV domain survives mapping, both report tracks and strict new evidence."""

from pathlib import Path
import json
import yaml
from typer.testing import CliRunner
from adroit.core.model_spec import ModelSpec
from adroit.parameter_space.classify import classify
from adroit.evidence.build import build
from adroit.orchestrator.cli import app
from adroit.orchestrator.track1 import report as track_report
from adroit.theory.running_report import study_section, report
from test_scalar_running import request
from test_vacuum_integration import result


def test_explicit_request_and_evidence():
    s = result()
    spec = s.request.spec.model_copy(update={"scalar_running": request(2000)})
    cls, p, _ = classify(spec)
    assert cls.running == spec.scalar_running
    assert cls.running_certificate(p).passed
    s.request.spec = spec
    s.scan.request.model_class = cls
    for row in s.scan.points:
        row.running_certificate = cls.running_certificate(row.point)
    assert "Declared-scale scalar RG" in track_report(s)
    envelope = build("track1", s, "sha")
    saved = envelope.certificates["scalar_one_loop_running"][0]
    assert saved["request"]["upper_scale_gev"] == 2000
    o = next(o for o in envelope.observations if o.observable == "scalar_one_loop_running")
    assert o.excluded is None and o.required_confidence_level is None
    assert study_section([]) == []
    assert "full-theory" in report(cls.running_certificate(p))
    legacy = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    )
    assert classify(legacy)[0].running is None
    assert classify(legacy)[0].running_certificate(p).status == "missing_input"


def test_free_running_cli_and_invalid_request(tmp_path):
    spec = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    )
    spec.scalar_running = request(2000)
    source = tmp_path / "spec.yaml"
    source.write_text(yaml.safe_dump(spec.model_dump(mode="json")))
    response = CliRunner().invoke(
        app, ["theory", "running", str(source), "--out", str(tmp_path / "out")]
    )
    assert response.exit_code == 0, response.output
    assert json.loads((tmp_path / "out/running.json").read_text())["passed"]
    spec.scalar_running = None
    source.write_text(yaml.safe_dump(spec.model_dump(mode="json")))
    response = CliRunner().invoke(
        app, ["theory", "running", str(source), "--out", str(tmp_path / "old")]
    )
    assert response.exit_code == 0
    assert json.loads((tmp_path / "old/running.json").read_text())["status"] == "missing_input"


def test_no_matching_precision_upgrade():
    import pytest
    from adroit.parameter_space.classify import Unsupported

    spec = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    )
    spec.scalar_running = request(2000).model_copy(update={"scalar_matching": "declared_MSbar"})
    with pytest.raises(Unsupported, match="matching"):
        classify(spec)


def test_the_running_cli_refuses_msbar_labelling_for_a_typed_model(tmp_path):
    """Release audit minor: Track 1 refused declared_MSbar for a typed model's potential; the CLI ran it."""
    spec = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    )
    spec.scalar_running = request(2000).model_copy(update={"scalar_matching": "declared_MSbar"})
    source = tmp_path / "spec.yaml"
    source.write_text(yaml.safe_dump(spec.model_dump(mode="json")))
    response = CliRunner().invoke(app, ["theory", "running", str(source), "--out", str(tmp_path / "out")])
    assert response.exit_code != 0 and "tree_level_identification" in response.output
    assert not (tmp_path / "out").exists()

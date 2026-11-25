"""Pending prerequisites reach both reports and saved evidence without changing rates."""

import json
from pathlib import Path
import yaml
import pytest
from typer.testing import CliRunner
from adroit.orchestrator.cli import app
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.parameter_space.classify import classify
from adroit.core.model_spec import ModelSpec
from adroit.evidence.build import build
from adroit.orchestrator.track1 import report as track_report
from adroit.orchestrator.single_idea import (
    SingleIdeaResult,
    SingleIdeaRequest,
    BandPoint,
    report as idea_report,
)
from test_vacuum_integration import result
from test_conversion_rates import example


def spec():
    result = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/tchannel_equilibrium.yaml").read_text())
    )
    result.chemical_equilibrium.source_born = None  # exercise preserved legacy diagnostic
    return result


def test_map_reports_evidence_and_pending():
    s = result()
    model = spec()
    cls, p, notes = classify(model)
    assert cls.conversion == model.chemical_equilibrium and cls.partner == "eR"
    assert cls.pending(p) and any("chemical equilibrium" in f for f in cls.flags(p))
    s.request.spec = model
    s.scan.request.model_class = cls
    s.scan.request.fixed = p
    s.fixed = p
    row = s.scan.points[0].model_copy(
        update={
            "point": p,
            "vacuum_certificate": None,
            "running_certificate": None,
            "model_contract": {},
            "chemical_certificate": cls.chemical_certificate(p),
            "flags": cls.flags(p),
            "pending": cls.pending(p),
        }
    )
    s.scan.points = [row] * 4
    assert "chemical-equilibrium prerequisite" in track_report(s)
    band = BandPoint(
        m_chi=p.m_chi,
        s_hat=1,
        events_at_unit=1,
        mu_hat=1,
        mu_68=(0.5, 2),
        z_local=1,
        point=p,
        m_med=p.m_med,
        evaluation=row,
        fitted_value=p.g_chi,
    )
    idea = SingleIdeaResult(
        request=SingleIdeaRequest(experiment="CDMS II Si (2013)", spec=model),
        band=[band],
        level="viable_pending",
        summary="pending",
    )
    assert "chemical-equilibrium prerequisite" in idea_report(idea)
    e = build("single_idea", idea, "sha")
    o = next(o for o in e.observations if o.observable == "coannihilation_chemical_equilibrium")
    assert o.calculation == "unresolved" and o.excluded is None
    assert (
        e.certificates["band_coannihilation_chemical_equilibrium"][0]["physical_prerequisite"]
        == "pending"
    )
    assert TChannel(partner="uR").pending(Point(m_chi=100, m_med=110, g_chi=0.3))


def test_cli_and_no_default_rates(tmp_path):
    src = tmp_path / "input.yaml"
    src.write_text(yaml.safe_dump(example().model_dump(mode="json")))
    response = CliRunner().invoke(
        app, ["theory", "equilibrium", str(src), "--out", str(tmp_path / "out")]
    )
    assert response.exit_code == 0, response.output
    c = json.loads((tmp_path / "out/equilibrium.json").read_text())
    assert c["passed"] is None and c["physical_prerequisite"] == "pending"
    response = CliRunner().invoke(
        app,
        [
            "theory",
            "equilibrium",
            "docs/examples/tchannel_equilibrium.yaml",
            "--out",
            str(tmp_path / "spec"),
        ],
    )
    assert response.exit_code == 0, response.output
    missing = TChannel(partner="eR").chemical_certificate(
        Point(m_chi=10000, m_med=10500, g_chi=0.3)
    )
    assert missing.status == "missing_input" and not missing.rates
    wrong = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    )
    with pytest.raises(ValueError):
        ModelSpec.model_validate(
            wrong.model_copy(update={"chemical_equilibrium": example().request}).model_dump()
        )

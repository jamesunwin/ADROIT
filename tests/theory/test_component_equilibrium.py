"""Explicit source accuracy, complete channels, robust decisions and legacy preservation."""

import copy
import pytest
from adroit.theory.chemical_equilibrium import certify
from adroit.theory.component_equilibrium import THRESHOLD
from adroit.parameter_space.portals.tchannel import TChannel
from test_source_born import source_inputs
from test_conversion_rates import example


def test_source_component_passes_without_inclusive_claim():
    p = source_inputs(3e-5)
    c = certify(p)
    assert c.algorithm_version == 4 and c.status == "passed" and c.complete and c.passed
    assert c.component_prerequisite == "supported" and c.physical_prerequisite == "pending"
    assert len(c.required_channels) == 4 and not c.missing_channels
    assert len(c.uncomputed_corrections) == 3 and c.calibrated_threshold == THRESHOLD
    cls = TChannel(partner="eR", conversion=p.request)
    assert not cls.pending(p.point)
    assert any("declared source-regulated component" in f for f in cls.flags(p.point))
    c.rates.clear()
    assert certify(p).rates


def test_source_weak_and_missing_channels_fail_closed():
    p = source_inputs(1e-7)
    c = certify(p)
    assert c.component_prerequisite == "unsupported" and c.passed is False and c.complete
    assert c.physical_prerequisite == "pending"
    p.request.include_odd_sector = False
    c = certify(p)
    assert c.status == "missing_rates" and c.passed is None and c.missing_channels
    assert len(c.required_channels) == 4
    p = source_inputs()
    p.point.g_chi = 0
    c = certify(p)
    assert (
        c.algorithm_version == 4
        and c.component_prerequisite == "unsupported"
        and c.physical_prerequisite == "failed"
    )


def test_boundary_and_unresolved_rate_never_pass(monkeypatch):
    import adroit.theory.component_equilibrium as ce

    p = source_inputs()
    c = certify(p)
    scale = (100 / c.minimum_relaxation_over_h) ** 0.5
    p.point.g_chi *= scale
    assert certify(p).status == "unresolved"
    row = copy.deepcopy(c.rates[0])
    row.quadrature_relative_difference = 0.2
    monkeypatch.setattr(ce, "rate_point", lambda *args: row)
    p.point.g_chi *= 1.012345
    assert certify(p).status == "unresolved" and certify(p).passed is None


def test_default_old_diagnostic_stays_pending_and_scheme_is_explicit():
    c = certify(example(3e-5))
    assert c.algorithm_version == 1 and c.passed is None and c.component_prerequisite is None
    p = source_inputs()
    p.partner = "muR"
    assert certify(p).status == "missing_rates" and certify(p).algorithm_version == 4
    from adroit.core.chemical_equilibrium import SourceBornSettings

    with pytest.raises(ValueError):
        SourceBornSettings(
            scheme="garny_1705_appendix_A_full_angle_vacuum_mass_MB",
            scope="retained_abelian_component_only",
            energy_cuts_gev=(0.1, 0.5, 50.0),
        )


def test_source_cli_reports_and_evidence(tmp_path):
    import json
    import yaml
    from pathlib import Path
    from typer.testing import CliRunner
    from adroit.orchestrator.cli import app
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.classify import classify
    from adroit.evidence.build import build
    from adroit.orchestrator.track1 import report
    from test_vacuum_integration import result

    spec = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/tchannel_equilibrium.yaml").read_text())
    )
    cls, p, _ = classify(spec)
    c = cls.chemical_certificate(p)
    saved = result()
    saved.request.spec = spec
    saved.scan.request.model_class = cls
    saved.scan.points = [
        v.model_copy(update={"point": p, "chemical_certificate": c, "vacuum_certificate": None})
        for v in saved.scan.points
    ]
    assert "supported" in report(saved) and "Inclusive/plasma" in report(saved)
    e = build("track1", saved, "sha")
    o = next(o for o in e.observations if o.observable == "coannihilation_chemical_equilibrium")
    assert o.calculation == "computed" and o.excluded is None
    assert (
        o.details["component_prerequisite"] == "supported" and o.details["uncomputed_corrections"]
    )
    response = CliRunner().invoke(
        app,
        [
            "theory",
            "equilibrium",
            "docs/examples/tchannel_equilibrium.yaml",
            "--out",
            str(tmp_path),
        ],
    )
    assert response.exit_code == 0, response.output
    data = json.loads((tmp_path / "equilibrium.json").read_text())
    assert (
        data["passed"]
        and data["component_prerequisite"] == "supported"
        and data["physical_prerequisite"] == "pending"
    )

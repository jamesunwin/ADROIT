"""Free theory checks on complete model or coefficient inputs."""

from __future__ import annotations

import json
from pathlib import Path
import typer
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.core.theory import ScalarVacuumInput, VacuumSettings
from adroit.theory.scalar_vacuum import certify, for_potential
from adroit.theory.report import report

app = typer.Typer(pretty_exceptions_show_locals=False, help="Explicitly scoped deterministic theory certificates. $0.")


@app.command("vacuum")
def vacuum(
    source: Path,
    out: Path = typer.Option(..., "--out", help="folder for vacuum.json and report.md"),
    tolerance: float = typer.Option(1e-10, "--tolerance", min=1e-16, max=1e-4,
                                    help="relative resolution of the sign, stationarity and vacuum-depth decisions"),
) -> None:
    """Tree-level Z2 scalar potential, global vacuum and competing extrema; no lifetime/RG claim."""
    try:
        data = yaml.safe_load(source.read_text())
        settings = VacuumSettings(relative_tolerance=tolerance)
        if "fields" in data:
            spec = ModelSpec.model_validate(data)
            if spec.scalar_potential is None:
                result = certify(None, settings)
            else:
                from adroit.model_building.scalar_contract import resolved_spec

                resolved_spec(spec)
                inputs = for_potential(spec.scalar_potential.resolve()).inputs
                result = certify(inputs, settings)
        else:
            result = certify(ScalarVacuumInput.model_validate(data), settings)
    except (ValueError, OSError, TypeError) as error:
        raise typer.BadParameter(str(error)) from None
    _export(out, {"vacuum.json": result.model_dump_json(indent=2),
                  "report.md": report(result) + _as_found(source)})
    typer.echo(
        json.dumps(
            {
                "vacuum": result.vacuum,
                "boundedness": result.boundedness,
                "passed": result.passed,
                "complete": result.complete,
                "out": str(out),
                "cost_usd": 0,
            }
        )
    )


@app.command("unitarity")
def unitarity(
    source: Path,
    out: Path = typer.Option(..., "--out", help="folder for unitarity.json and report.md"),
    tolerance: float = typer.Option(1e-10, "--tolerance", min=1e-16, max=1e-4,
                                    help="relative resolution of the eigensystem checks and the |a₀| boundary decision"),
) -> None:
    """Complete normalized scalar-pair matrix in the high-energy contact limit. $0."""
    from adroit.core.theory import UnitaritySettings
    from adroit.theory.scalar_unitarity import certify as unitary
    from adroit.theory.unitarity_report import report as unitarity_report

    try:
        data = yaml.safe_load(source.read_text())
        inputs = None
        if "fields" in data:
            spec = ModelSpec.model_validate(data)
            if spec.scalar_potential is not None:
                from adroit.model_building.scalar_contract import resolved_spec

                resolved_spec(spec)
                inputs = for_potential(spec.scalar_potential.resolve()).inputs
        else:
            inputs = ScalarVacuumInput.model_validate(data)
        result = unitary(inputs, UnitaritySettings(relative_tolerance=tolerance))
    except (ValueError, OSError, TypeError) as error:
        raise typer.BadParameter(str(error)) from None
    _export(out, {"unitarity.json": result.model_dump_json(indent=2),
                  "report.md": unitarity_report(result) + _as_found(source)})
    typer.echo(
        json.dumps(
            {
                "status": result.status,
                "passed": result.passed,
                "complete": result.complete,
                "channels": len(result.channels),
                "max_abs_a0": result.maximum_abs_a0,
                "out": str(out),
                "cost_usd": 0,
            }
        )
    )


@app.command("running")
def running(source: Path, out: Path = typer.Option(..., "--out", help="folder for running.json and report.md")) -> None:
    """One-loop scalar running; input must declare matching, threshold policy and upper scale."""
    from adroit.core.running import RGRequest
    from adroit.theory.scalar_running import certify as run_rg
    from adroit.theory.running_report import report as rg_report
    try:
        data=yaml.safe_load(source.read_text())
        if "fields" in data:
            spec=ModelSpec.model_validate(data)
            if spec.scalar_potential:
                from adroit.model_building.scalar_contract import resolved_spec
                resolved_spec(spec)
            inputs=for_potential(spec.scalar_potential.resolve()).inputs if spec.scalar_potential else None
            request=spec.scalar_running
            # a typed model's potential is fixed by tree-level identification with the physical masses: as in Track 1
            # (CompleteScalarPortal), its couplings cannot be labelled MSbar (release audit minor)
            if spec.scalar_potential and request is not None and request.scalar_matching!="tree_level_identification":
                raise ValueError("a typed model's potential is identified at tree level from its physical masses; label "
                                 "its running scalar_matching: tree_level_identification, or give standalone coefficient "
                                 "RG inputs for declared MSbar parameters")
        else:
            inputs=ScalarVacuumInput.model_validate(data["potential"])
            request=RGRequest.model_validate(data["running"])
        result=run_rg(inputs,request)
    except (ValueError,OSError,TypeError,KeyError) as error:
        raise typer.BadParameter(str(error)) from None
    _export(out, {"running.json": result.model_dump_json(indent=2),
                  "report.md": rg_report(result) + _as_found(source)})
    typer.echo(json.dumps({"status":result.status,"passed":result.passed,"out":str(out),"cost_usd":0}))


@app.command("equilibrium")
def equilibrium(source: Path,out: Path = typer.Option(...,"--out",help="folder for equilibrium.json and report.md")) -> None:
    """Scoped coannihilation prerequisite with separately labelled Born conversion diagnostics."""
    from adroit.core.chemical_equilibrium import ConversionInput
    from adroit.theory.chemical_equilibrium import certify as chemical
    from adroit.theory.chemical_report import report as chemical_report
    try:
        data=yaml.safe_load(source.read_text())
        if "fields" in data:
            from adroit.parameter_space.classify import classify
            from adroit.parameter_space.portals.tchannel import TChannel
            cls,point,_=classify(ModelSpec.model_validate(data))
            if not isinstance(cls,TChannel):
                raise ValueError("chemical equilibrium requires a t-channel model")
            result=cls.chemical_certificate(point)
        else:
            result=chemical(ConversionInput.model_validate(data))
    except (ValueError,OSError,TypeError) as error:
        raise typer.BadParameter(str(error)) from None
    _export(out, {"equilibrium.json": result.model_dump_json(indent=2),
                  "report.md": chemical_report(result) + _as_found(source)})
    typer.echo(json.dumps({"status":result.status,"physical_prerequisite":result.physical_prerequisite,
        "component_prerequisite":result.component_prerequisite,"born_diagnostic_passed":result.born_diagnostic_passed,"out":str(out),"cost_usd":0}))


def _as_found(source: Path) -> str:
    """The report's statement of what it was made of, read as found (``evidence.version.as_found``)."""
    from adroit.evidence.version import as_found
    return as_found(f"It was made of {Path(source).name} as it was read when this check ran.")


def _export(out: Path, members: dict[str, str]) -> None:
    """A check's results and report, written whole under one hold of ``out`` (``durable.export``: each to its own
    entry, a link replaced, never written through; refused in a saved study's folder; the auditor's DI recheck, DJ-01,
    2026-11-07)."""
    from adroit.core.durable import export
    try:
        export(out, members)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None


"""CLI for free evidence export, verification and explicit point replay."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(pretty_exceptions_show_locals=False, help="Scientific evidence export, integrity checks and explicit deterministic replay.")


@app.command(name="export")
def export(source: Path, out: Path = typer.Option(..., "--out", help="the new evidence ZIP; an existing file is refused"),
           include_agents: bool = typer.Option(False, "--include-agents",
                                               help="also include allowlisted advisory agent outputs (never arbitrary logs)"),
           include_private_prompts: bool = typer.Option(False, "--include-private-prompts",
                                                        help="keep prompt and response text in the included agent "
                                                             "evidence (needs --include-agents or --agent-evidence)"),
           agent_evidence: list[Path] | None = typer.Option(None, "--agent-evidence",
                                                            help="an advisory agent JSON from a separate review "
                                                                 "folder; repeatable")) -> None:
    """Export a selected result/study graph; never recalculate physics. $0."""
    from adroit.evidence.archive import export_run
    try:
        manifest = export_run(source, out, include_agents=include_agents,
                              include_private_prompts=include_private_prompts, agent_evidence=agent_evidence)
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(f"Exported {len(manifest.nodes)} studies, {len(manifest.artifacts)} artifacts to {out}; $0.")
    for warning in manifest.warnings:
        typer.echo(warning)
    if manifest.local_paths:                       # also in the bundle's manifest (AL3-22)
        typer.echo(f"Local paths: {manifest.local_paths}.")


@app.command(name="verify")
def verify(archive: Path, check_environment: bool = typer.Option(
        False, "--check-environment",
        help="also compare the bundle's software, external-tool and package-input hashes with this installation")) -> None:
    """Verify integrity and reconstruct saved decisions; no numerical calculations. $0.

    "valid" means internally consistent; provenance is not verified (anyone can build a self-consistent
    bundle).
    """
    from adroit.evidence.archive import verify_bundle
    try:
        result = verify_bundle(archive, check_environment=check_environment)
    except OSError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(result.model_dump_json(indent=2))
    if not result.valid:
        raise typer.Exit(1)


@app.command(name="replay")
def replay(archive: Path, node: str = typer.Option("n0", "--node", help="the bundle's study node: n0 the exported "
                                                    "study, n1, n2, ... the studies linked to it (as verify lists them)"),
           index: int = typer.Option(0, "--index", min=0, help="the saved point to recompute (0-based): a Track 1 "
                                                               "scan point, or a fit or band entry"),
           eligibility:bool=typer.Option(False,'--eligibility',help='recalculate captured physical eligibility comparisons instead of the NR fit')) -> None:
    """Explicitly recalculate ONE point/fit using installed deterministic code. $0.

    The installed code runs on the bundle's inputs (untrusted data); the bundle's own code never runs.
    """
    from adroit.evidence.replay import replay_bundle
    typer.echo("Replay runs installed ADROIT code on this bundle's inputs; treat them as untrusted data.", err=True)
    try:
        result = replay_bundle(archive, node_id=node, index=index,**({'eligibility':True} if eligibility else {}))
    except (ValueError, OSError) as error:
        from adroit.evidence.archive import readable
        raise typer.BadParameter(readable(error)) from None
    typer.echo(result.model_dump_json(indent=2))
    if result.status != "matched":
        raise typer.Exit(1)


@app.command(name="point")
def point(result: Path, point_id: str = typer.Option("", "--point", help="the point (grid:i, contour:j, fitted:k, "
                                                                        "thermal:k, candidate:LABEL); omit to list them")) -> None:
    """Explain one point of a saved study from its saved result and evidence: what was calculated there and what each
    constraint decided (excluded, allowed or pending, with the reasons). Nothing is recalculated. $0."""
    import json
    from adroit.evidence import points
    from adroit.evidence.version import resolve
    try:
        found = resolve(result)                     # a fresh selection: the version saved now, read once
        if not point_id:
            held = found.saved()
            for row in points.points(held.workflow, held.result):
                typer.echo(f"{row.point_id}\t{row.status}\t{row.kind}\t{row.reason[:100]}")
            return
        typer.echo(json.dumps(points.explain(found, point_id).model_dump(mode="json"), indent=2))
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from None


@app.command(name="tables")
def tables(result: Path, out: Path = typer.Option(..., "--out", help="a new folder for the tables")) -> None:
    """A saved study's numbers as tables: points.csv (full precision; units, status, confidence levels, sources,
    review, pending reasons and each point's halo), points.json, points_numeric.csv, README.txt and halo.json (the halo
    its run resolved, or as read from an older result's request). A value that was not calculated is empty, never
    zero. Nothing is recalculated. $0."""
    from adroit.evidence import exports
    _write(out, exports.tables(result / "result.json" if result.is_dir() else result))


@app.command(name="figures")
def figures(result: Path, out: Path = typer.Option(..., "--out", help="a new folder for the figures"),
            fmt: list[str] = typer.Option(["pdf", "svg"], "--format", help="pdf, svg or png; repeatable")) -> None:
    """A saved study's figures, redrawn from its saved scan and verdict in each format, with its saved PNGs. $0."""
    from adroit.evidence import exports
    _write(out, exports.figures(result / "result.json" if result.is_dir() else result, tuple(fmt)))


def _write(out: Path, files: dict[str, bytes]) -> None:
    if out.exists():
        raise typer.BadParameter("the output folder already exists")
    try:
        out.mkdir(parents=True)     # only where none is, when it is made: another made meanwhile is refused
    except FileExistsError:
        raise typer.BadParameter("the output folder already exists: another was made there meanwhile") from None
    for name, data in files.items():
        (out / name).write_bytes(data)
        typer.echo(str(out / name))

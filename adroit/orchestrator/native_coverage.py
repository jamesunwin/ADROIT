"""Free, typed CLI boundary for a native nuisance-coverage study."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from adroit.core.model_spec import ModelSpec, PhysicalFitRange
from adroit.core.state import StrictModel
from adroit.experiments import registry
from adroit.parameter_space.classify import classify
from adroit.parameter_space.native_joint import prepare, observed_data, SIGNAL, LOW_MASS_NULL
from adroit.parameter_space.native_coverage import (
    CoverageSettings,
    NuisanceScenario,
    CoverageResult,
    study,
)
from adroit.parameter_space.physical_fit import FitSettings
from adroit.core.chronology import dated_report


class CoverageRequest(StrictModel):
    """All physical inputs and statistical choices required for reproducibility."""

    spec: ModelSpec
    masses_gev: list[float] = Field(min_length=1)
    signal_experiment: str = SIGNAL
    null_experiment: str = LOW_MASS_NULL
    scenarios: list[NuisanceScenario] = Field(min_length=1)
    settings: CoverageSettings = Field(default_factory=CoverageSettings)
    fit_settings: FitSettings = Field(default_factory=FitSettings)


def run(request: CoverageRequest, folder: Path) -> CoverageResult:
    """Run the declared finite-grid diagnostic; do not mutate the supplied model."""
    return run_reported(request, folder)[0]


def run_reported(request: CoverageRequest, folder: Path) -> tuple[CoverageResult, str]:
    """``run``, with the report as it wrote it, of the result it holds: what the command prints, never the file read
    again (the auditor's DA recheck, DB-02, 2026-11-03: another result's report, published there since, had been printed)."""
    if request.signal_experiment != SIGNAL or request.null_experiment != LOW_MASS_NULL:
        raise ValueError("nuisance study currently supports CDMS Si plus PICO")
    if len(set(request.masses_gev)) != len(request.masses_gev):
        raise ValueError("distinct supplied masses required")
    from adroit.evidence.runtime import capture_request
    from adroit.evidence.build import publish
    evidence_context = capture_request(request)
    cls, point, _ = classify(request.spec)
    bounds = request.spec.physical_fit or PhysicalFitRange.perturbative_branch(point.g_chi)
    signal = registry.load_module(request.signal_experiment)
    null = registry.load_module(request.null_experiment)
    templates = [
        prepare(
            cls,
            point.model_copy(update={"m_chi": m}),
            bounds,
            signal,
            null,
            request.spec.dark_matter.spin,
        )
        for m in request.masses_gev
    ]
    from adroit.core.durable import publishing
    with publishing(folder) as owned:        # the folder held from its first file to its result (DF-01)
        (folder / "request.json").write_text(request.model_dump_json(indent=2))

        def progress(result: CoverageResult) -> None:
            (folder / "progress.json").write_text(result.model_dump_json(exclude={"cases"}))

        result = study(
            templates,
            observed_data(signal),
            signal,
            request.scenarios,
            request.settings,
            request.fit_settings,
            progress,
        )
        # the result, its evidence and its report, bound to it, of one serialization (the auditor's CX recheck, CY-03; its CY
        # recheck, CZ-02), the report dated by that evidence (as ``build.save`` had dated it, reading it again)
        from adroit.core.chronology import analysis_report
        _, text = publish(folder / "result.json", result.model_dump_json(indent=2).encode(), result,
                          lambda envelope: (analysis_report(report(result), context=envelope.context)
                                            if envelope.context.calculation_started_at else report(result)),
                          workflow="native_coverage", context=evidence_context,
                          original_inputs=request.model_dump(mode="json"), claim=owned)
    return result, text




@dated_report
def report(result: CoverageResult) -> str:
    """Render empirical coverage without claiming a continuous nuisance certificate."""
    lines = [
        "# Native nuisance-coverage diagnostic",
        "",
        result.construction,
        "",
        f"Complete: {result.complete}; conclusion: {result.conclusion}; {result.fits} physical maxima; "
        f"alpha={result.settings.alpha}; masses={result.masses_gev} GeV.",
        "",
        "| true Si theta | true PICO backgrounds | trials | false positives | simultaneous interval | conclusion |",
        "|---|---|---|---|---|---|",
    ]
    for c in result.cases:
        lines.append(
            f"| {c.scenario.theta:g} | {c.scenario.null_backgrounds} | {c.trials} | "
            f"{c.rejections} | {c.interval} | {c.conclusion}; {c.reason} |"
        )
    return "\n".join(lines) + "\n"

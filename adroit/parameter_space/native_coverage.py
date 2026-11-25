"""Nested simulation of the actual conditional native discovery procedure.

Each outer null dataset is recalibrated at its own fitted nuisances. The
reported false-positive rates concern only the explicit finite nuisance grid.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from pydantic import Field, model_validator
from scipy.stats import beta

from adroit.core.state import StrictModel
from adroit.experiments.historical import HistoricalSearch
from adroit.parameter_space.native_joint import (
    PairTemplate,
    JointSettings,
    _calibrate,
    LOW_MASS_NULL,
)
from adroit.parameter_space.native_toys import draw_background, pico_maximum
from adroit.parameter_space.physical_fit import FitSettings
from adroit.statistics.native_pair import EventData


class NuisanceScenario(StrictModel):
    """Specified true silicon and PICO background parameters under no dark matter."""

    theta: float = Field(ge=0, allow_inf_nan=False)
    null_backgrounds: list[float] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _finite(self) -> NuisanceScenario:
        if not np.isfinite(self.null_backgrounds).all() or min(self.null_backgrounds) < 0:
            raise ValueError("finite nonnegative PICO backgrounds required")
        return self


class CoverageSettings(StrictModel):
    """Declared nested toy statistics, familywise intervals and fit cap."""

    outer_trials: int = Field(default=200, ge=1, le=10000)
    inner_toys: int = Field(default=199, ge=19, le=10000)
    alpha: float = Field(default=0.05, gt=0, lt=0.5)
    family_error: float = Field(default=0.05, gt=0, lt=1)
    seed: int = Field(default=20261008, ge=0)
    max_fits: int = Field(default=1000000, ge=1, le=100000000)


class CoverageCase(StrictModel):
    """Empirical false-positive probability at one true nuisance point."""

    scenario: NuisanceScenario
    complete: bool = False
    trials: int = 0
    rejections: int = 0
    fraction: float | None = None
    interval: tuple[float, float] | None = None
    conclusion: str = "incomplete"
    p_values: list[float] = Field(default_factory=list)
    reason: str = ""


class CoverageResult(StrictModel):
    """A finite-grid diagnostic, never a uniform nuisance-coverage certificate."""

    settings: CoverageSettings
    masses_gev: list[float]
    complete: bool = False
    fits: int = 0
    cases: list[CoverageCase] = Field(default_factory=list)
    conclusion: str = "incomplete"
    construction: str = (
        "nested background-only simulation: every outer dataset refits and recalibrates at its own "
        "null nuisance estimates; same mass bank/continuous physical bounds; Bonferroni simultaneous "
        "Clopper-Pearson intervals over the specified finite nuisance grid; not uniform coverage "
        "over a continuous or unbounded nuisance space, and not coverage of LR confidence regions"
    )


class _OuterTrial(StrictModel):
    complete: bool = False
    fits: int = 0
    p: float | None = None
    reason: str = ""


def _one_trial(
    templates: list[PairTemplate],
    data: EventData,
    signal: HistoricalSearch,
    scenario: NuisanceScenario,
    settings: CoverageSettings,
    fit_settings: FitSettings,
    rng: np.random.Generator,
) -> _OuterTrial:
    trial = _OuterTrial()
    try:
        observation = draw_background(data, signal, scenario.theta, scenario.null_backgrounds, rng)
        maxima = []
        for template in templates:
            trial.fits += 1
            maxima.append(pico_maximum(template, observation, fit_settings).q0)
        inner = JointSettings(
            null_experiment=LOW_MASS_NULL,
            toys=settings.inner_toys,
            seed=int(rng.integers(0, 2**32)),
            max_toy_fits=len(templates) * settings.inner_toys,
        )
        calibrated = _calibrate(
            templates,
            observation.signal,
            signal,
            max(maxima),
            inner,
            fit_settings,
            null_observed=observation.null_counts,
        )
        trial.fits += calibrated.toy_fits
        if not calibrated.complete:
            raise ValueError(calibrated.reason)
        trial.complete = True
        trial.p = calibrated.p_mc
    except (ValueError, RuntimeError, ArithmeticError) as error:
        trial.reason = str(error)
    return trial


def study(
    templates: list[PairTemplate],
    data: EventData,
    signal: HistoricalSearch,
    scenarios: list[NuisanceScenario],
    settings: CoverageSettings,
    fit_settings: FitSettings | None = None,
    progress: Callable[[CoverageResult], None] | None = None,
) -> CoverageResult:
    """Measure Type-I error of the whole fitted-nuisance calibration on an explicit grid."""
    if not templates or not scenarios or any(t.null_experiment != LOW_MASS_NULL for t in templates):
        raise ValueError("complete native PICO templates and nonempty nuisance scenarios required")
    if 1 / (settings.inner_toys + 1) > settings.alpha:
        raise ValueError("inner Monte Carlo resolution cannot test the requested alpha")
    fit_settings = fit_settings or FitSettings()
    result = CoverageResult(settings=settings, masses_gev=[t.point.m_chi for t in templates])
    rng = np.random.default_rng(settings.seed)
    required = len(templates) * (settings.inner_toys + 1)
    for scenario in scenarios:
        case = CoverageCase(scenario=scenario)
        result.cases.append(case)
        for _ in range(settings.outer_trials):
            if result.fits + required > settings.max_fits:
                case.reason = "nested native coverage fit budget exhausted"
                return result
            trial = _one_trial(templates, data, signal, scenario, settings, fit_settings, rng)
            result.fits += trial.fits
            if not trial.complete:
                case.reason = trial.reason
                return result
            case.p_values.append(trial.p)
            case.rejections += trial.p <= settings.alpha
            case.trials += 1
            if progress and case.trials % 10 == 0:
                progress(result)
        _finish_case(case, settings, len(scenarios))
        if progress:
            progress(result)
    result.complete = True
    labels = {c.conclusion for c in result.cases}
    result.conclusion = (
        "undercoverage_detected"
        if "undercoverage_detected" in labels
        else "inconclusive_on_tested_grid"
        if "inconclusive" in labels
        else "controlled_on_tested_grid"
    )
    return result


def _finish_case(case: CoverageCase, settings: CoverageSettings, count: int) -> None:
    k, n = case.rejections, case.trials
    tail = settings.family_error / (2 * count)
    low = 0.0 if k == 0 else float(beta.ppf(tail, k, n - k + 1))
    high = 1.0 if k == n else float(beta.ppf(1 - tail, k + 1, n - k))
    case.complete = True
    case.fraction = k / n
    case.interval = low, high
    case.conclusion = (
        "undercoverage_detected"
        if low > settings.alpha
        else "controlled"
        if high <= settings.alpha
        else "inconclusive"
    )

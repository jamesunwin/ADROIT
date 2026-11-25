"""CDMS II Si + DEAP native module likelihoods and bounded-domain toy calibration.

The pilot uses the modules' declared fidelity-B reconstruction, not unreleased
collaboration nuisance models. Pure SI models with proven quadratic recoil
scaling reuse exact component spectra; other models remain explicitly pending.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from pydantic import Field
from scipy.stats import beta, norm

from adroit.core.model_spec import PhysicalFitRange
from adroit.core.dm_state import CrossSectionKind, DarkMatterParticle, ExpectedSignal
from adroit.core.state import StrictModel
from adroit.core.fit_domain import PhysicalDomain, DomainFitSettings
from adroit.parameter_space.multiparameter_fit import DomainFit
from adroit.experiments import registry
from adroit.experiments.historical import HistoricalSearch
from adroit.experiments.deap3600 import Deap3600
from adroit.experiments.pico60 import Pico60, EXPOSURES
from adroit.experiments.native_validation import certified_range
from adroit.inference.signal_fit import event_densities, seen_events
from adroit.parameter_space.classes import Point, Spin1Class, ScalarClass
from adroit.parameter_space.flavour_vector import FlavourVectorClass
from adroit.constraints.spin1 import Spin1Kind
from adroit.parameter_space.physical_fit import PhysicalFit, FitSettings, FitTrial, fit_trials
from adroit.parameter_space.native_toys import draw_background, pico_maximum
from adroit.statistics.native_pair import (
    EventData,
    event_profile,
    zero_count_log_l,
    binned_free_background_log_l,
)

SIGNAL = "CDMS II Si (2013)"
NULL = "DEAP-3600 (2019)"
LOW_MASS_NULL = "PICO-60 C3F8 (2019)"


class JointSettings(StrictModel):
    """Explicit pair, simulation count/seed and hard calibration fit cap."""

    null_experiment: str = NULL
    toys: int = Field(default=1000, ge=1, le=100000)
    seed: int = Field(default=20261007, ge=0)
    max_toy_fits: int = Field(default=10000, ge=1, le=1000000)
    domain: PhysicalDomain | None = None
    domain_settings: DomainFitSettings = Field(default_factory=DomainFitSettings)


class PairTemplate(StrictModel):
    """Exact physical spectra at a reference coupling for a quadratic SI model."""

    point: Point
    bounds: PhysicalFitRange
    signal_count: float                  # events seen inside the window at ``point`` (signal_fit.seen_events)
    signal_grid: list[float]
    signal_density: list[float]
    null_count: float
    null_relative_uncertainty: float
    resolution_kev: float
    scaling_verified_relative_error: float
    null_experiment: str = NULL
    null_counts: list[float] = Field(default_factory=list)
    null_observed: list[int] = Field(default_factory=list)


class Calibration(StrictModel):
    """Monte Carlo tail probability for the exact requested physical search."""

    complete: bool = False
    toys_requested: int
    toys_completed: int = 0
    seed: int
    toy_fits: int = 0
    exceedances: int | None = None
    p_mc: float | None = None
    p_interval_95: tuple[float, float] | None = None
    z_mc: float | None = None
    minimum_resolvable_p: float | None = None
    q0_comparison_tolerance: float = 0.0
    maxima_q0: list[float] = Field(default_factory=list)
    reason: str = ""
    construction: str = (
        "conditional plug-in background-only calibration; refit the same "
        "discrete mass bank and continuous bounded g_chi in every toy; auxiliary observations "
        "drawn from the fitted bifurcated likelihood without clipping; DEAP has zero background; "
        "add-one Monte Carlo p and binomial 95% interval; not unconditional nuisance coverage"
    )


class JointResult(StrictModel):
    """Native joint fits and their separately labelled calibrated significance."""

    signal_experiment: str = SIGNAL
    null_experiment: str = NULL
    settings: JointSettings
    masses_gev: list[float]
    bounds: PhysicalFitRange | None = None
    reference_point: Point | None = None
    fit_settings: FitSettings = Field(default_factory=FitSettings)
    model_class: FlavourVectorClass | Spin1Class | ScalarClass | None = None  # actual engine; absent in legacy results
    spin: float | None = None
    fits: list[PhysicalFit] = Field(default_factory=list)
    domain_fit: DomainFit | None = None
    best_point: Point | None = None
    observed_max_q0: float | None = None
    log_l_components: dict[str, float] = Field(default_factory=dict)
    background_theta: float | None = None
    null_backgrounds: list[float] = Field(default_factory=list)
    calibration: Calibration | None = None
    complete: bool = False
    omitted: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(
        default_factory=lambda: [
            "CDMS II Si public event list, declared resolution/background shape and uncertainty",
            "DEAP zero-event Poisson likelihood with the module's Cousins-Highland Gaussian sensitivity",
            "DEAP quenching/acceptance uncertainties unavailable in usable form remain omitted",
            "common fixed published SHM halo; independent detector/background nuisance models",
            "one-sign g_chi range containing zero; mediator and other couplings fixed",
            "native to declared fidelity-B modules; not the full unreleased collaboration likelihoods",
            "joint pair only; other limit-equivalent/null constraints stay separately labelled",
        ]
    )


def _supported(cls: Any) -> bool:
    if isinstance(cls,FlavourVectorClass):
        return False  # generic native SI certificate did not validate new arbitrary flavour/current shapes
    return (isinstance(cls, Spin1Class) and cls.kind is Spin1Kind.vector) or (
        isinstance(cls, ScalarClass) and not cls.dm_pseudoscalar and not cls.sm_pseudoscalar
    )


def observed_data(module: HistoricalSearch) -> EventData:
    """The silicon observations and source auxiliary background constraint."""
    events, _ = module.observations()
    rate = module.background_rate()
    if rate is None or not rate.free:
        raise ValueError("source background-rate constraint required")
    return EventData(
        energies=events.tolist(),
        background_at_events=module.background_at(events).tolist(),
        background_total=rate.total,
        sigma_minus=rate.minus,
        sigma_plus=rate.plus,
        auxiliary=rate.centre,
    )


def _null_prediction(cls: Any, p: Point, null: Deap3600 | Pico60, spin: float) -> ExpectedSignal:
    conv = null.conventions()
    return null.expected_signal(
        DarkMatterParticle(mass_gev=p.m_chi, spin=spin),
        cls.interaction(p),
        conv.halo,
        conv.nuclear_model,
    )


def _scaling_error(
    cls: Any,
    high: Point,
    signal: HistoricalSearch,
    null: Deap3600 | Pico60,
    spin: float,
    original: ExpectedSignal,
    original_null: ExpectedSignal,
) -> float:
    from adroit.orchestrator.single_idea import _candidate
    from adroit.orchestrator.signal import _signal

    errors = []
    for fraction in (0.25, 0.5):
        p = high.model_copy(update={"g_chi": high.g_chi * fraction})
        s = _signal(signal, _candidate(cls, p, spin))
        n = _null_prediction(cls, p, null, spin)
        for actual, wanted in (
            (s.density, np.array(original.density) * fraction**2),
            (n.density, np.array(original_null.density) * fraction**2),
        ):
            errors.append(
                float(
                    np.max(abs(np.array(actual) - wanted)) / max(float(np.max(abs(wanted))), 1e-300)
                )
            )
        if abs(n.relative_uncertainty - original_null.relative_uncertainty) > 1e-8:
            raise ValueError("null sensitivity uncertainty changes with coupling")
    if max(errors) > 1e-8:
        raise ValueError("exact quadratic scaling check failed")
    return max(errors)


def prepare(
    cls: Any,
    point: Point,
    bounds: PhysicalFitRange,
    signal: HistoricalSearch,
    null: Deap3600 | Pico60,
    spin: float,
) -> PairTemplate:
    """Prepare exact, checked quadratic templates in both detectors' allowed domain."""
    from adroit.orchestrator.single_idea import _candidate
    from adroit.orchestrator.signal import _signal

    if not _supported(cls):
        raise ValueError("pilot requires a pure-SI spin-1 vector or scalar-scalar class")
    if bounds.low < 0 < bounds.high or bounds.low != 0 and bounds.high != 0:
        raise ValueError("pilot requires one coupling-sign branch including zero")
    span = (
        certified_range(null.name)
        if isinstance(null, Pico60)
        else null.validated_range(CrossSectionKind.si)
    )
    if span is None or not span[0] <= point.m_chi <= span[1]:
        raise ValueError(f"mass outside {null.name}'s validated native SI envelope")
    if signal.conventions().halo != null.conventions().halo:
        raise ValueError("a common fixed halo is required for this pair")
    ref = bounds.low if bounds.low < 0 else bounds.high
    high = point.model_copy(update={"g_chi": ref})
    if hasattr(cls, "domain") and cls.domain(high):
        raise ValueError(cls.domain(high))
    allowed = (
        cls.perturbative(high)
        if hasattr(cls, "perturbative")
        else max(abs(high.g_chi), abs(high.g_q), abs(high.g_l)) <= math.sqrt(4 * math.pi)
    )
    if not allowed:
        raise ValueError("declared range exceeds the model's perturbative branch")
    original = _signal(signal, _candidate(cls, high, spin))
    original_null = _null_prediction(cls, high, null, spin)
    if original.total_events <= 0 or original_null.total_events <= 0:
        raise ValueError("nonzero physical signal support in both searches required")
    error = _scaling_error(cls, high, signal, null, spin, original, original_null)
    _, resolution = signal.observations()
    if not np.all(resolution == resolution[0]):
        raise ValueError("pilot requires the source's constant resolution")
    return PairTemplate(
        point=high,
        bounds=bounds,
        signal_count=seen_events(original.observable, original.density, resolution),
        signal_grid=original.observable,
        signal_density=original.density,
        null_count=original_null.total_events,
        null_relative_uncertainty=original_null.relative_uncertainty,
        resolution_kev=float(resolution[0]),
        scaling_verified_relative_error=error,
        null_experiment=null.name,
        null_counts=original_null.density if isinstance(null, Pico60) else [],
        null_observed=[n for _, _, n in EXPOSURES] if isinstance(null, Pico60) else [],
    )


def null_log_l(template: PairTemplate, factor: float, observed: list[int] | None = None) -> float:
    """Native null component at the same physical rate factor as the silicon signal."""
    if template.null_experiment == LOW_MASS_NULL:
        return binned_free_background_log_l(
            template.null_observed if observed is None else observed,
            (np.array(template.null_counts) * factor).tolist(),
        )
    return zero_count_log_l(template.null_count * factor, template.null_relative_uncertainty)


def fit_pair(
    template: PairTemplate,
    data: EventData,
    settings: FitSettings,
    null_observed: list[int] | None = None,
) -> PhysicalFit:
    """One shared physical coupling fit with actual native likelihood components."""
    f = event_densities(
        np.array(template.signal_grid),
        np.array(template.signal_density),
        np.array(data.energies),
        template.resolution_kev,
    )
    null = event_profile(0.0, np.zeros(len(f)), data).log_l

    def evaluate(p: Point) -> FitTrial:
        factor = (p.g_chi / template.point.g_chi) ** 2
        s = template.signal_count * factor
        value = event_profile(s, f, data).log_l + null_log_l(template, factor, null_observed)
        return FitTrial(point=p, log_l=value, signal_events=s, densities_at_events=f.tolist())

    result = fit_trials(template.point, template.bounds, settings, null, evaluate)
    result.construction = (
        "native module joint likelihood: Si background profiled once; "
        + (
            "PICO independent nonnegative backgrounds profiled once; "
            if template.null_experiment == LOW_MASS_NULL
            else "DEAP sensitivity C-H averaged once; "
        )
        + "nominal likelihood-ratio regions, not calibrated boundary coverage"
    )
    return result


def _calibrate(
    templates: list[PairTemplate],
    data: EventData,
    signal: HistoricalSearch,
    observed_q0: float,
    settings: JointSettings,
    fit_settings: FitSettings,
    null_observed: list[int] | None = None,
) -> Calibration:
    rng = np.random.default_rng(settings.seed)
    result = Calibration(toys_requested=settings.toys, seed=settings.seed)
    theta = event_profile(0.0, np.zeros(len(data.energies)), data).theta
    n_null = templates[0].null_observed if null_observed is None else null_observed
    pico = templates[0].null_experiment == LOW_MASS_NULL
    if pico:
        result.construction = result.construction.replace(
            "DEAP has zero background",
            "PICO backgrounds are independent/free; toys use their observed null estimates",
        )
    maxima = []
    try:
        for _ in range(settings.toys):
            observation = draw_background(data, signal, theta, n_null, rng)
            values = []
            for template in templates:
                if result.toy_fits >= settings.max_toy_fits:
                    raise ValueError("native joint calibration fit budget exhausted")
                result.toy_fits += 1
                if pico:
                    fit = pico_maximum(template, observation, fit_settings)
                else:
                    fit = fit_pair(template, observation.signal, fit_settings)
                    if not fit.resolved or not fit.identifiable:
                        raise ValueError(f"toy physical fit unresolved: {fit.reason}")
                values.append(fit.q0)
            maxima.append(max(values))
            result.toys_completed += 1
    except (ValueError, RuntimeError, ArithmeticError) as error:
        result.reason = str(error)
        result.maxima_q0 = maxima
        return result
    result.q0_comparison_tolerance = max(1e-9, 2 * fit_settings.log_l_tolerance)
    hits = int(np.sum(np.array(maxima) >= observed_q0 - result.q0_comparison_tolerance))
    n = len(maxima)
    low = 0.0 if hits == 0 else float(beta.ppf(0.025, hits, n - hits + 1))
    high = 1.0 if hits == n else float(beta.ppf(0.975, hits + 1, n - hits))
    result.complete = True
    result.exceedances = hits
    result.p_mc = (hits + 1) / (n + 1)
    result.p_interval_95 = (low, high)
    result.minimum_resolvable_p = 1 / (n + 1)
    result.z_mc = max(0.0, float(norm.isf(result.p_mc))) if result.p_mc < 1 else 0.0
    result.maxima_q0 = maxima
    return result


def published_halo_only() -> None:
    """Refuse (``ValueError``) where a fixed benchmark halo is in force (``halo_region.using``): the native joint
    likelihood has no form at a benchmark yet, and is never calculated at its published halo in the benchmark's
    place."""
    from adroit.core.halo_choice import FixedHalo, resolve, unsupported
    from adroit.parameter_space import halo_region
    value = halo_region.preset()
    if isinstance(value, FixedHalo):
        raise ValueError(unsupported(resolve(value), "native-joint"))


def run(
    cls: Any,
    point: Point,
    masses: list[float],
    bounds: PhysicalFitRange,
    settings: JointSettings,
    fit_settings: FitSettings,
    spin: float,
    signal_experiment: str = SIGNAL,
    checkpoint=None,
) -> JointResult:
    """Fit/calibrate the entire requested physical domain, or report missing coverage. Refused at a fixed benchmark
    halo in force (``halo_choice.CONSUMERS``: built and calibrated at its searches' common published halo only)."""
    published_halo_only()
    result = JointResult(
        settings=settings,
        masses_gev=masses,
        bounds=bounds,
        reference_point=point,
        fit_settings=fit_settings,
        null_experiment=settings.null_experiment,
        signal_experiment=signal_experiment,
        model_class=cls if isinstance(cls, (Spin1Class, ScalarClass)) else None,
        spin=spin,
    )
    if signal_experiment != SIGNAL:
        result.omitted[signal_experiment] = "no native joint adapter for this signal search"
        return result
    if settings.null_experiment not in (NULL, LOW_MASS_NULL):
        result.omitted[settings.null_experiment] = "no native joint adapter for this null search"
        return result
    if settings.domain is not None:
        from adroit.parameter_space.native_domain import run_domain
        return run_domain(result, cls, point, masses, settings.domain,
                          settings.domain_settings, spin, checkpoint)
    if not masses or len(set(masses)) != len(masses):
        result.omitted["domain"] = "nonempty distinct mass bank required"
        return result
    signal = registry.load_module(SIGNAL)
    null = registry.load_module(settings.null_experiment)
    if isinstance(null, Pico60):
        result.assumptions = [a for a in result.assumptions if not a.startswith("DEAP")]
        result.assumptions += [
            "PICO observed counts 3/0 in the 1404/1167 kg-day exposures at 2.45/3.29 keV",
            "PICO independent free nonnegative backgrounds; fixed best-fit nucleation curves",
            "PICO calibration/threshold covariance unavailable in usable form remains omitted",
            "native SI certificate only; generic DM3 limit-envelope eligibility unchanged",
        ]
    data = observed_data(signal)
    templates = _fitted(result, cls, point, masses, bounds, signal, null, spin, data, fit_settings)
    if result.omitted:
        return result
    _best(result, templates, data, settings)
    result.calibration = _calibrate(templates, data, signal, result.observed_max_q0, settings, fit_settings)
    result.complete = result.calibration.complete
    return result


def _fitted(result: JointResult, cls: Any, point: Point, masses: list[float], bounds: PhysicalFitRange, signal, null,
            spin: float, data, fit_settings: FitSettings) -> list:
    """Each mass's template and its fit (added to ``result.fits``); a mass that cannot be fitted is omitted with
    why."""
    templates = []
    for mass in masses:
        try:
            template = prepare(
                cls, point.model_copy(update={"m_chi": mass}), bounds, signal, null, spin
            )
            fit = fit_pair(template, data, fit_settings)
            result.fits.append(fit)
            if not fit.resolved or not fit.identifiable:
                raise ValueError(fit.reason)
            templates.append(template)
        except (ValueError, RuntimeError, ArithmeticError) as error:
            result.omitted[repr(mass)] = str(error)
    return templates


def _best(result: JointResult, templates: list, data, settings: JointSettings) -> None:
    """The best fit's point, q0, background and log L components, and the null search's backgrounds there."""
    best = max(result.fits, key=lambda f: f.q0)
    template = next(t for t in templates if t.point.m_chi == best.point.m_chi)
    f = event_densities(
        np.array(template.signal_grid),
        np.array(template.signal_density),
        np.array(data.energies),
        template.resolution_kev,
    )
    factor = (best.point.g_chi / template.point.g_chi) ** 2
    profile = event_profile(template.signal_count * factor, f, data)
    result.best_point = best.point
    result.observed_max_q0 = best.q0
    result.background_theta = profile.theta
    result.log_l_components = {
        SIGNAL: profile.log_l,
        settings.null_experiment: null_log_l(template, factor),
    }
    result.null_backgrounds = np.maximum(
        0, np.array(template.null_observed) - factor * np.array(template.null_counts)
    ).tolist()

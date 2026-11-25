"""Named physical-domain fits for the existing public-data native pairs.

Mass banks are discrete. At every new mediator mass/SM-coupling point we
calculate fresh spectra; only verified exact g_chi² scaling is reused.
No interpolation or new discovery calibration is introduced.
"""
from __future__ import annotations

import math
import numpy as np

from adroit.core.evidence import content_hash
from adroit.core.checkpoint import CheckpointMismatch
from adroit.core.fit_domain import PhysicalDomain, DomainFitSettings
from adroit.core.model_spec import PhysicalFitRange
from adroit.experiments import registry
from adroit.core.dm_state import CrossSectionKind
from adroit.experiments.native_validation import certified_range
from adroit.experiments.pico60 import Pico60, EXPOSURES
from adroit.parameter_space.multiparameter_fit import fit_domain
from adroit.parameter_space.physical_fit import FitTrial
from adroit.inference.signal_fit import event_densities
from adroit.statistics.native_pair import event_profile


def evaluator(cls, spin, signal, null, data, checkpoint=None, null_observed=None):
    """Return one coherent likelihood and a fresh-component verification hook."""
    from adroit.parameter_space.native_joint import prepare, PairTemplate, null_log_l
    templates = {}
    densities = {}

    def components(p, fresh=False):
        if min(p.m_chi,p.m_med) <= 0 or max(abs(p.g_chi),abs(p.g_q),abs(p.g_l)) > math.sqrt(4*math.pi):
            raise ValueError("outside positive-mass/perturbative Point domain")
        if p.g_q == 0:
            # Pure SI vector/scalar pairs have no nuclear signal without quark coupling.
            f = np.zeros(len(data.energies))
            ll = event_profile(0, f, data)
            from adroit.statistics.native_pair import binned_free_background_log_l
            null_ll = binned_free_background_log_l(null_observed if null_observed is not None else
                [v[2] for v in EXPOSURES],[0.,0.]) if isinstance(null,Pico60) else 0.
            return ll, null_ll, 0., f, None
        anchor = p.model_copy(update={"g_chi": 1.})
        key = content_hash(anchor.model_dump(mode="json"))
        if fresh or key not in templates:
            template = None if fresh or checkpoint is None else checkpoint.load("native_templates",key,PairTemplate)
            if template is not None and (template.point != anchor or template.null_experiment != null.name):
                raise CheckpointMismatch("cached native template does not match requested Point/search")
            if template is None:
                template = prepare(cls,anchor,PhysicalFitRange(low=0,high=1),signal,null,spin)
                if checkpoint is not None and not fresh:
                    checkpoint.save("native_templates",key,template)
            templates[key] = template
            densities[key] = event_densities(np.array(template.signal_grid),np.array(template.signal_density),
                                            np.array(data.energies),template.resolution_kev)
        template, f = templates[key], densities[key]
        factor = p.g_chi**2
        s = template.signal_count*factor
        return event_profile(s,f,data),null_log_l(template,factor,null_observed),s,f,template

    def evaluate(p):
        ll, n, s, f, _ = components(p)
        return FitTrial(point=p,log_l=ll.log_l+n,signal_events=s,densities_at_events=f.tolist())
    return evaluate, components


def run_domain(result, cls, point, masses, domain: PhysicalDomain,
               settings: DomainFitSettings, spin, checkpoint=None):
    """Fit a named physical domain on a discrete mass bank to the native pair's signal experiment and null search
    (``fit_domain``), with detector templates remade at the optimum; fills ``result``'s best point, q0 and log L
    components, or records why the fit is omitted."""
    from adroit.parameter_space.native_joint import observed_data
    result.bounds = None
    result.assumptions = [a for a in result.assumptions if not a.startswith("one-sign")]
    result.assumptions += [
        "named physical domain; discrete mass bank; continuous coordinates evaluated directly",
        "finite-resolution maxima/profiles; local rank does not prove global uniqueness",
        "multiparameter q0 is descriptive; discovery calibration and region coverage deferred",
        "uncalibrated sampled profile values are diagnostics, not confidence regions",
    ]
    try:
        signal, null = _domain_modules(result, cls, point, masses, domain)
        if isinstance(null,Pico60):
            result.assumptions = [a for a in result.assumptions if not a.startswith('DEAP')]
            result.assumptions += [
                "PICO independent free nonnegative backgrounds; fixed best-fit nucleation curves",
                "PICO calibration/threshold covariance unavailable in usable form remains omitted",
            ]
        data = observed_data(signal)
        background = event_profile(0,np.zeros(len(data.energies)),data).log_l
        if isinstance(null,Pico60):
            from adroit.statistics.native_pair import binned_free_background_log_l
            background += binned_free_background_log_l([v[2] for v in EXPOSURES],[0.,0.])
        evaluate, components = evaluator(cls,spin,signal,null,data,checkpoint)
        fit = fit_domain(point,domain,settings,background,evaluate,checkpoint)
        result.domain_fit = fit
        if fit.point is None:
            result.omitted['domain'] = fit.reason
            return result
        _optimum(result, fit, components, settings)
        # Calibration stays None: old one-parameter toys cannot calibrate this new search.
    except (ValueError, RuntimeError, ArithmeticError) as error:
        result.omitted['domain'] = str(error)
    return result


def _domain_modules(result, cls, point, masses, domain: PhysicalDomain):
    """The native pair's (signal, null) modules once the domain is one they fit: the certified engine, one discrete
    mass bank equal to the requested masses, inside the null search's validated envelope, one source halo; else
    ValueError, why."""
    from adroit.parameter_space.native_joint import _supported, SIGNAL
    if not _supported(cls):
        raise ValueError("native domain requires the certified pure-SI vector or scalar-scalar engine")
    mass_axis = next((c for c in domain.coordinates if c.parameter=='m_chi'),None)
    if mass_axis is not None and mass_axis.values is None:
        raise ValueError("native m_chi must remain an explicit discrete mass bank")
    if any(r.target=='m_chi' for r in domain.relations) or any('m_chi' in b.fixed for b in domain.branches):
        raise ValueError("declare fitted masses in one discrete mass coordinate")
    expected = mass_axis.values if mass_axis else [domain.fixed.get('m_chi',point.m_chi)]
    if not masses or masses != expected:
        raise ValueError("requested masses must equal the declared physical-domain mass bank in order")
    signal, null = registry.load_module(SIGNAL),registry.load_module(result.null_experiment)
    span = certified_range(null.name) if isinstance(null,Pico60) else null.validated_range(CrossSectionKind.si)
    if span is None or any(not span[0] <= m <= span[1] for m in masses):
        raise ValueError("entire mass bank must lie in the null search's validated native SI envelope")
    if signal.conventions().halo != null.conventions().halo:
        raise ValueError("one common fixed source halo required")
    return signal, null


def _optimum(result, fit, components, settings: DomainFitSettings) -> None:
    """The fit's optimum in ``result``, with the detector templates independently remade there (no cached shape): a
    disagreement unresolves the fit."""
    from adroit.parameter_space.native_joint import SIGNAL, LOW_MASS_NULL
    ll, n, s, _, template = components(fit.point,fresh=True)
    if abs(ll.log_l+n-fit.log_l) > settings.log_l_tolerance:
        fit.resolved = False
        fit.identifiable = False
        fit.reason = "fresh detector spectra disagree with the fitted maximum"
    result.best_point = fit.point
    result.observed_max_q0 = fit.q0
    result.background_theta = ll.theta
    result.log_l_components = {SIGNAL:ll.log_l,result.null_experiment:n}
    result.null_backgrounds = (np.maximum(0,np.array(template.null_observed)-fit.point.g_chi**2*np.array(template.null_counts)).tolist()
                              if template and result.null_experiment==LOW_MASS_NULL else [])
    result.complete = fit.resolved
    if not fit.resolved:
        result.omitted['domain'] = fit.reason

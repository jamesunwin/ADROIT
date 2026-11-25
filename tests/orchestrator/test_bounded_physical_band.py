"""Physical fallback changes fit quality honestly while preserving NR references."""

import math

import pytest

from adroit.core.model_spec import PhysicalFitRange
from adroit.experiments import registry
from adroit.orchestrator import single_idea as idea
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.physical_fit import FitSettings


def reference(cls, point, module):
    return idea._fit_at(module, cls, point, point.m_chi, 0.5)


def test_declared_range_fits_boundary_instead_of_clipping_the_free_amplitude():
    module = registry.load_module("CDMS II Si (2013)")
    cls, p = Spin1Class(), Point(m_chi=10, m_med=125.09, g_chi=0.001, g_q=0.25)
    raw = reference(cls, p, module)
    fitted = idea._on_band(
        cls, p, raw, module, assess=False, fit_range=PhysicalFitRange(low=0, high=0.001)
    )
    assert fitted.physical_fit.resolved and fitted.physical_fit.at_boundary
    assert fitted.point.g_chi == 0.001
    assert fitted.mu_hat == raw.mu_hat and fitted.z_local == raw.z_local
    assert fitted.physical_fit.delta_log_l_vs_reference < 0
    assert idea._fit_z(fitted) < 1 < raw.z_local
    assert idea._level([fitted], [], True)[0] == "no_fit"
    assert fitted.physical_fit.regions[-1].high_at_bound


def test_default_fallback_rescues_an_out_of_range_inverse_and_zero_reference():
    module = registry.load_module("CDMS II Si (2013)")
    cls = Spin1Class()
    p = Point(m_chi=10, m_med=4000, g_chi=1, g_q=0.25)
    raw = reference(cls, p, module)
    assert raw.mu_hat>math.sqrt(4*math.pi)
    fitted = idea._on_band(cls, p, raw, module, assess=False)
    assert fitted.physical_fit is not None and fitted.physical_fit.resolved
    assert fitted.point.g_chi == pytest.approx(math.sqrt(4 * math.pi))
    assert fitted.physical_fit.at_boundary
    p = p.model_copy(update={"m_med": 125.09, "g_chi": 0.0})
    raw = reference(cls, p, module)
    fitted = idea._on_band(cls, p, raw, module, assess=False)
    assert fitted.physical_fit.resolved and fitted.point.g_chi > 0
    assert idea._fit_z(fitted) > 1 and raw.z_local == 0


def test_budget_failure_remains_pending_and_declared_range_reaches_window():
    module = registry.load_module("CDMS II Si (2013)")
    cls, p = Spin1Class(), Point(m_chi=10, m_med=125.09, g_chi=0.001, g_q=0.25)
    raw = reference(cls, p, module)
    domain = PhysicalFitRange(low=0, high=0.02)
    failed = idea._on_band(
        cls,
        p,
        raw,
        module,
        assess=False,
        fit_range=domain,
        fit_settings=FitSettings(max_evaluations=5),
    )
    assert failed.point is None and failed.status == "pending"
    assert idea._level([failed], [], True)[0] == "undetermined"
    fitted = idea._on_band(cls, p, raw, module, assess=False, fit_range=domain)
    x, _ = idea._window([fitted], 4, domain)
    assert domain.low <= x.low < x.high <= domain.high


def test_bound_range_survives_model_roundtrip_and_empty_reference_fit():
    from adroit.parameter_space.simplified import model

    spec = model("vector", 10, 125.09, 0.001, 0.25).model_copy(
        update={"physical_fit": PhysicalFitRange(low=0, high=0.02)}
    )
    assert type(spec).model_validate_json(spec.model_dump_json()).physical_fit == spec.physical_fit
    module = registry.load_module("CDMS II Si (2013)")
    cls = Spin1Class()
    point = Point(m_chi=10, m_med=125.09, g_chi=0, g_q=0.25)
    rows, _, z, method, _ = idea._fit_masses(module, [idea._candidate(cls, point, 0.5)], 20)
    assert z == 0 and "not computed" in method and rows[0].events_at_unit == 0


def test_a_fit_stuck_at_its_boundary_cannot_support_a_headline():
    """Release audit minor: a bounded fit at the edge of its range passed the "fits" test (√q0 ≥ 1)."""
    module = registry.load_module("CDMS II Si (2013)")
    cls, p = Spin1Class(), Point(m_chi=10, m_med=125.09, g_chi=0.0, g_q=0.25)
    fitted = idea._on_band(cls, p, reference(cls, p, module), module, assess=False)
    assert idea._fit_z(fitted) > 1
    stuck = fitted.model_copy(update={"physical_fit": fitted.physical_fit.model_copy(update={"at_boundary": True})})
    assert idea._fit_z(stuck) == 0
    level, why = idea._level([stuck], [], True)
    assert level == "undetermined" and "edge of its declared range" in why

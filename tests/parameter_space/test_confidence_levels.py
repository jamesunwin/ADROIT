"""Native 90% curves are not 95% cuts or Gaussian 95% likelihood inputs."""
import math

import pytest

from adroit.constraints.searches import Outcome
from adroit.parameter_space import likelihood, limits, searches
from adroit.parameter_space.classes import Point, ScalarClass


def test_poisson_native_and_requested_cl_from_same_likelihood():
    from adroit.statistics.poisson import poisson_upper_limit as upper_limit
    # A zero-background counting likelihood has P(0|s)=exp(-s).
    a, b = upper_limit(0, cl=0.9), upper_limit(0, cl=0.95)
    assert a == pytest.approx(2.302585092994046)
    assert b == pytest.approx(2.995732273553991)
    assert math.exp(-a) == pytest.approx(0.1)
    assert math.exp(-b) == pytest.approx(0.05)


def test_unconverted_limit_preserves_native_result_and_cannot_enter_combination():
    native = Outcome(name="source", excluded=True, ratio=1.2, confidence_level=0.9,
                     source="native curve").at95()
    assert native.excluded is None and native.ratio is None
    assert native.native_excluded and native.native_ratio == 1.2
    assert "95%" in native.why and "90%" in native.why
    with pytest.raises(ValueError, match="95%"):
        likelihood.combined({"source": 1.2}, {}, confidence_levels={"source": 0.9})
    original = Outcome(name="95", excluded=False, ratio=0.8)
    assert original.at95() == original
    assert "native 95.4%" in original.model_copy(update={"confidence_level": .954}).at95().why


def test_dd_95_recomputes_module_procedure_and_preserves_native_table(monkeypatch):
    from adroit.experiments import registry
    from adroit.core.dm_state import CrossSectionKind
    name = "DEAP-3600 (2019)"
    monkeypatch.setattr(registry, "module_names", lambda: [name])
    limits.clear_cache()
    module = registry.load_module(name)
    native = module.reference_limits(CrossSectionKind.si, [100.0])[0]
    result = limits.at95("SI", 100.0)
    assert result.value > native
    assert result.value == pytest.approx(module.reference_limits(CrossSectionKind.si, [100.0], cl=0.95)[0])
    assert result.confidence_level == 0.95 and result.source == name
    assert limits.envelope("SI", 100.0) is not None
    limits.clear_cache()


def test_flavour_native_exclusion_is_pending_at_95():
    cls = ScalarClass(name="a", dm_pseudoscalar=True, sm_pseudoscalar=True)
    result = searches.flavour(cls, Point(m_chi=0.1, m_med=1, g_chi=1, g_q=1), True)
    assert result.native_excluded and result.excluded is None and result.ratio is None
    assert result.confidence_level == 0.9 and "1303.7465" in result.source


def test_native_record_gate_does_not_suppress_independent_95_limit(monkeypatch):
    from adroit.parameter_space.portals.vector import ChargedZPrime
    monkeypatch.setattr(searches, "_ccfr", lambda p, unverified: (True, 1.5))
    results = searches.lmu_ltau(ChargedZPrime(charges="Lmu-Ltau"),
                               Point(m_chi=1, m_med=100, g_q=.1), False)
    native = next(o for o in results if "BaBar/Belle" in o.name)
    ccfr = next(o for o in results if o.name == searches.LMU)
    assert native.excluded is None and native.confidence_level == .9
    assert ccfr.excluded and ccfr.ratio == 1.5 and ccfr.confidence_level == .95

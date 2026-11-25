"""A fitted NR strength must describe a physical model and a thermal headline."""
import math

import pytest

from adroit.experiments import registry
from adroit.orchestrator import single_idea as idea
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.fit_inversion import invert
from adroit.parameter_space.portals.higgs import HiggsPortalScalar


@pytest.mark.parametrize("cls,spin", [(HiggsPortalScalar(), 0), (Spin1Class(), .5)])
def test_factor_four_amplitude_reproduces_full_spectrum_and_likelihood(cls, spin):
    module = registry.load_module("CDMS II Si (2013)")
    point = Point(m_chi=10, m_med=125.09, g_chi=.001, g_q=.25)
    fitted = idea._on_band(cls, point, idea.BandPoint(m_chi=10, s_hat=2, events_at_unit=1,
            mu_hat=4, mu_68=(2, 5), z_local=2), module, spin, assess=False)
    assert fitted.point is not None, fitted.inversion_reason
    assert fitted.point.m_med == 125.09
    assert fitted.fitted_value == pytest.approx(.004)
    assert fitted.spectrum_relative_error < 1e-7 and fitted.delta_log_l_error < 1e-6
    before = idea.path2._signal(module, idea._candidate(cls, point, spin))
    after = idea.path2._signal(module, idea._candidate(cls, fitted.point, spin))
    assert after.total_events / before.total_events == pytest.approx(16)


def test_zero_boundary_and_unsupported_inversions():
    cls, p = Spin1Class(), Point(m_chi=10, m_med=1000, g_chi=1)
    assert invert(cls, p, 0).g_chi == 0
    assert invert(cls, p, math.sqrt(4*math.pi)).g_chi == pytest.approx(math.sqrt(4*math.pi))
    with pytest.raises(ValueError, match="outside"):
        invert(cls, p, 4)
    with pytest.raises(ValueError, match="zero reference"):
        invert(cls, p.model_copy(update={"g_chi": 0}), 1)
    class Degenerate:
        def interaction(self, point):
            return cls.interaction(p)
    with pytest.raises(ValueError, match="unique"):
        invert(Degenerate(), p, 1)


def row(omega, status, converged=False):
    return idea.BandPoint(m_chi=10, s_hat=2, events_at_unit=1, mu_hat=1, mu_68=(.5, 2), z_local=2,
                          omega_h2=omega, status=status, converged=converged, target=.12,
                          relative_residual=0 if converged else None)


def test_thermal_headline_is_separate_from_fitted_band_compatibility():
    band = [row(10, "viable")]
    assert idea._level(band, [row(.12, "excluded", True)], True)[0] == "excluded"
    assert idea._level(band, [], True)[0] == "no_thermal"
    assert idea._level(band, [], True, ["root failed"])[0] == "undetermined"
    assert idea._level(band, [row(.12, "viable", True)], True)[0] == "viable"
    assert idea._level(band, [row(.12, "pending", True)], True)[0] == "viable_pending"
    assert idea._level(band, [row(.12, "viable")], True)[0] != "viable"


def test_thermal_search_never_bridges_a_failed_mass():
    p = Point(m_chi=10, m_med=1000)
    a = row(.06, "viable").model_copy(update={"point": p})
    b = row(None, "pending").model_copy(update={"m_chi": 20})
    c = row(.24, "viable").model_copy(update={"m_chi": 30, "point": p})
    roots, pending = idea._thermal(Spin1Class(), p, [a,b,c], .12, None, .5)
    assert not roots and pending

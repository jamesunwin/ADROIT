"""The oblique parameters S and T at one loop (``constraints.oblique``, Grimus et al. arXiv:0802.4353)."""
import math

import pytest

from adroit.constraints import oblique as ob


def test_g_hat_matches_the_papers_figure_and_its_asymptotic_form():
    """Ĝ(m², m_Z²) (eq. (C5)): about −5.4 at 80 GeV and through zero near 280 GeV (Fig. 5); for m ≫ m_Z,
    −5/3 + ln(1/ε) − 17ε/2 with ε = m_Z²/m² (eq. (C11))."""
    q = ob.M_Z ** 2
    assert ob.big_g_hat(80.0 ** 2, q) == pytest.approx(-5.39, abs=0.02)
    assert ob.big_g_hat(270.0 ** 2, q) < 0 < ob.big_g_hat(290.0 ** 2, q)
    eps = q / 2000.0 ** 2
    assert ob.big_g_hat(2000.0 ** 2, q) == pytest.approx(-5 / 3 + math.log(1 / eps) - 8.5 * eps, abs=1e-3)


@pytest.mark.parametrize("masses", [(65.0, 100.0, 120.0), (500.0, 520.0, 560.0), (990.0, 992.36, 998.12)])
def test_the_inert_doublets_t_is_the_closed_form(masses):
    h0, a0, hc = masses
    closed = (ob.big_f(hc ** 2, h0 ** 2) + ob.big_f(hc ** 2, a0 ** 2) - ob.big_f(h0 ** 2, a0 ** 2)) / (
        16 * math.pi * ob.S_W2 * ob.M_W ** 2)
    assert ob.inert_doublet(*masses)[1] == pytest.approx(closed, rel=1e-12)


@pytest.mark.parametrize("masses, tolerance", [((1000.0, 1300.0, 1100.0), 0.02), ((2000.0, 2600.0, 2300.0), 0.03)])
def test_the_inert_doublets_s_approaches_its_zero_momentum_form_for_heavy_scalars(masses, tolerance):
    """S at Q = m_Z² against Barbieri, Hall & Rychkov's q² → 0 form: they agree up to O(m_Z²/m²)."""
    x, y, c = (m * m for m in masses)
    zero = (math.log(x / c) / 6 - 5 / 36 + x * y / (3 * (y - x) ** 2)
            + y * y * (y - 3 * x) / (6 * (y - x) ** 3) * math.log(y / x)) / (2 * math.pi)
    assert ob.inert_doublet(*masses)[0] == pytest.approx(zero, rel=tolerance)


def test_degenerate_and_custodial_scalars_leave_t_zero():
    s, t = ob.inert_doublet(1000.0, 1000.0, 1000.0)
    assert t == 0.0 and abs(s) < 1e-4
    assert ob.two_hdm_a(1000.0, 1000.0, 400.0, 1000.0, 0.35)[1] == pytest.approx(0.0, abs=1e-12)   # m_H = m_H±
    assert ob.two_hdm_a(1000.0, 1000.0, 400.0, 800.0, 0.35)[1] > 0.3                             # split: large T


@pytest.mark.parametrize("masses, s_ref, t_ref", [
    ((1e6, 1e6 + 0.001, 1e6 + 0.002), -1.0840118390066899e-10, 3.681538804537593e-11),
    ((1e4, 1e4 + 1e-5, 1e4 + 2e-5), -2.883184138571448e-07, 3.681538804537593e-15),
    ((100.0, 10000.0, 100.0), 0.2214906698714715, 0.0)])
def test_heavy_near_degenerate_and_widely_split_scalars_keep_their_digits(masses, s_ref, t_ref):
    """The tactical audit's T20-08: in double precision the first gave S = 0.227, T = −0.528 (χ² = 1170 for the
    decoupled 3.78) and the third an S 3% low. References: the same closed forms at 80 digits (the audit's control)."""
    s, t = ob.inert_doublet(*masses)
    assert s == pytest.approx(s_ref, rel=1e-6) and t == pytest.approx(t_ref, rel=1e-6, abs=1e-20)


@pytest.mark.needs("ufo_models")
def test_a_decoupled_inert_doublet_is_not_excluded_by_electroweak_precision():
    from adroit.parameter_space import library, searches
    e = library.entry("inert_doublet")
    p = e.point.model_copy(update=dict(m_chi=1e6, m_med=1e6 + 0.002, g_q=0.001, g_chi=0.1))
    assert searches.electroweak_precision(e.model_class, p, True).excluded is False

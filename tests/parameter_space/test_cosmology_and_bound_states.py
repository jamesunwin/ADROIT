"""BBN and N_eff, CCFR, the wino's bound state, and the UFO engine's off-shell and resonant channels."""

import numpy as np
import pytest

from adroit.constraints import searches as s
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals import multiplet as mp
from adroit.parameter_space.portals.vector import ChargedZPrime, DarkPhoton

needs_ccfr = pytest.mark.skipif(s._tool("CCFR trident (digitised)") is None, reason="CCFR's digitisation not fetched")


def test_a_thermalised_light_vector_is_bounded_by_bbn_and_the_cmb(awaiting):
    dp, lm, bl = DarkPhoton(), ChargedZPrime(charges="Lmu-Ltau"), ChargedZPrime()
    assert ps.bbn(dp, Point(m_chi=1.0, m_med=0.005, g_q=1e-6), True).excluded is True
    assert ps.bbn(dp, Point(m_chi=1.0, m_med=0.012, g_q=1e-6), True).excluded is False
    assert ps.bbn(dp, Point(m_chi=1.0, m_med=0.005, g_q=1e-9), True).excluded is True      # freeze-in: Ibe et al.
    assert ps.bbn(dp, Point(m_chi=1.0, m_med=0.05, g_q=1e-6), True) is None               # above 20 MeV
    assert ps.bbn(lm, Point(m_chi=0.1, m_med=0.006, g_q=1e-4), True).excluded is True
    assert ps.bbn(bl, Point(m_chi=0.1, m_med=0.005, g_q=1e-5), True).excluded is True
    assert ps.bbn(bl, Point(m_chi=0.1, m_med=0.005, g_q=1e-7), True).excluded is False
    awaiting("sabti-1910.01649-bbn")                                    # while its record awaits verification
    assert "awaits" in ps.bbn(dp, Point(m_chi=1.0, m_med=0.005, g_q=1e-6), False).why


def test_a_dark_photon_near_its_thermalisation_is_flagged_good_up_to_an_o1_factor_in_epsilon():
    """ε ≈ 10⁻⁸ is a representative value (Ibe et al.): within a factor 3 of it, a verdict the other side would change
    is flagged, not made pending (the owner, 2026-10-17; the external audit's item 18)."""
    dp = DarkPhoton()
    above = ps.bbn(dp, Point(m_chi=1.0, m_med=0.009, g_q=1.2e-8), True)          # 8.5 < m < 9.8 MeV: the two differ
    below = ps.bbn(dp, Point(m_chi=1.0, m_med=0.009, g_q=8e-9), True)
    assert above.excluded is True and below.excluded is False
    assert all(any("O(1) factor in ε" in f for f in o.flags) for o in (above, below))
    far = ps.bbn(dp, Point(m_chi=1.0, m_med=0.009, g_q=5e-8), True)               # beyond a factor 3
    agree = ps.bbn(dp, Point(m_chi=1.0, m_med=0.005, g_q=1.2e-8), True)          # both exclude at 5 MeV
    assert far.excluded is True and not far.flags and agree.excluded is True and not agree.flags


@needs_ccfr
def test_ccfr_bounds_l_mu_minus_l_tau_with_its_heavy_limit_above_the_digitised_curve(awaiting):
    lm = ChargedZPrime(charges="Lmu-Ltau")
    excluded, ratio = ps._ccfr(Point(m_chi=7.0, m_med=20.0, g_q=0.05), True)
    assert excluded and ratio > 1
    assert ps._ccfr(Point(m_chi=7.0, m_med=20.0, g_q=0.01), True)[0] is False
    heavy = ps._ccfr(Point(m_chi=300.0, m_med=1000.0, g_q=2.0), True)                    # M/g = 500 < 567 GeV
    assert heavy[0] is True and heavy[1] == pytest.approx((2.0 / (1000 / 567)) ** 2)
    awaiting("ccfr-1406.2332-trident")
    assert ps._ccfr(Point(m_chi=7.0, m_med=20.0, g_q=0.05), False) is None              # while unverified
    out = ps.lmu_ltau(lm, Point(m_chi=7.0, m_med=20.0, g_q=0.05, g_chi=0.05), True)
    assert next(o for o in out if o.name == ps.LMU).excluded is True
    assert next(o for o in out if "BaBar/Belle" in o.name).excluded is None  # native 90%, separate from CCFR


def test_the_wino_bound_state_exists_only_above_its_critical_mass_and_below_t_c():
    t = np.array([2900.0 / 30, 2900.0 / 1000])
    assert np.all(mp.wino_bound_rate(1500.0, t) == 0.0)                                  # below ≈ 2.0 TeV: unbound
    rate = mp.wino_bound_rate(2900.0, np.array([300.0, 2900.0 / 1000]))
    assert rate[0] == 0.0 and rate[1] > 0.0                                               # above T_c: none
    se = mp.effective_rate("wino", 2900.0, 0.165, t, True)
    assert np.all(mp.wino_bound_rate(2900.0, t) < 0.3 * se)                               # a correction


def test_off_shell_w_and_z_are_integrated_over_their_breit_wigner():
    from adroit.constraints import tree
    from adroit.parameter_space.portals import ufo
    m = tree.Model({})
    m.add(tree.Particle("S", 0, 70.0), tree.Particle("W+", 1, 80.4, width=2.1, anti="W-", pdg=24, charge=1.0))
    m.vertices.append(tree.Vertex("VVSS", ("W+", "W-", "S", "S"), 0.4))
    proc = tree.Process(m, "S", "S", "W+", "W-", points=8)
    below = 2 * 70.0 * 1.02
    assert proc.sigma(below ** 2) == 0.0 and ufo.off_shell_sigma(proc, below ** 2) > 0.0       # W W* below 2 m_W
    far = 400.0
    assert ufo.off_shell_sigma(proc, far ** 2) == pytest.approx(proc.sigma(far ** 2))         # on shell far above

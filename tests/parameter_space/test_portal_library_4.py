"""The portal library, part 4: loop-level direct detection in the portals, γ-ray lines and antiprotons."""

import math

import pytest

from adroit.constraints import searches as s
from adroit.parameter_space import operator_limits, searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.library import TWO_HDM_A
from adroit.parameter_space.portals import multiplet
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.physics import conventions


# --- direct detection at loop level --------------------------------------------------------------

def test_a_majorana_coloured_partner_scatters_spin_independently():
    tc = TChannel(name="t", partner="uR", majorana=True)
    n = tc.nucleon(Point(m_chi=300.0, m_med=360.0, g_chi=1.0))
    assert conventions.sigma_si_cm2(n.c1_p, 300.0) == pytest.approx(3.65e-44, rel=0.02)
    assert n.c4_p != 0
    pending=tc.pending(Point(m_chi=300.0, m_med=360.0, g_chi=1.0))
    assert pending and all("coannihilation chemical equilibrium" in reason for reason in pending)
    # Near degeneracy the uncertainty is quantified (``test_dd_channels``); only where the expansion fails is it flagged.
    assert not any("on shell" in f for f in tc.flags(Point(m_chi=300.0, m_med=305.0, g_chi=1.0)))
    assert any("on shell" in f for f in tc.flags(Point(m_chi=300.0, m_med=300.5, g_chi=1.0)))


def test_a_dirac_coloured_partner_adds_twist_two_to_its_vector_coupling():
    tc = TChannel(name="t", partner="uR", majorana=False)
    p = Point(m_chi=500.0, m_med=600.0, g_chi=1.0)
    g = 1.0 / (8.0 * (600.0 ** 2 - 500.0 ** 2))
    assert tc.nucleon(p).c1_p > 2.0 * g


def test_a_majorana_lepton_partner_scatters_through_its_anapole():
    tc = TChannel(name="l", partner="muR", majorana=True)
    n = tc.nucleon(Point(m_chi=100.0, m_med=100.0 * math.sqrt(1.1), g_chi=1.0))
    assert n.structure == "anapole" and n.scale == pytest.approx(5.53e-6, rel=0.01)
    assert tc.dd(Point(m_chi=100.0, m_med=110.0, g_chi=1.0))[0] == "anapole"
    pending=tc.pending(Point(m_chi=300.0, m_med=400.0, g_chi=1.0))
    assert pending and all("coannihilation chemical equilibrium" in reason for reason in pending)


def test_a_dirac_lepton_partner_scatters_on_protons_through_its_charge_radius():
    tc = TChannel(name="l", partner="muR", majorana=False)
    n = tc.nucleon(Point(m_chi=100.0, m_med=110.0, g_chi=1.0))
    assert n.c1_n == 0.0 and abs(n.c1_p) == pytest.approx(0.3028 * 0.3028 * (5.16e-6 + 3.54e-5 / 200.0), rel=0.02)
    assert any("lower bound" in t for t in tc.pending(Point(m_chi=300.0, m_med=400.0, g_chi=1.0)))


@pytest.mark.needs("diamx")
def test_the_higgsino_and_the_2hdma_scatter_through_loops():
    h = ElectroweakMultiplet(name="h", multiplet="higgsino")
    assert h.dd(Point(m_chi=1100.0, m_med=1.0, g_q=0.0)) == ("SI", pytest.approx(7.4e-50, rel=1e-6))
    kind, sigma = TWO_HDM_A.dd(Point(m_chi=100.0, m_med=250.0, g_chi=1.0, g_q=0.35, g_l=1.0))
    assert kind == "SI" and 1e-48 < sigma < 1e-47                # heavy states at 1 TeV: below the 600 GeV benchmark


def test_the_anapole_structure_is_the_library_card_and_its_ratio_scales_quadratically(monkeypatch):
    coefficients = {c.operator: c for c in operator_limits.anapole(100.0).coefficients}
    assert coefficients[8].proton == pytest.approx(2 * 0.30282, rel=1e-3) and coefficients[8].neutron == 0.0
    assert coefficients[9].proton / coefficients[8].proton == pytest.approx(2.7928, rel=1e-3)
    table = {"masses_gev": [10.0, 100.0, 1000.0], "mu_up": [1e-6, 1e-7, 1e-6]}
    monkeypatch.setattr(operator_limits, "table", lambda name: table)
    assert operator_limits.mu_limit("anapole", 100.0) == pytest.approx(1e-7)
    assert operator_limits.ratio("anapole", 100.0, 2e-7) == pytest.approx(4.0)
    assert operator_limits.ratio("anapole", 5000.0, 2e-7) is None


# --- γ-ray lines ------------------------------------------------------------------------------------

def test_the_hess_reference_line_matches_the_tree_level_sommerfeld_calculation():
    """The cross-check of DMγSpec's default (D21): the curves H.E.S.S. compares with."""
    assert multiplet.wino_line(2900.0, 0.165) == pytest.approx(5.96e-26, rel=0.05)    # the survey's 5.75e-26
    w = ElectroweakMultiplet(name="w", multiplet="wino")
    rates = w.hess_reference_line(Point(m_chi=2900.0, m_med=1.0, g_q=0.0))
    line = rates["gamma"] + 0.5 * rates["Zgamma"]
    assert line == pytest.approx(3.23e-26, rel=0.1)                   # Baumgart et al.'s NLL, H.E.S.S.'s curve
    assert rates["Zgamma"] / rates["gamma"] == pytest.approx(2 * multiplet.CW2 / multiplet.SW2)


def test_the_default_line_is_dmyspecs_and_falls_back_to_the_reference(monkeypatch):
    from adroit.constraints import resummed_lines
    w = ElectroweakMultiplet(name="w", multiplet="wino")
    p = Point(m_chi=2900.0, m_med=1.0, g_q=0.0)
    if resummed_lines.available():
        assert w.line_sigma_v(p) == {"gamma": pytest.approx(resummed_lines.line_sigma_v("wino", 2900.0))}
        far = Point(m_chi=2900.0, m_med=1.0, g_q=0.5)                 # a splitting DMγSpec's tables do not hold
        assert w.line_sigma_v(far) == w.hess_reference_line(far)
    monkeypatch.setattr(resummed_lines, "available", lambda: False)
    assert w.line_sigma_v(p) == w.hess_reference_line(p)


def test_hess_excludes_the_thermal_wino_but_not_the_thermal_higgsino(awaiting, monkeypatch):
    from adroit.constraints import resummed_lines
    if resummed_lines.available():                                  # DMγSpec's NLO potential: 1.7 × the reference
        wino = ps.lines(ElectroweakMultiplet(name="w", multiplet="wino"), Point(m_chi=2900.0, m_med=1.0, g_q=0.0), True)
        assert wino.excluded is True and wino.ratio == pytest.approx(14.4, rel=0.05)
    monkeypatch.setattr(resummed_lines, "available", lambda: False)
    wino = ps.lines(ElectroweakMultiplet(name="w", multiplet="wino"), Point(m_chi=2900.0, m_med=1.0, g_q=0.0), True)
    assert wino.excluded is True and wino.ratio == pytest.approx(8.4, rel=0.15)     # the cored profile
    hino = ps.lines(ElectroweakMultiplet(name="h", multiplet="higgsino"), Point(m_chi=1100.0, m_med=1.0, g_q=0.0), True)
    assert hino.excluded is False and 0.05 < hino.ratio < 0.3
    awaiting("hess-1805.05741-lines", "hess-2608.07234-lines", "fermi-lat-1506.00013-lines")   # all held unverified
    blocked = ps.lines(ElectroweakMultiplet(name="w", multiplet="wino"), Point(m_chi=2900.0, m_med=1.0, g_q=0.0), False)
    assert blocked.excluded is None and "verification" in blocked.why


def test_fermi_resolves_the_z_gamma_line():
    curve = s._bundled("fermi-lat-1506.00013-lines")["limit"]
    m = 150.0
    energy = m - ps.M_Z ** 2 / (4 * m)
    expected = 1e-28 / (2 * (m / energy) ** 2 * s.interpolate(curve, energy))
    assert ps._line_ratio("fermi-lat-1506.00013-lines", 0.0, 1e-28, m) == pytest.approx(expected)
    assert ps._line_ratio("hess-2608.07234-lines", 1e-28, 2e-28, 1000.0) == pytest.approx(
        2e-28 / s.interpolate(s._bundled("hess-2608.07234-lines")["limit"], 1000.0))


# --- antiprotons ------------------------------------------------------------------------------------

class _Annihilating:
    def __init__(self, rates: dict, majorana: bool = True):
        self.rates, self.majorana = rates, majorana

    def self_conjugate(self) -> bool:
        return self.majorana

    def sigma_v_today(self, p, v):
        return self.rates


def test_antiprotons_require_pure_channels_and_halve_a_dirac_pair(monkeypatch):
    from adroit.constraints import propagation
    monkeypatch.setattr(propagation, "chosen", lambda: "central")      # the paper's fiducial curves, as tabulated
    p = Point(m_chi=100.0, m_med=1.0)
    limits = s._bundled("calore-2202.03076-pbar")["limits"]
    bb = s.interpolate(limits["bb"], 100.0)
    out = ps.antiprotons(_Annihilating({"b": 3e-26, "W": 3e-26, "tau": 1e-25}), p, True)
    assert out.ratio is None and out.excluded is None
    dirac = ps.antiprotons(_Annihilating({"b": 3e-26}, majorana=False), p, True)
    assert dirac.ratio == pytest.approx(0.5 * 3e-26 / bb)
    assert ps.antiprotons(_Annihilating({"b": 1e-24}), p, True).excluded is True
    assert ps.antiprotons(_Annihilating({"tau": 1e-24}), p, True).excluded is None
    light = Point(m_chi=60.0, m_med=1.0)                    # off-shell/mixed spectra require a recast
    assert ps.antiprotons(_Annihilating({"W": 3e-26, "mu": 1e-24}), light, True).excluded is None
    assert ps.antiprotons(_Annihilating({"b": 3e-26}), Point(m_chi=5.0, m_med=1.0), True) is None   # below 10 GeV


@pytest.mark.skipif(s._injection_table() is None, reason="Slatyer's f_eff tables are not in the tools folder")
def test_the_cmb_below_5_gev_uses_injected_electrons_photons_and_muons():
    f = s.f_eff_low_mass(1.0)
    assert set(f) >= {"e+e-", "gammagamma", "mu+mu-"}
    assert s.muon_f_eff(1.0) == pytest.approx(0.186, abs=0.004)       # Slatyer's notebook: 0.1843
    assert s.muon_f_eff(3.0) == pytest.approx(0.162, abs=0.004)

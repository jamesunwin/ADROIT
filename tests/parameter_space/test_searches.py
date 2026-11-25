"""The portal library's searches and the CMB (constraints.searches, parameter_space.searches)."""

import math

import numpy as np
import pytest

from adroit.constraints import searches as s
from adroit.parameter_space import library
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.parameter_space.portals.vector import ChargedZPrime, DarkPhoton
from adroit.parameter_space.scan import evaluate

needs_darkcast = pytest.mark.skipif(s._tool("DarkCast") is None, reason="DarkCast is not in the tools folder")
needs_feff = pytest.mark.skipif(s._tool("Slatyer f_eff") is None, reason="Slatyer's f_eff is not in the tools folder")


def test_muon_g2_formulas_have_their_known_limits():
    assert s.muon_g2_vector(4.5e-4, 1e-6) == pytest.approx(4.5e-4 ** 2 / (8 * math.pi ** 2), rel=1e-3)
    heavy = s.muon_g2_scalar_partner(1.0, 1000.0, 1e-3)              # m_χ → 0: −y² m_μ²/(96π² m_φ²)
    assert heavy == pytest.approx(-s.M_MU ** 2 / (96 * math.pi ** 2 * 1e6), rel=1e-3)
    equal = s.muon_g2_scalar_partner(1.0, 1000.0, 1000.0)            # m_χ = m_φ: half of that
    assert equal == pytest.approx(heavy / 2, rel=1e-3)


def test_b_to_k_a_matches_dolan_et_al():
    data = s._record("flavour-b-to-k-invisible").data
    per_g2 = s.b_to_k_pseudoscalar(1e-3, 1.0, data["h_s_per_g_y"], data["f0"], data["f0_pole_gev2"],
                                   data["mb_minus_ms_gev"])
    assert 15 < per_g2 < 25                                          # "BR(B → K a) ∼ 20 g_Y²"
    assert s.b_to_k_pseudoscalar(5.0, 1.0, 2.3e-5, 0.33, 38.0, 4.687) == 0.0


def test_the_s_wave_part_drops_p_wave_channels():
    class Fake:
        def sigma_v_today(self, p, v):
            return {"b": 2e-26, "hh": 1e-24 * v * v}
    rates = s.s_wave(Fake(), Point(m_chi=10.0, m_med=30.0))
    assert rates == {"b": pytest.approx(2e-26, rel=1e-6, abs=0)}


@needs_feff
def test_the_cmb_brackets_an_untabulated_cascade_and_applies_where_it_can_matter(monkeypatch, awaiting):
    class Fake:
        def __init__(self, rates):
            self.rates = rates

        def sigma_v_today(self, p, v):
            return dict(self.rates)

        def self_conjugate(self):
            return True
    p = Point(m_chi=20.0, m_med=60.0)
    assert ps.cmb(Fake({"b": 1e-30}), p, True) is None                         # p_ann far below any limit
    assert ps.cmb(Fake({"b": 1e-25}), p, True).excluded is True
    assert ps.cmb(Fake({"b": 2e-27}), p, True).excluded is False
    undecided = ps.cmb(Fake({"Z'Z'": 3.2e-28 * 20 / 0.3}), p, True)
    assert undecided.excluded is None and "cascade" in undecided.why
    awaiting("planck-2018-pann")                                        # while its record awaits verification
    assert "awaits" in ps.cmb(Fake({"b": 1e-25}), p, False).why


@needs_feff
def test_the_cmb_does_not_interpolate_through_the_zeros_below_a_channels_first_tabulated_mass():
    """The owner's record review (2026-10-13): Slatyer's zeros below a threshold mean "not computed". Interpolating
    through them gave f_eff(W⁺W⁻) = 0.0189 at 81 GeV (0.1791 at 90 GeV, his first W⁺W⁻ mass), and ⟨σv⟩ = 10⁻²⁴ cm³/s
    there was allowed."""
    class Fake:
        def __init__(self, rates):
            self.rates = rates

        def sigma_v_today(self, p, v):
            return dict(self.rates)

        def self_conjugate(self):
            return True
    table, _, _ = ps._f_eff(81.0)
    assert "W+W-" not in table and "e+e-" in table                          # below 90 GeV: not tabulated
    assert ps._f_eff(95.0)[0]["W+W-"] == pytest.approx(0.1784, abs=0.001)    # between 90 and 100 GeV
    assert {c: ps._first_tabulated(c) for c in ("bbbar", "W+W-", "Z0Z0", "hh", "ttbar")} == \
        {"bbbar": 6.0, "W+W-": 90.0, "Z0Z0": 100.0, "hh": 130.0, "ttbar": 180.0}
    near = ps.cmb(Fake({"W": 1e-24}), Point(m_chi=81.0, m_med=200.0), True)
    assert near.excluded is None and "W+W-" in near.why and "from 90 GeV" in near.why
    assert ps.cmb(Fake({"W": 1e-24}), Point(m_chi=95.0, m_med=200.0), True).excluded is True
    assert ps.cmb(Fake({"W": 2e-26}), Point(m_chi=81.0, m_med=200.0), True).excluded is False   # even with f_eff = 1


@needs_feff
def test_the_cmb_reads_a_cascades_f_eff_range_and_neutrinos_deposit_nothing(awaiting):
    """G6: a cascade with a model-supplied f_eff range decides where the range does, with no single ratio; a
    neutrino pair deposits no energy."""
    class Fake:
        def __init__(self, rates):
            self.rates = rates

        def sigma_v_today(self, p, v):
            return dict(self.rates)

        def self_conjugate(self):
            return True

        def cmb_f_eff_range(self, channel, p):
            return (0.2, 0.25) if channel == "S S" else None
    p = Point(m_chi=20.0, m_med=60.0)
    limit = s._record("planck-2018-pann").data["p_ann_cm3_s_gev"]
    high = ps.cmb(Fake({"S S": 1.5 * limit * 20 / 0.2}), p, True)
    assert high.excluded is True and high.ratio is None and high.value == pytest.approx(1.5)
    low = ps.cmb(Fake({"S S": 0.5 * limit * 20 / 0.25}), p, True)
    assert low.excluded is False and low.ratio is None
    assert ps.cmb(Fake({"S S": limit * 20 / 0.22}), p, True).excluded is None             # inside the range
    assert ps.cmb(Fake({"nu_mu": 1e-22}), p, True) is None                                # neutrinos: nothing


def test_the_squark_contour_decides_nothing_with_qcd_production_alone():
    """Decision D33 (the external audit's R20): the contour assumes QCD pair production, and the t-channel
    interference, of unestablished sign, could lower the partner's: inside the contour is pending, not excluded."""
    t = TChannel(partner="uR")
    inside = ps.partner(t, Point(m_chi=100.0, m_med=900.0, g_chi=1.0), True)
    assert inside.excluded is None and inside.why.startswith("inside") and "not a lower bound" in inside.why
    outside = ps.partner(t, Point(m_chi=600.0, m_med=900.0, g_chi=1.0), True)
    assert outside.excluded is None and "QCD alone" in outside.why     # χ exchange adds production: not "allowed"
    assert ps.partner(t, Point(m_chi=100.0, m_med=1500.0, g_chi=1.0), True).excluded is None      # beyond: likewise
    assert ps.partner(t, Point(m_chi=100.0, m_med=300.0, g_chi=1.0), True).excluded is None
    assert ps.partner(TChannel(partner="muR"), Point(m_chi=100.0, m_med=300.0, g_chi=1.0), True) is None
    assert ps.muon_g2(TChannel(partner="muR"), Point(m_chi=100.0, m_med=300.0, g_chi=1.0), True).name == ps.G2


def test_b_minus_l_meets_lep_and_the_lhc():
    model = ChargedZPrime()
    strong, weak = Point(m_chi=1000.0, m_med=3000.0, g_q=0.1, g_chi=0.03), Point(m_chi=1000.0, m_med=3000.0, g_q=0.003,
                                                                                    g_chi=0.001)
    lep, lhc = ps.dilepton(model, strong, True)
    assert lep.excluded is False and lhc.excluded is True          # M/g = 30 TeV passes LEP, fails ATLAS
    assert all(o.excluded is False for o in ps.dilepton(model, weak, True))
    assert ps.dilepton(model, Point(m_chi=100.0, m_med=150.0, g_q=0.1), True) is None


@needs_darkcast
def test_dark_photon_searches_use_visible_or_invisible_limits():
    dp = DarkPhoton()
    visible = Point(m_chi=5.0, m_med=0.3, g_chi=0.1, g_q=1e-3)        # A′ → χχ̄ closed
    assert ps.dark_photon(dp, visible, True).native_excluded is True        # BaBar and beam dumps at ε = 10⁻³
    assert ps.dark_photon(dp, visible, True).excluded is None  # LHCb prompt excludes at 90%: pending at 95%
    invisible = Point(m_chi=1.0, m_med=3.0, g_chi=0.5, g_q=2e-3)
    assert ps._dark_photon_branching(dp, invisible) > 0.99
    assert ps.dark_photon(dp, invisible, True).native_excluded is True      # BaBar invisible (2017)
    # allowed only where every search covering the mass applies (the owner, 2026-10-13): below LHCb's 0.214 GeV
    assert ps.dark_photon(dp, Point(m_chi=0.03, m_med=0.1, g_chi=0.01, g_q=1e-6), True).native_excluded is False
    narrow = ps.dark_photon(dp, Point(m_chi=1.0, m_med=3.0, g_chi=0.05, g_q=1e-5), True)   # Γ = 0.18 MeV
    assert narrow.excluded is False                     # below LHCb's 3.6 MeV (0.12% of m) and BaBar's 1.5 MeV
    broad = ps.dark_photon(dp, Point(m_chi=1.0, m_med=3.0, g_chi=0.5, g_q=1e-5), True)     # Γ = 18 MeV
    assert broad.excluded is None and "LHCb 2019 prompt: Γ = 18.1 MeV is not below its mass resolution" in broad.why
    heavy = ps.dark_photon(dp, Point(m_chi=100.0, m_med=500.0), True)      # R4 (M14): pending, not silent
    assert heavy.excluded is None and "not yet records" in heavy.why


def test_the_inert_doublet_at_lep_and_the_g2_window():
    class Fake:
        searches = ["lep_inert_doublet"]
        dm, partners = "H0", ["A0", "H+"]

        def __init__(self, masses):
            self.masses = masses

        def model(self, p):
            from adroit.constraints import tree
            return tree.Model({n: tree.Particle(n, 0, m) for n, m in zip(("H0", "A0", "H+"), self.masses)})
    assert ps.inert_doublet(Fake((60.0, 90.0, 150.0)), Point(m_chi=1.0, m_med=1.0), True).excluded is True     # the neutralino recast
    assert ps.inert_doublet(Fake((70.0, 75.0, 150.0)), Point(m_chi=1.0, m_med=1.0), True).excluded is False    # Δm < 8 GeV
    assert ps.inert_doublet(Fake((40.0, 45.0, 150.0)), Point(m_chi=1.0, m_med=1.0), True).excluded is True     # Z → H₀A₀
    assert ps.inert_doublet(Fake((100.0, 110.0, 60.0)), Point(m_chi=1.0, m_med=1.0), True).excluded is True    # m_H± < 70 GeV
    assert ps._g2(ps.G2, 1e-9, True).excluded is False and ps._g2(ps.G2, 3e-9, True).excluded is True


@pytest.mark.needs("diamx", "solar_model")
def test_a_scan_point_records_each_search_and_its_reason(awaiting):
    awaiting("atlas-1903.06248-dilepton")
    e = library.entry("b_minus_l")
    r = evaluate(e.model_class, e.point, unverified=False)
    assert r.excluded[ps.DILEPTON] is None and any("awaits a person's verification" in x for x in r.pending)
    r = evaluate(e.model_class, e.point, unverified=True)
    assert r.excluded[ps.DILEPTON] is True and ps.DILEPTON in r.values


def test_the_bundled_tables_hold_what_their_records_say():
    table = s._bundled("atlas-1903.06248-dilepton")
    rows = np.array([[np.nan if v is None else v for v in r] for r in table["rows"]], dtype=float)
    assert rows[0, 0] == 250.0 and rows[0, 1] == pytest.approx(3.57303) and rows[0, 6] == pytest.approx(13.0839)
    ratio = rows[:, 9] / rows[:, 8]                                      # ATLAS's fiducial SSM over our LO SSM
    above = (rows[:, 0] >= 1000.0) & (rows[:, 0] <= 5000.0) & ~np.isnan(ratio)
    assert 0.75 < np.min(ratio[above]) and np.max(ratio[above]) < 1.35      # noisy sampling; the median is used
    assert table["correction_fid_over_lo"] == pytest.approx(float(np.median(ratio[above])), rel=1e-3)
    assert s._bundled("atlas-2010.14293-squark")["points"][0] == [1220.0, 0.0]
    assert s.interpolate(s._bundled("lmu-ltau-babar-belle2")["points"], 0.01) == pytest.approx(0.002628)



def test_the_axial_muon_g2_has_its_known_limits():
    """``muon_g2_axial`` (P4, 2026-10-20): a heavy axial vector gives −5g²m_μ²/(12π²M²), a heavy vector +g²m_μ²/(12π²M²);
    a light axial vector's grows as 1/M² and stays negative."""
    heavy = 1000.0
    assert s.muon_g2_axial(1.0, heavy) == pytest.approx(-5 * s.M_MU ** 2 / (12 * math.pi ** 2 * heavy ** 2), rel=1e-3)
    assert s.muon_g2_vector(1.0, heavy) == pytest.approx(s.M_MU ** 2 / (12 * math.pi ** 2 * heavy ** 2), rel=1e-3)
    light = s.muon_g2_axial(1e-3, 0.01)
    assert light < 0 and abs(light) > abs(s.muon_g2_axial(1e-3, 0.1)) * 50

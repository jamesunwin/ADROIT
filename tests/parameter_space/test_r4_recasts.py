"""R4: collider recasts and record application (audit M2, M3, M14, M15, M16 and the searches-and-records minors)."""

import math
from types import SimpleNamespace

import pytest

from adroit.constraints import searches as s
from adroit.parameter_space import resonances as rs
from adroit.parameter_space import searches
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class
from adroit.parameter_space.library import TWO_HDM_A


def _masses(**values):
    return SimpleNamespace(particles={k: SimpleNamespace(mass=v) for k, v in values.items()})


@pytest.mark.parametrize("r,expected", [(0.945, None), (1.3, True), (0.3, False), (1.1, None), (0.45, None)])
def test_mono_h_decides_only_outside_the_resonant_to_full_band(monkeypatch, r, expected) -> None:
    """M2: our resonant σ is 0.419–1.240 of ATLAS's full benchmark σ, so r between them decides nothing."""
    cls, p = rs._reference(TWO_HDM_A, 0.35, 1000.0), Point(m_chi=10.0, m_med=500.0, g_chi=1.0, g_q=0.35, g_l=1.0)
    monkeypatch.setattr(type(cls), "model", lambda self, point: _masses(h4=500.0, h3=1000.0))
    monkeypatch.setattr(rs, "_relative_width", lambda model, name: 0.05)
    limit = math.exp(float(rs._sigma95_interpolator()(1000.0, 500.0)))
    monkeypatch.setattr(rs, "_resonant_rates", lambda cls, point: {"h": r * limit / 1e3})
    out = rs.monoh(cls, p, True)
    assert out.excluded is expected
    assert rs.RESONANT_OVER_FULL == (0.4189, 1.2400)


@pytest.mark.slow
@pytest.mark.skipif(not __import__("adroit.constraints.maddm", fromlist=["available"]).available(),
                    reason="MadGraph's Python is needed to read UFO files")
def test_the_audits_mono_h_point_is_no_longer_allowed() -> None:
    cls = rs._reference(TWO_HDM_A, 0.35, 1000.0)
    out = rs.monoh(cls, Point(m_chi=10.0, m_med=500.0, g_chi=1.0, g_q=0.35, g_l=1.0), True)
    assert out.excluded is None and "band" in out.why            # was r = 0.945, "allowed"; ATLAS excludes there


@pytest.mark.parametrize("m_a,m_heavy,excluded", [(520, 800, False), (540, 850, False), (555, 1000, False),
                                                  (500, 600, True), (500, 1000, True), (500, 1500, False)])
def test_the_folded_2hdma_contour_is_read_as_a_polygon(m_a, m_heavy, excluded) -> None:
    """M3: at m_a = 500 GeV the contour crosses m_A = 736.5, 870.6 and 1361.2 GeV."""
    cls = rs._reference(TWO_HDM_A, 0.35, float(m_heavy))
    out = searches.two_hdma(cls, Point(m_chi=10.0, m_med=float(m_a), g_chi=1.0, g_q=0.35, g_l=1.0), True)
    assert out.excluded is excluded


def test_b_to_k_is_not_applied_beyond_babars_signal_region() -> None:
    """M15: BaBar's 3.7e-5 holds for s_B < 0.3, m_a < 2.89 GeV."""
    cls = ScalarClass(dm_pseudoscalar=True, sm_pseudoscalar=True)
    out = searches.flavour(cls, Point(m_chi=1.0, m_med=3.5, g_chi=1.0, g_q=1.0), True)
    assert out.excluded is None and "s_B" in out.why


def test_a_dark_photon_above_200_gev_is_pending_not_silent() -> None:
    """M14."""
    from adroit.parameter_space.library import entry
    e = entry("dark_photon_dirac")
    out = searches.dark_photon(e.model_class, e.point.model_copy(update={"m_med": 500.0, "m_chi": 200.0}), True)
    assert out is not None and out.excluded is None and "not yet records" in out.why


@pytest.mark.usefixtures("resigned")
def test_a_stale_cms_signature_decides_nothing(monkeypatch) -> None:
    """M16: Track 1 routes the CMS spin-1 records through the verification gate."""
    from adroit.constraints import review_identity
    from adroit.constraints.spin1 import Spin1Kind
    from adroit.parameter_space import scan
    cls, p = Spin1Class(kind=Spin1Kind.vector, name="V1"), Point(m_chi=100.0, m_med=1000.0, g_chi=1.0, g_q=0.25)
    assert scan._collider(cls, p).excluded is True
    original = review_identity.signature_status
    monkeypatch.setattr(review_identity, "signature_status",
                        lambda record: original(record).model_copy(update={"usable": False}))
    blocked = scan._collider(cls, p)
    assert blocked.excluded is None and "verification" in blocked.needed_calculation
    assert scan._collider(cls, p, unverified=True).excluded is True


def test_smodels_does_not_apply_narrow_maps_to_a_broad_mediator(monkeypatch) -> None:
    from adroit.constraints.spin1 import Spin1Kind
    cls = Spin1Class(kind=Spin1Kind.vector, name="V1")
    broad = Point(m_chi=100.0, m_med=2000.0, g_chi=3.0, g_q=1.0)
    assert searches._broadest_mediator(cls, broad) > searches.SMODELS_NARROW
    monkeypatch.setattr(searches, "lhc_spectrum", lambda cls, p: ("slha", 1.0))
    out = searches.lhc_search(cls, broad, True, prefetched={"r_max": 3.4})
    assert out.excluded is None and "broad" in out.why
    narrow = Point(m_chi=100.0, m_med=2000.0, g_chi=0.1, g_q=0.1)
    assert searches._broadest_mediator(cls, narrow) < searches.SMODELS_NARROW


def test_the_cms_dijet_data_are_counted_once() -> None:
    from adroit.parameter_space import scan
    found = [s.Outcome(name=searches.LHC, excluded=False, ratio=0.5, why="CMS-EXO-19-012")]
    ratios = {rs.DIJET: 0.4, searches.LHC: 0.5}
    scan._same_data(found, ratios)
    assert searches.LHC not in ratios and rs.DIJET in ratios


def test_a_missing_production_cross_section_is_pending_not_silent(monkeypatch) -> None:
    from adroit.constraints.spin1 import Spin1Kind
    from adroit.constraints import production
    monkeypatch.setattr(production, "sigma_pb", lambda table, mass: None)
    spectrum = searches.mediator_spectrum(Spin1Class(kind=Spin1Kind.vector, name="V1"),
                                          Point(m_chi=100.0, m_med=1000.0, g_chi=1.0, g_q=0.25))
    assert spectrum == ("", None)


@pytest.mark.skipif(searches.production_unavailable(*searches.VECTOR_TABLES.values()) != "",
                    reason="the Z′ production tables are not in the tools folder")
def test_a_broad_zprime_below_1_5_tev_is_pending(monkeypatch) -> None:
    from adroit.constraints.spin1 import Spin1Kind
    cls = Spin1Class(kind=Spin1Kind.vector, name="V1")
    p = Point(m_chi=100.0, m_med=1000.0, g_chi=0.5, g_q=0.45)            # Γ/m ≈ 10.3%: not narrow, not wider than 12%
    out = rs.dijet(cls, p, True)
    assert out is not None and out.excluded is None and "1.5 TeV" in out.why


def test_the_mono_z_contour_closes_on_the_planes_edge() -> None:
    contour = s._bundled("atlas-2111.08372-monoz")["contours"]["0.35"]
    assert not rs._inside(contour, 102.0, 800.0) and rs._inside(rs.closed_on_edge(contour), 102.0, 800.0)
    assert not rs._covered(contour, 150.0, 1500.0)


def test_lep_contact_starts_well_above_lep_energies() -> None:
    from adroit.parameter_space.library import entry
    e = entry("b_minus_l")
    near = searches.dilepton(e.model_class, e.point.model_copy(update={"m_med": 250.0}), True)
    contact = next(o for o in near if o.name == searches.LEP_CONTACT)
    assert contact.excluded is None and "300 GeV" in contact.why


@pytest.mark.parametrize("m_med,decided", [(4400.0, True), (5000.0, False), (5900.0, False)])
def test_the_dilepton_recast_stops_at_4p5_tev(m_med, decided) -> None:
    """The owner's data audit (2026-10-12): the constant fiducial/LO correction overshoots above 4.5 TeV."""
    from adroit.parameter_space.library import entry
    e = entry("b_minus_l")
    found = searches.dilepton(e.model_class, e.point.model_copy(update={"m_med": m_med, "g_q": 0.3}), True)
    lhc = next(o for o in found if o.name == searches.DILEPTON)
    assert (lhc.excluded is not None) is decided
    if not decided:
        assert "above 4.5 TeV" in lhc.why and lhc.ratio is None


def test_the_dilepton_limit_uses_every_hepdata_mass() -> None:
    table = s._bundled("atlas-1903.06248-dilepton")
    assert {k: len(v) for k, v in table["limits_full"].items()} == {w: 1101 for w in ("0", "0.5", "1.2", "3", "6", "10")}


def test_indirect_verdicts_do_not_crash_on_line_and_antiproton_records() -> None:
    from adroit.constraints import database, spin1, verdicts
    from adroit.core.dm_state import DarkMatterParticle
    model = spin1.benchmark("V1", 1000.0)
    candidate = verdicts.Candidate(label="t", particle=DarkMatterParticle(mass_gev=100.0),
                                   interaction=spin1.interaction(model, 100.0), completion=model)
    for rid in ("fermi-lat-1506.00013-lines", "calore-2202.03076-pbar", "hess-2608.07234-lines"):
        assert verdicts.verdict(candidate, database.record(rid)).excluded is None


def test_the_singlets_invisible_higgs_width_uses_its_reduced_production() -> None:
    from adroit.parameter_space.portals.higgs import SingletMixing
    cls = SingletMixing()
    p = Point(m_chi=20.0, m_med=300.0, g_chi=1.0, g_q=0.3)
    assert cls.higgs_coupling_scale(p) == pytest.approx(1 - 0.3 ** 2)


def test_the_winos_w_continuum_leaves_out_its_lines() -> None:
    from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
    wino, p = ElectroweakMultiplet(multiplet="wino", sommerfeld=True), Point(m_chi=1000.0, m_med=1.0, g_q=0.0)
    rates, total = wino.sigma_v_today(p, 1e-3), wino.sigma_v_today(p, 1e-3, with_lines=True)["W"]
    assert 0.85 < rates["W"] / total < 0.97
    assert sum(rates.values()) == pytest.approx(total)                   # the lines are kept, as their own channels
    assert rates["Zgamma"] / rates["gamma"] == pytest.approx(2 * (1 - 0.2312) / 0.2312, rel=0.02)
    assert wino.cmb_sigma_v(p)["W"] == pytest.approx(wino.sigma_v_today(p, 1e-4, with_lines=True)["W"])


def test_an_undecided_outcome_keeps_its_own_reason_at_95() -> None:
    out = s.Outcome(name="x", excluded=None, why="no recorded search covers it", confidence_level=None).at95()
    assert out.why == "no recorded search covers it"


@pytest.mark.needs("pdg_r_ratio")
def test_belle_ii_decides_a_narrow_zprime_and_leaves_a_broad_one_undecided() -> None:
    """Mini-audit regression: the width check was inverted, so Belle II never applied to a narrow Z′ and a broad
    one crashed."""
    from adroit.parameter_space.library import entry
    e = entry("lmu_minus_ltau")
    point = e.point.model_copy(update={"m_chi": 0.3, "m_med": 1.0, "g_q": 0.00241})
    narrow = searches._lmu_native(e.model_class, point.model_copy(update={"g_chi": 1.0}), True)   # Γ/m = 0.025
    assert narrow.native_excluded is True and narrow.native_ratio > 1.0      # Belle II excludes at its native 90%
    assert narrow.excluded is None                                            # and a 90% exclusion is void at 95%
    broad = searches._lmu_native(e.model_class, point.model_copy(update={"g_chi": 3.0}), True)    # Γ/m = 0.23
    assert broad.excluded is None and "recoil-mass resolution" in broad.why
    assert searches.belle2_resolution(1.0) == pytest.approx(0.03)          # 0.06 GeV² / (2 × 1 GeV): Γ/m = 3% at 1 GeV
    tight = searches._lmu_native(e.model_class, point.model_copy(update={"m_med": 4.0, "g_chi": 1.0}), True)
    assert tight.excluded is None and "recoil-mass resolution" in tight.why  # Γ/m = 2.5% at 4 GeV: not negligible


def test_a_2hdma_point_above_the_contours_reach_is_undecided() -> None:
    """Mini audit: the polygon had no upper m_A edge, so points beyond ATLAS's contour read as allowed."""
    out = searches.two_hdma(rs._reference(TWO_HDM_A, 0.35, 1800.0),
                            Point(m_chi=10.0, m_med=400.0, g_chi=1.0, g_q=0.35, g_l=1.0), True)
    assert out.excluded is None and "highest m_A" in out.why


def _thdma(m_big: float, **fixed: str):
    """The library's 2HDM+a with m_H = m_A = m_H± = m_big; sin θ and tan β follow the point's g_q and g_l."""
    heavy = {k: repr(m_big) for k in ("mh2", "mh3", "mhc")}
    return TWO_HDM_A.model_copy(update={"parameters": {**TWO_HDM_A.parameters, **heavy, **fixed}})


def _monoh(monkeypatch, cls, p, m_big, m_a, r):
    """rs.monoh with A narrow and the resonant rate r times ATLAS's limit at (m_A, m_a)."""
    monkeypatch.setattr(type(cls), "model", lambda self, point: _masses(h4=m_a, h3=m_big))
    monkeypatch.setattr(rs, "_relative_width", lambda model, name: 0.05)
    limit = math.exp(float(rs._sigma95_interpolator()(m_big, m_a)))
    monkeypatch.setattr(rs, "_resonant_rates", lambda cls, point: {"h": r * limit / 1e3})
    return rs.monoh(cls, p, True)


@pytest.mark.parametrize("m_big,m_a,sin_theta,tan_beta,fixed,named", [
    (1000.0, 250.0, 0.8, 2.0, {}, "sinp = 0.8"),
    (1000.0, 250.0, 0.5, 7.0, {}, "tanbeta = 7"),
    (1000.0, 250.0, 0.5, 2.0, {"lam3": "1.0"}, "lam3 = 1"),
    (1000.0, 500.0, 0.5, 2.0, {}, "m_a = 500 GeV"),
    (1500.0, 250.0, 0.5, 2.0, {}, "m_A = 1500 GeV")])
def test_mono_h_decides_nothing_outside_the_calibrated_box(monkeypatch, m_big, m_a, sin_theta, tan_beta, fixed,
                                                           named) -> None:
    """The owner (2026-10-12): the band applies only where it was calibrated, the benchmark and MadGraph's box."""
    cls, p = _thdma(m_big, **fixed), Point(m_chi=10.0, m_med=m_a, g_chi=1.0, g_q=sin_theta, g_l=tan_beta)
    out = _monoh(monkeypatch, cls, p, m_big, m_a, 1e9)                              # far above any limit
    assert out.excluded is None and "calibrated at ATLAS's benchmark" in out.why and named in out.why


def test_inside_the_calibrated_box_the_widened_band_decides(monkeypatch) -> None:
    """MadGraph's full gg → h a widens the benchmark band by the shift's range at (sin θ, tan β) (docs/monoh)."""
    low, high = rs.shift_range(0.5, 2.0)
    low, high = rs.RESONANT_OVER_FULL[0] * low, rs.RESONANT_OVER_FULL[1] * high
    cls, p = _thdma(1000.0), Point(m_chi=10.0, m_med=250.0, g_chi=1.0, g_q=0.5, g_l=2.0)
    for r, expected in ((1.05 * high, True), (0.95 * low, False), (math.sqrt(low * high), None)):
        assert _monoh(monkeypatch, cls, p, 1000.0, 250.0, r).excluded is expected


def test_between_grid_points_the_shift_is_the_envelope_of_the_corners(monkeypatch) -> None:
    monkeypatch.setattr(rs, "SHIFTS", {(0.2, 1.0): (0.5, 0.9), (0.2, 2.0): (0.8, 1.3), (0.35, 1.0): (1.0, 1.0),
                                       (0.35, 2.0): (0.9, 1.1)})
    assert rs.shift_range(0.3, 1.5) == (0.5, 1.3)
    assert rs.shift_range(0.2, 2.0) == (0.8, 1.3) and rs.shift_range(0.35, 1.0) == (1.0, 1.0)
    assert rs.shift_range(0.35, 1.5) == (0.9, 1.1)


def test_the_calibration_covers_every_corner_of_the_box() -> None:
    """Every (sin θ, tan β) of the grid has a shift range, and the benchmark's is exactly 1."""
    assert {k[0] for k in rs.SHIFTS} == {0.2, 0.35, 0.5, 0.7} and {k[1] for k in rs.SHIFTS} == {1.0, 2.0, 3.0, 5.0}
    assert len(rs.SHIFTS) == 16 and rs.SHIFTS[(0.35, 1.0)] == (1.0, 1.0)
    assert all(0 < lo <= hi for lo, hi in rs.SHIFTS.values())


def test_at_atlas_benchmark_couplings_its_own_band_holds_at_any_mass(monkeypatch) -> None:
    """ATLAS's band was measured over its own grid of masses, beyond MadGraph's mass box."""
    cls, p = _thdma(1500.0), Point(m_chi=10.0, m_med=250.0, g_chi=1.0, g_q=0.35, g_l=1.0)
    assert _monoh(monkeypatch, cls, p, 1500.0, 250.0, 1.05 * rs.RESONANT_OVER_FULL[1]).excluded is True


def test_the_inelastic_dark_photon_names_why_dark_photon_searches_do_not_decide() -> None:
    from adroit.parameter_space.library import entry
    e = entry("inelastic_dark_photon")
    out = searches.dark_photon(e.model_class, e.point, True)
    assert out is not None and out.excluded is None and "semi-visible" in out.why


def test_babars_4mu_limit_applies_only_below_its_mass_resolution(monkeypatch) -> None:
    """The owner's record review (2026-10-13): BaBar's narrow-signal templates have a 1–9 MeV resolution, but ADROIT
    allowed Γ/M ≤ 10%; at M = 5 GeV, m_χ = 1 GeV, g′ = 0.11, g_χ = 1 (Γ = 136 MeV) it returned a native exclusion."""
    from adroit.parameter_space.library import entry
    e = entry("lmu_minus_ltau")
    monkeypatch.setattr(s, "_tool", lambda name: "DarkCast")
    monkeypatch.setattr(s, "darkcast_excludes", lambda stem, m, coupling: True)
    monkeypatch.setattr(s, "darkcast_ratio", lambda stem, m, coupling: 2.0)
    narrow = e.point.model_copy(update={"m_chi": 3.0, "m_med": 5.0, "g_q": 1e-3, "g_chi": 1e-3})
    assert e.model_class.mediator(narrow).width < searches.BABAR_4MU_RESOLUTION
    assert searches._lmu_native(e.model_class, narrow, True).native_excluded is True
    broad = searches._lmu_native(e.model_class, e.point.model_copy(update={"m_chi": 1.0, "m_med": 5.0, "g_q": 0.11,
                                                                           "g_chi": 1.0}), True)
    assert broad.native_excluded is None and "1–9 MeV" in broad.why and "136 MeV" in broad.why
    assert searches.BABAR_4MU_RESOLUTION == 0.001

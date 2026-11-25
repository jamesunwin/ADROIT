"""Resonance searches beyond SModelS's maps: dijets, tt̄, broad ZZ, the 2HDM+a's mono-Higgs and mono-Z."""

import math

import numpy as np
import pytest

from adroit.constraints import searches as s
from adroit.parameter_space import resonances as rs
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class
from adroit.parameter_space.portals.higgs import SingletMixing

needs_vector_tables = pytest.mark.skipif(ps.production_unavailable(*ps.VECTOR_TABLES.values()) != "",
                                         reason="the Z′ production tables are not in the tools folder")
needs_gluon_fusion = pytest.mark.skipif(rs._rates_missing().startswith("MadGraph"),
                                        reason="the gluon-fusion tables are not in the tools folder")


def test_the_quark_only_reference_has_no_top_below_its_threshold():
    assert rs._reference_jj(300.0) == pytest.approx(1.0)
    assert 0.75 < rs._reference_jj(1000.0) < 0.9                          # tt̄ takes its share above 2m_t


def test_cms_dijets_treat_a_z_prime_through_its_effective_coupling(monkeypatch, awaiting):
    from adroit.constraints import production
    monkeypatch.setattr(production, "sigma_pb", lambda name, m, column="sigma_pb": 100.0)
    v1 = Spin1Class(name="V1")
    p = Point(m_chi=1000.0, m_med=1000.0, g_chi=1.0, g_q=0.1, g_l=0.0)
    sigma, _, _, widths = ps._z_prime(v1, p)
    total = sum(widths.values())
    jj = sum(w for k, w in widths.items() if k != "dm" and abs(k[0]) <= 5) / total
    limit = s.interpolate(s._bundled("cms-1806.00843-dijet")["limit"], 1000.0)
    expected = (sigma * jj / (100.0 * rs._reference_jj(1000.0))) / limit ** 2
    out = rs.dijet(v1, p, True)
    assert out.ratio == pytest.approx(expected) and out.excluded == (expected > 1.0)
    assert rs.dijet(v1, p.model_copy(update={"m_med": 400.0}), True) is None      # below CMS's 0.6 TeV
    awaiting("cms-1806.00843-dijet")
    assert rs.dijet(v1, p, False).excluded is None                               # while its record awaits verification


@needs_vector_tables
def test_a_broad_z_prime_meets_atlas_gaussian_limits_or_is_undecided():
    """Γ/m 10–12%: ATLAS's Gaussian limits; broader than ATLAS's widest DM Z′ (12%): undecided (docs/widths.md)."""
    v1 = Spin1Class(name="V1")
    broad = rs.dijet(v1, Point(m_chi=100.0, m_med=5000.0, g_chi=0.5, g_q=0.45, g_l=0.0), True)     # Γ/m ≈ 10.3%
    assert broad.excluded is not None and broad.ratio > 0
    unlisted = rs.dijet(v1, Point(m_chi=100.0, m_med=2500.0, g_chi=0.5, g_q=0.45, g_l=0.0), True)  # no A at 2.5 TeV
    assert unlisted.excluded is None and "acceptance" in unlisted.why
    too_broad = rs.dijet(v1, Point(m_chi=100.0, m_med=2500.0, g_chi=1.0, g_q=0.6, g_l=0.0), True)  # Γ/m ≈ 20%
    assert too_broad.excluded is None and "widest DM Z′" in too_broad.why


@pytest.mark.needs("production_tables")
def test_the_gaussian_route_takes_the_acceptance_of_the_atlas_z_prime_of_the_same_width(monkeypatch):
    data = s._bundled("atlas-1910.08447-dijet-gaussian")
    at = {float(g): s.interpolate([r for r in col if r[1] is not None], 5000.0)
          for g, col in data["zprime_acceptance"].items()}
    w4, w5 = 3 * 0.4 ** 2 / (2 * math.pi), 3 * 0.5 ** 2 / (2 * math.pi)
    p = Point(m_chi=100.0, m_med=5000.0, g_chi=0.5, g_q=0.1, g_l=0.0)          # the coupling no longer picks A
    mid = 0.5 * (w4 + w5)
    limit = float(np.interp(100 * mid / rs.FWHM, sorted(float(w) for w in data["gaussian_limits"]),
                            [s.interpolate(data["gaussian_limits"][str(w)], 5000.0)
                             for w in sorted(float(w) for w in data["gaussian_limits"])]))
    assert rs._atlas_gaussian(p, 1.0, mid)[1] == pytest.approx(0.5 * (at[0.4] + at[0.5]) / limit, rel=1e-9)
    ratio, matched, why = rs._atlas_gaussian(p.model_copy(update={"m_med": 3000.0}), 1.0, mid)   # A only to 4.3%
    assert ratio is None and matched is None and "acceptance" in why


@needs_vector_tables
def test_atlas_gaussian_limits_decide_by_the_truncation_recipe_and_flag_the_full_width_match():
    """ATLAS's own Breit–Wigner Z′ with g_q = 0.5 is excluded below 4.6 TeV (arXiv:1910.08447 Table 2): ATLAS's
    truncation recipe excludes it below 4.2 TeV, the full width at half maximum match below 4.9 TeV
    (scripts/validate_dijet_breit_wigner.py; the external audit's item 18, the owner's decision of 2026-10-17)."""
    z = Spin1Class(name="ATLAS's DM Z′")

    def at(m):
        return rs.dijet(z, Point(m_chi=2e4, m_med=m, g_q=0.5, g_chi=0.0, g_l=0.0), True)

    low, mid, high = at(4000.0), at(4600.0), at(5200.0)
    assert low.excluded is True and low.ratio > 1                                # both exclude
    assert mid.excluded is False and 0.3 < mid.ratio < 1                         # only the match excludes: flagged
    assert any("flagged, not counted as an exclusion" in f for f in mid.flags)
    assert any("atlas-1910.08447-dijet-gaussian" in f for f in mid.flags)        # the deciding record's notes
    assert high.excluded is False and not any("flagged, not" in f for f in high.flags)
    recipe, matched, _ = rs._atlas_gaussian(Point(m_chi=2e4, m_med=4600.0), 1.0, 0.119)
    assert matched / recipe > 2                                                  # the bracket around ATLAS's own


@needs_vector_tables
def test_the_window_share_falls_with_the_width_and_the_mass():
    """The q q̄ luminosity lifts a broad Breit–Wigner's low tail, most at high mass (ATLAS's recipe removes it)."""
    assert rs.window_fraction(2000.0, 1e-3) > 0.99                               # a narrow resonance sits inside
    shares = [rs.window_fraction(m, 0.12) for m in (2000.0, 4000.0, 6000.0)]
    assert shares == sorted(shares, reverse=True) and shares[-1] < 0.2
    assert rs.window_fraction(4000.0, 0.10) > rs.window_fraction(4000.0, 0.12)


def test_ttbar_bands_need_both_bracketing_widths_to_agree():
    data = s._bundled("cms-1908.01115-ttbar")
    lower = s.interpolate(data["borders"]["scalar"]["2.5"]["lower"], 500.0)
    assert rs._ttbar_state(data, "scalar", 500.0, 2.5, lower * 1.1) is True
    assert rs._ttbar_state(data, "scalar", 500.0, 2.5, lower * 0.9) is False
    assert rs._ttbar_state(data, "scalar", 500.0, 40.0, 5.0) is None              # broader than 25%
    entry = data["borders"]["pseudoscalar"]["10.0"]                               # an allowed island at 740 GeV
    low, high = (s.interpolate(entry[k], 740.0) for k in ("island_low", "island_high"))
    assert rs._excluded_at(entry, 740.0, 0.5 * (low + high)) is False
    assert rs._excluded_at(entry, 740.0, high * 1.05) is True


def test_ttbar_reads_each_portals_top_coupling():
    assert rs.ttbar(ScalarClass(), Point(m_chi=1000.0, m_med=500.0, g_chi=1.0, g_q=2.0), True).excluded is True
    assert rs.ttbar(SingletMixing(), Point(m_chi=100.0, m_med=500.0, g_chi=1.0, g_q=0.3), True).excluded is False
    assert rs.ttbar(ScalarClass(), Point(m_chi=1000.0, m_med=900.0, g_chi=1.0, g_q=2.0), True) is None


def test_broad_zz_interpolates_in_the_width_only_for_a_model_matching_atlas_interference():
    zz = s._bundled("atlas-2009.14791-zz")
    at = {w: s.interpolate(zz["broad"][w], 600.0) for w in ("5.0", "10.0")}
    assert ps._zz_limit(zz, 600.0, 7.5, "")[0] == pytest.approx(0.5 * (at["5.0"] + at["10.0"]))
    assert ps._zz_limit(zz, 600.0, 0.0, "")[0] == pytest.approx(s.interpolate(zz["limit"], 600.0))
    limit, why = ps._zz_limit(zz, 600.0, 7.5, "the singlet's interference differs")
    assert limit is None and "0.5%" in why and "the singlet's interference differs" in why


def test_the_narrow_zz_limit_stops_at_half_a_percent_of_the_mass():
    """ATLAS (arXiv:2009.14791 §9.1.1): its narrow-width result is valid for Γ/m < 0.5%, not 5%."""
    zz = s._bundled("atlas-2009.14791-zz")
    assert ps._zz_limit(zz, 300.0, 0.4, "x")[0] == pytest.approx(s.interpolate(zz["limit"], 300.0))
    limit, why = ps._zz_limit(zz, 300.0, 2.0, "")
    assert limit is None and "400 GeV" in why                                  # no large-width table below 400 GeV
    assert ps._zz_limit(zz, 150.0, 0.1, "") == (None, "")                      # below ATLAS's masses: not applicable
    assert ps.ZZ_NARROW == 0.005 and ps.ww_resolution(1000.0) == pytest.approx(0.07)
    assert ps.ww_resolution(5000.0) == pytest.approx(0.04)


def test_the_narrow_ww_limit_stops_at_0p6_of_the_resolution_as_atlas_uses_it():
    """The owner (2026-10-12): ATLAS's radion, Γ/m = 3.2% at 3 TeV where the resolution is 5.5%, is the widest case
    ATLAS applies its narrow limits to (0.58 of the resolution); ADROIT stops at 0.6 of it."""
    assert ps.ww_resolution(3000.0) == pytest.approx(0.055)
    assert ps.ww_narrow(3000.0) == pytest.approx(0.033)
    assert 0.032 < ps.ww_narrow(3000.0) < ps.ww_resolution(3000.0)        # the radion stays inside the domain
    assert ps.ww_narrow(1000.0) == pytest.approx(0.042)


@pytest.mark.needs("ufo_models")
def test_ttbar_needs_the_top_loop_and_a_single_state():
    from adroit.parameter_space.library import TWO_HDM_A
    heavy = {k: "600.0" for k in ("mh2", "mh3", "mhc")}
    cls = TWO_HDM_A.model_copy(update={"parameters": {**TWO_HDM_A.parameters, **heavy}})
    large_tan_beta = rs.ttbar(cls, Point(m_chi=200.0, m_med=250.0, g_chi=1.0, g_q=0.35, g_l=8.0), True)
    assert large_tan_beta.excluded is None and "b-quark loop" in large_tan_beta.why
    assert rs._top_loop_mismatch("scalar", 500.0, 1.0, 0.0) == ""
    assert rs._top_loop_mismatch("scalar", 500.0, 1.0, 1.0) == ""              # SM-like: the top loop dominates


def test_the_monotone_contour_rule():
    square = [[100.0, 200.0], [500.0, 200.0], [500.0, 1000.0], [100.0, 1000.0]]
    assert rs._inside(square, 300.0, 500.0) and not rs._inside(square, 600.0, 500.0)


@pytest.mark.slow
def test_the_2hdma_mono_higgs_reproduces_atlas_on_its_own_plane():
    from adroit.parameter_space.library import TWO_HDM_A
    data = s._bundled("atlas-2108.13391-monoh")
    agree = total = 0
    for m_big, m_a, theory in data["benchmark_sigma"]:
        out = rs.monoh(rs._reference(TWO_HDM_A, 0.35, m_big), Point(m_chi=10.0, m_med=m_a, g_chi=1.0, g_q=0.35,
                                                                   g_l=1.0), True)
        if out is None or out.excluded is None:
            continue
        atlas = next(r[2] for r in data["sigma95"] if r[:2] == [m_big, m_a]) < theory
        total += 1
        agree += out.excluded == atlas
    # R4 (audit M2): points whose ratio lies inside the resonant-to-full band (0.419-1.240) are undecided; the
    # 39 of 94 decided outside it all agree with ATLAS
    assert total >= 35 and agree == total


def _two_hdma(m_heavy: float):
    from adroit.parameter_space.library import TWO_HDM_A
    heavy = {k: repr(m_heavy) for k in ("mh2", "mh3", "mhc")}
    return TWO_HDM_A.model_copy(update={"parameters": {**TWO_HDM_A.parameters, **heavy}})


@needs_gluon_fusion
def test_mono_z_is_extended_beyond_atlas_benchmarks_only_inside_the_calibrated_box(monkeypatch):
    """The owner's data audit (2026-10-12): a benchmark contour is not extended blindly. MadGraph's full gg → Z a
    calibrates it over sin θ 0.2–0.7, tan β 1–5, m_H 500–800 GeV, m_a 150–300 GeV; beyond, the point is undecided."""
    monkeypatch.setattr(rs, "_relative_width", lambda model, name: 0.05)
    beyond = rs.monoz(_two_hdma(800.0), Point(m_chi=10.0, m_med=250.0, g_chi=1.0, g_q=0.35, g_l=7.0), True)
    assert beyond.excluded is None and "calibration" in beyond.why and "tanbeta = 7" in beyond.why
    heavy = rs.monoz(_two_hdma(1000.0), Point(m_chi=10.0, m_med=250.0, g_chi=1.0, g_q=0.35, g_l=2.0), True)
    assert heavy.excluded is None and "m_H = 1000 GeV" in heavy.why
    inside = rs.monoz(_two_hdma(800.0), Point(m_chi=10.0, m_med=250.0, g_chi=1.0, g_q=0.35, g_l=2.0), True)
    assert "calibration" not in (inside.why or "")
    assert rs.MONOZ_BENCHMARK == {"tanbeta": 1.0, "lam3": 3.0, "laP1": 3.0, "laP2": 3.0}


def test_mono_z_shifts_are_one_on_each_contours_own_benchmark_at_any_mass():
    planes = {"0.35": None, "0.7": None}
    values = {"sinp": 0.35, "tanbeta": 1.0, "lam3": 3.0, "laP1": 3.0, "laP2": 3.0, "mh2": 1200.0, "mh3": 1200.0,
              "mhc": 1200.0}
    shifts, away = rs._monoz_shifts(values, 1200.0, 400.0, planes)          # beyond the calibrated masses
    assert shifts == {"0.35": (1.0, 1.0)} and "m_H = 1200 GeV" in away
    shifts, _ = rs._monoz_shifts({**values, "mh2": 600.0, "mh3": 600.0, "mhc": 600.0}, 600.0, 200.0, planes)
    assert shifts["0.35"] == (1.0, 1.0) and shifts["0.7"] == rs.SHIFTS_Z[0.7][(0.35, 1.0)]
    unequal, why = rs._monoz_shifts({**values, "mhc": 700.0}, 1200.0, 400.0, planes)
    assert unequal == {} and "differ" in why


@pytest.mark.parametrize("ratio,inside,expected", [(1.03, True, True), (1.0, True, None), (0.95, False, False),
                                                   (0.995, False, None), (1.03, False, None), (0.95, True, None)])
@pytest.mark.needs("ufo_models")
def test_mono_z_thresholds_are_the_calibrated_shift_range(monkeypatch, ratio, inside, expected):
    """Inside a contour: excluded only at ≥ max s times its reference's rate; outside (and covered): allowed only at
    ≤ min s times it. At (sin θ, tan β) = (0.5, 2) the 0.35 contour's s spans 0.991–1.008."""
    cls = _two_hdma(600.0)
    monkeypatch.setattr(rs, "_relative_width", lambda model, name: 0.05)
    monkeypatch.setattr(rs, "_inside", lambda contour, m_a, m_big: inside)
    monkeypatch.setattr(rs, "_covered", lambda contour, m_a, m_big: True)
    monkeypatch.setattr(s, "_bundled", lambda name: {"contours": {"0.35": [[100.0, 500.0]]}})
    monkeypatch.setattr(s, "_blocked", lambda *a: None)
    rates = iter([ratio, 1.0])                                                 # the point's, then the reference's
    monkeypatch.setattr(rs, "_resonant_rates", lambda c, p: {"Z": next(rates)})
    out = rs.monoz(cls, Point(m_chi=10.0, m_med=200.0, g_chi=1.0, g_q=0.5, g_l=2.0), True)
    assert rs.shift_range(0.5, 2.0, rs.SHIFTS_Z[0.35]) == (0.991, 1.008)
    assert out.excluded is expected


def test_the_mono_z_calibration_found_the_resonant_picture_holds_to_a_few_percent():
    """docs/monoz/calibration.json: the boxes' share hardly changes with sin θ and tan β (unlike mono-h's)."""
    for plane, table in rs.SHIFTS_Z.items():
        assert {k[0] for k in table} == {0.2, 0.35, 0.5, 0.7} and {k[1] for k in table} == {1.0, 2.0, 3.0, 5.0}
        assert table[(plane, 1.0)] == (1.0, 1.0)
        assert all(0.95 < low <= high < 1.03 for low, high in table.values())


def test_a_missing_production_table_leaves_the_search_undecided_with_its_reason(monkeypatch):
    """The clean-machine install test (2026-10-12, CERN's twiki and FeynRules down): without its tables a search said
    nothing (dijets), crashed (mono-Z: an invented zero rate) or read a file that was not there (the LHC search)."""
    from adroit.constraints import lhc, production
    monkeypatch.setattr(production, "available", lambda name: False)
    v1 = Spin1Class(name="V1")
    out = rs.dijet(v1, Point(m_chi=100.0, m_med=1000.0, g_chi=1.0, g_q=0.1, g_l=0.0), True)
    assert out.excluded is None and "not in the tools folder" in out.why
    monkeypatch.setattr(lhc, "table_available", lambda kind: False)
    assert lhc.cross_section_pb("coloured", 1000.0) is None and "not in the tools folder" in lhc.unavailable("coloured")


@pytest.mark.needs("ufo_models")
def test_a_missing_production_table_leaves_the_mono_z_rate_unknown(monkeypatch):
    """The same install test's mono-Z part (an invented zero rate): the 2HDM+a is built from its UFO model, which
    MadGraph's Python reads, so this part needs the tools folder; the searches above do not (B20-08)."""
    from adroit.constraints import production
    from adroit.parameter_space.library import TWO_HDM_A
    monkeypatch.setattr(production, "available", lambda name: False)
    cls = rs._reference(TWO_HDM_A, 0.35, 600.0)
    assert rs._resonant_rates(cls, Point(m_chi=10.0, m_med=200.0, g_chi=1.0, g_q=0.35, g_l=1.0))["Z"] is None

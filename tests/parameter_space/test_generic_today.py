"""G8: long-range effects today for the generic engine, from G3's amplitudes (``portals.generic_today``)."""

import math

import numpy as np
import pytest

from adroit.core.model_spec import ModelSpec
from adroit.evaluation import zoo
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals import generic as gm
from adroit.parameter_space.portals import generic_id as gid
from adroit.parameter_space.portals import generic_today as gt
from adroit.parameter_space.portals.multiplet import ALPHA_2_MZ, ElectroweakMultiplet


def _wino(m: float):
    e = next(x for x in zoo.entries() if x.id == "wino_majorana_triplet_bottaro")
    engine = gm.GenericModel.of(zoo._spec(e, e.targets[0]))
    p = engine.point().model_copy(update={"m_chi": m})
    return engine, p


def _higgsino(m: float):
    spec = ModelSpec.model_validate({"name": "h", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": m,
         "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}]})
    engine = gm.GenericModel.of(spec)
    return engine, engine.point()


def test_the_one_loop_splittings_are_the_multiplets():
    """Cirelli, Fornengo & Strumia at M ≫ M_W: the wino's 165 MeV and the higgsino's 353 MeV."""
    assert gt.splitting(3, 0.0, 1, 80.377, 91.1876, ALPHA_2_MZ) == pytest.approx(0.1654, abs=5e-4)
    assert gt.splitting(2, 0.5, 1, 80.377, 91.1876, ALPHA_2_MZ) == pytest.approx(0.3531, abs=5e-4)
    assert gt.splitting(5, 0.0, 2, 80.377, 91.1876, ALPHA_2_MZ) == pytest.approx(4 * 0.1654, abs=2e-3)


def test_the_winos_potential_is_hisanos_boson_by_boson():
    """From G3: W couples χ⁰χ⁰ to χ⁺χ⁻ and χ⁻χ⁺ by α₂, Z and γ act on the charged pairs by c_W²α₂ and α."""
    engine, p = _wino(2000.0)
    mb, rules, model = engine.at(p)
    grp, block, j = gt.neutral_block(engine.long_range_effects(p), mb, model)
    assert block[j] == ("chi0", "chi0") and len(block) == 3
    terms = {round(mass): a for a, mass in gt.potential_terms(model, block)}
    assert terms[80][j, 1] == pytest.approx(ALPHA_2_MZ, rel=2e-3) and terms[80][1, 1] == pytest.approx(0.0, abs=1e-9)
    assert terms[91][1, 1] == pytest.approx(ALPHA_2_MZ * (80.37 / 91.1876) ** 2, rel=3e-3)
    assert terms[0][1, 1] == pytest.approx(1 / 128.9, rel=2e-3) and terms[0][j, j] == pytest.approx(0.0, abs=1e-12)
    assert gt.thresholds(mb, model, grp, block)[1] == pytest.approx(2 * 0.1654, abs=1e-3)


def test_without_the_potential_today_is_g6s_tree_level(monkeypatch):
    engine, p = _wino(1000.0)
    mb, rules, model = engine.at(p)
    found = engine.long_range_effects(p)
    grp, block, _ = gt.neutral_block(found, mb, model)
    monkeypatch.setattr(gt, "potential_terms", lambda model, block: [(np.zeros((3, 3)), 80.0)])
    ours = gt.rates_today(mb, rules, model, found, 1e-3)
    tree = gid.annihilation_today(mb, rules, model, 1e-3)
    for name, value in tree.items():
        if name in ours:
            assert ours[name] == pytest.approx(grp.running * value, rel=5e-3, abs=0.0), name


@pytest.mark.parametrize("m,tolerance", [(1000.0, 0.01), (1500.0, 0.02), (4000.0, 0.02), (8000.0, 0.05)])
def test_the_winos_annihilation_today_is_the_librarys(m, tolerance):
    """The library's hand-written broken-phase wino (``portals.multiplet``) away from the 2.4 TeV resonance."""
    engine, p = _wino(m)
    mb, rules, model = engine.at(p)
    ours = sum(gt.rates_today(mb, rules, model, engine.long_range_effects(p), 1e-3).values())
    library = sum(ElectroweakMultiplet(name="w", multiplet="wino").sigma_v_today(
        Point(m_chi=m, m_med=1.0, g_q=0.0), 1e-3).values())
    assert ours == pytest.approx(library, rel=tolerance, abs=0.0)     # abs: approx's own (1e-12) passes any rate


def test_the_higgsinos_annihilation_today_is_the_librarys():
    """The lightest Majorana state's (the spin-0 sector alone, doubled against the searches' halving for a Dirac pair:
    AL2-02), in both routes; the library's Γ is Cirelli et al.'s symmetric-limit one."""
    engine, p = _higgsino(1000.0)
    mb, rules, model = engine.at(p)
    assert gt.split_today(mb, rules) and not gt.split_today(*_wino(1000.0)[0].at(_wino(1000.0)[1])[:2])
    ours = sum(gt.rates_today(mb, rules, model, engine.long_range_effects(p), 1e-3).values())
    library = sum(ElectroweakMultiplet(name="h", multiplet="higgsino").sigma_v_today(
        Point(m_chi=1000.0, m_med=1.0, g_q=0.0), 1e-3).values())
    assert ours == pytest.approx(library, rel=0.06, abs=0.0)


def test_the_generic_wino_has_annihilation_today_and_bounded_lines(monkeypatch):
    """G8 decides what G6 left undecided: σv today with the Sommerfeld effect. Its lines are DMγSpec's resummed rate
    where that table is installed (D21), else the general n-plet's NLL rate at 1–100 TeV (``endpoint_nll``), and
    otherwise only an upper bound."""
    from adroit.constraints import resummed_lines
    engine, p = _wino(3000.0)
    assert engine.today_unknown(p) == ""
    rates = engine.sigma_v_today(p, 1e-3)
    assert rates["W"] > 1e-25 and rates["gamma"] > 0
    if resummed_lines.available():
        assert engine.lines_upper_bound(p) == "" and engine.resummed_line(p)[0] == "wino"
    monkeypatch.setattr(resummed_lines, "available", lambda: False)
    kind, line = engine.resummed_line(p)
    assert kind == "nplet3" and 1e-27 < line < 1e-24 and engine.lines_upper_bound(p) == ""
    light = p.model_copy(update={"m_chi": 800.0})
    assert engine.resummed_line(light) == ("nplet3", None) and engine.lines_upper_bound(light) == gt.LINES_REASON


def test_the_generic_quintuplets_lines_are_the_nll_rate():
    """A pure Majorana quintuplet takes ``endpoint_nll``'s rate in the H.E.S.S. window, the library's n-plet the
    same rate."""
    from adroit.constraints import endpoint_nll
    from adroit.parameter_space.portals.nplet import ElectroweakNplet
    e = next(x for x in zoo.entries() if x.id == "majorana_quintuplet_mdm_bottaro")
    engine = gm.GenericModel.of(zoo._spec(e, e.targets[0]))
    p = engine.point().model_copy(update={"m_chi": 13600.0})
    kind, line = engine.resummed_line(p)
    assert kind == "nplet5" and line == pytest.approx(endpoint_nll.line_sigma_v(5, 13600.0), rel=1e-9)
    assert engine.lines_upper_bound(p) == ""
    library = ElectroweakNplet(name="q", n=5).resummed_lines(p)
    assert library["gamma"] == pytest.approx(line, rel=1e-9)


def test_a_sub_gev_mediators_sommerfeld_factor_is_matched_beyond_its_range():
    """The audit's G8-1 (G12): the matching radius was the W's, so a 0.1 GeV dark photon's potential was cut inside
    its range (S = 8.8). The converged single-channel Yukawa factor at α = 0.01, m = 100 GeV, v = 10⁻⁴ is 77.6."""
    from adroit.constraints import sommerfeld
    g = math.sqrt(4 * math.pi * 0.01)
    spec = ModelSpec.model_validate({"name": "dqed", "phase": "broken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "Ad", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 0.1}],
        "terms": [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Ad"}],
                   "lorentz": "vector", "coupling": f"{g}"}]})
    engine = gm.GenericModel.for_spec(spec)
    p = engine.point()
    ratio = sum(engine.sigma_v_today(p, 1e-4).values()) / sum(
        engine.model_copy(update={"sommerfeld": False}).sigma_v_today(p, 1e-4).values())
    exact = sommerfeld.enhancement(lambda r: np.array([[-0.01 * math.exp(-0.1 * r) / r]]), np.array([0.0]),
                                   np.array([0.0]), 50.0, 0.25 * 100 * 1e-8, r_max=400.0)
    assert ratio == pytest.approx(abs(exact[0, 0]) ** 2, rel=0.02)


def test_an_unresummed_line_neither_allows_nor_excludes(monkeypatch):
    """The audit's G8-5 (G12): near a zero of the tree amplitude b the resummed rate is far larger (the quintuplet at
    2.63 TeV: tree 2.5e-29, NLL 4.6e-26 cm³/s), so the tree-level rate is no upper bound and cannot allow."""
    from adroit.constraints import resummed_lines
    from adroit.parameter_space import searches
    engine, p = _wino(800.0)
    monkeypatch.setattr(resummed_lines, "available", lambda: False)
    assert engine.lines_upper_bound(p) == gt.LINES_REASON
    outcome = searches.lines(engine, p, True)
    assert outcome is None or (outcome.excluded is None and gt.LINES_REASON in outcome.why)


def test_a_charged_pair_below_the_dark_matters_is_refused_today():
    """The audit's G8-9 (G12): a Dirac 4-plet (Y = ½) at 2 TeV, whose χ⁻χ̄⁻ lies 44.5 MeV below χ⁰χ̄⁰: today's
    rate is not computed (the searches are undecided with the reason), never a silent zero."""
    spec = ModelSpec.model_validate({"name": "q4", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 2000.0,
         "charges": {"su2": 4, "hypercharge": 0.5}},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}]})
    engine = gm.GenericModel.of(spec)
    p = engine.point()
    mb, rules, model = engine.at(p)
    assert gt.rates_today(mb, rules, model, engine.long_range_effects(p), 1e-3) is None
    assert engine.today_unknown(p).startswith("needs the Sommerfeld effect today")

"""The generic engine (G4): a typed model's relic density from its own Feynman rules, its long-range criterion and
estimate (decision D4), its certificates, and its place after the library's maps in ``classify``."""

import math

import pytest

from adroit.constraints import long_range_bracket as lb
from adroit.core.model_spec import ModelSpec
from adroit.model_building.gauge_basis import V_EW
from adroit.evaluation import zoo
from adroit.model_building.feynman import MassVertex, ParticleRecord, Rules
from adroit.parameter_space.classify import Unsupported, classify
from adroit.parameter_space.portals import generic_checks as gc
import numpy as np

from adroit.parameter_space.portals import generic as gm
from adroit.parameter_space.portals.generic import GenericModel, final_states


def singlet_doublet(m1: float = 180.0, m2: float = 320.0, sin_theta: float = 0.2) -> ModelSpec:
    """A Dirac singlet χ⁰ and a Dirac doublet N (Y = −½) mixed by −y N̄H̃χ⁰ + h.c.: mass eigenvalues m1 and m2, the
    lighter mostly singlet, with angle θ. Lagrangian masses m1cos²θ + m2sin²θ and m1sin²θ + m2cos²θ; y v/√2 =
    (m2 − m1) sin θ cos θ."""
    c2, s2 = 1 - sin_theta ** 2, sin_theta ** 2
    y = (m2 - m1) * sin_theta * math.sqrt(c2) * math.sqrt(2) / V_EW
    return ModelSpec.model_validate({"name": "singlet_doublet", "phase": "unbroken", "fields": [
        {"name": "chi0", "role": "dark_matter", "spin": 0.5, "mass_gev": m1 * c2 + m2 * s2, "dark_parity": -1},
        {"name": "N", "role": "dark_matter", "spin": 0.5, "mass_gev": m1 * s2 + m2 * c2, "dark_parity": -1,
         "charges": {"su2": 2, "hypercharge": -0.5}},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
        "couplings": [{"name": "Y", "value": y}],
        "terms": [{"fields": [{"field": "N", "conjugate": True}, {"field": "H", "conjugate": True}, {"field": "chi0"}],
                   "lorentz": "scalar", "coupling": "-Y", "plus_hc": True, "indices": "eps[i,j] N*[i] H*[j] chi0"}]})


def _entry_spec(entry_id: str) -> ModelSpec:
    e = next(x for x in zoo.entries() if x.id == entry_id)
    return zoo._spec(e, e.targets[0])


@pytest.fixture(scope="module")
def wino():
    return GenericModel.of(_entry_spec("wino_majorana_triplet_bottaro"), sommerfeld=False)


@pytest.fixture(scope="module")
def wino_point(wino):
    return wino.point().model_copy(update={"m_chi": 1000.0})


def test_final_states_need_a_tree_diagram(wino, wino_point):
    """Charge conservation alone would admit χ⁰χ⁰ → e μ̄ and → γg; only pairs with a diagram are kept."""
    _, _, model = wino.at(wino_point)
    found = final_states(model, "chi0", "chi0")
    assert ("W", "W~") in found and ("e", "mu~") not in found and ("A", "g") not in found


def test_the_wino_perturbatively_matches_the_library(wino, wino_point):
    """At 1 TeV without the Sommerfeld effect: the generic route's Ωh² against the n-plet engine's (which adds the
    165 MeV radiative splitting), and against MadDM's 0.0237 on the exported model (docs/g4_generic.md)."""
    e = next(x for x in zoo.entries() if x.id == "wino_majorana_triplet_bottaro")
    library, point, _, _ = zoo.mapped(e, e.targets[0])
    library = library.model_copy(update={"sommerfeld": False, "bound_states": False})
    ours = wino.omega_h2(wino_point)
    assert ours == pytest.approx(library.omega_h2(point.model_copy(update={"m_chi": 1000.0})), rel=0.03)
    assert ours == pytest.approx(0.0237, rel=0.10)


def test_the_winos_sommerfeld_effect_is_computed_inside_g4s_bracket(wino, wino_point):
    """G7 computes what G4 refused: the Sommerfeld effect alone takes Ωh² to the library's 0.686 × perturbative at
    1 TeV (``portals.multiplet``), inside G4's bracket."""
    engine = wino.model_copy(update={"sommerfeld": True, "bound_states": False})
    assert engine.domain(wino_point) == ""
    ratio = engine.omega_h2(wino_point) / wino.omega_h2(wino_point)
    assert ratio == pytest.approx(0.686, rel=0.05)
    b = engine.estimate(wino_point)
    assert b.omega_low < ratio * b.omega_perturbative < b.omega_high


def _septuplet() -> GenericModel:
    """A Majorana 7-plet at 5 TeV: G7 does not compute bound states in channels I ≥ 7."""
    return GenericModel.of(ModelSpec.model_validate({"name": "seven", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
         "mass_gev": 5000.0, "charges": {"su2": 7}}]}))


def test_where_g7_refuses_g4s_bracket_decides():
    engine = _septuplet()
    p = engine.point()
    reason = engine.domain(p)
    assert reason.startswith("needs the Sommerfeld effect (G7)") and "7-plet" in reason
    assert engine.omega_h2(p) is None


def test_the_estimate_is_a_flag_and_never_a_verdict():
    engine = _septuplet().model_copy(update={"long_range": "estimate"})
    p = engine.point()
    assert engine.omega_h2(p) is None
    flags = engine.flags(p)
    assert any(f.startswith("Ωh² refused; the estimate on request") and lb.WARNING in f for f in flags)


def test_the_bath_is_in_chemical_equilibrium_through_the_w(wino, wino_point):
    """χ± converts to χ⁰ by W exchange with the light bath, far faster than H."""
    assert not any("chemical equilibrium" in f for f in wino.flags(wino_point))


def test_a_coloured_states_representation_is_conjugated_for_its_antiparticle():
    spec = ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
         "mass_gev": 300.0},
        {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 320.0,
         "charges": {"su3": "3", "hypercharge": 2 / 3}}]})
    mb, _, _ = GenericModel.of(spec).at(GenericModel.of(spec).point())
    assert gc.representation(mb, "Phi(+0.667)") == pytest.approx((1, "3", 2 / 3, 2 / 3))
    assert gc.representation(mb, "Phi(+0.667)~") == pytest.approx((1, "3bar", -2 / 3, -2 / 3))


def test_a_partner_with_no_conversion_refuses_the_relic_and_leaves_the_rest():
    """De Simone et al.'s coloured triplet as the zoo writes it, with no coupling to χ: nothing converts it, so the
    coannihilation relic is refused (the owner's decision #5, 2026-10-20: it had been a flag), while the model's other
    calculations stay available."""
    spec = _entry_spec("coloured_coannihilation_scalar_triplet_desimone")
    engine = GenericModel.of(spec, tied="chi_prime", sommerfeld=False)
    p = engine.point().model_copy(update={"m_chi": 1000.0, "m_med": 1000.1})
    assert engine.domain(p).startswith("several stable components: chi_prime0") and engine.omega_h2(p) is None
    assert not any("chemical equilibrium" in f for f in engine.flags(p))
    assert engine.scattering(p) is not None


def _rules(coupling: float) -> Rules:
    """A dark photon V of 1 GeV that decays to e⁺e⁻ with vector coupling ``coupling``."""
    particles = [ParticleRecord("V", 1, 1.0, "", "1", 0.0, 1), ParticleRecord("e", 0.5, 0.000511, "e~", "1", -1.0, 1)]
    return Rules(particles, [MassVertex("FFV", ("e", "e~", "V"), coupling)], 0.0)


@pytest.mark.parametrize("coupling,flagged", [(1e-3, False), (1e-14, True)])
def test_kinetic_contact_of_a_new_final_state(coupling, flagged):
    finals = {(0, 0): [("V", "V")]}
    assert bool(gc.kinetic_flags(_rules(coupling), finals, 25.0, 100.0)) is flagged


def test_a_light_new_state_is_flagged_for_g_star():
    assert gc.light_state_flags(_rules(1e-3), 25.0, 100.0)               # T_f = 4 GeV > m_V = 1 GeV
    assert not gc.light_state_flags(_rules(1e-3), 25.0, 10.0)            # T_f = 0.4 GeV


def test_the_invisible_higgs_width_of_a_majorana_portal():
    """L ⊃ −½ g h χ̄χ: Γ(h → χχ) = g² m_h β³/16π."""
    g, m = 0.01, 30.0
    rules = Rules([ParticleRecord("h", 0, 125.25, "", "1", 0.0, 1), ParticleRecord("chi0", 0.5, m, "", "1", 0.0, -1)],
                  [MassVertex("FFS", ("chi0", "chi0", "h"), -g)], 0.0)
    beta = math.sqrt(1 - 4 * m * m / 125.25 ** 2)
    assert gc.invisible_widths(rules, "chi0", "chi0")["h"] == pytest.approx(g * g * 125.25 * beta ** 3 / (16 * math.pi))


def test_classify_falls_back_to_the_generic_route():
    """A singlet–doublet Dirac model is outside the library's maps: classify gives the generic route, with the maps'
    refusal in its notes (the default since the owner's decision of 2026-10-15); with generic_route=False the
    refusal stands."""
    spec = singlet_doublet()
    engine, _, notes = classify(spec)
    assert isinstance(engine, GenericModel) and notes[0].startswith("the generic route (G4)")
    with pytest.raises(Unsupported):
        classify(spec, generic_route=False)


def test_a_model_the_generic_route_cannot_build_keeps_its_refusal():
    spec = ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0,
         "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 200.0}],
        "couplings": [{"name": "y", "value": 0.3}],
        "terms": [{"fields": [{"field": "chi"}, {"field": "chi"}, {"field": "S"}], "lorentz": "scalar",
                   "coupling": "y", "text": "χχS: hypercharge 1, not invariant"}]})
    with pytest.raises(Unsupported, match="the generic route cannot build it either"):
        classify(spec, generic_route=True)


def test_a_narrow_pole_is_integrated_from_its_table():
    """σβ = a Breit–Wigner of Γ/M = 10⁻⁴ tabulated on the engine's nodes: its integral to 1% (linear interpolation
    on the old 13 nodes overestimated it, which made Choubey et al.'s BP1 8% low in Ωh²)."""
    import numpy as np
    from adroit.parameter_space.portals import generic as gm
    threshold, mass, width = 175.0, 195.0, 0.0195
    nodes = gm._nodes(threshold, threshold, [(mass, width)])
    def bw(u):
        root = threshold * (1 + u)
        return 1.0 / ((root ** 2 - mass ** 2) ** 2 + (mass * width) ** 2)
    sigma = gm._interpolated(nodes, bw(nodes), threshold, threshold / 2, threshold / 2)
    u = np.linspace(nodes[0], 0.3, 4_000_001)
    s = (threshold * (1 + u)) ** 2
    beta = np.sqrt(np.clip((s - threshold ** 2) * s, 0, None)) / s
    assert np.trapezoid(sigma(s) * beta, u) == pytest.approx(np.trapezoid(bw(u), u), rel=0.01)


def test_only_poles_with_the_pairs_charge_enter_its_s_channel(wino, wino_point):
    from adroit.parameter_space.portals.generic import _s_channel
    _, rules, model = wino.at(wino_point)
    neutral = {round(m, 3) for m, _ in _s_channel(model, "chi0", "chi0", rules)}
    charged = {round(m, 3) for m, _ in _s_channel(model, "chi0", "chi+", rules)}
    assert 91.188 in neutral and 80.37 not in neutral and charged == {80.37}


def test_a_top_pair_just_above_threshold_is_flagged():
    from adroit.constraints import tree
    model = tree.Model({})
    model.add(tree.Particle("t", 0.5, 172.5, 0.0, "t~"))
    flags = gc.three_body_flags(model, [("t", "t~")], 160.0)
    assert flags and flags[0].startswith("three-body tail not computed")
    assert not gc.three_body_flags(model, [("t", "t~")], 120.0) and not gc.three_body_flags(model, [("t", "t~")], 180.0)


# --- direct detection (G5) ---------------------------------------------------------------------------------------

def test_the_wino_scatters_through_the_n_plet_loops(wino, wino_point):
    """No tree-level coupling for the wino: its σ_SI is the n-plet engine's two-loop result."""
    from adroit.parameter_space.portals.nplet import sigma_si
    from adroit.parameter_space.portals.base import sigma_from
    found = wino.scattering(wino_point)
    assert found.route.startswith("loop (the electroweak 3-plet")
    assert sigma_from(found.nucleon.c1_p, wino_point.m_chi) == pytest.approx(sigma_si(3, 0.0, "p")[0], rel=1e-6)


def test_a_model_without_quark_couplings_is_loop_dominated_and_undecided():
    """Giacchino et al.'s real scalar with a lepton partner: nothing at tree level, no loop entry."""
    spec = _entry_spec("real_scalar_dm_vectorlike_lepton_giacchino")
    engine = GenericModel.of(spec, sommerfeld=False)
    p = engine.point()
    found = engine.scattering(p)
    assert found.route == "none" and found.nucleon.suppressed == "loop-dominated, not computed"
    assert any(x.startswith("direct detection: loop-dominated") for x in engine.pending(p))


def test_a_pseudo_dirac_pair_scatters_inelastically():
    """Two Majorana states 100 keV apart, joined by a Z′ that couples to quarks: no elastic scattering, and the
    inelastic channel goes to Path 1. (Between two Majorana fields χ̄₁γ^μχ₂ = −χ̄₂γ^μχ₁, so a real vector coupling
    plus its conjugate vanishes; the axial one, χ̄₁γ^μγ⁵χ₂ = χ̄₂γ^μγ⁵χ₁, does not.)"""
    fields = [{"name": "chi1", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 100.0},
              {"name": "chi2", "role": "other", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 100.0001},
              {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 300.0},
              {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R",
               "charges": {"su3": "3", "hypercharge": 2 / 3}}]
    terms = [{"fields": [{"field": "chi1", "conjugate": True}, {"field": "chi2"}, {"field": "Zp"}],
              "lorentz": "axial", "coupling": "g", "plus_hc": True},
             {"fields": [{"field": "uR", "conjugate": True}, {"field": "uR"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": "g"}]
    spec = ModelSpec.model_validate({"name": "ps", "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "g", "value": 0.2}]})
    engine = GenericModel.of(spec, sommerfeld=False)
    p = engine.point()
    assert engine.scattering(p).route == "inelastic" and engine.dd(p) == ("inelastic", 0.0)
    assert any("inelastic scattering" in x for x in engine.pending(p))


def test_the_zoo_compares_the_proton_cross_section():
    """A singlet–doublet Dirac relic scatters through the Z, whose vector coupling to protons is suppressed by
    1 − 4s_W²: the neutron's c₁ (which ``dd`` would weigh for xenon) is many times the proton's, and the zoo's σ_SI
    is the proton's, σ_p = (c₁ᵖ)²μ²/π."""
    from adroit.parameter_space.portals.base import sigma_from
    engine = GenericModel.of(singlet_doublet(), sommerfeld=False)
    point = engine.point()
    n = engine.nucleon(point)
    value, why = zoo._proton_si(engine, point)
    assert abs(n.c1_n_odd) > 5 * abs(n.c1_p_odd) and not why
    assert value == pytest.approx(sigma_from(n.c1_p, point.m_chi) + sigma_from(n.c1_p_odd, point.m_chi))


def test_a_majorana_coloured_partner_is_the_t_channel_engines():
    """Majorana χ with a partner of u_R: the generic route's c₁ (Hisano et al.'s loops) and c₄ (Fierz) are the
    t-channel engine's for the same couplings."""
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.portals.tchannel import TChannel
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 300.0},
              {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 600.0,
               "charges": {"su3": "3", "hypercharge": 2 / 3}},
              {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R",
               "charges": {"su3": "3", "hypercharge": 2 / 3}}]
    terms = [{"fields": [{"field": "Phi", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": "uR"}],
              "lorentz": "chiral", "coupling": "y", "plus_hc": True}]
    spec = ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "y", "value": 0.8}]})
    engine = GenericModel.of(spec, sommerfeld=False)
    found = engine.scattering(engine.point())
    library = TChannel(name="t", partner="uR", majorana=True).nucleon(Point(m_chi=300.0, m_med=600.0, g_chi=0.8))
    assert found.route.startswith("tree + loop (the coloured partners")
    assert found.nucleon.c1_p == pytest.approx(library.c1_p, rel=1e-9)
    assert found.nucleon.c4_p == pytest.approx(library.c4_p, rel=1e-9)


def test_directdm_carries_the_full_operator_set():
    """Das et al.'s BP2 through DirectDM: O₁ within 1% of the closed form (DirectDM's running and inputs)."""
    from adroit.library.interactions import quark_level as ql
    if not ql.available():
        pytest.skip("DirectDM is not set up")
    e = next(x for x in zoo.entries() if x.id == "singlet_fermion_scalar_mediator_das")
    t = next(x for x in e.targets if x.quantity == "sigma_si_cm2")
    engine, point = zoo._generic(e, t)
    o1 = next(c for c in engine.interaction(point).coefficients if c.operator == 1 and c.q_power == 0)
    assert o1.proton == pytest.approx(engine.nucleon(point).c1_p, rel=0.01)


def test_a_pseudo_dirac_fermion_scatters_inelastically():
    """A Dirac fermion with a Majorana mass of 50 keV and a vector Z′ to quarks: two Majorana states 100 keV apart
    with an off-diagonal Z′ coupling, so the scattering is inelastic only (the physical construction)."""
    fields = [{"name": "psi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1},               # mass by terms
              {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 300.0},
              {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R",
               "charges": {"su3": "3", "hypercharge": 2 / 3}}]
    terms = [{"fields": [{"field": "psi", "conjugate": True}, {"field": "psi"}], "lorentz": "scalar", "coupling": "-M"},
             {"fields": [{"field": "psi"}, {"field": "psi"}], "lorentz": "scalar", "coupling": "-d/2", "plus_hc": True},
             {"fields": [{"field": "psi", "conjugate": True}, {"field": "psi"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": "g"},
             {"fields": [{"field": "uR", "conjugate": True}, {"field": "uR"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": "g"}]
    spec = ModelSpec.model_validate({"name": "pd", "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "g", "value": 0.2},
                                                   {"name": "M", "value": 100.0, "mass_dimension": 1},
                                                   {"name": "d", "value": 50e-6, "mass_dimension": 1}]})
    engine = GenericModel.of(spec, scan="M", sommerfeld=False)
    p = engine.point()
    assert engine.scattering(p).route == "inelastic" and engine.dd(p) == ("inelastic", 0.0)


# --- annihilation today (G6) ---------------------------------------------------------------------------------------

def _library_and_generic(entry_id: str, k: int):
    e = next(x for x in zoo.entries() if x.id == entry_id)
    t = e.targets[k]
    library, lp, _, _ = zoo.mapped(e, t)
    library = library.model_copy(update={o: v for o, v in t.engine_options.items() if o in type(library).model_fields})
    engine, gp = zoo._generic(e, t)
    return library.sigma_v_today(lp, 1e-3), engine.sigma_v_today(gp, 1e-3)


def test_annihilation_today_is_the_librarys_higgs_portal():
    """GAMBIT's Dirac Higgs-portal EFT: every channel the library has, the Higgs's loop-induced γγ and Zγ included."""
    library, generic = _library_and_generic("dirac_fermion_higgs_portal_eft_cpv_gambit", 0)
    for channel in ("W", "Z", "hh", "t", "gamma", "Zgamma"):
        assert generic[channel] == pytest.approx(library[channel], rel=2e-3), channel


def test_annihilation_today_through_two_mixed_scalars():
    """Das et al.'s BP8: W, Z and the Higgs's gluons within 1%, bb̄ within 3% (the library runs m_b to √s)."""
    library, generic = _library_and_generic("singlet_fermion_scalar_mediator_das", 2)
    for channel, tolerance in (("W", 0.01), ("Z", 0.015), ("g", 0.01), ("b", 0.03)):
        assert generic[channel] == pytest.approx(library[channel], rel=tolerance), channel


def test_long_range_effects_today_are_computed_or_named(wino, wino_point):
    """With the Sommerfeld switch on, G8 computes annihilation today; off, the long-range effect is named."""
    assert wino.model_copy(update={"sommerfeld": True}).today_unknown(wino_point) == ""
    assert wino.model_copy(update={"sommerfeld": False}).today_unknown(wino_point).startswith(
        "needs the Sommerfeld effect today (G8)")
    e = next(x for x in zoo.entries() if x.id == "dirac_fermion_higgs_portal_eft_cpv_gambit")
    engine, point = zoo._generic(e, e.targets[0])
    assert engine.today_unknown(point) == ""


def _cascade_model() -> GenericModel:
    """Majorana χ (200 GeV) with a 50 GeV singlet S that mixes with the Higgs: χχ → SS, S → bb̄, ττ̄, …"""
    v, m1, m2, st = 246.21965, 125.09, 50.0, 0.1
    ct = math.sqrt(1 - st ** 2)
    mss, mhh, mhs = m2 ** 2 * ct ** 2 + m1 ** 2 * st ** 2, m1 ** 2 * ct ** 2 + m2 ** 2 * st ** 2, (m2 ** 2 - m1 ** 2) * st * ct
    occ = lambda *xs: [{"field": f.rstrip("*"), "conjugate": f.endswith("*")} for f in xs]   # noqa: E731
    spec = ModelSpec.model_validate({"name": "cascade", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 200.0},
        {"name": "s", "role": "mediator", "spin": 0, "self_conjugate": True},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
        "couplings": [{"name": "mu_hs", "value": mhs / v, "mass_dimension": 1}, {"name": "l_hs", "value": 0.0},
                      {"name": "mu_s2", "value": mss, "mass_dimension": 2}, {"name": "l_h", "value": mhh / (2 * v ** 2)},
                      {"name": "y", "value": 0.8}],
        "terms": [{"fields": occ("H", "H*", "s"), "lorentz": "scalar", "coupling": "-mu_hs"},
                  {"fields": occ("s", "s"), "lorentz": "scalar", "coupling": "-mu_s2/2"},
                  {"fields": occ("H", "H*", "H", "H*"), "lorentz": "scalar", "coupling": "-l_h"},
                  {"fields": occ("chi*", "chi", "s"), "lorentz": "pseudoscalar", "coupling": "-y/2"}]})
    return GenericModel.of(spec, sommerfeld=False)


@pytest.mark.needs("pppc")
def test_a_cascade_through_a_light_scalar_has_a_two_body_spectrum():
    from adroit.constraints import spectra
    engine = _cascade_model()
    p = engine.point()
    rates = engine.sigma_v_today(p, 1e-3)
    pair = next(k for k in rates if " " in k and len(set(k.split())) == 1)                     # χχ → S S
    mixed = next(k for k in rates if " " in k and "h" in k.split())                           # χχ → h S
    assert rates[pair] > 0 and rates[mixed] > 0
    component = engine.cascade(pair, p)
    assert component.mode == "two_body" and len(component.daughters) == 2
    decays = {d.channel: d.branching for d in component.daughters[0].decays}
    assert max(decays, key=decays.get) == "b" and sum(decays.values()) == pytest.approx(1.0)
    assert 0.01 < decays["g"] / decays["b"] < 0.2                  # the Higgs's loop, at 50 GeV
    assert [d.channel for d in engine.cascade(mixed, p).daughters if d.channel] == ["hh"]
    continuum = {k: v for k, v in rates.items() if k not in ("gamma", "Zgamma")}    # lines: not PPPC columns
    request = spectra.from_rates(200.0, continuum, engine, p)
    assert spectra.spectrum(request) is not None
    assert sum(c.mode == "two_body" for c in request.components) == 2
    from adroit.parameter_space.searches import _f_eff
    if _f_eff(100.0) is not None:                             # Slatyer's table, where it is installed
        low, high = engine.cmb_f_eff_range(pair, p)
        assert 0.15 < low <= high < 0.3                       # about b b̄'s 0.21


@pytest.mark.parametrize("which", ["higgs portal", "cascade"])
@pytest.mark.needs("solar_model")
def test_every_search_reads_a_generic_model(which):
    """G6's gate: the scan's full evaluation of a generic point runs every search without an exception."""
    from adroit.parameter_space.scan import evaluate
    if which == "cascade":
        engine = _cascade_model()
        point = engine.point()
    else:
        e = next(x for x in zoo.entries() if x.id == "dirac_fermion_higgs_portal_eft_cpv_gambit")
        engine, point = zoo._generic(e, e.targets[0])
    result = evaluate(engine, point)
    assert result.omega_h2 is not None and "gamma rays (Fermi-LAT dwarfs)" in result.excluded


@pytest.mark.slow
@pytest.mark.skipif(not __import__("adroit.constraints.maddm", fromlist=["available"]).available(),
                    reason="MadGraph and MadDM are not installed")
def test_maddm_gives_the_generic_annihilation_today(tmp_path):
    """D14: MadDM's tree-level σv today, channel by channel, for a Majorana χ with a Higgs-mixed scalar (s-wave WW,
    ZZ, hh, tt̄, bb̄ and the p-wave cascades S S and h S), in our convention (``maddm.relative``)."""
    from adroit.constraints import maddm
    from adroit.model_building import ufo_export as ux
    engine = _cascade_model()
    p = engine.point()
    mb, rules, _ = engine.at(p)
    table = ux.names(rules)
    v, theirs = maddm.indirect(ux.write(rules, tmp_path, "cascade"), table[mb.spectrum.dark_matter().name][0],
                               "cascade_id", tmp_path / "work")
    ours = engine.sigma_v_today(p, v)
    s = next(st.name for st in mb.spectrum.states if st.spin == 0 and st.parity == 1 and st.name != "h")
    finals = maddm.MADDM_FINALS | {f"{table[s][0]}{table[s][0]}": f"{s} {s}", f"h{table[s][0]}": f"h {s}"}
    assert set(theirs) <= set(finals)
    for final, value in theirs.items():
        if value > 1e-6 * sum(theirs.values()):
            assert ours[finals[final]] == pytest.approx(value, rel=1e-3), final


def test_the_w_and_z_take_the_measured_widths():
    """As the library's Higgs: the tree-level widths into SM states scaled to the measured ones (the far tail of an
    off-shell W or Z scales with its width)."""
    from adroit.constraints import higgs
    e = next(x for x in zoo.entries() if x.id == "dirac_fermion_higgs_portal_eft_cpv_gambit")
    engine, point = zoo._generic(e, e.targets[0])
    widths = {x.name: x.width for x in engine.at(point)[1].particles}
    assert widths["W"] == pytest.approx(higgs.GAMMA_W, rel=1e-3) and widths["Z"] == pytest.approx(higgs.GAMMA_Z, rel=1e-3)


def test_the_off_shell_rate_is_right_at_the_initial_threshold():
    """σ_off grows as 1/β at the pair's own threshold; its table must follow it (G7's held-out run: the inert
    doublet's H₀H₀ → WW* at 73 GeV was twenty times too large at u = 10⁻³ when σ itself was interpolated)."""
    from adroit.constraints import tree
    from adroit.parameter_space.portals.ufo import off_shell_sigma
    e = next(x for x in zoo.entries() if x.id == "inert_doublet_kalinowski")
    engine, p = zoo._generic(e, e.targets[0])
    mb, rules, model = engine.at(p)
    a = mb.spectrum.dark_matter().name
    m = model.particles[a].mass
    finals = [f for f in final_states(model, a, a) if f in (("W", "W~"), ("Z", "Z"))]
    table = gm._pair_sigma(model, a, a, finals, gm._s_channel(model, a, a, rules))
    for u in (5e-4, 3e-3):
        s = (2 * m * (1 + u)) ** 2
        direct = sum(off_shell_sigma(tree.Process(model, a, a, *f), s) for f in finals)
        assert float(table(np.array([s]))[0]) == pytest.approx(direct, rel=1e-3)



def test_the_off_shell_integral_is_its_nodes_summed_one_by_one():
    """F2: ``off_shell_sigma`` evaluates its Breit–Wigner nodes in one stacked call; the result is the earlier loop's,
    ``sigma`` at each node weighted and summed (10⁻¹²), for the vector Higgs portal's W W* and Z Z* near the Higgs
    pole (a development-half model)."""
    from adroit.constraints import tree
    from adroit.parameter_space.portals import ufo

    def by_node(proc, s):
        first, second = proc.p[2:]
        vectors = [x for x in (first, second) if abs(x.pdg) in ufo.OFF_SHELL and x.width > 0]
        root = math.sqrt(s)
        splits = tuple(root - second.mass + k * ufo.POLE_REACH * second.width for k in (-1, 0, 1)) \
            if second in vectors else ()
        total = 0.0
        for m1, w1 in (ufo._breit_wigner(first, root - 1.0, splits) if first in vectors else [(first.mass, 1.0)]):
            if root - m1 - 1e-3 <= 1.0:
                continue
            nodes = ufo._breit_wigner(second, root - m1 - 1e-3)
            total += sum(w1 * w2 * proc.sigma(s, (m1, m2)) for m2, w2 in nodes)
        return total
    e = next(x for x in zoo.entries() if x.id == "vector_higgs_portal_athron")
    engine, p = zoo._generic(e, e.targets[0])
    mb, _, model = engine.at(p)
    a = mb.spectrum.dark_matter().name
    m = model.particles[a].mass
    for final in (("W", "W~"), ("Z", "Z")):
        proc = tree.Process(model, a, a, *final, points=gm.ANGLES)
        for u in (1e-3, 0.05):
            s = (2 * m * (1 + u)) ** 2
            assert ufo.off_shell_sigma(proc, s) == pytest.approx(by_node(proc, s), rel=1e-12)


# --- the closure audit (G12) ------------------------------------------------------------------------------------

def test_below_two_pion_masses_the_dark_matter_annihilates_to_leptons_not_quarks():
    """The audit's G3/G4-1: a 33 MeV dark matter (Feng et al.) had annihilated to free u ū and d d̄ quarks."""
    e = next(x for x in zoo.entries() if x.id == "dark_photon_complex_scalar_feng")
    engine, p = zoo._generic(e, e.targets[0])
    s = (2.02 * p.m_chi) ** 2
    rates = {k: float(np.ravel(v)[0]) for k, v in engine.channels(np.array([s]), p).items()}
    assert rates["e e~"] > 0 and all(rates[k] == 0.0 for k in rates if k.split()[0] in ("u", "d", "s"))
    refused = engine.domain(p.model_copy(update={"m_chi": 0.5}))      # the hadronic window (owner, 2026-10-20)
    assert "the annihilation into hadrons" in refused and "for a vector current" in refused


def test_a_coloured_odd_state_lighter_than_the_dark_matter_is_refused():
    """The audit's G3/G4-2: the stable coloured partner's Ωh² had been reported as the dark matter's."""
    spec = ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
         "mass_gev": 300.0},
        {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 250.0,
         "charges": {"su3": "3", "hypercharge": 2 / 3}},
        {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R",
         "charges": {"su3": "3", "hypercharge": 2 / 3}}],
        "terms": [{"fields": [{"field": "Phi", "conjugate": True}, {"field": "chi", "conjugate": True},
                              {"field": "uR"}], "lorentz": "chiral", "coupling": "0.5", "plus_hc": True}]})
    engine = GenericModel.for_spec(spec)
    assert engine.tied == "Phi" and "charged or coloured" in engine.domain(engine.point())
    assert engine.omega_h2(engine.point()) is None


def test_a_charged_partner_degenerate_at_tree_level_is_not_lighter():
    """The zoo's development half at G12: the complex triplet (Y = 1) is degenerate at tree level, and its neutral
    state is the lightest after the one-loop splitting; G3/G4-2's check had refused it for the tie."""
    from adroit.evaluation import zoo
    e = next(x for x in zoo.entries() if x.id == "complex_scalar_triplet_y1_bottaro")
    engine = GenericModel.of(zoo._spec(e, e.targets[0]))
    assert "charged or coloured" not in engine.domain(engine.point())


def test_m_med_is_a_coordinate_only_where_a_single_mediator_is_tied():
    """The audit's G3/G4-3: a generic-routed model's m_med axis moved nothing; and G3/G4-6: a mediator with no
    stated mass raised a TypeError."""
    from adroit.parameter_space.scan_setup import active_coordinates
    two = ModelSpec.model_validate({"name": "two", "phase": "broken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "A1", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 500.0},
        {"name": "A2", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 700.0}]})
    assert active_coordinates(GenericModel.for_spec(two)) == ["m_chi"]
    massless = two.model_copy(update={"fields": [two.fields[0], two.fields[1].model_copy(update={"mass_gev": None})]})
    assert GenericModel.for_spec(massless).tied == ""
    with pytest.raises(ValueError, match="states no mass"):
        gm._read(massless, "A1")


def test_an_inert_doublet_split_by_100_kev_scatters_inelastically_through_the_z():
    """The audit's G5-2 (G12): the H⁰–A⁰ Z vertex (VSS) was not searched, so the point read "allowed" at 10⁻⁵⁰ cm²."""
    from adroit.parameter_space.portals import generic_dd
    mh, ma, mhp, l345 = 500.0, 500.0001, 510.0, 0.001
    l5, l4 = (mh ** 2 - ma ** 2) / V_EW ** 2, (mh ** 2 + ma ** 2 - 2 * mhp ** 2) / V_EW ** 2

    def occ(*xs):
        return [{"field": f.rstrip("*"), "conjugate": f.endswith("*")} for f in xs]
    terms = [{"fields": occ("p", "p*", "p", "p*"), "lorentz": "scalar", "coupling": "-l2/2"},
             {"fields": occ("H", "H*", "p", "p*"), "lorentz": "scalar", "coupling": "-l3",
              "indices": "H*[i] H[i] p*[j] p[j]"},
             {"fields": occ("H*", "p", "p*", "H"), "lorentz": "scalar", "coupling": "-l4",
              "indices": "H*[i] p[i] p*[j] H[j]"},
             {"fields": occ("H*", "H*", "p", "p"), "lorentz": "scalar", "coupling": "-l5/2", "plus_hc": True,
              "indices": "H*[i] p[i] H*[j] p[j]"}]
    spec = ModelSpec.model_validate({"name": "idm", "phase": "unbroken", "fields": [
        {"name": "p", "role": "dark_matter", "spin": 0, "dark_parity": -1,
         "mass_gev": math.sqrt(mh ** 2 - l345 * V_EW ** 2 / 2), "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
        "terms": terms, "couplings": [{"name": "l2", "value": 1.4}, {"name": "l3", "value": l345 - l4 - l5},
                                      {"name": "l4", "value": l4}, {"name": "l5", "value": l5}]})
    engine = GenericModel.of(spec, sommerfeld=False)
    mb, rules, _ = engine.at(engine.point())
    assert "keV above the dark matter, through Z" in generic_dd.inelastic_partner(mb, rules)


def test_a_lightly_mixed_scalars_width_carries_the_off_shell_sm_channels():
    """The audit's G3/G4-7 (G12): a singlet with a 1.5% H share at 140 GeV kept G2's two-body tree width (4.9e-5 GeV),
    without W*, Z* and gluons; share·Γ_SM(m) + its decays into new states is 1.27e-4 GeV."""
    from adroit.constraints import higgs
    spec = ModelSpec.model_validate({"name": "mix", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 66.0},
        {"name": "s", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 140.0},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
        "couplings": [{"name": "g_chi", "value": 0.005}, {"name": "mu_hs", "value": 5.0, "mass_dimension": 1}],
        "terms": [{"fields": [{"field": "s"}, {"field": "chi", "conjugate": True}, {"field": "chi"}],
                   "lorentz": "scalar", "coupling": "g_chi"},
                  {"fields": [{"field": "H"}, {"field": "H", "conjugate": True}, {"field": "s"}],
                   "lorentz": "scalar", "coupling": "-mu_hs"}]})
    engine = GenericModel.of(spec, sommerfeld=False)
    mb, rules, _ = engine.at(engine.point())
    state = next(st for st in mb.spectrum.states if st.spin == 0 and st.parity == 1 and abs(st.mass_gev - 125.09) > 5)
    share = state.composition.get("H[m=-0.5,re]", 0.0) + state.composition.get("h[m=0,r]", 0.0)
    record = next(x for x in rules.particles if x.name == state.name)
    assert 1e-6 < share < 0.5
    assert record.width == pytest.approx(share * float(higgs.width(state.mass_gev)) + gm._dark_width(rules, state.name),
                                         rel=1e-9)


def test_a_dark_matter_with_nothing_to_annihilate_to_is_refused():
    """The audit's G3/G4-9: with its only interaction lost the generic route had returned Ωh² = 3.8 × 10⁷."""
    spec = ModelSpec.model_validate({"name": "alone", "phase": "broken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0}]})
    engine = GenericModel.of(spec)
    assert "no annihilation channel" in engine.domain(engine.point())


def test_the_searches_read_the_dark_matters_physical_mass():
    """The audit's G3/G4-4 (G12): a real singlet with λ = 0.1 and a stated (Lagrangian) 100 GeV is physically at
    114.15 GeV after the vacuum shift; the limits had been read at 100 GeV."""
    from adroit.parameter_space import searches
    spec = ModelSpec.model_validate({"name": "singlet", "phase": "unbroken", "fields": [
        {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
        "couplings": [{"name": "lam", "value": 0.1}],
        "terms": [{"fields": [{"field": "H", "conjugate": True}, {"field": "H"}, {"field": "S"}, {"field": "S"}],
                   "lorentz": "scalar", "coupling": "-lam/2"}]})
    engine = GenericModel.of(spec, sommerfeld=False)
    p = engine.point()
    assert p.m_chi == 100.0
    assert searches.dm_mass(engine, p) == pytest.approx(math.sqrt(100.0 ** 2 + 0.1 * V_EW ** 2 / 2), rel=1e-6)


def test_a_p_wave_sigma_beta_is_followed_between_the_nodes():
    """The audit's G4-11 (G12): σβ ∝ u (a p-wave), u² and √u are interpolated exactly at the nodes' geometric
    midpoints (a p-wave had been 2% low at u = 0.01). Poles keep their own nodes (their tests: Choubey et al.'s Δ⁰)."""
    from adroit.parameter_space.portals import generic as gm
    threshold = 200.0
    nodes = gm._nodes(threshold, threshold, [])
    mid = np.sqrt(nodes[1:-1] * nodes[2:])
    s = (threshold * (1 + mid)) ** 2
    beta = np.sqrt(1 - threshold ** 2 / s)
    for power in (1, 2, 0.5):
        sigma = gm._interpolated(nodes, nodes ** power, threshold, 100.0, 100.0)
        assert np.allclose(sigma(s) * beta, mid ** power, rtol=1e-9)

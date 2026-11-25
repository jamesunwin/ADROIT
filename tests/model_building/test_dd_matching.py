"""Direct detection at tree level (G5): G2's vertices onto DirectDM's basis, against the library's closed forms, the
Fierz signs against the tree engine's own interference, and the nucleon couplings."""

import math

import pytest

from adroit.constraints import tree
from adroit.core.model_spec import ModelSpec
from adroit.evaluation import zoo
from adroit.model_building import dd_matching as dd
from adroit.model_building import feynman as fy
from adroit.model_building import spectrum as sp
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.generic import tree_model

H = {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}


def _rules(data: dict):
    mb = sp.compute(ModelSpec.model_validate(data))
    return mb, fy.feynman_rules(mb)


def test_a_real_scalar_higgs_portal_is_the_librarys():
    """V ⊃ ½λ S²|H|²: c₁ = λ f_N m_N/(2m_h² m_S), at the model's own physical mass (m_S² = μ² + λv²/2)."""
    from adroit.parameter_space.portals.higgs import HiggsPortalScalar
    mb, rules = _rules({"name": "s", "phase": "unbroken", "fields": [
        {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1, "mass_gev": 300.0},
        H], "couplings": [{"name": "lam", "value": 0.1}],
        "terms": [{"fields": [{"field": "S"}, {"field": "S"}, {"field": "H", "conjugate": True}, {"field": "H"}],
                   "lorentz": "scalar", "coupling": "-lam/2"}]})
    m = dd.match(mb, rules)
    library = HiggsPortalScalar(name="h").nucleon(Point(m_chi=m.dm_mass, m_med=1.0, g_chi=0.1))
    assert dd.nucleon_couplings(m)["c1_p"] == pytest.approx(library.c1_p, rel=0.01)       # F_N 0.307 against 0.3066
    assert m.coefficients["C65"] == pytest.approx(-m.coefficients["C63u"])            # the top, as gluons


@pytest.mark.parametrize("entry_id,options", [("dirac_fermion_higgs_portal_eft_cpv_gambit", ("xi",)),
                                              ("vector_higgs_portal_athron", ()),
                                              ("singlet_fermion_scalar_mediator_das", ())])
def test_the_library_controls_agree_at_tree_level(entry_id, options):
    """The development half's tree-level controls: the generic c₁ᵖ within 1% of the library engine's (the library
    takes m_h = 125.09 GeV)."""
    e = next(x for x in zoo.entries() if x.id == entry_id)
    for t in e.targets:
        library, point, _, _ = zoo.mapped(e, t)
        library = library.model_copy(update={k: v for k, v in t.engine_options.items() if k in options})
        engine, gp = zoo._generic(e, t)
        mb, rules, _ = engine.at(gp)
        assert dd.nucleon_couplings(dd.match(mb, rules))["c1_p"] == pytest.approx(library.nucleon(point).c1_p, rel=0.01)


def _partner_model(majorana: bool, zp: float, y: float):
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0,
               "self_conjugate": majorana},
              {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 500.0,
               "charges": {"su3": "3", "hypercharge": 2 / 3}},
              {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R",
               "charges": {"su3": "3", "hypercharge": 2 / 3}},
              {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 500.0}]
    terms = [{"fields": [{"field": "Phi", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": "uR"}],
              "lorentz": "chiral", "coupling": "y", "plus_hc": True},
             {"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Zp"}],
              "lorentz": "axial" if majorana else "vector", "coupling": "gz"},
             {"fields": [{"field": "uR", "conjugate": True}, {"field": "uR"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": "gz"}]
    return _rules({"name": "f", "phase": "unbroken", "fields": fields, "terms": terms,
                   "couplings": [{"name": "y", "value": y}, {"name": "gz", "value": zp}]})


@pytest.mark.parametrize("majorana,key", [(False, "C61u"), (True, "C64u")])
def test_the_partners_fierz_sign_is_the_tree_engines(majorana, key):
    """χu → χu at low energy through a Z′ and a right-handed coloured partner: the full theory's interference has the
    sign the matched coefficients predict (both in C61 for Dirac χ, both in C64 for Majorana)."""
    sigma, coefficient = {}, {}
    for label, zp, y in (("z", 0.3, 0.0), ("p", 0.0, 1.0), ("both", 0.3, 1.0)):
        mb, rules = _partner_model(majorana, zp, y)
        dm = mb.spectrum.dark_matter().name
        sigma[label] = tree.Process(tree_model(rules), dm, "u", dm, "u").sigma(101.0 ** 2)
        coefficient[label] = dd.match(mb, rules).coefficients.get(key, 0.0)
    interference = sigma["both"] - sigma["z"] - sigma["p"]
    assert math.copysign(1, interference) == math.copysign(1, coefficient["z"] * coefficient["p"])
    assert coefficient["both"] == pytest.approx(coefficient["z"] + coefficient["p"])


def test_a_majorana_partners_coefficients_are_the_t_channel_engines():
    """Majorana χ with a partner of u_R: c₄ = 4·2g·Δu with g = y²/8(m_φ² − m_χ²), as ``portals.tchannel``."""
    from adroit.constraints import spin1
    mb, rules = _partner_model(True, 0.0, 1.0)
    m = dd.match(mb, rules)
    g = 1.0 / (8 * (500.0 ** 2 - 100.0 ** 2))
    assert "C61u" not in m.coefficients and m.coefficients["C64u"] == pytest.approx(2 * g)
    assert dd.nucleon_couplings(m)["c4_p"] == pytest.approx(4 * 2 * g * spin1.DMWG_2016.delta_u)


def test_scalar_and_vector_parts_add_in_rate_nucleus_by_nucleus_for_a_dirac_relic():
    """Half the relic is antiparticles, whose vector coupling has the other sign, so a nucleus's rate is
    (Z S_p + N S_n)² + (Z V_p + N V_n)². The audit's G5-1 (G12): S and V had been combined nucleon by nucleon,
    ±√(S² + V²), low by up to 7 for a Higgs-like S with a Z-like V (V_p ≈ 0.076 S, V_n = −S)."""
    from adroit.parameter_space import dd_channels
    from adroit.physics import conventions
    s_part, v_p, v_n, mass = 1e-8, 0.076e-8, -1.05e-8, 100.0
    (channel,) = dd_channels.channels_of(s_part, s_part, 0.0, 0.0, mass, c1_odd=(v_p, v_n))
    assert (channel.c_p, channel.c_n, channel.odd_p, channel.odd_n) == (s_part, s_part, v_p, v_n)
    f = 54 / 131                                                        # xenon's Z/A
    rate = conventions.sigma_si_cm2(f * channel.c_p + (1 - f) * channel.c_n, mass) + \
        conventions.sigma_si_cm2(f * channel.odd_p + (1 - f) * channel.odd_n, mass)
    old_p, old_n = math.hypot(s_part, v_p), -math.hypot(s_part, v_n)    # the old per-nucleon ±√(S² + V²)
    assert rate > 3 * conventions.sigma_si_cm2(f * old_p + (1 - f) * old_n, mass)


def test_a_mixed_dirac_states_z_exchange_is_yagunas_eq_9():
    """A Dirac singlet S and a Dirac doublet ψ (Y = −½) with chiral Yukawas y₁ψ̄_L H̃ S_R and y₂ψ̄_R H̃ S_L (Yaguna,
    arXiv:1510.06151): Z exchange gives σ_N = G_F²μ²/8π (sin²θ_L + sin²θ_R)² [(1 − 4s_W²)Z − (A − Z)]² per nucleon
    (eq. 9), with θ_L, θ_R from eqs. (5)–(6). The vector part of the matching (C61) reproduces it on protons and
    neutrons; the Higgs exchange, which eq. (9) leaves out, is the scalar part."""
    from adroit.model_building.gauge_basis import M_W, M_Z, V_EW
    ms, md, y1, y2 = 200.0, 300.0, 0.05, 0.08
    occ = lambda *xs: [{"field": f.rstrip("*"), "conjugate": f.endswith("*")} for f in xs]   # noqa: E731
    mb, rules = _rules({"name": "sd", "phase": "unbroken", "fields": [
        {"name": "chi0", "role": "dark_matter", "spin": 0.5, "mass_gev": ms, "dark_parity": -1},
        {"name": "N", "role": "dark_matter", "spin": 0.5, "mass_gev": md, "dark_parity": -1,
         "charges": {"su2": 2, "hypercharge": -0.5}}, H],
        "couplings": [{"name": "y1", "value": y1}, {"name": "y2", "value": y2}],
        "terms": [{"fields": occ("N*", "H*", "chi0"), "lorentz": "chiral", "coupling": "-y1", "plus_hc": True,
                   "indices": "eps[i,j] N*[i] H*[j] chi0"},
                  {"fields": occ("chi0*", "N", "H"), "lorentz": "chiral", "coupling": "-y2", "plus_hc": True,
                   "indices": "eps[i,j] N[i] H[j] chi0*"}]})
    v = V_EW
    theta_l = 0.5 * math.atan(math.sqrt(2) * v * (ms * y1 + md * y2) / (md ** 2 - ms ** 2 + v ** 2 * (y1 ** 2 - y2 ** 2) / 2))
    theta_r = 0.5 * math.atan(math.sqrt(2) * v * (ms * y2 + md * y1) / (md ** 2 - ms ** 2 + v ** 2 * (y2 ** 2 - y1 ** 2) / 2))
    mixing = math.sin(theta_l) ** 2 + math.sin(theta_r) ** 2
    g_f, s2 = 1 / (math.sqrt(2) * v ** 2), 1 - (M_W / M_Z) ** 2
    m = dd.match(mb, rules)
    c = m.coefficients
    vector = {"p": 2 * c["C61u"] + c["C61d"], "n": c["C61u"] + 2 * c["C61d"]}
    # σ = c₁²μ²/π (ADROIT) against eq. (9) with A = 1: |c₁| = G_F (sin²θ_L + sin²θ_R) |charge| / (2√2)
    for n, charge in (("p", 1 - 4 * s2), ("n", -1.0)):
        assert abs(vector[n]) == pytest.approx(g_f * mixing * abs(charge) / (2 * math.sqrt(2)), rel=1e-9), n
    assert mb.spectrum.dark_matter().mass_gev == pytest.approx(ms, rel=0.05) and 0.01 < mixing < 0.2

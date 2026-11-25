"""Feynman rules in the mass basis (G2): the Standard Model's couplings and widths, and the dark sector's vertices
against their closed forms."""

import math

import pytest

from adroit.core.model_spec import ModelSpec
from adroit.evaluation import core, zoo
from adroit.model_building import feynman as fy
from adroit.model_building import spectrum as sp
from adroit.model_building.gauge_basis import G2, M_H, M_W, M_Z, V_EW, GaugeBasisError

CW = M_W / M_Z


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
SW2 = 1 - CW ** 2
E = G2 * math.sqrt(SW2)


def rules(fields, terms=(), couplings=(), phase="unbroken"):
    spec = ModelSpec.model_validate({"name": "t", "phase": phase, "fields": list(fields), "terms": list(terms),
                                     "couplings": list(couplings)})
    return fy.feynman_rules(sp.compute(spec))


def table(r):
    return {(v.kind, v.legs): v for v in r.vertices}


DIRAC = {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0}


def test_the_standard_models_couplings():
    t = table(rules([DIRAC]))
    assert t[("SSS", ("h", "h", "h"))].c == pytest.approx(-3 * M_H ** 2 / V_EW)
    assert t[("SSSS", ("h", "h", "h", "h"))].c == pytest.approx(-3 * M_H ** 2 / V_EW ** 2)
    assert t[("VVS", ("W", "W~", "h"))].c == pytest.approx(2 * M_W ** 2 / V_EW)
    assert t[("VVS", ("Z", "Z", "h"))].c == pytest.approx(2 * M_Z ** 2 / V_EW)
    assert t[("VVV", ("W", "W~", "A"))].c == pytest.approx(-E)
    assert t[("VVV", ("W", "W~", "Z"))].c == pytest.approx(-G2 * CW)
    zee = t[("FFV", ("e", "e~", "Z"))]                        # canonical order flips the vector part's sign
    assert -zee.c == pytest.approx(G2 / CW * (-0.25 + SW2)) and zee.c2 == pytest.approx(G2 / CW * 0.25)
    assert -t[("FFV", ("e", "e~", "A"))].c == pytest.approx(-E)
    w = t[("FFV", ("e", "nu_e~", "W"))]                      # ν̄γ(g/√2)P_L e W⁺, slots in canonical order
    assert -w.c == pytest.approx(G2 / (2 * math.sqrt(2))) and w.c2 == pytest.approx(-G2 / (2 * math.sqrt(2)))
    assert t[("FFS", ("t", "t~", "h"))].c == pytest.approx(-172.5 / V_EW)


def test_the_standard_models_widths_at_tree_level():
    w = {p.name: p.width for p in rules([DIRAC]).particles}
    assert w["W"] == pytest.approx(9 * G2 ** 2 * M_W / (48 * math.pi), rel=2e-3)     # nine massless doublets
    assert w["Z"] == pytest.approx(2.44, rel=0.01)
    def pair(m_yukawa: float, m_pole: float, colours: int) -> float:              # h → f f̄ at tree level
        return colours * M_H * m_yukawa ** 2 / (8 * math.pi * V_EW ** 2) * (1 - 4 * m_pole ** 2 / M_H ** 2) ** 1.5
    expected = pair(fy.yukawa_mass("b"), 4.7, 3) + pair(fy.yukawa_mass("c"), 1.27, 3) + \
        pair(1.77686, 1.77686, 1) + pair(0.10566, 0.10566, 1)
    assert w["h"] == pytest.approx(expected, rel=0.01)      # b and c with their MS-bar masses at m_h, as the library


@pytest.mark.parametrize("fields,expected", [
    ({"self_conjugate": True, "charges": {"su2": 3}}, {("chi+~", "chi0", "W"): G2, ("chi+~", "chi+", "A"): E,
                                                       ("chi+~", "chi+", "Z"): G2 * CW}),
    ({"charges": {"su2": 2, "hypercharge": 0.5}}, {("chi+~", "chi0", "W"): G2 / math.sqrt(2),
                                                   ("chi+~", "chi+", "A"): E,
                                                   ("chi0~", "chi0", "Z"): G2 / (2 * CW),
                                                   ("chi+~", "chi+", "Z"): G2 / CW * (0.5 - SW2)})])
def test_electroweak_multiplets_couple_with_their_gauge_charges(fields, expected):
    r = rules([{**DIRAC, "mass_gev": 1000.0, **fields}])
    t = {frozenset(v.legs): v for v in r.vertices if v.kind == "FFV"}
    for legs, size in expected.items():
        assert abs(complex(t[frozenset(legs)].c)) == pytest.approx(size)


def test_a_majorana_higgs_portal_and_its_two_higgs_term():
    """L ⊃ −½(λ/Λ)[cos ξ χ̄χ + sin ξ χ̄iγ⁵χ](v h + ½h²): the identical-field 2 cancels the ½."""
    lam, xi = 6.3e-6, 1.41
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 61.03}, {"name": "h", "role": "standard_model", "spin": 0, "self_conjugate": True}]
    occ = [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "h"}]
    terms = [{"fields": occ, "lorentz": "scalar", "coupling": "-l*cos(x)*v/2"},
             {"fields": occ, "lorentz": "pseudoscalar", "coupling": "-l*sin(x)*v/2"},
             {"fields": occ + [{"field": "h"}], "lorentz": "scalar", "coupling": "-l*cos(x)/4"}]
    t = table(rules(fields, terms, [{"name": "l", "value": lam, "mass_dimension": -1}, {"name": "x", "value": xi}],
                    phase="broken"))
    ffs = t[("FFS", ("chi0", "chi0", "h"))]
    assert ffs.c == pytest.approx(-lam * math.cos(xi) * 246.22, rel=1e-5)
    assert ffs.c2 == pytest.approx(-lam * math.sin(xi) * 246.22, rel=1e-5)
    assert t[("FFSS", ("chi0", "chi0", "h", "h"))].c == pytest.approx(-lam * math.cos(xi))


def test_mixing_dark_fermions_couple_through_their_angles():
    """A singlet–doublet Dirac pair (``singlet_doublet``): the doublet-like N⁰ and the singlet-like χ share the Z
    and W couplings by θ."""
    t = {frozenset(v.legs): v for v in fy.feynman_rules(sp.compute(singlet_doublet())).vertices if v.kind == "FFV"}
    st, ct = 0.2, math.sqrt(1 - 0.2 ** 2)
    z = G2 / (2 * CW)
    assert abs(t[frozenset(("chi00", "chi00~", "Z"))].c) == pytest.approx(z * st ** 2, rel=1e-6)
    assert abs(t[frozenset(("N0", "N0~", "Z"))].c) == pytest.approx(z * ct ** 2, rel=1e-6)
    assert abs(t[frozenset(("N-", "chi00~", "W"))].c) == pytest.approx(G2 / math.sqrt(2) * st, rel=1e-6)


def test_a_lepton_partners_yukawa_is_right_handed():
    e = next(x for x in zoo.entries() if x.id == "real_scalar_dm_vectorlike_lepton_giacchino")
    t = table(fy.feynman_rules(sp.compute(zoo._spec(e, e.targets[0]))))
    v = t[("FFS", ("Psi+", "e", "S0"))]
    cl, cr = v.c - 1j * v.c2, v.c + 1j * v.c2
    assert abs(cl) < 1e-12 and abs(cr) == pytest.approx(1.17)


def test_every_development_model_gets_its_rules():
    for entry in zoo.entries():
        if core.half_of(zoo.NAME, entry.id) is core.Half.development:
            r = fy.feynman_rules(sp.compute(zoo._spec(entry, entry.targets[0])))
            assert r.vertices and any(p.parity == -1 for p in r.particles)


def _coloured_partner():
    """Majorana χ with a coloured scalar partner, y Φ†χ̄ u_R + h.c.; the electroweak vertices are dropped below."""
    return rules([{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
                   "mass_gev": 300.0},
                  {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 360.0,
                   "charges": {"su3": "3", "hypercharge": 2 / 3}},
                  {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R",
                   "charges": {"su3": "3", "hypercharge": 2 / 3}}],
                 [{"fields": [{"field": "Phi", "conjugate": True}, {"field": "chi", "conjugate": True},
                              {"field": "uR"}], "lorentz": "chiral", "coupling": "y", "plus_hc": True}],
                 [{"name": "y", "value": 0.9}])


@pytest.mark.parametrize("root_s", [721.0, 900.0, 2000.0])
def test_the_strong_interaction_matches_the_hand_written_processes(root_s):
    """φφ* → gg, φφ* → uū, χφ → ug against ``constraints.processes`` (gauge cancellation needs the right signs)."""
    from adroit.constraints import processes, tree
    from adroit.parameter_space.portals.generic import tree_model
    r = _coloured_partner()
    m = tree_model(r)
    m.vertices = [v for v in m.vertices if not set(v.legs) & {"A", "Z", "W", "W~"}]
    phi, s = "Phi(+0.667)", root_s ** 2
    pairs = [(tree.Process(m, phi, phi + "~", "g", "g").sigma(s),
              processes.partners_to_gauge_bosons(s, 360.0, r.g_s, True)),
             (tree.Process(m, phi, phi + "~", "u", "u~").sigma(s),
              processes.partners_to_fermions(s, 360.0, 0.0, r.g_s, 1.0, True, y=0.9, m_chi=300.0)),
             (tree.Process(m, "chi0", phi, "u", "g").sigma(s),
              processes.dm_partner_to_fermion_boson(s, 300.0, 360.0, 0.0, 0.9, r.g_s, 1.0, True))]
    for ours, hand in pairs:
        assert ours == pytest.approx(hand, rel=1e-4)


def test_a_majorana_octet_is_madgraphs_gluino():
    """χχ → gg and (without squarks) χχ → uū for a Majorana octet at the MSSM fixture's gluino mass and g_s."""
    import gzip
    import json
    from pathlib import Path
    from adroit.constraints import tree, ufo_model
    from adroit.parameter_space.portals.generic import tree_model
    path = Path(__file__).parents[1] / "constraints" / "data" / "g3_ufo_MSSM_SLHA2.json.gz"
    mssm = ufo_model.to_model(json.load(gzip.open(path)), full_colour=True)[0]
    mssm.vertices = [v for v in mssm.vertices if not ("go" in v.legs and v.kind == "FFS")]
    m_go = mssm.particles["go"].mass
    g_s = next(abs(v.c) for v in mssm.vertices if v.kind == "VVV" and v.legs == ("g", "g", "g"))
    spec = ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
         "mass_gev": m_go, "charges": {"su3": "8"}}]})
    m = tree_model(fy.feynman_rules(sp.compute(spec), g_s=g_s))
    s = (3 * m_go) ** 2
    for final in (("g", "g"), ("u", "u~")):
        assert tree.Process(m, "chi0", "chi0", *final).sigma(s) == pytest.approx(
            tree.Process(mssm, "go", "go", *final).sigma(s), rel=1e-4)


def test_a_fermions_two_body_width_is_the_tops():
    """Γ(t → W⁺b) = G_F m_t³/(8π√2) (1 − x)²(1 + 2x), x = m_W²/m_t², with m_b → 0."""
    r = rules([DIRAC])
    v = next(v for v in r.vertices if v.kind == "FFV" and set(v.legs) == {"b", "t~", "W"})
    k = v.legs.index("t~")
    masses = [{"b": 0.0, "t~": 172.5, "W": M_W}[x] for x in v.legs]
    g_f = G2 ** 2 / (4 * math.sqrt(2) * M_W ** 2)
    x = (M_W / 172.5) ** 2
    expected = g_f * 172.5 ** 3 / (8 * math.pi * math.sqrt(2)) * (1 - x) ** 2 * (1 + 2 * x)
    assert fy.two_body_width(v, k, masses) == pytest.approx(expected, rel=1e-6)


def _right_handed_current(generations: int):
    spec = ModelSpec.model_validate({"name": "zp", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 500.0},
        {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 2000.0},
        {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": generations,
         "charges": {"su3": "3", "hypercharge": 2 / 3}}],
        "terms": [{"fields": [{"field": "chi"}, {"field": "chi"}, {"field": "Zp"}], "lorentz": "axial", "coupling": "g"},
                  {"fields": [{"field": "uR", "conjugate": True}, {"field": "uR"}, {"field": "Zp"}],
                   "lorentz": "vector", "coupling": "g"}],
        "couplings": [{"name": "g", "value": 0.3}]})
    rules = fy.feynman_rules(sp.compute(spec))
    return {v.legs[0]: v for v in rules.vertices if v.kind == "FFV" and "Zp" in v.legs and v.legs[0] in "uct"}


def test_a_three_generation_right_handed_field_couples_every_flavour():
    """uR declared with three generations, as the Standard Model's own (``spec.SM_FIELDS``), is u, c and t; with
    one generation it is the up quark alone."""
    three, one = _right_handed_current(3), _right_handed_current(1)
    assert set(three) == {"u", "c", "t"} and set(one) == {"u"}
    assert all(abs(three[q].c - one["u"].c) < 1e-12 and abs(three[q].c2 - one["u"].c2) < 1e-12 for q in three)


def test_sm_fermion_names_are_read_or_refused_by_name():
    assert fy.sm_names("QL") == (fy.GENERIC["q"], "L")
    assert fy.sm_names("dR", 3) == (["d", "s", "b"], "R")
    assert fy.sm_names("Lmu") == (["mu", "nu_mu"], "L") and fy.sm_names("L_tau") == (["tau", "nu_tau"], "L")
    with pytest.raises(GaugeBasisError, match="one generation or three"):
        fy.sm_names("muR", 3)
    with pytest.raises(GaugeBasisError, match="not a Standard Model fermion"):
        fy.sm_names("quark")


def test_a_dirac_fermion_written_as_two_weyl_fields_has_the_four_component_current():
    """η (charge +1) and ξ (charge −1), left-handed, with the Dirac mass M ηξ + h.c. and the currents g η†σ̄η A′ −
    g ξ†σ̄ξ A′, are the four-component Ψ = (η, ξ†) with M Ψ̄Ψ and g Ψ̄γΨ A′."""
    from adroit.model_building import equivalence
    vector = {"name": "Ap", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 30.0}
    weyl = ModelSpec.model_validate({"name": "weyl", "phase": "broken", "fields": [
        {"name": "eta", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1},
        {"name": "xi", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1}, vector],
        "couplings": [{"name": "g", "value": 0.3}],
        "terms": [{"fields": [{"field": "eta"}, {"field": "xi"}], "lorentz": "scalar", "coupling": "-10.0",
                   "plus_hc": True},
                  {"fields": [{"field": "eta", "conjugate": True}, {"field": "eta"}, {"field": "Ap"}],
                   "lorentz": "vector", "coupling": "g"},
                  {"fields": [{"field": "xi", "conjugate": True}, {"field": "xi"}, {"field": "Ap"}],
                   "lorentz": "vector", "coupling": "-g"}]})
    dirac = ModelSpec.model_validate({"name": "dirac", "phase": "broken", "fields": [
        {"name": "psi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 10.0}, vector],
        "couplings": [{"name": "g", "value": 0.3}],
        "terms": [{"fields": [{"field": "psi", "conjugate": True}, {"field": "psi"}, {"field": "Ap"}],
                   "lorentz": "vector", "coupling": "g"}]})
    check = equivalence.compare(weyl, dirac)
    assert check.equal, check.differences


def test_a_second_doublets_type_ii_yukawas():
    """The owner (2026-10-15): a second doublet H₂ (no vacuum value) with Type-II couplings in the Higgs basis,
    (√2 m_d/v) tan β Q̄H₂d_R − (√2 m_u/v) cot β Q̄H̃₂u_R + h.c.: its CP-odd state couples to b̄iγ⁵b with m_b tan β/v and
    to t̄iγ⁵t with m_t cot β/v; H₂⁺ t̄(√2 m_t cot β/v P_L + √2 m_b tan β/v P_R)b. The masses are the Yukawas'
    (m_b running to m_h, as h's own: the audit's G1-12, G12)."""
    tanb = 5.0
    spec = ModelSpec.model_validate({"name": "thdm", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "H2", "role": "other", "spin": 0, "mass_gev": 500.0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "qL", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
         "charges": {"su3": "3", "su2": 2, "hypercharge": 1 / 6}},
        {"name": "dR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"su3": "3", "hypercharge": -1 / 3}},
        {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"su3": "3", "hypercharge": 2 / 3}}],
        "couplings": [{"name": "tanb", "value": tanb}],
        "terms": [{"fields": [{"field": "qL", "conjugate": True}, {"field": "H2"}, {"field": "dR"}], "lorentz": "scalar",
                   "coupling": "sqrt(2)*m_q/v*tanb", "plus_hc": True, "indices": "qL*[i,c] H2[i] dR[c]"},
                  {"fields": [{"field": "qL", "conjugate": True}, {"field": "H2", "conjugate": True}, {"field": "uR"}],
                   "lorentz": "scalar", "coupling": "-sqrt(2)*m_q/v/tanb", "plus_hc": True,
                   "indices": "eps[i,j] qL*[i,c] H2*[j] uR[c]"}]})
    rules = fy.feynman_rules(sp.compute(spec))
    m_b, m_t = fy.yukawa_mass("b"), fy.yukawa_mass("t")
    by = {v.legs: v for v in rules.vertices if v.kind == "FFS"}
    odd = next(k for k in by if k[0] == "b" and abs(by[k].c2) > 0)[2]
    assert abs(by[("b", "b~", odd)].c2) == pytest.approx(m_b * tanb / V_EW, rel=1e-5)
    assert abs(by[("t", "t~", odd)].c2) == pytest.approx(m_t / tanb / V_EW, rel=1e-5)
    v = next(by[k] for k in by if k[0] == "b" and k[1] == "t~")
    left, right = v.c - 1j * v.c2, v.c + 1j * v.c2
    assert abs(left) == pytest.approx(math.sqrt(2) * m_t / tanb / V_EW, rel=1e-5)
    assert abs(right) == pytest.approx(math.sqrt(2) * m_b * tanb / V_EW, rel=1e-5)


def _mediator(terms, extra=()):
    return ModelSpec.model_validate({"name": "m", "phase": "broken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 500.0},
        {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 900.0},
        {"name": "phi", "role": "mediator", "spin": 0, "mass_gev": 300.0},
        {"name": "b", "role": "standard_model", "spin": 0.5}, {"name": "s", "role": "standard_model", "spin": 0.5},
        {"name": "e", "role": "standard_model", "spin": 0.5}, *extra], "terms": terms})


def _occ(*xs):
    return [{"field": x.rstrip("*"), "conjugate": x.endswith("*")} for x in xs]


def test_a_chiral_yukawa_to_an_sm_fermion_is_a_scalar_coupling():
    """The audit's G1-5 (G12): 0.1 S b̄P_R b + h.c. is 0.1 S b̄b; it had been read as a pseudoscalar coupling 0.2."""
    spec = _mediator([{"fields": _occ("b*", "b", "S"), "lorentz": "chiral", "coupling": "0.1", "plus_hc": True}])
    rules = fy.feynman_rules(sp.compute(spec))
    total = [0j, 0j]
    for v in rules.vertices:
        if v.kind == "FFS" and {"b", "b~"} <= set(v.legs) and any(x.startswith("S") for x in v.legs):
            total = [total[0] + v.c, total[1] + v.c2]
    assert abs(total[0] - 0.1) < 1e-12 and abs(total[1]) < 1e-12


@pytest.mark.parametrize("terms", [
    [{"fields": _occ("b*", "s", "S"), "lorentz": "scalar", "coupling": "0.1", "plus_hc": True}],       # S b̄s
    [{"fields": _occ("b*", "s", "Zp"), "lorentz": "vector", "coupling": "0.1", "plus_hc": True}],      # Z′ b̄s
    [{"fields": _occ("chi*", "e", "Zp"), "lorentz": "vector", "coupling": "0.1", "plus_hc": True}],    # χ̄γe Z′
    [{"fields": _occ("chi*", "chi", "b*", "b"), "lorentz": "scalar", "coupling": "0.1"}],              # χ̄χ b̄b
    [{"fields": _occ("phi*", "phi", "Zp"), "lorentz": "vector", "coupling": "0.1"}],                   # a scalar
])
def test_a_term_g2_has_no_rule_for_is_refused_not_dropped(terms):
    """The audit's G1-5 and G3/G4-9 (G12): each of these had been dropped or misread without a word."""
    with pytest.raises(GaugeBasisError):
        sp.compute(_mediator(terms))


def test_a_complex_doublet_yukawa_gives_hermitian_vertices():
    """The audit's G1-6 (G12): with k = 0.1i the real scalars' vertices came out complex and the charged pair was not
    conjugate. A real state's (c, c₂) are real, and (t̄ b H₂⁺) and (b̄ t H₂⁻) are each other's conjugates."""
    spec = ModelSpec.model_validate({"name": "thdm", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "H2", "role": "other", "spin": 0, "mass_gev": 500.0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "qL", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
         "charges": {"su3": "3", "su2": 2, "hypercharge": 1 / 6}},
        {"name": "dR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"su3": "3", "hypercharge": -1 / 3}}],
        "terms": [{"fields": [{"field": "qL", "conjugate": True}, {"field": "H2"}, {"field": "dR"}],
                   "lorentz": "scalar", "coupling": "I*0.1", "plus_hc": True, "indices": "qL*[i,c] H2[i] dR[c]"}]})
    rules = fy.feynman_rules(sp.compute(spec))
    real = {p.name for p in rules.particles if p.spin == 0 and (not p.anti or p.anti == p.name)}
    for v in rules.vertices:
        if v.kind == "FFS" and v.legs[0] == "b" and v.legs[1] == "b~" and v.legs[2] in real:
            assert abs(complex(v.c).imag) < 1e-12 and abs(complex(v.c2).imag) < 1e-12
    up = next(v for v in rules.vertices if v.kind == "FFS" and v.legs[:2] == ("b", "t~"))
    down = next(v for v in rules.vertices if v.kind == "FFS" and v.legs[:2] == ("b~", "t"))
    left_u, right_u = up.c - 1j * up.c2, up.c + 1j * up.c2
    left_d, right_d = down.c - 1j * down.c2, down.c + 1j * down.c2
    assert abs(right_u - complex(left_d).conjugate()) < 1e-12 and abs(left_u - complex(right_d).conjugate()) < 1e-12


def test_the_epsilon_order_of_an_up_type_yukawa_is_read():
    """The audit's G1-7 (G12): writing ε[j,i] instead of ε[i,j] (−Q̄Φ̃u_R) kept the coupling's sign."""
    def top(indices: str) -> complex:
        spec = ModelSpec.model_validate({"name": "thdm", "phase": "unbroken", "fields": [
            {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
            {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}},
            {"name": "H2", "role": "other", "spin": 0, "mass_gev": 500.0, "charges": {"su2": 2, "hypercharge": 0.5}},
            {"name": "qL", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
             "charges": {"su3": "3", "su2": 2, "hypercharge": 1 / 6}},
            {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
             "charges": {"su3": "3", "hypercharge": 2 / 3}}],
            "terms": [{"fields": [{"field": "qL", "conjugate": True}, {"field": "H2", "conjugate": True},
                                  {"field": "uR"}], "lorentz": "scalar", "coupling": "0.1", "plus_hc": True,
                       "indices": indices}]})
        rules = fy.feynman_rules(sp.compute(spec))
        return next(v.c + v.c2 for v in rules.vertices if v.kind == "FFS" and v.legs[:2] == ("t", "t~")
                    and v.legs[2].startswith("H2") and abs(v.c + v.c2) > 1e-9)
    assert abs(top("eps[i,j] qL*[i,c] H2*[j] uR[c]") + top("eps[j,i] qL*[i,c] H2*[j] uR[c]")) < 1e-12


def test_a_term_whose_hypercharges_do_not_cancel_is_refused():
    """The audit's G1-7: φ (Y = 0) χ̄ e_R violates hypercharge and gave a charge-violating vertex."""
    spec = ModelSpec.model_validate({"name": "bad", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 300.0},
        {"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": {"hypercharge": -1.0}}],
        "terms": [{"fields": [{"field": "phi", "conjugate": True}, {"field": "chi", "conjugate": True},
                              {"field": "eR"}], "lorentz": "chiral", "coupling": "0.5", "plus_hc": True}]})
    with pytest.raises(GaugeBasisError, match="hypercharges sum"):
        sp.compute(spec)


def test_a_majorana_pairs_vector_current_needs_an_imaginary_coupling():
    """χ̄₁γ^μχ₂ between two Majorana fields is anti-hermitian: i e_D (Berlin et al.'s) gives the vertex i e_D; a real
    e_D, or e_D with + h.c. (which cancels), is refused, not read silently (the closure audit, G12)."""
    def spec(coupling, plus_hc=False):
        return ModelSpec.model_validate({"name": "idm", "phase": "broken", "fields": [
            {"name": "chi1", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
             "mass_gev": 10.0},
            {"name": "chi2", "role": "other", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 11.0},
            {"name": "Ap", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 30.0}],
            "couplings": [{"name": "e_D", "value": 1.1}],
            "terms": [{"fields": [{"field": "chi1", "conjugate": True}, {"field": "chi2"}, {"field": "Ap"}],
                       "lorentz": "vector", "coupling": coupling, "plus_hc": plus_hc}]})
    rules = fy.feynman_rules(sp.compute(spec("I*e_D")))
    (v,) = [v for v in rules.vertices if v.kind == "FFV" and "Ap" in v.legs]
    assert abs(complex(v.c)) == pytest.approx(1.1) and abs(complex(v.c).real) < 1e-12
    for coupling, plus_hc, match in (("e_D", False, "not hermitian"), ("e_D", True, "vanishes")):
        with pytest.raises(GaugeBasisError, match=match):
            fy.feynman_rules(sp.compute(spec(coupling, plus_hc)))


def test_a_quark_doublet_named_q_and_a_rounded_hypercharge_are_read():
    """G12's live check L9: a doublet Yukawa with the quark doublet named Q (one of G2's names) had been refused as
    flavour-changing, and a partner's hypercharge written 0.6667 for 2/3 refused as not summing to zero."""
    spec = ModelSpec.model_validate({"name": "thdm_q", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "H2", "role": "other", "spin": 0, "mass_gev": 500.0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "Q", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
         "charges": {"su3": "3", "su2": 2, "hypercharge": 1 / 6}},
        {"name": "dR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"su3": "3", "hypercharge": -1 / 3}}],
        "couplings": [{"name": "tanb", "value": 5.0}],
        "terms": [{"fields": [{"field": "Q", "conjugate": True}, {"field": "H2"}, {"field": "dR"}], "lorentz": "scalar",
                   "coupling": "sqrt(2)*m_q/v*tanb", "plus_hc": True, "indices": "Q*[i,c] H2[i] dR[c]"}]})
    rules = fy.feynman_rules(sp.compute(spec))
    assert any(v.kind == "FFS" and v.legs[:2] == ("b", "b~") for v in rules.vertices)
    partner = ModelSpec.model_validate({"name": "tch", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
         "mass_gev": 100.0},
        {"name": "phiu", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 300.0,
         "charges": {"su3": "3", "hypercharge": 0.6667}},
        {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": {"su3": "3", "hypercharge": 2 / 3}}],
        "couplings": [{"name": "y", "value": 1.0}],
        "terms": [{"fields": [{"field": "uR", "conjugate": True}, {"field": "chi"}, {"field": "phiu"}],
                   "lorentz": "chiral", "coupling": "y", "plus_hc": True}]})
    assert fy.feynman_rules(sp.compute(partner)).vertices
    with pytest.raises(GaugeBasisError, match="hypercharges sum"):
        sp.compute(partner.model_copy(update={"fields": [f if f.name != "phiu" else f.model_copy(
            update={"charges": f.charges.model_copy(update={"hypercharge": 0.5})}) for f in partner.fields]}))


def _second_doublet(terms) -> ModelSpec:
    return ModelSpec.model_validate({"name": "thdm_w", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "H2", "role": "other", "spin": 0, "mass_gev": 500.0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "Q", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
         "charges": {"su3": "3", "su2": 2, "hypercharge": 1 / 6}},
        {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"su3": "3", "hypercharge": 2 / 3}},
        {"name": "dR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"su3": "3", "hypercharge": -1 / 3}}], "terms": terms})


def _ffs(spec: ModelSpec) -> dict:
    return {v.legs: (complex(v.c), complex(v.c2)) for v in fy.feynman_rules(sp.compute(spec)).vertices
            if v.kind == "FFS" and v.legs[2].startswith("H2")}


@pytest.mark.parametrize("weyl_up_indices", ["eps[i,j] Q[i,c] H2[j] uR*[c]", ""])
def test_the_generators_weyl_doublet_yukawa_is_its_dirac_conjugate(weyl_up_indices):
    """G12's live check L9: the generator writes a second doublet's Yukawas in Weyl form, k Q d_R^c Φ* and
    k Q u_R^c Φ + h.c., the hermitian conjugates of Q̄Φd_R and Q̄Φ̃u_R; G2 had read only the Dirac form. The Weyl
    form's k is the Dirac form's k*, so a complex coupling checks the conjugation as well as the orientation."""
    dirac = _second_doublet([
        {"fields": _occ("Q*", "H2", "dR"), "lorentz": "scalar", "coupling": "0.1 + 0.03*I", "plus_hc": True,
         "indices": "Q*[i,c] H2[i] dR[c]"},
        {"fields": _occ("Q*", "H2*", "uR"), "lorentz": "scalar", "coupling": "0.2 - 0.05*I", "plus_hc": True,
         "indices": "eps[i,j] Q*[i,c] H2*[j] uR[c]"}])
    weyl = _second_doublet([
        {"fields": _occ("Q", "dR*", "H2*"), "lorentz": "chiral", "coupling": "0.1 - 0.03*I", "plus_hc": True},
        {"fields": _occ("Q", "uR*", "H2"), "lorentz": "chiral", "coupling": "0.2 + 0.05*I", "plus_hc": True,
         "indices": weyl_up_indices}])
    a, b = _ffs(dirac), _ffs(weyl)
    assert a and set(a) == set(b)
    for legs in a:
        assert abs(a[legs][0] - b[legs][0]) < 1e-12 and abs(a[legs][1] - b[legs][1]) < 1e-12, legs


def test_a_weyl_doublet_yukawa_with_the_wrong_scalar_is_refused():
    """In the Weyl form an up-type Yukawa takes Φ itself (Q u_R^c Φ); Q u_R^c Φ* does not conserve hypercharge."""
    with pytest.raises(GaugeBasisError):
        sp.compute(_second_doublet([{"fields": _occ("Q", "uR*", "H2*"), "lorentz": "chiral", "coupling": "0.2",
                                     "plus_hc": True}]))

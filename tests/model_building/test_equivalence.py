"""G10's deterministic check: two writings of a model are the same physics (``model_building.equivalence``)."""

import json

import pytest

from adroit.core.model_spec import ModelSpec
from adroit.evaluation import zoo
from adroit.model_building import equivalence


def _wino() -> ModelSpec:
    e = next(x for x in zoo.entries() if x.id == "wino_majorana_triplet_bottaro")
    return zoo._spec(e, e.targets[0])


def _edited(spec: ModelSpec, **changes) -> ModelSpec:
    data = json.loads(spec.model_dump_json())
    for f in data["fields"]:
        if f["role"] == "dark_matter":
            f.update(changes)
    return ModelSpec.model_validate(data)


def test_a_renamed_model_is_the_same_physics():
    spec = _wino()
    renamed = ModelSpec.model_validate_json(spec.model_dump_json().replace('"chi"', '"W3plet"'))
    assert equivalence.compare(spec, renamed).equal


def test_a_changed_mass_is_found():
    found = equivalence.compare(_wino(), _edited(_wino(), mass_gev=2861.0))
    assert not found.equal and "no counterpart" in found.differences[0]


def test_a_model_g1_refuses_is_a_difference():
    bad = _edited(_wino(), charges={"su2": 3, "hypercharge": 0.5})
    found = equivalence.compare(_wino(), bad)
    assert not found.equal


def test_the_sm_higgs_can_be_set_aside_as_a_diagnosis():
    """A broken-phase Z′ model without H against the same model in the unbroken phase (which has G1's h): they
    differ by the h alone."""
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 300.0},
              {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 1000.0},
              {"name": "q", "role": "standard_model", "spin": 0.5, "charges": {"su3": "3"}}]
    terms = [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": "g"},
             {"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": "g/4"}]
    spec = {"name": "zp", "fields": fields, "terms": terms, "couplings": [{"name": "g", "value": 1.0}]}
    broken = ModelSpec.model_validate(spec | {"phase": "broken"})
    unbroken = ModelSpec.model_validate(spec | {"phase": "unbroken"})
    assert not equivalence.compare(unbroken, broken).equal
    assert equivalence.compare(unbroken, broken, without_sm_higgs=True).equal
    assert equivalence.compare(unbroken, broken, d19=True).equal          # D19: the h meets no new state


def test_d19_compares_an_h_that_couples_to_a_new_state():
    """A scalar singlet with a Higgs portal (h couples to the dark matter) against the same singlet without the
    portal, written in the broken phase: D19 does not set that h aside."""
    singlet = {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 300.0}
    higgs = {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}
    portal = {"fields": [{"field": "H", "conjugate": True}, {"field": "H"}, {"field": "S"}, {"field": "S"}],
              "lorentz": "scalar", "coupling": "-lam/2"}
    with_portal = ModelSpec.model_validate({"name": "a", "phase": "unbroken", "fields": [singlet, higgs],
                                            "terms": [portal], "couplings": [{"name": "lam", "value": 0.1}]})
    bare = ModelSpec.model_validate({"name": "b", "phase": "broken", "fields": [singlet]})
    assert not equivalence.compare(with_portal, bare, d19=True).equal


def test_d19_sets_aside_an_h_joined_to_a_dark_photon_by_kinetic_mixing_alone():
    """A dark photon mixing with hypercharge in the unbroken phase has h Z A′ at O(ε): the h meets a new state only
    through the vector portal, which the extended D19 sets aside (a broken-phase writing has no h)."""
    from adroit.model_building import gauge_basis as gbm
    eps, cw = 1e-3, gbm.M_W / gbm.M_Z
    chi = {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0}
    ad = {"name": "Ad", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 10.0}
    dark = {"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Ad"}], "lorentz": "vector",
            "coupling": "0.5"}
    unbroken = ModelSpec.model_validate({"name": "u", "phase": "unbroken", "fields": [
        chi, ad, {"name": "B", "role": "standard_model", "spin": 1, "self_conjugate": True},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
        "terms": [dark, {"fields": [{"field": "Ad"}, {"field": "B"}], "lorentz": "kinetic_mixing",
                         "coupling": f"{eps}/(2*{cw})"}]})
    from adroit.model_building import feynman, spectrum
    rules = feynman.feynman_rules(spectrum.compute(unbroken))
    assert not equivalence.sm_higgs_alone(rules) and equivalence.sm_higgs_alone(rules, equivalence.portal_vectors(unbroken))


def test_a_current_eps_e_q_written_out_is_the_kinetic_mixing_it_stands_for():
    """−(ε/2) V_μν F^μν (a dark photon below breaking) and the currents −ε e Q_f f̄γf V of every charged fermion (G1's
    photon couples as +e Q f̄γf A, and A → A − εV removes the mixing) are the same couplings. Both are DarkCast's ε:
    the electron's coupling is ε e(0), as the library's dark photon's (decision D29, G12; e in a stated coupling is
    e(0), ``gauge_basis.ELECTROWEAK``)."""
    eps = 1e-5
    chi = {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 1.0}
    vector = {"name": "V", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 1.3}
    dark = {"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "V"}], "lorentz": "vector",
            "coupling": "-1.1"}
    mixing = ModelSpec.model_validate({"name": "mixing", "phase": "broken", "fields": [
        chi, vector, {"name": "A", "role": "standard_model", "spin": 1, "self_conjugate": True}],
        "terms": [dark, {"fields": [{"field": "V"}, {"field": "A"}], "lorentz": "kinetic_mixing",
                         "coupling": f"-{eps}/2"}]})
    charges = {"u": "2/3", "c": "2/3", "t": "2/3", "d": "-1/3", "s": "-1/3", "b": "-1/3", "e": "-1", "mu": "-1",
               "tau": "-1"}
    sm = [{"name": f, "role": "standard_model", "spin": 0.5} for f in charges]
    currents = [{"fields": [{"field": f, "conjugate": True}, {"field": f}, {"field": "V"}], "lorentz": "vector",
                 "coupling": f"-{eps}*e*{q}"} for f, q in charges.items()]
    written = ModelSpec.model_validate({"name": "written", "phase": "broken", "fields": [chi, vector, *sm],
                                        "terms": [dark, *currents]})
    from adroit.model_building import feynman, spectrum

    def currents_of(spec):
        rules = feynman.feynman_rules(spectrum.compute(spec))
        return {v.legs: (v.c, v.c2) for v in rules.vertices if v.kind == "FFV" and "V" in v.legs}
    a, b = currents_of(written), currents_of(mixing)
    assert len(a) == 10 and a.keys() == b.keys()           # nine charged fermions and the dark one
    assert all(abs(complex(a[k][i]) - complex(b[k][i])) <= 1e-9 * abs(complex(b[k][0])) + 1e-15
               for k in a for i in (0, 1))
    from adroit.constraints import kinetic_mixing as km
    from adroit.model_building.gauge_basis import E_THOMSON
    electron = abs(complex(b[next(k for k in b if k[0] == "e")][0]))
    assert electron == pytest.approx(eps * E_THOMSON, rel=1e-6)
    assert abs(km.couplings(1.3, eps, 1.1)["A'"]["fermions"]["e"][0]) == pytest.approx(electron, rel=1e-3)


def _zprime(gu: str, gd: str, chi: str = "vector", chi_coupling: str = "g", m_chi: float = 100.0) -> ModelSpec:
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": m_chi},
              {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 1000.0},
              {"name": "u", "role": "standard_model", "spin": 0.5}, {"name": "d", "role": "standard_model", "spin": 0.5}]
    terms = [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Zp"}], "lorentz": chi,
              "coupling": chi_coupling},
             {"fields": [{"field": "u", "conjugate": True}, {"field": "u"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": gu},
             {"fields": [{"field": "d", "conjugate": True}, {"field": "d"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": gd}]
    return ModelSpec.model_validate({"name": "zp", "phase": "broken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "g", "value": 0.25}]})


def test_vector_and_axial_couplings_are_not_the_same_model():
    """The audit's G1-1 (G12): the comparison kept √(|c|² + |c₂|²), so a vector and an axial Z′ compared equal."""
    assert not equivalence.compare(_zprime("g", "g"), _zprime("g", "g", chi="axial")).equal


def test_the_relative_sign_of_two_couplings_to_one_mediator_is_physics():
    """g_u = g_d against g_u = −g_d: the xenon rate differs by ~300; no field sign maps one onto the other."""
    check = equivalence.compare(_zprime("g", "g"), _zprime("g", "-g"))
    assert not check.equal and "relative signs" in check.differences[0]


def test_a_mediator_written_with_the_opposite_sign_throughout_is_the_same_model():
    """Z′ → −Z′ flips every Z′ coupling: a field redefinition, not physics."""
    assert equivalence.compare(_zprime("g", "g"), _zprime("-g", "-g", chi_coupling="-g")).equal


def test_a_scalar_and_a_pseudoscalar_coupling_differ():
    def spec(lorentz: str) -> ModelSpec:
        return ModelSpec.model_validate({"name": "s", "phase": "broken", "fields": [
            {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
            {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 500.0},
            {"name": "b", "role": "standard_model", "spin": 0.5}],
            "terms": [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "S"}],
                       "lorentz": lorentz, "coupling": "0.5"},
                      {"fields": [{"field": "b", "conjugate": True}, {"field": "b"}, {"field": "S"}],
                       "lorentz": lorentz, "coupling": "0.1"}]})
    assert not equivalence.compare(spec("scalar"), spec("pseudoscalar")).equal


def test_masses_within_the_tolerance_key_their_vertices_alike():
    """The audit's G1-11: 100.0049 and 100.0051 GeV matched as states but rounded apart in the vertices' keys."""
    assert equivalence.compare(_zprime("g", "g", m_chi=100.0049), _zprime("g", "g", m_chi=100.0051)).equal


def test_a_broken_phase_charged_singlet_has_its_photon_and_z_couplings():
    """The audit's G1-2 (G12): new charged states written below breaking had no photon or Z coupling (φ⁺φ⁻ → γγ lost).
    The broken-phase writing now equals the unbroken one (D19 sets the h aside)."""
    def spec(phase: str) -> ModelSpec:
        sm = "eR" if phase == "unbroken" else "e"
        charged = {"hypercharge": -1.0} if phase == "unbroken" else {"electric_charge": -1.0}
        fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
                   "mass_gev": 100.0},
                  {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 300.0,
                   "charges": charged},
                  {"name": "psi", "role": "other", "spin": 0.5, "dark_parity": -1, "mass_gev": 400.0,
                   "charges": charged}]
        fields += ([{"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R",
                     "charges": {"hypercharge": -1.0}},
                    {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}]
                   if phase == "unbroken" else [{"name": "e", "role": "standard_model", "spin": 0.5}])
        return ModelSpec.model_validate({"name": phase, "phase": phase, "fields": fields, "terms": [
            {"fields": [{"field": "phi", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": sm}],
             "lorentz": "chiral", "coupling": "0.5", "plus_hc": True}]})
    check = equivalence.compare(spec("broken"), spec("unbroken"), d19=True)
    assert check.equal, check.differences


def _degenerate(first: str, second: str) -> ModelSpec:
    """Degenerate odd real scalars X, Y and real mediators S, T: g S {first}² + g T {second}² (the external audit's
    A02, 2026-10-16, adapted from its equivalence_repros.py)."""
    return ModelSpec.model_validate({"name": "degenerate", "phase": "broken", "fields": [
        {"name": "X", "role": "dark_matter", "spin": 0, "self_conjugate": True, "mass_gev": 100, "dark_parity": -1},
        {"name": "Y", "role": "other", "spin": 0, "self_conjugate": True, "mass_gev": 100, "dark_parity": -1},
        {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 300},
        {"name": "T", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 500}],
        "couplings": [{"name": "g", "value": 1, "mass_dimension": 1}],
        "terms": [{"fields": [{"field": x}, {"field": x}, {"field": m}], "lorentz": "scalar", "coupling": "g"}
                  for m, x in (("S", first), ("T", second))]})


def test_degenerate_species_keep_one_identity_across_vertices():
    """A02: g S X² + g T X² and g S X² + g T Y² had compared equal; their invariant Tr(G_S G_T) is 4 against 0, so no
    rotation of the degenerate X, Y maps one onto the other. Renaming X and Y throughout is still the same model."""
    found = equivalence.compare(_degenerate("X", "X"), _degenerate("X", "Y"))
    assert not found.equal
    assert equivalence.compare(_degenerate("X", "X"), _degenerate("Y", "Y")).equal          # X ↔ Y renamed
    assert equivalence.compare(_degenerate("X", "Y"), _degenerate("Y", "X")).equal


def _phase(second: str, flipped: bool = False) -> ModelSpec:
    """Charged complex P, Q and real S, T: g S P*Q + {second} g T P*Q + h.c. (A03); ``flipped`` writes each term as
    its hermitian conjugate, g S Q*P + h.c."""
    first, other = ("Q", "P") if flipped else ("P", "Q")
    return ModelSpec.model_validate({"name": "phase", "phase": "broken", "fields": [
        {"name": "X", "role": "dark_matter", "spin": 0, "self_conjugate": True, "mass_gev": 100, "dark_parity": -1},
        *({"name": n, "role": "mediator", "spin": 0, "mass_gev": m, "charges": {"electric_charge": 1}}
          for n, m in (("P", 400), ("Q", 600))),
        *({"name": n, "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": m}
          for n, m in (("S", 300), ("T", 500)))],
        "couplings": [{"name": "g", "value": 1, "mass_dimension": 1}],
        "terms": [{"fields": [{"field": first, "conjugate": True}, {"field": other}, {"field": s}],
                   "lorentz": "scalar", "coupling": c, "plus_hc": True}
                  for s, c in (("S", "g"), ("T", f"{second}*g"))]})


def test_a_relative_complex_phase_between_vertices_is_physical():
    """A03: g S P*Q + g T P*Q and g S P*Q + i g T P*Q had compared equal (magnitudes only); Re[(g_S g_T*)²] is +1
    against −1, which no rephasing of P or Q, sign of S or T, or charge conjugation changes."""
    assert not equivalence.compare(_phase("1"), _phase("I")).equal


def test_a_harmless_rephasing_and_a_hermitian_conjugate_writing_are_the_same_model():
    """Positive controls: Q → iQ multiplies both vertices by i; −g T P*Q is T → −T; writing each term as its own
    hermitian conjugate is the same Lagrangian."""
    base = _phase("1")
    rephased = ModelSpec.model_validate({**base.model_dump(mode="json"), "terms": [
        {**t, "coupling": f"I*({t['coupling']})"} for t in base.model_dump(mode="json")["terms"]]})
    assert equivalence.compare(base, rephased).equal
    assert equivalence.compare(base, _phase("-1")).equal                              # T → −T
    assert equivalence.compare(base, _phase("1", flipped=True)).equal
    assert equivalence.compare(_phase("I"), _phase("-I")).equal                       # T → −T again


def _singlet_doublet(writing: str, y: float = 0.3) -> ModelSpec:
    """One singlet–doublet Dirac model (χ⁰ 200 GeV, N (Y = −½) 212 GeV, vector-like Yukawa y), three writings: a Dirac
    Yukawa, two chiral Yukawas, and four Weyl fields with their Dirac masses."""
    h = {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}
    occ = lambda *xs: [{"field": x.rstrip("*"), "conjugate": x.endswith("*")} for x in xs]  # noqa: E731
    if writing == "weyl":
        fields = [{"name": "SL", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1},
                  {"name": "SR", "role": "dark_matter", "spin": 0.5, "chirality": "R", "dark_parity": -1},
                  *({"name": n, "role": "dark_matter", "spin": 0.5, "chirality": c, "dark_parity": -1,
                     "charges": {"su2": 2, "hypercharge": -0.5}} for n, c in (("psiL", "L"), ("psiR", "R"))), h]
        terms = [{"fields": occ("psiL*", "psiR"), "lorentz": "scalar", "coupling": "-212", "plus_hc": True,
                  "indices": "psiL*[i] psiR[i]"},
                 {"fields": occ("SL*", "SR"), "lorentz": "scalar", "coupling": "-200", "plus_hc": True},
                 {"fields": occ("psiL*", "H*", "SR"), "lorentz": "scalar", "coupling": "-y", "plus_hc": True,
                  "indices": "eps[i,j] psiL*[i] H*[j] SR"},
                 {"fields": occ("psiR*", "H*", "SL"), "lorentz": "scalar", "coupling": "-y", "plus_hc": True,
                  "indices": "eps[i,j] psiR*[i] H*[j] SL"}]
    else:
        fields = [{"name": "chi0", "role": "dark_matter", "spin": 0.5, "mass_gev": 200.0, "dark_parity": -1},
                  {"name": "N", "role": "dark_matter", "spin": 0.5, "mass_gev": 212.0, "dark_parity": -1,
                   "charges": {"su2": 2, "hypercharge": -0.5}}, h]
        one = {"fields": occ("N*", "H*", "chi0"), "lorentz": "scalar" if writing == "dirac" else "chiral",
               "coupling": "-y", "plus_hc": True, "indices": "eps[i,j] N*[i] H*[j] chi0"}
        terms = [one] if writing == "dirac" else [one, {"fields": occ("chi0*", "N", "H"), "lorentz": "chiral",
                                                        "coupling": "-y", "plus_hc": True,
                                                        "indices": "eps[i,j] N[i] H[j] chi0*"}]
    return ModelSpec.model_validate({"name": writing, "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "y", "value": y}]})


def test_dirac_chiral_and_weyl_writings_of_one_model_are_equal():
    """Positive control for the repaired comparison: G2 writes a fermion pair's barred spinor first, so (x, ȳ) is the
    transposed form of ȳΓx; the three writings' mixed Z and W couplings agree only once that is read (the external
    audit's A02/A03 repair; an earlier draft had compared Yaguna et al.'s Weyl writing as different)."""
    dirac, chiral, weyl = (_singlet_doublet(w) for w in ("dirac", "chiral", "weyl"))
    assert equivalence.compare(dirac, chiral).equal and equivalence.compare(dirac, weyl).equal
    assert not equivalence.compare(dirac, _singlet_doublet("dirac", y=0.31)).equal


def test_a_charged_mediator_written_as_its_conjugate_is_the_same_model():
    """Charge conjugation as part of the mapping: φ (Y = +1) in y φ χ̄ P_R e_R and φ′ = φ* (Y = −1) in y φ′* χ̄ P_R e_R are
    the same Lagrangian."""
    def spec(name: str, hypercharge: float, conjugate: bool) -> ModelSpec:
        return ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": [
            {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
             "mass_gev": 300.0},
            {"name": name, "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 900.0,
             "charges": {"hypercharge": hypercharge}},
            {"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": {"hypercharge": -1.0}}],
            "couplings": [{"name": "y", "value": 0.8}],
            "terms": [{"fields": [{"field": name, "conjugate": conjugate}, {"field": "chi", "conjugate": True},
                                  {"field": "eR"}], "lorentz": "chiral", "coupling": "y", "plus_hc": True}]})
    found = equivalence.compare(spec("Phi", 1.0, False), spec("Phim", -1.0, True))
    assert found.equal, found.differences
    assert not equivalence.compare(spec("Phi", 1.0, False), spec("Phim", -1.0, True).model_copy(update={
        "couplings": [spec("Phi", 1.0, False).couplings[0].model_copy(update={"value": 0.9})]})).equal

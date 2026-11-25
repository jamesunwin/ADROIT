"""The physical spectrum (G1): the Standard Model, electroweak multiplets and the analytic spectra of mixing
models, each against its closed form."""

import math

import numpy as np
import pytest

from adroit.core.model_spec import ModelSpec
from adroit.model_building import spectrum as sp
from adroit.model_building.gauge_basis import GaugeBasisError, M_H, M_W, M_Z, V_EW

H = {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}
R2 = math.sqrt(2)


def model(fields, terms=(), couplings=(), phase="unbroken"):
    return ModelSpec.model_validate({"name": "t", "phase": phase, "fields": list(fields), "terms": list(terms),
                                     "couplings": list(couplings)})


def masses(s, parity=-1):
    return sorted((round(x.mass_gev, 6), x.kind, x.charge) for x in s.states if x.parity == parity)


def test_the_standard_model_comes_out_with_its_inputs_and_no_goldstones():
    s = sp.spectrum(model([{"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True,
                            "dark_parity": -1, "mass_gev": 100.0}]))
    by = {x.name: x for x in s.states}
    assert by["h"].mass_gev == pytest.approx(M_H) and by["W"].mass_gev == pytest.approx(M_W)
    assert by["Z"].mass_gev == pytest.approx(M_Z) and by["A"].mass_gev == 0.0          # exactly: the tree engine
    #                                                     gives a massive vector a longitudinal state ∝ 1/m
    assert [x.kind for x in s.states if x.spin == 0] == ["real", "real"]          # S and h only
    assert s.solved["H"] == pytest.approx(-M_H ** 2 / 2)                           # V ⊃ −μ²|H|², μ² = m_h²/2


@pytest.mark.parametrize("fields,expected", [
    ({"spin": 0.5, "self_conjugate": True, "charges": {"su2": 3}}, [("majorana", 0), ("dirac", 1)]),       # wino
    ({"spin": 0.5, "charges": {"su2": 2, "hypercharge": 0.5}}, [("dirac", 0), ("dirac", 1)]),             # higgsino
    ({"spin": 0, "self_conjugate": True, "charges": {"su2": 5}}, [("real", 0), ("complex", 1), ("complex", 2)]),
    ({"spin": 0.5, "charges": {"su2": 5, "hypercharge": 1.0}},
     [("dirac", 0), ("dirac", 1), ("dirac", -1), ("dirac", 2), ("dirac", 3)])])   # Q = T₃ + 1 of the particles
def test_electroweak_multiplets_are_degenerate_at_tree_level_with_their_charges(fields, expected):
    s = sp.spectrum(model([{"name": "chi", "role": "dark_matter", "dark_parity": -1, "mass_gev": 1000.0, **fields}]))
    found = masses(s)
    assert sorted((k, q) for _, k, q in found) == sorted(expected)
    assert all(m == pytest.approx(1000.0) for m, _, _ in found)


def test_the_singlet_doublet_majorana_spectrum_matches_its_mass_matrix():
    """Cohen et al. eq. (3): basis (S, ν, νᶜ), entries λv/√2 and λ′v/√2; at λ′ = −λ one state sits at M_D."""
    lam, lamp, ms, md = 0.2, -0.2, 2000.0, 1100.0
    fields = [{"name": "S", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1, "mass_gev": ms},
              {"name": "D", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1,
               "charges": {"su2": 2, "hypercharge": -0.5}},
              {"name": "Dc", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1,
               "charges": {"su2": 2, "hypercharge": 0.5}}, H]
    terms = [{"fields": [{"field": "D"}, {"field": "H"}, {"field": "S"}], "lorentz": "scalar", "coupling": "-lam",
              "plus_hc": True, "indices": "eps[i,j] D[i] H[j] S"},
             {"fields": [{"field": "Dc"}, {"field": "H", "conjugate": True}, {"field": "S"}], "lorentz": "scalar",
              "coupling": "-lam_prime", "plus_hc": True, "indices": "Dc[i] H*[i] S"},
             {"fields": [{"field": "D"}, {"field": "Dc"}], "lorentz": "scalar", "coupling": "-M_D", "plus_hc": True,
              "indices": "eps[i,j] D[i] Dc[j]"}]
    couplings = [{"name": "lam", "value": lam}, {"name": "lam_prime", "value": lamp},
                 {"name": "M_D", "value": md, "mass_dimension": 1}]
    s = sp.spectrum(model(fields, terms, couplings))
    a, b = lam * V_EW / R2, lamp * V_EW / R2
    expected = np.sort(np.abs(np.linalg.eigvalsh(np.array([[ms, a, b], [a, 0, md], [b, md, 0]]))))
    neutral = sorted(x.mass_gev for x in s.states if x.parity == -1 and x.charge == 0)
    assert neutral == pytest.approx(list(expected), rel=1e-10)
    assert s.dark_matter().mass_gev == pytest.approx(md)
    assert [x.mass_gev for x in s.states if x.parity == -1 and x.charge == 1] == pytest.approx([md])


def test_the_singlet_doublet_dirac_spectrum_follows_from_m1_m2_and_the_angle():
    m1, m2, st = 200.0, 300.0, 0.26
    ct = math.sqrt(1 - st ** 2)
    fields = [{"name": "chi0", "role": "dark_matter", "spin": 0.5, "dark_parity": -1,
               "mass_gev": m1 * ct ** 2 + m2 * st ** 2},
              {"name": "N", "role": "dark_matter", "spin": 0.5, "dark_parity": -1,
               "mass_gev": m1 * st ** 2 + m2 * ct ** 2, "charges": {"su2": 2, "hypercharge": -0.5}}, H]
    terms = [{"fields": [{"field": "N", "conjugate": True}, {"field": "H", "conjugate": True}, {"field": "chi0"}],
              "lorentz": "scalar", "coupling": "-Y", "plus_hc": True, "indices": "eps[i,j] N*[i] H*[j] chi0"}]
    s = sp.spectrum(model(fields, terms, [{"name": "Y", "value": R2 * (m2 - m1) * st * ct / V_EW}]))
    assert masses(s) == [(200.0, "dirac", 0.0), (pytest.approx(293.24), "dirac", -1.0), (300.0, "dirac", 0.0)]


def test_the_inert_doublet_masses_follow_from_its_quartics():
    mh, ma, mhp, l345 = 72.77, 107.803, 114.639, -0.00440723
    l5, l4 = (mh ** 2 - ma ** 2) / V_EW ** 2, (mh ** 2 + ma ** 2 - 2 * mhp ** 2) / V_EW ** 2
    occ = lambda *xs: [{"field": f.rstrip("*"), "conjugate": f.endswith("*")} for f in xs]   # noqa: E731
    terms = [{"fields": occ("p", "p*", "p", "p*"), "lorentz": "scalar", "coupling": "-l2/2"},
             {"fields": occ("H", "H*", "p", "p*"), "lorentz": "scalar", "coupling": "-l3",
              "indices": "H*[i] H[i] p*[j] p[j]"},
             {"fields": occ("H*", "p", "p*", "H"), "lorentz": "scalar", "coupling": "-l4",
              "indices": "H*[i] p[i] p*[j] H[j]"},
             {"fields": occ("H*", "H*", "p", "p"), "lorentz": "scalar", "coupling": "-l5/2", "plus_hc": True,
              "indices": "H*[i] p[i] H*[j] p[j]"}]
    couplings = [{"name": "l2", "value": 1.4}, {"name": "l3", "value": l345 - l4 - l5}, {"name": "l4", "value": l4},
                 {"name": "l5", "value": l5}]
    fields = [{"name": "p", "role": "dark_matter", "spin": 0, "dark_parity": -1,
               "mass_gev": math.sqrt(mh ** 2 - l345 * V_EW ** 2 / 2), "charges": {"su2": 2, "hypercharge": 0.5}}, H]
    s = sp.spectrum(model(fields, terms, couplings))
    assert [m for m, _, _ in masses(s)] == pytest.approx([mh, ma, mhp], rel=1e-9)


def test_a_mixing_singlet_gives_its_angle_and_a_tadpole_term():
    """Das et al.'s structure: s mixes with h through μ_hs|H|²s; ⟨s⟩ = 0 needs the singlet's linear term."""
    m1, m2, st = 125.25, 200.0, 0.1
    ct = math.sqrt(1 - st ** 2)
    mss, mhh, mhs = m2 ** 2 * ct ** 2 + m1 ** 2 * st ** 2, m1 ** 2 * ct ** 2 + m2 ** 2 * st ** 2, \
        (m2 ** 2 - m1 ** 2) * st * ct
    occ = lambda *xs: [{"field": f.rstrip("*"), "conjugate": f.endswith("*")} for f in xs]   # noqa: E731
    terms = [{"fields": occ("H", "H*", "s"), "lorentz": "scalar", "coupling": "-mu_hs"},
             {"fields": occ("H", "H*", "s", "s"), "lorentz": "scalar", "coupling": "-l_hs/2"},
             {"fields": occ("s", "s"), "lorentz": "scalar", "coupling": "-mu_s2/2"},
             {"fields": occ("H", "H*", "H", "H*"), "lorentz": "scalar", "coupling": "-l_h"}]
    couplings = [{"name": "mu_hs", "value": mhs / V_EW, "mass_dimension": 1}, {"name": "l_hs", "value": 2.4},
                 {"name": "mu_s2", "value": mss - 2.4 * V_EW ** 2 / 2, "mass_dimension": 2},
                 {"name": "l_h", "value": mhh / (2 * V_EW ** 2)}]
    fields = [{"name": "s", "role": "mediator", "spin": 0, "self_conjugate": True},
              {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 50.0}, H]
    s = sp.spectrum(model(fields, terms, couplings))
    heavy = s.state("s0")
    assert heavy.mass_gev == pytest.approx(m2) and s.state("h").mass_gev == pytest.approx(m1)
    assert heavy.composition["H[m=-0.5,re]"] == pytest.approx(st ** 2)
    assert s.linear_terms["s"] == pytest.approx(-mhs * V_EW / 2)        # a₁ = −μ_hs v²/2 cancels the tadpole


def test_a_dark_higgs_gives_its_vector_a_mass_and_eats_its_goldstone():
    g, vphi = 0.7, 300.0
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 50.0},
              {"name": "X", "role": "mediator", "spin": 1, "self_conjugate": True},
              {"name": "Phi", "role": "mediator", "spin": 0, "vev_gev": vphi, "charges": {"extra": {"X": 1.0}}}, H]
    occ = lambda *xs: [{"field": f.rstrip("*"), "conjugate": f.endswith("*")} for f in xs]   # noqa: E731
    terms = [{"fields": occ("X", "Phi*", "Phi"), "lorentz": "scalar_current", "coupling": "g"},
             {"fields": occ("X", "X", "Phi*", "Phi"), "lorentz": "scalar", "coupling": "g**2"},
             {"fields": occ("Phi", "Phi*", "Phi", "Phi*"), "lorentz": "scalar", "coupling": "-0.1"}]
    s = sp.spectrum(model(fields, terms, [{"name": "g", "value": g}]))
    assert s.state("X").mass_gev == pytest.approx(g * vphi)
    scalars = [x for x in s.states if x.spin == 0]
    assert len(scalars) == 2                                              # h and the radial φ: the phase is eaten
    assert s.state("Phi0").mass_gev == pytest.approx(math.sqrt(2 * 0.1) * vphi)   # m² = 2λ v_φ²


def test_a_vacuum_that_is_not_stationary_is_refused():
    fields = [{"name": "T", "role": "mediator", "spin": 0, "charges": {"su2": 3, "hypercharge": 1.0}},
              {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 50.0}, H]
    occ = [{"field": "H"}, {"field": "H"}, {"field": "T", "conjugate": True}]
    terms = [{"fields": occ, "lorentz": "scalar", "coupling": "10.0", "plus_hc": True,
              "indices": "eps[i,j] H[i] sigma[A,j,k] H[k] cartc[A,m] T*[m]"}]
    with pytest.raises(GaugeBasisError, match="not stationary"):
        sp.spectrum(model(fields, terms))


def occ(*xs):
    return [{"field": f.rstrip("*"), "conjugate": f.endswith("*")} for f in xs]


def test_a_term_that_is_not_gauge_invariant_is_refused():
    from adroit.model_building.indices import IndexError_
    fields = [{"name": "T", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1, "mass_gev": 100.0,
               "charges": {"su2": 3}},
              {"name": "D", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1,
               "charges": {"su2": 2, "hypercharge": -0.5}}, H]
    terms = [{"fields": occ("T", "H", "D"), "lorentz": "scalar", "coupling": "1.0", "plus_hc": True,
              "indices": "eps[a,b] cart[A,m] T[m] H[a] sigma[A,c,b] D[c]"}]      # τ on the wrong side of ε
    with pytest.raises(IndexError_, match="not SU\\(2\\) invariant"):
        sp.spectrum(model(fields, terms))


def test_the_doublet_triplet_spectrum_matches_its_printed_mass_matrices():
    """Dedes & Karamitros eq. (2.12): M_N = [[M_T, m₁, −m₂], [m₁, 0, M_D], [−m₂, M_D, 0]],
    M_C = [[M_T, √2 m₁], [√2 m₂, −M_D]], m_i = Y_i v/√2; in the custodial limit m₁ = m₂ a state sits at M_D."""
    mt, md, m1, m2 = 100.0, 110.0, 200.0, 170.0
    fields = [{"name": "T", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1, "mass_gev": mt,
               "charges": {"su2": 3}},
              {"name": "D1bar", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1,
               "charges": {"su2": 2, "hypercharge": -0.5}},
              {"name": "D2bar", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1,
               "charges": {"su2": 2, "hypercharge": 0.5}}, H]
    terms = [{"fields": occ("T", "H", "D1bar"), "lorentz": "scalar", "coupling": "Y1", "plus_hc": True,
              "indices": "eps[a,b] D1bar[a] sigma[A,b,c] H[c] cart[A,m] T[m]"},
             {"fields": occ("T", "H*", "D2bar"), "lorentz": "scalar", "coupling": "-Y2", "plus_hc": True,
              "indices": "H*[a] sigma[A,a,c] D2bar[c] cart[A,m] T[m]"},
             {"fields": occ("D1bar", "D2bar"), "lorentz": "scalar", "coupling": "-M_D", "plus_hc": True,
              "indices": "eps[a,b] D1bar[a] D2bar[b]"}]
    couplings = [{"name": "Y1", "value": m1 * R2 / V_EW}, {"name": "Y2", "value": m2 * R2 / V_EW},
                 {"name": "M_D", "value": md, "mass_dimension": 1}]
    s = sp.spectrum(model(fields, terms, couplings))
    neutral = np.sort(np.abs(np.linalg.eigvalsh(np.array([[mt, m1, -m2], [m1, 0, md], [-m2, md, 0]]))))
    charged = np.sort(np.linalg.svd(np.array([[mt, R2 * m1], [R2 * m2, -md]]), compute_uv=False))
    assert sorted(x.mass_gev for x in s.states if x.parity == -1 and x.charge == 0) == pytest.approx(list(neutral))
    assert sorted(x.mass_gev for x in s.states if x.parity == -1 and x.charge == 1) == pytest.approx(list(charged))


def test_the_singlet_triplet_scalars_and_fermions_follow_the_papers_relations():
    """Choubey et al. eqs. (15)–(18): a real triplet with vev v_Δ = v tan δ/2 gives m_h₁, m_h₂, m_H± and the angle α;
    the Majorana singlet and triplet mix by Y v_Δ/2 (their '+ h.c.' would double a Majorana bilinear; eq. (16) is
    followed, so the term has no + h.c.)."""
    mh1, mh2, mhp, sa, sd = 125.5, 195.5, 195.5, 0.03, 0.03
    ca, cd = math.sqrt(1 - sa ** 2), math.sqrt(1 - sd ** 2)
    vd = V_EW * sd / cd / 2
    mu = mhp ** 2 * sd * cd / V_EW
    l32 = (mh1 ** 2 + mh2 ** 2 + (mh2 ** 2 - mh1 ** 2) * (1 - 2 * sa ** 2) - 2 * mhp ** 2 * cd ** 2) / (2 * vd ** 2)
    lh = (mh1 ** 2 + mh2 ** 2 + (mh1 ** 2 - mh2 ** 2) * (1 - 2 * sa ** 2)) / V_EW ** 2
    l41 = ((mh1 ** 2 - mh2 ** 2) * 2 * sa * ca + mhp ** 2 * 2 * sd * cd) / (V_EW * vd)
    mn, mr, mix = 88.0, 127.6, 4.0
    fields = [{"name": "Np", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": mn},
              {"name": "rho", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": mr, "charges": {"su2": 3}},
              {"name": "Delta", "role": "mediator", "spin": 0, "self_conjugate": True, "vev_gev": vd,
               "charges": {"su2": 3}}, H]
    terms = [{"fields": occ("rho*", "Np", "Delta"), "lorentz": "scalar", "coupling": "-Y/2"},
             {"fields": occ("H*", "Delta", "H"), "lorentz": "scalar", "coupling": "-mu/2", "plus_hc": True,
              "indices": "H*[i] sigma[A,i,j] H[j] cart[A,m] Delta[m]"},
             {"fields": occ("Delta", "Delta", "Delta", "Delta"), "lorentz": "scalar", "coupling": "-l32/8"},
             {"fields": occ("H", "H*", "Delta", "Delta"), "lorentz": "scalar", "coupling": "-l41/4"},
             {"fields": occ("H", "H*", "H", "H*"), "lorentz": "scalar", "coupling": "-lh/4"}]
    couplings = [{"name": "Y", "value": 2 * mix / vd}, {"name": "mu", "value": mu, "mass_dimension": 1},
                 {"name": "l32", "value": l32}, {"name": "l41", "value": l41}, {"name": "lh", "value": lh}]
    s = sp.spectrum(model(fields, terms, couplings))
    assert s.state("h").mass_gev == pytest.approx(mh1) and s.state("Delta0").mass_gev == pytest.approx(mh2)
    assert s.state("Delta+").mass_gev == pytest.approx(mhp)
    assert s.state("Delta0").composition["H[m=-0.5,re]"] == pytest.approx(sa ** 2)
    expected = np.sort(np.linalg.eigvalsh(np.array([[mr, mix], [mix, mn]])))
    neutral = sorted(x.mass_gev for x in s.states if x.parity == -1 and x.charge == 0)
    assert neutral == pytest.approx(list(expected)) and s.state("rho+").mass_gev == pytest.approx(mr)


S_ODD = {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1, "mass_gev": 100.0}


@pytest.mark.parametrize("terms,couplings,match", [
    ([{"fields": [{"field": "S"}, {"field": "H", "conjugate": True}, {"field": "H"}], "lorentz": "scalar",
       "coupling": "mu"}], [{"name": "mu", "value": 10.0, "mass_dimension": 1}], "dark parity"),
    ([{"fields": [{"field": "S"}, {"field": "S"}, {"field": "H", "conjugate": True}, {"field": "H"}],
       "lorentz": "scalar", "coupling": "lam"}], [{"name": "lam", "value": 0.1, "mass_dimension": 1}],
     "needs 0"),
    ([{"fields": [{"field": "S"}, {"field": "S"}, {"field": "H", "conjugate": True}, {"field": "H"}],
       "lorentz": "scalar", "coupling": "1/0"}], [], "has no value|not finite")])
def test_a_term_must_keep_the_dark_parity_its_dimension_and_a_finite_coupling(terms, couplings, match):
    """The generic route builds what the library's maps refuse, so G1 refuses what is not a consistent model."""
    with pytest.raises(GaugeBasisError, match=match):
        sp.spectrum(model([S_ODD, H], terms, couplings))


def test_a_stated_mass_must_be_finite():
    with pytest.raises(GaugeBasisError, match="finite and non-negative"):
        sp.spectrum(model([{**S_ODD, "mass_gev": float("nan")}]))


def test_a_broken_phase_model_without_scalars_has_a_vacuum():
    """A colour-octet Majorana partner below electroweak breaking: no scalar coordinates, nothing to solve."""
    s = sp.spectrum(model([{**S_ODD, "name": "chi", "spin": 0.5, "mass_gev": 1000.0},
                           {"name": "O", "role": "other", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
                            "mass_gev": 1000.1, "charges": {"su3": "8"}}], phase="broken"))
    assert masses(s) == [(1000.0, "majorana", 0.0), (1000.1, "majorana", 0.0)]


def test_a_majorana_mass_splits_a_dirac_field_into_a_pseudo_dirac_pair():
    """−Mψ̄ψ − ½δ(\\overline{ψᶜ}ψ + h.c.): two Majorana states at M ± δ (it was read as a Dirac mass, M + δ for both);
    a chiral Majorana mass splits them by δ around M + δ/2."""
    def states(lorentz: str):
        spec = model([{"name": "psi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1}],     # mass by terms
                     [{"fields": [{"field": "psi", "conjugate": True}, {"field": "psi"}], "lorentz": "scalar",
                       "coupling": "-M"},
                      {"fields": [{"field": "psi"}, {"field": "psi"}], "lorentz": lorentz, "coupling": "-d/2",
                       "plus_hc": True}],
                     [{"name": "M", "value": 100.0, "mass_dimension": 1}, {"name": "d", "value": 1.0, "mass_dimension": 1}])
        return masses(sp.spectrum(spec))
    assert states("scalar") == [(99.0, "majorana", 0.0), (101.0, "majorana", 0.0)]
    low, high = states("chiral")                               # (δ ± √(δ² + 4M²))/2
    assert low[0] == pytest.approx(99.50125, abs=1e-5) and high[0] == pytest.approx(100.50125, abs=1e-5)


def test_a_new_field_may_not_take_a_standard_model_particles_name():
    """A dark vector named "A" would be merged with the photon."""
    spec = ModelSpec.model_validate({"name": "clash", "phase": "broken", "fields": [
        {"name": "X", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "A", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 0.0}]})
    with pytest.raises(GaugeBasisError, match="the name of a Standard Model particle"):
        sp.compute(spec)


def _portal(coupling: str) -> ModelSpec:
    return ModelSpec.model_validate({"name": "portal", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 30.0},
        {"name": "a0", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 100.0},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "H2", "role": "other", "spin": 0, "mass_gev": 600.0, "charges": {"su2": 2, "hypercharge": 0.5}}],
        "couplings": [{"name": "B", "value": 40.0, "mass_dimension": 1}],
        "terms": [{"fields": [{"field": "a0"}, {"field": "H", "conjugate": True}, {"field": "H2"}], "lorentz": "scalar",
                   "coupling": coupling, "plus_hc": True, "indices": "a0 H*[i] H2[i]"}]})


def test_a_complex_coupling_with_its_conjugate_is_the_cp_odd_portal():
    """i B a₀H†H₂ + h.c. (a complex coefficient, I in the formula) mixes a₀ with H₂'s CP-odd component; the real
    B a₀H†H₂ + h.c. with its CP-even one."""
    def share(coupling: str, part: str) -> float:
        light = min((s for s in sp.compute(_portal(coupling)).spectrum.states if s.name.startswith("a0")),
                    key=lambda s: s.mass_gev)
        return sum(v for k, v in light.composition.items() if k.startswith("H2") and k.endswith(f",{part}]"))
    assert share("I*B", "im") > 1e-4 and share("I*B", "re") < 1e-12
    assert share("B", "re") > 1e-4 and share("B", "im") < 1e-12


def test_a_stated_mass_beside_a_bilinear_of_the_field_itself_is_refused():
    """χ with mass_gev 30 GeV and a stray χ̄iγ⁵χ term (G10's Ipek case, 2026-10-15) states its mass twice; a Dirac
    mass between two Weyl fields, each with a stated mass, is not refused."""
    spec = ModelSpec.model_validate({"name": "twice", "phase": "broken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 30.0}],
        "terms": [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}], "lorentz": "pseudoscalar",
                   "coupling": "0.8"}]})
    with pytest.raises(GaugeBasisError, match="states its mass twice"):
        sp.compute(spec)
    weyl = ModelSpec.model_validate({"name": "weyl", "phase": "broken", "fields": [
        {"name": "eta", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1, "mass_gev": 10.0},
        {"name": "xi", "role": "dark_matter", "spin": 0.5, "chirality": "L", "dark_parity": -1, "mass_gev": 10.0}],
        "terms": [{"fields": [{"field": "eta"}, {"field": "xi"}], "lorentz": "scalar", "coupling": "-10.0",
                   "plus_hc": True}]})
    sp.compute(weyl)


def _closure_model(fields, terms=(), phase="broken"):
    return ModelSpec.model_validate({"name": "m", "phase": phase, "fields": list(fields), "terms": list(terms)})


CHI = {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0}


@pytest.mark.parametrize("fields, terms, phase, match", [
    ([CHI, {"name": "h", "role": "standard_model", "spin": 0}],
     [{"fields": [{"field": "h"}, {"field": "h"}], "lorentz": "scalar", "coupling": "-m_h**2/2"}],
     "broken", "own potential"),                                                                       # G1-4
    ([CHI, {"name": "h", "role": "standard_model", "spin": 0}], [], "unbroken", "doublet H"),           # G1-8
    ([CHI, {"name": "B", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 10.0}], [],
     "broken", "name of a Standard Model particle"),                                                  # G1-8
    ([CHI, {"name": "V", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 10.0},
      {"name": "gamma", "role": "standard_model", "spin": 1, "self_conjugate": True}],
     [{"fields": [{"field": "V"}, {"field": "gamma"}], "lorentz": "kinetic_mixing", "coupling": "-1e-3/2"}],
     "broken", "kinetic mixing"),                                                                       # G1-8
    ([CHI, {"name": "G", "role": "mediator", "spin": 2, "self_conjugate": True, "mass_gev": 500.0}], [],
     "broken", "spin 2 is not supported"),                                          # had been skipped silently
    ([CHI, {"name": "R", "role": "mediator", "spin": 1.5, "mass_gev": 500.0}], [], "broken", "spin 1.5"),
])
def test_the_closure_audits_misreadings_are_refused(fields, terms, phase, match):
    """The audit's G1-4 and G1-8 (G12): each had been accepted and misread (h's potential doubled, an extra massless
    h, a vector merged with the SM's, a kinetic mixing dropped). G1-9 is ``test_a_field_of_several_generations_...``."""
    with pytest.raises(GaugeBasisError, match=match):
        sp.compute(_closure_model(fields, terms, phase))


def test_a_field_of_several_generations_keeps_them_all():
    """The audit's G1-9 (G12): a field's other generations had been lost, so G1 refused them; since the owner's
    decision #5 (2026-10-20) each generation is its own field (``model_building.generations``), none lost."""
    odd = [s for s in sp.spectrum(_closure_model([{**CHI, "generations": 3}])).states if s.parity == -1]
    assert len(odd) == 3 and all(s.mass_gev == pytest.approx(100.0) for s in odd)


def test_a_stated_mass_is_kept_beside_a_mixing_term_and_a_zero_vacuum_value_is_none():
    """The audit's G1-3 (G12): χ (100) and ψ (200) mixed by a 1 GeV term came out at 1 GeV each; a scalar with
    vev_gev = 0 came out massless."""
    psi = {"name": "psi", "role": "other", "spin": 0.5, "dark_parity": -1, "mass_gev": 200.0}
    mixing = [{"fields": [{"field": "chi", "conjugate": True}, {"field": "psi"}], "lorentz": "scalar",
               "coupling": "-1.0", "plus_hc": True}]
    spec = _closure_model([CHI, psi], mixing)
    masses = sorted(s.mass_gev for s in sp.spectrum(spec).states if s.parity == -1)
    assert masses[0] == pytest.approx(99.99, abs=0.01) and masses[-1] == pytest.approx(200.01, abs=0.01)
    scalar = {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 50.0, "vev_gev": 0.0}
    states = sp.spectrum(_closure_model([CHI, scalar])).states
    assert any(abs(s.mass_gev - 50.0) < 1e-9 for s in states)


def test_an_unbroken_phase_massless_dark_photon_keeps_its_own_name():
    """The audit's G1-8 (G12): a massless dark photon with no mixing was named A and the photon V."""
    spec = _closure_model([CHI, {"name": "Ad", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 0.0},
                           {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
                          [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Ad"}],
                            "lorentz": "vector", "coupling": "0.3"}], phase="unbroken")
    from adroit.model_building import feynman as fy
    rules = fy.feynman_rules(sp.compute(spec))
    names = {p.name for p in rules.particles if p.spin == 1}
    assert {"A", "Ad"} <= names
    photon = [v for v in rules.vertices if v.kind == "FFV" and "A" in v.legs and "e" in v.legs]
    assert photon


def test_a_right_handed_weyl_singlet_takes_its_stated_majorana_mass():
    """The audit's G1-10 (G12): N_R with mass_gev had raised a KeyError; it is a Majorana state at its mass, as N_L."""
    for chirality in ("L", "R"):
        s = sp.spectrum(model([{"name": "N", "role": "dark_matter", "spin": 0.5, "chirality": chirality,
                                "dark_parity": -1, "mass_gev": 100.0}]))
        assert masses(s) == [(100.0, "majorana", 0.0)]


def test_a_vector_mass_below_the_mass_matrix_resolution_is_refused():
    """The audit's G1-13 (G12): a 10 keV dark photon had come out massless; below the eigenvalues' resolution it is
    refused, and at 1 MeV it keeps its mass."""
    def dark_photon(m):
        return model([{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 0.1},
                      {"name": "Vd", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": m}],
                     [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Vd"}],
                       "lorentz": "vector", "coupling": "0.5"}])
    with pytest.raises(GaugeBasisError, match="below the resolution"):
        sp.spectrum(dark_photon(1e-5))
    assert next(x for x in sp.spectrum(dark_photon(1e-3)).states if x.name == "Vd").mass_gev == pytest.approx(1e-3)


def test_a_keyword_cannot_name_a_coupling():
    """The audit's G1-14 (G12): ``lambda`` had failed in the formula reader as "no value"; it is refused by name."""
    with pytest.raises(ValueError, match="reserved word"):
        model([], couplings=[{"name": "lambda", "value": 0.1}])


def test_a_stated_m_q_yukawa_is_tan_beta_times_the_higgss_own():
    """The audit's G1-12 (G12): m_q in a stated coupling is the flavour's Yukawa mass (m_b running to m_h, as h's
    own), so m_q/v·tanβ is tanβ times h's Yukawa, not 1.39 tanβ."""
    from adroit.core.model_spec import ModelTerm
    from adroit.model_building import feynman
    spec = model([{"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1,
                   "mass_gev": 100.0}], couplings=[{"name": "tanb", "value": 3.0}])
    yukawa = ModelTerm.model_validate({"fields": [{"field": "S"}, {"field": "S"}], "lorentz": "scalar",
                                       "coupling": "m_q/v*tanb"})
    assert feynman._sm_coupling(spec, yukawa, "b") == pytest.approx(3.0 * feynman.yukawa_mass("b") / V_EW)
    assert feynman.yukawa_mass("b") < 3.1

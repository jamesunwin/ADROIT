"""Gauge-index contractions (G1): representation conventions, the index notation, and the unique defaults."""

import numpy as np
import pytest

from adroit.core.model_spec import ModelSpec
from adroit.model_building import indices as ix

H = {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_su2_generators_close_and_the_metric_is_invariant(n):
    t = ix.su2_generators(n)
    j = (n - 1) / 2
    assert np.allclose(t[0] @ t[1] - t[1] @ t[0], 1j * t[2])
    assert np.allclose(sum(x @ x for x in t), j * (j + 1) * np.eye(n))
    c = ix.su2_metric(n)
    assert all(np.allclose(x.T @ c + c @ x, 0) for x in t)            # C_{mn} φ_m ψ_n is invariant


def test_the_triplet_cartesian_map_gives_the_adjoint_and_the_reality_condition():
    u, t = ix.triplet_cartesian(), ix.su2_generators(3)
    eps = ix._levi_civita3()
    assert all(np.allclose(u @ t[a] @ np.linalg.inv(u), -1j * eps[a]) for a in range(3))
    phi = np.linalg.inv(u) @ np.array([0.3, -1.1, 0.7])                 # a real Cartesian triplet
    assert phi[2] == pytest.approx(-np.conj(phi[0])) and abs(phi[1].imag) < 1e-15   # φ₋₁ = −φ₊₁*
    assert np.allclose(u.T @ u, ix.su2_metric(3))                       # λ^A λ^A = C_{mn} λ_m λ_n


def test_su3_structure_constants():
    f = ix.su3_structure()
    assert f[0, 1, 2] == pytest.approx(1.0) and f[3, 4, 7] == pytest.approx(np.sqrt(3) / 2)
    t = ix.su3_generators("8")
    assert np.allclose(t[0] @ t[1] - t[1] @ t[0], 1j * t[2])


def spec(terms, fields):
    return ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "c", "value": 1.0}]})


PHI = {"name": "phi", "role": "dark_matter", "spin": 0, "dark_parity": -1, "charges": {"su2": 2, "hypercharge": 0.5}}


def test_two_doublet_quartics_need_their_indices_and_parse_into_different_tensors():
    occ = [{"field": "H"}, {"field": "H", "conjugate": True}, {"field": "phi"}, {"field": "phi", "conjugate": True}]
    s = spec([{"fields": occ, "lorentz": "scalar", "coupling": "c"}], [PHI, H])
    with pytest.raises(ix.IndexError_, match="2 independent"):
        ix.contraction(s, s.terms[0])
    l3 = s.terms[0].model_copy(update={"indices": "H*[i] H[i] phi*[j] phi[j]"})
    l4 = s.terms[0].model_copy(update={"indices": "H*[i] phi[i] phi*[j] H[j]"})
    a, b = ix.contraction(s, l3), ix.contraction(s, l4)
    order = [b.occurrences.index(o) for o in a.occurrences]              # b's axes in a's occurrence order
    assert a.su2.shape == (2, 2, 2, 2) and not np.allclose(a.su2, np.transpose(b.su2, order))


def test_the_stated_contractions_span_a_terms_invariants_and_say_when_pairings_cannot():
    """``stated_contractions`` (the generator's terms, 2026-10-20): λ₃ and λ₄ of a second doublet, λ₅'s single
    pairing, two colour triplets' two, and nothing for a triplet joined to two doublets (σ must be stated)."""
    def term(*occ):
        return spec([{"fields": [{"field": f, "conjugate": c} for f, c in occ], "lorentz": "scalar",
                      "coupling": "c"}], [PHI, H, TRIPLET, R, T]).terms[0]
    s = spec([], [PHI, H, TRIPLET, R, T])
    assert ix.stated_contractions(s, term(("H", False), ("H", True), ("phi", False), ("phi", True))) == [
        "H[i] H*[i] phi[j] phi*[j]", "H[i] H*[j] phi[j] phi*[i]"]                     # |H|²|φ|², |H†φ|²
    l5 = ix.stated_contractions(s, term(("H", False), ("H", False), ("phi", True), ("phi", True)))
    assert l5 == ["H[i] H[j] phi*[i] phi*[j]"]                                       # (φ†H)²
    assert len(ix.stated_contractions(s, term(("R", False), ("R", True), ("T", False), ("T", True)))) == 2
    assert ix.stated_contractions(s, term(("H", True), ("Delta", False), ("H", False))) == []
    for text in l5:                                                                  # each is invariant
        ix.contraction(s, term(("H", False), ("H", False), ("phi", True), ("phi", True)).model_copy(
            update={"indices": text}))


TRIPLET = {"name": "Delta", "role": "mediator", "spin": 0, "self_conjugate": True, "charges": {"su2": 3}}
R = {"name": "R", "role": "mediator", "spin": 0, "charges": {"su3": "3", "hypercharge": 2 / 3}}
T = {"name": "T", "role": "mediator", "spin": 0, "charges": {"su3": "3", "hypercharge": -1 / 3}}


def test_a_field_with_its_conjugate_pairs_by_delta_and_two_doublets_by_epsilon():
    single = {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1}
    s = spec([{"fields": [{"field": "S"}, {"field": "S"}, {"field": "H"}, {"field": "H", "conjugate": True}],
               "lorentz": "scalar", "coupling": "c"}], [single, H])
    c = ix.contraction(s, s.terms[0])
    assert np.allclose(np.squeeze(c.su2), np.eye(2))                    # S² H†H
    d = {"name": "D", "role": "dark_matter", "spin": 0.5, "chirality": "L", "charges": {"su2": 2, "hypercharge": -0.5}}
    s2 = spec([{"fields": [{"field": "D"}, {"field": "H"}, {"field": "S"}], "lorentz": "scalar", "coupling": "c"}],
              [d, H, single])
    assert np.allclose(np.squeeze(ix.contraction(s2, s2.terms[0]).su2), [[0, 1], [-1, 0]])   # ε, ε₁₂ = +1


def test_the_notation_is_checked():
    s = spec([{"fields": [{"field": "H"}, {"field": "H", "conjugate": True}], "lorentz": "scalar", "coupling": "c",
               "indices": "H*[i] H[j]"}], [H, {**PHI, "charges": {}}])
    with pytest.raises(ix.IndexError_, match="exactly twice"):
        ix.contraction(s, s.terms[0])
    wrong = s.terms[0].model_copy(update={"indices": "H*[i] H[i] H[k]"})
    with pytest.raises(ix.IndexError_, match="names"):
        ix.contraction(s, wrong)


def test_a_majorana_current_is_neutral_under_its_u1():
    """N̄γ^μγ⁵N Z′ of a Majorana N with B−L charge −1, written without a conjugation mark (N̄ = NᵀC): neutral, as
    is N N Φ with Φ of charge +2; N N Z′ alone, a mass-type product, is not (Okada et al.'s entry, G4 held-out)."""
    from adroit.core.model_spec import ModelSpec
    from adroit.model_building.indices import IndexError_, contraction
    spec = ModelSpec.model_validate({"name": "bl", "phase": "unbroken", "fields": [
        {"name": "N", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
         "mass_gev": 500.0, "charges": {"extra": {"BL": -1.0}}},
        {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 3000.0},
        {"name": "Phi", "role": "mediator", "spin": 0, "mass_gev": 1000.0, "charges": {"extra": {"BL": 2.0}}}],
        "couplings": [{"name": "g", "value": 0.2}],
        "terms": [{"fields": [{"field": "N"}, {"field": "N"}, {"field": "Zp"}], "lorentz": "axial", "coupling": "g"},
                  {"fields": [{"field": "N"}, {"field": "N"}, {"field": "Phi"}], "lorentz": "scalar", "coupling": "g"},
                  {"fields": [{"field": "N"}, {"field": "N"}], "lorentz": "scalar", "coupling": "g"}]})
    contraction(spec, spec.terms[0])
    contraction(spec, spec.terms[1])
    with pytest.raises(IndexError_, match="net BL"):
        contraction(spec, spec.terms[2])

"""Textbook field contents give their textbook Lagrangians."""

from adroit.core.model_spec import FieldRole
from adroit.model_building.content import STANDARD_MODEL, content
from adroit.model_building.lagrangian import general_lagrangian
from tests.model_building.conftest import field, model


def inventory(ops) -> set[tuple]:
    return {(o.structure, tuple(sorted(o.blocks)), o.count) for o in ops}


def test_the_standard_model() -> None:
    ops = inventory(general_lagrangian(list(STANDARD_MODEL), include_standard_model=True))
    assert ops == {("mass", ("H", "H*"), 1), ("potential", ("H", "H", "H*", "H*"), 1),
                   ("yukawa", ("H", "Q", "uR^c"), 9), ("yukawa", ("H*", "Q", "dR^c"), 9),
                   ("yukawa", ("H*", "L", "eR^c"), 9)}


def test_real_singlet_with_and_without_z2() -> None:
    odd = inventory(general_lagrangian(content(model(field("S", 0, self_conjugate=True, dark_parity=-1)))))
    assert odd == {("mass", ("S", "S"), 1), ("potential", ("H", "H*", "S", "S"), 1), ("potential", ("S", "S", "S", "S"), 1)}
    free = {o.blocks.__len__() for o in general_lagrangian(content(model(field("S", 0, self_conjugate=True))))}
    assert free == {1, 2, 3, 4}                      # the tadpole, S|H|² and S³ appear without the Z2


def test_inert_doublet_has_five_quartics() -> None:
    ops = general_lagrangian(content(model(field("Phi", 0, charges={"su2": 2, "hypercharge": 0.5}, dark_parity=-1))))
    quartics = [o for o in ops if o.dimension == 4]
    assert sum(o.count for o in quartics) == 4      # λ2, λ3, λ4, λ5 (λ1 is the Standard Model's)
    assert any(o.blocks == ["H", "H", "Phi*", "Phi*"] and not o.hermitian for o in quartics)    # λ5, + h.c.


def test_minimal_dark_matter_is_accidentally_stable() -> None:
    ops = general_lagrangian(content(model(field("X", 0.5, self_conjugate=True, charges={"su2": 5}))))
    assert [o.structure for o in ops] == ["mass"]


def test_fermion_triplet_couples_to_l_h_only_without_the_z2() -> None:
    free = inventory(general_lagrangian(content(model(field("Sigma", 0.5, self_conjugate=True, charges={"su2": 3})))))
    assert ("yukawa", ("H", "L", "Sigma"), 3) in free
    odd = general_lagrangian(content(model(field("Sigma", 0.5, self_conjugate=True, charges={"su2": 3}, dark_parity=-1))))
    assert [o.structure for o in odd] == ["mass"]


def test_scalar_triplet_type_two() -> None:
    chi = field("chi", 0.5, self_conjugate=True, dark_parity=-1)
    delta = field("Delta", 0, role=FieldRole.other, charges={"su2": 3, "hypercharge": 1.0})
    ops = inventory(o for o in general_lagrangian(content(model(chi, delta))) if "Delta" in o.fields)
    assert ("yukawa", ("Delta", "L", "L"), 6) in ops and ("potential", ("Delta*", "H", "H"), 1) in ops
    assert ("potential", ("Delta", "Delta*", "H", "H*"), 2) in ops and ("potential", ("Delta", "Delta", "Delta*", "Delta*"), 2) in ops


def test_neutral_dirac_fermion_admits_majorana_masses_unless_charged() -> None:
    plain = general_lagrangian(content(model(field("chi", 0.5, dark_parity=-1))))
    assert {tuple(o.blocks) for o in plain} == {("chi", "chi"), ("chi", "chi^c"), ("chi^c", "chi^c")}
    charged = general_lagrangian(content(model(field("chi", 0.5, dark_parity=-1, charges={"extra": {"D": 1.0}}))))
    assert [tuple(o.blocks) for o in charged] == [("chi", "chi^c")]


def test_vectors() -> None:
    chi = field("chi", 0.5, dark_parity=-1, charges={"extra": {"D": 1.0}})
    zp = field("Zp", 1, role=FieldRole.mediator, self_conjugate=True)
    ops = general_lagrangian(content(model(chi, zp)))
    structures = [o.structure for o in ops]
    assert structures.count("vector_current") == 7 and "kinetic_mixing" in structures and "scalar_current" in structures
    dark_photon = general_lagrangian(content(model(field("chi", 0.5, dark_parity=-1, charges={"extra": {"Ap": 1.0}}),
                                                   field("Ap", 1, role=FieldRole.mediator, self_conjugate=True))))
    assert "vector_current" not in [o.structure for o in dark_photon]      # couplings come from D_μ
    vector_dm = general_lagrangian(content(model(field("V", 1, self_conjugate=True, dark_parity=-1))))
    assert {o.text for o in vector_dm} == {"V_μ V^μ", "V_μ V^μ (H H*)"}


def test_unsupported_fields_are_refused() -> None:
    import pytest
    with pytest.raises(ValueError):
        content(model(field("W2", 1, charges={"su2": 3})))                 # a non-abelian vector
    with pytest.raises(ValueError):
        content(model(field("S", 0, self_conjugate=True, charges={"hypercharge": 1.0})))

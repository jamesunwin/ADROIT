from adroit.core.model_spec import FieldRole
from adroit.model_building import eft, indices
from adroit.model_building.content import content
from adroit.model_building.lagrangian import general_lagrangian
from adroit.model_building.spec import general_spec
from tests.model_building.conftest import field, model


def test_dirac_and_majorana_bilinears() -> None:
    dirac = eft.operators(model(field("chi", 0.5, dark_parity=-1)), 6)
    majorana = eft.operators(model(field("chi", 0.5, self_conjugate=True, dark_parity=-1)), 6)
    assert len(dirac) == 20 and len(majorana) == 9
    assert not any(o.lorentz in ("vector", "dipole", "charge_radius") for o in majorana)
    assert {o.dimension for o in eft.operators(model(field("chi", 0.5, dark_parity=-1)), 5)} == {5.0}


def test_effective_operators_are_for_the_dark_matter_only() -> None:
    ops = eft.operators(model(field("chi", 0.5, dark_parity=-1), field("Zp", 1, role=FieldRole.mediator,
                                                                       self_conjugate=True)), 6)
    assert all("chi" in o.fields for o in ops)


def test_eft_validity() -> None:
    assert eft.eft_flags(4, None, 100) == []
    assert any("freeze-out" in f for f in eft.eft_flags(6, 500, 300))
    assert any("cutoff" in f for f in eft.eft_flags(6, None, 300))
    assert not any("freeze-out" in f for f in eft.eft_flags(6, 5000, 300))


def test_the_general_spec_speaks_dirac() -> None:
    base = model(field("chi", 0.5, dark_parity=-1, charges={"extra": {"D": 1.0}}),
                 field("Zp", 1, role=FieldRole.mediator, self_conjugate=True),
                 field("S", 0, role=FieldRole.mediator, self_conjugate=True))
    spec = general_spec(base, general_lagrangian(content(base)))
    labels = {t.lorentz for t in spec.terms if {o.field for o in t.fields} == {"Zp", "chi"}}
    assert labels == {"vector", "axial"}
    yuk = [t for t in spec.terms if {o.field for o in t.fields} == {"S", "chi"}]
    assert {t.lorentz for t in yuk} == {"scalar", "pseudoscalar"}
    assert {"H", "B", "Q"} <= {f.name for f in spec.fields}
    assert all(c.value is None for c in spec.couplings)


def test_the_general_lagrangian_of_a_second_doublet_has_its_four_quartics_and_builds() -> None:
    """A second doublet's potential has λ₂, λ₃, λ₄ and λ₅ (plus its mass); until 2026-10-20 the generator wrote
    H H† H₂ H₂† once, without indices, so λ₄ was missing and G1 refused λ₅'s term. Every term now has a contraction."""
    base = model(field("H2", 0, dark_parity=-1, charges={"su2": 2, "hypercharge": 0.5}))
    spec = general_spec(base, general_lagrangian(content(base)))
    quartics = [t for t in spec.terms if len(t.fields) == 4]
    assert len(quartics) == 4 and len({t.coupling for t in quartics}) == 4
    assert {c.name for c in spec.couplings} >= {t.coupling for t in spec.terms}
    for t in spec.terms:
        indices.contraction(spec, t)

"""The audit: seeded errors are caught, valid models raise no alarm, omitted terms are found."""

import pytest
import yaml

from adroit.core.model_spec import FieldRole, ModelCoupling, ModelSpec, ModelTerm, Occurrence
from adroit.model_building.audit import audit, coupling_dimension, operator_dimension
from adroit.model_building.content import content
from adroit.model_building.lagrangian import general_lagrangian
from adroit.model_building.spec import general_spec
from tests.model_building.conftest import field, model


def with_terms(spec: ModelSpec, *terms: tuple, couplings: dict | None = None) -> ModelSpec:
    built = []
    for fields, lorentz, coupling, *rest in terms:
        built.append(ModelTerm(fields=[Occurrence(field=f.lstrip("~"), conjugate=f.startswith("~")) for f in fields],
                               lorentz=lorentz, coupling=coupling, plus_hc=bool(rest and rest[0])))
    cs = [ModelCoupling(name=n, mass_dimension=d) for n, d in (couplings or {}).items()]
    names = {c.name for c in cs}
    cs += [ModelCoupling(name=t.coupling) for t in built if t.coupling not in names and t.coupling.isidentifier()]
    data = spec.model_dump()
    data.update(terms=[t.model_dump() for t in built], couplings=[c.model_dump() for c in cs])
    return ModelSpec.model_validate(data)


CHI = field("chi", 0.5, dark_parity=-1, charges={"extra": {"D": 1.0}})
MAJ = field("chi", 0.5, self_conjugate=True, dark_parity=-1)
ZP = field("Zp", 1, role=FieldRole.mediator, self_conjugate=True)
S = field("S", 0, role=FieldRole.mediator, self_conjugate=True)
PHI = field("phi", 0, dark_parity=-1, charges={"extra": {"D": 1.0}})

SEEDED = [
    ("vector label without a vector field", model(CHI, S), (["~chi", "chi", "S"], "vector", "g"), "Lorentz"),
    ("scalar label with a lone vector", model(CHI, ZP), (["~chi", "chi", "Zp"], "scalar", "g"), "Lorentz"),
    ("odd number of fermions", model(CHI, S), (["chi", "S"], "scalar", "g"), "Lorentz"),
    ("dipole without a field strength", model(CHI, S), (["~chi", "chi", "S"], "dipole", "d"), "Lorentz"),
    ("kinetic mixing of a scalar", model(CHI, S, ZP), (["Zp", "S"], "kinetic_mixing", "eps"), "Lorentz"),
    ("Majorana vector current", model(MAJ, ZP), (["~chi", "chi", "Zp"], "vector", "g"), "identity"),
    ("real scalar current", model(MAJ, S, ZP), (["S", "S", "Zp"], "scalar_current", "g"), "identity"),
    ("dimension-5 term with a dimensionless coupling", model(CHI, S), (["~chi", "chi", "S", "S"], "scalar", "g"), "dimension"),
    ("gauge charge left over", model(CHI, S), (["chi", "chi", "S"], "scalar", "g"), "gauge"),
    ("dimension-5 quartic of a fermion quintuplet", model(field("X", 0.5, self_conjugate=True, charges={"su2": 5}), S), (["X", "X", "S", "S"], "scalar", "g", False), "dimension"),
]


@pytest.mark.parametrize("what, spec, term, check", SEEDED, ids=[s[0] for s in SEEDED])
def test_seeded_errors_are_caught(what, spec, term, check) -> None:
    report = audit(with_terms(spec, term))
    assert not report.valid and check in {p.check for p in report.problems}, report.problems


def test_a_dimension_five_term_with_a_cutoff_is_valid_and_flagged() -> None:
    higgs = field("H", 0, role=FieldRole.standard_model, charges={"su2": 2, "hypercharge": 0.5})
    spec = with_terms(model(field("chi", 0.5, dark_parity=-1, mass_gev=300.0, charges={"extra": {"D": 1.0}}), higgs),
                      (["~chi", "chi", "H", "~H"], "scalar", "c5"), couplings={"c5": -1})
    report = audit(spec)
    assert report.valid and any("dimension-5" in f for f in report.flags)


def test_dm8_gate_models_raise_no_alarm() -> None:
    models = yaml.safe_load(open("docs/dm8/gate_models.yaml"))["models"]
    for m in models:
        report = audit(ModelSpec.model_validate(m["reference"]["spec"]))
        assert report.valid, (m["name"], report.problems)


@pytest.mark.parametrize("fields", [
    [CHI, ZP], [field("Phi", 0, charges={"su2": 2, "hypercharge": 0.5}, dark_parity=-1)],
    [field("S", 0, self_conjugate=True, dark_parity=-1)], [MAJ, S],
    [field("V", 1, self_conjugate=True, dark_parity=-1)]])
def test_generated_models_are_valid_and_complete(fields) -> None:
    base = model(*fields)
    full = general_spec(base, general_lagrangian(content(base)))
    report = audit(full)
    assert report.valid and not report.missing, (report.problems, [t.text for t in report.missing])


def test_omitted_terms_are_found() -> None:
    singlet = with_terms(model(field("S", 0, self_conjugate=True, dark_parity=-1)), (["S", "S", "S", "S"], "scalar", "lam"))
    assert any(t.text == "H H* S S" for t in audit(singlet).missing)                  # the Higgs portal
    zp = with_terms(model(CHI, ZP), (["Zp", "~chi", "chi"], "vector", "g"))
    missing = audit(zp).missing
    assert {"kinetic_mixing", "axial"} <= {t.lorentz for t in missing}                  # kinetic mixing, axial
    dirac = with_terms(model(field("chi", 0.5, dark_parity=-1), S), (["S", "~chi", "chi"], "scalar", "y"))
    report = audit(dirac)
    assert any("(pseudoscalar)" in t.text for t in report.missing) and any("pseudo-Dirac" in n for n in report.notes)


def test_dimensions_of_operators_and_couplings() -> None:
    spec = with_terms(model(CHI, ZP), (["Zp", "~chi", "chi"], "vector", "g*m_chi/v"))
    term = spec.terms[0]
    assert operator_dimension(spec, term) == 4 and coupling_dimension(spec, term) == 0


def test_broken_phase_models_are_not_compared_for_missing_terms() -> None:
    spec = ModelSpec.model_validate({**model(CHI, S).model_dump(), "phase": "broken"})
    assert "below" in audit(spec).notes[0] if audit(spec).notes else True


def test_identical_scalars_enter_the_gauge_check_as_a_symmetric_power():
    """Release audit minor: ε_ij D^i D^j and ε_abc T^a T^b T^c vanish for one bosonic field, so neither is an
    invariant; D†D and a real SU(2) triplet's square are."""
    from adroit.model_building.audit import gauge_invariant
    doublet = field("D", 0, role=FieldRole.mediator, charges={"su2": 2})
    triplet = field("T", 0, role=FieldRole.mediator, charges={"su3": "3"})
    real_triplet = field("W3", 0, role=FieldRole.mediator, self_conjugate=True, charges={"su2": 3})
    dd = with_terms(model(CHI, doublet), (["D", "D"], "scalar", "m2"))
    ttt = with_terms(model(CHI, triplet), (["T", "T", "T"], "scalar", "y"))
    assert not gauge_invariant(dd, dd.terms[0]) and not gauge_invariant(ttt, ttt.terms[0])
    ddbar = with_terms(model(CHI, doublet), (["~D", "D"], "scalar", "m2"))
    ww = with_terms(model(CHI, real_triplet), (["W3", "W3"], "scalar", "m2"))
    assert gauge_invariant(ddbar, ddbar.terms[0]) and gauge_invariant(ww, ww.terms[0])


SMUON = field("phi", 0, role=FieldRole.mediator, dark_parity=-1, charges={"hypercharge": -1.0})


def _muon(name: str = "mu") -> object:
    return field(name, 0.5, role=FieldRole.standard_model, chirality="R", charges={"hypercharge": -1.0})


def test_an_sm_field_under_its_own_name_is_the_generators_field_live_check_l2() -> None:
    """Live check L2: a right-handed muon typed as `mu` made the audit call the model's only interaction
    `eR^c chi phi` missing. `mu` is now read as eR in generation 2, and the general Lagrangian keeps `mu`."""
    spec = with_terms(model(MAJ, SMUON, _muon()), (["~phi", "chi", "mu"], "chiral", "y", True))
    report = audit(spec)
    assert report.valid
    assert not any({o.field for o in t.fields} & {"mu", "eR"} for t in report.missing)
    assert any("read as eR, generation 2 of 3" in n for n in report.notes)
    general = general_spec(spec.model_copy(update={"terms": [], "couplings": []}), general_lagrangian(content(spec)))
    assert "eR" not in {f.name for f in general.fields} and "mu^c chi phi" in {t.text for t in general.terms}


def test_two_flavours_of_one_sm_field_share_its_terms() -> None:
    spec = with_terms(model(MAJ, SMUON, _muon("mu"), _muon("tau")),
                      (["~phi", "chi", "mu"], "chiral", "y_mu", True), (["~phi", "chi", "tau"], "chiral", "y_tau", True))
    report = audit(spec)
    assert not any({o.field for o in t.fields} & {"mu", "tau", "eR"} for t in report.missing)
    assert sum("shares eR's terms" in n for n in report.notes) == 2


def test_sm_identity_matches_quantum_numbers_and_names_the_generation() -> None:
    from adroit.model_building.spec import generation, sm_identity
    assert [generation(n) for n in ("mu", "muR", "tau_R", "bR", "t", "chi")] == [2, 2, 3, 3, 3, None]
    left = field("muL", 0.5, role=FieldRole.standard_model, chirality="L", charges={"hypercharge": -1.0})
    identity = sm_identity(model(MAJ, _muon("bR"), left))
    assert identity.own == {"eR": "bR"} and identity.shared == {}          # quantum numbers decide, not the name
    assert sm_identity(model(MAJ, field("eR", 0.5, role=FieldRole.standard_model, chirality="R",
                                        charges={"hypercharge": -1.0}))).own == {}


def test_a_coupling_set_to_zero_is_flagged_as_natural_only_under_a_protecting_symmetry() -> None:
    """The owner (2026-10-12): a zero coupling is technically natural only if a symmetry protects it."""
    spec = with_terms(model(MAJ, SMUON, _muon()), (["~phi", "chi", "mu"], "chiral", "y", True))
    spec = spec.model_copy(update={"couplings": [c.model_copy(update={"value": 0.0}) for c in spec.couplings]})
    report = audit(spec)
    assert any(f.startswith("y = 0") and "technically natural only if a symmetry protects this zero" in f
               for f in report.flags)
    assert not any("technically natural" in f for f in audit(with_terms(model(MAJ, SMUON, _muon()),
                                                                         (["~phi", "chi", "mu"], "chiral", "y", True))).flags)

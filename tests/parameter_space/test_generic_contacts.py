"""Four-fermion contact interactions in the generic route (the batch plan's §5, 2026-10-20): G1 accepts
(Ψ̄_DΓΨ_D)(f̄Γ'f), G2 writes FFFF vertices, and a heavy mediator integrated out gives the same relic density and
direct detection as its contact operator; the relic is refused where √s at freeze-out is not well below Λ."""
import pytest

from adroit.core.model_spec import ModelSpec
from adroit.model_building.gauge_basis import GaugeBasisError
from adroit.parameter_space.portals import generic, generic_dd
from adroit.parameter_space.portals.generic import GenericModel

HEAVY = 1e5


def _occ(*names):
    return [{"field": n.rstrip("*"), "conjugate": n.endswith("*")} for n in names]


def _fields(sm: str = "l", majorana: bool = False, m_chi: float = 500.0) -> list[dict]:
    return [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": m_chi,
             "self_conjugate": majorana}, {"name": sm, "role": "standard_model", "spin": 0.5}]


def _mediator(lorentz: str, g_chi: float, g_f: float, sm: str = "l", majorana: bool = False, spin: int = 1,
              m_chi: float = 500.0, yukawa: bool = False, mass: float = HEAVY) -> GenericModel:
    half = 0.5 if majorana else 1.0                      # a Majorana bilinear's Lagrangian ½
    spec = ModelSpec.model_validate({"name": "mediator", "phase": "broken", "fields": _fields(sm, majorana, m_chi) + [
        {"name": "X", "role": "mediator", "spin": spin, "self_conjugate": True, "mass_gev": mass}],
        "terms": [{"fields": _occ("chi*", "chi", "X"), "lorentz": lorentz, "coupling": f"{half}*g_chi"},
                  {"fields": _occ(f"{sm}*", sm, "X"), "lorentz": lorentz,
                   "coupling": "g_f*m_q/v" if yukawa else "g_f"}],
        "couplings": [{"name": "g_chi", "value": g_chi}, {"name": "g_f", "value": g_f}]})
    return GenericModel.for_spec(spec)


def _contact(label: str, c: float, sm: str = "l", majorana: bool = False, m_chi: float = 500.0,
             yukawa: bool = False) -> GenericModel:
    spec = ModelSpec.model_validate({"name": "contact", "phase": "broken", "fields": _fields(sm, majorana, m_chi),
                                     "terms": [{"fields": _occ("chi*", "chi", f"{sm}*", sm), "lorentz": label,
                                                "coupling": "c*m_q/v" if yukawa else "c"}],
                                     "couplings": [{"name": "c", "value": c}]})
    return GenericModel.for_spec(spec)


@pytest.mark.parametrize("majorana, lorentz, label", [(False, "vector", "VV"), (True, "axial", "AA")])
def test_a_heavy_vector_and_its_contact_operator_give_the_same_relic(majorana, lorentz, label):
    """L ⊃ X·(g_χ J_χ + g_f J_f) integrated out is −g_χ g_f (J_χ·J_f)/M² (J_χ = ½χ̄Γχ for Majorana χ): Ωh² to
    2 × 10⁻³, the size of the mediator's s/M² (5 × 10⁻⁴ at freeze-out) and Γ²/M² (2 × 10⁻⁵) here. (A broad mediator,
    Γ ≈ M, is not its contact: the propagator's constant width halves its rate.)"""
    g, mass = 0.2, 1e4
    c = -g * g / mass ** 2 * (0.5 if majorana else 1.0)
    heavy = _mediator(lorentz, g, g, majorana=majorana, m_chi=100.0, mass=mass)
    contact = _contact(label, c, majorana=majorana, m_chi=100.0)
    a, b = heavy.omega_h2(heavy.point()), contact.omega_h2(contact.point())
    assert contact.domain(contact.point()) == "" and b == pytest.approx(a, rel=2e-3)


@pytest.mark.parametrize("lorentz, label, spin, yukawa, field", [
    ("scalar", "SS", 0, True, "c1_p"), ("vector", "VV", 1, False, "c1_p_odd"), ("axial", "AA", 1, False, "c4_p")])
def test_a_heavy_mediator_and_its_contact_operator_scatter_alike(lorentz, label, spin, yukawa, field):
    """Direct detection: the contact is DirectDM's operator itself (C61–C64, C75–C78), the mediator's exchange the
    same at q → 0."""
    sign = 1.0 if spin == 0 else -1.0
    heavy = _mediator(lorentz, 0.5, 0.3, sm="q", spin=spin, m_chi=100.0, yukawa=yukawa)
    contact = _contact(label, sign * 0.15 / HEAVY ** 2, sm="q", m_chi=100.0, yukawa=yukawa)
    out = []
    for engine in (heavy, contact):
        mb, rules, _ = engine.at(engine.point())
        out.append(getattr(generic_dd.scattering(mb, rules).nucleon, field))
    assert out[0] != 0 and out[1] == pytest.approx(out[0], rel=1e-9)


def test_the_relic_is_refused_where_freeze_out_is_not_well_below_the_contact_scale():
    """√s at freeze-out ≈ 2m_χ(1 + 3/2x_f) against Λ = |c|^(−1/2): refused above Λ/3, with the reason."""
    c = -1.0 / 3000.0 ** 2                                # Λ = 3 TeV
    assert _contact("VV", c, m_chi=400.0).domain(_contact("VV", c, m_chi=400.0).point()) == ""
    far = _contact("VV", c, m_chi=600.0)
    assert "not well below the contact term's scale" in far.domain(far.point())


def test_a_relic_between_a_fifth_and_a_third_of_the_contact_scale_is_computed_and_flagged():
    """The owner's decision #6 (2026-10-20): keep Λ/3, flag Λ/5 < √s ≤ Λ/3 with the shift a unit-coupling mediator of
    mass Λ would make, |1/(1 − s/Λ²)|² − 1: 27% at Λ/3 (not the 20% once written), 9% at Λ/5."""
    assert generic.contact_shift(1.0, 3.0) == pytest.approx(81 / 64 - 1) and round(generic.contact_shift(1, 3), 2) == 0.27
    assert generic.contact_shift(1.0, 5.0) == pytest.approx(625 / 576 - 1)
    c = -1.0 / 3000.0 ** 2                                # Λ = 3 TeV: Λ/5 = 600 GeV, Λ/3 = 1000 GeV
    flagged = {}
    for m_chi in (250.0, 400.0, 600.0):                   # √s = 537.5, 860 and 1290 GeV
        engine = _contact("VV", c, m_chi=m_chi)
        mb, rules, _ = engine.at(engine.point())
        flagged[m_chi] = generic._contact_flag(mb, rules)
    assert flagged[250.0] == "" and flagged[600.0] == ""
    assert "between Λ/5 and Λ/3" in flagged[400.0] and "by about 19%" in flagged[400.0]
    near = _contact("VV", c, m_chi=400.0)
    assert near.domain(near.point()) == "" and flagged[400.0] in near.flags(near.point())


def test_contact_terms_g2_has_no_rule_for_are_refused_and_a_tensor_scatters_pending():
    def build(terms, fields=None):
        spec = ModelSpec.model_validate({"name": "x", "phase": "broken", "fields": fields or _fields("q"),
                                         "terms": terms, "couplings": [{"name": "c", "value": 1e-8}]})
        engine = GenericModel.for_spec(spec)
        return engine, engine.at(engine.point())
    with pytest.raises(GaugeBasisError, match="dark self-interactions"):
        build([{"fields": _occ("chi*", "chi", "chi*", "chi"), "lorentz": "VV", "coupling": "c"}])
    with pytest.raises(GaugeBasisError, match="lorentz one of"):
        build([{"fields": _occ("chi*", "chi", "q*", "q"), "lorentz": "vector", "coupling": "c"}])
    engine, (mb, rules, _) = build([{"fields": _occ("chi*", "chi", "q*", "q"), "lorentz": "TT", "coupling": "c"}])
    assert any("tensor contact" in p for p in generic_dd.scattering(mb, rules).pending)


def test_a_weyl_fields_contact_bilinear_is_its_chiral_current():
    """Above breaking, (χ̄γ^μχ)(L̄γ_μL) is the left-handed current ½(V − A) of each lepton and neutrino; a scalar
    bilinear of a Weyl field is refused."""
    fields = [_fields()[0], {"name": "L", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
                             "charges": {"su2": 2, "hypercharge": -0.5}}]
    spec = ModelSpec.model_validate({"name": "left", "phase": "unbroken", "fields": fields,
                                     "terms": [{"fields": _occ("chi*", "chi", "L*", "L"), "lorentz": "VV",
                                                "coupling": "c"}], "couplings": [{"name": "c", "value": -1e-8}]})
    engine = GenericModel.for_spec(spec)
    _, rules, _ = engine.at(engine.point())
    contacts = {v.legs[3]: v.structure for v in rules.vertices if v.kind == "FFFF"}
    assert {"e", "mu", "tau", "nu_e"} <= set(contacts)
    assert contacts["mu"] == (("V", "V", pytest.approx(-0.5e-8)), ("V", "A", pytest.approx(0.5e-8)))
    scalar = GenericModel.for_spec(spec.model_copy(update={"terms": [spec.terms[0].model_copy(update={"lorentz": "SS"})]}))
    with pytest.raises(GaugeBasisError, match="Weyl field"):
        scalar.at(scalar.point())


def test_a_majorana_contact_scatters_as_its_heavy_mediator():
    """Majorana χ: L ⊃ X·(½g_χ χ̄γγ⁵χ + g_q q̄γγ⁵q) is the contact −(g_χ g_q/2M²)(χ̄γ^μγ⁵χ)(q̄γ_μγ⁵q); DirectDM's
    Majorana operators carry ½, so both give the same c₄."""
    heavy = _mediator("axial", 0.5, 0.3, sm="q", majorana=True, m_chi=100.0)
    contact = _contact("AA", -0.5 * 0.3 / (2 * HEAVY ** 2), sm="q", majorana=True, m_chi=100.0)
    out = []
    for engine in (heavy, contact):
        mb, rules, _ = engine.at(engine.point())
        out.append(generic_dd.scattering(mb, rules).nucleon.c4_p)
    assert out[0] != 0 and out[1] == pytest.approx(out[0], rel=1e-9)


def test_a_contact_written_as_two_halves_is_judged_as_the_whole():
    """The tactical audit's T20-04: the validity scale took the largest single term, so two halves of a contact
    refused as a whole (√s = 1290 GeV > Λ/3 = 1000 GeV) gave Ωh² = 0.111; and two terms that cancel are no contact."""
    whole = _contact("VV", -1 / 3000 ** 2, m_chi=600.0)
    spec = whole.model_spec()
    half = spec.terms[0].model_copy(update={"coupling": spec.terms[0].coupling + "/2"})
    split = GenericModel.for_spec(spec.model_copy(update={"terms": [half, half]}))
    assert whole.domain(whole.point()).startswith("√s at freeze-out (1290 GeV)")
    assert split.domain(split.point()) == whole.domain(whole.point()) and split.omega_h2(split.point()) is None
    against = half.model_copy(update={"coupling": "-(" + half.coupling + ")"})
    cancelled = GenericModel.for_spec(spec.model_copy(update={"terms": [half, against]}))
    assert "contact" not in cancelled.domain(cancelled.point())

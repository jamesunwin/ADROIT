"""The Yukawa convention (the owner's decision #2, 2026-10-20; ``model_building.yukawa``): a model declares the masses
its stated couplings mean by m_f, "sm" by default, a reference card where the library's simplified mediators use one.
Equivalent models with the same declared convention agree across routes; the convention changes no kinematic mass,
no explicitly supplied coupling and not the Higgs boson's own Yukawas."""
import math

import pytest

from adroit.core.model_spec import ModelSpec
from adroit.model_building import yukawa
from adroit.model_building.gauge_basis import V_EW
from adroit.parameter_space import library, searches
from adroit.parameter_space.classes import ScalarClass
from adroit.parameter_space.classify import classify
from adroit.parameter_space.portals import generic_portrait as gp
from adroit.parameter_space.portals.generic import GenericModel

CARD = "DMsimp_s_spin0_MD"


def _spec(convention: str, m_med: float, pseudo: bool = False, m_chi: float = 100.0) -> ModelSpec:
    """The library's Yukawa-like scalar (or pseudoscalar) mediator, quark-only (g_q = 1, g_χ = 1), declaring
    ``convention``: L ⊃ −g_χ S χ̄χ − g_q Σ_q (m_q/v) S q̄q."""
    e = library.entry("scalar_mediator")
    spec = e.spec()
    lorentz = "pseudoscalar" if pseudo else "scalar"
    terms = [t.model_copy(update={"lorentz": lorentz}) for t in spec.terms]
    fields = [f.model_copy(update={"mass_gev": {"chi": m_chi, "S": m_med}.get(f.name, f.mass_gev)})
              for f in spec.fields]
    return spec.model_copy(update={"yukawa": convention, "terms": terms, "fields": fields, "couplings": [
        c.model_copy(update={"value": 1.0}) for c in spec.couplings]})


def _routes(convention: str, m_med: float, pseudo: bool = False, m_chi: float = 100.0):
    """(the typed class and its point, the generic portrait) of the same model."""
    spec = _spec(convention, m_med, pseudo, m_chi)
    cls, point, _ = classify(spec)
    engine = GenericModel.for_spec(spec)
    (portrait,) = [m for m in gp.portraits(engine, engine.point()) if m.spin == 0]
    return cls, point, portrait


@pytest.mark.parametrize("convention", ["sm", CARD])
@pytest.mark.parametrize("m_med, pseudo", [(5.0, True), (8.0, False), (80.0, False), (150.0, False)])
def test_the_same_declared_convention_gives_the_same_widths_on_both_routes(convention, m_med, pseudo):
    """Light mediators where c c̄ dominates (a pseudoscalar between 2m_c and 2m_b at 5 GeV, a scalar at 8 GeV) and
    heavier ones, the dark matter's decay closed (m_χ = 100 GeV): the typed class (``classify`` passes the spec's
    convention on) and the generic route give the same total width, b b̄ and c c̄ branching fractions and lifetime.
    The routes share the kinematic masses (b the DMsimp card's 4.7 GeV), so their b thresholds agree too
    (``test_the_yukawa_inputs_and_the_kinematic_b_mass_change_the_width_apart``)."""
    cls, point, m = _routes(convention, m_med, pseudo)
    assert isinstance(cls, ScalarClass) and cls.yukawa == convention
    widths = searches._scalar(cls, point)[3]
    total = sum(widths.values())
    assert m.width_gev == pytest.approx(total, rel=1e-2)
    for name, code in (("b", 5), ("c", 4)):
        typed = widths.get((code, -code), 0.0) / total
        assert m.partial(name, f"{name}~") / m.width_gev == pytest.approx(typed, rel=1e-2, abs=1e-6), name
    assert 6.582119569e-25 / m.width_gev == pytest.approx(6.582119569e-25 / total, rel=1e-2)   # lifetime, s


def _b_vertex(convention: str, m_med: float, pseudo: bool):
    """The mediator's b b̄ vertex in G2's rules, the mediator's index in it and the route's kinematic b mass."""
    from adroit.model_building.feynman import SM_FERMIONS
    engine = GenericModel.for_spec(_spec(convention, m_med, pseudo))
    _, rules, _ = engine.at(engine.point())
    v = next(x for x in rules.vertices if x.kind == "FFS" and sorted(x.legs[:2]) == ["b", "b~"])
    return v, 2, next(f.mass for f in SM_FERMIONS if f.name == "b")


@pytest.mark.parametrize("m_med", [12.0, 20.0, 40.0])
@pytest.mark.parametrize("pseudo", [False, True])
def test_the_yukawa_inputs_and_the_kinematic_b_mass_change_the_width_apart(m_med, pseudo):
    """The owner's answer (2026-10-20): both routes take the DMsimp card's m_b = 4.7 GeV as the b's kinematic mass, and
    the Yukawa inputs are apart from it. The b b̄ width's ratios, with the same vertex function:
    - Yukawa only (the "sm" model over the card's, kinematics fixed): (3.007/4.7)² = 0.409, at every mass;
    - kinematics only (m_b^kin = 4.18, the MS-bar input G2 had used, over 4.7; Yukawas fixed): β³ for a CP-even
      scalar, 1.537 at 12 GeV and 1.0184 at 40, but β for a pseudoscalar, 1.154 and 1.006;
    - both: the product.
    Across routes the same model's width now agrees at the b threshold (it had differed by the kinematic ratio)."""
    from adroit.model_building.feynman import two_body_width
    v_sm, k, m_kin = _b_vertex("sm", m_med, pseudo)
    v_card, _, _ = _b_vertex(CARD, m_med, pseudo)
    assert m_kin == 4.7
    width = {(c, mb): two_body_width(v, k, [mb, mb, m_med])
             for c, v in (("sm", v_sm), (CARD, v_card)) for mb in (4.18, 4.7)}
    yukawa_only = width[("sm", 4.7)] / width[(CARD, 4.7)]
    kinematics_only = width[(CARD, 4.18)] / width[(CARD, 4.7)]
    beta = {mb: math.sqrt(1 - 4 * mb * mb / m_med ** 2) for mb in (4.18, 4.7)}
    power = 1 if pseudo else 3
    assert yukawa_only == pytest.approx((yukawa.mass("sm", "b") / 4.7) ** 2, rel=1e-9)
    assert kinematics_only == pytest.approx((beta[4.18] / beta[4.7]) ** power, rel=1e-9)
    assert width[("sm", 4.18)] / width[(CARD, 4.7)] == pytest.approx(yukawa_only * kinematics_only, rel=1e-9)
    if m_med in (12.0, 40.0):
        quoted = {(12.0, False): 1.537, (40.0, False): 1.0184, (12.0, True): 1.154, (40.0, True): 1.006}
        assert kinematics_only == pytest.approx(quoted[(m_med, pseudo)], abs=1e-3)
    cls, point, generic = _routes(CARD, m_med, pseudo)
    typed = searches._scalar(cls, point)[3][(5, -5)]
    assert generic.partial("b", "b~") / typed == pytest.approx(1.0, rel=1e-3)


def test_the_convention_changes_no_kinematic_mass_supplied_coupling_or_higgs_yukawa():
    """Requirement 4: a card changes the stated m_q only: the thresholds (the b's open channel at 9.5 GeV but not at 9
    GeV, from its kinematic mass), an explicitly numeric coupling and the Higgs boson's own couplings are the same under
    either convention."""
    def built(convention, coupling="g_q*m_q/v", m_med=12.0):
        spec = _spec(convention, m_med)
        spec = spec.model_copy(update={"terms": [spec.terms[0], spec.terms[1].model_copy(update={"coupling": coupling})]})
        engine = GenericModel.for_spec(spec)
        return engine, engine.point()
    from adroit.model_building.feynman import SM_FERMIONS
    explicit = [gp.portraits(*built(c, coupling="0.001"))[0].coupling("b").even for c in ("sm", CARD)]
    assert explicit[0] == explicit[1] and abs(explicit[0]) == pytest.approx(0.001, rel=1e-9)
    for convention in ("sm", CARD):
        engine, p = built(convention)
        _, rules, _ = engine.at(p)
        b = next(x for x in rules.particles if x.name == "b")
        assert b.mass == next(f.mass for f in SM_FERMIONS if f.name == "b")                 # kinematics unchanged
        stated = gp.portraits(engine, p)[0].coupling("b").even
        assert abs(stated) == pytest.approx(yukawa.mass(convention, "b") / V_EW, rel=1e-9)
    h = []
    for convention in ("sm", CARD):                                # a model with the Higgs boson: its Yukawas the same
        engine = GenericModel.for_spec(_mixed(convention))
        _, rules, _ = engine.at(engine.point())
        h.append(gp._sm_couplings(rules, "h", {"b", "c", "t"}))
    assert h[0] == h[1] and h[0]["b"][0] != 0


def test_a_library_entry_carries_its_card_to_the_generic_route_and_reports_name_it():
    """Requirements 1 and 2: the library's Yukawa-like mediators declare the card, and the spec the generic route gets
    from them keeps it; a convention is described with its numbers."""
    for entry_id in ("scalar_mediator", "alp_portal"):
        e = library.entry(entry_id)
        assert e.model_class.yukawa == e.spec().yukawa == CARD
    valued = _spec(CARD, 300.0)
    assert classify(valued)[0].yukawa == CARD and classify(_spec("sm", 300.0))[0].yukawa == "sm"
    assert "b and c MS-bar (one loop) at m_h" in yukawa.describe("sm") and "b 3.007" in yukawa.describe("sm")
    assert "b 4.7" in yukawa.describe(CARD) and "t 172," in yukawa.describe(CARD)
    with pytest.raises(ValueError, match="yukawa is one of"):
        _spec("pole", 20.0).model_validate({**_spec("sm", 20.0).model_dump(), "yukawa": "pole"})
    old = {k: v for k, v in _spec("sm", 20.0).model_dump(mode="json").items() if k != "yukawa"}
    assert ModelSpec.model_validate(old).yukawa == "sm"                          # a stored model reads as "sm"


def test_a_scalar_mixing_the_higgs_under_a_card_leaves_direct_detection_through_it_pending():
    """Requirement 3's other half in direct detection: a singlet mixed with the Higgs boson, its own stated Yukawas the
    card's, carries both conventions; it is named, not silently divided by one."""
    from adroit.model_building import dd_matching as dd
    engine = GenericModel.for_spec(_mixed(CARD))
    mb, rules, _ = engine.at(engine.point())
    m = dd.match(mb, rules)
    assert any(dd.MIXED_CONVENTION in n for n in m.notes)
    assert math.isfinite(sum(m.coefficients.values()) if m.coefficients else 0.0)
    plain = GenericModel.for_spec(_mixed("sm"))
    assert not any(dd.MIXED_CONVENTION in n for n in dd.match(*plain.at(plain.point())[:2]).notes)


def _mixed(convention: str) -> ModelSpec:
    """A singlet S mixed with the Higgs boson through S H†H, coupled to the dark matter, under ``convention``."""
    return ModelSpec.model_validate({"name": "mixed", "phase": "unbroken", "yukawa": convention, "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 50.0},
        {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 200.0},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
        "terms": [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "S"}],
                   "lorentz": "scalar", "coupling": "-1.0"},
                  {"fields": [{"field": "S"}, {"field": "H", "conjugate": True}, {"field": "H"}],
                   "lorentz": "scalar", "coupling": "-10.0"}]})

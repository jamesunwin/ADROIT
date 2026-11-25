"""P5 of ``docs/generic_route_next.md``: the model-specific LEP and LHC combinations through a structural match, and
its declared gate: the library's outcomes on its own models through the generic route, undecided with the reason
for a near match."""
import math

import pytest

from adroit.model_building.gauge_basis import V_EW
from adroit.parameter_space import library, searches
from adroit.parameter_space.portals.generic import GenericModel


def _inert_at(h0: float, a0: float, hc: float, l345: float) -> GenericModel:
    """The library's inert doublet (its fields only, DM12's general potential) at the library's (M_H₀, M_A₀, M_H±,
    λ₃₄₅): V ⊃ μ₂²|H₂|² + λ₃|H|²|H₂|² + λ₄|H†H₂|² + (λ₅/2)[(H†H₂)² + h.c.], the generator's terms L ⊃ +c·O, so
    c₃ = −λ₃, c₄ = −λ₄, c₅ = −λ₅/2."""
    mu2 = h0 ** 2 - l345 * V_EW ** 2 / 2
    l3 = 2 * (hc ** 2 - mu2) / V_EW ** 2
    l4_minus_l5 = 2 * (a0 ** 2 - mu2) / V_EW ** 2 - l3
    l4, l5 = ((l345 - l3) + l4_minus_l5) / 2, ((l345 - l3) - l4_minus_l5) / 2
    values = {"lam_H_H2_2": -l3, "lam_H_H2_2_c2": -l4, "lam_H_H2": -l5 / 2, "lam_H2": -0.1}
    spec = library.entry("inert_doublet").spec()
    spec = spec.model_copy(update={
        "couplings": [c.model_copy(update={"value": values[c.name]}) for c in spec.couplings],
        "fields": [f.model_copy(update={"mass_gev": math.sqrt(mu2)}) if f.name == "H2" else f for f in spec.fields]})
    return GenericModel.for_spec(spec)


@pytest.mark.parametrize("h0, a0, hc, l345", [
    (50.0, 70.0, 120.0, 0.01),          # LEP's (H₀, A₀) region: excluded
    (60.0, 65.0, 65.0, 0.01),           # the charged scalar below 70 GeV: excluded
    (40.0, 45.0, 150.0, 0.01),          # Z → H₀A₀ open: excluded
    (70.0, 75.0, 120.0, 0.01),          # split below 8 GeV: allowed
    (60.0, 110.0, 130.0, -0.005),       # A₀ above 100 GeV: allowed
    (990.0, 992.36, 998.12, -0.051),    # Kalinowski et al. HP10: allowed
])
@pytest.mark.needs("ufo_models")
def test_the_library_inert_doublets_lep_outcome_is_reproduced_through_the_generic_route(h0, a0, hc, l345):
    """P5's gate on the inert doublet: the same masses from the generic spectrum (to 10⁻⁵) and the same decision."""
    e = library.entry("inert_doublet")
    p = e.point.model_copy(update={"m_chi": h0, "m_med": hc, "g_chi": l345, "g_q": a0 - h0})
    engine = _inert_at(h0, a0, hc, l345)
    q = engine.point()
    assert searches._generic_inert(engine, q) == pytest.approx((h0, a0, hc), rel=1e-5)
    ours, theirs = searches.inert_doublet(engine, q, False), searches.inert_doublet(e.model_class, p, False)
    assert theirs is not None and ours is not None and ours.excluded == theirs.excluded


def test_a_doublet_with_company_is_undecided_and_a_model_without_one_is_not_judged():
    """A near match (the doublet and another dark field) is undecided with the reason; a Z′ model has no LEP
    inert-doublet outcome at all."""
    engine = _inert_at(50.0, 70.0, 120.0, 0.01)
    spec = engine.model_spec()
    singlet = {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "dark_parity": -1, "mass_gev": 300.0}
    crowded = GenericModel.for_spec(spec.model_copy(update={"fields": [*spec.fields, type(spec.fields[0])(**singlet)]}))
    outcome = searches.inert_doublet(crowded, crowded.point(), False)
    assert outcome.excluded is None and "doublet alone" in outcome.why
    e = library.entry("dmwg_V1")
    zprime = GenericModel.for_spec(e.spec().model_copy(update={
        "couplings": [c.model_copy(update={"value": 0.25}) for c in e.spec().couplings]}))
    assert searches.inert_doublet(zprime, zprime.point(), False) is None



# --- the 2HDM+a ------------------------------------------------------------------------------------------------------

SCENARIO = {"MXd": 10.0, "mh1": 125.09, "sinp": 0.35, "tanbeta": 1.0, "sinbma": 1.0, "gPXd": 1.0, "lam3": 3.0,
            "laP1": 3.0, "laP2": 3.0}


def _two_hdma_at(m_a: float, m_heavy: float, **change) -> dict:
    return {**SCENARIO, "mh4": m_a, "mh2": m_heavy, "mh3": m_heavy, "mhc": m_heavy, **change}


needs_ufo_reader = pytest.mark.skipif(not __import__("adroit.constraints.maddm", fromlist=["python"]).python().exists(),
                                      reason="the UFO models are read with MadGraph's Python (the tools folder)")
needs_gluon_fusion = pytest.mark.skipif(__import__("adroit.parameter_space.resonances", fromlist=["_rates_missing"])
                                        ._rates_missing().startswith("MadGraph"),
                                        reason="the gluon-fusion tables are not in the tools folder")


@needs_gluon_fusion
@pytest.mark.parametrize("x", [
    _two_hdma_at(200.0, 1000.0), _two_hdma_at(200.0, 1600.0), _two_hdma_at(400.0, 1200.0),
    _two_hdma_at(250.0, 700.0), _two_hdma_at(300.0, 600.0, sinp=0.5, tanbeta=2.0),
    _two_hdma_at(500.0, 700.0), _two_hdma_at(500.0, 800.0), _two_hdma_at(450.0, 900.0),    # mono-h allowed; the island
    _two_hdma_at(400.0, 1000.0, MXd=160.0),                       # the library's benchmark: outside scenario 1a
    _two_hdma_at(300.0, 900.0, MXd=160.0, sinp=0.5, tanbeta=2.0, lam3=2.0, laP1=1.0, laP2=4.0, mh2=950.0, mhc=920.0),
])
def test_the_library_2hdma_outcomes_are_reproduced_through_the_generic_route(x):
    """P5's gate on the 2HDM+a: the Working Group's model written in the Higgs basis as a generic spec
    (``generic_2hdma.spec``) is read back to its parameters, and ATLAS's combination, mono-h and mono-Z give the
    library's own outcomes at those parameters: the same decisions and reasons, ratios to 1%."""
    from adroit.parameter_space import resonances
    from adroit.parameter_space.portals import generic_2hdma
    engine = GenericModel.for_spec(generic_2hdma.spec(x))
    q = engine.point()
    found = generic_2hdma.match(engine, q)
    assert not isinstance(found, str), found
    assert all(found.values[k] == pytest.approx(v, rel=1e-6, abs=1e-9) for k, v in x.items())
    cls, p = generic_2hdma.Match(values=x, names={}).portal()
    for evaluate in (searches.two_hdma, resonances.monoh, resonances.monoz):
        ours, theirs = evaluate(engine, q, True), evaluate(cls, p, True)
        assert (ours is None) == (theirs is None)
        if theirs is not None:
            assert ours.excluded == theirs.excluded and (ours.why or "") == (theirs.why or "")
            if theirs.ratio is not None:
                assert ours.ratio == pytest.approx(theirs.ratio, rel=1e-2)


@needs_ufo_reader
def test_a_near_2hdma_is_undecided_by_atlas_2hdma_searches_with_the_reason():
    """A generic model with the 2HDM+a's fields that is not the model (type-I Yukawas; a different l₇, l_P2 or l₂)
    is undecided by the three searches with what differs; a model without its fields is not judged by them."""
    from adroit.parameter_space import resonances
    from adroit.parameter_space.portals import generic_2hdma
    x = _two_hdma_at(300.0, 900.0, MXd=160.0, sinp=0.5, tanbeta=2.0, lam3=2.0, laP1=1.0, laP2=4.0, mh2=950.0,
                     mhc=920.0)
    base = generic_2hdma.spec(x)

    def altered(name, value):
        return GenericModel.for_spec(base.model_copy(update={"couplings": [
            c.model_copy(update={"value": value(c.value)}) if c.name == name else c for c in base.couplings]}))
    for engine, said in ((altered("xi_d", lambda v: 0.5), "not type II"), (altered("c_l7", lambda v: 1.2 * v), "H H⁺H⁻"),
                         (altered("c_lP2", lambda v: 1.5 * v), "SSSS"), (altered("c_l2", lambda v: 1.3 * v), "SSSS")):
        for evaluate in (searches.two_hdma, resonances.monoh, resonances.monoz):
            outcome = evaluate(engine, engine.point(), True)
            assert outcome.excluded is None and said in outcome.why
    inert = _inert_at(990.0, 992.36, 998.12, -0.051)
    assert all(evaluate(inert, inert.point(), True) is None
               for evaluate in (searches.two_hdma, resonances.monoh, resonances.monoz))


@needs_ufo_reader
@pytest.mark.parametrize("multiplier", [0.0, -1.0])
def test_a_missing_or_reversed_quartic_is_not_the_2hdma(multiplier):
    """The tactical audit's T20-05: with λ_P1 = λ_P2 = 0 the comparison had visited only the generic model's own
    vertices, in magnitude, so |H₂|⁴'s coupling set to zero or reversed still matched. Every vertex either model has
    is compared now, and a rephasing-invariant one (H⁺H⁺H⁻H⁻) with its sign."""
    from adroit.parameter_space.portals import generic_2hdma as g
    from adroit.parameter_space.portals.generic import GenericModel
    x = dict(MXd=10., mh1=125.09, mh2=900., mh3=900., mh4=300., mhc=900., sinp=.35, tanbeta=1., sinbma=1., gPXd=1.,
             lam3=3., laP1=0., laP2=0.)
    spec = g.spec(x)
    engine = GenericModel.for_spec(spec)
    assert not isinstance(g.match(engine, engine.point()), str)                   # the 2HDM+a itself still matches
    changed = spec.model_copy(update={"couplings": [c.model_copy(update={"value": c.value * multiplier})
                                                    if c.name == "c_l2" else c for c in spec.couplings]})
    engine = GenericModel.for_spec(changed)
    found = g.match(engine, engine.point())
    assert isinstance(found, str) and "differs: SSSS" in found


@needs_ufo_reader
@pytest.mark.parametrize("change", [{"mh2": 900.0, "mh3": 900.0, "mhc": 900.0},
                                    {"mh2": 900.0, "mh3": 900.0, "mhc": 900.0, "mh4": 900.0},
                                    {"mh2": 900.0, "mh3": 900.0, "mhc": 900.0, "mh4": 900.0, "sinp": 0.35}])
def test_an_exactly_degenerate_2hdma_is_matched_and_its_cancelling_quartics_are_zero(change):
    """The recheck's RB20-05 (2026-10-20), its control: at H = A = H± = 900 GeV (and with a at 900 too, at zero and at
    sin θ = 0.35 mixing) l4 = (2m_A² + m_h² + m_H² − 4m_H±² + Δc₂)/2v² is analytically zero at alignment, but came out
    −1.9 × 10⁻¹⁵, which the generic route's resolution refused as a feeble coupling. From the mass differences
    (``generic_2hdma.higgs_basis``) it is exactly zero and the true model is matched."""
    from adroit.parameter_space.portals import generic_2hdma as g
    from adroit.model_building.gauge_basis import V_EW
    x = {**dict(MXd=10., mh1=125.09, mh2=950., mh3=900., mh4=300., mhc=920., sinp=0., tanbeta=1., sinbma=1., gPXd=1.,
                lam3=3., laP1=0., laP2=0.), **change}
    assert g.higgs_basis(x, V_EW)["l4"] == 0.0
    engine = GenericModel.for_spec(g.spec(x))
    found = g.match(engine, engine.point())
    assert not isinstance(found, str), found


@pytest.mark.parametrize("m_a", [1e-3, 5e-4, 1e-4, 1e-5])
def test_a_light_singlet_keeps_its_mass_through_the_higgs_basis(m_a):
    """The auditor's RC20-03 (2026-10-20), its control: at alignment, no mixing, H = A = H± = 900 GeV, tan β = 1, λ₃ = 3,
    λ_P1 = λ_P2 = 0, the singlet requested at 1, 0.5, 0.1 and 0.01 MeV: m_P² is that mass squared (the cancelling
    form had made it zero below 1 MeV), and the generated spectrum has the singlet at it."""
    from adroit.model_building.gauge_basis import V_EW
    from adroit.parameter_space.portals import generic_2hdma as g
    x = dict(MXd=10., mh1=125.09, mh2=900., mh3=900., mh4=m_a, mhc=900., sinp=0., tanbeta=1., sinbma=1., gPXd=1.,
             lam3=3., laP1=0., laP2=0.)
    assert g.higgs_basis(x, V_EW)["mP2"] == pytest.approx(m_a ** 2, rel=1e-12)
    engine = GenericModel.for_spec(g.spec(x))
    (singlet,) = [s for s in engine.at(engine.point())[0].spectrum.states if s.name.startswith("P")]
    assert singlet.mass_gev == pytest.approx(m_a, rel=1e-9)


def test_a_supplied_feeble_coupling_is_still_refused_with_its_own_reason():
    """A dark-matter coupling the user sets below the generic route's resolution is refused, and the match says so
    rather than misreading the empty portrait as wrong CP content."""
    from adroit.parameter_space.portals import generic_2hdma as g
    x = dict(MXd=10., mh1=125.09, mh2=950., mh3=900., mh4=300., mhc=920., sinp=0.35, tanbeta=1., sinbma=1.,
             gPXd=1e-12, lam3=3., laP1=0., laP2=0.)
    engine = GenericModel.for_spec(g.spec(x))
    found = g.match(engine, engine.point())
    assert isinstance(found, str) and found.startswith("the generic route refuses it: a coupling below")


@needs_ufo_reader
@pytest.mark.parametrize("change, expected", [
    ({}, {"sinp": 0.0, "tanbeta": 1.0, "mh3": 900.0, "mh4": 300.0}),
    ({"tanbeta": 5.0}, {"sinp": 0.0, "tanbeta": 5.0, "mh3": 900.0, "mh4": 300.0}),
    ({"sinp": 1.0}, {"sinp": 0.0, "tanbeta": 1.0, "mh3": 300.0, "mh4": 900.0}),        # relabelled by doublet content
    ({"mh4": 900.0, "sinp": 0.35}, {"sinp": 0.0, "tanbeta": 1.0, "mh3": 900.0, "mh4": 900.0}),  # degenerate: θ moot
])
def test_the_unmixed_and_degenerate_2hdma_is_still_the_2hdma(change, expected):
    """The batch audit's B20-10: at sin θ = 0 the singlet has no Standard Model coupling, so its CP label came out
    empty and the true model was refused. A state with no SM coupling takes its CP from its coupling to the dark
    matter, and the pure singlet is not held to the type-II pattern."""
    from adroit.parameter_space.portals import generic_2hdma as g
    x = {**dict(MXd=10., mh1=125.09, mh2=950., mh3=900., mh4=300., mhc=920., sinp=0., tanbeta=1., sinbma=1., gPXd=1.,
                lam3=3., laP1=0., laP2=0.), **change}
    engine = GenericModel.for_spec(g.spec(x))
    found = g.match(engine, engine.point())
    assert not isinstance(found, str), found
    assert {k: found.values[k] for k in expected} == pytest.approx(expected, abs=1e-6)


@needs_ufo_reader
def test_a_2hdma_declaring_the_card_is_type_ii_in_its_declared_inputs():
    """The owner's decision #2, requirement 3: with the DMsimp card declared, H₂'s stated Yukawas carry b 4.7 and c 1.27
    while h's own are "sm" (3.007, 0.776); the type-II check takes them against h's in the declared inputs, so the model
    is still the 2HDM+a at the same tan β, and is not misread as another Yukawa type."""
    from adroit.parameter_space.portals import generic_2hdma as g
    x = dict(MXd=10., mh1=125.09, mh2=950., mh3=900., mh4=300., mhc=920., sinp=.35, tanbeta=2., sinbma=1., gPXd=1.,
             lam3=3., laP1=0., laP2=0.)
    plain = GenericModel.for_spec(g.spec(x))
    card = GenericModel.for_spec(g.spec(x).model_copy(update={"yukawa": "DMsimp_s_spin0_MD"}))
    read = [g.match(e, e.point()) for e in (plain, card)]
    assert not any(isinstance(r, str) for r in read), read
    assert read[1].values["tanbeta"] == pytest.approx(read[0].values["tanbeta"], rel=1e-6) == pytest.approx(2.0)

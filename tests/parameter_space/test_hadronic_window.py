"""The hadronic window (the owner's decision, 2026-10-20; ``constraints.hadronic_window``): a free-quark rate is not
computed where the energy entering (√s ≈ 2m_χ for an annihilation, the mass for a decay) lies between the hadronic
opening and 2 GeV for a pure vector current, 3 GeV inclusive for any other; what depends on it is decided only where
it does not depend on it."""
import math

import pytest

from adroit.constraints import hadronic_window as hw
from adroit.core.model_spec import ModelSpec
from adroit.parameter_space import library, searches
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals import generic_portrait as gp
from adroit.parameter_space.portals.generic import GenericModel
from tests.parameter_space.test_generic_portrait import _dark_photon
from tests.parameter_space.test_yukawa_convention import CARD, _spec

ALP = library.entry("alp_portal").model_class
ALP_0 = Point(m_chi=1.0, m_med=1.0782138807000883, g_chi=0.5, g_q=1.0, g_l=1.0)      # R3's alp_portal#0
ALP_1 = Point(m_chi=1.0770500691071183, m_med=2.6826957952797255, g_chi=0.5, g_q=1.0, g_l=1.0)   # alp_portal#1


def test_the_window_is_on_the_energy_its_current_and_its_edges():
    """2m_π (3m_π for a CP-odd current) to 2 GeV for a vector current and to 3 GeV for any other, both tops
    inclusive; an annihilation from 0.9 × the opening (its thermal tail)."""
    assert hw.state(2.0, vector=True) == hw.UNKNOWN and hw.state(2.0 + 1e-9, vector=True) == hw.PARTONIC
    assert hw.state(3.0) == hw.UNKNOWN and hw.state(3.0 + 1e-9) == hw.PARTONIC
    assert hw.state(0.4, cp_odd=True) == hw.CLOSED and hw.state(0.42, cp_odd=True) == hw.UNKNOWN
    assert hw.state(0.27) == hw.CLOSED and hw.state(0.26, annihilation=True) == hw.UNKNOWN
    assert hw.state(0.25, annihilation=True) == hw.CLOSED
    assert hw.propagator_insensitive(1e4, 1.0, 1.0) and not hw.propagator_insensitive(4.0, 1.0, 1.0)
    assert not hw.propagator_insensitive(0.5, 1.0, 1e-9)                       # below m²: the resonance is reached
    assert hw.propagator_insensitive(0.5, 1.0, 1e-9, fixed=True)


@pytest.mark.needs("f_eff")
def test_the_library_alps_two_crossings_lose_their_relic_but_keep_an_independent_exclusion():
    """alp_portal#0 (m_χ = 1 GeV exactly, √s = 2 GeV: the window includes its top) and #1 (√s ≈ 2.154 GeV): Ωh² is
    not computed. #0's CMB exclusion stands on its leptonic channels alone, at the a's largest hadronic width; #1's
    needs Γ_had near 0, so it is undecided."""
    for p in (ALP_0, ALP_1):
        assert "the annihilation into hadrons" in ALP.domain(p) and ALP.omega_h2(p) is None
        assert set(ALP.sigma_v_today(p, 1e-3)) == {"e", "mu", "tau", "SS"}           # the quark pairs not computed
    cmb_0, cmb_1 = searches.cmb(ALP, ALP_0, False), searches.cmb(ALP, ALP_1, False)
    assert cmb_0.excluded is True and "excluded by the channels computed alone" in cmb_0.flags[0]
    assert cmb_1.excluded is None and "no upper bound" in cmb_1.why
    edge = ALP_1.model_copy(update={"m_chi": 1.5, "m_med": 5.0})            # the a above its window: 2m_χ alone
    above = edge.model_copy(update={"m_chi": 1.5 + 1e-6})
    assert "the annihilation into hadrons" in ALP.domain(edge) and not ALP.domain(above)
    assert ALP.omega_h2(above) > 0
    assert "moves the s-channel propagator" in ALP.domain(above.model_copy(update={"m_med": 2.68}))


def test_the_library_scalars_quark_channels_close_below_the_opening_and_its_width_is_bounded_in_the_window():
    """Below 3m_π a CP-odd a has no hadronic decay (μμ, ee only); in the window its width is 0 ≤ Γ_had ≤ m_a above
    the leptons' and ``width`` refuses; B → K a is decided only where both ends agree."""
    below = Point(m_chi=50.0, m_med=0.4, g_chi=0.5, g_q=1.0, g_l=1.0)
    widths, unknown = ALP._widths(below)
    assert set(widths) == {"e", "mu"} and unknown == ""
    inside = below.model_copy(update={"m_med": 1.0})
    low, high, unknown = ALP.width_bounds(inside)
    assert high == pytest.approx(low + 1.0) and "hadronic window" in unknown
    with pytest.raises(hw.HadronicUnknown):
        ALP.width(inside)
    s = (2 * 0.2) ** 2 * 1.0001
    import numpy as np
    sigma = ALP._sigma(np.array([s]), below.model_copy(update={"m_chi": 0.2, "m_med": 5.0}))
    assert all(sigma[q][0] == 0.0 for q in ("u", "d", "s")) and sigma["mu"][0] > 0     # √s < 3m_π: no hadrons
    invisible = Point(m_chi=0.3, m_med=1.0, g_chi=0.5, g_q=1.0, g_l=1.0)
    outcome = searches._flavour_native(ALP, invisible, True)
    assert outcome.excluded is None or "decided alike" in " ".join(outcome.flags)


def test_the_generic_route_refuses_the_same_alp_and_classifies_the_current():
    """The ALP's spec through the generic route at R3's two crossings (3 GeV: a pseudoscalar current); a pure dark
    photon's vector current is computed from 2 GeV (m_χ = 1.2 GeV) and refused at m_χ = 0.9 GeV; with an axial part
    it is not vector, and 3 GeV applies."""
    for p in (ALP_0, ALP_1):
        spec = _spec(CARD, p.m_med, True, m_chi=p.m_chi)
        engine = GenericModel.for_spec(spec)
        assert "the annihilation into hadrons" in engine.domain(engine.point())
    vector, q = _dark_photon(1.2, 3.6, 0.5, 1e-3)
    assert "hadronic" not in vector.domain(q)
    assert "the annihilation into hadrons" in vector.domain(q.model_copy(update={"m_chi": 0.9}))
    mb, rules, model = vector.at(q)
    from adroit.parameter_space.portals import generic_hadronic as gh
    assert gh.annihilation_vector(rules, *gh.bath_pairs(mb, rules)[0])
    axial = _axial_dark_photon(1.2, 3.6)
    assert "the annihilation into hadrons" in axial.domain(axial.point())


def _axial_dark_photon(m_chi: float, m_med: float) -> GenericModel:
    """A vector coupled axially to the dark matter and vectorially and axially to the quarks: not a vector current."""
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": m_chi},
              {"name": "Ap", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": m_med},
              {"name": "q", "role": "standard_model", "spin": 0.5}]
    terms = [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Ap"}], "lorentz": "vector",
              "coupling": "0.5"},
             {"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "Ap"}], "lorentz": "axial",
              "coupling": "0.01"}]
    spec = ModelSpec.model_validate({"name": "axial", "phase": "broken", "fields": fields, "terms": terms})
    return GenericModel.for_spec(spec)


def test_a_generic_mediator_in_its_window_has_its_width_and_branchings_as_bounds():
    """The ALP's a at 2 GeV through the generic route: no quark pair computed, 0 ≤ Γ_had ≤ m_a, the share of Standard
    Model pairs refused as one number and BR(invisible) a range; at 3.2 GeV the quarks are free again."""
    spec = _spec(CARD, 2.0, True, m_chi=0.3)
    engine = GenericModel.for_spec(spec)
    (a,) = [m for m in gp.portraits(engine, engine.point()) if m.spin == 0]
    assert a.hadronic_bound_gev == 2.0 and not any(set(c.final) & {"s", "s~"} for c in a.channels)
    with pytest.raises(hw.HadronicUnknown):
        a.visible_share()
    low, high = a.invisible_bounds()
    assert low < high and "hadronic window" in a.unresolved_reason()
    heavier = GenericModel.for_spec(_spec(CARD, 3.2, True, m_chi=0.3))
    (b,) = [m for m in gp.portraits(heavier, heavier.point()) if m.spin == 0]
    assert b.hadronic_reason == "" and any(c.final == ("s", "s~") for c in b.channels)


def test_the_librarys_spin1_z_and_t_channel_classes_refuse_their_window_too():
    """The same policy on the library's other free-quark calculations: DMWG's vector mediator (a pure vector current,
    to 2 GeV) and axial one (to 3 GeV) at R3's dmwg_V1#0 and dmwg_A1#0 (m_χ = 1 GeV), the Z portal (vector and axial
    couplings: to 3 GeV) and a quark partner's t-channel exchange (unclassified: to 3 GeV); their exclusions by other
    searches are untouched, and annihilation today into quarks is not computed there (the CMB from the rest alone)."""
    v1, a1 = (library.entry(e).model_class for e in ("dmwg_V1", "dmwg_A1"))
    p = Point(m_chi=1.0, m_med=69.2, g_chi=1.0, g_q=0.25, g_l=0.0)
    assert "the annihilation into hadrons" in v1.domain(p) and v1.omega_h2(p) is None
    assert not v1.domain(p.model_copy(update={"m_chi": 1.08})) and v1.omega_h2(p.model_copy(update={"m_chi": 1.08}))
    assert "the annihilation into hadrons" in a1.domain(p.model_copy(update={"m_chi": 1.4}))
    assert not a1.domain(p.model_copy(update={"m_chi": 1.6}))
    assert "the annihilation into hadrons" in v1.today_hadronic(p)
    cmb = searches.cmb(v1, p, False)
    assert cmb.excluded is None or "excluded by the channels computed alone" in " ".join(cmb.flags)
    z = library.entry("z_portal_vector").model_class
    assert "the annihilation into hadrons" in z.domain(Point(m_chi=1.4, m_med=91.19, g_chi=1.0, g_q=0.25))
    assert not z.domain(Point(m_chi=1.6, m_med=91.19, g_chi=1.0, g_q=0.25))
    t = library.entry("tchannel_uR_dirac").model_class
    assert "the annihilation into hadrons" in t.domain(Point(m_chi=1.2, m_med=1500.0, g_chi=1.0, g_q=1.0))
    assert "hadronic" not in t.domain(Point(m_chi=10.0, m_med=1500.0, g_chi=1.0, g_q=1.0))


def test_a_spin1_mediator_in_its_window_refuses_the_relic_where_its_width_matters():
    """An axial mediator at 2 GeV: its hadronic width (0 to m) moves the propagator for m_χ = 1.6 GeV (s just above
    m²), not for m_χ = 20 GeV."""
    a1 = library.entry("dmwg_A1").model_class
    near = Point(m_chi=1.6, m_med=2.0, g_chi=1.0, g_q=0.25, g_l=0.0)
    assert "moves the s-channel propagator" in a1.domain(near) and a1.today_unknown(near)
    far = near.model_copy(update={"m_chi": 20.0})
    assert not a1.domain(far) and a1.omega_h2(far) > 0


# --- the candidate audit's C21-01 to C21-03 (2026-10-21) ------------------------------------------------------------

def _flavour(couplings: dict[str, float]):
    from adroit.core.model_contracts import VECTOR_FLAVOURS
    from adroit.parameter_space.flavour_vector import FlavourVectorClass
    return FlavourVectorClass(flavour_couplings={n: couplings.get(n, 0.0) for n in VECTOR_FLAVOURS})


def test_a_named_flavour_current_is_refused_in_its_window_as_the_universal_one_is():
    """C21-01: the flavour-vector class keeps g_q = 0 and its quark current in its named couplings; the window reads
    the model's couplings. g_u = 1 at m_χ = 0.8 GeV (√s = 1.6 GeV, a vector current's window): no Ωh², no quark rate
    today. With every quark at 0.25 it is the universal vector mediator, refused and computed exactly as Spin1Class,
    the mediator's width in its window included."""
    from adroit.parameter_space.classes import Spin1Class
    u_only = _flavour({"u": 1.0})
    p = Point(m_chi=0.8, m_med=10.0, g_chi=0.5, g_q=0.0, g_l=0.0)
    assert "the annihilation into hadrons" in u_only.domain(p) and u_only.omega_h2(p) is None
    assert "the annihilation into hadrons" in searches.today_unknown(u_only, p)
    assert not {"u", "d", "s"} & set(u_only.sigma_v_today(p, 1e-3))
    universal, plain = _flavour({q: 0.25 for q in "udscbt"}), Spin1Class()
    for m_chi, m_med in ((0.8, 10.0), (1.08, 10.0), (1.2, 2.0), (20.0, 2.0)):
        q = p.model_copy(update={"m_chi": m_chi, "m_med": m_med})
        r = q.model_copy(update={"g_q": 0.25})
        assert universal.domain(q) == plain.domain(r)
        assert universal.omega_h2(q) == plain.omega_h2(r)
    assert "moves the s-channel propagator" in universal.domain(p.model_copy(update={"m_chi": 1.2, "m_med": 2.0}))


def test_closed_quark_channels_are_zero_in_every_spin1_consumer():
    """C21-02, the library: below the opening (√s ≈ 0.2 GeV < 2m_π) the vector and axial mediators' quark pairs are
    zero today (the scalar's already were), the leptons unchanged; a mediator below 2m_π has no quark width."""
    from adroit.constraints import spin1
    for name in ("dmwg_V1", "dmwg_A1"):
        cls = library.entry(name).model_class
        p = Point(m_chi=0.1, m_med=10.0, g_chi=0.5, g_q=0.1, g_l=0.1)
        rates = cls.sigma_v_today(p, 1e-3)
        assert all(rates[q] == 0.0 for q in "udscbt") and rates["e"] > 0
        # unchanged but for the quarks' share of the mediator's width in its propagator (7 × 10⁻⁵ here)
        assert rates["e"] == pytest.approx(cls.sigma_v_today(p.model_copy(update={"g_q": 0.0}), 1e-3)["e"], rel=2e-4)
    light = spin1.Spin1Model(kind=spin1.Spin1Kind.vector, m_med_gev=0.25, g_dm=0.5, g_q=0.1, g_l=0.1)
    leptons = light.model_copy(update={"g_q": 0.0})
    assert spin1.width(light, 1.0) == spin1.width(leptons, 1.0)


def test_the_dm7_verdicts_refuse_the_window_too():
    """C21-02's propagation to the anomaly workflow's complementary verdicts (DM7): a spin-1 completion at m_χ = 1 GeV
    (√s = 2 GeV, the vector window's top) has no Ωh² and no dwarf comparison; at 1.08 GeV both are computed."""
    from adroit.constraints import database, spin1, verdicts
    from adroit.core.dm_state import Applicability, DarkMatterParticle

    def candidate(m_dm: float) -> verdicts.Candidate:
        completion = spin1.benchmark("V1", 69.2)
        return verdicts.Candidate(label="V1", particle=DarkMatterParticle(mass_gev=m_dm),
                                  interaction=spin1.interaction(completion, m_dm), completion=completion)
    for record in ("planck-2018-omega", "fermi-1503.02641-dsph"):
        inside = verdicts.verdict(candidate(1.0), database.record(record))
        assert inside.applicability is Applicability.needs_calculation and inside.excluded is None
        assert "hadronic window" in inside.needed_calculation
    assert "Ωh² = " in verdicts.relic(candidate(1.08), database.record("planck-2018-omega")).note


def test_the_generic_routes_closed_partons_are_zero_today_and_in_cascades():
    """C21-02, the generic route: its dark photon at m_χ = 0.1 GeV has no quark rate today (its Ωh² tables had none);
    a CP-odd scalar at 0.4 GeV (below 3m_π) has no quark decay in its cascades, as in its portrait, and none in the
    kinetic-contact rate."""
    from adroit.parameter_space.portals import generic_checks as gc, generic_id as gi
    engine, p = _dark_photon(0.1, 10.0, 0.5, 0.01)
    rates = engine.sigma_v_today(p, 1e-3)
    assert set(rates) == {"e"} and rates["e"] > 0
    engine = GenericModel.for_spec(_spec(CARD, 0.4, True, m_chi=10.0))
    p = engine.point()
    mb, rules, _ = engine.at(p)
    (s,) = [m for m in gp.portraits(engine, p) if m.spin == 0]
    assert s.width_gev == 0.0 and not s.channels
    assert gi.decays(rules, s.name, gi.dark_pair(mb)) is None
    assert gc._decays(rules, s.name, {"u", "u~", "d", "d~", "s", "s~"}) == 0.0
    heavier = GenericModel.for_spec(_spec(CARD, 3.2, True, m_chi=10.0))
    mb, rules, _ = heavier.at(heavier.point())
    assert gc._decays(rules, "S0", {"s", "s~"}) > 0                       # above the window: free quarks again


def _two_vectors(quark: tuple[float, float], axial: float = 0.0, scalar: float = 0.0) -> GenericModel:
    """Dirac dark matter at 1.25 GeV and two vectors at 10 GeV (dark couplings 0.5), with quark vector couplings
    ``quark``, an axial coupling ``axial`` to the first (the audit's C21-03 model) and, if ``scalar``, a scalar at
    10 GeV coupled pseudoscalarly to the dark matter (0.5) and scalarly to the quarks (the recheck's RC21-02)."""
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 1.25},
              {"name": "q", "role": "standard_model", "spin": 0.5}]
    fields += [{"name": n, "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 10.0} for n in ("V1", "V2")]
    terms = []
    for v, g in zip(("V1", "V2"), quark):
        terms.append({"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": v}],
                      "coupling": "0.5", "lorentz": "vector"})
        terms.append({"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": v}],
                      "coupling": str(g), "lorentz": "vector"})
    if axial:
        terms.append({"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "V1"}],
                      "coupling": str(axial), "lorentz": "axial"})
    if scalar:
        fields.append({"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 10.0})
        terms.append({"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "S"}],
                      "coupling": "0.5", "lorentz": "pseudoscalar"})
        terms.append({"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "S"}],
                      "coupling": str(scalar), "lorentz": "scalar"})
    return GenericModel.for_spec(ModelSpec.model_validate({"name": "two vectors", "phase": "broken",
                                                           "fields": fields, "terms": terms}))


def test_cancelling_vector_currents_do_not_hide_an_axial_one():
    """C21-03: vector quark couplings +0.01 and −0.01 through equal vectors cancel, leaving the 10⁻⁶ axial coupling the
    whole rate (√s = 2.5 GeV, between 2 and 3 GeV): not a vector current, refused. The same couplings adding (+0.01,
    +0.01) and nothing else are a vector current, computed; with the 10⁻⁶ axial coupling beside them, mixed, refused
    (RC21-02)."""
    from adroit.parameter_space.portals import generic_hadronic as gh
    for quark, axial, vector in (((0.01, -0.01), 1e-6, False), ((0.01, 0.01), 0.0, True), ((0.01, 0.01), 1e-6, False)):
        engine = _two_vectors(quark, axial)
        mb, rules, _ = engine.at(engine.point())
        assert gh.annihilation_vector(rules, *gh.bath_pairs(mb, rules)[0]) is vector
        assert ("the annihilation into hadrons" in engine.domain(engine.point())) is not vector


def test_a_mixed_scalar_and_vector_current_is_not_vector():
    """RC21-02 (the recheck, 2026-10-22): vectors with vector quark couplings 0.01 beside a scalar with scalar quark
    couplings 10⁻⁶ at √s = 2.5 GeV. The coefficient ratio had passed such a current as vector, though in the
    recheck's model (axially coupled dark matter, its vector part p-wave) the scalar carried 98.7% of the rate today
    at v = 2·10⁻⁵; mixed, it is refused, with no quark rate today."""
    from adroit.parameter_space.portals import generic_hadronic as gh
    engine = _two_vectors((0.01, 0.01), scalar=1e-6)
    mb, rules, _ = engine.at(engine.point())
    assert not gh.annihilation_vector(rules, *gh.bath_pairs(mb, rules)[0])
    p = engine.point()
    assert "the annihilation into hadrons" in engine.domain(p) and engine.today_hadronic(p)
    assert not {"u", "d", "s"} & set(engine.sigma_v_today(p, 2e-5))


def test_every_portals_quarks_are_closed_below_the_opening():
    """RC21-01 (the recheck, 2026-10-22): below the opening (√s ≈ 0.2 GeV < 2m_π) the Z portal's and the t-channel
    partner's quark rates today were free quarks; the portals' common rates (``base.close_partons``, used by
    ``total`` and ``sigma_v_today``, and the t-channel's own bath) now close them, the leptons unchanged."""
    from adroit.parameter_space.portals.base import close_partons
    from adroit.parameter_space.portals.tchannel import TChannel
    from adroit.parameter_space.portals.vector import ZPortal
    p = Point(m_chi=0.1, m_med=100.0, g_chi=0.5, g_q=0.1)
    for cls in (ZPortal(), ZPortal(coupling="axial"), TChannel(partner="uR", sommerfeld=False, bound_states=False),
                TChannel(partner="dR", majorana=True, sommerfeld=False, bound_states=False)):
        rates = cls.sigma_v_today(p, 1e-3)
        assert all(rates[q] == 0.0 for q in "udscbt" if q in rates) and set("udscbt") & set(rates)
    assert ZPortal().sigma_v_today(p, 1e-3)["e"] > 0
    closed = close_partons([0.2 ** 2, 0.3 ** 2], {"u": [1.0, 1.0], "g g": [1.0, 1.0], "hadrons": [1.0, 1.0],
                                                  "e": [1.0, 1.0]})
    assert list(closed["u"]) == [0.0, 1.0] and list(closed["g g"]) == [0.0, 1.0]
    assert list(closed["hadrons"]) == [1.0, 1.0] and list(closed["e"]) == [1.0, 1.0]


@pytest.mark.needs("pdg_r_ratio")
def test_the_dark_photons_invisible_fraction_is_its_own_widths():
    """RC21-06 (the recheck, 2026-10-22): DarkCast's invisible comparison read BR(A′ → χχ̄) with the Standard Model's
    part summed over free quarks (0.26 at m_A′ = 0.1 GeV, m_χ = 25 MeV, g_D = 3·10⁻⁴, ε = 10⁻³), not the model's own
    width (0.49); it now reads the dark partial width over the A′'s own total width."""
    from adroit.parameter_space.portals.vector import DarkPhoton, _width
    cls, p = DarkPhoton(), Point(m_chi=0.025, m_med=0.1, g_chi=3e-4, g_q=1e-3)
    meds, dark, fermions = cls.bosons(p)
    to_dm = _width(meds[1].mass, {f: (0.0, 0.0) for f in fermions}, dark[1], p.m_chi, cls._dm())
    assert searches._dark_photon_branching(cls, p) == pytest.approx(to_dm / meds[1].width, rel=1e-12)
    assert searches._dark_photon_branching(cls, p) == pytest.approx(0.48881, rel=1e-4)
    assert searches._dark_photon_branching(cls, p.model_copy(update={"m_chi": 0.06})) == 0.0     # 2m_χ > m_A′


def test_a_light_coloured_bath_is_refused():
    """The re-audit's RR22-01 (2026-10-22): with χχ closed below 2m_π, a quark partner at 0.16 GeV still sent its χφ
    and φφ* free-parton rates (19.96 GeV⁻² at √s = 0.32 GeV) to the relic solver. A coloured partner whose pairs
    start at or below 3 GeV (m_χ + m_φ) is refused, confined states not being free partons; above it, unchanged."""
    from adroit.parameter_space.portals.tchannel import TChannel
    cls = TChannel(partner="uR", majorana=True, sommerfeld=False, bound_states=False)
    for m_med in (0.16, 2.89):
        p = Point(m_chi=0.1, m_med=m_med, g_chi=0.2)
        assert "coloured partner's pairs in the bath" in cls.domain(p) and cls.omega_h2(p) is None
    assert "coloured" not in cls.domain(Point(m_chi=0.1, m_med=2.91, g_chi=0.2))


@pytest.mark.needs("ufo_models")
def test_the_ufo_table_closes_partons_between_its_nodes():
    """RR22-02: the UFO portal tabulated the sum of its channels and closed the partons only at its nodes, so a bin
    straddling 2m_π interpolated them back (2.8% at 0.279139 GeV for the inert doublet's H₀H₀). Partons and the rest
    are tabulated apart and the partons closed at every √s: below the opening the total is the non-partonic table."""
    import numpy as np
    from unittest.mock import patch
    from adroit.parameter_space.library import INERT_DOUBLET
    from adroit.parameter_space.portals.ufo import _SIGMA, UFOPortal
    cls, p = INERT_DOUBLET, Point(m_chi=0.1, m_med=100.0, g_chi=0.1, g_q=100.0)
    a = cls.dm
    b = cls.model(p).particles[a].conjugate
    _SIGMA.clear()
    total = cls._sigma(p, a, b)
    finals = UFOPortal._finals

    def without_partons(self, model, x, y, top):
        return [(c, d) for c, d in finals(self, model, x, y, top)
                if not any(abs(model.particles[n].pdg) in (1, 2, 3, 4, 5, 6, 21) for n in (c, d))]
    with patch.object(UFOPortal, "_finals", without_partons):
        _SIGMA.clear()
        reference = cls._sigma(p, a, b)
    _SIGMA.clear()
    for root in (0.278, 0.279139):
        assert float(total(np.array([root ** 2]))[0]) == pytest.approx(float(reference(np.array([root ** 2]))[0]),
                                                                       rel=1e-12)


@pytest.mark.needs("pdg_r_ratio")
def test_the_lmu_ltau_invisible_fraction_is_its_own_widths():
    """RR22-05: L_μ − L_τ's invisible fraction was one minus its visible fermions' free-quark widths over a total whose
    hadrons are the R ratio's (0.51918 against 0.51877 at 1.019 GeV); it is now the dark matter's and the neutrinos'
    partial widths over the Z′'s own total, below the R ratio's start, at the φ and above."""
    from adroit.constraints import spin1
    from adroit.parameter_space.portals.vector import _width
    cls = library.entry("lmu_minus_ltau").model_class
    for m in (0.1, 0.25, 0.77, 1.019, 1.5):
        p = Point(m_chi=m / 4, m_med=m, g_chi=3e-4, g_q=1e-3)
        couplings = cls.fermions(p)
        own = (_width(m, {f.name: (0.0, 0.0) for f in spin1.FERMIONS}, (p.g_chi, 0.0), p.m_chi, "fermion")
               + sum(spin1.partial_width(m, f.mass_gev, f.colours, *couplings[f.name]) for f in spin1.FERMIONS
                     if f.family == "neutrino")) / cls.mediator(p).width
        assert searches._lmu_numbers(cls, p)[3] == pytest.approx(own, rel=1e-12)


@pytest.mark.needs("pdg_r_ratio")
@pytest.mark.parametrize("m_med", [0.01, 0.02, 0.03, 0.04])
def test_the_lmu_ltau_neff_share_is_its_own_dark_width_below_the_opening(m_med):
    """The RV22 audit's RX22-06: N_eff read the dark share as one minus every free fermion's width over the Z′'s own
    total, so its loop-induced u, d widths counted at 10–40 MeV, where its hadrons are closed: a true 1.0001% share
    read 0.997% and decided (excluded at 10 MeV, allowed at 20–40 MeV) where its own 1% rule leaves it pending."""
    from adroit.constraints import spin1
    cls = library.entry("lmu_minus_ltau").model_class
    p = Point(m_chi=m_med / 4, m_med=m_med, g_chi=0.0, g_q=1e-3)
    want, unit = 0.010001, spin1.partial_width(m_med, p.m_chi, 1, 1.0, 0.0)
    p = p.model_copy(update={"g_chi": math.sqrt(want / (1 - want) * cls.mediator(p).width / unit)})
    assert searches._lmu_dark_width(p) / cls.mediator(p).width == pytest.approx(want, rel=1e-9)
    found = searches.neff(cls, p, True)
    assert found.excluded is None and "decays to the dark matter" in found.why


def _coloured_bath(majorana: bool, m_chi: float, m_phi: float) -> GenericModel:
    """Dark matter χ and an odd colour-triplet scalar Φ coupled to u_R (y = 0.2), unbroken phase, perturbative (the
    re-audit's RV22-01 model)."""
    fields = [{"name": "chi", "role": "dark_matter", "spin": .5, "self_conjugate": majorana, "dark_parity": -1,
               "mass_gev": m_chi},
              {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": m_phi,
               "charges": {"su3": "3", "hypercharge": 2 / 3}},
              {"name": "uR", "role": "standard_model", "spin": .5, "chirality": "R",
               "charges": {"su3": "3", "hypercharge": 2 / 3}}]
    terms = [{"fields": [{"field": "Phi", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": "uR"}],
              "lorentz": "chiral", "coupling": "y", "plus_hc": True}]
    spec = ModelSpec.model_validate({"name": "coloured bath", "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "y", "value": .2}]})
    return GenericModel.for_spec(spec, sommerfeld=False, bound_states=False)


def test_the_generic_routes_light_coloured_bath_is_refused():
    """RV22-01 (2026-10-22): the generic route computed Ωh² = 0.0023 for a colour-triplet partner at 0.12 GeV beside
    Majorana dark matter at 0.1 GeV (its ΦΦ* → γγ as well as its partons); a bath pair with a coloured state at or below
    3 GeV is refused, for Majorana and Dirac dark matter, as the library's t-channel class; above it, not."""
    for majorana in (True, False):
        engine = _coloured_bath(majorana, 0.1, 0.12)
        p = engine.point()
        assert "the coloured state's pair" in engine.domain(p) and engine.omega_h2(p) is None
    heavy = _coloured_bath(True, 2.0, 2.2)
    assert "the coloured state's pair" not in heavy.domain(heavy.point())


def _solver_pairs(mb, rules) -> set[tuple[str, str]]:
    from adroit.parameter_space.portals.generic import bath_states
    names = [name for name, _, _ in bath_states(mb, rules)]
    return {tuple(sorted((a, b))) for i, a in enumerate(names) for b in names[i:]}


@pytest.mark.parametrize("majorana", [True, False])
@pytest.mark.parametrize("delta", [-1e-10, 0.0, 1e-10])
def test_the_hadronic_checks_see_every_pair_the_relic_solver_integrates(majorana, delta):
    """The RV22 audit's RX22-01: the checks' bath stopped strictly below 1.3 m_χ, the solver's includes it, so a
    colour-triplet partner at exactly 1.3 m_χ (0.13 GeV beside 0.1 GeV dark matter) had Ωh² = 0.0043 (Majorana),
    0.012 (Dirac). The checks now read the solver's own species: the same pairs on both sides of the edge and at it."""
    from adroit.parameter_space.portals import generic_hadronic
    from adroit.parameter_space.portals.generic import BATH
    engine = _coloured_bath(majorana, 0.1, BATH * 0.1 + delta)
    p = engine.point()
    mb, rules, _ = engine.at(p)
    guard = {tuple(sorted(pair)) for pair in generic_hadronic.bath_pairs(mb, rules)}
    assert guard == _solver_pairs(mb, rules)
    if delta <= 0.0:
        assert any(name.startswith("Phi") for pair in guard for name in pair)
        why = engine.domain(p)                    # the partner's pair in the window, or its confinement
        assert "Phi" in why and "not computed" in why and engine.omega_h2(p) is None
    else:
        assert not any(name.startswith("Phi") for pair in guard for name in pair)


def test_an_uncoloured_partner_at_the_bath_edge_is_in_both_lists():
    from adroit.parameter_space.portals import generic_hadronic
    from adroit.parameter_space.portals.generic import BATH
    fields = [{"name": "chi", "role": "dark_matter", "spin": .5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 50.0},
              {"name": "Pe", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": BATH * 50.0,
               "charges": {"hypercharge": -1.0}},
              {"name": "eR", "role": "standard_model", "spin": .5, "chirality": "R", "charges": {"hypercharge": -1.0}}]
    terms = [{"fields": [{"field": "Pe", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": "eR"}],
              "lorentz": "chiral", "coupling": "y", "plus_hc": True}]
    spec = ModelSpec.model_validate({"name": "lepton partner", "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "y", "value": .2}]})
    engine = GenericModel.for_spec(spec, sommerfeld=False, bound_states=False)
    mb, rules, _ = engine.at(engine.point())
    guard = {tuple(sorted(pair)) for pair in generic_hadronic.bath_pairs(mb, rules)}
    assert guard == _solver_pairs(mb, rules) and any(name.startswith("Pe") for pair in guard for name in pair)


@pytest.mark.needs("ufo_models")
def test_a_ufo_coannihilating_pair_in_the_window_is_refused():
    """The RV22 audit's RX22-02 (2026-10-22): the UFO portal checked the dark matter's pair alone. The inert doublet at
    M_H0 = 0.12 GeV (its pair closed, below 0.9 × 2m_π), M_A0 = M_H± = 0.16 GeV had Ωh² = 0.057, H⁺H⁻ → uū among its
    rates at 0.32 GeV. Every pair the relic solver integrates is now checked."""
    from adroit.parameter_space.library import INERT_DOUBLET
    p = Point(m_chi=.12, m_med=.16, g_chi=.1, g_q=.04)
    model = INERT_DOUBLET.model(p)
    assert hw.state(2 * p.m_chi, annihilation=True) == hw.CLOSED
    assert len(INERT_DOUBLET._bath(model)) == len(INERT_DOUBLET.coannihilation(p)[0])
    why = INERT_DOUBLET.domain(p)
    assert "hadronic window" in why and "coannihilating" in why and INERT_DOUBLET.omega_h2(p) is None


@pytest.mark.needs("ufo_models")
def test_a_ufo_light_mediator_whose_width_is_free_partons_refuses_the_relic_and_today():
    """RX22-02's second case: the 2HDM+a at m_χ = 1.6 GeV (its pair above 3 GeV) with the pseudoscalar a at 1 GeV,
    whose width the portal computes from free partons; Γ_had up to m moves the χχ̄ propagator by 1.1%, beyond the
    declared 0.1%. Ωh² was 0.0008; now refused, and today's rates are not computed."""
    from adroit.parameter_space.library import TWO_HDM_A
    p = Point(m_chi=1.6, m_med=1.0, g_chi=.5, g_q=.2, g_l=1.0)
    why = TWO_HDM_A.domain(p)
    assert why.startswith("h4's hadronic width at m = 1 GeV") and "propagator of" in why
    assert TWO_HDM_A.omega_h2(p) is None and TWO_HDM_A.today_unknown(p).startswith("h4's hadronic width")


@pytest.mark.needs("ufo_models")
def test_ufo_points_away_from_the_window_are_unchanged():
    from adroit.parameter_space.library import INERT_DOUBLET, TWO_HDM_A
    assert TWO_HDM_A.domain(Point(m_chi=200.0, m_med=400.0, g_chi=1.0, g_q=.35, g_l=1.0)) == ""
    assert TWO_HDM_A.today_unknown(Point(m_chi=200.0, m_med=400.0, g_chi=1.0, g_q=.35, g_l=1.0)) == ""
    assert INERT_DOUBLET.domain(Point(m_chi=60.0, m_med=80.0, g_chi=.01, g_q=10.0)) == ""


def _closed_vector(m_v: float) -> GenericModel:
    """Dirac dark matter at 0.1 GeV and a vector V coupled to a quark-like and a lepton-like fermion (the RX22 audit's
    width control)."""
    fields = [dict(name='chi', role='dark_matter', spin=.5, dark_parity=-1, mass_gev=.1),
              dict(name='q', role='standard_model', spin=.5), dict(name='l', role='standard_model', spin=.5),
              dict(name='V', role='mediator', spin=1, self_conjugate=True, mass_gev=m_v)]
    terms = [dict(fields=[dict(field=f, conjugate=True), dict(field=f), dict(field='V')], coupling=str(g),
                  lorentz='vector') for f, g in [('chi', .5), ('q', .01), ('l', .01)]]
    spec = ModelSpec.model_validate(dict(name='closed width', phase='broken', fields=fields, terms=terms))
    return GenericModel.for_spec(spec, sommerfeld=False, bound_states=False)


def test_a_closed_bosons_propagator_reads_the_width_the_portrait_states():
    """The RX22 audit's RY23-01 (2026-10-23): below 2m_π a 0.2 GeV vector's portrait left out its free u, d widths,
    but the tree model's propagator kept them (3.7 against 0.53 × 10⁻⁶ GeV), and the electron rate today near its
    pole was 49 times too small. The tree model now carries the portrait's width; above the window, the partons
    stay."""
    from dataclasses import replace
    from unittest.mock import patch

    from adroit.parameter_space.portals import generic
    for m_v, closed in ((0.2, True), (5.0, False)):
        engine = _closed_vector(m_v)
        p = engine.point()
        mb, rules, model = engine.at(p)
        v = next(x for x in rules.particles if x.name == 'V')
        portrait = gp._portrait(mb, rules, v, mb.spectrum.dark_matter().name)
        assert (gh_state(rules) == hw.CLOSED) is closed
        if closed:
            assert model.particles['V'].width == pytest.approx(portrait.width_gev, rel=1e-12)
            assert engine.domain(p) == '' and engine.today_unknown(p) == ''
            today = engine.sigma_v_today(p, 1e-4)
            same = model.__class__(dict(model.particles), model.vertices)
            same.particles['V'] = replace(model.particles['V'], width=portrait.width_gev)
            same.parity = model.parity
            generic._today.cache_clear()
            with patch.object(generic, '_built', return_value=(mb, rules, same)):
                assert engine.sigma_v_today(p, 1e-4)['e'] == pytest.approx(today['e'], rel=1e-9)
            generic._today.cache_clear()
        else:
            assert model.particles['V'].width > portrait.width_gev * 0.999      # the quark channels open


def gh_state(rules) -> str:
    from adroit.parameter_space.portals import generic_hadronic
    return generic_hadronic.state(rules, 'V')


@pytest.mark.needs("ufo_models")
@pytest.mark.parametrize("m_a, closed", [(0.2, True), (0.24, True), (5.0, False)])
def test_a_ufo_boson_below_the_opening_has_no_parton_width(m_a, closed):
    """RY23-01's UFO case: the 2HDM+a's a at 0.24 GeV (tan β = 10) kept its free u, d, s widths, three quarters of its
    total, and its muon rate today at the pole was 16.6 times too small. Below 2m_π its width is its leptons'."""
    from adroit.constraints import ufo_model
    from adroit.parameter_space.library import TWO_HDM_A
    p = Point(m_chi=m_a / 2, m_med=m_a, g_chi=.5, g_q=.2, g_l=10.0)
    model = TWO_HDM_A.model(p)
    a = model.particles['h4']
    names = {x.pdg: x.name for x in model.particles.values()}
    part = {k: ufo_model._two_body(model, a, model.particles[names[k]], model.particles[names[-k]])
            for k in (1, 2, 3, 11, 13)}
    leptons = part[11] + part[13]
    assert sum(part[k] for k in (1, 2, 3)) > 0
    if closed:
        assert a.width == pytest.approx(leptons, rel=1e-9)
    else:
        assert a.width > leptons + part[3] * 0.999


def _das_with_light_scalar(m2: float, sine: float, m1: float = 125.0) -> GenericModel:
    """Das et al.'s development-half model with its scalar potential set for eigenmasses 125 GeV and ``m2``, mixing
    sin θ = ``sine`` (the RY23 audit's control; not the paper's benchmark)."""
    import math

    from adroit.evaluation import zoo
    from adroit.model_building.gauge_basis import V_EW
    entry = next(e for e in zoo.entries() if e.id == 'singlet_fermion_scalar_mediator_das')
    base = zoo._spec(entry, entry.targets[0])
    v, co = V_EW, math.sqrt(1 - sine * sine)
    values = {c.name: c.value for c in base.couplings}
    values.update(mu_hs=sine * co * (m2 * m2 - m1 * m1) / v,
                  mu_s2=m1 * m1 * sine * sine + m2 * m2 * co * co - values['lam_hs'] * v * v / 2,
                  lam_H=(m1 * m1 * co * co + m2 * m2 * sine * sine) / (2 * v * v))
    spec = base.model_copy(update={'couplings': [c.model_copy(update={'value': values[c.name]})
                                                 for c in base.couplings]})
    return GenericModel.for_spec(spec)


def test_a_light_mostly_doublet_scalar_keeps_its_open_width_and_is_refused():
    """The RY23 audit's RZ23-03 (2026-10-23): a 0.24 GeV scalar the mixing makes 64% doublet (named h) took the SM
    width table's zero below 2 GeV, its open lepton decays erased, and the Higgs signal strength divided by it. It
    keeps its tree width (its quarks closed below 2m_π: its leptons', 1.1992e-10 GeV); Ωh² and today's rates are
    refused, named. The signal strength is the 125 GeV state's (s0, 36% doublet: RF23-01), and excludes it. A 36%
    doublet light state (s0) is a new scalar as before."""
    from adroit.model_building import feynman
    engine = _das_with_light_scalar(0.24, 0.8)
    p = engine.point()
    mb, rules, _ = engine.at(p)
    (h,) = [x for x in rules.particles if x.spin == 0 and x.parity == 1 and 0 < x.mass < 2]
    by = {y.name: y for y in rules.particles} | {y.anti: y for y in rules.particles if y.anti}
    leptons = sum(feynman.two_body_width(v, v.legs.index(h.name), [by[n].mass for n in v.legs])
                  for v in rules.vertices if v.kind == 'FFS' and v.legs.count(h.name) == 1
                  and all(n in ('e', 'e~', 'mu', 'mu~', 'tau', 'tau~') for n in v.legs if n != h.name))
    assert h.name == 'h' and leptons > 0 and h.width == pytest.approx(leptons, rel=1e-9)
    for why in (engine.domain(p), engine.today_unknown(p)):
        assert why.startswith('the scalar h at 0.24 GeV is mostly the SM doublet')
    assert not engine.higgs_mu_reason(p) and 0 < engine.higgs_mu(p) < 0.36 ** 2 / 0.36
    outcome = searches.higgs_signal(engine, p, True)
    assert outcome.excluded is True and not outcome.why
    singlet = _das_with_light_scalar(0.24, 0.6)
    q = singlet.point()
    assert 'mostly the SM doublet' not in singlet.domain(q) and not singlet.higgs_mu_reason(q)
    assert singlet.higgs_mu(q) is not None


def test_the_higgs_signal_strength_is_the_125_gev_states():
    """The RZ23 re-audit's RF23-01 (2026-10-23): the signal strength was the largest doublet share's, wherever that
    state lay. With eigenmasses 2.5 and 125 GeV and sin θ = 0.99, the 2.5 GeV state (98% doublet) gave μ = 0.98,
    allowed, while the 125 GeV state the measurement sees is 2% doublet: μ = c⁴Γ_SM/Γ_total = 8.27e-7, excluded. The
    ordinary ordering (125 and 300 GeV, sin θ = 0.3) is unchanged: μ = 0.91."""
    from adroit.constraints import higgs
    from adroit.parameter_space.portals import generic_lhc
    engine = _das_with_light_scalar(2.5, 0.99)
    p = engine.point()
    assert searches.higgs_signal(engine, p, True).excluded is True
    assert engine.higgs_mu(p) == pytest.approx(8.270235274039038e-07, rel=1e-6)
    mb, rules, _ = engine.at(p)
    state, why = generic_lhc.measured_higgs(mb, rules)
    assert not why and state.name == 's0' and state.mass_gev == pytest.approx(125.0)
    width = next(x.width for x in rules.particles if x.name == 's0')
    share = 1 - 0.99 ** 2
    assert engine.higgs_mu(p) == pytest.approx(share ** 2 * float(higgs.width(state.mass_gev)) / width, rel=1e-9)
    ordinary = _das_with_light_scalar(300.0, 0.3)
    q = ordinary.point()
    assert ordinary.higgs_mu(q) == pytest.approx(0.91, rel=1e-6)
    assert generic_lhc.measured_higgs(*ordinary.at(q)[:2])[0].name == 'h'


def test_two_scalars_at_the_measured_mass_leave_the_signal_strength_undecided():
    """RF23-01: states at 125 and 126.5 GeV both lie under the measured peaks; their combined signal is not
    implemented, so the search is undecided, named, not computed for either."""
    engine = _das_with_light_scalar(126.5, 0.5)
    p = engine.point()
    assert engine.higgs_mu(p) is None
    outcome = searches.higgs_signal(engine, p, True)
    assert outcome.excluded is None and 'combined signal is not implemented' in outcome.why


def test_the_signal_strength_needs_the_records_rescaling():
    """RF23-01: μ = c⁴Γ_SM/(c²Γ_SM + Γ_new) holds for a state whose SM couplings are one multiple κ of the SM Higgs's
    (κ² = c²), CP-even, to the generator's numerical accuracy (the owner's review, 2026-10-23: 10⁻⁴, not 2%), with no
    new charged or coloured state in its loops. Choubey et al.'s triplet's vev gives the 125 GeV state a W coupling
    9 × 10⁻⁴ off its others, and its charged triplet scalar couples to it (its γγ loop): undecided. A top Yukawa off
    the common κ by 10% or 0.1%, a CP-odd part, a new charged state coupled to it is named; 10⁻⁶ is numerical."""
    import dataclasses

    from adroit.evaluation import zoo
    from adroit.parameter_space.portals import generic_lhc
    entry = next(e for e in zoo.entries() if e.id == 'singlet_triplet_fermion_choubey')
    engine, p = zoo._generic(entry, entry.targets[0])
    outcome = searches.higgs_signal(engine, p, True)
    assert outcome.excluded is None and 'κ_W = ' in outcome.why and 'one multiple' in outcome.why
    das = _das_with_light_scalar(300.0, 0.3)
    mb, rules, _ = das.at(das.point())
    assert generic_lhc._rescaling_reason(rules, 'h', 0.91) == ''
    top = next(v for v in rules.vertices if v.kind == 'FFS' and set(v.legs) == {'t', 't~', 'h'})
    for change, words in ((dict(c=top.c * 1.1), 'one multiple'), (dict(c2=0.1 * top.c), 'CP-odd'),
                          (dict(c=top.c * 1.001), 'one multiple'), (dict(c2=0.001 * top.c), 'CP-odd'),
                          (dict(c=top.c * (1 + 1e-6)), '')):
        changed = [dataclasses.replace(v, **change) if v is top else v for v in rules.vertices]
        reason = generic_lhc._rescaling_reason(dataclasses.replace(rules, vertices=changed), 'h', 0.91)
        assert words in reason if words else reason == ''
    from adroit.model_building.feynman import MassVertex, ParticleRecord
    charged = ParticleRecord('X+', 0, 300.0, 'X-', '1', 1.0, 1, 1.0)
    loop = dataclasses.replace(rules, particles=[*rules.particles, charged],
                               vertices=[*rules.vertices, MassVertex('SSS', ('h', 'X+', 'X-'), 10.0)])
    assert 'the new state X+' in generic_lhc._rescaling_reason(loop, 'h', 0.91)


def test_the_signal_strength_is_decided_only_at_a_compatible_mass():
    """The owner's review of RF23-01 (2026-10-23): the 3 GeV window identifies which state may be the observed Higgs;
    it is not a compatible mass. μ is decided only within 2σ of the measured m_h = 125.09 ± 0.24 GeV: a state at
    124 GeV is identified but pending, one at 125.4 GeV decided."""
    far = _das_with_light_scalar(300.0, 0.3, m1=124.0)
    p = far.point()
    outcome = searches.higgs_signal(far, p, True)
    assert outcome.excluded is None and 'not compatible with the measured m_h' in outcome.why and far.higgs_mu(p) is None
    near = _das_with_light_scalar(300.0, 0.3, m1=125.4)
    q = near.point()
    assert not near.higgs_mu_reason(q) and near.higgs_mu(q) == pytest.approx(0.91, rel=1e-6)


def test_the_singlet_mixing_light_mediator_keeps_its_lepton_width():
    """The RZ23 re-audit's RF23-02 (2026-10-23): the library's h₂ below 2 GeV took the SM table's zero as its width,
    its open muon decay erased, with no refusal. Below 2m_π it is sin²θ times a Higgs boson's open lepton widths,
    G_F m_ℓ² m β³/(4√2π) each (1.874e-12 GeV at 0.24 GeV, sin θ = 0.1), and Ωh² stands; from 2 GeV, the table."""
    from adroit.constraints import higgs
    from adroit.parameter_space.portals.higgs import SingletMixing
    cls = SingletMixing()
    for mass, leptons in ((0.1, (0.51099895e-3,)), (0.24, (0.51099895e-3, 0.10566)), (1.999, (0.51099895e-3, 0.10566))):
        p = Point(m_chi=10.0, m_med=mass, g_chi=0.1, g_q=0.1)
        expected = sum(0.01 * higgs.G_F * m ** 2 * mass * (1 - 4 * m * m / mass ** 2) ** 1.5 / (4 * math.sqrt(2) * math.pi)
                       for m in leptons)
        assert cls.mediators(p)[1].width == pytest.approx(expected, rel=1e-9) and expected > 0
        assert cls.domain(p) == '' and cls.today_unknown(p) == ''
    assert cls.mediators(Point(m_chi=10.0, m_med=0.24, g_chi=0.1, g_q=0.1))[1].width == pytest.approx(1.874e-12,
                                                                                                   rel=1e-3)
    at_table = Point(m_chi=10.0, m_med=2.0, g_chi=0.1, g_q=0.1)
    assert cls.mediators(at_table)[1].width == pytest.approx(0.01 * float(higgs.width(2.0)), rel=1e-12)


def test_the_singlet_mixing_light_mediator_is_refused_as_the_generic_routes():
    """RF23-02: the same light scalar is decided as on the generic route. Mostly doublet (sin²θ > ½) below 2 GeV: no
    SM-like width or hadronic prescription, Ωh² and today refused (``generic._light_higgs``). Mostly singlet in the
    hadronic window (2m_π to 3 GeV): its hadronic width (0 ≤ Γ_had ≤ m) refused where it moves the s-channel
    propagator (m_χ = 2.1 GeV at m₂ = 1 GeV), computed where it cannot (m_χ = 10 GeV), as
    ``generic_hadronic.propagator_reason``."""
    from adroit.parameter_space.portals.higgs import SingletMixing
    cls = SingletMixing()
    doublet = Point(m_chi=10.0, m_med=0.24, g_chi=0.1, g_q=0.8)
    assert cls.domain(doublet).startswith('the scalar h₂ at 0.24 GeV is mostly the SM doublet')
    assert cls.today_unknown(doublet) == cls.domain(doublet)
    generic = _das_with_light_scalar(0.24, 0.8)
    assert 'mostly the SM doublet' in generic.domain(generic.point())
    assert cls.domain(Point(m_chi=10.0, m_med=2.5, g_chi=0.1, g_q=0.8)) == ''
    near = Point(m_chi=2.1, m_med=1.0, g_chi=0.1, g_q=0.1)
    for why in (cls.domain(near), cls.today_unknown(near)):
        assert 'hadronic window' in why and 'moves the s-channel propagator' in why
    assert cls.domain(Point(m_chi=10.0, m_med=1.0, g_chi=0.1, g_q=0.1)) == ''
    assert cls.domain(Point(m_chi=2.1, m_med=0.2, g_chi=0.1, g_q=0.1)) == ''        # below 2m_π: closed
    assert cls.domain(Point(m_chi=2.1, m_med=1.0, g_chi=0.1, g_q=0.0)) == ''        # no SM coupling


def test_the_higgs_portals_annihilate_today_below_the_width_table():
    """The owner's follow-up to the RZ23 re-audit (2026-10-23): below m_DM = 1 GeV (√s < 2 GeV) the library's Higgs
    portals read the SM width table's zero for every channel, so today's rates were empty and the CMB took them as out
    of reach (no outcome at all). The lepton pairs and γγ are computed there (``higgs.light_channel_width``); in the
    hadronic window the quark pairs are named as not computed, so the CMB is undecided unless the computed channels
    exclude alone; below 2m_π nothing hadronic is open and it decides on the computed channels."""
    from adroit.parameter_space.portals.higgs import (HiggsPortalFermion, HiggsPortalScalar, HiggsPortalVector,
                                                      SingletMixing)

    def lepton(mass: float, root: float) -> float:
        return mass ** 2 * (1 - 4 * mass ** 2 / root ** 2) ** 1.5 if root > 2 * mass else 0.0

    for cls in (HiggsPortalScalar(), HiggsPortalFermion(), HiggsPortalVector(), SingletMixing()):
        p = Point(m_chi=0.5, m_med=50.0, g_chi=0.1, g_q=0.1)
        rates = cls.sigma_v_today(p, 1e-3)
        root = math.sqrt(4 * 0.25 / (1 - 0.5e-3 ** 2))
        assert rates['e'] > 0 and rates['mu'] > 0 and rates['gamma'] > 0
        assert rates['e'] / rates['mu'] == pytest.approx(lepton(0.51099895e-3, root) / lepton(0.10566, root), rel=1e-9)
        assert 'hadronic window' in searches.today_unknown(cls, p)
        closed = Point(m_chi=0.1, m_med=50.0, g_chi=0.1, g_q=0.1)
        assert searches.today_unknown(cls, closed) == '' and cls.sigma_v_today(closed, 1e-3)['e'] > 0
        assert 'e' not in cls.sigma_v_today(Point(m_chi=3.0, m_med=50.0, g_chi=0.1, g_q=0.1), 1e-3)
    scalar = HiggsPortalScalar()
    p = Point(m_chi=0.5, m_med=50.0, g_chi=0.1)
    outcome = searches.cmb(scalar, p, True)
    assert outcome is not None and outcome.excluded is None and 'hadronic window' in outcome.why
    below, above = (scalar.sigma_v_today(Point(m_chi=m, m_med=50.0, g_chi=0.1), 1e-3)['gamma']
                    for m in (0.99999, 1.00001))
    assert below == pytest.approx(above, rel=1e-3)                     # γγ continuous at the table's start

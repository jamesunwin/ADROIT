"""P1, the mediator's portrait (``portals.generic_portrait``), and its declared gate: the library families' own
mediators reproduced from the generic route, couplings to 10⁻⁶ and widths to 1%."""
import math

import pytest

from adroit.model_building.ufo_export import SM_NAMES
from adroit.parameter_space import library, searches
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals import generic_portrait as gp
from adroit.parameter_space.portals.generic import GenericModel

# each library entry's spec couplings and the library point's slot that sets them
VALUES = {'dmwg_V1': {'g_DM': 'g_chi', 'g_q': 'g_q'}, 'dmwg_A1': {'g_DM': 'g_chi', 'g_q': 'g_q'},
          'scalar_mediator': {'g_chi': 'g_chi', 'g_q': 'g_q'}, 'alp_portal': {'g_chi': 'g_chi', 'g_q': 'g_q', 'g_l': 'g_l'},
          'b_minus_l': {'g_chi': 'g_chi', 'g_BL': 'g_q'}, 'lmu_minus_ltau': {'g_chi': 'g_chi', 'g_mt': 'g_q'}}
QUARKS = ('u', 'd', 's', 'c', 'b', 't')
NEEDS_TABLES = pytest.mark.needs('production_tables')     # a case the tools folder decides (B20-08)
NEEDS_R = pytest.mark.needs('pdg_r_ratio')                  # below 2 GeV the hadronic width needs the PDG's R


def _portrait(entry_id: str):
    e = library.entry(entry_id)
    spec = e.spec()
    names = VALUES[entry_id]
    spec = spec.model_copy(update={'couplings': [c.model_copy(update={'value': getattr(e.point, names[c.name])})
                                                 if c.name in names else c for c in spec.couplings]})
    engine = GenericModel.for_spec(spec)
    found = gp.portraits(engine, engine.point())
    assert len(found) == 1
    return e, found[0]


def _library_widths(e) -> dict:
    cls, p = e.model_class, e.point
    built = searches._z_prime(cls, p) or searches._scalar(cls, p)
    return built[3] if built else searches._vector_widths(p, cls.fermions(p), (p.g_chi, 0.0))


@pytest.mark.parametrize('entry_id', sorted(VALUES))
def test_the_library_mediators_widths_are_reproduced(entry_id):
    """Each partial width the library computes, and the total, within 1%. The Yukawa-like scalar and ALP declare the
    DMsimp _MD card's Yukawa inputs on both routes (the owner's decision #2, 2026-10-20: equivalent models with the
    same declared convention agree; until then their b and c widths had differed by (4.7/3.007)² = 2.44)."""
    e, m = _portrait(entry_id)
    widths = _library_widths(e)
    codes = {abs(code): name for name, (_, _, code) in SM_NAMES.items()}
    expected = 0.0
    for key, width in widths.items():
        name = '' if key == 'dm' else codes[abs(key[0])]
        expected += width
        if width < 1e-3 * sum(widths.values()):
            continue
        dm = m.dark_matter.fermion if m.dark_matter else ''
        ours = m.partial(dm, dm + '~') if key == 'dm' else m.partial(name, name + '~')
        assert ours == pytest.approx(width, rel=1e-2), key
    assert m.width_gev == pytest.approx(expected, rel=1e-2)


def test_the_library_mediators_couplings_are_reproduced():
    """The Lagrangian's couplings, to 10⁻⁶: the DMWG's vector and axial-vector g_q and g_DM; B − L's charges (the
    left-handed neutrinos' (g_V, g_A) = (g, −g)/2); the scalar and the ALP Yukawa-like, κ = −g_q (G2's h couples as
    −m_f/v) and κ₅ = −g_q, with nothing else in their couplings."""
    e, v1 = _portrait('dmwg_V1')
    assert v1.cp == 'vector' and v1.dark_matter.even == pytest.approx(e.point.g_chi, rel=1e-6)
    assert all(v1.coupling(q).even == pytest.approx(e.point.g_q, rel=1e-6) and v1.coupling(q).odd == 0 for q in QUARKS)
    e, a1 = _portrait('dmwg_A1')
    assert a1.cp == 'axial' and all(a1.coupling(q).odd == pytest.approx(e.point.g_q, rel=1e-6) for q in QUARKS)
    e, bl = _portrait('b_minus_l')
    g = e.point.g_q
    assert all(bl.coupling(q).even == pytest.approx(g / 3, rel=1e-6) for q in QUARKS)
    assert all(bl.coupling(lep).even == pytest.approx(-g, rel=1e-6) for lep in ('e', 'mu', 'tau'))
    nu = bl.coupling('nu_e')
    assert (nu.even, nu.odd) == (pytest.approx(-g / 2, rel=1e-6), pytest.approx(g / 2, rel=1e-6))
    from adroit.model_building import yukawa
    from adroit.model_building.gauge_basis import V_EW
    e, m = _portrait('alp_portal')                       # Yukawa-like to quarks and leptons alike, in the card's inputs
    assert e.spec().yukawa == 'DMsimp_s_spin0_MD'
    assert all(abs(m.coupling(f).odd) == pytest.approx(e.point.g_q * yukawa.mass('DMsimp_s_spin0_MD', f) / V_EW,
                                                       rel=1e-6) for f in (*QUARKS, 'mu', 'tau'))
    e, m = _portrait('scalar_mediator')                  # Yukawa-like to the quarks only (the tactical audit's T20-01)
    from adroit.parameter_space.portals import generic_production as gpr
    assert gpr.heavy_higgs_kappa(m) is None              # the card's Yukawas are not the h's ("sm") exactly
    spec = e.spec()
    spec = spec.model_copy(update={'yukawa': 'sm', 'couplings': [c.model_copy(update={'value': getattr(
        e.point, VALUES['scalar_mediator'][c.name])}) if c.name in VALUES['scalar_mediator'] else c
        for c in spec.couplings]})
    engine = GenericModel.for_spec(spec)
    (m,) = gp.portraits(engine, engine.point())
    h = gp._standard()['h']
    leptons = sum(h[f][0] ** 2 for f in ('e', 'mu', 'tau')) / sum(c[0] ** 2 for c in h.values())
    assert gpr.heavy_higgs_kappa(m) == pytest.approx(-e.point.g_q, rel=1e-6)     # "sm": the h's times κ
    assert m.pattern_residual == pytest.approx(leptons ** 0.5, rel=1e-6)


def test_a_singlets_mixing_and_a_dark_photons_kinetic_mixing_are_read_from_their_couplings():
    """A Higgs-mixed singlet's couplings are sin θ times the h's (Das et al.'s benchmark, sin θ = 10⁻³: a
    development-half zoo model); a kinetically mixed dark photon's are a multiple of the photon's, with no Z part
    (Feng et al.'s), and its decay to the dark scalar pair is invisible."""
    from adroit.evaluation import zoo
    def portrait(entry_id):
        e = next(x for x in zoo.entries() if x.id == entry_id)
        engine, p = zoo._generic(e, e.targets[0])
        return gp.portraits(engine, p)
    singlet = [m for m in portrait('singlet_fermion_scalar_mediator_das') if m.spin == 0][0]
    assert singlet.cp == 'even' and singlet.higgs_like == pytest.approx(1e-3, rel=1e-6)
    assert singlet.pattern_residual < 1e-9
    photon = portrait('dark_photon_complex_scalar_feng')[0]
    assert photon.cp == 'vector' and abs(photon.photon_like) > 1e-4 and abs(photon.z_like) < 1e-8 * abs(photon.photon_like) + 1e-10
    assert photon.pattern_residual < 1e-5
    assert photon.invisible_width_gev == pytest.approx(photon.width_gev, rel=1e-6)


# --- P2: production from the portrait ---------------------------------------------------------------------------------

@pytest.mark.parametrize('entry_id', ['dmwg_V1', 'dmwg_A1', 'b_minus_l', pytest.param('scalar_mediator', marks=NEEDS_TABLES),
                                      pytest.param('alp_portal', marks=NEEDS_TABLES)])
def test_the_library_mediators_production_is_reproduced(entry_id):
    """P2's gate: the library's σ to 1%. The vectors through the per-flavour q q̄ tables (their sum is the universal
    and the B − L tables); the scalars, which declare the DMsimp card's Yukawa inputs on both routes (decision #2),
    through the t, b and tb gluon-fusion tables × K, each loop scaled by its coupling in the tables' own masses."""
    from adroit.parameter_space.portals import generic_production as gpr
    e, m = _portrait(entry_id)
    built = searches._z_prime(e.model_class, e.point) or searches._scalar(e.model_class, e.point)
    library = built[0]
    if m.spin == 0:
        assert gpr.single(m).process.startswith('gg → X through the t and b loops')
    assert gpr.single(m).sigma_pb == pytest.approx(library, rel=1e-2)


@pytest.mark.needs("production_tables")
def test_a_mediator_coupled_to_no_quark_is_not_produced_and_outside_the_tables_says_why():
    from adroit.parameter_space.portals import generic_production as gpr
    _, m = _portrait('lmu_minus_ltau')
    assert gpr.single(m).sigma_pb == 0.0
    _, v1 = _portrait('dmwg_V1')
    far = gpr.single(v1.model_copy(update={'mass_gev': 1e5}))
    assert far.sigma_pb is None and 'outside' in far.why


# --- P3: the resonance searches through the generic route ---------------------------------------------------------------

def _generic_at(entry_id: str, point):
    """The library entry as a generic model at a point of its plane (its couplings from the point's slots)."""
    e = library.entry(entry_id)
    names = VALUES[entry_id]
    spec = e.spec()
    spec = spec.model_copy(update={'couplings': [c.model_copy(update={'value': getattr(point, names[c.name])})
                                                 if c.name in names else c for c in spec.couplings]})
    engine = GenericModel.for_spec(spec)
    return engine, engine.point().model_copy(update={'m_chi': point.m_chi, 'm_med': point.m_med})


def _same(library_outcome, generic_outcome):
    if isinstance(library_outcome, list):                      # B − L: LEP's contact bound, then ATLAS's
        assert isinstance(generic_outcome, list) and len(generic_outcome) == len(library_outcome)
        for a, b in zip(library_outcome, generic_outcome):
            _same(a, b)
        return
    assert (library_outcome is None) == (generic_outcome is None)
    if library_outcome is None:
        return
    assert library_outcome.excluded == generic_outcome.excluded
    if library_outcome.ratio is not None:
        assert generic_outcome.ratio == pytest.approx(library_outcome.ratio, rel=1e-2)


@pytest.mark.parametrize('entry_id, search, points', [
    ('dmwg_V1', 'dijet', [(100, 1000, .25), (100, 2000, .1), (100, 2500, .5), (300, 3000, .05), (100, 700, .02)]),
    ('dmwg_A1', 'dijet', [(100, 1200, .2), (200, 3500, .3)]),
    pytest.param('scalar_mediator', 'ttbar', [(100, 500, 1.0), (100, 600, 3.0), (300, 700, 0.5), (50, 450, 2.0)],
                 marks=NEEDS_TABLES),       # gg → S from the tables (with #2's card Yukawas its b loop is read)
    pytest.param('b_minus_l', 'dilepton', [(1000, 2000, .1), (500, 3000, .3), (100, 1000, .01), (100, 1500, .003),
                                           (100, 4000, .2)], marks=NEEDS_TABLES),
])
def test_the_library_outcomes_are_reproduced_through_the_generic_route(entry_id, search, points):
    """P3's gate: the library's resonance outcomes on its own families, through the generic route (the portrait, its
    production and the same records), at points of the test planes: the same decision, ratios to 1%. B − L's LEP
    contact bound, calibrated on its charges, applies to a generic vector with exactly those charges (P4)."""
    from adroit.parameter_space import resonances
    evaluate = getattr(resonances, search, None) or getattr(searches, search)
    e = library.entry(entry_id)
    for m_chi, m_med, g in points:
        update = {'m_chi': m_chi, 'm_med': m_med, 'g_q': g} | ({'g_chi': g / 3} if entry_id == 'b_minus_l' else {})
        p = e.point.model_copy(update=update)
        engine, q = _generic_at(entry_id, p)
        _same(evaluate(e.model_class, p, False), evaluate(engine, q, False))


@pytest.mark.needs("production_tables")
def test_a_generic_scalar_beyond_the_diboson_searches_reach_is_not_judged_by_them():
    from adroit.evaluation import zoo
    e = next(x for x in zoo.entries() if x.id == 'singlet_fermion_scalar_mediator_das')
    engine, p = zoo._generic(e, e.targets[0])                  # its singlet at 200 GeV, below ATLAS's ZZ and WW
    assert searches.heavy_scalar(engine, p, False) is None


# --- P4: light vectors ----------------------------------------------------------------------------------------------

SM_CHARGES = {'u': 2 / 3, 'c': 2 / 3, 't': 2 / 3, 'd': -1 / 3, 's': -1 / 3, 'b': -1 / 3, 'e': -1, 'mu': -1, 'tau': -1}


def _dark_photon(m_chi: float, m_med: float, g_d: float, epsilon: float):
    """The library's Dirac dark photon as a generic model written below breaking: its couplings −ε e Q_f to every
    charged fermion (e at the Thomson limit, as DarkCast's ε) and g_D to the dark matter."""
    from adroit.core.model_spec import ModelSpec
    fields = [{'name': 'chi', 'role': 'dark_matter', 'spin': 0.5, 'dark_parity': -1, 'mass_gev': m_chi},
              {'name': 'Ap', 'role': 'mediator', 'spin': 1, 'self_conjugate': True, 'mass_gev': m_med}]
    fields += [{'name': f, 'role': 'standard_model', 'spin': 0.5} for f in SM_CHARGES]
    terms = [{'fields': [{'field': 'chi', 'conjugate': True}, {'field': 'chi'}, {'field': 'Ap'}], 'lorentz': 'vector',
              'coupling': 'g_D'}]
    terms += [{'fields': [{'field': f, 'conjugate': True}, {'field': f}, {'field': 'Ap'}], 'lorentz': 'vector',
               'coupling': f'-eps*e*({q:.6f})'} for f, q in SM_CHARGES.items()]
    spec = ModelSpec.model_validate({'name': 'dark photon', 'phase': 'broken', 'fields': fields, 'terms': terms,
                                     'couplings': [{'name': 'g_D', 'value': g_d}, {'name': 'eps', 'value': epsilon}]})
    engine = GenericModel.for_spec(spec)
    return engine, engine.point()


def test_a_generic_dark_photon_reads_its_kinetic_mixing_in_darkcasts_convention():
    """P4: ε from the couplings is DarkCast's, relative to e at the Thomson limit (G2's photon couples at the
    electroweak scale: 0.30842 against 0.30282), so a spec writing −ε e Q_f gives back ε."""
    engine, p = _dark_photon(1.0, 3.0, 0.5, 2e-4)
    (epsilon, m, ((width, invisible, visible),), unknown), = searches._generic_dark_photons(engine, p)
    assert epsilon == pytest.approx(2e-4, rel=1e-6) and m == pytest.approx(3.0) and 0 < invisible <= 1
    assert visible == pytest.approx(1 - invisible, rel=1e-12) and unknown == ""


@pytest.mark.parametrize('m_med, epsilon', [*(pytest.param(*x, marks=NEEDS_R) for x in [(0.02, 1e-3), (0.02, 1e-6), (0.1, 3e-4),
                                                                                       (0.25, 1e-5)]),
                                            (10.0, 1e-3), (30.0, 1e-4), (300.0, 1e-3)])
def test_the_library_dark_photon_outcomes_are_reproduced(m_med, epsilon):
    """P4's gate (dark photon): DarkCast's outcome on the library's Dirac dark photon (α_D = 0.5, m_A′ = 3 m_χ) and on
    the same model through the generic route: the same decision. Above 200 GeV both are pending."""
    from adroit.parameter_space.library import ALPHA_D_HALF
    e = library.entry('dark_photon_dirac')
    p = e.point.model_copy(update={'m_chi': m_med / 3, 'm_med': m_med, 'g_chi': ALPHA_D_HALF, 'g_q': epsilon})
    engine, q = _dark_photon(m_med / 3, m_med, ALPHA_D_HALF, epsilon)
    ours, theirs = searches.dark_photon(engine, q, False), searches.dark_photon(e.model_class, p, False)
    assert (ours is None) == (theirs is None)
    if theirs is not None:
        assert ours.excluded == theirs.excluded, (ours.why, theirs.why)


@pytest.mark.parametrize('m_med, g', [*(pytest.param(*x, marks=NEEDS_R) for x in [(0.03, 3e-4), (0.2, 1e-3), (1.5, 1e-3), (1.5, 1e-4)]),
                                      (8.0, 5e-3), (30.0, 0.05)])
def test_the_library_lmu_minus_ltau_outcomes_are_reproduced(m_med, g):
    """P4's gate (L_μ − L_τ): muon g − 2, BaBar and Belle II, CCFR's trident limit and CMS's 4μ (pending) on the
    library's Z′ (m_Z′ = 3 m_χ, unit charges) and on the same model through the generic route, recognised by its
    charges: the same decisions, ratios to 2%."""
    e = library.entry('lmu_minus_ltau')
    p = e.point.model_copy(update={'m_chi': m_med / 3, 'm_med': m_med, 'g_chi': g, 'g_q': g})
    engine, q = _generic_at('lmu_minus_ltau', p)
    ours, theirs = searches.lmu_ltau(engine, q, False), searches.lmu_ltau(e.model_class, p, False)
    assert [o.name for o in ours] == [o.name for o in theirs]
    for a, b in zip(ours, theirs):
        assert a.excluded == b.excluded, (a.name, a.why, b.why)
        if b.ratio:
            assert a.ratio == pytest.approx(b.ratio, rel=2e-2), a.name


@pytest.mark.parametrize('entry_id, m_med, g', [('dark_photon_dirac', 0.003, 1e-6), ('dark_photon_dirac', 0.008, 1e-9),
                                                ('b_minus_l', 0.004, 1e-9), ('b_minus_l', 0.002, 3e-6),
                                                ('lmu_minus_ltau', 0.005, 1e-3), ('lmu_minus_ltau', 0.009, 1e-7)])
def test_the_library_light_vectors_bbn_outcomes_are_reproduced(entry_id, m_med, g):
    """P4's gate (BBN): Sabti et al.'s bound on the library's light dark photon (thermalised or by freeze-in), B − L
    and L_μ − L_τ vectors and on the same models through the generic route, recognised by their coupling patterns."""
    from adroit.parameter_space.library import ALPHA_D_HALF
    e = library.entry(entry_id)
    if entry_id == 'dark_photon_dirac':
        p = e.point.model_copy(update={'m_chi': m_med / 3, 'm_med': m_med, 'g_chi': ALPHA_D_HALF, 'g_q': g})
        engine, q = _dark_photon(m_med / 3, m_med, ALPHA_D_HALF, g)
    else:
        p = e.point.model_copy(update={'m_chi': m_med / 3, 'm_med': m_med, 'g_chi': g / 3, 'g_q': g})
        engine, q = _generic_at(entry_id, p)
    _same(searches.bbn(e.model_class, p, False), searches.bbn(engine, q, False))


def test_a_coupling_below_the_generic_routes_resolution_is_refused_not_ignored():
    """P4's gate found it: G2 drops vertices below 10⁻¹⁰, so a B − L vector at g = 10⁻¹² had no couplings and looked
    uncoupled to every search. The generic route now refuses such a model by name (its domain)."""
    e = library.entry('b_minus_l')
    p = e.point.model_copy(update={'m_chi': 0.004 / 3, 'm_med': 0.004, 'g_chi': 1e-12 / 3, 'g_q': 1e-12})
    engine, q = _generic_at('b_minus_l', p)
    assert 'resolution' in engine.domain(q) and not searches.generic_mediators(engine, q, 1)
    assert searches.bbn(engine, q, False) is None              # nothing read from a partly dropped pattern
    p = p.model_copy(update={'g_chi': 1e-6, 'g_q': 1e-6})
    engine, q = _generic_at('b_minus_l', p)
    assert 'resolution' not in engine.domain(q)



def _g2_band() -> tuple[float, float]:
    from adroit.constraints import searches as cs
    d = cs._record('muon-g2-2025').data
    return d['delta_a_mu'] - 1.96 * d['sigma'], d['delta_a_mu'] + 1.96 * d['sigma']


def _muon_spec(fields: list[dict], terms: list[tuple], couplings: dict):
    """A broken-phase generic model: the dark matter χ (Dirac, 50 GeV) and the muon, plus ``fields``; each term
    (fields, lorentz, coupling)."""
    from adroit.core.model_spec import ModelSpec
    base = [{'name': 'chi', 'role': 'dark_matter', 'spin': .5, 'dark_parity': -1, 'mass_gev': 50.0},
            {'name': 'mu', 'role': 'standard_model', 'spin': .5}]
    spec = ModelSpec.model_validate({'name': 'muon', 'phase': 'broken', 'fields': base + fields, 'terms': [
        {'fields': [{'field': f.rstrip('*'), 'conjugate': f.endswith('*')} for f in legs], 'lorentz': lorentz,
         'coupling': c} for legs, lorentz, c in terms], 'couplings': [{'name': k, 'value': v} for k, v in couplings.items()]})
    engine = GenericModel.for_spec(spec)
    return engine, engine.point()


def _vector(name: str, mass: float) -> dict:
    return {'name': name, 'role': 'mediator', 'spin': 1, 'self_conjugate': True, 'mass_gev': mass}


@pytest.mark.needs("pdg_r_ratio", "darkcast")      # the library vectors' widths: the R ratio, DarkCast's B − L
@pytest.mark.parametrize('side', [0.9, 1.1])
@pytest.mark.parametrize('entry_id, m_med', [('b_minus_l', .05), ('b_minus_l', 1.0), ('b_minus_l', 20.0),
                                             ('lmu_minus_ltau', .05), ('lmu_minus_ltau', 1.0), ('lmu_minus_ltau', 20.0),
                                             ('dark_photon_dirac', .05), ('dark_photon_dirac', 1.0)])
def test_a_library_vectors_g2_is_the_generic_routes_on_both_sides_of_its_bound(entry_id, m_med, side):
    """The owner's decision #11 (2026-10-20): one muon g − 2 for the library and the generic route. The library's
    B − L and L_μ − L_τ vectors and Dirac dark photon, and the same models through the generic route, with the coupling
    set so that Δa_μ is 0.9 and 1.1 times the record's upper 95% edge: the same Δa_μ and the same decision, allowed
    and excluded. The library's L_μ − L_τ class adds the loop-induced kinetic mixing εeQ to the charged leptons'
    couplings, which its spec does not write (Δa_μ 0.88% higher): written into the spec, the routes agree. The
    library's dark photon is the exact diagonalisation with the Z, the spec its photon-like limit (10⁻⁵ below 1 GeV)."""
    from adroit.parameter_space.library import ALPHA_D_HALF
    e = library.entry(entry_id)
    dark_photon = entry_id == 'dark_photon_dirac'

    def at(g: float):
        update = {'m_med': m_med, 'm_chi': m_med / 3, 'g_q': g, 'g_chi': ALPHA_D_HALF if dark_photon else g / 3}
        return e.point.model_copy(update=update)
    reference = searches.muon_g2(e.model_class, at(1e-3), True).value
    g = 1e-3 * math.sqrt(side * _g2_band()[1] / reference)
    p = at(g)
    theirs = searches.muon_g2(e.model_class, p, True)
    if dark_photon:
        engine, q = _dark_photon(m_med / 3, m_med, ALPHA_D_HALF, g)
    elif entry_id == 'lmu_minus_ltau':
        share = e.model_class.fermions(p)['mu'][0] / g             # 1 + e²ln(m_τ²/m_μ²)/(12π²)
        assert share == pytest.approx(1.00438, abs=1e-5)
        spec = e.spec()
        spec = spec.model_copy(update={
            'terms': [t.model_copy(update={'coupling': f'g_mt*{share!r}'}) if t.fields[0].field == 'mu' else t
                      for t in spec.terms],
            'couplings': [c.model_copy(update={'value': {'g_chi': g / 3, 'g_mt': g}[c.name]}) for c in spec.couplings]})
        engine = GenericModel.for_spec(spec)
        q = engine.point().model_copy(update={'m_chi': m_med / 3, 'm_med': m_med})
    else:
        engine, q = _generic_at(entry_id, p)
    ours = searches.muon_g2(engine, q, True)
    assert ours.value == pytest.approx(theirs.value, rel=1e-4 if dark_photon else 1e-9)
    assert ours.excluded is theirs.excluded is (side > 1)


@pytest.mark.parametrize('side', [0.9, 1.1])
def test_a_muon_partners_g2_is_one_calculation_on_both_sides_of_its_bound(side):
    """The library's lepton portal (Majorana χ, a partner φ of μ_R, L ⊃ y φ* χ̄ P_R μ) and the same model through the
    generic route: Δa_μ < 0, with y set so that it is 0.9 and 1.1 times the record's lower 95% edge."""
    from adroit.constraints import searches as cs
    from tests.parameter_space.test_scan_fallback import SPEC
    low = _g2_band()[0]
    assert low < 0
    m_chi, m_phi = 120.0, 250.0
    y = math.sqrt(side * low / cs.muon_g2_scalar_partner(1.0, m_phi, m_chi))
    theirs = searches.muon_g2(library.entry('lepton_portal_muR').model_class,
                              Point(m_chi=m_chi, m_med=m_phi, g_chi=y), True)
    spec = SPEC.model_copy(update={'couplings': [c.model_copy(update={'value': y}) for c in SPEC.couplings]})
    engine = GenericModel.for_spec(spec)
    ours = searches.muon_g2(engine, engine.point(), True)
    assert ours.value == pytest.approx(theirs.value, rel=1e-9) and ours.excluded is theirs.excluded is (side > 1)
    assert searches.partner(library.entry('lepton_portal_muR').model_class, Point(m_chi=m_chi, m_med=m_phi), True) \
        is None                                                    # its g − 2 is the total's alone


def test_the_total_is_compared_so_parts_of_opposite_sign_cancel():
    """A vector coupled to the muon (Δa_μ > 0) and an axial one (Δa_μ < 0): each alone outside the record's band,
    together at its centre, allowed. Each excluding alone was the old reading."""
    from adroit.constraints import searches as cs
    low, high = _g2_band()
    centre = (low + high) / 2
    g_v = math.sqrt(2 * high / cs.muon_g2_vector(1.0, 1.0))
    g_a = math.sqrt((2 * high - centre) / -cs.muon_g2_axial(1.0, 2.0))
    vector = ([_vector('X1', 1.0)], [(('chi*', 'chi', 'X1'), 'vector', 'gc'), (('mu*', 'mu', 'X1'), 'vector', 'gv')])
    axial = ([_vector('X2', 2.0)], [(('mu*', 'mu', 'X2'), 'axial', 'ga')])
    values = {'gc': 0.1, 'gv': g_v, 'ga': g_a}
    both = searches.muon_g2(*_muon_spec(vector[0] + axial[0], vector[1] + axial[1], values), True)
    alone = searches.muon_g2(*_muon_spec(vector[0], vector[1], {'gc': .1, 'gv': g_v}), True)
    assert both.value == pytest.approx(centre, rel=1e-6) and both.excluded is False and 'the sum of' in both.why
    assert alone.excluded is True and alone.value == pytest.approx(2 * high, rel=1e-6)
    only_axial = ([_vector('X1', 1.0), _vector('X2', 2.0)], [(('chi*', 'chi', 'X1'), 'vector', 'gc'), axial[1][0]])
    assert searches.muon_g2(*_muon_spec(*only_axial, {'gc': .1, 'ga': g_a}), True).excluded is True


def test_the_total_is_pending_where_a_state_coupled_to_the_muon_is_not_computed(monkeypatch):
    """The applicability policy (the owner, 2026-10-20): a neutral scalar coupled to the muon leaves the total pending,
    its two-loop Barr–Zee terms being able to compete with its one loop (Ilisie, arXiv:1502.04199), beside a computed
    vector or alone; a scalar with no coupling to the muon does not. A charged partner coupled to both chiralities,
    alone (which G1 cannot yet write: a partner's Yukawa is chiral, with a singlet; the rules are edited here), is
    pending: its chirality flip is not computed."""
    from tests.parameter_space.test_scan_fallback import SPEC
    scalar = {'name': 'S', 'role': 'mediator', 'spin': 0, 'self_conjugate': True, 'mass_gev': 3.0}
    terms = [(('chi*', 'chi', 'X1'), 'vector', 'gc'), (('mu*', 'mu', 'X1'), 'vector', 'gv'),
             (('mu*', 'mu', 'S'), 'scalar', 'gs')]
    mixed = searches.muon_g2(*_muon_spec([_vector('X1', 1.0), scalar], terms, {'gc': .1, 'gv': 1e-4, 'gs': 1e-3}), True)
    scalar_reason = 'the neutral-scalar contribution, including relevant two-loop terms, is not computed (S0)'
    assert mixed.excluded is None and mixed.why.startswith(scalar_reason) and 'X1' in mixed.why
    alone = _muon_spec([scalar], [(('chi*', 'chi', 'S'), 'scalar', 'gc'), terms[2]], {'gc': .1, 'gs': 1e-3})
    by_itself = searches.muon_g2(*alone, True)
    assert by_itself.excluded is None and by_itself.why == scalar_reason and by_itself.value is None
    decoupled = _muon_spec([scalar], [(('chi*', 'chi', 'S'), 'scalar', 'gc')], {'gc': .1})
    assert searches.muon_g2(*decoupled, True) is None
    engine = GenericModel.for_spec(SPEC)
    q = engine.point()
    mb, rules, model = engine.at(q)
    from dataclasses import replace
    both = [replace(v, c2=0j) if v.kind == 'FFS' and 'phi+' in v.legs[2] else v for v in rules.vertices]
    monkeypatch.setattr(GenericModel, 'at', lambda self, p: (mb, replace(rules, vertices=both), model))
    outcome = searches.muon_g2(engine, q, True)
    assert outcome.excluded is None and 'both chiralities' in outcome.why


def test_a_charged_scalar_with_a_neutrino_is_computed_and_a_neutral_scalar_beside_it_leaves_the_total_pending():
    """The zoo's development half (Choubey et al.'s singlet-triplet fermions with a scalar triplet Δ): Δ⁺ joins the
    muon to ν_μ with one chirality, the partner formula at m_ν = 0, computed; Δ⁰ is a neutral scalar coupled to the
    muon, not computed, so the total is pending. Before the owner's decision #11 the model had no g − 2 outcome."""
    from adroit.evaluation import zoo
    from adroit.evaluation.core import Half, half_of
    entry = next(e for e in zoo.entries() if e.id == 'singlet_triplet_fermion_choubey')
    assert half_of('model_zoo', entry.id) is Half.development
    target = entry.targets[0]
    engine = GenericModel.of(zoo._spec(entry, target), scan=target.scan, tied=target.tied or '')
    q = engine.point()
    parts, unknown, scalars = searches.g2_parts(engine, q)
    assert [label for label, _ in parts] == ['Delta+ with nu_mu'] and parts[0][1] < 0 and not unknown
    assert scalars == ['Delta0']
    outcome = searches.muon_g2(engine, q, True)
    assert outcome.excluded is None and 'Delta0' in outcome.why and 'Delta+ with nu_mu' in outcome.why


@pytest.mark.parametrize('entry_id, coupled', [('alp_portal', 'S (its g_ℓ)'), ('singlet_scalar_mixing', 'h₂'),
                                              ('scalar_mediator', None), ('inert_doublet', None)])
def test_a_library_scalar_coupled_to_the_muon_leaves_its_g2_pending(entry_id, coupled):
    """The same policy on the library's route: the ALP (g_ℓ = 1) and the singlet mixed with the Higgs boson
    (sin θ ≠ 0) are pending, naming the scalar; the scalar mediator at its benchmark (g_ℓ = 0) and the inert doublet
    (no Yukawas) have no g − 2 outcome."""
    e = library.entry(entry_id)
    if entry_id == 'inert_doublet':
        pytest.importorskip('adroit.constraints.maddm')
        from adroit.constraints import maddm
        if not maddm.python().exists():
            pytest.skip('the UFO models are read with MadGraph\'s Python (the tools folder)')
    outcome = searches.muon_g2(e.model_class, e.point, True)
    if coupled is None:
        assert outcome is None
    else:
        assert outcome.excluded is None and outcome.why.startswith('the neutral-scalar contribution, including '
                                                                   'relevant two-loop terms, is not computed')
        assert coupled in outcome.why


@pytest.mark.needs("pdg_r_ratio")
def test_lmu_ltau_leaves_its_g2_to_the_total():
    """An L_μ − L_τ vector's g − 2, library and generic, is ``muon_g2``'s; ``lmu_ltau`` no longer states its own."""
    e = library.entry('lmu_minus_ltau')
    p = e.point.model_copy(update={'m_med': 1.0, 'm_chi': 1 / 3, 'g_q': 1e-3, 'g_chi': 1e-3 / 3})
    engine, q = _generic_at('lmu_minus_ltau', p)
    for cls, point in ((e.model_class, p), (engine, q)):
        assert searches.G2 not in [o.name for o in searches.lmu_ltau(cls, point, True)]
        assert searches.muon_g2(cls, point, True).name == searches.G2


def _named(why: str) -> str:
    """A reason with the mediator's name taken out: the library calls its pseudoscalar S, the generic route a0."""
    import re
    return re.sub(r"\b(S|a0)'s\b", "the mediator's", why or "")


@pytest.mark.parametrize('m_chi, m_a, g_chi, g_q', [
    (0.5, 2.0, 1.0, 1.0), (0.5, 2.0, 1.0, 0.01), (0.1, 1.0, 1.0, 0.003), (0.2, 2.5, 0.05, 0.2),   # excluded
    (0.3, 0.8, 1.0, 1e-3),                                                                       # allowed
    (0.5, 2.0, 1e-3, 0.01),                                                   # a decays visibly: undecided
    (1.0, 3.5, 1.0, 1.0),                                                     # above BaBar's signal region
])
def test_the_library_alps_b_to_k_outcomes_are_reproduced_through_the_generic_route(m_chi, m_a, g_chi, g_q):
    """P4's B → K + invisible (the remainder, 2026-10-20): the library's ALP through the generic route, its quarks'
    Yukawa-like factor read from its portrait, gives the library's native outcome (decision, ratio to 1%) and its 95%
    one. Below the c c̄ threshold, where the two codes' Yukawa masses agree."""
    e = library.entry('alp_portal')
    p = e.point.model_copy(update={'m_chi': m_chi, 'm_med': m_a, 'g_chi': g_chi, 'g_q': g_q, 'g_l': g_q})
    engine, q = _generic_at('alp_portal', p)
    for evaluate in (searches._flavour_native, searches.flavour):
        theirs, ours = evaluate(e.model_class, p, True), evaluate(engine, q, True)
        assert ours.excluded == theirs.excluded and _named(ours.why)[:40] == _named(theirs.why)[:40]
        if theirs.ratio is not None:
            assert ours.ratio == pytest.approx(theirs.ratio, rel=1e-2)


def test_a_light_scalar_coupled_to_quarks_otherwise_is_undecided_by_b_to_k():
    """A light CP-odd scalar whose quark couplings are not Yukawa-like (one universal coupling, not each quark's mass
    times one factor) is undecided with the reason; a heavy one has no B → K outcome."""
    e = library.entry('alp_portal')
    p = e.point.model_copy(update={'m_chi': 0.5, 'm_med': 2.0, 'g_chi': 1.0, 'g_q': 0.01, 'g_l': 0.01})
    engine, q = _generic_at('alp_portal', p)
    spec = engine.model_spec()
    universal = spec.model_copy(update={'terms': [t.model_copy(update={'coupling': 'g_q*1e-3'})
                                                  if t.coupling == 'g_q*m_q/v' else t for t in spec.terms]})
    odd = GenericModel.for_spec(universal)
    outcome = searches._flavour_native(odd, odd.point().model_copy(update={'m_chi': q.m_chi, 'm_med': q.m_med}), True)
    assert outcome.excluded is None and 'Yukawa-like' in outcome.why
    heavy, h = _generic_at('alp_portal', e.point)
    assert searches._flavour_native(heavy, h, True) is None


# --- the tactical audit's T20-01-T20-03 (2026-10-20) -------------------------------------------------------------------

def _muon_only(spin: int, mass: float):
    from adroit.core.model_spec import ModelSpec
    spec = ModelSpec.model_validate(dict(name='muon_only', phase='broken', fields=[
        dict(name='chi', role='dark_matter', spin=.5, dark_parity=-1, mass_gev=100.),
        dict(name='X', role='mediator', spin=spin, self_conjugate=True, mass_gev=mass),
        dict(name='mu', role='standard_model', spin=.5)],
        terms=[dict(fields=[dict(field='mu', conjugate=True), dict(field='mu'), dict(field='X')],
                    lorentz='scalar' if spin == 0 else 'vector', coupling='g')], couplings=[dict(name='g', value=.001)]))
    engine = GenericModel.for_spec(spec)
    return engine, engine.point()


@pytest.mark.needs("production_tables")
def test_a_mediator_coupled_to_the_muon_alone_is_neither_higgs_nor_photon_like():
    """T20-01: the fit had used only the fermions present, so a muon-only scalar read as a heavy Higgs (53 pb of
    gluon fusion it has no top loop for) and a muon-only vector as a dark photon (an electron-beam search applied)."""
    from adroit.parameter_space.portals import generic_production as gpr
    engine, p = _muon_only(0, 300.)
    (scalar,) = gp.portraits(engine, p)
    assert scalar.pattern_residual > 0.9 and gpr.heavy_higgs_kappa(scalar) is None
    assert gpr.single(scalar).sigma_pb == 0.0
    engine, p = _muon_only(1, .3)
    (vector,) = gp.portraits(engine, p)
    assert vector.pattern_residual > 0.5 and searches._generic_dark_photons(engine, p) == []


@pytest.mark.parametrize('sine', [.001, .3, .6])
@pytest.mark.needs("production_tables")
def test_a_mixed_singlet_is_produced_as_sin_theta_squared_times_a_heavy_higgs(sine):
    """T20-02: κ is read against the unmixed Standard Model's h, so it is sin θ (the model's own h, cos θ times the
    Standard Model's, had given tan θ: 56% too much production at sin θ = 0.6). Das et al.'s field content (a
    development-half zoo model) at a 300 GeV scalar."""
    import math
    from adroit.constraints import production
    from adroit.evaluation import zoo
    from adroit.evaluation.core import Half, half_of
    from adroit.model_building.gauge_basis import V_EW
    from adroit.parameter_space.portals import generic_production as gpr
    entry = next(e for e in zoo.entries() if e.id == 'singlet_fermion_scalar_mediator_das')
    assert half_of(zoo.NAME, entry.id) is Half.development
    base = zoo._spec(entry, entry.targets[0])
    m1, m2, v, co = 125., 300., V_EW, math.sqrt(1 - sine * sine)
    values = {c.name: c.value for c in base.couplings}
    values.update(mu_hs=sine * co * (m2 * m2 - m1 * m1) / v,
                  mu_s2=m1 * m1 * sine * sine + m2 * m2 * co * co - values['lam_hs'] * v * v / 2,
                  lam_H=(m1 * m1 * co * co + m2 * m2 * sine * sine) / (2 * v * v))
    spec = base.model_copy(update={'couplings': [c.model_copy(update={'value': values[c.name]})
                                                 for c in base.couplings]})
    engine = GenericModel.for_spec(spec)
    (m,) = [x for x in gp.portraits(engine, engine.point()) if x.spin == 0]
    assert m.higgs_like == pytest.approx(sine, rel=1e-6) and gpr.heavy_higgs_kappa(m) == pytest.approx(sine, rel=1e-6)
    assert gpr.single(m).sigma_pb == pytest.approx(sine ** 2 * production.heavy_higgs_pb(m.mass_gev), rel=1e-6)


def _unresolved_vector(neutral: float, charged: float):
    """X (1 GeV) coupled to the electron, the dark matter χ (10 MeV), a neutral Z₂-odd N and a charged Z₂-odd F
    (100 MeV each), with couplings g_N and g_F."""
    from adroit.core.model_spec import ModelSpec
    fields = [dict(name='chi', role='dark_matter', spin=.5, dark_parity=-1, mass_gev=.01),
              dict(name='N', role='mediator', spin=.5, dark_parity=-1, mass_gev=.1),
              dict(name='F', role='mediator', spin=.5, dark_parity=-1, mass_gev=.1, charges=dict(electric_charge=1)),
              dict(name='X', role='mediator', spin=1, self_conjugate=True, mass_gev=1.),
              dict(name='e', role='standard_model', spin=.5)]
    used = [(f, c) for f, c, g in (('chi', 'gc', 1), ('N', 'gN', neutral), ('F', 'gF', charged), ('e', 'ge', 1)) if g]
    terms = [dict(fields=[dict(field=f, conjugate=True), dict(field=f), dict(field='X')], lorentz='vector', coupling=c)
             for f, c in used]
    values = {'gc': .01, 'gN': neutral, 'gF': charged, 'ge': .001}
    spec = ModelSpec.model_validate(dict(name='unresolved', phase='broken', fields=fields, terms=terms,
                                         couplings=[dict(name=c, value=values[c]) for _, c in used]))
    engine = GenericModel.for_spec(spec)
    (x,) = gp.portraits(engine, engine.point())
    return x


def test_a_charged_pair_is_never_invisible_and_a_neutral_one_widens_the_invisible_bounds():
    """T20-03 and the owner's decision #7 (2026-10-20): only the dark matter's and neutrinos' pairs are invisible. An
    unresolved pair of neutral, colourless states may be unseen, so it sets BR(invisible)'s upper assignment; a pair
    with a charged state is always seen and moves neither. The Standard Model pairs' share is exact; nothing is
    tolerated (the 1% share below which unresolved width counted as visible is withdrawn)."""
    x = _unresolved_vector(neutral=.05, charged=.1)
    share = {' '.join(c.final): c.width_gev / x.width_gev for c in x.channels}
    assert set(share) == {'chi0 chi0~', 'N0 N0~', 'F+ F+~', 'e e~'}       # G1's names
    charged = next(c for c in x.channels if 'F+' in c.final)
    neutral = next(c for c in x.channels if 'N0' in c.final)
    assert charged.unresolved and not charged.may_hide and neutral.unresolved and neutral.may_hide
    low, high = x.invisible_bounds()
    assert low == pytest.approx(share['chi0 chi0~'], rel=1e-12)
    assert high == pytest.approx(share['chi0 chi0~'] + share['N0 N0~'], rel=1e-12)
    assert x.visible_share() == pytest.approx(share['e e~'], rel=1e-12)
    assert x.visible_share() + high + share['F+ F+~'] == pytest.approx(1.0, rel=1e-12)
    assert 'F+ F+~' in x.unresolved_reason() and f'between {low:.3g} and {high:.3g}' in x.unresolved_reason()
    only_charged = _unresolved_vector(neutral=0.0, charged=.1)
    assert only_charged.invisible_bounds()[0] == only_charged.invisible_bounds()[1] > 0
    tiny = _unresolved_vector(neutral=1e-4, charged=0.0)                     # a share far below the old 1%
    assert 0 < tiny.unresolved_width_gev < 1e-3 * tiny.width_gev
    assert tiny.invisible_bounds()[1] > tiny.invisible_bounds()[0]


def test_a_search_is_decided_only_where_both_assignments_of_brinv_agree():
    """The owner's decision #7: the decision both extreme assignments give, from the one nearer the limit, flagged;
    pending where they differ, or where either is pending."""
    def at(excluded, ratio):
        return searches.Outcome(name='x', excluded=excluded, ratio=ratio, why=f'r={ratio}')
    why = 'X decays 0.2 of the time to new states'
    assert searches._edges([at(True, 3.0)], why) == at(True, 3.0)
    both = searches._edges([at(True, 3.0), at(True, 1.5)], why)
    assert both.excluded is True and both.ratio == 1.5 and both.flags == [f'{why}; decided alike at both']
    assert searches._edges([at(False, .2), at(False, .7)], why).ratio == .7
    split = searches._edges([at(False, .5), at(True, 2.0)], why)
    assert split.excluded is None and split.ratio is None and split.why.startswith(why)
    assert 'excludes at one assignment and allows at the other' in split.why
    assert searches._edges([at(True, 2.0), at(None, None)], why).excluded is None
    assert searches._distinct((.1, .1)) == (.1,) and searches._distinct((.1, .3)) == (.1, .3)


def test_a_photon_like_vector_with_unresolved_decays_is_judged_at_both_assignments(monkeypatch):
    """DarkCast's visible searches read the exact Standard Model share; its invisible ones decide only where both
    assignments of BR(invisible) agree (the owner's decision #7)."""
    seen = []
    def darkcast(epsilon, m, width, invisible, unverified, visible=None):
        seen.append((invisible, visible))
        return searches.Outcome(name=searches.DARK_PHOTON, excluded=invisible > .5, ratio=2 * invisible)
    monkeypatch.setattr(searches, '_darkcast', darkcast)
    monkeypatch.setattr(searches, '_generic_dark_photons', lambda cls, p: [(1e-3, .5, [(1e-6, .2, .3), (1e-6, .7, .3)], 'X decays')])
    outcome = searches._dark_photon_native(object(), None, True)
    assert seen == [(.2, .3), (.7, .3)] and outcome.excluded is None and outcome.why.startswith('X decays')
    monkeypatch.setattr(searches, '_generic_dark_photons', lambda cls, p: [(1e-3, .5, [(1e-6, .6, .3), (1e-6, .7, .3)], 'X decays')])
    outcome = searches._dark_photon_native(object(), None, True)
    assert outcome.excluded is True and outcome.ratio == pytest.approx(1.2)


def test_darkcasts_displaced_searches_need_a_dark_photon_with_standard_model_decays_alone(monkeypatch):
    """The displaced searches' limits are the minimal dark photon's lifetime: no invisible and no unresolved width."""
    from adroit.constraints import searches as s
    stems = []
    monkeypatch.setattr(s, '_blocked', lambda *args: None)
    monkeypatch.setattr(s, '_tool', lambda name: name)
    monkeypatch.setattr(s, 'darkcast_excludes', lambda stem, m, c: stems.append(stem) or False)
    monkeypatch.setattr(s, 'darkcast_ratio', lambda stem, m, c: .5)
    monkeypatch.setattr(s, 'darkcast_info', lambda stem: {'cl': .9})
    monkeypatch.setattr(searches, '_darkcast_width_gate', lambda *args, **kw: '')
    for visible, displaced in ((1.0, True), (1 - 1e-6, False)):
        stems.clear()
        searches._darkcast(1e-4, .05, 1e-12, 0.0, True, visible)
        assert bool(set(stems) & set(searches.VISIBLE_DISPLACED)) is displaced


def test_the_4mu_coupling_reads_the_standard_model_pairs_share(monkeypatch):
    """Z → 4μ's and BaBar's limits are the vanilla L_μ − L_τ's, B(μμ) among Standard Model pairs alone: the dark
    matter's and the unresolved pairs both left out, so BR(μμ)/vanilla is the Standard Model pairs' share (an unresolved
    pair counted as Standard Model had raised it)."""
    def channel(final, width, **kw):
        return gp.Channel(final=final, width_gev=width, **kw)
    x = gp.MediatorPortrait(name='X', spin=1, mass_gev=1.0, width_gev=1.0, channels=[
        channel(('mu', 'mu~'), .2), channel(('nu_mu', 'nu_mu~'), .1, invisible=True),
        channel(('chi', 'chi~'), .3, invisible=True), channel(('N', 'N~'), .4, unresolved=True, may_hide=True)],
        invisible_width_gev=.4, unresolved_width_gev=.4, dark_matter=gp.FermionCoupling(fermion='chi', even=.1, odd=0))
    monkeypatch.setattr(searches, '_generic_pattern', lambda cls, p, charges: [(.01, x)])
    (g, m, width, muons, vanilla, bounds, unknown), = searches._generic_lmu(object(), None)
    assert muons == pytest.approx(.2) and vanilla == pytest.approx(.2 / .3) and muons / vanilla == pytest.approx(.3)
    assert bounds == pytest.approx((.4, .8)) and 'between 0.4 and 0.8' in unknown

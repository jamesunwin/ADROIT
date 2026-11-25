"""G7: long-range effects in freeze-out for the generic engine, from G3's amplitudes (``portals.generic_lr``)."""

import math

import numpy as np
import pytest

from adroit.constraints import tree
from adroit.evaluation import zoo
from adroit.model_building.gauge_basis import G1, G2
from adroit.parameter_space.portals import generic as gm
from adroit.parameter_space.portals import generic_lr as lr
from adroit.parameter_space.portals import nplet

A2, AY = G2 ** 2 / (4 * math.pi), G1 ** 2 / (4 * math.pi)


def _entry(entry_id: str, k: int = 0):
    e = next(x for x in zoo.entries() if x.id == entry_id)
    engine, point = zoo._generic(e, e.targets[k])
    mb, rules, model = engine.at(point)
    return engine, point, mb, rules, model, gm.bath_states(mb, rules)


@pytest.fixture(scope="module")
def wino():
    return _entry("wino_majorana_triplet_bottaro")


def test_amplitudes_square_to_the_engines_cross_section(wino):
    """``Process.amplitudes`` keeps every colour and spin explicit: Σ|M|² averaged is ``squared``."""
    *_, model, _ = wino
    for legs in [("chi0", "chi0", "W", "W~"), ("chi+", "chi+~", "Z", "h"), ("chi0", "chi+", "W", "A")]:
        proc = tree.Process(model, *legs)
        s, cos = (2.02 * 2860.0) ** 2, np.array([-0.3, 0.2, 0.7])
        amp = proc.amplitudes(s, cos)
        average = amp.shape[0] * amp.shape[1] * amp.shape[4] * amp.shape[5]
        assert np.sum(np.abs(amp) ** 2, axis=tuple(range(8))) / average == pytest.approx(proc.squared(s, cos))


def test_the_winos_potential_is_group_theorys(wino):
    """Read from G3's W, Z and γ exchange: 2α₂, α₂ and −α₂ in I = 1, 3, 5, with 1, 3 and 5 states."""
    *_, mb, rules, model, bath = wino
    found = lr.analyse(mb, rules, model, bath)
    assert not found.refused and len(found.groups) == 1
    channels = {c.su2: c for c in found.groups[0].channels}
    assert {i: round(c.alpha_tree / A2, 6) for i, c in channels.items()} == {1: 2.0, 3: 1.0, 5: -1.0}
    assert {i: c.dim for i, c in channels.items()} == {1: 1, 3: 3, 5: 5}


def test_the_winos_hard_rates_are_mrss_channel_by_channel(wino):
    """The annihilation matrix projected on the channels and spins: MRSS's (1, 0), (5, 0) and (3, 1) rates for the
    Majorana triplet (``nplet.hard_rates``, at G2's α₂), and nothing in the others."""
    *_, mb, rules, model, bath = wino
    channels = {c.su2: c for c in lr.analyse(mb, rules, model, bath).groups[0].channels}
    m = bath[0][1]
    reference = {k: v * (A2 / nplet.alpha_2(m)) ** 2 for k, v in nplet.hard_rates(3, 0.0, m).items()}
    g2 = 6.0 ** 2                                      # the Majorana triplet's g_χ² initial states
    for (i, spin), rate in reference.items():
        assert channels[i].by_spin[spin] / g2 == pytest.approx(rate, rel=2e-3), (i, spin)
        assert channels[i].by_spin[1 - spin] / g2 < 1e-5 * rate


def test_a_scalar_pairs_potential_takes_the_sign_of_its_statistics():
    """The complex scalar triplet (Y = 1): χχ̄ attracts in I = 1 by 2α₂ + α_Y, and χχ (no Fermi sign) repels in
    I = 5 by α₂ + α_Y; χχ, which cannot annihilate, is not a group."""
    *_, mb, rules, model, bath = _entry("complex_scalar_triplet_y1_bottaro")
    found = lr.analyse(mb, rules, model, bath)
    assert not found.refused and len(found.groups) == 1
    grp = found.groups[0]
    channels = {c.su2: c.alpha_tree for c in grp.channels}
    assert channels[1] == pytest.approx(2 * A2 + AY, rel=1e-3) and channels[5] == pytest.approx(-A2 + AY, rel=1e-3)
    mults, _ = lr.multiplets(mb, bath)
    particles = next(x for x in mults if not x.anti)
    v = lr.potential(lr.heavy_copy(model), [(s, s) for s in particles.states if s.startswith("chi++")])
    assert np.real(v[0, 0]) == pytest.approx(-(A2 + AY), rel=1e-3)


def test_a_coloured_partners_channels_are_singlet_and_octet():
    """A scalar colour triplet with its antiparticle: +4/3 and −1/6 α_s from G3's gluon exchange, and the
    annihilation into gluons shared 2/7 : 5/7."""
    *_, mb, rules, model, bath = _entry("coloured_coannihilation_bsf_harz")
    grp = lr.analyse(mb, rules, model, bath).groups[0]
    alpha_s = rules.g_s ** 2 / (4 * math.pi)
    channels = {c.su3: c for c in grp.channels}
    y2 = grp.a.y ** 2
    assert channels["1"].alpha_tree == pytest.approx(4 / 3 * alpha_s + y2 * AY, rel=1e-3)
    assert channels["8"].alpha_tree == pytest.approx(-1 / 6 * alpha_s + y2 * AY, rel=1e-3)
    share = channels["1"].rate / (channels["1"].rate + channels["8"].rate)
    assert grp.bound == "colour" and share == pytest.approx(2 / 7, rel=0.05)


def test_the_channels_rates_add_up_to_the_pairs(wino):
    """Tr Γ over every state is Σ g_a g_b σv of the ordered pairs at threshold (the relic's normalisation)."""
    *_, mb, rules, model, bath = wino
    grp = lr.analyse(mb, rules, model, bath).groups[0]
    names = [b[0] for b in bath]
    m = bath[0][1]
    s = 4 * m * m / (1 - (0.5 * lr.THRESHOLD_V) ** 2)
    total = 0.0
    for a in names:
        for b in names:
            for c, d in gm.final_states(model, a, b):
                total += 4.0 * tree.Process(model, a, b, c, d).sigma(s) * lr.THRESHOLD_V
    assert sum(c.rate for c in grp.channels) == pytest.approx(total, rel=2e-3)


def test_g7_computes_the_wino_and_flags_what_it_did(wino):
    engine, point, *_ = wino
    assert engine.domain(point) == "" and engine.omega_h2(point) is not None
    assert any(f.startswith("long-range effects (G7), chi chi") and "MRSS" in f for f in engine.flags(point))


def _dark_qed(alpha: float = 0.03, m: float = 1000.0, m_v: float = 0.0):
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals.generic import GenericModel
    spec = ModelSpec.model_validate({"name": "dark_qed", "phase": "broken", "fields": [
        {"name": "X", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": m,
         "charges": {"extra": {"Ad": 1.0}}},
        {"name": "Ad", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": m_v}],
        "couplings": [{"name": "e_d", "value": math.sqrt(4 * math.pi * alpha)}],
        "terms": [{"fields": [{"field": "X", "conjugate": True}, {"field": "X"}, {"field": "Ad"}],
                   "lorentz": "vector", "coupling": "e_d"}]})
    return GenericModel.of(spec, sommerfeld=True, bound_states=True)


def test_dark_u1_capture_is_hydrogen_like():
    """σ_BSF/σ_ann → (2⁹/3)e⁻⁴ = 3.13 in the Coulomb limit (von Harling & Petraki), and E_B = mα²/4."""
    m, alpha = 1000.0, 0.03
    v = alpha / 300.0                                            # ζ = 300
    zeta = alpha / v
    annihilation = math.pi * alpha ** 2 / m ** 2 * 2 * math.pi * zeta / -math.expm1(-2 * math.pi * zeta)
    assert lr.dark_u1_capture(np.array([v]), m, alpha)[0] / annihilation == pytest.approx(2 ** 9 / 3 * math.exp(-4),
                                                                                         rel=1e-4)
    assert lr.dark_u1_capture(np.array([10.0]), m, alpha)[0] < 1e-6 * annihilation      # no capture without binding


def test_a_dark_qed_pair_forms_bound_states_that_lower_its_relic_density():
    engine = _dark_qed()
    p = engine.point()
    found = engine.long_range_effects(p)
    assert [g.bound for g in found.groups] == ["dark_u1"]
    with_bound = engine.omega_h2(p)
    without = engine.model_copy(update={"bound_states": False}).omega_h2(p)
    assert 0.3 * without < with_bound < 0.99 * without


def test_the_dark_qed_flag_names_its_bound_states():
    """The audit's G7-7 (G12): every dark-QED point had carried "bound-state formation not computed"."""
    from adroit.parameter_space.portals.generic import _long_range_flags
    engine = _dark_qed()
    found = engine.long_range_effects(engine.point())
    (flag,) = _long_range_flags(found, True)
    assert "hydrogen-like ground state" in flag and "not computed" not in flag


def test_a_massive_dark_photon_is_not_taken_as_massless():
    """Above 1% of the binding energy (mα²/4 = 0.225 GeV here) the capture is not computed."""
    engine = _dark_qed(m_v=1.0)
    assert [g.bound for g in engine.long_range_effects(engine.point()).groups] == [""]


def test_a_scalar_mediators_yukawa_force_gets_no_dark_photon_bound_states():
    """The audit's G7-4 (G12): a Dirac singlet with a light scalar mediator was tagged "dark_u1" and given vector
    dipole capture (Ωh² 3.3 times too low)."""
    import math

    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals.generic import GenericModel
    spec = ModelSpec.model_validate({"name": "yukawa", "phase": "broken", "fields": [
        {"name": "X", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 1000.0},
        {"name": "phi", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 0.001}],
        "terms": [{"fields": [{"field": "X", "conjugate": True}, {"field": "X"}, {"field": "phi"}],
                   "lorentz": "scalar", "coupling": f"{math.sqrt(4 * math.pi * 0.03)}"}]})
    engine = GenericModel.of(spec)
    found = engine.long_range_effects(engine.point())
    assert found.groups and all(g.bound != "dark_u1" for g in found.groups)


def test_a_trilinear_scalar_force_has_the_yukawa_strength_of_its_pair():
    """The audit's G3/G4-8 (G12): −μ φ*φ s acts on a φφ* pair as a Yukawa μ/(2m), α = μ²/(16π m²); it had been
    four times that."""
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals import generic_checks as gc
    from adroit.parameter_space.portals.generic import GenericModel
    m, mu = 500.0, 100.0
    spec = ModelSpec.model_validate({"name": "sss", "phase": "broken", "fields": [
        {"name": "phi", "role": "dark_matter", "spin": 0, "dark_parity": -1, "mass_gev": m},
        {"name": "s", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 1.0}],
        "couplings": [{"name": "mu", "value": mu, "mass_dimension": 1}],
        "terms": [{"fields": [{"field": "phi", "conjugate": True}, {"field": "phi"}, {"field": "s"}],
                   "lorentz": "scalar", "coupling": "-mu"}]})
    engine = GenericModel.of(spec)
    mb, rules, _ = engine.at(engine.point())
    (alpha, mass, _, spin), = gc.dark_forces(rules, mb.spectrum.dark_matter().name)
    assert alpha == pytest.approx(mu ** 2 / (16 * math.pi * m ** 2)) and mass == pytest.approx(1.0) and spin == 0


def test_a_coloured_doublets_thermal_factor_leaves_the_gluon_unscreened():
    """The audit's G7-8 (G12): in a coloured SU(2) doublet's I = 1 colour-singlet channel the W mass had screened the
    gluon's part too (⟨S⟩ 6.00 against 6.46 at x = 100). With each part's mass weighted by its α, the Hulthén average
    is within 3% of the exact solution of −(α₂λ e^{−m_W r} + α_s C)/r."""
    from adroit.constraints import sommerfeld
    from adroit.parameter_space.portals import nplet
    from adroit.parameter_space.portals.multiplet import alpha_2
    m, t = 1500.0, 15.0
    ch = lr.Channel(su2=1, su3="1", dim=1, lam=0.75, y_term=0.0, colour=4 / 3, dark=[])
    v = np.minimum(np.sqrt(4.0 * t * nplet._Y_GRID / m), 1.0)
    a2 = alpha_2(nplet.potential_scale(m)) * ch.lam
    colour = lr.channel_alpha(ch, m, v) - a2
    exact = []
    for vi, ac in zip(v[::8], colour[::8]):
        mu, k = m / 2, m / 2 * vi
        amplitude = sommerfeld.enhancement(lambda r, ac=ac: np.array([[-(a2 * math.exp(-80.377 * r) + ac) / r]]),
                                           np.array([0.0]), np.array([ac]), mu, 0.25 * m * vi * vi,
                                           r_max=max(30 / 80.377, 6 / k))
        exact.append(abs(amplitude[0, 0]) ** 2)
    average = float(np.trapezoid(nplet._WEIGHT * np.interp(v, v[::8], exact), nplet._Y_GRID))
    assert lr.thermal_factor(ch, m, t) == pytest.approx(average, rel=0.03)


def test_a_split_groups_correction_takes_each_states_own_weight():
    """The audit's G7-10 (G12): a group whose two states are split by 2% shares its correction by the states' own
    densities, ⟨ρ̂⟩²/ρ̂₀²; a degenerate group's share is 1."""
    from scipy.special import kve
    from types import SimpleNamespace as NS
    m, split = 1000.0, 1.02
    t = np.array([40.0, 20.0, 1.0])                                     # x = 25, 50, 1000

    def group(m2):
        multiplet = NS(states=["a0", "a1"])
        return NS(a=multiplet, b=multiplet), [("a0", m, 2.0), ("a1", m2, 2.0)]
    assert np.allclose(lr.boltzmann_share(*group(m))(t), 1.0)
    density = [x ** 2 * kve(2, x / t) * np.exp(-(x - m) / t) for x in (m, split * m)]
    expected = (0.5 * (density[0] + density[1])) ** 2 / density[0] ** 2
    assert np.allclose(lr.boltzmann_share(*group(split * m))(t), expected, rtol=1e-12)
    assert lr.boltzmann_share(*group(split * m))(t)[0] == pytest.approx(0.25 * (1 + 1.02 ** 1.5 * math.exp(-0.5)) ** 2,
                                                                         rel=0.02)

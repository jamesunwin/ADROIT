"""General electroweak n-plets (the owner, 2026-10-13): the symmetric-limit engine against the papers it follows."""

import math

import numpy as np
import pytest

from adroit.core.model_spec import Charges, FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm, Occurrence, Phase
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals import nplet


def _unit(m: float) -> float:
    return math.pi * nplet.alpha_2(m) ** 2 / m ** 2


def test_the_majorana_channels_sum_to_mitridate_et_al_and_split_as_they_do():
    m = 1000.0
    for n, total, split in ((3, 37 / 12, {(1, 0): 16 / 111, (5, 0): 20 / 111, (3, 1): 75 / 111}),
                            (5, 207 / 20, {(1, 0): 16 / 69, (5, 0): 28 / 69, (3, 1): 25 / 69})):
        rates = nplet.hard_rates(n, 0.0, m)
        assert sum(rates.values()) / _unit(m) == pytest.approx(total)                  # MRSS eq. (17)
        for channel, fraction in split.items():                                         # MRSS eqs. (85), (89)
            assert rates[channel] / sum(rates.values()) == pytest.approx(fraction)


@pytest.mark.parametrize("n,y", [(3, 1.0), (4, 0.5), (5, 1.0), (6, 0.5)])
def test_the_dirac_channels_sum_to_cirelli_strumia_and_tamburini(n, y):
    """CST eq. (39)'s s-wave: c_s = g_X(C₁ + C₂)/8πn + g_X[(3g₂⁴(n²−1) + 20g_Y⁴Y²)/16π + (g₂⁴(n²−1) + 4g_Y⁴Y²)/128π],
    ⟨σv⟩ = c_s/2g_X²M² with g_X = 4n (their eqs. (41)–(43))."""
    m = 2000.0
    g2, gy = 4 * math.pi * nplet.alpha_2(m), 4 * math.pi * nplet.alpha_y(m)          # g², not g
    c1 = gy ** 2 * n * y ** 4 + g2 * gy * y * y * n * (n * n - 1) / 2 + g2 ** 2 * n * (n * n - 1) ** 2 / 16
    c2 = gy ** 2 * n * y ** 4 + g2 * gy * y * y * n * (n * n - 1) / 2 + g2 ** 2 * n * (n * n - 1) * (n * n - 5) / 16
    gx = 4 * n
    c_s = gx * (c1 + c2) / (8 * math.pi * n) + gx * ((3 * g2 ** 2 * (n * n - 1) + 20 * gy ** 2 * y * y) / (16 * math.pi)
                                                   + (g2 ** 2 * (n * n - 1) + 4 * gy ** 2 * y * y) / (128 * math.pi))
    assert sum(nplet.hard_rates(n, y, m).values()) == pytest.approx(c_s / (2 * gx ** 2 * m ** 2), rel=1e-10)


def _spin(n):
    j = (n - 1) / 2
    m = np.arange(j, -j - 1, -1)
    jp = np.zeros((n, n))
    for k in range(1, n):
        jp[k - 1, k] = math.sqrt(j * (j + 1) - m[k] * (m[k] + 1))
    return [(jp + jp.T) / 2, (jp - jp.T) / 2j, np.diag(m)]


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_the_group_factor_is_mitridate_et_al_eq_48_for_every_transition(n):
    """Σ_{aMM'}|C_J + γC_T|² computed from the Clebsch–Gordan coefficients of n ⊗ n̄ (MRSS eqs. (48a,b))."""
    t = _spin(n)
    total = [np.kron(a, np.eye(n)) + np.kron(np.eye(n), -a.conj()) for a in t]
    w, v = np.linalg.eigh(sum(x @ x for x in total))
    sectors = {i: [v[:, k].reshape(n, n) for k in np.where(np.isclose(w, (i * i - 1) / 4))[0]]
               for i in range(1, 2 * n, 2)}
    eps = np.zeros((3, 3, 3))
    for a, b, c, sign in ((0, 1, 2, 1), (1, 2, 0, 1), (2, 0, 1, 1), (0, 2, 1, -1), (2, 1, 0, -1), (1, 0, 2, -1)):
        eps[a, b, c] = sign
    for i_i in sectors:
        for i_f in (i_i - 2, i_i + 2):
            if i_f not in sectors:
                continue
            for gamma in (0.0, 0.4, -0.7):
                direct = sum(abs(0.5 * (np.einsum("ij,kj,ki->", cm, cp.conj(), t[a])
                                        + np.einsum("ij,il,lj->", cm, cp.conj(), t[a].conj()))
                                 + gamma * 1j * sum(eps[a, b, c] * np.einsum("ij,kl,ki,jl->", cm, cp.conj(), t[b], t[c])
                                                    for b in range(3) for c in range(3))) ** 2
                             for cm in sectors[i_i] for cp in sectors[i_f] for a in range(3))
                assert nplet.group_factor(n, i_i, i_f, gamma) == pytest.approx(direct, abs=1e-9)
    assert nplet.group_factor(5, 3, 1, 0.5) == pytest.approx(6 * 1.5 ** 2)               # MRSS Table 1: 6|1 ± γ|²


def test_the_bound_state_widths_are_mitridate_et_al_table_91():
    m = 10000.0
    a2 = nplet.alpha_2(m)
    rates = nplet.hard_rates(5, 0.0, m)
    for (i, s, lam_f), coefficient in (((1, 0, 6), 3240), ((3, 1, 5), 15625 / 48), ((5, 0, 3), 567 / 4)):
        width = nplet.annihilation_width(rates[(i, s)], 10, i, s, lam_f * a2, m)
        assert width == pytest.approx(coefficient * a2 ** 5 * m, rel=1e-12)
    wino = nplet.annihilation_width(nplet.hard_rates(3, 0.0, m)[(1, 0)], 6, 1, 0, 2 * a2, m)
    assert wino == pytest.approx(8 * a2 ** 5 * m, rel=1e-12)                             # MRSS p. 26


def test_repulsive_capture_neither_overflows_nor_divides_inf_by_inf():
    zeta = np.array([-50.0, -5.0, 0.5, 50.0])
    for shape in (nplet.shape_1s(zeta, np.full(4, 30.0)), nplet.shape_2s(zeta, np.full(4, 30.0))):
        assert np.all(np.isfinite(shape)) and np.all(shape >= 0) and shape[0] < shape[-1]


def test_the_sommerfeld_only_masses_follow_bottaro_et_al_figure_1():
    """BB21 Fig. 1 (digitised, ±2%): the 5- and 7-plets with the Sommerfeld effect alone."""
    assert nplet.thermal_mass(5, 0.0, bound_states=False) / 1e3 == pytest.approx(9.33, rel=0.05)
    assert nplet.thermal_mass(7, 0.0, bound_states=False) / 1e3 == pytest.approx(22.2, rel=0.05)


@pytest.mark.slow
@pytest.mark.parametrize("n,y,published,at_m", [(3, 1.0, 2.85, None), (4, 0.5, 4.8, None), (5, 0.0, 13.6, 0.05),
                                                 (5, 1.0, 9.9, 0.05)])
def test_the_thermal_masses_are_bottaro_et_al_tables(n, y, published, at_m):
    """BB21 and BB22 Table I, with the Sommerfeld effect and bound states: within 15% with the potentials' couplings
    at the inverse Bohr radius (MRSS's choice, the default). For the 5-plets, within 5% with them at M (a scale
    Bottaro et al. do not state; the spread is the engine's theory uncertainty). The 3₁ and 4₁/₂ come out 6–9% low
    at either scale: Bottaro et al. compute their Sommerfeld effect in the broken phase (n < 6)."""
    from unittest import mock
    assert nplet.thermal_mass(n, y) / 1e3 == pytest.approx(published, rel=0.15)
    if at_m:
        with mock.patch.object(nplet, "potential_scale", lambda m: m):
            nplet._states.cache_clear()
            assert nplet.thermal_mass(n, y) / 1e3 == pytest.approx(published, rel=at_m)
        nplet._states.cache_clear()


def test_the_owners_quintuplet_is_underabundant_at_6_tev():
    assert 0.04 < nplet.omega_h2(5, 1.0, 6000.0) < 0.07


def test_direct_detection_matches_the_winos_value_and_the_hypercharge_cancellation():
    sigma, _ = nplet.sigma_si(3, 0.0)
    assert sigma == pytest.approx(2.3e-47, rel=0.15)                         # ADROIT's wino (Hisano et al.)
    assert nplet.sigma_si(5, 1.0)[0] < nplet.sigma_si(5, 0.0)[0] / 3          # Z loops cancel part of the W loops
    cls = nplet.ElectroweakNplet(n=5, hypercharge=1.0)
    assert cls.dd_channels(Point(m_chi=9900.0, m_med=1.0, g_q=2.2e-4))[0].amplitude_uncertainty == 1.0


def test_the_engine_refuses_what_it_does_not_validate():
    point = Point(m_chi=10000.0, m_med=1.0, g_q=0.0)
    assert "n = 7" in nplet.ElectroweakNplet(n=7).domain(point)
    assert nplet.ElectroweakNplet(n=7).omega_h2(point) is None
    assert "Y = 1.5" in nplet.ElectroweakNplet(n=4, hypercharge=1.5).domain(point)
    assert "1000" in nplet.ElectroweakNplet(n=5).domain(point.model_copy(update={"m_chi": 500.0}))
    dirac = nplet.ElectroweakNplet(n=5, hypercharge=1.0)
    assert "δm₀ is not stated" in dirac.pending(point)[0]
    assert dirac.pending(point.model_copy(update={"g_q": 1e-3})) == []


def test_annihilation_today_leaves_the_indirect_searches_undecided():
    from adroit.parameter_space import searches
    from adroit.parameter_space.scan import evaluate
    cls, point = nplet.ElectroweakNplet(n=5, hypercharge=1.0), Point(m_chi=9900.0, m_med=1.0, g_q=1e-3)
    assert searches.today_unknown(cls, point)
    for evaluator in (searches.cmb, searches.lines, searches.antiprotons):
        outcome = evaluator(cls, point, True)
        assert outcome is None or (outcome.excluded is None and "broken-phase" in outcome.why)
    result = evaluate(cls, point, unverified=True)
    assert result.excluded["gamma rays (Fermi-LAT dwarfs)"] is None


def test_a_majorana_nplets_lines_are_decided_by_the_resummed_rate():
    """Its other annihilation today is not computed, but its γ-ray lines are (``endpoint_nll``, 1–100 TeV): the line
    search compares them; below 1 TeV it stays undecided."""
    from adroit.constraints import endpoint_nll
    from adroit.parameter_space import searches
    cls = nplet.ElectroweakNplet(n=5)
    point = Point(m_chi=13600.0, m_med=1.0, g_q=0.0)
    assert searches.today_unknown(cls, point)
    outcome = searches.lines(cls, point, True)
    assert outcome.value == pytest.approx(endpoint_nll.line_sigma_v(5, 13600.0), rel=1e-9)
    assert "broken-phase" not in outcome.why
    low = searches.lines(cls, Point(m_chi=800.0, m_med=1.0, g_q=0.0), True)
    assert low.excluded is None and "broken-phase" in low.why


def _quintuplet(**changes) -> ModelSpec:
    fields = [ModelField(name=n, role=FieldRole.dark_matter, spin=0.5, chirality="L", mass_gev=6000.0, dark_parity=-1,
                         charges=Charges(su2=5, hypercharge=y)) for n, y in (("F5P", 1.0), ("F5M", -1.0))]
    coupling = ModelCoupling(name="m2", mass_dimension=1, value=changes.get("mass_value"))
    terms = [ModelTerm(fields=[Occurrence(field="F5P"), Occurrence(field="F5M")], lorentz="chiral", coupling="m2",
                       plus_hc=True)]
    return ModelSpec(name="quintuplet", phase=Phase.unbroken, fields=fields, couplings=[coupling], terms=terms)


def test_the_mapper_reads_a_vectorlike_weyl_pair_as_one_dirac_nplet():
    from adroit.parameter_space.classify import Unsupported, classify
    cls, point, _ = classify(_quintuplet())
    assert isinstance(cls, nplet.ElectroweakNplet) and (cls.n, cls.hypercharge) == (5, 1.0) and point.m_chi == 6000.0
    assert isinstance(classify(_quintuplet(mass_value=6000.0))[0], nplet.ElectroweakNplet)
    with pytest.raises(Unsupported, match="differs from the fields' mass"):
        classify(_quintuplet(mass_value=5000.0), generic_route=False)


def test_the_mapper_sends_the_wino_and_the_higgsino_to_their_broken_phase_engine():
    from adroit.parameter_space.classify import Unsupported, classify
    from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet

    def single(su2, y, majorana):
        dm = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, self_conjugate=majorana, mass_gev=2000.0,
                        dark_parity=-1, charges=Charges(su2=su2, hypercharge=y))
        return ModelSpec(name="x", phase=Phase.unbroken, fields=[dm])
    assert classify(single(3, 0.0, True))[0] == ElectroweakMultiplet(name="wino", multiplet="wino")
    assert classify(single(2, 0.5, False))[0].multiplet == "higgsino"
    assert classify(single(3, 1.0, False))[0].n == 3
    with pytest.raises(Unsupported, match="no neutral member"):
        classify(single(2, 1.5, False), generic_route=False)
    with pytest.raises(Unsupported, match="must be real"):
        classify(single(4, 0.0, True), generic_route=False)

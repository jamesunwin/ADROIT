"""DM7: the spin-1 completions, their annihilation and the relic density."""

from __future__ import annotations

import math

import numpy as np
import pytest
import yaml

from adroit.constraints import amplitudes, annihilation, relic, spin1

DIGITISED = "adroit/constraints/data/digitised/cms_2405.13778_spin1.yaml"


# --- the explicit amplitudes -----------------------------------------------------------

def test_spinors_solve_the_dirac_equation() -> None:
    p3 = np.array([[0.3, -0.2, 1.1]])
    m = 0.7
    p = np.concatenate([[np.sqrt(m * m + np.sum(p3 ** 2))], p3[0]])[None]
    for xi in amplitudes._BASIS:
        u = amplitudes.spinor_u(p3, m, xi)[0]
        v = amplitudes.spinor_v(p3, m, xi)[0]
        assert np.allclose((amplitudes.slash(p)[0] - m * np.eye(4)) @ u, 0)
        assert np.allclose((amplitudes.slash(p)[0] + m * np.eye(4)) @ v, 0)


def test_polarisations_are_complete() -> None:
    m_v = 3.0
    k = np.array([[5.0, 4.0 * math.sin(0.4), 0.0, 4.0 * math.cos(0.4)]])
    k[0, 0] = math.sqrt(m_v ** 2 + 16.0)
    total = sum(np.outer(e[0], e[0]) for e in amplitudes.polarisations(k, m_v))
    metric = np.diag(amplitudes.METRIC)
    assert np.allclose(total, -metric + np.outer(k[0], k[0]) / m_v ** 2)


@pytest.mark.parametrize("chi,f", [((1.0, 0.0), (0.25, 0.0)), ((0.0, 1.0), (0.0, 0.25)),
                                   ((1.0, 0.0), (0.05, -0.05)), ((0.0, 1.0), (0.05, -0.05)),
                                   ((0.3, 0.7), (0.2, 0.4))])
@pytest.mark.parametrize("m,m_f,m_med,s", [(200.0, 172.5, 1000.0, 4 * 230.0 ** 2),
                                           (50.0, 4.7, 90.0, 4 * 60.0 ** 2),
                                           (500.0, 172.5, 300.0, 4 * 700.0 ** 2)])
def test_the_analytic_s_channel_equals_the_explicit_amplitude(chi, f, m, m_f, m_med, s) -> None:
    explicit = amplitudes.s_channel_sigma(s, m, m_f, chi, f, m_med, 5.0, colours=3)
    analytic = annihilation.fermion_pair_sigma(np.array([s]), m, m_f, 3, chi, f, m_med, 5.0)[0]
    assert explicit == pytest.approx(analytic, rel=1e-6)


@pytest.mark.parametrize("chi", [(1.0, 0.0), (0.0, 1.0)])
def test_mediator_pairs_have_the_working_groups_s_wave(chi) -> None:
    """arXiv:1703.05703, eqs. 3.7–3.8: σv → g⁴ β (m² − M²)/(4π (M² − 2m²)²)."""
    m, m_med, p = 1000.0, 300.0, 0.5
    s = 4 * (m * m + p * p)
    v = 2 * p / math.sqrt(s / 4)
    reference = math.sqrt(1 - (m_med / m) ** 2) * (m * m - m_med ** 2) / (4 * math.pi * (m_med ** 2 - 2 * m * m) ** 2)
    assert amplitudes.pair_sigma(s, m, m_med, chi) * v == pytest.approx(reference, rel=1e-3)


def test_axial_mediator_pairs_carry_a_p_wave() -> None:
    m, m_med = 1000.0, 300.0
    low, high = [amplitudes.pair_sigma(4 * (m * m + p * p), m, m_med, (0.0, 1.0)) * 2 * p / math.sqrt(m * m + p * p)
                 for p in (0.5, 50.0)]
    assert high > low * 1.01


# --- the models ------------------------------------------------------------------------

def test_widths_follow_the_working_group() -> None:
    """arXiv:1703.05703, eqs. 2.4–2.11, and its statement that V2 and A2 are at most 3.2% wide."""
    m_med = 1000.0
    z = (172.5 / m_med) ** 2
    vector_top = spin1.partial_width(m_med, 172.5, 3, 0.25, 0.0)
    assert vector_top == pytest.approx(0.25 ** 2 * m_med / (4 * math.pi) * math.sqrt(1 - 4 * z) * (1 + 2 * z))
    axial_top = spin1.partial_width(m_med, 172.5, 3, 0.0, 0.25)
    assert axial_top == pytest.approx(0.25 ** 2 * m_med / (4 * math.pi) * (1 - 4 * z) ** 1.5)
    assert spin1.partial_width(m_med, 0.0, 1, 0.05, -0.05) == pytest.approx(0.1 ** 2 * m_med / (24 * math.pi))
    for name in ("V2", "A2"):
        assert spin1.width(spin1.benchmark(name, m_med), 1.0) / m_med <= 0.0325


def test_gauge_invariance_fixes_the_neutrino_coupling() -> None:
    assert spin1.benchmark("V2", 500.0).g_nu == 0.01
    assert spin1.benchmark("A2", 500.0).g_nu == -0.1


@pytest.mark.parametrize("name", ["V1", "A1", "V2", "A2"])
@pytest.mark.parametrize("m_med,m_dm", [(1000.0, 100.0), (2000.0, 10.0), (500.0, 1000.0)])
def test_the_library_route_gives_the_working_groups_cross_section(name, m_med, m_dm) -> None:
    """DM7 gate, item 2: the card, the rate conventions and arXiv:1603.04156 agree to 1%."""
    model = spin1.benchmark(name, m_med)
    assert spin1.nucleon_cross_section_cm2(model, m_dm) == pytest.approx(
        spin1.working_group_cross_section_cm2(model, m_dm), rel=0.01)


def test_the_cards_are_the_library_mediators() -> None:
    card, values = spin1.card_values(spin1.benchmark("V1", 1000.0))
    assert card == "M_vector" and values["gV_p"] == values["gV_n"] == pytest.approx(0.75)
    card, values = spin1.card_values(spin1.benchmark("A1", 1000.0))
    assert card == "M_axial" and values["gA_p"] == pytest.approx(0.25 * 0.32)


# --- annihilation ----------------------------------------------------------------------

def test_s_wave_limits_are_the_working_groups() -> None:
    """arXiv:1703.05703, eqs. 3.3 (vector) and 3.4 (axial), for annihilation to b quarks."""
    m, m_med, m_b = 60.0, 500.0, 4.7
    width = 10.0
    beta = 0.5e-3
    s = 4 * m * m / (1 - beta ** 2)
    v = 2 * beta
    bw = (m_med ** 2 - 4 * m * m) ** 2 + (m_med * width) ** 2
    root = math.sqrt(1 - (m_b / m) ** 2)
    vector = annihilation.fermion_pair_sigma(np.array([s]), m, m_b, 3, (1, 0), (0.25, 0), m_med, width)[0] * v
    axial = annihilation.fermion_pair_sigma(np.array([s]), m, m_b, 3, (0, 1), (0, 0.25), m_med, width)[0] * v
    assert vector == pytest.approx(3 * 0.25 ** 2 * root * (2 * m * m + m_b ** 2) / (2 * math.pi * bw), rel=1e-4)
    assert axial == pytest.approx(3 * 0.25 ** 2 * root * m_b ** 2 * (4 * m * m - m_med ** 2) ** 2
                                  / (2 * math.pi * m_med ** 4 * bw), rel=1e-4)


def test_mediator_pairs_open_in_the_thermal_tail() -> None:
    model = spin1.benchmark("A1", 840.0)
    below, above = (4 * 809.0 ** 2) * 1.01, (2 * 845.0) ** 2
    assert annihilation.to_mediator_pairs(np.array([below]), model, 809.0)[0] == 0.0
    assert annihilation.to_mediator_pairs(np.array([above]), model, 809.0)[0] > 0.0


def test_sigma_v_today_names_every_channel() -> None:
    channels = annihilation.sigma_v_today(spin1.benchmark("V1", 1000.0), 300.0)
    assert set(channels) == {f.name for f in spin1.FERMIONS} | {"Z'Z'"}
    assert channels["t"] > channels["e"] == 0.0


# --- the relic density -----------------------------------------------------------------

def test_degrees_of_freedom_at_the_ends() -> None:
    """Saikawa & Shirai's equation of state: 10.55 at 1 MeV (their table: 10.53, the neutrinos starting to decouple)
    and 104.1 at 10 TeV (the electroweak plasma's interactions, below the ideal gas's 106.75)."""
    assert relic.degrees_of_freedom(1e-3)[0] == pytest.approx(10.55, rel=2e-3)
    assert relic.degrees_of_freedom(1e4)[0] == pytest.approx(104.13, rel=2e-3)


def test_the_equation_of_state_is_saikawa_and_shirais_fit() -> None:
    """arXiv:1803.01038, App. C: today g*ρ → 3.383 and g*s → 3.931 (their eq. C.3, C.4); the two fits meet at 120 MeV;
    lattice QCD lies below the ideal gas through the crossover (the reason for the change, 2026-10-19)."""
    g, h = relic.saikawa_shirai(1e-7)
    assert g == pytest.approx(3.383, abs=1e-3) and h == pytest.approx(3.931, abs=1e-3)
    below, above = relic.saikawa_shirai(0.12 * (1 - 1e-9)), relic.saikawa_shirai(0.12)
    assert below[0] == pytest.approx(above[0], rel=1e-3) and below[1] == pytest.approx(above[1], rel=1e-3)
    for t in (0.2, 0.3, 0.5):
        assert relic.saikawa_shirai(t)[0] < relic.ideal_gas(t)[0]


def test_the_thermal_average_of_an_s_wave_is_flat() -> None:
    m, a = 100.0, 1e-9
    u = relic.energy_grid(m)
    beta = np.sqrt(np.clip(1 - 1 / (1 + u) ** 2, 1e-300, None))
    sigma = a / (2 * beta)
    averages = relic.thermal_average(u, sigma, np.array([500.0, 2000.0]))
    assert averages == pytest.approx([a, a], rel=0.01)


def test_the_canonical_cross_section_gives_the_observed_abundance() -> None:
    """σv ≈ 2.2 × 10⁻²⁶ cm³/s gives Ωh² ≈ 0.12 for self-conjugate dark matter; Dirac needs twice it."""
    m = 100.0
    a = 2.2e-26 / annihilation.GEV2_TO_CM3_S

    def sigma(s: np.ndarray) -> np.ndarray:
        return a / (2 * np.sqrt(np.clip(1 - 4 * m * m / s, 1e-300, None)))
    majorana = relic.omega_h2(sigma, m, dirac=False)
    dirac = relic.omega_h2(sigma, m, dirac=True)
    # with g = 2 for a Majorana fermion Ωh² = 0.114 (the release audit found that g = 4 had made it 3.7% high);
    # the bath path, which always counted g = 2, agrees
    assert majorana == pytest.approx(0.12, rel=0.07)
    assert majorana == pytest.approx(relic.omega_h2_single(sigma, m, 0.5, True), rel=1e-3)
    assert dirac == pytest.approx(2 * majorana, rel=0.05)


def test_a_point_on_cms_relic_contour() -> None:
    """V1 at (m_med, m_DM) = (1000, 100) GeV lies near CMS's Ωh² = 0.12 contour (docs/dm7)."""
    assert annihilation.omega_h2(spin1.benchmark("V1", 1000.0), 100.0) == pytest.approx(0.13, rel=0.1)


# --- the digitised summary -------------------------------------------------------------

def test_the_monojet_records_reproduce_cms_table_2() -> None:
    """DM7 gate, item 3: m_Z′ > 1.95 TeV for V1 and A1 (arXiv:2405.13778, Table 2), within 3%."""
    record = yaml.load(open(DIGITISED), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    for name in ("V1", "A1"):
        searches = record["panels"][name]["searches"]
        (monojet,) = [v for k, v in searches.items() if "j/V(qq)" in k]
        reach = max(p[0] for line in monojet["observed"] for p in line)
        assert reach == pytest.approx(1950.0, rel=0.03)


def test_a_non_finite_rate_is_named_not_left_to_the_integrator():
    x = np.geomspace(1.0, 2e4, 140)
    sigma_v = np.full_like(x, 2e-9)
    sigma_v[40] = np.nan
    with pytest.raises(ValueError, match="not finite"):
        relic.freeze_out(1000.0, x, sigma_v)


@pytest.mark.parametrize("m,sigma_v", [(80.0, 2.2e-9), (0.05, 5e-8)])
def test_particle_and_antiparticle_together_are_twice_one_species(m, sigma_v):
    """The change of variables behind D31 (the external audit's A11, 2026-10-16): with equal populations n = 2n_φ, so
    the total obeys the one-species equation with ⟨σv⟩/2 and degeneracy 2 and its yield is exactly twice the
    one-species yield (degeneracy 1, ⟨σv⟩). Keeping g = 2 in both, as D31's first diagnostic did, gives about 1.94."""
    x = np.geomspace(1.0, 2e4, 140)
    sv = np.full_like(x, sigma_v)
    def y(rate, g):
        return relic.freeze_out(m, x, rate, log_yeq=lambda t: relic.log_equilibrium_yield(t, m, g))
    # exact in the equations; the two numerical solutions agree to the integrator's precision (2.6e-5 at 80 GeV with
    # Saikawa & Shirai's degrees of freedom, 2026-10-19), far from the 3% of the wrong degeneracy below
    assert y(sv / 2, 2.0) / y(sv, 1.0) == pytest.approx(2.0, rel=5e-5)
    assert abs(y(sv / 2, 2.0) / y(sv, 2.0) - 2.0) > 0.03


def test_the_decoupled_history_reaches_todays_radiation():
    """Below the e± annihilation, g_eff = 2 + (7/8)·6·(4/11)^{4/3} = 3.363 and h_eff = 2 + (7/8)·6·(4/11) = 3.909 (the
    audit's 3.36264 and 3.90909); above 1 MeV the two histories are the same table."""
    g, h, _ = relic.decoupled_neutrinos(1e-5)
    assert g == pytest.approx(3.3626, rel=2e-3) and h == pytest.approx(3.9091, rel=2e-3)
    assert relic.decoupled_neutrinos(2e-3) == relic.degrees_of_freedom(2e-3)
    assert relic.degrees_of_freedom(1e-5)[0] == pytest.approx(10.545, rel=1e-3)         # the table held at 1 MeV


def _constant(m, sigma_v):
    species = relic.dark_matter(m, 0.0, True)
    return lambda: relic.omega_h2_rate(species, lambda temperature: np.full_like(temperature, sigma_v))


def test_a_relic_density_set_below_one_mev_is_pending():
    """The external audit's A06 (2026-10-16): a 200 keV scalar with a constant rate had Ωh² 0.128 with the table held
    at 1 MeV against 0.207 with the late-temperature degrees of freedom; it now carries a reason."""
    omega = _constant(2e-4, 3.0e-9)
    assert relic.thermal_history_reason(omega, 2e-4)
    held = omega()
    with relic.low_temperature_history():
        moved = omega()
    assert abs(moved / held - 1) > relic.LOW_T_SENSITIVITY


@pytest.mark.parametrize("m", [100.0, 1.0])
def test_a_relic_density_set_above_one_mev_is_not(m):
    """A WIMP, and a 1 GeV relic whose annihilation has stopped well before 1 MeV, keep their decision."""
    assert relic.thermal_history_reason(_constant(m, 2.2e-9), m) == ""


# --- a Boltzmann solve that stops short is never read as a relic (the physics-extensions verdict study) ----------------

def test_a_stiff_resonant_solve_is_completed_not_read_where_it_stopped():
    """The vector Higgs portal at λ = 10 just below m_h/2: BDF's step underflowed at x ≈ 4 at some masses and the
    yield there, still at equilibrium, had been taken as the relic (Ωh² ≈ 10⁷ beside 0.13). Retried (Radau), the
    curve is smooth through those masses."""
    from adroit.parameter_space import library
    e = library.entry('higgs_portal_vector')
    def omega(m):
        return e.model_class.omega_h2(e.point.model_copy(update={'m_chi': m, 'm_med': 125.09, 'g_chi': 10.0,
                                                                 'g_q': 0.25}))
    values = [omega(m) for m in (48.0, 49.0, 49.79674901159337, 50.5)]
    assert all(0.05 < v < 0.3 for v in values) and values == sorted(values, reverse=True)


@pytest.mark.needs("diamx", "solar_model")
def test_an_integration_that_never_reaches_the_end_is_unresolved(monkeypatch):
    """Every attempt stopping short raises RelicUnresolved; the scan records it as the relic density's pending reason
    (never a number)."""
    import pytest
    from types import SimpleNamespace
    from adroit.constraints import relic
    failing = SimpleNamespace(success=False, message="synthetic failure", t=np.array([3.0]), y=np.array([[-5.0]]))
    monkeypatch.setattr(relic, "_boltzmann", lambda *a, **k: failing)
    with pytest.raises(relic.RelicUnresolved, match="synthetic failure"):
        relic.freeze_out(100.0, np.geomspace(1, 2e4, 140), np.full(140, 2e-9))
    from adroit.parameter_space import scan
    from adroit.parameter_space.classes import Point, Spin1Class
    result = scan.evaluate(Spin1Class(), Point(m_chi=100.0, m_med=1000.0, g_chi=1.0, g_q=0.25), False)
    assert result.omega_h2 is None and any("could not be integrated" in x for x in result.pending)


def test_a_tables_zero_temperature_row_is_its_low_temperature_hold(tmp_path) -> None:
    """The tactical audit's T20-10: micrOMEGAs' DHS table ends with a T = 0 row; it is the hold below the lowest
    temperature, not a point whose logarithm is taken (that gave NaN and refused a 100 MeV solve)."""
    import math
    import numpy as np
    temperatures = np.geomspace(1e4, 1.99526e-5, 60)
    h = np.interp(np.log(temperatures), np.log([1.99526e-5, 1e-3, 0.2, 1e4]), [3.93872, 10.7, 60.0, 106.75])
    rows = np.column_stack([np.append(temperatures, 0.0), np.append(h, h[-1]), np.append(h * 0.97, h[-1] * 0.97)])
    table = tmp_path / "with_zero.thg"
    np.savetxt(table, rows)
    dof = relic.tabulated_dof(table)
    for t in (3e-5, 2e-5, 1e-5, 1e-7, 0.0, 2e4):
        assert all(math.isfinite(v) for v in dof(t)), t
    g, h_low, root = dof(1e-6)
    assert (g, h_low) == pytest.approx((h[-1] * 0.97, h[-1])) and root == pytest.approx(h_low / math.sqrt(g))
    x = np.geomspace(3, 2e4, 100)                        # to twice the endpoint, as every route's (AL7-02)
    with relic.equation_of_state(dof):
        assert math.isfinite(relic.freeze_out(0.1, x, np.full_like(x, 2e-9), dirac=False))
    np.savetxt(table, np.column_stack([temperatures, h, -h]))
    with pytest.raises(ValueError, match="not a table"):
        relic.tabulated_dof(table)

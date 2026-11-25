"""The neutrino fog (O'Hare's construction): fluxes, rates, the discovery statistic, its three regimes, the floor
and the published curves."""
import math

import numpy as np
import pytest
from scipy.special import erf

from adroit.physics import neutrino_fog as nf


def test_the_fluxes_are_ohares_with_their_uncertainties_scaled_or_replaced():
    by_name = {f.name: f for f in nf.FLUXES}
    assert len(nf.FLUXES) == 15 and by_name['8B'].uncertainty == 0.02 and by_name['Atm'].uncertainty == 0.25
    chosen = {f.name: f for f in nf.fluxes(nf.FogSettings(group_scale={'solar': 0.1}, uncertainties={'Atm': 0.1},
                                                          exclude=['Reactor']))}
    assert chosen['8B'].uncertainty == pytest.approx(0.002) and chosen['Atm'].uncertainty == 0.1
    assert 'Reactor' not in chosen and chosen['DSNB'].uncertainty == 0.5
    with pytest.raises(ValueError, match='unknown flux or group'):
        nf.fluxes(nf.FogSettings(group_scale={'cosmic': 2.0}))


def test_a_lines_recoils_end_at_its_kinematic_limit_and_scale_as_the_weak_charge():
    pep = next(f for f in nf.FLUXES if f.name == 'pep')
    m_n_kev = nf.AMU_GEV * 131 * 1e6
    end = 2 * (pep.endpoint_mev * 1e3) ** 2 / m_n_kev
    below, above = nf.cevns_density(np.array([0.5 * end, 1.01 * end]), pep, 77, 54)
    assert below > 0 and above == 0
    # at E_r → 0 the rate per tonne is Q_W² m_N × (nuclei per tonne) ∝ Q_W²
    low = np.array([1e-9])
    ratio = nf.cevns_density(low, pep, 77, 54)[0] / nf.cevns_density(low, pep, 22, 18)[0]
    q_xe, q_ar = 77 - (1 - 4 * nf.SIN2_THETA_W) * 54, 22 - (1 - 4 * nf.SIN2_THETA_W) * 18
    assert ratio == pytest.approx(q_xe ** 2 / q_ar ** 2, rel=1e-6)


def _ohare_signal(e_kev, m_chi, a, sigma=1e-45):
    """O'Hare's WIMPFuncs.dRdE with his analytic SHM (independent of ADROIT's halo code): per tonne-year per keV."""
    sig_v, v_esc, v_lab = 167.0, 533.0, 245.6
    n_esc = erf(v_esc / (math.sqrt(2) * sig_v)) - math.sqrt(2 / math.pi) * v_esc / sig_v * math.exp(-v_esc ** 2 / (2 * sig_v ** 2))
    v0 = sig_v * math.sqrt(2)
    m_p, m_n = 0.931494e6, a * 0.931494e6
    mu_p, mu_n = 1e6 * m_chi * m_p / (1e6 * m_chi + m_p), 1e6 * m_chi * m_n / (1e6 * m_chi + m_n)
    x = np.sqrt(m_n * e_kev / 2) / mu_n * nf.C_KM_S / v0
    y, z = v_lab / v0, v_esc / v0
    g = (erf(x + y) - erf(x - y) - 4 / math.sqrt(math.pi) * y * math.exp(-z ** 2)) / (2 * n_esc * v0 * y)
    r0 = (nf.C_KM_S * 1e5) ** 2 * 0.3e6 * a ** 2 * sigma / (2 * m_chi * 1e6 * 1.782661921e-33 * mu_p ** 2)
    from adroit.physics.nuclear import helm_form_factor
    ff = helm_form_factor(np.sqrt(2 * a * 0.931494 * e_kev * 1e-6), a) ** 2
    return r0 * g / 1e5 * ff * nf.YEAR_S * 1000


def test_the_signal_rate_is_the_standard_formula_with_adroits_halo():
    e = np.array([1.0, 5.0, 20.0])
    ours = nf.signal_density(e, 100.0, 131, nf.ohare_halo())
    assert ours == pytest.approx(_ohare_signal(e, 100.0, 131), rel=2e-3)


def test_the_discovery_limit_passes_through_three_regimes():
    # a background shaped exactly as the signal, known to δ = 0.1%: no background (n ≈ 1), Poisson subtraction (n ≈ 2),
    # then saturation at σ_sat = 3δ σ_ref, below which no exposure discovers the signal
    shape = np.exp(-np.linspace(0, 3, 20))
    sigmas = np.logspace(-50, -42, 200)
    exposure, status = nf.discovery_exposure(shape, np.array([shape]), np.array([1e-3]), sigmas, (1e-8, 1e14))
    assert set(status) <= {"reached", "not reached"}
    index, floor = nf.index_and_floor(sigmas, exposure, cap=1e14)
    events = exposure * shape.sum()
    assert 0.9 < np.nanmedian(index[events < 0.01]) < 1.4
    assert 1.85 < np.nanmedian(index[(events > 30) & (events < 1e4)]) < 2.1
    saturation = 3 * 1e-3 * nf.REFERENCE_SIGMA
    assert saturation < sigmas[np.isfinite(exposure)].min() < 1.5 * saturation
    assert saturation < floor < 30 * saturation and np.nanmax(index) > 2


def test_q0_vanishes_without_signal_and_grows_with_it():
    rates = np.array([np.ones(10), np.linspace(1, 2, 10)])
    signal_row = np.linspace(2, 0.1, 10)
    q = nf.asimov_q0(np.repeat(signal_row[None], 3, 0), rates, np.array([0.1, 0.2]), np.full(3, 10.0),
                     np.array([0.0, 1e-46, 1e-45]))
    assert abs(q[0]) < 1e-9 and 0 < q[1] < q[2]


def test_the_published_floor_is_the_standard_curve():
    masses, sigmas = nf.published_floor('Xe')
    assert masses[0] == pytest.approx(0.1) and len(masses) > 100
    assert nf.floor_at(100.0) == pytest.approx(6.29e-49, rel=0.02)     # O'Hare's Xe_SI.txt (8.5e-49 had passed unread)
    assert nf.floor_at(1e6) is None
    with pytest.raises(ValueError, match='no published floor'):
        nf.published_floor('Pb')


def test_a_coarse_xenon_fog_follows_the_published_floor():
    fog = nf.fog(nf.FogSettings(masses_gev=(20.0, 1000.0, 3), sigmas_cm2=(1e-50, 1e-44, 150)))
    for m, f in zip(fog.masses_gev, fog.floor_cm2):
        assert f == pytest.approx(nf.floor_at(m), rel=0.3)          # a coarse σ grid; the gate is in the slow test


def _with_ohares_line_factor(monkeypatch):
    """O'Hare's code multiplies a monochromatic flux's rate by its energy in MeV (NeutrinoFuncs.dRdE, the line
    branch); ADROIT does not. The diagnostic that explains the gate's sub-GeV miss (docs/neutrino_fog.md)."""
    original = nf.cevns_density
    monkeypatch.setattr(nf, 'cevns_density',
                        lambda e, flux, n, z: original(e, flux, n, z) * (flux.endpoint_mev if flux.line else 1.0))


@pytest.mark.slow
def test_the_floor_reproduces_ohares_published_floors(monkeypatch):
    """The declared gate (docs/neutrino_fog.md), with his settings (single isotopes, his halo, 500 σ points, his
    normalisation of each spectrum: ``binning='ohare'``): within
    5% of the published floor at every mass. As built it is met above 3 GeV (xenon, germanium) and 10 GeV (argon) and
    missed below (up to 13%, where the ⁷Be and pep lines set the floor); with his line factor it is met at every mass."""
    targets = (('Xe131', 'Xe', 30, 3.0), ('Ar40', 'Ar', 8, 10.0), ('Ge74', 'Ge', 8, 3.0))
    for target, element, points, low in targets:          # argon's lines reach higher masses (a lighter nucleus)
        fog = nf.fog(nf.FogSettings(target=target, masses_gev=(low, 1e4, points // 2), binning='ohare'))
        for m, f in zip(fog.masses_gev, fog.floor_cm2):
            assert f is not None and abs(f / nf.floor_at(m, element) - 1) < 0.05, (target, m)
    _with_ohares_line_factor(monkeypatch)
    for target, element, points, _ in targets:
        fog = nf.fog(nf.FogSettings(target=target, masses_gev=(0.1, 1e4, points), binning='ohare'))
        for m, f in zip(fog.masses_gev, fog.floor_cm2):
            assert f is not None and abs(f / nf.floor_at(m, element) - 1) < 0.05, (target, m, 'his line factor')


def test_the_point_inspector_places_an_si_prediction_against_xenons_floor():
    from types import SimpleNamespace
    from adroit.evidence.points import fog_of
    beneath = fog_of(SimpleNamespace(dd_kind='SI', dd_sigma_cm2=1e-49, point=SimpleNamespace(m_chi=100.0)))
    assert beneath['beneath'] and beneath['floor_cm2'] == pytest.approx(nf.floor_at(100.0))
    assert not fog_of(SimpleNamespace(dd_kind='SI', dd_sigma_cm2=1e-46, point=SimpleNamespace(m_chi=100.0)))['beneath']
    assert fog_of(SimpleNamespace(dd_kind='SD-proton', dd_sigma_cm2=1e-49, point=SimpleNamespace(m_chi=100.0))) == {}
    assert fog_of(None) == {}


def _path1_result():
    from adroit.orchestrator import exclusion
    request = exclusion.ExclusionRequest(card_id='O1', values={'c_p': 2e-6, 'c_n': 2e-6}, masses_gev=[10.0, 100.0, 1000.0])
    limits = exclusion.ModuleLimits(experiment='synthetic', masses_gev=[10.0, 100.0, 1000.0], mu_up=[0.5, 0.2, 0.4],
                                    validated=[True, True, True], route='reference SI', fidelity='A')
    return exclusion.ExclusionResult(request=request, interaction_name='O1', per_module=[limits])


def test_path_one_draws_si_limits_over_the_neutrino_fog(tmp_path):
    from adroit.orchestrator import exclusion
    result = _path1_result()
    predicted = exclusion.si_predictions(result)
    assert predicted is not None and len(predicted) == 3 and all(p > 0 for p in predicted)
    assert predicted[0] == pytest.approx(predicted[1], rel=1.0)      # σ_SI of a fixed contact varies only with μ_N
    assert exclusion.sigma_plot(result, tmp_path / 'sigma.png', predicted).is_file()
    section = exclusion.fog_section(result, predicted)
    assert 'exclusion_sigma_si.png' in section and 'An annotation, not a constraint' in section
    assert section.count('above the floor') + section.count('beneath the floor') == 3
    sd = result.model_copy(update={'request': result.request.model_copy(update={'card_id': 'O4', 'values': {}})})
    assert exclusion.si_predictions(sd) is None


def test_the_fog_commands_write_the_standard_floor_and_a_map(tmp_path):
    from typer.testing import CliRunner
    from adroit.orchestrator.cli import app
    done = CliRunner().invoke(app, ['fog', 'standard', '--target', 'Xe', '--out', str(tmp_path / 'standard')])
    assert done.exit_code == 0, done.output
    assert (tmp_path / 'standard' / 'floor.csv').read_text().startswith('mass_gev,sigma_cm2\n0.1,')
    done = CliRunner().invoke(app, ['fog', 'map', '--masses', '20:1000:2', '--sigmas', '1e-50:1e-44:80',
                                    '--scale', 'atmospheric=0.5', '--out', str(tmp_path / 'map')])
    assert done.exit_code == 0, done.output
    report = (tmp_path / 'map' / 'report.md').read_text()
    assert '| Atm | 0.125 |' in report and (tmp_path / 'map' / 'fog.png').is_file()
    assert '*Read as found.*' in report                             # a diagnostic output (the owner, 2026-11-03)
    refused = CliRunner().invoke(app, ['fog', 'map', '--masses', 'ten', '--out', str(tmp_path / 'bad')])
    assert refused.exit_code != 0


def test_q0_is_stable_at_any_exposure_and_failures_are_not_read_as_not_reached():
    """The focused audit's NF-01: one bin with background E and signal 0.31 E, δ = 0.1, against the closed form
    (q₀ → 0.31²/0.1² = 9.61): the deviance does not cancel at 10¹⁸; a bin with signal and no background makes q₀
    infinite (background-free); the reachable discovery is reached under the default exposure cap."""
    for exposure in (1.0, 1e6, 1e14, 1e18, 1e19):
        n, b, d = exposure * 1.31, exposure, 0.1
        phi = 2 * n * d * d / (b * d * d - 1 + math.sqrt((b * d * d - 1) ** 2 + 4 * n * d * d))
        z = (b * phi - n) / n
        closed = 2 * n * (z - math.log1p(z) if abs(z) > 1e-3 else z * z / 2 - z ** 3 / 3 + z ** 4 / 4) \
            + (phi - 1) ** 2 / d ** 2
        q = nf.asimov_q0(np.ones((1, 1)), np.ones((1, 1)), np.array([d]), np.array([exposure]),
                         np.array([0.31 * nf.REFERENCE_SIGMA]))[0]
        assert q == pytest.approx(closed, rel=1e-9)
    assert nf.asimov_q0(np.array([[0.0, 1.0]]), np.array([[1.0, 0.0]]), np.array([0.1]), np.array([1.0]),
                        np.array([nf.REFERENCE_SIGMA]))[0] == math.inf
    exposure, status = nf.discovery_exposure(np.ones(1), np.ones((1, 1)), np.array([0.1]),
                                             np.array([0.31e-45, 0.2e-45]), (1e-5, 1e19))
    assert list(status) == ["reached", "not reached"] and math.isfinite(exposure[0])
    _, free = nf.discovery_exposure(np.array([0.0, 1.0]), np.array([[1.0, 0.0]]), np.array([0.1]),
                                    np.array([1e-45]), (1e-5, 1e19))
    assert list(free) == ["background-free"]
    with pytest.raises(ValueError, match="finite and positive"):
        nf.asimov_q0(np.ones((1, 1)), np.ones((1, 1)), np.array([0.0]), np.array([1.0]), np.array([1e-45]))


def test_the_recoil_window_counts_only_the_recoils_inside_it():
    """NF-02: ⁸B on xenon-131 above 10⁻⁴ keV; the binned count equals the direct integral over the window (the
    ``ohare`` reproduction normalises to the whole spectrum instead, as his code does)."""
    from scipy.integrate import quad
    flux = next(f for f in nf.FLUXES if f.name == "8B")
    others = [f.name for f in nf.FLUXES if f.name != "8B"]
    for top in (1.0, 5.0):
        settings = nf.FogSettings(max_recoil_kev=top, exclude=others)
        direct = quad(lambda e: float(nf.cevns_density(np.array([e]), flux, 77, 54)[0]), settings.threshold_kev, top,
                      points=[v for v in (1.0, 2.0, 4.0) if v < top], limit=200)[0]
        assert nf.background(settings)[1].sum() == pytest.approx(direct, rel=1e-4)
    legacy = nf.FogSettings(max_recoil_kev=1.0, exclude=others, binning="ohare")
    assert nf.background(legacy)[1].sum() > 1.1 * nf.background(legacy.model_copy(update={"binning": "window"}))[1].sum()


def test_settings_are_validated_and_a_compound_target_is_resolved():
    """NF-04 and NF-05."""
    assert nf.target_of("CaWO4").name == "CaWO4" and nf.target_of("Xe131").isotopes[0].mass_number == 131
    assert nf.published_target("CaWO4") == "CaWO4" and nf.published_target("Xe131") == "Xe"
    assert nf.published_target("Xe") == "Xe" and nf.published_target("Si28") is None
    for bad in ({"uncertainties": {"8B": -0.02}}, {"uncertainties": {"8B": 0.0}}, {"group_scale": {"solar": math.inf}},
                {"threshold_kev": 300.0}, {"masses_gev": (10.0, 1.0, 5)}, {"exposure_ton_year": (1.0, 1.0)}):
        with pytest.raises(ValueError):
            nf.FogSettings(**bad)


def test_a_flux_held_at_zero_does_not_stop_the_others_converging():
    """FR-05 (the recheck's boundary control): one flux driven to zero while the other is far from its optimum. The
    profile meets the bound-constrained optimality conditions: q₀ equals an independent L-BFGS-B solution (71625.67 at
    exposure 10⁴, φ = (6.331, 0); 7.16257 with widths 10 at exposure 1, below the discovery threshold 9), where the
    clipped Newton step had stopped at 193457 and 19.35."""
    from scipy.optimize import minimize
    rates, signal_row = np.array([[1.0, 1.0], [0.0, 1.0]]), np.array([[10.0, 0.0]])
    for exposure, width in ((1e4, 0.1), (1.0, 10.0)):
        q0 = nf.asimov_q0(signal_row, rates, np.array([width, width]), np.array([exposure]),
                          np.array([nf.REFERENCE_SIGMA]))[0]
        b, n = exposure * rates, exposure * (signal_row[0] + rates.sum(0))

        def nll(phi):
            mu = phi @ b
            return float(np.sum(mu - n + n * np.log(n / mu)) + 0.5 * np.sum((phi - 1) ** 2) / width ** 2)
        best = minimize(nll, np.ones(2), method='L-BFGS-B', bounds=[(1e-12, None)] * 2, options={'ftol': 1e-15})
        assert q0 == pytest.approx(2 * best.fun, rel=1e-6)
    assert q0 < 9.0

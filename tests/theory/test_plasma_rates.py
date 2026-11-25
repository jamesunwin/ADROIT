"""M27's leading-order plasma rates (the owner's request of 2026-10-19), validated only against their limits: the
vacuum Maxwell–Boltzmann limit, the collinear leading logarithm, Maxwell–Boltzmann statistics at large ΔM/T and
detailed balance; and the certificate's physical prerequisite."""

import math

import numpy as np
import pytest
from scipy.special import kve

from adroit.core.chemical_equilibrium import PlasmaRatePoint, PlasmaSettings
from adroit.theory import plasma_rates as pl
from adroit.theory import source_born as sb
from adroit.theory.chemical_equilibrium import certify
from test_source_born import source_inputs

M_CHI, M_PHI, Y, G = 8000.0, 8400.0, 1e-5, 0.357
VACUUM = (sb.ELECTRON_MASS, 0.0, M_PHI)


def test_with_a_massless_b_the_cross_section_is_the_vacuum_codes():
    for channel in pl.CHANNELS:
        for root in (8401.0, 9000.0, 15000.0):
            ours = pl.cross_section(root ** 2, M_CHI, M_PHI, sb.ELECTRON_MASS, 0.0, channel)
            assert ours == pytest.approx(sb.cross_section(root ** 2, M_CHI, M_PHI, sb.ELECTRON_MASS, channel), rel=1e-9)


def test_the_vacuum_maxwell_boltzmann_limit_is_the_source_rate():
    T = M_CHI / 25
    for channel in pl.CHANNELS:
        reference = sb.scattering_rate(M_CHI, M_PHI, Y, G, T, channel, 0.5, refined=True)
        ours = pl.scattering_rate(M_CHI, M_PHI, Y, G, T, channel, VACUUM, statistics=False, cut=0.5)
        assert ours == pytest.approx(reference, rel=1.5e-3)
    unblocked = pl.decay_rate(M_CHI, M_PHI, Y, T, VACUUM, statistics=False)
    from adroit.theory.conversion_amplitudes import decay_width
    assert unblocked == pytest.approx(decay_width(M_CHI, M_PHI, sb.ELECTRON_MASS, Y)
                                      * float(kve(1, M_PHI / T) / kve(2, M_PHI / T)), rel=1e-10)


def _weyl_collinear_coefficient(s: float) -> float:
    """The coefficient of ln(1/m_e²) in σ(χ B → φ e) at unit couplings: the Weyl splitting B → e_R ē, averaged over
    the B's polarisations, (α/2π)[x² + (1 − x)²]/2, times the narrow inverse decay σ(χ ē → φ) = (π/2) δ(ŝ − M²)."""
    x0 = (M_PHI ** 2 - M_CHI ** 2) / (s - M_CHI ** 2)
    return (x0 ** 2 + (1 - x0) ** 2) / (32 * math.pi * (s - M_CHI ** 2))


def test_the_collinear_logarithm_has_the_factorised_coefficient():
    for root in (8450.0, 9500.0):
        s = root ** 2
        a, b = 1e-3, 1e-5
        slope = ((pl.cross_section(s, M_CHI, M_PHI, b, 0.0, "chi_B", 192)
                  - pl.cross_section(s, M_CHI, M_PHI, a, 0.0, "chi_B", 192)) / (math.log(a * a) - math.log(b * b)))
        assert slope == pytest.approx(_weyl_collinear_coefficient(s), rel=1e-3)


def test_the_plasma_codes_logarithm_is_the_thermal_average_of_that_coefficient():
    T = M_CHI / 25
    me, mb, _ = pl.thermal_masses(T, G, M_PHI)
    values = [pl.scattering_rate(M_CHI, M_PHI, Y, G, T, "chi_B", (k * me, k * mb, M_PHI), statistics=False,
                                 nodes=(24, 24, 64, 12), angles=96) for k in (1e-3, 1e-4)]
    slope = (values[1] - values[0]) / (math.log(1e8) - math.log(1e6))
    w = np.geomspace(1e-6 * T, 80 * T, 4000)
    root = M_PHI + w
    weight = kve(1, root / T) / kve(2, M_CHI / T) * np.exp(-(root - M_CHI) / T)
    average = Y * Y * G * G * np.trapezoid(_weyl_collinear_coefficient(root ** 2) * (root ** 2 - M_CHI ** 2) ** 2
                                           * weight * w, np.log(w)) / (2 * math.pi ** 2 * M_CHI ** 2)
    assert slope == pytest.approx(average, rel=5e-3)


def test_incoming_statistics_and_decay_blocking_become_maxwell_boltzmann_at_large_splitting():
    M, T = 12000.0, M_CHI / 50                     # ΔM/T = 25
    masses = pl.thermal_masses(T, G, M)
    for channel in pl.CHANNELS:
        quantum = pl.scattering_rate(M_CHI, M, Y, G, T, channel, masses, statistics="incoming")
        classical = pl.scattering_rate(M_CHI, M, Y, G, T, channel, masses, statistics=False)
        assert quantum == pytest.approx(classical, rel=1e-5)
    assert pl.decay_rate(M_CHI, M, Y, T, masses) == pytest.approx(pl.decay_rate(M_CHI, M, Y, T, masses, False), rel=1e-6)


def test_inverse_decays_are_the_decays_by_detailed_balance():
    for x in (10.0, 45.0):
        T = M_CHI / x
        masses = pl.thermal_masses(T, G, M_PHI)
        up = pl.inverse_decay_rate(M_CHI, M_PHI, Y, T, masses)
        down = pl.decay_rate(M_CHI, M_PHI, Y, T, masses)
        assert up == pytest.approx(down * pl.equilibrium_ratio(M_CHI, masses[2], T), rel=1e-10)
        assert down < pl.decay_rate(M_CHI, M_PHI, Y, T, masses, statistics=False)      # Pauli blocking


def test_the_thermal_masses_close_b_to_e_ebar():
    me, mb, MT = pl.thermal_masses(500.0, G, M_PHI)
    assert mb < 2 * me and MT > M_PHI
    assert me == pytest.approx(sb.thermal_mass(500.0, G), rel=1e-6)                   # the existing regulator


@pytest.fixture
def fresh():
    """``certify`` is memoised on its inputs: clear it around a test that stubs the plasma rates."""
    from adroit.theory import chemical_equilibrium as ce
    ce._cached.cache_clear()
    yield
    ce._cached.cache_clear()


def _plasma(y: float):
    inputs = source_inputs(y)
    inputs.request.plasma = PlasmaSettings(scheme="leading_order_asymptotic_masses_quantum_statistics")
    return inputs


@pytest.mark.parametrize('scale,expected', [(1e4, 'supported'), (1e-4, 'failed'), (1.0, 'unresolved')])
def test_the_physical_prerequisite_is_decided_by_the_plasma_bank(monkeypatch, fresh, scale, expected):
    def point(inputs, x):
        return PlasmaRatePoint(x=x, temperature_gev=1.0, hubble_gev=1.0,
                               rates_over_h={'0.5': 150.0 * scale, '1.0': 140.0 * scale, '2.0': 120.0 * scale})
    monkeypatch.setattr(pl, 'rate_point', point)
    c = certify(_plasma(3e-5))
    assert c.physical_prerequisite == expected and c.algorithm_version == 5 and c.plasma_rates
    assert c.component_prerequisite == 'supported'                       # the component certificate unchanged
    assert any('leading order in the plasma' in r for r in c.reasons)


def test_a_request_without_plasma_keeps_its_identity_and_result():
    plain = certify(source_inputs(3e-5))
    assert 'plasma' not in source_inputs(3e-5).request.model_dump(mode='json')
    assert plain.physical_prerequisite == 'pending' and not plain.plasma_rates and plain.algorithm_version == 4
    assert 'plasma_rates' not in plain.model_dump(mode='json')
    assert certify(_plasma(3e-5)).parameter_sha256 != plain.parameter_sha256


def test_the_portal_reads_the_plasma_decision(monkeypatch, fresh):
    from adroit.parameter_space.portals.tchannel import TChannel

    def point(inputs, x):
        return PlasmaRatePoint(x=x, temperature_gev=1.0, hubble_gev=1.0, rates_over_h={'0.5': 1e-3, '1.0': 1e-3,
                                                                                         '2.0': 1e-3})
    monkeypatch.setattr(pl, 'rate_point', point)
    inputs = _plasma(3e-5)
    cls = TChannel(partner='eR', conversion=inputs.request)
    assert any('fails at leading order in the plasma' in f for f in cls.flags(inputs.point))
    assert any('failed at leading order in the plasma' in p for p in cls.pending(inputs.point))


@pytest.mark.slow
def test_a_certificate_with_the_plasma_rates():
    c = certify(_plasma(3e-5))
    assert c.physical_prerequisite in ('supported', 'failed', 'unresolved') and len(c.plasma_rates) == 9
    for row in c.plasma_rates:
        assert row.rates_over_h['0.5'] > 0 and set(row.rates_over_h) == {'0.5', '1.0', '2.0'}


# --- the audit of 2026-10-19 (PX-07, PX-08) ------------------------------------------------------------------------

def _crossing(m: float, T: float, g: float, scale: float) -> float:
    """The partner's mass at which χ B's incoming threshold, m + m_B, meets φ e's outgoing one, M_T + m_e."""
    from scipy.optimize import brentq
    me, mb, _ = pl.thermal_masses(T, g, m, scale)
    return brentq(lambda M: pl.thermal_masses(T, g, M, scale)[2] + me - m - mb, m, m + 10 * mb)


def test_a_compressed_spectrum_with_a_heavy_thermal_b_has_finite_continuous_rates():
    """PX-07: with a small splitting the incoming threshold m_χ + m_B can exceed M_T + m_e; the table starts at the
    higher one, so every rate is finite and positive (8 TeV, 1% splitting, T = 800 GeV had given NaN) and the rate
    is continuous where the two thresholds cross."""
    g = source_inputs(3e-5).g_prime
    for scale in pl.SCALES:
        masses = pl.thermal_masses(800.0, g, 8080.0, scale)
        for channel in pl.CHANNELS:
            rate = pl.scattering_rate(8000.0, 8080.0, 1.0, g, 800.0, channel, masses)
            assert math.isfinite(rate) and rate > 0
    M = _crossing(8000.0, 800.0, g, 2.0)
    below, above = (pl.scattering_rate(8000.0, x, 1.0, g, 800.0, "chi_B", pl.thermal_masses(800.0, g, x, 2.0))
                    for x in (M * (1 - 1e-5), M * (1 + 1e-5)))
    assert below == pytest.approx(above, rel=1e-2)


@pytest.mark.parametrize('rates', [{'0.5': float('nan'), '1.0': 1e4, '2.0': 1e4}, {'0.5': 1e4, '1.0': 1e4}])
def test_a_nonfinite_or_incomplete_bank_is_unresolved(monkeypatch, fresh, rates):
    """PX-07: a bank with a NaN or a missing scale decides nothing, even where every other entry passes."""
    monkeypatch.setattr(pl, 'rate_point', lambda inputs, x: PlasmaRatePoint(x=x, temperature_gev=1.0, hubble_gev=1.0,
                                                                            rates_over_h=rates))
    c = certify(_plasma(3e-5))
    assert c.physical_prerequisite == 'unresolved' and not c.plasma_rates and c.algorithm_version == 5
    assert any('bank is incomplete' in r for r in c.reasons)


def test_a_failed_plasma_calculation_keeps_the_prerequisite_pending(monkeypatch, fresh):
    """PX-08: asked for and failed, the plasma rates leave the prerequisite pending; the component certificate's
    support does not take their place."""
    from adroit.parameter_space.portals.tchannel import TChannel

    def fail(inputs, x):
        raise ArithmeticError('synthetic unresolved quadrature')
    monkeypatch.setattr(pl, 'rate_point', fail)
    inputs = _plasma(3e-5)
    c = certify(inputs)
    assert c.component_prerequisite == 'supported' and c.physical_prerequisite == 'unresolved' and not c.plasma_rates
    cls = TChannel(partner='eR', conversion=inputs.request)
    assert any('unresolved at leading order in the plasma' in p for p in cls.pending(inputs.point))
    assert not any('component accuracy' in f for f in cls.flags(inputs.point))

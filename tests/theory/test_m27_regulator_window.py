"""R5 (audit M11): the chemical-equilibrium certificate survives a thermal-mass regulator and is tied to freeze-out."""

import math

import numpy as np
import pytest

from adroit.constraints import relic
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.theory.chemical_equilibrium import certify
from test_source_born import source_inputs


def _audit_point(y: float):
    p = source_inputs(y)
    p.point.m_chi, p.point.m_med = 8000.0, 8080.0
    return p


def test_the_audits_flip_example_is_unresolved_under_the_thermal_regulator():
    """At (8000, 8080, y = 1.6e-5) the vacuum-regulated bank gave min Γ/H = 176 (supported); with the plasma's
    electron mass in the bank the conservative bound falls below the threshold of 100."""
    c = certify(_audit_point(1.6e-5))
    assert c.status == "unresolved" and c.component_prerequisite == "unresolved" and c.algorithm_version == 4
    assert c.minimum_relaxation_over_h < 100
    for row in c.rates:
        assert row.regulator_rates_over_h["thermal"] == min(row.regulator_rates_over_h.values())


def test_the_plasma_mass_cuts_the_scattering_well_below_the_vacuum_regulators():
    from adroit.theory.source_born import scattering_rate, thermal_mass
    from adroit.constraints.kinetic_mixing import G_PRIME
    T = 8000.0 / 25
    for channel in ("chi_B", "chi_ebar"):
        vacuum = scattering_rate(8000.0, 8080.0, 1e-5, G_PRIME, T, channel, 0.5)
        plasma = scattering_rate(8000.0, 8080.0, 1e-5, G_PRIME, T, channel, 0.5, mf=thermal_mass(T, G_PRIME))
        assert 0.02 < plasma / vacuum < 0.5
    assert thermal_mass(T, G_PRIME) == pytest.approx(G_PRIME * T / 2, rel=1e-6)


def test_a_window_that_misses_freeze_out_is_refused_and_one_that_brackets_it_starts_there():
    p = _audit_point(3e-5)
    late = p.request.model_copy(update={"x_low": 45.0, "x_high": 50.0})
    cls = TChannel(partner="eR", conversion=late)
    c = cls.chemical_certificate(p.point)
    assert c.status == "unresolved" and "does not bracket" in c.reasons[0]
    assert any("coannihilation chemical equilibrium" in reason for reason in cls.pending(p.point))
    wide = TChannel(partner="eR", conversion=p.request.model_copy(update={"x_low": 10.0, "x_high": 50.0}))
    c = wide.chemical_certificate(p.point)
    x_f = wide.freeze_out_x(p.point)
    assert 15 < x_f < 30 and c.inputs.request.x_low == pytest.approx(x_f) and c.rates[0].x == pytest.approx(x_f)


def test_freeze_out_x_is_where_the_yield_doubles_its_equilibrium_value():
    m, x_nodes = 100.0, np.geomspace(1.0, 2e4, 140)
    sigma_v = np.full_like(x_nodes, 2.2e-26 / 1.1673e-17)            # a thermal WIMP, cm³/s → GeV⁻²
    x_f = relic.freeze_out_x(m, x_nodes, sigma_v)
    assert 18 < x_f < 28


def test_majorana_freeze_out_without_a_bath_counts_two_states():
    """Audit minor: dirac=False without log_yeq used g = 4."""
    m, x_nodes = 100.0, np.geomspace(1.0, 2e4, 140)
    sigma_v = np.full_like(x_nodes, 2e-9)
    majorana = relic.freeze_out(m, x_nodes, sigma_v, dirac=False)
    by_hand = relic.freeze_out(m, x_nodes, sigma_v, log_yeq=lambda x: relic.log_equilibrium_yield(x, m, 2.0))
    assert majorana == pytest.approx(by_hand, rel=1e-9)
    assert not math.isclose(majorana, relic.freeze_out(m, x_nodes, sigma_v, log_yeq=lambda x: relic.log_equilibrium_yield(x, m, 4.0)), rel_tol=1e-3)


def test_a_missing_freeze_out_refuses_the_window(monkeypatch):
    """Mini audit: with x_f = None the declared window was used, and [45, 50] passed."""
    from adroit.parameter_space.portals import tchannel
    p = _audit_point(1.6e-5)
    late = p.request.model_copy(update={"x_low": 45.0, "x_high": 50.0})
    monkeypatch.setattr(tchannel, "_freeze_out_x", lambda cls_json, point_json: None)
    cls = TChannel(partner="eR", conversion=late)
    c = cls.chemical_certificate(p.point)
    assert c.status == "unresolved" and c.component_prerequisite == "unresolved" and "no freeze-out" in c.reasons[0]
    assert any("coannihilation chemical equilibrium" in reason for reason in cls.pending(p.point))


def test_the_thermal_variant_gives_the_decays_the_same_plasma_mass():
    """The owner (2026-10-12): the thermal-mass variant is consistent: φ → χ e and its inverse use the electron's
    plasma mass too, and close when m_φ < m_χ + m_f (thermal blocking)."""
    from adroit.constraints.kinetic_mixing import G_PRIME
    from adroit.theory.conversion_amplitudes import decay_width
    from adroit.theory.conversion_rates import ELECTRON_MASS
    from adroit.theory.source_born import _cached, thermal_mass
    T = 8000.0 / 10                                                        # m_f = g′T/2 = 143 GeV
    plasma = thermal_mass(T, G_PRIME)
    assert plasma > 80.0 and decay_width(8000.0, 8080.0, ELECTRON_MASS, 1.0) > 0
    assert decay_width(8000.0, 8080.0, plasma, 1.0) == 0.0                 # 80 GeV split < m_f: blocked
    assert 0 < decay_width(8000.0, 8080.0, thermal_mass(320.0, G_PRIME), 1.0) < decay_width(8000.0, 8080.0, ELECTRON_MASS, 1.0)
    point = _cached(_audit_point(1.6e-5).model_dump_json(), 10.0)
    vacuum_decays = point.decay_down_gev * (1 + point.partner_to_chi_equilibrium_ratio) / point.hubble_gev
    thermal = point.regulator_rates_over_h["thermal"]
    assert thermal < point.regulator_rates_over_h["0.5"] - 0.5 * vacuum_decays   # the vacuum decays are not in it

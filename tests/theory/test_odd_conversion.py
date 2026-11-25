"""External Majorana exchange, traces, symmetry factors and thermal detailed balance."""

import math
import numpy as np
import pytest
from scipy.special import kv
from adroit.constraints import processes as pr
from adroit.constraints.amplitudes import _BASIS, bar, spinor_u, slash, GAMMA
from adroit.constraints.relic import thermal_average
from adroit.theory.odd_conversion import (
    conversion_chain,
    squared,
    cross_section,
    thermal_rate,
    equilibrium_relaxation,
)
from test_conversion_rates import example


def test_majorana_chain_against_explicit_external_antisymmetrization():
    x = np.array([-0.8, 0.0, 0.7])
    m, M, mf = 100.0, 105.0, 0.000511
    for root in (220, 250, 400):
        a, b, c, d, _, _ = pr.frame(root**2, m, m, M, M, x)
        total = np.zeros(3)

        def diagram(chi, scalar, left, right):
            q = chi - scalar
            chain = pr.P_R @ slash(q) @ pr.P_L / (pr._dot(q, q) - mf * mf)[:, None, None]
            return np.einsum("ni,nij,nj->n", left, chain, right)

        for xi in _BASIS:
            one = spinor_u(a[:, 1:], m, xi)
            vone = bar(pr.conjugate(one))
            for eta in _BASIS:
                two = spinor_u(b[:, 1:], m, eta)
                vtwo = bar(pr.conjugate(two))
                amplitude = diagram(a, c, vtwo, one) - diagram(b, c, vone, two)
                total += abs(amplitude) ** 2
        assert np.allclose(total, squared(a, b, c, d, m, mf), rtol=1e-12, atol=1e-12)
        C = conversion_chain(a, c, d, mf)
        adj = GAMMA[0] @ C.conj().transpose(0, 2, 1) @ GAMMA[0]
        trace = np.trace(
            (slash(b) - m * pr.UNIT) @ C @ (slash(a) + m * pr.UNIT) @ adj, axis1=1, axis2=2
        ).real
        assert np.allclose(total, trace, rtol=1e-12, atol=1e-12)


def test_forward_reverse_degeneracies_and_threshold():
    m, M, mf, y = 100.0, 105.0, 0.000511, 0.03
    for root in (211.0, 250.0, 500.0):
        s = root**2
        a = cross_section(s, m, M, mf, y)
        b = cross_section(s, m, M, mf, y, reverse=True)
        assert b / a == pytest.approx(2 * (s - 4 * m * m) / (s - 4 * M * M), rel=1e-11)
        assert cross_section(s, m, M, mf, 2 * y) == pytest.approx(16 * a)
    assert cross_section((2 * M) ** 2, m, M, mf, y) == 0
    with pytest.raises(ValueError):
        cross_section(0, m, M, mf, y)


def test_thermal_detailed_balance_and_linearized_eigenvalue():
    m, M, mf, y, x = 100.0, 105.0, 0.000511, 0.03, 25.0
    T = m / x
    u = np.r_[0.0, np.geomspace(1e-9, 80, 1801)]
    sig = np.array(
        [cross_section(float((2 * M * (1 + v)) ** 2), m, M, mf, y, True, 128) for v in u]
    )
    reverse = float(thermal_average(u, sig, np.array([M / T]))[0])
    forward = thermal_rate(m, M, mf, y, x, True)
    nc = 2 * m * m * T * kv(2, x) / (2 * math.pi**2)
    npart = 2 * M * M * T * kv(2, M / T) / (2 * math.pi**2)
    assert nc * nc * forward == pytest.approx(0.5 * npart * npart * reverse, rel=0.002)
    sv, relaxation = equilibrium_relaxation(m, M, mf, y, x, True)
    r = npart / nc
    # Independent Jacobian in the two physical number densities.
    J = np.array([[-2 * sv * nc, 2 * sv * npart / r**2], [2 * sv * nc, -2 * sv * npart / r**2]])
    assert sorted(np.linalg.eigvals(J))[0] == pytest.approx(-relaxation, rel=1e-12)
    assert sorted(np.linalg.eigvals(J))[1] == pytest.approx(0, abs=1e-24)
    assert thermal_rate(m, M, mf, y, x) == pytest.approx(forward, rel=0.002)


def test_odd_sector_requires_explicit_opt_in_and_does_not_create_physical_pass():
    from adroit.theory.conversion_rates import rate_point
    from adroit.theory.chemical_equilibrium import certify

    p = example(3e-5)
    assert rate_point(p, 25).odd_sector_sigma_v_gev2 is None
    p.request.include_odd_sector = True
    rate = rate_point(p, 25)
    assert rate.odd_sector_sigma_v_gev2 > 0 and rate.odd_sector_relaxation_gev > 0
    assert rate.odd_sector_quadrature_difference < 0.002
    c = certify(p)
    assert c.passed is None and c.physical_prerequisite == "pending"
    assert len(c.missing_channels) == 2 and any(
        "phi_dagger" in channel for channel in c.required_channels
    )

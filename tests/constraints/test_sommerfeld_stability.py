"""The Sommerfeld solver's exact channel thresholds, without moving sample energies."""
import numpy as np
import pytest

from adroit.constraints import sommerfeld
from adroit.parameter_space.portals import multiplet


def square_well_amplitude(potential, thresholds, mu, energy, radius):
    """Match exact matrix sine/hyperbolic-sine solutions at the edge of a well."""
    eigenvalues, vectors = np.linalg.eigh(2 * mu * (potential + np.diag(thresholds - energy)))
    k = np.sqrt(np.abs(eigenvalues))
    u = vectors @ np.diag(np.where(eigenvalues > 0, np.sinh(k * radius), np.sin(k * radius)) / k) @ vectors.T
    du = vectors @ np.diag(np.where(eigenvalues > 0, np.cosh(k * radius), np.cos(k * radius))) @ vectors.T
    matrix, rhs = np.zeros((4, 4), complex), np.zeros(4, complex)
    for i, threshold in enumerate(thresholds):
        momentum = np.sqrt(2 * mu * abs(energy - threshold))
        matrix[i, :2], matrix[i + 2, :2] = u[i], du[i]
        if energy > threshold:
            h = np.exp(1j * momentum * radius) / momentum
            dh = 1j * np.exp(1j * momentum * radius)
            rhs[i], rhs[i + 2] = np.sin(momentum * radius) / momentum, np.cos(momentum * radius)
        else:
            h, dh = 1, -momentum
        matrix[i, i + 2], matrix[i + 2, i + 2] = -h, -dh
    return np.linalg.solve(matrix, rhs)[:2]


def test_free_channel_at_its_exact_threshold_matches_an_analytic_coupled_well():
    mu, energy, radius = 500., 1., .05
    thresholds = np.array([0., 1.])
    well = np.array([[0., -.5], [-.5, 0.]])
    expected = square_well_amplitude(well, thresholds, mu, energy, radius)
    result = sommerfeld.enhancement(lambda r: well if r < radius else np.zeros((2, 2)),
                                    thresholds, np.zeros(2), mu, energy, r_max=.25)
    assert result[:, 0] == pytest.approx(expected, rel=2e-7, abs=1e-9)
    assert result[:, 1] == pytest.approx([0., 0.], abs=0)


@pytest.mark.parametrize('alpha_mu', [-1.7, 0., 1.7])
def test_zero_energy_wave_satisfies_the_coulomb_equation(alpha_mu):
    r, step = .3, 1e-6
    def logarithmic_derivative(radius):
        h, dh = sommerfeld._threshold_wave(alpha_mu, radius)
        assert np.isfinite(h) and np.isfinite(dh) and h != 0
        return dh / h
    slope = logarithmic_derivative(r)
    derivative = (logarithmic_derivative(r + step) - logarithmic_derivative(r - step)) / (2 * step)
    assert derivative + slope ** 2 == pytest.approx(-2 * alpha_mu / r, rel=1e-8, abs=1e-8)
    if alpha_mu > 0:
        assert slope.imag > 0  # outward flux
    elif alpha_mu < 0:
        assert slope.real < 0 and slope.imag == 0  # decaying wave


def test_higgsino_exact_threshold_matches_the_positive_energy_coulomb_limit():
    sector = multiplet.higgsino_sectors(3000.)[0]
    def amplitude(offset):
        return sommerfeld.enhancement(sector.potential, sector.thresholds * .6, sector.tails,
                                       1500., 1.2 + offset, r_max=30 / multiplet.M_W)
    threshold = amplitude(0.)
    assert np.all(np.isfinite(threshold))
    assert threshold[:, 0] == pytest.approx([0., 0.], abs=0)
    above, nearer = amplitude(1e-4)[:, 1], amplitude(1e-5)[:, 1]
    assert threshold[:, 1] == pytest.approx(nearer, rel=1e-5)
    assert np.linalg.norm(nearer - threshold[:, 1]) < np.linalg.norm(above - threshold[:, 1]) / 8


def test_zero_momentum_free_asymptotic_basis_is_finite():
    assert sommerfeld._asymptotic(0., 0., .3, False) == (0., 0., 1., 0.)


def test_a_rounding_error_below_a_coulomb_threshold_is_the_threshold():
    """The wino at M = 1 TeV: the neutral pair's sample energy K = 0.4 GeV meets the charged pair's threshold 2δ.
    With δ = 0.2 + 4×10⁻¹⁷ GeV the charged channel is 5.6×10⁻¹⁷ GeV below it: before the fix a closed channel with
    η ≈ 1.6×10⁷ and a NaN amplitude (which stopped Ωh² with a non-finite Jacobian)."""
    sector = multiplet.wino_sectors(1000.)[0]
    def amplitude(delta):
        thresholds = sector.thresholds * delta
        energy = thresholds[1] - thresholds.min() + 0.25 * 1000. * 0.04 ** 2
        return sommerfeld.enhancement(sector.potential, thresholds - thresholds.min(), sector.tails, 500., energy,
                                      r_max=30 / multiplet.M_W)
    exact, rounded = amplitude(0.2), amplitude(0.20000000000000004)
    assert np.all(np.isfinite(rounded))
    assert rounded == pytest.approx(exact, rel=1e-9, abs=0)


def test_re_orthonormalising_the_solutions_leaves_the_amplitudes_unchanged(monkeypatch):
    """The stretched integration (``sommerfeld.GROWTH``) gives the single pass's amplitudes where both work."""
    from adroit.constraints import endpoint_nll as nll
    from adroit.constraints import sommerfeld
    single = nll.amplitudes(5, 5000.0, 1e-3)
    monkeypatch.setattr(sommerfeld, "GROWTH", 0.0)
    stretched = nll.amplitudes(5, 5000.0, 1e-3)
    assert all(abs(stretched[q] - single[q]) <= 1e-5 * abs(single[q]) for q in single)


def test_a_heavy_quintuplets_closed_channels_do_not_swamp_the_solutions():
    """At 70 TeV κr_max ~ 100 for the χ⁺⁺χ⁻⁻ pair: a single pass loses the solutions (a tree line of 10⁻³⁹ cm³/s);
    re-orthonormalised, the line is the paper's order, 10⁻²⁷–10⁻²⁵."""
    from adroit.constraints import endpoint_nll as nll
    s = nll.amplitudes(5, 70000.0, 1e-3)
    assert 1e-28 < nll.tree_line(70000.0, 5, s) < 1e-24


def test_a_deeply_closed_channel_does_not_underflow():
    """The audit's G8-3 (G12): beyond κr ≈ 720 the closed wave e^{−κr} underflowed to 0 and the matching was singular
    (a quintuplet at 20 TeV and v = 10⁻⁴; a 13-plet's line at 2 TeV). Only its log-derivative is used now."""
    import cmath

    from adroit.constraints import endpoint_nll as nll
    s = nll.amplitudes(5, 20000.0, 1e-4)
    assert all(cmath.isfinite(x) and abs(x) > 1.0 for x in s.values())
    assert 0.0 < nll.line_sigma_v(13, 2000.0) < 1e-18

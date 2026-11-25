"""Reuse identical wave equations, never the sector's distinct annihilation matrix."""
import numpy as np

from adroit.parameter_space.portals import multiplet as mp


def test_shared_potential_reuses_amplitudes_but_keeps_spin_dependent_rates(monkeypatch):
    sectors = mp.higgsino_sectors(1100.)
    assert sectors[0].potential is sectors[1].potential
    calls = []
    def solve(*args, **kwargs):
        calls.append((args, kwargs))
        return np.array([[1., .2j], [.3, 1.]], dtype=complex)
    monkeypatch.setattr(mp.sommerfeld, 'enhancement', solve)
    cache = {}
    kinetic = np.array([.01, 1.])
    first = mp._sector_rates(sectors[0], 1100., .341, kinetic, True, cache)
    second = mp._sector_rates(sectors[1], 1100., .341, kinetic, True, cache)
    assert len(calls) == 4 and not np.array_equal(first, second)
    reference = mp._sector_rates(sectors[1], 1100., .341, kinetic, True)
    assert len(calls) == 8 and np.array_equal(second, reference)
    assert all(not matrix.flags.writeable for matrix in cache.values())


def test_changed_mass_splitting_tail_or_potential_does_not_reuse_a_wave_equation(monkeypatch):
    calls = []
    def solve(*args, **kwargs):
        calls.append(1)
        return np.eye(len(args[1]), dtype=complex)
    monkeypatch.setattr(mp.sommerfeld, 'enhancement', solve)
    sector = mp.higgsino_sectors(1100.)[0]
    cache, kinetic = {}, np.array([.01])
    mp._sector_rates(sector, 1100., .341, kinetic, True, cache)
    assert len(calls) == 2
    mp._sector_rates(sector, 1100., .4, kinetic, True, cache)
    assert len(calls) == 4
    mp._sector_rates(sector, 1200., .341, kinetic, True, cache)
    assert len(calls) == 6
    sector.tails = sector.tails + .001
    mp._sector_rates(sector, 1100., .341, kinetic, True, cache)
    assert len(calls) == 8
    sector.potential = lambda r: np.zeros((2, 2))
    mp._sector_rates(sector, 1100., .341, kinetic, True, cache)
    assert len(calls) == 10


def test_tree_rates_do_not_invoke_the_wave_solver(monkeypatch):
    def unavailable(*args, **kwargs):
        raise AssertionError('wave solver called with Sommerfeld switched off')
    monkeypatch.setattr(mp.sommerfeld, 'enhancement', unavailable)
    sector = mp.higgsino_sectors(1100.)[0]
    result = mp._sector_rates(sector, 1100., .341, np.array([.01, 1.]), False, {})
    assert np.array_equal(result, np.repeat(np.diag(sector.gamma)[:, None], 2, axis=1))


def test_real_shared_solver_keeps_the_exact_charged_threshold_finite():
    sectors = mp.higgsino_sectors(3000.)
    kinetic, cache = np.array([.01, 1.2]), {}
    for sector in sectors[:2]:
        shared = mp._sector_rates(sector, 3000., .6, kinetic, True, cache)
        separate = mp._sector_rates(sector, 3000., .6, kinetic, True)
        assert np.isfinite(shared).all() and np.array_equal(shared, separate)
